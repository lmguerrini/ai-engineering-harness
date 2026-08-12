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
