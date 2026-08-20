# Routing policy — operational

**Classification: PRIVATE.** Names models and vendors; the role-level judgement
behind these choices is `skills/core/delegation.md`. Re-verify every slug
against the locally installed CLI/model cache before dispatch — never invent
one because it is plausible.

## Role → configuration, today

| Role | Default configuration | Why |
|---|---|---|
| COORDINATOR | strongest available frontier model, high effort | owns judgement + all Git writes; caps consecutive direct implementations at ~3/capability |
| AUDIT_PRIMARY | fresh strong same-family session, read-only | blind, falsification-instructed |
| AUDIT_CROSS | fresh strong cross-vendor session (codex-cli, top tier) | mandatory for critical/final-gate closures; seeded sampling elsewhere |
| IMPL_SUBSTANTIVE / IMPL_ROUTINE | claude-cli (validated) or codex-cli mid tier, by task size | per-subscription; cross-vendor by default when both are eligible |
| IMPL_BOUNDED | codex-cli small-window tier (e.g. Spark-class) | window fit is the hard reason, not an intelligence ranking |
| IMPL_LOCAL | local-mlx (Qwen-class) | zero token price is never the routing reason; exclusive lockfile; environmental-unknown today (`routing-table.md`) — re-qualify before use |
| READER | cheapest eligible model that can hold the artifact | protects coordinator context; structured private reports only |

## Routing procedure (coordinator-applied, three stages, no software)

1. **Hard gates:** a `routing-table.md` row exists for this task/risk class;
   the brief fits ≤~60% of the worker's context window; the oracle is strong
   enough or independent review is added; the write-probe preflight passed
   (`skills/core/worker-contract.md`); no independence conflict; capacity is
   observed-or-honestly-unknown, never invented. For the Claude backend a
   documented reading is available (`tools/resource_observation.py`,
   `policy/execution-boundaries.md`); everywhere else capacity stays `UNKNOWN`
   until a documented surface proves it, and a human-read figure is timestamped
   advisory evidence rather than a current observation.
2. **Cheapest eligible** for work that is familiar, bounded, strongly-tested,
   and reversible.
3. **Recorded deliberation**, three lines in PROGRESS.md, when a trigger
   fires: weak oracle, public-contract/security/concurrency/migration surface,
   high ambiguity, scarce quota, or escalation after a prior failure.

**Whenever more than one candidate was eligible, record at least one
not-chosen candidate and the reason** in PROGRESS.md — without this the
evidence base can only confirm existing preferences.

## Effort rules

Design, audit, and diagnosis reward maximum effort at the strongest available
model — every real finding in the evidence base came from there. Mechanical
repairs do not need it. Effort is passed **explicitly per invocation, never
inherited** from a previous call in the same session.

## Bans

*   `ultra`-style nested delegation (a worker implicitly spawning its own
    sub-agents) is banned outright.
*   **Standing opt-ins that make coordinator-level fan-out the default are off**
    unless a human enables one for a bounded experiment with a stated stopping
    condition. This is a *separate* ban from the one above, and was written
    after it: that ban on workers spawning sub-agents was in force while a
    *coordinator* elected ~156 executions for 52 units of work and exhausted the
    runway. Every fan-out carries a recorded estimate, cost-versus-value and
    runway check (`skills/core/delegation.md`).
*   `max` effort requires explicit human instruction; it is never the routing
    default.

## Independence rules

Auditor ≠ implementer of the audited work. A producer never closes its own
finding. Classification is frozen before routing. Evidence is never pooled
across distinct configuration strings (`routing-table.md`). Workers sharing a
working tree are serialised, never run concurrently against it
(`skills/core/worker-contract.md`).
