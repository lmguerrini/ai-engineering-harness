"""The recorded silence, replayed, plus the shapes that would let it recur.

The decisive fixture is the one that matters: declare a wait on a real detached
process, let the process exit, and then **do nothing at all**. A happy-path test
that polls on the coordinator's behalf re-creates the recurrence it is supposed
to catch, because the coordinator that has gone silent is exactly the one that
cannot poll.
"""

import json
import subprocess
import sys
import time

import pytest

import continuation
import task_output
from continuation import Blocker, ContinuationRecord, State, Wait, WaitKind
from errors import IntegrityError, PreconditionError


def _record(**overrides):
    fields = dict(capability="CAP-EXAMPLE", updated_at=continuation.now())
    fields.update(overrides)
    return ContinuationRecord(**fields)


def _spawn_and_reap(tmp_path):
    """A real detached process that exits, and the exit-status file it leaves.

    Reaped here so the test does not depend on the parent's zombie handling,
    which would make the process appear alive on some platforms and turn a
    correct observation into a flake.
    """
    sentinel = tmp_path / "exit-status"
    process = subprocess.Popen([
        sys.executable, "-c",
        f"import sys, pathlib; pathlib.Path({str(sentinel)!r}).write_text('0')",
    ])
    process.wait()
    for _ in range(200):
        if sentinel.exists():
            break
        time.sleep(0.01)
    return process.pid, sentinel


# --- the decisive fixture ---------------------------------------------------------


def test_a_finished_job_advances_the_state_with_nobody_acting(tmp_path):
    """The recurrence, replayed. Declared correctly — job, process, expected
    result — and then the job exits and nothing happens on the coordinator's
    side. The state is derived, so it has already moved by the time anybody
    looks, which is the whole difference from a sentence."""
    pid, sentinel = _spawn_and_reap(tmp_path)
    record = _record(waits=(
        Wait(job_id="regen", kind=WaitKind.EXIT_FILE, path=str(sentinel),
             expects="the regenerated records, in the output root"),
    ))

    report = continuation.derive(record, relative_to=tmp_path)

    assert report.state == State.COMPLETED_NOT_CONSUMED
    assert report.unconsumed == ("regen",)
    assert report.wake_required
    assert continuation.COORDINATOR_WAKE_REQUIRED in report.render()


def test_a_running_job_is_not_reported_as_finished(tmp_path):
    """The other half. A detector that called everything finished would pass
    the test above and be useless."""
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        record = _record(waits=(
            Wait(job_id="slow", kind=WaitKind.PROCESS, pid=process.pid,
                 expects="a long analysis"),
        ))
        report = continuation.derive(record, relative_to=tmp_path)
        assert report.state == State.WAITING_ON_IDENTIFIED_JOB
        assert not report.wake_required
    finally:
        process.kill()
        process.wait()


def test_a_process_wait_reports_that_a_reused_number_would_look_the_same(tmp_path):
    """Liveness by process number cannot distinguish a reused one, and the
    report says so rather than implying a certainty it does not have."""
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        record = _record(waits=(Wait(job_id="j", kind=WaitKind.PROCESS, pid=process.pid,
                                     expects="anything"),))
        assert "reused number" in continuation.derive(record, relative_to=tmp_path).render()
    finally:
        process.kill()
        process.wait()


# --- the state is not stored, so it cannot be stale ---------------------------------


def test_the_record_stores_no_state_field_at_all():
    """Structural, and it is the whole design. A stored state is a value that
    can be right when it is written and wrong a second later, which is what
    two hours and twenty-one minutes of silence was."""
    stored = set(ContinuationRecord.__dataclass_fields__)
    assert "state" not in stored
    assert not any("state" in name for name in stored), sorted(stored)
    written = json.loads(json.dumps(_record().as_dict()))
    assert "state" not in written


def test_a_saved_record_round_trips_and_derives_the_same_answer(tmp_path):
    record = _record(
        actionable=("write the gate record",),
        waits=(Wait(job_id="j1", kind=WaitKind.PATH_EXISTS, path="never-appears",
                    expects="a report"),),
    )
    path = continuation.save(record, tmp_path / "CONTINUATION.json")
    reloaded = continuation.load(path)
    assert reloaded.as_dict() == record.as_dict()
    assert (continuation.derive(reloaded, relative_to=tmp_path).state
            == continuation.derive(record, relative_to=tmp_path).state)


# --- the defect state -----------------------------------------------------------------


def test_authorised_work_with_nothing_in_the_way_is_a_defect_and_not_a_rest():
    report = continuation.derive(_record(actionable=("repair the gate", "close the capability")))
    assert report.state == State.SILENT_IDLE
    assert report.is_defect, "SILENT_IDLE must be representable as a defect, never a resting place"
    assert report.wake_required
    assert "DEFECT" in report.render()


def test_nothing_outstanding_is_ready_rather_than_idle():
    """The distinction the defect state depends on. If an empty record were
    also SILENT_IDLE the state would mean nothing."""
    report = continuation.derive(_record())
    assert report.state == State.ACTIONABLE_WORK_READY
    assert not report.is_defect and not report.wake_required


# --- a wait nobody can observe ------------------------------------------------------


def test_a_wait_with_no_observable_condition_is_refused_at_declaration():
    """Refused where it is written, because a wait that cannot be checked is
    the exact shape that decayed."""
    for kind, missing in ((WaitKind.PROCESS, {}), (WaitKind.EXIT_FILE, {}),
                          (WaitKind.OUTPUT_ROOT, {"path": "/tmp/x"})):
        with pytest.raises(PreconditionError) as caught:
            Wait(job_id="j", kind=kind, expects="a result", **missing)
        assert "sentence cannot have a transition" in caught.value.render()


def test_a_wait_that_does_not_say_what_it_expects_is_refused():
    with pytest.raises(PreconditionError):
        Wait(job_id="j", kind=WaitKind.PATH_EXISTS, path="p", expects="  ")


def test_an_output_root_that_cannot_be_classified_needs_recovery_not_patience(tmp_path):
    """The MUST-GO-RED half: an observation that can no longer be made is
    reported as unobservable rather than as still-waiting. Waiting out a
    condition nobody can evaluate is the recurrence with extra steps."""
    contract = task_output.OutputContract(
        task_id="batch", output_root=tmp_path / "out", max_bytes_per_write=64)
    task_output.claim_root(contract)
    task_output.materialise(contract, 0, "a chunk")
    (contract.output_root / "who-wrote-this.txt").write_text("x")  # -> UNKNOWN

    record = _record(waits=(
        Wait(job_id="batch", kind=WaitKind.OUTPUT_ROOT, path=str(contract.output_root),
             task_id="batch", max_bytes_per_write=64, expects="the records"),
    ))
    report = continuation.derive(record, relative_to=tmp_path)
    assert report.state == State.RECOVERY_REQUIRED
    assert report.unobservable == ("batch",)
    assert report.wake_required


def test_an_unreadable_exit_file_is_unobservable_rather_than_finished(tmp_path):
    directory = tmp_path / "status-is-a-directory"
    directory.mkdir()
    record = _record(waits=(
        Wait(job_id="j", kind=WaitKind.EXIT_FILE, path=str(directory), expects="a status"),
    ))
    assert continuation.derive(record, relative_to=tmp_path).state == State.RECOVERY_REQUIRED


# --- blocked, which is neither progress nor a defect ------------------------------------


def test_a_human_block_names_the_row_it_sits_on():
    with pytest.raises(PreconditionError):
        Blocker(kind="human", detail="the freeze decision")
    report = continuation.derive(_record(
        actionable=("cut the release",),
        blockers=(Blocker(kind="human", detail="the freeze decision", hitl_row=2),),
    ))
    assert report.state == State.BLOCKED_ON_HUMAN
    assert "row 2" in report.render()
    assert not report.is_defect, "waiting on a person is not a defect"


def test_a_capacity_block_is_distinct_from_waiting_on_a_job():
    """What resolves one is a clock; what resolves the other is a result. The
    two produced the same observable and needed different answers."""
    report = continuation.derive(_record(
        actionable=("dispatch the next wave",),
        blockers=(Blocker(kind="capacity", detail="the rolling window is exhausted",
                          pool_id="shared-with-the-parent-session"),),
    ))
    assert report.state == State.BLOCKED_ON_CAPACITY
    assert "pool shared-with-the-parent-session" in report.render()


def test_a_human_wait_is_reported_as_a_human_block_not_as_an_unobservable_job():
    report = continuation.derive(_record(waits=(
        Wait(job_id="freeze", kind=WaitKind.HUMAN, expects="the founder's authorisation"),
    )))
    assert report.state == State.BLOCKED_ON_HUMAN
    assert report.unobservable == (), "a person is not a broken observable"


# --- ordering, and it is not arbitrary ---------------------------------------------------


def test_an_unconsumed_completion_is_not_buried_under_another_running_job(tmp_path):
    """The edge four of five recurrences were. Reporting only "still waiting on
    something" is how it stayed invisible."""
    _pid, sentinel = _spawn_and_reap(tmp_path)
    running = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        record = _record(waits=(
            Wait(job_id="done", kind=WaitKind.EXIT_FILE, path=str(sentinel), expects="a result"),
            Wait(job_id="still-going", kind=WaitKind.PROCESS, pid=running.pid, expects="another"),
        ))
        report = continuation.derive(record, relative_to=tmp_path)
        assert report.state == State.COMPLETED_NOT_CONSUMED
        assert report.unconsumed == ("done",)
    finally:
        running.kill()
        running.wait()


def test_something_that_cannot_be_established_outranks_everything_else(tmp_path):
    """Acting on an unestablished state is the error class the pack exists to
    refuse, so it is reported before any answer that could be acted on."""
    _pid, sentinel = _spawn_and_reap(tmp_path)
    record = _record(waits=(
        Wait(job_id="done", kind=WaitKind.EXIT_FILE, path=str(sentinel), expects="a result"),
        Wait(job_id="lost", kind=WaitKind.EXIT_FILE, path=str(tmp_path), expects="another"),
    ))
    assert continuation.derive(record, relative_to=tmp_path).state == State.RECOVERY_REQUIRED


def test_a_consumed_completion_is_superseded_rather_than_reported_again(tmp_path):
    """A stale wait left declared after its result was taken up is how a quorum
    of waiters reported RUNNING indefinitely and fired four notifications after
    the job had exited."""
    _pid, sentinel = _spawn_and_reap(tmp_path)
    record = _record(waits=(
        Wait(job_id="done", kind=WaitKind.EXIT_FILE, path=str(sentinel),
             expects="a result", consumed=True),
    ))
    report = continuation.derive(record, relative_to=tmp_path)
    assert report.superseded == ("done",)
    assert report.state == State.ACTIONABLE_WORK_READY
    assert "retire it" in report.render()


def test_a_record_that_is_terminal_and_also_has_work_cannot_be_both():
    report = continuation.derive(_record(terminal=True, actionable=("one more thing",)))
    assert report.state == State.RECOVERY_REQUIRED


def test_terminal_with_nothing_outstanding_is_terminal():
    assert continuation.derive(_record(terminal=True)).state == State.TERMINAL


# --- refusals a reader can act on -----------------------------------------------------


def test_a_malformed_record_is_refused_with_its_path(tmp_path):
    broken = tmp_path / "CONTINUATION.json"
    broken.write_text("{ not json")
    with pytest.raises(PreconditionError) as caught:
        continuation.load(broken)
    assert str(broken) in caught.value.render()

    broken.write_text(json.dumps({"capability": "C", "waits": [{"job_id": "j"}]}))
    with pytest.raises(PreconditionError):
        continuation.load(broken)


def test_an_unknown_wait_kind_names_the_kinds_that_exist():
    with pytest.raises(IntegrityError) as caught:
        Wait(job_id="j", kind="vibes", expects="something")
    assert "process" in caught.value.render() and "human" in caught.value.render()


# --- the command line -------------------------------------------------------------------


def test_the_cli_exit_status_separates_owed_from_blocked_from_unestablished(tmp_path, capsys):
    path = tmp_path / "CONTINUATION.json"

    continuation.save(_record(), path)
    assert continuation._cli([str(path)]) == 0

    continuation.save(_record(actionable=("do the thing",)), path)
    assert continuation._cli([str(path)]) == 1
    assert State.SILENT_IDLE in capsys.readouterr().out

    continuation.save(_record(waits=(
        Wait(job_id="j", kind=WaitKind.EXIT_FILE, path=str(tmp_path), expects="a status"),
    )), path)
    assert continuation._cli([str(path)]) == 2

    continuation.save(_record(blockers=(
        Blocker(kind="human", detail="the freeze decision", hitl_row=2),
    )), path)
    assert continuation._cli([str(path)]) == 3
