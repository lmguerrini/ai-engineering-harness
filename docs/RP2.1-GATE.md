# RP2.1 — gate record

**Date:** 2026-08-15. **Pack VERSION:** 2.1.0. **Assessed by:** COORDINATOR, by
execution. Every claim below was re-run before it counted.

Baseline at the start of this pass: VERSION `2.0.0`, HEAD `0ec6726`, **98 tests
passing**. Final: **167 tests passing**, +69.

| # | Gate condition | Result | Evidence |
|---|---|---|---|
| 1 | All tests green | GREEN | `python3 -m pytest tools/tests/ -q` → **167 passed**, coordinator-re-executed |
| 2 | Every tool standalone | GREEN | all 9 tools run `--help` and execute from `/tmp` |
| 3 | Tool imports contained | GREEN | own AST check over `tools/*.py`: stdlib + `tools/` siblings only. **VIOLATIONS: none.** PyYAML is present on this host and deliberately **not** used (D3) |
| 4 | No stateful authority reintroduced | GREEN | `publication_gate` and `project_contract` are a checker and a reader; no state held and adjudicated in one component |
| 5 | No Git write verbs added | GREEN | the four new `gitread` verbs are `for-each-ref`, `config --list`, `merge-base --is-ancestor`, `rev-list`, plus `ls-files --stage`. All read |
| 6 | Contract reader fails loud | GREEN | 7 malformed-document cases raise; a missing default term set raises; an unreadable contract exits **2**, distinct from a clean 0 |
| 7 | Publication gate, executed | GREEN | see below |
| 8 | Commit-drift detection | GREEN | see below |
| 9 | Cross-domain non-regression | GREEN | fixture-tally scans clean via `--project` alone; real 220-line `PROJECT.yaml` parses correctly |
| 10 | Idempotency | GREEN | repeated invocations byte-identical; every tool is a pure function of repository state |
| 11 | Held prose within budget | **QUALIFIED — 10% over, recorded** | see below |
| 12 | Candidate-inbox separation preserved | GREEN | the pack was read-only during the project; every change here entered through this evolution pass |

## Gate 7 — the publication gate, executed

**Two defects in this pass's own work were found by executing the gate, not by
its tests.**

1. **Wrong matcher domain.** Ref globs were matched with `pathmatch` — the
   *filesystem* semantics, where `*` does not cross `/`. In a git refspec it
   does, so `refs/heads/*` covers `refs/heads/feature/x`; matched as a path, a
   branch of that shape is misreported as an unrecognised namespace — wrong, and
   noisy enough to train a reader straight past the findings that matter. This is
   the same wrong-domain shape as EC-K, committed by the delta that closes EC-K.
2. **Inverted emphasis.** The report put `REACHABLE FROM THE PUBLIC REF` in
   capitals and `not reachable` in lower case. Both are true statements, and the
   alarm belongs on the second — a ref already contained in the public ref adds
   no object to the push; a ref outside it holds material nobody reviewed.
   Renamed to containment and re-rendered.

Both repaired, both now carry a falsification test. Neither was reachable from
the test suite as written, because both tests and implementation shared the
author's assumption about what the fixture looked like.

## Gate 8 — commit-convention drift

`commit_gate --range` checks a whole range of commits rather than only the
newest message. This is the governing prompt's lesson H, and it is the argument
for a range check rather than more reminders.

## Gate 9 — the vocabulary tiering, measured on the real corpus

Same repository, same range, `refs/heads/main` full history, **no content
exemption declared at all**:

| Vocabulary | Findings | True positives |
|---|---|---|
| RP2.0 flat (every term on every surface) | **102** | 0 |
| RP2.1 tiered | **0** | 0 |

The 102 break down as 89 from the opt-in ticket pattern (`utf-8`, `SHA-256`,
lockfile entries), 6 × `claude` (Jean-Claude Martin in committed prose),
6 × `terra` (Italian for "ground"), and 1 ticket-pattern hit in a commit
message. With the tiered set no content exemption is needed at all.

**The honest counterpoint, found by testing for it.** Tiering removes bare
common words from *committed blob content*, and process vocabulary reaching
prose about the work (`harness` in a test docstring, for instance) is exactly
that shape. The multi-word forms — `engineering
harness`, `worker envelope`, `runtime pack` — still fire on content and carry
most of the real signal, but "most" is not a claim to make about a leak gate.
Closed by making the **staged** gate strict: full vocabulary where a correction
costs one reword, tiered where it costs a commit, a fixup and a rebase.

## Gate 11 — held prose, measured and over

    skills/core/*.md + policy/*.md + the two installed skills    2,204 lines
    target                                                      ~2,000
    Wave B baseline                                              2,022

**10.2% over, recorded rather than rounded.** Deletions were taken first, as
`BUDGETS.md` requires — both cuts Wave A had named in advance (the
`delegation.md` / `routing-policy.md` overlap on recording a not-chosen
candidate; `evidence.md` restating `repair.md` on reproduce-before-repair) — and
the publication *procedure* was moved to a pull-on-demand template, leaving only
the invariant held. Together those recovered ~15 lines against ~180 added.

I stopped there deliberately. Reaching 2,000 from here means deleting the
evidence sentences that make a rule survive a cold read — the measured numbers,
the failure that motivated each rule — and Wave A refused that trade for the
same reason. Every added line is tied to a specific measured failure.

**Next cuts if the budget binds**, named now so the decision is not improvised:
`capability-closure/SKILL.md` at 583 lines is the largest single item and has
not been re-read for redundancy since Wave A cut it from 786; `skills/core/
audit-strategy.md` and `policy/auditor-strategy.md` were de-duplicated once and
are worth re-checking; the `policy/routing-table.md` derived view could move to
`docs/` on the same argument that excludes `observations.jsonl`, though it is
genuinely consulted per session and I declined to re-scope it to flatter the
number.

## Budgets consumed

    implementation passes                1 of 1
    qualification repair passes          1 of 1
    final verification pass              1 of 1
    HITL stops                           0  (none genuine; none false)

Bounded convergence respected. Both qualification defects were found in the
repair pass and fixed within it; the verification pass found none.

## Deliberately deferred, each with a named trigger

- **EC-O** (machine-path rule fires on fixed platform locations) — trigger: a
  second project blocked by it where the workaround is not, as it was here,
  better engineering anyway. Narrowing the one rule that catches real leaks on
  one project's evidence is the highest-regret direction available.
- **EC-T** (certify a binary rather than exempt it) — trigger: a project
  shipping enough unscannable blobs that the exemption total stops being
  readable. `skipped` and `exempted` are already distinct in the data model.
- **EC-Z** (a project-specific code lesson) — rejected for Core: it would
  couple the pack to one project's internals.
