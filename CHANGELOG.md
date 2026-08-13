# Changelog

## 2.0.0 — Wave A + Wave B complete, ready for a real project

Wave A built the pack; Wave B proved it by taking a disposable fixture project
end to end. Both gates are recorded in `docs/WAVE-A-GATE.md` and
`docs/WAVE-B-GATE.md`.

- `tools/` — eight stateless, non-authoritative checkers plus a read-only Git
  layer, 98 standalone tests, importing nothing outside `tools/`. `gitread.py`
  is a 272-line read-only subset of a 1,455-line module and carries no Git write
  verb (`DECISIONS.md` D2).
- Seven findings in Wave A (F1–F7), eight in Wave B (C1–C8), **all reproduced by
  coordinator execution and all closed**. None was caught by an implementing
  worker's own passing suite.
- The rehearsal's two most valuable findings were **test-domain** defects: two
  independently written obviously-wrong implementations each passed a fully green
  suite. Neither was reachable by mutating production code.
- Wave B ran a real cold-continuation drill (passed from 4 file reads), a
  deliberate leak injection (blocked at both gates), a failure-classification
  exercise (environmental, budget correctly not charged), and **two blind
  audits** whose unique-discovery counts are recorded rather than pooled.

Not in this version, deliberately: no database, event store, reducer, lifecycle
engine, release-identity authority, or trust root; no automated Core evolution;
no Pilot Run Project. The pack exists to start real work, not to be the work.

## 2.0.0-wave-a — pack skeleton, Core Skills, policy, templates

Runtime Pack 2.0 is the successor to a deterministic-kernel architecture that
was terminally abandoned after four audit rounds found stateful software
authority failing every round while small stateless checkers survived every
one (see `DECISIONS.md` D1). This wave builds the pack itself: no project has
started yet.

**What this pack is:** a coordinator-governance layer expressed in durable
structured context (files + Git), Skills (procedure), and a small toolbelt of
stateless, non-authoritative checkers. Authority lives in files a coordinator
maintains under this governance and in Git; nothing here holds state and
adjudicates it in the same component.

**What this wave adds:**

- `skills/core/` — the ten Core skills carried from the prior Kernel project's
  seed corpus, reconciled against the architecture audit (kernel-authority
  references replaced with this pack's file-and-toolbelt architecture), plus
  three new skills: `oracle-discipline.md`, `continuation.md`,
  `worker-contract.md`. All model-agnostic, role names only.
- `policy/` — private operational policy: `observations.jsonl` (seeded
  honestly with the 8-configuration worker-ladder outcomes), `routing-table.md`
  (a derived view, regenerated, never hand-edited), `hitl-matrix.md` (the
  17-row blocking taxonomy with a named application point per row),
  `auditor-strategy.md` and `routing-policy.md` (absorbed and reconciled to the
  owner-approved defaults), `private-terms.default.json` (carried).
- `templates/` — pull-on-demand, project-instantiated artifacts: the project
  contract, capability scope/progress/findings, task and audit briefs, HITL
  decisions, product bugs, evidence index, the nine-field human acceptance
  protocol, and the requirement-coverage register with its tiny stdlib-only
  validator.

**What this wave deliberately does not contain:**

- No database, event store, reducer, lifecycle engine, release-identity
  authority, or trust root. State lives in files and Git, not software.
- No toolbelt code — that is a separate, parallel Wave-A stream (`tools/`),
  owned and delivered independently of this one.
- No real project. `PROJECT.yaml` has not been authored for anything yet;
  Wave C is the point at which a project actually starts.
- No vendor or model names in `skills/core/` — those live only in `policy/`.
