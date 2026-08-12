# Decomposition

## Capabilities

A capability is a unit that can *close*: it has acceptance criteria, a mutation
boundary, and a state at which asking "is it done" has an answer. If you cannot
say what would make it closed, it is not a capability yet.

Draw boundaries at **mutation scope**, not at subject matter. Two pieces of work
that touch the same files are one capability however different they sound,
because they cannot proceed independently and pretending otherwise produces a
dependency nobody declared.

## Tasks

A task is what one worker does in one attempt, judged once. It carries:

*   declared paths it may change — declared, never inferred from what a worker
    touched. A scope derived from the past describes the past; the question is
    what it may touch next;
*   a task class and a risk class, because evidence is scoped by them;
*   acceptance that is checkable without asking the worker.

## Dependencies

Declare them. A dependency discovered at integration time is a dependency that
was always there and was not written down — and the cost lands on the run that
finds it, not on the plan that omitted it.

## The oracle must not be inside the scope

If a task may edit the tests that judge it, its verdict is not evidence. This is
easy to introduce accidentally: a task that "fixes the module and its tests" has
been given permission to make itself pass. Split it, or narrow the scope, or
accept explicitly that the verdict is weaker and record it as such.

## Parallelism

Maximum **safe** parallelism, which is a much smaller number than the maximum
possible. Two tasks may overlap only when dependencies are satisfied, declared
mutation scopes are disjoint, each has its own workspace, their oracles are
independent, integration order is already fixed, resource leases are available,
and no shared scarce resource is required by both.

Any one of those failing serialises the pair. Concurrency being *available* is
not a reason to use it, and a wave that produces a different history depending
on which task finished first is not parallelism, it is a race.
