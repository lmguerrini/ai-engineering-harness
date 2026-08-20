"""Live execution-resource truth, from a documented surface, as routing evidence.

Routing decisions were being made against capacity that was either invented or
honestly unknown. `policy/routing-policy.md` already required "observed-or-
honestly-unknown, never invented" — this module is what makes the first half
possible for one backend, without weakening the second half for the rest.

## The surface, and why it is allowed

Claude Code invokes a configured `statusLine` command with a JSON payload on
stdin. That payload is **documented in the client itself**, and the fields this
module reads were verified against the installed client's own documentation
block rather than assumed:

    rate_limits.five_hour.used_percentage    number, 0-100
    rate_limits.five_hour.resets_at          unix epoch seconds
    rate_limits.seven_day.used_percentage    number, 0-100
    rate_limits.seven_day.resets_at          unix epoch seconds
    model.id, model.display_name
    version                                  client version
    effort.level                             only when the model supports it
    context_window.used_percentage           null until the first response

`rate_limits` is documented as *optional*, present only for subscribers and only
after a first API response, and each window is individually optional. So absence
is the normal case and is recorded as `UNKNOWN` rather than as zero — a missing
quota reading rendered as `0% used` is an invitation to spend.

This is a **documented** contract, which is what separates it from the reads
`policy/execution-boundaries.md` forbids. It is nonetheless **version-fragile**:
the client version is recorded in every observation, and a client update
invalidates the derivation rather than the observation.

## What is deliberately not carried

The payload also contains `session_id`, `transcript_path`, `cwd`,
`workspace.project_dir` and more. None of it reaches an observation. The
projection is an **allowlist**, not a redaction pass, because a redaction pass
fails open the first time the payload grows a field. This is not fastidiousness:
routing observations are scanned by the pack's own leak gate, and a transcript
path is a local filesystem path and a session id is a UUID — the two things
`UNIVERSAL_LEAK_KINDS` exists to refuse.

## What an observation does not license

*   It is **not a prediction.** A five-hour window at 40% says 40% was used as
    of `observed_at`. It says nothing about what the next dispatch will cost.
*   It **ages.** `age_seconds` is computed against a caller-supplied clock and
    `stale` is reported explicitly, because a reading is evidence about a moment.
*   It is **not qualification.** Capacity is capacity (`DECISIONS.md` D8).
*   Core reads it and **owns no credential and no account state.** There is no
    login here, no API call, and nothing to configure but the status line.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "UNKNOWN",
    "SOURCE_STATUS_LINE",
    "DEFAULT_STALE_AFTER_SECONDS",
    "Window",
    "ResourceObservation",
    "from_status_line",
    "append_observation",
]

UNKNOWN = "UNKNOWN"

#: Named so an observation says where it came from. A reading whose provenance
#: is not recorded cannot be re-derived when the surface changes.
SOURCE_STATUS_LINE = "claude-code/status-line-json"

#: After this, a reading is reported stale. Long enough that a capability
#: boundary does not have to re-poll to act, short enough that it cannot be
#: mistaken for current. Polling more often than a capability boundary buys
#: nothing: the number moves with dispatches, not with wall clock.
DEFAULT_STALE_AFTER_SECONDS = 30 * 60


def _number(value: Any) -> float | str:
    """A number, or `UNKNOWN`. Never a coerced zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return UNKNOWN
    return float(value)


def _text(value: Any) -> str:
    return value if isinstance(value, str) and value.strip() else UNKNOWN


@dataclass(frozen=True)
class Window:
    """One rate-limit window, as read.

    `used_percentage` and `resets_at` are independently optional because the
    documented payload makes them so.
    """

    name: str
    used_percentage: float | str = UNKNOWN
    resets_at: float | str = UNKNOWN

    @property
    def known(self) -> bool:
        return self.used_percentage != UNKNOWN

    def seconds_until_reset(self, now: float) -> float | str:
        if self.resets_at == UNKNOWN:
            return UNKNOWN
        return max(0.0, float(self.resets_at) - now)

    def describe(self, now: float) -> str:
        if not self.known:
            return f"{self.name}: UNKNOWN (not reported by the client)"
        remaining = self.seconds_until_reset(now)
        when = "reset time UNKNOWN" if remaining == UNKNOWN else f"resets in {int(remaining) // 60}m"
        return f"{self.name}: {self.used_percentage:.0f}% used, {when}"


@dataclass(frozen=True)
class ResourceObservation:
    """One timestamped reading of a backend's resource state."""

    source: str
    observed_at: float
    backend_family: str = UNKNOWN
    client_version: str = UNKNOWN
    model_observed: str = UNKNOWN
    effort_observed: str = UNKNOWN
    context_used_percentage: float | str = UNKNOWN
    windows: tuple[Window, ...] = ()
    #: Every documented field this payload did not carry, named.
    absent: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)

    def window(self, name: str) -> Window:
        for candidate in self.windows:
            if candidate.name == name:
                return candidate
        return Window(name)

    def age_seconds(self, now: float) -> float:
        return max(0.0, now - self.observed_at)

    def stale(self, now: float, *, after: float = DEFAULT_STALE_AFTER_SECONDS) -> bool:
        return self.age_seconds(now) > after

    @property
    def any_quota_known(self) -> bool:
        """Whether this reading establishes quota at all.

        The distinction routing needs: a payload from a non-subscriber, or from
        before the first API response, is a valid observation that establishes
        nothing about quota — and must not be treated as "quota is fine".
        """
        return any(window.known for window in self.windows)

    def render(self, now: float) -> str:
        age = int(self.age_seconds(now))
        head = (
            f"resource observation [{self.source}] "
            f"{'STALE ' if self.stale(now) else ''}{age}s old"
        )
        lines = [head]
        lines.append(f"  backend: {self.backend_family} client {self.client_version}")
        lines.append(f"  model observed: {self.model_observed} · effort {self.effort_observed}")
        if self.context_used_percentage == UNKNOWN:
            lines.append("  context: UNKNOWN")
        else:
            lines.append(f"  context: {self.context_used_percentage:.0f}% used")
        if not self.any_quota_known:
            # Two different reasons, and saying the wrong one is the same defect
            # this module exists to avoid: the payload may have been read fine
            # and carried no limits, or it may not have been read at all.
            reason = (
                "the payload could not be read, so nothing was established"
                if self.notes
                else "the client reported no rate limits — the documented case for a "
                "non-subscriber, or before the first response"
            )
            lines.append(f"  quota: UNKNOWN — {reason}. This is not a statement that quota is available")
        for window in self.windows:
            lines.append(f"  {window.describe(now)}")
        for name in self.absent:
            lines.append(f"  not reported: {name}")
        lines.extend(f"  note: {note}" for note in self.notes)
        lines.append("  this reading describes a moment; it does not predict consumption")
        return "\n".join(lines)

    def as_record(self) -> dict:
        """The observation as a routing-evidence record.

        Only the allowlisted fields. Nothing here can carry a path, a session
        identifier or a working directory, because nothing here reads one.
        """
        return {
            "source": self.source,
            "observed_at": self.observed_at,
            "backend_family": self.backend_family,
            "client_version": self.client_version,
            "model_observed": self.model_observed,
            "effort_observed": self.effort_observed,
            "context_used_percentage": self.context_used_percentage,
            "windows": [
                {
                    "name": window.name,
                    "used_percentage": window.used_percentage,
                    "resets_at": window.resets_at,
                }
                for window in self.windows
            ],
            "absent": list(self.absent),
        }


#: The documented windows. Named here so a payload carrying neither is reported
#: as two absences rather than as an empty list nobody notices.
_WINDOW_NAMES = ("five_hour", "seven_day")


def from_status_line(payload: str | bytes | dict, *, observed_at: float) -> ResourceObservation:
    """One observation from a Claude Code status-line payload.

    `observed_at` is supplied by the caller rather than read from a clock in
    here, so the same payload always produces the same observation and a test
    is not a race. Wall-clock time is an input, not an ambient fact.

    A payload that cannot be parsed produces an observation whose every field is
    `UNKNOWN`, with the reason in `notes` — **not** an exception and not an
    absence. A routing input that vanishes when the adapter breaks is a routing
    input that silently stops constraining anything.
    """
    notes: list[str] = []
    document: dict = {}
    if isinstance(payload, dict):
        document = payload
    else:
        try:
            text = payload.decode("utf-8", "replace") if isinstance(payload, bytes) else payload
            loaded = json.loads(text)
            if isinstance(loaded, dict):
                document = loaded
            else:
                notes.append("the status-line payload was not a JSON object")
        except (ValueError, AttributeError) as exc:
            notes.append(f"the status-line payload could not be read: {exc}")

    model = document.get("model")
    model = model if isinstance(model, dict) else {}
    effort = document.get("effort")
    effort = effort if isinstance(effort, dict) else {}
    context = document.get("context_window")
    context = context if isinstance(context, dict) else {}
    limits = document.get("rate_limits")
    limits = limits if isinstance(limits, dict) else {}

    windows: list[Window] = []
    absent: list[str] = []
    for name in _WINDOW_NAMES:
        raw = limits.get(name)
        if not isinstance(raw, dict):
            absent.append(f"rate_limits.{name}")
            windows.append(Window(name))
            continue
        windows.append(
            Window(
                name=name,
                used_percentage=_number(raw.get("used_percentage")),
                resets_at=_number(raw.get("resets_at")),
            )
        )

    observation = ResourceObservation(
        source=SOURCE_STATUS_LINE,
        observed_at=observed_at,
        # Attributed only when the payload carries something only this client
        # emits. `if document` attributed *any* non-empty JSON object on stdin
        # to this vendor, which is a claim about provenance made from nothing.
        backend_family=(
            "claude-cli"
            if isinstance(document.get("version"), str) and isinstance(model, dict) and model
            else UNKNOWN
        ),
        client_version=_text(document.get("version")),
        # The status line reports the model the session is *running*, which is
        # the observation the routing table needs and the one a dispatch
        # request cannot supply.
        model_observed=_text(model.get("id")),
        effort_observed=_text(effort.get("level")),
        context_used_percentage=_number(context.get("used_percentage")),
        windows=tuple(windows),
        absent=tuple(absent),
        notes=tuple(notes),
    )
    return observation


def append_observation(path: str | Path, observation: ResourceObservation) -> bool:
    """Append one observation to a project-local JSONL. Returns whether it wrote.

    **Append-only project-local facts**, which is the shape everything else in
    this pack uses for evidence: the file is the record and any view over it is
    derived. Core writes only where the caller points it, owns no location, and
    never writes into a pinned release.

    Deduplicated against the last line, and this is not an optimisation. A
    status-line command runs on **every render**, so an unconditional append
    turns a routing record into a log of how often the terminal repainted — and
    a file that large stops being read, which is the same as not having it. A
    reading whose quota figures and model are unchanged records nothing new; only
    its timestamp would differ, and a timestamp is not an observation.
    """
    path = Path(path)
    record = observation.as_record()
    comparable = {key: value for key, value in record.items() if key != "observed_at"}

    if path.exists():
        try:
            previous = path.read_text(encoding="utf-8").strip().splitlines()
        except OSError:
            previous = []
        if previous:
            try:
                last = json.loads(previous[-1])
                if {k: v for k, v in last.items() if k != "observed_at"} == comparable:
                    return False
            except ValueError:
                # An unreadable last line is not a match. Append rather than
                # silently drop the reading.
                pass

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return True


def _cli(argv: list[str]) -> int:
    """Read a status-line payload on stdin; print an observation.

    Usable *as* the status-line command, which is the point: the operator makes
    one explicit, reversible configuration change and the reading becomes
    available. Nothing here edits anyone's configuration — a tool that installs
    itself into a user's global settings to obtain telemetry is doing the thing
    this pack refuses to do.
    """
    import argparse
    import sys
    import time

    parser = argparse.ArgumentParser(
        prog="resource_observation.py",
        description="Turn a Claude Code status-line payload into a routing observation.",
    )
    parser.add_argument("--json", action="store_true", help="emit the record rather than the report")
    parser.add_argument(
        "--status-line",
        action="store_true",
        help="emit one terse line, for use as the statusLine command itself",
    )
    parser.add_argument(
        "--append",
        metavar="PATH",
        help=(
            "append this observation to a project-local JSONL, unless it is identical "
            "to the last one. For capability boundaries; a status line runs on every "
            "render and does not need a record of each"
        ),
    )
    args = parser.parse_args(argv)

    now = time.time()
    observation = from_status_line(sys.stdin.read(), observed_at=now)

    if args.append:
        try:
            wrote = append_observation(args.append, observation)
        except OSError as exc:
            print(f"the observation could not be appended: {exc}", file=sys.stderr)
            return 2
        if not args.status_line and not args.json:
            print(f"{'appended to' if wrote else 'unchanged since the last reading in'} {args.append}")

    if args.json:
        print(json.dumps(observation.as_record(), indent=2))
        return 1 if observation.notes else 0
    if args.status_line:
        five = observation.window("five_hour")
        seven = observation.window("seven_day")
        parts = [observation.model_observed, f"effort {observation.effort_observed}"]
        parts.append(f"5h {five.used_percentage:.0f}%" if five.known else "5h UNKNOWN")
        parts.append(f"7d {seven.used_percentage:.0f}%" if seven.known else "7d UNKNOWN")
        print(" · ".join(parts))
        return 0
    print(observation.render(now))
    # A payload that could not be read is not a reading. The report says so, but
    # a `--json` consumer reads the exit status, and 0 there is indistinguishable
    # from a clean observation.
    return 1 if observation.notes else 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
