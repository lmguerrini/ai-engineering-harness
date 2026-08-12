# Cold-continuation drill — protocol

**Frozen before the drill runs.** A recovery test designed after the interruption
grades the coordinator's memory, not the artifacts. This protocol is written
first, and the pass/fail criteria below are not revisable during the drill.

**Applied by:** COORDINATOR, once per project as a scheduled exercise (audit §8),
and as the Wave-B injected exercise.

## What is being tested

Not "can the coordinator continue" — a model with the conversation in context can
always continue. The claim under test is:

> **The durable artifacts alone are sufficient to resume safely, and no hidden
> conversational state is load-bearing.**

## Procedure

1. **Interrupt at a meaningful point.** Not between capabilities, where state is
   trivially clean. The interruption must land mid-capability with at least one
   task committed and at least one task in flight — the state that actually has to
   be reconstructed.
2. **Record the ground truth first, sealed.** Before continuation, the
   interrupting coordinator writes the true current state to
   `evidence/drill-ground-truth.md`: which tasks are done, which is in flight,
   what the next action is, which budgets are consumed, what is uncommitted. This
   file is written **once** and is not read by the continuing context.
3. **Start a genuinely cold context.** A fresh session or an equivalent
   context with no access to the interrupted conversation. It is given only the
   project's private root path and nothing else — no summary, no narration.
4. **Reconstruct, counting reads.** The cold context reads, in order:
   `PROJECT.yaml` → `HANDOFF.md` → active capability's `SCOPE.md` → its
   `PROGRESS.md`, then runs one `git status` + `git log`. It writes what it
   believes the state to be, **before** looking at anything else.
5. **Compare against the sealed ground truth.** Differences are findings.
6. **Resume.** The cold context continues the capability.

## Pass criteria — all four required

| # | Criterion | Fails if |
|---|---|---|
| 1 | **≤ 4 file reads + 1 Git reconciliation** to full state | a fifth file, or a search, was needed to know what to do next |
| 2 | **Reconstruction matches the sealed ground truth** on: tasks done, task in flight, next action, budgets consumed, uncommitted work | any material disagreement |
| 3 | **No replay of hidden conversation state** | resumption required a fact that exists only in the interrupted conversation |
| 4 | **Resume-or-redispatch, never both** | the in-flight task is both resumed and re-dispatched, or its status is left ambiguous |

## The rule the drill enforces

**Reconcile from disk first; distrust summaries.** In the recorded history this
rule caught a stale premise on the very first step of a continuation. A handoff
that reads well but disagrees with `git log` is wrong, and Git wins.

If the drill fails, the failure is a **pack defect, not a coordinator defect**:
the artifacts were insufficient. The repair is to the artifact set — usually
HANDOFF.md's fields — and the drill is re-run. Do not repair by adding prose;
HANDOFF.md is bounded at 200 lines and is REPLACED, never accreted.

## Recording

Result to the capability's `evidence/` via `evidence_put`, one line to
`policy/observations.jsonl`. An interrupted drill is INCOMPLETE, never passed.
