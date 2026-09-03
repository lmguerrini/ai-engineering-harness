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

    in-release (skills/core/*.md + policy/*.md)   1563
    installed adapters, outside the envelope      1023
    total against a ~2,000 target                 2586   29.3% over the ~2,000

**The breach is inherited, and its composition is the part 2.2.0's disclosure
did not separate.** 1553 lines are in-release and **that half is under the
~2,000 target**; the 1023 that put the total over are the two installed adapters,
which this pack did not write, cannot freeze, and counts anyway because they are
loaded every session. Both figures are stated because `policy/BUDGETS.md` already
requires both — reporting one number made a breach the pack could act on
indistinguishable from one it could not.

*Delete before adding* was applied twice and honestly. A sentence duplicated word
for word inside `auditor-strategy.md` was removed. Then, at C14, two blocks were
**relocated rather than deleted**, under the split `BUDGETS.md` itself states —
*`policy/` holds what governs; `docs/` holds what happened*: the routing table's
account of two grades that were once wrong, and the resource observation's setup
procedure. Both are read when they are needed rather than held every session, and
both are in `docs/` unchanged. That recovered 25 lines and does not pretend to
be more than it is.

**What was not done: the prose was not shaved to fit the number.** 2.2.0 declined
that on the ground that re-scoping a rule to fit its number deletes the
disclosure rather than the excess, and cutting the in-release half — already
under target — to compensate for adapters outside the envelope would be exactly
that.

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

### C11 — Evidence and close correctness

**The generator iterates the declarations, not the results**, and that single
choice is the whole capability. A closure record's gate block was prose;
somebody wrote down which checks had passed and nothing compared that sentence
to anything, so two capabilities closed green over red gates and a profile that
was never run looked exactly like one that did. `close_attestation.attest`
enumerates the `validation_profiles` the contract declares and reports what
became of each — so a profile nobody ran is **enumerated and reported `UNRUN`**,
and omission is not something an author has to remember to avoid. A generator
walking the results could only ever describe what somebody chose to record,
which is the prose form with extra steps.

**A result for a profile the contract does not declare is refused** rather than
appended: the attestation and the contract then disagree about what this project
validates, and the contract is the authority.

**D24, implemented.** Generating the attestation is mandatory and always
satisfiable — its input is a block the contract already carries. Refusing to
close over an `UNRUN` profile is the project's declared policy, **defaulting to
refusing**, and a project that declares otherwise still gets every profile
enumerated. The obligation that is unconditional is not *run everything*; it is
that a step nobody ran must not be indistinguishable afterwards from a step that
passed. A failed or incomplete profile stops the close whatever the policy says,
because the policy governs absence and nothing else — an interrupted run did not
pass and did not fail.

**A figure inside a human decision decays into human authority.** A ruling was
taken on a measurement a later commit falsified, and it went on standing because
nothing downstream questions a decision a person made. A premise may now declare
the command that produces it, closing re-runs it, and a premise that stops
reproducing **names the decision that now rests on nothing** — *a check failed*
is not the finding. A premise that could not be re-derived is neither clean nor
broken and still stops the close: nobody established it. The launch goes through
a blast radius built from the command the record declares, so a decision record
cannot name one program and cause another to run.

**A tautology was found in this capability's own tests.** One assertion compared
a set literal with itself while claiming to check that the radius was derived
from the declared command. Replaced with one that captures the radius at the
call and reads it. **Nine mutants, nine killed** afterwards.

### C12 — The diagnostic projection

**The evidence refuses this, and it ships anyway on a human decision.** Worth
restating in the gate record rather than glossing: *five liveness recurrences
make a dashboard feel obviously justified, and a human wanting one is not
evidence that Core should ship one.* The refusal was a recommendation to a
person; a person decided otherwise, which is where that decision belongs.

**The concrete objection is answered by ordering, not by argument.** *A
projection over a state nothing transitions displays a stale value confidently*
— the decisive recorded instance would have shown `WAITING_ON_JOB` for two hours
and twenty-one minutes and been wrong. C4 made coordinator state **derived**
rather than stored, so there is no stored value here to go stale. This is why
C12 sits after C4, C5 and C7 in the dependency order rather than anywhere else.

**A renderer, not a service.** One invocation, one answer, exit. No port, no
daemon, no cache, no database — `EC-CC-33` asked for a localhost dashboard and
that is the thing the record refuses; a one-shot renderer over existing files is
what Decision E asks for in its own words. A test asserts nothing else in the
toolbelt imports it, so removing this capability is deleting one file.

**Four properties, each asserted rather than described.**

*   *It writes nothing.* Proved by hashing the project tree before and after a
    render and a full CLI run — not by reading the source for write calls.
*   *It derives nothing.* Every answer is delegated to the module that owns the
    question, and a test asserts the state vocabulary is not spelled out here.
    Two derivations of one fact eventually disagree; this makes the
    disagreement impossible rather than adjudicable.
*   *It follows the record.* Identical output across two runs could equally mean
    it reads nothing, so a second test changes the durable state and asserts the
    view changes with it.
*   *An absence is reported as unknown, never as a resting state.* A missing
    continuation record, an absent capacity observation, an unreadable contract:
    each named, and the exit status distinguishes *rendered with everything
    established* from *rendered with something it could not read*.

**Two mutants survived, and both were the same defect in the oracle**: the tests
asserted on the *rendered text*, and moving a sentence from the unknown list to
an ordinary line renders almost identically while changing the verdict — which
is precisely the confusion the projection exists to prevent. Rewritten to assert
against the `UNKNOWN` list. The second attempt still survived, because a looser
substring also matched a *different panel's* unknown: two panels, one sentence
fragment, and a test that could not tell them apart. **The distinction between
an absence and a reading is the thing this capability is for, and it took two
tries to write a test that could see it.**

### C13 — Launch, migration and compatibility

**Real-consumer contact first, because that is what the evidence says pays.**
Every tool this release adds was pointed read-only at all five project contracts
on this machine before anything else in this capability was written. Four loaded
and behaved. One did not, and the finding is worth more than the capability
around it.

**RP3-26 — a live project's contract has been unreadable by every tool since the
schema changed.** `private_terms:` is a **list** in it, which is the pre-2.1
shape, and the reader answers *`private_terms:` must be a mapping*. Confirmed
identical against the frozen 2.2.0 baseline, so this is inherited rather than
introduced. The defect is not the refusal — the refusal is correct — it is that
a project a generation behind is told its file is the wrong type, learns nothing
about which generation it is behind, and is given no migration.

Repaired the way an unverifiable legacy pin is: the older shape is recognised
and **named as legacy**, the refusal states the current shape and where the
template is, and the entries are **not migrated automatically**. That last part
is the safety half — the two tiers differ in whether a term applies to blob
content, so choosing for the project would change what gets scanned.

**Compatibility is asserted, not claimed.** The representative-consumer corpus
gains four shapes and, for the first time, a collection of shapes that must be
**refused** — a refusal fixture whose expected message is not asserted is a
fixture that passes on any refusal at all. The load-bearing one is
`unchanged_since_2_2`: a contract carrying none of the keys this release adds,
which must load and behave exactly as it did. **That is the MINOR claim, and it
is a test rather than an argument.**

**The release index exists now**, at the install root beside the release
directories, where D18 says it belongs. It lists 2.2.0 and **deliberately omits
2.1.1**: that release is qualified and has no root of its own, because it lives
in the checkout the next version is developed in. Listing the directory would
enshrine the D18 layout defect rather than record it, and a project pinned to
2.1.1 stays correctly pinned either way. The full readiness path was then run
against a real consumer with the index supplied and returned `READY`, with the
newer release reported as information and not as a gate (D21).

**A project cannot adopt this candidate**, and that is now a test rather than a
property of the manifest: the migration gate refuses an `IN_PROGRESS` target,
and the assertion says out loud that it only means something while the candidate
is unfrozen.

**The launch contract needed one addition and no more.** Its own rule is that a
project reads the release's shipped templates rather than reconstructing a
schema from the launch document, so every new declaration this release adds
needs nothing there. What it did need was the index: a sentence saying it exists,
that an entry is a claim rather than an answer, and that a project runs against
its own pin and never against an index.

### C14 — Rehearsal, qualification and release candidate

**The cold-continuation drill, run against this session's own tree.** Five reads
and one Git check, using nothing but what is on disk:

    VERSION and PACK_MANIFEST.json      2.3.0, IN_PROGRESS, gate record named
    the gate record's baseline block    2.2.0 at d70d72f, digest 4bab6b8d
    the capability map                  14 capabilities planned
    the gate record's capability heads  13 closed; C14 open
    the reproduction table              26 defects reproduced before repair
    git log against the baseline        15 commits, tree clean at each close

A returning coordinator reconstructs the position from those without reading a
conversation, which is what the drill exists to establish.

**Held prose, relocated rather than shaved.** See *Measured overhead* above: the
in-release half is under target and the total is over because of the two
installed adapters, which are counted and cannot be frozen. Two blocks moved to
`docs/` under the pack's own `policy`/`docs` split.

**`docs/RP2.3-RELEASE-PACKET.md`** is what a returning release authority reads
first. It leads with what the release deliberately does not do, and with the
mutation history — because nine of this release's mutants survived their first
pass and every one was the same shape: **an assertion the code satisfied for a
reason the test did not name.**

## Closure audit — round 1

Two blind auditors on distinct lenses, against an **immutable snapshot** at
`446b2540be3aa0320514ed47f62d70ada5f6ec90`, both barred from this document, the
capability map and the release packet. The working tree did not move while they
read — the previous release recorded a dispatch error of exactly that shape, and
avoiding it was deliberate.

| leg | configuration | verdict |
|---|---|---|
| falsification | codex-cli 0.149.0, `gpt-5.6-terra`, xhigh, `--sandbox read-only`, **independent pool** | **NOT READY** — 5 blockers, 3 major |
| release authority | fresh same-family session, read-only, `capability-auditor` | **NOT READY** — 2 blockers, 5 major, 3 minor |

**Cross-vendor was available and was used.** The row-12 fallback named at the
session freeze was not needed and was not invoked.

**Their findings are almost disjoint**, which is the whole reason two lenses run.
One overlap only: both reached `close_attestation`, from opposite directions —
the cross-vendor leg through the exported constructor, the release-authority leg
through the headline sentence.

**Every finding was reproduced by execution before any repair.** Eight from the
cross-vendor leg, two blockers and five majors from the release-authority leg.
None was refuted; none was a documented limitation re-reported; none was an
environment finding.

### The two that matter most

**The verdict went green exactly when the loss became irreversible.**
`history_anchor` reported `UNREACHABLE` and blocked while an orphaned commit was
still recoverable — and after `git gc --prune=now` destroyed it, the same command
over the same record reported *every cited commit is reachable or anchored*. The
auditor ran the prune. A destroyed forty-character citation had been falling into
`NOT_A_COMMIT`, the state reserved for prose that happens to be hexadecimal, and
`NOT_A_COMMIT` does not block. Repaired: a full-length object name this
repository does not have is `DESTROYED`, blocks, and gets its own headline —
nobody writes forty hexadecimal characters into a closure record by accident. A
short one is still prose, because a checker that called every unrecognised
seven-character word a lost commit produces a list nobody can act on.

**A read-only Git layer that could write a ref.** `DECISIONS.md` D2 extracted
this module precisely to leave the write verbs behind — *"the discarded remainder
is mostly Git write verbs, which a report-only toolbelt must not carry at all"* —
and then `probe` took the verb as a parameter and put every one of them back. The
auditor created `refs/heads/illicit` through the public read API. Repaired with an
**allowlist**, not a denylist: a denylist has to anticipate every verb Git will
ever add and the failure mode of missing one is a write. `git bundle` is checked
at the subcommand, because it has one that writes. And `archive --remote` was a
second network read reachable with `ssh` enabled, so a transport may now be
enabled only for the one verb the postcondition exception is scoped to.

One detail of that repair is worth recording: the refusal is an
`IntegrityError` rather than a `GitRefusal`, because `probe`'s whole job is to
turn a Git failure into an answer-shaped result — raising the wrong class made
*this module will not run a write verb* arrive as an ordinary negative, and the
first version of the fix did exactly that.

### The rest, by root cause

**A non-finite number passes a `< 0` check** — one cause, two modules. `NaN`
remaining dispatched an unmeasurable pool; two `NaN` readings produced `STALLED`
with **zero flat signals named in the report**. Every comparison against a NaN is
false, so it passed every guard rather than failing one. **`gitread` already
refuses a non-finite timeout for this exact reason, with a comment saying why,
and the rule was not carried across.** Finiteness is now checked before the sign,
so an infinity gets a message about the defect it has rather than one about
negativity.

**A guarantee that holds in the generator and fails at a boundary a caller can
reach** — four instances. `Occurrence.key` omitted `location`, so a term found in
a path and in that path's blob shared one adjudication. The exported
`Attestation` constructor carried no declared set, so `close_gate` was clean over
a record missing a profile — repaired by putting the declaration **on the record**
and validating it there, which makes the omission unrepresentable rather than
merely unproduced. `ProfileOutcome` accepted `PASSED` with no exit status, so the
word meant only that somebody typed it; the state is now **derived** from the
recorded status, which is the rule `evidence_index` already states. And
`re_derive` compared by substring, so a measurement that drifted from `10` to
`100` reported as still reproducing — **the same naive-substring defect this pack
reproduced and repaired in its own term scanner, made again one release later.**

**A completion condition satisfied before the job started.** A wait pointed at
`/dev/null` derived a finished result for a worker that never existed. The first
repair put the check in `__post_init__` and made a saved record **unloadable**
once its job had finished — a worse failure than the one it closed, and the
fixtures caught it immediately. Declaration and reconstruction are different
acts, so `Wait.declare` performs the check and the constructor does not.

**A completion marker beside a chunk still in progress** classified
`COMPLETED_WITH_DURABLE_OUTPUT` and prescribed consumption. And an over-bound
chunk was a trailing annotation under a clean headline while the module's
docstring claimed enforcement — the two sentences disagreed, and the code was the
weaker one. Both are now `UNKNOWN`: a producer that ignored the contract is a
producer whose output this cannot vouch for.

**A guard that could not fail.** The held-prose disclosure check read the adapter
figure with a regex written against 2.2.0's wording; this release reworded the
sentence, the match became `None`, the count fell back to **zero**, and the `if`
below it became unreachable. **It would have passed with the entire disclosure
deleted** — which is precisely the regression its sibling's docstring records
having happened once. A fallback to zero in a guard is the guard's own off
switch, so it now refuses rather than defaults.

**A vocabulary with no producer.** `DispatchOutcome` was four names, and the only
test compared the class's own tuple with a literal copy of it — *an assertion
that would pass unchanged if the mechanism it named were deleted, because there
was no mechanism.* A decision now **produces** an outcome: a refusal is
`NOT_DISPATCHED`, a permitted dispatch is `IN_FLIGHT` until whoever ran it
records which of the other two it became.

**The public-safety disclosure was inherited verbatim and unfalsifiable.** *Ten
occurrences in four files* was carried word for word from 2.1.1 through 2.2.0 and
across a release adding ten thousand lines, and **there is no adjudication
artifact anywhere in the tree from which it can be reproduced.** The auditor could
not falsify it, and said so — that was the finding. Re-measured with this
release's own `publication_history` over the complete reachable history at the
strict tier: **2090 occurrences across 100 paths**, 902 at the tiered tier. The
largest contributors are this repository's own manifest, changelog and gate
records *discussing the vocabulary* — which is the case
`skills/core/public-safety.md` describes when it says a project whose product is
a harness cannot scan its own source for harness vocabulary. They are
**unadjudicated**, and by this release's own rule a bare count is not a
remediation list. The disclosure now says that, and the adjudication is recorded
as owed.

### What the auditors attacked and could not break

Recorded because it is the most informative half of a report. The suite and the
manifest's test count agreed exactly. The release identity verified. **Every
held-prose number recomputed correctly** — 1563 in-release, 1023 adapters, 2586,
29.3% — and the baseline figure quoted from 2.2.0 was checked against 2.2.0's own
frozen manifest. Every `D<n> clause <m>` citation in every file was parsed
against `DECISIONS.md` and matched: **zero dangling pointers**, which one auditor
said it had expected to find. No AI attribution anywhere in sixteen commit
messages or any changed file. `projection` wrote nothing, verified by diffing the
tree around a run rather than by grepping for write calls. The four recovery
states survived six adversarial fixtures. Authority never moved under resource
pressure. An unmeasurable pool with a worker already running was refused rather
than serialised. `ModeSet` refused a single-mode declaration. And an AST sweep
for tests with no reachable assertion found four candidates, three of them sound.

### Round 1 repair count

Fifteen findings repaired, eight new tests added, and the delta re-audited below.
No finding was closed by weakening an assertion, and none was deferred.

### C15 — Closing ACTIONABLE_WORK + SILENT_IDLE

**The release produced another instance of the failure class it was closing, and
that is the most useful thing that happened to it.** A bounded delta re-audit was
dispatched at 06:33:20 and the coordinator was still waiting at 12:12:43 — **five
hours and thirty-nine minutes** — on a process that had consumed 0.34 seconds of
processor time, written zero output bytes, and created no provider rollout at
all. The 39 bytes of stderr said why: *Reading additional input from stdin...*
It was backgrounded without closing stdin and never began.

Four distinct mechanism failures, each now a fixture.

**1. There was no continuation record.** `tools/continuation.py` shipped in this
candidate and the coordinator never wrote one for its own run, so nothing could
derive a state — there was no declaration to derive from. *A mechanism with no
caller is not implemented*, and this release wrote that sentence twice while
doing it. The session now maintains one, and deriving it reported the
coordinator's own position as `SILENT_IDLE` — correctly, and immediately.

**2. A declared wait had no deadline, so it could never end.** Even with a
record, the derived state of a wait on a live process is
`WAITING_ON_IDENTIFIED_JOB`, and a live process satisfies a liveness question
*forever*. The model could **name** silence and could not **end** it. A wait now
declares `not_beyond_seconds`, an observable wait without one is unwritable, and
past the deadline the state is `RECOVERY_REQUIRED` **whatever the process is
doing** — the deadline is a statement about the coordinator's patience, not
about the worker. That single field is what makes the condition terminate.

Its ordering is deliberate in both directions: **before** the running branch,
because a live stalled process would otherwise report a legitimate wait forever;
**after** the unconsumed branch, because a job that finished past its deadline
has left a result and taking it up *is* the recovery.

**3. The stall classifier could not see the stall.** It compared its horizon
against the interval between the two samples rather than against how long the
run had been flat. Sampled 90 seconds apart against a 900-second horizon, it
returned `RUNNING` for a run dead for five hours — **and a caller who polls
could never have obtained a stall verdict at all.** The instrument built to
detect this incident did not detect this incident. `flat_since_seconds` is now
required with no default, and the report states both durations so the old
arithmetic would be visible rather than silent.

**4. The waiter could not terminate.** `until [ -s report ] && ! pgrep -qf
"codex exec"` — and `pgrep -f "codex exec"` matched the waiter's own command
line, so the loop could never exit *even after the worker did*. That is RP3-13,
which this release refuses at construction in `progress.Waiter`, recurring in a
shell one-liner that never went through it. The reason a coordinator hand-writes
a waiter is that the pack did not ship one, so it now does:
`progress.waiter_command` watches a registered process number with `kill -0` and
contains no pattern for anything to match.

**And a fifth, found while writing the record.** A blocker with no stated scope
silenced work it had nothing to do with: one human decision about two stalled
processes reported the whole capability `BLOCKED_ON_HUMAN` while five authorised
items sat undone. From outside, a blocker that stops unrelated work is
indistinguishable from a coordinator that has stopped. A blocker now says what
it blocks; unscoped still blocks everything, because that is the safe default
for one nobody has thought about.

**Duplicate workers.** A wait names the **obligation** it discharges, and two
live waits on one obligation are `RECOVERY_REQUIRED` rather than a race —
whichever answers second is work nobody asked for. Retiring a wait frees the
obligation, and retiring is not deleting: the record still says what happened,
which is how the replacement dispatch is provably not a duplicate.

### How the incident was handled, and the boundary that was not crossed

Classified from durable evidence **before anything was touched**: three
independently observed signals flat, no provider rollout where a previous run
had a complete one — the recorded `EC-CC-90 RECURRENCE 2` signature. **No
durable output existed to recover**, verified rather than assumed.

**The worker was not terminated.** Autonomous termination is out of scope for
this release, and the frozen recovery contract gates a coordinator's own
termination on seven preconditions with the default posture *escalate, never
terminate*. Two are absent: no durable checkpoint verified to exist, and no
task-owned output root. Precondition 7 requires a durable human-visible
escalation whenever any precondition is absent, and
`rp2.3-session/INCIDENT-2026-09-03-silent-idle.md` is it. **The exact limitation
is reported rather than crossed:** ending processes 2775/2776 is a human
decision under row 4.

The **waiter** was retired, and it is a different object — the coordinator's own
broken instrument, holding no output and provably unable to complete. Retiring
it through the harness that started it is supervisory control over a tool, not
termination of work.

**Mutation-checked, eight for eight** — plus two mutations that taught nothing
because they were near-equivalent, which is the second and third time that has
happened this session and is worth recording as a property of the harness rather
than of the code.

## Closure audit — round 2, the bounded delta re-audit

One blind same-family auditor against an immutable snapshot at `26d31ed`,
barred from this document, the capability map and the release packet.
**NOT READY: five blockers, four recommendations, and six tests named as
decorative.** Every finding reproduced by execution before repair.

**Three of the five blockers were defects in round 1's repairs**, which is what
a delta re-audit is for and the reason the standing condition of any final
repair is that it is unaudited.

### The allowlist still wrote

`config` sat on the read-only allowlist under a comment asserting that *"a write
needs a value argument this module never passes"* — while `probe(cwd,
*arguments)` is a public varargs API and **the caller passes the arguments**.
The auditor added `[audit] injected = yes` to a repository through the read-only
layer and removed `user.name` from it. Separately, `diff --output=FILE` created
a file.

**The verb is not the unit of read-onlyness, and believing it was is how an
allowlist still wrote.** A verb whose read-onlyness depends on its arguments now
declares the forms it may take, options that make a read write to the filesystem
are refused, and the test that should have caught this — twenty-four verbs
asserted absent from a list they were never on — is replaced by one that runs
**every permitted verb** against a scratch repository and asserts it is
byte-identical afterwards.

### The deadline failed open

`expired_at` swallowed a parse failure and returned *not expired*, so a wait
whose `declared_at` was the word `soon` never expired — **and it round-tripped
through save and load**, putting the indefinite wait this release exists to end
back within reach from disk, in three lines. A deadline that cannot be evaluated
has passed; the alternative is the failure class. And a naive ISO timestamp
raised a `TypeError` out of `derive` because the subtraction sat outside the
guard, so the shipped command line printed a traceback where it should have
reported a refusal — a class this pack's own observation log already records as
repaired once.

### The scoped blocker did not close the case it was named for

`_stops_the_outstanding_work` used `any`, so a blocker naming one of five items
silenced the other four — **the scenario in its own docstring, reproduced
verbatim against it.** A blocker now stops the run only when every outstanding
item is one it names, and `SILENT_IDLE` is measured against the unblocked
remainder.

### The expiry repair broke a terminal record

A job that finished, whose result was consumed, in a record declaring itself
terminal, reported `RECOVERY_REQUIRED` — permanently, because time only moves
one way. A wait that finished is not waiting, so patience does not apply to it.

### And the repair for a hand-written waiter shipped a hole the hand-written one did not have

`waiter_command` interpolated the sentinel path into a shell string unquoted, so
a quote in it started a second command. Quoted now, and the test asserts the
property by **running** the generated condition rather than by inspecting its
text.

### Six tests were named as passing for reasons they did not state

All repaired rather than deleted. The `DESTROYED` state reported *"GONE FROM
THIS REPOSITORY"* about blobs and trees the repository holds — it asked only
whether the token resolved to a *commit* — and now asks. An attestation accepted
two contradictory outcomes for one profile while its `examined` count said
"declared profiles" and counted outcomes. `classify` trusted a `flat_since` that
two identical readings contradict, which is the hole the required horizon exists
to close, one field over.

**And one defect the suite caught within a minute of being introduced:** the
argument-form loop named its variable `text`, shadowing `_run`'s own `text`
parameter, and turned every binary read into a text read. Recorded because the
difference between that and the findings above is only that a test existed.

## Closure audit — round 3, the blind cross-vendor read

One blind independent-vendor auditor, read-only, falsification-instructed,
barred from the design and repair documents. **NOT READY: five blockers, three
majors.** Every finding re-executed here before anything was touched.

### Six of the eight were already repaired, and the report could not say so

The auditor read a snapshot taken before rounds 1 and 2 landed. Re-executed
against the candidate: the NaN capacity pool refuses, the NaN progress reading
refuses, `Occurrence.key` already carries `location`, the `Attestation`
constructor already refuses an empty declared set, `probe` refuses both
`update-ref` and `archive --remote`, and a completion marker beside an
interrupted chunk already classifies `UNKNOWN` and refuses to resume. Two
findings were real.

**The stale-snapshot problem is the release finding here, not an inconvenience.**
The report never stated which revision it read, so nothing but re-execution
could distinguish a live defect from a repaired one — six times, one at a time.
The harmless direction is the one that happened. The other direction is a clean
audit of an old tree reading as clean for a new one, which is a green gate over
a tree nobody examined. `close_gate(..., against=(revision, digest))` now
refuses evidence recorded about a different tree, and **an audit brief states
the revision and digest the auditor read**.

### A rewrite mapping was accepting its own assertion as evidence

`{orphan: any_reachable_commit}` cleared the orphan and did not block. Reachable
is a test every reachable commit passes equally, so it distinguished nothing —
and the citation read as settled while the original was genuinely gone. The
successor claim is now corroborated by the preserved original in a verified
bundle or it is `REMAPPED_UNVERIFIED` and blocking, naming the two things that
would settle it. Adjudicating a rewrite is a human act in this release; the
checker's job is to say what it cannot establish.

### A wait completed on `/dev/null`

`Wait.declare` already refused a completion condition satisfied before the job
starts — and that check is in the right place for the right reason, since a
constructor invariant makes a legitimate saved record unloadable after its job
finishes. But `declare` is reachable only by the caller who declares, and the
auditor built the record directly. **A check nothing forces you through is a
check on the honest path.** So the observation asks again, in the two forms that
survive a reload: a sentinel is a regular file, and it does not predate its own
wait. A file last written before the coordinator began waiting for it did not
come from the job being waited on, whatever it contains.

The bound is a test of its own: a sentinel the job actually wrote still
completes the wait, which is what keeps a fail-closed repair from becoming a
refusal to ever finish.

## The controlled continuation rehearsal

Seven steps, executed as `tools/tests/test_continuation_rehearsal.py`, because a
rehearsal that is described rather than run is a plan.

**The reconstruction runs in a separate process.** This is the whole design of
the test and not an implementation detail: a reconstruction inside the same
interpreter shares imports, module state and live objects with the thing it is
reconstructing from, so it cannot demonstrate the property under test — that
nothing but the file crosses the boundary. The child gets `sys.executable`, a
`sys.path` entry and two paths.

Step 6 is the one the rehearsal exists for. The job is still running and the
coordinator that dispatched it is gone; a reconstruction that reports
`ACTIONABLE_WORK_READY` there sends a second auditor after an obligation that
already has one. It reports `WAITING_ON_IDENTIFIED_JOB`, and a record that
somehow acquires two workers under one obligation reports `RECOVERY_REQUIRED` —
two workers is a defect to name, not a tidier way of waiting.

Step 7 writes a `SUMMARY.md` beside the record saying the audit finished and
everything passed, in the place a compaction summary would live, and asserts the
derived state does not move. Conversation, summaries and task UI are not
governance authority, and this is the check that they are not *needed*.

And the rehearsal is bounded by a test that breaks it: with the record's waits
and blockers removed, the reconstruction must stop saying
`WAITING_ON_IDENTIFIED_JOB`. Every other assertion in the module passes
trivially if `derive` ignores its input.

## The dispatch that failed twice, and what it was

Two cross-vendor dispatches held a named wait for **5h39m and 6h42m** at roughly
a third of a second of CPU. The third — same brief, same model, same sandbox,
**stdin redirected from `/dev/null`** — wrote 120KB of progress in three minutes.
`codex exec` had been reading stdin and waiting for input that was never coming.

Worth stating plainly because the release was about to record *cross-vendor is
an unreliable route* as field evidence. It was the dispatcher, both times. A
routing table that had learned from those two runs would have learned something
false about somebody else's software.

What actually held is the thing that did not depend on understanding the cause:
**every observable wait carries a deadline**, so a route that never starts costs
the deadline rather than the afternoon. The next cause will be different and
will also not be understood at the time.

## The pack's own complete history, scanned with the capability it ships

`publication_history.py` did not exist before this release, so this history had
never been read end to end. Run over the complete reachable history of the
evolution branch — 3 refs, 1027 objects — it reports **218 occurrences to
adjudicate**, and its own last line is the disposition: *this is a finding list,
NOT a remediation list.*

**Exit 1 means there is something to adjudicate. It does not mean there is a
leak, and the distinction is the capability.** A checker that decided for you
which absolute path is innocent would be adjudicating, and adjudicating is what
this one refuses to do.

What the occurrences are, checked rather than assumed:

- **No personal username or home path exists in the tree or in any commit this
  evolution made.** A recursive grep for this machine's home directory over the
  whole checkout returns one line, in the worktree's `.git` pointer file —
  machine-local plumbing that is never committed and is outside the digest.
  Counting the added lines across the whole evolution's patch that mention a
  home directory returns **0**. (Neither command is written out here with its
  real argument: `test_no_tracked_file_carries_a_real_machine_path` refuses a
  tracked file containing one, and it caught this paragraph on the first
  attempt to write it — which is the guard doing exactly its job.)
- The 165 *local filesystem path* occurrences are absolute paths of the
  `/tmp/...`, `/dev/null`, `/usr/bin/...` kind, in tests and templates.
- The 41 *credential-shaped token* occurrences are **the scanner's own test
  fixtures** — synthetic keys that exist so the credential detector has
  something to detect. A scanner tested with no credential-shaped string in its
  fixtures is a scanner nobody has run.

**Disposition: declared, not blocking, and not remediated.** Nothing in this
release is published, and remediating a historical object is a history rewrite —
HITL rows 2 and 4, and frozen decision D says this release detects, classifies,
prepares and verifies while execution stays with a person. The finding list is
what a publication decision would start from, and producing it is the
capability closing, not failing.

The obligation that *does* bind now is the one about what this evolution wrote,
and it is satisfied: zero personal paths, zero credentials, zero private project
material in twenty-two commits, with the commit gate run against the pack's own
published vocabulary before each one.

## Closure audit — round 4, the release-authority read

One blind cross-vendor auditor with release authority, against the candidate
itself. **NOT READY: six blockers, two majors, two minors.** Its report opens
with the revision and digest it read — the requirement added one round earlier,
and it worked: nothing had to be re-executed to find out which tree the findings
were about. Every one was reproduced here before it was touched.

### A read-only interface was running the subject's code

`diff.external` in a scratch repository's own config, `probe(repo, "diff", ...)`
through the public read API, and the named script ran. **It ran without the flag
too** — the config alone is enough. For a module whose entire purpose is reading
repositories somebody else controls, that is arbitrary code execution on every
diff, and the auditor noted it also removes any meaning from the scoped
transport exception.

The neutralised-config table says of that key: *"deliberately absent. An empty
value does not mean no external diff — Git tries to run the empty string and
every diff dies with cannot run. **The diff family has its own switch for
this.**"* The reasoning is correct, the switch is `--no-ext-diff`, and it was
never passed. **A comment naming the right answer is not the right answer**, and
this one had been sitting there since 2.2.0.

`--no-ext-diff` and `--no-textconv` are now passed to every verb that accepts
them, and `--ext-diff`/`--textconv` are refused from callers. The switch rather
than a config key, because it also disables the per-driver `diff.<name>.command`
that `.gitattributes` selects — which no enumerable set of keys reaches, and
which is its own test.

### The complete-history scanner was not scanning complete history, twice

A six-megabyte blob whose first line held a private term reported **clean, exit
0**, with `NOT SCANNED: large.txt exceeds the scan limit` printed two lines
below. The skip was recorded honestly and then not counted. **The word in the
module's name is complete**; a scan with a hole in it has not answered the
question, and it now says `INCOMPLETE` and exits non-zero.

And two paths sharing one blob produced one occurrence instead of three. The
cause was deeper than the deduplication set: **`git rev-list --objects` prints
one name per object**, so the second path was never enumerated at all. Names now
come from the trees, deduplicated by the pair. This is the third finding in this
release about identity of an occurrence, after `Occurrence.key` and the
adjudication collision — the same mistake at three different layers.

### Two blockers, each covering half the work, stopped nothing

Each was asked separately *do you leave the coordinator with nothing to do?*
Each named one of two items and answered no, so both were filed as scoped, the
unblocked remainder came out empty, and the report read *nothing is in the way
and nothing is outstanding* above a list of two outstanding items and two
blockers. Coverage is a property of the union.

**It is the `any`/`all` defect from round 2, one level up.** That round changed
the quantifier inside the predicate; this one changes the set the predicate is
asked about. The same misreading twice, which is worth recording as a fact about
the reader rather than about the code.

### Another task's finished work was this task's result

A contract for `beta` pointed at `alpha`'s complete output root returned `beta
COMPLETED_WITH_DURABLE_OUTPUT`. The owner marker was already being written for
exactly this purpose and only the writer was reading it. `UNKNOWN` now, not a
refusal — a mismatched owner is a real state of the disk that a person resolves,
and `resume_plan` already refuses to act on `UNKNOWN`, so it cannot become a
retry.

### And the horizon itself was never checked

Non-finite readings were refused a round earlier; the horizon they are compared
against was not. `NaN` made the comparison false and reported `STALLED` with no
flat signal behind it; infinity made it true forever and reported `RUNNING` for
a run dead a thousand seconds. **The same rule one field over, which is where
this class of defect always is.** A capacity reading with no `observed_at` was
the same shape: the class docstring says the timestamp matters as much as the
figure, and the class accepted a bare number and gated on it.

### The finding the repair does not close

*An unrelated writer can satisfy a path wait.* Correct, and it stays correct: no
property of a bare filesystem path distinguishes who wrote it. The observation
was strengthened as far as a filesystem permits — a sentinel must be a regular
file that does not predate its own wait — and beyond that the honest answer is
that `PATH_EXISTS` establishes *that* something happened, not *who* did it.
`OUTPUT_ROOT` is the kind that establishes a producer, and it now genuinely
does. A test pins both halves so the weaker claim cannot quietly become the
stronger one.

### Two tests that could not fail

`tree_digest(pack) == tree_digest(pack)`, in two modules. Replaced with the
property actually worth pinning: the digest is **content-addressed**, so
rewriting a file with identical bytes and a moved mtime leaves it unchanged, and
one added byte changes it. And the claim *nothing imports the projection* is
false — its own tests do. The true claim is that no runtime tool module does,
and it is now the one being made.

## The mutation pass over rounds 3 and 4

Twelve guards added by the last two rounds, each deliberately broken, each
suite re-run. **Eleven mutants died. One survived, and it was mine.**

The surviving mutant emptied `CODE_ENABLING_OPTIONS` — the list of options
through which a caller re-enables repository-controlled code execution. The test
guarding it looped over that same constant, so an empty list meant zero
iterations and a pass.

**A test that iterates its subject's own configuration tests nothing when the
configuration is emptied.** It is the third appearance in this release of one
idea — a check that asks the subject what to check — after the twenty-four verbs
asserted absent from a list they were never on, and the two digest tautologies.
The options are named literally now, and the mutant dies.

Worth stating plainly: the survivor was found by running the mutation pass, not
by writing the test. Every one of these tests was written believing it worked.

## Closure audit — round 5, the delta re-audit of round 4's repairs

One blind cross-vendor auditor against the repairs, stating the revision and
digest it read. **NOT READY: seven findings, and four of them were defects in
the repairs it was sent to check.** Six reproduced exactly; the seventh was a
correct criticism of an oracle's strength rather than a reproducible defect.

### Two more ways the subject's own code runs

The round-4 hardening closed `diff.external` and the attribute-selected diff
driver. It did not close `cat-file --filters`, which applies the repository's
`.gitattributes` filter chain, and it did not close `diff --submodule=diff` —
**because a nested Git process is a second process, and the parent's command
line never reaches it.** The submodule's own `diff.external` ran straight
through flags that protect only the parent.

Three rounds of the same idea, each closing the instances visible from where the
last one stood. The refusal set now covers `--filters`, `--submodule=diff` and
`--recurse-submodules`, and `submodule.recurse=false` joins the neutralised
config — two answers to *will this recurse* rather than one, because the cost of
the wrong answer is running somebody else's program.

### Absent is not permission

The owner-marker check asked the marker *when there was one*. Deleting it
restored the defect exactly, and the auditor deleted it and then replaced it
with a directory. A root with no readable marker has an unknown owner, and
unknown is the answer — for the task that really did own it as well, because
nothing on disk says so any more.

### `int()` converts; it does not validate

`pid=1.5` became process 1 — init, always alive, so the wait reported a running
job forever. `pid=inf` raised a bare `OverflowError`. Both found on the repair
for the string case one round earlier. A process id is a whole number, and
anything that merely converts to one is not one.

### An exemption covered a name nobody exempted

Identical bytes at an exempt path and an unexempt one reported **clean**: the
content exemption was decided from the single arbitrary name `rev-list
--objects` prints. The tree walk added one round earlier already knew every
name, and the content scan was still trusting one of them. An object is exempt
only if every name it has is exempt.

### And the oracle that replaced a tautology was still too weak

The content-addressing tests appended bytes, which changes the framed length —
so a digest that framed the length and never hashed the content would still have
passed. **The auditor removed `digest.update(content)` and said so.** Both
oracles now flip one byte in place, and both kill that mutant on their own.

The same report also noted that `test_the_diff_family_still_reads_after_the_
hardening` asserted `answered` rather than `ok`, and a Git parse failure caused
by the injected flags produces `answered=True, ok=False` — the test passed
through exactly the breakage it existed to catch.

## Human authorizations for the unattended window, 2026-09-03

Granted in one consolidated pre-flight. Recorded here because
`policy/BUDGETS.md` says a session authorisation is recorded in the gate record
of the version it cut.

**Closure / requalification cycles raised from 4 to 8 per capability**, spendable
only to close a verified release-blocking defect or to delta-audit repairs that
changed a guarantee — never for reassurance. Repair attempts (12) and repair
rounds (8) unchanged; the three-consecutive-failures rule still ends any single
hypothesis. Requested because round 5 found four defects in round 4's repairs
and the most-audited capability had reached 4 of 4.

**Row 4, exercised once and only for two process ids.** Processes 2775 and 2776
were ended after 7h50m at 0.42s and 0.11s of processor time. Both were
classified `FAILED_BEFORE_USEFUL_OUTPUT` with no durable output to recover, and
their subject revision could no longer close any gate. **The pack still ships no
termination verb**: `M-03e` is unchanged, and the next stalled worker is
escalated rather than ended.

**Row 12 fallback named:** if the cross-vendor route becomes unavailable the
final audit may be a fresh blind same-family context — *recorded in the gate as
same-family rather than cross-vendor*. Disclosure is the condition. Not needed
so far: three clean cross-vendor runs since the stdin cause was found.

**SemVer stays with the founder.** A defect that can only be closed
incompatibly is implemented, recorded as MAJOR-shaped under D11/D24, and stopped
at a scoped HITL rather than renumbered.

## Round 6 — the reading its own provider stopped, and what was recovered from it

The sixth blind cross-vendor delta re-audit **was terminated mid-run by the
provider's content filter** and wrote a zero-byte report. Its stderr held 342KB
of durable partial output, and five real findings were recovered from it before
anything was retried — which is the recovery contract this release ships,
applied to the release's own audit.

**Four reproduced from the log, and one was the probe it announced in the last
sentence it wrote.**

### `core.gitProxy`, and the first repair in this release that could not harden the key

A program named in a scratch repository's own config, executed through
`ls-remote` with a transport enabled. **The fourth route in this release by
which a repository being read chose what ran — and the only one that came
through the single exception that exists to let one operation cross a
boundary.**

It cannot be neutralised from the environment. `core.gitProxy` is multi-valued:
`GIT_CONFIG_KEY_n` appends to the list rather than replacing it, `git config
--get-all` shows both entries, and Git uses the repository's. Setting it to
`none` and to the empty string were each tried and each left the program
running. **Verified, not reasoned about** — the reasoning would have been wrong
and the first patch written for this finding was exactly that wrong patch.

So the closure is that `git://` is no longer enablable. It is unauthenticated
and unencrypted, nothing here verifies a remote over it, and `core.gitProxy`
applies to no other protocol. Narrowing the exception is the repair; there was
no version of this that kept the protocol and closed the hole. A test asserts
the remaining four transports still work, because a repair that closed all of
them would pass the first test and break the postcondition the exception exists
for.

### `--submodule diff`, written with a space

Git accepts both spellings and the refusal knew one. This was the auditor's
announced next probe, written in the last sentence before it was cut off.

### A symlinked owner marker

`is_file()` follows a link, so a marker pointing elsewhere and naming `beta` let
beta read alpha's finished work. **Third appearance of one defect** — the owner
check has now been wrong when the marker was unread, when it was absent, and
when it was a link. Each repair closed the shapes visible from where it stood.

### And a marker holding `null` or `[]`

`.get` on whatever JSON happened to be there, raising a bare `AttributeError`
out of a function whose contract is a four-valued state.

### The routing fact

The termination was the provider's content filter, not a capacity limit or a
hang, and it is recorded as an `environmental_failure` row. It charges no
budget. **Row 12 was not reached**: the run produced recoverable findings, and
the same-family fallback the founder authorised was not needed.

## The projection, refined — and the two things it immediately said about me

The evidence base refused a dashboard and the refusal still stands in
`tools/projection.py`'s own docstring. What changed is the ordering: coordinator
state is derived rather than stored, so there is no stale value here to render
confidently. The refinement is about **what a human watching a long run needs to
answer without reading files**, and every field is delegated or declared —
nothing is computed here and nothing is guessed.

What it now shows, where the data exists: a headline naming the state in a
sentence; the pack's own identity and whether it is adoptable; each job's
executor, obligation, **subject revision and digest**, declaration time,
deadline and time remaining; budgets used against their ceilings with who raised
them; standing evidence (candidate, suite, gates, latest audit, closure);
whether a blocker is scoped and what remains runnable behind it; the exact next
authorised action; and **how old the record is**.

Two of those needed the record to carry more than it did. A dashboard cannot
show what the authoritative state does not hold, and the right repair for a
missing field is to add it to the record, never to infer it in the view:
`Wait` gained `subject_revision`, `subject_digest` and `executor`;
`ContinuationRecord` gained `budgets` and `evidence`. **Both new record fields
were dropped on the first save**, because `as_dict` and `load` enumerate their
fields and a field added to the dataclass alone survives neither — caught by
round-tripping them before they were used once, which is the whole reason to
round-trip a new field before using it.

### What it said about this session, unprompted

Pointed at this evolution's own record, the refined view reported that the
record was **50 minutes stale** and that the outstanding wait **did not state
the revision it was about**. Both were true, both were mine, and neither would
have been visible in the previous version. A dashboard whose first act is to
find two defects in its author's record-keeping is behaving correctly.

### Falsified, not admired

Fourteen adverse cases: a record hours old, a record moments old (the bound — a
warning that is always on is not a warning), an unreadable timestamp, malformed
JSON, an absent record, a wait with and without a declared subject, an expired
deadline, an undeclared budget, a declared one, a scoped blocker with unrelated
work still runnable, a finished job nobody read, `SILENT_IDLE`, and a
write-nothing check hashing the whole tree around a fully-populated render.

One of those tests failed for the wrong reason on first writing — a substring
test over the whole render matched a timestamp — and is now scoped to the panel
it is about. **Fifth appearance in this release of a check that passed for a
reason it did not state.**

## The live rehearsal against the two real consumers, read-only

The suite's consumer-compatibility tests run against fixtures. This ran the
shipped commands against the **two projects that actually pin this pack**,
read-only, mutating nothing.

| | `consumer-c-v1` | `consumer-a-v0.1.0-baseline` |
|---|---|---|
| `project_contract.py` | 0 | 0 |
| `pack_migration.py --index <real index>` | 0, **VERIFIED_PIN** | 0, **VERIFIED_PIN** |
| `adapter_pin.py` | 0, 4 adapter files verified | **2 — reported and refused** |

`VERIFIED_PIN` on both is the result that matters: the migration path reads the
real release index, finds each project's real pin, and verifies it against the
release itself rather than believing the index. Neither project was offered
2.3.0, correctly — the index lists only `QUALIFIED_AND_FROZEN` roots and this
candidate is neither frozen nor in it.

**The `adapter_pin` refusal is the tool working, not failing.** Consumer-A
declares no `adapters` key, and the answer is not *no adapters*: *"this is not
the same as declaring none: write `adapters: []` to state that this project
dispatches through no adapter, and this will verify that claim instead of
refusing to guess."* It names the one-line fix and it is a finding about that
project, not about this pack — **and nothing here changed it.** A release that
edited a real consumer to make its own rehearsal green would have proved
nothing.

`consumer-c-v1`'s adapter row is worth reading closely too: four adapter *files*
verified, and **zero executables**, reported as *"executable NOT verified (none
declared)"*. That is the adapter-drift gap this release named and did not close,
saying so on live data rather than in a limitation nobody reads.

## Backward compatibility, measured rather than asserted

`surface_diff.py . <2.2.0> HEAD` over the whole consumer surface: **121
entries, and every one an addition** — 105 public names, 6 star exports, 3
methods, 1 optional parameter on `gitread.probe`.

The two `removed_public_name` entries are the two tautological digest tests this
release deleted. **A test function is not consumer surface**, and the honest
thing is that the tool cannot tell — it compares module-level names and says so
in its own disclosure, which also lists what it does not compare (class-level
attributes, dataclass field types, base classes, anything done at import time).
The optional fields added to `Wait` and `ContinuationRecord` fall in that
uncompared region; they carry defaults, and their compatibility rests on the
save/load round-trip tests rather than on this diff.

Additions only, with one explained removal, is what MINOR means (D11, D24).

## Closure audit — round 7, the release-authority property read

Eight findings and one test that could not fail, against the candidate itself,
with the revision and digest stated. Every one reproduced before repair.

### The fifth way a repository chose what ran, and it was inside the exception

`remote.<name>.uploadpack` names a program Git runs on the far side of a
transport — and with a `file://` remote the far side is this machine, so the
program ran **with the reader's own permissions and wrote into the reader**.

That is five routes in four rounds, each found where the previous repair could
not see. No config key closes this one either: the setting is per-remote and
remote names cannot be enumerated in advance. `--upload-pack=git-upload-pack`
overrides the config, verified rather than reasoned about — with the flag the
program does not run, without it it does.

### The chunks beside the marker

The owner marker is checked and then the artifacts are read from wherever the
`chunks` directory points. A link to another task's chunks, a valid completion
marker, and one task's finished work read back as another's. **Fourth
appearance of one defect:** ownership has now been wrong for the marker unread,
absent, linked, and for the directory beside it.

### And three more of the same shape as things already fixed

A saved record with `"actionable": [[]]` loaded and then raised `TypeError:
unhashable type` out of the derivation — an exception where the contract is a
state. A `Sample` taken at a NaN time produced `STALLED` with
`flat_for_seconds=nan`: the signals were guarded, then the horizon, and the
moment was **the third field over**. A branch named after a private term and an
annotated tag whose message held one both scanned CLEAN, because the scan read
paths and blobs and a ref name is published with the repository.

### Two findings that changed what a state MEANS

`history_anchor` treated a verified bundle as corroborating a rewrite mapping.
It does not. The reader kept the original in a bundle, pointed the mapping at an
unrelated reachable commit, and the citation went green. **A bundle proves the
original is preserved and says nothing about identity.** Preservation is the
real remedy, so that is the state — `ANCHORED` — and the mapping is reported
beside it as the assertion it is.

`close_gate`'s tree check was optional, which the reader correctly called a
check nobody performs: the module's unconditional claim is *evidence about one
tree does not close another*, and the default closed on evidence from any tree.
It is required now, with an explicit `UNSTATED` for a caller that genuinely
cannot name the tree — **so the gap sits in the caller's code where a reader can
see it, rather than in an argument nobody passed.**

A test in this release asserted the old behaviour and said it was deliberate:
*"a caller with no identity to compare against is not silently told its evidence
is fine — it is told nothing."* An empty problem list **is** the pass. The test
now asserts the opposite and says why it was wrong.

### The one that was correct as designed

`capacity.gate` returns `DISPATCH_SERIALLY` with five unknowns, which the reader
called an answer without evidence. **The verdict is kept.** No machine-readable
quota surface is the ordinary case for the providers this pack routes to, and a
gate that refused everything it could not compute would refuse everything —
which is unusability, not conservatism, and a coordinator would route around it
within a day. What UNKNOWN buys is the most conservative posture that still
permits work: one at a time, and every unknown named.

The reader's point is answered by disclosure. `why` now distinguishes *the
arithmetic below is partial* from **NO ARITHMETIC WAS PERFORMED** — because
"nothing came out unfavourable" and "nothing was computed" are different
statements and were rendered identically.

### The test that could not fail

`test_the_module_derives_nothing_of_its_own` searched source text for
`continuation.derive`. The reader **deleted `projection.project` outright** and
the test still passed. It now runs the projection with the owners' functions
wrapped and asserts they were called. Sixth appearance in this release of a
check that passed for a reason it did not state — and the fourth found by
someone other than its author.

## Closing the class instead of the route

Five separate routes by which **a repository being read chose a program to run**
were found in four consecutive audit rounds:

| Round | Route | Closed by |
|---|---|---|
| 4 | `diff.external` | `--no-ext-diff` |
| 4 | an attribute-selected `diff.<n>.command` | the same flag, which is why it is a flag and not a config key |
| 5 | a `.gitattributes` filter chain via `cat-file --filters` | refusing the option |
| 6 | `core.gitProxy` | the `git://` protocol is no longer enablable |
| 7 | `remote.<name>.uploadpack` | `--upload-pack` overrides the config |

Each was closed where the previous repair could not see it, and each time the
next reader found another. **Closing routes one at a time was losing**, and the
right response to five instances of one class is not a sixth patch.

So the check moved from the routes to the **shape of the key**. A repository's
own local configuration is read before anything runs, and a key whose value Git
would execute refuses the read — *unless this module has a NAMED CLOSURE for
that key*, listed with the mechanism. The asymmetry is the design: a key with a
closure has been thought about, and a key without one has not. The sixth route
will arrive as a key nobody here has heard of, and it is refused by a check
written before anyone found it.

The bound matters as much as the check. `core.pager`, `core.editor`,
`diff.external`, a filter and `credential.helper` are all program-valued and all
allowed, because each has a closure. **Refusing to read a repository because its
developer set a pager is hardening in name and obstruction in fact** — and a
tool that obstructs gets routed around, which is worse than one that never
hardened.

### Three defects in the defence, found by writing it

The general check was wrong three times before it was right, and every one is a
recognisable member of a class this release has already named.

**It failed open.** `git config include.path /bin/sh` makes every subsequent
config read fail — so a repository could disable the check that inspects it by
breaking itself, and seven unrecognised program-valued keys came back as none.
The discriminator that tells *not a repository* from *unreadable config* now
asks the filesystem, because it has to work in exactly the case where Git is
what is failing.

**It re-entered itself.** The inspection runs Git and every Git run is
inspected; the first guard was on the verb `config`, and the function's own
fallback probe was a different verb. Two test modules that take ten seconds ran
for over six minutes without finishing. *A guard on the verb was a guard on one
of the paths the function takes.*

**It hijacked refusals belonging to the caller.** A caller asking about a broken
config got a security finding instead of *your config does not parse*, and a
caller with an expired deadline got one instead of a timeout. Both are the same
mistake: a precondition check that answers a question the caller did not ask.

The cost is about 17 seconds on a 110-second suite — two extra Git processes per
repository per invocation. Recorded because it is real, and because a check
whose cost nobody measured is a check somebody eventually disables.

### The pack's own history, re-read after the scanner grew

Re-run once ref names and annotated tag messages became part of the scan:
**253 occurrences over 3 refs and 1179 objects, and — the number that changed
meaning — ZERO NOT SCANNED.**

The earlier run reported 218 and could not have told you whether that was all of
them. This one can: every reachable object was read, so the finding list is the
whole finding list rather than as much of it as the scanner could reach. That is
the difference the `INCOMPLETE` verdict bought.

No occurrence is in a ref name or a tag message. All 253 are content findings of
the two kinds already adjudicated in prose — absolute paths of the `/tmp` and
`/dev/null` kind, and the credential-shaped fixtures the credential detector is
tested against. **No personal path and no real credential**, re-verified
directly. The disposition is unchanged: declared, not remediated, and the input
to a publication decision rather than a substitute for one.

## Closure audit — round 8, the last authorised cycle, also killed by its provider

The final release-authority read was **terminated mid-run by the provider's
content filter**, like round 6, after 286K tokens and a zero-byte report. Its
stderr held 650KB of durable partial output, and four probes were recovered from
it before anything was retried. Three were real.

**The reader had gone straight at the structural change**, which is what the
brief asked it to do, and it found the two things wrong with it.

### The inspection guard was a module-level flag

One thread held inside the inspection, a second public read issued from another
— and the second **skipped its inspection entirely** and ran against a
repository nobody had checked. A guard against a function calling itself had
become a guard against anyone calling it, which is a different and much larger
claim, made by accident. Thread-local now.

That is the second defect in the general defence found by a reader, after the
fail-open on an unreadable config, and the fourth in it overall. **The check
that replaced five route-by-route patches needed four repairs of its own** —
worth recording plainly, because "we closed the class instead of the route" is
the kind of sentence that sounds like an ending.

### A commit message is not a blob

The blob walk skips commits because they are not blobs, so a private term
written into a **commit message** scanned CLEAN — close to the most likely place
for one to be, and the last place a complete-history scan still did not look
after ref names and tag messages were added one round earlier.

### And the same integer defect, one field over again

`max_bytes_per_write: "not-an-int"` raised a bare `ValueError` out of `derive`.
The pid repair two rounds earlier did not generalise **because it was written as
a repair for the pid rather than for the class** — every integer a saved record
carries is untrusted input, and now every one of them is checked.

### What was NOT a defect

An output root reached through a symlinked alias classifies normally when the
contract names the task that owns it, and returns UNKNOWN when it does not. The
owner marker still governs; an alias is a second path to the same root, not a
second owner. Checked rather than assumed, because the previous three findings
in this area were all real.

### The routing fact, twice now

Two of eight cross-vendor readings were ended by the provider's content policy
rather than by capacity or by a hang, and **both times the findings were
recovered from stderr and both times they mattered**. An auditor that dies is
still evidence if its working output is durable — which is the recovery contract
this release ships, applied to the release's own audits. Recorded as
`environmental_failure`; it charges no budget.

## Cycle 9 — the founder-authorised ninth reading

Granted specifically to audit round 8's repairs. **NOT READY: five properties
did not hold, plus a test that could not fail** — and the first finding is that
round 8's own commit-message repair was broken three ways.

### The repair from one round earlier was wrong three times over

`commit_messages` asked Git to format the bodies — `rev-list --format=%B%x00` —
and split on NUL. The reader took that apart in a paragraph:

*   Git writes a newline after each formatted record, so **every message except
    the tip came back with a leading newline.** A pattern anchored to the start
    of a message stopped matching and the scan reported clean.
*   A message containing a NUL byte was **truncated at it** — precisely the byte
    chosen as the delimiter.
*   An empty message came back as `"\n"` rather than `""`.

It also cost one full history walk per ref.

Now read from the raw commit objects through `cat-file --batch`, which states
each object's size and then emits exactly that many bytes: **the boundary is
counted rather than searched for**, so nothing inside a message can be mistaken
for the end of it. One pass, and the merge-parent, empty-message and NUL cases
each have a test.

**The test that was supposed to cover this could not fail.** Its fixture had one
commit, so `HEAD` *was* the whole history and it could not tell traversal from a
single read — the reader proved it by replacing the function with one that reads
only the tip. Seventh instance in this release of a check passing for a reason
it does not state; the fixture now has an ancestor, a side branch and a merge.

### A deadline the constructor never looked at

`Wait.__post_init__` validates `not_beyond_seconds` **only for observable
kinds**, so a `human` wait carrying `"not-a-number"` loaded, skipped the check,
and raised a bare `ValueError` out of `expired_at`. And a `max_bytes_per_write`
of `0` or `-5` is an integer, so it passed the type check and reached
`OutputContract`, which refused with a `PreconditionError` that escaped
`derive`. **A refusal from the wrong layer is still an exception where the
contract is a state.**

### A hard link, after the symlink

The symlink repair one round earlier closed the shape it could see. A regular
hard link into another task's finished chunk is indistinguishable from a first
name by `is_file()`, and alpha's artifact read back as beta's.

The check is `st_nlink > 1`, and **it is symmetric — which is correct rather
than over-broad.** Both names report two links, so alpha is flagged too, and
nothing on disk distinguishes the root that wrote the bytes from the root that
linked to them. What is true of both is exactly what the check says: these bytes
are also somewhere else. `UNKNOWN` loses nothing, because `resume_plan` refuses
to act on it. The first version of the test asserted alpha was still fine, and
that assertion was the thing that was wrong.

### Arithmetic that skipped an unknown is not arithmetic that cleared it

`capacity.gate` computed production against the reserve, found room, and
answered a confident `DISPATCH` while carrying *what reading the result would
cost* as unknown. **The reserve exists for the result.** That is the failure
this module was built from — eight dispatches on one window returned two results
and lost eighty-one records — reappearing as a skipped term. Any remaining
unknown now yields `DISPATCH_SERIALLY`.

### The claim that was too strong

`close_gate(against=UNSTATED)` closes, and the reader was right that the literal
property *evidence cannot close a tree it was not gathered from* therefore does
not hold universally. The escape is deliberate and stays. **The claim was
narrowed instead:** a mismatch is always caught, and the only way past the check
is to write the words in the caller's own code where a reader of that code sees
them. A disclosed gap is not the same as no gap, and it was being described as
if it were.

Five mutants over these repairs, all killed.

## The final evidence-closure check, and the two things it found in the evidence

*Do not assume completeness from counts alone.* The check was run as a
cross-reference rather than as a reading: every verified reproduction in the
capability map traced against the closure matrix, the recurrence-class map and
the gate record; every mechanism's disposition parsed against the authorised
vocabulary; every oracle named in an `ALREADY_COVERED` row executed.

It found two defects **in the evidence artifacts themselves**, which is the only
place a check like this can find anything.

### Sixteen mechanism identifiers named two mechanisms each

The matrix had grown in two places. `M-08` through `M-25` existed already, and
eighteen rows added across rounds 4 to 9 reused exactly those numbers for
different mechanisms — so `M-12` meant both *an object with two names is
examined under one* and *formal conformance certifies unreadable public
history*, and a citation to either was ambiguous.

**A closure matrix whose identifiers do not identify is not a matrix**, and this
is the release's central evidence artifact. The added rows are `M-30` to `M-47`
now; 67 rows, 67 unique identifiers. The one prose citation of a colliding
number — `M-17` in this document — was checked and refers to the older row it
always meant.

### Six rows claimed coverage and two of them named nothing

The authorised vocabulary is PREVENTED, DETECTED_AND_BLOCKED,
SAFELY_RECOVERABLE, **ALREADY_COVERED — demonstrated by an existing mechanism
and a discriminating oracle** — and DEFERRED. The matrix said `COVERED`, and its
own definition asked for *demonstrated rather than asserted* — but one row read
only *inherited from 2.2.0; no new evidence in this phase*, and another *inherited
from 2.2.0 unchanged.*

That is a description of inheritance, not a demonstration. **Coverage claimed
without an oracle is the assertion this matrix exists to refuse, made by the
matrix.** Four rows now name the oracle that would go red and it was executed;
one — contract, classification and sandbox gaps — is `DEFERRED` with the reason
written out, because no discriminating oracle was demonstrated for it in this
release and calling it covered would have been the drift.

### The counts, after the correction

    mechanisms                67, with 67 unique identifiers
    PREVENTED                 38
    DETECTED_AND_BLOCKED      20
    SAFELY_RECOVERABLE         3
    ALREADY_COVERED            5   every one naming an oracle that was run
    DEFERRED                   1   with its reason, and bounded
    outside the vocabulary     0
    reproductions with no closure trace   0   (74 checked)
    recurrence classes proved against an executing oracle   39 of 39
