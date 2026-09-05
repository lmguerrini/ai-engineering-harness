"""The sixteen ways a routing decision goes wrong, and one lifecycle that must not.

Deterministic fixtures. Each is a situation somebody will actually be in, written
so that the wrong implementation fails it — not so that the right one passes,
which any fixture does.

Two rules the fixtures obey, because the release's own audits kept finding them
broken. **No expectation is derived from the implementation under test**: every
expected value is written out, and the mutation cases assert the mutant and the
subject disagree rather than asserting the subject alone. And **no fixture makes
its mutant observationally equivalent**: where a case exists to separate two
identities it asserts they differ under the real key first.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

import continuation
import model_discovery
import qualification as q
import routing
from backend_contract import TaskClassGrade
from qualification import UNKNOWN, ConfigurationIdentity, Equivalence
from routing import (
    AVAILABLE,
    CRITICAL,
    PROBE,
    ROUTINE,
    UNAVAILABLE,
    AvailabilityObservation,
    Candidate,
    Derivation,
    Role,
    availability_for,
    design_audit_route,
    eligibility,
)

PACK = Path(__file__).resolve().parent.parent.parent

KNOWN = ConfigurationIdentity(
    surface="surface-a", family="family-a", client="client-a", model_observed="known-model",
    effort="high", isolation="read-only", network="none",
    authentication_class="subscription", identity_method="execution_surface_turn_record",
    build="1.0.0",
)


def _row(identity, task_class, outcome, **extra):
    tokens = [
        f"surface={identity.surface}", f"family={identity.family}", f"agent={identity.client}",
        f"model={identity.model_observed}", f"model_observed={identity.model_observed}",
        f"identity_method={identity.identity_method}",
        f"auth={identity.authentication_class}", f"effort_observed={identity.effort}",
        f"isolation={identity.isolation}", f"network={identity.network}",
        f"build={identity.build}",
    ]
    row = {"recorded_at": "2026-09-05", "dispatch_date": "2026-09-05",
           "configuration": " ".join(tokens), "task_class": task_class, "outcome": outcome,
           "detail": "fixture", "evidence": "fixture", "provenance": "fixture"}
    row.update(extra)
    return row


def _log(tmp_path, rows, name="observations.jsonl"):
    path = tmp_path / name
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def _candidate(identity, grade, *, validated=0, contradicted=0, availability=AVAILABLE,
               task_class="review", producer=None, provider="vendor-a", session=None):
    # THE SESSION DEFAULTS PER PRODUCER, not to one shared string. Every
    # candidate carried the same session IDENTIFIER, which says they all ran in
    # the same session — so once the router began comparing seated readers
    # against each other rather than only against the subject, two genuinely
    # independent candidates were correctly refused and the FIXTURE was what was
    # wrong. A fixture that says two readings share a session is testing that
    # case whether or not it meant to.
    producer = producer or identity.model_observed
    return Candidate(
        identity=identity, task_class=task_class,
        grade=TaskClassGrade(task_class, grade, observations=validated + contradicted,
                             validated=validated, contradicted=contradicted),
        availability=availability,
        derivation=Derivation(producer=producer, session=session or f"session-of-{producer}",
                              provider=provider, surface=identity.surface),
    )


# =============================================================================
# 1-16: the adversarial rehearsals
# =============================================================================


def test_01_a_known_qualified_model_is_qualified_and_only_where_it_was_probed(tmp_path):
    log = _log(tmp_path, [_row(KNOWN, "review", "validated")] * 2
                         + [_row(KNOWN, "implement", "validated")])
    graded = q.qualifications_from_observations(log)
    assert graded[KNOWN.key("review")].grade == "confirmed"
    assert graded[KNOWN.key("implement")].grade == "provisional"
    assert q.grade_for(KNOWN, "audit", graded, {})[0].grade == "unprobed"


def test_02_a_new_model_in_a_known_family_starts_unprobed(tmp_path):
    log = _log(tmp_path, [_row(KNOWN, "review", "validated")] * 2)
    graded = q.qualifications_from_observations(log)
    priors = q.priors_from_observations(log)
    newcomer = replace(KNOWN, model_observed="brand-new-model")
    grade, prior = q.grade_for(newcomer, "review", graded, priors)
    assert grade.grade == "unprobed" and grade.observations == 0
    assert prior is not None and prior.advisory
    assert prior.grade.grade == "confirmed", "the family history must still be reported"
    assert not eligibility(_candidate(newcomer, "unprobed"), purpose=ROUTINE).allowed


def test_03_a_completely_new_family_starts_unprobed_with_no_prior_at_all(tmp_path):
    log = _log(tmp_path, [_row(KNOWN, "review", "validated")] * 2)
    graded = q.qualifications_from_observations(log)
    priors = q.priors_from_observations(log)
    stranger = replace(KNOWN, family="family-nobody-has", model_observed="stranger")
    grade, prior = q.grade_for(stranger, "review", graded, priors)
    assert grade.grade == "unprobed"
    assert prior is None, "a family with no history must not produce a prior out of nothing"


def test_04_the_same_model_at_a_different_effort_is_a_different_configuration(tmp_path):
    log = _log(tmp_path, [_row(KNOWN, "review", "validated")] * 2)
    graded = q.qualifications_from_observations(log)
    louder = replace(KNOWN, effort="low")
    assert KNOWN.key("review") != louder.key("review")
    assert q.grade_for(louder, "review", graded, {})[0].grade == "unprobed"


def test_05_the_same_model_under_different_isolation_is_a_different_configuration(tmp_path):
    """The largest block of evidence in the shipped log is exactly this: six
    configurations that never reached a model under kernel confinement, and two
    that validated under it."""
    log = _log(tmp_path, [_row(KNOWN, "review", "validated")] * 2)
    graded = q.qualifications_from_observations(log)
    confined = replace(KNOWN, isolation="kernel-confinement")
    assert q.grade_for(confined, "review", graded, {})[0].grade == "unprobed"

    networked = replace(KNOWN, network="allowed")
    assert q.grade_for(networked, "review", graded, {})[0].grade == "unprobed"


def test_06_an_unavailable_model_is_not_eligible_however_strong_its_evidence(tmp_path):
    refused = _candidate(KNOWN, "confirmed", validated=9, availability=UNAVAILABLE)
    for purpose in routing.PURPOSES:
        assert not eligibility(refused, purpose=purpose).allowed
    assert refused.disposition == UNAVAILABLE


def test_07_a_stale_discovery_document_is_reported_and_answers_nothing(tmp_path):
    """The live case: a document written by a newer client listed a model the
    installed client refused with a 400."""
    document = tmp_path / "cache.json"
    document.write_text(json.dumps(
        {"client_version": "0.153.1", "models": [{"slug": "listed-but-refused"}]}), "utf-8")
    reading = model_discovery.read(document)
    assert "listed-but-refused" in reading.identifiers()
    assert reading.skew("0.149.0"), "a document from another client must be reported as skewed"

    identity = replace(KNOWN, model_observed="listed-but-refused")
    refusal = AvailabilityObservation(identity=identity, state=UNAVAILABLE,
                                      observed_at="2026-09-05", build="0.149.0",
                                      detail="provider refused: client too old")
    state, _ = availability_for(identity, set(), [refusal], build="0.149.0")
    assert state == UNAVAILABLE, "being listed must not outrank being refused"


def test_08_a_model_that_disappears_after_planning_loses_availability_not_evidence(tmp_path):
    log = _log(tmp_path, [_row(KNOWN, "review", "validated")] * 2)
    graded = q.qualifications_from_observations(log)
    before = model_discovery.read(_log_json(tmp_path, ["known-model", "other"], "before.json"))
    after = model_discovery.read(_log_json(tmp_path, ["other"], "after.json"))
    assert model_discovery.merge(after, before)["disappeared"] == ("known-model",)

    # The evidence survives; the eligibility does not, once a dispatch is refused.
    assert graded[KNOWN.key("review")].grade == "confirmed"
    gone = _candidate(KNOWN, "confirmed", validated=2, availability=UNAVAILABLE)
    assert not eligibility(gone, purpose=ROUTINE).allowed


def _log_json(tmp_path, slugs, name):
    path = tmp_path / name
    path.write_text(json.dumps({"client_version": "1",
                                "models": [{"slug": s} for s in slugs]}), "utf-8")
    return path


def test_09_a_requested_model_never_becomes_an_observed_one(tmp_path):
    """Two shapes: the observed field absent, and the observed field filled from
    the request and labelled honestly. The second got past an earlier design."""
    absent = replace(KNOWN, model_observed=UNKNOWN)
    copied = replace(KNOWN, identity_method="requested_only")
    for identity in (absent, copied):
        assert not identity.complete
        log = _log(tmp_path, [_row(identity, "review", "validated")] * 2, "x.jsonl")
        assert q.qualifications_from_observations(log) == {}
        assert q.grade_for(identity, "review", {}, {})[0].grade == "unprobed"


def test_10_a_renamed_model_does_not_inherit_and_a_declared_alias_only_advises(tmp_path):
    log = _log(tmp_path, [_row(KNOWN, "review", "validated")] * 2)
    graded = q.qualifications_from_observations(log)
    renamed = replace(KNOWN, model_observed="known-model-v2")

    assert q.grade_for(renamed, "review", graded, {})[0].grade == "unprobed"
    assert q.prior_via_equivalence(renamed, "review", (), graded) is None

    alias = Equivalence(surface=KNOWN.surface, family=KNOWN.family, client=KNOWN.client,
                        from_model="known-model", to_model="known-model-v2",
                        reason="the vendor published the rename")
    prior = q.prior_via_equivalence(renamed, "review", (alias,), graded)
    assert prior is not None and prior.advisory
    assert q.grade_for(renamed, "review", graded, {})[0].grade == "unprobed", (
        "the alias moved a grade"
    )


def test_11_family_evidence_without_model_evidence_answers_unprobed(tmp_path):
    """The shipped log, which is entirely of this shape."""
    graded = q.qualifications_from_observations(PACK / "policy" / "observations.jsonl")
    priors = q.priors_from_observations(PACK / "policy" / "observations.jsonl")
    unseen = ConfigurationIdentity(
        surface="codex-cli", family="codex-cli", client="codex-exec",
        model_observed="a-model-that-has-never-run", effort="xhigh", isolation="read-only",
        network="none", authentication_class="subscription",
        identity_method="execution_surface_turn_record")
    grade, prior = q.grade_for(unseen, "blind_closure_audit_cross_vendor", graded, priors)
    assert grade.grade == "unprobed"
    assert prior.grade.grade == "confirmed"
    assert "advisory" in prior.sentence()


def test_12_a_provisional_model_may_take_a_probe_and_not_a_critical_leg(tmp_path):
    thin = _candidate(KNOWN, "provisional", validated=1)
    assert eligibility(thin, purpose=PROBE).allowed
    assert eligibility(thin, purpose=ROUTINE).allowed
    assert not eligibility(thin, purpose=CRITICAL).allowed


def test_13_an_independently_qualified_design_auditor_is_seated(tmp_path):
    subject = Derivation(producer="the-implementer", session="s1", provider="vendor-a")
    primary = _candidate(replace(KNOWN, model_observed="m1"), "confirmed", validated=3,
                         producer="w1", provider="vendor-b")
    falsifier = _candidate(replace(KNOWN, model_observed="m2"), "confirmed", validated=2,
                           producer="w2", provider="vendor-c")
    report = design_audit_route([primary, falsifier], task_class="review", subject=subject)
    assert report.complete
    assert report.as_dict()["seats"][0]["chosen"]["disposition"] == "QUALIFIED"


def test_14_the_implementer_is_refused_as_its_own_independent_reader(tmp_path):
    subject = Derivation(producer="the-implementer", session="s1", provider="vendor-a")
    itself = _candidate(KNOWN, "confirmed", validated=5, producer="the-implementer",
                        session="s2", provider="vendor-a")
    report = design_audit_route([itself], task_class="review", subject=subject,
                                roles=(Role("READER"),))
    assert report.seats[0]["candidate"] is None
    assert any("never closes its own finding" in reason
               for reason in report.seats[0]["reasons"])


def test_15_the_capability_closes_with_no_vendor_continuation_state_at_all(tmp_path):
    """Delete everything a vendor could be holding; the position must be
    reconstructible from the durable record alone."""
    record_path = tmp_path / "CONTINUATION.json"
    continuation.save(continuation.ContinuationRecord(
        capability="C40", updated_at=continuation.now(),
        actionable=("record the probe outcome",),
        record_path="PROGRESS.md",
    ), record_path)

    # ONE SURFACE, DERIVED BEFORE AND AFTER. This used to delete the vendor state
    # before deriving anything, so a `derive` that read it would never have been
    # caught: an independent reader replaced `derive` with one that returns
    # TERMINAL when the file is present, and every test still passed.
    vendor = tmp_path / "vendor-state"
    vendor.mkdir()
    (vendor / "thread.json").write_text(
        '{"resume": "abc", "status": "complete", "capability": "C40"}', encoding="utf-8")

    with_vendor = continuation.derive(continuation.load(record_path), relative_to=tmp_path)

    import shutil

    shutil.rmtree(vendor)
    assert not vendor.exists()

    without_vendor = continuation.derive(continuation.load(record_path), relative_to=tmp_path)
    assert with_vendor.state == without_vendor.state, (
        f"removing the vendor state changed the derived position: "
        f"{with_vendor.state} -> {without_vendor.state}"
    )

    record = continuation.load(record_path)
    report = continuation.derive(record, relative_to=tmp_path)
    assert record.capability == "C40"
    assert record.actionable == ("record the probe outcome",), (
        "removing every vendor artifact changed what the durable record says"
    )
    # SILENT_IDLE is the right answer and is the pack's own word for it: work is
    # authorised, nothing is in the way and nothing is running, so the next
    # action is owed NOW. That is exactly the position a coordinator resumes
    # into, and it was reconstructed with no vendor artifact in existence.
    assert report.state == continuation.State.SILENT_IDLE
    assert not record.terminal


def test_16_vendor_continuation_contradicting_the_durable_record_loses(tmp_path):
    """A vendor thread claiming the work is finished, against a record that says
    it is not. The pack reads the record."""
    record_path = tmp_path / "CONTINUATION.json"
    continuation.save(continuation.ContinuationRecord(
        capability="C40", updated_at=continuation.now(),
        actionable=("the falsification round is not closed",),
        record_path="PROGRESS.md",
    ), record_path)

    # THE SAME SURFACE test 15 uses, not a different filename. Test 16 wrote
    # `vendor-thread.json` while test 15 used `vendor-state/thread.json`, so a
    # dependency on either was invisible to both.
    vendor = tmp_path / "vendor-state"
    vendor.mkdir()
    (vendor / "thread.json").write_text(json.dumps(
        {"status": "complete", "capability": "C40", "summary": "all done",
         "terminal": True}), encoding="utf-8")

    contradicted = continuation.derive(continuation.load(record_path), relative_to=tmp_path)
    import shutil

    shutil.rmtree(vendor)
    agreed = continuation.derive(continuation.load(record_path), relative_to=tmp_path)
    assert contradicted.state == agreed.state, (
        "a vendor artifact claiming completion changed the derived state"
    )
    vendor.mkdir()
    (vendor / "thread.json").write_text(json.dumps({"status": "complete"}), encoding="utf-8")

    report = continuation.derive(continuation.load(record_path), relative_to=tmp_path)
    assert report.state != continuation.State.TERMINAL, (
        "the vendor's claim of completion reached the derived state"
    )
    assert continuation.load(record_path).actionable == (
        "the falsification round is not closed",)
    assert not continuation.load(record_path).terminal, (
        "the vendor's claim of completion reached the durable state"
    )
    # And the dependency is checked by OBSERVATION rather than by grepping for a
    # filename: a substring assertion passes against any module that reads the
    # file under a name spelled differently.
    assert report.state == contradicted.state == agreed.state


# =============================================================================
# O12 / O13: the lifecycle, rehearsed against a synthetic consumer
# =============================================================================


def _frozen_release(tmp_path):
    """A real, verifiable, QUALIFIED_AND_FROZEN release root, built here.

    The rehearsal used to pin the pack under construction with three of the four
    identity fields missing, so `capability_open` answered `NOT_READY` with a
    `LEGACY` pin on every single case — and the tests passed, because they only
    ever inspected the routing component. An independent reader ran the reports
    and found all six refused. A rehearsal that never opens the capability is not
    a rehearsal of adoption.

    So this builds one: a git checkout carrying a manifest whose digest is
    computed over its own tracked tree, at a revision that exists. Built rather
    than borrowed, because pointing at a real release on this machine would make
    the rehearsal depend on this machine.
    """
    import subprocess

    import pack_pin

    root = tmp_path / "frozen-release"
    (root / "tools").mkdir(parents=True)
    (root / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    (root / "tools" / "placeholder.py").write_text("# a release has files\n", encoding="utf-8")

    def git(*args):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                       timeout=120)

    git("init", "--quiet", "--initial-branch", "main")
    git("config", "user.name", "Ordinary Human")
    git("config", "user.email", "human@example.invalid")
    git("config", "commit.gpgsign", "false")

    manifest = {
        "pack": "runtime-pack-2", "version": "9.9.9", "state": "QUALIFIED_AND_FROZEN",
        "tree_digest_sha256": "", "digest_excludes": "PACK_MANIFEST.json",
        "digest_algorithm": "sha256-framed-v1",
    }
    (root / "PACK_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    git("add", "-A")
    git("commit", "--quiet", "-m", "seed")
    digest, count = pack_pin.tree_digest(root)
    manifest["tree_digest_sha256"] = digest
    manifest["digest_file_count"] = count
    (root / "PACK_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    git("add", "-A")
    git("commit", "--quiet", "-m", "record the digest")
    sha = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True,
                         capture_output=True, text=True, timeout=60).stdout.strip()

    # The manifest is excluded from its own digest, so recording it changed
    # nothing the digest covers. Asserted rather than assumed: a fixture whose
    # pin does not verify is the defect this whole helper exists to repair.
    assert pack_pin.verify_pin(root, expect_version="9.9.9", expect_sha=sha,
                               expect_digest=digest,
                               expect_state="QUALIFIED_AND_FROZEN") == []
    return root, sha, digest


def _synthetic_project(tmp_path, *, name, observations, discovery_slugs):
    release, sha, digest = _frozen_release(tmp_path)
    root = tmp_path / name
    root.mkdir()
    (root / "PROJECT.yaml").write_text(
        "project:\n"
        f"  name: {name}\n"
        '  repo_path: "."\n'
        "pack:\n"
        f'  root_path: "{release}"\n'
        '  version_adopted: "9.9.9"\n'
        f'  sha_adopted: "{sha}"\n'
        f'  tree_digest_sha256: "{digest}"\n'
        '  state_adopted: "QUALIFIED_AND_FROZEN"\n'
        "requires:\n"
        "  routing: true\n"
        "routing:\n"
        "  observations: observations.jsonl\n"
        "  discovery: discovery.json\n"
        '  dispatching_client: "1.0.0"\n'
        "adapters: []\n"
        "capabilities:\n"
        "  - id: C1\n",
        encoding="utf-8")
    (root / "observations.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in observations), encoding="utf-8")
    (root / "discovery.json").write_text(json.dumps(
        {"client_version": "1.0.0",
         "models": [{"slug": slug} for slug in discovery_slugs]}), encoding="utf-8")
    return root


#: Exactly the shipped observations, so the rehearsal starts where a real
#: adopting project starts: with family history and no complete identity.
def _shipped_rows():
    return [json.loads(line) for line
            in (PACK / "policy" / "observations.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]


def test_the_full_adoption_rehearsal_closes_from_durable_records_alone(tmp_path):
    """capability open -> discovery -> route -> probe -> record -> interrupt ->
    reconstruct -> close, with no vendor state in existence."""
    import capability_open

    rows = [row for row in _shipped_rows() if row.get("recorded_at", "") < "2026-09-05"]
    root = _synthetic_project(tmp_path, name="demo-synthetic", observations=rows,
                              discovery_slugs=["newest-model", "older-model"])

    # 1. capability open reports the routing component and does not block on it.
    report = capability_open.open_capability(root / "PROJECT.yaml", capability="C1")
    # THE AGGREGATE ANSWER, not one component of it. This asserted the routing
    # component alone while every report was NOT_READY on a LEGACY pin.
    assert report.ready, (
        "the capability did not open:\n" + report.render()
    )
    component = report.component("routing")
    assert component is not None and component.state == capability_open.VERIFIED
    assert any("NO observation carries a complete configuration identity" in note
               for note in component.notes), (
        "the honest state of a freshly adopted project is not being reported"
    )

    # 2. discovery finds both models, neither of which is thereby available.
    reading = model_discovery.read(root / "discovery.json")
    assert set(reading.identifiers()) == {"newest-model", "older-model"}

    # 3. every configuration is unprobed, so the design-audit route needs a probe.
    graded = q.qualifications_from_observations(root / "observations.jsonl")
    assert graded == {}
    newest = replace(KNOWN, model_observed="newest-model")
    older = replace(KNOWN, model_observed="older-model")
    subject = Derivation(producer="the-implementer", session="s1", provider="vendor-a")
    candidates = [_candidate(newest, "unprobed", producer="w-new", provider="vendor-b"),
                  _candidate(older, "unprobed", producer="w-old", provider="vendor-c")]

    refused = design_audit_route(candidates, task_class="review", subject=subject)
    assert not refused.complete, "an unprobed model took a seat without a declared probe"
    assert all(seat["candidate"] is None for seat in refused.seats)

    # WITH probes allowed the ORDINARY seats fill and the MANDATORY CROSS-PROVIDER
    # ONE DOES NOT. This test asserted `routed.complete` and therefore depended on
    # a defect: a probe was filling the leg `policy/hitl-matrix.md` row 12 governs.
    # An independent reader found the defect AND that this rehearsal expected it,
    # which is the sharper half of the finding — a rehearsal that encodes the bug
    # is worse than no rehearsal.
    routed = design_audit_route(candidates, task_class="review", subject=subject,
                                allow_probe=True)
    seats = {seat["role"].name: seat for seat in routed.seats}
    assert seats["PRIMARY_DESIGN_READER"]["candidate"] is not None
    assert any("DECLARED PROBE" in reason
               for reason in seats["PRIMARY_DESIGN_READER"]["reasons"])
    assert seats["INDEPENDENT_FALSIFIER"]["candidate"] is None, (
        "a probe filled the mandatory cross-provider leg"
    )
    assert not routed.complete, (
        "the route reported itself complete with its mandatory independent leg unfilled; the "
        "capability escalates to a human (row 12) rather than substituting"
    )

    # 4. the probe runs and is recorded — for the configuration it tested only.
    with (root / "observations.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_row(newest, "review", "validated")) + "\n")
    graded = q.qualifications_from_observations(root / "observations.jsonl")
    assert graded[newest.key("review")].grade == "provisional"
    assert q.grade_for(newest, "implement", graded, {})[0].grade == "unprobed", (
        "one successful run made a model universally qualified"
    )

    # AND ONE PROBE DOES NOT PROMOTE IT ANYWHERE THAT MATTERS. The ladder is
    # climbed by evidence, and the two rungs it does not reach are stated apart
    # because they are different rules: an UNPROBED configuration may not fill a
    # seat that requires an independent provider, and a PROVISIONAL one may not
    # fill a CRITICAL seat, which is what row 16 governs.
    probed = _candidate(newest, "provisional", validated=1, producer="w-new",
                        provider="vendor-b")
    critical = design_audit_route([probed], task_class="review", subject=subject,
                                  allow_probe=True,
                                  roles=(Role("MANDATORY", purpose=CRITICAL),))
    assert critical.seats[0]["candidate"] is None, (
        "one probe promoted a configuration into a critical-domain seat"
    )

    unprobed_still = _candidate(older, "unprobed", producer="w-old", provider="vendor-c")
    cross = design_audit_route([unprobed_still], task_class="review", subject=subject,
                               allow_probe=True,
                               roles=(Role("CROSS", require_distinct_provider=True),))
    assert cross.seats[0]["candidate"] is None, (
        "a declared probe filled a seat that exists to give an independent reading"
    )

    # 5. interruption, then reconstruction from the durable record alone.
    record_path = root / "CONTINUATION.json"
    continuation.save(continuation.ContinuationRecord(
        capability="C1", updated_at=continuation.now(),
        actionable=("close C1",), record_path="PROGRESS.md"), record_path)
    rebuilt = continuation.load(record_path)
    assert rebuilt.capability == "C1"
    assert rebuilt.actionable == ("close C1",)
    # Work owed and nothing in the way: the pack's own word for that is
    # SILENT_IDLE, a defect rather than a resting state, which is precisely what
    # a coordinator resuming after an interruption should be told.
    assert continuation.derive(rebuilt, relative_to=root).state == \
        continuation.State.SILENT_IDLE

    # 6. close.
    continuation.save(replace(rebuilt, actionable=(), terminal=True,
                              updated_at=continuation.now()), record_path)
    closed = continuation.derive(continuation.load(record_path), relative_to=root)
    assert closed.state == continuation.State.TERMINAL


@pytest.mark.parametrize("situation", [
    "unavailable", "unprobed", "provisional", "outranked", "no_capacity",
])
def test_the_rehearsal_closes_without_the_newest_model(tmp_path, situation):
    """The same capability, five ways the newest model is not the answer."""
    rows = [row for row in _shipped_rows() if row.get("recorded_at", "") < "2026-09-05"]
    root = _synthetic_project(tmp_path, name=f"demo-{situation}", observations=rows,
                              discovery_slugs=["newest-model", "older-model"])
    newest = replace(KNOWN, model_observed="newest-model")
    older = replace(KNOWN, model_observed="older-model")
    subject = Derivation(producer="the-implementer", session="s1", provider="vendor-a")

    if situation == "unavailable":
        candidates = [_candidate(newest, "confirmed", validated=3, availability=UNAVAILABLE,
                                 producer="w-new", provider="vendor-b"),
                      _candidate(older, "confirmed", validated=2, producer="w-old",
                                 provider="vendor-c")]
        expected = "older-model"
    elif situation == "unprobed":
        candidates = [_candidate(newest, "unprobed", producer="w-new", provider="vendor-b"),
                      _candidate(older, "confirmed", validated=2, producer="w-old",
                                 provider="vendor-c")]
        expected = "older-model"
    elif situation == "provisional":
        candidates = [_candidate(newest, "provisional", validated=1, producer="w-new",
                                 provider="vendor-b"),
                      _candidate(older, "confirmed", validated=4, producer="w-old",
                                 provider="vendor-c")]
        expected = "older-model"
    elif situation == "outranked":
        candidates = [_candidate(newest, "confirmed", validated=2, producer="w-new",
                                 provider="vendor-b"),
                      _candidate(older, "confirmed", validated=9, producer="w-old",
                                 provider="vendor-c")]
        expected = "older-model"
    else:  # provider capacity unavailable: nothing from that provider answers
        candidates = [_candidate(older, "confirmed", validated=2, producer="w-old",
                                 provider="vendor-c")]
        expected = "older-model"

    report = design_audit_route(candidates, task_class="review", subject=subject,
                               roles=(Role("READER"),))
    chosen = report.seats[0]["candidate"]
    assert chosen is not None, f"no seat filled in the {situation} case; the capability stalls"
    assert chosen.identity.model_observed == expected, (
        f"the {situation} case chose {chosen.identity.model_observed}"
    )

    # And the capability still opens.
    import capability_open

    opened = capability_open.open_capability(root / "PROJECT.yaml", capability="C1")
    assert opened.ready, "the capability did not open:\n" + opened.render()
    assert opened.component("routing").state == capability_open.VERIFIED


def test_the_rehearsal_refuses_rather_than_substituting_when_nothing_qualifies(tmp_path):
    """`Unavailability is never authorization`, as an executable claim."""
    subject = Derivation(producer="the-implementer", session="s1", provider="vendor-a")
    only_unprobed = _candidate(replace(KNOWN, model_observed="newest-model"), "unprobed",
                               producer="w", provider="vendor-b")
    report = design_audit_route([only_unprobed], task_class="review", subject=subject,
                                roles=(Role("MANDATORY", purpose=CRITICAL),), allow_probe=True)
    assert report.seats[0]["candidate"] is None
    assert any("rows 12 and 16" in reason for reason in report.seats[0]["reasons"])
