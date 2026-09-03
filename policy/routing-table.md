# Routing table — DERIVED VIEW, regenerated

**Not a record.** Regenerated wholesale from `policy/observations.jsonl` at every
capability boundary — the full log each time, never patched, never a rolling
summary that overwrites adverse evidence. If this file and `observations.jsonl`
disagree, the log wins and this file is due for regeneration.

Regenerated 2026-09-03 at the RP2.3 evolution boundary from **39** observations.
The observation count,
every grade and **every count in the evidence column** are compared against the
log by `test_the_routing_table_grades_are_the_derived_ones` and
`test_every_count_the_routing_table_states_is_the_number_of_rows_behind_it`.
The log records no session identifier, so this table states none. Ordinal bands only. A
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
| AUDIT_PRIMARY | fresh, blind, same-family closure audit | **`confirmed`** — 15 real closure audits, every material finding reproduced, 0 false positives |
| AUDIT_CROSS | fresh, blind, cross-vendor closure audit | **`confirmed`** — 5 rows: 4 real closure audits with 0 false positives, and 1 `environmental_failure` that was the DISPATCHER reading standard input rather than anything about this route |
| IMPL_SUBSTANTIVE | multi-file, weaker-oracle implementation | `provisional` — claude-cli, 2 RP2 dispatches, none on the Pilot Run |
| IMPL_ROUTINE | familiar, bounded, strongly-tested implementation | `provisional` — claude-cli, 1 bounded repair |
| IMPL_BOUNDED | small-window implementation | `environmental-unknown` — codex-cli, 5 configs; cause was the profile |
| EXTRACT_LOCAL | local model, mechanical retrieval over supplied source | `provisional` — 2 bounded probes against AST-frozen ground truth |
| REVIEW_LOCAL | local model, analytical judgement | **`contradicted`** — 1 dispatch; see below |
| READER | cheapest eligible, protects coordinator context | `provisional` — 2 dispatches, but at **two different task classes**, one each |

## Where the reasoning is

The narrative behind each grade — what each dispatch measured, what it cost, what
was considered and rejected — is `docs/RP2.1-ROUTING-EVIDENCE.md`. It is read
when a grade needs defending, not held every session (`policy/BUDGETS.md`).

Per-configuration detail with evidence paths: `policy/observations.jsonl`.

## Where the history is

Two grades in this table were once wrong, and an independent audit found them by
running the command below and reading the table above it. That account is in
`docs/ROUTING-TABLE-HISTORY.md`: **`policy/` holds what governs and `docs/` holds
what happened** (`policy/BUDGETS.md`), and a narrative held every session is a
narrative competing with the rules for the same budget.

## The grades are computable, and this file is not the authority

`tools/backend_contract.py` derives per-(family, task class) grades from
`observations.jsonl` directly — same log, same conservative rule: any
contradiction grades `contradicted`; failures that never started grade
`environmental-unknown`; two or more validations grade `confirmed`; one grades
`provisional`; none grades `unprobed`.

    python3 tools/backend_contract.py   # or grades_from_observations(...)

`tools/backend_contract.py` also records which observed (family, task class)
pairs stand behind each **role** here, so the role rows above are derived rather
than restated. A role spanning several classes takes the weakest of them.

So this file is a **reading aid over a computation**, and the log remains the
record. Where they disagree the log wins — and
`test_the_routing_table_grades_are_the_derived_ones` fails when they do, which is
what "checkable rather than promised" has to mean.
