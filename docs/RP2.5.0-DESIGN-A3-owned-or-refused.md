# DESIGN — RP2.5.0: what the build does not own, it refuses

**Change class:** MATERIAL
**Base revision:** 34c8f1209833fe747d12e3faa7db64cbe762a7a7
**Frozen:** yes

## What was falsified, and why it is one thing rather than fifteen

Two independent certifications of `34c8f12` returned NOT_READY with fifteen release
blockers between them. They are not fifteen defects. They are one, and it falsifies
the sentence design A1 rests its safety argument on:

> it is **fail-closed**: the directory is built by adding what a read needs, never by
> removing what it must not have, so anything missed makes a read fail loudly
> instead of running a program.

**The second half is false.** What the build does not reproduce does not fail loudly.
It changes the answer, silently, at exit 0. Measured on ordinary repositories — none
hostile, none naming a program (`docs/acceptance/rp2.5.0-divergence.py`):

| the repository declares | real Git | this boundary |
|---|---|---|
| `status.showUntrackedFiles=no` | (nothing) | `?? "caf\303\251.txt"` |
| `core.quotepath=false` | `?? café.txt` | `?? "caf\303\251.txt"` |
| `core.abbrev=4` | `37e6` | `37e6f5e` |
| `diff.renames=false` | `D a.txt` / `A b.txt` | `R100 a.txt b.txt` |
| `diff.noprefix=true` | `diff --git a.txt a.txt` | `diff --git a/a.txt b/a.txt` |
| a reflog | `git log -g -1` answers | answers **empty**, exit 0 |
| `HEAD@{1}` | resolves | refused |
| `MERGE_HEAD` during a merge | resolves | refused |

Eight ordinary repositories, eight disagreements. A ninth, found by the cross-vendor
reader: a clean nested gitlink to a `reftable` repository is reported ` M module`
where real Git reports nothing, and `diff` invents a `-dirty` subproject line.

**The name for it.** 2.4.1 enumerated DANGEROUS things in order to refuse them, and
its incompleteness was fail-open: a key nobody listed ran somebody's program. 2.5.0
replaced that with enumerating NEEDED things in order to reproduce them —
`CARRIED_DATA` is a four-element tuple and `STORAGE_KEYS` a short one — and *that*
enumeration is open in exactly the same way. The treadmill did not end. It moved
from the refuse side to the copy side, where its incompleteness is quieter and
therefore worse: a missed key used to run a program, and now it returns a wrong
answer that nothing marks as wrong.

## The mechanism

**One question decides everything: does the build OWN this key?**

The build owns a key when it writes that key's value itself, for a stated reason of
safety or location — `GIT_DIR`, the work tree, `HOME` and `XDG_CONFIG_HOME`, the
transport posture, the object-format and ref-storage descriptors it reproduces.
That set is **closed by construction**: it is exactly the set of keys the build
writes, and the build can enumerate it because it wrote it. Nothing predicts it.

Every other key the subject declares is one of two things, and the build does not
guess which:

*   **carried**, when the build reproduces it verbatim, or
*   **not carried**, in which case **the read refuses and names the key.**

There is no third case, and in particular there is no case where a key the build
did not think about silently fails to reach Git.

**Why this is not the same list under another name.** It is a list, and pretending
otherwise would be dishonest. What changes is the polarity of its incompleteness:

*   2.4.1's list was of things to REFUSE. Missing an entry meant a program ran.
    **Incomplete → fail-open.**
*   2.5.0's list was of things to CARRY. Missing an entry meant a wrong answer at
    exit 0. **Incomplete → fail-open, and silent.**
*   A3's list is of things the build OWNS. Missing an entry means the subject
    declares a key the build neither owns nor carries, and the read **refuses by
    name**. **Incomplete → fail-closed, and loud.**

That is the whole of the improvement, and it is worth stating plainly rather than
dressing up: A3 does not abolish enumeration, because no design here can. It makes
the residual enumeration's failure mode a refusal instead of a lie, and it makes
completeness **observable** — the build asks the subject what it declares, compares
that with what it owns and carries, and the remainder is a fact rather than a
prediction.

**The same rule, applied to state that is not configuration.** Refs, reflogs and
pseudo-refs are subject state exactly as configuration is, and the same partition
applies: the build reproduces the subject's ref state, and where it cannot, the read
refuses rather than answering from a smaller repository. `git log -g` answering
empty on a repository that has a reflog is the identical defect wearing different
clothes.

**What is deliberately overridden, and therefore deliberately divergent.** Some
subject configuration is *not* reproduced, on purpose, and A3 requires that each
such key be named with its reason and its consequence — because a divergence a
caller cannot see is the defect regardless of whether it was chosen. The transport
posture, the ambient-file redirections and replace-object handling are overrides,
not omissions, and they are disclosed as divergences rather than left to be found.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Expand `CARRIED_DATA` as each divergence is found | REJECTED | It is the treadmill. Five independent readings produced nine new members of the set and none of them exhausted it; the sixth would produce more. Its incompleteness stays fail-open and silent |
| 2 | Own or refuse: the build carries what it does not own, and refuses what it can carry neither way | SELECTED | Completeness becomes observable rather than predicted, and incompleteness becomes a named refusal rather than a wrong answer. The residual list is the set the build writes, which is closed because the build writes it |
| 3 | Carry the subject's configuration verbatim and prevent execution structurally | REJECTED | There is no portable, config-independent barrier to Git spawning a process. A1 rejected the OS sandbox for the same reason and that reasoning is unchanged: `sandbox-exec` was denied to a reader inside this project and Windows has no equivalent, so the guarantee would be environmental rather than architectural |
| 4 | Answer from the subject directly and detect divergence afterwards | REJECTED as a barrier | Detection after the answer is not prevention, and A1 already settled this shape for execution. Retained as an ORACLE: the divergence corpus is exactly that detector, and it is what falsified A1 |
| 5 | Refuse every repository declaring any key the build does not own | REJECTED | Correct and useless. An ordinary repository declares `remote.*`, `branch.*` and `user.*`; refusing all of them makes the boundary unusable, and 2.4.1 died of over-refusal as much as of under-refusal |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | Over-refusal: a repository declaring an ordinary key the build has no policy for is refused where 2.5.0 answered | The refusal NAMES the key, so the cost is visible and the owned set grows on evidence rather than on guesswork. B15b is the reminder that over-refusal is a real failure and not a safe default, which is why O-A3-6 bounds it |
| 2 | A key is wrongly OWNED when it should have been carried, so its divergence is silent for that key | Every owned key must state its reason and its consequence, and O-A3-4 checks that; the divergence corpus measures answers rather than reading the list, so a wrongly owned key shows up as a row that disagrees |
| 3 | Ref state reproducible in principle but not by this build | It refuses rather than answering from a smaller repository; O-A3-7 pins the reflog case that answered empty at exit 0 |
| 4 | A key shapes an answer without appearing in `config --list` | The partition cannot see it, and this is stated as the design's falsifying condition rather than hidden. O-A3-1 is the detector: it compares answers, not lists, so such a key surfaces as a divergence even though the mechanism did not predict it |
| 5 | The corpus looks conclusive while proving little | Every row is an ORDINARY repository and none names a program, so a row that agrees is evidence about semantics rather than about safety; the count of rows and the count that diverge are both printed by the script rather than transcribed |

## Authority boundaries

A3 supersedes A1's fail-closed claim and nothing else. It does not reopen the
sterile git directory, the name-decides rule for nested repositories, the empty
ambient home, or the refusal of unsupported representations — every one of those
survived independent falsification and A3 preserves them unchanged. No founder
authority is required: this is the same superseding-record path A2 took after an
independent design reading falsified A1, under the authorisation already granted.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O-A3-1 | ACCEPTANCE | every ordinary repository in the divergence corpus either answers exactly as real Git or refuses by name; none answers differently at exit 0 | tools/tests/test_gitread.py::test_an_ordinary_repository_answers_as_real_git_or_refuses |
| O-A3-2 | NEGATIVE | a subject declaring a key the build neither owns nor carries refuses the read, and the refusal names the key | tools/tests/test_gitread.py::test_a_key_the_build_does_not_own_refuses_and_names_itself |
| O-A3-3 | ACCEPTANCE | the owned set is exactly the set of keys the built configuration contains, established by asking Git for that configuration rather than by reading the list | tools/tests/test_gitread.py::test_the_owned_set_is_what_the_build_actually_writes |
| O-A3-4 | ACCEPTANCE | every owned key carries a stated reason, and every deliberate divergence is disclosed in the records | tools/tests/test_release_integrity.py::test_every_owned_key_states_why_it_is_owned |
| O-A3-5 | NEGATIVE | A2 is unchanged: no spelling of a nested `.git` executes anything, the operator's global ignore does not shape an answer, a CRLF tree is clean, an unbuildable nested repository refuses | tools/tests/test_gitread.py::test_no_spelling_of_a_nested_git_executes_the_subjects_program |
| O-A3-6 | ACCEPTANCE | over-refusal is bounded: an ordinary repository declaring `remote.*`, `branch.*` and `user.*` still reads and agrees with real Git | tools/tests/test_gitread.py::test_an_ordinary_repository_with_remotes_and_branches_still_reads |
| O-A3-7 | ACCEPTANCE | a repository with a reflog answers `log -g` as real Git does, or refuses; it does not answer empty | tools/tests/test_gitread.py::test_a_repository_with_a_reflog_does_not_answer_empty |
| O-A3-8 | MUTATION | removing a key from the owned set must fail O-A3-2 rather than produce an answer; removing the unowned-key check must fail O-A3-1; restoring `CARRIED_DATA` as the decision must fail O-A3-1 | tools/tests/test_gitread.py::test_a_key_the_build_does_not_own_refuses_and_names_itself |

## What this does not settle

The residue in failure mode 4. Whether the owned set can be derived rather than
written. Whether Git's own `config --list` is a complete account of what shapes an
answer — A3 assumes it is, and that assumption is the next thing worth attacking.
