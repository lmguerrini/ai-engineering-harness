# Audit brief — <capability id>, <AUDIT_PRIMARY | AUDIT_CROSS>

Every non-negotiable below is required, not optional
(`policy/auditor-strategy.md`). An audit missing one is not a lesser audit; it
is not this kind of audit, and must not be recorded as a closure audit.

## What you are auditing

- Exact immutable revision (SHA):
- Repository path (read-only checkout):
- Declared dimensions in scope: (from SCOPE.md)

## Conditions

- **Fresh context.** You have not seen this capability's design discussion or
  repair reports. If anything below looks like one, stop and say so.
- **Read-only.** Make no edits. Report only.
- **Blind.** If another auditor is running in parallel, you do not see their
  findings and they do not see yours.
- **Barred from:** design documents, repair reports, prior audit findings for
  this capability.
- **Bounded turns:** <n>, stated so that stopping early is visible rather than
  looking like completion.

## Instruction

You are instructed to falsify, not to review. Here are the claims this
capability makes about itself (from SCOPE.md's acceptance criteria and
declared dimensions) — attack them. Write, if useful, an obviously-wrong
implementation and check whether the existing tests would let it pass.

## Required sections in your report

1. **What I attacked and could not break.** Not optional — the only defence
   against a padded finding list.
2. **Findings**, each with: what is wrong, why, a reproduction, and severity.
   Write findings to `capabilities/<id>/evidence/` incrementally as you find
   them, not held for a final message.
3. **What I could not evaluate**, and why (time, access, scope) — unknown is a
   third answer (`skills/core/evidence.md`).

## What happens to your findings

The coordinator reproduces every material claim before it counts. An
unreproduced claim does not gate closure on its own. If this audit is
interrupted by a quota, session, or turn limit, it is **incomplete**, not
clean, and does not consume the closure-audit-cycle counter.

## Where the auditor works — coordinator sets this up BEFORE dispatch

The auditor gets a **disposable checkout of its own**, never the coordinator's
live working tree:

    git worktree add --detach <private_root>/worktrees/audit-<capability> <sha>

State that path in the brief as the auditor's working directory, and state that
it must not touch any other tree.

**Why this is mandatory.** An auditor told "read-only, at this immutable SHA"
and handed a live repository has no compliant way to pin the revision — it must
either run `git checkout --detach` (a write) or trust that HEAD will not move
underneath it. That happened: an auditor detached HEAD in the coordinator's tree
while a second auditor was reading it. The git fence caught it and nothing was
damaged, but the brief was the defect. An instruction that forbids the only
available means of compliance is a specification error.

Remove the worktree at closure: `git worktree remove <path>`.

