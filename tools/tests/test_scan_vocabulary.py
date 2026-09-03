"""The acceptance criteria the Pilot Run's candidates named, as executable tests.

Each test here is the criterion from one evolution candidate, written so that
removing the change makes it fail. They are grouped because they are one defect
class seen four times: a rule set that is not what the report implies it is.
"""

import json
import subprocess

import pytest

import outgoing_scan
from commit_gate import TermSet, validate_message
from project_contract import ProjectContract


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)


def _head(repo):
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    directory = tmp_path / "project"
    directory.mkdir()
    _git(directory, "init", "--quiet", "--initial-branch", "main")
    _git(directory, "config", "user.name", "Ordinary Human")
    _git(directory, "config", "user.email", "human@example.invalid")
    _git(directory, "config", "commit.gpgsign", "false")
    return directory


@pytest.fixture
def pack_defaults(tmp_path):
    """The shipped default vocabulary, as the tiering change leaves it."""
    pack = tmp_path / "pack"
    (pack / "policy").mkdir(parents=True)
    source = __import__("pathlib").Path(__file__).resolve().parent.parent.parent
    (pack / "policy" / "private-terms.default.json").write_text(
        (source / "policy" / "private-terms.default.json").read_text()
    )
    return pack


def _contract(tmp_path, repo, body=""):
    path = tmp_path / "PROJECT.yaml"
    path.write_text(f"project:\n  repo_path: {repo}\n{body}")
    return path


# --- EC-P: one --project invocation reproduces the runner script's verdict ----

def test_the_project_flag_alone_reproduces_a_scan(repo, tmp_path, pack_defaults, capsys):
    """EC-P's criterion: only `--project`, and the same answer.

    With the contract supplying the repository, the positionals are
    [REF] [BASELINE]. Getting that wrong bound the ref to `repository` and then
    refused for want of a ref — the contract was supplying the repo path while
    the command line was still read as though it were not.
    """
    (repo / "a.txt").write_text("ordinary content\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "--quiet", "-m", "first")

    contract = tmp_path / "PROJECT.yaml"
    contract.write_text(
        f"project:\n  repo_path: {repo}\n"
        f"private_terms:\n  default_set: {pack_defaults / 'policy' / 'private-terms.default.json'}\n"
    )

    assert outgoing_scan._cli(["--project", str(contract), "main"]) == 0
    out = capsys.readouterr().out
    assert "outgoing range ROOT..main [tiered]: clean" in out
    # The rule the scan ran is named, with how it was reached and its digest, so
    # a surprising count can be attributed to the tree or to the checker. This
    # contract names one absolute location, so the answer is `declared`: nothing
    # was substituted for anything, which is a different fact from `canonical`
    # and is reported as one.
    assert "rules read from:" in out and "(declared, sha256 " in out
    assert "rules applied:" in out


def test_an_unreadable_contract_exits_distinctly_rather_than_scanning_nothing(tmp_path, capsys):
    """Exit 2, not 0. A gate that could not read its rules has not passed."""
    bad = tmp_path / "PROJECT.yaml"
    bad.write_text("project:\n  name: a\n   bad_indent: b\n")
    assert outgoing_scan._cli(["--project", str(bad), "main"]) == 2
    assert "CONTRACT UNREADABLE" in capsys.readouterr().out


# --- EC-M: bare common words must not fire on blob content -------------------

def test_ordinary_prose_containing_a_worker_name_scans_clean_in_a_data_file(repo, tmp_path, pack_defaults):
    """EC-M's criterion, verbatim.

    `claude` matched Jean-Claude Martin in committed prose and `terra` is
    Italian for "ground". Four such findings, zero true positives, and clearing
    one cost a full history rebuild.
    """
    (repo / "corpus.txt").write_text(
        "Jean-Claude Martin spoke about the envelope of the agreement.\n"
        "Il satellite fu lasciato a terra.\n"
    )
    _git(repo, "add", "corpus.txt")
    _git(repo, "commit", "--quiet", "-m", "add source material")

    contract = ProjectContract.load(_contract(tmp_path, repo), pack_root=pack_defaults)
    scanner = outgoing_scan.Scanner(
        TermSet.of(
            contract.default_terms, contract.default_patterns,
            contract.default_identity_terms, contract.default_identity_patterns,
        )
    )
    report = outgoing_scan.scan_outgoing(repo, ref=_head(repo), baseline=None, scanner=scanner)
    assert report.clean, report.render()


def test_the_same_worker_name_in_a_commit_message_is_still_refused(repo, tmp_path, pack_defaults):
    """The other half of EC-M. Narrowing the tier must not disarm the real case."""
    contract = ProjectContract.load(_contract(tmp_path, repo), pack_root=pack_defaults)
    term_set = TermSet.of(
        contract.default_terms, contract.default_patterns,
        contract.default_identity_terms, contract.default_identity_patterns,
    )
    violations = validate_message(
        "Add the loader\n\n- Route the work to claude for review\n- Record the outcome\n",
        term_set,
    )
    assert any(v.rule == "PRIVATE_TERM" for v in violations), violations


def test_a_branch_name_carrying_a_worker_name_is_still_refused(repo, tmp_path, pack_defaults):
    """Ref names are written deliberately, so they keep the full vocabulary."""
    (repo / "a.txt").write_text("x\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "--quiet", "-m", "first")
    contract = ProjectContract.load(_contract(tmp_path, repo), pack_root=pack_defaults)
    scanner = outgoing_scan.Scanner(
        TermSet.of(
            contract.default_terms, contract.default_patterns,
            contract.default_identity_terms, contract.default_identity_patterns,
        )
    )
    leaks = scanner.scan_name("feature/spark-review", location="ref_name", subject="ref")
    assert any(leak.kind == "private_term" for leak in leaks), leaks


# --- EC-I: the ticket pattern must not fire on an ordinary Python project ----

def test_a_lockfile_and_a_sha256_reference_scan_clean_with_no_exemption(repo, tmp_path, pack_defaults):
    """EC-I's criterion, verbatim. Measured at 7 findings, 0 true positives."""
    (repo / "uv.lock").write_text("blis-1.2.0\ncffi-2.0.0\nidna-3.10\n")
    (repo / "notes.md").write_text("Encoded as utf-8 and hashed with SHA-256 for post-2011 records.\n")
    _git(repo, "add", "uv.lock", "notes.md")
    _git(repo, "commit", "--quiet", "-m", "add dependency lock")

    contract = ProjectContract.load(_contract(tmp_path, repo), pack_root=pack_defaults)
    scanner = outgoing_scan.Scanner(
        TermSet.of(
            contract.default_terms, contract.default_patterns,
            contract.default_identity_terms, contract.default_identity_patterns,
        )
    )
    report = outgoing_scan.scan_outgoing(repo, ref=_head(repo), baseline=None, scanner=scanner)
    assert report.clean, report.render()


# --- EC-H: the defaults must apply, and the report must say what it applied ---

def test_the_two_invocations_that_disagreed_now_agree(repo, tmp_path, pack_defaults):
    """EC-H's criterion.

    The same scanner over the same range reported `clean (5 commits, 17 blobs)`
    with project terms only and `7 leak(s)` with defaults plus project terms.
    Nothing in the first report disclosed that 59 rules were absent.
    """
    (repo / "doc.md").write_text("The runtime pack governs this work.\n")
    _git(repo, "add", "doc.md")
    _git(repo, "commit", "--quiet", "-m", "add a document")
    head = _head(repo)

    contract = ProjectContract.load(
        _contract(tmp_path, repo, "private_terms:\n  project_additions: [\"projectword\"]\n"),
        pack_root=pack_defaults,
    )
    # What the coordinator types: only the project's own additions.
    with_project_terms = TermSet.of(
        (*contract.default_terms, *contract.project_terms),
        (*contract.default_patterns, *contract.project_patterns),
        contract.default_identity_terms,
        contract.default_identity_patterns,
    )
    report = outgoing_scan.scan_outgoing(
        repo, ref=head, baseline=None, scanner=outgoing_scan.Scanner(with_project_terms)
    )
    assert not report.clean, "the default vocabulary was not applied"
    assert any("private term" in leak.detail for leak in report.leaks)


def test_every_report_states_the_rule_counts_it_applied(repo, tmp_path, pack_defaults):
    """A report that does not say what it loaded cannot be audited."""
    (repo / "a.txt").write_text("ordinary\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "--quiet", "-m", "first")
    contract = ProjectContract.load(_contract(tmp_path, repo), pack_root=pack_defaults)
    scanner = outgoing_scan.Scanner(
        TermSet.of(
            contract.default_terms, contract.default_patterns,
            contract.default_identity_terms, contract.default_identity_patterns,
        )
    )
    rendered = outgoing_scan.scan_outgoing(
        repo, ref=_head(repo), baseline=None, scanner=scanner
    ).render()
    assert "rules applied:" in rendered
    assert "identity-only term(s)" in rendered


# --- EC-K: directory exemptions, and dead declarations that say so -----------

def test_a_directory_exemption_covers_everything_beneath_it(repo):
    """EC-K's criterion. Under fnmatch, `annotations/` matched nothing at all."""
    (repo / "annotations").mkdir()
    (repo / "annotations" / "gold.jsonl").write_text("mentions runtime pack internals\n")
    # `-f` because this host's global ignore rule excludes `*.jsonl`, which is
    # the very condition EC-J exists to catch. It surfaced here by accident,
    # exactly as it did on the real project — see `test_workspace_tracking`.
    _git(repo, "add", "-f", "annotations/gold.jsonl")
    _git(repo, "commit", "--quiet", "-m", "add annotations")

    scanner = outgoing_scan.Scanner(TermSet.of(terms=["runtime pack"]))
    report = outgoing_scan.scan_outgoing(
        repo, ref=_head(repo), baseline=None, scanner=scanner,
        content_exempt_paths=["annotations/"],
    )
    assert report.clean, report.render()
    assert report.exempted == ["annotations/gold.jsonl"]


def test_an_exemption_matching_nothing_is_reported_as_matching_nothing(repo):
    """The half that made the defect invisible: silence.

    With and without the exemption the two reports were byte-identical, so
    nothing distinguished 'exempted' from 'the declaration did nothing'.
    """
    (repo / "a.txt").write_text("ordinary content\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "--quiet", "-m", "first")

    scanner = outgoing_scan.Scanner(TermSet.of(terms=["absentword"]))
    report = outgoing_scan.scan_outgoing(
        repo, ref=_head(repo), baseline=None, scanner=scanner,
        content_exempt_paths=["nowhere/"],
    )
    assert report.unused_exemptions == ["nowhere/"]
    assert "DECLARED BUT MATCHED NOTHING: nowhere/" in report.render()


def test_a_clean_report_still_states_a_zero_exemption_count(repo):
    (repo / "a.txt").write_text("ordinary\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "--quiet", "-m", "first")
    scanner = outgoing_scan.Scanner(TermSet.of(terms=["absentword"]))
    rendered = outgoing_scan.scan_outgoing(
        repo, ref=_head(repo), baseline=None, scanner=scanner
    ).render()
    assert "0 file(s) content-exempt by declaration" in rendered


# --- EC-N: amending the tip does not reach an earlier blob -------------------

def test_a_finding_on_a_path_with_two_reachable_blobs_says_amending_will_not_clear_it(repo):
    """EC-N's criterion.

    Observed: 2 findings → reword + `--amend` → 1 finding, with the survivor in
    the preceding commit. The operator is shown a smaller number, which reads as
    progress rather than as an incomplete repair.
    """
    (repo / "notes.md").write_text("the runtime pack decides this\n")
    _git(repo, "add", "notes.md")
    _git(repo, "commit", "--quiet", "-m", "first version")
    (repo / "notes.md").write_text("the runtime pack still decides this\n")
    _git(repo, "add", "notes.md")
    _git(repo, "commit", "--quiet", "-m", "second version")

    scanner = outgoing_scan.Scanner(TermSet.of(terms=["runtime pack"]))
    report = outgoing_scan.scan_outgoing(repo, ref=_head(repo), baseline=None, scanner=scanner)
    assert report.blob_multiplicity["notes.md"] == 2
    assert "amending the tip will not clear the earlier one" in report.render()


def test_a_single_blob_finding_does_not_claim_an_amend_trap(repo):
    """The negative half: the advice must not fire where it does not apply."""
    (repo / "notes.md").write_text("the runtime pack decides this\n")
    _git(repo, "add", "notes.md")
    _git(repo, "commit", "--quiet", "-m", "only version")
    scanner = outgoing_scan.Scanner(TermSet.of(terms=["runtime pack"]))
    rendered = outgoing_scan.scan_outgoing(
        repo, ref=_head(repo), baseline=None, scanner=scanner
    ).render()
    assert "amending the tip" not in rendered


# --- EC-AA/AB: the staged diff, before the commit exists ---------------------

def test_the_staged_scan_catches_vocabulary_before_it_becomes_a_commit(repo):
    """Vocabulary in prose about the work, caught here rather than at closure."""
    (repo / "seed.txt").write_text("x\n")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "--quiet", "-m", "seed")

    (repo / "test_thing.py").write_text('"""Exercises the runtime pack loader."""\n')
    _git(repo, "add", "test_thing.py")

    scanner = outgoing_scan.Scanner(TermSet.of(terms=["runtime pack"]))
    report = outgoing_scan.scan_staged(repo, scanner=scanner)
    assert not report.clean
    assert any(leak.subject == "test_thing.py" for leak in report.leaks)


def test_the_staged_gate_is_strict_where_the_history_gate_is_tiered(repo):
    """The asymmetry, and the hole it closes.

    Tiering keeps bare common words off committed blob content, because there
    they found four false positives and no true one, and clearing one cost a
    history rebuild. But process vocabulary
    in prose about the work — in a test docstring, say — uses
    exactly the bare words the tier stops applying.

    So the staged gate applies everything: there a false positive costs one
    reword before the text is committed, and the expense that justified tiering
    does not exist.
    """
    (repo / "seed.txt").write_text("x\n")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "--quiet", "-m", "seed")

    (repo / "test_thing.py").write_text('"""Exercises the harness loader."""\n')
    _git(repo, "add", "test_thing.py")

    identity_only = TermSet.of(terms=["runtime pack"], identity_terms=["harness"])

    strict = outgoing_scan.scan_staged(
        repo, scanner=outgoing_scan.Scanner(identity_only, strict=True)
    )
    assert not strict.clean, "the staged gate must see a bare identity term in content"

    tiered = outgoing_scan.scan_staged(
        repo, scanner=outgoing_scan.Scanner(identity_only)
    )
    assert tiered.clean, "the history tiering must still exclude it, or nothing changed"


def test_the_staged_report_says_it_ran_strict(repo):
    """A stricter run that does not disclose its strictness is unauditable."""
    (repo / "seed.txt").write_text("x\n")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "--quiet", "-m", "seed")
    (repo / "a.py").write_text("ordinary\n")
    _git(repo, "add", "a.py")
    scanner = outgoing_scan.Scanner(TermSet.of(terms=["absentword"]), strict=True)
    assert "strict" in outgoing_scan.scan_staged(repo, scanner=scanner).render()


def test_the_staged_scan_reads_the_index_not_the_working_tree(repo):
    """What gets committed is what the index holds.

    Reading the working tree passes a gate on text nobody is committing — and
    fails one on text nobody staged.
    """
    (repo / "seed.txt").write_text("x\n")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "--quiet", "-m", "seed")

    (repo / "doc.md").write_text("clean text\n")
    _git(repo, "add", "doc.md")
    # Dirty the working tree *after* staging. The index is still clean.
    (repo / "doc.md").write_text("now mentions the runtime pack\n")

    scanner = outgoing_scan.Scanner(TermSet.of(terms=["runtime pack"]))
    assert outgoing_scan.scan_staged(repo, scanner=scanner).clean
