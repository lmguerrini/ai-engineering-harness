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

Every observation records `pool_id` — which capacity window it drew on — and
`qualification_basis`, `field` or `synthetic`. A benchmark is **prior** evidence:
field outcomes narrow or downgrade it, a synthetic pass never overrides a
contradictory field one, and a grade whose observations are all benchmarks is
annotated so nobody reads it as a track record. An observation that says neither
is counted as neither.

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

## Three questions, never one (D26)

| | Answered by | Positive evidence |
|---|---|---|
| DISCOVERED | `tools/model_discovery.py` | a surface offered the identifier |
| AVAILABLE | an observed dispatch outcome | a run started, under these preconditions |
| QUALIFIED | `tools/qualification.py` | this configuration did this task class |

**None substitutes for another.** A model listed locally has been refused by its
provider; the same account offers different sets under different client versions;
and one configuration in this log started under one precondition and not the
other. Discovery is an input to availability and never an answer, and a static
table is always subordinate to what a run establishes.

**Qualification is keyed on nine dimensions** — surface, family, client, observed
model, effort, isolation, network, authentication class, task class. Change one
and it is a different configuration, `unprobed` until dispatched. The client
build and the capacity pool are recorded and are NOT in the key; a governed
`Invalidation` is what answers when a client change really did alter what a
configuration can do.

**The observed model is read from the execution surface, never from the worker.**
A worker in this evidence base reported its own model as a different generation
than the one that ran. An identity whose provenance says it was not observed is
`unprobed`, and a requested slug copied into the observed field is refused as
loudly as an absent one.

**Family history is PRIOR: advisory, display-only.** It is printed beside an
`unprobed` answer and ranks nothing. `policy/routing-table.md` is that view and
says so.

## The ladder, and the one way onto it

    DISCOVERED -> UNPROBED -> PROVISIONAL -> CONFIRMED
                     \-> CONTRADICTED, ENVIRONMENTAL-UNKNOWN (off-ladder)

A configuration nothing has dispatched is `unprobed` and may take work **only as
a declared probe**: bounded, its task class and observed configuration recorded,
its outcome evidence for what it tested and nothing else. One successful probe
is `provisional`, not qualified, and not qualified anywhere else. **A probe never
fills a mandatory independent audit leg or a critical-domain promotion** (rows
12, 16). Newest is never a reason: nothing in the router reads a generation, a
priority or a context window to order candidates.

## Independence rules

Auditor ≠ implementer of the audited work. A producer never closes its own
finding. Classification is frozen before routing. Workers sharing a working tree
are serialised, never run concurrently against it
(`skills/core/worker-contract.md`).

**Independence is a property of the producer, not of the configuration**
(`tools/routing.py`): the worker, the session, and the provider where a leg is
declared cross-provider. Comparing configurations is wrong in both directions —
the same session auditing its own work has a different configuration the moment
the task class changes, and two genuinely fresh blind sessions have the same one.

**Evidence is never pooled across distinct evidence-relevant configuration
identities.** The two fields excluded from that identity are named above and in
D26; that narrowing is a governance change and carries the founder's
authorisation, not this file's.
