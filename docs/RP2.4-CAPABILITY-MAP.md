# RP2.4 — capability map and dependency order

The evolution session's working plan. Written from the mechanism the failure
lives in, not from the summary that recommends a fix, and updated only by
appending.

Baseline: `2.3.0` at `ab7dea97a12c699e8123bcb5d5be976cd05c075e`, state
`QUALIFIED_AND_FROZEN`, tree digest
`389ef7cd5f7fb60f6819f5d5990d0f04259775e76f6f53190c3a96d2037fcbac`, verified with
the shipped `pack_pin.py` before anything was created and again after the one
environment change this session made. The suite passes at that frozen revision;
the count is the baseline manifest's `tests.passed` and is not restated here.

## Scope classes

Unchanged from 2.3.0: `MUST_THIS_RELEASE`, `SHOULD_THIS_RELEASE`,
`DEFER_WITH_TRIGGER`, each deferral carrying the observation that reopens it.

## Capabilities, in dependency order

| # | Capability | Class | Depends on |
|---|---|---|---|
| C40 | Configuration identity, availability axis and the qualification derivation | MUST | — |
| C41 | Dynamic discovery with no model vocabulary | MUST | C40 |
| C42 | Probation ladder and the declared probe | MUST | C40, C41 |
| C43 | Design-audit routing as a governed capability | MUST | C42 |
| C44 | Routing state in the readiness path and the projection | SHOULD | C43 |
| C45 | Generation-agnostic publication vocabulary | MUST | — |
| C46 | Adversarial rehearsals and the synthetic adoption drill | MUST | C43, C44 |

C40 is first because every other capability is a claim about it. C45 is
independent and was done alongside; it is `MUST` because the vocabulary had
**already** aged out from under the models in use, not because a future one
might.

## What each capability actually is

**C40.** `tools/qualification.py`. A nine-dimension key, a completeness rule that
covers both the absent observed model and the copied-and-honestly-labelled one, a
governed `Invalidation` for a client change that really did alter capability, and
a declared equivalence that moves no grade. `backend_contract` is untouched and
becomes the family-level prior by name rather than by reimplementation.

**C41.** `tools/model_discovery.py`. Reads a document through FIELD names, never
model names; carries the producing client, the age and the skew; treats a
disappearance as a fact about a document rather than a verdict about a model.

**C42.** In `tools/routing.py`: purposes, and a probe that may fill an ordinary
seat and never a critical one. The pack's existing grade vocabulary throughout —
no second set of words for the same idea.

**C43.** `routing.design_audit_route`. Seats described by the independence and
evidence they need. No vendor, model or family name appears in the module.

**C44.** A `routing` component in `capability_open` behind `requires.routing`,
defaulting false; a panel in `projection` that derives on every render and stores
nothing.

**C45.** One literal replaced by one pattern in the same tier, falsified against
a corpus in both directions.

**C46.** Sixteen deterministic fixtures and one lifecycle drill, run five ways.

## DEFER_WITH_TRIGGER

| Item | Trigger that reopens it |
|---|---|
| `build` in the qualification key | an A/B pair at one configuration where a client version changes the outcome. Neither falsification reading could produce one from this evidence base, and both said so |
| A durable availability-observation record | today `AvailabilityObservation` is constructed by the caller from what it observed; a project that wants availability to survive a restart needs a file for it. Trigger: the first coordinator that asks the same availability question twice across sessions |
| Per-effort context-fit gating | the router does not read a context window at all, deliberately. Trigger: a dispatch refused for window size that the evidence could have predicted |
| Automatic identity capture in the adapter | the observed identity is read by hand from the execution surface today. Trigger: the first configuration that stays `unprobed` only because nobody transcribed what ran |

## RP2.3 deferrals

Carried unchanged. See `docs/RP2.3-CAPABILITY-MAP.md` for each item and its
trigger; none was reopened by this release.
