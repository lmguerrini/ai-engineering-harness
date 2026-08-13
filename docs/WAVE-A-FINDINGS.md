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

---

## F3 — two toolbelt inputs had no declared source in `PROJECT.yaml`

**Severity:** MINOR (structural). **Status:** CLOSED — repaired by coordinator.
**Found by:** coordinator, by execution against the fixture repository.

`workspace_report` ships with an intentionally **empty** default safe-generated
set — deny-by-default, so an artifact is classified because the project said so,
not because a tool guessed. That design is right. But `PROJECT.yaml.template`
declared no field to say it in, and likewise none for `outgoing_scan`'s
content-exempt paths. A tool input with no declared home is *"built but
unwired"* — the pack's own refusal criterion, applied to itself.

Left unrepaired, every capability close would trip on ordinary `__pycache__`
artifacts, and the coordinator would improvise flags per invocation until
somebody switched the check off — the exact failure mode the audit warns about.

**Repair.** Added a `workspace_classification:` section to
`PROJECT.yaml.template` carrying `safe_generated`, `ignore_private` and
`content_exempt`, each with its semantics stated. Template re-parsed as valid
YAML after the change.

**Coordinator error worth recording (twice now).** Both times this section
looked like a tool defect, it was the coordinator assuming an interface instead
of reading it: fnmatch-style `__pycache__/*` patterns against a matcher that
documents **gitignore** semantics (trailing slash covers a directory; `*` does
not cross a separator). The documented form classifies all 7 artifacts and exits
0. The same error shape produced the first leak-injection instrument. Recorded
because "the tool is broken" is the most expensive wrong conclusion available to
a coordinator, and it was reached twice from the same cause.

---

---

## F4 — `scope_check` accepted a path with an interior record separator

**Severity:** MATERIAL. **Status:** CLOSED — repaired and verified by execution.
**Found by:** coordinator, by execution during the Wave-B T1 ingestion.

**Mechanism.** `normalise()` refused leading and trailing whitespace via
`path != path.strip()`, but nothing rejected a separator *inside* the string.
`"src/ok.py\ntests/evil.py"` normalises to a value beginning under an allowed
root, so it was reported **CONTAINED** — carrying a second path that was never
checked against the mutation boundary through a single approving verdict.

**Reproduction (before repair).**

    scope_check --allow src -- "src/ok.py\ntests/evil.py"
    CONTAINED: 'src/ok.py
    tests/evil.py' -> 'src/ok.py
    tests/evil.py'
    exit=0

**Why it is material, not cosmetic.** This is the tool the architecture audit
singled out as having "resisted every attack from both lenses across four
rounds", applied at ingestion *before validation spends anything*. The delivery
mechanism is not exotic: `git status --porcelain | awk '{print $2}'` piped into
the tool produces exactly this blob under a shell that does not word-split
unquoted expansions — and **the coordinator wrote precisely that invocation on
the first attempt.** A boundary defeated by the most natural way to call it is
defeated.

The recorded attack matrix (`..` climbing, absolute, UNC, drive letter, NUL,
whitespace) covered *leading and trailing* whitespace. Interior separators were
never in the domain. Same shape as every other finding in this register: the
enumeration was sound over the wrong question.

**Class named before repair:** *one argument must denote exactly one path* —
therefore every record separator, not merely the newline that surfaced.

**Repair.** `normalise()` refuses any candidate containing `\n`, `\r` or `\x00`
anywhere. POSIX permits these in filenames; a boundary gate refuses them anyway,
because "refuse when the answer is unclear" is the rule that has held.

**Sibling-mutation check — RESULT.** The named-site-only repair is "refuse
`\n`". Re-introduced exactly that: **3 tests went RED**
(`test_interior_carriage_return_is_refused`, `test_interior_nul_is_refused`,
`test_nul_byte_is_refused_without_crashing`). The class-level fix was restored;
suite 95 passed.

**Deliberate behaviour change, recorded.** One pre-existing test asserted that a
NUL byte was *not* refused and that the byte was preserved. That test pinned the
implementation; its stated intent was a property — never crash, never silently
change containment. Refusing satisfies that intent strictly more conservatively,
and the operating system rejects a NUL in `argv` before an invoked tool sees it,
so acceptance bought nothing. This **strengthens** a boundary control, so it
needs no governance waiver; a weakening would have.

---

---

## F5 — the commit contract's read-back half rejected git's own output

**Severity:** MATERIAL. **Status:** CLOSED — repaired and verified by execution.
**Found by:** coordinator, by execution, while committing Wave-B task T1.

**Mechanism.** `git log -1 --format=%B` terminates a message with **two**
newlines. `_structural_violations` stripped exactly one (`message[:-1]`), so a
blank line survived and read as `EXTRA_CONTENT`. Separately, the `SHAPE` regex
was matched against the **raw** message while the line checks used the stripped
body — one rule with two representations.

**Reproduction.** The pre-commit side of the contract passed on the T1 message
and the read-back side failed on the *same commit*:

    commit_gate /tmp/t1msg.txt   -> VALID          (exit 0)
    git log -1 --format=%B | commit_gate
                                 -> VIOLATION EXTRA_CONTENT: no prose or blank
                                    lines are permitted after the bullets, found ''

**Why it is material.** Double-sided validation is a governance control, and its
read-back half was unusable in its documented form: **every well-formed commit
failed it.** A control that always fails is a control that gets bypassed, and
the operator learns to ignore it — the false-positive cost the pivot warns about
in exactly these bespoke gates.

**Class named before repair:** *trailing blank lines are not content, on every
validation path, and every path validates the same normalised body.*

**The first repair was the named-site-only fix, and the mutation caught it.**
Changing only `message[:-1]` → `message.rstrip("\n")` moved the failure from
`EXTRA_CONTENT` to `SHAPE`, because the shape regex still matched the raw
message. The class fix points both paths at `body`.

**Sibling-mutation check — RESULT.** Re-introduced exactly the named-site-only
repair (line checks stripped, `SHAPE.fullmatch(message)` restored): **2 tests
went RED**. Restored; suite **98 passed**. Negative control holds — real prose
after the bullets still trips `EXTRA_CONTENT`.

---

---

## F7 — an auditor ran a Git write in the coordinator's live working tree

**Severity:** MATERIAL (protocol, not code). **Status:** CLOSED — protocol
amended; no damage, verified by the fence.
**Found by:** coordinator, reading the auditor's own incremental findings file.

**What happened.** The blind primary auditor was instructed "read-only; do not
run any git command that writes." To pin the immutable revision it ran

    git checkout --detach 3f2c334…

in the **coordinator's live repository**, while a second (cross-vendor) auditor
was reading the same tree.

**Blast radius, measured against the fence snapshot taken before dispatch:**

    pre-HEAD  3f2c334…      now-HEAD  3f2c334…      (same commit)
    refs      UNCHANGED     stash     UNCHANGED     tree clean

No commit created, no ref moved, no content changed — only the symbolic ref
detached from the branch to the same commit. **The capability branch still
points at `3f2c334`.** The git fence did exactly what it exists to do: made an
unauthorized Git write detectable rather than trusted-not-to-happen.

**Why it is a finding anyway.** Two auditors and the coordinator were sharing one
working tree. The pack already carries the rule *"the coordinator must not edit a
working tree while a worker runs in it"* and *"serialize workers sharing a tree"*
— and the symmetric case was never written down: **an auditor must not operate in
the coordinator's live tree at all.** The project structure already provides
`worktrees/` for exactly this, and the architecture's own worker topology is
"detached, credential-free, disposable". The audit path simply never used it.

**The brief was the defect, not the auditor.** It named the immutable SHA but
gave the auditor the live repository and no checkout of its own, so pinning the
revision *required* either a Git write or trusting that HEAD would not move. An
instruction that forbids the only available means of compliance is a
specification error.

**Repair (protocol).** `templates/audit-brief.template.md` now requires the
coordinator to provide the auditor a **disposable read-only checkout** —
`git worktree add --detach <path> <sha>` under `worktrees/`, created by the
coordinator before dispatch — and to state that the auditor must not touch any
other tree. `capability-closure` names the same step at `CLOSURE_AUDIT`.

---

**Not a finding — checked and cleared:**
- `clean` is correctly tri-state at the data level: `not leaks and not skipped`.
- The baseline-exempt-from-itself fix works: without `--exempt` the reviewed
  baseline trips on its own recorded match (reproduced); with it, it does not.
- The CLI exit status is correct (1 on leaks). An earlier reading of `0` was
  `head`'s status through a pipe, not the tool's.
