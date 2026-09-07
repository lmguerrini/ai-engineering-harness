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

**Derived, not asserted.** `tools/surface_diff.py . 9d906ce64bd69cb1a29594a7110829da7df5d996 HEAD`
over the non-test modules reports **additions only**:

    tools/gitread.py         added_public_name  repository_location  (+ star export)
    tools/gitread.py         added_public_name  VERB_ENABLING_OPTIONS
    tools/gitread.py         added_public_name  MAXIMUM_NESTED_DEPTH
    tools/gitread.py         added_public_name  FLAG_BASED_CLOSURES
    tools/gitread.py         added_public_name  CONDITIONAL_CLOSURES
    tools/gitread.py         added_optional_parameter  program_valued_config
    tools/design_record.py   added_public_name  CHANGE_CLASS_RANK
    tools/design_record.py   added_optional_parameter  DesignRecord.problems
    tools/backend_contract.py  added_public_name  normalised_identity_value  (+ star export)

**Nothing is removed and no signature changes**, which is the point of keeping the
enumeration's names as projections: the mechanism behind them is gone and the
surface a consumer imports is not.

**And a blind spot in that derivation, stated rather than left to be found.**
`surface_diff` compares modules present at both revisions, so `tools/sterile.py`
— a module that did not exist at the baseline — does not appear in its output at
all. The tool cannot see the single largest thing this release adds. So the MINOR
derivation rests on two facts and the second is not `surface_diff`'s: the compared
surface only grew, **and** a new tool ships, which is the criterion `PACK_MANIFEST.json`
`version_semantics` names for MINOR and the one 2.4.1 checked and failed.

MAJOR was checked and rejected: no contract key or CLI input is added or removed,
no project's pin moves, and no migration changes. Behaviour that previously
refused and now reads is the repair rather than an incompatibility — but three
behaviour changes a consumer can observe are disclosed in `CHANGELOG.md` rather
than left for one to discover.

## Design before build

| | |
|---|---|
| Record | `docs/RP2.5.0-DESIGN-A1-sterile-execution.md` |
| Class | MATERIAL |
| Frozen at | `71e24f89cf1d0d8084531418ab758ce4f4c945fa` |
| Committed at | `154be5fe2547293aa8a2a16bb1edbe523bb35b7c`, **before any implementation existed** |
| Checked by | `python3 tools/design_record.py docs/RP2.5.0-DESIGN-A1-sterile-execution.md --repository .` → `DESIGN FROZEN` |

`design_record.py` tallies **three** rejected alternatives for A1, and the record
considers five designs. The fifth — the observational one, kept as an oracle
because detection after execution is not a barrier — has the verdict
`REJECTED as a barrier`, which the parser does not count as `REJECTED`. Three
rejected outright, one rejected in the role it was proposed for and retained in
another. An independent certification read the mismatch as an inconsistency, and
it was: the prose said four where the tool says three.

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

## Design records, and where their oracles landed

`docs/RP2.5.0-DESIGN-A1-sterile-execution.md` is frozen at
`71e24f89cf1d0d8084531418ab758ce4f4c945fa` and committed at `154be5f`, before any
implementation existed. `docs/RP2.5.0-DESIGN-A2-nested-and-ambient.md` supersedes
part of it after an independent design reading returned `DESIGN_BLOCKED`, and is
frozen at `fb2f450e53db1d3b5e5f1b752af3ffb9d4900f97`.

Both are left exactly as they were frozen. One selector in A1 has been superseded
and is recorded here rather than edited there, because a frozen design record that
is corrected afterwards is no longer evidence of what was decided beforehand:

| Record | Oracle | Selector as frozen | The test that implements it |
|---|---|---|---|
| A1 | O2 | `test_a_nested_repositorys_configuration_never_executes` | `test_no_spelling_of_a_nested_git_executes_the_subjects_program`, parametrised over four spellings of a nested `.git` — A2 widened the property from *a* nested repository to *any spelling of one*, and the name followed |

Every other oracle in A1 and A2 names a test that exists and runs.

## What the implementation changed, and what was measured about it

The boundary is `tools/sterile.py`, and `tools/gitread.py` is its only caller.
`tools/release_delta.py` was the last module reaching Git around it and now goes
through it; the only remaining subprocess callers in `tools/` run `pytest` and
`ps`, so `gitread` is the toolbelt's single path to Git.

Eight defects were found in the implementation while building it, each reproduced
by a test before being repaired, and each recorded because a boundary nobody broke
is a claim:

| # | What was wrong | How it failed |
|---|---|---|
| 1 | a deadline escaped the construction as `TimeoutExpired` | neither of this pack's refusals, and not recognisable as one |
| 2 | `git config --get` read the harness's own configuration | a silent wrong answer about the wrong repository |
| 3 | `git config --file` does not follow `include.path` under an explicit `GIT_DIR` | keys hidden behind an include would have been reported as absent |
| 4 | the view's post-condition asked only whether a `.git` resolved under the scratch directory | a **copied** `.git` satisfies that; it now requires membership in the set this build made |
| 5 | the HEAD round trip refused a subject whose own HEAD is dangling | the build reproduces that subject exactly, and `ls-files` never needed HEAD |
| 6 | `protocol.allow = never` was set only when a caller enabled a transport | every other read fell back to Git's defaults, dropping a posture this module has always had |
| 7 | three callers asked Git where the repository is | under the boundary Git answers about the build; `activity` counted one repository as six |
| 8 | `ls-tree` was routed through the boundary without `-z` | a C-quoted path would reach the delta as an escaped literal |

## Mutation scoring

Eleven well-formed mutants against a verified-green baseline of the twenty-four
oracle tests, each reversing one thing the design says is load-bearing. **Eleven
killed, none survived, none malformed**, and the harness asserts the subject is
byte-identical afterwards.

Scoring did not merely confirm the implementation. It found three things a
reading had not:

| What scoring found | Why it mattered |
|---|---|
| A **non-effective mutant**, rejected rather than counted | "nested detection asks the TYPE" used `Path.is_dir()`, which *follows* a symlink, so it still detected the spelling it was written to miss. Replaced with the defect that actually shipped — the directory-symlink branch running before the name check — which the oracle kills |
| The post-condition's **call site was unpinned** | Deleting the call left the direct test of the check passing, because that test invokes the check itself. It measured the property and never the wiring |
| An oracle measuring **half the property** | A mutant that dropped a symlinked `.git` from the walk executed nothing and passed every assertion. Not executing is half the guarantee: a view that omits a nested repository describes a repository that is not there. The oracle now also compares the superproject's answer against real Git's |

The harness itself was wrong once and the run is what showed it: a mutant killed
in isolation survived in a full run. That is order dependence from CPython's
`(mtime, size)` bytecode cache under a loop that rewrites the same paths many
times a second, not a property of the subject. The harness now clears
`__pycache__` and sets `PYTHONDONTWRITEBYTECODE` before every run, because a
score taken against a stale `.pyc` is wrong in whichever direction happens to
suit.

## Consumer rehearsal

Two disposable consumers, copied from the real projects and never written back.
The real `consumer-a-v0.1.0-baseline` tree is fingerprinted before and after and
is byte-identical; `consumer-c-v1` is 437 MB and only its contract surface was
copied, so nothing of it was touched either.

| Check | Result |
|---|---|
| frozen 2.4.0 verifies from a working directory belonging to neither consumer | PASS |
| the candidate verifies against its own manifest and still declares `IN_PROGRESS`, so no project may pin it | PASS |
| migration reports a pin class without adopting anything | PASS |
| both consumers verify concurrently, from a foreign working directory | PASS |
| a governed read of a directory that is not a repository refuses rather than answering | PASS |
| the real project is byte-identical afterwards | PASS |
| no sterile scratch directory survives the rehearsal | PASS |

The behaviours the plan names beyond these — the design-first gate, discovery of
an unseen model identifier, per-configuration qualification and `UNKNOWN`,
durable restart with no phantom work, producer completion, failure and capacity,
rollback and refusal — are exercised by `test_two_consumer_rehearsal.py`,
`test_adoption_rehearsal.py`, `test_lifecycle_rehearsal.py`,
`test_continuation_rehearsal.py`, `test_consumer_compatibility.py` and
`test_background_governance.py`, which are part of the suite this release
records. Their population is not restated here, for the same reason the delta is
not — measure it:

```bash
python3 -m pytest tools/tests/test_two_consumer_rehearsal.py \
    tools/tests/test_adoption_rehearsal.py tools/tests/test_lifecycle_rehearsal.py \
    tools/tests/test_continuation_rehearsal.py tools/tests/test_consumer_compatibility.py \
    tools/tests/test_background_governance.py -q
```

## The hostile matrix, against the shipped implementation

Re-run against `tools/sterile.py` as committed rather than against the prototype:
**zero execution leaks**. Every verbosity spelling including `--verbo`; an
explicitly requested `--textconv` and `--ext-diff`; the ignored never-a-submodule
checkout that broke `workspace_report`; a nested `.git` that is a symlink to a
directory; `sha256` reads; `reftable` refuses by name; a dangling symlink, an
empty file and a FIFO in place of a nested `.git` each refuse and name the path.

## Mechanical gates, and the commands that produced them

Run on the revision this record is committed with. Each is repeatable from a
checkout; none of the figures below is transcribed from a previous run.

| Gate | Command | Result |
|---|---|---|
| release identity | `python3 tools/pack_pin.py . --version <VERSION> --sha <HEAD> --digest <manifest digest> --state IN_PROGRESS` | verified |
| release delta | `python3 tools/release_delta.py . --baseline 9d906ce…` | DELTA COMPLETE, nothing omitted |
| design provenance | `python3 tools/design_record.py docs/RP2.5.0-DESIGN-A{1,2}-*.md --repository .` | DESIGN FROZEN, both |
| surface derivation | `python3 tools/surface_diff.py . 9d906ce… HEAD` | additions only over the compared surface |
| full suite | `python3 -m pytest tools/tests/ -q` | green; the population is `PACK_MANIFEST.json` `tests.passed` |
| clean-room clone | clone with `--no-local`, check out the revision, run every gate and the suite inside it | every gate passed and the suite was green, with a tree reporting nothing changed |
| line-ending variants | clone and check out under `core.autocrlf` `true`, `input` and `false`, then verify the pin in each | verified in all three |
| hostile Git configuration | `<scratch>/repro/module_check.py`, `spellings.py`, and the batteries an independent design reading wrote | zero executions |
| mutation | `<scratch>/mutation/mutate.py` | every mutant killed, subject byte-identical afterwards |
| consumer rehearsal | `<scratch>/rehearsal/rehearse.py` | every check passed, the real project byte-identical |

The clean-room clone is the one that matters most for the design records: it
establishes that both `**Base revision:**` values still resolve in a repository
that has only this line's commits, which a rewrite of any commit in that ancestry
would end.

## What the first independent certification found

A whole-candidate certification returned **READY** with no release blocker, three
non-blocking findings and one coverage gap. All four were reproduced here and all
four are repaired, because a non-blocking finding that is true is still true.

| Finding | What it was | What was done |
|---|---|---|
| the record said "three" behaviour changes where the changelog lists more | loose prose in this record | the count is gone; the changelog's list is the disclosure |
| `design_record` tallies three rejected designs where this record said four | the parser does not count `REJECTED as a barrier` | stated above, in the tool's terms and the record's |
| `ALLOWABLE_TRANSPORTS` is consulted in a refusal, while A1 lists it among names that decide nothing | the design's phrasing was wrong | it is a **caller-capability** allowlist, not a projection: it bounds what a caller may ask to enable, and the subject's own transport settings are not read at all. Said where the constant is defined |
| the mutation and hostile-matrix figures cited scripts outside the release | a reader could reproduce the property but not the number | both ship as `docs/acceptance/rp2.5.0-mutation.py` and `docs/acceptance/rp2.5.0-hostile-matrix.py` |

**And a finding the certification's third point led to, which was larger than the
point itself.** Chasing why `ALLOWABLE_TRANSPORTS` appeared to be consulted twice
showed that `_NEUTRALISED_CONFIG`, `_config_environment`, `_GIT_ENVIRONMENT` and
`_environment` — the whole pre-2.5.0 environment layer — were still in
`tools/gitread.py` with **no production caller**. They were unreachable, so they
could not disagree with anything; but **seven tests still exercised them**, and
those tests were green about a code path no governed read executes. That is this
pack's own recurrence class *oracle satisfied for a reason other than its claim*,
sitting inside the release built to end a different one.

The machinery is deleted. Six of the seven tests were rewritten to assert the
same guarantees against the live path — a transport refusal is now measured by
asking Git to reach a remote rather than by reading a dictionary the code no
longer builds — and one, which asserted that enabling a transport lifts a
neutralisation of `core.sshCommand`, is gone with the mechanism: the sterile
configuration never sets that key, because the subject's is not read.

## The second certification attempt, and what it found before it ended

A re-certification of the revision before this one reported a **blocker-class
record defect** and then ended without issuing a verdict — its session could not
be resumed. Under this project's own rule an environmental failure is neither a
finding nor a successful certification, so **that run is not a certification of
anything**, and the findings it did produce were still reproduced and repaired
before it was set aside.

**The blocker.** `PACK_MANIFEST.json` `supersedes` carried 2.4.1's text verbatim:
it called this release **PATCH** and stated that **no tool, policy or capability
is new**. Both are false, and the second is false about the single fact the MINOR
derivation rests on — `tools/sterile.py`. A manifest that contradicts its own gate
record is exactly the defect, and the machine-readable record is the one a
consumer reads first.

**The same staleness, found by following it.** `known_limitations[0]` still
described this candidate as the one that "closes six defects an independent full
behavioural audit reproduced in frozen 2.4.0" and pointed at `docs/RP2.4.1-GATE.md`.
And six limitations — 9, 10, 14, 98, 99 and 100 — describe the pre-2.5.0 mechanism
in the present tense, including one that says `-v`/`--verbose` "is refused as an
argument now" and that the walk "enumerates directories containing `.git`",
neither of which is how this release works.

Those six are **kept verbatim and marked**, not corrected and not deleted. They
are the evidence `docs/RP2.5.0-RECURRENCE-MAP.md` argues from — the repairs whose
failure to converge is the case for replacing the mechanism — so rewriting them
would weaken the argument they support, and removing them would erase it. Each now
opens with a marker saying the mechanism was deleted in 2.5.0 and that its present
tense should be read as the state at 2.4.1. `supersedes` and limitation 0, which
make claims about **this** release rather than recording a past one, are corrected
outright.

## Evolution evidence

Every repair in this release classifies against classes
`policy/recurrence-classes.json` already carries — chiefly *read-only Git
executing repository-configured programs*, *shared object/path enumeration
incomplete*, *oracle satisfied for a reason other than its claim*, *vacuous
mutation test*, *transcribed counts drifting from computable facts*, and
*projection becoming authority*, which is the class the founder's constraint on
keeping the enumeration's names as projections is guarding against and which
`test_no_refusal_depends_on_a_projection` is the live oracle for.

**No class was added, and one was considered and rejected.** The architectural
lesson this release carries — that an authority mechanism whose completeness
obligation grows with the system it guards does not converge — was drafted as a
new class and withdrawn: `policy/recurrence-classes.json` has a prose twin in
`docs/RP2.3-REFALSIFICATION-MAP.md` and a test that requires the two to hold the
same classes, so adding it would have meant editing a 2.3 release record to
carry a 2.5.0 lesson. The lesson is in `docs/RP2.5.0-RECURRENCE-MAP.md`, which is
this release's own document and the place a reader would look for it.

One selector *was* corrected, because the test it named no longer exists: the
class *a repository disabling the check that inspects it* selected
`breaking_its_own or re_enter`, and the re-entrancy guard those matched went with
the mechanism. It now selects the tests that carry the same guarantee under the
new one.

## Not yet done

The independent certifications, and the terminal gates that depend on them.

`AUTH-4` holds the Codex/Astra budget until its weekly reset, and the findings an
independent design reading produced are that reader's own, so their independent
closure must route to the other provider against the implementation rather than
against the prototype. No self-review substitutes for it, and this record does
not treat the repair of those findings as confirmed until it has run.

One thing this line does not yet satisfy, recorded rather than left to be
discovered: three of its own commit messages predate the discipline the rest of
the line follows and do not conform to `tools/commit_gate.py`. Repairing a commit
message rewrites the commit, and `docs/RP2.5.0-DESIGN-A2-nested-and-ambient.md`
is frozen at one of the revisions that would move — so the repair trades the
commit-range gate for the design-provenance gate, in a clean-room clone where the
old object does not exist. It is a history rewrite either way, which is a founder
decision and is not taken here.
