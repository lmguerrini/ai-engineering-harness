# RP2.3 — gate record

What happened, in the order it happened, including what the coordinator got
wrong. Appended to as each capability closes; never rewritten.

**Version `2.3.0`, state `IN_PROGRESS`.** No project may adopt this candidate. Moving it to
`QUALIFIED_AND_FROZEN` is a human decision (`policy/hitl-matrix.md` row 2) and
the coordinator does not take it.

## Baseline

    version   2.2.0
    revision  d70d72fbcadb98cb8a2979f9c63ed84e595662e8
    digest    4bab6b8d505735f164e928e36eca674835f38478d5d5f334d740fa41c49c5a24
    state     QUALIFIED_AND_FROZEN

Verified before anything was created, by two means that do not share code: the
`pack_pin.py` that ships inside the release, and an independent
re-implementation of `sha256-framed-v1` written from the algorithm's prose
description rather than by importing the module under test. Both produced the
recorded digest over the recorded file count. Untracked, non-ignored files in
the release root: none. The suite passes at that revision; the figure is the
baseline manifest's own `tests.passed` and is not restated here.

**The evolution workspace is a worktree, and that was not a convenience.** One
live project pins the pack's *working* checkout by root path — the layout defect
`DECISIONS.md` D18 records and the 2.2.0 manifest names as the finding that most
deserves a decision. It verifies today only because that checkout happens to sit
on its pinned revision, so checking a branch out in it would have broken a
currently-verifying pin. A worktree leaves the pinned root untouched. Both live
pins were re-verified after the workspace was created and both still pass.

## Session authorisations

Recorded here because `policy/BUDGETS.md` requires it and because an
authorisation nobody can find later is one nobody can audit.

| | |
|---|---|
| Repair / audit counters | `policy/BUDGETS.md`, RP2.3 column. Repeats RP2.2's numbers rather than raising them |
| Cross-vendor fallback | named in `policy/auditor-strategy.md`: a second blind same-family auditor on a distinct lens, only after the cross-vendor channel has been attempted and refused, recorded as *not cross-vendor* |
| Version class | MINOR, following `DECISIONS.md` D24 rather than preceding it. The mandatory-versus-declared fork was the human decision; the number follows from it |
| Fan-out | none requested and none authorised. `policy/routing-policy.md`'s ban on standing fan-out opt-ins stands. Dispatches are serial, and the measured reason is eight parallel workers on a shared window returning two results and losing eighty-one records |

## Qualification

The suite count is not written here. Adding a test changes it, and a figure this
document's own edit invalidates is one it must not carry — it lives in
`PACK_MANIFEST.json` `tests.passed`, recorded by the same collection the check
re-runs.

Delta against the frozen baseline: **not stated here.** Editing this file
changes it. Measure it:

    git diff --shortstat d70d72fbcadb98cb8a2979f9c63ed84e595662e8 -- .

## Measured overhead

Held prose, measured at this point in the session and re-measured at close
(`policy/BUDGETS.md`):

    in-release (skills/core/*.md + policy/*.md)   1476
    installed adapters, outside the envelope      1023
    total against a ~2,000 target                 2499   24.9% over the ~2,000

**The breach is inherited and it has grown.** 2.2.0 recorded 2486 on the same
rule and declined to shave it, on the ground that re-scoping a rule to fit its
number deletes the disclosure rather than the excess. That reasoning still
holds and it is not a licence. This session applied *delete before adding* where
it could — a sentence duplicated word for word inside `auditor-strategy.md` was
removed rather than left beside its new neighbour — and it did not cover the
addition. A held-prose pass is owed before qualification, and it is recorded as
owed rather than described as done.

## Capabilities

### C1 — Architecture record and session governance

`DECISIONS.md` D23 records the founder architecture decision this release rests
on, additively, in the form D14 established. D24 records the rule that decides
the version class: an obligation an adopting project cannot fail to satisfy is
mandatory, one that needs new project capability is declared.

`docs/RP2.3-ARCHITECTURE.md` states the only thing the layering picture gains —
the first machine-written, machine-transitioned state in the pack's history —
and the three properties that keep it from being a second authority.

`docs/RP2.3-CAPABILITY-MAP.md` is the plan, its dependency order, the two
orderings that are not preferences, and what was removed from scope.

**RP3-2 — a guard demanded that a superseded release's own gate record be
rewritten.** Found by appending a decision, which is the ordinary act it was
written to survive.

`test_every_pointer_at_the_decision_layer_reaches_the_last_decision` requires
every `D<n>-D<m>` range to name the highest decision on file, and scanned a
typed literal `docs/RP2.2-*.md`. Appending D23 and D24 put two documents in
breach: the previous release's packet, and the previous release's own CHANGELOG
entry. Both were true when written. Its sibling guard,
`test_no_document_restates_a_count_of_things_the_repository_can_count`, already
exempts prior releases' documents in terms — *rewriting them to satisfy a rule
invented afterwards is the one thing this pack's own policy forbids* — so the
two guards disagreed about whose documents they were checking, and the one that
was wrong was the one nobody was looking at.

Repaired at the root rather than at the symptom. Both guards now derive their
document set from the gate record the manifest declares, so a checker that reads
the declaration cannot disagree with it. The CHANGELOG is scoped to the entry
this release is adding, by the reader that already existed for the version
check. Both guards now also refuse to pass having scanned nothing, because a
glob that matches no files is indistinguishable afterwards from a glob that
found no offenders — the defect class this release exists to close, occurring in
the instrument on its first day.

Two further literals were derived rather than retyped: the baseline revision the
non-regression differential runs against, and the release whose held-prose
figure this one quotes. The second was hardcoded to `2.1.1`, so a release
comparing itself to 2.2.0 would have searched for a sentence nobody would write
and failed with a message about the wrong release.
