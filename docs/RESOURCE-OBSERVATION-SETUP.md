# Enabling the resource observation

Moved out of `policy/execution-boundaries.md` in RP2.3. The judgement stayed there; this is
the procedure, and a procedure is pulled on demand rather than held every session
(`policy/BUDGETS.md`). Left exactly as written.

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

To keep a reading as project-local routing evidence, at a capability boundary:

    … | python3 <pack_root>/tools/resource_observation.py --append <project>/ROUTING_OBSERVATIONS.jsonl

Append-only, and deduplicated against the last line. Not on the status line
itself: that command runs on every render, so an unconditional append records
how often the terminal repainted rather than how much quota moved — and a file
that large stops being read, which is the same as not having one.

`rate_limits` is documented as present only for subscribers and only after a
first API response, so **absent is the ordinary case** and is reported
`UNKNOWN` — never as `0% used`, which reads as room to spend. A reading is
evidence about the moment it was taken: it carries its own age, reports itself
stale, and never licenses a claim about what the next dispatch will cost.

Poll at capability boundaries. The number moves with dispatches, not with wall
clock, so polling more often buys nothing and spends the thing being measured.
