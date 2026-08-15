"""EC-J: a path the project requires to be tracked, which silently is not.

The motivating case is worth stating because it was a near miss, not a failure.
This machine's global gitignore excludes `*.jsonl`. The project's required files were JSONL in a tracked directory. `git add` would have committed
nothing, silently, and every gate would still have reported green. It was found
by accident, when an unrelated throwaway repository refused to commit a sample
file.

The classification buckets cannot catch this. They answer "has somebody said
what this file is", and a file that never arrived is not unclassified — it is
absent, and absence is what a bucket check structurally cannot see.

This host still carries that ignore rule, so the first test below exercises the
real condition rather than a simulation of it.
"""

import subprocess

import pytest

from workspace_report import classify_workspace


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    directory = tmp_path / "project"
    directory.mkdir()
    _git(directory, "init", "--quiet", "--initial-branch", "main")
    _git(directory, "config", "user.name", "Ordinary Human")
    _git(directory, "config", "user.email", "human@example.invalid")
    _git(directory, "config", "commit.gpgsign", "false")
    (directory / "readme.md").write_text("a project\n")
    _git(directory, "add", "readme.md")
    _git(directory, "commit", "--quiet", "-m", "first")
    return directory


def _ignore_jsonl(repo):
    """Reproduce the machine-level condition inside the fixture repository."""
    (repo / ".gitignore").write_text("*.jsonl\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "--quiet", "-m", "add ignore rules")


def test_a_required_path_excluded_by_an_ignore_rule_fails_the_report(repo):
    """EC-J's criterion, with the offending rule named."""
    _ignore_jsonl(repo)
    (repo / "annotations").mkdir()
    (repo / "annotations" / "gold.jsonl").write_text('{"id": 1}\n')
    _git(repo, "add", "annotations/gold.jsonl")  # succeeds at nothing, silently

    report = classify_workspace(
        repo,
        safe_generated=[".gitignore"],
        must_be_tracked=["annotations/"],
    )
    assert not report.clean
    assert [item.path for item in report.untracked_requirements] == ["annotations/gold.jsonl"]
    rule = report.untracked_requirements[0].rule
    assert ".gitignore" in rule and "*.jsonl" in rule, rule


def test_the_report_is_clean_once_the_required_path_is_actually_tracked(repo):
    """The positive half: the check must pass when the artifact is really there."""
    _ignore_jsonl(repo)
    (repo / "annotations").mkdir()
    (repo / "annotations" / "gold.jsonl").write_text('{"id": 1}\n')
    _git(repo, "add", "-f", "annotations/gold.jsonl")
    _git(repo, "commit", "--quiet", "-m", "add the gold subset")

    report = classify_workspace(repo, must_be_tracked=["annotations/"])
    assert report.untracked_requirements == []


def test_a_declaration_naming_work_not_yet_done_does_not_fail(repo):
    """A required path that does not exist yet is not a defect.

    The check runs at capability open as well as close. Failing on a directory
    the capability is about to create would make it unusable at the one point
    where it is cheapest to act on.
    """
    report = classify_workspace(repo, must_be_tracked=["annotations/"])
    assert report.untracked_requirements == []
    assert report.clean


def test_an_untracked_required_file_with_no_ignore_rule_still_fails(repo):
    """Never added is as absent as excluded, and the report must not blame a rule."""
    (repo / "data").mkdir()
    (repo / "data" / "gold.csv").write_text("a,b\n")

    report = classify_workspace(repo, safe_generated=["data/"], must_be_tracked=["data/gold.csv"])
    assert [item.path for item in report.untracked_requirements] == ["data/gold.csv"]
    assert "never added to the index" in report.untracked_requirements[0].rule


def test_a_tracked_but_unstaged_required_path_is_not_reported(repo):
    """Already committed is tracked. The check is about presence, not staging."""
    (repo / "data").mkdir()
    (repo / "data" / "gold.csv").write_text("a,b\n")
    _git(repo, "add", "data/gold.csv")
    _git(repo, "commit", "--quiet", "-m", "add gold")
    report = classify_workspace(repo, must_be_tracked=["data/"])
    assert report.untracked_requirements == []
