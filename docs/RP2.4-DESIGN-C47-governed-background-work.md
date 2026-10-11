# DESIGN — C47 one governed waiting path, and a selector that cannot report zero as green

**Change class:** MATERIAL
**Base revision:** 20e826c68ae170cd5db70835ec4ccb4fa4284367
**Frozen:** yes

Two properties, one architectural lesson, and both were established by live
execution in this session rather than by reasoning about what might happen.

## The mechanism

`continuation` holds a durable wait and derives a state from it, and
`progress.waiter_command` builds a waiter that cannot match its own command
line — but nothing binds the two, nothing refuses a waiter built any other way,
nothing reconciles a wait whose producer has ended, and the two modules answer
*has this process finished* differently, so a coordinator can create a second
waiting mechanism the pack cannot see and a zombie producer stays RUNNING in the
durable model forever.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Prohibit ad-hoc waiters in prose and leave the mechanisms as they are | REJECTED | It is what 2.3.0 already did. The waiter builder shipped with a docstring naming this exact failure, and the coordinator hand-wrote three self-matching monitors anyway, in the session that ships it. A rule whose only enforcement is that somebody read it has been measured, twice, not to hold |
| 2 | A new background-job registry module owning launch, wait, completion and reconciliation | REJECTED | It puts a SECOND place that knows about waiting beside `continuation`, which is the bypass this change exists to close, reproduced as architecture. It also has Core launching workers, which D14 forbids — invoking a worker is the adapter's business and a pack that ran them would have to know every provider |
| 3 | Allow custom monitors, validated at registration | REJECTED AS THE WHOLE ANSWER, KEPT AS A CLAUSE | Validation is necessary and insufficient: it only ever sees a monitor somebody chose to register, so the unregistered one — the actual failure — stays invisible. It is the refusal path inside design 4, not an alternative to it |
| 4 | Extend the wait that already exists: a declared wait may carry its waiter, the waiter is refused unless it is governed, one process-liveness answer serves both modules, and a reconciliation derives the eight dispositions from the durable record and the process table | SELECTED | The smallest change that makes the bad path structurally hard rather than discouraged. It adds no second registry, no new authority and no launcher; it makes the existing durable declaration the only thing that can hold a wait, and makes an ungoverned waiter a refusal at the boundary a wait is written rather than a note somebody may read |

### Why the selected design is the smallest one that works

Three facts decided it.

**The durable wait already carries almost everything.** `Wait` has a job id, a
kind, an expected result, a producer pid, a path, a deadline, a subject revision
and digest, `consumed` and `retired`. What it lacks is the waiter itself and a
vocabulary for *what became of this*. Adding a second registry to hold those
would mean two records disagreeing about one wait.

**The two modules already disagree about one question.**
`progress.waiter_command` treats a zombie as ended and says why;
`continuation._process_is_gone` asks `os.kill(pid, 0)`, which succeeds for a
zombie, so the durable model reports a finished producer as running forever.
Reproduced here against a real unreaped child. One question gets one answer, and
it is the repaired one.

**The failure is invisible, not permitted.** Nothing tonight was forbidden and
did it anyway; the coordinator simply waited somewhere the pack has no view of.
So the repair is not a prohibition. It is to make the *recorded* path carry the
waiter, and to make an unrecorded one nameable — `UNGOVERNED_BACKGROUND_WORK` —
so a reader sees the gap instead of an empty list.

## The second property: zero selected is not green

A targeted run that executes none of the tests it names exited 0 and was very
nearly read as a forty-five-fold speed-up. **`exit status 0` is not evidence
that the intended check ran.** A selector used as evidence records its intended
selector, what it collected, what it executed, what it skipped and its exit
status, and answers `NOT_EVIDENCE` when it collected fewer than expected.

This binds performance work too, and indicts this session's own measurement: a
comparison between two runs is admissible only if both ran the **same test
population**. A faster run over fewer tests is not a faster run.

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | A coordinator waits in a shell and records nothing, so the pack still cannot see it | Not closed, and not claimable as closed: the pack cannot police the coordinator's shell without becoming the thing it refuses to be. What changes is that the recorded path now carries the waiter, so an unrecorded wait is a wait somebody chose not to declare rather than one the mechanism had no room for. Stated as a bounded limitation, with `UNGOVERNED_BACKGROUND_WORK` as the name a reader sees |
| 2 | A waiter validator passes a self-matching monitor because the pattern is built at runtime | The validator refuses command-line matching outright — `pgrep -f`, `pkill -f`, `ps | grep` — rather than trying to decide whether a particular pattern is safe. A rule that has to reason about the pattern is a rule that can be argued with |
| 3 | Reconciliation calls a live producer finished and a stale waiter is retired under a running job | The producer's own state decides, read through `ps` and never through the monitor's existence; and retiring is a caller's act on a classification, never something reconciliation performs |
| 4 | A superseded job blocks the current candidate because nothing compares subjects | `Wait.subject_revision` already exists and is compared against the candidate revision when the caller supplies one; where it does not, the answer is `UNKNOWN` rather than "current" |
| 5 | PID reuse makes a different process look like the producer | Named, not solved. `os.kill`/`ps` answer about a NUMBER, and the honest bound is already in `_process_is_gone`'s docstring. A completion artifact — an exit file or an owned output root — is what distinguishes producers, and the kinds that use one are preferred |
| 6 | The selector guard passes because the expected count is derived from the run it is checking | The expected minimum is an argument the caller states, never read back from the result, and a mutation drops it to zero to prove the guard is what refuses |
| 7 | An optimization silently changes the test population and reads as a speed-up | A comparison refuses unless both runs report the same collected and executed counts |
| 8 | The dashboard shows a job as running because a monitor exists | The panel derives from the reconciliation, which reads the producer; a monitor is not an input to it |

## Authority boundaries

**It may decide:** whether a waiter is governed; what disposition a recorded
wait carries; whether a selector run is evidence.

**It must never decide:** to launch a worker, to end one, or to retire a wait.
Reconciliation reports; retiring is the coordinator's act, and terminating a
worker stays a human decision (`policy/hitl-matrix.md` row 4), which this does
not touch. It signals nothing: asking `ps` for a state is an observation.

No HITL row is added, removed or weakened. Row 4 keeps its human for ending a
worker, and this change makes the ending *unnecessary* in the common case rather
than easier.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O1 | ACCEPTANCE | A zombie producer is finished, in `continuation` as it already is in `progress`, and both modules answer through one implementation | `tools/tests/test_background_governance.py -k zombie` |
| O2 | NEGATIVE | A waiter that greps a command line is refused as `UNGOVERNED_BACKGROUND_WORK`, including one whose pattern appears in its own text | `tools/tests/test_background_governance.py -k self_matching` |
| O3 | NEGATIVE | A `Wait` carrying an ungoverned waiter is refused where the wait is declared, not merely reported later | `tools/tests/test_background_governance.py -k refused_at_declaration` |
| O4 | ACCEPTANCE | Reconciliation classifies each of the eight dispositions from the durable record and the process table, with a reason | `tools/tests/test_background_governance.py -k disposition` |
| O5 | NEGATIVE | A completed producer is never `LIVE_AND_PROGRESSING` because a monitor survived; the monitor is not an input | `tools/tests/test_background_governance.py -k monitor_is_not_evidence` |
| O6 | NEGATIVE | A wait naming a different subject than the candidate is `SUPERSEDED` and cannot block it | `tools/tests/test_background_governance.py -k superseded` |
| O7 | ACCEPTANCE | A fresh process reading only the durable record reconstructs the same dispositions and no phantom work | `tools/tests/test_background_governance.py -k cold` |
| O8 | NEGATIVE | A selector collecting zero tests is `NOT_EVIDENCE` however the command exited | `tools/tests/test_selector_evidence.py -k zero` |
| O9 | NEGATIVE | A comparison between two runs is refused when their test populations differ | `tools/tests/test_selector_evidence.py -k population` |
| O10 | MUTATION | Reverting the zombie answer, the self-match refusal, the declaration refusal and the zero-selector refusal each fails a test that passes now | `tools/tests/test_background_governance.py tools/tests/test_selector_evidence.py` |
| O11 | REHEARSAL | The three self-matching monitors this session actually ran are refused by the validator, verbatim | `tools/tests/test_background_governance.py -k the_monitors_this_session_ran` |
