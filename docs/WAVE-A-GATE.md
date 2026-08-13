# Wave A — gate record

**Date:** 2026-08-13. **Pack VERSION:** 2.0.0-wave-a. **Assessed by:** COORDINATOR,
by execution. Worker reports were re-executed before they counted.

Wave B does not begin until every row below is green.

| # | Gate condition | Result | Evidence |
|---|---|---|---|
| 1 | Every tool standalone | GREEN | all 7 toolbelt tools run `--help` and execute from an unrelated cwd (`/tmp`). `gitread` is the Git-read *layer*, not a listed tool; it has a usage line, not argparse. |
| 2 | All tests green | GREEN | `python3 -m pytest tools/tests/ -q` → **98 passed**, coordinator-re-executed |
| 3 | Tool imports contained | GREEN | own AST check: every `tools/*.py` imports only stdlib + `tools/` siblings. **VIOLATIONS: none.** No `hx`, no `sitecustomize`, no relative imports |
| 4 | No stateful authority reintroduced | GREEN | no sqlite/event-store/reducer/lifecycle/trust-root in `tools/`; only match was a docstring naming history. No tool writes outside a caller-supplied path except `evidence_put`, whose destination is an explicit argument |
| 5 | No Git write verbs in the read layer | GREEN | every `gitread` verb is `cat-file` / `rev-list` / `ls-tree` / `diff` / `status`. `"commit"` and `"tag"` occur only as `cat-file` object types |
| 6 | Held prose within budget | GREEN (0.55% over a ~2,000 target, recorded) | see count below |
| 7 | Every rule names its application point | GREEN | all 17 HITL rows carry actor + step + file. Toolbelt application points named in `capability-closure`. F3 was raised and repaired precisely because two tool inputs had no declared home |
| 8 | Leak-injection acceptance case defined | GREEN | `docs/leak-injection-acceptance.md`, 7 surfaces × rule class |
| 9 | Leak injection **executed** | GREEN | **7 / 7 blocked**, exit 1. `docs/acceptance/RESULT-leak-injection.md` |
| 10 | Public-safety architecture preserved | GREEN | zero vendor names and zero private paths in `skills/core/`; vendor names confined to `policy/` |
| 11 | No private runtime material in project Git | GREEN | fixture repo full-history scan: `ROOT..main: clean (1 commits, 5 blobs)` |
| 12 | Requirement-coverage mechanism works | GREEN | 3 cases + sibling mutation, all by execution (F2) |

## Findings raised and closed in Wave A

| id | severity | status |
|---|---|---|
| F1 | MATERIAL | CLOSED — `outgoing_scan` reported `clean` without disclosing content exemptions |
| F2 | MATERIAL | CLOSED — requirement-coverage gate validated the coverage file against itself |
| F3 | MINOR | CLOSED — two toolbelt inputs had no declared source in `PROJECT.yaml` |
| F4 | MATERIAL | CLOSED — `scope_check` accepted a path with an interior record separator |
| F5 | MATERIAL | CLOSED — the commit contract's read-back half rejected git's own output |
| F6 | MINOR | CLOSED — capability status duplicated between `PROJECT.yaml` and `PROGRESS.md` |

**Zero open material findings.** Six raised, six closed.

**Every one was found by executing the artifacts adversarially, not by reading
them, and not one was caught by the implementing worker's own passing suite.**
Three (F1, F4, F5) sat in the toolbelt after it reported 90 tests green. That is
the architecture audit's central claim reproduced on the pack itself: **green is
"no known defect", never "no defect."**

Two are worth singling out. **F5's first repair was the named-site-only fix** —
it moved the failure from one rule to its sibling, and only the mandatory
sibling-mutation step exposed it. **F2 and F4 were both domain-derivation
errors**: a gate that enumerated rows in a derived view instead of consulting the
authority, and an attack matrix that covered leading and trailing whitespace but
never interior separators. Same shape as the defect class that ended the Kernel.

## Budgets consumed

    repair attempts on F1        1 of 3
    repair attempts on F2        1 of 3   (coordinator-executed)
    repair attempts on F3        1 of 3   (coordinator-executed)
    repair attempts on F4        1 of 3   (coordinator-executed)
    repair attempts on F5        2 of 3   (first was the named-site-only fix;
                                           the sibling mutation caught it)
    repair attempts on F6        1 of 3   (coordinator-executed)
    coordinator direct implementations   6
    closure-audit cycles         0 of 1   — Wave A is pack construction, not a
                                            product capability; the binding
                                            adversarial pass is Wave B's blind audit

## Held prose — measured, not projected

    skills/core/*.md  (14 skills)         776
    policy/*.md       (6 files)           275
    capability-closure/SKILL.md           560   (from 786)
    codex-worker/SKILL.md                 400   (from 486)
    ----------------------------------------
    TOTAL                               2,011   target ~2,000

**2,011 against a target the architecture audit states as "≤ ~2,000" — 0.55%
over, recorded rather than rounded.** Real cuts got it here: the Goal Activation
Gate deleted entire (~59 lines, dead); the fixed worker-escalation ladder
replaced by a routing-table reference in both operational skills; the audit
non-negotiables de-duplicated between `skills/core/audit-strategy.md` and
`policy/auditor-strategy.md`, which were stating the same rules twice — a
one-authority-per-fact violation as well as bulk; README and routing table
compressed.

I stopped there deliberately. Continuing would have meant shaving comments off
documents to reach a round number, which buys nothing and costs the reasoning
that makes a rule survive a cold read.

**Next cuts if the budget binds**, named in advance so the decision is not
improvised later: `policy/routing-policy.md` and `skills/core/delegation.md`
overlap on the three-stage routing procedure and could collapse to one authority
plus a reference; `skills/core/evidence.md` restates parts of
`skills/core/repair.md` on reproduce-before-repair.

Records of what *happened* (this file, findings, probe and acceptance results)
live in `docs/`, never `policy/`, so evidence never competes with live policy for
the held-prose budget. That rule is now written into `policy/BUDGETS.md`.

## Deliberately deferred (each with a named trigger)

- codex/local confinement re-derivation — trigger: first need to run a Codex or
  local worker under seatbelt. Default envelope until then is **output
  containment**, which is what the evidence actually supports.
- sibling-repo read denial in `confine` — trigger: decision to run two projects
  concurrently.
- evolution-loop automation — trigger: ≥2 projects' candidate volume.
- `gitread` argparse CLI — trigger: a second consumer needing it. It is a layer,
  not a listed tool.
