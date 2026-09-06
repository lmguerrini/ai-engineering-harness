# DESIGN — RP2.4.1 B1–B4: what a governed Git read may execute, and what it may answer about

**Change class:** MATERIAL
**Base revision:** 8deec51e88d92d9a5c41cecad677cfa001458f5e
**Frozen:** yes

Read by `tools/design_record.py`. This record authorises nothing.

Four blockers from the whole-candidate certification reduce to two questions, and
both belong to `gitread`, which is the one place that already claims to answer
them for every caller.

## The mechanism

`gitread._run` refuses a configured filter program instead of claiming it is
unreachable, and establishes that the repository and worktree Git resolves are
the ones the caller asked about — so no caller has to remember either.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | B1 by neutralising `filter.*` in the standing config, and B3/B4 by a per-caller toplevel check | REJECTED | Filter names are arbitrary, so neutralising means enumerating configured names and blanking each; an empty clean command makes Git fail rather than proceed, and `filter.<n>.required` then errors — that is breakage wearing the costume of neutralisation. And a per-caller check is the divergence this release exists to close: twelve modules call this reader, `pack_pin` already grew its own copy, and B3 is exactly the caller that did not get one |
| 2 | B1 by removing the false closure so an uncovered filter refuses, and B3/B4 by binding the answer inside `_run` | SELECTED | Both use machinery that already exists. The closed-key table's own rule is that an unrecognised program-valued key refuses rather than waiting to be found; `filter.*.clean` was listed as closed on a claim that is not true, so deleting three wrong rows restores the rule rather than adding one. The binding sits where the environment hardening already sits, so `pack_pin`'s local copy is deleted rather than left as a second answer |
| 3 | Bind on the worktree alone | REJECTED | A bare repository has no worktree, and callers legitimately read one. Binding on the resolved repository catches the nested-archive case, and binding on the worktree only when Git reports one catches the redirect, without a verb list to keep current |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | A repository legitimately using clean/smudge filters (Git-LFS) now refuses | Stated as a limitation in the manifest and named in the refusal itself; fail-closed is the direction that cannot execute somebody's program |
| 2 | A non-checkout nested in another repository | Repository binding refuses; the pin reports UNESTABLISHED rather than a digest over a zero-file tree |
| 3 | `core.worktree` redirects reads away from the requested root | Worktree binding refuses, for every caller rather than for `pack_pin` alone |
| 4 | The binding recurses, since it asks Git about Git | The existing inspection guard covers it, as it already does for the config read |
| 5 | A legitimate linked worktree | Its own toplevel IS its root and its git-dir sits under the root, so both bindings pass; covered by a regression |

## Authority boundaries

This reports and refuses; it opens nothing and weakens no row of
`policy/hitl-matrix.md`. It may only make reads that previously succeeded
refuse — never the reverse.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O1 | NEGATIVE | a configured clean filter does not execute during a read | tools/tests/test_gitread.py::test_a_configured_clean_filter_is_refused_rather_than_run |
| O2 | NEGATIVE | smudge and process filters are refused the same way | tools/tests/test_gitread.py::test_every_filter_program_shape_is_refused |
| O3 | ACCEPTANCE | a repository configuring no filter still reads | tools/tests/test_gitread.py::test_a_repository_with_no_filter_still_reads |
| O4 | NEGATIVE | a redirected worktree is refused for every caller | tools/tests/test_gitread.py::test_a_redirected_worktree_is_refused_for_every_caller |
| O5 | NEGATIVE | a non-checkout nested in another repository is refused | tools/tests/test_gitread.py::test_a_directory_inside_another_repository_is_refused |
| O6 | ACCEPTANCE | standalone repositories and linked worktrees still read | tools/tests/test_gitread.py::test_a_standalone_repository_and_a_linked_worktree_still_read |
| O7 | NEGATIVE | explicit absence never inherits a packed value | tools/tests/test_qualification.py::test_explicit_absence_never_inherits_a_packed_value |
| O8 | REHEARSAL | the pin reports UNESTABLISHED for a nested archive | tools/tests/test_pack_pin.py::test_an_archive_inside_another_checkout_cannot_be_decided |
| O9 | MUTATION | restoring either false closure or removing either binding fails O1/O4/O5 | tools/tests/test_gitread.py::test_a_configured_clean_filter_is_refused_rather_than_run |
