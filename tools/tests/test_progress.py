"""The hung run, the healthy one that looks like it, and the waiters that hung.

The three fixtures are the measured pair plus the waiter quorum. The second is
the one that protects work: a detector that fails it kills recoverable workers,
and it was measured four minutes after the stall rule was written.
"""

import pathlib

import sys
import tempfile
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
        horizon_seconds=900, flat_since_seconds=0,
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
        horizon_seconds=120, flat_since_seconds=0,
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
            horizon_seconds=1, flat_since_seconds=0,
        )
        assert report.state == ProgressState.RUNNING, advancing
        assert report.advanced == (advancing,)


# --- the refusal that keeps the mirror error out ------------------------------------


def test_one_flat_signal_is_never_a_stall_however_long_it_stays_flat():
    """`UNKNOWN`, and it is the correct answer: a single flat signal is the
    measured false positive rather than evidence."""
    report = progress.classify(
        "log-only", _sample(0, log_bytes=100), _sample(100_000, log_bytes=100),
        horizon_seconds=1, flat_since_seconds=0,
    )
    assert report.state == ProgressState.UNKNOWN
    assert "single flat signal" in report.why
    assert "observe a second kind" in report.why


def test_two_agreeing_flat_signals_past_the_horizon_are_a_stall():
    """The other side of the same rule. If two were also unknown the classifier
    could never say anything, which is a different way of being useless."""
    report = progress.classify(
        "two-flat", _sample(0, log_bytes=1, cpu_seconds=1),
        _sample(1000, log_bytes=1, cpu_seconds=1), horizon_seconds=100, flat_since_seconds=0,
    )
    assert report.state == ProgressState.STALLED


def test_flat_inside_the_horizon_is_still_running():
    report = progress.classify(
        "young", _sample(0, log_bytes=1, cpu_seconds=1),
        _sample(30, log_bytes=1, cpu_seconds=1), horizon_seconds=900, flat_since_seconds=0,
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
        _sample(1000, log_bytes=1), horizon_seconds=100, flat_since_seconds=0,
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
        horizon_seconds=100, flat_since_seconds=0,
    )
    assert report.state == ProgressState.STALLED
    assert set(report.flat) == {"log_bytes", "cpu_seconds"}
    assert report.incomparable == ("provider_rollout",)
    rendered = report.render()
    flat_line = next(line for line in rendered.splitlines() if line.strip().startswith("flat:"))
    assert "provider_rollout" not in flat_line


def test_nothing_observed_in_both_samples_is_unknown_rather_than_stalled():
    report = progress.classify("blind", _sample(0), _sample(9999), horizon_seconds=1,
                              flat_since_seconds=0)
    assert report.state == ProgressState.UNKNOWN
    assert "read nothing is not a result" in report.why


def test_a_finished_run_is_complete_whatever_its_signals_did():
    report = progress.classify(
        "done", _sample(0, log_bytes=1, cpu_seconds=1),
        _sample(9999, log_bytes=1, cpu_seconds=1), horizon_seconds=1, flat_since_seconds=0,
        finished=True,
    )
    assert report.state == ProgressState.COMPLETE


# --- the horizon is the caller's, and the report says so -----------------------------


def test_a_horizon_nobody_declared_is_refused_rather_than_defaulted():
    """A built-in number would be wrong exactly where it mattered, because how
    long is too long depends on the task class and the backend."""
    for bad in (0, -1, None, "600"):
        with pytest.raises(PreconditionError):
            progress.classify("r", _sample(0, log_bytes=1, cpu_seconds=1),
                              _sample(1, log_bytes=1, cpu_seconds=1), horizon_seconds=bad, flat_since_seconds=0)


def test_the_report_states_the_horizon_it_was_measured_against():
    report = progress.classify(
        "r", _sample(0, log_bytes=1, cpu_seconds=1), _sample(1000, log_bytes=1, cpu_seconds=1),
        horizon_seconds=333, flat_since_seconds=0,
    )
    assert "333" in report.render()


def test_a_stall_says_in_its_own_output_that_it_is_not_an_instruction():
    """Ending a worker is the only destructive act in this area, its false
    positive is measured, and it sits on a numbered human row."""
    report = progress.classify(
        "r", _sample(0, log_bytes=1, cpu_seconds=1), _sample(1000, log_bytes=1, cpu_seconds=1),
        horizon_seconds=10, flat_since_seconds=0,
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
                          horizon_seconds=10, flat_since_seconds=0)


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
    stalled = progress._cli(["r", "--horizon", "10", "--flat-since", "0",
                             "--earlier", "0", "log_bytes=1",
                             "cpu_seconds=1", "--later", "100", "log_bytes=1", "cpu_seconds=1"])
    assert stalled == 1 and ProgressState.STALLED in capsys.readouterr().out

    unknown = progress._cli(["r", "--horizon", "10", "--flat-since", "0",
                             "--earlier", "0", "log_bytes=1",
                             "--later", "100", "log_bytes=1"])
    assert unknown == 2 and ProgressState.UNKNOWN in capsys.readouterr().out

    running = progress._cli(["r", "--horizon", "10", "--flat-since", "0",
                             "--earlier", "0", "log_bytes=1",
                             "cpu_seconds=1", "--later", "100", "log_bytes=1", "cpu_seconds=9"])
    assert running == 0 and ProgressState.RUNNING in capsys.readouterr().out


# --- a reading that is not a reading -------------------------------------------


def test_a_non_finite_signal_is_refused_rather_than_producing_a_stall_with_no_flat_signals():
    """Two NaN readings produced `STALLED` with **zero** flat signals named in
    its own report — a verdict with nothing behind it. Found by a cross-vendor
    auditor, and the same root cause as the capacity gate's."""
    import math

    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(IntegrityError) as caught:
            Sample(0, {"log_bytes": bad})
        assert "neither flat nor advancing" in caught.value.render()


def test_a_monotonic_signal_that_went_backwards_is_a_broken_instrument_not_a_quiet_run():
    """Every signal here is documented monotonic. Folding a decrease into
    "flat" tells a reader the run was quiet when the truth is that the
    measurement cannot be trusted."""
    report = progress.classify(
        "rotated", _sample(0, log_bytes=22000, cpu_seconds=4.0),
        _sample(9999, log_bytes=12, cpu_seconds=4.0), horizon_seconds=1, flat_since_seconds=0,
    )
    assert report.state == ProgressState.UNKNOWN
    assert report.regressed == ("log_bytes",)
    assert "log_bytes" not in report.flat
    assert "went backwards" in report.render()


# --- the horizon is about the run, not about the sampling interval --------------
#
# THE LIVE INCIDENT. A dispatched auditor sat for 5h39m with 0.34 seconds of
# processor time, no output bytes and no provider rollout, while the coordinator
# waited. Sampled 90 seconds apart against a 900-second horizon, this module
# returned RUNNING — because 90 is less than 900. The instrument built to detect
# that incident did not detect that incident.


def test_the_live_incident_is_classified_stalled(tmp_path):
    """Reproduced from the durable evidence: three flat signals, a run that has
    been without progress for five hours and thirty-nine minutes, sampled ninety
    seconds apart."""
    report = progress.classify(
        "rp23-delta-audit",
        _sample(20393.0, log_bytes=39.0, cpu_seconds=0.43, provider_rollout=0.0),
        _sample(20483.0, log_bytes=39.0, cpu_seconds=0.43, provider_rollout=0.0),
        horizon_seconds=900, flat_since_seconds=0.0,
    )
    assert report.state == ProgressState.STALLED
    assert report.flat_for_seconds == 20483.0
    assert "20483s" in report.render() and "900s" in report.render()


def test_a_short_sampling_interval_cannot_hide_a_long_stall():
    """The general form. Whatever gap the caller samples at, the verdict is
    about the run — otherwise a poller can never see a stall at all."""
    for gap in (1, 5, 30, 90, 300):
        report = progress.classify(
            "poller", _sample(100000.0, log_bytes=1, cpu_seconds=1),
            _sample(100000.0 + gap, log_bytes=1, cpu_seconds=1),
            horizon_seconds=900, flat_since_seconds=0.0,
        )
        assert report.state == ProgressState.STALLED, gap


def test_the_report_states_both_durations_so_the_old_misuse_would_be_visible():
    """A caller with only two samples passes the earlier one's time, which
    reproduces the old arithmetic — and the report then says "flat for 90s", so
    a reader can see the claim is about ninety seconds rather than the run."""
    report = progress.classify(
        "narrow", _sample(20393.0, log_bytes=1, cpu_seconds=1),
        _sample(20483.0, log_bytes=1, cpu_seconds=1),
        horizon_seconds=900, flat_since_seconds=20393.0,
    )
    assert report.state == ProgressState.RUNNING
    assert "flat for 90s" in report.render()
    assert "90s between the two readings" in report.render()


def test_the_moment_the_run_last_advanced_is_required_and_has_no_default():
    with pytest.raises(TypeError):
        progress.classify("r", _sample(0, log_bytes=1, cpu_seconds=1),
                          _sample(1, log_bytes=1, cpu_seconds=1), horizon_seconds=10)
    for bad in (None, "0", float("nan")):
        with pytest.raises((PreconditionError, IntegrityError)):
            progress.classify("r", _sample(0, log_bytes=1, cpu_seconds=1),
                              _sample(1, log_bytes=1, cpu_seconds=1),
                              horizon_seconds=10, flat_since_seconds=bad)


def test_a_run_recorded_as_advancing_after_it_was_observed_is_refused():
    with pytest.raises(IntegrityError):
        progress.classify("r", _sample(0, log_bytes=1, cpu_seconds=1),
                          _sample(10, log_bytes=1, cpu_seconds=1),
                          horizon_seconds=1, flat_since_seconds=99)


def test_the_shipped_waiter_command_watches_a_number_and_cannot_match_itself():
    """The reason a coordinator hand-writes a waiter is that the pack did not
    ship one — and the hand-written one matched itself, so it could never
    terminate even after its worker exited. Measured live."""
    command = progress.waiter_command("delta-audit", 2776, sentinel="/private/tmp/report.md")
    joined = " ".join(command)
    assert "pgrep" not in joined, "a pattern matches whatever looks like it, including the watcher"
    assert "/private/tmp/report.md" in joined
    assert "-p 2776" in joined, "the waiter does not name the process number it watches"

    # The decisive property: the waiter's own command line does not contain
    # anything that would make it look like the thing it waits on. No pattern is
    # matched against any command line — the only thing asked about the number
    # is its own process state.
    for pattern_matcher in ("pgrep", "pkill", "ps -ef", "ps aux", "grep -f"):
        assert pattern_matcher not in joined, f"{pattern_matcher} matches whatever looks like it"

    #: THAT IT ENDS is asserted by running it, not by reading it — see
    #: `test_the_shipped_waiter_ends_when_its_worker_ends_even_if_nothing_is_written`.
    #: A string assertion about termination is a claim about the author's
    #: intent, and a mutant that turned the conjunction into a disjunction left
    #: this test and its sibling green.


def test_a_waiter_command_needs_a_real_process_number_and_a_sentinel():
    for bad in (0, -1, True, "2776", None):
        with pytest.raises(IntegrityError):
            progress.waiter_command("r", bad, sentinel="/tmp/x")
    with pytest.raises(IntegrityError):
        progress.waiter_command("r", 1, sentinel="   ")


def test_a_flat_since_the_samples_themselves_contradict_is_refused():
    """The module refuses an undeclared horizon precisely so a caller cannot pick
    a convenient one, and the repair left the same hole one field over: two
    identical readings prove the run was already flat at the earlier one, so a
    later `flat_since` contradicts the samples it came with."""
    with pytest.raises(PreconditionError) as caught:
        progress.classify(
            "delta-audit", _sample(20393.0, log_bytes=39.0, cpu_seconds=0.43),
            _sample(20483.0, log_bytes=39.0, cpu_seconds=0.43),
            horizon_seconds=900, flat_since_seconds=20483.0)
    assert "contradicts the readings" in caught.value.render()


def test_a_flat_since_after_the_earlier_sample_is_fine_when_something_advanced():
    """The other side: if a signal moved between the readings, the caller's
    later `flat_since` is consistent with them and must not be refused."""
    report = progress.classify(
        "moving", _sample(0, log_bytes=1, cpu_seconds=1),
        _sample(100, log_bytes=1, cpu_seconds=9),
        horizon_seconds=10, flat_since_seconds=100.0)
    assert report.state == ProgressState.RUNNING


def test_a_sentinel_path_cannot_break_out_of_the_generated_waiter():
    """New code shipped in the repair for a hand-written waiter, carrying a hole
    the hand-written one did not have: the path was interpolated raw, so a quote
    in it started a second command."""
    import subprocess as sub

    marker = "/private/tmp/waiter-injection-marker"
    hostile = f'/tmp/a b"; touch {marker}; #'
    script = progress.waiter_command("r", 2776, sentinel=hostile)[2]

    # Asserted by RUNNING the generated script's condition, not by reading it: a
    # string assertion about quoting is a claim about the author's intent, and
    # the property is what a shell does with it.
    pathlib.Path(marker).unlink(missing_ok=True)
    sub.run(["sh", "-c", script.replace("kill -0 2776 2>/dev/null", "false")],
            capture_output=True, timeout=20)
    assert not pathlib.Path(marker).exists(), "the sentinel path broke out and ran a command"

    for bad in (0, -1, 999999, True, "20", 1.5):
        with pytest.raises(IntegrityError):
            progress.waiter_command("r", 1, sentinel="/tmp/x", poll_seconds=bad)


def test_a_horizon_that_is_not_a_number_of_seconds_is_refused():
    """The signals were guarded against non-finite readings a round earlier and
    the horizon they are compared against was not. `NaN` made `flat_for <
    horizon` false and reported STALLED with no flat signal behind it; infinity
    made it true forever and reported RUNNING for a run dead a thousand seconds.
    The same rule, one field over, which is where this class always is."""
    earlier = progress.Sample(0, {"log_bytes": 1, "cpu_seconds": 1})
    later = progress.Sample(1000, {"log_bytes": 1, "cpu_seconds": 1})
    for horizon in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(PreconditionError):
            progress.classify("r", earlier, later, horizon_seconds=horizon,
                              flat_since_seconds=0)
    assert progress.classify("r", earlier, later, horizon_seconds=100,
                             flat_since_seconds=0).state == "STALLED"


def test_a_sample_taken_at_no_measurable_time_is_refused():
    """The signals were guarded against non-finite readings, then the horizon
    they are compared against, and the MOMENT the reading was taken at was not —
    so two NaN timestamps produced STALLED with `flat_for_seconds=nan` behind
    it. The same rule, a third field over."""
    for moment in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(IntegrityError):
            progress.Sample(moment, {"log_bytes": 1})
    assert progress.Sample(0.0, {"log_bytes": 1}).at_seconds == 0.0


def test_the_shipped_waiter_ends_when_its_worker_ends_even_if_nothing_is_written():
    """**The property the whole tool exists for, executed rather than read.**

    Both tests of `waiter_command` inspected the generated string. The claim
    they were written for is behavioural — *it terminates even after the worker
    exited* — and a mutant turning the conjunction into a disjunction left both
    of them green; it was caught only incidentally, by an unrelated injection
    test hanging until its own timeout.

    This is not hypothetical. Five hand-written waiters in this release's own
    session watched output content instead of a process, and when their workers
    exited without ever writing the string those waiters were looking for, they
    slept on. Three of them for over ninety-five minutes, on 0.3 seconds of
    processor time, while the interface showed them as live work. A live
    process satisfies a liveness question forever: that is the failure class
    this release was built to close, and this is the executable statement of
    the closure.
    """
    import subprocess as sub
    import time

    sentinel = pathlib.Path(tempfile.mkdtemp()) / "never-written"
    worker = sub.Popen([sys.executable, "-c", "import time; time.sleep(1.5)"])
    try:
        command = progress.waiter_command("r", worker.pid, sentinel=str(sentinel),
                                          poll_seconds=1)
        started = time.monotonic()
        waiter = sub.run(command, capture_output=True, timeout=25)
        elapsed = time.monotonic() - started
    finally:
        worker.wait(timeout=30)

    assert waiter.returncode == 0
    assert not sentinel.exists(), "the sentinel was written, so this proved nothing"
    assert elapsed < 20, (
        f"the waiter ran {elapsed:.1f}s after a worker that lived 1.5s and wrote nothing: "
        f"it is watching for something that will never arrive")
    #: and it really did wait for the worker rather than returning at once
    assert elapsed >= 1.0, (
        f"the waiter returned in {elapsed:.1f}s, before its worker had finished — it is not "
        f"waiting on the process at all")


def test_the_shipped_waiter_ends_the_moment_the_sentinel_appears():
    """The other half. A waiter that only ended when the process died would make
    every completion wait for a teardown, and a worker that writes its result
    and lingers would look like a worker still working."""
    import subprocess as sub
    import time

    sentinel = pathlib.Path(tempfile.mkdtemp()) / "written"
    sentinel.write_text("the result")
    worker = sub.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
    try:
        started = time.monotonic()
        waiter = sub.run(progress.waiter_command("r", worker.pid, sentinel=str(sentinel),
                                                 poll_seconds=1),
                         capture_output=True, timeout=25)
        elapsed = time.monotonic() - started
    finally:
        worker.kill()
        worker.wait(timeout=30)

    assert waiter.returncode == 0
    assert elapsed < 3, (
        f"the result was already on disk and the waiter took {elapsed:.1f}s to notice")
