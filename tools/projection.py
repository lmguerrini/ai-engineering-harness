"""One read-only view of everything, rebuilt from disk every time it is asked.

The evidence base refuses a dashboard, and the refusal is worth restating
because this ships anyway on a human decision rather than against the argument:
**five liveness recurrences make a dashboard feel obviously justified, and a
human wanting one is not evidence that Core should ship one.** The concrete
objection is sharper than the principle — *a projection over a state nothing
transitions displays a stale value confidently*, and the decisive recorded
instance would have shown `WAITING_ON_JOB` for two hours and twenty-one minutes
and been wrong.

That objection is answered by ordering rather than by argument. Coordinator
state is now **derived** rather than stored (`tools/continuation.py`), so there
is no stored value here to go stale: this recomputes from the artifacts on every
invocation, and it delegates every question to the module that owns it rather
than deriving anything of its own.

## What keeps this from being an authority

*   **It is a renderer, not a service.** One invocation, one answer, exit. No
    port, no daemon, no cache, no database. `DECISIONS.md` D14 clause 11 forbids
    a stateful global coordinator and this is not one — removing it is deleting
    a file that nothing else imports.
*   **It writes nothing.** Not a cache, not a snapshot, not a last-known-good.
    A projection that persisted anything would have state of its own, and state
    of its own is how a projection becomes a second record.
*   **It derives nothing.** Every answer is delegated: liveness to
    `continuation`, output recovery to `task_output`, the pin to `pack_pin`, the
    contract to `project_contract`. A second derivation is a second opinion, and
    two derivations of one fact eventually disagree.
*   **Disagreement with the governance record is a defect here, always.** The
    record is authority; this is a reading of it. That direction is fixed in
    advance so nobody has to adjudicate it while it matters.
*   **What it could not read, it says.** A missing continuation record, an
    unreadable contract, an absent capacity declaration: reported as unknown and
    never as clean, because a dashboard that renders an absence as a resting
    state is the failure it exists to prevent, one level up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Panel", "Projection", "project"]

UNKNOWN = "UNKNOWN"


#: How a line should READ, not how it should look. A tone is a statement about
#: the fact — *this is the thing to do next*, *this could not be established* —
#: and the two renderers below decide separately what that means in a terminal
#: and in a browser.
#:
#: Set by the panel that knows the fact. The alternative was for the HTML
#: renderer to recognise `"UNKNOWN:"` and `"EXPIRED"` in the text, which is a
#: presentation layer inferring meaning from prose — the same
#: passes-for-a-reason-it-does-not-state shape this release has now found seven
#: times, one layer up.
class Tone:
    PLAIN = "plain"
    #: An established good state. Never used for an absence.
    GOOD = "good"
    #: Something a reader should look at, that is not yet wrong.
    WARN = "warn"
    #: A defect, an expiry, a blocked state.
    BAD = "bad"
    #: Could not be established. NEVER rendered as healthy.
    UNKNOWN = "unknown"
    #: The next authorised action.
    ACTION = "action"
    #: Provenance and detail: true, and not what a reader scans for.
    MUTED = "muted"

    ALL = (PLAIN, GOOD, WARN, BAD, UNKNOWN, ACTION, MUTED)


@dataclass
class Line:
    text: str
    tone: str = Tone.PLAIN
    #: Rendered as a key beside the value where a renderer can.
    label: str = ""
    #: Indentation depth, for facts that belong to the fact above them.
    depth: int = 0

    def __post_init__(self) -> None:
        if self.tone not in Tone.ALL:
            raise ValueError(f"unknown tone {self.tone!r}")


@dataclass
class Panel:
    """One section of the view, and what it could not establish."""

    title: str
    lines: list = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    #: A one-phrase answer for this panel, shown beside its title.
    summary: str = ""
    summary_tone: str = Tone.PLAIN

    def say(self, text: str, tone: str = Tone.PLAIN, label: str = "", depth: int = 0) -> None:
        self.lines.append(Line(text, tone, label, depth))

    def rows(self) -> "list[Line]":
        """Every line as a `Line`, including the ones appended as bare strings.

        Bare strings are still accepted because most of this module's panels
        predate tones and say nothing a reader must scan for. A string is
        `PLAIN`, which is the honest default: the panel did not say the fact was
        good, and nothing else should say it for it.
        """
        return [line if isinstance(line, Line) else Line(str(line)) for line in self.lines]

    def render(self) -> str:
        out = [f"── {self.title} " + "─" * max(0, 58 - len(self.title))]
        for line in self.rows():
            out.append("  " + "  " * line.depth
                       + (f"{line.label}: " if line.label else "") + line.text)
        out.extend(f"  {UNKNOWN}: {item}" for item in self.unknown)
        if not self.lines and not self.unknown:
            out.append(f"  {UNKNOWN}: nothing to read")
        return "\n".join(out)


@dataclass
class Projection:
    panels: list[Panel] = field(default_factory=list)

    @property
    def unknowns(self) -> list[str]:
        return [item for panel in self.panels for item in panel.unknown]

    #: The one line a reader glancing at a long run needs, and the reason the
    #: panels below it are detail rather than a search. Delegated, never
    #: decided here: the words come from the state `continuation` derived.
    headline: str = ""

    def render(self) -> str:
        header = [
            "RUNTIME PACK — PROJECTION",
            "  read-only. Rebuilt from durable state on every invocation, and it stores nothing.",
            "  Where this and the governance record disagree, THIS is the defect.",
        ]
        if self.headline:
            header += ["", f"  {self.headline}"]
        if self.unknowns:
            header += [f"  {len(self.unknowns)} thing(s) could not be read — listed in their panels,",
                       "  and an absence is never rendered as a resting state."]
        header.append("")
        return "\n".join(header + [panel.render() for panel in self.panels])


def _contract_panel(contract_path: Path) -> tuple[Panel, object | None]:
    panel = Panel("project and pin")
    try:
        from project_contract import ContractError, ProjectContract

        contract = ProjectContract.load(contract_path)
    except Exception as exc:
        panel.unknown.append(f"the project contract at {contract_path} could not be read: {exc}")
        return panel, None

    pack = contract.raw.get("pack") or {}
    panel.lines.append(f"repository: {contract.repo_path or UNKNOWN}")
    panel.lines.append(
        f"pack pin: {pack.get('version_adopted', UNKNOWN)} at "
        f"{str(pack.get('sha_adopted', UNKNOWN))[:12]} "
        f"state {pack.get('state_adopted', UNKNOWN)}"
    )
    root = pack.get("root_path")
    if not root:
        panel.unknown.append("the pin declares no root path, so the release it names cannot be identified")
    else:
        # Delegated. This module has no opinion about what a valid pin is.
        try:
            import pack_pin

            problems = pack_pin.verify_pin(
                root, expect_version=pack.get("version_adopted"),
                expect_sha=pack.get("sha_adopted"), expect_digest=pack.get("tree_digest_sha256"),
                expect_state=pack.get("state_adopted"),
            )
            panel.lines.append("pin verifies" if not problems
                               else f"PIN DOES NOT VERIFY: {problems[0]}")
        except Exception as exc:
            panel.unknown.append(f"the pin could not be checked: {exc}")
    intent = getattr(contract, "publication_intent", None)
    panel.lines.append(f"publication intent: {intent or 'not declared'}")
    return panel, contract


def _liveness_panel(record_path: Path) -> tuple[Panel, object | None]:
    panel = Panel("coordinator state")
    if not record_path.is_file():
        panel.unknown.append(
            f"no continuation record at {record_path}; the coordinator's position cannot be read, "
            "which is not the same as there being nothing to do"
        )
        return panel, None
    try:
        import continuation

        record = continuation.load(record_path)
        report = continuation.derive(record, relative_to=record_path.parent)
    except Exception as exc:
        panel.unknown.append(f"the continuation record could not be derived: {exc}")
        return panel, None

    panel.lines.append(f"capability: {record.capability}")
    panel.lines.append(f"state: {report.state}")
    panel.lines.append(f"  {report.why}")
    if report.wake_required:
        panel.lines.append("  COORDINATOR_WAKE_REQUIRED")
    if report.is_defect:
        panel.lines.append("  ^ this state is a DEFECT, not a resting place")
    by_id = {wait.job_id: wait for wait in record.waits}
    for observation in report.observations:
        mark = ("COMPLETE" if observation.finished
                else (UNKNOWN if observation.unobservable else "RUNNING"))
        panel.lines.append(f"job {observation.job_id}: {mark} — {observation.how}")
        wait = by_id.get(observation.job_id)
        if wait is None:
            continue
        panel.lines.append(f"    expects: {wait.expects}")
        if wait.obligation and wait.obligation != wait.job_id:
            panel.lines.append(f"    obligation: {wait.obligation}")
        if wait.executor:
            panel.lines.append(f"    executor: {wait.executor}")
        # The subject's identity, because evidence is about ONE tree and a
        # reader who cannot see which one cannot tell current evidence from
        # evidence two repair rounds old. That is not hypothetical here.
        if wait.subject_revision or wait.subject_digest:
            panel.lines.append(
                f"    subject: {wait.subject_revision[:12] or UNKNOWN}"
                f" / {wait.subject_digest[:16] or UNKNOWN}")
        elif wait.kind != continuation.WaitKind.HUMAN:
            panel.unknown.append(
                f"{observation.job_id} does not state the revision it is about, so evidence it "
                f"returns cannot be matched to a tree")
        panel.lines.append(f"    {_deadline_line(wait)}")
    for label, values in (("unconsumed results", report.unconsumed),
                          ("waits nobody can observe", report.unobservable),
                          ("PAST THE DECLARED DEADLINE", report.expired),
                          ("obligations held by more than one wait", report.duplicated),
                          ("superseded waits, retire them", report.superseded),
                          ("blocked", report.blockers)):
        if values:
            panel.lines.append(f"{label}: {', '.join(values)}")
    if report.actionable:
        panel.lines.append(f"authorised and outstanding: {len(report.actionable)} item(s)")
        panel.lines.extend(f"  - {item}" for item in report.actionable)
    # THE NEXT AUTHORISED ACTION, said last so it is the line nearest the eye.
    # It is the record's own first outstanding item, not a choice made here.
    unblocked = [i for i in report.actionable
                 if i not in {n for b in record.blockers for n in b.blocks}]
    if unblocked:
        panel.lines.append(f"NEXT AUTHORISED ACTION: {unblocked[0]}")
    elif report.state in (continuation.State.WAITING_ON_IDENTIFIED_JOB,):
        panel.lines.append("NEXT AUTHORISED ACTION: wait — see the deadline above")
    elif report.blockers:
        panel.lines.append("NEXT AUTHORISED ACTION: none; every outstanding item is blocked")
    return panel, record


def _deadline_line(wait) -> str:
    """When this wait was declared, when it expires, and how far through it is."""
    import continuation

    if wait.not_beyond_seconds is None:
        return "no deadline (a person resolves this; patience is not the question)"
    declared = continuation._moment(wait.declared_at) if wait.declared_at else None
    if declared is None:
        return (f"deadline {wait.not_beyond_seconds:.0f}s after a declaration time that cannot be "
                f"read — TREATED AS EXPIRED")
    from datetime import datetime, timezone

    age = (datetime.now(timezone.utc) - declared).total_seconds()
    remaining = float(wait.not_beyond_seconds) - age
    state = f"{remaining / 60:.0f} min left" if remaining > 0 else f"EXPIRED {-remaining / 60:.0f} min ago"
    return (f"declared {age / 60:.0f} min ago, deadline {float(wait.not_beyond_seconds) / 60:.0f} "
            f"min — {state}")


def _budget_panel(record) -> Panel:
    panel = Panel("budgets and standing evidence")
    if record is None:
        panel.unknown.append("no continuation record, so no budget position is declared")
        return panel
    if not record.budgets:
        panel.unknown.append(
            "the record declares no budgets. NOT the same as none spent — an untracked counter is "
            "unknown, and zero-used is a claim nobody made")
    for counter, position in sorted(record.budgets.items()):
        used, ceiling = position.get("used"), position.get("ceiling")
        left = (ceiling - used) if isinstance(used, int) and isinstance(ceiling, int) else UNKNOWN
        line = f"{counter}: {used}/{ceiling} used, {left} remaining"
        if position.get("authorised_by"):
            line += f"  (raised by {position['authorised_by']})"
        panel.lines.append(line)
    if not record.evidence:
        panel.unknown.append(
            "the record declares no standing evidence — suite, gates, latest audit verdict and "
            "closure position are not readable from here")
    for name in ("candidate", "suite", "gates", "latest_audit", "closure"):
        if name in record.evidence:
            panel.lines.append(f"{name}: {record.evidence[name]}")
    for name, value in sorted(record.evidence.items()):
        if name not in ("candidate", "suite", "gates", "latest_audit", "closure"):
            panel.lines.append(f"{name}: {value}")
    return panel


def _freshness_panel(record, record_path: Path) -> Panel:
    """How old the reading is. A projection of a stale record is a stale
    projection, and the objection this whole module was built against was
    exactly that — so the age of the record is rendered rather than assumed
    small."""
    panel = Panel("freshness of this reading")
    if record is None:
        panel.unknown.append("no record, so nothing to date")
        return panel
    import continuation
    from datetime import datetime, timezone

    written = continuation._moment(record.updated_at) if record.updated_at else None
    if written is None:
        panel.unknown.append(
            f"the record's own timestamp {record.updated_at!r} cannot be read, so how old this "
            f"reading is cannot be established")
        return panel
    age = (datetime.now(timezone.utc) - written).total_seconds()
    panel.lines.append(f"record written {age / 60:.0f} min ago ({record.updated_at})")
    panel.lines.append(f"read from {record_path}")
    if age > 3600:
        panel.lines.append(
            "  STALE: this record has not been rewritten in over an hour. Every state above is "
            "derived from artifacts and so is current, but the OBLIGATIONS are as the coordinator "
            "last wrote them and may no longer be what it is doing")
    return panel


def _pack_panel(here: Path) -> Panel:
    """The identity of the pack this projection is part of — not the project's
    pin, which is the panel above, but what is actually running."""
    panel = Panel("the pack this projection ships in")
    manifest = here / "PACK_MANIFEST.json"
    if not manifest.is_file():
        panel.unknown.append(f"no manifest at {manifest}")
        return panel
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        panel.unknown.append(f"the manifest could not be read: {exc}")
        return panel
    panel.lines.append(f"version {document.get('version', UNKNOWN)}  "
                       f"state {document.get('state', UNKNOWN)}")
    panel.lines.append(f"digest {str(document.get('tree_digest_sha256', UNKNOWN))[:16]}…")
    if document.get("state") != "QUALIFIED_AND_FROZEN":
        panel.lines.append("  NOT ADOPTABLE: only QUALIFIED_AND_FROZEN may be pinned by a project")
    return panel


def _output_panel(record, base: Path) -> Panel:
    panel = Panel("durable worker output")
    if record is None:
        panel.unknown.append("no continuation record, so no output roots are declared")
        return panel

    import continuation
    import task_output

    roots = [w for w in record.waits if w.kind == continuation.WaitKind.OUTPUT_ROOT]
    if not roots:
        panel.lines.append("no task declares an output root")
        return panel
    for wait in roots:
        root = Path(wait.path)
        if not root.is_absolute():
            root = base / root
        try:
            contract = task_output.OutputContract(
                task_id=wait.task_id, output_root=root,
                max_bytes_per_write=int(wait.max_bytes_per_write),
            )
            report = task_output.classify(contract)
        except Exception as exc:
            panel.unknown.append(f"{wait.job_id}: the output root could not be classified: {exc}")
            continue
        panel.lines.append(f"{wait.job_id}: {report.state} — {report.examined.summary()}")
        if report.state == task_output.RecoveryState.UNKNOWN:
            panel.lines.append(f"  {report.why}")
    return panel


def _capacity_panel(path: Path) -> Panel:
    """Whatever the project last observed about its windows.

    Read from a declaration rather than measured, and the age of that
    declaration is part of the answer: a reading is evidence about the moment it
    was taken and licenses no claim about what the next dispatch will cost.
    """
    panel = Panel("capacity")
    if not path.is_file():
        panel.unknown.append(
            f"no capacity observation at {path}; no window is known, which is the ordinary case "
            "for a provider with no machine-readable surface and is not zero"
        )
        return panel
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        pools = raw.get("pools") or []
    except Exception as exc:
        panel.unknown.append(f"the capacity observation could not be read: {exc}")
        return panel

    import capacity

    if not pools:
        panel.unknown.append("the capacity observation declares no pools")
    for entry in pools:
        try:
            pool = capacity.Pool(**entry)
        except Exception as exc:
            panel.unknown.append(f"a pool declaration could not be read: {exc}")
            continue
        remaining = pool.remaining if pool.known else UNKNOWN
        panel.lines.append(
            f"{pool.pool_id} [{pool.kind}/{pool.window}]: {remaining} {pool.unit} remaining, "
            f"{pool.active_workers} active, resets {pool.resets_at or UNKNOWN}, "
            f"observed {pool.observed_at or UNKNOWN}"
        )
    reserve = raw.get("reserve") or {}
    if reserve:
        try:
            declared = capacity.Reserve(**reserve)
            panel.lines.append(
                f"reserve: coordinator {declared.coordinator}, consumption "
                f"{declared.result_consumption}, repair and audit {declared.repair_and_audit}"
                + ("" if declared.declared else "  (partial, so the total is UNKNOWN)")
            )
        except Exception as exc:
            panel.unknown.append(f"the reserve declaration could not be read: {exc}")
    else:
        panel.unknown.append("no reserve is declared, so no dispatch arithmetic can be done")
    return panel


def project(
    project_root: str | Path,
    *,
    contract: str = "PROJECT.yaml",
    continuation_record: str = "CONTINUATION.json",
    capacity_observation: str = "CAPACITY.json",
) -> Projection:
    """Read the durable state and render it. Nothing else.

    Every path is relative to the project root and every one may be absent —
    absence is reported as unknown, never rendered as a resting state.
    """
    base = Path(project_root)
    record_path = base / continuation_record
    contract_panel, _contract = _contract_panel(base / contract)
    liveness_panel, record = _liveness_panel(record_path)
    return Projection(
        headline=_headline(record),
        panels=[
            _pack_panel(Path(__file__).resolve().parent.parent),
            contract_panel,
            liveness_panel,
            _output_panel(record, base),
            _budget_panel(record),
            _capacity_panel(base / capacity_observation),
            _freshness_panel(record, record_path),
        ],
    )


def _headline(record) -> str:
    """One line: is useful progress occurring, and if not, what is in the way.

    **Delegated, never decided here.** The words come from the state
    `continuation` derived; this chooses which sentence to put at the top and
    nothing else. A projection that reached its own verdict would be a second
    opinion about the thing it is a reading of.
    """
    if record is None:
        return ("UNKNOWN — no continuation record. This is not 'nothing to do': it is 'the "
                "coordinator's position cannot be read'.")
    try:
        import continuation

        report = continuation.derive(record, relative_to=Path(record.record_path or ".").parent)
    except Exception as exc:
        return f"UNKNOWN — the record could not be derived: {exc}"
    S = continuation.State
    sentences = {
        S.WAITING_ON_IDENTIFIED_JOB: "WAITING — a named job is running and its deadline is below.",
        S.COMPLETED_NOT_CONSUMED: "A RESULT IS WAITING TO BE READ. The job finished; nobody has consumed it.",
        S.RECOVERY_REQUIRED: "RECOVERY REQUIRED — something is wrong with the record or a job, detail below.",
        S.BLOCKED_ON_HUMAN: "BLOCKED ON A PERSON — see exactly what it blocks below.",
        S.BLOCKED_ON_CAPACITY: "BLOCKED ON CAPACITY — no window is available for the outstanding work.",
        S.SILENT_IDLE: "SILENT_IDLE — THERE IS WORK TO DO AND NOTHING IS OUTSTANDING. This is the defect this release exists to close, not a resting state.",
        S.ACTIONABLE_WORK_READY: "WORK IS READY and the coordinator is expected to be doing it.",
        S.TERMINAL: "TERMINAL — nothing is outstanding and nothing is authorised.",
    }
    return f"{report.state}: {sentences.get(report.state, 'see below')}"


def _cli(argv: list[str]) -> int:
    """Render the current state of one project, read-only.

    Usage: ``projection.py PROJECT_ROOT [--contract NAME] [--continuation NAME]
                           [--capacity NAME]``

    Exit status: ``0`` rendered with everything established, ``1`` rendered with
    something it could not read. Never non-zero because the *project* is in a
    bad state — that is the project's business and this only reports it.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="projection.py",
        description="One read-only view of a project's durable state. Writes nothing.")
    parser.add_argument("project_root")
    parser.add_argument("--contract", default="PROJECT.yaml")
    parser.add_argument("--continuation", default="CONTINUATION.json")
    parser.add_argument("--capacity", default="CAPACITY.json")
    args = parser.parse_args(argv)

    view = project(args.project_root, contract=args.contract,
                   continuation_record=args.continuation,
                   capacity_observation=args.capacity)
    print(view.render())
    return 1 if view.unknowns else 0


if __name__ == "__main__":
    import sys

    # Run the module, not a second copy of it. A file executed as a script is
    # `__main__`, and a sibling that imports it BY NAME gets a separate module
    # object with separate class objects — so an `isinstance` check across that
    # boundary is False for an object that is exactly that class. Imported
    # statically, by name, because a dynamic import would route around the
    # toolbelt's import-closure check.
    from errors import run_cli
    from projection import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
