"""Certification: the ways a candidate must not be able to certify itself.

Each test is an attempt to obtain `CERTIFIED` from records that do not support
it — a non-zero status called a pass, a truncated run called clean, a waiver
borrowed from another tree, a cited report that is not the bytes it claims, a
directory holding evidence the index never mentions.
"""

import pytest

import evidence_put
from evidence_index import (
    CERTIFICATION_VERIFICATION,
    CERTIFIED,
    COMPLETE,
    DISCOVERY,
    MISSING,
    OPEN,
    PARTIAL,
    REOPENED,
    CandidateIdentity,
    Certification,
    CheckerResult,
    EvidenceEntry,
    EvidenceError,
    Waiver,
    index_bijection,
    verify_reference,
)

CANDIDATE = CandidateIdentity(base_sha="a" * 40, head_sha="b" * 40, tree_digest="c" * 64)
OTHER = CandidateIdentity(base_sha="a" * 40, head_sha="d" * 40, tree_digest="e" * 64)


def _passing(name="suite"):
    return CheckerResult(checker=name, command="python3 -m pytest -q", exit_status=0)


# --- a raw result is never rewritten -------------------------------------------


def test_passed_is_derived_from_the_exit_status_and_cannot_be_set():
    """There is nowhere to write PASS over a non-zero status."""
    import dataclasses

    result = CheckerResult(checker="suite", command="c", exit_status=1)
    assert result.passed is False
    # Two independent reasons it cannot be overwritten: the record is frozen,
    # and `passed` is a property with no setter rather than a stored field.
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.passed = True
    assert "passed" not in {f.name for f in dataclasses.fields(CheckerResult)}


def test_a_non_zero_status_cannot_produce_a_certified_candidate():
    certification = Certification(candidate=CANDIDATE, results=(
        CheckerResult(checker="suite", command="c", exit_status=1),
    ))
    assert certification.state() == OPEN
    assert "exited 1" in certification.render()


def test_an_exit_status_of_two_is_a_failure_not_a_different_kind_of_pass():
    """The toolbelt's own gates exit 2 for a contract refusal, which is a
    refusal."""
    certification = Certification(candidate=CANDIDATE, results=(
        CheckerResult(checker="commit_gate", command="c", exit_status=2),
    ))
    assert certification.state() == OPEN


def test_a_boolean_is_not_an_exit_status():
    with pytest.raises(EvidenceError):
        CheckerResult(checker="suite", command="c", exit_status=True)


# --- completeness is three-valued ------------------------------------------------


def test_a_truncated_run_is_neither_a_pass_nor_a_fail():
    result = CheckerResult(checker="audit", command="c", exit_status=0, completeness=PARTIAL)
    assert result.passed is False
    assert "not a verdict" in result.describe()


def test_a_partial_result_blocks_certification_and_says_it_consumes_no_cycle():
    certification = Certification(candidate=CANDIDATE, results=(
        CheckerResult(checker="audit", command="c", exit_status=0, completeness=PARTIAL),
    ))
    assert certification.state() == OPEN
    assert "does not consume an audit cycle" in certification.render()


def test_a_missing_result_blocks_certification():
    certification = Certification(candidate=CANDIDATE, results=(
        CheckerResult(checker="audit", command="c", exit_status=0, completeness=MISSING),
    ))
    assert certification.state() == OPEN
    assert "expected to run and did not" in certification.render()


def test_a_missing_result_cannot_cite_a_report():
    with pytest.raises(EvidenceError):
        CheckerResult(checker="a", command="c", exit_status=0,
                      completeness=MISSING, report_reference="sha256-" + "a" * 64 + "-r.txt")


def test_an_unknown_completeness_is_refused():
    with pytest.raises(EvidenceError):
        CheckerResult(checker="a", command="c", exit_status=0, completeness="PROBABLY_FINE")


# --- bound to an exact candidate ---------------------------------------------------


def test_an_abbreviated_identity_is_refused():
    """An identity that cannot discriminate between two candidates has failed at
    its only job."""
    with pytest.raises(EvidenceError):
        CandidateIdentity(base_sha="abc1234", head_sha="b" * 40, tree_digest="c" * 64)
    with pytest.raises(EvidenceError):
        CandidateIdentity(base_sha="a" * 40, head_sha="b" * 40, tree_digest="tooshort")


def test_a_waiver_applies_only_to_the_candidate_it_was_granted_against():
    waiver = Waiver(finding_id="F1", reason="accepted", authority="a person", bound_to=OTHER)
    certification = Certification(
        candidate=CANDIDATE, results=(_passing(),), open_findings=("F1",), waivers=(waiver,)
    )
    assert certification.state() == OPEN
    assert certification.unwaived_findings() == ("F1",)
    assert "does not apply here" in certification.render()


def test_a_waiver_bound_to_this_candidate_clears_its_finding():
    waiver = Waiver(finding_id="F1", reason="accepted", authority="a person", bound_to=CANDIDATE)
    certification = Certification(
        candidate=CANDIDATE, results=(_passing(),), open_findings=("F1",), waivers=(waiver,)
    )
    assert certification.state() == CERTIFIED
    assert certification.unwaived_findings() == ()


def test_a_waiver_must_name_its_authority():
    with pytest.raises(EvidenceError):
        Waiver(finding_id="F1", reason="fine", authority="", bound_to=CANDIDATE)


# --- discovery is not certification-verification ------------------------------------


def test_a_discovery_run_cannot_certify():
    certification = Certification(
        candidate=CANDIDATE, kind=DISCOVERY, results=(_passing(),)
    )
    assert certification.state() == OPEN
    assert "did not confirm the candidate" in certification.render()


def test_a_certification_verification_run_with_everything_green_certifies():
    certification = Certification(
        candidate=CANDIDATE, kind=CERTIFICATION_VERIFICATION, results=(_passing(),)
    )
    assert certification.state() == CERTIFIED
    assert certification.problems() == []


def test_a_certification_with_no_results_is_not_certified():
    """Nothing ran, so nothing was established."""
    assert Certification(candidate=CANDIDATE).state() == OPEN


# --- reopening is explicit -----------------------------------------------------------


def test_a_new_finding_after_certification_reopens_visibly():
    certification = Certification(
        candidate=CANDIDATE, results=(_passing(),), reopened_by=("F9",)
    )
    assert certification.state() == REOPENED
    assert "certification does not stand" in certification.render()


# --- byte-exact ingestion --------------------------------------------------------------


@pytest.fixture
def evidence(tmp_path):
    directory = tmp_path / "evidence"
    source = tmp_path / "report.txt"
    source.write_text("the checker's actual output\n")
    reference = evidence_put.put(directory, source)
    return directory, reference


def test_a_cited_report_that_matches_verifies(evidence):
    directory, reference = evidence
    assert verify_reference(directory, reference) == []


def test_a_cited_report_that_is_absent_is_reported(evidence):
    directory, reference = evidence
    (directory / reference).unlink()
    assert "absent from the evidence directory" in verify_reference(directory, reference)[0]


def test_a_cited_report_whose_bytes_changed_is_not_the_report_that_was_cited(evidence):
    """A summary of a report is not the report, and neither is an edited one."""
    directory, reference = evidence
    (directory / reference).chmod(0o600)
    (directory / reference).write_text("a tidier version of what it said\n")
    assert "not the report that was cited" in verify_reference(directory, reference)[0]


def test_a_malformed_reference_is_refused():
    assert verify_reference("/nowhere", "report.txt")


def test_an_index_entry_must_be_content_addressed():
    with pytest.raises(EvidenceError):
        EvidenceEntry(reference="report.txt", description="the report")


# --- the bijection ---------------------------------------------------------------------


def test_a_complete_index_and_directory_are_a_bijection(evidence):
    directory, reference = evidence
    entries = [EvidenceEntry(reference=reference, description="the report")]
    assert index_bijection(directory, entries) == ([], [])


def test_an_entry_with_no_file_is_a_citation_of_nothing(evidence):
    directory, reference = evidence
    (directory / reference).unlink()
    dangling, unaccounted = index_bijection(directory, [EvidenceEntry(reference, "the report")])
    assert dangling == [reference]
    assert unaccounted == []


def test_a_file_with_no_entry_is_evidence_nobody_is_accounting_for(evidence):
    """The direction that usually goes unchecked, and the more interesting one:
    material sitting in the evidence directory that no index mentions."""
    directory, reference = evidence
    dangling, unaccounted = index_bijection(directory, [])
    assert dangling == []
    assert unaccounted == [reference]


def test_both_directions_block_certification(evidence, tmp_path):
    directory, reference = evidence
    stray = tmp_path / "stray.txt"
    stray.write_text("an unaccounted artifact\n")
    stray_reference = evidence_put.put(directory, stray)

    certification = Certification(
        candidate=CANDIDATE, results=(_passing(),),
        entries=(EvidenceEntry(reference, "the report"),),
    )
    problems = certification.problems(directory)
    assert any(stray_reference in problem and "in no index entry" in problem for problem in problems)


def test_an_empty_directory_and_an_empty_index_are_a_bijection(tmp_path):
    assert index_bijection(tmp_path / "absent", []) == ([], [])


# --- retention --------------------------------------------------------------------------


def test_retention_is_declared_per_entry(evidence):
    directory, reference = evidence
    assert EvidenceEntry(reference, "d", retention="PERMANENT").retention == "PERMANENT"
    assert EvidenceEntry(reference, "d", retention="TRANSIENT").retention == "TRANSIENT"


def test_an_unknown_retention_class_is_refused(evidence):
    _directory, reference = evidence
    with pytest.raises(EvidenceError):
        EvidenceEntry(reference, "d", retention="probably keep")


# --- the whole reading ---------------------------------------------------------------------


def test_a_fully_supported_certification_states_what_it_checked(evidence):
    directory, reference = evidence
    certification = Certification(
        candidate=CANDIDATE,
        results=(CheckerResult("suite", "python3 -m pytest -q", 0, COMPLETE, reference),),
        entries=(EvidenceEntry(reference, "the suite output", retention="RELEASE"),),
    )
    assert certification.problems(directory) == []
    assert certification.state() == CERTIFIED
    assert "every waiver is bound to this candidate" in certification.render(directory)
