# Worker contract

The envelope every dispatch uses, regardless of which worker fills it: a frozen
brief goes in — acceptance criteria, declared paths, base revision, invariants,
nothing about the orchestration around it (see `delegation.md`) — and a patch
plus a structured report comes out. Nothing else crosses the boundary.

## A worker report is a claim, not a fact

Until the coordinator re-executes it. This holds regardless of which worker
produced it, and regardless of how confident the report reads. Validation the
coordinator did not run itself is `worker-reported` evidence (`evidence.md`) —
the weakest class, and never sufficient alone for a material claim.

## Findings go to a durable file — where the envelope permits a file

Not held for the final message. A worker or auditor that discovers something
material and keeps working risks losing it to a truncated run, a crash, or its
own later confusion about what it already knew. Write it, then keep going.

**This applies to mutating dispatches only.** A read-only sandbox denies *all*
writes, not only writes inside the repository, so a reviewer told both "you are
read-only" and "write your findings to a file" has a contract that prohibits and
requires the same act. The observed failure is the expensive one: the worker
completes the whole analysis, discovers it cannot write, and returns an apology.
A repository-wide evidence sweep was lost that way. Read-only dispatches return
the entire report in the final message, and the brief must say so — otherwise
the worker follows the durable-file rule and loses its work.

## Permission is not capability

`read-only` describes what a worker *may* do. It says nothing about what it
*can* do, and reading it as a competence is how a family validated for
mechanical extraction came to be dispatched on a code review. Separate the two,
and keep them separate in the routing record:

*   **`EXTRACT`** — retrieval, classification, presence and absence against
    supplied source, with a right answer fixed in advance.
*   **`REVIEW`** — analytical judgement: hold a hypothesis, test it against
    semantics, and **discard** it.

A local model validated for `EXTRACT` against AST-frozen ground truth, given a
read-only code review, produced seven findings it asserted and then retracted
itself, spent its entire budget relitigating one thread, hit the cap
mid-sentence, never reached two of three questions, and was factually wrong
about the code. It could generate hypotheses and could not discard them — which
is the half that makes a review. Qualification is per task class; a worker
qualified at one is `unprobed` at the other. Availability is not qualification.

## Read-only dispatches get no worktree

Isolation is for work that mutates. A reviewer that cannot write has nothing to
isolate, and giving one a worktree anyway cost 1.4 GB and created a branch ref
named for the agent **inside the repository under review** — the one namespace
the publication contract depends on. Isolation is opt-in, for mutating work.

## Preflight includes a write probe, not just an auth check

An auth-only preflight is not enough: it was observed passing on every run of
five separate worker configurations that then failed to start, because each
needed to write to a per-user runtime root the confinement denied, and "logged
in" says nothing about "can write here." Preflight must attempt the actual write
the runtime needs and observe the result, not infer it from a credential check.
A preflight failure here is `environmental`, not a capability finding.

## Identity is observed, or it is `requested_only`

Never assumed. If the dispatch path does not carry a verifiable record of what
actually ran — model, effort, build — record what was *requested* and label it
so, rather than let a requested value read as an observed one.

## What a worker may never do

*   Edit the tests or oracles that judge its own work.
*   Commit to a governed branch. A worker may commit inside its own disposable
    checkout — the topology makes that harmless, since only the coordinator
    ingests a patch from it — but it never writes history the coordinator did
    not choose to accept.

## Tree ownership while a worker runs

The coordinator does not edit a working tree while a worker is running in it. A
worker "restoring" a file it believes it dirtied can silently revert a
concurrent edit that was never its own. Workers sharing a tree are serialised,
not run concurrently against it — see `decomposition.md` on safe parallelism.
