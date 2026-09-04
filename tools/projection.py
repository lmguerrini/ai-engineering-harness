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
import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Cell", "Line", "Panel", "Projection", "Tone", "project", "render_html"]

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
        # COERCED HERE, NOT AT EVERY CALL SITE. `{"capability": 7}` loads and
        # then made the view raise `TypeError` while joining the attention
        # strip — the third shape of *a saved record the projection cannot
        # render* found by an independent reader, after two were closed one
        # field at a time. A record is untrusted input and a `Line` is where
        # every panel's text becomes text, so this is the boundary. Whatever
        # the record holds, the view says what it holds.
        self.text = self.text if isinstance(self.text, str) else str(self.text)
        self.label = self.label if isinstance(self.label, str) else str(self.label)


@dataclass
class Cell:
    """One reading as a FIGURE rather than as a sentence.

    A cell is the compact form of a fact its panel **also says in full**, and
    the panel that knows the fact is the one that makes it. Two rules hold it
    there:

    * **It computes nothing.** Every number in a cell was already in the record
      or in the answer of the module that owns the question. A cell that
      derived one would be the page reaching a second opinion about the thing
      it is a reading of.
    * **It never stands alone.** The line stays where it was, so no reading
      exists only as a figure — otherwise the page and the text view would be
      showing different things, and the page would be the one nobody could
      check. `test_a_cell_says_nothing_its_panel_does_not_say` is that bound.
    """

    label: str
    value: str
    tone: str = Tone.PLAIN
    #: ``(used, ceiling)`` — set ONLY where a ceiling was actually declared. A
    #: meter needs a denominator, and a bar drawn against a guessed one is
    #: fabricated precision in the one place a reader trusts a picture rather
    #: than reading the number.
    share: "tuple | None" = None
    #: What a full bar MEANS. `consumption` — something is being spent, and full
    #: is a warning. `coverage` — something is being covered, and full is good.
    #: `age` — time since, against the threshold at which it goes stale.
    #: A smaller second value: an age, a unit, a subject.
    note: str = ""
    #: ``situation`` for the command band a reader takes in first, ``telemetry``
    #: for the instrument row under it.
    band: str = "telemetry"
    #: What a full bar MEANS. `consumption` — something is being spent, and full
    #: is a warning. `coverage` — something is being covered, and full is good.
    #: `age` — time since, against the threshold at which it goes stale.
    #: `deadline` — elapsed against a declared limit, and past it is a defect.
    #:
    #: **The same picture with the opposite meaning** is how a dashboard tells a
    #: reader that an exhausted budget is fine because it looks like complete
    #: coverage. A bar with no sense is drawn neutrally.
    sense: str = ""
    #: WHAT KIND of thing this is about — ``job``, ``output``, ``audit``,
    #: ``capacity``, ``budget``, ``evidence``. A view that collects every job
    #: across every project needs to recognise one without matching on the text
    #: of its label, which is prose and changes.
    kind: str = ""
    #: Further named fields, for a table that has columns. Same rule as
    #: `value`: each one restates something the panel already says.
    fields: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.tone not in Tone.ALL:
            raise ValueError(f"unknown tone {self.tone!r}")
        if self.band not in ("situation", "telemetry", "identity"):
            raise ValueError(f"unknown band {self.band!r}")
        if self.sense not in ("", "consumption", "coverage", "age", "deadline"):
            raise ValueError(f"unknown sense {self.sense!r}")
        if self.share is not None:
            used, ceiling = self.share
            if not isinstance(used, (int, float)) or not isinstance(ceiling, (int, float)):
                raise ValueError(f"a share is two numbers, not {self.share!r}")
            # A DENOMINATOR OF ZERO IS NOT A DENOMINATOR. Nothing is drawn
            # against it: the value is still said, and the picture is left out
            # rather than divided by nothing.
            import math

            # FINITE, TOO. Zero, negative and NaN were refused and infinity was
            # not, so a wait declaring an unbounded deadline drew a bar against
            # a limit that does not exist — at 0%, which reads as *just
            # started*. Found by an independent reader.
            if (ceiling <= 0 or used < 0 or not math.isfinite(used)
                    or not math.isfinite(ceiling)):
                self.share = None
        for name in ("label", "value", "note", "kind"):
            value = getattr(self, name)
            if not isinstance(value, str):
                setattr(self, name, str(value))
        self.fields = {str(k): str(v) for k, v in dict(self.fields or {}).items()}


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
    #: The same facts as figures, for the console's first two bands. Adding
    #: one here does not remove the line it restates.
    cells: list = field(default_factory=list)
    #: A panel whose lines are a VOCABULARY rather than findings. The state
    #: legend marks the current state urgently, correctly, and hoisting that into
    #: the attention strip restates the headline in different words — noise in
    #: the one place that must not have any.
    legend: bool = False

    def say(self, text: str, tone: str = Tone.PLAIN, label: str = "", depth: int = 0) -> None:
        self.lines.append(Line(text, tone, label, depth))

    def figure(self, label: str, value: str, tone: str = Tone.PLAIN, *,
               share=None, note: str = "", band: str = "telemetry", kind: str = "",
               sense: str = "", **fields: str) -> None:
        """Say a fact this panel already says, as a figure. Never instead of it."""
        self.cells.append(Cell(label, value, tone, share, note, band, sense, kind,
                               dict(fields)))

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
        #
        # SCOPED TO THE PANEL THAT OWNS IT. Two panels label a line `state`:
        # the coordinator's, which the headline repeats, and the pack's, which
        # is a different fact about a different thing. Excluding the word
        # excluded both, so `state: IN_PROGRESS` — the reading that says this
        # release may not be adopted — was hoisted nowhere. Found by writing
        # down what makes a section safe to fold and checking the page.
        said_already = {"state"}
        found = []
        for panel in self.panels:
            if panel.legend:
                continue
            for line in panel.rows():
                if line.label in said_already and panel.group == "now":
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
    def situation(self) -> "list[Cell]":
        """The level-1 figures, in the order their panels were built."""
        return [c for p in self.panels for c in p.cells if c.band == "situation"]

    @property
    def telemetry(self) -> "list[Cell]":
        """The level-2 figures. Same rule: made by the panel that owns the fact."""
        return [c for p in self.panels for c in p.cells if c.band == "telemetry"]

    @property
    def identity(self) -> "list[Cell]":
        """What this project and this pack ARE. Read by the status bar and by
        the console's identity view, so neither has to recognise a panel by its
        title — which is prose, and moves."""
        return [c for p in self.panels for c in p.cells if c.band == "identity"]

    def figure_of(self, kind: str) -> "list[Cell]":
        """Every figure of one kind, in the order the panels were built."""
        return [c for p in self.panels for c in p.cells if c.kind == kind]

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
            if not problems:
                panel.say("pin verifies", Tone.GOOD, label="pin")
            elif any(p.startswith(pack_pin.UNESTABLISHED) for p in problems):
                # Could not be checked is not the same as checked and wrong, and
                # a projection that renders the first as the second is the fail-
                # closed-but-mislabelled shape this pack refuses elsewhere.
                panel.say(next(p for p in problems if p.startswith(pack_pin.UNESTABLISHED)),
                          Tone.UNKNOWN, label="pin")
            else:
                panel.say(f"PIN DOES NOT VERIFY: {problems[0]}", Tone.BAD, label="pin")
        except Exception as exc:
            panel.unknown.append(f"the pin could not be checked: {exc}")
    intent = getattr(contract, "publication_intent", None)
    panel.lines.append(f"publication intent: {intent or 'not declared'}")
    pinned = (f"{pack.get('version_adopted', UNKNOWN)} at "
              f"{str(pack.get('sha_adopted', UNKNOWN))[:12]} "
              f"state {pack.get('state_adopted', UNKNOWN)}")
    verifies = next((l for l in panel.rows() if l.text.startswith("pin ")
                     or l.text.startswith("PIN ")), None)
    panel.figure("pin", pinned,
                 Tone.BAD if verifies is not None and "DOES NOT" in verifies.text
                 else (Tone.GOOD if verifies is not None else Tone.UNKNOWN),
                 note=verifies.text if verifies is not None else UNKNOWN,
                 band="identity", kind="pin",
                 repository=str(contract.repo_path or UNKNOWN),
                 publication=str(intent or "not declared"))
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
        expired = "EXPIRED" in deadline
        panel.say(deadline,
                  Tone.BAD if expired else
                  (Tone.MUTED if "no deadline" in deadline else Tone.PLAIN), depth=1)
        # The same job as a lifecycle cell. Its note is the tail of the deadline
        # line above — a slice of a string this panel already produced, not a
        # second reading of the clock.
        elapsed = _guarded(_deadline_share, wait, default=None)
        panel.figure(f"job {observation.job_id}", mark,
                     Tone.BAD if expired else
                     {"COMPLETE": Tone.GOOD, UNKNOWN: Tone.UNKNOWN}.get(mark, Tone.PLAIN),
                     note=deadline.rpartition(" — ")[2] if " — " in deadline else "",
                     band="situation", kind="job",
                     share=elapsed if isinstance(elapsed, tuple) else None,
                     sense="deadline" if isinstance(elapsed, tuple) else "",
                     job=observation.job_id, expects=wait.expects,
                     owner=wait.executor or UNKNOWN,
                     subject=wait.subject_revision[:12] or UNKNOWN,
                     obligation=wait.obligation or wait.job_id,
                     deadline=deadline,
                     progress=_guarded(_progress_line, wait, observation,
                                       default=f"{UNKNOWN} — could not be dated"))
    for label, values, tone in (
            ("unconsumed results", report.unconsumed, Tone.WARN),
            ("waits nobody can observe", report.unobservable, Tone.UNKNOWN),
            ("PAST THE DECLARED DEADLINE", report.expired, Tone.BAD),
            ("obligations held by more than one wait", report.duplicated, Tone.BAD),
            ("superseded waits, retire them", report.superseded, Tone.WARN),
            ("blocked", report.blockers, Tone.WARN)):
        # ONE LINE EACH. Six categories comma-joined into six lines put four
        # blockers, their HITL rows and their scopes into a single run-on line
        # a reader has to parse — in the panel that exists to say what is in
        # the way. Same facts, same words, one per line.
        for value in values:
            panel.say(value, tone, label=label)
    # SAID WHETHER OR NOT THERE IS ONE. An absent blocker line and a record
    # nobody has declared a blocker on look identical, and *is a person needed*
    # is the first question a reader of a long run asks.
    panel.say(", ".join(report.blockers) if report.blockers else "none declared",
              Tone.WARN if report.blockers else Tone.PLAIN, label="human intervention")
    panel.figure("intervention", ", ".join(report.blockers) if report.blockers
                 else "none declared",
                 Tone.WARN if report.blockers else Tone.PLAIN, band="situation",
                 kind="intervention")
    if report.actionable:
        panel.say(f"{len(report.actionable)} item(s)", label="authorised and outstanding")
        panel.figure("outstanding", f"{len(report.actionable)} item(s)", band="situation",
                     kind="outstanding")
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
    if declared:
        # WHICH candidate. The panel compared every audit against this and never
        # printed it, so a reader could see *the candidate* and not what it was.
        # Found by extending the figure invariant to a table's columns.
        panel.say(declared, Tone.MUTED, label="the candidate this record declares")
    audits = [w for w in record.waits if w.subject_revision or w.subject_digest]
    if not audits:
        panel.say("no outstanding job states a subject revision", Tone.MUTED)
        return panel
    for wait in audits:
        short = wait.subject_revision[:12]
        # WHO RAN IT. An audit's verdict is only as independent as its executor,
        # and this panel named the subject and not the reader.
        panel.say(wait.executor or UNKNOWN,
                  Tone.MUTED if wait.executor else Tone.UNKNOWN, label="executor", depth=1)
        if not declared:
            panel.say(f"{short or UNKNOWN} — cannot be compared", Tone.UNKNOWN, label=wait.job_id)
            # `kind` WAS MISSING HERE. An audit whose subject cannot be
            # compared is still an audit in flight, and without the kind every
            # view that collects audits counted it as a project with none —
            # so the one audit nobody could place looked like no audit at all.
            # Found by an independent reader of the instruments.
            panel.figure(f"audit {wait.job_id}", "cannot be compared", Tone.UNKNOWN,
                         note=short, band="situation", kind="audit", audit=wait.job_id,
                         subject=short or UNKNOWN, candidate=UNKNOWN,
                         owner=wait.executor or UNKNOWN)
        elif short and short in declared:
            panel.say(f"{short} — the candidate", Tone.GOOD, label=wait.job_id)
            panel.figure(f"audit {wait.job_id}", "the candidate", Tone.GOOD, note=short,
                         band="situation", kind="audit", audit=wait.job_id,
                         subject=short or UNKNOWN, candidate=declared or UNKNOWN,
                         owner=wait.executor or UNKNOWN)
        else:
            panel.figure(f"audit {wait.job_id}", "NOT the candidate", Tone.BAD, note=short,
                         band="situation", kind="audit", audit=wait.job_id,
                         subject=short or UNKNOWN, candidate=declared or UNKNOWN,
                         owner=wait.executor or UNKNOWN)
            panel.say(f"{short or UNKNOWN} — NOT the candidate this record declares. Findings "
                      f"from it describe a different tree", Tone.BAD, label=wait.job_id)
    return panel


def _deadline_share(wait):
    """How far through its declared deadline a wait is, as ``(elapsed, limit)``.

    `None` when there is no deadline or no readable declaration time — a bar
    drawn against a limit nobody set would be a picture of a rule that does not
    exist. Past the limit the elapsed value is held at it, so the bar is full
    rather than overflowing, and the TONE is what says it expired.
    """
    import continuation
    from datetime import datetime, timezone

    if wait.not_beyond_seconds is None:
        return None
    declared = continuation._moment(wait.declared_at) if wait.declared_at else None
    limit = float(wait.not_beyond_seconds)
    if declared is None or limit <= 0:
        return None
    age = (datetime.now(timezone.utc) - declared).total_seconds()
    return (min(max(age, 0.0), limit), limit)


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
            panel.figure(counter, UNKNOWN, Tone.UNKNOWN, note="not a position this view can read")
            continue
        used, ceiling = position.get("used"), position.get("ceiling")
        left = (ceiling - used) if isinstance(used, int) and isinstance(ceiling, int) else UNKNOWN
        spent = isinstance(left, int) and left <= 0
        if isinstance(used, int) and isinstance(ceiling, int):
            text = f"{used}/{ceiling} used, {left} remaining"
        elif isinstance(used, int):
            # NOT `3/None`. A missing ceiling printed as `None` reads like a
            # value, and a reader scanning a strip of ratios would take it for
            # one. A counter with no ceiling has been counted and not bounded.
            text = f"{used} used against no declared ceiling"
        else:
            text = f"{UNKNOWN}: this counter records {used!r} used and {ceiling!r} as a ceiling"
        if position.get("authorised_by"):
            text += f"  (raised by {position['authorised_by']})"
        panel.say(text, Tone.WARN if spent else Tone.PLAIN, label=counter)
        if isinstance(used, int) and isinstance(ceiling, int):
            panel.figure(counter, f"{used}/{ceiling}", Tone.WARN if spent else Tone.PLAIN,
                         share=(used, ceiling), note=f"{left} remaining", kind="budget",
                         sense="consumption")
        elif isinstance(used, int):
            # No denominator, so no bar. A meter here would be a picture of a
            # fraction nobody declared.
            panel.figure(counter, f"{used} used", note="no declared ceiling", kind="budget")
        else:
            panel.figure(counter, UNKNOWN, Tone.UNKNOWN, kind="budget")
    # THE READINGS A LONG RUN NEEDS, listed whether or not the record carries
    # them. An absent key simply did not appear before, which makes *nobody
    # declared this* and *this is fine* look identical — the one thing this
    # projection may never do. Named here so absence is a visible UNKNOWN.
    for name in ("candidate", "suite", "gates", "latest_audit", "closure",
                 "recurrence_classes", "real_consumers", "adapters", "continuation",
                 "public_safety", "evolution_candidates"):
        if name in record.evidence:
            panel.say(str(record.evidence[name]), label=name)
            panel.figure(name.replace("_", " "), str(record.evidence[name]), kind="evidence")
        else:
            panel.figure(name.replace("_", " "), UNKNOWN, Tone.UNKNOWN, kind="evidence",
                         note=f"no {name.replace(chr(95), chr(32))}")
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
        panel.figure("reading age", UNKNOWN, Tone.UNKNOWN, band="situation", kind="freshness")
        return panel
    age = (datetime.now(timezone.utc) - written).total_seconds()
    panel.lines.append(f"record written {age / 60:.0f} min ago ({record.updated_at})")
    # The bar is age against the hour at which this record is called stale —
    # a threshold the panel already applies, not a horizon invented here.
    panel.figure("reading age", f"{age / 60:.0f} min ago",
                 Tone.WARN if age > 3600 else Tone.PLAIN,
                 share=(min(age, 3600), 3600), sense="age",
                 note="STALE" if age > 3600 else "", band="situation", kind="freshness",
                 # THE AGE AS A NUMBER. A caller comparing `9 min ago` with
                 # `120 min ago` as text gets the fresher one, which is how the
                 # console's `oldest reading` reported a nine-minute record
                 # while a two-hour one sat beside it marked STALE. Found by an
                 # independent reader.
                 minutes=f"{age / 60:.0f}")
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
    panel.figure("pack", str(document.get("version", UNKNOWN)),
                 Tone.GOOD if state == "QUALIFIED_AND_FROZEN" else Tone.WARN,
                 note=str(state), band="identity", kind="pack",
                 version=str(document.get("version", UNKNOWN)), state=str(state),
                 digest=f"{str(document.get('tree_digest_sha256', UNKNOWN))[:16]}…")
    panel.summary = f"{document.get('version', UNKNOWN)} {state}"
    panel.summary_tone = Tone.GOOD if state == "QUALIFIED_AND_FROZEN" else Tone.WARN
    # SAID IN BOTH DIRECTIONS, under a label. It was said only when the answer
    # was no, so the positive reading was unreachable — and the contract's
    # marker for it, the bare word `ADOPTABLE`, matched the sentence that
    # denies it. A marker that matches the opposite state discriminates
    # nothing, and an independent reader demonstrated exactly that.
    panel.say("this state may be pinned by a project" if state == "QUALIFIED_AND_FROZEN"
              else "NO — only QUALIFIED_AND_FROZEN may be pinned by a project",
              Tone.GOOD if state == "QUALIFIED_AND_FROZEN" else Tone.WARN,
              label="adoptability", depth=1)
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
        # WHERE THE ARTIFACTS ARE. The panel classified a partial recovery and
        # never said the root, so *recover the partial output before any retry*
        # sent a reader to the record to find out where. Third place the column
        # invariant found the table showing what the panel does not say.
        panel.say(str(root), Tone.MUTED, label="output root", depth=1)
        expected = getattr(contract, "expected_chunks", None)
        written = len(getattr(report, "complete", ()) or ())
        panel.figure(f"output {wait.job_id}", report.state,
                     {task_output.RecoveryState.COMPLETED_WITH_DURABLE_OUTPUT: Tone.GOOD,
                      task_output.RecoveryState.UNKNOWN: Tone.UNKNOWN,
                      task_output.RecoveryState.FAILED_WITH_PARTIAL_DURABLE_OUTPUT: Tone.WARN,
                      task_output.RecoveryState.FAILED_BEFORE_USEFUL_OUTPUT: Tone.WARN}
                     .get(report.state, Tone.PLAIN), note=str(wait.task_id), kind="output",
                     share=(written, expected) if isinstance(expected, int) and expected > 0
                     else None,
                     sense="coverage" if isinstance(expected, int) and expected > 0 else "",
                     job=wait.job_id, task=str(wait.task_id), root=str(root),
                     examined=report.examined.summary())
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
        panel.figure("capacity", UNKNOWN, Tone.UNKNOWN, note="no window is known",
                     band="situation", kind="capacity")
        return panel
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        pools = raw.get("pools") or []
    except Exception as exc:
        panel.unknown.append(f"the capacity observation could not be read: {exc}")
        return panel

    import capacity

    if not pools:
        # AN EMPTY POOL LIST IS AN ANSWER, and it was reaching the panel as an
        # unknown with no figure — so the capacity instrument counted neither a
        # measured nor an unmeasured window and reported nothing outstanding
        # about a project whose own table said UNKNOWN.
        panel.unknown.append("the capacity observation declares no pools")
        panel.figure("capacity", UNKNOWN, Tone.UNKNOWN, note="declares no pools",
                     band="situation", kind="capacity")
    for entry in pools:
        try:
            pool = capacity.Pool(**entry)
        except Exception as exc:
            panel.unknown.append(f"a pool declaration could not be read: {exc}")
            continue
        # `340.0 requests` is a float printed as a measurement. The pool model
        # holds a number; this renders it as the count it is.
        remaining = (f"{pool.remaining:g}" if pool.known and isinstance(pool.remaining, float)
                     else (pool.remaining if pool.known else UNKNOWN))
        panel.lines.append(
            f"{pool.pool_id} [{pool.kind}/{pool.window}]: {remaining} {pool.unit} remaining, "
            f"{pool.active_workers} active, resets {pool.resets_at or UNKNOWN}, "
            f"observed {pool.observed_at or UNKNOWN}"
        )
        panel.figure(f"capacity {pool.pool_id}", f"{remaining} {pool.unit}",
                     Tone.PLAIN if pool.known else Tone.UNKNOWN,
                     note=f"{pool.active_workers} active", band="situation", kind="capacity",
                     pool=pool.pool_id, provider=pool.kind, window=pool.window,
                     resets=pool.resets_at or UNKNOWN, observed=pool.observed_at or UNKNOWN)
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
/* TERMINAL MISSION CONTROL
   ------------------------------------------------------------------
   Three layers, and the reason for each.

   LEVEL 1 — COMMAND. What is happening, whether a person is needed, what
   happens next. Given room, and never collapsed.
   LEVEL 2 — TELEMETRY. Established figures AS figures: meters, counts, status
   cells. Dense on purpose, because a strip a reader must read a sentence at a
   time is a strip they stop reading.
   LEVEL 3 — FORENSICS. Prose, paths, provenance, vocabulary. Behind a
   disclosure wherever collapsing it cannot hide uncertainty.

   And two colour layers, kept apart.

   SEMANTIC tokens say what a fact IS — bad, warn, unknown, good, action.
   Same hue family in every theme, because a state that reads differently
   under a theme is a theme that changed the meaning.

   THEME tokens say what the surface looks like — ground, panel, rule, ink,
   and one accent. A theme may move all of those and none of the semantics.  */

:root{
  color-scheme:dark;

  /* ---- the presentation substrate -------------------------------------
     Every size, space and family the console draws with is a variable, so
     the Settings view can move it at runtime without a second stylesheet
     and without touching a single reading. A lens moves colour; an operator
     moves the rest; neither moves a meaning. */
  --ui:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,"Helvetica Neue",sans-serif;
  --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,"JetBrains Mono","DejaVu Sans Mono",
         Consolas,monospace;
  --font:var(--mono);
  --fs:12.5px;            /* body and telemetry values */
  --fs-state:30px;        /* the one state a reader looks for first */
  --fs-micro:8.5px;       /* uppercase field labels */
  --fs-forensic:11.5px;   /* paths, provenance, raw messages */
  --lh:1.5;
  --pad-x:16px;           /* the page's horizontal rhythm */
  --pad-y:2px;            /* the vertical rhythm inside a list */
  --gap:1px;              /* between zones */
  --rail:216px;

  /* ---- the DEFAULT lens: MONOCHROME ------------------------------------
     The founder reviewed five lenses against real states and chose this one,
     so it is what the release ships rather than what it offers. Black ground,
     graphite surfaces, white and grey type — and colour only where an
     operator has to act on it: a defect, a warning, an unestablished reading,
     an established good state. Everything structural is neutral, so the four
     places carrying hue are the four places worth looking at. */

  --ground:#000; --panel:#0e0d0c; --panel-2:#171614; --panel-3:#1f1d1a;
  --rule:#282521; --rule-strong:#3b3831;
  --ink:#f5f2ed; --dim:#b0aba3; --faint:#807b73;
  --accent:#f0c68a; --select:#2b2620;
  --bad:#f2635c; --warn:#c9821f; --unknown:#7d8f9c; --good:#54b98a;
  --action:#f0c68a;
  --bad-bg:#1e100e; --warn-bg:#1d1408; --unknown-bg:#141b21; --good-bg:#0b1d16;
  --action-bg:#241d13;
}

:root[data-theme="terminal"]{
  --ground:#09090a; --panel:#111112; --panel-2:#171718; --panel-3:#1d1d1f;
  --rule:#252528; --rule-strong:#37373d;
  --ink:#e7e7e9; --dim:#9d9da4; --faint:#75757d;
  --accent:#4cc9f0; --select:#12303c;

  /* ---- semantics -------------------------------------------------------
     Four answers, four hues, in every lens. UNKNOWN is STEEL: a desaturated
     blue-grey that reads as *not established* rather than as an action, and
     that no lens turns into the accent. It was violet, which collided with
     nothing and looked like decoration; the founder's review called it out
     and the whole system is free of purple now. */
  --bad:#ff6b63; --warn:#f0b429; --unknown:#7d8f9c; --good:#3ecf8e; --action:#4cc9f0;
  --bad-bg:#26100e; --warn-bg:#241c07; --unknown-bg:#12202a; --good-bg:#08251b;
  --action-bg:#0a2430;
}

}

:root[data-theme="matrix"]{
  /* MATRIX — a green-phosphor console, and unmistakably one. The ground is
     nearly black with green in it, every structural surface and rule is a
     further step of the same green, and the neutral type is green.
     The semantics are NOT: a defect is red, a warning is amber, an
     unestablished reading is steel. A console where everything is green is a
     console where nothing means anything. */
  --ground:#030702; --panel:#071206; --panel-2:#0b1c09; --panel-3:#10270d;
  --rule:#1c4a16; --rule-strong:#2b7524;
  --ink:#8df56a; --dim:#4fbf3a; --faint:#38912a;
  --accent:#62f542; --select:#0d3a09;
  --bad:#ff6a5e; --warn:#ffc33f; --unknown:#7d8f9c; --good:#23a52a;
  --action:#62f542;
  --bad-bg:#25100c; --warn-bg:#221b06; --unknown-bg:#0a2029; --good-bg:#0a2c08;
  --action-bg:#0c3208;
}

:root[data-theme="minimal"]{
  /* MINIMAL — the calm one. Same information, more room: black, almost no
     rules, hierarchy carried by size and space rather than by boxes. It is
     deliberately LESS dense than monochrome, which is the difference between
     the two — one is a precision operations console, the other is a
     workspace to sit in front of for an hour. */
  --ground:#000; --panel:#0a0908; --panel-2:#100e0d; --panel-3:#161413;
  --rule:#1f1c19; --rule-strong:#2f2b27;
  --ink:#efebe5; --dim:#a6a099; --faint:#767069;
  --accent:#d8cfc2; --select:#1d1a16;
  --bad:#ef6f68; --warn:#c98a2f; --unknown:#7d8f9c; --good:#54bd8d;
  --action:#d8cfc2;
  --bad-bg:#1a0e0d; --warn-bg:#191307; --unknown-bg:#121a1f; --good-bg:#091b14;
  --action-bg:#191614;
  --lh:1.65; --pad-y:4px; --fs-micro:9px; --gap:1px;
}

:root[data-theme="futuristic"]{
  /* FUTURISTIC — a research console: neutral cool ground, hairline
     structure, and one ice-blue used only for interaction. Depth from three
     close surfaces rather than from shadow. No HUD, no glow, no purple. */
  --ground:#06080a; --panel:#0d1114; --panel-2:#12171c; --panel-3:#181f25;
  --rule:#1e262d; --rule-strong:#2e3c47;
  --ink:#dde7ee; --dim:#93a4b1; --faint:#6b7d8b;
  --accent:#67e8f9; --select:#0d2f38;
  --bad:#ff6f85; --warn:#ffc75c; --unknown:#7d8f9c; --good:#2fcf90;
  --action:#67e8f9;
  --bad-bg:#280f16; --warn-bg:#261e08; --unknown-bg:#0f2029; --good-bg:#052a23;
  --action-bg:#062731;
}

@media(prefers-color-scheme:light){
  :root:not([data-theme]){
    color-scheme:light;
    --ground:#eceff2; --panel:#fff; --panel-2:#f5f7f9; --panel-3:#eceff3;
    --rule:#d6dade; --rule-strong:#b6bcc4;
    --ink:#0e1114; --dim:#525a63; --faint:#79828c;
    --accent:#1a44a0; --select:#dde6f8;
    --bad:#a81f16; --warn:#7a4e00; --unknown:#33707d; --good:#0e6145;
    --action:#1a44a0;
    --bad-bg:#fcecea; --warn-bg:#fbf3e0; --unknown-bg:#e6f1f7; --good-bg:#e6f5ef;
    --action-bg:#e7f2f8;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
font:var(--fs)/var(--lh) var(--font);font-variant-numeric:tabular-nums;
-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
b,i,em,u{font-style:normal;font-weight:inherit;text-decoration:none}

/* ============ IDENTITY BAR — what this is, in one line ================ */
.bar{display:flex;flex-wrap:wrap;align-items:center;gap:0 20px;
padding:6px var(--pad-x);background:var(--panel-2);border-bottom:1px solid var(--rule-strong);
font-size:var(--fs-forensic);letter-spacing:.01em}
.bar b{color:var(--faint);text-transform:uppercase;letter-spacing:.12em;font-size:var(--fs-micro);
margin-right:6px}
.bar span{color:var(--dim)}
.bar .id{color:var(--accent);font-weight:600}

/* ============ LEVEL 1 — COMMAND ======================================= */
header{border-bottom:1px solid var(--rule-strong)}
h1{margin:0;padding:9px var(--pad-x) 0;font-size:var(--fs-micro);letter-spacing:.3em;text-transform:uppercase;
color:var(--faint);font-weight:600}

.cmd{display:grid;grid-template-columns:1fr;gap:14px;padding:10px var(--pad-x) 14px;
background:var(--panel);border-left:3px solid var(--dim)}
@media(min-width:1000px){.cmd{grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);
gap:22px;align-items:start}}
.v-bad{border-left-color:var(--bad)} .v-warn{border-left-color:var(--warn)}
.v-good{border-left-color:var(--good)} .v-unknown{border-left-color:var(--unknown)}

.state{font-size:var(--fs-state);line-height:1.08;font-weight:700;letter-spacing:-.02em;margin:2px 0 6px;
word-break:break-word}
.v-bad .state{color:var(--bad)} .v-warn .state{color:var(--warn)}
.v-good .state{color:var(--good)} .v-unknown .state{color:var(--unknown)}
.said{font-size:var(--fs);color:var(--dim);max-width:74ch;margin:0}

.next{margin-top:12px;padding:9px 12px;background:var(--action-bg);
border:1px solid var(--action);border-left-width:3px}
.next b{display:block;font-size:var(--fs-micro);letter-spacing:.18em;color:var(--action);margin-bottom:3px}
.next span{font-size:calc(var(--fs) + 2px);font-weight:600;color:var(--ink);word-break:break-word}

/* the situation grid: level-1 readings as cells, never as sentences */
.sit{display:grid;grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:1px;
background:var(--rule);border:1px solid var(--rule)}
.sit>div{background:var(--panel-2);padding:6px 9px;min-width:0}
.sit i{display:block;font-size:var(--fs-micro);letter-spacing:.14em;text-transform:uppercase;
color:var(--faint);margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sit em{display:block;font-size:var(--fs);font-weight:700;color:var(--ink);
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sit u{display:block;font-size:var(--fs-forensic);color:var(--dim);margin-top:1px;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sit .good em{color:var(--good)} .sit .warn em{color:var(--warn)}
.sit .bad em{color:var(--bad)} .sit .unknown em{color:var(--unknown)}
.sit .action em{color:var(--action)}
.sit .bad{background:var(--bad-bg)} .sit .unknown{background:var(--unknown-bg)}
.sit .warn em::before{content:"▲ "} .sit .bad em::before{content:"✕ "}
.sit .unknown em::before{content:"? "} .sit .good em::before{content:"✓ "}
.sit-head{display:flex;align-items:baseline;gap:8px;margin-bottom:5px}
.sit-head b{font-size:var(--fs-micro);letter-spacing:.18em;text-transform:uppercase;color:var(--faint)}
.sit-head span{font-size:var(--fs-forensic);color:var(--dim)}

/* attention: never collapsed away, always counted */
.attn{background:var(--panel-2);border-top:1px solid var(--rule)}
.attn>summary{cursor:pointer;padding:7px var(--pad-x);font-size:var(--fs-micro);letter-spacing:.16em;
text-transform:uppercase;color:var(--dim);list-style:none;user-select:none}
.attn>summary::-webkit-details-marker{display:none}
.attn>summary::before{content:"▸ "} .attn[open]>summary::before{content:"▾ "}
.attn ul{padding:0 0 7px}
.attn li{font-size:var(--fs);padding-top:2px;padding-bottom:2px}
.count{display:inline-block;min-width:16px;text-align:center;padding:0 6px;
font-size:var(--fs-forensic);font-weight:700;margin-left:5px;letter-spacing:0;border:1px solid}
.count.bad{background:var(--bad-bg);color:var(--bad)}
.count.warn{background:var(--warn-bg);color:var(--warn)}
.count.unknown{background:var(--unknown-bg);color:var(--unknown)}
.count.good{background:var(--good-bg);color:var(--good)}

/* ============ LEVEL 2 — TELEMETRY ===================================== */
.strip{display:grid;grid-template-columns:repeat(auto-fill,minmax(163px,1fr));gap:1px;
background:var(--rule);border-bottom:1px solid var(--rule-strong)}
.fact{background:var(--panel);padding:6px 10px 7px;min-width:0}
.fact i{display:block;font-size:var(--fs-micro);letter-spacing:.13em;text-transform:uppercase;
color:var(--faint);margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fact em{font-size:var(--fs);font-weight:700;color:var(--ink);display:block;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fact u{font-size:var(--fs-forensic);color:var(--faint);display:block;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fact.good em{color:var(--good)} .fact.warn em{color:var(--warn)}
.fact.bad em{color:var(--bad)} .fact.unknown em{color:var(--unknown)}
.fact.warn{box-shadow:inset 2px 0 0 var(--warn)} .fact.bad{box-shadow:inset 2px 0 0 var(--bad)}
.fact.unknown{box-shadow:inset 2px 0 0 var(--unknown)}
.fact.good{box-shadow:inset 2px 0 0 var(--good)}
/* ---- the instruments -------------------------------------------------------
   A bar is drawn only where a denominator exists, and its colour comes from
   what the fraction MEANS. Consumption fills toward a warning; coverage fills
   toward an established good; an age fills toward stale; a deadline fills
   toward expired. The exact value is always beside it — a picture is never the
   only place a number appears. */
.meter{display:block;height:3px;background:var(--rule-strong);margin-top:4px;overflow:hidden}
.meter i{display:block;height:100%;background:var(--accent);min-width:1px}
.meter i.warn{background:var(--warn)} .meter i.bad{background:var(--bad)}
.meter i.good{background:var(--good)} .meter i.unknown{background:var(--unknown)}
.meter i.plain,.meter i.action{background:var(--dim)}
/* an age and a deadline carry the threshold they are measured against */
.meter.age,.meter.deadline{position:relative}
.meter.age::after,.meter.deadline::after{content:"";position:absolute;right:0;top:-1px;
bottom:-1px;width:1px;background:var(--ink);opacity:.55}

/* a categorical distribution: one segment per answer, none of them omitted */
.dist{display:block;height:6px;display:flex;gap:1px;margin:5px 0 4px;background:var(--rule)}
.dist span{display:block;min-width:2px}
.dist .bad{background:var(--bad)} .dist .warn{background:var(--warn)}
.dist .unknown{background:var(--unknown)} .dist .good{background:var(--good)}
.dist .plain{background:var(--dim)} .dist .action{background:var(--accent)}
.legend{display:flex;flex-wrap:wrap;gap:2px 12px;font-size:var(--fs-forensic);color:var(--dim)}
.legend span{white-space:nowrap;display:flex;align-items:center;gap:5px}
.legend i{width:8px;height:8px;display:inline-block;background:var(--dim);flex:0 0 auto}
.legend .bad i{background:var(--bad)} .legend .warn i{background:var(--warn)}
.legend .unknown i{background:var(--unknown)} .legend .good i{background:var(--good)}
.legend b{color:var(--ink);font-weight:700;font-variant-numeric:tabular-nums}
.legend .bad b{color:var(--bad)} .legend .warn b{color:var(--warn)}
.legend .unknown b{color:var(--unknown)} .legend .good b{color:var(--good)}

/* ============ LEVEL 3 — ZONES AND PANELS ============================== */
main{display:grid;grid-template-columns:1fr;gap:var(--gap);background:var(--rule)}
@media(min-width:900px){main{grid-template-columns:minmax(0,1.3fr) minmax(0,1fr)}}
@media(min-width:1320px){main{grid-template-columns:minmax(0,1.35fr) minmax(0,1fr) minmax(0,1fr)}}
.zone{background:var(--ground);min-width:0;padding-bottom:14px}
.zone.wide{grid-column:1/-1}
.zone>h3{margin:0;padding:7px var(--pad-x) 6px;font-size:var(--fs-micro);letter-spacing:.22em;
text-transform:uppercase;color:var(--faint);font-weight:700;
background:var(--panel-2);border-bottom:1px solid var(--rule)}

section{background:var(--panel);border-bottom:1px solid var(--rule);overflow:hidden}
.head{display:flex;justify-content:space-between;gap:9px;align-items:baseline;
padding:7px var(--pad-x);background:var(--panel-3);border-bottom:1px solid var(--rule)}
.head h2{margin:0;font-size:var(--fs-micro);letter-spacing:.15em;text-transform:uppercase;color:var(--dim);
font-weight:600}
.chip{font-size:var(--fs-micro);padding:1px 7px;background:var(--ground);color:var(--dim);
white-space:nowrap;border:1px solid var(--rule-strong);max-width:22ch;overflow:hidden;
text-overflow:ellipsis}
.chip.good{color:var(--good);border-color:var(--good)}
.chip.warn{color:var(--warn);border-color:var(--warn)}
.chip.bad{color:var(--bad);border-color:var(--bad);background:var(--bad-bg)}
.chip.unknown{color:var(--unknown);border-color:var(--unknown);background:var(--unknown-bg)}
.chip.good::before{content:"✓ "} .chip.warn::before{content:"▲ "}
.chip.bad::before{content:"✕ "} .chip.unknown::before{content:"? "}

ul{list-style:none;margin:0;padding:4px 0}
li{padding:var(--pad-y) var(--pad-x);display:flex;gap:9px;flex-wrap:wrap;word-break:break-word;line-height:1.45}
li .k{color:var(--faint);flex:0 0 auto}
li .k::after{content:":"}
li .v{flex:1 1 15rem;min-width:0;max-width:96ch}
li.d1{padding-left:calc(var(--pad-x) + 14px);box-shadow:inset 1px 0 0 var(--rule);margin-left:16px}
li.d2{padding-left:calc(var(--pad-x) + 28px);box-shadow:inset 1px 0 0 var(--rule);margin-left:16px}
li.good .v{color:var(--good)} li.warn .v{color:var(--warn)}
li.bad .v{color:var(--bad);font-weight:600}
li.muted,li.muted .v,li.muted .k{color:var(--faint)}
li.unknown{background:var(--unknown-bg)} li.unknown .v{color:var(--unknown)}
li.unknown>.k{color:var(--unknown);font-weight:600}
li.action{background:var(--action-bg)} li.action .v{color:var(--action);font-weight:600}
li.bad .v::before{content:"✕ "} li.warn .v::before{content:"▲ "}
li.unknown .v::before{content:"? "}

section>details>summary{cursor:pointer;padding:5px var(--pad-x) 6px;font-size:var(--fs-forensic);color:var(--faint);
letter-spacing:.06em;list-style:none;border-top:1px solid var(--rule);user-select:none}
section>details>summary::-webkit-details-marker{display:none}
section>details>summary::before{content:"▸ "}
section>details[open]>summary::before{content:"▾ "}
summary:hover{color:var(--accent)}
summary:focus-visible,a:focus-visible,button:focus-visible,input:focus-visible,
select:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
::selection{background:var(--select);color:var(--ink)}

footer{padding:14px var(--pad-x) 30px;color:var(--faint);font-size:var(--fs-forensic);max-width:88ch}

/* ============ NARROW — a deliberate order, not a stack ================ */
@media(max-width:760px){
  body{font-size:var(--fs)}
  .bar{gap:0 14px;padding:5px 12px;font-size:var(--fs-forensic)}
  h1{padding:8px 12px 0}
  .cmd{padding:9px 12px 12px;gap:11px}
  .state{font-size:calc(var(--fs-state) * 0.8)}
  .said{font-size:var(--fs)}
  .next span{font-size:calc(var(--fs) + 2px)}
  .sit{grid-template-columns:repeat(auto-fill,minmax(min(100%,132px),1fr))}
  .strip{grid-template-columns:repeat(auto-fill,minmax(min(100%,146px),1fr))}
  .attn>summary{padding:7px 12px}
  .zone>h3{padding:6px 12px 5px}
  .head{padding:6px 12px}
  li{padding-left:12px;padding-right:12px}
  li .v{flex:1 1 100%}
  li.d1{padding-left:24px;margin-left:10px} li.d2{padding-left:34px;margin-left:10px}
  section>details>summary{padding-left:12px}
  footer{padding:12px 12px 26px}
}
"""


#: Every lens the stylesheet defines, read from the stylesheet. Written out
#: once, a list here and a set of `[data-theme=…]` blocks below drift, and the
#: drift is silent: a lens with no entry is unreachable from the command line
#: and a lens with no block renders as the default while claiming not to.
LENSES = ("",) + tuple(sorted(set(re.findall(r'\[data-theme="([a-z]+)"\]', _STYLE))))


def _escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


#: Which band of the console a panel's rows belong in. Presentation only: the
#: panel says which QUESTION it answers (`Panel.group`, five values a test
#: bounds), and this says where that question goes on a wide screen. Keeping
#: them separate is the point — a panel that had to know about a grid column
#: would be a panel that changes when the layout does.
_ZONES = (
    ("operations", ("now",)),
    ("evidence and audit", ("evidence",)),
    ("capacity and routing", ("resources",)),
    ("forensics — identity, vocabulary, provenance", ("identity", "detail")),
)


def render_html(view: "Projection", title: str = "Runtime Pack — projection", *,
                theme: str = "", accent: str = "") -> str:
    """The same reading, as an operations console.

    Three bands, in the order a reader of a long run actually needs them.
    **Command** — the state, whether a person is required, what happens next,
    and the level-1 readings as cells. **Telemetry** — every established figure
    as a figure. **Zones** — the panels, grouped by the question they answer,
    with prose behind a disclosure wherever collapsing it cannot hide
    uncertainty.

    Derives nothing the text renderer does not. Every figure in the first two
    bands is a `Cell` some panel made, and every cell restates a line that
    panel also shows — so nothing here is the only place a reading appears.
    """
    tone = _verdict_tone(view.headline)
    verdict_class = {Tone.BAD: "v-bad", Tone.WARN: "v-warn", Tone.GOOD: "v-good",
                     Tone.UNKNOWN: "v-unknown"}.get(tone, "")
    state, _, sentence = view.headline.partition(":")
    attention = view.attention
    counts = {t: sum(1 for line in attention if line.tone == t)
              for t in (Tone.BAD, Tone.WARN, Tone.UNKNOWN)}

    root_attrs = f' data-theme="{_escape(theme)}"' if theme else ""
    accent_rule = (f"<style>:root{{--accent:{_escape(accent)}}}</style>" if accent else "")
    return "\n".join([
        "<!doctype html>", f"<html lang=\"en\"{root_attrs}>", "<head>",
        "<meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
        f"<title>{_escape(title)}</title>", f"<style>{_STYLE}</style>", accent_rule,
        "</head>", "<body>", render_body(view),
        "<footer>Every answer here is delegated to the module that owns it. "
        "This page authorises nothing, schedules nothing, wakes nothing and stores "
        "nothing; deleting it breaks no checker.</footer>", "</body></html>"])


def render_body(view: "Projection", heading: str = "Runtime Pack — mission control", *,
                widget_prefix: str = "") -> str:
    """The three bands, without a document around them.

    Split out so the multi-project console composes exactly this page per
    project rather than a second rendering of the same reading. One
    implementation, so the two cannot say different things.
    """
    tone = _verdict_tone(view.headline)
    verdict_class = {Tone.BAD: "v-bad", Tone.WARN: "v-warn", Tone.GOOD: "v-good",
                     Tone.UNKNOWN: "v-unknown"}.get(tone, "")
    state, _, sentence = view.headline.partition(":")
    attention = view.attention
    counts = {t: sum(1 for line in attention if line.tone == t)
              for t in (Tone.BAD, Tone.WARN, Tone.UNKNOWN)}
    band = (f" data-widget='{widget_prefix}:command' data-widget-name="
            f"'{_escape(widget_prefix)} — state and next action'" if widget_prefix else "")
    out = [_status_bar(view),
           f"<header{band}>", f"<h1>{_escape(heading)}</h1>",
           f"<div class='cmd {verdict_class}'>",
           "<div class=primary>",
           f"<p class=state>{_escape(state.strip())}</p>",
           f"<p class=said>{_escape(sentence.strip() or view.headline)}</p>"]

    if view.next_action:
        out.append("<div class=next><b>NEXT AUTHORISED ACTION</b>"
                   f"<span>{_escape(view.next_action)}</span></div>")
    out.append("</div>")
    out.append(_situation(view))
    out.append("</div>")

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
    out.append("</header>")

    strip = _operational_strip(view)
    if strip:
        out.append(strip)

    out.append("<main>")
    for heading, groups in _ZONES:
        panels = [p for p in view.panels if p.group in groups]
        if not panels:
            continue
        wide = " wide" if len(groups) > 1 else ""
        out.append(f"<div class='zone{wide}'><h3>{_escape(heading)}</h3>")
        for panel in panels:
            order = view.panels.index(panel)
            out.append(_section(panel,
                                node_id=f"{widget_prefix}:{order}" if widget_prefix else "",
                                name=f"{widget_prefix} — {panel.title}" if widget_prefix
                                else panel.title))
        out.append("</div>")
    out.append("</main>")
    return "\n".join(out)


def _section(panel: "Panel", *, node_id: str = "", name: str = "") -> str:
    """One panel: its answer as a chip, its findings open, its prose behind a
    disclosure — and never its uncertainty."""
    rows = panel.rows()
    #: The forensic half. A line is detail when its own panel marked it MUTED or
    #: nested it under another — never when it is BAD, WARN or UNKNOWN, because
    #: putting uncertainty behind a disclosure is hiding it.
    # Depth does NOT decide this. The first version collapsed anything nested,
    # and an expired deadline is a nested line marked BAD — so the single most
    # urgent fact on the page went behind a disclosure. Caught by the test that
    # asserts uncertainty is never collapsed, which is the reason to write that
    # test rather than assume it.
    urgent = (Tone.BAD, Tone.WARN, Tone.UNKNOWN, Tone.ACTION)
    head = [l for l in rows if l.tone in urgent or (l.depth == 0 and l.tone != Tone.MUTED)]
    rest = [l for l in rows if l not in head]
    tone_here = panel.summary_tone if panel.summary_tone in Tone.ALL else Tone.PLAIN
    chip = (f"<span class='chip {tone_here}'>{_escape(panel.summary)}</span>"
            if panel.summary else "")
    if panel.unknown:
        chip += f"<span class='count unknown'>{len(panel.unknown)}</span>"
    tag = (f" data-widget='{_escape(node_id)}' data-widget-name='{_escape(name or panel.title)}'"
           if node_id else "")
    # SECTIONS AN OPERATOR MAY FOLD AWAY, and the rule that decides which.
    #
    # Not *carries no finding* — the identity panel carries one whenever the
    # pack is unfrozen. The rule is that **everything urgent inside a foldable
    # section is also in the attention strip**, which cannot be folded, so
    # folding one changes where a marked line is and never whether it is on the
    # page.
    #
    # The state vocabulary fails that rule and is NOT foldable: `attention`
    # deliberately skips legend panels, so `SILENT_IDLE: THIS ONE` is marked
    # BAD there and hoisted nowhere. Found by writing the rule down and
    # checking the page against it.
    if panel.group == "identity" and not panel.legend:
        tag += " data-optional='identity'"
    out = [f"<section{tag}><div class=head><h2>{_escape(panel.title)}</h2>{chip}</div><ul>"]
    out.extend(_row(line) for line in head)
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
    return "".join(out)


#: Readings that belong in the top bar rather than in a panel: a reader wants
#: identity at a glance and does not want to hunt for it.
def _status_bar(view: "Projection") -> str:
    """Identity, always, in one line. Never a summary — every value here is
    lifted verbatim from a panel that also shows it."""
    # READ OFF THE FIGURES, not off panel titles. Matching `panel.title ==
    # "the pack this projection ships in"` made the bar a second reader of
    # prose: rewording a heading emptied it, silently, with nothing red.
    pack = next((c for c in view.identity if c.kind == "pack"), None)
    pin = next((c for c in view.identity if c.kind == "pin"), None)
    fresh = next(iter(view.figure_of("freshness")), None)
    cells = [("pack", f"{pack.value} {pack.note}" if pack else UNKNOWN, "id"),
             ("digest", pack.fields.get("digest", UNKNOWN) if pack else UNKNOWN, ""),
             ("project", pin.value if pin else UNKNOWN, ""),
             ("read", fresh.value if fresh else UNKNOWN, "")]
    return ("<div class=bar>" + "".join(
        f"<b>{_escape(k)}</b><span class='{cls}'>{_escape(v)}</span>" for k, v, cls in cells)
        + "</div>")


def _situation(view: "Projection") -> str:
    """Level 1 as cells: the readings a person needs before deciding whether to
    look further.

    Every cell was made by the panel that owns its fact, and restates a line
    that panel also shows. The one thing computed here is the tally beside the
    heading — a count of the cells on this page, the same page furniture as the
    badge on the attention strip, and not a reading of the record.
    """
    cells = view.situation
    if not cells:
        return "<div class=sit></div>"
    tally = {}
    for cell in cells:
        if cell.kind == "job":
            tally[cell.value] = tally.get(cell.value, 0) + 1
    summary = (" · ".join(f"{n} {name.lower()}" for name, n in sorted(tally.items()))
               if tally else "nothing is outstanding")
    return ("<div><div class=sit-head><b>situation</b>"
            f"<span>{_escape(summary)}</span></div>"
            "<div class=sit>" + "".join(_cell(c, "sit") for c in cells) + "</div></div>")


def _operational_strip(view: "Projection") -> str:
    """Level 2: established figures as figures.

    **Nothing is computed here.** Every value is a `Cell` a panel produced from
    a fact it also states as a line, and a budget with no ceiling gets no bar
    rather than a guessed one.

    The previous version read the strip out of the panels' PROSE with a regular
    expression for `N/M used`. It worked, and it meant the instruments were one
    rewording away from silently emptying — with nothing red, because no test
    can require a meter that the page infers.
    """
    facts = [_cell(c, "fact") for c in view.telemetry]
    return f"<div class=strip>{''.join(facts)}</div>" if facts else ""


def _cell(cell: "Cell", css: str) -> str:
    """One figure: the exact value, and a bar only where a real denominator says
    what the fraction is a fraction OF.

    Tone decides colour AND a glyph, because status carried by colour alone is
    status a colour-blind reader does not have. The bar's own colour comes from
    `Cell.sense`, and the two senses are opposite on purpose — a spent budget
    and complete coverage are both "full", and a console that draws them the
    same way tells a reader that running out is an achievement.
    """
    tone = cell.tone if cell.tone in Tone.ALL else Tone.PLAIN
    meter = ""
    if cell.share:
        used, ceiling = cell.share
        share = min(100.0, max(0.0, 100.0 * used / ceiling))
        full = used >= ceiling
        bar = {"consumption": Tone.BAD if full else (Tone.WARN if share >= 75 else tone),
               "coverage": Tone.GOOD if full else tone,
               "age": Tone.WARN if full else tone,
               "deadline": Tone.BAD if full else (Tone.WARN if share >= 85 else tone),
               }.get(cell.sense, tone)
        meter = (f"<span class='meter {cell.sense}' role=img "
                 f"aria-label='{_escape(cell.value)}'>"
                 f"<i class='{bar}' style='width:{share:.1f}%'></i></span>")
    note = f"<u>{_escape(cell.note)}</u>" if cell.note else ""
    return (f"<div class='{css} {tone}'><i>{_escape(cell.label)}</i>"
            f"<em>{_escape(cell.value)}</em>{note}{meter}</div>")


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
    parser.add_argument("--theme", default="", choices=list(LENSES),
                        help="presentation only; it changes no state and no classification")
    parser.add_argument("--accent", default="",
                        help="a CSS colour for the presentation accent, e.g. '#37ff9b'")
    args = parser.parse_args(argv)

    view = project(args.project_root, contract=args.contract,
                   continuation_record=args.continuation,
                   capacity_observation=args.capacity)
    print(render_html(view, args.title, theme=args.theme, accent=args.accent)
          if args.html else view.render())
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
