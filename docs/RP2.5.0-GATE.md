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
| Digest | `PACK_MANIFEST.json` `tree_digest_sha256`, recomputed over the tree this gate ran against |
| Revision | **not in the manifest** — `PACK_MANIFEST.json` `revision` says so in as many words, because a file cannot name the commit that contains it. It is `git rev-parse HEAD` here, and a consumer records it in its own pin |

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

**No non-test name is removed and no non-test signature changes**, which is the
point of keeping the enumeration's names as projections: the mechanism behind them
is gone and the surface a consumer imports is not.

Over the WHOLE compared surface — test modules included — the same command also
reports removals and signature changes, **and every one of them is inside
`tools/tests/`**. That is not a compatibility event: `tools/tests/` is not a
surface anything imports, and it is where the obsolete mechanism's tests were
removed and rewritten.

**No totals are written here, and that is the second time this record has had to
learn it.** An earlier draft claimed the tool reported "additions only", which its
own output contradicts. The correction then stated the three totals — and the very
commit that stated them added two test functions, so "92 added public names" was
already the PREVIOUS revision's figure when it was written, and an independent
certification recomputed 94 and called it a release blocker. It was right to. A
figure that changes whenever the tree changes cannot be transcribed into prose that
ships with the tree. What is stated instead is the claim the version actually rests
on, and that claim is bound by a test rather than by a sentence:
`test_no_tool_removed_a_public_name_or_changed_a_signature_since_the_baseline`
compares every `tools/*.py` against the declared baseline and fails on any removal
or signature change outside `tools/tests/`.

**And a blind spot in that derivation, stated rather than left to be found.**
`surface_diff` compares modules present at both revisions, so `tools/sterile.py`
— a module that did not exist at the baseline — does not appear in its output at
all. The tool cannot see the single largest thing this release adds. So the MINOR
derivation rests on two facts and the second is not `surface_diff`'s: the compared
surface only grew, **and** a new tool ships, which is the criterion `PACK_MANIFEST.json`
`version_semantics` names for MINOR and the one 2.4.1 checked and failed.

MAJOR was checked and rejected: no contract key or CLI input is added or removed,
no project's pin moves, and no migration changes. Behaviour that previously
refused and now reads is the repair rather than an incompatibility. Every
consumer-observable change is listed under *What a consumer will notice* in
`CHANGELOG.md` rather than left for one to discover; the number is not restated
here, for the same reason no other count in this record is.

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
| Hostile cases | measured by `docs/acceptance/rp2.5.0-hostile-matrix.py`, which ships |
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
| A1 | O2 | `test_a_nested_repositorys_configuration_never_executes` | `test_no_spelling_of_a_nested_git_executes_the_subjects_program`, parametrised over every spelling of a nested `.git` this release could build — A2 widened the property from *a* nested repository to *any spelling of one*, and the name followed. The count is not written here: adding a spelling is exactly the change this table should not have to be edited for, and a stated "four" survived the commit that made it five |

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

Eleven well-formed mutants against a verified-green baseline of the oracles they
name, each reversing one thing the design says is load-bearing. **Eleven killed,
none survived, none malformed**, and the harness asserts the subject is
byte-identical afterwards.

The baseline population is **not stated here**. This record used to say
twenty-four oracle tests; collection said twenty-two, and neither number could be
recomputed from anything that ships — the same defect as a figure cited from a
script that does not exist. The harness now derives and prints its own population on its baseline line, so the
figure a reader recomputes is the only one that exists. None is repeated here.

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

**Copy these verbatim.** An independent read found three rows that did not run as
printed: a brace expansion handed two records to a CLI that takes one, and a
typographic ellipsis inside `9d906ce…` is not a revision Git resolves. A command
a reader cannot paste is not a repeatable command, whatever the row claims, so
the full baseline is spelled out and the two design records are two invocations.

| Gate | Command | Result |
|---|---|---|
| release identity | `python3 tools/pack_pin.py . --version <VERSION> --sha <HEAD> --digest <manifest digest> --state IN_PROGRESS` | verified |
| release delta | `python3 tools/release_delta.py . --baseline 9d906ce64bd69cb1a29594a7110829da7df5d996` | DELTA COMPLETE, nothing omitted |
| design provenance | `python3 tools/design_record.py docs/RP2.5.0-DESIGN-A1-sterile-execution.md --repository .` then the same for `docs/RP2.5.0-DESIGN-A2-nested-and-ambient.md` | DESIGN FROZEN, both |
| surface derivation | `python3 tools/surface_diff.py . 9d906ce64bd69cb1a29594a7110829da7df5d996 HEAD` | additions only over the NON-TEST modules; every removal and every signature change it reports is inside `tools/tests/`. No totals are quoted here — see *Why this release is not 2.4.2* for why |
| full suite | `python3 -m pytest tools/tests/ -q` | green; the population is `PACK_MANIFEST.json` `tests.passed` |
| clean-room clone | clone with `--no-local`, check out the revision, run every gate and the suite inside it | every gate passed and the suite was green, with a tree reporting nothing changed |
| line-ending variants | clone and check out under `core.autocrlf` `true`, `input` and `false`, then verify the pin in each | verified in all three |
| hostile Git configuration | `python3 docs/acceptance/rp2.5.0-hostile-matrix.py` | zero executions; the script reports how many rows carry a positive control |
| mutation | `python3 docs/acceptance/rp2.5.0-mutation.py` | every mutant killed, none malformed, subject byte-identical afterwards |
| consumer rehearsal | **not shipped as a script** — it copies the machine's real projects, so it cannot run from a checkout. Its behaviours are covered by the six suite modules named under *Consumer rehearsal* below | every check passed, the real project byte-identical |

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
| the mutation and hostile-matrix figures cited scripts outside the release | a reader could reproduce the property but not the number | both ship as `docs/acceptance/rp2.5.0-mutation.py` and `docs/acceptance/rp2.5.0-hostile-matrix.py`. The pre-design prototype's "31 hostile cases" is gone from this record: the shipped script counts its own cases and its own positive controls in its last line, and THAT is the figure a reader recomputes. No number is written here, because one was — "13 cases with 9" — and it went stale the moment a row was added |

**And a finding the certification's third point led to, which was larger than the
point itself.** Chasing why `ALLOWABLE_TRANSPORTS` appeared to be consulted twice
showed that `_NEUTRALISED_CONFIG`, `_config_environment`, `_GIT_ENVIRONMENT` and
`_environment` — the whole pre-2.5.0 environment layer — were still in
`tools/gitread.py` with **no production caller**. They were unreachable, so they
could not disagree with anything; but **seven tests still exercised them**, and
those tests were green about a code path no governed read executes. That is this
pack's own recurrence class *oracle satisfied for a reason other than its claim*,
sitting inside the release built to end a different one.

The machinery is deleted. **Five** test functions referenced it, not seven:
**three** were rewritten to assert the same guarantees against the live path — a
transport refusal is now measured by asking Git to reach a remote rather than by
reading a dictionary the code no longer builds — and **two** were removed, one
asserting that enabling a transport lifts a neutralisation of `core.sshCommand`
and one asserting that every conditional closure is known to an inspection that
no longer exists.

The first version of this paragraph said seven and six and one. An independent
certification measured five, three and two, and corroborated it from this
release's own arithmetic: `tests.passed` went 2873 → 2871, a net loss of two,
which "six rewritten and one dropped" cannot produce. The figure was wrong in a
record whose whole subject is figures being wrong, and it is corrected here
rather than quietly.

## The second certification, and the four things it found

A whole-candidate re-certification of the revision before this one returned
**NOT_READY**: one release blocker and three non-blocking findings, plus an
observation. Its verdict is superseded by the repairs below — every repair
invalidates every certification taken before it — but its findings are recorded
here because three of them are about this record's own truthfulness, and one of
them is that a repair this record claimed to have made had not been made.

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

**The three non-blocking findings, and the one that matters most.** The
certification found that this record still said "three behaviour changes" where
the changelog lists more — **and that the table above already claimed the count was
gone**. It was not: the sentence is line-wrapped, the edit that was supposed to
remove it did not match, and nobody checked. A record that asserts its own repair
without verifying it is the same defect as a figure nobody recomputed, one level
up. It is removed now, and the removal was verified by searching for it again
rather than by assuming.

It also found the accounting of the deleted layer wrong — corrected below, in the
certification's numbers rather than mine — and the "31 hostile cases" figure
unrecomputable, because it came from a prototype that does not ship. That figure
is gone FROM THIS RECORD, and the shipped script's own output stands in its place.
It survives in `docs/RP2.5.0-DESIGN-A1-sterile-execution.md`, which is FROZEN and
must not be edited: there it is a prototype measurement taken before the design
was written, which is what a design record is for. An earlier draft of this
sentence said the figure was gone without saying from where, and a reader
grepping the tree found it and was right to. A dead helper the
deleted tests left behind is removed. And `qualified_at` carried a date under a
state that says the release is not qualified, which is how a reader comes to
believe a candidate was qualified on a day nobody qualified it; the field now says
what it actually records.

What the certification could **not** break is worth as much as what it found: it
established independently that deleting the environment layer weakened no
guarantee — every property it carried is measured on the live path, and
`protocol.file.allow=always` no longer standing is a tightening — and that the
rewritten tests discriminate rather than merely passing, which mutation confirms
by killing the mutant that drops the standing transport refusal.

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

## What the second qualification pass found in this release's own work

The first independent certification returned READY on revision `3dec69a`. A second pass ran anyway, on the principle that a certification
is evidence and not a guarantee, and it found four defects that certification had
not: one in the mechanism this release exists to introduce, and three in the
oracles whose whole job is to catch exactly that. All four are repaired here, each
reproduced before it was repaired — which is why the READY on `3dec69a` is
SUPERSEDED rather than carried forward. A certification belongs to the tree it
read, and this is not that tree.

**A shipped tool reached the operator as a traceback, on a repository nobody had to
be hostile to build.** `os.path.lexists(here / ".git")` is answered by the
FILESYSTEM, and a case-insensitive volume — the ordinary macOS default — answers it
YES for `.GIT` and `.Git`. Comparing a walked name to the literal `".git"` answers
NO. `tools/sterile.py` asked that one question both ways and believed both answers:
the detector saw a nested repository, the copier reproduced the entry into the view
verbatim, and the build then raised `FileExistsError` installing its own `.git`
over a name that already existed. `errors.run_cli` catches `HxError` and
`gitread.probe` catches `GitRefusal`, so an `OSError` from the construction escaped
both — `python3 tools/workspace_report.py` on a repository containing an ordinary
empty directory named `.Git` printed a Python traceback. **The safety property was
never broken**: measured against a real positive control, plain Git ran the
subject's program for 36 marker bytes on every case-variant fixture and the
boundary ran it for none. The defect was the crash.

It is repaired as the class rather than the spelling, twice over. `dot_git_name()`
resolves the on-disk spelling THROUGH the filesystem and is now the single answer
used by `nested_repository_paths`, `_build_view` and the post-condition alike — one
question, one answer, from the same source Git will consult. And `build` now
converts anything that is not one of this pack's own refusals into a named
`GitRefusal`, which closes a class this release had already repaired once for a
single spelling, a `subprocess.TimeoutExpired` escaping the same construction.

**The evidence that ships passed with the mechanism gutted.** A mutant deleting the
line that installs each rebuilt nested repository into the view — so that the view
describes repositories that are not there — still produced *13 cases, 9 carrying a
positive control, 0 execution leaks* and exit 0 from
`docs/acceptance/rp2.5.0-hostile-matrix.py`. The suite caught that mutant; the
script a reader is told to recompute did not, because it counted marker bytes and
never compared an answer. That is this pack's own recurrence class *an oracle that
measured half the property*, which this release had already found once and fixed in
the suite only. The matrix now also compares each row's `status --porcelain`
against real Git's — a STATE report, so a driver that rewrites CONTENT does not
make the reference unfair, which a content verb like `diff` would — counts the
comparisons so that a comparison of nothing cannot pass, treats an exception that
is not a refusal as a failure rather than printing it at exit 0, and carries a new
row for the case-variant spelling. It now fails on both defects above.

**A guarantee lived in a comment.** `gitread._run` discards the construction in a
`finally`, and the comment beside it says that is where zero residual scratch is
kept true. Deleting the call left every behavioural test green — a full suite
produced only the four identity-and-digest failures that any byte change produces —
while that same run leaked 3,548 directories into the system temp directory.
`test_a_governed_read_discards_its_construction_however_the_read_ends` now pins the
CALL SITE, and asserts the construction actually ran, so it cannot pass by
measuring nothing.

**The non-regression check measured against the wrong release.**
`QUALIFIED_BASELINE` named 2.3.0's tip while `PACK_MANIFEST.json`
`baseline_revision` declares 2.4.0 and 2.4.0 is what consumers pin. 2.3.0 is an
ancestor, so the check ran and passed — but a public name introduced in 2.4.0 and
removed here is absent from a 2.3.0 surface and produces no change at all, which is
a blind spot in the direction of the claim. Corrected to the declared baseline.
Measured before and after: zero such names exist, so this closed a gap rather than
reporting a regression.

Each of the three new oracles was run against the defect it claims to catch and
fails there, and against the other two and does not.

### And what a second independent reader found in the records

A cross-vendor read of the records — deliberately scoped away from the execution
surface another reader held — reproduced thirteen findings against them. The ones
that were true are repaired above and here; the ones that were not are said so.

**A limitation described the deleted mechanism in the present tense, unmarked.**
`known_limitations[64]` still said an unrecognised program-valued key "refuses"
and that the inspection costs two extra Git processes per repository. Both are
false here: nothing refuses on that list and the inspection that ran those
processes is gone. Six entries like it were marked as historical when the
mechanism was deleted; this one was missed, which is exactly the class the
marking exists to prevent. It is now marked and dated rather than deleted,
because the recurrence map argues from the original sentence.

**Three rows of the command table did not run as printed**, in a table whose own
preamble says each row is repeatable from a checkout. A brace expansion handed
two design records to a CLI that accepts one, and `9d906ce…` carries a
typographic ellipsis that Git does not resolve. Both are now spelled out. A
command a reader cannot paste is not a repeatable command, whatever the row says.

**The record said a figure was gone that is still in the tree.** The pre-design
prototype's "31 hostile cases" is gone from this record, and it remains in
`docs/RP2.5.0-DESIGN-A1-sterile-execution.md`, which is frozen and must not be
edited — there it is a prototype measurement that predates the design, which is
what a design record is for. The sentence now says from where.

**The mutation baseline was a transcribed number.** This record said twenty-four
oracle tests; collection said twenty-two, and after the new spelling above it says
twenty-three. No figure that moves when a parametrisation changes should be typed
into prose, so the harness derives and prints its own population and this record
cites nothing.

**The record and the manifest contradicted each other about the revision.** This
record placed it in `PACK_MANIFEST.json`; the manifest says in as many words that
it is not there, and cannot be. Split into two rows.

**The recurrence map claimed every source was on disk.** Two of the five are
session records outside the release envelope, and a reader holding only this
release cannot inspect them — the path the map named is not in this tree. The map
now says which three ship and which two do not.

**And one the repair above uncovered, which no reader reported.** Correcting the
non-regression baseline made
`test_the_baseline_figure_this_release_quotes_is_the_baselines_own` fail, and it
was right to. The manifest's held-prose entry is **byte-identical to 2.4.0's** and
compares this release to 2.3.0 — the release before its own baseline. It is the
same defect as the `supersedes` field an earlier certification caught: a previous
release's text carried forward without being recomputed. The check that should
have caught it was reading the same wrong baseline, so it was green *because* it
was wrong. Measured rather than assumed on the way out: `skills/core/*.md` plus
`policy/*.md` is 1896 lines at 2.4.0 and 1896 lines here, so the figure itself was
right and only the comparison was stale.

**Reported and not repaired, recorded so the next reader does not re-derive them.**
The frozen `A2` record assigns O12 ten named nested-`.git` constructions and its
selector parametrises five, and assigns O15 both a global ignore file and global
attributes while its selector constructs only the ignore file. The record is
frozen and is not edited to match the code; the shortfall is stated here instead,
and the attributes half is **unestablished**, not passing. Separately,
`CLOSED_PROGRAM_KEYS`, `FLAG_BASED_CLOSURES`, `CONDITIONAL_CLOSURES` and
`MAXIMUM_NESTED_DEPTH` are retained public names that nothing consults; O6's
docstring, which justified one of them by a safety reason that is no longer true,
now says so. Removing them would remove a public name 2.4.0 shipped, which is a
SemVer decision this release does not take. Some private constants and a private
helper have no remaining caller, and `sterile.build`'s `needs_working_tree=False`
branch has no caller, and its `overlay` parameter is passed by `gitread._run` but
never with a value; they are disclosed here
rather than removed, because churn in a candidate under certification buys less
than an accurate record does.

### And what the certification of THAT work found, which was the same defect again

The pass described above was itself certified, and returned **NOT_READY** on two
release blockers. Both were in the records the pass had just rewritten, and both
were the class it had just spent a day closing.

`PACK_MANIFEST.json` and this record stated that `surface_diff` reports **92**
added public names. The tree reports 94. The 92 was correct at the PARENT revision
and stopped being correct in the very commit that wrote it down, because that
commit added two test functions — so the sentence was stale before it was
committed, in the field that carries the version derivation, under the words
"measured rather than transcribed". And this record told a reader that the shipped
hostile matrix "reports 13 cases with 9 carrying a positive control, and that is
the figure a reader can recompute", in the same document as a later sentence
saying the matrix had gained a row. A reader who accepts the invitation gets 14
and 10.

Neither figure was load-bearing — the certification confirmed independently that
no removal or signature change falls outside `tools/tests/`, and that the matrix
passes with a positive control on every row it claims one for. **The defect was
that they were written down at all.** A count a shipped command derives does not
belong in prose that ships beside it, because prose does not get recomputed when
the tree changes and the command does. Every total that a reader is INVITED TO
RECOMPUTE is now gone from this record and from the manifest, replaced by the claim
a test binds and by a pointer to the line each script prints. A first draft of this
sentence said *every* such total was gone, which the next certification falsified in
a paragraph: the numbers describing what that certification itself found are still
here, and have to be, because a finding is not reproducible without them. They are
narrative about a moment, not standing claims about the tree — and the difference
matters only because a reader cannot tell them apart unless the record says which is
which, which is what this sentence now does. That is the third time this release has met this
class — a figure from a script that did not ship, then a repair claim that did not
match the tree, and now two counts that aged in place — and it is the first time
the answer has been to stop writing the number rather than to correct it.

### And a wrong answer, found by building the volume nobody had

Every certification of this release so far has run on one filesystem, and each has
said so in its own limitations. Building the missing one — a case-sensitive APFS
image, which is also a genuinely different *device* from the system temp directory
— confirmed what the design claimed about case-sensitive volumes and then produced
a defect nothing else had reached.

    real git : M file.txt
    boundary : M file.txt
               M payload.sh      <- an executable, reported modified

`_build_view` hardlinks each of the subject's files into the constructed view,
because a link copies no content. `os.link` fails with `EXDEV` when the subject and
the scratch directory are on different filesystems, and the fallback was
`shutil.copyfile`, which copies **content only**. The executable arrived in the view
as `644`, Git compared it with `100755` in the index, and a governed `status`
reported a file modified that real Git said nothing about.

This release's own design record calls a wrong answer at exit 0 the worst outcome
the boundary can produce, and this one required no hostility whatever: only a
subject that does not live on the same volume as the system temp directory — an
external disk, a network mount, a second volume, a container bind mount. It needed
a nested repository too, since that is what makes the build construct a view at
all, which is why every fixture on one filesystem agreed and this one did not.

The fallback now copies the metadata as well as the bytes, so it produces the same
file the link would have. `test_a_view_built_across_a_filesystem_boundary_keeps_every_mode`
pins it without requiring two filesystems: it makes `os.link` raise `EXDEV` so the
fallback runs anywhere, and it fails when the metadata copy is removed. Verified on
the real cross-device volume afterwards, where `status --porcelain`,
`status --porcelain -uall`, `diff --stat` and `ls-files -s` now all match real Git.

**What it says about the certifications, and about this record.** Three independent
readings passed over this code without finding it, and none of them was careless —
the defect is invisible unless the subject sits on another device, and each reader
recorded that it had tested one filesystem only. A limitation honestly disclosed is
still a limitation: it says where to look next, and looking there is what found
this. The same disclosure still stands for Windows, for `core.symlinks=false` and
for network transports, and those remain **unestablished** rather than passing.

### And the certification after that one found the view is not the tree

A third certification of this line returned **NOT_READY** with a code blocker that
matters more than anything else this record describes, because it is a wrong answer
and it was reachable without any hostility at all.

**A committed symlink arrived in the constructed view as an ordinary file.**
`os.link` follows symlinks by default, so it never fails on one — it succeeds, and
hard-links the *target*. Git then compared mode `100644` against the `120000` in
the index and a governed `status` reported `T` for a typechange the subject does not
have, while `diff` invented a deleted file mode. What makes this worth stating
plainly: the symlink handling was already written, and it sat inside an
`except OSError` that the one case needing it could never reach. A branch guarded by
a condition that cannot occur is not a repair; it is a comment that looks like one.
The check now runs first, deciding by what the entry *is* before anything is
attempted, which is the same order the `.git` name check uses and for the same reason.

**And a directory the walk could not read became a smaller tree.** `os.walk`
swallows an unreadable directory and simply yields less, so the view was missing a
subtree and Git answered confidently about what was left: a tracked file under it
came back reported as **deleted** while real Git said nothing. An inability to look
had turned into a definite negative, which is this pack's own `UNKNOWN coerced into
an answer` class arriving through a filesystem walk rather than through a
comparison. Both walks now refuse by name instead, and the oracle carries the bound
as well as the property — it checks that the same subject, once readable, still
answers exactly as real Git, so the repair cannot be a blanket refusal.

Both were reproduced before repair and both oracles were run against the defect they
name and against each other: each fails on its own and passes the other.

**Three certifications of this line have now each found something the previous one
did not**, and the pattern is worth naming. The first found records that contradicted
the tree. The second found records that had aged between being written and being
committed. The third found the mechanism itself answering wrongly on inputs no
earlier reader had built — symlinks, an unreadable directory — because each reader
attacked what the previous one had not. That is what independent reading buys, and
it is the argument for spending it again rather than for concluding that a clean
verdict was ever near.

### A disclosed over-acceptance, adjudicated rather than repaired

The same certification found that a directory whose `.git` contains only a `HEAD`
file is **answered about** by this boundary where real Git refuses it as "not a git
repository". The polarity is the opposite of the one already recorded above: this
release refuses a corrupted ref store where Git limps on, and here it proceeds where
Git stops. It is disclosed rather than repaired because repairing it means deciding
what a repository *is* — Git's own answer is `HEAD` plus `objects/` plus `refs/` —
and adding that triple is another enumeration of the kind this release exists to
remove. Every consumer of this pack lands conservatively on such a subject (the pin
fails, the workspace is not closable), so the exposure is a wrong answer to a
question no shipped caller asks. **Unrepaired, stated, and the first thing a later
release should take up.**

## Not yet done

The independent certifications, and the terminal gates that depend on them.

`AUTH-4` holds the Codex/Astra budget until its weekly reset, and the findings an
independent design reading produced are that reader's own, so their independent
closure must route to the other provider against the implementation rather than
against the prototype. No self-review substitutes for it, and this record does
not treat the repair of those findings as confirmed until it has run.

One thing this line does not satisfy, and the decision that was taken about it.
Three of its own commit messages — `154be5f`, `fb2f450` and `f773db9` — predate the
discipline the rest of the line follows and do not conform to
`tools/commit_gate.py`. Repairing a commit message rewrites the commit, and
`docs/RP2.5.0-DESIGN-A2-nested-and-ambient.md` is frozen at one of the revisions
that would move, so the repair trades the commit-range gate for the
design-provenance gate in exactly the clean-room clone where the old object does
not exist.

**The founder took `policy/hitl-matrix.md` row 9 and accepted it as a limitation
rather than authorising the rewrite**, on the ground that rewriting would dangle a
frozen design record's stated base revision and cost the reconstructible ancestry
that the clean-room gate exists to prove. So the history stands as it is, and:

    python3 tools/commit_gate.py --range HEAD --baseline 9d906ce --repo .

REPORTS NINE VIOLATIONS OVER THOSE THREE COMMITS AND EXITS NON-ZERO. That raw
result is the truth and is left raw. It is not reinterpreted as a pass, no
exemption is added to `commit_gate.py`, and nothing here weakens the checker: **a
raw non-zero checker result is never rewritten as a pass.** A reader who runs the
command sees the same nine violations this record admits to.

Run with `--default-terms .` — the vocabulary a consuming PROJECT declares rather
than the one this pack self-applies — the same command reports FIVE non-conforming
commits, because `beb81d8` and `710fc54` use a word that vocabulary makes private.
Three is the number under `NO_PRIVATE_TERMS`, which is the contract this pack's own
`validate_range` tests use and therefore the one its own history is judged by. Both
numbers are recorded so neither is a surprise.
