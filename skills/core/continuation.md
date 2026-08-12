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
