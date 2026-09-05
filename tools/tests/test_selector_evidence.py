"""A command that exits cleanly having run nothing is not evidence.

The measured case, from this release's own session: a targeted run exited in
0.56 seconds and was nearly read as a forty-five-fold speed-up over the same
guard's 25.7 seconds. It had selected zero tests, because the selector said
`never_prints` and the test is called `ever_prints`.
"""

from dataclasses import replace

import pytest

import selector_evidence as se
from selector_evidence import EVIDENCE, NOT_EVIDENCE, SelectorRun


def _summary(text, *, selector="s", exit_status=0):
    return se.read_summary(text, selector=selector, exit_status=exit_status)


# --- O8: zero executed is NOT_EVIDENCE, however the command exited -----------


@pytest.mark.parametrize("exit_status", [0, 1, 5])
def test_zero_executed_is_not_evidence_whatever_the_exit_status(exit_status):
    run = _summary("70 deselected in 0.01s", exit_status=exit_status)
    assert run.executed == 0
    assert run.verdict() == NOT_EVIDENCE
    assert se.problems(run), "a run that executed nothing was accepted as evidence"


def test_the_real_typo_from_this_session_is_not_evidence():
    """The literal shape that nearly became a performance claim."""
    run = _summary("70 deselected in 0.01s",
                   selector='tools/tests/test_release_integrity.py -k never_prints_a_traceback')
    assert run.verdict() == NOT_EVIDENCE
    assert any("does not name what it meant to" in problem for problem in se.problems(run))


def test_a_selector_that_ran_something_is_evidence():
    run = _summary("1 passed, 69 deselected in 6.97s")
    assert run.executed == 1 and run.deselected == 69 and run.collected == 70
    assert run.verdict() == EVIDENCE
    assert se.problems(run) == ()


def test_zero_is_distinguished_from_unreadable():
    """`nothing ran` and `what ran is unknown` are different claims, and the
    second must never be rendered as the first."""
    unreadable = _summary("some output pytest never printed a summary for")
    assert unreadable.unreadable
    assert unreadable.verdict() == NOT_EVIDENCE
    assert any("which is not the same as nothing" in p for p in se.problems(unreadable))


def test_every_selected_test_being_skipped_is_not_evidence():
    """A skipped test is a test that did not run. This is the shape where the
    selector was RIGHT and still nothing happened."""
    run = _summary("3 skipped in 0.02s")
    assert run.collected == 3 and run.executed == 0 and run.skipped == 3
    assert run.verdict() == NOT_EVIDENCE
    assert any("3 skipped" in problem for problem in se.problems(run))


def test_an_expectation_of_more_than_one_is_the_callers_claim():
    """The threshold is an argument, never read back out of the result — a
    threshold derived from the thing it checks cannot fail."""
    run = _summary("2 passed in 1.0s")
    assert run.verdict(expect_at_least=2) == EVIDENCE
    assert run.verdict(expect_at_least=3) == NOT_EVIDENCE
    assert "at least 3 was expected" in se.problems(run, expect_at_least=3)[0]


def test_a_failing_run_still_counts_as_having_executed():
    """Evidence is about whether the check RAN, not about whether it passed."""
    run = _summary("1 failed, 2 passed in 1.0s", exit_status=1)
    assert run.executed == 3
    assert run.verdict() == EVIDENCE


# --- O9: a comparison needs one population ----------------------------------


def test_a_faster_run_over_fewer_tests_is_refused_as_a_comparison():
    """The claim this session nearly made."""
    before = _summary("1 passed, 69 deselected in 25.70s")
    after = _summary("70 deselected in 0.56s", exit_status=5)
    problems = se.comparison_problems(before, after)
    assert problems
    assert any("a faster run over fewer tests is not a faster run" in p for p in problems)


def test_a_comparison_over_one_population_is_allowed():
    """And it needs the IDENTITIES, not only the counts — two different single
    tests both report `1 passed`, which an independent reader demonstrated with
    two real runs."""
    same = ("m.py::test_one",)
    before = replace(_summary("1 passed, 69 deselected in 25.70s"), identities=same)
    after = replace(_summary("1 passed, 69 deselected in 6.90s"), identities=same)
    assert se.comparison_problems(before, after) == ()


def test_a_comparison_without_identities_is_refused():
    before = _summary("1 passed, 69 deselected in 25.70s")
    after = _summary("1 passed, 69 deselected in 6.90s")
    assert any("did not record which tests" in problem
               for problem in se.comparison_problems(before, after))


def test_two_different_single_tests_do_not_compare_equal():
    """The exact shape counts cannot catch."""
    before = replace(_summary("1 passed in 1.0s"), identities=("m.py::test_one",))
    after = replace(_summary("1 passed in 1.0s"), identities=("m.py::test_two",))
    problems = se.comparison_problems(before, after)
    assert any("DIFFERENT tests, not merely the same number" in p for p in problems)


def test_a_comparison_is_refused_when_the_population_grew_too():
    """Both directions: an optimization that runs MORE is also not the same
    measurement."""
    before = _summary("10 passed in 1.0s")
    after = _summary("12 passed in 1.0s")
    assert any("different numbers of tests" in p for p in se.comparison_problems(before, after))


# --- against the real suite, not only against strings ------------------------


def test_the_tool_answers_correctly_against_a_real_pytest_run(tmp_path):
    """Strings are cheap; this runs pytest."""
    module = tmp_path / "test_sample.py"
    module.write_text("def test_one():\n    assert True\n\n\ndef test_two():\n    assert True\n",
                      encoding="utf-8")
    # `record_identities=False`: these assert counts, not populations, and the
    # identity pass is a second pytest spawn this test has no use for.
    real = se.run_selector([str(module), "-k", "one"], record_identities=False)
    assert real.executed == 1 and real.deselected == 1
    assert real.verdict() == EVIDENCE

    typo = se.run_selector([str(module), "-k", "a_name_no_test_carries"],
                           record_identities=False)
    assert typo.executed == 0
    assert typo.verdict() == NOT_EVIDENCE


def test_an_empty_parametrisation_executes_nothing_and_is_caught(tmp_path):
    """The shape a parametrised test degrades into when its case list empties."""
    module = tmp_path / "test_empty_param.py"
    module.write_text(
        "import pytest\n\n\n@pytest.mark.parametrize('case', [])\n"
        "def test_nothing(case):\n    assert False\n", encoding="utf-8")
    run = se.run_selector([str(module)], record_identities=False)
    assert run.executed == 0
    assert run.verdict() == NOT_EVIDENCE


# --- collection is a weaker claim, and says so -------------------------------


@pytest.mark.parametrize("text", ["no tests collected in 0.01s", "collected 0 items"])
def test_a_collection_that_names_nothing_is_not_evidence(text):
    """And it says ZERO, not `unknown`.

    Both answers are NOT_EVIDENCE, so a test asserting only the verdict passes
    against an implementation that confuses them — which a mutant proved. The
    two are different claims: *nothing was named* is a measurement, *what was
    named is unknown* is a gap, and the pack refuses to render the second as the
    first anywhere else.
    """
    run = se.read_collection(text, selector="s")
    assert run.verdict() == NOT_EVIDENCE
    assert not run.unreadable, "a readable zero was reported as unknown"
    assert run.executed == 0 and run.collected == 0
    assert any("0 test(s) executed" in problem for problem in se.problems(run))


def test_a_collection_reports_what_the_selector_names():
    run = se.read_collection("63 tests collected in 0.02s", selector="s")
    assert run.executed == 63 and run.collected == 63
    assert run.verdict() == EVIDENCE

    narrowed = se.read_collection("1/70 tests collected (69 deselected) in 0.05s", selector="s")
    assert narrowed.executed == 1 and narrowed.deselected == 69 and narrowed.collected == 70
    assert narrowed.verdict() == EVIDENCE


def test_an_unreadable_collection_is_not_zero():
    run = se.read_collection("something else entirely", selector="s")
    assert run.unreadable and run.verdict() == NOT_EVIDENCE


def test_collect_only_against_a_real_selector(tmp_path):
    # DISTINCTIVE NAMES. `-k` matches an item's parents too, and pytest's tmp
    # directory name contains most short letters — so `-k "a"` selected both
    # tests through the PATH, and the fixture was measuring a coincidence.
    module = tmp_path / "test_c.py"
    module.write_text("def test_zzalpha():\n    pass\n\n\ndef test_zzbeta():\n    pass\n",
                      encoding="utf-8")
    named = se.run_selector([str(module), "-k", "zzalpha"], collect_only=True)
    assert named.executed == 1, named.identities
    assert named.verdict() == EVIDENCE
    missing = se.run_selector([str(module), "-k", "zznosuchname"], collect_only=True)
    assert missing.executed == 0 and missing.verdict() == NOT_EVIDENCE


# --- an outcome is not a test body that ran ----------------------------------


@pytest.mark.parametrize("summary,exit_status", [
    ("1 xfailed in 0.04s", 0),
    ("1 error in 0.04s", 1),
    ("2 errors in 0.04s", 1),
    ("1 xfailed, 1 error in 0.1s", 1),
])
def test_zero_a_selected_test_whose_body_never_ran_is_not_evidence(summary, exit_status):
    """Two shapes an independent reader found inside real pytest runs.

    `xfail(run=False)` does not run the body and the command exits 0. An `error`
    is a failure in SETUP, so the body was never reached. Both were counted as
    execution, and both exit as though something happened.
    """
    run = _summary(summary, exit_status=exit_status)
    assert run.executed == 0
    assert run.not_reached >= 1
    assert run.verdict() == NOT_EVIDENCE
    assert any("never reached" in problem for problem in se.problems(run))


def test_a_test_that_failed_in_its_body_did_run():
    """The bound: `failed` is a body that ran and disagreed. Evidence is about
    whether the check RAN."""
    run = _summary("1 failed in 0.1s", exit_status=1)
    assert run.executed == 1 and run.not_reached == 0
    assert run.verdict() == EVIDENCE


# --- the floor is not the caller's to remove ---------------------------------


@pytest.mark.parametrize("expectation", [0, -1, -100])
def test_zero_the_caller_cannot_set_the_floor_below_one(expectation):
    """`expect_at_least=0` made every zero-execution run evidence — the argument
    meant to strengthen the guarantee could switch it off, and the shipped CLI
    exposed it to any caller."""
    run = _summary("63 deselected in 0.1s", exit_status=5)
    assert run.verdict(expect_at_least=expectation) == NOT_EVIDENCE
    assert any("the floor is one" in problem
               for problem in se.problems(run, expect_at_least=expectation))


def test_the_caller_may_still_raise_the_floor():
    run = _summary("2 passed in 1.0s")
    assert run.verdict(expect_at_least=2) == EVIDENCE
    assert run.verdict(expect_at_least=3) == NOT_EVIDENCE


def test_zero_the_command_line_cannot_set_the_floor_below_one(tmp_path):
    """Through the shipped entry point, which is where a caller reaches it."""
    import subprocess
    import sys
    from pathlib import Path

    module = tmp_path / "test_e.py"
    module.write_text("def test_zzsomething():\n    pass\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(Path(se.__file__)), "--expect-at-least", "0", "--",
         str(module), "-k", "zznosuchname"],
        capture_output=True, text=True, timeout=300)
    assert "NOT_EVIDENCE" in result.stdout, result.stdout
    assert result.returncode != 0, "the CLI reported a zero-execution run as success"


# --- the collection summary is the last lines, not the whole output ----------


def test_a_collected_node_id_cannot_be_mistaken_for_an_empty_collection():
    """Searching the whole output meant a COLLECTED TEST NAME containing the
    words `no tests collected` reported the run as empty — and this module's own
    parametrised names contain them. Found by pointing the tool at its own tests.
    """
    output = (
        "tools/tests/test_selector_evidence.py::test_a_collection_that_names_nothing"
        "[no tests collected in 0.01s]\n"
        "tools/tests/test_selector_evidence.py::test_another\n"
        "\n"
        "2 tests collected in 0.02s\n"
    )
    run = se.read_collection(output, selector="s")
    assert run.executed == 2, "a collected node id was read as an empty collection"
    assert run.verdict() == EVIDENCE


def test_a_genuinely_empty_collection_is_still_empty():
    """The bound in the other direction."""
    run = se.read_collection("no tests collected in 0.01s", selector="s")
    assert run.executed == 0 and run.verdict() == NOT_EVIDENCE
    assert not run.unreadable
