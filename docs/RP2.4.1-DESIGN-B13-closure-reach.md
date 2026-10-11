# DESIGN — RP2.4.1: a closure holds only where its mechanism reaches

**Change class:** MATERIAL
**Base revision:** 60d245fea45ea44800ba5220e192c78a653dea2c
**Frozen:** yes

Read by `tools/design_record.py`. This record authorises nothing.

## Two reproduced defects, both inside the previous cycle's repair

**B13a — a closure that rests on a command-line flag does not cover a process
Git launches itself.** `CLOSED_PROGRAM_KEYS` excuses `diff.external`,
`diff.*.command` and `diff.*.textconv` because this module passes
`--no-ext-diff --no-textconv`. Those flags are on the OUTER command line. The
nested `diff` that `diff.submodule=diff` makes Git run does not inherit them, so
the submodule walk added last cycle applied the same closure table one directory
down where its mechanism does not reach. Reproduced: `diff.external` declared in
a submodule ran, inspection returned `[]`, `probe(sup,"diff")` returned ok.

**B13b — the gitlink listing swallowed its own refusal, including a timeout.**
The walk read the index through `except GitRefusal: return []`, so an index read
that timed out reported "no submodules" and the governed read proceeded. An
independent certification reproduced execution of a submodule's `filter.x.clean`
at 35 ms and 40 ms deadlines against a 90,000-entry index, with the same
repository correctly refused at a long deadline.

**B13b is limitation 14 written again.** That entry records this module wrapping
the worktree-configuration read in `except GitRefusal: pass`, reasoning it
errors when the extension is off — and swallowing the timeout with it. The same
rationalisation, in a new function, one cycle after documenting it.

## The rule, stated once

A closure is a claim that Git will not run the program **on every path the
closure covers**. Two things decide the reach of a closure's mechanism:

| Mechanism | Reaches a process Git launches itself? |
|---|---|
| the standing configuration, passed as `GIT_CONFIG_*` | YES — inherited by nested Git processes, confirmed by a marker reporting `GIT_CONFIG_COUNT=20` from inside a submodule |
| a command-line flag on this module's invocation | NO — the nested command line is Git's, not this module's |

So a closure resting on a flag is closed for the repository the flag was passed
to, and open for every nested repository. And a check that cannot read its
subject has not cleared it — for the index exactly as for the configuration.

## The mechanism

`FLAG_BASED_CLOSURES` names the entries whose reason rests on a command-line
flag. When the inspection is applied to a nested repository, those entries are
dropped from the closure table, exactly as `CONDITIONAL_CLOSURES` entries are
dropped when their condition fails. The gitlink listing stops catching its own
refusal and answers through the handler shape this module already proved: a
timeout is the caller's, a path that is not a repository is not this check's
business, and an unreadable index is a finding.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Pass `--no-ext-diff --no-textconv` into the nested process too | REJECTED | There is no supported way to put flags on a command line Git builds for itself; `submodule.recurse=false` was already checked and does not govern this path. A repair that cannot be made to hold is not one |
| 2 | Set `diff.external` and the textconv keys empty in the standing configuration, so the neutralisation is inherited | REJECTED | The module already recorded why it does not: `core.sshCommand = ""` made Git try to run the empty string and die with `cannot run :`, a non-functional postcondition wearing a different error. Limitation 10 and the `diff.external` entry both say the key is deliberately absent for that reason |
| 3 | Drop flag-based closures when inspecting a nested repository, and stop swallowing the index refusal | SELECTED | Applies the rule the closure table already states, to the paths where its mechanism actually reaches. It refuses a submodule declaring a diff helper — the same treatment the superproject gets — and it costs nothing for a repository with no submodules. The swallow is removed rather than narrowed, which is how the same defect was closed the first time |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | A flag-based closure is added later without being listed | An oracle asserts every closure whose stated reason mentions a flag is listed in `FLAG_BASED_CLOSURES` |
| 2 | The nested rule is applied to the outer repository, refusing ordinary diffs | An acceptance oracle keeps a superproject declaring `diff.external` in its OWN config reading, since the flags do reach there |
| 3 | The index read refuses a path that is not a repository | The same filesystem test the configuration handler uses, for the same reason: the caller's verb owns that refusal |
| 4 | A timeout is reported as no submodules | It is re-raised as the caller's refusal, and an oracle drives the deadline |

## Authority boundaries

Reports and refuses; opens nothing, weakens no row of `policy/hitl-matrix.md`.
Behaviour that previously executed a repository's own program and now refuses is
the repair.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O1 | NEGATIVE | a diff helper declared in a submodule is seen and does not run | tools/tests/test_gitread.py::test_a_diff_helper_in_a_submodule_is_not_closed_by_an_outer_flag |
| O2 | ACCEPTANCE | the same key in the superproject's own config still reads, because the flags reach there | tools/tests/test_gitread.py::test_a_diff_helper_in_the_outer_repository_stays_closed |
| O3 | NEGATIVE | an index read that times out refuses instead of reporting no submodules | tools/tests/test_gitread.py::test_an_index_listing_timeout_is_the_callers_refusal |
| O4 | NEGATIVE | an unreadable index is a finding, not an empty one | tools/tests/test_gitread.py::test_an_unreadable_index_is_refused_not_read_as_no_submodules |
| O5 | ACCEPTANCE | a path that is not a repository is left to the caller's own verb | tools/tests/test_gitread.py::test_a_path_that_is_not_a_repository_is_still_the_callers_own_refusal |
| O6 | STRUCTURAL | every flag-justified closure is declared as one | tools/tests/test_gitread.py::test_every_flag_based_closure_is_declared |
| O7 | MUTATION | restoring the swallow, and keeping flag-based closures for nested repositories, must fail O3 and O1 | tools/tests/test_gitread.py::test_a_diff_helper_in_a_submodule_is_not_closed_by_an_outer_flag |
