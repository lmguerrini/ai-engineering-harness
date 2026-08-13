# Wave A — gate record

**Date:** 2026-08-13. **Pack VERSION:** 2.0.0-wave-a. **Assessed by:** COORDINATOR,
by execution. Worker reports were re-executed before they counted.

Wave B does not begin until every row below is green.

| # | Gate condition | Result | Evidence |
|---|---|---|---|
| 1 | Every tool standalone | GREEN | all 7 toolbelt tools run `--help` and execute from an unrelated cwd (`/tmp`). `gitread` is the Git-read *layer*, not a listed tool; it has a usage line, not argparse. |
| 2 | All tests green | GREEN | `python3 -m pytest tools/tests/ -q` → **91 passed**, coordinator-re-executed |
| 3 | Tool imports contained | GREEN | own AST check: every `tools/*.py` imports only stdlib + `tools/` siblings. **VIOLATIONS: none.** No `hx`, no `sitecustomize`, no relative imports |
| 4 | No stateful authority reintroduced | GREEN | no sqlite/event-store/reducer/lifecycle/trust-root in `tools/`; only match was a docstring naming history. No tool writes outside a caller-supplied path except `evidence_put`, whose destination is an explicit argument |
| 5 | No Git write verbs in the read layer | GREEN | every `gitread` verb is `cat-file` / `rev-list` / `ls-tree` / `diff` / `status`. `"commit"` and `"tag"` occur only as `cat-file` object types |
| 6 | Held prose within budget | GREEN | see count below |
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

**Zero open material findings.**

Two of the three were found by executing the artifacts adversarially, not by
reading them, and neither was caught by the implementing worker's own suite.
That is the audit's central claim reproduced on the pack itself: **green is "no
known defect", never "no defect."**

## Budgets consumed

    repair attempts on F1        1 of 3
    repair attempts on F2        1 of 3   (coordinator-executed)
    repair attempts on F3        1 of 3   (coordinator-executed)
    coordinator direct implementations   3  (F2 repair, F3 repair, oracle-discipline.md)
    closure-audit cycles         0 of 1   — Wave A is pack construction, not a
                                            product capability; the binding
                                            adversarial pass is Wave B's blind audit

## Held prose

    skills/core/*.md                     753
    policy/*.md                          291
    capability-closure/SKILL.md          560
    codex-worker/SKILL.md                396
    ---------------------------------------
    TOTAL                              2,000   ceiling 2,000

## Deliberately deferred (each with a named trigger)

- codex/local confinement re-derivation — trigger: first need to run a Codex or
  local worker under seatbelt. Default envelope until then is **output
  containment**, which is what the evidence actually supports.
- sibling-repo read denial in `confine` — trigger: decision to run two projects
  concurrently.
- evolution-loop automation — trigger: ≥2 projects' candidate volume.
- `gitread` argparse CLI — trigger: a second consumer needing it. It is a layer,
  not a listed tool.
