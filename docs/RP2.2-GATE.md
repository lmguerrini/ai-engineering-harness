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
