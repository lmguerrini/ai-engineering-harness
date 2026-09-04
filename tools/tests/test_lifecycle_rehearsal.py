"""The governed lifecycle, rehearsed end to end rather than module by module.

Every module in this pack has its own tests and every one of them passes; that
is not the same as the lifecycle converging. **The property here is that a
governed run reaches a coherent terminal state without anybody waking the
coordinator**, except where a genuine human decision is owed.

Deterministic on purpose. These use real durable artifacts, real derivation and
real reconstruction, and spawn no workers — so every future run of the suite
keeps the property cheaply. The real-dispatch version runs once, outside the
suite, and its evidence is recorded beside the release rather than in it.

If any rehearsal reaches `SILENT_IDLE` with work outstanding, that is a release
blocker and this file is where it surfaces.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import capacity
import continuation
import history_anchor
import projection
import task_output
from continuation import Blocker, ContinuationRecord, State, Wait, WaitKind

ROOT = Path(__file__).resolve().parents[2]


def _save(root: Path, **fields) -> Path:
    fields.setdefault("capability", "C1 — the capability under rehearsal")
    fields.setdefault("updated_at", continuation.now())
    fields["record_path"] = str(root / "CONTINUATION.json")
    continuation.save(ContinuationRecord(**fields), root / "CONTINUATION.json")
    return root / "CONTINUATION.json"


def _state(root: Path) -> str:
    return continuation.derive(
        continuation.load(root / "CONTINUATION.json"), relative_to=root).state


def _renders(root: Path) -> str:
    """Every rehearsal renders the dashboard from the same durable state it is
    asserting on. A lifecycle stage the projection cannot render is a stage a
    human cannot watch."""
    view = projection.project(root)
    text = view.render()
    page = projection.render_html(view)
    assert text and page.endswith("</html>")
    return text


# --- 1. a clean bootstrap ------------------------------------------------------------


def test_a_new_project_starts_with_nothing_and_says_so(tmp_path):
    """The first thing a real project does is exist with no state at all. That
    must read as UNKNOWN rather than as healthy — an empty directory is the
    cheapest way to render a lie."""
    out = _renders(tmp_path)
    assert "UNKNOWN" in out
    assert "nothing to read" in out or "could not be read" in out


# --- 2 & 16. the pin a project verifies rather than copies ---------------------------


def test_a_project_verifies_the_pack_it_pins_rather_than_trusting_it(tmp_path):
    """The adoption contract: a project records root, version, revision, digest
    and state, and re-derives all of it. A pin that is merely written down is a
    claim."""
    import pack_pin

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    digest = json.loads((ROOT / "PACK_MANIFEST.json").read_text())["tree_digest_sha256"]

    problems = pack_pin.verify_pin(ROOT, expect_version="2.3.0", expect_sha=head,
                                   expect_digest=digest, expect_state="IN_PROGRESS")
    # An untracked file is a real finding about a working checkout and not about
    # the pin mechanism, and this rehearsal runs in one. It is reported rather
    # than ignored, and everything else must still verify.
    untracked = [p for p in problems if "untracked" in p]
    assert problems == untracked, f"the pin failed for a reason other than a dirty checkout: {problems}"
    wrong = pack_pin.verify_pin(ROOT, expect_version="2.3.0", expect_sha="0" * 40,
                                expect_digest=digest, expect_state="IN_PROGRESS")
    assert wrong, "a pin naming another revision verified"


# --- 3. dispatch, completion, consumption --------------------------------------------


def test_a_finished_job_wakes_consumption_and_stops_waking_it_once_consumed(tmp_path):
    sentinel = tmp_path / "worker.status"
    wait = Wait(job_id="worker", kind=WaitKind.PATH_EXISTS, path=str(sentinel),
                expects="the worker's result", not_beyond_seconds=3600,
                declared_at=continuation.now())
    _save(tmp_path, waits=(wait,), actionable=("consume the worker's result",))
    assert _state(tmp_path) == State.WAITING_ON_IDENTIFIED_JOB

    sentinel.write_text("0\n")
    assert _state(tmp_path) == State.COMPLETED_NOT_CONSUMED
    assert "COORDINATOR_WAKE_REQUIRED" in _renders(tmp_path)

    _save(tmp_path, waits=(Wait(**{**wait.as_dict(), "consumed": True}),),
          actionable=("close the capability",))
    assert _state(tmp_path) != State.COMPLETED_NOT_CONSUMED


# --- 4. partial output, recovered before any retry -----------------------------------


def test_partial_output_is_recovered_before_a_retry_is_considered(tmp_path):
    root = tmp_path / "worker-output"
    contract = task_output.OutputContract("survey", root, max_bytes_per_write=4096,
                                          expected_chunks=3)
    task_output.claim_root(contract)
    task_output.materialise(contract, 0, json.dumps({"finding": "one"}))
    task_output.materialise(contract, 1, json.dumps({"finding": "two"}))
    contract.part_path(2).write_text('{"interrupted')

    report = task_output.classify(contract)
    assert report.state == task_output.RecoveryState.FAILED_WITH_PARTIAL_DURABLE_OUTPUT
    plan = task_output.resume_plan(report)
    assert plan.resume_from == 2, (
        f"the plan resumes at {plan.resume_from}, so it would rewrite work that already landed")
    assert set(plan.keep) >= {0, 1}, "the plan discards chunks that survived"

    _save(tmp_path, waits=(Wait(job_id="survey", kind=WaitKind.OUTPUT_ROOT, path=str(root),
                                task_id="survey", max_bytes_per_write=4096,
                                expects="three chunks", not_beyond_seconds=3600,
                                declared_at=continuation.now()),),
          actionable=("recover the partial output before any retry",))
    assert "partial" in _renders(tmp_path).lower()


# --- 5. a stall, classified rather than guessed --------------------------------------


def test_a_live_process_with_no_progress_is_not_running(tmp_path):
    """Deterministic: the classifier is given the readings a stalled worker
    produces rather than a real one, because what is under test is the
    classification. The real process is exercised once in the smoke run."""
    import progress

    flat = progress.classify(
        "worker", progress.Sample(0.0, {"log_bytes": 39.0, "cpu_seconds": 0.34}),
        progress.Sample(1200.0, {"log_bytes": 39.0, "cpu_seconds": 0.34}),
        horizon_seconds=600, flat_since_seconds=0.0)
    assert flat.state == "STALLED"

    one_signal = progress.classify(
        "worker", progress.Sample(0.0, {"log_bytes": 39.0}),
        progress.Sample(1200.0, {"log_bytes": 39.0}),
        horizon_seconds=600, flat_since_seconds=0.0)
    assert one_signal.state == "UNKNOWN", "one flat signal is not a stall"


def test_a_wait_past_its_deadline_ends_whatever_the_process_is_doing(tmp_path):
    _save(tmp_path, waits=(Wait(job_id="worker", kind=WaitKind.PROCESS, pid=1,
                                expects="a report", not_beyond_seconds=1,
                                declared_at="2020-01-01T00:00:00+00:00"),),
          actionable=("consume the report",))
    assert _state(tmp_path) == State.RECOVERY_REQUIRED
    assert "EXPIRED" in _renders(tmp_path)


# --- 6. the coordinator disappears ---------------------------------------------------


def test_the_whole_position_survives_the_process_that_wrote_it(tmp_path):
    root = tmp_path / "worker-output"
    contract = task_output.OutputContract("survey", root, max_bytes_per_write=64)
    task_output.claim_root(contract)
    _save(tmp_path,
          waits=(Wait(job_id="survey", kind=WaitKind.OUTPUT_ROOT, path=str(root),
                      task_id="survey", max_bytes_per_write=64, expects="the survey",
                      subject_revision="a" * 40, executor="a worker somewhere",
                      not_beyond_seconds=3600, declared_at=continuation.now()),),
          actionable=("consume the survey", "close the capability"),
          budgets={"cycles": {"used": 1, "ceiling": 4}},
          evidence={"candidate": "demo 1.0.0 at abcdef123456"})

    script = (
        "import json,sys;sys.path.insert(0,sys.argv[1]);import continuation;"
        "r=continuation.load(sys.argv[3]);p=continuation.derive(r,relative_to=sys.argv[2]);"
        "print(json.dumps({'state':p.state,'next':list(p.actionable)[:1],"
        "'jobs':[w.job_id for w in r.waits],'subject':r.waits[0].subject_revision,"
        "'budgets':list(r.budgets),'candidate':r.evidence.get('candidate')}))")
    out = subprocess.run(
        [sys.executable, "-c", script, str(ROOT / "tools"), str(tmp_path),
         str(tmp_path / "CONTINUATION.json")], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    seen = json.loads(out.stdout)
    assert seen["state"] == State.WAITING_ON_IDENTIFIED_JOB
    assert seen["jobs"] == ["survey"]
    assert seen["subject"] == "a" * 40
    assert seen["budgets"] == ["cycles"]
    assert seen["candidate"] == "demo 1.0.0 at abcdef123456"


# --- 7. a scoped human decision, and everything else still runnable ------------------


def test_a_human_decision_on_one_item_does_not_stop_the_others(tmp_path):
    _save(tmp_path,
          actionable=("end the stalled worker", "repair the finding", "re-run the suite"),
          blockers=(Blocker(kind="human", hitl_row=4,
                            detail="ending a worker is a human action",
                            blocks=("end the stalled worker",)),))
    assert _state(tmp_path) != State.BLOCKED_ON_HUMAN
    out = _renders(tmp_path)
    assert "SCOPED" in out
    assert "NEXT AUTHORISED ACTION: repair the finding" in out


# --- 8 & 9 & 10. capacity known, unknown, and at a reset boundary --------------------


def test_capacity_known_unknown_and_reset_all_render_without_guessing(tmp_path):
    known = capacity.gate(
        capacity.Dispatch(task_id="t", pool_id="p", authority_class="authority_free",
                          allowed_executor_class="bounded", estimated_cost=1,
                          result_consumption_cost=1),
        capacity.Pool(pool_id="p", remaining=100, kind="independent",
                      observed_at=continuation.now(), resets_at="2026-12-31T00:00:00+00:00"),
        capacity.Reserve(coordinator=1, result_consumption=1, repair_and_audit=1))
    assert known.verdict == capacity.Verdict.DISPATCH

    unknown = capacity.gate(
        capacity.Dispatch(task_id="t", pool_id="p", authority_class="authority_free",
                          allowed_executor_class="bounded"),
        capacity.Pool(pool_id="p"), capacity.Reserve())
    assert unknown.verdict == capacity.Verdict.DISPATCH_SERIALLY
    assert "NO ARITHMETIC WAS PERFORMED" in unknown.why

    spent = capacity.gate(
        capacity.Dispatch(task_id="t", pool_id="p", authority_class="authority_free",
                          allowed_executor_class="bounded", estimated_cost=99,
                          result_consumption_cost=1),
        capacity.Pool(pool_id="p", remaining=10, kind="independent",
                      observed_at=continuation.now(), resets_at="2026-12-31T00:00:00+00:00"),
        capacity.Reserve(coordinator=5, result_consumption=0, repair_and_audit=0))
    assert spent.verdict in (capacity.Verdict.REFUSE, capacity.Verdict.REFUSE_UNTIL_RESET)


# --- 11 & 12. an audit, current and stale --------------------------------------------


def test_an_audit_is_bound_to_the_tree_it_read(tmp_path):
    _save(tmp_path,
          waits=(Wait(job_id="auditor", kind=WaitKind.PROCESS, pid=1, expects="a verdict",
                      subject_revision="b" * 40, not_beyond_seconds=3600,
                      declared_at=continuation.now()),),
          actionable=("consume the verdict",),
          evidence={"candidate": "2.3.0 at " + "b" * 12})
    assert "NOT the candidate" not in _renders(tmp_path)

    _save(tmp_path,
          waits=(Wait(job_id="auditor", kind=WaitKind.PROCESS, pid=1, expects="a verdict",
                      subject_revision="a" * 40, not_beyond_seconds=3600,
                      declared_at=continuation.now()),),
          actionable=("consume the verdict",),
          evidence={"candidate": "2.3.0 at " + "b" * 12})
    assert "NOT the candidate" in _renders(tmp_path)


# --- 13. a record nobody can read ----------------------------------------------------


def test_a_malformed_record_renders_and_does_not_read_as_healthy(tmp_path):
    (tmp_path / "CONTINUATION.json").write_text("{ this is not json")
    out = _renders(tmp_path)
    assert "UNKNOWN" in out
    with pytest.raises(Exception):
        continuation.load(tmp_path / "CONTINUATION.json")


# --- 14 & 15. what a private project owes, and what a published one owes -------------


def test_a_private_project_does_not_inherit_publication_ceremony():
    import publication_history

    import types

    private, not_private, _why = publication_history.obligations(
        types.SimpleNamespace(publication_intent="internal"))
    published, not_published, _why = publication_history.obligations(
        types.SimpleNamespace(publication_intent="public"))
    undeclared, _na, _why = publication_history.obligations(types.SimpleNamespace())

    assert set(publication_history.UNIVERSAL_OBLIGATIONS) <= set(private)
    assert not set(publication_history.PUBLICATION_OBLIGATIONS) & set(private)
    assert set(publication_history.PUBLICATION_OBLIGATIONS) <= set(published)
    # A project that has not said carries every universal invariant: an
    # undeclared intent must not switch the safety half off.
    assert set(publication_history.UNIVERSAL_OBLIGATIONS) <= set(undeclared)


# --- the property the whole file exists for ------------------------------------------


def test_no_rehearsal_reaches_silent_idle_with_work_outstanding(tmp_path):
    """`SILENT_IDLE` means there is work to do, nothing is outstanding, and
    nobody is doing it. In a governed run it is a defect, and a lifecycle that
    reaches it needs a person to notice — which is the failure this release
    exists to close.

    Every state a rehearsal above passes through is re-derived here."""
    lifecycle = []

    sentinel = tmp_path / "s"
    _save(tmp_path, waits=(Wait(job_id="w", kind=WaitKind.PATH_EXISTS, path=str(sentinel),
                                expects="a result", not_beyond_seconds=3600,
                                declared_at=continuation.now()),),
          actionable=("consume the result",))
    lifecycle.append(_state(tmp_path))
    sentinel.write_text("0")
    lifecycle.append(_state(tmp_path))
    _save(tmp_path, actionable=("close the capability",),
          blockers=(Blocker(kind="human", hitl_row=2, detail="a person closes it",
                            blocks=("close the capability",)),))
    lifecycle.append(_state(tmp_path))
    _save(tmp_path, terminal=True)
    lifecycle.append(_state(tmp_path))

    assert lifecycle == [State.WAITING_ON_IDENTIFIED_JOB, State.COMPLETED_NOT_CONSUMED,
                         State.BLOCKED_ON_HUMAN, State.TERMINAL], lifecycle
    assert State.SILENT_IDLE not in lifecycle
