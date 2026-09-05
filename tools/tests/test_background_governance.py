"""One governed waiting path, attacked.

Every test here is a situation this session actually produced or a neighbouring
one it could have. The headline case is real: three monitors ran for about an
hour against producers that had exited and whose results had already been read,
because each monitor's `pgrep` pattern was inside the monitor's own command
line.
"""

import subprocess
import sys
from pathlib import Path

import pytest

import continuation
import progress
from continuation import ContinuationRecord, Disposition, Wait, WaitKind

PACK_TOOLS = Path(__file__).resolve().parent.parent

#: Verbatim, from this session's own process table.
THE_MONITORS_THIS_SESSION_RAN = (
    'while pgrep -qf "pytest tools/tests" || pgrep -qf "codex exec"; do sleep 20; done;'
    ' echo "SUITE:"; tail -6 /tmp/out',
    'while pgrep -qf "pytest tools/tests"; do sleep 20; done; tail -8 /tmp/out',
    'while pgrep -qf "codex exec"; do sleep 20; done; echo done',
    'while pgrep -f "pytest tools/tests" >/dev/null; do sleep 10; done',
)


def _zombie():
    """A real unreaped child, which is what `os.kill(pid, 0)` gets wrong."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    for _ in range(400):
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(child.pid)],
                               capture_output=True, text=True).stdout.strip()
        if state.startswith("Z") or not state:
            break
    return child


# --- O1: a zombie producer is ended, in both modules -------------------------


def test_zombie_producer_is_finished_not_running():
    child = _zombie()
    try:
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(child.pid)],
                               capture_output=True, text=True).stdout.strip()
        if not state.startswith("Z"):
            pytest.skip("the child was reaped before it could be observed as a zombie")
        finished, how = progress.process_has_ended(child.pid)
        assert finished, f"a zombie producer read as running: {how}"
        assert "not been reaped" in how
    finally:
        child.wait()


def test_zombie_the_continuation_model_gives_the_same_answer_as_the_waiter():
    """One question, one answer. The two disagreed: `waiter_command` treated a
    zombie as ended and `_process_is_gone` asked `os.kill(pid, 0)`, which
    succeeds for one — so the DURABLE state model held the wrong answer."""
    child = _zombie()
    try:
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(child.pid)],
                               capture_output=True, text=True).stdout.strip()
        if not state.startswith("Z"):
            pytest.skip("the child was reaped before it could be observed as a zombie")
        assert continuation._process_is_gone(child.pid) == \
            progress.process_has_ended(child.pid)
        assert continuation._process_is_gone(child.pid)[0] is True
    finally:
        child.wait()


def test_a_running_process_is_not_reported_as_finished():
    """The bound in the other direction: a guard that says everything is
    finished is as useless as one that says nothing is."""
    finished, how = progress.process_has_ended(__import__("os").getpid())
    assert not finished and "running" in how


# --- O2: a waiter that greps a command line cannot be trusted ---------------


@pytest.mark.parametrize("command", THE_MONITORS_THIS_SESSION_RAN)
def test_self_matching_monitors_this_session_ran_are_refused(command):
    problems = progress.waiter_problems(command)
    assert problems, f"a monitor that cannot terminate was accepted: {command[:60]}"
    assert any("COMMAND LINE" in problem for problem in problems)
    assert not progress.is_governed_waiter(command)


def test_self_matching_is_refused_as_a_class_not_pattern_by_pattern():
    """Including a pattern that happens NOT to appear in the command, because
    deciding which patterns are safe is an argument, and the argument is what
    produced three monitors that could never end."""
    assert not progress.is_governed_waiter('while pgrep -qf "something-else"; do sleep 1; done')
    assert not progress.is_governed_waiter("ps aux | grep worker")
    assert not progress.is_governed_waiter("pkill -f worker")


def test_the_shipped_builder_produces_a_governed_waiter():
    command = progress.waiter_command("run", 12345, sentinel="/tmp/report.md")
    assert progress.is_governed_waiter(command)
    assert progress.waiter_problems(command) == ()


def test_a_waiter_observing_nothing_is_refused():
    assert not progress.is_governed_waiter("sleep 600")
    assert any("neither a process state nor a completion artifact" in problem
               for problem in progress.waiter_problems("sleep 600"))
    assert any("not stated" in problem for problem in progress.waiter_problems(""))


# --- O3: refused where the wait is declared ---------------------------------


@pytest.mark.parametrize("command", THE_MONITORS_THIS_SESSION_RAN)
def test_refused_at_declaration_rather_than_reported_afterwards(command):
    """A check that runs later describes a wait already entered, and the wait
    that could not end is the one nobody looked at again."""
    with pytest.raises(Exception) as caught:
        Wait(job_id="j", kind=WaitKind.HUMAN, expects="x", waiter=command)
    assert "cannot be trusted to end" in str(caught.value)


def test_refused_at_declaration_survives_the_durable_boundary(tmp_path):
    """And a record on disk cannot smuggle one back in through `load`."""
    import json

    path = tmp_path / "CONTINUATION.json"
    good = Wait(job_id="j", kind=WaitKind.HUMAN, expects="x",
                waiter=" ".join(progress.waiter_command("r", 1, sentinel="/tmp/s")))
    continuation.save(ContinuationRecord(capability="C", updated_at=continuation.now(),
                                         waits=(good,)), path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["waits"][0]["waiter"] = THE_MONITORS_THIS_SESSION_RAN[0]
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(Exception):
        continuation.load(path)


def test_a_wait_with_no_waiter_is_allowed_and_named(tmp_path):
    """Empty is a GAP a reader can see, not a waiter the pack has approved."""
    wait = Wait(job_id="j", kind=WaitKind.PATH_EXISTS, expects="a report",
                path=str(tmp_path / "r.md"), not_beyond_seconds=60,
                declared_at=continuation.now())
    record = ContinuationRecord(capability="C", updated_at=continuation.now(), waits=(wait,))
    named = continuation.ungoverned_waits(record)
    assert named and "UNGOVERNED_BACKGROUND_WORK" in named[0]


# --- O4/O5/O6: the eight dispositions ---------------------------------------


def _record(*waits):
    return ContinuationRecord(capability="C1", updated_at=continuation.now(), waits=waits)


def _path_wait(tmp_path, job_id="j", **kwargs):
    fields = dict(job_id=job_id, kind=WaitKind.PATH_EXISTS, expects="a report",
                  path=str(tmp_path / f"{job_id}.md"), not_beyond_seconds=600,
                  declared_at=continuation.now())
    fields.update(kwargs)
    return Wait(**fields)


def test_disposition_live_and_progressing(tmp_path):
    result = continuation.reconcile(_record(_path_wait(tmp_path)), relative_to=tmp_path)
    assert result[0].disposition == Disposition.LIVE_AND_PROGRESSING
    assert result[0].blocks


def test_disposition_live_but_stalled(tmp_path):
    wait = _path_wait(tmp_path, not_beyond_seconds=1, declared_at="2020-01-01T00:00:00Z")
    result = continuation.reconcile(_record(wait), relative_to=tmp_path)
    assert result[0].disposition == Disposition.LIVE_BUT_STALLED


def test_disposition_completed_unconsumed(tmp_path):
    (tmp_path / "j.md").write_text("a report", encoding="utf-8")
    result = continuation.reconcile(_record(_path_wait(tmp_path)), relative_to=tmp_path)
    assert result[0].disposition == Disposition.COMPLETED_UNCONSUMED
    assert result[0].blocks


def test_disposition_completed_consumed(tmp_path):
    (tmp_path / "j.md").write_text("a report", encoding="utf-8")
    result = continuation.reconcile(_record(_path_wait(tmp_path, retired=True)),
                                    relative_to=tmp_path)
    assert result[0].disposition == Disposition.COMPLETED_CONSUMED
    assert not result[0].blocks


def test_disposition_orphaned_waiter(tmp_path):
    """This session's own shape: the producer finished, the result was read, and
    the wait was still declared."""
    (tmp_path / "j.md").write_text("a report", encoding="utf-8")
    result = continuation.reconcile(_record(_path_wait(tmp_path, consumed=True)),
                                    relative_to=tmp_path)
    assert result[0].disposition == Disposition.ORPHANED_WAITER
    assert not result[0].blocks, "a finished, consumed job held the candidate open"
    assert result[0].action == "retire the wait"
    assert "already happened" in result[0].why


def test_disposition_superseded_cannot_block_the_candidate(tmp_path):
    wait = _path_wait(tmp_path, subject_revision="a" * 40)
    result = continuation.reconcile(_record(wait), relative_to=tmp_path,
                                    candidate_revision="b" * 40)
    assert result[0].disposition == Disposition.SUPERSEDED
    assert not result[0].blocks
    assert "must not be re-run" in result[0].why


def test_disposition_superseded_needs_both_revisions_to_be_known(tmp_path):
    """Absence is not agreement: a wait naming no subject is not 'current'."""
    result = continuation.reconcile(_record(_path_wait(tmp_path)), relative_to=tmp_path,
                                    candidate_revision="b" * 40)
    assert result[0].disposition != Disposition.SUPERSEDED


def test_disposition_zombie(tmp_path):
    child = _zombie()
    try:
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(child.pid)],
                               capture_output=True, text=True).stdout.strip()
        if not state.startswith("Z"):
            pytest.skip("the child was reaped before it could be observed as a zombie")
        wait = Wait(job_id="z", kind=WaitKind.PROCESS, expects="a run", pid=child.pid,
                    not_beyond_seconds=600, declared_at=continuation.now())
        result = continuation.reconcile(_record(wait), relative_to=tmp_path)
        assert result[0].disposition == Disposition.ZOMBIE
        assert "ENDED" in result[0].why
    finally:
        child.wait()


def test_disposition_unknown_is_never_rendered_as_a_settled_one(tmp_path):
    wait = Wait(job_id="h", kind=WaitKind.HUMAN, expects="a decision")
    result = continuation.reconcile(_record(wait), relative_to=tmp_path)
    assert result[0].disposition == Disposition.UNKNOWN
    assert result[0].blocks


def test_every_disposition_is_reachable_and_named():
    assert len(Disposition.ALL) == 8
    assert set(Disposition.SETTLED) < set(Disposition.ALL)


# --- O5: a monitor is not an input ------------------------------------------


def test_monitor_is_not_evidence_that_anything_is_running(tmp_path):
    """The inversion that produced the incident: a job is running because its
    PRODUCER is running, never because something watching it still exists."""
    (tmp_path / "j.md").write_text("a report", encoding="utf-8")
    watcher = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        wait = _path_wait(tmp_path, consumed=True,
                          waiter=" ".join(progress.waiter_command(
                              "r", watcher.pid, sentinel=str(tmp_path / "j.md"))))
        result = continuation.reconcile(_record(wait), relative_to=tmp_path)
        assert result[0].disposition == Disposition.ORPHANED_WAITER, (
            "a live monitor made a finished producer read as running"
        )
    finally:
        watcher.kill()
        watcher.wait()


# --- O7: cold reconstruction -------------------------------------------------


def test_cold_reconstruction_from_disk_alone_produces_no_phantom_work(tmp_path):
    """A fresh process, reading only the record, reaches the same dispositions
    and reports nothing outstanding that is not really outstanding."""
    import json

    (tmp_path / "j.md").write_text("a report", encoding="utf-8")
    path = tmp_path / "CONTINUATION.json"
    continuation.save(_record(_path_wait(tmp_path, consumed=True)), path)

    read = subprocess.run(
        [sys.executable, "-c",
         "import sys, json; sys.path.insert(0, sys.argv[1]); import continuation;"
         "r = continuation.load(sys.argv[2]);"
         "print(json.dumps([(x.job_id, x.disposition, x.blocks) for x in"
         " continuation.reconcile(r, relative_to=sys.argv[3])]))",
         str(PACK_TOOLS), str(path), str(tmp_path)],
        capture_output=True, text=True, check=True, timeout=120)
    cold = json.loads(read.stdout)
    assert cold == [["j", Disposition.ORPHANED_WAITER, False]]
    assert not any(blocks for _job, _disposition, blocks in cold), (
        "cold reconstruction reported phantom outstanding work"
    )


def test_reconciliation_signals_nothing_and_ends_nothing(tmp_path):
    """It reports. Ending a worker is a human decision (hitl row 4) and this
    does not touch it."""
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        wait = Wait(job_id="p", kind=WaitKind.PROCESS, expects="a run", pid=child.pid,
                    not_beyond_seconds=600, declared_at=continuation.now())
        continuation.reconcile(_record(wait), relative_to=tmp_path)
        assert child.poll() is None, "reconciliation ended a running producer"
    finally:
        child.kill()
        child.wait()
