#!/usr/bin/env python3
"""Build and differentially score the submodule no-child feasibility corpus.

Run from the checkout root::

    FLOOR_FROZEN_ROOT=/path/to/rp240 \
      python3 docs/acceptance/rp2.5.0-submodule-differential.py

The script leaves no fixture repositories behind.  It uses only ordinary Git
fixture setup; the composition and its oracle invoke Git through each release's
``gitread._run``.  Trace2 destinations are supplied exclusively through that
API's ``env_overlay``.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from submodule_no_child import Composition, UnsupportedFrozenForm, _compose_for_control


# The frozen release is selected exactly as the floor differential selects it.
# A developer's directory name is not a release identity and cannot be a shipped
# acceptance prerequisite.
FROZEN_TOOLS = Path(os.environ["FLOOR_FROZEN_ROOT"]).resolve() / "tools"
FIXTURE_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_AUTHOR_NAME": "Proof",
    "GIT_AUTHOR_EMAIL": "proof@example.invalid",
    "GIT_COMMITTER_NAME": "Proof",
    "GIT_COMMITTER_EMAIL": "proof@example.invalid",
    "GIT_AUTHOR_DATE": "2001-02-03T04:05:06+0000",
    "GIT_COMMITTER_DATE": "2001-02-03T04:05:06+0000",
}

READS = (
    ("status porcelain", ("status", "--porcelain")),
    ("status porcelain v2", ("status", "--porcelain=v2")),
    ("status short", ("status", "--short")),
    ("status porcelain uall", ("status", "--porcelain", "-uall")),
    ("status ignore dirty", ("status", "--porcelain", "--ignore-submodules=dirty")),
    ("diff", ("diff",)),
    ("diff submodule", ("diff", "--submodule")),
    ("diff submodule diff", ("diff", "--submodule=diff")),
    ("diff cached", ("diff", "--cached")),
    ("diff-index HEAD", ("diff-index", "HEAD")),
    # ``-z`` is intentionally the same status grammar as its newline sibling;
    # these rows prove separator and raw-path rendering, not a new dispatcher.
    ("status porcelain z", ("status", "--porcelain", "-z")),
    ("status porcelain v2 z", ("status", "--porcelain=v2", "-z")),
    ("status short z", ("status", "--short", "-z")),
)

FIXTURES = (
    "clean-populated",
    "dirty-tracked-content",
    "untracked-content",
    "staged-submodule-change",
    "unstaged-submodule-change",
    "new-commit-gitlink-head-movement",
    "detached-submodule-head",
    "nested-submodules",
    "uninitialised-submodule",
    "uninitialised-ignore-policy",
    "deleted-submodule-worktree",
    "moved-submodule-worktree",
    "symlinked-submodule-worktree",
    "staged-superproject-gitlink",
    "nul-status-forms",
    "quoted-gitlink-path",
    "ordered-parent-after-gitlink",
    "submodule-ignore-policy",
)


def _git(where: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(where), *arguments), env=FIXTURE_ENV,
        check=True, capture_output=True,
    )
    return completed.stdout


def _init(where: Path) -> None:
    where.mkdir()
    _git(where, "init", "-q", "-b", "main")


def _commit(where: Path, message: str) -> None:
    _git(where, "add", "-A")
    _git(where, "commit", "-q", "-m", message)


def _base(root: Path, *, nested: bool = False, sub_path: str = "sub") -> Path:
    """Create a committed superproject with a populated child at ``sub_path``."""
    source = root / "sub-source"
    _init(source)
    (source / "tracked.txt").write_text("base\n")
    (source / "other.txt").write_text("other\n")
    _commit(source, "sub base")

    if nested:
        nested_source = root / "nested-source"
        _init(nested_source)
        (nested_source / "nested.txt").write_text("nested base\n")
        _commit(nested_source, "nested base")
        _git(source, "-c", "protocol.file.allow=always", "submodule", "add", "-q", "../nested-source", "nested")
        _commit(source, "nested link")

    superproject = root / "super"
    _init(superproject)
    (superproject / "top.txt").write_text("top\n")
    _commit(superproject, "top base")
    # The URL recorded in .gitmodules is relative, so it does not make the
    # fixture's commit ID depend on tempfile's randomly chosen directory.
    _git(superproject, "-c", "protocol.file.allow=always", "submodule", "add", "-q", "../sub-source", sub_path)
    _commit(superproject, "add submodule")
    if nested:
        _git(superproject, "-c", "protocol.file.allow=always", "submodule", "update", "--init", "--recursive")
    return superproject


@contextmanager
def fixture(name: str) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix=f"gitread-proof-{name}-") as temporary:
        root = Path(temporary)
        sub_path = "sub\tmodule" if name == "quoted-gitlink-path" else "sub"
        superproject = _base(root, nested=name == "nested-submodules", sub_path=sub_path)
        sub = superproject / sub_path
        if name == "dirty-tracked-content":
            (sub / "tracked.txt").write_text("staged dirty\n")
            _git(sub, "add", "tracked.txt")
            (sub / "other.txt").write_text("unstaged dirty\n")
        elif name == "untracked-content":
            (sub / "untracked.txt").write_text("untracked\n")
        elif name == "staged-submodule-change":
            (sub / "tracked.txt").write_text("staged\n")
            _git(sub, "add", "tracked.txt")
        elif name == "unstaged-submodule-change":
            (sub / "tracked.txt").write_text("unstaged\n")
        elif name == "new-commit-gitlink-head-movement":
            (sub / "tracked.txt").write_text("new commit\n")
            _commit(sub, "sub advance")
        elif name == "detached-submodule-head":
            _git(sub, "checkout", "-q", "--detach", "HEAD")
        elif name == "nested-submodules":
            (sub / "nested" / "nested.txt").write_text("nested dirty\n")
        elif name == "uninitialised-submodule":
            shutil.rmtree(sub)
            sub.mkdir()
        elif name == "uninitialised-ignore-policy":
            shutil.rmtree(sub)
            sub.mkdir()
            _git(superproject, "config", "-f", ".gitmodules", "submodule.sub.ignore", "all")
            _commit(superproject, "declare ignore for uninitialised child")
        elif name == "deleted-submodule-worktree":
            shutil.rmtree(sub)
        elif name == "moved-submodule-worktree":
            sub.rename(superproject / "moved-sub")
        elif name == "symlinked-submodule-worktree":
            external = superproject / "external-sub"
            sub.rename(external)
            # Moving the checkout changes the relative gitdir line that
            # submodule add wrote.  Preserve a usable child, then make only
            # the superproject gitlink path a symbolic link.
            (external / ".git").write_text(f"gitdir: {superproject / '.git' / 'modules' / 'sub'}\n")
            sub.symlink_to(external, target_is_directory=True)
            (external / "tracked.txt").write_text("dirty\n")
        elif name == "staged-superproject-gitlink":
            (sub / "tracked.txt").write_text("advanced\n")
            _commit(sub, "sub advance")
            _git(superproject, "add", "sub")
        elif name == "nul-status-forms":
            (superproject / "aaa.txt").write_text("base\n")
            _commit(superproject, "add aaa")
            (superproject / "aaa.txt").write_text("parent dirty\n")
            (sub / "tracked.txt").write_text("child dirty\n")
        elif name == "quoted-gitlink-path":
            (sub / "tracked.txt").write_text("child dirty\n")
        elif name == "ordered-parent-after-gitlink":
            (superproject / "zzz.txt").write_text("base\n")
            _commit(superproject, "add zzz")
            (superproject / "zzz.txt").write_text("parent dirty\n")
            (sub / "tracked.txt").write_text("child dirty\n")
        elif name == "submodule-ignore-policy":
            _git(superproject, "config", "-f", ".gitmodules", "submodule.sub.ignore", "all")
            _commit(superproject, "declare submodule ignore")
            (sub / "tracked.txt").write_text("child dirty\n")
        yield superproject


@contextmanager
def _import_tools(directory: Path) -> Iterator[object]:
    """Load one release's three top-level modules without cross-release reuse."""
    names = ("gitread", "instrument", "errors", "sterile")
    saved = {name: sys.modules.pop(name, None) for name in names}
    sys.path.insert(0, str(directory))
    try:
        yield importlib.import_module("gitread")
    finally:
        for name in names:
            sys.modules.pop(name, None)
        sys.path.remove(str(directory))
        for name, module in saved.items():
            if module is not None:
                sys.modules[name] = module


@dataclass(frozen=True)
class TraceResult:
    children: int
    bound: bool
    detail: str


def _expected_trace_argv(arguments: tuple[str, ...]) -> list[str]:
    """The argv after the frozen boundary's documented hardening insertion."""
    verb, *rest = arguments
    if verb in {"diff", "diff-index", "diff-tree", "log", "show"}:
        return [verb, "--no-ext-diff", "--no-textconv", *rest]
    return [verb, *rest]


def _trace(path: Path, arguments: tuple[str, ...]) -> TraceResult:
    """Prove a fresh trace belongs to this exact Git invocation.

    A version event alone establishes only that *some* Git process wrote the
    file.  A valid witness instead has one session id shared by version,
    start (whose argv names this read), and terminal exit.  The direct and
    composed harnesses use a fresh destination for every runner call.
    """
    if not path.exists():
        return TraceResult(0, False, "trace absent")
    try:
        events = [json.loads(line) for line in path.read_text().splitlines() if line]
    except json.JSONDecodeError as exc:
        return TraceResult(0, False, f"invalid trace JSON: {exc}")
    children = sum(event.get("event") == "child_start" for event in events)
    expected = _expected_trace_argv(arguments)
    starts = [
        event for event in events
        if event.get("event") == "start" and event.get("argv", [None])[1:] == expected
    ]
    if not starts:
        return TraceResult(children, False, f"no start argv for {' '.join(expected)}")
    for start in starts:
        sid = start.get("sid")
        has_version = any(event.get("event") == "version" and event.get("sid") == sid for event in events)
        has_exit = any(event.get("event") == "exit" and event.get("sid") == sid for event in events)
        if has_version and has_exit:
            return TraceResult(children, True, f"sid={sid}")
    return TraceResult(children, False, "start lacked same-session version or exit")


@dataclass(frozen=True)
class Captured:
    value: bytes | None
    refusal: str | None
    children: int
    trace_bound: bool
    trace_detail: str


def _frozen_call(gitread: object, repo: Path, arguments: tuple[str, ...], trace: Path) -> Captured:
    try:
        value = gitread._run(repo, *arguments, text=False, env_overlay={"GIT_TRACE2_EVENT": str(trace)})
        refusal = None
    except Exception as exc:  # frozen refusal is an expected corpus result
        value = None
        refusal = f"{type(exc).__name__}: {exc}"
    result = _trace(trace, arguments)
    # ``diff --submodule=diff`` is refused at the frozen API boundary before
    # Git starts, so there is no governed invocation whose trace could bind.
    if refusal and refusal.startswith("IntegrityError:") and not trace.exists():
        result = TraceResult(0, True, "pre-invocation frozen refusal")
    return Captured(value, refusal, result.children, result.bound, result.detail)


class InvocationTracer:
    """Give every composed primitive a fresh, argv-bound Trace2 witness."""

    def __init__(self, gitread: object, requested_trace: Path):
        self.gitread = gitread
        self.requested_trace = requested_trace
        self.directory = requested_trace.parent / f"{requested_trace.stem}-calls"
        self.directory.mkdir(exist_ok=True)
        self.number = 0
        self.children = 0
        self.problems: list[str] = []

    def run(
        self, repository: Path, *arguments: str, text: bool = False,
        env_overlay: dict[str, str] | None = None,
    ) -> str | bytes:
        self.number += 1
        supplied = (env_overlay or {}).get("GIT_TRACE2_EVENT")
        if supplied != str(self.requested_trace):
            self.problems.append(f"call {self.number} dropped or changed caller trace overlay")
        trace = self.directory / f"{self.number:03d}.json"
        overlay = dict(env_overlay or {})
        overlay["GIT_TRACE2_EVENT"] = str(trace)
        try:
            return self.gitread._run(repository, *arguments, text=text, env_overlay=overlay)
        finally:
            result = _trace(trace, tuple(arguments))
            self.children += result.children
            if not result.bound:
                self.problems.append(f"call {self.number}: {result.detail}")

    def result(self) -> TraceResult:
        if self.problems:
            return TraceResult(self.children, False, "; ".join(self.problems))
        return TraceResult(self.children, True, f"{self.number} invocation(s) bound")


def _candidate_call(gitread: object, repo: Path, arguments: tuple[str, ...], trace: Path, fault: str | None = None) -> tuple[Composition | None, str | None, int, bool, str]:
    tracer = InvocationTracer(gitread, trace)
    try:
        answer = _compose_for_control(
            repo, *arguments, runner=tracer.run,
            env_overlay={"GIT_TRACE2_EVENT": str(trace)}, fault=fault,
        )
        refusal = None
    except Exception as exc:
        answer = None
        refusal = f"{type(exc).__name__}: {exc}"
    result = tracer.result()
    # The explicit frozen pre-invocation refusal makes no runner call.
    if refusal and refusal.startswith("UnsupportedFrozenForm:") and tracer.number == 0:
        result = TraceResult(0, True, "pre-invocation composed refusal")
    return answer, refusal, result.children, result.bound, result.detail


def _oracle_child_v2(frozen: object, repo: Path) -> bytes:
    return frozen._run(repo / "sub", "status", "--porcelain=v2", text=False)


def main() -> int:
    requested = tuple(filter(None, os.environ.get("PROOF_FIXTURES", "").split(",")))
    selected_fixtures = tuple(name for name in FIXTURES if not requested or name in requested)
    if requested and len(selected_fixtures) != len(requested):
        unknown = sorted(set(requested) - set(selected_fixtures))
        raise SystemExit(f"unknown fixture(s): {', '.join(unknown)}")
    run_controls = not os.environ.get("PROOF_SKIP_CONTROLS")
    failures: list[str] = []
    rows: list[str] = []
    control_rows: list[str] = []
    # The candidate calls the frozen boundary's own `_run` for every primitive.
    # This isolates the proposed composition from unrelated later-release
    # changes while comparing its bytes to that same release's direct answer.
    with _import_tools(FROZEN_TOOLS) as frozen:
        for fixture_name in selected_fixtures:
            with fixture(fixture_name) as repo:
                for read_name, arguments in READS:
                    trace_dir = repo.parent / "trace"
                    trace_dir.mkdir(exist_ok=True)
                    frozen_trace = trace_dir / f"frozen-{read_name.replace(' ', '-')}.json"
                    candidate_trace = trace_dir / f"candidate-{read_name.replace(' ', '-')}.json"
                    expected = _frozen_call(frozen, repo, arguments, frozen_trace)
                    actual, refusal, children, bound, trace_detail = _candidate_call(
                        frozen, repo, arguments, candidate_trace
                    )
                    if fixture_name == "submodule-ignore-policy":
                        ok = (
                            (expected.value == b"" or expected.refusal is not None)
                            and refusal is not None
                            and (
                                "submodule declares an ignore policy" in refusal
                                or (
                                    expected.refusal is not None
                                    and expected.refusal.startswith("IntegrityError:")
                                    and refusal.startswith("UnsupportedFrozenForm:")
                                )
                            )
                            and expected.trace_bound and bound
                        )
                        detail = (
                            "declared refusal for submodule ignore policy; "
                            f"frozen_refusal={expected.refusal!r}; "
                            f"frozen_trace={expected.trace_bound}; composed_trace={bound}"
                        )
                    elif expected.refusal:
                        if expected.refusal.startswith("IntegrityError:"):
                            refusal_matches = refusal is not None and refusal.startswith("UnsupportedFrozenForm:")
                        else:
                            refusal_matches = refusal == expected.refusal
                        ok = refusal_matches and expected.trace_bound and bound
                        detail = "refusal"
                    else:
                        ok = (
                            actual is not None and actual.value == expected.value and children == 0
                            and expected.trace_bound and bound
                        )
                        detail = (
                            f"{len(expected.value or b'')} bytes; frozen children={expected.children}; "
                            f"composed children={children}; trace={trace_detail}"
                        )
                    marker = "PASS" if ok else "FAIL"
                    rows.append(f"{marker}\t{fixture_name}\t{read_name}\t{detail}")
                    if not ok:
                        failures.append(rows[-1])

        # Each control changes exactly one part of the composition.  The
        # staging control is tested against the direct child observation because
        # the frozen parent formats staged and unstaged child dirt as the same
        # outer `M`, an observed property rather than a weakness hidden here.
        controls = (
            ("missed dirty state", "dirty-tracked-content", ("status", "--porcelain=v2"), "missed-dirty-state"),
            ("wrong staged versus unstaged", "staged-submodule-change", ("status", "--porcelain=v2"), "wrong-staged-versus-unstaged"),
            ("wrong new-commit classification", "new-commit-gitlink-head-movement", ("status", "--porcelain=v2"), "wrong-new-commit-classification"),
            ("omitted untracked state", "untracked-content", ("status", "--porcelain=v2"), "omitted-untracked-state"),
            ("wrong gitlink identity", "new-commit-gitlink-head-movement", ("diff",), "wrong-gitlink-identity"),
            ("accidental child process", "clean-populated", ("status", "--porcelain"), "accidental-child-process"),
            ("symlink classification", "symlinked-submodule-worktree", ("status", "--porcelain"), "omit-symlink-classification"),
            ("staged gitlink identity", "staged-superproject-gitlink", ("diff-index", "HEAD"), "omit-staged-gitlink"),
            ("NUL separator", "nul-status-forms", ("status", "--porcelain", "-z"), "newline-for-nul"),
            ("Git path quoting", "quoted-gitlink-path", ("status", "--porcelain"), "raw-gitlink-path"),
            ("index record ordering", "ordered-parent-after-gitlink", ("status", "--porcelain"), "append-gitlinks"),
            ("dropped trace overlay", "clean-populated", ("status", "--porcelain"), "dropped-trace-child-process"),
        )
        for label, fixture_name, arguments, fault in (controls if run_controls else ()):
            with fixture(fixture_name) as repo:
                expected = _frozen_call(frozen, repo, arguments, repo.parent / "control-frozen.json")
                actual, refusal, children, bound, trace_detail = _candidate_call(
                    frozen, repo, arguments, repo.parent / "control-candidate.json", fault
                )
                if fault == "wrong-staged-versus-unstaged":
                    oracle = _oracle_child_v2(frozen, repo)
                    detected = actual is not None and actual.observations.get(b"sub") != oracle
                elif fault == "accidental-child-process":
                    detected = children > 0 and bound
                elif fault == "dropped-trace-child-process":
                    detected = not bound
                else:
                    detected = (
                        (actual is not None and expected.value != actual.value)
                        or (expected.refusal is not None and refusal != expected.refusal)
                    )
                marker = "DETECTED" if detected else "MISSED"
                control_rows.append(f"{marker}\t{label}\tchildren={children}; trace={trace_detail}")
                if not detected:
                    failures.append(control_rows[-1])

    print("DIFFERENTIAL CORPUS")
    print("\n".join(rows))
    print("POSITIVE CONTROLS")
    print("\n".join(control_rows))
    if failures:
        print("FAILURES")
        print("\n".join(failures))
        return 1
    print(
        f"PASS: {len(rows)} composition matrix rows and {len(control_rows)} positive controls "
        "through frozen 2.4.0 gitread primitives; this does not exercise the candidate _run integration"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
