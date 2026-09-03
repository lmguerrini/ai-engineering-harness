# Changelog

## 2.3.0 — durable execution, liveness, capacity truth and complete-history safety

A **MINOR** release (`DECISIONS.md` D11 and D24): new backward-compatible
capability, plus enforcement of guarantees earlier versions already promised.
**State `IN_PROGRESS` — no project may adopt this candidate.** Every defect
below was reproduced by execution against the frozen 2.2.0 baseline before it
was repaired, and every repaired guarantee carries an oracle that fails against
the pre-repair behaviour. Gate: `docs/RP2.3-GATE.md`.

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
