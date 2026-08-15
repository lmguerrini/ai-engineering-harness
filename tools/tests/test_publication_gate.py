"""EC-AF: publication safety as a ref-namespace contract.

The scenario every test here reconstructs is real. A repository's branch
history passed every authorship check, with no trailers anywhere,
while `refs/notes/chatter` carried gzip+base64 records naming an agent, a model
id and a session uuid. `git log`, `git status`, `git ls-files`, `git diff` and
`git show` were all blind to it, and those five were the entire hygiene surface.

The adversarial cases matter more than the happy path, so they are most of this
file: a writer that re-creates refs within seconds of deletion, a push form that
carries every ref regardless of the allowlist, and a remote that cannot be read.
"""

import subprocess

import pytest

import publication_gate
from publication_gate import check_push_command, inspect_namespace, verify_remote


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)


@pytest.fixture
def repo(tmp_path):
    directory = tmp_path / "project"
    directory.mkdir()
    _git(directory, "init", "--quiet", "--initial-branch", "main")
    _git(directory, "config", "user.name", "Lorenzo")
    _git(directory, "config", "user.email", "human@example.invalid")
    _git(directory, "config", "commit.gpgsign", "false")
    (directory / "readme.md").write_text("a project\n")
    _git(directory, "add", "readme.md")
    _git(directory, "commit", "--quiet", "-m", "first")
    return directory


def _add_notes_ref(repo, ref="refs/notes/chatter"):
    """Reproduce the observed writer: a note commit under a non-human identity."""
    _git(
        repo, "-c", "user.name=chatter", "-c", "user.email=observer@chatter.local",
        "-c", f"core.notesRef={ref}", "notes", "add", "-m",
        "chatter:gzip:H4sIAAAAAAAA", "HEAD",
    )


# --- (a) enumerate and classify every namespace ------------------------------

def test_a_clean_repository_with_only_branches_passes(repo):
    report = inspect_namespace(repo, public_ref="refs/heads/main")
    assert report.clean, report.render()
    assert report.refs_seen == 1


def test_a_notes_ref_is_refused_even_though_every_other_gate_reports_clean(repo):
    """The whole finding, in one test.

    The precise claim, checked rather than assumed: the pack's **own** outgoing
    scanner walks the object range of one ref, so it never reaches a ref nobody
    named. It reports clean on this repository while `refs/notes/chatter` sits
    in it carrying a non-human identity.

    (`git log --all` *does* traverse notes refs, which is worth stating because
    it is the one command that would have shown this. The project's own check
    used `--all` but formatted only `%H%n%B`, so it read the payload — base64,
    matching no vocabulary — and never the author line.)
    """
    import outgoing_scan
    from commit_gate import NO_PRIVATE_TERMS

    _add_notes_ref(repo)

    assert _git(repo, "status", "--porcelain").stdout.strip() == ""
    assert "chatter" not in _git(repo, "log", "--format=%an <%ae>%n%B").stdout

    scan = outgoing_scan.scan_outgoing(
        repo, ref="refs/heads/main", baseline=None,
        scanner=outgoing_scan.Scanner(NO_PRIVATE_TERMS),
    )
    assert scan.clean, "the outgoing scan was expected to be blind to the ref namespace"

    report = inspect_namespace(repo, public_ref="refs/heads/main")
    assert not report.clean
    finding = next(f for f in report.findings if f.refname == "refs/notes/chatter")
    assert "invisible to git log" in finding.reason
    assert "observer@chatter.local" in finding.identity


def test_an_agent_worktree_branch_inside_the_repository_is_refused(repo):
    """EC-X's second instance: a read-only reviewer's worktree ref."""
    _git(repo, "branch", "worktree-agent-1234")
    report = inspect_namespace(repo, public_ref="refs/heads/main")
    assert any(f.refname == "refs/heads/worktree-agent-1234" for f in report.findings)


def test_a_recovery_branch_retained_through_implementation_is_refused(repo):
    _git(repo, "branch", "recovery/pre-rewrite-backup")
    report = inspect_namespace(repo, public_ref="refs/heads/main")
    assert any("recovery" in f.refname for f in report.findings)


def test_an_unrecognised_namespace_is_reported_rather_than_ignored(repo):
    """The case the gate exists for: a namespace nobody anticipated."""
    _git(repo, "update-ref", "refs/inventedbysomeone/x", "HEAD")
    report = inspect_namespace(repo, public_ref="refs/heads/main")
    finding = next(f for f in report.findings if f.refname == "refs/inventedbysomeone/x")
    assert "not a namespace this gate recognises" in finding.reason


def test_the_allowlist_is_a_declaration_not_a_hardcoded_set(repo):
    """A project publishing only main must not silently publish every branch."""
    _git(repo, "branch", "integration")
    report = inspect_namespace(
        repo, public_ref="refs/heads/main", publishable=("refs/heads/main",)
    )
    assert any(f.refname == "refs/heads/integration" for f in report.findings)


def test_reachability_from_the_public_ref_is_measured_not_assumed(repo):
    """Safety never rests on how notes refs 'normally' behave."""
    _add_notes_ref(repo)
    report = inspect_namespace(repo, public_ref="refs/heads/main")
    finding = next(f for f in report.findings if f.refname == "refs/notes/chatter")
    assert finding.reachable_from_public is False
    assert "not reachable from the public ref" in report.render()


# --- authorship --------------------------------------------------------------

def test_an_undeclared_author_on_the_public_ref_is_reported(repo):
    _git(
        repo, "-c", "user.name=Somebody Else", "-c", "user.email=other@example.invalid",
        "commit", "--quiet", "--allow-empty", "-m", "an empty commit",
    )
    report = inspect_namespace(
        repo, public_ref="refs/heads/main",
        human_identities=("Lorenzo <human@example.invalid>",),
    )
    assert any("not a declared human author" in item for item in report.identity_findings)


def test_the_declared_author_alone_produces_no_identity_finding(repo):
    report = inspect_namespace(
        repo, public_ref="refs/heads/main",
        human_identities=("Lorenzo <human@example.invalid>",),
    )
    assert report.identity_findings == []


# --- (b) config read with origins -------------------------------------------

def test_notes_configuration_is_reported_with_the_file_it_came_from(repo):
    """Reported, never concluded from.

    Two sessions inferred causation from exactly these keys being present. An
    intervention test falsified it: with the config removed and no amend or
    rebase performed, the refs still reappeared.
    """
    _git(repo, "config", "notes.rewriteRef", "refs/notes/rewrite-analytics")
    report = inspect_namespace(repo, public_ref="refs/heads/main")
    assert any("notes.rewriteref" in note.lower() for note in report.config_notes)
    assert any(".git/config" in note for note in report.config_notes)


# --- (e) the push form -------------------------------------------------------

def test_the_supported_form_is_accepted():
    assert check_push_command("git push origin refs/heads/main:refs/heads/main") == []


@pytest.mark.parametrize(
    "command",
    [
        "git push --mirror origin",
        "git push --all origin",
        "git push origin refs/*:refs/*",
        "git push origin",
        "git push",
        "git push --tags origin",
        "git push --follow-tags origin refs/heads/main:refs/heads/main",
    ],
)
def test_every_form_that_carries_more_than_one_named_branch_is_refused(command):
    """Named mechanically rather than described, so the check cannot drift."""
    assert check_push_command(command), f"{command!r} was accepted"


def test_a_refspec_naming_an_undeclared_branch_is_refused():
    problems = check_push_command(
        "git push origin refs/heads/integration:refs/heads/integration",
        publishable_branches=("refs/heads/main",),
    )
    assert any("not a declared publishable ref" in problem for problem in problems)


def test_the_explicit_refspec_is_safe_regardless_of_what_the_namespace_holds():
    """Why the structural form beats cleanup.

    A cleanup step performed minutes earlier is a race against a writer that
    re-creates refs in under a minute. This form cannot carry `refs/notes/*` at
    all, so it does not depend on winning that race.
    """
    assert check_push_command("git push origin refs/heads/main:refs/heads/main") == []


# --- (f) the remote postcondition, failing closed ---------------------------

def test_an_unreadable_remote_is_a_failure_not_an_absence_of_findings(repo):
    problems = verify_remote(repo, "nonexistent-remote", expected={"refs/heads/main": ""})
    assert problems
    assert "could not be read" in problems[0]


def test_an_unexpected_ref_on_the_remote_fails_the_postcondition(tmp_path, repo):
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--quiet", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "--quiet", "origin", "refs/heads/main:refs/heads/main")
    _git(repo, "push", "--quiet", "origin", "refs/heads/main:refs/heads/leaked")

    problems = verify_remote(repo, "origin", expected={"refs/heads/main": ""})
    assert any("unexpected ref refs/heads/leaked" in problem for problem in problems)


def test_a_remote_matching_exactly_what_was_published_passes(tmp_path, repo):
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--quiet", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "--quiet", "origin", "refs/heads/main:refs/heads/main")
    assert verify_remote(repo, "origin", expected={"refs/heads/main": ""}) == []


def test_a_missing_expected_ref_fails_the_postcondition(tmp_path, repo):
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--quiet", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    problems = verify_remote(repo, "origin", expected={"refs/heads/main": ""})
    assert any("does not carry refs/heads/main" in problem for problem in problems)


def test_a_notes_ref_reaches_the_remote_under_a_mirror_push(tmp_path, repo):
    """The consequence the refspec rule prevents, demonstrated rather than asserted."""
    _add_notes_ref(repo)
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--quiet", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "--quiet", "--mirror", "origin")

    problems = verify_remote(repo, "origin", expected={"refs/heads/main": ""})
    assert any("refs/notes/chatter" in problem for problem in problems)


def test_the_explicit_refspec_leaves_the_notes_ref_behind(tmp_path, repo):
    """The positive half of the same demonstration."""
    _add_notes_ref(repo)
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--quiet", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "--quiet", "origin", "refs/heads/main:refs/heads/main")

    assert verify_remote(repo, "origin", expected={"refs/heads/main": ""}) == []


# --- fails closed ------------------------------------------------------------

def test_a_namespace_that_cannot_be_enumerated_is_not_clean(tmp_path):
    """A check that could not be performed must never render as one that passed."""
    report = inspect_namespace(tmp_path / "not-a-repository", public_ref="refs/heads/main")
    assert not report.clean
    assert report.could_not_check
    assert "COULD NOT CHECK" in report.render()


def test_the_default_allowlist_does_not_silently_include_notes():
    assert "refs/notes/*" not in publication_gate.DEFAULT_PUBLISHABLE_REFS
