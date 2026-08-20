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

import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import gitread
import pathmatch

__all__ = ["WorkspaceReport", "classify_workspace", "UntrackedRequirement"]

#: Generated output a project may declare safe. Deliberately empty: what is
#: safe to regenerate is a property of the project, not of this tool, and a
#: default list here would silently classify somebody else's data.
DEFAULT_SAFE_GENERATED: tuple[str, ...] = ()


@dataclass(frozen=True)
class UntrackedRequirement:
    """A path the project declared must be tracked, which is not.

    ``rule`` names the ignore rule responsible, in `git check-ignore -v` form,
    because "this file is not tracked" sends someone looking at their `git add`
    while the cause is a line in a file they have never opened.
    """

    path: str
    rule: str


@dataclass
class WorkspaceReport:
    tracked_product: list[str] = field(default_factory=list)
    ignored_private: list[str] = field(default_factory=list)
    safe_generated: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    whitespace_damage: str = ""
    #: Declared-required paths that exist on disk and are not tracked. The
    #: motivating case: a machine-level `core.excludesFile` excluded `*.jsonl`,
    #: and the project's required files were JSONL in a tracked directory. `git
    #: add` committed nothing, silently, and every gate reported green. It was
    #: caught by accident, in an unrelated throwaway repository.
    untracked_requirements: list[UntrackedRequirement] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.unknown and not self.whitespace_damage and not self.untracked_requirements

    def render(self) -> str:
        if self.clean:
            return (
                f"workspace: {len(self.tracked_product)} tracked, "
                f"{len(self.ignored_private)} ignored, {len(self.safe_generated)} generated"
            )
        lines = ["workspace is not in a closable state"]
        for path in self.unknown:
            lines.append(f"  unclassified: {path}")
        for requirement in self.untracked_requirements:
            lines.append(f"  declared must_be_tracked but NOT TRACKED: {requirement.path}")
            lines.append(f"    excluded by: {requirement.rule}")
        if self.whitespace_damage:
            lines.append("  whitespace damage:")
            lines.extend(f"    {line}" for line in self.whitespace_damage.splitlines())
        return "\n".join(lines)


#: One path semantics for every path declaration in the pack, `pathmatch`.
#: This module and the outgoing scanner read patterns out of the same contract
#: block and used to interpret them differently.
_matches_any = pathmatch.matches_any


def _check_required_tracking(
    repository: str | Path, required: tuple[str, ...], tracked: set[str]
) -> list[UntrackedRequirement]:
    """Declared-required paths that exist on disk and are not in the index.

    The classification buckets answer "has somebody said what this file is".
    They have no notion of a file that *should* be there, so a path that never
    arrived is not unclassified — it is absent, and absence is exactly what a
    bucket check cannot see.
    """
    findings: list[UntrackedRequirement] = []
    root = Path(repository)
    for declaration in required:
        candidates = [
            path for path in _existing_paths(root, declaration)
            if path not in tracked
        ]
        for path in sorted(candidates):
            findings.append(UntrackedRequirement(path, _ignore_rule(repository, path)))
    return findings


def _existing_paths(root: Path, declaration: str) -> list[str]:
    """Paths on disk covered by one declaration, as repository-relative strings."""
    target = root / declaration.strip("/")
    if target.is_file():
        return [str(target.relative_to(root))]
    if target.is_dir():
        return [
            str(child.relative_to(root))
            for child in sorted(target.rglob("*"))
            if child.is_file() and ".git" not in child.parts
        ]
    # A glob, or a path that does not exist. Only what is on disk can be
    # reported as untracked: a declaration naming work not yet done is not a
    # defect, and failing on it would make the check unusable at capability
    # open.
    return [
        str(child.relative_to(root))
        for child in sorted(root.glob(declaration.strip("/")))
        if child.is_file() and ".git" not in child.parts
    ]


def _ignore_rule(repository: str | Path, path: str) -> str:
    """Which rule excludes this path, in `git check-ignore -v` form."""
    # `check-ignore` exits 0 when the path IS ignored and 1 when it is not, so
    # 1 is this command's documented negative and every other status is a
    # failure to look.
    answer = gitread.probe(
        repository, "check-ignore", "--no-index", "-v", "--", path, negative_statuses=(1,),
    )
    if not answer.answered:
        return f"unknown — git could not be asked ({answer.cause})"
    # 1 is the documented negative; every other status means git ran and could
    # not answer. Returning the negative's sentence for it stated, as a fact,
    # that no ignore rule covers the path — a definite claim from a failed
    # question (DECISIONS.md D15).
    if answer.failed:
        return f"unknown — git could not answer ({answer.cause})"
    if not answer.ok:
        return "no ignore rule; the path exists but was never added to the index"
    return answer.value.strip() or "an ignore rule git declined to name"


def _staged_additions(repository: str | Path) -> list[str]:
    """Paths added to the index that the last commit does not contain."""
    # `require` rather than a default. A caller that cannot look must not be
    # told "the index holds no additions" — that would make an unread
    # repository read as a clean report at the one gate where that must never
    # happen.
    answer = gitread.probe(
        repository, "diff", "--no-ext-diff", "--cached", "--name-only", "--diff-filter=A", "-z",
        # Declared empty on purpose. `git diff --name-only` has no documented
        # negative exit — it prints nothing and exits 0 when there is nothing
        # to report — so every non-zero status is a failure to look.
        negative_statuses=(),
    )
    output = answer.require("what is staged in the index")
    return gitread.nul_paths(output.encode("utf-8", "surrogateescape"))


def _listing(repository: str | Path, *arguments: str) -> list[str]:
    """Tracked or untracked paths, NUL-separated.

    `-z` is not optional here. Without it git C-quotes any path it cannot print
    literally, so `annotations/café.txt` arrives as the literal
    `"annotations/caf\303\251.txt"` — which then matches no declared pattern,
    and the project's `annotations/` exemption silently stops covering it.
    Reproduced against frozen 2.1.1 (`pack_pin.py` already did this correctly;
    this module did not).
    """
    output = gitread._run(repository, "ls-files", "-z", *arguments, text=False)
    assert isinstance(output, bytes)
    return gitread.nul_paths(output)


def classify_workspace(
    repository: str | Path,
    *,
    ignored_private: Iterable[str] = (),
    safe_generated: Iterable[str] = DEFAULT_SAFE_GENERATED,
    must_be_tracked: Iterable[str] = (),
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

    report.untracked_requirements = _check_required_tracking(
        repository, tuple(must_be_tracked), tracked
    )
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
    parser.add_argument("repository", nargs="?", help="defaults to the contract's project.repo_path")
    parser.add_argument("--project", help="path to PROJECT.yaml; supplies every declaration below")
    parser.add_argument("--ignore-private", action="append", default=[], metavar="PATTERN")
    parser.add_argument("--safe-generated", action="append", default=[], metavar="PATTERN")
    parser.add_argument("--must-be-tracked", action="append", default=[], metavar="PATTERN")
    args = parser.parse_args(argv)

    contract = None
    if args.project:
        from project_contract import ContractError, ProjectContract

        try:
            contract = ProjectContract.load(args.project)
        except ContractError as exc:
            # Stated, never degraded. A declaration reader that reports an
            # empty set when it cannot parse its input turns "I could not read
            # the contract" into "the contract asked for nothing".
            print(f"CONTRACT UNREADABLE {exc}")
            return 2

    repository = args.repository or (contract.repository() if contract else None)
    if not repository:
        print("a repository is required, either positionally or via --project")
        return 2

    report = classify_workspace(
        repository,
        ignored_private=[*(contract.ignore_private if contract else ()), *args.ignore_private],
        safe_generated=[*(contract.safe_generated if contract else ()), *args.safe_generated],
        must_be_tracked=[*(contract.must_be_tracked if contract else ()), *args.must_be_tracked],
    )
    print(report.render())
    return 0 if report.clean else 1


if __name__ == "__main__":
    import sys

    # Run the module, not a second copy of it. A file executed as a script is
    # `__main__`, and a sibling that imports it BY NAME gets a separate module
    # object with separate class objects — so an `isinstance` check across that
    # boundary is False for an object that is exactly that class. It crashed
    # `project_context.py --project` against a real consumer's contract, on a
    # shape the suite covers completely: tests import the module and never run
    # it as a script. Imported statically, by name, because a dynamic import
    # would route around the toolbelt's import-closure check.
    from errors import run_cli
    from workspace_report import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
