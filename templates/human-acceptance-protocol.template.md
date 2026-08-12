# Human product acceptance — <capability or project> — <review id>

Automation prepares this packet and stops. Only a human sets the Decision
field below (`skills/core/human-decisions.md`; HITL row 9 for accepting a
limitation). The nine fields are the whole protocol; none is optional.

## Flow

What normal use of the product looks like for this review — the user-facing
story, not the implementation.

## Environment

Exactly what is running, where, and against what data/configuration.

## Starting state

What must be true before step 1 — a clean slate, a seeded fixture, a specific
account state. Precise enough that the review is repeatable.

## Steps

Numbered. Each one an action a human actually performs.

1.

## Expected outcome

What should be observably true at the end, stated so a reviewer with no other
context could judge pass/fail from it alone.

## Evidence to capture

Screenshots, logs, exported state — named specifically, not "relevant
evidence."

## Failure criteria

What would make this a FAILED review, stated as concretely as the expected
outcome.

## Residual risks

Known, bounded limitations this review does not exercise, and why that is an
acceptable gap for this review — or a note that it is not, and blocks
acceptance.

## Reset instructions

How to return the environment to a state where this protocol can run again.

---

## Decision

- [ ] PASSED
- [ ] FAILED
- [ ] HITL_ACCEPTED_LIMITATION

Reviewer: __________  Date: __________
