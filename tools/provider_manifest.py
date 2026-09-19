"""A provider is one declared manifest; billing safety is a proof about the
exact route, not a property anyone gets to assert about a name.

`docs/RP2.6.0-DESIGN-P1-provider-registry-and-billing-safety.md` (D29-D32,
D34) answers a registry that had been growing as a fixed slot per vendor: a
fourth provider was a Core release, and "subscription" was written on the pool
rather than proven about the route that would actually carry the dispatch.
Neither defect is hypothetical here — D29 exists because a founder-authorised
fixed subscription and a pay-as-you-go fallback of the SAME vendor are
mechanically indistinguishable unless something checks the route rather than
the label.

**The registry has no slots and no count (D31).** A provider is a JSON
document, schema `runtime-pack-provider-1`, a project declares under
`PROJECT.yaml providers:`. This module validates one manifest completely —
closed vocabularies, unknown keys refused at every level, non-slug
identifiers refused — and never asks how many providers a project has
declared or which one a dispatch should prefer. Adding a fourth conforming
provider changes no line here.

**Registration routes nothing (D31, D34).** A manifest that validates is
UNPROBED: no credential is assumed, no billing mode is assumed authorised, and
the dormant fixture this release ships (`templates/providers/`) proves the
seam by registering unchanged and staying `NOT_ROUTABLE` until a founder
records `authorised_by`, a credential reference and a capacity observer — all
data this module reads, never data it invents. `routability` judges billing
and credential facts only; whether a route is *qualified* to carry a task
class is the routing eligibility report's question, a sibling task, and this
module never answers it.

**Billing safety is a fingerprint of the exact route, computed fresh every
time (D29, D32).** `fingerprint` never reads a cached verdict and never asks
the manifest what it believes about itself: `overage_enabled`,
`auto_topup_enabled` and `metered_fallback_enabled` are each exactly `True`,
`False` or `UNKNOWN`, and `routability` treats `UNKNOWN` on any of them as a
hard deny for every billed route — `local` alone ignores an unknown flag,
because a local route has no billing pool to overrun, while a flag established
`True` denies it like any other — the same rule `backend_contract.UNKNOWN`
states for every other first-class unknown in this pack: an unread field is
not a cleared one.
`overage_enabled` and `auto_topup_enabled` are read straight from the
manifest. `metered_fallback_enabled` is read differently, because it is the
one flag an environment can actually falsify: the manifest's own declaration
is a claim about the PLAN, and `true` there is final — no environment makes a
plan cleaner than its author admits it is. A declared `false` is a claim this
module still checks, by inspecting the environment for the credential names
the manifest itself asked to forbid; a declared `null` means the author never
made the claim at all, so a CLEAN inspection cannot clear it — `null` reads
`UNKNOWN` against a clean environment. Positive evidence runs the other way
whatever was declared: a metered credential name found in the environment
makes the flag `True` under `false` and under `null` alike. A caller that
passes no environment to inspect gets `UNKNOWN`, never an optimistic default.

**A credential reference is a NAME, never a value.** `credential.env_file_ref`
names the environment variable that holds a file path; it is validated as an
environment-variable identifier (`^[A-Za-z_][A-Za-z0-9_]*$`) and refused
otherwise, so a path, a Windows drive, a `~`-relative shorthand or a
space-separated phrase is refused at validation rather than read as a name.
No fingerprint field, no rendered report and no CLI output this module
produces ever carries an environment variable's VALUE — only variable names
and the facts they establish.

## What this module must never decide

It does not choose which provider a dispatch goes to, does not contact a
network, does not read a credential's value, does not remember a route it
computed, and does not decide that a routable route is a good idea to use
right now — that is capacity and the coordinator's job, elsewhere. It answers
one question, honestly: given exactly what this manifest, this environment and
this client configuration establish, is this route provably safe to bill as
what it claims to be?
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import adapter_pin
import backend_contract
from errors import IntegrityError, PreconditionError

__all__ = [
    "SCHEMA",
    "PROTOCOLS",
    "BILLING_MODES",
    "WINDOW_NAMES",
    "OBSERVER_SOURCES",
    "CREDENTIAL_KINDS",
    "UNKNOWN",
    "ROUTABLE",
    "NOT_ROUTABLE_BILLING",
    "NOT_ROUTABLE_UNAUTHORISED",
    "NOT_ROUTABLE_CREDENTIAL",
    "NOT_ROUTABLE_UNKNOWN",
    "DISPOSITIONS",
    "Surface",
    "Credential",
    "Billing",
    "CapacityObserver",
    "ProviderManifest",
    "RouteFingerprint",
    "Routability",
    "load",
    "manifest_digest",
    "fingerprint",
    "routability",
    "render",
]

#: The one schema this module reads. A document naming another schema is not
#: read partially; it is refused, the same rule `pack_pin` applies to a digest
#: algorithm this module never computed.
SCHEMA = "runtime-pack-provider-1"

#: D31: the supported protocol vocabulary. Adding a third is a Core change,
#: stated here as the bounded edge of the seam rather than hidden in a manifest
#: value nobody checks.
PROTOCOLS = ("anthropic-compatible", "openai-compatible")

#: D29: the prohibited condition is METERED billing, never the protocol or the
#: vendor. Anything not positively named here is UNKNOWN, and UNKNOWN is HARD
#: DENY — never read as "presumably fine".
BILLING_MODES = ("subscription", "local", "prepaid_existing", "metered_api")

WINDOW_NAMES = ("rolling_5h", "seven_day", "weekly", "monthly", "none")

#: D33: the documented readers a capacity observer configuration may name.
#: Not read here — this module validates the declaration, never the reading.
OBSERVER_SOURCES = (
    "provider-quota-json",
    "client-status-line",
    "client-local-file",
    "dispatch-snapshot",
    "human-reading",
)

CREDENTIAL_KINDS = ("subscription_key", "session_token")

#: The one canonical *not established* reading, shared with the rest of the
#: toolbelt rather than a second spelling of the same claim.
UNKNOWN = backend_contract.UNKNOWN

ROUTABLE = "ROUTABLE"
NOT_ROUTABLE_BILLING = "NOT_ROUTABLE_BILLING"
NOT_ROUTABLE_UNAUTHORISED = "NOT_ROUTABLE_UNAUTHORISED"
NOT_ROUTABLE_CREDENTIAL = "NOT_ROUTABLE_CREDENTIAL"
NOT_ROUTABLE_UNKNOWN = "NOT_ROUTABLE_UNKNOWN"

DISPOSITIONS = (
    ROUTABLE,
    NOT_ROUTABLE_BILLING,
    NOT_ROUTABLE_UNAUTHORISED,
    NOT_ROUTABLE_CREDENTIAL,
    NOT_ROUTABLE_UNKNOWN,
)

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")

#: An environment-variable identifier — the shape `env_file_ref` must have. A
#: path, a Windows drive, a `~`-relative shorthand and a space-separated phrase
#: all fail this, which is the point: the field names a variable, never a value.
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: An environment variable NAME shaped like a metered credential, independent
#: of anything a manifest declared. A structural heuristic, never a substitute
#: for `credential.generic_env_forbidden`: it catches a poisoning name the
#: manifest's author never thought to list, and an empty forbidden list still
#: is not the same claim as a checked, clean one.
_METERED_ENV_NAME_SUFFIXES = ("_API_KEY", "_ENV_KEY")

#: A bare hostname: labels of alphanumerics and internal hyphens, joined by
#: dots. No scheme (a colon fails this), no path (a slash fails this), no port.
_GATEWAY = re.compile(
    r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
)

_TOP_LEVEL_FIELDS = frozenset({
    "schema", "provider_id", "vendor", "gateway", "surfaces", "adapter",
    "credential", "billing", "capacity_observer", "discovery", "private_terms",
})
_SURFACE_FIELDS = frozenset({"surface", "client", "protocol"})
_CREDENTIAL_FIELDS = frozenset({"kind", "env_file_ref", "generic_env_forbidden"})
_BILLING_FIELDS = frozenset({
    "billing_mode", "billing_pool_id", "windows", "authorised_by",
    "overage_enabled", "auto_topup_enabled", "metered_fallback_enabled",
})
_OBSERVER_FIELDS = frozenset({"source", "freshness_horizon_s", "command"})


def _found(value: object) -> str:
    """How a refusal names what it found — bounded, never the value's own repr.

    A container is described by type and size and a string by its length: a
    document can nest a value deep enough that `repr` overflows the interpreter
    before the refusal is printed, and a field this module exists to keep out
    of any output must not be echoed by the message that refuses it.
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


def _is_slug(value: object) -> bool:
    return isinstance(value, str) and bool(_SLUG.fullmatch(value))


def _expect_mapping(value: object, where: str) -> dict:
    if not isinstance(value, dict):
        raise IntegrityError(f"{where} is missing or not a mapping", found=type(value).__name__)
    return value


def _expect_list(value: object, where: str) -> list:
    if not isinstance(value, list):
        raise IntegrityError(f"{where} is missing or not a list", found=_found(value))
    return value


def _expect_str(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise IntegrityError(f"{where} is missing or not a non-empty string", found=_found(value))
    if not value.isprintable():
        # A control or line-separating character in a field that `render` prints
        # is a second line a reader did not write; refused rather than escaped.
        raise IntegrityError(f"{where} carries a non-printable character", found=f"<{len(value)} characters>")
    return value


def _key_name(key: object) -> str:
    """A key as a refusal may name it: printable, bounded, or described.

    Keys are names a reader wrote, so a refusal may usually repeat one — but a
    key can be as long or as unprintable as any value, and the message that
    refuses it must stay one line of bounded length."""
    if not isinstance(key, str):
        return type(key).__name__
    if not key.isprintable() or len(key) > 64:
        return f"<{len(key)} characters>"
    return key


def _refuse_unknown(mapping: dict, known: frozenset, where: str) -> None:
    unknown = sorted(set(mapping) - known)
    if unknown:
        # An unread field is a declaration the project believes it made — the
        # same rule `adapter_pin.declarations_from` applies to `adapters:`.
        raise IntegrityError(
            f"{where} declares field(s) this schema does not implement",
            unknown=", ".join(_key_name(name) for name in unknown), known=", ".join(sorted(known)),
        )


@dataclass(frozen=True)
class Surface:
    """One execution surface this provider is reached through, and the
    protocol it speaks. Which surface a dispatch actually uses is
    `fingerprint`'s `surface_index`, never guessed here."""

    surface: str
    client: str
    protocol: str

    def __post_init__(self) -> None:
        if not isinstance(self.surface, str) or not self.surface:
            raise IntegrityError("a surface entry names its surface", found=_found(self.surface))
        if not isinstance(self.client, str) or not self.client:
            raise IntegrityError("a surface entry names its client", found=_found(self.client))
        if self.protocol not in PROTOCOLS:
            raise IntegrityError(
                "a surface protocol is one of the two this release supports; adding a third "
                "is a Core change (D31), never a value a manifest can just declare",
                found=_found(self.protocol), known=", ".join(PROTOCOLS),
            )


@dataclass(frozen=True)
class Credential:
    """A reference, never a value. `env_file_ref` names the environment
    variable that HOLDS a file path; it is refused outright if it looks like
    the path or the value itself."""

    kind: str
    env_file_ref: str | None
    generic_env_forbidden: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in CREDENTIAL_KINDS:
            raise IntegrityError(
                "credential.kind is not one of the declared kinds",
                found=_found(self.kind), known=", ".join(CREDENTIAL_KINDS),
            )
        if self.env_file_ref is not None:
            if not isinstance(self.env_file_ref, str) or not _ENV_NAME.fullmatch(self.env_file_ref):
                raise IntegrityError(
                    "credential.env_file_ref names the environment variable that HOLDS a file "
                    "path — an identifier matching ^[A-Za-z_][A-Za-z0-9_]*$ — and it must never "
                    "be the path or the value itself; the offending text is not echoed, because "
                    "it may be exactly the value this field exists to keep out of any output",
                    found=(f"<{len(self.env_file_ref)} characters>" if isinstance(self.env_file_ref, str)
                           else type(self.env_file_ref).__name__),
                )
        if not isinstance(self.generic_env_forbidden, tuple) or not all(
            isinstance(name, str) and _ENV_NAME.fullmatch(name) for name in self.generic_env_forbidden
        ):
            raise IntegrityError(
                "credential.generic_env_forbidden is a list of environment variable NAMES",
                found=_found(self.generic_env_forbidden),
            )


@dataclass(frozen=True)
class Billing:
    """The mode this route bills under, and the three negative facts a
    `subscription` route must prove rather than assume (D29).

    `metered_fallback_enabled` is a DECLARATION about the plan, not a reading:
    `true` says the author admits a metered fallback exists, and `fingerprint`
    treats that as final; `false` says the author asserts there is none, and
    `fingerprint` still checks it against the environment before believing it;
    `null` says the author never made the claim, and a clean inspection does not
    manufacture one — it reads `UNKNOWN` against a clean environment, while a
    poisoned environment makes it `True` exactly as it would a declared
    `false`: positive evidence of a metered path outranks every declaration."""

    billing_mode: str
    billing_pool_id: str
    windows: tuple[str, ...] = ()
    authorised_by: str | None = None
    overage_enabled: bool | None = None
    auto_topup_enabled: bool | None = None
    metered_fallback_enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.billing_mode not in BILLING_MODES:
            raise IntegrityError(
                "billing.billing_mode is not established or is outside the vocabulary; anything "
                "not positively named here is UNKNOWN and UNKNOWN is HARD DENY (D29)",
                found=_found(self.billing_mode), known=", ".join(BILLING_MODES),
            )
        if not _is_slug(self.billing_pool_id):
            raise IntegrityError(
                "billing.billing_pool_id is not a slug", found=_found(self.billing_pool_id)
            )
        if not isinstance(self.windows, tuple) or not all(
            window in WINDOW_NAMES for window in self.windows
        ):
            raise IntegrityError(
                "billing.windows names a window outside the vocabulary",
                found=_found(self.windows), known=", ".join(WINDOW_NAMES),
            )
        if self.authorised_by is not None and (
            not isinstance(self.authorised_by, str) or not self.authorised_by.strip()
            or not self.authorised_by.isprintable() or self.authorised_by.strip() == UNKNOWN
        ):
            raise IntegrityError(
                "billing.authorised_by is a decision reference string or null; an empty or "
                "whitespace-only value is not a decision reference, the same rule every other "
                "string field in this schema uses",
                found=_found(self.authorised_by),
            )
        for name in ("overage_enabled", "auto_topup_enabled", "metered_fallback_enabled"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise IntegrityError(f"billing.{name} is true, false or null", found=_found(value))


@dataclass(frozen=True)
class CapacityObserver:
    """How this provider's remaining capacity would be read, declared but not
    read here — D33 governs the reader; this is only its configuration."""

    source: str
    freshness_horizon_s: int
    command: str | None = None

    def __post_init__(self) -> None:
        if self.source not in OBSERVER_SOURCES:
            raise IntegrityError(
                "capacity_observer.source is outside the vocabulary",
                found=_found(self.source), known=", ".join(OBSERVER_SOURCES),
            )
        if (not isinstance(self.freshness_horizon_s, int)
                or isinstance(self.freshness_horizon_s, bool)
                or self.freshness_horizon_s <= 0):
            raise IntegrityError(
                "capacity_observer.freshness_horizon_s is a positive integer",
                found=_found(self.freshness_horizon_s),
            )
        if self.command is not None and not isinstance(self.command, str):
            raise IntegrityError("capacity_observer.command is a string or null", found=_found(self.command))


@dataclass(frozen=True)
class ProviderManifest:
    """One provider, exactly as a project declared it. Validation is
    everything this class does with the data — it never contacts the gateway,
    never reads a credential's value, and never asks whether the adapter it
    names actually exists (that is a caller's contract, not this one's)."""

    schema: str
    provider_id: str
    vendor: str
    gateway: str
    surfaces: tuple[Surface, ...]
    adapter: str
    credential: Credential
    billing: Billing
    capacity_observer: CapacityObserver | None = None
    #: A path relative to the project, resolved by the caller — never read
    #: here, and never absolute or home-relative: a manifest is project-local
    #: data and must not point outside it.
    discovery: str | None = None
    private_terms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise IntegrityError(
                "manifest.schema is not the one this module reads", found=_found(self.schema), expected=SCHEMA
            )
        if not _is_slug(self.provider_id):
            raise IntegrityError("provider_id is not a slug", found=_found(self.provider_id))
        if not _is_slug(self.vendor):
            raise IntegrityError("vendor is not a slug", found=_found(self.vendor))
        if not isinstance(self.gateway, str) or not _GATEWAY.fullmatch(self.gateway):
            raise IntegrityError(
                "gateway is a bare hostname — no scheme, no path, no port", found=_found(self.gateway)
            )
        if not self.surfaces:
            raise IntegrityError("a manifest declares at least one surface")
        if not _is_slug(self.adapter):
            raise IntegrityError("adapter is not a slug", found=_found(self.adapter))
        if self.billing.billing_pool_id == self.provider_id:
            raise IntegrityError(
                "billing.billing_pool_id must differ from provider_id; a pool sharing the "
                "provider's own identity is how independent billing gets conflated with routing",
                provider_id=self.provider_id,
            )
        if self.discovery is not None:
            if not isinstance(self.discovery, str) or not self.discovery:
                raise IntegrityError(
                    "discovery is a relative path string or null", found=_found(self.discovery)
                )
            segments = self.discovery.replace("\\", "/").split("/")
            if (self.discovery.startswith(("/", "~", "\\")) or ".." in segments
                    or re.match(r"^[A-Za-z]:", self.discovery)):
                raise IntegrityError(
                    "discovery is a path relative to the project, resolved by the caller; an "
                    "absolute, home-relative, drive-rooted or parent-escaping path is refused "
                    "because a manifest is project-local data and must not point outside it",
                    found=_found(self.discovery),
                )
        if not isinstance(self.private_terms, tuple) or not all(
            isinstance(term, str) and term for term in self.private_terms
        ):
            raise IntegrityError("private_terms is a list of words", found=_found(self.private_terms))

    @classmethod
    def from_mapping(cls, mapping: object) -> "ProviderManifest":
        """Parse and validate a manifest. Every malformed field raises rather
        than being dropped — the same rule `adapter_pin.declarations_from`
        applies, for the same reason: a checker that skips what it could not
        parse reports "validated" while having validated less than it read."""
        top = _expect_mapping(mapping, "manifest")

        schema = top.get("schema")
        if schema != SCHEMA:
            # Decided before anything nested is read: a document of another
            # schema is refused for being another schema, not for the first
            # nested field this one happens to require.
            raise IntegrityError(
                "manifest.schema is not the one this module reads", found=_found(schema), expected=SCHEMA
            )
        _refuse_unknown(top, _TOP_LEVEL_FIELDS, "manifest")

        raw_surfaces = _expect_list(top.get("surfaces"), "manifest.surfaces")
        surfaces = []
        for position, entry in enumerate(raw_surfaces, start=1):
            where = f"manifest.surfaces[{position}]"
            entry = _expect_mapping(entry, where)
            _refuse_unknown(entry, _SURFACE_FIELDS, where)
            surfaces.append(Surface(
                surface=_expect_str(entry.get("surface"), f"{where}.surface"),
                client=_expect_str(entry.get("client"), f"{where}.client"),
                protocol=_expect_str(entry.get("protocol"), f"{where}.protocol"),
            ))

        credential_map = _expect_mapping(top.get("credential"), "manifest.credential")
        _refuse_unknown(credential_map, _CREDENTIAL_FIELDS, "manifest.credential")
        env_file_ref = credential_map.get("env_file_ref")
        if env_file_ref is not None and not isinstance(env_file_ref, str):
            raise IntegrityError(
                "manifest.credential.env_file_ref is a string or null; the offending content is "
                "not echoed", found=type(env_file_ref).__name__
            )
        forbidden = _expect_list(
            credential_map.get("generic_env_forbidden"), "manifest.credential.generic_env_forbidden"
        )
        credential = Credential(
            kind=_expect_str(credential_map.get("kind"), "manifest.credential.kind"),
            env_file_ref=env_file_ref,
            generic_env_forbidden=tuple(forbidden),
        )

        billing_map = _expect_mapping(top.get("billing"), "manifest.billing")
        _refuse_unknown(billing_map, _BILLING_FIELDS, "manifest.billing")
        windows = _expect_list(billing_map.get("windows"), "manifest.billing.windows")
        authorised_by = billing_map.get("authorised_by")
        if authorised_by is not None and not isinstance(authorised_by, str):
            raise IntegrityError(
                "manifest.billing.authorised_by is a string or null", found=_found(authorised_by)
            )
        billing = Billing(
            billing_mode=_expect_str(billing_map.get("billing_mode"), "manifest.billing.billing_mode"),
            billing_pool_id=_expect_str(
                billing_map.get("billing_pool_id"), "manifest.billing.billing_pool_id"
            ),
            windows=tuple(windows),
            authorised_by=authorised_by,
            overage_enabled=billing_map.get("overage_enabled"),
            auto_topup_enabled=billing_map.get("auto_topup_enabled"),
            metered_fallback_enabled=billing_map.get("metered_fallback_enabled"),
        )

        raw_observer = top.get("capacity_observer")
        capacity_observer = None
        if raw_observer is not None:
            observer_map = _expect_mapping(raw_observer, "manifest.capacity_observer")
            _refuse_unknown(observer_map, _OBSERVER_FIELDS, "manifest.capacity_observer")
            command = observer_map.get("command")
            if command is not None and not isinstance(command, str):
                raise IntegrityError(
                    "manifest.capacity_observer.command is a string or null", found=_found(command)
                )
            capacity_observer = CapacityObserver(
                source=_expect_str(observer_map.get("source"), "manifest.capacity_observer.source"),
                freshness_horizon_s=observer_map.get("freshness_horizon_s"),
                command=command,
            )

        discovery = top.get("discovery")
        if discovery is not None and not isinstance(discovery, str):
            raise IntegrityError("manifest.discovery is a string or null", found=_found(discovery))

        private_terms = _expect_list(top.get("private_terms"), "manifest.private_terms")

        return cls(
            schema=schema,
            provider_id=_expect_str(top.get("provider_id"), "manifest.provider_id"),
            vendor=_expect_str(top.get("vendor"), "manifest.vendor"),
            gateway=_expect_str(top.get("gateway"), "manifest.gateway"),
            surfaces=tuple(surfaces),
            adapter=_expect_str(top.get("adapter"), "manifest.adapter"),
            credential=credential,
            billing=billing,
            capacity_observer=capacity_observer,
            discovery=discovery,
            private_terms=tuple(private_terms),
        )


def load(path: str | Path) -> ProviderManifest:
    """A validated manifest from a JSON file, or a stated refusal.

    Read in one shot, the same choice `adapter_pin.file_digest` makes: a
    manifest too large to hold is a finding in itself.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise IntegrityError("provider manifest cannot be read", path=str(path), error=str(exc)) from exc
    try:
        payload = json.loads(text, object_pairs_hook=_refuse_repeated_keys)
    except ValueError as exc:
        # JSONDecodeError is a ValueError; so is the refusal Python raises for an
        # integer literal beyond its digit limit, which is not a JSONDecodeError.
        raise IntegrityError("provider manifest is not valid JSON", path=str(path),
                             error=type(exc).__name__) from exc
    except RecursionError as exc:
        raise IntegrityError("provider manifest is nested beyond what this reader will follow",
                             path=str(path), error=type(exc).__name__) from exc
    if _depth(payload) > _MAX_DEPTH:
        raise IntegrityError("provider manifest is nested beyond what this reader will follow",
                             path=str(path), limit=_MAX_DEPTH)
    return ProviderManifest.from_mapping(payload)


#: A manifest is three levels deep. Anything an order of magnitude past that is
#: not a manifest, and refusing it here keeps every later message bounded.
_MAX_DEPTH = 32


def _depth(value: object, level: int = 0) -> int:
    """Nesting depth of a decoded document, computed iteratively so that the
    measurement itself cannot overflow on the shape it exists to refuse."""
    deepest = level
    pending = [(value, level)]
    while pending:
        current, at = pending.pop()
        deepest = max(deepest, at)
        if at > _MAX_DEPTH:
            return at
        if isinstance(current, dict):
            pending.extend((child, at + 1) for child in current.values())
        elif isinstance(current, list):
            pending.extend((child, at + 1) for child in current)
    return deepest


def _refuse_repeated_keys(pairs: list) -> dict:
    """A repeated key is refused, not resolved last-wins. A document that
    states `metered_api` first and `subscription` later would parse as the
    later value while a person reading the file sees the earlier one — the
    route the fingerprint proves must be the route the founder read."""
    seen: set = set()
    for key, _value in pairs:
        if key in seen:
            raise IntegrityError("provider manifest repeats a key; a document with two answers "
                                 "to one question is refused", key=_key_name(key))
        seen.add(key)
    return dict(pairs)


def manifest_digest(path: str | Path) -> str:
    """The manifest's digest, computed exactly as an adapter's is — the same
    mechanism, because a provider manifest is pinned the way an adapter is."""
    return adapter_pin.file_digest(path)


def _is_metered_key(key: str) -> bool:
    """Whether a client configuration key names a metered credential, read by
    its LAST segment's suffix — so `model.default.api_key` and
    `env.VENDOR_API_KEY` are caught wherever they are nested, on the same rule
    the environment-name check applies, and a key that merely mentions "api"
    in passing is not. Case-folded, so `model.API_KEY` is caught exactly as
    `model.api_key` is."""
    last = key.rsplit(".", 1)[-1].casefold()
    return last.endswith(("api_key", "env_key"))


def _is_metered_environment_name(name: str) -> bool:
    """Whether an environment variable's NAME alone has the shape of a metered
    credential — case-insensitively, and whatever the manifest declared. An
    author's `generic_env_forbidden` list names what THEY thought to forbid; a
    name a manifest never anticipated is still not a name this module ignores."""
    upper = name.upper()
    return upper.endswith(_METERED_ENV_NAME_SUFFIXES)


@dataclass(frozen=True)
class RouteFingerprint:
    """What is established about ONE exact route — never what the manifest
    merely hopes about itself. `established_by` says how each fact was
    obtained; `problems` names every fact this fingerprint could NOT establish.
    No field here ever carries an environment variable's VALUE, only names and
    the facts they establish — it is safe to print, log or hand to a reason
    string."""

    provider_id: str
    gateway: str
    endpoint_or_client: str
    credential_ref: str
    billing_pool_id: str
    billing_mode: str
    authorised_subscription: str | None
    overage_enabled: bool | str
    auto_topup_enabled: bool | str
    metered_fallback_enabled: bool | str
    #: Whether the manifest names a capacity observer at all — not whether it
    #: has ever produced a reading, which this module never touches.
    capacity_observer_configured: bool = False
    established_by: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()


def fingerprint(
    manifest: ProviderManifest,
    *,
    surface_index: int = 0,
    environment: Mapping[str, str] | None = None,
    client_config_keys: Iterable[str] = (),
) -> RouteFingerprint:
    """The billing route fingerprint this exact dispatch would use.

    `environment` is read for NAMES only — presence, never a value — and its
    absence is not treated as a clean environment: it is `UNKNOWN`, because a
    caller that never looked has not established that nothing forbidden is
    there. `metered_fallback_enabled`: a declared `true` is final; positive
    evidence — a forbidden or metered-shaped name in a supplied environment, or
    a metered client configuration key — makes it `True` under `false` and
    under `null` alike; against a clean inspection, `null` stays `UNKNOWN` and
    `false` becomes `False` only when something was actually declared to look
    for — see the module docstring.
    """
    if not 0 <= surface_index < len(manifest.surfaces):
        raise PreconditionError(
            "surface_index does not name a surface this manifest declares",
            surface_index=surface_index, surfaces=len(manifest.surfaces),
        )
    surface = manifest.surfaces[surface_index]
    established = [
        "provider_id from manifest.provider_id",
        "gateway from manifest.gateway",
        f"endpoint_or_client from manifest.surfaces[{surface_index}].client",
        "billing_pool_id from manifest.billing.billing_pool_id",
        "billing_mode from manifest.billing.billing_mode",
    ]
    problems: list[str] = []

    credential_ref = manifest.credential.env_file_ref
    if credential_ref is None:
        credential_ref = UNKNOWN
        problems.append("credential_ref is UNKNOWN: manifest.credential.env_file_ref is null")
    else:
        established.append("credential_ref from manifest.credential.env_file_ref")

    authorised_subscription = manifest.billing.authorised_by
    if authorised_subscription is None:
        problems.append("authorised_subscription is null: manifest.billing.authorised_by is not set")
    else:
        established.append("authorised_subscription from manifest.billing.authorised_by")

    def _declared_flag(value: bool | None, name: str) -> bool | str:
        if value is None:
            problems.append(f"{name} is UNKNOWN: manifest.billing.{name} is null")
            return UNKNOWN
        established.append(f"{name} from manifest.billing.{name}")
        return value

    overage_enabled = _declared_flag(manifest.billing.overage_enabled, "overage_enabled")
    auto_topup_enabled = _declared_flag(manifest.billing.auto_topup_enabled, "auto_topup_enabled")

    declared_metered_fallback = manifest.billing.metered_fallback_enabled
    if declared_metered_fallback is True:
        # A manifest that admits a metered fallback has answered the question
        # itself; no environment can make that route cleaner than it declares.
        metered_fallback_enabled: bool | str = True
        established.append(
            "metered_fallback_enabled is True: manifest.billing.metered_fallback_enabled declares it"
        )
    elif environment is None and any(_is_metered_key(key) for key in client_config_keys):
        # Positive evidence supplied on its own is still positive evidence: a
        # metered client key denies the route whether or not an environment
        # was handed over beside it.
        metered_fallback_enabled = True
        established.append(
            "metered_fallback_enabled is True: a client config key names a metered credential"
        )
    elif environment is None:
        metered_fallback_enabled = UNKNOWN
        problems.append(
            "metered_fallback_enabled is UNKNOWN: no environment was supplied to check against "
            "credential.generic_env_forbidden, and the manifest's declaration alone cannot clear it"
        )
    else:
        forbidden_present = any(
            name in environment for name in manifest.credential.generic_env_forbidden
        )
        generic_shape_present = any(_is_metered_environment_name(name) for name in environment)
        metered_key_present = any(_is_metered_key(key) for key in client_config_keys)
        if forbidden_present or generic_shape_present or metered_key_present:
            # Positive evidence of a metered path outranks every declaration:
            # a poisoned environment makes the flag True whether the manifest
            # said `false` or said nothing. `null` only decides the CLEAN case.
            metered_fallback_enabled = True
            reason = (
                "a forbidden environment variable is present" if forbidden_present else
                "an environment variable NAME has the shape of a metered credential" if generic_shape_present else
                "a client config key names a metered credential"
            )
            established.append(f"metered_fallback_enabled is True: {reason}")
        elif declared_metered_fallback is None:
            # The environment is clean, but the manifest's author never made the
            # claim at all. A `null` here is not "presumably false" — a clean
            # inspection establishes absence of what was looked for, not the
            # plan's own promise, and that promise is the author's to make.
            metered_fallback_enabled = UNKNOWN
            problems.append(
                "metered_fallback_enabled is UNKNOWN: manifest.billing.metered_fallback_enabled is "
                "null, and a clean environment does not substitute for a claim never made"
            )
        elif not manifest.credential.generic_env_forbidden:
            # Nothing was declared to look for. A clean read against an EMPTY
            # forbidden list is not the same claim as a clean read against a
            # checked one, and this module does not conflate the two.
            metered_fallback_enabled = UNKNOWN
            problems.append(
                "metered_fallback_enabled is UNKNOWN: manifest.credential.generic_env_forbidden is "
                "empty, so no environment variable NAME was declared to check for"
            )
        else:
            metered_fallback_enabled = False
            established.append(
                "metered_fallback_enabled is False: declared false by the manifest and no "
                "forbidden environment variable or metered client key is present"
            )

    return RouteFingerprint(
        provider_id=manifest.provider_id,
        gateway=manifest.gateway,
        endpoint_or_client=surface.client,
        credential_ref=credential_ref,
        billing_pool_id=manifest.billing.billing_pool_id,
        billing_mode=manifest.billing.billing_mode,
        authorised_subscription=authorised_subscription,
        overage_enabled=overage_enabled,
        auto_topup_enabled=auto_topup_enabled,
        metered_fallback_enabled=metered_fallback_enabled,
        capacity_observer_configured=manifest.capacity_observer is not None,
        established_by=tuple(established),
        problems=tuple(problems),
    )


@dataclass(frozen=True)
class Routability:
    """The verdict `routability` reaches and the reason that decided it. First
    refusal wins, so `reasons` carries the one that fired; a reader who wants
    the rest re-runs after repairing it, because a route is not "almost
    routable" for having failed only one rung."""

    disposition: str
    reasons: tuple[str, ...] = ()


def _flag_is_false(value: object) -> bool:
    """Whether a billing flag has cleared this rung: exactly `False`, and
    nothing else. `UNKNOWN` and `True` both fail it — an unread flag is not a
    cleared one, which is the whole content of D29's "UNKNOWN is HARD DENY"."""
    return value is False


def routability(fp: RouteFingerprint, *, authorised_pools: Iterable[str]) -> Routability:
    """Whether this exact route is provably safe to bill as what it claims.

    First refusal wins, in the order D29/D32 state: a metered route is denied
    whatever else holds; an unestablished or out-of-vocabulary billing mode is
    denied before anything about the pool is asked; an unauthorised pool is
    denied before the credential is asked; a subscription or prepaid route
    with no credential reference, no configured capacity observer, or with any
    billing flag not exactly `False` is denied; a `local` route needs neither a
    credential nor an observer and is judged on its pool alone — with one
    exception: a flag this fingerprint established as `True` (self-declared, or
    a poisoned inspected environment) denies a `local` route exactly as it does
    every other mode, because a live metered or overage fact is true of the
    route regardless of what bills it. An `UNKNOWN` flag stays irrelevant for
    `local`: a route with no billing pool to overrun has nothing that
    unestablished fact could overrun.

    This function judges billing and credential facts only. Whether a route is
    *qualified* to carry a task class is the routing eligibility report's
    question, not this one's.
    """
    pools = frozenset(authorised_pools)

    if fp.billing_mode == "metered_api":
        return Routability(NOT_ROUTABLE_BILLING, (
            f"{fp.provider_id}: billing_mode is 'metered_api'; a metered route is hard-denied "
            "whatever the credential, the pool or the flags say (D29)",
        ))

    if fp.billing_mode == UNKNOWN or fp.billing_mode not in BILLING_MODES:
        return Routability(NOT_ROUTABLE_UNKNOWN, (
            f"{fp.provider_id}: billing_mode {fp.billing_mode!r} is not established or is "
            f"outside {BILLING_MODES}; an unestablished billing mode is hard deny",
        ))

    if fp.billing_mode == "prepaid_existing" and (
        fp.authorised_subscription is None or fp.billing_pool_id not in pools
    ):
        return Routability(NOT_ROUTABLE_UNAUTHORISED, (
            f"{fp.provider_id}: a prepaid_existing route needs authorised_by set and its pool "
            f"{fp.billing_pool_id!r} among the authorised pools, and at least one is missing (D29: "
            "prepaid balances are denied unless explicitly authorised for the project)",
        ))

    if fp.billing_mode == "subscription" and (
        fp.authorised_subscription is None or fp.billing_pool_id not in pools
    ):
        return Routability(NOT_ROUTABLE_UNAUTHORISED, (
            f"{fp.provider_id}: a subscription route needs authorised_by set and its pool "
            f"{fp.billing_pool_id!r} among the authorised pools, and at least one is missing",
        ))

    if fp.billing_mode in ("subscription", "prepaid_existing"):
        if fp.credential_ref == UNKNOWN:
            return Routability(NOT_ROUTABLE_CREDENTIAL, (
                f"{fp.provider_id}: credential_ref is not established for a {fp.billing_mode} "
                "route; an unnamed credential is not a route this pack will pin work to",
            ))
        if not fp.capacity_observer_configured:
            return Routability(NOT_ROUTABLE_UNKNOWN, (
                f"{fp.provider_id}: capacity_observer is null: no observation source is configured",
            ))
        for name, value in (
            ("overage_enabled", fp.overage_enabled),
            ("auto_topup_enabled", fp.auto_topup_enabled),
            ("metered_fallback_enabled", fp.metered_fallback_enabled),
        ):
            if _flag_is_false(value):
                continue
            if value == UNKNOWN:
                return Routability(NOT_ROUTABLE_UNKNOWN, (
                    f"{fp.provider_id}: {name} is not established; UNKNOWN is hard deny (D29)",
                ))
            return Routability(NOT_ROUTABLE_BILLING, (
                f"{fp.provider_id}: {name} is true; a route with a live metered fallback is "
                "never routable as a subscription",
            ))
        return Routability(ROUTABLE, (
            f"{fp.provider_id}: {fp.billing_mode} route to {fp.billing_pool_id!r} is authorised, "
            "credentialed and carries no metered fallback",
        ))

    # billing_mode == "local": no credential and no observer needed, and an
    # UNKNOWN flag is irrelevant — but a flag established TRUE is a live fact
    # about the route whatever bills it, so it still denies.
    for name, value in (
        ("overage_enabled", fp.overage_enabled),
        ("auto_topup_enabled", fp.auto_topup_enabled),
        ("metered_fallback_enabled", fp.metered_fallback_enabled),
    ):
        if value is True:
            return Routability(NOT_ROUTABLE_BILLING, (
                f"{fp.provider_id}: {name} is true; a live metered or overage fact is true of "
                "this route whatever bills it, local included",
            ))
    if fp.billing_pool_id in pools:
        return Routability(ROUTABLE, (
            f"{fp.provider_id}: local route to {fp.billing_pool_id!r} is authorised and needs no "
            "credential",
        ))
    return Routability(NOT_ROUTABLE_UNAUTHORISED, (
        f"{fp.provider_id}: local billing_pool_id {fp.billing_pool_id!r} is not among the "
        "authorised pools",
    ))


def render(manifest: ProviderManifest, fp: RouteFingerprint, disposition: Routability) -> str:
    """The identity, the route and the verdict. Never a credential value."""

    def _flag(value: object) -> str:
        if value == UNKNOWN:
            return "UNKNOWN"
        return "true" if value else "false"

    lines = [
        f"provider {manifest.provider_id} (vendor {manifest.vendor}, gateway {manifest.gateway})",
        f"  route: {fp.endpoint_or_client} via credential {fp.credential_ref}",
        f"  billing: {fp.billing_mode} on pool {fp.billing_pool_id}, "
        f"authorised_by={fp.authorised_subscription or UNKNOWN}",
        f"  overage_enabled={_flag(fp.overage_enabled)} "
        f"auto_topup_enabled={_flag(fp.auto_topup_enabled)} "
        f"metered_fallback_enabled={_flag(fp.metered_fallback_enabled)}",
        f"disposition: {disposition.disposition}",
    ]
    lines.extend(f"  {reason}" for reason in disposition.reasons)
    if fp.problems:
        lines.append("  not established: " + "; ".join(fp.problems))
    return "\n".join(lines)


def _cli(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="provider_manifest.py",
        description="Validate a provider manifest and derive whether its exact route is routable.",
    )
    parser.add_argument("manifest", metavar="MANIFEST", help="path to a provider manifest JSON document")
    parser.add_argument(
        "--environment-from-current-process", action="store_true",
        help="check this process's environment variable NAMES against the manifest's forbidden "
             "list; a value is never read or printed",
    )
    parser.add_argument(
        "--authorised-pool", dest="authorised_pools", action="append", default=[], metavar="ID",
        help="a billing_pool_id this dispatch is authorised against; repeatable",
    )
    parser.add_argument("--json", action="store_true", help="print the result as JSON instead of text")
    args = parser.parse_args(argv)

    manifest = load(args.manifest)
    environment = {name: "" for name in os.environ} if args.environment_from_current_process else None
    route = fingerprint(manifest, environment=environment)
    disposition = routability(route, authorised_pools=args.authorised_pools)

    if args.json:
        print(json.dumps({
            "provider_id": manifest.provider_id,
            "vendor": manifest.vendor,
            "gateway": manifest.gateway,
            "disposition": disposition.disposition,
            "reasons": list(disposition.reasons),
        }))
    else:
        print(render(manifest, route, disposition))

    return 0 if disposition.disposition == ROUTABLE else 1


if __name__ == "__main__":
    import sys

    # Run the module, not a second copy of it. A file executed as a script is
    # `__main__`, and a sibling that imports it BY NAME gets a separate module
    # object with separate class objects — so an `isinstance` check across that
    # boundary is False for an object that is exactly that class. Imported
    # statically, by name, because a dynamic import would route around the
    # toolbelt's import-closure check.
    from errors import run_cli
    from provider_manifest import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
