# RP 2.5.0 — gate record

**This record is being written as the release is built, and says only what has
been established.** Anything not below has not been done. The release is
`IN_PROGRESS`; no project may pin it.

## Subject

| | |
|---|---|
| Version | 2.5.0 (`VERSION`) |
| Baseline | `9d906ce64bd69cb1a29594a7110829da7df5d996` — the 2.4.0 release commit. 2.4.1 was never released |
| State | `IN_PROGRESS`. **No project may pin this.** |
| Revision, digest | in `PACK_MANIFEST.json`, recomputed over the tree this gate ran against |

## Why this release is not 2.4.2

2.4.1 was a PATCH line: enforcement of already-promised guarantees. It reached a
convergence blocker instead of a release. Seven consecutive repair cycles each
found a defect in the immediately preceding repair of the same boundary, and its
final independent certification reproduced an under-refusal and an over-refusal
**in the same repair**. `docs/RP2.5.0-RECURRENCE-MAP.md` reads all fifteen
together and names the cause: the boundary decided authority by enumerating
Git's semantics, which is an open set with a fail-open failure mode.

This release replaces that mechanism rather than correcting another entry in it,
which is a new authority mechanism and a new tool — MINOR, not PATCH.
`tools/surface_diff.py . 9d906ce64bd69cb1a29594a7110829da7df5d996 HEAD` is the
mechanical derivation and is recorded below when the implementation is complete;
until then the number in `VERSION` is a claim this record has not yet checked.

## Design before build

| | |
|---|---|
| Record | `docs/RP2.5.0-DESIGN-A1-sterile-execution.md` |
| Class | MATERIAL |
| Frozen at | `71e24f89cf1d0d8084531418ab758ce4f4c945fa` |
| Committed at | `154be5fe2547293aa8a2a16bb1edbe523bb35b7c`, **before any implementation existed** |
| Checked by | `python3 tools/design_record.py docs/RP2.5.0-DESIGN-A1-sterile-execution.md --repository .` → `DESIGN FROZEN` |

Four alternatives were rejected with reasons, including the observational design
kept as an oracle because detection after execution is not a barrier.

## What has been measured

Against real Git 2.50.1 on macOS, before the design record was written:

| | |
|---|---|
| Hostile cases | 31 |
| Execution leaks | **0** |
| Answers equal to real Git, byte for byte | every case where real Git answers, except where real Git's answer *contains the helper's output* |
| Child processes started, by `GIT_TRACE2_EVENT` | 0 |
| Cost, no nested repository | 4 ms (200 files) – 12 ms (20,000 files) |
| Cost, nested repository present | 40 ms (200 files) – 2.3 s (20,000 files) |

The two blockers that stopped 2.4.1 were reproduced here first and then closed:
`git status -vv`, `--verb` and a third spelling no reader had reported,
`--verbo`, each executed a repository's text conversion helper; and an ignored,
never-a-submodule checkout made `workspace_report.classify_workspace` raise
where real Git exits 0.

Three defects were found in the coordinator's own prototype before it reached the
design record, and are recorded because a prototype nobody broke is a claim:
two unknowns compared equal, so a `reftable` subject reported every tracked file
as newly added at exit 0; a directory symlink was materialised as a real
directory, so the view lied about the tree; and an unrecognised `extensions.*`
key refused wholesale, which over-refused ordinary linked worktrees.

## Figures, bound rather than typed

Every number a reader might rely on is measured by a test or given as a command,
because four stale figures in one section of an earlier gate record is what
taught this pack the difference.

    held prose, in-release (skills/core/*.md + policy/*.md) 1896

against the `policy/BUDGETS.md` ~2,000 target, and under it. This release adds no
line to either directory.

The suite count is not restated here. It lives in `PACK_MANIFEST.json` `tests.passed`,
and `test_the_recorded_test_count_is_the_count_the_suite_actually_collects` binds
that figure to what the suite really collects.

Delta against the frozen baseline: **not stated here.** Any number written in
this file is wrong the moment the file is edited, which is the manifest's own
revision problem in prose. Measure it:

```bash
git diff --shortstat 9d906ce64bd69cb1a29594a7110829da7df5d996..HEAD
```

## What the freeze does not settle about publication

The publication adjudication this release points at is
`docs/RP2.4-PUBLICATION-ADJUDICATION.md`, unchanged and still the owner of that
conclusion. **One occurrence in the complete reachable history names a real
machine account.** It is remediable only by a history rewrite
(`policy/hitl-matrix.md` rows 2 and 4), and that rewrite is not taken here.
Nothing is published, so nothing is exposed — but a record that states a
publication conclusion while dropping its only known exception is a defect this
pack has already shipped once, so it is stated here rather than left to the
document next door.

## Not yet done

The implementation, its oracles, mutation scoring, the consumer rehearsals, the
independent certifications and the terminal gates. Each is recorded here when it
has run, with the command that produced it.
