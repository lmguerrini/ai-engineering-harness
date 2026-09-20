"""The one writer of CAPACITY.json, and the reader that quarantines.

A capacity record was writable by anything with a text editor, including every
lane-local script that wanted a pool to exist. **One writer** closes that: the
document this module writes is the shape it vouches for, and a file it did not
write is read as the 2.5.0 shape it is — with the difference stated as a note
rather than repaired on read, because a reader that rewrites is a second
writer and the record would have two of them.

Two decisions this module exists to hold:

*   **Per-element quarantine (D36).** A reader that refused a whole record
    because one pool entry was malformed would turn one bad edit into a total
    outage of the capacity view — and the view's whole job is to say what
    could not be established. So a malformed entry is a SENTENCE and a COUNT:
    reported, excluded from the pools, never dropped without trace.
*   **A writer never drops what it could not read.** `--keep-existing`
    re-reads the record and refuses — without touching the file — when any
    existing entry is quarantined. Overwriting a file that holds an entry this
    reader cannot parse is deciding, silently, that the entry is gone; that
    decision belongs to a person reading the quarantine sentence, not to a
    writer trying to be helpful.

Freshness is computed at READ time and never stored (D33): `check` judges each
pool's observation against its own source's horizon at the moment it is asked,
so a record cannot pre-decide when a later reader must stop trusting it.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import capacity
import resource_observation
from errors import IntegrityError

__all__ = [
    "SCHEMA",
    "CheckReport",
    "write",
    "read_pools",
    "check",
    "render",
]

#: The one schema this module writes and reads without comment. A document
#: naming another schema is reported as such rather than best-effort parsed:
#: a reader guessing at a schema it was never given is how a field quietly
#: changes meaning between the writer and the reader.
SCHEMA = "runtime-pack-capacity-1"


def _found(value: object) -> str:
    """How a refusal names what it found — bounded, never the value's own repr.

    Same rule as `resource_observation._found`, stated again here because it is
    private there: a value deep enough to overflow a line must not be echoed at
    full length by the message that refuses it.
    """
    if isinstance(value, bool) or value is None:
        return repr(value)
    if isinstance(value, (int, float)):
        return type(value).__name__
    if isinstance(value, str):
        return repr(value) if len(value) <= 40 else f"<{len(value)} characters>"
    if isinstance(value, dict):
        return f"<object of {len(value)} key(s)>"
    if isinstance(value, (list, tuple)):
        return f"<list of {len(value)} item(s)>"
    return type(value).__name__


def _key_name(key: object) -> str:
    """A pool id as a sentence may name it: printable and bounded."""
    if not isinstance(key, str):
        return type(key).__name__
    if not key.isprintable() or len(key) > 64:
        return f"<{len(key)} characters>"
    return key


def _bounded(text: str, limit: int = 200) -> str:
    """A sentence as a refusal's DETAIL may print it: one line, bounded."""
    single = " ".join(str(text).split())
    return single if len(single) <= limit else single[: limit - 1] + "…"


def _sentence(exc: BaseException) -> str:
    # `HxError.__str__` is its one-line cause, so a house refusal and the bare
    # `TypeError` a `Pool(**entry)` raises for a stray key both reduce to one
    # sentence here.
    return str(exc)


def _iso_utc(now: float) -> str:
    """An epoch moment as `YYYY-MM-DDTHH:MM:SSZ` — the house timestamp shape."""
    if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(now):
        raise IntegrityError("written_at is a finite moment", found=_found(now))
    return datetime.fromtimestamp(float(now), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: str | Path) -> object:
    """The JSON document at `path`, or a stated refusal."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise IntegrityError(
            "the capacity record cannot be read", path=str(path), error=type(exc).__name__
        ) from exc
    except ValueError as exc:  # not UTF-8 text, or not JSON
        raise IntegrityError(
            "the capacity record is not UTF-8 JSON", path=str(path), error=type(exc).__name__
        ) from exc


def _pools_from(document: object) -> tuple[list[capacity.Pool], list[str]]:
    """The document's readable pools, and one sentence per entry that is not.

    Per entry, not per file (D36): a quarantine sentence names the entry's
    position and its pool id when the id is readable, so a person can find the
    line they broke without parsing anything.
    """
    pools: list[capacity.Pool] = []
    quarantined: list[str] = []
    if not isinstance(document, dict) or not isinstance(document.get("pools"), list):
        return pools, ["the capacity record carries no pools list, so no pool could be read"]
    for index, entry in enumerate(document["pools"], start=1):
        named = ""
        if isinstance(entry, dict) and isinstance(entry.get("pool_id"), str):
            named = f" (pool_id {_key_name(entry['pool_id'])})"
        try:
            pools.append(capacity.Pool(**entry))
        except Exception as exc:
            # Broad by design: the whole point is that whatever is wrong with
            # THIS entry — an unknown key, an unparsable timestamp, a billing
            # mode nobody declared — becomes a sentence while the other entries
            # still load.
            quarantined.append(f"pool entry {index}{named} could not be read: {_sentence(exc)}")
    return pools, quarantined


def _document(
    *, pools: Iterable[capacity.Pool], reserve: capacity.Reserve | None,
    written_by: str, now: float,
) -> dict:
    """The document `write` persists — built and validated BEFORE anything opens.

    Every refusal this module can raise about content happens here, so a write
    that is refused has not created a file, and an existing record is left
    byte-identical.
    """
    if not isinstance(written_by, str) or not written_by.strip():
        raise IntegrityError(
            "a capacity record says who wrote it, and a blank attribution is nobody — a record "
            "nobody stands behind is the shape this module exists to replace")
    entries = list(pools)
    seen: set[str] = set()
    for position, pool in enumerate(entries, start=1):
        if not isinstance(pool, capacity.Pool):
            raise IntegrityError(
                "a capacity record holds pools; something else was offered to write",
                position=position, found=type(pool).__name__)
        if pool.pool_id in seen:
            raise IntegrityError(
                "a capacity record carries each pool once; two entries with one id are two "
                "readings racing to be the one a coordinator believes",
                pool_id=pool.pool_id)
        seen.add(pool.pool_id)
    if reserve is not None and not isinstance(reserve, capacity.Reserve):
        raise IntegrityError(
            "a capacity record's reserve is a Reserve or absent",
            found=type(reserve).__name__)
    return {
        "schema": SCHEMA,
        "written_at": _iso_utc(now),
        "written_by": written_by,
        "pools": [asdict(pool) for pool in entries],
        "reserve": None if reserve is None else asdict(reserve),
    }


def write(
    path: str | Path, *, pools: Iterable[capacity.Pool], reserve: capacity.Reserve | None,
    written_by: str, now: float,
) -> dict:
    """Write the record atomically, and return the document written.

    The swap is `os.replace` of a temporary file in the destination's own
    directory, so a reader never sees half a document and a failed write
    leaves the previous record intact.
    """
    document = _document(pools=pools, reserve=reserve, written_by=written_by, now=now)
    destination = Path(path)
    try:
        descriptor, temporary = tempfile.mkstemp(
            dir=str(destination.parent), prefix=destination.name + ".", suffix=".tmp")
    except OSError as exc:
        raise IntegrityError(
            "the capacity record could not be written",
            path=str(destination), error=type(exc).__name__) from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(document, indent=2) + "\n")
        os.replace(temporary, destination)
    except OSError as exc:
        try:
            os.unlink(temporary)  # a failed write leaves no residue beside the record
        except OSError:
            pass
        raise IntegrityError(
            "the capacity record could not be written",
            path=str(destination), error=type(exc).__name__) from exc
    return document


def read_pools(path: str | Path, *, now: float) -> tuple[list[capacity.Pool], list[str]]:
    """The record's readable pools and its quarantine sentences. Never writes.

    `now` is accepted because every reader in this pack takes the caller's
    clock rather than reading one of its own; reading a pool judges its SHAPE
    only, and the freshness verdict belongs to `check`, which reports it at
    the moment it is asked.
    """
    return _pools_from(_load(path))


@dataclass(frozen=True)
class CheckReport:
    """What one check found, as sentences and counts rather than an exit status."""

    schema_ok: bool
    pools_ok: int
    quarantined: tuple[str, ...]
    #: "declared", "absent", or "unreadable: <why>".
    reserve: str
    #: pool_id → FRESH | STALE | UNKNOWN | UNAVAILABLE, judged at `now`.
    freshness: dict[str, str]
    notes: tuple[str, ...]


def _reserve_state(document: object) -> str:
    raw = document.get("reserve") if isinstance(document, dict) else None
    if raw is None:
        return "absent"
    if not isinstance(raw, dict):
        return (f"unreadable: the reserve holds coordinator, result_consumption and "
                f"repair_and_audit, and this one is {_found(raw)}")
    try:
        capacity.Reserve(**raw)
    except Exception as exc:
        return f"unreadable: {_sentence(exc)}"
    return "declared"


def check(path: str | Path, *, now: float) -> CheckReport:
    """Read a record and report it — pools, quarantine, reserve, freshness.

    Read-only by construction: everything it needs is in the document, and the
    moment a checker repaired what it found it would be a third writer.
    """
    document = _load(path)
    notes: list[str] = []
    schema_ok = True
    if isinstance(document, dict) and "schema" in document:
        declared = document.get("schema")
        if declared != SCHEMA:
            schema_ok = False
            notes.append(f"the record declares the schema {_found(declared)}, not {SCHEMA!r}")
    else:
        # Reported, not repaired: rewriting a record on read would make this
        # reader a second writer, and a project can hold the 2.5.0 shape while
        # it decides whether to adopt this one.
        notes.append("no schema declared; read as a 2.5.0 document")
    pools, quarantined = _pools_from(document)
    return CheckReport(
        schema_ok=schema_ok,
        pools_ok=len(pools),
        quarantined=tuple(quarantined),
        reserve=_reserve_state(document),
        freshness={pool.pool_id: pool.freshness(now) for pool in pools},
        notes=tuple(notes),
    )


def render(report: CheckReport) -> str:
    """The report as text: a line per pool with its freshness, the quarantine
    sentences, the reserve's state, and any notes."""
    lines = [
        f"capacity record: schema {'ok' if report.schema_ok else 'NOT ok'}, "
        f"{report.pools_ok} pool(s) readable, {len(report.quarantined)} quarantined"
    ]
    for pool_id, verdict in report.freshness.items():
        lines.append(f"  {pool_id}: {verdict}")
    for sentence in report.quarantined:
        lines.append(f"  quarantined: {sentence}")
    lines.append(f"reserve: {report.reserve}")
    lines.extend(f"note: {note}" for note in report.notes)
    return "\n".join(lines)


def _observation_from(document: object) -> resource_observation.ResourceObservation:
    """One observation from either document shape this pack's readers emit.

    Detected by the `schema` key: a `runtime-pack-quota-1` document carries
    one, and a record — exactly what `ResourceObservation.as_record()`
    produces and what `resource_observation.py --json` prints — does not, and
    would refuse the key as unknown if it were handed to the quota reader.
    """
    if isinstance(document, dict) and document.get("schema") == resource_observation.QUOTA_SCHEMA:
        return resource_observation.from_provider_quota(document)
    return resource_observation.from_record(document)


#: What `--reserve` may state. A held-back quantity this vocabulary has no name
#: for is a quantity nobody accounts for, so an unknown name is a refusal
#: rather than a quiet drop.
_RESERVE_FIELDS = ("coordinator", "result_consumption", "repair_and_audit")


def _reserve_from(text: str) -> capacity.Reserve:
    parsed: dict[str, float] = {}
    for pair in text.split(","):
        name, separator, raw = pair.partition("=")
        name = name.strip()
        if not separator or name not in _RESERVE_FIELDS:
            raise IntegrityError(
                "--reserve is written coordinator=N,result_consumption=N,repair_and_audit=N",
                found=_found(pair))
        if name in parsed:
            raise IntegrityError(f"--reserve states {name} once", found=_found(pair))
        try:
            parsed[name] = float(raw)
        except ValueError as exc:
            raise IntegrityError(f"--reserve for {name} is a number", found=_found(raw)) from exc
    return capacity.Reserve(**parsed)


def _moment(text: str, *, what: str) -> float:
    """One moment as ISO8601 text or epoch seconds — a refusal, never a guess.

    A naive ISO moment is read as UTC rather than as local time, so a rehearsal
    that pinned `--now` as text does not get a different verdict from a
    different timezone.
    """
    try:
        moment = float(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
        except ValueError as exc:
            raise IntegrityError(
                f"{what} is ISO8601 or epoch seconds", found=_found(text)) from exc
        moment = (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()
    if not math.isfinite(moment):
        raise IntegrityError(f"{what} is a finite moment", found=_found(text))
    return moment


def _cli(argv: list[str]) -> int:
    """Check a capacity record, or write ONE pool to it.

    Usage: ``capacity_record.py check CAPACITY.json [--now ISO8601|EPOCH]
                         [--json]``
    or    ``capacity_record.py write CAPACITY.json --written-by NAME
                         --pool-from OBSERVATION.json --pool-id ID --kind KIND
                         --window WINDOW --window-name NAME [--billing-mode MODE]
                         [--provider-id ID] [--active-workers N]
                         [--reserve coordinator=N,result_consumption=N,
                          repair_and_audit=N] [--keep-existing] [--now ...]
                         [--dry-run]``

    Exit status: ``0`` the record checks clean / the write succeeded, ``1``
    something is quarantined or the schema is wrong, ``2`` a refusal.
    """
    import argparse
    import time

    parser = argparse.ArgumentParser(
        prog="capacity_record.py",
        description="Write and check the project capacity record — the only writer of CAPACITY.json.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    checking = commands.add_parser(
        "check", help="read a capacity record and report what it holds; writes nothing")
    checking.add_argument("path", metavar="CAPACITY.json")
    checking.add_argument("--now", metavar="ISO8601|EPOCH", default=None,
                          help="the moment freshness is judged at, instead of the clock")
    checking.add_argument("--json", action="store_true",
                          help="emit the report as a JSON document rather than text")

    writing = commands.add_parser(
        "write", help="write ONE pool to a capacity record, built from an observation")
    writing.add_argument("path", metavar="CAPACITY.json")
    writing.add_argument("--written-by", required=True, metavar="NAME",
                         help="who is making this record; the file names them")
    writing.add_argument("--pool-from", required=True, metavar="OBSERVATION.json",
                         help="a runtime-pack-quota-1 document, or a record "
                              "resource_observation.py --json prints")
    writing.add_argument("--pool-id", required=True, metavar="ID")
    writing.add_argument("--kind", required=True, choices=list(capacity.PoolKind.ALL))
    writing.add_argument("--window", required=True, choices=list(capacity.WindowKind.ALL))
    writing.add_argument("--window-name", required=True, metavar="NAME",
                         help="the observation window this pool is measured against")
    writing.add_argument("--billing-mode", metavar="MODE", default=None,
                         help="how this pool is paid for, instead of UNKNOWN")
    writing.add_argument("--provider-id", metavar="ID", default=None,
                         help="who was read, instead of the observation's own attribution")
    writing.add_argument("--active-workers", type=int, default=0, metavar="N",
                         help="dispatches already running against this pool")
    writing.add_argument("--reserve", metavar="NAME=N,NAME=N", default=None,
                         help="coordinator=N,result_consumption=N,repair_and_audit=N; "
                              "absent leaves the record with no reserve")
    writing.add_argument("--keep-existing", action="store_true",
                         help="keep the record's other readable pools instead of replacing the file")
    writing.add_argument("--now", metavar="ISO8601|EPOCH", default=None,
                         help="the moment written_at states and freshness is judged at")
    writing.add_argument("--dry-run", action="store_true",
                         help="print the document that would be written, and write nothing")
    args = parser.parse_args(argv)

    now = time.time() if args.now is None else _moment(args.now, what="--now")

    if args.command == "check":
        report = check(args.path, now=now)
        if args.json:
            print(json.dumps(asdict(report), indent=2))
        else:
            print(render(report))
        return 0 if report.schema_ok and not report.quarantined else 1

    observation = _observation_from(_load(args.pool_from))
    # `--provider-id` overrides; absent one, the reading says who was read
    # (D33), and UNKNOWN beside a figure that names its provider would be the
    # poorer attribution of the two this invocation has.
    provider_id = (args.provider_id if args.provider_id is not None
                   else observation.provider_id)
    pool = capacity.pool_from_observation(
        observation,
        pool_id=args.pool_id, kind=args.kind, window=args.window,
        window_name=args.window_name,
        billing_mode=capacity.UNKNOWN if args.billing_mode is None else args.billing_mode,
        provider_id=provider_id, active_workers=args.active_workers,
    )
    reserve = None if args.reserve is None else _reserve_from(args.reserve)
    pools = [pool]
    if args.keep_existing and Path(args.path).exists():
        existing, quarantined = read_pools(args.path, now=now)
        if quarantined:
            raise IntegrityError(
                f"the existing record holds {len(quarantined)} entry(ies) this reader could not "
                "parse, and a writer never silently drops a pool it could not read; fix or "
                "remove them first",
                path=str(args.path), first=_bounded(quarantined[0]),
            )
        # Same pool_id means this invocation is the newer reading of that pool;
        # every other id is kept as it was read.
        pools = [kept for kept in existing if kept.pool_id != pool.pool_id] + [pool]
    if args.dry_run:
        # The document, not a summary of it: what a dry run is FOR is showing a
        # person exactly the bytes that would land.
        print(json.dumps(_document(pools=pools, reserve=reserve,
                                   written_by=args.written_by, now=now), indent=2))
        return 0
    write(args.path, pools=pools, reserve=reserve, written_by=args.written_by, now=now)
    print(f"wrote {args.path}: {len(pools)} pool(s), schema {SCHEMA}")
    return 0


if __name__ == "__main__":
    import sys

    # Run the module, not a second copy of it. A file executed as a script is
    # `__main__`, and a sibling that imports it BY NAME gets a separate module
    # object with separate class objects — so an `isinstance` check across that
    # boundary is False for an object that is exactly that class. Imported
    # statically, by name, because a dynamic import would route around the
    # toolbelt's import-closure check.
    from errors import run_cli
    from capacity_record import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
