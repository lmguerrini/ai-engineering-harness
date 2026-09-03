# RP2.3 — gate record

What happened, in the order it happened, including what the coordinator got
wrong. Appended to as each capability closes; never rewritten.

**Version `2.3.0`, state `IN_PROGRESS`.** No project may adopt this candidate. Moving it to
`QUALIFIED_AND_FROZEN` is a human decision (`policy/hitl-matrix.md` row 2) and
the coordinator does not take it.

## Baseline

    version   2.2.0
    revision  d70d72fbcadb98cb8a2979f9c63ed84e595662e8
    digest    4bab6b8d505735f164e928e36eca674835f38478d5d5f334d740fa41c49c5a24
    state     QUALIFIED_AND_FROZEN

Verified before anything was created, by two means that do not share code: the
`pack_pin.py` that ships inside the release, and an independent
re-implementation of `sha256-framed-v1` written from the algorithm's prose
description rather than by importing the module under test. Both produced the
recorded digest over the recorded file count. Untracked, non-ignored files in
the release root: none. The suite passes at that revision; the figure is the
baseline manifest's own `tests.passed` and is not restated here.

**The evolution workspace is a worktree, and that was not a convenience.** One
live project pins the pack's *working* checkout by root path — the layout defect
`DECISIONS.md` D18 records and the 2.2.0 manifest names as the finding that most
deserves a decision. It verifies today only because that checkout happens to sit
on its pinned revision, so checking a branch out in it would have broken a
currently-verifying pin. A worktree leaves the pinned root untouched. Both live
pins were re-verified after the workspace was created and both still pass.

## Session authorisations

Recorded here because `policy/BUDGETS.md` requires it and because an
authorisation nobody can find later is one nobody can audit.

| | |
|---|---|
| Repair / audit counters | `policy/BUDGETS.md`, RP2.3 column. Repeats RP2.2's numbers rather than raising them |
| Cross-vendor fallback | named in `policy/auditor-strategy.md`: a second blind same-family auditor on a distinct lens, only after the cross-vendor channel has been attempted and refused, recorded as *not cross-vendor* |
| Version class | MINOR, following `DECISIONS.md` D24 rather than preceding it. The mandatory-versus-declared fork was the human decision; the number follows from it |
| Fan-out | none requested and none authorised. `policy/routing-policy.md`'s ban on standing fan-out opt-ins stands. Dispatches are serial, and the measured reason is eight parallel workers on a shared window returning two results and losing eighty-one records |

## Qualification

The suite count is not written here. Adding a test changes it, and a figure this
document's own edit invalidates is one it must not carry — it lives in
`PACK_MANIFEST.json` `tests.passed`, recorded by the same collection the check
re-runs.

Delta against the frozen baseline: **not stated here.** Editing this file
changes it. Measure it:

    git diff --shortstat d70d72fbcadb98cb8a2979f9c63ed84e595662e8 -- .

## Measured overhead

Held prose, measured at this point in the session and re-measured at close
(`policy/BUDGETS.md`):

    in-release (skills/core/*.md + policy/*.md)   1519
    installed adapters, outside the envelope      1023
    total against a ~2,000 target                 2542   27.1% over the ~2,000

**The breach is inherited and it has grown.** 2.2.0 recorded 2486 on the same
rule and declined to shave it, on the ground that re-scoping a rule to fit its
number deletes the disclosure rather than the excess. That reasoning still
holds and it is not a licence. This session applied *delete before adding* where
it could — a sentence duplicated word for word inside `auditor-strategy.md` was
removed rather than left beside its new neighbour — and it did not cover the
addition. A held-prose pass is owed before qualification, and it is recorded as
owed rather than described as done.

## Capabilities

### C1 — Architecture record and session governance

`DECISIONS.md` D23 records the founder architecture decision this release rests
on, additively, in the form D14 established. D24 records the rule that decides
the version class: an obligation an adopting project cannot fail to satisfy is
mandatory, one that needs new project capability is declared.

`docs/RP2.3-ARCHITECTURE.md` states the only thing the layering picture gains —
the first machine-written, machine-transitioned state in the pack's history —
and the three properties that keep it from being a second authority.

`docs/RP2.3-CAPABILITY-MAP.md` is the plan, its dependency order, the two
orderings that are not preferences, and what was removed from scope.

**RP3-2 — a guard demanded that a superseded release's own gate record be
rewritten.** Found by appending a decision, which is the ordinary act it was
written to survive.

`test_every_pointer_at_the_decision_layer_reaches_the_last_decision` requires
every `D<n>-D<m>` range to name the highest decision on file, and scanned a
typed literal `docs/RP2.2-*.md`. Appending D23 and D24 put two documents in
breach: the previous release's packet, and the previous release's own CHANGELOG
entry. Both were true when written. Its sibling guard,
`test_no_document_restates_a_count_of_things_the_repository_can_count`, already
exempts prior releases' documents in terms — *rewriting them to satisfy a rule
invented afterwards is the one thing this pack's own policy forbids* — so the
two guards disagreed about whose documents they were checking, and the one that
was wrong was the one nobody was looking at.

Repaired at the root rather than at the symptom. Both guards now derive their
document set from the gate record the manifest declares, so a checker that reads
the declaration cannot disagree with it. The CHANGELOG is scoped to the entry
this release is adding, by the reader that already existed for the version
check. Both guards now also refuse to pass having scanned nothing, because a
glob that matches no files is indistinguishable afterwards from a glob that
found no offenders — the defect class this release exists to close, occurring in
the instrument on its first day.

Two further literals were derived rather than retyped: the baseline revision the
non-regression differential runs against, and the release whose held-prose
figure this one quotes. The second was hardcoded to `2.1.1`, so a release
comparing itself to 2.2.0 would have searched for a sentence nobody would write
and failed with a message about the wrong release.

### C2 — Checker hygiene: the instrument before the measurement

Second, and the ordering is the point. The rehearsal obligations this release
must satisfy are unconditional about it — *every rehearsal's own tooling is
subject to these rules* — so building the instruments after the measurements
they validate would qualify the release with the same class of defect it exists
to close.

`tools/instrument.py` carries four refusals and one output requirement. Nothing
in it is about whether a check is *correct*; all of it is about whether the
answer is interpretable, which is a different property and the one that failed.

**RP3-3 — a gate with two modes named neither.** Reproduced on a scratch
repository at the frozen baseline: one range, one vocabulary, two tiers. The
tiered run printed `clean`; the strict run printed `1 leak(s)`. Neither headline
said which tier produced it, and the staged gate hid its mode in a suffix on the
provenance line, where a reader taking the first line of a stored report never
sees it. The same shape appeared on a real tree, where the two tiers' counts differ,
and a recorded limitation then quoted one of those counts without its tier —
proposing a remedy that could not have cleared the hits the other tier finds.
Repaired: the mode is composed *inside* the headline, before the verdict, and a
test asserts the position rather than the presence.

**RP3-4 — a scan that read nothing reported `clean`.** Reproduced:
`clean (0 commits, 0 blobs)`, byte-comparable to a range that was read and found
safe. `NOTHING EXAMINED` is now a third verdict with its own exit status — `2`,
this module's existing code for a verdict it could not reach — and the report
says what the usual cause is, because it is almost always a baseline or a ref
that is not the one the caller meant. Deliberately not a refusal of empty
counts in general: a range with one commit and no blobs is a real observation,
and a guard that refused it would refuse correct work.

**RP3-5 — a checker silently read a stale copy of its own rule.** Reproduced
against the frozen baseline, and this is the one that was not on the inherited
list. `_load_default_terms` searched three locations in order — the declared
pack root, the module's own root, then *the directory beside the project's own
contract* — took the first that existed, and reported only how many terms it
had loaded. A project that declares a pack root whose rule is missing therefore
got a copy from its own working directory, applied it, and had no way to find
out. The same shape elsewhere was measured at nine refusals where the real count
against the current rule was one.

Repaired in two halves, because either alone is insufficient. A search order
that lands outside the declared root is now a **refusal** naming both the file
it refused and everything else it looked at; and every scan reports the file it
actually read, with its digest, so a surprising finding count can be attributed
to the tree or to the checker before anyone starts editing history. Verified
read-only against a live 215-commit consumer repository: the mode, the counts
and the rule's path and digest all appear.

**One candidate is not a search order**, and the distinction is reported rather
than flattened. A project naming exactly one absolute location has not been
substituted against — it asked for that file, the choice is visible in its own
contract, and the digest is in every report. That resolution is labelled
`declared`, distinct from `canonical`; refusing it would have refused a real
consumer shape, which is how this class of control fails in the other
direction.

**RP3-7 — an equivalence gate that never named the layer it entered.**
`surface_diff` compares two revisions' public Python surface and carries an
honest gap — class attributes, dataclass field types, base classes, nested
classes — in its docstring and its `--help`, neither of which is stored beside
the verdict. The class this belongs to survived six audit cycles and twelve
blind legs elsewhere: a parity gate compared two transports' already-decoded
arguments and was structurally unable to see that the two decoders disagreed
about what the same request text meant. The layer statement now prints with
every verdict, clean ones included, and an equivalence report missing either
side is refused at construction.

**The toolbelt's launch surface is declared and enforced.** Every read it
performs is a Git invocation through one function, so `gitread` declares
`launches=("git",)` with its reason, and the launch helper refuses an executable
the declaration does not name. The instance behind this crossed a host security
boundary by launching a browser; the version of the rule that was a note had
already failed four times.

**Mutation-checked, eight for eight.** Each guard was broken deliberately and
the suite went red: the empty-count check forced false, the mode appended after
the verdict instead of inside it, the root check disabled, the launch check
made permissive, the equivalence-side check removed, the layer statement not
printed, the nothing-examined exit folded back into `0`, and the staged mode
returned to the provenance line. A killed mutant proves the check can fail, not
that it asks the right question — the pinned-test-asserting-the-buggy-value
case is why that sentence is here rather than a claim of correctness.

### C3 — Durable worker output, bounds and recovery

The first of the two capabilities whose absence **destroyed** work rather than
delaying it. `skills/core/worker-contract.md` already required a durable file;
the gap was that a durable path is necessary and not sufficient.

**The evidence, and it is two different mechanisms with two different
remedies.** One worker produced a complete result, tried to return it in a
single write, exceeded the provider's output limit and left no artifact at all —
27 records, and the file's absence is indistinguishable from never having
started. Separately, a wave of eight lost 81 records, while three of six killed
workers had in fact left usable bytes on disk and one had written a complete
generator it never executed. Nothing looked, because the retry decision was
taken from each worker's status label.

`tools/task_output.py` carries the contract, the clause that puts it in the
brief, ownership of the output root, and the four-valued classification
afterwards. It does not write a worker's output: a dispatched worker is another
vendor's process and will not import a Python module, so the rule travels in the
brief clause and Core owns the parts that must be identical for every backend.

**The chunk protocol is one rename.** A piece is written to `NNNN.ext.part`,
finished, and only then renamed onto `NNNN.ext`. A process killed before the
rename leaves a part file; one killed after leaves a complete chunk; there is no
third state. That is the whole of what bounds an interruption at one chunk, and
`materialise` uses the same protocol the brief describes so the fixtures
exercise it rather than an imitation of it.

**`UNKNOWN` is earned, never a catch-all**, and it never resolves itself. Each
of its five reasons is specific and reproduced by a fixture: a gap in the index,
a completion marker that disagrees with what is on disk, a completion marker
that cannot be read, more than one part file, and bytes the contract does not
describe. `resume_plan` refuses on `UNKNOWN` rather than guessing, because
auto-resolving an unknown is how one task acquires two workers.

**The case a two-valued classifier discards** is the one that recovered 22
records: declared products present with no chunks at all. Neither the result nor
nothing.

**A task owns its output root** (M-18f). A root under a declared generated tree
is refused — hand-authored content there is cached rather than stored, and the
destructive rebuild that destroyed two documents was itself correct — and so is
a root another task has already claimed, because two producers interleaving
indices leave a sequence neither can be recovered from.

**What this does not establish.** Whether the chunk size is right. That number
comes from the backend's output limit and the per-record cost, both adapter
facts that change; the module enforces that a bound was declared and that what
landed honours it, and holds no opinion on the value. The rehearsal plan says
the same thing and it is repeated here rather than assumed.

**Mutation-checked, eleven for eleven.** A part file read as complete, a gap
resolving to a resume, a resume restarting from zero, undescribed bytes ignored,
the completion marker believed, an unbounded write allowed, an over-bound write
written anyway, a generator-owned root claimable, another task's root claimable,
`UNKNOWN` yielding a plan, and products-with-no-chunks reading as nothing. Every
one turned the suite red.

### C4 — Coordinator continuation and liveness state

The largest recurring class in the evidence, and the one whose decisive instance
removes every explanation but the mechanical one.

**Four situations produce one observable — nothing happening.** Finished.
Blocked on a provider window. Legitimately waiting on a live job. Idle with
authorised work outstanding. Only the last is a defect, and from outside they
are identical: ten recorded instances, and more than six hours of wall clock
across three of them in a single phase.

**The decisive instance is not the longest.** In it the coordinator applied
every rule the previous four had produced — it declared that it was waiting and
it named the job, the process and the log — and then the job exited and the
declaration stayed exactly as written, for two hours and twenty-one minutes.
That removes "somebody forgot", which is what the earlier instances invited. **A
state that exists only as a sentence cannot have a transition.**

**So the state is derived, not stored.** `tools/continuation.py` stores a
declaration — what is being waited for and how anyone could observe that it
finished — and computes the state from that declaration plus the artifacts every
time it is asked. It therefore advances on job exit whether or not anybody is
watching, which is the only property that helps: *the coordinator that has gone
silent is the one that cannot poll.* A structural test asserts the record holds
no state field at all, because a stored state is a value that can be right when
written and wrong a second later.

**It is not a second authority**, by construction rather than by promise. D23
clause 8 requires every transition to be reconstructible from a durable
artifact; a derived state has nothing to reconstruct because nothing was stored.
Where the derivation and the governance record disagree, the derivation is the
defect.

**A declared wait must name an observable**, and this is refused where the wait
is written rather than discovered later: a process, an exit-status file, a task
output root, a path that appears. A wait carrying none of them is the shape that
decayed, and it is now unwritable. `HUMAN` is the deliberate exception — a
person is not a broken observable, and a wait on one reports as a human block.

**Ordering is part of the answer.** Anything that cannot be established outranks
anything that can, because acting on an unestablished state is the class this
pack refuses. A completed-and-unconsumed result outranks a remaining job,
because burying it under "still waiting on something else" is how the edge four
of five recurrences share stayed invisible.

**`SILENT_IDLE` is representable and is a defect.** Authorised work outstanding,
nothing declared to be in the way, nothing running. An empty record is
`ACTIONABLE_WORK_READY` instead, and the distinction is what makes the defect
state mean anything.

**`COORDINATOR_WAKE_REQUIRED` is a fact this module reports and not an act it
performs** (D23 clause 4). It starts nothing and wakes nothing.

**What this does not establish.** That silence will not recur. It establishes
that silence is now nameable, which is what the rehearsal plan says this
capability is for and is repeated here rather than quietly upgraded.

**Mutation-checked, nine for nine**, including the two that matter most: folding
`SILENT_IDLE` into a ready state, and burying an unconsumed completion under a
job that is still running.

### C5 — Progress, stall and waiter lifecycle

Two measurements from the same phase, four minutes apart, pointing in opposite
directions. A worker that existed for thirty-one minutes and consumed 0.05
seconds of processor time, with no log bytes and no provider rollout at all —
process existence read as progress, and it was not. And a healthy worker that
looked exactly like it: over four minutes with no log output while its processor
time climbed 3.81 → 4.05 → 4.14. It was working the whole time.

**So the disjunction is a safety property, not a completeness one.** Any
observed signal advancing means running, whatever the others did. What follows
from that is the rule that actually protects work: `tools/progress.py` **refuses
to assert a stall from a single kind of observation**, and answers `UNKNOWN`
instead. The alternative was measured killing recoverable work, and `UNKNOWN`
there is the correct answer rather than a hedge.

**The horizon is the caller's and is refused if undeclared.** How long is too
long depends on the task class and the backend; a built-in number would be wrong
exactly where it mattered. Every report states the horizon it was measured
against.

**A stall is a classification and says so in its own output.** Ending a worker
is the only destructive act in this area, its false-positive rate is measured
rather than theoretical, and it sits on `policy/hitl-matrix.md` row 4. The
release ships the detection and not the termination, which is recorded in
`docs/RP2.3-CAPABILITY-MAP.md` as removed from scope rather than overlooked.

**A run is a registered identity and never a pattern.** One worker acquired
three coordinator-owned waiters whose patterns matched each other's command
lines, so none could terminate while any sibling lived — a quorum reporting
RUNNING indefinitely, and four notifications that fired after the job had
exited. A waiter whose own command line matches its own pattern is now refused
**at construction**, because observing it hang later is too late to be useful.
Completion retires every waiter on the run, on any terminal state and not only
on success: one that exits cleanly on success and hangs on failure is armed
precisely when something has gone wrong.

**A mutant survived, and the repair is the more useful fact.** Padding the
report's `flat` list with signals that appeared in only one sample changed no
verdict — the stall decision keys off the comparable set — so seven of eight
mutants died and this one lived. What it broke was the report's honesty: it
would have named a signal as flat that nobody compared, which is a claim about
an observation that was never made. The oracle now asserts against the `flat`
set and against the rendered line, not only against the verdict. **A test that
checks only the verdict passes while the report lies**, and that is this
release's own subject arriving in its own test.
