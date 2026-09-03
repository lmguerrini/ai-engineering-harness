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

    in-release (skills/core/*.md + policy/*.md)   1562
    installed adapters, outside the envelope      1023
    total against a ~2,000 target                 2585   29.2% over the ~2,000

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

### C6 — Adapter and routing identity

**RP3-1, and it was live at this release's baseline rather than reconstructed.**
An adapter's four definition files matched their declared digests exactly. The
report read `adapters verified: 4 of 4`. The program one of those adapters
drives was a version ahead of the version the project had qualified against, and
the only record of the qualified version was a sentence in a note beside the
declaration saying it had been "verified installed at bootstrap" — which nothing
compared to the path.

**A digest describes the files; it says nothing about the binary that reads
them.** The two drift independently. So a declaration may now name the
`executable`, the `version_command` and the `qualified_version`, and the
verifier **asks the program** rather than reading a sentence: a property check
where there had been a shape check. The launch goes through the declared blast
radius from C2, so an adapter cannot cause an arbitrary program to run by
naming one in its version command.

**All three fields or none.** A version nothing knows how to obtain is a
requirement the project believes is enforced and nothing checks, which D22
refuses rather than ignores.

**The headline now says what it verified.** `4 file(s), 0 executable(s)`, and
the adapters whose executables were never declared are named. `4 of 4` over four
definition files reads as a statement about four running things and was not one.
Demonstrated on the live installation: with the executable declared, the drift
is reported with both versions and refuses to close.

**Routing observations carry `pool_id` and `qualification_basis`.** A pool is a
fact about capacity and never about capability, so it travels with a grade and
does not change it; the capacity gate needs it and the grade must not. The basis
is three-valued and not two: `field`, `synthetic`, and **unlabelled**. Every
observation in the existing log predates the field, and reading that silence as
`field` would promote every benchmark in it while reading it as `synthetic`
would relabel thirteen real closure audits as a benchmark. An unrecognised basis
is refused rather than folded into a known one — the rule the outcome field
already learned, for the same reason.

**A counting error was caught by its own test.** The basis counters were added
to the same bucket as the outcomes, and the observation count behind every grade
is `sum(bucket.values())` — so every grade briefly claimed twice the evidence it
had. Repaired by summing the outcome keys explicitly, and pinned by a test that
asserts the parts equal the whole.

**Nine mutants, nine killed — and one that taught something else.** A mutation
written as `return None or (...)` is a no-op: `None or X` is `X`, so the module
was unchanged and the "survivor" was an instrument defect rather than a gap in
the oracle. Rewritten as a genuine defect, it died. **A mutation that does not
change behaviour proves nothing about the test that fails to notice it**, which
is this release's own subject arriving in its own mutation harness.

### C7 — Capacity-aware pre-dispatch gate

Eight workers, two waves, one window — the coordinator's own. Two came back
complete, three partial, three with nothing, and **eighty-one records were
lost**. The rule that produced the wave was not carelessness: it was a recorded
routing rule, *default to the worker*, correct every previous time because the
pools had always been independent. It had never stated that precondition,
because the precondition had never been false. Weekly capacity was never the
binding constraint; the rolling session window was, and six of eight died on it.

**This is a gate, and the distinction is load-bearing.** It answers about one
proposed dispatch at a time. It holds no queue, has no dispatch verb, and never
decides what to run next — a queue that later drains is a scheduler however it
is described, and the frozen record forbids one. A structural test asserts the
module has acquired no such verb, so a later convenience cannot quietly add one.

**Authority is checked before any arithmetic, because no amount of capacity
makes rerouting a decision acceptable.** A dispatch that does not state its
authority class is refused at construction — this was blocker S5-02 against the
input evidence, where the rule *authority attaches to the TASK, not the ROUTE*
was asserted with no field on a task to hang it on, so its own rehearsal could
only have passed on a hand-labelled fixture. A task carrying a semantic or
product decision goes to the executor class it was classed for and nowhere else,
and a reroute of one is refused rather than preferred against. Wait-versus-spend
is `policy/hitl-matrix.md` row 15 and is provided as a **named refusal** so a
caller reaching for it finds the row instead of an answer.

**No universal reserve exists here and none will.** A number that fits one
provider's window is wrong for another's, and a wrong one fails in both
directions: too low reproduces the loss, too high strands capacity that had no
other use. Three reserves are declared by the project — coordinator,
result-consumption, repair-and-audit — because they are spent at three different
moments, and a partial declaration makes the total `UNKNOWN` rather than
smaller. Silently lowering a floor is worse than not having one.

**`UNKNOWN` is the ordinary case and it is neither zero nor a refusal.** One of
the two providers in the evidence base had no machine-readable capacity surface
at all. An unmeasurable window earns **serial dispatch** — one at a time, no
fan-out — and a second concurrent dispatch on it is refused. It does not
deadlock: a gate that refused everything whenever telemetry was absent is a gate
a coordinator routes around, which is worse than no gate. Every quantity that
could not be established is named in the decision, so a reader can see which
parts of the arithmetic were done.

**Negative return is a refusal.** A dispatch whose result could not be read and
verified before the window is exhausted is refused however cheap it is to
produce: work nobody can consume is work nobody did.

**Not dispatched and dispatched-and-lost stay separate.** Three of the eight
were the second, and a record that cannot tell them apart cannot learn from
either.

**Mutation-checked, ten for ten**, including the two that matter most: rerouting
a task that carries authority, and turning the unknown case into a deadlock.

### C8 — Remote verification across a real transport

The three local publication checks are all claims about what *should* happen.
The postcondition after a push is the only observation of what *did*, and it was
non-functional on every real remote: `gitread` refuses every protocol, correctly
— nothing else in the toolbelt has business leaving the machine — and the check
that exists to leave it was refused by the same setting.

**Scoped by name, per invocation, beside the standing refusal.**
`protocol.allow = never` is not relaxed. Named protocols are added as
`protocol.<name>.allow`, Git consults the specific key first, and everything
unnamed stays refused *including inside the widened operation*. The allowable
set is enumerated, so a caller cannot re-enable an unreviewed transport by
spelling it. The negative control asserts every other entry point still carries
`protocol.allow = never` and no per-protocol key at all — a rehearsal that only
proved the postcondition works would hide a global widening.

**RP3-17, and it is why the transport fix alone would have shipped a
half-repair.** With the protocol allowed, the read still failed: `cannot run :`,
then `unable to fork`. `core.sshCommand = ""` does not mean *no ssh command* —
Git runs the empty string. **This module records that exact lesson two entries
above the key it set to empty**, where `diff.external` is deliberately absent
rather than empty and the comment says why. So the neutralisation is *removed*
for an operation that enables `ssh`, not set to something: absent, Git falls
through to its own default, which is deterministic here because every ambient
`GIT_*` variable is stripped and both config files are `/dev/null`. A transport
needing no external program lifts nothing.

**RP3-18 — the report could not tell two opposite remedies apart.** A refused
transport and a host that does not resolve both arrived as `git invocation
failed`, because the probe answer carried the cause and discarded what Git
actually printed. One of those is a setting this pack controls. The detail is
now part of the finding.

**The expectation set is derived, never typed.** *Never hand-type an identifier
a mapping already holds*: the authorised refspec is that mapping, and the
supported push form constrains it to one source and one destination. A push form
with no derivable expectation is refused rather than given a guessed one, and an
expectation carrying no revision is refused because a remote still holding last
week's commit under the right name would otherwise verify clean.

**A mutant survived twice, and the second survival was the useful one.** The
first pass showed the oracle could not distinguish the hardened case from the
repaired one at all — both failures said `git invocation failed` — which is what
produced RP3-18. After that repair the mutation *still* survived: the new tests
proved the **mechanism** worked while nothing asserted that `verify_remote`
**used** it. That is *a control with no caller is not implemented*, arriving as
a live mutation rather than as a maxim. The assertion that closes it drives the
postcondition itself across a non-file transport.

**Nine mutants, nine killed** after those two repairs.

**RP3-19 — the non-regression gate refused a change that breaks nothing.** Found
by this capability's own work: adding a keyword-only parameter with a default to
a public function turned the gate red, under a message that reads *the qualified
baseline's callers would break on*. No call written against the previous
signature would fail. That is an instrument asking a narrower question than its
message claims, and a gate that fires where nothing breaks is one a release
learns to override — which is worse than the drift it was written to catch.

Relaxed exactly, and bounded by fixtures for everything it must still refuse: a
parameter appended, keyword-capable and carrying a default, is
`added_optional_parameter`. A parameter without a default, one inserted among
the existing ones, one removed, a default withdrawn, a kind or annotation
altered, or a function becoming async, all remain `changed_signature`. The
compatible case is **reported rather than silenced** — it appears in the output
under a name that says what it is.

**Two mutants survived the first pass and both taught something.** One was a
missing fixture: a keyword-only parameter altered underneath an addition, which
is compared by name rather than position and so needed its own case. The other
was a length comparison **no fixture could reach** — every path it guarded was
already refused by an earlier clause — so it was removed rather than left as
decoration, which is the shape this release spends its time deleting. Its
neighbour, the emptiness check, *is* reachable but only through the helper's own
contract rather than through the gate, so it is tested there and the reason is
written down beside it.

### C9 — History, refs and closure anchors

This is the one evidence defect whose window closes on its own: a rewrite can
orphan a commit that records cite, and the interval in which it can still be
recovered is about a month, because `gc.reflogExpireUnreachable` defaults to
thirty days and an orphaned commit survives only through its reflog. It ends
the instant anyone expires a reflog, which is sooner and unannounced.

**The mapping ships with the check, not after it.** A rewrite gives every commit
a new identity, so the moment one happens every commit-shaped token in every
record stops resolving at once. A reachability check shipped alone would fail
closed across an entire corpus — not on a defect, but on a rewrite the same
release exists to make safe. The mapping is a first-class input with a declared
schema, refused rather than skipped when unreadable, and refused when it holds
abbreviations, because an ambiguous mapping is worse than none: it answers.

**And the mapping is consulted for a commit Git can still resolve**, which is
the case that matters and was wrong in the first implementation. After a local
rewrite the old commit is still an object — Git resolves it perfectly — and
simply nothing points at it. Consulting the map only for tokens Git cannot
resolve would have missed every citation a rewrite in that repository
invalidated, which is the whole population.

**Prose that happens to be hexadecimal is not a lost commit.** A checker that
called every unrecognised seven-character word a finding would emit a
remediation list nobody could act on, which is the same failure the publication
work exists to prevent one layer up.

**A bundle nobody verified is a file**, and an anchor is a verified bundle or a
ref. Nothing here rewrites history, creates a ref or prunes anything: the
rewrite invariants exist so an authorised rewrite can be checked rather than
trusted, and they name the field rather than merely failing. A rewrite with no
demonstrated rollback is itself a finding, not a parameter with a convenient
default. `refs/rewritten/*` and `refs/replace/*` are now named private
namespaces — the former is what a history-rewrite tool leaves behind, and
nothing in the governance corpus recorded it.

**Six mutants survived the first pass. That is the most useful result in this
capability**, and every one was the same shape: an assertion the code satisfied
for a reason the test did not name.

*   A mapped successor that was itself unreachable — the fixture mapped one
    invented revision to another and exercised the not-an-object path instead.
*   An unverified bundle anchoring a commit — **two** fixtures failed to reach
    this. One used a file that was not a bundle, so every path refused it; the
    other truncated a valid bundle, and `git bundle verify` checks prerequisites
    rather than pack contents, so every corruption tried verified clean. The
    construction that works is a range bundle verified in a shallow clone that
    holds the cited commit and lacks the one the bundle is relative to — and
    the first attempt at *that* still failed, because deleting the branch left
    `refs/remotes/origin/main` reaching it and `rev-list --all` means every ref.
*   An ambiguous abbreviation resolving to the first match — the citation in the
    fixture was longer than the shared prefix, so nothing was ambiguous.
*   A repository Git could not read reported as prose rather than as unknown.
*   A verified bundle anchoring a commit it does not carry, which would let one
    anchor clear every finding in a corpus.

All six are closed, each by a fixture that enters the branch rather than by
widening an assertion, and the reason each earlier fixture missed is written
beside it.

### The coordinator's own instrument was the wrong one

Recorded because it is this release's own subject, occurring in this release's
own workflow, and because a gate record that only reports what the code got
wrong is not the record this pack asks for.

Every commit message on this branch was validated twice: once by the shipped
`commit_gate`, and once by a short script the coordinator wrote to apply the
default vocabulary — because **this repository has no project contract**, so
`--project` had nothing to read and the shipped path could only check structure.
On the ninth commit the script reported a private term. The shipped scanner,
given the same message and the same vocabulary, reported it clean.

The message was fine. The term was `sol`, an identity-tier worker name, and the
script found it inside the word *resolves* — because it matched with `in` while
the scanner this pack ships **word-bounds a bare term**, deliberately and for a
measured reason. *The instrument was not the one that runs.* That is `M-17`
exactly, in the coordinator's own tooling, which the evidence base already
warned is the least reviewed tooling there is.

Two things follow, and neither is "be more careful":

*   Every commit on this branch is re-validated with the shipped scanner and the
    full published vocabulary. All of them conform.
*   The reason the script existed is a real gap, so it is closed rather than
    worked around. `commit_gate.py --default-terms <pack_root>` applies the
    pack's own published vocabulary to a repository that has no contract,
    resolved through `instrument.read_rule` from the declared root and reported
    with its digest. **The pack can now check its own history with the rules it
    publishes**, which it could not before, and the ad-hoc script is deleted
    rather than corrected.

### C10 — Complete-history public safety and the publication profile

Two scans shipped and both were correct. The staged one is strict over what is
about to be committed; the range one is tiered over what a push would send.
**Neither combined the strict tier with the complete reachable history**, and
the gap is not academic: a term committed and then deleted survives in a blob
that the working tree, the index, `ls-files` and every tip-shaped scan all miss.
It was measured by driving the scanner directly, because no command existed to
run it.

**Both halves ship or neither does.** The measured scan produced 147 findings,
of which **four were genuine and one hundred and six were ordinary English** —
and among the rest were `.gitignore` entries whose removal would make the
repository less safe. Emitting that count as a remediation list manufactures
pressure to rewrite history in order to remove nothing, and a rewrite is the
irreversible operation this whole area exists to keep behind a person. So a
remediation list is **refused while any occurrence is unadjudicated**, and an
occurrence explicitly marked undecided blocks exactly as an absent one does:
somebody looked at the list, and looking is not deciding.

**Adjudication is per occurrence, and the per-term form is unexpressible rather
than discouraged.** A word private in one file is ordinary English in the next,
which is the common case; one project applied a class per term and had to
correct it. An adjudication is keyed by the occurrence triple, so a per-term
verdict cannot be written down, and `by_finding` makes the split legible so a
reader can see that a finding was judged nine times rather than once. A
classification without a reason is refused: a count without reasons is what this
stage exists to replace.

**The report says it is a finding list and not a remediation list**, in its own
output, and names rows 2 and 4. The scan enumerates every ref rather than the
default branch, because a blob reachable only from a tag or a stale branch is as
published as any other once the repository is.

**Decision A, implemented as a split rather than as a preference.** Universal
public-safety invariants hold for every project — private is an access control
rather than a property of the content, one click makes a repository public, and
that click has no gate in front of it. Reproducibility and presentation are
**profile-scoped**: a project declares `publication.intent`, `internal` is a
first-class answer, and an internal project is not walked through publication
ceremony because the pack is capable of performing it. The asymmetry is
asserted in both directions, and the direction that matters is that an
**undeclared** intent imposes no presentation obligation and removes no safety
one.

Each validation profile may declare the environment it is `reproducible_by` —
`public_clone` meaning a fresh clone in a fresh directory with every private
root unset, not the development tree with one variable changed, which is the
defect rather than the test. The field ships; the clean-clone gate that would
run it needs a runner the project does not control and is deferred with its
trigger.

**Nine mutants, nine killed** after one repair: an occurrence explicitly
recorded as undecided was indistinguishable from an absent one in the oracle,
though not in the code.
