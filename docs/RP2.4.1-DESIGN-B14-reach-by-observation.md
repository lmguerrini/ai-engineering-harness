# DESIGN — RP2.4.1: reach is a fact about Git, not a description of this module

**Change class:** MATERIAL
**Base revision:** 3dfaf743c371b53a75aeee62ca69a2e82d3831cf
**Frozen:** yes

Read by `tools/design_record.py`. This record authorises nothing.

## Two reproduced defects, one cause

**B14a — a flag-based closure was asserted for a verb the flag is not passed to.**
`diff.*.textconv` is excused as "disabled by `--no-textconv`". That flag is
added only for `EXTERNAL_PROGRAM_VERBS` — `diff`, `diff-index`, `diff-tree`,
`log`, `show`. `git status -v` prints a patch and applies textconv drivers, and
**`status` does not accept `--no-textconv` at all**, so the closure's mechanism
cannot reach that verb by any spelling. Reproduced: the driver ran twice under
`probe(repo, "status", "-v")` while the inspection reported `[]`.

**B14b — the nested walk enumerated the index; Git opens the working tree.**
`_gitlink_paths` lists mode-160000 entries. Git's inline submodule diff opens
`<path>/.git` **from the working tree** for a gitlink change in the commit being
shown, whether or not that path is still in the index. A populated checkout left
at a former submodule path — which `git rm` of a submodule leaves behind on
every other machine — is therefore opened by Git and never inspected. Reproduced:
`diff.external` in that directory ran under `probe(sup, "show", <rev>)` with
`_gitlink_paths` returning `[]`.

## The cause, stated once

Both are the same mistake in the same place: **this module described its own
behaviour and called that the reach.** The flags it passes became "the flag is
passed"; the index it reads became "these are the nested repositories". Reach is
a fact about what Git does, and both facts were available to be checked.

This is the ninth defect of this family. The previous eight each closed one path;
this record closes the two ways reach itself was being decided.

## The mechanism

**Closures by verb.** A flag-based closure is closed for a verb only if the flag
is actually on that verb's command line. `FLAG_BASED_CLOSURES` already names the
entries; they are now dropped unless the verb is one the flags are added for, and
dropped for nested repositories as before.

**The walk by what Git can open.** A nested repository is a directory containing
`.git` in the working tree. That set strictly contains the populated index
gitlinks — an unpopulated gitlink has no configuration to apply — so the index
listing is replaced rather than supplemented. Descent stops at each nested
repository (its own nesting is the recursion's business) and inside the
repository's own `.git`.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Add `status` to the verbs that receive `--no-textconv` | REJECTED | `status` does not accept the flag; Git exits with a usage error. A closure cannot be repaired by passing a flag that does not exist |
| 2 | Enumerate the paths whose gitlink changed in the commits being read, and walk those as well as the index | REJECTED | Reintroduces the mistake at one remove: it predicts which nested repositories Git will open from the arguments, and `show`, `log -p`, `diff` and a `status` with a submodule each reach a different set. The filesystem already answers the question without predicting anything |
| 3 | Decide closure by verb, and the walk by the presence of `.git` in the working tree | SELECTED | Each replaces a description of this module with an observation. The closure is closed exactly where its flag is on the command line, which is checkable in one place; the walk covers every repository Git can open, including ones no longer in the index, without predicting which it will choose to |

## The cost, stated rather than discovered

A working-tree walk runs per governed read. It stops at every nested repository
and at the repository's own `.git`, so it is bounded by directory count rather
than file count, but it is not free on a very large tree. And `status`, `log`
and the diff verbs now refuse a repository declaring a textconv driver where
`status` previously read it — the same treatment those keys already get on the
diff verbs.

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | The walk descends into a huge tree on every read | Descent stops at each nested repository and at `.git`; an oracle pins that an ordinary repository still reads, and the pack's own suite is the standing cost measurement |
| 2 | A symlinked directory makes the walk loop | Directory symlinks are not followed, and the resolved-path set still guards the recursion |
| 3 | An unreadable directory aborts the walk | Traversal errors are refused, not skipped: a walk that could not look is not a walk that found nothing |
| 4 | A verb gains the flags later and the closure is not re-opened | The closure consults the same set the flags are added from, so there is one place, not two |

## Authority boundaries

Reports and refuses; opens nothing, weakens no row of `policy/hitl-matrix.md`.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O1 | NEGATIVE | a textconv driver is refused on a verb that never receives the flag | tools/tests/test_gitread.py::test_a_textconv_driver_is_refused_on_a_verb_the_flag_never_reaches |
| O2 | ACCEPTANCE | the same driver still reads on the verbs the flag is passed to | tools/tests/test_gitread.py::test_a_textconv_driver_stays_closed_where_the_flag_is_passed |
| O3 | NEGATIVE | a nested repository absent from the index is inspected | tools/tests/test_gitread.py::test_a_nested_repository_not_in_the_index_is_still_inspected |
| O4 | ACCEPTANCE | an ordinary repository with no nested repository still reads | tools/tests/test_gitread.py::test_a_superproject_with_an_ordinary_submodule_still_reads |
| O5 | NEGATIVE | a walk that cannot read a directory refuses | tools/tests/test_gitread.py::test_an_unwalkable_directory_is_refused_not_read_as_no_nested_repository |
| O6 | MUTATION | restoring the index-only walk must fail O3; restoring the verb-blind closure must fail O1 | tools/tests/test_gitread.py::test_a_nested_repository_not_in_the_index_is_still_inspected |
