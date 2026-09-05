# DESIGN — RP2.4.1 R1/R2: design strength and design provenance

**Change class:** MATERIAL
**Base revision:** 9d906ce64bd69cb1a29594a7110829da7df5d996
**Frozen:** yes

Written before the implementation it governs. `tools/design_record.py` reads it;
`tools/capability_open.py` composes that reading. This record authorises nothing.

Two reproduced blockers share one question — *what does this capability's design
have to establish, and did it establish it before the work began?* — and 2.4.0
answers it in two places that disagree. R1 and R2 are therefore one design.

## The mechanism

`DesignRecord.problems` becomes the single place that answers whether a record
satisfies a REQUIRED design strength and whether the record artifact itself
existed, byte-identical, before mutation began; every caller states what it
requires instead of re-deriving the answer beside it.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Caller-side strength comparison in `capability_open`, plus a self-declared freeze timestamp in the record | REJECTED | Both halves fail. The comparison repairs one caller while `design_record` keeps blessing a weaker record for the CLI, for a project's own script and for every future caller — the two-answers shape limitation 68 records as this release line's headline defect. And a record can state any timestamp it likes, which is the backdating this exists to refuse; it would also add a new required consumer-facing input and push the release across the PATCH boundary |
| 2 | Caller-side strength comparison in `capability_open`, plus git provenance of the record artifact | REJECTED | The provenance half is right, but the strength half still leaves the shared question answered in two places. A second caller — and `design_record.py` ships its own CLI — reaches the weaker answer directly, so the reproduced R1 scenario is closed for one entry point and open for the others |
| 3 | The reader owns both: `DesignRecord.problems(required_class=...)` ranks TRIVIAL < ROUTINE < MATERIAL and refuses a record weaker than what is required, and the same call establishes that the record's bytes were already present at `mutation_begins_at` | SELECTED | One module answers the whole question — *what must this design establish, and did it establish it before the work began* — and every caller states what it requires rather than re-deriving the answer beside it. Git is the one party to the provenance claim that cannot be backdated by editing a file. Every input already exists: record path, repository, `mutation_begins_at`. The required-strength parameter defaults to none, so a caller that requires nothing gets 2.4.0's answer unchanged |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | Record uncommitted, or edited after mutation began | Its bytes differ from the blob at `mutation_begins_at`; refused, naming which |
| 2 | Record renamed or moved between freezing and implementation | The path is absent at `mutation_begins_at`; refused rather than guessed. Re-freezing against the new path is the operator's move |
| 3 | Root is not a git checkout, so provenance cannot be read | Refused with that reason stated; never reported as established |
| 4 | `mutation_begins_at` not supplied | Provenance is not checked and the report says so. Unchanged from 2.4.0 and still the documented weak path; this release does not widen it |
| 5 | A caller requires a strength and passes it in a different spelling | The required class is validated against `CHANGE_CLASSES` and refused if unknown, rather than silently ranking as TRIVIAL |
| 6 | `capability_open` runs the design gate against the wrong repository | The contract's own `repository()` is passed, so provenance is read where the project's history actually is |

## Authority boundaries

This reports; it opens nothing, adjudicates no product meaning, and decides
nothing about whether a design is *good*. It may not weaken any row of
`policy/hitl-matrix.md`, and it does not: it makes an existing gate refuse in
cases it previously passed. It must never make a previously refused case pass.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O1 | NEGATIVE | a TRIVIAL record does not satisfy a MATERIAL requirement | tools/tests/test_design_record.py::test_a_weaker_record_does_not_satisfy_a_stronger_requirement |
| O2 | ACCEPTANCE | a valid MATERIAL record satisfies a MATERIAL requirement | tools/tests/test_design_record.py::test_a_material_record_satisfies_a_material_requirement |
| O3 | ACCEPTANCE | genuinely trivial work stays lightweight when nothing stronger is required | tools/tests/test_design_record.py::test_trivial_work_requiring_nothing_stays_lightweight |
| O4 | NEGATIVE | a record introduced after mutation began is refused | tools/tests/test_design_record.py::test_a_record_committed_after_mutation_is_refused |
| O5 | NEGATIVE | a record whose bytes changed after mutation began is refused | tools/tests/test_design_record.py::test_a_record_edited_after_mutation_is_refused |
| O6 | ACCEPTANCE | a record committed before mutation began is accepted | tools/tests/test_design_record.py::test_a_record_committed_before_mutation_is_accepted |
| O7 | NEGATIVE | provenance that cannot be read is refused, never assumed | tools/tests/test_design_record.py::test_provenance_that_cannot_be_read_is_refused
| O8 | ACCEPTANCE | every spelling of the mutation revision gives one answer | tools/tests/test_design_record.py::test_every_spelling_of_the_mutation_revision_agrees |
| O9 | REHEARSAL | the real capability-open path refuses the weak pair and opens the strong one | tools/tests/test_lifecycle_rehearsal.py::test_a_material_capability_needs_a_material_design_through_the_real_path |
| O10 | MUTATION | removing the strength comparison fails O1; removing the provenance check fails O4 | tools/tests/test_design_record.py::test_a_weaker_record_does_not_satisfy_a_stronger_requirement |
