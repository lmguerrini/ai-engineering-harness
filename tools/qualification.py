"""What a *configuration* has been shown to do, as opposed to what its family has.

`backend_contract.grades_from_observations` derives a grade per
`(family, task_class)`. That was the right shape while a family named one thing
anybody dispatched. It stopped being the right shape the moment a family gained
a model nobody had run, because the derivation answers for the family and the
coordinator asks about the model. Executed against the shipped log and the
shipped module, a model with **zero** observations returns

    qualified_for("blind_closure_audit_cross_vendor") -> True

on seven observations, none of which recorded any observed model at all. That is
not a bug in `backend_contract`; it is the promise
`policy/routing-policy.md` has been making — *evidence is never pooled across
distinct configuration strings* — being made by prose while the code pooled.

This module makes the promise computable. Two things do the work:

*   **A nine-dimension qualification key.** Eight describe the configuration —
    surface, family, client, observed model, effort, isolation, network,
    authentication class — and the ninth is the task class. Each is in the key
    for a reason stated in `docs/RP2.4-DESIGN-C40-qualification-identity.md`,
    and the set is CLOSED: widening it is an edit somebody has to make and
    defend, not a parameter.
*   **Completeness.** An identity with `UNKNOWN` in any keyed dimension — or
    whose provenance says the identity was not observed — can hold observations,
    can be reported, and can **never** answer a qualification question about a
    concrete configuration. No historical observation records an observed model,
    an authentication class or a surface, so all of them become prior evidence
    and none becomes a track record. Nothing is rewritten and nothing is
    invented; the uncertainty stays in the data.

Three things this module deliberately does not do. It does not decide that a
model may be used — that is `routing`, and above it a coordinator. It does not
answer whether a configuration can *start*: that is availability, a separate
axis, because the shipped log contains two dispatches identical in all nine
dimensions where one never started and the other validated. And it never merges
evidence between identities: a declared alias produces **prior** evidence and
never a grade, because a rule that transfers a grade on the strength of a reason
string is a rule for laundering one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from backend_contract import (
    UNKNOWN,
    BackendContractError,
    TaskClassGrade,
    grades_from_observations,
    normalised_identity_value,
    parse_configuration,
)

__all__ = [
    "UNKNOWN",
    "CONFIGURATION_DIMENSIONS",
    "KEYED_DIMENSIONS",
    "NON_IDENTITY_FIELDS",
    "UNOBSERVED_PROVENANCE",
    "ConfigurationIdentity",
    "IDENTITY_FIELDS",
    "QualificationError",
    "Prior",
    "Equivalence",
    "Invalidation",
    "identity_from_configuration",
    "identity_from_observation",
    "qualification_key",
    "qualifications_from_observations",
    "priors_from_observations",
    "prior_for",
    "grade_for",
    "equivalence_problems",
    "prior_via_equivalence",
    "invalidation_problems",
]


class QualificationError(Exception):
    """A qualification claim its evidence does not support."""


#: The eight dimensions that describe the configuration itself. ORDER IS PART OF
#: THE CONTRACT: it is the order the key is built in and the order a report
#: prints, so a reader comparing two identities is comparing the same columns.
CONFIGURATION_DIMENSIONS = (
    "surface",
    "family",
    "client",
    "model_observed",
    "effort",
    "isolation",
    "network",
    "authentication_class",
)

#: The whole key. The task class is the ninth because a grade at one class is
#: `unprobed` at every other (D8) — it is not a property of the configuration,
#: and holding it outside the key would let one class answer for another.
KEYED_DIMENSIONS = CONFIGURATION_DIMENSIONS + ("task_class",)

#: What an observation's structured `identity:` mapping may state. It exists
#: because the packed configuration string is space-separated `key=value` and
#: therefore cannot carry an identifier containing a space — a real shape: this
#: release's own discovery reader accepts `MODEL WITH SPACES` verbatim, and the
#: string would truncate it.
IDENTITY_FIELDS = CONFIGURATION_DIMENSIONS + ("identity_method", "build", "model_requested")

#: Recorded on the observation, reported beside the grade, and deliberately NOT
#: in the key. `build` because no A/B pair in this evidence base shows a client
#: version changing an outcome, and keying on it would reset every qualification
#: at every patch release; `pool_id` because a capacity window says nothing about
#: capability. Both readings of the design were asked for a falsifying build pair
#: and neither produced one. The claim is *no evidence in this base*, not
#: *version irrelevance*, and `Invalidation` is what answers when it appears.
NON_IDENTITY_FIELDS = ("build", "pool_id")

#: Provenance values that say the identity was NOT observed. An adapter that
#: cannot read back what ran records one of these, and an adapter that copies the
#: requested slug into the observed field and labels it honestly records one too
#: — which is the shape an independent reader found reaching a qualification
#: through a check that only looked for an *absent* observed model.
#:
#: A DENYLIST RATHER THAN AN ALLOWLIST, on purpose. An allowlist of admissible
#: methods is a vocabulary of execution surfaces, and a vocabulary of surfaces
#: ages exactly the way the model vocabulary this release replaces aged: the next
#: surface would be inadmissible for having been invented late. What it cannot
#: catch is a fabricated method name, and that is an explicit trust boundary
#: rather than an oversight — an adapter that lies about how it learned an
#: identity is outside what any check here can reach.
UNOBSERVED_PROVENANCE = frozenset({
    "", "unknown", "requested", "requestedonly", "assumed", "inferred",
    "declared", "none", "notobserved", "unobserved", "na", "guessed",
    "presumed", "default", "fromthebrief", "asrequested",
})


def _provenance_key(text: object) -> str:
    """Compare provenance by its WORD, not by its punctuation.

    An exact-string denylist held `not_observed` and not `unobserved`, and an
    independent reader walked a complete identity carrying `unobserved` straight
    to `confirmed`. Two spellings of one claim are one claim: separators and case
    are removed before the comparison, so a marker cannot evade the rule by being
    hyphenated, spaced or capitalised differently.

    It still cannot catch a method name somebody invented, which is the trust
    boundary stated in the release's own limitations.
    """
    return "".join(character for character in str(text).lower() if character.isalnum())


@dataclass(frozen=True)
class ConfigurationIdentity:
    """One execution configuration, as far as something actually observed it.

    Every field defaults to `UNKNOWN` because that is the honest default: a
    dataclass whose fields must be supplied is a dataclass that gets supplied
    with guesses, and a guess recorded in an observation's shape is
    indistinguishable from an observation a week later.
    """

    surface: str = UNKNOWN
    family: str = UNKNOWN
    client: str = UNKNOWN
    #: What the execution surface CONFIRMED ran. Never the request. There is no
    #: property on this class that falls back to the requested model, because a
    #: convenience that quietly substitutes one for the other is how the two stop
    #: being distinguishable.
    model_observed: str = UNKNOWN
    effort: str = UNKNOWN
    isolation: str = UNKNOWN
    network: str = UNKNOWN
    authentication_class: str = UNKNOWN
    #: How `model_observed` and `effort` were established. Checked against
    #: `UNOBSERVED_PROVENANCE`, not against a list of known surfaces.
    identity_method: str = UNKNOWN
    #: Carried, reported, never keyed on.
    build: str = UNKNOWN
    pool_id: str = UNKNOWN
    #: What the dispatch asked for. Held so a report can show the request beside
    #: the observation — the two differing is a finding, not a detail.
    model_requested: str = UNKNOWN
    #: Every way the source configuration string could not be read
    #: unambiguously — a token carrying no `key=`, or a key carrying more than
    #: one value. Either means nothing parsed out of it may be trusted as an
    #: identity, because the format is space-separated `key=value` and both
    #: shapes make it lossy in silence.
    ambiguous_tokens: tuple = ()

    def dimensions(self) -> dict:
        """The eight configuration dimensions, in key order."""
        return {name: getattr(self, name) for name in CONFIGURATION_DIMENSIONS}

    def incompleteness(self) -> tuple[str, ...]:
        """Every reason this identity cannot answer for a concrete configuration.

        Reported as reasons rather than as a boolean, because "incomplete" with
        no cause is exactly the kind of unanswerable answer this pack refuses.
        """
        reasons = []
        for name, value in self.dimensions().items():
            # THROUGH THE ONE BOUNDARY, not by comparing against the sentinel.
            # Comparing `str(value) == UNKNOWN` recognised the sentinel and
            # nothing else, so a dimension given as the WORD "unknown" — which
            # `normalised_identity_value` reads as unestablished everywhere the
            # persisted path touches it — was counted as established here. That
            # is this pack's own recurrence class, two mechanisms answering one
            # question differently, inside the boundary built to end it.
            if normalised_identity_value(value) == UNKNOWN:
                reasons.append(f"{name} is not established")
        method = _provenance_key(self.identity_method)
        if method in UNOBSERVED_PROVENANCE:
            reasons.append(
                f"identity_method is {self.identity_method!r}, which states that the identity "
                f"was not observed; a requested model is not an observed model"
            )
        if self.ambiguous_tokens:
            reasons.append(
                "the configuration string could not be read unambiguously "
                f"({'; '.join(str(token) for token in self.ambiguous_tokens)}), so no value "
                "parsed from it identifies a configuration"
            )
        return tuple(reasons)

    @property
    def complete(self) -> bool:
        """Whether this identity may answer a qualification question at all."""
        return not self.incompleteness()

    def key(self, task_class: str) -> tuple:
        """The nine-dimension key. Raises rather than keying on an unknown class."""
        if not str(task_class).strip() or str(task_class) == UNKNOWN:
            raise QualificationError(
                "a qualification key needs a task class; a grade at one class is unprobed at "
                "every other, so a key without one would answer for all of them"
            )
        return tuple(self.dimensions().values()) + (task_class,)

    def render(self) -> str:
        """One line per dimension, with the excluded fields shown as excluded."""
        lines = [f"  {name:22} {getattr(self, name)}" for name in CONFIGURATION_DIMENSIONS]
        lines.append(f"  {'identity_method':22} {self.identity_method}")
        lines.extend(
            f"  {name + ' (not keyed)':22} {getattr(self, name)}" for name in NON_IDENTITY_FIELDS
        )
        if self.model_requested != self.model_observed:
            lines.append(
                f"  requested vs observed   {self.model_requested} -> {self.model_observed}"
            )
        return "\n".join(lines)


def identity_from_configuration(text: str) -> ConfigurationIdentity:
    """Read a configuration string into an identity.

    Reuses `backend_contract.parse_configuration` for the fields it already
    reads, so the two cannot drift about what `unknown` means, and adds the two
    this release introduces. The historical observations are primary evidence
    and are not rewritten to fit this shape: they are read into it, and every
    key they do not carry stays `UNKNOWN`.
    """
    parsed = parse_configuration(text)
    # A BARE TOKEN MEANS THE STRING IS AMBIGUOUS, and the ambiguity is not
    # harmless: the format is space-separated `key=value`, so an identifier
    # containing a space is truncated at the space and its evidence lands under
    # the PREFIX. An independent reader recorded two validated observations of
    # `MODEL WITH SPACES` and read `confirmed` back for `MODEL`, a configuration
    # nothing had dispatched — the exact transfer this release exists to prevent,
    # arriving through the parser rather than through the key.
    #
    # The string cannot be made lossless without changing what every existing
    # observation means, so an ambiguous one is REFUSED rather than parsed: the
    # identity is marked incomplete, which is the answer that loses nothing. A
    # row that needs an identifier with a space carries the structured
    # `identity:` mapping instead, which has no tokenisation to lose it to.
    ambiguous = [token for token in str(text).split() if "=" not in token]
    # A REPEATED KEY IS THE SAME AMBIGUITY WITH BETTER PUNCTUATION. The parser
    # builds a mapping, so the last occurrence silently wins and nothing says a
    # choice was made: appending `model_observed=` to a string that already has
    # one changes which configuration the observation is filed under, in
    # silence. That is the whitespace truncation again by another route, and it
    # is refused the same way — the identity goes incomplete, which is the answer
    # that loses nothing.
    #
    # Refusing only when the two values DIFFER was considered and rejected: a
    # writer that emits a key twice is defective either way, and a rule that
    # tolerates the harmless case is a rule that has to decide which case it is.
    seen: dict[str, int] = {}
    extra: dict[str, str] = {}
    for token in str(text).split():
        key, _, value = token.partition("=")
        if not _:
            continue
        key, value = key.strip(), value.strip()
        seen[key] = seen.get(key, 0) + 1
        if key in ("surface", "pool_id"):
            # THE SAME BOUNDARY AS EVERY OTHER DIMENSION. `surface` and
            # `pool_id` are the two keys this function reads for itself rather
            # than taking from `parse_configuration`, and they carried their own
            # inline copy of the rule — so the RP2.4.1 repair that gave the
            # packed string and the structured mapping one normaliser left a
            # THIRD path, and `surface=un_known` completed an identity and
            # graded `confirmed` through it. Found by an independent reading of
            # the repair itself, which is the defect the repair was for.
            extra[key] = normalised_identity_value(value)
    ambiguous.extend(
        f"{key}= appears {count} times" for key, count in sorted(seen.items()) if count > 1)
    return ConfigurationIdentity(
        surface=extra.get("surface", UNKNOWN),
        family=parsed.family,
        client=parsed.client,
        model_observed=parsed.model_observed,
        # The OBSERVED effort. `effort=` on a configuration string is what the
        # dispatch asked for, and this surface accepts an effort it will not run
        # at — so the requested rung is a request here for the same reason the
        # requested model is.
        effort=parsed.effort_observed,
        isolation=parsed.sandbox_state,
        network=parsed.network_state,
        authentication_class=parsed.authentication_class,
        identity_method=parsed.identity_method,
        build=parsed.client_version,
        pool_id=extra.get("pool_id", UNKNOWN),
        model_requested=parsed.model_requested,
        ambiguous_tokens=tuple(ambiguous),
    )


def identity_from_observation(row: dict) -> ConfigurationIdentity:
    """The identity behind one observation row, `pool_id` included.

    `pool_id` is a row-level field rather than a configuration token in the
    shipped log, so it is read from both places and the row wins.
    """
    identity = identity_from_configuration(row.get("configuration", ""))
    # A STRUCTURED IDENTITY WINS, and exists because the packed string cannot
    # carry an identifier containing a space. Every field is optional and each
    # one supplied replaces what the string said, so a row can name exactly the
    # part the string cannot hold.
    declared = row.get("identity")
    if isinstance(declared, dict):
        unknown = sorted(set(declared) - set(IDENTITY_FIELDS))
        if unknown:
            raise QualificationError(
                f"an observation records identity field(s) {', '.join(unknown)}, which nothing "
                f"reads. Known: {', '.join(IDENTITY_FIELDS)}")
        # `str(value)` MADE A JSON NULL INTO THE STRING "None", which is not the
        # `UNKNOWN` sentinel and therefore read as an established dimension: an
        # observation with `authentication_class: null` produced a COMPLETE
        # identity whose authentication class was `'None'`, and two of them
        # graded `confirmed` for a configuration whose authentication was never
        # established. Found by an independent reading of this release's
        # behaviour. A null is the absence of a value and is dropped here, which
        # leaves the dimension `UNKNOWN` and the identity incomplete — the answer
        # that loses nothing.
        # NORMALISED THROUGH THE SAME BOUNDARY AS THE STRING, and this is the
        # whole of the RP2.4.1 R3 repair. The mapping used to be carried
        # verbatim, so `effort: "unknown"` — the honest answer an adapter writes
        # when the surface did not report one — arrived as the literal string
        # `"unknown"`, which is not the `UNKNOWN` sentinel `incompleteness`
        # tests for. The identity came out COMPLETE and two such rows graded
        # `confirmed` for a configuration nothing had established. A second
        # normaliser here would have been a second answer to one question, so
        # there is one function and both paths call it.
        # PRESENT-BUT-EMPTY IS NOT ABSENT, and the difference decided a
        # qualification. A row carrying `identity: {"effort": null}` — the
        # natural JSON for *the surface did not report it* — had that key
        # DROPPED before the overlay, so the packed string's `effort=high`
        # survived, the identity came out COMPLETE and two such rows graded
        # `confirmed` for a configuration nothing had established. The string
        # "unknown" refused correctly on the same path, which is what made it
        # look covered. A whole-candidate reading found it.
        #
        # A key the writer bothered to include is a statement about that
        # dimension. If it says nothing, the dimension is UNKNOWN — never
        # whatever an earlier source happened to say.
        supplied = {name: normalised_identity_value(value)
                    for name, value in declared.items()}
        if supplied:
            # **AN AMBIGUOUS STRING IS REFUSED, WHATEVER THE MAPPING SAYS.**
            #
            # This cleared every ambiguity note whenever ANY field was supplied,
            # so a row whose string said `model_observed=MODEL WITH SPACES` —
            # which truncates to `MODEL` — became COMPLETE by adding an unrelated
            # `build`, and two such rows graded `confirmed` for a configuration
            # nothing had dispatched. That is the transfer this release exists to
            # prevent, reached through the parser.
            #
            # THE FIRST REPAIR WAS TOO CLEVER AND A SECOND READER BROKE IT. It
            # cleared a bare token when some supplied VALUE contained it as a
            # word, which the same defect walks straight through:
            # `identity: {"build": "WITH SPACES"}` accounts for the words without
            # saying anything about the model. Its all-dimensions shortcut let a
            # lossy `identity_method=not observed` through as `not`, because
            # provenance is not one of the keyed dimensions.
            #
            # So the rule is the one the comment above already states: the
            # mapping is carried **instead of** a lossy string, not alongside
            # one. A string that could not be read unambiguously means nothing
            # parsed out of it may be trusted, and a mapping cannot say which
            # part of it was lost. The identity stays incomplete, which is the
            # answer that loses nothing — the row is prior evidence and qualifies
            # nothing.
            identity = replace(identity, **supplied)
    pool = row.get("pool_id")
    if pool:
        identity = replace(identity, pool_id=str(pool))
    return identity


def qualification_key(identity: ConfigurationIdentity, task_class: str) -> tuple:
    """The nine-tuple a grade is filed under."""
    return identity.key(task_class)


def _read_rows(source: str | Path) -> list[dict]:
    rows = []
    for number, line in enumerate(
        Path(source).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError as exc:
            raise QualificationError(
                f"{source} line {number} is not readable as an observation: {exc}"
            ) from exc
    return rows


def _version_tuple(text: object) -> tuple:
    """Order two client versions, or refuse to.

    An empty tuple means *not orderable*, and an unorderable version is never
    treated as older — an invalidation that cannot prove an observation predates
    its boundary keeps the observation, because dropping evidence you cannot
    place is how adverse evidence disappears.
    """
    if not isinstance(text, str):
        return ()
    parts = []
    for piece in text.split("."):
        digits = ""
        for character in piece:
            if not character.isdigit():
                break
            digits += character
        if not digits or digits != piece:
            # AN INCOMPLETE PARSE IS NOT AN ORDERING. This returned the numeric
            # prefix it had accumulated, so `1.nightly` ordered as `(1,)` and an
            # invalidation dropped a contradiction recorded at a build nothing
            # could place. The docstring already said an unorderable version is
            # never treated as older; an independent reader found the code
            # saying otherwise one component in.
            return ()
        parts.append(int(digits))
    return tuple(parts)


@dataclass(frozen=True)
class Invalidation:
    """A governed statement that a client change ended a configuration's history.

    The failure it answers: `grades_from_observations` grades any contradiction
    `contradicted`, permanently, so a configuration broken by one client release
    and repaired by the next can never be requalified. An independent reader
    found it and it is real.

    Two properties keep this from being a way to delete adverse evidence.
    It drops **every** observation before the boundary, favourable and adverse
    alike, so it cannot be aimed at a contradiction. And the surviving grade is
    **capped at `provisional`**: an invalidated identity can recover enough to be
    probed again and can never be promoted to `confirmed` by having its history
    removed. The report names the invalidation, its reason, and how many
    observations it dropped.
    """

    surface: str
    family: str
    client: str
    model_observed: str
    #: Observations recorded at a client version ORDERED BEFORE this one are
    #: dropped. An observation whose build cannot be ordered is kept.
    before_build: str
    reason: str
    #: `None` means every task class of this configuration.
    task_class: str | None = None

    def covers(self, identity: ConfigurationIdentity, task_class: str) -> bool:
        if self.task_class is not None and self.task_class != task_class:
            return False
        return (
            identity.surface == self.surface
            and identity.family == self.family
            and identity.client == self.client
            and identity.model_observed == self.model_observed
        )

    def drops(self, identity: ConfigurationIdentity) -> bool:
        here, boundary = _version_tuple(identity.build), _version_tuple(self.before_build)
        if not here or not boundary:
            return False
        return here < boundary


def invalidation_problems(invalidation: Invalidation) -> tuple[str, ...]:
    """Everything that stops this declaration from being actionable."""
    found = []
    for name in ("surface", "family", "client", "model_observed", "before_build"):
        value = getattr(invalidation, name)
        if not str(value).strip() or str(value) == UNKNOWN:
            found.append(f"an invalidation must name {name}; it names {value!r}")
    if not _version_tuple(invalidation.before_build):
        found.append(
            f"the boundary {invalidation.before_build!r} cannot be ordered against a client "
            f"version, so no observation can be shown to predate it"
        )
    if not str(invalidation.reason).strip():
        found.append(
            "an invalidation with no reason is a deletion. State what changed in the client "
            "and why the earlier observations no longer describe this configuration"
        )
    return tuple(found)


@dataclass(frozen=True)
class Prior:
    """Family-level history, labelled as what it is.

    **Display-only.** It is printed beside an unprobed answer so a coordinator is
    not left with nothing, and it enters no ranking, satisfies no eligibility
    test and breaks no tie. Both independent readings of the design said the same
    thing from different directions: a prior that can rank is the family bucket
    back under a new name.
    """

    family: str
    task_class: str
    grade: TaskClassGrade
    #: Why this is prior rather than a track record — the identity's own
    #: incompleteness, or the alias it was reached through.
    because: str
    advisory: bool = True

    def sentence(self) -> str:
        return (
            f"PRIOR (advisory, not this configuration's track record): family {self.family!r} "
            f"grades {self.grade.grade!r} at {self.task_class!r} on "
            f"{self.grade.observations} observation(s) — {self.because}"
        )


def qualifications_from_observations(
    source: str | Path,
    *,
    invalidations: "tuple[Invalidation, ...]" = (),
) -> dict:
    """Per-configuration grades, from complete identities only.

    A derived view in the sense `policy/routing-table.md` already uses: computed
    from the whole log every time, never patched, never a rolling summary that
    could overwrite adverse evidence. The grading rule is
    `backend_contract`'s, unchanged and deliberately so — any contradiction
    grades `contradicted`; observations that only ever failed environmentally
    grade `environmental-unknown`; two or more validations grade `confirmed`; one
    grades `provisional`.

    Rows whose identity is INCOMPLETE are not silently skipped and not counted
    here. They are the input to `priors_from_observations`, which is the same log
    read as family history.
    """
    for invalidation in invalidations:
        problems = invalidation_problems(invalidation)
        if problems:
            raise QualificationError("; ".join(problems))

    counts: dict[tuple, dict] = {}
    identities: dict[tuple, ConfigurationIdentity] = {}
    builds: dict[tuple, set] = {}
    dropped: dict[tuple, int] = {}
    dropped_adverse: dict[tuple, int] = {}

    for row in _read_rows(source):
        identity = identity_from_observation(row)
        if not identity.complete:
            continue
        task_class = row.get("task_class") or UNKNOWN
        if not str(task_class).strip() or task_class == UNKNOWN:
            continue
        key = qualification_key(identity, task_class)

        applicable = [i for i in invalidations if i.covers(identity, task_class)]
        if any(i.drops(identity) for i in applicable):
            dropped[key] = dropped.get(key, 0) + 1
            if row.get("outcome") == "contradicted":
                # WHICH observations were dropped decides whether the cap
                # applies. Dropping only favourable rows cannot launder
                # anything, so capping there would punish an honest declaration
                # and make the mechanism unusable.
                dropped_adverse[key] = dropped_adverse.get(key, 0) + 1
            continue

        bucket = counts.setdefault(
            key, {"validated": 0, "contradicted": 0, "environmental": 0,
                  "field": 0, "synthetic": 0, "basis_unknown": 0})
        identities.setdefault(key, identity)
        builds.setdefault(key, set()).add(identity.build)

        basis = row.get("qualification_basis")
        if basis is None:
            basis = UNKNOWN
        elif basis not in ("field", "synthetic"):
            raise QualificationError(
                f"observation records qualification_basis {basis!r}. Known: field, synthetic. "
                "An unrecognised basis must not be counted as either"
            )
        bucket[{"field": "field", "synthetic": "synthetic",
                UNKNOWN: "basis_unknown"}[basis]] += 1

        outcome = row.get("outcome")
        if outcome == "validated":
            bucket["validated"] += 1
        elif outcome == "contradicted":
            bucket["contradicted"] += 1
        elif outcome == "environmental_failure":
            bucket["environmental"] += 1
        else:
            raise QualificationError(
                f"observation records outcome {outcome!r}, which this derivation does not "
                f"recognise. Known: validated, contradicted, environmental_failure"
            )

    graded: dict = {}
    for key, bucket in counts.items():
        total = bucket["validated"] + bucket["contradicted"] + bucket["environmental"]
        if bucket["contradicted"]:
            grade = "contradicted"
        elif bucket["validated"] >= 2:
            grade = "confirmed"
        elif bucket["validated"] == 1:
            grade = "provisional"
        else:
            grade = "environmental-unknown"
        # THE CAP, and only where it does something. An identity whose
        # ADVERSE history was invalidated may recover far enough to be probed
        # again and no further, so removing evidence against a configuration can
        # never manufacture a `confirmed`. The bound this leaves is real and
        # stated: such an identity cannot reach `confirmed` again from evidence
        # alone, and restoring it is a human decision — which is what declaring
        # the invalidation was in the first place.
        if dropped_adverse.get(key) and grade == "confirmed":
            grade = "provisional"
        graded[key] = TaskClassGrade(
            task_class=key[-1],
            grade=grade,
            observations=total,
            validated=bucket["validated"],
            contradicted=bucket["contradicted"],
            environmental=bucket["environmental"],
            field_observations=bucket["field"],
            synthetic_observations=bucket["synthetic"],
            basis_unknown=bucket["basis_unknown"],
            pools=tuple(sorted({identities[key].pool_id})),
        )
    for key in dropped:
        graded.setdefault(key, TaskClassGrade(task_class=key[-1]))
    return graded


def priors_from_observations(source: str | Path) -> dict:
    """Family history, read straight from `backend_contract`.

    Not a second derivation of the same thing: it IS the family-keyed derivation
    the routing table has always been regenerated from, called by the name that
    says what it may be used for.
    """
    return grades_from_observations(source)


def prior_for(
    identity: ConfigurationIdentity,
    task_class: str,
    priors: dict,
    *,
    because: str = "",
) -> "Prior | None":
    """The advisory prior standing behind an unprobed configuration, if any."""
    grade = priors.get((identity.family, task_class))
    if grade is None:
        return None
    reasons = identity.incompleteness()
    return Prior(
        family=identity.family,
        task_class=task_class,
        grade=grade,
        because=because
        or (
            "; ".join(reasons)
            if reasons
            else "this configuration has no observations of its own at this task class"
        ),
    )


def grade_for(
    identity: ConfigurationIdentity,
    task_class: str,
    graded: dict,
    priors: "dict | None" = None,
) -> "tuple[TaskClassGrade, Prior | None]":
    """This configuration's own grade, and the prior that is NOT its grade.

    An incomplete identity, or one nothing has dispatched, is `unprobed`. It is
    not inherited from the family, however strong the family's history: the
    family's history is returned beside it, labelled, so a reader has it without
    being able to mistake it for a track record.
    """
    if identity.complete:
        try:
            key = qualification_key(identity, task_class)
        except QualificationError:
            key = None
        if key is not None and key in graded:
            return graded[key], None
    prior = prior_for(identity, task_class, priors or {})
    return TaskClassGrade(task_class), prior


@dataclass(frozen=True)
class Equivalence:
    """A declared statement that two model identifiers name one configuration.

    **It moves no grade.** Both independent readings of revision 1 found the same
    laundering path through a rule that transferred qualification on the strength
    of a reason string, and the repair is to remove the transfer rather than to
    police it: an equivalence surfaces the other identity's evidence as `Prior`,
    labelled, and the target stays `unprobed` until it is dispatched.

    It may rename the model and nothing else. An equivalence that crossed a
    surface, a family or a client would be asserting that two different execution
    contracts are one, which is the claim least likely to be true and most costly
    if it is not.
    """

    surface: str
    family: str
    client: str
    from_model: str
    to_model: str
    reason: str


def equivalence_problems(equivalence: Equivalence) -> tuple[str, ...]:
    """Everything that stops this declaration from being usable, even as prior."""
    found = []
    for name in ("surface", "family", "client", "from_model", "to_model"):
        value = getattr(equivalence, name)
        if not str(value).strip() or str(value) == UNKNOWN:
            found.append(f"an equivalence must name {name}; it names {value!r}")
    if equivalence.from_model == equivalence.to_model:
        found.append("an equivalence between one model and itself declares nothing")
    if not str(equivalence.reason).strip():
        found.append(
            "an equivalence with no reason is not a declaration; it is an assertion. State how "
            "the two identifiers were established to name the same configuration"
        )
    return tuple(found)


def prior_via_equivalence(
    identity: ConfigurationIdentity,
    task_class: str,
    equivalences: "tuple[Equivalence, ...]",
    graded: dict,
) -> "Prior | None":
    """The aliased identity's evidence, as prior. Never as this one's grade.

    An equivalence is refused unless every dimension except the model already
    matches — the same surface, family and client — so a declaration cannot reach
    across execution contexts.
    """
    for equivalence in equivalences:
        if equivalence_problems(equivalence):
            continue
        if (identity.surface, identity.family, identity.client) != (
            equivalence.surface, equivalence.family, equivalence.client
        ):
            continue
        if identity.model_observed != equivalence.to_model:
            continue
        source = replace(identity, model_observed=equivalence.from_model)
        if not source.complete:
            continue
        try:
            key = qualification_key(source, task_class)
        except QualificationError:
            continue
        grade = graded.get(key)
        if grade is None:
            continue
        return Prior(
            family=identity.family,
            task_class=task_class,
            grade=grade,
            because=(
                f"reached through a DECLARED ALIAS {equivalence.from_model!r} -> "
                f"{equivalence.to_model!r} ({equivalence.reason}). The alias moves no grade: "
                f"{identity.model_observed!r} stays unprobed until it is dispatched"
            ),
        )
    return None


def _cli(argv: list[str]) -> int:
    """Print the per-configuration table beside the family priors."""
    import argparse
    import sys
    from pathlib import Path as _Path

    parser = argparse.ArgumentParser(
        prog="qualification.py",
        description="Derive per-configuration qualification from the observation log.",
    )
    parser.add_argument(
        "observations", nargs="?",
        default=str(_Path(__file__).resolve().parent.parent / "policy" / "observations.jsonl"),
        help="path to observations.jsonl",
    )
    args = parser.parse_args(argv)

    try:
        graded = qualifications_from_observations(args.observations)
        priors = priors_from_observations(args.observations)
        rows = _read_rows(args.observations)
    except Exception as exc:
        print(f"the observation log could not be read: {exc}", file=sys.stderr)
        return 2

    complete = sum(1 for row in rows if identity_from_observation(row).complete)
    print(f"derived from {args.observations} — a view, not a record; the log wins")
    print(f"  {len(rows)} observation(s), {complete} with a COMPLETE configuration identity")
    print()
    print("PER-CONFIGURATION QUALIFICATION — the only thing that answers about a configuration")
    if not graded:
        print("  (none: no observation carries a complete identity yet)")
    # EVERY KEYED DIMENSION, because printing four of nine makes two DIFFERENT
    # configurations look like one. Three rows for one model differing only in
    # effort rendered identically, which reads as one configuration qualified at
    # three task classes — the exact conflation this module exists to prevent,
    # reappearing in the view of it.
    for key, grade in sorted(graded.items()):
        named = dict(zip(KEYED_DIMENSIONS, key))
        print(f"  {named['model_observed']} @ {named['task_class']}")
        print(f"      {grade.grade:22} ({grade.validated} validated, "
              f"{grade.contradicted} contradicted, {grade.environmental} environmental)")
        print("      " + "  ".join(
            f"{name}={named[name]}" for name in CONFIGURATION_DIMENSIONS
            if name != "model_observed"))
    print()
    print("FAMILY PRIOR — advisory, display-only, never a track record and never a ranking input")
    for (family, task_class), grade in sorted(priors.items()):
        print(f"  {family:14} {task_class[:48]:50} {grade.grade:22} ({grade.observations} obs)")
    print()
    print("  a family prior is not this configuration's evidence; an incomplete identity is "
          "unprobed")
    return 0


if __name__ == "__main__":
    import sys

    # The module, not a second copy of it: a file run as a script is `__main__`,
    # and a sibling importing it by name gets separate class objects, so an
    # `isinstance` across that boundary is False for an object that is exactly
    # that class. Imported statically because a dynamic import would route around
    # the toolbelt's import-closure check.
    from errors import run_cli
    from qualification import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
