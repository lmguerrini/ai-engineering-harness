# Routing table — DERIVED VIEW, regenerated

**This file is not a record.** It is regenerated wholesale from
`policy/observations.jsonl` at every capability boundary. It is never
hand-edited into a parallel authority, and it is never a rolling summary that
overwrites adverse evidence — regeneration reads the full observation log each
time, not just what changed since the last edit. If this table and
`observations.jsonl` ever disagree, `observations.jsonl` wins and this file is
wrong and due for regeneration.

Last regenerated: 2026-08-13 at the Wave-A boundary, from **13** observation
lines (the full log). Ordinal bands only — `validated`,
`environmental-unknown`, `unprobed`. No invented telemetry: a configuration
nothing has dispatched stays `unprobed`, never assumed working or assumed broken.

## Role classes (public-safe; see `skills/core/delegation.md` for the judgement)

| Role | Purpose | Today's evidence |
|---|---|---|
| COORDINATOR | judgement, decomposition, all Git writes | n/a — never delegated |
| AUDIT_PRIMARY | fresh, blind, same-family closure audit | `unprobed` under this pack |
| AUDIT_CROSS | fresh, blind, cross-vendor closure audit | `unprobed` under this pack |
| IMPL_SUBSTANTIVE | multi-file, weaker-oracle implementation | `validated` (claude-cli; 3 RP2 dispatches) |
| IMPL_ROUTINE | familiar, bounded, strongly-tested implementation | `validated` (claude-cli; incl. 1 bounded repair) |
| IMPL_BOUNDED | small-window implementation | `environmental-unknown` (codex-cli, 5 configs) |
| IMPL_LOCAL | local model, read-only envelope | `validated for read-only only` — see below |
| READER | cheapest eligible, protects coordinator context | `unprobed` under this pack |

## Today's honest state (7 validated, 6 environmental-unknown)

*   **Validated — `claude-cli` (5 observations).** Two from Kernel Wave 1
    (Sonnet, fresh Opus). Three from RP2 Wave A: tool extraction, policy and
    template authoring, and one bounded repair that named its defect class,
    established RED first, and ran its own sibling mutation. All three disclosed
    deviations unprompted. Every one of their reports was re-executed by the
    coordinator before it counted, and one carried a material defect its own
    suite did not catch (`docs/WAVE-A-FINDINGS.md#F1`) — worker green is not
    evidence of correctness.

*   **Validated for read-only only — `local-mlx` / Qwen3-Coder-Next-4bit
    (2 observations).** Two bounded probes passed against a ground truth frozen
    by AST *before* dispatch: exact mechanical extraction, and correct
    `NOT_PRESENT` under a deliberately leading prompt that presupposed two absent
    facts. **This validates read-only inspection, classification and extraction
    inside a supplied-source envelope, and nothing else.** It does not license
    code changes, multi-file reasoning, unverifiable judgement, or any critical
    path. Two easy read-only tasks are two data points.

    This also **corrects** the earlier record: the prior
    `environmental_failure` for this family was the Kernel confinement profile
    denying a startup write, not a capability limit. Outside that profile the
    same model class runs.

*   **Environmental-unknown (6).** All five `codex-cli` configurations (Spark,
    Luna, Terra, Terra/xhigh, Sol) and the original `local-mlx` observation died
    at startup under the confinement then in force — classified `environmental`,
    not `capability`. This says nothing about what those configurations can do;
    it says the profile denied them a write they needed before any task work
    began. Note `~/.codex` is writable on this host today, so the recorded cause
    is specific to the seatbelt profile, not to the machine. Re-probing is a
    named, evidence-gated trigger (`policy/routing-policy.md`), not a standing
    task.

**Not yet measured, and not to be assumed:** audit yield by vendor diversity
(both AUDIT roles are `unprobed` under this pack), and every `codex-cli`
capability claim. The first real closure audit produces the first data point.

Full detail, per configuration, with evidence paths: `policy/observations.jsonl`.
