# RP2.4 — three questions that were one, and the axis that was missing

`DECISIONS.md` D26 carries the decision. `docs/RP2.2-ARCHITECTURE.md` states the
authority layering and `docs/RP2.3-ARCHITECTURE.md` states where machine-written
state sits within it; both are unchanged. This file states only what this release
adds to that picture.

## The shape

    RUNTIME DISCOVERY                     what a surface is offering right now
      model_discovery.read(document)      -> DISCOVERED, and nothing more
        │  advisory by policy/execution-boundaries.md; never normative
        ▼
    OBSERVED DISPATCH OUTCOMES            what actually happened when we ran it
      availability_for(identity, preconditions, observations)
        │  the only positive evidence for AVAILABLE, keyed WITH preconditions
        ▼
    PER-CONFIGURATION QUALIFICATION       what this configuration has done
      qualifications_from_observations()  -> nine-dimension key, complete only
        │  a grade at one task class is unprobed at every other
        ▼
    ELIGIBILITY AND ROUTE                 what may take this work, and why not
      routing.eligibility / design_audit_route
        │  reports and refuses; ranks on this configuration's own evidence
        ▼
    THE COORDINATOR                       decides

    FAMILY HISTORY ── printed beside an unprobed answer, ranks nothing ──┘
      priors_from_observations()  ==  policy/routing-table.md

Static documentation — this file, the routing table, an adapter's model table —
is **subordinate to runtime discovery at every level**. A table that disagrees
with a reading is a stale table, and a reading that disagrees with a dispatch is
a stale reading.

## Why the axes are separate

Each layer answers a question whose evidence the layer above cannot supply, and
every conflation has a measured case behind it:

*   **A document listed a model its own client could not run.** The provider
    refused it outright. Discovery therefore claims membership of a catalogue
    and nothing else.
*   **The same account offered different sets under two client versions,
    minutes apart.** So a reading carries its producer, and a producer that is
    not the dispatching client is reported as skew rather than read as truth.
*   **One configuration started under one precondition and hung under another.**
    So preconditions are part of the availability key, and a success cannot
    answer for the dispatch that never began.
*   **A worker reported its own model as a different generation than the one
    that ran.** So the observed identity is read from the execution surface, and
    a provenance that says otherwise makes the identity incomplete.

## What did NOT become a new authority

Nothing here decides that a model may be used. `routing.py` ranks and refuses; it
launches nothing, contacts no network, and writes no observation. The dashboard
panel derives from the same functions in the same process on every render and
stores no route, so there is no held value to go stale — the property that let a
diagnostic projection ship in 2.3.0 at all, and the same one applies.

The observation log stays the record. Both derivations are views over it,
computed from the whole log every time, never patched.

## What a new model costs the Core

Nothing. A model identifier this pack has never seen flows from a discovery
document to a route report with no edit here: discovery reads FIELD names rather
than model names, the identity is whatever the surface reported, and the grade is
whatever that configuration's own observations say. There is no allowlist to
extend and no table to update — and a test asserts the toolbelt contains no model
identifier at all, matched as a shape so that the guard cannot age the way the
vocabulary it replaced aged.

What a new model does cost is **evidence**. It starts `unprobed`, it may be
probed deliberately, and it becomes qualified at a task class by doing that task
class. That is the whole of the ladder.
