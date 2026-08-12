"""The two known audit fixes: baseline self-exemption, and tri-state clean."""

import subprocess

import pytest

import outgoing_scan
from commit_gate import TermSet


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
    (directory / "readme.txt").write_text("an ordinary file\n")
    _git(directory, "add", "readme.txt")
    _git(directory, "commit", "--quiet", "-m", "first commit")
    return directory


def test_baseline_file_is_exempt_from_its_own_scan(repo):
    term_set = TermSet.of(terms=["projectcodename"])
    # The reviewed-baseline file records a prior match of the private term —
    # that is its entire purpose — so scanning its content would trip on the
    # very thing it exists to record.
    (repo / "reviewed-baseline.txt").write_text("projectcodename matched in commit abc123\n")
    _git(repo, "add", "reviewed-baseline.txt")
    _git(repo, "commit", "--quiet", "-m", "record a reviewed match")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout.strip()

    scanner = outgoing_scan.Scanner(term_set)
    report = outgoing_scan.scan_outgoing(
        repo, ref=head, baseline=None, scanner=scanner,
        content_exempt_paths=["reviewed-baseline.txt"],
    )

    assert "reviewed-baseline.txt" in report.exempted
    assert all(leak.subject != "reviewed-baseline.txt" for leak in report.leaks if leak.location == "blob")
    assert report.clean


def test_render_discloses_content_exemptions_even_when_clean(repo):
    """A clean report that exempted a file from content scanning must say so
    on its *rendered* surface, not only in the `exempted` field.

    The rendered string is what gets stored as capability evidence and read
    later by an auditor who did not run the command. The dataclass already
    carries `exempted` correctly, so asserting against the field would pass
    while the disclosure defect stood; this asserts against `render()`.
    """
    term_set = TermSet.of(terms=["projectcodename"])
    (repo / "reviewed-baseline.txt").write_text("projectcodename matched in commit abc123\n")
    _git(repo, "add", "reviewed-baseline.txt")
    _git(repo, "commit", "--quiet", "-m", "record a reviewed match")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout.strip()

    scanner = outgoing_scan.Scanner(term_set)
    report = outgoing_scan.scan_outgoing(
        repo, ref=head, baseline=None, scanner=scanner,
        content_exempt_paths=["reviewed-baseline.txt"],
    )

    assert report.clean  # data-level verdict is unchanged: exempted-but-clean stays clean
    rendered = report.render()
    assert "reviewed-baseline.txt" in rendered
    assert "exempt" in rendered.lower()


def test_without_the_exemption_the_baseline_file_trips_on_its_own_record(repo):
    term_set = TermSet.of(terms=["projectcodename"])
    (repo / "reviewed-baseline.txt").write_text("projectcodename matched in commit abc123\n")
    _git(repo, "add", "reviewed-baseline.txt")
    _git(repo, "commit", "--quiet", "-m", "record a reviewed match")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout.strip()

    scanner = outgoing_scan.Scanner(term_set)
    report = outgoing_scan.scan_outgoing(repo, ref=head, baseline=None, scanner=scanner, content_exempt_paths=())

    assert not report.clean
    assert any(leak.subject == "reviewed-baseline.txt" for leak in report.leaks)


def test_a_skipped_object_yields_clean_false_even_with_no_leaks(repo, monkeypatch):
    # Force one blob over the scan limit, so it lands in `skipped` rather than
    # being read. Nothing in the range is a leak, and the report must still
    # refuse to call itself clean: skipped is not clean.
    monkeypatch.setattr(outgoing_scan, "MAX_SCANNED_BLOB_BYTES", 1)
    scanner = outgoing_scan.Scanner(outgoing_scan.NO_PRIVATE_TERMS)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout.strip()
    report = outgoing_scan.scan_outgoing(repo, ref=head, baseline=None, scanner=scanner)

    assert report.skipped
    assert not report.leaks
    assert report.clean is False


def test_clean_range_reports_clean(repo):
    scanner = outgoing_scan.Scanner(outgoing_scan.NO_PRIVATE_TERMS)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout.strip()
    report = outgoing_scan.scan_outgoing(repo, ref=head, baseline=None, scanner=scanner)
    assert report.clean
    assert not report.skipped
    assert not report.leaks


def test_credential_in_a_blob_is_a_leak(repo):
    (repo / "config.txt").write_text("token=sk-ant-abcdefghijklmnopqrstuvwx0123456789\n")
    _git(repo, "add", "config.txt")
    _git(repo, "commit", "--quiet", "-m", "add config")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout.strip()
    scanner = outgoing_scan.Scanner(outgoing_scan.NO_PRIVATE_TERMS)
    report = outgoing_scan.scan_outgoing(repo, ref=head, baseline=None, scanner=scanner)
    assert not report.clean
    assert any(leak.kind == "credential" for leak in report.leaks)


def test_scanner_rejects_non_scanner_argument(repo):
    with pytest.raises(TypeError):
        outgoing_scan.scan_outgoing(repo, ref="HEAD", baseline=None, scanner=object())
