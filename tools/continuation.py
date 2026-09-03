"""Coordinator state as a value derived from artifacts, so silence has a name.

Four different situations produce one identical observable — nothing happening.
Finished. Blocked on capacity. Legitimately waiting on a live job. Idle with
authorised work outstanding. Only the last is a defect, and from outside they
are indistinguishable, which is why one of them ran for two hours and twenty-one
minutes before a person noticed.

Ten recorded instances, and the decisive one is not the longest. In it the
coordinator did everything the previous four had taught: it declared that it was
waiting, and it named the job, the process and the log. Then the job exited and
the declaration stayed exactly as written. **A state that exists only as a
sentence cannot have a transition**, and that removes the explanation that the
earlier instances invited — that somebody forgot the rule.

## The state is derived, not stored

This module stores a **declaration**: what the coordinator is waiting for, and
how anyone could observe that it finished. It does not store the state. The
state is computed from that declaration plus the artifacts, every time anybody
asks, so it advances on job exit whether or not the coordinator is there to
notice — which matters because *the coordinator that has gone silent is the one
that cannot poll.*

That is also what keeps this from becoming a second authority. `DECISIONS.md`
D23 clause 8: no governed action may be taken whose only premise is a state
value, and every transition must be reconstructible from a durable artifact.
A derived state satisfies the second by construction — there is nothing to
reconstruct, because nothing was stored. The governance record remains
authoritative; where this and the record disagree, this is the defect.

## A declared wait names an observable

The failure this refuses is the one that actually happened: a wait declared in
prose, with nothing a later reader could check. So a wait must carry at least
one condition a stateless checker can evaluate — a process, an exit-status file,
a task output root, a path that appears. A wait whose completion nobody can
observe is `RECOVERY_REQUIRED`, immediately and by construction, because it is
the shape that decayed.

`HUMAN` is the deliberate exception and is not an observable: it is a wait on a
person, it resolves when a person resolves it, and it is reported as a human
block rather than as a job. Coordinator unavailability never implies
authorisation, and neither does a checker's impatience.

## What this never does

It starts nothing, wakes nothing, and creates no session. `COORDINATOR_WAKE_REQUIRED`
is a **fact this module can report**, not an act it can perform (D23 clause 4).
Deciding what work is next stays coordinator judgement: this says a job has
finished and its result is unconsumed, never what to do about it.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import task_output
from errors import IntegrityError, PreconditionError

__all__ = [
    "State",
    "WaitKind",
    "Wait",
    "Blocker",
    "ContinuationRecord",
    "LivenessReport",
    "derive",
    "load",
    "save",
    "COORDINATOR_WAKE_REQUIRED",
]

#: What this module may report when a job has finished and nobody has consumed
#: its result. A fact, not an act: nothing here creates or wakes a session.
COORDINATOR_WAKE_REQUIRED = "COORDINATOR_WAKE_REQUIRED"

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class State:
    """Every answer, including the one that is a defect.

    Strings, so a record written today is readable by a reader that does not
    import this module — the same reasoning as the recovery classes.
    """

    #: Authorised work is ready and nothing is in the way. The state a
    #: coordinator should be acting from.
    ACTIONABLE_WORK_READY = "ACTIONABLE_WORK_READY"
    #: A named job is still running and its completion is observable.
    WAITING_ON_IDENTIFIED_JOB = "WAITING_ON_IDENTIFIED_JOB"
    #: A job finished and its result has not been taken up. This is the edge
    #: four of five recurrences were.
    COMPLETED_NOT_CONSUMED = "COMPLETED_NOT_CONSUMED"
    #: A human decision is outstanding. Not a defect and not a thing to wait out.
    BLOCKED_ON_HUMAN = "BLOCKED_ON_HUMAN"
    #: A provider window is exhausted. Distinct from waiting on a job, because
    #: the thing that resolves it is a clock and not a result.
    BLOCKED_ON_CAPACITY = "BLOCKED_ON_CAPACITY"
    #: Something cannot be established: a wait nobody can observe, an output
    #: root in an unknown state, a record that contradicts itself.
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    #: Done. Nothing outstanding.
    TERMINAL = "TERMINAL"
    #: **A defect, never a resting state.** Work is authorised, nothing is
    #: declared to be in the way, and nothing is happening.
    SILENT_IDLE = "SILENT_IDLE"

    ALL = (
        ACTIONABLE_WORK_READY, WAITING_ON_IDENTIFIED_JOB, COMPLETED_NOT_CONSUMED,
        BLOCKED_ON_HUMAN, BLOCKED_ON_CAPACITY, RECOVERY_REQUIRED, TERMINAL, SILENT_IDLE,
    )

    #: The one state that is a defect wherever it appears.
    DEFECTS = (SILENT_IDLE,)


class WaitKind:
    """How a wait's completion is observed. Each is checkable without asking
    the worker, because the worker is what has gone."""

    PROCESS = "process"
    EXIT_FILE = "exit_file"
    OUTPUT_ROOT = "output_root"
    PATH_EXISTS = "path_exists"
    #: A person. Not an observable, and deliberately so.
    HUMAN = "human"

    OBSERVABLE = (PROCESS, EXIT_FILE, OUTPUT_ROOT, PATH_EXISTS)
    ALL = OBSERVABLE + (HUMAN,)


@dataclass(frozen=True)
class Wait:
    """One thing the coordinator is waiting for, and how anyone can check it.

    ``expects`` is what the result is supposed to be — not decoration. A wait
    that cannot say what it is waiting *for* produces a completion nobody can
    recognise as the answer to anything.
    """

    job_id: str
    kind: str
    expects: str
    #: **What this wait discharges.** Two un-retired waits naming the same
    #: obligation are a duplicate dispatch, and the state model refuses rather
    #: than letting two workers race to satisfy one requirement. Defaults to the
    #: job id, so a caller that does not distinguish them gets one-per-job.
    obligation: str = ""
    #: **The longest the coordinator will remain in this wait.** Required for
    #: every observable kind, and this is the field that makes indefinite
    #: silence impossible rather than merely nameable.
    #:
    #: Measured live: a dispatched worker sat for five hours and thirty-nine
    #: minutes with 0.34 seconds of processor time, no output and no provider
    #: rollout, while the coordinator waited. The state model of the moment
    #: could say `WAITING_ON_IDENTIFIED_JOB` and could say it forever, because a
    #: live process satisfies a liveness question indefinitely. A wait past its
    #: deadline is `RECOVERY_REQUIRED` **whatever the process is doing** — the
    #: deadline is a statement about the coordinator's patience, not about the
    #: worker, and it is the only thing that terminates the state.
    not_beyond_seconds: float | None = None
    pid: int | None = None
    path: str | None = None
    task_id: str | None = None
    max_bytes_per_write: int | None = None
    #: WHAT this job is about, when that is a tree. An audit is evidence about
    #: one revision, and a reader who cannot see which one cannot tell current
    #: evidence from evidence two repair rounds old — which happened here, and
    #: cost six findings' worth of re-execution to discover.
    subject_revision: str = ""
    subject_digest: str = ""
    #: The executor, for a reader deciding whether a route is behaving.
    executor: str = ""
    declared_at: str = ""
    #: Set once the coordinator has taken the result up. An unconsumed
    #: completion is the state this whole module exists to name.
    consumed: bool = False
    #: Set when a wait has been recovered from and must no longer be considered.
    #: A retired wait does not hold its obligation, so a replacement dispatch is
    #: not a duplicate.
    retired: bool = False

    def expired_at(self, now: str) -> bool:
        """Whether the declared patience has run out.

        Compared on the clock the caller supplies rather than on wall time, so
        the answer is deterministic and a rehearsal can reach it without
        waiting.

        **Fails closed.** The first version swallowed a parse failure and
        returned `False`, so a wait whose `declared_at` was the word `soon`
        never expired — and it round-tripped through `save`/`load`, which made
        the indefinite wait this module exists to end reachable from disk. An
        auditor wrote it in three lines. A deadline that cannot be evaluated is
        a deadline that has passed: the alternative is the failure class.
        """
        if self.not_beyond_seconds is None or not self.declared_at:
            return False
        started, current = _moment(self.declared_at), _moment(now)
        if started is None or current is None:
            return True
        try:
            bound = float(self.not_beyond_seconds)
        except (TypeError, ValueError):
            # The same rule one field over, and reachable because the
            # constructor validates the bound only for OBSERVABLE kinds: a HUMAN
            # wait carrying `"not-a-number"` loaded, skipped that check, and
            # raised out of here. Found by an independent reader. A deadline
            # nobody can read has passed.
            return True
        return (current - started).total_seconds() > bound

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.job_id or ""):
            raise IntegrityError("a job id must be a short stable name", job_id=repr(self.job_id))
        if self.kind not in WaitKind.ALL:
            raise IntegrityError("no such wait kind", kind=repr(self.kind),
                                 known=", ".join(WaitKind.ALL))
        if not (self.expects or "").strip():
            raise PreconditionError(
                "a wait states what result it expects; a completion nobody can recognise as an "
                "answer is the shape that decayed into silence",
                job_id=self.job_id,
            )
        object.__setattr__(self, "obligation", (self.obligation or self.job_id).strip())
        if not (self.declared_at or "").strip():
            object.__setattr__(self, "declared_at", now())
        if self.kind in WaitKind.OBSERVABLE:
            bound = self.not_beyond_seconds
            if (not isinstance(bound, (int, float)) or isinstance(bound, bool)
                    or not math.isfinite(bound) or bound <= 0):
                raise PreconditionError(
                    "an observable wait declares how long the coordinator will remain in it. "
                    "Without a deadline a live process satisfies the wait forever, which is how "
                    "a dispatch that never started held a coordinator for five hours and "
                    "thirty-nine minutes",
                    job_id=self.job_id, declared=repr(bound),
                )
        required = {
            WaitKind.PROCESS: ("pid",),
            WaitKind.EXIT_FILE: ("path",),
            WaitKind.PATH_EXISTS: ("path",),
            WaitKind.OUTPUT_ROOT: ("path", "task_id", "max_bytes_per_write"),
            WaitKind.HUMAN: (),
        }[self.kind]
        missing = [name for name in required if getattr(self, name) in (None, "")]
        if missing:
            raise PreconditionError(
                "a declared wait must name an observable completion condition; without one it is "
                "a sentence, and a sentence cannot have a transition",
                job_id=self.job_id, kind=self.kind, missing=", ".join(missing),
            )

    @classmethod
    def declare(cls, **fields) -> "Wait":
        """Build a wait AT THE MOMENT IT IS DECLARED, with the extra check that
        only makes sense then.

        A path that already exists when a wait is declared is a completion
        condition that was satisfied before the job started — an auditor pointed
        one at `/dev/null` and derived a finished result for a worker that never
        existed. The sentinel a job creates on exit does not exist yet, by
        definition.

        **This is not a constructor invariant, and the difference is the whole
        point.** A record saved before a job finished is reconstructed after it
        finished, when the path *does* exist; a check in `__post_init__` made
        that record unloadable, which is a worse failure than the one it fixed.
        Declaration and reconstruction are different acts, so they have
        different entry points: `load` builds; only a caller declaring a new
        wait calls this.
        """
        wait = cls(**fields)
        if wait.kind in (WaitKind.EXIT_FILE, WaitKind.PATH_EXISTS) and wait.path:
            if Path(wait.path).exists():
                raise PreconditionError(
                    "this wait's completion condition is already satisfied at the moment it is "
                    "declared, so it can never mean that the job finished. A sentinel a job "
                    "creates on exit does not exist yet",
                    job_id=wait.job_id, path=wait.path,
                )
        return wait

    def as_dict(self) -> dict:
        return {key: value for key, value in self.__dict__.items() if value is not None}


@dataclass(frozen=True)
class Blocker:
    """Something outside the coordinator that has to move first."""

    kind: str  # "human" or "capacity"
    detail: str
    #: The numbered row of `policy/hitl-matrix.md` this block sits on, where one
    #: applies. A human block with no row is a block nobody can look up.
    hitl_row: int | None = None
    #: For a capacity block: which pool, and when it is expected to reset. Both
    #: may be unknown, and unknown is recorded rather than estimated.
    pool_id: str | None = None
    resets_at: str | None = None
    #: **What this blocker actually blocks.** Empty means everything, which is
    #: the safe default for a blocker whose scope nobody stated.
    #:
    #: Scoped because an unscoped one is another way into silent idling: a human
    #: decision outstanding on one stalled process reported the whole capability
    #: `BLOCKED_ON_HUMAN` while five authorised items sat undone. A blocker that
    #: stops work it has nothing to do with is indistinguishable, from outside,
    #: from a coordinator that has stopped.
    blocks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in ("human", "capacity"):
            raise IntegrityError("a blocker is human or capacity", kind=repr(self.kind))
        if not (self.detail or "").strip():
            raise IntegrityError("a blocker states what it is", kind=self.kind)
        if self.kind == "human" and self.hitl_row is None:
            raise PreconditionError(
                "a human block names the numbered row it sits on, so a reader can look up who "
                "decides it and at which step",
                detail=self.detail,
            )


@dataclass(frozen=True)
class ContinuationRecord:
    """The declaration. Not the state — the state is derived from this.

    Project-local, and the governance record remains authoritative over it.
    """

    capability: str
    updated_at: str
    #: Work the coordinator has authorised and not yet done. The presence of
    #: this with nothing in the way is what makes silence a defect.
    actionable: tuple[str, ...] = ()
    waits: tuple[Wait, ...] = ()
    blockers: tuple[Blocker, ...] = ()
    terminal: bool = False
    #: Where the authoritative governance record lives, so a reader who
    #: disbelieves this file knows what to read instead.
    record_path: str = ""
    #: Ceilings and what has been spent against them, as
    #: ``{"counter": {"used": n, "ceiling": m, "authorised_by": "..."}}``.
    #: Optional and empty by default: a coordinator that does not track budgets
    #: reads as UNKNOWN rather than as zero spent, because zero is a claim.
    budgets: dict = field(default_factory=dict)
    #: Standing status a reader needs and cannot derive from this file —
    #: ``{"suite": ..., "gates": ..., "latest_audit": ..., "closure": ...,
    #: "candidate": ...}``. Free-form strings, deliberately: this module does
    #: not adjudicate them and must not appear to.
    evidence: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "capability": self.capability,
            "updated_at": self.updated_at,
            "actionable": list(self.actionable),
            "waits": [wait.as_dict() for wait in self.waits],
            "blockers": [blocker.__dict__ for blocker in self.blockers],
            "terminal": self.terminal,
            "record_path": self.record_path,
            # Enumerated here AND in `load`, which is the whole hazard of this
            # shape: a field added to the dataclass and to neither is silently
            # dropped at the boundary this record exists to survive. Caught by
            # round-tripping the two added above before they were used once.
            "budgets": self.budgets,
            "evidence": self.evidence,
        }


# --- observing one wait --------------------------------------------------------


def _process_is_gone(pid: int) -> tuple[bool, str]:
    """``(finished, how it was established)``.

    `os.kill(pid, 0)` answers whether *a* process with that number exists. It
    does not answer whether it is the same one, because process numbers are
    reused, and this says so rather than implying a certainty it does not have.
    A stronger discriminator is a progress question rather than a liveness one,
    and it belongs with the progress model, not here.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True, f"no process {pid} exists"
    except PermissionError:
        return False, f"process {pid} exists and belongs to another user"
    except (OverflowError, ValueError, OSError) as exc:
        return False, f"process {pid} could not be asked about: {exc}"
    return False, f"process {pid} exists (a reused number would look the same)"


@dataclass(frozen=True)
class WaitObservation:
    job_id: str
    finished: bool | None  # None = could not be established
    how: str

    @property
    def unobservable(self) -> bool:
        return self.finished is None


def _mtime(target: Path) -> "datetime | None":
    try:
        return datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _observe(wait: Wait, *, relative_to: Path) -> WaitObservation:
    if wait.kind == WaitKind.HUMAN:
        return WaitObservation(wait.job_id, None, "a person resolves this; no machine can observe it")

    if wait.kind == WaitKind.PROCESS:
        # A saved record is untrusted input: it loads so that a run can be
        # continued, and every field it carries has to survive being wrong. A
        # `pid` of `"not-a-pid"` reloaded happily and then raised a bare
        # `ValueError` out of `derive` — an unhandled exception where the
        # contract is a named state, so the caller learned nothing and the
        # record could not even be reported as broken.
        try:
            # `int()` was the whole check, and it is a converter rather than a
            # validator: `1.5` became process 1 — init, always alive, so the
            # wait reported a running job forever — and infinity raised a bare
            # `OverflowError`. Both found by a blind reader on the repair for
            # the string case. A process id is a whole number, and anything
            # that merely converts to one is not a process id.
            if isinstance(wait.pid, bool) or not (
                    isinstance(wait.pid, int)
                    or (isinstance(wait.pid, str) and wait.pid.strip().lstrip("+-").isdigit())):
                raise ValueError(repr(wait.pid))
            pid = int(wait.pid)
        except (TypeError, ValueError, OverflowError):
            return WaitObservation(
                wait.job_id, None,
                f"this wait names {wait.pid!r} as a process id and that is not one, so nothing "
                f"about the job can be observed and the record itself needs repair",
            )
        finished, how = _process_is_gone(pid)
        return WaitObservation(wait.job_id, finished, how)

    target = Path(wait.path)
    if not target.is_absolute():
        target = relative_to / target

    if wait.kind in (WaitKind.EXIT_FILE, WaitKind.PATH_EXISTS):
        if not target.exists():
            return WaitObservation(wait.job_id, False, f"{target} has not appeared")

        # `Wait.declare` refuses a path that already exists, and that is the
        # right check at the right moment — but it is only reachable by the
        # caller who declares, and the auditor who pointed a wait at `/dev/null`
        # built the record directly. So the OBSERVATION asks the same question
        # again, in the two forms that survive a reload of a legitimate record.
        #
        # First: a sentinel a job writes on exit is a regular file. A character
        # device, a socket or a fifo is ambient furniture that was there before
        # the job and will be there after it.
        if wait.kind == WaitKind.EXIT_FILE and not target.is_file():
            return WaitObservation(
                wait.job_id, None,
                f"{target} is not a regular file, so it is not a sentinel any job wrote; a "
                f"wait cannot complete on something that was already there",
            )
        # Second: it must not predate its own wait. A path written before the
        # coordinator began waiting for it did not come from the job being
        # waited on, whatever it contains.
        declared, wrote = _moment(wait.declared_at), _mtime(target)
        if declared is None or wrote is None:
            return WaitObservation(
                wait.job_id, None,
                f"{target} exists and cannot be dated against this wait's declaration, so "
                f"whether the job wrote it is unknown",
            )
        if wrote < declared:
            return WaitObservation(
                wait.job_id, None,
                f"{target} was last written before this wait was declared, so it is not this "
                f"job's result; the job may still be running",
            )

        # WHAT THIS ESTABLISHES, stated because an auditor was right about what
        # it does not. A path becoming true after the wait began is evidence
        # that SOMETHING wrote it; it is not evidence about WHO. A second
        # process writing to the same path satisfies this wait, and no property
        # of a bare filesystem path can distinguish the two.
        #
        # `OUTPUT_ROOT` is the kind that establishes a producer: the root
        # carries an owner marker naming the task, and `task_output.classify`
        # refuses a root another task owns. A caller who needs to know whose
        # result this is declares that kind — and this comment exists so the
        # choice is made knowingly rather than discovered later.
        detail = ""
        if wait.kind == WaitKind.EXIT_FILE:
            try:
                detail = f", status {target.read_text(encoding='utf-8').strip()[:16]}"
            except OSError as exc:
                return WaitObservation(wait.job_id, None,
                                       f"{target} exists and cannot be read: {exc}")
        return WaitObservation(wait.job_id, True, f"{target} exists{detail}")

    # The SAME defect as the process id, one field over, and the pid repair did
    # not generalise because it was written as a repair for the pid. A saved
    # record's `max_bytes_per_write` of `"not-an-int"` raised a bare ValueError
    # out of a function whose contract is a state.
    try:
        bound = wait.max_bytes_per_write
        if isinstance(bound, bool) or not (
                isinstance(bound, int)
                or (isinstance(bound, str) and bound.strip().isdigit())):
            raise ValueError(repr(bound))
        # POSITIVE. Zero and negative are integers, so the type check passed
        # them straight into `OutputContract`, which refused with a
        # `PreconditionError` that escaped `derive` — a refusal from the wrong
        # layer is still an exception where the contract is a state.
        if int(bound) <= 0:
            raise ValueError(repr(bound))
        contract = task_output.OutputContract(
            task_id=wait.task_id, output_root=target, max_bytes_per_write=int(bound),
        )
    except (TypeError, ValueError, OverflowError):
        return WaitObservation(
            wait.job_id, None,
            f"this wait declares a write bound of {wait.max_bytes_per_write!r}, which is not a "
            f"number of bytes, so its output root cannot be classified and the record needs repair",
        )
    report = task_output.classify(contract)
    if report.state == task_output.RecoveryState.UNKNOWN:
        return WaitObservation(wait.job_id, None, f"the output root is UNKNOWN: {report.why}")
    finished = report.state == task_output.RecoveryState.COMPLETED_WITH_DURABLE_OUTPUT
    return WaitObservation(wait.job_id, finished, f"the output root reports {report.state}")


# --- the derivation ----------------------------------------------------------------


@dataclass(frozen=True)
class LivenessReport:
    capability: str
    state: str
    why: str
    observations: tuple[WaitObservation, ...] = ()
    #: Completed waits nobody has taken up. The reason a wake may be needed.
    unconsumed: tuple[str, ...] = ()
    #: Waits whose completion nobody can observe, and waits pointing at nothing.
    unobservable: tuple[str, ...] = ()
    #: A completed wait already marked consumed, still declared. Harmless, and
    #: worth retiring so a stale quorum cannot report `RUNNING` indefinitely.
    superseded: tuple[str, ...] = ()
    #: Waits past the deadline their declaration carried. The state that makes
    #: indefinite silence impossible.
    expired: tuple[str, ...] = ()
    #: Obligations held by more than one live wait.
    duplicated: tuple[str, ...] = ()
    actionable: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    @property
    def wake_required(self) -> bool:
        return bool(self.unconsumed) or bool(self.expired) or self.state in (
            State.RECOVERY_REQUIRED, State.SILENT_IDLE,
        )

    @property
    def is_defect(self) -> bool:
        return self.state in State.DEFECTS

    def render(self) -> str:
        lines = [f"{self.capability}: {self.state}", f"  {self.why}"]
        if self.wake_required:
            lines.append(f"  {COORDINATOR_WAKE_REQUIRED}")
        for observation in self.observations:
            mark = "finished" if observation.finished else ("UNOBSERVABLE" if observation.unobservable else "running")
            lines.append(f"  job {observation.job_id}: {mark} — {observation.how}")
        for label, values in (("unconsumed", self.unconsumed),
                              ("cannot be observed", self.unobservable),
                              ("PAST THE DECLARED DEADLINE", self.expired),
                              ("obligation held twice", self.duplicated),
                              ("superseded, retire it", self.superseded)):
            if values:
                lines.append(f"  {label}: {', '.join(values)}")
        for blocker in self.blockers:
            lines.append(f"  blocked: {blocker}")
        if self.actionable:
            lines.append(f"  authorised and outstanding: {len(self.actionable)} item(s)")
        return "\n".join(lines)


def derive(
    record: ContinuationRecord, *, relative_to: str | Path = ".", now: str | None = None
) -> LivenessReport:
    """The current state, computed from the declaration and the artifacts.

    Order matters and is not arbitrary. Anything that cannot be established
    outranks anything that can, because acting on an unestablished state is the
    error class this pack exists to refuse. A completed-and-unconsumed result
    outranks a remaining wait, because that is the edge four of five recurrences
    were and burying it under "still waiting on something else" is how it
    stayed invisible.
    """
    base = Path(relative_to)
    moment = now or _now()
    #: A retired wait is out of the picture entirely: it holds no obligation and
    #: is not observed. Recovery retires; it does not delete, so the record
    #: still says what happened.
    live = tuple(w for w in record.waits if not w.retired)
    observations = tuple(_observe(wait, relative_to=base) for wait in live)
    by_id = {wait.job_id: wait for wait in live}

    #: Two live waits on one obligation are two workers racing to satisfy one
    #: requirement, and whichever answers second is work nobody asked for.
    holders: dict[str, list[str]] = {}
    for wait in live:
        holders.setdefault(wait.obligation, []).append(wait.job_id)
    duplicated = {ob: jobs for ob, jobs in holders.items() if len(jobs) > 1}

    #: Past its declared deadline, whatever the process is doing. A live process
    #: satisfies a liveness question forever, which is how a dispatch that never
    #: started held a coordinator for five hours and thirty-nine minutes.
    finished_ids = {o.job_id for o in observations if o.finished}
    #: A wait that finished is not waiting, so patience does not apply to it —
    #: and one whose result was taken up is simply done. Including them made a
    #: terminal record report RECOVERY_REQUIRED permanently, because time only
    #: moves one way. Introduced by the expiry repair and found by an auditor.
    expired = tuple(
        w.job_id for w in live
        if w.expired_at(moment) and not (w.consumed or w.job_id in finished_ids)
    )

    unobservable = tuple(
        o.job_id for o in observations
        if o.unobservable and by_id[o.job_id].kind != WaitKind.HUMAN
    )
    finished = [o for o in observations if o.finished]
    unconsumed = tuple(o.job_id for o in finished if not by_id[o.job_id].consumed)
    superseded = tuple(o.job_id for o in finished if by_id[o.job_id].consumed)
    running = tuple(o.job_id for o in observations if o.finished is False)
    human_waits = tuple(w.job_id for w in live if w.kind == WaitKind.HUMAN)

    #: A blocker with no `blocks` names nothing, so it names everything.
    unscoped = [b for b in record.blockers if not b.blocks]
    named_by_a_blocker = {item for b in record.blockers for item in b.blocks}
    #: What is outstanding and NOT named by any blocker. This, not the whole
    #: list, is what silence is measured against.
    unblocked = () if unscoped else tuple(
        i for i in record.actionable if i not in named_by_a_blocker)

    #: **The question is asked of the blockers TOGETHER, and that is the repair.**
    #:
    #: It was asked of each one separately: *does this blocker leave the
    #: coordinator with nothing to do?* Two blockers, one human and one capacity,
    #: each naming half of two outstanding items — neither stopped everything, so
    #: both were filed as scoped, `unblocked` came out empty, and the report read
    #: *nothing is in the way and nothing is outstanding* while listing two
    #: outstanding items and two blockers beneath it. Found by a blind auditor,
    #: and it is the same shape as the `any`/`all` defect one round earlier: the
    #: predicate was right and the quantifier was over the wrong set.
    #:
    #: Coverage is a property of the union. Whether any single blocker happens to
    #: cover everything is not the question a coordinator is asking.
    stopped = bool(record.blockers) and not unblocked

    human = [b for b in record.blockers if b.kind == "human"] if stopped else []
    capacity = [b for b in record.blockers if b.kind == "capacity"] if stopped else []
    #: Recorded and reported whatever their scope, because a blocker nobody can
    #: see is a blocker nobody resolves.
    scoped_away = [] if stopped else list(record.blockers)
    blocker_lines = tuple(
        f"{b.kind}: {b.detail}" + (f" (row {b.hitl_row})" if b.hitl_row else "")
        + (f" (pool {b.pool_id})" if b.pool_id else "")
        + (" — SCOPED, and it does not stop the outstanding work"
           if b in scoped_away else "")
        for b in record.blockers
    )

    common = dict(
        capability=record.capability, observations=observations, unconsumed=unconsumed,
        unobservable=unobservable, superseded=superseded, expired=expired,
        duplicated=tuple(sorted(duplicated)),
        actionable=tuple(record.actionable), blockers=blocker_lines,
    )

    if duplicated:
        return LivenessReport(**common, state=State.RECOVERY_REQUIRED, why=(
            "two live waits hold the same obligation — "
            + "; ".join(f"{ob}: {', '.join(jobs)}" for ob, jobs in sorted(duplicated.items()))
            + ". Whichever answers second is work nobody asked for, and retiring one is a "
              "decision rather than a race"))

    if unobservable:
        return LivenessReport(**common, state=State.RECOVERY_REQUIRED, why=(
            "a declared wait names no completion anyone can observe, or names one that can no "
            "longer be read; that is the shape that decayed into silence and it is not waited out"))

    if unconsumed:
        return LivenessReport(**common, state=State.COMPLETED_NOT_CONSUMED, why=(
            f"{len(unconsumed)} job(s) finished and nothing has taken the result up; this is the "
            "edge four of five recorded recurrences were"))

    if expired:
        # BEFORE the running branch, deliberately. A stalled process is alive, so
        # a liveness question about it answers WAITING_ON_IDENTIFIED_JOB forever —
        # which is precisely the state that held for five hours and thirty-nine
        # minutes. AFTER the unconsumed branch, equally deliberately: a job that
        # finished past its deadline has left a result, and taking it up is the
        # recovery. Expiry is the answer when there is nothing to take up.
        return LivenessReport(**common, state=State.RECOVERY_REQUIRED, why=(
            f"{len(expired)} wait(s) are past the deadline the coordinator declared for them "
            f"({', '.join(expired)}). This is true whatever the job is doing: a live process "
            "satisfies a liveness question forever, so the deadline is what ends the wait. "
            "Classify from the artifacts and recover before retrying anything"))

    if running:
        return LivenessReport(**common, state=State.WAITING_ON_IDENTIFIED_JOB, why=(
            f"{len(running)} job(s) still running, each with an observable completion condition"))

    if human or human_waits:
        return LivenessReport(**common, state=State.BLOCKED_ON_HUMAN, why=(
            "a human decision is outstanding; unavailability never implies authorisation, so the "
            "work waits"))

    if capacity:
        return LivenessReport(**common, state=State.BLOCKED_ON_CAPACITY, why=(
            "a provider window is exhausted; what resolves this is a clock, not a result"))

    if record.terminal:
        if record.actionable:
            return LivenessReport(**common, state=State.RECOVERY_REQUIRED, why=(
                "the record declares itself terminal and also declares authorised work "
                "outstanding; those cannot both be true"))
        return LivenessReport(**common, state=State.TERMINAL, why="nothing is outstanding")

    if unblocked:
        return LivenessReport(**common, state=State.SILENT_IDLE, why=(
            f"{len(unblocked)} authorised item(s) are outstanding, nothing is declared to "
            "be in the way, and no job is running. This is a DEFECT, not a resting state: the "
            "next action is owed now"))

    return LivenessReport(**common, state=State.ACTIONABLE_WORK_READY, why=(
        "nothing is in the way and nothing is outstanding; the coordinator decides what is next"))


# --- the durable declaration -------------------------------------------------------


def save(record: ContinuationRecord, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record.as_dict(), indent=2) + "\n", encoding="utf-8")
    return target


def _only_strings(values, field_name: str) -> list[str]:
    """A list of strings, or a refusal naming what was there instead."""
    if values is None:
        return []
    if not isinstance(values, list):
        raise PreconditionError(f"`{field_name}` is a list of strings",
                                found=type(values).__name__)
    for value in values:
        if not isinstance(value, str):
            raise PreconditionError(
                f"`{field_name}` holds strings; this record names work that is not a name",
                found=repr(value)[:60],
            )
    return list(values)


def load(path: str | Path) -> ContinuationRecord:
    target = Path(path)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PreconditionError("the continuation record cannot be read",
                                path=str(target), error=str(exc)) from exc
    except ValueError as exc:
        raise PreconditionError("the continuation record is not readable JSON",
                                path=str(target), error=str(exc)) from exc
    if not isinstance(raw, dict):
        raise PreconditionError("a continuation record is an object", path=str(target))
    try:
        return ContinuationRecord(
            capability=raw["capability"],
            updated_at=raw.get("updated_at", ""),
            # Checked, because a saved record is untrusted input and `derive`
            # puts these in a set: `"actionable": [[]]` loaded fine and then
            # raised `TypeError: unhashable type` out of the derivation, which
            # is an exception where the contract is a state. Found by a blind
            # reader.
            actionable=tuple(_only_strings(raw.get("actionable"), "actionable")),
            waits=tuple(Wait(**entry) for entry in raw.get("waits") or ()),
            # `blocks` is a tuple on the way out and JSON has only arrays, so
            # without this it comes back a list — the record survives the
            # boundary with a different type than it crossed with. Found by
            # asserting field-by-field equality across a round trip rather than
            # by checking the fields somebody remembered to check.
            blockers=tuple(
                Blocker(**{**entry, "blocks": tuple(_only_strings(entry.get("blocks"), "blocks"))})
                for entry in raw.get("blockers") or ()
            ),
            terminal=bool(raw.get("terminal", False)),
            record_path=raw.get("record_path", ""),
            budgets=dict(raw.get("budgets") or {}),
            evidence=dict(raw.get("evidence") or {}),
        )
    except (KeyError, TypeError) as exc:
        raise PreconditionError("the continuation record is malformed",
                                path=str(target), error=str(exc)) from exc


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


#: Internal alias so `derive` can default its clock without shadowing the
#: parameter a caller supplies.
_now = now


def _moment(text: object) -> datetime | None:
    """One timestamp, always comparable, or `None`.

    Naive and aware timestamps cannot be subtracted from each other, and the
    subtraction sat outside the guard — so an ordinary ISO-8601 string with no
    offset raised a `TypeError` out of `derive`, and the shipped command line
    printed a traceback where it should have reported a refusal. That exact
    class is already in this pack's observation log as repaired once.

    A timestamp with no offset is read as UTC rather than refused: it is
    unambiguous in every record this pack writes, and refusing it would turn a
    formatting difference into a stop.
    """
    if not isinstance(text, str):
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _cli(argv: list[str]) -> int:
    """Derive the current state from a continuation record.

    Usage: ``continuation.py RECORD [--relative-to DIR]``

    Exit status follows the state, because the states are not degrees of one
    thing: ``0`` nothing is owed, ``1`` something is owed now — a result to
    consume, or authorised work nobody is doing — ``2`` a state that cannot be
    established, and ``3`` blocked on a human or on a provider window, which is
    neither progress nor a defect.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="continuation.py",
        description="Derive coordinator state from a declaration and the artifacts.",
    )
    parser.add_argument("record", help="path to the continuation record")
    parser.add_argument("--relative-to", default=None, metavar="DIR",
                        help="base for relative paths in the record; defaults to its directory")
    args = parser.parse_args(argv)

    record = load(args.record)
    base = args.relative_to or Path(args.record).parent
    report = derive(record, relative_to=base)
    print(report.render())

    if report.state in (State.COMPLETED_NOT_CONSUMED, State.SILENT_IDLE):
        return 1
    if report.state == State.RECOVERY_REQUIRED:
        return 2
    if report.state in (State.BLOCKED_ON_HUMAN, State.BLOCKED_ON_CAPACITY):
        return 3
    return 0


if __name__ == "__main__":
    import sys

    # Run the module, not a second copy of it. A file executed as a script is
    # `__main__`, and a sibling that imports it BY NAME gets a separate module
    # object with separate class objects — so an `isinstance` check across that
    # boundary is False for an object that is exactly that class. Imported
    # statically, by name, because a dynamic import would route around the
    # toolbelt's import-closure check.
    from errors import run_cli
    from continuation import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
