"""The release-delta check, against deltas built here rather than against this one.

`test_release_integrity.py` runs this tool over the real release. That answers
whether THIS entry is complete; it does not answer whether the tool can say no.
Two mutants proved it could not be assumed: one made the tool report every
addition as named and one made it find no additions, and the release guard passed
against both because it asked the tool whether the tool was satisfied.

So this module builds small repositories with known deltas and known entries, and
checks the answers in both directions.
"""

import subprocess
import sys
from pathlib import Path

import pytest

import release_delta


def _repository(tmp_path, *, baseline_files, added_files, decisions_before=(), decisions_after=()):
    """A repository with one commit before the release and one after it."""
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args],
                                capture_output=True, text=True, timeout=120)
        assert not result.returncode, f"git {args}: {result.stderr}"
        return result

    git("init", "-q", "--initial-branch", "main")
    git("config", "user.name", "Ordinary Human")
    git("config", "user.email", "human@example.invalid")
    git("config", "commit.gpgsign", "false")

    def write(path, body):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")

    for path in baseline_files:
        write(path, "before\n")
    write("DECISIONS.md", "# Decisions\n\n" + "".join(
        f"## {d} — something\n\nbody\n\n" for d in decisions_before))
    git("add", "-A")
    git("commit", "-q", "-m", "the previous release")
    baseline = git("rev-parse", "HEAD").stdout.strip()

    for path in added_files:
        write(path, "after\n")
    write("DECISIONS.md", "# Decisions\n\n" + "".join(
        f"## {d} — something\n\nbody\n\n" for d in (*decisions_before, *decisions_after)))
    git("add", "-A")
    git("commit", "-q", "-m", "this release")
    return root, baseline


def test_an_entry_naming_every_addition_is_complete(tmp_path):
    root, baseline = _repository(
        tmp_path, baseline_files=["VERSION"],
        added_files=["tools/new_thing.py", "policy/new-rule.md"],
        decisions_after=["D9"])
    changelog = (
        "# Changelog\n\n## 9.9.9 — this release\n\n"
        "Added `tools/new_thing.py` and `policy/new-rule.md`, and recorded D9.\n\n"
        "## 9.9.8 — the one before\n\nolder\n")
    report = release_delta.coverage(root, version="9.9.9", baseline=baseline,
                                    changelog=changelog)
    assert report.complete, report.render()
    assert len(report.named) == 3


@pytest.mark.parametrize("dropped", ["tools/new_thing.py", "policy/new-rule.md", "D9"])
def test_an_entry_missing_one_addition_is_incomplete_and_names_it(tmp_path, dropped):
    root, baseline = _repository(
        tmp_path, baseline_files=["VERSION"],
        added_files=["tools/new_thing.py", "policy/new-rule.md"],
        decisions_after=["D9"])
    full = ("# Changelog\n\n## 9.9.9 — this release\n\n"
            "Added `tools/new_thing.py` and `policy/new-rule.md`, and recorded D9.\n")
    changelog = full.replace(Path(dropped).name if "/" in dropped else dropped, "something")
    report = release_delta.coverage(root, version="9.9.9", baseline=baseline,
                                    changelog=changelog)
    assert not report.complete, f"dropping {dropped} left the delta reported as complete"
    assert any(dropped in delta.path or delta.token in dropped for delta in report.omitted), (
        f"{dropped} was dropped and the report names {[d.path for d in report.omitted]}")
    assert dropped.split("/")[-1] in report.render() or dropped in report.render()


def test_a_version_with_no_entry_is_refused_rather_than_reported_complete(tmp_path):
    root, baseline = _repository(tmp_path, baseline_files=["VERSION"],
                                 added_files=["tools/new_thing.py"])
    with pytest.raises(ValueError, match="no `## 9.9.9` entry"):
        release_delta.coverage(root, version="9.9.9", baseline=baseline,
                               changelog="# Changelog\n\n## 9.9.8 — older\n\nbody\n")


def test_an_empty_entry_is_refused_rather_than_reported_complete(tmp_path):
    """A heading with nothing under it is the obvious way to satisfy a check that
    only looks for the heading."""
    root, baseline = _repository(tmp_path, baseline_files=["VERSION"],
                                 added_files=["tools/new_thing.py"])
    with pytest.raises(ValueError, match="is empty"):
        release_delta.coverage(root, version="9.9.9", baseline=baseline,
                               changelog="# Changelog\n\n## 9.9.9 — this release\n\n\n"
                                         "## 9.9.8 — older\n\nbody\n")


def test_the_entry_read_is_this_versions_and_not_a_later_ones(tmp_path):
    """A neighbouring entry naming the file must not satisfy this version's."""
    root, baseline = _repository(tmp_path, baseline_files=["VERSION"],
                                 added_files=["tools/new_thing.py"])
    changelog = ("# Changelog\n\n"
                 "## 9.9.9 — this release\n\nsomething happened\n\n"
                 "## 9.9.8 — older\n\nAdded `tools/new_thing.py`\n")
    report = release_delta.coverage(root, version="9.9.9", baseline=baseline,
                                    changelog=changelog)
    assert not report.complete, (
        "an addition named only in a DIFFERENT version's entry satisfied this one")


def test_additions_are_read_from_the_repository_and_not_from_the_entry(tmp_path):
    """The population under test comes from the range. If it came from the prose,
    an entry that named nothing would have nothing to be incomplete about."""
    root, baseline = _repository(
        tmp_path, baseline_files=["VERSION"],
        added_files=["tools/a.py", "tools/b.py", "docs/c.md"], decisions_after=["D9", "D10"])
    found = release_delta.additions(root, baseline=baseline)
    assert {delta.token for delta in found} == {"a.py", "b.py", "c.md", "D9", "D10"}
    assert {delta.category for delta in found} >= {
        "a tool a consuming project runs", "a release record or design record",
        "a pack-level decision"}


def test_a_file_the_release_removed_is_not_demanded(tmp_path):
    """Requiring an entry to name every DELETED file would fire on tidying, and a
    deletion is not something a reader can look up afterwards. Stated in the
    module and pinned here so it is a decision rather than an omission."""
    root, baseline = _repository(tmp_path, baseline_files=["VERSION", "tools/gone.py"],
                                 added_files=["tools/new_thing.py"])
    subprocess.run(["git", "-C", str(root), "rm", "-q", "tools/gone.py"], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=x", "-c", "user.email=x@y",
                    "commit", "-q", "-m", "remove"], check=True, capture_output=True)
    report = release_delta.coverage(
        root, version="9.9.9", baseline=baseline,
        changelog="# Changelog\n\n## 9.9.9 — this\n\nAdded `tools/new_thing.py`\n")
    assert report.complete, report.render()


def test_the_cli_answers_and_exits_non_zero_on_an_incomplete_delta(tmp_path):
    root, baseline = _repository(tmp_path, baseline_files=["VERSION"],
                                 added_files=["tools/new_thing.py"])
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 9.9.9 — this release\n\nnothing named here\n", encoding="utf-8")
    (root / "PACK_MANIFEST.json").write_text('{"version": "9.9.9"}', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(Path(release_delta.__file__)), str(root), "--baseline", baseline],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 1, result.stdout
    assert "DELTA INCOMPLETE" in result.stdout
    assert "new_thing.py" in result.stdout


def test_a_test_module_named_in_the_entry_does_not_cover_the_module_it_tests(tmp_path):
    """THROUGH `coverage`, not through the helper. A first oracle for this checked
    `_names` directly, so a mutant reverting the CALL SITE to substring
    membership left the helper correct and unused, and survived.

    The real case: `tools/evolution_evidence.py` counted as named because
    `evolution_evidence.py` occurs inside `test_evolution_evidence.py`, which the
    entry did name.
    """
    root, baseline = _repository(
        tmp_path, baseline_files=["VERSION"],
        added_files=["tools/evolution_evidence.py", "tools/tests/test_evolution_evidence.py"])
    changelog = ("# Changelog\n\n## 9.9.9 — this release\n\n"
                 "Added `tools/tests/test_evolution_evidence.py`.\n")
    report = release_delta.coverage(root, version="9.9.9", baseline=baseline,
                                    changelog=changelog)
    assert not report.complete, (
        "naming the test module covered the module it tests; substring membership is not naming")
    assert [delta.path for delta in report.omitted] == ["tools/evolution_evidence.py"], (
        [delta.path for delta in report.omitted])


def test_a_longer_decision_identifier_does_not_cover_a_shorter_one(tmp_path):
    root, baseline = _repository(tmp_path, baseline_files=["VERSION"],
                                 added_files=["tools/a.py"], decisions_after=["D9", "D90"])
    changelog = ("# Changelog\n\n## 9.9.9 — this release\n\n"
                 "Added `tools/a.py` and recorded D90.\n")
    report = release_delta.coverage(root, version="9.9.9", baseline=baseline,
                                    changelog=changelog)
    assert not report.complete, "D90 covered an omitted D9"
    assert [delta.token for delta in report.omitted] == ["D9"], (
        [delta.token for delta in report.omitted])
