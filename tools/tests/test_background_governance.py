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
    # The refusal is now one sentence for every ungoverned shape, because
    # governance is decided by reconstruction rather than by naming what is
    # wrong. The message points at the builder, which is the actionable part.
    assert any("waiter_command" in problem for problem in problems)
    assert not progress.is_governed_waiter(command)


def test_self_matching_is_refused_as_a_class_not_pattern_by_pattern():
    """Including patterns that happen NOT to appear in the command, and
    including shapes no denylist would have enumerated. Deciding which patterns
    are safe is an argument, and the argument produced three monitors that could
    never end — and then let two more past the list that replaced it."""
    for command in ('while pgrep -qf "something-else"; do sleep 1; done',
                    "ps aux | grep worker", "pkill -f worker",
                    "ps -ax -o command= | grep worker", "pidof worker",
                    "while true; do sleep 1; done"):
        assert not progress.is_governed_waiter(command), command


def test_the_shipped_builder_produces_a_governed_waiter():
    command = progress.waiter_command("run", 12345, sentinel="/tmp/report.md")
    assert progress.is_governed_waiter(command)
    assert progress.waiter_problems(command) == ()
    # AND THE PROPERTY, not only the round trip. An independent reader pointed
    # out that asserting `waiter_problems(waiter_command(...)) == ()` checks the
    # module against itself; these are facts about the command that would hold
    # however it had been produced.
    text = " ".join(command)
    assert "12345" in text, "the waiter does not name the process it watches"
    assert "/tmp/report.md" in text, "the waiter does not name the artifact"
    for matcher in ("pgrep", "pkill", "grep", "pidof", "ps ax", "ps aux", "ps -ef"):
        assert matcher not in text, f"the built waiter searches a command line ({matcher})"


def test_a_waiter_observing_nothing_is_refused():
    assert not progress.is_governed_waiter("sleep 600")
    assert progress.waiter_problems("sleep 600")
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
    # A REAL PRODUCER WAIT, because a waiter must now watch the wait it belongs
    # to — a person is not a producer and a human wait may carry no waiter.
    report = tmp_path / "r.md"
    good = Wait(job_id="j", kind=WaitKind.PATH_EXISTS, expects="a report", path=str(report),
                not_beyond_seconds=600, declared_at=continuation.now(),
                waiter=" ".join(progress.waiter_command("r", 1, sentinel=str(report))))
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


def test_the_disposition_vocabulary_is_the_eight_this_release_promised():
    """A VOCABULARY check, and named as one. It used to be called a reachability
    test and passed against a `reconcile` mutated to return nothing at all —
    an independent reader demonstrated exactly that. Reachability is
    `test_every_disposition_is_reachable_through_reconciliation`.
    """
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


# =============================================================================
# What an independent reading of the delta walked past the first version
# =============================================================================


#: Waiters that CANNOT terminate, or that search a command line, and that the
#: first denylist accepted. Verbatim from the reading that found them.
UNGOVERNED_THAT_GOT_PAST_THE_DENYLIST = (
    # Observes an artifact that is always there, so the loop is endless.
    "while [ -e / ]; do sleep 1; done",
    # A `ps` spelling the list did not hold, with a comment satisfying the
    # positive check.
    'while ps -ax -o command= | grep -q "pytest tools/tests"; do sleep 1; done # [ -e / ]',
    # Well-formed shape, wrong grammar.
    "sh -c while true; do sleep 1; done",
    # The right grammar with a value nothing could have produced.
    'sh -c while s=$(ps -o stat= -p 0 2>/dev/null); [ -n "$s" ]; do sleep 1; done',
)


@pytest.mark.parametrize("command", UNGOVERNED_THAT_GOT_PAST_THE_DENYLIST)
def test_self_matching_only_a_waiter_this_module_built_is_governed(command):
    """Governance is decided by RECONSTRUCTION, not by a list of bad shapes.

    A denylist has to enumerate every way to be wrong, and an independent reader
    walked two past it: a `ps | grep` spelling the list did not hold, and a loop
    that observed nothing and so could not terminate at all. The design record
    already said *refused as a class rather than pattern by pattern*; the
    implementation did not match it.
    """
    assert progress.waiter_problems(command), f"an ungoverned waiter was accepted: {command[:70]}"
    assert not progress.is_governed_waiter(command)


def test_self_matching_the_builders_own_output_reconstructs_to_itself():
    """The bound in the other direction: a rule that refuses everything is as
    useless as one that refuses nothing."""
    for pid, sentinel, poll in ((1, "/tmp/a", 20), (4242, "/tmp/with space/r.md", 1),
                                (999999, "/tmp/r", 3600)):
        command = progress.waiter_command("r", pid, sentinel=sentinel, poll_seconds=poll)
        assert progress.is_governed_waiter(command), (command, sentinel)
        assert progress.waiter_watches(command) == (pid, sentinel)


def test_a_governed_waiter_says_which_producer_it_watches():
    """So a caller can check it watches the one its wait names — a governed
    waiter over somebody else's process is well-formed and wrong."""
    command = progress.waiter_command("r", 4242, sentinel="/tmp/r.md")
    assert progress.waiter_watches(command) == (4242, "/tmp/r.md")
    assert progress.waiter_watches("while true; do :; done") == (None, "")


# --- a failed query is not an absent process ---------------------------------


def test_a_process_table_that_cannot_be_read_is_unknown_not_finished():
    """`ps` exits 1 for a number that is gone and non-zero for reasons that have
    nothing to do with the process. Reading the second as the first reports a
    RUNNING producer as finished, which is the direction that loses work — found
    from inside a sandbox where `ps` was denied."""
    from unittest.mock import patch

    denied = subprocess.CompletedProcess([], 2, "", "ps: permission denied")
    with patch("subprocess.run", return_value=denied):
        finished, how = progress.process_has_ended(12345)
    assert finished is None, "a denied process table read as an absent process"
    assert "could not be read" in how


def test_an_unreadable_process_table_makes_the_wait_unobservable(tmp_path):
    from unittest.mock import patch

    wait = Wait(job_id="p", kind=WaitKind.PROCESS, expects="a run", pid=4242,
                not_beyond_seconds=600, declared_at=continuation.now())
    denied = subprocess.CompletedProcess([], 2, "", "ps: permission denied")
    with patch("subprocess.run", return_value=denied):
        result = continuation.reconcile(_record(wait), relative_to=tmp_path)
    assert result[0].disposition == Disposition.UNKNOWN


# --- retirement settles before anything transient is observed ----------------


def test_disposition_a_retired_wait_stays_settled_when_its_artifact_disappears(tmp_path):
    """It was decided inside the `finished` branch, so a retired wait whose
    artifact had since been removed fell through to a live disposition and
    started blocking again — while `derive` excludes retired waits entirely."""
    result = continuation.reconcile(
        _record(_path_wait(tmp_path, retired=True, consumed=True)), relative_to=tmp_path)
    assert result[0].disposition == Disposition.COMPLETED_CONSUMED
    assert not result[0].blocks
    assert "holds no obligation" in result[0].why


# --- absence is not agreement ------------------------------------------------


def test_disposition_a_wait_naming_no_subject_is_unknown_against_a_candidate(tmp_path):
    """The failure-mode table said UNKNOWN and the code fell through to a
    positive live answer. The previous test asserted only `!= SUPERSEDED`, which
    passed against exactly that."""
    result = continuation.reconcile(_record(_path_wait(tmp_path)), relative_to=tmp_path,
                                    candidate_revision="b" * 40)
    assert result[0].disposition == Disposition.UNKNOWN
    assert result[0].blocks
    assert "not the same as it being about this one" in result[0].why


def test_disposition_no_candidate_asked_means_no_comparison_is_owed(tmp_path):
    """The bound: a caller that asks about no candidate is not owed an UNKNOWN
    for every job."""
    result = continuation.reconcile(_record(_path_wait(tmp_path)), relative_to=tmp_path)
    assert result[0].disposition == Disposition.LIVE_AND_PROGRESSING


# --- a recorded producer that has ended outranks an absent artifact ----------


def test_disposition_a_producer_that_exited_is_not_reported_as_running(tmp_path):
    """`_observe` chooses by wait KIND, so a path wait carrying a process number
    never consulted it — and a producer demonstrably exited, with no result,
    reported as running. Against a real exited child."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    result = continuation.reconcile(
        _record(_path_wait(tmp_path, pid=child.pid)), relative_to=tmp_path)
    assert result[0].disposition == Disposition.UNKNOWN
    assert result[0].blocks
    assert "has ended" in result[0].why


def test_disposition_a_live_producer_with_a_pending_artifact_is_still_live(tmp_path):
    """The other direction, so the rule above cannot be satisfied by calling
    everything unknown."""
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        result = continuation.reconcile(
            _record(_path_wait(tmp_path, pid=child.pid)), relative_to=tmp_path)
        assert result[0].disposition == Disposition.LIVE_AND_PROGRESSING
    finally:
        child.kill()
        child.wait()


# --- the panel asks with the candidate it already has ------------------------


def test_the_background_panel_passes_the_records_own_candidate(tmp_path):
    """Without it every superseded job read as holding the capability open —
    the panel asking a question it already had the answer to."""
    import projection

    record = ContinuationRecord(
        capability="C", updated_at=continuation.now(),
        waits=(_path_wait(tmp_path, subject_revision="a" * 40),),
        evidence={"candidate": "b" * 40})
    panel = projection._background_panel(record, tmp_path)
    rendered = panel.render()
    assert Disposition.SUPERSEDED in rendered
    assert "0 holding the capability open" in rendered


def test_every_disposition_is_reachable_through_reconciliation(tmp_path):
    """A REACHABILITY oracle, not a vocabulary one.

    The previous test asserted `len(Disposition.ALL) == 8` and passed against a
    `reconcile` mutated to return nothing at all — an independent reader
    demonstrated exactly that. This drives the function.
    """
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    (tmp_path / "done.md").write_text("a report", encoding="utf-8")

    seen = set()
    cases = [
        (_record(_path_wait(tmp_path)), {}),
        (_record(_path_wait(tmp_path, not_beyond_seconds=1,
                            declared_at="2020-01-01T00:00:00Z")), {}),
        (_record(_path_wait(tmp_path, job_id="done")), {}),
        (_record(_path_wait(tmp_path, job_id="done", consumed=True)), {}),
        (_record(_path_wait(tmp_path, retired=True)), {}),
        (_record(_path_wait(tmp_path, subject_revision="a" * 40)),
         {"candidate_revision": "b" * 40}),
        (_record(Wait(job_id="h", kind=WaitKind.HUMAN, expects="a decision")), {}),
    ]
    for record, kwargs in cases:
        seen.update(item.disposition for item in
                    continuation.reconcile(record, relative_to=tmp_path, **kwargs))

    expected = set(Disposition.ALL) - {Disposition.ZOMBIE}
    assert expected <= seen, f"never reached: {sorted(expected - seen)}"


# =============================================================================
# What the second delta reading found, including a guarantee with no oracle
# =============================================================================


def test_monitor_is_not_evidence_the_panel_renders_what_reconciliation_says(tmp_path):
    """GUARANTEE 10, which had no oracle at all.

    An independent reader replaced the panel's `reconcile` call with a tuple
    saying `LIVE_AND_PROGRESSING / "a monitor exists"` for every wait — the exact
    inversion the design says is closed — and **the whole suite passed**. The
    panel was entered 145 times across the run and nothing looked at what it
    said. This looks.
    """
    import projection

    watcher = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        record = _record(_path_wait(tmp_path, waiter=" ".join(
            progress.waiter_command("j", watcher.pid, sentinel=str(tmp_path / "j.md")))))
        # THE SENTINEL IS WRITTEN AFTER THE WAIT IS DECLARED, WHICH IS BOTH THE
        # REAL ORDER AND THE ONLY DETERMINISTIC ONE.
        #
        # `declared_at` is recorded truncated to whole seconds, so a sentinel
        # written just BEFORE the declaration compares as contemporaneous when the
        # two land in the same second and as predating it when they straddle the
        # boundary. Written first, this test asserted COMPLETED_UNCONSUMED and got
        # it by luck: an independent certification hit the other side of the
        # boundary and the suite failed once in a run that otherwise passed. A
        # coordinator declares a wait and the job then writes, so writing here in
        # that order is what the guarantee is actually about.
        (tmp_path / "j.md").write_text("a report", encoding="utf-8")
        rendered = projection._background_panel(record, tmp_path).render()

        # What reconciliation says, said by the panel.
        expected = continuation.reconcile(record, relative_to=tmp_path)[0]
        assert expected.disposition == Disposition.COMPLETED_UNCONSUMED
        assert expected.disposition in rendered
        assert expected.why in rendered
        assert f"the coordinator may: {expected.action}" in rendered
        # And NOT the thing a surviving monitor would make it say.
        assert Disposition.LIVE_AND_PROGRESSING not in rendered, (
            "a live monitor made the panel report its finished job as running"
        )
    finally:
        watcher.kill()
        watcher.wait()


def test_the_panel_says_what_reconciliation_says_for_every_disposition(tmp_path):
    """Stronger than one case: whatever reconciliation answers, the panel prints
    it. A panel that derived its own answer would diverge on some input."""
    import projection

    (tmp_path / "done.md").write_text("a report", encoding="utf-8")
    records = [
        _record(_path_wait(tmp_path)),
        _record(_path_wait(tmp_path, job_id="done")),
        _record(_path_wait(tmp_path, job_id="done", consumed=True)),
        _record(_path_wait(tmp_path, retired=True)),
        _record(_path_wait(tmp_path, not_beyond_seconds=1,
                           declared_at="2020-01-01T00:00:00Z")),
        _record(Wait(job_id="h", kind=WaitKind.HUMAN, expects="a decision")),
    ]
    for record in records:
        rendered = projection._background_panel(record, tmp_path).render()
        for item in continuation.reconcile(record, relative_to=tmp_path):
            assert item.disposition in rendered, (item.job_id, item.disposition)
            assert item.why in rendered


def test_blocks_is_derived_from_the_settled_set_and_not_set_by_hand():
    """`Disposition.SETTLED` was documented as the rule governing `blocks` and
    consulted by nothing; `blocks` was hand-set at eight construction sites, so
    the two could disagree."""
    for disposition in Disposition.ALL:
        item = continuation.Reconciliation("j", disposition, "why")
        assert item.blocks is (disposition not in Disposition.SETTLED), disposition
    assert set(Disposition.SETTLED) == {
        Disposition.COMPLETED_CONSUMED, Disposition.ORPHANED_WAITER, Disposition.SUPERSEDED}


def test_a_retired_wait_settles_whatever_its_producer_or_a_person_is_doing(tmp_path):
    """`derive` filters retired waits out entirely; `reconcile` consulted
    `retired` only inside its finished branch, so a retired wait with a RUNNING
    producer, and any retired HUMAN wait, went on blocking — and the two panels
    contradicted each other on one screen."""
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        running = Wait(job_id="r", kind=WaitKind.PROCESS, expects="a run", pid=child.pid,
                       not_beyond_seconds=600, declared_at=continuation.now(), retired=True)
        human = Wait(job_id="h", kind=WaitKind.HUMAN, expects="a decision", retired=True)
        for wait in (running, human):
            result = continuation.reconcile(_record(wait), relative_to=tmp_path)[0]
            assert result.disposition == Disposition.COMPLETED_CONSUMED, wait.job_id
            assert not result.blocks, wait.job_id
        # AND THE TWO MODELS AGREE. That is the property; the disposition is how.
        for wait in (running, human):
            derived = continuation.derive(_record(wait), relative_to=tmp_path)
            assert derived.state != continuation.State.RECOVERY_REQUIRED
            assert not any(item.blocks for item
                           in continuation.reconcile(_record(wait), relative_to=tmp_path))
    finally:
        child.kill()
        child.wait()


def test_a_wait_configuration_holds_text_and_not_a_nested_object():
    """An identity field is a string everywhere else, and a nested object
    round-trips through save/load into a consumer expecting text."""
    for bad in ({"surface": {"nested": 1}}, {"effort": ["a"]}, {"family": 3}):
        with pytest.raises(Exception) as caught:
            Wait(job_id="j", kind=WaitKind.HUMAN, expects="x", configuration=bad)
        assert "holds text" in str(caught.value)


def test_the_zombie_signal_is_a_shared_constant_not_matched_prose():
    """`continuation` recognised a zombie by searching another module's sentence
    for `has not been reaped`; rewording it there would have silently downgraded
    the disposition."""
    # `or True` was here, which the suite's own vacuity sweep caught: an
    # assertion joined to a truthy constant cannot fail. It was defensive noise
    # around a sentence whose wording is not the property; the property is that
    # `continuation` keys on the constant rather than on the prose.
    assert isinstance(progress.ENDED_UNREAPED, str) and progress.ENDED_UNREAPED.strip()
    source = (PACK_TOOLS / "continuation.py").read_text(encoding="utf-8")
    assert "ENDED_UNREAPED" in source
    assert '"has not been reaped"' not in source, (
        "the zombie disposition is keyed on prose again"
    )


# =============================================================================
# What a bounded reading of the repairs found in the repairs
# =============================================================================


def test_an_unaskable_producer_is_unknown_and_not_running(tmp_path):
    """`process_has_ended` gained a THIRD answer and `reconcile` read it as the
    second: `if ended:` treats `None` as `False`, so a producer nobody could ask
    about reported as running. This module's whole thesis is that an
    unanswerable question is never rendered as its reassuring answer, and the
    repair that introduced the third answer forgot to read it.
    """
    from unittest.mock import patch

    wait = _path_wait(tmp_path, pid=4242)
    denied = subprocess.CompletedProcess([], 2, "", "ps: permission denied")
    with patch("subprocess.run", return_value=denied):
        result = continuation.reconcile(_record(wait), relative_to=tmp_path)[0]
    assert result.disposition == Disposition.UNKNOWN
    assert result.blocks
    assert "cannot be asked about" in result.why


def test_a_pid_that_is_not_a_number_is_unknown_and_not_running(tmp_path):
    """The same hole through a different door: a record carrying `pid` as TEXT.

    The pid is deliberately carried rather than refused at construction — this
    module decided that against an earlier reader, because a saved record is
    untrusted input and must reach a STATE rather than a traceback. So the
    reconciliation is where it has to be closed.
    """
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    wait = _path_wait(tmp_path, pid=str(child.pid))
    result = continuation.reconcile(_record(wait), relative_to=tmp_path)[0]
    assert result.disposition == Disposition.UNKNOWN
    assert result.blocks


def test_a_waiter_must_watch_the_wait_it_is_recorded_against(tmp_path):
    """`waiter_watches` was added so a caller could check this, and then no
    caller did — so a perfectly reconstructed waiter over an unrelated
    long-lived process was recorded as governing this wait. The module's own
    docstring already said such a waiter is well-formed and wrong.
    """
    report = tmp_path / "r.md"
    unrelated = " ".join(progress.waiter_command("r", 1, sentinel="/unrelated-sentinel"))
    assert progress.is_governed_waiter(unrelated), "the fixture must be governed in itself"

    # The detail is in the refusal's `detail`, not its headline — the headline
    # is one sentence for every ungoverned waiter and would pass whatever the
    # reason was.
    with pytest.raises(Exception) as caught:
        Wait(job_id="p", kind=WaitKind.PROCESS, expects="a run", pid=999999,
             not_beyond_seconds=600, declared_at=continuation.now(), waiter=unrelated)
    assert "watches process 1" in caught.value.detail["why"]

    with pytest.raises(Exception) as caught:
        Wait(job_id="j", kind=WaitKind.PATH_EXISTS, expects="a report", path=str(report),
             not_beyond_seconds=600, declared_at=continuation.now(), waiter=unrelated)
    assert "unrelated-sentinel" in caught.value.detail["why"]

    # AND THE MATCHING ONE IS ACCEPTED, so the rule is not "refuse everything".
    matching = " ".join(progress.waiter_command("r", 999999, sentinel=str(report)))
    Wait(job_id="p", kind=WaitKind.PROCESS, expects="a run", pid=999999,
         not_beyond_seconds=600, declared_at=continuation.now(), waiter=matching)
    Wait(job_id="j", kind=WaitKind.PATH_EXISTS, expects="a report", path=str(report),
         not_beyond_seconds=600, declared_at=continuation.now(), waiter=matching)


def test_a_person_is_not_a_producer_and_carries_no_waiter():
    with pytest.raises(Exception) as caught:
        Wait(job_id="h", kind=WaitKind.HUMAN, expects="a decision",
             waiter=" ".join(progress.waiter_command("r", 1, sentinel="/tmp/s")))
    assert "a person is not a producer" in caught.value.detail["why"]
