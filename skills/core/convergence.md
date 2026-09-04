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

## Closing a capability, in order

Two readers adopting this release from its artifacts alone could find every
closure mechanism and no sequence putting them in an order. The mechanisms were
distributed across templates, skills and tools, each correct and none saying
what comes first. This is the order.

1.  **Every acceptance criterion in `SCOPE.md` is met, or is recorded as not
    met with a reason.** A criterion nobody mentions is a criterion nobody
    checked.
2.  **Every requirement is covered.** `REQUIREMENT_COVERAGE.md` validates, and
    a requirement covered by a claim rather than by evidence is not covered.
3.  **Every validation profile the project declares has RUN.** Not passed —
    run. A profile that was not run blocks by default, because *we did not
    check* and *it is fine* are the two readings a blank must never merge.
4.  **The closure audit has completed and its findings are consumed.** Its
    subject revision is compared against the candidate: an audit of another
    tree is evidence about another tree.
5.  **Every material finding is reproduced and then closed, refuted, or
    accepted by a person.** Accepting one is a human decision and is recorded
    as one.
6.  **The record and Git agree.** No unknown workspace artifact, no divergence
    between what the record says is done and what the tree holds.
7.  **The attestation is made against the tree it is about:**

        python3 <pack_root>/tools/close_attestation.py \
            --project PROJECT.yaml --head <sha> --tree-digest <digest> <capability>

    It refuses when it is not told the tree, when the identity is empty, and
    when the identity does not match. Those refusals are the point of it.
8.  **The next dependency-satisfied capability activates immediately**, and its
    first act is `capability_open.py`. There is no resting state between one
    capability closing and the next opening — that gap is where a coordinator
    stops and nobody notices.


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
