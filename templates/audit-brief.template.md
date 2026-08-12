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
