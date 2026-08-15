# Runtime Pack 2.0 — pack-level decisions

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
