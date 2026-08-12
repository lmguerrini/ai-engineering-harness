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
one that gets switched off. The exemption covers blob content only: the path
itself, every reference and tag name, every message and every identity are
still scanned, and every exempted blob is named in `exempted`, so the report
says what it did not read rather than reading clean.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import gitread
from commit_gate import _CREDENTIAL_PATTERNS, _UUID, TermSet, NO_PRIVATE_TERMS, _redact, contains_local_path

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


class Scanner:
    """Finds every prohibited thing in a piece of text, not the first one."""

    __slots__ = ("_terms", "_patterns")

    def __init__(self, term_set: TermSet) -> None:
        self._terms = term_set
        compiled: list[tuple[str, re.Pattern[str]]] = []
        for pattern_text in term_set.patterns:
            try:
                compiled.append((pattern_text, re.compile(pattern_text, re.IGNORECASE)))
            except re.error as exc:
                # A declared pattern that will not compile is a contract
                # defect. Raising here is right: the alternative is a scanner
                # that silently checks less than the project asked it to.
                raise ValueError(f"declared private pattern {pattern_text!r} is not a regex: {exc}") from exc
        self._patterns = tuple(compiled)

    def scan(self, text: object, *, location: str, subject: str) -> list[Leak]:
        """Every prohibited thing in ``text``, described without reproducing it."""
        if text is None:
            return []
        if isinstance(text, bytes):
            text = text.decode("utf-8", "surrogateescape")
        if not isinstance(text, str):
            raise TypeError(f"scannable text must be str or bytes, not {type(text).__name__}")

        leaks: list[Leak] = []
        for term, pattern in self._terms.compiled_terms():
            if pattern.search(text):
                leaks.append(Leak("private_term", location, subject, f"declared private term {_redact(term)!r}"))
        for pattern_text, compiled in self._patterns:
            match = compiled.search(text)
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
        if self.clean and not self.exempted:
            return (
                f"outgoing range {self.baseline or 'ROOT'}..{self.ref}: clean "
                f"({self.commits_examined} commits, {self.blobs_examined} blobs)"
            )
        if self.clean:
            # Clean implies no skips (`clean` is `not leaks and not skipped`),
            # so the only thing left to disclose here is the exemption list.
            lines = [
                f"outgoing range {self.baseline or 'ROOT'}..{self.ref}: clean, "
                f"{len(self.exempted)} file(s) content-exempt by declaration "
                f"({self.commits_examined} commits, {self.blobs_examined} blobs)"
            ]
            for path in self.exempted:
                lines.append(f"  content exempt by declaration: {path}")
            return "\n".join(lines)
        lines = [f"outgoing range {self.baseline or 'ROOT'}..{self.ref}: {len(self.leaks)} leak(s)"]
        for leak in self.leaks:
            lines.append(f"  {leak.location} {leak.subject}: {leak.detail}")
        for item in self.skipped:
            lines.append(f"  not scanned: {item.path or item.sha} ({item.reason})")
        for path in self.exempted:
            lines.append(f"  content exempt by declaration: {path}")
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
    report = OutgoingReport(ref=ref, baseline=baseline)

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
            size = gitread.object_size(repository, sha)
            if size > MAX_SCANNED_BLOB_BYTES:
                report.skipped.append(SkippedObject(sha, path, f"{size} bytes exceeds the scan limit"))
                continue
            if path and _matches_exempt(path, content_exempt_paths):
                report.exempted.append(path)
                continue
            data = gitread.object_bytes(repository, sha)
            text = _decoded(data)
            if text is None:
                report.skipped.append(SkippedObject(sha, path, "content is not decodable as text"))
                continue
            report.blobs_examined += 1
            report.leaks.extend(scanner.scan(text, location="blob", subject=path or sha[:12]))
        elif kind == "tree":
            # Paths inside a tree arrive as the second column of the object
            # listing, so they are scanned with their blobs.
            continue
    return report


def _matches_exempt(path: str, patterns: Sequence[str]) -> bool:
    """Whether a project declared this path's content to be denylist data."""
    import fnmatch

    return any(path == pattern or fnmatch.fnmatch(path, pattern) for pattern in patterns)


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
    parser.add_argument("repository", help="path to the Git repository")
    parser.add_argument("ref", help="the ref or SHA whose outgoing range is scanned")
    parser.add_argument("baseline", nargs="?", default=None, help="the baseline the range is relative to; omit for the whole history")
    parser.add_argument("--exempt", action="append", default=[], metavar="PATH", help="a path whose blob content is exempt (repeatable)")
    parser.add_argument("--term", action="append", default=[], help="a declared private term (repeatable)")
    parser.add_argument("--pattern", action="append", default=[], help="a declared private regex pattern (repeatable)")
    args = parser.parse_args(argv)

    term_set = TermSet.of(args.term, args.pattern) if (args.term or args.pattern) else NO_PRIVATE_TERMS
    scanner = Scanner(term_set)
    report = scan_outgoing(
        args.repository, ref=args.ref, baseline=args.baseline,
        scanner=scanner, content_exempt_paths=args.exempt,
    )
    print(report.render())
    return 0 if report.clean else 1


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
