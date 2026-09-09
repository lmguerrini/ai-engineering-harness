"""Mutation scoring for the 2.5.0 boundary, as a runnable file.

    python3 docs/acceptance/rp2.5.0-mutation.py [--only N] [pack root]

The gate record cites a mutation figure. An independent certification could
reproduce the property but not the figure, because the harness lived outside the
release — so it ships, and the number is recomputable rather than transcribed.

Each mutant reverses one thing the design says is load-bearing, and names the
oracle that must die. The rules this obeys are the ones the release plan sets:
a verified-green baseline first; mutate the subject and never a guard or a test;
reject a malformed or non-effective mutant rather than counting it; restore the
subject after a timeout or an interruption; an unrelated failure is not a kill.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[2]))
parser.add_argument("--only", type=int, default=None)
ARGUMENTS = parser.parse_args()
ROOT = Path(ARGUMENTS.root)

NESTED_BEFORE = (
    '        entry = dot_git_name(here, list(directories) + list(files))\n'
    '        if entry in directories:\n'
    '            directories.remove(entry)\n'
    '        if entry in files:\n'
    '            files.remove(entry)\n'
    '        if relative != Path(".") and entry is not None:\n'
    '            nested.append(relative)\n'
    '        for name in list(directories):\n'
    '            source = here / name\n'
    '            if source.is_symlink():'
)
NESTED_AFTER = (
    '        for name in list(directories):\n'
    '            source = here / name\n'
    '            if source.is_symlink():'
)
DOT_GIT_NAME_BEFORE = (
    '    probe = here / DOT_GIT\n'
    '    if not os.path.lexists(probe):\n'
    '        return None'
)
DOT_GIT_NAME_AFTER = (
    '    probe = here / DOT_GIT\n'
    '    if not probe.is_dir() or probe.is_symlink():\n'
    '        return None'
)
SPELLING_ORACLE = ("tools/tests/test_gitread.py::"
                   "test_no_spelling_of_a_nested_git_executes_the_subjects_program")
KIND_ORACLE = ("tools/tests/test_gitread.py::"
               "test_a_nested_git_symlink_is_rebuilt_as_harness_state")

#: (why it matters, file, the exact text to replace, what to replace it with, the oracle)
#:
#: The first entry is the defect that actually shipped: the directory-symlink
#: branch ran BEFORE the name check and consumed `.git`, so the symlink was
#: reproduced into the view and pointed Git back at the subject's configuration.
#: An earlier attempt at this mutant used `Path.is_dir()`, which FOLLOWS a
#: symlink and therefore still detected the spelling it was meant to miss — a
#: non-effective mutant, and it is recorded here because rejecting one is part of
#: the discipline rather than an embarrassment.
MUTANTS = [
    ("the symlink branch consumes .git before the name check sees it",
     "tools/sterile.py", NESTED_BEFORE, NESTED_AFTER, SPELLING_ORACLE),
    ("the name check asks the KIND of .git instead of the name", "tools/sterile.py",
     DOT_GIT_NAME_BEFORE, DOT_GIT_NAME_AFTER,
     KIND_ORACLE),
    ("the view post-condition is never called", "tools/sterile.py",
     "    _every_git_in_the_view_is_ours(view, built)\n", "    pass\n",
     "tools/tests/test_gitread.py::test_the_view_builder_actually_runs_its_own_post_condition"),
    ("an unbuildable nested repository is skipped instead of refused", "tools/sterile.py",
     '            raise GitRefusal(\n                f"the repository at {relative} inside '
     'the working tree could not be rebuilt "',
     '            continue\n            raise GitRefusal(\n                f"the repository at '
     '{relative} inside the working tree could not be rebuilt "',
     "tools/tests/test_gitread.py::test_a_nested_repository_that_cannot_be_rebuilt_refuses_the_read"),
    ("the operator's home is inherited again", "tools/sterile.py",
     '        "HOME": str(home),\n        "XDG_CONFIG_HOME": str(home),',
     '        "RP_MUTANT_HOME": str(home),',
     "tools/tests/test_gitread.py::test_an_operators_home_does_not_shape_a_governed_answer"),
    ("a ref store this build cannot import is answered about", "tools/sterile.py",
     "    if not reproducible:", "    if False:",
     "tools/tests/test_gitread.py::test_a_ref_store_the_build_cannot_import_is_refused_not_answered"),
    ("the subject's own git directory is used again", "tools/sterile.py",
     '        "GIT_DIR": os.path.relpath(gitdir, cwd),',
     '        "RP_MUTANT_GIT_DIR": os.path.relpath(gitdir, cwd),',
     "tools/tests/test_gitread.py::"
     "test_every_configuration_source_git_reports_is_one_the_harness_wrote"),
    ("content-encoding descriptors are dropped", "tools/sterile.py",
     '    "core.autocrlf",\n    "core.eol",', "",
     "tools/tests/test_gitread.py::test_the_sterile_answer_equals_real_gits_answer"),
    ("a config read goes back to the harness's own configuration", "tools/gitread.py",
     '        if sources:\n            arguments = (arguments[0], "--file", '
     'str(sources[0]), *arguments[1:])',
     "        pass",
     "tools/tests/test_gitread.py::"
     "test_a_configuration_read_reports_the_subjects_settings_not_the_harnesss"),
    ("the standing transport refusal is dropped", "tools/gitread.py",
     '        "protocol.allow": "never",\n', "",
     "tools/tests/test_gitread.py::test_the_standing_transport_refusal_reaches_the_read"),
    ("repository location is asked of the read again", "tools/gitread.py",
     "    return sterile.where_is(_repository(repository))",
     '    return {"gitdir": _run(repository, "rev-parse", "--git-dir").strip(),\n'
     '            "common": _run(repository, "rev-parse", "--git-common-dir").strip(),\n'
     '            "toplevel": _run(repository, "rev-parse", "--show-toplevel").strip(),\n'
     '            "linked_worktree": False, "bare": False}',
     "tools/tests/test_gitread.py::test_repository_location_is_taken_from_subject_files"),
#: A7.1 added a second backend and a composition above the boundary, so five
#: more things became load-bearing. They are APPENDED rather than substituted:
#: the implementation pass replaced this file with its own five and dropped the
#: eleven below, along with the assertion that the subject is restored — which is
#: the assertion that makes a harness editing real source safe to ship.
    ("the local child denial is removed",
     "tools/gitread.py",
     'return profile + "(deny process-fork)\\n" + f"(deny file-write* {denied})\\n"',
     'return profile + f"(deny file-write* {denied})\\n"',
     "tools/tests/test_gitread.py::test_a_local_read_creates_no_child"),
    ("the local backend is applied to a caller-named transport",
     "tools/gitread.py",
     "local_backend = _uses_local_backend(verb, allow_transports)",
     "local_backend = True",
     "tools/tests/test_publication_gate.py::test_a_file_remote_still_verifies_after_the_change"),
    ("the composition invents a submodule status field",
     "tools/submodule_no_child.py",
     'return b"S" + (b"C" if self.commit_changed else b".") + (',
     'return b"X" + (b"C" if self.commit_changed else b".") + (',
     "docs/acceptance/rp2.5.0-submodule-differential.py"),
    ("a gitlink identity is taken from .gitmodules rather than the index",
     "tools/submodule_no_child.py",
     'runner, repository, "ls-files", "--stage", "-z", env_overlay=env_overlay,',
     'runner, repository, "config", "--file", str(repository / ".gitmodules"), "--get-regexp", "path", env_overlay=env_overlay,',
     "tools/tests/test_gitread.py::test_routing_does_not_consult_the_subject"),
    ("zero child starts is accepted without a Git-written trace",
     "tools/gitread.py",
     'if not any(event.get("event") == "version" for event in events):',
     "if False:",
     "tools/tests/test_gitread.py::test_a_local_read_creates_no_child"),
    ("the public path-restoration call is bypassed",
     "tools/gitread.py",
     "    return _restore_subject_paths(result.stdout, read, repository, arguments=tuple(arguments))",
     "    return result.stdout",
     "tools/tests/test_gitread.py::"
     "test_public_run_restores_constructed_gitdir_before_discard"),
    ("the environment-overlay guard is removed",
     "tools/sterile.py",
     "    if replaced or undelegated_git:\n",
     "    if False:\n",
     "tools/tests/test_gitread.py::"
     "test_a_public_overlay_cannot_retarget_the_subjects_index"),
    ("the subject's own programs are carried into the constructed directory",
     "tools/sterile.py",
     "                *_PROGRAM_ROOTS,",
     "",
     "tools/tests/test_gitread.py::"
     "test_the_constructed_git_directory_carries_no_program_of_the_subjects"),
    ("the constructed configuration stops pointing hooks at an empty directory",
     "tools/sterile.py",
     '    core["hookspath"] = str(empty_hooks)',
     "",
     "tools/tests/test_gitread.py::"
     "test_the_constructed_configuration_points_hooks_at_an_empty_harness_directory"),
    ("a linked worktree common directory is restored as its private git directory",
     "tools/gitread.py",
     '    if arguments == ("rev-parse", "--git-common-dir") and location["linked_worktree"]:\n',
     "    if False:\n",
     "tools/tests/test_gitread.py::"
     "test_a_linked_worktrees_common_directory_matches_real_git_byte_for_byte"),
    ("a remote's last url is fetched from instead of its first",
     "tools/gitread.py",
     "        url = found[0] if found else None",
     "        url = found[-1] if found else None",
     "tools/tests/test_gitread.py::"
     "test_a_remote_with_two_urls_is_fetched_from_the_first_like_real_git"),
    ("a repeated remote setting is carried as its last value only",
     "tools/sterile.py",
     "            remote_tracking.setdefault(remote, {})[setting] = all_declared.get(name, [value])",
     "            remote_tracking.setdefault(remote, {})[setting] = [value]",
     "tools/tests/test_gitread.py::"
     "test_a_repeated_fetch_refspec_still_finds_the_branchs_upstream"),
    ("an include in the main configuration is answered around instead of refused",
     "tools/sterile.py",
     "        for name in common_declared\n    ):",
     "        for name in ()\n    ):",
     "tools/tests/test_gitread.py::"
     "test_a_main_configuration_include_is_refused_rather_than_answered_around"),
]


def collect(selectors, timeout=900):
    """How many tests the named oracles actually amount to, asked of pytest.

    The gate record stated this number in prose, where it went stale the moment a
    parametrisation changed: the record said twenty-four and collection said
    twenty-two. A figure a reader cannot recompute is the thing this pack's own
    rule about figures exists to stop, so it is derived here and printed.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         "--no-header", *selectors],
        cwd=str(ROOT), capture_output=True, text=True, timeout=timeout,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    found = re.search(r"(\d+) tests? collected", proc.stdout)
    return int(found.group(1)) if found else 0


def run(selector, timeout=900):
    """No bytecode cache, ever.

    A mutant KILLED alone once SURVIVED in a full run, which is order dependence
    in this harness rather than a property of the subject: CPython decides whether
    to recompile from (mtime, size), and a mutation loop rewrites the same paths
    many times a second. A score taken against a stale `.pyc` is wrong in
    whichever direction happens to suit.
    """
    for cache in ROOT.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    started = time.time()
    # An oracle may be a shipped acceptance SCRIPT rather than a pytest selector.
    # Running a script through pytest imports it as a test module, which fails at
    # import for anything that reads its configuration from the environment — and
    # reads as a red baseline rather than as the harness calling it wrongly.
    command = (
        [sys.executable, selector]
        if selector.endswith(".py")
        else [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
              "--no-header", selector]
    )
    proc = subprocess.run(
        command,
        cwd=str(ROOT), capture_output=True, text=True, timeout=timeout, env=environment)
    summary = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    return proc.returncode, summary, time.time() - started


def main():
    pristine = {path: (ROOT / path).read_text(encoding="utf-8")
                for _n, path, *_rest in MUTANTS}
    selected = [
        (index, mutant) for index, mutant in enumerate(MUTANTS)
        if ARGUMENTS.only is None or index == ARGUMENTS.only
    ]
    if not selected:
        print(f"no mutant has index {ARGUMENTS.only}")
        return 2

    def restore():
        for path, text in pristine.items():
            (ROOT / path).write_text(text, encoding="utf-8")

    print("baseline: every named oracle on the pristine subject")
    # A focused ``--only`` proof establishes only the selected mutant's
    # baseline.  The full run remains the all-oracle baseline; making a focused
    # proof construct unrelated fixtures would make its scope larger, not safer.
    oracles = sorted({mutant[4] for _index, mutant in selected})
    collected = collect(oracles)
    for oracle in oracles:
        code, summary, _seconds = run(oracle)
        if code != 0:
            print(f"  BASELINE NOT GREEN: {oracle}\n    {summary}")
            return 2
    print(f"  {len(oracles)} oracle selectors green over {collected} collected tests\n")

    results = []
    unstable: list = []
    try:
        for index, (name, path, before, after, oracle) in selected:
            source = pristine[path]
            occurrences = source.count(before)
            if occurrences != 1:
                results.append((index, name, "MALFORMED",
                                f"the anchor appears {occurrences} times"))
                print(f"[{index}] MALFORMED  {name}  (anchor appears {occurrences} times)")
                continue
            (ROOT / path).write_text(source.replace(before, after, 1), encoding="utf-8")
            try:
                code, summary, seconds = run(oracle)
                if code == 0:
                    # A SURVIVOR IS A CLAIM ABOUT AN ORACLE, AND ONE OBSERVATION IS
                    # NOT ONE. A mutant killed on its own every time was seen to
                    # survive inside a full run: the oracle it belonged to compared
                    # end-of-line conversion only when the fixture landed inside
                    # Git's one-second racily-clean window, so under load it
                    # sometimes compared nothing and passed. The fixture is fixed,
                    # and this stands behind it — because the next oracle to depend
                    # on the clock should cost a visible UNSTABLE line rather than a
                    # quietly wrong score.
                    again, again_summary, again_seconds = run(oracle)
                    seconds += again_seconds
                    if again != 0:
                        print(f"[{index}] UNSTABLE   {name}  survived once, killed on re-run")
                        unstable.append((index, name))
                        code, summary = again, again_summary
            finally:
                restore()
            verdict = "KILLED" if code != 0 else "SURVIVED"
            results.append((index, name, verdict, summary))
            print(f"[{index}] {verdict:9} {name}\n      {summary}  ({seconds:.1f}s)")
    finally:
        restore()
        for path, text in pristine.items():
            if (ROOT / path).read_text(encoding="utf-8") != text:
                print(f"!! {path} WAS NOT RESTORED")
                return 3
        print("\nsubject restored byte-identical")

    killed = [r for r in results if r[2] == "KILLED"]
    survived = [r for r in results if r[2] == "SURVIVED"]
    malformed = [r for r in results if r[2] == "MALFORMED"]
    if unstable:
        print(f"\n{len(unstable)} mutant(s) gave a different verdict on re-run, which means an "
              f"oracle here does not discriminate deterministically:")
        for index, name in unstable:
            print(f"  UNSTABLE [{index}] {name}")
    print(f"\n{len(killed)} killed, {len(survived)} survived, {len(malformed)} malformed, "
          f"{len(results)} attempted")
    for row in survived + malformed:
        print(f"  {row[2]:9} [{row[0]}] {row[1]}  {row[3]}")
    return 0 if not survived and not malformed and not unstable else 1


if __name__ == "__main__":
    sys.exit(main())
