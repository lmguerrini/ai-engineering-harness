"""What models an execution surface is offering, read rather than remembered.

The Runtime Pack has never carried a model allowlist and this module does not
introduce one. That is the guarantee it exists to make explicit and checkable: a
previously unknown model identifier reaches a route report **without a Core
edit**, whatever it is called, in whatever alphabet, and no name is privileged
because somebody thought of it first.

Three things this release measured while it was being built, all of which the
design turned into rules rather than anecdotes:

*   **A discovery document is written by a client, and clients disagree.** The
    same account, at the same moment, listed nine models under one client version
    and eight under another; the ninth was the newest one. So a reading carries
    its PRODUCER, and a document produced by a client other than the one that
    will dispatch is reported as skewed rather than read as truth.
*   **Discovery is not availability.** A model present in the local document was
    refused by the provider on the installed client. `DISCOVERED` is the whole
    claim this module makes. Whether a configuration can actually start is
    `routing`'s availability axis, and its only positive evidence is a run.
*   **Inspection does not refresh.** The document this machine keeps is rewritten
    by a dispatch, not by asking. A reading therefore states its own age and
    never implies currency.

**No network.** This reads a path the caller supplies. The pack does not know how
to fetch a vendor's catalogue and should not learn: the adapter that dispatches
knows where its surface writes one, and the boundary between a pack that holds
rules and adapters that hold vendors is the reason no vendor's absence breaks
anything here.

## Shapes

The neutral shape is `{"schema": "runtime-pack-discovery-1", "models": [...]}`.
Anything else is read through a **field map the caller supplies**, defaulting to
conventional field NAMES — not model names. The distinction is the whole point:
`slug` and `context_window` are field names an adapter can describe; a list of
models would be a vocabulary that ages.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "UNKNOWN",
    "NEUTRAL_SCHEMA",
    "DEFAULT_FIELD_MAP",
    "DiscoveryError",
    "DiscoveredModel",
    "DiscoveryReading",
    "read",
    "merge",
]

UNKNOWN = "UNKNOWN"

#: The shape this pack owns. A document declaring it is read directly.
NEUTRAL_SCHEMA = "runtime-pack-discovery-1"

#: FIELD NAMES, tried in order. Not model names, and nothing here privileges any
#: vendor: an adapter whose document uses different field names passes its own
#: map. Every value is a key to look up, never a value to match.
DEFAULT_FIELD_MAP = {
    "models": ("models", "data", "items", "entries"),
    "identifier": ("identifier", "slug", "id", "name", "model"),
    "visibility": ("visibility", "listed"),
    "context_window": ("context_window", "context", "max_tokens"),
    "efforts": ("supported_reasoning_levels", "efforts", "reasoning_levels"),
    "effort_name": ("effort", "name", "level"),
    "default_effort": ("default_reasoning_level", "default_effort"),
    "producer": ("client_version", "producer", "written_by"),
    "observed_at": ("fetched_at", "observed_at", "written_at"),
}


class DiscoveryError(Exception):
    """A discovery document could not be read as one."""


@dataclass(frozen=True)
class DiscoveredModel:
    """One identifier an execution surface offered, and nothing more than that.

    `DISCOVERED` is the entire claim. Not available, not qualified, not
    supported: `policy/execution-boundaries.md` says a read of an undocumented
    provider surface may inform a routing preference and may never establish a
    qualification, a capability or a verdict, and this class is that sentence as
    a type.
    """

    identifier: str
    #: The vendor's own listing flag, verbatim and uninterpreted. Carried so a
    #: report can show it; never used to decide anything here.
    visibility: str = UNKNOWN
    #: ADVERTISED, not measured. The surface that reported this did not report
    #: running at it.
    context_window: str = UNKNOWN
    efforts: tuple[str, ...] = ()
    default_effort: str = UNKNOWN

    def sentence(self) -> str:
        return (
            f"{self.identifier} — DISCOVERED only (visibility {self.visibility}, advertised "
            f"context {self.context_window}, efforts {', '.join(self.efforts) or UNKNOWN})"
        )


@dataclass(frozen=True)
class DiscoveryReading:
    """One reading of one document, with everything that qualifies it."""

    source: str
    models: tuple[DiscoveredModel, ...] = ()
    #: Which client wrote the document. Compared against the client that will
    #: dispatch, because they differed here and the difference was the whole
    #: finding.
    producer: str = UNKNOWN
    observed_at: str = UNKNOWN
    read_at: str = UNKNOWN
    notes: tuple[str, ...] = ()

    def identifiers(self) -> tuple[str, ...]:
        return tuple(model.identifier for model in self.models)

    def find(self, identifier: str) -> "DiscoveredModel | None":
        for model in self.models:
            if model.identifier == identifier:
                return model
        return None

    def skew(self, dispatching_client: str) -> tuple[str, ...]:
        """Whether this document was written by the client that will dispatch.

        Measured: a document written by a newer client listed a model the
        installed client could not run, and the installed client's own rewrite
        did not list it at all. Reported rather than resolved — which document is
        right is a question only a dispatch answers.
        """
        if self.producer == UNKNOWN or not str(dispatching_client).strip():
            return (
                "the producing client version is not established, so whether this document "
                "describes what the dispatching client can run is UNKNOWN",
            )
        if self.producer != dispatching_client:
            return (
                f"this document was written by client {self.producer} and the dispatch will use "
                f"{dispatching_client}. The two have been observed to offer different model sets "
                f"for the same account, so membership here is not a claim about that client",
            )
        return ()

    def render(self) -> str:
        lines = [
            f"discovery reading: {self.source}",
            f"  produced by client {self.producer}, written {self.observed_at}, "
            f"read {self.read_at}",
            f"  {len(self.models)} identifier(s) DISCOVERED — discovery is not availability",
        ]
        lines.extend(f"    {model.sentence()}" for model in self.models)
        lines.extend(f"  note: {note}" for note in self.notes)
        return "\n".join(lines)


def _first(mapping: dict, names) -> object:
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def _text(value: object) -> str:
    if value is None:
        return UNKNOWN
    if isinstance(value, bool):
        return UNKNOWN
    text = str(value).strip()
    return text or UNKNOWN


def read(
    source: str | Path,
    *,
    field_map: "dict | None" = None,
    now: "str | None" = None,
) -> DiscoveryReading:
    """Read a discovery document. Never raises on content it cannot interpret.

    An entry with no identifier is dropped **with a note**, because a silent drop
    and an empty catalogue are the same output and mean opposite things. Every
    identifier is taken verbatim: no normalisation, no case folding, no
    validation against a shape. A model called `модель-7` or `x.y_z:9` is a model
    called that, and a pack that decided otherwise would have invented the closed
    vocabulary it promises not to have.
    """
    names = dict(DEFAULT_FIELD_MAP)
    for key, value in (field_map or {}).items():
        if key not in DEFAULT_FIELD_MAP:
            raise DiscoveryError(
                f"the field map names {key!r}, which nothing reads. Known: "
                f"{', '.join(sorted(DEFAULT_FIELD_MAP))}"
            )
        names[key] = tuple(value) if isinstance(value, (list, tuple)) else (value,)

    path = Path(source)
    read_at = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DiscoveryError(f"{path} is not a readable discovery document: {exc}") from exc
    if not isinstance(document, dict):
        raise DiscoveryError(
            f"{path} holds {type(document).__name__}, and a discovery document is an object "
            f"carrying a list of models"
        )

    notes: list[str] = []
    schema = document.get("schema")
    if schema is not None and schema != NEUTRAL_SCHEMA:
        notes.append(
            f"the document declares schema {schema!r}, which this release does not own; it was "
            f"read through the supplied field map and every field it does not carry is UNKNOWN"
        )
    entries = _first(document, names["models"])
    if not isinstance(entries, list):
        raise DiscoveryError(
            f"{path} carries no list of models under any of {', '.join(names['models'])}"
        )

    models: list[DiscoveredModel] = []
    for position, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            notes.append(f"entry {position} is not an object and was not read")
            continue
        identifier = _first(entry, names["identifier"])
        if identifier is None or not str(identifier).strip():
            notes.append(
                f"entry {position} carries no identifier under any of "
                f"{', '.join(names['identifier'])} and was dropped — a silent drop and an empty "
                f"catalogue are the same output and mean opposite things"
            )
            continue
        raw_efforts = _first(entry, names["efforts"])
        efforts: list[str] = []
        if isinstance(raw_efforts, list):
            for item in raw_efforts:
                if isinstance(item, dict):
                    value = _first(item, names["effort_name"])
                    if value is not None and str(value).strip():
                        efforts.append(str(value).strip())
                elif str(item).strip():
                    efforts.append(str(item).strip())
        models.append(
            DiscoveredModel(
                identifier=str(identifier),
                visibility=_text(_first(entry, names["visibility"])),
                context_window=_text(_first(entry, names["context_window"])),
                efforts=tuple(efforts),
                default_effort=_text(_first(entry, names["default_effort"])),
            )
        )

    duplicates = sorted({m.identifier for m in models
                         if [x.identifier for x in models].count(m.identifier) > 1})
    if duplicates:
        notes.append(
            f"the document lists {', '.join(duplicates)} more than once; every entry is kept, "
            f"because deciding which one is the real one is not this module's to make"
        )
    if not models:
        notes.append("the document lists no readable model; that is a reading, not an outage")

    return DiscoveryReading(
        source=str(path),
        models=tuple(models),
        producer=_text(_first(document, names["producer"])),
        observed_at=_text(_first(document, names["observed_at"])),
        read_at=read_at,
        notes=tuple(notes),
    )


def merge(current: DiscoveryReading, previous: DiscoveryReading) -> dict:
    """What changed between two readings — appeared, disappeared, unchanged.

    A model absent from the current reading is `disappeared` and NOT thereby
    unavailable: this release watched the same account offer different sets under
    two client versions within five minutes. Disappearance is a fact about a
    document. What it licenses is a re-read and, if it matters, a dispatch.
    """
    here, there = set(current.identifiers()), set(previous.identifiers())
    return {
        "appeared": tuple(sorted(here - there)),
        "disappeared": tuple(sorted(there - here)),
        "unchanged": tuple(sorted(here & there)),
        "note": (
            "a disappearance is a fact about a document, not a verdict about a model; the same "
            "account has been observed offering different sets under two client versions"
        ),
    }


def _cli(argv: list[str]) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="model_discovery.py",
        description="Read a model discovery document. Discovery is never availability.",
    )
    parser.add_argument("document", help="path to the discovery document")
    parser.add_argument("--dispatching-client", default="",
                        help="the client version that will dispatch, to report producer skew")
    parser.add_argument("--against", default=None,
                        help="a previous reading to diff against")
    parser.add_argument("--json", action="store_true", help="emit the reading as JSON")
    args = parser.parse_args(argv)

    try:
        reading = read(args.document)
    except DiscoveryError as exc:
        print(f"{exc}", file=sys.stderr)
        return 2

    skew = reading.skew(args.dispatching_client) if args.dispatching_client else ()
    if args.json:
        print(json.dumps({
            "source": reading.source,
            "producer": reading.producer,
            "observed_at": reading.observed_at,
            "read_at": reading.read_at,
            "models": [
                {
                    "identifier": model.identifier,
                    "visibility": model.visibility,
                    "context_window": model.context_window,
                    "efforts": list(model.efforts),
                    "default_effort": model.default_effort,
                    "state": "DISCOVERED",
                }
                for model in reading.models
            ],
            "notes": list(reading.notes) + list(skew),
        }, indent=2))
        return 0

    print(reading.render())
    for note in skew:
        print(f"  SKEW: {note}")
    if args.against:
        try:
            print()
            for key, value in merge(reading, read(args.against)).items():
                print(f"  {key}: {value}")
        except DiscoveryError as exc:
            print(f"  the previous reading could not be read: {exc}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    import sys

    from errors import run_cli
    from model_discovery import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
