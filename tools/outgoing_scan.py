"""The one scanner every outgoing-safety check uses, over the one gate that runs it.

Three kinds of thing must never leave: a project's declared private vocabulary,
a credential, and a local filesystem path. The vocabulary is project data — one
project's private identifier is another's ordinary product noun — while
credentials and paths are structural and the same everywhere. That split is why
a `Scanner` is constructed from a `TermSet` rather than being a free function.

A commit is not the only place text lives. The object range being sent carries
blob contents, path names, commit messages, author and committer identities,
annotated tag objects with their own messages and taggers, and the name of the
ref itself. A gate that reads commit messages catches one of those six and
reports clean on the rest, which is worse than no gate because it is believed.

Two properties are deliberate:

*   **The range, not the tip.** Private material three commits back is in the
    range. `baseline=None` means the whole history, which is what a first push
    actually sends.
*   **Nothing is skipped silently.** A blob too large or too binary to scan is
    recorded in `skipped`, and a report with skips is `clean` only when there
    are none — `clean` is tri-state (leaks / skips / clean), never collapsed to
    a boolean that reads "skipped" as "passed".

A project may declare paths whose *content* is exempt. This is not an override
and it is deliberately narrow: some files in a security-conscious project **are**
the denylist, or the negative fixtures for it — or, as here, a reviewed-baseline
record that itself names a prior match — and a scanner that cannot be told so is
one that gets switched off. The exemption covers **the project's own
vocabulary in blob content**, and nothing else: the path itself, every
reference and tag name, every message and every identity are still scanned, the
universal rules — credential, local path, private identifier — still apply to
the exempted blob's content, and every exempted blob is named in `exempted`, so
the report says what it narrowed rather than reading clean.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import gitread
import pathmatch
from commit_gate import (
    _CREDENTIAL_PATTERNS,
    _UUID,
    TermSet,
    NO_PRIVATE_TERMS,
    _redact,
    _term_set_from_args,
    contains_local_path,
)

__all__ = ["Leak", "Scanner", "OutgoingReport", "SkippedObject", "scan_outgoing"]

#: What a leak *is*, as opposed to where it was found. The location is
#: supplied by the caller that knows which Git object it was reading.
LEAK_KINDS = ("private_term", "private_pattern", "credential", "local_path", "private_identifier")

#: Rules a *project* declares, in its own vocabulary. What counts as private
#: here depends entirely on whose repository it is.
VOCABULARY_LEAK_KINDS = ("private_term", "private_pattern")

#: Rules that hold for **every** project, because what they find is private
#: whoever wrote it: a credential, a path naming somebody's machine and
#: account, a generated identifier. No repository has a reason to carry these,
#: so no project gets to declare them acceptable.
UNIVERSAL_LEAK_KINDS = ("credential", "local_path", "private_identifier")

#: What a declared content exemption may switch off: **the project's own
#: vocabulary, and nothing else.**
#:
#: RP2.2 (CA-AMD-5 / RP-EC-1) found the sentence above stated and not
#: implemented. An exempted blob was not scanned at all, so a project that
#: exempted `fixtures/` to stop its denylist matching itself also switched off
#: credential and local-path detection for everything under it. Reproduced: an
#: AWS-shaped key and a path naming a home directory, both inside an exempted
#: file, reported `clean`.
#:
#: The exemption exists for a real case — a file that *is* the denylist, or the
#: negative fixtures for it — and that case is entirely about the project's own
#: vocabulary. It was never about credentials, and a credential in a fixture is
#: exactly the thing somebody should have to look at.
EXEMPTIBLE_LEAK_KINDS = VOCABULARY_LEAK_KINDS

#: Blobs above this size are recorded as skipped rather than read into memory.
MAX_SCANNED_BLOB_BYTES = 5 * 1024 * 1024

#: How much of a blob is inspected to decide whether it is text.
_BINARY_SNIFF_BYTES = 8192


@dataclass(frozen=True)
class Leak:
    kind: str
    location: str
    subject: str
    detail: str

    def __post_init__(self) -> None:
        if self.kind not in LEAK_KINDS:
            raise ValueError(f"unknown leak kind {self.kind!r}")


#: Surfaces holding content nobody wrote as a deliberate label. The identity
#: tier of the vocabulary does not reach these — see `TermSet` for the measured
#: reason. Everything else (commit messages, ref and tag names, identities,
#: repository paths) is something a person chose to write, and gets the whole
#: vocabulary.
CONTENT_LOCATIONS = ("blob",)


class Scanner:
    """Finds every prohibited thing in a piece of text, not the first one.

    ``strict`` applies the identity tier to blob content too. It is for the
    **staged** gate, and the asymmetry is deliberate: strict where a correction
    costs one edit, tiered where it costs a commit, a fixup and a rebase.

    Without it the tiering has a hole. Process vocabulary
    reaches prose *about* the work — a test docstring, a
    repair note, a committed file's own description — and the bare-word forms
    (`harness`, `envelope`) are exactly what the identity tier stops applying to
    content. The multi-word forms (`engineering harness`, `worker envelope`)
    still fire everywhere and carry most of the real signal, but "most" is not
    the claim to make about a leak gate.
    """

    __slots__ = ("_terms", "_patterns", "_strict")

    def __init__(self, term_set: TermSet, *, strict: bool = False) -> None:
        self._terms = term_set
        self._strict = strict
        compiled: dict[str, re.Pattern[str]] = {}
        for pattern_text in (*term_set.patterns, *term_set.identity_patterns):
            try:
                compiled[pattern_text] = re.compile(pattern_text, re.IGNORECASE)
            except re.error as exc:
                # A declared pattern that will not compile is a contract
                # defect. Raising here is right: the alternative is a scanner
                # that silently checks less than the project asked it to.
                raise ValueError(f"declared private pattern {pattern_text!r} is not a regex: {exc}") from exc
        self._patterns = compiled

    @property
    def vocabulary(self) -> TermSet:
        """The term set this scanner applies, so a report can disclose it."""
        return self._terms

    def scan(self, text: object, *, location: str, subject: str) -> list[Leak]:
        """Every prohibited thing in ``text``, described without reproducing it."""
        if text is None:
            return []
        if isinstance(text, bytes):
            text = text.decode("utf-8", "surrogateescape")
        if not isinstance(text, str):
            raise TypeError(f"scannable text must be str or bytes, not {type(text).__name__}")

        content_surface = location in CONTENT_LOCATIONS and not self._strict
        leaks: list[Leak] = []
        for term, pattern in self._terms.compiled_terms(content_surface=content_surface):
            if pattern.search(text):
                leaks.append(Leak("private_term", location, subject, f"declared private term {_redact(term)!r}"))
        for pattern_text in self._terms.applicable_patterns(content_surface=content_surface):
            match = self._patterns[pattern_text].search(text)
            if match:
                leaks.append(
                    Leak("private_pattern", location, subject,
                         f"declared private pattern {pattern_text!r} matched {_redact(match.group(0))!r}")
                )
        for name, pattern in _CREDENTIAL_PATTERNS:
            if pattern.search(text):
                leaks.append(Leak("credential", location, subject, f"credential-shaped token ({name})"))
        if contains_local_path(text):
            leaks.append(Leak("local_path", location, subject, "a local filesystem path"))
        if _UUID.search(text):
            leaks.append(Leak("private_identifier", location, subject, "a UUID-shaped private identifier"))
        return leaks

    def scan_name(self, name: str, *, location: str, subject: str) -> list[Leak]:
        """A path or ref name, checked for everything except being a path.

        The local-path rule is about *content* mentioning a machine's layout.
        A repository path is a path by definition, so applying that rule here
        would reject every file.
        """
        return [leak for leak in self.scan(name, location=location, subject=subject) if leak.kind != "local_path"]


@dataclass(frozen=True)
class SkippedObject:
    sha: str
    path: str
    reason: str


@dataclass
class OutgoingReport:
    ref: str
    baseline: str | None
    leaks: list[Leak] = field(default_factory=list)
    skipped: list[SkippedObject] = field(default_factory=list)
    exempted: list[str] = field(default_factory=list)
    commits_examined: int = 0
    blobs_examined: int = 0
    #: What vocabulary actually ran. A report that does not say what it loaded
    #: cannot be audited, and the motivating defect was a scan that applied
    #: none of the default rules and printed `clean`.
    vocabulary: str = ""
    #: Exemption patterns the project declared that matched no path in this
    #: range. A dead declaration is silent otherwise, which is exactly how one
    #: survived unnoticed until a deliberate A/B run.
    unused_exemptions: list[str] = field(default_factory=list)
    #: For each offending path, how many distinct blobs of it are reachable.
    #: More than one means the earlier commit still carries the material and
    #: amending the tip will not clear it.
    blob_multiplicity: dict[str, int] = field(default_factory=dict)

    @property
    def clean(self) -> bool:
        """No leaks, and nothing the gate could not read.

        A skipped blob is not `clean`, on the reasoning that a blob the
        scanner could not read is a blob it cannot vouch for. A project that
        legitimately ships unreadable content declares it, which makes it
        `exempted` — a decision somebody took — instead of `skipped`.
        """
        return not self.leaks and not self.skipped

    def render(self) -> str:
        """A rendering that never claims more than the data behind it.

        `clean` is a verdict over leaks and skips only — an exempted blob is
        still `clean` at the data level, by design. But this string is what
        gets stored as durable evidence, read later by someone who did not
        run the scan, so a rendering that says only "clean" for a range that
        declined to read something by declaration is a verdict standing in
        for a disclosure. Every rendering path below must name what it did
        not read, whether or not the range is `clean`.
        """
        header = f"outgoing range {self.baseline or 'ROOT'}..{self.ref}"
        provenance = [f"  rules applied: {self.vocabulary}"] if self.vocabulary else []
        # An exemption count is printed even when it is zero. `0 file(s)
        # content-exempt by declaration` beats silence: a declaration that
        # matched nothing produced a report byte-identical to one where it
        # matched, and that is what made a dead exemption invisible.
        exemption_lines = [
            f"  {len(self.exempted)} file(s) content-exempt by declaration "
            "(project vocabulary only; credential, local-path and identifier rules still applied)"
        ]
        exemption_lines.extend(f"    content exempt by declaration: {path}" for path in self.exempted)
        exemption_lines.extend(
            f"    DECLARED BUT MATCHED NOTHING: {pattern}" for pattern in self.unused_exemptions
        )

        if self.clean:
            lines = [
                f"{header}: clean ({self.commits_examined} commits, {self.blobs_examined} blobs)"
            ]
            lines.extend(provenance)
            lines.extend(exemption_lines)
            return "\n".join(lines)

        lines = [f"{header}: {len(self.leaks)} leak(s)"]
        lines.extend(provenance)
        for leak in self.leaks:
            lines.append(f"  {leak.location} {leak.subject}: {leak.detail}")
            reachable = self.blob_multiplicity.get(leak.subject, 0)
            if leak.location == "blob" and reachable > 1:
                # The natural repair is to fix the text and amend. When the same
                # path has more than one reachable blob, amending moves only the
                # tip: the finding count drops, which reads as progress, and the
                # range is still dirty. Say so where the remedy is chosen.
                lines.append(
                    f"    {reachable} distinct blobs of this path are reachable — "
                    f"amending the tip will not clear the earlier one; rebuild the branch"
                )
        for item in self.skipped:
            lines.append(f"  not scanned: {item.path or item.sha} ({item.reason})")
        lines.extend(exemption_lines)
        return "\n".join(lines)


def _decoded(data: bytes) -> str | None:
    """The text of a blob, or ``None`` when it genuinely is not text.

    UTF-16 is the case that matters: it is full of NUL bytes and it is
    ordinary text a person wrote. Treating a NUL as proof of binary content
    meant a UTF-16 file full of private material was recorded as unscannable
    and passed.
    """
    head = data[:_BINARY_SNIFF_BYTES]
    if b"\x00" not in head:
        return data.decode("utf-8", "surrogateescape")
    for encoding in ("utf-16", "utf-32"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def scan_outgoing(
    repository: str | Path,
    *,
    ref: str,
    baseline: str | None,
    scanner: Scanner,
    content_exempt_paths: Sequence[str] = (),
) -> OutgoingReport:
    """Scan every object, name and identity in the range ``baseline..ref``.

    ``content_exempt_paths`` names files whose *content* the project has
    declared to be denylist data, negative fixtures, or a reviewed-baseline
    record of prior matches. Their paths are still scanned, and each is listed
    in the report.
    """
    if not isinstance(scanner, Scanner):
        raise TypeError("an outgoing scan requires a Scanner built from the project's declared terms")
    report = OutgoingReport(ref=ref, baseline=baseline, vocabulary=scanner.vocabulary.summary())
    exempt_patterns = tuple(content_exempt_paths)
    exemptions_used: set[str] = set()
    blobs_by_path: dict[str, set[str]] = {}

    # The ref name travels with the objects. `HEAD` is not a name anyone
    # receives, so it is not scanned as one.
    if ref != "HEAD" and not _looks_like_sha(ref):
        report.leaks.extend(scanner.scan_name(ref, location="ref_name", subject=ref))

    # Paths come from the trees, not from the object listing. A blob already
    # reachable from the baseline is not listed, so a file *moved* into a
    # directory with a private name produced a listing in which that name
    # never appeared.
    for path in gitread.paths_in_outgoing_range(repository, ref, baseline):
        report.leaks.extend(scanner.scan_name(path, location="path", subject=path))

    for sha, path in gitread.objects_in_outgoing_range(repository, ref, baseline):
        kind = gitread.object_type(repository, sha)
        if kind == "commit":
            report.commits_examined += 1
            report.leaks.extend(
                scanner.scan(gitread.commit_message(repository, sha), location="commit_message", subject=sha[:12])
            )
            metadata = gitread.commit_metadata(repository, sha)
            for role in ("author", "committer"):
                identity = f"{metadata[f'{role}_name']} <{metadata[f'{role}_email']}>"
                report.leaks.extend(scanner.scan(identity, location=role, subject=sha[:12]))
        elif kind == "tag":
            # An annotated tag is in the object range in its own right — Git
            # lists it alongside the commit it points at.
            tag = gitread.tag_object(repository, sha)
            name = tag["tag"] or path
            report.leaks.extend(scanner.scan(tag["message"], location="tag_message", subject=name))
            report.leaks.extend(scanner.scan(tag["tagger"], location="tag_tagger", subject=name))
            report.leaks.extend(scanner.scan_name(name, location="tag_name", subject=name))
        elif kind == "blob":
            if path:
                blobs_by_path.setdefault(path, set()).add(sha)
            size = gitread.object_size(repository, sha)
            if size > MAX_SCANNED_BLOB_BYTES:
                report.skipped.append(SkippedObject(sha, path, f"{size} bytes exceeds the scan limit"))
                continue
            engaged = _engaged_exemptions(path, exempt_patterns) if path else []
            exempted = bool(engaged) and _is_exempt(path, exempt_patterns)
            if engaged:
                exemptions_used.update(engaged)
            if exempted:
                report.exempted.append(path)
            data = gitread.object_bytes(repository, sha)
            text = _decoded(data)
            if text is None:
                report.skipped.append(SkippedObject(sha, path, "content is not decodable as text"))
                continue
            report.blobs_examined += 1
            report.leaks.extend(
                _scoped(scanner.scan(text, location="blob", subject=path or sha[:12]), exempted)
            )
        elif kind == "tree":
            # Paths inside a tree arrive as the second column of the object
            # listing, so they are scanned with their blobs.
            continue

    report.unused_exemptions = [p for p in exempt_patterns if p not in exemptions_used]
    report.blob_multiplicity = {path: len(shas) for path, shas in blobs_by_path.items()}
    return report


def scan_staged(
    repository: str | Path,
    *,
    scanner: Scanner,
    content_exempt_paths: Sequence[str] = (),
) -> OutgoingReport:
    """Scan what the index would commit, before the commit exists.

    The range scan is the gate that must hold, and it runs at closure. This one
    runs while the sentence is still being written. Private vocabulary
    reaches prose *about* the work — a test module docstring, a repair note, a
    committed file's own description — and a range scan catches it only at
    closure, where the remedy is a
    commit, a fixup and a rebase rather than an edit.

    It is deliberately not a hook. A hook is machine configuration outside the
    pack's boundary, it does not travel with the project, and a gate a project
    cannot see is a gate it cannot audit.

    This gate is **strict**: the identity tier applies to staged content as
    well. Here a false positive costs one reword before the text is committed,
    so the tiering that protects committed history from noise is not needed and
    would only reopen the hole it was measured to leave.
    """
    if not isinstance(scanner, Scanner):
        raise TypeError("a staged scan requires a Scanner built from the project's declared terms")
    report = OutgoingReport(ref="INDEX", baseline="HEAD", vocabulary=scanner.vocabulary.summary() + ", strict")
    exempt_patterns = tuple(content_exempt_paths)
    exemptions_used: set[str] = set()

    for path, sha in gitread.staged_entries(repository):
        report.leaks.extend(scanner.scan_name(path, location="path", subject=path))
        engaged = _engaged_exemptions(path, exempt_patterns)
        exempted = bool(engaged) and _is_exempt(path, exempt_patterns)
        if engaged:
            exemptions_used.update(engaged)
        if exempted:
            report.exempted.append(path)
        if gitread.object_size(repository, sha) > MAX_SCANNED_BLOB_BYTES:
            report.skipped.append(SkippedObject(sha, path, "exceeds the scan limit"))
            continue
        text = _decoded(gitread.object_bytes(repository, sha))
        if text is None:
            report.skipped.append(SkippedObject(sha, path, "content is not decodable as text"))
            continue
        report.blobs_examined += 1
        report.leaks.extend(_scoped(scanner.scan(text, location="blob", subject=path), exempted))

    report.unused_exemptions = [p for p in exempt_patterns if p not in exemptions_used]
    return report


def _scoped(leaks: list[Leak], exempted: bool) -> list[Leak]:
    """Apply a declared content exemption to one blob's findings.

    An exemption removes the project's **own vocabulary** and leaves every
    universal rule in force. Not implemented as "skip the blob", which is what
    it was: skipping is indistinguishable from exempting everything, and the
    difference is a credential.
    """
    if not exempted:
        return leaks
    return [leak for leak in leaks if leak.kind not in EXEMPTIBLE_LEAK_KINDS]


def _engaged_exemptions(path: str, patterns: Sequence[str]) -> list[str]:
    """Which declared exemptions **engage** this path, under gitignore semantics.

    One semantics for every path declaration in the pack (`pathmatch`). This
    used to be `fnmatch`, which meant a directory exemption written the way the
    contract template documents — `annotations/` — matched nothing at all, and
    said so nowhere.

    Engagement, not coverage. A negation (`!fixtures/real-notes.md`) engages the
    path it names and *removes* it from the exemption, so it belongs in the
    used-declarations bookkeeping while contributing nothing to coverage. Ask
    :func:`_is_exempt` for the verdict.
    """
    exact = [pattern for pattern in patterns if path == pattern]
    return exact + [p for p in pathmatch.matching_patterns(path, patterns) if p not in exact]


def _is_exempt(path: str, patterns: Sequence[str]) -> bool:
    """Whether the declared exemptions, read in order, cover this path."""
    return pathmatch.matches_any(path, patterns)


def _looks_like_sha(ref: str) -> bool:
    return len(ref) >= 7 and all(character in "0123456789abcdef" for character in ref.lower())


def _cli(argv: list[str]) -> int:
    """Scan a range in a repository and print findings.

    Usage: ``outgoing_scan.py REPO REF [BASELINE] [--exempt PATH ...] [--term TERM ...] [--pattern REGEX ...]``
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="outgoing_scan.py",
        description="Scan every object, name and identity an outgoing range would send.",
    )
    parser.add_argument("repository", nargs="?", help="path to the Git repository; defaults to the contract's repo_path")
    parser.add_argument("ref", nargs="?", help="the ref or SHA whose outgoing range is scanned")
    parser.add_argument("baseline", nargs="?", default=None, help="the baseline the range is relative to; omit for the whole history")
    parser.add_argument("--project", help="path to PROJECT.yaml; supplies vocabulary, exemptions and repo path")
    parser.add_argument("--exempt", action="append", default=[], metavar="PATH", help="a path whose blob content is exempt (repeatable, additive)")
    parser.add_argument("--term", action="append", default=[], help="a declared private term (repeatable, additive)")
    parser.add_argument("--pattern", action="append", default=[], help="a declared private regex pattern (repeatable, additive)")
    parser.add_argument("--staged", action="store_true", help="scan the staged diff instead of a committed range")
    args = parser.parse_args(argv)

    contract = None
    if args.project:
        from project_contract import ContractError, ProjectContract

        try:
            contract = ProjectContract.load(args.project)
        except ContractError as exc:
            # Stated, and distinctly: exit 2, never 0. A gate that could not
            # read its own rules has not passed, and this is the one place
            # where a traceback would be indistinguishable from a crash.
            print(f"CONTRACT UNREADABLE {exc}")
            return 2
        # With `--project` supplying the repository, the positionals are
        # [REF] [BASELINE] rather than [REPO] [REF] [BASELINE]. Without this
        # shift `outgoing_scan --project P main` bound "main" to `repository`
        # and then refused for want of a ref — the contract was supplying the
        # repo path and the command line was still being read as though it
        # were not.
        if args.repository is not None and args.ref is None and contract.repo_path:
            args.repository, args.ref, args.baseline = None, args.repository, args.baseline

    try:
        term_set = _term_set_from_args(args)
    except Exception as exc:
        print(f"CONTRACT UNREADABLE {exc}")
        return 2
    scanner = Scanner(term_set)

    repository = args.repository or (contract.repository() if contract else None)
    if not repository:
        print("a repository is required, either positionally or via --project")
        return 2
    exempt = [*(contract.content_exempt if contract else ()), *args.exempt]

    if args.staged:
        # The staged diff, checked before the commit exists. Process vocabulary
        # reaching prose *about* the work — a test docstring, a repair note, a
        # file's own description — is otherwise
        # caught at closure, when the remedy costs a commit, a fixup and a
        # rebase. Here the sentence is still being written.
        report = scan_staged(
            repository, scanner=Scanner(term_set, strict=True), content_exempt_paths=exempt
        )
        print(report.render())
        return 0 if report.clean else 1

    if not args.ref:
        print("a ref is required unless --staged is given")
        return 2
    report = scan_outgoing(
        repository, ref=args.ref, baseline=args.baseline,
        scanner=scanner, content_exempt_paths=exempt,
    )
    print(report.render())
    return 0 if report.clean else 1


if __name__ == "__main__":
    import sys

    from errors import run_cli

    raise SystemExit(run_cli(_cli, sys.argv[1:]))
