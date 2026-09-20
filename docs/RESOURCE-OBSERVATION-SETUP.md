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

## A provider's own window, and a person's reading — the same shape (2.6.0)

The status line is one source. Two more read into the same observation, and every observation now answers
whether it is still current:

*   **A provider quota document** — the generic shape `runtime-pack-quota-1` an adapter's observer prints
    (provider id, billing pool id, the document's own `observed_at`, and every window the source exposes with
    its native remaining/limit/unit and reset): `python3 tools/resource_observation.py --provider-quota quota.json
    [--append observations.jsonl]`. Percentages are derived only when both natives are present; a window the
    document does not carry is `UNAVAILABLE`; a document that cannot be read is a refusal (exit 2), never a
    reading full of UNKNOWN windows.
*   **A human reading** — `python3 tools/resource_observation.py --human-reading --provider-id P --pool-id Q
    --window weekly=50 --observed-at 2000-01-01T00:00:00Z`: advisory, timestamped, and it says so.

**Freshness is computed when the reading is asked, never stored.** Each source carries a horizon (status line
30 min, provider quota 15 min, human reading 2 h): inside it the reading is `FRESH`, past it `STALE`; a reading
without a moment, with an unknown horizon, or dated in the future is `UNKNOWN`; one whose windows are all
unexposed is `UNAVAILABLE`. A stale figure is shown with its age and is never presented as current.

**One writer of `CAPACITY.json`.** `python3 tools/capacity_record.py write CAPACITY.json --written-by '<who>'
--pool-from quota.json --pool-id <billing pool> --kind independent --window rolling --window-name rolling_5h
--billing-mode subscription [--reserve …] [--keep-existing]` turns a reading into the pool the capacity gate and
the projection read; `capacity_record.py check CAPACITY.json` reports each pool's freshness and quarantines,
per element, any entry it cannot read — the count blocks closure, the rest still derives (D36). Both identifiers
of one subscription draw on one pool: record one pool, never two.
