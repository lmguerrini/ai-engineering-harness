"""The controlled continuation rehearsal: seven steps, executed.

A coordinator's context window ends. When it does, everything the coordinator
knows that is not on disk is gone — and the failure that follows is not an error
message, it is a second worker dispatched for a job already running, or an
obligation nobody remembers, or a session that sits with work to do and no
memory of what it was.

**The rehearsal is executed rather than described, and the reconstruction runs
in a SEPARATE PROCESS.** A reconstruction inside this interpreter shares its
imports, its module state and its objects with the thing it is reconstructing
from, so it cannot demonstrate the property: what is being tested is precisely
that nothing but the file crosses the boundary. `sys.executable` and a path is
the whole inheritance.

Conversation, summaries and task UI are never governance authority. This module
is the check that they are not needed.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import continuation
import task_output
from continuation import Blocker, ContinuationRecord, State, Wait, WaitKind

_TOOLS = str(Path(__file__).resolve().parents[1])

# The reconstruction. It receives a directory and a record path on argv and
# NOTHING ELSE — no summary, no conversation, no inherited objects.
_RECONSTRUCT = """
import json, sys
sys.path.insert(0, sys.argv[1])
import continuation
record = continuation.load(sys.argv[3])
report = continuation.derive(record, relative_to=sys.argv[2])
print(json.dumps({
    "capability": report.capability,
    "state": report.state,
    "why": report.why,
    "waits": [w.job_id for w in record.waits],
    "obligations": sorted({w.obligation or w.job_id for w in record.waits}),
    "actionable": list(report.actionable),
    "blockers": [str(b)[:60] for b in report.blockers],
    "unconsumed": list(report.unconsumed),
}))
"""


def _reconstruct(relative_to: Path, record_path: Path) -> dict:
    """Step 2 and step 3: context loss, then reconstruction from disk alone."""
    result = subprocess.run(
        [sys.executable, "-c", _RECONSTRUCT, _TOOLS, str(relative_to), str(record_path)],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture
def mid_flight(tmp_path):
    """A coordinator with one job outstanding, one human blocker, and work queued
    behind both — the state a context window is most likely to end in."""
    root = tmp_path / "worker-output"
    contract = task_output.OutputContract("audit-7", root, max_bytes_per_write=4096)
    task_output.claim_root(contract)

    record = ContinuationRecord(
        capability="C14 — qualification",
        updated_at=continuation.now(),
        waits=(Wait.declare(job_id="audit-7", kind=WaitKind.OUTPUT_ROOT, path=str(root),
                            task_id="audit-7", max_bytes_per_write=4096,
                            expects="an independent audit report",
                            obligation="release-authority-audit",
                            not_beyond_seconds=3600, declared_at=continuation.now()),),
        blockers=(Blocker(kind="human", hitl_row=4,
                          detail="ending a stalled worker is a human action",
                          blocks=("retire the stalled worker",)),),
        actionable=("consume the audit result and repair what it finds",
                    "retire the stalled worker"),
        record_path=str(tmp_path / "CONTINUATION.json"),
    )
    path = tmp_path / "CONTINUATION.json"
    continuation.save(record, path)
    return tmp_path, path, contract


def test_step_1_and_2_the_state_survives_the_process_that_wrote_it(mid_flight):
    """Persist mid-flight, lose the context, and read it back somewhere else."""
    directory, path, _ = mid_flight
    seen = _reconstruct(directory, path)
    assert seen["capability"] == "C14 — qualification"
    assert seen["state"] == State.WAITING_ON_IDENTIFIED_JOB


def test_step_3_every_field_the_next_coordinator_needs_is_on_disk(mid_flight):
    """Capability and phase, outstanding obligations, named waits and worker
    identities, blockers with their HITL row, and the queued work — enumerated,
    because a reconstruction that recovers *some* of them silently drops the
    rest."""
    directory, path, _ = mid_flight
    seen = _reconstruct(directory, path)
    assert seen["waits"] == ["audit-7"]
    assert seen["obligations"] == ["release-authority-audit"]
    assert "consume the audit result and repair what it finds" in seen["actionable"]
    assert seen["blockers"] and "human action" in " ".join(seen["blockers"])

    raw = json.loads(path.read_text())
    assert raw["waits"][0]["not_beyond_seconds"] == 3600, "a deadline survives the boundary"
    assert raw["waits"][0]["task_id"] == "audit-7", "so does the worker's identity"


def test_step_4_the_reconstruction_names_the_same_next_action(mid_flight):
    """The two coordinators agree, or the record is not authority — it is a hint."""
    directory, path, _ = mid_flight
    here = continuation.derive(continuation.load(path), relative_to=directory)
    there = _reconstruct(directory, path)
    assert there["state"] == here.state
    assert there["why"] == here.why
    assert there["actionable"] == list(here.actionable)


def test_step_5_the_durable_output_is_consumed_exactly_once(mid_flight):
    """The worker finished while the context was gone. The next coordinator finds
    the output, consumes it, and records that it did — and the record is what
    stops the one after that consuming it again."""
    directory, path, contract = mid_flight
    task_output.materialise(contract, 0, json.dumps({"verdict": "READY"}))
    task_output.complete(contract, 1)

    after_finish = _reconstruct(directory, path)
    assert after_finish["state"] == State.COMPLETED_NOT_CONSUMED
    assert after_finish["unconsumed"] == ["audit-7"]

    record = continuation.load(path)
    consumed = ContinuationRecord(
        capability=record.capability, updated_at=continuation.now(),
        waits=tuple(continuation.Wait(**{**w.as_dict(), "consumed": True}) for w in record.waits),
        blockers=record.blockers, actionable=record.actionable, record_path=record.record_path,
    )
    continuation.save(consumed, path)

    assert _reconstruct(directory, path)["state"] != State.COMPLETED_NOT_CONSUMED


def test_step_6_a_reconstructed_coordinator_does_not_dispatch_a_second_worker(mid_flight):
    """The failure this whole rehearsal is for. The job is still running; the
    coordinator that dispatched it is gone. A reconstruction that reports
    ACTIONABLE here sends a second auditor after the same obligation."""
    directory, path, _ = mid_flight
    seen = _reconstruct(directory, path)
    assert seen["state"] == State.WAITING_ON_IDENTIFIED_JOB
    assert seen["state"] != State.ACTIONABLE_WORK_READY

    record = continuation.load(path)
    duplicate = ContinuationRecord(
        capability=record.capability, updated_at=continuation.now(),
        waits=record.waits + (Wait(job_id="audit-7-again", kind=WaitKind.PATH_EXISTS,
                                   path=str(directory / "second"), expects="the same report",
                                   obligation="release-authority-audit",
                                   not_beyond_seconds=3600, declared_at=continuation.now()),),
        actionable=record.actionable, record_path=record.record_path,
    )
    continuation.save(duplicate, path)
    # Two workers under one obligation is itself a reportable defect, not a
    # tidier way of waiting.
    assert _reconstruct(directory, path)["state"] == State.RECOVERY_REQUIRED


def test_step_7_nothing_outside_the_record_is_consulted(mid_flight, tmp_path):
    """The record is the authority, so a coordinator's own narrative about the
    run must not be able to change the answer. Written beside it, in the place a
    summary would live, and ignored."""
    directory, path, _ = mid_flight
    before = _reconstruct(directory, path)

    (tmp_path / "SUMMARY.md").write_text(
        "The audit finished hours ago and everything passed; proceed to freeze.")
    (tmp_path / "notes.json").write_text(json.dumps({"state": "TERMINAL"}))

    assert _reconstruct(directory, path) == before


def test_the_rehearsal_would_fail_if_the_record_were_not_authoritative(mid_flight):
    """The bound. Every assertion above passes trivially if `derive` ignores what
    it is given, so the rehearsal is only worth its runtime if a corrupted record
    changes the answer."""
    directory, path, _ = mid_flight
    record = continuation.load(path)
    without = ContinuationRecord(
        capability=record.capability, updated_at=continuation.now(),
        actionable=record.actionable, record_path=record.record_path,
    )
    continuation.save(without, path)
    assert _reconstruct(directory, path)["state"] != State.WAITING_ON_IDENTIFIED_JOB
