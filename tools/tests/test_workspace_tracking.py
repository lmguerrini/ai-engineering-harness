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


# --- EC-A(i): the classifier has to see the real path -----------------------
#
# `git ls-files` without `-z` C-quotes any path it cannot print literally, so
# `annotations/café.txt` arrived at classification as the literal
# `"annotations/caf\303\251.txt"` — which matches no declared pattern, and the
# project's `annotations/` exemption then silently stopped covering it.
# Reproduced against frozen 2.1.1.


QUOTED_PATHS = [
    "annotations/plain.txt",         # printed literally
    "annotations/with space.txt",    # printed literally: the control
    "annotations/café.txt",          # non-ASCII: quoted
    'annotations/say"hi.txt',        # a quote: quoted
]


@pytest.fixture
def repo_with_awkward_paths(tmp_path):
    root = tmp_path / "awkward"
    (root / "annotations").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
    for key, value in (("user.email", "a@b.c"), ("user.name", "T"),
                       ("core.excludesFile", "/dev/null")):
        subprocess.run(["git", "config", key, value], cwd=root, check=True)
    for path in QUOTED_PATHS:
        (root / path).write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=root, check=True)
    return root


def test_paths_git_quotes_arrive_unquoted(repo_with_awkward_paths):
    report = classify_workspace(repo_with_awkward_paths)
    seen = set(report.tracked_product)
    assert seen == set(QUOTED_PATHS), sorted(seen)
    assert not any(path.startswith('"') for path in seen)


def test_a_declared_directory_exemption_covers_every_one_of_them(tmp_path):
    """The consequence, stated as the property that actually matters: a
    declaration means the same thing regardless of how git chose to print it.

    Asserted on the *untracked* bucket, which is where `ignored_private`
    classifies. An unclassified artifact blocks closure, so a quoted path
    escaping its declared exemption turns a declared directory into a pile of
    blockers — or, with the exemption written the other way, hides them.
    """
    root = tmp_path / "untracked"
    (root / "annotations").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
    for key, value in (("user.email", "a@b.c"), ("user.name", "T"),
                       ("core.excludesFile", "/dev/null")):
        subprocess.run(["git", "config", key, value], cwd=root, check=True)
    (root / "seed.txt").write_text("x")
    subprocess.run(["git", "add", "seed.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=root, check=True)
    for path in QUOTED_PATHS:
        (root / path).write_text("x")

    report = classify_workspace(root, ignored_private=["annotations/"])
    assert sorted(report.ignored_private) == sorted(QUOTED_PATHS)
    assert report.unknown == [], (
        f"a declared exemption stopped covering the paths git quotes: {report.unknown}"
    )
