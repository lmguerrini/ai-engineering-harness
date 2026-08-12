# Requirement interpretation

Turning what somebody asked for into what must be true.

## Normalise before decomposing

A requirement as written mixes three things, and separating them is most of the
work:

*   **What must be true** — the property. Testable, or it is not a requirement.
*   **How somebody imagined achieving it** — a proposed mechanism, which may be
    wrong and is not binding unless it was declared so.
*   **What was assumed without being said** — the part that causes the argument
    later.

Write the property. Keep the mechanism as a note if it carries intent. Surface
the assumption while it is still cheap to correct.

## A requirement with no oracle is not a requirement

If nothing could show it was violated, it cannot be delivered or refused. Either
find the observation that would settle it, or record it as an intention with no
acceptance criterion — clearly labelled, so nobody later reads it as a promise.

## Scope is the deliverable

The requested scope is what to build: not a narrower version that is easier, not
a wider one that is more interesting. If a requirement seems wrong, say so in a
sentence and build it anyway under a stated assumption — scaling the work down
is the human's call, not the harness's.

Ambiguity is resolved the way a careful colleague resolves it: make the routine
judgement, record the assumption, and ask only when two readings would produce
materially different work.

## Gaps are decisions

A requirement with neither a test nor a recorded gap means nobody decided. A
recorded gap with a named owner means somebody looked and chose to leave it. The
first is invisible; the second is a position that can be reviewed. Never leave
the first.
