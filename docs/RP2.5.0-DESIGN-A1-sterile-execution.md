# DESIGN — RP2.5.0: a read Git cannot be told to execute anything by

**Change class:** MATERIAL
**Base revision:** 262ed9f9392b98fcad365199216dfd1a9b06567a
**Frozen:** yes

Read by `tools/design_record.py`. This record authorises nothing.

Input: `RP2.5.0-RECURRENCE-MAP.md`, which shows fifteen repairs of one boundary
were fifteen corrections to this module's *description* of Git.

## The question the boundary must answer

A governed read asks a repository a question. The repository may have been written
by a worker, an auditor, or a process nobody trusts. Nothing the repository contains
may cause a program of its choosing to run.

2.4.1 answered "which of this repository's settings are dangerous?" — a question
whose answer is an open set. **The invariant below answers a different question,
whose answer is a closed set Git itself reports.**

## The invariant

> **Every configuration source Git consults during a governed read is a file this
> harness created.**

Two properties make it convergent where the 2.4.1 invariant was not:

- **Closed and observable.** Git's configuration sources are files, and Git names
  them: `git config --list --show-origin --show-scope` reports every one. The
  invariant is checked by reading that list and requiring every origin to be under
  a directory the harness built. No key, verb, flag, transport or spelling appears
  in the check, so no future Git addition can invalidate it.
- **Fail-closed.** The sterile directory is built by **adding what a read needs,
  never by removing what it must not have.** Anything not added makes the read
  fail loudly; nothing not removed can execute, because nothing was inherited.
  2.4.1's denylist had the opposite polarity: a missed entry ran a program.

## The mechanism

`GIT_DIR` decides which files are local and worktree configuration. It is chosen by
the caller, not by the subject. So the harness constructs the git directory:

1. **A git directory the harness owns.** A fresh directory containing a config file
   written from a blank slate; the subject's object database attached by
   `objects/info/alternates` (attached, never copied); `HEAD`, `refs/` and
   `packed-refs` copied as plain files by the harness, with no Git involved; the
   index copied, so a refresh writes to ours and never to the subject's.
2. **Storage descriptors, carried deliberately.** `core.*` keys are carried only
   from a small allowlist that describes how the store is *encoded*; every
   `extensions.*` key is carried verbatim, which needs no allowlist because an
   extension changes how Git interprets the **git directory**, and this git
   directory contains only files this build created. An extension naming a store
   the build did not import makes the read fail — measured: `reftable` refuses,
   `sha256` reads.
3. **Ambient configuration removed at the source.** `GIT_CONFIG_GLOBAL` and
   `GIT_CONFIG_SYSTEM` point at an empty file the harness writes — a real file, not
   `/dev/null`, so the mechanism is the same on a platform without it. Every `GIT_*`
   variable is supplied, none inherited.
4. **A sterile view, only when the working tree contains another repository.** Git
   opens `<path>/.git` from the working tree, so a nested repository is a second
   subject. Where any exist, the read runs against a hardlink mirror of the working
   tree in which each nested `.git` is a sterile directory built the same way,
   recursively. Where none exist — the ordinary case — the subject's own working
   tree is used and the view costs nothing.
5. **A build that cannot reproduce the subject refuses.** After construction, the
   HEAD the subject resolves *as data* must equal the HEAD the sterile directory
   resolves. Two unknowns comparing equal is not agreement and is refused by name.

Refusal is no longer the barrier. Execution is impossible, so a repository that
merely *declares* a filter, textconv, hook or transport is read like any other.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Continue 2.4.1: inspect the repository's configuration and refuse what looks dangerous | REJECTED | Its proof requires a complete list of keys, verbs, flags, transports, spellings and nested layouts. Fifteen repairs; the last cycle produced an under-refusal and an over-refusal in the same edit. Its incompleteness is fail-open |
| 2 | Sterile execution: the harness constructs the git directory, so no subject-written file is a configuration source | SELECTED | The source set is closed, Git reports it, and incompleteness makes a read fail instead of execute. Measured: 31 hostile cases, 0 executions, answers byte-identical to real Git wherever real Git answers |
| 3 | Controlled clone/snapshot: copy the subject into harness-owned storage and read the copy | REJECTED | Buys the same guarantee at O(repository) cost on every read, and a copy is a different tree: untracked, ignored and permission truth become claims about the copy. Design 2 obtains the guarantee from `GIT_DIR` alone, and pays a tree cost only where a nested repository forces it |
| 4 | OS sandbox: let Git read anything, deny the process the ability to execute | REJECTED | Not portable — `sandbox-exec` was denied to a reader in this project's own certification, and Windows has no equivalent primitive. It also fails closed only if the sandbox is present, so its guarantee is environmental rather than architectural |
| 5 | Observational: run normally and detect execution afterwards with `GIT_TRACE2_EVENT` | REJECTED as a barrier | Detection happens after the program has run, which is not a barrier. **Retained as an oracle**: TRACE2 reports every child process Git starts, so it independently falsifies the claim that none was started. Measured at 0 children under design 2 |

## The cost, stated rather than discovered

Measured on Git 2.50.1, macOS:

| Path | Work | Cost |
|---|---|---|
| No nested repository (ordinary) | walk to decide, then build the git directory | 4 ms (200 files) — 12 ms (20,000 files) |
| Nested repository present | the above, plus a hardlink mirror of the working tree | 40 ms (200 files) — 2.3 s (20,000 files) |

The slow path is bounded by file count and is entered only when the working tree
really contains another repository. It is not free and is not hidden.

## What changes for a consumer

- A repository that merely declares program-valued configuration is now **read**,
  not refused. Refusals get strictly rarer. This is the authorised behaviour change:
  refusal was a proxy for "this might execute something", and the proxy caused the
  `workspace_report` outage in B15b.
- A diff of content with a textconv or external-diff driver is now the **raw** diff,
  because no driver runs. For a pack that scans content for leaks and whitespace
  damage, the raw bytes are the honest subject.
- Reading a repository's own configuration *values* (a remote URL, a branch setting)
  stays available, and becomes a parse of the file as data rather than a Git
  invocation — strictly less capable of executing anything than it was.
- A repository whose ref store this build cannot import (`extensions.refstorage`)
  is refused by name rather than answered wrongly.

## Authority boundaries

Reports and refuses. It opens nothing, grants nothing, and weakens no row of
`policy/hitl-matrix.md`. It does not decide whether a repository is trustworthy —
it removes the question by making the repository's configuration unreachable. The
transport policy pinned in the harness's own config file is a harness policy, not
a claim about what the subject may do, because the subject's configuration is not
in the picture at all.

The names 2.4.1 exported for the enumeration — `PROGRAM_VALUED_CONFIG`,
`CLOSED_PROGRAM_KEYS`, `FLAG_BASED_CLOSURES`, `CONDITIONAL_CLOSURES`,
`ALLOWABLE_TRANSPORTS`, `program_valued_config` — survive as **projections**: they
report, and no security decision consults them. That they cannot become a second
answer to the same question is a property this design requires to be proved, not
assumed (oracles O8 and O9).

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | The build silently loses part of the subject's state and Git answers about a repository that is not the subject | The HEAD round trip (mechanism 5) refuses on mismatch, and refuses two unknowns comparing equal. Reproduced: without it, a `reftable` subject reported every tracked file as newly added, at exit 0 |
| 2 | A nested repository is missed and its configuration is applied | The view is built from the working tree, which is the set Git opens from; over-inclusion costs a hardlink and refuses nothing, so the walk can be generous. TRACE2 independently reports any child process |
| 3 | A future Git reads configuration from a source this design does not know about | The origin check is against Git's own `--show-scope` output, so a new source appears as an origin outside the harness directory and fails the invariant rather than passing unnoticed |
| 4 | A `core.*` storage key is not carried and answers differ subtly from real Git | Differential oracles compare the sterile answer against real Git's on the same fixture, byte for byte |
| 5 | The hardlink mirror lets a read write to the subject | Only the index is written, and the index is a copy. An oracle asserts the subject's tree and git directory are byte-identical after a read |
| 6 | The slow path is entered on every read of a large tree | The fast path is chosen by a walk that stops at each nested repository; cost is measured by an oracle, not assumed |
| 7 | A projection disagrees with the boundary and a caller believes it | O8 asserts no security decision reads a projection; O9 asserts a projection cannot report a repository as unreadable |

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O1 | NEGATIVE | no option spelling of a verbose verb executes a repository's textconv driver, including abbreviations nobody enumerated | tools/tests/test_gitread.py::test_no_spelling_of_a_verb_executes_the_repositorys_driver |
| O2 | NEGATIVE | a populated nested repository's own configuration never executes, whether or not it is in the index | tools/tests/test_gitread.py::test_a_nested_repositorys_configuration_never_executes |
| O3 | ACCEPTANCE | an ignored, never-a-submodule checkout leaves the project readable, and the answer equals real Git's | tools/tests/test_gitread.py::test_an_unrelated_ignored_checkout_leaves_the_project_readable |
| O4 | ACCEPTANCE | the configuration sources Git reports are all harness-owned, asked of Git rather than asserted | tools/tests/test_gitread.py::test_every_configuration_source_git_reports_is_one_the_harness_wrote |
| O5 | NEGATIVE | a subject whose ref store the build cannot import is refused by name, not answered | tools/tests/test_gitread.py::test_a_ref_store_the_build_cannot_import_is_refused_not_answered |
| O6 | ACCEPTANCE | a read leaves the subject's working tree and git directory byte-identical | tools/tests/test_gitread.py::test_a_governed_read_leaves_the_subject_byte_identical |
| O7 | NEGATIVE | Git starts no child process during a governed read of a hostile repository, by TRACE2 | tools/tests/test_gitread.py::test_git_starts_no_child_process_during_a_governed_read |
| O8 | NEGATIVE | no security decision consults a projection: removing every projection changes no refusal | tools/tests/test_gitread.py::test_no_refusal_depends_on_a_projection |
| O9 | ACCEPTANCE | a projection reports what the subject declares without making a repository unreadable | tools/tests/test_gitread.py::test_a_projection_reports_without_refusing |
| O10 | ACCEPTANCE | answers equal real Git's byte for byte across the hostile matrix, wherever real Git answers | tools/tests/test_gitread.py::test_the_sterile_answer_equals_real_gits_answer |
| O11 | MUTATION | restoring subject-owned configuration to the source set must fail O4 and O1; removing the HEAD round trip must fail O5; removing the nested view must fail O2 | tools/tests/test_gitread.py::test_every_configuration_source_git_reports_is_one_the_harness_wrote |

## Why this should converge where 2.4.1 did not

2.4.1's proof obligation grew with every Git feature: one more key, one more verb,
one more spelling. This design's proof obligation is a single sentence Git can be
asked to confirm, and the things that can go wrong with it make reads **fail**
rather than **succeed unsafely**. The list that remains — which `core.*` storage
keys to carry — governs availability, not safety, and its incompleteness is a
refusal somebody notices.

It is not unfalsifiable. If a reader shows a configuration source Git consults that
is not a file, or a path by which a subject's file becomes a source despite
`GIT_DIR`, the invariant is wrong and this design fails as a whole rather than
needing another entry.
