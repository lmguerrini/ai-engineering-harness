# RP2.3 — failure-mode closure matrix

**The rule this table exists to enforce:** a proposed *solution* may be deferred;
a verified *failure mechanism* may not remain able to recur. Every mechanism
below is either **PREVENTED** (it cannot be expressed), **DETECTED_AND_BLOCKED**
(it is caught and stops the work), **SAFELY_RECOVERABLE** (it can happen and
costs bounded, recoverable work), or **COVERED** (an existing guarantee already
closes it, demonstrated rather than asserted).

A deferral appears here only where the *mechanism* has a disposition and the
deferred item is an improvement on top of it. Where that is the case, the
deferred item and its trigger are named.

Every row's evidence is a test or a rehearsal in this release, or a named
guarantee in a prior qualified one. Nothing here is closed by prose.

## The mechanisms this release was built to close

| # | verified failure mechanism | disposition | how, and where it is proved |
|---|---|---|---|
| M-01 | a coordinator's state is prose, so four situations produce one observable and only one is a defect | **PREVENTED** | state is *derived* from artifacts, never stored, so there is no value to go stale. `SILENT_IDLE` is representable and is a defect. `test_continuation.py`, `test_silent_idle_closure.py` |
| M-01a | `WAITING_ON_JOB` never advances on job exit | **PREVENTED** | derivation recomputes on every read, so it advances whether or not anyone is watching. A structural test asserts the record holds no state field at all |
| M-01b | a wait decays into silence indefinitely | **PREVENTED** | a wait declares `not_beyond_seconds`; an observable wait without one is unwritable; past it the state is `RECOVERY_REQUIRED` whatever the process is doing. **Reproduced live at 5h39m and closed** — `test_silent_idle_closure.py` |
| M-01c | nothing wakes a coordinator | **DETECTED_AND_BLOCKED** | `COORDINATOR_WAKE_REQUIRED` is reported from the derived state. Creating or waking a session is deliberately out of scope (D23 clause 4) and is an Evolution Candidate with its trigger: a qualified first-party session primitive plus a governance rule authorising it. **The mechanism cannot recur silently** because the deadline ends the wait regardless |
| M-02 | routing has no capacity model; "delegate to the worker" is false when the worker draws on the coordinator's own window | **DETECTED_AND_BLOCKED** | a pre-dispatch refusal with pool identity, three declared reserves, and negative-return refusal. A second dispatch on an unmeasurable window is refused. `test_capacity.py` |
| M-02 (authority) | a semantic decision is rerouted under resource pressure | **PREVENTED** | `authority_class` is a precondition checked before any arithmetic; a task carrying a decision cannot be rerouted at all |
| M-03 | a worker that exists is treated as working | **DETECTED_AND_BLOCKED** | a disjunction over independent signals; process existence is not one of them |
| M-03a | a single-signal detector kills healthy work | **PREVENTED** | a stall cannot be asserted from one kind of observation; the answer is `UNKNOWN` |
| M-03a′ | the horizon is measured against the sampling interval, so a poller never sees a stall | **PREVENTED** | `flat_since_seconds` is required with no default; the report states both durations. **Found by using the instrument on the live incident** |
| M-03b/d | a waiter matches a pattern, including itself | **PREVENTED** | a waiter watches a registered run; a self-matching pattern is refused at construction; `waiter_command` ships so there is no reason to hand-write one. **Recurred live in a shell one-liner and is closed** |
| M-03c | a waiter exits only on success | **PREVENTED** | retirement is on any terminal state, asserted directly |
| M-03e | a stalled worker is terminated on a false positive | **PREVENTED by exclusion** | the release ships classification and no termination verb; a test enumerates the verbs no module may acquire. Ending a worker stays row 4. *Deferred proposal:* gated autonomous termination — trigger: a measured false-negative cost that exceeds the measured false-positive cost |
| M-03f | a dispatched worker never starts and holds the coordinator anyway | **PREVENTED, and the cause is now known** | the field failure twice over: 5h39m and 6h42m, both at ~0.3s CPU. **Root cause found and confirmed by repair: `codex exec` was reading stdin and waiting forever.** Closing stdin produced 11KB of progress in 20 seconds against 39 bytes in 5h39m. The deadline on every observable wait bounds it whatever the cause |
| M-03g | a superseded worker's result is consumed as current | **DETECTED_AND_BLOCKED** | evidence records the revision and digest it was gathered from; `close_gate(against=...)` refuses evidence about a different tree. A stalled worker whose subject is three commits behind cannot close its gate even if it returns |
| M-06a | a checker's guard depends on the name of a command rather than its arguments | **PREVENTED** | a verb whose read-onlyness is argument-dependent declares the forms it may take; the regression runs every allowlisted verb and asserts the repository is byte-identical afterwards |
| M-06b | a deadline that cannot be evaluated is treated as not yet passed | **PREVENTED** | an unparseable or undatable moment expires; the failure class the deadline exists to close is not reachable through a malformed field |
| M-06c | a blocker scoped to some work silences all of it | **PREVENTED** | a blocker stops the run only when every outstanding item is one it names; SILENT_IDLE is measured against the unblocked remainder |
| M-06d | a repair for a hand-written waiter ships an injection the hand-written one did not have | **PREVENTED** | the generated condition quotes its sentinel, and the regression asserts it by RUNNING the generated script rather than reading it |
| M-07a | a completion condition is satisfied by something the job did not produce | **PREVENTED** | a sentinel must be a regular file that does not predate its own wait; the declaration-time refusal is kept and the observation asks again, because a check nothing forces you through is a check on the honest path |
| M-07b | a rewrite mapping clears a citation on its own assertion | **DETECTED_AND_BLOCKED** | a successor claim is corroborated against the preserved original in a verified bundle or it is `REMAPPED_UNVERIFIED` and blocks. Adjudicating a rewrite stays a human act |
| M-08 | a context window ends and the coordinator's state ends with it | **PREVENTED** | state is derived from a file and never stored in a session; the seven-step rehearsal reconstructs it **in a separate process** that receives a path and nothing else, and step 6 asserts a reconstruction does not dispatch a second worker under an obligation already outstanding |
| M-09 | an audit is accepted without knowing which tree it read | **DETECTED_AND_BLOCKED** | it happened here: six of one reading's eight findings were about a snapshot two rounds old and nothing could tell. The brief states the revision and digest; the gate refuses evidence recorded about another tree |
| M-10 | a checker executes code belonging to the thing it is checking | **PREVENTED** | the diff family is run with `--no-ext-diff` and `--no-textconv`, and the options that re-enable them are refused. The switch rather than a config key, because it also disables the `.gitattributes`-selected driver no enumerable key set reaches. Both forms have a test that runs a program and asserts the marker is absent |
| M-11 | a scan reports clean about objects it did not read | **PREVENTED** | a skip makes the report INCOMPLETE and the exit non-zero. The skips were already recorded and simply not counted, which discloses a gap rather than closing one |
| M-12 | an object with two names is examined under one | **PREVENTED** | names come from `ls-tree` over every commit, deduplicated by (sha, path). `rev-list --objects` names an object once, so the second path was never enumerated rather than deduplicated afterwards |
| M-13 | blockers that jointly cover all work are individually scoped and stop nothing | **PREVENTED** | coverage is computed from the union. The round-2 repair changed the quantifier inside the predicate; this changes the set the predicate is asked about |
| M-14 | one task consumes another task's durable output as its own | **DETECTED_AND_BLOCKED** | `classify` reads the owner marker it was already writing; a mismatch is UNKNOWN, and `resume_plan` refuses to act on UNKNOWN, so it cannot become a retry |
| M-15 | a threshold a measurement is compared against is itself unmeasurable | **PREVENTED** | a non-finite stall horizon is refused, and a numeric capacity reading with no `observed_at` is refused. Both are the earlier non-finite rule one field over, which is where this class always is |
| M-16 | a test compares a pure function with itself | **PREVENTED** | the two digest tautologies are replaced by content-addressing oracles that fail if the digest reads filesystem metadata and fail if it ignores content |
| M-17 | a wait completes on work its named job did not do | **SAFELY_RECOVERABLE, and bounded honestly** | a sentinel must be a regular file that does not predate its wait; beyond that no property of a bare path names a producer, and `OUTPUT_ROOT` with a checked owner marker is the kind that does. A test pins both halves so the weaker claim cannot become the stronger one |
| M-18 | a repository being read chooses a program that runs | **PREVENTED, at the class rather than the route** | five routes in four rounds closed one at a time, then a check on the SHAPE of the config key: a program-valued key with no named closure refuses before anything runs. Keys with named closures are allowed, because the closure protects and obstruction does not |
| M-19 | a repository disables the check that inspects it | **PREVENTED** | an unreadable configuration is not an empty one; the discriminator asks the filesystem because it must work when Git is what is failing |
| M-20 | a concurrent reader bypasses a precondition another reader is inside | **PREVENTED** | the re-entrancy guard is thread-local; a module-level flag made one thread's inspection excuse every other thread's |
| M-21 | a commit message carries what the object walk cannot see | **PREVENTED** | commit messages are scanned alongside ref names, tag messages, paths and blobs |
| M-04 | one write too large to land leaves no artifact | **SAFELY_RECOVERABLE** | bounded chunks materialised by rename; a kill costs at most one chunk; an over-bound write is refused before it lands |
| M-04 (classify) | a retry decision is taken from a worker's status label | **PREVENTED** | four-valued classification from artifacts only; `UNKNOWN` never auto-resolves; a plan never reproduces a completed chunk |
| M-05 | a projection becomes a second authority | **PREVENTED** | writes nothing (proved by hashing the tree around a run), derives nothing, imported by no runtime tool module (its tests import it, which is what tests do), and names which side loses a disagreement |
| M-06 | the complete reachable history is never asked the strict question | **DETECTED_AND_BLOCKED** | `publication_history` asks it over every ref. The pack's own tree measures 2090 unadjudicated occurrences and that is disclosed, not rounded away |
| M-07 | a mechanical count is emitted as a remediation list | **PREVENTED** | the list is refused while any occurrence is unadjudicated, and an occurrence explicitly marked undecided blocks exactly as an absent one does |
| M-07 (per-term) | one classification covers many occurrences | **PREVENTED** | adjudication is keyed by finding, object, path **and location**; the per-term form is unexpressible |
| M-08 | a rewrite tool leaves a ref namespace nobody records | **DETECTED_AND_BLOCKED** | `refs/rewritten/*` and `refs/replace/*` are named private namespaces the publication gate refuses |
| M-09 | the one postcondition that must cross a boundary is disabled by the hardening | **PREVENTED** | a named per-invocation transport, scoped to the single verb that needs it, with the emptied ssh command lifted for that operation only. Every other read still refuses every protocol |
| M-10 | publication readiness is confused with publication safety | **COVERED** | the two are separate obligation sets; readability is profile-scoped and cannot borrow safety's urgency. *Deferred:* the full readiness dimension — trigger: a second measured occurrence |
| M-11 | a precondition measured where it is already satisfied names the smaller constraint | **DETECTED_AND_BLOCKED** | each profile declares the environment it is `reproducible_by`. *Deferred:* the clean-clone gate — trigger: a project with an external runner and a declared public profile. **The mechanism is disclosed, not hidden**: a profile claiming `public_clone` says so where a reader sees it |
| M-12 | formal conformance certifies unreadable public history | **COVERED** | the existing commit contract is preserved and its calibration obligation recorded. *Deferred:* a length ceiling — trigger: a project adopting one with its calibration. A ceiling met by damaging the artifact measures nothing |
| M-13 | a bulk record rewrite hardens hedges into claims | **DETECTED_AND_BLOCKED** | the two-oracle obligation ships with the rewrite invariants, and structural equivalence is stated to carry no evidence about truth |
| M-14 | a rewrite breaks an invariant nobody checks | **DETECTED_AND_BLOCKED** | invariants name the field they broke; an undemonstrated rollback is itself a finding; the pack performs no rewrite (D23 clause 6) |
| M-15 | a figure inside a human decision decays into human authority | **DETECTED_AND_BLOCKED** | a premise declares the command that produces it; closing re-runs it and **names the decision** that now rests on nothing. Compared exactly, not by substring |
| M-16 | an instrument cannot fail, samples where the property holds, or compares an implementation with itself | **DETECTED_AND_BLOCKED** | zero examined is never clean; an equivalence gate names the layer it enters each path at, in its own output |
| M-16e | a guard is decoration | **DETECTED_AND_BLOCKED** | every new guard in this release was mutation-checked, and **nine survived their first pass** — each forced a stronger oracle. The method is recorded because the count will not transfer |
| M-17 | the checker is stale, buggy, or is not the one you think you are running | **DETECTED_AND_BLOCKED** | a rule resolved by a search order must come from the declared root; every report names the file it read with its digest; the toolbelt's launch surface is declared and enforced. **Recurred three times in coordinator tooling this session** and each is recorded |
| M-18a | a later capability's commits invalidate an earlier one's evidence | **DETECTED_AND_BLOCKED** | an attestation carries the exact candidate it was taken against |
| M-18b | a closure names a commit and nothing keeps it reachable | **DETECTED_AND_BLOCKED** | reachability over the project's own records; an anchor is a ref or a **verified** bundle |
| M-18b′ | the first rewrite makes every citation in the corpus unresolvable | **PREVENTED** | the revision map ships with the check and is consulted for a commit Git can still resolve, which is what a local rewrite actually leaves |
| M-18b″ | the verdict goes green once the loss is irreversible | **PREVENTED** | a full-length token the repository lacks is `DESTROYED` and blocks, with its own headline. **Found by an auditor running the prune** |
| M-18c | a closure record's gate block is prose | **PREVENTED** | the block is generated from the contract's declarations, so omission is unrepresentable; the declared set is carried on the record, not only used by the generator |
| M-18d | a party audits a tree that is still moving | **COVERED** | every audit in this release ran against an immutable snapshot at a named revision, and the tree was verified stationary at dispatch. *Deferred:* a lease mechanism — trigger: a concurrent writer that the snapshot discipline does not stop |
| M-18e | running a declared profile mutates the evidence tree | **COVERED** | inherited from 2.2.0 unchanged |
| M-18f | hand-authored content in a generator-owned directory is cached, not stored | **PREVENTED** | a task output root under a declared generated tree is refused |
| M-19 | a gate with modes does not print its mode | **PREVENTED** | the mode is composed inside the headline, before the verdict, and the position is asserted |
| M-20 | a mandated audit's fallback executes without a human decision | **PREVENTED** | row 12 stands; the fallback for this session was **named by a human in advance** and, in the event, was not needed |
| M-21 | an adapter pin verifies files, not the executable | **DETECTED_AND_BLOCKED** | a declaration may name the program, how to ask its version, and the qualified version; the report says `N file(s), M executable(s)` and names what was never declared |
| M-22 | routing evidence is not comparable across projects | **SAFELY_RECOVERABLE** | `pool_id` and `qualification_basis` ship, three-valued so the existing log is not relabelled. *Deferred:* the full schema — trigger: a second project whose records cannot be compared for a reason the shipped fields cause |
| M-23 | contract, classification and sandbox gaps | **COVERED** | inherited from 2.2.0; no new evidence in this phase |
| M-24 | a write ceiling is prose with no runtime | **COVERED** | the task-owned output root covers the measured case. *Deferred:* a scope ceiling — trigger: an exceedance the output root does not catch |

## The mechanisms this release produced in itself

Recorded because a release that only lists inherited failures is not describing
its own risk.

| # | mechanism | disposition | proof |
|---|---|---|---|
| RP3-2 | a guard demands that a superseded release's own record be rewritten | **PREVENTED** | guards derive their document set from the gate record the manifest declares |
| RP3-17 | enabling a protocol is not enough when the program it needs was neutralised by emptying it | **PREVENTED** | the neutralisation is lifted for the operation that enables ssh, and only there |
| RP3-18 | two failures with opposite remedies arrive as one sentence | **PREVENTED** | the reason Git gave is part of the finding |
| RP3-19 | the non-regression gate calls a compatible addition a break | **PREVENTED** | an appended keyword-capable parameter with a default is reported as what it is |
| RP3-22 | the pack cannot check its own commits with the vocabulary it publishes | **PREVENTED** | `--default-terms`, resolved canonically and reported with its digest |
| RP3-26 | a live project's contract is a schema generation behind and is told only that its type is wrong | **DETECTED_AND_BLOCKED** | the legacy shape is named as legacy with its migration; the entries are **not** migrated automatically, because the two tiers differ in what they scan |
| RP3-27..31 | the five causes of the live 5h39m silence | **PREVENTED** | see the C15 section of the gate record and `test_silent_idle_closure.py` |

## What is NOT closed, stated plainly

These are the release's real residue. None is a mechanism that can recur
unnoticed; each is a bounded, disclosed condition.

1. **2090 unadjudicated public-safety occurrences in this repository's own
   history.** The mechanism that finds them ships and works; the adjudication is
   owed before any first remote. This is `DETECTED_AND_BLOCKED` for a consumer
   and **an open obligation for this pack itself** — a private remote does not
   resolve it, and the release says so.
2. **The D18 layout defect.** One real project pins the pack's working checkout.
   The mechanism that notices it ships; the layout move affects a live project
   and is the founder's. Every session since has avoided the hazard with a
   worktree rather than removing it.
3. **Two stalled processes this coordinator may not end.** Classified, holding
   no work, escalated under row 4. The limitation is reported rather than
   crossed.
4. **The adapter executable path is unexercised by any real declaration.** The
   mechanism is demonstrated against the live installation; no project declares
   one yet.
5. **The capacity gate has never seen a live provider reading.** The arithmetic,
   the refusals and the conservative posture are exercised; whether a real
   reading arrives in the shape the gate expects is not established.
