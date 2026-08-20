"""workspace_report: four buckets, and the unknown one that blocks."""

import subprocess

import pytest

import workspace_report


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)


@pytest.fixture
def repo(tmp_path):
    directory = tmp_path / "throwaway"
    directory.mkdir()
    _git(directory, "init", "--quiet", "--initial-branch", "main")
    _git(directory, "config", "user.name", "Throwaway Tester")
    _git(directory, "config", "user.email", "tester@example.invalid")
    _git(directory, "config", "commit.gpgsign", "false")
    (directory / "tracked.txt").write_text("committed content\n")
    _git(directory, "add", "tracked.txt")
    _git(directory, "commit", "--quiet", "-m", "first commit")
    return directory


def test_tracked_committed_file_is_tracked_product(repo):
    report = workspace_report.classify_workspace(repo)
    assert "tracked.txt" in report.tracked_product
    assert report.clean


def test_unclassified_untracked_file_is_unknown_and_blocks(repo):
    (repo / "mystery.tmp").write_text("nobody said anything about this\n")
    report = workspace_report.classify_workspace(repo)
    assert "mystery.tmp" in report.unknown
    assert report.clean is False
    assert "unclassified: mystery.tmp" in report.render()


def test_untracked_file_matching_ignored_private_pattern_is_ignored_private(repo):
    (repo / "secret.local").write_text("private scratch data\n")
    report = workspace_report.classify_workspace(repo, ignored_private=("*.local",))
    assert "secret.local" in report.ignored_private
    assert "secret.local" not in report.unknown
    assert report.clean


def test_untracked_file_matching_safe_generated_pattern_is_safe_generated(repo):
    (repo / "build.out").write_text("regeneratable\n")
    report = workspace_report.classify_workspace(repo, safe_generated=("*.out",))
    assert "build.out" in report.safe_generated
    assert "build.out" not in report.unknown
    assert report.clean


def test_staged_but_uncommitted_file_is_not_tracked_product(repo):
    (repo / "staged.txt").write_text("about to be committed\n")
    _git(repo, "add", "staged.txt")
    report = workspace_report.classify_workspace(repo)
    # Pending, undeclared, so it is unknown rather than silently treated as
    # already-committed tracked product.
    assert "staged.txt" in report.unknown
    assert "staged.txt" not in report.tracked_product
    assert report.clean is False


def test_whitespace_damage_blocks_even_with_no_unknown_files(repo):
    (repo / "tracked.txt").write_text("committed content   \n")
    _git(repo, "add", "tracked.txt")
    report = workspace_report.classify_workspace(repo)
    assert report.unknown == []
    assert report.whitespace_damage != ""
    assert report.clean is False


def test_report_never_deletes_or_mutates_the_workspace(repo):
    (repo / "mystery.tmp").write_text("still here after reporting\n")
    workspace_report.classify_workspace(repo)
    assert (repo / "mystery.tmp").exists()
    assert (repo / "mystery.tmp").read_text() == "still here after reporting\n"


# --- D15: an undeclared exit status is not the documented negative -------------
#
# `_ignore_rule` was the third call site D15 names, and the only one no test
# pinned — an independent audit mutated the `failed` branch away and the whole
# suite still passed. Exit 1 means "not ignored"; anything else means git ran
# and could not answer, and returning the negative's sentence for it states, as
# a fact, that no ignore rule covers the path.


def test_an_unanswerable_ignore_question_is_unknown_not_no_rule(tmp_path):
    import subprocess

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)

    # A path that escapes the repository: git exits 128, not 1.
    answer = workspace_report._ignore_rule(str(root), "../escapes")
    assert answer.startswith("unknown")
    assert "no ignore rule" not in answer


def test_an_ordinary_not_ignored_path_still_says_so(tmp_path):
    import subprocess

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
    subprocess.run(["git", "config", "core.excludesFile", "/dev/null"], cwd=root, check=True)
    (root / ".git" / "info" / "exclude").write_text("")

    assert "no ignore rule" in workspace_report._ignore_rule(str(root), "ordinary.txt")
