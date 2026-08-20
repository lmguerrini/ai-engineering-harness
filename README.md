# Runtime Pack 2.2.0

A coordinator-governance layer for AI-delegated engineering: durable structured
context, Skills, and a small stateless toolbelt — no deterministic software
authority. Successor to a Kernel architecture whose stateful authority failed
every audit round while its stateless checkers survived every one
(`DECISIONS.md` D1).

## Release identity

| | |
|---|---|
| Version | **2.2.0** — `VERSION` is the single machine-readable authority |
| State | **IN_PROGRESS** (`PACK_MANIFEST.json` `state`) — an evolution candidate, not adoptable |
| Gate record | `docs/RP2.2-GATE.md` |
| Identity | version **+** full 40-character revision **+** manifest tree digest. All three, or the pin does not discriminate |

Verify a checkout — run it, do not read it:

```bash
python3 tools/pack_pin.py . --version 2.2.0 --sha <full 40-char revision> \
    --digest <PACK_MANIFEST.json tree_digest_sha256> --state IN_PROGRESS
```

`--state` is the state this checkout actually declares, and it is currently
`IN_PROGRESS`. **A project may only adopt `QUALIFIED_AND_FROZEN`**, so this
release is not adoptable yet; the command a consumer will run names that state
instead, and passing it against this checkout fails — correctly.

Use the `pack_pin.py` **inside the release being verified**: the digest framing
is release-local and named in the manifest's `digest_algorithm`, so a
cross-release mismatch fails as a version mismatch rather than as tampering.

A project records all three fields in `PROJECT.yaml` `pack:`
(`templates/PROJECT.yaml.template`). **A frozen release never mutates during a
project run** — verification failing mid-project means the checkout changed, and
that is a stop, not a pin to refresh. Several projects may pin the same release
concurrently, or different qualified releases, provided each version resolves to
its own immutable root. Operational state and Evolution Candidate inboxes stay
project-local; no project run evolves the pack it is pinned to.

**Version bumps** (`DECISIONS.md` D11):

- **PATCH** — backward-compatible fixes, metadata and documentation
  corrections, and enforcement of guarantees the pack already promised.
- **MINOR** — a new backward-compatible policy, tool or capability.
- **MAJOR** — an incompatible authority, contract or migration change.

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
- **Installed skills** (`~/.claude/skills/`): **adapters, not authority.** They
  sit outside this release, are covered by no digest, and can change under a
  running project. Where an adapter and the pinned pack disagree, the pinned
  pack wins; an external skill that must be normative is pinned and verified
  under its own dependency contract.

## Repository

Derived from the tracked tree, not maintained by hand
(`templates/repository-layout.template.md`).

    runtime-pack-2/
    ├── VERSION                     the single machine-readable version authority
    ├── PACK_MANIFEST.json          release identity: state, digest, test count, gate
    ├── CHANGELOG.md                per-version record, including errata
    ├── DECISIONS.md                pack-level decisions D1–D19, append-only
    ├── skills/core/                13 public-safe skills, roles only, no vendor names
    ├── policy/                     private operational policy
    │   ├── observations.jsonl      append-only routing evidence — the record
    │   ├── routing-table.md        derived view, regenerated from it, never patched
    │   ├── auditor-strategy.md     audit depth and capacity economics
    │   ├── execution-boundaries.md what a harness is, and what it is not
    │   ├── routing-policy.md       role → configuration
    │   ├── hitl-matrix.md          the 17-row blocking taxonomy
    │   ├── BUDGETS.md              frozen counters and bureaucracy budgets
    │   └── private-terms.default.json
    ├── templates/                  pull-on-demand, project-instantiated
    │   ├── PROJECT.yaml.template   the project contract, including the pack pin
    │   ├── RELEASE_INDEX.json.template  the index, which lives outside every release
    │   ├── audit-brief.template.md
    │   ├── task-brief.template.md
    │   └── …                       scope, progress, findings, handoff, coverage
    ├── tools/                      stateless checkers, stdlib + siblings only
    │   ├── gitread.py              read-only Git layer, carries no write verb
    │   ├── publication_gate.py     ref namespace + push form + remote postcondition
    │   ├── pack_pin.py             verifies this release against its own manifest
    │   ├── outgoing_scan.py        leak scan over history, staged content and refs
    │   ├── commit_gate.py          one message, or a whole range
    │   └── tests/                  the suite; `python3 -m pytest tools/tests/ -q`
    └── docs/                       what happened: gate records, findings, probes
        ├── RP2.1.1-GATE.md         the previous release's gate
        ├── RP2.2-GATE.md           this release's gate
        ├── RP2.1-GATE.md           prior releases, left as written
        └── acceptance/             drills and injection results

## The stop rule

This pack exists to **start real project work**, not to be the project. If pack
construction is still ongoing with no real project started after its
pre-committed budget, that is a mandatory human escalation recommending ship
as-is. A pack deficiency found mid-project is recorded as a candidate and
worked around with judgement; the project is never stopped to perfect the pack.
