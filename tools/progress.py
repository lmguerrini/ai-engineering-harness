"""A worker that exists is not a worker that is working, and one signal is worse.

Two measurements, four minutes apart in the same phase, and they point in
opposite directions:

*   **A worker that existed for thirty-one minutes and did nothing.** 30m50s
    elapsed, 0.05 seconds of processor time, zero log bytes, no provider rollout
    at all — beside a previous run's complete one. Process existence had been
    read as progress, and it was not.
*   **A healthy worker that looked exactly like it.** Over four minutes with no
    log output while its processor time climbed 3.81 → 4.05 → 4.14 seconds. It
    was working the whole time. A detector reading the log alone would have
    called it stalled, and the action a stall invites destroys work.

So the model is a **disjunction**, and that is a safety property rather than a
completeness one: *any* observed signal advancing means running. It follows that
a stall can only be asserted when several independent signals agree, and this
module refuses to assert one from a single kind of observation at all. `UNKNOWN`
is the answer there, and it is the correct one — the alternative was measured
killing recoverable work.

## What this module does not do

**It never terminates anything.** Ending a worker is the only destructive act in
this whole area, its false-positive rate is measured rather than theoretical,
and it sits on `policy/hitl-matrix.md` row 4. This classifies; a person decides.
`STALLED` here means *these signals were flat for longer than the horizon you
declared*, and the report says which signals were even available to be flat.

**It has no opinion on the horizon.** How long is too long depends on the task
class and on the backend, both of which change. The caller declares it, the
report states it, and a horizon nobody declared is a refusal rather than a
default — a built-in number would be wrong exactly where it mattered.

## Waiters

One worker acquired three coordinator-owned waiters. Each waited on a pattern
that matched the others' own command lines, so `until ! pgrep -f <pattern>`
could never terminate while any sibling lived: a quorum reporting RUNNING
indefinitely, and four notifications that fired after the job had already
exited.

Two rules follow, and both are enforced here rather than described. **A run is a
registered identity, never a pattern**: patterns match whatever happens to look
like them, including the watcher. And **a waiter whose own command line matches
its own pattern is refused at construction**, because observing it hang later is
too late to be useful.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from errors import IntegrityError, PreconditionError

__all__ = [
    "SignalKind",
    "Sample",
    "ProgressState",
    "ProgressReport",
    "classify",
    "Waiter",
    "retire_waiters",
    "MINIMUM_AGREEING_SIGNALS",
]

#: How many independently sourced signals must agree before a stall may be
#: asserted. Two, and the number is the measurement rather than a preference: a
#: single-signal detector was observed calling a healthy worker stalled while
#: its processor time climbed.
MINIMUM_AGREEING_SIGNALS = 2


class SignalKind:
    """What can be observed about a run, and where each comes from.

    Each is a *monotonic* quantity — it only goes up while work happens — so
    "advanced" is a comparison of two readings and needs no interpretation.
    """

    #: Bytes in the run's log. The cheapest, and the one that produced the
    #: measured false positive on its own.
    LOG_BYTES = "log_bytes"
    #: Processor seconds consumed. The best discriminator in the measured pair —
    #: 0.05s over thirty-one minutes against 4.14s over four — and the one this
    #: module cannot read for itself, because reading another process's
    #: accounting means launching something and that is the caller's declared
    #: blast radius, not this module's.
    CPU_SECONDS = "cpu_seconds"
    #: Bytes under the task's own output root.
    OUTPUT_BYTES = "output_bytes"
    #: Completed chunks in the task's output root.
    CHECKPOINTS = "checkpoints"
    #: Whatever the executing backend exposes as its own progress surface. An
    #: adapter fact, supplied rather than assumed.
    PROVIDER_ROLLOUT = "provider_rollout"

    ALL = (LOG_BYTES, CPU_SECONDS, OUTPUT_BYTES, CHECKPOINTS, PROVIDER_ROLLOUT)


class ProgressState:
    RUNNING = "RUNNING"
    #: Every observed signal was flat for longer than the declared horizon. A
    #: classification, never an instruction: ending a worker is row 4.
    STALLED = "STALLED"
    #: The job is over. Nothing to watch.
    COMPLETE = "COMPLETE"
    #: Too little was observed to say. Includes the case that matters most —
    #: only one kind of signal was available — because that is where a detector
    #: kills healthy work.
    UNKNOWN = "UNKNOWN"

    ALL = (RUNNING, STALLED, COMPLETE, UNKNOWN)


@dataclass(frozen=True)
class Sample:
    """One reading of a run's monotonic signals, with the moment it was taken.

    A signal absent from ``signals`` was **not observed**; a signal present with
    value zero **was observed and was zero**. Conflating those is how a
    measurement that read nothing gets reported as a result.
    """

    at_seconds: float
    signals: Mapping[str, float]

    def __post_init__(self) -> None:
        if not isinstance(self.at_seconds, (int, float)) or isinstance(self.at_seconds, bool):
            raise IntegrityError("a sample is taken at a time", at_seconds=repr(self.at_seconds))
        for kind, value in self.signals.items():
            if kind not in SignalKind.ALL:
                raise IntegrityError("no such progress signal", kind=repr(kind),
                                     known=", ".join(SignalKind.ALL))
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise IntegrityError("a progress signal is a non-negative quantity",
                                     kind=kind, value=repr(value))
            # Finiteness BEFORE the sign, and the order is the repair: every
            # comparison against a NaN is false, so `value < 0` let one through
            # and two NaN readings then produced STALLED with **zero** flat
            # signals named in the report — a verdict with nothing behind it.
            # Found by a cross-vendor auditor, and the same root cause as the
            # capacity gate's. Checking the sign first would also give an
            # infinity a message about negativity, which describes the wrong
            # defect.
            if not math.isfinite(value):
                raise IntegrityError(
                    "a progress signal is finite; a non-finite reading is neither flat nor "
                    "advancing, so it would produce a stall with no flat signal behind it",
                    kind=kind, value=repr(value),
                )
            if value < 0:
                raise IntegrityError("a progress signal is a non-negative quantity",
                                     kind=kind, value=repr(value))

    @property
    def observed(self) -> tuple[str, ...]:
        return tuple(sorted(self.signals))


@dataclass(frozen=True)
class ProgressReport:
    run_id: str
    state: str
    why: str
    horizon_seconds: float
    elapsed_seconds: float
    #: How long the run has been without observed progress. This, not the gap
    #: between the samples, is what the horizon is compared against.
    flat_for_seconds: float = 0.0
    advanced: tuple[str, ...] = ()
    flat: tuple[str, ...] = ()
    #: Signals present in one sample and not the other. Not evidence either way,
    #: and named so a reader can see the comparison was partial.
    incomparable: tuple[str, ...] = ()
    #: Monotonic signals that went backwards. A broken instrument, never a quiet
    #: run, and never counted among the flat ones that produce a stall.
    regressed: tuple[str, ...] = ()

    def render(self) -> str:
        lines = [f"run {self.run_id}: {self.state}", f"  {self.why}"]
        lines.append(f"  flat for {self.flat_for_seconds:.0f}s against a declared horizon of "
                     f"{self.horizon_seconds:.0f}s "
                     f"({self.elapsed_seconds:.0f}s between the two readings)")
        for label, values in (("advanced", self.advanced), ("flat", self.flat),
                              ("observed in only one sample", self.incomparable),
                              ("WENT BACKWARDS, so the instrument is untrustworthy", self.regressed)):
            if values:
                lines.append(f"  {label}: {', '.join(values)}")
        if self.state == ProgressState.STALLED:
            lines.append("  this is a classification, not an instruction: ending a worker is a "
                         "human decision (policy/hitl-matrix.md row 4)")
        return "\n".join(lines)


def classify(
    run_id: str,
    earlier: Sample,
    later: Sample,
    *,
    horizon_seconds: float,
    flat_since_seconds: float,
    finished: bool = False,
) -> ProgressReport:
    """One of four answers about a run, from two readings of its signals.

    The disjunction is the safety property: **any** signal that advanced means
    running, however many others were flat. The mirror rule is what makes the
    disjunction honest — a stall needs several independent signals to agree, and
    with fewer than that the answer is `UNKNOWN`.

    **The horizon applies to how long the run has been without progress, not to
    the gap between the two samples**, and getting that wrong made this module
    miss the exact incident it was built for. Sampling a run 90 seconds apart
    against a 900-second horizon returned `RUNNING` for a dispatch that had
    produced nothing in five hours and thirty-nine minutes — because 90 is less
    than 900. **A caller that samples periodically could never obtain a stall
    verdict at all.**

    So `flat_since_seconds` is required and has no default: it is the moment, on
    the same clock as the samples, at or after which nothing is known to have
    advanced — the run's start, or the last reading that moved. A caller with
    only two samples passes the earlier one's time, which reproduces the old
    arithmetic *visibly*: the report then says "flat for 90s", and a reader can
    see the claim is about ninety seconds rather than about the run.
    """
    if not isinstance(horizon_seconds, (int, float)) or isinstance(horizon_seconds, bool) or horizon_seconds <= 0:
        raise PreconditionError(
            "a stall horizon is declared by the caller and stated in the report; how long is too "
            "long depends on the task class and the backend, and a built-in number would be wrong "
            "exactly where it mattered",
            run_id=run_id, declared=repr(horizon_seconds),
        )
    elapsed = later.at_seconds - earlier.at_seconds
    if elapsed < 0:
        raise IntegrityError("the later sample is earlier than the earlier one",
                             run_id=run_id, elapsed=elapsed)
    if (not isinstance(flat_since_seconds, (int, float)) or isinstance(flat_since_seconds, bool)
            or not math.isfinite(flat_since_seconds)):
        raise PreconditionError(
            "a stall verdict is about how long the run has been without progress, so the moment "
            "it was last known to advance is required. Measuring the horizon against the gap "
            "between two samples means a caller who polls can never see a stall",
            run_id=run_id, given=repr(flat_since_seconds),
        )
    flat_for = later.at_seconds - float(flat_since_seconds)
    if flat_for < 0:
        raise IntegrityError(
            "the run is recorded as last advancing after the sample that observed it",
            run_id=run_id, flat_for=flat_for)

    common = sorted(set(earlier.signals) & set(later.signals))
    incomparable = tuple(sorted(set(earlier.signals) ^ set(later.signals)))
    advanced = tuple(k for k in common if later.signals[k] > earlier.signals[k])
    flat = tuple(k for k in common if later.signals[k] == earlier.signals[k])
    # Every signal here is documented monotonic, so a reading that went DOWN is
    # a broken instrument — a rotated log, a reset counter, a second writer —
    # and folding it into "flat" tells a reader the run was quiet when the truth
    # is that the measurement is untrustworthy.
    regressed = tuple(k for k in common if later.signals[k] < earlier.signals[k])

    base = dict(run_id=run_id, horizon_seconds=float(horizon_seconds),
                elapsed_seconds=float(elapsed), flat_for_seconds=float(flat_for),
                advanced=advanced, flat=flat,
                incomparable=incomparable, regressed=regressed)

    if finished:
        return ProgressReport(**base, state=ProgressState.COMPLETE,
                              why="the run is over; there is nothing left to watch")

    if advanced:
        return ProgressReport(**base, state=ProgressState.RUNNING, why=(
            f"{', '.join(advanced)} advanced, so the run is working whatever the others did; "
            "a healthy worker was measured silent on its log for over four minutes while its "
            "processor time climbed"))

    if regressed:
        return ProgressReport(**base, state=ProgressState.UNKNOWN, why=(
            f"{', '.join(regressed)} went backwards, and every one of these is documented "
            "monotonic; a reading that decreases is a broken instrument rather than a quiet run"))

    if not common:
        return ProgressReport(**base, state=ProgressState.UNKNOWN, why=(
            "no signal was observed in both samples, so nothing was compared; a measurement that "
            "read nothing is not a result"))

    if len(common) < MINIMUM_AGREEING_SIGNALS:
        return ProgressReport(**base, state=ProgressState.UNKNOWN, why=(
            f"only {common[0]} was observable, and a single flat signal is the measured false "
            f"positive rather than evidence of a stall; observe a second kind before asking again"))

    if flat_for < horizon_seconds:
        return ProgressReport(**base, state=ProgressState.RUNNING, why=(
            f"every observed signal is flat and the run has been without progress for only "
            f"{flat_for:.0f}s against a declared horizon of {horizon_seconds:.0f}s; flat is not "
            "yet stalled"))

    return ProgressReport(**base, state=ProgressState.STALLED, why=(
        f"{len(flat)} independently observed signals were all flat, and the run has been without "
        f"progress for {flat_for:.0f}s, which exceeds the declared horizon"))


# --- waiters ---------------------------------------------------------------------


@dataclass(frozen=True)
class Waiter:
    """A watcher on one registered run.

    ``run_id`` is a registered handle and not a pattern. A pattern matches
    whatever happens to look like it — including the watcher's own command line,
    which is how three waiters on one worker formed a quorum that could never
    terminate.
    """

    waiter_id: str
    run_id: str
    #: The command line this waiter itself runs as, when it is a process. Given
    #: so the self-match below can be refused at construction rather than
    #: observed hanging later.
    own_command: str = ""
    #: An optional pattern the waiter uses to look for its run. Discouraged, and
    #: checked hard when present.
    match_pattern: str = ""
    retired: bool = False

    def __post_init__(self) -> None:
        if not (self.waiter_id or "").strip() or not (self.run_id or "").strip():
            raise IntegrityError("a waiter names itself and the run it watches",
                                 waiter_id=repr(self.waiter_id), run_id=repr(self.run_id))
        if self.match_pattern:
            try:
                compiled = re.compile(self.match_pattern)
            except re.error as exc:
                raise IntegrityError("a waiter's match pattern is not a regex",
                                     pattern=self.match_pattern, error=str(exc)) from exc
            if self.own_command and compiled.search(self.own_command):
                raise PreconditionError(
                    "this waiter's own command line matches its own pattern, so it can never "
                    "observe its run end: three such waiters on one worker formed a quorum that "
                    "reported RUNNING indefinitely and fired four times after the job had exited",
                    waiter_id=self.waiter_id, pattern=self.match_pattern,
                    own_command=self.own_command,
                )


def waiter_command(run_id: str, pid: int, *, sentinel: str, poll_seconds: int = 20) -> list[str]:
    """A wait command that watches a REGISTERED IDENTITY and cannot match itself.

    Provided because the reason a coordinator hand-writes one is that the pack
    did not ship one, and a hand-written one did exactly what `Waiter` refuses:
    `until [ -s report ] && ! pgrep -qf "codex exec"` had its own pattern in its
    own command line, so `pgrep` matched the waiter and the loop could never
    terminate — **even after the worker exited**. Measured live, in this
    release's own session.

    This watches a process NUMBER, which nothing else can accidentally be, and a
    sentinel path. `kill -0` asks whether the number exists without signalling
    anything, so the wait is an observation and not an act.
    """
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        raise IntegrityError("a waiter watches a real process number", run_id=run_id, pid=repr(pid))
    if not (sentinel or "").strip():
        raise IntegrityError("a waiter needs the path whose appearance ends it", run_id=run_id)
    return ["sh", "-c",
            f'while kill -0 {pid} 2>/dev/null && [ ! -s "{sentinel}" ]; do sleep {poll_seconds}; done']


def retire_waiters(waiters: Sequence[Waiter], *, finished_runs: Sequence[str]) -> tuple[Waiter, ...]:
    """Every waiter on a finished run retires, on **any** terminal state.

    Not only on success. A waiter that exits cleanly on success and hangs on
    failure is a waiter that is armed precisely when something has gone wrong,
    and a late fire is then readable as current state.
    """
    done = set(finished_runs)
    return tuple(
        Waiter(waiter_id=w.waiter_id, run_id=w.run_id, own_command=w.own_command,
               match_pattern=w.match_pattern, retired=w.retired or w.run_id in done)
        for w in waiters
    )


def _cli(argv: list[str]) -> int:
    """Classify a run from two readings of its signals.

    Usage: ``progress.py RUN_ID --horizon SECONDS --flat-since AT
                         --earlier AT KIND=VALUE... --later AT KIND=VALUE...``

    Exit status follows the answer: ``0`` running or complete, ``1`` stalled,
    ``2`` unknown. Stalled is `1` rather than `0` because it is owed an
    inspection; it is not `2` because it is a verdict that was reached.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="progress.py",
        description="Classify a run's progress from two readings of its monotonic signals.",
    )
    parser.add_argument("run_id")
    parser.add_argument("--horizon", type=float, required=True, metavar="SECONDS",
                        help="how long the run may be without progress before this is a stall")
    parser.add_argument("--flat-since", type=float, required=True, metavar="AT",
                        help="the time, on the samples' clock, the run was last known to advance")
    parser.add_argument("--earlier", nargs="+", required=True, metavar="AT|KIND=VALUE",
                        help="the earlier reading: a time, then KIND=VALUE pairs")
    parser.add_argument("--later", nargs="+", required=True, metavar="AT|KIND=VALUE")
    parser.add_argument("--finished", action="store_true", help="the run is over")
    args = parser.parse_args(argv)

    def _sample(parts: list[str]) -> Sample:
        try:
            at = float(parts[0])
        except ValueError as exc:
            raise IntegrityError("a reading starts with the time it was taken",
                                 given=parts[0]) from exc
        signals: dict[str, float] = {}
        for pair in parts[1:]:
            if "=" not in pair:
                raise IntegrityError("a signal is KIND=VALUE", given=pair)
            kind, _, value = pair.partition("=")
            try:
                signals[kind] = float(value)
            except ValueError as exc:
                raise IntegrityError("a signal value is a number", kind=kind, given=value) from exc
        return Sample(at_seconds=at, signals=signals)

    report = classify(args.run_id, _sample(args.earlier), _sample(args.later),
                      horizon_seconds=args.horizon, flat_since_seconds=args.flat_since,
                      finished=args.finished)
    print(report.render())
    if report.state == ProgressState.STALLED:
        return 1
    if report.state == ProgressState.UNKNOWN:
        return 2
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
    from progress import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
