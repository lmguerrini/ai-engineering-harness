"""Which configuration a task may go to, and the honest reason it may not.

Three questions that were one question, and the conflation was the defect:

    DISCOVERED    an execution surface offered this identifier      model_discovery
    AVAILABLE     a dispatch under these preconditions has started  here
    QUALIFIED     this configuration has done this task class       qualification

Each is answered by its own evidence and none substitutes for another. The pack
already said the first two sentences of that — `DECISIONS.md` D8, *availability
is never qualification* — and had no place to put the middle one, so it lived
inside the qualification key, where two dispatches identical in all nine
dimensions but differing in whether standard input was closed were graded as one:
the shipped log has that pair, and one of them never started.

## What availability actually rests on

**A completed run, or an observed refusal. Nothing else.** Not membership of a
discovery document: this release watched a model listed locally be refused by the
provider, and watched the same account offer different sets under two client
versions minutes apart. Discovery is an input to the *question*, never an answer
to it — so a model absent from a stale document that is currently running is
available, and a model listed in a fresh one that has never run is `UNKNOWN`.

Availability is keyed on the configuration **plus the dispatch preconditions**,
because a precondition is what decides whether the thing starts at all.

## What this module refuses to do

It does not launch anything, does not contact a network, does not write the
observation log, and does not decide that a route is a good idea. It reports a
ranked list with a reason per candidate and a reason per rejection, and the
decision stays with the coordinator — which is where
`policy/routing-policy.md` has always kept it, in three coordinator-applied
stages with no software.

Two guarantees hold the ranking honest. **An advisory family prior never ranks**:
it is printed so a coordinator is not left with nothing, and it breaks no tie,
satisfies no eligibility test and moves no candidate. And **newest is never a
reason**: nothing here reads a version, a generation or a priority number, so a
model is preferred over another only where its own evidence at this task class is
stronger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import qualification
from backend_contract import TaskClassGrade
from qualification import UNKNOWN, ConfigurationIdentity, Prior

__all__ = [
    "UNKNOWN",
    "AVAILABLE",
    "UNAVAILABLE",
    "AVAILABILITY_STATES",
    "DISPOSITIONS",
    "PROBE",
    "ROUTINE",
    "CRITICAL",
    "PURPOSES",
    "RoutingError",
    "Derivation",
    "AvailabilityObservation",
    "availability_for",
    "Candidate",
    "disposition_of",
    "eligibility",
    "independence_problems",
    "Role",
    "DESIGN_AUDIT_ROLES",
    "RouteReport",
    "design_audit_route",
]


class RoutingError(Exception):
    """A route was asked for on terms that cannot be answered."""


#: A dispatch under these preconditions has been observed to start.
AVAILABLE = "AVAILABLE"
#: A dispatch under these preconditions has been observed to be refused.
UNAVAILABLE = "UNAVAILABLE"
AVAILABILITY_STATES = (AVAILABLE, UNAVAILABLE, UNKNOWN)

#: What a candidate is, in one word, derived from both axes and stored nowhere.
#: The five qualification words are `backend_contract`'s own — this introduces no
#: second vocabulary for the same idea — and the three others describe the
#: availability axis, which had no words at all.
DISPOSITIONS = (
    "QUALIFIED",
    "PROVISIONAL",
    "UNPROBED",
    "CONTRADICTED",
    "ENVIRONMENTAL_UNKNOWN",
    "AVAILABLE",
    "UNAVAILABLE",
    UNKNOWN,
)

#: A bounded exploratory dispatch whose purpose is to produce the first evidence.
PROBE = "PROBE"
#: Ordinary work.
ROUTINE = "ROUTINE"
#: A mandatory independent audit leg, or a critical-domain promotion. HITL rows
#: 12 and 16 keep their human and this refuses rather than substituting.
CRITICAL = "CRITICAL"
PURPOSES = (PROBE, ROUTINE, CRITICAL)


@dataclass(frozen=True)
class Derivation:
    """Who produced a piece of work, for deciding what is independent of it.

    Independence is a property of the PRODUCER, not of the configuration. Key
    equality is wrong in both directions and an independent reader demonstrated
    both: the same session auditing its own work has a different key the moment
    the task class changes, and two genuinely fresh blind sessions have an
    identical one — which is exactly what `AUDIT_PRIMARY` is.
    """

    #: The worker or agent that produced the work. Not a display name.
    producer: str = UNKNOWN
    #: The session it ran in. A reader in the producer's own session is not fresh
    #: however different its configuration.
    session: str = UNKNOWN
    #: For a leg declared cross-provider. Two models from one provider are not a
    #: cross-provider reading, whatever else differs.
    provider: str = UNKNOWN
    surface: str = UNKNOWN


def independence_problems(
    reader: Derivation,
    subject: Derivation,
    *,
    require_distinct_provider: bool = False,
) -> tuple[str, ...]:
    """Every reason this reader is not independent of this work.

    Fails closed: an unestablished producer or session is a refusal, because
    "nobody recorded who did it" is not "somebody else did it".
    """
    found = []
    if reader.producer == UNKNOWN or subject.producer == UNKNOWN:
        found.append(
            "independence cannot be established: the producer of the reader or of the work is "
            "not recorded, and an unrecorded producer is not a different one"
        )
    elif reader.producer == subject.producer:
        found.append(
            f"the proposed reader is the producer of the work ({reader.producer}). A producer "
            f"never closes its own finding, whatever task class it is dispatched under"
        )
    if reader.session == UNKNOWN or subject.session == UNKNOWN:
        found.append(
            "session freshness cannot be established: one of the sessions is not recorded"
        )
    elif reader.session == subject.session:
        found.append(
            f"the reader would run in the session that produced the work ({reader.session}); a "
            f"blind reading is a fresh context, not a fresh instruction"
        )
    if require_distinct_provider:
        if reader.provider == UNKNOWN or subject.provider == UNKNOWN:
            found.append(
                "this leg is declared cross-provider and a provider is not recorded on both "
                "sides, so distinctness cannot be established"
            )
        elif reader.provider == subject.provider:
            found.append(
                f"this leg is declared cross-provider and both sides are {reader.provider}; two "
                f"models from one provider are one provider's reading"
            )
    return tuple(found)


@dataclass(frozen=True)
class AvailabilityObservation:
    """One observed dispatch outcome, which is the only availability evidence.

    `preconditions` is part of the key. The shipped log holds two dispatches at
    one configuration where the only difference is whether standard input was
    closed: one never started, the other validated, and a scheme in which the
    second answers for the first is a scheme that routes to a dispatch known to
    hang.
    """

    identity: ConfigurationIdentity
    preconditions: frozenset = field(default_factory=frozenset)
    state: str = UNKNOWN
    observed_at: str = UNKNOWN
    #: The client the dispatch actually ran on. Not keyed for qualification;
    #: reported here because availability is exactly the question a client
    #: version has been observed to change.
    build: str = UNKNOWN
    detail: str = ""

    def __post_init__(self) -> None:
        if self.state not in AVAILABILITY_STATES:
            raise RoutingError(
                f"availability {self.state!r} is not one of {', '.join(AVAILABILITY_STATES)}"
            )

    def key(self) -> tuple:
        return tuple(self.identity.dimensions().values()) + (
            tuple(sorted(self.preconditions)),
        )


def availability_for(
    identity: ConfigurationIdentity,
    preconditions,
    observations,
    *,
    build: str = UNKNOWN,
) -> "tuple[str, tuple[str, ...]]":
    """This configuration's availability under these preconditions, and why.

    The most recent observation wins, and where two carry the same date a refusal
    outranks a success: availability is the question where the conservative
    reading is the safe one, and a dispatch that has been seen to be refused is
    not made available by an older success.

    An observation recorded on a different client is reported and does not
    answer. That is the measured case rather than a hypothetical — this release
    watched one client run a model the other refused.
    """
    wanted = tuple(sorted(frozenset(preconditions)))
    dimensions = tuple(identity.dimensions().values())
    notes: list[str] = []
    matching = []
    for observation in observations:
        if observation.key() != dimensions + (wanted,):
            continue
        if build != UNKNOWN and observation.build != UNKNOWN and observation.build != build:
            notes.append(
                f"an availability observation for this configuration exists at client "
                f"{observation.build} and the dispatch would use {build}; it is reported and does "
                f"not answer, because a client version has been observed to change which models "
                f"a provider accepts"
            )
            continue
        matching.append(observation)
    if not matching:
        notes.append(
            "no dispatch has been observed at this configuration under these preconditions, so "
            "availability is UNKNOWN. Discovery membership is not an answer to this question"
        )
        return UNKNOWN, tuple(notes)
    # A REFUSAL WINS A TIE. Sorted ascending and read from the end, so the
    # later observation wins and, on the same date, the refusal does: the
    # comparison used to be `!=`, which put the success last and let an older
    # success answer for a dispatch seen to be refused the same day.
    matching.sort(key=lambda o: (o.observed_at, o.state == UNAVAILABLE))
    latest = matching[-1]
    notes.append(
        f"availability {latest.state} from a dispatch observed {latest.observed_at}"
        + (f" — {latest.detail}" if latest.detail else "")
    )
    return latest.state, tuple(notes)


@dataclass(frozen=True)
class Candidate:
    """One configuration considered for one task, on both axes at once."""

    identity: ConfigurationIdentity
    task_class: str
    grade: TaskClassGrade
    availability: str = UNKNOWN
    #: Advisory only. Printed, never ranked on.
    prior: "Prior | None" = None
    discovered: "bool | None" = None
    derivation: Derivation = field(default_factory=Derivation)
    notes: tuple[str, ...] = ()

    @property
    def disposition(self) -> str:
        return disposition_of(self.availability, self.grade.grade)


def disposition_of(availability: str, grade: str) -> str:
    """One word for a candidate, derived from both axes.

    Availability decides first and adverse evidence decides next, so a
    configuration that cannot start never reads as qualified, and one with
    evidence against it never reads as merely unprobed.
    """
    if availability == UNAVAILABLE:
        return UNAVAILABLE
    if grade == "contradicted":
        return "CONTRADICTED"
    if availability == UNKNOWN:
        return UNKNOWN
    if grade == "confirmed":
        return "QUALIFIED"
    if grade == "provisional":
        return "PROVISIONAL"
    if grade == "environmental-unknown":
        return "ENVIRONMENTAL_UNKNOWN"
    return "UNPROBED"


@dataclass(frozen=True)
class Eligibility:
    allowed: bool
    reasons: tuple[str, ...] = ()

    def sentence(self) -> str:
        return ("eligible" if self.allowed else "NOT eligible") + (
            ": " + "; ".join(self.reasons) if self.reasons else ""
        )


def eligibility(candidate: Candidate, *, purpose: str) -> Eligibility:
    """Whether this candidate may take this work, for this purpose.

    The purpose is the caller's, because only the caller knows whether a dispatch
    is a bounded probe or a mandatory audit leg — the same rule
    `capability_open` already applies to the change class, for the same reason.
    """
    if purpose not in PURPOSES:
        raise RoutingError(
            f"purpose {purpose!r} is not one of {', '.join(PURPOSES)}. An unrecognised purpose is "
            f"not a small one: this refuses rather than choosing the lenient reading"
        )
    reasons: list[str] = []
    if candidate.availability == UNAVAILABLE:
        reasons.append(
            "a dispatch at this configuration has been observed to be refused; evidence of what "
            "it can do does not make it startable"
        )
    if candidate.grade.grade == "contradicted":
        reasons.append(
            f"this configuration is CONTRADICTED at {candidate.task_class!r}. Adverse evidence is "
            f"not absence of evidence"
        )
    if not candidate.identity.complete:
        reasons.append(
            "the configuration identity is INCOMPLETE ("
            + "; ".join(candidate.identity.incompleteness())
            + "), so nothing can be established about it"
        )

    if purpose == CRITICAL:
        if candidate.grade.grade != "confirmed":
            reasons.append(
                f"a mandatory independent audit leg or a critical-domain promotion needs a "
                f"CONFIRMED configuration at this task class; this one is "
                f"{candidate.grade.grade!r}. HITL rows 12 and 16 keep their human, and an "
                f"unavailable qualified worker is never authorization to use an unqualified one"
            )
        if candidate.availability != AVAILABLE:
            reasons.append(
                "availability at this configuration is not established by a dispatch, and a "
                "critical leg is not the place to find out"
            )
    elif purpose == ROUTINE:
        if candidate.grade.grade not in ("confirmed", "provisional"):
            reasons.append(
                f"this configuration is {candidate.grade.grade!r} at {candidate.task_class!r}. An "
                f"unprobed configuration takes work through a declared PROBE, which records what "
                f"it tested, not through ordinary routing"
            )
        if candidate.availability != AVAILABLE:
            reasons.append("availability is not established by an observed dispatch")
    else:  # PROBE
        if candidate.availability == UNAVAILABLE:
            pass  # already recorded above
    return Eligibility(not reasons, tuple(reasons))


@dataclass(frozen=True)
class Role:
    """One seat in a routed reading, described by what it must be, not by whom."""

    name: str
    purpose: str = ROUTINE
    require_distinct_provider: bool = False
    optional: bool = False
    why: str = ""


#: Derived roles, named by function. NO VENDOR, no model, no family appears here
#: or anywhere else in this module: the seats are described by the independence
#: and evidence they need, and which configuration fills one is computed from
#: what was discovered and what its evidence says.
DESIGN_AUDIT_ROLES = (
    Role("PRIMARY_DESIGN_READER", purpose=ROUTINE,
         why="reads the design against its own claims"),
    Role("INDEPENDENT_FALSIFIER", purpose=ROUTINE, require_distinct_provider=True,
         why="tries to break it, and must not share a provider with the primary reading"),
    Role("IMPLEMENTATION_SPECIALIST", purpose=ROUTINE, optional=True,
         why="reads the design against the domain it will be implemented in"),
)

#: Weakest first, so a sort by this index puts the strongest evidence last.
_GRADE_PRECEDENCE = (
    "contradicted",
    "unprobed",
    "environmental-unknown",
    "provisional",
    "confirmed",
)


def _rank(candidate: Candidate) -> tuple:
    """Order candidates by their OWN evidence, and by nothing else.

    Not by generation, not by a vendor's priority field, not by a context window
    and not by a family's history. A newer model outranks an older one here only
    where its own observations at this task class are stronger.
    """
    grade = candidate.grade
    return (
        _GRADE_PRECEDENCE.index(grade.grade) if grade.grade in _GRADE_PRECEDENCE else 0,
        grade.validated,
        grade.field_observations,
        -grade.contradicted,
        candidate.availability == AVAILABLE,
    )


@dataclass
class RouteReport:
    """A ranked reading, its reasons, and everything it could not establish."""

    task_class: str
    subject: Derivation
    seats: list = field(default_factory=list)
    considered: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    @property
    def complete(self) -> bool:
        """Whether every non-optional seat was filled."""
        return all(
            seat["candidate"] is not None
            for seat in self.seats
            if not seat["role"].optional
        )

    def render(self) -> str:
        lines = [
            f"design-audit route for {self.task_class!r}",
            f"  subject produced by {self.subject.producer} in session {self.subject.session} "
            f"({self.subject.provider})",
        ]
        for seat in self.seats:
            role = seat["role"]
            chosen = seat["candidate"]
            mark = "  " if chosen is not None or role.optional else "!!"
            if chosen is None:
                lines.append(f"{mark} {role.name:26} UNFILLED"
                             + (" (optional)" if role.optional else ""))
            else:
                lines.append(
                    f"{mark} {role.name:26} {chosen.identity.model_observed} "
                    f"[{chosen.disposition}] on {chosen.identity.surface}"
                )
            lines.append(f"       why this seat: {role.why}")
            for reason in seat["reasons"]:
                lines.append(f"       {reason}")
        if self.considered:
            lines.append("  considered and not chosen:")
            for entry in self.considered:
                lines.append(f"    {entry}")
        lines.extend(f"  note: {note}" for note in self.notes)
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {
            "task_class": self.task_class,
            "complete": self.complete,
            "seats": [
                {
                    "role": seat["role"].name,
                    "optional": seat["role"].optional,
                    "chosen": (
                        None if seat["candidate"] is None
                        else {
                            "model_observed": seat["candidate"].identity.model_observed,
                            "surface": seat["candidate"].identity.surface,
                            "disposition": seat["candidate"].disposition,
                            "grade": seat["candidate"].grade.grade,
                            "availability": seat["candidate"].availability,
                            "observations": seat["candidate"].grade.observations,
                            "prior": (
                                None if seat["candidate"].prior is None
                                else seat["candidate"].prior.sentence()
                            ),
                        }
                    ),
                    "reasons": list(seat["reasons"]),
                }
                for seat in self.seats
            ],
            "considered": list(self.considered),
            "notes": list(self.notes),
        }


def design_audit_route(
    candidates,
    *,
    task_class: str,
    subject: Derivation,
    roles=DESIGN_AUDIT_ROLES,
    allow_probe: bool = False,
) -> RouteReport:
    """Fill each seat from the candidates, on evidence and independence alone.

    `allow_probe` lets an unprobed configuration take a seat **as a declared
    probe**, which is how the first evidence for anything is ever obtained: an
    empty table cannot acquire its first observation if qualification is required
    before every dispatch. It never applies to a `CRITICAL` seat, and the report
    says which seats were filled that way.
    """
    report = RouteReport(task_class=task_class, subject=subject)
    taken: set = set()
    for role in roles:
        reasons: list[str] = []
        pool = []
        for candidate in candidates:
            if candidate.task_class != task_class:
                continue
            name = candidate.identity.model_observed
            if name in taken:
                reasons.append(
                    f"{name}: already seated in this reading; one configuration cannot hold two "
                    f"seats and still be two readings"
                )
                continue
            purpose = role.purpose
            verdict = eligibility(candidate, purpose=purpose)
            if not verdict.allowed and allow_probe and role.purpose != CRITICAL:
                probe = eligibility(candidate, purpose=PROBE)
                if probe.allowed:
                    verdict = Eligibility(True, (
                        "seated as a DECLARED PROBE: unprobed at this task class, and its outcome "
                        "becomes evidence for this configuration and for no other",
                    ))
            if not verdict.allowed:
                reasons.append(f"{name}: {verdict.sentence()}")
                continue
            conflicts = independence_problems(
                candidate.derivation, subject,
                require_distinct_provider=role.require_distinct_provider,
            )
            if conflicts:
                reasons.append(f"{name}: not independent — {'; '.join(conflicts)}")
                continue
            pool.append((candidate, verdict))
        pool.sort(key=lambda pair: _rank(pair[0]))
        chosen = pool[-1][0] if pool else None
        if chosen is not None:
            taken.add(chosen.identity.model_observed)
            reasons.extend(pool[-1][1].reasons)
            reasons.append(
                f"chosen on its own evidence at {task_class!r}: {chosen.grade.grade} on "
                f"{chosen.grade.observations} observation(s) "
                f"({chosen.grade.validated} validated, {chosen.grade.contradicted} contradicted)"
            )
            if chosen.prior is not None:
                reasons.append(chosen.prior.sentence())
                reasons.append(
                    "the prior above did not rank this candidate and broke no tie; it is printed "
                    "so the reading is not left with nothing"
                )
            for other, _ in reversed(pool[:-1]):
                report.considered.append(
                    f"{other.identity.model_observed} for {role.name}: eligible, ranked lower on "
                    f"{other.grade.grade} / {other.grade.validated} validated"
                )
        elif not role.optional:
            reasons.append(
                "no candidate fills this seat. Unavailability is never authorization: the work "
                "waits, or a human decides (HITL rows 12, 16)"
            )
        report.seats.append({"role": role, "candidate": chosen, "reasons": reasons})
    report.notes.append(
        "ranked on per-configuration evidence at this task class only. No generation, priority, "
        "context window or family history entered the order"
    )
    return report


def _cli(argv: list[str]) -> int:
    """Report what the observation log and a discovery document jointly support."""
    import argparse
    import json as _json
    import sys
    from pathlib import Path as _Path

    parser = argparse.ArgumentParser(
        prog="routing.py",
        description="Report per-configuration routing state. Reports; authorises nothing.",
    )
    parser.add_argument(
        "observations", nargs="?",
        default=str(_Path(__file__).resolve().parent.parent / "policy" / "observations.jsonl"))
    parser.add_argument("--discovery", default=None, help="a discovery document to read")
    parser.add_argument("--task-class", default=None, help="report one task class")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        graded = qualification.qualifications_from_observations(args.observations)
        priors = qualification.priors_from_observations(args.observations)
    except Exception as exc:
        print(f"the observation log could not be read: {exc}", file=sys.stderr)
        return 2

    discovered: tuple = ()
    discovery_note = "no discovery document supplied, so DISCOVERED is UNKNOWN for every model"
    if args.discovery:
        try:
            import model_discovery

            reading = model_discovery.read(args.discovery)
            discovered = reading.identifiers()
            discovery_note = (
                f"{len(discovered)} identifier(s) discovered from {reading.source}, produced by "
                f"client {reading.producer} — discovery is not availability"
            )
        except Exception as exc:
            print(f"the discovery document could not be read: {exc}", file=sys.stderr)
            return 2

    payload = {
        "per_configuration": [
            {
                "identity": list(key[:-1]),
                "task_class": key[-1],
                "grade": grade.grade,
                "observations": grade.observations,
                "availability": UNKNOWN,
                "disposition": disposition_of(UNKNOWN, grade.grade),
            }
            for key, grade in sorted(graded.items())
            if args.task_class in (None, key[-1])
        ],
        "family_prior_advisory": [
            {"family": family, "task_class": task_class, "grade": grade.grade,
             "observations": grade.observations}
            for (family, task_class), grade in sorted(priors.items())
            if args.task_class in (None, task_class)
        ],
        "discovered": list(discovered),
        "notes": [
            discovery_note,
            "a family prior is advisory: it never ranks a candidate and never satisfies "
            "eligibility",
            "availability is answered by an observed dispatch and is UNKNOWN here, because this "
            "command reads records and dispatches nothing",
        ],
    }
    if args.json:
        print(_json.dumps(payload, indent=2))
        return 0
    print(f"routing state from {args.observations}")
    print(f"  per-configuration qualifications: {len(payload['per_configuration'])}")
    for row in payload["per_configuration"]:
        print(f"    {'/'.join(row['identity'][:4])} @ {row['task_class']}: "
              f"{row['grade']} -> {row['disposition']}")
    print(f"  family priors (ADVISORY, display-only): {len(payload['family_prior_advisory'])}")
    print(f"  discovered identifiers: {len(payload['discovered'])}")
    for note in payload["notes"]:
        print(f"  note: {note}")
    return 0


if __name__ == "__main__":
    import sys

    from errors import run_cli
    from routing import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
