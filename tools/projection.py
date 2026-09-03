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

__all__ = ["Line", "Panel", "Projection", "Tone", "project", "render_html"]

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
    #: Which question this panel answers. A reader scanning a long run asks four
    #: things in order — what is happening, is anything wrong, what happens next,
    #: and then everything else — and panels in the order they were written do
    #: not answer them in that order.
    group: str = "detail"
    #: A panel whose lines are a VOCABULARY rather than findings. The state
    #: legend marks the current state urgently, correctly, and hoisting that into
    #: the attention strip restates the headline in different words — noise in
    #: the one place that must not have any.
    legend: bool = False

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

    @property
    def attention(self) -> "list[Line]":
        """Every line a reader must not miss, hoisted out of its panel.

        Nothing is computed: these are the lines the owning panel already marked
        BAD, WARN or UNKNOWN. Hoisting them is a change of position, not of
        judgement — the panel still shows them where they belong, and this is a
        second place to find them rather than the only one.
        """
        urgent = (Tone.BAD, Tone.WARN, Tone.UNKNOWN)
        #: What the header already says, in the words it says it in. The state
        #: appeared three times in the strip — as the coordinator's `state`, as
        #: the legend's current entry, and as the headline above it.
        said_already = {"state"}
        found = []
        for panel in self.panels:
            if panel.legend:
                continue
            for line in panel.rows():
                if line.label in said_already:
                    continue
                if line.tone in urgent:
                    found.append(Line(f"{panel.title} — "
                                      + (f"{line.label}: " if line.label else "") + line.text,
                                      line.tone))
            for item in panel.unknown:
                found.append(Line(f"{panel.title} — {item}", Tone.UNKNOWN))
        found.sort(key=lambda l: (Tone.BAD, Tone.WARN, Tone.UNKNOWN).index(l.tone))
        return found

    @property
    def next_action(self) -> str:
        for panel in self.panels:
            for line in panel.rows():
                if line.label == "NEXT AUTHORISED ACTION":
                    return line.text
        return ""

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
    panel = Panel("project and pin", group="identity")
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
    panel = Panel("coordinator state", group="now")
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

    panel.say(record.capability, label="capability")
    panel.say(report.state, Tone.BAD if report.is_defect else Tone.PLAIN, label="state")
    panel.say(report.why, Tone.MUTED, depth=1)
    panel.summary, panel.summary_tone = report.state, (Tone.BAD if report.is_defect else Tone.PLAIN)
    if report.wake_required:
        panel.say("COORDINATOR_WAKE_REQUIRED", Tone.WARN, depth=1)
    if report.is_defect:
        panel.say("this state is a DEFECT, not a resting place", Tone.BAD, depth=1)
    by_id = {wait.job_id: wait for wait in record.waits}
    for observation in report.observations:
        mark = ("COMPLETE" if observation.finished
                else (UNKNOWN if observation.unobservable else "RUNNING"))
        panel.say(f"{mark} — {observation.how}",
                  {"COMPLETE": Tone.GOOD, UNKNOWN: Tone.UNKNOWN}.get(mark, Tone.PLAIN),
                  label=f"job {observation.job_id}")
        wait = by_id.get(observation.job_id)
        if wait is None:
            continue
        panel.say(wait.expects, Tone.MUTED, label="expects", depth=1)
        if wait.attempt and wait.attempt > 1:
            panel.say(f"attempt {wait.attempt}"
                      + (f" — the previous one {wait.retry_reason}" if wait.retry_reason else
                         " — no reason recorded for the previous one"),
                      Tone.WARN, depth=1)
        panel.say(wait.routing_qualification or UNKNOWN,
                  Tone.MUTED if wait.routing_qualification else Tone.UNKNOWN,
                  label="routing qualification", depth=1)
        if wait.obligation and wait.obligation != wait.job_id:
            panel.say(wait.obligation, Tone.MUTED, label="obligation", depth=1)
        if wait.executor:
            panel.say(wait.executor, Tone.MUTED, label="executor", depth=1)
        # The subject's identity, because evidence is about ONE tree and a
        # reader who cannot see which one cannot tell current evidence from
        # evidence two repair rounds old. That is not hypothetical here.
        if wait.subject_revision or wait.subject_digest:
            panel.say(f"{wait.subject_revision[:12] or UNKNOWN} / "
                      f"{wait.subject_digest[:16] or UNKNOWN}",
                      Tone.MUTED, label="subject", depth=1)
        elif wait.kind != continuation.WaitKind.HUMAN:
            panel.unknown.append(
                f"{observation.job_id} does not state the revision it is about, so evidence it "
                f"returns cannot be matched to a tree")
        panel.say(_guarded(_progress_line, wait, observation,
                           default=f"{UNKNOWN} — could not be dated"),
                  Tone.MUTED, label="last progress", depth=1)
        deadline = _guarded(_deadline_line, wait,
                            default=f"{UNKNOWN} — this wait's deadline could not be read")
        panel.say(deadline,
                  Tone.BAD if "EXPIRED" in deadline else
                  (Tone.MUTED if "no deadline" in deadline else Tone.PLAIN), depth=1)
    for label, values, tone in (
            ("unconsumed results", report.unconsumed, Tone.WARN),
            ("waits nobody can observe", report.unobservable, Tone.UNKNOWN),
            ("PAST THE DECLARED DEADLINE", report.expired, Tone.BAD),
            ("obligations held by more than one wait", report.duplicated, Tone.BAD),
            ("superseded waits, retire them", report.superseded, Tone.WARN),
            ("blocked", report.blockers, Tone.WARN)):
        if values:
            panel.say(", ".join(values), tone, label=label)
    if report.actionable:
        panel.say(f"{len(report.actionable)} item(s)", label="authorised and outstanding")
        blocked_names = {n for b in record.blockers for n in b.blocks}
        for item in report.actionable:
            panel.say(item, Tone.MUTED if item in blocked_names else Tone.PLAIN, depth=1)
    # THE NEXT AUTHORISED ACTION, said last so it is the line nearest the eye.
    # It is the record's own first outstanding item, not a choice made here.
    unblocked = [i for i in report.actionable
                 if i not in {n for b in record.blockers for n in b.blocks}]
    if unblocked:
        panel.say(unblocked[0], Tone.ACTION, label="NEXT AUTHORISED ACTION")
    elif report.state in (continuation.State.WAITING_ON_IDENTIFIED_JOB,):
        panel.say("wait — see the deadline above", Tone.ACTION, label="NEXT AUTHORISED ACTION")
    elif report.blockers:
        panel.say("none; every outstanding item is blocked", Tone.WARN,
                  label="NEXT AUTHORISED ACTION")
    return panel, record


def _progress_line(wait, observation) -> str:
    """When this job last did something a reader could see, and how long ago.

    **Process existence is not progress**, so a live process with nothing to show
    reports the age of its declaration and says that is all it has. For an output
    root the newest artifact is a real event; for a sentinel, its mtime is.
    Everything else is UNKNOWN, and UNKNOWN is what it says.
    """
    from datetime import datetime, timezone
    import continuation

    newest, what = None, ""
    if wait.path:
        target = Path(wait.path)
        candidates = ([target] if target.is_file() else
                      [p for p in target.rglob("*") if p.is_file()] if target.is_dir() else [])
        if candidates:
            newest = max(p.stat().st_mtime for p in candidates)
            what = "an artifact it wrote"
    if newest is None:
        declared = continuation._moment(wait.declared_at) if wait.declared_at else None
        if declared is None:
            return f"{UNKNOWN} — nothing dates this job"
        age = (datetime.now(timezone.utc) - declared).total_seconds()
        return (f"{UNKNOWN} — nothing observable has been written; the job was declared "
                f"{age / 60:.0f} min ago and a live process is not progress")
    age = (datetime.now(timezone.utc) - datetime.fromtimestamp(newest, tz=timezone.utc)).total_seconds()
    return f"{age / 60:.0f} min ago ({what})"


def _states_panel(record, report) -> Panel:
    """Every state this projection can report, and which one is true now.

    A reader who sees `WAITING` needs to know what the alternatives were. Without
    the vocabulary in front of them, an absent state and an impossible state look
    identical — and two of these, `STALLED` and `ORPHANED`, are states this
    single reading genuinely cannot establish. Saying so is the point of the
    panel.
    """
    import continuation

    panel = Panel("the states this reading can report", group="now", legend=True)
    if report is None:
        panel.unknown.append("no derived state, so none of the vocabulary applies")
        return panel
    S = continuation.State
    current = report.state
    for state in (S.WAITING_ON_IDENTIFIED_JOB, S.COMPLETED_NOT_CONSUMED, S.ACTIONABLE_WORK_READY,
                  S.BLOCKED_ON_HUMAN, S.BLOCKED_ON_CAPACITY, S.RECOVERY_REQUIRED,
                  S.SILENT_IDLE, S.TERMINAL):
        here = state == current
        panel.say("THIS ONE" if here else "not now",
                  (Tone.BAD if state in continuation.State.DEFECTS else Tone.PLAIN) if here
                  else Tone.MUTED, label=state)
    panel.say("this reading cannot establish it: a stall needs two independently observed "
              "flat signals over time and this is one reading. `progress.classify` is the "
              "module that answers it", Tone.UNKNOWN, label="STALLED")
    orphans = [o.job_id for o in report.observations
               if o.finished and o.job_id in report.unconsumed]
    panel.say(", ".join(orphans) + " — finished with a result nobody has taken up"
              if orphans else "no job finished without its result being consumed",
              Tone.WARN if orphans else Tone.MUTED, label="ORPHANED")
    panel.say(", ".join(report.superseded) if report.superseded else "none",
              Tone.WARN if report.superseded else Tone.MUTED, label="SUPERSEDED")
    return panel


def _audit_freshness_panel(record) -> Panel:
    """Whether any audit in flight is about the tree this record calls the
    candidate. An audit of revision A must never look current for revision B —
    it happened in this release and cost six findings' worth of re-execution."""
    panel = Panel("audit subject vs candidate", group="evidence")
    if record is None:
        panel.unknown.append("no record, so no audit subject is declared")
        return panel
    declared = str(record.evidence.get("candidate", ""))
    if not declared:
        panel.unknown.append(
            "the record does not state which revision is the candidate, so no audit's subject "
            "can be compared against it")
    audits = [w for w in record.waits if w.subject_revision or w.subject_digest]
    if not audits:
        panel.say("no outstanding job states a subject revision", Tone.MUTED)
        return panel
    for wait in audits:
        short = wait.subject_revision[:12]
        if not declared:
            panel.say(f"{short or UNKNOWN} — cannot be compared", Tone.UNKNOWN, label=wait.job_id)
        elif short and short in declared:
            panel.say(f"{short} — the candidate", Tone.GOOD, label=wait.job_id)
        else:
            panel.say(f"{short or UNKNOWN} — NOT the candidate this record declares. Findings "
                      f"from it describe a different tree", Tone.BAD, label=wait.job_id)
    return panel


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
    panel = Panel("budgets and standing evidence", group="evidence")
    if record is None:
        panel.unknown.append("no continuation record, so no budget position is declared")
        return panel
    if not record.budgets:
        panel.unknown.append(
            "the record declares no budgets. NOT the same as none spent — an untracked counter is "
            "unknown, and zero-used is a claim nobody made")
    for counter, position in sorted(record.budgets.items()):
        if not isinstance(position, dict):
            # `budgets: {"cycles": 7}` loads and then raises here. A projection
            # may not raise, least of all on the record it exists to display.
            panel.say(f"{position!r} — not a position this view can read", Tone.UNKNOWN,
                      label=counter)
            continue
        used, ceiling = position.get("used"), position.get("ceiling")
        left = (ceiling - used) if isinstance(used, int) and isinstance(ceiling, int) else UNKNOWN
        spent = isinstance(left, int) and left <= 0
        text = f"{used}/{ceiling} used, {left} remaining"
        if position.get("authorised_by"):
            text += f"  (raised by {position['authorised_by']})"
        panel.say(text, Tone.WARN if spent else Tone.PLAIN, label=counter)
    # THE READINGS A LONG RUN NEEDS, listed whether or not the record carries
    # them. An absent key simply did not appear before, which makes *nobody
    # declared this* and *this is fine* look identical — the one thing this
    # projection may never do. Named here so absence is a visible UNKNOWN.
    for name in ("candidate", "suite", "gates", "latest_audit", "closure",
                 "recurrence_classes", "real_consumers", "adapters", "continuation",
                 "public_safety", "evolution_candidates"):
        if name in record.evidence:
            panel.say(str(record.evidence[name]), label=name)
        else:
            panel.unknown.append(f"the record declares no {name.replace('_', ' ')}")
    for name, value in sorted(record.evidence.items()):
        if name not in ("candidate", "suite", "gates", "latest_audit", "closure",
                        "recurrence_classes", "real_consumers", "adapters", "continuation",
                        "public_safety", "evolution_candidates"):
            panel.say(str(value), Tone.MUTED, label=name)
    return panel


def _freshness_panel(record, record_path: Path) -> Panel:
    """How old the reading is. A projection of a stale record is a stale
    projection, and the objection this whole module was built against was
    exactly that — so the age of the record is rendered rather than assumed
    small."""
    panel = Panel("freshness of this reading", group="identity")
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
    panel = Panel("the pack this projection ships in", group="identity")
    manifest = here / "PACK_MANIFEST.json"
    if not manifest.is_file():
        panel.unknown.append(f"no manifest at {manifest}")
        return panel
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        panel.unknown.append(f"the manifest could not be read: {exc}")
        return panel
    state = document.get("state", UNKNOWN)
    panel.say(str(document.get("version", UNKNOWN)), label="version")
    panel.say(str(state), Tone.GOOD if state == "QUALIFIED_AND_FROZEN" else Tone.WARN,
              label="state")
    panel.say(f"{str(document.get('tree_digest_sha256', UNKNOWN))[:16]}…", Tone.MUTED,
              label="digest")
    # Absent from the tree BY DESIGN, and said rather than left blank: a manifest
    # cannot name the commit that contains it. The identity is version + revision
    # + digest + state, and the consuming project records the revision in its own
    # pin. A reader who needs it runs the command.
    panel.say("not in the tree — `git rev-parse HEAD`, because a manifest cannot name the "
              "commit that contains it", Tone.MUTED, label="revision")
    panel.summary = f"{document.get('version', UNKNOWN)} {state}"
    panel.summary_tone = Tone.GOOD if state == "QUALIFIED_AND_FROZEN" else Tone.WARN
    if state != "QUALIFIED_AND_FROZEN":
        panel.say("NOT ADOPTABLE: only QUALIFIED_AND_FROZEN may be pinned by a project",
                  Tone.WARN, depth=1)
    return panel


def _output_panel(record, base: Path) -> Panel:
    panel = Panel("durable worker output", group="now")
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
        panel.say(f"{report.state} — {report.examined.summary()}",
                  {task_output.RecoveryState.COMPLETED_WITH_DURABLE_OUTPUT: Tone.GOOD,
                   task_output.RecoveryState.UNKNOWN: Tone.UNKNOWN,
                   task_output.RecoveryState.FAILED_WITH_PARTIAL_DURABLE_OUTPUT: Tone.WARN,
                   task_output.RecoveryState.FAILED_BEFORE_USEFUL_OUTPUT: Tone.WARN}
                  .get(report.state, Tone.PLAIN), label=wait.job_id)
        # WHOSE root this is. The panel showed a state and never said which task
        # owns the artifacts it describes — found by sharpening the contract's
        # marker for *task ownership* until it stopped matching something else,
        # at which point there was nothing left for it to match.
        panel.say(str(wait.task_id), Tone.MUTED, label="task_id", depth=1)
        if report.state == task_output.RecoveryState.UNKNOWN:
            panel.say(report.why, Tone.UNKNOWN, depth=1)
    return panel


def _capacity_panel(path: Path) -> Panel:
    """Whatever the project last observed about its windows.

    Read from a declaration rather than measured, and the age of that
    declaration is part of the answer: a reading is evidence about the moment it
    was taken and licenses no claim about what the next dispatch will cost.
    """
    panel = Panel("capacity", group="resources")
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
    # The liveness panel is built inside the same guard as the rest. It returns
    # the record as well, so it could not go through `_panel` — and being the
    # one panel outside the guard is how `attempt: "three"` still raised after
    # every other panel was covered.
    try:
        liveness_panel, record = _liveness_panel(record_path)
    except Exception as exc:
        liveness_panel = Panel("coordinator state", group="now")
        liveness_panel.unknown.append(
            f"the coordinator's position could not be rendered from this record: "
            f"{type(exc).__name__}: {exc}"[:300])
        liveness_panel.summary, liveness_panel.summary_tone = UNKNOWN, Tone.UNKNOWN
        try:
            import continuation
            record = continuation.load(record_path)
        except Exception:
            record = None
    return Projection(
        headline=_guarded(_headline, record, default=f"{UNKNOWN} — the headline could not be derived"),
        panels=[
            _pack_panel(Path(__file__).resolve().parent.parent),
            contract_panel,
            liveness_panel,
            # EVERY panel, not the fields anybody has thought of. Guarding the
            # deadline and the budget position one at a time closed two shapes
            # and left `attempt: "three"` and `{"pools": 1}` — an independent
            # reader found both, and would have found a third. A panel that
            # cannot be built reports that it could not be built, which is the
            # only behaviour a view of a broken record may have.
            _panel(_states_panel, record, _report_or_none(record, record_path),
                   title="the states this reading can report", group="now"),
            _panel(_audit_freshness_panel, record,
                   title="audit subject vs candidate", group="evidence"),
            _panel(_output_panel, record, base,
                   title="durable worker output", group="now"),
            _panel(_budget_panel, record,
                   title="budgets and standing evidence", group="evidence"),
            _panel(_capacity_panel, base / capacity_observation,
                   title="capacity", group="resources"),
            _panel(_freshness_panel, record, record_path,
                   title="freshness of this reading", group="identity"),
        ],
    )


def _panel(build, *args, title: str, group: str) -> Panel:
    """Build a panel, or a panel saying why it could not be built."""
    try:
        return build(*args)
    except Exception as exc:
        panel = Panel(title, group=group)
        panel.unknown.append(
            f"this panel could not be built from the record: {type(exc).__name__}: {exc}"[:300])
        panel.summary, panel.summary_tone = UNKNOWN, Tone.UNKNOWN
        return panel


# --- the same reading, in a browser ------------------------------------------------
#
# One file, no network. The pack is stdlib-only and a projection that fetched a
# stylesheet would be a projection that fails differently depending on where it
# is opened — and it must render the same on a laptop with no route to anywhere
# as it does anywhere else.
#
# It writes nothing, exactly as the text renderer writes nothing: the HTML goes
# to stdout, and a caller redirecting that to a file is the caller writing.

_STYLE = """
/* --- the structural pass -------------------------------------------------
   A reader of a long run asks four things in order: what is happening, is
   anything wrong, what happens next, and then everything else. The page is
   laid out in that order and the type sizes follow it. Detail is preserved
   in full and put behind a disclosure rather than deleted, because the
   forensic reading is the second reading and both have to be possible.      */
.state{font-size:26px;line-height:1.15;font-weight:700;letter-spacing:-.01em;margin:0 0 6px}
.said{font-size:13px;color:var(--dim);max-width:78ch;margin:0}
.next{margin-top:14px;padding:12px 14px;border-radius:8px;background:var(--actionbg);
border-left:4px solid var(--action)}
.next b{display:block;font-size:11px;letter-spacing:.12em;color:var(--action);margin-bottom:3px}
.next span{font-size:15px;font-weight:600}
.attn{margin-top:14px;border:1px solid var(--rule);border-radius:8px;overflow:hidden}
.attn>summary{cursor:pointer;padding:9px 14px;font-size:12px;letter-spacing:.08em;
text-transform:uppercase;color:var(--dim);background:var(--bg);list-style:none}
.attn>summary::-webkit-details-marker{display:none}
.attn>summary::before{content:"▸ ";color:var(--dim)}
.attn[open]>summary::before{content:"▾ "}
.attn ul{padding:4px 0}
.attn li{font-size:12.5px}
.count{display:inline-block;min-width:20px;text-align:center;padding:1px 7px;border-radius:99px;
font-size:11px;font-weight:700;margin-left:6px}
.count.bad{background:var(--badbg);color:var(--bad)}
.count.warn{background:var(--warnbg);color:var(--warn)}
.count.unknown{background:var(--unknownbg);color:var(--unknown)}
.count.good{background:var(--goodbg);color:var(--good)}
h3.group{grid-column:1/-1;margin:10px 2px 0;font-size:11px;letter-spacing:.16em;
text-transform:uppercase;color:var(--dim);font-weight:700}
h3.group:first-of-type{margin-top:0}
section>details>summary{cursor:pointer;padding:6px 14px 8px;font-size:11.5px;color:var(--dim);
letter-spacing:.06em;list-style:none;border-top:1px solid var(--rule)}
section>details>summary::-webkit-details-marker{display:none}
section>details>summary::before{content:"▸ ";}
section>details[open]>summary::before{content:"▾ ";}

:root{--ink:#12161c;--dim:#5b6675;--rule:#dde3ea;--card:#fff;--bg:#f4f6f9;
--good:#1a7f4b;--warn:#8a5a00;--bad:#b3261e;--unknown:#5b4b8a;--action:#0b4fa8;
--goodbg:#e8f5ee;--warnbg:#fdf3e0;--badbg:#fdeceb;--unknownbg:#efecf8;--actionbg:#e8f0fc}
@media(prefers-color-scheme:dark){:root{--ink:#e6ebf2;--dim:#98a4b4;--rule:#2a3340;
--card:#161b22;--bg:#0d1117;--good:#5ed09a;--warn:#e3b341;--bad:#ff7b72;--unknown:#b9a6ff;
--action:#79b8ff;--goodbg:#12261c;--warnbg:#2a2010;--badbg:#2d1513;--unknownbg:#1e1a2e;
--actionbg:#111d2e}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
header{padding:20px 20px 16px;border-bottom:1px solid var(--rule);background:var(--card)}
h1{margin:0 0 4px;font-size:15px;letter-spacing:.14em;text-transform:uppercase}
.sub{color:var(--dim);font-size:12px;max-width:70ch}
.verdict{margin-top:14px;padding:12px 14px;border-radius:8px;font-size:14px;
border-left:4px solid var(--dim);background:var(--bg)}
.verdict b{display:block;font-size:12px;letter-spacing:.1em;margin-bottom:3px}
.v-bad{border-left-color:var(--bad);background:var(--badbg);color:var(--bad)}
.v-warn{border-left-color:var(--warn);background:var(--warnbg);color:var(--warn)}
.v-good{border-left-color:var(--good);background:var(--goodbg);color:var(--good)}
.v-unknown{border-left-color:var(--unknown);background:var(--unknownbg);color:var(--unknown)}
main{display:grid;gap:14px 14px;padding:16px 20px 40px;
grid-template-columns:repeat(auto-fit,minmax(min(100%,400px),1fr));align-items:start}
@media(min-width:1250px){main{grid-template-columns:repeat(3,1fr)}}
section{background:var(--card);border:1px solid var(--rule);border-radius:8px;overflow:hidden}
.head{display:flex;justify-content:space-between;gap:10px;align-items:baseline;
padding:10px 14px;border-bottom:1px solid var(--rule)}
.head h2{margin:0;font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--dim)}
.chip{font-size:11px;padding:2px 8px;border-radius:99px;background:var(--bg);color:var(--dim);
white-space:nowrap}
.chip.good{background:var(--goodbg);color:var(--good)}
.chip.warn{background:var(--warnbg);color:var(--warn)}
.chip.bad{background:var(--badbg);color:var(--bad)}
.chip.unknown{background:var(--unknownbg);color:var(--unknown)}
ul{list-style:none;margin:0;padding:6px 0}
li{padding:3px 14px;display:flex;gap:8px;flex-wrap:wrap;word-break:break-word}
li .k{color:var(--dim);flex:0 0 auto}
/* The value shares the label's line and wraps inside its own column. Without
   this a long value wrapped BELOW its key, and the key read as having no
   value at all -- found by rendering, not by reading. */
li .v{flex:1 1 14rem;min-width:0}
li .k::after{content:":"}
li.d1{padding-left:32px}li.d2{padding-left:50px}
li.good .v{color:var(--good)}li.warn .v{color:var(--warn)}li.bad .v{color:var(--bad);font-weight:600}
li.muted{color:var(--dim)}li.muted .v{color:var(--dim)}
li.unknown{background:var(--unknownbg)}li.unknown .v{color:var(--unknown)}
li.action{background:var(--actionbg)}li.action .v{color:var(--action);font-weight:600}
li.unknown>.k{color:var(--unknown);font-weight:600}
.empty{padding:8px 14px;color:var(--unknown);background:var(--unknownbg)}
footer{padding:0 20px 30px;color:var(--dim);font-size:12px;max-width:78ch}
@media(max-width:700px){main{padding:12px;gap:12px}header{padding:14px}
li{padding-left:12px;padding-right:12px}li.d1{padding-left:24px}li.d2{padding-left:36px}}
"""


def _escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_html(view: "Projection", title: str = "Runtime Pack — projection") -> str:
    """The same panels, for a browser. Derives nothing the text renderer does not.

    Laid out in the order a reader of a long run actually asks: **what is
    happening, is anything wrong, what happens next**, and only then the panels.
    Nothing is summarised away — every line the text view shows is here, and the
    ones hoisted into the attention strip appear in their panels as well.
    """
    tone = _verdict_tone(view.headline)
    verdict_class = {Tone.BAD: "v-bad", Tone.WARN: "v-warn", Tone.GOOD: "v-good",
                     Tone.UNKNOWN: "v-unknown"}.get(tone, "")
    state, _, sentence = view.headline.partition(":")
    attention = view.attention
    counts = {t: sum(1 for line in attention if line.tone == t)
              for t in (Tone.BAD, Tone.WARN, Tone.UNKNOWN)}

    out = ["<!doctype html>", "<html lang=\"en\">", "<head>", "<meta charset=\"utf-8\">",
           "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
           f"<title>{_escape(title)}</title>", f"<style>{_STYLE}</style>", "</head>", "<body>",
           "<header>", "<h1>Runtime Pack — projection</h1>",
           f"<div class='verdict {verdict_class}'>",
           f"<p class=state>{_escape(state.strip())}</p>",
           f"<p class=said>{_escape(sentence.strip() or view.headline)}</p>", "</div>"]

    if view.next_action:
        out.append("<div class=next><b>NEXT AUTHORISED ACTION</b>"
                   f"<span>{_escape(view.next_action)}</span></div>")

    if attention:
        badge = "".join(
            f"<span class='count {t}'>{n}</span>" for t, n in counts.items() if n)
        out.append(f"<details class=attn open><summary>needs attention{badge}</summary><ul>")
        for line in attention:
            out.append(f"<li class='{line.tone}'><span class=v>{_escape(line.text)}</span></li>")
        out.append("</ul></details>")
    else:
        out.append("<details class=attn><summary>needs attention"
                   "<span class='count good'>0</span></summary>"
                   "<ul><li class=muted><span class=v>nothing is marked wrong, unknown or "
                   "waiting on a person. That is a reading of this record, not a promise about "
                   "the run.</span></li></ul></details>")

    out.append("</header><main>")
    for group, heading in (("now", "what is happening"), ("evidence", "what is established"),
                           ("resources", "what it is spending"), ("identity", "what this is"),
                           ("detail", "everything else")):
        panels = [p for p in view.panels if p.group == group]
        if not panels:
            continue
        out.append(f"<h3 class=group>{_escape(heading)}</h3>")
        for panel in panels:
            rows = panel.rows()
            #: The forensic half. A line is detail when its own panel marked it
            #: MUTED or nested it under another — never when it is BAD, WARN or
            #: UNKNOWN, because putting uncertainty behind a disclosure is
            #: hiding it.
            # Depth does NOT decide this. The first version collapsed anything
            # nested, and an expired deadline is a nested line marked BAD — so
            # the single most urgent fact on the page went behind a disclosure.
            # Caught by the test that asserts uncertainty is never collapsed,
            # which is the reason to write that test rather than assume it.
            urgent = (Tone.BAD, Tone.WARN, Tone.UNKNOWN, Tone.ACTION)
            head = [l for l in rows
                    if l.tone in urgent or (l.depth == 0 and l.tone != Tone.MUTED)]
            rest = [l for l in rows if l not in head]
            tone_here = panel.summary_tone if panel.summary_tone in Tone.ALL else Tone.PLAIN
            chip = (f"<span class='chip {tone_here}'>{_escape(panel.summary)}</span>"
                    if panel.summary else "")
            if panel.unknown:
                chip += f"<span class='count unknown'>{len(panel.unknown)}</span>"
            out.append(f"<section><div class=head><h2>{_escape(panel.title)}</h2>{chip}</div><ul>")
            for line in head:
                out.append(_row(line))
            for item in panel.unknown:
                out.append(f"<li class='unknown d0'><span class=k>{UNKNOWN}</span>"
                           f"<span class=v>{_escape(item)}</span></li>")
            if not rows and not panel.unknown:
                out.append("<li class='unknown d0'><span class=v>nothing to read</span></li>")
            out.append("</ul>")
            if rest:
                out.append(f"<details><summary>{len(rest)} more</summary><ul>")
                out.extend(_row(line) for line in rest)
                out.append("</ul></details>")
            out.append("</section>")
    out.append("</main><footer>Every answer here is delegated to the module that owns it. "
               "This page authorises nothing, schedules nothing, wakes nothing and stores "
               "nothing; deleting it breaks no checker.</footer></body></html>")
    return "\n".join(out)


def _row(line: "Line") -> str:
    safe = line.tone if line.tone in Tone.ALL else Tone.PLAIN
    key = f"<span class=k>{_escape(line.label)}</span>" if line.label else ""
    return (f"<li class='{safe} d{min(line.depth, 2)}'>{key}"
            f"<span class=v>{_escape(line.text)}</span></li>")


def _verdict_tone(headline: str) -> str:
    """The tone of the headline, from the state name the owner produced."""
    import continuation

    S = continuation.State
    first = (headline or "").split(":")[0].strip()
    return {
        S.SILENT_IDLE: Tone.BAD, S.RECOVERY_REQUIRED: Tone.BAD,
        S.BLOCKED_ON_HUMAN: Tone.WARN, S.BLOCKED_ON_CAPACITY: Tone.WARN,
        S.COMPLETED_NOT_CONSUMED: Tone.WARN,
        S.WAITING_ON_IDENTIFIED_JOB: Tone.PLAIN, S.ACTIONABLE_WORK_READY: Tone.PLAIN,
        S.TERMINAL: Tone.GOOD, UNKNOWN: Tone.UNKNOWN,
    }.get(first, Tone.UNKNOWN)


def _guarded(work, *args, default):
    """Run a panel's own work, or report that it could not be done.

    **A projection may not raise.** `derive()` returns `RECOVERY_REQUIRED` for a
    record with an unreadable deadline, and this module then raised `ValueError`
    reaching the same field for its own display — so the view of a broken record
    was no view at all, which is the one state a reader most needs to see. Found
    by an independent reader.
    """
    try:
        return work(*args)
    except Exception as exc:
        return f"{default}: {type(exc).__name__}: {exc}"[:400]


def _report_or_none(record, record_path: Path):
    if record is None:
        return None
    try:
        import continuation

        return continuation.derive(record, relative_to=Path(record_path).parent)
    except Exception:
        return None


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
    parser.add_argument("--html", action="store_true",
                        help="render as a self-contained page on stdout instead of text")
    parser.add_argument("--title", default="Runtime Pack — projection")
    args = parser.parse_args(argv)

    view = project(args.project_root, contract=args.contract,
                   continuation_record=args.continuation,
                   capacity_observation=args.capacity)
    print(render_html(view, args.title) if args.html else view.render())
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
