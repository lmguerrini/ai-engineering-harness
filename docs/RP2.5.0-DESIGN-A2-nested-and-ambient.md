# DESIGN — RP2.5.0: the name decides, and ambient files stop existing

**Change class:** MATERIAL
**Base revision:** 57767a200b5acdc0aba3ca8d31d26186d649d893
**Frozen:** yes

Read by `tools/design_record.py`. This record authorises nothing.
It extends `RP2.5.0-DESIGN-A1-sterile-execution.md`, which stands as frozen; this
record says what an independent reading falsified in it and what replaced that.

## What the independent design reading falsified

`RP2.5.0-DESIGN-A1` was read before implementation by an independent falsifier
that did not write it. Verdict: **DESIGN_BLOCKED**, one release blocker, two
non-blocking findings. All three were reproduced here before being accepted, and
the blocker was reproduced with the reader's own script, unmodified.

**Blocker — a nested `.git` that is a *symlink to a directory* executed the
subject's program.** The walk classified it as an ordinary directory symlink and
reproduced it into the sterile view verbatim, so Git followed it to the subject's
real git directory and ran the filter named there. Measured: 3 marker bytes on a
plain `git status --porcelain`, and `GIT_TRACE2_EVENT` recorded the subject's
program as a child process — falsifying A1's oracles O2 and O7 by observation.

The reader's diagnosis is the part that matters, and it is correct:

> Config-source safety was moved off the enumeration treadmill; nested-repository
> safety was left on it.

A1 claimed nested repositories were handled "not by enumeration". They were not.
The walk enumerated the *layouts* a nested repository can have — a directory, a
gitlink file — and a layout it had not enumerated was **fail-open**. That is the
class the recurrence map says does not converge, reproduced inside the design
built to end it. It is repaired by changing the mechanism's polarity, not by
adding symlinks to the list of layouts.

**Non-blocking 1 — ambient operator files were still read.** `GIT_CONFIG_GLOBAL`
redirects the global *config* file and nothing else, so Git still read the
operator's `$XDG_CONFIG_HOME/git/ignore` and `git/attributes`. A governed
`status` silently suppressed an untracked file because of one — and `git config
--show-scope`, which is A1's own invariant check, never lists those files, so the
check could not see the source. Not subject-controlled and not an execution
vector, but for a pack whose job is finding what a repository is carrying, an
answer that silently omits a file is the wrong answer.

**Non-blocking 2 — `core.autocrlf` was not carried**, so a clean CRLF working
tree produced a full spurious diff. Not execution; a wrong answer.

## The mechanism

**The name decides, and never the type.** `.git` is the only name Git opens a
repository from in a working tree; the other way in is `GIT_DIR`, which is ours.
So the view is built by withholding *every* entry named `.git`, whatever kind of
thing it is, and rebuilding it as a sterile directory. A nested repository this
build cannot rebuild — a dangling symlink, an empty file, a FIFO — **refuses the
read**. The incompleteness that remains is therefore a refusal, not an execution.

**The loop is an argument; the post-condition is the check.** After the view is
built, it is walked again, and every entry named `.git` in it must resolve inside
this build's own scratch directory. If one reaches the view by a route nobody
thought of, the read refuses rather than running what is behind it. A1 had no
such check: it trusted the loop that built the view.

**Ambient files stop existing rather than being neutralised one key at a time.**
`HOME` and `XDG_CONFIG_HOME` point at an empty directory this build owns, so
every file Git derives from the operator's home — ignore, attributes, netrc, and
whatever a later Git adds — is absent by construction. Naming
`core.excludesFile` and `core.attributesFile` would have closed the two files the
reader found and waited for the third.

**Content-encoding descriptors are carried** (`core.autocrlf`, `core.eol`), and a
symbolic-ref chain is followed when resolving HEAD as data, because a chain is
legal and refusing it was an availability loss with no safety gain.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Add the symlink case to the layouts the walk recognises | REJECTED | It is the 2.4.1 move exactly: one more entry in an open list of layouts, still fail-open when the next one is missed. The reader's finding is that the list exists, not that it is short |
| 2 | Refuse any working tree containing a nested repository | REJECTED | Over-refusal, which is the same defect in the other direction — it is what B15b did to this pack's own `workspace_report`, and ignored dependency checkouts are ordinary project contents |
| 3 | Decide by the NAME `.git`, rebuild every one, refuse what cannot be rebuilt, and verify the finished view by looking | SELECTED | The name is fixed by Git rather than open-ended, so there is no list to keep complete; and both remaining failure modes — a layout that cannot be rebuilt, and a route nobody predicted — end in a refusal instead of an execution |
| 4 | Name `core.excludesFile` and `core.attributesFile` in the sterile config | REJECTED | Closes the two ambient files that were found and none of the ones that were not. Pointing `HOME` at an empty directory removes the class |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | Git gains a second name it opens repositories from | The post-condition walk refuses on any `.git` resolving outside the build; a new name would defeat both mechanisms, so it is stated as the design's falsifying condition rather than hidden |
| 2 | A nested repository is unbuildable and the read proceeds anyway | Rebuild failure raises a refusal naming the path; measured on a dangling symlink, an empty file and a FIFO |
| 3 | The post-condition passes because it walked nothing | It is a walk of the same tree the read uses, and O14 asserts it refuses on a planted foreign `.git` |
| 4 | An ambient file this design did not consider shapes an answer | `HOME` and `XDG_CONFIG_HOME` are an empty directory, so the file is absent rather than overridden |
| 5 | A content-encoding key is not carried and the answer differs from real Git | O10's differential matrix compares against real Git; incompleteness here is an answer difference, never an execution |
| 6 | The matrix looks conclusive while proving little | Rows without a positive control are recorded as such: of thirteen spellings, three make real Git execute (9, 12 and 9 marker bytes) and the rest are constructions real Git does not run a program for |

## Authority boundaries

Unchanged from A1: reports and refuses, opens nothing, weakens no row of
`policy/hitl-matrix.md`. This record widens what is refused — an unbuildable
nested repository, and a view containing a `.git` this build did not make — and
widens nothing that is permitted.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O12 | NEGATIVE | no spelling of a nested `.git` executes the subject's program — directory, gitlink file relative and absolute, symlink to directory, symlink to gitlink file, symlink out of the tree, symlink to the superproject, at depth, inside an ignored directory, under a symlinked directory | tools/tests/test_gitread.py::test_no_spelling_of_a_nested_git_executes_the_subjects_program |
| O13 | NEGATIVE | a nested repository that cannot be rebuilt sterile refuses the read and names the path | tools/tests/test_gitread.py::test_a_nested_repository_that_cannot_be_rebuilt_refuses_the_read |
| O14 | NEGATIVE | a `.git` reaching the finished view from outside the build refuses, even if the loop that built it did not notice | tools/tests/test_gitread.py::test_a_foreign_git_in_the_view_refuses_the_read |
| O15 | ACCEPTANCE | an operator's global ignore and attributes files do not shape a governed answer | tools/tests/test_gitread.py::test_an_operators_home_does_not_shape_a_governed_answer |
| O16 | ACCEPTANCE | a CRLF working tree, an unborn branch, a detached HEAD, a symbolic-ref chain, packed refs and an assume-unchanged entry all answer as real Git answers | tools/tests/test_gitread.py::test_the_sterile_answer_equals_real_gits_answer |
| O17 | MUTATION | restoring the type-based nested detection must fail O12's symlink row; deleting the post-condition must fail O14; restoring the inherited home must fail O15 | tools/tests/test_gitread.py::test_no_spelling_of_a_nested_git_executes_the_subjects_program |

## What this does not settle

The reader may not close its own finding. The independent closure of the blocker
above routes to the other provider, on the implemented code rather than on this
prototype, and this record does not treat the repair as confirmed until then.

Coverage the reading did not have: macOS and one Git build only; no Windows, no
case-sensitive volume, no `core.symlinks=false`, no network transports, no
sparse-checkout, and no measurement of a subject-controlled cost attack.
