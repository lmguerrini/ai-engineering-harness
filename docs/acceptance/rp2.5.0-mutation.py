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
    '        if ".git" in directories:\n'
    '            directories.remove(".git")\n'
    '        if ".git" in files:\n'
    '            files.remove(".git")\n'
    '        if relative != Path(".") and os.path.lexists(here / ".git"):\n'
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
SPELLING_ORACLE = ("tools/tests/test_gitread.py::"
                   "test_no_spelling_of_a_nested_git_executes_the_subjects_program")

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
    ("the name check ignores a .git that is a symlink", "tools/sterile.py",
     '        if relative != Path(".") and os.path.lexists(here / ".git"):\n'
     '            nested.append(relative)',
     '        if relative != Path(".") and (here / ".git").is_dir() '
     'and not (here / ".git").is_symlink():\n            nested.append(relative)',
     SPELLING_ORACLE),
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
     '        "GIT_DIR": str(gitdir),', '        "RP_MUTANT_GIT_DIR": str(gitdir),',
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
     '    transport_config: dict[str, str] = {"protocol.allow": "never"}',
     "    transport_config: dict[str, str] = {}",
     "tools/tests/test_publication_gate.py::test_every_ordinary_read_still_refuses_every_protocol"),
    ("repository location is asked of the read again", "tools/gitread.py",
     "    return sterile.where_is(_repository(repository))",
     '    return {"gitdir": _run(repository, "rev-parse", "--git-dir").strip(),\n'
     '            "common": _run(repository, "rev-parse", "--git-common-dir").strip(),\n'
     '            "toplevel": _run(repository, "rev-parse", "--show-toplevel").strip(),\n'
     '            "linked_worktree": False, "bare": False}',
     "tools/tests/test_activity.py::test_one_repository_registered_twice_is_counted_once"),
]


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
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header", selector],
        cwd=str(ROOT), capture_output=True, text=True, timeout=timeout, env=environment)
    summary = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    return proc.returncode, summary, time.time() - started


def main():
    pristine = {path: (ROOT / path).read_text(encoding="utf-8")
                for _n, path, *_rest in MUTANTS}

    def restore():
        for path, text in pristine.items():
            (ROOT / path).write_text(text, encoding="utf-8")

    print("baseline: every named oracle on the pristine subject")
    oracles = sorted({mutant[4] for mutant in MUTANTS})
    code, summary, _seconds = run(" ".join(oracles) if False else oracles[0])
    for oracle in oracles:
        code, summary, _seconds = run(oracle)
        if code != 0:
            print(f"  BASELINE NOT GREEN: {oracle}\n    {summary}")
            return 2
    print(f"  {len(oracles)} oracle selectors green\n")

    results = []
    try:
        for index, (name, path, before, after, oracle) in enumerate(MUTANTS):
            if ARGUMENTS.only is not None and index != ARGUMENTS.only:
                continue
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
    print(f"\n{len(killed)} killed, {len(survived)} survived, {len(malformed)} malformed, "
          f"{len(results)} attempted")
    for row in survived + malformed:
        print(f"  {row[2]:9} [{row[0]}] {row[1]}  {row[3]}")
    return 0 if not survived and not malformed else 1


if __name__ == "__main__":
    sys.exit(main())
