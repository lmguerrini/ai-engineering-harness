"""The ten conditions the founder's row-7 authorisation of D26 was granted on.

`DECISIONS.md` D26 narrows a governance control. The founder authorised that
narrowing against a specific, enumerated set of invariants — not against the
word "D26" — and this module is those invariants as executable oracles.

Its purpose is not to re-test the modules. Each condition already has oracles in
`test_qualification.py`, `test_routing.py`, `test_model_discovery.py` and
`test_backend_contract.py`, and this module deliberately does not duplicate
their coverage. What it adds is a **single place that fails when the decision is
broadened past what was authorised**, so that a later contributor who widens the
pooling, or lets a family grade reach a configuration, or admits an unobserved
identity, breaks the record of the authorisation rather than passing quietly and
leaving the authorisation standing over semantics it was never granted for.

The conditions are quoted from the authorisation in
`docs/RP2.4-FOUNDER-AUTHORISATIONS.md`. Every assertion here is over behaviour.
Nothing here reads prose, because a document that authorises something and a
test that reads that document agree with each other by construction.
"""

import json
from dataclasses import replace

import pytest

import backend_contract
import model_discovery
import qualification as q
import routing as r
from qualification import UNKNOWN, ConfigurationIdentity, Equivalence


#: A complete, observed identity. Every field established, provenance naming a
#: real observation surface. Written out rather than built from the module's own
#: dimension tuple, so that removing a dimension from the key does not silently
#: remove it from this fixture too.
COMPLETE = dict(
    surface="codex-cli",
    family="OPENAI",
    client="codex/0.153.3",
    model_observed="a-model-nothing-has-run",
    effort="high",
    isolation="read-only",
    network="restricted",
    authentication_class="subscription",
    identity_method="rollout turn_context",
    build="0.153.3",
    pool_id="pool-a",
    model_requested="a-model-nothing-has-run",
)


def _observation(**overrides):
    """One log row whose identity is complete unless a test breaks it."""
    identity = dict(COMPLETE)
    row = {
        "task_class": overrides.pop("task_class", "design_falsification_review"),
        "outcome": overrides.pop("outcome", "validated"),
        "qualification_basis": overrides.pop("qualification_basis", "field"),
        # The family-keyed PRIOR derivation reads the configuration STRING only
        # — it is `backend_contract.grades_from_observations`, unchanged — so a
        # row carrying its family in the structured mapping alone would make
        # every prior in this module UNKNOWN and the family-inheritance oracles
        # inert. The shipped log carries both; so does this.
        "configuration": f"family={identity['family']}",
    }
    identity.update(overrides)
    # `pool_id` is a ROW-level field in the shipped log, not an identity field.
    row["pool_id"] = identity.pop("pool_id")
    row["identity"] = identity
    return row


def _log(tmp_path, rows):
    """The shipped log's shape: one JSON object per line, not a wrapper object."""
    path = tmp_path / "observations.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""))
    return path


# ---------------------------------------------------------------------------
# Condition 1 — dynamic discovery with no frozen model allowlist
# ---------------------------------------------------------------------------

def test_1_discovery_names_no_model_and_reads_an_identifier_it_has_never_seen(tmp_path):
    """A model vocabulary in Core is the thing this release removed."""
    source = tmp_path / "models.json"
    source.write_text(json.dumps({"data": [
        {"id": "a-generation-that-does-not-exist-yet-9", "object": "model"},
    ]}))
    reading = model_discovery.read(source)
    assert reading.identifiers() == ("a-generation-that-does-not-exist-yet-9",), (
        "an unseen identifier must survive discovery, or Core carries a vocabulary again"
    )


def test_1_no_core_module_holds_a_model_vocabulary():
    """The falsifier for condition 1: a literal slug list reappearing in Core."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    for module in ("model_discovery.py", "qualification.py", "routing.py"):
        source = (root / module).read_text()
        # `DEFAULT_FIELD_MAP` names FIELDS. A model name would be a value.
        for banned in ("gpt-4", "gpt-5", "gpt-6", "claude-3", "claude-4", "claude-5",
                       "o1-", "o3-", "sonnet", "haiku", "opus", "astra"):
            assert banned not in source.lower(), (
                f"{module} names the model {banned!r}. Discovery reads FIELD names; a model "
                f"name in Core is the closed allowlist this release removed"
            )


# ---------------------------------------------------------------------------
# Condition 2 — a newly discovered configuration begins UNPROBED
# ---------------------------------------------------------------------------

def test_2_a_configuration_with_no_observations_of_its_own_is_unprobed(tmp_path):
    identity = ConfigurationIdentity(**COMPLETE)
    graded = q.qualifications_from_observations(_log(tmp_path, []))
    grade, _prior = q.grade_for(identity, "design_falsification_review", graded, {})
    assert grade.grade == "unprobed", (
        f"a configuration nothing has dispatched graded {grade.grade!r}; the authorisation "
        f"was granted on it beginning unprobed"
    )


# ---------------------------------------------------------------------------
# Conditions 3 and 4 — family history is advisory prior, never a track record
# ---------------------------------------------------------------------------

def test_3_a_family_with_a_confirmed_history_leaves_a_new_model_unprobed(tmp_path):
    """THE HEADLINE INVARIANT. The defect this release opened on, in one test."""
    sibling = dict(COMPLETE, model_observed="a-model-that-has-run")
    rows = [
        _observation(**dict(sibling, task_class="design_falsification_review")),
        _observation(**dict(sibling, task_class="design_falsification_review")),
        _observation(**dict(sibling, task_class="design_falsification_review")),
    ]
    source = _log(tmp_path, rows)
    graded = q.qualifications_from_observations(source)
    priors = q.priors_from_observations(source)

    established = q.grade_for(
        ConfigurationIdentity(**sibling), "design_falsification_review", graded, priors)
    assert established[0].grade == "confirmed", "fixture is inert: the sibling never qualified"

    newcomer = ConfigurationIdentity(**COMPLETE)
    grade, prior = q.grade_for(newcomer, "design_falsification_review", graded, priors)
    assert grade.grade == "unprobed", (
        f"a model with NO observations of its own graded {grade.grade!r} inside a family whose "
        f"history is confirmed. This is the defect the release exists to close"
    )
    assert prior is not None, "the family history must still be VISIBLE, or a reader has nothing"
    assert prior.grade.grade == "confirmed", "the prior must report what the family history is"


def test_4_the_prior_is_labelled_as_the_family_and_not_as_this_configuration(tmp_path):
    """Advisory means the reader cannot mistake it for a track record."""
    sibling = dict(COMPLETE, model_observed="a-model-that-has-run")
    source = _log(tmp_path, [_observation(**sibling), _observation(**sibling)])
    priors = q.priors_from_observations(source)
    _grade, prior = q.grade_for(
        ConfigurationIdentity(**COMPLETE), "design_falsification_review", {}, priors)
    sentence = prior.sentence().lower()
    assert "family" in sentence and prior.family == COMPLETE["family"], (
        f"the prior does not name itself as family history: {prior.sentence()!r}"
    )


def test_4_a_declared_alias_surfaces_evidence_as_prior_and_moves_no_grade(tmp_path):
    """The laundering path two readers found: a grade transferred on a reason string."""
    source_model = dict(COMPLETE, model_observed="an-older-identifier")
    source = _log(tmp_path, [_observation(**source_model), _observation(**source_model)])
    graded = q.qualifications_from_observations(source)

    target = ConfigurationIdentity(**COMPLETE)
    alias = Equivalence(
        surface=COMPLETE["surface"], family=COMPLETE["family"], client=COMPLETE["client"],
        from_model="an-older-identifier", to_model=COMPLETE["model_observed"],
        reason="the vendor renamed it and the rollout reports the new name")
    prior = q.prior_via_equivalence(
        target, "design_falsification_review", (alias,), graded)
    assert prior is not None, "fixture is inert: the alias resolved to nothing"
    assert prior.grade.grade == "confirmed", "the aliased evidence must be visible as prior"

    grade, _ = q.grade_for(target, "design_falsification_review", graded, {})
    assert grade.grade == "unprobed", (
        f"a declared alias moved a grade onto the target ({grade.grade!r}). An alias renames a "
        f"model; it does not transfer a track record"
    )


# ---------------------------------------------------------------------------
# Condition 5 — an UNKNOWN or unobserved execution identity cannot qualify
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dimension", sorted(q.CONFIGURATION_DIMENSIONS))
def test_5_unknown_in_any_keyed_dimension_cannot_positively_qualify(tmp_path, dimension):
    broken = dict(COMPLETE)
    broken[dimension] = UNKNOWN
    rows = [_observation(**broken), _observation(**broken), _observation(**broken)]
    graded = q.qualifications_from_observations(_log(tmp_path, rows))
    assert graded == {}, (
        f"three validated observations with {dimension}=UNKNOWN produced a grade. An identity "
        f"missing a keyed dimension does not identify a configuration"
    )
    grade, _ = q.grade_for(
        ConfigurationIdentity(**broken), "design_falsification_review", graded, {})
    assert grade.grade == "unprobed"


@pytest.mark.parametrize("provenance", sorted(q.UNOBSERVED_PROVENANCE - {""}))
def test_5_a_provenance_that_says_it_was_not_observed_cannot_qualify(tmp_path, provenance):
    broken = dict(COMPLETE, identity_method=provenance)
    rows = [_observation(**broken), _observation(**broken)]
    assert q.qualifications_from_observations(_log(tmp_path, rows)) == {}, (
        f"identity_method={provenance!r} reached a grade. It states the identity was not observed"
    )


def test_5_a_backend_record_without_an_observed_model_is_not_qualified():
    """The same rule at the other reader, where the original defect returned True."""
    record = backend_contract.BackendRecord(
        identity=backend_contract.BackendIdentity(
            family="OPENAI", client="codex-cli", client_version="0.153.3",
            model_requested="a-model", model_observed=UNKNOWN,
            authentication_class="subscription"),
        capability={"design_falsification_review": backend_contract.TaskClassGrade(
            task_class="design_falsification_review", grade="confirmed",
            observations=7, validated=7)},
    )
    assert record.grade_for("design_falsification_review").grade == "confirmed", (
        "fixture is inert: the family-keyed grade this guard must survive is not present"
    )
    assert record.qualified_for("design_falsification_review") is False, (
        "a record with no OBSERVED model reported qualified. This returned True on seven "
        "observations, none of which recorded a model, and is why the release exists"
    )


# ---------------------------------------------------------------------------
# Condition 6 — the execution surface outranks the worker's self-report
# ---------------------------------------------------------------------------

def test_6_what_the_surface_observed_outranks_what_the_dispatch_requested(tmp_path):
    """A worker cannot qualify a configuration by naming a model it did not run."""
    row = _observation(**dict(COMPLETE,
                              model_requested="a-model-the-worker-claims",
                              model_observed="the-model-the-surface-reported"))
    identity = q.identity_from_observation(row)
    assert identity.model_observed == "the-model-the-surface-reported"
    assert identity.model_requested == "a-model-the-worker-claims"

    graded = q.qualifications_from_observations(_log(tmp_path, [row, row]))
    keys = list(graded)
    assert len(keys) == 1
    assert "the-model-the-surface-reported" in keys[0], (
        "the grade was filed under something other than the observed model"
    )
    assert "a-model-the-worker-claims" not in keys[0], (
        "a requested model reached the qualification key. The request is not the observation"
    )


def test_6_a_configuration_string_naming_only_a_request_observes_nothing(tmp_path):
    """THE PATH A REAL LOG ROW TAKES. A mutant that made the parser fall back from
    the observed model to the requested one survived an oracle written only over
    the dataclass, which is the fixture rule one level up: a guard that never sees
    the code path it guards is not a guard."""
    # THE SHIPPED KEY NAMES. `model=` is the REQUEST and `model_observed=` is the
    # observation — a fixture spelling the request `model_requested=` parses to
    # UNKNOWN, which made an earlier version of this oracle pass against a subject
    # that did fall back, because there was nothing to fall back to.
    parsed = q.identity_from_configuration(
        "family=OPENAI client=codex-cli model=a-model-the-worker-asked-for auth=subscription")
    assert parsed.model_requested == "a-model-the-worker-asked-for", (
        "fixture is inert: the requested model did not parse, so a fall-back would have "
        "nothing to fall back to"
    )
    assert parsed.model_observed == UNKNOWN, (
        f"a configuration string naming only a REQUEST produced model_observed="
        f"{parsed.model_observed!r}. The request is not the observation, and this is the "
        f"substitution the whole release is about"
    )
    assert not parsed.complete, "an identity with no observed model must not be complete"

    row = {"configuration": "family=OPENAI client=codex-cli surface=codex-cli "
                            "model=a-model-the-worker-asked-for effort_observed=high "
                            "isolation=read-only network=restricted "
                            "auth=subscription identity_method=rollout build=0.153.3",
           "task_class": "design_falsification_review", "outcome": "validated",
           "qualification_basis": "field"}
    log = tmp_path / "observations.jsonl"
    log.write_text("\n".join([json.dumps(row)] * 3) + "\n")
    assert q.qualifications_from_observations(log) == {}, (
        "three validated rows naming only a requested model produced a per-configuration "
        "grade; nothing observed which model ran"
    )


def test_6_no_property_falls_back_from_observed_to_requested():
    """The falsifier: a convenience that substitutes one for the other."""
    identity = ConfigurationIdentity(
        **dict(COMPLETE, model_observed=UNKNOWN, model_requested="something-plausible"))
    assert identity.model_observed == UNKNOWN, (
        "model_observed fell back to model_requested; that substitution is the release's subject"
    )
    assert not identity.complete


# ---------------------------------------------------------------------------
# Condition 7 — availability and qualification are separate axes
# ---------------------------------------------------------------------------

def _candidate(grade_name, availability, task_class="design_falsification_review"):
    return r.Candidate(
        identity=ConfigurationIdentity(**COMPLETE),
        task_class=task_class,
        grade=backend_contract.TaskClassGrade(
            task_class=task_class, grade=grade_name,
            observations=2 if grade_name == "confirmed" else 0,
            validated=2 if grade_name == "confirmed" else 0),
        availability=availability,
        derivation=r.Derivation(producer="a-worker", session="s1", provider="P", fresh=True),
    )


def test_7_a_qualified_configuration_that_is_unavailable_is_not_dispatchable():
    verdict = r.eligibility(_candidate("confirmed", r.UNAVAILABLE), purpose=r.ROUTINE)
    assert verdict.allowed is False, (
        "a confirmed but unavailable configuration was eligible; availability is the other axis"
    )


def test_7_an_available_unprobed_configuration_is_not_qualified_by_being_available():
    candidate = _candidate("unprobed", r.AVAILABLE)
    assert r.eligibility(candidate, purpose=r.ROUTINE).allowed is False, (
        "an unprobed configuration became eligible for routine work by being available"
    )
    assert r.eligibility(candidate, purpose=r.CRITICAL).allowed is False, (
        "an unprobed configuration became eligible for critical work by being available"
    )


@pytest.mark.parametrize("purpose", [r.PROBE, r.ROUTINE, r.CRITICAL])
def test_7_an_unavailable_configuration_is_refused_for_every_purpose(purpose):
    """INCLUDING A PROBE. A mutant removing the availability refusal survived an
    oracle that only checked ROUTINE, because ROUTINE carries a second
    availability test of its own — so the removal changed nothing there and
    changed everything for a probe, which is the dispatch most likely to be aimed
    at a configuration nothing has established."""
    verdict = r.eligibility(_candidate("confirmed", r.UNAVAILABLE), purpose=purpose)
    assert verdict.allowed is False, (
        f"a configuration observed to REFUSE a dispatch was eligible for {purpose}. Evidence of "
        f"what it can do does not make it startable"
    )
    assert any("refused" in reason for reason in verdict.reasons), (
        f"the refusal for {purpose} does not cite the observed refusal: {verdict.reasons}"
    )


def test_7_the_two_axes_do_not_share_a_derivation(tmp_path):
    """Availability comes from availability observations, not from grades."""
    identity = ConfigurationIdentity(**COMPLETE)
    rows = [_observation(**COMPLETE), _observation(**COMPLETE)]
    graded = q.qualifications_from_observations(_log(tmp_path, rows))
    grade, _ = q.grade_for(identity, "design_falsification_review", graded, {})
    assert grade.grade == "confirmed", "fixture is inert"
    state, _why = r.availability_for(identity, (), ())
    assert state == r.UNKNOWN, (
        f"availability read {state!r} from an empty availability log while the qualification "
        f"was confirmed. A grade is not a dispatch precondition"
    )


# ---------------------------------------------------------------------------
# Condition 8 — the governed dimensions stay governed
# ---------------------------------------------------------------------------

#: WRITTEN OUT, NOT IMPORTED. Importing the module's own tuple would make this
#: test agree with any change to it, which is the one thing it must not do.
AUTHORISED_DIMENSIONS = (
    "surface", "family", "client", "model_observed", "effort",
    "isolation", "network", "authentication_class",
)
AUTHORISED_KEY = AUTHORISED_DIMENSIONS + ("task_class",)


def test_8_the_key_is_exactly_the_nine_dimensions_that_were_authorised():
    assert tuple(q.CONFIGURATION_DIMENSIONS) == AUTHORISED_DIMENSIONS, (
        "the configuration dimensions changed. The row-7 authorisation was granted on these "
        "eight plus task class; changing the set is a new governance question"
    )
    assert tuple(q.KEYED_DIMENSIONS) == AUTHORISED_KEY


@pytest.mark.parametrize("dimension", [d for d in AUTHORISED_DIMENSIONS])
def test_8_each_authorised_dimension_actually_separates_two_configurations(tmp_path, dimension):
    """A dimension in the tuple but absent from the key would pool silently."""
    other = dict(COMPLETE)
    other[dimension] = COMPLETE[dimension] + "-different"
    rows = [_observation(**COMPLETE), _observation(**COMPLETE),
            _observation(**other), _observation(**other)]
    graded = q.qualifications_from_observations(_log(tmp_path, rows))
    assert len(graded) == 2, (
        f"two configurations differing only in {dimension} produced {len(graded)} grade(s); "
        f"they must not pool"
    )


def test_8_effort_variants_of_one_model_do_not_inherit_each_other(tmp_path):
    """Named separately because it is the case a reader is most likely to call a gap."""
    low = dict(COMPLETE, effort="low")
    high = dict(COMPLETE, effort="high")
    source = _log(tmp_path, [_observation(**low), _observation(**low)])
    graded = q.qualifications_from_observations(source)
    assert q.grade_for(ConfigurationIdentity(**low),
                       "design_falsification_review", graded, {})[0].grade == "confirmed"
    assert q.grade_for(ConfigurationIdentity(**high),
                       "design_falsification_review", graded, {})[0].grade == "unprobed", (
        "evidence at one effort qualified another effort of the same model"
    )


def test_8_a_grade_at_one_task_class_is_unprobed_at_every_other(tmp_path):
    source = _log(tmp_path, [
        _observation(task_class="design_falsification_review"),
        _observation(task_class="design_falsification_review")])
    graded = q.qualifications_from_observations(source)
    identity = ConfigurationIdentity(**COMPLETE)
    assert q.grade_for(identity, "design_falsification_review", graded, {})[0].grade == "confirmed"
    assert q.grade_for(identity, "blind_release_authority_audit",
                       graded, {})[0].grade == "unprobed"


# ---------------------------------------------------------------------------
# Condition 9 — pooling stays bounded to the two authorised non-identity fields
# ---------------------------------------------------------------------------

AUTHORISED_POOLING = ("build", "pool_id")


def test_9_pooling_is_bounded_to_exactly_the_two_authorised_fields():
    assert tuple(q.NON_IDENTITY_FIELDS) == AUTHORISED_POOLING, (
        f"evidence now pools across {tuple(q.NON_IDENTITY_FIELDS)}. The founder authorised "
        f"pooling across {AUTHORISED_POOLING} and nothing else; widening this is a new row-7 "
        f"question, not an implementation detail"
    )
    for field in AUTHORISED_POOLING:
        assert field not in q.CONFIGURATION_DIMENSIONS, (
            f"{field} is both pooled and keyed, which cannot both be true"
        )


@pytest.mark.parametrize("field", AUTHORISED_POOLING)
def test_9_the_authorised_fields_pool_and_are_still_reported(tmp_path, field):
    a = dict(COMPLETE); a[field] = "one"
    b = dict(COMPLETE); b[field] = "two"
    graded = q.qualifications_from_observations(
        _log(tmp_path, [_observation(**a), _observation(**b)]))
    assert len(graded) == 1, (
        f"observations differing only in {field} did not pool; the authorisation was granted "
        f"on them pooling"
    )
    assert list(graded.values())[0].grade == "confirmed", (
        "pooling that does not actually combine the evidence is not pooling"
    )
    rendered = ConfigurationIdentity(**a).render()
    assert field in rendered and "not keyed" in rendered, (
        f"{field} pools but is not reported as carried-and-excluded; the authorisation was "
        f"granted on it being visible"
    )


# ---------------------------------------------------------------------------
# Condition 10 — audit independence constraints are intact
# ---------------------------------------------------------------------------

def test_10_a_producer_never_closes_its_own_finding():
    same = r.Derivation(producer="w", session="s1", provider="P", fresh=True)
    problems = r.independence_problems(same, replace(same, session="s2"))
    assert problems, "a reader with the same producer as the work was accepted as independent"


def test_10_independence_fails_closed_on_an_unrecorded_producer():
    problems = r.independence_problems(
        r.Derivation(producer=UNKNOWN, fresh=True), r.Derivation(producer="w"))
    assert problems, "an unrecorded producer was read as a different one"


def test_10_a_whitespace_producer_does_not_establish_independence():
    problems = r.independence_problems(
        r.Derivation(producer="   ", session="s1", fresh=True),
        r.Derivation(producer="   ", session="s2"))
    assert problems, "a whitespace producer compared unequal to itself and passed"


def test_10_a_cross_provider_leg_refuses_two_readers_from_one_provider():
    problems = r.independence_problems(
        r.Derivation(producer="a", session="s1", provider="P", fresh=True),
        r.Derivation(producer="b", session="s2", provider="P"),
        require_distinct_provider=True)
    assert problems, "two models from one provider satisfied a cross-provider leg"


def test_10_a_probe_never_fills_a_mandatory_independent_leg():
    falsifier = [role for role in r.DESIGN_AUDIT_ROLES
                 if role.require_distinct_provider][0]
    assert falsifier.accepts_a_probe is False, (
        f"{falsifier.name} accepts a probe. A probe is how an unqualified configuration "
        f"acquires its first evidence; it cannot also be the independent leg"
    )


def test_10_independence_is_not_decided_by_configuration_equality():
    """Key equality is wrong in BOTH directions, and an authorisation rests on that."""
    one_session_two_classes = r.independence_problems(
        r.Derivation(producer="w", session="s", provider="P"),
        r.Derivation(producer="w", session="s", provider="P"))
    assert one_session_two_classes, (
        "the same session reading its own work was accepted because a task class differed"
    )
    two_fresh_readings = r.independence_problems(
        r.Derivation(producer="a", provider="P", fresh=True),
        r.Derivation(producer="b", provider="P", fresh=True))
    assert not two_fresh_readings, (
        "two genuinely independent fresh readings were refused because their derivations look "
        "alike; identical shape is what an independent blind reading LOOKS like"
    )
