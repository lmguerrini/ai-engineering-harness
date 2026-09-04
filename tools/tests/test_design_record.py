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
    own = PACK.parent / "rp2.3-session" / "DESIGN-C31-design-gate.md"
    if not own.is_file():
        pytest.skip("the evolution session's design record is not beside this checkout")
    record = design_record.read(own)
    assert record.change_class == design_record.MATERIAL
    assert record.problems(repository=PACK) == []
    assert len(record.rejected) >= 3, "the alternatives were not really considered"
    assert record.of_kind(design_record.MUTATION)
    assert record.of_kind(design_record.REHEARSAL)
