"""Certification bound to an exact candidate, over evidence nobody rewrote.

Everything here is **append-only project-local facts, plus a deterministic
derived view**. There is no service, nothing adjudicates, and nothing holds
state it also judges. A certification is a *reading* of records that already
exist; if the records change, the reading changes, and that is the point.

Eight properties, each of which existed as an intention somewhere and as an
enforcement nowhere.

**A raw checker result is never rewritten as PASS.** `passed` is a **derived
property** of the recorded exit status, not a field anybody can set. That is
not a stylistic choice: a boolean stored beside an exit status is a boolean
that will eventually disagree with it, and the disagreement is always in the
reassuring direction. `§17` says "never reinterpret a non-zero checker result
as PASS" — so the type makes the reinterpretation unrepresentable.

**Completeness is three-valued.** `COMPLETE`, `PARTIAL`, `MISSING`. A checker
whose output was truncated by a transport, a turn limit or a quota did not pass
and did not fail: it did not finish. Collapsing that into the exit status is how
an interrupted audit becomes a clean one.

**A certification is bound to an exact candidate** — base revision, head
revision, tree digest — and a waiver is bound to the same. A waiver that
outlives the tree it was granted against is a waiver for code nobody looked at.

**Reports are ingested byte-exact.** A cited report is a content-addressed
reference whose digest is checked against the bytes on disk. A summary of a
report is not the report.

**The index and the directory are checked as a bijection.** Both directions:
an entry with no file is a citation of nothing, and a file with no entry is
evidence nobody is accounting for. One direction is not a check.

**Discovery is not certification-verification.** Finding problems and
confirming a candidate are different acts with different postures, and a run
that did the first does not satisfy the second.

**Reopening is explicit.** A certified candidate that acquires a new finding
returns to `REOPENED`, which is a state a reader can see, rather than being
quietly re-certified or quietly left certified.

**Retention is declared per entry.** Evidence that may be discarded and evidence
that must be kept are different, and a directory in which they are
indistinguishable gets cleaned by whoever needs the disk.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "COMPLETE",
    "PARTIAL",
    "MISSING",
    "COMPLETENESS",
    "DISCOVERY",
    "CERTIFICATION_VERIFICATION",
    "RUN_KINDS",
    "OPEN",
    "CERTIFIED",
    "REOPENED",
    "CERTIFICATION_STATES",
    "RETENTION_CLASSES",
    "CandidateIdentity",
    "CheckerResult",
    "Waiver",
    "EvidenceEntry",
    "Certification",
    "certification_from",
    "index_bijection",
    "verify_reference",
]

#: The checker ran to completion and its whole output was captured.
COMPLETE = "COMPLETE"
#: It started and its output was cut off — transport, turn limit, quota, signal.
#: Neither a pass nor a fail. An interrupted run is incomplete, never clean.
PARTIAL = "PARTIAL"
#: It was supposed to run and there is no output at all.
MISSING = "MISSING"

COMPLETENESS = (COMPLETE, PARTIAL, MISSING)

#: Looking for problems. A discovery run that finds nothing has found nothing;
#: it has not confirmed anything.
DISCOVERY = "DISCOVERY"
#: Confirming a specific candidate against specific claims, with the posture
#: that goes with it. The two are recorded separately because a run that did
#: the first does not satisfy the second.
CERTIFICATION_VERIFICATION = "CERTIFICATION_VERIFICATION"

RUN_KINDS = (DISCOVERY, CERTIFICATION_VERIFICATION)

OPEN = "OPEN"
CERTIFIED = "CERTIFIED"
#: Certified, and then something arrived. Visible, rather than quietly
#: re-certified or quietly left certified.
REOPENED = "REOPENED"

CERTIFICATION_STATES = (OPEN, CERTIFIED, REOPENED)

#: `PERMANENT` outlives the project. `RELEASE` is kept while the release it
#: supports is pinned by anything. `TRANSIENT` may be discarded once the
#: capability closes. Declared per entry, because a directory in which they are
#: indistinguishable gets cleaned by whoever needs the disk.
RETENTION_CLASSES = ("PERMANENT", "RELEASE", "TRANSIENT")

_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
#: The reference shape `evidence_put` produces: `sha256-<64 hex>-<name>`.
_REFERENCE = re.compile(r"^sha256-(?P<digest>[0-9a-f]{64})-(?P<name>.+)$")


class EvidenceError(Exception):
    """An evidence record claims something the records do not support."""


@dataclass(frozen=True)
class CandidateIdentity:
    """The exact tree a certification is about.

    Three fields, for the reason D11 gives about release identity: a branch name
    or a version is a label, and two trees can carry it and differ.
    """

    base_sha: str
    head_sha: str
    tree_digest: str

    def __post_init__(self) -> None:
        for name, value, pattern in (
            ("base_sha", self.base_sha, _FULL_SHA),
            ("head_sha", self.head_sha, _FULL_SHA),
            ("tree_digest", self.tree_digest, _DIGEST),
        ):
            if not isinstance(value, str) or not pattern.match(value):
                raise EvidenceError(
                    f"{name} is {value!r}; an abbreviated or malformed identity cannot "
                    "discriminate between two candidates, which is its whole job"
                )


@dataclass(frozen=True)
class CheckerResult:
    """One checker run, as it actually came back."""

    checker: str
    command: str
    #: **Raw.** Recorded exactly as the process exited, and never adjusted.
    exit_status: int
    completeness: str = COMPLETE
    #: The content-addressed reference to the captured output, where there is
    #: one. A result citing no report is a claim about a run nobody kept.
    report_reference: str | None = None

    def __post_init__(self) -> None:
        if self.completeness not in COMPLETENESS:
            raise EvidenceError(
                f"completeness {self.completeness!r} is not one of {', '.join(COMPLETENESS)}"
            )
        if not isinstance(self.exit_status, int) or isinstance(self.exit_status, bool):
            raise EvidenceError(f"exit_status {self.exit_status!r} is not a process exit status")
        if self.completeness == MISSING and self.report_reference:
            raise EvidenceError("a MISSING result cannot cite a report")

    @property
    def passed(self) -> bool:
        """Derived, never stored.

        A stored `passed` beside a stored `exit_status` is two facts that will
        eventually disagree, and the disagreement is always reassuring. There
        is nowhere here to write "PASS" over a non-zero status.
        """
        return self.exit_status == 0 and self.completeness == COMPLETE

    def describe(self) -> str:
        if self.completeness != COMPLETE:
            return f"{self.checker}: {self.completeness} (exit {self.exit_status}) — not a verdict"
        return f"{self.checker}: {'pass' if self.passed else 'FAIL'} (exit {self.exit_status})"


@dataclass(frozen=True)
class Waiver:
    """A finding accepted, by a named authority, for one exact candidate."""

    finding_id: str
    reason: str
    authority: str
    bound_to: CandidateIdentity

    def __post_init__(self) -> None:
        for name in ("finding_id", "reason", "authority"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise EvidenceError(f"a waiver must record its {name}")

    def applies_to(self, candidate: CandidateIdentity) -> bool:
        """Only to the exact candidate it was granted against.

        A waiver that outlives its tree is a waiver for code nobody looked at,
        and it is precisely the long-lived ones that stop being re-argued.
        """
        return self.bound_to == candidate


@dataclass(frozen=True)
class EvidenceEntry:
    """One indexed piece of evidence."""

    reference: str
    description: str
    retention: str = "RELEASE"

    def __post_init__(self) -> None:
        if self.retention not in RETENTION_CLASSES:
            raise EvidenceError(
                f"retention {self.retention!r} is not one of {', '.join(RETENTION_CLASSES)}"
            )
        if not _REFERENCE.match(self.reference):
            raise EvidenceError(f"{self.reference!r} is not a content-addressed evidence reference")


def verify_reference(evidence_dir: str | Path, reference: str) -> list[str]:
    """Every way a cited report is not the bytes it claims to be.

    Byte-exact, because a summary of a report is not the report. The reference
    carries the digest, so the check is self-contained: nothing has to be
    remembered about what the file should have contained.
    """
    match = _REFERENCE.match(reference)
    if not match:
        return [f"{reference!r} is not a content-addressed evidence reference"]

    path = Path(evidence_dir) / reference
    if not path.is_file():
        return [f"{reference}: cited, and absent from the evidence directory"]
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        return [f"{reference}: cited, and could not be read ({exc})"]
    if actual != match.group("digest"):
        return [
            f"{reference}: the bytes on disk digest to {actual[:16]}…, so this is not the "
            "report that was cited"
        ]
    return []


def index_bijection(
    evidence_dir: str | Path, entries: "list[EvidenceEntry] | tuple[EvidenceEntry, ...]"
) -> tuple[list[str], list[str]]:
    """``(dangling, unaccounted)`` — the index against the directory, both ways.

    `dangling` are entries with no file: a citation of nothing.
    `unaccounted` are files no entry mentions: evidence nobody is accounting for.

    Checking one direction is not checking a bijection, and the direction that
    usually gets checked is the one that catches the less interesting problem.
    """
    directory = Path(evidence_dir)
    on_disk = {
        path.name for path in directory.iterdir()
        if path.is_file() and not path.name.startswith(".")
    } if directory.is_dir() else set()
    indexed = {entry.reference for entry in entries}

    dangling = sorted(indexed - on_disk)
    unaccounted = sorted(on_disk - indexed)
    return dangling, unaccounted


@dataclass
class Certification:
    """A reading of the records for one exact candidate."""

    candidate: CandidateIdentity
    kind: str = CERTIFICATION_VERIFICATION
    results: tuple[CheckerResult, ...] = ()
    waivers: tuple[Waiver, ...] = ()
    entries: tuple[EvidenceEntry, ...] = ()
    #: Findings that are open against this candidate right now.
    open_findings: tuple[str, ...] = ()
    #: Set when the candidate was certified and something arrived afterwards.
    reopened_by: tuple[str, ...] = ()
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.kind not in RUN_KINDS:
            raise EvidenceError(f"kind {self.kind!r} is not one of {', '.join(RUN_KINDS)}")

    def applicable_waivers(self) -> tuple[Waiver, ...]:
        return tuple(waiver for waiver in self.waivers if waiver.applies_to(self.candidate))

    def foreign_waivers(self) -> tuple[Waiver, ...]:
        """Waivers granted against some other candidate. Reported, not applied."""
        return tuple(waiver for waiver in self.waivers if not waiver.applies_to(self.candidate))

    def unwaived_findings(self) -> tuple[str, ...]:
        waived = {waiver.finding_id for waiver in self.applicable_waivers()}
        return tuple(finding for finding in self.open_findings if finding not in waived)

    def state(self) -> str:
        """`OPEN`, `CERTIFIED` or `REOPENED`, derived from the records."""
        if self.reopened_by:
            return REOPENED
        if self.kind != CERTIFICATION_VERIFICATION:
            # A discovery run cannot certify. It found what it found.
            return OPEN
        if self.unwaived_findings():
            return OPEN
        if not self.results:
            return OPEN
        if any(not result.passed for result in self.results):
            return OPEN
        return CERTIFIED

    def problems(self, evidence_dir: str | Path | None = None) -> list[str]:
        """Every reason this certification does not hold."""
        problems: list[str] = []

        for result in self.results:
            if result.completeness == PARTIAL:
                problems.append(
                    f"{result.checker}: PARTIAL — the run was cut off, so it is neither a pass "
                    "nor a fail and does not consume an audit cycle"
                )
            elif result.completeness == MISSING:
                problems.append(f"{result.checker}: MISSING — it was expected to run and did not")
            elif not result.passed:
                problems.append(f"{result.checker}: exited {result.exit_status}")

        for finding in self.unwaived_findings():
            problems.append(f"open finding with no applicable waiver: {finding}")

        for waiver in self.foreign_waivers():
            problems.append(
                f"waiver for {waiver.finding_id} is bound to another candidate "
                f"({waiver.bound_to.head_sha[:12]}…), so it does not apply here"
            )

        for identifier in self.reopened_by:
            problems.append(f"REOPENED by {identifier}: certification does not stand")

        if self.kind == DISCOVERY:
            problems.append(
                "this is a DISCOVERY run: it looked for problems and did not confirm the "
                "candidate. A certification-verification run is a separate act"
            )

        if evidence_dir is not None:
            for result in self.results:
                if result.report_reference:
                    problems.extend(verify_reference(evidence_dir, result.report_reference))
            for entry in self.entries:
                problems.extend(verify_reference(evidence_dir, entry.reference))
            dangling, unaccounted = index_bijection(evidence_dir, list(self.entries))
            problems.extend(f"index cites {item}, which is not in the evidence directory"
                            for item in dangling)
            problems.extend(f"{item} is in the evidence directory and in no index entry"
                            for item in unaccounted)

        return problems

    def render(self, evidence_dir: str | Path | None = None) -> str:
        problems = self.problems(evidence_dir)
        state = self.state()
        lines = [
            f"candidate {self.candidate.head_sha[:12]}… "
            f"(base {self.candidate.base_sha[:12]}…, tree {self.candidate.tree_digest[:12]}…): "
            f"{state}"
        ]
        lines.extend(f"  {result.describe()}" for result in self.results)
        lines.extend(f"  {item}" for item in problems)
        lines.extend(f"  note: {item}" for item in self.notes)
        if state == CERTIFIED and not problems:
            lines.append("  every checker result is raw and every waiver is bound to this candidate")
        return "\n".join(lines)


def certification_from(document: dict) -> Certification:
    """Build a certification from a project-local facts record.

    The record is **append-only project-local facts**; this is the deterministic
    derived view over them. Nothing here decides anything: it reads what was
    recorded and reports what that supports, so re-running it on an unchanged
    record gives an unchanged answer, and on a changed one gives a changed
    answer without anybody editing a verdict.
    """
    if not isinstance(document, dict):
        raise EvidenceError("a certification record must be an object")

    candidate = document.get("candidate")
    if not isinstance(candidate, dict):
        raise EvidenceError("the record must carry a `candidate` object")
    identity = CandidateIdentity(
        base_sha=candidate.get("base_sha", ""),
        head_sha=candidate.get("head_sha", ""),
        tree_digest=candidate.get("tree_digest", ""),
    )

    results = []
    for position, raw in enumerate(document.get("results") or [], start=1):
        if not isinstance(raw, dict):
            raise EvidenceError(f"results[{position}] is not an object")
        missing = [key for key in ("checker", "command", "exit_status") if key not in raw]
        if missing:
            raise EvidenceError(f"results[{position}] is missing {', '.join(missing)}")
        results.append(CheckerResult(
            checker=raw["checker"], command=raw["command"], exit_status=raw["exit_status"],
            completeness=raw.get("completeness", COMPLETE),
            report_reference=raw.get("report_reference"),
        ))

    waivers = []
    for position, raw in enumerate(document.get("waivers") or [], start=1):
        if not isinstance(raw, dict) or not isinstance(raw.get("bound_to"), dict):
            raise EvidenceError(f"waivers[{position}] must carry a `bound_to` candidate identity")
        bound = raw["bound_to"]
        waivers.append(Waiver(
            finding_id=raw.get("finding_id", ""), reason=raw.get("reason", ""),
            authority=raw.get("authority", ""),
            bound_to=CandidateIdentity(
                base_sha=bound.get("base_sha", ""), head_sha=bound.get("head_sha", ""),
                tree_digest=bound.get("tree_digest", ""),
            ),
        ))

    entries = []
    for position, raw in enumerate(document.get("entries") or [], start=1):
        if not isinstance(raw, dict):
            raise EvidenceError(f"entries[{position}] is not an object")
        entries.append(EvidenceEntry(
            reference=raw.get("reference", ""), description=raw.get("description", ""),
            retention=raw.get("retention", "RELEASE"),
        ))

    return Certification(
        candidate=identity,
        kind=document.get("kind", CERTIFICATION_VERIFICATION),
        results=tuple(results), waivers=tuple(waivers), entries=tuple(entries),
        open_findings=tuple(document.get("open_findings") or ()),
        reopened_by=tuple(document.get("reopened_by") or ()),
    )


def _cli(argv: list[str]) -> int:
    """Read a project-local certification record; print what it supports."""
    import argparse
    import json as _json
    import sys

    parser = argparse.ArgumentParser(
        prog="evidence_index.py",
        description="Report what a project's recorded evidence supports for one exact candidate.",
    )
    parser.add_argument("record", help="path to the project-local certification record (JSON)")
    parser.add_argument("--evidence-dir", help="verify cited references and the index bijection")
    args = parser.parse_args(argv)

    try:
        certification = certification_from(_json.loads(Path(args.record).read_text(encoding="utf-8")))
    except (OSError, ValueError, EvidenceError) as exc:
        print(f"the certification record could not be read: {exc}", file=sys.stderr)
        return 2

    print(certification.render(args.evidence_dir))
    # A non-zero exit is the raw fact. There is deliberately no flag that turns
    # it into a zero.
    return 0 if certification.state() == CERTIFIED and not certification.problems(
        args.evidence_dir
    ) else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
