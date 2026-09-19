# RP 2.6.0 — gate record

Opened 2026-09-19 on branch `evolution/rp2.6` from the frozen 2.5.0 release commit
`aa55575b614df3ed4454df87f33c8796dc602258`. **State `IN_PROGRESS`**: a candidate no project may pin. Every
figure this record will state is measured by a command a reader can paste, or it is not stated.

## Subject

The release the founder authorised on 2026-09-19 from the read-only audit's decision packet: a declared
N-provider registry with one live new provider and one dormant fixture, billing safety as a route proof,
one normalised capacity observation with first-class freshness, quarantining readers, an adapter
function-probe basis, bounded gate waits with a truthful PAUSED state, the sterile scratch repair, a
read-only-mode oracle over every touched tool, and a rendering-only overview. Design:
`docs/RP2.6.0-DESIGN-P1-provider-registry-and-billing-safety.md` (frozen at the base revision; P0 is the
superseded history). Decisions: `DECISIONS.md` D29–D36.

## Session-scoped counters (D35, `policy/BUDGETS.md` "Session-scoped authorisation")

| Counter | This session |
|---|---|
| Repair attempts per reproduced root cause | 12 |
| Repair rounds per capability | 8 |
| Closure / requalification cycles per capability | 4 — raisable to 8 only by a further recorded founder decision |

Environmental and transient retries are classified first and never charged; three consecutive failures on
one root-cause hypothesis end that hypothesis. Consumption is recorded below as it happens.

## What has been measured

At the opening: both design records read `DESIGN FROZEN` by `tools/design_record.py`; the identity files
carry `2.6.0` / `IN_PROGRESS`; the manifest digest is recomputed over this tree at every commit.

## Figures, bound rather than typed

    held prose, in-release (skills/core/*.md + policy/*.md) 1896

measured by `tools/tests/test_release_integrity.py` against the tree, and against the `policy/BUDGETS.md`
target of 2,000 in-release lines; the two installed adapters outside this envelope are counted by the
same rule and disclosed in `PACK_MANIFEST.json` `known_limitations`.

The suite count is not restated here. It lives in `PACK_MANIFEST.json` `tests.passed`, and a test
recomputes it from what the suite collects.

Delta against the frozen baseline: **not stated here.** Any number written in this file is wrong from the
moment the file is edited. Measure it:

    git diff --shortstat aa55575b614df3ed4454df87f33c8796dc602258..HEAD

## The publication adjudication this release still ships

`docs/RP2.4-PUBLICATION-ADJUDICATION.md` remains the adjudication the manifest names, unchanged, and this
record carries its one known exception rather than the conclusion alone: a historical blob at the tiered
tier names a real machine account. Nothing in this release rewrites that history (rows 2 and 4).

## Mechanical gates (run at every canonical commit; results recorded raw at the freeze)

| Gate | Command |
|---|---|
| release identity | `python3 tools/pack_pin.py . --version 2.6.0 --sha <HEAD> --digest <manifest digest> --state IN_PROGRESS` |
| release delta | `python3 tools/release_delta.py . --baseline aa55575b614df3ed4454df87f33c8796dc602258` |
| design provenance | `python3 tools/design_record.py docs/RP2.6.0-DESIGN-P1-provider-registry-and-billing-safety.md --repository .` |
| surface derivation | `python3 tools/surface_diff.py . aa55575b614df3ed4454df87f33c8796dc602258 HEAD` |
| commit range | `python3 tools/commit_gate.py --range HEAD --baseline aa55575b614df3ed4454df87f33c8796dc602258 --repo .` |
| outgoing scan | `python3 tools/outgoing_scan.py --staged` before every commit |
| full suite | `python3 -m pytest tools/tests/ -q` at closure, on the exact head |

## This line's own commit contract

COMMIT-RANGE GATE: REPORTS NO VIOLATION OVER THIS LINE — measured by
`python3 tools/commit_gate.py --range HEAD --baseline aa55575b614df3ed4454df87f33c8796dc602258 --repo .`
and bound by a test that recomputes it. The hook in `templates/commit-msg.hook` is installed in the clone
this line is developed in, so a non-conforming message is refused by Git before it becomes a commit. The
twelve adjudicated historical violations of the 2.5.0 line stay recorded in that release's own gate record,
as history.

## Budget consumption

repair attempts 0 / 12 · repair rounds 0 / 8 · closure cycles 0 / 4.

## Not yet done

Everything the design promises; each item is recorded here as it lands, with the command that measured it.
Publication, tagging, a remote and consumer migration are not authorised (row 2). The mandatory
cross-vendor certification of the frozen candidate waits for the cross-vendor pool to be available again.
