# RP2.2 — founder release packet

**The manifest declares `IN_PROGRESS`**, which is the closest state the existing
model permits: `pack_pin` knows two, and `QUALIFIED_AND_FROZEN` is the one a
project may adopt. Moving it there is a human act and was not performed.

**Read this before deciding.** Three closure-audit rounds ran — six blind
auditors on distinct lenses — and **every round returned NOT READY**. Every
finding was reproduced by the coordinator and repaired, and the next round then
found more, including in the repairs themselves. Round 1's repair **regressed
the commit gate against the qualified 2.1.1 baseline**, which two independent
auditors caught. `docs/RP2.2-GATE.md` records each round, what was right, and
what the coordinator got wrong.

That history is the most decision-relevant thing about this candidate, and it
cuts both ways: the code was hard to break — one auditor ran 143,820 pattern
comparisons against `git check-ignore` and another 111,267, both finding zero
divergences; injected mutations reverting every claimed repair were killed every
time — while the release's **account of itself** failed repeatedly, and had to
be repaired by binding numbers to measurements rather than by retyping them.

**No round has yet returned READY.** The final round's findings are closed and
the suite is green, but no auditor has seen the result of closing them.

## What to check first

```bash
# Verify the candidate WITHOUT checking it out in a root a project pins (D18):
git clone --local --no-hardlinks --branch evolution/rp2.2 <pack_root> <scratch_dir>
cd <scratch_dir>
python3 tools/pack_pin.py . --version 2.2.0 --sha "$(git rev-parse HEAD)" \
    --digest "$(python3 -c 'import json;print(json.load(open("PACK_MANIFEST.json"))["tree_digest_sha256"])')" \
    --state IN_PROGRESS
python3 -m pytest tools/tests/ -q
```

**The clone is the point, not a convenience.** `<pack_root>` is the directory
Consumer-A pins, and checking this branch out there is exactly what broke its
pin — the finding below, and D18. A release is verified at a root nobody works
in; a clone is how you get one without disturbing the pinned tree. Everything in
the block resolves against `<scratch_dir>`, which is why the `cd` is there.

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
against, and the **capacity** a routing decision assumes. Plus **ten** reproduced defects in the machinery that was already there — one of
them a real leak — and one enforcement added where no drift existed. The gate
record's C3 table has eleven rows and says so of the eleventh.

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
they can be pinned. **The pre-repair originals are not retained anywhere durable** — they were held in an ephemeral session directory. Their content is recoverable only from the description in the gate record, which is a real gap in the evidence for C2 and is stated here rather than left to be discovered.

**Both take effect at the next session, not this one** — see RP-EC-6, which was
reproduced live when two auditors dispatched after the repair still received
worktrees.

## Deferred, each with its trigger

In `docs/RP2.2-GATE.md`: baseline maturity phase, audit-cycle accounting as
Core code, delta-scoped requalification driven from SHAs, and vendoring any
adapter. None is a blocker for a project adopting this release.

## Known limitations

- **No audit round has returned READY.** Three rounds each returned NOT READY;
  the last round's findings are repaired and unaudited. A fourth round is the
  obvious next step and was not run before handing this over.
- **Round 1's repair regressed the commit gate** against 2.1.1 (a trailer
  escaping behind whitespace or a second prefix). Repaired, and now pinned by a
  differential against the frozen baseline — but it happened, and it happened in
  a repair.
- **Held prose is over the ~2,000-line target** — the figure is in
  `PACK_MANIFEST.json` `known_limitations` and `docs/RP2.2-GATE.md`, measured
  and bound by test. 2.1.1 was 14.9% over on the same rule.
- **Both halves of that figure are not equally checkable.** The in-release lines
  are measured by a test; the installed-adapter lines are outside the release and
  cannot be verified from it.
- **Several claims are unfalsifiable from the repository**, and are marked as
  such in the gate record: the four adapter digests and the two adapter repairs
  (outside the envelope), the Project Context file count (in another project),
  and the status-line payload schema (read from the installed client's own
  documentation, with no artifact shipped). `resource_observation.py` has been
  exercised against constructed payloads and **never against a live one**.
- **Cross-vendor audit was not available** in any round. The tier asks for two
  blind auditors with one cross-vendor *where available*; two ran each round, and
  the measured value of the tier — that the two populations come back almost
  disjoint — was obtained within one family instead. Recorded as a real
  reduction in coverage.
- **The tree digest is over working-tree bytes.** A checkout with
  `core.autocrlf=true` produces a different digest for the same commit. There is
  no `.gitattributes`.
- The routing evidence base is still the recorded observations plus this
  session's. Nothing was invented, and unprobed configurations stay unprobed.

## Where the detail is

| | |
|---|---|
| Gate record, per capability, with every reproduction | `docs/RP2.2-GATE.md` |
| Capability map and dependency order | `docs/RP2.2-CAPABILITY-MAP.md` |
| Architecture decision layer | `DECISIONS.md` D14–D19, `docs/RP2.2-ARCHITECTURE.md` |
| What changed, in release terms | `CHANGELOG.md` |
