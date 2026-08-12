"""gitread against a throwaway repository built fresh in a tmp dir.

No mocking: every function under test shells out to a real `git`, so the
throwaway repo is the fixture.
"""

import subprocess

import pytest

import gitread
from errors import GitRefusal


def _git(repo, *args, env=None):
    command = ["git", *args]
    result = subprocess.run(
        command, cwd=str(repo), capture_output=True, text=True, check=True, env=env,
    )
    return result.stdout


@pytest.fixture
def repo(tmp_path):
    directory = tmp_path / "throwaway"
    directory.mkdir()
    _git(directory, "init", "--quiet", "--initial-branch", "main")
    _git(directory, "config", "user.name", "Throwaway Tester")
    _git(directory, "config", "user.email", "tester@example.invalid")
    _git(directory, "config", "commit.gpgsign", "false")
    (directory / "file.txt").write_text("hello world\n")
    _git(directory, "add", "file.txt")
    _git(directory, "commit", "--quiet", "-m", "first commit")
    return directory


def test_probe_answers_a_real_question(repo):
    answer = gitread.probe(repo, "rev-parse", "--verify", "HEAD")
    assert answer.answered
    assert answer.ok
    assert len(answer.value) == 40


def test_probe_distinguishes_cannot_ask_from_no(repo, tmp_path):
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    answer = gitread.probe(not_a_repo, "rev-parse", "--verify", "HEAD")
    # Git ran, found no repository, and exited non-zero for an undeclared
    # status: this must be a failure, not a silent negative.
    assert answer.answered
    assert answer.failed


def test_commit_message_round_trips(repo):
    head = _git(repo, "rev-parse", "HEAD").strip()
    message = gitread.commit_message(repo, head)
    assert message == "first commit\n"


def test_commit_metadata_has_full_identity(repo):
    head = _git(repo, "rev-parse", "HEAD").strip()
    metadata = gitread.commit_metadata(repo, head)
    assert metadata["author_name"] == "Throwaway Tester"
    assert metadata["author_email"] == "tester@example.invalid"
    assert metadata["committer_name"] == "Throwaway Tester"


def test_whitespace_damage_is_empty_when_clean(repo):
    assert gitread.whitespace_damage(repo) == ""


def test_whitespace_damage_detects_trailing_whitespace(repo):
    (repo / "file.txt").write_text("hello world   \n")
    _git(repo, "add", "file.txt")
    damage = gitread.whitespace_damage(repo)
    assert damage != ""
    assert "file.txt" in damage


def test_object_type_and_size(repo):
    head = _git(repo, "rev-parse", "HEAD").strip()
    assert gitread.object_type(repo, head) == "commit"
    tree = _git(repo, "rev-parse", f"{head}^{{tree}}").strip()
    assert gitread.object_type(repo, tree) == "tree"
    blob = _git(repo, "rev-parse", f"{head}:file.txt").strip()
    assert gitread.object_type(repo, blob) == "blob"
    assert gitread.object_size(repo, blob) == len("hello world\n")


def test_object_bytes_matches_file_content(repo):
    head = _git(repo, "rev-parse", "HEAD").strip()
    blob = _git(repo, "rev-parse", f"{head}:file.txt").strip()
    assert gitread.object_bytes(repo, blob) == b"hello world\n"


def test_objects_and_paths_in_outgoing_range(repo):
    first = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "second.txt").write_text("more\n")
    _git(repo, "add", "second.txt")
    _git(repo, "commit", "--quiet", "-m", "second commit")
    second = _git(repo, "rev-parse", "HEAD").strip()

    objects = gitread.objects_in_outgoing_range(repo, second, first)
    shas = {sha for sha, _path in objects}
    assert second in shas

    paths = gitread.paths_in_outgoing_range(repo, second, first)
    assert paths == ["second.txt"]


def test_paths_in_outgoing_range_with_no_baseline_lists_everything(repo):
    paths = gitread.paths_in_outgoing_range(repo, "HEAD", None)
    assert paths == ["file.txt"]


def test_tag_object_carries_its_own_message_and_tagger(repo):
    env = {**__import__("os").environ, "GIT_COMMITTER_NAME": "Throwaway Tester", "GIT_COMMITTER_EMAIL": "tester@example.invalid"}
    _git(repo, "tag", "-a", "v1", "-m", "release notes", env=env)
    tag_sha = _git(repo, "rev-parse", "v1").strip()
    tag = gitread.tag_object(repo, tag_sha)
    assert tag["message"] == "release notes\n"
    assert tag["tag"] == "v1"
    assert "Throwaway Tester" in tag["tagger"]


def test_run_refuses_a_nonexistent_repository_path(tmp_path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(GitRefusal):
        gitread._run(missing, "rev-parse", "--verify", "HEAD")


def test_run_refuses_a_nonpositive_timeout(repo):
    with pytest.raises(GitRefusal):
        gitread._run(repo, "rev-parse", "--verify", "HEAD", timeout=0)
