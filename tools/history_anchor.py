"""A record that names a commit, and whether anything keeps that commit reachable.

Closure records cite revisions. Git keeps an object alive because a **ref**
reaches it, and nothing else — a branch rebuild, a rebase, a squash or an
amend can orphan a commit that half a dozen governance documents point at, and
the citation goes on looking exactly as authoritative as it did the day it was
written. It stops resolving only when somebody expires a reflog, which is not an
event anybody announces.

**This is the one evidence defect whose window closes on its own.**
`gc.reflogExpireUnreachable` defaults to thirty days and an orphaned commit
survives only through its reflog, so the interval is roughly a
month — and it ends the instant anyone expires a reflog, which is sooner and
unpredictable.

## Why the mapping ships with the reachability check and not after it

A rewrite gives every commit a new identity. The moment one happens, **every
commit-shaped token in every record stops resolving at once** — so a
reachability check shipped alone would fail closed across an entire corpus, not
on a defect but on a rewrite the same release exists to make safe.

So a rewrite emits an old-to-new mapping, and resolution consults it. The
mapping is a first-class input here rather than a convention, because the
version of this that was a convention produced a file nobody's checker read.

## What is not decided here

A token that Git does not recognise at all is **not** a finding. Records are
prose, prose contains hexadecimal, and a checker that called every unrecognised
seven-character word a lost commit would produce a remediation list nobody
could act on. Three answers, and only one of them blocks: Git knows this commit
and a ref reaches it; Git knows it and nothing does; Git does not know it.

Nothing here rewrites history, creates a ref, or prunes anything. It reports,
and `policy/hitl-matrix.md` rows 2 and 4 decide what happens next.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import gitread
from errors import IntegrityError, PreconditionError
from instrument import Examined

__all__ = [
    "CitationState",
    "Citation",
    "ReachabilityReport",
    "Anchor",
    "load_mapping",
    "citations_in",
    "check_reachability",
    "verify_rewrite",
    "RewriteFinding",
    "MAPPING_SCHEMA",
]

#: The shape a rewrite's old-to-new mapping must take on disk. Named so the
#: producer and the consumer cannot drift: a mapping the reachability check
#: cannot read is a mapping that does not exist.
MAPPING_SCHEMA = "old-to-new-revision-map-v1"

#: Seven is Git's own shortest unambiguous abbreviation in practice, and forty
#: is a full object name. Below seven the false-positive rate over ordinary
#: prose stops being worth the reading.
_TOKEN = re.compile(r"(?<![0-9a-zA-Z])(?P<sha>[0-9a-f]{7,40})(?![0-9a-zA-Z])")

_FULL = re.compile(r"^[0-9a-f]{40}$")


class CitationState:
    #: Git knows this commit and a ref reaches it. Nothing to do.
    REACHABLE = "REACHABLE"
    #: Git knows this commit and no ref reaches it. **The finding.** It is alive
    #: only for as long as a reflog keeps it.
    UNREACHABLE = "UNREACHABLE"
    #: Unreachable from a ref, and present in a verified bundle the project
    #: declared as an anchor. Durable, and a different fact from reachable.
    ANCHORED = "ANCHORED"
    #: Git does not recognise it. Almost always prose that happens to be
    #: hexadecimal, so it is reported and never blocks.
    NOT_A_COMMIT = "NOT_A_COMMIT"
    #: Git does not recognise it, and the rewrite mapping does — under a new
    #: identity that a ref reaches. The citation is stale, not lost.
    REMAPPED = "REMAPPED"
    #: Git could not be asked. Never read as any of the above.
    UNKNOWN = "UNKNOWN"

    ALL = (REACHABLE, UNREACHABLE, ANCHORED, NOT_A_COMMIT, REMAPPED, UNKNOWN)
    #: The states that stop a closure.
    BLOCKING = (UNREACHABLE, UNKNOWN)


@dataclass(frozen=True)
class Citation:
    token: str
    state: str
    where: str
    detail: str = ""
    maps_to: str | None = None

    def __str__(self) -> str:
        arrow = f" -> {self.maps_to[:12]}" if self.maps_to else ""
        return f"{self.where}: {self.token}{arrow} {self.state}" + (f" ({self.detail})" if self.detail else "")


@dataclass(frozen=True)
class Anchor:
    """Something that keeps a commit alive after no branch does.

    Two kinds, and the second exists because the first is not always available:
    where a fence forbids creating refs in a repository, a **bundle** is the only
    durable form, and it is durable only if it has been restored into an
    isolated repository and read back. A bundle nobody has verified is a file.
    """

    kind: str  # "ref" or "bundle"
    locator: str
    verified: bool = False
    detail: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ("ref", "bundle"):
            raise IntegrityError("an anchor is a ref or a bundle", kind=repr(self.kind))


def load_mapping(path: str | Path | None) -> dict[str, str]:
    """An old-to-new revision map, or an empty one, or a stated refusal.

    Refused rather than skipped when unreadable: a reachability check running
    with a mapping it silently failed to load reports every rewritten citation
    as lost, which is a corpus-sized false positive.
    """
    if path is None:
        return {}
    target = Path(path)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PreconditionError("the revision mapping cannot be read",
                                path=str(target), error=str(exc)) from exc
    except ValueError as exc:
        raise PreconditionError("the revision mapping is not readable JSON",
                                path=str(target), error=str(exc)) from exc
    if not isinstance(raw, dict) or raw.get("schema") != MAPPING_SCHEMA:
        raise PreconditionError(
            "the revision mapping does not declare the schema this checker reads; a mapping the "
            "consumer cannot read is a mapping that does not exist",
            path=str(target), expected=MAPPING_SCHEMA, found=repr(raw.get("schema") if isinstance(raw, dict) else raw),
        )
    pairs = raw.get("map")
    if not isinstance(pairs, dict):
        raise PreconditionError("the revision mapping carries no `map`", path=str(target))
    mapping: dict[str, str] = {}
    for old, new in pairs.items():
        if not (_FULL.match(str(old)) and _FULL.match(str(new))):
            raise PreconditionError(
                "a revision mapping holds full forty-character revisions on both sides; an "
                "abbreviation is what makes a mapping ambiguous exactly when it matters",
                path=str(target), entry=f"{old} -> {new}",
            )
        mapping[str(old)] = str(new)
    return mapping


def citations_in(text: str, *, where: str) -> list[tuple[str, str]]:
    """Every commit-shaped token in a record, with where it was found."""
    return [(match.group("sha"), where) for match in _TOKEN.finditer(text)]


@dataclass
class ReachabilityReport:
    citations: list[Citation] = field(default_factory=list)
    records_read: int = 0
    anchors: list[Anchor] = field(default_factory=list)

    @property
    def examined(self) -> Examined:
        return Examined({"records": self.records_read, "citations": len(self.citations)})

    @property
    def blocking(self) -> list[Citation]:
        return [c for c in self.citations if c.state in CitationState.BLOCKING]

    def render(self) -> str:
        examined = self.examined
        verdict = examined.verdict_or_nothing(
            "every cited commit is reachable or anchored" if not self.blocking
            else f"{len(self.blocking)} cited commit(s) NOT REACHABLE"
        )
        lines = [f"closure anchors: {verdict}", f"  examined: {examined.summary()}"]
        counts: dict[str, int] = {}
        for citation in self.citations:
            counts[citation.state] = counts.get(citation.state, 0) + 1
        if counts:
            lines.append("  " + ", ".join(f"{n} {state}" for state, n in sorted(counts.items())))
        for citation in self.blocking:
            lines.append(f"  {citation}")
        for anchor in self.anchors:
            mark = "verified" if anchor.verified else "NOT VERIFIED"
            lines.append(f"  anchor {anchor.kind} {anchor.locator}: {mark} {anchor.detail}".rstrip())
        return "\n".join(lines)


def _reachable_set(repository: str | Path) -> set[str] | None:
    """Every commit any ref reaches, or `None` when Git could not be asked."""
    answer = gitread.probe(repository, "rev-list", "--all", negative_statuses=())
    if not answer.answered or not answer.ok:
        return None
    return {line.strip() for line in answer.value.splitlines() if line.strip()}


def _bundle_contains(repository: str | Path, bundle: Path, sha: str) -> bool:
    answer = gitread.probe(repository, "bundle", "list-heads", str(bundle), negative_statuses=())
    if not answer.answered or not answer.ok:
        return False
    return any(line.split()[0].strip() == sha for line in answer.value.splitlines() if line.strip())


def check_reachability(
    repository: str | Path,
    records: Mapping[str, str],
    *,
    mapping: Mapping[str, str] | None = None,
    bundles: Sequence[str | Path] = (),
) -> ReachabilityReport:
    """Whether every commit these records cite is still kept alive by something.

    ``records`` is ``{where: text}`` — the caller enumerates its own governance
    corpus, because the domain of this check is *the records this project
    keeps*, and a checker that went looking for them itself would be sampling
    wherever it happened to look.
    """
    report = ReachabilityReport(records_read=len(records))
    reachable = _reachable_set(repository)
    mapping = dict(mapping or {})

    verified_bundles: list[Path] = []
    for bundle in bundles:
        path = Path(bundle)
        # Verified from inside the repository, because that is where Git can
        # check the bundle's prerequisites. Verified elsewhere it can only say
        # the file parses, which is not what an anchor has to establish.
        answer = gitread.probe(repository, "bundle", "verify", str(path), negative_statuses=())
        ok = bool(answer.answered and answer.ok)
        report.anchors.append(Anchor(
            kind="bundle", locator=str(path), verified=ok,
            detail="" if ok else (answer.detail or answer.cause),
        ))
        if ok:
            verified_bundles.append(path)

    seen: set[tuple[str, str]] = set()
    for where, text in records.items():
        for token, origin in citations_in(text, where=where):
            if (token, origin) in seen:
                continue
            seen.add((token, origin))
            report.citations.append(
                _classify(repository, token, origin, reachable, mapping, verified_bundles)
            )
    return report


def _successor(full: str | None, token: str, mapping: Mapping[str, str]) -> str | None:
    """What a rewrite renamed this commit to, if the mapping says.

    Looked up by the full identity when one is known and by the cited token
    otherwise, and an abbreviation that matches two entries resolves to neither:
    a mapping consulted ambiguously is worse than one not consulted, because it
    answers.
    """
    for key in (full, token):
        if key and key in mapping:
            return mapping[key]
    if len(token) < 40:
        candidates = {new for old, new in mapping.items() if old.startswith(token)}
        if len(candidates) == 1:
            return candidates.pop()
    return None


def _classify(repository, token, where, reachable, mapping, bundles) -> Citation:
    if reachable is None:
        return Citation(token, CitationState.UNKNOWN, where,
                        "the repository's reachable set could not be read, so nothing was checked")

    answer = gitread.probe(repository, "rev-parse", "--verify", "--quiet", f"{token}^{{commit}}",
                           negative_statuses=(1,))
    if not answer.answered:
        return Citation(token, CitationState.UNKNOWN, where, answer.cause)
    if answer.negative or not answer.ok:
        # Git does not know it. Consult the mapping before calling it prose:
        # after a rewrite every old identity looks exactly like this.
        full = _successor(None, token, mapping)
        if full and full in reachable:
            return Citation(token, CitationState.REMAPPED, where,
                            "a rewrite gave this commit a new identity and a ref reaches it",
                            maps_to=full)
        if full:
            return Citation(token, CitationState.UNREACHABLE, where,
                            "the mapping names a successor and no ref reaches it either",
                            maps_to=full)
        return Citation(token, CitationState.NOT_A_COMMIT, where,
                        "not an object in this repository")

    full = answer.value.strip()
    if full in reachable:
        return Citation(token, CitationState.REACHABLE, where)

    # The mapping is consulted HERE too, and this is the case that matters most.
    # After a local rewrite the old commit is still an object — Git resolves it
    # perfectly — and simply nothing points at it any more. Consulting the map
    # only for tokens Git cannot resolve would therefore miss every citation a
    # rewrite in this repository invalidated, which is the whole population.
    successor = _successor(full, token, mapping)
    if successor and successor in reachable:
        return Citation(token, CitationState.REMAPPED, where,
                        "a rewrite gave this commit a new identity and a ref reaches it",
                        maps_to=successor)

    for bundle in bundles:
        if _bundle_contains(repository, bundle, full):
            return Citation(token, CitationState.ANCHORED, where,
                            f"held by the verified bundle {bundle.name}")
    return Citation(
        token, CitationState.UNREACHABLE, where,
        "the object exists and no ref reaches it; it survives only while a reflog keeps it, "
        "and that ends the instant anyone expires one",
        maps_to=successor,
    )


# --- the invariants a rewrite must not break -----------------------------------------


@dataclass(frozen=True)
class RewriteFinding:
    field: str
    detail: str

    def __str__(self) -> str:
        return f"{self.field}: {self.detail}"


def verify_rewrite(
    before: str | Path,
    after: str | Path,
    mapping: Mapping[str, str],
    *,
    rollback_proven: bool = False,
) -> list[RewriteFinding]:
    """Every invariant a rewrite broke, **naming the field** rather than failing.

    Nothing here performs a rewrite, authorises one, or makes one easier. The
    pack detects, classifies and verifies; executing a rewrite is a human
    decision under rows 2 and 4 (`DECISIONS.md` D23 clause 6). These invariants
    exist so that an authorised one can be checked rather than trusted, and they
    ship in the same release as anything that produces a remediation list —
    because a list of historical blobs to remediate authorises a rewrite by
    consequence.

    ``rollback_proven`` is the caller's statement that a restorable baseline was
    demonstrated **before** anything was touched. It is a finding when absent,
    not a parameter with a convenient default.
    """
    findings: list[RewriteFinding] = []
    if not rollback_proven:
        findings.append(RewriteFinding(
            "rollback",
            "no restorable baseline was demonstrated before the rewrite; a mirror that has not "
            "been restored and read back is a file, not a rollback",
        ))
    if not mapping:
        findings.append(RewriteFinding(
            "mapping",
            "a rewrite emits an old-to-new revision map; without one every commit-shaped token "
            "in every record stops resolving at once",
        ))
        return findings

    for old, new in sorted(mapping.items()):
        old_meta = _metadata(before, old)
        new_meta = _metadata(after, new)
        if old_meta is None:
            findings.append(RewriteFinding("mapping", f"{old[:12]} is not a commit in the baseline"))
            continue
        if new_meta is None:
            findings.append(RewriteFinding("mapping", f"{new[:12]} is not a commit in the rewritten repository"))
            continue
        for field_name, label in (("author_date", "author date"), ("committer_date", "committer date"),
                                  ("author", "author identity"), ("tree", "tree")):
            if old_meta.get(field_name) != new_meta.get(field_name):
                findings.append(RewriteFinding(
                    label,
                    f"{old[:12]} -> {new[:12]} changed it from {old_meta.get(field_name)!r} to "
                    f"{new_meta.get(field_name)!r}",
                ))

    before_order = _commit_order(before)
    after_order = _commit_order(after)
    if before_order is not None and after_order is not None:
        expected = [mapping.get(sha, sha) for sha in before_order if sha in mapping]
        actual = [sha for sha in after_order if sha in set(mapping.values())]
        if expected != actual:
            findings.append(RewriteFinding(
                "order", "the rewritten commits are not in the order the baseline had them"))
    return findings


def _metadata(repository: str | Path, sha: str) -> dict[str, str] | None:
    answer = gitread.probe(
        repository, "show", "--no-patch", "--format=%an <%ae>%n%aI%n%cI%n%T", sha,
        negative_statuses=(128,),
    )
    if not answer.answered or not answer.ok:
        return None
    lines = answer.value.splitlines()
    if len(lines) < 4:
        return None
    return {"author": lines[0], "author_date": lines[1], "committer_date": lines[2], "tree": lines[3]}


def _commit_order(repository: str | Path) -> list[str] | None:
    answer = gitread.probe(repository, "rev-list", "--all", "--reverse", negative_statuses=())
    if not answer.answered or not answer.ok:
        return None
    return [line.strip() for line in answer.value.splitlines() if line.strip()]


def _cli(argv: list[str]) -> int:
    """Check that every commit a project's records cite is still kept alive.

    Usage: ``history_anchor.py REPO --record PATH [--record PATH ...]
                               [--mapping PATH] [--bundle PATH ...]``

    Exit status: ``0`` every citation is reachable, anchored, remapped or prose;
    ``1`` at least one cited commit is unreachable; ``2`` nothing was examined
    or something could not be established.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="history_anchor.py",
        description="Whether the commits a project's records cite are still reachable.")
    parser.add_argument("repository")
    parser.add_argument("--record", action="append", default=[], metavar="PATH",
                        help="a governance record to read (repeatable)")
    parser.add_argument("--mapping", default=None, help="an old-to-new revision map from a rewrite")
    parser.add_argument("--bundle", action="append", default=[], metavar="PATH",
                        help="a bundle anchor holding commits no ref reaches (repeatable)")
    args = parser.parse_args(argv)

    records: dict[str, str] = {}
    for entry in args.record:
        path = Path(entry)
        try:
            records[str(path)] = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"REFUSED the record {path} could not be read: {exc}")
            return 2

    report = check_reachability(args.repository, records,
                                mapping=load_mapping(args.mapping), bundles=args.bundle)
    print(report.render())
    if report.examined.nothing:
        return 2
    if any(c.state == CitationState.UNKNOWN for c in report.citations):
        return 2
    return 1 if report.blocking else 0


if __name__ == "__main__":
    import sys

    # Run the module, not a second copy of it. A file executed as a script is
    # `__main__`, and a sibling that imports it BY NAME gets a separate module
    # object with separate class objects — so an `isinstance` check across that
    # boundary is False for an object that is exactly that class. Imported
    # statically, by name, because a dynamic import would route around the
    # toolbelt's import-closure check.
    from errors import run_cli
    from history_anchor import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
