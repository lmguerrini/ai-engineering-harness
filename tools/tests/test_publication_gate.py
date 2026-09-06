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
    assert "outside the declared publishable allowlist" in finding.reason


def test_a_nested_feature_branch_is_covered_by_the_branch_glob(repo):
    """Ref globs follow git, not gitignore.

    In a refspec `*` crosses `/`, so `refs/heads/*` covers
    `refs/heads/feature/x` — which is what a push with that refspec would
    actually carry. Borrowing the filesystem path matcher would report every nested
    branch as an unrecognised namespace: wrong, and noisy enough to train a
    reader straight past the findings that matter.
    """
    _git(repo, "branch", "feature/example-feature")
    report = inspect_namespace(repo, public_ref="refs/heads/main")
    assert all("feature/example-feature" not in f.refname for f in report.findings)


def test_a_project_publishing_one_branch_still_flags_the_others(repo):
    """The narrower declaration must remain expressible."""
    _git(repo, "branch", "feature/example-feature")
    report = inspect_namespace(
        repo, public_ref="refs/heads/main", publishable=("refs/heads/main",)
    )
    assert any(f.refname == "refs/heads/feature/example-feature" for f in report.findings)


def test_the_allowlist_is_a_declaration_not_a_hardcoded_set(repo):
    """A project publishing only main must not silently publish every branch."""
    _git(repo, "branch", "integration")
    report = inspect_namespace(
        repo, public_ref="refs/heads/main", publishable=("refs/heads/main",)
    )
    assert any(f.refname == "refs/heads/integration" for f in report.findings)


def test_containment_is_measured_not_assumed_and_the_alarm_lands_on_the_alarming_case(repo):
    """Safety never rests on how notes refs 'normally' behave — and the
    rendering must shout at the ref that carries extra objects, not at the one
    that does not.

    Rendering `REACHABLE FROM THE PUBLIC REF` in capitals and `not reachable`
    in lower case would invert the emphasis: a ref already contained in the
    public ref adds no object to the push, and a ref outside it is the one
    holding material nobody reviewed.
    """
    _add_notes_ref(repo)
    _git(repo, "branch", "merged-already")
    report = inspect_namespace(
        repo, public_ref="refs/heads/main", publishable=("refs/heads/main",)
    )

    notes = next(f for f in report.findings if f.refname == "refs/notes/chatter")
    assert notes.contained_in_public is False

    merged = next(f for f in report.findings if f.refname == "refs/heads/merged-already")
    assert merged.contained_in_public is True

    rendered = report.render()
    assert "CARRIES OBJECTS THE PUBLIC REF DOES NOT" in rendered
    assert "already contained in the public ref" in rendered


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


# --- falsification: every form the RP2.1.0 check accepted -------------------
#
# Each of these was reproduced against the previous implementation and returned
# `[]`, which the CLI rendered as "an explicit single-branch refspec, which
# cannot carry refs/notes/*" — a sentence about a command that was not being
# run. The check enumerated bad forms; a blacklist passes everything its author
# did not think of. RP2.1.1 replaced it with the single good form.

@pytest.mark.parametrize(
    "command, why",
    [
        ("git log refs/heads/main:refs/heads/main", "any command at all, given a refspec-shaped token"),
        ("rm -rf / refs/heads/main:refs/heads/main", "not even a git command"),
        ("git fetch origin refs/heads/main:refs/heads/main", "a git command that is not push"),
        ("", "an empty command"),
        ("   ", "whitespace"),
        ("git push origin refs/heads/main:refs/heads/main refs/heads/secret:refs/heads/secret",
         "a second refspec publishes a ref nobody judged"),
        ("git push origin refs/heads/main:refs/heads/other",
         "destination differs from source, so the remote carries a name nobody reviewed"),
        ("git push origin refs/heads/main:refs/heads/main --receive-pack=/tmp/evil",
         "a trailing option changes what runs on the far side"),
        ("git push origin refs/heads/main:refs/heads/main extra-token",
         "an extra positional alters the publication set"),
        ("git push refs/heads/main:refs/heads/main", "no remote named at all"),
        ("git push origin second-remote refs/heads/main:refs/heads/main", "two remotes"),
        ("git push --force origin refs/heads/main:refs/heads/main", "an option nobody declared"),
        ("git push origin refs/tags/v1:refs/tags/v1", "a tag is not a branch refspec"),
        ("git push origin main:main", "abbreviated names are not full refs"),
    ],
)
def test_every_form_the_previous_check_accepted_is_refused(command, why):
    assert check_push_command(
        command, publishable_branches=publication_gate.DEFAULT_PUBLISHABLE_REFS
    ), f"{command!r} was accepted ({why})"


def test_the_default_allowlist_does_not_rescue_an_extra_refspec():
    """The CLI's default is `refs/heads/*`, which admits any branch.

    The previous check only ever compared a refspec's *source* against the
    allowlist, so under the default every additional refspec passed. Testing
    with a narrowed allowlist would have hidden that.
    """
    problems = check_push_command(
        "git push origin refs/heads/main:refs/heads/main refs/heads/recovery/x:refs/heads/recovery/x",
        publishable_branches=publication_gate.DEFAULT_PUBLISHABLE_REFS,
    )
    assert any("exactly one" in problem for problem in problems)


def test_the_remote_can_be_pinned():
    assert check_push_command(
        "git push origin refs/heads/main:refs/heads/main", expected_remote="origin"
    ) == []
    problems = check_push_command(
        "git push attacker refs/heads/main:refs/heads/main", expected_remote="origin"
    )
    assert any("expected 'origin'" in problem for problem in problems)


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

def _head(repo, ref="refs/heads/main"):
    return subprocess.run(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
        cwd=str(repo), capture_output=True, text=True, check=True,
    ).stdout.strip()


def test_an_expectation_with_no_revision_is_refused(repo):
    """The RP2.1.0 CLI passed exactly this, and every caller inherited it.

    "Does a ref with that name exist" is a question a remote still carrying
    last week's commit answers yes to, so the postcondition — the *only*
    observation of what actually happened, the reason the other three checks
    are not enough — was satisfied by a stale remote.
    """
    problems = verify_remote(repo, "origin", expected={"refs/heads/main": ""})
    assert any("carries no revision" in problem for problem in problems)


def test_a_stale_remote_fails_the_postcondition(tmp_path, repo):
    """The case the empty expectation could not see, end to end."""
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--quiet", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "--quiet", "origin", "refs/heads/main:refs/heads/main")
    stale = _head(repo)

    (repo / "later.txt").write_text("a commit the remote never received\n")
    _git(repo, "add", "later.txt")
    _git(repo, "commit", "--quiet", "-m", "later")
    current = _head(repo)
    assert current != stale

    problems = verify_remote(repo, "origin", expected={"refs/heads/main": current})
    assert any("on the remote, expected" in problem for problem in problems)


def test_an_unreadable_remote_is_a_failure_not_an_absence_of_findings(repo):
    problems = verify_remote(repo, "nonexistent-remote", expected={"refs/heads/main": _head(repo)})
    assert problems
    assert "could not be read" in problems[0]


def test_an_unexpected_ref_on_the_remote_fails_the_postcondition(tmp_path, repo):
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--quiet", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "--quiet", "origin", "refs/heads/main:refs/heads/main")
    _git(repo, "push", "--quiet", "origin", "refs/heads/main:refs/heads/leaked")

    problems = verify_remote(repo, "origin", expected={"refs/heads/main": _head(repo)})
    assert any("unexpected ref refs/heads/leaked" in problem for problem in problems)


def test_a_remote_matching_exactly_what_was_published_passes(tmp_path, repo):
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--quiet", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "--quiet", "origin", "refs/heads/main:refs/heads/main")
    assert verify_remote(repo, "origin", expected={"refs/heads/main": _head(repo)}) == []


def test_a_missing_expected_ref_fails_the_postcondition(tmp_path, repo):
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--quiet", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    problems = verify_remote(repo, "origin", expected={"refs/heads/main": _head(repo)})
    assert any("does not carry refs/heads/main" in problem for problem in problems)


def test_a_notes_ref_reaches_the_remote_under_a_mirror_push(tmp_path, repo):
    """The consequence the refspec rule prevents, demonstrated rather than asserted."""
    _add_notes_ref(repo)
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--quiet", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "--quiet", "--mirror", "origin")

    problems = verify_remote(repo, "origin", expected={"refs/heads/main": _head(repo)})
    assert any("refs/notes/chatter" in problem for problem in problems)


def test_the_explicit_refspec_leaves_the_notes_ref_behind(tmp_path, repo):
    """The positive half of the same demonstration."""
    _add_notes_ref(repo)
    remote = tmp_path / "remote.git"
    _git(repo, "init", "--quiet", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "--quiet", "origin", "refs/heads/main:refs/heads/main")

    assert verify_remote(repo, "origin", expected={"refs/heads/main": _head(repo)}) == []


# --- fails closed ------------------------------------------------------------

def test_a_namespace_that_cannot_be_enumerated_is_not_clean(tmp_path):
    """A check that could not be performed must never render as one that passed."""
    report = inspect_namespace(tmp_path / "not-a-repository", public_ref="refs/heads/main")
    assert not report.clean
    assert report.could_not_check
    assert "COULD NOT CHECK" in report.render()


def test_the_default_allowlist_does_not_silently_include_notes():
    assert "refs/notes/*" not in publication_gate.DEFAULT_PUBLISHABLE_REFS


# --- EC-C: the explanation must be true, not merely safe ---------------------
#
# The verdict was already right — every ref below is refused. What was wrong was
# the *sentence*, and a gate is read by people who act on its sentences.
# Reproduced against frozen 2.1.1: a blob ref reported "CARRIES OBJECTS THE
# PUBLIC REF DOES NOT" as a fact although the ancestry call had exited 128, and
# an annotated tag reported "carries no extra object" although the tag object is
# an extra object carrying a tagger identity.


def _finding(report, refname):
    return next(f for f in report.findings if f.refname == refname)


def test_an_annotated_tag_is_not_reported_as_carrying_no_extra_object(repo):
    """`merge-base` peels a tag to its commit, so the old boolean answered
    "contained" — in the reassuring direction — for an object the public ref
    does not carry and which holds a tagger name, email and message."""
    _git(repo, "tag", "-a", "v1", "-m", "annotated")
    report = inspect_namespace(repo, public_ref="refs/heads/main", publishable=("refs/heads/main",))

    finding = _finding(report, "refs/tags/v1")
    assert finding.objecttype == "tag"
    assert "ANNOTATED TAG" in finding.sentence()
    assert "carries no extra object" not in finding.sentence()
    assert not report.clean


def test_a_ref_naming_a_blob_reports_that_containment_does_not_apply(repo):
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"], cwd=str(repo), input=b"private payload",
        capture_output=True, check=True,
    ).stdout.decode().strip()
    _git(repo, "update-ref", "refs/private/blob", blob)

    report = inspect_namespace(repo, public_ref="refs/heads/main", publishable=("refs/heads/main",))
    finding = _finding(report, "refs/private/blob")
    assert finding.objecttype == "blob"
    assert finding.containment == publication_gate.NOT_APPLICABLE
    assert "containment does not apply" in finding.sentence()
    assert "CARRIES OBJECTS THE PUBLIC REF DOES NOT" not in finding.sentence()
    assert not report.clean


def test_a_ref_naming_a_tree_reports_that_containment_does_not_apply(repo):
    tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=str(repo),
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    _git(repo, "update-ref", "refs/private/tree", tree)

    report = inspect_namespace(repo, public_ref="refs/heads/main", publishable=("refs/heads/main",))
    assert _finding(report, "refs/private/tree").containment == publication_gate.NOT_APPLICABLE


def test_an_ordinary_branch_still_reports_containment_both_ways(repo):
    """The repair must not blur the two states that were already correct."""
    _git(repo, "branch", "contained-elsewhere")
    _git(repo, "checkout", "--quiet", "-b", "carries-extra")
    (repo / "extra.txt").write_text("extra\n")
    _git(repo, "add", "extra.txt")
    _git(repo, "commit", "--quiet", "-m", "extra")
    _git(repo, "checkout", "--quiet", "main")

    report = inspect_namespace(repo, public_ref="refs/heads/main", publishable=("refs/heads/main",))
    assert _finding(report, "refs/heads/contained-elsewhere").containment == publication_gate.CONTAINED
    assert _finding(report, "refs/heads/carries-extra").containment == publication_gate.NOT_CONTAINED
    assert "carries no extra object" in _finding(report, "refs/heads/contained-elsewhere").sentence()
    assert "CARRIES OBJECTS" in _finding(report, "refs/heads/carries-extra").sentence()


def test_the_backward_compatible_field_is_true_only_for_contained(repo):
    """`contained_in_public` survives for 2.1.1 callers, and is deliberately
    false for NOT_APPLICABLE and UNKNOWN: neither is a statement that the ref
    carries nothing extra."""
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"], cwd=str(repo), input=b"x",
        capture_output=True, check=True,
    ).stdout.decode().strip()
    _git(repo, "update-ref", "refs/private/blob", blob)
    _git(repo, "branch", "contained-elsewhere")

    report = inspect_namespace(repo, public_ref="refs/heads/main", publishable=("refs/heads/main",))
    assert _finding(report, "refs/heads/contained-elsewhere").contained_in_public is True
    assert _finding(report, "refs/private/blob").contained_in_public is False


def test_an_unanswerable_containment_question_renders_as_unknown(repo, monkeypatch):
    """`NOT_APPLICABLE` was pinned and `UNKNOWN` was not — an independent audit
    mutated the branch to `CONTAINED` and the suite passed, which means the
    report would have printed "carries no extra object" for a question git could
    not answer."""
    import gitread

    _git(repo, "branch", "some-branch")

    def refuse(*args, **kwargs):
        raise gitread.GitRefusal("git could not answer")

    monkeypatch.setattr(gitread, "is_ancestor", refuse)
    report = inspect_namespace(repo, public_ref="refs/heads/main", publishable=("refs/heads/main",))

    finding = _finding(report, "refs/heads/some-branch")
    assert finding.containment == publication_gate.UNKNOWN
    assert "CONTAINMENT UNKNOWN" in finding.sentence()
    assert "carries no extra object" not in finding.sentence()
    assert report.could_not_check
    assert not report.clean


def test_a_boolean_in_the_containment_field_is_refused():
    """RP2.2 changed the 4th positional from `bool` to one of four strings. A
    caller written against the older signature would have stored `True` and
    silently reported the UNKNOWN sentence."""
    with pytest.raises(ValueError):
        publication_gate.RefFinding("refs/heads/x", "reason", "identity", True)
    with pytest.raises(ValueError):
        publication_gate.RefFinding("refs/heads/x", "reason", "identity", "probably")


# --- the postcondition that could not cross a boundary --------------------------
#
# RP3-16. `gitread` refuses every protocol, correctly: nothing else in the
# toolbelt has business leaving the machine. The one check that exists TO leave
# it — the single observation of what a push actually did — was disabled by the
# same setting, and was measured non-functional on every real remote.

import subprocess as _subprocess

import gitread as _gitread
from errors import (
    GitRefusal as _GitRefusal,
    IntegrityError as _IntegrityError,
    PreconditionError as _PreconditionError,
)


def _config_pairs(environment):
    count = int(environment["GIT_CONFIG_COUNT"])
    return {environment[f"GIT_CONFIG_KEY_{i}"]: environment[f"GIT_CONFIG_VALUE_{i}"]
            for i in range(count)}


def test_every_ordinary_read_still_refuses_every_protocol():
    """The negative control, and it is the point of the whole exercise. A
    rehearsal that only proved the postcondition works would hide a global
    widening."""
    pairs = _config_pairs(_gitread._environment(None))
    assert pairs["protocol.allow"] == "never"
    assert not any(key.startswith("protocol.") and key.endswith(".allow")
                   and key not in ("protocol.allow", "protocol.file.allow")
                   for key in pairs), sorted(pairs)


def test_the_widening_names_transports_beside_the_standing_refusal():
    """`protocol.allow = never` is not relaxed; specific protocols are added
    beside it, and Git consults the specific key first. Everything unnamed
    stays refused even inside the widened operation."""
    pairs = _config_pairs(_gitread._environment(None, ("ssh", "https")))
    assert pairs["protocol.allow"] == "never"
    assert pairs["protocol.ssh.allow"] == "always"
    assert pairs["protocol.https.allow"] == "always"
    assert "protocol.ftp.allow" not in pairs


def test_a_transport_this_module_will_not_enable_is_refused_by_name():
    """Free-form protocol names would let a caller re-enable an unreviewed
    transport by spelling it."""
    with pytest.raises(_IntegrityError) as caught:
        _gitread._environment(None, ("ftp",))
    assert "ssh" in caught.value.render() and "ftp" in caught.value.render()


def test_the_postcondition_declares_only_the_transports_it_needs():
    assert set(publication_gate.REMOTE_VERIFICATION_TRANSPORTS) == {"ssh", "https", "file"}


def test_the_hardening_is_what_refused_ssh_and_the_scoped_widening_is_what_lifts_it():
    """The reproduction and its repair, side by side, at the layer where the
    difference lives.

    Asserted on the transport refusal rather than on whatever the network says
    next: `.invalid` never resolves, but a resolver that wildcard-answered
    would make a message-matching test lie. What must change is that Git stops
    refusing the protocol; what happens after that is the network's business.
    """
    import subprocess as sub
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        sub.run(["git", "init", "--quiet"], cwd=directory, check=True, capture_output=True)
        hardened = _gitread.probe(directory, "ls-remote", "ssh://git@no-such-host.invalid/x.git",
                                  negative_statuses=())
        widened = _gitread.probe(directory, "ls-remote", "ssh://git@no-such-host.invalid/x.git",
                                 negative_statuses=(),
                                 allow_transports=publication_gate.REMOTE_VERIFICATION_TRANSPORTS)

    assert "transport 'ssh' not allowed" in hardened.detail, hardened.detail
    assert "transport 'ssh' not allowed" not in widened.detail, widened.detail
    # And not the OTHER non-functional shape: emptying `core.sshCommand` made
    # Git try to run the empty string, so enabling the protocol alone moved the
    # failure from "not allowed" to "unable to fork" without restoring anything.
    assert "unable to fork" not in widened.detail, widened.detail
    assert "cannot run :" not in widened.detail, widened.detail


def test_the_ssh_command_neutralisation_is_lifted_only_where_ssh_is_enabled():
    """`core.sshCommand = ""` does not mean "no ssh command" — Git runs the
    empty string. This module recorded that exact lesson for `diff.external`
    and set the ssh key to empty anyway."""
    ordinary = _config_pairs(_gitread._environment(None))
    assert ordinary["core.sshCommand"] == "", "the neutralisation must stand everywhere else"

    widened = _config_pairs(_gitread._environment(None, ("ssh",)))
    assert "core.sshCommand" not in widened, (
        "absent, not empty: Git falls through to its own default, and every ambient GIT_* "
        "variable is already stripped"
    )

    https_only = _config_pairs(_gitread._environment(None, ("https",)))
    assert https_only["core.sshCommand"] == "", "a transport that needs no external program lifts nothing"


def test_the_postcondition_says_why_a_remote_could_not_be_read(tmp_path):
    """Two failures with opposite remedies arrived as one sentence — "git
    invocation failed" — so a refused transport and a dead host were the same
    finding. One is a setting this pack controls."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True, capture_output=True)
    problems = publication_gate.verify_remote(
        repo, f"file://{tmp_path / 'absent.git'}", expected={"refs/heads/main": "a" * 40})
    assert problems
    assert problems[0].rstrip().rstrip(":") != problems[0].split(":")[0], problems[0]
    assert len(problems[0]) > len("the remote '' could not be read, so publication is unverified: "
                                  "git invocation failed"), problems[0]
    assert "does not appear to be a git repository" in problems[0] or "not a git repo" in problems[0].lower(), problems[0]


def test_the_postcondition_itself_crosses_a_non_file_transport(tmp_path):
    """The mechanism working proves nothing until the caller uses it.

    A control with no caller is not implemented, and this is the assertion that
    fails when `verify_remote` is reverted to the hardened environment — the
    two tests above pass unchanged in that case, because they exercise the
    layer below.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True, capture_output=True)
    problems = publication_gate.verify_remote(
        repo, "ssh://git@no-such-host.invalid/x.git",
        expected={"refs/heads/main": "a" * 40},
    )
    assert problems and "publication is unverified" in problems[0]
    assert "transport 'ssh' not allowed" not in problems[0], (
        "the postcondition is still being refused by the hardening rather than reaching the "
        "remote: " + problems[0]
    )
    assert "unable to fork" not in problems[0], problems[0]


def test_a_file_remote_still_verifies_after_the_change(tmp_path):
    """Unchanged behaviour on the one transport that already worked."""
    origin = tmp_path / "origin.git"
    _subprocess.run(["git", "init", "--bare", "--quiet", str(origin)], check=True, capture_output=True)
    work = tmp_path / "work"
    work.mkdir()
    for command in (["git", "init", "--quiet", "--initial-branch", "main"],
                    ["git", "config", "user.email", "t@example.invalid"],
                    ["git", "config", "user.name", "T"],
                    ["git", "config", "commit.gpgsign", "false"]):
        _subprocess.run(command, cwd=work, check=True, capture_output=True)
    (work / "a.txt").write_text("x\n")
    _subprocess.run(["git", "add", "a.txt"], cwd=work, check=True, capture_output=True)
    _subprocess.run(["git", "commit", "--quiet", "-m", "first"], cwd=work, check=True, capture_output=True)
    head = _subprocess.run(["git", "rev-parse", "HEAD"], cwd=work, capture_output=True,
                           text=True, check=True).stdout.strip()
    _subprocess.run(["git", "push", "--quiet", f"file://{origin}",
                     "refs/heads/main:refs/heads/main"], cwd=work, check=True, capture_output=True)

    assert publication_gate.verify_remote(
        work, f"file://{origin}",
        expected=publication_gate.expectation_from_refspec("refs/heads/main:refs/heads/main", head),
    ) == []


def test_an_unreadable_remote_still_fails_closed_in_the_same_words(tmp_path):
    """The property that must not be lost while the transport is fixed."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True, capture_output=True)
    problems = publication_gate.verify_remote(
        repo, f"file://{tmp_path / 'no-such-repository.git'}",
        expected={"refs/heads/main": "b" * 40},
    )
    assert problems and "publication is unverified" in problems[0]


# --- the expectation set, derived rather than typed ---------------------------------


def test_the_expectation_is_derived_from_the_authorised_refspec():
    """Never hand-typed. A hand-authored expectation set is the shape the
    checker-hygiene rules refuse in terms, and the refspec is a mapping that
    already holds the answer."""
    head = "c" * 40
    assert publication_gate.expectation_from_refspec(
        "refs/heads/main:refs/heads/main", head) == {"refs/heads/main": head}
    assert publication_gate.expectation_from_refspec(
        "refs/heads/work:refs/heads/release", head) == {"refs/heads/release": head}


def test_a_push_form_with_no_derivable_expectation_is_refused_not_guessed():
    for form in ("--mirror", "refs/heads/*:refs/heads/*", "main:main", ""):
        with pytest.raises(_PreconditionError):
            publication_gate.expectation_from_refspec(form, "d" * 40)


def test_an_expectation_without_the_exact_revision_is_refused():
    """A remote still carrying last week's commit under the right name would
    otherwise verify clean."""
    with pytest.raises(_PreconditionError):
        publication_gate.expectation_from_refspec("refs/heads/main:refs/heads/main", "abc123")


def test_remote_verification_refuses_a_repository_supplied_ssh_program(tmp_path):
    """O3. The reported path, end to end. `verify_remote` enables `ssh`, which
    removes the `core.sshCommand` neutralisation; a repository configuring that
    key had its program executed and could answer the verification with a
    fabricated ref advertisement — a clean publication result computed from the
    repository's own claim about itself.
    """
    repo = tmp_path / "pubssh"
    repo.mkdir()
    for args in (("init", "-q", "-b", "main"), ("config", "user.email", "t@e.invalid"),
                 ("config", "user.name", "T")):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    (repo / "f.txt").write_text("hi\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True, capture_output=True)

    marker = tmp_path / "MARKER"
    program = tmp_path / "ssh.py"
    program.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        f"pathlib.Path({str(marker)!r}).write_text('ran')\n"
        "sys.stdout.write('0' * 40 + chr(9) + 'refs/heads/main' + chr(10))\n")
    program.chmod(0o755)
    subprocess.run(["git", "config", "core.sshCommand", str(program)],
                   cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", "ssh://example.invalid/x.git"],
                   cwd=repo, check=True, capture_output=True)

    with pytest.raises(_gitread.IntegrityError):
        verify_remote(repo, "origin", expected={"refs/heads/main": "0" * 40})
    assert not marker.exists(), "the repository's own ssh program was executed"


def _seeded(path):
    path.mkdir(parents=True, exist_ok=True)
    for args in (("init", "-q", "-b", "main"), ("config", "user.email", "t@e.invalid"),
                 ("config", "user.name", "T")):
        subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)
    (path / "f.txt").write_text("hi\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=path, check=True, capture_output=True)
    return path


def test_remote_verification_refuses_a_repository_re_enabled_transport(tmp_path):
    """O5. The reported path. A repository that re-enables a transport and names
    a program over it had that program run by the publication gate's own remote
    verification — and a program that speaks the protocol can answer the
    postcondition, so the repository being verified supplies its own result.
    """
    repo = _seeded(tmp_path / "reenable_pub")
    marker = tmp_path / "MARKER"
    program = tmp_path / "prog.sh"
    program.write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n")
    program.chmod(0o755)
    subprocess.run(["git", "config", "protocol.ext.allow", "always"],
                   cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", f"ext::{program} %S"],
                   cwd=repo, check=True, capture_output=True)
    verify_remote(repo, "origin", expected={"refs/heads/main": "0" * 40})
    assert not marker.exists(), "the repository's own program answered its verification"


def test_remote_verification_still_reads_an_enabled_transport(tmp_path):
    """O4. The bound. Pinning must not reach the transport the caller deliberately
    enabled, or the one observation of what a push actually did goes away — which
    is the whole reason the transport exception exists."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", "."],
                   cwd=origin, check=True, capture_output=True)
    repo = _seeded(tmp_path / "pusher")
    # The repository declares the SAME transport the caller enables. Without
    # this the fixture proves nothing: the pinning only ever touches names the
    # repository itself mentions, so a version that pinned the enabled transport
    # too would leave an untouched fixture passing. Mutation caught exactly that.
    subprocess.run(["git", "config", "protocol.file.allow", "always"],
                   cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", f"file://{origin}"],
                   cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "push", "-q", "origin", "main"],
                   cwd=repo, check=True, capture_output=True)
    head = subprocess.run(["git", "rev-parse", "refs/heads/main"], cwd=repo,
                          capture_output=True, text=True, check=True).stdout.strip()
    assert verify_remote(repo, "origin", expected={"refs/heads/main": head}) == []
