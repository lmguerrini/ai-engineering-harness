# Changelog

## 2.4.0 — qualification belongs to a configuration, not to a family

A **MINOR** release (`DECISIONS.md` D11, and proposed D26 in
`docs/RP2.4-D26-PROPOSED.md`), derived rather than assumed:
no authority, contract or migration change is incompatible — `requires.routing`
is new and defaults to false, no public name is removed, no pinned project moves
— and the release ships tools that did not exist, which PATCH does not cover.
**State `QUALIFIED_AND_FROZEN`** — a project may pin it, at the revision and digest
its own `PROJECT.yaml` records and verifies. Frozen is not published: no push, tag,
remote or consumer migration is authorised. Gate: `docs/RP2.4-GATE.md`.

### The defect, reproduced before anything was written

Executed against the shipped observation log and the shipped module, a model with
**zero observations** returned `qualified_for("blind_closure_audit_cross_vendor")
-> True`, on seven observations none of which recorded any observed model at all.
`policy/routing-policy.md` had forbidden pooling across configuration strings for
two releases while `backend_contract.grades_from_observations` keyed on
`(family, task_class)` and pooled across them. The prose was right, the code did
the opposite, and nothing compared the two.

### Designed first, and falsified twice before implementation

The design record was frozen against the 2.3.0 release commit and sent to two
independent cross-vendor readings **before any implementation existed**. Both
returned NOT SOUND — four blockers and nine majors between them, findings
partly disjoint — and every factual claim was reproduced by execution before it
was accepted, including one the coordinator had stated wrongly in the design
itself. What they changed: the key, the availability axis, the equivalence rule,
the independence predicate and all thirteen oracles. That is the whole point of
`skills/core/design-falsification.md`: the cheapest thing to change was still a
paragraph.

### Configuration identity

- **Nine keyed dimensions** — surface, family, client, observed model, effort,
  isolation, network, authentication class, task class. Change one and it is a
  different configuration, `unprobed` until dispatched. The client build and the
  capacity pool are carried, reported and deliberately not keyed; a governed
  `Invalidation` answers when a client change really did alter capability, and it
  is capped so removing adverse evidence can never manufacture a `confirmed`.
- **An incomplete identity answers nothing.** `UNKNOWN` in a keyed dimension, or
  a provenance saying the identity was not observed, and the configuration is
  `unprobed`. A requested slug copied into the observed field is refused as
  loudly as an absent one.
- **The migration is that rule and nothing else.** No observation predating this
  release records an observed model, an authentication class or a surface, so all
  of them are prior evidence and none is a track record. Nothing was rewritten
  and nothing was invented.
- **Family history is display-only.** Printed beside an `unprobed` answer, and it
  ranks nothing, satisfies no eligibility test and breaks no tie.
- **A declared alias moves no grade**, and may not cross a surface, family or
  client. It surfaces the other identity's evidence as prior, labelled.

### Availability is its own axis

- Keyed on the configuration **plus the dispatch preconditions**. This log holds
  one configuration where standard input decided whether the dispatch started at
  all, and a scheme in which the success answers for it routes to a known hang.
- Fed only by observed dispatch outcomes. **Discovery is never availability**: a
  model listed in the local document was refused outright by its provider, and
  the same account offered different model sets under two client versions minutes
  apart. Absence from a document refuses nothing either.
- A refusal outranks a success recorded the same day, and an observation from a
  different client is reported rather than answered with.

### Dynamic discovery, guaranteed rather than observed

- A previously unknown identifier reaches a route report **with no Core edit**, in
  any alphabet, with no normalisation and no validation of shape. The reader
  takes FIELD names, which an adapter can describe; it never takes model names.
- A test asserts the toolbelt contains no model identifier at all, matched as a
  shape so the guard cannot age the way the vocabulary it replaced aged.
- A reading carries its producer, its age and its skew against the dispatching
  client. Static tables — this file, the routing table, an adapter's — are
  explicitly subordinate to it.

### The ladder, and the way onto it

`DISCOVERED -> UNPROBED -> PROVISIONAL -> CONFIRMED`, in the pack's existing
vocabulary with no duplicate semantics. An unprobed configuration takes work only
as a **declared probe** whose outcome is evidence for what it tested and nothing
else; one success is `provisional` and qualified nowhere else. A probe never
fills a mandatory independent audit leg or a critical-domain promotion — rows 12
and 16 keep their human.

### Independence, corrected

Independence is a property of the **producer** — worker, session, and provider
where a leg is declared cross-provider — never of the configuration. Comparing
configurations is wrong in both directions: the same session auditing its own
work has a different configuration once the task class changes, and two genuinely
fresh blind sessions have the same one.

### Publication safety that does not age

The literal `gpt-5` is replaced by a generation-agnostic pattern in the same
tier. It matched `gpt-5.6-terra` and not `gpt-6-astra`, so the vocabulary had
already stopped covering the models in use — a literal per slug means a release
per slug. Falsified against a corpus of current slugs, synthetic future slugs and
legitimate public prose, and asserted to cover everything the literal covered.
What it does not cover, deliberately: a bare codename with no vendor prefix.

### Observability

A routing panel in the projection, deriving from the same functions in the same
process on every render, holding nothing. Per-configuration qualification and
family prior are shown as two things and never summed; `UNKNOWN` renders as
`UNKNOWN`.

### One governed waiting path

The coordinator hand-wrote three background monitors that could never terminate:
`pgrep -f` matches a whole command line including the waiter's own, so each
matched itself and survived about an hour against producers that had already
finished and been read. The first reading was a session mistake. The correct one
is that **the pack held two answers to one question** — `waiter_command` treated
a zombie as ended, `continuation._process_is_gone` asked `os.kill(pid, 0)` which
succeeds for one, and the durable state model had the wrong answer.

- **One liveness answer**, `progress.process_has_ended`, which `continuation`
  delegates to so the two cannot drift apart again.
- **The waiter belongs to the wait**, and one matching a command line is refused
  where the wait is declared — as a class, because deciding which patterns are
  safe is the argument that produced the incident.
- **`continuation.reconcile`** derives eight dispositions from the record and
  the process table; a monitor is not an input to any of them.
- **`UNGOVERNED_BACKGROUND_WORK`** names a declared wait carrying no waiter.
- A dashboard panel over the reconciliation, and a cold reconstruction that
  reaches the same answers from disk alone.
- Not closed and not claimed: a coordinator can still wait in a shell and record
  nothing. Seeing that would mean policing the coordinator's own shell.

### A run that executed nothing is not evidence

A targeted run exited in 0.56s and was nearly recorded as a forty-five-fold
speed-up; it had selected zero tests, because the selector said `never_prints`
and the test is called `ever_prints`. `tools/selector_evidence.py` records the
intended selector and the collected, executed, skipped and deselected counts,
and answers `NOT_EVIDENCE` below what the caller expected. **Two runs are
comparable only over the same test population.**

### Verification cost, and a withdrawn claim

Two subprocess fan-outs were a third of the suite. Both now run concurrently over
the same commands with the same assertions, mutation-tested afterwards to prove
no detection was lost.

The whole-suite speed-up this entry used to claim is **withdrawn**. Measured
properly, the two sides ran different numbers of tests — the delta adds some —
which is precisely the comparison `selector_evidence.comparison_problems` refuses
of anybody else. An independent reader noticed the claim carried none of the
counts its own rule demands; producing them showed the comparison cannot be made.

### What the closing pass changed, and what found it

Four independent readings of the finished candidate — two providers, fresh
sessions — returned NOT SOUND or NOT READY between them. Their findings moved
steadily: the first two found defects in the release, the third found them in the
repairs the first two prompted, and the last two found them only in the oracles
written for those repairs, with the pack's behaviour correct in every case.

Two defects only running the assembled thing could find, both of which would
have met an adopting project first:

- **A checkout on a machine that normalises line endings failed its own pin.**
  `core.autocrlf=true` is the Git for Windows default; cloning this branch under
  it rewrote LF to CRLF in every tracked file and `tools/pack_pin.py` reported
  PACK PIN NOT VERIFIED **against a checkout of the correct revision**. Closed at
  the cause by `.gitattributes` declaring `* -text`; three clones under three
  line-ending settings now produce one digest. The oracle asks Git whether any
  tracked path still carries an attribute that rewrites bytes — `text`, `eol`,
  `filter`, `ident` or `working-tree-encoding` — because checking `text` alone
  passed while a smudge filter changed a file from 14 bytes to 17.
- **A project's declared paths were resolved against the process, not the
  project.** `ProjectContract.repository()` returned a relative `repo_path`
  verbatim, so `commit_gate --range`, `outgoing_scan`, `workspace_report` and
  `publication_gate` all ran against whatever repository the invoking shell was
  standing in; the multiproject history view showed one repository's commit count
  under two projects' names. The same class was then found live in two more
  places: `project_context.py` verified a context digest against **another
  project's context** and reported CURRENTLY_VERIFIED, and `adapter_pin.py`
  reported an adapter clean over another directory's bytes — and, once the file
  half was repaired, over another directory's **executable**. All four are
  resolved against the contract, whose own path is now absolute at load.

Governance and integrity:

- **D26 and D27 are in `DECISIONS.md`.** The row-7 narrowing was authorised by
  the founder before the entry was written, which is that row's application
  point. `docs/RP2.4-FOUNDER-AUTHORISATIONS.md` records the authorisation and the
  ten conditions it carries, and `tools/tests/test_founder_authorisation.py`
  makes each one executable: a later change that broadens D26 past what was
  authorised breaks the suite rather than passing quietly.
- **One commit's message was repaired under founder authorisation**, with both
  tree objects reused rather than re-derived — ten commits before and after, same
  order, whole-range diff empty. It was there because a shell chain's `&&`
  attached to `tail -1` while the gate printed VIOLATION and exited non-zero.
- **The bypass was removed, not re-checked.** `templates/commit-msg.hook` moves
  the contract into Git, which refuses the commit on a non-zero exit whatever the
  caller's shell does with pipes; it uses the project's own declared vocabulary
  where a contract exists, and refuses rather than passing when it cannot find
  the gate. Replay paths (`cherry-pick`, `rebase`) are not covered and the file
  says so; `commit_gate.py --range` catches those.
- **A release root that something else can move is now named.**
  `pack_pin.root_kind` reports a linked worktree, and `capability_open` prints it
  beside a verified pin as a note rather than a block — a linked worktree on its
  pinned revision is a correct checkout of the right tree.

Rehearsals and evidence:

- `tools/tests/test_two_consumer_rehearsal.py` runs two adopting projects at
  once against one pinned release, differing in every declared way: one declares
  an executable adapter and a Git repository, one declares neither. They run
  concurrent background producers held alive while their waits are declared and
  reconciled, each against its own recorded process; one consumes its result
  without settling the other's; both reconstruct cold in a fresh interpreter.
- `tools/tests/test_adoption_rehearsal.py` holds the sixteen adversarial routing
  situations and the full adoption lifecycle;
  `tools/tests/test_background_governance.py`, `tools/tests/test_qualification.py`,
  `tools/tests/test_routing.py`, `tools/tests/test_model_discovery.py` and
  `tools/tests/test_selector_evidence.py` hold the mechanisms this release added.
- `tools/model_discovery.py` reads a discovery document through FIELD names and
  never through model names, `tools/qualification.py` derives the
  per-configuration grades and `tools/routing.py` the availability axis and the
  design-audit route.
- **The whole new-model lifecycle was proved live** through the installed
  subscription surface, with the target chosen by absence of evidence rather than
  by name: discovered, classified `unprobed` with its family history beside it,
  refused for routine and critical work, dispatched as a declared probe, its
  identity read from the execution surface, and graded `provisional` then
  `confirmed` — qualified at the configuration it ran on and `unprobed` at a
  different effort, task class, isolation or client.

Records a reader needs, all new: `docs/RP2.4-GATE.md`,
`docs/RP2.4-RELEASE-PACKET.md`, `docs/RP2.4-ARCHITECTURE.md`,
`docs/RP2.4-CAPABILITY-MAP.md`, `docs/RP2.4-INVENTORY.md` (every recorded
limitation classified as fixed, worth fixing, a real bound or future work),
`docs/RP2.4-PUBLICATION-ADJUDICATION.md` (the pack's own history, adjudicated —
and one occurrence names a real machine account, stated rather than denied),
`docs/RP2.4-FOUNDER-AUTHORISATIONS.md`,
`docs/RP2.4-BACKGROUND-RECONCILIATION.md`, `docs/RP2.4-HITL-PREFLIGHT.md`,
`docs/RP2.4-D26-PROPOSED.md`, and the two frozen design records
`docs/RP2.4-DESIGN-C40-qualification-identity.md` and
`docs/RP2.4-DESIGN-C47-governed-background-work.md`.

### The behaviour a reading found when it stopped reading deltas

Three bounded readings of three repair deltas found fewer and fewer defects and
none in behaviour, and this release read that as convergence. It was the deltas
converging. A reading pointed at the modules a consuming project actually calls
returned **seven reproduced defects** in code no repair had touched since the
first round — three of them the class this release's headline repair was for,
two mechanisms answering one question differently:

- readiness reported an adapter VERIFIED where the adapter verifier itself
  refused, because `capability_open` called it by a path the repair to
  `verify_contract` never reached;
- `derive` did not consult a recorded producer where `reconcile` did, so one
  record was WAITING and RECOVERY_REQUIRED at once;
- the projection's headline resolved artifacts against the process while its own
  panel resolved them against the record, so one page gave two answers.

And four more: a content exemption covering a path it was not written for, with
content arriving at a new path never scanned there — repaired by reading the
trees for blobs as well as for names, through the new
`gitread.blobs_at_paths_in_outgoing_range`; a JSON null becoming an established
qualification dimension as the string `None`; an unscoped human blocker covering
nothing in the page that reads it, while `continuation` returned
BLOCKED_ON_HUMAN; and availability timestamps ordered as text, so a success in
one offset outranked a later refusal in another.

All seven are pinned in `tools/tests/test_behaviour_findings.py`, and eight
mutants reverting them die.

### Evidence that repeats a known failure

`policy/recurrence-classes.json` has been the deduplication mechanism since
2.3.0. `tools/evolution_evidence.py` adds the half it lacked: a recurrence
strengthens the class it belongs to with its own provenance instead of becoming
a second record of one failure; a proposal closely resembling a recorded class
comes back for a distinction rather than being merged or accepted; occurrences
are appended and never rewritten; and an engineering-loop failure — a vacuous
oracle, a lost exit code, an audit reading the wrong revision — is evidence like
any other. `tools/tests/test_evolution_evidence.py` executes every case,
including reading provenance back through a fresh interpreter.

### The delta contract, from here on

This entry is the release delta, and `tools/release_delta.py`, with
`tools/tests/test_release_delta.py` proving it can say no, checks that it
accounts for what the release changed: every file the range added, and every
decision it recorded, must be named in the version's own entry. It exists
because this entry stopped being updated partway through and ended up naming one
of four new tools, none of eight new test modules and two of fourteen new files —
so the question *what changed from 2.3.0 to 2.4.0* could only be answered by
reading the commit range, which is what a changelog is for.

    python3 tools/release_delta.py . --baseline <the previous release's revision>

`2.5.0` states its delta from `2.4.0`, `2.6.0` from `2.5.0`, and the check runs
in the suite against the manifest's own version, so a release cannot be prepared
with an entry that silently omits what it added.

### Erratum against 2.3.0

None. 2.3.0 is untouched and verifies byte-identical throughout this evolution.

## 2.3.0 — durable execution, liveness, capacity truth and complete-history safety

A **MINOR** release (`DECISIONS.md` D11 and D24): new backward-compatible
capability, plus enforcement of guarantees earlier versions already promised.
**State `QUALIFIED_AND_FROZEN` — frozen by the founder, and adoptable at a project's next capability boundary.** Every defect
below was reproduced by execution against the frozen 2.2.0 baseline before it
was repaired, and every repaired guarantee carries an oracle that fails against
the pre-repair behaviour. Gate: `docs/RP2.3-GATE.md`.

### Closing ACTIONABLE_WORK + SILENT_IDLE

The release produced another instance of the failure class it was closing — a
dispatched audit held this session for **five hours and thirty-nine minutes** on
a process with 0.34 seconds of processor time and no output — and the incident is
the evidence.

- **A wait declares how long the coordinator will remain in it**, and an
  observable wait without a deadline is unwritable. Past it the state is
  `RECOVERY_REQUIRED` whatever the process is doing: a live process satisfies a
  liveness question forever, so the deadline is what ends the wait.
- **The stall classifier measures the horizon against how long the run has been
  flat**, not the gap between two samples. Sampled 90s apart it had reported
  `RUNNING` for a run dead five hours — a caller who polls could never have seen
  a stall.
- **A wait names the obligation it discharges.** Two live waits on one
  obligation are refused rather than raced; retiring frees it, and retiring is
  not deleting.
- **A blocker says what it blocks.** An unscoped one still blocks everything;
  one scoped to a stalled process no longer silences unrelated authorised work.
- **`progress.waiter_command`** watches a registered process number, because the
  reason a coordinator hand-writes a waiter is that the pack shipped none — and
  the hand-written one matched its own pattern and could never terminate.
- **`docs/RP2.3-FAILURE-MODE-CLOSURE.md`**: every verified in-scope failure
  mechanism with an explicit disposition, and the five residues that remain.

### Repairs from closure audit round 1

Two blind auditors, one cross-vendor on an independent pool, both NOT READY,
findings almost disjoint. Fifteen repairs, every finding reproduced first.

- **The closure-anchor check went green exactly when the loss became
  irreversible.** A destroyed forty-character citation fell into the state
  reserved for prose. It is now `DESTROYED`, blocks, and has its own headline.
- **The read-only Git layer could write a ref.** `probe` took the verb as a
  parameter, which put back every write verb `DECISIONS.md` D2 extracted the
  module to leave behind. Repaired with an allowlist, a subcommand check for
  `git bundle`, and a transport that may be enabled only for the one verb the
  postcondition is scoped to.
- **A non-finite number passed every guard rather than failing one**, in the
  capacity gate and the progress classifier. Finiteness is now checked before
  the sign.
- **Four guarantees held in a generator and failed at a boundary**: an
  occurrence key omitting where it was found, an exported attestation
  constructor carrying no declared set, `PASSED` accepted with no exit status,
  and a premise compared by substring so `10` still reproduced as `100`.
- **A wait whose completion condition was satisfied before the job started.**
  Declaration and reconstruction are now different entry points, because the
  first repair made a saved record unloadable.
- **A completion marker beside a chunk still in progress**, and an over-bound
  chunk under a clean headline. Both `UNKNOWN`.
- **A guard that could not fail**: the held-prose check fell back to zero when
  its regex stopped matching, and would have passed with the disclosure deleted.
- **A vocabulary with no producer**: a decision now produces an outcome.
- **The public-safety disclosure was inherited verbatim and unfalsifiable**, and
  is re-measured with this release's own tool: 2090 unadjudicated occurrences
  over the complete reachable history at the strict tier, not ten in four files.

### Repairs from closure audit round 2 — the bounded delta re-audit

**Three of five blockers were defects in round 1's repairs.** That is what a
delta re-audit is for, and the reason a final repair is unaudited by
construction until the next one.

- **A read-only allowlist still wrote.** `config` was permitted because *"a
  write needs a value argument this module never passes"* — while `probe` is a
  varargs API and the caller passes the arguments. An auditor set and unset keys
  through it, and `diff --output=FILE` created a file. A verb whose
  read-onlyness depends on its arguments now declares the forms it may take, and
  options that make a read write are refused. The test that should have caught
  it asserted twenty-four verbs were absent from a list they were never on; it
  now runs **every permitted verb** and asserts the repository is byte-identical
  afterwards.
- **A deadline that could not be parsed never expired** — and round-tripped
  through save and load, putting the indefinite wait this release exists to end
  back within reach from disk. A deadline nobody can evaluate has passed.
- **A naive ISO timestamp raised a `TypeError` out of `derive`**, so the shipped
  command printed a traceback where it should have reported a refusal.
- **A blocker naming one of five items silenced the other four** — the scenario
  in its own docstring. A blocker stops the run only when every outstanding item
  is one it names.
- **A finished, consumed wait in a terminal record reported `RECOVERY_REQUIRED`**
  permanently, because time only moves one way. A wait that finished is not
  waiting.
- **The generated waiter interpolated its sentinel path into a shell string
  unquoted** — a hole the hand-written waiter it replaced did not have. Quoted,
  and the regression asserts it by running the generated condition.

Six tests that passed for reasons they did not state were repaired rather than
deleted: `DESTROYED` claimed *"gone from this repository"* about blobs the
repository holds, an attestation accepted two contradictory outcomes for one
profile, and `classify` trusted a `flat_since` that its own two identical
readings contradict.

### Repairs from closure audit round 3 — the blind cross-vendor read

**Six of the eight findings were already repaired, and the report could not say
so.** The auditor had read a snapshot taken before rounds 1 and 2; it never
stated the revision, so only re-executing all eight, one at a time, could
distinguish a live defect from a repaired one.

- **Evidence about a different tree does not close this one.**
  `close_gate(..., against=(revision, digest))` refuses it. The harmless
  direction is the one that happened; the other is a clean audit of an old tree
  reading as clean for a new one, which is a green gate over a tree nobody
  examined. **An audit brief now states the revision and digest the auditor
  read.**
- **A rewrite mapping was accepting its own assertion as evidence.**
  `{orphan: any_reachable_commit}` cleared the orphan: *reachable* is a test
  every reachable commit passes equally. A successor claim is corroborated
  against the preserved original in a verified bundle, or it is
  `REMAPPED_UNVERIFIED` and blocks, naming what would settle it. A mapping
  handed in by keyword is held to the shape its file loader enforces.
- **A wait completed on `/dev/null`.** The declaration-time refusal was correct
  and unreachable — a record built directly never passes through it, and making
  it a constructor invariant makes a legitimate saved record unloadable. So the
  observation asks again in the two forms that survive a reload: a sentinel is a
  regular file, and it does not predate its own wait.

### The continuation rehearsal, and a dispatcher mistaken for a route

Seven steps, executed, with the reconstruction in a **separate process** that
receives a path and nothing else — a same-interpreter rehearsal shares the
objects it claims to be recovering. Step 6 asserts the reconstructed coordinator
waits rather than sending a second worker after an obligation that already has
one. Step 7 writes a summary beside the record saying the work finished, in the
place a compaction summary would live, and requires the derived answer not to
move.

Two cross-vendor dispatches held a named wait for **5h39m and 6h42m** at a third
of a second of CPU each. The third, identical but with **stdin closed**, wrote
120KB in three minutes: the dispatcher had been reading standard input. The
release was about to record *cross-vendor is unreliable* as field evidence about
somebody else's software. What held without needing the cause understood is the
deadline on every observable wait — and the next cause will also not be
understood at the time.

### Repairs from closure audit round 4 — the release-authority read

Ten findings against the candidate itself, all reproduced before repair. The
report opened with the revision and digest it had read, which is the requirement
added one round earlier working as intended.

- **A read-only Git interface ran the subject repository's own configured
  program.** `diff.external` in a scratch repository's config and any `diff`
  through the public API executed it — **with or without `--ext-diff`**. For a
  module whose purpose is reading repositories other people control, that is
  arbitrary code execution on every diff. The neutralised-config table had said
  since 2.2.0 that *"the diff family has its own switch for this"*; the switch
  was never passed. `--no-ext-diff` and `--no-textconv` are now passed and the
  options that undo them refused — the switch rather than a config key, because
  it also disables the `.gitattributes`-selected driver.
- **The complete-history scanner reported clean about objects it had not read**,
  printing `NOT SCANNED` two lines below the word. A skip now makes the report
  INCOMPLETE and the exit non-zero.
- **Two paths sharing one blob produced one occurrence.** `git rev-list
  --objects` names an object once, so the second path was never enumerated at
  all. Names come from the trees now.
- **Two blockers each covering half the outstanding work stopped nothing**, and
  the report said *nothing is in the way and nothing is outstanding* above a
  list of both. Coverage is a property of the union. This is round 2's
  `any`/`all` defect one level up: that round fixed the quantifier inside the
  predicate, this one fixes the set it is asked about.
- **One task's complete output root classified as another task's result.** The
  owner marker was being written for exactly this and only the writer read it.
- **A non-finite stall horizon** produced STALLED with no flat signal and
  RUNNING for a run dead a thousand seconds, and **a capacity reading with no
  `observed_at`** gated a dispatch — the same rule as an earlier round, one
  field over.
- **A `pid` of `"not-a-pid"`** reloaded and raised a bare `ValueError` where the
  contract is a named state.
- **Two digest tests compared a pure function with itself.** Replaced by the
  property they stood in for: the digest is content-addressed, so a file
  rewritten with identical bytes and a moved mtime leaves it unchanged.

One finding is closed as far as it can be rather than closed. *An unrelated
writer can satisfy a path wait* is correct and stays correct: no property of a
bare filesystem path names who wrote it. The observation is strengthened to what
a filesystem can prove, `OUTPUT_ROOT` is the kind that establishes a producer,
and a test pins both halves so the weaker claim cannot quietly become the
stronger one.

### Qualification

- **`docs/RP2.3-RELEASE-PACKET.md`** — what a returning release authority reads
  first: what the release deliberately does not do, why it is MINOR, and the
  mutation history, because nine mutants survived their first pass and every one
  was the same shape.
- **Held prose is disclosed by composition.** The in-release half is under the
  ~2,000 target; the total is over because of the two installed adapters, which
  are counted and cannot be frozen. Two blocks were relocated to `docs/` under
  the pack's own rule that `policy/` holds what governs and `docs/` holds what
  happened, and the in-release half was **not** shaved to offset the adapters.
- The cold-continuation drill was run against this session's own tree: five
  reads and one Git check reconstruct the position with no conversation.

### Launch, migration and compatibility

- **A pre-2.1 contract is named as legacy rather than reported as a type
  error.** A live project has been unreadable by every `--project` tool since
  the schema changed; the refusal now states the current shape, points at the
  template, and says the entries are not migrated automatically, because the
  two tiers differ in whether a term applies to blob content.
- **Four new representative consumer shapes**, including one carrying none of
  the keys this release adds — the MINOR claim, as a test. Plus the first
  collection of shapes that must be **refused**, each naming what its refusal
  has to say.
- **A release index now exists beside the release roots.** It omits 2.1.1
  deliberately: that release has no root of its own, and listing the working
  checkout would enshrine the D18 defect rather than record it.
- **The migration gate refuses any target that is not `QUALIFIED_AND_FROZEN`**,
  and that is a test. It refused this release throughout its candidacy.
- The launch contract gains one sentence: the index exists, an entry is a claim,
  and a project runs against its own pin rather than against an index.

### A diagnostic projection that is a projection

- **`tools/projection.py`** renders one read-only view of a project's durable
  state: the pin, the derived coordinator state, durable worker output, capacity
  windows and reserves, and everything it could not read.
- **A renderer, not a service.** One invocation, one answer, exit. No port, no
  daemon, no cache, no database, and nothing else in the toolbelt imports it.
- **It writes nothing and derives nothing.** Both asserted — the first by
  hashing the tree around a render, the second by delegating every question to
  the module that owns it. Where this and the governance record disagree, this
  is the defect, and the view says so in its own header.
- **An absence is unknown, never a resting state**, and the exit status
  distinguishes a complete reading from a partial one.

### A material change begins with a falsified design

- **`tools/design_record.py`** reads a design frozen before the implementation
  it governs: the mechanism, the designs considered, which was rejected and
  why, which was selected, the failure modes of that choice, the authority
  boundaries, and the acceptance, negative and mutation oracles — all named
  before there is anything for them to judge.
- **Composed into `capability_open`**, which is already the one deterministic
  path run before a governed capability opens. It reports; it authorises
  nothing, adds no HITL row and weakens none.
- **Risk-scaled.** `TRIVIAL` needs no record; `ROUTINE` needs the mechanism and
  its oracles; `MATERIAL` needs the whole thing. The class is the caller's
  declaration, because Core cannot know which of a project's changes are
  material — a project may declare `requires.design: true` instead.
- **Freezing is bound to a revision.** The base must resolve and be an ancestor
  of `HEAD`, and where the coordinator names where mutation began
  (`--mutation-begins-at`) it must be a strict ancestor of that too. A design
  frozen against a tree that already holds the work it governs is refused.
- **`skills/core/design-falsification.md`** is the discipline;
  `skills/core/repair.md` remains the other half. One governs what must exist
  before there is a defect; the other what happens once there is one.

### A console over every project, and two histories that score nothing

- **`tools/console.py`** renders one read-only page over every project that has
  adopted this release: an overview at three densities, an all-systems page, a
  control room built for a wide display, cross-project workers, audits,
  capacity, history and identity, a custom-view builder, settings, and help
  with a question index. Monochrome is the default lens; four others ship.
- **It decides nothing.** Every answer belongs to the module that owns the
  question. A figure restates a line, a bar needs a real denominator, UNKNOWN
  is never an absence, and nothing the attention strip marks can be folded away
   — each with a test that fails without it.
- **`tools/activity.py`** reads two histories from what is already on disk.
  Repository activity: local commits by UTC day as a contribution calendar at
  four scales or between two dates, with the remote side read from
  remote-tracking refs and **never from the network**. The relationship is
  containment — `LOCAL TOTAL ⊇ REMOTE-REPRESENTED ⊍ LOCAL-ONLY` — because a
  pushed commit is one commit two refs reach.
- **Four remote states are four different answers**: none configured, never
  observed, observed, unreadable. An unreadable repository reports UNKNOWN
  rather than zero, and a linked worktree is the same repository, not a second.
- **Pack events are rebuilt only from artifacts that carry a time.** Seven
  classes ship because seven are evidenced; every event names the artifact that
  dates it, and the one class that is arithmetic rather than a record says so
  and can be filtered out.
- **Neither is evidence of quality.** No productivity, velocity, developer or
  good-day figure exists, and a test refuses the vocabulary that would add one.

### Close correctness — which gates ran, answered by something other than the runner

- **`tools/close_attestation.py`** generates the closure gate block from the
  contract's declared `validation_profiles`. A profile nobody ran is enumerated
  and reported `UNRUN`; omission is unrepresentable because the list being
  iterated is the declaration.
- **`closure.refuses_on_unrun`** is the project's policy and defaults to `true`
  (`DECISIONS.md` D24). A project that declares otherwise still gets every
  profile enumerated. A failed or incomplete profile stops the close whatever
  the policy says.
- **A decision may declare the command that produces its premise.** Closing
  re-runs it, and a premise that stops reproducing names *the decision that now
  rests on nothing* rather than reporting a failed check. One that could not be
  re-derived stops the close too.
- The attestation carries the exact candidate it was taken against, because a
  later capability's commits invalidate an earlier one's evidence.

### Complete-history public safety, and a profile that keeps internal work out of ceremony

- **`tools/publication_history.py`** asks the question no shipped invocation
  asked: is the **complete reachable history** public-safe at the **strict**
  tier. Every ref, not the default branch. A term committed and then deleted
  survives in a blob every tip-shaped scan misses.
- **Detection ships with adjudication or not at all.** A remediation list is
  refused while any occurrence is unadjudicated, and an occurrence explicitly
  marked undecided blocks exactly as an absent one does.
- **Adjudication is per occurrence and the per-term form is unexpressible.** A
  classification without a reason is refused, and `by_finding` makes a mixed
  verdict legible.
- **The report says it is a finding list, not a remediation list**, and names
  rows 2 and 4. Nothing here remediates anything.
- **`publication.intent`**: `internal` is a first-class answer and an internal
  project is not walked through publication ceremony. The universal safety
  invariants are not profile-scoped, and an undeclared intent cannot switch them
  off.
- **`validation_profiles.<name>.reproducible_by`** declares the environment a
  profile is claimed to run in.

### The pack can check its own history with the rules it publishes

- **`commit_gate.py --default-terms <pack_root>`** applies the pack's own
  default vocabulary to a repository with no project contract — this repository
  being the case that mattered. Resolved through the canonical rule path and
  reported with its digest.
- Found by a coordinator error: a hand-written substring check reported a
  private term inside the word *resolves*, while the shipped scanner
  word-bounds a bare term and reported the same message clean. The instrument
  was not the one that runs, and the reason a substitute existed is now closed.

### Closure anchors — whether anything still keeps a cited commit reachable

- **`tools/history_anchor.py`** reads a project's own records and answers per
  citation: reachable, anchored, remapped, unreachable, not a commit, or
  unknown. Only unreachable and unknown block. Prose that happens to be
  hexadecimal is not a lost commit.
- **An old-to-new revision map ships with the check**, with a declared schema,
  refused when unreadable or when it holds abbreviations — and consulted for a
  commit Git can still resolve, which is what a local rewrite actually leaves.
- **An anchor is a ref or a verified bundle**, and a bundle anchors only the
  commits it carries.
- **Rewrite invariants name the field they broke** — author and committer date,
  identity, tree, order — and a rewrite with no demonstrated rollback is a
  finding. Nothing here performs a rewrite: that stays a human decision.
- `refs/rewritten/*` and `refs/replace/*` are named private namespaces.

### Remote verification — the one check that has to leave the machine

- **The transport widening is scoped to the postcondition, named, and per
  invocation.** `protocol.allow = never` stays; specific protocols are added
  beside it. Every other read in the toolbelt still refuses every protocol, and
  a test asserts it.
- **Enabling the protocol was not enough.** `core.sshCommand = ""` makes Git run
  the empty string, so the read moved from `transport not allowed` to `unable to
  fork` — the same non-functional check in different words. The neutralisation
  is removed for an operation that enables ssh, not set to something.
- **A failed remote read now says why.** A refused transport and a host that
  does not resolve arrived as one sentence, and one of them is a setting this
  pack controls.
- **The expectation set is derived from the authorised refspec** rather than
  hand-typed, and a push form with no derivable expectation is refused rather
  than guessed at.

### The non-regression gate — a compatible addition is not a break

- **A keyword-capable parameter appended with a default is
  `added_optional_parameter`, not `changed_signature`.** No call written against
  the previous signature can fail on it, and the gate's own message says callers
  would break. Reported rather than silenced.
- Everything else still breaks: a parameter without a default, one inserted
  among the existing ones, one removed, a default withdrawn, a kind or
  annotation altered, or a function becoming async.

### Capacity — a refusal before a dispatch, never a queue that dispatches

- **`tools/capacity.py`** gates one proposed dispatch at a time against one
  pool. No queue, no dispatch verb, and a structural test asserting it never
  acquires one.
- **A dispatch states its authority class before anything else is considered.**
  A task carrying a semantic or product decision goes to the executor class it
  was classed for and nowhere else, whatever is still answering. Wait-versus-
  spend is row 15 and is offered as a named refusal rather than an answer.
- **No universal reserve.** The project declares three — coordinator,
  result-consumption, repair-and-audit — and a partial declaration makes the
  total `UNKNOWN` rather than smaller.
- **`UNKNOWN` earns serial dispatch, not a deadlock and not a guess.** A second
  concurrent dispatch on an unmeasurable window is refused; every unestablished
  quantity is named in the decision.
- **A result that could not be read before exhaustion is negative return** and
  is refused. `NOT_DISPATCHED` and `DISPATCHED_AND_LOST` are distinct outcomes.

### Adapter and routing identity — the program, not only the files

- **An adapter may declare the executable it drives**, how to ask its version,
  and the version the project qualified against; `adapter_pin` runs the command
  through a declared blast radius and compares. A digest describes the files and
  says nothing about the binary that reads them, and at this release's baseline
  the two had drifted while every gate passed.
- **All three fields together or none.** A version nothing knows how to obtain
  is a requirement nothing checks.
- **The report states what it verified** — `N file(s), M executable(s)` — and
  names the adapters whose executables were never declared. `4 of 4` over four
  definition files read as a statement about four running things.
- **Routing observations carry `pool_id` and `qualification_basis`.** A pool
  travels with a grade and never changes it. The basis is `field`, `synthetic`,
  or unlabelled, and an unrecognised value is refused rather than folded into a
  known one; a grade whose observations are all benchmarks is annotated so it
  cannot be read as a track record.

### Progress and stalls — a disjunction, because one signal kills healthy workers

- **`tools/progress.py`**: `RUNNING`, `STALLED`, `COMPLETE`, `UNKNOWN` from two
  readings of a run's monotonic signals. **Any** signal advancing means running;
  a stall requires at least two independently observed signals to agree, and a
  single flat signal is `UNKNOWN` rather than a stall.
- **The stall horizon is declared by the caller and refused if absent**, and
  every report states the horizon it was measured against.
- **A stall is a classification, and the report says so.** Ending a worker stays
  a human decision (row 4); this release ships the detection and not the
  termination.
- **A waiter watches a registered run, never a pattern**, and one whose own
  command line matches its own pattern is refused at construction. Completion
  retires every waiter on that run, on any terminal state and not only success.
- A signal present in only one of the two readings is named as such and is never
  counted as flat — a report that did would claim an observation nobody made.

### Coordinator continuation — a state derived from artifacts, so silence has a name

- **`tools/continuation.py`**: eight states including `SILENT_IDLE`, which is a
  **defect** rather than a resting place. The record stores a declaration — what
  is being waited for and how anyone can observe it finishing — and the state is
  **derived** from that plus the artifacts, so it advances on job exit whether
  or not anybody is watching.
- **A declared wait must name an observable completion condition** and is
  refused where it is written otherwise. A wait on a person is the deliberate
  exception and reports as a human block, which names the numbered row it sits
  on.
- **A finished job whose result nobody took up has its own state.** That edge is
  four of five recorded recurrences, and it outranks a job still running so it
  cannot be buried under one.
- **`COORDINATOR_WAKE_REQUIRED` is reported, never performed.** Nothing here
  starts, wakes or creates a session.
- Anything that cannot be established outranks anything that can: an
  unobservable wait, an output root in an unknown state, or a record that
  declares itself both terminal and outstanding, all report `RECOVERY_REQUIRED`.

### Durable worker output — bounded, incremental, recovered before retry

- **`tools/task_output.py`**: an output root a task owns, a chunk scheme whose
  indices are derivable from the brief alone, a byte bound per individual write,
  and the four answers a retry decision is taken from —
  `COMPLETED_WITH_DURABLE_OUTPUT`, `FAILED_WITH_PARTIAL_DURABLE_OUTPUT`,
  `FAILED_BEFORE_USEFUL_OUTPUT`, `UNKNOWN` — read from the artifacts and never
  from a worker's status label.
- **A write is materialised by a rename.** Written to a part file, finished,
  then renamed. A kill before the rename costs that chunk; a kill after costs
  nothing. There is no third state.
- **`UNKNOWN` never resolves itself**, and every one of its reasons is specific:
  a gap in the index, a completion marker that disagrees with the disk or cannot
  be read, two producers writing at once, or bytes the contract does not
  describe. The resume planner refuses rather than guessing.
- **A task that does not bound a single write is refused before dispatch**, and
  a plan never reproduces a chunk that is already complete.
- **A task owns its output root**: one under a declared generated tree is
  refused, because content there is cached rather than stored, and so is one
  another task has claimed.
- `skills/core/worker-contract.md` and `templates/task-brief.template.md` carry
  the obligation; the brief clause is generated rather than written by hand.

### Checker hygiene — the instrument before the measurement

- **`tools/instrument.py`**: what a checker must state about itself before its
  verdict is interpretable. A gate with modes names the active one **inside its
  headline**; an instrument that examined nothing renders `NOTHING EXAMINED`
  rather than `clean`; a rule resolved by a search order must come from the
  declared root, and every report names the file it read with its digest; an
  equivalence gate names the layer it enters each path at and what it therefore
  never reaches; and a tool that launches an external program declares it or is
  refused.
- **The same range, the two tiers, two verdicts, no tier in either headline.**
  Reproduced against the frozen baseline. Elsewhere, a recorded limitation
  quoted one tier's count without saying which, and proposed a remedy that
  could not have cleared the other tier's hits.
- **A scan of an empty range printed `clean (0 commits, 0 blobs)`.** Now a third
  verdict with its own exit status. Not a refusal of empty counts in general: a
  range with one commit and no blobs is a real observation.
- **A checker silently substituted a stale copy of its own rule.** A project
  declaring a pack root whose default term set was absent got a copy from beside
  its own contract, applied it, and could not find out. A search order leaving
  the declared root is now refused, naming everything it looked at. A single
  declared location is *not* a search order and is not refused — it is reported
  as `declared` rather than `canonical`, because refusing it would refuse
  correct work.
- **The public-surface gate now prints the layer it compares at**, with every
  verdict rather than only in `--help`, along with what it never reaches.
- **The read-only Git layer declares the one program the toolbelt launches**,
  and an undeclared executable is refused rather than noted.

### Architecture and session governance

- **`DECISIONS.md` D23** records the founder architecture decision this release
  rests on: 2.2.0 is the non-regression floor; publication obligations are
  profile-scoped; no autonomous restart of a coordinator; coordinator headroom
  is mandatory as a concept and carries no universal number; Core never gains
  generic authority to rewrite history; and the diagnostic projection is a
  projection, with the two corollaries that keep that from being decorative.
- **`DECISIONS.md` D24** decides the version class before the version is cut. An
  obligation an adopting project cannot fail to satisfy is mandatory; one that
  needs new project capability is declared. Generating a close attestation is
  therefore mandatory — its input is the contract's own declared profiles — while
  refusing to close over an unrun profile is the project's declared policy,
  defaulting to refusal.
- **A guard demanded that a superseded release's own gate record be rewritten**,
  and was found by the ordinary act of appending a decision. Two guards
  disagreed about whose documents they were checking: one exempted prior
  releases in terms, the other scanned a typed literal naming one. Both now
  derive their document set from the gate record the manifest declares, both
  scope the changelog to the entry the release is adding, and both refuse to
  pass having scanned nothing.

## 2.2.0 — adapter integrity, tooling integrity, and truth about execution

A **MINOR** release (`DECISIONS.md` D11): new backward-compatible capability,
plus enforcement of guarantees earlier versions already promised. **State
`QUALIFIED_AND_FROZEN` — frozen by human authority on 2026-08-21, and adoptable
at a project's next capability boundary.** Every
defect below was reproduced by execution against the frozen 2.1.1 baseline
before it was repaired, and every repaired guarantee carries an oracle that
fails against the pre-repair behaviour. Gate: `docs/RP2.2-GATE.md`.

### Adapter integrity

- **The installed reviewer adapter declared an isolation mode the reviewer
  contract forbids.** `worker-contract.md` and `audit-brief.template.md` both
  say a reviewer never creates a ref, a branch or a worktree, and say why; the
  adapter carried `isolation: worktree` anyway. Reproduced end to end: that mode
  lands `refs/heads/worktree-agent-*` in the audited repository and
  `publication_gate.py` exits 1 on exactly that ref. Every gate passed, because
  nothing was looking at adapters at all. The mutating implementer adapter
  declared no isolation — the two were exactly inverted.
- **`tools/adapter_pin.py`** gives an adapter a pinning contract: exact
  identity, canonical locator, digest, required/optional status, and the name
  read from the file rather than inferred from its path. Verified at capability
  open, fails closed, and **never refreshes a declared digest** — `--observe`
  prints a current digest labelled an observation, not a verification.
  `required` governs absence only: a present adapter that differs blocks either
  way, and an unreadable one blocks because nothing was established.

### Tooling integrity — every defect reproduced before repair

- **Declared path patterns did not mean what the documentation said.**
  Differentially tested against real `git check-ignore` it diverged in both
  directions — mostly under-matching, and over-matching on a handful: a wildcard
  directory name was compared with string equality, a bare name did not cover
  the directory it named, `dist/*` stopped one level down, and a directory-only
  pattern matched files. The count is computed by
  `test_the_recorded_baseline_divergence_figure_is_the_measured_one` rather than
  asserted here, because it was asserted from memory twice and was wrong twice. Matching is now defined once in
  git's terms — a pattern matches an entity, and a file is covered when the
  pattern matches it or any ancestor. `**` is implemented, matching is
  case-sensitive, and `pathmatch` has its first direct test module, oracled
  against git rather than against a table.
- **A private term in a path could scan clean.** Git C-quotes any path it cannot
  print literally, and the leak scanner read that output, so a directory whose
  name was a declared private term was matched against
  `"session\303\251-private/..."` — which does not contain the term. Every path
  enumeration is now NUL-separated through one decoder. `pack_pin.py` already
  did this and said why; the other four sites did not.
- **An unanswerable git question was rendered as an answer.** `probe`
  distinguishes "git answered" from "git ran and could not answer", and three
  callers consulted only the first: an unreadable `.git/config` reported as a
  repository with no settings — including no `notes.*` keys, the exact surface
  D7 exists to watch — and an ancestry question about a non-commit reported "not
  contained", which the publication gate printed as fact. Both "nobody looked"
  refusal paths also raised `TypeError` instead of a named refusal, latent since
  2.1.1, because `cause=` collides with a positional parameter of that name.
- **Publication reasoning ignored ref object type.** An annotated tag reported
  "carries no extra object", in the reassuring direction, although the tag
  object is an extra object carrying a tagger identity and message. Containment
  is now four-valued — contained, not contained, not applicable, unknown — and
  the object type, already read and never used, selects the sentence.
- **A content exemption switched off the universal rules.** `UNIVERSAL_LEAK_KINDS`
  said no project may declare a credential acceptable, and
  `skills/core/public-safety.md` named the exact mechanism — "writing the
  exemption as *skip blob content* takes both out at once". It was written that
  way. An AWS-shaped key and a home-directory path inside an exempted file
  reported `clean`. An exemption is now a scope over findings, not a skip over
  the object.
- **A Conventional Commit subject was refused as a trailer.** `fix: …` was
  rejected `TRAILER` while `feat: …` passed, so the gate refused the form its own
  contract asks for.
- **The contract reader refused valid multi-line data.** `|`, `>`, `|-`, `|+` and
  a flow sequence spanning lines all raised `unexpected indentation`, so a
  project could not write a multi-line value in the one file D10 makes the single
  source for every gate. Block scalars are implemented in the subset parser and
  verified against a reference implementation across the full cross-product of
  style, chomping and body shape — **no dependency was added**, and D3 holds.
- **Evidence was written world-readable.** Directory `0o755`, entries `0o644`,
  mode checked by nothing. Evidence is now created owner-only and the mode is
  read back from the filesystem, because the mode a call requests and the mode a
  file has are different facts.
- **The repository listing named fewer modules than the release ships**, and
  five more went unlisted while the edits meant to add them silently matched
  nothing. Now complete, and checked mechanically — an omission is harder to
  notice than a lie.
- **Character classes did four different things git does not.** POSIX classes
  (`[[:digit:]]`) matched nothing at all — a silently dead declaration; escapes
  inside a class were passed through to a matcher that doubles backslashes, so
  `[a\-c]` became a range and matched `]`, `^` and `_`; an unterminated bracket
  was read as a literal `[` where git aborts and matches nothing; and an escaped
  `!` was re-emitted in the one position where it means negation, so a class
  written to match `!` matched everything except its members. All four widen or
  invert an exemption silently. Class bodies are now parsed and re-emitted
  rather than forwarded.
- **`**` matching was exponential in the number of segments.** Seven of them
  against a long path took nearly seven seconds, and patterns come from a
  project's own contract — a cliff this release introduced, since the previous
  one had no `**` at all. Memoised; the same case is now under four
  milliseconds.

### Found by running this release against the projects it ships to

- **The contract reader refused a real project's contract outright.** This
  release invented the field name `project_context.revision`; the only real
  Project Context in existence calls it `control_revision` and records its
  digest in prose rather than in a field. Because an absent identity field
  raised, `ProjectContract.load` failed completely — that project's contract
  could not be read **by any tool, for any purpose**, over one optional block.
  An absent field is now `UNVERIFIABLE`, naming exactly what is missing; a field
  present and malformed still raises, because a typo is not an older shape. The
  field is spelled `control_revision`, after the project that has one.
- **Every tool exited on an unhandled traceback when git could not answer.** A
  ref that does not resolve, a repository that cannot be read: the caller got a
  stack trace instead of the stable code and specific cause a refusal carries,
  and could not tell a refusal from a bug in the tool. Every CLI now reports
  `REFUSED <code>: <cause>` and exits on the refusal's own status;
  `SystemExit` and `KeyboardInterrupt` still pass through.
- **`Pin.from_contract` answered about contracts it had never opened.** Given
  anything without a `raw` mapping — a path, for instance — it produced an empty
  pin and reported a well-formed four-field pin as an unverifiable legacy one.
  It now refuses a non-contract.

### Manifest schema

- **`tracked_files` is now `digest_file_count`.** The old name read as the
  number of files git tracks and was always one fewer than that, because the
  manifest excludes itself from its own digest. **The previous spelling is still
  accepted**, so a 2.2.0 verifier can still check an older pinned root during
  migration; a manifest carrying both, disagreeing, is refused rather than
  resolved by preference, and the digest writer leaves exactly one behind.

### New capability — one readiness path

- **`tools/capability_open.py`** answers, in one deterministic read-only pass,
  whether a governed capability may open against a project: is the contract
  readable, is the pin complete and does it verify, is the release it names
  adoptable, do the declared adapters match, is the declared Project Context
  established, is the named capability one this project declared. One aggregate
  state — `READY`, `READY_WITH_UPDATE_AVAILABLE` or `NOT_READY` — over per
  component results that stay semantically distinct.
- **It introduces no new source of truth.** Every component is delegated to the
  tool that already owns that question. It infers nothing only the caller can
  know: the capability boundary is an input, and adoption is refused when it is
  unstated rather than assumed.
- **A newer release is information, never a gate.** A project pinned to an older
  qualified immutable release is correctly pinned until it adopts at a boundary.
  There is no state meaning "blocked because not latest", and an unreadable
  release index leaves availability unknown without affecting readiness.
- **`requires:` in the project contract** lets a project declare that it needs a
  Project Context. A fixture or utility may omit one and be clean; a product
  whose correctness depends on durable semantic authority declares the
  requirement, and then absence is a stop. A requirement governs absence only —
  a *declared* context that cannot be established stops the open either way. A
  requirement key nothing checks is refused rather than ignored.
- **Two questions that had been one:** *is this root what you pinned* and *is
  what you pinned adoptable*. A project pinned to an `IN_PROGRESS` release
  satisfied the first completely, and nothing asked the second.

### New capability

- **`tools/pack_migration.py`** — `pack.root_path`, required, canonicalised and
  verified; `UNVERIFIABLE_LEGACY_PIN` for a pin that cannot be checked, named
  rather than repaired into one that verifies and describes nothing; a migration
  gate requiring a verified target at a capability boundary; rollback only to a
  retained root that still verifies; a release index that lives outside every
  release and is read as untrusted input; and candidate accounting, so one that
  arrived late cannot be skipped. A security advisory is disclosed and
  authorises nothing.
- **`tools/project_context.py`** — a project's durable semantic authority,
  declared, located, revisioned and digested, in five distinct states, with
  non-mutation across a capability proved by comparing the digest and proposal
  separated from adoption. The Core reads no content.
- **`tools/backend_contract.py`** — backend identity where availability cannot
  reach a qualification answer and permission cannot reach a capability answer,
  with per-task-class grades derived from the observation log.
- **`tools/resource_observation.py`** — the documented Claude Code status-line
  rate limits as timestamped routing evidence. Absent means `UNKNOWN`, never
  `0% used`; readings carry their age; the projection is an allowlist, so no
  session id, transcript path or working directory reaches a record.
- **`tools/evidence_index.py`** — certification bound to an exact candidate,
  over raw checker results that cannot be recorded as anything else.

### Decisions

D14 records the founder architecture decision as the current authority layer.
D15–D22 record the rules the repairs established: an unanswerable question is
never rendered as its reassuring answer; an exemption scopes the project's
vocabulary and never a universal rule; the release states its push form once; a
release root is a checkout nobody works in; Project Context is a contract
capability whose meaning stays project-local; readiness is composed and is never
a second source of truth; a newer release is information and only a broken
prerequisite is a gate; and a requirement governs absence, while a declared
thing that cannot be established always stops. D1–D13 are unchanged and no prior
gate record was rewritten.

## 2.1.1 — release integrity: the checks now mean what they said

A **PATCH** release (`DECISIONS.md` D11): backward-compatible fixes, metadata
corrections, and enforcement of guarantees 2.1.0 already promised. No new
capability, no architecture change, no contract migration. An independent
cross-vendor audit returned NOT_READY on 2.1.0's release integrity; every
finding below was **reproduced by execution before it was repaired**, and every
repaired guarantee carries a falsification test that fails against the old
behaviour. Tests **175 → 237**. Gate: `docs/RP2.1.1-GATE.md`.

- **`pack_pin.py` verified less than the sentence it printed.** Six ways, each
  reproduced: a **one-character** `--sha` passed, because the comparison was
  `startswith`; `PACK_MANIFEST.json` could claim any version, because nothing
  compared it to `VERSION`; an untracked non-ignored file sat in the checkout
  unmentioned; the digest concatenated path and content unframed, so path `ab` +
  content `c` and path `a` + content `bc` hash identically; tracked paths were
  split on whitespace, so a committed `a file.md` became two absent entries; and
  every other manifest field — test count, gate record, state — was outside the
  digest by design and checked by nothing. Now: full-SHA equality, NUL-safe
  enumeration, length-framed digest, `VERSION` as the compared authority,
  untracked files refused, manifest metadata validated, and `--digest`/`--state`
  pins. A checker that passes for a reason weaker than its message is worse than
  no checker, because it is believed.
- **The push form was a blacklist, and passed everything its author did not
  think of.** `git push origin refs/heads/main:refs/heads/main` was the only
  supported form; the check accepted `git log refs/heads/main:refs/heads/main`
  (any command at all, given a refspec-shaped token — `rm -rf /` included), a
  second refspec beside the first, a destination different from the source, an
  undeclared remote, and a trailing `--receive-pack=…`. Each rendered as "an
  explicit single-branch refspec, which cannot carry refs/notes/\*" — a sentence
  about a command that was not being run. Replaced by a whitelist of the one
  shape. **The remote postcondition was also blind:** the CLI passed an empty
  expected revision, so it asked only whether a ref of that name existed, which
  a remote stuck on an older commit answers yes to. An expectation with no
  revision is now refused, and the CLI resolves the local ref itself.
- **No contract may forbid and require the same act.** `audit-strategy.md` and
  the audit brief told a read-only reviewer to write findings to a file — the
  failure that lost a repository-wide evidence sweep to a 315-byte apology. The
  brief now states the capture channel **once**: final message when read-only,
  a named file when write permission exists. A reviewer never creates its own
  branch, ref or worktree; where a pinned revision is genuinely needed, the
  **coordinator** prepares the snapshot before dispatch.
- **A filesystem immutable flag is not a control against a live writer**
  (EC-U, adopted in 2.1.0 and silently never implemented). `chflags uchg` and
  its equivalents look like a lock and are not one. The guarantee stays where it
  is checkable: ref namespace + reachability + exact refspec + remote
  postcondition.
- **One grade authority.** `policy/auditor-strategy.md` still asserted both
  audit roles `unprobed` after the Pilot Run moved both to `confirmed`. The
  duplicated grade is deleted; the regenerated `routing-table.md` is the single
  authority.
- **A project pin is now checkable.** `PROJECT.yaml` records version **+** full
  revision **+** digest **+** state, not a version label. Several projects may
  pin one frozen release concurrently, or different qualified releases; a frozen
  release never mutates during a run; project state never enters the pack
  (`DECISIONS.md` D13).
- **Installed skills are adapters, not authority** (`DECISIONS.md` D12), and
  per-project overhead is recorded in that project's `PROGRESS.md` — 2.1.0
  pointed at `policy/overhead-measurements.md`, a file that never existed.
- Also: a release-integrity test that reads the **real repository** rather than
  a fixture, the first permanent regression test for `commit_gate --range`, a
  repository tree in `README.md` derived from `git ls-files`, and stated
  PATCH/MINOR/MAJOR semantics.

### Errata against 2.1.0, as recorded rather than as corrected in place

The 2.1.0 entry and manifest below are **wrong on two counts**, left standing so
the drift stays visible:

- **Tests: 98 → 175, not 98 → 167.** The suite collected and passed 175 at the
  2.1.0 gate, and `docs/RP2.1-GATE.md` records 175 throughout. The CHANGELOG and
  `PACK_MANIFEST.json` figure was never re-read against collection.
- **Held prose: 2,256 lines, not 2,204.** Recounted under the rule
  `policy/BUDGETS.md` declares, unchanged. 12.8% over the ~2,000 target rather
  than 10.2% — still recorded rather than shaved, and 997 of those lines are the
  two installed adapters, which sit outside the release envelope.

`README.md` also still said "Runtime Pack 2.0" under `VERSION` 2.1.0.
`docs/RP2.1-GATE.md` and `docs/RP2.1-DELTA-AUDIT.md` are **left exactly as
written** — a gate record describes the pass that produced it, and correcting
one after the fact destroys the evidence that the drift happened.

## 2.1.0 — evidence consolidation from the completed Pilot Run Project

The first evolution pass driven by a **finished real project** rather than by a
fixture. Its 32 recorded candidates were re-verified against pack source before
any was adopted (`docs/RP2.1-DELTA-AUDIT.md`); the gate is `docs/RP2.1-GATE.md`.
Tests **98 → 167**.

- **Publication is now a ref-namespace contract** (`tools/publication_gate.py`).
  A repository can pass every authorship check while carrying AI attribution and
  session identifiers in `refs/notes/*`, invisible to `git log`, `git status`,
  `git ls-files`, `git diff` and `git show`. Safety rests on an allowed source
  ref **+** containment **+** an exact push refspec **+** a remote postcondition
  verified after, all in the same step as the push — because a writer of
  such refs can re-create them in under a minute and rewrite
  `.git/config` between sessions.
- **The contract is read once, not retyped per gate** (`tools/project_contract.py`,
  `--project`). A scan invoked with a project's own terms used to apply *none* of
  the 59 default rules and print `clean`. The reader fails loud on every parse
  problem: an unreadable declaration must never reach a gate as an empty one.
- **The private vocabulary is tiered.** Measured on the real corpus: the flat
  RP2.0 set produced **102 findings, zero true positives**; the tiered set
  produces **0, with no content exemption at all**. Bare common words (`claude` matching Jean-Claude
  Martin, `terra` matching Italian for "ground") apply where a person writes
  deliberately, not to blob content. The staged gate stays strict, closing the
  hole tiering would otherwise leave.
- **One path semantics** (`tools/pathmatch.py`). `content_exempt` used `fnmatch`
  while the template documented gitignore, so `annotations/` matched nothing and
  said so nowhere. A declaration matching no path is now reported as such.
- **Commit-convention drift is detectable** (`commit_gate --range`): the whole
  range is checked, not only the newest message.
- **Permission, capability and qualification are three claims**, not one. A local
  family validated for mechanical extraction is recorded `contradicted` for
  analytical review. `AUDIT_PRIMARY` and `READER` move to `confirmed`; five Pilot
  Run dispatches join `observations.jsonl` (14 → 19).
- **Fan-out carries a recorded estimate, cost-versus-value and runway check.** A
  standing opt-in once turned a bounded 52-item task into ~156 executions and
  exhausted the runway without finishing it.
- Also: `must_be_tracked` (a global ignore rule nearly dropped a project's
  central artifact silently), the amend trap named where the remedy is chosen,
  the read-only durable-output contradiction resolved, no worktree for read-only
  reviewers, and the bootstrap's stale path and 7-vs-8-column trap corrected.

**Known limitation:** held prose is 2,204 lines against a ~2,000 target — 10%
over, recorded rather than shaved. Next cuts named in `docs/RP2.1-GATE.md`.

**Deferred:** EC-O, EC-T, each with a trigger. **Rejected for Core:** EC-Z.

## 2.0.0 — Wave A + Wave B complete, ready for a real project

Wave A built the pack; Wave B proved it by taking a disposable fixture project
end to end. Both gates are recorded in `docs/WAVE-A-GATE.md` and
`docs/WAVE-B-GATE.md`.

- `tools/` — eight stateless, non-authoritative checkers plus a read-only Git
  layer, 98 standalone tests, importing nothing outside `tools/`. `gitread.py`
  is a 272-line read-only subset of a 1,455-line module and carries no Git write
  verb (`DECISIONS.md` D2).
- Seven findings in Wave A (F1–F7), eight in Wave B (C1–C8), **all reproduced by
  coordinator execution and all closed**. None was caught by an implementing
  worker's own passing suite.
- The rehearsal's two most valuable findings were **test-domain** defects: two
  independently written obviously-wrong implementations each passed a fully green
  suite. Neither was reachable by mutating production code.
- Wave B ran a real cold-continuation drill (passed from 4 file reads), a
  deliberate leak injection (blocked at both gates), a failure-classification
  exercise (environmental, budget correctly not charged), and **two blind
  audits** whose unique-discovery counts are recorded rather than pooled.

Not in this version, deliberately: no database, event store, reducer, lifecycle
engine, release-identity authority, or trust root; no automated Core evolution;
no Pilot Run Project. The pack exists to start real work, not to be the work.

## 2.0.0-wave-a — pack skeleton, Core Skills, policy, templates

Runtime Pack 2.0 is the successor to a deterministic-kernel architecture that
was terminally abandoned after four audit rounds found stateful software
authority failing every round while small stateless checkers survived every
one (see `DECISIONS.md` D1). This wave builds the pack itself: no project has
started yet.

**What this pack is:** a coordinator-governance layer expressed in durable
structured context (files + Git), Skills (procedure), and a small toolbelt of
stateless, non-authoritative checkers. Authority lives in files a coordinator
maintains under this governance and in Git; nothing here holds state and
adjudicates it in the same component.

**What this wave adds:**

- `skills/core/` — the ten Core skills carried from the prior Kernel project's
  seed corpus, reconciled against the architecture audit (kernel-authority
  references replaced with this pack's file-and-toolbelt architecture), plus
  three new skills: `oracle-discipline.md`, `continuation.md`,
  `worker-contract.md`. All model-agnostic, role names only.
- `policy/` — private operational policy: `observations.jsonl` (seeded
  honestly with the 8-configuration worker-ladder outcomes), `routing-table.md`
  (a derived view, regenerated, never hand-edited), `hitl-matrix.md` (the
  17-row blocking taxonomy with a named application point per row),
  `auditor-strategy.md` and `routing-policy.md` (absorbed and reconciled to the
  owner-approved defaults), `private-terms.default.json` (carried).
- `templates/` — pull-on-demand, project-instantiated artifacts: the project
  contract, capability scope/progress/findings, task and audit briefs, HITL
  decisions, product bugs, evidence index, the nine-field human acceptance
  protocol, and the requirement-coverage register with its tiny stdlib-only
  validator.

**What this wave deliberately does not contain:**

- No database, event store, reducer, lifecycle engine, release-identity
  authority, or trust root. State lives in files and Git, not software.
- No toolbelt code — that is a separate, parallel Wave-A stream (`tools/`),
  owned and delivered independently of this one.
- No real project. `PROJECT.yaml` has not been authored for anything yet;
  Wave C is the point at which a project actually starts.
- No vendor or model names in `skills/core/` — those live only in `policy/`.
