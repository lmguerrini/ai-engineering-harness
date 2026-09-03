# RP2.3 — capability map and dependency order

The evolution session's working plan. Written before implementation, from the
mechanisms rather than from the summary that recommends them, and updated only
by appending.

Baseline: `2.2.0` at `d70d72fbcadb98cb8a2979f9c63ed84e595662e8`, state
`QUALIFIED_AND_FROZEN`, tree digest
`4bab6b8d505735f164e928e36eca674835f38478d5d5f334d740fa41c49c5a24`, verified with
the shipped `pack_pin.py` and again with an independent re-implementation of
`sha256-framed-v1` written from the algorithm description rather than by
importing the module under test. The suite passes at that frozen revision; the
count is the baseline manifest's `tests.passed` and is not restated here.

## Scope classes

`MUST_THIS_RELEASE` — a measured failure class that destroys work, closes a
window on its own, or lets an incorrect claim reach a human. Anything the above
need in order to be safely usable.

`SHOULD_THIS_RELEASE` — small, strongly evidenced supersets whose implementation
and qualification cost is low.

`DEFER_WITH_TRIGGER` — everything whose return is not clearly positive in this
session. Each carries the observation that reopens it.

## Capabilities, in dependency order

| # | Capability | Class | Depends on |
|---|---|---|---|
| C1 | Architecture record and session governance | MUST | — |
| C2 | Checker hygiene: the instrument before the measurement | MUST | C1 |
| C3 | Durable worker output, bounds and recovery | MUST | C2 |
| C4 | Coordinator continuation and liveness state | MUST | C3 |
| C5 | Progress, stall and waiter lifecycle | MUST | C4 |
| C6 | Adapter and routing identity | MUST | C2 |
| C7 | Capacity-aware pre-dispatch gate | MUST | C5, C6 |
| C8 | Remote verification across a real transport | MUST | C2 |
| C9 | History, refs and closure anchors | MUST | C8 |
| C10 | Complete-history public safety and the publication profile | MUST | C9 |
| C11 | Evidence and close correctness | MUST | C2 |
| C12 | The diagnostic projection | SHOULD | C4, C5, C7 |  *(shipped on human decision; see the gate record)*
| C13 | Launch, migration and compatibility | MUST | C3–C11 |
| C14 | Rehearsal, qualification and release candidate | MUST | all |
| C15 | Closing ACTIONABLE_WORK + SILENT_IDLE | MUST | C4, C5, C12 |

**C2 comes second, and the ordering is the point.** The rehearsal obligations
this release must satisfy are unconditional about it: *every rehearsal's own
tooling is subject to the checker-hygiene rules*. Building the instruments after
the measurements they validate is how a release qualifies itself with a stale
copy of its own rule — measured three times in one phase, in both directions.

**C3 before C4** because a state machine's transitions must be reconstructible
from durable artifacts, and C3 is what makes those artifacts exist.
**C6 before C7** because a capacity gate that cannot say which pool a dispatch
draws on cannot distinguish the failure it exists to prevent.
**C9 before C10** because the publication gate's candidate list is a list of
historical objects, and remediating one is a rewrite: the invariants have to
exist in the same release as anything that produces the list.

## The two orderings that are not preferences

1.  **Detection without adjudication makes matters worse.** A complete-history
    scan produced 147 findings of which 4 were genuine and 106 were ordinary
    English, and one flagged entry was material whose removal would make the
    repository *less* safe. A gate emitting a raw count as a remediation list
    manufactures pressure to rewrite history to remove nothing. C10 ships both
    halves or neither.
2.  **A projection over a state nothing transitions displays a stale value
    confidently.** The decisive recorded instance would have shown
    `WAITING_ON_JOB` for two hours and twenty-one minutes and been wrong. C12
    is downstream of C4 and C5, and that is why it sits where it does.

## Removed from scope, deliberately

*   **Autonomous termination of a stalled worker.** The only destructive
    autonomous action in the candidate set. A false positive is *measured* — a
    healthy worker produced no log output for over four minutes while its CPU
    time climbed — and the destructive half of a detector is not carried by the
    evidence that earns the detecting half. C5 classifies; ending a worker stays
    a coordinator action under `policy/hitl-matrix.md` row 4.
*   **An observer that restarts a coordinator.** D23 clause 4. The requirement is
    evidenced by three human restarts totalling more than six hours; the
    mechanism needs a session-creation primitive that was established not to
    exist on the inspected surface. Recorded as an Evolution Candidate with its
    trigger, not designed here.

## Deferred with a trigger

| deferred | trigger that reopens it |
|---|---|
| the full routing-evidence schema | *its own* caution applies: a schema fixed before enough projects have expressed the need fixes the wrong fields. C6 ships pool identity, qualification basis and the additive rule. Reopens when a second project's routing records cannot be compared for a reason the shipped fields cause |
| the clean-clone reproducibility gate | it needs a runner the project does not control. C10 ships the per-profile declaration. Reopens when a project has an external runner and a declared public profile |
| a commit-subject length ceiling | measured on both sides: a ceiling met by damaging the artifact is not measuring what it claims. Reopens when a project adopts one and can show the calibration |
| publication readiness beyond the profile declaration | safety and readability are different questions and readability must not borrow safety's urgency. Reopens on a second measured trigger |
| a write-ceiling runtime for delegation scope | C3's task-owned output root covers the measured case. Reopens when a scope ceiling is exceeded in a way the output root does not catch |

## Reproduced before repair

Every entry is reproduced by execution against the frozen baseline before any
repair is written, and recorded here as it is done. Reproductions that turn out
to be artefacts of the harness rather than the code are recorded too, because a
discarded finding is evidence about the oracle.

| ID | Defect | Reproduction |
|---|---|---|
| RP3-1 | an adapter pin verifies the files an adapter is made of, and reports success while the executable those files drive is a different version from the qualified one | live at this baseline: the qualified executable version and the installed one differ, `adapter_pin.py` reports `4 of 4`, and the only record of the qualified version is a sentence in a note nothing compares to the path |
| RP3-2 | two release guards disagreed about whose documents they check, and the one that was wrong demanded a superseded release's own gate record be rewritten | appending a decision put the previous release's packet and changelog entry in breach of a guard whose sibling exempts them in terms |
| RP3-3 | a gate with two modes names neither in its headline | one range, one vocabulary: the tiered run prints `clean`, the strict run prints `1 leak(s)`, and neither headline says which ran |
| RP3-4 | an instrument that examined nothing reports a result | a range resolving to no commits renders `clean (0 commits, 0 blobs)` |
| RP3-5 | a checker silently reads a stale copy of its own rule | a project declaring a pack root whose term set is absent gets the copy beside its own contract, applies it, and no report says which file was read |
| RP3-7 | an equivalence gate does not name the layer it enters each path at | the public-surface gate's honest gap lives in a docstring and `--help`, neither of which is stored beside the verdict |
| RP3-8 | a durable output path does not bound the write that fills it | one write over the backend's output limit leaves no artifact, and its absence is indistinguishable from never having started — 27 records, then 81 across a wave |
| RP3-9 | a retry decision taken from a worker's status label discards work the worker left behind | three of six killed workers left usable bytes; one left a complete generator it never ran, worth 22 records |
| RP3-10 | a task's output root can be a directory a generator owns | a correct destructive rebuild destroyed two hand-written documents inside one |
| RP3-11 | a coordinator's declared wait is prose, so it cannot have a transition | four distinct situations — finished, capacity-blocked, waiting on a live job, idle with authorised work — produce one identical observable, and the decisive instance declared its wait correctly and still went silent for 2h 21m after the job exited |
| RP3-12 | liveness read from one signal produces the mirror-image error of reading it from process existence | a hung run at 0.05s of processor time over 31 minutes, and a HEALTHY run silent on its log for over four minutes while processor time climbed — one detector cannot tell them apart, and the action a stall invites destroys work |
| RP3-13 | a waiter that matches on a pattern matches itself | one worker acquired three waiters whose patterns matched each other's command lines, so none could terminate while any sibling lived; four notifications fired after the job had exited |
| RP3-14 | routing has no capacity model, and a recorded rule was valid only under a precondition it never stated | eight workers in two waves on the coordinator's own rolling window: two complete, three partial, three nothing, 81 records lost. Weekly capacity was never the binding constraint |
| RP3-15 | the rule that authority attaches to the task had no field on a task to attach to | its own rehearsal could only pass on a hand-labelled fixture |
| RP3-16 | the one check that must cross a boundary is disabled by the hardening that protects every other read | `ls-remote` on an `ssh://` remote returns `transport 'ssh' not allowed`, so the single observation of what a push actually did is unavailable on every real transport |
| RP3-17 | enabling the protocol is not enough, because the ssh command was neutralised by emptying it | with the transport allowed, the read fails `cannot run :` / `unable to fork` — the same non-functional postcondition in different words. The module records this exact lesson for `diff.external` two entries above the key it set to empty |
| RP3-18 | a failure to read a remote reports only that it failed | a refused transport and a host that does not resolve both arrive as `git invocation failed`, and one is a setting this pack controls |
| RP3-19 | the non-regression gate reports a compatible addition as a break, and its own message says callers would break | adding a keyword-only parameter with a default to a public function turns the gate red; no call written against the previous signature would fail |
| RP3-20 | a closure record names a commit and nothing keeps it reachable | a branch rebuild orphans a cited commit; the citation resolves for as long as a reflog keeps it and then stops, with no event to notice |
| RP3-21 | a reachability check shipped without a revision map fails closed across a whole corpus after the first rewrite | every commit-shaped token stops resolving at once, and the old commit remains resolvable-but-unreachable so a map consulted only on unresolvable tokens misses all of them |
| RP3-22 | the pack cannot check its own commit messages with the vocabulary it publishes | this repository has no project contract, so `--project` has nothing to read and the shipped gate can only check structure — which is why a coordinator wrote a substitute instrument, and the substitute manufactured a finding on `resolves` |
| RP3-23 | the strict tier and the complete reachable history are never combined by any shipped invocation | a term committed and then deleted survives in a blob that the staged scan, the working tree and `ls-files` all miss, while the range scan that would see it runs at the tier that does not apply the rule |
| RP3-24 | a closure record's gate block is prose, so a profile nobody ran is indistinguishable from one that passed | two capabilities closed green over red gates, and nothing compared the sentence to a run |
| RP3-25 | a measurement inside a human decision record is never re-checked, and nothing downstream questions a ruling | one ruling was taken on a figure a later commit falsified, and the decision went on standing |
| RP3-26 | a live project's contract is written to the pre-2.1 schema, unreadable by every tool since, and told only that its type is wrong | `private_terms:` as a list refuses with a message about a mapping; nothing names the schema generation or the migration, and the refusal is identical at the frozen 2.2.0 baseline |
| RP3-27 | a declared wait has no deadline, so a live process satisfies it forever | measured LIVE during this session: a dispatched auditor held the coordinator 5h39m with 0.34s of processor time, no output and no provider rollout, and the state model could say WAITING_ON_IDENTIFIED_JOB indefinitely |
| RP3-28 | the stall classifier compares its horizon against the gap between two samples, not against how long the run has been flat | the same incident, sampled 90s apart against a 900s horizon, classified RUNNING — a caller who polls can never obtain a stall verdict |
| RP3-29 | a hand-written waiter matches its own command line | `until ! pgrep -qf "codex exec"` — `pgrep` returned the waiter's own pid, so it could not terminate even after the worker exited. RP3-13 recurring, in a shell one-liner that bypassed the mechanism that refuses it |
| RP3-30 | a blocker with no stated scope silences work it has nothing to do with | one human decision on two stalled processes reported a whole capability BLOCKED_ON_HUMAN while five authorised items sat undone |
| RP3-31 | no continuation record existed for the coordinator's own run | the mechanism shipped in this candidate and its primary intended caller never wrote one, so nothing could derive a state |
| RP3-32 | a rewrite mapping cleared a citation by naming any reachable commit | the successor being reachable is a test every reachable commit passes, so the mapping was accepting its own assertion as its evidence |
| RP3-33 | `check_reachability(mapping=...)` took an abbreviated revision `load_mapping` refuses | a validating loader beside an unvalidated keyword is a validated path, and callers take the other one |
| RP3-34 | a wait completed on `/dev/null` for a worker that never existed | the declaration-time refusal was right and unreachable: the record was built directly, so the observation had to ask again |
| RP3-35 | a wait completed on any pre-existing regular file | a path last written before the wait was declared did not come from the job being waited on |
| RP3-36 | a close gate accepted evidence gathered from a different tree | six of one audit's eight findings were about a snapshot two repair rounds old, and nothing in the gate could tell |
| RP3-37 | a dispatched auditor read stdin and waited forever, twice, for a total of 12h21m | the two hangs were the dispatcher's defect and not the route's; the deadline bounded them anyway, which is the property that survives the next unknown cause |
| RP3-38 | a coordinator's state lived only in a context window | the seven-step rehearsal reconstructs it in a separate process given a path and nothing else |
| RP3-39 | a read-only git interface ran a program the subject repository named, with and without the flag | the neutralised-config table named the right switch in a comment and the code never passed it |
| RP3-40 | a complete-history scan reported clean while printing what it had not read | a skip was recorded honestly and then not counted, which discloses a gap rather than closing one |
| RP3-41 | two paths sharing one blob produced one occurrence | `rev-list --objects` names an object once, so the second path was never enumerated at all |
| RP3-42 | two blockers each covering half the work left the run reporting nothing outstanding | coverage is a property of the union; the round-2 quantifier repair was one level too deep |
| RP3-43 | another task's complete output root classified as this task's result | the owner marker was written for exactly this and only the writer read it |
| RP3-44 | a non-finite stall horizon produced STALLED and RUNNING | the signals were guarded a round earlier and the figure they are compared against was not |
| RP3-45 | a capacity reading with no `observed_at` gated a dispatch | the class docstring said the timestamp mattered as much as the figure |
| RP3-46 | two digest tests compared a pure function with itself | replaced by the content-addressing property they were standing in for |
| RP3-47 | `cat-file --filters` ran the repository's own filter chain | the second hardening closed the routes visible from where it stood |
| RP3-48 | `diff --submodule=diff` ran the submodule's configured program | a nested Git process never sees the parent's command line |
| RP3-49 | `core.gitProxy` ran a program through the one enabled transport | the key is multi-valued, so environment config appends to it and cannot replace it |
| RP3-50 | a symlinked owner marker let one task read another's finished work | `is_file()` follows a link, which is the one shape the previous two owner repairs could not see |
| RP3-51 | an owner marker holding `null` raised an AttributeError | a four-valued contract returned a traceback |
| RP3-52 | an audit was killed by its provider and wrote a zero-byte report | its stderr held five real findings, recovered before any retry |
| RP3-53 | a record field added to the dataclass alone was dropped by save and load | the boundary the record exists to survive enumerates its fields twice |
| RP3-54 | the projection could not show whose tree an audit was about | a dashboard cannot render what the authoritative record does not carry, and the repair belongs in the record |
| RP3-55 | a remote the repository configured ran its own program during `ls-remote` | the fifth execution route, inside the one exception that lets an operation cross a boundary |
| RP3-56 | a linked chunks directory lent one task another's finished work | the marker was checked and the artifacts were read from wherever the directory pointed |
| RP3-57 | a saved record naming work that is not a name raised out of the derivation | untrusted input reached a set |
| RP3-58 | a sample taken at a NaN time manufactured a stall | the signals and the horizon were guarded and the moment was not |
| RP3-59 | a branch name and an annotated tag message scanned clean | a ref name is published with the repository and was not history to this scanner |
| RP3-60 | a verified bundle was read as corroborating a rewrite mapping | a bundle proves preservation and says nothing about identity |
| RP3-61 | the close gate's tree check was optional | an optional check is a check nobody performs, and the empty problem list is the pass |
| RP3-62 | a delegation test passed with its subject deleted | it searched source text for a name instead of watching the call |
| RP3-63 | five execution routes in four rounds, each closed where the last repair could not see | the check was an enumeration of routes and the population was open-ended |
| RP3-64 | the general check failed open when a repository broke its own configuration | the discriminator needed Git, and Git was what the repository had broken |
| RP3-65 | the general check re-entered itself and never finished | a guard on the verb was a guard on one of the paths the function takes |
| RP3-66 | the general check hijacked a timeout and a parse error belonging to the caller | a precondition answering a question the caller did not ask |
| RP3-67 | a second thread's read skipped the inspection a first thread was inside | a guard against self-recursion written as a guard against everyone |
| RP3-68 | a private term in a commit message scanned clean | the blob walk skips commits because they are not blobs |
| RP3-69 | a write bound that was not a number raised out of the derivation | the pid repair was written for the pid rather than for the class |

*(appended as each capability reproduces its own)*
