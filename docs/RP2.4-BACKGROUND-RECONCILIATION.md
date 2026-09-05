# Background-activity reconciliation

Reconstructed from the process table, producer exit status, durable output files
and whether each result had already been consumed — not from the UI.

## The finding

**Three long-running "activities" were self-perpetuating waiters, not work.**

Each was a hand-written monitor of the shape

    while pgrep -qf "pytest tools/tests" || pgrep -qf "codex exec"; do sleep 20; done

and `pgrep -f` matches a process's whole command line — **including the waiter's
own**, which contains that exact string. So each loop matched itself and could
never terminate, however long ago its producer exited. Demonstrated directly: a
shell running `pgrep -f "pytest tools/tests"` reports three matches with no
pytest running anywhere.

**The shipped mechanism does not have this flaw and never did.**
`tools/progress.py::waiter_command` watches a process NUMBER through
`ps -o stat=`, matches no command line, treats a zombie as ended, and quotes the
sentinel. Its own docstring records this failure class, measured live in the
2.3.0 session.

So this is not a defect in the release. It is the limitation the manifest already
states — *the liveness model governs declared waits and nothing else; a waiter a
coordinator writes by hand and never records is outside it* — reproduced by the
coordinator, in the session that ships the tool which prevents it. Recorded
because a limitation demonstrated is worth more than a limitation asserted.

## Classification

| Activity | Producer state | Result | Classification | Action |
|---|---|---|---|---|
| release-authority audits completion | both `codex exec` exited; reports written and read | consumed | ORPHANED_WAITER | ended by its own timeout during reconciliation |
| all three verification runs complete | suite + both audits exited | consumed | ORPHANED_WAITER (self-matching) | retired with TaskStop |
| final suite and remaining audit | suite exited 2196 passed; audit exited | consumed, and superseded by two later candidates | ORPHANED_WAITER + SUPERSEDED | retired with TaskStop |
| finalized suite result | suite exited 2237 passed | consumed | ORPHANED_WAITER (self-matching) | completed during reconciliation |
| every earlier monitor | — | — | COMPLETED_CONSUMED | none |

## Producers, checked individually

Every background producer this session started has exited, and every one's
output was read and acted on: five full-suite runs, two history scans, four
codex dispatches, one durations run, one static file server. **No producer
output is unconsumed.** No zombie processes. No orphaned worker was terminated
to tidy the display — the only things ended were waiters whose subjects were
already finished.

## Reconstruction from disk alone

Nothing in the candidate's durable state refers to any of these activities:
they were coordinator-side monitors, outside the project record by construction.
`CONTINUATION.json` for the candidate declares no waits, so a fresh process
reading the durable state alone reconstructs **zero** outstanding work — which is
the correct answer, and is what the reconciliation establishes rather than
assumes.

## Effect on the overnight path

None. No stale activity holds a lock, a file, an output root or a quota window,
and none is watched by anything that must finish before the release can be
qualified.
