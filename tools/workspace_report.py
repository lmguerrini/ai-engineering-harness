"""Workspace classification, and the gate on anything nobody has classified.

Every artifact in a workspace belongs to exactly one of four buckets: tracked
product, ignored private, safe generated, or unknown. The fourth is the whole
point. An unknown artifact is a file that appeared during the work and that
nobody has said anything about — and the two obvious responses to it are both
wrong. Committing it ships whatever it is. Deleting it destroys work somebody
may have been relying on. So it blocks, and stays exactly where it is, until a
human or a declaration says which of the other three it belongs to.

This module reports. It does not repair, stage, delete or move anything, and
there is no argument that makes it do so.
"""

from __future__ import annotations

import fnmatch
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import gitread

__all__ = ["WorkspaceReport", "classify_workspace"]

#: Generated output a project may declare safe. Deliberately empty: what is
#: safe to regenerate is a property of the project, not of this tool, and a
#: default list here would silently classify somebody else's data.
DEFAULT_SAFE_GENERATED: tuple[str, ...] = ()


@dataclass
class WorkspaceReport:
    tracked_product: list[str] = field(default_factory=list)
    ignored_private: list[str] = field(default_factory=list)
    safe_generated: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    whitespace_damage: str = ""

    @property
    def clean(self) -> bool:
        return not self.unknown and not self.whitespace_damage

    def render(self) -> str:
        if self.clean:
            return (
                f"workspace: {len(self.tracked_product)} tracked, "
                f"{len(self.ignored_private)} ignored, {len(self.safe_generated)} generated"
            )
        lines = ["workspace is not in a closable state"]
        for path in self.unknown:
            lines.append(f"  unclassified: {path}")
        if self.whitespace_damage:
            lines.append("  whitespace damage:")
            lines.extend(f"    {line}" for line in self.whitespace_damage.splitlines())
        return "\n".join(lines)


def _segment_match(segment: str, pattern: str) -> bool:
    """One path segment against one pattern segment.

    `fnmatch` on the whole path is wrong here: its `*` crosses `/`, so a
    project declaring `dist/*` safe silently classified everything at every
    depth beneath `dist`. Matching segment by segment gives `*` the meaning a
    project writing an ignore rule expects.
    """
    return fnmatch.fnmatch(segment, pattern)


def _matches_any(path: str, patterns: Sequence[str]) -> bool:
    """Whether a repository-relative path matches a declared pattern.

    Follows `.gitignore` in the three ways that matter: a trailing slash names
    a directory and covers everything beneath it, a leading slash anchors to
    the repository root, and a bare name matches at any depth. What it does
    *not* follow is `fnmatch`'s `*`, which crosses directory separators.
    """
    parts = Path(path).parts
    for pattern in patterns:
        anchored = pattern.startswith("/")
        directory = pattern.endswith("/")
        core = pattern.strip("/")
        if not core:
            continue
        segments = core.split("/")

        if directory and not anchored and len(segments) == 1:
            # A bare directory name covers everything beneath it, at any depth.
            if segments[0] in parts[:-1] or path == segments[0]:
                return True
            continue

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


def _staged_additions(repository: str | Path) -> list[str]:
    """Paths added to the index that the last commit does not contain."""
    # `require` rather than a default. A caller that cannot look must not be
    # told "the index holds no additions" — that would make an unread
    # repository read as a clean report at the one gate where that must never
    # happen.
    answer = gitread.probe(
        repository, "diff", "--no-ext-diff", "--cached", "--name-only", "--diff-filter=A",
        # Declared empty on purpose. `git diff --name-only` has no documented
        # negative exit — it prints nothing and exits 0 when there is nothing
        # to report — so every non-zero status is a failure to look.
        negative_statuses=(),
    )
    output = answer.require("what is staged in the index")
    return [line for line in output.splitlines() if line]


def _listing(repository: str | Path, *arguments: str) -> list[str]:
    output = gitread._run(repository, "ls-files", *arguments)
    return [line for line in str(output).splitlines() if line]


def classify_workspace(
    repository: str | Path,
    *,
    ignored_private: Iterable[str] = (),
    safe_generated: Iterable[str] = DEFAULT_SAFE_GENERATED,
) -> WorkspaceReport:
    """Sort every artifact into exactly one bucket and report what blocks closure.

    The buckets are checked in a fixed order and each path is assigned once,
    so a path can never appear in two of them.
    """
    private = tuple(ignored_private)
    generated = tuple(safe_generated)

    report = WorkspaceReport()
    tracked = set(_listing(repository, "--cached"))
    # A file staged but not yet committed is not "tracked product" — nobody
    # has said anything about it, and staging is exactly how the motivating
    # incident happened: a wildcard `add -A` captured a scratch directory and
    # the gate then reported clean.
    pending = set(_staged_additions(repository))
    # Untracked, including files an ignore rule already covers: an ignored
    # file is a *classification*, not an absence, and the project has to have
    # said so.
    untracked_all = set(_listing(repository, "--others"))

    for path in sorted(tracked):
        if path not in pending:
            report.tracked_product.append(path)
        elif _matches_any(path, private):
            report.ignored_private.append(path)
        elif _matches_any(path, generated):
            report.safe_generated.append(path)
        else:
            report.unknown.append(path)
    for path in sorted(untracked_all):
        if _matches_any(path, private):
            report.ignored_private.append(path)
        elif _matches_any(path, generated):
            report.safe_generated.append(path)
        else:
            # Everything else is unknown, including files an ignore rule
            # already hides. Being ignored by Git is not a classification: it
            # is exactly the case where a file is invisible to `status` and
            # nobody has said what it holds.
            report.unknown.append(path)

    report.whitespace_damage = gitread.whitespace_damage(repository)
    return report


def _cli(argv: list[str]) -> int:
    """Classify a workspace and report anything blocking closure.

    Usage: ``workspace_report.py REPO [--ignore-private PATTERN ...] [--safe-generated PATTERN ...]``
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="workspace_report.py",
        description="Classify every artifact in a Git workspace; report unknown artifacts as blocking.",
    )
    parser.add_argument("repository")
    parser.add_argument("--ignore-private", action="append", default=[], metavar="PATTERN")
    parser.add_argument("--safe-generated", action="append", default=[], metavar="PATTERN")
    args = parser.parse_args(argv)

    report = classify_workspace(
        args.repository,
        ignored_private=args.ignore_private,
        safe_generated=args.safe_generated,
    )
    print(report.render())
    return 0 if report.clean else 1


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
