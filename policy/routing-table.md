# Routing table — DERIVED VIEW, regenerated

**Not a record.** Regenerated wholesale from `policy/observations.jsonl` at every
capability boundary — the full log each time, never patched, never a rolling
summary that overwrites adverse evidence. If this file and `observations.jsonl`
disagree, the log wins and this file is due for regeneration.

Regenerated 2026-08-15 at the RP2.1 evolution boundary from **19** observations
(14 prior + 5 from the completed Pilot Run Project). Ordinal bands only. A
configuration nothing has dispatched stays `unprobed` — never assumed working,
never assumed broken, no invented telemetry.

**Grades are per task class, never per worker.** A worker qualified at one class
is `unprobed` at another until evidence says otherwise, and *availability is
never qualification*. Read `EXTRACT` and `REVIEW` as different competences
rather than one permission: the first is retrieval against ground truth fixed in
advance, the second requires holding a hypothesis, testing it against semantics,
and **discarding** it. One family here does the first and demonstrably not the
second.

| Role | Purpose | Evidence today |
|---|---|---|
| COORDINATOR | judgement, decomposition, all Git writes | n/a — never delegated |
| AUDIT_PRIMARY | fresh, blind, same-family closure audit | **`confirmed`** — 1 real closure audit, 15 findings, 0 false positives |
| AUDIT_CROSS | fresh, blind, cross-vendor closure audit | **`confirmed`** — 2 real closure audits, 17 findings, 0 false positives |
| IMPL_SUBSTANTIVE | multi-file, weaker-oracle implementation | `provisional` — claude-cli, 3 RP2 dispatches, none on the Pilot Run |
| IMPL_ROUTINE | familiar, bounded, strongly-tested implementation | `provisional` — claude-cli, incl. 1 bounded repair |
| IMPL_BOUNDED | small-window implementation | `environmental-unknown` — codex-cli, 5 configs; cause was the profile |
| EXTRACT_LOCAL | local model, mechanical retrieval over supplied source | `provisional` — 2 bounded probes against AST-frozen ground truth |
| REVIEW_LOCAL | local model, analytical judgement | **`contradicted`** — see below |
| READER | cheapest eligible, protects coordinator context | **`confirmed`** — 2 dispatches, 2 tiers, 0 false positives |

## What the Pilot Run actually measured

**AUDIT_PRIMARY — `confirmed`, was `unprobed`.** One real closure audit, every
finding reproduced, false-positive rate zero. It executed checks instead of only
reading them — things a read-only sandbox structurally cannot do. Cost ~33 min,
327k tokens, 132 tool calls — roughly an order of magnitude more than the
cross-vendor dispatch, which is the number to weigh when this tier is optional.

**AUDIT_CROSS — `confirmed`, second and third data points, consistent.** Its
most valuable finding was one the coordinator's own verification could not
structurally have produced. ~20 minutes, read-only. One recorded inaccuracy —
counts slightly off where it reconstructed by reading rather than running, which
it stated. Direction and conclusion were correct.

**The two-auditor tier is not redundancy, and that is now measured.** Run
concurrently on the same work, the two auditors' finding sets were **almost
disjoint** — different classes of defect, not the same defects twice. Either
alone would have missed real problems behind a report that read complete.
Report the two populations separately, never pooled.

**READER — `confirmed` at two tiers.** A wide-context evidence sweep
independently confirmed the coordinator's own decomposition, finding nothing it
had missed — itself a useful datum about the tier. A cheapest-tier consistency
sweep returned zero findings in **56 seconds** against supplied ground truth.
That second result is about **cost, not discrimination**: no defects were
available to find, so it tested throughput and honesty. The generalisable rule
is in `skills/core/delegation.md` — prepare the ground truth and the task drops
a tier.

**REVIEW_LOCAL — `contradicted`.** Dispatched on a read-only code review, the
local family produced **zero substantiated findings of ~7 asserted and then
self-retracted**, spent its entire 1,400-token budget relitigating one thread,
hit the cap mid-sentence, never reached two of three questions, and was
factually wrong about the code's behaviour. Every case it raised was executed
against the real code: zero failures. Measured cost: 42 GB of weights, peak
47.0 of 64 GB, 91 s wall clock. `EXTRACT_LOCAL` stays `provisional` on its two
prior probes — the word "read-only" was doing two jobs, and splitting the row is
the correction.

**One useful result came out of that exercise, and the worker did not produce
it** — it came from *verifying* the worker. Project-specific findings are
omitted from the public edition.

## What this says about routing, stated narrowly

Two of five Pilot Run dispatches changed the outcome, and **both were
adversarial reviews of finished work** rather than delegated production.
Production work did not benefit from delegation at all: context-reconstruction
cost exceeded the work, because each remaining task depended on facts and
decisions the coordinator already held.

**Bounded workers earned their place as independent verifiers, not as extra
hands.** One project is one project — but the direction is consistent with every
dispatch recorded here.

**Considered and rejected, not overlooked:** a second cross-vendor auditor (it
would have exceeded the frozen review budget once the one independence-critical
slot was spent) and the Claude implementer (context reconstruction exceeded the
work). Both stay `provisional`/`unprobed` for those task classes — a rejection
is not a negative observation.

**Still not measured:** relative *yield* between AUDIT_PRIMARY and AUDIT_CROSS
per unit cost. Three audits is not a rate, and the sampled cross-vendor set is
risk-selected, so the two populations are not comparable without saying so.

**environmental-unknown (6).** Five `codex-cli` configurations and the original
`local-mlx` observation died at startup under the confinement then in force —
`environmental`, not `capability`. Says nothing about what they can do.
`~/.codex` is writable on this host today, so the cause was the profile, not the
machine. Re-probing is evidence-gated (`routing-policy.md`), not a standing task.

Per-configuration detail with evidence paths: `policy/observations.jsonl`.
