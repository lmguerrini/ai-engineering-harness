# RP2.2 — capability map and dependency order

The evolution session's working plan. Written before implementation, from
reproductions rather than from the handoff, and updated only by appending.

Baseline: `2.1.1` at `4495e61850c08027e47eac6d0db84b4b3380e300`, state
`QUALIFIED_AND_FROZEN`, tree digest
`d445c5ce10095edd9a8f6063e9c708f2af7cf1cec266f6758d26f58f7bd50f3e` over 85
tracked files, 237 tests passing. Verified with the shipped `pack_pin.py` and
again with an independent re-implementation of `sha256-framed-v1` written from
the algorithm description rather than by importing the module under test.

## Scope classes

`MUST_THIS_RELEASE` — Gate 0C blockers, reproduced 2.1.1 defects, adapter
integrity, Core migration/update/rollback essentials, the execution backend
truth contract, Execution Resource Truth, and anything the above need in order
to be safely usable by a consuming project.

`SHOULD_THIS_RELEASE` — small, strongly evidenced semantic supersets whose
implementation and qualification cost is low.

`DEFER_WITH_TRIGGER` — everything whose return is not clearly positive in this
session. Each carries the observation that would reopen it.

## Capabilities, in dependency order

| # | Capability | Class | Depends on |
|---|---|---|---|
| C1 | Architecture record | MUST | — |
| C2 | Adapter integrity and pinning | MUST | C1 |
| C3 | Tooling integrity | MUST | C1 |
| C4 | First-party boundary statements | MUST | C1, C2 |
| C5 | Provider internal-surface truthfulness | MUST | C1 |
| C6 | Multi-project migration, update and rollback | MUST | C3 |
| C7 | Project Context contract | MUST | C3, C6 |
| C8 | Execution backend qualification contract | MUST | C1 |
| C9 | Execution Resource Truth | MUST | C5, C8 |
| C10 | Evidence and audit strengthening | SHOULD | C3 |
| C11 | Context-efficiency invariants | SHOULD | C1 |
| C12 | Qualification and release packet | MUST | all |

C3 comes before C6–C7 because the migration and contract work is gated by the
same contract reader and path matcher C3 repairs. Trusting an unrepaired gate
to qualify later work is the failure this ordering exists to avoid.

## Reproduced before repair

Every entry below was reproduced by execution against the frozen baseline
before any repair was written. Reproductions that turned out to be artefacts of
the harness rather than the code are recorded too, because a discarded finding
is evidence about the oracle.

| ID | Defect | Reproduction |
|---|---|---|
| B2 | reviewer isolation contradicts the reviewer contract | a reviewer worktree lands `refs/heads/worktree-agent-*` in the audited repository; `publication_gate.py` exits 1 on it |
| EC-A(i) | path enumeration is not NUL-safe | a tracked `café.txt` reaches classification as `"annotations/caf\303\251.txt"`, and the declared `annotations/` exemption then does not cover it |
| EC-A(ii) | wildcard and directory semantics | divergences against `git check-ignore` in **both** directions on the shipped grid. The count is `BASELINE_DIVERGENCES` in `tools/tests/test_pathmatch.py`, computed against the frozen baseline rather than written down here |
| EC-B | Conventional Commit subject read as a trailer | `fix: …` is refused `TRAILER`; `feat: …` passes |
| EC-C | publication reasoning ignores ref object type | an annotated tag reports "carries no extra object"; a blob ref reports "CARRIES OBJECTS THE PUBLIC REF DOES NOT" as fact when the question was never answered |
| EC-E | evidence is created world-readable | directory `0o755`, file `0o644`, mode verified by nothing |
| CA-AMD-6 | contract reader refuses valid multiline data | `\|`, `>`, `\|-`, `\|+` and multi-line flow sequences all raise |
| RP-EC-3 | an undeclared git exit status renders as an ordinary negative | `is_ancestor`, `config_with_origin` and `_ignore_rule` check `answered` and never `failed`; an unreadable `.git/config` reports as having no settings, `notes.*` included |

`RP-EC-3` was not on the inherited list. It was found by reproducing `EC-C` and
is the root cause beneath it, so `EC-C` is repaired at that layer rather than at
its symptom.

## Oracle notes

**The grid a number is measured on is part of the number — and this was got
wrong three times.** EC-A(ii)'s divergence count was first recorded from a grid
that was then replaced without re-measuring. An audit caught it. The correction
was measured on the *replaced* grid, in the same commit that widened the grid
again. A second audit caught that, observing that this file had narrated the
mistake and then committed it a generation later. A third found the corrected
figure still restated in this very paragraph, and proved it by shipping a
fabricated one green. The measured figure on the shipped grid is `BASELINE_DIVERGENCES` in
`tools/tests/test_pathmatch.py`, and it is not repeated here — a third audit
round demonstrated that a fabricated figure in *this sentence* shipped green,
because the guard written to prevent exactly that could not see this shape.

The repair is not the number. The repair is that no document states it: it is
computed from the frozen baseline against the shipped grid, and the grid and the
figure now fail together. A stated result a reader cannot re-derive from the
artifacts is the defect class this pack exists to refuse, and it took two audits
to stop restating one.

**The oracle has to be isolated.** The first `pathmatch` differential reported
a great many divergences and every one was the harness: `git check-ignore` was
consulting a global `core.excludesFile` containing `dist/`, `build/`,
`node_modules/` and `*.log`, so the oracle answered for patterns it had never
been given. Isolating the oracle left a small fraction of them. Recorded because
the discarded ones are the reason the remaining ones are worth believing.
