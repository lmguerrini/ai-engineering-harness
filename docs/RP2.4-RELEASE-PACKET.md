# RP2.4 — release packet

What a returning release authority reads first. It points; it does not restate.
Where this file and a computation disagree, the computation wins.

## Identity

    version   2.4.0                          VERSION
    state     IN_PROGRESS                    PACK_MANIFEST.json  -- a candidate
    digest    PACK_MANIFEST.json tree_digest_sha256
    revision  git rev-parse HEAD             -- a manifest cannot name its own commit
    baseline  2.3.0 at ab7dea97a12c699e8123bcb5d5be976cd05c075e, untouched

Verify, do not read:

    python3 tools/pack_pin.py . --version 2.4.0 --sha <rev> \
        --digest <manifest digest> --state IN_PROGRESS

## What this release is

`backend_contract.grades_from_observations` keyed qualification on
`(family, task_class)`. A model with zero observations therefore returned
`qualified_for("blind_closure_audit_cross_vendor") -> True` on seven
observations that recorded no observed model at all — reproduced by execution
before anything was written, and the command is in `docs/RP2.4-GATE.md`.

This release adds a second derivation keyed on the evidence, a separate
availability axis, and a routing surface that ranks on a configuration's own
outcomes. `DECISIONS.md` D26 carries the decision;
`docs/RP2.4-ARCHITECTURE.md` carries the shape;
`docs/RP2.4-DESIGN-C40-qualification-identity.md` carries the design that two
independent readings falsified before it was implemented.

## The two decisions this candidate cannot take for itself

1. **HITL row 7** — D26 narrows a stated governance control.
2. **HITL row 2** — the state transition to `QUALIFIED_AND_FROZEN`.

Both, with the exact commands, are under *the freeze procedure* at the end of
`docs/RP2.4-GATE.md`. No push, tag, remote or consumer migration is included in
either; those are separate row-2 decisions.

## What is not established

`PACK_MANIFEST.json` `known_limitations` is the list, and it is the list rather
than a summary of one. The four a reader should not miss:

- the per-configuration table is nearly empty, because no observation predating
  this release carries an observed identity — the honest state of this evidence;
- the newest model is `provisional` at two task classes and `unprobed`
  everywhere else, on one dispatch each against one alternative;
- both design readings came from one provider, so they are not independent of
  each other's provider — which this release's own router would refuse for a leg
  declared cross-provider;
- previously-used configurations read `UNKNOWN` on the updated client, because
  their availability evidence was recorded on the old one and is not carried
  across.

## Where the numbers live

Suite count: `PACK_MANIFEST.json` `tests.passed`, written by the collection the
check re-runs. Held prose: `docs/RP2.4-GATE.md`, measured. Delta against the
baseline: `git diff --shortstat`, because a literal here is wrong the moment
this file is edited.
