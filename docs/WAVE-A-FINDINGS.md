# Wave A — findings register

Append-only. Every finding is reproduced by the coordinator's own execution
before it counts. A finding raised by a worker or an auditor and *not* reproduced
is labelled as such.

---

## F1 — `outgoing_scan` reports `clean` without disclosing what it declined to read

**Severity:** MATERIAL. **Status:** CLOSED — repaired (1 of 3 attempts), verified
by the coordinator re-running the original reproduction.
**Found by:** coordinator, by execution. **Reproduced:** yes, directly.

**Closure evidence.**

    RENDERED : outgoing range 199c79da…..HEAD: clean, 1 file(s) content-exempt
               by declaration (1 commits, 0 blobs)
      content exempt by declaration: REVIEWED-BASELINE.md

`clean` stayed `True` — the verdict semantics were correctly left alone; this was
a disclosure defect. Sibling mutation (gate solely on `not self.skipped`) was
re-introduced by the implementer and the new test went RED under it, then the
class-level fix was restored. Suite 91 passed; the 7-surface attack still blocks
7/7 with no regression.

**Mechanism.** `OutgoingReport.render()` opens with

    if self.clean and not self.skipped:
        return f"outgoing range …: clean ({n} commits, {m} blobs)"

and the loop that prints `exempted` lives *after* that early return, in the
leaks branch. So a scan that had content exemptions and found no leaks renders
as a bare `clean` and never names them.

**Reproduction.**

    scan_outgoing(repo, ref="HEAD", baseline=<base>, scanner=…,
                  content_exempt_paths=["REVIEWED-BASELINE.md"])

    clean     : True
    exempted  : ['REVIEWED-BASELINE.md']
    RENDERED  : 'outgoing range 199c79da…..HEAD: clean (1 commits, 0 blobs)'

**Why it is material.** The module's own docstring states the opposite contract:
"every exempted blob is named in `exempted`, so the report says what it did not
read rather than reading clean." The data structure honours that; the rendering
does not. The rendered string is what gets stored as capability evidence and read
later by an auditor who did not run the command. That auditor has no way to learn
that a file's content went unread. This is over-claiming — the evidence-integrity
failure class — in the pack's highest-value asset.

`blobs_examined: 0` hints at it, but a reader inferring an exemption from a
count is not disclosure.

**Repair required.** The clean branch must name the exemptions, e.g.

    outgoing range …: clean, 1 file content-exempt by declaration
      content exempt by declaration: REVIEWED-BASELINE.md

**Sibling-mutation check on repair.** Re-introduce the named-site-only fix —
printing exemptions only when `skipped` is non-empty — and require the test to go
red. The class is "a report that declines to read something must say so on
*every* rendering path", not "this one branch forgot a loop".

---

## F2 — the requirement-coverage gate checks the coverage file against itself

**Severity:** MATERIAL. **Status:** CLOSED — repaired and verified by execution.
**Found by:** coordinator, by execution. **Reproduced:** yes, directly.

**Mechanism.** `validate_requirement_coverage.py` derives the expected
requirement count from a `<!-- requirement_count: N -->` comment **inside the
coverage file it is validating**. The authority for how many requirements exist
is `REQUIREMENTS.md` — the verbatim transcription of the official specification.
The gate never reads it. So the file being checked also declares the standard it
is checked against.

**Reproduction.** Official specification has three requirements. Coverage drops
`R2` from the table *and* decrements the declared count:

    <!-- requirement_count: 2 -->
    | R1 | … |
    | R3 | … |

    $ validate_requirement_coverage.py cov-drift.md
    Requirement coverage: OK (2 requirements)
    exit=0

`R2` has vanished from the project and the gate is green.

**Why it is material.** This is the exact failure the mechanism exists to
prevent — "no grouping may erase an individual requirement" — and it is the
Kernel's own dominant failure class reproduced in miniature: **the domain was
derived from the wrong abstraction.** The gate enumerates rows in a derived view
and calls that completeness, while the authority sits unread in another file. It
is also a direct violation of *one authority per fact*: a generated view was
allowed to become its own gate input.

Caught only because the gate was executed against an adversarial case. Its own
three happy-path cases all passed.

**Repair (coordinator, attempt 1 of 3).** The validator now takes
`REQUIREMENTS.md` as the authority and cross-checks **identifiers**, not counts:
every authority id must appear in coverage; every coverage id must exist in the
authority; duplicates refused. The in-file declared count is kept only as a
secondary tripwire. Verified by execution below.

**Sibling-mutation check — RESULT.** The named-site-only repair here is "also
read `REQUIREMENTS.md` and compare the two counts." That mutation is defeated by
construction: with `R2` dropped and `R9` added, the counts are equal (3 = 3) and
a count comparison passes, but the repaired gate still fails:

    requirements with no coverage row: R2
    coverage rows for requirements the specification does not declare: R9
    exit=1

The class was "compare by identifier against the authority", not "read the other
file too". Verified by execution across three cases: all-covered → pass; the
original drift case → fail; the sibling mutation → fail.

---

**Not a finding — checked and cleared:**
- `clean` is correctly tri-state at the data level: `not leaks and not skipped`.
- The baseline-exempt-from-itself fix works: without `--exempt` the reviewed
  baseline trips on its own recorded match (reproduced); with it, it does not.
- The CLI exit status is correct (1 on leaks). An earlier reading of `0` was
  `head`'s status through a pipe, not the tool's.
