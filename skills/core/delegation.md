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

## Record the road not taken

Whenever more than one candidate was eligible, record at least one not-chosen
candidate and the reason, in PROGRESS.md. Without this the evidence base can
only confirm existing preferences.

## Never

Substitute a cheaper worker for a decision that required the more capable one
because the capable one was unavailable. **Unavailability is never
authorization.** The work waits.
