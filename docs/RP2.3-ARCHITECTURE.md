# RP2.3 — the three new components, and why none of them is an authority

`DECISIONS.md` D23 carries the decision. `docs/RP2.2-ARCHITECTURE.md` states the
authority layering and is unchanged. This file states only what this release
adds to that picture, because it adds the first components in the pack's history
that hold a *machine-written, machine-transitioned* value — and that is the
shape D1 exists to refuse when it is done wrong.

## The shape

    AUTHORITATIVE PROJECT-LOCAL DURABLE GOVERNANCE RECORD
      the contract, progress, decisions, findings, evidence
        │  written by the coordinator, read by everything
        ▼
    DURABLE MACHINE-WRITTEN STATE
      coordinator continuation · job and worker execution records
      capacity observations · close attestations
        │  every value reconstructible from an artifact that caused it
        ▼
    DETERMINISTIC DERIVATIONS
      capacity pre-dispatch gate · progress classifier · output recovery
      closure and reachability checks · history and publication checks
        │  report and refuse; hold nothing
        ▼
    READ-ONLY PROJECTIONS
      the diagnostic renderer

Each layer may refuse what the layer below produced. **No layer may promote
itself by being newer, by being machine-readable, or by being the only thing
present when a decision was needed.**

## Why machine-written state is not a second authority

Three properties, and losing any one of them makes it one:

1.  **Every transition is caused by a durable artifact** — a job's exit status,
    its log, a materialised checkpoint — and can be recomputed from that
    artifact after the process that wrote it is gone. A transition whose only
    evidence is that something wrote it is not reconstructible, and an
    unreconstructible value is a claim.
2.  **No governed action may be taken whose only premise is a state value.**
    The state says a job exited; whether the next thing to do is repair, close,
    or escalate stays coordinator judgement. This is the clause that keeps a
    state machine from becoming a scheduler.
3.  **The record wins, without discussion.** Where durable state and the
    governance record disagree, the state is the defect. Where the projection
    and either of them disagree, the projection is the defect. The direction is
    fixed in advance so that nobody has to adjudicate it while it matters.

An earlier draft of the evidence this release rests on promoted its state
machine to *authority alongside* the record and wrote the record-wins rule only
against the dashboard. An independent audit found it. That is the exact error
this file exists to make hard to repeat.

## What is still not built

Not built here, and not by consequence either:

*   a scheduler. The capacity component is a **pre-dispatch refusal**. It never
    holds a queue it later drains, because a queue that dispatches is a
    scheduler however it is described;
*   an orchestration database, an event store, or any single-runtime authority
    (D14 clause 11);
*   a daemon, a service, or a listening port. The projection is a renderer that
    runs once and exits;
*   an actor that can start, wake or restart a coordinator (D23 clause 4). A
    mechanism may record that one is needed;
*   an autonomous terminator. A stalled worker is **classified**; ending it is a
    coordinator action under `policy/hitl-matrix.md` row 4. A single-signal
    detector was measured killing healthy work, and the destructive half of a
    detector is not carried by the same evidence as the detecting half;
*   any scalar score for semantic quality, and any universal grade for a
    provider. The class boundary carries the decision; a number erases it.

## What an external corpus is

Unchanged from RP2.2: design and evidence input, never automatic authority. The
reconciliation this release draws on is verified rather than believed — its
manifest re-hashes, its files verify, its validator re-executes — and its
mechanisms are adopted individually, on their own reproductions. The
findings it left open are inputs here rather than closed items.
