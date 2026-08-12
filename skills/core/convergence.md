# Knowing when to stop

The failure mode, stated plainly because it has happened: audit, repair, a
regression the repair introduced, a new head, another whole-repository audit,
another repair. It can run indefinitely, every individual step is defensible,
and nothing inside the loop tells you that you are in one.

## Classify before you repair

Every finding is one of these, and the classification decides what happens next:

*   `NEW_BLOCKER` — repair now, in scope
*   `NEW_MATERIAL_DEFECT` — repair now, in scope
*   `REPAIR_REGRESSION` — the last repair caused this. Count it, and watch
*   `DOCUMENTED_BOUNDED_LIMITATION` — already known and accepted. Do not repair
*   `DELTA_GATE_HARDENING` — an improvement, not a defect. Backlog
*   `NON_MATERIAL_OBSERVATION` — record and move on
*   `ENVIRONMENT` — nobody's competence, and not the capability failing
*   `AUDIT_DISAGREEMENT` — reconcile the facts, once, in bounded fashion

The budget counters in `policy/BUDGETS.md`, initialised into each capability's
SCOPE.md and tracked live in its PROGRESS.md, bound the rounds and refuse past
them. They do not classify, and nothing should: which of these a finding *is*
needs judgement about evidence, and a rule that guessed would be wrong exactly
when it mattered.

## The economic stopping rule

Stop when the next repair costs more than the defect it removes. That is not a
counsel of laziness — it is the recognition that "absence of all possible
defects" is not a reachable state, and pursuing it spends the budget that a real
blocker will need.

What must never be frozen around: a known safety blocker, or a baseline that
cannot be used. What may remain: a documented, bounded limitation whose cost is
understood. The difference is whether somebody decided.

## Scope creep, which is the same failure wearing a different hat

An issue discovered outside the approved boundary is recorded for later — not
implemented — unless it is a genuine safety blocker or makes the baseline
unusable. "While I am in here" is how a bounded change becomes an unbounded one,
and the audit that follows is then reviewing something nobody approved.
