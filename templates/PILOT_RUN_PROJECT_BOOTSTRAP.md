# Pilot Run Project — bootstrap template

**Status:** PREPARED, NOT EXECUTED. This template is ready to accept the official
task specification. **Nothing in it invents a requirement.** No Pilot Run
capability exists until the official specification is read.

**Applied by:** COORDINATOR, in the session that receives the official tasks.
**Entry gate:** Wave-B gate green; PROJECT.yaml authored and human-authorized
(HITL row 1); capability map frozen; measurement plan active.

---

## Step 0 — Before reading the official tasks

Confirm on disk, do not assume:

- [ ] `runtime-pack-2/VERSION` is the pack version this project will pin, and
      `PACK_MANIFEST.json` declares `state: QUALIFIED_AND_FROZEN`.
- [ ] The pin **verifies**, all three fields at once — not read, run:

      ```bash
      python3 <pack_root>/tools/pack_pin.py <pack_root> \
          --version <VERSION> --sha <full 40-char HEAD> \
          --digest <tree_digest_sha256> --state QUALIFIED_AND_FROZEN
      ```

- [ ] The gate record named by the manifest exists in `runtime-pack-2/docs/`.
- [ ] `tools/` tests pass at the exact pack HEAD.
- [ ] No project pins Kernel `042c1b9`. It is a frozen evidence archive.

Record all three pin fields in `PROJECT.yaml` `pack:`. Another project may be
pinned to this same release right now — that is supported and requires nothing
from either of them, because the release is read-only and no project state
lives inside it.

## Step 1 — Transcribe requirements verbatim, before decomposing

Create `projects/<project>/REQUIREMENTS.md` and copy every official requirement
**verbatim**, each with a stable identifier (`R1`, `R2`, …). Do not paraphrase,
merge, split, reorder, or interpret at this stage. Interpretation is Step 3 and is
recorded separately so the two can be told apart later.

    | id | requirement (verbatim) | source location |
    |----|------------------------|-----------------|

This file is the **single authority** for what was asked. It is written once and
corrected only when the official specification itself is corrected.

## Step 2 — Derive the capability map

`PROJECT → CAPABILITIES → TASKS`. **No Version layer** — the project is the
execution unit (audit §4, pivot §10).

A capability is a coherent slice that can be scoped, branched, validated, audited
and closed on its own. Capabilities may group requirements for execution
convenience. **Grouping may never erase requirement-level status or evidence.**

Write `ROADMAP.md` from `templates/ROADMAP.md.template`: capabilities,
dependencies, order, and for each capability the list of requirement ids it
carries.

## Step 3 — Requirement coverage mechanism (the anti-grouping control)

Create `projects/<project>/REQUIREMENT_COVERAGE.md` from
`templates/requirement-coverage.md.template`. **Every requirement holds its own
row, independently, forever** — even when several share a capability, a task, a
commit, or a test.

The gate enforces **exactly these eight columns, in this order** — they are the
`COLUMNS` list in `templates/validate_requirement_coverage.py`, and a table of
any other shape fails on every row:

    | ID | Source | Capability | Task | Implementation status | Required validation | Evidence | Status |

- `Status` is tri-state-aware: `PLANNED` / `IN_PROGRESS` / `PASSED` /
  `BLOCKED` / `N/A-with-reason` / `HITL_ACCEPTED_LIMITATION`. **Not-run is never
  recorded as passed. Absent is never recorded as zero.**
- `Evidence` is a content-addressed reference produced by `evidence_put`, not
  a prose claim.
- **Interpretation notes have no column**, and adding a ninth breaks the gate.
  They live in a keyed section beneath the table, one entry per requirement id.
  That is where Step 1's verbatim text meets judgment: any reading that narrows
  a requirement is recorded there and, if it has cross-capability blast radius,
  escalated (HITL row 5). Do **not** drop the note to satisfy the tool — the
  note is the anti-narrowing control. An earlier version of this sketch showed
  seven columns ending in `interpretation note`; following it literally cost a
  bootstrap author a full rewrite of the register.

**The check:**

```bash
python3 templates/validate_requirement_coverage.py REQUIREMENTS.md REQUIREMENT_COVERAGE.md
```

It takes **two** files on purpose. `REQUIREMENTS.md` is the authority for *which*
requirements exist; `REQUIREMENT_COVERAGE.md` is a derived view of how each is
met. The gate compares them **by identifier, in both directions** — every
authority id must have a coverage row, and no coverage row may name a
requirement the specification does not declare. It also refuses any requirement
whose status is undecided and which carries no evidence: the condition that means
*nobody decided*.

Comparing counts is not sufficient and was an early defect here: a requirement
dropped from the coverage table *and* from a self-declared count passed green,
and swapping one requirement for another keeps the counts equal. A derived view
may never be its own gate input.

Application points, named:
- capability closure — coordinator runs it before CLOSED is recorded;
- project close — coordinator runs it before the human acceptance packet.

## Step 4 — Author PROJECT.yaml

From `templates/PROJECT.yaml.template`. Must state: repository path, integration
ref, release ref, pinned pack VERSION, declared dimensions, validation profiles
with their real commands, mutation policy, private terms, critical domains, HITL
selections, and whether autonomous integration merges are permitted.

Owner-approved Git policy for this project (DECISIONS.md D6.6): distinct
integration and release refs; **autonomous integration merges allowed**; every
push, remote creation, tag, release merge, publication, deployment and submission
is **human-gated**.

## Step 5 — Freeze scope per capability, one at a time

Only the capability being started is frozen. `SCOPE.md` from its template, with
budget counters initialised from `policy/BUDGETS.md`:

    repair attempts per finding        0 / 3
    repair rounds this capability      0 / 2
    closure audit cycles               0 / 1
    auditor retries (external)         0 / 1
    — per material invariant —
    oracle-correction cycles           0 / 2
    implementation attempts            0 / 2
    post-audit sibling repair          0 / 1

Mark which requirements are **material** (silent, expensive, or irreversible on
violation). Those get full oracle discipline
(`skills/core/oracle-discipline.md`) and two blind auditors, one cross-vendor.
Everything else gets the routine path.

## Step 6 — Run the loop

Driven by the installed closure skill (`~/.claude/skills/capability-closure/`),
which is an **adapter, not an authority**. It lives outside the pinned release,
is covered by no digest, and can change under a running project without any pin
noticing. Where it and the pinned pack disagree, **the pinned pack wins**; a
project that genuinely needs an external skill to be normative pins and verifies
it under its own dependency contract, exactly as it pins the pack.

## Step 7 — Project close

- [ ] Final cross-capability audit (integration, composition, coverage).
- [ ] `validate_requirement_coverage.py` green, with no grouping erasing a row.
- [ ] Final full-history `outgoing_scan` over the whole repository.
- [ ] Human product acceptance packet generated from
      `templates/human-acceptance-protocol.template.md` (nine fields).
- [ ] Human release gate. **Push, tag, publication and submission are human
      actions.** The coordinator prepares; it never performs them.

---

## What this template deliberately does not do

- It does not name a single Pilot Run capability. Those come from the official
  specification and nowhere else.
- It does not assume a technology, a repository layout, or a deliverable format.
- It does not create a Version layer.
- It does not permit a requirement to exist only inside a group.
