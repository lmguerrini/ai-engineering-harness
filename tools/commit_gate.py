"""The public commit contract.

Every commit has exactly this shape::

    <project-facing title>
    <blank line>
    - <project-facing engineering/product outcome>
    - <project-facing engineering/product outcome>

with two to four bullets (frozen decision D4: exactly-three cost rejected
commits and added no safety over a bounded range). This module is a pure
function over a message string plus a project term set. It holds no I/O and no
Git knowledge so that it can be applied identically before a commit is created,
after it is read back from the created object, and retroactively over an
entire existing history.

Two classes of rule are enforced.

*Structural* rules hold for every project and are not configurable: the shape,
trailers, ``Co-authored-by``, literal ``\\n`` escapes, filesystem paths,
credential-shaped tokens, and UUIDs. These are the rules whose violation could
not plausibly be project-facing language in any project.

*Vocabulary* rules come from the project's private-term set. They are
**required**, not optional: :func:`validate_message` will not run without a
term set, because a validator that silently degrades to "no forbidden words"
when a caller forgets an argument is worse than no validator — it reports
success. A project that genuinely declares no private terms passes
:data:`NO_PRIVATE_TERMS` explicitly, which is a recorded decision rather than
an omission.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

from errors import CommitContractError

__all__ = [
    "ContractViolation",
    "TermSet",
    "NO_PRIVATE_TERMS",
    "validate_message",
    "assert_valid",
    "SHAPE",
]

#: Two to four bullets, per D4. The first through the second-to-last bullet
#: require a trailing newline; the final bullet's is optional, so a message
#: that does not end in a newline still matches.
SHAPE = re.compile(r"\A.+\n\n(?:- .+\n){1,3}- .+\n?\Z")

_LITERAL_NEWLINE = re.compile(r"\\n")
_COAUTHOR = re.compile(r"co-authored-by", re.IGNORECASE)
# Includes the Unicode line and paragraph separators. Python's ``.`` matches
# them, so without this they can smuggle a visual line break past the shape.
_CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\r\x85\u2028\u2029]")
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

# A trailer is a line — with or without a bullet marker — that opens with a
# trailer-shaped token followed by a colon. Hyphenated capitalised tokens
# (``Relates-to:``, ``Change-Id:``, ``Signed-off-by:``) are trailer syntax by
# construction; single-word tokens are matched against the conventional set so
# that an ordinary bullet like "- Retry: bounded backoff" is not a false
# positive.
# The colon does not have to be followed by a space: Git parses
# ``Signed-off-by:someone`` as a trailer just as readily as the spaced form.
_TRAILER_HYPHENATED = re.compile(r"(?m)^(?:-\s+)?[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+:")
_TRAILER_TOKENS = re.compile(
    r"(?mi)^(?:-\s+)?(?:signed|reviewed|acked|tested|reported|suggested|helped"
    r"|cc|refs|ref|closes|close|fixes|fix|resolves|resolve|change-id|bug|ticket"
    r"|issue|see-also|link)\s*:",
)

#: A Conventional Commit subject. `fix` is in the trailer token set above, so a
#: perfectly ordinary `fix: correct the parser` was refused as `TRAILER` while
#: `feat: …` passed — reproduced by execution, and blocking, because the commit
#: contract asks for a Conventional Commit subject in the first place. A gate
#: that refuses the form its own contract requires is not strict, it is wrong.
#:
#: The exemption is deliberately narrow, and narrower than it first was. Only
#: the matched **prefix** is removed from the subject before trailer detection
#: runs — not the subject line. Blanking the line let
#: `fix: Signed-off-by: A Person` pass clean, which an independent audit caught:
#: the exemption exists so `fix:` stops looking like a trailer token, not so the
#: rest of the subject stops being read. A real trailer does not become legal by
#: moving up one line, or by having a type word put in front of it.
_CONVENTIONAL_SUBJECT = re.compile(
    r"^(?:build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(?:\([^()\n]+\))?!?:\s",
)


def _trailer_surface(message: str) -> str:
    """The part of a message trailer detection applies to.

    Only the Conventional Commit **prefix** is removed, not the subject line.
    Blanking the whole line was wrong and was caught by an independent audit:
    `fix: Signed-off-by: A Person` passed clean, because nothing was left of
    the subject to detect. The exemption exists so `fix:` stops looking like a
    trailer token — it was never meant to make the rest of the subject
    unreadable.

    The prefix is *removed* rather than blanked. Padding it with spaces was the
    first attempt and did not work: the trailer patterns anchor with `^`, so
    leading whitespace hid the very token the removal exists to expose.
    """
    subject, separator, rest = message.partition("\n")
    match = _CONVENTIONAL_SUBJECT.match(subject) if separator else None
    if match:
        subject = subject[match.end():]
    return subject + separator + rest

# Path detection, in three shapes. A repository-relative path such as
# ``src/loader.py`` is deliberately *not* matched: naming a file you changed is
# ordinary project-facing language. What is prohibited is a path that reveals a
# local filesystem — an absolute path, a home-relative path, a parent-escaping
# path, or a drive letter.
_PATH_OPEN = r"(?:^|[\s(\[\"'<>=,;])"
_PATH_ROOTED = re.compile(_PATH_OPEN + r"/[\w.\-]+(?:/[\w.\-]+)+")
#: A sensitive root followed by something. A bare `/tmp` is the same on every
#: machine and reveals nothing; `/tmp/build-4417` is a path on *this* one. The
#: rule exists to stop a machine's layout from shipping, and matching the root
#: alone made it fire on the string literals in the code that implements it.
_PATH_SENSITIVE_ROOT = re.compile(
    _PATH_OPEN + r"/(?:Users|home|root|etc|var|tmp|opt|private|srv|mnt|media"
    r"|Volumes|Applications|Library|System|proc|sys|dev)/[\w.\-]",
    re.IGNORECASE,
)
#: Likewise: `~/`, `../` and `C:\` are path *syntax*. They become a path when
#: something follows them.
_PATH_ANCHORED = re.compile(_PATH_OPEN + r"(?:~[/\\]|\.\.[/\\]|[A-Za-z]:[\\/])[\w.\-]")

#: Paths that are identical on every machine and therefore reveal nothing about
#: this one. The rule exists to stop a developer's home directory or a private
#: root from shipping; `/dev/null` is neither, and it appears in the header of
#: every unified diff that adds or deletes a file — so without this, the audit
#: capsule for any new file was refused for containing Git's own syntax.
_NEUTRAL_PATHS = (
    "/dev/null", "/dev/stdin", "/dev/stdout", "/dev/stderr",
    "/usr/bin/env", "/bin/sh", "/bin/bash",
)


def contains_local_path(text: str) -> bool:
    """Whether this text names a path that says something about a machine.

    One implementation, used by the message validator and by the general
    scanner. Two copies of a path heuristic diverge, and the one that is wrong
    is whichever the current caller happens not to be using.
    """
    for neutral in _NEUTRAL_PATHS:
        text = text.replace(neutral, "")
    return bool(
        _PATH_ROOTED.search(text) or _PATH_SENSITIVE_ROOT.search(text) or _PATH_ANCHORED.search(text)
    )

_CREDENTIAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai-style key", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}")),
    ("anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}")),
    ("github token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}")),
    ("github pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("aws access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{16,}")),
    ("url userinfo", re.compile(r"\b[A-Za-z][A-Za-z0-9+.\-]*://[^\s/@:]+:[^\s/@]+@")),
    (
        "inline secret",
        re.compile(r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token)\s*[=:]\s*\S+"),
    ),
)

#: A long run of hex is not a credential *shape* — every real one carries a
#: prefix. It is a useful heuristic in a commit message, where nobody writes
#: forty hex characters by accident, and a useless one anywhere content
#: legitimately records hashes: source files, manifests, and a task capsule,
#: which must name the base revision it is built on. Keeping it in the shared
#: credential table meant the general scanner refused a capsule for containing
#: the one field it is required to contain.
_MESSAGE_ONLY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("long hex token", re.compile(r"\b[0-9a-fA-F]{32,}\b")),
)


def _redact(term: str) -> str:
    """A term rendered for a diagnostic without reproducing it in full.

    Violation text is written to logs and terminals. Echoing a project's
    private identifier verbatim in the message that exists to stop that
    identifier from escaping is a small but gratuitous leak.
    """
    stripped = term.strip()
    if len(stripped) <= 2:
        return "*" * len(stripped)
    return f"{stripped[0]}{'*' * (len(stripped) - 2)}{stripped[-1]}"


def _term_pattern(term: str) -> re.Pattern[str]:
    """Word-boundary matcher for a term, tolerant of internal whitespace runs.

    Substring matching is wrong here: it rejects "Resolve" for containing a
    model name, and a gate that fires on ordinary English is a gate that gets
    switched off.
    """
    words = [re.escape(part) for part in term.strip().split()]
    core = r"\s+".join(words)
    return re.compile(rf"(?<!\w){core}(?!\w)", re.IGNORECASE)


@dataclass(frozen=True)
class TermSet:
    """A project's declared private vocabulary, in two tiers.

    ``declared_empty`` distinguishes "this project has no private terms, and
    someone decided that" from "nobody supplied a term set".

    ``terms`` and ``patterns`` apply to **every** surface. ``identity_terms``
    and ``identity_patterns`` apply only where a person writes deliberately —
    commit messages, ref and tag names, author and committer identities, and
    repository paths — and not to blob content.

    The split is measured, not aesthetic. A vocabulary of bare common words
    (`claude`, `terra`, `sol`, `envelope`, `harness`) is unusable against the
    contents of a prose corpus: `claude` matches Jean-Claude
    Martin, `terra` is Italian for "ground". Four such findings on one real
    project, zero true positives, and one cost a full history rebuild because
    amending the tip does not reach an earlier blob. The failure that matters
    is not the noise — it is that the only cheap remedy is a content exemption
    over the whole directory, which converts a precise control into the hole
    the public-safety rules exist to forbid. A worker name in a commit message
    is still refused, which is the case that was ever a real leak.
    """

    terms: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()
    identity_terms: tuple[str, ...] = ()
    identity_patterns: tuple[str, ...] = ()
    declared_empty: bool = False
    _compiled: dict[str, re.Pattern[str]] = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def of(
        cls,
        terms: object = (),
        patterns: object = (),
        identity_terms: object = (),
        identity_patterns: object = (),
    ) -> "TermSet":
        term_tuple = tuple(str(t) for t in terms)  # type: ignore[union-attr]
        pattern_tuple = tuple(str(p) for p in patterns)  # type: ignore[union-attr]
        identity_term_tuple = tuple(str(t) for t in identity_terms)  # type: ignore[union-attr]
        identity_pattern_tuple = tuple(str(p) for p in identity_patterns)  # type: ignore[union-attr]
        if not (term_tuple or pattern_tuple or identity_term_tuple or identity_pattern_tuple):
            raise ValueError(
                "an empty term set must be declared explicitly with NO_PRIVATE_TERMS"
            )
        return cls(
            terms=term_tuple,
            patterns=pattern_tuple,
            identity_terms=identity_term_tuple,
            identity_patterns=identity_pattern_tuple,
        )

    def compiled_terms(self, *, content_surface: bool = False) -> list[tuple[str, re.Pattern[str]]]:
        """Every term that applies to this surface, compiled.

        ``content_surface=True`` means blob content, which the identity tier
        deliberately does not reach.
        """
        selected = self.terms if content_surface else (*self.terms, *self.identity_terms)
        out = []
        for term in selected:
            if term not in self._compiled:
                self._compiled[term] = _term_pattern(term)
            out.append((term, self._compiled[term]))
        return out

    def applicable_patterns(self, *, content_surface: bool = False) -> tuple[str, ...]:
        """Every declared regex that applies to this surface."""
        if content_surface:
            return self.patterns
        return (*self.patterns, *self.identity_patterns)

    def summary(self) -> str:
        """What this set actually carries, for a report header.

        A report that does not say what it loaded cannot be audited, and the
        motivating defect was a scan that applied 0 of 59 rules and printed
        `clean`.
        """
        if self.declared_empty:
            return "no private vocabulary (declared empty)"
        return (
            f"{len(self.terms)} term(s), {len(self.identity_terms)} identity-only term(s), "
            f"{len(self.patterns)} pattern(s), {len(self.identity_patterns)} identity-only pattern(s)"
        )

    def offenders(self, text: str, *, content_surface: bool = False) -> list[str]:
        """Every declared private term or pattern this text contains."""
        found: list[str] = []
        for term, pattern in self.compiled_terms(content_surface=content_surface):
            if pattern.search(text):
                found.append(term)
        for pattern_text in self.applicable_patterns(content_surface=content_surface):
            try:
                compiled = re.compile(pattern_text, re.IGNORECASE)
            except re.error:
                # A malformed declared pattern is a contract defect, but a
                # scanner that raises here would turn a scan into an outage.
                # Report it as an offender so it is visible and fix-forced.
                found.append(f"unparseable pattern {pattern_text!r}")
                continue
            if compiled.search(text):
                found.append(pattern_text)
        return sorted(set(found))


#: The explicit way to say "this project declares no private vocabulary".
NO_PRIVATE_TERMS = TermSet(declared_empty=True)


@dataclass(frozen=True)
class ContractViolation:
    """One reason a message is not contract-conforming."""

    rule: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.rule}: {self.detail}"


def _structural_violations(message: str) -> list[ContractViolation]:
    out: list[ContractViolation] = []

    if _CONTROL.search(message):
        out.append(
            ContractViolation(
                "CONTROL_CHARACTER",
                "message contains carriage returns or control characters",
            )
        )

    # Trailing blank lines are not content, on any input path. `git log -1
    # --format=%B` terminates a message with TWO newlines, so stripping only
    # one left a blank line that read as EXTRA_CONTENT — which failed the
    # read-back half of the double-sided contract on every well-formed
    # commit. Real prose after the bullets still trips EXTRA_CONTENT.
    body = message.rstrip("\n")
    lines = body.split("\n")

    # Content checks run unconditionally. Gating them behind a shape match is
    # how " \n\n-  \n- two\n- three" slipped through: the shape regex is
    # satisfied by whitespace, and `.+` says nothing about meaning.
    if not lines or not lines[0].strip():
        out.append(ContractViolation("TITLE_MISSING", "the first line must be a non-empty title"))

    if len(lines) < 2:
        out.append(
            ContractViolation("BLANK_LINE_MISSING", "the title must be followed by exactly one blank line")
        )
    elif lines[1] != "":
        out.append(
            ContractViolation("BLANK_LINE_MISSING", f"line 2 must be blank, found {lines[1]!r}")
        )

    remainder = lines[2:] if len(lines) > 2 else []
    bullets = [line for line in remainder if line.startswith("- ")]
    non_bullets = [line for line in remainder if not line.startswith("- ")]

    if not (2 <= len(bullets) <= 4):
        out.append(
            ContractViolation(
                "BULLET_COUNT", f"between two and four bullets are required, found {len(bullets)}"
            )
        )
    if any(not line[2:].strip() for line in bullets):
        out.append(
            ContractViolation("BULLET_EMPTY", "every bullet must carry a non-empty outcome")
        )
    if non_bullets:
        out.append(
            ContractViolation(
                "EXTRA_CONTENT",
                f"no prose or blank lines are permitted after the bullets, found {non_bullets[0]!r}",
            )
        )
    if remainder and not remainder[0].startswith("- "):
        out.append(
            ContractViolation(
                "BULLETS_NOT_ADJACENT", "the bullets must begin immediately after the blank line"
            )
        )

    # Match the SAME normalised body the line checks used. Matching the raw
    # message here meant one rule had two representations, and they
    # disagreed on git's own read-back output.
    if not out and not SHAPE.fullmatch(body):
        out.append(ContractViolation("SHAPE", "message does not match the required shape"))
    return out


def _content_violations(message: str, term_set: TermSet) -> list[ContractViolation]:
    out: list[ContractViolation] = []

    if _LITERAL_NEWLINE.search(message):
        out.append(
            ContractViolation("LITERAL_NEWLINE_ESCAPE", "message contains a literal backslash-n sequence")
        )
    if _COAUTHOR.search(message):
        out.append(ContractViolation("COAUTHOR", "Co-authored-by is prohibited"))
    trailer_surface = _trailer_surface(message)
    if _TRAILER_HYPHENATED.search(trailer_surface) or _TRAILER_TOKENS.search(trailer_surface):
        out.append(ContractViolation("TRAILER", "commit trailers are prohibited"))
    if contains_local_path(message):
        out.append(ContractViolation("ABSOLUTE_PATH", "local filesystem paths are prohibited"))
    if _UUID.search(message):
        out.append(
            ContractViolation("PRIVATE_IDENTIFIER", "a UUID-shaped private identifier is prohibited")
        )

    for label, pattern in (*_CREDENTIAL_PATTERNS, *_MESSAGE_ONLY_PATTERNS):
        if pattern.search(message):
            out.append(ContractViolation("CREDENTIAL", f"credential-shaped token detected ({label})"))

    for term, pattern in term_set.compiled_terms():
        if pattern.search(message):
            out.append(
                ContractViolation("PRIVATE_TERM", f"private term {_redact(term)!r} is prohibited")
            )

    # A commit message is a surface a person wrote deliberately, so the whole
    # vocabulary applies — including the identity tier that blob content does
    # not receive.
    for raw in term_set.applicable_patterns():
        try:
            compiled = re.compile(raw, re.IGNORECASE)
        except re.error as exc:
            out.append(ContractViolation("BAD_POLICY_PATTERN", f"invalid private pattern: {exc}"))
            continue
        if compiled.search(message):
            out.append(ContractViolation("PRIVATE_TERM", f"private pattern {_redact(raw)!r} matched"))

    return out


def validate_message(message: str, term_set: TermSet) -> list[ContractViolation]:
    """Return every contract violation in ``message``; empty means conforming.

    ``term_set`` is required. Pass :data:`NO_PRIVATE_TERMS` to state
    deliberately that the project declares none.

    The validator never stops at the first violation, because reporting one
    problem at a time turns a deterministic gate into a guessing game.
    """
    if not isinstance(message, str):
        raise TypeError("commit message must be a string")
    if not isinstance(term_set, TermSet):
        raise TypeError(
            "a TermSet is required; pass NO_PRIVATE_TERMS to declare that the "
            "project has no private vocabulary"
        )

    violations = _structural_violations(message)
    violations.extend(_content_violations(message, term_set))
    return violations


def assert_valid(message: str, term_set: TermSet, *, stage: str = "pre-commit") -> None:
    """Raise :class:`CommitContractError` unless ``message`` conforms.

    ``stage`` distinguishes the pre-commit check from the post-commit re-read,
    so a failure names which side of the double-sided gate caught it.
    """
    violations = validate_message(message, term_set)
    if violations:
        raise CommitContractError(
            f"commit message rejected at {stage}",
            stage=stage,
            violations="; ".join(str(v) for v in violations),
        )


def validate_range(repository: str, ref: str, baseline: str | None, term_set: TermSet) -> list[tuple[str, list[ContractViolation]]]:
    """Every non-conforming commit message in ``baseline..ref``.

    The single-message gate is applied before staging and again on read-back,
    which protects the commit being made and says nothing about the ones
    already made. A long project drifts: the convention is kept perfectly for
    the first commits and then relaxes, and nothing notices, because no surface
    ever re-reads a message after its own commit succeeded.

    This is that surface. It is a report over a range, not a rewrite: history
    that has already been published cannot be repaired by a checker, and
    knowing where the drift starts is what lets a coordinator decide whether an
    unpublished branch is worth rebuilding.
    """
    import gitread

    out: list[tuple[str, list[ContractViolation]]] = []
    for sha, _ in gitread.objects_in_outgoing_range(repository, ref, baseline):
        if gitread.object_type(repository, sha) != "commit":
            continue
        violations = validate_message(gitread.commit_message(repository, sha), term_set)
        if violations:
            out.append((sha, violations))
    return out


def _term_set_from_args(args: object) -> TermSet:
    """The vocabulary a CLI invocation actually applies.

    `--project` reads the contract, which is the single source. The `--term`
    flags remain, and are **additive** to whatever the contract supplies: a
    flag that silently replaced the declared vocabulary is how a gate came to
    apply 0 of 59 rules and report `clean`.
    """
    project = getattr(args, "project", None)
    terms: list[str] = []
    patterns: list[str] = []
    identity_terms: list[str] = []
    identity_patterns: list[str] = []

    if project:
        from project_contract import ProjectContract

        contract = ProjectContract.load(project)
        terms.extend(contract.default_terms)
        terms.extend(contract.project_terms)
        patterns.extend(contract.default_patterns)
        patterns.extend(contract.project_patterns)
        identity_terms.extend(contract.default_identity_terms)
        identity_patterns.extend(contract.default_identity_patterns)

    terms.extend(getattr(args, "term", None) or [])
    patterns.extend(getattr(args, "pattern", None) or [])

    if not (terms or patterns or identity_terms or identity_patterns):
        return NO_PRIVATE_TERMS
    return TermSet.of(terms, patterns, identity_terms, identity_patterns)


def _cli(argv: list[str]) -> int:
    """Validate a commit message, or every message in a range.

    Usage: ``commit_gate.py [FILE] [--project PATH] [--term TERM ...] [--pattern REGEX ...]``
           ``commit_gate.py --range REF [BASELINE] --repo PATH [--project PATH]``

    Reads ``FILE`` if given, otherwise stdin. Prints each violation and exits
    non-zero if the message does not conform.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="commit_gate.py",
        description="Validate a commit message against the public commit contract.",
    )
    parser.add_argument("file", nargs="?", help="path to the message file; stdin if omitted")
    parser.add_argument("--project", help="path to PROJECT.yaml; supplies the declared vocabulary")
    parser.add_argument("--term", action="append", default=[], help="a declared private term (repeatable, additive)")
    parser.add_argument("--pattern", action="append", default=[], help="a declared private regex pattern (repeatable, additive)")
    parser.add_argument("--range", metavar="REF", help="validate every commit message reachable in a range")
    parser.add_argument("--baseline", default=None, help="the baseline for --range; omit for the whole history")
    parser.add_argument("--repo", help="repository path for --range; defaults to the contract's repo_path")
    args = parser.parse_args(argv)

    try:
        term_set = _term_set_from_args(args)
    except Exception as exc:  # ContractError and friends: state it, never degrade
        print(f"CONTRACT UNREADABLE {exc}")
        return 2  # distinct from 1: could-not-check is not a clean verdict

    print(f"vocabulary: {term_set.summary()}")

    if args.range:
        repository = args.repo
        if not repository and args.project:
            from project_contract import ProjectContract

            repository = ProjectContract.load(args.project).repository()
        if not repository:
            print("VIOLATION --range needs --repo or a --project declaring project.repo_path")
            return 2
        failures = validate_range(repository, args.range, args.baseline, term_set)
        if not failures:
            # `--range` already accepts an `A..B` form, so prefixing a baseline
            # unconditionally printed `ROOT..A..B` — a range that does not
            # exist. Report the range that was actually walked.
            walked = args.range if ".." in args.range else f"{args.baseline or 'ROOT'}..{args.range}"
            print(f"VALID every commit message in {walked} conforms")
            return 0
        for sha, violations in failures:
            for violation in violations:
                print(f"VIOLATION {sha[:12]} {violation}")
        return 1

    if args.file:
        with open(args.file, encoding="utf-8") as handle:
            message = handle.read()
    else:
        message = sys.stdin.read()

    violations = validate_message(message, term_set)
    if not violations:
        print("VALID")
        return 0
    for violation in violations:
        print(f"VIOLATION {violation}")
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
