"""evidence_put: content-addressed write-then-reference, and its refusal."""

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

import evidence_put
from errors import IntegrityError

TOOLS_DIR = Path(__file__).resolve().parent.parent


def test_digest_round_trips(tmp_path):
    source = tmp_path / "source.txt"
    source.write_bytes(b"evidence bytes\n")
    evidence_dir = tmp_path / "evidence"

    reference = evidence_put.put(evidence_dir, source)

    expected_digest = hashlib.sha256(b"evidence bytes\n").hexdigest()
    assert reference == f"sha256-{expected_digest}-source.txt"
    stored = evidence_dir / reference
    assert stored.is_file()
    assert stored.read_bytes() == b"evidence bytes\n"


def test_put_is_idempotent_for_identical_content(tmp_path):
    source = tmp_path / "source.txt"
    source.write_bytes(b"same bytes\n")
    evidence_dir = tmp_path / "evidence"

    first = evidence_put.put(evidence_dir, source)
    second = evidence_put.put(evidence_dir, source)
    assert first == second


def test_differing_content_at_the_same_reference_refuses(tmp_path):
    source = tmp_path / "source.txt"
    source.write_bytes(b"original bytes\n")
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    reference = evidence_put.put(evidence_dir, source)
    # Corrupt the stored evidence in place, so its content no longer matches
    # the digest its own name promises.
    (evidence_dir / reference).write_bytes(b"corrupted bytes that do not match the digest\n")

    with pytest.raises(IntegrityError):
        evidence_put.put(evidence_dir, source)


def test_no_temporary_file_survives_a_successful_put(tmp_path):
    source = tmp_path / "source.txt"
    source.write_bytes(b"clean\n")
    evidence_dir = tmp_path / "evidence"
    evidence_put.put(evidence_dir, source)
    leftovers = [p for p in evidence_dir.iterdir() if p.name.startswith(".")]
    assert leftovers == []


def test_missing_source_refuses(tmp_path):
    with pytest.raises(IntegrityError):
        evidence_put.put(tmp_path / "evidence", tmp_path / "does-not-exist.txt")


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS_DIR / "evidence_put.py"), *args],
        capture_output=True, text=True, cwd=str(TOOLS_DIR),
    )


def test_cli_prints_the_reference_and_exits_zero(tmp_path):
    source = tmp_path / "source.txt"
    source.write_bytes(b"cli bytes\n")
    evidence_dir = tmp_path / "evidence"
    result = _run_cli(str(evidence_dir), str(source))
    assert result.returncode == 0
    expected_digest = hashlib.sha256(b"cli bytes\n").hexdigest()
    assert result.stdout.strip() == f"sha256-{expected_digest}-source.txt"


def test_cli_exits_nonzero_on_refusal(tmp_path):
    source = tmp_path / "source.txt"
    source.write_bytes(b"original\n")
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    reference = evidence_put.put(evidence_dir, source)
    (evidence_dir / reference).write_bytes(b"corrupted\n")
    result = _run_cli(str(evidence_dir), str(source))
    assert result.returncode != 0


# --- EC-E: evidence is private material and was written world-readable -------
#
# Reproduced against frozen 2.1.1: directory `0o755`, entry `0o644`, and nothing
# checked either. The mode is now requested AND read back, because `mkdir` and
# `open` are both masked by the umask, so the mode a call asks for and the mode
# a file has are two different facts.

import os
import stat


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def test_the_evidence_directory_is_owner_only(tmp_path):
    source = tmp_path / "finding.txt"
    source.write_text("private reproduction output")
    evidence = tmp_path / "evidence"

    evidence_put.put(evidence, source)
    assert _mode(evidence) == 0o700


def test_every_evidence_entry_is_owner_only(tmp_path):
    source = tmp_path / "finding.txt"
    source.write_text("private reproduction output")
    evidence = tmp_path / "evidence"

    reference = evidence_put.put(evidence, source)
    assert _mode(evidence / reference) == 0o600


def test_the_mode_holds_under_a_permissive_umask(tmp_path):
    """The reproduction condition. `mkdir(mode=0o700)` alone is masked by the
    umask, so a permissive umask silently reopened the directory."""
    source = tmp_path / "finding.txt"
    source.write_text("private")
    evidence = tmp_path / "evidence"

    previous = os.umask(0o000)
    try:
        reference = evidence_put.put(evidence, source)
    finally:
        os.umask(previous)

    assert _mode(evidence) == 0o700
    assert _mode(evidence / reference) == 0o600


def test_a_pre_existing_loose_directory_is_tightened(tmp_path):
    """Directories created by earlier versions are `0o755`. Tightening cannot
    open a hole, and refusing would strand every one of them."""
    source = tmp_path / "finding.txt"
    source.write_text("private")
    evidence = tmp_path / "evidence"
    evidence.mkdir(mode=0o755)
    os.chmod(evidence, 0o755)

    evidence_put.put(evidence, source)
    assert _mode(evidence) == 0o700


def test_an_entry_that_became_readable_is_refused_rather_than_retrusted(tmp_path):
    """A put that finds its reference already present verifies it. Content was
    already verified; the mode is now verified too, because an entry somebody
    else can read is not the entry this module promised to store."""
    source = tmp_path / "finding.txt"
    source.write_text("private")
    evidence = tmp_path / "evidence"
    reference = evidence_put.put(evidence, source)

    os.chmod(evidence / reference, 0o644)
    with pytest.raises(IntegrityError) as caught:
        evidence_put.put(evidence, source)
    assert "readable beyond its owner" in caught.value.cause


def test_the_content_guarantee_is_unchanged(tmp_path):
    """Non-regression: the mode work must not have touched the digest rules."""
    source = tmp_path / "finding.txt"
    source.write_text("private")
    evidence = tmp_path / "evidence"
    reference = evidence_put.put(evidence, source)

    assert evidence_put.put(evidence, source) == reference
    (evidence / reference).chmod(0o600)
    (evidence / reference).write_text("tampered")
    with pytest.raises(IntegrityError):
        evidence_put.put(evidence, source)


def test_every_directory_created_for_the_store_is_owner_only(tmp_path):
    """`mkdir(parents=True, mode=…)` applies the mode to the leaf only, so a
    store two levels down left its new parents at `0o755` — contents protected,
    directory names traversable. Found by an independent audit."""
    source = tmp_path / "finding.txt"
    source.write_text("private")
    evidence_put.put(tmp_path / "deep" / "nested" / "evidence", source)

    assert _mode(tmp_path / "deep") == 0o700
    assert _mode(tmp_path / "deep" / "nested") == 0o700
    assert _mode(tmp_path / "deep" / "nested" / "evidence") == 0o700


def test_an_existing_directory_is_not_re_moded_by_this_module(tmp_path):
    """Only what it creates. An evidence directory inside a project must not
    make the project directory owner-only."""
    project = tmp_path / "project"
    project.mkdir(mode=0o755)
    os.chmod(project, 0o755)
    source = tmp_path / "finding.txt"
    source.write_text("private")

    evidence_put.put(project / "evidence", source)
    assert _mode(project) == 0o755
    assert _mode(project / "evidence") == 0o700


def test_an_older_store_is_tightened_even_when_its_entry_is_refused(tmp_path):
    """The entry check ran first, so a store made by an earlier version was
    refused on its first put and left with its loose directory mode intact —
    the exact stranding the tightening exists to avoid."""
    source = tmp_path / "finding.txt"
    source.write_text("private")
    evidence = tmp_path / "evidence"
    reference = evidence_put.put(evidence, source)

    os.chmod(evidence, 0o755)
    os.chmod(evidence / reference, 0o644)
    with pytest.raises(IntegrityError):
        evidence_put.put(evidence, source)
    assert _mode(evidence) == 0o700, "the directory was left loose by an early refusal"
