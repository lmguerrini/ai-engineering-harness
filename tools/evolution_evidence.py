"""What happens when a project finds a pack defect that has been found before.

`policy/recurrence-classes.json` is this pack's list of failure classes and the
oracle that proves each one closed. It is the deduplication mechanism, and it
works by construction: evidence that belongs to an existing class strengthens
that class rather than creating a second record of it. What it could not do until
now is **hold the evidence** — the schema carried a class and a selector and
nowhere to say who found it, in which project, at which revision, or how it was
reproduced. So a recurrence either overwrote nothing or was lost.

This module adds the missing half and nothing else. It does not adjudicate
meaning: a submission DECLARES which class it belongs to, exactly as a project
declares its own change class and its own task classes elsewhere in this pack.
What Core does is narrower and is the part a person gets wrong:

*   **It refuses to guess.** A submission proposing a NEW class whose name is a
    near-duplicate of an existing one is not merged and not accepted; it is
    returned as `NEEDS_DISTINCTION` until the submitter says what different
    invariant it violates. Guessing either way is the failure — a wrong merge
    loses a distinct failure mode, a wrong split loses the pattern that four
    instances of one thing were four instances of one thing.
*   **It never collapses provenance.** Occurrences are appended, never rewritten
    and never summarised. A class that has been hit five times carries five
    records, each naming its own project, release, revision, reproduction and
    producer, so a later reader can go back to any one of them.
*   **A process failure is evidence like any other.** The classes already include
    *oracle satisfied for a reason other than its claim*, *vacuous mutation
    test*, *gate failure hidden by a pipeline or lost exit code*, *audit evidence
    about revision A accepted for revision B* and *false RUNNING from process
    existence*. Those recur across real work exactly the way product defects do,
    and they use this pipeline unchanged.

**The bound, stated rather than dressed up.** Near-duplicate detection is over
words. A submission that describes the same invariant in entirely different
vocabulary reads as new, and a submission that shares vocabulary with an
unrelated class is returned for a distinction it should not have to make. Both
are failures towards ASKING A PERSON, which is the direction this pack takes
whenever the alternative is Core deciding what two sentences mean.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

__all__ = [
    "Evidence", "Occurrence", "Verdict", "RECURRENCE", "NEW", "NEEDS_DISTINCTION",
    "classify", "reinforce", "occurrences_of", "load", "problems",
]

#: This submission belongs to a class the pack already records.
RECURRENCE = "RECURRENCE"
#: A materially new failure class, which becomes a new entry with its own oracle.
NEW = "NEW"
#: It resembles an existing class and the submission has not said how it differs.
NEEDS_DISTINCTION = "NEEDS_DISTINCTION"

#: Words that carry no distinguishing weight in a failure-class name.
_NOISE = frozenset("""
a an the and or of in on at to from for by with without into over under
is are was were be been being not no non
""".split())


def _words(text: str) -> frozenset:
    return frozenset(w for w in re.split(r"[^a-z0-9]+", str(text).lower()) if w and w not in _NOISE)


def _overlap(left: str, right: str) -> float:
    """How much of the smaller name the two share. Jaccard was wrong here: a
    short, precise class name and a long one describing the same thing scored
    low because the long one has more words."""
    a, b = _words(left), _words(right)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


#: Above this, two class names are near-duplicates and a submitter must say what
#: differs. Chosen so that the shipped classes do not collide with each other —
#: `test_evolution_evidence.py` asserts that, so the threshold is measured
#: against the real vocabulary rather than picked.
NEAR_DUPLICATE = 0.75


def _present(value: object) -> str:
    """The text of a value that is actually there, or `""`.

    **`str(value).strip()` IS NOT THIS.** It turns `None` into the string
    `"None"`, which is four characters of nothing and passes every emptiness
    test — so a submission with `distinct_because=None` was accepted as
    distinguished "because None", and one whose project, release, revision and
    reproduction were all `None` recorded an occurrence nobody can go back to.
    Both found by an independent reading, and both are the same defect this
    release had already fixed in `qualification.identity_from_observation` a few
    hours earlier: a null is the absence of a value and stringifying it is how
    absence becomes presence.
    """
    if value is None or isinstance(value, bool):
        return ""
    # AN EMPTY CONTAINER IS ALSO ABSENCE. `str([])` is `"[]"`, two characters
    # that survive a strip — the same shape as `str(None)` one type over, and
    # the reading that found the first found this too.
    if isinstance(value, (list, tuple, set, dict)) and not value:
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("none", "null", "[]", "{}", "()") else text


@dataclass(frozen=True)
class Occurrence:
    """One time a class was hit, with enough to go back to it."""

    project: str
    release: str
    revision: str
    #: How it was reproduced. Not a description of the defect — the command, the
    #: fixture, or the reading that produced it.
    reproduction: str
    #: Who found it. A worker, a reader, a person, a suite.
    producer: str = ""
    provider: str = ""
    #: The mechanisms this occurrence touched, so a later reader can see whether
    #: a class keeps landing in one place.
    mechanisms: tuple = ()
    observed_at: str = ""
    #: What this occurrence adds that earlier ones did not — a boundary
    #: condition, a new path in, a wider blast radius.
    adds: str = ""


@dataclass(frozen=True)
class Evidence:
    """A submission from a project, before anything is written."""

    #: The class the submitter says this belongs to. An existing name is a
    #: recurrence; a new name is a proposal.
    recurrence_class: str
    occurrence: Occurrence
    #: Required when proposing a class that resembles an existing one: which
    #: different invariant it violates. Its absence is why a near-duplicate is
    #: returned rather than merged or accepted.
    distinct_because: str = ""


@dataclass(frozen=True)
class Verdict:
    outcome: str
    #: The existing class this belongs to, or the one it resembles.
    matched: str = ""
    similarity: float = 0.0
    why: str = ""

    def sentence(self) -> str:
        return f"{self.outcome}: {self.why}"


def load(path: str | Path) -> list:
    return json.loads(Path(path).read_text(encoding="utf-8"))["classes"]


def problems(evidence: Evidence) -> tuple:
    """Everything that stops this submission from being usable at all."""
    found = []
    if not _present(evidence.recurrence_class):
        found.append("a submission must name the class it belongs to or proposes")
    occurrence = evidence.occurrence
    for name in ("project", "release", "revision", "reproduction"):
        if not _present(getattr(occurrence, name, "")):
            found.append(
                f"an occurrence must record {name}; evidence whose provenance is a recollection "
                f"cannot be gone back to, and going back to it is what this record is for")
    return tuple(found)


def classify(evidence: Evidence, classes) -> Verdict:
    """Whether this is a recurrence, a new class, or a question for a person."""
    broken = problems(evidence)
    if broken:
        raise ValueError("; ".join(broken))

    names = [entry["class"] for entry in classes]
    if evidence.recurrence_class in names:
        # A DISTINCTION AGAINST THE CLASS YOU ARE SUBMITTING UNDER IS A
        # CONTRADICTION. This returned RECURRENCE and threw the explanation
        # away, so a submitter who had said *this violates a different
        # invariant* had that statement silently merged into the class they
        # were distinguishing themselves from. Found by an independent reading.
        # Refusing sends them back to name the new class, which is the whole
        # point of having said it.
        if _present(evidence.distinct_because):
            raise ValueError(
                f"this submission names the recorded class {evidence.recurrence_class!r} AND "
                f"states how it differs ({_present(evidence.distinct_because)}). Those cannot "
                f"both be true: submit it under that class with no distinction, or propose a "
                f"class of its own")
        return Verdict(
            RECURRENCE, matched=evidence.recurrence_class, similarity=1.0,
            why=(f"{evidence.recurrence_class!r} is already recorded. This strengthens it with "
                 f"another occurrence rather than creating a second record of one failure"))

    nearest, score = "", 0.0
    for name in names:
        overlap = _overlap(evidence.recurrence_class, name)
        if overlap > score:
            nearest, score = name, overlap

    if score >= NEAR_DUPLICATE and not _present(evidence.distinct_because):
        return Verdict(
            NEEDS_DISTINCTION, matched=nearest, similarity=score,
            why=(f"{evidence.recurrence_class!r} closely resembles the recorded class "
                 f"{nearest!r}. It is not merged and not accepted: say which different "
                 f"invariant it violates, or submit it under the existing class. Merging two "
                 f"failure modes loses one of them and splitting one loses the pattern"))

    return Verdict(
        NEW, matched=nearest, similarity=score,
        why=(f"{evidence.recurrence_class!r} is a materially new class"
             + (f", distinguished from {nearest!r} because {_present(evidence.distinct_because)}"
                if _present(evidence.distinct_because) else "")
             + ". It needs an entry and an oracle of its own"))


def reinforce(classes, evidence: Evidence, *, files=(), keyword=None) -> list:
    """The classes with this evidence recorded. Appends; never rewrites.

    A new class arrives with no oracle and the entry says so — `files` empty is
    the state a pack-evolution session resolves, and it is visible rather than
    implied. `test_recurrence_classes.py` refuses a class whose selector matches
    no test, so an entry cannot sit there unresolved and pass.
    """
    verdict = classify(evidence, classes)
    if verdict.outcome == NEEDS_DISTINCTION:
        raise ValueError(verdict.why)

    updated = [dict(entry) for entry in classes]
    target = evidence.recurrence_class
    record = _as_dict(evidence.occurrence)
    for entry in updated:
        if entry["class"] == target:
            existing = list(entry.get("occurrences") or ())
            # A REPLAY IS NOT A SECOND OCCURRENCE. Calling this twice with one
            # piece of evidence stored two identical records, so a class read as
            # having recurred without anything having recurred — the strength of
            # a record is how many separate times it was hit, and a retry, a
            # re-import or a re-run must not add to it. Found by an independent
            # reading.
            if record in existing:
                raise ValueError(
                    f"this occurrence is already recorded against {target!r}; recording it "
                    f"again would say the failure recurred when nothing recurred. If it did "
                    f"happen again, the second time has its own revision and reproduction")
            existing.append(record)
            entry["occurrences"] = existing
            return updated

    updated.append({
        "class": target,
        "files": list(files),
        "keyword": keyword,
        "occurrences": [record],
    })
    return updated


def _as_dict(occurrence: Occurrence) -> dict:
    return {
        "project": occurrence.project, "release": occurrence.release,
        "revision": occurrence.revision, "reproduction": occurrence.reproduction,
        "producer": occurrence.producer, "provider": occurrence.provider,
        "mechanisms": list(occurrence.mechanisms), "observed_at": occurrence.observed_at,
        "adds": occurrence.adds,
    }


def occurrences_of(classes, name: str) -> tuple:
    """Every recorded occurrence of one class, in the order they were recorded."""
    for entry in classes:
        if entry["class"] == name:
            return tuple(Occurrence(**{**record, "mechanisms": tuple(record.get("mechanisms", ()))})
                         for record in (entry.get("occurrences") or ()))
    return ()


def _cli(argv: list[str]) -> int:  # pragma: no cover - exercised through the API
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="evolution_evidence.py",
        description="Whether a piece of evidence is a recurrence, a new class, or a question.")
    parser.add_argument("classes", help="path to policy/recurrence-classes.json")
    parser.add_argument("--class", dest="name", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--reproduction", required=True)
    parser.add_argument("--distinct-because", default="")
    arguments = parser.parse_args(argv)

    evidence = Evidence(
        recurrence_class=arguments.name,
        occurrence=Occurrence(project=arguments.project, release=arguments.release,
                              revision=arguments.revision, reproduction=arguments.reproduction),
        distinct_because=arguments.distinct_because)
    try:
        verdict = classify(evidence, load(arguments.classes))
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(verdict.sentence())
    return 0 if verdict.outcome != NEEDS_DISTINCTION else 2


if __name__ == "__main__":
    import sys as _sys

    from errors import run_cli
    from evolution_evidence import _cli as _entry

    raise SystemExit(run_cli(_entry, _sys.argv[1:]))
