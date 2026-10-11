# DESIGN — RP2.5.0: keep the qualified semantics, and take away the capability instead

**Change class:** MATERIAL
**Base revision:** 998b18edd3bf68b52e5efee81e608bddce4226f5
**Frozen:** yes

## What the founder decided, and what it removes from the problem

Harness-defined semantics are authoritative for a governed read. Semantic equivalence to plain Git
running with arbitrary subject-controlled configuration is not required, and the qualified 2.4.0
contract is the non-regression floor.

That decision retires the question six designs died on. A1 through A4 were falsified against a
standard — real Git's answer on the subject's own configuration — that does not apply. A5 and A6
were built to satisfy that standard and reintroduced the subject as the author of the answer,
which is the thing the pack exists to prevent. Neither direction has to be continued.

What survives from all six generations is a single measured fact that nobody has broken: **an OS
barrier can remove a process capability, and that removal does not depend on knowing which
configuration key would have used it.** Two independent readers attacked the barrier itself in A5
and A6 and failed: `fork`, `vfork` and `posix_spawn` all return `EPERM`, the trace cannot be
hijacked or silenced by subject configuration, and no write escaped the denied regions across
eight repository shapes. The barrier was never the defect. The thing it was wrapped around was.

## The mechanism

**Wrap the barrier around the qualified path instead of replacing it.** The sterile governed read
is unchanged — same construction, same configuration written from a blank slate, same answers.
The only change is that the Git invocation at `gitread._run`'s single boundary is launched inside
an OS profile.

**The profile denies two capabilities and names no key.**

| clause | what it takes away | why the read never needs it |
|---|---|---|
| `(deny file-write* (subpath <subject>))` | writing to the subject | the qualified mechanism already copies the index into harness scratch precisely so a refresh cannot reach the subject; this makes that property enforced rather than intended |
| `(deny process-exec*)` with a single `(allow process-exec* (literal <git>))` | executing anything that is not the Git binary | a governed read runs Git; every other program it could run was named by configuration, and configuration is the harness's |

**The harness scratch stays writable, deliberately.** The denial is scoped to the subject, not to
the constructed git directory. That directory is where the qualified mechanism puts the index copy,
and denying writes there would break the very property the copy exists to provide.

**Fork is not denied, and that is a measured choice rather than an omission.** Denying it refuses
a populated submodule's `status` and `diff`, which 2.4.0 answers; permitting the Git binary alone
answers them identically and still prevents every injected non-Git gap. A5's objection — that
permitting Git permits every Git subcommand, chosen by the repository — required the subject's
configuration to be in force. Here the harness writes the configuration from a blank slate, and
the nested repository a submodule child reads is sterile too, which was tested rather than argued.

**Establishment is proven, not assumed.** Before the read, a canary write into the subject is
attempted inside the same profile the read will use. If it succeeds, the barrier is not in force
and the read refuses rather than proceeding under a guarantee it cannot offer.

## What this costs and what it buys, measured rather than asserted

| | measured |
|---|---|
| answers identical to the qualified sterile answer | **347 of 347**, across 35 repositories and 10 command forms, with 3 further reads refused identically by both |
| children attempted by an ordinary governed read | **none**, across 700 barriered Git invocations |
| barrier establishment failures | **none** |
| a program-valued key the enumeration missed | injected as `-c` on three keys with live positive controls — **prevented on every one**, with **zero keys named by the barrier** |
| subject bytes after a governed read | **unchanged**, across ordinary, split-index, linked-worktree and superproject-with-submodule shapes, all with stale stat data |
| the attack that falsified A6 | the falsifier's own daemon forges a clean answer for plain Git and **cannot reach a governed read**, because the subject's `core.fsmonitor` is never in force |
| the same attack one level down, inside the submodule | **also cannot reach it** — the nested repository the child reads is sterile |
| populated submodule availability | **identical to the qualified path** |

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Continue A5/A6: read the subject authentically and prevent execution | REJECTED | The founder's decision removes its purpose, and two readers falsified it: preventing execution is not preventing influence, and ordinary configuration shaped an authentic-labelled answer with no child created |
| 2 | Continue A1–A4: keep reproducing the subject more completely | REJECTED | Four falsifications, each by a source outside the previous model. The decision does not repair the open set; it only means the corpus was scoring the wrong thing |
| 3 | Qualified sterile semantics, with an OS profile denying subject writes and every non-Git execution, wrapped around the unchanged path | SELECTED | Preserves every qualified answer measured, adds an execution and mutation guarantee the qualified path did not have, and needs no key list to do it |
| 4 | The same, but also denying `fork` | REJECTED | Measured: refuses a populated submodule's `status` and `diff` where the qualified path answers. It buys nothing the exec denial does not already buy, and costs a qualified capability that D14 protects |
| 5 | Keep the enumeration as the only execution authority and harden nothing | REJECTED | This is 2.4.0, and its incompleteness fails open into execution. The whole point of the composition is to make that incompleteness stop being a security boundary |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | The profile is present but not in force, so the read runs unprotected | A canary write into the subject is attempted inside the same profile the read uses, and the read refuses when it succeeds. Presence is not enforcement, and an independent reader broke exactly this check in A6 |
| 2 | The subject path handed to the profile is not the kernel-canonical one, making the denial inert | A reader measured this in A6: a deny naming an unresolved path is silently ignored. The subject is resolved before the profile is written, and failure mode 1's canary is what catches it when it is not |
| 3 | Permitting the Git binary permits a Git subcommand the repository chose | It cannot choose one: the configuration Git reads is written by the harness from a blank slate, and the nested repository a submodule child reads is sterile too. Both were measured, the second with the forgery placed inside the submodule |
| 4 | The barrier is unavailable on a platform | The read refuses rather than proceeding. This narrows availability on platforms the pack makes no claim about, and it fails closed |
| 5 | A capability the read legitimately needs is denied, refusing an ordinary repository | Measured on a real corpus and on four repository shapes, and it is why fork denial was rejected. The oracle that would catch a regression compares against the qualified answer, not against plain Git |
| 6 | Git influences an answer through a channel that is neither an execution nor a write | This is the A6 defect, and the reason it does not arise here is that the channel had to be requested by configuration the subject no longer controls. If a channel exists that needs no configuration at all, no clause in this profile would see it |

## Authority boundaries

This design decides how the qualified read is launched. It does not decide:

- what a governed read means — that is the qualified 2.4.0 contract, and this design's whole
  claim is that it changes none of it;
- what `READ_ONLY_VERBS` contains, or any other part of the enumeration, which remains exactly as
  qualified and merely stops being the only thing standing between a missed key and execution;
- whether this candidate is frozen, tagged, published, or adopted by any consumer;
- that absence of evidence is evidence: an unestablished barrier and an unresolvable subject path
  each refuse.

## Oracles, frozen before implementation

The central oracle is not equivalence to plain Git. It is: does every applicable qualified 2.4.0
semantic survive, while an execution and mutation guarantee appears that 2.4.0 did not have?

| ID | Kind | The property it settles | The wrong implementation it rejects | Selector |
|---|---|---|---|---|
| O-A7-1 | ACCEPTANCE | every governed read answers exactly as the same read answers without the barrier, across a real corpus and every public verb form, comparing refusals as well as answers | any implementation that changes a qualified answer, including one that quietly drops a capability the read needed; the comparator is the qualified answer, so an implementation that matches plain Git instead fails here | tools/tests/test_gitread.py::test_the_barrier_changes_no_qualified_answer |
| O-A7-2 | ACCEPTANCE | the whole frozen 2.4.0 governed-read test population passes unchanged against the composed path | an implementation that preserves the corpus this design happens to sample while breaking a qualified semantic nobody re-listed | tools/tests/test_gitread.py::test_the_qualified_suite_passes_under_the_barrier |
| O-A7-3 | NEGATIVE | a program-valued key injected as if the enumeration had missed it does not execute, on rows each carrying a live positive control | an implementation that strips the injected key rather than denying the capability — the control proves the key reached a program without the barrier | tools/tests/test_gitread.py::test_a_missed_key_still_cannot_execute |
| O-A7-4 | NEGATIVE | a subject that requests an out-of-process answerer cannot shape a governed result, with the forgery placed both in the subject and inside a populated submodule | an implementation that inherits any part of the subject's configuration; the positive control is that the same forgery succeeds against plain Git | tools/tests/test_gitread.py::test_an_out_of_process_answerer_cannot_shape_a_governed_read |
| O-A7-5 | ACCEPTANCE | the subject and its resolved git directory are byte-identical after every governed verb, on shapes including stale stat data, split index, linked worktree and submodule | the qualified implementation itself, which achieves this by care rather than by enforcement and would pass silently if the denial were inert | tools/tests/test_gitread.py::test_a_governed_read_leaves_the_subject_byte_identical |
| O-A7-6 | NEGATIVE | the barrier is proven in force by a canary write that must fail inside the same profile the read uses, and an unenforced or inert profile refuses instead of answering | defining establishment as the sandbox tool being present, and defining the denial by an unresolved path — both broke this check in A6 | tools/tests/test_gitread.py::test_an_unenforced_barrier_refuses |
| O-A7-7 | ACCEPTANCE | a populated submodule answers identically to the qualified path, and the child Git it spawns reads a sterile nested repository | an implementation that denies fork, which is safe and refuses a qualified capability | tools/tests/test_gitread.py::test_a_populated_submodule_answers_as_it_did |
| O-A7-8 | MUTATION | five named mutants, each applied and verified by a runner: remove the exec denial → O-A7-3 must fail; remove the write denial → O-A7-5 must fail; hand the profile an unresolved subject path → O-A7-6 must fail; accept the sandbox tool's presence as establishment → O-A7-6 must fail; add a fork denial → O-A7-7 must fail | a mutation oracle that re-runs an ordinary test instead of applying mutants, which is what A5's and A6's were | docs/acceptance/rp2.5.0-mutation.py |

## What this does not settle

- One machine, one Git build, one operating system. The barrier is platform-specific and its
  vendor deprecates the tool that provides it; when it is gone this returns to qualified 2.4.0
  behaviour, which is a loss of the added guarantee and not of a capability.
- Whether the enumeration can now be simplified. It must not be, in this change: it remains
  exactly as qualified, and the barrier is added beneath it. Removing enumeration entries because
  a barrier exists is a separate decision with its own evidence.
- Failure mode 6. Nothing here can rule out an influence channel that needs no configuration,
  because such a channel would be invisible to a profile that denies execution and writing.
- Whether any consumer needs to know that a read was barriered. No answer shape changes, so no
  consumer contract changes; if that turns out to be wanted it is additive and separate.
