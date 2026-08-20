# Routing table — DERIVED VIEW, regenerated

**Not a record.** Regenerated wholesale from `policy/observations.jsonl` at every
capability boundary — the full log each time, never patched, never a rolling
summary that overwrites adverse evidence. If this file and `observations.jsonl`
disagree, the log wins and this file is due for regeneration.

Regenerated 2026-08-20 at the RP2.2 evolution boundary from **26** observations
(19 prior + 7 from that session). The count is compared against the log by
`test_the_routing_table_grades_are_the_derived_ones`. Ordinal bands only. A
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
| AUDIT_PRIMARY | fresh, blind, same-family closure audit | **`confirmed`** — 7 real closure audits across four sessions, every finding reproduced, 0 false positives |
| AUDIT_CROSS | fresh, blind, cross-vendor closure audit | **`confirmed`** — 2 real closure audits, 17 findings, 0 false positives |
| IMPL_SUBSTANTIVE | multi-file, weaker-oracle implementation | `provisional` — claude-cli, 3 RP2 dispatches, none on the Pilot Run |
| IMPL_ROUTINE | familiar, bounded, strongly-tested implementation | `provisional` — claude-cli, incl. 1 bounded repair |
| IMPL_BOUNDED | small-window implementation | `environmental-unknown` — codex-cli, 5 configs; cause was the profile |
| EXTRACT_LOCAL | local model, mechanical retrieval over supplied source | `provisional` — 2 bounded probes against AST-frozen ground truth |
| REVIEW_LOCAL | local model, analytical judgement | **`contradicted`** — see below |
| READER | cheapest eligible, protects coordinator context | `provisional` — 2 dispatches, but at **two different task classes**, one each |

## Where the reasoning is

The narrative behind each grade — what each dispatch measured, what it cost, what
was considered and rejected — is `docs/RP2.1-ROUTING-EVIDENCE.md`. It is read
when a grade needs defending, not held every session (`policy/BUDGETS.md`).

Per-configuration detail with evidence paths: `policy/observations.jsonl`.

## Two grades in this table were wrong, and that is why the next section exists

`AUDIT_PRIMARY` and `READER` both read **`confirmed`** through 2.1.1. Neither was,
under the rule stated at the top of this file and applied by the command below:
`AUDIT_PRIMARY` had one validation, which is `provisional`; `READER` has two
dispatches at **two different task classes**, which is one each — and "grades are
per task class, never per worker" is this file's own rule, three lines up.

An independent audit found it by running the command printed here and reading
the table above it. Corrected, and now compared by a test rather than by a
reader — which is why `AUDIT_PRIMARY` reads `confirmed` again today and means it:
six more real closure audits happened during the RP2.2 evolution session, every
finding reproduced before it counted, and the grade follows the log rather than
the other way round.

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
