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
| EC-A(ii) | 13 pattern/path pairs disagreed with real `git check-ignore`, **all under-matching** — a wildcard directory name compared by string equality, a bare name not covering the directory it named, and `dist/*` stopping one level down | matching defined once in git's own terms: a pattern matches an entity, and a file is covered when the pattern matches it or any ancestor. `**` implemented; matching made case-sensitive |
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
reported 114 divergences and every one was the harness: `git check-ignore`
consults `core.excludesFile`, and this machine's global ignore file contains
`dist/`, `build/`, `node_modules/` and `*.log`, so the oracle answered for
patterns it had never been given. Isolating it left 13. An oracle answering from
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
| Full local test suite | **509 passed**, 0 failed |
| Release-integrity checks against the real repository | included in the suite; all pass |
| Tree digest, recomputed **independently** | matches: an implementation written from the algorithm's description, not by importing the module under test, produces the manifest's digest over the same file count |
| Clean-clone-equivalent run | a fresh local clone at the exact candidate revision: tree clean, **509 passed**. No remote operation of any kind |
| Pre-repair falsification | the candidate's tests run against **baseline source** fail **80** tests across all nine touched modules, and pass against the candidate. Six new-capability test modules cannot import at baseline, which is expected: they test capability that did not exist |
| Primary-path non-regression | `pack_pin` verifies; `publication_gate` reports the namespace clean over 2 refs; `commit_gate --range` reports every commit message on the branch conforming |
| D3 import closure | **0 violations** across 19 modules, checked by AST walk including function-local imports; every module also imports standalone, so the one deliberately lazy pair forms no cycle |

`workspace_report` exits 1 against the pack itself. That is correct and not a
finding: the pack is not a project, has no contract declaring its
classifications, and the artifacts it names are gitignored OS and cache files.
None is tracked, so none is inside the digest.

## Measured overhead

Held prose, by the `BUDGETS.md` rule:

    in-release (skills/core/*.md + policy/*.md)   1,413
    installed adapters (outside the envelope)       997
    total                                         2,410     target ~2,000

**20.5% over, recorded rather than shaved** — 2.1.1 was 14.9% over on the same
rule. One principled reduction was made rather than a cosmetic one: the routing
table's narrative moved to `docs/`, where read-once evidence belongs, and its
grade rows became computable from the observation log. Trimming further would
have meant deleting live governance to reach a number, which is the pressure
`BUDGETS.md` itself names. The remaining growth is the new governance for five
new Core capabilities.

Delta: 47 files changed, 6,251 insertions, 177 deletions.

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
