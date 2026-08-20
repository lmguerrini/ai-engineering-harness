"""D4: the commit contract accepts two to four bullets, not exactly three."""

import subprocess
import sys
from pathlib import Path

import pytest

import commit_gate

TOOLS_DIR = Path(__file__).resolve().parent.parent


def _message(*bullets: str, title: str = "Fix the widget") -> str:
    body = "\n".join(f"- {bullet}" for bullet in bullets)
    return f"{title}\n\n{body}\n"


def test_two_bullets_accepted():
    violations = commit_gate.validate_message(_message("first outcome", "second outcome"), commit_gate.NO_PRIVATE_TERMS)
    assert violations == []


def test_three_bullets_accepted():
    violations = commit_gate.validate_message(
        _message("first outcome", "second outcome", "third outcome"), commit_gate.NO_PRIVATE_TERMS
    )
    assert violations == []


def test_four_bullets_accepted():
    violations = commit_gate.validate_message(
        _message("one", "two", "three", "four"), commit_gate.NO_PRIVATE_TERMS
    )
    assert violations == []


def test_one_bullet_rejected():
    violations = commit_gate.validate_message(_message("only outcome"), commit_gate.NO_PRIVATE_TERMS)
    rules = {v.rule for v in violations}
    assert "BULLET_COUNT" in rules


def test_five_bullets_rejected():
    violations = commit_gate.validate_message(
        _message("one", "two", "three", "four", "five"), commit_gate.NO_PRIVATE_TERMS
    )
    rules = {v.rule for v in violations}
    assert "BULLET_COUNT" in rules


def test_credential_pattern_caught():
    message = _message("added a client using sk-ant-abcdefghijklmnopqrstuvwx0123456789", "cleaned up tests")
    violations = commit_gate.validate_message(message, commit_gate.NO_PRIVATE_TERMS)
    rules = {v.rule for v in violations}
    assert "CREDENTIAL" in rules


def test_local_path_caught():
    message = _message("fixed a bug in /Users/alice/project/loader.py", "added a test")
    violations = commit_gate.validate_message(message, commit_gate.NO_PRIVATE_TERMS)
    rules = {v.rule for v in violations}
    assert "ABSOLUTE_PATH" in rules


def test_repository_relative_path_is_not_a_violation():
    message = _message("fixed a bug in src/loader.py", "added a test")
    violations = commit_gate.validate_message(message, commit_gate.NO_PRIVATE_TERMS)
    rules = {v.rule for v in violations}
    assert "ABSOLUTE_PATH" not in rules


def test_private_term_caught_and_redacted_without_reproducing_the_secret():
    term_set = commit_gate.TermSet.of(terms=["projectcodename"])
    message = _message("shipped the projectcodename integration", "added a test")
    violations = commit_gate.validate_message(message, term_set)
    rendered = "; ".join(str(v) for v in violations)
    assert any(v.rule == "PRIVATE_TERM" for v in violations)
    # The redaction must not reproduce the full term verbatim in the report.
    assert "projectcodename" not in rendered


def test_missing_term_set_is_a_type_error():
    with pytest.raises(TypeError):
        commit_gate.validate_message(_message("a", "b"), None)


def test_bullet_shape_regex_matches_two_through_four():
    assert commit_gate.SHAPE.fullmatch(_message("a", "b"))
    assert commit_gate.SHAPE.fullmatch(_message("a", "b", "c"))
    assert commit_gate.SHAPE.fullmatch(_message("a", "b", "c", "d"))
    assert not commit_gate.SHAPE.fullmatch(_message("a"))
    assert not commit_gate.SHAPE.fullmatch(_message("a", "b", "c", "d", "e"))


def _run_cli(stdin: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS_DIR / "commit_gate.py"), *args],
        input=stdin, capture_output=True, text=True, cwd=str(TOOLS_DIR),
    )


def test_cli_accepts_valid_message_from_stdin():
    result = _run_cli(_message("a", "b"))
    assert result.returncode == 0
    assert "VALID" in result.stdout


def test_cli_rejects_and_prints_each_violation():
    result = _run_cli(_message("only one"))
    assert result.returncode != 0
    assert "VIOLATION" in result.stdout


# --- F5: the read-back side must accept git's own output -------------------
# `git log -1 --format=%B` terminates the message with TWO newlines. Stripping
# only one leaves a blank line that reads as EXTRA_CONTENT, so the read-back
# half of the double-sided contract failed on every well-formed commit.

GOOD = (
    "Summarize a numeric column from a CSV file\n"
    "\n"
    "- Report count, minimum, maximum and mean for a named column\n"
    "- Refuse a missing column, naming what was wrong\n"
)


def test_git_format_B_readback_is_accepted():
    assert commit_gate.validate_message(GOOD + "\n", commit_gate.NO_PRIVATE_TERMS) == []


def test_many_trailing_newlines_are_still_accepted():
    assert commit_gate.validate_message(GOOD + "\n\n\n", commit_gate.NO_PRIVATE_TERMS) == []


def test_real_prose_after_bullets_is_still_refused():
    bad = GOOD + "\nThis trailing paragraph is real content.\n"
    codes = [v.rule for v in commit_gate.validate_message(bad, commit_gate.NO_PRIVATE_TERMS)]
    assert "EXTRA_CONTENT" in codes


# --- the range gate: drift across a branch ----------------------------------
#
# `validate_range` shipped in 2.1.0 with **no test at all**,
# although the drift it detects — a convention that breaks once and never
# recovers — is easy to construct. A permanent regression test is cheap here
# because the property is deterministic: build a branch whose drift point is
# known, and assert the gate names exactly that point.


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)


@pytest.fixture
def drifting_history(tmp_path):
    """Five conforming commits, then three that drift, in that order."""
    repo = tmp_path / "history"
    repo.mkdir()
    _git(repo, "init", "--quiet", "--initial-branch", "main")
    _git(repo, "config", "user.name", "Ordinary Human")
    _git(repo, "config", "user.email", "human@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")

    conforming, drifting = [], []
    for index in range(8):
        (repo / f"f{index}.txt").write_text(f"{index}\n")
        _git(repo, "add", f"f{index}.txt")
        if index < 5:
            message = _message("first outcome", "second outcome", title=f"Add file number {index}")
        else:
            message = f"wip {index}\n"
        _git(repo, "commit", "--quiet", "-m", message)
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True
        ).stdout.strip()
        (conforming if index < 5 else drifting).append(sha)
    return repo, conforming, drifting


def test_a_range_reports_exactly_the_commits_that_drifted(drifting_history):
    repo, conforming, drifting = drifting_history
    failures = commit_gate.validate_range(str(repo), "refs/heads/main", None, commit_gate.NO_PRIVATE_TERMS)

    reported = {sha for sha, _ in failures}
    assert reported == set(drifting)
    assert reported.isdisjoint(conforming)
    assert all(violations for _, violations in failures)


def test_a_range_of_conforming_commits_is_clean(drifting_history):
    """The drift point is a boundary, so the clean side is asserted too."""
    repo, conforming, _ = drifting_history
    failures = commit_gate.validate_range(
        str(repo), conforming[-1], None, commit_gate.NO_PRIVATE_TERMS
    )
    assert failures == []


def test_a_baseline_excludes_history_before_it(drifting_history):
    """Range drift is asked about an unpublished segment, not all of history."""
    repo, conforming, drifting = drifting_history
    failures = commit_gate.validate_range(
        str(repo), "refs/heads/main", conforming[-1], commit_gate.NO_PRIVATE_TERMS
    )
    assert {sha for sha, _ in failures} == set(drifting)


def test_the_single_message_gate_cannot_see_range_drift(drifting_history):
    """Why the range surface exists, stated as a test rather than as a comment.

    Every one of those commits passed a gate at the moment it was made — the
    check runs before staging and on read-back, and then nothing ever re-reads
    the message again.
    """
    repo, _, drifting = drifting_history
    import gitread

    drifted = gitread.commit_message(str(repo), drifting[0])
    assert commit_gate.validate_message(drifted, commit_gate.NO_PRIVATE_TERMS)
    failures = commit_gate.validate_range(str(repo), drifting[0], None, commit_gate.NO_PRIVATE_TERMS)
    assert failures, "the range surface is the only one that re-reads a committed message"


# --- EC-B: a Conventional Commit subject is not a trailer --------------------
#
# Reproduced against the frozen 2.1.1 baseline before repair: `fix: correct the
# parser` was refused `TRAILER` while `feat: …` passed, because `fix` is in the
# trailer token set and the detector never asked *where* on the message the
# match occurred. The commit contract asks for a Conventional Commit subject, so
# the gate was refusing the form it requires.


def _codes(message):
    return [str(violation).split(":")[0] for violation in
            commit_gate.validate_message(message, commit_gate.NO_PRIVATE_TERMS)]


BODY = "\n\n- one bullet here\n- two bullet here\n"


@pytest.mark.parametrize(
    "subject",
    [
        "fix: correct the parser",        # the reproduced defect
        "feat: add the thing",
        "fix(pathmatch): correct it",
        "fix!: breaking change",
        "refactor(a/b): move it",
        "revert: undo it",
        "docs: update the readme",
        "perf: speed it up",
        "test: add the missing cases",
        "build: bump the toolchain",
        "ci: run the suite on push",
        "chore: tidy up",
        "style: reflow the prose",
    ],
)
def test_a_conventional_commit_subject_is_accepted(subject):
    assert _codes(subject + BODY) == []


@pytest.mark.parametrize(
    "subject",
    [
        "Signed-off-by: A Person",
        "Reviewed-by: A Person",
        "Change-Id: I0123456789",
        "Closes: #3",
    ],
)
def test_a_real_trailer_as_the_subject_is_still_refused(subject):
    """The exemption is for the Conventional type set, not for line 1."""
    assert "TRAILER" in _codes(subject + BODY)


@pytest.mark.parametrize(
    "body",
    [
        "\n\n- one bullet here\n- Fixes: #12\n",
        "\n\n- one bullet here\n- Signed-off-by: A Person\n",
        "\n\n- one bullet here\n- Change-Id: I0123456789\n",
    ],
)
def test_a_trailer_in_the_body_is_refused_under_a_conventional_subject(body):
    """A trailer does not become legal by sitting under an exempted subject."""
    assert "TRAILER" in _codes("fix: correct the parser" + body)


def test_a_subject_that_merely_starts_with_a_type_word_is_not_exempted():
    """`fixing:` and `features:` are not Conventional Commit types, and the
    exemption must not widen to anything that begins with one."""
    assert "TRAILER" in _codes("fix-it-later: something" + BODY)


def test_co_authored_by_is_still_refused_as_a_subject():
    assert "COAUTHOR" in _codes("Co-authored-by: An Assistant" + BODY)


@pytest.mark.parametrize(
    "subject",
    [
        "fix: Signed-off-by: A Person",
        "feat: Change-Id: I0123456789",
        "test: Fixes: #12",
        "chore: Reviewed-by: A Person",
        "refactor(core): Closes: #3",
    ],
)
def test_a_trailer_behind_a_conventional_prefix_is_still_refused(subject):
    """The first repair blanked the whole subject line, so `fix: Signed-off-by:
    A Person` passed clean — the docstring claimed otherwise and an independent
    audit caught it. Only the matched prefix is removed now."""
    assert "TRAILER" in _codes(subject + BODY)


def test_co_authored_by_behind_a_conventional_prefix_is_still_refused():
    assert "COAUTHOR" in _codes("fix: Co-authored-by: An Assistant" + BODY)
