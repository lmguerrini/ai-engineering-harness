# DESIGN — RP2.5.0: one governing API, two qualified backends, and no child inside a local read

**Change class:** MATERIAL
**Base revision:** 673d97f94ba4b3406e1afd6ddc52bd5b23e56e29
**Frozen:** yes

## What A7 got right, and the one thing that falsified it

A7 wrapped an OS barrier around the qualified read and denied every execution but Git's own binary.
Two independent readings broke it on one clause. The allowlist is not a capability boundary: Git's
helpers in `git-core` are symlinks to the Git binary, so the clause permits `fsmonitor--daemon` to
detach and outlive a read, while `git-remote-http` is a separate binary, so the same clause denies
the transports the frozen release answers. Eleven frozen tests regressed, and one of them asserts
against that failure by name.

The barrier itself was never falsified. Both readers said so: an injected missed key is prevented
with controls in both directions, and the whole governed-read population passes under it. What
failed was making one program list serve two capabilities whose legitimate needs are opposite.

## The mechanism

**One governing API, two backends, selected by the requested capability.** The selection is made
from the governed operation the caller asked for. It is never made from anything the subject
controls — not configuration, not a helper, not a hook, not repository contents.

| backend | what it is for | execution policy |
|---|---|---|
| local read | every governed read of a repository on this machine | **no child process, at all**; any attempt fails closed |
| transport | the remote-verification capability, which is `ls-remote` with a caller-named transport | the already-qualified mechanism, unchanged |

**The local backend denies child creation, not a list of programs.** No allowlist participates in
the decision, so nothing about which binaries exist, what they are named, or which of them are
symlinks to each other can widen it. This is the clause A7 needed and could not express while it
was also trying to serve transports.

**The transport backend is not new and is not weakened.** It stays exactly as qualified: the verb
is the one transport verb, the transports are the named set, and the caller opens one per
invocation. Nothing here narrows it, because the local backend's policy is not applied to it.

**Submodule-aware reads are decomposed above the boundary, never by permitting a child.** A read of
a superproject with a populated submodule is answered as a composition of independently governed
childless reads:

1. the submodule identities come from closed structural state — stage-zero gitlink entries and the
   recorded tree gitlinks. Not from `.gitmodules`, not from configuration;
2. the superproject is read with submodule recursion suppressed, which needs no child;
3. each populated gitlink is observed by its **own top-level governed read**, under the same
   no-child policy, recursing by the same rule for nested submodules;
4. the results are composed using Git's own porcelain-v2 submodule field rather than an invented
   substitute, by a rule derived from what the frozen release actually emits.

`gitread._run` remains exactly one boundary and gains no policy table. Decomposition is
orchestration above it, which is what keeps both of those true at once.

## What this costs and what it buys, measured before this record was written

| | measured |
|---|---|
| submodule composition against the frozen release | **110 corpus rows byte-exact**, eleven fixtures against ten read forms, including trailing newlines |
| child processes on the composed side | **none**, on every row, with the trace rejected as evidence unless it contains Git's own version event |
| positive controls | **six of six detected** — missed dirty state, wrong staged/unstaged, wrong new-commit classification, omitted untracked state, wrong gitlink identity, and an accidental child |
| the four behaviours the candidate had lost | **restored**, matching the frozen release exactly |
| the routes by which a subject could regain authority | `config`, `config.worktree`, `include.path` and `includeIf` each demonstrated live in the subject and dead in the governed read |
| a program-valued key the enumeration missed | prevented, with a live positive control, and with no key named by the mechanism |

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | A7 unchanged: one barrier, one program allowlist, both capabilities | REJECTED | Falsified independently twice. The allowlist admits Git's own daemons through symlinks and denies the transports the frozen release answers; eleven frozen tests regress and one asserts against it by name |
| 2 | Keep A7's shape and enumerate the helper binaries a transport needs | REJECTED | It makes a list of program names the security boundary, which is the shape this release exists to stop writing, and the list is open: it would have to change whenever a Git build changes its helpers |
| 3 | Scope the barrier by verb inside the single boundary | REJECTED | A verb table inside `_run` is the enumeration the module's own comment says this release exists to remove, and it would have to grow with every option that changes what a verb needs |
| 4 | Deny children in local reads and accept that populated submodules refuse | REJECTED | Measured: the frozen release answers those reads, so refusing them loses a capability at the qualified floor |
| 5 | One governing API with a local no-child backend and the qualified transport backend, submodule reads decomposed above the boundary | SELECTED | Each capability gets the policy its legitimate semantics need, the security decision names no program, and the capability the strict policy would have cost is recovered by composition proven byte-exact against the floor |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | The composition drifts from what the frozen release emits, and a governed answer becomes quietly wrong | The corpus compares exact bytes against the frozen release, and its six positive controls each break one part of the composition deliberately to show the corpus reports it. A composition rule with no failing control is not evidence |
| 2 | A submodule state nobody built a fixture for composes incorrectly | The rule is derived from Git's own porcelain-v2 submodule field rather than reconstructed, so a state the corpus omits is still carried by the field it already reads. This is a reason to expect fewer gaps, not a proof there are none, and it is the first thing an independent reading should attack |
| 3 | A child is created and nothing notices | Child creation is observed through Git's own trace, and a zero count is rejected as evidence unless the trace proves it was written. An unwritten trace reads as no evidence, never as no children |
| 4 | The routing decision is influenced by the subject | Selection is made from the requested capability before the subject is read. Submodule identities come from stage-zero gitlinks and recorded tree gitlinks, which are structural facts of the repository being read, not statements the subject makes about how it should be handled |
| 5 | The transport backend is quietly given the local policy, or the local backend quietly given the transport's | They are separately qualified, and the oracles assert both directions: a transport read must still answer, and a local read must still create no child |
| 6 | Composition costs more than the read it replaces | It performs one governed read per populated gitlink instead of one child per gitlink. That is the same order of work, and the corpus records the counts rather than asserting it |

## Authority boundaries

This design decides how a governed operation is launched and how a submodule-aware answer is
assembled. It does not decide:

- what a governed read means; the qualified contract is unchanged and this design's whole claim is
  that it stays unchanged;
- what the transport capability may reach, which stays exactly as qualified;
- what `READ_ONLY_VERBS` contains, or any other enumeration, which remains as qualified and stops
  being the only thing between a missed key and a running program;
- whether this candidate is frozen, tagged, published, or adopted by any consumer.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | The wrong implementation it rejects | Selector |
|---|---|---|---|---|
| O-A71-1 | ACCEPTANCE | every governed local read answers exactly as the frozen release answers it, across the real corpus and every public form, comparing refusals as well as answers | an implementation that matches the current candidate rather than the floor — that baseline is what hid four lost behaviours until they were measured against the frozen release | tools/tests/test_gitread.py::test_no_local_read_regresses_the_floor |
| O-A71-2 | ACCEPTANCE | the submodule corpus matches the frozen release byte for byte on every fixture and form, including trailing newlines | a composition that normalises, trims, or compares "equivalently"; the oracle compares bytes | docs/acceptance/rp2.5.0-submodule-differential.py |
| O-A71-3 | NEGATIVE | no governed local read creates a child process, and a zero count is not accepted unless the trace proves it was written | an implementation that never enables the trace and reports zero children forever | tools/tests/test_gitread.py::test_a_local_read_creates_no_child |
| O-A71-4 | NEGATIVE | each of the six deliberate composition defects is detected by the corpus | a corpus that passes because it cannot fail; each control breaks one part and must be reported | docs/acceptance/rp2.5.0-submodule-differential.py |
| O-A71-5 | ACCEPTANCE | a caller-named transport still answers through the transport backend, and the frozen publication tests pass unchanged | an implementation that applies the local no-child policy to transports, which is exactly what falsified A7 | tools/tests/test_publication_gate.py |
| O-A71-6 | NEGATIVE | a program-valued key the enumeration missed does not execute, on rows each carrying a live positive control | an implementation that strips the injected key instead of denying the capability | tools/tests/test_gitread.py::test_a_missed_key_still_cannot_execute |
| O-A71-7 | NEGATIVE | the subject cannot regain authority through `config`, `config.worktree`, `include.path` or `includeIf`, each demonstrated live in the subject | an implementation that owns the configuration file but reads one of the other three routes | tools/tests/test_gitread.py::test_the_subject_cannot_configure_the_checker |
| O-A71-8 | NEGATIVE | routing is decided before the subject is consulted, and no repository content changes which backend runs | an implementation that inspects the repository to choose a backend, which would let a subject select its own execution policy | tools/tests/test_gitread.py::test_routing_does_not_consult_the_subject |
| O-A71-9 | MUTATION | five named mutants, each applied and verified by a runner: remove the child denial → O-A71-3 must fail; apply the local policy to transports → O-A71-5 must fail; compose from an invented field instead of the porcelain-v2 submodule field → O-A71-2 must fail; take submodule identities from `.gitmodules` → O-A71-8 must fail; accept a zero child count without the trace-written check → O-A71-3 must fail | a mutation oracle that re-runs an ordinary test instead of applying mutants, which is what A5, A6 and A7 all shipped | docs/acceptance/rp2.5.0-mutation.py |

## What this does not settle

- One machine, one Git build, one operating system. The barrier is platform-specific; where it
  cannot be established the read fails closed rather than proceeding, and that is a narrowing of
  availability on platforms this pack makes no claim about.
- `diff --submodule=diff` is refused by the frozen release before Git runs, because it is the
  option that lets the repository choose a program. There are no frozen bytes to compose, so the
  composition does not claim it. It is not a floor regression; the floor refuses it too.
- Whether the enumeration can now be simplified. It must not be, in this change: it stays exactly
  as qualified and the denial is added beneath it.
- Failure mode 2. A submodule state no fixture covers is carried by Git's own field rather than by
  a rule this design wrote, which is a reason for confidence and not a proof.
