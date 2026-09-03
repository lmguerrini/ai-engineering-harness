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


# --- CA-AMD-5 / RP-EC-1: an exemption scopes the project's vocabulary --------
#
# `UNIVERSAL_LEAK_KINDS` states that a credential, a local path and a generated
# identifier are private whoever wrote them, so "no project gets to declare them
# acceptable". That sentence was in the source and was not implemented: an
# exempted blob was not read at all. Reproduced against frozen 2.1.1 — an
# AWS-shaped key and a home-directory path inside an exempted file reported
# `clean`.


CREDENTIAL = "AKIAIOSFODNN7EXAMPLE"
LOCAL_PATH = "/Users/someone/private/session-4417/notes"


@pytest.fixture
def repo_with_fixture_dir(repo):
    (repo / "fixtures").mkdir()
    (repo / "fixtures" / "leaky.md").write_text(
        f"a credential: {CREDENTIAL}\nand a path: {LOCAL_PATH}\n"
    )
    (repo / "fixtures" / "denylist.md").write_text(
        "the denylist itself names forbidden-codename-alpha as a fixture\n"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "add fixtures")
    return repo


def _scan(repo, exempt=()):
    scanner = outgoing_scan.Scanner(TermSet.of(terms=["forbidden-codename-alpha"]))
    return outgoing_scan.scan_outgoing(
        repo, ref="refs/heads/main", baseline=None, scanner=scanner,
        content_exempt_paths=tuple(exempt),
    )


def test_an_exemption_does_not_switch_off_credential_detection(repo_with_fixture_dir):
    report = _scan(repo_with_fixture_dir, exempt=["fixtures/"])
    assert not report.clean
    assert any(leak.kind == "credential" for leak in report.leaks)


def test_an_exemption_does_not_switch_off_local_path_detection(repo_with_fixture_dir):
    report = _scan(repo_with_fixture_dir, exempt=["fixtures/"])
    assert any(leak.kind == "local_path" for leak in report.leaks)


def test_an_exemption_does_remove_the_projects_own_vocabulary(repo_with_fixture_dir):
    """The motivating case, which must keep working: a file that *is* the
    denylist, or the negative fixtures for it."""
    without = _scan(repo_with_fixture_dir)
    assert any(leak.kind == "private_term" for leak in without.leaks)

    with_exemption = _scan(repo_with_fixture_dir, exempt=["fixtures/denylist.md"])
    assert not any(leak.kind == "private_term" for leak in with_exemption.leaks)
    # Everything still reported comes from the file that was NOT exempted, and
    # every one of those is a universal kind.
    assert {leak.kind for leak in with_exemption.leaks} <= set(outgoing_scan.UNIVERSAL_LEAK_KINDS)
    assert {leak.subject for leak in with_exemption.leaks} == {"fixtures/leaky.md"}


def test_the_report_states_that_the_exemption_was_narrow(repo_with_fixture_dir):
    """A reader must not take `content-exempt` to mean `not scanned`."""
    rendered = _scan(repo_with_fixture_dir, exempt=["fixtures/"]).render()
    assert "project vocabulary only" in rendered
    assert "still applied" in rendered


def test_every_universal_kind_survives_an_exemption():
    """Stated against the constant rather than against three examples, so a
    kind added later is covered by construction."""
    exemptible = set(outgoing_scan.EXEMPTIBLE_LEAK_KINDS)
    assert exemptible == set(outgoing_scan.VOCABULARY_LEAK_KINDS)
    assert not exemptible & set(outgoing_scan.UNIVERSAL_LEAK_KINDS)


def test_the_staged_gate_applies_the_same_rule(repo_with_fixture_dir):
    """The staged gate is the strict one; an exemption may not make it looser
    there either."""
    (repo_with_fixture_dir / "fixtures" / "staged.md").write_text(f"key {CREDENTIAL}\n")
    _git(repo_with_fixture_dir, "add", "fixtures/staged.md")

    scanner = outgoing_scan.Scanner(TermSet.of(terms=["forbidden-codename-alpha"]))
    report = outgoing_scan.scan_staged(
        repo_with_fixture_dir, scanner=scanner, content_exempt_paths=("fixtures/",)
    )
    assert any(leak.kind == "credential" for leak in report.leaks)


# --- the tier a verdict came from, and the range that was never read ----------
#
# Both reproduced against the frozen 2.2.0 baseline before repair: the same
# range under the two tiers produced `clean` and `1 leak(s)` with neither
# headline naming a tier, and a range resolving to nothing rendered
# `clean (0 commits, 0 blobs)`.


def _identity_only(term):
    """A bare common word: applied to names everywhere, to content only in strict."""
    return TermSet.of(terms=(), patterns=(), identity_terms=[term], identity_patterns=())


def test_the_two_tiers_disagree_on_one_range_and_each_headline_names_its_tier(repo):
    (repo / "prose.md").write_text("the envelope was sealed\n")
    _git(repo, "add", "prose.md")
    _git(repo, "commit", "--quiet", "-m", "add prose")

    verdicts = {}
    for strict in (False, True):
        report = outgoing_scan.scan_outgoing(
            repo, ref="HEAD", baseline=None,
            scanner=outgoing_scan.Scanner(_identity_only("envelope"), strict=strict),
        )
        verdicts[strict] = (len(report.leaks), report.render().splitlines()[0])

    # The disagreement is the reason the tier has to be stated. If this ever
    # stops holding, the fixture no longer reproduces the defect and the
    # assertions below would pass for the wrong reason.
    assert verdicts[False][0] != verdicts[True][0], "the fixture no longer distinguishes the tiers"
    assert "[tiered]" in verdicts[False][1] and "[strict]" not in verdicts[False][1]
    assert "[strict]" in verdicts[True][1] and "[tiered]" not in verdicts[True][1]


def test_a_range_that_resolved_to_nothing_does_not_render_as_clean(repo):
    report = outgoing_scan.scan_outgoing(
        repo, ref="HEAD", baseline="HEAD",
        scanner=outgoing_scan.Scanner(_identity_only("envelope"), strict=True),
    )
    rendered = report.render()
    assert outgoing_scan.NOTHING_EXAMINED in rendered.splitlines()[0]
    assert "clean" not in rendered.splitlines()[0]
    # And it says why a reader is probably here.
    assert "not the one you meant" in rendered


def test_the_cli_exits_two_when_it_read_nothing(repo, capsys):
    """Distinct from 0 and from 1. A gate that read nothing has not passed and
    has not found anything either."""
    status = outgoing_scan._cli([str(repo), "HEAD", "HEAD", "--term", "envelope"])
    assert status == 2
    assert outgoing_scan.NOTHING_EXAMINED in capsys.readouterr().out


def test_the_staged_gate_names_strict_in_its_headline_not_in_its_vocabulary(repo):
    """The mode used to be appended to the provenance line, where a reader
    taking the first line of a stored report never saw it."""
    (repo / "staged.md").write_text("nothing notable\n")
    _git(repo, "add", "staged.md")
    report = outgoing_scan.scan_staged(
        repo, scanner=outgoing_scan.Scanner(_identity_only("envelope"), strict=True)
    )
    headline = report.render().splitlines()[0]
    assert "[strict]" in headline
    assert "strict" not in report.vocabulary
