# Release notes — Runtime Pack 2.0.0 → 2.5.0, and 2.6.0 in development

Runtime Pack is the versioned core of the AI Engineering Harness (`ai-engineering-harness`).

A concise, public summary of each version. The complete per-version record, including errata and the raw results
each release preserved, is `CHANGELOG.md`; each version's gate record in `docs/` holds its qualification evidence.

**Status vocabulary.** `QUALIFIED_AND_FROZEN` — qualified by its gate and frozen by a recorded human decision;
a project may pin it, and it never changes again. `superseded` — an earlier release replaced by a later one and not
recorded as qualified and frozen. `IN_PROGRESS` — a candidate or development line; no project may pin it.
Public commits are the commits of *this* repository (see the public-edition note on identities).

| Version | Released | State | Test population | Public commit |
|---|---|---|---|---|
| 2.0.0 | 2026-08-13 | superseded | 98 | `afd8fd546d25` |
| 2.1.0 | 2026-08-15 | superseded | 175 | `1991a1431e5d` |
| 2.1.1 | 2026-08-15 | QUALIFIED_AND_FROZEN | 237 | `271d10ee393a` |
| 2.2.0 | 2026-08-21 | QUALIFIED_AND_FROZEN | 765 | `9b883f964bf7` |
| 2.3.0 | 2026-09-05 | QUALIFIED_AND_FROZEN | 2,036 | `e96fc4e9ce01` |
| 2.4.0 | 2026-09-05 | QUALIFIED_AND_FROZEN | 2,626 | `a0c8d9bc7a48` |
| 2.4.1 | — | never released (`IN_PROGRESS`) | 2,863 | `262ed9f9392b` |
| **2.5.0** | **2026-09-10** | **QUALIFIED_AND_FROZEN — current stable** | **3,011** | `c2fcf9cedf17` |
| 2.6.0 | — | `IN_PROGRESS` — development, paused at a checkpoint; not qualified | 3,319 at the checkpoint (0 failing, 2 skipped) | `b7f85623ebe7` |

---

## 2.5.0 — the boundary stops describing Git and starts constructing the repository  *(current stable)*

**Capabilities.** Every governed local Git read now runs against a *constructed* git directory (`tools/sterile.py`):
a blank configuration, the subject's objects attached, refs/HEAD/index copied, so no file the inspected repository
wrote is ever read as configuration. Child-process creation is denied by a generated sandbox profile and its absence
is verified from Git's Trace2 output (`gitread`); populated submodules are composed above that boundary
(`tools/submodule_no_child.py`). Each capability gets the execution policy its semantics need.
**Architecture.** Replaces the 2.4-era approach of *inspecting* a repository's configuration and refusing dangerous
keys one by one — an enumeration that independent readings kept finding new holes in — with construction plus denial.
Eight design generations were frozen before implementation and read blind by independent readers; five of them
(A3–A7) were falsified and stay in the history as records, while A1, A2 and the capability-scoped A7.1 ship.
**Verification.** 3,011 tests; a frozen-floor differential over 49 fixture repositories × 200 read forms against
2.4.0; a hostile-repository matrix; a sixteen-mutant mutation script; two independent certifications that ended ready.
**Compatibility.** MINOR. Signature-compatible, but some answers change (stated under *What a consumer will notice* in
the changelog): the version bump is derived from both the API surface and the answer contract (D28). One read
(`verify-pack`, which spawns an indexer) is now refused explicitly.
**Known limitations.** macOS Seatbelt is required for governed local reads; elsewhere they are refused. Remaining
items are recorded in the manifest's `known_limitations`.

## 2.4.1 — the six the full-release audit reproduced  *(never released)*

A PATCH line repairing six defects a full-release audit reproduced in 2.4.0's Git read authority (nested-repository
configuration, configuration scope, conditional closures, transport re-enabling, reach by observation). Successive
certifications kept finding defects *inside the repairs*; the line reached a convergence blocker and was superseded by
2.5.0's architectural change rather than released. It is kept in history as evolution evidence. 2.4.0 stayed the
release projects pinned throughout.

## 2.4.0 — qualification belongs to a configuration, not to a family

**Capabilities.** Per-configuration qualification over a nine-dimension identity (`tools/qualification.py`);
dynamic model discovery read through field names, never model names (`tools/model_discovery.py`); routing with a
reason per rejection and availability as a separate axis (`tools/routing.py`); one governed waiting path with a single
liveness answer (`continuation`, `progress`).
**Why.** Reproduced first: a model with zero observations of its own was reported qualified for cross-vendor audit on
the strength of seven observations that recorded no observed model at all.
**Verification.** 2,626 tests; the design was falsified by two independent readers before implementation; a run that
executed nothing is no longer accepted as evidence.
**Compatibility.** MINOR; new optional contract key, nothing removed.

## 2.3.0 — durable execution, liveness, capacity truth and complete-history safety

**Capabilities.** Waits with declared deadlines and disk-derived waiting state, so a finished job cannot stay unnoticed
(`continuation`); liveness as a disjunction of signals, telling a quiet worker from a dead one (`progress`); capacity
refusal before dispatch (`capacity`); bounded durable task output (`task_output`); per-dispatch sandbox profiles
(`confine`); complete-history publication scanning at the strict tier (`publication_history`); reachability of cited
commits (`history_anchor`); a read-only projection and multi-project console (`projection`, `console`, `activity`);
frozen designs before material change (`design_record`, D25).
**Why.** The release reproduced, live, the failure class it was closing: a dispatched audit held the coordinator for
hours on a process that had stopped working.
**Verification.** 2,036 tests; every defect reproduced against frozen 2.2.0 before repair, each repair carrying an
oracle that fails on the old behaviour; repeated blind review rounds, each recorded with what it found;
a mutation pass over the new guards.

## 2.2.0 — adapter integrity, tooling integrity, and truth about execution

**Capabilities.** Executable adapters verified by digest and by the program they drive (`adapter_pin`); a backend
identity contract and documented resource readings (`backend_contract`, `resource_observation`); migration and
rollback between qualified releases (`pack_migration`); verification of a project's declared semantic authority
(`project_context`); certification bound to an exact candidate (`evidence_index`); one composed readiness check
(`capability_open`).
**Verification.** 765 tests; every defect reproduced against frozen 2.1.1 before repair; representative consumer
shapes exercised end to end; the release's surfaces checked against a qualified baseline.

## 2.1.1 — release integrity: the checks now mean what they said

A PATCH release after an independent cross-vendor audit found that release checks verified less than they printed —
for example a one-character revision passed the pin because the comparison was a prefix match, and the tree digest
concatenated paths and contents without framing. Release identity became *version + revision + digest + state*.
237 tests (from 175), each repaired guarantee with a falsification test.

## 2.1.0 — evidence consolidation from the first completed project

The first evolution pass driven by a finished real project rather than a fixture: 32 recorded candidates re-verified
against source before adoption. Publication became a ref-namespace contract; the project contract became the single
source for every gate; the private vocabulary became tiered by surface after a flat list produced 102 findings and
zero true positives on real content.

## 2.0.0 — hybrid architecture, ready for a real project

The pack itself: eight stateless checkers and a read-only Git layer importing nothing outside the toolbelt, core
skills, policy tables and templates. Built after the predecessor's stateful authority failed every audit round while
its stateless checkers survived. A disposable fixture project was taken end to end; every finding was reproduced by
execution and closed.

---

## 2.6.0 — a provider is a declared record, billing is a proof, and capacity says how fresh it is  *(IN_PROGRESS — not a release)*

**State.** Opened on 2026-09-19 from the 2.5.0 release commit and paused at a checkpoint on 2026-09-20 (branch
`main`, public commit `b7f85623ebe7`). Not qualified, not frozen and not adoptable: its manifest says
`IN_PROGRESS`, its gate record lists what is not yet done, and no freeze decision exists. Every figure below describes
the checkpoint, not a release.
**Why.** The cross-vendor audit leg depended on one configuration drawing on one shared account-level pool, every
failover was a human decision, cross-pool routing was being re-implemented outside the pack, and projects had extended
the capacity record with fields the frozen reader refused (D29–D36).
**Landed so far.** A provider is one declared, validated manifest with no slots and no count
(`tools/provider_manifest.py`); a billing-route fingerprint under which anything not proven subscription or local is
`NOT_ROUTABLE`, and a metered route stays denied whatever credentials the environment holds; cross-vendor
independence computed on the model vendor rather than the gateway, and a vendor-independent eligibility report that
lists and explains but neither dispatches nor ranks (`tools/routing.py --eligibility`); provider-quota and human
capacity readings whose freshness is judged at read time, and the single validated writer of the capacity record
(`tools/resource_observation.py`, `tools/capacity.py`, `tools/capacity_record.py`); a read-only-mode oracle over every
touched tool; a dormant, unauthorised provider template that proves a new vendor registers without routing anything.
**Not landed.** Of the design's thirteen frozen oracles, three have no implementation yet (quarantine for evidence
rows and waits, bounded gate waits with a `PAUSED` state, the overview panel) and a fourth only in part (the
cost-policy check before capacity arithmetic). No closure audit, cross-vendor certification or freeze has taken place.
**Verification at the checkpoint.** Tests: 3,317 of 3,319 pytest tests pass on macOS with Python 3.14.0 and Git 2.50.1, and 2 are skipped by the line's own conditions because they check records the line has not produced yet; passing tests do not qualify a development line. The line's commit range conforms to the pack's commit
contract; its version grade is to be derived at a freeze that has not happened (expected MINOR).

## Planned

From the evolution candidates recorded in `PACK_MANIFEST.json`, each with the observation that would trigger it: a
durable event log, a multi-year activity calendar, a measured relative yield between same-family and cross-vendor
audits, an execution-trace oracle shipped as a tool, and a read-only way to enumerate a bundle's objects. None is a
commitment.
