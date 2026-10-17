# Changelog

## 2.6.0 — a provider is a declared record, billing is a proof, and capacity says how fresh it is

**State `IN_PROGRESS`** — a candidate; no project may pin it. Grade to be derived at the freeze from
`tools/surface_diff.py` over `aa55575b..HEAD` and the answer contract (D11, D28); expected **MINOR**: new
tools ship and every existing signature stays callable. **2.5.0 is untouched** at `aa55575b`, digest
`bd5118c7`, and every project pinned to it stays pinned to exactly what it verified.

### Why this release exists

Read at the boundary: the cross-vendor audit leg was qualified on one configuration drawing on one
shared account-level pool while another pool stood partly unspent; every failover was a human decision;
cross-pool routing was being re-implemented outside the pack; projects extended the pack's capacity record
with the freshness and provenance they needed and the frozen reader refused the record, so the shared console
showed capacity and coordinator positions UNKNOWN; the only official capacity observer never produced a
machine reading in the desktop workflow. The founder's decisions are D29–D36.

### What this release adds (kept current as the line grows; `tools/release_delta.py` checks it)

- `docs/RP2.6.0-DESIGN-P1-provider-registry-and-billing-safety.md` — the authoritative design, frozen before
  implementation, with its oracles; `docs/RP2.6.0-DESIGN-P0-third-provider-slot.md` — the design it
  falsified and supersedes, kept as history.
- `docs/RP2.6.0-GATE.md` — the gate record, opened with the session counters D35 authorises.
- `DECISIONS.md` D29–D36 — billing mode not protocol (D29); independence by vendor on the derivation (D30);
  a provider is a declared manifest, no slots, no count (D31); billing safety as Core invariants (D32);
  capacity observability as a must-fix with first-class freshness (D33); one live new provider and a dormant
  fixture (D34); session counters (D35); quarantining readers whose count blocks (D36).
- `tools/provider_manifest.py` — a provider as one declared manifest (`runtime-pack-provider-1`), the
  billing route fingerprint, `routability`, and its CLI.
- `tools/tests/test_provider_manifest.py` — the suite behind it.
- `templates/providers/moonshot-kimi-code.dormant.json` — the D34 dormant fixture that proves the seam
  registers unchanged and routes nothing.
- `templates/providers/README.md` — what a dormant template promises and does not.
- `tools/tests/test_readonly_modes.py` — the read-only-mode oracle (O10): every touched tool's `--help`, one
  unrecognised flag and its default read path run against a fixture governance tree and must leave it
  byte-identical, with no traceback; two negative controls (a helper that rewrites, a helper that creates)
  prove the check discriminates. It changes no tool.
- `tools/routing.py` — `Derivation` gains `vendor` and `gateway` (D30): a cross-provider leg is now
  refused on distinct VENDOR, never on gateway, with `provider` read only as `vendor`'s alias; the
  `NOT_ROUTABLE_*` dispositions join `DISPOSITIONS` from `provider_manifest`'s own vocabulary;
  `disposition_with_routability` and `eligibility(..., routability=)` let billing safety refuse a
  candidate before availability or grade is read; and the new `eligibility_report`
  (`routing.py --eligibility`) joins per-configuration qualification, a declared manifest's route and a
  capacity pool's freshness into one report, in identity order, that lists and explains and neither
  dispatches nor ranks nor picks (S0-C5, O3, O4, O12).
- `tools/tests/test_routing.py` — the `-k vendor`, `-k not_routable` and `-k mutation` oracles behind it.
- `tools/tests/test_adoption_rehearsal.py` — O13's rehearsal of a third family that registers, is
  reported UNAUTHORISED and then authorised, with no vendor name reaching `tools/routing.py` or
  `tools/provider_manifest.py`.
- `tools/resource_observation.py` — reads the generic provider-quota document `runtime-pack-quota-1` an
  adapter's observer emits and a timestamped human reading, beside the status line it already read; every
  reading now answers `freshness(now)` ∈ {FRESH, STALE, UNKNOWN, UNAVAILABLE} at READ time against its source's
  own horizon — a percentage only with an established denominator, natives preserved, a window the source does
  not expose UNAVAILABLE, never absent and never zero; `from_record` rebuilds a reading from its own record and
  refuses anything else (S0-C3, D33, O6, O7).
- `tools/capacity.py` — `Pool` carries its normalised `observation` and its `billing_mode`; `Pool.freshness(now)`;
  `pool_from_observation`; `gate` counts a STALE observation as exactly one unknown, so a stale pool never
  reaches DISPATCH (D33).
- `tools/capacity_record.py` — the ONE writer of `CAPACITY.json`: validate-on-write, atomic, one pool per
  invocation, `--keep-existing` that refuses rather than drop a pool it could not read, and `check` with
  per-element quarantine (D36) and per-pool freshness (S0-C4).
- `tools/projection.py` — the capacity panel renders every window of an observation-bearing pool with its
  freshness and age, and a 2.5.0-shaped record exactly as before.
- `templates/CAPACITY.json.template` — a valid record that reads STALE by construction.
- `tools/tests/test_capacity_record.py` — the writer's round trip, quarantine, refusal and no-write oracles.

### What a consumer will notice

Every existing public name and signature still answers as it did (`tools/surface_diff.py` over the baseline
reports additions only); what changes is what a caller is TOLD, recorded here as each addition lands:

- `tools/routing.py`: an observation's `derivation` may now carry `vendor` and `gateway`; a leg declared
  cross-provider is refused when both sides share a **vendor**, whatever gateway served them (`provider` is
  read as the alias of `vendor`), and the refusal names the vendor. **One existing answer changes:**
  `independence_problems(..., require_distinct_provider=True)` now canonicalises both `provider` values
  (NFKC, case, whitespace, separators) and requires a vendor slug, so a pair that differed only in spelling
  (`Vendor-A` / `vendor-a`, `vendor_a` / `vendor_b`) or carried prose (`Acme Corp`) satisfied the leg in 2.5.0
  and refuses now — fail-closed, by D30. `eligibility(...)` accepts an optional `routability`: `None` asks
  nothing, exactly `ROUTABLE` passes, anything else refuses every purpose. `routing.py --eligibility` is a new
  report mode whose JSON rows carry `availability_supposed` and whose report carries `quarantined`; a
  non-slug `--subject-vendor` is refused with exit 2; `--now` pins the ageing moment. The existing report
  mode is byte-for-byte unchanged.
- `tools/provider_manifest.py` is new: a project that declares no manifest sees nothing change.
- `tools/resource_observation.py`: `--provider-quota PATH` and `--human-reading …` are new modes; the status-line
  path is unchanged; `as_record()` carries new keys (provider, pool, provenance, horizon, per-window natives,
  availability) that `from_record` reads back. `tools/capacity.py`: a `Pool` declared as before still reads and
  gates as before; one carrying an `observation` is aged by its source's horizon. `CAPACITY.json` written by
  `capacity_record.py` declares `schema: runtime-pack-capacity-1`; a record without it is read as a 2.5.0 record
  and says so.
- `tools/tests/test_readonly_modes.py` is new: every touched tool's `--help`, an unrecognised flag and its
  default read path are executed against a fixture governance directory and must leave it byte-identical;
  two negative controls prove the check discriminates. It changes no tool.

### Public edition — development history, not a release (2026-10-11)

This tree is the **public edition** of the 2.6.0 line at the checkpoint where it was paused. It is `IN_PROGRESS`:
not qualified, not frozen and not to be pinned. Its history was rewritten for publication, so its commit ids and its
tree digest differ from the private line's, and the manifest records this tree's own digest. It adds documentation
and changes no tool:

- `.github/README.md` — the public landing page;
- `.github/assets/architecture.svg` — the landing page's diagram of the six roles (added 2026-10-17);
- `.github/assets/repository-layout.svg` — the landing page's drawing of the repository layout (added 2026-10-17);
- `.github/RELEASE_NOTES.md` — a summary of every release from 2.0.0 to 2.5.0 and of this line's state;
- `.github/PUBLIC_EDITION.md` — how the history was prepared, what was preserved and what was sanitized.

The release self-checks and each design record's base revision point at this history's commits; prose references
keep the ids they were written with, which belong to the private repository.

## 2.5.0 — the boundary stops describing Git and starts constructing the repository

A **MINOR** release (`DECISIONS.md` D11 and D28): a new tool ships, and the
authority mechanism behind every governed read is replaced. Derived rather than
assumed — `tools/surface_diff.py` over `9d906ce..HEAD` is the check for the API
surface, and `docs/acceptance/rp2.5.0-floor-differential.py` is the check for the
answers, because a release can be signature-compatible and answer-incompatible
and this one is.

**The grade rests on a stated ground, not on the absence of a signature change.**
This release changes what callers are TOLD in the ways listed under *What a
consumer will notice*. D11 grades an incompatible contract change MAJOR, so the
reason 2.5.0 stands is that **at the moment the contract changed, nothing had
adopted it**: the `state` was `IN_PROGRESS` throughout the change, no project
pinned it, and 2.4.0 was and remains the release projects pin — a contract
nothing has adopted cannot be broken by changing it. D28 records that argument
and the founder authority for it, so a reader does not have to reconstruct
either. **The 2026-09-10 freeze does not weaken that ground and is not
retroactive.** It makes 2.5.0 adoptable from that date forward; it adopts
nothing, it moves no existing pin, and 2.4.0 stays byte-identical, so anything
pinned to 2.4.0 is still pinned to exactly what it verified.
**State `QUALIFIED_AND_FROZEN`** — frozen by the founder on 2026-09-10 at
`policy/hitl-matrix.md` row 2, against a named candidate whose version,
revision, tree, digest, pre-freeze state and test population were all stated in
the authorisation and verified to match before the first freeze mutation. **A
project may pin it**, at the revision and digest it verifies, at its next
capability boundary. Both mandatory independent certifications of that exact
candidate ended READY with no Class A blocker upheld — one cross-vendor, one
same-family — and the raw verdicts stand unrewritten beside their separate
adjudications. **2.4.0 is untouched**: same revision, same digest, same state,
and anything pinned to it remains pinned to exactly what it verified. **Nothing
is published**: no push, tag, remote, deployment or consumer migration is
authorised, and none has happened.

### Why 2.4.1 was never released

2.4.1 set out to close six defects an independent audit reproduced in frozen
2.4.0. It closed those, and then eleven cycles closed defects the readings of
those repairs reproduced *inside the repairs themselves*. Seven consecutive
cycles each found a defect in the immediately preceding repair of the same
boundary. Its final independent certification reproduced two more — an
under-refusal (`git status -vv` and `--verb` executed a repository's text
conversion helper) and an over-refusal (an ignored, never-a-submodule checkout
made the whole project unreadable, breaking this pack's own `workspace_report`)
— **in one repair, in one cycle**.

That is not a run of bad luck. `docs/RP2.5.0-RECURRENCE-MAP.md` puts all fifteen
in one table, and every row is the same move: the boundary answered a question
about Git's behaviour by consulting its own description of Git's behaviour — a
list of keys, then of verbs, then of flags, then of transports, then of option
spellings, then of nested paths. Those lists are open sets, and a denylist that
misses an entry runs somebody's program. Narrowing one to stop over-refusing
widens the hole; that is why the last cycle produced both failures at once.

2.4.1 is preserved on `evolution/rp2.4.1` as evolution evidence. Nothing pins
it, and nothing here pretends it shipped.

### What replaces it

`docs/RP2.5.0-DESIGN-A1-sterile-execution.md` was the first frozen design,
committed before a line of implementation existed — see *Six designs, six
falsifications* below for what became of it and of the five that followed. It replaces the question. Instead of
asking which of a repository's settings are dangerous, the boundary makes every
configuration source Git consults a file this harness wrote:

> Every configuration source Git consults during a governed read is a file this
> harness created.

ONE READ IS THE DELIBERATE EXCEPTION, AND IT IS THE POINT OF THAT READ. A
`config` read's SUBJECT MATTER is the repository's own configuration: the
boundary directs Git at the subject's `config` on purpose, `--show-origin`
reports that file as the origin, and `config_with_origin` exists to say which
file each setting came from. What the sentence above governs is the
configuration that can change HOW GIT BEHAVES while answering, and no part of
the subject's configuration reaches that. Two independent certifications read
the sentence as universal and falsified it on this route, so the scope is
written here rather than left to be re-derived from `tools/gitread.py`.

`GIT_DIR` decides which files are local and worktree configuration, and it is
chosen by the caller, not by the subject. So the harness builds the git
directory: its own config from a blank slate, the subject's objects attached by
`objects/info/alternates`, refs and `HEAD` copied as plain files, the index
copied so a refresh never touches the subject. Where the working tree contains
another repository — which Git opens from the working tree, in or out of the
index — the read runs against a mirror in which each nested `.git` is sterile
too.

Two properties make it converge where the enumeration did not. The source set is
**closed and observable**: Git reports every origin, so the invariant is checked
by asking Git rather than by predicting it, and no key, verb, flag, transport or
spelling appears in the check. And it is **fail-closed**: the directory is built
by adding what a read needs, never by removing what it must not have, so
anything missed makes a read fail loudly instead of running a program.

### What a consumer will notice

- A repository that merely *declares* a textconv driver, hook or
  transport is now **read**, not refused. Refusal was a proxy for "this might
  execute something", and prevention makes the proxy unnecessary. Refusals are
  strictly rarer for these declarations. A repository carrying an **executable
  hook on disk** is read too: the subject's own programs are not carried into the constructed git
  directory, and the constructed configuration points `core.hooksPath` at an
  empty directory this build owns. A certification found that an ordinary read
  of such a repository ran the subject's `post-index-change` hook and then
  refused; both halves of that are closed, and the hostile matrix now carries a
  row that fails if either returns.
- `rev-parse --git-common-dir` answers the **common** directory on a linked
  worktree, as real Git and 2.4.0 do. It previously answered that worktree's
  private git directory at exit 0 — a wrong answer rather than a refusal.
- The environment overlay a caller may pass is **additive**. It can add an
  ordinary variable; it can never replace one this build constructed, and every
  `GIT_*` name is closed except the delegated Trace2 witness. An overlay that
  tried could redirect Git's configuration sources or aim the construction-time
  index refresh at the subject's own index.
- A diff of content with a text conversion or external diff driver is now the
  **raw** diff, because no driver runs.
- A repository declaring `filter.*.clean`, `.smudge`, or `.process` is refused
  before Git launches. Omitting an active filter made a clean file appear dirty
  and exposed its pre-clean content through `diff`; executing it is outside the
  sterile boundary, so the safe bounded answer is a named refusal.
- `core.excludesFile`, `status.showUntrackedFiles`, `core.attributesFile`, and
  `core.abbrev` are named refusals. Each changes ordinary answer bytes, and
  silently dropping each produced a wrong exit-zero answer.
- Accepted configuration values preserve whitespace before an empty quoted run
  and data before continuation syntax. Losing the former let a governed remote
  name resolve to a different address from real Git and answer at exit zero.
- A repository whose ref store this build cannot import is refused **by name**
  rather than answered wrongly.
- `probe` on a directory that is **not a repository** now reports *cannot ask*
  rather than *Git looked and said no*. Both are non-answers and the new one
  carries a named cause, but a caller branching on `answer.failed` takes the
  `not answered` path instead.
- `config_with_origin` reports the repository's **own** configuration files and
  no longer the operator's global or system ones, because a governed answer must
  not depend on the machine it runs on. It **refuses** a configuration that
  includes another file, rather than reporting the part it read: under an
  explicit `GIT_DIR` Git does not follow `include.path`, and a shorter list would
  have been a repository hiding `notes.*` behind an include.
- A remote **name** is resolved to its URL from the repository's configuration
  read as data, so `url.<base>.insteadOf` rewriting no longer applies. The
  address contacted is the one written in the file and visible to the caller.
- The **file transport stays enabled**, as it is in 2.4.0, so an `ls-remote`
  against a local path reads whether the caller spells the path or the
  repository's own `remote.<name>.url` does. The permission is constant rather
  than derived from the arguments, because a permission that varies is one an
  argument can steer. What 2.4.0 left open and this release closes is the
  program: `--upload-pack` is injected for every transport verb, so
  `remote.<name>.uploadpack` no longer names something that runs.
- On a populated submodule, local forms outside the measured composition report
  the committed gitlink state and suppress the submodule's dirty detail.
- A populated submodule with `submodule.<name>.ignore` in `.gitmodules` is
  refused because the no-child composition cannot reproduce that dirty-state
  suppression without widening its measured grammar. The same declaration in
  main or active worktree configuration is refused by the answer-shaping boundary.
- An uninitialised gitlink remains readable when `.gitmodules` declares ignore:
  without a child `.git`, the policy shapes no child answer. Real Git and frozen
  2.4.0 report the cross-product clean; the previous blanket refusal regressed it.
- A filesystem-read-only subject Git directory is copied into owner-writable
  private scratch before the harness writes its configuration or refreshes its
  copied index. The subject's modes are left unchanged; only the harness-owned
  copy changes permissions, and existing file execute bits are preserved.
- **`verify-pack` is refused, and remains one explicit read reduction.**
  Frozen 2.4.0 answers it; this release does not, because `git verify-pack`
  spawns `git index-pack --verify-stat` and a local governed read creates no
  child process. The refusal is explicit and names its cause. Nothing in this
  toolbelt calls `verify-pack`, and this release already declines to index a
  pack elsewhere for the same reason.

  **This release is therefore not free of behavioural reductions, and does not
  claim to be.** It is a strict security and governance improvement in spite of
  those reductions, because the boundary refuses instead of returning bytes it
  cannot reproduce safely, while `verify-pack` remains an unused read at the edge of the
  declared surface and what it adds is structural: every configuration source
  Git consults is a file this harness wrote; a local read creates no child
  process at all, so no repository can name a program that runs; the boundary no
  longer decides anything from a list of verbs, options, helpers or spellings,
  which is the mechanism that failed in six previous generations; and the answers
  are measured against the previous release by the shipped differential rather than
  asserted. A capability that no caller uses is a smaller thing to lose than
  those are to gain, and the trade is stated here rather than left for a reader
  to discover.

- A working tree containing a directory named `.Git` or `.GIT` is **read** on a
  case-insensitive volume, where a second qualification pass found it crashing a
  tool with an unhandled `FileExistsError`. Which entry Git will open as `.git`
  is now resolved through the filesystem rather than by comparing a name to a
  string, so the detector and the copier cannot disagree about it.
- **Every** failure of the sterile construction is now a refusal with a named
  cause. Anything it can raise that is not one of this pack's own refusals used
  to escape both `run_cli` and `probe` and reach the operator as a traceback
  indistinguishable from a bug in the tool.

### The 2.4.1 records this tree carries

2.4.1's work is in this release's ancestry, so its records are in this release's
tree. They are kept, not deleted: eight of them are the frozen designs whose
successive failure is the evidence `RP2.5.0-RECURRENCE-MAP.md` reads, and a
release that removed them would be arguing from evidence a reader cannot see.
None of them describes a shipped release, and `evolution/rp2.4.1` is where the
line itself stops.

- `docs/RP2.4.1-GATE.md` — the gate record 2.4.1 reached before its final
  certification refused it. Retained as the account of what that line did.
- `docs/RP2.4.1-DESIGN-R1R2-design-strength-and-provenance.md` — design strength
  and provenance; the one 2.4.1 design not about the Git boundary.
- `docs/RP2.4.1-DESIGN-B1B4-git-read-authority.md` — what a governed read may
  execute and answer about. First of the eight.
- `docs/RP2.4.1-DESIGN-B5-configuration-scope.md` — asking Git which
  configuration it applies, by scope, after two versions inferred it.
- `docs/RP2.4.1-DESIGN-B7-conditional-closure.md` — a closure whose reason names
  a condition, declared where the inspection could act on it.
- `docs/RP2.4.1-DESIGN-B8-transport-reenable.md` — pinning the transport names
  the repository itself mentions, after a repository re-enabled one.
- `docs/RP2.4.1-DESIGN-B12-nested-repository-config.md` — every repository whose
  configuration Git applies.
- `docs/RP2.4.1-DESIGN-B13-closure-reach.md` — a closure holds only where its
  mechanism reaches.
- `docs/RP2.4.1-DESIGN-B14-reach-by-observation.md` — reach is a fact about Git,
  not a description of this module. The last of them, and the one whose own
  repair produced both an under-refusal and an over-refusal.

### What this release ships

- `tools/sterile.py` — the boundary. It constructs the git directory a governed
  read runs against: its own configuration from a blank slate, the subject's
  objects attached rather than copied, refs and `HEAD` copied as plain files, and
  the index copied so that a refresh never touches the subject. Where the working
  tree holds another repository it builds a view in which every `.git` is one this
  harness made, and it refuses — rather than answers — when it cannot reproduce
  what it was asked about. `gitread._run` is its only caller.

`tools/gitread.py` loses the machinery that decided authority by enumeration: the
configuration inspection, its thread-local re-entrancy guard, the nested walk, the
root binding, and the option refusals that matched `-v` and `--verbose` while Git
also accepted `-vv`, `--verb` and `--verbo`. The names that machinery exported
remain as projections: they report what a repository declares and decide nothing,
which `test_no_refusal_depends_on_a_projection` establishes by emptying all four
and finding that no answer, no refusal and no execution changed.

`tools/release_delta.py` was the last caller that reached Git around the boundary
and now goes through it, so `gitread` is the toolbelt's only path to Git.

### Evidence this release ships as runnable files

- `docs/acceptance/rp2.5.0-hostile-matrix.py` — the hostile Git-configuration
  matrix: every verbosity spelling, an explicitly requested driver, an ignored
  never-a-submodule checkout, a nested `.git` in several spellings, three that
  cannot be rebuilt, `sha256`, `reftable`, and a `.git` that is a file. It reports
  how many rows carry a positive control, because a row where real Git runs
  nothing proves nothing.
- `docs/acceptance/rp2.5.0-mutation.py` — the mutation harness, which verifies a
  green baseline first, refuses to count a malformed mutant, and asserts the
  subject is byte-identical afterwards.
- `tools/submodule_no_child.py` — the composition itself, as a module rather than
  a prototype: it answers a submodule-sensitive read from structural Git
  observations made above the boundary, so the answer is assembled without any
  read recursing into a child's working tree. Gitlink identity comes from the
  index and the recorded tree. `.gitmodules` is read only to refuse an ignore
  policy the composition cannot reproduce; it never supplies gitlink identity.
- `docs/acceptance/rp2.5.0-submodule-differential.py` — the corpus that scores it:
  its matrix population is derived at runtime against frozen 2.4.0 with deliberate positive controls,
  including a control that detects a trace which was written by an earlier call
  rather than by the read being counted.
- `docs/acceptance/RP2.5.0-submodule-proof.md` — what that corpus establishes and
  what it does not, written beside it so a reader is not left to infer the scope
  of a passing run from the fact that it passed.
- `docs/acceptance/rp2.5.0-floor-differential.py` — the frozen-floor differential:
  the same public entry point called on this release and on 2.4.0 in separate
  interpreters, compared as raw bytes, refusals included, over a fixture and form
  population derived by the script. It needs a 2.4.0 checkout named by `FLOOR_FROZEN_ROOT`, because the
  floor is a release and not a file, and it writes its report outside the checkout
  so that running it does not unpin the tree. It found four capability regressions
  that every byte-comparing oracle baselined on this release had passed over.

All three were in the author's scratch directory when the gate record first cited
their figures. An independent certification could reproduce the properties and
not the numbers, which is exactly what this pack's rule about figures exists to
prevent, so they ship.

### Records this release adds

- `docs/RP2.5.0-GATE.md` — this release's gate record, written as the release is
  built and saying only what has been established.
- `docs/RP2.5.0-RECURRENCE-MAP.md` — what fifteen repairs of one boundary were
  evidence of, and the hypothesis that reading them together produced.
- `docs/RP2.5.0-DESIGN-A1-sterile-execution.md` — the frozen design: the
  invariant, the mechanism, four rejected alternatives with their reasons, the
  measured cost, seven failure modes and eleven oracles.
- `docs/RP2.5.0-DESIGN-A2-nested-and-ambient.md` — what an independent design
  reading falsified in A1 before anything was implemented, and the two polarity
  inversions that replaced it. A nested `.git` that was a *symlink to a
  directory* executed the subject's program, because the mechanism for nested
  repositories was still enumerating layouts while the mechanism for
  configuration sources had stopped enumerating keys. The name `.git` now
  decides and the kind of the entry never does; anything that cannot be rebuilt
  sterile refuses the read; and the finished view is checked by walking it
  rather than by trusting the loop that built it.

### One governing interface, two backends qualified separately

`docs/RP2.5.0-DESIGN-A7-qualified-semantics-hardened.md` did not survive its own
reading. Permitting exactly the Git binary is not a boundary: the helpers in
`git-core` are symlinks to that binary, so the clause admitted Git's own
background daemons, while the helper a remote read needs is a separate binary
the same clause denied. Eleven frozen tests regressed, one of them asserting
against that failure by name.

`docs/RP2.5.0-DESIGN-A7.1-capability-scoped-backends.md` supersedes it. The
governed interface stays one interface, and the execution policy is chosen from
the operation the caller asked for, never from anything the repository controls:

* a **local read** may create no child process at all, and any attempt fails
  closed. No list of programs takes part in that decision, so nothing about
  which binaries exist or what they are named can widen it;
* the **remote-verification capability** keeps the mechanism already qualified
  for it, because its legitimate semantics require programs a local read never
  needs.

A populated submodule is the case where those two rules would collide, since the
previous release answers it by letting Git start a child. It is answered instead
by composing independently governed childless reads — submodule identities taken
from stage-zero gitlinks rather than from `.gitmodules`, each submodule observed
by its own top-level governed read, and the result assembled with Git's own
porcelain field rather than a reimplementation. Seventeen fixtures across
thirteen read forms yield 183 byte-exact answers, 25 matching frozen refusals,
and 13 declared refusals for submodule ignore policy, with twelve deliberate
positive controls to prove the corpus can fail.

### The question was answered, and the seventh design follows from the answer

The owner ruled that **harness-defined semantics are authoritative** for a governed
read: equivalence to real Git running under configuration the repository supplied
is not required, and the qualified 2.4.0 contract is the non-regression floor.

That retires the standard the first six designs were judged against.
`docs/acceptance/rp2.5.0-divergence.py` has been reclassified rather than
deleted, and every row it recorded is still reproduced. What changed is that it
now separates two things it had been scoring as one: rows where the repository
asked to change how the checker itself behaves, which the decision makes
expected, from rows where the constructed view simply failed to carry
git-directory state, which remain defects and still fail the script.

`docs/RP2.5.0-DESIGN-A7-qualified-semantics-hardened.md` is the design that
follows. It leaves the qualified sterile read exactly as it is and wraps the
OS barrier — the one part of A5 and A6 that no reader ever broke — around it:
writes to the subject denied, every execution but Git's own binary denied, and
no configuration key named anywhere in the profile. The enumeration stays
exactly as qualified and stops being the only thing between a missed key and a
running program.

### Six designs, six falsifications, and the question underneath them

Every generation was frozen before implementation and read blind by independent
readers. A1 and A2 ship in `tools/sterile.py`; A7.1 ships as the
capability-scoped backends and submodule composition. A3 through A7 are
falsified historical designs, not the current implementation. This section
records what each one died of, because the pattern is the finding.

`docs/RP2.5.0-DESIGN-A3-owned-or-refused.md` stopped enumerating what a read
needs and asked instead which keys the harness owns. A reader found an owned-key
exemption resting on a judgement about what a setting could probably affect,
which is the open set again under a new name.

`docs/RP2.5.0-DESIGN-A4-sources-and-standing.md` replaced that with declared
sources and standing. A reader found a source outside all four generations'
models: the case-folding semantics of the volume the harness materialised on.

`docs/RP2.5.0-DESIGN-A5-authentic-read-denied-exec.md` stopped reproducing the
subject at all — read the real repository, and deny the process the ability to
execute. Two readers working blind and separately returned the same verdict from
opposite directions. One found an ordinary `git status` rewriting the subject's
real index while merely answering. The other found that permitting the Git binary
permits *every Git subcommand*, chosen by the repository: with `diff.external`
set to the bare word `git` and a working-tree file named after a subcommand, a
governed read repacked the subject's own object store, at exit zero, with every
child process completing successfully.

`docs/RP2.5.0-DESIGN-A6-authentic-or-declared.md` took away the capability the
barrier could not safely grant — the process could create no child at all and
could write to neither the subject nor its resolved Git directory — and let the
kernel's denial bit choose between the authentic answer and a fallback. Two
readers broke it too. Denying execution turned out not to be denying *influence*:
`core.fsmonitor` is a boolean that names no program, and a repository that leaves
a socket where Git expects its file-system monitor is believed by Git, over a
channel that creates no process and so is never denied. A governed read then
reported a tampered file as clean, three times running, and labelled the answer
authentic. Ordinary configuration does the same thing without any socket at all.

The pattern across all six is a question this pack has not answered, and each
design has been judged against both answers at once:

> **Should a governed read report what the repository says, or what the harness
> says?**

The promise above — *every configuration source Git consults during a governed
read is a file this harness created* — answers *the harness*.
`docs/acceptance/rp2.5.0-divergence.py` answers *the repository*: it scores a
governed read against real Git and calls every disagreement a divergence to be
closed, beginning with a repository that sets `status.showUntrackedFiles` and is
therefore obeyed. A1 through A4 satisfy the promise and fail that corpus. A5 and
A6 satisfy the corpus and fail the promise. The two standards cannot both be met,
which is what six falsifications look like from the inside.

Deciding which one governs was a human decision under `DECISIONS.md` D14 and
D23, and **it has been taken: harness-defined semantics are authoritative for a
governed read.** Equivalence to real Git running under configuration the
repository supplied is not required and is not a defect. The qualified 2.4.0
contract is the non-regression floor: subject-supplied configuration is input to
inspect and report where the contract says so, and is not authority over how the
governed checker itself behaves.

That ruling settles which standard applies. It settles nothing else. When it
was taken, 2.5.0 was still `IN_PROGRESS` and no project could pin it; the
separate 2026-09-10 row-2 freeze is what changed that, and this ruling neither
anticipated nor authorised it. In particular the ruling does not authorise
losing a capability 2.4.0 holds — that remains a separate decision under the
same two entries.

## 2.4.1 — the six the full-release audit reproduced

A **PATCH** release (`DECISIONS.md` D11), derived rather than assumed: every
change here is *enforcement of an already-promised guarantee*, which is what
PATCH covers. No new tool, policy or capability ships. No contract key, CLI
input or public name is added or removed — `DesignRecord.problems` gains one
keyword argument whose default is 2.4.0's behaviour, and `backend_contract`
exports one function two existing callers now share. Nothing about authority,
contracts or migration changes incompatibly. `tools/surface_diff.py` over the
range is the check, not this paragraph.
**State `IN_PROGRESS`** — a candidate. **No project may pin it.** The transition
to `QUALIFIED_AND_FROZEN` is `policy/hitl-matrix.md` row 2 and has not been
taken. Gate: `docs/RP2.4.1-GATE.md`. **2.4.0 is untouched**: same revision, same
digest, same state, and it remains the release a project pins today.

### Why this release exists

A full behavioural audit of frozen 2.4.0 — two independent readers plus
coordinator re-execution — reproduced six defects that a delta-scoped reading
could not have found, because none of them was in what the last delta touched.
That is limitation 67 of 2.4.0 happening on purpose rather than by accident.
Every one of the six was reproduced by execution before a line was written, and
each is a **recurrence of a class this pack already records** — `RECURRENCE` from
`tools/evolution_evidence.py` for all six, no new class, none merged by guess.

### What each one was, and what it is now

- **A record could lower the bar the work was opened against.** A capability
  honestly declared `MATERIAL`, on a contract declaring `requires.design: true`,
  reached `capability open: READY` against a five-line record that declared
  itself `TRIVIAL` and stated no alternatives, no failure modes and no oracles —
  and the readiness report said `design VERIFIED`, which is an affirmative claim
  that the gate was met, not the `NOT_REQUIRED` limitation 51 describes.
  `DesignRecord.problems` now takes the strength the opening authority requires
  and refuses a record weaker than it. The comparison lives in the reader,
  because the module a second caller reaches directly was where the weaker
  answer was.
- **A design could be written after the implementation it governed.** The gate
  established ancestry between two revisions the record *named*, and never asked
  when the record itself came into being: a record first committed after the
  work, naming a base that predates it, reported `DESIGN FROZEN` with
  `--mutation-begins-at` correctly supplied. Its content must now already be
  present, byte for byte, in the tree at the revision where mutation began —
  which answers all three ways of getting this wrong (written after, edited
  after, never committed) from history the repository already holds, with no new
  input from any project.
- **`unknown` meant two different things.** The packed configuration string
  normalised it and the structured identity mapping — a supported path, and the
  one an adapter uses for any identifier containing a space — carried it
  verbatim. So `effort: "unknown"`, the honest answer when a surface does not
  report one, completed an identity and two such rows graded `confirmed` for a
  configuration nothing had established. One function now answers for both
  paths, and it compares by word rather than by punctuation, for the reason
  `_provenance_key` already gave about provenance markers.
- **Verifying a pin executed the verified repository's own program.**
  `gitread` neutralises the configuration keys whose values Git runs, "for
  *every* invocation rather than at the call sites somebody remembered", and
  `pack_pin` was the call site nobody remembered: it called `subprocess`
  directly, so a `core.fsmonitor` — local, or **global, needing no write to the
  release at all** — ran twice and the tool printed `pack pin verified`. Every
  Git read the pin makes now goes through the guarded reader.
- **The one file the digest cannot cover was compared to nothing.**
  `PACK_MANIFEST.json` is excluded from its own digest of necessity, so a root
  could claim any test population it liked, or replace every known limitation
  with one sentence saying nothing was wrong, and still verify. It is now compared
  with the manifest committed at the pinned revision. That establishes the
  manifest is the one in the commit — **not** that its claims are true; no
  mechanism here can count a release's tests or audit its own limitations, and a
  check whose message outran its reason is the defect this module exists to
  refuse.
- **The operator's ignore rules hid release material.** `--exclude-standard`
  honours `core.excludesFile` and `.git/info/exclude`, neither of which the
  release ships, can see, or is a claim about — so on a machine whose global
  ignore file carries `*.jsonl`, any `.jsonl` could sit in a verified root
  unreported, and anyone able to write `.git/info/exclude` could choose their own
  exemption. Untracked material is now measured against the `.gitignore` files
  the release actually tracks.

### And the certification of THAT repair found reach described, not observed

Two more, with one cause. `diff.*.textconv` is excused as disabled by
`--no-textconv`, a flag this module adds for the diff-producing verbs — and
`git status -v` prints a patch, applies textconv drivers, and accepts no
`--no-textconv` by any spelling. And the nested walk enumerated index gitlinks
while Git's inline submodule diff opens `<path>/.git` from the working tree,
whether or not that path is still a gitlink; `git rm` of a submodule leaves
exactly such a directory behind on every other machine.

Both are the same mistake in the same place: **this module described its own
behaviour and called that the reach.** The flags it passes became "the flag is
passed"; the index it reads became "these are the nested repositories". Reach is
a fact about Git, and both facts were there to be checked.

`-v` and `--verbose` are refused as arguments now, beside `--textconv` and
`--ext-diff`, so the closure stays true rather than narrowed and
`status --porcelain` — which emits no patch and reaches no driver — keeps
reading. The walk enumerates directories containing `.git`, which strictly
contains the populated gitlinks, stopping at each repository it finds.

Repairing them exposed a third: `remote.*.uploadpack` had been grouped with the
diff keys as though one flag covered both. `--upload-pack` goes on the transport
reads and `--no-ext-diff` on the diff verbs, so that grouping was wrong in both
directions at once — closing the key where its flag is absent and opening it
where its flag is passed. Each flag-based closure carries its own verbs now.

The reasoning and the two rejected designs are in
`docs/RP2.4.1-DESIGN-B14-reach-by-observation.md`. The cost of the walk is
recorded in `known_limitations` rather than left to be discovered.

### And the certification of that walk found two defects inside it

**A closure reaches only as far as its mechanism does.** `diff.external` and the
two attribute-selected diff keys are excused because this module passes
`--no-ext-diff --no-textconv`. Those flags are on the outer command line, and the
nested `diff` Git runs for `diff.submodule=diff` does not inherit them — so the
submodule walk applied that table one directory down where it does not reach, and
a submodule's `diff.external` ran while the inspection reported nothing. The
standing configuration does travel to a nested process, as `GIT_CONFIG_*`; a flag
does not. Those entries are declared now and dropped for a nested repository, and
a structural test asserts every closure justified by a flag is declared as one.

**And the gitlink listing swallowed its own refusal.** It was wrapped in
`except GitRefusal: return []`, reasoning that it errors for a path that is not a
repository. It does — and it also errors when it times out, so an index read past
the caller's deadline reported no submodules and the read went ahead with a
submodule's filter applied. Reproduced at 35ms and 40ms against a 90,000-entry
index.

That is limitation 14 written again, in a new function, one cycle after that
entry was recorded — the same rationalisation, in the same words, about a
different read. It is recorded here rather than quietly fixed, because a pack
that repeats its own documented defect while widening a check is evidence about
how this kind of widening goes, not only about one function. Both are in
`docs/RP2.4.1-DESIGN-B13-closure-reach.md`.

### And the certification found the inspection asking about one repository

A populated submodule is a second repository, and Git applies **its**
configuration when it runs the nested `status` and `diff` that an ordinary
superproject read requires. The inspection listed only the superproject's, so a
clean filter declared one directory down was invisible to it and ran — nine
times in one reproduction, through this pack's own `workspace_report` path.

That is the fifth defect in this area and the same shape as the first, so the
rule is stated once rather than patched again: **the inspection's subject is
whatever configuration Git will apply to this read.** `--local` read one file
while Git applied two; the general `protocol.allow` was assumed to cover the
specific key Git consults; a lower-cased name was written where Git keeps the
subsection verbatim; and now the superproject was inspected while Git also read
the submodule.

Every populated submodule is inspected now, under the rule the superproject
already lives under, and the finding names the path that owns it. The reasoning,
the recurrence table and the two rejected designs are in
`docs/RP2.4.1-DESIGN-B12-nested-repository-config.md`. Suppressing
the nested processes instead was rejected: it would close the route by making
the reports lie, and a submodule change would stop appearing in `status` and
`diff` — trading repository-chosen execution for a false report.

The cost is recorded in `known_limitations` rather than discovered later: a
superproject whose submodule declares a program-valued key is refused where it
was read before.

Mutation found two gaps in the first version of these tests. Dropping the gitlink
mode check left every tracked path treated as a possible submodule, so a tracked
symlink pointing at an unrelated repository would have refused the superproject;
and the depth bound returned what the walk had seen instead of refusing, which is
a partial inspection reported as a clean one. Both are pinned now.

### And mutation found the same repair matching two transports as one

The pin compared the repository's spelling case-insensitively against the
transports the caller had enabled. But `protocol.File.allow` and
`protocol.file.allow` are different transports to Git — the first enables a
`git-remote-File` helper — so a repository could keep its helper enabled simply
by spelling the name differently from the transport the caller asked for. With
`file` enabled and the repository declaring `File`, the helper ran.

No test distinguished the two spellings and every one of them passed; a mutant
of the comparison is what found it, and the mutant was right where the shipped
code was wrong. Only the spelling the caller actually enabled is left alone now.

### And the certification of THAT repair found the pin renaming its own key

Git folds a configuration section and variable name to lower case and keeps a
**subsection** verbatim, so `protocol.Review.allow` and `protocol.review.allow`
are different keys to it. The new pinning read the transport name off its own
lowercased copy of the key, so against a repository declaring
`protocol.Review.allow = always` it wrote `protocol.review.allow = never` — a
setting nobody had made — and left the one that was in force untouched.

An independent certification reproduced it with an installed remote helper whose
transport name carries a capital: the helper ran, and the publication
verification accepted the namespace the helper invented, with no findings. The
lowercase control was refused, which is what made the case the whole mechanism.

The name is sliced from the spelling the listing actually reports now, and
compared case-insensitively only against the transports a caller enabled —
because callers name ordinary transports, while the key written has to be the
one Git will consult.

The same reading found the identity's own completeness check comparing against
the `UNKNOWN` sentinel rather than passing through `normalised_identity_value`,
so a dimension given as the word "unknown" was unestablished on the persisted
path and established in the identity. It was reported as non-blocking and is
repaired here anyway: it is this pack's own recurrence class, two mechanisms
answering one question differently, inside the boundary this release built to
end it — and it erred towards calling a configuration qualified.

### And the certification of that repair found the subject choosing the policy

The hardened reader refuses transports with `protocol.allow = never` at command
scope, and reasoned from Git's precedence that this was enough:

> Git consults the specific key first and falls back to the general one, so every
> transport the caller did not name stays refused

The first clause is true and the conclusion does not follow. `protocol.allow` and
`protocol.ext.allow` are **different keys**, so the general refusal never
contests the specific one — and the repository being read can set the specific
one itself. A repository declaring `protocol.ext.allow = always` beside an
`ext::` remote had its own program executed with **no transport enabled by any
caller**, and `ext` is not even a transport this module will enable. The
inspection reported nothing, because a key that re-enables a transport is not a
key whose value is a program.

It also falsified the closure next door, which excused `core.gitProxy` as
unreachable because `git://` "is not enablable": the repository enables it.

The transport names the repository itself mentions are pinned to `never` at
command scope now, where the same key outranks the repository's copy. The names
come from the subject rather than from a list of transports someone remembered,
because `protocol.<name>.allow` accepts any remote-helper name. A transport the
caller deliberately enabled is left alone, so the one observation of what a push
actually did still works.

This hole is present in frozen 2.4.0 as well, so it is a standing one rather
than a regression here — but it was reachable, undisclosed, and stated as
closed. Rejected alternatives are in
`docs/RP2.4.1-DESIGN-B8-transport-reenable.md`: refusing any repository that
sets the key over-refuses, and pinning a fixed list of known transport names
guesses at what Git will accept next.

### And the certification found a closure that holds only sometimes

`CLOSED_PROGRAM_KEYS` excuses a program-valued key from the safety inspection
when this module can show Git will never run it. One entry excused itself on a
condition and was then applied unconditionally:

    "core.sshcommand": "neutralised, and removed only when ssh is deliberately enabled"

The standing configuration does neutralise it. But the transport settings
**remove that neutralisation** when a caller deliberately enables `ssh`, which
hands the repository's own value back to Git — and the inspection skipped the
key anyway, because the closure named a condition nothing acted on.

Reproduced with no network, no socket and no ssh binary: a repository
configuring `core.sshCommand` to a local program had that program executed
through this module's own hardened reader by the publication gate's remote
verification, while the inspection reported nothing. The fabricated ref
advertisement it printed could then be read as a clean verification — a
publication result computed from the repository's own claim about itself.

This is the fourth time this release has found a key called closed on a premise
that does not hold on every path; the first three claimed reachability only
through `--filters`, which ordinary `diff` disproved. The condition is now
declared where the inspection can act on it, and the transports a call enables
reach the inspection that decides which closures still hold. A repository
declaring the key is refused for the SSH operation, by name, and reads normally
otherwise. Pinning the key to Git's default instead was rejected: it would have
silently discarded a legitimate per-repository SSH wrapper, and deleting the
closure outright would have refused every ordinary read of such a repository.
The reasoning is in `docs/RP2.4.1-DESIGN-B7-conditional-closure.md`.

### And the reading of THAT one found a configuration Git reads and this did not

A configuration key need not be valid UTF-8. Git reads one that is not without
complaint, and `nul_paths` decodes with `surrogateescape` for exactly that
reason — its own words are that a byte string which cannot be decoded must still
reach a checker, because refusing to represent it is how it goes unexamined.

The scope-labelled listing was being read as text and re-encoded to hand back,
and a bare `.encode()` cannot invert a `surrogateescape` decode. A repository
carrying a non-UTF-8 subsection name therefore raised `UnicodeEncodeError` out of
`program_valued_config` and out of every governed read: a denial that names no
cause, and neither of this module's two refusals. The defect predated the scope
repair, on the line that repair rewrote, and had no test.

The listing is read as bytes now, which is what every other `-z` enumeration in
this module already did, so there is no round trip left to invert. Both
directions are pinned by one oracle: the harmless case must read, and a
program-valued key whose subsection cannot be decoded must still be found and
refused — a repair that merely made the undecodable key disappear would have
passed the first half and opened the hole the check exists to close.

The same reading noted the timeout oracle set its deadline from a single warm
measurement, so a transient inflation of that one measurement would stop it
biting. The budget is capped as well as scaled now.

### And the reading of THAT repair found it refused valid repositories

Not catching the worktree read meant every way it could fail now reached the
caller — including two that are not failures of the repository at all. Git lets
`extensions.worktreeConfig` be enabled without `config.worktree` ever being
created, and it refuses `--worktree` outright when the extension is off and more
than one worktree exists. Both are ordinary repositories that `git ls-files`
reads perfectly well, and both were refused.

That is the third answer this inspection has given to one question, and the
second to be wrong, so the question itself was reconsidered rather than the
handling patched again. The check must know **which configuration Git will
apply**. It had been inferring that — first from a single file, then from the
extension key's presence, then from whether a second read failed. Git will
simply say: `--show-scope` labels every applied key with where it came from.

The reasoning is frozen in `docs/RP2.4.1-DESIGN-B5-configuration-scope.md`,
written before the change and recording the two designs rejected — classifying
the second read's failures more finely, and parsing `config.worktree` directly.

One read now replaces two, keeping the keys Git labels `local` or `worktree`.
The extension's value, the missing optional file, linked worktrees, and Git's
own rule about `--worktree` are all Git's business again. Keeping the scopes
rather than dropping the ones to ignore is deliberate: a scope a later Git adds
arrives ignored instead of silently trusted.

The scope filter is load-bearing. Under this module's hardened environment Git
reports fifteen program-valued keys in `command` and `unknown` scope, including
the module's own hardening flags; without the filter the check refuses every
repository. Mutation also showed the framing guard had no test, and that
removing it made a reply the parser could not read return *nothing found* —
this check's own fail-open, arriving through the parser. The guard stayed and
the missing test was written.

### And the reading of that repair found the widened read could be skipped

The worktree inspection was wrapped in `except GitRefusal: pass`, on the
reasoning that it errors when the extension is off. It does — and it also errors
when it times out, so a per-worktree configuration large enough to outlast a
caller's deadline returned an empty inspection while Git applied the filter, and
the read went ahead. The handler two branches below already refuses exactly
that, in the same words.

It is not caught at all now; that handler owns every way the read can fail. The
fix is smaller than the thing it replaces. A defensive branch the first attempt
added alongside it turned out to be unreachable — Git validates the worktree
file during the local read too — and mutation is what showed it, so it is gone
rather than kept.

### And the closure reading found the standing rule had a blind spot

Deleting three false closures made the filter keys fall to the rule that an
unclosed program-valued key refuses — and that rule read one configuration file
while Git applied two. With `extensions.worktreeConfig`, Git also applies
`config.worktree`, which `git config --local --list` never shows, so a filter
declared there stayed invisible and ran seven times through the guarded reader.
Both sources are inspected now. The extension key was always visible to
`--local`; the module had what it needed to ask the second question and asked
only the first.

The same reading found a regression in the repair before it: preserving an
integrity refusal's words was implemented by testing which module an exception
came from, which caught `GitRefusal` too, so an unresolvable HEAD raised out of
`verify_pin` instead of reporting `HEAD could not be read`. Narrowed to the
integrity refusal.

Two oracles written for that work were green against their own defect — one
drove the single verb the binding exempts, the other did not exist — and
mutation caught both.

### The certification found four, and they were two questions

Designed first, because both move an authority boundary:
`docs/RP2.4.1-DESIGN-B1B4-git-read-authority.md`, frozen against the audited
candidate and committed before any implementation commit. Three architectures
were considered and two rejected — neutralising arbitrary filter names, which an
empty clean command turns into breakage wearing the costume of neutralisation,
and a per-caller binding, which is the divergence this release exists to close.

**That record also carries a correction, rather than being reshaped to match
what shipped.** Its selected design bound the resolved repository as well as the
worktree, on the premise that a linked worktree's git dir sits under its own
root. It does not — it lives under the main repository — so that binding refused
every linked worktree, which is the layout this pack develops in. Execution
falsified it before anything was committed, and the design it had rejected is
what ships.


A whole-candidate reading before adoption returned four blockers. They reduce to
two questions, and both belonged to the one reader that already claims to answer
them for every caller.

**What a read may execute.** Three filter closures were asserted and never true:
`filter.*.clean`, `.smudge` and `.process` were listed as reachable only through
`--filters`, which this reader refuses as an argument. An ordinary `diff`
converts the worktree through the clean filter regardless, and the reading
watched a configured program run twice while the inspection reported nothing to
see. They are no longer listed, so they fall to the standing rule that an
unclosed program-valued key refuses. A repository legitimately using such
filters is now refused — stated as a limitation rather than discovered later.

**What a read may answer about.** `core.worktree` redirected reads to a sibling
directory, so a workspace gate reported no unclassified files while one sat in
the project it was asked about; and a release unpacked into a vendor directory
let Git discover the enclosing repository and return zero tracked paths, so the
pin digested an empty tree and declared a byte-identical release not to be the
pack. Git's toplevel is now compared with the requested root inside `gitread`,
once, for every caller — and the local copy `pack_pin` had grown is deleted
rather than left as a second answer.

**And explicit absence stopped inheriting.** A row carrying
`identity: {"effort": null}` — the natural JSON for *the surface did not report
it* — had that key dropped before the overlay, so the packed `effort=high`
survived and two such rows graded `confirmed`. A key a writer includes is a
statement about that dimension; if it says nothing, the dimension is UNKNOWN.

### A whole-candidate reading found the verifier could be pointed elsewhere

`core.worktree` in a checkout's own configuration redirects what Git treats as
the working tree. The untracked-file enumeration then described that other
directory: an unreviewed module sat in the named release root and the pin
printed `pack pin verified`. It is a path rather than a program, so the hardened
reader's program-valued neutralisation never reached it.

The verifier now asks Git which directory it is answering about and refuses when
that is not the root it was given. Asked rather than neutralised, because a
linked worktree sets that key legitimately and its toplevel *is* its root —
which is precisely the case a blanket neutralisation would have broken.

The same reading caught a sentence carried forward from 2.4.0 saying **a project
may pin this release** while `state` read `IN_PROGRESS`. A manifest that
contradicts its own state field about adoptability is the one thing a reader
consults it for. It now states 2.4.0's freeze as history, and no entry claims
this candidate is pinnable.

### And the reading of THAT one found the same hole wearing a new name

A third bounded reading — routed to a different reader, because the one who
found a defect may not certify its closure — returned NOT_READY on two counts,
both introduced by the repair before it.

`--exclude-per-directory=<name>` makes Git look for that name in **every**
directory it walks. The guard checked only the root. So an untracked
`anywhere/.gitignore-not-tracked-by-this-release` containing `*` hid itself and
an unreviewed module while the pin verified: the first repair's defect, reached
through the very filename chosen to close it. No chosen name is safe, because
the name is in the source. The option is gone entirely — Git now reads no
working-tree ignore file anywhere, and the release's tracked `.gitignore` is
supplied by absolute path.

The second: `--exclude-from` was built from the root as spelled and resolved by
Git against that same root, so a relative root with a path component refused a
byte-identical tree. The root is resolved first.

### And the reading of THAT repair found one more, which is the point

A second bounded reading of the repair delta returned NOT_READY on one blocker,
and it was the repair itself. Matching the release's ignore rules in Python was
wrong in both directions against real Git — an anchored root rule stripped of
its `/` hid material at every depth, a nested rule lost bare-name recursion, and
significant whitespace was normalised away. The predecessor had been right about
all of it. Git is the only correct reader of a `.gitignore`; the enumeration now
supplies the release's rules to Git rather than interpreting them, and a
differential over eight rule shapes holds it there. A nested tracked declaration,
which this construction cannot express, is refused rather than guessed.

That is two readings in a row finding the defect inside the repair rather than
in the thing repaired, which is the pattern this release's own limitations
already record about itself.

### The independent reading found three blockers, all of them in the repairs

A single independent reading of this delta returned NOT_READY, and it was right
on every one of them. Every one was reproduced by the coordinator before anything
was changed.

- **The normalisation repair left a third path.** `identity_from_configuration`
  reads `surface` and `pool_id` for itself rather than taking them from the
  parser, and carried its own inline copy of the rule. So `surface=un_known`
  completed an identity and two rows graded `confirmed` — this release's own
  defect, one dimension along, inside its own repair for it.
- **The untracked-material repair read the wrong rules.**
  `--exclude-per-directory=.gitignore` reads the ignore files *present in the
  working tree*, tracked or not, so an untracked `unreviewed/.gitignore`
  containing `*` hid itself and an unreviewed module while the pin still
  verified. The rules now come from the `.gitignore` files the release TRACKS,
  applied with `pathmatch` — the pack's one gitignore semantics, already
  differentially tested against real `git check-ignore`. Refusing wholesale
  whenever an untracked ignore file exists was tried and rejected: `pytest`
  writes `.pytest_cache/.gitignore` into any root the suite has run in, and that
  rule reported the entire cache of the frozen 2.4.0 root.
- **The provenance repair was unreachable from a command line.** `problems()`
  returned before checking when no repository was given, and the CLI defaulted
  one to `None`, so `--mutation-begins-at` alone still printed `DESIGN FROZEN`
  for a design first committed after the work. A requested binding that cannot
  be established is now a finding, and the CLI defaults the repository to the
  record's own directory.

It also found that both `byte-for-byte` comparisons compared decoded text, that
three of this release's new tests did not discriminate what their names claimed,
and that the repaired publication guard still dropped absent declared records
silently. All are repaired above.

### The reading before that found one, and it was a real one

A prefix rename switched off a live public-safety oracle. The guard that stops a
release record stating a publication conclusion while dropping its only known
exception resolved that record from the gate-record **prefix**; this release
moved the prefix and ships the previous release's adjudication, which its
manifest still names. So the guard skipped — and it still skipped with the
protected occurrence deleted from `known_limitations`, which is a check that
reads as active and protects nothing.

It is repaired by reading the manifest's declaration instead of a filename, by
failing rather than skipping when a declaration resolves to nothing, and by
scanning every record the manifest declares rather than one prefix glob. The
first thing it did once repaired was catch a real omission in this release's own
gate record, which is now fixed. Four subject mutants — the manifest dropping
the occurrence, the gate record dropping it, a declaration pointing at a missing
file, and a release genuinely shipping none — behave correctly.

### One guard was rebound, and it is not a quiet edit

`test_this_versions_changelog_entry_names_what_this_release_added` carried a
floor requiring the range to add more than five files before it would assert
anything. That floor exists so the guard cannot be vacuously green on a range
with no additions — a real property, and it stays. But the number was calibrated
against a release that added fourteen files, and it made a *bounded repair
release* — which legitimately adds a design record and a gate record and nothing
else — impossible to ship without deleting the guard outright.

So the floor is now zero rather than five: the guard establishes something
whenever there is at least one addition, and refuses only when there are none.
The property it protects is unchanged and its completeness assertion is
untouched. This is recorded here rather than made quietly, because re-scoping a
rule to fit the release in front of it is the move this pack's own gate records
say must not happen without being said out loud.

### What this release does NOT claim

The design gate reads provenance from the repository the contract declares, so a
project whose design record lives outside that repository gets a stated refusal
rather than an established answer when it supplies `--mutation-begins-at`. That
is failure mode 3 of the frozen design, taken deliberately: fail closed, say so.
Without `--mutation-begins-at` the binding is unchanged and still the documented
weak path. Neither is widened here.

### Designed before it was built

R1 and R2 move the design-before-build authority boundary, so they were designed
first: `docs/RP2.4.1-DESIGN-R1R2-design-strength-and-provenance.md`, frozen
against the 2.4.0 release commit and **committed before any implementation
commit in this release** — a claim checkable by the very mechanism it specifies,
which is the point. Three whole architectures were considered and two rejected
with reasons: caller-side comparison plus a self-declared freeze timestamp, and
caller-side comparison plus git provenance. Both were rejected for the same
half — a comparison that lives in one caller leaves the module a second caller
reaches directly still holding the weaker answer.

R3 to R6 carry no design record. They are enforcement of boundaries that already
exist, in the modules that already own them, and a design document for each
would be ceremony this pack's own scaling rule refuses.

### Evidence

Nine well-formed subject mutants, one per repaired mechanism plus a second for
each of the three whose repair has two halves, scored against a **green 338-test
baseline that excludes the tests failing on any byte change** — the exclusion
limitation 70 of 2.4.0 records after this pack scored one of its own passes
invalidly. All nine killed. Each repair also has the audit's own reproduction
re-run against it, and both directions of the design gate are rehearsed through
the real `capability_open` path rather than through its parts.

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
