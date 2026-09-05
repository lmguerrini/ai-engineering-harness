# RP2.4 — gate record

What happened, in the order it happened, including what the coordinator got
wrong. Appended to as each capability closes; never rewritten.

**Version `2.4.0`, state `IN_PROGRESS`.** A candidate, not a release. No project
may pin it. Moving it to `QUALIFIED_AND_FROZEN` is a human decision
(`policy/hitl-matrix.md` row 2), and this candidate carries a **second** human
decision besides — a row-7 governance narrowing recorded in `DECISIONS.md` D26.
The freeze procedure is at the end of this file. This release ships no verb that
promotes itself.

## Baseline

    version   2.3.0
    revision  ab7dea97a12c699e8123bcb5d5be976cd05c075e
    digest    389ef7cd5f7fb60f6819f5d5990d0f04259775e76f6f53190c3a96d2037fcbac
    state     QUALIFIED_AND_FROZEN

Verified with the `pack_pin.py` that ships inside 2.3.0 before anything was
created, and re-verified after every environment change this session made —
including the deliberate client update, which is the only change outside this
repository. `evolution/rp2.3` remains on its own worktree, its status clean, its
`HEAD` unmoved. The suite passes at that revision; the figure is the baseline
manifest's own `tests.passed` and is not restated here.

**The evolution workspace is a worktree, for the reason 2.3.0 recorded.** One
live project pins the pack's *working* checkout by root path (D18). That root is
`main` at `2.1.1` and was not touched: this candidate is a separate worktree on
`evolution/rp2.4`, branched from the frozen 2.3.0 commit.

## Session authorisations

| | |
|---|---|
| Repair / audit counters | `policy/BUDGETS.md`, unchanged. No counter was raised |
| Version class | MINOR, **derived before the number was adopted**. The governing prompt proposed 2.4.0; a number adopted because it was suggested is not a derivation, so each clause of `version_semantics` was applied in writing. MAJOR fails on all three tests (no incompatible authority, contract or migration change); PATCH fails because the release ships tools that did not exist |
| Client update | authorised in the governing prompt, Phase 7, and taken deliberately after execution proved it necessary. Recorded below |
| Fan-out | none. Two design readings dispatched serially against one window |

## Qualification

The suite count is not written here — adding a test changes it, and a figure this
document's own edit invalidates is one it must not carry. It lives in
`PACK_MANIFEST.json` `tests.passed`.

    in-release (skills/core/*.md + policy/*.md) 1849
    installed adapters                          1035
    total against a ~2000 target                2884

Delta against the frozen baseline: **not stated here.** Editing this file changes it.
Measure it:

    git diff --shortstat ab7dea97a12c699e8123bcb5d5be976cd05c075e -- .

## The defect, reproduced before a line was written

    python3 - <<'PY'
    import sys; sys.path.insert(0, 'tools')
    import backend_contract as bc
    g = bc.grades_from_observations('policy/observations.jsonl')
    r = bc.record_for('codex-cli', g)
    print(r.qualified_for('blind_closure_audit_cross_vendor'))   # -> True
    PY

`True`, for a model that had never been dispatched, on seven observations none of
which recorded any observed model at all. `policy/routing-policy.md` had said
since 2.1 that evidence is never pooled across distinct configuration strings.
The prose was right, the code keyed on `(family, task_class)`, and nothing
compared them. Everything below follows from that one command.

## Phase 0 — the design, and the two readings that broke it

A design record was frozen against `ab7dea97`, the 2.3.0 release commit, which
contains none of the work it governs. It was then sent, **before any
implementation existed**, to two independent cross-vendor readings on the same
brief and the same revision.

| | reading A | reading B |
|---|---|---|
| observed model | `gpt-6-astra` | `gpt-5.6-terra` |
| observed effort | high | xhigh |
| client | 0.153.3 | 0.153.3 |
| isolation | read-only, network none | read-only, network none |
| verdict | NOT SOUND — 2 blocker, 6 major, 1 minor | NOT SOUND — 2 blocker, 3 major |

They converged on three findings and were otherwise disjoint. **Every factual
claim was reproduced against the shipped log before it was accepted**, and one of
them was a statement the coordinator had made wrongly in the design record: the
confinement ladder was described as eight configurations that all failed
environmentally, and rows 7 and 8 of the log are validated runs. It was corrected
rather than argued with.

What the readings changed, none of it cosmetic:

1. **The alias rule was a laundering path.** Both found it, from opposite
   directions: a reason string transferred a grade to a model nobody had run.
   Removed — an equivalence now surfaces prior evidence and moves no grade.
2. **Independence was being tested on the qualification key**, which is wrong in
   both directions. Reading A produced both: a producer auditing its own work has
   a *different* key once the task class changes, and two genuinely fresh blind
   sessions have an *identical* one — which is exactly what `AUDIT_PRIMARY` is.
   Independence became a property of the producer.
3. **A dimension excluded from the key decides whether a dispatch starts at
   all.** Reading B found rows 37 and 38: one configuration, one differing
   precondition, `dispatch_never_started` against `validated`. Availability
   became a separate axis keyed with its preconditions — which also answered
   reading A's independent complaint that the key was being used as an
   availability gate.
4. **The completeness check did not cover its own named failure mode.** It looked
   for an absent observed model; an adapter that copies the requested slug into
   the observed field and labels the provenance honestly produces a row where the
   field is present. Completeness now requires an admissible provenance.
5. **Discovery membership had been frozen into an oracle as an availability
   gate**, which both readings called out as contradicting the design's own
   stated separation. O5 now asserts both directions.
6. **A configuration contradicted once was contradicted forever**, so a client
   defect since repaired could never be requalified. A governed `Invalidation`
   answers it, capped so it cannot launder.
7. **"No governance control is weakened" was false**, and reading A falsified it
   against `policy/hitl-matrix.md`. Withdrawn; the narrowing is named and carried
   into the freeze procedure below as row 7.
8. **The thirteen oracles were not discriminating.** Both readings produced
   implementations that would do the wrong thing and pass. All thirteen were
   rewritten: per-dimension collision fixtures, one mutation per keyed dimension,
   and a fixture-adequacy assertion in the mutation test itself, so a case whose
   values make the mutant observationally equivalent fails as a bad fixture
   rather than passing as evidence.

Revision 2 of the record was frozen against the same base and committed before
the first line of implementation.

## Phase 6/7 — the live adoption, and what it actually established

**Discovery is client-version-dependent, measured rather than argued.** The local
discovery document listed `gpt-6-astra` when this session began, written by
client `0.153.1`. The installed client was `0.149.0`. The smallest possible probe
— *reply with one word* — was refused by the provider:

    HTTP 400 invalid_request_error: the 'gpt-6-astra' model requires a newer
    version of Codex

and the failed run rewrote the document, which then listed **eight** models with
that one absent. Same account, same minute, two client versions, two catalogues.
Three rules came out of that single observation: a reading carries its producer;
inspection does not refresh a document, a dispatch does; and discovery is never
availability.

**The client was then updated deliberately**, which is the only change this
session made outside this repository. `0.149.0 -> 0.153.3`, subscription auth
re-verified, no API key, write probe re-run. The probe was repeated and returned
`READY`, exit 0.

**Observed identity was read from the execution surface, never from the worker.**

    model  gpt-6-astra    effort  low    sandbox  read-only    client  0.153.3

One reading reported honestly that it could not observe its own identity. **The
other reported its own model as a different generation than the one that ran** —
its observed identity is `gpt-5.6-terra` and it said `GPT-5`. Nothing in this
release rests on a worker's self-report, and that is why.

**What Astra's evidence actually is, and what it is not.** Two observations, two
task classes, `provisional` at each:

    surface=codex-cli family=codex-cli client=codex-exec model_observed=gpt-6-astra
    auth=subscription isolation=read-only network=none
      effort=low   model_usability_probe        provisional  (1 validated)
      effort=high  design_falsification_review  provisional  (1 validated)

It is `unprobed` at every other task class and at every other effort, including
`blind_closure_audit_cross_vendor`, where the family-keyed derivation returns
`confirmed` on seven observations. That family row is reported beside the
`unprobed` answer and labelled advisory. **Astra is not CONFIRMED anywhere.**

Its advertised context window is 272,000 with a stated maximum of 872,000; the
execution surface reports a window *identifier* rather than a size, so the
observed limit is `UNKNOWN` and the advertised figure is recorded as advertised.
Supported efforts as advertised: low, medium, high, xhigh, max, ultra — `ultra`
remains banned outright, because on this surface it enables the vendor's own
internal task delegation.

**Compared against the strongest alternative on the same task.** Both readings
found real, reproduced defects; their findings were partly disjoint; reading A
found more and reading B found the one that most changed the design. On this
single comparison neither dominates, and **one dispatch each is not a rate**. The
honest conclusion is that both are `provisional` at this task class and that a
generation number established nothing.

**Provider correlation, stated because it bounds the result.** Both readings came
from one provider through one client. They are independent of the coordinator
that wrote the design and independent of each other's session, and they are not
independent of each other's provider. `routing.independence_problems` refuses
exactly this pairing for a leg declared cross-provider.

## The adapter, and the table that had already aged

The installed adapter carried a **static table of four model slugs with their
efforts and context windows**. By the time this session read it, the table was
wrong in the way that matters: it did not contain the model the provider was
offering, and its efforts column for two of the four entries no longer matched
what the surface advertised. A table nobody consults is harmless; this one is
consulted before every dispatch.

Two changes, both in the direction of *less* authority:

*   **The table is gone.** Section 2 of the adapter now says there is no table,
    says why, and gives the command that reads the surface. Worker names stay
    role labels; which slug fills one is read at dispatch, never recalled.
*   **The caveats became measurements.** "The cache may have been written by a
    different CLI version" is now followed by what happened when it was.

The adapter remains **outside this release envelope**, covered by no digest and
changeable without a pin noticing (D12, D14). What this release can do about that
is exactly what `tools/adapter_pin.py` already does — verify what a project
declares — and that is unchanged. The edit is recorded here because it happened
on this machine during this session and a reader comparing the adapter to the
2.3.0 gate record would otherwise find an undocumented difference.

**Client version:** `0.149.0 -> 0.153.3`, deliberately, after execution proved
`0.149.0` could not run the model under evaluation. Subscription auth re-verified
after the update; no API key stored; write probe re-run and passing. Old routes
were not re-probed on the new client and their availability is therefore
**UNKNOWN on `0.153.3`** — the evidence for them was recorded on `0.149.0` and
`availability_for` reports exactly that rather than carrying it across. That is a
real cost of the update and it is stated rather than papered over.

## The vendor continuation surfaces, inventoried and kept non-authoritative

Present and stable on the installed client: `resume`, `fork`, `queue`,
`archive`, and a goals store. `codex exec` additionally takes `resume` and
`fork` subcommands and a thread-source classification.

`policy/execution-boundaries.md` boundaries 2 and 3 already govern these and are
unchanged: vendor context, memory and task stores are **subordinate to project
durable records**, and an experimental orchestration surface is not a dependency
— the test being whether the capability still closes with the surface absent.

This release makes that testable rather than merely stated:

*   `test_15_the_capability_closes_with_no_vendor_continuation_state_at_all`
    deletes the entire vendor state and reconstructs the position from the
    durable record alone. The derived state is `SILENT_IDLE` — the pack's own
    word for *work is owed now* — which is exactly the position a coordinator
    resumes into, and it was reached with no vendor artifact in existence.
*   `test_16_vendor_continuation_contradicting_the_durable_record_loses` writes a
    vendor thread claiming the capability is complete against a record that says
    it is not. The durable record wins, and a second assertion establishes that
    **no module in the toolbelt reads that file at all** — the strongest form of
    "non-authoritative" available: not consulted and overruled, but not
    consulted.

No experimental memory feature was enabled. None was needed, and enabling one
because it exists is the move boundary 3 exists to refuse.

## Phase 13 — the qualification run

Recorded as each suite completes; see the sections that follow.

## The freeze procedure

Two human decisions, not one, and neither is the coordinator's:

1. **HITL row 7 — the governance narrowing (`DECISIONS.md` D26).**
   `policy/routing-policy.md` says evidence is never pooled across distinct
   configuration strings. This release pools across two named non-identity
   fields — the client build and the capacity pool — while widening the key from
   one dimension to nine. Net tightening is still a change to a control. The
   founder authorises the narrowing, or the two fields move into the key and the
   candidate is re-qualified.
2. **HITL row 2 — the state transition.** With row 7 authorised, and with this
   gate record's checks green:

       # 1. the baseline is untouched
       cd <2.3.0 root> && git status --porcelain          # empty
       python3 tools/pack_pin.py . --version 2.3.0 \
           --sha ab7dea97a12c699e8123bcb5d5be976cd05c075e \
           --digest 389ef7cd5f7fb60f6819f5d5990d0f04259775e76f6f53190c3a96d2037fcbac \
           --state QUALIFIED_AND_FROZEN

       # 2. the candidate qualifies
       cd <2.4.0 root> && python3 -m pytest tools/tests/ -q

       # 3. set PACK_MANIFEST.json "state" to QUALIFIED_AND_FROZEN, and
       #    "qualified_at" to the date, then recompute the digest:
       python3 tools/pack_pin.py . --write          # recomputes tree_digest_sha256
       python3 -m pytest tools/tests/ -q            # the digest guards re-run

       # 4. commit, and record the revision. The manifest cannot name the commit
       #    that contains it; the consuming project's pin does.

No push, no tag, no remote, no consumer migration. Those are row 2 as well and
are separate decisions taken separately.
