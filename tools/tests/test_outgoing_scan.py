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


# --- the path surface has to be the real path -------------------------------
#
# Git's default, line-based output C-quotes any path it cannot print literally.
# The leak scanner read that output, so a declared private term appearing in a
# non-ASCII directory name was matched against `"session\303\251-private/..."`
# — which does not contain the term. Reproduced against frozen 2.1.1: the scan
# reported `clean`. `pack_pin.py` already used `-z` and said why; this path did
# not.


@pytest.mark.parametrize(
    "directory",
    [
        "sessioné-private",       # non-ASCII: C-quoted by git
        "session private",        # a space: NOT quoted, so this must keep working
        'session"private',        # a quote: C-quoted
    ],
)
def test_a_private_term_in_a_path_git_must_quote_is_still_found(repo, directory):
    (repo / directory).mkdir()
    (repo / directory / "notes.md").write_text("ordinary content\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "add material")

    scanner = outgoing_scan.Scanner(TermSet.of(terms=[directory]))
    report = outgoing_scan.scan_outgoing(
        repo, ref="refs/heads/main", baseline=None, scanner=scanner
    )
    assert not report.clean, "a declared private term in a path scanned as clean"
    assert any(directory in leak.subject for leak in report.leaks)


def test_the_report_does_not_echo_the_private_term_it_found(repo):
    """The finding names the path; the term itself is redacted."""
    (repo / "sessioné-private").mkdir()
    (repo / "sessioné-private" / "notes.md").write_text("content\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "add material")

    scanner = outgoing_scan.Scanner(TermSet.of(terms=["sessioné-private"]))
    rendered = outgoing_scan.scan_outgoing(
        repo, ref="refs/heads/main", baseline=None, scanner=scanner
    ).render()
    assert "declared private term" in rendered
    assert "sessioné-private/notes.md" in rendered  # the path is named
    assert "'sessioné-private'" not in rendered     # the term is not
