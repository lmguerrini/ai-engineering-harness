# RP2.2 — founder release packet

**Status: `READY_FOR_FOUNDER_RELEASE`** as a candidate. The manifest declares
`IN_PROGRESS`, which is the closest state the existing model permits: `pack_pin`
knows two states, and `QUALIFIED_AND_FROZEN` is the one a project may adopt.
Moving it there is a human act and was not performed.

## What to check first

```bash
git -C <pack_root> checkout evolution/rp2.2
python3 tools/pack_pin.py . --version 2.2.0 --sha "$(git rev-parse HEAD)" \
    --digest "$(python3 -c 'import json;print(json.load(open("PACK_MANIFEST.json"))["tree_digest_sha256"])')" \
    --state IN_PROGRESS
python3 -m pytest tools/tests/ -q
```

The revision is read from the branch rather than printed here, for the reason
`PACK_MANIFEST.json` gives about its own: **a document cannot name the commit
that contains it.** Writing a revision into this file would name the commit
before this one, and be wrong from the moment it was committed.

## Candidate identity

| | |
|---|---|
| Branch | `evolution/rp2.2`, cut from the frozen baseline, linear, never pushed |
| Baseline | `4495e61850c08027e47eac6d0db84b4b3380e300` (2.1.1), **not rewritten** |
| Candidate HEAD | the tip of `evolution/rp2.2`; read it with `git rev-parse` |
| Version | `2.2.0` — MINOR under D11 |
| State | `IN_PROGRESS` |
| Tree digest | `PACK_MANIFEST.json` `tree_digest_sha256`; verified, not copied |
| Tracked files | `PACK_MANIFEST.json` `tracked_files` |

No push, no tag, no remote, no publication. The repository has no remote
configured and none was added.

## What this release is for

The pack now checks four things it previously asserted and could not check: the
**adapters** it dispatches through, the **release** a project is pinned to and
how it moves between releases, the **semantic authority** a project runs
against, and the **capacity** a routing decision assumes. Plus eleven reproduced
defects in the machinery that was already there — one of which was a real leak.

## The finding that most deserves a decision

**A release root and a working tree cannot be the same directory** (D18). The
Consumer-A project pins `root_path` to this repository, and its pin — correctly
formed, every field present — stopped verifying the moment this evolution branch
was checked out here. The verifier caught it precisely. The layout is what is
wrong.

The candidate ships the mechanism (`tools/pack_migration.py`, a release index
outside every release, `RELEASE_INDEX.json.template`). **Placing releases at
their own roots is an operational change affecting a live project, so it was not
performed.** Nothing was migrated and no project file was touched.

## What was left alone deliberately

- **No project was migrated or modified.** `consumer-d` and
  `fixture-tally` still carry version-only pins, which classify as
  `UNVERIFIABLE_LEGACY_PIN`. They are evidence, not authorisation.
- **No adapter was vendored.** Pinning was proved sufficient (D12, D14).
- **No dependency was added.** D3 holds: 0 violations across 19 modules.
- **No new stateful runtime**, daemon, scheduler or registry.
- **Global configuration was not modified to obtain telemetry.** The status-line
  adapter is opt-in and reversible; no `statusLine` was installed.

## Two adapters were repaired, outside the release envelope

`~/.claude/agents/capability-auditor.md` (isolation mode removed) and
`~/.claude/skills/codex-worker/SKILL.md` (its reads of undocumented Codex
internals now carry the four required rules). Digests are in the gate record so
they can be pinned. Originals are retained in this session's scratch directory.

**Both take effect at the next session, not this one** — see RP-EC-6, which was
reproduced live when two auditors dispatched after the repair still received
worktrees.

## Deferred, each with its trigger

In `docs/RP2.2-GATE.md`: baseline maturity phase, audit-cycle accounting as
Core code, delta-scoped requalification driven from SHAs, and vendoring any
adapter. None is a blocker for a project adopting this release.

## Known limitations

- **Held prose is 22.7% over the ~2,000-line target** (2.1.1 was 14.9% over).
  Recorded rather than shaved; one principled reduction was made.
- **Both closure auditors were same-family.** The final-gate tier requires two
  blind auditors, "one cross-vendor **where available**"
  (`policy/auditor-strategy.md`). Two blind auditors ran, on distinct lenses,
  each on its own coordinator-prepared snapshot. Cross-vendor was **not**
  available: the session's routing direction was that the Codex general pool is
  constrained and should not be used. So the tier is satisfied as written,
  and the more valuable half of it — the measured finding that the two auditor
  populations are *almost disjoint* rather than redundant — was not obtained.
  Recorded as a real reduction in coverage rather than as a met requirement.
- The routing evidence base is still the same recorded observations. Nothing was
  invented, and unprobed configurations stay unprobed.

## Where the detail is

| | |
|---|---|
| Gate record, per capability, with every reproduction | `docs/RP2.2-GATE.md` |
| Capability map and dependency order | `docs/RP2.2-CAPABILITY-MAP.md` |
| Architecture decision layer | `DECISIONS.md` D14–D19, `docs/RP2.2-ARCHITECTURE.md` |
| What changed, in release terms | `CHANGELOG.md` |
