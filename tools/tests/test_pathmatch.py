"""`pathmatch`'s first direct tests, oracled against git rather than a table.

This module had no tests of its own. It was covered only through the callers
that use it, which is how it shipped agreeing with git on the cases somebody
had thought of and disagreeing on the ones they had not — a declared exemption
silently covering nothing, or silently covering more than it said, with the
report looking normal either way.

**How many is not written down here. It is computed** —
`test_the_recorded_baseline_divergence_figure_is_the_measured_one` runs the
frozen 2.1.1 module against this grid and this oracle, and
`BASELINE_DIVERGENCES` has to equal what it finds.

That is not fastidiousness. The figure was asserted from memory twice and was
wrong both times: first 13, measured on a grid that was then replaced; then 29,
re-measured on the *replaced* grid in the same commit that widened it. Two
independent audits caught it, the second one noting that the release narrated
the mistake and committed it again a generation later. A number in prose is not
a measurement, and this module's own thesis is that a hand-written table is how
the first implementation passed.

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

import pathlib
import shutil
import subprocess

import pytest

from pathmatch import matches_any, matching_patterns

PACK_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

#: `(total, under, over)` — the frozen 2.1.1 module against the grid below.
#: **Asserted here and verified by computation**, never the other way round.
#: Under-matching means a declared rule silently covered nothing; over-matching
#: means it silently covered more than it said. Both directions were present.
BASELINE_DIVERGENCES = (131, 114, 17)


# --- individually reproduced divergences, as direct assertions ---------------
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
    """The root cause behind nine of them: the bare-directory branch used `in`,
    so only literal directory names ever matched."""
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


def test_matching_is_case_sensitive_on_windows_and_does_not_discriminate_here():
    """A **portability guard that cannot fail on POSIX**, and saying so is the point.

    The original justification was wrong, and an independent audit caught it:
    `os.path.normcase` is *OS*-dependent, not filesystem-dependent — it is the
    identity on every POSIX platform, including this case-insensitive one. So
    `fnmatch` and `fnmatchcase` answer identically here, this assertion passed
    before the change as well as after, and it could not have come out of the
    differential the module once credited it to. It came from reading the
    documentation.

    The change to `fnmatchcase` is still right: on Windows `normcase`
    lowercases, and a declaration whose meaning depends on the OS reading it is
    not a declaration. The test is kept as a guard for that platform and is
    named as one, rather than left looking like an oracle that constrains
    behaviour where the pack actually runs.
    """
    import fnmatch
    import os.path
    import posixpath

    assert not matches_any("DIST/a.txt", ["dist/"])
    assert not matches_any("a.txt", ["A.txt"])

    if os.path.normcase is posixpath.normcase:
        # Asserted rather than skipped. The *reason* this guard cannot
        # discriminate here is itself a falsifiable claim about the platform, and
        # a skip would make the collected count and the manifest's passing count
        # disagree — a small dishonesty in the file that exists to stop those.
        assert fnmatch.fnmatch("DIST", "dist") == fnmatch.fnmatchcase("DIST", "dist"), (
            "normcase is the identity here, so the two must agree; if they do not, "
            "this guard has become discriminating and the docstring is stale"
        )


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
    # Anchors whose own name also appears in PATTERNS as a trailing `**`.
    # Without these the grid cannot see a trailing-`**` over-match at all,
    # which is how one shipped: an independent differential found it and this
    # one could not.
    "foo", "foo/bar", "foo/bar/baz.txt", "a/foo.tar.gz", "b/a", "b/a/c", "a/d.txt",
    "q/r/u.txt", "fixtures/one.md", "fixtures/real-notes.md", "a b/c.txt", "q.txt",
    "a*b.txt", "aXb.txt", "?.txt", "fix!.txt", "a.txt\t", "b.txt",
]

PATTERNS = [
    "dist/", "dist*/", "annotations/", "annotations", "build*/", "a/b/", "/dist/",
    "*.log", "node_modules/", "*.egg-info/", "logs/*/", "dist/*", "/a.txt",
    "__pycache__/", "*.py", "a/b/c.txt", "**/build/", "logs/**", "**/*.log",
    "a/**/d.txt", "?.txt", "[ab].txt", "src/**/x.py", "dist", "DIST/",
    "notes/*/day.md", "t/**", "**", "*",
    "foo/**", "foo/**/", "**/a/**", "a/**", "a/**/", "annotations/**", "annotations/**/",
    "q/**/u.txt", "*/*/*", "**/**", "a b/", "fixtures/*", "[!a].txt", "*.txt ",
    # Forms an independent differential found and this grid could not see:
    # escapes, `[^…]` negation, and non-space trailing whitespace.
    "[^a].txt", "a\\*b.txt", "\\?.txt", "fix\\!.txt", "*.txt\t", "dist//",
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

    def ignored(rules, paths):
        if isinstance(rules, str):
            rules = [rules]
        (root / ".gitignore").write_text("\n".join(rules) + "\n")
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


# --- negation, and the rule that constrains it --------------------------------
#
# `!` was read as part of a filename, so a negation matched nothing and the
# declaration it expressed was silently overruled. Found by an independent
# audit, which reproduced a suppressed private-term leak end to end.


def test_a_negation_removes_a_path_from_an_exemption():
    declared = ["fixtures/*", "!fixtures/real-notes.md"]
    assert matches_any("fixtures/one.md", declared)
    assert not matches_any("fixtures/real-notes.md", declared)


def test_last_match_wins():
    """Git's rule, and the reason `matches_any` is a loop and not an `any()`."""
    assert not matches_any("a.txt", ["*.txt", "!a.txt"])
    assert matches_any("a.txt", ["*.txt", "!a.txt", "a.txt"])


def test_a_negation_cannot_re_include_under_an_excluded_directory():
    """The subtle half, and the one the first repair got wrong in the permissive
    direction. Git: "it is not possible to re-include a file if a parent
    directory of that file is excluded"."""
    assert matches_any("dist/sub/a.txt", ["dist/", "!dist/sub/a.txt"])
    assert matches_any("dist/a.txt", ["**", "!a.txt"])
    # …and the leaf itself is re-includable when no parent is excluded.
    assert not matches_any("a.txt", ["**", "!a.txt"])


def test_a_negation_that_fires_is_reported_as_engaged_not_as_dead():
    """A declaration that did something must not be reported as one that matched
    nothing — that sends somebody to look for a rule that is working."""
    declared = ["fixtures/*", "!fixtures/real-notes.md"]
    assert matching_patterns("fixtures/real-notes.md", declared) == declared
    assert not matches_any("fixtures/real-notes.md", declared)


def test_an_escaped_bang_is_a_literal_name():
    assert matches_any("!odd.txt", ["\\!odd.txt"])


# --- trailing `**` ------------------------------------------------------------


def test_a_trailing_double_star_matches_everything_inside_not_the_anchor():
    """Git's rule. The first implementation let `**` consume zero components
    everywhere, so `annotations/**` matched `annotations` itself — an
    over-match, which widens an exemption. The shipped grid could not see it
    because no trailing-`**` pattern had its own anchor in the path list; both
    are in the grid now."""
    assert not matches_any("foo", ["foo/**"])
    assert matches_any("foo/bar", ["foo/**"])
    assert matches_any("foo/bar/baz.txt", ["foo/**"])
    assert not matches_any("annotations", ["annotations/**"])
    assert matches_any("annotations/x.md", ["annotations/**"])


def test_an_interior_double_star_still_matches_zero_components():
    """Only the *trailing* case is constrained; `a/**/d.txt` must still match
    `a/d.txt`."""
    assert matches_any("a/d.txt", ["a/**/d.txt"])
    assert matches_any("a/b/c/d.txt", ["a/**/d.txt"])


# --- whitespace ---------------------------------------------------------------


def test_trailing_spaces_are_stripped_from_a_pattern_and_other_whitespace_is_not():
    """Git strips trailing **spaces** only. This test asserted that a trailing
    tab was stripped too — a divergence from the oracle named in its own title,
    and in the over-matching direction. Found by an independent differential."""
    assert matches_any("a.txt", ["*.txt "])
    assert not matches_any("a.txt", ["*.txt\t"])
    assert matches_any("a.txt\t", ["*.txt\t"])


def test_an_escaped_trailing_space_is_kept():
    assert matches_any("odd ", ["odd\\ "])
    assert not matches_any("odd", ["odd\\ "])


# --- the differential, over negation sets -------------------------------------

NEGATION_SETS = [
    ["fixtures/*", "!fixtures/real-notes.md"],
    ["*.log", "!logs/a.log"],
    ["dist/", "!dist/sub/a.txt"],
    ["**", "!a.txt"],
    ["a/**", "!a/b.txt", "a/b.txt"],
    ["*.txt", "!b.txt", "!q.txt"],
    ["annotations/", "!annotations/x.md"],
]


@pytest.mark.parametrize("rules", NEGATION_SETS, ids=lambda r: " ".join(r))
def test_negation_sets_match_git_check_ignore(oracle, rules):
    truth = oracle(rules, PATHS)
    mine = {path for path in PATHS if matches_any(path, rules)}
    assert not (truth - mine), f"{rules} under-matches: {sorted(truth - mine)}"
    assert not (mine - truth), f"{rules} over-matches: {sorted(mine - truth)}"


# --- the figure, computed rather than remembered -------------------------------


def test_the_recorded_baseline_divergence_figure_is_the_measured_one(oracle):
    """`BASELINE_DIVERGENCES` against the frozen 2.1.1 module and this grid.

    The one test that would have prevented two blockers. It fails if the grid
    changes and the number does not, which is exactly how both wrong figures
    were produced.
    """
    import importlib.util
    import subprocess
    import tempfile

    baseline = subprocess.run(
        ["git", "show", "4495e61850c08027e47eac6d0db84b4b3380e300:tools/pathmatch.py"],
        cwd=str(PACK_ROOT), capture_output=True, check=True,
    ).stdout.decode("utf-8")

    with tempfile.TemporaryDirectory() as scratch:
        module_path = pathlib.Path(scratch) / "baseline_pathmatch.py"
        module_path.write_text(baseline, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("baseline_pathmatch", module_path)
        frozen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(frozen)

        under = over = 0
        for pattern in PATTERNS:
            truth = oracle(pattern, PATHS)
            for path in PATHS:
                expected, actual = path in truth, frozen.matches_any(path, [pattern])
                under += expected and not actual
                over += actual and not expected

    assert (under + over, under, over) == BASELINE_DIVERGENCES, (
        f"the grid measures {under + over} divergences ({under} under, {over} over); "
        f"BASELINE_DIVERGENCES records {BASELINE_DIVERGENCES}. The grid and the figure "
        "must be changed together"
    )


def test_the_repaired_module_has_no_divergences_on_the_same_grid(oracle):
    """The other half: whatever the baseline figure is, the repair drives it to
    zero on the identical grid and oracle."""
    divergent = []
    for pattern in PATTERNS:
        truth = oracle(pattern, PATHS)
        for path in PATHS:
            if (path in truth) != matches_any(path, [pattern]):
                divergent.append((pattern, path))
    assert not divergent, divergent


def test_the_grid_is_the_size_the_documents_quote():
    #: The grid must stay large enough to be worth the name. The *figure* is
    #: bound by `test_the_recorded_baseline_divergence_figure_is_the_measured_one`,
    #: which fails whenever the grid changes and the number does not — which is
    #: exactly what happened when this grid was last widened.
    assert len(PATTERNS) * len(PATHS) >= 2000


# --- escapes and character classes ---------------------------------------------
#
# `fnmatch` has neither git's backslash escapes nor its `[^…]` negation, so a
# pattern using either was silently dead or silently over-matching. Both
# pre-existing at 2.1.1, both found by an independent differential rather than
# by reading the code.


@pytest.mark.parametrize(
    "pattern, path, expected",
    [
        ("a\\*b.txt", "a*b.txt", True),      # an escaped star is a literal star
        ("a\\*b.txt", "aXb.txt", False),
        ("\\?.txt", "?.txt", True),
        ("\\?.txt", "a.txt", False),
        ("\\[a\\].txt", "[a].txt", True),
        ("fix\\!.txt", "fix!.txt", True),
        ("a\\ b", "a b", True),
    ],
)
def test_a_backslash_escapes_a_wildcard(pattern, path, expected):
    assert matches_any(path, [pattern]) is expected


@pytest.mark.parametrize(
    "pattern, path, expected",
    [
        ("[^a].txt", "a.txt", False),   # git reads `^` as a negator
        ("[^a].txt", "b.txt", True),
        ("[!a].txt", "a.txt", False),   # …and `!` as the same thing
        ("[!a].txt", "b.txt", True),
        ("[ab].txt", "a.txt", True),
        ("[ab].txt", "c.txt", False),
    ],
)
def test_a_character_class_negates_with_either_marker(pattern, path, expected):
    assert matches_any(path, [pattern]) is expected


def test_a_doubled_separator_matches_nothing_as_git_treats_it():
    assert not matches_any("dist/a.txt", ["dist//"])
    assert matches_any("dist/a.txt", ["dist/"])
