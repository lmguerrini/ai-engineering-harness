"""`pathmatch`'s first direct tests, oracled against git rather than a table.

This module had no tests of its own. It was covered only through the callers
that use it, which is how it shipped agreeing with git on the cases somebody
had thought of and disagreeing on thirteen they had not — every one of them
under-matching, so a declared exemption silently covered nothing and the report
looked normal.

So the oracle here is **real `git check-ignore`**, asked about the same
pattern/path pairs. That matters more than the number of cases: the claim this
module makes is "gitignore semantics", and the only thing that can falsify a
claim about gitignore is gitignore. A hand-written expectation table is written
by the same person who wrote the implementation, from the same misunderstanding.

## The oracle has to be isolated, and that is not a detail

The first differential run reported **114** divergences. Every one was the
harness: `git check-ignore` consults `core.excludesFile`, and this machine's
global ignore file contained `dist/`, `build/`, `node_modules/` and `*.log`, so
git answered "ignored" for patterns it had never been given. Isolating the
oracle left 13 real divergences.

An oracle that answers from a source the test did not control produces
confident, specific, entirely fictional findings — and it fails in the
direction of *more* findings, which reads as diligence. Every repository built
below therefore pins `core.excludesFile` to `/dev/null`, empties
`.git/info/exclude`, and sets `core.ignorecase=false`.
"""

import shutil
import subprocess

import pytest

from pathmatch import matches_any, matching_patterns

# --- the thirteen reproduced divergences, as direct assertions ---------------
#
# Stated independently of git so the specific defects stay pinned even where
# the differential cannot run. Each was produced by the differential first;
# none was written from reasoning about what the code ought to do.

WILDCARD_DIRECTORY = [
    ("dist*/", "dist/a.txt"),
    ("dist*/", "dist/sub/a.txt"),
    ("dist*/", "dist-1/a.txt"),
    ("dist*/", "distx/a.txt"),
    ("build*/", "build/x.o"),
    ("build*/", "build2/x.o"),
    ("build*/", "src/build/x.o"),
    ("*.egg-info/", "f.egg-info/x"),
    ("*.egg-info/", "pkg/f.egg-info/x"),
]

BARE_NAME_COVERS_THE_DIRECTORY = [
    ("annotations", "docs/annotations/x.md"),
    ("annotations", "annotations/x.md"),
    ("annotations", "annotations/deep/x.md"),
]

MATCHED_DIRECTORY_COVERS_EVERYTHING_BENEATH = [
    ("dist/*", "dist/sub/a.txt"),
]


@pytest.mark.parametrize(
    "pattern, path",
    WILDCARD_DIRECTORY + BARE_NAME_COVERS_THE_DIRECTORY + MATCHED_DIRECTORY_COVERS_EVERYTHING_BENEATH,
)
def test_the_reproduced_under_matches_now_match(pattern, path):
    """Each of these silently covered nothing before RP2.2."""
    assert matches_any(path, [pattern])


def test_a_wildcard_directory_name_is_not_compared_with_string_equality():
    """The root cause behind nine of the thirteen: the bare-directory branch
    used `in`, so only literal directory names ever matched."""
    assert matches_any("dist-1/a.txt", ["dist*/"])
    assert not matches_any("adist/a.txt", ["dist*/"])


def test_star_still_does_not_cross_a_separator():
    """The property the module was written for, unchanged by the repair."""
    assert matches_any("dist/a.txt", ["dist/*"])
    assert not matches_any("src/deep/x.py", ["src/*.py"])
    assert matches_any("src/x.py", ["src/*.py"])


def test_a_directory_only_pattern_never_matches_the_file_itself():
    assert not matches_any("dist", ["dist/"])
    assert matches_any("dist", ["dist"])


def test_matching_is_case_sensitive():
    """`fnmatch` applies `os.path.normcase`, so this answered differently on a
    case-insensitive filesystem than on a case-sensitive one."""
    assert not matches_any("DIST/a.txt", ["dist/"])
    assert not matches_any("a.txt", ["A.txt"])


def test_double_star_matches_zero_or_more_components():
    assert matches_any("build/x.o", ["**/build/"])
    assert matches_any("src/deep/build/x.o", ["**/build/"])
    assert matches_any("a/b/c/d.txt", ["a/**/d.txt"])
    assert matches_any("a/d.txt", ["a/**/d.txt"])


def test_an_interior_separator_anchors_the_pattern():
    assert matches_any("a/b/c.txt", ["a/b/"])
    assert not matches_any("x/a/b/c.txt", ["a/b/"])
    assert matches_any("x/a/b/c.txt", ["**/a/b/"])


def test_matching_patterns_reports_which_declaration_covered_a_path():
    """The other half of the original defect: a declaration that matches
    nothing must be visible as matching nothing."""
    declared = ["dist/", "annotations/", "*.log"]
    assert matching_patterns("dist/a.txt", declared) == ["dist/"]
    assert matching_patterns("src/main.py", declared) == []


def test_an_empty_pattern_matches_nothing():
    assert not matches_any("a.txt", ["", "/", "//"])


# --- the differential ---------------------------------------------------------

PATHS = [
    "a.txt", "A.txt", "dist/a.txt", "dist/sub/a.txt", "dist/sub/deep/a.txt",
    "dist-1/a.txt", "distx/a.txt", "DIST/a.txt",
    "docs/annotations/x.md", "annotations/x.md", "annotations/deep/x.md", "annotations",
    "build/x.o", "build2/x.o", "src/build/x.o", "src/deep/build/x.o",
    "a/b/c.txt", "a/b.txt", "x/a/b/c.txt", "a/b/c/d.txt",
    "node_modules/p/i.js", "src/node_modules/p/i.js",
    "f.egg-info/x", "pkg/f.egg-info/x",
    "logs/2024/a.log", "a.log", "src/a.log", "logs/a.log",
    "x.py", "src/x.py", "__pycache__/x.pyc", "src/__pycache__/x.pyc",
    "notes/2024-01/day.md", "t/e/s/t.txt",
]

PATTERNS = [
    "dist/", "dist*/", "annotations/", "annotations", "build*/", "a/b/", "/dist/",
    "*.log", "node_modules/", "*.egg-info/", "logs/*/", "dist/*", "/a.txt",
    "__pycache__/", "*.py", "a/b/c.txt", "**/build/", "logs/**", "**/*.log",
    "a/**/d.txt", "?.txt", "[ab].txt", "src/**/x.py", "dist", "DIST/",
    "notes/*/day.md", "t/**", "**", "*",
]


@pytest.fixture(scope="module")
def oracle(tmp_path_factory):
    """A repository whose ignore rules are ONLY the pattern under test."""
    if shutil.which("git") is None:  # pragma: no cover - environment
        pytest.skip("git is required to oracle gitignore semantics")
    root = tmp_path_factory.mktemp("pathmatch-oracle")
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
    for key, value in (("core.excludesFile", "/dev/null"), ("core.ignorecase", "false")):
        subprocess.run(["git", "config", key, value], cwd=root, check=True)
    (root / ".git" / "info" / "exclude").write_text("")

    def ignored(pattern, paths):
        (root / ".gitignore").write_text(pattern + "\n")
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "-z", "--stdin"],
            cwd=root, input="\0".join(paths).encode(), capture_output=True,
        )
        return {entry.decode() for entry in result.stdout.split(b"\0") if entry}

    return ignored


def test_the_oracle_is_isolated_from_this_machines_global_ignore_rules(oracle):
    """Guards the harness, not the module. `dist/` is in this machine's global
    ignore file; if it leaked in, the oracle would answer for every pattern and
    the differential below would be worthless in the reassuring direction."""
    assert oracle("nothing-matches-this", ["dist/a.txt", "a.log", "node_modules/p.js"]) == set()


@pytest.mark.parametrize("pattern", PATTERNS)
def test_matches_git_check_ignore(oracle, pattern):
    truth = oracle(pattern, PATHS)
    mine = {path for path in PATHS if matches_any(path, [pattern])}
    under = truth - mine
    over = mine - truth
    assert not under, f"{pattern!r} under-matches (a declared rule covering nothing): {sorted(under)}"
    assert not over, f"{pattern!r} over-matches: {sorted(over)}"
