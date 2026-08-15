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
    """
    return fnmatch.fnmatch(segment, pattern)


def _matches_one(path: str, pattern: str) -> bool:
    parts = PurePosixPath(path).parts
    anchored = pattern.startswith("/")
    directory = pattern.endswith("/")
    core = pattern.strip("/")
    if not core:
        return False
    segments = core.split("/")

    if directory and not anchored and len(segments) == 1:
        # A bare directory name covers everything beneath it, at any depth.
        return segments[0] in parts[:-1] or path == segments[0]

    starts = [0] if anchored or len(segments) > 1 else list(range(len(parts)))
    for start in starts:
        window = parts[start : start + len(segments)]
        if len(window) != len(segments):
            continue
        if not all(_segment_match(part, spec) for part, spec in zip(window, segments)):
            continue
        covers_rest = directory or start + len(segments) < len(parts)
        if directory or not covers_rest or start + len(segments) == len(parts):
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
