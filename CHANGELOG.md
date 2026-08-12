# Changelog

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
