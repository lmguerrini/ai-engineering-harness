"""The question nobody was asking: is the COMPLETE history public-safe, strictly?

Two scans shipped and both were correct. Neither asked this.

*   The **staged** scan is strict and covers what is about to be committed.
*   The **range** scan is tiered and covers what a push would send.

The strict tier and the complete reachable history had never been combined in
any invocation, and the gap is not academic: a project can be public-safe by
construction, pass every shipped gate, and reach its first push with private
material in a historical blob that no tip carries. That was measured by driving
the scanner directly, because no command existed to do it.

**A private repository does not resolve this.** One click makes it public, that
click has no gate in front of it, and by then the history is already on
somebody else's infrastructure. *Private is not permission to upload history
that would later need sanitising.*

## Detection without adjudication makes things worse

This is why the two halves ship together and why neither is useful alone. The
measured scan produced **147 findings. Four were genuine. One hundred and six
were ordinary English** — `harness`, `envelope`, `phase 2` — and among the rest
were `.gitignore` entries whose removal would make the repository *less* safe.

Emitting that count as a remediation list manufactures pressure to rewrite
history in order to remove nothing, and rewriting history is the irreversible
operation this whole area exists to keep behind a human. So:

**A remediation list is refused while any occurrence is unclassified**, and
classification is **per occurrence, never per term**. A term that is private in
one file and ordinary English in the next is the common case rather than the
exception — the project that measured this found one class applied per term
instead of per occurrence and had to correct it — so a classification that
names only a term is refused as one that has not been made.

## What this never does

It produces a classified list a human acts on. It does not remediate, rewrite,
amend or delete anything: that is `policy/hitl-matrix.md` rows 2 and 4, and
`DECISIONS.md` D23 clause 6 withholds the permission from Core deliberately.
Nor does it authorise a push — the gate's checks are joined by an explicit
human authorisation, separately, which an earlier draft of the lifecycle table
silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import gitread
import outgoing_scan
from errors import IntegrityError, PreconditionError
from instrument import Examined

__all__ = [
    "Occurrence",
    "Adjudication",
    "OccurrenceClass",
    "HistoryReport",
    "scan_complete_history",
    "remediation_list",
    "unadjudicated",
    "by_finding",
    "obligations",
    "UNIVERSAL_OBLIGATIONS",
    "PUBLICATION_OBLIGATIONS",
]

class OccurrenceClass:
    """What one occurrence of one finding actually is.

    Four answers, and three of them are reasons to leave the history alone.
    """

    #: Genuinely private material that must not be published.
    GENUINE = "GENUINE"
    #: The word in its ordinary sense. A hundred and six of a hundred and
    #: forty-seven, in the one corpus where this was measured.
    ORDINARY_LANGUAGE = "ORDINARY_LANGUAGE"
    #: Material whose removal would make the repository less safe — a
    #: `.gitignore` entry naming what must never be committed being the
    #: measured case.
    LEGITIMATE_PUBLIC_BOUNDARY = "LEGITIMATE_PUBLIC_BOUNDARY"
    #: Nobody has looked at this one yet. The list is refused while any remain.
    UNCLASSIFIED = "UNCLASSIFIED"

    ALL = (GENUINE, ORDINARY_LANGUAGE, LEGITIMATE_PUBLIC_BOUNDARY, UNCLASSIFIED)


@dataclass(frozen=True)
class Occurrence:
    """One finding, at one place, in one object.

    Identity is the triple. Two occurrences of the same term in two blobs are
    two occurrences and are classified twice, because one of them being ordinary
    English says nothing about the other.
    """

    #: The scanner's own redacted description of what it found, not the raw
    #: string. A report that reproduced the private material would be the leak
    #: it is reporting, and this one gets stored as evidence.
    finding: str
    object_sha: str
    path: str
    location: str = "blob"

    @property
    def key(self) -> tuple[str, str, str, str]:
        """Finding, object, path AND location.

        `location` was missing, so the same term found in a path and in that
        path's blob shared one key and one adjudication covered both — the blob
        occurrence could be genuine and was silently treated as judged. Found by
        a cross-vendor auditor. Two places are two occurrences, which is the
        rule this whole stage exists to enforce.
        """
        return (self.finding, self.object_sha, self.path, self.location)

    def __str__(self) -> str:
        return f"{self.finding} in {self.location} {self.path or self.object_sha[:12]} ({self.object_sha[:12]})"


@dataclass(frozen=True)
class Adjudication:
    """A human's reading of one occurrence, with the reason."""

    occurrence_key: tuple[str, str, str, str]
    classification: str
    because: str

    def __post_init__(self) -> None:
        if self.classification not in OccurrenceClass.ALL:
            raise IntegrityError("no such occurrence class", found=repr(self.classification),
                                 known=", ".join(OccurrenceClass.ALL))
        if self.classification != OccurrenceClass.UNCLASSIFIED and not self.because.strip():
            raise PreconditionError(
                "a classification states its reason; one without a reason cannot be reviewed, "
                "and this stage exists because a count without reasons is not a remediation list",
                occurrence=str(self.occurrence_key),
            )


@dataclass
class HistoryReport:
    repository: str
    mode: str
    occurrences: list[Occurrence] = field(default_factory=list)
    objects_examined: int = 0
    refs_examined: int = 0
    skipped: list[str] = field(default_factory=list)
    vocabulary: str = ""
    rule_source: str = ""

    @property
    def examined(self) -> Examined:
        return Examined({"refs": self.refs_examined, "objects": self.objects_examined})

    def render(self) -> str:
        examined = self.examined
        verdict = examined.verdict_or_nothing(
            f"clean ({examined.summary()})" if not self.occurrences
            else f"{len(self.occurrences)} occurrence(s) to adjudicate ({examined.summary()})"
        )
        # Two axes, and both belong in the headline. The SCOPE is in the
        # subject because this module only ever asks the complete question —
        # that is what it is for — and the TIER is the mode, because the same
        # scope gives different answers under the two rule sets and a number
        # quoted without its tier is the defect this pack already measured.
        lines = [outgoing_scan.MODES.headline(
            f"complete reachable history of {self.repository}", verdict, self.mode)]
        if self.vocabulary:
            lines.append(f"  rules applied: {self.vocabulary}")
        if self.rule_source:
            lines.append(f"  rules read from: {self.rule_source}")
        for occurrence in self.occurrences:
            lines.append(f"  {occurrence}")
        for entry in self.skipped:
            lines.append(f"  NOT SCANNED: {entry}")
        if self.occurrences:
            lines.append(
                "  this is a finding list, NOT a remediation list. Every occurrence is "
                "adjudicated individually before anything is proposed, and remediating a "
                "historical object is a rewrite: rows 2 and 4."
            )
        return "\n".join(lines)


def scan_complete_history(
    repository: str | Path,
    scanner: outgoing_scan.Scanner,
    *,
    content_exempt_paths: tuple[str, ...] = (),
) -> HistoryReport:
    """Every reachable object in the repository, at the scanner's own tier.

    The complete reachable set, not one ref's history: a blob reachable only
    from a tag, a stale branch or a recovery ref is as published as any other
    once the repository is.
    """
    repository = Path(repository)
    report = HistoryReport(
        repository=str(repository), mode=scanner.mode.name,
        vocabulary=scanner.vocabulary.summary(),
    )
    # Every ref, not every branch. A blob reachable only from a tag, a stale
    # branch or a recovery ref is as published as any other once the repository
    # is, and `refs/notes/*` is the namespace this pack exists to remember.
    names = [entry["refname"] for entry in gitread.refs(repository)]
    report.refs_examined = len(names)
    if not names:
        return report

    seen: set[str] = set()
    for name in names:
        for sha, path in gitread.objects_in_outgoing_range(repository, name, None):
            if sha in seen:
                continue
            seen.add(sha)
            report.objects_examined += 1
            if outgoing_scan.pathmatch.matches_any(path, list(content_exempt_paths)):
                # Scoped, never skipped: a declared exemption removes the
                # project's own vocabulary from this object's findings and
                # leaves every universal rule in force.
                exempt = True
            else:
                exempt = False
            if path:
                for leak in scanner.scan_name(path, location="path", subject=path):
                    report.occurrences.append(
                        Occurrence(finding=leak.detail, object_sha=sha, path=path, location="path"))
            try:
                if gitread.object_type(repository, sha) != "blob":
                    continue
                if gitread.object_size(repository, sha) > outgoing_scan.MAX_SCANNED_BLOB_BYTES:
                    report.skipped.append(f"{path or sha[:12]} exceeds the scan limit")
                    continue
                text = outgoing_scan._decoded(gitread.object_bytes(repository, sha))
            except Exception as exc:  # a refusal from the read-only layer
                report.skipped.append(f"{path or sha[:12]} could not be read: {exc}")
                continue
            if text is None:
                report.skipped.append(f"{path or sha[:12]} is not decodable as text")
                continue
            for leak in outgoing_scan._scoped(
                scanner.scan(text, location="blob", subject=path or sha), exempt
            ):
                report.occurrences.append(
                    Occurrence(finding=leak.detail, object_sha=sha, path=path, location="blob"))
    return report


def remediation_list(
    report: HistoryReport, adjudications: dict[tuple[str, str, str, str], Adjudication]
) -> list[Occurrence]:
    """The occurrences a human judged genuine, or a refusal.

    Refused while **any** occurrence is unadjudicated, because a partially
    adjudicated list is the raw count wearing a review's clothes — and the raw
    count, in the corpus where this was measured, was thirty-six times larger
    than the genuine set.
    """
    unclassified = [
        occurrence for occurrence in report.occurrences
        if adjudications.get(occurrence.key) is None
        or adjudications[occurrence.key].classification == OccurrenceClass.UNCLASSIFIED
    ]
    if unclassified:
        raise PreconditionError(
            "a remediation list is refused while any occurrence is unadjudicated: emitting a "
            "raw count as a list of things to remove manufactures pressure to rewrite history "
            "in order to remove nothing",
            unadjudicated=len(unclassified),
            of=len(report.occurrences),
            first=str(unclassified[0]),
        )

    return [
        occurrence for occurrence in report.occurrences
        if adjudications[occurrence.key].classification == OccurrenceClass.GENUINE
    ]


def by_finding(
    report: HistoryReport, adjudications: dict[tuple[str, str, str, str], Adjudication]
) -> dict[str, dict[str, int]]:
    """How each finding was classified across its occurrences.

    A classification recorded against a **term** rather than against each of
    its occurrences is not a classification — a word that is private in one
    file is ordinary English in the next, which is the common case rather than
    the exception, and one project applied a class per term and had to correct
    it. Keying an adjudication by the occurrence triple makes the per-term form
    unexpressible; this makes the split **visible**, so a reader can see that a
    finding was judged nine times rather than once.
    """
    split: dict[str, dict[str, int]] = {}
    for occurrence in report.occurrences:
        adjudication = adjudications.get(occurrence.key)
        classification = (
            adjudication.classification if adjudication else OccurrenceClass.UNCLASSIFIED)
        counts = split.setdefault(occurrence.finding, {})
        counts[classification] = counts.get(classification, 0) + 1
    return split


def unadjudicated(
    report: HistoryReport, adjudications: dict[tuple[str, str, str, str], Adjudication]
) -> list[Occurrence]:
    """What still needs a person, so the stage can be worked through."""
    return [
        occurrence for occurrence in report.occurrences
        if adjudications.get(occurrence.key) is None
        or adjudications[occurrence.key].classification == OccurrenceClass.UNCLASSIFIED
    ]


# --- which obligations a project actually carries -----------------------------------


#: Hold for every project, whatever it intends. What they find is private
#: whoever wrote it, and **private is an access control rather than a property
#: of the content** — one click makes a repository public, that click has no
#: gate in front of it, and by then the history is already elsewhere.
UNIVERSAL_OBLIGATIONS = (
    "the complete reachable history is scanned at the strict tier before a first remote",
    "every occurrence is adjudicated individually before any remediation is proposed",
    "an explicit human authorisation, separately, at the first remote and at first public "
    "visibility (policy/hitl-matrix.md row 2)",
)

#: Apply only where a project says it intends to publish. These are about
#: whether a stranger can read and rebuild the thing, which is a different
#: question from whether it is safe — and readability must not borrow safety's
#: urgency. A project that will never be published is not walked through them.
PUBLICATION_OBLIGATIONS = (
    "each validation profile declares the environment it is reproducible by",
    "a profile declared `public_clone` runs from a fresh clone with every private root unset",
    "the repository explains itself to a reader who was not here",
)


def obligations(contract: object) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    """``(applicable, not_applicable, why)`` for one project's declaration.

    The split `DECISIONS.md` D23 clause 3 records: Core carries universal
    public-safety invariants, and reproducibility and presentation are
    profile-scoped. An internal project is not walked through publication
    ceremony because Core is capable of performing it.

    A project that has not said is treated as **not yet public** for the
    presentation half and still carries every universal invariant — because the
    safety half is what an undeclared intent must not be allowed to switch off.
    """
    intent = getattr(contract, "publication_intent", None)
    if intent == "public":
        return (UNIVERSAL_OBLIGATIONS + PUBLICATION_OBLIGATIONS, (),
                "the project declares it intends to publish")
    if intent == "internal":
        return (UNIVERSAL_OBLIGATIONS, PUBLICATION_OBLIGATIONS,
                "the project declares itself internal; the safety invariants still hold, because "
                "private is an access control and access controls change")
    return (UNIVERSAL_OBLIGATIONS, PUBLICATION_OBLIGATIONS,
            "the project has not declared an intent, so the presentation obligations are not "
            "imposed and every safety invariant still is — an undeclared intent must not be able "
            "to switch off the half that is about content")


def _cli(argv: list[str]) -> int:
    """Scan every reachable object for private material, strictly.

    Usage: ``publication_history.py REPO [--project PATH] [--term TERM ...]
                                    [--pattern REGEX ...] [--tiered]``

    Strict by default, because the question this exists to ask is the one the
    tiered scan cannot answer. Exit status: ``0`` nothing found, ``1``
    occurrences to adjudicate, ``2`` nothing examined or the rules could not be
    read.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="publication_history.py",
        description="Whether the complete reachable history is public-safe, at the strict tier.")
    parser.add_argument("repository", nargs="?")
    parser.add_argument("--project", help="path to PROJECT.yaml; supplies vocabulary and exemptions")
    parser.add_argument("--term", action="append", default=[])
    parser.add_argument("--pattern", action="append", default=[])
    parser.add_argument("--tiered", action="store_true",
                        help="run the tiered rules instead; the answer will differ and the "
                             "headline will say which ran")
    args = parser.parse_args(argv)

    contract = None
    if args.project:
        from project_contract import ContractError, ProjectContract

        try:
            contract = ProjectContract.load(args.project)
        except ContractError as exc:
            print(f"CONTRACT UNREADABLE {exc}")
            return 2

    try:
        term_set = outgoing_scan._term_set_from_args(args)
    except Exception as exc:
        print(f"CONTRACT UNREADABLE {exc}")
        return 2

    repository = args.repository or (contract.repository() if contract else None)
    if not repository:
        print("a repository is required, either positionally or via --project")
        return 2

    scanner = outgoing_scan.Scanner(term_set, strict=not args.tiered)
    report = scan_complete_history(
        repository, scanner,
        content_exempt_paths=tuple(contract.content_exempt) if contract else (),
    )
    source = getattr(contract, "default_terms_source", None) if contract else None
    report.rule_source = source.summary() if source is not None else ""
    print(report.render())
    if report.examined.nothing:
        return 2
    return 1 if report.occurrences else 0


if __name__ == "__main__":
    import sys

    # Run the module, not a second copy of it. A file executed as a script is
    # `__main__`, and a sibling that imports it BY NAME gets a separate module
    # object with separate class objects — so an `isinstance` check across that
    # boundary is False for an object that is exactly that class. Imported
    # statically, by name, because a dynamic import would route around the
    # toolbelt's import-closure check.
    from errors import run_cli
    from publication_history import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
