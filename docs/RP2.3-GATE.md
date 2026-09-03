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

### C2 — Checker hygiene: the instrument before the measurement

Second, and the ordering is the point. The rehearsal obligations this release
must satisfy are unconditional about it — *every rehearsal's own tooling is
subject to these rules* — so building the instruments after the measurements
they validate would qualify the release with the same class of defect it exists
to close.

`tools/instrument.py` carries four refusals and one output requirement. Nothing
in it is about whether a check is *correct*; all of it is about whether the
answer is interpretable, which is a different property and the one that failed.

**RP3-3 — a gate with two modes named neither.** Reproduced on a scratch
repository at the frozen baseline: one range, one vocabulary, two tiers. The
tiered run printed `clean`; the strict run printed `1 leak(s)`. Neither headline
said which tier produced it, and the staged gate hid its mode in a suffix on the
provenance line, where a reader taking the first line of a stored report never
sees it. The same shape appeared on a real tree, where the two tiers' counts differ,
and a recorded limitation then quoted one of those counts without its tier —
proposing a remedy that could not have cleared the hits the other tier finds.
Repaired: the mode is composed *inside* the headline, before the verdict, and a
test asserts the position rather than the presence.

**RP3-4 — a scan that read nothing reported `clean`.** Reproduced:
`clean (0 commits, 0 blobs)`, byte-comparable to a range that was read and found
safe. `NOTHING EXAMINED` is now a third verdict with its own exit status — `2`,
this module's existing code for a verdict it could not reach — and the report
says what the usual cause is, because it is almost always a baseline or a ref
that is not the one the caller meant. Deliberately not a refusal of empty
counts in general: a range with one commit and no blobs is a real observation,
and a guard that refused it would refuse correct work.

**RP3-5 — a checker silently read a stale copy of its own rule.** Reproduced
against the frozen baseline, and this is the one that was not on the inherited
list. `_load_default_terms` searched three locations in order — the declared
pack root, the module's own root, then *the directory beside the project's own
contract* — took the first that existed, and reported only how many terms it
had loaded. A project that declares a pack root whose rule is missing therefore
got a copy from its own working directory, applied it, and had no way to find
out. The same shape elsewhere was measured at nine refusals where the real count
against the current rule was one.

Repaired in two halves, because either alone is insufficient. A search order
that lands outside the declared root is now a **refusal** naming both the file
it refused and everything else it looked at; and every scan reports the file it
actually read, with its digest, so a surprising finding count can be attributed
to the tree or to the checker before anyone starts editing history. Verified
read-only against a live 215-commit consumer repository: the mode, the counts
and the rule's path and digest all appear.

**One candidate is not a search order**, and the distinction is reported rather
than flattened. A project naming exactly one absolute location has not been
substituted against — it asked for that file, the choice is visible in its own
contract, and the digest is in every report. That resolution is labelled
`declared`, distinct from `canonical`; refusing it would have refused a real
consumer shape, which is how this class of control fails in the other
direction.

**RP3-7 — an equivalence gate that never named the layer it entered.**
`surface_diff` compares two revisions' public Python surface and carries an
honest gap — class attributes, dataclass field types, base classes, nested
classes — in its docstring and its `--help`, neither of which is stored beside
the verdict. The class this belongs to survived six audit cycles and twelve
blind legs elsewhere: a parity gate compared two transports' already-decoded
arguments and was structurally unable to see that the two decoders disagreed
about what the same request text meant. The layer statement now prints with
every verdict, clean ones included, and an equivalence report missing either
side is refused at construction.

**The toolbelt's launch surface is declared and enforced.** Every read it
performs is a Git invocation through one function, so `gitread` declares
`launches=("git",)` with its reason, and the launch helper refuses an executable
the declaration does not name. The instance behind this crossed a host security
boundary by launching a browser; the version of the rule that was a note had
already failed four times.

**Mutation-checked, eight for eight.** Each guard was broken deliberately and
the suite went red: the empty-count check forced false, the mode appended after
the verdict instead of inside it, the root check disabled, the launch check
made permissive, the equivalence-side check removed, the layer statement not
printed, the nothing-examined exit folded back into `0`, and the staged mode
returned to the provenance line. A killed mutant proves the check can fail, not
that it asks the right question — the pinned-test-asserting-the-buggy-value
case is why that sentence is here rather than a claim of correctness.
