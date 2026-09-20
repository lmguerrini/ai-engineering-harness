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

import re
import time
import unicodedata
from dataclasses import replace, dataclass, field
from datetime import date
from typing import Iterable, Mapping

import capacity
import provider_manifest
import qualification
from errors import IntegrityError
from backend_contract import TaskClassGrade
from provider_manifest import (
    NOT_ROUTABLE_BILLING,
    NOT_ROUTABLE_CREDENTIAL,
    NOT_ROUTABLE_UNAUTHORISED,
    NOT_ROUTABLE_UNKNOWN,
)
from qualification import UNKNOWN, ConfigurationIdentity, Prior

__all__ = [
    "UNKNOWN",
    "AVAILABLE",
    "UNAVAILABLE",
    "AVAILABILITY_STATES",
    "DISPOSITIONS",
    "NOT_ROUTABLE_BILLING",
    "NOT_ROUTABLE_UNAUTHORISED",
    "NOT_ROUTABLE_CREDENTIAL",
    "NOT_ROUTABLE_UNKNOWN",
    "PROBE",
    "ROUTINE",
    "CRITICAL",
    "PURPOSES",
    "RoutingError",
    "Derivation",
    "DERIVATION_FIELDS",
    "derivation_from_observation",
    "AvailabilityObservation",
    "availability_for",
    "Candidate",
    "disposition_of",
    "disposition_with_routability",
    "eligibility",
    "independence_problems",
    "Role",
    "DESIGN_AUDIT_ROLES",
    "RouteReport",
    "design_audit_route",
    "PoolState",
    "EligibilityRow",
    "EligibilityReport",
    "eligibility_report",
]


class RoutingError(Exception):
    """A route was asked for on terms that cannot be answered."""


def _bounded(text: object, limit: int = 80) -> str:
    """A printable, single-line, length-bounded description of text this
    module did not produce and does not trust — a pool id, a client, a vendor,
    a manifest id echoed into a note or a reason.

    Non-printable characters are replaced with U+FFFD so a newline cannot
    inject a line and a zero-width space cannot hide; over-long text is
    truncated with `…`; and anything that had to be altered — or that carries
    whitespace or a quote, where a reader could no longer see where the echoed
    value ends and the sentence resumes — is quoted. A clean short token is
    left bare: quoting `bad` as `"bad"` states nothing `bad` does not, and the
    notes about ordinary ids read as they always did. The returned string is
    never longer than `limit` characters.
    """
    original = "" if text is None else str(text)
    cleaned = "".join(
        character if character.isprintable() else "�" for character in original
    )
    if len(cleaned) > limit - 2:
        cleaned = cleaned[:limit - 3] + "…"
    if cleaned != original or not cleaned or any(
        character.isspace() or character == '"' for character in cleaned
    ):
        return f'"{cleaned}"'
    return cleaned


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
    #: D29/D32: billing safety, imported from `provider_manifest` so the two
    #: modules share one vocabulary rather than each spelling it separately.
    NOT_ROUTABLE_BILLING,
    NOT_ROUTABLE_UNAUTHORISED,
    NOT_ROUTABLE_CREDENTIAL,
    NOT_ROUTABLE_UNKNOWN,
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
    #: The session it ran in, as an IDENTIFIER. Compared for equality, so it must
    #: be one — a session *class* is a different kind of fact and lives below.
    session: str = UNKNOWN
    #: Whether this reader ran in a NEW context, where no identifier is recorded.
    #: Two facts, not one, and conflating them is a defect this release made and
    #: a test caught: every fresh dispatch shares the class `fresh`, so comparing
    #: classes for equality reported two independent readings as one session. A
    #: session identifier cannot go in the log either — it is a private
    #: identifier and this pack's own publication scan refuses one — so the log
    #: records the class and this records what the class claims.
    fresh: "bool | None" = None
    #: For a leg declared cross-provider. Kept as the ALIAS source only (D30):
    #: independence itself is decided on `vendor`, never read here directly.
    provider: str = UNKNOWN
    #: Whose model this is. A leg declared cross-provider is satisfied only by
    #: a distinct vendor on both sides (D30) — two gateways of one vendor are
    #: one vendor's reading, whatever else differs.
    vendor: str = UNKNOWN
    #: The gateway that served this reading. Re-hosting keys a different
    #: configuration and the same vendor (D30); carried for the record and
    #: NEVER compared for independence.
    gateway: str = UNKNOWN
    surface: str = UNKNOWN


def _named(derivation: "Derivation") -> "Derivation":
    """The same derivation with every blank field reported as `UNKNOWN`."""
    from dataclasses import replace as _replace

    return _replace(derivation, **{
        field: (getattr(derivation, field) if str(getattr(derivation, field)).strip()
                else UNKNOWN)
        for field in ("producer", "session", "provider", "vendor", "gateway", "surface")
    })


#: The grammar a vendor name must satisfy to be read as a vendor at all. It
#: mirrors `provider_manifest._SLUG` and is stricter where that shape is
#: silent: a run of hyphens and a trailing hyphen are NOT normalised away —
#: they refuse (D30, fail-closed). Anything else that is not lowercase
#: alphanumerics joined by single hyphens — an underscore, a space, a dot, a
#: zero-width space, a Cyrillic look-alike — refuses the same way.
_VENDOR_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _separatorless(text: str) -> str:
    """The letters and digits of a vendor name, every separator removed — the
    form in which two spellings of one vendor are compared."""
    return "".join(character for character in text if character.isalnum())


def _canonical_vendor(text: object) -> str:
    """The one canonical reading of a vendor name, or `UNKNOWN`.

    Both sides of every vendor comparison cross this boundary (D30):
    NFKC, strip, casefold — so a full-width `ｖ` and a `V` are the same letter —
    and then the slug grammar, so a name that is not a slug reads as `UNKNOWN`
    rather than as a second vendor nothing validates. The honest sentinel word
    reads as `UNKNOWN` exactly as it does everywhere else in the toolbelt.
    """
    if text is None or isinstance(text, bool):
        return UNKNOWN
    normalised = unicodedata.normalize("NFKC", str(text)).strip().casefold()
    if not normalised or _separatorless(normalised) == "unknown":
        return UNKNOWN
    return normalised if _VENDOR_SLUG.fullmatch(normalised) else UNKNOWN


def _vendor_reading(derivation: "Derivation") -> "tuple[str, bool]":
    """`(canonical vendor, misspelt)`: the vendor this derivation names in its
    canonical form, and whether a NON-BLANK vendor was recorded that is not a
    vendor slug — the fact that turns "not recorded" into "not recorded, or is
    not a vendor slug" in the refusal, so a misspelling is named as one instead
    of passing silently as absence."""
    raw = derivation.vendor if derivation.vendor != UNKNOWN else derivation.provider
    normalised = unicodedata.normalize("NFKC", "" if raw is None else str(raw)).strip().casefold()
    canonical = _canonical_vendor(raw)
    # A blank and the honest sentinel word are ABSENCE, not misspelling; every
    # other non-blank recording that fails the grammar is.
    misspelt = (
        canonical == UNKNOWN
        and bool(normalised)
        and _separatorless(normalised) != "unknown"
    )
    return canonical, misspelt


def _vendor_of(derivation: "Derivation") -> str:
    """The vendor this derivation names, reading `provider` as its alias when
    `vendor` itself was never recorded (D30). The ONE place that fallback is
    read, so a caller comparing two derivations never has to know which field
    carried the fact."""
    return _vendor_reading(derivation)[0]


def _vendors_distinct(reader: "Derivation", subject: "Derivation") -> bool:
    """Whether the two sides name different, established vendors.

    Factored out so a mutation can be aimed at this comparison alone (O12):
    the vendor-equality guard is the property under test, not the caller
    around it. Two spellings of one vendor are one vendor even here: the
    canonical forms are compared and so are their separator-stripped forms,
    because a vendor does not become a different vendor by dropping, doubling
    or re-punctuating a hyphen (D30) — the fail-closed reading of a name that
    differs only in its separators is that it names the same vendor, never
    that it established a second one.
    """
    left = _vendor_of(reader)
    right = _vendor_of(subject)
    if left == UNKNOWN or right == UNKNOWN:
        return False
    return left != right and _separatorless(left) != _separatorless(right)


def independence_problems(
    reader: Derivation,
    subject: Derivation,
    *,
    require_distinct_provider: bool = False,
    #: An alias: either flag turns the cross-vendor check on (D30).
    require_distinct_vendor: bool = False,
) -> tuple[str, ...]:
    """Every reason this reader is not independent of this work.

    Fails closed: an unestablished producer or session is a refusal, because
    "nobody recorded who did it" is not "somebody else did it".
    """
    found = []
    # A BLANK IS NOT A VALUE. `" "` is not the `UNKNOWN` sentinel, so a
    # whitespace producer compared unequal to every other producer and satisfied
    # every check — an independent reader walked one into the mandatory
    # cross-provider leg. Normalised here as well as at the reader, because a
    # predicate that trusts its inputs to have been cleaned is a predicate that
    # will eventually be handed one that was not.
    reader = _named(reader)
    subject = _named(subject)
    if reader.producer == UNKNOWN or subject.producer == UNKNOWN:
        found.append(
            "independence cannot be established: the producer of the reader or of the work is "
            "not recorded, and an unrecorded producer is not a different one"
        )
    elif reader.producer == subject.producer:
        found.append(
            f"the proposed reader is the producer of the work "
            f"({_bounded(reader.producer, 40)}). A producer "
            f"never closes its own finding, whatever task class it is dispatched under"
        )
    known = reader.session != UNKNOWN and subject.session != UNKNOWN
    if known and reader.session == subject.session:
        found.append(
            f"the reader would run in the session that produced the work "
            f"({_bounded(reader.session, 40)}); a "
            f"blind reading is a fresh context, not a fresh instruction"
        )
    elif not known and reader.fresh is not True:
        # Fails closed on absence and is satisfied by EITHER of the two things
        # that establish it: a session identifier that differs, or an explicit
        # claim that this reader ran in a new context. Requiring both would
        # refuse every observation the log can legally carry, because a session
        # identifier is a private identifier and does not go in it.
        found.append(
            "session freshness cannot be established: no session identifier distinguishes the "
            "reader from the work, and the reader does not declare a fresh context"
        )
    if require_distinct_provider or require_distinct_vendor:
        # VENDOR, not provider or gateway (D30). Two gateways of one vendor are
        # one vendor's reading, whatever else differs, and `provider` is read
        # only as `vendor`'s alias, through `_vendor_of` — never compared here
        # in its own right.
        reader_vendor, subject_vendor = _vendor_of(reader), _vendor_of(subject)
        if reader_vendor == UNKNOWN or subject_vendor == UNKNOWN:
            # A vendor that was recorded but is not a slug is named as such:
            # `vendor_a` and `vendor a` are misspellings of a vendor, not two
            # vendors and not one, and pretending they were simply absent
            # hides the repair the caller has to make.
            misspelt = _vendor_reading(reader)[1] or _vendor_reading(subject)[1]
            found.append(
                "this leg is declared cross-provider and a vendor is not recorded on both "
                "sides, so distinctness cannot be established"
                + (", or is not a vendor slug" if misspelt else "")
            )
        elif not _vendors_distinct(reader, subject):
            known_gateways = sorted({
                gateway for gateway in (reader.gateway, subject.gateway) if gateway != UNKNOWN
            })
            gateway_clause = (
                f" ({' and '.join(_bounded(gateway) for gateway in known_gateways)})"
                if known_gateways else ""
            )
            spelling_clause = (
                "" if reader_vendor == subject_vendor
                else f" — {_bounded(subject_vendor, 32)} differs from it only by separators"
            )
            # BOUNDED IN PROSE, COMPARED IN FULL (O12, criterion 6): a vendor
            # slug has no length limit, so a ten-thousand-character pair once
            # rendered a twenty-thousand-character reason line. The comparison
            # above reads the whole name; the sentence a human reads does not —
            # and at 32, because the sentence is itself echoed inside a
            # "not independent —" reason and must leave the line its margin.
            found.append(
                f"this leg is declared cross-provider and both sides are vendor "
                f"{_bounded(reader_vendor, 32)}{spelling_clause}{gateway_clause}; two gateways "
                f"of one vendor are one vendor's reading"
            )
    return tuple(found)


#: How an observation records who produced it. A SESSION CLASS rather than a
#: session identifier: the pack's own publication scan refuses UUID-shaped
#: tokens in tracked content, and it is right to — a raw session id is a private
#: identifier and recording one to prove independence would be trading one
#: governance rule for another. What independence actually needs from the log is
#: whether two readings came from the same producer, the same provider, and
#: whether each was a fresh context; a class answers all three without naming a
#: session.
DERIVATION_FIELDS = ("producer", "provider", "session_class", "role", "vendor", "gateway")


def derivation_from_observation(row: dict) -> Derivation:
    """The producer behind one observation, where the observation recorded one.

    Absent fields stay `UNKNOWN`, and `independence_problems` fails closed on
    them: an observation that did not say who produced it cannot establish that
    somebody else did.
    """
    declared = row.get("derivation")
    if not isinstance(declared, dict):
        return Derivation()
    unknown = sorted(set(declared) - set(DERIVATION_FIELDS))
    if unknown:
        raise RoutingError(
            f"an observation records derivation field(s) {', '.join(unknown)}, which nothing "
            f"reads. Known: {', '.join(DERIVATION_FIELDS)}")
    session_class = str(declared.get("session_class") or "").strip().lower()
    # VENDOR, aliased from `provider` where it was never declared (D30). Both
    # cross the one canonical vendor boundary on the way in, so an observation
    # whose derivation names a vendor that is not a slug reads as `UNKNOWN`
    # here and refuses the leg there — never as a second vendor nothing
    # validates, and never as a spelling that evades the comparison.
    provider = _canonical_vendor(declared.get("provider"))
    vendor = _canonical_vendor(declared.get("vendor") or declared.get("provider"))
    return _named(Derivation(
        producer=str(declared.get("producer") or UNKNOWN),
        # NOT the session class. A class is shared by every dispatch of its kind,
        # so putting one where an identifier is compared reports two independent
        # readings as the same session — which is exactly what happened.
        session=UNKNOWN,
        fresh=True if session_class.startswith("fresh") else (None if not session_class else False),
        provider=provider,
        vendor=vendor,
        gateway=str(declared.get("gateway") or UNKNOWN),
        surface=str(row.get("surface") or UNKNOWN),
    ))


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


def _moment(text: object) -> "tuple":
    """One availability observation's instant, comparable across offsets.

    Returns `(0,)` for anything that cannot be read as a time, so an unreadable
    timestamp sorts before every readable one and can never win a comparison it
    should not be in. Refusing the observation outright was considered and
    rejected: the log is primary evidence and is not rewritten to suit a reader.
    """
    from datetime import datetime, timezone

    raw = str(text).strip()
    if not raw:
        return (0,)
    normalised = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    for shape in (normalised, normalised + "T00:00:00+00:00"):
        try:
            moment = datetime.fromisoformat(shape)
        except ValueError:
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return (1, moment.timestamp())
    return (0,)


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
    # THE BUILD IS RESOLVED, not merely accepted. It defaulted to the caller's
    # argument alone, so a caller that omitted it — while the identity itself
    # carried one — got a positive answer from an observation on a different
    # client. Two arguments naming the same fact is how they come to disagree.
    if build == UNKNOWN:
        build = identity.build
    matching = []
    for observation in observations:
        if observation.key() != dimensions + (wanted,):
            continue
        # BOTH must be established and equal. `UNKNOWN` on either side used to
        # match everything, so an observation that did not say which client it
        # ran on answered for every client. A client version is precisely the
        # thing this release watched change which models a provider accepts, so
        # not knowing it is not knowing the answer.
        if build != observation.build or build == UNKNOWN:
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
    # ORDERED IN REAL TIME, not as text. Sorting the timestamps lexically put a
    # `+02:00` success after a `Z` refusal that happened an hour LATER, so an
    # older success answered for a dispatch that had since been refused — the
    # exact inversion the tie-break below exists to prevent, reached through the
    # comparison rather than through the tie. Found by an independent reading of
    # this release's behaviour. An unparseable timestamp sorts FIRST, so it can
    # never outrank one that can be read.
    matching.sort(key=lambda o: (_moment(o.observed_at), o.state == UNAVAILABLE))
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


#: Every disposition `provider_manifest.routability` can return. Billing
#: safety precedes availability and grade (D29, D32): a route that is not
#: provably safe to bill is not routed to for being merely qualified.
_NOT_ROUTABLE = (
    NOT_ROUTABLE_BILLING,
    NOT_ROUTABLE_UNAUTHORISED,
    NOT_ROUTABLE_CREDENTIAL,
    NOT_ROUTABLE_UNKNOWN,
)


def disposition_with_routability(routability_disposition: str, availability: str, grade: str) -> str:
    """One word for a candidate, billing safety checked before either axis.

    A `NOT_ROUTABLE_*` disposition wins before availability or grade is even
    read — the same precedence `eligibility`'s `routability` keyword applies —
    so a confirmed, available configuration behind an unauthorised or
    unproven billing route never reads as merely qualified. `ROUTABLE` hands
    the word to `disposition_of`, which stays untouched. Anything ELSE —
    `UNKNOWN`, a lower-case spelling, a word nobody defined — reads as
    `NOT_ROUTABLE_UNKNOWN`: a value outside the vocabulary is not an
    established route, and treating it as one is how a refused disposition
    once outranked nothing at all.
    """
    if routability_disposition in _NOT_ROUTABLE:
        return routability_disposition
    if routability_disposition != provider_manifest.ROUTABLE:
        return NOT_ROUTABLE_UNKNOWN
    return disposition_of(availability, grade)


@dataclass(frozen=True)
class Eligibility:
    allowed: bool
    reasons: tuple[str, ...] = ()

    def sentence(self) -> str:
        return ("eligible" if self.allowed else "NOT eligible") + (
            ": " + "; ".join(self.reasons) if self.reasons else ""
        )


def eligibility(
    candidate: Candidate, *, purpose: str, routability: "str | None" = None,
) -> Eligibility:
    """Whether this candidate may take this work, for this purpose.

    The purpose is the caller's, because only the caller knows whether a dispatch
    is a bounded probe or a mandatory audit leg — the same rule
    `capability_open` already applies to the change class, for the same reason.

    `routability` is optional and defaults to `None`, which keeps every
    existing caller's behaviour unchanged. `None` means the question was not
    asked and `ROUTABLE` means the route is established; a `NOT_ROUTABLE_*`
    disposition refuses the candidate for EVERY purpose, PROBE included —
    billing safety precedes evidence of what the configuration can do (D29) —
    and ANY other value refuses the same way, because a routability outside
    the vocabulary is not an established route and must never read as one.
    """
    if purpose not in PURPOSES:
        raise RoutingError(
            f"purpose {purpose!r} is not one of {', '.join(PURPOSES)}. An unrecognised purpose is "
            f"not a small one: this refuses rather than choosing the lenient reading"
        )
    reasons: list[str] = []
    if routability is not None:
        if routability in _NOT_ROUTABLE:
            # TWO SENTENCES, TWO REASONS (O12, criterion 6): the render puts one
            # reason on one line, and a single 200+-character sentence made a
            # line no terminal shows whole. Split where the thought splits.
            reasons.append(f"billing safety refuses this route: {routability}")
            reasons.append(
                "an unauthorised or unproven billing route is refused for every purpose, "
                "PROBE included, whatever the configuration's own evidence says (D29)"
            )
        elif routability != provider_manifest.ROUTABLE:
            reasons.append(
                f"routability {_bounded(routability)} is not ROUTABLE, so the route is not "
                f"established"
            )
    if candidate.grade.task_class != candidate.task_class:
        # THE GRADE CARRIES THE CLASS IT WAS MEASURED AT, and nothing compared
        # the two: a candidate declared at one class holding a grade measured at
        # another passed a CRITICAL leg. `unprobed at every other class` is the
        # rule the whole release rests on, and it is worth nothing if the
        # evidence and the question can name different classes. The classes are
        # BOUNDED echoes: a task class is caller-supplied text, and an unbounded
        # one once rendered a reason line as long as it liked.
        reasons.append(
            f"this candidate is offered for {_bounded(candidate.task_class, 40)} and carries "
            f"evidence measured at {_bounded(candidate.grade.task_class, 40)}"
        )
        reasons.append(
            "a grade at one task class is unprobed at every other, so this grade answers a "
            "different question"
        )
    if candidate.availability == UNAVAILABLE:
        reasons.append(
            "a dispatch at this configuration has been observed to be refused; evidence of what "
            "it can do does not make it startable"
        )
    if candidate.grade.grade == "contradicted":
        reasons.append(
            f"this configuration is CONTRADICTED at {_bounded(candidate.task_class, 40)}. "
            f"Adverse evidence is not absence of evidence"
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
                f"{candidate.grade.grade!r}"
            )
            reasons.append(
                "HITL rows 12 and 16 keep their human, and an unavailable qualified worker is "
                "never authorization to use an unqualified one"
            )
        if candidate.availability != AVAILABLE:
            reasons.append(
                "availability at this configuration is not established by a dispatch, and a "
                "critical leg is not the place to find out"
            )
    elif purpose == ROUTINE:
        if candidate.grade.grade not in ("confirmed", "provisional"):
            reasons.append(
                f"this configuration is {candidate.grade.grade!r} at "
                f"{_bounded(candidate.task_class, 40)}"
            )
            reasons.append(
                "an unprobed configuration takes work through a declared PROBE, which records "
                "what it tested, not through ordinary routing"
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
    #: Whether an UNPROBED configuration may fill this seat as a declared probe.
    #: **False for every mandatory independent leg**, and the default is derived
    #: rather than typed: a seat that requires a distinct provider IS the
    #: mandatory cross-vendor leg `policy/hitl-matrix.md` row 12 governs, and an
    #: independent reader seated a probe in exactly that seat because the flag
    #: keyed on `purpose` alone. `None` means "derive it"; a caller may still say
    #: so explicitly.
    probeable: "bool | None" = None

    @property
    def accepts_a_probe(self) -> bool:
        if self.probeable is not None:
            return self.probeable
        return self.purpose != CRITICAL and not self.require_distinct_provider


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
    #: The READERS already seated, not their model names. Deduplicating by name
    #: was wrong in both directions, and an independent reader produced both: two
    #: readings by the SAME producer in the SAME session were seated because
    #: their models differed, and two genuinely independent sessions were refused
    #: because their model was the same. A reading is a producer in a session.
    seated: list = []
    for role in roles:
        reasons: list[str] = []
        pool = []
        for candidate in candidates:
            if candidate.task_class != task_class:
                continue
            name = candidate.identity.model_observed
            already = [
                other for other in seated
                if (other.derivation.producer, other.derivation.session)
                == (candidate.derivation.producer, candidate.derivation.session)
            ]
            if already:
                reasons.append(
                    f"{name}: this producer already holds a seat in this reading; two seats "
                    f"filled by one producer in one session are one reading, whatever models "
                    f"they name"
                )
                continue
            purpose = role.purpose
            verdict = eligibility(candidate, purpose=purpose)
            if not verdict.allowed and allow_probe and role.accepts_a_probe:
                probe = eligibility(candidate, purpose=PROBE)
                if probe.allowed:
                    verdict = Eligibility(True, (
                        "seated as a DECLARED PROBE: unprobed at this task class, and its outcome "
                        "becomes evidence for this configuration and for no other",
                    ))
            if not verdict.allowed:
                reasons.append(f"{name}: {verdict.sentence()}")
                continue
            conflicts = list(independence_problems(
                candidate.derivation, subject,
                require_distinct_provider=role.require_distinct_provider,
            ))
            # AND INDEPENDENT OF THE READERS ALREADY SEATED. A cross-provider
            # seat exists to differ from the other READING, and the check
            # compared it only against the subject — so two readers from one
            # provider filled a route that then reported itself complete.
            for other in seated:
                conflicts.extend(
                    f"against the reading already seated: {problem}"
                    for problem in independence_problems(
                        candidate.derivation, other.derivation,
                        require_distinct_provider=role.require_distinct_provider,
                    )
                )
            if conflicts:
                reasons.append(f"{name}: not independent — {'; '.join(conflicts)}")
                continue
            pool.append((candidate, verdict))
        pool.sort(key=lambda pair: _rank(pair[0]))
        chosen = pool[-1][0] if pool else None
        if chosen is not None:
            seated.append(chosen)
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


# =============================================================================
# The eligibility report (S0-C5, O3)
#
# It lists every configuration this task class has evidence for, joined to
# what it would bill and how fresh its capacity is, and says which of them are
# eligible and why. **It never dispatches, never ranks by newness and never
# picks** — those verbs stay with the coordinator, in
# `policy/routing-policy.md`'s three coordinator-applied stages. An advisory
# family prior still satisfies no eligibility test here either.
# =============================================================================


@dataclass(frozen=True)
class PoolState:
    """One capacity pool's state, as far as this report can read it.

    Never a dispatch decision — `capacity.gate` is the module that takes one.
    `freshness` is computed against `capacity._STALE_READING_SECONDS`, the same
    horizon `capacity.gate` itself ages a reading against, and is `UNKNOWN`
    whenever either `remaining` or `observed_at` is unestablished: a number
    with no moment is not a reading (`capacity.Pool`'s own contract). A
    NEGATIVE age — a reading dated in the future — is UNKNOWN the same way:
    a moment this side of the observation cannot be used to age it.
    """

    pool_id: str
    remaining: "float | str" = UNKNOWN
    unit: str = "units"
    observed_at: "str | None" = None
    age_seconds: "float | None" = None
    freshness: str = UNKNOWN


def _pool_state(pool: "capacity.Pool", *, now: "float | None") -> PoolState:
    moment = capacity._moment(pool.observed_at) if pool.observed_at else None
    if pool.remaining == UNKNOWN or moment is None:
        return PoolState(pool_id=pool.pool_id, remaining=pool.remaining, unit=pool.unit,
                          observed_at=pool.observed_at, age_seconds=None, freshness=UNKNOWN)
    current = now if now is not None else time.time()
    age = current - moment.timestamp()
    if age < 0:
        # A reading dated AHEAD of the question being asked of it cannot be
        # aged: there is no honest FRESH or STALE for a negative age, only
        # UNKNOWN with the size of the future it claims, carried by the row.
        return PoolState(pool_id=pool.pool_id, remaining=pool.remaining, unit=pool.unit,
                          observed_at=pool.observed_at, age_seconds=age, freshness=UNKNOWN)
    freshness = "STALE" if age > capacity._STALE_READING_SECONDS else "FRESH"
    return PoolState(pool_id=pool.pool_id, remaining=pool.remaining, unit=pool.unit,
                      observed_at=pool.observed_at, age_seconds=age, freshness=freshness)


def _match_manifest(
    client: str, family: str, manifests: "tuple[provider_manifest.ProviderManifest, ...]",
) -> "tuple[provider_manifest.ProviderManifest | None, int | None]":
    """The manifest, and the matching surface index, this configuration would
    route through — or `(None, None)` when none does.

    Matched by CLIENT first, on any surface any manifest declares: the surface
    a configuration actually dispatches through is the fact that decides its
    route. Falls back to VENDOR only when exactly one manifest names it,
    because two manifests sharing a vendor is an ambiguity this function
    refuses to guess through rather than silently pick one.

    Every vendor comparison is CANONICAL (D30): `Vendor-A` and `vendor-a` are
    one vendor, so a manifest declaring one spelling matches a family recorded
    in the other — the raw comparison refused a route that existed because two
    honest writers disagreed about a capital letter.
    """
    canonical_family = _canonical_vendor(family)
    by_client = [
        (manifest, index)
        for manifest in manifests
        for index, surface in enumerate(manifest.surfaces)
        if surface.client == client
    ]
    if len(by_client) > 1:
        # One gateway serving several vendors, or several accounts at one
        # gateway, declares the same client string more than once. Narrow by
        # the configuration's own vendor; what is still ambiguous after that
        # is refused — the answer must not depend on the order the project
        # listed its manifests in.
        by_client = [
            pair for pair in by_client
            if _canonical_vendor(pair[0].vendor) == canonical_family
        ]
    if len(by_client) == 1:
        return by_client[0]
    if len(by_client) > 1:
        # MANIFESTS ARE COUNTED, not (manifest, surface) pairs: one manifest
        # declaring the client on two surfaces is ONE manifest with an
        # ambiguous surface, not two manifests, and a refusal that counts it
        # as two states a falsehood about the project's own declarations.
        if len({pair[0] for pair in by_client}) == 1:
            raise RoutingError(
                f"manifest {_bounded(by_client[0][0].provider_id)} declares client "
                f"{_bounded(client)} on {len(by_client)} surfaces; an ambiguous route is refused"
            )
        raise RoutingError(
            f"{len({pair[0] for pair in by_client})} declared manifests match client "
            f"{_bounded(client)} at vendor {_bounded(family)}; an ambiguous route is refused "
            f"rather than resolved by list order"
        )
    by_vendor = [
        manifest for manifest in manifests
        if _canonical_vendor(manifest.vendor) == canonical_family
    ]
    if len(by_vendor) > 1:
        # Two manifests at one vendor and NEITHER declares this client: the
        # configuration's own vendor cannot choose between them, so this is an
        # ambiguity like the client-side one above — refused, never resolved
        # by list order, and never reported as mere absence, because the
        # project has declared two routes where one was asked for.
        raise RoutingError(
            f"{len(by_vendor)} declared manifests carry vendor {_bounded(family)} and none "
            f"declares client {_bounded(client)}; an ambiguous route is refused"
        )
    if len(by_vendor) == 1:
        # The route the configuration actually dispatches through is not a
        # surface this manifest declares; the billing facts are the manifest's
        # and hold for every surface, but the recorded endpoint is not this
        # configuration's client — the row says so.
        return by_vendor[0], 0
    return None, None


@dataclass(frozen=True)
class EligibilityRow:
    """One configuration's evidence, route and verdict — nothing chosen."""

    identity: tuple
    task_class: str
    grade: str
    observations: int
    availability: str
    vendor: str
    gateway: str
    provider_id: str
    billing_pool_id: str
    routability: str
    pool: "PoolState | None"
    independence: "tuple[str, ...]"
    disposition: str
    eligible: bool
    reasons: "tuple[str, ...]"
    #: True exactly when this verdict was reached by SUPPOSING availability —
    #: a report dispatches nothing, so for PROBE and ROUTINE it asks the
    #: frozen predicate what would still refuse if a dispatch started, and a
    #: row that owes its verdict to a supposition must never be read as one
    #: that observed anything. A CRITICAL row never supposes.
    availability_supposed: bool = False


@dataclass(frozen=True)
class EligibilityReport:
    """Every configuration this task class has evidence for, joined and
    explained. Rows are in IDENTITY ORDER — never sorted by grade or
    newness — because a report that ranks is a router with a different name."""

    task_class: str
    purpose: str
    require_distinct_vendor: bool
    subject: "Derivation | None"
    rows: "tuple[EligibilityRow, ...]"
    notes: "tuple[str, ...]" = ()
    #: The quarantine sentences (D36): one per pool element this report's
    #: caller could not read. Structured so a count of the unread is a field
    #: rather than something to re-derive from prose notes.
    quarantined: "tuple[str, ...]" = ()

    def as_dict(self) -> dict:
        return {
            "task_class": self.task_class,
            "purpose": self.purpose,
            "require_distinct_vendor": self.require_distinct_vendor,
            "subject": (
                None if self.subject is None else {
                    "producer": self.subject.producer, "vendor": self.subject.vendor,
                    "gateway": self.subject.gateway, "surface": self.subject.surface,
                }
            ),
            "rows": [
                {
                    "identity": list(row.identity),
                    "task_class": row.task_class,
                    "grade": row.grade,
                    "observations": row.observations,
                    "availability": row.availability,
                    "vendor": row.vendor,
                    "gateway": row.gateway,
                    "provider_id": row.provider_id,
                    "billing_pool_id": row.billing_pool_id,
                    "routability": row.routability,
                    "pool": (
                        None if row.pool is None else {
                            "pool_id": row.pool.pool_id, "remaining": row.pool.remaining,
                            "unit": row.pool.unit, "observed_at": row.pool.observed_at,
                            "age_seconds": row.pool.age_seconds, "freshness": row.pool.freshness,
                        }
                    ),
                    "independence": list(row.independence),
                    "disposition": row.disposition,
                    "eligible": row.eligible,
                    "availability_supposed": row.availability_supposed,
                    "reasons": list(row.reasons),
                }
                for row in self.rows
            ],
            "notes": list(self.notes),
            "quarantined": list(self.quarantined),
        }

    def render(self) -> str:
        # EVERY FIELD A ROW ECHOES crosses `_bounded` on the way to a human
        # (O12, criterion 6): the four identity dimensions, the vendor, the
        # gateway, the pool's unit, the task class — all of it text the
        # observation log, a manifest or a capacity document supplied and none
        # of it text this module produced. `capacity.Pool` does not validate
        # `unit`, so a unit carrying a newline and a live escape once rendered
        # as a second line this report never wrote. JSON mode needs none of
        # this: it escapes by construction and is unchanged.
        lines = [
            f"eligibility report for {_bounded(self.task_class)}, purpose {self.purpose}"
        ]
        for row in self.rows:
            # The header echoes FIVE fields on one line (four identity
            # dimensions and the class), so the class — the field a row shares
            # with every other row and the one a hostile spelling put last — is
            # bounded tighter than the dimensions to keep the whole line bounded.
            lines.append(
                f"  {'/'.join(_bounded(value) for value in row.identity[:4])} "
                f"@ {_bounded(row.task_class, 40)}"
            )
            lines.append(f"    grade: {row.grade} ({row.observations} observation(s))")
            lines.append(f"    vendor={_bounded(row.vendor)} gateway={_bounded(row.gateway)}")
            lines.append(
                f"    billing: {row.routability}"
                + (f" — {row.reasons[0]}" if row.reasons else "")
            )
            if row.pool is None:
                lines.append("    pool: none observed")
            else:
                lines.append(
                    f"    pool {_bounded(row.pool.pool_id)}: {row.pool.remaining} "
                    f"{_bounded(row.pool.unit)} "
                    f"({row.pool.freshness}, age {row.pool.age_seconds})"
                )
            if row.independence:
                lines.append("    independence: " + "; ".join(row.independence))
            for reason in row.reasons:
                lines.append(f"    reason: {reason}")
            verdict = (
                "ELIGIBLE (availability supposed)"
                if row.eligible and row.availability_supposed
                else "ELIGIBLE" if row.eligible else "NOT ELIGIBLE"
            )
            lines.append(f"    {verdict}")
        lines.extend(f"  note: {note}" for note in self.notes)
        return "\n".join(lines)


def _refuse_non_object_observation_lines(source: "str") -> None:
    """Refuse an observation line that is not an object, in this module's own
    words, before `qualification` reads the log.

    A JSON line that parses to a list or a scalar reaches
    `identity_from_observation` and dies on `row.get(...)` — and the
    interpreter's own words (`'list' object has no attribute 'get'`) reach the
    caller where a refusal sentence should be. The log is read here first so
    the refusal names the line and says what it is; everything else about the
    log stays `qualification`'s to refuse, in the sentences it already has.
    """
    import json as _json
    from pathlib import Path as _Path

    try:
        lines = _Path(source).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        # An unreadable log gets `qualification`'s own refusal, which is a
        # sentence; this pre-read exists only for what it would misreport.
        return
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = _json.loads(line)
        except ValueError:
            # An unparseable line is `qualification`'s to refuse, in the
            # sentence it already has.
            continue
        if not isinstance(value, dict):
            raise RoutingError(
                f"observation line {number} is a {type(value).__name__}, not an object"
            )


def eligibility_report(
    observations_path: "str",
    *,
    task_class: str,
    purpose: str = ROUTINE,
    require_distinct_vendor: bool = False,
    subject: "Derivation | None" = None,
    manifests: "Iterable[provider_manifest.ProviderManifest]" = (),
    capacity_pools: "Iterable[capacity.Pool]" = (),
    authorised_pools: "Iterable[str]" = (),
    environment: "Mapping[str, str] | None" = None,
    now: "float | None" = None,
    #: Pool id -> the sentence that quarantined it (D36). A pool whose capacity
    #: element the caller could not read is capacity UNKNOWN for the row whose
    #: manifest names it — neither an absent pool nor a reading — and the row
    #: carries the sentence rather than a bare id, so the coordinator reads WHY.
    quarantined_pools: "Mapping[str, str] | None" = None,
) -> EligibilityReport:
    """Every configuration this task class has evidence for, joined to what it
    would bill and how fresh its capacity is. **Lists and explains; dispatches
    nothing, ranks nothing by newness, and picks nothing** — the coordinator
    chooses among the rows this reports as eligible (S0-C5, O3).
    """
    if purpose not in PURPOSES:
        raise RoutingError(
            f"purpose {purpose!r} is not one of {', '.join(PURPOSES)}; a report labelled with a "
            "purpose nobody defined would be a report nobody could read"
        )
    _refuse_non_object_observation_lines(observations_path)
    manifests = tuple(manifests)
    pools = tuple(capacity_pools)
    quarantined = dict(quarantined_pools) if quarantined_pools else {}
    graded = qualification.qualifications_from_observations(observations_path)

    rows: list[EligibilityRow] = []
    for key in sorted(graded):
        if key[-1] != task_class:
            continue
        grade = graded[key]
        named = dict(zip(qualification.KEYED_DIMENSIONS, key))
        identity_tuple = key[:-1]
        family, client, model_observed = named["family"], named["client"], named["model_observed"]

        row_reasons: list[str] = []
        ambiguous = False
        try:
            manifest, surface_index = _match_manifest(client, family, manifests)
        except RoutingError as ambiguity:
            manifest, surface_index = None, None
            ambiguous = True
            row_reasons.append(str(ambiguity))
        if manifest is not None and surface_index is not None and not any(
            surface.client == client for surface in manifest.surfaces
        ):
            row_reasons.append(
                f"the manifest was matched by vendor, not by client: its billing facts hold, but "
                f"the recorded endpoint {_bounded(manifest.surfaces[surface_index].client)} is "
                f"not this configuration's client {_bounded(client)}"
            )
            # The row says the configuration's own client is undeclared HERE;
            # where another manifest does declare it, naming that manifest is
            # the fact a coordinator needs to repair the route rather than
            # guess at one.
            declaring = sorted(
                other.provider_id for other in manifests
                if any(surface.client == client for surface in other.surfaces)
            )
            if declaring:
                row_reasons.append(
                    f"client {_bounded(client)} is declared by other manifests: "
                    + ", ".join(_bounded(provider_id) for provider_id in declaring)
                )
        if manifest is None:
            vendor, gateway, provider_id, billing_pool_id = family, UNKNOWN, UNKNOWN, UNKNOWN
            # An ambiguity has already said, in its own sentence, exactly what
            # is wrong; appending "no declared provider manifest covers this
            # configuration" would say something false — two of them do.
            route_reasons = () if ambiguous else (
                "no declared provider manifest covers this configuration",
            )
            if not ambiguous:
                # AND WHERE THE CLIENT IS DECLARED, SAY WHERE. A row whose
                # family matches no declared vendor used to stop at "no
                # declared provider manifest covers this configuration" even
                # while two manifests at OTHER vendors declared its client —
                # the exact fact a coordinator needs to repair the route,
                # because it says the client string is right and the family
                # join is what is missing.
                elsewhere = sorted(
                    other.provider_id for other in manifests
                    if any(surface.client == client for surface in other.surfaces)
                )
                if elsewhere:
                    row_reasons.append(
                        f"client {_bounded(client)} is declared by manifests at other vendors: "
                        + ", ".join(_bounded(provider_id) for provider_id in elsewhere)
                    )
            route = provider_manifest.Routability(NOT_ROUTABLE_UNKNOWN, route_reasons)
        else:
            gateway = manifest.gateway
            provider_id, billing_pool_id = manifest.provider_id, manifest.billing.billing_pool_id
            fp = provider_manifest.fingerprint(
                manifest, surface_index=surface_index, environment=environment,
            )
            route = provider_manifest.routability(fp, authorised_pools=authorised_pools)
            # THE OBSERVED FAMILY DECIDES THE VENDOR (D30: "family is read as
            # the model vendor"). The row's vendor used to be whatever the
            # manifest DECLARED, so a manifest naming another vendor silently
            # supplied the independence comparison a vendor nobody observed,
            # and a leg read as cross-vendor on a declaration alone. The family
            # is what was observed; where the manifest's canonical vendor
            # disagrees with it — or the family cannot be canonicalised at all
            # — the vendor reads UNKNOWN (which refuses the leg), the
            # disagreement is said in the row's own words, and the route is
            # NOT_ROUTABLE_UNKNOWN: a manifest that misdescribes the model it
            # serves does not establish a route, whatever its billing facts.
            observed_vendor = _canonical_vendor(family)
            if observed_vendor == UNKNOWN or observed_vendor != _canonical_vendor(manifest.vendor):
                vendor = UNKNOWN
                row_reasons.append(
                    f"the observed family {_bounded(family, 32)} and the declared manifest vendor "
                    f"{_bounded(manifest.vendor, 32)} disagree; independence cannot be established "
                    f"on a declaration"
                )
                route = provider_manifest.Routability(NOT_ROUTABLE_UNKNOWN, ())
            else:
                vendor = observed_vendor
        row_reasons.extend(route.reasons)

        pool_state = None
        # A DUPLICATE POOL ID IS AN AMBIGUOUS READING, never a list-order
        # choice (D36). Two capacity elements carrying one id — one fresh and
        # one stale, or one quarantined with a surviving duplicate — are two
        # answers to one question, and reading the first made the row's
        # capacity depend on the order the document happened to list them in.
        # The reading is refused: the row's pool is UNKNOWN with the count,
        # whether the duplicate survived as a readable element or as a
        # quarantine.
        carried = [
            candidate_pool for candidate_pool in pools
            if candidate_pool.pool_id == billing_pool_id
        ]
        ambiguous_pool = len(carried) > 1 or (
            bool(carried) and billing_pool_id in quarantined
        )
        if not ambiguous_pool and len(carried) == 1:
            pool_state = _pool_state(carried[0], now=now)
        # Four ways a row's capacity is UNKNOWN, in precedence order: the id is
        # carried by more than one element (an ambiguous reading is refused),
        # the pool's element was quarantined, no pool was observed at all, or
        # the pool exists below but cannot be aged.
        capacity_unknown = False
        if manifest is not None and ambiguous_pool:
            row_reasons.append(
                f"{len(carried) + (1 if billing_pool_id in quarantined else 0)} capacity pools "
                f"carry id {_bounded(billing_pool_id)}; an ambiguous reading is refused, never "
                f"resolved by list order"
            )
            capacity_unknown = True
        elif manifest is not None and billing_pool_id in quarantined:
            row_reasons.append(
                f"the capacity observation for pool {_bounded(billing_pool_id)} was quarantined: "
                f"{quarantined[billing_pool_id]}"
            )
            capacity_unknown = True
        elif manifest is not None and pool_state is None:
            row_reasons.append(f"no capacity observation for pool {_bounded(billing_pool_id)}")
            capacity_unknown = True

        independence: tuple[str, ...] = ()
        if subject is not None:
            # A HYPOTHETICAL fresh dispatch of this configuration — nothing has
            # actually run, so `fresh=True` is declared rather than observed,
            # and this note says so.
            reader = Derivation(
                producer=model_observed, fresh=True, vendor=vendor, gateway=gateway, provider=vendor,
            )
            independence = independence_problems(
                reader, subject, require_distinct_vendor=require_distinct_vendor,
            )

        identity = ConfigurationIdentity(
            surface=named["surface"], family=family, client=client, model_observed=model_observed,
            effort=named["effort"], isolation=named["isolation"], network=named["network"],
            authentication_class=named["authentication_class"],
            # Not a provenance marker (`UNOBSERVED_PROVENANCE`): this key only
            # exists in `graded` because its identity was already complete.
            identity_method="already_confirmed_complete_by_qualification",
        )
        candidate = Candidate(
            identity=identity, task_class=task_class, grade=grade, availability=UNKNOWN,
        )
        # A report never dispatches, so it can never hold availability evidence.
        # For ROUTINE and PROBE it asks the frozen predicate the only question it
        # can answer here — "if a dispatch started, what would still refuse?" —
        # by supposing availability; the row says so, and an observed refusal at
        # dispatch time ends it. CRITICAL is asked as it stands: a mandatory leg
        # needs availability ESTABLISHED, and a report cannot establish it.
        supposed = candidate if purpose == CRITICAL else replace(candidate, availability=AVAILABLE)
        verdict = eligibility(supposed, purpose=purpose, routability=route.disposition)
        disposition = disposition_with_routability(route.disposition, UNKNOWN, grade.grade)

        reasons = list(verdict.reasons) + row_reasons
        if purpose != CRITICAL:
            reasons.append(
                "availability supposed for this verdict: a dispatch establishes it, and an "
                "observed refusal withdraws the verdict"
            )
        reasons.extend(f"not independent — {problem}" for problem in independence)
        eligible = verdict.allowed and not independence
        if pool_state is not None:
            if pool_state.remaining != UNKNOWN and pool_state.remaining <= 0:
                eligible = False
                reasons.append(
                    "the pool is exhausted (0 remaining): REFUSE_UNTIL_RESET or a human PARK "
                    "decision, never a metered alternative"
                )
            if pool_state.freshness == "STALE":
                eligible = False
                reasons.append("capacity reading is STALE")
            elif pool_state.freshness == UNKNOWN:
                capacity_unknown = True
                if pool_state.age_seconds is not None and pool_state.age_seconds < 0:
                    reasons.append(
                        f"observed in the future by {int(-pool_state.age_seconds)} s; the reading "
                        f"cannot be aged"
                    )
        # The caution a coordinator gets for capacity this report could not
        # establish — quarantined, absent, or unageable. NEVER on a CRITICAL
        # row: nothing below sets `eligible` for CRITICAL, because the verdict
        # above has already refused it on availability (a report dispatches
        # nothing, so it can never establish what CRITICAL requires), and
        # "dispatch serially" after a refusal would be advice to act on one.
        if capacity_unknown and purpose != CRITICAL:
            reasons.append("capacity UNKNOWN: dispatch serially")

        rows.append(EligibilityRow(
            identity=identity_tuple, task_class=task_class, grade=grade.grade,
            observations=grade.observations, availability=UNKNOWN, vendor=vendor, gateway=gateway,
            provider_id=provider_id, billing_pool_id=billing_pool_id, routability=route.disposition,
            pool=pool_state, independence=independence, disposition=disposition, eligible=eligible,
            reasons=tuple(reasons), availability_supposed=purpose != CRITICAL,
        ))

    notes = [
        "this report lists and explains; it dispatches nothing and picks nothing — the "
        "coordinator chooses among the eligible",
        "availability is UNKNOWN here: this command reads records and dispatches nothing, so a "
        "CRITICAL row is never eligible from a report alone",
    ]
    if subject is not None:
        notes.append(
            "independence is checked against a HYPOTHETICAL fresh dispatch of each configuration, "
            "not an actual one"
        )
    return EligibilityReport(
        task_class=task_class, purpose=purpose, require_distinct_vendor=require_distinct_vendor,
        subject=subject, rows=tuple(rows), notes=tuple(notes),
    )


#: The only keys this capacity reader implements. An element carrying more is
#: QUARANTINED, never silently trimmed (D36: nothing is silently dropped): a
#: project's own extension is a declaration to report, and the reader that
#: filtered it out reported a pool while having read less than the document
#: said. `provider_manifest` refuses an unknown key the same way, for the same
#: reason.
_POOL_KEYS = frozenset({
    "pool_id", "kind", "window", "remaining", "unit", "resets_at", "observed_at", "active_workers",
})


def _refuse_repeated_capacity_keys(pairs: list) -> dict:
    """A repeated key in a capacity document is refused, not resolved
    last-wins — the same rule `provider_manifest.load` applies to a manifest
    through the same means, an `object_pairs_hook` that raises, for the same
    reason: a document that states `remaining` twice parses as the later value
    while a person reading the file sees the earlier one, and the capacity a
    coordinator dispatches against must be the capacity the document's author
    believed they wrote."""
    seen: set = set()
    for key, _value in pairs:
        if key in seen:
            raise ValueError(
                f"the capacity document repeats key {_bounded(key, 40)}; a document with two "
                f"answers to one question is refused"
            )
        seen.add(key)
    return dict(pairs)


def _read_capacity_pool_entry(entry: object) -> "tuple[object, str | None]":
    """One capacity document pool element as a `capacity.Pool`, or the note
    that quarantines it (D36).

    Every sentence says what the element lacked or was — a type, a missing id,
    an unknown key — never an interpreter's own words: `Pool(**entry)` raises
    `TypeError`, `AttributeError` and `IntegrityError` whose messages carry
    Python's vocabulary (`Pool.__init__() missing 1 required positional
    argument: 'pool_id'`, `'int' object has no attribute 'strip'`), and a
    quarantine is for a coordinator, not a debugger. The fields are checked
    here, one by one, BEFORE the constructor runs, so the translation names
    the field rather than paraphrasing whatever the constructor said about it;
    what still slips past is caught and said without echoing it.
    """
    if not isinstance(entry, dict):
        return None, f"a pool element is a {type(entry).__name__}, not a mapping"
    raw_id = entry.get("pool_id")
    named = f"pool {_bounded(raw_id)}" if isinstance(raw_id, str) and raw_id.strip() else None
    prefix = f"{named} could not be read: " if named else ""
    # The prefix names the pool at the full echo bound; a sentence that named
    # it a second time at the same bound rendered a quarter-thousand-character
    # note for one ten-thousand-character id, so the in-sentence echo is
    # shorter. The id itself is never echoed raw.
    short = f"pool {_bounded(raw_id, 24)}"
    unknown = sorted(set(entry) - _POOL_KEYS)
    if unknown:
        return None, (
            prefix + "a pool element declares key(s) "
            + ", ".join(_bounded(key, 40) for key in unknown)
            + ", which this capacity reader does not implement; it is quarantined, never "
              "silently trimmed"
        )
    if not isinstance(raw_id, str) or not raw_id.strip():
        if raw_id is not None and not isinstance(raw_id, str):
            return None, (
                f"field pool_id of a pool element is a {type(raw_id).__name__}, not a string"
            )
        return None, "a pool element declares no pool_id"
    for key in ("kind", "window", "unit", "resets_at", "observed_at"):
        value = entry.get(key)
        if value is not None and not isinstance(value, str):
            return None, (
                prefix + f"field {key} of {short} is a {type(value).__name__}, not a string"
            )
    remaining = entry.get("remaining")
    if remaining is not None and remaining != capacity.UNKNOWN and (
            not isinstance(remaining, (int, float)) or isinstance(remaining, bool)):
        return None, (
            prefix + f"field remaining of {short} is a {type(remaining).__name__}, "
            "not a number or UNKNOWN"
        )
    if isinstance(remaining, (int, float)) and not isinstance(remaining, bool) and remaining < 0:
        return None, prefix + f"field remaining of {short} is a negative number, not a quantity"
    workers = entry.get("active_workers")
    if workers is not None and (not isinstance(workers, int) or isinstance(workers, bool)):
        return None, (
            prefix + f"field active_workers of {short} is a {type(workers).__name__}, not a count"
        )
    for key, vocabulary in (("kind", capacity.PoolKind.ALL), ("window", capacity.WindowKind.ALL)):
        value = entry.get(key)
        if isinstance(value, str) and value not in vocabulary:
            return None, (
                prefix + f"field {key} of {short} is {_bounded(value, 40)}, not one of "
                + ", ".join(vocabulary)
            )
    try:
        return capacity.Pool(**entry), None
    except (TypeError, AttributeError, IntegrityError):
        # Translated, never echoed: whatever the constructor said, a value it
        # rejected must not ride out of this reader inside its own message.
        return None, (
            prefix + "a field of this element is not a value the capacity reader accepts"
        )


def _eligibility_cli(args) -> int:
    """`routing.py --eligibility ...`. A report, never a verdict: exit 0
    whenever it renders, 2 only on a refusal (an unreadable log or manifest).
    """
    import json as _json
    import os
    import sys
    from dataclasses import replace as _replace
    from pathlib import Path as _Path

    observations_path = args.eligibility_observations or args.observations
    if not args.task_class:
        print("--eligibility requires --task-class", file=sys.stderr)
        return 2

    subject = None
    if args.subject_producer is not None:
        if args.subject_vendor and _canonical_vendor(args.subject_vendor) == UNKNOWN:
            # Refused OUTRIGHT, before any report is read (D30, fail-closed): a
            # vendor the caller cannot spell is not a vendor the comparison can
            # canonicalise, and letting one through would either found a second
            # vendor nothing validates or pass a misspelling as a real one.
            print(
                f"--subject-vendor {_bounded(args.subject_vendor)} is not a vendor slug (lowercase "
                f"letters, digits and single hyphens); a vendor this report does not know is "
                f"omitted, never misspelt", file=sys.stderr)
            return 2
        subject = Derivation(
            producer=args.subject_producer,
            vendor=_canonical_vendor(args.subject_vendor) if args.subject_vendor else UNKNOWN,
        )
    elif args.require_distinct_vendor or args.subject_vendor:
        print("--require-distinct-vendor and --subject-vendor describe the work's producer; "
              "without --subject-producer there is no producer to be independent of", file=sys.stderr)
        return 2

    manifests = []
    try:
        for path in args.manifests:
            manifests.append(provider_manifest.load(path))
    except Exception as exc:
        print(f"a provider manifest could not be read: {exc}", file=sys.stderr)
        return 2

    capacity_pools = []
    capacity_notes = []
    quarantine_sentences = []
    quarantined_pools = {}
    if args.capacity:
        try:
            payload = _json.loads(
                _Path(args.capacity).read_text(encoding="utf-8"),
                object_pairs_hook=_refuse_repeated_capacity_keys,
            )
        except Exception as exc:
            print(f"the capacity document could not be read: {exc}", file=sys.stderr)
            return 2
        pool_entries = payload.get("pools", []) if isinstance(payload, dict) else None
        if not isinstance(payload, dict):
            capacity_notes.append("the capacity document is not an object; no pool was read")
            pool_entries = []
        elif not isinstance(pool_entries, list):
            capacity_notes.append("the capacity document's `pools` is not a list; no pool was read")
            pool_entries = []
        # PER-ELEMENT QUARANTINE (D36): one unreadable pool is a note, not a
        # refusal of the whole report. A pool id this loop COULD read becomes a
        # join key the report matches rows against, so a row whose manifest
        # names that pool reads its capacity as quarantined — with this note's
        # sentence — rather than as an absent pool.
        for entry in pool_entries:
            pool, refusal = _read_capacity_pool_entry(entry)
            if refusal is None:
                capacity_pools.append(pool)
                continue
            capacity_notes.append(refusal)
            quarantine_sentences.append(refusal)
            if isinstance(entry, dict):
                pool_id = entry.get("pool_id")
                if isinstance(pool_id, str) and pool_id.strip():
                    quarantined_pools.setdefault(pool_id, refusal)
        # AN ID THE DOCUMENT CARRIES TWICE is named here as well as in the row
        # that joins it: the report refuses the reading, and the reader that
        # held the document says so at its own level, so the note exists even
        # for an id no row happened to join against.
        carried_counts: dict = {}
        for pool in capacity_pools:
            carried_counts[pool.pool_id] = carried_counts.get(pool.pool_id, 0) + 1
        for pool_id in sorted(set(carried_counts) | set(quarantined_pools)):
            total = carried_counts.get(pool_id, 0) + (1 if pool_id in quarantined_pools else 0)
            if total > 1:
                capacity_notes.append(
                    f"capacity pool id {_bounded(pool_id)} is carried by {total} elements; an "
                    f"ambiguous reading is refused, never resolved by list order"
                )

    # NAMES ONLY, never a value — the same rule `provider_manifest`'s own flag
    # states, applied here because `eligibility_report` forwards `environment`
    # straight to `provider_manifest.fingerprint`.
    environment = {name: "" for name in os.environ} if args.environment_from_current_process else None

    try:
        report = eligibility_report(
            observations_path, task_class=args.task_class, purpose=args.purpose,
            require_distinct_vendor=args.require_distinct_vendor, subject=subject,
            manifests=manifests, capacity_pools=capacity_pools,
            authorised_pools=args.authorised_pools, environment=environment,
            quarantined_pools=quarantined_pools or None, now=args.now,
        )
    except Exception as exc:
        print(f"the eligibility report could not be rendered: {exc}", file=sys.stderr)
        return 2

    if capacity_notes:
        report = _replace(
            report,
            notes=report.notes + tuple(capacity_notes),
            quarantined=tuple(quarantine_sentences),
        )

    if args.json:
        print(_json.dumps(report.as_dict(), indent=2))
    else:
        print(report.render())
    return 0


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
    # --- the eligibility report (S0-C5). Inert unless --eligibility is given,
    # so the existing behaviour above is unchanged when it is absent. ---------
    parser.add_argument("--eligibility", action="store_true",
                         help="render the eligibility report instead of the routing state above")
    parser.add_argument("--observations", dest="eligibility_observations", default=None,
                         help="observation log for --eligibility (the positional argument is used "
                              "otherwise)")
    parser.add_argument("--purpose", default=ROUTINE, choices=list(PURPOSES))
    parser.add_argument("--require-distinct-vendor", action="store_true")
    parser.add_argument("--subject-producer", default=None, metavar="NAME")
    parser.add_argument("--subject-vendor", default=None, metavar="VENDOR")
    parser.add_argument("--manifest", dest="manifests", action="append", default=[], metavar="PATH",
                         help="a provider manifest to join against; repeatable")
    parser.add_argument("--capacity", default=None, metavar="CAPACITY.json")
    parser.add_argument("--authorised-pool", dest="authorised_pools", action="append", default=[],
                         metavar="ID", help="a billing_pool_id authorised for this dispatch; repeatable")
    parser.add_argument(
        "--environment-from-current-process", action="store_true",
        help="check this process's environment variable NAMES; a value is never read or printed",
    )
    parser.add_argument(
        "--now", default=None, type=float, metavar="EPOCH_SECONDS",
        help="the instant the eligibility report ages capacity readings against; pin it and two "
             "runs over one capacity document are byte-identical",
    )
    args = parser.parse_args(argv)

    if args.eligibility:
        return _eligibility_cli(args)

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
