# Runtime Pack 2.1 — read-only delta audit

**Date:** 2026-08-15. **Starting state:** VERSION `2.0.0`, HEAD `0ec6726`, working
tree clean, `tools/tests/` **98 passed** re-executed before this audit began.

**Input:** the 32 evolution candidates recorded during the completed Pilot Run
Project (EC-A…EC-AF).

**Method.** Every candidate was re-verified against pack source at `0ec6726`
rather than accepted on its own description. A candidate claiming a defect that
the pack does not actually have would otherwise buy a change that closes nothing.
Line references below are the verification, not the candidate's citation.

---

## Disposition

| id | severity | disposition | verified against |
|---|---|---|---|
| EC-A | low | IMPLEMENT_NOW | `PROJECT.yaml.template` — no execution-profile stub for the project's type |
| EC-B | low | IMPLEMENT_NOW | `PROJECT.yaml.template` — no `data_provenance` |
| EC-C | low | IMPLEMENT_NOW | `SCOPE.md.template` — binary-predicate acceptance only |
| EC-D | low | IMPLEMENT_NOW | bootstrap:18 cites `policy/wave-b-gate.md`; real file `docs/WAVE-B-GATE.md` |
| EC-E | low | IMPLEMENT_NOW | no template for `REQUIREMENTS.md`, `DECISIONS.md`, `EVOLUTION_CANDIDATES.md` |
| EC-F | medium | IMPLEMENT_NOW | bootstrap:55 shows 7 columns; `validate_requirement_coverage.py:29` enforces 8 |
| EC-G | medium | IMPLEMENT_NOW (policy) | no review point on a `content_exempt` declaration |
| **EC-H** | **high** | **IMPLEMENT_NOW** | `outgoing_scan.py:324` — `--term` replaces; fallback is `NO_PRIVATE_TERMS` |
| EC-I | high | IMPLEMENT_NOW | `private-terms.default.json` ships `\b[A-Z]{2,4}-\d{1,4}\b` |
| EC-J | high | IMPLEMENT_NOW | `workspace_report.py` — no `must_be_tracked` concept |
| **EC-K** | **high** | **IMPLEMENT_NOW** | `outgoing_scan.py:294` `_matches_exempt` uses `fnmatch`; template documents gitignore |
| EC-L | medium | IMPLEMENT_NOW (policy) | `public-safety.md` — no pre-adoption check for declared terms |
| EC-M | high | IMPLEMENT_NOW | defaults ship bare `claude`, `terra`, `sol`, `luna`, `spark`, `opus`, `envelope`, `harness` |
| EC-N | medium | IMPLEMENT_NOW | no amend-trap rule; report does not count reachable blobs per path |
| EC-O | medium | **DEFER** | real, but narrowing the one rule that catches real leaks on one project's evidence |
| EC-P | high | IMPLEMENT_NOW | all three tools take declarations as CLI flags only |
| **EC-Q** | **high** | **IMPLEMENT_NOW (policy)** | `delegation.md` has a delegation floor, no fan-out estimate or runway check |
| EC-R | high | **SUPERSEDED** by EC-AF | namespace-blindness finding stands and is carried into EC-AF's implementation |
| EC-S | high | IMPLEMENT_NOW (policy) | `worker-contract.md` and `codex-worker` §6 require a write §7 forbids |
| EC-T | medium | **DEFER** | one instance; `skipped`/`exempted` are already distinct in the data model |
| EC-U | medium | IMPLEMENT_NOW (policy) | pack does not name `chflags` as a race |
| EC-V | low | IMPLEMENT_NOW (policy) | no absolute-`PYTHONPATH` note in execution-profile guidance |
| EC-W | high | IMPLEMENT_NOW (policy) | `routing-table.md` records `validated for read-only only` — permission as capability |
| EC-X | medium | IMPLEMENT_NOW (policy) | `capability-closure` §8.1 gives every auditor a worktree |
| EC-Y | low | IMPLEMENT_NOW (policy) | positive finding, absent from `delegation.md` |
| EC-Z | medium | **REJECT for Core** | project-specific lesson; would couple Core to one project's internal structure |
| EC-AA | high | IMPLEMENT_NOW | implemented as a scanner mode, **not** as the proposed hook |
| EC-AB | high | (with EC-AA) | same defect, same fix |
| EC-AC | high | IMPLEMENT_NOW (policy) | `oracle-discipline.md` — no dependency-edge enumeration rule |
| EC-AD | high | IMPLEMENT_NOW (policy) | no rule that provenance is reported by the executing component |
| EC-AE | medium | IMPLEMENT_NOW (policy) | no repository-layout presentation convention |
| **EC-AF** | **high** | **IMPLEMENT_NOW** | `grep -rn "for-each-ref\|refs/notes\|show-origin" tools/ skills/ policy/ templates/` → **no match** |

Plus one gap not in the candidate list, taken from the governing prompt's
lesson H and verified the same way:

| — | medium | IMPLEMENT_NOW | `commit_gate.py` validates one message; nothing validates a **range**, so format drift across a branch is undetected |

## The three that carry the delta

**EC-AF is the largest hole in the pack.** Publication safety is currently a
per-project human checklist. The pack asserts nothing about a repository's ref
namespace, reads no git config, and has no notion of a push refspec. A project
that needs one has to invent a publication checklist by hand, and no checklist
keeps up with background tooling that re-creates deleted refs within seconds
and rewrites repository configuration between sessions.

**EC-H and EC-K are the same defect class as the one that ended the Kernel**:
the oracle's *domain derivation* is wrong, not its assertions. EC-H scans with 0
of 59 rules and prints `clean`. EC-K's exemption matches nothing and the report
is byte-identical to one where it matched. Both are believed.

**EC-P is the root cause of both, and of lesson H.** Every declaration reaches
the tools as a flag a human retyped. `--project` makes the contract the single
source, which is the fix EC-H, EC-P and commit-drift all reduce to.

## Architectural test

Nothing here adds state, authority, or a component that both holds state and
adjudicates it. `publication_gate.py` is a checker that reports and refuses.
`project_contract.py` is a reader. D1–D5 are untouched and not reopened. The
delta closes empirical gaps in the approved architecture rather than changing it,
so Phase 3's HITL trigger does not fire.

**Deferred with named triggers:** EC-O (trigger: a second project blocked by the
machine-path rule where the workaround is not better engineering); EC-T (trigger:
a project shipping enough unscannable blobs that the exemption total stops being
readable); EC-Z (trigger: none — rejected for Core, recorded as project advice).
