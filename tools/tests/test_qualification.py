"""Every attempt to obtain a qualification from something that is not evidence of one.

These are the oracles frozen in `docs/RP2.4-DESIGN-C40-qualification-identity.md`
before the module existed, so the implementation could not choose them. Two are
there because independent readers of the design found that the first versions
would have passed against an implementation doing the wrong thing.

Not shape tests. A shape test passes against a structure that lets a reader
conclude anything.
"""

import json
from dataclasses import replace

import pytest

import backend_contract
import qualification as q
from qualification import (
    CONFIGURATION_DIMENSIONS,
    KEYED_DIMENSIONS,
    UNKNOWN,
    ConfigurationIdentity,
    Equivalence,
    Invalidation,
    QualificationError,
)

#: THE CONTRACT, WRITTEN OUT HERE AND NOT IMPORTED. The parametrised cases below
#: used to take their dimensions from `qualification.CONFIGURATION_DIMENSIONS`,
#: so deleting a dimension from the implementation deleted its own tests: an
#: independent reader dropped `client` from the tuple, its cases simply stopped
#: being collected, every remaining test passed, and a configuration differing
#: only in its client then inherited `confirmed`.
#:
#: A test that derives its expectation from the implementation under test is not
#: evidence. This is the expectation.
REQUIRED_CONFIGURATION_DIMENSIONS = (
    "surface",
    "family",
    "client",
    "model_observed",
    "effort",
    "isolation",
    "network",
    "authentication_class",
)
REQUIRED_KEYED_DIMENSIONS = REQUIRED_CONFIGURATION_DIMENSIONS + ("task_class",)


def test_the_key_is_the_nine_dimensions_this_release_promised():
    """Stated independently, in this file, and compared — not imported."""
    assert tuple(CONFIGURATION_DIMENSIONS) == REQUIRED_CONFIGURATION_DIMENSIONS
    assert tuple(KEYED_DIMENSIONS) == REQUIRED_KEYED_DIMENSIONS
    assert len(REQUIRED_KEYED_DIMENSIONS) == 9
    # And the key really has nine slots, so a dimension cannot be dropped from
    # the tuple while the key keeps answering as if it were there.
    assert len(COMPLETE.key("T")) == 9


COMPLETE = ConfigurationIdentity(
    surface="a-surface",
    family="a-family",
    client="a-client",
    model_observed="a-model",
    effort="high",
    isolation="read-only",
    network="none",
    authentication_class="subscription",
    identity_method="execution_surface_turn_record",
    build="1.2.3",
)


def _row(identity: ConfigurationIdentity, task_class: str, outcome: str, **extra) -> dict:
    """One observation in the log's own shape, built from an identity."""
    tokens = [
        f"surface={identity.surface}",
        f"family={identity.family}",
        f"agent={identity.client}",
        f"model={identity.model_requested if identity.model_requested != UNKNOWN else identity.model_observed}",
        f"model_observed={identity.model_observed}",
        f"identity_method={identity.identity_method}",
        f"auth={identity.authentication_class}",
        f"effort_observed={identity.effort}",
        f"isolation={identity.isolation}",
        f"network={identity.network}",
        f"build={identity.build}",
    ]
    row = {
        "recorded_at": "2026-09-05",
        "dispatch_date": "2026-09-05",
        "configuration": " ".join(tokens),
        "task_class": task_class,
        "outcome": outcome,
        "detail": "fixture",
        "evidence": "fixture",
        "provenance": "fixture",
    }
    row.update(extra)
    return row


def _log(tmp_path, rows, name="observations.jsonl"):
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


# --- O1: the grades, and that they stay at the class they were observed at ----


def test_grades_and_stays_at_its_own_class(tmp_path):
    """One validation is provisional, two are confirmed, and a contradiction at
    the same key outranks both — and none of it reaches another task class."""
    one = _log(tmp_path, [_row(COMPLETE, "T", "validated")], "one.jsonl")
    assert q.qualifications_from_observations(one)[COMPLETE.key("T")].grade == "provisional"

    two = _log(tmp_path, [_row(COMPLETE, "T", "validated")] * 2, "two.jsonl")
    assert q.qualifications_from_observations(two)[COMPLETE.key("T")].grade == "confirmed"

    against = _log(
        tmp_path,
        [_row(COMPLETE, "T", "validated"), _row(COMPLETE, "T", "validated"),
         _row(COMPLETE, "T", "contradicted")],
        "against.jsonl",
    )
    graded = q.qualifications_from_observations(against)
    assert graded[COMPLETE.key("T")].grade == "contradicted", (
        "two validations must not outvote a contradiction; adverse evidence is not averaged away"
    )

    # And nothing reached the other class.
    grade, prior = q.grade_for(COMPLETE, "ANOTHER-T", graded, {})
    assert grade.grade == "unprobed" and grade.observations == 0
    assert prior is None


# --- O3: no inheritance across ANY keyed dimension ----------------------------


@pytest.mark.parametrize("dimension", REQUIRED_CONFIGURATION_DIMENSIONS)
def test_does_not_inherit_across_one_changed_dimension(tmp_path, dimension):
    """Change exactly one keyed dimension away from a twice-validated identity
    and the result is `unprobed`.

    Parametrised over every dimension rather than over the one that motivated
    the release: an independent reader pointed out that a fixture naming only the
    model would be satisfied by an implementation that keyed on the model alone.
    """
    log = _log(tmp_path, [_row(COMPLETE, "T", "validated")] * 2)
    graded = q.qualifications_from_observations(log)
    assert graded[COMPLETE.key("T")].grade == "confirmed"

    other = replace(COMPLETE, **{dimension: "something-else"})
    assert other.complete, "the collision fixture must itself be complete, or it proves nothing"
    grade, _prior = q.grade_for(other, "T", graded, {})
    assert grade.grade == "unprobed", (
        f"changing {dimension} left the grade at {grade.grade!r}; that dimension is not in the key"
    )
    assert grade.observations == 0


def test_a_brand_new_model_in_a_confirmed_family_does_not_inherit(tmp_path):
    """The release's motivating case, against the shipped log rather than a fixture."""
    shipped = q.qualifications_from_observations("policy/observations.jsonl")
    priors = q.priors_from_observations("policy/observations.jsonl")
    never_run = replace(COMPLETE, family="codex-cli", model_observed="a-model-nobody-ran")

    grade, prior = q.grade_for(never_run, "blind_closure_audit_cross_vendor", shipped, priors)
    assert grade.grade == "unprobed"
    assert prior is not None and prior.advisory
    assert prior.grade.grade == "confirmed", (
        "the family history must still be REPORTED; hiding it would be a different defect"
    )
    assert "not this configuration's track record" in prior.sentence()


# --- O4: incompleteness, per dimension and by provenance ---------------------


@pytest.mark.parametrize("dimension", REQUIRED_CONFIGURATION_DIMENSIONS)
def test_incomplete_in_one_dimension_answers_nothing(tmp_path, dimension):
    log = _log(tmp_path, [_row(COMPLETE, "T", "validated")] * 2)
    graded = q.qualifications_from_observations(log)
    blank = replace(COMPLETE, **{dimension: UNKNOWN})
    assert not blank.complete
    assert any(dimension in reason for reason in blank.incompleteness())
    grade, _ = q.grade_for(blank, "T", graded, {})
    assert grade.grade == "unprobed"


def test_incomplete_when_the_observed_field_holds_a_requested_value(tmp_path):
    """The shape an independent reader found getting past the first design.

    An adapter that copies the requested slug into the observed field and labels
    the provenance honestly produces a row whose observed model is PRESENT. A
    check that only looked for an absent observed model would qualify it.
    """
    copied = replace(COMPLETE, identity_method="requested_only")
    assert not copied.complete
    assert any("not observed" in reason for reason in copied.incompleteness())

    log = _log(tmp_path, [_row(copied, "T", "validated")] * 2)
    graded = q.qualifications_from_observations(log)
    assert graded == {}, "a requested-only provenance produced a per-configuration grade"
    grade, _ = q.grade_for(copied, "T", graded, {})
    assert grade.grade == "unprobed"


def test_every_shipped_observation_predating_this_release_is_prior_only():
    """The migration, asserted rather than described.

    No historical row records an observed model, an authentication class or a
    surface, so none can become a track record without inventing one. This is
    what "conservative migration" has to mean if it means anything.
    """
    rows = [json.loads(line) for line
            in open("policy/observations.jsonl", encoding="utf-8") if line.strip()]
    historical = [row for row in rows if row.get("recorded_at", "") < "2026-09-05"]
    assert len(historical) >= 41
    assert not any(q.identity_from_observation(row).complete for row in historical), (
        "a pre-2.4.0 observation was read as a complete identity; the migration invented a fact"
    )


# --- O7: equivalence never moves a grade -------------------------------------


def test_equivalence_moves_no_grade_and_only_offers_prior(tmp_path):
    log = _log(tmp_path, [_row(COMPLETE, "T", "validated")] * 2)
    graded = q.qualifications_from_observations(log)
    target = replace(COMPLETE, model_observed="renamed-model")
    alias = Equivalence(
        surface=COMPLETE.surface, family=COMPLETE.family, client=COMPLETE.client,
        from_model=COMPLETE.model_observed, to_model="renamed-model",
        reason="the vendor renamed the slug and said so",
    )
    assert q.equivalence_problems(alias) == ()

    grade, _ = q.grade_for(target, "T", graded, {})
    assert grade.grade == "unprobed", "a declared alias moved a grade"

    prior = q.prior_via_equivalence(target, "T", (alias,), graded)
    assert prior is not None and prior.advisory
    assert "DECLARED ALIAS" in prior.sentence()
    assert "stays unprobed" in prior.sentence()


@pytest.mark.parametrize("dimension", ("surface", "family", "client"))
def test_equivalence_may_not_cross_an_execution_context(tmp_path, dimension):
    log = _log(tmp_path, [_row(COMPLETE, "T", "validated")] * 2)
    graded = q.qualifications_from_observations(log)
    target = replace(COMPLETE, model_observed="renamed-model", **{dimension: "elsewhere"})
    alias = Equivalence(
        surface=COMPLETE.surface, family=COMPLETE.family, client=COMPLETE.client,
        from_model=COMPLETE.model_observed, to_model="renamed-model", reason="stated",
    )
    assert q.prior_via_equivalence(target, "T", (alias,), graded) is None, (
        f"an equivalence reached across {dimension}"
    )


def test_an_equivalence_with_no_reason_is_not_a_declaration():
    problems = q.equivalence_problems(
        Equivalence(surface="s", family="f", client="c", from_model="a", to_model="b", reason="  ")
    )
    assert any("not a declaration" in problem for problem in problems)


def test_an_undeclared_alias_merges_nothing(tmp_path):
    log = _log(tmp_path, [_row(COMPLETE, "T", "validated")] * 2)
    graded = q.qualifications_from_observations(log)
    target = replace(COMPLETE, model_observed="renamed-model")
    assert q.prior_via_equivalence(target, "T", (), graded) is None
    assert q.grade_for(target, "T", graded, {})[0].grade == "unprobed"


# --- invalidation: recovers, and cannot launder ------------------------------


def test_an_invalidation_drops_history_and_caps_the_result(tmp_path):
    """A client defect must not contradict a configuration forever, and removing
    history must not be a way to reach `confirmed`."""
    old = replace(COMPLETE, build="1.0.0")
    log = _log(tmp_path, [
        _row(old, "T", "validated"), _row(old, "T", "validated"), _row(old, "T", "contradicted"),
    ])
    assert q.qualifications_from_observations(log)[old.key("T")].grade == "contradicted"

    invalidation = Invalidation(
        surface=old.surface, family=old.family, client=old.client,
        model_observed=old.model_observed, before_build="2.0.0",
        reason="the client truncated repository reads; repaired in 2.0.0",
    )
    graded = q.qualifications_from_observations(log, invalidations=(invalidation,))
    assert graded[old.key("T")].grade == "unprobed", (
        "every observation before the boundary must be dropped, favourable and adverse alike"
    )

    # Drop ONE adverse row and leave two validations standing. Without the cap
    # this reads `confirmed`, which is a qualification obtained by deleting the
    # evidence against it.
    boundary = replace(invalidation, before_build="1.1.0")
    mixed = _log(tmp_path, [
        _row(replace(COMPLETE, build="1.0.0"), "T", "contradicted"),
        _row(COMPLETE, "T", "validated"),
        _row(COMPLETE, "T", "validated"),
    ], "mixed.jsonl")
    assert q.qualifications_from_observations(mixed)[COMPLETE.key("T")].grade == "contradicted"
    capped = q.qualifications_from_observations(mixed, invalidations=(boundary,))
    assert capped[COMPLETE.key("T")].grade == "provisional", (
        "an identity whose adverse history was invalidated must not reach `confirmed`; the cap "
        "is what stops evidence against a configuration being deleted into a qualification"
    )

    # Dropping only FAVOURABLE rows launders nothing, so the cap must not fire.
    favourable = _log(tmp_path, [
        _row(replace(COMPLETE, build="1.0.0"), "T", "validated"),
        _row(COMPLETE, "T", "validated"),
        _row(COMPLETE, "T", "validated"),
    ], "favourable.jsonl")
    uncapped = q.qualifications_from_observations(favourable, invalidations=(boundary,))
    assert uncapped[COMPLETE.key("T")].grade == "confirmed", (
        "capping an invalidation that dropped nothing adverse punishes an honest declaration"
    )


def test_an_observation_whose_build_cannot_be_ordered_is_kept(tmp_path):
    odd = replace(COMPLETE, build="nightly")
    log = _log(tmp_path, [_row(odd, "T", "contradicted")])
    invalidation = Invalidation(
        surface=odd.surface, family=odd.family, client=odd.client,
        model_observed=odd.model_observed, before_build="2.0.0", reason="stated",
    )
    graded = q.qualifications_from_observations(log, invalidations=(invalidation,))
    assert graded[odd.key("T")].grade == "contradicted", (
        "an unorderable build must not be treated as older; that is how adverse evidence "
        "disappears"
    )


def test_an_invalidation_with_no_reason_is_refused(tmp_path):
    log = _log(tmp_path, [_row(COMPLETE, "T", "validated")])
    with pytest.raises(QualificationError) as caught:
        q.qualifications_from_observations(log, invalidations=(Invalidation(
            surface="s", family="f", client="c", model_observed="m",
            before_build="2.0.0", reason="",
        ),))
    assert "deletion" in str(caught.value)


# --- O8: one mutation per keyed dimension ------------------------------------


@pytest.mark.parametrize("dropped", REQUIRED_KEYED_DIMENSIONS)
def test_mutation_per_dimension_dropping_it_from_the_key_is_caught(tmp_path, dropped):
    """Break the key one dimension at a time and show the collision fixture kills it.

    The mutant is the key with `dropped` removed. If the surviving key still
    separates the two identities, the fixture is not discriminating for that
    dimension and this test says so — which is the failure mode an independent
    reader named: *a fixture whose values make the mutant observationally
    equivalent is not evidence*.
    """
    if dropped == "task_class":
        left, right = ("T", "OTHER-T")
        first, second = COMPLETE, COMPLETE
    else:
        left = right = "T"
        first, second = COMPLETE, replace(COMPLETE, **{dropped: "something-else"})

    def key(identity, task_class):
        full = dict(zip(REQUIRED_KEYED_DIMENSIONS, identity.key(task_class)))
        return tuple(v for k, v in full.items() if k != dropped)

    assert first.key(left) != second.key(right), "the fixture does not differ under the real key"
    assert key(first, left) == key(second, right), (
        f"dropping {dropped} still distinguishes these two identities, so this fixture cannot "
        f"kill that mutant"
    )

    log = _log(tmp_path, [_row(first, left, "validated")] * 2)
    graded = q.qualifications_from_observations(log)
    grade, _ = q.grade_for(second, right, graded, {})
    assert grade.grade == "unprobed", (
        f"the real key does not separate identities differing only in {dropped}"
    )


def test_a_key_without_a_task_class_is_refused():
    with pytest.raises(QualificationError) as caught:
        COMPLETE.key(UNKNOWN)
    assert "unprobed at every other" in str(caught.value)


# --- the vocabulary is the existing one, not a second one --------------------


def test_the_grades_are_the_packs_own_grades():
    """No duplicate semantics: this module grades with `backend_contract`'s words."""
    log = "policy/observations.jsonl"
    for grade in q.qualifications_from_observations(log).values():
        assert grade.grade in backend_contract.QUALIFICATION_GRADES


def test_the_family_prior_is_the_family_keyed_derivation_itself():
    """Not a reimplementation that could drift from the routing table."""
    log = "policy/observations.jsonl"
    assert q.priors_from_observations(log) == backend_contract.grades_from_observations(log)


# --- the denylist was a list of spellings, not a rule about meaning ----------


@pytest.mark.parametrize("marker", [
    "unobserved", "not_observed", "NOT-OBSERVED", "not observed",
    "requested_only", "Requested Only", "REQUESTED-ONLY", "requested",
    "assumed", "inferred", "declared", "guessed", "presumed", "n/a", "N / A",
    "  unknown  ", "from the brief", "as requested", "default", "",
])
def test_incomplete_for_every_spelling_of_a_provenance_that_says_unobserved(marker):
    """One claim, many spellings, and the exact-string list held only some.

    An independent reader walked a COMPLETE identity carrying `unobserved` — a
    word plainly saying the identity was not observed — all the way to
    `confirmed`, because the denylist held `not_observed` and not that. Compared
    by word now, so punctuation and case cannot evade the rule.
    """
    identity = replace(COMPLETE, identity_method=marker)
    assert not identity.complete, f"{marker!r} was read as an observation of identity"
    assert any("not observed" in reason for reason in identity.incompleteness())


@pytest.mark.parametrize("marker", [
    "rollout_turn_context", "execution_surface_turn_record", "provider_response_header",
    "a-surface-nobody-has-written-yet", "turn_context",
])
def test_a_method_that_names_a_surface_is_still_admissible(marker):
    """The bound in the other direction: an ALLOWLIST of surfaces would age the
    way the model vocabulary this release replaced aged, so a surface nobody has
    heard of must still be admissible."""
    assert replace(COMPLETE, identity_method=marker).complete


def test_the_unobserved_marker_that_got_past_the_first_denylist_grades_nothing(tmp_path):
    """End to end, on the exact input an independent reader used."""
    unobserved = replace(COMPLETE, identity_method="unobserved")
    log = _log(tmp_path, [_row(unobserved, "T", "validated")] * 2)
    assert q.qualifications_from_observations(log) == {}


# --- a key stated twice is the same ambiguity with better punctuation --------


def test_a_repeated_key_makes_the_identity_incomplete(tmp_path):
    """The parser builds a mapping, so the last occurrence silently wins.

    Appending `model_observed=` to a string that already carries one changes
    which configuration the observation is filed under, and nothing says a
    choice was made. Found by attacking configuration serialisation against
    qualification rather than either alone.
    """
    row = _row(COMPLETE, "T", "validated")
    row["configuration"] += " model_observed=SOMETHING-ELSE"
    identity = q.identity_from_observation(row)
    assert not identity.complete
    assert any("appears 2 times" in reason for reason in identity.incompleteness())

    log = _log(tmp_path, [row, dict(row)])
    assert q.qualifications_from_observations(log) == {}, (
        "an ambiguous configuration string produced a per-configuration grade"
    )


def test_a_repeated_key_is_refused_even_when_both_values_agree():
    """Refusing only on disagreement was considered and rejected: a writer that
    emits a key twice is defective either way, and a rule that tolerates the
    harmless case has to decide which case it is."""
    row = _row(COMPLETE, "T", "validated")
    row["configuration"] += f" model_observed={COMPLETE.model_observed}"
    assert not q.identity_from_observation(row).complete


def test_a_clean_configuration_string_is_still_read():
    """The bound in the other direction: the guard must not refuse every row."""
    assert q.identity_from_observation(_row(COMPLETE, "T", "validated")).complete
    for line in open("policy/observations.jsonl", encoding="utf-8"):
        if line.strip():
            q.identity_from_observation(json.loads(line))  # must not raise


def test_the_structured_identity_carries_what_the_string_cannot(tmp_path):
    """An identifier containing a space, round-tripped through an observation."""
    spaced = replace(COMPLETE, model_observed="MODEL WITH SPACES")
    row = _row(COMPLETE, "T", "validated")
    row["identity"] = {"model_observed": "MODEL WITH SPACES"}
    identity = q.identity_from_observation(row)
    assert identity.model_observed == "MODEL WITH SPACES"
    assert identity.complete

    log = _log(tmp_path, [row, dict(row)])
    graded = q.qualifications_from_observations(log)
    assert graded[spaced.key("T")].grade == "confirmed"
    # And the prefix gets nothing.
    assert q.grade_for(replace(COMPLETE, model_observed="MODEL"), "T", graded, {})[0].grade == \
        "unprobed"


def test_a_structured_identity_field_nothing_reads_is_refused(tmp_path):
    row = _row(COMPLETE, "T", "validated")
    row["identity"] = {"vibes": "good"}
    with pytest.raises(QualificationError) as caught:
        q.identity_from_observation(row)
    assert "nothing reads" in str(caught.value)


# --- RP2.4.1 R3: one normalisation boundary for every identity ingestion path ---

@pytest.mark.parametrize("spelling", [
    "unknown", "UNKNOWN", "Unknown", "  unknown  ", "un_known", "un-known", "UN KNOWN", "",
])
@pytest.mark.parametrize("dimension", [
    "effort", "model_observed", "surface", "family", "client",
    "isolation", "network", "authentication_class",
])
def test_unknown_reads_the_same_through_both_identity_paths(spelling, dimension):
    """A dimension nobody established cannot become established by its spelling.

    2.4.0 normalised `unknown` in the packed configuration string and did not
    normalise it in the structured mapping, so the same honest answer completed
    an identity through one supported path and refused through the other.
    """
    complete = dict(surface="codex-cli", family="gpt-6", client="0.153.3",
                    model_observed="a-model", effort="high", isolation="workspace-write",
                    network="denied", authentication_class="subscription",
                    identity_method="turn_context")
    declared = dict(complete, **{dimension: spelling})
    structured = q.identity_from_observation({"identity": declared})
    assert not structured.complete, (
        f"{dimension}={spelling!r} completed an identity through the structured path")
    assert any(dimension in reason for reason in structured.incompleteness())

    # THE PACKED PATH TOO, which this test's name claims and did not do. An
    # independent reader restored the old packed normalisation and all of these
    # cases still passed, because only the mapping was exercised — and the
    # defect that survived in `surface` was on the packed side. Named keys
    # differ between the two spellings, which is why the mapping is built here
    # rather than reusing the one above.
    packed_key = {"effort": "effort_observed", "client": "agent",
                  "authentication_class": "auth"}.get(dimension, dimension)
    tokens = {"surface": "codex-cli", "family": "gpt-6", "agent": "0.153.3",
              "model_observed": "a-model", "effort_observed": "high",
              "isolation": "workspace-write", "network": "denied",
              "auth": "subscription", "identity_method": "turn_context"}
    tokens[packed_key] = spelling if spelling.strip() else "unknown"
    packed = q.identity_from_configuration(
        " ".join(f"{key}={value}" for key, value in tokens.items()))
    assert not packed.complete, (
        f"{dimension}={spelling!r} completed an identity through the packed string")


def test_the_structured_path_still_carries_a_real_value():
    """The repair must not swallow values that ARE established."""
    declared = dict(surface="codex-cli", family="gpt-6", client="0.153.3",
                    model_observed="a model with spaces", effort="xhigh",
                    isolation="workspace-write", network="denied",
                    authentication_class="subscription", identity_method="turn_context")
    identity = q.identity_from_observation({"identity": declared})
    assert identity.complete
    assert identity.model_observed == "a model with spaces"
    assert identity.effort == "xhigh"


def test_a_structured_unknown_effort_cannot_reach_a_grade(tmp_path):
    """The consumer-visible consequence: no affirmative qualification."""
    declared = dict(surface="codex-cli", family="gpt-6", client="0.153.3",
                    model_observed="gpt-6-nova", effort="unknown",
                    isolation="workspace-write", network="denied",
                    authentication_class="subscription", identity_method="turn_context")
    log = tmp_path / "observations.jsonl"
    log.write_text("".join(
        json.dumps({"recorded_at": "2026-09-05", "configuration": "", "identity": declared,
                    "task_class": "implementation", "outcome": "validated",
                    "detail": f"row {n}", "evidence": "fixture", "provenance": "fixture"}) + "\n"
        for n in (1, 2)))
    graded = q.qualifications_from_observations(log)
    assert not graded, "a configuration whose effort is unknown reached a per-configuration grade"


def test_pool_id_is_normalised_through_the_same_boundary():
    """`surface` and `pool_id` are the two keys `identity_from_configuration`
    reads for itself. `surface` was found carrying its own copy of the rule by
    an independent reader; `pool_id` sits on the same line and is pinned here so
    the next reader does not have to find it too."""
    base = ("surface=codex-cli family=gpt-6 agent=0.153.3 model_observed=a-model "
            "effort_observed=high isolation=workspace-write network=denied "
            "auth=subscription identity_method=turn_context")
    for spelling in ("unknown", "UNKNOWN", "un_known", "Unknown", ""):
        identity = q.identity_from_configuration(f"{base} pool_id={spelling}")
        assert identity.pool_id == q.UNKNOWN, (
            f"pool_id={spelling!r} was carried as an established pool")
    assert q.identity_from_configuration(f"{base} pool_id=real-pool").pool_id == "real-pool"

    # A SPACED SPELLING IS NOT A NORMALISATION CASE HERE. The packed string is
    # space-separated, so `pool_id=UN KNOWN` truncates at the space and leaves a
    # bare token — which the parser already refuses as an ambiguity, marking the
    # whole identity incomplete. That is the documented tokenisation bound, and
    # the safe answer; a value with a space travels in the structured mapping.
    spaced = q.identity_from_configuration(f"{base} pool_id=UN KNOWN")
    assert spaced.ambiguous_tokens and not spaced.complete


@pytest.mark.parametrize("absent", [None, "", False, True, "unknown", "UNKNOWN",
                                    "un_known", "UN KNOWN", "   "])
@pytest.mark.parametrize("dimension", ["effort", "model_observed", "surface", "family",
                                       "client", "isolation", "network",
                                       "authentication_class"])
def test_explicit_absence_never_inherits_a_packed_value(dimension, absent):
    """O7. A key the writer bothered to include is a statement about that
    dimension. If it says nothing, the dimension is UNKNOWN — never whatever an
    earlier source happened to say.

    A row carrying `identity: {"effort": null}` — the natural JSON for *the
    surface did not report it* — had that key DROPPED before the overlay, so the
    packed string's `effort=high` survived, the identity came out COMPLETE, and
    two such rows graded `confirmed` for a configuration nothing had
    established. The string `"unknown"` refused correctly on the same path,
    which is what made it look covered.
    """
    packed = ("surface=codex-cli family=gpt-6 agent=0.153.3 model_observed=a-model "
              "model=a-model effort_observed=high isolation=workspace-write "
              "network=denied auth=subscription identity_method=turn_context")
    identity = q.identity_from_observation(
        {"configuration": packed, "identity": {dimension: absent}})
    assert not identity.complete, (
        f"{dimension}={absent!r} inherited a packed value and completed an identity")
    assert any(dimension in reason for reason in identity.incompleteness()), (
        identity.incompleteness())


def test_a_real_structured_value_still_overrides_the_packed_one():
    """The other direction: the overlay exists so a row can say what the packed
    string cannot hold."""
    packed = ("surface=codex-cli family=gpt-6 agent=0.153.3 model_observed=a-model "
              "model=a-model effort_observed=high isolation=workspace-write "
              "network=denied auth=subscription identity_method=turn_context")
    identity = q.identity_from_observation(
        {"configuration": packed, "identity": {"model_observed": "a model with spaces"}})
    assert identity.complete
    assert identity.model_observed == "a model with spaces"
    assert identity.effort == "high"


def test_the_word_unknown_is_unestablished_in_the_identity_itself(tmp_path):
    """The persisted path already read the WORD "unknown" as unestablished,
    through `normalised_identity_value`. The identity's own completeness check
    compared against the sentinel instead, so the same dimension was incomplete
    on one path and complete on the other — this pack's recurrence class inside
    the boundary built to end it. Found as a non-blocking observation by an
    independent certification and folded in deliberately, because the direction
    of the error is over-claiming qualification.
    """
    def identity(effort):
        return q.ConfigurationIdentity(
            surface="s", family="f", client="c", model_observed="m", effort=effort,
            isolation="i", network="none", authentication_class="subscription",
            identity_method="turn_record")

    for spelling in ("unknown", "UNKNOWN", " Unknown ", ""):
        assert not identity(spelling).complete, f"{spelling!r} counted as established"
        assert any("effort" in reason for reason in identity(spelling).incompleteness())
    assert identity("xhigh").complete
