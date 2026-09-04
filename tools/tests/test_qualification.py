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


@pytest.mark.parametrize("dimension", CONFIGURATION_DIMENSIONS)
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


@pytest.mark.parametrize("dimension", CONFIGURATION_DIMENSIONS)
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


@pytest.mark.parametrize("dropped", KEYED_DIMENSIONS)
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
        full = dict(zip(KEYED_DIMENSIONS, identity.key(task_class)))
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
