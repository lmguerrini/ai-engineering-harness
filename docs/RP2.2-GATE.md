# RP2.2 — gate record

**State: `IN_PROGRESS`.** This release is an evolution candidate. It is not
adoptable, and no project may pin it, until a human release authority moves it
to `QUALIFIED_AND_FROZEN`. Version `2.2.0`, a MINOR bump under D11: new
backward-compatible capability, plus enforcement of guarantees earlier versions
already promised.

## Baseline

Verified before any mutation, on every axis the release declares:

| | |
|---|---|
| Version | `2.1.1` |
| Revision | `4495e61850c08027e47eac6d0db84b4b3380e300` |
| State | `QUALIFIED_AND_FROZEN` |
| Tree digest | `d445c5ce10095edd9a8f6063e9c708f2af7cf1cec266f6758d26f58f7bd50f3e` over 85 tracked files |
| Algorithm | `sha256-framed-v1` |
| Tests | 237 passed |

The digest was checked twice: once with the shipped `pack_pin.py`, and once
with an independent re-implementation of `sha256-framed-v1` written from the
algorithm's description rather than by importing the module under test. A
verifier confirming itself is not a verification.

The frozen 2.1.1 commit is not rewritten. Work proceeds on a dedicated
evolution branch cut from that exact revision.

## Session budget authorisation

Recorded per `policy/BUDGETS.md`: this evolution session was authorised at 12
repair attempts per reproduced root cause, 8 repair rounds per capability, and
4 closure cycles per capability. The three-consecutive-failures rule survives
the raise — a raised ceiling buys more distinct approaches, never more
repetitions of one. The authorisation is session-scoped and does not carry
forward to any project run.

## Capabilities

Tracked in `docs/RP2.2-CAPABILITY-MAP.md`, with the reproduction that justifies
each. Closed capabilities are recorded below as they close.

### C1 — architecture record — CLOSED

The founder architecture decision is recorded as `DECISIONS.md` D14, additively;
D1–D13 and every prior gate record are unchanged. D15 records the rule that an
unanswerable question is never rendered as its reassuring answer, which is the
root cause found beneath EC-C.

### C2 — adapter integrity and pinning — CLOSED

**Reproduced first.** `~/.claude/agents/capability-auditor.md` declared
`isolation: worktree`. `skills/core/worker-contract.md` and
`templates/audit-brief.template.md` both state that a reviewer never creates a
ref, a branch or a worktree. Reproduced end to end: that isolation mode lands
`refs/heads/worktree-agent-*` in the audited repository, and the pack's own
`publication_gate.py` exits 1 on exactly that ref, naming it "an agent worktree
branch created inside the repository under review". The mutating implementer
adapter declared no isolation at all — the two were exactly inverted.

**Repaired.** The reviewer adapter no longer declares an isolation mode, no
longer instructs a detached checkout, and now verifies the tree it was given
rather than moving it. Its git allowance names `merge-base --is-ancestor` and
explicitly refuses `worktree add`, `branch`, `checkout`, `switch` and
`update-ref` as ref-namespace writes.

**Closed durably.** `tools/adapter_pin.py` gives adapters a pinning contract —
exact identity, canonical locator, digest, required/optional status, and the
declared name read from the file rather than inferred from its path. It is
verified at capability open (`templates/PILOT_RUN_PROJECT_BOOTSTRAP.md` Step
0), fails closed on a required adapter that does not match, and never refreshes
a declared digest: `--observe` prints a current digest labelled as an
observation, not a verification. `required` governs absence only — a present
adapter that differs blocks either way, and an unreadable one blocks because
nothing was established.

23 tests. Each was mutation-checked: five independent mutations of the
implementation were introduced and every one was killed by the suite, so the
oracle constrains behaviour rather than restating it.

### C3 — tooling integrity — CLOSED

Every defect reproduced by execution against the frozen baseline before repair.
Three were not on the inherited list and were found by reproducing the ones that
were.

| ID | Defect, as reproduced | Repair |
|---|---|---|
| EC-A(i) | `git ls-files` without `-z` C-quotes any path it cannot print literally, so `annotations/café.txt` reached classification as `"annotations/caf\303\251.txt"` and the project's `annotations/` exemption stopped covering it | every path enumeration goes through one exported NUL decoder; `_run` decodes with `surrogateescape` so an undecodable path reaches a checker rather than crashing it |
| EC-A(ii) | the module diverged from real `git check-ignore` in **both** directions — a wildcard directory name compared by string equality, a bare name not covering the directory it named, `dist/*` stopping one level down, and a directory-only pattern matching files. The count is computed, not recorded: `BASELINE_DIVERGENCES` in `tools/tests/test_pathmatch.py` | matching defined once in git's own terms: a pattern matches an entity, and a file is covered when the pattern matches it or any ancestor. `**` implemented; matching made case-sensitive |
| EC-B | a Conventional Commit `fix:` subject was refused `TRAILER` while `feat:` passed — the gate refusing the form its own contract requires | trailer detection excludes the subject line **only** for the declared Conventional type set; every body line unchanged, and `Signed-off-by:` as a subject is still a trailer |
| EC-C | an annotated tag reported "carries no extra object" (`merge-base` peels it), and a blob ref reported "CARRIES OBJECTS THE PUBLIC REF DOES NOT" as fact although the call had exited 128 | containment became four-valued — CONTAINED / NOT_CONTAINED / NOT_APPLICABLE / UNKNOWN — and the ref's object type, already read and never used, now selects the sentence |
| EC-E | evidence was created `0o755` / `0o644`, world-readable, and the mode was checked by nothing | created owner-only through `os.open` with an explicit mode, and the mode is **read back from the filesystem**; an existing loose directory is tightened, and an entry that became readable is refused rather than retrusted |
| CA-AMD-5 | a declared content exemption switched off **credential and local-path detection** for the exempted blob. `UNIVERSAL_LEAK_KINDS` said no project may do this and `public-safety.md` named the exact mechanism — "writing the exemption as *skip blob content* takes both out at once" | an exemption is a scope over the findings, not a skip over the object (D16) |
| CA-AMD-6 | every form of valid multi-line data raised `unexpected indentation` — `\|`, `>`, `\|-`, `\|+`, and a flow sequence spanning lines | block scalars implemented in the subset parser, verified against a reference YAML implementation across the full cross-product of style, chomping and body shape (60 cases, zero divergence). **No dependency added** — the reference implementation was an oracle during development and D3 holds |
| CA-AMD-7 | the push form was a constant in the gate and a restatement in two documents, compared by nothing | a release-integrity test compares every restatement on an instructional surface against the constant, and a second binds the constant to what the checker accepts. **No drift existed** — this is enforcement added, not a defect repaired |
| RP-EC-3 | `probe` distinguishes "answered" from "ran and could not answer", and three callers consulted only the first. An unreadable `.git/config` reported as a repository with no settings — including no `notes.*` keys, the exact surface D7 watches | every caller consults `failed`; the unanswerable case raises or reports `UNKNOWN` (D15) |
| RP-EC-4 | both "nobody looked" paths raised `TypeError` instead of a named refusal, because `cause=` collides with the positional parameter of the same name. Latent in 2.1.1 and reproduced against it | fixed, and a mechanical test scans the toolbelt so the construction cannot recur |
| RP-EC-5 | **a real leak.** A directory whose name was a declared private term scanned `clean`, because the scanner matched the term against git's escaped form of the path | closed by EC-A(i); the leak is now found |

`pathmatch` received its first direct test module, oracled against real
`git check-ignore` rather than a hand-written table.

**An oracle failure worth recording.** The first `pathmatch` differential
reported a great many divergences and every one was the harness: `git check-ignore`
consults `core.excludesFile`, and this machine's global ignore file contains
`dist/`, `build/`, `node_modules/` and `*.log`, so the oracle answered for
patterns it had never been given. Isolating it left a small fraction. An oracle answering from
a source the test did not control produces confident, specific, entirely
fictional findings — and it fails toward *more* findings, which reads as
diligence. The isolation is now part of the test module, with the reason.

### C4, C5 — first-party boundaries and provider-surface truthfulness — CLOSED

`policy/execution-boundaries.md`. Vendor enforcement is additive and authorises
nothing; vendor stores are subordinate to durable records; experimental
orchestration surfaces are never dependencies; a mode that changes
authentication or billing class is a **different backend** and inherits no
qualification; and no harness authorises HITL, release, integration or
qualification. Undocumented provider internals are optional, version-fragile,
never normative, and fall back to `UNKNOWN` — and no new logic scrapes them.
Codex quota has no proven machine-readable surface, so it is `UNKNOWN`, with a
human reading admissible as timestamped advisory evidence only.

### C6 — migration, update and rollback — CLOSED

`tools/pack_migration.py`. `pack.root_path` required, canonicalised and
verified; `UNVERIFIABLE_LEGACY_PIN` named rather than repaired; a migration gate
that requires a verified target at a capability boundary; rollback only to a
retained root that still verifies; a release index that lives outside every
release and is read as untrusted input; and candidate accounting, so a candidate
that arrived late cannot be skipped. A security advisory is disclosed loudly and
authorises nothing.

**Reproduced during this session, and it is the reason D18 exists.** The
Consumer-A project carries a correctly formed pin — every field present — to
`root_path: …/runtime-pack-2`, which is the directory this evolution session
works in. Its pin stopped verifying the moment the evolution branch was checked
out there. The verifier reported it precisely, which is the system working; the
situation is a layout defect. **No project was migrated or modified.** Two others
carry version-only pins (`2.0.0`, `2.0.0-wave-a`) and are left exactly as they
are: they are evidence, not authorisation.

### C7 — Project Context — CLOSED

`tools/project_context.py`. Declared, located by canonical reference, carrying a
project-local revision and a digest, in one of five distinct states, with the
digest compared across a capability to prove non-mutation and proposal separated
from adoption. The Core reads no content: a semantically enormous change and a
one-space change are reported identically.

Generalised from a real project's Project Context without vendoring any of its
implementation, and checked against it — this module's tree walk counts the
files in that context and matches the count the project itself records.

### C8, C9 — backend truth and Execution Resource Truth — CLOSED

`tools/backend_contract.py` structures backend identity so that availability
cannot reach a qualification answer and permission cannot reach a capability
answer, and derives per-(family, task class) grades from the real observation
log. `UNKNOWN` is a value on every field; a requested model never populates the
observed one.

`tools/resource_observation.py` reads the **documented** Claude Code status-line
payload. The field set was verified against the installed client's own
documentation block rather than assumed: `rate_limits` is optional, present only
for subscribers and only after a first response, with each window independently
optional — so absent is the ordinary case and is `UNKNOWN`, never `0% used`.
Readings carry their age and report themselves stale. The projection into an
observation is an **allowlist**, not a redaction pass, so the session id,
transcript path and working directory in the payload reach no record: a
redaction pass fails open the first time the payload grows a field, and those
two fields are exactly what the pack's own leak gate refuses. Nothing installs
itself — enabling it is one explicit, reversible setting the operator writes.

### C10, C11 — evidence strengthening and context invariants — CLOSED (bounded)

`tools/evidence_index.py`: `passed` is a derived property of the raw exit status
and not a field, so there is nowhere to record a non-zero result as a pass;
completeness is three-valued so a truncated run is neither; certifications and
waivers bind to an exact candidate; reports are ingested byte-exact; the index
and the directory are checked as a bijection in both directions; discovery is
distinguished from certification-verification; reopening is explicit; retention
is declared per entry.

Context-efficiency invariants were added to `skills/core/continuation.md` rather
than as a new file, and `policy/routing-table.md` shed its narrative to
`docs/RP2.1-ROUTING-EVIDENCE.md` — the grades it held by hand are now computable
from the log by `tools/backend_contract.py`, so the held file is a reading aid
over a computation rather than a second authority.

## Scope classification (release discipline)

**MUST_THIS_RELEASE — all delivered.** The Gate-0C blockers (architecture record,
adapter integrity, first-party boundaries, provider-surface truthfulness, the
mandatory-gate defects), every reproduced 2.1.1 defect, the migration/update/
rollback essentials, the execution-backend truth contract, Execution Resource
Truth, and the Project Context contract Consumer-A needs in order to use this
release safely.

**SHOULD_THIS_RELEASE — delivered.** The bounded evidence strengthening, the
context-efficiency invariants, and the routing-table reduction.

**DEFER_WITH_TRIGGER.** Each carries the observation that reopens it.

| Deferred | Why not now | Trigger that reopens it |
|---|---|---|
| Baseline maturity / convergence phase as a Core field | One project has reached closure. A maturity scale derived from one point describes that point, not a scale | A second project reaches capability closure, giving two comparable points |
| Audit-cycle accounting as Core code | The counters live in `PROGRESS.md` against `BUDGETS.md` and are read by a coordinator. Moving them into Core buys enforcement of a number no one has yet exceeded unknowingly | A capability exceeds an audit budget without anyone noticing, or a second evolution session needs counters that cross sessions |
| Delta-scoped requalification driven mechanically from SHAs | `surface_diff.py` already derives the changed public Python surface between two revisions, and `evidence_index` already binds certification to an exact `(base, head, digest)`. What is missing is deriving a *requalification scope* from those and checking that a run covered it | A candidate whose delta is large enough that full requalification, rather than the work, is the cost driver |
| Vendoring any adapter into the release | Pinning was proved sufficient: `adapter_pin.py` catches the exact contradiction that motivated this release, by digest, before dispatch | Pinning demonstrably failing to provide a guarantee that vendoring would — which would also reverse D12 |

## Qualification

| Step | Result |
|---|---|
| Full local test suite | passes with **0 failures**. The count is `PACK_MANIFEST.json` `tests.passed`, which `test_the_recorded_test_count_is_the_count_the_suite_actually_collects` binds to the suite. Not restated here: adding a test changes it, and a figure this document's own edit invalidates is one it must not carry |
| Release-integrity checks against the real repository | included in the suite; all pass |
| Tree digest, recomputed **independently** | matches: an implementation written from the algorithm's description, not by importing the module under test, produces the manifest's digest over the same file count |
| Clean-clone-equivalent run | a fresh local clone at the exact candidate revision: tree clean, whole suite passing. No remote operation of any kind |
| Pre-repair falsification | the candidate's tests, run against **baseline source**, fail across every touched module and pass against the candidate. **No count is stated here**, because nothing in the release computes one — the same rule the divergence figure now follows. Reproduce: export the baseline with `git archive`, replace its `tools/tests` with the candidate's, drop the six new-capability test modules (they cannot import at baseline, by construction), and run the suite |
| Primary-path non-regression | `pack_pin` verifies; `publication_gate` reports the namespace clean over 2 refs; `commit_gate --range` reports every commit message on the branch conforming |
| D3 import closure | **0 violations** across 19 modules, checked by AST walk including function-local imports; every module also imports standalone, so neither deliberately lazy import — `project_contract` reaching `adapter_pin` and `project_context` — forms a cycle |

`workspace_report` exits 1 against the pack itself. That is correct and not a
finding: the pack is not a project, has no contract declaring its
classifications, and the artifacts it names are gitignored OS and cache files.
None is tracked, so none is inside the digest.

## Measured overhead

Held prose, by the `BUDGETS.md` rule:

    in-release (skills/core/*.md + policy/*.md)   1460
    installed adapters (outside the envelope)     1023
    total                                         2483     target ~2,000

**24.2% over, recorded rather than shaved** — 2.1.1 was 14.9% over on the same
rule. One principled reduction was made rather than a cosmetic one: the routing
table's narrative moved to `docs/`, where read-once evidence belongs, and its
grade rows became computable from the observation log. Trimming further would
have meant deleting live governance to reach a number, which is the pressure
`BUDGETS.md` itself names. The remaining growth is the new governance for five
new Core capabilities.

Delta against the frozen baseline: **not stated here.** Editing this file
changes it, so any literal written here is wrong from the moment it is
committed — the same reason `PACK_MANIFEST.json` does not name its own
revision. Measure it:

    git diff --shortstat 4495e61850c08027e47eac6d0db84b4b3380e300..HEAD

## RP-EC-6 — an adapter repair does not take effect in the session that makes it

Found by dispatching the two closure auditors, which is the most useful way it
could have been found.

The reviewer adapter's `isolation: worktree` had been removed and the corrected
file was on disk. Both auditors were nonetheless given worktrees, and two
`refs/heads/worktree-agent-*` refs appeared **inside this repository** — where
`publication_gate.py` refused them by name, exit 1, exactly as designed. The
same gate had reported the namespace clean an hour earlier, so the control
discriminates rather than always firing.

The harness loads an adapter definition when the session starts. Editing it
later changed the file and not the behaviour.

This is recorded rather than repaired because there is nothing here to repair:
it is how the harness works, and it makes the design of `adapter_pin.py`
sharper rather than weaker.

*   **Verification at capability open, before the first dispatch, is the only
    point where it means anything.** A check that runs afterwards describes a
    dispatch that has already happened; a repair applied afterwards has not
    taken effect at all.
*   **A verified digest describes the file; the session describes what is
    running.** The two agree only across a session boundary, so a repair is
    followed by a new session — and the pin is what makes them comparable.

Both worktrees and both refs are removed before the candidate is finalised, and
the namespace is re-verified. Recorded in `tools/adapter_pin.py` and
`policy/execution-boundaries.md` so the next coordinator does not rediscover it.

## Installed adapters, as they stand at this candidate

Recorded **in full**, because `adapter_pin` requires 64 lowercase hex
characters and refuses anything shorter — a truncated digest is a digest that
cannot be pinned, which would have defeated the whole of C2 through the form of
its own evidence. Found by an independent audit that tried to use them.

Recorded so the founder can pin them, and so a later reader can tell whether the
adapters changed under a running project. **They are outside the release
envelope and covered by no tree digest** — that is exactly why they are declared
and verified rather than frozen (D12, D14 clause 10).

| Adapter | sha256 (full, so `adapter_pin` accepts it) | Change in this session |
|---|---|---|
| `~/.claude/agents/capability-auditor.md` | `62d1a9c1d24eb1871f43dcdb2bb1819c3ed7c47289a7152d31ad58309a08a84b` | **repaired** — isolation mode removed, detached checkout replaced by verification, ref-namespace writes named and refused |
| `~/.claude/agents/capability-implementer.md` | `c5a0a07daa65c3e7c93fa0f9ea2644996cc54e8fe3ecdc4441d04eb60afa916d` | unchanged; it declares no isolation, which is correct for a mutating worker and was the inverted half of the B2 finding |
| `~/.claude/skills/capability-closure/SKILL.md` | `c2055158b8ff28a9d06203f3bb98c45d0145f14a5963856ba5d7ade80d81368e` | unchanged |
| `~/.claude/skills/codex-worker/SKILL.md` | `ac750a8b516cfc7ecb2091d16a28091ce840f45ab47b33d3de71dcf9ed8cebae` | **repaired** — its reads of undocumented Codex internals now carry the four rules in full: explicitly optional, version-fragile, never normative, fallback `requested_only`/`UNKNOWN`. `§8.1` previously *required* the session rollout for identity evidence, which contradicted "optional"; an unreadable rollout now yields `UNKNOWN` rather than a failed dispatch |

Both repairs take effect **at the next session** (`RP-EC-6`), so neither changed
the behaviour of this one.

## Closure audit — round 1

Two blind auditors, fresh context, distinct lenses, each reading a
coordinator-prepared snapshot outside this repository at
`0b34f35c7bd1df4346addc6f76ff2dd7ec65087c`. **Both returned NOT READY.**

Cross-vendor was not available and that is a real reduction in coverage, not a
met requirement: `policy/auditor-strategy.md` asks for two blind auditors with
one cross-vendor *where available*, and the measured value of the tier is that
the two populations come back **almost disjoint**. They did here too — the
correctness lens and the honesty lens overlapped on three findings out of
twenty-nine.

**Every material claim was reproduced by the coordinator before it counted.**

### What the audits were right about

| Finding | Reproduced | Repair |
|---|---|---|
| **The divergence figure does not reproduce** | it was measured on a grid that was then replaced without re-measuring | **restated on the wrong grid, caught again in round 2, and found still restated in round 3.** See below |
| **`routing-table.md` contradicted the command printed inside it** | `AUDIT_PRIMARY` read `confirmed` on one validation, and `READER` read `confirmed` on two dispatches at *two* task classes — against the file's own "one validation is provisional" and "grades are per task class" | both corrected to `provisional`; the role → (family, task class) mapping is now machine-readable and a test compares every row to the derivation |
| **The held-prose breach was undisclosed and 2.1.1's disclosure was deleted** | The manifest's `known_limitations[0]` carried the figure at 2.1.1 and did not at 2.2.0 | measured, recorded, and now checked by a test against the tree |
| **Four surfaces told a project to create the pin this release calls unverifiable** | Following the bootstrap produced `UNVERIFIABLE_LEGACY_PIN` | corrected to four fields; a test binds the documented set to `_REQUIRED_FOR_VERIFICATION`, as D17 does for the push form |
| **The release-index template declared *this* candidate `QUALIFIED_AND_FROZEN`** | An index is what a consumer reads to decide what is adoptable | the example entry that named this candidate now names a placeholder; the other names 2.1.1, which is real and frozen and therefore accurate. `read_release_index` validates `state` |
| **A trailer behind a Conventional prefix escaped** | `fix: Signed-off-by: A Person` passed clean, contradicting the docstring beside it | only the matched prefix is removed now, not the subject line |
| **`pathmatch` over-matched a trailing `**`** | `annotations/**` matched `annotations`; git matches everything *inside* | trailing `**` requires ≥1 component |
| **`pathmatch` did not implement negation** | `!fixtures/real-notes.md` matched nothing, so the file the project excluded stayed exempt and its private-term leak was suppressed | last-match-wins over an ancestor walk — including git's rule that a negation cannot re-include under an excluded directory, which the first attempt got wrong in the permissive direction |
| **`backend_contract` graded every unrecognised outcome `environmental-unknown`** | A case variant of `contradicted` became "nothing was learned" | unrecognised outcomes raise |
| **The grading rule had no test** | `validated >= 2 → >= 1` survived the whole suite | grades asserted per family and task class against the shipped log |
| **`evidence_index` printed `CERTIFIED` above the reasons it did not hold** | `state()` and `problems()` never met | `clean(evidence_dir)` added; the headline refuses the word while problems exist |
| **`nul_paths`' "every enumeration" was false** | `objects_in_outgoing_range` still split on lines | made NUL-safe, and a test now enforces the universal claim |
| **Three D15/D16 branches had no test** | `_ignore_rule`'s `failed` branch, `publication_gate`'s `UNKNOWN` containment, and `index_bijection`'s subdirectories each survived mutation | each pinned |
| **The case-sensitivity claim was wrong** | `os.path.normcase` is OS-dependent, not filesystem-dependent; the test cannot fail on POSIX | claim corrected, and the test renamed as the portability guard it is. It asserts the *reason* it cannot discriminate here rather than skipping, because a skip would make the collected count and the manifest's passing count disagree |
| **Project Context had no integration path** | The contract loader never parsed the block, and `DECLARED` was returned by no code path | parsed at load like every other block; `report_declared` reaches the state |
| **A block scalar on a `- key: |` line was refused** | …with a message telling the author to write what they had written | parsed |
| Minor: anchors mis-parsed, `''` unescaped, trailing pattern whitespace, `\|+` all-blank body, evidence parent modes, an older store stranded, `RefFinding`'s changed positional, `adapters` type, the `ROOT..A..B` range message, vendor attribution from any JSON | each reproduced | each repaired |

### What the audits were wrong about, and why

*   **"The gate record covers 2 of 12 capabilities" and "the CHANGELOG entry has
    no content."** Both true at the audited revision and both already false: the
    C3–C11 sections and the CHANGELOG body landed in the commit after it. An
    artifact of auditing a moving branch, and the coordinator's fault rather
    than the auditors' — they audited exactly the revision they were given.
*   One auditor reported the `13` figure as **honest**, having checked the 13
    recorded pairs (all of which do under-match); the other ran the whole
    shipped grid and found 29. Both measurements are correct. The second is the
    one that matters, because it is the grid the release ships.

### Reductions in coverage this round did not have

*   Neither auditor could verify the status-line payload schema (one was denied
    `strings` on the client binary). The coordinator extracted it from the
    installed client's own documentation block; the artifact is not in the
    release, so the provenance claim remains unfalsifiable from the repository
    alone.
*   Neither could verify the D19 file-count check or the adapter repairs, both
    of which live outside the review surface.

## Closure audit — round 2

Two blind auditors again, fresh context, distinct lenses — *did the repairs
actually repair* and *non-regression plus honesty* — each on its own
coordinator-prepared snapshot at `7faf79f64b671a961fb2245595577b565d566274`,
with the tree frozen for the duration. **Both returned NOT READY.** Between them: 11 blockers, 11 majors,
15 minors. Every material claim was reproduced before it counted.

### The finding that matters most

**A regression.** `fix:` followed by **two** spaces, or by a second Conventional
prefix, let a trailer through the commit gate — and 2.1.1 refused both. The
round-1 repair had replaced "blank the subject line" with "remove the matched
prefix", and left the same hole one space wider: the trailer patterns anchor
with `^`, so anything remaining in front of the token hides it. The repair's own
docstring claimed that mechanism had been understood and avoided.

Reproduced against both toolbelts. Repaired by stripping prefixes exhaustively
and consuming the whitespace each one leaves, which also closes a hole 2.1.1 had
(`docs:  Reviewed-by:`). `Co-authored-by` was never affected — it is matched on
the raw message — so the attribution guarantee held throughout.

**What kind of regression, precisely.** 2.1.1 refused these messages *because
`fix` is in the trailer token set*, not because it detected the trailer after
the prefix — its patterns are `^`-anchored, so it could not see one there and
`feat:  Signed-off-by:` was clean at 2.1.1 too. The **observable guarantee**
regressed: a message the previous release refused, this one accepted. The
**detection capability** did not, because it never existed. Both halves are
worth saying, and the first is the one that matters: a consumer's contract is
what the gate does, not why.

That distinction also cost two attempts at the oracle. A differential against
2.1.1 excused the loss, because 2.1.1 had not detected it either; substituting a
neutral type word and re-asking 2.1.1 excused it for the same reason. The
working oracle asks neither module — it judges independently whether the subject
tail bears a trailer, and calls a lost refusal a regression whenever it does.

### The same defect, a second time

The divergence figure was corrected in round 1 **onto the wrong grid** — the one
that had just been replaced, in the same commit that widened it, where the real
figure is larger and includes over-matches. One auditor put it precisely: this
file had narrated the mistake and then committed it a generation later.

**So the number is no longer written anywhere.** `BASELINE_DIVERGENCES` lives in
`tools/tests/test_pathmatch.py`, a test computes it from the frozen 2.1.1 module
against the shipped grid, and a release-integrity test refuses any prose that
states a divergence count of its own. The grid and the figure now fail together.

### What both auditors concluded independently

> Every number this release binds to a test is correct. Every number it does not
> is stale.

That was exactly right: the manifest's count, digest and file count, the
in-release prose figure, the routing grades, the pin field set and the push form
all reproduced; the gate record's suite count (509, twice), its falsification
count (80), its delta (47/6,251/177) and the packet's prose percentage (22.7%)
were all the previous revision's, freshly written into the repair commit.

Repaired by binding rather than by retyping. `test_the_gate_record_qualification_figures_are_measured`
binds the suite count and the delta; `test_the_release_packet_and_the_manifest_agree_on_the_prose_breach`
binds the percentage; the falsification count is **removed** and replaced with
the method and a reproduction, because nothing in the release computes it.

### The rest

| Finding | Reproduced | Repair |
|---|---|---|
| `tools/pathmatch.py` still asserted the refuted "13, all under-matched" | the round-1 repair corrected two *other* files and never the module the finding was about | corrected, and no prose may carry a count |
| The universal NUL-safety test was blind to the function it was written for | it read only positional string constants, and `objects_in_outgoing_range` builds a list and splats it. Removing the `-z` the repair added left the test passing | widened to list literals, splatted names and `subprocess.run(["git", …])`; falsified in both previously blind shapes |
| `evidence_index` still headlined `CERTIFIED` through its CLI's default path | `--evidence-dir` was optional, so the cited reports and the bijection went unchecked | the flag is required, and `state()` accounts for the directory when given one |
| The packet's first command told the release authority to check the branch out in the pinned root | the exact layout defect D18 records, in the document that records it | verify from a clone, at a root nobody works in |
| The gate record described repairs that were not made: a test "skipped" that deliberately does not skip, an example that "no longer names a real version" when one entry legitimately does, "eleven reproduced defects" when one was enforcement added where no drift existed, "the one deliberately lazy pair" when there are two | each read against the code | each corrected |
| A real machine path shipped in a findings document | `contains_local_path` — this release's own rule — refuses it. Pre-existing at 2.1.1, so not a regression | redacted to `<home>`, the finding untouched, and a test now scans every tracked file. It is the only one in the release |
| `TermSet` accepted an empty declared term; `dist//` over-matched | both by execution | both refused |

### What the auditors could not break

`pathmatch` against real `git check-ignore`: one auditor ran ~41,000
pattern-set/path pairs and found a single degenerate divergence (`dist//`, now
refused); the other ran 143,820 single-pattern pairs and 1,500 generated
negation sets across 145 paths and found **zero**. Between them 21 and 23
injected mutations reverting every claimed repair — **all killed**. The 2.1.1
suite over this implementation: 233 of 237, with all four failures
self-referential release-identity checks. `surface_diff` and an independent AST
walk agree that **no public name was removed and no signature changed**.

And the question the brief asked specifically — does the `pathmatch` rework make
any exemption cover *more* than 2.1.1 did? It covers more in a number of cases, and every
one of them is a case where 2.1.1 disagreed with git and this release agrees. An auditor
reproduced the safety consequence end to end on the same repository: 2.1.1
scanned it `clean`; this release reports three leaks, because an exempted blob
is now read and only the project's own vocabulary is filtered from its findings.


## Closure audit — round 3

Two blind auditors, snapshots at `47b7c677fdf8458f7fac1a276bb658061b0eb5c9`,
lenses *break it* and *is this fit for a release authority*. **Both returned NOT
READY.** Six blockers between them, and again almost no overlap.

### The code held; the account did not, again

One auditor ran **143,820** single-pattern comparisons against real
`git check-ignore` plus 1,500 generated negation sets, the other **111,267** on
a grid the release does not ship. Between them they removed the `-z` from all
ten path enumerations and injected mutations reverting every claimed repair —
all killed. Six of the seven binding tests introduced in round 2 failed under
mutation of what they guard. The digest reproduced from two independent
clean-room implementations.

### What they found

| Finding | Reproduced | Repair |
|---|---|---|
| **The divergence figure was restated a third time** — and a fabricated one shipped green, because the guard written to prevent that could not see the shape it was written in | demonstrated by mutation | **no prose states a count anywhere now.** The guard scans every file this release touched, in every shape a restatement has taken, and prior releases' records are excluded mechanically from the diff rather than by a filename list |
| **The commit gate accepted four more classes 2.1.1 refused** — an invisible character after the prefix, a doubled `!!`, an empty scope `()`, two scope groups `(a)(b)` | all reproduced through both CLIs | the prefix stripper is a **parser, not a pattern** — three regexes each missed a decoration nobody had thought of. Invisible formatting characters are now refused outright *and* removed from the trailer surface, so the message fails and the reader is told which rule |
| **A leading space defeated trailer detection entirely** — pre-existing at 2.1.1, and the test asserting the opposite was named for the universal it did not hold | reproduced | both trailer patterns tolerate leading whitespace; the prefix stripper does too, so an indented Conventional subject still passes |
| **`pathmatch` stripped trailing tabs; git strips only spaces** — and the test pinning it asserted the divergence *while naming git in its own title* | differential | spaces only, and the test now asserts git's answer |
| **`pathmatch` implemented no backslash escapes and read `[^…]` as a literal class** — silently dead declarations, and over-matching in the negated-class case. Both pre-existing at 2.1.1 | differential | escapes and `[^…]` translated for `fnmatch`; both directions now agree with git |
| **The YAML subset returned double-quoted escapes unresolved** — a declared private *pattern* compiled to something matching nothing, so a leak could ship clean. The founding defect of this toolbelt, reintroduced through the parser | reproduced end to end | escapes resolved, unknown ones refused, and an escaped quote inside a double-quoted scalar no longer reads as unterminated |
| **`PACK_MANIFEST.json` still instructed a three-field pin** — the fourth surface, missed by round 1's repair, in the field D18 added | reproduced with `classify_pin` | corrected, and the manifest added to the binding test's file list |
| **The adapter digests were recorded truncated**, so `adapter_pin` refuses them — C2's whole guarantee defeated by the form of its own evidence | reproduced | recorded in full |
| **The packet was written before round 2 and never revisited** — it never said any audit returned NOT READY, nor that a repair had regressed the gate | read against `git log` | rewritten, and it now opens with that history |
| **D14 clause 7 was contradicted by two shipped drills** telling a project to append to `policy/observations.jsonl` — inside the pinned release, inside its digest | read | both corrected; D14 clause 7 states that the pack's log is pack evidence written only in an evolution session |
| The manifest's `deferred` block was a release out of date; a test hardcoded an adapter line count; the machine-path guard exempted two plausible usernames; `resource_observation` exited 0 on an unreadable payload | each read or run | each repaired |

### What this round says about the process

Three rounds, six auditors, and the same shape every time: **the code was hard
to break and the release's account of itself was not.** Every number bound to a
measurement reproduced; every number left in prose was stale or wrong. Three of
the coordinator's own oracles had to be repaired before they could catch the
thing they were written for — a differential that excused the regression because
the baseline had not detected it either, a neutral-substitution variant that
excused it for the same reason, and an ASCII-only tail judge that excused a
non-ASCII variant. Each was found by falsifying it, not by reading it.

**No round has returned READY.** These findings are closed and the suite is
green; no auditor has yet seen the result.

### C12 — qualification and release packet — CLOSED

Three audit rounds, every finding reproduced before repair and every repair
falsified against the behaviour it replaced. The candidate's identity, its
qualification figures, its prose budget, its pin field set, its push form, its
routing grades and its divergence figure are each bound to a measurement rather
than restated. What remains unverifiable from the repository is listed in the
release packet's known limitations rather than left to be discovered.
