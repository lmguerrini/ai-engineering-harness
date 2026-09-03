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
import os
import re
from dataclasses import dataclass
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
    pid: int | None = None
    path: str | None = None
    task_id: str | None = None
    max_bytes_per_write: int | None = None
    declared_at: str = ""
    #: Set once the coordinator has taken the result up. An unconsumed
    #: completion is the state this whole module exists to name.
    consumed: bool = False

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

    def as_dict(self) -> dict:
        return {
            "capability": self.capability,
            "updated_at": self.updated_at,
            "actionable": list(self.actionable),
            "waits": [wait.as_dict() for wait in self.waits],
            "blockers": [blocker.__dict__ for blocker in self.blockers],
            "terminal": self.terminal,
            "record_path": self.record_path,
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


def _observe(wait: Wait, *, relative_to: Path) -> WaitObservation:
    if wait.kind == WaitKind.HUMAN:
        return WaitObservation(wait.job_id, None, "a person resolves this; no machine can observe it")

    if wait.kind == WaitKind.PROCESS:
        finished, how = _process_is_gone(int(wait.pid))
        return WaitObservation(wait.job_id, finished, how)

    target = Path(wait.path)
    if not target.is_absolute():
        target = relative_to / target

    if wait.kind in (WaitKind.EXIT_FILE, WaitKind.PATH_EXISTS):
        if target.exists():
            detail = ""
            if wait.kind == WaitKind.EXIT_FILE:
                try:
                    detail = f", status {target.read_text(encoding='utf-8').strip()[:16]}"
                except OSError as exc:
                    return WaitObservation(wait.job_id, None,
                                           f"{target} exists and cannot be read: {exc}")
            return WaitObservation(wait.job_id, True, f"{target} exists{detail}")
        return WaitObservation(wait.job_id, False, f"{target} has not appeared")

    contract = task_output.OutputContract(
        task_id=wait.task_id, output_root=target,
        max_bytes_per_write=int(wait.max_bytes_per_write),
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
    actionable: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    @property
    def wake_required(self) -> bool:
        return bool(self.unconsumed) or self.state in (
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
        for label, values in (("unconsumed", self.unconsumed), ("cannot be observed", self.unobservable),
                              ("superseded, retire it", self.superseded)):
            if values:
                lines.append(f"  {label}: {', '.join(values)}")
        for blocker in self.blockers:
            lines.append(f"  blocked: {blocker}")
        if self.actionable:
            lines.append(f"  authorised and outstanding: {len(self.actionable)} item(s)")
        return "\n".join(lines)


def derive(record: ContinuationRecord, *, relative_to: str | Path = ".") -> LivenessReport:
    """The current state, computed from the declaration and the artifacts.

    Order matters and is not arbitrary. Anything that cannot be established
    outranks anything that can, because acting on an unestablished state is the
    error class this pack exists to refuse. A completed-and-unconsumed result
    outranks a remaining wait, because that is the edge four of five recurrences
    were and burying it under "still waiting on something else" is how it
    stayed invisible.
    """
    base = Path(relative_to)
    observations = tuple(_observe(wait, relative_to=base) for wait in record.waits)
    by_id = {wait.job_id: wait for wait in record.waits}

    unobservable = tuple(
        o.job_id for o in observations
        if o.unobservable and by_id[o.job_id].kind != WaitKind.HUMAN
    )
    finished = [o for o in observations if o.finished]
    unconsumed = tuple(o.job_id for o in finished if not by_id[o.job_id].consumed)
    superseded = tuple(o.job_id for o in finished if by_id[o.job_id].consumed)
    running = tuple(o.job_id for o in observations if o.finished is False)
    human_waits = tuple(w.job_id for w in record.waits if w.kind == WaitKind.HUMAN)

    human = [b for b in record.blockers if b.kind == "human"]
    capacity = [b for b in record.blockers if b.kind == "capacity"]
    blocker_lines = tuple(
        f"{b.kind}: {b.detail}" + (f" (row {b.hitl_row})" if b.hitl_row else "")
        + (f" (pool {b.pool_id})" if b.pool_id else "")
        for b in record.blockers
    )

    common = dict(
        capability=record.capability, observations=observations, unconsumed=unconsumed,
        unobservable=unobservable, superseded=superseded,
        actionable=tuple(record.actionable), blockers=blocker_lines,
    )

    if unobservable:
        return LivenessReport(**common, state=State.RECOVERY_REQUIRED, why=(
            "a declared wait names no completion anyone can observe, or names one that can no "
            "longer be read; that is the shape that decayed into silence and it is not waited out"))

    if unconsumed:
        return LivenessReport(**common, state=State.COMPLETED_NOT_CONSUMED, why=(
            f"{len(unconsumed)} job(s) finished and nothing has taken the result up; this is the "
            "edge four of five recorded recurrences were"))

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

    if record.actionable:
        return LivenessReport(**common, state=State.SILENT_IDLE, why=(
            f"{len(record.actionable)} authorised item(s) are outstanding, nothing is declared to "
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
            actionable=tuple(raw.get("actionable") or ()),
            waits=tuple(Wait(**entry) for entry in raw.get("waits") or ()),
            blockers=tuple(Blocker(**entry) for entry in raw.get("blockers") or ()),
            terminal=bool(raw.get("terminal", False)),
            record_path=raw.get("record_path", ""),
        )
    except (KeyError, TypeError) as exc:
        raise PreconditionError("the continuation record is malformed",
                                path=str(target), error=str(exc)) from exc


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
