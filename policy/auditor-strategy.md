# Auditor strategy — operational policy

**Classification: PRIVATE.** Names model configurations and observed capacity
economics, both excluded from tracked history by the public-safety invariant.
The generic, role-level reasoning is `skills/core/audit-strategy.md`; this file
is the part that cannot be public.

## Default audit depth (owner-approved, `DECISIONS.md` D6.4)

*   **Routine capability closure:** one blind fresh-context auditor, plus
    **seeded cross-vendor sampling**: `sha256(head_sha + "|" + salt) mod 100 <
    rate`. Unsteerable (the coordinator cannot pick which heads get sampled)
    and verifiable (anyone can recompute it from the recorded `salt` and
    `rate`, both set in `PROJECT.yaml`).
*   **Critical / material / security / concurrency / migration /
    public-contract / final-gate closures:** two blind auditors, one
    cross-vendor where available — mandatory, never silently substituted for
    the routine default (HITL row 12, `policy/hitl-matrix.md`).
*   This routine-case default is a **deliberate, labeled, cost-driven
    weakening** of the pivot's finding that two auditors is the calibration
    minimum — not a claim that one auditor is as good as two. A skipped audit
    is never recorded as passed, at either tier.

## Non-negotiables, every audit, both tiers

Fresh context; read-only; an exact immutable SHA; barred from design documents
and repair reports; falsification-instructed ("here are the claims this makes
about itself — try to break them"); a required "what I attacked and could not
break" section; findings written incrementally to a durable file, not held to
the final message; every material claim reproduced by the coordinator before it
counts.

## Configurations in use today

Default strong closure pair: a fresh strong same-family session, cross-checked
by a fresh strong cross-vendor session — blind to each other, read-only, same
immutable HEAD, bounded turns. A scarce top-tier specialist is reserved, not
default: a material dispute surviving both default auditors, or a final review
whose expected information gain clearly justifies the capacity cost.

## The observation behind the scarce-capacity rule

Across four repository-wide read-only Kernel audits: two of four premium
same-family sessions were session-limited mid-audit and produced no verdict,
once also removing the coordinator's own remaining capacity to ingest findings.
The cross-vendor side, a separate pool, completed every audit asked of it. An
**economic** fact about a shared pool, dated and revisable — never a capability
judgement, and it may never narrow an evidence envelope.

## Rules that hold regardless of configuration

An audit terminated by a quota, session, or turn limit is **incomplete**, never
clean, and does not consume the audit-cycle counter. If a fresh strong auditor
cannot run with enough reserve left for the coordinator to close the cycle,
wait for capacity — do not degrade the audit or substitute automatically. Do
not use configurations that implicitly spawn additional agents unless that is
explicitly intended and separately budgeted.

## Disagreement

Reconcile the facts once, in bounded fashion, by reproducing what each auditor
claims. If bounded reconciliation cannot settle it: HITL row 17.

## Scope sizing

A repository-wide audit and a focused one are different economic objects. The
same configuration may be eligible for the second and not the first.
