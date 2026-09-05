"""One deterministic readiness path, run before a governed capability opens.

Every prerequisite this answers about was already checkable before 2.2.0 — by
running four tools by hand and reading a prose checklist in a bootstrap
template. That is not a readiness path. It has no aggregate answer, nothing
compares its parts, and a step nobody ran is indistinguishable from a step that
passed.

**This module introduces no new source of truth.** Every component result is
delegated: the contract parser reads the contract, `pack_pin` and
`pack_migration` answer about the pin, `adapter_pin` about adapters,
`project_context` about the context, `migration_gate` about adoption. What is
added is composition, one truthful aggregate, and the requirement rule that
says which components a given project must satisfy.

Three things it deliberately does NOT do:

*   **It does not infer the capability boundary.** Only the caller knows whether
    the project is at one, so it is an input, and `UNKNOWN` when not supplied.
    A checker that guessed would be inventing the one fact that makes adoption
    safe.
*   **It does not treat a newer release as a failure.** A project pinned to an
    older *qualified* release is correctly pinned, and stays that way until it
    adopts at a boundary. Availability is reported as
    `READY_WITH_UPDATE_AVAILABLE` — a ready state — and never as a block.
*   **It authorises nothing.** It reports; integration, release and human
    decisions are elsewhere and stay there.

Stateless, read-only, and deterministic: it writes nothing, remembers nothing
between runs, and given the same filesystem returns the same report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import adapter_pin
import pack_migration
import project_context
from project_contract import ContractError, ProjectContract

__all__ = [
    "VERIFIED",
    "UNVERIFIABLE",
    "LEGACY",
    "NOT_PRESENT",
    "NOT_REQUIRED",
    "UNKNOWN",
    "UPDATE_AVAILABLE",
    "COMPONENT_STATES",
    "READY",
    "READY_WITH_UPDATE_AVAILABLE",
    "NOT_READY",
    "READINESS_STATES",
    "ADOPTABLE_STATE",
    "REQUIREMENT_KEYS",
    "ComponentResult",
    "ReadinessReport",
    "requirements_from",
    "open_capability",
]

#: Established: the component was checked and is what the project declared.
VERIFIED = "VERIFIED"
#: Declared and could not be established. **Never** the same as absent — the
#: distinction this whole pack exists to keep.
UNVERIFIABLE = "UNVERIFIABLE"
#: Declared in a form that predates the field set needed to identify it. A real
#: state of a real project, not a defect in the project.
LEGACY = "LEGACY"
#: Nobody declared one.
NOT_PRESENT = "NOT_PRESENT"
#: Not declared and not needed by this project's requirements. Distinct from
#: `NOT_PRESENT`, which says nothing about whether it was needed.
NOT_REQUIRED = "NOT_REQUIRED"
#: The question could not be answered. Fail-closed when the component is
#: required: an unanswered question is never its reassuring answer.
UNKNOWN = "UNKNOWN"
#: A newer qualified release exists. Belongs to the release-availability
#: component alone, and is **never** a failure: it is the difference between
#: `READY_WITH_UPDATE_AVAILABLE` and `READY`, both of which are ready.
UPDATE_AVAILABLE = "UPDATE_AVAILABLE"

COMPONENT_STATES = (
    VERIFIED, UNVERIFIABLE, LEGACY, NOT_PRESENT, NOT_REQUIRED, UNKNOWN, UPDATE_AVAILABLE,
)

#: Every required prerequisite established.
READY = "READY"
#: Every required prerequisite established, **and** a newer qualified release
#: exists. A ready state. Being deliberately pinned to an older qualified
#: release is the supported case, not a deficiency.
READY_WITH_UPDATE_AVAILABLE = "READY_WITH_UPDATE_AVAILABLE"
#: At least one required prerequisite failed or could not be established.
NOT_READY = "NOT_READY"

READINESS_STATES = (READY, READY_WITH_UPDATE_AVAILABLE, NOT_READY)

#: The only release state a project may run a capability against. `verify_pin`
#: answers "is this root what you pinned"; it does not answer "is what you
#: pinned adoptable", and a project pinned to an IN_PROGRESS release verifies
#: clean. That is correct of `verify_pin` and insufficient here.
ADOPTABLE_STATE = "QUALIFIED_AND_FROZEN"

#: What a project may declare it requires. Unknown keys are refused rather than
#: ignored: a requirement nobody reads is worse than no requirement, because
#: the project believes it is enforced.
REQUIREMENT_KEYS = frozenset({"project_context", "design", "routing"})


@dataclass(frozen=True)
class ComponentResult:
    """One prerequisite, its state, whether it was required, whether it stops.

    `required` and `blocking` are two different facts and the difference is
    load-bearing. **A requirement governs ABSENCE only** — the rule
    `adapter_pin` already established and this reuses rather than reinventing: a
    declared adapter that does not match blocks whether or not it was required,
    because something in this project dispatches through it. The same is true of
    a declared Project Context that cannot be verified. Declaring a semantic
    authority and being unable to establish it is not made safe by nobody having
    written `required: true`.
    """

    name: str
    state: str
    required: bool
    blocking: bool = True
    findings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def satisfied(self) -> bool:
        """`VERIFIED`, or not blocking. Nothing else counts.

        Not "has no findings": a component can be `UNKNOWN` with nothing to
        report, and an unanswered question about a prerequisite that stops the
        open is a stop.
        """
        return self.state == VERIFIED or not self.blocking


@dataclass
class ReadinessReport:
    state: str
    contract_path: str
    capability: str | None = None
    components: tuple[ComponentResult, ...] = ()
    notes: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.state in (READY, READY_WITH_UPDATE_AVAILABLE)

    def component(self, name: str) -> ComponentResult | None:
        for item in self.components:
            if item.name == name:
                return item
        return None

    @property
    def blocking(self) -> tuple[ComponentResult, ...]:
        return tuple(item for item in self.components if not item.satisfied)

    def render(self) -> str:
        lines = [f"capability open: {self.state}"]
        if self.capability:
            lines.append(f"  capability: {self.capability}")
        lines.append(f"  contract:   {self.contract_path}")
        for item in self.components:
            mark = "  " if item.satisfied else "!!"
            requirement = "required" if item.required else "optional"
            lines.append(f"{mark} {item.name:18} {item.state:14} ({requirement})")
            lines.extend(f"       {finding}" for finding in item.findings)
            lines.extend(f"       note: {note}" for note in item.notes)
        lines.extend(f"  note: {note}" for note in self.notes)
        return "\n".join(lines)

    def as_dict(self) -> dict:
        """The same report, for a caller that would rather parse than read."""
        return {
            "state": self.state,
            "contract": self.contract_path,
            "capability": self.capability,
            "components": [
                {
                    "name": item.name,
                    "state": item.state,
                    "required": item.required,
                    "satisfied": item.satisfied,
                    "findings": list(item.findings),
                    "notes": list(item.notes),
                }
                for item in self.components
            ],
            "notes": list(self.notes),
        }


def requirements_from(raw: object) -> dict:
    """The project's declared prerequisites, defaulted and validated.

    A project that declares nothing gets the defaults, which are the shape a
    simple fixture or utility needs: a Project Context is optional. A project
    whose semantic correctness depends on a durable context declares that it
    requires one, and then a missing or unverifiable context is a stop rather
    than a clean absence.

    The declaration is a **property of the project**, deliberately not a list of
    project names in Core. Core cannot know which products have durable semantic
    authority, and a Core that decided would be adjudicating product meaning.
    """
    requirements = {"project_context": False, "design": False, "routing": False}
    if raw is None:
        return requirements
    if not isinstance(raw, dict):
        raise ContractError("`requires:` must be a mapping")

    unknown = sorted(set(raw) - REQUIREMENT_KEYS)
    if unknown:
        raise ContractError(
            f"`requires:` declares {', '.join(unknown)}, which nothing checks. "
            f"Known requirements: {', '.join(sorted(REQUIREMENT_KEYS))}"
        )
    for key, value in raw.items():
        if not isinstance(value, bool):
            raise ContractError(f"`requires.{key}` must be true or false, not {value!r}")
        requirements[key] = value
    return requirements


def _contract_component(contract_path: Path) -> tuple[ComponentResult, ProjectContract | None]:
    try:
        contract = ProjectContract.load(contract_path)
    except ContractError as exc:
        return (
            ComponentResult(
                name="project_contract",
                state=UNVERIFIABLE,
                required=True,
                findings=(f"the project contract could not be read: {exc}",),
            ),
            None,
        )
    return ComponentResult(name="project_contract", state=VERIFIED, required=True), contract


def _pin_components(contract: ProjectContract) -> tuple[ComponentResult, ComponentResult]:
    """Two questions, kept apart on purpose.

    *Is the root what you pinned* and *is what you pinned adoptable* are
    different, and only the first had an answer. A project pinned to an
    `IN_PROGRESS` release satisfies the first completely.
    """
    pin = pack_migration.Pin.from_contract(contract)
    classification = pack_migration.classify_pin(pin)

    if classification == pack_migration.UNVERIFIABLE_LEGACY_PIN:
        missing = ", ".join(pack_migration.missing_pin_fields(pin))
        pin_result = ComponentResult(
            name="pack_pin",
            state=LEGACY,
            required=True,
            findings=(
                f"the pin lacks {missing}, so the release this project runs against cannot "
                "be identified. Being on a legacy pin is a real state of a real project and "
                "is not repaired by writing today's values into it",
            ),
            notes=(
                "the remedy is adoption of a qualified release at a capability boundary, "
                "through the migration gate",
            ),
        )
        return pin_result, ComponentResult(
            name="pack_release_state",
            state=UNKNOWN,
            required=True,
            findings=("the pinned release cannot be identified, so its state is unknown",),
        )

    problems = pack_migration.verify_pinned_root(pin)
    if problems:
        pin_result = ComponentResult(
            name="pack_pin", state=UNVERIFIABLE, required=True, findings=tuple(problems)
        )
    else:
        pin_result = ComponentResult(
            name="pack_pin",
            state=VERIFIED,
            required=True,
            notes=(f"{pin.version} at {pin.root_path}",),
        )

    return pin_result, _release_state_component(pin)


def _release_state_component(pin: "pack_migration.Pin") -> ComponentResult:
    """The state of the release ON DISK, not the state the project claims.

    This component exists because *is this root what you pinned* and *is what
    you pinned adoptable* are different questions. Reading `state_adopted` back
    out of the contract answers **neither** — it restates the project's claim
    and calls it verification. An independent audit reproduced it against a real
    consumer: one line said the pinned root's manifest reads `IN_PROGRESS`, and
    the next said the release-state prerequisite was `VERIFIED`.

    The state of a release that cannot be located is `UNKNOWN`. It is never
    `VERIFIED`.
    """
    declared = pin.state
    if declared is None:
        return ComponentResult(
            name="pack_release_state", state=UNKNOWN, required=True,
            findings=("the pin declares no release state",),
        )

    root = pin.root_path
    if not root or not Path(root).expanduser().is_absolute():
        return ComponentResult(
            name="pack_release_state", state=UNKNOWN, required=True,
            findings=("the pinned root cannot be located, so the release's state is unknown",),
        )
    manifest_path = pack_migration.canonical_root(root) / "PACK_MANIFEST.json"
    try:
        observed = json.loads(manifest_path.read_text(encoding="utf-8")).get("state")
    except (OSError, ValueError) as exc:
        return ComponentResult(
            name="pack_release_state", state=UNKNOWN, required=True,
            findings=(f"the pinned release's manifest could not be read: {exc}",),
        )

    if observed != declared:
        return ComponentResult(
            name="pack_release_state", state=UNVERIFIABLE, required=True,
            findings=(
                f"the project pinned a release in state {declared!r} and the root holds one in "
                f"state {observed!r}. Whichever is right, this project is not running against "
                "the release it believes it is",
            ),
        )
    if observed != ADOPTABLE_STATE:
        return ComponentResult(
            name="pack_release_state", state=UNVERIFIABLE, required=True,
            findings=(
                f"the pinned release is in state {observed!r}; a capability may open only "
                f"against {ADOPTABLE_STATE}. The pin may verify perfectly — the root IS what "
                "was pinned — and what was pinned is not adoptable",
            ),
        )
    return ComponentResult(name="pack_release_state", state=VERIFIED, required=True)


def _adapter_component(contract: ProjectContract, home: str | Path | None) -> ComponentResult:
    declarations = contract.adapters
    if declarations is None:
        # "Nobody said" is not "someone said none" — `adapter_pin`'s own
        # distinction, kept here rather than flattened. It does not block: a
        # project that dispatches through nothing needs no adapters, and
        # refusing every contract that predates the block would be punishing an
        # omission. It is `UNKNOWN` rather than `NOT_PRESENT`, because what the
        # project dispatches through has not been stated.
        return ComponentResult(
            name="adapters",
            state=UNKNOWN,
            required=False,
            blocking=False,
            notes=(
                "no `adapters:` block. A project that dispatches through an installed agent "
                "or skill and declares none has an executable surface nothing verifies, and "
                "this cannot tell that apart from a project that dispatches through none. "
                "Declare `adapters: []` to say the second one",
            ),
        )
    if not declarations:
        return ComponentResult(
            name="adapters",
            state=NOT_PRESENT,
            required=False,
            blocking=False,
            notes=("the project declares it dispatches through no adapter",),
        )
    report = adapter_pin.verify(declarations, home=home)
    findings = tuple(finding.sentence() if hasattr(finding, "sentence") else str(finding)
                     for finding in report.findings)
    required = any(getattr(declaration, "required", True) for declaration in declarations)
    # `clean` is the adapter verifier's own judgement about whether to BLOCK,
    # and it already applies the requirement-governs-absence rule per
    # declaration. Re-deriving that would be a second opinion about a question
    # that has an owner. But clean is not the same as verified: an adapter that
    # is absent BY PERMISSION is clean and was not checked, and reporting the
    # component `VERIFIED` while a finding below it says "declared and not
    # installed" collapses two of the states this module exists to keep apart.
    verified = len(getattr(report, "verified", ()) or ())
    if not report.clean:
        state = UNVERIFIABLE
    elif verified == len(declarations):
        state = VERIFIED
    else:
        state = UNKNOWN
    notes = tuple(report.notes)
    if state is UNKNOWN:
        notes += (
            f"{verified} of {len(declarations)} declared adapters verified; the rest are absent "
            "by permission, so what they would have done is unverified rather than confirmed",
        )
    return ComponentResult(
        name="adapters",
        state=state,
        required=required,
        blocking=not report.clean,
        findings=findings,
        notes=notes,
    )


def _context_component(contract: ProjectContract, required: bool) -> ComponentResult:
    declaration = contract.project_context
    if declaration is None:
        # The one case `required` decides. Absence is clean for a fixture or a
        # utility and a stop for a product whose correctness depends on durable
        # semantic authority — and the project says which it is, because Core
        # cannot know and a Core that decided would be adjudicating product
        # meaning.
        return ComponentResult(
            name="project_context",
            state=NOT_PRESENT if required else NOT_REQUIRED,
            required=required,
            blocking=required,
            findings=(
                (
                    "this project declares `requires.project_context: true` and declares no "
                    "context. A product whose correctness depends on durable semantic "
                    "authority cannot open a capability without one",
                )
                if required
                else ()
            ),
        )

    if required and getattr(declaration, "activated", True) is False:
        return ComponentResult(
            name="project_context",
            state=UNVERIFIABLE,
            required=True,
            blocking=True,
            findings=(
                "this project declares `requires.project_context: true` and the declared "
                "context is NOT ACTIVATED. A deactivated context is verified and not "
                "consulted, which is precisely what a project requiring one cannot proceed "
                "on. Its identity may be perfect; nothing will read it",
            ),
        )

    report = project_context.verify(declaration)
    state = {
        project_context.CURRENTLY_VERIFIED: VERIFIED,
        project_context.NOT_PRESENT: NOT_PRESENT,
        project_context.STALE: UNVERIFIABLE,
        project_context.UNVERIFIABLE: UNVERIFIABLE,
        project_context.DECLARED: UNKNOWN,
    }.get(report.state, UNKNOWN)
    notes = tuple(report.notes) + (f"context verifier reports {report.state}",)
    if state != VERIFIED and not required:
        notes += (
            "this project does not declare that it REQUIRES a context, and it declared one "
            "anyway. A requirement governs absence; a declared authority that cannot be "
            "established still stops the open",
        )
    return ComponentResult(
        name="project_context",
        state=state,
        required=required,
        blocking=True,
        findings=tuple(report.findings),
        notes=notes,
    )


def _capability_component(contract: ProjectContract, capability: str | None) -> ComponentResult:
    if capability is None:
        return ComponentResult(
            name="capability",
            state=NOT_REQUIRED,
            required=False,
            blocking=False,
            notes=("no capability named; the pack-level prerequisites were checked alone",),
        )
    declared = contract.raw.get("capabilities")
    if not isinstance(declared, list):
        return ComponentResult(
            name="capability",
            state=UNKNOWN,
            required=True,
            findings=("the contract declares no `capabilities:` list to check the name against",),
        )
    names = [item.get("id") for item in declared if isinstance(item, dict)]
    if capability in names:
        return ComponentResult(name="capability", state=VERIFIED, required=True)
    return ComponentResult(
        name="capability",
        state=UNVERIFIABLE,
        required=True,
        findings=(
            f"{capability!r} is not a declared capability of this project. Declared: "
            + (", ".join(str(name) for name in names) if names else "none"),
        ),
    )


def _design_component(contract: ProjectContract, capability: str | None,
                      change_class: str | None, required: bool,
                      record_path: str | Path | None,
                      mutation_begins_at: str) -> ComponentResult:
    """Whether a design was frozen before the implementation this opens.

    The whole point is the ORDER. `skills/core/repair.md` governs what happens
    once a defect exists; this governs what has to exist before there is
    anything to defect. It reports and never authorises: the aggregate answer
    is this report's, and the decision to open is the coordinator's.

    Risk-scaled by the caller's declared change class, because a rule that
    demands a design document for a typo is a rule that gets routed around.
    """
    import design_record

    declared = (change_class or "").strip().upper() or None
    if declared is not None and declared not in design_record.CHANGE_CLASSES:
        return ComponentResult(
            name="design",
            state=UNKNOWN,
            required=True,
            findings=(f"the change class {change_class!r} is not one of "
                      f"{', '.join(design_record.CHANGE_CLASSES)}. An unrecognised class is not "
                      f"a small one: this refuses rather than choosing the lenient reading",),
        )

    where = Path(record_path) if record_path else None
    # DISCOVERED, or NAMED. `DESIGN.md` is one of the commonest filenames there
    # is, and a project that has an architecture note beside its contract has
    # not thereby opted into this mechanism. A discovered record is read and
    # reported; only a record this project asked for can stop the open.
    discovered = False
    if where is None:
        beside = Path(contract.path).parent if getattr(contract, "path", None) else Path(".")
        for candidate in ([beside / f"DESIGN-{capability}.md"] if capability else []) + \
                [beside / "DESIGN.md"]:
            if candidate.is_file():
                where, discovered = candidate, True
                break

    # A DECLARED record that cannot be read blocks whether or not it was
    # required — D22, and the same rule adapters and Project Context already
    # follow. Something in this project points at it.
    if record_path and not Path(record_path).is_file():
        return ComponentResult(
            name="design",
            state=UNVERIFIABLE,
            required=True,
            findings=(f"a design record was named at {record_path} and there is no file there",),
        )

    must = required or (declared is not None and design_record.required_for(declared))
    if declared == design_record.TRIVIAL and not required:
        return ComponentResult(
            name="design", state=NOT_REQUIRED, required=False, blocking=False,
            notes=("the caller declared this change TRIVIAL — reversible, local, and promising "
                   "nothing new. That declaration is recorded here rather than checked: Core "
                   "cannot know which of a project's changes are material",))
    if where is None:
        if not must:
            return ComponentResult(
                name="design", state=NOT_REQUIRED, required=False, blocking=False,
                notes=("no design record, and none required: the project does not declare "
                       "`requires.design` and no change class was declared",))
        return ComponentResult(
            name="design", state=NOT_PRESENT, required=True,
            findings=(f"this change is declared {declared or 'required by the contract'} and no "
                      f"design record exists. Implementation is not authorised by this report: "
                      f"the alternatives, the failure modes and the oracles are what a material "
                      f"change states before it mutates anything",))

    record = design_record.read(where)
    problems = record.problems(mutation_begins_at=mutation_begins_at,
                               repository=Path(where).parent)
    chosen = record.selected.name if record.selected else ""
    # THE SUMMARY IS UNCONDITIONAL. It used to hang on the selected design
    # having a name, so the emptier the record the less the report said about
    # it — the rubber stamp rendered as one line.
    notes = [f"design record: {where}" + (" (found beside the contract, not declared)"
                                          if discovered else ""),
             f"selected: {chosen or UNKNOWN}",
             f"{len(record.candidates)} design(s) considered, {len(record.rejected)} rejected, "
             f"{len(record.failure_modes)} failure mode(s) stated, "
             f"{len(record.oracles)} oracle(s) frozen"]
    if problems:
        return ComponentResult(name="design", state=UNVERIFIABLE, required=bool(must),
                               blocking=bool(must) or not discovered,
                               findings=tuple(problems), notes=tuple(notes))
    return ComponentResult(name="design", state=VERIFIED, required=bool(must),
                           notes=tuple(notes))


def _routing_component(contract: ProjectContract, required: bool) -> ComponentResult:
    """Whether this project's routing evidence can answer about a configuration.

    It reads records and dispatches nothing. What it establishes is narrow and
    stated: the declared observation log parses, every row's identity is
    readable, and the two derivations are reported side by side so a reader sees
    how much of the evidence is a per-configuration track record and how much is
    family history. It never says a model may be used — that is the
    coordinator's, and `routing.py` only ranks and refuses.

    A project that declares no `routing:` block gets `NOT_REQUIRED`, which is the
    same non-blocking answer it got before this component existed.
    """
    declared = contract.raw.get("routing")
    if declared is None:
        return ComponentResult(
            name="routing",
            state=NOT_PRESENT if required else NOT_REQUIRED,
            required=required,
            blocking=required,
            findings=(
                (
                    "this project declares `requires.routing: true` and declares no `routing:` "
                    "block, so there is no observation log to answer about a configuration from. "
                    "A family's history is not a configuration's track record",
                )
                if required
                else ()
            ),
        )
    if not isinstance(declared, dict):
        return ComponentResult(
            name="routing", state=UNVERIFIABLE, required=True,
            findings=("`routing:` must be a mapping naming at least `observations:`",))

    where = declared.get("observations")
    if not where:
        return ComponentResult(
            name="routing", state=UNVERIFIABLE, required=True,
            findings=("`routing:` names no `observations:` log",))

    base = Path(contract.path).parent if getattr(contract, "path", None) else Path(".")
    log = Path(where)
    if not log.is_absolute():
        log = base / log
    # A DECLARED thing that cannot be read blocks whether or not it was required
    # — D22, the rule adapters, Project Context and the design record already
    # follow. Something in this project routes off it.
    if not log.is_file():
        return ComponentResult(
            name="routing", state=UNVERIFIABLE, required=True,
            findings=(f"the declared observation log {log} does not exist",))

    import qualification

    try:
        graded = qualification.qualifications_from_observations(log)
        priors = qualification.priors_from_observations(log)
        rows = qualification._read_rows(log)
    except Exception as exc:
        return ComponentResult(
            name="routing", state=UNVERIFIABLE, required=True,
            findings=(f"the declared observation log could not be derived from: {exc}",))

    complete = sum(1 for row in rows if qualification.identity_from_observation(row).complete)
    notes = [
        f"{len(rows)} observation(s); {complete} carry a complete configuration identity",
        f"{len(graded)} per-configuration qualification(s); {len(priors)} family prior(s), which "
        f"are advisory and rank nothing",
    ]
    if complete == 0 and rows:
        notes.append(
            "NO observation carries a complete configuration identity, so every answer this "
            "project can give about a configuration is `unprobed` with a family prior beside it. "
            "That is the honest state of this evidence, not a defect in it — the remedy is "
            "recording an observed identity at the next dispatch, in the adapter"
        )

    discovery = declared.get("discovery")
    if discovery:
        import model_discovery

        document = Path(discovery)
        if not document.is_absolute():
            document = base / document
        try:
            reading = model_discovery.read(document)
        except Exception as exc:
            return ComponentResult(
                name="routing", state=UNVERIFIABLE, required=True,
                findings=(f"the declared discovery document could not be read: {exc}",),
                notes=tuple(notes))
        notes.append(
            f"{len(reading.models)} identifier(s) DISCOVERED from {document}, produced by client "
            f"{reading.producer} — discovery is never availability")
        notes.extend(reading.skew(str(declared.get("dispatching_client", ""))))

    return ComponentResult(name="routing", state=VERIFIED, required=required, notes=tuple(notes))


def _update_component(
    contract: ProjectContract, release_index: str | Path | None
) -> ComponentResult:
    """Whether a newer qualified release exists. **Informational, never a block.**

    A project deliberately pinned to an older qualified immutable release is
    correctly pinned. "Not latest" is not a defect, and a readiness checker that
    treated it as one would break the multi-project model this pack is built on.
    """
    if release_index is None:
        return ComponentResult(
            name="release_update",
            state=UNKNOWN,
            required=False,
            blocking=False,
            notes=("no release index supplied, so availability of a newer release is unknown",),
        )
    try:
        entries = pack_migration.read_release_index(release_index)
    except Exception as exc:
        return ComponentResult(
            name="release_update",
            state=UNKNOWN,
            required=False,
            blocking=False,
            findings=(f"the release index could not be read: {exc}",),
            notes=("an unreadable index means availability is unknown; it never blocks an "
                   "open, because a project's own pin is what it runs against",),
        )

    pin = pack_migration.Pin.from_contract(contract)
    current = _sortable(pin.version)
    if not current:
        # An unparseable pin version sorts below everything, which would tell a
        # project it is behind a release it may not be behind at all. Reproduced
        # by an audit: a pin reading `wave-a` was told 3.0.0 was newer.
        return ComponentResult(
            name="release_update",
            state=UNKNOWN,
            required=False,
            blocking=False,
            notes=(
                f"the pinned version {pin.version!r} cannot be ordered against the index, so "
                "whether anything newer exists is unknown. Nothing is offered rather than "
                "something being invented",
            ),
        )

    # The index is UNTRUSTED INPUT — `pack_migration` says so of itself, and
    # then this offered entries on the index's word alone. An audit put an
    # `IN_PROGRESS` release and a root that does not exist into an index that
    # declared both qualified, and both were announced as available qualified
    # releases. An entry is verified against the release it names before it is
    # offered.
    newer, unverified = [], []
    for entry in entries:
        if entry.state != ADOPTABLE_STATE or _sortable(entry.version) <= current:
            continue
        try:
            problems = pack_migration.verify_pinned_root(
                pack_migration.Pin(
                    version=entry.version, sha=entry.sha, digest=entry.digest,
                    state=entry.state, root_path=entry.root_path, retained_roots=(),
                )
            )
        except Exception as exc:  # an entry that cannot be checked is not offered
            problems = [str(exc)]
        (newer if not problems else unverified).append((entry, problems))

    if unverified and not newer:
        return ComponentResult(
            name="release_update",
            state=UNKNOWN,
            required=False,
            blocking=False,
            notes=tuple(
                f"the index lists {entry.version} at {entry.root_path} as qualified, and it does "
                f"not verify ({problems[0]}). Listed, not offered"
                for entry, problems in unverified
            ),
        )
    if not newer:
        return ComponentResult(
            name="release_update",
            state=NOT_PRESENT,
            required=False,
            blocking=False,
            notes=("no newer qualified release is listed",),
        )
    notes = []
    for entry, _problems in newer:
        advisory = (
            f" It carries a SECURITY ADVISORY: {entry.security_advisory}. That is a human "
            "decision about urgency and nothing here makes it faster."
            if entry.security_advisory
            else ""
        )
        notes.append(
            f"a newer qualified release is available and verifies: {entry.version} at "
            f"{entry.root_path}. This is information, not a finding — adoption happens at a "
            "capability boundary, through the migration gate, and staying on the current "
            "qualified release is a supported choice." + advisory
        )
    notes.extend(
        f"the index lists {entry.version} at {entry.root_path} as qualified, and it does not "
        f"verify ({problems[0]}). Listed, not offered"
        for entry, problems in unverified
    )
    return ComponentResult(
        name="release_update", state=UPDATE_AVAILABLE, required=False,
        blocking=False, notes=tuple(notes),
    )


def _sortable(version: object) -> tuple:
    """Compare versions without pretending unparseable ones are ordered.

    A version this cannot parse sorts below everything, so an unrecognisable
    pin never produces a fabricated "you are behind".
    """
    if not isinstance(version, str):
        return ()
    parts = []
    for piece in version.split("."):
        digits = ""
        for character in piece:
            if not character.isdigit():
                break
            digits += character
        if not digits:
            return tuple(parts)
        parts.append(int(digits))
    return tuple(parts)


def open_capability(
    contract_path: str | Path,
    *,
    capability: str | None = None,
    release_index: str | Path | None = None,
    proposed_release: object | None = None,
    at_capability_boundary: bool | None = None,
    home: str | Path | None = None,
    change_class: str | None = None,
    design: str | Path | None = None,
    mutation_begins_at: str = "",
) -> ReadinessReport:
    """Whether a governed capability may open against this project, and why not.

    `at_capability_boundary` is the caller's statement about the project, used
    only when `proposed_release` names a release to adopt. Adoption is refused
    when the caller cannot say — an active capability must not silently change
    the release it is running against, and "the caller did not say" is not
    "yes".
    """
    contract_path = Path(contract_path)
    contract_result, contract = _contract_component(contract_path)
    if contract is None:
        return ReadinessReport(
            state=NOT_READY,
            contract_path=str(contract_path),
            capability=capability,
            components=(contract_result,),
            notes=["nothing else was checked: without the contract there are no declarations "
                   "to check against, and assuming defaults would be inventing them"],
        )

    requirements = requirements_from(contract.raw.get("requires"))
    pin_result, state_result = _pin_components(contract)
    components = [
        contract_result,
        pin_result,
        state_result,
        _adapter_component(contract, home),
        _context_component(contract, requirements["project_context"]),
        _capability_component(contract, capability),
        _design_component(contract, capability, change_class, requirements["design"],
                          design, mutation_begins_at),
        _routing_component(contract, requirements["routing"]),
        _update_component(contract, release_index),
    ]

    notes: list[str] = []
    if proposed_release is not None:
        pin = pack_migration.Pin.from_contract(contract)
        if at_capability_boundary is None:
            components.append(
                ComponentResult(
                    name="migration",
                    state=UNKNOWN,
                    required=True,
                    findings=(
                        "a release was proposed for adoption and the caller did not say whether "
                        "the project is at a capability boundary. Only the caller knows, and "
                        "this refuses rather than assumes: an active capability silently "
                        "changing release is the failure this exists to prevent",
                    ),
                )
            )
        else:
            gate = pack_migration.migration_gate(
                pin, proposed_release, at_capability_boundary=at_capability_boundary
            )
            components.append(
                ComponentResult(
                    name="migration",
                    state=VERIFIED if gate.clean else UNVERIFIABLE,
                    required=True,
                    findings=tuple(gate.findings),
                    notes=tuple(gate.notes),
                )
            )

    frozen = tuple(components)
    blocking = [item for item in frozen if not item.satisfied]
    if blocking:
        state = NOT_READY
    else:
        update = next((item for item in frozen if item.name == "release_update"), None)
        state = (
            READY_WITH_UPDATE_AVAILABLE
            if update is not None and update.state == UPDATE_AVAILABLE
            else READY
        )

    return ReadinessReport(
        state=state,
        contract_path=str(contract_path),
        capability=capability,
        components=frozen,
        notes=notes,
    )


def _cli(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="capability_open.py",
        description="Verify a project's prerequisites before a governed capability opens.",
    )
    parser.add_argument("project", help="path to PROJECT.yaml, or the directory holding it")
    parser.add_argument("--capability", help="the capability id being opened")
    parser.add_argument("--release-index", help="path to a release index, to report availability")
    parser.add_argument("--home", help="override the home directory adapters resolve against")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument("--change-class", default=None,
                        help="TRIVIAL, ROUTINE or MATERIAL — what this capability is about to "
                             "change. Scales what a design record must state; the caller "
                             "declares it because only the caller knows")
    parser.add_argument("--design", default=None,
                        help="path to the frozen design record, if it is not beside the contract")
    parser.add_argument("--mutation-begins-at", default="",
                        help="the revision at which this capability first mutated anything, so "
                             "a design frozen after it can be refused")
    args = parser.parse_args(argv)

    report = open_capability(
        args.project,
        capability=args.capability,
        release_index=args.release_index,
        home=args.home,
        change_class=args.change_class,
        design=args.design,
        mutation_begins_at=args.mutation_begins_at,
    )
    print(json.dumps(report.as_dict(), indent=2) if args.json else report.render())
    return 0 if report.ready else 1


if __name__ == "__main__":
    import sys

    # Run the module, not a second copy of it. A file executed as a script is
    # `__main__`, and a sibling that imports it BY NAME gets a separate module
    # object with separate class objects — so an `isinstance` check across that
    # boundary is False for an object that is exactly that class. It crashed
    # `project_context.py --project` against a real consumer's contract, on a
    # shape the suite covers completely: tests import the module and never run
    # it as a script. Imported statically, by name, because a dynamic import
    # would route around the toolbelt's import-closure check.
    from errors import run_cli
    from capability_open import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
