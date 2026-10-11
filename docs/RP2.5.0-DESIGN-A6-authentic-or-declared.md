# DESIGN — RP2.5.0: the answer no program could have shaped, or the mechanism that shaped it

**Change class:** MATERIAL
**Base revision:** a7fb84d3ede778e6b46dfbc60248e6e50a132201
**Frozen:** yes

## What the two independent readings settled

A5 was read blind by two independent readers who did not see each other's work. Both returned
DESIGN_BLOCKED, and they reached the same defect from opposite ends.

The cross-vendor reader reached it from an **ordinary** repository: `git status` on a repository
whose cached stat data is stale rewrites the real `.git/index`. A1 copied the index for exactly
this reason and froze a byte-identity oracle over it. A5 deleted that oracle without replacing
it, and all seven of A5's oracles pass an implementation that makes this write.

The same-vendor reader reached it from a **hostile** one: `diff.external = git`. The value is a
bare word, so no shell is involved and the route A5 had already closed does not apply. Git's
external-diff protocol hands the program the working-tree path as `argv[1]`, so a file named
after a Git subcommand makes `git diff` exec `git <that subcommand>`. With a file named
`repack`, a governed read repacked the subject's real object store — `in-pack 0 → 3` — at exit
0, with every child completing successfully.

Both findings are one fact: **A5 stopped execution and did not stop writing.** Its refusal
signal keyed on a child that failed to complete, and the attack is a child that completes.

A third fact follows from the second. The reader's impossibility argument — that Git-to-Git must
be permitted for submodules and that permitting it is the hole — is correct *as long as the
permitted set is the thing being adjusted*. It stops being correct when the process loses the
ability to create children at all.

## The mechanism

**Read the real repository.** Kept from A5, and it is the part both readers confirmed: all
twelve rows of the divergence corpus genuinely dissolve, because an authentic read has nothing
to diverge from.

**Own the process environment, and build it by addition from empty.** Seven names — `PATH`,
`HOME`, `XDG_CONFIG_HOME`, `GIT_CONFIG_NOSYSTEM`, `GIT_OPTIONAL_LOCKS`, `TZ`, `LC_ALL` — added
to an empty environment. This is closed in the way the founder's rule requires: there is no list
of variables to *strip*, so no enumeration can be incomplete. It answers the cross-vendor
reader's F2 by choosing: the repository is authentic, the environment is the harness's. Measured
across 35 repositories × 12 command forms: nothing broke, 385 of 420 answers identical to the
operator's own environment, and the 35 that differ are all `config --list` — the one command
whose job is to report configuration. A2's promise is preserved, and it is visible in exactly
one place.

**Deny writes to the subject and to its resolved Git directory.** The same OS barrier that
denies execution also denies writing. This is not Git's `GIT_OPTIONAL_LOCKS=0`, which was
measured and is not sufficient: it stops `status` writing the index but not `diff`, which writes
it anyway. The resolved Git directory must be named separately, because in a **linked worktree**
the real Git directory lives under the *main* repository, outside the subject — a subject-only
deny was measured letting `git diff` write `main/.git/worktrees/<n>/index`.

**Deny the process the ability to fork.** Not an allowlist of permitted programs — the removal
of the capability to create a child. This is what makes the reader's impossibility argument stop
applying: the subject can still *name* any program it likes, and no naming can produce one.

**The kernel then yields one bit, and that bit selects the mechanism.**

| what the kernel reported | what it means | what the read returns |
|---|---|---|
| no child was denied | nothing ran, so nothing the subject configured could have shaped this answer | the authentic answer, marked as authentic |
| a child was denied | this read genuinely needs a program to run | the already-qualified 2.4.0 sterile answer, marked as reconstructed |
| the barrier could not be established | the guarantee is unavailable | the 2.4.0 answer, marked as reconstructed |
| neither mechanism answers | the honest state | UNKNOWN |

The selector is a single kernel-produced bit. It is not a judgement about what a setting can
probably affect, and it is not a list of anything.

**Every answer carries the mechanism that produced it, and a strict caller may refuse a
reconstructed one.** This is not decoration. It is what stops the subject choosing its own
authority — see failure mode 1 — and it is the A4 output contract the cross-vendor reader's F2
correctly said A5 had dropped with no replacement.

## What this costs, measured rather than asserted

| | measured |
|---|---|
| ordinary repositories that answer authentically | **600 of 600** — 40 repositories × 15 command forms, byte-identical to plain Git, **0 refusals, 0 divergences** |
| the cross-vendor reader's index-refresh write | **closed** — subject byte-identical, answer unchanged |
| the same-vendor reader's `diff.external = git` repack | **closed** — child denied (`code -1`), `in-pack 0 → 0`, subject byte-identical, read refuses at rc 128 rather than answering at 0 |
| a populated submodule | the authentic path **refuses** (measured, both `status --porcelain` and `diff --submodule=diff`); the fallback answers it as 2.4.0 does today, marked reconstructed |
| an active external diff | the authentic path refuses; the fallback returns A1's raw diff, marked reconstructed — so A1's published promise is kept rather than silently turned into a refusal |
| platforms without the barrier | everything falls back, so they get **exactly 2.4.0**, which is why this narrows no capability anywhere |

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Continue A1–A4: reproduce the subject in a constructed environment | REJECTED | Four generations, every one falsified, each by a source outside the previous generation's model |
| 2 | A5 as frozen: read the real repository behind an execution allowlist | REJECTED | Falsified independently by two blind readers. It stops execution and not writing, and its refusal signal keys on a child failing to complete while the attack is a child that completes |
| 3 | A5 plus a write deny, keeping Git-to-Git permitted | REJECTED | Measured to close both readers' reproductions. But the subject still chooses *which* Git subcommand runs, so safety rests on an open-ended search over subcommands that exit 0 without writing — the open-ended enumeration that fails open, which section 4 forbids |
| 4 | Deny fork and writes, and refuse whenever a child is denied | REJECTED | Measured: an ordinary superproject with a populated submodule then refuses where 2.4.0 answers. Safe, and a capability regression against the qualified floor that D14 forbids |
| 5 | Deny fork and writes; let the kernel's denial bit select between the authentic answer and the already-qualified 2.4.0 mechanism, and label which one answered | SELECTED | Takes design 4's guarantee without design 4's regression. Nothing the subject names can execute; nothing a read does can change the subject; where a read genuinely needs a program the pack still answers exactly as 2.4.0 does, and says so |
| 6 | Family C: substitute config-free query forms for the governed verbs | REJECTED | Measured by the cross-vendor probe: only 2 of 19 verbs are config-free outright, and `status` — the most-used governed read — requires refusal for its full answer, changed by fourteen settings. Retained as a future fallback for refused classes, not as the mechanism |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | The subject forces the fallback by naming any program-valued key, and so chooses which authority answers it | It cannot obtain a 2.4.0 answer *labelled authentic*: the label is set by the kernel bit, not by the answer's content. The subject can degrade itself to 2.4.0 behaviour, which is the behaviour it would have had anyway, and a strict caller refuses reconstructed answers outright. O-A6-5 |
| 2 | The write deny misses a path Git writes through that `rev-parse` did not name | O-A6-1 fingerprints the whole subject *and* the resolved Git directory before and after every governed verb, so an unmodelled path shows as a changed fingerprint rather than as a passing test. This failure mode is not hypothetical: the linked-worktree case was found this way |
| 3 | The barrier is present but not in force, so the read runs unprotected | O-A6-6 proves enforcement by writing a canary into the subject *inside the same profile the read uses*, rather than by observing that `sandbox-exec` exists. Presence is not enforcement, and the cross-vendor reader named the presence-check cheat explicitly |
| 4 | The trace is silent, or belongs to some other invocation, so a denied child goes unseen | O-A6-7 correlates the trace to the target invocation by session and terminal event. A non-empty file is not evidence: a harness sentinel, a preflight, or an unrelated session makes it non-empty |
| 5 | Fork denial blocks something an ordinary read legitimately needs on a Git build or platform not measured here | It fails closed into the fallback, so the worst case is 2.4.0's answer, marked reconstructed. O-A6-4 measures the rate on a real corpus; it is 0 of 600 here, on one machine and one Git build, and that limit is stated rather than generalised |
| 6 | Git gains a way to shape an answer without creating a child | The divergence corpus compares answers rather than mechanisms, so such a case surfaces as a wrong answer even though this model did not predict it |

## Authority boundaries

This design decides how a governed read is performed. It does not decide:

- whether a reconstructed answer is acceptable for any particular use — the caller decides, which
  is the whole reason the label exists and the reason it is part of the answer rather than a log line;
- what `READ_ONLY_VERBS` contains, which stays a closed set changed only by its own authority;
- whether this candidate is frozen, tagged, published, or adopted by any consumer;
- that absence of evidence is evidence: a barrier that cannot be established, a trace that cannot
  be correlated, and a fingerprint that cannot be taken each refuse or fall back, never proceed.

## Oracles, frozen before implementation

Each oracle names the wrong implementation it exists to reject. The cross-vendor reader's F4
showed that all seven of A5's oracles admitted a wrong implementation, including two that passed
the whole suite while failing D2 and A2; an oracle that no wrong implementation fails is a
restatement of the design, not a test of it.

| ID | Kind | The property it settles | The wrong implementation it rejects | Selector |
|---|---|---|---|---|
| O-A6-1 | ACCEPTANCE | the subject and its resolved Git directory are byte-identical before and after every governed verb, on a corpus that includes a stat-stale index and a linked worktree | the A5 implementation, which passes all seven A5 oracles and still rewrites the real index; and a subject-only deny, which passes on an ordinary repository and writes in a linked worktree | tools/tests/test_gitread.py::test_a_governed_read_leaves_the_subject_byte_identical |
| O-A6-2 | NEGATIVE | `diff.external = git` with a working-tree file named after a Git subcommand refuses, and the object store is unchanged, against a positive control showing the unbarriered read does repack | any implementation that permits Git to spawn Git, including design 3 | tools/tests/test_gitread.py::test_the_git_binary_cannot_be_turned_against_the_barrier |
| O-A6-3 | NEGATIVE | no child is created at all: on every row of the hostile corpus the marker is 0 bytes while a per-row unbarriered positive control writes more than 0 | a fixture-specific block, which the per-row control catches, and a profile that is written but never loaded | tools/tests/test_gitread.py::test_no_program_runs_under_the_barrier |
| O-A6-4 | ACCEPTANCE | a real corpus of at least 35 repositories answers authentically, byte-identical to plain Git under the owned environment, with zero refusals | "refuse everything", which is otherwise perfectly safe and satisfies every negative oracle | tools/tests/test_gitread.py::test_ordinary_repositories_are_not_refused |
| O-A6-5 | ACCEPTANCE | a populated submodule and an active external diff answer through the fallback and are labelled reconstructed; an ordinary read is labelled authentic; the label follows the kernel bit and not the content | an implementation that returns the fallback answer unlabelled, which is failure mode 1 made silent | tools/tests/test_gitread.py::test_every_answer_names_the_mechanism_that_produced_it |
| O-A6-6 | NEGATIVE | the barrier is proven in force by a canary write that fails inside the same profile the read uses; if it cannot be proven, the read falls back rather than proceeding | defining establishment as `sandbox-exec` being present and then running the target unsandboxed | tools/tests/test_gitread.py::test_an_unenforced_barrier_never_answers_authentically |
| O-A6-7 | NEGATIVE | the trace is correlated to the target invocation by session and terminal event; a pre-seeded or foreign trace does not count as observation | treating "the trace file is non-empty" as evidence that the governed read emitted it | tools/tests/test_gitread.py::test_a_foreign_trace_is_not_an_observation |
| O-A6-8 | MUTATION | five named mutants, each applied and verified by a mutation runner: remove the fork denial → O-A6-2 must fail; remove the write deny → O-A6-1 must fail; narrow the write deny to the subject alone → O-A6-1 must fail on the linked worktree; return the fallback answer without its label → O-A6-5 must fail; accept a non-empty trace as establishment → O-A6-6 must fail | a "mutation oracle" that re-runs an ordinary test instead of applying mutants, which is what A5's was | docs/acceptance/rp2.5.0-mutation.py |

## What this does not settle

- One machine, one Git build (2.50.1, Apple Git-155), macOS 15.7.9 arm64. Every rate here is that
  population's rate. The fallback is what makes this survivable rather than fatal: an unmeasured
  platform gets 2.4.0, not a wrong answer.
- `sandbox-exec` is deprecated by its vendor. When it is removed, this pack returns 2.4.0
  behaviour everywhere and the authentic path becomes unavailable — a loss of improvement, not a
  loss of capability. No replacement barrier has been qualified.
- Whether the two mechanisms' answers should ever be compared against each other. They are not,
  deliberately: the differential design was measured at 89.5% agreement and 5.1× cost and
  rejected in A5, and reintroducing the comparison here would reintroduce that cost.
- Whether any consumer wants the reconstructed label. That is a consumer decision and this record
  does not make it.
