# Changelog

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
