# HITL preflight — every row, decided before the loop starts

Read against `policy/hitl-matrix.md`. The point is to decide once, so the loop
does not stop repeatedly for questions that were already answerable.

| # | Condition | Tonight |
|---|---|---|
| 1 | Initial project authorization | N/A — the project exists and is authorized |
| 2 | Push, remote, tag, PR, merge, publication, deployment | **FOUNDER ONLY. Isolated.** Nothing tonight does any of these. The freeze is this row; it is deferred and blocks nothing else |
| 3 | Credentials / billing / API-key changes | N/A — subscription auth only, no key stored, no change contemplated. The codex adapter's own §0 forbids it |
| 4 | Destructive / irreversible operations | AVOIDED BY CONSTRUCTION. No history rewrite, no consumer mutation, no deletion of any durable record. The one already-crossed boundary (a commit that briefly carried D26) is left in history rather than rewritten, because rewriting it is this row |
| 5 | Genuine product ambiguity, cross-capability blast radius | None open. If one appears it is recorded and deferred to morning rather than decided |
| 6 | Security decisions / sandbox widening | **NOT TAKEN.** Every dispatch stays `-s read-only`, `--ignore-rules`, network denied, multi-agent disabled. No profile is widened for any reason tonight |
| 7 | Governance waiver / weakening a control | **FOUNDER ONLY. Isolated.** The narrowing is held in `docs/RP2.4-D26-PROPOSED.md`, OUT of the decision layer. Nothing tonight treats it as authorized, and no work depends on it |
| 8 | Repair/audit budget exhausted with an open material finding | **AUTHORIZED FOR TONIGHT** by the governing prompt, which asks for a bounded convergence loop with verification at meaningful boundaries. The stop rule is the prompt's §11, not a counter. An open material finding at the end is still a stop |
| 9 | Accepting a limitation | **NOT TAKEN.** Limitations are RECORDED tonight, never accepted. Recording is not accepting, and the manifest says so of each |
| 10 | Scope insufficiency crossing a capability boundary | None open. Recorded and deferred if it appears |
| 11 | Record-vs-Git divergence | Prevented: every commit tonight is claimed by this record and by the gate record |
| 12 | Mandatory cross-vendor audit unavailable | **LIVE RISK, and addressed rather than deferred.** Both prior readings came from one provider. A blind reader from a different provider is used tonight for the final reading, which is the axis that was missing. If it cannot be obtained, that is this row and it is reported, not substituted |
| 13 | External blockers | Classified environmental and routed on, never retried into the same wall |
| 14 | Licensing / legal | N/A |
| 15 | Budget expansion / wait-vs-spend | **AUTHORIZED FOR TONIGHT** by the governing prompt's own framing. Dispatches stay serial; no fan-out opt-in is enabled |
| 16 | Critical-domain worker promotion | **NOT TAKEN.** No configuration is promoted into a critical domain tonight. Evidence is recorded from real observations and grades follow from it |
| 17 | Unresolved auditor disagreement | Both positions recorded with their evidence; not resolved by the coordinator picking one |

## What this leaves

Exactly two founder decisions, both already isolated, and **neither blocks any
other work tonight**: row 7 (the narrowing) and row 2 (the freeze).

Everything else is either not engaged, avoided by construction, or covered by
the authorization the governing prompt itself carries.
