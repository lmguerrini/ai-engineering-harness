# DESIGN — RP2.4.1: which configuration a governed read must inspect

**Change class:** MATERIAL
**Base revision:** 8afb462ec78f75b956369d9cabe9d7e810b549f0
**Frozen:** yes

Read by `tools/design_record.py`. This record authorises nothing.

## The failure class, twice in consecutive cycles

The safety inspection must answer one question: **which configuration will Git
actually apply to this read?** Three attempts answered a proxy for it instead.

1.  `--local` alone. Git also applies `config.worktree`, so a declared filter was
    invisible and ran.
2.  A second explicit `--worktree` listing, wrapped in `except GitRefusal: pass`.
    That swallowed a **timeout**, so a slow configuration cleared the inspection.
3.  The same listing, not caught. That refused two configurations Git reads
    perfectly well: an enabled extension with no `config.worktree` file, and an
    explicitly disabled extension in a repository with more than one worktree.

Attempts 2 and 3 are the same mistake in opposite directions — inferring *is
there anything to read* from whether a read failed. The class does not close by
choosing better failure handling, because the question was never a failure
question.

## The mechanism

Ask Git, in one call, for the configuration it will apply, labelled by the scope
it came from, and inspect the scopes belonging to the repository.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Keep the two listings, and classify the second read's failures more finely — file absent, extension off, multiple worktrees, timeout | REJECTED | This is attempt 4 at the same proxy. Each failure string is a Git version's wording, the list is open-ended, and two rounds already produced a defect in each direction. It also cannot state what it covers: an unlisted failure mode falls to whichever branch was written last |
| 2 | Read `config.worktree` from the filesystem and parse it | REJECTED | Reimplementing the configuration format, which is the mistake this release already made once with gitignore and repaired by delegating. It also still needs the extension semantics to know whether Git applies the file at all |
| 3 | One `config --list --name-only --show-scope` call, keeping the `local` and `worktree` scopes | SELECTED | It asks the actual question rather than a proxy. Git decides what it applies and says where each key came from, so the extension, the file's absence, its presence in some worktrees only, and the multiple-worktree rule are all Git's business and never this module's. One call replaces two; no failure needs interpreting; and the repository-only boundary the function already promised becomes a scope filter rather than a flag |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | `--show-scope` unsupported by an older Git | The call fails and the existing handler refuses; a check that cannot read its subject has not cleared it |
| 2 | A scope name changes or is added | Only `local` and `worktree` are kept, so a new scope is ignored rather than silently trusted; a regression test lists what was kept |
| 3 | Global or system configuration appearing in the listing | Filtered out by scope, which is stricter than the previous flag and matches the function's stated boundary |
| 4 | The inspection times out | Unchanged: the existing handler re-raises it as the caller's refusal |

## Authority boundaries

Reports and refuses; it opens nothing and weakens no row of
`policy/hitl-matrix.md`. It may only make a read refuse that previously
proceeded, or proceed where Git itself proceeds — never execute a program.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O1 | NEGATIVE | a worktree-scoped program key is seen and refused | tools/tests/test_gitread.py::test_a_program_declared_in_the_worktree_config_is_seen_and_refused |
| O2 | ACCEPTANCE | an enabled extension with no file reads normally | tools/tests/test_gitread.py::test_an_enabled_extension_with_no_worktree_file_still_reads |
| O3 | ACCEPTANCE | a disabled extension reads normally, with worktrees present | tools/tests/test_gitread.py::test_a_disabled_extension_still_reads_with_several_worktrees |
| O4 | NEGATIVE | a disabled extension's file is not inspected, because Git does not apply it | tools/tests/test_gitread.py::test_a_disabled_extension_hides_nothing_because_git_ignores_it |
| O5 | ACCEPTANCE | only repository scopes are inspected | tools/tests/test_gitread.py::test_only_the_repositorys_own_scopes_are_inspected |
| O6 | MUTATION | dropping the worktree scope fails O1 | tools/tests/test_gitread.py::test_a_program_declared_in_the_worktree_config_is_seen_and_refused |
| O7 | NEGATIVE | a reply this function cannot parse refuses rather than reporting nothing | tools/tests/test_gitread.py::test_an_unparseable_scope_listing_is_refused_not_read_as_empty |

## Correction, recorded after mutation scoring

O7 was not in the frozen list. Mutation scoring of the implemented design showed
that deleting the parity guard changed no test, and that without it a reply
framed differently from `scope, key, scope, key` pairs every second key as a
scope, matches none, and returns `[]` — reporting *nothing found* from an answer
it did not understand. That is this check's own fail-open class arriving through
the parser rather than through a swallowed error, so the guard was kept and the
missing oracle written, rather than the guard being dropped as unreachable.

This is the opposite disposition from the unreachable branch removed in the
preceding cycle, and for a stated reason: that branch was a second handler for a
question another handler already answered, while nothing else checks framing.
