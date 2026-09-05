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


def _unprobed_candidate(model, *, prior=None, provider="P"):
    """A candidate in the ONLY state that actually carries a prior.

    `grade_for` returns a `Prior` exactly when the configuration has no grade of
    its own, so a candidate holding one is always `unprobed`. Every earlier
    oracle for "the prior ranks nothing" built candidates graded `provisional` or
    `confirmed` — states in which production never attaches a prior at all — so
    the guarantee was tested where it cannot apply and untested where it always
    does. An independent reader ranked on the prior and passed 135 tests.
    """
    from dataclasses import replace as _replace

    return r.Candidate(
        identity=_replace(ConfigurationIdentity(**COMPLETE), model_observed=model),
        task_class="design_falsification_review",
        grade=backend_contract.TaskClassGrade("design_falsification_review"),
        availability=r.AVAILABLE,
        prior=prior,
        discovered=True,
        derivation=r.Derivation(producer=model, session=f"session-of-{model}",
                                provider=provider, fresh=True))


def _loud_prior(grade_name="confirmed", observations=15):
    return q.Prior(
        family=COMPLETE["family"], task_class="design_falsification_review",
        grade=backend_contract.TaskClassGrade(
            "design_falsification_review", grade_name,
            observations=observations, validated=observations),
        because="the family has history and this configuration has none")


def test_3_a_family_prior_does_not_order_two_unprobed_candidates():
    """CONDITION 3'S OTHER HALF. `Prior` is documented display-only: it "enters no
    ranking, satisfies no eligibility test and breaks no tie", and D26 says it
    ranks nothing. The grade half of that was executable; the ranking half was
    prose."""
    with_history = _unprobed_candidate("a-model-whose-family-has-history",
                                       prior=_loud_prior())
    without = _unprobed_candidate("a-model-whose-family-has-none")

    assert r._rank(with_history) == r._rank(without), (
        f"a family prior changed a candidate's rank: {r._rank(with_history)} vs "
        f"{r._rank(without)}. That is the family bucket back under a new name, deciding "
        f"which newly discovered model gets probed first")


@pytest.mark.parametrize("order", ["as given", "reversed"])
@pytest.mark.parametrize("louder", ["confirmed", "provisional"])
def test_3_attaching_a_family_prior_does_not_change_which_candidate_is_seated(order, louder):
    """THE DISCRIMINATING COMPARISON, and not the one a first draft reached for.

    Asserting that both pool ORDERS seat the same candidate is wrong: two
    identically-ranked unprobed candidates tie, and a tie broken by input order
    is a tie the prior did not break. The subject does that today and it is not a
    violation.

    What must hold is that the ANSWER DOES NOT MOVE WHEN THE PRIOR MOVES. So the
    same pool, in the same order, is routed twice — once with a loud family prior
    on one candidate and once with none — and the seat must not change. Run in
    both orders because a rank function consulting the prior looks identical in
    whichever order already agreed with it.
    """
    subject = r.Derivation(producer="the-implementer", session="s0", provider="Z")

    def seat_of(pool):
        report = r.design_audit_route(pool, task_class="design_falsification_review",
                                      subject=subject, allow_probe=True)
        for seat in report.seats:
            if seat["role"].name == "PRIMARY_DESIGN_READER" and seat["candidate"] is not None:
                return seat["candidate"].identity.model_observed
        return None

    without = [_unprobed_candidate("model-a", provider="P"),
               _unprobed_candidate("model-b", provider="Q")]
    with_prior = [_unprobed_candidate("model-a", prior=_loud_prior(louder), provider="P"),
                  _unprobed_candidate("model-b", provider="Q")]
    if order == "reversed":
        without = list(reversed(without))
        with_prior = list(reversed(with_prior))

    assert seat_of(without) is not None, "the fixture is inert: no seat was filled at all"
    assert seat_of(with_prior) == seat_of(without), (
        f"attaching a {louder!r} family prior to one unprobed candidate changed the seat from "
        f"{seat_of(without)!r} to {seat_of(with_prior)!r}. The family's history decided which "
        f"newly discovered model was probed first, which is the ranking the prior is "
        f"forbidden to do")


def test_3_the_prior_is_carried_and_reported_even_though_it_ranks_nothing():
    """Display-only is not the same as discarded. If the prior stopped reaching the
    reader, the two tests above would pass for the wrong reason."""
    candidate = _unprobed_candidate("a-model", prior=_loud_prior())
    assert candidate.prior is not None
    assert "PRIOR" in candidate.prior.sentence()
    assert "advisory" in candidate.prior.sentence()


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


#: THE MARKERS THE AUTHORISATION NAMES, WRITTEN OUT. This was parametrised over
#: `q.UNOBSERVED_PROVENANCE` — the implementation's own set — so an edit to that
#: set silently edited the oracle's cases with it. An independent reader replaced
#: one marker with a different word: `identity_method="none"` then reached
#: `confirmed`, and the whole suite passed. An oracle whose cases come from its
#: subject is this pack's own definition of not-evidence, and this file is where
#: that mattered most.
AUTHORISED_UNOBSERVED_MARKERS = (
    "asrequested", "assumed", "declared", "default", "fromthebrief", "guessed",
    "inferred", "na", "none", "notobserved", "presumed", "requested",
    "requestedonly", "unknown", "unobserved",
)


def test_5_the_unobserved_marker_set_is_the_one_the_authorisation_was_granted_on():
    """Removing a marker admits an identity the authorisation excluded; adding one
    is a widening nobody authorised either. Equality, not containment."""
    assert tuple(sorted(q.UNOBSERVED_PROVENANCE - {""})) == AUTHORISED_UNOBSERVED_MARKERS, (
        f"the unobserved-provenance vocabulary changed to "
        f"{tuple(sorted(q.UNOBSERVED_PROVENANCE - {''}))}. The row-7 authorisation was granted "
        f"on {AUTHORISED_UNOBSERVED_MARKERS}; changing it is a new governance question"
    )


@pytest.mark.parametrize("provenance", AUTHORISED_UNOBSERVED_MARKERS)
def test_5_a_provenance_that_says_it_was_not_observed_cannot_qualify(tmp_path, provenance):
    broken = dict(COMPLETE, identity_method=provenance)
    rows = [_observation(**broken), _observation(**broken)]
    assert q.qualifications_from_observations(_log(tmp_path, rows)) == {}, (
        f"identity_method={provenance!r} reached a grade. It states the identity was not observed"
    )


def test_5_an_unrelated_structured_field_does_not_resolve_a_lossy_string(tmp_path):
    """CONDITION 5, AT THE PARSER. Found by an independent reader of the candidate.

    The configuration string is space-separated `key=value`, so a model
    identifier containing a space is truncated at the space and its evidence
    lands under the PREFIX. That is refused: the identity goes incomplete. But
    the structured mapping cleared EVERY ambiguity note whenever ANY field was
    supplied — so adding an unrelated `build` made the truncated identity
    complete, and two such rows graded `confirmed` for a configuration nothing
    had ever dispatched. The transfer this release exists to prevent, reached
    through the parser rather than through the key.
    """
    lossy = ("surface=codex-cli family=OPENAI agent=codex-exec model=M "
             "model_observed=MODEL WITH SPACES identity_method=rollout auth=subscription "
             "effort_observed=high isolation=read-only network=restricted build=1.0")

    alone = q.identity_from_observation({"configuration": lossy})
    assert not alone.complete, "the fixture is inert: the lossy string was not refused"
    assert alone.model_observed == "MODEL", (
        "the fixture is inert: the identifier did not truncate, so nothing was lost")

    unrelated = q.identity_from_observation(
        {"configuration": lossy, "identity": {"build": "1.0"}})
    assert not unrelated.complete, (
        f"an unrelated structured field made a lossy string complete, with "
        f"model_observed={unrelated.model_observed!r}. A mapping resolves the ambiguity it "
        f"states and no other")

    row = {"configuration": lossy, "identity": {"build": "1.0"},
           "task_class": "design_falsification_review", "outcome": "validated",
           "qualification_basis": "field"}
    log = tmp_path / "observations.jsonl"
    log.write_text("\n".join([json.dumps(row)] * 3) + "\n")
    assert q.qualifications_from_observations(log) == {}, (
        "three rows whose model identifier was truncated at a space produced a grade")


def test_5_the_mapping_does_resolve_the_ambiguity_it_actually_states(tmp_path):
    """The other half, so the repair is not merely a refusal.

    The structured mapping exists BECAUSE a packed string cannot carry an
    identifier with a space. A row that states the identifier in the mapping has
    resolved the ambiguity, and must be usable — otherwise the repair breaks the
    one case the mapping was added for.
    """
    lossy = ("surface=codex-cli family=OPENAI agent=codex-exec model=M "
             "model_observed=MODEL WITH SPACES identity_method=rollout auth=subscription "
             "effort_observed=high isolation=read-only network=restricted build=1.0")
    stated = q.identity_from_observation(
        {"configuration": lossy, "identity": {"model_observed": "MODEL WITH SPACES"}})
    assert stated.complete, (
        f"a row that states the whole identifier in the mapping is still incomplete: "
        f"{stated.incompleteness()}")
    assert stated.model_observed == "MODEL WITH SPACES"


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
