"""The hung run, the healthy one that looks like it, and the waiters that hung.

The three fixtures are the measured pair plus the waiter quorum. The second is
the one that protects work: a detector that fails it kills recoverable workers,
and it was measured four minutes after the stall rule was written.
"""

import pytest

import progress
from errors import IntegrityError, PreconditionError
from progress import ProgressState, Sample, SignalKind, Waiter


def _sample(at, **signals):
    return Sample(at_seconds=at, signals=signals)


# --- the measured pair ------------------------------------------------------------


def test_a_run_that_existed_for_thirty_one_minutes_and_did_nothing_is_stalled():
    """30m50s elapsed, 0.05s of processor time, zero log bytes, no rollout."""
    report = progress.classify(
        "hung",
        _sample(0, cpu_seconds=0.05, log_bytes=0, provider_rollout=0),
        _sample(1850, cpu_seconds=0.05, log_bytes=0, provider_rollout=0),
        horizon_seconds=900,
    )
    assert report.state == ProgressState.STALLED
    assert set(report.flat) == {"cpu_seconds", "log_bytes", "provider_rollout"}


def test_a_healthy_run_silent_on_its_log_is_not_stalled():
    """The measurement that makes the disjunction a safety property rather than
    a completeness one: over four minutes with no log output while processor
    time climbed 3.81 -> 4.05 -> 4.14. A detector reading the log alone calls
    this stalled, and the action a stall invites destroys work."""
    report = progress.classify(
        "healthy",
        _sample(0, cpu_seconds=3.81, log_bytes=22452),
        _sample(260, cpu_seconds=4.14, log_bytes=22452),
        horizon_seconds=120,
    )
    assert report.state == ProgressState.RUNNING
    assert report.advanced == ("cpu_seconds",)
    assert "log_bytes" in report.flat


def test_any_single_advancing_signal_is_enough_however_many_are_flat():
    """The disjunction, asserted directly rather than only through the fixture
    above — a rule that happened to hold for one pair is not a rule."""
    for advancing in SignalKind.ALL:
        signals_before = {kind: 1.0 for kind in SignalKind.ALL}
        signals_after = dict(signals_before)
        signals_after[advancing] = 2.0
        report = progress.classify(
            "one-mover", Sample(0, signals_before), Sample(10_000, signals_after),
            horizon_seconds=1,
        )
        assert report.state == ProgressState.RUNNING, advancing
        assert report.advanced == (advancing,)


# --- the refusal that keeps the mirror error out ------------------------------------


def test_one_flat_signal_is_never_a_stall_however_long_it_stays_flat():
    """`UNKNOWN`, and it is the correct answer: a single flat signal is the
    measured false positive rather than evidence."""
    report = progress.classify(
        "log-only", _sample(0, log_bytes=100), _sample(100_000, log_bytes=100),
        horizon_seconds=1,
    )
    assert report.state == ProgressState.UNKNOWN
    assert "single flat signal" in report.why
    assert "observe a second kind" in report.why


def test_two_agreeing_flat_signals_past_the_horizon_are_a_stall():
    """The other side of the same rule. If two were also unknown the classifier
    could never say anything, which is a different way of being useless."""
    report = progress.classify(
        "two-flat", _sample(0, log_bytes=1, cpu_seconds=1),
        _sample(1000, log_bytes=1, cpu_seconds=1), horizon_seconds=100,
    )
    assert report.state == ProgressState.STALLED


def test_flat_inside_the_horizon_is_still_running():
    report = progress.classify(
        "young", _sample(0, log_bytes=1, cpu_seconds=1),
        _sample(30, log_bytes=1, cpu_seconds=1), horizon_seconds=900,
    )
    assert report.state == ProgressState.RUNNING
    assert "not yet stalled" in report.why


def test_signals_observed_in_only_one_sample_are_named_and_never_called_flat():
    """Present in one reading and absent from the other is not evidence either
    way. A report that listed it as `flat` would be claiming an observation
    nobody made — the instrument stopped reporting, which is a fact about the
    instrument and not about the run.

    Asserted against `flat` and not only against the verdict: the verdict here
    is `UNKNOWN` for a different reason (one comparable signal), so a test that
    checked only the verdict would pass while the report lied."""
    report = progress.classify(
        "partial", _sample(0, log_bytes=1, cpu_seconds=1),
        _sample(1000, log_bytes=1), horizon_seconds=100,
    )
    assert report.incomparable == ("cpu_seconds",)
    assert "cpu_seconds" not in report.flat and "cpu_seconds" not in report.advanced
    assert report.state == ProgressState.UNKNOWN


def test_a_stall_report_never_claims_an_uncompared_signal_was_flat():
    """The same rule where it actually reaches a verdict. Two comparable
    signals are flat past the horizon, so this is a stall — and the third,
    which only one sample carried, must not be counted among the agreeing
    signals that produced it."""
    report = progress.classify(
        "three-signals",
        _sample(0, log_bytes=1, cpu_seconds=1, provider_rollout=5),
        _sample(1000, log_bytes=1, cpu_seconds=1),
        horizon_seconds=100,
    )
    assert report.state == ProgressState.STALLED
    assert set(report.flat) == {"log_bytes", "cpu_seconds"}
    assert report.incomparable == ("provider_rollout",)
    rendered = report.render()
    flat_line = next(line for line in rendered.splitlines() if line.strip().startswith("flat:"))
    assert "provider_rollout" not in flat_line


def test_nothing_observed_in_both_samples_is_unknown_rather_than_stalled():
    report = progress.classify("blind", _sample(0), _sample(9999), horizon_seconds=1)
    assert report.state == ProgressState.UNKNOWN
    assert "read nothing is not a result" in report.why


def test_a_finished_run_is_complete_whatever_its_signals_did():
    report = progress.classify(
        "done", _sample(0, log_bytes=1, cpu_seconds=1),
        _sample(9999, log_bytes=1, cpu_seconds=1), horizon_seconds=1, finished=True,
    )
    assert report.state == ProgressState.COMPLETE


# --- the horizon is the caller's, and the report says so -----------------------------


def test_a_horizon_nobody_declared_is_refused_rather_than_defaulted():
    """A built-in number would be wrong exactly where it mattered, because how
    long is too long depends on the task class and the backend."""
    for bad in (0, -1, None, "600"):
        with pytest.raises(PreconditionError):
            progress.classify("r", _sample(0, log_bytes=1, cpu_seconds=1),
                              _sample(1, log_bytes=1, cpu_seconds=1), horizon_seconds=bad)


def test_the_report_states_the_horizon_it_was_measured_against():
    report = progress.classify(
        "r", _sample(0, log_bytes=1, cpu_seconds=1), _sample(1000, log_bytes=1, cpu_seconds=1),
        horizon_seconds=333,
    )
    assert "333" in report.render()


def test_a_stall_says_in_its_own_output_that_it_is_not_an_instruction():
    """Ending a worker is the only destructive act in this area, its false
    positive is measured, and it sits on a numbered human row."""
    report = progress.classify(
        "r", _sample(0, log_bytes=1, cpu_seconds=1), _sample(1000, log_bytes=1, cpu_seconds=1),
        horizon_seconds=10,
    )
    assert "row 4" in report.render()
    assert "not an instruction" in report.render()


def test_a_signal_this_module_does_not_know_is_refused():
    with pytest.raises(IntegrityError):
        Sample(0, {"vibes": 1})
    with pytest.raises(IntegrityError):
        Sample(0, {"log_bytes": -1})


def test_a_later_sample_that_is_earlier_is_refused():
    with pytest.raises(IntegrityError):
        progress.classify("r", _sample(100, log_bytes=1), _sample(0, log_bytes=1),
                          horizon_seconds=10)


# --- waiters ---------------------------------------------------------------------------


def test_a_waiter_whose_own_command_matches_its_own_pattern_is_refused_at_construction():
    """Three such waiters on one worker formed a quorum that could never
    terminate and fired four times after the job had exited. Observing that
    later is too late to be useful, so it is refused where it is written."""
    with pytest.raises(PreconditionError) as caught:
        Waiter(waiter_id="w1", run_id="job-1",
               own_command="bash -c 'until ! pgrep -f codex-exec; do sleep 5; done'",
               match_pattern="codex-exec")
    assert "quorum" in caught.value.render()


def test_a_waiter_on_a_registered_run_needs_no_pattern_at_all():
    """A run is a registered handle. A pattern matches whatever happens to look
    like it, which is the whole mechanism above."""
    waiter = Waiter(waiter_id="w1", run_id="job-1")
    assert waiter.match_pattern == ""
    assert not waiter.retired


def test_a_pattern_that_does_not_match_the_waiter_is_allowed():
    """The guard must not refuse correct work: a pattern is discouraged, not
    forbidden."""
    assert Waiter(waiter_id="w1", run_id="job-1", own_command="python3 wait.py",
                  match_pattern="the-real-worker").match_pattern == "the-real-worker"


def test_a_pattern_that_is_not_a_regex_is_refused():
    with pytest.raises(IntegrityError):
        Waiter(waiter_id="w1", run_id="job-1", match_pattern="unbalanced(")


def test_every_waiter_on_a_finished_run_retires_at_once():
    """One worker, three coordinator-owned waiters. Completion retires all of
    them; a late fire is otherwise readable as current state."""
    waiters = [Waiter(waiter_id=f"w{n}", run_id="job-1") for n in range(3)]
    waiters.append(Waiter(waiter_id="w-other", run_id="job-2"))

    retired = progress.retire_waiters(waiters, finished_runs=["job-1"])

    assert [w.retired for w in retired] == [True, True, True, False]


def test_retirement_happens_on_any_terminal_state_not_only_on_success():
    """A waiter that exits cleanly on success and hangs on failure is armed
    precisely when something has gone wrong."""
    waiters = [Waiter(waiter_id="w", run_id="failed-job")]
    assert progress.retire_waiters(waiters, finished_runs=["failed-job"])[0].retired


def test_retiring_is_idempotent_and_leaves_an_already_retired_waiter_alone():
    waiters = [Waiter(waiter_id="w", run_id="job", retired=True)]
    assert progress.retire_waiters(waiters, finished_runs=[])[0].retired


# --- the command line -----------------------------------------------------------------


def test_the_cli_exit_status_separates_stalled_from_unknown(capsys):
    stalled = progress._cli(["r", "--horizon", "10", "--earlier", "0", "log_bytes=1",
                             "cpu_seconds=1", "--later", "100", "log_bytes=1", "cpu_seconds=1"])
    assert stalled == 1 and ProgressState.STALLED in capsys.readouterr().out

    unknown = progress._cli(["r", "--horizon", "10", "--earlier", "0", "log_bytes=1",
                             "--later", "100", "log_bytes=1"])
    assert unknown == 2 and ProgressState.UNKNOWN in capsys.readouterr().out

    running = progress._cli(["r", "--horizon", "10", "--earlier", "0", "log_bytes=1",
                             "cpu_seconds=1", "--later", "100", "log_bytes=1", "cpu_seconds=9"])
    assert running == 0 and ProgressState.RUNNING in capsys.readouterr().out
