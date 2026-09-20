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

## The other two readers, and why they are the same kind of thing

`runtime-pack-quota-1` is the generic provider-side document an adapter's
observer emits: provider and billing-pool ids, the document's own
`observed_at`, and every window the source exposes. It is a **closed**
schema — an unknown key at any level is a refusal, numbers are finite, and
an unreadable payload never becomes an observation full of UNKNOWN windows,
because a provider document that could not be read must not become a reading
a writer then records as one. Percentages are DERIVED from the source's own
native remaining and limit when both are present (D33): a provider's stated
percentage may be coarse, so a stated figure that disagrees with the natives
by more than half a point is kept in a note and never in the number. A
window the source does not expose is `UNAVAILABLE`, never absent and never
zero. A human reading is the same contract with a person as the instrument —
percentages the operator reports, an `observed_at` they vouch for — and its
advisory note stays on the observation for good.

## Freshness is computed at read time, never stored

`freshness` is a verdict about a reading and a caller-supplied moment:
FRESH, STALE, UNKNOWN or UNAVAILABLE. It is derived from `observed_at` —
which is the document's own moment, never the clock — against the horizon
the reading's source carries. A reading from the future is UNKNOWN, not
fresh-by-overflow: a moment that has not happened cannot establish anything
about this one.

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
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from errors import IntegrityError
from provider_manifest import OBSERVER_SOURCES

__all__ = [
    "UNKNOWN",
    "SOURCE_STATUS_LINE",
    "SOURCE_PROVIDER_QUOTA",
    "SOURCE_HUMAN_READING",
    "SOURCE_HORIZONS",
    "DEFAULT_STALE_AFTER_SECONDS",
    "PROVENANCES",
    "FRESHNESS",
    "WINDOW_AVAILABILITIES",
    "QUOTA_SCHEMA",
    "Window",
    "ResourceObservation",
    "from_status_line",
    "from_provider_quota",
    "from_human_reading",
    "from_record",
    "append_observation",
]

UNKNOWN = "UNKNOWN"

#: Named so an observation says where it came from. A reading whose provenance
#: is not recorded cannot be re-derived when the surface changes.
SOURCE_STATUS_LINE = "claude-code/status-line-json"

#: The generic provider-side document an adapter's observer emits (D33). Both
#: new source names are drawn from `provider_manifest.OBSERVER_SOURCES` — the
#: declared reader vocabulary — rather than coined here, so a manifest can name
#: either reader without a Core edit. Checked at import and pinned by a test,
#: because a source name the registry has never heard of is a configuration no
#: manifest can declare.
SOURCE_PROVIDER_QUOTA = "provider-quota-json"
SOURCE_HUMAN_READING = "human-reading"
assert SOURCE_PROVIDER_QUOTA in OBSERVER_SOURCES and SOURCE_HUMAN_READING in OBSERVER_SOURCES

#: The one schema `from_provider_quota` reads. A document naming another
#: schema is refused for being another schema, the same rule
#: `provider_manifest.SCHEMA` applies.
QUOTA_SCHEMA = "runtime-pack-quota-1"

#: How old a reading from each source may be before it is STALE (D33: freshness
#: is first-class). A provider quota document is polled from a live endpoint
#: and gets the shortest horizon; a status line repaints on every render and
#: gets half an hour; a human reading is worth what the person vouches for and
#: gets two hours. Read at READER time, so a horizon change re-ages every
#: document already recorded.
SOURCE_HORIZONS: dict[str, float] = {
    SOURCE_STATUS_LINE: 1800.0,
    SOURCE_PROVIDER_QUOTA: 900.0,
    SOURCE_HUMAN_READING: 7200.0,
}

#: How a reading was obtained — a fact about the instrument, not the vendor.
#: Anything not positively named here is UNKNOWN.
PROVENANCES = (
    "official_client_hook",
    "client_local_file",
    "provider_endpoint",
    "dispatch_snapshot",
    "human_reading",
)

#: The four freshness verdicts (D33). Routing may consume a window as available
#: only when FRESH; STALE and UNKNOWN stay conservative.
FRESHNESS = ("FRESH", "STALE", "UNKNOWN", "UNAVAILABLE")

#: Whether a window is exposed by its source at all. An unexposed window is
#: UNAVAILABLE, never absent and never zero.
WINDOW_AVAILABILITIES = ("AVAILABLE", "UNAVAILABLE")

#: After this, a reading is reported stale. Long enough that a capability
#: boundary does not have to re-poll to act, short enough that it cannot be
#: mistaken for current. Polling more often than a capability boundary buys
#: nothing: the number moves with dispatches, not with wall clock.
DEFAULT_STALE_AFTER_SECONDS = 30 * 60

#: A quota document past this size is refused before it is parsed: a document
#: too large to hold is a finding in itself, and refusing it here keeps every
#: later message bounded.
QUOTA_MAX_BYTES = 1024 * 1024

#: A quota document is four levels deep (document, `windows`, a window, its
#: values). Anything twice that is not a quota document, and refusing the depth
#: keeps a refusal message from having to name what sits at the bottom of it.
QUOTA_MAX_DEPTH = 8


def _number(value: Any) -> float | str:
    """A number, or `UNKNOWN`. Never a coerced zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return UNKNOWN
    return float(value)


def _text(value: Any) -> str:
    return value if isinstance(value, str) and value.strip() else UNKNOWN


def _found(value: object) -> str:
    """How a refusal names what it found — bounded, never the value's own repr.

    Same rule as `provider_manifest._found`, stated again here because it is
    private there: a provider document can nest a value deep enough that
    `repr` overflows the interpreter before the refusal is printed, and a field
    this module exists to keep out of any output must not be echoed by the
    message that refuses it.
    """
    if isinstance(value, bool) or value is None:
        return repr(value)
    if isinstance(value, (int, float)):
        return type(value).__name__
    if isinstance(value, str):
        return f"<{len(value)} characters>"
    if isinstance(value, dict):
        return f"<object of {len(value)} key(s)>"
    if isinstance(value, (list, tuple)):
        return f"<list of {len(value)} item(s)>"
    return type(value).__name__


def _key_name(key: object) -> str:
    """A key as a refusal may name it: printable and bounded, or described."""
    if not isinstance(key, str):
        return type(key).__name__
    if not key.isprintable() or len(key) > 64:
        return f"<{len(key)} characters>"
    return key


def _finite_number(value: object) -> bool:
    """Whether this is a number a verdict may be computed from.

    `bool` is an `int` in Python and JSON parses `NaN`/`Infinity` into floats,
    so both shapes a document can smuggle in are refused here rather than
    downstream, where an age or a percentage would silently misbehave.
    """
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _quota_number(value: object, where: str) -> float:
    """A finite number out of a quota document, or a stated refusal."""
    if not _finite_number(value):
        raise IntegrityError(f"{where} is a finite number", found=_found(value))
    return float(value)


def _quota_text(value: object, where: str) -> str:
    """A non-empty printable string out of a quota document, or a refusal.

    Printable because `render` prints these fields: a control character in one
    is a second line a reader did not write. Bounded in the refusal for the
    same reason `_found` is.
    """
    if not isinstance(value, str) or not value:
        raise IntegrityError(f"{where} is a non-empty string", found=_found(value))
    if not value.isprintable():
        raise IntegrityError(f"{where} carries a non-printable character", found=_found(value))
    return value


def _refuse_unknown(mapping: Mapping, known: frozenset, where: str) -> None:
    """The closed-schema rule: an unread key is a refusal, never a drop."""
    unknown = sorted(set(mapping) - known)
    if unknown:
        raise IntegrityError(
            f"{where} declares field(s) this schema does not implement",
            unknown=", ".join(_key_name(name) for name in unknown),
            known=", ".join(sorted(known)),
        )


@dataclass(frozen=True)
class Window:
    """One rate-limit window, as read.

    `used_percentage` and `resets_at` are independently optional because the
    documented payload makes them so. The native fields carry what a provider
    actually counts in (D33): used and remaining percentage only where the
    denominator is established, native remaining/limit/unit otherwise.
    """

    name: str
    used_percentage: float | str = UNKNOWN
    resets_at: float | str = UNKNOWN
    remaining_percentage: float | str = UNKNOWN
    native_remaining: float | str = UNKNOWN
    native_limit: float | str = UNKNOWN
    native_unit: str = UNKNOWN
    availability: str = "AVAILABLE"

    def __post_init__(self) -> None:
        if self.availability not in WINDOW_AVAILABILITIES:
            # A misspelt availability is a window that silently reads as
            # exposed when its source never offered it — refused, not mapped.
            raise IntegrityError(
                "a window availability is AVAILABLE or UNAVAILABLE",
                found=_found(self.availability), known=", ".join(WINDOW_AVAILABILITIES),
            )

    @property
    def known(self) -> bool:
        return self.used_percentage != UNKNOWN

    def seconds_until_reset(self, now: float) -> float | str:
        if self.resets_at == UNKNOWN:
            return UNKNOWN
        return max(0.0, float(self.resets_at) - now)

    def describe(self, now: float) -> str:
        if self.availability == "UNAVAILABLE":
            return f"{self.name}: UNAVAILABLE (not exposed by the source)"
        if not self.known:
            return f"{self.name}: UNKNOWN (not reported by the client)"
        remaining = self.seconds_until_reset(now)
        when = "reset time UNKNOWN" if remaining == UNKNOWN else f"resets in {int(remaining) // 60}m"
        facts = [f"{self.used_percentage:.0f}% used"]
        if self.remaining_percentage != UNKNOWN:
            facts.append(f"{self.remaining_percentage:.0f}% remaining")
        if self.native_remaining != UNKNOWN and self.native_limit != UNKNOWN:
            # The native pair is what the provider actually counts; printing it
            # beside the percentage is what lets a reader check the derivation.
            facts.append(f"native {self.native_remaining:g}/{self.native_limit:g} {self.native_unit}")
        return f"{self.name}: {', '.join(facts)}, {when}"


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
    #: Who was read and on whose bill the reading counts (D33): one normalised
    #: observation per pool, so a capacity figure can be attributed without a
    #: lane-local parser inventing the mapping.
    provider_id: str = UNKNOWN
    billing_pool_id: str = UNKNOWN
    #: How the reading was obtained — a fact about the instrument. Kept on the
    #: observation because a reading whose provenance is not recorded cannot be
    #: re-derived when the surface changes.
    provenance: str = UNKNOWN
    #: How old this source's reading may be before it is STALE. The horizon
    #: travels WITH the reading so the verdict is about the source that made
    #: it, not about whoever happens to ask later.
    freshness_horizon_s: float | str = UNKNOWN

    def __post_init__(self) -> None:
        if self.provenance != UNKNOWN and self.provenance not in PROVENANCES:
            raise IntegrityError(
                "an observation provenance is a named reader or UNKNOWN",
                found=_found(self.provenance), known=", ".join(PROVENANCES),
            )

    def window(self, name: str) -> Window:
        for candidate in self.windows:
            if candidate.name == name:
                return candidate
        return Window(name)

    def age_seconds(self, now: float) -> float:
        return max(0.0, now - self.observed_at)

    def stale(self, now: float, *, after: float = DEFAULT_STALE_AFTER_SECONDS) -> bool:
        return self.age_seconds(now) > after

    def freshness(self, now: float) -> str:
        """FRESH, STALE, UNKNOWN or UNAVAILABLE — computed now, never stored.

        Storing a verdict would freeze a fact about one moment into the record
        and let a writer decide when a later reader must stop trusting it. The
        age is judged against the reading's own `observed_at` — a document's
        moment, not the clock — and a reading from the future is UNKNOWN: a
        moment that has not happened establishes nothing about this one.
        """
        if not self.windows or all(
            window.availability == "UNAVAILABLE" for window in self.windows
        ):
            return "UNAVAILABLE"
        if not _finite_number(self.observed_at):
            return "UNKNOWN"
        if not _finite_number(self.freshness_horizon_s):
            return "UNKNOWN"
        age = now - float(self.observed_at)
        if age < 0:
            return "UNKNOWN"
        if age > float(self.freshness_horizon_s):
            return "STALE"
        return "FRESH"

    def freshness_reason(self, now: float) -> str:
        """One sentence saying why `freshness` reached the verdict it did."""
        verdict = self.freshness(now)
        if verdict == "UNAVAILABLE":
            return "no window is exposed by this source, so there is nothing to age"
        if not _finite_number(self.observed_at):
            return "observed_at is not a finite number, so no age can be computed"
        if not _finite_number(self.freshness_horizon_s):
            return "no freshness horizon is recorded for this source, so no age can be judged stale"
        age = now - float(self.observed_at)
        horizon = int(round(float(self.freshness_horizon_s) / 60))
        if age < 0:
            return (
                f"observed_at is {int(round(-age))} s in the future, and a reading from "
                "the future is not evidence about now"
            )
        minutes = int(round(age / 60))
        if verdict == "STALE":
            return f"the reading is {minutes} min old, past its {horizon} min horizon"
        return f"the reading is {minutes} min old, within its {horizon} min horizon"

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
        # The verdict first: a reader who stops after one line must have the
        # fact that decides whether the rest may be trusted.
        lines.append(f"  freshness: {self.freshness(now)} — {self.freshness_reason(now)}")
        lines.append(
            f"  provider: {self.provider_id} · pool {self.billing_pool_id} "
            f"· provenance {self.provenance}"
        )
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
            "provider_id": self.provider_id,
            "billing_pool_id": self.billing_pool_id,
            "provenance": self.provenance,
            "freshness_horizon_s": self.freshness_horizon_s,
            "windows": [
                {
                    "name": window.name,
                    "used_percentage": window.used_percentage,
                    "resets_at": window.resets_at,
                    "remaining_percentage": window.remaining_percentage,
                    "native_remaining": window.native_remaining,
                    "native_limit": window.native_limit,
                    "native_unit": window.native_unit,
                    "availability": window.availability,
                }
                for window in self.windows
            ],
            "absent": list(self.absent),
            "notes": list(self.notes),
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
        # The status line is a hook the client's own documentation defines, so
        # the reading can say how it was obtained — and carries the horizon
        # this source's repaint cadence justifies, so freshness is judged
        # against the source rather than against whoever asks later.
        provenance="official_client_hook",
        freshness_horizon_s=SOURCE_HORIZONS[SOURCE_STATUS_LINE],
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


#: The closed vocabulary of a quota document, top level and per window. A key
#: outside either is a refusal, the same rule `provider_manifest` applies to a
#: manifest: an unread field is a declaration the provider believes it made.
_QUOTA_FIELDS = frozenset({
    "schema", "provider_id", "billing_pool_id", "observed_at", "windows", "notes",
})
_QUOTA_WINDOW_FIELDS = frozenset({
    "name", "availability", "used_percentage", "remaining_percentage",
    "native_remaining", "native_limit", "native_unit", "resets_at",
})


def _derive_percentages(fields: dict) -> tuple[dict, list[str]]:
    """Derive a window's percentages from its own natives, or decline to.

    The precedence, stated once and used by the reader: when BOTH native
    remaining and native limit are present the percentages are computed from
    them — a provider's stated percentage may be coarse, so its own counts win
    — and a stated figure that disagrees with the derived one by more than half
    a point is kept in a note and never in the number. When only one native is
    present there is no denominator, so the percentages stay UNKNOWN and
    nothing is inferred. Kept as a named seam so the precedence itself can be
    mutation-tested.
    """
    name = fields.get("name", "window")
    remaining = fields.get("native_remaining", UNKNOWN)
    limit = fields.get("native_limit", UNKNOWN)
    if remaining == UNKNOWN or limit == UNKNOWN:
        declined = dict(fields)
        notes: list[str] = []
        if (remaining == UNKNOWN) != (limit == UNKNOWN):
            # One native alone establishes no denominator. A stated percentage
            # is moved to a note rather than silently dropped: the source's own
            # claim stays readable without ever becoming the figure.
            for key in ("used_percentage", "remaining_percentage"):
                stated = fields.get(key, UNKNOWN)
                if stated != UNKNOWN:
                    which = key.split("_", 1)[0]
                    notes.append(
                        f"{name}: the source stated {stated:g}% {which} but only one native "
                        "value is present, so no percentage is derived"
                    )
                declined[key] = UNKNOWN
        return declined, notes
    used_derived = round(100.0 * (float(limit) - float(remaining)) / float(limit), 2)
    remaining_derived = round(100.0 * float(remaining) / float(limit), 2)
    notes = [f"{name}: percentages derived from the document's own native remaining and limit"]
    derived = dict(fields)
    for key, value in (("used_percentage", used_derived), ("remaining_percentage", remaining_derived)):
        stated = fields.get(key, UNKNOWN)
        if stated != UNKNOWN and abs(float(stated) - value) > 0.5:
            notes.append(
                f"{name}: the source stated {stated:g}%; derived {value:g}% from its own natives"
            )
        derived[key] = value
    return derived, notes


def _depth(value: object, level: int = 1) -> int:
    """Nesting depth of a decoded document, computed iteratively so the
    measurement itself cannot overflow on the shape it exists to refuse. The
    document is level 1, so a window's own values sit at level 4."""
    deepest = level
    pending = [(value, level)]
    while pending:
        current, at = pending.pop()
        deepest = max(deepest, at)
        if at > QUOTA_MAX_DEPTH:
            return at
        if isinstance(current, dict):
            pending.extend((child, at + 1) for child in current.values())
        elif isinstance(current, list):
            pending.extend((child, at + 1) for child in current)
    return deepest


def _horizon(horizon_s: float | None, source: str) -> float:
    """The caller's horizon, or the source's own. A stated one must be usable."""
    if horizon_s is None:
        # Read from SOURCE_HORIZONS at call time, not captured at import, so
        # the horizon a reading carries is the one in force when it was read.
        return SOURCE_HORIZONS[source]
    if not _finite_number(horizon_s) or horizon_s <= 0:
        raise IntegrityError(
            "a freshness horizon is a positive number of seconds",
            found=_found(horizon_s),
        )
    return float(horizon_s)


def from_provider_quota(
    payload: str | bytes | dict, *, horizon_s: float | None = None
) -> ResourceObservation:
    """One observation from a generic `runtime-pack-quota-1` document.

    The only provider-side input, emitted by an adapter's observer, and it is
    read STRICTLY: a payload that is not UTF-8, not JSON, not an object, names
    another schema, carries an unknown key at any level, a bool or non-finite
    number, nesting beyond `QUOTA_MAX_DEPTH` or a size beyond `QUOTA_MAX_BYTES`
    is a refusal — never an observation of UNKNOWN windows that a writer then
    records as a reading. `observed_at` is the document's own moment, never the
    clock, so the same document read later is the same reading, merely older.
    """
    if isinstance(payload, (str, bytes)) and len(payload) > QUOTA_MAX_BYTES:
        raise IntegrityError(
            "the quota document is larger than this reader will hold",
            size=len(payload), limit=QUOTA_MAX_BYTES,
        )
    if isinstance(payload, dict):
        document = payload
    else:
        try:
            text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        except UnicodeDecodeError as exc:
            raise IntegrityError(
                "the quota document is not UTF-8 text", error=type(exc).__name__
            ) from exc
        try:
            document = json.loads(text)
        except ValueError as exc:
            # JSONDecodeError is a ValueError; so is the refusal Python raises
            # for an integer literal beyond its digit limit, which is not a
            # JSONDecodeError.
            raise IntegrityError(
                "the quota document is not valid JSON", error=type(exc).__name__
            ) from exc
        except RecursionError as exc:
            raise IntegrityError(
                "the quota document is nested beyond what this reader will follow",
                limit=QUOTA_MAX_DEPTH,
            ) from exc
    if not isinstance(document, dict):
        raise IntegrityError("the quota document is a JSON object", found=_found(document))
    schema = document.get("schema")
    if schema != QUOTA_SCHEMA:
        # Decided before anything nested is read: a document of another schema
        # is refused for being another schema, not for the first nested field
        # this one happens to require.
        raise IntegrityError(
            "the quota document names a schema this reader does not implement",
            found=_found(schema), expected=QUOTA_SCHEMA,
        )
    if _depth(document) > QUOTA_MAX_DEPTH:
        raise IntegrityError(
            "the quota document is nested beyond what this reader will follow",
            limit=QUOTA_MAX_DEPTH,
        )
    _refuse_unknown(document, _QUOTA_FIELDS, "the quota document")

    provider_id = _quota_text(document.get("provider_id"), "quota provider_id")
    billing_pool_id = _quota_text(
        document.get("billing_pool_id"), "quota billing_pool_id"
    )
    observed_at = _quota_number(document.get("observed_at"), "quota observed_at")

    raw_notes = document.get("notes", [])
    if not isinstance(raw_notes, list):
        raise IntegrityError("quota notes is a list of strings", found=_found(raw_notes))
    notes = [
        _quota_text(note, f"quota notes[{position}]")
        for position, note in enumerate(raw_notes, start=1)
    ]

    raw_windows = document.get("windows")
    if not isinstance(raw_windows, list):
        raise IntegrityError("quota windows is a list", found=_found(raw_windows))
    windows: list[Window] = []
    for position, raw in enumerate(raw_windows, start=1):
        where = f"quota windows[{position}]"
        if not isinstance(raw, dict):
            raise IntegrityError(f"{where} is an object", found=_found(raw))
        _refuse_unknown(raw, _QUOTA_WINDOW_FIELDS, where)
        name = _quota_text(raw.get("name"), f"{where}.name")
        availability = raw.get("availability", "AVAILABLE")
        if availability not in WINDOW_AVAILABILITIES:
            raise IntegrityError(
                f"{where}.availability is AVAILABLE or UNAVAILABLE",
                found=_found(availability), known=", ".join(WINDOW_AVAILABILITIES),
            )
        numbers: dict[str, float | str] = {}
        for key in ("used_percentage", "remaining_percentage", "native_remaining",
                    "native_limit", "resets_at"):
            if key not in raw:
                numbers[key] = UNKNOWN
                continue
            if availability == "UNAVAILABLE":
                # An unexposed window carries no figures at all: a percentage
                # on a window the source says it does not expose would read as
                # a reading.
                raise IntegrityError(
                    f"{where} is UNAVAILABLE and carries {key}",
                    found=_found(raw[key]),
                )
            numbers[key] = _quota_number(raw[key], f"{where}.{key}")
        unit = UNKNOWN
        if "native_unit" in raw:
            if availability == "UNAVAILABLE":
                raise IntegrityError(
                    f"{where} is UNAVAILABLE and carries native_unit",
                    found=_found(raw["native_unit"]),
                )
            unit = _quota_text(raw["native_unit"], f"{where}.native_unit")
        for key in ("used_percentage", "remaining_percentage"):
            if numbers[key] != UNKNOWN and not 0 <= float(numbers[key]) <= 100:
                raise IntegrityError(
                    f"{where}.{key} is a percentage between 0 and 100",
                    found=_found(raw[key]),
                )
        if numbers["native_remaining"] != UNKNOWN and numbers["native_limit"] != UNKNOWN:
            if not 0 < float(numbers["native_limit"]):
                raise IntegrityError(
                    f"{where}.native_limit is greater than zero",
                    found=_found(raw["native_limit"]),
                )
            if float(numbers["native_remaining"]) > float(numbers["native_limit"]):
                raise IntegrityError(
                    f"{where}.native_remaining is at most its native_limit",
                    found=_found(raw["native_remaining"]),
                )
        elif (numbers["native_remaining"] == UNKNOWN
              and numbers["native_limit"] == UNKNOWN
              and numbers["used_percentage"] != UNKNOWN
              and numbers["remaining_percentage"] != UNKNOWN
              and abs(float(numbers["used_percentage"])
                      + float(numbers["remaining_percentage"]) - 100) > 0.5):
            # Only where no denominator exists does the pair have to be
            # self-consistent: with natives present, the natives settle it and
            # a coarse stated pair lands in a note instead.
            raise IntegrityError(
                f"{where} states a used and remaining percentage that do not sum to 100",
                found=_found(raw["used_percentage"]),
            )
        fields, window_notes = _derive_percentages({
            "name": name,
            "used_percentage": numbers["used_percentage"],
            "remaining_percentage": numbers["remaining_percentage"],
            "native_remaining": numbers["native_remaining"],
            "native_limit": numbers["native_limit"],
        })
        notes.extend(window_notes)
        windows.append(
            Window(
                name=name,
                used_percentage=fields["used_percentage"],
                resets_at=numbers["resets_at"],
                remaining_percentage=fields["remaining_percentage"],
                native_remaining=numbers["native_remaining"],
                native_limit=numbers["native_limit"],
                native_unit=unit,
                availability=availability,
            )
        )

    return ResourceObservation(
        source=SOURCE_PROVIDER_QUOTA,
        observed_at=observed_at,
        provider_id=provider_id,
        billing_pool_id=billing_pool_id,
        provenance="provider_endpoint",
        freshness_horizon_s=_horizon(horizon_s, SOURCE_PROVIDER_QUOTA),
        windows=tuple(windows),
        notes=tuple(notes),
    )


def from_human_reading(
    *,
    provider_id: str,
    billing_pool_id: str,
    windows: Mapping[str, float],
    observed_at: float,
    resets: Mapping[str, float] | None = None,
    horizon_s: float | None = None,
) -> ResourceObservation:
    """One observation from percentages a person read and vouches for.

    The weakest source this pack accepts, and accepted DELIBERATELY (D33):
    where no documented reader can be produced, an honest human reading with
    its own timestamp beats a hole in the record. It carries an advisory note
    for its whole life so no projection mistakes it for an instrumented one.
    """
    provider = _quota_text(provider_id, "the human reading provider_id")
    billing = _quota_text(billing_pool_id, "the human reading billing_pool_id")
    if not isinstance(windows, Mapping):
        raise IntegrityError(
            "a human reading's windows map a name to a used percentage",
            found=_found(windows),
        )
    reset_map = resets or {}
    if not isinstance(reset_map, Mapping):
        raise IntegrityError(
            "a human reading's resets map a name to a moment",
            found=_found(reset_map),
        )
    for name, moment in reset_map.items():
        if name not in windows:
            # A reset for a window nobody reported is a reading about nothing,
            # and accepting it would invent a window the operator never gave.
            raise IntegrityError(
                "a human reading's resets name a reported window",
                found=_key_name(name),
            )
    read: list[Window] = []
    for name, value in windows.items():
        where = f"the human reading window {_key_name(name)}"
        used = _quota_number(value, where)
        if not 0 <= used <= 100:
            raise IntegrityError(
                f"{where} is a used percentage between 0 and 100", found=_found(value)
            )
        read.append(
            Window(
                name=_quota_text(name, f"{where} name"),
                used_percentage=used,
                resets_at=(
                    _quota_number(reset_map[name], f"the reset for {_key_name(name)}")
                    if name in reset_map else UNKNOWN
                ),
            )
        )
    if not read:
        raise IntegrityError("a human reading reports at least one window")
    return ResourceObservation(
        source=SOURCE_HUMAN_READING,
        observed_at=_quota_number(observed_at, "the human reading observed_at"),
        provider_id=provider,
        billing_pool_id=billing,
        provenance="human_reading",
        freshness_horizon_s=_horizon(horizon_s, SOURCE_HUMAN_READING),
        windows=tuple(read),
        notes=("advisory, human-reported",),
    )


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


#: The record shape `as_record` writes. `from_record` refuses anything outside
#: it at either level, because a reader that skipped an unknown field would
#: rebuild a different observation than the one that was written.
_RECORD_FIELDS = frozenset({
    "source", "observed_at", "backend_family", "client_version", "model_observed",
    "effort_observed", "context_used_percentage", "provider_id", "billing_pool_id",
    "provenance", "freshness_horizon_s", "windows", "absent", "notes",
})
_WINDOW_RECORD_FIELDS = frozenset({
    "name", "used_percentage", "resets_at", "remaining_percentage",
    "native_remaining", "native_limit", "native_unit", "availability",
})


def from_record(record: Mapping) -> ResourceObservation:
    """Rebuild an observation from a record `as_record` wrote.

    The record shape IS the allowlist: an unknown key at either level is
    refused by name, so `from_record(x.as_record()) == x` for every reader and
    a record grown a field no reader implements is a stated refusal, never a
    silently slimmer observation.
    """
    if not isinstance(record, Mapping):
        raise IntegrityError("a record is a mapping", found=_found(record))
    _refuse_unknown(record, _RECORD_FIELDS, "the record")
    if "source" not in record or "observed_at" not in record:
        raise IntegrityError("a record carries its source and its observed_at")

    raw_windows = record.get("windows", [])
    if not isinstance(raw_windows, list):
        raise IntegrityError("a record's windows field is a list", found=_found(raw_windows))
    windows: list[Window] = []
    for position, raw in enumerate(raw_windows, start=1):
        where = f"the record window {position}"
        if not isinstance(raw, Mapping):
            raise IntegrityError(f"{where} is a mapping", found=_found(raw))
        _refuse_unknown(raw, _WINDOW_RECORD_FIELDS, where)
        windows.append(
            Window(
                name=raw.get("name", UNKNOWN),
                used_percentage=raw.get("used_percentage", UNKNOWN),
                resets_at=raw.get("resets_at", UNKNOWN),
                remaining_percentage=raw.get("remaining_percentage", UNKNOWN),
                native_remaining=raw.get("native_remaining", UNKNOWN),
                native_limit=raw.get("native_limit", UNKNOWN),
                native_unit=raw.get("native_unit", UNKNOWN),
                availability=raw.get("availability", "AVAILABLE"),
            )
        )

    return ResourceObservation(
        source=record["source"],
        observed_at=record["observed_at"],
        backend_family=record.get("backend_family", UNKNOWN),
        client_version=record.get("client_version", UNKNOWN),
        model_observed=record.get("model_observed", UNKNOWN),
        effort_observed=record.get("effort_observed", UNKNOWN),
        context_used_percentage=record.get("context_used_percentage", UNKNOWN),
        windows=tuple(windows),
        absent=tuple(record.get("absent", ())),
        notes=tuple(record.get("notes", ())),
        provider_id=record.get("provider_id", UNKNOWN),
        billing_pool_id=record.get("billing_pool_id", UNKNOWN),
        provenance=record.get("provenance", UNKNOWN),
        freshness_horizon_s=record.get("freshness_horizon_s", UNKNOWN),
    )


def _parse_assignments(pairs: list[str], what: str) -> dict[str, float]:
    """NAME=VALUE command-line strings into a mapping, or a stated refusal."""
    parsed: dict[str, float] = {}
    for pair in pairs:
        name, separator, raw = pair.partition("=")
        if not separator or not name:
            raise IntegrityError(f"{what} is written NAME=VALUE", found=_found(pair))
        try:
            parsed[name] = float(raw)
        except ValueError as exc:
            raise IntegrityError(
                f"{what} for {_key_name(name)} is a number", found=_found(raw)
            ) from exc
    return parsed


def _parse_moment(text: str) -> float:
    """One moment as ISO8601 text or epoch seconds — a refusal, never a guess."""
    from datetime import datetime

    try:
        moment = float(text)
    except ValueError:
        try:
            moment = datetime.fromisoformat(text).timestamp()
        except ValueError as exc:
            raise IntegrityError(
                "an observation moment is ISO8601 or epoch seconds",
                found=_found(text),
            ) from exc
    if not math.isfinite(moment):
        raise IntegrityError("an observation moment is a finite moment", found=_found(text))
    return moment


def _cli(argv: list[str]) -> int:
    """Read one reading — a status-line payload on stdin, a provider quota
    document, or a human reading — and print an observation.

    Usable *as* the status-line command, which is the point: the operator makes
    one explicit, reversible configuration change and the reading becomes
    available. Nothing here edits anyone's configuration — a tool that installs
    itself into a user's global settings to obtain telemetry is doing the thing
    this pack refuses to do.

    Stdin is read only where a flag asks for it — the status-line path (no new
    flag given) and `--provider-quota -` — so `--help` and the file-based
    readers answer without touching, or waiting on, anyone's input.
    """
    import argparse
    import sys
    import time

    parser = argparse.ArgumentParser(
        prog="resource_observation.py",
        description=(
            "Turn a Claude Code status-line payload, a provider quota document "
            "or a human reading into a routing observation."
        ),
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
    parser.add_argument(
        "--provider-quota",
        metavar="PATH",
        help=(
            "read a runtime-pack-quota-1 document from PATH ('-' for stdin) instead "
            "of a status-line payload"
        ),
    )
    parser.add_argument(
        "--horizon",
        type=float,
        metavar="SECONDS",
        help=(
            "the freshness horizon for --provider-quota or --human-reading, instead "
            "of the source's own"
        ),
    )
    parser.add_argument(
        "--now",
        type=float,
        metavar="EPOCH_SECONDS",
        help="the moment to judge freshness against, instead of the clock",
    )
    parser.add_argument(
        "--human-reading",
        action="store_true",
        help="record percentages a person read and vouches for, instead of reading a payload",
    )
    parser.add_argument("--provider-id", metavar="ID", help="the provider a human reading is about")
    parser.add_argument("--pool-id", metavar="ID", help="the billing pool a human reading is about")
    parser.add_argument(
        "--window",
        action="append",
        default=[],
        metavar="NAME=USED_PERCENT",
        help="one window of a human reading as NAME=USED_PERCENT; repeatable, at least one",
    )
    parser.add_argument(
        "--observed-at",
        metavar="ISO8601|EPOCH",
        help="when the human reading was taken",
    )
    parser.add_argument(
        "--resets",
        action="append",
        default=[],
        metavar="NAME=EPOCH",
        help="when one window of a human reading resets; repeatable, optional",
    )
    args = parser.parse_args(argv)

    if args.provider_quota is not None and args.human_reading:
        raise IntegrityError(
            "--provider-quota and --human-reading are two different readers of one "
            "reading; give one of them, not both"
        )

    now = time.time() if args.now is None else args.now

    if args.human_reading:
        missing = [
            name for name, value in (
                ("--provider-id", args.provider_id),
                ("--pool-id", args.pool_id),
                ("--observed-at", args.observed_at),
            )
            if value is None
        ]
        if missing or not args.window:
            absent = missing + ([] if args.window else ["--window"])
            raise IntegrityError(
                "a human reading needs --provider-id, --pool-id, --observed-at and at "
                f"least one --window; not given: {' '.join(absent)}"
            )
        observation = from_human_reading(
            provider_id=args.provider_id,
            billing_pool_id=args.pool_id,
            windows=_parse_assignments(args.window, "a used percentage"),
            observed_at=_parse_moment(args.observed_at),
            resets=_parse_assignments(args.resets, "a reset"),
            horizon_s=args.horizon,
        )
    elif args.provider_quota is not None:
        if args.provider_quota == "-":
            raw = sys.stdin.buffer.read()
        else:
            try:
                raw = Path(args.provider_quota).read_bytes()
            except OSError as exc:
                raise IntegrityError(
                    "the quota document cannot be read",
                    error=type(exc).__name__,
                ) from exc
        observation = from_provider_quota(raw, horizon_s=args.horizon)
    else:
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

    # Run the module, not a second copy of it. A file executed as a script is
    # `__main__`, and a sibling that imports it BY NAME gets a separate module
    # object with separate class objects — so an `isinstance` check across that
    # boundary is False for an object that is exactly that class. It crashed
    # `project_context.py --project` against a real consumer's contract, on a
    # shape the suite covers completely: tests import the module and never run
    # it as a script. Imported statically, by name, because a dynamic import
    # would route around the toolbelt's import-closure check.
    from errors import run_cli
    from resource_observation import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
