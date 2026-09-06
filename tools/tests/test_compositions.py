"""Pairs of mechanisms that are each correct alone.

Every module here has its own tests and passes them. This file is about what
happens where two of them meet — because that is where this release's recorded
failures actually happened: a scoped human decision met unrelated authorised
work and stopped it; an audit's verdict met a candidate that had moved and
looked current; a completion marker met a restart and the result was consumed
twice.

**A composition test earns its place by reaching a branch neither part reaches
alone.** Repeating one module's fixture with another module's literals is not a
composition, and this file would be longer and worth less.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import capacity
import continuation
import gitread
import projection
import task_output
from continuation import Blocker, ContinuationRecord, State, Wait, WaitKind

ROOT = Path(__file__).resolve().parents[2]


def _save(root: Path, **fields):
    fields.setdefault("capability", "C1 — a capability")
    fields.setdefault("updated_at", continuation.now())
    continuation.save(ContinuationRecord(**fields), root / "CONTINUATION.json")
    return root / "CONTINUATION.json"


def _derive(root: Path):
    return continuation.derive(continuation.load(root / "CONTINUATION.json"), relative_to=root)


# --- stale evidence meets a coordinator restart ---------------------------------------


def test_a_restart_does_not_make_an_audit_of_an_older_tree_look_current(tmp_path):
    """Two correct mechanisms: derivation recomputes from artifacts on every
    read, and an audit declares the revision it is about. Composed, the
    dangerous reading is *the coordinator restarted, so its evidence is fresh* —
    the record's own candidate moved on and the finished audit is about the
    tree before it.
    """
    subject = "a" * 40
    sentinel = tmp_path / "audit.status"
    sentinel.write_text("0\n")
    _save(tmp_path,
          waits=(Wait(job_id="audit", kind=WaitKind.PATH_EXISTS, path=str(sentinel),
                      expects="a verdict", subject_revision=subject,
                      not_beyond_seconds=3600, declared_at=continuation.now()),),
          actionable=("consume the audit",),
          evidence={"candidate": "demo 2.0.0 at " + "b" * 12})

    # A separate process, as a restart actually is.
    out = subprocess.run(
        [sys.executable, "-c",
         "import sys;sys.path.insert(0,sys.argv[1]);import continuation;"
         "r=continuation.load(sys.argv[2]);p=continuation.derive(r,relative_to=sys.argv[3]);"
         "print(p.state)", str(ROOT / "tools"), str(tmp_path / "CONTINUATION.json"),
         str(tmp_path)], capture_output=True, text=True, timeout=120)
    assert out.stdout.strip() == State.COMPLETED_NOT_CONSUMED, out.stderr

    view = projection.project(tmp_path)
    audit = next(c for c in view.figure_of("audit"))
    assert audit.tone == projection.Tone.BAD, (
        "a finished audit of a tree the record no longer calls the candidate read as current "
        "across a restart")
    assert "NOT the candidate" in audit.value
    assert any("NOT the candidate" in line.text for line in view.attention)


# --- partial output meets an interruption and a retry ---------------------------------


def test_a_retry_cannot_start_while_partial_output_is_unrecovered(tmp_path):
    """Recovery classification and the next-action rule are separate answers.
    The composition that matters: a job died with two of four chunks written,
    and the coordinator's next authorised action must be to recover them —
    never to dispatch the same obligation again, because the second worker
    would claim a root the first one owns.
    """
    root = tmp_path / "out"
    contract = task_output.OutputContract("survey", root, max_bytes_per_write=64,
                                          expected_chunks=4)
    task_output.claim_root(contract)
    task_output.materialise(contract, 0, "one")
    task_output.materialise(contract, 1, "two")
    contract.part_path(2).write_text('{"partial')
    _save(tmp_path,
          waits=(Wait(job_id="survey", kind=WaitKind.OUTPUT_ROOT, path=str(root),
                      task_id="survey", max_bytes_per_write=64, expects="four chunks",
                      obligation="repository-survey", not_beyond_seconds=3600,
                      declared_at=continuation.now()),),
          actionable=("recover the partial output before any retry",))

    report = task_output.classify(contract)
    assert report.state == task_output.RecoveryState.FAILED_WITH_PARTIAL_DURABLE_OUTPUT

    # A SECOND WORKER FOR THE SAME OBLIGATION IS REFUSED AT THE ROOT.
    with pytest.raises(Exception):
        task_output.claim_root(task_output.OutputContract(
            "survey-retry", root, max_bytes_per_write=64, expected_chunks=4))

    view = projection.project(tmp_path)
    assert "recover" in view.next_action.lower()
    output = next(c for c in view.figure_of("output"))
    assert output.tone == projection.Tone.WARN
    assert "partial" in output.fields["examined"]


# --- a scoped human decision meets unrelated authorised work ---------------------------


def test_a_second_blocker_on_the_same_item_does_not_stop_a_third_item(tmp_path):
    """The recorded incident was one blocker stopping everything. The
    composition nobody tested: TWO blockers of different kinds landing on the
    same item, with a third item free. Coverage is computed from the union, so
    the arithmetic that says *everything is blocked* has two chances to be
    wrong.
    """
    _save(tmp_path,
          actionable=("end the stalled worker", "repair the finding", "re-run the suite"),
          blockers=(Blocker(kind="human", hitl_row=4, detail="ending a worker is a human act",
                            blocks=("end the stalled worker",)),
                    Blocker(kind="capacity", pool_id="independent",
                            detail="no window for the retry",
                            blocks=("end the stalled worker",))))
    report = _derive(tmp_path)
    assert report.state != State.BLOCKED_ON_HUMAN
    assert report.state != State.BLOCKED_ON_CAPACITY
    view = projection.project(tmp_path)
    assert view.next_action in ("repair the finding", "re-run the suite")
    assert len([c for c in view.situation if c.kind == "intervention"]) == 1


def test_every_item_blocked_by_two_different_kinds_is_blocked_and_says_which(tmp_path):
    """The other half, and the reason the union is computed rather than the
    first blocker read: with both kinds present the state must be blocked, and
    the reader must be able to see both reasons."""
    _save(tmp_path, actionable=("end the stalled worker",),
          blockers=(Blocker(kind="human", hitl_row=4, detail="a person decides",
                            blocks=("end the stalled worker",)),
                    Blocker(kind="capacity", pool_id="independent", detail="no window",
                            blocks=("end the stalled worker",))))
    report = _derive(tmp_path)
    assert report.state in (State.BLOCKED_ON_HUMAN, State.BLOCKED_ON_CAPACITY)
    rendered = projection.project(tmp_path).render()
    assert "a person decides" in rendered and "no window" in rendered


# --- capacity UNKNOWN meets a completion ------------------------------------------------


def test_an_unknown_window_does_not_stop_consuming_a_finished_result(tmp_path):
    """Two conservative mechanisms compose into a wrong one if nobody checks:
    an unmeasured pool downgrades dispatch, and a finished job needs consuming.
    Consuming is not dispatching, and a coordinator that waited for a window
    before reading a result it already has would idle holding the answer.
    """
    sentinel = tmp_path / "done"
    sentinel.write_text("ok")
    _save(tmp_path,
          waits=(Wait(job_id="audit", kind=WaitKind.PATH_EXISTS, path=str(sentinel),
                      expects="a verdict", not_beyond_seconds=3600,
                      declared_at=continuation.now()),),
          actionable=("consume the verdict",))
    (tmp_path / "CAPACITY.json").write_text(json.dumps({
        "schema": "capacity-observation-v1",
        "pools": [{"pool_id": "independent", "kind": "independent", "window": "weekly"}]}))

    assert _derive(tmp_path).state == State.COMPLETED_NOT_CONSUMED
    verdict = capacity.gate(
        capacity.Dispatch(task_id="next", pool_id="independent",
                          authority_class="authority_free", allowed_executor_class="bounded"),
        capacity.Pool(pool_id="independent"), capacity.Reserve())
    assert verdict.verdict == capacity.Verdict.DISPATCH_SERIALLY
    view = projection.project(tmp_path)
    assert "consume" in view.next_action.lower(), (
        "an unmeasured window suppressed the action that needs no window at all")


# --- ownership meets reconstruction in a fresh process -----------------------------------


def test_an_output_root_owned_by_another_task_is_refused_after_a_restart(tmp_path):
    """Ownership is decided from a marker on disk and reconstruction reads the
    record from disk. Composed: after a restart the coordinator knows the job
    id and not who claimed the root, and the check must still refuse."""
    root = tmp_path / "out"
    task_output.claim_root(task_output.OutputContract("first", root, max_bytes_per_write=64))
    out = subprocess.run(
        [sys.executable, "-c",
         "import sys;sys.path.insert(0,sys.argv[1]);import task_output;"
         "c=task_output.OutputContract('second',sys.argv[2],max_bytes_per_write=64);"
         "r=task_output.classify(c);print(r.state);print(r.why)",
         str(ROOT / "tools"), str(root)], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines()[0] == task_output.RecoveryState.UNKNOWN
    assert "first" in out.stdout, "the refusal does not say who owns the root"


# --- a deadline meets a progress signal ---------------------------------------------------


def test_an_expired_deadline_is_not_excused_by_a_live_process(tmp_path):
    """`progress` and the deadline are different questions, and the wrong
    composition is *the process exists, so the deadline does not matter*. A
    live process is not progress; an expired deadline is a fact about the
    clock."""
    _save(tmp_path,
          waits=(Wait(job_id="j", kind=WaitKind.PROCESS, pid=os.getpid(), expects="a report",
                      not_beyond_seconds=1, declared_at="2020-01-01T00:00:00+00:00"),),
          actionable=("consume the report",))
    report = _derive(tmp_path)
    assert list(report.expired) == ["j"]
    assert report.state == State.RECOVERY_REQUIRED
    rendered = projection.project(tmp_path).render()
    assert "EXPIRED" in rendered
    assert "a live process is not progress" in rendered


# --- a completion meets a restart meets an unconsumed result --------------------------------


def test_consuming_a_result_twice_across_a_restart_is_visible_as_the_same_result(tmp_path):
    """The recorded shape: a coordinator restarts, sees a completion marker, and
    consumes a result it already consumed. Consumption is recorded in the
    record, so the composition to check is that the SECOND reading after
    consumption no longer reports the state that invites it."""
    sentinel = tmp_path / "done"
    sentinel.write_text("ok")
    wait = Wait(job_id="audit", kind=WaitKind.PATH_EXISTS, path=str(sentinel),
                expects="a verdict", not_beyond_seconds=3600, declared_at=continuation.now())
    _save(tmp_path, waits=(wait,), actionable=("consume the verdict",))
    assert _derive(tmp_path).state == State.COMPLETED_NOT_CONSUMED

    # The coordinator consumes it: the wait is retired and the item is done.
    _save(tmp_path, waits=(), actionable=(),
          evidence={"latest_audit": "consumed at " + continuation.now()})
    after = _derive(tmp_path)
    # NOT terminal: only the coordinator can say a capability is finished, and
    # `nothing outstanding, nothing blocked` means it decides what is next. What
    # must be true is that the result is no longer on offer — the reading that
    # invites a second consumption is gone.
    assert after.state != State.COMPLETED_NOT_CONSUMED, after.state
    assert not after.unconsumed, "the same result is still on offer after being consumed"
    assert not after.observations, "a retired wait is still being observed"


# --- a repository that configures git meets a read-only operation ----------------------------


def test_a_repository_cannot_make_a_read_only_read_run_a_program(tmp_path):
    """The read-only layer refuses config shapes whose value is a program. The
    composition: a repository sets one AND the caller asks a question that
    would use it. Neither half is interesting alone — a refused config nobody
    reaches is not a defence."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for command in (("init", "--quiet", "--initial-branch", "main"),
                    ("config", "user.name", "T"), ("config", "user.email", "t@e.invalid"),
                    ("config", "commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(repo), *command], check=True, capture_output=True)
    (repo / "a.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "one"], check=True,
                   capture_output=True)
    marker = tmp_path / "IT-RAN"
    subprocess.run(["git", "-C", str(repo), "config", "diff.external",
                    f"sh -c 'touch {marker}'"], check=True, capture_output=True)

    # THERE IS NO CLOSURE TO EXERCISE ANY MORE, AND THAT IS THE POINT. The key is
    # still named as program-valued — the projection reports it — but the read
    # does not depend on that report: the driver is not defined in the
    # configuration Git reads, so `--ext-diff` can be asked for by name and still
    # runs nothing. The composition is unchanged and its measurement is stronger:
    # a repository sets the key AND the caller asks the question that would use
    # it, and nothing runs.
    assert "diff.external" in gitread.PROGRAM_VALUED_CONFIG
    assert gitread.program_valued_config(repo) == ["diff.external"], (
        "the projection no longer reports what the repository declares")
    gitread._run(repo, "diff", "--ext-diff", "HEAD")
    assert not marker.exists(), "an explicitly requested external diff ran the driver"

    names = gitread.every_name_in_history(repo, "HEAD")
    assert "a.txt" in [path for _sha, path in names]
    assert not marker.exists(), "a repository's own configuration ran a program"
    # And the read that actually diffs, which is where a driver would run.
    gitread.whitespace_damage(repo)
    assert not marker.exists(), "a whitespace read ran the repository's diff driver"

    # AND THE OTHER HALF: a program-valued key with NO named closure is still
    # reported, so the empty list above is a closure and not a blind spot.
    subprocess.run(["git", "-C", str(repo), "config", "difftool.x.cmd",
                    f"sh -c 'touch {marker}'"], check=True, capture_output=True)
    assert "difftool.x.cmd" in gitread.program_valued_config(repo), (
        "a program-valued key the repository declares is missing from the report")
    assert not marker.exists()


# --- several abnormal conditions at once ------------------------------------------------------


def test_four_abnormal_conditions_at_once_all_reach_the_reader(tmp_path):
    """The composition nobody plans for. An expired deadline, a duplicated
    obligation, an unconsumed result and an unreadable budget, in one record.
    Each has a test; what this asks is whether the view still shows all four
    rather than the first one it meets.
    """
    done = tmp_path / "done"
    done.write_text("ok")
    _save(tmp_path,
          waits=(Wait(job_id="a", kind=WaitKind.PROCESS, pid=os.getpid(), expects="a report",
                      obligation="one-audit", not_beyond_seconds=1,
                      declared_at="2020-01-01T00:00:00+00:00"),
                 Wait(job_id="b", kind=WaitKind.PROCESS, pid=os.getpid(), expects="a report",
                      obligation="one-audit", not_beyond_seconds=3600,
                      declared_at=continuation.now()),
                 Wait(job_id="c", kind=WaitKind.PATH_EXISTS, path=str(done), expects="a verdict",
                      not_beyond_seconds=3600, declared_at=continuation.now())),
          actionable=("consume the verdict",),
          budgets={"cycles": "not a position"})
    report = _derive(tmp_path)
    assert list(report.expired) == ["a"]
    assert report.duplicated, "the duplicated obligation was lost among the others"
    assert list(report.unconsumed) == ["c"]

    view = projection.project(tmp_path)
    rendered = view.render()
    for expected in ("EXPIRED", "one-audit", "not a position this view can read"):
        assert expected in rendered, f"{expected!r} did not survive the company of the others"
    tones = {line.tone for line in view.attention}
    assert projection.Tone.BAD in tones and projection.Tone.UNKNOWN in tones
    assert projection.render_html(view).endswith("</html>")


def test_the_console_shows_every_abnormal_project_and_not_only_the_worst(tmp_path):
    """Aggregation is where several bad states become one. Three projects, three
    different defects: the overview must carry all three, and the counts must
    not collapse into the worst."""
    import console

    roots = []
    for name, fields in (
            ("idle", {"actionable": ("work nobody is doing",)}),
            ("expired", {"actionable": ("consume",), "waits": (
                Wait(job_id="j", kind=WaitKind.PROCESS, pid=os.getpid(), expects="a report",
                     not_beyond_seconds=1, declared_at="2020-01-01T00:00:00+00:00"),)}),
            ("blocked", {"actionable": ("freeze",), "blockers": (
                Blocker(kind="human", hitl_row=2, detail="the founder's act",
                        blocks=("freeze",)),)})):
        root = tmp_path / name
        root.mkdir()
        _save(root, **fields)
        roots.append((None, root))
    sites = console.survey(roots)
    assert {s.state for s in sites} == {State.SILENT_IDLE, State.RECOVERY_REQUIRED,
                                        State.BLOCKED_ON_HUMAN}
    page = console.render_console(sites)
    for state in (State.SILENT_IDLE, State.RECOVERY_REQUIRED, State.BLOCKED_ON_HUMAN):
        assert state in page
    assert all(sum(s.attention.values()) > 0 for s in sites), (
        "a project with a defect reports nothing needing attention")
