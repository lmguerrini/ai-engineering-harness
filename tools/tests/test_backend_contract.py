"""The three inferences a routing record must not permit.

Not "does the dataclass hold the fields" — a shape test passes against a
structure that lets a reader conclude anything. Every test here is an attempt
to obtain a positive qualification from something that is not evidence of one.
"""

from pathlib import Path

import pytest

from backend_contract import (
    AUTHENTICATION_CLASSES,
    QUALIFICATION_GRADES,
    UNKNOWN,
    BackendContractError,
    BackendIdentity,
    BackendRecord,
    TaskClassGrade,
    grades_from_observations,
    parse_configuration,
    record_for,
)

PACK_ROOT = Path(__file__).resolve().parent.parent.parent
OBSERVATIONS = PACK_ROOT / "policy" / "observations.jsonl"


# --- availability is never qualification (D8) --------------------------------


def test_an_available_backend_is_not_thereby_qualified():
    record = BackendRecord(identity=BackendIdentity(family="claude-cli"), availability="available")
    assert not record.qualified_for("analytical_code_review")
    assert record.grade_for("analytical_code_review").grade == "unprobed"


def test_qualified_for_cannot_be_moved_by_availability():
    """Stated as a difference rather than as an assertion about one value: if
    availability reached the answer at all, these two would differ."""
    graded = {("f", "t"): TaskClassGrade("t", "confirmed", observations=2, validated=2)}
    available = record_for("f", graded, availability="available")
    absent = record_for("f", graded, availability="unreachable")
    assert available.qualified_for("t") == absent.qualified_for("t") is True

    ungraded_available = record_for("f", {}, availability="available")
    assert ungraded_available.qualified_for("t") is False


def test_a_grade_that_asserts_capability_needs_an_observation():
    """A grade is a claim about evidence. Without one it is a preference."""
    for grade in ("provisional", "confirmed", "contradicted"):
        with pytest.raises(BackendContractError) as caught:
            TaskClassGrade("t", grade, observations=0)
        assert "availability is not evidence" in str(caught.value)


def test_unprobed_and_environmental_unknown_need_no_observation():
    """The two honest zero-evidence states, and they must stay reachable."""
    assert TaskClassGrade("t", "unprobed").observations == 0
    assert TaskClassGrade("t", "environmental-unknown").grade == "environmental-unknown"


# --- permission is never capability ------------------------------------------


def test_permission_state_does_not_reach_the_qualification_answer():
    graded = {("f", "review"): TaskClassGrade("review", "unprobed")}
    permitted = record_for("f", graded, identity=BackendIdentity(permission_state="read-write"))
    assert not permitted.qualified_for("review")
    assert permitted.identity.permission_state == "read-write"


# --- a grade at one class is unprobed at every other --------------------------


def test_a_grade_is_not_inherited_by_a_neighbouring_task_class():
    """The measured case: a family validated for mechanical extraction, given
    analytical review, produced seven findings it then retracted."""
    graded = {("local-mlx", "extract"): TaskClassGrade("extract", "confirmed", 2, validated=2)}
    record = record_for("local-mlx", graded)
    assert record.qualified_for("extract")
    assert not record.qualified_for("review")
    assert record.grade_for("review").grade == "unprobed"


# --- UNKNOWN is a value, on every field ---------------------------------------


def test_every_identity_field_defaults_to_unknown():
    identity = BackendIdentity()
    assert set(vars(identity).values()) == {UNKNOWN}


def test_a_requested_model_is_not_an_observed_model():
    """`model` returns only what a surface confirmed. A convenience that fell
    back to the request is how a routing table comes to describe a
    configuration that never ran."""
    identity = BackendIdentity(model_requested="claude-opus-5")
    assert identity.model == UNKNOWN

    observed = BackendIdentity(model_requested="claude-opus-5", model_observed="claude-opus-5")
    assert observed.model == "claude-opus-5"


def test_the_record_names_what_it_does_not_know():
    record = BackendRecord(identity=BackendIdentity(family="claude-cli"))
    missing = record.unknown_fields()
    assert "identity.model_observed" in missing
    assert "interruption_semantics" in missing
    assert "availability" in missing
    assert "identity.family" not in missing


def test_an_unrecognised_authentication_class_is_refused():
    with pytest.raises(BackendContractError):
        BackendIdentity(authentication_class="free-trial")


def test_api_key_is_nameable_so_it_can_be_refused():
    """D14 clause 12 forbids depending on it. Naming it is how a record can say
    that a backend is on it."""
    assert "api_key" in AUTHENTICATION_CLASSES
    assert BackendIdentity(authentication_class="api_key").authentication_class == "api_key"


def test_an_unrecognised_grade_is_refused():
    with pytest.raises(BackendContractError):
        TaskClassGrade("t", "probably-fine", observations=3)


# --- reading the evidence the pack already has --------------------------------


def test_the_existing_configuration_strings_parse():
    identity = parse_configuration(
        "family=claude-cli agent=capability-auditor effort=unknown "
        "isolation=git-worktree network=allowed"
    )
    assert identity.family == "claude-cli"
    assert identity.client == "capability-auditor"
    assert identity.sandbox_state == "git-worktree"
    assert identity.network_state == "allowed"


def test_a_literal_unknown_and_an_absent_key_mean_the_same_thing():
    """Several observations record `effort=unknown`, which meant exactly what a
    missing key meant and could not be told apart from it."""
    assert parse_configuration("effort=unknown").effort_requested == UNKNOWN
    assert parse_configuration("family=x").effort_requested == UNKNOWN


def test_parsing_never_fills_the_observed_model_from_the_requested_one():
    identity = parse_configuration("family=local-mlx model=some/model-4bit")
    assert identity.model_requested == "some/model-4bit"
    assert identity.model_observed == UNKNOWN


def test_grades_derive_from_the_real_observation_log():
    """Against the log this release actually ships, not a fixture."""
    graded = grades_from_observations(OBSERVATIONS)
    assert graded, "the observation log produced no grades"
    for (family, task_class), grade in graded.items():
        assert grade.grade in QUALIFICATION_GRADES
        assert grade.observations >= 1
        assert family and task_class


def test_a_contradiction_is_never_outvoted_by_validations():
    """Adverse evidence is not averaged away. `REVIEW_LOCAL` is `contradicted`
    on one observation and must stay so."""
    graded = grades_from_observations(OBSERVATIONS)
    contradicted = [key for key, grade in graded.items() if grade.contradicted]
    assert contradicted, "the log carries a contradiction; the derivation lost it"
    for key in contradicted:
        assert graded[key].grade == "contradicted"


def test_environmental_failures_do_not_grade_a_backend_incapable():
    """The runtime never started, so nothing was learned about capability.
    Grading that `contradicted` would retire a backend on no evidence."""
    graded = grades_from_observations(OBSERVATIONS)
    environmental_only = [
        grade for grade in graded.values()
        if grade.environmental and not grade.validated and not grade.contradicted
    ]
    assert environmental_only, "the log carries environmental failures; the derivation lost them"
    for grade in environmental_only:
        assert grade.grade == "environmental-unknown"


def test_the_derived_view_is_a_pure_function_of_the_log():
    """It is regenerated wholesale, never patched — so two derivations of an
    unchanged log must be identical."""
    assert grades_from_observations(OBSERVATIONS) == grades_from_observations(OBSERVATIONS)
