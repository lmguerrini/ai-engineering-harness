"""The recorded silence, replayed, plus the shapes that would let it recur.

The decisive fixture is the one that matters: declare a wait on a real detached
process, let the process exit, and then **do nothing at all**. A happy-path test
that polls on the coordinator's behalf re-creates the recurrence it is supposed
to catch, because the coordinator that has gone silent is exactly the one that
cannot poll.
"""

import json
import os
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


def _declare_wait_then_finish(tmp_path, job_id="regen", name="exit-status"):
    """Declare the wait FIRST, then let a real process create the sentinel.

    The order is the fixture. A wait declared against a path that already exists
    has a completion condition that was satisfied before the job started, which
    is now refused at construction — and every fixture here originally built the
    wait after reaping the process, so they were all testing a shape the module
    should never see. Found by a cross-vendor auditor pointing a wait at
    `/dev/null`.
    """
    sentinel = tmp_path / name
    wait = Wait.declare(job_id=job_id, kind=WaitKind.EXIT_FILE, path=str(sentinel),
                        expects="the regenerated records, in the output root", not_beyond_seconds=1800)
    process = subprocess.Popen([
        sys.executable, "-c",
        f"import pathlib; pathlib.Path({str(sentinel)!r}).write_text('0')",
    ])
    process.wait()
    for _ in range(200):
        if sentinel.exists():
            break
        time.sleep(0.01)
    return wait, sentinel


# --- the decisive fixture ---------------------------------------------------------


def test_a_finished_job_advances_the_state_with_nobody_acting(tmp_path):
    """The recurrence, replayed. Declared correctly — job, process, expected
    result — and then the job exits and nothing happens on the coordinator's
    side. The state is derived, so it has already moved by the time anybody
    looks, which is the whole difference from a sentence."""
    wait, _sentinel = _declare_wait_then_finish(tmp_path)
    record = _record(waits=(wait,))

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
                 expects="a long analysis", not_beyond_seconds=1800),
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
                                     expects="anything", not_beyond_seconds=1800),))
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
                    expects="a report", not_beyond_seconds=1800),),
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
            Wait(job_id="j", kind=kind, expects="a result", **missing, not_beyond_seconds=1800)
        assert "sentence cannot have a transition" in caught.value.render()


def test_a_wait_that_does_not_say_what_it_expects_is_refused():
    with pytest.raises(PreconditionError):
        Wait(job_id="j", kind=WaitKind.PATH_EXISTS, path="p", expects="  ", not_beyond_seconds=1800)


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
             task_id="batch", max_bytes_per_write=64, expects="the records", not_beyond_seconds=1800),
    ))
    report = continuation.derive(record, relative_to=tmp_path)
    assert report.state == State.RECOVERY_REQUIRED
    assert report.unobservable == ("batch",)
    assert report.wake_required


def test_an_unreadable_exit_file_is_unobservable_rather_than_finished(tmp_path):
    """Declared against a path that does not exist, and what appears there is
    not a status anyone can read."""
    directory = tmp_path / "status-is-a-directory"
    record = _record(waits=(
        Wait(job_id="j", kind=WaitKind.EXIT_FILE, path=str(directory), expects="a status", not_beyond_seconds=1800),
    ))
    directory.mkdir()
    assert continuation.derive(record, relative_to=tmp_path).state == State.RECOVERY_REQUIRED


def test_a_wait_whose_condition_is_already_satisfied_is_refused_at_declaration(tmp_path):
    """A completion condition that holds before the job starts can never mean
    the job finished. An auditor declared a wait on `/dev/null` and derived a
    completed result for a worker that never existed."""
    existing = tmp_path / "already-here"
    existing.write_text("0")
    for kind in (WaitKind.EXIT_FILE, WaitKind.PATH_EXISTS):
        with pytest.raises(PreconditionError) as caught:
            Wait.declare(job_id="j", kind=kind, path=str(existing), expects="a result", not_beyond_seconds=1800)
        assert "already satisfied" in caught.value.render()

    with pytest.raises(PreconditionError):
        Wait.declare(job_id="j", kind=WaitKind.EXIT_FILE, path="/dev/null", expects="a result", not_beyond_seconds=1800)

    # And reconstruction is a different act: a record saved before the job
    # finished must reload after it finished. A check in the constructor made
    # that record unloadable, which is worse than the defect it closed.
    assert Wait(job_id="j", kind=WaitKind.EXIT_FILE, path=str(existing),
                expects="a result", not_beyond_seconds=1800).path == str(existing)


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
    done, _sentinel = _declare_wait_then_finish(tmp_path, job_id="done")
    running = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        record = _record(waits=(
            done,
            Wait(job_id="still-going", kind=WaitKind.PROCESS, pid=running.pid, expects="another", not_beyond_seconds=1800),
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
    done, _sentinel = _declare_wait_then_finish(tmp_path, job_id="done")
    lost = Wait(job_id="lost", kind=WaitKind.EXIT_FILE,
                path=str(tmp_path / "never-a-file"), expects="another", not_beyond_seconds=1800)
    (tmp_path / "never-a-file").mkdir()
    record = _record(waits=(done, lost))
    assert continuation.derive(record, relative_to=tmp_path).state == State.RECOVERY_REQUIRED


def test_a_consumed_completion_is_superseded_rather_than_reported_again(tmp_path):
    """A stale wait left declared after its result was taken up is how a quorum
    of waiters reported RUNNING indefinitely and fired four notifications after
    the job had exited."""
    done, _sentinel = _declare_wait_then_finish(tmp_path, job_id="done")
    # Marked consumed afterwards, the way a coordinator that took the result up
    # would — by replacing the record's own field, not by re-declaring the wait
    # against a path that now exists.
    # Reconstructed, not re-declared: the sentinel exists by now, and that is
    # exactly the state a saved record is reloaded into.
    consumed = Wait(**{**done.as_dict(), "consumed": True})
    record = _record(waits=(consumed,))
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
        Wait(job_id="j", kind="vibes", expects="something", not_beyond_seconds=1800)
    assert "process" in caught.value.render() and "human" in caught.value.render()


# --- the command line -------------------------------------------------------------------


def test_the_cli_exit_status_separates_owed_from_blocked_from_unestablished(tmp_path, capsys):
    path = tmp_path / "CONTINUATION.json"

    continuation.save(_record(), path)
    assert continuation._cli([str(path)]) == 0

    continuation.save(_record(actionable=("do the thing",)), path)
    assert continuation._cli([str(path)]) == 1
    assert State.SILENT_IDLE in capsys.readouterr().out

    unobservable = Wait(job_id="j", kind=WaitKind.EXIT_FILE,
                        path=str(tmp_path / "becomes-a-directory"), expects="a status", not_beyond_seconds=1800)
    (tmp_path / "becomes-a-directory").mkdir()
    continuation.save(_record(waits=(unobservable,)), path)
    assert continuation._cli([str(path)]) == 2, (
        "a record LOADED from disk describes a wait declared earlier; reloading it must not "
        "re-apply the declaration-time check to a world that has since moved"
    )

    continuation.save(_record(blockers=(
        Blocker(kind="human", detail="the freeze decision", hitl_row=2),
    )), path)
    assert continuation._cli([str(path)]) == 3


# --- a completion condition that was already satisfied -------------------------------


def test_an_exit_file_wait_cannot_complete_on_a_character_device():
    """The finding, from a blind cross-vendor reader: a wait pointed at
    `/dev/null` derived a finished result for a worker that never existed.

    `Wait.declare` already refused this, and that check is right where it is —
    but it is reachable only by the caller who declares, and the auditor built
    the record directly. So the OBSERVATION asks again. A sentinel a job writes
    on exit is a regular file; a character device is furniture.
    """
    record = ContinuationRecord(
        capability="cap", updated_at=continuation.now(),
        waits=(Wait(job_id="imaginary-worker", kind=WaitKind.EXIT_FILE,
                                 path="/dev/null", expects="the worker result",
                                 not_beyond_seconds=3600, declared_at=continuation.now()),),
    )
    report = continuation.derive(record, now=continuation.now())
    assert report.state == State.RECOVERY_REQUIRED
    assert "not a regular file" in " ".join(o.how for o in report.observations)


def test_an_exit_file_older_than_its_own_wait_is_not_that_job_s_result(tmp_path):
    """The general form of the same hole: any pre-existing readable path. A file
    last written BEFORE the coordinator began waiting for it did not come from
    the job being waited on, whatever it contains — so the wait is unresolved,
    not complete, and the job may still be running."""
    stale = tmp_path / "exit.status"
    stale.write_text("0")
    os.utime(stale, (1, 1))

    record = ContinuationRecord(
        capability="cap", updated_at=continuation.now(),
        waits=(Wait(job_id="j", kind=WaitKind.EXIT_FILE,
                                 path=str(stale), expects="the worker result",
                                 not_beyond_seconds=3600, declared_at=continuation.now()),),
    )
    report = continuation.derive(record, now=continuation.now())
    assert report.state == State.RECOVERY_REQUIRED
    assert "before this wait was declared" in " ".join(o.how for o in report.observations)


def test_a_sentinel_the_job_actually_wrote_still_completes_the_wait(tmp_path):
    """The bound on the two checks above: the honest path is unchanged, which is
    what stops a fail-closed repair from becoming a refusal to ever finish."""
    sentinel = tmp_path / "exit.status"
    wait = Wait(job_id="j", kind=WaitKind.EXIT_FILE,
                             path=str(sentinel), expects="the worker result",
                             not_beyond_seconds=3600, declared_at=continuation.now())
    sentinel.write_text("0")

    record = ContinuationRecord(capability="cap", updated_at=continuation.now(), waits=(wait,))
    report = continuation.derive(record, now=continuation.now())
    assert report.state == State.COMPLETED_NOT_CONSUMED


# --- what the blockers say TOGETHER ---------------------------------------------------


def test_two_blockers_covering_half_the_work_each_stop_the_run():
    """The finding, from a blind cross-vendor reader. Each blocker was asked
    separately *do you leave the coordinator with nothing to do?*, each named one
    of two items, each answered no — so both were filed as scoped, the unblocked
    remainder came out empty, and the report said **nothing is in the way and
    nothing is outstanding** above a list of two outstanding items and two
    blockers.

    Coverage is a property of the union. It is the same shape as the `any`/`all`
    defect one round earlier: the predicate was right and the quantifier was
    over the wrong set."""
    record = ContinuationRecord(
        capability="cap", updated_at=continuation.now(), actionable=("a", "b"),
        blockers=(Blocker(kind="human", detail="a person decides a", hitl_row=2, blocks=("a",)),
                  Blocker(kind="capacity", detail="no pool for b", pool_id="p", blocks=("b",))),
    )
    report = continuation.derive(record)
    assert report.state == State.BLOCKED_ON_HUMAN
    assert "nothing is in the way" not in report.why


def test_a_blocker_that_leaves_work_uncovered_still_does_not_stop_the_run():
    """The bound, and the defect the union repair could have reintroduced: the
    round-2 finding was a scoped blocker silencing what it did not name."""
    record = ContinuationRecord(
        capability="cap", updated_at=continuation.now(), actionable=("a", "b", "c"),
        blockers=(Blocker(kind="human", detail="a person decides a", hitl_row=2, blocks=("a",)),),
    )
    report = continuation.derive(record)
    assert report.state != State.BLOCKED_ON_HUMAN
    assert "2" in report.why, "the two unblocked items are what silence is measured against"


def test_a_process_id_that_is_not_one_is_a_named_state_not_a_traceback():
    """A saved record is untrusted input. `pid: "not-a-pid"` reloaded happily and
    raised a bare ValueError out of `derive`, where the contract is a state."""
    record = ContinuationRecord(
        capability="cap", updated_at=continuation.now(),
        waits=(Wait(job_id="j", kind=WaitKind.PROCESS, expects="a worker",
                    not_beyond_seconds=60, pid="not-a-pid",
                    declared_at=continuation.now()),),
    )
    report = continuation.derive(record)
    assert report.state == State.RECOVERY_REQUIRED
    assert "not one" in " ".join(o.how for o in report.observations)


def test_a_path_wait_says_that_it_cannot_name_a_producer(tmp_path):
    """An auditor pointed out that an unrelated writer satisfies a path wait, and
    was right: no property of a bare path distinguishes who wrote it. This test
    pins the two things that ARE true, so the weaker claim cannot quietly become
    the stronger one — the path wait completes on any writer, and the kind that
    establishes a producer is the owned output root."""
    completion = tmp_path / "completion"
    wait = Wait.declare(job_id="worker-a", kind=WaitKind.PATH_EXISTS, path=str(completion),
                        expects="worker-a's report", not_beyond_seconds=60)
    completion.write_text("written by somebody else")
    record = ContinuationRecord(capability="cap", updated_at=continuation.now(), waits=(wait,))
    assert continuation.derive(record, relative_to=tmp_path).state == State.COMPLETED_NOT_CONSUMED

    # The kind that does establish it.
    root = tmp_path / "owned"
    contract = task_output.OutputContract("worker-a", root, max_bytes_per_write=64)
    task_output.claim_root(contract)
    task_output.materialise(contract, 0, "done")
    task_output.complete(contract, 1)
    intruder = ContinuationRecord(
        capability="cap", updated_at=continuation.now(),
        waits=(Wait(job_id="worker-b", kind=WaitKind.OUTPUT_ROOT, path=str(root),
                    task_id="worker-b", max_bytes_per_write=64, expects="worker-b's report",
                    not_beyond_seconds=60, declared_at=continuation.now()),),
    )
    assert continuation.derive(intruder, relative_to=tmp_path).state == State.RECOVERY_REQUIRED


@pytest.mark.parametrize("pid", [1.5, float("inf"), float("nan"), True, "1.5", "x"])
def test_a_process_id_must_be_a_whole_number_not_merely_convertible(pid):
    """`int()` was the whole check, and it converts rather than validates. `1.5`
    became process 1 — init, always alive, so the wait reported a running job
    forever — and infinity raised a bare OverflowError. Both found by a blind
    reader ON the repair for the string case."""
    record = ContinuationRecord(
        capability="cap", updated_at=continuation.now(),
        waits=(Wait(job_id="j", kind=WaitKind.PROCESS, expects="a worker",
                    not_beyond_seconds=60, pid=pid, declared_at=continuation.now()),),
    )
    assert continuation.derive(record).state == State.RECOVERY_REQUIRED


def test_a_real_process_id_still_observes_the_process():
    record = ContinuationRecord(
        capability="cap", updated_at=continuation.now(),
        waits=(Wait(job_id="j", kind=WaitKind.PROCESS, expects="a worker",
                    not_beyond_seconds=60, pid=os.getpid(), declared_at=continuation.now()),),
    )
    assert continuation.derive(record).state == State.WAITING_ON_IDENTIFIED_JOB


def test_every_field_of_a_record_survives_being_written_and_read_back(tmp_path):
    """`as_dict` and `load` each enumerate their fields, so a field added to the
    dataclass and to neither is silently dropped at exactly the boundary this
    record exists to survive. Both fields added for the projection were dropped
    on their first save, and this test survived a mutant that deleted one of
    them from `as_dict` until it was written.

    Asserted over the field list rather than over a hand-written set, so the
    next field added is covered by this test on the day it is added."""
    import dataclasses

    record = ContinuationRecord(
        capability="C1", updated_at=continuation.now(),
        actionable=("do the thing",),
        waits=(Wait(job_id="j", kind=WaitKind.HUMAN, expects="a decision",
                    obligation="ob", subject_revision="a" * 40, subject_digest="b" * 64,
                    executor="somebody", declared_at=continuation.now()),),
        blockers=(Blocker(kind="human", detail="d", hitl_row=4, blocks=("do the thing",)),),
        terminal=False, record_path=str(tmp_path / "C.json"),
        budgets={"cycles": {"used": 6, "ceiling": 8}},
        evidence={"suite": "1163 passing"},
    )
    path = tmp_path / "C.json"
    continuation.save(record, path)
    back = continuation.load(path)

    for f in dataclasses.fields(ContinuationRecord):
        assert getattr(back, f.name) == getattr(record, f.name), f"{f.name} did not survive"
    for f in dataclasses.fields(Wait):
        assert getattr(back.waits[0], f.name) == getattr(record.waits[0], f.name), \
            f"Wait.{f.name} did not survive"


@pytest.mark.parametrize("body", [
    {"capability": "cap", "updated_at": "2026-01-01T00:00:00Z", "actionable": [[]]},
    {"capability": "cap", "updated_at": "2026-01-01T00:00:00Z", "actionable": [None]},
    {"capability": "cap", "updated_at": "2026-01-01T00:00:00Z", "actionable": "not a list"},
    {"capability": "cap", "updated_at": "2026-01-01T00:00:00Z",
     "blockers": [{"kind": "human", "detail": "d", "blocks": [{}]}]},
])
def test_a_saved_record_that_names_work_that_is_not_a_name_is_refused(tmp_path, body):
    """A saved record is untrusted input, and `derive` puts these in a set:
    `"actionable": [[]]` loaded fine and raised `TypeError: unhashable type` out
    of the derivation — an exception where the contract is a state."""
    path = tmp_path / "C.json"
    path.write_text(json.dumps(body))
    with pytest.raises(PreconditionError):
        continuation.load(path)


@pytest.mark.parametrize("bound", ["not-an-int", None, 1.5, True, [], "  "])
def test_a_write_bound_that_is_not_a_number_of_bytes_is_a_state_not_a_traceback(tmp_path, bound):
    """The same defect as the process id, one field over — and the pid repair did
    not generalise, because it was written as a repair for the pid rather than
    for the class. Every integer a saved record carries is untrusted input."""
    body = {"capability": "cap", "updated_at": continuation.now(),
            "waits": [{"job_id": "w", "kind": "output_root", "expects": "output",
                       "not_beyond_seconds": 60, "declared_at": continuation.now(),
                       "path": str(tmp_path / "root"), "task_id": "w",
                       "max_bytes_per_write": bound}]}
    path = tmp_path / "C.json"
    path.write_text(json.dumps(body))
    try:
        record = continuation.load(path)
    except PreconditionError:
        return  # refused at the boundary, which is also a named refusal
    assert continuation.derive(record).state == State.RECOVERY_REQUIRED


def test_a_deadline_is_validated_whatever_kind_of_wait_carries_it(tmp_path):
    """The constructor validates the bound only for OBSERVABLE kinds, so a HUMAN
    wait carrying `"not-a-number"` loaded, skipped that check, and raised a bare
    ValueError out of `derive`. A deadline nobody can read has passed."""
    body = {"capability": "cap", "updated_at": continuation.now(),
            "waits": [{"job_id": "human", "kind": "human", "expects": "a decision",
                       "not_beyond_seconds": "not-a-number",
                       "declared_at": "2020-01-01T00:00:00+00:00"}]}
    path = tmp_path / "C.json"
    path.write_text(json.dumps(body))
    assert continuation.derive(continuation.load(path)).state == State.RECOVERY_REQUIRED


@pytest.mark.parametrize("bound", [0, -5, "0"])
def test_a_write_bound_of_zero_or_less_is_a_state_not_a_refusal_from_another_layer(tmp_path, bound):
    """Zero and negative are integers, so the type check passed them into
    `OutputContract`, which refused with a PreconditionError that escaped
    `derive`. A refusal from the wrong layer is still an exception where the
    contract is a state."""
    body = {"capability": "cap", "updated_at": continuation.now(),
            "waits": [{"job_id": "w", "kind": "output_root", "expects": "output",
                       "not_beyond_seconds": 60, "declared_at": continuation.now(),
                       "path": str(tmp_path / "root"), "task_id": "w",
                       "max_bytes_per_write": bound}]}
    path = tmp_path / "C.json"
    path.write_text(json.dumps(body))
    try:
        record = continuation.load(path)
    except PreconditionError:
        return
    assert continuation.derive(record).state == State.RECOVERY_REQUIRED
