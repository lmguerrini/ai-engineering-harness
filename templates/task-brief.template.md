# Task brief — <task id> (frozen)

This is the entire envelope a worker sees (`skills/core/worker-contract.md`).
Nothing about which other worker was considered, what a previous attempt did,
or any orchestration state belongs below — a capsule that carries it leaks it
(`skills/core/delegation.md`).

## Objective

State as a property that must be true, not a mechanism.

## Base revision

## Declared paths (may change)

## Forbidden paths / files

Explicitly: no test or oracle file may be edited by this worker
(`skills/core/decomposition.md` — the oracle must not be inside the scope).

## Invariants this task must not break

## Acceptance criteria

Checkable without asking the worker.

## Focused validation command

From `PROJECT.yaml`'s `validation_profiles.focused`. This worker's own report
of passing is `worker-reported` evidence; the coordinator re-runs it.

## Commit message

Prepare in a temporary file. Title, blank line, 2–4 adjacent outcome bullets —
no private/internal IDs, no orchestration vocabulary
(`policy/private-terms.default.json`). Validated before staging and after
`git show` reads it back (`commit-gate` toolbelt check).

```text
<public title>

- <outcome bullet>
- <outcome bullet>
```

## Output contract — for a task that produces more than a patch

Generated, not written by hand:

    python3 <pack_root>/tools/task_output.py <root> --task <id> --max-bytes <N> \
        [--expect <N>] [--product <name>] --brief

Paste the clause it prints. The byte bound is derived from the executing
backend's output limit and the per-record cost of this task's records — it is an
adapter fact, so it is looked up per dispatch rather than remembered. Omit the
whole section for a task whose only product is a patch.

After the dispatch, whatever happened to it:

    python3 <pack_root>/tools/task_output.py <root> --task <id> --max-bytes <N>

Read the state before deciding what to retry. `UNKNOWN` prints no plan, and that
is the point: it is classified by a person, because auto-resolving it is how one
task acquires two workers.

## Report format expected back

Patch (or committed diff inside the worker's own disposable checkout) +
structured report: what was done, what was validated and how, identity
observed-or-`requested_only`, anything the worker could not do and why.

**Where findings go — state one, never both** (`skills/core/worker-contract.md`):

- [ ] this dispatch may write: findings appended to `<exact path>` incrementally,
      so a run that dies mid-task still leaves what it found;
- [ ] this dispatch is read-only: the whole report comes back in the final
      message, and no file is attempted.
