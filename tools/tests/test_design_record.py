"""A design, frozen before the implementation it governs.

The oracles here are the ones the design record for this capability froze
before any of it was written — `rp2.3-session/DESIGN-C31-design-gate.md`, O1
through O16. Each negative one fails when its guard is removed; the mutation
pass at the bottom of this file demonstrates that rather than asserting it.
"""

import subprocess
from pathlib import Path

import pytest

import capability_open
import design_record


def _git(where, *args):
    subprocess.run(["git", "-C", str(where), *args], check=True, capture_output=True, timeout=120)


@pytest.fixture
def repo(tmp_path):
    where = tmp_path / "project"
    where.mkdir()
    _git(where, "init", "--quiet", "--initial-branch", "main")
    for key, value in (("user.name", "T"), ("user.email", "t@e.invalid"),
                       ("commit.gpgsign", "false")):
        _git(where, "config", key, value)
    (where / "seed.txt").write_text("seed")
    _git(where, "add", "-A")
    _git(where, "commit", "-qm", "seed")
    return where


def _head(where) -> str:
    return subprocess.run(["git", "-C", str(where), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True, timeout=60).stdout.strip()


COMPLETE = """# DESIGN — C1

**Change class:** {change_class}
**Base revision:** {base}
**Frozen:** {frozen}

## The mechanism

{mechanism}

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
{candidates}

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
{modes}

## Authority boundaries

{authority}

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
{oracles}
"""

_CANDIDATES = ("| 1 | do it the loud way | REJECTED | it needs a daemon |\n"
               "| 2 | do it by composition | SELECTED | the path already exists |")
_MODES = "| 1 | ceremony creep | the class scales it |"
_ORACLES = ("| O1 | ACCEPTANCE | a complete record verifies | test_a_complete |\n"
            "| O2 | NEGATIVE | an incomplete one is refused | test_refused |\n"
            "| O3 | MUTATION | the guard breaks the test | mutants |")


def _write(where, **over):
    body = COMPLETE.format(**{
        "change_class": "MATERIAL", "base": _head(where), "frozen": "yes",
        "mechanism": "the coordinator can mutate before deciding, and nothing records it",
        "candidates": _CANDIDATES, "modes": _MODES,
        "authority": "reports only; weakens no HITL row", "oracles": _ORACLES, **over})
    path = Path(where) / "DESIGN-C1.md"
    path.write_text(body, encoding="utf-8")
    return path


# --- O1, O11, O12: what a complete record of each class is ----------------------------


def test_a_complete_material_design_verifies(repo):
    """O1."""
    record = design_record.read(_write(repo))
    assert record.problems(repository=repo) == []
    assert record.selected.name == "do it by composition"
    assert len(record.rejected) == 1
    assert [o.kind for o in record.oracles] == ["ACCEPTANCE", "NEGATIVE", "MUTATION"]


def test_a_trivial_change_needs_no_record_at_all(repo):
    """O11. A rule that demands a design document for a typo is a rule that
    gets routed around, and one that gets routed around is worse than none."""
    assert design_record.required_for(design_record.TRIVIAL) is False
    assert design_record.required_for(design_record.ROUTINE) is True
    assert design_record.required_for(design_record.MATERIAL) is True

    record = design_record.read(_write(repo, change_class="TRIVIAL", candidates="", modes="",
                                       oracles="", authority="", mechanism="", frozen="no"))
    assert record.problems(repository=repo) == [], "a trivial change was asked for ceremony"


def test_a_routine_change_needs_oracles_and_not_alternatives(repo):
    """O12. Routine work inside an existing design is not a design decision;
    it still may not be judged by a test that does not exist yet."""
    record = design_record.read(_write(repo, change_class="ROUTINE", candidates="", modes="",
                                       authority=""))
    assert record.problems(repository=repo) == []

    without = design_record.read(_write(repo, change_class="ROUTINE", candidates="", modes="",
                                        authority="", oracles=""))
    problems = without.problems(repository=repo)
    assert any("ACCEPTANCE oracle" in p for p in problems), problems
    assert any("NEGATIVE oracle" in p for p in problems), problems


# --- O3 to O8: what a material record may not leave out -------------------------------


@pytest.mark.parametrize("over, expected", [
    ({"candidates": "| 1 | the only idea | SELECTED | it was first |"}, "at least two"),
    ({"candidates": "| 1 | a | SELECTED | x |\n| 2 | b | SELECTED | y |"}, "exactly one"),
    ({"candidates": _CANDIDATES.replace("REJECTED", "SELECTED")}, "rejected"),
    ({"modes": ""}, "failure mode"),
    ({"authority": ""}, "authority boundary"),
    ({"oracles": "| O1 | ACCEPTANCE | a | t |\n| O2 | NEGATIVE | b | t |"}, "mutation oracle"),
    ({"frozen": "no"}, "frozen"),
    ({"mechanism": ""}, "mechanism"),
])
def test_a_material_design_missing_a_part_is_refused(repo, over, expected):
    """O3 to O6. Each of these is a way of writing a design that looks like one."""
    problems = design_record.read(_write(repo, **over)).problems(repository=repo)
    assert any(expected in p for p in problems), (expected, problems)


def test_a_base_revision_that_resolves_to_nothing_is_refused(repo):
    """O7. A design frozen against an invented revision is frozen against
    nothing, and reads exactly like one that is not."""
    problems = design_record.read(_write(repo, base="0" * 40)).problems(repository=repo)
    assert any("does not resolve" in p for p in problems), problems

    problems = design_record.read(_write(repo, base="not-a-revision")).problems(repository=repo)
    assert any("forty-character revision" in p for p in problems), problems


def test_a_base_revision_outside_this_history_is_refused(repo, tmp_path):
    """O7. Resolving somewhere is not the same as being where this work began."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _git(elsewhere, "init", "--quiet", "--initial-branch", "main")
    for key, value in (("user.name", "T"), ("user.email", "t@e.invalid"),
                       ("commit.gpgsign", "false")):
        _git(elsewhere, "config", key, value)
    (elsewhere / "other.txt").write_text("other")
    _git(elsewhere, "add", "-A")
    _git(elsewhere, "commit", "-qm", "other")
    _git(repo, "remote", "add", "other", str(elsewhere))
    _git(repo, "fetch", "-q", "other")

    stranger = subprocess.run(["git", "-C", str(elsewhere), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    problems = design_record.read(_write(repo, base=stranger)).problems(repository=repo)
    assert any("not an ancestor of" in p and "HEAD" in p for p in problems), problems


def test_a_design_frozen_after_the_work_it_governs_is_refused(repo):
    """O8. Backdating is the obvious cheat and the only one worth building for:
    write the code, then write the design, then date it earlier."""
    (repo / "already.txt").write_text("the work")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "the work this design claims to govern")
    after = _head(repo)

    same = design_record.read(_write(repo, base=after))
    problems = same.problems(mutation_begins_at=after, repository=repo)
    assert any("already contains the work" in p for p in problems), problems

    later = design_record.read(_write(repo, base=after))
    _git(repo, "commit", "-q", "--allow-empty", "-m", "later")
    problems = later.problems(mutation_begins_at=_head(repo), repository=repo)
    assert problems == [] or all("already contains" not in p for p in problems)


def test_an_unreadable_record_is_a_reading_and_never_a_pass(repo):
    """O10, and D15: an unanswerable question is never its reassuring answer."""
    record = design_record.read(repo / "there-is-no-such-file.md")
    assert record.unreadable
    assert record.problems(repository=repo), "a record nobody could read reported no problems"


def test_an_unrecognised_change_class_refuses_rather_than_choosing_the_lenient_one(repo):
    problems = design_record.read(_write(repo, change_class="SMALL")).problems(repository=repo)
    assert any("change class" in p for p in problems), problems


# --- O2, O9, O10 at the lifecycle transition ------------------------------------------


PACK = Path(__file__).resolve().parents[2]

CONTRACT = """project:
  name: "designed"
  publication_intent: "internal"
pack:
  root_path: "%s"
  version_adopted: "2.3.0"
  state_adopted: "IN_PROGRESS"
  adopted_at: "2026-09-04"
  adoption_boundary: "at a capability boundary"
capabilities:
  - id: "C1"
adapters: []
%s"""


def _contract(where, requires=""):
    path = Path(where) / "PROJECT.yaml"
    path.write_text(CONTRACT % (PACK, requires), encoding="utf-8")
    return path


def test_the_readiness_path_reports_a_frozen_design_at_the_open(repo):
    """O2. The transition is *before a governed capability opens*, which is the
    one deterministic readiness path this pack already runs there."""
    _write(repo)
    report = capability_open.open_capability(_contract(repo), capability="C1",
                                             change_class="MATERIAL")
    design = report.component("design")
    assert design is not None, "the readiness path does not ask about the design at all"
    assert design.state == capability_open.VERIFIED, design.findings
    assert design.satisfied
    assert design not in report.blocking
    assert any("selected: do it by composition" in note for note in design.notes), design.notes


def test_a_material_change_with_no_design_is_not_authorised_to_implement(repo):
    """O9. The whole property, at the transition: implementation is not
    authorised, and the reason is named rather than being an empty report."""
    report = capability_open.open_capability(_contract(repo), capability="C1",
                                             change_class="MATERIAL")
    design = report.component("design")
    assert design.state == capability_open.NOT_PRESENT
    assert design.required and design.blocking and not design.satisfied
    assert design in report.blocking
    assert not report.ready
    assert any("not authorised" in f for f in design.findings), design.findings


def test_a_trivial_change_opens_without_a_design_and_says_that_is_a_declaration(repo):
    """O11 at the transition. And the note matters: a reader must be able to
    see that the answer rests on the caller's own claim about the change."""
    report = capability_open.open_capability(_contract(repo), capability="C1",
                                             change_class="TRIVIAL")
    design = report.component("design")
    assert design.state == capability_open.NOT_REQUIRED
    assert design.satisfied and not design.blocking
    assert any("TRIVIAL" in note for note in design.notes), design.notes


def test_a_declared_design_that_is_not_there_blocks_whether_or_not_required(repo):
    """O10, and D22: a requirement governs ABSENCE. Something in this project
    points at that file, and being unable to read it is not made safe by
    nobody having written `required: true`."""
    report = capability_open.open_capability(_contract(repo), capability="C1",
                                             change_class="TRIVIAL",
                                             design=str(repo / "gone.md"))
    design = report.component("design")
    assert design.state == capability_open.UNVERIFIABLE
    assert design.blocking and not design.satisfied


def test_a_project_can_require_a_design_without_declaring_a_class(repo):
    """The requirement is a property of the project, exactly as
    `requires.project_context` is. Core cannot know which capabilities are
    material and does not decide."""
    report = capability_open.open_capability(_contract(repo, "requires:\n  design: true\n"),
                                             capability="C1")
    design = report.component("design")
    assert design.state == capability_open.NOT_PRESENT
    assert design.required and not design.satisfied

    _write(repo)
    report = capability_open.open_capability(_contract(repo, "requires:\n  design: true\n"),
                                             capability="C1")
    assert report.component("design").state == capability_open.VERIFIED


def test_an_incomplete_design_blocks_and_names_every_thing_it_does_not_state(repo):
    _write(repo, candidates="| 1 | the only idea | SELECTED | it was first |", modes="")
    report = capability_open.open_capability(_contract(repo), capability="C1",
                                             change_class="MATERIAL")
    design = report.component("design")
    assert design.state == capability_open.UNVERIFIABLE
    assert not design.satisfied
    assert any("at least two" in f for f in design.findings), design.findings
    assert any("failure mode" in f for f in design.findings), design.findings


def test_the_design_of_this_capability_is_itself_a_frozen_design(repo):
    """The mechanism, used on itself. If this file's own design record does not
    satisfy the rule it introduced, the rule is one nobody has ever met."""
    # IN THE PACK, not beside it. It lived in the session directory, so the
    # documents cited a file no consumer receives and this test skipped
    # everywhere except the one checkout that happened to sit next to it — a
    # test that silently does not run, cited as the evidence that it did.
    own = PACK / "docs" / "RP2.3-DESIGN-C31-design-gate.md"
    assert own.is_file(), "the release cites its own design record and does not ship it"
    record = design_record.read(own)
    assert record.change_class == design_record.MATERIAL
    assert record.problems(repository=PACK) == []
    assert len(record.rejected) >= 3, "the alternatives were not really considered"
    assert record.of_kind(design_record.MUTATION)
    assert record.of_kind(design_record.REHEARSAL)


# --- what an independent reader got past the first version -----------------------------


def test_a_material_record_that_states_nothing_is_refused(repo):
    """B1. An independent reader wrote a MATERIAL record whose every cell was
    empty — two unnamed designs, a rejection with no reason, a failure mode with
    no mitigation, three oracles settling nothing — and it verified, and the
    readiness report said less about it than about a complete one.

    The documents had said the rule all along: *a rejected design with no
    reason is not a rejection; it is a list.* Nothing checked it.
    """
    hollow = design_record.read(_write(
        repo,
        candidates="| 1 |  | REJECTED |  |\n| 2 |  | SELECTED |  |",
        modes="| 1 | . |  |",
        oracles=("| O1 | ACCEPTANCE |  |  |\n| O2 | NEGATIVE |  |  |\n"
                 "| O3 | MUTATION |  |  |")))
    problems = hollow.problems(repository=repo)
    assert any("unnamed" in p for p in problems), problems
    assert any("it is a list" in p for p in problems), problems
    assert any("state no property" in p for p in problems), problems

    #: and each is refused on its own, not only all together
    named = design_record.read(_write(
        repo, candidates="| 1 | lock it all | REJECTED |  |\n| 2 | version it | SELECTED | x |"))
    assert any("it is a list" in p for p in named.problems(repository=repo))
    reasoned = design_record.read(_write(
        repo, oracles="| O1 | ACCEPTANCE |  | t |\n| O2 | NEGATIVE | b | t |\n"
                      "| O3 | MUTATION | c | t |"))
    assert any("state no property" in p for p in reasoned.problems(repository=repo))


def test_a_design_note_a_project_never_asked_for_does_not_stop_it(repo):
    """B2. `DESIGN.md` is one of the commonest filenames there is. A project
    with an architecture note beside its contract has not opted into this
    mechanism, and every existing consumer that has one would otherwise have
    lost readiness the moment it adopted this release."""
    (repo / "DESIGN.md").write_text("# Design\n\nSome notes about the architecture.\n",
                                    encoding="utf-8")
    report = capability_open.open_capability(_contract(repo), capability="C1")
    design = report.component("design")
    assert design.state == capability_open.UNVERIFIABLE, "the note should still be reported"
    assert not design.required
    assert not design.blocking, "a note nobody declared stopped the open"
    assert design.satisfied
    assert design not in report.blocking
    assert any("not declared" in note for note in design.notes), design.notes

    #: but the moment the project asks for one, the same file stops it
    asked = capability_open.open_capability(_contract(repo, "requires:\n  design: true\n"),
                                            capability="C1")
    assert asked.component("design").blocking
    #: and so does a class that requires one
    classed = capability_open.open_capability(_contract(repo), capability="C1",
                                              change_class="MATERIAL")
    assert classed.component("design").blocking


def test_the_report_says_as_much_about_an_empty_record_as_a_full_one(repo):
    """The summary used to hang on the selected design having a name, so the
    emptier the record the less the report said about it."""
    _write(repo, candidates="| 1 |  | REJECTED |  |\n| 2 |  | SELECTED |  |")
    report = capability_open.open_capability(_contract(repo), capability="C1",
                                             change_class="MATERIAL")
    notes = " ".join(report.component("design").notes)
    assert "selected:" in notes and "design(s) considered" in notes and "rejected" in notes


def test_a_design_frozen_on_a_branch_that_never_led_to_the_work_is_refused(repo):
    """T6. Every test of the freeze binding exercised `base == mutation_begins_at`
    and none exercised the strict-ancestor property the packet, the changelog,
    D25 and the skill all state. The implementation was right; nothing held it
    there, and deleting the comparison left the suite green."""
    _git(repo, "checkout", "-q", "-b", "sideline")
    (repo / "aside.txt").write_text("aside")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "a commit on a branch the work never came from")
    sideline = _head(repo)
    _git(repo, "checkout", "-q", "main")
    (repo / "work.txt").write_text("work")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "where the work began")
    began = _head(repo)
    _git(repo, "merge", "-q", "--no-ff", "-m", "bring the sideline in", "sideline")

    record = design_record.read(_write(repo, base=sideline))
    #: the base resolves and IS an ancestor of HEAD after the merge
    assert not any("does not resolve" in p for p in record.problems(repository=repo))
    assert not any("ancestor of HEAD" in p for p in record.problems(repository=repo))
    #: and is still not where the work started from
    problems = record.problems(mutation_begins_at=began, repository=repo)
    assert any("not frozen before the implementation" in p for p in problems), problems


def test_declaring_a_change_trivial_cannot_bypass_a_project_that_requires_a_design(repo):
    """T7. A project that declares `requires.design: true` has said the question
    is unconditional. A caller answering `TRIVIAL` must not be able to retract
    that on the project's behalf — the honest bound is a project that never
    declared one, not one that did."""
    report = capability_open.open_capability(_contract(repo, "requires:\n  design: true\n"),
                                             capability="C1", change_class="TRIVIAL")
    design = report.component("design")
    assert design.state == capability_open.NOT_PRESENT
    assert design.required and design.blocking and not design.satisfied


def test_the_revision_where_mutation_began_is_resolved_before_it_is_compared(repo):
    """**The freeze binding held in exactly one spelling.**

    `mutation_begins_at == self.base_revision` was a string comparison, and the
    `--is-ancestor` fallback beside it is reflexive. So the same commit written
    as an abbreviation or as a ref name was *not equal* to the base, the
    ancestor check said yes, and a design frozen against the very commit where
    mutation began reported FROZEN — the backdating case the binding exists to
    refuse, failing silently in the unsafe direction. An independent reader
    found it, and the template this release ships prints
    `--mutation-begins-at <the first commit>` with no `git rev-parse` around it.
    """
    (repo / "work.txt").write_text("the work")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "where the work began")
    began = _head(repo)
    short = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short=12", "HEAD"],
                           capture_output=True, text=True, check=True).stdout.strip()
    _git(repo, "branch", "began", began)
    _git(repo, "tag", "began-tag", began)
    record = design_record.read(_write(repo, base=began))

    #: every spelling of one commit is that commit
    for spelling in (began, short, "began", "began-tag", "HEAD"):
        problems = record.problems(mutation_begins_at=spelling, repository=repo)
        assert any("already contains the work" in p for p in problems), (
            f"{spelling!r} names the commit the design was frozen against and the "
            f"binding did not notice: {problems}")

    #: and a value that names no commit is that, not backdating
    problems = record.problems(mutation_begins_at="zzz-no-such-revision", repository=repo)
    assert any("does not resolve" in p for p in problems), problems
    assert not any("already contains the work" in p for p in problems), (
        "an unresolvable revision was reported as backdating")


def test_a_design_frozen_before_the_work_still_passes_in_every_spelling(repo):
    """The other direction, so the repair above cannot be a blanket refusal.

    The design is committed BEFORE the work commit, which is the sequence the
    gate exists to require. It used to be written afterwards and left
    uncommitted, and passed anyway — which is the RP2.4.1 R2 defect standing
    inside the test written to show the gate was not a blanket refusal.
    """
    base = _head(repo)
    _write(repo, base=base)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "freeze the design")
    (repo / "work.txt").write_text("the work")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "where the work began")
    began = _head(repo)
    short = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short=12", "HEAD"],
                           capture_output=True, text=True, check=True).stdout.strip()
    _git(repo, "branch", "began2", began)
    record = design_record.read(Path(repo) / "DESIGN-C1.md")
    for spelling in (began, short, "began2", "HEAD"):
        assert record.problems(mutation_begins_at=spelling, repository=repo) == [], (
            f"a design frozen before the work was refused when the work was named {spelling!r}")


# --- RP2.4.1 R1/R2: required strength, and provenance of the record itself ----

def _commit(where, message="work"):
    _git(where, "add", "-A")
    _git(where, "commit", "-qm", message)
    return _head(where)


def test_a_weaker_record_does_not_satisfy_a_stronger_requirement(repo):
    """O1/O10. The reproduced R1 scenario, at the boundary that owns it.

    A record that declares itself TRIVIAL states nothing, by design. 2.4.0 let
    that nothing satisfy a requirement its own caller had declared MATERIAL,
    and reported VERIFIED rather than NOT_REQUIRED — an affirmative claim that
    the design gate had been met.
    """
    record = design_record.read(_write(repo, change_class="TRIVIAL", candidates="", modes="",
                                       oracles="", authority="", mechanism="", frozen="no"))
    problems = record.problems(repository=repo, required_class=design_record.MATERIAL)
    assert problems, "a TRIVIAL record satisfied a MATERIAL requirement"
    assert any("MATERIAL" in problem and "TRIVIAL" in problem for problem in problems), problems


def test_a_routine_record_does_not_satisfy_a_material_requirement(repo):
    """The rank is a rank, not a two-value flag."""
    record = design_record.read(_write(repo, change_class="ROUTINE", candidates="", modes=""))
    assert record.problems(repository=repo, required_class=design_record.MATERIAL)


def test_a_material_record_satisfies_a_material_requirement(repo):
    """O2. The repair must not refuse the case it exists to protect."""
    record = design_record.read(_write(repo))
    assert record.problems(repository=repo, required_class=design_record.MATERIAL) == []


def test_a_stronger_record_satisfies_a_weaker_requirement(repo):
    """Over-documenting is not an error."""
    record = design_record.read(_write(repo))
    assert record.problems(repository=repo, required_class=design_record.ROUTINE) == []


def test_trivial_work_requiring_nothing_stays_lightweight(repo):
    """O3. The scaling rule survives: ceremony nobody needs is ceremony nobody performs."""
    record = design_record.read(_write(repo, change_class="TRIVIAL", candidates="", modes="",
                                       oracles="", authority="", mechanism="", frozen="no"))
    assert record.problems(repository=repo) == []
    assert record.problems(repository=repo, required_class=design_record.TRIVIAL) == []


def test_an_unknown_required_class_is_refused_rather_than_ranked(repo):
    """Failure mode 5. A spelling nobody recognises must not rank as TRIVIAL."""
    record = design_record.read(_write(repo))
    problems = record.problems(repository=repo, required_class="material")
    assert problems and any("required" in p.lower() for p in problems), problems


def test_a_record_committed_before_mutation_is_accepted(repo):
    """O6. The ordinary, correct sequence: freeze, then build."""
    base = _head(repo)
    _write(repo, base=base)
    _commit(repo, "freeze the design")
    (repo / "impl.py").write_text("print('work')\n")
    mutation = _commit(repo, "implementation")
    record = design_record.read(Path(repo) / "DESIGN-C1.md")
    assert record.problems(repository=repo, mutation_begins_at=mutation) == []


def test_a_record_committed_after_mutation_is_refused(repo):
    """O4. The reproduced R2 scenario.

    Ancestry between two claimed revisions was all 2.4.0 established, so a
    record written today, naming a base that predates the work, reported
    DESIGN FROZEN. Git holds the answer and was never asked.
    """
    base = _head(repo)
    (repo / "impl.py").write_text("print('work')\n")
    mutation = _commit(repo, "implementation lands first")
    _write(repo, base=base)
    _commit(repo, "design written after the fact")
    record = design_record.read(Path(repo) / "DESIGN-C1.md")
    problems = record.problems(repository=repo, mutation_begins_at=mutation)
    assert problems, "a design written after the implementation reported frozen"
    assert any("did not exist" in p or "provenance" in p.lower() for p in problems), problems


def test_a_record_edited_after_mutation_is_refused(repo):
    """O5. Backdating by editing the file it names."""
    base = _head(repo)
    path = _write(repo, base=base)
    _commit(repo, "freeze the design")
    (repo / "impl.py").write_text("print('work')\n")
    mutation = _commit(repo, "implementation")
    path.write_text(path.read_text() + "\nAn oracle thought of afterwards.\n")
    record = design_record.read(path)
    problems = record.problems(repository=repo, mutation_begins_at=mutation)
    assert problems, "a record edited after the work reported frozen"
    assert any("changed" in p or "differs" in p for p in problems), problems


def test_an_uncommitted_record_cannot_establish_provenance(repo):
    """Failure mode 1. Never established by default; refused with a reason."""
    base = _head(repo)
    (repo / "impl.py").write_text("print('work')\n")
    mutation = _commit(repo, "implementation")
    _write(repo, base=base)
    record = design_record.read(Path(repo) / "DESIGN-C1.md")
    assert record.problems(repository=repo, mutation_begins_at=mutation)


def test_provenance_that_cannot_be_read_is_refused(repo, tmp_path):
    """O7. Failure mode 3: outside a checkout, provenance is not established."""
    base = _head(repo)
    path = _write(repo, base=base)
    _commit(repo, "freeze")
    (repo / "impl.py").write_text("x\n")
    mutation = _commit(repo, "implementation")
    elsewhere = tmp_path / "not-a-repo"
    elsewhere.mkdir()
    (elsewhere / "DESIGN-C1.md").write_text(path.read_text(), encoding="utf-8")
    record = design_record.read(elsewhere / "DESIGN-C1.md")
    assert record.problems(repository=elsewhere, mutation_begins_at=mutation)


def test_every_spelling_of_the_mutation_revision_agrees(repo):
    """O8. One answer, however the caller spells the revision."""
    base = _head(repo)
    (repo / "impl.py").write_text("print('work')\n")
    mutation = _commit(repo, "implementation lands first")
    _write(repo, base=base)
    _commit(repo, "design after the fact")
    record = design_record.read(Path(repo) / "DESIGN-C1.md")
    for spelling in (mutation, mutation[:7], mutation[:12], "HEAD~1", "HEAD~1^{commit}"):
        assert record.problems(repository=repo, mutation_begins_at=spelling), spelling
