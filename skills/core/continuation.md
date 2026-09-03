# Continuation

A coordinator picking this up — cold, or after a break — reconciles from disk
first and distrusts its own conversation summary. A summary is a claim about
what happened; disk is what happened. Where the two disagree, disk wins, and the
disagreement itself is worth a line in HANDOFF.md so the next reader does not
re-discover it.

## The four-read reconstruction target

Full state, in this order, before touching anything:

1. `PROJECT.yaml` — the contract: what this project is, its dimensions, its
   validation profiles, its refs.
2. `HANDOFF.md` — current continuation state.
3. The active capability's `SCOPE.md` — frozen scope, acceptance, mutation
   boundary, budget counters.
4. The active capability's `PROGRESS.md` — task states, budget counters as
   actually spent, routing deliberations.

Then one `git status` and `git log` against the branch HANDOFF.md names, to
confirm the record and the tree agree. If they do not, that is HITL row 11
(`policy/hitl-matrix.md`) — a consumer never re-derives a fact the record and
Git disagree about, it stops and asks. Target: full reconstruction in these four
reads plus the one Git check. Anything else is pull-on-demand, not held.

## A declared wait is a machine-readable declaration, not a sentence

The rule above is necessary and was measured insufficient. A coordinator that
declared its wait correctly — naming the job, the process and the log — still
produced a two-hour silence after that job exited, because **a state that exists
only as a sentence cannot have a transition**. Four of five recorded recurrences
are that one edge.

So a wait is declared in `tools/continuation.py`'s record, with a completion
condition somebody other than the coordinator can evaluate, and the state is
**derived** from that declaration and the artifacts rather than stored. It
therefore advances on job exit whether or not anyone is watching, which is the
point: the coordinator that has gone silent is the one that cannot poll. Where
the derived state and the governance record disagree, the record wins and the
derivation is the defect.

`SILENT_IDLE` — authorised work outstanding, nothing declared to be in the way,
nothing running — is representable, and it is a **defect**, never a resting
state.

## State what budgets are consumed

Reconstruction is not just position, it is spend. Read the counters in
PROGRESS.md against the bounds in `policy/BUDGETS.md` before deciding what
happens next — a fresh session with no memory of the previous rounds is exactly
the session that will silently re-spend a budget already exhausted.

## Name what is unrecoverable, explicitly

Some things a summary implies were captured and were not: an auditor's full
reasoning, an unpersisted intermediate judgement, a worker's discarded attempt.
Say plainly what is gone rather than let a confident-sounding HANDOFF.md imply
completeness it does not have.

## Resume from checkpoint, or cleanly re-dispatch — never both

A task in an ambiguous state (did the worker's patch land? did the last commit
claim it?) is resolved one way, deliberately, before continuing. Resuming a
worker that already committed and *also* re-dispatching a fresh one is how one
piece of work enters history twice. Reconcile Git against the record first;
only then choose.

## HANDOFF.md: format and bound

`HANDOFF.md.template` in `templates/`. **Replaced** each update, never
accreted — it is current state, not a log. **≤200 lines.** Everything durable
belongs in SCOPE.md, PROGRESS.md, FINDINGS.md or DECISIONS.md instead; HANDOFF.md
only points at them. A HANDOFF.md that is growing is a HANDOFF.md absorbing
content that has a real home elsewhere.

## Context is spent, so spend it on ground truth

Stable invariants only. Anything vendor-specific — a client's cache behaviour, a
model's window, a flag — belongs in that vendor's adapter, which can be wrong
without the Core being wrong.

*   **Route from ground truth, not from recollection.** A fact re-derived from
    disk costs one read; a fact carried in a summary costs every turn until it
    turns out to be stale.
*   **Reduce command-output noise at the source.** Ask for the lines that decide
    something. A gate's verdict and its findings are the answer; its full
    transcript is an evidence entry, stored once and cited, not pasted.
*   **Irrelevant context is not free and is not neutral.** It displaces the
    material a judgement actually needs, and it makes a wrong answer look
    well-supported.
*   **Durable state lives on disk, continuously** — not assembled at the end.
    Work that exists only in a session is work a limit can delete.
*   **Independence needs a fresh context, not a request for one.** Where a task's
    semantics require an unseeded reader — an audit, a blind check — start a new
    session. Asking a session that has seen the implementation to disregard it
    does not make it a blind reader.
*   **Do not switch model or effort inside a session for a marginal reason.**
    A switch is not free, and a saving that costs a re-read of everything so far
    is not a saving.
*   **Context reduction is a reconstruction, never a compression.** When context
    must be shed, the recovery path is the four reads above. A summary of a
    summary is the failure mode this whole file exists to prevent.
