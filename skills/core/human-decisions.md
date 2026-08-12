# The human boundary

Some decisions are not the coordinator's to make, and the list is short enough
to hold in mind:

*   release and publication;
*   the first remote, and the first push;
*   weakening any governance rule;
*   accepting a critical limitation;
*   anything destructive or irreversible;
*   an ambiguous product decision — what the thing should *do*;
*   potentially critical evolution of the pack itself;
*   a security waiver;
*   a genuinely contested cross-auditor disagreement that bounded reconciliation
    could not settle.

This is the judgement behind the list, not the list itself. The precise,
numbered taxonomy — every blocking condition, and who checks it at which step —
lives in `policy/hitl-matrix.md`; this skill is why those rows exist and how to
recognise one that is not yet written down.

## Two rules that are easy to state and easy to violate

**Coordinator unavailability never implies authorization.** If the decision
needed a human and no human is available, the work waits. If it needed the
coordinator and the coordinator has no capacity, the work waits. Substituting a
lesser decision-maker converts "we could not ask" into "we asked and got this
answer", which is the same defect as reading an unknown as a success.

**Automation must never fabricate acceptance.** Not by defaulting, not by
inferring from silence, not by treating a previous approval as covering this
one. Approval is per-action: a human who approved one thing has not approved the
next thing that resembles it.

## Asking well

A question worth a human's time states the decision, the options, what each
costs, and a recommendation. A question that says "how would you like to
proceed?" has handed back the analysis they delegated. If you know the right
answer, say so and say why — being overruled is cheap, and being asked to do the
thinking twice is not.
