# Wave B — gate record

**Date:** 2026-08-13. **Pack VERSION:** 2.0.0-wave-a. **Assessed by:**
COORDINATOR, by execution. Every worker and auditor claim was re-executed before
it counted.

Fixture: `fixture-tally`, a **disposable** rehearsal project. Not the Pilot
Run. One micro-capability, three tasks, taken end to end.

| # | Gate condition | Result | Evidence |
|---|---|---|---|
| 1 | Rehearsal closes | GREEN | C1 `INTEGRATED`; full profile 28 passed at `49fefa4`; both dimensions PASSED |
| 2 | Cold continuation succeeds from ≤4 reads | GREEN | 4 reads, matched the sealed ground truth on every field (`drill-result.md`) |
| 3 | Leak blocked | GREEN | synthetic injection blocked at **both** gates; plus a **real, unplanned** leak caught at closure (C8) |
| 4 | Zero false HITL stops | GREEN | no stop occurred; the one candidate escalation was correctly resolved in-scope (D-F1) |
| 5 | No hidden state required | GREEN | a fresh context resumed from artifacts alone, with no conversation replay |
| 6 | Pack within bureaucracy budget | QUALIFIED | held prose 2,022 vs ~2,000 target; per-capability ratio measured below |
| 7 | Project Git reads as ordinary engineering | GREEN | 2 commits, product language throughout, no harness nouns, no worker names, no budgets |
| 8 | Outgoing/history scan green | GREEN | range `clean (1 commits, 6 blobs)`; **full history** `clean (2 commits, 11 blobs)` |
| 9 | Evidence and routing observations recorded | GREEN | 14 observations in `observations.jsonl`; routing table regenerated from the full log |

## The loop that was actually exercised

`SCOPE_FROZEN` → `workspace_report` clean → branch → **T1** (route, dispatch,
`scope_check`, surface check, coordinator validation, `commit_gate` both sides,
commit) → **T2** (same) → **T3** (failure-classification exercise) →
interruption + cold continuation → leak injection → full-profile validation →
**two blind audits** → repair round → mutation verification → history rebuild →
closure → autonomous integration merge → post-merge validation.

Every toolbelt tool ran at its named application point. None was decorative.

## What the rehearsal actually caught

This is the part worth reading. **Every finding below came from executing the
artifacts, not from reading them.**

- **Two independent auditors both returned NOT READY**, with **5 unique
  discoveries between them** (3 cross-vendor, 2 primary) and 3 convergent. A
  single auditor — either one — would have shipped real defects with a report
  that looked complete. This reproduces the pivot's calibration finding on the
  first try.
- **Two test-domain defects.** Each auditor independently wrote an
  obviously-wrong implementation that passed the entire green suite: one
  returning `values[0]`/`values[-1]` (every fixture was sorted), one silently
  de-duplicating (no fixture had repeats). **Neither was reachable by mutating
  production code**, because the tests' domain never entered the mechanism.
  This is the exact defect class that ended the Kernel, reproduced live in a
  200-line program.
- **A real leak, not a drill.** The closure scan refused a machine path in
  `tests/test_cli.py` that the *repair* had introduced. Committing a fix forward
  **did not clear the range** — the original blob still tripped it. The
  unpublished branch was rebuilt from the verified tree. Had it been pushed
  first, that remedy would not have existed: the whole argument for the
  human-gated push, demonstrated rather than asserted.
- **A protocol defect in the coordinator's own brief** (F7): an auditor told
  "read-only at this immutable SHA" was handed the live tree, so pinning the
  revision required a Git write. The fence caught it; no ref moved. Audit briefs
  now require a detached worktree per auditor.
- **The mutation boundary held under pressure.** The full fix for the packaging
  defect needed `pyproject.toml`; `scope_check` refused it as out of boundary.
  Recorded as a stated gap in the README rather than stepped over (D-F1).

## Bureaucracy — measured, and the honest caveat

    held prose (loaded per session)      2,022 lines   target ~2,000
    templates (pull-on-demand)             658 lines   excluded by definition
    toolbelt code                        2,631 lines
    toolbelt tests                       1,023 lines
    docs / evidence (read once)            664 lines   excluded by definition

    fixture project private artifacts      792 lines
    fixture delivered code + tests         415 lines
    ratio                                  1.9 : 1

**The 1.9:1 ratio is real and is reported without flattering it.** It is also
not a fair estimate of the Pilot Run's overhead, in a specific and checkable
way: roughly 60% of those 792 lines are the *products of the rehearsal itself*
— the drill protocol and result, the audit-yield comparison, the injected-exercise
record — which exist because measuring the loop was the point. A real capability
of the same governance weight would deliver several times 415 lines of code
against a similar artifact volume.

**The number to watch on the Pilot Run is the overhead share per capability
closure, not this ratio.** If it does not fall well below 1:1 by the second real
capability, cut pack scope — that is the standing instruction, and this is the
measurement that triggers it.

## Budgets consumed

    repair rounds, capability C1         2 of 2 — exhausted
    closure-audit cycles                 1 of 1
    auditor retries (external)           0 of 1
    repair attempts, worst finding       1 of 3
    HITL stops                           0   (none genuine; none false)

Budget exhaustion was reached and **respected**: a further material finding in
C1 would have been HITL row 8, not a third round.

## Clean state at close

    fixture repo      integration @ 49fefa4, working tree clean, 0 unknown artifacts
    release ref main  515d272 — UNCHANGED, human-gated, correctly not advanced
    worktrees         none (repair worktree removed)
    branches          main, integration, capability/C1-column-summary
    remotes           none.  tags none.  nothing pushed, anywhere.
