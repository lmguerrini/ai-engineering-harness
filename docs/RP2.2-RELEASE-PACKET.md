# RP2.2 — founder release packet

**The manifest declares `IN_PROGRESS`**, which is the closest state the existing
model permits: `pack_pin` knows two, and `QUALIFIED_AND_FROZEN` is the one a
project may adopt. Moving it there is a human act and was not performed.

**Read this before deciding.** Four closure-audit rounds ran — eight blind
auditors on distinct lenses — and **every round returned NOT READY**. Every
*material* finding was reproduced by the coordinator before it counted, and
repaired; a few were artefacts of auditing a moving branch, and the gate record
says which. Each round then found more, including in the repairs
themselves — repairs **regressed the commit gate against the qualified 2.1.1
baseline** five separate times, in five distinct classes, each caught by an
audit or by an adversarial probe written after one. `docs/RP2.2-GATE.md` records
each round, what was right, and what the coordinator got wrong.

That history is the most decision-relevant thing about this candidate, and it
cuts both ways.

**The code was hard to break.** Auditors ran large differentials against real
`git check-ignore` — one on a grid this release does not ship — and found zero
divergences; the previously qualified suite passes against this implementation
with no behavioural regression; no public name was removed and no signature
changed.

**The tests were not always hard to break.** Round 1 left three injected
mutations alive, each a real unpinned branch, and round 4 found four repairs
from round 3 that could be reverted with the suite still green. Rounds 2 and 3
killed every mutation thrown at them. Each gap was closed by pinning the
guarantee absolutely rather than against the previous release — a differential
cannot see a hole the previous release also had.

**The release's account of itself failed repeatedly**, and had to be repaired by
binding numbers to measurements rather than by retyping them. The divergence
figure alone was restated wrongly three times, in the document that narrates the
first two.

**No round has yet returned READY.** The final round's findings are closed and
the suite is green, but no auditor has seen the result of closing them.

**And then, after the audit budget closed, two minutes of contact with reality
beat four rounds of inspection.** Running the shipped tools read-only against
the three real `PROJECT.yaml` files on this machine — which no round had ever
done — found three defects in about half an hour. The worst: the contract reader
**raised on a live project's contract**, making it unreadable by every tool over
one optional block, because this release had invented a field spelling that
project does not use. The other two: a pin classifier that answered about a
project whose contract it had never opened, and every CLI printing a stack trace
where it should have reported a refusal. Eight auditors were
given the repository and audited the repository; nobody was asked to point the
release at the world it ships into, and that omission is the coordinator's. Both
defects are repaired and mutation-tested; the account is in
`docs/RP2.2-GATE.md`, under *After the audit budget closed*.

**Read that section before the rest.** It is the strongest evidence in this
packet about what kind of defect this candidate is still likely to contain, and
it argues for a specific next step: a round that runs the release against real
consumers rather than against itself.

## What to check first

```bash
# Verify the candidate WITHOUT checking it out in a root a project pins (D18):
git clone --local --no-hardlinks --branch evolution/rp2.2 <pack_root> <scratch_dir>
cd <scratch_dir>
python3 tools/pack_pin.py . --version 2.2.0 --state IN_PROGRESS
python3 -m pytest tools/tests/ -q

# Then record the identity, from the clone, for every LATER verification:
git rev-parse HEAD
python3 -c 'import json;print(json.load(open("PACK_MANIFEST.json"))["tree_digest_sha256"])'
```

**`--sha` and `--digest` are deliberately absent from the first command**, and
this is the correction of a real defect: an earlier version of this block read
the digest out of `PACK_MANIFEST.json` and passed it back to a verifier that
checks against `PACK_MANIFEST.json`. That comparison cannot fail, and printing
it beside the ones that can made the whole block look stronger than it was.

What the first command *does* check is not circular: the digest recorded in the
manifest is recomputed from the tree, the file count is recounted, untracked
strays are enumerated, `--version` is compared against the `VERSION` file, and
`--state` against the manifest. A tampered tree fails every one of those.

`--sha` and `--digest` are the fields a **consumer** supplies from a record
kept outside the tree. They become real checks the moment the two commands above
have been run once and their output written down somewhere this repository
cannot reach — which is what a release announcement is for.

**The clone acquires an `origin` pointing back at the pack root** — every local
clone does, and this one was made and checked, not assumed. That is a remote on
a repository whose release model says it has none (D5), so the scratch clone is
for reading and running, never for pushing from. Delete it when the check is
done, or `git remote remove origin` first. Stated because the procedure above is
the one this document tells you to run, and it leaves you holding something the
pack root deliberately does not have.

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
| Files the digest covers | `PACK_MANIFEST.json` `digest_file_count` — every tracked file except the manifest |

No push, no tag, no remote, no publication. The repository has no remote
configured and none was added.

## What this release is for

The pack now checks four things it previously asserted and could not check: the
**adapters** it dispatches through, the **release** a project is pinned to and
how it moves between releases, the **semantic authority** a project runs
against, and the **capacity** a routing decision assumes. Plus **ten** reproduced defects in the machinery that was already there — one of
them a real leak — and one enforcement added where no drift existed. The gate
record's C3 table has eleven rows, and the row that says so of itself is the
one for the push form.

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

- **No audit round has returned READY.** Four rounds each returned NOT READY;
  the last round's findings are repaired and unaudited. Four closure cycles were
  the authorised budget and four ran, so a fifth round — not a smaller step — is
  what remains, and it is the release authority's call rather than a step that
  was skipped.
- **The release was never exercised against a real consumer until after the
  audit budget closed**, and doing so immediately found three defects including
  the most serious in the release. Two of the three real projects are still on legacy pins
  — theirs to change at a capability boundary, and deliberately not touched —
  and the third now reads correctly: a verified pack pin, and a Project Context
  that names the one field it does not record. What is *not* established is
  whether any other tool in this release behaves against real project data the
  way it behaves against fixtures. One pass found two defects; nothing says the
  second pass would find none.
- **Prose claims about this release's own history are not checked by anything.**
  Two guards cover the two lies that actually recurred: no document may state a
  divergence figure, and every count in the derived routing view must match the
  observation log. A sentence elsewhere in this packet that misdescribed an
  audit would ship green. Four rounds' evidence says that is the likeliest
  remaining defect in this candidate, and it is the reason the gate record
  exists in the shape it does.
- **Repairs regressed the commit gate against 2.1.1 more than once** — a trailer
  escaping behind extra whitespace, a second prefix, a non-ASCII token, an
  invisible character, and a Unicode space after a bullet marker. Each was found
  by an audit, and the last of them in work no auditor had yet seen. All are
  closed and now pinned by an **absolute** property test over generated
  decorations, because a differential against 2.1.1 is structurally blind to any
  hole 2.1.1 also had.
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
