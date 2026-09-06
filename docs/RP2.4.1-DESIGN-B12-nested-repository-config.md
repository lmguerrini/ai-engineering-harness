# DESIGN — RP2.4.1: the inspection's subject must be Git's subject

**Change class:** MATERIAL
**Base revision:** 3d94c4d78cd72b01019f8662937337835a013460
**Frozen:** yes

Read by `tools/design_record.py`. This record authorises nothing.

## The reproduced defect

A populated submodule is a second repository. Git applies **its** configuration
when it runs the nested `status` and `diff` that an ordinary superproject read
requires. The inspection lists only the configuration Git applies to the
superproject, so a program declared in the submodule's own config is invisible
to it and runs.

Reproduced against real Git, marker on disk, nine executions in one run:

    git -C sup/sub config filter.x.clean <prog>
    git -C sup/sub config diff.external  <prog>
    git -C sup    config diff.submodule  diff
    -> program_valued_config(sup) == []
    -> whitespace_damage(sup), probe(sup,"status"), probe(sup,"diff") each ran <prog>
       with GIT_DIR=sup/.git/modules/sub

`whitespace_damage` is what this pack's own `workspace_report` calls, so the
route is reachable through the pack rather than only through a caller.

It also falsifies two statements: `diff.external` is closed as "disabled by
`--no-ext-diff` on every verb that accepts it", which is not true of the nested
diff Git launches itself; and limitation 10 says a clean filter falls to the
standing rule and refuses, which is not true when the filter is a submodule's.

## The recurring root cause

This is the fifth defect in this area and the same shape as the first:
**the inspection's subject is narrower than Git's subject.**

| Found | The subject the inspection used | The subject Git used |
|---|---|---|
| B5 | `config` only | `config` and `config.worktree` |
| B8 | the general `protocol.allow` | the specific `protocol.<name>.allow` |
| B9 | a lower-cased key name | the verbatim subsection |
| B12 | the superproject | the superproject and every populated submodule |

So the rule is stated once, here, rather than patched again: whatever
configuration Git will apply to this read is what has to be inspected.

## The mechanism

Gitlinks are already in the index, so the submodule paths cost one
`ls-files --stage -z`. Each populated one is inspected by the same function that
inspects the superproject, and its findings are reported against its path.
Recursion is bounded and cycle-guarded; exceeding the bound refuses rather than
returning what it managed to look at, because a partial inspection is not a
clean one.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Suppress the nested processes with `diff.ignoreSubmodules=all` / `diff.submodule=short` at command scope | REJECTED | Closes the route by making the reports lie. A submodule change would stop appearing in `status` and `diff`, so the pack's own workspace reporting would call a dirty tree clean — trading repository-chosen execution for a false report, which is the worse of the two |
| 2 | Inspect only when the caller asks for a submodule-aware verb | REJECTED | The reproduced route is `whitespace_damage` → `diff --check`, an ordinary verb nobody would flag as submodule-aware. Choosing which verbs recurse is the same guess about Git's behaviour that produced the four previous defects |
| 3 | Inspect every populated submodule under the rule already applied to the superproject | SELECTED | The rule does not change; only the set of repositories it is applied to, which becomes the set Git actually reads. It refuses exactly what it already refuses one directory up, so nothing new is decided — and the refusal names the submodule, so the operator can see which repository is responsible |

## The cost, stated rather than discovered

A superproject whose submodule declares a program-valued key is refused, where
before it was read. That is the same treatment the superproject already gets for
the same key, and limitation 10 already records the Git-LFS shape as the common
one — but in a submodule it is now newly reachable. No consumer of this pack
uses submodules (checked: no `.gitmodules` in any of the five projects), so the
cost is disclosed rather than incurred. It belongs in `known_limitations`.

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | A submodule is listed in the index but not populated | It has no configuration to apply, so Git reads none; the walk skips what is not there and an oracle covers the unpopulated case |
| 2 | Submodules nest, or a link cycles | Bounded depth and a visited set of resolved paths; exceeding the bound REFUSES rather than reporting what it saw |
| 3 | The cost of a config read per submodule per governed read | Gitlinks come from one `ls-files`, and a repository with no submodules pays one extra process; an oracle pins that an ordinary repository still reads |
| 4 | A submodule's configuration is unreadable | The same handler as the superproject's: an unreadable configuration is not an empty one |

## Authority boundaries

Reports and refuses. It opens nothing and weakens no row of
`policy/hitl-matrix.md`. Behaviour that previously executed a repository's own
program and now refuses is the repair, not an incompatibility.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O1 | NEGATIVE | a program declared in a submodule's config is seen and refused | tools/tests/test_gitread.py::test_a_program_declared_in_a_submodule_is_seen_and_refused |
| O2 | NEGATIVE | it does not run through the pack's own workspace path | tools/tests/test_gitread.py::test_a_submodule_program_does_not_run_through_whitespace_damage |
| O3 | ACCEPTANCE | a superproject whose submodule declares nothing still reads | tools/tests/test_gitread.py::test_a_superproject_with_an_ordinary_submodule_still_reads |
| O4 | ACCEPTANCE | an index gitlink with no populated directory still reads | tools/tests/test_gitread.py::test_an_unpopulated_submodule_is_not_a_finding |
| O5 | MUTATION | not walking the gitlinks restores the reproduced execution and must fail O1 and O2 | tools/tests/test_gitread.py::test_a_submodule_program_does_not_run_through_whitespace_damage |
| O6 | MUTATION | reporting the submodule's key without its path must fail O1, which names the path | tools/tests/test_gitread.py::test_a_program_declared_in_a_submodule_is_seen_and_refused |
