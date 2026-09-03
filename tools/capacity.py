"""A refusal before a dispatch, not a queue that dispatches.

Eight workers went out in two waves drawn from the coordinator's own rolling
window. Two came back complete, three partial, three with nothing. **Eighty-one
records were lost**, and the rule that produced the wave was not careless — it
was a recorded routing rule, *default to the worker*, which had been correct
every previous time because the pools had always been independent. It had never
stated that precondition, because the precondition had never been false.

Weekly capacity was never the binding constraint. The rolling session window
was, and six of eight workers died on it.

So this module exists to answer one question before one dispatch: **given what
is known about this pool, is issuing this dispatch safe?** It holds no queue, it
has no dispatch verb, and it never decides what to run next. The frozen record
forbids a scheduler and this is not one: a queue that later drains is a
scheduler however it is described.

## What it will not invent

There is **no universal reserve percentage here, and there will not be one.** A
number that fits one provider's window is wrong for another's, and a wrong one
fails in both directions — too low reproduces the loss, too high strands
capacity that had no other use. The project declares its reserves and this
module enforces them.

`UNKNOWN` is a first-class reading and the common one: one of the two providers
in the evidence base had **no machine-readable capacity surface at all**. A gate
that cannot represent `UNKNOWN` will invent a number, so this one represents it
and becomes **conservative** rather than precise — serial dispatch on that pool
and no fan-out. It does not refuse outright, because a gate that deadlocks
whenever telemetry is absent is a gate a coordinator routes around.

## Authority does not move

`policy/hitl-matrix.md` row 15 governs wait-versus-spend, and **the wait-versus-
spend branch is not automated here.** A dispatch that carries a semantic or
product decision may go to the executor class it was classed for and nowhere
else, whatever is still answering. Rerouting it under resource pressure is
refused, not preferred against.

That rule was asserted once with no field on a task to hang it on, so the
rehearsal that tested it could only pass on a hand-labelled fixture. It is a
**precondition** here: a dispatch that does not state its authority class is
refused before anything else is considered.

## Not dispatched is not dispatched-and-lost

Three of the eight were the second. A record that cannot tell them apart cannot
learn anything from either, so the outcome vocabulary keeps them separate and
`IN_FLIGHT` distinct from both.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Sequence

from errors import IntegrityError, PreconditionError

__all__ = [
    "UNKNOWN",
    "PoolKind",
    "WindowKind",
    "Pool",
    "Reserve",
    "AuthorityClass",
    "Dispatch",
    "Verdict",
    "Decision",
    "DispatchOutcome",
    "gate",
]

#: Not a number, not zero, and never estimated into one.
UNKNOWN = "UNKNOWN"


def _moment(text: str) -> "datetime | None":
    """An ISO-8601 instant, or None. Naive input is read as UTC."""
    try:
        parsed = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class PoolKind:
    #: Drawn from the same window the coordinator itself consumes. The failure
    #: mode: spending it can leave nothing to read the result with.
    SHARED_WITH_COORDINATOR = "shared_with_coordinator"
    #: A genuinely separate quota. The reason the recovery routing worked.
    INDEPENDENT = "independent"
    UNKNOWN = UNKNOWN

    ALL = (SHARED_WITH_COORDINATOR, INDEPENDENT, UNKNOWN)


class WindowKind:
    ROLLING = "rolling"
    WEEKLY = "weekly"
    UNKNOWN = UNKNOWN

    ALL = (ROLLING, WEEKLY, UNKNOWN)


class AuthorityClass:
    #: The task carries no semantic or product decision, so which executor runs
    #: it is a routing question.
    AUTHORITY_FREE = "authority_free"
    #: The task carries a decision. It goes where it was classed to go, and
    #: nowhere else, whatever is still answering.
    CARRIES_AUTHORITY = "carries_authority"

    ALL = (AUTHORITY_FREE, CARRIES_AUTHORITY)


class Verdict:
    DISPATCH = "DISPATCH"
    #: Allowed, and only one at a time on this pool. What `UNKNOWN` earns.
    #:
    #: A blind reader called this a violation of the no-evidence rule: the gate
    #: answers *may dispatch* with five unknowns behind it. **The verdict is
    #: deliberate and it is kept.** No machine-readable quota surface is the
    #: ORDINARY case for the providers this pack routes to, and a gate that
    #: refused every dispatch it could not compute would refuse all of them —
    #: which is not conservatism, it is unusability, and the coordinator would
    #: route around it within a day.
    #:
    #: What UNKNOWN buys is the most conservative posture that still permits
    #: work: one at a time, so an unmeasured window cannot be drained in
    #: parallel, and every unknown named in the decision. The reader's point is
    #: answered by disclosure rather than by refusal, and `why` now says
    #: explicitly when NO arithmetic was performed at all — which is a different
    #: statement from arithmetic that came out favourable.
    DISPATCH_SERIALLY = "DISPATCH_SERIALLY"
    REFUSE = "REFUSE"
    #: The pool is spent. Names the reset horizon, or says it is unknown.
    REFUSE_UNTIL_RESET = "REFUSE_UNTIL_RESET"
    #: A human decision under row 15. This module does not take it.
    ESCALATE_ROW_15 = "ESCALATE_ROW_15"

    ALL = (DISPATCH, DISPATCH_SERIALLY, REFUSE, REFUSE_UNTIL_RESET, ESCALATE_ROW_15)


class DispatchOutcome:
    """What became of a dispatch. Four answers, and the first two are the ones
    a two-valued record conflates.

    **Produced, not merely enumerated.** An auditor observed that nothing in the
    release wrote or read any of these values and that the only test restated
    the class definition — *an assertion that would pass unchanged if the
    mechanism it names were deleted, because there was no mechanism.* So
    `Decision.outcome` derives one: a refusal is `NOT_DISPATCHED`, and a
    permitted dispatch is `IN_FLIGHT` until a caller records what became of it.
    The two the record must never conflate are then produced by different
    parties at different times, which is the distinction they exist for.
    """

    NOT_DISPATCHED = "NOT_DISPATCHED"
    DISPATCHED_AND_LOST = "DISPATCHED_AND_LOST"
    DISPATCHED_AND_CONSUMED = "DISPATCHED_AND_CONSUMED"
    IN_FLIGHT = "IN_FLIGHT"

    ALL = (NOT_DISPATCHED, DISPATCHED_AND_LOST, DISPATCHED_AND_CONSUMED, IN_FLIGHT)


def _quantity(value: object, *, field: str) -> float | str:
    """A non-negative number, or `UNKNOWN`. Nothing in between."""
    if value == UNKNOWN or value is None:
        return UNKNOWN
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise IntegrityError(
            f"{field} is a non-negative quantity or UNKNOWN; a guess dressed as a number is the "
            "thing this module exists not to produce",
            found=repr(value),
        )
    # Checked BEFORE the sign, because every comparison against a NaN is False:
    # `NaN < 0` is False, so a NaN passed the sign check, and then
    # `remaining - cost < reserve` was False too and the gate DISPATCHED an
    # unmeasurable pool. Found by a cross-vendor auditor. `gitread` already
    # refuses a non-finite timeout for exactly this reason and the rule was not
    # carried across.
    if not math.isfinite(value):
        raise IntegrityError(
            f"{field} is not a finite number, and every comparison against it is false — so it "
            "would pass every guard below rather than fail one. UNKNOWN is how this module says "
            "it does not know",
            found=repr(value),
        )
    if value < 0:
        raise IntegrityError(f"{field} is a non-negative quantity or UNKNOWN", found=repr(value))
    return float(value)


@dataclass(frozen=True)
class Pool:
    """One quota window, as it was last observed.

    ``observed_at`` matters as much as ``remaining``: a reading is evidence
    about the moment it was taken, it carries its own age, and it licenses no
    claim about what the next dispatch will cost.
    """

    pool_id: str
    kind: str = PoolKind.UNKNOWN
    window: str = WindowKind.UNKNOWN
    #: Units left, in whatever the provider counts. `UNKNOWN` is the ordinary
    #: case for a provider with no machine-readable surface.
    remaining: float | str = UNKNOWN
    unit: str = "units"
    #: When the window refills, if that is observable. Surfaced so a coordinator
    #: can reason about it; this module encodes no preference, because "spend it
    #: before it resets" is a routing judgement and not a safety rule.
    resets_at: str | None = None
    observed_at: str | None = None
    #: Dispatches already running against this pool.
    active_workers: int = 0

    def __post_init__(self) -> None:
        if not (self.pool_id or "").strip():
            raise IntegrityError("a pool has an id; an unnamed window cannot be reasoned about")
        if self.kind not in PoolKind.ALL:
            raise IntegrityError("no such pool kind", kind=repr(self.kind),
                                 known=", ".join(PoolKind.ALL))
        if self.window not in WindowKind.ALL:
            raise IntegrityError("no such window kind", window=repr(self.window),
                                 known=", ".join(WindowKind.ALL))
        object.__setattr__(self, "remaining", _quantity(self.remaining, field="remaining"))
        if not isinstance(self.active_workers, int) or isinstance(self.active_workers, bool) or self.active_workers < 0:
            raise IntegrityError("active_workers is a count", found=repr(self.active_workers))

        # A NUMBER WITH NO MOMENT IS NOT A READING. The docstring two lines up
        # says `observed_at` matters as much as `remaining`, and the class
        # accepted a bare `remaining=100` and gated on it with no unknowns
        # recorded — a figure with no age, which is the one property that
        # distinguishes a measurement from an assertion. Found by a blind
        # auditor quoting this class's own contract back at it.
        #
        # `UNKNOWN` needs no timestamp: it is already the answer this module
        # gives when it does not know, and dating it would suggest otherwise.
        if self.remaining != UNKNOWN:
            # NOT MERELY NON-BLANK. The first version tested for a non-empty
            # string, so `--observed-at not-a-time` dispatched and an integer
            # raised a bare `AttributeError` — a required field nobody can read
            # is a required field in name only, which is what a blind reader
            # said about it.
            moment = self.observed_at if isinstance(self.observed_at, str) else None
            parsed = _moment(moment) if moment else None
            if parsed is None:
                raise IntegrityError(
                    "a numeric capacity reading states WHEN it was taken, as a timestamp that can "
                    "be read. A reading is evidence about a moment, and one whose moment cannot "
                    "be parsed can be neither aged nor compared",
                    pool_id=self.pool_id, remaining=repr(self.remaining),
                    observed_at=repr(self.observed_at),
                )
    @property
    def known(self) -> bool:
        return self.remaining != UNKNOWN


@dataclass(frozen=True)
class Reserve:
    """What is held back, declared by the project rather than by this module.

    Three distinct reserves because they are spent at three different moments
    and one of them was asked for and never instrumented. Any may be `UNKNOWN`,
    and `UNKNOWN` makes the total unknown rather than zero.
    """

    #: What the coordinator needs to keep working at all.
    coordinator: float | str = UNKNOWN
    #: What reading and verifying the result will cost. A result that cannot be
    #: consumed is negative return however cheap it was to produce.
    result_consumption: float | str = UNKNOWN
    #: Repairs and the audits a closure requires. An audit that is unaffordable
    #: at close is an audit that will be skipped at close.
    repair_and_audit: float | str = UNKNOWN

    def __post_init__(self) -> None:
        for name in ("coordinator", "result_consumption", "repair_and_audit"):
            object.__setattr__(self, name, _quantity(getattr(self, name), field=name))

    @property
    def total(self) -> float | str:
        parts = [self.coordinator, self.result_consumption, self.repair_and_audit]
        if any(part == UNKNOWN for part in parts):
            return UNKNOWN
        return sum(parts)

    @property
    def declared(self) -> bool:
        return self.total != UNKNOWN


@dataclass(frozen=True)
class Dispatch:
    """One proposed dispatch, and what it would cost."""

    task_id: str
    pool_id: str
    #: **A precondition.** The rule that authority attaches to the task and not
    #: to the route was once asserted with no field on a task to hang it on, so
    #: the rehearsal that tested it could only pass on a hand-labelled fixture.
    authority_class: str = ""
    allowed_executor_class: str = ""
    allowed_fallback_routes: tuple[str, ...] = ()
    estimated_cost: float | str = UNKNOWN
    #: What it will cost to read and verify the result. Separate from the cost
    #: of producing it, because they are spent at different moments and only
    #: the second decides whether the first was worth anything.
    result_consumption_cost: float | str = UNKNOWN
    #: The executor this dispatch would actually go to, when it differs from
    #: the class it was declared for. Naming one is a reroute request.
    reroute_to: str | None = None

    def __post_init__(self) -> None:
        if not (self.task_id or "").strip():
            raise IntegrityError("a dispatch names its task")
        if self.authority_class not in AuthorityClass.ALL:
            raise PreconditionError(
                "a dispatch states its authority class before anything else is considered: "
                "authority attaches to the TASK, not to the route, and a rule with no field to "
                "hang it on can only be tested on a hand-labelled fixture",
                task_id=self.task_id, found=repr(self.authority_class),
                known=", ".join(AuthorityClass.ALL),
            )
        if not (self.allowed_executor_class or "").strip():
            raise PreconditionError(
                "a dispatch names the executor class it was classed for",
                task_id=self.task_id,
            )
        object.__setattr__(self, "estimated_cost", _quantity(self.estimated_cost, field="estimated_cost"))
        object.__setattr__(self, "result_consumption_cost",
                           _quantity(self.result_consumption_cost, field="result_consumption_cost"))


@dataclass(frozen=True)
class Decision:
    task_id: str
    verdict: str
    why: str
    pool_id: str = ""
    #: Everything that could not be established. Named, so a reader can see
    #: which parts of the arithmetic were done and which were skipped.
    unknowns: tuple[str, ...] = ()
    resets_at: str | None = None

    @property
    def may_dispatch(self) -> bool:
        return self.verdict in (Verdict.DISPATCH, Verdict.DISPATCH_SERIALLY)

    @property
    def outcome(self) -> str:
        """The outcome this decision produces, before anything runs.

        A refusal is `NOT_DISPATCHED` and nothing else can make it one later; a
        permitted dispatch is `IN_FLIGHT` until whoever ran it records
        `DISPATCHED_AND_CONSUMED` or `DISPATCHED_AND_LOST`. Three of eight
        dispatches were the second, and a record that cannot tell *not
        dispatched* from *dispatched and lost* cannot learn from either.
        """
        return DispatchOutcome.IN_FLIGHT if self.may_dispatch else DispatchOutcome.NOT_DISPATCHED

    def render(self) -> str:
        lines = [f"dispatch {self.task_id} on pool {self.pool_id or UNKNOWN}: {self.verdict}",
                 f"  {self.why}", f"  outcome so far: {self.outcome}"]
        if self.unknowns:
            lines.append(f"  not established: {', '.join(self.unknowns)}")
        if self.verdict == Verdict.REFUSE_UNTIL_RESET:
            lines.append(f"  the window resets at: {self.resets_at or UNKNOWN}")
        return "\n".join(lines)


def gate(dispatch: Dispatch, pool: Pool, reserve: Reserve) -> Decision:
    """Whether issuing this dispatch is safe, given what is known.

    Order is deliberate. Authority first, because no amount of capacity makes
    rerouting a decision acceptable. Then the arithmetic where it can be done,
    then the conservative posture where it cannot. Nothing here queues, retries
    or chooses what to run next.
    """
    if dispatch.pool_id != pool.pool_id:
        raise IntegrityError(
            "this dispatch was measured against a different pool than the one it names",
            task_id=dispatch.task_id, dispatch_pool=dispatch.pool_id, measured=pool.pool_id,
        )

    unknowns = []
    if not pool.known:
        unknowns.append(f"how much of pool {pool.pool_id} remains")
    if pool.kind == PoolKind.UNKNOWN:
        unknowns.append("whether this pool is shared with the coordinator")
    if not reserve.declared:
        unknowns.append("the reserve this project holds back")
    if dispatch.estimated_cost == UNKNOWN:
        unknowns.append("what this dispatch would cost")
    if dispatch.result_consumption_cost == UNKNOWN:
        unknowns.append("what reading the result would cost")
    common = dict(task_id=dispatch.task_id, pool_id=pool.pool_id,
                  unknowns=tuple(unknowns), resets_at=pool.resets_at)

    # --- authority, before anything about capacity ---------------------------
    if dispatch.reroute_to and dispatch.reroute_to != dispatch.allowed_executor_class:
        if dispatch.authority_class == AuthorityClass.CARRIES_AUTHORITY:
            return Decision(**common, verdict=Verdict.REFUSE, why=(
                f"this task carries a semantic or product decision, so it goes to "
                f"{dispatch.allowed_executor_class!r} and nowhere else. Authority attaches to the "
                f"TASK, not to the route, and resource pressure does not move it"))
        if dispatch.reroute_to not in dispatch.allowed_fallback_routes:
            return Decision(**common, verdict=Verdict.REFUSE, why=(
                f"{dispatch.reroute_to!r} is not among the fallback routes this task declared "
                f"({', '.join(dispatch.allowed_fallback_routes) or 'none'}); a reroute to an "
                "undeclared executor is a routing decision nobody recorded"))

    # --- the arithmetic, where it can be done --------------------------------
    if pool.known and reserve.declared and dispatch.estimated_cost != UNKNOWN:
        after_production = pool.remaining - dispatch.estimated_cost
        if after_production < 0:
            return Decision(**common, verdict=Verdict.REFUSE_UNTIL_RESET, why=(
                f"the pool holds {pool.remaining:g} {pool.unit} and this dispatch is estimated at "
                f"{dispatch.estimated_cost:g}; issuing it is how three of eight workers came back "
                "with nothing"))
        if after_production < reserve.total:
            return Decision(**common, verdict=Verdict.REFUSE, why=(
                f"{after_production:g} {pool.unit} would remain against a declared reserve of "
                f"{reserve.total:g}. Continuation safety outranks utilisation: a window spent to "
                "the floor leaves nothing to repair, audit or read a result with"))

        if dispatch.result_consumption_cost != UNKNOWN:
            after_consumption = after_production - dispatch.result_consumption_cost
            if after_consumption < reserve.coordinator:
                return Decision(**common, verdict=Verdict.REFUSE, why=(
                    "the result could not be read and verified before this pool is exhausted, so "
                    "this dispatch scores negative return however cheap it is to produce: work "
                    "nobody can consume is work nobody did"))

        if pool.kind == PoolKind.SHARED_WITH_COORDINATOR and pool.active_workers >= 1:
            return Decision(**common, verdict=Verdict.DISPATCH_SERIALLY, why=(
                f"{pool.active_workers} dispatch(es) already draw on the coordinator's own window; "
                "eight in two waves on one shared window returned two results and lost eighty-one "
                "records"))
        return Decision(**common, verdict=Verdict.DISPATCH, why=(
            f"{after_production:g} {pool.unit} would remain, above the declared reserve of "
            f"{reserve.total:g}"))

    # --- conservative, because something is not known ------------------------
    if pool.active_workers >= 1:
        return Decision(**common, verdict=Verdict.REFUSE, why=(
            f"{len(unknowns)} thing(s) about this pool are not established and {pool.active_workers} "
            "dispatch(es) are already running on it. Fanning out on a window nobody can measure is "
            "the exact shape of the measured loss"))
    nothing_measured = (pool.remaining == UNKNOWN and reserve.total == UNKNOWN
                        and dispatch.estimated_cost == UNKNOWN)
    return Decision(**common, verdict=Verdict.DISPATCH_SERIALLY, why=(
        (
            "NO ARITHMETIC WAS PERFORMED. Neither the window, nor the reserve, nor the cost is "
            "established, so nothing here was computed and nothing came out favourable — this is "
            "the most conservative posture that still permits work, and it is a posture rather "
            "than a result. "
            if nothing_measured else
            f"{len(unknowns)} thing(s) are not established, so the arithmetic below is partial. "
        )
        + "One at a time and no fan-out. Unknown is not zero and it is not a refusal either: a "
          "gate that deadlocked whenever telemetry was absent is a gate a coordinator routes "
          "around"))


def wait_or_spend(dispatch: Dispatch, pool: Pool) -> Decision:
    """The branch this module deliberately does not take.

    Whether to wait for a window to reset or to spend scarce capacity now is
    `policy/hitl-matrix.md` row 15 — budget expansion, or wait-versus-spend
    beyond policy — and it is a human decision. Provided as a named refusal so
    a caller reaching for it finds the row rather than an answer.
    """
    return Decision(
        task_id=dispatch.task_id, pool_id=pool.pool_id, verdict=Verdict.ESCALATE_ROW_15,
        resets_at=pool.resets_at,
        why=("waiting for a reset against spending scarce capacity now is row 15 and is not "
             "automated here; state the options, what each costs, and a recommendation"),
    )


def _cli(argv: list[str]) -> int:
    """Gate one proposed dispatch against one pool.

    Usage: ``capacity.py TASK --pool ID --authority CLASS --executor CLASS
                         [--remaining N | --remaining UNKNOWN] [--unit U]
                         [--kind K] [--window W] [--active N] [--resets-at WHEN]
                         [--cost N] [--consumption-cost N]
                         [--reserve-coordinator N] [--reserve-consumption N]
                         [--reserve-repair N] [--reroute-to CLASS]
                         [--fallback CLASS ...]``

    Exit status: ``0`` may dispatch, ``1`` refused, ``2`` a human decision.
    """
    import argparse

    def _maybe(value):
        return UNKNOWN if value is None or value == UNKNOWN else float(value)

    parser = argparse.ArgumentParser(
        prog="capacity.py", description="Refuse a dispatch a window cannot safely carry.")
    parser.add_argument("task")
    parser.add_argument("--pool", required=True)
    parser.add_argument("--authority", required=True, choices=list(AuthorityClass.ALL))
    parser.add_argument("--executor", required=True)
    parser.add_argument("--remaining", default=None)
    parser.add_argument("--unit", default="units")
    parser.add_argument("--kind", default=PoolKind.UNKNOWN, choices=list(PoolKind.ALL))
    parser.add_argument("--window", default=WindowKind.UNKNOWN, choices=list(WindowKind.ALL))
    parser.add_argument("--active", type=int, default=0)
    parser.add_argument("--resets-at", default=None)
    parser.add_argument("--observed-at", default=None)
    parser.add_argument("--cost", default=None)
    parser.add_argument("--consumption-cost", default=None)
    parser.add_argument("--reserve-coordinator", default=None)
    parser.add_argument("--reserve-consumption", default=None)
    parser.add_argument("--reserve-repair", default=None)
    parser.add_argument("--reroute-to", default=None)
    parser.add_argument("--fallback", action="append", default=[])
    args = parser.parse_args(argv)

    try:
        pool = Pool(pool_id=args.pool, kind=args.kind, window=args.window,
                    remaining=_maybe(args.remaining), unit=args.unit,
                    resets_at=args.resets_at, observed_at=args.observed_at,
                    active_workers=args.active)
    except IntegrityError as exc:
        # Reported, not raised through the command line. A reading the module
        # will not accept is an answer this command has to give, and a traceback
        # is not one.
        print(exc.render() if hasattr(exc, "render") else str(exc))
        return 2
    reserve = Reserve(coordinator=_maybe(args.reserve_coordinator),
                      result_consumption=_maybe(args.reserve_consumption),
                      repair_and_audit=_maybe(args.reserve_repair))
    dispatch = Dispatch(
        task_id=args.task, pool_id=args.pool, authority_class=args.authority,
        allowed_executor_class=args.executor, allowed_fallback_routes=tuple(args.fallback),
        estimated_cost=_maybe(args.cost), result_consumption_cost=_maybe(args.consumption_cost),
        reroute_to=args.reroute_to,
    )
    decision = gate(dispatch, pool, reserve)
    print(decision.render())
    if decision.verdict == Verdict.ESCALATE_ROW_15:
        return 2
    return 0 if decision.may_dispatch else 1


if __name__ == "__main__":
    import sys

    # Run the module, not a second copy of it. A file executed as a script is
    # `__main__`, and a sibling that imports it BY NAME gets a separate module
    # object with separate class objects — so an `isinstance` check across that
    # boundary is False for an object that is exactly that class. Imported
    # statically, by name, because a dynamic import would route around the
    # toolbelt's import-closure check.
    from errors import run_cli
    from capacity import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
