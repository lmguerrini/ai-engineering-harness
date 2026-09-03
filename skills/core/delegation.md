# Delegation

The coordinator applies the hard gates before a worker is even considered — a
routing-table row for this task/risk class, the brief fitting the worker's
window, an adequate oracle, a passed write-probe preflight — checked against
`policy/routing-table.md` (preflight itself: `worker-contract.md`). That is a
question about facts. Which eligible worker *suits* the task is a question
about the work, and it stays here.

## What the choice actually turns on

*   **The cheapest qualified worker, not the cheapest and not the strongest.**
    Reaching for the most capable option by default spends scarce capacity on
    work that did not need it; reaching for the cheapest spends it twice.
*   **Qualified means qualified at this task class and this risk class.** A
    worker strong at bounded edits may be unqualified at architecture. There is
    no such thing as a better worker in general, and a single ranking would
    assert exactly that.
*   **Scarcity ranks below price.** Among workers that cost the same, prefer the
    less scarce. A windfall never promotes an expensive worker over a qualified
    cheaper one; it only decides between equals.
*   **Unspent capacity is lost at a reset.** A window refilling soon and mostly
    unspent is *cheaper* to draw on than a nearly-empty one refilling tomorrow.
    Reading only the balance gets this backwards.
*   **Some capacity is shared with the coordinator.** Spending it is not free
    even when it succeeds: a delegated task that leaves the coordinator unable
    to read the result has cost more than it produced. Keep a reserve.

## The delegation floor

Below some size, setting up and reviewing a delegation costs more than doing the
work. The floor exists because it is easy to delegate reflexively and call the
overhead someone else's problem.

## Estimate the fan-out before dispatching it

Parallelism is not free, and its cost is invisible at the moment it is chosen —
the coordinator's visible output stays small while hidden subagent work spends
the window. A bounded 52-item task was once given two independent workers plus a
reconciler per item: ~156 executions for 52 units of work, chosen because a
standing opt-in made orchestration the default rather than a decision with a
price. It exhausted several usage windows, consumed a large share of a freshly
reset one, and **still did not finish**. A single coordinator then completed the
remaining work from the salvaged drafts.

Before any fan-out, state three numbers and record them:

*   **the estimate** — units of work × agents per unit × expected retries;
*   **cost against value** — duplicated context and reconciliation counted as
    cost, not assumed away;
*   **the runway** — whether the remaining window plausibly covers the estimate,
    with margin.

Gate each one before issuing it (`tools/capacity.py`): a **refusal**, never a
queue that later drains. A task states its authority class first — one carrying a
semantic or product decision goes where it was classed to go whatever else is
still answering — then the arithmetic runs where the numbers exist, and where
they do not, `UNKNOWN` earns serial dispatch rather than an invented figure or a
deadlock. Wait-versus-spend stays row 15.

Then declare bounded concurrency and bounded spawn depth. **Target maximum safe
parallelism, never maximum possible parallelism.** A standing configuration that
makes fan-out the default is off unless a human has opted in, for a bounded
experiment with a stated stopping condition.

**Prefer single-agent execution when the marginal value does not justify the
duplicated work** — the common case for uniform, bounded, per-item tasks. The
evidence is narrow and worth stating plainly: across one full project, the
dispatches that changed the deliverable were **adversarial reviews of finished
work**, not delegated production. Bounded workers earned their place as
independent verifiers, not as extra hands.

## Prepare the ground truth and route down a tier

When a check can be expressed as a diff against supplied ground truth, prepare
the ground truth. A consistency sweep over every numeric claim in two documents
ran in **56 seconds on the cheapest tier**, zero false positives, because the
values had been recomputed into a file first. Without that file the same task is
open-ended research needing a far stronger worker. The preparation is a few
minutes of deterministic coordinator work and it changes which worker the task
needs.

## What to send

The capsule is what the worker sees. It should contain what the task needs and
nothing that describes the machinery around it:

*   the acceptance criteria, stated as what must be true;
*   the declared paths it may change;
*   the base revision;
*   the invariants it must not break.

Not: which other worker was considered, what a previous attempt did, or anything
about the orchestration. A worker that knows it is being compared behaves
differently, and a capsule carrying orchestration state is a capsule that leaks
it.

## Never

Substitute a cheaper worker for a decision that required the more capable one
because the capable one was unavailable. **Unavailability is never
authorization.** The work waits.
