"""The golden test and the negative one, which are the whole argument.

Golden: rebuild the view from durable state alone. Negative: there is nothing
else to mutate, because the projection stores nothing — which is asserted
rather than described, by hashing the tree before and after.
"""

import hashlib
import json
import subprocess
import sys

import pytest

import continuation
import projection
import task_output
from continuation import Blocker, ContinuationRecord, State, Wait, WaitKind


def _tree_digest(root):
    """Every file under a directory, by path and content."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


@pytest.fixture
def project_root(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "PROJECT.yaml").write_text(
        "project:\n  name: example\n  repo_path: .\n"
        "publication:\n  intent: internal\n",
        encoding="utf-8",
    )
    continuation.save(
        ContinuationRecord(
            capability="CAP-EXAMPLE", updated_at=continuation.now(),
            actionable=("close the capability",),
            blockers=(Blocker(kind="human", detail="the freeze decision", hitl_row=2),),
        ),
        root / "CONTINUATION.json",
    )
    (root / "CAPACITY.json").write_text(json.dumps({
        "pools": [{"pool_id": "shared", "kind": "shared_with_coordinator", "window": "rolling",
                   "remaining": "UNKNOWN", "active_workers": 1, "observed_at": "2026-09-03T04:00Z"}],
        "reserve": {"coordinator": 10},
    }), encoding="utf-8")
    return root


# --- the golden test ------------------------------------------------------------


def test_the_view_is_rebuilt_from_durable_state_alone(project_root):
    """Two invocations, no state carried between them, one answer. There is no
    cache to warm and none to go stale."""
    first = projection.project(project_root).render()
    second = projection.project(project_root).render()
    assert first == second
    assert "CAP-EXAMPLE" in first
    assert State.BLOCKED_ON_HUMAN in first
    assert "row 2" in first


def test_the_view_follows_the_durable_state_when_it_changes(project_root):
    """The other half of golden: identical output could also mean it reads
    nothing at all."""
    before = projection.project(project_root).render()
    continuation.save(
        ContinuationRecord(capability="CAP-EXAMPLE", updated_at=continuation.now(),
                           actionable=("close the capability",)),
        project_root / "CONTINUATION.json",
    )
    after = projection.project(project_root).render()
    assert before != after
    assert State.SILENT_IDLE in after and "DEFECT" in after


# --- the negative test ------------------------------------------------------------


def test_rendering_writes_nothing_at_all(project_root):
    """A projection that persisted anything would have state of its own, and
    state of its own is how a projection becomes a second record. Asserted by
    hashing the tree, not by reading the source."""
    before = _tree_digest(project_root)
    projection.project(project_root).render()
    projection._cli([str(project_root)])
    assert _tree_digest(project_root) == before


def test_the_module_has_no_write_verb(project_root):
    names = set(dir(projection))
    for forbidden in ("save", "write", "cache", "snapshot", "persist", "update", "store",
                      "serve", "watch", "run_server"):
        assert forbidden not in names, f"projection gained {forbidden!r}"


def test_the_module_derives_nothing_of_its_own(project_root):
    """Every answer is delegated. Two derivations of one fact eventually
    disagree, and the disagreement is the thing this ordering exists to make
    impossible rather than adjudicable."""
    source = (
        __import__("pathlib").Path(projection.__file__).read_text(encoding="utf-8"))
    for owner in ("continuation.derive", "task_output.classify", "pack_pin.verify_pin"):
        assert owner in source, f"{owner} is the owner of its question and must be called"
    # And it must not reimplement the state vocabulary it renders.
    for state in (State.SILENT_IDLE, State.COMPLETED_NOT_CONSUMED, State.RECOVERY_REQUIRED):
        assert f'"{state}"' not in source, (
            f"{state} is spelled out here instead of coming from the module that owns it"
        )


def test_the_projection_reports_the_same_state_the_owner_derives(project_root):
    """Disagreement is a defect here, always — so the view is asserted against
    the deriving module rather than against a hand-written expectation."""
    record = continuation.load(project_root / "CONTINUATION.json")
    owner_says = continuation.derive(record, relative_to=project_root).state
    assert owner_says in projection.project(project_root).render()


# --- what it could not read ---------------------------------------------------------


def test_a_missing_continuation_record_is_unknown_and_not_a_resting_state(tmp_path):
    root = tmp_path / "bare"
    root.mkdir()
    view = projection.project(root)
    rendered = view.render()
    assert "not the same as there being nothing to do" in rendered
    # Asserted against the UNKNOWN list rather than against the text. Moving
    # the same sentence from `unknown` to `lines` renders almost identically
    # and changes the verdict, which is exactly the confusion the whole
    # projection exists to avoid — and a mutation proved the text assertion
    # could not see it.
    # Matched on the liveness panel's own phrasing. A looser substring also
    # matched the OUTPUT panel's unknown, so the assertion held while the
    # liveness panel had quietly stopped reporting one — two panels, one
    # sentence fragment, and a test that could not tell them apart.
    assert any("not the same as there being nothing to do" in item for item in view.unknowns)
    assert projection._cli([str(root)]) == 1


def test_an_absent_capacity_observation_says_unknown_rather_than_zero(project_root):
    (project_root / "CAPACITY.json").unlink()
    view = projection.project(project_root)
    assert "is not zero" in view.render()
    assert any("no capacity observation" in item for item in view.unknowns), (
        "an absence rendered as an ordinary line is an absence a reader will read as a reading"
    )


def test_an_unreadable_contract_is_reported_rather_than_skipped(project_root):
    (project_root / "PROJECT.yaml").write_text("project:\n  - this is not a mapping\n")
    view = projection.project(project_root)
    assert any("could not be read" in item for item in view.unknowns)


def test_a_pin_that_does_not_verify_is_said_plainly(project_root, tmp_path):
    (project_root / "PROJECT.yaml").write_text(
        "project:\n  repo_path: .\n"
        f"pack:\n  root_path: {tmp_path / 'no-such-release'}\n"
        "  version_adopted: 9.9.9\n  sha_adopted: " + "a" * 40 + "\n"
        "  tree_digest_sha256: " + "b" * 64 + "\n  state_adopted: QUALIFIED_AND_FROZEN\n"
    )
    rendered = projection.project(project_root).render()
    assert "PIN DOES NOT VERIFY" in rendered or "could not be checked" in rendered


# --- durable output, delegated ---------------------------------------------------------


def test_output_roots_are_classified_by_the_module_that_owns_the_question(project_root):
    contract = task_output.OutputContract(
        task_id="batch", output_root=project_root / "out", max_bytes_per_write=64)
    task_output.claim_root(contract)
    task_output.materialise(contract, 0, "a chunk")
    continuation.save(
        ContinuationRecord(
            capability="CAP-EXAMPLE", updated_at=continuation.now(),
            waits=(Wait(job_id="batch", kind=WaitKind.OUTPUT_ROOT, path=str(contract.output_root),
                        task_id="batch", max_bytes_per_write=64, expects="records", not_beyond_seconds=1800),),
        ),
        project_root / "CONTINUATION.json",
    )
    rendered = projection.project(project_root).render()
    assert task_output.RecoveryState.FAILED_WITH_PARTIAL_DURABLE_OUTPUT in rendered


# --- it is a renderer, not a service -------------------------------------------------


def test_one_invocation_answers_and_exits(project_root):
    """No port, no daemon, no loop. Removing this capability is deleting a file
    nothing else imports."""
    result = subprocess.run(
        [sys.executable, "tools/projection.py", str(project_root)],
        capture_output=True, text=True, timeout=60,
        cwd=str(__import__("pathlib").Path(projection.__file__).parent.parent),
    )
    assert result.returncode in (0, 1)
    assert "RUNTIME PACK — PROJECTION" in result.stdout
    assert "Rebuilt from durable state" in result.stdout


def test_no_runtime_tool_module_imports_it():
    """Easy to disable and easy to remove is a structural property, not a
    promise.

    Named precisely, because the loose form of the claim — *nothing imports it*
    — is false and an auditor said so: this module imports it, and so does
    `test_silent_idle_closure`. Tests importing a module is what tests are for.
    The property is that no RUNTIME tool module does, so deleting the file
    breaks no checker."""
    import pathlib

    tools = pathlib.Path(projection.__file__).parent
    importers = [
        path.name for path in tools.glob("*.py")
        if path.name != "projection.py" and "import projection" in path.read_text(encoding="utf-8")
    ]
    assert importers == [], f"these depend on the projection: {importers}"


def test_the_view_says_which_direction_a_disagreement_resolves(project_root):
    assert "THIS is the defect" in projection.project(project_root).render()


# --- falsifying the projection ---------------------------------------------------
#
# A dashboard is believed. That is its whole value and its whole hazard, so the
# adverse cases below are the ones where being believed is expensive: a stale
# record, a missing field, a malformed one, a coordinator that vanished, a
# result nobody took up. In each, the requirement is the same and it is not
# "render something reasonable" — it is SAY WHAT COULD NOT BE ESTABLISHED.

import json as _json
from pathlib import Path as _Path

import continuation as _continuation


def _record(tmp_path, **fields):
    fields.setdefault("capability", "C1")
    fields.setdefault("updated_at", _continuation.now())
    record = _continuation.ContinuationRecord(**fields)
    path = tmp_path / "CONTINUATION.json"
    _continuation.save(record, path)
    return path


def test_a_record_written_hours_ago_is_labelled_stale(tmp_path):
    """The objection this whole module was built against: *a projection over a
    state nothing transitions displays a stale value confidently.* The states
    above are derived from artifacts and so are current; the OBLIGATIONS are as
    the coordinator last wrote them, and how long ago that was is rendered."""
    _record(tmp_path, updated_at="2020-01-01T00:00:00Z", actionable=("something",))
    out = projection.project(tmp_path).render()
    assert "STALE" in out
    assert "2020-01-01" in out


def test_a_record_written_moments_ago_is_not(tmp_path):
    """The bound: a warning that is always on is not a warning."""
    _record(tmp_path, actionable=("something",))
    assert "STALE" not in projection.project(tmp_path).render()


def test_an_unreadable_timestamp_is_unknown_rather_than_fresh(tmp_path):
    _record(tmp_path, updated_at="whenever", actionable=("something",))
    out = projection.project(tmp_path).render()
    assert "cannot be read" in out
    assert "min ago" not in out.split("freshness")[1]


def test_a_malformed_record_says_so_and_renders_the_rest(tmp_path):
    """One broken file must not blank the view: everything else is still
    readable, and the reader needs to know which part is missing."""
    (tmp_path / "CONTINUATION.json").write_text("{ this is not json")
    out = projection.project(tmp_path).render()
    assert "UNKNOWN" in out
    assert "the pack this projection ships in" in out, "the other panels still render"


def test_a_missing_record_is_not_rendered_as_nothing_to_do(tmp_path):
    out = projection.project(tmp_path).render()
    assert "cannot be read" in out
    assert "UNKNOWN" in out.splitlines()[4], "the headline itself says unknown"


def test_a_wait_with_no_declared_subject_is_named_as_such(tmp_path):
    """Evidence is about one tree. A reader who cannot see which tree cannot
    tell current evidence from evidence two repair rounds old — which is not
    hypothetical: it happened in this release and cost six findings' worth of
    re-execution."""
    _record(tmp_path, waits=(_continuation.Wait(
        job_id="auditor", kind=_continuation.WaitKind.HUMAN, expects="a verdict"),),
        actionable=("wait",))
    unstated = _record(tmp_path, waits=(_continuation.Wait(
        job_id="auditor", kind=_continuation.WaitKind.PROCESS, pid=1, expects="a verdict",
        not_beyond_seconds=60, declared_at=_continuation.now()),))
    out = projection.project(tmp_path).render()
    assert "does not state the revision it is about" in out


def test_a_declared_subject_is_shown(tmp_path):
    _record(tmp_path, waits=(_continuation.Wait(
        job_id="auditor", kind=_continuation.WaitKind.PROCESS, pid=1, expects="a verdict",
        subject_revision="a" * 40, subject_digest="b" * 64,
        not_beyond_seconds=60, declared_at=_continuation.now()),))
    out = projection.project(tmp_path).render()
    assert "subject: aaaaaaaaaaaa" in out
    assert "does not state the revision" not in out


def test_an_expired_deadline_is_shown_as_overdue(tmp_path):
    _record(tmp_path, waits=(_continuation.Wait(
        job_id="auditor", kind=_continuation.WaitKind.PROCESS, pid=1, expects="a verdict",
        not_beyond_seconds=1, declared_at="2020-01-01T00:00:00Z"),))
    assert "EXPIRED" in projection.project(tmp_path).render()


def test_an_undeclared_budget_is_unknown_and_not_zero(tmp_path):
    """*Zero used* is a claim. A coordinator that does not track a counter has
    not spent nothing; it has not said."""
    _record(tmp_path, actionable=("something",))
    out = projection.project(tmp_path).render()
    assert "an untracked counter is unknown" in out
    # Checked inside the budget panel, not across the whole render: a substring
    # test over everything matches a timestamp and passes for the wrong reason,
    # which is the anti-test this release has now found five times.
    panel = out.split("── budgets and standing evidence")[1].split("──")[0]
    assert "used," not in panel, "no counter was rendered as spent"


def test_a_declared_budget_shows_what_is_left(tmp_path):
    _record(tmp_path, actionable=("x",),
            budgets={"cycles": {"used": 6, "ceiling": 8, "authorised_by": "a person"}})
    out = projection.project(tmp_path).render()
    assert "6/8 used, 2 remaining" in out
    assert "raised by a person" in out


def test_a_scoped_blocker_shows_what_it_blocks_and_what_stays_runnable(tmp_path):
    """The question a reader most needs answered about a blocker is not that it
    exists — it is what it stops, and what it does not."""
    _record(tmp_path, actionable=("blocked thing", "free thing"),
            blockers=(_continuation.Blocker(kind="human", detail="a person decides",
                                            hitl_row=4, blocks=("blocked thing",)),))
    out = projection.project(tmp_path).render()
    assert "SCOPED, and it does not stop the outstanding work" in out
    assert "NEXT AUTHORISED ACTION: free thing" in out


def test_a_finished_job_nobody_read_is_the_headline(tmp_path):
    """Four of five recorded liveness recurrences were here. It is the first
    line, not a detail."""
    sentinel = tmp_path / "done"
    wait = _continuation.Wait(job_id="j", kind=_continuation.WaitKind.PATH_EXISTS,
                              path=str(sentinel), expects="a result",
                              not_beyond_seconds=3600, declared_at=_continuation.now())
    sentinel.write_text("ok")
    path = _record(tmp_path, waits=(wait,))
    out = projection.project(tmp_path).render()
    assert "A RESULT IS WAITING TO BE READ" in out


def test_silent_idle_is_never_rendered_as_a_resting_state(tmp_path):
    _record(tmp_path, actionable=("work nobody is doing",))
    out = projection.project(tmp_path).render()
    assert "SILENT_IDLE" in out
    assert "not a resting state" in out


def test_the_projection_still_writes_nothing_with_every_panel_populated(tmp_path):
    """The invariant, re-asserted over the enlarged surface: more panels is more
    code that could write, and the hash is taken around the whole render."""
    import hashlib

    _record(tmp_path, actionable=("x",), budgets={"c": {"used": 1, "ceiling": 2}},
            evidence={"suite": "green"},
            waits=(_continuation.Wait(job_id="j", kind=_continuation.WaitKind.HUMAN,
                                      expects="a decision"),))

    def fingerprint():
        digest = hashlib.sha256()
        for path in sorted(p for p in tmp_path.rglob("*") if p.is_file()):
            digest.update(str(path.relative_to(tmp_path)).encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()

    before = fingerprint()
    projection.project(tmp_path).render()
    assert fingerprint() == before
