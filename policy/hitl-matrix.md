# HITL matrix — the precise taxonomy

The judgement behind this list is `skills/core/human-decisions.md`. This file
is the exact, numbered application of it: every row states who checks it and at
which step, because a rule with no named application point is refused, not
written (governing rule, pack review).

## Never stops the run (recorded, continue)

Task complete · validation complete · local commit · product bug
detected/repaired · routine audit pass · capability closed → next
dependency-satisfied capability activates immediately · recorded assumptions
(reversible, internal, non-security, testable — batched and surfaced at the
next capability boundary).

## Blocks — human required

| # | Condition | Who checks it, at which step |
|---|---|---|
| 1 | Initial project authorization | COORDINATOR, before `PROJECT.yaml` is authored/frozen — project start |
| 2 | Any push, remote creation, tag, PR, merge to release ref, publication, deployment, submission | COORDINATOR, at every Git state transition in the `INTEGRATED` step of capability closure |
| 3 | Credentials/billing/API-key changes | COORDINATOR, at task routing, before a brief naming such a change is dispatched |
| 4 | Destructive/irreversible operations, data-loss acceptance, irreversible migrations | COORDINATOR, at task routing (`skills/core/decomposition.md`), before dispatch |
| 5 | Genuine product ambiguity with cross-capability blast radius | COORDINATOR, at `skills/core/requirement-interpretation.md`, `SCOPE_FROZEN` |
| 6 | Security decisions and sandbox widening | COORDINATOR, at any `confine` profile change or preflight escalation (`skills/core/worker-contract.md`) |
| 7 | Governance waiver or any weakening of a governance control | COORDINATOR, before any entry lands in the pack's `DECISIONS.md` (pack-evolution session) |
| 8 | Repair/audit budgets exhausted with an open material finding | COORDINATOR, at the convergence check (`skills/core/convergence.md`) against `policy/BUDGETS.md` counters in PROGRESS.md |
| 9 | Accepting a limitation (`HITL_ACCEPTED_LIMITATION`) | COORDINATOR, at capability closure, resolving a dimension in SCOPE.md |
| 10 | Scope insufficiency crossing a capability boundary | COORDINATOR, at `SCOPE_FROZEN` / mutation-boundary check (`skills/core/decomposition.md`) |
| 11 | Record-vs-Git divergence | COORDINATOR, at the closure checklist (every commit in `base..head` claimed by a task record) |
| 12 | Mandatory cross-vendor audit unavailable | COORDINATOR, at `CLOSURE_AUDIT` dispatch (`policy/auditor-strategy.md` non-negotiables) |
| 13 | External blockers (missing data/credentials/service) | COORDINATOR, at task preflight (`skills/core/worker-contract.md` write probe / availability check) |
| 14 | Licensing/legal | COORDINATOR, at `skills/core/requirement-interpretation.md` / `PROJECT.yaml` authoring |
| 15 | Budget expansion, or wait-vs-spend beyond policy | COORDINATOR, at routing Stage 3 deliberation (`policy/routing-policy.md`) |
| 16 | Critical-domain worker promotion | COORDINATOR, at routing Stage 1 hard gates (`policy/routing-table.md` envelope check) |
| 17 | Unresolved auditor disagreement after bounded reconciliation | COORDINATOR, at the "Disagreement" step in `skills/core/audit-strategy.md`, during `CLOSURE_AUDIT` |

## Rules that travel with the table

*   A row fires once its condition is true; it does not wait for a convenient
    stopping point elsewhere in the loop.
*   **Coordinator unavailability never implies authorization** for any row
    above (`skills/core/human-decisions.md`). The work waits.
*   A question raised against any row states the decision, the options, the
    cost of each, and a recommendation — never "how would you like to proceed?"
