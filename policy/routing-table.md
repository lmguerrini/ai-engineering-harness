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

## Where the reasoning is

The narrative behind each grade — what each dispatch measured, what it cost, what
was considered and rejected — is `docs/RP2.1-ROUTING-EVIDENCE.md`. It is read
when a grade needs defending, not held every session (`policy/BUDGETS.md`).

Per-configuration detail with evidence paths: `policy/observations.jsonl`.

## The grades are computable, and this file is not the authority

`tools/backend_contract.py` derives per-(family, task class) grades from
`observations.jsonl` directly — same log, same conservative rule: any
contradiction grades `contradicted`; failures that never started grade
`environmental-unknown`; two or more validations grade `confirmed`; one grades
`provisional`; none grades `unprobed`.

    python3 tools/backend_contract.py   # or grades_from_observations(...)

So this file is a **reading aid over a computation**, and the log remains the
record. Where they disagree the log wins — which was already the rule, and is now
checkable rather than promised.
