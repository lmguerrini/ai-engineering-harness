"""The failure class this release exists to close, reproduced end to end.

`ACTIONABLE_WORK + SILENT_IDLE` — a coordinator with authorised work outstanding
that is doing nothing, and cannot tell that from legitimately waiting. Ten
recorded instances before this release, and then **one more during it**: a
dispatched auditor held the coordinator for five hours and thirty-nine minutes
with 0.34 seconds of processor time, no output bytes and no provider rollout.

The instances are not the point. The point is that the release must make the
condition **terminate deterministically**, and that is what these rehearsals
establish. Each names what it must be able to fail.

The live incident had four distinct causes and every one of them is a fixture
below:

1.  no continuation record existed at all, so nothing could derive a state;
2.  a declared wait had no deadline, so a live process satisfied it forever;
3.  the stall classifier compared its horizon against the interval between two
    samples rather than against how long the run had been flat, so a caller who
    polled could never obtain a stall verdict;
4.  the waiter's own command line matched its own pattern, so it could not
    terminate even after the worker exited.
"""

import json
import subprocess
import sys

import pytest

import continuation
import progress
import projection
import task_output
from continuation import Blocker, ContinuationRecord, State, Wait, WaitKind
from errors import PreconditionError

DECLARED = "2026-09-03T06:33:20+00:00"
FIVE_HOURS_LATER = "2026-09-03T12:12:43+00:00"
ONE_MINUTE_LATER = "2026-09-03T06:34:20+00:00"


def _wait(**overrides):
    fields = dict(job_id="delta-audit", kind=WaitKind.PROCESS, pid=1,
                  obligation="rp23-bounded-delta-re-audit",
                  expects="a bounded delta re-audit report",
                  declared_at=DECLARED, not_beyond_seconds=1800)
    fields.update(overrides)
    return Wait(**fields)


def _record(**overrides):
    fields = dict(capability="C14", updated_at=DECLARED,
                  actionable=("close the capability",))
    fields.update(overrides)
    return ContinuationRecord(**fields)


# --- 1. the incident itself, and it must end -------------------------------------


def test_a_live_process_past_its_deadline_ends_the_wait(monkeypatch):
    """**The closure.** The process is alive — a liveness question about it
    answers "running" forever, which is exactly what held for five hours and
    thirty-nine minutes. The deadline is a statement about the coordinator's
    patience, not about the worker, and it is what terminates the state."""
    monkeypatch.setattr(continuation, "_process_is_gone",
                        lambda pid: (False, f"process {pid} exists"))
    record = _record(waits=(_wait(pid=2776),))

    inside = continuation.derive(record, now=ONE_MINUTE_LATER)
    assert inside.state == State.WAITING_ON_IDENTIFIED_JOB, (
        "a wait inside its deadline is a legitimate wait, and a rehearsal that could not "
        "produce one would be proving the wrong thing"
    )

    past = continuation.derive(record, now=FIVE_HOURS_LATER)
    assert past.state == State.RECOVERY_REQUIRED
    assert past.expired == ("delta-audit",)
    assert past.wake_required
    assert "whatever the job is doing" in past.why
    assert "PAST THE DECLARED DEADLINE" in past.render()


def test_the_deadline_is_required_so_an_unbounded_wait_cannot_be_written():
    """The declaration is where this is refused. A wait with no deadline is the
    shape that held the coordinator, and it is now unwritable."""
    for kind, extra in ((WaitKind.PROCESS, {"pid": 1}),
                        (WaitKind.EXIT_FILE, {"path": "/nonexistent/sentinel"}),
                        (WaitKind.PATH_EXISTS, {"path": "/nonexistent/other"})):
        with pytest.raises(PreconditionError) as caught:
            Wait(job_id="j", kind=kind, expects="a result", **extra)
        assert "five hours and" in caught.value.render()


def test_a_wait_on_a_person_needs_no_deadline_because_patience_is_not_the_question():
    """The exception, and it is deliberate: coordinator unavailability never
    implies authorisation, and neither does a checker's impatience."""
    record = _record(waits=(Wait(job_id="freeze", kind=WaitKind.HUMAN,
                                 expects="the founder's authorisation"),))
    assert continuation.derive(record, now=FIVE_HOURS_LATER).state == State.BLOCKED_ON_HUMAN


def test_the_expiry_outranks_a_process_that_still_looks_alive(monkeypatch):
    """Ordering, asserted directly. If the observation ran first, a live process
    would report WAITING_ON_IDENTIFIED_JOB and the deadline would never be
    reached — which is the bug wearing the fix's clothes."""
    monkeypatch.setattr(continuation, "_process_is_gone", lambda pid: (False, "alive"))
    report = continuation.derive(_record(waits=(_wait(),)), now=FIVE_HOURS_LATER)
    assert report.state == State.RECOVERY_REQUIRED
    assert any(o.finished is False for o in report.observations), (
        "the fixture must still show the process as running, or it is not reproducing the case"
    )


# --- 2. the stall classifier, on the incident's own numbers -----------------------


def test_the_classifier_now_diagnoses_the_incident_it_missed():
    """Sampled the way it was sampled at the time — ninety seconds apart — over
    the durable readings taken from the live processes."""
    report = progress.classify(
        "delta-audit",
        progress.Sample(20393.0, {"log_bytes": 39.0, "cpu_seconds": 0.43, "provider_rollout": 0.0}),
        progress.Sample(20483.0, {"log_bytes": 39.0, "cpu_seconds": 0.43, "provider_rollout": 0.0}),
        horizon_seconds=900, flat_since_seconds=0.0,
    )
    assert report.state == progress.ProgressState.STALLED
    assert report.flat == ("cpu_seconds", "log_bytes", "provider_rollout")


# --- 3. duplicate workers for one obligation ---------------------------------------


def test_two_live_waits_on_one_obligation_are_refused_rather_than_raced(monkeypatch):
    monkeypatch.setattr(continuation, "_process_is_gone", lambda pid: (False, "alive"))
    record = _record(waits=(
        _wait(job_id="attempt-1", pid=1),
        _wait(job_id="attempt-2", pid=2),
    ))
    report = continuation.derive(record, now=ONE_MINUTE_LATER)
    assert report.state == State.RECOVERY_REQUIRED
    assert report.duplicated == ("rp23-bounded-delta-re-audit",)
    assert "work nobody asked for" in report.why


def test_retiring_the_first_frees_the_obligation_for_a_replacement(monkeypatch):
    """Recovery retires; it does not delete. The record still says what
    happened, and the replacement is not a duplicate."""
    monkeypatch.setattr(continuation, "_process_is_gone", lambda pid: (False, "alive"))
    record = _record(waits=(
        _wait(job_id="attempt-1", pid=1, retired=True),
        _wait(job_id="attempt-2", pid=2, declared_at=ONE_MINUTE_LATER),
    ))
    report = continuation.derive(record, now=ONE_MINUTE_LATER)
    assert report.duplicated == ()
    assert report.state == State.WAITING_ON_IDENTIFIED_JOB
    assert [w.job_id for w in record.waits] == ["attempt-1", "attempt-2"], (
        "the retired attempt is still in the record; retiring is not deleting"
    )


# --- 4. a blocker must not silence work it has nothing to do with -------------------


def test_a_scoped_blocker_does_not_stop_unrelated_authorised_work():
    """Another way into the same failure class: a human decision outstanding on
    one stalled process reported a whole capability BLOCKED_ON_HUMAN while five
    authorised items sat undone. From outside, a blocker that stops unrelated
    work is indistinguishable from a coordinator that has stopped."""
    blocker = Blocker(kind="human", detail="ending two stalled processes", hitl_row=4,
                      blocks=("end the stalled processes",))
    report = continuation.derive(_record(actionable=("write the rehearsal",),
                                         blockers=(blocker,)))
    assert report.state == State.SILENT_IDLE, "the outstanding work is owed, not blocked"
    assert "SCOPED" in report.render()
    assert "does not stop the outstanding work" in report.render()


def test_a_blocker_whose_scope_nobody_stated_blocks_everything():
    """The safe default. An unscoped blocker is one nobody has thought about,
    and guessing that it is narrow is the unsafe direction."""
    blocker = Blocker(kind="human", detail="something outstanding", hitl_row=2)
    report = continuation.derive(_record(actionable=("anything",), blockers=(blocker,)))
    assert report.state == State.BLOCKED_ON_HUMAN


# --- 5. the waiter that could not terminate ------------------------------------------


def test_the_shipped_waiter_cannot_match_itself_and_the_handwritten_one_did():
    """The live waiter was `until [ -s report ] && ! pgrep -qf "codex exec"`, and
    `pgrep -f "codex exec"` matched the waiter's own command line. It could never
    terminate — not even after the worker exited."""
    generated = " ".join(progress.waiter_command("delta-audit", 2776, sentinel="/tmp/report.md"))
    assert "pgrep" not in generated
    assert "kill -0 2776" in generated

    with pytest.raises(PreconditionError):
        progress.Waiter(waiter_id="w", run_id="delta-audit",
                        own_command='until ! pgrep -qf "codex exec"; do sleep 20; done',
                        match_pattern="codex exec")


# --- 6. survives a coordinator that is gone -------------------------------------------


def test_the_whole_position_reconstructs_from_disk_alone(tmp_path):
    """The continuation rehearsal: persist, lose the coordinator, reconstruct,
    consume exactly once, continue without duplicate dispatch.

    Nothing here reads a summary, and the second half runs in a **separate
    process** so it cannot inherit anything the first half held in memory.
    """
    sentinel = tmp_path / "exit-status"
    wait = Wait.declare(job_id="worker-1", kind=WaitKind.EXIT_FILE, path=str(sentinel),
                        obligation="the-one-obligation", expects="a report",
                        not_beyond_seconds=3600)
    continuation.save(
        _record(capability="CAP-REHEARSAL", actionable=("consume the result",), waits=(wait,)),
        tmp_path / "CONTINUATION.json")

    # ... the coordinator is gone. The worker finishes anyway.
    sentinel.write_text("0")

    # A FRESH process, holding nothing.
    script = f'''
import sys; sys.path.insert(0, {str(__import__("pathlib").Path(continuation.__file__).parent)!r})
import json, continuation
record = continuation.load({str(tmp_path / "CONTINUATION.json")!r})
report = continuation.derive(record, relative_to={str(tmp_path)!r})
print(json.dumps({{
    "capability": record.capability,
    "state": report.state,
    "unconsumed": list(report.unconsumed),
    "obligations": [w.obligation for w in record.waits],
    "actionable": list(record.actionable),
    "wake": report.wake_required,
}}))
'''
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    recovered = json.loads(out.stdout)

    assert recovered["capability"] == "CAP-REHEARSAL"
    assert recovered["state"] == State.COMPLETED_NOT_CONSUMED
    assert recovered["unconsumed"] == ["worker-1"]
    assert recovered["obligations"] == ["the-one-obligation"]
    assert recovered["actionable"] == ["consume the result"]
    assert recovered["wake"] is True

    # Consumed exactly once: the same obligation is now held by a retired wait,
    # so a replacement dispatch is not a duplicate and the result is not taken
    # up twice.
    consumed = Wait(**{**wait.as_dict(), "consumed": True})
    after = continuation.derive(
        _record(capability="CAP-REHEARSAL", actionable=(), waits=(consumed,)),
        relative_to=tmp_path)
    assert after.unconsumed == ()
    assert after.superseded == ("worker-1",)
    assert after.state == State.ACTIONABLE_WORK_READY


def test_the_reconstruction_needs_no_conversation_and_no_summary(tmp_path):
    """The negative half: a record that carried a stored state could be right
    when written and wrong when read. There is no state on disk to be stale."""
    written = json.loads(
        (continuation.save(_record(waits=(_wait(),)), tmp_path / "c.json")).read_text())
    assert "state" not in written
    assert not any("state" in key for key in written)
    for wait in written["waits"]:
        assert "not_beyond_seconds" in wait and "obligation" in wait


# --- 7. and the projection shows it -----------------------------------------------------


def test_the_projection_surfaces_an_expired_wait(tmp_path, monkeypatch):
    monkeypatch.setattr(continuation, "_process_is_gone", lambda pid: (False, "alive"))
    (tmp_path / "PROJECT.yaml").write_text("project:\n  name: r\n  repo_path: .\n")
    continuation.save(_record(waits=(_wait(),)), tmp_path / "CONTINUATION.json")

    rendered = projection.project(tmp_path).render()
    assert "delta-audit" in rendered
    # The projection derives with the real clock, and the fixture's deadline is
    # long past it, so the expiry must reach the view.
    assert "PAST THE DECLARED DEADLINE" in rendered or State.RECOVERY_REQUIRED in rendered


# --- 8. what these rehearsals do NOT establish -------------------------------------------


def test_the_release_ships_no_mechanism_that_ends_a_worker():
    """Stated as a test so it cannot drift. Every mechanism above **classifies**
    and **reports**; ending a process remains a coordinator action under
    `policy/hitl-matrix.md` row 4, and during the live incident the coordinator
    escalated rather than terminating because two of the frozen contract's seven
    preconditions were absent."""
    for module in (continuation, progress, task_output, projection):
        names = set(dir(module))
        for forbidden in ("kill", "terminate", "stop_worker", "abort", "signal_worker"):
            assert forbidden not in names, f"{module.__name__} gained {forbidden!r}"


def test_a_result_that_arrived_late_is_consumed_rather_than_recovered(tmp_path):
    """Ordering, and it is not arbitrary. A job that finished past its deadline
    has left something to take up, and taking it up IS the recovery. Expiry is
    the answer when there is nothing there."""
    sentinel = tmp_path / "exit-status"
    wait = Wait(job_id="late", kind=WaitKind.EXIT_FILE, path=str(sentinel),
                obligation="one", expects="a report",
                declared_at=DECLARED, not_beyond_seconds=1800)
    sentinel.write_text("0")
    report = continuation.derive(_record(waits=(wait,)), relative_to=tmp_path,
                                 now=FIVE_HOURS_LATER)
    assert report.state == State.COMPLETED_NOT_CONSUMED
    assert report.unconsumed == ("late",)
    assert report.expired == ("late",), "the deadline is still reported; it is just not the verdict"
