# RP 2.4.1 — gate record

A bounded blocker-repair release. It closes the six defects an independent full
behavioural audit of frozen 2.4.0 reproduced, and nothing else. No Evolution
Candidate is implemented here, no capability is added, and 2.4.0 is untouched.

## Subject

| | |
|---|---|
| Version | 2.4.1 (`VERSION`) |
| Baseline | `9d906ce64bd69cb1a29594a7110829da7df5d996` — the 2.4.0 release commit |
| State | `IN_PROGRESS`. **No project may pin this.** |
| Revision, digest | in `PACK_MANIFEST.json`, recomputed over the tree this gate ran against |

## SemVer, derived

`PACK_MANIFEST.json` `version_semantics`: PATCH is *backward-compatible fixes,
metadata/docs corrections, **enforcement of already-promised guarantees***.
All six repairs are the third of those — each makes a mechanism do what its own
documentation, or the module beside it, already said it did:

| Repair | The promise it enforces |
|---|---|
| R1 | the scaling table: `MATERIAL` requires the whole record |
| R2 | `design_record`: "a design, frozen **before** the implementation it governs" |
| R3 | 2.4.0 limitation 16: an unreported effort cannot complete an identity |
| R4 | `gitread`: neutralised "for *every* invocation rather than at the call sites somebody remembered" |
| R5 | `pack_pin`: "a verifier must mean exactly what the documentation around it claims" |
| R6 | `pack_pin`: "a pinned release is a claim about the *directory*, not only about the index" |

MINOR was checked and rejected: no policy, tool or capability is added.
`DesignRecord.problems` gains one keyword argument that defaults to 2.4.0's
behaviour, and `backend_contract` exports one function two existing callers
share. MAJOR was checked and rejected: no authority, contract or migration
change is incompatible, no contract key or CLI input is added or removed, and no
project's pin moves. Behaviour that previously passed and now refuses is the
repair, not an incompatibility: every such case is one where the report was
making a claim it could not support.

`tools/surface_diff.py . 9d906ce64bd69cb1a29594a7110829da7df5d996 HEAD` is the
mechanical check, and its answer over the non-test modules is:

    added_public_name    backend_contract.normalised_identity_value
    added_star_export    backend_contract.normalised_identity_value
    added_public_name    design_record.CHANGE_CLASS_RANK
    added_optional_parameter  design_record.DesignRecord.problems

**Nothing is removed and no signature changes.** The one judgement in that list
is whether two added names cross into MINOR. They do not: MINOR is *a new
policy, tool or capability*, and a consumer gains no ability here it did not
have. `normalised_identity_value` is the normalisation the configuration-string
parser already performed, lifted into one place so the structured path cannot
answer differently; `CHANGE_CLASS_RANK` is the ordering `required_for` and the
scaling table already implied, written down. No tool ships that did not ship
before — which is the criterion 2.4.0 itself used when it derived MINOR, and it
is the criterion that fails here. The added parameter is optional and defaults
to 2.4.0's behaviour.

## Figures, bound rather than typed

Every number a reader might rely on is either measured by a test or given as a
command. Four stale figures in one section of an earlier gate record is what
taught this pack the difference.

    held prose, in-release (skills/core/*.md + policy/*.md) 1896

against the `policy/BUDGETS.md` ~2,000 target, and under it. The total including
the two installed adapters, and the percentage it is over, are in
`PACK_MANIFEST.json` `known_limitations` and are unchanged by this release,
which adds no line to either directory.

The suite count is not restated here. It lives in `PACK_MANIFEST.json` `tests.passed`,
and `test_the_recorded_test_count_is_the_count_the_suite_actually_collects` is
what binds that figure to what the suite really collects.

Delta against the frozen baseline: **not stated here.** Any number written in
this file is wrong the moment this file is edited, which is the manifest's
own-revision problem in prose. Measure it:

```bash
git diff --shortstat 9d906ce64bd69cb1a29594a7110829da7df5d996..HEAD
```

## What was run

Recorded in the release packet and reproducible from this checkout. The
deterministic suite, the release-integrity gates, the commit-range gate, the
release delta, a clean-room clone, the hostile line-ending clones, the hostile
Git-configuration attacks for R4 and R6, the design gate in both directions
through the real `capability_open` path, the structured/string `UNKNOWN`
equivalence, the integrated consumer lifecycle, two-consumer isolation, and cold
reconstruction.

## Mutation scoring

Nine well-formed subject mutants against a **green baseline that excludes the
tests which fail on any byte change** — the six identity-comparing tests
`PACK_MANIFEST.json` already names, plus
`test_lifecycle_rehearsal.py::test_a_project_verifies_the_pack_it_pins_rather_than_trusting_it`.
2.4.0 limitation 70 records this pack scoring one of its own passes without that
exclusion, so the exclusion is stated here rather than assumed. All nine killed.

## Evolution evidence

All six repairs classify as `RECURRENCE` under
`tools/evolution_evidence.py` against `policy/recurrence-classes.json`. No new
class was created, none was merged by guess, and no occurrence was overwritten.

## The freeze — NOT TAKEN

The transition to `QUALIFIED_AND_FROZEN` is `policy/hitl-matrix.md` row 2 and is
the founder's, not this work's. It has not been taken and nothing here infers it.

To take it, against a candidate named by all five fields:

```bash
cd <this checkout>
git rev-parse HEAD                      # the candidate revision
python3 tools/pack_pin.py . --version 2.4.1 \
    --sha <that revision> \
    --digest <PACK_MANIFEST.json tree_digest_sha256> \
    --state IN_PROGRESS                 # verifies the tree, and that it is NOT yet adoptable
python3 -m pytest tools/tests/ -q       # the population the manifest records
```

### What the freeze does not settle about publication

The publication adjudication this release still points at is
`docs/RP2.4-PUBLICATION-ADJUDICATION.md`, unchanged and still the owner of that
conclusion. **One occurrence in the complete reachable history names a real
machine account**, it is remediable only by a history rewrite (HITL rows 2 and
4), and that rewrite is not taken here. Nothing is published, so nothing is
exposed — but a record that states a publication conclusion while dropping its
only known exception is the defect this pack has already shipped once, so it is
stated here rather than left to the document next door.

Then, and only then, set `state` to `QUALIFIED_AND_FROZEN` in
`PACK_MANIFEST.json`, update the README state row, recompute the identity over
the tree that decision produced (`python3 tools/pack_pin.py . --write`), and
commit. Publication is a separate decision and is not authorised by the freeze:
no push, tag, remote, or consumer migration.
