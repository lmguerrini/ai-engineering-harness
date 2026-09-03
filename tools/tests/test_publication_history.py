"""A private term in a blob no tree carries, and the hundred near-misses beside it.

Rehearsal A4. The fixture is the measured shape rather than a convenient one: one
genuine hit that only the complete strict scan can see, more than twenty ordinary
English near-misses, and one `.gitignore` entry whose removal would make the
repository **less** safe.

Every entry names what it must be able to fail, and the three MUST-GO-RED cases
are the ones that prove the gap is real rather than asserted.
"""

import subprocess

import pytest

import outgoing_scan
import publication_history
from commit_gate import TermSet
from errors import PreconditionError
from publication_history import Adjudication, OccurrenceClass


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True,
                          check=True).stdout.strip()


NEAR_MISSES = " ".join(
    f"the {word} case" for word in
    ["harness", "envelope", "harnesses", "enveloped", "harness's", "re-harness",
     "envelope-like", "harnessing", "envelopes", "unharnessed", "harness2", "envelope1",
     "wire harness", "manila envelope", "harness racing", "envelope theorem",
     "safety harness", "envelope budget", "harness bell", "envelope glue",
     "harness room", "envelope flap"]
)


@pytest.fixture
def repo(tmp_path):
    """A repository whose private material survives only in history."""
    directory = tmp_path / "repo"
    directory.mkdir()
    _git(directory, "init", "--quiet", "--initial-branch", "main")
    _git(directory, "config", "user.name", "Throwaway Tester")
    _git(directory, "config", "user.email", "tester@example.invalid")
    _git(directory, "config", "commit.gpgsign", "false")

    # Committed, then deleted. The blob stays reachable through history and
    # leaves the working tree, the index and every tip-shaped scan.
    (directory / "notes.md").write_text("internal note: projectcodename ships on Friday\n")
    _git(directory, "add", ".")
    _git(directory, "commit", "--quiet", "-m", "a note that should never have been committed")
    (directory / "notes.md").unlink()
    (directory / "prose.md").write_text(NEAR_MISSES + "\n")
    (directory / ".gitignore").write_text(
        "# never commit these\nprojectcodename-secrets.env\n*.pem\n")
    _git(directory, "add", "-A")
    _git(directory, "commit", "--quiet", "-m", "remove the note and add ordinary prose")
    return directory


def _scanner(strict=True):
    return outgoing_scan.Scanner(TermSet.of(terms=["projectcodename"]), strict=strict)


# --- MUST PASS ---------------------------------------------------------------------


def test_the_complete_strict_scan_finds_the_hit_no_tree_carries(repo):
    report = publication_history.scan_complete_history(repo, _scanner())
    blobs = [o for o in report.occurrences if o.location == "blob"]
    assert any(o.path == "notes.md" for o in blobs), (
        "the deleted note is the whole point of the fixture"
    )
    assert "[strict]" in report.render()
    assert "complete reachable history" in report.render()


# --- MUST GO RED, three ways --------------------------------------------------------


def test_the_staged_scan_on_a_clean_tree_misses_it(repo):
    """Proving the gap is real rather than asserted."""
    report = outgoing_scan.scan_staged(repo, scanner=_scanner())
    assert report.clean or not any("notes.md" in leak.subject for leak in report.leaks)


def test_the_working_tree_no_longer_contains_it_at_all(repo):
    assert not (repo / "notes.md").exists()
    assert "notes.md" not in _git(repo, "ls-files")


def test_the_gate_refuses_a_remediation_list_while_anything_is_unadjudicated(repo):
    report = publication_history.scan_complete_history(repo, _scanner())
    assert report.occurrences
    with pytest.raises(PreconditionError) as caught:
        publication_history.remediation_list(report, {})
    assert "manufactures pressure to rewrite history" in caught.value.render()


def test_a_partially_adjudicated_list_is_refused_too(repo):
    """The raw count wearing a review's clothes."""
    report = publication_history.scan_complete_history(repo, _scanner())
    one = report.occurrences[0]
    partial = {one.key: Adjudication(one.key, OccurrenceClass.GENUINE, "it is the note")}
    if len(report.occurrences) == 1:
        pytest.skip("this fixture produced a single occurrence")
    with pytest.raises(PreconditionError):
        publication_history.remediation_list(report, partial)


def test_an_occurrence_explicitly_marked_undecided_still_blocks(repo):
    """Every occurrence has an entry and one of them says *not yet*. That is a
    different state from an absent entry and must not resolve differently —
    somebody looked at the list, and looking is not deciding."""
    report = publication_history.scan_complete_history(repo, _scanner())
    assert len(report.occurrences) > 1, "the fixture needs more than one occurrence"
    adjudications = {}
    for index, occurrence in enumerate(report.occurrences):
        if index == 0:
            adjudications[occurrence.key] = Adjudication(
                occurrence.key, OccurrenceClass.UNCLASSIFIED, "")
        else:
            adjudications[occurrence.key] = Adjudication(
                occurrence.key, OccurrenceClass.ORDINARY_LANGUAGE, "ordinary sense")

    with pytest.raises(PreconditionError) as caught:
        publication_history.remediation_list(report, adjudications)
    assert "unadjudicated: 1" in caught.value.render()

    assert len(publication_history.unadjudicated(report, adjudications)) == 1


# --- adjudication, per occurrence -----------------------------------------------------


def _adjudicate(report, classify):
    return {
        occurrence.key: Adjudication(occurrence.key, *classify(occurrence))
        for occurrence in report.occurrences
    }


def test_a_fully_adjudicated_list_holds_only_what_a_person_called_genuine(repo):
    report = publication_history.scan_complete_history(repo, _scanner())

    def classify(occurrence):
        if occurrence.path == "notes.md":
            return OccurrenceClass.GENUINE, "an internal note committed by mistake"
        if occurrence.path == ".gitignore":
            return (OccurrenceClass.LEGITIMATE_PUBLIC_BOUNDARY,
                    "this entry is what stops the secret being committed; removing it is worse")
        return OccurrenceClass.ORDINARY_LANGUAGE, "the word in its ordinary sense"

    genuine = publication_history.remediation_list(report, _adjudicate(report, classify))
    assert [o.path for o in genuine] == ["notes.md"]


def test_the_gitignore_entry_is_not_in_the_remediation_list(repo):
    """The negative control. Blindly remediating would delete the line that
    keeps the secret out of the repository."""
    report = publication_history.scan_complete_history(repo, _scanner())
    ignore_hits = [o for o in report.occurrences if o.path == ".gitignore"]
    if not ignore_hits:
        pytest.skip("the fixture's ignore entry did not match the declared vocabulary")

    adjudications = _adjudicate(
        report,
        lambda o: (OccurrenceClass.LEGITIMATE_PUBLIC_BOUNDARY, "removing it makes things worse")
        if o.path == ".gitignore" else (OccurrenceClass.ORDINARY_LANGUAGE, "ordinary sense"),
    )
    assert publication_history.remediation_list(report, adjudications) == []


def test_the_same_finding_is_judged_once_per_occurrence_and_the_split_is_visible(repo):
    """A word private in one file is ordinary English in the next, which is the
    common case. Keying by the occurrence triple makes a per-term verdict
    unexpressible; `by_finding` makes the split legible."""
    report = publication_history.scan_complete_history(repo, _scanner())
    if len({o.path for o in report.occurrences}) < 2:
        pytest.skip("the fixture produced occurrences in only one file")

    adjudications = _adjudicate(
        report,
        lambda o: (OccurrenceClass.GENUINE, "the note") if o.path == "notes.md"
        else (OccurrenceClass.ORDINARY_LANGUAGE, "ordinary sense"),
    )
    split = publication_history.by_finding(report, adjudications)
    mixed = [finding for finding, counts in split.items() if len(counts) > 1]
    assert mixed, "the fixture must produce one finding judged two different ways"


def test_an_unadjudicated_list_can_be_worked_through(repo):
    report = publication_history.scan_complete_history(repo, _scanner())
    assert len(publication_history.unadjudicated(report, {})) == len(report.occurrences)


def test_a_classification_without_a_reason_is_refused():
    """A count without reasons is not a remediation list, which is the whole
    reason this stage exists."""
    with pytest.raises(PreconditionError):
        Adjudication(("f", "s", "p"), OccurrenceClass.GENUINE, "   ")


def test_an_unknown_classification_is_refused_by_name():
    with pytest.raises(Exception) as caught:
        Adjudication(("f", "s", "p"), "probably fine", "because")
    assert "GENUINE" in str(caught.value) or "GENUINE" in getattr(caught.value, "render", str)()


# --- what the scan says about itself ------------------------------------------------


def test_a_repository_with_no_refs_examines_nothing_rather_than_reporting_clean(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    _git(empty, "init", "--quiet")
    report = publication_history.scan_complete_history(empty, _scanner())
    assert report.examined.nothing
    assert "NOTHING EXAMINED" in report.render()


def test_the_report_says_it_is_not_a_remediation_list(repo):
    report = publication_history.scan_complete_history(repo, _scanner())
    assert "NOT a remediation list" in report.render()
    assert "rows 2 and 4" in report.render()


def test_this_module_removes_nothing(repo):
    """Core produces a classified list a human acts on. A module that could
    remediate would hold the permission D23 clause 6 withholds."""
    names = set(dir(publication_history))
    for forbidden in ("remediate", "rewrite", "purge", "redact_history", "filter_repo",
                      "amend", "delete_blob"):
        assert forbidden not in names, f"publication_history gained {forbidden!r}"


def test_the_cli_separates_findings_from_nothing_examined(repo, tmp_path, capsys):
    assert publication_history._cli([str(repo), "--term", "projectcodename"]) == 1
    assert "to adjudicate" in capsys.readouterr().out

    assert publication_history._cli([str(repo), "--term", "absent-from-this-tree"]) == 0
    assert "clean" in capsys.readouterr().out

    empty = tmp_path / "bare"
    empty.mkdir()
    _git(empty, "init", "--quiet")
    assert publication_history._cli([str(empty), "--term", "projectcodename"]) == 2


# --- which obligations a project actually carries -------------------------------
#
# D23 clause 3. Core carries universal public-safety invariants; reproducibility
# and presentation are profile-scoped. An internal project is not walked through
# publication ceremony because the pack is capable of performing it.


class _Contract:
    def __init__(self, intent=None):
        self.publication_intent = intent


def test_an_internal_project_carries_the_safety_half_and_not_the_presentation_half():
    applicable, not_applicable, why = publication_history.obligations(_Contract("internal"))
    assert set(applicable) == set(publication_history.UNIVERSAL_OBLIGATIONS)
    assert set(not_applicable) == set(publication_history.PUBLICATION_OBLIGATIONS)
    assert "access controls change" in why


def test_a_public_project_carries_both_halves():
    applicable, not_applicable, _why = publication_history.obligations(_Contract("public"))
    assert not not_applicable
    assert set(publication_history.PUBLICATION_OBLIGATIONS) <= set(applicable)


def test_an_undeclared_intent_cannot_switch_off_the_safety_half():
    """The direction that matters. Silence must not be able to remove an
    invariant about content; it may only decline a presentation requirement."""
    applicable, not_applicable, why = publication_history.obligations(_Contract(None))
    assert set(publication_history.UNIVERSAL_OBLIGATIONS) <= set(applicable)
    assert set(not_applicable) == set(publication_history.PUBLICATION_OBLIGATIONS)
    assert "must not be able to switch off" in why


def test_the_complete_history_scan_is_a_universal_obligation_not_a_publication_one():
    """Decision A's exact line: Core may carry universal public-safety
    invariants; reproducibility and presentation are opt-in."""
    universal = " ".join(publication_history.UNIVERSAL_OBLIGATIONS)
    assert "complete reachable history" in universal and "strict" in universal
    assert "row 2" in universal, "the human authorisation is part of the invariant, not beside it"
    presentation = " ".join(publication_history.PUBLICATION_OBLIGATIONS)
    assert "reproducible" in presentation and "explains itself" in presentation


def test_an_intent_nothing_recognises_is_refused(tmp_path):
    from project_contract import ContractError, ProjectContract

    contract = tmp_path / "PROJECT.yaml"
    contract.write_text("project:\n  repo_path: .\npublication:\n  intent: probably-fine\n")
    with pytest.raises(ContractError) as caught:
        ProjectContract.load(contract)
    assert "internal" in str(caught.value) and "public" in str(caught.value)


def test_a_profile_declares_the_environment_it_is_reproducible_by(tmp_path):
    from project_contract import ProjectContract

    contract = tmp_path / "PROJECT.yaml"
    contract.write_text(
        "project:\n  repo_path: .\n"
        "publication:\n  intent: public\n"
        "validation_profiles:\n"
        "  focused:\n    command: pytest -q\n    reproducible_by: developer_machine\n"
        "  full:\n    command: pytest\n    reproducible_by: public_clone\n"
    )
    loaded = ProjectContract.load(contract)
    assert loaded.publication_intent == "public"
    assert dict(loaded.reproducible_by) == {"focused": "developer_machine", "full": "public_clone"}


def test_a_profile_that_declares_no_environment_is_silent_rather_than_guessed(tmp_path):
    from project_contract import ProjectContract

    contract = tmp_path / "PROJECT.yaml"
    contract.write_text(
        "project:\n  repo_path: .\nvalidation_profiles:\n  focused:\n    command: pytest -q\n")
    assert ProjectContract.load(contract).reproducible_by == ()


def test_an_environment_that_is_not_a_name_is_refused(tmp_path):
    from project_contract import ContractError, ProjectContract

    contract = tmp_path / "PROJECT.yaml"
    contract.write_text(
        "project:\n  repo_path: .\nvalidation_profiles:\n  focused:\n    reproducible_by: \"  \"\n")
    with pytest.raises(ContractError):
        ProjectContract.load(contract)


# --- a scan with a hole in it ---------------------------------------------------------


def test_an_object_too_large_to_read_means_the_history_was_not_scanned(repo):
    """The finding, from a blind cross-vendor reader: a six-megabyte blob whose
    first line held a private term reported `clean` and exited `0`, while
    printing `NOT SCANNED` two lines below.

    The skip was recorded honestly and then not counted, which is the difference
    between disclosing a gap and closing one. The word in this module's name is
    *complete*."""
    big = repo / "large.txt"
    big.write_text("needleprivate\n" + "z" * (outgoing_scan.MAX_SCANNED_BLOB_BYTES + 1024))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "a blob nobody can read")

    report = publication_history.scan_complete_history(
        repo, outgoing_scan.Scanner(TermSet(terms=("needleprivate",))))
    assert report.skipped
    assert not report.complete
    assert "INCOMPLETE" in report.render()


def test_two_paths_sharing_a_blob_are_both_examined(repo):
    """`rev-list --objects` names an object once, so the second path was never
    examined — not deduplicated after the fact, never looked at. Names come from
    the trees now, deduplicated by the pair."""
    (repo / "a.txt").write_text("needleprivate\n")
    (repo / "z-needleprivate.txt").write_text("needleprivate\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "one blob, two names")

    report = publication_history.scan_complete_history(
        repo, outgoing_scan.Scanner(TermSet(terms=("needleprivate",))))
    locations = sorted((o.location, o.path) for o in report.occurrences)
    assert ("path", "z-needleprivate.txt") in locations
    assert ("blob", "a.txt") in locations
