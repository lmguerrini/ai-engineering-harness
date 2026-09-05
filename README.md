# Runtime Pack 2.4.0

A coordinator-governance layer for AI-delegated engineering: durable structured
context, Skills, and a small stateless toolbelt — no deterministic software
authority. Successor to a Kernel architecture whose stateful authority failed
every audit round while its stateless checkers survived every one
(`DECISIONS.md` D1).

## Release identity

| | |
|---|---|
| Version | **2.4.0** — `VERSION` is the single machine-readable authority |
| State | **IN_PROGRESS** (`PACK_MANIFEST.json` `state`) — a candidate, not a release. **No project may pin it.** Moving it to `QUALIFIED_AND_FROZEN` is a human decision (`policy/hitl-matrix.md` row 2) and carries a row-7 authorisation as well (`docs/RP2.4-D26-PROPOSED.md`, which is where the entry is held **until** that authorisation) |
| Gate record | `docs/RP2.4-GATE.md` |
| Identity | root path **+** version **+** full 40-character revision **+** manifest tree digest. All four, or the pin does not discriminate: the root says *which directory*, the rest say *what is in it* |

Verify a checkout — run it, do not read it:

```bash
python3 tools/pack_pin.py . --version 2.4.0 --sha <full 40-char revision> \
    --digest <PACK_MANIFEST.json tree_digest_sha256> --state IN_PROGRESS
```

`--state` is the state this checkout actually declares. **A project may only
adopt `QUALIFIED_AND_FROZEN`**, and this checkout declares `IN_PROGRESS`, so the
command above verifies the checkout and the checkout is **not adoptable**.
Passing `QUALIFIED_AND_FROZEN` against it fails — correctly, and that is the
whole point of carrying the state in the pin: a candidate that verifies perfectly
is still a candidate.

Use the `pack_pin.py` **inside the release being verified**: the digest framing
is release-local and named in the manifest's `digest_algorithm`, so a
cross-release mismatch fails as a version mismatch rather than as tampering.

A project records all four pin fields — **root, version, revision and digest** — in
`PROJECT.yaml` `pack:`
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
  procedure, and **no vendor name appears there**. `policy/` — private
  operational policy, where vendor names are expected. `tools/` may name a
  vendor **only** in a module that adapts to one specific documented surface
  (`resource_observation.py` reads one client's status-line contract, and
  `backend_contract.py` quotes a real observation); the rules themselves stay
  vendor-neutral, and a backend is added by writing an observation source, not
  by editing them. `templates/` — pull-on-demand, project-instantiated. `tools/` —
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
    ├── DECISIONS.md                pack-level decisions D1–D27, append-only
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
    │   ├── RELEASE_INDEX.json.template  the release index, which lives outside every release
    │   ├── audit-brief.template.md
    │   ├── task-brief.template.md
    │   └── …                       scope, progress, findings, handoff, coverage
    ├── tools/                      stateless checkers, stdlib + siblings only
    │   ├── gitread.py              read-only Git layer, carries no write verb
    │   ├── publication_gate.py     ref namespace + push form + remote postcondition
    │   ├── pack_pin.py             verifies this release against its own manifest
    │   ├── pack_migration.py       pin class, migration gate, rollback, release index
    │   ├── adapter_pin.py          verifies the executable adapters a project declares
    │   ├── project_context.py      verifies a project's declared semantic authority
    │   ├── capability_open.py      one readiness path over all of the above, before work starts
    │   ├── backend_contract.py     backend identity and per-family qualification, now prior
    │   ├── qualification.py        per-configuration qualification, keyed on the evidence
    │   ├── model_discovery.py      what a surface offers now; no model vocabulary anywhere
    │   ├── routing.py              availability, eligibility and the design-audit route
    │   ├── selector_evidence.py    whether a targeted run is evidence that anything ran
    │   ├── resource_observation.py documented resource truth as routing evidence
    │   ├── evidence_index.py       certification bound to one exact candidate
    │   ├── close_attestation.py    which gates ran, generated from the contract's own declarations
    │   ├── outgoing_scan.py        leak scan over history, staged content and refs
    │   ├── publication_history.py  the complete reachable history, strictly, and who adjudicates it
    │   ├── commit_gate.py          one message, or a whole range
    │   ├── project_contract.py     one contract, read by every gate that enforces it
    │   ├── workspace_report.py     classifies every artifact; unknown is blocking
    │   ├── surface_diff.py         the public Python surface two revisions apart
    │   ├── pathmatch.py            one path-pattern semantics, oracled against git
    │   ├── scope_check.py          one containment rule, for every gate that asks
    │   ├── evidence_put.py         content-addressed, owner-only, write-then-verify
    │   ├── design_record.py        a design frozen before the implementation it governs
    │   ├── projection.py           one read-only view, rebuilt from disk and storing nothing
    │   ├── console.py              many projects, one page; it arranges projections and decides nothing
    │   ├── activity.py             two histories: when code changed, and what durable artifacts can date
    │   ├── confine.py              the sandbox profile a dispatched worker runs under
    │   ├── continuation.py         coordinator state derived from artifacts, so silence has a name
    │   ├── progress.py             a disjunction over signals, so a quiet worker is not a dead one
    │   ├── capacity.py             a refusal before a dispatch; never a queue that dispatches
    │   ├── history_anchor.py       whether anything still keeps a cited commit reachable
    │   ├── task_output.py          bounded durable output, and the four answers before a retry
    │   ├── instrument.py           what a checker must say about itself to be believed
    │   ├── errors.py               the refusal hierarchy; every refusal names its cause
    │   └── tests/                  the suite; `python3 -m pytest tools/tests/ -q`
    └── docs/                       what happened: gate records, findings, probes
        ├── RP2.3-GATE.md           this release's gate
        ├── RP2.3-ARCHITECTURE.md   what the layering picture gains, and why it is not an authority
        ├── RP2.3-CAPABILITY-MAP.md the plan, and every reproduction behind it
        ├── RP2.3-RELEASE-PACKET.md what a returning release authority reads first
        ├── RP2.3-FAILURE-MODE-CLOSURE.md every verified failure mechanism, and its disposition
        ├── ROUTING-TABLE-HISTORY.md two grades that were wrong, moved out of policy
        ├── RESOURCE-OBSERVATION-SETUP.md the opt-in procedure, pulled on demand
        ├── RP2.2-GATE.md           the previous release's gate
        ├── RP2.2-ARCHITECTURE.md   the authority layers, and what is not one
        ├── RP2.2-RELEASE-PACKET.md what a returning release authority read first
        ├── …                       prior gate records, left as written
        └── acceptance/             drills and injection results

## The stop rule

This pack exists to **start real project work**, not to be the project. If pack
construction is still ongoing with no real project started after its
pre-committed budget, that is a mandatory human escalation recommending ship
as-is. A pack deficiency found mid-project is recorded as a candidate and
worked around with judgement; the project is never stopped to perfect the pack.
