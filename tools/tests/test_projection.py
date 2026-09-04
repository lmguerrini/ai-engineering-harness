"""The golden test and the negative one, which are the whole argument.

Golden: rebuild the view from durable state alone. Negative: there is nothing
else to mutate, because the projection stores nothing — which is asserted
rather than described, by hashing the tree before and after.
"""

import hashlib
import json
import subprocess
import sys

import re

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

    # THE VIEW LAYER IS TWO FILES NOW. `console.py` composes exactly this
    # module's page per project rather than rendering a second reading of the
    # same state, so it depends on it by construction. The property is
    # unchanged and says so precisely: no CHECKER depends on either, and
    # deleting both breaks nothing that decides anything.
    view = {"projection.py", "console.py"}
    tools = pathlib.Path(projection.__file__).parent
    importers = [
        path.name for path in tools.glob("*.py")
        if path.name not in view
        and re.search(r"^\s*(import|from) (projection|console)\b",
                      path.read_text(encoding="utf-8"), re.M)
    ]
    assert importers == [], f"these depend on the view layer: {importers}"


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
    # The headline is split across the state and its sentence in the page, so
    # both halves are checked rather than the joined literal.
    state, _, sentence = view.headline.partition(":")
    assert projection._escape(state.strip()) in page
    assert projection._escape(sentence.strip()) in page
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
    # Hoisted into the attention strip AND left in its panel: a reader who
    # scans the top sees it, and a reader who reads the panel sees it too.
    assert "needs attention" in page
    assert "count unknown" in page


def test_the_headline_tone_comes_from_the_state_and_not_from_its_wording(tmp_path):
    """A defect state must not be able to render calm because someone reworded
    its sentence."""
    def verdict_class(page):
        # The class on the VERDICT BLOCK, not anywhere in the document. The first
        # version searched the whole page — and every one of these names is
        # defined in the stylesheet above it, so the assertion was true whatever
        # the code did. It survived a mutant that mapped SILENT_IDLE to GOOD.
        import re
        return re.search(r"<div class='cmd ([a-z-]*)'>", page).group(1)

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
    # The BREAKPOINT, not a literal. Asserting the number spelled in the
    # stylesheet made the test fail the moment the layout was retuned, which
    # told nobody anything: the property is that a narrow layout exists and
    # begins somewhere a phone actually is.
    import re

    narrow = [int(w) for w in re.findall(r"@media\(max-width:(\d+)px\)", page)]
    assert narrow, "the page declares no narrow layout at all"
    assert any(600 <= w <= 900 for w in narrow), (
        f"the narrow layout begins at {narrow}, which is not a phone")


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


def test_a_budget_position_that_is_not_a_position_does_not_raise(tmp_path):
    """`budgets: {"cycles": 7}` loads and the view then called `.get` on an
    integer. A projection may not raise, least of all on the record it exists to
    display."""
    import json as _json

    (tmp_path / "CONTINUATION.json").write_text(_json.dumps({
        "capability": "cap", "updated_at": _continuation.now(),
        "actionable": ["x"], "budgets": {"cycles": 7}}))
    out = projection.project(tmp_path).render()
    assert "not a position this view can read" in out
    assert projection.render_html(projection.project(tmp_path)).endswith("</html>")


# --- the structural pass ---------------------------------------------------------


def test_uncertainty_is_never_put_behind_a_disclosure(tmp_path):
    """Detail is collapsed and uncertainty is not. A line marked BAD, WARN or
    UNKNOWN by its own panel stays in the panel's open list AND is hoisted into
    the attention strip; only MUTED and nested lines go behind `<details>`."""
    import re

    _record(tmp_path, actionable=("x",), waits=(_continuation.Wait(
        job_id="j", kind=_continuation.WaitKind.PROCESS, pid=1, expects="a result",
        not_beyond_seconds=1, declared_at="2020-01-01T00:00:00+00:00"),))
    page = projection.render_html(projection.project(tmp_path))

    collapsed = "".join(re.findall(r"<details>(?!\s*<summary>needs).*?</details>", page, re.S))
    for tone in ("bad", "warn", "unknown"):
        assert f"class='{tone} " not in collapsed, f"a {tone} line is hidden behind a disclosure"


def test_the_attention_strip_repeats_rather_than_replaces(tmp_path):
    """Hoisting is a change of position, not of judgement. Every line in the
    strip is still in the panel it came from."""
    _record(tmp_path, actionable=("x",))
    view = projection.project(tmp_path)
    assert view.attention, "this state has unknowns to hoist"
    page = projection.render_html(view)
    for line in view.attention:
        assert projection._escape(line.text.split(" — ", 1)[-1]) in page


def test_the_next_action_is_lifted_out_of_the_panel_it_lives_in(tmp_path):
    """The question a reader most often has is *what happens next*, and it was
    one line among forty."""
    _record(tmp_path, actionable=("consume the audit", "then verify identity"))
    view = projection.project(tmp_path)
    assert view.next_action == "consume the audit"
    assert "<div class=next><b>NEXT AUTHORISED ACTION</b>" in projection.render_html(view)


def test_a_clean_reading_says_so_without_claiming_the_run_is_fine(tmp_path):
    """An empty attention strip is a reading of a record, not a promise about a
    run, and the page says which."""
    sentinel = tmp_path / "done"
    wait = _continuation.Wait(job_id="j", kind=_continuation.WaitKind.PATH_EXISTS,
                              path=str(sentinel), expects="a result",
                              not_beyond_seconds=3600, declared_at=_continuation.now())
    sentinel.write_text("ok")
    _record(tmp_path, waits=(wait,),
            evidence={n: "declared" for n in
                      ("candidate", "suite", "gates", "latest_audit", "closure",
                       "recurrence_classes", "real_consumers", "adapters", "continuation",
                       "public_safety", "evolution_candidates")},
            budgets={"cycles": {"used": 1, "ceiling": 8}})
    page = projection.render_html(projection.project(tmp_path))
    if "count good" in page:
        assert "not a promise about the run" in page


def test_every_panel_belongs_to_one_of_the_questions_a_reader_asks(tmp_path):
    _record(tmp_path, actionable=("x",))
    groups = {p.group for p in projection.project(tmp_path).panels}
    assert groups <= {"now", "evidence", "resources", "identity", "detail"}
    assert "now" in groups and "identity" in groups


@pytest.mark.parametrize("record,capacity", [
    ({"waits": [{"job_id": "h", "kind": "human", "expects": "a decision",
                 "attempt": "three"}]}, None),
    ({"actionable": ["x"]}, {"pools": 1}),
    ({"actionable": ["x"]}, {"pools": [{"pool_id": 7}]}),
    ({"waits": [{"job_id": "h", "kind": "human", "expects": "e", "depth": "deep"}]}, None),
    ({"actionable": ["x"], "evidence": {"suite": {"nested": True}}}, None),
])
def test_no_shape_of_a_saved_record_makes_the_view_raise(tmp_path, record, capacity):
    """Guarding the deadline, then the budget position, then the write bound
    closed three shapes and left `attempt: "three"` and `{"pools": 1}` — an
    independent reader found both and would have found a third.

    **Every panel is built inside a guard now**, so the question stops being
    which field somebody thought of. A panel that cannot be built says it could
    not be built, which is the only behaviour a view of a broken record may
    have."""
    import json as _json

    (tmp_path / "CONTINUATION.json").write_text(_json.dumps(
        {"capability": "c", "updated_at": _continuation.now(), **record}))
    if capacity is not None:
        (tmp_path / "CAPACITY.json").write_text(_json.dumps(capacity))

    out = projection.project(tmp_path).render()
    assert out
    assert projection.render_html(projection.project(tmp_path)).endswith("</html>")


def test_a_panel_that_cannot_be_built_says_so_rather_than_vanishing(tmp_path, monkeypatch):
    """A panel that raised used to take the whole view with it; a panel that
    silently disappeared would be worse, because a reader cannot miss what is
    not there."""
    _record(tmp_path, actionable=("x",))

    def broken(*_args, **_kw):
        raise RuntimeError("this panel cannot be built")

    monkeypatch.setattr(projection, "_capacity_panel", broken)
    view = projection.project(tmp_path)
    capacity = [p for p in view.panels if p.title == "capacity"]
    assert capacity, "the panel vanished instead of reporting"
    assert any("could not be built" in u for u in capacity[0].unknown)


# --- TERMINAL MISSION CONTROL: theming is presentation and nothing else --------------


def _themed(tmp_path, **kw):
    return projection.render_html(projection.project(tmp_path), **kw)


def test_a_theme_changes_no_state_and_no_classification(tmp_path):
    """The whole boundary in one test. A theme may move every surface colour and
    no semantic one, and it may not change a single word the projection derived
    — a state that reads differently under a theme is a theme that decided what
    the state is."""
    import re

    # A fixture that reaches EVERY part of the page, including the status bar
    # and the operational strip. Without budgets the strip renders empty for
    # both themes, and a mutant that dropped the strip under one of them
    # survived — the comparison was real and the fixture had nothing to compare.
    _record(tmp_path, actionable=("work nobody is doing",),
            budgets={"cycles": {"used": 6, "ceiling": 8, "authorised_by": "a person"}},
            evidence={"suite": "412 passing", "candidate": "demo at abcdef123456"},
            waits=(_continuation.Wait(job_id="j", kind=_continuation.WaitKind.HUMAN,
                                      expects="a decision"),))
    plain = _themed(tmp_path)
    matrix = _themed(tmp_path, theme="matrix")
    assert "class=strip" in plain, "the fixture does not reach the operational strip"

    def body(page):
        return re.sub(r"<style>.*?</style>", "", page, flags=re.S)

    assert body(plain).replace('<html lang="en">', '') == \
        body(matrix).replace('<html lang="en" data-theme="matrix">', ''), \
        "the theme changed something other than the stylesheet"


@pytest.mark.parametrize("theme", projection.LENSES)
def test_every_semantic_tone_keeps_its_own_colour_under_every_theme(theme):
    """Matrix mode is a green console, not a green everything. **A warning that
    turned green would be a theme deciding what a warning is** — so the theme
    moves ground, panel, rule, ink and one accent, and re-tones the semantics
    for contrast without merging them."""
    import re

    style = projection._STYLE
    block = style if not theme else style[style.index(f'[data-theme="{theme}"]'):]
    block = block[:block.index("}")] if theme else block

    colours = {}
    # ACTION TOO. It was omitted, and a matrix mutant setting `--action` to the
    # same green as `--good` passed — the tone that marks the next authorised
    # action, merged with the tone that marks an established good state, in the
    # test for *every semantic tone*. Found by an independent reader.
    for name in ("bad", "warn", "unknown", "good", "action"):
        found = re.search(rf"--{name}:(#[0-9a-f]{{6}})", block)
        assert found, f"the {theme or 'default'} theme does not define --{name}"
        colours[name] = found.group(1)
    assert len(set(colours.values())) == 5, (
        f"two semantic tones share a colour under {theme or 'default'}: {colours}")


@pytest.mark.parametrize("theme", projection.LENSES)
@pytest.mark.parametrize("what,record,marker", [
    ("SILENT_IDLE", {"actionable": ["work nobody is doing"]}, "SILENT_IDLE"),
    ("an unknown", {}, "UNKNOWN"),
    ("a human blocker", {"actionable": ["x"], "blockers": [
        {"kind": "human", "detail": "a person decides", "hitl_row": 2, "blocks": ["x"]}]},
     "BLOCKED_ON_HUMAN"),
])
def test_styling_cannot_hide_a_state_under_either_theme(tmp_path, theme, what, record, marker):
    """Visual hierarchy may not change authority. Each of these must be present
    in the page's text under both themes — not merely coloured, present."""
    import json as _json

    (tmp_path / "CONTINUATION.json").write_text(_json.dumps(
        {"capability": "c", "updated_at": _continuation.now(), **record}))
    page = _themed(tmp_path, theme=theme)
    assert marker in page, f"{what} is not in the page under theme {theme or 'default'}"


def test_the_accent_is_configurable_without_touching_governance(tmp_path):
    """One variable, set at render time. It reaches no record, no classification
    and no file — a presentation preference that needed authoritative state to
    hold it would be a dashboard storing governance."""
    _record(tmp_path, actionable=("x",))
    page = _themed(tmp_path, accent="#ff00aa")
    assert "--accent:#ff00aa" in page
    assert "#ff00aa" not in _themed(tmp_path)


def test_the_status_bar_lifts_values_it_does_not_invent(tmp_path):
    """Identity at a glance, and every cell of it is a line some panel also
    shows. A bar that computed its own values would be a second reading."""
    _record(tmp_path, actionable=("x",))
    view = projection.project(tmp_path)
    bar = projection._status_bar(view)
    assert "2.3.0" in bar and "IN_PROGRESS" in bar
    text = view.render()
    for shown in ("2.3.0", "IN_PROGRESS"):
        assert shown in text, f"the bar shows {shown!r} and no panel does"


def test_a_budget_with_no_ceiling_gets_no_bar(tmp_path):
    """The strip renders figures, never estimates. A meter needs a denominator
    and a budget without one is shown as text rather than as a guessed fraction."""
    _record(tmp_path, actionable=("x",), budgets={"counted": {"used": 6, "ceiling": 8},
                                                  "uncounted": {"used": 3}})
    page = projection.render_html(projection.project(tmp_path))
    assert "6/8" in page and "class=meter" in page
    assert "3/None" not in page and "3/0" not in page


# --- TERMINAL MISSION CONTROL: the console's own invariants ---------------------------


def _rich(tmp_path):
    """A project that reaches every band of the console: budgets with and
    without a ceiling, evidence, a job with a deadline, an output root, a
    scoped blocker and a capacity observation."""
    import json as _json
    import task_output as _t

    root = tmp_path / "worker-output"
    contract = _t.OutputContract("survey", root, max_bytes_per_write=64, expected_chunks=2)
    _t.claim_root(contract)
    _t.materialise(contract, 0, "a finding")
    _record(tmp_path, actionable=("consume the survey", "free thing"),
            budgets={"cycles": {"used": 6, "ceiling": 8}, "uncounted": {"used": 3}},
            evidence={"suite": "412 passing", "candidate": "demo at abcdef123456"},
            blockers=(_continuation.Blocker(kind="human", detail="a person decides",
                                            hitl_row=4, blocks=("free thing",)),),
            waits=(_continuation.Wait(
                job_id="survey", kind=_continuation.WaitKind.OUTPUT_ROOT, path=str(root),
                task_id="survey", max_bytes_per_write=64, expects="two chunks",
                subject_revision="abcdef123456" + "0" * 28,
                not_beyond_seconds=3600, declared_at=_continuation.now()),))
    (tmp_path / "CAPACITY.json").write_text(_json.dumps({
        "schema": "capacity-observation-v1",
        "pools": [{"pool_id": "independent", "kind": "independent", "window": "weekly",
                   "remaining": 340, "unit": "requests", "observed_at": _continuation.now(),
                   "active_workers": 1}],
        "reserve": {"coordinator": 20, "result_consumption": 10, "repair_and_audit": 10}}))
    return projection.project(tmp_path)


def test_a_cell_says_nothing_its_panel_does_not_say(tmp_path):
    """**The whole bound on the instrument bands.**

    A figure is the compact form of a fact its panel also states in full. If a
    cell could carry a value no line carries, the console would have a reading
    the text view does not — and the page would be the one nobody can check
    against the record. So every value and every note must occur in the text
    its own panel renders.
    """
    view = _rich(tmp_path)
    assert view.situation and view.telemetry, "the fixture reaches neither band"
    for panel in view.panels:
        said = panel.render()
        for cell in panel.cells:
            assert cell.value in said, (
                f"{panel.title!r} shows the figure {cell.value!r} for {cell.label!r} and says it "
                f"nowhere. A cell restates a line; it may not be the only place a reading is")
            assert not cell.note or cell.note in said, (
                f"{panel.title!r} annotates {cell.label!r} with {cell.note!r}, which it never says")
            #: AND EVERY COLUMN. A cross-project table has more columns than a
            #: cell has room for, and a column is exactly where a value that no
            #: panel states could hide: nobody scrolls a table looking for the
            #: line it came from.
            for column, entry in cell.fields.items():
                assert entry in said, (
                    f"{panel.title!r} tabulates {column}={entry!r} for {cell.label!r} and says it "
                    f"nowhere")


def test_a_cell_that_invents_a_value_is_caught(tmp_path):
    """The bound above, falsified. The check must fail for the thing it forbids
    — otherwise it is a loop over a list that is usually empty."""
    view = _rich(tmp_path)
    panel = next(p for p in view.panels if p.cells)
    panel.figure("fabricated", "a figure no line carries")
    said = panel.render()
    assert not all(c.value in said for c in panel.cells), (
        "a cell carrying a value its panel never says passed the completeness check")


def test_every_figure_reaches_the_page(tmp_path):
    """Cells are not a second data model that can quietly stop rendering."""
    view = _rich(tmp_path)
    page = projection.render_html(view)
    for cell in view.situation + view.telemetry:
        assert projection._escape(cell.value) in page, f"the page dropped the figure {cell!r}"
        assert projection._escape(cell.label) in page


def test_a_meter_is_drawn_only_against_a_declared_denominator(tmp_path):
    """Fabricated precision is worse than prose: a reader trusts a bar without
    reading it."""
    view = _rich(tmp_path)
    for cell in view.telemetry:
        if cell.share:
            used, ceiling = cell.share
            assert isinstance(used, int) and isinstance(ceiling, int) and ceiling > 0
    counted = next(c for c in view.telemetry if c.label == "cycles")
    uncounted = next(c for c in view.telemetry if c.label == "uncounted")
    assert counted.share == (6, 8) and uncounted.share is None
    page = projection.render_html(view)
    assert "class=meter" in page and "3/None" not in page and "3/0" not in page


def test_the_command_band_is_never_behind_a_disclosure(tmp_path):
    """Level 1 is what a reader gets in the first seconds. A state, a next
    action or a blocker inside a `<details>` is a state nobody read."""
    import re

    view = _rich(tmp_path)
    page = projection.render_html(view)
    head = page[:page.index("<main>")]
    collapsed = "".join(re.findall(r"<details[^>]*>(?!\s*<summary>needs).*?</details>", head, re.S))
    assert collapsed == "", "part of the command band is collapsed"
    for cell in view.situation:
        assert projection._escape(cell.value) in head, f"{cell.label} is not in the command band"
    assert "NEXT AUTHORISED ACTION" in head


def test_uncertainty_stays_open_however_the_disclosure_is_spelled(tmp_path):
    """The same property as `test_uncertainty_is_never_put_behind_a_disclosure`,
    against a renderer that adds an attribute to its `<details>`.

    The original matched the literal `<details>`, so putting a class on the
    element would have emptied the check silently — a gate defeated by a
    presentation change nobody would think to look at.
    """
    import re

    _record(tmp_path, actionable=("x",), waits=(_continuation.Wait(
        job_id="j", kind=_continuation.WaitKind.PROCESS, pid=1, expects="a result",
        not_beyond_seconds=1, declared_at="2020-01-01T00:00:00+00:00"),))
    page = projection.render_html(projection.project(tmp_path))
    hidden = "".join(re.findall(r"<details(?![^>]*class=attn)[^>]*>.*?</details>", page, re.S))
    assert hidden, "the fixture collapses nothing, so this proves nothing"
    for tone in ("bad", "warn", "unknown"):
        assert f"class='{tone} " not in hidden, f"a {tone} line is hidden behind a disclosure"


def test_no_status_is_carried_by_colour_alone(tmp_path):
    """Every urgent tone gets a glyph as well as a hue. A reader who cannot
    separate red from amber must still be able to separate a defect from a
    warning."""
    style = projection._STYLE
    for tone in ("bad", "warn", "unknown"):
        assert f".{tone} em::before" in style or f"li.{tone} .v::before" in style, (
            f"{tone} is distinguished by colour alone")
    page = projection.render_html(_rich(tmp_path))
    assert "✕" in style and "▲" in style and "?" in style


@pytest.mark.parametrize("theme", projection.LENSES)
def test_the_console_reads_in_the_order_a_reader_needs(tmp_path, theme):
    """Command, then telemetry, then panels — in the DOM, so a phone that
    stacks the page gets the same order without a second layout to keep true."""
    page = _themed(tmp_path, theme=theme) if False else projection.render_html(
        _rich(tmp_path), theme=theme)
    order = [page.index(mark) for mark in
             ("<div class=bar>", "class=state", "NEXT AUTHORISED ACTION", "class=sit",
              "class=attn", "class=strip", "<main>", "<footer>")]
    assert order == sorted(order), "the console's bands are not in reading order"


def test_the_situation_tally_counts_only_what_the_page_shows(tmp_path):
    """The one computed thing in the command band is a count of its own cells —
    page furniture, like the badge on the attention strip. It may not become a
    reading."""
    view = _rich(tmp_path)
    band = projection._situation(view)
    jobs = [c for c in view.situation if c.label.startswith("job ")]
    assert jobs, "the fixture declares no job"
    for cell in jobs:
        assert cell.value in band
    assert f"{len(jobs)} {jobs[0].value.lower()}" in band


def _theme_tokens(name: str) -> dict:
    """The colour variables one theme actually resolves to."""
    import re

    style = projection._STYLE
    if name in projection.LENSES and name:
        block = style[style.index(f'[data-theme="{name}"]'):]
    elif name == "light":
        block = style[style.index("prefers-color-scheme:light"):]
    else:
        block = style[style.index(":root{"):]
    block = block[:block.index("}")]
    tokens = dict(re.findall(r"--([a-z0-9-]+):(#[0-9a-f]{3,8})", block))
    if name != "":
        tokens = {**_theme_tokens(""), **tokens}
    return tokens


def _contrast(fg: str, bg: str) -> float:
    """WCAG 2.1 relative-luminance contrast ratio."""
    def channels(colour):
        value = colour.lstrip("#")
        if len(value) == 3:
            value = "".join(c * 2 for c in value)
        return [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]

    def luminance(colour):
        r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                   for c in channels(colour))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    a, b = luminance(fg), luminance(bg)
    lo, hi = sorted((a, b))
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("theme", list(projection.LENSES) + ["light"])
def test_every_pairing_the_console_actually_paints_is_legible(theme):
    """Contrast, measured rather than eyeballed.

    Every foreground the stylesheet puts on a given surface, checked against
    WCAG 2.1 AA: 4.5:1 for text, 3:1 for the micro-labels and rules that are
    never the only place a reading appears. **Written after the palette, and it
    failed** — which is the reason to compute a ratio instead of looking at it.
    """
    t = _theme_tokens(theme)
    body = [("ink", "ground"), ("ink", "panel"), ("ink", "panel-2"), ("ink", "panel-3"),
            ("dim", "panel"), ("dim", "panel-2"), ("dim", "panel-3"),
            ("bad", "panel"), ("warn", "panel"), ("unknown", "panel"), ("good", "panel"),
            ("bad", "bad-bg"), ("warn", "warn-bg"), ("unknown", "unknown-bg"),
            ("good", "good-bg"), ("action", "action-bg"), ("accent", "panel"),
            ("bad", "panel-2"), ("warn", "panel-2"), ("unknown", "panel-2"),
            ("good", "panel-2"), ("unknown", "unknown-bg")]
    #: Uppercase micro-labels and disclosure summaries. Never the only place a
    #: reading is: every one of them labels a value rendered in `ink`.
    secondary = [("faint", "panel"), ("faint", "panel-2"), ("faint", "panel-3"),
                 ("faint", "ground")]
    for fg, bg in body:
        ratio = _contrast(t[fg], t[bg])
        assert ratio >= 4.5, (
            f"{theme or 'default'}: --{fg} on --{bg} is {ratio:.2f}:1, below AA for text")
    for fg, bg in secondary:
        ratio = _contrast(t[fg], t[bg])
        assert ratio >= 3.0, (
            f"{theme or 'default'}: --{fg} on --{bg} is {ratio:.2f}:1, below AA for a label")


@pytest.mark.parametrize("theme", list(projection.LENSES) + ["light"])
def test_the_theme_moves_the_ground_and_not_the_meanings(theme):
    """A green console, not a green everything: the four semantic hues stay
    separable from each other AND from the theme's own accent, in every theme."""
    t = _theme_tokens(theme)
    semantic = {name: t[name] for name in ("bad", "warn", "unknown", "good")}
    assert len(set(semantic.values())) == 4, f"{theme}: two semantic tones share a colour"
    for name, colour in semantic.items():
        if name == "action":
            continue
        assert _contrast(colour, t["accent"]) > 1.15 or colour != t["accent"], (
            f"{theme}: --{name} is the accent, so the theme decided what it means")


#: Every field a saved record can carry, crossed with values of the wrong shape.
#: **Generated, not chosen.** Three rounds of *no shape of a saved record makes
#: the view raise* were closed one hand-picked field at a time — the deadline,
#: then the budget position, then the write bound — and each time an
#: independent reader found the next one: `attempt: "three"`, `{"pools": 1}`,
#: and then `capability: 7`, which raised in the attention strip. A list of
#: shapes somebody thought of is a list of shapes somebody thought of.
_WRONG_SHAPES = [
    (field, value)
    for field in ("capability", "updated_at", "actionable", "waits", "blockers", "budgets",
                  "evidence", "record_path")
    for value in (7, 1.5, True, [], {}, "", ["a", 2], {"k": ["v"]}, None)
]


@pytest.mark.parametrize("field,value", _WRONG_SHAPES,
                         ids=[f"{f}={v!r}" for f, v in _WRONG_SHAPES])
def test_no_field_of_the_wrong_shape_makes_the_view_raise(tmp_path, field, value):
    """A projection may not raise, whatever the record holds.

    The record is untrusted input: a coordinator writes it, a person edits it,
    a half-finished write truncates it. **A view of a broken record is the one
    view a reader most needs**, so a field that cannot be rendered is rendered
    as what it is rather than taking the page with it.
    """
    import json as _json

    document = {"capability": "c", "updated_at": _continuation.now(), field: value}
    (tmp_path / "CONTINUATION.json").write_text(_json.dumps(document))
    view = projection.project(tmp_path)
    assert view.render()
    assert projection.render_html(view).endswith("</html>")
    #: And it must not have rendered the wreck as a resting state.
    assert view.headline


def test_the_generated_shapes_would_notice_the_defect_they_were_written_for(tmp_path):
    """The bound. `capability: 7` is the shape an independent reader found, and
    it must be in the generated set and must reach the code that broke."""
    import json as _json

    assert ("capability", 7) in _WRONG_SHAPES
    (tmp_path / "CONTINUATION.json").write_text(_json.dumps(
        {"capability": 7, "updated_at": _continuation.now(), "actionable": ["x"]}))
    view = projection.project(tmp_path)
    # It reaches the attention strip, which is where it raised.
    assert view.attention or view.unknowns
    assert "7" in view.render()


def test_every_lens_the_stylesheet_defines_is_reachable_from_the_command_line():
    """A lens with no way to select it is a lens nobody sees, and a selectable
    lens with no block renders as the default while claiming not to. Both halves
    come from one list, read off the stylesheet."""
    import re

    defined = set(re.findall(r'\[data-theme="([a-z]+)"\]', projection._STYLE))
    assert defined == set(projection.LENSES) - {""}
    assert len(defined) >= 4, f"only {len(defined)} lenses are defined"
    for lens in projection.LENSES:
        # The ROOT ELEMENT, not the document: the stylesheet names every lens,
        # so searching the page finds them all whichever one was asked for.
        root = (projection.render_html(projection.Projection(), theme=lens)
                .split(">")[1].strip() + ">")
        assert root.startswith("<html"), root
        assert (f'data-theme="{lens}"' in root) if lens else ("data-theme" not in root)


@pytest.mark.parametrize("lens", [l for l in projection.LENSES if l])
def test_a_lens_is_a_stylesheet_and_never_a_reading(tmp_path, lens):
    """The whole boundary, for every lens rather than for the first two.

    A lens may move every surface colour and no semantic one, and may not
    change a single word the projection derived. Parametrised off the same
    list the stylesheet defines, so a fifth lens cannot arrive untested.
    """
    import re

    _record(tmp_path, actionable=("work nobody is doing",),
            budgets={"cycles": {"used": 6, "ceiling": 8}},
            evidence={"suite": "412 passing", "candidate": "demo at abcdef123456"},
            waits=(_continuation.Wait(job_id="j", kind=_continuation.WaitKind.HUMAN,
                                      expects="a decision"),))
    plain = _themed(tmp_path)
    themed = _themed(tmp_path, theme=lens)
    assert "class=strip" in plain, "the fixture does not reach the operational strip"

    def body(page):
        return re.sub(r"<style>.*?</style>", "", page, flags=re.S)

    assert body(plain).replace('<html lang="en">', "") == \
        body(themed).replace(f'<html lang="en" data-theme="{lens}">', ""), \
        f"the {lens} lens changed something other than the stylesheet"


@pytest.mark.parametrize("state,expected,tone", [
    ("QUALIFIED_AND_FROZEN", "may be pinned", projection.Tone.GOOD),
    ("IN_PROGRESS", "NO — only QUALIFIED_AND_FROZEN", projection.Tone.WARN),
    ("WITHDRAWN", "NO — only QUALIFIED_AND_FROZEN", projection.Tone.WARN),
])
def test_adoptability_is_stated_in_both_directions(tmp_path, state, expected, tone):
    """**A mutant survived here.** Making the panel state adoptability only when
    the answer is no changed nothing that any test could see, because the pack
    under test is never frozen and the positive branch was therefore never
    rendered by anything.

    A reading that only exists in one of its two states is a reading a reader
    cannot rely on: with a frozen pack in front of them they would see silence
    where the release says *this may be adopted*, and silence is what an
    unstated fact looks like.
    """
    import json as _json

    root = tmp_path / "pack"
    root.mkdir()
    (root / "PACK_MANIFEST.json").write_text(_json.dumps({
        "version": "2.3.0", "state": state, "tree_digest_sha256": "a" * 64,
        "digest_algorithm": "sha256-framed-v1", "digest_file_count": 1,
        "tests": {"passed": 1}}))
    panel = projection._pack_panel(root)
    said = next((l for l in panel.rows() if l.label == "adoptability"), None)
    assert said is not None, "the panel does not state adoptability at all"
    assert expected in said.text, said.text
    assert said.tone == tone, f"{state} is toned {said.tone}"


def _hue_and_luminance(colour: str):
    """A crude hue angle and a relative luminance, enough to tell two tones
    apart the way an eye does rather than the way `!=` does."""
    value = colour.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    high, low = max(r, g, b), min(r, g, b)
    span = high - low
    if span == 0:
        hue = None                      # grey: no hue to compare
    elif high == r:
        hue = (60 * ((g - b) / span)) % 360
    elif high == g:
        hue = 60 * ((b - r) / span) + 120
    else:
        hue = 60 * ((r - g) / span) + 240
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return hue, 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


@pytest.mark.parametrize("theme", list(projection.LENSES) + ["light"])
def test_no_two_semantic_tones_merely_differ_in_their_hex(theme):
    """**Distinct is not the same as distinguishable.**

    The previous check asserted five different strings, and two greens that
    differ in the last digit are five different strings. `--good` and
    `--action` in the matrix lens were the same value, which that check did
    catch; two values a shade apart it would not have. A reader separates
    tones by hue and by brightness, so that is what is compared.
    """
    t = _theme_tokens(theme)
    tones = {name: _hue_and_luminance(t[name])
             for name in ("bad", "warn", "unknown", "good", "action")}
    names = list(tones)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            (hue_a, lum_a), (hue_b, lum_b) = tones[first], tones[second]
            brighter = (max(lum_a, lum_b) + 0.05) / (min(lum_a, lum_b) + 0.05)
            if hue_a is None or hue_b is None:
                apart = brighter >= 1.6
            else:
                turn = abs(hue_a - hue_b)
                turn = min(turn, 360 - turn)
                apart = turn >= 22 or brighter >= 1.6
            assert apart, (
                f"{theme or 'default'}: --{first} {t[first]} and --{second} {t[second]} are "
                f"{turn if hue_a is not None and hue_b is not None else 0:.0f}° apart and "
                f"{brighter:.2f}:1 in brightness — a reader cannot tell them apart")


def test_the_visual_system_holds_no_purple():
    """The founder's review: no purple anywhere in the default visual system.

    UNKNOWN was violet in every lens, which collided with nothing and read as
    decoration rather than as *this could not be established*. It is steel now.
    Checked by hue rather than by hunting for particular hex values, because a
    different purple is still purple.
    """
    import re

    for theme in list(projection.LENSES) + ["light"]:
        for name, colour in _theme_tokens(theme).items():
            if not re.fullmatch(r"#[0-9a-f]{6}", colour):
                continue
            hue, _lum = _hue_and_luminance(colour)
            if hue is None:
                continue
            assert not (255 <= hue <= 330), (
                f"{theme or 'default'}: --{name} is {colour}, a purple at {hue:.0f}°")
