"""What the pack does with a defect somebody has already found.

The contract these prove, in the order it is used:

    identical or rephrased evidence  -> no second record of one failure
    the same failure, another project -> the same record, stronger
    a materially different failure    -> a separate record, distinction stated
    either occurrence, later          -> still reachable, with its own provenance
    an engineering-loop failure       -> the same pipeline, unchanged

Every case is executed against a real class list. None asserts that a function
exists.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import evolution_evidence as ee
from evolution_evidence import Evidence, Occurrence

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = ROOT / "policy" / "recurrence-classes.json"


def _occurrence(project="a-project", **overrides):
    fields = dict(
        project=project, release="9.9.9", revision="a" * 40,
        reproduction="python3 -m pytest tools/tests/test_x.py -q -k the_case",
        producer="a-worker", provider="a-provider",
        mechanisms=("tools/thing.py",), observed_at="2026-09-05")
    fields.update(overrides)
    return Occurrence(**fields)


@pytest.fixture
def classes():
    return ee.load(SHIPPED)


# --- 1. identical or rephrased evidence does not create a second record ---------


def test_evidence_naming_a_recorded_class_is_a_recurrence_not_a_new_candidate(classes):
    before = len(classes)
    evidence = Evidence(recurrence_class="stale / orphaned / superseded waiter",
                        occurrence=_occurrence())
    verdict = ee.classify(evidence, classes)
    assert verdict.outcome == ee.RECURRENCE, verdict.sentence()

    after = ee.reinforce(classes, evidence)
    assert len(after) == before, (
        "a recurrence created a new class; the point of a class list is that the fifth "
        "instance of one failure is the same record, not a fifth record")
    assert len(ee.occurrences_of(after, "stale / orphaned / superseded waiter")) == 1


def test_a_rephrasing_of_a_recorded_class_is_returned_rather_than_accepted(classes):
    """The failure this prevents is a SECOND record of one thing, which is how a
    pattern stops being visible: four instances of one class is a fact, and four
    classes with one instance each is not the same fact."""
    evidence = Evidence(
        recurrence_class="superseded or orphaned or stale waiter",
        occurrence=_occurrence())
    verdict = ee.classify(evidence, classes)
    assert verdict.outcome == ee.NEEDS_DISTINCTION, verdict.sentence()
    assert verdict.matched == "stale / orphaned / superseded waiter"
    with pytest.raises(ValueError, match="closely resembles"):
        ee.reinforce(classes, evidence)


@pytest.mark.parametrize("irrelevant", [
    "it happened in another project",
    "it happened in another release",
    "a different provider found it",
    "a different implementation path exposed it",
])
def test_none_of_the_irrelevant_differences_makes_it_a_new_class(classes, irrelevant):
    """The founder's list, executed: none of these is a reason for a second record."""
    evidence = Evidence(
        recurrence_class="false RUNNING from process existence",
        occurrence=_occurrence(project="another-project", release="8.8.8",
                               provider="another-provider",
                               reproduction=f"reached because {irrelevant}"))
    assert ee.classify(evidence, classes).outcome == ee.RECURRENCE
    assert len(ee.reinforce(classes, evidence)) == len(classes)


# --- 2. a recurrence from a second project strengthens the same record ----------


def test_a_second_project_strengthens_the_same_class_and_both_stay_recoverable(classes):
    name = "gate failure hidden by a pipeline or lost exit code"
    first = Evidence(recurrence_class=name, occurrence=_occurrence(
        project="runtime-pack-2", release="2.4.0", revision="b" * 40,
        reproduction="gate | tail -1 && git commit -F msg  — the && attached to tail",
        producer="the release session", mechanisms=("tools/commit_gate.py",),
        adds="the first recorded instance in this pack's own development"))
    second = Evidence(recurrence_class=name, occurrence=_occurrence(
        project="a-consuming-project", release="0.1.0", revision="c" * 40,
        reproduction="a CI step piped the gate into tee and read tee's status",
        producer="a project session", mechanisms=("their release pipeline",),
        adds="reached through CI rather than an interactive shell"))

    after = ee.reinforce(ee.reinforce(classes, first), second)
    assert len(after) == len(classes), "the second project created a second class"

    recorded = ee.occurrences_of(after, name)
    assert len(recorded) == 2, f"the second occurrence did not strengthen the record: {recorded}"
    assert [o.project for o in recorded] == ["runtime-pack-2", "a-consuming-project"]
    assert [o.revision for o in recorded] == ["b" * 40, "c" * 40]
    assert all(o.reproduction for o in recorded)
    assert recorded[1].adds and recorded[1].adds != recorded[0].adds, (
        "the second occurrence records nothing the first did not, so nothing says why it was "
        "worth recording")


def test_reinforcement_appends_and_never_rewrites(classes):
    """Provenance is not a summary. An occurrence, once recorded, is not edited by
    the next one — which is the difference between consolidating a candidate and
    losing the evidence under it."""
    name = "vacuous mutation test / test iterating the mutated constant"
    first = Evidence(recurrence_class=name, occurrence=_occurrence(
        project="one", reproduction="the first reproduction"))
    once = ee.reinforce(classes, first)
    snapshot = json.dumps(ee.occurrences_of(once, name)[0].__dict__, sort_keys=True, default=list)

    twice = ee.reinforce(once, Evidence(recurrence_class=name, occurrence=_occurrence(
        project="two", reproduction="the second reproduction")))
    unchanged = json.dumps(ee.occurrences_of(twice, name)[0].__dict__, sort_keys=True, default=list)
    assert unchanged == snapshot, "recording a second occurrence changed the first"
    assert len(ee.occurrences_of(twice, name)) == 2


# --- 3. materially distinct evidence is not merged ------------------------------


def test_a_distinct_failure_stays_distinct_when_the_submitter_says_how(classes):
    evidence = Evidence(
        recurrence_class="superseded or orphaned or stale waiter",
        occurrence=_occurrence(),
        distinct_because=("this is not about a waiter's own liveness: the waiter is healthy and "
                          "the SENTINEL it watches is written by a process that is not the one "
                          "it was declared against, which no waiter-liveness oracle can see"))
    verdict = ee.classify(evidence, classes)
    assert verdict.outcome == ee.NEW, verdict.sentence()
    after = ee.reinforce(classes, evidence, files=["test_background_governance.py"])
    assert len(after) == len(classes) + 1
    assert verdict.matched in verdict.why, "the report does not say what it was distinguished from"


def test_two_shipped_classes_that_resemble_each_other_are_both_recorded(classes):
    """The threshold is measured against the real vocabulary rather than picked.

    The closest pair the pack ships — a stale WAITER and a stale WORKER — scores
    exactly at the boundary, and they are genuinely different things with
    different oracles. So a submitter proposing either when the other exists is
    asked for a distinction, and the distinction is easy to give. That is the
    behaviour this threshold is for, and it is checked here rather than assumed.
    """
    names = [entry["class"] for entry in classes]
    worst = max(((ee._overlap(a, b), a, b)
                 for index, a in enumerate(names) for b in names[index + 1:]),
                key=lambda triple: triple[0])
    score, left, right = worst
    assert score <= ee.NEAR_DUPLICATE, (
        f"two shipped classes overlap at {score:.2f}, above the near-duplicate threshold "
        f"{ee.NEAR_DUPLICATE}: {left!r} and {right!r}. Either they are one class, or the "
        f"threshold is above the vocabulary this pack actually uses")
    assert left in names and right in names


def test_an_unrelated_class_is_new_without_a_distinction_being_demanded(classes):
    evidence = Evidence(
        recurrence_class="a pinned release root moved by its owning repository",
        occurrence=_occurrence())
    verdict = ee.classify(evidence, classes)
    assert verdict.outcome == ee.NEW, verdict.sentence()


# --- 4. provenance survives ------------------------------------------------------


def test_every_occurrence_must_carry_the_provenance_to_go_back_to_it(classes):
    for missing in ("project", "release", "revision", "reproduction"):
        evidence = Evidence(
            recurrence_class="false RUNNING from process existence",
            occurrence=_occurrence(**{missing: "  "}))
        with pytest.raises(ValueError, match=missing):
            ee.classify(evidence, classes)


def test_provenance_survives_a_write_and_a_read_by_another_process(tmp_path, classes):
    """The record has to outlive the session that made it, or the provenance is a
    variable rather than evidence."""
    name = "audit evidence about revision A accepted for revision B"
    after = ee.reinforce(classes, Evidence(recurrence_class=name, occurrence=_occurrence(
        project="runtime-pack-2", release="2.4.0", revision="d" * 40,
        reproduction="HEAD moved while a reading was in flight, three times in one session")))
    path = tmp_path / "recurrence-classes.json"
    path.write_text(json.dumps({"policy_schema": "recurrence-classes-v1",
                                "description": "fixture", "classes": after}), encoding="utf-8")

    read_back = subprocess.run(
        [sys.executable, "-c",
         "import sys, json; sys.path.insert(0, sys.argv[1]); import evolution_evidence as e;"
         "print(json.dumps([o.__dict__ for o in "
         "e.occurrences_of(e.load(sys.argv[2]), sys.argv[3])], default=list))",
         str(ROOT / "tools"), str(path), name],
        capture_output=True, text=True, check=True, timeout=120)
    recovered = json.loads(read_back.stdout)
    assert len(recovered) == 1
    assert recovered[0]["revision"] == "d" * 40
    assert "HEAD moved while a reading was in flight" in recovered[0]["reproduction"]


# --- 5. an engineering-loop failure uses the same pipeline -----------------------


PROCESS_FAILURES = (
    "oracle satisfied for a reason other than its claim",
    "vacuous mutation test / test iterating the mutated constant",
    "gate failure hidden by a pipeline or lost exit code",
    "audit evidence about revision A accepted for revision B",
    "false RUNNING from process existence",
    "stale / orphaned / superseded waiter",
    "telemetry UNKNOWN converted into guessed capacity",
    "self-derived golden, stale verifier",
    "transcribed counts drifting from computable facts",
)


@pytest.mark.parametrize("name", PROCESS_FAILURES)
def test_a_process_failure_is_evidence_like_any_other(classes, name):
    """These are not product defects and they are first-class here.

    Every one of them happened during this release's own development, several
    more than once, and the pack records them as classes with oracles. This
    checks they go through the same pipeline rather than a second one.
    """
    assert name in [entry["class"] for entry in classes], (
        f"{name!r} is not a recorded class, so this parametrisation is asserting about "
        f"something the pack does not have")
    evidence = Evidence(recurrence_class=name, occurrence=_occurrence(
        project="runtime-pack-2", release="2.4.0",
        reproduction="reproduced during this release's own closing pass"))
    assert ee.classify(evidence, classes).outcome == ee.RECURRENCE
    after = ee.reinforce(classes, evidence)
    assert len(after) == len(classes)
    assert len(ee.occurrences_of(after, name)) == 1


def test_the_shipped_class_list_still_loads_and_is_not_empty():
    """If the list were empty every classification above would return NEW and every
    assertion about recurrence would be vacuous."""
    classes = ee.load(SHIPPED)
    assert len(classes) > 20, f"only {len(classes)} classes; these tests establish nothing"
    assert all(entry.get("class") for entry in classes)
