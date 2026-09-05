# PROPOSED D26 — not a decision, and deliberately not in `DECISIONS.md`

**This entry has NOT landed in the decision layer, and that is the point.**

`policy/hitl-matrix.md` row 7 fires on any weakening of a governance control
and states its application point exactly: **before any entry lands in the
pack's `DECISIONS.md`**. This release narrows a governance control — see
below — so the entry needs the founder's authorisation *before* it is written
there, not after.

The coordinator wrote it there first. An independent reader of the candidate
found the sequencing, and was right: correctly identifying row 7 inside the
entry does not make writing the entry compliant, and a later freeze decision
cannot make an earlier sequence compliant retroactively. **The entry was
removed from `DECISIONS.md` and is held here as a proposal.** The commit that
briefly carried it is in this branch's history and is named in
`docs/RP2.4-GATE.md`; rewriting that history is itself rows 2 and 4, so what
is corrected is the tree and the record, not the past.

**To adopt it:** the founder authorises the narrowing, and the text below is
appended to `DECISIONS.md` as D26 — in that order.

---

## D26 — qualification is a property of a configuration, not of a family (RP2.4)

**Question the release opened with:** model discovery is already dynamic and a
new frontier model reached this pack with no Core change at all. So what breaks?

**Answered by execution, against the shipped log and the shipped module.** A
model with zero observations returned

    qualified_for("blind_closure_audit_cross_vendor") -> True

on seven observations, none of which recorded any observed model. Not a
hypothetical: `backend_contract.grades_from_observations` keys on
`(family, task_class)`, and `policy/routing-policy.md` has said since 2.1 that
evidence is never pooled across distinct configuration strings. The prose was
right and the code did the opposite, and nothing compared them.

**Decided: a second derivation, keyed on the evidence, beside the first.**

*   **Nine dimensions, closed and reasoned.** Surface, family, client, observed
    model, effort, isolation, network, authentication class, task class. Each is
    in the key for a stated reason and the set does not grow by parameter. The
    client build and the capacity pool are carried, reported, and deliberately
    out — no A/B pair in this evidence base shows a build change altering an
    outcome, and keying on it would reset every qualification at every patch
    release.
*   **Availability is a separate axis, and preconditions are part of its key.**
    The shipped log holds one configuration where standard input decided whether
    the dispatch started at all. What a configuration *can do* and whether it
    *can start* are different questions with different evidence, and answering
    the second with the first is what routed to a dispatch known to hang.
*   **Incomplete identities answer nothing.** An identity with `UNKNOWN` in a
    keyed dimension, or whose provenance says it was not observed, holds
    observations and can never qualify a concrete configuration. Every
    observation recorded before this release is therefore prior evidence and none
    is a track record. Nothing was rewritten and nothing was invented.
*   **Family history is display-only.** It is printed beside an `unprobed`
    answer so a coordinator is not left with nothing. It ranks nothing, satisfies
    no eligibility test and breaks no tie.
*   **A declared alias moves no grade.** It surfaces the other identity's
    evidence as prior, labelled. Two independent readings found the same
    laundering path through a rule that transferred a grade on a reason string.
*   **Independence is derivation, never configuration.** The producer, the
    session and — where a leg is declared cross-provider — the provider. Key
    equality is wrong in both directions and an independent reader demonstrated
    both.
*   **An unprobed configuration takes work only through a declared probe**,
    whose outcome becomes evidence for what it tested and nothing else. Without
    it an empty table could never acquire its first observation. A probe never
    fills a mandatory independent leg or a critical-domain promotion.

**This narrows a governance control, and that is HITL row 7.** An earlier draft
of the design claimed no control was touched; an independent reader falsified it
and the claim is withdrawn. `policy/routing-policy.md` says evidence is never
pooled across distinct configuration strings, and this release pools across two
named non-identity fields while widening the key from one dimension to nine. Net
tightening is still a change to a control. **The narrowing is authorised by the
founder at freeze, not by this work**, and it is listed in the freeze procedure
in `docs/RP2.4-GATE.md`.

**Rows 12 and 16 keep their human and are strengthened in the direction they
already point:** the evidence behind a critical-domain promotion becomes
per-configuration rather than per-family, so an unavailable qualified worker is
still never authorization to use an unqualified one.

**Reverses on:** an A/B pair showing a client version changing what a
configuration can do, which would move `build` into the key; or an adopting
project finding the key so fine-grained that every real dispatch is a probe,
which would mean the granularity is wrong rather than the principle.
