"""Three questions that were one question, kept apart under attack.

Every test here is an attempt to route to something the evidence does not
support, or to be refused something the evidence does support. Both directions,
because a gate that refuses everything is as useless as one that refuses nothing
— and an independent reading of the design found the first version failing in
exactly that direction.
"""

from dataclasses import replace

import pytest

import routing
from backend_contract import TaskClassGrade
from qualification import UNKNOWN, ConfigurationIdentity, Prior
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
    RoutingError,
    availability_for,
    design_audit_route,
    disposition_of,
    eligibility,
    independence_problems,
)

IDENTITY = ConfigurationIdentity(
    surface="a-surface", family="a-family", client="a-client", model_observed="a-model",
    effort="high", isolation="read-only", network="none",
    authentication_class="subscription", identity_method="execution_surface_turn_record",
    build="1.0.0",
)
OTHER = replace(IDENTITY, model_observed="another-model")


def _candidate(identity=IDENTITY, *, grade="confirmed", validated=2, availability=AVAILABLE,
               task_class="T", producer="p", session="s", provider="v", prior=None,
               contradicted=0):
    return Candidate(
        identity=identity,
        task_class=task_class,
        grade=TaskClassGrade(task_class, grade, observations=validated + contradicted,
                             validated=validated, contradicted=contradicted),
        availability=availability,
        prior=prior,
        derivation=Derivation(producer=producer, session=session, provider=provider,
                              surface=identity.surface),
    )


SUBJECT = Derivation(producer="the-implementer", session="the-session", provider="vendor-a",
                     surface="a-surface")


# --- O5: discovery is not availability, in both directions -------------------


def test_discovery_is_not_availability_a_refused_dispatch_is_ineligible():
    refused = _candidate(availability=UNAVAILABLE)
    verdict = eligibility(refused, purpose=ROUTINE)
    assert not verdict.allowed
    assert any("observed to be refused" in reason for reason in verdict.reasons)
    assert refused.disposition == UNAVAILABLE, (
        "a configuration that cannot start must never read as qualified, however strong its "
        "evidence"
    )


def test_discovery_is_not_availability_absence_from_a_document_refuses_nothing():
    """The direction an independent reader found the first design failing.

    A configuration with a completed run is available. It stays available when
    it is missing from a discovery document, because the document is a client's
    catalogue and the run is what happened.
    """
    ran = AvailabilityObservation(
        identity=IDENTITY, preconditions=frozenset({"stdin=closed"}), state=AVAILABLE,
        observed_at="2026-09-05", build="1.0.0", detail="completed",
    )
    state, notes = availability_for(IDENTITY, {"stdin=closed"}, [ran], build="1.0.0")
    assert state == AVAILABLE
    candidate = Candidate(identity=IDENTITY, task_class="T",
                          grade=TaskClassGrade("T", "confirmed", 2, 2),
                          availability=state, discovered=False)
    assert eligibility(candidate, purpose=ROUTINE).allowed, (
        "a currently-running configuration was refused for being absent from a catalogue"
    )
    assert candidate.disposition == "QUALIFIED"


def test_discovery_membership_alone_leaves_availability_unknown():
    state, notes = availability_for(IDENTITY, set(), [], build="1.0.0")
    assert state == UNKNOWN
    assert any("Discovery membership is not an answer" in note for note in notes)


# --- preconditions: the pair the shipped log holds ---------------------------


def test_a_dispatch_that_never_started_is_not_answered_by_one_that_did():
    """Rows 37 and 38 of the shipped log: one configuration, two preconditions,
    one never started and the other validated."""
    started = AvailabilityObservation(
        identity=IDENTITY, preconditions=frozenset({"stdin=/dev/null"}), state=AVAILABLE,
        observed_at="2026-09-03", build="1.0.0")
    hung = AvailabilityObservation(
        identity=IDENTITY, preconditions=frozenset({"stdin=INHERITED"}), state=UNAVAILABLE,
        observed_at="2026-09-03", build="1.0.0", detail="never started")

    assert availability_for(IDENTITY, {"stdin=/dev/null"}, [started, hung],
                            build="1.0.0")[0] == AVAILABLE
    assert availability_for(IDENTITY, {"stdin=INHERITED"}, [started, hung],
                            build="1.0.0")[0] == UNAVAILABLE, (
        "the successful precondition answered for the one that hangs"
    )


def test_a_refusal_outranks_a_success_recorded_on_the_same_day():
    good = AvailabilityObservation(identity=IDENTITY, state=AVAILABLE, observed_at="2026-09-05")
    bad = AvailabilityObservation(identity=IDENTITY, state=UNAVAILABLE, observed_at="2026-09-05")
    assert availability_for(IDENTITY, set(), [good, bad])[0] == UNAVAILABLE
    assert availability_for(IDENTITY, set(), [bad, good])[0] == UNAVAILABLE


def test_an_observation_on_a_different_client_is_reported_and_does_not_answer():
    """The measured case: one client ran a model the other refused."""
    elsewhere = AvailabilityObservation(
        identity=IDENTITY, state=AVAILABLE, observed_at="2026-09-05", build="0.149.0")
    state, notes = availability_for(IDENTITY, set(), [elsewhere], build="0.153.3")
    assert state == UNKNOWN
    assert any("does not answer" in note for note in notes)


def test_an_availability_state_outside_the_three_is_refused():
    with pytest.raises(RoutingError):
        AvailabilityObservation(identity=IDENTITY, state="PROBABLY")


# --- O6: independence is derivation, not configuration -----------------------


def test_independence_the_producer_is_refused_even_at_another_task_class():
    """Key equality is the wrong test in this direction: the producer's key
    changes the moment the task class does."""
    itself = Derivation(producer="the-implementer", session="another-session",
                        provider="vendor-a", surface="a-surface")
    problems = independence_problems(itself, SUBJECT)
    assert problems and any("never closes its own finding" in p for p in problems)


def test_independence_a_fresh_session_with_an_identical_configuration_is_not_refused():
    """And wrong in this direction too: two fresh blind sessions have the same
    key, which is exactly what a same-family primary audit is."""
    fresh = Derivation(producer="another-worker", session="a-fresh-session",
                       provider="vendor-a", surface="a-surface")
    assert independence_problems(fresh, SUBJECT) == ()


def test_independence_the_producers_own_session_is_refused():
    same_session = Derivation(producer="another-worker", session="the-session",
                              provider="vendor-a", surface="a-surface")
    problems = independence_problems(same_session, SUBJECT)
    assert any("fresh context, not a fresh instruction" in p for p in problems)


def test_independence_a_same_provider_pair_is_refused_for_a_cross_provider_leg():
    same_provider = Derivation(producer="another-worker", session="fresh",
                               provider="vendor-a", surface="a-surface")
    assert independence_problems(same_provider, SUBJECT) == ()
    problems = independence_problems(same_provider, SUBJECT, require_distinct_provider=True)
    assert any("one provider's reading" in p for p in problems)


def test_independence_fails_closed_when_a_producer_is_not_recorded():
    anonymous = Derivation(producer=UNKNOWN, session="fresh", provider="vendor-b")
    problems = independence_problems(anonymous, SUBJECT)
    assert any("not a different one" in p for p in problems)


# --- eligibility by purpose --------------------------------------------------


def test_a_critical_leg_needs_a_confirmed_configuration_and_names_its_hitl_rows():
    thin = _candidate(grade="provisional", validated=1)
    verdict = eligibility(thin, purpose=CRITICAL)
    assert not verdict.allowed
    assert any("rows 12 and 16" in reason for reason in verdict.reasons)
    assert any("never authorization" in reason for reason in verdict.reasons)


def test_an_unprobed_configuration_takes_work_only_as_a_declared_probe():
    unprobed = _candidate(grade="unprobed", validated=0)
    assert not eligibility(unprobed, purpose=ROUTINE).allowed
    assert not eligibility(unprobed, purpose=CRITICAL).allowed
    assert eligibility(unprobed, purpose=PROBE).allowed


def test_a_contradicted_configuration_is_refused_for_every_purpose():
    against = _candidate(grade="contradicted", validated=2, contradicted=1)
    for purpose in routing.PURPOSES:
        verdict = eligibility(against, purpose=purpose)
        assert not verdict.allowed, f"{purpose} accepted a contradicted configuration"
        assert any("not absence of evidence" in reason for reason in verdict.reasons)


def test_an_incomplete_identity_is_refused_for_every_purpose():
    blank = _candidate(identity=replace(IDENTITY, model_observed=UNKNOWN),
                       grade="unprobed", validated=0)
    for purpose in routing.PURPOSES:
        assert not eligibility(blank, purpose=purpose).allowed


def test_an_unrecognised_purpose_is_refused_rather_than_read_leniently():
    with pytest.raises(RoutingError) as caught:
        eligibility(_candidate(), purpose="probably-fine")
    assert "not a small one" in str(caught.value)


# --- O10: an advisory prior never ranks --------------------------------------


def test_advisory_never_ranks_a_candidate_or_breaks_a_tie():
    """Two candidates identical in their own evidence, one carrying a strong
    family prior. The prior must change nothing about the order."""
    strong_prior = Prior(family="a-family", task_class="T",
                         grade=TaskClassGrade("T", "confirmed", 15, 15),
                         because="family history")
    with_prior = _candidate(identity=IDENTITY, grade="provisional", validated=1,
                            prior=strong_prior, producer="w1")
    without = _candidate(identity=OTHER, grade="provisional", validated=1, producer="w2")

    assert routing._rank(with_prior) == routing._rank(without), (
        "the prior entered the ranking key"
    )
    report = design_audit_route([with_prior, without], task_class="T", subject=SUBJECT,
                                roles=(Role("SEAT"),))
    assert report.seats[0]["candidate"] is not None


def test_advisory_never_satisfies_eligibility():
    strong_prior = Prior(family="a-family", task_class="T",
                         grade=TaskClassGrade("T", "confirmed", 15, 15), because="family history")
    unprobed = _candidate(grade="unprobed", validated=0, prior=strong_prior)
    assert not eligibility(unprobed, purpose=ROUTINE).allowed
    assert not eligibility(unprobed, purpose=CRITICAL).allowed


def test_a_prior_is_printed_where_a_candidate_carries_one():
    prior = Prior(family="a-family", task_class="T",
                  grade=TaskClassGrade("T", "confirmed", 7, 7), because="family history")
    report = design_audit_route([_candidate(prior=prior)], task_class="T", subject=SUBJECT,
                                roles=(Role("SEAT"),))
    rendered = report.render()
    assert "PRIOR (advisory" in rendered
    assert "broke no tie" in rendered


# --- ranking is on evidence, never on novelty --------------------------------


def test_the_newest_model_does_not_outrank_a_better_evidenced_one():
    newcomer = _candidate(identity=replace(IDENTITY, model_observed="brand-new"),
                          grade="provisional", validated=1, producer="w-new")
    established = _candidate(identity=replace(IDENTITY, model_observed="older"),
                             grade="confirmed", validated=4, producer="w-old")
    report = design_audit_route([newcomer, established], task_class="T", subject=SUBJECT,
                                roles=(Role("SEAT"),))
    assert report.seats[0]["candidate"].identity.model_observed == "older"
    assert any("ranked lower" in entry for entry in report.considered)


def test_the_route_report_states_what_did_not_enter_the_order():
    report = design_audit_route([_candidate()], task_class="T", subject=SUBJECT,
                                roles=(Role("SEAT"),))
    assert any("No generation, priority, context window or family history" in note
               for note in report.notes)


# --- the design-audit route --------------------------------------------------


def test_a_design_audit_route_fills_its_seats_from_different_providers():
    primary = _candidate(identity=replace(IDENTITY, model_observed="m1"),
                         producer="w1", provider="vendor-b")
    falsifier = _candidate(identity=replace(IDENTITY, model_observed="m2"),
                           producer="w2", provider="vendor-c")
    report = design_audit_route([primary, falsifier], task_class="T", subject=SUBJECT)
    seats = {seat["role"].name: seat["candidate"] for seat in report.seats}
    assert seats["PRIMARY_DESIGN_READER"] is not None
    assert seats["INDEPENDENT_FALSIFIER"] is not None
    assert (seats["PRIMARY_DESIGN_READER"].identity.model_observed
            != seats["INDEPENDENT_FALSIFIER"].identity.model_observed)
    assert report.complete


def test_a_seat_nothing_can_fill_is_unfilled_and_says_the_work_waits():
    report = design_audit_route([], task_class="T", subject=SUBJECT)
    assert not report.complete
    reasons = " ".join(r for seat in report.seats for r in seat["reasons"])
    assert "Unavailability is never authorization" in reasons


def test_the_same_configuration_cannot_hold_two_seats():
    only = _candidate(producer="w1", provider="vendor-b")
    report = design_audit_route([only], task_class="T", subject=SUBJECT)
    seated = [seat for seat in report.seats if seat["candidate"] is not None]
    assert len(seated) == 1
    reasons = " ".join(r for seat in report.seats for r in seat["reasons"])
    assert "already seated" in reasons


def test_an_unprobed_candidate_can_take_a_seat_only_as_a_declared_probe():
    """The cold start: an empty table cannot acquire its first observation if
    qualification is required before every dispatch."""
    unprobed = _candidate(grade="unprobed", validated=0, producer="w1", provider="vendor-b")
    refused = design_audit_route([unprobed], task_class="T", subject=SUBJECT,
                                 roles=(Role("SEAT"),))
    assert refused.seats[0]["candidate"] is None

    allowed = design_audit_route([unprobed], task_class="T", subject=SUBJECT,
                                 roles=(Role("SEAT"),), allow_probe=True)
    assert allowed.seats[0]["candidate"] is not None
    assert any("DECLARED PROBE" in reason for reason in allowed.seats[0]["reasons"])


def test_a_probe_never_fills_a_critical_seat():
    unprobed = _candidate(grade="unprobed", validated=0, producer="w1", provider="vendor-b")
    report = design_audit_route([unprobed], task_class="T", subject=SUBJECT, allow_probe=True,
                                roles=(Role("MANDATORY", purpose=CRITICAL),))
    assert report.seats[0]["candidate"] is None, (
        "a declared probe filled a mandatory independent leg; HITL rows 12 and 16 keep their human"
    )


def test_the_implementer_is_never_seated_as_its_own_reader():
    """O6's end-to-end form: the producer of the work offered as its own auditor."""
    itself = _candidate(producer=SUBJECT.producer, session="a-fresh-one", provider="vendor-a")
    report = design_audit_route([itself], task_class="T", subject=SUBJECT, roles=(Role("SEAT"),))
    assert report.seats[0]["candidate"] is None
    assert any("not independent" in reason for reason in report.seats[0]["reasons"])


# --- O9: mutations -----------------------------------------------------------


def test_mutation_removing_the_availability_axis_from_eligibility_is_caught():
    """The mutant: eligibility that reads only the grade.

    Killed by a candidate whose grade is `confirmed` and whose dispatch has been
    observed to be refused — which the mutant would accept.
    """
    refused = _candidate(grade="confirmed", validated=5, availability=UNAVAILABLE)

    def mutant(candidate):
        return candidate.grade.grade == "confirmed"

    assert mutant(refused) is True
    assert eligibility(refused, purpose=ROUTINE).allowed is False


def test_mutation_substituting_discovery_membership_for_availability_is_caught():
    """The mutant: availability derived from a discovery document.

    Two candidates kill it in opposite directions, which is the point — a mutant
    that only over-refuses would survive a fixture that only over-accepts.
    """
    listed_but_refused = Candidate(identity=IDENTITY, task_class="T",
                                   grade=TaskClassGrade("T", "confirmed", 2, 2),
                                   availability=UNAVAILABLE, discovered=True)
    unlisted_but_running = Candidate(identity=IDENTITY, task_class="T",
                                     grade=TaskClassGrade("T", "confirmed", 2, 2),
                                     availability=AVAILABLE, discovered=False)

    def mutant(candidate):
        return bool(candidate.discovered)

    assert mutant(listed_but_refused) != eligibility(listed_but_refused, purpose=ROUTINE).allowed
    assert mutant(unlisted_but_running) != eligibility(unlisted_but_running,
                                                       purpose=ROUTINE).allowed


def test_mutation_ranking_on_a_family_prior_is_caught():
    """The mutant: a ranking key that reads the prior."""
    prior = Prior(family="f", task_class="T", grade=TaskClassGrade("T", "confirmed", 15, 15),
                  because="family")
    thin_with_prior = _candidate(identity=IDENTITY, grade="provisional", validated=1, prior=prior)
    strong_without = _candidate(identity=OTHER, grade="confirmed", validated=3)

    def mutant(candidate):
        return (candidate.prior.grade.validated if candidate.prior else 0,)

    assert mutant(thin_with_prior) > mutant(strong_without)
    assert routing._rank(thin_with_prior) < routing._rank(strong_without)


# --- the six dispositions the coordinator must be able to tell apart ---------


def test_every_disposition_the_coordinator_needs_is_reachable_and_distinct():
    seen = {
        disposition_of(UNAVAILABLE, "confirmed"): "UNAVAILABLE",
        disposition_of(UNKNOWN, "confirmed"): UNKNOWN,
        disposition_of(AVAILABLE, "confirmed"): "QUALIFIED",
        disposition_of(AVAILABLE, "provisional"): "PROVISIONAL",
        disposition_of(AVAILABLE, "unprobed"): "UNPROBED",
        disposition_of(AVAILABLE, "contradicted"): "CONTRADICTED",
        disposition_of(AVAILABLE, "environmental-unknown"): "ENVIRONMENTAL_UNKNOWN",
    }
    for produced, expected in seen.items():
        assert produced == expected
    for required in ("QUALIFIED", "PROVISIONAL", "UNPROBED", "UNAVAILABLE", UNKNOWN):
        assert required in routing.DISPOSITIONS
    assert "AVAILABLE" in routing.DISPOSITIONS
    assert set(seen) <= set(routing.DISPOSITIONS)


def test_an_unavailable_configuration_never_reads_as_qualified():
    for grade in ("confirmed", "provisional", "unprobed", "contradicted"):
        assert disposition_of(UNAVAILABLE, grade) == UNAVAILABLE


# --- an observation records who produced it, without naming a session --------


def test_a_derivation_is_read_off_an_observation_that_records_one():
    """Phase-3 requirement: a probe records independence-relevant attributes."""
    row = {"derivation": {"producer": "a-worker", "provider": "a-provider",
                          "session_class": "fresh-blind-dispatch", "role": "design falsifier"},
           "surface": "a-surface"}
    derivation = routing.derivation_from_observation(row)
    assert derivation.producer == "a-worker"
    assert derivation.provider == "a-provider"
    # NOT the session field: a class is not an identifier, and putting one where
    # equality is tested reported two independent readings as one session.
    assert derivation.session == UNKNOWN
    assert derivation.fresh is True


def test_an_observation_that_records_no_derivation_fails_independence_closed():
    """An observation that did not say who produced it cannot establish that
    somebody else did."""
    derivation = routing.derivation_from_observation({})
    assert derivation.producer == UNKNOWN
    problems = independence_problems(derivation, SUBJECT)
    assert any("not a different one" in problem for problem in problems)


def test_a_derivation_field_nothing_reads_is_refused():
    with pytest.raises(RoutingError) as caught:
        routing.derivation_from_observation({"derivation": {"vibes": "good"}})
    assert "nothing reads" in str(caught.value)


def test_no_observation_records_a_session_identifier():
    """A session id is a private identifier and this pack's own publication scan
    refuses UUID-shaped tokens in tracked content — correctly. Independence needs
    a session CLASS, which answers the same question without naming a session.
    """
    import json
    import pathlib
    import re

    log = pathlib.Path(__file__).resolve().parents[2] / "policy" / "observations.jsonl"
    uuid = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
                      re.IGNORECASE)
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        declared = row.get("derivation") or {}
        assert "session" not in declared, "a raw session field appeared; the field is session_class"
        assert not uuid.search(json.dumps(declared)), "a session identifier reached the log"


def test_the_two_readings_this_release_dispatched_are_not_independent_of_each_other():
    """The release's own bound, asserted rather than described.

    Both design readings came from one provider. They are independent of the
    coordinator and of each other's session; a leg declared cross-provider
    refuses the pair, and this is that refusal.
    """
    import json
    import pathlib

    log = pathlib.Path(__file__).resolve().parents[2] / "policy" / "observations.jsonl"
    readings = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()
                if line.strip() and json.loads(line).get("task_class")
                == "design_falsification_review"]
    assert len(readings) >= 2
    first, second = (routing.derivation_from_observation(row) for row in readings[:2])
    assert independence_problems(first, second) == (), (
        "different producers in fresh sessions are independent for an ordinary leg"
    )
    problems = independence_problems(first, second, require_distinct_provider=True)
    assert any("one provider's reading" in problem for problem in problems)
