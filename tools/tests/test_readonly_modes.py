"""The read-only-mode oracle: a governance helper must not write on a read.

The founder requirement this proves, concretely: a governance helper's `--help`
fell through and rewrote a record. For every tool
this release touches or adds, three invocations are proved against a fixture
governance directory, and after each of them the fixture must come back
byte-identical — same files, same bytes, nothing new:

  * `--help`, which must exit 0 and print a usage;
  * one unrecognised flag, which must be refused (non-zero, no traceback)
    without touching anything either;
  * the default read path — the tool's ordinary report, invoked with the
    fixture paths and no mode flag at all. A report that finds problems may
    exit non-zero; finding problems is still a read. What it may not do is
    write, create, or raise.

A fourth case is added for a tool only where its own `--help` text names one
of the convenience modes outright, since a mode that exists is a mode that
can be run. Nothing here asserts the exit status of a default read: a
refusal, a `NOT_ROUTABLE` disposition and a clean report are all reads, and
only a write or a raise is the hazard.

A touched module with no `__main__` block has no CLI and is given no cases;
the excluded set is asserted to be exactly `project_contract.py`, so a new
exclusion is a visible test change rather than a silent hole.

The oracle is proven discriminating by two negative controls: tiny helpers,
written into `tmp_path` and not part of the toolbelt, one of which rewrites a
file on `--help` and one of which creates a new one. The same snapshot check
must catch both, or every passing case above would be equally consistent
with an oracle that never looks.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "tools"
TEMPLATES_DIR = ROOT / "templates"

UNRECOGNISED_FLAG = "--no-such-flag-9f"

#: The pseudo-mode that means "no mode flag at all": the tool's ordinary
#: report over the fixture paths, which is the read a coordinator actually
#: runs and the one the read-only-mode hazard was about.
DEFAULT_READ = "default-read"

#: Convenience modes probed only where a tool's own `--help` text names them
#: literally — this release's tools mostly do not carry any of these, and
#: that absence is discovered here rather than assumed.
CANDIDATE_MODES = ("--version", "--check", "--status", "--dry-run")

#: This release's touched set (T8 brief), deliberately not the whole
#: toolbelt: the founder bounded it to what 2.6.0 adds or changes, and a
#: repository-wide sweep would test tools nobody asked this release about.
#: Each is listed only if it has a `__main__` block, i.e. is a CLI at all —
#: that criterion is applied (and the exclusions asserted) below, so the
#: comment is the intent and `TOOLS_WITHOUT_A_CLI` is the enforcement.
TOUCHED_TOOLS = (
    "provider_manifest.py",
    "routing.py",
    "resource_observation.py",
    "capacity.py",
    "continuation.py",
    "adapter_pin.py",
    "qualification.py",
    "projection.py",
    "console.py",
    "project_contract.py",
    "gitread.py",
)

#: A `__main__` block, whatever the author's spacing or quote style. A
#: substring test for one canonical spelling would silently exclude a real
#: CLI whose author wrote it differently — which is a hole, not a filter.
_MAIN_BLOCK = re.compile(r"""if\s+__name__\s*==\s*(['"])__main__\1\s*:""")

#: Every touched module with no CLI at all. Running such a module as a script
#: executes nothing and exits 0 on any argument, so no assertion here could
#: mean anything for it — but which modules that is must be pinned, not
#: discovered silently by whoever adds one next.
TOOLS_WITHOUT_A_CLI = tuple(
    tool
    for tool in TOUCHED_TOOLS
    if not _MAIN_BLOCK.search((TOOLS_DIR / tool).read_text(encoding="utf-8"))
)

#: The arguments each tool needs beside a mode flag: the fixture files its
#: ordinary path reads, plus any flag its own parser makes mandatory. The
#: same table serves the unrecognised-flag case (argparse answers the flag
#: last) and the default read, so the invocation exercised is the invocation
#: a coordinator would type.
#:
#: `capacity.py` reads no fixture file — its ordinary path is a pure function
#: of its required flags and a task name, none of which a governance
#: directory can supply — so its arguments are spelled out here and it is the
#: snapshot assertion that carries the whole weight for it.
FIXTURE_ARGV = {
    "provider_manifest.py": ("providers/manifest.json",),
    "routing.py": ("observations.jsonl",),
    "resource_observation.py": (),
    "capacity.py": ("--pool", "p", "--authority", "authority_free",
                    "--executor", "e", "task-under-capacity"),
    "continuation.py": ("CONTINUATION.json",),
    "adapter_pin.py": ("--project", "PROJECT.yaml"),
    "qualification.py": ("observations.jsonl",),
    "projection.py": (".",),
    "console.py": (".",),
    "gitread.py": ("repo", "whitespace-damage"),
}

#: `resource_observation.py` reads a status-line payload from stdin; every
#: invocation supplies an empty one so it never blocks waiting for input.
#: Its default read is that empty payload, so its `FIXTURE_ARGV` is empty for
#: the same reason, not by omission.
STDIN_TEXT = {"resource_observation.py": ""}

_FLAG_TOKEN = re.compile(r"(?<![\w-])(--[a-z][a-z-]*)(?![\w-])")


def _flags_mentioned(text: str) -> set[str]:
    """The exact flag spellings a help text names, as whole tokens.

    A substring search would let `--status-line` answer for `--status`,
    which is a different flag with a different contract. Word-bounded so a
    mode is only exercised where the tool actually declares it.
    """
    return set(_FLAG_TOKEN.findall(text))


def _argv_for(tool: str, mode: str) -> tuple[str, ...]:
    if mode == "--help":
        return ("--help",)
    if mode == DEFAULT_READ:
        return FIXTURE_ARGV.get(tool, ())
    return (*FIXTURE_ARGV.get(tool, ()), mode)


def _invoke(tool: str, argv: tuple[str, ...], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS_DIR / tool), *argv],
        cwd=str(cwd), capture_output=True, text=True, timeout=60,
        input=STDIN_TEXT.get(tool),
    )


def _discover_cases() -> list[tuple[str, str]]:
    """(tool, mode) pairs: `--help`, the unrecognised flag and the default
    read for every touched CLI, plus a candidate mode only where that tool's
    own `--help` names it.

    The invocation needs a working directory before any fixture exists, and
    it cannot be `tmp_path`: cases are discovered at import time, when
    collection has not yet built a single fixture. So this uses a
    `TemporaryDirectory` of its own — cleaned up by the context manager, and
    never a fixture directory, because nothing here asserts on it.
    """
    cases: list[tuple[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="readonly-mode-discovery-") as scratch:
        for tool in TOUCHED_TOOLS:
            if tool in TOOLS_WITHOUT_A_CLI:
                continue
            help_result = _invoke(tool, ("--help",), Path(scratch))
            cases.append((tool, "--help"))
            cases.append((tool, UNRECOGNISED_FLAG))
            cases.append((tool, DEFAULT_READ))
            mentioned = _flags_mentioned(help_result.stdout + help_result.stderr)
            for mode in CANDIDATE_MODES:
                if mode in mentioned:
                    cases.append((tool, mode))
    return cases


READONLY_MODE_CASES = _discover_cases()


@pytest.fixture
def fixture_dir(tmp_path):
    return _build_fixture(tmp_path / "fixture")


#: A child environment that inherits nothing: the fixture's history must not
#: depend on whoever runs the suite. A global `commit.gpgsign=true` would
#: fail the commit outright, and an `init.templateDir` pointing elsewhere
#: would shape `.git` — so every channel a user configuration could reach git
#: through is closed here, and the identity is fixed so the commit object's
#: bytes are the same on every machine.
#:
#: `PATH` is the one variable inherited, because the rest of the suite already
#: trusts the git it resolves; pinning system locations instead would make the
#: fixture fail on a machine whose git lives elsewhere, and a path literal is
#: also what the outgoing scan refuses to let leave.
FIXTURE_GIT_ENV = {
    "PATH": os.environ.get("PATH", ""),
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
}


def _run_git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ("git", *args), cwd=str(cwd), capture_output=True, text=True, check=True,
        timeout=30, env=FIXTURE_GIT_ENV,
    )


def _build_fixture(root: Path) -> Path:
    """A minimal governance directory: a subject repository, a project
    contract, a continuation record, a capacity record, an observation log
    and a provider manifest — one of each file shape a touched tool reads."""
    root.mkdir(parents=True)

    repo = root / "repo"
    repo.mkdir()
    _run_git(repo, "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", "init", "-q")
    (repo / "f.txt").write_text("hello\n", encoding="utf-8")
    _run_git(repo, "add", "f.txt")
    _run_git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init")

    (root / "PROJECT.yaml").write_text(
        "project:\n  name: fixture-project\n  repo_path: repo\n"
        "adapters: []\n"
        "routing:\n  observations: observations.jsonl\n"
        "pack:\n  root_path: placeholder\n  version_adopted: placeholder\n",
        encoding="utf-8",
    )

    template = TEMPLATES_DIR / "CONTINUATION.json.template"
    try:
        continuation_text = template.read_text(encoding="utf-8")
        json.loads(continuation_text)
    except (OSError, json.JSONDecodeError):
        continuation_text = json.dumps({
            "capability": "x", "updated_at": "", "actionable": [], "waits": [],
            "blockers": [], "budgets": {}, "evidence": {},
        })
    (root / "CONTINUATION.json").write_text(continuation_text, encoding="utf-8")

    (root / "CAPACITY.json").write_text(json.dumps({"pools": []}), encoding="utf-8")
    # An outcome the derivation recognises, so the tools that read this log
    # get as far as their report instead of stopping at a well-earned refusal
    # about a malformed record — a refusal never reaches the code the oracle
    # is trying to watch.
    (root / "observations.jsonl").write_text(
        json.dumps({"task_class": "x", "configuration": "y", "outcome": "validated"}) + "\n",
        encoding="utf-8",
    )

    providers = root / "providers"
    providers.mkdir()
    shutil.copyfile(TEMPLATES_DIR / "providers" / "moonshot-kimi-code.dormant.json", providers / "manifest.json")

    return root


def _snapshot(root: Path) -> dict[str, str]:
    """Relative path -> sha256 of bytes, for every file under root. Mtime is
    deliberately not part of this: only bytes and names are the property."""
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _differences(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Paths that appeared, vanished or changed bytes between two snapshots."""
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


@pytest.mark.parametrize(
    "tool, mode", READONLY_MODE_CASES,
    ids=[f"{tool}:{mode}" for tool, mode in READONLY_MODE_CASES],
)
def test_a_touched_tools_read_only_mode_leaves_the_fixture_untouched(tool, mode, fixture_dir):
    before = _snapshot(fixture_dir)
    result = _invoke(tool, _argv_for(tool, mode), fixture_dir)
    after = _snapshot(fixture_dir)

    changed = _differences(before, after)
    assert not changed, f"{tool} {mode} left the fixture different at: {changed}"
    new_paths = sorted(set(after) - set(before))
    assert not any(path.endswith((".tmp", ".lock", ".bak")) for path in new_paths), (
        f"{tool} {mode} created residue: {new_paths}"
    )

    if mode == "--help":
        # Help is answered either by argparse (exit 0, usage on stdout) or, for
        # a positional-only CLI, by a usage refusal (usage on stderr, non-zero):
        # both are stated answers. A traceback or silence is neither.
        assert "Traceback" not in result.stderr, f"{tool} --help raised instead of answering:\n{result.stderr}"
        assert "usage" in (result.stdout + result.stderr).lower(), (
            f"{tool} --help printed no usage (exit {result.returncode})"
        )
    if mode == UNRECOGNISED_FLAG:
        assert result.returncode != 0, f"{tool} accepted {UNRECOGNISED_FLAG} as if it were valid"
        assert "Traceback" not in result.stderr, f"{tool} {mode} raised instead of refusing:\n{result.stderr}"
    if mode == DEFAULT_READ:
        # The ordinary read may refuse (exit non-zero) — a report that finds
        # problems is still a read. It may not raise: a traceback is the tool
        # losing, not answering, and a traceback on stdout of a status-line
        # helper is exactly the read-only-mode hazard in another costume.
        assert "Traceback" not in result.stderr, (
            f"{tool} raised on its default read instead of reporting:\n{result.stderr}"
        )


def test_the_touched_modules_without_a_cli_are_exactly_the_expected_set():
    """Which touched modules get no cases must be pinned, not emergent. A
    module that loses its `__main__` block — or a new touched module written
    without one — drops out of the oracle above silently unless this list is
    a visible test change."""
    assert TOOLS_WITHOUT_A_CLI == ("project_contract.py",)


_MUTATING_HELPER = """\
import sys
from pathlib import Path

if "--help" in sys.argv[1:]:
    Path(sys.argv[1]).write_text("rewritten by the negative control\\n", encoding="utf-8")
    print("usage: mutating-helper TARGET [--help]")
    raise SystemExit(0)
print("nothing to do")
"""


def test_the_snapshot_check_detects_a_control_helper_that_rewrites_on_help(tmp_path):
    """The read-only-mode hazard, reproduced on purpose: a helper that mutates a file
    the moment it is asked for `--help`. If the snapshot check missed this,
    every passing case above would be equally consistent with an oracle that
    never looks — so the check must catch this one to mean anything."""
    fixture = _build_fixture(tmp_path / "control-fixture")
    helper = tmp_path / "mutating_helper.py"
    helper.write_text(_MUTATING_HELPER, encoding="utf-8")
    target = fixture / "observations.jsonl"

    before = _snapshot(fixture)
    result = subprocess.run(
        [sys.executable, str(helper), str(target), "--help"],
        cwd=str(fixture), capture_output=True, text=True, timeout=60,
    )
    after = _snapshot(fixture)

    assert result.returncode == 0
    changed = _differences(before, after)
    assert changed, "the control helper's rewrite must be visible as a difference"


_CREATING_HELPER = """\
import sys
from pathlib import Path

if "--help" in sys.argv[1:]:
    Path(sys.argv[1]).write_text("created by the negative control\\n", encoding="utf-8")
    print("usage: creating-helper TARGET [--help]")
    raise SystemExit(0)
print("nothing to do")
"""


def test_the_snapshot_check_detects_a_control_helper_that_creates_on_help(tmp_path):
    """The other half of the property: `--help` must not leave anything new
    behind either. A helper that only rewrites existing files exercises the
    changed-bytes half of the snapshot; this one creates a file that was
    never there, which only the appeared-paths half can see."""
    fixture = _build_fixture(tmp_path / "control-fixture")
    helper = tmp_path / "creating_helper.py"
    helper.write_text(_CREATING_HELPER, encoding="utf-8")
    created = fixture / "created-by-help.json"

    before = _snapshot(fixture)
    result = subprocess.run(
        [sys.executable, str(helper), str(created), "--help"],
        cwd=str(fixture), capture_output=True, text=True, timeout=60,
    )
    after = _snapshot(fixture)

    assert result.returncode == 0
    changed = _differences(before, after)
    assert changed, "the control helper's creation must be visible as a difference"
    assert "created-by-help.json" in changed, (
        f"the control helper's new file must be the difference, not side noise: {changed}"
    )
