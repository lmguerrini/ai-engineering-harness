"""One path-pattern semantics, for every path declaration in the pack.

Path patterns are declared in exactly one place — the `workspace_classification`
block of a project contract — and were then interpreted two different ways:
`workspace_report` read them as gitignore rules, `outgoing_scan` read them with
`fnmatch`. The template documented gitignore, immediately above the field that
used the other one.

The consequence is worth stating precisely, because it is the reason this module
exists rather than a comment. A directory exemption written the way the template
implies — `annotations/` — matched **nothing** under `fnmatch`, and the failure
direction is toward *more* scanning, so it never announced itself. The scan
reported normally; the exemption simply did nothing. Detecting it took a
deliberate A/B run whose two reports were byte-identical.

Two rules follow, and both are implemented here:

*   **Gitignore semantics, everywhere.** A trailing slash names a directory and
    covers everything beneath it; a leading slash anchors to the repository
    root; a bare name matches at any depth; and `*` does **not** cross a
    directory separator.
*   **A declaration that matches nothing is reported as matching nothing.**
    That is the caller's job, not this module's, but it is the other half of
    the same defect: silence is what made a dead exemption invisible.

## What RP2.2 repaired, and how it was found

The rules above were right and the implementation delivered them only for the
cases somebody had thought of. Differentially tested against **real
`git check-ignore`** — the semantics this module claims, asked of the program
that defines them — it diverged in **both** directions: mostly under-matching, a
declared exemption silently covering nothing, and in a handful of cases
over-matching, one silently covering more than it said.

**The count is not written here.** It is `BASELINE_DIVERGENCES` in
`tools/tests/test_pathmatch.py`, and a test computes it from the frozen 2.1.1
module against the shipped grid rather than trusting anyone's memory of it. That
indirection exists because the number was written down from memory twice and was
wrong twice — 13 measured on a grid that was then replaced, then 29 re-measured
on the replaced grid in the same commit that widened it. Both were caught by
independent audits, the second observing that this module had narrated the
mistake and then repeated it.

Several root causes, one class. In gitignore, **a pattern that matches a
directory covers everything beneath it**, and the old implementation only ever
compared a pattern against the whole path:

*   `dist*/`, `build*/`, `*.egg-info/` — a *wildcard* directory name was
    compared with string equality, so only literal directory names ever matched;
*   `annotations` — a bare name that names a directory matched the directory and
    nothing under it, so `annotations/x.md` escaped;
*   `dist/*` — matched `dist/<one component>` and stopped, so `dist/sub/a.txt`
    escaped.

So matching is now defined once, in the terms git uses: a pattern matches an
**entity**, and a file is covered when the pattern matches the file itself or
**any ancestor directory of it**. A directory-only pattern is simply one that
cannot match the file itself.

Two further corrections came out of the same differential:

*   `**` is implemented, matching zero or more components. It was previously
    treated as an ordinary `*` within one component, which silently narrowed
    every pattern that used it.
*   Matching is **case-sensitive** (`fnmatchcase`). `fnmatch` applies
    `os.path.normcase`, so the same declaration matched different files on a
    case-insensitive filesystem than on a case-sensitive one — a portable
    contract that is not portable.

The oracle for all of this is `tools/tests/test_pathmatch.py`, which runs the
comparison against `git check-ignore` rather than against a table somebody typed
out. A hand-written table is exactly how the first implementation passed.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Sequence
from pathlib import PurePosixPath

__all__ = ["matches_any", "matching_patterns"]


def _segment_match(segment: str, pattern: str) -> bool:
    """One path segment against one pattern segment.

    `fnmatch` on the whole path is wrong here: its `*` crosses `/`, so a
    project declaring `dist/*` safe silently classified everything at every
    depth beneath `dist`. Matching segment by segment gives `*` the meaning a
    project writing an ignore rule expects.

    `fnmatchcase`, not `fnmatch`: the latter runs `os.path.normcase` first, so
    on a case-insensitive filesystem `DIST/` would match `dist/` and on a
    case-sensitive one it would not. A declaration whose meaning depends on the
    filesystem it is read from is not a declaration.
    """
    return fnmatch.fnmatchcase(segment, _fnmatch_safe(pattern))


def _match_segments(parts: tuple[str, ...], segments: list[str]) -> bool:
    """Whether ``segments`` matches the whole component sequence ``parts``.

    ``**`` matches zero or more components; every other segment matches exactly
    one. Written recursively because that is the shape of the rule — a loop
    over start offsets cannot express "zero or more" without becoming this
    anyway.
    """
    if not segments:
        return not parts
    head, rest = segments[0], segments[1:]
    if head == "**":
        # Zero components, then one, then two … except at the end of a pattern:
        # git's rule is that a trailing `/**` matches everything **inside** the
        # thing it is anchored to, not the anchor itself. The first
        # implementation let it match zero components everywhere, so
        # `annotations/**` matched `annotations` — an over-match, which widens
        # an exemption. Found by an independent differential against git, not
        # by the one shipped here, whose pattern list had no trailing `**`
        # whose anchor was also in its path list.
        start = 1 if not rest else 0
        for taken in range(start, len(parts) + 1):
            if _match_segments(parts[taken:], rest):
                return True
        return False
    if not parts or not _segment_match(parts[0], head):
        return False
    return _match_segments(parts[1:], rest)


def _matches_entity(parts: tuple[str, ...], segments: list[str], anchored: bool) -> bool:
    """Whether the pattern names this exact entity.

    An anchored pattern — one with a leading `/`, or with a separator anywhere
    inside it — is measured from the repository root. An unanchored one is a
    single name and matches at any depth, which is the same statement as
    "prefix it with `**/`".
    """
    if anchored:
        return _match_segments(parts, segments)
    return _match_segments(parts, ["**", *segments])


def _names_entity(parts: tuple[str, ...], pattern: str, *, is_directory: bool) -> bool:
    """Whether ``pattern`` names this exact entity — no ancestor walking.

    ``is_directory`` decides whether a directory-only pattern (trailing `/`)
    applies. The caller knows which entity it is asking about, and a matcher
    that guesses is a matcher that lets `dist/` match a *file* called `dist`.
    """
    # Git strips trailing whitespace from a pattern unless it is backslash-
    # escaped, so `"*.txt "` is `*.txt`. Without this it matched nothing, which
    # is the silent-dead-declaration failure this module exists to prevent.
    pattern = _strip_trailing_space(pattern)
    anchored = pattern.startswith("/")
    directory_only = pattern.endswith("/")
    # `strip("/")` alone made `dist//` behave as `dist/`; git treats a doubled
    # separator as matching nothing. Degenerate, and found by a differential
    # rather than by reasoning, which is the point of running one.
    if "//" in pattern:
        return False
    core = pattern.strip("/")
    if not core or (directory_only and not is_directory):
        return False
    segments = core.split("/")
    # A separator inside the pattern anchors it to the root. This is git's rule,
    # not a simplification of it: `a/b/` is a path from the root, while `b/` is
    # a name at any depth.
    return _matches_entity(parts, segments, anchored or len(segments) > 1)


def _verdict(parts: tuple[str, ...], patterns: Sequence[str], *, is_directory: bool) -> bool:
    """Last match wins, over one entity."""
    covered = False
    for pattern in patterns:
        negated, core = _split_negation(pattern)
        if _names_entity(parts, core, is_directory=is_directory):
            covered = not negated
    return covered


def _matches_one(path: str, pattern: str) -> bool:
    """Whether one pattern engages this path, at it or at any ancestor.

    Used for *engagement* reporting. Coverage is :func:`matches_any`, which has
    to walk the ancestors in order because negation depends on that order.
    """
    parts = PurePosixPath(path).parts
    if not parts:
        return False
    _negated, core = _split_negation(pattern)
    if _names_entity(parts, core, is_directory=False):
        return True
    return any(
        _names_entity(parts[:end], core, is_directory=True) for end in range(1, len(parts))
    )


def _strip_trailing_space(pattern: str) -> str:
    """Trailing **spaces** removed, unless the last one is escaped.

    Spaces only. `rstrip()` was the first version and also removed tabs, which
    git does not: `"*.txt\t"` matched `a.txt` here and nothing in git, and the
    direction is over-matching — a `content_exempt` declaration silently
    widened, which is the failure this module exists to prevent. Worse, the test
    that pinned it asserted the divergence *and named git in its own title*.
    Found by an independent differential.
    """
    stripped = pattern.rstrip(" ")
    if len(stripped) < len(pattern) and stripped.endswith("\\"):
        return stripped[:-1] + " "
    return stripped


#: POSIX character classes, which git's wildmatch understands and `fnmatch` does
#: not. Without translation `[[:alpha:]].txt` matched nothing here and matched
#: every letter in git — a silently dead declaration, which is the failure this
#: module exists to prevent. Found by differential rather than by reading.
_POSIX_CLASSES = {
    "alpha": "a-zA-Z",
    "digit": "0-9",
    "alnum": "a-zA-Z0-9",
    "upper": "A-Z",
    "lower": "a-z",
    "space": " \\t\\n\\r\\f\\v",
    "blank": " \\t",
    "xdigit": "0-9A-Fa-f",
    # `]` first, `-` last, backslash doubled — the three positional rules a
    # character class has. Written as an explicit set rather than as ranges,
    # because the range form put `]` and `-` in positions that changed what
    # the class meant.
    "punct": ']!"#$%&\'()*+,./:;<=>?@[^_`{|}~\\\\-',
    "print": " -~",
    "graph": "!-~",
    "cntrl": "\\x00-\\x1f\\x7f",
}


def _class_end(segment: str, start: int) -> int:
    """Index of the `]` closing the class opened at ``start``, or -1.

    POSIX class syntax contains its own `]`, so a naive search for the next one
    truncated `[[:alpha:]]` to `[[:alpha:` and produced a class of literal
    punctuation. The scan skips over `[:…:]` and over a `]` in first position,
    which is how a class says "a literal right bracket".
    """
    index = start + 1
    if index < len(segment) and segment[index] in "!^":
        index += 1
    if index < len(segment) and segment[index] == "]":
        index += 1                          # a leading `]` is a member
    while index < len(segment):
        if segment.startswith("[:", index):
            closing = segment.find(":]", index + 2)
            if closing == -1:
                return -1
            index = closing + 2
            continue
        if segment[index] == "]":
            return index
        index += 1
    return -1


def _fnmatch_safe(segment: str) -> str:
    """One pattern segment, with git's escapes and `[^…]` translated for fnmatch.

    `fnmatch` has neither. Two consequences, both found by an independent
    differential against git and both **pre-existing at 2.1.1**:

    *   `a\\*b.txt` matched nothing here and matched the literal `a*b.txt` in
        git — a silently dead declaration, which is this module's whole subject.
    *   `[^a].txt` was read as a class containing `^` and `a`, so it matched
        `a.txt` (git does not) and missed `b.txt` (git does) — divergent in
        **both** directions, including the exemption-widening one.

    An escaped metacharacter becomes a one-character class, which `fnmatch`
    treats literally; `[^` becomes `[!`, which is the negation syntax it does
    understand.
    """
    out: list[str] = []
    index = 0
    while index < len(segment):
        character = segment[index]
        if character == "\\" and index + 1 < len(segment):
            following = segment[index + 1]
            # Only `*`, `?` and `[` mean anything to `fnmatch` outside a class,
            # and a one-character class is how you make them literal. Everything
            # else — `!`, `^`, `-`, a space — is already literal, and wrapping it
            # was wrong: `[!]` reads as an unterminated *negated* class.
            out.append(f"[{following}]" if following in "*?[" else following)
            index += 2
            continue
        if character == "[":
            close = _class_end(segment, index)
            if close == -1:
                out.append("[[]")          # an unclosed bracket is a literal
                index += 1
                continue
            body = segment[index + 1:close]
            if body.startswith("^"):
                body = "!" + body[1:]
            for name, members in _POSIX_CLASSES.items():
                body = body.replace(f"[:{name}:]", members)
            out.append("[" + body + "]")
            index = close + 1
            continue
        out.append(character)
        index += 1
    return "".join(out)


def _split_negation(pattern: str) -> tuple[bool, str]:
    """``(negated, core)``. A leading `\\!` is an escaped literal `!`."""
    if pattern.startswith("!"):
        return True, pattern[1:]
    if pattern.startswith("\\!"):
        return False, pattern[1:]
    return False, pattern


def matches_any(path: str, patterns: Sequence[str]) -> bool:
    """Whether the declared patterns, read in order, cover this path.

    **Last match wins**, which is git's rule and the reason this is a loop
    rather than an `any()`. A leading `!` negates, so a project can write

        content_exempt: ["fixtures/*", "!fixtures/real-notes.md"]

    and mean it. Before RP2.2 the `!` was read as part of a filename, so the
    negation matched nothing and the file it named stayed exempt — the project
    had written down the one exclusion it cared about and been silently
    overruled. Found by an independent audit, reproduced end to end: a declared
    private term in that file was suppressed and the scan reported `clean`.
    """
    parts = PurePosixPath(path).parts
    if not parts:
        return False

    # Ancestors first, outermost in. Git's rule: **a negation cannot re-include
    # a path whose parent directory is excluded.** Evaluating the leaf alone got
    # `dist/` + `!dist/sub/a.txt` wrong in the permissive direction — the file
    # read as re-included when git keeps it excluded — which was found by a
    # differential over negation sets and is why this is a walk rather than one
    # last-match-wins pass.
    for depth in range(1, len(parts)):
        if _verdict(parts[:depth], patterns, is_directory=True):
            return True
    return _verdict(parts, patterns, is_directory=False)


def matching_patterns(path: str, patterns: Sequence[str]) -> list[str]:
    """Which declared patterns **engage** this path, in declaration order.

    Engagement, not coverage: a negation that fires is listed, because it did
    something — it is not a dead declaration, and reporting it as one would
    send somebody to look for a rule that is working. Ask :func:`matches_any`
    whether the path is actually covered; the two answer different questions
    and a caller needs both.
    """
    return [pattern for pattern in patterns if _matches_one(path, pattern)]
