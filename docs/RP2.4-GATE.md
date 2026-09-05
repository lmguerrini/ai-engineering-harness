# RP2.4 — gate record

What happened, in the order it happened, including what the coordinator got
wrong. Appended to as each capability closes; never rewritten.

**Version `2.4.0`, state `IN_PROGRESS`.** A candidate, not a release. No project
may pin it. Moving it to `QUALIFIED_AND_FROZEN` is a human decision
(`policy/hitl-matrix.md` row 2), and this candidate carries a **second** human
decision besides — a row-7 governance narrowing, held OUT of the decision layer
in `docs/RP2.4-D26-PROPOSED.md` until it is authorised.
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

    in-release (skills/core/*.md + policy/*.md) 1896
    installed adapters                          1035
    total against a ~2000 target                2931

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

**The deterministic suite.** `python3 -m pytest tools/tests/ -q`. The count is
`PACK_MANIFEST.json` `tests.passed`, written by the collection the check re-runs,
and is not restated here.

**The design gate, against the real first-implementation commit.** The record is
frozen at `ab7dea97`, the 2.3.0 release commit; mutation began at `a01480f`.
Run with `--mutation-begins-at a01480f` the record reports `DESIGN FROZEN`; run
with `--mutation-begins-at ab7dea97` — the base itself — it reports

    the base revision is the revision at which mutation began, so the design was
    frozen against a tree that already contains the work it governs

so the binding is demonstrated to bite rather than merely to pass.

**The dashboard, in a real browser.** Served over loopback and read through a
browser rather than through the renderer's own test: the routing panel shows
`3 configuration(s), 18 prior(s)`, the per-configuration grades, the discovered
identifiers each marked `DISCOVERED only`, the pack state `IN_PROGRESS` and the
line `NO — only QUALIFIED_AND_FROZEN may be pinned by a project`. No console
errors. Every unanswerable field rendered `UNKNOWN`.

**The real consumers, read-only.** Four `PROJECT.yaml` contracts on this machine,
hashed before and after the session: **none changed**. The pinned working
checkout one of them names by root path is still on its pinned revision, its tree
clean, and it re-verifies against its own manifest with the release's own
`pack_pin.py`.

**The frozen baseline.** Re-verified at every checkpoint, including after the
client update — the only change this session made outside this repository.

**The complete reachable history, scanned with the capability this pack ships.**

    python3 tools/publication_history.py . --project <contract inheriting pack defaults>

    complete reachable history [strict]: 4705 occurrence(s) to adjudicate
                                         (4 refs, 1892 objects)
    rules applied: 35 term(s), 15 identity-only, 7 pattern(s), 1 identity-only

**They are now ADJUDICATED**, in `docs/RP2.4-PUBLICATION-ADJUDICATION.md`,
which resolves each finding class to the text behind it rather than counting it:
at the tier a governed project runs, every occurrence is a home-relative form, a
fixture path, a template placeholder or a synthetic identifier, and every
credential-shaped token is a negative fixture in a test that exists to prove the
scanner finds that shape. At the strict tier the dominant classes are this
pack's own governance words appearing in its own documentation. The counts
themselves are not restated here — the tool prints both, and a count restated in
two places goes stale in one.

Three things a reader should not misread here. The figure is **not** comparable
to 2.3.0's 2090: this history has 1892 objects against 1179, and the generation
pattern this release adds matches more than the literal it replaced — which is
the point of it. The credential-shaped tokens are in the scanner's **own negative
test fixtures**, which is the case `skills/core/public-safety.md` describes when
it says a project whose product is a harness cannot scan its own source for
harness vocabulary. And a scan run with **no** vocabulary returns 375, which is
the same history read through the built-in rules alone — the asymmetry the mode
announcement exists for.

Adjudication is owed before any first remote and is recorded as owed, not as
done. A private remote does not resolve it.

## The release-authority reading, and the four things it found

A blind cross-vendor release-authority read of the candidate at
`a0b6d1d9b5f67b2180dbebb7ee4c0fc058df9140`, read-only, network none. It opened
with the revision and the digest it read, which is why nothing below had to be
re-executed to learn which tree it meant. **NOT READY — four blockers.**

**Finding 1 was mine, not the release's, and it is the more useful of the two
kinds.** The report says the candidate's manifest digest does not match the tree.
It does not: `a0b6d1d` verifies cleanly in a fresh worktree, and so does the
revision after it. What happened is that **HEAD moved under a running audit** —
the coordinator committed a second time while the reading was in flight — so the
auditor compared the earlier manifest against the later tree. The auditor said so
explicitly and kept its scope. This is the stale-evidence failure the previous
release spent a round closing from the auditor's side, reproduced here from the
coordinator's, and the rule that follows is the coordinator's to keep: **do not
move HEAD while a reading of it is running.**

The other three are real, were reproduced by execution before any repair, and are
each closed with an oracle that fails against the pre-repair behaviour.

**A provenance saying `unobserved` reached `confirmed`.** The denylist held
`not_observed` and not `unobserved` — two spellings of one claim, and an
exact-string list is the wrong shape for a claim about meaning. Reproduced: a
complete identity carrying `unobserved` graded `confirmed` on two observations.
Repaired by comparing the provenance **by its word** — case and separators
removed before the comparison — and widening the set. The oracle is
parametrised over twenty spellings, and a second one asserts that a method naming
a surface nobody has heard of is still admissible, because an allowlist of
surfaces would age exactly the way the model vocabulary this release replaced
aged.

**A declared probe filled the mandatory cross-provider leg.** `INDEPENDENT_
FALSIFIER` requires a distinct provider, which makes it the leg
`policy/hitl-matrix.md` row 12 governs; it carried `purpose=ROUTINE`, and the
probe fallback keyed on the purpose alone. Reproduced: an unprobed configuration
was seated in it and the route reported itself **complete**. Repaired by deriving
probeability from what the seat requires rather than from a flag somebody has to
remember to set — a seat needing an independent provider does not accept a probe,
and neither does a critical one.

**And the adoption rehearsal expected the defect.** That is the sharper half of
the same finding, and the auditor named it: the rehearsal asserted
`routed.complete`, so it encoded the bug it was there to catch. A rehearsal that
encodes the bug is worse than no rehearsal. It now asserts the true arc — the
ordinary seats fill by probe, the mandatory leg does not, the route is
**incomplete**, and the capability escalates to a human rather than substituting.

**A blank producer established independence.** `" "` is not the `UNKNOWN`
sentinel, so it compared unequal to every real producer and satisfied every
check. Reproduced: a derivation with whitespace producer and provider passed a
leg declared cross-provider with zero problems. Repaired at the reader **and** at
the predicate, because a check that trusts its inputs to have been cleaned is one
that will eventually be handed an input that was not.

**The mutation pass.** Each repair was reverted in place and the suite re-run:

    KILLED  compare provenance as an exact string again      11 failed
    KILLED  let a probe fill any non-CRITICAL seat again       2 failed
    KILLED  stop normalising a blank producer                  1 failed

**What the reading could not do, in its own words.** It could not run the suite —
the read-only sandbox gives pytest no usable temporary directory — and it could
not mutate files to check the guards, so it executed the candidate's sources in
memory instead. Its coverage of the suite is therefore *collection* and reasoning
rather than execution, which is a real bound on what this round establishes.

**These repairs are themselves unaudited** until a delta re-audit, which is the
standing condition of any final repair and is why the closure ceiling is stated
rather than reached.

## The second release-authority reading, and the thirteen things it found

The same brief, the same revision, a second reader on the same surface at a
higher effort. **NOT READY — three blockers, seven majors, three minors**, and
almost none of them the same as the first reading's. That divergence is the
finding about the method rather than about the release: two readings of one
candidate, converging on almost nothing, both correct.

It opened with the revision and the digest and reproduced the digest
independently over 165 files. It then said plainly that **HEAD moved under it**
and that it had kept scope — the same coordinator error the first reading
surfaced, observed twice.

**The one that matters most: the defect this release exists for was still
reachable through the API a consumer calls.**

    record_for("codex-cli", grades_from_observations(log),
               identity=BackendIdentity(family="codex-cli",
                                        model_requested="never-dispatched"))
        .qualified_for("blind_closure_audit_cross_vendor")   ->  True

A correct derivation had been added *beside* the old one, and the old one still
answered. `BackendRecord.qualified_for` now requires an observed identity as well
as a grade; `grade_for` is untouched, so nothing that reads history loses
anything. **A repair with no oracle is a claim**: this one initially survived its
own mutant, which is how the missing test was found.

**An identifier containing a space transferred its evidence to its prefix.** The
configuration string is space-separated `key=value`, so two validated
observations of `MODEL WITH SPACES` were readable as `confirmed` for `MODEL` — a
configuration nothing had dispatched. The parser now refuses an ambiguous string
outright, and a structured `identity:` mapping carries what the string cannot.

**A grade measured at one task class satisfied a critical leg at another.** The
router compared the candidate's declared class to the requested one and never to
the class its own evidence was measured at.

**Availability crossed client builds, two ways.** The build defaulted from the
caller's argument alone while the identity carried one, and an observation with
an unknown build matched every build. Both now refuse.

**Independence was checked against the subject and never against the reader
already seated**, so two readers from one provider filled a cross-provider route
that reported itself complete — and seats were deduplicated by MODEL NAME, which
is wrong in both directions: two readings by one producer in one session were
seated because their models differed, and two genuinely independent sessions
were refused because their model was the same. Seats are now producer-and-session
and every candidate is checked against the readers already seated.

**The new publication pattern fired on ordinary English.** `I started using
ChatGPT 2 years ago` matched, because the pattern allowed a space as a separator.
That is precisely the false-positive class `policy/private-terms.default.json`'s
own tiering rationale was written about. The space is gone; the cost is the prose
form `GPT 6`, and the sentence is now in the negative corpus.

**An unorderable client version ordered anyway.** `_version_tuple("1.nightly")`
returned the prefix it had accumulated, so an invalidation dropped a contradiction
recorded at a build nothing could place — while the function's own docstring said
an unorderable version is never treated as older.

**And three findings were about the tests rather than the code**, which is the
class this release most needed to hear:

*   **The adoption rehearsal reported success while every capability open was
    refused.** All six synthetic consumers returned `NOT_READY` with a `LEGACY`
    pin, and the tests passed because they inspected one component. The
    rehearsal now builds a real verifiable frozen release — a git checkout whose
    manifest digest is computed over its own tracked tree — and asserts
    `report.ready`.
*   **The advisory-prior oracle passed against a sort that reads the prior.** It
    asserted `_rank` equality and then only that *somebody* was selected. It now
    asserts the selected candidate is unchanged when the prior is removed and
    when it is made louder, in both candidate orders.
*   **The two vendor-continuation tests never shared a surface**, so a `derive`
    that read vendor state was invisible to both. They now derive before and
    after removal on one surface and compare, instead of asserting that no module
    mentions a filename.
*   **The dimension oracles took their coverage from the implementation.**
    Dropping `client` from `CONFIGURATION_DIMENSIONS` deleted three of its own
    tests from collection and the rest passed. The nine-dimension contract is
    now written out in the test file and compared, because a test that derives
    its expectation from its subject is not evidence.

**The mutation pass over this round**, each guard reverted in place:

    KILLED  let an unobserved identity qualify again
    KILLED  parse an ambiguous configuration string anyway
    KILLED  check independence against the subject only
    KILLED  deduplicate seats by model name again
    KILLED  stop comparing the grade's task class
    KILLED  let an unknown build match any client
    KILLED  order a partially parsed version again
    KILLED  allow a space in the generation separator again
    KILLED  sort the route by the family prior
    KILLED  drop a dimension from the key

**The governance finding, which is the one this release cannot repair by
editing.** The reader checked D26 against `policy/hitl-matrix.md` and found the
sequencing wrong: row 7's application point is *before any entry lands in the
pack's `DECISIONS.md`*, and the entry had landed, declaring the narrowing decided
and the authorisation due at freeze. Correctly naming row 7 inside the entry does
not make writing it compliant, and a later freeze cannot make an earlier sequence
compliant retroactively. **The entry was removed from the decision layer** and is
held as `docs/RP2.4-D26-PROPOSED.md`; every pointer at it now names the proposal.
The commit that briefly carried it is in this branch's history and is named here,
because rewriting that history is itself rows 2 and 4.

**What this reading could not do, in its own words.** It could not execute the
suite — the read-only sandbox gives pytest no usable temporary directory — so it
collected the suite and ran the candidate's sources in memory. It did not
reproduce the live client experiments or the publication-history scan. Its
verdict rests on reasoning and targeted execution, not on a suite run.

**These repairs are themselves unaudited.** That is the standing condition of any
final repair, and it is why the closure ceiling is stated rather than reached.

## The overnight convergence pass, and the two failure classes it closed

### The composition pass

Seventeen combinations attacked, each individually correct. Fourteen behaved.
Two did not, and both were repaired design-first with mutants that die:

**A key stated twice resolved silently to one of its values.** The configuration
string is space-separated `key=value` and the parser builds a mapping, so
appending `model_observed=` to a string that already carried one changed which
configuration the observation was filed under, in silence — the whitespace
truncation again, by better punctuation. Refused now, the same way, and refused
even when both values agree: a writer that emits a key twice is defective either
way, and a rule that tolerates the harmless case has to decide which case it is.

**A wait could not say what configuration its dispatch was running on.** Found
by attacking model identity against continuation rather than either alone. The
only thing naming a still-running dispatch was the provider's own rollout file
— so with the vendor state removed, as this release's own invariant requires, an
interrupted dispatch's observation could only be recorded with an UNKNOWN
identity, which makes it prior evidence and loses it. `Wait.configuration` now
carries the structured identity, and a fresh process reading only the record
gets it back.

### The waiting path, closed structurally

Three monitors this session ran survived roughly an hour against producers that
had exited and whose results had already been read. Each was of the shape

    while pgrep -qf "pytest tools/tests"; do sleep 20; done

and `pgrep -f` matches a whole command line — **including the waiter's own**,
which contains the pattern it searches for. Each loop matched itself.

The first reading of that was *the coordinator made a mistake*. The second, and
the correct one, is that **the pack held two answers to one question**:
`progress.waiter_command` treated a zombie as ended and said so in its docstring,
while `continuation._process_is_gone` asked `os.kill(pid, 0)`, which succeeds for
a zombie — so the DURABLE STATE MODEL reported a finished producer as running
forever. Reproduced against a real unreaped child before anything was changed.
That is a release defect, not a session mistake, and the design record for it is
`docs/RP2.4-DESIGN-C47-governed-background-work.md`, frozen against `215a537`
before implementation.

What ships:

*   **One liveness answer** — `progress.process_has_ended`, which `continuation`
    delegates to, so the two cannot drift apart again.
*   **The waiter belongs to the wait**, and one that matches a command line is
    refused *where the wait is declared*, not reported afterwards. Refused as a
    class: `pgrep`, `pkill`, `ps | grep`, whatever the pattern.
*   **`continuation.reconcile`** derives eight dispositions from the record and
    the process table. **A monitor is not an input.**
*   **`UNGOVERNED_BACKGROUND_WORK`** names a declared wait with no waiter, so a
    reader is shown the gap rather than an empty list.
*   A dashboard panel deriving from the reconciliation, and a cold
    reconstruction that reaches the same dispositions from disk alone.

**What is NOT closed, and is not claimed to be:** a coordinator can still wait in
a shell and record nothing. Acquiring the power to see that would mean policing
the coordinator's own shell, which is what this pack refuses to become.

### The zero-test false green

A targeted run exited in 0.56 seconds and was nearly recorded as a
forty-five-fold speed-up over the same guard's 25.7 seconds. It had selected
**zero** tests: the selector said `never_prints` and the test is called
`ever_prints`. **Exit status is not evidence that a check ran.**

`tools/selector_evidence.py` records the intended selector, the collected,
executed, skipped and deselected counts and the exit status, and answers
`NOT_EVIDENCE` below what the caller expected — with the expectation an argument
rather than something read back out of the result. It binds performance work
hardest: two runs are comparable only over the same test population, and the
rule is enforced against this session's own near-miss as a fixture. The release's
own matrix guard now speaks this vocabulary instead of grepping stdout for `::`.

### Three ill-formed mutants, recorded because they nearly counted

A mutant that the subject does not read is not a mutant, and tonight produced
three: a matrix row edited in a cell the guard never parses; a CLI wrapper
removed from a tool that already handled the inputs itself; and a `-k` selector
that matched nothing. Each first read as *the guard is weak*. Each was the
measurement being wrong. The same rule as fixtures, one level up — **a mutant
whose subject never sees it is not evidence** — and the third is the reason the
selector tool exists.

### Verification cost, and a claim this release's own rule refuses

Two subprocess fan-outs were a third of the suite: the oracle-selector guard and
the CLI refusal guard, both spending their time in interpreter startup rather
than in anything they verify. Both now run concurrently over the same commands
with the same assertions — nothing about what is checked changed, only when the
processes run — and both were mutation-tested afterwards with well-formed
mutants to prove no detection was lost.

**The whole-suite figure this section used to state is WITHDRAWN.** It claimed a
speed-up *over an identical test population*, and it was refused by this
release's own `selector_evidence.comparison_problems`, which requires two runs to
have the same population before they may be compared. Both sides were then
measured properly, and **they are not comparable**: the delta adds tests, so the
populations differ, and a comparison over different populations is exactly what
this release now refuses of anybody else.

Measure it rather than read it — and note that neither figure may be written
here, for the same reason the suite count is not:

    git worktree add --detach <somewhere> 215a537 && \
        cd <somewhere> && python3 -m pytest tools/tests/ -q     # the before
    python3 -m pytest tools/tests/ -q                           # the candidate

An independent reader pointed out that the original claim carried none of the
counts its own rule demands. Producing them showed the comparison cannot be made,
rather than that it comes out well.

What CAN be said, over one test measured the same way either side: the
oracle-selector guard fell from about 52s to about 14s and the CLI refusal guard
from about 26s to about 7s. Both figures were taken under different machine load
— one of them alongside two audits — so they are honest measurements of a real
change and not controlled ones, and this says so rather than rounding them into
a headline.

### Background reconciliation

Every long-running activity displayed during this session was classified from
the process table, producer exit status and durable output rather than from the
display: three orphaned self-matching waiters, retired without terminating
anything; every producer completed and every result consumed; no zombies. The
record is `docs/RP2.4-BACKGROUND-RECONCILIATION.md`.

## The two delta readings, from two providers, and the fourteen things they found

The overnight delta was read twice at `abbe0d8`, bounded to the guarantees it
changed. **HEAD did not move under either**, which is the rule the first
release-authority round taught and this round kept.

| | reading A | reading B |
|---|---|---|
| observed model | `gpt-6-astra`, effort xhigh | a fresh same-family session |
| provider | openai, through codex-cli | anthropic |
| independent of | the coordinator (cross-vendor) | the coordinator's context, and of reading A's PROVIDER |
| could run the suite | **no** — its sandbox gives pytest no temporary directory | **yes** — 2309 passed, plus 24 of its own mutants |
| verdict | DELTA_NOT_SOUND — 9 major, 2 minor, 1 observation | DELTA_NOT_SOUND — 1 blocker, 4 major, 7 minor, 7 observations |

**That pairing is the point.** The provider-diversity gap the previous round
recorded as a limitation is closed: two readings, two providers, and their
findings were largely disjoint — one converging blocker and, either side of it,
defects the other did not see. Reading B could execute, and everything it found
that reading A could not turns on execution.

### The blocker both found, and what it says about the coordinator

**The validator refused command-line matching by DENYLIST while the design
record said it refused the class.** `docs/RP2.4-DESIGN-C47-governed-background-work.md`
states *"Refused as a class rather than pattern by pattern: a rule that has to
decide whether a particular pattern is safe is a rule that can be argued with"*
— and the implementation was five literals plus a fallback that any of three
substrings disabled. Between them the readings walked six waiters past it:

    while [ -e / ] && ps ax | grep -q "pytest tools/tests"; do sleep 20; done
    while ps | grep -q worker; do sleep 20; done  # [ -e /tmp/s ]
    while pidof python3 >/dev/null; do sleep 20; done  # [ -e /tmp/x ]
    sleep infinity  # [ -s out.txt ]

The last is the clearest: it observes nothing, can never end, and was accepted
because a **shell comment** contained a token the fallback looked for. Three
loaded cleanly through the durable boundary and were recorded as governed.

Reading B also named why the whitelist was so weak: `"ps -o stat="` is the
literal `waiter_command` emits, so *governed* meant *contains a substring the
shipped builder emits* — `progress.py` checked against itself, with an oracle
that asserted the round trip.

**Repaired by RECONSTRUCTION.** The pid, sentinel and poll are read back out of
a candidate, `waiter_command` is asked to build the waiter those values imply,
and the two are compared byte for byte. Anything this module did not produce is
refused, whatever it looks like, and nothing has to reason about whether a
pattern is safe. All six cases are refused; the builder's own output is accepted
for every input tried; and the oracle now asserts the PROPERTY — the command
names its process number and its artifact and contains no command-line matcher —
rather than only the round trip.

### What execution found that reading could not

**The manifest's test count was not reproducible.** One new test selected with
`-k "a"`, which matches pytest's own generated `tmp_path` directory name. It
passed here only because macOS puts temporary files outside the repository;
reading B proved it by setting `TMPDIR` inside the tree and getting
`1 failed, 2308 passed`. The subject was correct throughout — it faithfully
reported that two tests were named. **The defect was in the test**, and it is the
same class as the `-k` typo that produced this release's selector tool.

**Guarantee 10 had no oracle at all.** Reading B replaced the panel's
`reconcile` call with a tuple claiming every job was `LIVE_AND_PROGRESSING`
because *"a monitor exists"* — the exact inversion the design says is closed —
and the whole suite passed. It instrumented the panel to show it is entered 145
times across a run: entered, and never looked at. There is a test now.

**`reconcile` and `derive` contradicted each other on one screen.** `derive`
filters retired waits out entirely; `reconcile` consulted `retired` only inside
its finished branch, so a retired wait with a RUNNING producer, and any retired
human wait, went on blocking. The coordinator-state panel read *nothing
outstanding* beside a background panel reading *1 of 1 holding open*.

**`Disposition.SETTLED` was dead.** Documented as the rule governing `blocks`,
consulted by nothing, while `blocks` was hand-set at eight construction sites.
It is derived from the tuple now — one rule, in one place.

### The rest, each reproduced before repair

A `ps` that could not be read was reported as an **absent process**, so a
running producer read as finished — found from inside a sandbox where `ps` was
denied, which is exactly where it bites. A wait naming no subject fell through to
a positive live answer when asked about a candidate, which the failure-mode table
had already forbidden and the code did not do. A producer that had demonstrably
exited was reported as running, because `_observe` chooses by wait kind and never
consulted the recorded process number. The dashboard omitted the candidate
revision it already had. `xfail(run=False)` and setup errors counted as executed
— both exit as though something happened and neither runs a body.
`expect_at_least=0` switched the zero-execution guarantee off, and the shipped
CLI exposed that to any caller. Equal counts were accepted as identical
populations, when two DIFFERENT single tests both report `1 passed`. The
empty-collection check searched the whole output, so a collected node id
containing the words *no tests collected* — which this module's own test names do
— reported the run as empty. A configuration accepted a nested object where every
other identity field is text. And the zombie disposition was keyed on another
module's prose, so rewording a sentence would have silently downgraded it.

### The mutation pass

Seventeen mutants over the repaired subjects, each reverted in place and the
suite re-run. **All seventeen die.** Three survived their first pass — the
repairs had been made and their oracles had not — which is the rule this pack
states as *a repair with no oracle is a claim*, met by the coordinator in its own
work, again.

## The bounded reading of the repairs, and the two defects in them

The fourteen repairs were themselves unaudited, which is the standing condition
of any final repair. One bounded reading closed that delta: **the router chose
the reader, and refused the obvious candidate by name.**

    gpt-6-astra: not independent — the proposed reader is the producer of the
    work (gpt-6-astra). A producer never closes its own finding, whatever task
    class it is dispatched under

Astra had produced most of the findings being repaired, so verifying the repairs
would have been closing its own findings. The seat went to a configuration
`unprobed` at that task class, seated as a declared probe, with the family prior
printed beside it and explicitly ranking nothing. That is the whole mechanism of
this release, deciding a real dispatch.

**REPAIRS_NOT_SOUND — two majors, and both were defects in the repairs.**

**An unanswerable question was rendered as its reassuring answer, by the repair
that created the third answer.** `process_has_ended` was changed to return
`None` where the process table cannot be read — and `reconcile` tests
`if ended:`, which treats `None` as `False`. So a producer nobody could ask
about reported `LIVE_AND_PROGRESSING`. In the module whose thesis is that an
unanswerable question is never its reassuring answer. Reproduced with a denied
`ps` and, by a second route, with a process number persisted as text.

The second route is worth stating because of what it did NOT change. A `pid`
that is not a number is deliberately **carried and named as a state** rather than
refused at construction — this module decided that against an earlier blind
reader, on the ground that a saved record is untrusted input and must reach a
state rather than a traceback. A first draft of this repair started refusing such
a pid at construction, which would have reversed that decision as a side effect
of fixing something else. It was reverted: the hole was never the value, it was
`reconcile` reading `None` as `False`, and it is closed where it happened.

**A governed waiter was not bound to the wait it governs.** `waiter_watches` was
added so a caller could check that a waiter watches the producer its wait names —
and then no caller checked, so a perfectly reconstructed waiter over an unrelated
long-lived process and an unrelated sentinel was recorded as governing this
wait. The module's own docstring already said such a waiter is well-formed and
wrong. A waiter is now refused unless it watches this wait's process number and
this wait's path, and a human wait may carry none at all, because a person is not
a producer.

Five mutants over these two repairs; all five die.

**And the coordinator moved the tree under the reader again.** Not `HEAD` this
time — an uncommitted edit to this file, updating the history-scan figures while
the reading was in flight. The reader noticed, said so, and correctly observed
that the working directory therefore fails `pack_pin` while the candidate commit
still verifies. Third instance of one class in one session: a subject must not
change under a reading, and *uncommitted* is not an exemption.

## The blocking defect, and the founder repair that closed it

**The candidate failed its own commit-range gate on exactly one commit.**

    VIOLATION 62386d4b26f3 PRIVATE_TERM: private term 'c*********r' is prohibited

It was there because `git commit` ran in a shell chain whose earlier link — the
commit gate itself — had already **refused the message**. The gate printed
`VIOLATION`, exited non-zero, and the `&&` was attached to `tail -1`, so the
refusal was reported and ignored in one line. Worth naming plainly: the contract
was not bypassed by ignorance. It was run, it refused, and the commit happened
anyway.

**The founder authorised the minimal repair.** Scope, as given: amend only that
message, preserve the tree exactly, no squash, no rebase of unrelated commits,
no reorder, nothing else rewritten, no push, no tag, no publication, no remote,
no consumer migration.

**Done with `git commit-tree`, not with `rebase`,** so each tree object was
reused rather than reconstructed from a re-applied diff. One phrase of the
message differs; everything else is byte-identical. The child commit's
identifier changed because a commit names its parent; its message and its tree
did not. The full before/after table is in
`docs/RP2.4-FOUNDER-AUTHORISATIONS.md`, and the proof is three commands:

    # PINNED TO THE AMEND. Against HEAD these stopped reproducing as soon as the
    # next commit landed, and an independent reader followed them and concluded
    # the repair had changed content.
    git diff 11dad746… 1dd2aa93… --stat        # empty — no content differs
    git rev-list --count ab7dea97..1dd2aa93    # 10, unchanged, same order
    git rev-parse 62386d4b^{tree} 5069b1c2^{tree}   # one tree object, reused
    git rev-parse 11dad746^{tree} 1dd2aa93^{tree}   # one tree object, reused

    # and at every later revision:
    python3 tools/commit_gate.py --range HEAD --baseline ab7dea97 --repo . --default-terms .
    # VALID every commit message in ab7dea97..HEAD conforms

The pre-amend tip is retained as `refs/pre-amend/rp2.4` in this working
repository only, so the amend is itself auditable. It is not part of the release.

**AND THE CLASS WAS CLOSED, not merely the instance.** A gate whose refusal
depends on the caller reading an exit status will be ignored again.
`templates/commit-msg.hook` moves the enforcement into Git, which refuses the
commit on a non-zero exit whatever the caller's shell does with pipes or `&&`.
The pack does not install it — writing into a project's `.git` is the project's
decision — and `--no-verify` still bypasses it deliberately, because a hook that
cannot be bypassed is a hook people stop installing. What it removes is the
ACCIDENTAL bypass, which is the one that happened. Four oracles, including the
original chain replayed verbatim:

    python3 <gate> "$MSG" --default-terms <pack> | tail -1 && git commit -F "$MSG"

which now produces no commit, and two negative cases — an unconfigured hook and
a missing gate both REFUSE rather than pass, because a check that cannot run is
not a check that passed.

## The pilot-run closure pass

### What was fixed, and what found it

**A checkout on a machine that normalises line endings failed its own pin.**
`core.autocrlf=true` is the Git for Windows default; cloning this branch under
it rewrote LF to CRLF in every tracked file and `pack_pin.py` reported
`PACK PIN NOT VERIFIED` against a checkout of the correct revision. Closed at
the cause with `.gitattributes` declaring `* -text`. Verified end to end: three
clones under `autocrlf=true`, `false` and `input` produce **one identical
digest**. The oracle asks Git whether any tracked path still carries the `text`
attribute — a test that read the file for `* -text` would pass against a pattern
Git ignores.

**A project's repository resolved against the process, not the project.** Found
by rendering the multiproject console over two adopting projects from a third
directory and reading **the pack's own commit count under both of their names**.
`ProjectContract.repository()` returned a relative `repo_path` verbatim, so `commit_gate
--range`, `outgoing_scan`, `workspace_report` and `publication_gate` all ran
against whatever repository the invoking shell was in. Repaired at the contract
so every caller is correct at once, plus the console's own resolver. Five
mutants dead — one of which survived a first oracle because `parent / absolute`
already yields the absolute path, and `.resolve()` would silently rewrite a
declaration made through a symlink.

**No unit test could have found either.** Every rehearsal was single-project and
ran from the project's own directory; every checkout was this machine's.

### The new-model lifecycle, live, through the subscription surface

No API key, no metered API, and no model named as a literal anywhere in the
script — the target is chosen from what discovery offers minus what the evidence
log already contains, so the same run proves the same property for whatever the
surface offers next.

    STEP 1  DISCOVER      9 identifiers, 7 listed, from the installed client
    STEP 2  SELECT        chosen by ABSENCE OF EVIDENCE, not by name
    STEP 3  CLASSIFY      unprobed, with the family's own history beside it,
                          labelled advisory
    STEP 4  AVAILABILITY  UNKNOWN — discovery membership is not an answer
    STEP 5  ROUTE         ROUTINE refused, CRITICAL refused, PROBE permitted
    STEP 6  DISPATCH      two live dispatches, exit 0, both returned READY
    STEP 7  OBSERVE       identity read from the rollout turn_context:
                          model, effort, sandbox and network, all from the
                          surface and none from the worker
    STEP 8  ACCUMULATE    unprobed -> provisional (1) -> confirmed (2)
    STEP 9  BOUND         unprobed at a different effort, a different task
                          class, a different isolation and a different client
    STEP 10 ELIGIBILITY   follows both axes, and says why

Both observations are appended to `policy/observations.jsonl`. The derived table
is printed by `python3 tools/qualification.py`; no count is restated here.

**Availability was re-established on the current client by dispatch**, which is
the only thing that establishes it. Every identifier discovery offers was
dispatched on `0.153.3`: all started, and the model the surface reported matched
the model requested in every case. That closes the recorded gap left by the
`0.149.0 -> 0.153.3` update.

### The application, run as an application

Twelve views, five lenses, three disclosure levels, over two live consumer roots.
**Zero browser console errors** in any state. Preference persistence verified in
a real browser: a lens, a view, a density and two disclosure levels survive a
full navigation and are read back from `localStorage`; a **corrupt** stored value
falls back to the default with no error and a fully working page. No horizontal
overflow and no clipped element at 3840x1600 or at 375x812, where the navigation
collapses to a bottom bar. This is the sweep that found the repository-resolution
defect.

### The composition audit

Eighteen combinations were attacked. Three were not previously covered and are
now:

*   **commit gate x shell chaining** — the hook above, with the original chain
    replayed as the oracle.
*   **history scan x linked worktrees** — a blob reachable only from a linked
    worktree's branch is scanned, pinned by a test whose CONTROL is asserted
    first, because a scan that finds nothing and a scan that reaches nothing
    produce the same number.
*   **clean room x dynamic discovery** — a missing or corrupt discovery document
    makes the capability NOT open, with a finding that names the file. It fails
    closed rather than reporting an empty catalogue.

### The vacuity sweep

Three named shapes had no mechanical guard and now do: `xfail(run=False)`,
`xfail` without `strict`, and an unconditional `skip` — each of which reports a
non-failure without running the test while the suite count still looks right.
The sweep ships with its own positive and negative cases, so it is known to be
able to fail.

**The loop-only shape was measured rather than guarded.** Thirty-six tests place
every assertion inside a loop over a computed iterable. All thirty-six were
traced under execution: every assertion in thirty-five executed, and the
thirty-sixth executed two of four, which is branch coverage rather than vacuity.
A shape guard would have forced cosmetic edits on thirty-six honest tests, so
the population is recorded as measured and the regression risk as an Evolution
Candidate.

**The measurement produced a false green of exactly the class it was
measuring.** The first trace run reported all thirty-six as vacuous — from a
pytest invocation that had matched no files and executed nothing, with `no tests
ran in 0.00s` sitting above the result. This pack's own rule caught it, and the
real answer is the opposite of the first one. It is recorded in
`known_limitations` because a tool that measures this failure class must itself
prove it ran, and that one did not.

### Performance

    python3 -m pytest tools/tests/ -q --durations=25

    The whole suite runs in about four minutes. The 25 slowest tests sum to
    roughly 53s of that; the two slowest are 14.3s (every oracle the closure
    matrix names is shown to select a test) and 9.5s (no tool CLI prints a
    traceback for an input it refuses). The test count is in the manifest and
    is not restated here.

**Nothing was optimised, and no speedup is claimed.** Both of the slowest spawn
one subprocess per row, and making them concurrent would change what runs for
about twenty seconds on a four-minute suite. `selector_evidence.comparison_problems`
exists to refuse exactly the comparison that would be used to justify it. Four
minutes is affordable; a verification nobody can afford is one people disable,
and this one is not there.

### Every recorded limitation, classified

`docs/RP2.4-INVENTORY.md`. Two class-A items and eight class-B items, all ten
closed. The remainder are C or D, each with what still holds, its failure
direction, whether an adopting project can meet it, and what would reopen it.
Five Evolution Candidates are now recorded in the manifest, which had none.

### The pack's own history

`docs/RP2.4-PUBLICATION-ADJUDICATION.md`. Adjudicated rather than owed: at the
tier that governs a project every occurrence resolves to a home-relative form, a
fixture path, a template placeholder or a synthetic identifier, and none names a
person, machine, account, session or credential. At the strict tier the
population is this pack's own governance vocabulary appearing in its own
documentation, which is the case `skills/core/public-safety.md` describes.

## The freeze procedure

**Row 7 is granted.** The founder authorised the governance narrowing before its
entry was written, which is that row's application point; D26 and D27 are in
`DECISIONS.md`, and the authorisation with the ten conditions it carries is in
`docs/RP2.4-FOUNDER-AUTHORISATIONS.md`, bound to
`tools/tests/test_founder_authorisation.py`.

**One human decision remains, and it is not the coordinator's.**

**HITL row 2 — the state transition.** With this gate record's checks green:

       # 1. the baseline is untouched
       cd <2.3.0 root> && git status --porcelain          # empty
       python3 tools/pack_pin.py . --version 2.3.0 \
           --sha ab7dea97a12c699e8123bcb5d5be976cd05c075e \
           --digest 389ef7cd5f7fb60f6819f5d5990d0f04259775e76f6f53190c3a96d2037fcbac \
           --state QUALIFIED_AND_FROZEN

       # 2. the candidate qualifies
       cd <2.4.0 root> && python3 -m pytest tools/tests/ -q

       # 3. the complete range conforms
       python3 tools/commit_gate.py --range HEAD \
           --baseline ab7dea97a12c699e8123bcb5d5be976cd05c075e \
           --repo . --default-terms .

       # 4. set PACK_MANIFEST.json "state" to QUALIFIED_AND_FROZEN, and
       #    "qualified_at" to the date, then recompute the digest:
       python3 tools/pack_pin.py . --write          # recomputes tree_digest_sha256
       python3 -m pytest tools/tests/ -q            # the digest guards re-run

       # 5. commit, and record the revision. The manifest cannot name the commit
       #    that contains it; the consuming project's pin does.

No push, no tag, no remote, no consumer migration. Those are row 2 as well and
are separate decisions taken separately.
