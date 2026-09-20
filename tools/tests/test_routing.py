"""Three questions that were one question, kept apart under attack.

Every test here is an attempt to route to something the evidence does not
support, or to be refused something the evidence does support. Both directions,
because a gate that refuses everything is as useless as one that refuses nothing
— and an independent reading of the design found the first version failing in
exactly that direction.
"""

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

import capacity
import provider_manifest
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
               task_class="T", producer="p", session=None, provider="v", prior=None,
               contradicted=0):
    # THE SESSION DEFAULTS PER PRODUCER, not to one shared string. Every
    # candidate carried the same session IDENTIFIER, which says they all ran in
    # the same session — so once the router began comparing seated readers
    # against each other rather than only against the subject, two genuinely
    # independent candidates were correctly refused and the FIXTURE was what was
    # wrong. A fixture that says two readings share a session is testing that
    # case whether or not it meant to.
    return Candidate(
        identity=identity,
        task_class=task_class,
        grade=TaskClassGrade(task_class, grade, observations=validated + contradicted,
                             validated=validated, contradicted=contradicted),
        availability=availability,
        prior=prior,
        derivation=Derivation(producer=producer, session=session or f"session-of-{producer}",
                              provider=provider,
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
    # BOTH observations name the client they ran on, because an observation that
    # does not is no longer an answer about any client. Written out here rather
    # than defaulted: the fixture's job is to isolate the tie-break, and a
    # fixture that also leaves the build unknown tests two things at once.
    good = AvailabilityObservation(identity=IDENTITY, state=AVAILABLE, observed_at="2026-09-05",
                                   build=IDENTITY.build)
    bad = AvailabilityObservation(identity=IDENTITY, state=UNAVAILABLE, observed_at="2026-09-05",
                                  build=IDENTITY.build)
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
    # VENDOR, not provider (D30): `provider` is read only as `vendor`'s alias
    # when the latter was never recorded, which is exactly this fixture's shape.
    assert any("one vendor's reading" in p for p in problems)


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

    # AND THE SELECTION ITSELF, in both orders. Asserting only that somebody was
    # selected passes against a sort that reads the prior — an independent reader
    # added `pair[0].prior.grade.validated` as a tiebreak, changed which model
    # the route picked, and all of the new tests still passed.
    def selected(pool):
        report = design_audit_route(pool, task_class="T", subject=SUBJECT,
                                    roles=(Role("SEAT"),))
        chosen = report.seats[0]["candidate"]
        return chosen.identity.model_observed if chosen else None

    for pool in ([with_prior, without], [without, with_prior]):
        stripped = [replace(candidate, prior=None) for candidate in pool]
        assert selected(pool) == selected(stripped), (
            "adding a family prior changed which candidate was selected"
        )
        louder = [replace(candidate, prior=Prior(
            family="a-family", task_class="T",
            grade=TaskClassGrade("T", "confirmed", 99, 99), because="louder"))
            if candidate is pool[0] else candidate for candidate in pool]
        assert selected(pool) == selected(louder), (
            "making a family prior louder changed which candidate was selected"
        )


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


def test_one_producer_cannot_hold_two_seats_and_still_be_two_readings():
    """Deduplication is by PRODUCER AND SESSION, not by model name.

    Names were the wrong key in both directions and an independent reader
    produced both: two readings by one producer in one session were seated
    because their models differed, and two genuinely independent sessions were
    refused because their model was the same.
    """
    only = _candidate(producer="w1", provider="vendor-b")
    report = design_audit_route([only], task_class="T", subject=SUBJECT)
    seated = [seat for seat in report.seats if seat["candidate"] is not None]
    assert len(seated) == 1
    reasons = " ".join(r for seat in report.seats for r in seat["reasons"])
    assert "this producer already holds a seat" in reasons


def test_two_independent_sessions_on_one_model_are_two_readings():
    """The other direction, which the name-based rule refused."""
    first = _candidate(identity=IDENTITY, producer="w1", session="s1", provider="vendor-b")
    second = _candidate(identity=IDENTITY, producer="w2", session="s2", provider="vendor-c")
    report = design_audit_route([first, second], task_class="T", subject=SUBJECT,
                                roles=(Role("ONE"), Role("TWO")))
    assert all(seat["candidate"] is not None for seat in report.seats), (
        "two independent producers were refused for sharing a model name"
    )


def test_two_readings_by_one_producer_are_refused_however_their_models_differ():
    same = Derivation(producer="w1", session="s1", provider="vendor-b")
    first = _candidate(identity=IDENTITY, producer="w1", session="s1", provider="vendor-b")
    second = replace(_candidate(identity=OTHER, producer="w1", session="s1",
                                provider="vendor-b"), derivation=same)
    report = design_audit_route([first, second], task_class="T", subject=SUBJECT,
                                roles=(Role("ONE"), Role("TWO")))
    filled = [seat for seat in report.seats if seat["candidate"] is not None]
    assert len(filled) == 1, "one producer in one session filled two seats"


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
    # VENDOR, not provider (D30): the log declares `provider`, which
    # `derivation_from_observation` reads as `vendor`'s alias (D30).
    assert any("one vendor's reading" in problem for problem in problems)


# --- a mandatory independent leg is not a place to find out ------------------


def test_a_probe_never_fills_the_mandatory_cross_provider_leg():
    """The seat an independent reader put a probe into.

    `INDEPENDENT_FALSIFIER` carries `require_distinct_provider`, which makes it
    the mandatory cross-vendor leg `policy/hitl-matrix.md` row 12 governs. It
    used to carry `purpose=ROUTINE`, and the probe fallback keyed on the purpose
    alone, so an unprobed configuration was seated in it and the route reported
    itself complete.
    """
    subject = Derivation(producer="implementer", session="s1", provider="vendor-a")
    confirmed = _candidate(identity=IDENTITY, grade="confirmed", validated=3,
                           producer="w1", provider="vendor-b")
    unprobed = _candidate(identity=OTHER, grade="unprobed", validated=0,
                          producer="w2", provider="vendor-c")

    report = design_audit_route([confirmed, unprobed], task_class="T", subject=subject,
                                allow_probe=True)
    seats = {seat["role"].name: seat["candidate"] for seat in report.seats}
    assert seats["INDEPENDENT_FALSIFIER"] is None, (
        "a declared probe filled the mandatory cross-provider leg"
    )
    assert not report.complete, "the route reported complete with its mandatory leg unfilled"


def test_the_probeability_of_a_seat_is_derived_from_what_the_seat_requires():
    """Derived, not typed: a flag somebody has to remember to set is a flag
    somebody eventually does not set."""
    assert Role("ORDINARY").accepts_a_probe is True
    assert Role("CROSS", require_distinct_provider=True).accepts_a_probe is False
    assert Role("MANDATORY", purpose=CRITICAL).accepts_a_probe is False
    assert Role("EXPLICIT", require_distinct_provider=True, probeable=True).accepts_a_probe is True
    assert all(
        role.accepts_a_probe is False
        for role in routing.DESIGN_AUDIT_ROLES if role.require_distinct_provider
    )


# --- a blank is not a value --------------------------------------------------


@pytest.mark.parametrize("blank", ["", " ", "   ", "\t", "\n"])
def test_a_blank_producer_is_not_a_different_producer(blank):
    """`" "` is not the UNKNOWN sentinel, so it compared unequal to every real
    producer and satisfied every independence check. An independent reader walked
    one into the mandatory cross-provider leg."""
    subject = Derivation(producer="implementer", session="s1", provider="vendor-a")
    parsed = routing.derivation_from_observation(
        {"derivation": {"producer": blank, "provider": blank,
                        "session_class": "fresh-blind-dispatch"}})
    assert parsed.producer == UNKNOWN and parsed.provider == UNKNOWN
    problems = independence_problems(parsed, subject, require_distinct_provider=True)
    assert problems, "a blank producer established independence"
    assert any("not a different one" in problem for problem in problems)


def test_the_predicate_normalises_even_when_the_reader_did_not():
    """Defence at the predicate as well as at the reader: a check that trusts its
    inputs to have been cleaned is one that will be handed an input that was
    not."""
    subject = Derivation(producer="implementer", session="s1", provider="vendor-a")
    raw = Derivation(producer="  ", session="  ", provider="  ")
    assert independence_problems(raw, subject, require_distinct_provider=True)


# =============================================================================
# D30 / O4 — independence is distinct VENDOR, not a provider string or gateway
# =============================================================================


def test_vendor_same_vendor_different_gateways_is_refused():
    one = Derivation(producer="w1", session="s1", vendor="vendor-a", gateway="gateway-a")
    two = Derivation(producer="w2", session="s2", vendor="vendor-a", gateway="gateway-b")
    problems = independence_problems(one, two, require_distinct_vendor=True)
    assert any("vendor-a" in p and "one vendor's reading" in p for p in problems)


def test_vendor_distinct_vendors_have_no_vendor_problem():
    one = Derivation(producer="w1", session="s1", vendor="vendor-a", gateway="gateway-a")
    two = Derivation(producer="w2", session="s2", vendor="vendor-b", gateway="gateway-a")
    assert independence_problems(one, two, require_distinct_vendor=True) == ()


def test_vendor_unknown_on_either_side_is_refused():
    known = Derivation(producer="w1", session="s1", vendor="vendor-a")
    unrecorded = Derivation(producer="w2", session="s2")
    problems = independence_problems(known, unrecorded, require_distinct_vendor=True)
    assert any("a vendor is not recorded on both sides" in p for p in problems)


def test_vendor_the_provider_alias_populates_vendor_when_absent():
    row = {"derivation": {"producer": "w", "provider": "vendor-z",
                          "session_class": "fresh-blind-dispatch"}}
    derivation = routing.derivation_from_observation(row)
    assert derivation.vendor == "vendor-z", "provider must alias vendor when vendor is absent (D30)"
    assert derivation.provider == "vendor-z"


def test_vendor_an_observation_declaring_gateway_and_vendor_keys_is_read():
    row = {"derivation": {"producer": "w", "vendor": "vendor-z", "gateway": "gateway-z",
                          "session_class": "fresh-blind-dispatch"}}
    derivation = routing.derivation_from_observation(row)
    assert derivation.vendor == "vendor-z"
    assert derivation.gateway == "gateway-z"


def test_vendor_an_unknown_derivation_key_still_raises():
    with pytest.raises(RoutingError) as caught:
        routing.derivation_from_observation(
            {"derivation": {"vendor": "vendor-z", "gateway": "gateway-z", "vibes": "good"}})
    assert "nothing reads" in str(caught.value)


# =============================================================================
# the eligibility report (S0-C5, O3): fixtures, then -k not_routable
# =============================================================================

_CONFIRMED_TOKENS = (
    "surface=surface-a family=vendor-a client=worker-a@gateway-a.example "
    "model=confirmed-model model_observed=confirmed-model "
    "identity_method=execution_surface_turn_record auth=subscription "
    "effort_observed=high isolation=read-only network=none build=1.0.0"
)


def _confirmed_log(tmp_path, task_class="T", validations=2):
    row = {"configuration": _CONFIRMED_TOKENS, "task_class": task_class,
           "outcome": "validated", "qualification_basis": "field"}
    path = tmp_path / "observations.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for _ in range(validations)), encoding="utf-8")
    return path


def _billing(**overrides):
    billing = dict(
        billing_mode="subscription", billing_pool_id="vendor-a-membership",
        windows=["rolling_5h"], authorised_by="decision-a-1",
        overage_enabled=False, auto_topup_enabled=False, metered_fallback_enabled=False,
    )
    billing.update(overrides)
    return billing


def _provider_manifest(*, provider_id="vendor-a-plan", client="worker-a@gateway-a.example",
                       vendor="vendor-a", pool_id="vendor-a-membership", billing_overrides=None):
    overrides = dict(billing_overrides or {})
    overrides.setdefault("billing_pool_id", pool_id)
    return provider_manifest.ProviderManifest.from_mapping({
        "schema": "runtime-pack-provider-1",
        "provider_id": provider_id, "vendor": vendor, "gateway": "gateway-a.example",
        "surfaces": [{"surface": "cli-a", "client": client, "protocol": "anthropic-compatible"}],
        "adapter": "anthropic-compatible-worker",
        "credential": {"kind": "subscription_key", "env_file_ref": "VENDOR_A_KEY_FILE",
                       "generic_env_forbidden": ["VENDOR_A_API_KEY"]},
        "billing": _billing(**overrides),
        "capacity_observer": {"source": "human-reading", "freshness_horizon_s": 3600, "command": None},
        "discovery": None, "private_terms": [],
    })


def test_not_routable_an_unauthorised_manifest_refuses_every_purpose(tmp_path):
    log = _confirmed_log(tmp_path)
    manifest = _provider_manifest(billing_overrides={"authorised_by": None})
    for purpose in routing.PURPOSES:
        report = routing.eligibility_report(log, task_class="T", purpose=purpose,
                                            manifests=[manifest], environment={})
        row = report.rows[0]
        assert row.routability == routing.NOT_ROUTABLE_UNAUTHORISED, purpose
        assert row.disposition == routing.NOT_ROUTABLE_UNAUTHORISED, purpose
        assert row.eligible is False, purpose


def test_not_routable_a_metered_manifest_refuses_every_purpose(tmp_path):
    log = _confirmed_log(tmp_path)
    manifest = _provider_manifest(billing_overrides={"billing_mode": "metered_api"})
    for purpose in routing.PURPOSES:
        report = routing.eligibility_report(log, task_class="T", purpose=purpose,
                                            manifests=[manifest], environment={})
        row = report.rows[0]
        assert row.routability == routing.NOT_ROUTABLE_BILLING, purpose
        assert row.eligible is False, purpose


def test_not_routable_no_manifest_matched_is_not_routable_unknown(tmp_path):
    log = _confirmed_log(tmp_path)
    report = routing.eligibility_report(log, task_class="T", purpose=ROUTINE,
                                        manifests=(), environment={})
    row = report.rows[0]
    assert row.routability == routing.NOT_ROUTABLE_UNKNOWN
    assert any("no declared provider manifest covers this configuration" in reason
               for reason in row.reasons)


def test_not_routable_availability_unknown_blocks_critical_but_not_routine(tmp_path):
    """NOTE: availability is UNKNOWN in every report (no dispatch), so a
    CRITICAL row is never eligible from a report alone — even fully
    authorised, credentialed, FRESH and confirmed."""
    log = _confirmed_log(tmp_path)
    manifest = _provider_manifest()
    now = datetime.now(timezone.utc).isoformat()
    pool = capacity.Pool(pool_id="vendor-a-membership", remaining=100, unit="req", observed_at=now)

    critical = routing.eligibility_report(
        log, task_class="T", purpose=CRITICAL, manifests=[manifest], capacity_pools=[pool],
        authorised_pools=["vendor-a-membership"], environment={},
    )
    routine = routing.eligibility_report(
        log, task_class="T", purpose=ROUTINE, manifests=[manifest], capacity_pools=[pool],
        authorised_pools=["vendor-a-membership"], environment={},
    )
    assert critical.rows[0].eligible is False
    assert routine.rows[0].eligible is True, (
        "a fully authorised, credentialed, FRESH, confirmed configuration was refused for "
        "ROUTINE by a report that can never itself supply availability"
    )


def test_not_routable_a_stale_pool_is_ineligible_with_the_stale_reason(tmp_path):
    log = _confirmed_log(tmp_path)
    manifest = _provider_manifest()
    old = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    pool = capacity.Pool(pool_id="vendor-a-membership", remaining=100, unit="req", observed_at=old)
    report = routing.eligibility_report(
        log, task_class="T", purpose=ROUTINE, manifests=[manifest], capacity_pools=[pool],
        authorised_pools=["vendor-a-membership"], environment={},
    )
    row = report.rows[0]
    assert row.pool.freshness == "STALE"
    assert row.eligible is False
    assert any("STALE" in reason for reason in row.reasons)


def test_not_routable_an_exhausted_fresh_pool_never_offers_a_metered_alternative(tmp_path):
    rows = [
        {"configuration": _CONFIRMED_TOKENS, "task_class": "T",
         "outcome": "validated", "qualification_basis": "field"},
        {"configuration": (
            "surface=surface-a family=vendor-a client=worker-b@gateway-a.example "
            "model=metered-model model_observed=metered-model "
            "identity_method=execution_surface_turn_record auth=subscription "
            "effort_observed=high isolation=read-only network=none build=1.0.0"),
         "task_class": "T", "outcome": "validated", "qualification_basis": "field"},
    ]
    path = tmp_path / "observations.jsonl"
    path.write_text("".join((json.dumps(row) + "\n") * 2 for row in rows), encoding="utf-8")

    subscription = _provider_manifest()
    metered = _provider_manifest(
        provider_id="vendor-a-metered", client="worker-b@gateway-a.example",
        pool_id="vendor-a-metered-pool", billing_overrides={"billing_mode": "metered_api"},
    )
    now = datetime.now(timezone.utc).isoformat()
    pool = capacity.Pool(pool_id="vendor-a-membership", remaining=0, unit="req", observed_at=now)

    report = routing.eligibility_report(
        path, task_class="T", purpose=ROUTINE, manifests=[subscription, metered],
        capacity_pools=[pool], authorised_pools=["vendor-a-membership"], environment={},
    )
    assert len(report.rows) == 2, "fixture is inert: both configurations must have graded"
    subscription_row = next(row for row in report.rows if row.provider_id == "vendor-a-plan")
    metered_row = next(row for row in report.rows if row.provider_id == "vendor-a-metered")

    assert subscription_row.routability == provider_manifest.ROUTABLE, (
        "fixture is inert: exhaustion is a CAPACITY fact, not a billing refusal"
    )
    assert subscription_row.eligible is False
    assert any("REFUSE_UNTIL_RESET" in reason or "PARK" in reason
               for reason in subscription_row.reasons)
    assert metered_row.routability == routing.NOT_ROUTABLE_BILLING, (
        "an exhausted subscription pool must never make a metered alternative eligible (D29)"
    )
    assert metered_row.eligible is False


def test_not_routable_a_matched_manifest_with_no_capacity_observation_is_noted(tmp_path):
    log = _confirmed_log(tmp_path)
    manifest = _provider_manifest()
    report = routing.eligibility_report(log, task_class="T", purpose=ROUTINE,
                                        manifests=[manifest],
                                        authorised_pools=["vendor-a-membership"], environment={})
    row = report.rows[0]
    assert row.pool is None
    assert any("no capacity observation for pool" in reason for reason in row.reasons)


# =============================================================================
# rows are never sorted by grade or newness
# =============================================================================


def test_rows_are_in_identity_order_not_grade_order(tmp_path):
    stronger = {"configuration": (
        "surface=surface-a family=vendor-a client=worker-a@gateway-a.example "
        "model=z-model model_observed=z-model identity_method=execution_surface_turn_record "
        "auth=subscription effort_observed=high isolation=read-only network=none build=1.0.0"),
        "task_class": "T", "outcome": "validated", "qualification_basis": "field"}
    weaker = {"configuration": (
        "surface=surface-a family=vendor-a client=worker-a@gateway-a.example "
        "model=a-model model_observed=a-model identity_method=execution_surface_turn_record "
        "auth=subscription effort_observed=high isolation=read-only network=none build=1.0.0"),
        "task_class": "T", "outcome": "validated", "qualification_basis": "field"}
    path = tmp_path / "observations.jsonl"
    path.write_text(
        "\n".join([json.dumps(stronger)] * 2 + [json.dumps(weaker)]) + "\n", encoding="utf-8"
    )
    report = routing.eligibility_report(path, task_class="T", purpose=ROUTINE, environment={})
    grades = [row.grade for row in report.rows]
    assert grades == ["provisional", "confirmed"], (
        "fixture is inert unless the two configurations carry different grades"
    )
    identities = [row.identity for row in report.rows]
    assert identities == sorted(identities), (
        "rows must stay in identity order even though the weaker grade sorts first"
    )


# =============================================================================
# O12 / -k mutation
# =============================================================================


def test_mutation_disabling_the_vendor_comparison_fails_the_same_vendor_oracle(monkeypatch):
    one = Derivation(producer="w1", session="s1", vendor="vendor-a", gateway="gateway-a")
    two = Derivation(producer="w2", session="s2", vendor="vendor-a", gateway="gateway-b")
    honest = independence_problems(one, two, require_distinct_vendor=True)
    assert honest, "fixture is inert: two readings of one vendor were not refused"

    monkeypatch.setattr(routing, "_vendors_distinct", lambda reader, subject: True)
    mutated = independence_problems(one, two, require_distinct_vendor=True)
    with pytest.raises(AssertionError):
        assert mutated, "the same-vendor oracle must fail once the comparison is disabled"


def test_mutation_ignoring_routability_fails_the_not_routable_oracle(tmp_path, monkeypatch):
    log = _confirmed_log(tmp_path)
    manifest = _provider_manifest(billing_overrides={"authorised_by": None})
    honest = routing.eligibility_report(log, task_class="T", purpose=ROUTINE,
                                        manifests=[manifest], environment={})
    assert honest.rows[0].disposition == routing.NOT_ROUTABLE_UNAUTHORISED, (
        "fixture is inert: the unauthorised route did not read as NOT_ROUTABLE_UNAUTHORISED"
    )

    monkeypatch.setattr(
        routing, "disposition_with_routability",
        lambda routability_disposition, availability, grade: disposition_of(availability, grade),
    )
    mutated = routing.eligibility_report(log, task_class="T", purpose=ROUTINE,
                                         manifests=[manifest], environment={})
    with pytest.raises(AssertionError):
        assert mutated.rows[0].disposition == routing.NOT_ROUTABLE_UNAUTHORISED, (
            "the not_routable oracle must fail once disposition ignores routability"
        )


# =============================================================================
# the CLI
# =============================================================================


def test_cli_eligibility_renders_and_exits_0(tmp_path, capsys):
    log = _confirmed_log(tmp_path)
    status = routing._cli(["--eligibility", "--observations", str(log), "--task-class", "T"])
    assert status == 0
    assert "eligibility report" in capsys.readouterr().out


def test_cli_eligibility_json_round_trips_as_dict(tmp_path, capsys):
    log = _confirmed_log(tmp_path)
    status = routing._cli(
        ["--eligibility", "--observations", str(log), "--task-class", "T", "--json"])
    assert status == 0
    payload = json.loads(capsys.readouterr().out)
    report = routing.eligibility_report(log, task_class="T")
    assert payload == report.as_dict()


def test_cli_eligibility_quarantines_an_unreadable_capacity_pool_element(tmp_path, capsys):
    log = _confirmed_log(tmp_path)
    capacity_doc = tmp_path / "capacity.json"
    capacity_doc.write_text(
        json.dumps({"pools": [{"pool_id": "bad", "remaining": -5}]}), encoding="utf-8")
    status = routing._cli(
        ["--eligibility", "--observations", str(log), "--task-class", "T",
         "--capacity", str(capacity_doc)])
    assert status == 0, "one unreadable pool element must not fail the whole report"
    printed = capsys.readouterr().out
    assert "pool bad could not be read" in printed


def test_cli_eligibility_environment_from_current_process_prints_no_value(
    tmp_path, capsys, monkeypatch
):
    log = _confirmed_log(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({
        "schema": "runtime-pack-provider-1", "provider_id": "vendor-a-plan", "vendor": "vendor-a",
        "gateway": "gateway-a.example",
        "surfaces": [{"surface": "cli-a", "client": "worker-a@gateway-a.example", "protocol": "anthropic-compatible"}],
        "adapter": "anthropic-compatible-worker",
        "credential": {"kind": "subscription_key", "env_file_ref": "VENDOR_A_KEY_FILE",
                       "generic_env_forbidden": ["VENDOR_A_TOKEN"]},
        "billing": _billing(), "capacity_observer": {"source": "human-reading", "freshness_horizon_s": 3600, "command": None},
        "discovery": None, "private_terms": []}))
    monkeypatch.setenv("VENDOR_A_TOKEN", "must-not-print")
    status = routing._cli(
        ["--eligibility", "--observations", str(log), "--task-class", "T",
         "--manifest", str(manifest_path), "--authorised-pool", "vendor-a-membership",
         "--environment-from-current-process", "--json"])
    printed = capsys.readouterr().out
    assert status == 0
    assert "must-not-print" not in printed
    payload = json.loads(printed)
    assert payload["rows"][0]["routability"] == routing.NOT_ROUTABLE_BILLING, (
        "the flag consulted nothing: a forbidden name in the process environment must poison the route"
    )


def test_not_routable_a_same_vendor_row_is_not_eligible_against_a_subject(tmp_path):
    """The independence join reaches `eligible`: a configuration at the
    subject's own vendor is listed and refused for a cross-vendor leg."""
    log = _confirmed_log(tmp_path)
    manifest = _provider_manifest()
    subject = routing.Derivation(producer="somebody-else", vendor="vendor-a")
    report = routing.eligibility_report(
        log, task_class="T", purpose=ROUTINE, require_distinct_vendor=True, subject=subject,
        manifests=[manifest], authorised_pools=["vendor-a-membership"], environment={},
    )
    assert report.rows[0].independence and report.rows[0].eligible is False
    other = routing.Derivation(producer="somebody-else", vendor="vendor-b")
    report = routing.eligibility_report(
        log, task_class="T", purpose=ROUTINE, require_distinct_vendor=True, subject=other,
        manifests=[manifest], authorised_pools=["vendor-a-membership"], environment={},
    )
    assert not report.rows[0].independence and report.rows[0].eligible is True


def test_not_routable_a_shared_client_is_narrowed_by_vendor_and_order_invariant(tmp_path):
    """Two manifests declaring the same client string — one gateway serving
    two vendors — resolve by the configuration's own vendor, in either order,
    and never by the order the project listed them in."""
    log = _confirmed_log(tmp_path)
    a = _provider_manifest(provider_id="plan-a", vendor="vendor-a", pool_id="pool-a")
    b = _provider_manifest(provider_id="plan-b", vendor="vendor-b", pool_id="pool-b")
    subject = routing.Derivation(producer="somebody-else", vendor="vendor-a")
    verdicts = []
    for order in ([a, b], [b, a]):
        report = routing.eligibility_report(
            log, task_class="T", purpose=ROUTINE, require_distinct_vendor=True, subject=subject,
            manifests=order, authorised_pools=["pool-a", "pool-b"], environment={},
        )
        verdicts.append((report.rows[0].vendor, report.rows[0].billing_pool_id, report.rows[0].eligible))
    assert verdicts[0] == verdicts[1] == ("vendor-a", "pool-a", False)


def test_not_routable_two_accounts_at_one_gateway_for_one_vendor_are_refused_as_ambiguous(tmp_path):
    log = _confirmed_log(tmp_path)
    one = _provider_manifest(provider_id="plan-one", pool_id="pool-one")
    two = _provider_manifest(provider_id="plan-two", pool_id="pool-two",
                             billing_overrides={"authorised_by": None})
    for order in ([one, two], [two, one]):
        report = routing.eligibility_report(
            log, task_class="T", purpose=ROUTINE, manifests=order,
            authorised_pools=["pool-one", "pool-two"], environment={},
        )
        row = report.rows[0]
        assert row.routability == routing.NOT_ROUTABLE_UNKNOWN and row.eligible is False
        assert any("ambiguous" in reason for reason in row.reasons)


def test_vendor_spellings_of_one_vendor_are_one_vendor():
    reader = routing.Derivation(producer="r", fresh=True, vendor="Vendor-A ")
    subject = routing.Derivation(producer="s", vendor="vendor-a")
    problems = routing.independence_problems(reader, subject, require_distinct_vendor=True)
    # The SPECIFIC sentence: a casing-and-padding variant of one vendor was
    # once read as a second vendor and satisfied the leg the comparison exists
    # to refuse.
    assert any("one vendor's reading" in problem for problem in problems)
    unknown = routing.Derivation(producer="r", fresh=True, vendor="unknown")
    problems = routing.independence_problems(unknown, subject, require_distinct_vendor=True)
    assert any("not recorded" in problem for problem in problems)


def test_cli_eligibility_refuses_a_vendor_requirement_without_a_subject(tmp_path, capsys):
    log = _confirmed_log(tmp_path)
    status = routing._cli(["--eligibility", "--observations", str(log), "--task-class", "T",
                           "--require-distinct-vendor"])
    assert status == 2


def test_cli_eligibility_renders_every_reason_including_the_supposition(tmp_path, capsys):
    log = _confirmed_log(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({
        "schema": "runtime-pack-provider-1", "provider_id": "vendor-a-plan", "vendor": "vendor-a",
        "gateway": "gateway-a.example",
        "surfaces": [{"surface": "cli-a", "client": "worker-a@gateway-a.example", "protocol": "anthropic-compatible"}],
        "adapter": "anthropic-compatible-worker",
        "credential": {"kind": "subscription_key", "env_file_ref": "VENDOR_A_KEY_FILE",
                       "generic_env_forbidden": ["VENDOR_A_TOKEN"]},
        "billing": _billing(), "capacity_observer": {"source": "human-reading", "freshness_horizon_s": 3600, "command": None},
        "discovery": None, "private_terms": []}))
    status = routing._cli(["--eligibility", "--observations", str(log), "--task-class", "T",
                           "--manifest", str(manifest_path), "--authorised-pool", "vendor-a-membership"])
    printed = capsys.readouterr().out
    assert status == 0 and "availability supposed" in printed


def test_cli_eligibility_notes_a_capacity_document_of_the_wrong_shape(tmp_path, capsys):
    log = _confirmed_log(tmp_path)
    bad = tmp_path / "CAPACITY.json"
    bad.write_text(json.dumps({"pools": "not-a-list"}))
    status = routing._cli(["--eligibility", "--observations", str(log), "--task-class", "T",
                           "--capacity", str(bad)])
    assert status == 0 and "not a list" in capsys.readouterr().out


def test_a_report_with_an_unknown_purpose_is_refused_before_any_row(tmp_path):
    log = _confirmed_log(tmp_path)
    with pytest.raises(routing.RoutingError):
        routing.eligibility_report(log, task_class="T", purpose="BOGUS")


# =============================================================================
# T2 round 2, B1 — vendor canonicalisation is fail-closed
# =============================================================================


def test_vendor_a_misspelt_vendor_is_named_not_read_as_a_second_one():
    """`vendor_a` is a misspelling of a vendor, not a vendor: the leg is
    refused with the slug requirement named, never satisfied, and never
    established as a second vendor nothing validates."""
    reader = routing.Derivation(producer="r", fresh=True, vendor="vendor_a")
    subject = routing.Derivation(producer="s", vendor="vendor-b")
    problems = routing.independence_problems(reader, subject, require_distinct_vendor=True)
    assert problems, "a misspelt vendor satisfied the cross-vendor requirement"
    assert any("is not a vendor slug" in problem for problem in problems)


@pytest.mark.parametrize("spelling", [
    "vendor_a",       # an underscore is not a hyphen
    "vendor-a.",      # a trailing dot
    "vendor a",       # a space
    "vendora",        # the hyphen dropped entirely
    "vendor--a",      # a run of hyphens
    "vendor-a​",      # a zero-width space riding behind a clean slug
    "ｖendor-a",      # a full-width v that NFKC folds onto the real one
    "vendor-а",      # a Cyrillic look-alike а (U+0430), which NFKC does not fold
])
def test_vendor_a_variant_spelling_is_never_distinct_and_clean(spelling):
    """Every way a vendor name can be misspelt, against the vendor it
    misspells. Two of them fold onto the real slug through NFKC or drop a
    separator and are refused as ONE vendor; the rest fail the slug grammar
    and are refused as not slugs. None is ever read as a second vendor."""
    reader = routing.Derivation(producer="r", fresh=True, vendor=spelling)
    subject = routing.Derivation(producer="s", vendor="vendor-a")
    problems = routing.independence_problems(reader, subject, require_distinct_vendor=True)
    assert problems, f"{spelling!r} was read as a clean vendor distinct from vendor-a"
    assert any(
        "is not a vendor slug" in problem or "one vendor's reading" in problem
        for problem in problems
    )


def test_vendor_an_observation_with_a_non_slug_vendor_reads_as_unknown():
    """The same boundary at the observation reader: a derivation that names a
    non-slug vendor is `UNKNOWN` on the way in, so it refuses the leg instead
    of smuggling a spelling past the comparison. The refusal carries the plain
    not-recorded reason — the raw misspelling no longer exists to be named."""
    row = {"derivation": {"producer": "w", "provider": "vendor_a",
                          "session_class": "fresh-blind-dispatch"}}
    derivation = routing.derivation_from_observation(row)
    assert derivation.vendor == UNKNOWN and derivation.provider == UNKNOWN
    subject = routing.Derivation(producer="s", vendor="vendor-b")
    problems = routing.independence_problems(derivation, subject, require_distinct_vendor=True)
    assert any("a vendor is not recorded on both sides" in problem for problem in problems)


def test_cli_eligibility_refuses_a_non_slug_subject_vendor(tmp_path, capsys):
    """The CLI refuses a non-slug `--subject-vendor` outright — one sentence on
    stderr, exit 2, no traceback — before any report is read."""
    log = _confirmed_log(tmp_path)
    status = routing._cli(["--eligibility", "--observations", str(log), "--task-class", "T",
                           "--subject-producer", "someone", "--subject-vendor", "vendor_a"])
    captured = capsys.readouterr()
    assert status == 2
    assert captured.out == ""
    assert "vendor slug" in captured.err
    assert captured.err.count("\n") == 1, "the refusal is one sentence, not a traceback"
    assert "Traceback" not in captured.err


# =============================================================================
# T2 round 2, R1 — a routability outside the vocabulary is not a route
# =============================================================================


@pytest.mark.parametrize("value", [UNKNOWN, "not_routable_billing", "NOT_ROUTABLE", "garbage"])
def test_not_routable_a_routability_outside_the_vocabulary_refuses_every_purpose(value):
    """`UNKNOWN`, a lower-case spelling, the shared prefix `NOT_ROUTABLE` and
    plain garbage were all read as an established route. None of them is one."""
    candidate = _candidate()
    for purpose in routing.PURPOSES:
        verdict = eligibility(candidate, purpose=purpose, routability=value)
        assert not verdict.allowed, f"{value!r} was read as an established route for {purpose}"
        assert any(f"routability {value} is not ROUTABLE" in reason
                   for reason in verdict.reasons), purpose


def test_not_routable_none_and_routable_still_mean_the_question_was_asked():
    candidate = _candidate()
    assert eligibility(candidate, purpose=ROUTINE, routability=None).allowed
    assert eligibility(candidate, purpose=ROUTINE,
                       routability=provider_manifest.ROUTABLE).allowed


def test_not_routable_a_disposition_value_outside_the_vocabulary_is_not_routable_unknown():
    for value in (UNKNOWN, "not_routable_billing", "NOT_ROUTABLE", "garbage"):
        assert routing.disposition_with_routability(value, AVAILABLE, "confirmed") == (
            routing.NOT_ROUTABLE_UNKNOWN), value
    assert routing.disposition_with_routability(
        provider_manifest.ROUTABLE, AVAILABLE, "confirmed") == "QUALIFIED"
    assert routing.disposition_with_routability(
        routing.NOT_ROUTABLE_BILLING, AVAILABLE, "confirmed") == routing.NOT_ROUTABLE_BILLING


# =============================================================================
# T2 round 2, R2 — a verdict reached by supposing says so
# =============================================================================


def _fresh_pool():
    return capacity.Pool(pool_id="vendor-a-membership", remaining=100, unit="req",
                         observed_at=datetime.now(timezone.utc).isoformat())


def test_not_routable_a_row_that_supposed_availability_says_so_in_json_and_render(tmp_path):
    log = _confirmed_log(tmp_path)
    manifest = _provider_manifest()
    for purpose, supposed in ((PROBE, True), (ROUTINE, True), (CRITICAL, False)):
        report = routing.eligibility_report(
            log, task_class="T", purpose=purpose, manifests=[manifest], capacity_pools=[_fresh_pool()],
            authorised_pools=["vendor-a-membership"], environment={})
        row = report.rows[0]
        assert row.availability_supposed is supposed, purpose
        assert report.as_dict()["rows"][0]["availability_supposed"] is supposed, purpose

    routine = routing.eligibility_report(
        log, task_class="T", purpose=ROUTINE, manifests=[manifest], capacity_pools=[_fresh_pool()],
        authorised_pools=["vendor-a-membership"], environment={})
    critical = routing.eligibility_report(
        log, task_class="T", purpose=CRITICAL, manifests=[manifest], capacity_pools=[_fresh_pool()],
        authorised_pools=["vendor-a-membership"], environment={})
    assert routine.rows[0].eligible is True and critical.rows[0].eligible is False, (
        "fixture is inert: the routine row must be eligible and the critical row never"
    )
    assert "ELIGIBLE (availability supposed)" in routine.render()
    assert "ELIGIBLE (availability supposed)" not in critical.render()


# =============================================================================
# T2 round 2, R3 — a quarantined pool is capacity UNKNOWN, with its sentence
# =============================================================================


def test_not_routable_a_quarantined_pool_is_capacity_unknown_with_the_sentence(tmp_path):
    log = _confirmed_log(tmp_path)
    manifest = _provider_manifest()
    sentence = "pool vendor-a-membership could not be read: remaining is a non-negative quantity"
    report = routing.eligibility_report(
        log, task_class="T", purpose=ROUTINE, manifests=[manifest],
        authorised_pools=["vendor-a-membership"], environment={},
        quarantined_pools={"vendor-a-membership": sentence})
    row = report.rows[0]
    assert row.pool is None
    assert any(f"the capacity observation for pool vendor-a-membership was quarantined: "
               f"{sentence}" in reason for reason in row.reasons)
    assert any("capacity UNKNOWN: dispatch serially" in reason for reason in row.reasons)


def test_not_routable_an_absent_pool_now_carries_the_serial_caution(tmp_path):
    log = _confirmed_log(tmp_path)
    manifest = _provider_manifest()
    report = routing.eligibility_report(log, task_class="T", purpose=ROUTINE,
                                        manifests=[manifest],
                                        authorised_pools=["vendor-a-membership"], environment={})
    row = report.rows[0]
    assert any("no capacity observation for pool vendor-a-membership" in reason
               for reason in row.reasons)
    assert any("capacity UNKNOWN: dispatch serially" in reason for reason in row.reasons), (
        "an absent pool is capacity UNKNOWN, and the coordinator was told to dispatch serially "
        "only where a pool existed"
    )


def test_not_routable_a_fresh_pool_carries_no_serial_caution(tmp_path):
    log = _confirmed_log(tmp_path)
    manifest = _provider_manifest()
    report = routing.eligibility_report(
        log, task_class="T", purpose=ROUTINE, manifests=[manifest], capacity_pools=[_fresh_pool()],
        authorised_pools=["vendor-a-membership"], environment={})
    assert not any("dispatch serially" in reason for reason in report.rows[0].reasons)


def test_cli_eligibility_a_quarantined_element_reaches_the_row_and_the_json(tmp_path, capsys):
    log = _confirmed_log(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({
        "schema": "runtime-pack-provider-1", "provider_id": "vendor-a-plan", "vendor": "vendor-a",
        "gateway": "gateway-a.example",
        "surfaces": [{"surface": "cli-a", "client": "worker-a@gateway-a.example", "protocol": "anthropic-compatible"}],
        "adapter": "anthropic-compatible-worker",
        "credential": {"kind": "subscription_key", "env_file_ref": "VENDOR_A_KEY_FILE",
                       "generic_env_forbidden": ["VENDOR_A_TOKEN"]},
        "billing": _billing(), "capacity_observer": {"source": "human-reading", "freshness_horizon_s": 3600, "command": None},
        "discovery": None, "private_terms": []}))
    capacity_doc = tmp_path / "capacity.json"
    capacity_doc.write_text(
        json.dumps({"pools": [{"pool_id": "vendor-a-membership", "remaining": -5}]}),
        encoding="utf-8")
    status = routing._cli(
        ["--eligibility", "--observations", str(log), "--task-class", "T",
         "--manifest", str(manifest_path), "--authorised-pool", "vendor-a-membership",
         "--capacity", str(capacity_doc), "--json"])
    assert status == 0
    payload = json.loads(capsys.readouterr().out)
    assert any("was quarantined" in reason for reason in payload["rows"][0]["reasons"]), (
        "the row still read its pool as merely absent"
    )
    assert any("capacity UNKNOWN: dispatch serially" in reason
               for reason in payload["rows"][0]["reasons"])
    # N1: the quarantined sentences are a field, not prose to re-derive.
    assert len(payload["quarantined"]) == 1
    assert "could not be read" in payload["quarantined"][0]


# =============================================================================
# T2 round 2, R4 — the environment flag forwards NAMES only (test gap)
# =============================================================================


def test_not_routable_environment_from_current_process_forwards_names_only(
        tmp_path, capsys, monkeypatch):
    """The flag's contract, pinned at the boundary it could leak through: a
    spy on `provider_manifest.fingerprint` captures the `environment` mapping
    the CLI forwards, and every VALUE in it must be the empty string. The
    fixture poisons `os.environ` with a fixture-only name whose value must
    never reach the fingerprint, the report, or the output."""
    captured = []
    real_fingerprint = provider_manifest.fingerprint

    def spy(manifest, **kwargs):
        captured.append(kwargs.get("environment"))
        return real_fingerprint(manifest, **kwargs)

    monkeypatch.setattr(provider_manifest, "fingerprint", spy)
    monkeypatch.setenv("FIXTURE_ONLY_NAME", "fixture-only-value")

    log = _confirmed_log(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({
        "schema": "runtime-pack-provider-1", "provider_id": "vendor-a-plan", "vendor": "vendor-a",
        "gateway": "gateway-a.example",
        "surfaces": [{"surface": "cli-a", "client": "worker-a@gateway-a.example", "protocol": "anthropic-compatible"}],
        "adapter": "anthropic-compatible-worker",
        "credential": {"kind": "subscription_key", "env_file_ref": "VENDOR_A_KEY_FILE",
                       "generic_env_forbidden": ["VENDOR_A_TOKEN"]},
        "billing": _billing(), "capacity_observer": {"source": "human-reading", "freshness_horizon_s": 3600, "command": None},
        "discovery": None, "private_terms": []}))
    status = routing._cli(
        ["--eligibility", "--observations", str(log), "--task-class", "T",
         "--manifest", str(manifest_path), "--environment-from-current-process", "--json"])
    assert status == 0
    assert captured, "fixture is inert: the fingerprint was never consulted"
    for environment in captured:
        assert environment is None or all(value == "" for value in environment.values()), (
            "a value from the process environment reached the fingerprint"
        )
    assert "fixture-only-value" not in capsys.readouterr().out


# =============================================================================
# T2 round 2, R5/R6 — same-vendor ambiguity, and a fallback row that tells the truth
# =============================================================================


def test_not_routable_two_same_vendor_manifests_neither_declaring_the_client_are_ambiguous(
        tmp_path):
    """Two manifests at the row's own vendor, neither declaring its client:
    the vendor cannot choose between them, so the route is refused as
    ambiguous — identically in either list order, and never as mere absence."""
    log = _confirmed_log(tmp_path)
    one = _provider_manifest(provider_id="plan-one", vendor="vendor-a",
                             client="worker-x@gateway-a.example", pool_id="pool-one")
    two = _provider_manifest(provider_id="plan-two", vendor="vendor-a",
                             client="worker-y@gateway-a.example", pool_id="pool-two")
    rows_by_order = []
    for order in ([one, two], [two, one]):
        report = routing.eligibility_report(
            log, task_class="T", purpose=ROUTINE, manifests=order,
            authorised_pools=["pool-one", "pool-two"], environment={})
        row = report.rows[0]
        assert row.routability == routing.NOT_ROUTABLE_UNKNOWN and row.eligible is False
        assert any("declared manifests carry vendor vendor-a and none declares client "
                   "worker-a@gateway-a.example; an ambiguous route is refused"
                   in reason for reason in row.reasons)
        assert not any("no declared provider manifest covers" in reason
                       for reason in row.reasons), (
            "an ambiguity row must not also claim no manifest covers the configuration — "
            "two of them do"
        )
        rows_by_order.append(row)
    assert rows_by_order[0] == rows_by_order[1], "the answer depended on list order"


def test_not_routable_a_vendor_fallback_row_names_the_manifests_that_do_declare_the_client(
        tmp_path):
    """The row's own vendor has one manifest, which does not declare its
    client; two other vendors' manifests do. The row is matched by vendor and
    names the manifests that declare the client — the fact that repairs the
    route, rather than a bare id the coordinator must go and find."""
    log = _confirmed_log(tmp_path)
    home = _provider_manifest(provider_id="plan-a", vendor="vendor-a",
                              client="worker-x@gateway-a.example", pool_id="pool-a")
    other_b = _provider_manifest(provider_id="plan-b", vendor="vendor-b", pool_id="pool-b")
    other_c = _provider_manifest(provider_id="plan-c", vendor="vendor-c", pool_id="pool-c")
    report = routing.eligibility_report(
        log, task_class="T", purpose=ROUTINE, manifests=[home, other_b, other_c],
        authorised_pools=["pool-a", "pool-b", "pool-c"], environment={})
    row = report.rows[0]
    assert row.provider_id == "plan-a", "fixture is inert: the row must match its own vendor"
    reasons = " ".join(row.reasons)
    assert "the manifest was matched by vendor, not by client" in reasons
    assert "client worker-a@gateway-a.example is declared by other manifests: plan-b, plan-c" \
        in reasons


# =============================================================================
# T2 round 2, R7 — a reading dated in the future cannot be aged
# =============================================================================


def test_not_routable_a_future_dated_capacity_reading_is_unknown_and_cannot_be_aged(tmp_path):
    log = _confirmed_log(tmp_path)
    manifest = _provider_manifest()
    ahead = (datetime.now(timezone.utc) + timedelta(seconds=90)).isoformat()
    pool = capacity.Pool(pool_id="vendor-a-membership", remaining=100, unit="req",
                         observed_at=ahead)
    report = routing.eligibility_report(
        log, task_class="T", purpose=ROUTINE, manifests=[manifest], capacity_pools=[pool],
        authorised_pools=["vendor-a-membership"], environment={})
    row = report.rows[0]
    assert row.pool.freshness == UNKNOWN, "a negative age was read as FRESH"
    assert row.pool.age_seconds is not None and row.pool.age_seconds < 0
    assert any("observed in the future by" in reason and "cannot be aged" in reason
               for reason in row.reasons)
    assert any("capacity UNKNOWN: dispatch serially" in reason for reason in row.reasons)


# =============================================================================
# T2 round 2, R8 — echoed input renders as one bounded line
# =============================================================================


def test_bounded_renders_one_printable_bounded_line_however_hostile_the_text():
    newline = routing._bounded("pool-\nwith-a-line-break")
    huge = routing._bounded("x" * 10000)
    for rendered in (newline, huge):
        assert "\n" not in rendered
        assert len(rendered) <= 80
        assert rendered.startswith('"') and rendered.endswith('"')
    assert newline.startswith('"pool-')


def test_cli_eligibility_renders_hostile_pool_ids_as_one_bounded_line_each(tmp_path, capsys):
    """A pool id carrying a newline and one ten thousand characters long, each
    quarantined: every note is one line, bounded, and still names its pool."""
    log = _confirmed_log(tmp_path)
    capacity_doc = tmp_path / "capacity.json"
    capacity_doc.write_text(json.dumps({"pools": [
        {"pool_id": "pool-\nslash", "remaining": -5},
        {"pool_id": "z" * 10000, "remaining": -5},
    ]}), encoding="utf-8")
    status = routing._cli(["--eligibility", "--observations", str(log), "--task-class", "T",
                           "--capacity", str(capacity_doc)])
    assert status == 0
    quarantine_lines = [line for line in capsys.readouterr().out.splitlines()
                        if "could not be read" in line]
    assert len(quarantine_lines) == 2, (
        "a newline inside a pool id must not manufacture or swallow a note line"
    )
    for line in quarantine_lines:
        assert len(line) <= 200, "a hostile pool id made an unbounded line"
        assert line.lstrip().startswith("note: pool ")


# =============================================================================
# T2 round 2, N2 — the dead CRITICAL line under UNKNOWN freshness, removed on proof
# =============================================================================


def test_not_routable_critical_over_an_unknowable_pool_is_refused_on_availability(tmp_path):
    """The pin for removing the unreachable `if purpose == CRITICAL: eligible
    = False` under UNKNOWN freshness: a CRITICAL row over a pool whose
    remaining is UNKNOWN is ALREADY refused — by availability, which a report
    cannot establish — so that line decided nothing, and the caution it guarded
    now belongs to the purposes that can still act on it."""
    log = _confirmed_log(tmp_path)
    manifest = _provider_manifest()
    pool = capacity.Pool(pool_id="vendor-a-membership", unit="req")
    report = routing.eligibility_report(
        log, task_class="T", purpose=CRITICAL, manifests=[manifest], capacity_pools=[pool],
        authorised_pools=["vendor-a-membership"], environment={})
    row = report.rows[0]
    assert row.eligible is False
    assert any("not established by a dispatch" in reason for reason in row.reasons)
    assert not any("dispatch serially" in reason for reason in row.reasons), (
        "a CRITICAL row is refused, not advised"
    )
