# Core Skills

Reusable semantic policy: what a coordinator should *think about*, in a form that
survives being read cold by a coordinator who was not here.

    coordinator judgement
    + skills — semantic policy        <- this directory
    + durable context (files + Git)   <- the record: PROJECT.yaml, HANDOFF.md,
                                         SCOPE.md, PROGRESS.md, FINDINGS.md,
                                         DECISIONS.md
    + toolbelt (stateless checkers)   <- report and refuse; never hold state

There is no deterministic authority layer beneath these skills. Files and Git are
the record, the coordinator maintains them, the toolbelt checks and reports. **No
component may both hold state and adjudicate it.**

Two rules keep the layers apart:

*   **Nothing here substitutes for a mechanical check.** A rule that can be
    checked deterministically belongs in the toolbelt; this directory references
    it, never restates it — a restatement drifts.
*   **Nothing here names a model, a vendor or a product.** Public-safe by
    construction. Skills describe **roles** — a premium auditor, a cheap
    implementer, a scarce specialist — so the policy survives a change of
    supplier, which is also the only form in which it is honestly reusable.
    Operational policy that must name a configuration lives in `policy/`.

| Skill | The judgement it is about |
|---|---|
| `requirement-interpretation.md` | Turning what somebody asked for into what must be true |
| `decomposition.md` | Capability and task boundaries, and why they are drawn there |
| `delegation.md` | Which work to hand to another worker, and what to send with it |
| `evidence.md` | Reading evidence, and what each kind can and cannot support |
| `repair.md` | Fixing something without breaking its neighbour |
| `failure-classification.md` | Which layer a lesson belongs to |
| `convergence.md` | Knowing when to stop, and what to do at the bound |
| `audit-strategy.md` | Getting a review worth having |
| `human-decisions.md` | What a human must decide, and what must never be inferred |
| `public-safety.md` | Habits that keep a repository publishable by construction |
| `oracle-discipline.md` | Deriving an oracle's domain from the mechanism, and proving it reaches it |
| `continuation.md` | Reconciling from disk, never from a summary, and handing off cleanly |
| `worker-contract.md` | The dispatch envelope, and why a report is a claim until re-run |

**Held prose.** `skills/core/*.md` + `policy/*.md` are loaded every session and
count against the pack's 2,000-line ceiling together with the two installed
operational skills (`policy/BUDGETS.md`). `templates/` and worked examples are
pulled on demand and excluded. On breach: delete before adding.
