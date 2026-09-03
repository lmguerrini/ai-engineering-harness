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
    impossible rather than adjudicable.

    **Asserted by watching the calls happen, not by grepping for their names.**
    A blind reader deleted `projection.project` outright and this test still
    passed, because searching source text asks whether a string is present and
    not whether anything runs. Sixth appearance in this release of a check that
    passed for a reason it did not state.
    """
    import continuation as _c
    import task_output as _t

    # A FIXTURE THAT REACHES BOTH OWNERS. The first version used a project with
    # no output-root wait, so `task_output.classify` was never called and the
    # test could not have noticed if the projection had stopped delegating to
    # it — an independent reader replaced that function with one that raises and
    # the test still passed.
    root = project_root / "worker-output"
    contract = _t.OutputContract("survey", root, max_bytes_per_write=64)
    _t.claim_root(contract)
    _t.materialise(contract, 0, "a finding")
    _continuation.save(_continuation.ContinuationRecord(
        capability="C1", updated_at=_continuation.now(),
        waits=(_continuation.Wait(job_id="survey", kind=_continuation.WaitKind.OUTPUT_ROOT,
                                  path=str(root), task_id="survey", max_bytes_per_write=64,
                                  expects="the survey", not_beyond_seconds=3600,
                                  declared_at=_continuation.now()),)),
        project_root / "CONTINUATION.json")

    called = []
    real_derive, real_classify = _c.derive, _t.classify
    _c.derive = lambda *a, **k: (called.append("continuation.derive"), real_derive(*a, **k))[1]
    _t.classify = lambda *a, **k: (called.append("task_output.classify"), real_classify(*a, **k))[1]
    try:
        projection.project(project_root).render()
    finally:
        _c.derive, _t.classify = real_derive, real_classify

    assert "continuation.derive" in called, "the owner of coordinator state was never asked"
    assert "task_output.classify" in called, "the owner of output recovery was never asked"

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


# --- the same reading, in a browser ---------------------------------------------------


def test_the_page_is_self_contained_and_reaches_no_network(tmp_path):
    """A projection that fetched a stylesheet would fail differently depending on
    where it is opened, and must render the same on a machine with no route to
    anywhere."""
    _record(tmp_path, actionable=("something",))
    page = projection.render_html(projection.project(tmp_path))
    for reach in ("http://", "https://", "//cdn", "<script", "@import", "<link"):
        assert reach not in page, f"the page reaches for {reach!r}"
    assert page.startswith("<!doctype html>")
    assert "<body>" in page and "</body></html>" in page


def test_rendering_the_page_writes_nothing(tmp_path):
    """The same invariant as the text renderer, over a second renderer."""
    import hashlib

    _record(tmp_path, actionable=("x",), budgets={"c": {"used": 1, "ceiling": 2}},
            evidence={"suite": "green"})

    def fingerprint():
        digest = hashlib.sha256()
        for path in sorted(p for p in tmp_path.rglob("*") if p.is_file()):
            digest.update(str(path.relative_to(tmp_path)).encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()

    before = fingerprint()
    projection.render_html(projection.project(tmp_path))
    assert fingerprint() == before


def test_every_line_the_text_view_shows_the_page_shows_too(tmp_path):
    """Two renderers over one reading. If the page can omit a line, a reader of
    the page is reading something else."""
    _record(tmp_path, actionable=("a thing to do",),
            blockers=(_continuation.Blocker(kind="human", detail="a person decides",
                                            hitl_row=4, blocks=("a thing to do",)),),
            budgets={"cycles": {"used": 6, "ceiling": 8}}, evidence={"suite": "412 passing"})
    view = projection.project(tmp_path)
    page = projection.render_html(view)
    # LABELS, TITLES AND THE HEADLINE TOO. The first version checked `Line.text`
    # and the unknown strings only — an independent reader built a page holding
    # nothing but those and it passed, with every panel title, every label and
    # the headline missing. A test for *the page shows what the text view shows*
    # that ignores most of what the text view shows is a test for something else.
    assert projection._escape(view.headline) in page
    for panel in view.panels:
        assert projection._escape(panel.title) in page, f"the page dropped the title {panel.title!r}"
        for line in panel.rows():
            assert projection._escape(line.text) in page, f"the page dropped {line.text!r}"
            if line.label:
                assert projection._escape(line.label) in page, f"the page dropped {line.label!r}"
        for item in panel.unknown:
            assert projection._escape(item) in page, f"the page dropped an UNKNOWN: {item!r}"


def test_an_unknown_is_marked_in_the_page_and_not_merely_written(tmp_path):
    """Absence of telemetry must never render as healthy. In text it is prefixed
    `UNKNOWN:`; in the page it carries a class a stylesheet colours, and losing
    that class would make an absence look like any other line."""
    _record(tmp_path, actionable=("x",))
    page = projection.render_html(projection.project(tmp_path))
    assert "class='unknown" in page or 'class="unknown' in page
    assert "not established" in page


def test_the_headline_tone_comes_from_the_state_and_not_from_its_wording(tmp_path):
    """A defect state must not be able to render calm because someone reworded
    its sentence."""
    def verdict_class(page):
        # The class on the VERDICT BLOCK, not anywhere in the document. The first
        # version searched the whole page — and every one of these names is
        # defined in the stylesheet above it, so the assertion was true whatever
        # the code did. It survived a mutant that mapped SILENT_IDLE to GOOD.
        import re
        return re.search(r"<div class='verdict ([a-z-]*)'><b>coordinator</b>", page).group(1)

    _record(tmp_path, actionable=("work nobody is doing",))
    assert verdict_class(projection.render_html(projection.project(tmp_path))) == "v-bad"

    sentinel = tmp_path / "done"
    sentinel.write_text("ok")
    _record(tmp_path, waits=(_continuation.Wait(
        job_id="j", kind=_continuation.WaitKind.PATH_EXISTS, path=str(sentinel),
        expects="a result", not_beyond_seconds=3600, declared_at=_continuation.now()),))
    assert verdict_class(projection.render_html(projection.project(tmp_path))) == "v-warn"


def test_a_malformed_record_still_produces_a_page_that_says_so(tmp_path):
    (tmp_path / "CONTINUATION.json").write_text("{ not json")
    page = projection.render_html(projection.project(tmp_path))
    assert "</html>" in page
    assert "UNKNOWN" in page


def test_content_that_looks_like_markup_is_escaped(tmp_path):
    """A capability name is prose somebody wrote. If it can close a tag, the page
    a reader trusts is a page that record's author controls."""
    _record(tmp_path, capability="<script>alert(1)</script> & <b>bold</b>",
            actionable=("x",))
    page = projection.render_html(projection.project(tmp_path))
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page and "&amp;" in page


def test_the_page_declares_a_viewport_so_a_phone_gets_the_narrow_layout(tmp_path):
    _record(tmp_path, actionable=("x",))
    page = projection.render_html(projection.project(tmp_path))
    assert "width=device-width" in page
    assert "@media(max-width:700px)" in page


def test_an_evidence_reading_nobody_declared_is_an_explicit_unknown(tmp_path):
    """An absent key simply did not appear, which makes *nobody declared this*
    and *this is fine* look identical — the one thing this projection may never
    do. The readings a long run needs are listed whether or not the record
    carries them."""
    _record(tmp_path, actionable=("x",), evidence={"suite": "412 passing"})
    out = projection.project(tmp_path).render()
    assert "suite: 412 passing" in out
    for absent in ("public safety", "evolution candidates", "real consumers", "adapters"):
        assert f"the record declares no {absent}" in out


def test_the_state_vocabulary_is_shown_with_the_current_one_marked(tmp_path):
    """A reader who sees WAITING needs to know what the alternatives were.
    Without the vocabulary in front of them an absent state and an impossible
    state look identical."""
    _record(tmp_path, actionable=("work nobody is doing",))
    out = projection.project(tmp_path).render()
    assert "SILENT_IDLE: THIS ONE" in out
    assert "TERMINAL: not now" in out


def test_a_stall_is_reported_as_unestablishable_rather_than_absent(tmp_path):
    """Two of the states a reader asks about cannot be answered by one reading.
    Saying which module answers them is the honest form."""
    _record(tmp_path, actionable=("x",))
    out = projection.project(tmp_path).render()
    assert "STALLED" in out and "cannot establish it" in out
    assert "progress.classify" in out


def test_an_audit_whose_subject_is_not_the_candidate_is_named_as_such(tmp_path):
    """An audit of revision A must never look current for revision B. It
    happened in this release and cost six findings' worth of re-execution."""
    stale = _continuation.Wait(job_id="auditor", kind=_continuation.WaitKind.PROCESS, pid=1,
                               expects="a verdict", subject_revision="a" * 40,
                               not_beyond_seconds=3600, declared_at=_continuation.now())
    _record(tmp_path, waits=(stale,), evidence={"candidate": "2.3.0 at bbbbbbbbbbbb digest x"})
    out = projection.project(tmp_path).render()
    assert "NOT the candidate this record declares" in out

    current = _continuation.Wait(job_id="auditor", kind=_continuation.WaitKind.PROCESS, pid=1,
                                 expects="a verdict", subject_revision="b" * 40,
                                 not_beyond_seconds=3600, declared_at=_continuation.now())
    _record(tmp_path, waits=(current,), evidence={"candidate": "2.3.0 at bbbbbbbbbbbb digest x"})
    assert "NOT the candidate" not in projection.project(tmp_path).render()


def test_a_live_process_with_nothing_written_does_not_report_progress(tmp_path):
    """Process existence is never proof of progress, and this is the line where
    a reader would most easily be misled into thinking otherwise."""
    _record(tmp_path, waits=(_continuation.Wait(
        job_id="j", kind=_continuation.WaitKind.PROCESS, pid=1, expects="a result",
        not_beyond_seconds=3600, declared_at=_continuation.now()),))
    out = projection.project(tmp_path).render()
    assert "a live process is not progress" in out


def test_a_retry_says_which_attempt_it_is(tmp_path):
    """A retry that looks like a first dispatch hides the thing worth seeing."""
    _record(tmp_path, waits=(_continuation.Wait(
        job_id="j", kind=_continuation.WaitKind.PROCESS, pid=1, expects="a result",
        attempt=3, retry_reason="ended without writing anything",
        not_beyond_seconds=3600, declared_at=_continuation.now()),))
    out = projection.project(tmp_path).render()
    assert "attempt 3" in out and "ended without writing anything" in out


def test_the_pack_says_its_revision_is_not_in_the_tree_rather_than_omitting_it(tmp_path):
    """A manifest cannot name the commit that contains it. Leaving the field out
    made a reader wonder whether it was missing or unknowable."""
    out = projection.project(tmp_path).render()
    assert "not in the tree" in out and "git rev-parse HEAD" in out


def test_a_record_the_deriver_can_read_and_the_view_cannot_still_renders(tmp_path):
    """`derive()` returns RECOVERY_REQUIRED for a wait whose deadline is
    unreadable, and this module then raised `ValueError` reaching the same field
    for its own display — so the view of a broken record was no view at all,
    which is the one state a reader most needs to see."""
    import json as _json

    (tmp_path / "CONTINUATION.json").write_text(_json.dumps({
        "capability": "cap", "updated_at": _continuation.now(),
        "waits": [{"job_id": "human", "kind": "human", "expects": "a decision",
                   "not_beyond_seconds": "not-a-number",
                   "declared_at": _continuation.now()}]}))
    out = projection.project(tmp_path).render()
    assert "RECOVERY_REQUIRED" in out
    assert projection.render_html(projection.project(tmp_path)).endswith("</html>")


def test_a_tone_is_a_class_name_and_not_free_text(tmp_path):
    """`Panel(summary_tone="x' onclick='…")` put an event attribute into the
    page: escaping covers content, and this was markup. Anything outside the
    vocabulary renders as plain."""
    panel = projection.Panel("t", summary="s", summary_tone="x' onclick='alert(1)")
    page = projection.render_html(projection.Projection(panels=[panel]))
    assert "onclick" not in page
    assert "class='chip plain'" in page
