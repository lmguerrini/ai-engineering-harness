"""A command that exits cleanly having run nothing is not evidence.

The measured case, from this release's own session: a targeted run exited in
0.56 seconds and was nearly read as a forty-five-fold speed-up over the same
guard's 25.7 seconds. It had selected zero tests, because the selector said
`never_prints` and the test is called `ever_prints`.
"""

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
    before = _summary("1 passed, 69 deselected in 25.70s")
    after = _summary("1 passed, 69 deselected in 6.90s")
    assert se.comparison_problems(before, after) == ()


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
    real = se.run_selector([str(module), "-k", "one"])
    assert real.executed == 1 and real.deselected == 1
    assert real.verdict() == EVIDENCE

    typo = se.run_selector([str(module), "-k", "a_name_no_test_carries"])
    assert typo.executed == 0
    assert typo.verdict() == NOT_EVIDENCE


def test_an_empty_parametrisation_executes_nothing_and_is_caught(tmp_path):
    """The shape a parametrised test degrades into when its case list empties."""
    module = tmp_path / "test_empty_param.py"
    module.write_text(
        "import pytest\n\n\n@pytest.mark.parametrize('case', [])\n"
        "def test_nothing(case):\n    assert False\n", encoding="utf-8")
    run = se.run_selector([str(module)])
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
    module = tmp_path / "test_c.py"
    module.write_text("def test_a():\n    pass\n\n\ndef test_b():\n    pass\n", encoding="utf-8")
    named = se.run_selector([str(module), "-k", "a"], collect_only=True)
    assert named.executed == 1 and named.verdict() == EVIDENCE
    missing = se.run_selector([str(module), "-k", "no_such_name"], collect_only=True)
    assert missing.executed == 0 and missing.verdict() == NOT_EVIDENCE
