# Runtime Pack 2.0

A coordinator-governance layer for AI-delegated engineering: durable structured
context, Skills, and a small stateless toolbelt — no deterministic software
authority. Successor to a Kernel architecture whose stateful authority failed
every audit round while its stateless checkers survived every one
(`DECISIONS.md` D1).

## Layers

    Coordinator (frontier model, judgement)  — decomposition, routing, diagnosis,
                                                 synthesis, all Git writes
    Skills (procedure)                       — skills/core (public-safe, roles
                                                 only) + project skills
    Durable context (files)                  — project contract, progress,
                                                 decisions, findings, handoff
    Toolbelt (stateless checkers)            — tools/: report and refuse, never
                                                 hold or adjudicate state
    Workers (stateless, replaceable)         — brief in, patch + report out;
                                                 reports are claims until re-run

## Where each authority lives

- **This pack** (`~/.../runtime-pack-2/`): `skills/core/` — public-safe
  procedure. `policy/` — private operational policy, vendor names allowed only
  here. `templates/` — pull-on-demand, project-instantiated. `tools/` —
  stateless checkers, import-closed. None of these hold project state.
- **Per-project private root**: `PROJECT.yaml`, `HANDOFF.md`, `ROADMAP.md`,
  `DECISIONS.md`, and each capability's `SCOPE.md`/`PROGRESS.md`/`FINDINGS.md`
  are the actual record — authoritative, never duplicated elsewhere.
- **The project repository**: ordinary engineering artifacts only. Nothing
  orchestration-flavored ever enters it.

## The stop rule

This pack exists to **start real project work**, not to be the project. If pack
construction is still ongoing with no real project started after its
pre-committed budget, that is a mandatory human escalation recommending ship
as-is. A pack deficiency found mid-project is recorded as a candidate and
worked around with judgement; the project is never stopped to perfect the pack.
