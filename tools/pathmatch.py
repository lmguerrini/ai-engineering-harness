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
that defines them — 13 pattern/path pairs disagreed, and **every one
under-matched**: the same direction as the original defect, a declared
exemption silently covering nothing.

Three root causes, one class. In gitignore, **a pattern that matches a directory
covers everything beneath it**, and the old implementation only ever compared a
pattern against the whole path:

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
    return fnmatch.fnmatchcase(segment, pattern)


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
        # Zero components, then one, then two … The empty case first so that a
        # trailing `**` matches the directory it is anchored to as well as
        # everything under it.
        for taken in range(len(parts) + 1):
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


def _matches_one(path: str, pattern: str) -> bool:
    parts = PurePosixPath(path).parts
    if not parts:
        return False

    anchored = pattern.startswith("/")
    directory = pattern.endswith("/")
    core = pattern.strip("/")
    if not core:
        return False
    segments = core.split("/")
    # A separator inside the pattern anchors it to the root. This is git's rule,
    # not a simplification of it: `a/b/` is a path from the root, while `b/` is
    # a name at any depth.
    anchored = anchored or len(segments) > 1

    # The entity itself, unless the pattern can only name a directory. Callers
    # ask about files, so a directory-only pattern never matches the path whole.
    if not directory and _matches_entity(parts, segments, anchored):
        return True

    # Every ancestor directory. This is the half that was missing: in gitignore
    # a pattern matching a directory covers everything beneath it, so a file is
    # covered when any of its parents is.
    for end in range(1, len(parts)):
        if _matches_entity(parts[:end], segments, anchored):
            return True
    return False


def matches_any(path: str, patterns: Sequence[str]) -> bool:
    """Whether a repository-relative path matches any declared pattern."""
    return any(_matches_one(path, pattern) for pattern in patterns)


def matching_patterns(path: str, patterns: Sequence[str]) -> list[str]:
    """Which declared patterns this path matches.

    Callers use this to report *which* declaration covered a path, and — by
    difference over every path — which declarations covered nothing at all.
    """
    return [pattern for pattern in patterns if _matches_one(path, pattern)]
