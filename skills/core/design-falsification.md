# Design falsification

**Applies to:** every MATERIAL change — a new promise, a new authority, a new
boundary, or a change to one. Applied by the COORDINATOR **before** the first
mutation, and read at the capability open by `capability_open.open_capability`.

Routine work does not need this. Trivial work must not have it. A rule that
demands a design document for a typo is a rule that gets routed around, and a
rule that gets routed around is worse than no rule, because the project
believes it is enforced.

---

## The shape this exists for

    implement → defect → repair → defect in the repair → repair → …

Every repair in that sequence is individually reasonable, which is exactly why
nobody notices the shape from inside it. Across this pack's own evolution about
a quarter of all audit findings were defects in the previous round's repairs,
and the ratio never improved across sixteen rounds.

`skills/core/repair.md` governs what happens once a defect exists. It is the
second half. This is the first: **the alternatives, the failure modes, the
authority boundaries and the oracles are written down and frozen before there
is anything to defect**, so the first detector of a bad design is not the
defect it produces.

## The sequence — in this order, no steps merged

1. **Name the mechanism.** One sentence, in terms of what the machine actually
   does. Not the symptom, not the file. Same rule, same reason, as
   `skills/core/oracle-discipline.md`.
2. **Consider at least two designs.** One candidate is a decision nobody made.
   Where the space is genuinely one design, say so as a rejected alternative
   with its reason — *doing nothing* is a candidate and usually a serious one.
3. **Reject with a reason.** A rejected design with no reason is not a
   rejection; it is a list.
4. **State the failure modes of the design you selected**, and beside each,
   what keeps it from being *silent*. A mode you cannot make non-silent is a
   bounded limitation: write it down rather than omitting it.
5. **State the authority boundaries.** What it may decide, and what it must
   never decide. A mechanism that does not say what it must never decide will
   eventually decide it. Say explicitly that no row of `policy/hitl-matrix.md`
   is weakened — or say which row it touches, which is HITL row 7.
6. **Freeze the oracles.** Acceptance for what must hold, negative for what
   must be refused, mutation for a material invariant's guard. They are named
   before the implementation they judge, so the implementation cannot choose
   them.
7. **Then implement**, and only then.

## What freezing means

The record names the exact forty-character revision it was frozen against. That
revision must resolve in the repository and be an ancestor of `HEAD`, and where
the coordinator can name the revision at which mutation began, the base must be
a strict ancestor of it. A design frozen against a tree that already contains
the work it governs is refused — backdating is the obvious cheat and the only
one worth building for.

## What this is not

*   **Not a planning ceremony.** Two candidates, a handful of failure modes and
    a table of oracles. If it is taking an afternoon, the capability is too big
    (`skills/core/decomposition.md`), not the design too small.
*   **Not a second authority.** It reports. It cannot open a capability, close
    one, satisfy a HITL row or move a release state. The aggregate answer stays
    in `capability_open`, and the decision stays with the coordinator.
*   **Not a judgement of the design.** Nothing here says the selected design is
    good. It says a design was selected against stated alternatives, with stated
    failure modes and frozen oracles. That is the part a machine can settle, and
    claiming more would be Core adjudicating product meaning.
*   **Not enforceable against a caller who lies about the class.** The change
    class is an input, because Core cannot know which of a project's changes are
    material. A caller who declares `TRIVIAL` to avoid the record has made a
    visible claim in the readiness report rather than a silent one. That is the
    honest bound; it is recorded as a limitation and not dressed up as
    prevention.

## The artifact

`templates/DESIGN.md.template`, read by `tools/design_record.py`, composed into
`tools/capability_open.py` as the `design` component. A project declares
`requires.design: true` when its capabilities are material by default;
otherwise the coordinator declares the class per open with `--change-class`.
