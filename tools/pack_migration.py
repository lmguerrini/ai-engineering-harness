"""Moving a project between qualified releases, and back.

D13 established that several projects may pin one frozen release, or different
releases, concurrently. What it did not establish is how a project *changes*
which release it is pinned to — and a pin nobody can move is a pin that gets
edited by hand, which is the same thing as no pin.

Everything here is file-oriented and stateless. There is no daemon, no
scheduler, no shared registry and no coordinated upgrade: a project adopts a
release by verifying it at its own next safe capability boundary, or it does
not adopt it.

## The four things this adds

**`pack.root_path`.** A pin recorded a version, a revision and a digest, and
never said *which directory* those describe. Two qualified releases must resolve
to distinct immutable roots (D13) and nothing checked that they did. The root is
now declared, canonicalised — symlinks resolved, `..` removed — and verified,
because a declared path that is a symlink into the release currently being
edited is exactly how "the pinned release never mutates" stops being true.

**An honest name for a pin that cannot be checked.** Pins already exist that
carry a version and nothing else. They cannot be verified, and there is no
honest way to reconstruct what they meant: the version is a label, and two
checkouts can carry it and differ. Such a pin is `UNVERIFIABLE_LEGACY_PIN` — a
named state, reported at every use, never silently upgraded by writing today's
digest into it. Writing today's digest would produce a pin that verifies and
means nothing, which is worse than one that admits it cannot.

**A release index, outside every release.** A frozen release cannot list the
releases that come after it, so the index of available releases lives beside
them rather than inside any one of them. It is therefore untrusted input, read
and verified exactly like an adapter: each entry's identity is checked against
the release it names before that release is offered.

**Rollback to a root that is still verifiable.** A retained previous root is
only a rollback target while it still verifies. A retained path that has been
deleted, edited or moved is reported as unavailable rather than offered.

## What this module will not do

It will not migrate anything. It reports whether a migration is permissible and
what is wrong when it is not; adopting is a decision, made at a capability
boundary, recorded by the project. In particular an **urgent security
migration** is a human decision with a name attached — this module can mark a
release as carrying a security advisory and can refuse to call a migration
clean, and it cannot authorise one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pack_pin

__all__ = [
    "VERIFIED_PIN",
    "UNVERIFIABLE_LEGACY_PIN",
    "PIN_CLASSES",
    "Pin",
    "MigrationReport",
    "classify_pin",
    "canonical_root",
    "verify_pinned_root",
    "read_release_index",
    "migration_gate",
    "rollback_targets",
    "unaccounted_candidates",
]

#: A pin carrying version + revision + digest + state + root, all checkable.
VERIFIED_PIN = "VERIFIED_PIN"

#: A pin carrying a version and not enough else to check it. Named rather than
#: repaired: the identity is not recoverable, and inventing one produces a pin
#: that verifies and means nothing.
UNVERIFIABLE_LEGACY_PIN = "UNVERIFIABLE_LEGACY_PIN"

PIN_CLASSES = (VERIFIED_PIN, UNVERIFIABLE_LEGACY_PIN)

_REQUIRED_FOR_VERIFICATION = ("version_adopted", "sha_adopted", "tree_digest_sha256", "root_path")


@dataclass(frozen=True)
class Pin:
    """What a project recorded about the release it is running against."""

    version: str | None = None
    sha: str | None = None
    digest: str | None = None
    state: str | None = None
    root_path: str | None = None
    #: Previously verified roots this project keeps for rollback. Retained, not
    #: guaranteed: each is re-verified before it is offered.
    retained_roots: tuple[str, ...] = ()

    @classmethod
    def from_contract(cls, contract: object) -> "Pin":
        raw = getattr(contract, "raw", None)
        block = (raw or {}).get("pack") or {}
        if not isinstance(block, dict):
            raise ValueError("`pack:` must be a mapping")
        retained = block.get("retained_roots") or ()
        if isinstance(retained, str):
            retained = (retained,)
        return cls(
            version=block.get("version_adopted"),
            sha=block.get("sha_adopted"),
            digest=block.get("tree_digest_sha256"),
            state=block.get("state_adopted"),
            root_path=block.get("root_path"),
            retained_roots=tuple(str(item) for item in retained),
        )


def classify_pin(pin: Pin) -> str:
    """`VERIFIED_PIN` or `UNVERIFIABLE_LEGACY_PIN`, and never a guess between.

    The classification is about *checkability*, not about correctness: a pin
    with every field present is `VERIFIED_PIN` before anything is verified, and
    then verification either passes or produces findings. Conflating the two
    would let "I have not checked yet" and "there is nothing to check" share a
    name.
    """
    values = {
        "version_adopted": pin.version,
        "sha_adopted": pin.sha,
        "tree_digest_sha256": pin.digest,
        "root_path": pin.root_path,
    }
    if all(isinstance(value, str) and value.strip() for value in values.values()):
        return VERIFIED_PIN
    return UNVERIFIABLE_LEGACY_PIN


def missing_pin_fields(pin: Pin) -> list[str]:
    """Which fields a legacy pin lacks, so the report says what is wrong."""
    values = {
        "version_adopted": pin.version,
        "sha_adopted": pin.sha,
        "tree_digest_sha256": pin.digest,
        "root_path": pin.root_path,
    }
    return [name for name in _REQUIRED_FOR_VERIFICATION if not (values.get(name) or "").strip()]


def canonical_root(path: str | Path) -> Path:
    """A declared root as an absolute, symlink-resolved path.

    Resolved rather than merely made absolute. D13 requires two qualified
    releases to resolve to *distinct immutable roots*, and a symlink is exactly
    how two declarations that look distinct become one directory — including one
    directory that is currently being edited.
    """
    return Path(path).expanduser().resolve()


@dataclass
class MigrationReport:
    """Every reason a project may not move to the release it named."""

    findings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    from_root: str | None = None
    to_root: str | None = None

    @property
    def clean(self) -> bool:
        return not self.findings

    def render(self) -> str:
        head = "migration permitted" if self.clean else "migration REFUSED"
        lines = [f"{head}: {self.from_root or 'UNKNOWN'} -> {self.to_root or 'UNKNOWN'}"]
        lines.extend(f"  {item}" for item in self.findings)
        lines.extend(f"  note: {item}" for item in self.notes)
        if self.clean:
            lines.append("  this is permission to adopt, not an adoption; a human records it")
        return "\n".join(lines)


def verify_pinned_root(pin: Pin) -> list[str]:
    """Every way the declared root is not the release the pin describes."""
    if classify_pin(pin) == UNVERIFIABLE_LEGACY_PIN:
        return [
            f"{UNVERIFIABLE_LEGACY_PIN}: this pin lacks "
            f"{', '.join(missing_pin_fields(pin))}, so the release it names cannot be "
            "identified. It is not repaired by recording today's values — that would "
            "produce a pin that verifies and describes nothing"
        ]

    root = canonical_root(pin.root_path or "")
    if not root.is_dir():
        return [f"pack.root_path {pin.root_path!r} does not resolve to a directory ({root})"]

    try:
        return pack_pin.verify_pin(
            root,
            expect_version=pin.version,
            expect_sha=pin.sha,
            expect_digest=pin.digest,
            expect_state=pin.state,
        )
    except Exception as exc:  # a root that cannot be read is a finding, not an absence
        return [f"the pinned root could not be verified: {exc}"]


@dataclass(frozen=True)
class ReleaseEntry:
    version: str
    root_path: str
    sha: str
    digest: str
    state: str
    security_advisory: str | None = None


def read_release_index(path: str | Path) -> tuple[ReleaseEntry, ...]:
    """Read the index of available releases. Untrusted input, parsed strictly.

    The index lives **outside** every release, because a frozen release cannot
    name the ones that come after it. That places it in the same category as an
    installed adapter: material the pack reads and does not own, so every entry
    is refused unless it is complete. An index entry is a *claim* that a release
    exists at a path; `migration_gate` is what turns it into a verification.
    """
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("releases"), list):
        raise ValueError("a release index must be an object with a `releases` list")

    entries: list[ReleaseEntry] = []
    seen_versions: set[str] = set()
    seen_roots: set[Path] = set()
    for position, raw in enumerate(document["releases"], start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"releases[{position}] is not an object")
        missing = [
            key for key in ("version", "root_path", "sha", "digest", "state")
            if not isinstance(raw.get(key), str) or not raw[key].strip()
        ]
        if missing:
            raise ValueError(f"releases[{position}] is missing {', '.join(missing)}")
        if raw["version"] in seen_versions:
            raise ValueError(f"releases[{position}] repeats version {raw['version']!r}")
        seen_versions.add(raw["version"])
        root = canonical_root(raw["root_path"])
        if root in seen_roots:
            # D13: different versions must resolve to distinct immutable roots,
            # never one directory moved between revisions — which would make
            # both pins unverifiable at once.
            raise ValueError(
                f"releases[{position}] resolves to {root}, which another entry already claims; "
                "two releases sharing a root cannot both be pinned"
            )
        seen_roots.add(root)
        entries.append(
            ReleaseEntry(
                version=raw["version"], root_path=raw["root_path"], sha=raw["sha"],
                digest=raw["digest"], state=raw["state"],
                security_advisory=raw.get("security_advisory"),
            )
        )
    return tuple(entries)


def migration_gate(
    pin: Pin,
    target: ReleaseEntry,
    *,
    at_capability_boundary: bool,
    candidates_accounted: bool = True,
) -> MigrationReport:
    """Whether this project may adopt ``target``.

    `at_capability_boundary` is supplied by the caller because only the caller
    knows: it is a statement about the project's own state, and a checker that
    inferred it from the filesystem would be inventing the one fact that makes
    adoption safe.
    """
    report = MigrationReport(from_root=pin.root_path, to_root=target.root_path)

    if not at_capability_boundary:
        report.findings.append(
            "a release is adopted only at a capability boundary, never mid-capability "
            "(PROJECT.yaml pack.adoption_boundary)"
        )

    if target.state != "QUALIFIED_AND_FROZEN":
        report.findings.append(
            f"the target declares state {target.state!r}; a project may adopt only "
            "QUALIFIED_AND_FROZEN"
        )

    current_class = classify_pin(pin)
    if current_class == UNVERIFIABLE_LEGACY_PIN:
        # Not a blocker on its own: migrating *away* from an unverifiable pin is
        # the remedy for having one. It is disclosed, because the project cannot
        # claim to know what it is migrating from.
        report.notes.append(
            f"the current pin is {UNVERIFIABLE_LEGACY_PIN} ({', '.join(missing_pin_fields(pin))} "
            "absent). Migration is permitted and is the remedy, but nothing can be "
            "concluded about what is being left behind"
        )
    else:
        current_problems = verify_pinned_root(pin)
        if current_problems:
            report.findings.append(
                "the CURRENT pin does not verify, so this checkout is not the release the "
                "project has been running against: " + "; ".join(current_problems)
            )
        if canonical_root(pin.root_path or "") == canonical_root(target.root_path):
            report.findings.append(
                "the target resolves to the same root as the current pin; a new release "
                "must be a distinct immutable root, never the same directory at a new revision"
            )

    target_root = canonical_root(target.root_path)
    if not target_root.is_dir():
        report.findings.append(f"the target root {target.root_path!r} does not resolve to a directory")
    else:
        try:
            problems = pack_pin.verify_pin(
                target_root, expect_version=target.version, expect_sha=target.sha,
                expect_digest=target.digest, expect_state=target.state,
            )
        except Exception as exc:
            problems = [f"the target root could not be verified: {exc}"]
        report.findings.extend(f"target: {item}" for item in problems)

    if target.security_advisory:
        # Recorded loudly and never used to skip anything. An urgent security
        # migration is a human decision; this module can say a release carries
        # an advisory and cannot authorise moving to it any faster.
        report.notes.append(
            f"the target carries a SECURITY ADVISORY: {target.security_advisory}. "
            "Urgency does not remove the capability boundary or the human authority; "
            "it is a reason for a person to decide sooner"
        )

    if not candidates_accounted:
        report.findings.append(
            "this project's Evolution Candidate inbox has entries with no recorded "
            "disposition against this release; a candidate that arrived during the "
            "evolution session must be answered, not skipped"
        )

    return report


def rollback_targets(pin: Pin) -> tuple[list[str], list[str]]:
    """``(available, unavailable)`` retained roots, by re-verification.

    Retention is not a guarantee. A retained path that has been deleted, edited
    or moved is *unavailable*, and offering it as a rollback target would be
    offering a directory nobody has checked since it stopped being the release
    it claims to be.
    """
    available: list[str] = []
    unavailable: list[str] = []
    for candidate in pin.retained_roots:
        root = canonical_root(candidate)
        if not root.is_dir():
            unavailable.append(f"{candidate}: no longer a directory")
            continue
        try:
            problems = pack_pin.verify_pin(root, expect_state="QUALIFIED_AND_FROZEN")
        except Exception as exc:
            problems = [str(exc)]
        if problems:
            unavailable.append(f"{candidate}: {'; '.join(problems)}")
        else:
            available.append(str(root))
    return available, unavailable


def unaccounted_candidates(candidate_ids: object, dispositions: object) -> list[str]:
    """Candidate ids with no recorded disposition.

    "No candidate arriving during evolution may be silently skipped" is a
    counting problem, so it is counted. The inbox is append-only and the
    disposition record is separate, which means a candidate added *after* the
    evolution session read the inbox is exactly the one that goes missing —
    and it is the one this finds.
    """
    recorded = {str(item) for item in (dispositions or ())}
    return [str(item) for item in (candidate_ids or ()) if str(item) not in recorded]


def _cli(argv: list[str]) -> int:
    """Report whether a project may adopt a release. It never adopts one."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="pack_migration.py",
        description="Classify a pin, verify its root, and gate a migration. Reports only.",
    )
    parser.add_argument("--project", required=True, help="path to PROJECT.yaml")
    parser.add_argument("--index", help="path to the release index, outside every release")
    parser.add_argument("--to", help="the version in the index to migrate to")
    parser.add_argument(
        "--at-capability-boundary", action="store_true",
        help="assert that this project is at a capability boundary; only the caller knows",
    )
    parser.add_argument(
        "--candidate", action="append", default=[], metavar="ID",
        help="an Evolution Candidate id in this project's inbox (repeatable)",
    )
    parser.add_argument(
        "--disposed", action="append", default=[], metavar="ID",
        help="a candidate id with a recorded disposition against the target (repeatable)",
    )
    parser.add_argument("--rollback", action="store_true", help="list verifiable rollback targets")
    args = parser.parse_args(argv)

    import project_contract

    try:
        contract = project_contract.ProjectContract.load(args.project)
        pin = Pin.from_contract(contract)
    except Exception as exc:
        print(f"the project contract could not be read: {exc}", file=sys.stderr)
        return 2

    classification = classify_pin(pin)
    print(f"pin class: {classification}")
    for problem in verify_pinned_root(pin):
        print(f"  {problem}")

    if args.rollback:
        available, unavailable = rollback_targets(pin)
        print(f"rollback targets: {len(available)} verifiable, {len(unavailable)} not")
        for item in available:
            print(f"  available: {item}")
        for item in unavailable:
            print(f"  UNAVAILABLE: {item}")

    if not args.to:
        # No target named: this was a pin inspection, and it says so rather than
        # printing a bare 0 that reads as "migration fine".
        return 0 if classification == VERIFIED_PIN and not verify_pinned_root(pin) else 1

    if not args.index:
        print("--to requires --index", file=sys.stderr)
        return 2
    try:
        entries = read_release_index(args.index)
    except Exception as exc:
        print(f"the release index could not be read: {exc}", file=sys.stderr)
        return 2

    target = next((entry for entry in entries if entry.version == args.to), None)
    if target is None:
        print(f"the index names no release {args.to!r}", file=sys.stderr)
        return 2

    missing = unaccounted_candidates(args.candidate, args.disposed)
    for identifier in missing:
        print(f"  candidate with no recorded disposition: {identifier}")

    report = migration_gate(
        pin, target,
        at_capability_boundary=args.at_capability_boundary,
        candidates_accounted=not missing,
    )
    print(report.render())
    return 0 if report.clean else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
