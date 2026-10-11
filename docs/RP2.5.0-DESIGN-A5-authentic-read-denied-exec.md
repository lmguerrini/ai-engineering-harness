# DESIGN — RP2.5.0: read the real repository, and deny the process the ability to execute

**Change class:** MATERIAL
**Base revision:** 9c7762ddb2e0ac3a148abf06eacee615d1a60336
**Frozen:** yes

## The question changes

A1, A2, A3 and A4 all asked one question: *which of the subject's configuration and
state can we safely reproduce?* Every answer was an open set, and every generation
was independently falsified — the last two twice each, by blind readers who
converged. A4's own reader could not break its central negative claim: **a
configuration cannot be both unreachable, so nothing it declares executes, and in
force, so answers match.** That negative result stands and this design accepts it.

So the question is no longer *what can we reproduce?* It is: **did anything try to
run?** That is one bit, observable, and it requires no list of keys, files, layouts,
storage properties, environment variables, verbs, options or transports.

## The mechanism

**Read the real repository.** A governed read runs Git against the subject itself —
its own configuration, its own git directory, its own working tree, on its own
filesystem. Nothing is copied, nothing is reconstructed, nothing is normalised.
**Every divergence class A1–A4 died of disappears by construction**, because there is
no second representation to diverge from. The twelve rows of
`docs/acceptance/rp2.5.0-divergence.py` are not repaired one by one; the mechanism
that produced them is gone.

**Deny the process the ability to execute anything but Git.** The read runs under an
OS-enforced exec barrier that permits exactly one binary — the `git` the harness
invoked, plus the toolchain paths Git itself requires — and denies every other
program. The permitted set is fixed by the harness and is not derived from anything
the subject says, so it is not an enumeration of the subject's content.

**Refuse when the answer depended on a program that could not run.** `GIT_TRACE2_EVENT`
records every child Git attempts and how it ended. A child that did not complete
successfully means Git wanted a program the barrier denied, so the answer is missing
something and **the read refuses**. Measured, the signal is structural rather than a
diagnostic string:

    plain      child_start=2  child_exit=2  codes=[0, 0]   marker 6 bytes (it ran)
    denied     child_start=1  child_exit=1  codes=[-1]     marker 0 bytes (it did not)

**The refusal cannot be based on Git's exit status.** An independent probe of fourteen
configuration points found exactly one case where Git exits **0** while silently
omitting output it would otherwise have produced — `gpg.program` under
`log --show-signature`, which prints `cannot exec` on stderr and still exits 0. Any
rule reading the exit code would have accepted that answer. The child-completion
signal catches it.

**If the barrier cannot be established, refuse before running.** The guarantee is a
checked precondition, not an assumption about the environment. A1 rejected OS
isolation partly because "it fails closed only if the sandbox is present"; checking
presence and refusing is what converts that into a fail-closed property.

## What this costs, measured rather than asserted

| | measured |
|---|---|
| ordinary repositories that answer authentically | **35 of 35** — zero refusals across the real corpus on this machine |
| children attempted by an ordinary read | **0**, across all ten governed verbs |
| hostile repository, 15 program-valued keys | real Git wrote 6–18 marker bytes; **under the barrier, 0 on every row** |
| an ordinary superproject with a populated submodule | `status`, `diff --stat`, `diff --submodule=diff`, `log` all **identical to plain Git** — Git spawning Git is permitted, so the capability survives |
| cost | one Git invocation, against the 5.1× a differential design would pay |

Contrast the alternatives this replaces: A3 refused 96 of 96 real repositories, and
A4's strict caller was refused on 78 of 78.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Continue A1–A4: reproduce the subject in a constructed environment | REJECTED | Four generations, every one falsified; the open set moved from dangerous keys to carried state to owned keys to declared sources, and the last reader found a source outside all four — the case-folding semantics of the volume the build materialised on |
| 2 | Read the real repository, deny exec of everything but Git, refuse on a child that could not complete | SELECTED | No reproduction, so no divergence class; the permitted set is one harness-chosen binary rather than anything derived from the subject; and the residual is a refusal, never a wrong answer |
| 3 | Deny exec of everything, including Git | REJECTED | Measured: an ordinary superproject with a populated submodule then refuses `status` and `diff`, because Git spawns Git to inspect it. Safe but a capability regression against 2.4.0, which section 14 forbids |
| 4 | Differential: answer only where a constrained read and a real read agree | REJECTED | Measured on real repositories: 137/153 = 89.5% agreement, one disagreement class (reflogs), at 5.1× cost while paying both reads. Dominated by design 2, which answers 100% at 1× |
| 5 | Build the view on the subject's own filesystem so storage semantics are identical | DISSOLVED | Measured and it does work — it repairs the case-folding divergence exactly. But design 2 builds no view at all, so the problem it solves does not arise |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | The subject points a program-valued key at the Git binary itself, which the barrier permits | Tested on one spelling and it did not open: Git tried to exec the whole string as a single path, and argument-bearing values route through `sh`, which is denied. **This is an observation about one spelling, not a proof**, and it is the first thing an independent reading must attack |
| 2 | The barrier is unavailable on a platform | The read refuses before running. The pack makes no cross-platform claim anywhere in its manifest, README or DECISIONS, so this narrows availability rather than breaking a promise — and it is disclosed as a platform-qualified backend |
| 3 | A child completes successfully but was not Git | Only Git is permitted, so a completed child is Git; O-A5-2 measures it with a marker and a positive control rather than trusting the profile |
| 4 | TRACE2 is unavailable or silent, so an attempt goes unseen | The environment carrying it is the harness's, not the subject's; O-A5-4 asserts the trace is present and non-empty, because a detector that saw nothing must not read as "nothing happened" |
| 5 | Git gains a way to affect an answer without spawning | The divergence corpus compares answers rather than mechanisms, so such a case surfaces there even though the model did not predict it |

## Authority boundaries

A5 supersedes A1's sterile-execution mechanism, A2's view construction, and A3 and A4
entirely. It **restores** A1's authorised behaviour change — a repository that merely
declares program-valued configuration is read, not refused — and it removes the
constructed view, so A2's nested-repository rules become unnecessary rather than
weakened. It narrows availability to platforms where the barrier can be established,
which is a consumer-visible change and is recorded as one. No founder authority is
required beyond the superseding-record path already authorised.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O-A5-1 | ACCEPTANCE | every row of the divergence corpus answers exactly as real Git; the corpus exits 0 | docs/acceptance/rp2.5.0-divergence.py |
| O-A5-2 | NEGATIVE | a hostile repository executes nothing, measured with a marker against a live positive control on every row | tools/tests/test_gitread.py::test_no_program_runs_under_the_barrier |
| O-A5-3 | NEGATIVE | a read whose answer depended on a denied program refuses, including the case where Git exits 0 | tools/tests/test_gitread.py::test_a_denied_child_refuses_even_at_exit_zero |
| O-A5-4 | ACCEPTANCE | the barrier and the trace are established before the read, and their absence refuses rather than proceeds | tools/tests/test_gitread.py::test_an_unestablished_barrier_refuses_before_running |
| O-A5-5 | ACCEPTANCE | an ordinary superproject with a populated submodule answers identically to plain Git | tools/tests/test_gitread.py::test_a_populated_submodule_still_answers |
| O-A5-6 | ACCEPTANCE | ordinary repositories are not refused: a real corpus answers with zero denied children | tools/tests/test_gitread.py::test_ordinary_repositories_are_not_refused |
| O-A5-7 | MUTATION | removing the barrier must fail O-A5-2; removing the child-completion check must fail O-A5-3; reading the exit status instead of the child signal must fail O-A5-3 | tools/tests/test_gitread.py::test_a_denied_child_refuses_even_at_exit_zero |

## What this does not settle

Failure mode 1 — whether the Git-only allowlist can be turned against itself — is
open and is the reason to read this design before building on it. Whether an
equivalent barrier exists on Linux and Windows is untested here. Whether
`sandbox-exec`, which Apple deprecates, remains available. And every measurement in
this record was taken on one machine with one Git build, as every reading in this
line has said of its own survey.
