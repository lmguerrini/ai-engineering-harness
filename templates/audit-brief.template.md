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
- **Read-only.** Make no edits, and create no branch, ref or worktree. Report
  only. Where your report goes is stated below, once.
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
3. **What I could not evaluate**, and why (time, access, scope) — unknown is a
   third answer (`skills/core/evidence.md`).

## Where your findings go — coordinator states ONE of these, never both

- [ ] **Read-only dispatch (the default).** You have no write permission
      anywhere, including outside the repository. **Return the entire report in
      your final message.** Do not attempt to write a file.
- [ ] **Write permission granted**, to `<exact path>` and nowhere else. Append
      findings there incrementally as you find them, so a run that dies
      mid-audit still leaves what it found.

A brief that says both prohibits and requires the same act
(`skills/core/worker-contract.md`). The observed failure is the expensive one: a
repository-wide evidence sweep completed the whole analysis, discovered it could
not write, and returned a 315-byte apology.

## What happens to your findings

The coordinator reproduces every material claim before it counts. An
unreproduced claim does not gate closure on its own. If this audit is
interrupted by a quota, session, or turn limit, it is **incomplete**, not
clean, and does not consume the closure-audit-cycle counter.

## Where the auditor works — coordinator sets this up BEFORE dispatch

**The auditor never creates a ref, a branch or a worktree**
(`skills/core/worker-contract.md`). It reads the path the brief names and
nothing else.

The default is the coordinator's checkout **already at the audited revision**,
read-only. No snapshot is needed, and creating one anyway cost 1.4 GB and put a
branch ref named for the agent inside the repository under review — the one
namespace the publication contract depends on.

Prepare a snapshot only when HEAD would otherwise move under the auditor —
concurrent auditors, or work continuing during the audit. The **coordinator**
creates it, outside the audited repository, and names it in the brief:

    git worktree add --detach <private_root>/worktrees/audit-<capability> <sha>
    # removed by the coordinator at closure: git worktree remove <path>

Either way the brief states one working directory and says the auditor must not
touch any other tree. An instruction that forbids the only available means of
compliance is a specification error, and it is fixed on the dispatching side.

