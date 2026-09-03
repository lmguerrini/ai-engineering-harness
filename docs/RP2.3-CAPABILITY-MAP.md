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

*(appended as each capability reproduces its own)*
