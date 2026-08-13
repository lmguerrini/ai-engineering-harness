# Routing table — DERIVED VIEW, regenerated

**Not a record.** Regenerated wholesale from `policy/observations.jsonl` at every
capability boundary — the full log each time, never patched, never a rolling
summary that overwrites adverse evidence. If this file and `observations.jsonl`
disagree, the log wins and this file is due for regeneration.

Regenerated 2026-08-13 at the Wave-B closure boundary from **14** observations. Ordinal
bands only. A configuration nothing has dispatched stays `unprobed` — never
assumed working, never assumed broken, no invented telemetry.

| Role | Purpose | Evidence today |
|---|---|---|
| COORDINATOR | judgement, decomposition, all Git writes | n/a — never delegated |
| AUDIT_PRIMARY | fresh, blind, same-family closure audit | `unprobed` |
| AUDIT_CROSS | fresh, blind, cross-vendor closure audit | `validated` — 1 real closure audit |
| IMPL_SUBSTANTIVE | multi-file, weaker-oracle implementation | `validated` — claude-cli, 3 RP2 dispatches |
| IMPL_ROUTINE | familiar, bounded, strongly-tested implementation | `validated` — claude-cli, incl. 1 bounded repair |
| IMPL_BOUNDED | small-window implementation | `environmental-unknown` — codex-cli, 5 configs |
| IMPL_LOCAL | local model | `validated for read-only only` |
| READER | cheapest eligible, protects coordinator context | `unprobed` |

**claude-cli — validated (5).** Two from Kernel Wave 1; three from RP2 Wave A
(tool extraction, policy/template authoring, one bounded repair that named its
defect class, established RED first, and ran its own sibling mutation). All
disclosed deviations unprompted. Every report was re-executed before it counted,
and one carried a material defect its own suite missed
(`docs/WAVE-A-FINDINGS.md#F1`) — worker green is not evidence of correctness.

**local-mlx / Qwen3-Coder-Next-4bit — read-only only (2).** Two bounded probes
passed against ground truth frozen by AST *before* dispatch: exact mechanical
extraction, and correct `NOT_PRESENT` under a leading prompt presupposing two
absent facts. Validates read-only inspection, classification and extraction over
supplied source — **nothing else.** No code changes, no multi-file reasoning, no
unverifiable judgement, no critical path. This also corrects the prior record:
that family's earlier `environmental_failure` was the Kernel seatbelt denying a
startup write, not a capability limit.

**environmental-unknown (6).** Five `codex-cli` configurations and the original
`local-mlx` observation died at startup under the confinement then in force —
`environmental`, not `capability`. Says nothing about what they can do. `~/.codex`
is writable on this host today, so the cause was the profile, not the machine.
Re-probing is an evidence-gated trigger (`policy/routing-policy.md`), not a
standing task.

**codex-cli / gpt-5.6-luna, effort high — validated for adversarial audit (1).**
The first AUDIT_CROSS data point under this pack, sampled by the seeded rule
rather than chosen. Returned NOT READY with 7 findings; the coordinator
reproduced all 7 by execution. Its highest-value finding was a **test-domain**
defect no mutation of production code could have revealed: an obviously-wrong
implementation passes the whole suite because every positive fixture is sorted.
It disclosed unprompted that it could not run pytest under the read-only
sandbox — a real constraint on that configuration, recorded, not a failure.

**Still not measured:** relative yield between AUDIT_PRIMARY and AUDIT_CROSS.
One cross-vendor audit is one data point and says nothing about the routine
tier's adequacy. Report the two populations separately, never pooled — the
sampled set is risk-selected (see `EVOLUTION_CANDIDATES.md` EC-4).

Per-configuration detail with evidence paths: `policy/observations.jsonl`.
