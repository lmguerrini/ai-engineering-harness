# DESIGN — RP2.5.0: four sources, and an answer that says what was not in force

**Change class:** MATERIAL
**Base revision:** 05c4c1528622ebaf7282a6b9d91dd2492b6eae33
**Frozen:** yes

## What two independent design readings falsified

A3 said the build OWNS a configuration key or CARRIES it, and refuses what it can do
neither with. Two blind readings — one same-family, one cross-vendor — returned
DESIGN_BLOCKED independently and converged on the same centre.

**The declared universe was never established.** A3 took `git config --list` as the
declaration and claimed "the same rule" for state that is not configuration while
naming no enumerator for it. Measured, the unobservable half is the larger one: of
twelve corpus rows only six are configuration keys, and the reader found a reflog
answering empty at exit 0 in every real repository that has one — all ninety-six git
directories on this machine do.

**`owned` was a label, not a derivation.** In the cross-vendor reader's words:
*generating the set of output keys does not generate the proof that a subject key may
be replaced or ignored.* A3's own oracle could not tell an owned value from a carried
one. And an inactive `config.worktree` — absent from Git's own configuration listing
— is parsed by the builder anyway and changes the answer, so the build reads a file
**Git does not**, which no inventory of Git's declarations could ever see.

**And A3 reversed a promise it claimed to leave standing.** A1's authorised behaviour
change is that "a repository that merely declares program-valued configuration is now
**read**, not refused — refusals get strictly rarer", achieved by making the subject's
configuration *unreachable*. A3 made a subject configuration inventory drive a
refusal. Measured, literal A3 refuses ninety-six of ninety-six real repositories.

## The tension, named, because it is the actual result

A1 makes the subject's configuration unreachable so that nothing it declares can
execute. Answer fidelity requires the subject's configuration to reach Git, or the
answers differ. **Both cannot hold.** Carrying keys verbatim restores execution;
refusing on keys reverses A1 and refuses everything; partitioning keys by whether
they *can* execute is the dangerous-key enumeration 2.4.1 died of.

So the resolution is not another partition of the same question. **It is to stop
claiming the thing that cannot be true, and to make what is true observable.**

## The mechanism

**A governed read does not claim to reproduce what Git says in the operator's
situation. It answers about the repository under the harness's declared
configuration, and it reports what of the subject's own configuration was not in
force.** A caller that requires Git-identical semantics checks that report is empty.
Nothing is silently wrong, because the divergence travels with the answer.

**Four sources, and the set of sources is closed.** Everything that can shape a
governed answer arrives through exactly one of:

| source | who declares it | what the build does |
|---|---|---|
| configuration | Git's own parse of the subject's files | the harness's configuration stands; the subject's non-storage keys are reported not-in-force |
| git-directory files | the directory listing | owns `config`, `config.worktree` and `hooks/`; carries everything else |
| working-tree files | A2's view | unchanged |
| the environment | the build | owned wholesale |

A post-condition checks every source is accounted for. That is the total source model
A3 lacked, and it is closed because there are four kinds, not because a list of names
is complete.

**Files need no list of ours.** Only a configuration file and a hook can name a
program, so those three names are owned — and the same three inside `modules/` and
`worktrees/`, because those are the same files for a repository Git opens. Everything
else in a git directory is data, and **data cannot execute without configuration
naming a program**. The release already argues exactly this for four files it
hand-picked; A4's move is to notice the argument is true of all of them, which turns
an allowlist into a three-name ownership rule and dissolves the reflog, `HEAD@{1}`,
`MERGE_HEAD`, `info/grafts`, the per-worktree refs and the nested reftable gitlink
without listing any of them.

**Provenance is disjoint and recorded.** Every value in the built configuration is
either harness-origin — a constant or a policy override — or subject-origin, carried
because it describes how the store is encoded. The build records which, so "owned"
and "carried" are facts about where a value came from rather than labels attached to
it. This is what A3's oracle could not distinguish.

**Configuration is read through Git, never through us.** A file Git does not read is
a file the build does not read, which is what makes the inactive `config.worktree`
disappear as a case rather than as an entry.

**Nothing new is refused.** A1's promise stands unchanged: a repository that merely
declares program-valued configuration is read. The not-in-force report replaces the
refusal A3 proposed, so refusals get rarer rather than universal.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Extend `CARRIED_DATA` per divergence | REJECTED | The treadmill in its third generation; six readings, sixteen members, no exhaustion |
| 2 | A3: own-or-refuse over `config --list` | REJECTED | Blind over the larger half of its scope, `owned` underived, and it refuses 96 of 96 real repositories while reversing A1's authorised behaviour change |
| 3 | Carry every key verbatim behind a process barrier | REJECTED | The barrier exists (`RLIMIT_NPROC=0`, Job objects) but fails open at exit 0: a clean filter degrades to a successful read with the wrong content |
| 4 | Four declared sources; files by ownership, configuration by standing policy, with the not-in-force set reported | SELECTED | The source set is closed by kind rather than by name; files need no list; nothing new is refused; and the residual divergence is carried in the answer instead of being silent |
| 5 | Answer from the subject's real configuration and detect divergence afterwards | REJECTED as a barrier | Detection after the answer is not prevention. Retained as the ORACLE: the corpus is that detector, and it falsified A1 and A3 in turn |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | A fifth source appears that shapes an answer | Stated as the design's falsifying condition. The corpus compares answers rather than sources, so a fifth surfaces as a divergence even though the model did not predict it — which is how the environment was found |
| 2 | The not-in-force report is computed but no caller reads it | O-A4-3 requires the report to be part of the answer, and a caller asking for Git-identical semantics to receive a refusal when it is non-empty |
| 3 | Git gains a fourth kind of file that names a program | O-A4-2 measures execution across every file the listing carries, with a marker and a positive control |
| 4 | A storage descriptor is carried that also changes semantics | Provenance is recorded per value, so the carried set is enumerable and testable against real Git rather than trusted |
| 5 | The environment is owned incompletely | Measured: `TZ` alone changes `log --date=local` by nine hours on the same commit. O-A4-6 pins the environment the child receives |

## Authority boundaries

A4 supersedes A3 entirely and A1's fail-closed sentence. It restores A1's authorised
behaviour change, which A3 had reversed, and widens nothing that is permitted. It
narrows a CLAIM rather than a capability: the release stops asserting Git-identical
answers under the operator's configuration and starts reporting what was not in
force. That is a consumer-visible change and is recorded as one. No founder authority
is required beyond the superseding-record path already authorised.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O-A4-1 | ACCEPTANCE | every row of the divergence corpus either answers exactly as real Git or reports the subject setting that was not in force; the corpus exits 0 | docs/acceptance/rp2.5.0-divergence.py |
| O-A4-2 | NEGATIVE | no file carried from the git directory causes a program to run, measured with a marker against a positive control | tools/tests/test_gitread.py::test_no_carried_file_executes_a_program |
| O-A4-3 | ACCEPTANCE | the not-in-force set travels with the answer, and a caller requiring Git-identical semantics is refused when it is non-empty | tools/tests/test_gitread.py::test_an_answer_reports_what_was_not_in_force |
| O-A4-4 | ACCEPTANCE | every value in the built configuration has recorded provenance, harness-origin or subject-origin, and the two sets are disjoint | tools/tests/test_gitread.py::test_every_built_value_has_disjoint_provenance |
| O-A4-5 | ACCEPTANCE | configuration is read through Git's own parse, so a file Git does not read is not read: an inactive config.worktree changes no answer | tools/tests/test_gitread.py::test_a_file_git_does_not_read_is_not_read |
| O-A4-6 | ACCEPTANCE | the environment the child receives is the build's: TZ does not change a governed answer | tools/tests/test_gitread.py::test_the_environment_does_not_shape_a_governed_answer |
| O-A4-7 | ACCEPTANCE | the four sources are accounted for by a post-condition, and a source left unaccounted fails the build | tools/tests/test_gitread.py::test_every_source_is_accounted_for |
| O-A4-8 | NEGATIVE | A1's behaviour change stands: a repository merely declaring program-valued configuration is read, not refused | tools/tests/test_gitread.py::test_a_repository_declaring_a_program_is_still_read |
| O-A4-9 | MUTATION | removing a name from the file-ownership rule must fail O-A4-2; dropping the not-in-force report must fail O-A4-3; reading configuration with the module's own parser must fail O-A4-5 | tools/tests/test_gitread.py::test_no_carried_file_executes_a_program |

## What this does not settle

Whether four sources are all of them. Whether a caller will read the not-in-force
report rather than ignore it — the design can require it to be present and cannot
require it to be understood. Whether the three owned file names hold for a future
Git. Both readings that produced A4 ran on one machine and one Git build, and both
said so about their own surveys.
