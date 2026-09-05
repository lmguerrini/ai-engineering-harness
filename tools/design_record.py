"""A design, frozen before the implementation it governs — read, never adjudicated.

The failure this exists for is not a defect. It is a *shape*:

    implement → defect → repair → defect in the repair → repair → …

Each repair is individually reasonable, which is why nobody notices the shape
from inside it. `skills/core/repair.md` already bounds what happens after a
defect exists. This is the other half: before a material capability is
implemented, the alternatives, the failure modes, the authority boundaries and
the oracles are written down and frozen, so the first detector of a bad design
is not the defect it produces.

**This module decides nothing.** It reads a file and reports whether that file
states what it claims to state. It does not judge whether the selected design
is good — that is product meaning, and Core does not adjudicate product
meaning. It cannot open a capability, satisfy a HITL row, or move any release
state. `capability_open` composes it, exactly as it composes the pin, the
adapters and the context, and the aggregate answer stays there.

**Risk-scaled, because ceremony nobody needs is ceremony nobody performs.**

    TRIVIAL   reversible, local, no new promise      no record required
    ROUTINE   real work inside an existing design    mechanism + oracles
    MATERIAL  a new promise, authority or boundary   the whole thing

The class is an INPUT. Core cannot know which of a project's capabilities are
material — that is a property of the project, as `requires.project_context`
already is. A caller who declares `TRIVIAL` to avoid the record has made a
visible claim in the readiness report rather than a silent one, which is the
honest bound and is recorded as a limitation rather than claimed as prevention.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "TRIVIAL", "ROUTINE", "MATERIAL", "CHANGE_CLASSES", "CHANGE_CLASS_RANK",
    "SELECTED", "REJECTED",
    "ACCEPTANCE", "NEGATIVE", "MUTATION", "REHEARSAL", "ORACLE_KINDS",
    "Candidate", "Oracle", "DesignRecord", "read", "required_for",
]

#: Reversible, local, and promising nothing that was not already promised.
TRIVIAL = "TRIVIAL"
#: Real work inside a design that already exists and is not being changed.
ROUTINE = "ROUTINE"
#: A new promise, a new authority, a new boundary, or a change to one.
MATERIAL = "MATERIAL"
CHANGE_CLASSES = (TRIVIAL, ROUTINE, MATERIAL)

#: The classes are a LADDER, not three labels. RP2.4.1 R1: a record may be as
#: strong as the work requires or stronger, never weaker. Ranked here rather
#: than compared by name at each caller, because a comparison written twice is
#: two answers to one question waiting to disagree.
CHANGE_CLASS_RANK = {TRIVIAL: 0, ROUTINE: 1, MATERIAL: 2}

SELECTED = "SELECTED"
REJECTED = "REJECTED"

ACCEPTANCE = "ACCEPTANCE"
NEGATIVE = "NEGATIVE"
MUTATION = "MUTATION"
REHEARSAL = "REHEARSAL"
ORACLE_KINDS = (ACCEPTANCE, NEGATIVE, MUTATION, REHEARSAL)

_SHA = re.compile(r"^[0-9a-f]{40}$")


def required_for(change_class: str) -> bool:
    """Whether a change of this class must carry a frozen design record.

    The scaling is the point: a rule that demands a design document for a typo
    is a rule that gets routed around, and a rule that gets routed around is
    worse than none because the project believes it is enforced.
    """
    return change_class in (ROUTINE, MATERIAL)


@dataclass
class Candidate:
    """One design that was considered, and what was decided about it."""

    name: str
    verdict: str
    why: str = ""


@dataclass
class Oracle:
    """One check that must exist before the implementation it judges."""

    ident: str
    kind: str
    property: str = ""
    selector: str = ""


@dataclass
class DesignRecord:
    path: str
    change_class: str = ""
    base_revision: str = ""
    frozen: bool = False
    mechanism: str = ""
    candidates: list = field(default_factory=list)
    failure_modes: list = field(default_factory=list)
    authority: str = ""
    oracles: list = field(default_factory=list)
    unreadable: str = ""

    @property
    def selected(self):
        chosen = [c for c in self.candidates if c.verdict == SELECTED]
        return chosen[0] if len(chosen) == 1 else None

    @property
    def rejected(self) -> list:
        return [c for c in self.candidates if c.verdict == REJECTED]

    def of_kind(self, kind: str) -> list:
        return [o for o in self.oracles if o.kind == kind]

    def problems(self, *, mutation_begins_at: str = "", repository=None,
                 required_class: str = "") -> list:
        """Everything this record does not state that its class requires.

        An empty list is not *the design is good*. It is *the design was made
        before the implementation, against stated alternatives, with stated
        failure modes and frozen oracles* — which is the only part a machine can
        settle.

        `required_class` is the strength the OPENING AUTHORITY demands, and it
        is the whole of the RP2.4.1 R1 repair. 2.4.0 asked this record only
        whether it stated what ITS OWN class requires, so a record declaring
        itself TRIVIAL — which requires nothing — satisfied a capability its
        caller had honestly declared MATERIAL, and the readiness report said
        VERIFIED. The comparison lives here, in the module that already owns
        *does this record state what is required of it*, so that every caller
        states what it needs instead of re-deriving the answer beside it.
        Callers that require nothing get 2.4.0's answer unchanged.
        """
        if self.unreadable:
            return [self.unreadable]
        found: list = []

        if required_class:
            if required_class not in CHANGE_CLASSES:
                # Never ranked leniently. An unrecognised spelling that fell
                # through to rank 0 would make the requirement vanish exactly
                # when a caller was trying to state one.
                found.append(
                    f"the required change class is {required_class!r}; it must be one of "
                    f"{', '.join(CHANGE_CLASSES)}, because an unrecognised requirement is "
                    f"not a weaker requirement")
            elif self.change_class in CHANGE_CLASSES and (
                    CHANGE_CLASS_RANK[self.change_class] < CHANGE_CLASS_RANK[required_class]):
                found.append(
                    f"this capability requires a {required_class} design and the record "
                    f"declares itself {self.change_class}. A record cannot lower the bar the "
                    f"work was opened against: state the class the work actually is, or open "
                    f"the capability as the class the record actually states")
                return found

        if self.change_class not in CHANGE_CLASSES:
            found.append(
                f"the change class is {self.change_class!r}; it must be one of "
                f"{', '.join(CHANGE_CLASSES)}, because the class is what scales everything else")
            return found
        if self.change_class == TRIVIAL:
            # Reached only when nothing stronger was required: the rank check
            # above has already refused a TRIVIAL record under a stronger bar.
            return found
        if not self.frozen:
            found.append("the record does not declare itself frozen, so it is a draft and the "
                         "implementation it governs is not authorised by it")
        if not self.mechanism.strip():
            found.append("no mechanism is stated. A design that cannot name what the machine "
                         "actually does is a design of a symptom")

        if self.change_class == MATERIAL:
            if len(self.candidates) < 2:
                found.append(
                    f"{len(self.candidates)} design(s) considered. A material change states at "
                    f"least two, because a single candidate is a decision nobody made")
            nameless = [i for i, c in enumerate(self.candidates, 1) if not c.name.strip()]
            if nameless:
                found.append(
                    f"design(s) {nameless} are considered and unnamed. A row with no design in "
                    f"it is a row, and the whole record was written to be read by somebody")
            if not self.rejected:
                found.append("no alternative was rejected. A design with nothing rejected "
                             "records a preference, not a choice")
            elif not any(c.why.strip() for c in self.rejected):
                # THE DOCUMENTS ALREADY SAID THIS and the code did not check it:
                # *a rejected design with no reason is not a rejection; it is a
                # list*. An independent reader got an empty MATERIAL record past
                # the whole mechanism.
                found.append("no rejected design says why it was rejected. A rejection with no "
                             "reason is not a rejection; it is a list")
            if self.selected is None:
                chosen = [c for c in self.candidates if c.verdict == SELECTED]
                found.append(f"{len(chosen)} designs are marked {SELECTED}; exactly one must be")
            if not self.failure_modes:
                found.append("no failure mode of the selected design is stated. The failure "
                             "modes are what the oracles are for")
            if not self.authority.strip():
                found.append("no authority boundary is stated. A mechanism that does not say "
                             "what it must never decide will eventually decide it")
            if not self.of_kind(MUTATION):
                found.append("no mutation oracle. A guard nobody has tried to break is a claim, "
                             "not evidence")

        empty = [o.ident or "?" for o in self.oracles if not o.property.strip()]
        if empty and self.change_class in (ROUTINE, MATERIAL):
            found.append(
                f"oracle(s) {empty} state no property. An oracle that does not say what it "
                f"settles cannot be the thing the implementation is not allowed to choose")
        for kind in (ACCEPTANCE, NEGATIVE):
            if not self.of_kind(kind):
                found.append(f"no {kind} oracle. Acceptance says what must hold; negative says "
                             f"what must be refused; a design with only one of them is half a "
                             f"specification")

        found.extend(self._revision_problems(mutation_begins_at, repository))
        return found

    def _revision_problems(self, mutation_begins_at: str, repository) -> list:
        """A design is frozen AT something, and backdating is the obvious cheat."""
        found: list = []
        if not _SHA.match(self.base_revision or ""):
            found.append(
                f"the base revision is {self.base_revision!r}; a frozen design names the exact "
                f"forty-character revision it was frozen against, or it names nothing")
            return found
        if repository is None:
            return found
        import gitread

        try:
            gitread._run(repository, "cat-file", "-e", f"{self.base_revision}^{{commit}}",
                         timeout=30)
        except Exception:
            found.append(f"the base revision {self.base_revision[:12]} does not resolve in this "
                         f"repository, so the design is frozen against nothing")
            return found
        try:
            gitread._run(repository, "merge-base", "--is-ancestor", self.base_revision, "HEAD",
                         timeout=30)
        except Exception:
            found.append(f"the base revision {self.base_revision[:12]} is not an ancestor of "
                         f"HEAD, so it is not the state this work started from")
        if mutation_begins_at:
            # RESOLVED FIRST. The strictness of this whole binding rested on a
            # string comparison, so the same commit spelled as an abbreviation
            # or as a ref name was not equal to the base and the reflexive
            # `--is-ancestor` then said yes: a design frozen against the very
            # commit where mutation began reported FROZEN. The pack already
            # says an abbreviation is not a weaker claim but a different one
            # (`pack_pin`); here the argument is a runtime input rather than a
            # recorded claim, so it is resolved rather than refused — which
            # also stops an unresolvable value being reported as backdating.
            try:
                mutation_begins_at = gitread._run(
                    repository, "rev-parse", f"{mutation_begins_at}^{{commit}}",
                    timeout=30).strip()
            except Exception:
                found.append(
                    f"the revision where mutation began, {mutation_begins_at!r}, does not "
                    f"resolve in this repository, so the design cannot be shown to precede it")
                return found
            if mutation_begins_at == self.base_revision:
                found.append(
                    "the base revision is the revision at which mutation began, so the design "
                    "was frozen against a tree that already contains the work it governs")
                return found
            try:
                gitread._run(repository, "merge-base", "--is-ancestor", self.base_revision,
                             mutation_begins_at, timeout=30)
            except Exception:
                found.append(
                    f"the base revision {self.base_revision[:12]} is not an ancestor of "
                    f"{mutation_begins_at[:12]}, where mutation began: this design was not "
                    f"frozen before the implementation it claims to govern")
                return found
            found.extend(self._provenance_problems(mutation_begins_at, repository))
        return found

    def _provenance_problems(self, mutation_begins_at: str, repository) -> list:
        """Whether the RECORD ITSELF existed, unchanged, before the work began.

        RP2.4.1 R2. Everything above this establishes ancestry between two
        revisions the record NAMES. None of it asks when the record's own bytes
        came into being — so a design written today, naming a base that predates
        an implementation that already shipped, reported DESIGN FROZEN. An
        independent reader reproduced exactly that, and the information was in
        the repository the whole time, unasked for.

        The claim is checked against the one party to it that cannot be
        backdated by editing a file: the record's content must already be
        present, byte for byte, in the tree at the revision where mutation
        began. That single comparison answers all three ways of getting this
        wrong — a record introduced afterwards, a record edited afterwards, and
        a record never committed at all — and it needs no input the caller was
        not already supplying.
        """
        import gitread

        found: list = []
        try:
            top = Path(gitread._run(repository, "rev-parse", "--show-toplevel",
                                    timeout=30).strip())
            here = Path(self.path).resolve()
            relative = here.relative_to(top.resolve()).as_posix()
        except Exception as exc:
            found.append(
                f"the design record's provenance could not be established: this repository "
                f"could not be asked where {self.path} sits within it ({exc}). A design whose "
                f"history cannot be read has not been shown to precede anything")
            return found
        try:
            committed = gitread._run(repository, "show",
                                     f"{mutation_begins_at}:{relative}", timeout=30)
        except Exception:
            found.append(
                f"{relative} did not exist at {mutation_begins_at[:12]}, where mutation began, "
                f"so this design record's provenance places it AFTER the implementation it "
                f"claims to govern. Ancestry of the revisions it names is not the same claim "
                f"as the record having been written first")
            return found
        try:
            on_disk = here.read_text(encoding="utf-8")
        except OSError as exc:
            found.append(f"the design record could not be read back for comparison: {exc}")
            return found
        if committed != on_disk:
            found.append(
                f"{relative} differs from the version committed at {mutation_begins_at[:12]}, "
                f"where mutation began: its content changed after the work started, so what is "
                f"frozen here is not what the implementation was built against")
        return found


def _rows(block: str) -> list:
    """The data rows of a pipe table, header and rule discarded."""
    rows = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or all(set(cell) <= set("-: ") for cell in cells):
            continue
        rows.append(cells)
    return rows[1:] if rows else rows


def _section(text: str, title: str) -> str:
    match = re.search(rf"^##\s+{re.escape(title)}\s*$(.*?)(?=^##\s|\Z)", text,
                      re.M | re.S | re.I)
    return match.group(1).strip() if match else ""


def read(path) -> DesignRecord:
    """Parse a design record. Never raises: an unreadable one is a reading."""
    where = Path(path)
    record = DesignRecord(path=str(where))
    try:
        text = where.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # A DESIGN RECORD THAT IS NOT TEXT is a reading, not a crash. Bytes
        # that are not UTF-8 arrive here as often as a missing file does — a
        # path pointed at the wrong artifact — and a traceback would report the
        # same situation as a defect in this module.
        record.unreadable = f"the design record could not be read: {type(exc).__name__}: {exc}"
        return record

    def field_of(name: str) -> str:
        match = re.search(rf"^\*\*{re.escape(name)}:\*\*\s*(.+)$", text, re.M | re.I)
        return match.group(1).strip() if match else ""

    record.change_class = field_of("Change class").upper()
    record.base_revision = field_of("Base revision").lower()
    record.frozen = field_of("Frozen").lower() in ("yes", "true")
    record.mechanism = _section(text, "The mechanism")
    record.authority = _section(text, "Authority boundaries")

    for cells in _rows(_section(text, "Designs considered")):
        if len(cells) >= 3:
            record.candidates.append(
                Candidate(name=cells[1], verdict=cells[2].upper(),
                          why=cells[3] if len(cells) > 3 else ""))
    for cells in _rows(_section(text, "Failure modes of the selected design")):
        if len(cells) >= 2 and cells[1]:
            record.failure_modes.append(cells[1])
    for cells in _rows(_section(text, "Oracles, frozen before implementation")):
        if len(cells) >= 2:
            record.oracles.append(
                Oracle(ident=cells[0], kind=cells[1].upper(),
                       property=cells[2] if len(cells) > 2 else "",
                       selector=cells[3] if len(cells) > 3 else ""))
    return record


def _cli(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("record")
    parser.add_argument("--repository", default=None)
    parser.add_argument("--mutation-begins-at", default="")
    args = parser.parse_args(argv)

    record = read(args.record)
    problems = record.problems(mutation_begins_at=args.mutation_begins_at,
                               repository=args.repository)
    print(f"design record: {record.path}")
    print(f"  class:    {record.change_class or 'not declared'}")
    print(f"  frozen at {record.base_revision or 'nothing'}")
    if record.selected:
        print(f"  selected: {record.selected.name}")
    print(f"  {len(record.rejected)} rejected, {len(record.failure_modes)} failure mode(s), "
          f"{len(record.oracles)} oracle(s)")
    for problem in problems:
        print(f"  !! {problem}")
    print("DESIGN FROZEN" if not problems else "DESIGN INCOMPLETE")
    return 0 if not problems else 1


if __name__ == "__main__":
    import sys

    # The module, not a second copy of it — the same reason `capability_open`
    # gives: a file run as a script is `__main__`, and a sibling importing it
    # by name gets separate class objects, so an `isinstance` across that
    # boundary is False for an object that is exactly that class.
    from errors import run_cli
    from design_record import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
