"""The three inferences a routing record must not permit.

Not "does the dataclass hold the fields" — a shape test passes against a
structure that lets a reader conclude anything. Every test here is an attempt
to obtain a positive qualification from something that is not evidence of one.
"""

from pathlib import Path

import pathlib

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
    # BOTH RECORDS NAME THE MODEL THAT RAN. From 2.4.0 an affirmative answer
    # needs an observed identity as well as a grade, so a record without one
    # would answer `False` for a reason that has nothing to do with the
    # difference this test isolates.
    observed = BackendIdentity(family="f", model_observed="a-model")
    available = record_for("f", graded, identity=observed, availability="available")
    absent = record_for("f", graded, identity=observed, availability="unreachable")
    assert available.qualified_for("t") == absent.qualified_for("t") is True

    ungraded_available = record_for("f", {}, identity=observed, availability="available")
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
    record = record_for("local-mlx", graded,
                        identity=BackendIdentity(family="local-mlx", model_observed="a-model"))
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
    """It is regenerated wholesale, never patched, so the view is a function of
    the log and of nothing else.

    **Was `f(x) == f(x)`, which cannot fail** — the third self-comparison of
    that exact shape in this release, after the two digest ones, and found by a
    mechanical sweep of the suite rather than by a reader. Calling a pure
    function twice tests the language.

    The property is that the view depends on the log ALONE: order does not
    change it, an unrelated row does not change the grades of other task
    classes, and one changed row changes exactly its own grade."""
    import json
    import tempfile

    rows = [json.loads(line) for line in
            OBSERVATIONS.read_text(encoding="utf-8").splitlines() if line.strip()]
    baseline = grades_from_observations(OBSERVATIONS)
    assert baseline, "the fixture log produced no grades, so nothing below discriminates"

    with tempfile.TemporaryDirectory() as scratch:
        def graded(records):
            path = pathlib.Path(scratch) / "log.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
            return grades_from_observations(path)

        assert graded(rows) == baseline, "the same rows through a copy gave a different view"
        assert graded(list(reversed(rows))) == baseline, "the order of the log changed the view"

        unrelated = rows + [{**rows[0],
                             "task_class": "a task class nothing else mentions",
                             "outcome": "validated"}]
        after = graded(unrelated)
        for key, grade in baseline.items():
            assert after[key] == grade, f"an unrelated row moved the grade for {key}"
        assert len(after) == len(baseline) + 1, "the new row produced no grade of its own"


# --- the derivation itself, asserted rather than shape-checked -----------------
#
# An independent audit mutated `validated >= 2` to `>= 1` and `qualified_for` to
# accept `provisional`, and the whole suite passed: nineteen tests asserted the
# grades were *in the enum* and none asserted what any grade actually was. The
# rule `routing-table.md` calls "checkable rather than promised" was neither.


def test_every_derived_grade_follows_the_stated_rule():
    """The derivation rule, applied to the real log, entry by entry.

    Written as the *rule* rather than as a snapshot of today's grades. The first
    version hardcoded them and went stale the moment this session's own audit
    observations were appended — which is the same defect as a figure in prose,
    one layer along. A threshold mutation still fails here, because the grade is
    compared against the counts that produced it.
    """
    for (family, task_class), grade in grades_from_observations(OBSERVATIONS).items():
        if grade.contradicted:
            expected = "contradicted"
        elif grade.validated >= 2:
            expected = "confirmed"
        elif grade.validated == 1:
            expected = "provisional"
        else:
            expected = "environmental-unknown"
        assert grade.grade == expected, (
            f"{family}/{task_class}: {grade.validated} validated, {grade.contradicted} "
            f"contradicted, {grade.environmental} environmental derives {expected!r}, "
            f"not {grade.grade!r}"
        )


def test_the_grades_that_do_not_move_with_new_evidence():
    """Two anchors that adverse and absent evidence pin permanently."""
    graded = grades_from_observations(OBSERVATIONS)
    assert graded[("local-mlx", "analytical_code_review")].grade == "contradicted"
    assert graded[
        ("codex-cli", "confinement dispatch qualification (worker configuration ladder, 8 configs)")
    ].grade == "environmental-unknown"


def test_a_provisional_grade_does_not_qualify_a_dispatch():
    """`qualified_for` is the routing gate. Nothing asserted it was false for
    the grade that means "some evidence, not enough to rely on"."""
    graded = {("f", "t"): TaskClassGrade("t", "provisional", observations=1, validated=1)}
    record = record_for("f", graded)
    assert record.grade_for("t").grade == "provisional"
    assert record.qualified_for("t") is False


@pytest.mark.parametrize("grade", ["unprobed", "provisional", "contradicted", "environmental-unknown"])
def test_only_confirmed_qualifies(grade):
    observations = 0 if grade == "unprobed" else 1
    graded = {("f", "t"): TaskClassGrade("t", grade, observations=observations,
                                         validated=1 if grade == "provisional" else 0)}
    assert record_for("f", graded).qualified_for("t") is False


def test_a_confirmed_grade_qualifies_when_the_record_says_which_model_ran():
    graded = {("f", "t"): TaskClassGrade("t", "confirmed", observations=2, validated=2)}
    observed = BackendIdentity(family="f", model_observed="a-model")
    assert record_for("f", graded, identity=observed).qualified_for("t") is True


def test_a_confirmed_family_grade_does_not_qualify_a_record_that_names_no_model():
    """The defect an independent reader found still open in the 2.4.0 candidate.

    The release added a correct per-configuration derivation and left the
    affirmative answer reachable through the API a consumer actually calls: a
    record built from FAMILY grades, naming no observed model, returned `True`
    for a model that had never been dispatched.

    `grade_for` is unchanged and still reports the family's history, so nothing
    that reads history loses anything. What is refused is the one thing this
    answer means: dispatch this here.
    """
    graded = {("codex-cli", "audit"): TaskClassGrade("audit", "confirmed", 7, validated=7)}
    unobserved = record_for("codex-cli", graded, identity=BackendIdentity(
        family="codex-cli", model_requested="never-dispatched"))

    assert unobserved.identity.model_observed == UNKNOWN
    assert unobserved.qualified_for("audit") is False, (
        "family evidence qualified a configuration that never ran"
    )
    assert unobserved.grade_for("audit").grade == "confirmed", (
        "the family's history must still be REPORTED; hiding it is a different defect"
    )
    # And the request is not a substitute for the observation.
    requested = record_for("codex-cli", graded, identity=BackendIdentity(
        family="codex-cli", model_requested="a-model"))
    assert requested.qualified_for("audit") is False


# --- an unrecognised outcome is not silently reclassified ----------------------


def test_an_unrecognised_outcome_is_a_parse_finding_not_environmental(tmp_path):
    """The `else` branch counted every unrecognised string as "the runtime never
    started, nothing was learned" — so a case variant of `contradicted` became
    adverse evidence quietly overwritten, in the module whose thesis is that
    such inferences are impossible to write. Found by an independent audit."""
    import json

    log = tmp_path / "observations.jsonl"
    log.write_text(json.dumps({
        "configuration": "family=x", "task_class": "t", "outcome": "CONTRADICTED",
    }) + "\n")
    with pytest.raises(BackendContractError) as caught:
        grades_from_observations(log)
    assert "does not recognise" in str(caught.value)


@pytest.mark.parametrize("outcome", ["capability_failure", "validatd", "", None, "unknown"])
def test_every_unrecognised_outcome_raises(tmp_path, outcome):
    import json

    log = tmp_path / "observations.jsonl"
    log.write_text(json.dumps({"configuration": "family=x", "task_class": "t", "outcome": outcome}) + "\n")
    with pytest.raises(BackendContractError):
        grades_from_observations(log)


@pytest.mark.parametrize("outcome, bucket", [
    ("validated", "validated"), ("contradicted", "contradicted"),
    ("environmental_failure", "environmental"),
])
def test_every_recognised_outcome_is_counted(tmp_path, outcome, bucket):
    import json

    log = tmp_path / "observations.jsonl"
    log.write_text(json.dumps({"configuration": "family=x", "task_class": "t", "outcome": outcome}) + "\n")
    grade = grades_from_observations(log)[("x", "t")]
    assert getattr(grade, bucket) == 1


# --- how an observation was obtained, and which pool it came from --------------
#
# A synthetic qualification is PRIOR evidence: field evidence narrows or
# downgrades it, and a synthetic pass never overrides a contradictory field
# outcome. A reader who cannot tell a benchmark from a track record will read
# one as the other, so the basis travels with the grade.


def _log(tmp_path, rows):
    import json as _json
    path = tmp_path / "observations.jsonl"
    path.write_text("\n".join(_json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def _row(**overrides):
    row = {"configuration": "family=some-cli model=m build=b effort=e isolation=none network=none",
           "task_class": "review", "outcome": "validated"}
    row.update(overrides)
    return row


def test_a_grade_from_benchmarks_alone_is_annotated_as_such(tmp_path):
    path = _log(tmp_path, [_row(qualification_basis="synthetic"),
                           _row(qualification_basis="synthetic")])
    grade = grades_from_observations(path)[("some-cli", "review")]
    assert grade.grade == "confirmed"
    assert grade.synthetic_only
    assert grade.synthetic_observations == 2 and grade.field_observations == 0


def test_one_real_dispatch_stops_a_grade_reading_as_a_benchmark(tmp_path):
    path = _log(tmp_path, [_row(qualification_basis="synthetic"),
                           _row(qualification_basis="field")])
    grade = grades_from_observations(path)[("some-cli", "review")]
    assert not grade.synthetic_only
    assert grade.field_observations == 1


def test_an_observation_that_never_said_is_neither_and_is_counted_as_neither(tmp_path):
    """The whole existing log predates the field. Reading its silence as
    `field` would promote every benchmark in it; reading it as `synthetic`
    would relabel thirteen real closure audits as a benchmark. It is counted
    as unknown, and `synthetic_only` is then false."""
    path = _log(tmp_path, [_row(), _row(qualification_basis="synthetic")])
    grade = grades_from_observations(path)[("some-cli", "review")]
    assert grade.basis_unknown == 1
    assert not grade.synthetic_only


def test_a_benchmark_pass_never_outweighs_a_real_contradiction(tmp_path):
    path = _log(tmp_path, [_row(qualification_basis="synthetic"),
                           _row(qualification_basis="synthetic"),
                           _row(qualification_basis="field", outcome="contradicted")])
    assert grades_from_observations(path)[("some-cli", "review")].grade == "contradicted"


def test_an_unrecognised_basis_is_refused_rather_than_counted_as_something(tmp_path):
    """The rule the outcome field already learned: an unrecognised value
    silently folded into a known one is adverse evidence overwritten."""
    path = _log(tmp_path, [_row(qualification_basis="Synthetic")])
    with pytest.raises(BackendContractError) as caught:
        grades_from_observations(path)
    assert "field, synthetic" in str(caught.value)


def test_the_basis_counters_do_not_inflate_the_observation_count(tmp_path):
    """How an observation was obtained is not an outcome. Summing the two
    together would have doubled every count behind every grade."""
    path = _log(tmp_path, [_row(qualification_basis="field"),
                           _row(qualification_basis="field")])
    grade = grades_from_observations(path)[("some-cli", "review")]
    assert grade.observations == 2
    assert grade.validated + grade.contradicted + grade.environmental == grade.observations


def test_the_pool_an_observation_came_from_is_carried_and_never_graded_on(tmp_path):
    """A pool is a fact about capacity and says nothing about capability, so it
    travels with the grade and does not change it."""
    path = _log(tmp_path, [_row(pool_id="shared-with-the-parent"),
                           _row(pool_id="independent")])
    grade = grades_from_observations(path)[("some-cli", "review")]
    assert grade.pools == ("independent", "shared-with-the-parent")
    assert grade.grade == "confirmed"


def test_an_observation_with_no_pool_records_that_it_did_not_say(tmp_path):
    grade = grades_from_observations(_log(tmp_path, [_row()]))[("some-cli", "review")]
    assert grade.pools == ("UNKNOWN",)
