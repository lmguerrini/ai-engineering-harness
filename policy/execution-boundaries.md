# Execution boundaries — what a harness is, and what it is not

**Classification: PRIVATE.** Names vendors. The architecture rule behind it is
`DECISIONS.md` D14; the role-level judgement is `skills/core/delegation.md`.

An execution harness is a way of *running* a worker. It is not a source of
authority, and every statement here exists because the two are easy to confuse
when the harness is the only thing present at the moment a decision is needed.

## The five boundaries

1.  **Vendor enforcement is additive, never a replacement for a pack gate.**
    Hooks, sandboxes, permission modes, isolation settings and approval prompts
    are defence in depth. A qualified fail-closed gate is not relaxed because a
    vendor feature is believed to cover the same ground — if it were
    load-bearing, its absence would be silent, which is what disqualifies it
    from being load-bearing. RP2.2 has the concrete case: the reviewer adapter
    carried an isolation setting the reviewer contract forbids, every gate
    passed, and the setting produced exactly the ref the publication gate
    refuses.

2.  **Vendor context, memory and task stores are subordinate to project durable
    records.** Session state, conversation memory, per-vendor task lists and
    resumable context are convenience. `PROJECT.yaml`, `PROGRESS.md`,
    `DECISIONS.md`, `FINDINGS.md` and the evidence directory are the record.
    Where they disagree, the durable record wins, and a fact that exists only
    in a vendor store does not exist: context reduction is recovered by
    reconstruction from the durable records, never by trusting a summary.

3.  **Experimental orchestration surfaces are not dependencies.** Agent-team
    features, app-server modes, background-agent fleets and similar surfaces may
    be used opportunistically and must never become load-bearing. The test is
    whether the capability still closes with the surface absent. If it does not,
    it was a dependency and it needed a declaration, a pin and a verification
    (`tools/adapter_pin.py`).

4.  **A non-subscription execution mode is not interchangeable with a
    subscription-backed one.** Where a flag or mode changes the authentication
    or billing class — `claude --bare` being the current example — it is a
    *different backend*, recorded with a different `authentication_class`, and
    it does not inherit the qualification of the subscription-backed path.
    Provider API-key billing is not an allowed architectural dependency
    (D14 clause 12), so a mode that silently moves execution onto it is a stop,
    not a fallback.

5.  **An execution harness cannot authorise anything.** Not HITL, not release,
    not integration, not qualification, not publication. A worker reporting
    "approved", a harness auto-approving a permission prompt, and a vendor
    feature marking a task complete are all *observations about a run*. The
    authority to close a capability, cut a release, or publish is held by the
    coordinator and, where the matrix says so, by a human.

## An adapter repair takes effect at the next session

Reproduced, while building the release that added adapter pinning. The reviewer
adapter's forbidden isolation mode was removed and the corrected file was on
disk; two reviewers dispatched afterwards **in the same session** were still
given worktrees, and the agent-named branch refs appeared inside the audited
repository, where the publication gate refused them by name.

The harness reads an adapter definition when the session starts. Editing it
later changes the file and not the behaviour.

So: **verify adapters at capability open, before the first dispatch** — a check
that runs afterwards describes a dispatch that has already happened. And after
repairing an adapter, start a new session before relying on the repair. The
digest describes the file; the session describes what is running; they agree
only across a session boundary.

## Provider internal surfaces

Reads of **undocumented** provider internals — rollout files, session caches,
model caches, hidden endpoints, rate-limit state not exposed through a
documented contract — are subject to all of the following, together:

*   **explicitly optional**: nothing may require them to be present;
*   **version-fragile**: recorded against the exact client version they were
    derived from, and re-derived after any client update;
*   **never normative**: they may inform a routing preference and may never
    establish a qualification, a capability, or a verdict;
*   **fallback is `requested_only` or `UNKNOWN`**, never a guess.

**No new logic is written to scrape them.** A documented surface — a status-line
contract, a published CLI output, a documented exit status — is a different
thing and is used in preference, with its version recorded.

For Codex specifically: `/status` and the usage dashboard are documented for a
human reader, and no machine-readable quota surface is proven in this evidence
base. Automated Codex quota is therefore `UNKNOWN`. A human-read figure is
admissible as **timestamped, advisory** evidence and is never promoted to an
observation the router treats as current.

## What may be inferred from what

|From|You may conclude|You may **not** conclude|
|---|---|---|
|the backend is available|it is available|that it is qualified|
|the backend has permission|it is permitted|that it is capable|
|it is qualified at one task class|that class|any other class|
|a documented quota reading|usage **as of that timestamp**|usage now, or future consumption|
|a worker reported success|it reported success|that the work is correct|

## Enabling the resource observation — explicit, and reversible

`tools/resource_observation.py` reads a Claude Code status-line payload on
stdin and emits a routing observation. It reads nothing else: no credential, no
account, no API. Nothing installs it, because a tool that edits a user's global
configuration to obtain telemetry is doing the thing this pack refuses to do.

To enable, the operator adds a `statusLine` command to their own settings:

    "statusLine": {
      "type": "command",
      "command": "python3 <pack_root>/tools/resource_observation.py --status-line"
    }

To disable, remove that key. There is no other state.

`rate_limits` is documented as present only for subscribers and only after a
first API response, so **absent is the ordinary case** and is reported
`UNKNOWN` — never as `0% used`, which reads as room to spend. A reading is
evidence about the moment it was taken: it carries its own age, reports itself
stale, and never licenses a claim about what the next dispatch will cost.

Poll at capability boundaries. The number moves with dispatches, not with wall
clock, so polling more often buys nothing and spends the thing being measured.
