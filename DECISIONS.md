# Runtime Pack — pack-level decisions

Append-only. Newest last. Each entry: what was decided, on what evidence, and
what would reverse it.

---

## D1 — HYBRID architecture adopted (audit §1, owner-approved)

Runtime Pack 2.0 is the authority and governance layer. Only small proven
*stateless* Kernel checkers survive, as non-authoritative tools. No Kernel
stateful authority survives. The Kernel stays frozen at `042c1b9` as a private
evidence archive: never pinned, never developed, never deleted.

**Evidence:** stateless checkers survived every audit round; stateful software
authority failed every audit round (audit §1, §2).
**Reverses on:** nothing short of an explicit human decision plus ≥2 independent
real-project incidents that procedure demonstrably could not handle (audit §11.3).

---

## D2 — `gitread.py` subset, not whole `gitops.py` (Wave-A decision, audit §3.4)

The audit left this open, to be decided by actual complexity and verification
cost. Measured at `042c1b9`:

    gitops.py whole                          1,455 lines, 72 defs
    call sites from outgoing.py + hygiene.py    11
    distinct functions actually called          10 + one private helper
    their function bodies                      217 lines
    + module-level env/constants               ~55 lines
    gitread.py subset                         ~272 lines

**Decided: extract the subset.** It is a 5.3× smaller trusted surface, and the
discarded remainder is mostly Git *write* verbs — which a report-only toolbelt
must not carry at all. Keeping the whole module would import write capability
into a layer whose defining property is that it cannot change state.

**Reverses on:** a tool needing a gitops verb outside the extracted subset —
in which case the verb is extracted individually, with its own test, never by
re-importing the whole module.

---

## D3 — Toolbelt is import-closed (audit §3.4 Wave-A gate)

Every tool imports only the Python standard library and other modules inside
`tools/`. `errors.py` is carried into the toolbelt as a trimmed local module so
no tool reaches back into `hx/`. The Kernel's import gate (`sitecustomize`
capability machinery) is stripped: it was falsified verbatim and is exactly the
"trust root inside the tree it anchors" pattern the audit rejects.

---

## D4 — Commit contract relaxed to 2–4 bullets (pivot §9, audit §2)

Exactly-three-bullets cost two rejected commits in the final round and adds no
safety. Structural and vocabulary rules are unchanged. Double-sided validation
(before staging + read-back after committing) is unchanged.

---

## D5 — Pack root location and Git posture

`~/.local/share/engineering-harness/runtime-pack-2/`, local Git, **no remote,
no tag, no push, ever, without a human gate.** The pack tracks itself so pack
evolution is reviewable; it is private material and never enters a project
repository.

---

## D6 — Owner-approved defaults recorded (governing prompt, 2026-08-13)

Recorded here so a fresh coordinator does not re-ask (audit §12 open decisions
1–8, all resolved):

1. Hybrid verdict + kernel disposition: **adopted** (D1).
2. Repo-visible project context: **product-facing docs allowed** in the project
   repo where useful and public-safe; all orchestration context stays private.
3. Repair/audit budgets: **as frozen in `policy/BUDGETS.md`**.
4. Audit depth: routine = one blind fresh-context auditor + seeded cross-vendor
   sampling; critical/material/security/concurrency/migration/public-contract/
   final gate = two blind auditors, one cross-vendor where available.
5. Overhead target: **≤15% of session work**, held prose ≤ ~2,000 lines.
6. Default project Git policy: distinct integration and release refs; autonomous
   integration merges allowed when PROJECT.yaml permits; every push, remote,
   tag, release merge, publication, deployment, submission **human-gated**.
7. Local model (Qwen): **not on the critical path**; one bounded non-blocking
   probe only if it does not delay Wave A/B.
8. HITL question cadence: **batched at capability boundaries**.

---

## D7 — publication safety is a ref-namespace contract, not a history check (RP2.1)

The pack asserted nothing about a repository's ref namespace. A repository can
pass every authorship check of its branch history — one author, no
trailers anywhere — while carrying AI contribution attribution,
private orchestration identities and session identifiers in `refs/notes/*`,
which `git log`, `git status`, `git ls-files`, `git diff` and `git show` cannot
see. Those five were the whole hygiene surface.

**Decided.** Safety derives from an allowed source ref **+** containment **+** an
exact push refspec **+** a remote postcondition verified after, evaluated in the
same step as the push — never from the namespace being clean at an earlier
instant. A notes-ref writer can re-create deleted refs within seconds, survive
history rewriting and rewrite repository-local `.git/config` between sessions;
IDE and provenance services are named as a class of external `.git` mutator.

**Evidence.** EC-R, EC-AF, and a live re-verification during this pass against
a real repository.
**Reverses on:** nothing short of a push form structurally safe against an
arbitrary namespace — which the single-refspec rule already is.

---

## D8 — permission, capability and qualification are three claims (RP2.1)

`read-only` was doing two jobs: describing what a worker *may* do, and being read
as what it *can* do. A local family validated for mechanical extraction against
AST-frozen ground truth was dispatched on analytical code review and produced
zero substantiated findings of seven asserted and then self-retracted.

**Decided.** The routing table grades per task class; `EXTRACT` and `REVIEW` are
separate rows; availability is never qualification. A worker qualified at one
class is `unprobed` at the other.
**Evidence.** EC-W, and the measured run now in `observations.jsonl`.
**Reverses on:** a family demonstrating hypothesis-*discarding* on a real review
task. One observation is one observation in that direction too.

---

## D9 — the private vocabulary is tiered by surface (RP2.1)

**Decided.** Distinctive multi-word terms apply to every surface; bare common
words apply only where a person writes deliberately — commit messages, ref and
tag names, identities, paths — and not to blob content. The **staged** gate is
exempt from the tiering and applies everything.

**Evidence.** On the real corpus the flat set produced 102 findings and zero true
positives; the tiered set produces zero with no content exemption at
all. The staged-gate exception exists because
tiering otherwise reopens a hole — process vocabulary in prose *about*
the work, the bare-word forms being exactly what the tier stops
matching. Strict where a reword is cheap; tiered where the remedy is a rebuild.
**Reverses on:** a true positive in blob content that only a bare common word
would have caught — which would mean the multi-word forms are too narrow, not
that the tiering is wrong.

---

## D10 — the project contract is the single source for every gate (RP2.1)

**Decided.** `commit_gate`, `outgoing_scan`, `workspace_report` and
`publication_gate` accept `--project` and read their own declarations.
`--term` / `--pattern` / `--exempt` remain and are **additive**. The reader
raises on every parse problem and the CLIs exit **2**, distinct from a clean 0.

**Evidence.** EC-H and EC-P: the same scanner over the same range reported
`clean (5 commits, 17 blobs)` and `7 leak(s)` depending on whether the caller
remembered the defaults, and nothing in the first report disclosed that 59 rules
were absent. Every report now states the rule counts it applied.
**Reverses on:** nothing. A verdict that depends on flags a human retyped is a
verdict obtainable twice with different answers.

---

## D11 — release identity is version + revision + digest, and the bump semantics are stated (RP2.1.1)

The pack had a version and no release *identity*. `README.md` still said 2.0
under `VERSION` 2.1.0; `CHANGELOG.md` and `PACK_MANIFEST.json` recorded 167
tests where the suite collected 175 and the gate record said so; nothing
recorded a qualification state a consumer could read; and no file said what a
version increment meant.

**Decided.**

*   `VERSION` is the **single machine-readable version authority**. Every other
    file restates it, and `pack_pin.verify_pin` refuses a manifest that
    disagrees — a restatement nothing compares is a second authority.
*   A release is identified by **version + full 40-character revision + manifest
    tree digest**, and `PACK_MANIFEST.json` carries an explicit `state`. The
    version alone is a label: two checkouts can carry it and differ.
*   **PATCH** — backward-compatible fixes, metadata and documentation
    corrections, and enforcement of guarantees already promised. **MINOR** — a
    new backward-compatible policy, tool or capability. **MAJOR** — an
    incompatible authority, contract or migration change.
*   The digest framing is **release-local**, named in the manifest's
    `digest_algorithm`, and a release is verified with the `pack_pin.py` that
    ships inside it. Improving the framing is therefore a PATCH, not a break.

**Evidence.** Every drift above was reproduced by execution before repair, and
`tools/tests/test_release_integrity.py` now fails on each of them against the
real repository rather than against a fixture.
**Reverses on:** nothing. A release whose identity is a label is not pinnable.

---

## D12 — installed skills are adapters, never authority (RP2.1.1)

`PILOT_RUN_PROJECT_BOOTSTRAP.md` said of an installed skill "nothing here
overrides it", and `PACK_MANIFEST.json` recorded two of them as *amended in
place*. Both files live in `~/.claude/skills/`, outside the release envelope and
covered by no digest, so a pinned, verified pack deferred to material that could
change under a running project with nothing noticing.

**Decided.** The pinned repository is the release authority. Installed skills
are **adapters and integration surfaces**; where one disagrees with the pinned
pack, the pinned pack wins. A project that needs an external skill to be
normative pins and verifies it under its own dependency contract, exactly as it
pins the pack. They are still *counted* against held prose, because they are
still loaded every session — the pack can measure what it cannot freeze, and
`BUDGETS.md` now states both figures rather than re-scoping the rule.
**Reverses on:** an external skill being vendored into the release, which would
make it pack material and subject to the digest.

---

## D13 — several projects may pin one frozen release, concurrently (RP2.1.1)

`PROJECT.yaml.template` recorded the pack version only — no revision, no digest
— so two projects claiming "2.1.0" could be reading different trees, and
`BUDGETS.md` directed per-project overhead measurements into a shared pack file
that did not exist.

**Decided.** A project records and **verifies** version + revision + digest +
state. A frozen release never mutates during a project run; verification failing
mid-project is a stop, not a pin to refresh. Several projects may pin the same
release concurrently, or different qualified releases, provided each version
resolves to a distinct immutable root. Operational state and Evolution Candidate
inboxes are project-local and never written into the pack. Candidates from
several projects are pooled only in a separate pack-evolution session, which
cuts a new version; each project adopts it independently at its own next safe
capability boundary. No scheduler, no shared mutable runtime.
**Reverses on:** nothing short of a project genuinely needing to write into a
pinned pack, which would mean the release is not frozen.
**Amended by D18 (RP2.2):** "distinct immutable root" was stated here as a
property of the pin and enforced by nothing. The root a project pins must be a
checkout nobody works in — a lesson learned by breaking a live project's pin
with a branch checkout in the directory it pinned.

---

## D14 — the founder architecture decision is the current authority layer (RP2.2)

Recorded at the opening of the RP2.2 evolution session, before implementation,
so that the decisions the rest of this release rests on are readable without
reconstructing a conversation. It is **additive**: D1–D13 are unchanged, and no
prior gate or decision record was rewritten.

1.  **2.1.1 is the qualified semantic and non-regression floor.** No capability
    it holds may be lost except by replacement with a demonstrated semantic
    superset.
2.  **D1 remains normative**, in its sharpest form: no component may both hold
    authoritative state and adjudicate it.
3.  The **coordinator is the semantic decision-maker**. That authority is not
    delegable to a worker, a harness, or a vendor feature.
4.  **Execution harnesses are subordinate.** A first-party CLI is an execution
    backend. Harness functionality never silently becomes project, release,
    HITL, routing, certification or integration authority.
5.  The **workflow shape is an architectural invariant** — decomposition and
    routing, workers, deterministic fail-closed gates, independent semantic
    audit where required, coordinator synthesis, human authority where genuinely
    mandatory, then integration — replaceable only by a demonstrated semantic
    superset.
6.  **Vendor enforcement is defence in depth.** Hooks, sandboxes, permission
    modes and orchestration features are additive; they never replace a
    qualified fail-closed gate, and a gate may not be relaxed because a vendor
    feature is believed to cover it.
7.  **Project runtime state stays project-local** — evidence, routing
    observations, Evolution Candidates and Project Context included. The pack's
    own `policy/observations.jsonl` is **pack** evidence, not project state: it
    is written only during a pack-evolution session, and a project that appends
    to it would mutate the release it is pinned to, change its digest, and break
    every pin to it mid-run. Two shipped drill documents said to write there and
    were corrected in RP2.2; an audit found them.
8.  **Releases remain immutable per active project capability.** A new release
    is never silently adopted by a running project.
9.  **Project Context is a first-class contract capability** at the declaration
    and verification level; its semantic content and evolution stay
    project-local.
10. **External executable adapters are pinned and verified, not vendored**,
    unless pinning is proved insufficient for the guarantee being claimed.
11. **No stateful global coordinator** — no daemon, scheduler, event database,
    single-runtime-authority store, generic provider runtime, or third-party
    harness.
12. **First-party subscription paths are the preferred cloud execution
    surfaces.** Provider API-key billing is not an allowed architectural
    dependency.

**Evidence.** The 2.1.1 baseline was verified on every axis it declares before
this entry was written. Clauses 2, 4 and 6 are the ones the session immediately
tested: an installed reviewer adapter was found asserting an isolation mode the
pinned reviewer contract forbids, which is clause 4's failure mode occurring in
the live installation rather than in theory.

**Reverses on:** an explicit human decision. Primary evidence appearing to
require the reversal of clause 2 is a stop condition, not an implementation
choice.

---

## D15 — an unanswerable question is never rendered as its reassuring answer (RP2.2)

`pack_pin` already stated the rule for verifiers: a check that passes for a
reason weaker than its message is worse than no check, because it is believed.
The same rule was found unenforced one layer below the checkers.

`gitread.probe` distinguishes three outcomes — Git answered, Git ran and could
not answer, nobody looked — and exposes `failed` for the middle one. Three
callers consulted only `answered`, so an undeclared exit status arrived as an
ordinary negative: an unreadable `.git/config` reported as a repository with no
settings and therefore no `notes.*` keys, which is the exact surface D7 exists
to watch; an ancestry question about a non-commit reported "not contained", and
the publication report printed that guess as a fact.

**Decided.** A probe result is consumed through `require`, or through an
explicit `failed` branch that produces an `UNKNOWN`. Rendering an unanswered
question as either verdict is a defect regardless of which verdict is safer,
because the safe verdict is still a claim nobody established.

**Evidence.** All three call sites reproduced by execution before repair.
**Reverses on:** nothing. This is D1's rule about adjudication applied to the
narrower case of a component adjudicating a question it could not ask.

---

## D16 — a content exemption scopes the project's vocabulary, never a universal rule (RP2.2)

`outgoing_scan` already separated the two classes and said why:
`UNIVERSAL_LEAK_KINDS` — credential, local path, generated identifier — are
"private whoever wrote it, so no project gets to declare them acceptable".
`skills/core/public-safety.md` went further and named the exact failure:
"writing the exemption as *skip blob content* takes both out at once."

It was written that way. A declared `content_exempt` path caused the blob to be
skipped entirely, so a project exempting `fixtures/` to stop its own denylist
matching itself also switched off credential and machine-path detection for
everything underneath. Reproduced: an AWS-shaped key and a home-directory path,
both inside an exempted file, reported `clean`.

**Decided.** An exemption removes the project's own vocabulary from a blob's
findings and leaves every universal rule in force. It is implemented as a
**scope over the findings**, not as a skip over the object, because skipping is
indistinguishable from exempting everything and the difference is a credential.
The report states the narrowing rather than printing `content-exempt` and
letting a reader supply "and therefore unscanned".

**Evidence.** Reproduced against the frozen 2.1.1 baseline before repair, and
the tests fail against that behaviour. The motivating case is unchanged: a file
that *is* the denylist still exempts cleanly.
**Reverses on:** nothing. This is D9's tiering rule applied to the one surface
where the project, rather than the pack, was choosing what not to look at.

---

## D17 — the release states its push form once (RP2.2)

`publication_gate.SUPPORTED_PUSH_FORM` is the authority for the publication
command, and the runbook and the project contract restate it for a person to
run. Nothing compared them, which is the same defect D11 named for release
identity: a restatement nothing checks is a second authority.

**Decided.** Planning, gating and execution read one canonical string. A
release-integrity test compares every restatement on an *instructional* surface
— templates, procedure skills, policy, README — against the constant, and a
second test asserts the constant is what the checker actually accepts, so the
agreement is about behaviour and not only about text. Test fixtures, changelog
entries and gate records are deliberately outside the comparison: their job is
to carry the wrong forms, and history is left as written.
**Reverses on:** nothing.

---

## D18 — a release root is a checkout nobody works in (RP2.2)

D13 required different qualified releases to resolve to distinct immutable
roots. It did not say where a release root comes from, and the pack's own
installation answered that question badly: one directory was simultaneously the
release a project pinned and the working tree in which the next release was
developed.

**Reproduced during this session, on a real project.** A correctly formed pin —
version, revision, digest, state and `root_path`, all present — stopped
verifying the moment the evolution branch was checked out in the root it named.
The verifier reported it precisely, which is the system working; the situation
it reported is a layout defect, not a pin defect.

**Decided.**

*   A **release root is a checkout nobody works in.** Evolution happens
    elsewhere. A version becomes a release by being placed at its own root and
    recorded in the release index.
*   `pack.root_path` is **required, canonicalised and verified**. Version +
    revision + digest say *what* a release is; the root says *which directory*
    holds it, and without it nothing can confirm the two are the same thing.
*   The **release index lives outside every release**, because a frozen release
    cannot name its successors. It is untrusted input: an entry is a claim, and
    the migration gate is the verification.
*   A pin that cannot be checked is **`UNVERIFIABLE_LEGACY_PIN`** — reported at
    every use, never repaired by writing today's values into it, and remedied by
    migrating rather than by editing.

**Evidence.** Two real projects carry version-only pins today, and a third
carries a complete pin whose root was being written to. None was migrated or
modified while this release was built: they are evidence, not authorisation.
**Reverses on:** nothing. A release that shares a directory with the work that
supersedes it is not frozen, whatever its manifest says.

---

## D19 — Project Context is a contract capability; its meaning stays project-local (RP2.2)

A real project already runs a Project Context — a durable record of what the
product means, what it has decided, and what is still open — and proves
non-mutation across a capability by showing the same digest before and after.
The pack knew nothing about it, so a capability could run against a semantic
authority that was absent, stale, or being edited underneath it, and no gate
could tell.

**Decided.** Project Context becomes a first-class contract capability **at the
declaration and verification level only**:

*   declared in `PROJECT.yaml`, so a capability cannot consult a context nobody
    declared;
*   located by a **canonical, resolved** reference path;
*   carrying a **project-local revision** and a **digest**, so non-mutation is a
    fact rather than an assurance;
*   in one of five distinct states — `NOT_PRESENT`, `DECLARED`,
    `CURRENTLY_VERIFIED`, `STALE`, `UNVERIFIABLE`. "Nobody declared one" and
    "one was declared and cannot be found" are different facts and the second is
    a stop;
*   with the digest taken at capability open and recomputed at close. A context
    that changed in between makes that capability's evidence **uninterpretable**
    rather than stale, because the evidence was produced against a semantic
    authority that no longer exists;
*   with **proposal separated from adoption**, so a suggestion cannot become
    authority by being written down.

**The Core does not adjudicate product meaning.** The verifier reads no content
and has exactly one opinion: whether the bytes are the ones declared. A
semantically enormous change and a one-space change are reported identically,
and that is deliberate — a governance layer that started grading product meaning
would hold state it also judged (D1).

None of the motivating project's implementation is vendored. Only the contract
and verifier semantics are generalised, and the generalisation was checked
against the real thing: this module's tree walk counts the files in that
context and matches the count the project itself records.

**Reverses on:** nothing short of Core needing to read context contents to make
a governance decision — which would be the reversal of D1, not of this.

---

## D20 — readiness is composed, never a second source of truth (RP2.2)

Every prerequisite a governed capability needs was checkable before this
release, by running four tools by hand against a prose checklist. That is not a
readiness path. It has no aggregate answer, nothing compares its parts, and **a
step nobody ran is indistinguishable afterwards from a step that passed** — the
same shape as the defect that let a real consumer's contract go unread through
four audit rounds.

So there is one deterministic readiness path, `tools/capability_open.py`, and it
**introduces no new source of truth**. Each component result is delegated to the
tool that owns that question: the contract parser reads the contract, `pack_pin`
and `pack_migration` answer about the pin, `adapter_pin` about adapters,
`project_context` about the context, `migration_gate` about adoption. What is
added is composition, one truthful aggregate state, and the rule saying which
components a given project must satisfy.

It is stateless, read-only and deterministic, it infers nothing only the caller
can know — the capability boundary is an input and `UNKNOWN` when unstated — and
it **authorises nothing**: integration, release and human decisions stay where
they are. A readiness checker that could approve its own findings would be a
component holding state it also adjudicates (D1).

Two questions that had been one are now separate, because only the first had an
answer: *is this root what you pinned* (`verify_pin`, which a project pinned to
an `IN_PROGRESS` release satisfies completely) and *is what you pinned
adoptable*.

**Reverses on:** a prerequisite that genuinely cannot be answered by delegation,
which would mean some checker is missing rather than that this one should grow
an opinion.

---

## D21 — a newer release is information; only a broken prerequisite is a gate (RP2.2)

A project pinned to an older **qualified** immutable release is correctly
pinned. It stays that way until it adopts at a capability boundary, through the
migration gate, and choosing not to adopt is a supported outcome rather than a
deficiency.

So availability of a newer release produces `READY_WITH_UPDATE_AVAILABLE` — a
**ready** state — and never a block. There is no `BLOCKED_BECAUSE_NOT_LATEST`,
and an unreadable release index leaves availability `UNKNOWN` without affecting
readiness, because a project runs against its own pin and not against an index.

The alternative regresses the whole multi-project model (D13, D18) into one
where cutting any release makes every project unready at once, and where the
pressure to adopt comes from a checker rather than from a decision.

Hard refusal is reserved for what is actually broken: a missing or malformed
required declaration, a pin that cannot be verified where verification is
required, root drift, a required adapter that does not match, a required Project
Context that is missing or cannot be established, an unauthorised mid-capability
release change, and a migration target that is not itself qualified and
verifiable.

**Reverses on:** a release carrying a security advisory severe enough that
remaining is unsafe — which is a **human** decision the migration gate already
records and refuses to make on its own, not a rule this checker should acquire.

---

## D22 — a requirement governs absence; a declared thing that cannot be established always stops (RP2.2)

`adapter_pin` established this rule and `capability_open` reuses it rather than
inventing a second semantics: `required: true` decides what happens when a thing
is **absent**, and nothing else.

A Project Context that is declared and cannot be verified stops a capability
opening whether or not the project declared it required — something in that
project consults it, and "nobody wrote `required: true`" does not make an
unestablished semantic authority safe to proceed on. The same is true of a
declared adapter whose digest does not match.

What the requirement does decide is the one case it should: a fixture or a
utility may declare no context and be clean; a product whose correctness depends
on durable semantic authority declares `requires.project_context: true`, and
then absence is a stop.

**The project declares this, not Core.** Core cannot know which products have
durable semantic authority, and a Core carrying a list of project names would be
making that judgement in the wrong place — unchangeable without a release, and
adjudicating product meaning, which D1 forbids. A requirement key nothing checks
is refused rather than ignored: a requirement silently unread is worse than
none, because the project believes it is enforced.

**Reverses on:** nothing. The alternative was tried by omission — absence read as
clean for every project, including products whose correctness depended on it.

---

## D23 — the founder architecture decision for RP2.3 (RP2.3)

Recorded at the opening of the RP2.3 evolution session, before implementation,
against a baseline verified on every axis it declares — by the shipped
`pack_pin.py` and again by an independent re-implementation of the digest
framing. **Additive**: D1–D22 are unchanged and no prior gate or decision record
was rewritten.

The release exists to prevent a set of failure classes measured on a real
project after 2.2.0 froze. It is not a rebuild of the stateful architecture D1
rejected, and every clause below exists to keep it from becoming one.

1.  **2.2.0 is the qualified semantic and non-regression floor.** No capability
    it holds may be lost except by replacement with a demonstrated semantic
    superset.
2.  **D1 and D14 remain normative.** No component may both hold authoritative
    state and adjudicate it, and the coordinator remains the semantic
    decision-maker.
3.  **Publication obligations are profile-scoped.** Core may carry universal
    public-safety invariants where they are justified; reproducibility and
    public-presentation requirements are opt-in. A project that is internal is
    not walked through publication ceremony because Core can perform it.
4.  **No autonomous restart of a coordinator in this release.** Durable
    continuation state, completion detection, a wake-needed signal, recovery
    packets and liveness projections are all in scope. Creating or waking a
    coordinator session is not. A mechanism may report that a coordinator is
    needed; it may not become one, and it may not cross a human-authority
    boundary. Deferred as an Evolution Candidate whose trigger is a qualified
    first-party session primitive plus an explicit governance rule authorising
    its use — neither exists today.
5.  **Coordinator headroom is mandatory as a concept and carries no universal
    number.** The model represents rolling windows, longer windows where
    observable, reset horizons, shared versus independent pool identity, active
    workers, estimated remaining cost, result-consumption cost and a repair and
    audit reserve. Where capacity cannot be known safely, `UNKNOWN` is
    first-class and dispatch becomes conservative rather than precise.
    **Continuation safety outranks quota utilisation and parallelism.** No
    percentage is invented, and no provider is graded by name.
6.  **Core is never given generic authority to rewrite history.** It may detect
    candidates, classify them, prepare a remediation package, compute a plan,
    verify preconditions, verify chronology, tree, date and identity
    invariants, require rollback evidence, emit an old-to-new revision mapping
    and verify postconditions. Executing a rewrite stays a human decision
    (`policy/hitl-matrix.md` rows 2 and 4). A public-safety check is never
    weakened to avoid remediation.
7.  **A diagnostic projection is in scope, and it is a projection.** It stores
    no governance truth, authorises nothing, adjudicates nothing, performs no
    transition, is reconstructible from durable state alone, and reports stale
    or unknown data as such. **A disagreement between the projection and the
    record is a defect in the projection, always.** So is a disagreement
    between the durable state machine and the record: the machine is
    machine-written and machine-transitioned, and that makes it downstream of
    the record rather than a second copy of it.
8.  **Two corollaries keep clause 7 from being decorative.** No governed action
    may be taken whose only premise is a state value, and every transition must
    be reconstructible from a durable artifact — a job's exit, its log, its
    checkpoint. A machine-produced premise sitting under a human ruling is the
    error class nothing downstream questions.

**Evidence.** A reconciliation package from a real project, verified here
rather than accepted, by re-executing the integrity checks it carries. That
package is design and evidence input.
It is not authority, and nothing here is adopted because a document assumed it.

**Reverses on:** an explicit human decision. Primary evidence appearing to
require the reversal of clause 1 is a stop condition, not an implementation
choice.

---

## D24 — a close obligation a project cannot fail to satisfy is mandatory; one that needs new project capability is declared (RP2.3)

The release adds two obligations at capability closure: a **generated close
attestation** that enumerates the declared validation profiles and reports which
actually ran, and a **re-derivation of the measurement a human decision rests
on**. Both close real, measured holes — two capabilities closed green over red
gates, and one human ruling was taken on a figure that was wrong by more than a
year. Both also change what closing requires, which under D11 is the difference
between a MINOR and a MAJOR release.

The question is not how large the change is. It is whether a project that adopts
the release can be left unable to close.

**Decided.**

*   **Generating the attestation is mandatory, because no adopting project can
    fail to do it.** It is derived from the `validation_profiles` the contract
    already declares, so the generator always has its input, and a profile that
    was never run is enumerated and reported `UNRUN` rather than omitted.
    Omission is what has to be impossible: a step nobody ran is otherwise
    indistinguishable afterwards from a step that passed.
*   **Refusing to close on an `UNRUN` profile is the project's declared policy,
    and it defaults to refusing.** A project that needs to close over a profile
    it cannot run says so, in its contract, once, where a reader can see it —
    rather than by the attestation quietly not mentioning it.
*   **Re-derivation of a decision premise is declared**, and required for a
    human decision record wherever it is declared. A project that declares none
    is clean; a project that declares it and cannot re-derive is a stop.
*   The release is therefore **backward-compatible and MINOR**. Nothing an
    adopting project cannot satisfy is imposed on it, and the guarantee that
    matters — *which gates ran is no longer answered by the party that ran
    them* — is unconditional.

This is D22's rule applied one layer up: a requirement governs absence, the
project declares it, and Core does not decide which products carry which
obligations. **The human decision this records is the mandatory-versus-declared
fork, taken at the session freeze; the version number follows from it rather
than the other way round.**

**Reverses on:** an adopting project demonstrating that it can produce an
attestation that omits a declared profile — which would mean the generator, not
this rule, is wrong.

## D25 — a material change begins with a falsified design, not with a repair loop (RP2.3)

**Question the founder put:** does this release actually *ship and enforce*
pre-implementation design falsification for future projects, or was that only
how this session happened to be run?

**Answered mechanically against the candidate, and the answer was no.**
`SCOPE_FROZEN` was a lifecycle point named in two rows of
`policy/hitl-matrix.md` and enforced by nothing. `skills/core/oracle-discipline.md`
described freezing an oracle's domain at scope freeze. `skills/core/repair.md`
required an invariant, a discriminating oracle and a mutation check before a
fix — but only once a defect already existed, which is the second half of the
loop and not the first. No template asked for a design, no artifact recorded
one, no tool read one, no test detected its absence, and cold reconstruction
preserved no design rationale. **DOCUMENTED_ONLY.**

**Decided: composed into the readiness path, not built as a new authority.**

*   **The transition is the capability open.** `capability_open.open_capability`
    is already the one deterministic path run before a governed capability
    opens; it already composes delegated components, already distinguishes
    *required* from *blocking*, and already fails closed on `UNKNOWN`. The
    design becomes one more component of it. Four alternatives were considered
    and rejected in writing before any of it was implemented — an intercepting
    gate process, a template-and-skill with no detector, a check in the commit
    gate, and a new blocking lifecycle state — and the record of that is
    `rp2.3-session/DESIGN-C31-design-gate.md`, which is itself the first thing
    the mechanism was run against.
*   **It reports and authorises nothing.** It reads a file and answers whether
    that file states what it claims to state. It never judges whether the
    selected design is good — that is product meaning, and Core does not
    adjudicate product meaning. It adds no HITL row, removes none, and weakens
    none.
*   **Risk-scaled, and the class is an input.** `TRIVIAL` requires no record at
    all. `ROUTINE` requires the mechanism and acceptance plus negative oracles.
    `MATERIAL` requires at least two candidate designs, at least one rejected
    with a reason, exactly one selected, its failure modes, its authority
    boundaries, and a mutation oracle. Core cannot know which of a project's
    changes are material — that is a property of the project, exactly as
    `requires.project_context` already is, and a project may declare
    `requires.design: true` to make it unconditional.
*   **Freezing is bound to a revision.** The base revision must resolve and be
    an ancestor of `HEAD`, and a strict ancestor of the revision where mutation
    began when the caller can name it. A design frozen against a tree that
    already contains the work it governs is refused, because backdating is the
    obvious cheat and the only one worth building for.
*   **This bounds the repair loop rather than adding an audit loop.** It adds
    no round, no auditor and no budget counter. It moves the falsification
    earlier, where the cheapest thing to change is still a paragraph.

**The bound, stated rather than dressed up:** a caller who declares a material
change `TRIVIAL` gets no record and no block. The declaration is recorded in
the readiness report, so it is a visible claim somebody can dispute rather than
a silent omission — but it is not prevention, and this decision does not claim
it is.

**Reverses on:** an adopting project showing that the record is being written
after the fact and passing, which would mean the revision binding is
insufficient rather than that the rule is wrong.
