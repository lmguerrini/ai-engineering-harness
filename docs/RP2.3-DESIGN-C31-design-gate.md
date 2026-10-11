# DESIGN — C31 pre-implementation design falsification

**Change class:** MATERIAL
**Base revision:** 28e69cbebd49a6faccbc7266c1278fb27aa0e79e
**Frozen:** yes

Written before any line of the mechanism it describes, and this file is the
first thing the mechanism is used on.

## The mechanism

A coordinator reaching a material capability can begin mutating immediately,
and nothing durable records what designs were considered, what failure modes
were expected, or which oracles had to exist first — so the only detector of a
bad design is the defect it produces, and the only response is another repair
round.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | A gate process that intercepts editing and refuses to let implementation start | REJECTED | This release ships nothing that runs. A gate with no way to intercept is prose with a filename, and building one would add the daemon the whole pack refuses. |
| 2 | A template plus a skill: write the design down, by convention | REJECTED | This is the present state, and the present state is what was classified DOCUMENTED_ONLY. `skills/core/repair.md` already says a recorded failure nobody consults is not enforcement. |
| 3 | Refuse the commit: `commit_gate.py` rejects a commit with no design record | REJECTED | Wrong domain. The commit gate's question is the message's vocabulary; a design is per capability and a capability is many commits, so the check would fire on every trivial commit and mean nothing on the material one. |
| 4 | A new authoritative lifecycle state that blocks the run | REJECTED | It would make the design record a second product authority, deciding when work may proceed. The founder's constraint is authority-preserving, and this pack's states are derived from artifacts, never asserted by a new adjudicator. |
| 5 | A composed component of the existing readiness path `capability_open.open_capability()` | SELECTED | It is the deterministic path already run *before a governed capability opens* — exactly the transition in question. It already composes delegated components, already distinguishes required from blocking, already fails closed on `UNKNOWN`, and already has a requirement rule that scales by project declaration. Adding a component is composition, not a new source of truth. |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | Ceremony creep: every trivial edit demands a design | The change class is an input, and `TRIVIAL` resolves to `NOT_REQUIRED` — a first-class answer, not an omission. Only `MATERIAL` requires alternatives and a mutation oracle. |
| 2 | It becomes a second authority, deciding product questions | It decides nothing. It reads a file and reports whether that file states what it claims to state. It cannot make a capability open, override a HITL row, or change any release state. |
| 3 | Rubber-stamp design: one candidate, named "do it" | A `MATERIAL` record is refused unless it carries at least two candidates, at least one `REJECTED`, exactly one `SELECTED`, at least one failure mode, an authority-boundary statement, and acceptance, negative and mutation oracles. |
| 4 | Backdating: a design written after the code, dated before it | The base revision must resolve in the repository and be an ancestor of `HEAD`; where the caller names the revision at which mutation began, the base must be a strict ancestor of it. An invented sha and a sha from the future are both refused. |
| 5 | The gate silences unrelated work | The component is scoped to the capability named in the call. Nothing about capability B's design appears in capability A's readiness report. |
| 6 | Oracles that are a wish list: named, never written | **NOT CLOSED, and stated rather than claimed.** A record is refused unless every oracle states the property it settles, which stops the emptiest version. Whether a named selector reaches a real test is not checked: nothing in `design_record.py` reads the selector column. The closure matrix already has that mechanism for the release's own oracles and wiring it here is a new promise, not a repair — recorded as an Evolution Candidate. An independent reader found this row claiming an enforcement that did not exist. |
| 7 | Skipping by declaring the class as trivial | Not preventable by construction, and not claimed to be. The declared class is recorded in the readiness report and in the design state, so "NOT_REQUIRED because the caller declared TRIVIAL" is a visible claim a reader or an auditor can dispute. Recorded as a bounded limitation. |

## Authority boundaries

*   It **reports**. It never authorises, opens, closes, freezes or promotes.
*   It **never adjudicates product meaning**: it does not judge whether the
    selected design is good, only whether a design was selected against stated
    alternatives with stated failure modes and frozen oracles.
*   It **never weakens HITL**. Every row of `policy/hitl-matrix.md` fires
    exactly as before; this adds no row and removes none.
*   It **never becomes a second identity or release authority**. It has no
    opinion about the pin, the digest or the state.
*   A project that declares nothing gets `NOT_REQUIRED`, because Core cannot
    know which of a project's capabilities are material — that is a property of
    the project, exactly as `requires.project_context` already is.

## Oracles, frozen before implementation

| ID | Kind | The property it settles |
|---|---|---|
| O1 | ACCEPTANCE | A complete MATERIAL design record verifies with no problems. |
| O2 | ACCEPTANCE | `capability_open` reports `design VERIFIED` and `READY` when the record is complete and the project requires one. |
| O3 | NEGATIVE | A MATERIAL record with one candidate design is refused. |
| O4 | NEGATIVE | A MATERIAL record with no rejected alternative is refused. |
| O5 | NEGATIVE | A MATERIAL record with no failure modes is refused. |
| O6 | NEGATIVE | A MATERIAL record with no mutation oracle is refused. |
| O7 | NEGATIVE | A record whose base revision does not resolve, or is not an ancestor of HEAD, is refused. |
| O8 | NEGATIVE | A record whose base revision already contains the mutation it governs is refused. |
| O9 | NEGATIVE | A project that requires a design and has none reports `NOT_PRESENT` and `NOT_READY` — implementation is not authorised. |
| O10 | NEGATIVE | A declared design that cannot be read reports `UNVERIFIABLE` and blocks whether or not it was required (D22). |
| O11 | ACCEPTANCE | A `TRIVIAL` change resolves to `NOT_REQUIRED` and does not block. |
| O12 | ACCEPTANCE | A `ROUTINE` change requires acceptance and negative oracles and does *not* require alternatives. |
| O13 | REHEARSAL | material change → design gate → design selected → oracles frozen → implementation authorised, as one sequence. |
| O14 | REHEARSAL | material change → immediate implementation with no design cannot reach an authorised state. |
| O15 | MUTATION | Each refusal above is demonstrated to fail when its guard is removed. |
| O16 | ACCEPTANCE | Cold reconstruction in a fresh process recovers the design decision and its rationale from disk alone. |
