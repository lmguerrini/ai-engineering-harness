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
