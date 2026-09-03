# Re-falsification map — every mandated recurrence class, and the oracle that proves it

A closure matrix says a mechanism is handled. This says **which executable check
would go red if it stopped being handled**, and it was produced by running every
one of them rather than by reading the code and agreeing with it.

The rule this document exists to enforce: *where a class is already closed, do
not rewrite it for reassurance — prove closure using its existing oracle.* Every
row below was executed. No row is asserted.

**A class with no executing oracle is the finding this table is for.** There are
none. Finding that out took three corrections to the table itself: three filters
selected nothing and reported green **by selecting nothing**, which is the same
vacuous-pass shape this release has now found six times in its own tests. A
selector that matches no test is a passing command and an empty claim, and the
run counts every row's tests for exactly that reason.

**The check is mechanical now.** `policy/recurrence-classes.json` is this
table's machine-readable twin and `tools/tests/test_recurrence_classes.py` runs
it: every class must select at least one real test, and a test asserts the two
copies of the list hold the same classes so the prose and the data cannot drift.

That the selected tests *pass* is established by the suite, which runs them.
Asserting it here as well took the suite from under three minutes to over six,
and made two classes fail whenever the release pin was mid-edit — a check nobody
can afford to run is a check somebody turns off.

| Recurrence class | Oracle |
|---|---|
| ACTIONABLE_WORK + SILENT_IDLE | `test_silent_idle_closure.py` (21) |
| summary emitted while authorised work exists | `test_continuation.py`, `test_silent_idle_closure.py` `-k "idle or ready_rather"` (22) |
| completed worker/auditor result not consumed | `test_continuation.py -k consum` |
| stale / orphaned / superseded waiter | `test_progress.py -k "waiter or retire"` |
| stale / orphaned / superseded worker | `test_silent_idle_closure.py -k "two_live_waits or retiring_the_first"` |
| false RUNNING from process existence | `test_progress.py -k "flat or single"` |
| false RUNNING from measuring the sample interval | `test_progress.py -k "horizon or flat_since"` |
| wait without a bounded deadline | `test_silent_idle_closure.py -k "deadline or expiry or unbounded"` |
| waiter whose condition can never wake the coordinator | `test_progress.py -k waiter` |
| stdin/EOF lifecycle hanging a worker | *no oracle is possible in-tree — see below* |
| context exhaustion / compaction / fresh session | `test_continuation_rehearsal.py` (7, reconstruction in a separate process) |
| durable state losing capability/wait/result/budget/blocker/identity/next action | `test_continuation_rehearsal.py::test_step_3...` |
| scoped HITL blocking unrelated authorised work | `test_silent_idle_closure.py -k scoped`, `test_continuation.py -k block` |
| provider quota / reset / capacity exhaustion | `test_capacity.py` (31) |
| telemetry UNKNOWN converted into guessed capacity | `test_capacity.py -k unknown` |
| insufficient coordinator / result / audit reserve | `test_capacity.py -k reserve` |
| duplicate dispatch, duplicate retry | `test_silent_idle_closure.py`, `test_continuation_rehearsal.py -k "two_live_waits or second_worker"` |
| partial durable output ignored before retry | `test_task_output.py -k "partial or resume"` |
| atomic output failure before materialisation | `test_task_output.py -k "atomic or part or rename"` |
| task result consumed by the wrong task | `test_task_output.py -k owner` |
| completed-but-not-consumed output | `test_continuation.py -k consum` |
| gate failure hidden by a pipeline or lost exit code | `test_commit_gate.py` (82) |
| oracle satisfied for a reason other than its claim | `test_pack_pin.py -k digest`, and the mutation pass |
| vacuous mutation test / test iterating the mutated constant | `test_gitread.py -k re_enables`, plus two mutation passes over 25 guards |
| self-derived golden, stale verifier | `test_release_integrity.py` (52) |
| audit evidence about revision A accepted for revision B | `test_close_attestation.py -k tree` |
| audit report not identifying the revision it read | the brief requires it; rounds 4, 5 and 6 complied |
| transcribed counts drifting from computable facts | `test_release_integrity.py -k "count or routing"` |
| substring-based semantic comparison | `test_close_attestation.py -k "exact or premise"` |
| non-finite values bypassing guards | `test_capacity.py`, `test_progress.py -k "finite or horizon or measurable"` — the signals, then the horizon, then the moment: three fields, three rounds |
| constructor bypassing the loader's validation | `test_history_anchor.py`, `test_close_attestation.py -k "shape or loader or declared"` |
| project contract / schema drift | `test_project_contract.py` (48) |
| real-consumer incompatibility | `test_consumer_compatibility.py` (62) |
| adapter executable drift | `test_adapter_pin.py` (31) |
| backend / model qualification drift | `test_backend_contract.py` (44) |
| read-only Git acquiring write authority | `test_gitread.py -k "write or verb or byte_identical"` |
| read-only Git executing repository-configured programs | `test_gitread.py -k "program or filter or submodule or proxy or closure"` — five routes, then a check on the shape of the config key |
| a repository disabling the check that inspects it | `test_gitread.py -k "breaking_its_own or re_enter"` |
| read-only operation gaining network authority | `test_gitread.py -k "transport or remote"` |
| scanner skipping unreadable objects | `test_publication_history.py -k "scanned or incomplete"` |
| shared object/path enumeration incomplete | `test_publication_history.py -k "sharing or alias or exempt or history_too"` |
| current-tree safety mistaken for complete-history safety | `test_publication_history.py` (28) |
| publication ceremony leaking into private projects | `test_publication_history.py -k "obligation or profile"` |
| disclosure broader than reproducible evidence | `test_publication_history.py -k profile` |
| anchor green after evidence is destroyed | `test_history_anchor.py -k "destroy or prune"` |
| closure anchor unreachable | `test_history_anchor.py -k "anchor or bundle"` |
| remote verification weakened by hardening | `test_gitread.py -k transport` |
| stale refs / rewrite refs creating false publication state | `test_publication_gate.py` (68) |
| projection becoming authority | `test_projection.py` (14) |

## The one class no in-tree oracle can hold

**stdin/EOF lifecycle hanging a worker.** The mechanism lives in a third-party
executable and its host process, not in this pack, and a test asserting *`codex
exec` reads standard input* would pin somebody else's behaviour and go red the
day they change it.

What is testable is the property that made the cause irrelevant: **every
observable wait carries a deadline**, so a dispatch that never starts costs the
deadline rather than the afternoon. That is
`test_silent_idle_closure.py -k "deadline or expiry"`, and it is the row above.

The cause is recorded where a cause belongs — `policy/observations.jsonl` as an
`environmental_failure` row, and `docs/ROUTING-TABLE-HISTORY.md` — with the fact
that attributing those two hangs to the route would have been wrong. **A
deadline is the mechanism; the cause is evidence.** Confusing the two is how a
routing table learns a false fact about somebody else's software.
