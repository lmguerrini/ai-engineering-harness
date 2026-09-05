# RP2.4 — release packet

What a returning release authority reads first. It points; it does not restate.
Where this file and a computation disagree, the computation wins.

## Identity

    version   2.4.0                          VERSION
    state     IN_PROGRESS                    PACK_MANIFEST.json  -- a candidate
    digest    PACK_MANIFEST.json tree_digest_sha256
    revision  git rev-parse HEAD             -- a manifest cannot name its own commit
    baseline  2.3.0 at ab7dea97a12c699e8123bcb5d5be976cd05c075e, untouched

Verify, do not read:

    python3 tools/pack_pin.py . --version 2.4.0 --sha <rev> \
        --digest <manifest digest> --state IN_PROGRESS

## What this release is

`backend_contract.grades_from_observations` keyed qualification on
`(family, task_class)`. A model with zero observations therefore returned
`qualified_for("blind_closure_audit_cross_vendor") -> True` on seven
observations that recorded no observed model at all — reproduced by execution
before anything was written, and the command is in `docs/RP2.4-GATE.md`.

This release adds a second derivation keyed on the evidence, a separate
availability axis, and a routing surface that ranks on a configuration's own
outcomes. `docs/RP2.4-D26-PROPOSED.md` carries the decision — as a proposal, not an entry;
`docs/RP2.4-ARCHITECTURE.md` carries the shape;
`docs/RP2.4-DESIGN-C40-qualification-identity.md` carries the design that two
independent readings falsified before it was implemented.

## The one decision this candidate cannot take for itself

**HITL row 2 — the state transition to `QUALIFIED_AND_FROZEN`.** With the exact
commands, under *the freeze procedure* at the end of `docs/RP2.4-GATE.md`. No
push, tag, remote or consumer migration is included in it; those are separate
row-2 decisions.

**Row 7 is granted.** The founder authorised the governance narrowing before its
entry was written, which is that row's application point. D26 and D27 are in
`DECISIONS.md`; the authorisation and the ten conditions it carries are in
`docs/RP2.4-FOUNDER-AUTHORISATIONS.md`, and those conditions are executable —
`tools/tests/test_founder_authorisation.py` fails if a later change broadens the
decision past what was authorised.

## What the pilot-run pass changed

Two defects that only running the thing could find, both of which would have met
an adopting project first:

- **A checkout on a machine that normalises line endings failed its own pin.**
  `core.autocrlf=true` is the Git for Windows default and rewrote every tracked
  file. Closed at the cause; three clones under three line-ending configurations
  now produce one identical digest.
- **A project's repository resolved against the process rather than the
  project.** A relative `repo_path` was returned verbatim, so every governed
  check that falls back to it ran against whatever repository the shell was in.
  Found by rendering the console over two projects and reading one repository's
  commit count under both their names.

And the bypass that let a refused commit message land was removed rather than
re-checked: `templates/commit-msg.hook` moves enforcement into Git, so the
caller's shell can no longer ignore a refusal.

`docs/RP2.4-INVENTORY.md` classifies every recorded limitation. Ten were
practically solvable and all ten are closed; the rest are stated with their
failure direction and what would reopen them.

## What this release also became, on the second night

Two operational failure classes were closed structurally after being produced by
the coordinator itself:

- **One governed waiting path.** The pack held two answers to *has this process
  finished*, and the durable state model had the wrong one. It now has one; a
  waiter is governed only if `progress.waiter_command` rebuilds it byte for byte
  and it watches the wait it is recorded against; and `continuation.reconcile`
  derives eight dispositions from the producer, never from a surviving monitor.
- **A run that executed nothing is not evidence.**
  `tools/selector_evidence.py`, after a zero-test run was nearly recorded as a
  forty-five-fold speed-up.

## What is not established

`PACK_MANIFEST.json` `known_limitations` is the list, and it is the list rather
than a summary of one. The five a reader should not miss:

- the per-configuration table is nearly empty, because no observation predating
  this release carries an observed identity — the honest state of this evidence;
- the newest model is `provisional` where it has evidence and `unprobed`
  everywhere else, including at a different EFFORT of a class it has run, which
  is the key working rather than a gap;
- availability was re-established on the current client by dispatch, which is
  the only thing that establishes it — and availability observed today is not
  availability tomorrow, and is never qualification;
- **the final repairs of each round are unaudited until the round after them**,
  which is the standing condition of any final repair and is why the closure
  ceiling is stated rather than reached;
- a wait the coordinator never declares stays invisible, because seeing it would
  mean policing the coordinator's own shell.

## Where the numbers live

Suite count: `PACK_MANIFEST.json` `tests.passed`, written by the collection the
check re-runs. Held prose: `docs/RP2.4-GATE.md`, measured. Delta against the
baseline: `git diff --shortstat`, because a literal here is wrong the moment
this file is edited.
