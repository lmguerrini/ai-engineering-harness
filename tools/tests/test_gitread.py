"""gitread against a throwaway repository built fresh in a tmp dir.

No mocking: every function under test shells out to a real `git`, so the
throwaway repo is the fixture.
"""

import json
import inspect
import itertools
import os
import random
import stat
import subprocess
import time
from pathlib import Path

import pytest

import gitread
from submodule_no_child import compose as _compose
from submodule_no_child import has_gitlinks as _has_gitlinks
from errors import GitRefusal


def _git(repo, *args, env=None):
    command = ["git", *args]
    result = subprocess.run(
        command, cwd=str(repo), capture_output=True, text=True, check=True, env=env,
    )
    return result.stdout


@pytest.fixture
def repo(tmp_path):
    directory = tmp_path / "throwaway"
    directory.mkdir()
    _git(directory, "init", "--quiet", "--initial-branch", "main")
    _git(directory, "config", "user.name", "Throwaway Tester")
    _git(directory, "config", "user.email", "tester@example.invalid")
    _git(directory, "config", "commit.gpgsign", "false")
    (directory / "file.txt").write_text("hello world\n")
    _git(directory, "add", "file.txt")
    _git(directory, "commit", "--quiet", "-m", "first commit")
    return directory


def test_probe_answers_a_real_question(repo):
    answer = gitread.probe(repo, "rev-parse", "--verify", "HEAD")
    assert answer.answered
    assert answer.ok
    assert len(answer.value) == 40


def test_commit_message_round_trips(repo):
    head = _git(repo, "rev-parse", "HEAD").strip()
    message = gitread.commit_message(repo, head)
    assert message == "first commit\n"


def test_commit_metadata_has_full_identity(repo):
    head = _git(repo, "rev-parse", "HEAD").strip()
    metadata = gitread.commit_metadata(repo, head)
    assert metadata["author_name"] == "Throwaway Tester"
    assert metadata["author_email"] == "tester@example.invalid"
    assert metadata["committer_name"] == "Throwaway Tester"


def test_whitespace_damage_is_empty_when_clean(repo):
    assert gitread.whitespace_damage(repo) == ""


def test_whitespace_damage_detects_trailing_whitespace(repo):
    (repo / "file.txt").write_text("hello world   \n")
    _git(repo, "add", "file.txt")
    damage = gitread.whitespace_damage(repo)
    assert damage != ""
    assert "file.txt" in damage


def test_object_type_and_size(repo):
    head = _git(repo, "rev-parse", "HEAD").strip()
    assert gitread.object_type(repo, head) == "commit"
    tree = _git(repo, "rev-parse", f"{head}^{{tree}}").strip()
    assert gitread.object_type(repo, tree) == "tree"
    blob = _git(repo, "rev-parse", f"{head}:file.txt").strip()
    assert gitread.object_type(repo, blob) == "blob"
    assert gitread.object_size(repo, blob) == len("hello world\n")


def test_object_bytes_matches_file_content(repo):
    head = _git(repo, "rev-parse", "HEAD").strip()
    blob = _git(repo, "rev-parse", f"{head}:file.txt").strip()
    assert gitread.object_bytes(repo, blob) == b"hello world\n"


def test_objects_and_paths_in_outgoing_range(repo):
    first = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "second.txt").write_text("more\n")
    _git(repo, "add", "second.txt")
    _git(repo, "commit", "--quiet", "-m", "second commit")
    second = _git(repo, "rev-parse", "HEAD").strip()

    objects = gitread.objects_in_outgoing_range(repo, second, first)
    shas = {sha for sha, _path in objects}
    assert second in shas

    paths = gitread.paths_in_outgoing_range(repo, second, first)
    assert paths == ["second.txt"]


def test_paths_in_outgoing_range_with_no_baseline_lists_everything(repo):
    paths = gitread.paths_in_outgoing_range(repo, "HEAD", None)
    assert paths == ["file.txt"]


def test_tag_object_carries_its_own_message_and_tagger(repo):
    env = {**__import__("os").environ, "GIT_COMMITTER_NAME": "Throwaway Tester", "GIT_COMMITTER_EMAIL": "tester@example.invalid"}
    _git(repo, "tag", "-a", "v1", "-m", "release notes", env=env)
    tag_sha = _git(repo, "rev-parse", "v1").strip()
    tag = gitread.tag_object(repo, tag_sha)
    assert tag["message"] == "release notes\n"
    assert tag["tag"] == "v1"
    assert "Throwaway Tester" in tag["tagger"]


def test_run_refuses_a_nonexistent_repository_path(tmp_path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(GitRefusal):
        gitread._run(missing, "rev-parse", "--verify", "HEAD")


def test_run_refuses_a_nonpositive_timeout(repo):
    with pytest.raises(GitRefusal):
        gitread._run(repo, "rev-parse", "--verify", "HEAD", timeout=0)


# --- D15: an undeclared exit status is not the documented negative -----------
#
# `probe` distinguishes three outcomes and exposes `failed` for "git ran and
# could not answer". Two callers consulted only `answered`, so exit 128 arrived
# as the ordinary negative. Both reproduced against the frozen 2.1.1 baseline
# before repair.


def _repo(tmp_path, name="r"):
    root = tmp_path / name
    root.mkdir()
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
    for key, value in (("user.email", "a@b.c"), ("user.name", "T")):
        subprocess.run(["git", "config", key, value], cwd=root, check=True)
    (root / "f.txt").write_text("hi")
    subprocess.run(["git", "add", "f.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=root, check=True)
    return root


def test_an_unreadable_config_is_a_refusal_not_an_empty_repository(tmp_path):
    """The exact D7 surface: a repository whose `.git/config` cannot be parsed
    reported as having no settings at all, `notes.*` keys included."""
    root = _repo(tmp_path)
    subprocess.run(["git", "config", "notes.rewriteRef", "refs/notes/commits"], cwd=root, check=True)
    assert any(e["key"] == "notes.rewriteref" for e in gitread.config_with_origin(str(root)))

    (root / ".git" / "config").write_text("[core\nthis is not valid\n")
    with pytest.raises(GitRefusal):
        gitread.config_with_origin(str(root))


def test_ancestry_of_a_non_commit_is_a_refusal_not_a_no(tmp_path):
    """`merge-base --is-ancestor` exits 128 on a blob. Returning `False` made
    the publication gate print "CARRIES OBJECTS THE PUBLIC REF DOES NOT" as a
    fact about a question that was never answered."""
    root = _repo(tmp_path)
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"], cwd=root, input=b"payload",
        capture_output=True, check=True,
    ).stdout.decode().strip()

    with pytest.raises(GitRefusal):
        gitread.is_ancestor(str(root), blob, "refs/heads/main")


def test_ancestry_of_a_commit_still_answers_both_ways(tmp_path):
    """The repair must not turn an ordinary negative into a refusal."""
    root = _repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert gitread.is_ancestor(str(root), head, "refs/heads/main") is True

    subprocess.run(["git", "checkout", "-q", "-b", "other"], cwd=root, check=True)
    (root / "g.txt").write_text("other")
    subprocess.run(["git", "add", "g.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "other"], cwd=root, check=True)
    other = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert gitread.is_ancestor(str(root), other, "refs/heads/main") is False


# --- a refusal that cannot be constructed is not a refusal -------------------


def test_every_refusal_path_raises_a_named_refusal(tmp_path):
    """Latent in 2.1.1 and reproduced against it: both "nobody looked" paths
    passed `cause=` to a constructor whose first positional parameter is named
    `cause`, so they raised `TypeError` — which carries neither the stable code
    nor the specific cause `errors.py` promises."""
    root = _repo(tmp_path)
    with pytest.raises(GitRefusal):
        gitread.config_with_origin(str(root), timeout=1e-9)
    with pytest.raises(GitRefusal):
        gitread.is_ancestor(str(root), "a" * 40, "b" * 40, timeout=1e-9)


def test_no_tool_constructs_a_refusal_with_a_colliding_cause_keyword():
    """Mechanical, because the defect above is invisible until the path runs.

    `HxError.__init__(self, cause, **detail)` takes `cause` positionally, so any
    construction passing it again by keyword raises `TypeError` at the moment
    the refusal was supposed to be raised — the worst possible moment.
    """
    import re
    from pathlib import Path

    pattern = re.compile(
        r"(?:GitRefusal|IntegrityError|GateRefusal|PreconditionError"
        r"|CommitContractError|HxError)\([^)]*\bcause\s*="
    )
    offenders = [
        f"{path.name}:{number}"
        for path in sorted(Path(__file__).resolve().parent.parent.glob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line)
    ]
    assert not offenders, f"these constructions raise TypeError instead of a refusal: {offenders}"


def test_object_listing_paths_are_nul_safe(tmp_path):
    """The last enumeration in the toolbelt still splitting on lines, which made
    `nul_paths`' claim to cover *every* path enumeration untrue. Found by an
    independent audit. A path with a newline split one object into three."""
    root = _repo(tmp_path, "objects")
    awkward = root / "weird\nname"
    awkward.mkdir()
    (awkward / "notes.md").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "awkward"], cwd=root, check=True)

    paths = {path for _sha, path in gitread.objects_in_outgoing_range(str(root), "HEAD", None)}
    assert "weird\nname/notes.md" in paths
    assert all("\n" not in path or path.startswith("weird\nname") for path in paths)


def test_every_object_listing_entry_carries_a_full_sha(tmp_path):
    root = _repo(tmp_path, "shas")
    for sha, _path in gitread.objects_in_outgoing_range(str(root), "HEAD", None):
        assert len(sha) == 40 and all(c in "0123456789abcdef" for c in sha), sha


# --- the module carries no write verb, which is why it exists ------------------
#
# `DECISIONS.md` D2 extracted this module to leave the write verbs behind, and
# then `probe` took a verb as a parameter and put every one of them back. A
# cross-vendor auditor created `refs/heads/illicit` through the public read API.

import subprocess as _subprocess

import pytest as _pytest

from errors import GitRefusal as _GitRefusal, IntegrityError as _IntegrityError


def _scratch_repo(tmp_path):
    directory = tmp_path / "repo"
    directory.mkdir()
    for command in (["git", "init", "--quiet"],
                    ["git", "config", "user.email", "t@example.invalid"],
                    ["git", "config", "user.name", "T"],
                    ["git", "commit", "--quiet", "--allow-empty", "-m", "first"]):
        _subprocess.run(command, cwd=directory, check=True, capture_output=True)
    head = _subprocess.run(["git", "rev-parse", "HEAD"], cwd=directory,
                           capture_output=True, text=True, check=True).stdout.strip()
    return directory, head


def test_a_write_verb_is_refused_and_writes_nothing(tmp_path):
    """The reproduction, inverted.

    Raised rather than answered: `probe`'s job is to turn a Git failure into an
    answer-shaped result, so a refusal that came back as a `ProbeAnswer` would
    read as an ordinary negative and the caller would walk past it. Asserted on the filesystem as well as on the
    refusal: a check that only asserted the exception would pass even if the ref
    were created first and the exception raised afterwards."""
    directory, head = _scratch_repo(tmp_path)
    with _pytest.raises(_IntegrityError) as caught:
        gitread.probe(directory, "update-ref", "refs/heads/illicit", head, negative_statuses=())
    assert "read-only Git commands only" in caught.value.render()
    assert "update-ref" in caught.value.render()

    shown = _subprocess.run(["git", "show-ref", "refs/heads/illicit"], cwd=directory,
                            capture_output=True, text=True)
    assert shown.returncode != 0, "the ref exists; the refusal came too late to be a control"


def test_every_write_verb_anyone_would_reach_for_is_refused(tmp_path):
    """Weak on its own — every verb here is absent from the allowlist and stays
    absent, so it cannot fail while that holds, and an auditor said so. It is
    kept as the cheap half of the pair; the binding half is
    `test_every_allowlisted_verb_is_actually_read_only_in_the_forms_permitted`,
    which exercises the verbs that ARE permitted and asserts the repository is
    unchanged."""
    directory, head = _scratch_repo(tmp_path)
    for verb in ("update-ref", "commit", "push", "fetch", "clone", "gc", "reflog", "checkout",
                 "branch", "tag", "reset", "add", "rm", "filter-branch", "replace", "prune",
                 "worktree", "stash", "apply", "am", "cherry-pick", "rebase", "merge", "init"):
        with _pytest.raises(_IntegrityError):
            gitread.probe(directory, verb, negative_statuses=())


def test_every_allowlisted_verb_is_actually_read_only_in_the_forms_permitted(tmp_path):
    """A denylist has to anticipate every verb Git will ever add, and the
    failure mode of missing one is a write — so this is an allowlist. But an
    allowlist is only as good as the claim that each entry belongs on it, and
    the first version of this test asserted that 24 verbs were absent (they were,
    and stayed so) plus that every entry was lowercase, which has nothing to do
    with read-onlyness. It never touched the one allowlisted verb that writes.

    This runs each permitted verb against a scratch repository and asserts the
    repository is byte-identical afterwards.
    """
    import hashlib

    directory, head = _scratch_repo(tmp_path)

    def _fingerprint():
        digest = hashlib.sha256()
        for path in sorted(p for p in (directory / ".git").rglob("*") if p.is_file()):
            digest.update(str(path.relative_to(directory)).encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()

    safe_arguments = {
        "config": ("--list",), "bundle": ("list-heads", str(tmp_path / "absent.bundle")),
        "ls-remote": (str(directory),), "cat-file": ("-t", head), "show": (head,),
        "diff": (head,), "log": ("-1",), "rev-parse": ("HEAD",), "rev-list": ("--all",),
        "merge-base": (head, head), "show-ref": (), "status": ("--porcelain",),
        "ls-files": (), "ls-tree": (head,), "for-each-ref": (), "diff-index": (head,),
        "diff-tree": (head,), "check-ignore": ("x",), "verify-pack": (),
    }
    assert set(safe_arguments) == set(gitread.READ_ONLY_VERBS), (
        "a verb was added to the allowlist without a case here proving it does not write"
    )

    before = _fingerprint()
    for verb, arguments in sorted(safe_arguments.items()):
        try:
            gitread.probe(directory, verb, *arguments, negative_statuses=tuple(range(1, 130)))
        except Exception:
            pass  # what it answers is another test's business; what it WRITES is this one's
        assert _fingerprint() == before, f"`git {verb}` changed the repository"


def test_the_reads_this_toolbelt_actually_performs_still_work(tmp_path):
    """The other half: an allowlist that refused correct work would be found
    immediately and removed."""
    directory, head = _scratch_repo(tmp_path)
    assert gitread.probe(directory, "rev-parse", "HEAD", negative_statuses=()).value.strip() == head
    assert gitread.refs(directory)
    assert gitread.object_type(directory, head) == "commit"


def test_git_bundle_may_read_and_may_not_write(tmp_path):
    """One verb, two subcommands that read and one that writes."""
    directory, _head = _scratch_repo(tmp_path)
    with _pytest.raises(_IntegrityError) as caught:
        gitread.probe(directory, "bundle", "create", "/private/tmp/should-not-exist.bundle",
                      "HEAD", negative_statuses=())
    assert "write subcommand" in caught.value.render()
    assert not __import__("pathlib").Path("/private/tmp/should-not-exist.bundle").exists()

    answer = gitread.probe(directory, "bundle", "list-heads", "/private/tmp/absent.bundle",
                           negative_statuses=())
    assert answer.answered, "the read subcommand must still be reachable"


def test_a_caller_named_bundle_is_read_byte_for_byte(tmp_path):
    """A caller-named path is readable even when it is outside the repository.

    Reverting the caller-operand repair makes both governed bundle reads fail
    at the Seatbelt boundary before Git can open this sibling file.  The
    comparison is against real Git's bytes for both read forms, not merely
    against a successful exit status.
    """
    repo = _isolated_committed_repo(tmp_path, "bundle-capability")
    bundle = tmp_path / "outside.bundle"
    _isolated_git(repo, "bundle", "create", str(bundle), "HEAD")
    read = _sterile.build(repo)
    try:
        profile = gitread._local_profile(read, repo, tmp_path, (
            "bundle", "list-heads", str(bundle),
        ))
    finally:
        read.discard()
    assert str(bundle.resolve()) in profile, "the caller-named bundle is not a readable root"
    assert (
        f'(deny file-write* (subpath "{repo.resolve()}") '
        f'(subpath "{(repo / ".git").resolve()}"))'
    ) in profile, "the caller-readable root changed the subject write deny"

    for subcommand in ("list-heads", "verify"):
        expected = subprocess.run(
            ["git", "bundle", subcommand, str(bundle)], cwd=str(repo),
            capture_output=True, check=True,
        ).stdout
        try:
            actual = gitread._run(repo, "bundle", subcommand, str(bundle), text=False)
        except GitRefusal as refusal:
            if "local no-child barrier" in str(refusal.cause):
                pytest.skip("the host cannot execute the local Seatbelt barrier")
            raise
        assert actual == expected, f"governed bundle {subcommand} differs from real Git"


def test_a_subject_supplied_path_cannot_widen_the_local_read(tmp_path, monkeypatch):
    """A repository-controlled remote path is not a caller permission.

    Reverting the caller-operand repair makes the subject's ``remote.origin.url``
    become an allowed read root after alias resolution, and this invocation
    then returns the sibling repository's refs instead of refusing.  The raw
    caller operand is only ``origin``, so the subject-controlled path must stay
    outside the profile's private read carve-out.
    """
    repo = _isolated_committed_repo(tmp_path, "subject-path")
    remote = _isolated_committed_repo(tmp_path, "subject-controlled-remote")
    _isolated_git(repo, "remote", "add", "origin", str(remote))
    read = _sterile.build(repo)
    try:
        profile = gitread._local_profile(read, repo, tmp_path, ("ls-remote", "origin"))
    finally:
        read.discard()
    assert str(remote.resolve()) not in profile, "a subject-controlled path widened the read roots"

    # AND END TO END, THROUGH A LOCAL READ. The direct call above proves the
    # profile does not carry the subject's path; this proves the same thing on
    # the route a real caller takes. It deliberately uses a LOCAL verb: an
    # earlier form drove `ls-remote` and expected the local barrier to refuse,
    # which stopped being true once the transport verb correctly began taking
    # the transport backend. A test that can only fail while a defect exists is
    # not a test of the property.
    profiles = []
    real_profile = gitread._local_profile

    def capture_profile(*arguments, **kwargs):
        captured = real_profile(*arguments, **kwargs)
        profiles.append(captured)
        return captured

    monkeypatch.setattr(gitread, "_local_profile", capture_profile)
    gitread._run(repo, "status", "--porcelain")
    assert profiles, "a local read rendered no profile"
    assert str(remote.resolve()) not in profiles[-1], (
        "a subject-controlled path reached the read roots of a local governed read"
    )

    # WHAT THIS TEST DOES NOT PROVE, said here rather than implied by silence.
    #
    # `_run` snapshots the caller's arguments BEFORE resolving anything the
    # subject controls, and builds the profile from that snapshot. That ordering
    # currently has **no live route to exercise**: the only step that rewrites an
    # argument from subject data is remote-alias resolution, and that happens
    # only for transport verbs, which no longer render a local profile at all.
    # Moving the snapshot past resolution therefore changes no observable
    # behaviour, and a test claiming to catch it would pass either way.
    #
    # Two attempts were made and both were discarded rather than kept green: one
    # drove `ls-remote` and stopped meaning anything once the transport verb
    # correctly took the transport backend; one used a gitlink subject expecting
    # the recursion-suppression rewrite to show through, which the composition
    # path never reaches. **A test that cannot fail is worse than an absent one,
    # because it is counted.**
    #
    # The ordering is defence in depth for a route that may exist again. What
    # keeps it safe today is structural and IS pinned, in
    # `test_routing_does_not_consult_the_subject`: every transport verb takes the
    # transport backend, so no subject-resolved address can reach a local read's
    # profile. If that ever changes, this ordering becomes load-bearing and will
    # need an oracle that can actually fail.


def test_a_transport_may_only_be_enabled_for_the_verb_the_exception_is_scoped_to(tmp_path):
    """`archive --remote` is a second network read, and it was reachable through
    the generic API with ssh enabled. Found by a cross-vendor auditor."""
    directory, _head = _scratch_repo(tmp_path)
    with _pytest.raises(_IntegrityError) as caught:
        gitread.probe(directory, "archive", "--remote=ssh://git@no-such-host.invalid/x.git",
                      "HEAD", negative_statuses=(), allow_transports=("ssh",))
    rendered = caught.value.render()
    assert "archive" in rendered
    assert "ls-remote" in rendered, "the refusal must name what the exception IS scoped to"

    # And the one verb it is scoped to still crosses.
    answer = gitread.probe(directory, "ls-remote", "ssh://git@no-such-host.invalid/x.git",
                           negative_statuses=(), allow_transports=("ssh",))
    assert "transport 'ssh' not allowed" not in (answer.detail or "")


def test_the_transport_verbs_are_exactly_the_one_the_postcondition_needs():
    assert gitread.TRANSPORT_VERBS == frozenset({"ls-remote"})


def test_a_callers_explicit_local_path_remains_a_readable_ls_remote_target(tmp_path):
    """Direct local paths need Git's file implementation, but no subject policy.

    The sterile configuration correctly denies transports by default.  That
    accidentally denied the ordinary ``ls-remote /path/to/repository`` form as
    well, despite the path being supplied by the caller.  Compare the complete
    answer with real Git so options and ref formatting stay Git's semantics.
    Reverting the repository-operand exception makes both direct calls refuse
    the file transport instead of returning these byte-identical answers.
    """
    remote = _isolated_committed_repo(tmp_path, "remote")
    reader = _isolated_committed_repo(tmp_path, "reader")

    for address in (str(remote), os.path.relpath(remote, reader)):
        expected = _isolated_real_git(reader, "ls-remote", address)
        assert expected.returncode == 0, expected.stderr
        assert gitread._run(reader, "ls-remote", address) == expected.stdout


def test_no_argument_can_change_whether_a_transport_is_permitted(tmp_path):
    """The transport permission is CONSTANT, and constant is the whole point.

    A repair once enabled the file transport only when the caller's operand
    looked like a local path. A policy that varies is a policy an argument can
    steer: an unrelated absolute argument standing beside a remote NAME turned it
    on, and Git then resolved that name from the SUBJECT's `remote.<name>.url`.
    The control call refused with `transport 'file' not allowed`; the same call
    with one extra argument answered. A blind reader walked through it in an hour.

    So this does not assert an outcome, it asserts INVARIANCE: the same operand
    must get the same permission however many incidental arguments follow it.
    Under the varying policy the two answers differ and this fails.
    """
    remote = _isolated_committed_repo(tmp_path, "remote")
    reader = _isolated_committed_repo(tmp_path, "reader")
    _isolated_git(reader, "remote", "add", "origin", str(remote))

    bare = gitread.probe(reader, "ls-remote", "origin", negative_statuses=())
    padded = gitread.probe(
        reader, "ls-remote", "origin", str(remote / "not-a-ref"), negative_statuses=(),
    )
    assert bare.ok == padded.ok, (
        "an incidental argument changed the transport permission: "
        f"bare ok={bare.ok}, padded ok={padded.ok}"
    )
    # And the constant this release ships is 2.4.0's: the file transport is open,
    # so a local address reads whoever spelled it. What 2.4.0 left open and this
    # release closes is the PROGRAM, guarded separately by the `--upload-pack`
    # injection, not the protocol.
    assert bare.ok, "the file transport is meant to be enabled, as it is in 2.4.0"


def test_a_transport_the_caller_did_not_open_is_still_refused(tmp_path):
    """`protocol.allow = never` still holds for everything but the constant.

    The file transport being constant must not be read as the transport gate
    being gone. Nothing else opens without the caller asking for it.
    """
    reader = _isolated_committed_repo(tmp_path, "reader")
    _isolated_git(reader, "remote", "add", "upstream", "ssh://git@no-such-host.invalid/x.git")

    answer = gitread.probe(reader, "ls-remote", "upstream", negative_statuses=())
    assert not answer.ok
    assert "not allowed" in answer.detail


# --- the verb is not the unit of read-onlyness -----------------------------------
#
# The first allowlist admitted `config`, under a comment asserting that "a write
# needs a value argument this module never passes" — while `probe(cwd, *args)`
# is a public varargs API and the CALLER passes the arguments. An auditor added
# a key to a repository through the read-only layer, and removed another.


def test_git_config_writes_and_is_therefore_gated_on_its_argument_form(tmp_path):
    directory, _head = _scratch_repo(tmp_path)

    for arguments in (("config", "audit.injected", "yes"),
                      ("config", "--unset", "user.name"),
                      ("config", "--replace-all", "user.name", "someone")):
        with _pytest.raises(_IntegrityError) as caught:
            gitread.probe(directory, *arguments, negative_statuses=())
        assert "argument forms" in caught.value.render()

    # Asserted on the repository, not only on the exception.
    written = _subprocess.run(["git", "config", "--get", "audit.injected"], cwd=directory,
                              capture_output=True, text=True)
    assert written.returncode != 0, "the key exists; the refusal came too late to be a control"
    kept = _subprocess.run(["git", "config", "--get", "user.name"], cwd=directory,
                           capture_output=True, text=True)
    assert kept.stdout.strip() == "T", "the value was removed through a read-only layer"


def test_the_read_shaped_config_forms_still_work(tmp_path):
    """A gate that refused correct work would be found immediately and removed."""
    directory, _head = _scratch_repo(tmp_path)
    answer = gitread.probe(directory, "config", "--get", "user.name", negative_statuses=(1,))
    assert answer.answered and answer.value.strip() == "T"
    assert gitread.probe(directory, "config", "--list", negative_statuses=(1,)).answered


def test_an_option_that_makes_a_read_write_to_a_file_is_refused(tmp_path):
    """`git diff --output=FILE` creates FILE. The verb is a read; the invocation
    is not."""
    directory, _head = _scratch_repo(tmp_path)
    target = tmp_path / "leaked.txt"
    with _pytest.raises(_IntegrityError) as caught:
        gitread.probe(directory, "diff", f"--output={target}", "HEAD", negative_statuses=())
    assert "write to the filesystem" in caught.value.render()
    assert not target.exists()


def test_every_verb_whose_read_onlyness_depends_on_arguments_declares_its_forms():
    """Structural: a verb added to the allowlist that can write in some form
    must appear in the argument-form table, or the table is decoration."""
    assert "config" in gitread.READ_ONLY_ARGUMENT_FORMS
    assert set(gitread.READ_ONLY_ARGUMENT_FORMS) <= gitread.READ_ONLY_VERBS
    assert gitread.WRITING_OPTIONS, "the option denylist must not be empty"


# --- code the repository chooses ------------------------------------------------------


def _repo_that_runs_a_program(tmp_path, key):
    """A repository whose own config names a program for Git to run on diff."""
    repo = tmp_path / "hostile"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "f").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    writer = repo / "writer.sh"
    writer.write_text(f"#!/bin/sh\ntouch {repo / 'EXTERNAL-DIFF-RAN'}\n")
    writer.chmod(0o755)
    _git(repo, "config", key, str(writer))
    (repo / "f").write_text("y")
    return repo, repo / "EXTERNAL-DIFF-RAN"


def test_the_subjects_own_config_cannot_make_a_read_run_a_program(tmp_path):
    """The finding, from a blind cross-vendor reader, and the worst one in the
    release: `diff.external` in a scratch repository's config, `probe(repo,
    "diff", ...)` through the read-only API, and the script ran.

    **It ran without the flag too.** For a checker whose whole purpose is
    reading repositories somebody else controls, that is arbitrary code
    execution on every diff. The neutralised-config table said of this key
    *"the diff family has its own switch for this"* — and the switch was never
    passed. A comment naming the answer is not the answer.
    """
    repo, marker = _repo_that_runs_a_program(tmp_path, "diff.external")
    answer = gitread.probe(repo, "diff", "HEAD", negative_statuses=())
    assert answer.answered
    assert not marker.exists(), "the subject's config ran a program through a read"


def test_an_attribute_selected_diff_driver_cannot_run_either(tmp_path):
    """The reason the repair is `--no-ext-diff` and not a config key: a driver
    named by `.gitattributes` lives under `diff.<name>.command`, and no
    enumerable set of keys reaches it."""
    repo, marker = _repo_that_runs_a_program(tmp_path, "diff.evil.command")
    (repo / ".gitattributes").write_text("* diff=evil\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "attributes")
    (repo / "f").write_text("z")

    assert gitread.probe(repo, "diff", "HEAD", negative_statuses=()).answered
    assert not marker.exists()


def test_the_diff_family_still_reads_after_the_hardening(tmp_path):
    """The bound: a repair that made every diff refuse would pass the three
    tests above and break the pack."""
    repo, _ = _repo_that_runs_a_program(tmp_path, "diff.external")
    # `ok`, not `answered`. A Git parse failure caused by the injected flags
    # produces `answered=True, ok=False`, so asserting `answered` passes through
    # exactly the breakage this test exists to catch — said by a blind reader
    # about the first version of this line.
    assert gitread.probe(repo, "diff", "--stat", "HEAD", negative_statuses=()).ok
    assert gitread.probe(repo, "log", "--oneline", "-1", negative_statuses=()).ok
    assert gitread.probe(repo, "show", "--stat", "HEAD", negative_statuses=()).ok


def test_two_paths_sharing_one_blob_are_two_names(tmp_path):
    """`rev-list --objects` prints one name per object, so the second path was
    never enumerated at all. Names come from the trees now."""
    repo = tmp_path / "aliased"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("identical\n")
    (repo / "b.txt").write_text("identical\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "two names, one blob")

    names = gitread.every_name_in_history(repo, "HEAD")
    assert sorted(path for _sha, path in names) == ["a.txt", "b.txt"]
    assert len({sha for sha, _path in names}) == 1, "one blob, deliberately"


def test_a_smudge_filter_the_attributes_select_cannot_run(tmp_path):
    """`cat-file --filters` applies the repository's own `.gitattributes` filter
    chain, which is a third way for the subject to name a program — after
    `diff.external` and the attribute-selected diff driver, both closed one
    round earlier. Found by a blind reader ON the repair for those two."""
    repo = tmp_path / "filtered"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    writer = repo / "smudge.sh"
    writer.write_text(f"#!/bin/sh\ntouch {repo / 'FILTER_RAN'}\ncat\n")
    writer.chmod(0o755)
    _git(repo, "config", "filter.evil.smudge", str(writer))
    (repo / ".gitattributes").write_text("* filter=evil\n")
    (repo / "f.txt").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    # A filter which shapes this answer is now a named refusal. It remains
    # important to prove the program did not run before that refusal.
    answer = gitread.probe(repo, "cat-file", "--filters", "HEAD:f.txt", negative_statuses=())
    assert not answer.answered
    assert "content filter" in answer.cause
    assert not (repo / "FILTER_RAN").exists(), "the repository's smudge filter ran"


def test_a_submodules_own_configuration_cannot_run_through_the_parent(tmp_path):
    """The escape the first hardening did not close, and the reason it did not:
    **a nested Git process is a second process**, and the parent's command line
    never reaches it. `diff --submodule=diff` ran the SUBMODULE's `diff.external`
    straight through flags that protect only the parent."""
    sub, sup = tmp_path / "sub", tmp_path / "sup"
    sub.mkdir(); sup.mkdir()
    _git(sub, "init", "-q", "-b", "main")
    (sub / "s").write_text("1")
    _git(sub, "add", "-A")
    _git(sub, "commit", "-qm", "s1")
    _git(sup, "init", "-q", "-b", "main")
    _git(sup, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "sub")
    _git(sup, "add", "-A")
    _git(sup, "commit", "-qm", "add sub")
    writer = tmp_path / "w.sh"
    writer.write_text(f"#!/bin/sh\ntouch {tmp_path / 'SUBMODULE_DIFF_RAN'}\n")
    writer.chmod(0o755)
    _git(sup / "sub", "config", "diff.external", str(writer))
    (sup / "sub" / "s").write_text("2")

    # Was a refusal, is now a read that executes nothing. A nested Git process is
    # still a second process — it simply has no configuration of the subject's to
    # act on, because the `.git` it opens is one this harness built.
    answer = gitread.probe(sup, "diff", "--submodule=diff", negative_statuses=())
    assert answer.answered, answer.cause
    assert not (tmp_path / "SUBMODULE_DIFF_RAN").exists(), \
        "the submodule's own diff.external ran through the parent"


def test_a_repository_with_no_commits_has_no_names_rather_than_an_error(tmp_path):
    """An empty history's name set is empty, which is an answer. `rev-list HEAD`
    exits non-zero on one, and the refusal reached callers who had asked a
    question with a correct empty answer."""
    repo = tmp_path / "empty"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    assert gitread.every_name_in_history(repo, "HEAD") == []


def test_a_real_read_failure_is_still_a_refusal_and_not_an_empty_answer(tmp_path):
    """The bound on the line above, and it survived a mutant until it was
    written: `except GitRefusal: return []` turns *this ref does not exist* and
    *this read failed* into the same answer, and the second one silently reports
    a repository as having no names.

    A repository WITH commits, asked about a ref that is not there, must refuse
    — because the empty answer is only correct when there is genuinely nothing
    to enumerate.
    """
    repo = tmp_path / "populated"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "f").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    assert [path for _sha, path in gitread.every_name_in_history(repo, "HEAD")] == ["f"]
    with pytest.raises(GitRefusal):
        gitread.every_name_in_history(repo, "refs/heads/no-such-branch")


def test_the_git_protocol_cannot_be_enabled_because_its_proxy_cannot_be_disabled(tmp_path):
    """The fourth execution route, and the only one that came through the single
    exception that exists to let one operation cross a boundary.

    `core.gitProxy` names a program Git runs to open a `git://` connection. It
    **cannot be neutralised from the environment** — the key is multi-valued, so
    `GIT_CONFIG_KEY_n` appends rather than replaces and Git uses the
    repository's entry. Setting it to `none` and to the empty string were each
    tried and each left the program running, which is why the repair narrows the
    exception instead of hardening the key.
    """
    repo = tmp_path / "proxied"
    repo.mkdir()
    _git(repo, "init", "-q")
    proxy = tmp_path / "proxy"
    proxy.write_text(f"#!/bin/sh\nprintf executed > {tmp_path / 'PROXY_RAN'}\nexit 1\n")
    proxy.chmod(0o700)
    _git(repo, "config", "core.gitProxy", str(proxy))

    assert "git" not in gitread.ALLOWABLE_TRANSPORTS
    with pytest.raises(_IntegrityError):
        gitread.probe(repo, "ls-remote", "git://example.invalid/nope",
                      allow_transports=("git",))
    assert not (tmp_path / "PROXY_RAN").exists()


def test_narrowing_the_exception_did_not_close_the_transports_it_exists_for():
    """The bound. The exception exists because one postcondition has to read a
    real remote, and a repair that closed every protocol would pass the test
    above and break that."""
    assert set(gitread.ALLOWABLE_TRANSPORTS) == {"ssh", "https", "http", "file"}


def test_a_remote_the_repository_configured_cannot_run_its_own_program(tmp_path):
    """The fifth execution route, and it came through the ONE transport
    exception. `remote.<name>.uploadpack` names a program Git runs on the far
    side — and with a `file://` remote the far side is this machine, so the
    program ran with the reader's own permissions and wrote into the reader.

    No config key closes it: the setting is per-remote and remote names cannot
    be enumerated. The command-line form overrides the config, verified rather
    than assumed."""
    remote, reader = tmp_path / "remote.git", tmp_path / "reader"
    remote.mkdir(); reader.mkdir()
    _git(remote, "init", "-q", "--bare")
    _git(reader, "init", "-q", "-b", "main")
    hostile = tmp_path / "up.sh"
    hostile.write_text(
        f'#!/bin/sh\ntouch {reader / "WRITTEN_BY_THE_REMOTE"}\nexec git-upload-pack "$@"\n')
    hostile.chmod(0o755)
    _git(reader, "remote", "add", "origin", f"file://{remote}")
    _git(reader, "config", "remote.origin.uploadpack", str(hostile))

    answer = gitread.probe(reader, "ls-remote", "origin", negative_statuses=(),
                           allow_transports=("file",))
    assert answer.answered
    assert not (reader / "WRITTEN_BY_THE_REMOTE").exists(), \
        "the repository being read chose a program and it ran"


# --- the shape of the key, rather than the routes anybody has thought of -------------


def _repo_setting(tmp_path, key, value="/bin/sh"):
    repo = tmp_path / key.replace(".", "-").replace("*", "x")
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", key, value)
    return repo


def test_a_path_that_is_not_a_repository_is_still_the_callers_own_refusal(tmp_path):
    """A missing directory is not a configuration finding, and reporting it as
    one hid what was actually wrong."""
    assert gitread.program_valued_config(tmp_path / "nowhere") == []


def test_a_deadline_the_caller_set_is_the_callers_own_refusal(tmp_path):
    """The inspection runs inside the caller's timeout, so an impatient caller
    expired inside it and got a configuration finding where it had asked for,
    and was owed, a timeout."""
    repo = _repo_setting(tmp_path, "merge.m.driver")
    # Through `probe`, which converts a refusal into an answer-shaped result:
    # the point is that it reports COULD NOT ASK, and specifically that the
    # reason is the deadline rather than this check's opinion of the config.
    answer = gitread.probe(repo, "status", timeout=1e-9, negative_statuses=())
    assert not answer.answered
    assert "timed out" in answer.cause


def test_a_commit_message_is_part_of_the_history(tmp_path):
    """Commits are skipped by the blob walk because they are not blobs, so a
    private term written into a commit message scanned CLEAN — close to the most
    likely place for one to be."""
    repo = tmp_path / "messages"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "f").write_text("ordinary\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "a message nobody scanned")

    # MORE THAN ONE COMMIT, and that is the whole repair to this test. An
    # independent reader replaced `commit_messages` with one that reads only the
    # named tip and no ancestors, and the test still passed: with a one-commit
    # fixture, HEAD IS the whole history, and the test could not tell traversal
    # from a single read. It did not state that it was relying on that.
    (repo / "f").write_text("second\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "a later message")
    _git(repo, "checkout", "-q", "-b", "side", "HEAD~1")
    (repo / "g").write_text("branch\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "a message on a side branch")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "side", "-m", "a merge message")

    bodies = [body for _sha, body in gitread.commit_messages(repo, "HEAD")]
    assert "a message nobody scanned\n" in bodies, "an ancestor was not traversed"
    assert "a message on a side branch\n" in bodies, "a merge parent was not traversed"
    assert "a merge message\n" in bodies
    # Exact, not `in`: the previous reader returned every non-tip body with a
    # leading newline, and a pattern anchored to the start of a message stopped
    # matching while `in` kept passing.
    assert all(not b.startswith("\n") for b in bodies), "a body carries a leading newline"


def test_a_commit_message_is_read_by_its_byte_count_and_not_by_a_delimiter(tmp_path):
    """Three shapes the format-string reader got wrong, in one test: an empty
    message came back as a newline, a message containing the delimiter byte was
    truncated at it, and every non-tip body carried a leading newline."""
    repo = tmp_path / "shapes"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "f").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "first")
    _git(repo, "commit", "-q", "--allow-empty", "--allow-empty-message", "-m", "")

    bodies = dict(gitread.commit_messages(repo, "HEAD"))
    assert "" in bodies.values(), "an empty message is empty, not a newline"
    assert "first\n" in bodies.values()


def test_an_object_the_store_cannot_produce_is_a_hole_and_not_an_absence(tmp_path, monkeypatch):
    """Git's documented `<sha> missing` batch record was dropped silently, so a
    caller could certify a COMPLETE history scan over commits nobody read — and
    that is the whole claim the word *complete* makes."""
    real = gitread._run

    def missing(repo, *args, **kw):
        if args[0] == "rev-list":
            return "a" * 40 + "\n"
        if args[0] == "cat-file":
            return ("a" * 40 + " missing\n").encode()
        return real(repo, *args, **kw)

    monkeypatch.setattr(gitread, "_run", missing)
    with pytest.raises(_IntegrityError):
        gitread.commit_messages(tmp_path, "HEAD")


def test_an_object_typed_commit_with_no_message_separator_is_refused(tmp_path, monkeypatch):
    """Calling its message empty is a guess about an object that is not shaped
    like a commit."""
    real = gitread._run
    body = b"tree " + b"0" * 40

    def malformed(repo, *args, **kw):
        if args[0] == "rev-list":
            return "b" * 40 + "\n"
        if args[0] == "cat-file":
            return ("b" * 40 + f" commit {len(body)}\n").encode() + body + b"\n"
        return real(repo, *args, **kw)

    monkeypatch.setattr(gitread, "_run", malformed)
    with pytest.raises(_IntegrityError):
        gitread.commit_messages(tmp_path, "HEAD")


# --- RP2.4.1 B1/B3/B4: what a read may execute, and what it may answer about ---


def test_a_repository_with_no_filter_still_reads(tmp_path):
    """O3. The bound. Refusing every repository would be obstruction, not
    hardening."""
    repo = tmp_path / "ordinary"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@e.invalid")
    _git(repo, "config", "user.name", "T")
    (repo / "f.txt").write_text("hello\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    assert gitread.program_valued_config(repo) == []
    assert gitread._run(repo, "rev-parse", "HEAD", timeout=30).strip()


def test_a_standalone_repository_and_a_linked_worktree_still_read(tmp_path):
    """O6. The two layouts that must keep working — and the linked worktree is
    the one the first attempt at this repair broke, by binding the resolved
    repository on the premise that its git dir sits under its own root. It does
    not; it lives under the main repository."""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    _git(main, "config", "user.email", "t@e.invalid")
    _git(main, "config", "user.name", "T")
    (main / "VERSION").write_text("1.0.0\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-q", "-m", "base")
    assert gitread._run(main, "rev-parse", "HEAD", timeout=30).strip()

    linked = tmp_path / "linked"
    _git(main, "worktree", "add", "-q", "--detach", str(linked))
    assert gitread._run(linked, "rev-parse", "HEAD", timeout=30).strip()
    assert gitread._run(linked, "ls-files", timeout=30).strip()


def test_a_linked_worktrees_common_directory_matches_real_git_byte_for_byte(tmp_path):
    """`--git-common-dir` names shared state, not this worktree's private state.

    The constructed directory has no worktree split, so generic scratch-path
    restoration once returned the linked worktree's private directory at exit
    zero.  This builds a real linked worktree and holds the public governed
    answer against real Git's bytes rather than a hand-written pathname.
    """
    main = _committed(tmp_path, "common-main")
    linked = tmp_path / "common-linked"
    _git(main, "worktree", "add", "-q", "--detach", str(linked))

    real = _real_git(linked, "rev-parse", "--git-common-dir")
    assert real.returncode == 0, real.stderr
    governed = gitread._run(linked, "rev-parse", "--git-common-dir")
    assert governed == real.stdout
    assert governed == str(main / ".git") + "\n"


def test_the_public_composition_signature_has_no_acceptance_fault_switch():
    """Positive-control wiring is private to the acceptance corpus."""
    assert "fault" not in inspect.signature(_compose).parameters


# --- RP2.4.1: every configuration source Git applies, and every verb bound -----

def _worktree_config_repo(tmp_path, name, program):
    """A repository declaring a filter in `config.worktree` rather than `config`."""
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@e.invalid")
    _git(repo, "config", "user.name", "T")
    (repo / "f.txt").write_text("hello\n")
    (repo / ".gitattributes").write_text("* filter=x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "config", "extensions.worktreeConfig", "true")
    _git(repo, "config", "--worktree", "filter.x.clean", str(program))
    (repo / "f.txt").write_text("hello\nchanged\n")
    return repo


def _committed(tmp_path, name):
    """An ordinary repository with one commit."""
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@e.invalid")
    _git(repo, "config", "user.name", "T")
    (repo / "f.txt").write_text("hello\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def test_an_enabled_extension_with_no_worktree_file_still_reads(tmp_path):
    """O2. Git lets the extension be enabled without the optional file ever being
    created, and reads such a repository perfectly well. A version of this check
    asked for the file whenever the key was present and turned Git's `no such
    file` into a refusal, so enabling an extension and writing nothing to it
    blocked every governed read of a valid repository."""
    repo = _committed(tmp_path, "enabled_nofile")
    _git(repo, "config", "extensions.worktreeConfig", "true")
    assert not (repo / ".git" / "config.worktree").exists()
    assert gitread.program_valued_config(repo) == []
    assert gitread._run(repo, "ls-files", timeout=30).strip() == "f.txt"


def test_a_disabled_extension_still_reads_with_several_worktrees(tmp_path):
    """O3. Git refuses `--worktree` outright when the extension is off and more
    than one worktree exists. A version of this check tested the key's PRESENCE
    rather than Git's reading of its VALUE, so an explicitly disabled extension
    took the same branch as an enabled one and that refusal reached the caller."""
    main = _committed(tmp_path, "disabled_many")
    linked = tmp_path / "disabled_many_linked"
    _git(main, "config", "extensions.worktreeConfig", "false")
    _git(main, "worktree", "add", "-q", "--detach", str(linked))
    for repository in (main, linked):
        assert gitread.program_valued_config(repository) == []
        assert gitread._run(repository, "ls-files", timeout=30).strip() == "f.txt"


def test_an_inactive_worktree_config_is_not_a_second_configuration_source(tmp_path):
    """A present `config.worktree` is ignored until the extension enables it.

    Git resolves `test.key` from the main config in this layout.  Treating a
    merely present file as live either refuses the public single-file `config`
    read or reports the inactive value through `config_with_origin`; both are
    wrong answers about a source Git did not consult.
    """
    repo = _isolated_committed_repo(tmp_path, "inactive-worktree-config")
    _isolated_git(repo, "config", "test.key", "main")
    main = repo / ".git" / "config"
    inactive = repo / ".git" / "config.worktree"
    inactive.write_text("[test]\n\tkey = worktree\n", encoding="utf-8")

    oracle = _isolated_real_git(repo, "config", "--get", "test.key")
    assert oracle.returncode == 0, oracle.stderr
    assert oracle.stdout == "main\n"

    assert gitread._configuration_files_of(repo) == [main]
    answer = gitread.probe(repo, "config", "--get", "test.key", negative_statuses=(1,))
    assert answer.answered and answer.ok and answer.value == oracle.stdout.strip()
    reported = [entry for entry in gitread.config_with_origin(repo) if entry["key"] == "test.key"]
    assert [entry["value"] for entry in reported] == ["main"]
    assert all(str(inactive) not in entry["origin"] for entry in reported)


def test_only_the_repositorys_own_scopes_are_inspected(tmp_path):
    """O5. The function promises the repository's OWN configuration. A key
    supplied on the command line is applied by Git and labelled `command`, so a
    check that kept every scope would report the caller's own environment as a
    finding of the repository."""
    repo = _committed(tmp_path, "scoped")
    listing = gitread._run(
        repo, "config", "--list", "--name-only", "--show-scope", "-z", timeout=30)
    scopes = {field for field in gitread.nul_paths(listing.encode())[::2]}
    assert scopes <= {"local", "worktree", "global", "system", "command", "unknown"}
    injected = subprocess.run(
        ["git", "-c", "filter.y.clean=/bin/cat", "config", "--list",
         "--name-only", "--show-scope", "-z"],
        cwd=repo, capture_output=True, check=True).stdout
    fields = gitread.nul_paths(injected)
    assert "filter.y.clean" in fields
    assert dict(zip(fields[1::2], fields[::2]))["filter.y.clean"] == "command"
    assert gitread.program_valued_config(repo) == []


def _ssh_program_repo(tmp_path, name):
    """A repository whose `core.sshCommand` is a local program that leaves a
    marker, so whether Git ran it is a fact on disk rather than an inference."""
    repo = _committed(tmp_path, name)
    marker = tmp_path / f"{name}-MARKER"
    program = tmp_path / f"{name}-ssh.py"
    program.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        f"pathlib.Path({str(marker)!r}).write_text('ran')\n"
        "sys.stdout.write('0' * 40 + chr(9) + 'HEAD' + chr(10))\n")
    program.chmod(0o755)
    _git(repo, "config", "core.sshCommand", str(program))
    _git(repo, "remote", "add", "origin", "ssh://example.invalid/x.git")
    return repo, marker


def _transport_reenable_repo(tmp_path, name, *, worktree_scope=False):
    """A repository that turns a transport back on and names a program to run
    over it. The marker is written by the program, so execution is a fact on
    disk rather than an inference from an exit status."""
    repo = _committed(tmp_path, name)
    marker = tmp_path / f"{name}-MARKER"
    program = tmp_path / f"{name}-prog.sh"
    program.write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n")
    program.chmod(0o755)
    if worktree_scope:
        _git(repo, "config", "extensions.worktreeConfig", "true")
        _git(repo, "config", "--worktree", "protocol.ext.allow", "always")
    else:
        _git(repo, "config", "protocol.ext.allow", "always")
    _git(repo, "remote", "add", "origin", f"ext::{program} %S")
    return repo, marker


def test_a_repository_cannot_re_enable_a_transport_the_reader_refuses(tmp_path):
    """O1. The reader refuses transports with `protocol.allow = never` at command
    scope and reasoned that the specific key Git consults first would fall back
    to it. It does not: they are DIFFERENT KEYS, so the general refusal never
    contests the specific one — and the repository being read can set the
    specific one itself.

    Reproduced with no transport enabled by any caller, and with `ext` not even
    among `ALLOWABLE_TRANSPORTS`: the repository's own program ran.
    """
    repo, marker = _transport_reenable_repo(tmp_path, "reenable")
    answer = gitread.probe(repo, "ls-remote", "origin", negative_statuses=())
    assert answer.answered and not answer.ok
    assert not marker.exists(), "the repository re-enabled a transport and its program ran"


def test_a_worktree_declared_transport_re_enable_is_pinned_too(tmp_path):
    """O2. `config.worktree` is applied by Git exactly as `config` is, so a
    re-enable declared there must be pinned the same way. The names are taken
    from the scope-labelled listing, which already covers both."""
    repo, marker = _transport_reenable_repo(tmp_path, "reenable_wt", worktree_scope=True)
    answer = gitread.probe(repo, "ls-remote", "origin", negative_statuses=())
    assert answer.answered and not answer.ok
    assert not marker.exists()


def test_the_git_protocol_closure_is_true_because_the_repository_cannot_enable_it(tmp_path):
    """O3. `core.gitproxy` is excused as "unreachable: the git:// protocol is not
    enablable". That was false while a repository could enable it: setting
    `protocol.git.allow` and a `core.gitProxy` ran the proxy. The closure is a
    statement about what Git will do, so it has to be true rather than intended.
    """
    repo = _committed(tmp_path, "gitproxy")
    marker = tmp_path / "gitproxy-MARKER"
    program = tmp_path / "gitproxy-prog.sh"
    program.write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n")
    program.chmod(0o755)
    _git(repo, "config", "protocol.git.allow", "always")
    _git(repo, "config", "core.gitProxy", str(program))
    _git(repo, "remote", "add", "origin", "git://example.invalid/x.git")
    answer = gitread.probe(repo, "ls-remote", "origin", negative_statuses=())
    assert answer.answered and not answer.ok
    assert not marker.exists(), "the repository enabled git:// and its proxy ran"


def test_a_transport_spelled_differently_from_the_enabled_one_is_still_pinned(tmp_path):
    """O9. `protocol.File.allow` and `protocol.file.allow` name DIFFERENT
    transports to Git: the first enables a `git-remote-File` helper.

    The first version of this comparison folded both to lower case before asking
    whether the caller had enabled the transport, so a repository could keep its
    helper enabled simply by spelling the name differently from the transport the
    caller asked for. Reproduced against real Git: with `file` enabled and the
    repository declaring `File`, the helper ran. Mutation is what found it — no
    test distinguished the two spellings, and every one of them passed.

    Only the spelling the caller actually enabled is left alone now.
    """
    repo = _committed(tmp_path, "spelling")
    marker = tmp_path / "FILE_HELPER_RAN"
    helpers = tmp_path / "helpers"
    helpers.mkdir()
    helper = helpers / "git-remote-File"
    helper.write_text(f"#!/bin/sh\nprintf 'x' >> {marker}\necho\n")
    helper.chmod(0o755)
    _git(repo, "config", "protocol.File.allow", "always")
    _git(repo, "remote", "add", "origin", "File::example")

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PATH", f"{helpers}:{os.environ.get('PATH', '')}")
        answer = gitread.probe(repo, "ls-remote", "origin", negative_statuses=(),
                               allow_transports=("file",))
        assert not answer.ok
    assert not marker.exists(), (
        "the repository kept a helper enabled by spelling its transport differently "
        "from the one the caller enabled")


def _superproject(tmp_path, name, *, declare=None, populate=True):
    """A superproject with one submodule, and a marker the submodule's program
    writes if Git ever runs it."""
    inner = tmp_path / f"{name}-inner"
    inner.mkdir()
    _git(inner, "init", "-q", "-b", "main")
    _git(inner, "config", "user.email", "t@e.invalid")
    _git(inner, "config", "user.name", "T")
    (inner / "s.txt").write_text("aaaa\n")
    (inner / ".gitattributes").write_text("*.txt filter=x\n")
    _git(inner, "add", "-A")
    _git(inner, "commit", "-q", "-m", "s1")

    sup = tmp_path / name
    sup.mkdir()
    _git(sup, "init", "-q", "-b", "main")
    _git(sup, "config", "user.email", "t@e.invalid")
    _git(sup, "config", "user.name", "T")
    (sup / "p.txt").write_text("p\n")
    _git(sup, "add", "-A")
    _git(sup, "commit", "-q", "-m", "p1")
    _git(sup, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(inner), "sub")
    _git(sup, "commit", "-q", "-m", "add sub")

    marker = tmp_path / f"{name}-MARKER"
    if declare:
        program = tmp_path / f"{name}-prog.sh"
        program.write_text(f"#!/bin/sh\nprintf 'x' >> {marker}\ncat 2>/dev/null\nexit 0\n")
        program.chmod(0o755)
        _git(sup / "sub", "config", declare, str(program))
        _git(sup, "config", "diff.submodule", "diff")
        (sup / "sub" / "s.txt").write_text("bbbb\n")
    if not populate:
        import shutil
        shutil.rmtree(sup / "sub")
        (sup / "sub").mkdir()
    return sup, marker


def test_a_superproject_with_an_ordinary_submodule_still_reads(tmp_path):
    """O3. The bound. A submodule that declares nothing must cost nothing: the
    rule applied is the one the superproject already lives under, not a new
    suspicion of submodules."""
    sup, marker = _superproject(tmp_path, "sm_plain")
    assert gitread.program_valued_config(sup) == []
    assert gitread._run(sup, "ls-files", timeout=30).strip()
    assert not marker.exists()


def test_an_unpopulated_submodule_is_not_a_finding(tmp_path):
    """O4. A gitlink in the index whose directory was never checked out has no
    configuration for Git to apply, so it is not something to refuse over."""
    sup, _ = _superproject(tmp_path, "sm_empty", populate=False)
    assert gitread.program_valued_config(sup) == []
    assert gitread._run(sup, "ls-files", timeout=30).strip()


def test_a_tracked_symlink_to_another_repository_is_not_walked(tmp_path):
    """O5. Only a gitlink is a submodule. A tracked SYMLINK that happens to point
    at a directory containing `.git` is an ordinary tracked file to Git, which
    never enters it and never applies its configuration — so inspecting it would
    refuse a superproject over a repository Git does not read.

    Mutation found this: dropping the mode test left every tracked path treated
    as a possible submodule, and no test told the difference.
    """
    other = tmp_path / "unrelated"
    other.mkdir()
    _git(other, "init", "-q", "-b", "main")
    _git(other, "config", "user.email", "t@e.invalid")
    _git(other, "config", "user.name", "T")
    (other / "f.txt").write_text("x\n")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "base")
    _git(other, "config", "filter.x.clean", "/bin/cat")

    repo = _committed(tmp_path, "symlinked")
    (repo / "link").symlink_to(other)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "link")

    assert gitread.program_valued_config(repo) == []
    assert gitread._run(repo, "ls-files", timeout=30).strip()


def _superproject_with_diff_helper(tmp_path, name, *, where):
    """A superproject and submodule where `where` ("outer" or "sub") declares a
    `diff.external` helper that leaves a marker if Git runs it."""
    sup, marker = _superproject(tmp_path, name)
    program = tmp_path / f"{name}-diff.sh"
    program.write_text(f"#!/bin/sh\nprintf 'x' >> {marker}\nexit 0\n")
    program.chmod(0o755)
    target = sup if where == "outer" else sup / "sub"
    _git(target, "config", "diff.external", str(program))
    _git(sup, "config", "diff.submodule", "diff")
    (sup / "sub" / "s.txt").write_text("bbbb\n")
    return sup, marker


def test_every_flag_based_closure_is_declared(tmp_path):
    """O6, KEPT BUT NO LONGER A SAFETY PROPERTY, and said so here rather than left
    to be inferred.

    This asserted that a closure resting on a command-line flag was declared as
    one, "or the next entry added will quietly cover a nested repository the flag
    never reaches". That reason was true of the 2.4.1 enumeration and is false
    here: `CLOSED_PROGRAM_KEYS` and `FLAG_BASED_CLOSURES` are retained public
    names under the founder's AUTH-2 and nothing consults them —
    `test_no_refusal_depends_on_a_projection` empties all four and shows no answer,
    no refusal and no execution changes. So what remains is a coherence check over
    two inert tables, and an independent read was right to call it a green test
    about a relationship no governed read uses. It is kept rather than deleted
    because a frozen 2.4.1 design record names this selector as O6, and dropping a
    named oracle is a provenance cost with nothing bought. Removing the tables
    themselves would remove a public name 2.4.0 shipped, which is a SemVer
    decision and not one this release takes."""
    for key, reason in gitread.CLOSED_PROGRAM_KEYS.items():
        mentions_flag = "--" in reason
        assert mentions_flag == (key in gitread.FLAG_BASED_CLOSURES), (
            f"{key!r} is justified by {reason!r}; declare it in FLAG_BASED_CLOSURES "
            f"if that reason is a command-line flag, which does not reach a nested repository")


def test_a_repository_declaring_no_worktree_config_still_reads(tmp_path):
    """The bound: the second question must not refuse ordinary repositories."""
    repo = tmp_path / "ordinary2"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@e.invalid")
    _git(repo, "config", "user.name", "T")
    (repo / "f.txt").write_text("hello\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    assert gitread.program_valued_config(repo) == []
    assert gitread._run(repo, "rev-parse", "HEAD", timeout=30).strip()


def test_a_root_reached_through_a_symlink_is_the_same_root(tmp_path):
    """M3. Both sides of the comparison are resolved, which is what lets a root
    reached through a symlinked parent verify. Nothing pinned it, so a mutant
    comparing the caller's spelling survived."""
    real = tmp_path / "real"
    real.mkdir()
    _git(real, "init", "-q", "-b", "main")
    _git(real, "config", "user.email", "t@e.invalid")
    _git(real, "config", "user.name", "T")
    (real / "f.txt").write_text("hello\n")
    _git(real, "add", "-A")
    _git(real, "commit", "-q", "-m", "base")

    link = tmp_path / "through-a-link"
    link.symlink_to(real, target_is_directory=True)
    # A BOUND VERB, not `rev-parse`. The binding deliberately exempts `rev-parse`
    # to avoid asking Git about Git, so an oracle written on it never reaches the
    # comparison at all — which is exactly why the spelling mutant survived the
    # first version of this test. Git resolves the symlink and reports the real
    # path, so a comparison of the caller's spelling refuses here and a
    # comparison of the resolved paths does not.
    assert gitread._run(link, "ls-files", timeout=30).strip()
    assert gitread._run(f"{real}/", "ls-files", timeout=30).strip()
    assert gitread._run(f"{real}/.", "ls-files", timeout=30).strip()


def _slow_worktree_config(tmp_path, name):
    """A repository whose per-worktree configuration takes measurably longer to
    read than its local one — inert padding, no program declared in the padding."""
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@e.invalid")
    _git(repo, "config", "user.name", "T")
    (repo / "f.txt").write_text("hello\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "config", "extensions.worktreeConfig", "true")
    _git(repo, "config", "--worktree", "filter.x.clean", "/bin/cat")
    worktree_config = repo / ".git" / "config.worktree"
    padding = "\n".join(f"\tpad{index} = {'y' * 160}" for index in range(60000))
    worktree_config.write_text(worktree_config.read_text() + "\n[padding]\n" + padding + "\n")
    return repo


def _timed(repository):
    """How long the inspection's own read of this repository takes, warm."""
    import time
    gitread._run(repository, "config", "--list", "--name-only", "--show-scope", "-z",
                 timeout=30)
    start = time.monotonic()
    gitread._run(repository, "config", "--list", "--name-only", "--show-scope", "-z",
                 timeout=30)
    return time.monotonic() - start


def test_a_repository_without_the_extension_is_not_asked_a_second_time(tmp_path):
    """The bound: the second read happens only where Git would apply the file."""
    repo = tmp_path / "noext"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@e.invalid")
    _git(repo, "config", "user.name", "T")
    (repo / "f.txt").write_text("hello\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    assert gitread.program_valued_config(repo, timeout=30) == []
    assert gitread._run(repo, "rev-parse", "HEAD", timeout=30).strip()


# --- the sterile boundary: what the enumeration used to promise, measured -------------
#
# Every test below replaces one this file used to carry. The old ones asserted
# that a repository declaring a program-valued key was REFUSED. These assert the
# stronger thing: the program does not RUN. `docs/RP2.5.0-RECURRENCE-MAP.md` is
# why the difference matters — refusal was a proxy, and narrowing the proxy to
# stop over-refusing is what produced an under-refusal and an over-refusal in the
# same edit.


import json as _json
import shutil as _shutil

import sterile as _sterile


def _marker_script(tmp_path):
    """A program that records having run. `did_it_run` is then a measurement."""
    marker = tmp_path / "marker.txt"
    marker.write_bytes(b"")
    script = tmp_path / "record-that-i-ran"
    script.write_text(
        '#!/bin/sh\nprintf RAN >> "%s"\n'
        'if [ -n "${1:-}" ]; then cat "$1"; else cat; fi\n' % marker
    )
    script.chmod(0o755)
    return script, marker


def _hostile(repo, script, *, attributes="* diff=evil filter=evil\n", filters=True):
    """Every ordinary route by which a repository names a program for Git to run."""
    keys = [
        "diff.evil.textconv", "diff.external", "core.fsmonitor",
        "core.alternateRefsCommand", "core.pager", "core.editor",
        "credential.helper", "gpg.program", "sequence.editor",
        "uploadpack.packObjectsHook", "core.gitProxy",
    ]
    if filters:
        keys[:0] = ["filter.evil.clean", "filter.evil.smudge"]
    for key in keys:
        _git(repo, "config", key, str(script))
    if attributes is not None:
        (repo / ".gitattributes").write_text(attributes)


def _did_it_run(marker):
    return marker.stat().st_size if marker.exists() else 0


def _commit_all(repo, name="f.txt", body="hello\n"):
    (repo / name).write_text(body)
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "c")


def _real_git(repo, *args):
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)


# O1 / B15a --------------------------------------------------------------------------

@pytest.mark.parametrize("option", ["-v", "-vv", "-vvv", "--verbose", "--verb", "--verbo"])
def test_no_spelling_of_a_verb_executes_the_repositorys_driver(tmp_path, option):
    """**B15a, the blocker that stopped 2.4.1.** Its refusal matched the two exact
    strings `-v` and `--verbose`. Git also accepts `-vv`, `--verb` and `--verbo`,
    and each of those ran the repository's text-conversion helper through a
    guarded `status`. A third spelling nobody had reported was found while
    reproducing it.

    An option spelling cannot be enumerated, so nothing here enumerates one: the
    driver is not defined in the configuration Git reads, so no spelling reaches
    it."""
    script, marker = _marker_script(tmp_path)
    repo = tmp_path / "subject"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "diff.evil.textconv", str(script))
    (repo / ".gitattributes").write_text("* diff=evil\n")
    _commit_all(repo)
    (repo / "f.txt").write_text("changed\n")
    _git(repo, "add", "-A")

    marker.write_bytes(b"")
    real = _real_git(repo, "status", option)
    ran_for_real_git = _did_it_run(marker)

    marker.write_bytes(b"")
    answer = gitread.probe(repo, "status", option, negative_statuses=())
    assert answer.answered, answer.cause
    assert _did_it_run(marker) == 0, (
        f"`git status {option}` executed the repository's helper through the boundary"
    )
    # THE POSITIVE CONTROL. Without it this test passes on a spelling Git ignores,
    # and proves nothing at all.
    assert ran_for_real_git > 0 and real.returncode == 0, (
        f"real git did not run the helper for {option}, so this row is not a control"
    )


@pytest.mark.parametrize("option", ["--textconv", "--ext-diff"])
def test_a_driver_the_caller_explicitly_asks_for_still_cannot_run(tmp_path, option):
    """2.4.x refused these options. It no longer needs to: the driver they enable
    is not defined in the configuration Git reads, so asking for it by name gets
    a diff of the raw bytes. Refusing an argument was a proxy for the thing this
    measures."""
    script, marker = _marker_script(tmp_path)
    repo = tmp_path / "explicit"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "diff.evil.textconv", str(script))
    _git(repo, "config", "diff.external", str(script))
    (repo / ".gitattributes").write_text("* diff=evil\n")
    _commit_all(repo)
    (repo / "f.txt").write_text("changed\n")
    _git(repo, "add", "-A")
    marker.write_bytes(b"")
    answer = gitread.probe(repo, "diff", option, "--cached", negative_statuses=())
    assert answer.answered, answer.cause
    assert _did_it_run(marker) == 0


# O2 / O12 — the name decides, the kind never does ------------------------------------

def _superproject_with_nested(tmp_path, script, spelling):
    """A superproject whose working tree holds a second repository, spelled one of
    the ways a repository can spell it."""
    inner = tmp_path / "inner"
    inner.mkdir()
    _git(inner, "init", "-q", "-b", "main")
    (inner / ".gitattributes").write_text("* diff=evil\n")
    _commit_all(inner, "i.txt")
    sup = tmp_path / "sup"
    sup.mkdir()
    _git(sup, "init", "-q", "-b", "main")
    _commit_all(sup, "top.txt")
    _git(sup, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(inner), "mod")
    _git(sup, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "sub")
    module = sup / ".git" / "modules" / "mod"
    for key in ("diff.evil.textconv", "diff.external"):
        _git(module, "config", key, str(script))
    entry = sup / "mod" / ".git"
    if spelling != "gitlink file":
        if entry.is_dir() and not entry.is_symlink():
            _shutil.rmtree(entry)
        else:
            entry.unlink()
    if spelling == "symlink to directory":
        os.symlink(module, entry)
    elif spelling == "symlink to gitlink file":
        pointer = sup / "pointer"
        pointer.write_text(f"gitdir: {module}\n")
        os.symlink(pointer, entry)
    elif spelling == "absolute gitlink file":
        entry.write_text(f"gitdir: {module}\n")
    elif spelling == "case variant of the name":
        # THE NAME RULE, ASKED OF A FILESYSTEM THAT DOES NOT COMPARE NAMES AS A
        # STRING COMPARISON DOES. `os.path.lexists(here / ".git")` is answered by
        # the volume, and a case-insensitive one answers YES for `.Git`, while
        # `name != ".git"` answers NO. The build asked both ways, believed both,
        # copied the entry into the view and then collided installing its own.
        entry.write_text(f"gitdir: {module}\n")
        os.rename(entry, sup / "mod" / ".Git")
    (sup / "mod" / "i.txt").write_text("changed in the nested repository\n")
    return sup


def _names_are_case_insensitive(directory) -> bool:
    """Whether THIS volume resolves `.GIT` to `.git`. Measured, because it differs
    between an ordinary macOS volume and an ordinary Linux one, and the answer
    decides whether `.Git` is a repository Git can find at all."""
    probe = Path(directory) / ".case-probe"
    probe.write_text("")
    try:
        return (Path(directory) / ".CASE-PROBE").exists()
    finally:
        probe.unlink()


@pytest.mark.parametrize("spelling", [
    "gitlink file", "absolute gitlink file", "symlink to directory",
    "symlink to gitlink file", "case variant of the name",
])
def test_no_spelling_of_a_nested_git_executes_the_subjects_program(tmp_path, spelling):
    """**The blocker an independent design reading found, before implementation.**

    A nested `.git` that was a SYMLINK to a directory was classified as an
    ordinary directory symlink, copied into the constructed working tree as it
    stood, and pointed Git back at the subject's own configuration — which Git
    ran, on a plain `status --porcelain`.

    The repair was not to add symlinks to a list of layouts. The NAME `.git`
    decides and the kind of the entry never does, which is what this
    parametrisation exists to hold: adding a spelling here must not require
    adding a branch to the subject."""
    if spelling == "case variant of the name" and not _names_are_case_insensitive(tmp_path):
        pytest.skip(
            "this volume compares names case-sensitively, so Git does not find `.Git` either "
            "and the row would carry no positive control"
        )
    script, marker = _marker_script(tmp_path)
    sup = _superproject_with_nested(tmp_path, script, spelling)

    marker.write_bytes(b"")
    _real_git(sup, "status", "--porcelain")
    _real_git(sup, "diff", "--submodule=diff")
    ran_for_real_git = _did_it_run(marker)

    for arguments in (("status", "--porcelain"), ("status", "-v"),
                      ("diff", "--submodule=diff"), ("status", "--porcelain", "-uall")):
        marker.write_bytes(b"")
        answer = gitread.probe(sup, *arguments, negative_statuses=())
        assert answer.answered, f"{arguments}: {answer.cause}"
        assert _did_it_run(marker) == 0, (
            f"a nested .git spelled as a {spelling} executed its own configuration "
            f"under `git {' '.join(arguments)}`"
        )
    # AND THE ANSWER IS STILL THE TRUTH. Not executing is half the property: a
    # build that simply omitted the nested `.git` from the view would also execute
    # nothing, and would describe a repository that is not there. Mutation found
    # that gap — a mutant which dropped a symlinked `.git` from the walk passed
    # every assertion above.
    marker.write_bytes(b"")
    expected, got = _exactly_as_real_git(sup, "status", "--porcelain")
    assert expected is not None, "real git refused the fixture, so this proves nothing"
    assert got == expected, (
        f"a nested .git spelled as a {spelling} changed what the superproject reports"
    )
    assert ran_for_real_git > 0, (
        f"real git ran no program for the {spelling} fixture, so this row carries no "
        f"positive control and proves nothing"
    )


def test_a_nested_git_symlink_is_rebuilt_as_harness_state(tmp_path):
    """A nested `.git` is recognised by its NAME before either walk uses its kind.

    This is the direct, helper-free form of the nested-git guarantee.  A
    gitlink's `.git` is deliberately replaced by a symlink to its own git
    directory, then the sterile builder must replace that spelling in the view
    with a directory it made.  Reverting the repair to ask ``Path.is_dir()``
    and reject symlinks makes the detector miss this entry; no view is built and
    the final ownership assertion fails against the subject's git directory.
    """
    inner = _isolated_committed_repo(tmp_path, "inner")
    superproject = _isolated_committed_repo(tmp_path, "superproject")
    _isolated_git(
        superproject, "-c", "protocol.file.allow=always", "submodule", "add", "-q",
        str(inner), "module",
    )
    _isolated_git(superproject, "commit", "-q", "-m", "add module")
    subject_gitdir = superproject / ".git" / "modules" / "module"
    entry = superproject / "module" / ".git"
    entry.unlink()
    os.symlink(subject_gitdir, entry)

    read = _sterile.build(superproject)
    try:
        assert read.worktree is not None
        rebuilt = read.worktree / "module" / ".git"
        assert os.path.lexists(rebuilt), "the constructed view omitted the nested repository"
        assert rebuilt.is_symlink(), "the rebuilt nested repository is not installed as a gitdir link"
        assert rebuilt.resolve().is_relative_to(read.scratch.resolve()), (
            f"the constructed view points at the subject git directory: {rebuilt.resolve()}"
        )
    finally:
        read.discard()


@pytest.mark.parametrize("kind", ["dangling symlink", "empty file", "fifo"])
def test_a_nested_repository_that_cannot_be_rebuilt_refuses_the_read(tmp_path, kind):
    """Fail-closed, by name. What cannot be rebuilt sterile is not read past: the
    alternative leaves the subject's own git directory reachable from a tree Git
    is about to read."""
    repo = tmp_path / "outer"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit_all(repo)
    nest = repo / "nest"
    nest.mkdir()
    entry = nest / ".git"
    if kind == "dangling symlink":
        os.symlink(tmp_path / "nothing-is-here", entry)
    elif kind == "empty file":
        entry.write_text("")
    else:
        os.mkfifo(entry)
    answer = gitread.probe(repo, "status", "--porcelain", negative_statuses=())
    assert not answer.answered
    assert "could not be rebuilt" in answer.cause
    assert "nest" in answer.cause, (
        "the refusal does not name the repository that caused it, and `probe` reports a "
        "refusal by its cause alone"
    )
    with pytest.raises(GitRefusal) as caught:
        gitread._run(repo, "status", "--porcelain")
    assert caught.value.detail.get("nested") == "nest"


@pytest.mark.parametrize("how", ["copied in", "symlinked out", "dangling"])
def test_a_foreign_git_in_the_view_refuses_the_read(tmp_path, how):
    """The post-condition, on its own, against a view the loop never made.

    The loop that builds the view is an argument; this check is the evidence. It
    must refuse a `.git` that arrived by a route nobody predicted — including one
    COPIED into the build, which an earlier version of this check accepted because
    it only asked whether the entry resolved somewhere under the scratch
    directory. Membership in the set of directories this build actually made is
    what it asks now."""
    subject = tmp_path / "subject"
    (subject / "nest").mkdir(parents=True)
    _git(subject, "init", "-q", "-b", "main") if False else None
    scratch = tmp_path / "scratch"
    view = scratch / "view"
    (view / "nest").mkdir(parents=True)
    foreign = tmp_path / "foreign.git"
    foreign.mkdir()
    (foreign / "config").write_text("[diff]\n\texternal = /bin/echo\n")

    entry = view / "nest" / ".git"
    if how == "copied in":
        _shutil.copytree(foreign, entry)
    elif how == "symlinked out":
        os.symlink(foreign, entry)
    else:
        os.symlink(tmp_path / "nothing-is-here", entry)

    with pytest.raises(Exception) as caught:
        _sterile._every_git_in_the_view_is_ours(view, built=set())
    rendered = str(caught.value) + getattr(caught.value, "cause", "")
    assert "not one this build made" in rendered or "does not resolve" in rendered


# O3 / B15b — over-refusal is the same defect as under-refusal ------------------------

def test_an_unrelated_ignored_checkout_leaves_the_project_readable(tmp_path):
    """**B15b, the other blocker that stopped 2.4.1.** An IGNORED, never-a-submodule
    checkout made the whole project unreadable: real Git exits 0, the guarded read
    refused, and this pack's own `workspace_report` broke on it. Ignored
    dependency caches are ordinary project contents."""
    script, marker = _marker_script(tmp_path)
    repo = tmp_path / "project"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".gitignore").write_text("cache/\n")
    (repo / "src").mkdir()
    (repo / "src" / "m.py").write_text("x = 1\n")
    _commit_all(repo, "keep.txt")
    dependency = repo / "cache" / "dependency"
    dependency.mkdir(parents=True)
    _git(dependency, "init", "-q", "-b", "main")
    _git(dependency, "config", "filter.review.clean", str(script))
    (dependency / "f.txt").write_text("dep\n")
    (repo / "untracked.py").write_text("y = 2\n")

    for arguments in (("status", "--porcelain"), ("status", "--porcelain", "-uall")):
        marker.write_bytes(b"")
        expected, got = _exactly_as_real_git(repo, *arguments)
        assert expected is not None, f"real git refused {arguments}, so this proves nothing"
        assert got == expected, f"`git {' '.join(arguments)}` disagreed with real git"
        assert _did_it_run(marker) == 0
    marker.write_bytes(b"")
    ignored = gitread.probe(repo, "check-ignore", "-v", "cache/dependency/f.txt",
                            negative_statuses=(1,))
    assert ignored.answered and "cache/" in ignored.value
    assert _did_it_run(marker) == 0

    import workspace_report
    classified = workspace_report.classify_workspace(repo, safe_generated=("cache/**",))
    assert classified is not None


# O4 — the invariant, asked of Git rather than asserted -------------------------------

def test_every_configuration_source_git_reports_is_one_the_harness_wrote(tmp_path):
    """**The invariant itself**, and it is checked by asking Git which files it
    read rather than by predicting which it would. A source outside the build
    fails this without anybody having to have thought of it. Reverting the
    `GIT_DIR` repair makes Git rediscover the subject from its working directory,
    so this test reports the subject's `config` as an origin and fails."""
    repo = _isolated_committed_repo(tmp_path, "subject")
    # `config.worktree` rather than `include.path`: a main-config include is now
    # REFUSED, because the root is replaced rather than followed and a storage
    # descriptor inside the included file would otherwise go missing from the
    # answer. `extensions.worktreeConfig` is the other live second root and is
    # still read, so the invariant is still exercised against a real one.
    _git(repo, "config", "extensions.worktreeConfig", "true")
    (repo / ".git" / "config.worktree").write_text(
        "[subject]\n\tsentinel = outside\n", encoding="utf-8")

    read = _sterile.build(repo)
    try:
        listed = subprocess.run(
            ["git", "config", "--list", "--show-origin", "--show-scope"],
            cwd=str(read.cwd), env=read.environment, capture_output=True, text=True,
        )
        assert listed.returncode == 0, listed.stderr
        origins = []
        for line in listed.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[1].startswith("file:"):
                origins.append(parts[1][len("file:"):])
        assert origins, "git reported no configuration source at all, so nothing was checked"
        for origin in origins:
            resolved = os.path.realpath(origin)
            assert resolved.startswith(os.path.realpath(str(read.scratch))), (
                f"git read configuration from {origin}, which this harness did not write"
            )
    finally:
        read.discard()


def test_a_public_overlay_cannot_add_an_unowned_configuration_source(tmp_path):
    """An unowned configuration source is refused at the public boundary.

    Reverting the overlay guard makes Git read this caller-named system file,
    suppress the ordinary untracked answer, and fail the refusal assertion.
    """
    repo = _isolated_committed_repo(tmp_path, "unowned-configuration")
    (repo / "ordinary-untracked.txt").write_text("ordinary\n")
    outside = tmp_path / "unowned-system.gitconfig"
    outside.write_text("[status]\n\tshowUntrackedFiles = no\n")

    with _pytest.raises(_GitRefusal) as raised:
        gitread._run(
            repo, "status", "--porcelain", env_overlay={
                "GIT_CONFIG_NOSYSTEM": "0",
                "GIT_CONFIG_SYSTEM": str(outside),
            },
        )
    rendered = raised.value.render()
    assert "GIT_CONFIG_NOSYSTEM" in rendered and "GIT_CONFIG_SYSTEM" in rendered
    assert gitread._run(repo, "status", "--porcelain") == "?? ordinary-untracked.txt\n"


@pytest.mark.parametrize("route", ("config", "config.worktree", "include.path", "includeIf"))
def test_replacing_the_configuration_root_excludes_every_subject_config_route(tmp_path, route):
    """The subject can only declare another configuration source from `config`.

    `extensions.worktreeConfig` selects `config.worktree`, while `include.path`
    and `includeIf` select their named files.  Each is deliberately live when
    Git reads the subject, then absent when it reads the generated root.  The
    included files themselves are carried as state: their presence is harmless
    because the declaration that reaches them was replaced with the root.
    """
    repo = _committed(tmp_path, route.replace(".", "-"))
    key = f"subject.{route.replace('.', '')}"
    value = f"entered-through-{route}"
    config = repo / ".git" / "config"

    if route == "config":
        with config.open("a", encoding="utf-8") as handle:
            handle.write(f"\n[subject]\n\tconfig = {value}\n")
    elif route == "config.worktree":
        _git(repo, "config", "extensions.worktreeConfig", "true")
        key, value = "subject.worktreeconfig", "entered-through-config.worktree"
        (repo / ".git" / "config.worktree").write_text(
            f"[subject]\n\tworktreeconfig = {value}\n", encoding="utf-8")
    elif route == "include.path":
        (repo / ".git" / "included").write_text(
            f"[subject]\n\tincludepath = {value}\n", encoding="utf-8")
        _git(repo, "config", "include.path", "included")
    else:
        (repo / ".git" / "conditional").write_text(
            f"[subject]\n\tincludeif = {value}\n", encoding="utf-8")
        with config.open("a", encoding="utf-8") as handle:
            handle.write('\n[includeIf "onbranch:main"]\n\tpath = conditional\n')

    assert _git(repo, "config", "--get", key).strip() == value
    if route in ("include.path", "includeIf"):
        # AN INCLUDE IS REFUSED RATHER THAN EXCLUDED, WHICH IS STRICTLY STRONGER.
        # Excluding it kept the read working while silently dropping whatever the
        # included file declared, and a storage descriptor declared there made an
        # ordinary `status` call a clean tracked file modified. Frozen 2.4.0
        # refuses such a repository too, so this is the floor's own answer.
        with _pytest.raises(_GitRefusal) as raised:
            _sterile.build(repo)
        assert "includes another configuration file" in raised.value.render()
        return
    read = _sterile.build(repo)
    try:
        result = subprocess.run(
            ["git", "config", "--get", key], cwd=str(read.cwd), env=read.environment,
            capture_output=True, text=True,
        )
        assert result.returncode == 1 and result.stdout == "", result.stderr
    finally:
        read.discard()


def _fixture_environment(extra=None):
    """The pinned, configuration-free environment for independent fixtures."""
    environment = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_AUTHOR_NAME": "Fixture Author",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture Committer",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2001-01-01T00:00:00+0000",
        "GIT_COMMITTER_DATE": "2001-01-01T00:00:00+0000",
    }
    environment.update(extra or {})
    return environment


def _isolated_git(repo, *args):
    """Construct state without ambient configuration or timestamp variance."""
    return _git(repo, *args, env=_fixture_environment())


def _isolated_real_git(repo, *args):
    """Run the real-Git side under the same pinned fixture environment."""
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_fixture_environment(),
    )


def _isolated_committed_repo(tmp_path, name):
    """An ordinary repository whose state has no ambient-config dependency."""
    repo = tmp_path / name
    repo.mkdir()
    _isolated_git(repo, "init", "-q", "-b", "main")
    _isolated_git(repo, "config", "user.email", "t@e.invalid")
    _isolated_git(repo, "config", "user.name", "T")
    (repo / "f.txt").write_text("one\n")
    _isolated_git(repo, "add", "-A")
    _isolated_git(repo, "commit", "-q", "-m", "first")
    return repo


def _config_records_as_git_list_bytes(config):
    """Render the ordered record view in Git's ``--list --null`` shape."""
    rendered = []
    for name, value in _sterile.config_records_as_data(config):
        key = name.encode("utf-8", "surrogateescape")
        rendered.append(
            key + b"\0" if value is None
            else key + b"\n" + value.encode("utf-8", "surrogateescape") + b"\0"
        )
    return b"".join(rendered)


@pytest.mark.parametrize(
    "shape, contents",
    (
        (
            "empty-comment-header-and-implicit-true",
            b" \t\r\n# a hash comment\n\t; a semicolon comment ending in a backslash \\\n"
            b"[core]  # a header comment\n\tbare\n",
        ),
        ("utf8-bom", b"\xef\xbb\xbf[core]\n\tvalue = bom\n"),
        ("escaped-backslash-value", b'[core]\n\tvalue = "tail\\\\"\n'),
        ("even-trailing-backslashes", b"[core]\n\tvalue = tail\\\\\n"),
        ("odd-backslash-continuation", b"[core]\n\tvalue = left\\\nright\n"),
        (
            "quoted-subsection-escapes",
            b'[remote "quo\\"te\\\\slash"]\n\turl = local\n',
        ),
        ("tab-separated-subsection", b'[branch\t"Topic"]\n\tmerge = refs/heads/main\n'),
        ("crlf", b"[core]\r\n\tfilemode = true\r\n"),
    ),
)
def test_the_strict_configuration_accept_list_agrees_with_git_byte_for_byte(
        tmp_path, shape, contents):
    """The closed positive oracle: accepted input has exactly Git's answer.

    This is intentionally a finite table, not a growing corpus of Git syntax.
    It exercises every accepted construct, including the BOM, CRLF, header and
    comment rules, the two accepted subsection escapes, and the one permitted
    continuation site.  Any configuration outside this table's grammar belongs
    to the refusal oracle below rather than to parser expansion.
    """
    config = tmp_path / f"accepted-{shape}.gitconfig"
    config.write_bytes(contents)

    oracle = subprocess.run(
        ["git", "config", "--file", str(config), "--list", "--null"],
        capture_output=True, check=False,
    )
    assert oracle.returncode == 0, oracle.stderr.decode("utf-8", "surrogateescape")
    assert _config_records_as_git_list_bytes(config) == oracle.stdout


def test_config_records_as_data_preserves_a_valueless_declaration(tmp_path):
    """A bare declaration is a record with no value, as in Git's list stream."""
    config = tmp_path / "valueless.gitconfig"
    config.write_text("[core]\n\tbare\n", encoding="utf-8")

    oracle = subprocess.run(
        ["git", "config", "--file", str(config), "--list", "--null"],
        capture_output=True, check=False,
    )
    assert oracle.returncode == 0, oracle.stderr.decode("utf-8", "surrogateescape")
    assert _sterile.config_records_as_data(config) == [("core.bare", None)]
    assert _config_records_as_git_list_bytes(config) == b"core.bare\0" == oracle.stdout
    # The pre-existing resolved-value views intentionally remain unchanged.
    assert _sterile.config_as_data(config) == {"core.bare": "true"}
    assert _sterile.config_values_as_data(config) == {"core.bare": ["true"]}


def test_config_records_as_data_preserves_an_explicit_true_value(tmp_path):
    """An explicit ``true`` remains distinguishable from a bare declaration."""
    config = tmp_path / "explicit-true.gitconfig"
    config.write_text("[core]\n\tbare = true\n", encoding="utf-8")

    oracle = subprocess.run(
        ["git", "config", "--file", str(config), "--list", "--null"],
        capture_output=True, check=False,
    )
    assert oracle.returncode == 0, oracle.stderr.decode("utf-8", "surrogateescape")
    assert _sterile.config_records_as_data(config) == [("core.bare", "true")]
    assert _config_records_as_git_list_bytes(config) == b"core.bare\ntrue\0" == oracle.stdout
    valueless = tmp_path / "bare-without-equals.gitconfig"
    valueless.write_text("[core]\n\tbare\n", encoding="utf-8")
    assert _sterile.config_records_as_data(valueless) != _sterile.config_records_as_data(config)
    assert _sterile.config_as_data(config) == {"core.bare": "true"}
    assert _sterile.config_values_as_data(config) == {"core.bare": ["true"]}


def test_config_records_as_data_preserves_interleaved_repeated_key_occurrences(tmp_path):
    """Records retain Git's declaration order instead of grouping repeated keys."""
    config = tmp_path / "interleaved-repeated.gitconfig"
    config.write_text("[core]\n\ta = one\n\tb = bee\n\ta = two\n", encoding="utf-8")

    oracle = subprocess.run(
        ["git", "config", "--file", str(config), "--list", "--null"],
        capture_output=True, check=False,
    )
    assert oracle.returncode == 0, oracle.stderr.decode("utf-8", "surrogateescape")
    assert _sterile.config_records_as_data(config) == [
        ("core.a", "one"),
        ("core.b", "bee"),
        ("core.a", "two"),
    ]
    assert (_config_records_as_git_list_bytes(config)
            == b"core.a\none\0core.b\nbee\0core.a\ntwo\0" == oracle.stdout)
    assert _sterile.config_as_data(config) == {"core.a": "two", "core.b": "bee"}
    assert _sterile.config_values_as_data(config) == {
        "core.a": ["one", "two"],
        "core.b": ["bee"],
    }


def test_a_nul_byte_in_a_configuration_is_refused_with_its_file_and_line(tmp_path):
    """NUL is refused rather than approximating Git's truncating list stream."""
    config = tmp_path / "nul-value.gitconfig"
    config.write_bytes(b"[core]\nvalue = x\0y\n")

    oracle = subprocess.run(
        ["git", "config", "--file", str(config), "--list", "--null"],
        capture_output=True, check=False,
    )
    assert oracle.returncode == 0, oracle.stderr.decode("utf-8", "surrogateescape")
    assert oracle.stdout == b"core.value\nx\0"

    with _pytest.raises(_GitRefusal) as raised:
        _sterile.config_records_as_data(config)
    assert raised.value.detail["configuration"] == str(config)
    assert raised.value.detail["line"] == 2
    assert "NUL byte" in raised.value.render()


@pytest.mark.parametrize(
    "shape, contents, line",
    (
        ("unclosed-header", b"[core\n", 1),
        ("legacy-dotted-section", b"[core.foo]\n\tvalue = yes\n", 1),
        ("header-with-variable", b"[core] value = yes\n", 1),
        ("stray-token", b"[core]\n\tvalue then more\n", 2),
        ("bad-variable-name", b"[core]\n\t1value = yes\n", 2),
        ("unterminated-continuation", b"[core]\n\tvalue = last\\", 2),
        ("unquoted-recognised-escape", b"[core]\n\tvalue = a\\tb\n", 2),
        ("quoted-unknown-escape", b'[core]\n\tvalue = "a\\xb"\n', 2),
    ),
)
def test_the_strict_configuration_refusal_list_names_its_file_and_line(
        tmp_path, shape, contents, line):
    """The closed negative oracle: an unlisted spelling never becomes data."""
    config = tmp_path / f"rejected-{shape}.gitconfig"
    config.write_bytes(contents)

    with _pytest.raises(_GitRefusal) as raised:
        _sterile.config_as_data(config)
    assert raised.value.detail["configuration"] == str(config)
    assert raised.value.detail["line"] == line


def test_a_bom_before_include_is_seen_and_refused(tmp_path):
    """BOM removal occurs before include detection, never before key matching."""
    repo = _isolated_committed_repo(tmp_path, "bom-include")
    config = repo / ".git" / "config"
    config.write_bytes(b"\xef\xbb\xbf[include]\n\tpath = unseen.gitconfig\n")

    with _pytest.raises(_GitRefusal) as raised:
        gitread._run(repo, "status", "--porcelain")
    assert "includes another configuration file" in raised.value.render()


@pytest.mark.parametrize("trailing_backslashes", (2, 3))
def test_even_and_triple_trailing_backslashes_route_ls_remote_like_git(
        tmp_path, trailing_backslashes):
    """Only the last backslash in an odd run continues a value physical line."""
    target = _isolated_committed_repo(tmp_path, "backslash-target\\")
    reader = _isolated_committed_repo(tmp_path, f"backslash-reader-{trailing_backslashes}")
    config = reader / ".git" / "config"
    address = str(target)
    with config.open("a", encoding="utf-8") as handle:
        handle.write(f'\n[remote "origin"]\n\turl = {address}')
        handle.write("\\" * (trailing_backslashes - 1))
        handle.write("\n")
        if trailing_backslashes == 3:
            handle.write("\n")

    oracle = _isolated_real_git(reader, "ls-remote", "origin", "HEAD")
    assert oracle.returncode == 0, oracle.stderr
    actual = gitread._run(reader, "ls-remote", "origin", "HEAD", text=False)
    assert actual == oracle.stdout.encode("utf-8", "surrogateescape")


def test_a_comment_ending_in_a_backslash_does_not_consume_the_next_header(tmp_path):
    config = tmp_path / "comment-does-not-continue.gitconfig"
    config.write_bytes(b"# comment ends here \\\n[core]\n\tfilemode = true\n")
    assert _sterile.config_as_data(config) == {"core.filemode": "true"}


def test_a_trailing_value_comment_ending_in_a_backslash_does_not_continue(tmp_path):
    config = tmp_path / "value-comment-does-not-continue.gitconfig"
    config.write_bytes(b"[core]\n\tvalue = kept # comment ends here \\\n\tfilemode = true\n")
    assert _sterile.config_as_data(config) == {
        "core.value": "kept",
        "core.filemode": "true",
    }


def test_a_header_ending_in_a_backslash_does_not_consume_the_next_line(tmp_path):
    config = tmp_path / "header-does-not-continue.gitconfig"
    config.write_bytes(b"[core] # header ends here \\\n\tfilemode = true\n")
    assert _sterile.config_as_data(config) == {"core.filemode": "true"}


def test_invalid_configuration_grammar_refuses_instead_of_answering_cleanly(tmp_path):
    repo = _isolated_committed_repo(tmp_path, "invalid-grammar")
    config = repo / ".git" / "config"
    with config.open("a", encoding="utf-8") as handle:
        handle.write("\n[core] this-is-not-a-variable = true\n")

    with _pytest.raises(_GitRefusal) as raised:
        gitread._run(repo, "status", "--porcelain")
    assert raised.value.detail["configuration"] == str(config)
    assert raised.value.detail["line"] > 0


@pytest.mark.parametrize(
    "shape, spelling",
    (
        ("quoted", '"quoted value"'),
        ("unquoted", "unquoted value"),
        ("embedded-hash", '"left#right"'),
        ("embedded-semicolon", '"left;right"'),
        ("embedded-quote", r'"said \"hello\""'),
        ("backslash-escapes", r'"quote \" slash \\ newline \n tab \t backspace \b"'),
        ("trailing-hash-comment", "plain value # ignored"),
        ("trailing-semicolon-comment", "plain value ; ignored"),
        ("mixed-quoted-unquoted", 'a"b c"d'),
        ("quoted-leading-trailing-space", '   "  kept at both edges  "   '),
    ),
)
def test_config_as_data_value_syntax_matches_real_git_byte_for_byte(tmp_path, shape, spelling):
    """Every listed VALUE spelling agrees with ``git config --get`` byte for byte.

    The repository config is written with the spelling under test and real Git
    is the oracle. Reverting the value decoder to the previous ``value.strip``
    implementation makes every quoted, escaped, mixed, or quoted-comment case
    fail; unquoted values and outside-comment controls remain passing controls.
    """
    repo = tmp_path / f"value-{shape}"
    repo.mkdir()
    _isolated_git(repo, "init", "-q", "-b", "main")
    config = repo / ".git" / "config"
    config.write_text(f"[oracle]\n\tvalue = {spelling}\n", encoding="utf-8")

    oracle = subprocess.run(
        ["git", "config", "--null", "--get", "oracle.value"], cwd=str(repo),
        capture_output=True, check=False, env=_fixture_environment(),
    )
    assert oracle.returncode == 0, oracle.stderr.decode("utf-8", "surrogateescape")
    assert oracle.stdout.endswith(b"\0")
    actual = _sterile.config_as_data(config)["oracle.value"].encode("utf-8", "surrogateescape")
    assert actual == oracle.stdout[:-1], shape


def test_config_as_data_either_matches_git_or_refuses_differential_fuzz(tmp_path):
    """Fixed-seed differential oracle: seed 0x2F50, 512 configuration files.

    The small grammar varies BOM and CRLF spellings, comments, quoted
    subsections, physical continuations, NUL bytes in values and elsewhere,
    and recognised and unrecognised backslashes both inside and outside quotes.
    It also emits bare
    declarations and repeated keys interleaved with another key.  The ordered
    record view is rendered in the same ``--list --null`` shape as Git.  Every
    case must do exactly one of two things: agree byte-for-byte with real Git
    or raise the named refusal.  In particular, accepting an unquoted escape
    is not an approximation this parser is allowed to make.
    """
    seed = 0x2F50
    cases = 512
    generator = random.Random(seed)
    sections = (
        "[core]",
        '[remote "origin"]',
        r'[remote "quo\"te"]',
        r'[remote "slash\\name"]',
        r'[remote "unknown\x"]',
        "[co\0re]",
    )
    values = (
        "plain",
        "plain value",
        '"quoted # ; value"',
        r'"quote \" slash \\ newline \n tab \t backspace \b"',
        r'"unknown \x escape"',
        r'unquoted\tknown',
        r'unquoted\"known',
        r'C:\temp\x',
        "continued",
        "trailing-run",
        '"unclosed',
        "nul\0value",
    )
    comments = ("", "# ignored comment", "; ignored slash \\", "\0comment")
    saw_nul_in_value = False
    saw_nul_elsewhere = False
    for number in range(cases):
        newline = "\r\n" if generator.randrange(2) else "\n"
        prefix = "\ufeff" if generator.randrange(2) else ""
        comment = generator.choice(comments)
        section = generator.choice(sections)
        value = generator.choice(values)
        saw_nul_in_value |= "\0" in value
        saw_nul_elsewhere |= "\0" in prefix + comment + section
        def assignment_for(key):
            if value == "continued":
                return f"{key} = left\\" + newline + "right"
            if value == "trailing-run":
                return f"{key} = tail\\\\"
            return f"{key} = {value}"

        # Cycling guarantees that this fixed corpus exercises both kinds of
        # information the former grouped views discarded, while its seeded
        # choices retain every pre-existing header, comment, and value shape.
        declaration_shape = number % 3
        if declaration_shape == 0:
            declarations = (assignment_for("value"),)
        elif declaration_shape == 1:
            declarations = ("bare", assignment_for("value"))
        else:
            declarations = ("a = one", "b = bee", assignment_for("a"))
        contents = (prefix + (comment + newline if comment else "") + section + newline
                    + newline.join(declarations) + newline)
        config = tmp_path / f"differential-{number}.gitconfig"
        config.write_bytes(contents.encode("utf-8", "surrogateescape"))
        oracle = subprocess.run(
            ["git", "config", "--file", str(config), "--list", "--null"],
            capture_output=True, check=False,
        )
        try:
            actual = _config_records_as_git_list_bytes(config)
            refused = False
        except _GitRefusal:
            actual = None
            refused = True
        matches = not refused and oracle.returncode == 0 and actual == oracle.stdout
        assert int(refused) + int(matches) == 1, (
            f"seed {seed:#x}, case {number}: parser neither refused nor agreed; "
            f"git returncode={oracle.returncode}, contents={contents!r}, "
            f"actual={actual!r}, expected={oracle.stdout!r}"
        )
    assert saw_nul_in_value and saw_nul_elsewhere, (
        f"seed {seed:#x} must cover NUL bytes both in values and elsewhere"
    )


def test_config_records_as_data_exhaustively_agrees_or_refuses_value_bodies(tmp_path):
    """Exhaust every VALUE body through length 4 over 10 boundary characters.

    The alphabet is SPACE, TAB, CR, LF, BACKSLASH, DOUBLE QUOTE, HASH,
    SEMICOLON, NUL, and ``a``. Lengths zero through four contain exactly
    11,111 bodies. In particular this
    covers bare CR and whitespace-before-continuation without relying on a
    random generator to happen to emit either shape.  The fixed-seed corpus
    above remains because it explores headers, BOMs, CRLF, and declarations
    that this deliberately one-value-body enumeration does not.
    """
    alphabet = (b" ", b"\t", b"\r", b"\n", b"\\", b'"', b"#", b";", b"\0", b"a")
    maximum_length = 4
    expected_cases = sum(len(alphabet) ** length for length in range(maximum_length + 1))
    assert expected_cases == 11_111
    config = tmp_path / "exhaustive-value-body.gitconfig"
    number = 0
    for length in range(maximum_length + 1):
        for pieces in itertools.product(alphabet, repeat=length):
            body = b"".join(pieces)
            contents = b"[core]\n\tvalue = " + body + b"\n"
            config.write_bytes(contents)
            oracle = subprocess.run(
                ["git", "config", "--file", str(config), "--list", "--null"],
                capture_output=True, check=False,
            )
            try:
                actual = _config_records_as_git_list_bytes(config)
            except _GitRefusal:
                refused = True
                actual = None
            else:
                refused = False
            matches = oracle.returncode == 0 and actual == oracle.stdout
            assert refused != matches, (
                f"exhaustive value case {number}/{expected_cases}: parser "
                f"{'refused' if refused else 'answered'} and Git returncode={oracle.returncode}; "
                f"body={body!r}, actual={actual!r}, expected={oracle.stdout!r}"
            )
            number += 1
    assert number == expected_cases


@pytest.mark.parametrize("contents, expected", (
    (b"[core]\n\tk = a\r\\\n; c\n", b"core.k\na\r\0"),
    (b"[core]\n\tk = a\r\\\n \t\n", b"core.k\na\r\0"),
    (b"[core]\n\tk = a\\\n\r\r\n", b"core.k\na\0"),
    (b"[core]\n\tk = a\r\\\n\r\r\n", b"core.k\na\r\0"),
    (b"[core]\n\tk = a\\\n\tk = \"\"\n", b"core.k\na\tk = \0"),
))
def test_a_continuation_cannot_erase_preceding_value_data(tmp_path, contents, expected):
    """Physical continuation syntax cannot turn earlier data into edge whitespace."""
    config = tmp_path / "continued.gitconfig"
    config.write_bytes(contents)
    oracle = subprocess.run(
        ["git", "config", "--file", str(config), "--list", "--null"],
        capture_output=True, check=False,
    )
    assert oracle.returncode == 0
    assert oracle.stdout == expected
    assert _config_records_as_git_list_bytes(config) == oracle.stdout


def test_an_empty_quoted_run_preserves_the_remote_address_whitespace(tmp_path):
    """A governed transport must not resolve a different address from real Git."""
    donor = _committed(tmp_path, "quoted-donor")
    repo = _committed(tmp_path, "quoted-subject")
    config = repo / ".git" / "config"
    with config.open("a") as stream:
        stream.write(f'[remote "wrong"]\n\turl = {donor} ""\n')

    listed = subprocess.run(
        ["git", "config", "--file", str(config), "--list", "--null"],
        capture_output=True, check=True,
    )
    assert b"remote.wrong.url\n" + str(donor).encode() + b" \0" in listed.stdout
    with pytest.raises(GitRefusal):
        gitread._run(repo, "ls-remote", "wrong", text=False)


def test_a_used_clean_filter_refuses_before_disclosing_worktree_content(tmp_path):
    """Dropping an active clean filter made a clean file dirty and exposed it."""
    repo = _committed(tmp_path, "clean-filter")
    _git(repo, "config", "filter.redact.clean", "sed s/SECRET/REDACTED/")
    (repo / ".gitattributes").write_text("*.txt filter=redact\n")
    (repo / "filtered.txt").write_text("value=SECRET\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "filtered")
    assert _git(repo, "status", "--porcelain") == ""
    assert _git(repo, "show", "HEAD:filtered.txt") == "value=REDACTED\n"
    with pytest.raises(GitRefusal) as raised:
        gitread._run(repo, "diff", text=False)
    assert "content filter" in raised.value.render()
    assert "filter.redact.clean" in raised.value.render()


@pytest.mark.parametrize("key,arguments", (
    ("core.excludesFile", ("status", "--porcelain")),
    ("status.showUntrackedFiles", ("status", "--porcelain")),
    ("core.attributesFile", ("diff",)),
    ("core.abbrev", ("log", "--oneline", "-1")),
))
def test_answer_shaping_configuration_refuses_instead_of_being_dropped(
    tmp_path, key, arguments,
):
    """Each known answer-shaping declaration reaches one named fail-closed rule."""
    repo = _committed(tmp_path, "answer-shaping")
    if key == "core.excludesFile":
        declaration = repo / "declared-ignore"
        declaration.write_text("*.tmp\n")
        _git(repo, "config", key, str(declaration))
        (repo / "hidden.tmp").write_text("hidden\n")
        (repo / "visible").write_text("visible\n")
        assert _git(repo, *arguments) == "?? declared-ignore\n?? visible\n"
    elif key == "status.showUntrackedFiles":
        _git(repo, "config", key, "no")
        (repo / "hidden").write_text("hidden\n")
        assert _git(repo, *arguments) == ""
    elif key == "core.attributesFile":
        declaration = repo / "declared-attributes"
        declaration.write_text("*.txt -diff\n")
        _git(repo, "config", key, str(declaration))
        (repo / "f.txt").write_text("changed\n")
        assert "Binary files" in _git(repo, *arguments)
    else:
        _git(repo, "config", key, "12")
        assert len(_git(repo, *arguments).split()[0]) == 12
    with pytest.raises(GitRefusal) as raised:
        gitread._run(repo, *arguments, text=False)
    assert "answer-shaping configuration" in raised.value.render()
    assert key.lower() in raised.value.render()


@pytest.mark.parametrize("key,value", (
    ("core.abbrev", "12"),
    ("filter.redact.clean", "sed s/SECRET/REDACTED/"),
))
def test_active_worktree_answer_shaping_configuration_is_also_refused(
    tmp_path, key, value,
):
    """An active second configuration root cannot bypass either refusal class."""
    repo = _committed(tmp_path, "worktree-answer-shaping")
    _git(repo, "config", "extensions.worktreeConfig", "true")
    _git(repo, "config", "--worktree", key, value)
    if key == "core.abbrev":
        assert len(_git(repo, "rev-parse", "--short", "HEAD").strip()) == 12
    else:
        (repo / ".gitattributes").write_text("filtered.txt filter=redact\n")
        (repo / "filtered.txt").write_text("value=SECRET\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "filtered")
        assert _git(repo, "status", "--porcelain") == ""
    with pytest.raises(GitRefusal) as raised:
        gitread._run(repo, "status", "--porcelain", text=False)
    assert key.split(".", 1)[0] in raised.value.render()


@pytest.mark.parametrize("source", ("gitmodules", "local-config"))
def test_a_submodule_ignore_declaration_refuses_before_dirty_state_is_invented(
    tmp_path, source,
):
    """Neither configuration source can silently suppress submodule dirt."""
    sup, _marker = _superproject(tmp_path, "ignored-submodule")
    if source == "gitmodules":
        _git(sup, "config", "-f", ".gitmodules", "submodule.sub.ignore", "all")
        _git(sup, "add", ".gitmodules")
        _git(sup, "commit", "-qm", "ignore submodule dirt")
    else:
        _git(sup, "config", "submodule.sub.ignore", "all")
    (sup / "sub" / "s.txt").write_text("dirty\n")
    assert _git(sup, "status", "--porcelain") == ""
    with pytest.raises(GitRefusal) as raised:
        gitread._run(sup, "status", "--porcelain", text=False)
    expected = (
        "submodule declares an ignore policy"
        if source == "gitmodules" else "answer-shaping configuration"
    )
    assert expected in raised.value.render()
    assert "sub" in raised.value.render()


def test_a_submodule_ignore_declaration_does_not_refuse_an_uninitialised_gitlink(
    tmp_path,
):
    """An ignore declaration has no child answer to shape until the child exists.

    Real Git and frozen 2.4.0 both report this cross-product clean. Replacing
    the population test with a bare gitlink test makes this oracle fail.
    """
    sup, _marker = _superproject(tmp_path, "uninitialised-ignored", populate=False)
    _git(sup, "config", "-f", ".gitmodules", "submodule.sub.ignore", "all")
    _git(sup, "add", ".gitmodules")
    _git(sup, "commit", "-qm", "declare ignore for uninitialised child")
    assert not os.path.lexists(sup / "sub" / ".git")

    expected, governed = _exactly_as_real_git(sup, "status", "--porcelain")
    assert expected == "", "real Git did not report the uninitialised fixture clean"
    assert governed == expected


def test_read_only_subject_git_state_is_writable_only_in_private_scratch(tmp_path):
    """Source permissions cannot prevent construction or be changed by a read.

    Without scratch normalisation, copied git state remains read-only and the
    harness-owned configuration cannot be written. The mode snapshot also
    proves that the repair never writes through to the subject.
    """
    repo = _committed(tmp_path, "read-only-git-state")
    gitdir = repo / ".git"
    paths = [gitdir, *gitdir.rglob("*")]
    original = {path: stat.S_IMODE(path.lstat().st_mode) for path in paths}
    try:
        for path in sorted(paths, key=lambda item: len(item.parts), reverse=True):
            if not path.is_symlink():
                path.chmod(0o555 if path.is_dir() else 0o444)
        locked = {path: stat.S_IMODE(path.lstat().st_mode) for path in paths}
        assert locked[gitdir] == 0o555 and locked[gitdir / "index"] == 0o444

        expected, governed = _exactly_as_real_git(repo, "status", "--porcelain")
        assert expected == "", "real Git did not read the locked fixture"
        assert governed == expected
        assert {path: stat.S_IMODE(path.lstat().st_mode) for path in paths} == locked

        read = _sterile.build(repo)
        try:
            scratch = Path(read.gitdir)
            assert stat.S_IMODE(scratch.stat().st_mode) & stat.S_IWUSR
            assert stat.S_IMODE((scratch / "index").stat().st_mode) & stat.S_IWUSR
        finally:
            read.discard()
    finally:
        for path in sorted(paths, key=lambda item: len(item.parts)):
            if path.exists() and not path.is_symlink():
                path.chmod(original[path])


@pytest.mark.parametrize("contents", (
    b"[core]\n\tv = \rab\n",
    b"[core]\n\tv = ab\r",
))
def test_a_bare_carriage_return_at_a_value_edge_matches_git_byte_for_byte(tmp_path, contents):
    """Git trims bare CR at either unquoted value edge, so the parser must too."""
    config = tmp_path / "bare-carriage-return.gitconfig"
    config.write_bytes(contents)

    oracle = subprocess.run(
        ["git", "config", "--file", str(config), "--list", "--null"],
        capture_output=True, check=False,
    )
    assert oracle.returncode == 0
    assert oracle.stdout == b"core.v\nab\0"
    assert _config_records_as_git_list_bytes(config) == oracle.stdout


def test_a_tab_separated_includeif_header_is_refused_not_reported_as_complete(tmp_path):
    """Git accepts a TAB before an includeIf subsection, and applies its file.

    The generated configuration cannot reproduce included storage descriptors,
    so this route must refuse rather than list only the main file and call that
    partial list complete.  Replacing header whitespace with literal-space-only
    parsing makes `config_with_origin` return at exit zero after the real-Git
    control below has established that `core.bare` came from the include.
    """
    repo = _isolated_committed_repo(tmp_path, "tab-includeif")
    config = repo / ".git" / "config"
    included = repo / ".git" / "storage.inc"
    included.write_text("[core]\n\tbare = true\n", encoding="utf-8")
    with config.open("a", encoding="utf-8") as handle:
        handle.write(
            f'\n[includeIf\t"gitdir:{(repo / ".git").resolve()}"]\n'
            f"\tpath = {included}\n"
        )

    oracle = _isolated_real_git(repo, "config", "--get", "core.bare")
    assert oracle.returncode == 0, oracle.stderr
    assert oracle.stdout == "true\n", "the TAB form did not make Git apply the include"

    with _pytest.raises(_GitRefusal) as raised:
        gitread.config_with_origin(repo)
    assert "did not follow the include" in raised.value.render()


def test_a_continued_remote_url_reaches_the_same_address_as_real_git(tmp_path):
    """A trailing backslash unfolds a remote URL before the transport resolver sees it.

    The old physical-line parser kept the backslash and routed `origin` to a
    different address.  This asks both implementations for the remote's HEAD;
    no URL is merely inspected without being consumed by the governed route.
    """
    target = _isolated_committed_repo(tmp_path, "continued-target")
    reader = _isolated_committed_repo(tmp_path, "continued-reader")
    config = reader / ".git" / "config"
    address = str(target)
    with config.open("a", encoding="utf-8") as handle:
        handle.write('\n[remote "origin"]\n\turl = ' + address[:-2] + chr(92)
                     + "\n" + address[-2:] + "\n")

    oracle = _isolated_real_git(reader, "ls-remote", "origin", "HEAD")
    assert oracle.returncode == 0, oracle.stderr
    actual = gitread._run(reader, "ls-remote", "origin", "HEAD", text=False)
    assert actual == oracle.stdout.encode("utf-8", "surrogateescape")


def test_a_malformed_header_is_refused_by_the_data_parser_and_governed_report(tmp_path):
    """A bare opening bracket is invalid to Git and cannot become a data answer.

    Calling `config_with_origin` alone would be vacuous here because its later
    real-Git invocation also refuses.  `program_valued_config` consumes the
    pure parser directly, so both assertions below prove that the handwritten
    parser, not an incidental subprocess failure, refuses the malformed root.
    """
    repo = _isolated_committed_repo(tmp_path, "malformed-header")
    config = repo / ".git" / "config"
    with config.open("a", encoding="utf-8") as handle:
        handle.write("\n[broken\n")

    oracle = _isolated_real_git(repo, "config", "--list")
    assert oracle.returncode == 128
    assert "bad config line" in oracle.stderr

    with _pytest.raises(_GitRefusal) as raised:
        _sterile.config_as_data(config)
    assert raised.value.detail["line"] > 0
    with _pytest.raises(_GitRefusal):
        gitread.program_valued_config(repo)


def test_an_escaped_quote_in_a_remote_subsection_reaches_the_same_address_as_git(tmp_path):
    """Quoted subsection escapes are decoded before a remote name is resolved."""
    target = _isolated_committed_repo(tmp_path, "escaped-subsection-target")
    reader = _isolated_committed_repo(tmp_path, "escaped-subsection-reader")
    config = reader / ".git" / "config"
    with config.open("a", encoding="utf-8") as handle:
        handle.write('\n[remote "foo' + chr(92) + f'"bar"]\n\turl = {target}\n')

    oracle = _isolated_real_git(reader, "ls-remote", 'foo"bar', "HEAD")
    assert oracle.returncode == 0, oracle.stderr
    actual = gitread._run(reader, "ls-remote", 'foo"bar', "HEAD", text=False)
    assert actual == oracle.stdout.encode("utf-8", "surrogateescape")


def test_config_parser_keeps_non_newline_separators_that_git_keeps_in_a_value(tmp_path):
    """FF and an interior quoted CR remain data, as Git renders them.

    Byte reads remain load-bearing: universal-newline translation cannot conceal
    either spelling before the parser preserves Git's value semantics.
    """
    repo = _isolated_committed_repo(tmp_path, "form-feed")
    config = repo / ".git" / "config"
    with config.open("a", encoding="utf-8") as handle:
        handle.write('\n[remote "origin"]\n\turl = "a\fb"\n')

    oracle = subprocess.run(
        ["git", "config", "--null", "--get", "remote.origin.url"], cwd=str(repo),
        capture_output=True, check=False, env=_fixture_environment(),
    )
    assert oracle.returncode == 0
    assert oracle.stdout == b"a\x0cb\0"
    actual = _sterile.config_as_data(config)["remote.origin.url"]
    assert actual.encode("utf-8", "surrogateescape") == oracle.stdout[:-1]

    with config.open("a", encoding="utf-8") as handle:
        handle.write('\tvalue = "a\fb\rc"\n')
    quoted = subprocess.run(
        ["git", "config", "--file", str(config), "--list", "--null"],
        capture_output=True, check=False,
    )
    assert quoted.returncode == 0
    assert _config_records_as_git_list_bytes(config) == quoted.stdout


def test_ls_remote_remote_name_with_a_quoted_hash_url_matches_real_git(tmp_path):
    """A remote URL Git quoted for ``#`` reaches the same remote as real Git.

    Reverting the value decoder leaves the opening quote in the address and
    truncates it at ``#``; the governed ``ls-remote origin`` then raises its
    invocation refusal instead of producing this byte-identical answer.
    """
    remote = _isolated_committed_repo(tmp_path, "remote#hash")
    reader = _isolated_committed_repo(tmp_path, "reader")
    _isolated_git(reader, "remote", "add", "origin", str(remote))
    config = reader / ".git" / "config"
    assert f'url = "{remote}"' in config.read_text(encoding="utf-8")

    oracle = subprocess.run(
        ["git", "ls-remote", "origin"], cwd=str(reader), capture_output=True,
        check=False, env=_fixture_environment(),
    )
    assert oracle.returncode == 0, oracle.stderr.decode("utf-8", "surrogateescape")
    actual = gitread._run(reader, "ls-remote", "origin")
    assert actual.encode("utf-8", "surrogateescape") == oracle.stdout


def test_the_reflog_is_carried_for_log_g(tmp_path):
    """A previous short list omitted `logs/`, making `log -g` answer empty."""
    repo = _isolated_committed_repo(tmp_path, "reflog")
    assert gitread._run(repo, "log", "-g", "-1", "--format=%s") == "first\n"


def test_the_reflog_is_carried_for_head_at_one(tmp_path):
    """`HEAD@{1}` is state in the reflog, not a ref this build can reconstruct."""
    repo = _isolated_committed_repo(tmp_path, "head-at-one")
    first = _isolated_git(repo, "rev-parse", "HEAD").strip()
    (repo / "f.txt").write_text("two\n")
    _isolated_git(repo, "add", "-A")
    _isolated_git(repo, "commit", "-q", "-m", "second")
    assert gitread._run(repo, "rev-parse", "HEAD@{1}") == first + "\n"


def test_the_merge_head_pseudoref_is_carried(tmp_path):
    """A merge in progress records its other head as git-directory state."""
    repo = _isolated_committed_repo(tmp_path, "merge-head")
    head = _isolated_git(repo, "rev-parse", "HEAD").strip()
    (repo / ".git" / "MERGE_HEAD").write_text(head + "\n", encoding="utf-8")
    assert gitread._run(repo, "rev-parse", "MERGE_HEAD") == head + "\n"


def test_info_grafts_is_carried_for_history_walks(tmp_path):
    """A graft changes ancestry even though it is neither a ref nor configuration."""
    repo = _isolated_committed_repo(tmp_path, "grafts")
    for number in (2, 3):
        (repo / "f.txt").write_text(f"{number}\n")
        _isolated_git(repo, "add", "-A")
        _isolated_git(repo, "commit", "-q", "-m", f"commit {number}")
    head = _isolated_git(repo, "rev-parse", "HEAD").strip()
    (repo / ".git" / "info" / "grafts").write_text(head + "\n", encoding="utf-8")
    assert gitread._run(repo, "rev-list", "--count", "HEAD") == "1\n"


def test_a_bare_subject_is_rebuilt_as_bare_and_preserves_read_capabilities(tmp_path):
    """A bare git directory is not a working tree containing Git internals."""
    source = _isolated_committed_repo(tmp_path, "source")
    (source / "f.txt").write_text("two\n")
    _isolated_git(source, "add", "f.txt")
    _isolated_git(source, "commit", "-q", "-m", "second")
    bare = tmp_path / "subject.git"
    bare.mkdir()
    _isolated_git(bare, "init", "-q", "--bare")
    _isolated_git(bare, "fetch", "-q", str(source), "main:refs/heads/main")
    _isolated_git(bare, "symbolic-ref", "HEAD", "refs/heads/main")

    for arguments in (
        ("rev-list", "HEAD"),
        ("show", "--format=raw", "HEAD"),
        ("diff-tree", "-r", "HEAD"),
        ("diff-index", "--cached", "HEAD"),
    ):
        expected = _real_git(bare, *arguments)
        assert expected.returncode == 0, (arguments, expected.stderr)
        assert gitread._run(bare, *arguments) == expected.stdout

    for arguments in (("status",), ("ls-files", "--deleted"),
                      ("ls-files", "--modified"),
                      ("ls-files", "--others", "--exclude-standard")):
        with pytest.raises(GitRefusal):
            gitread._run(bare, *arguments)


def test_a_bare_shaped_git_directory_with_a_declared_worktree_is_not_bare(tmp_path):
    """A bare-shaped git directory can legitimately describe another worktree.

    Reverting to the structural bare predicate sets the constructed config bare
    and refuses this ordinary status.  The source repository and the bare
    subject are built independently so the comparison is not self-fulfilling.
    """
    source = _isolated_committed_repo(tmp_path, "hybrid-source")
    subject = tmp_path / "hybrid.git"
    copied = subprocess.run(
        ["git", "clone", "--bare", str(source), str(subject)], capture_output=True, text=True,
        env=_fixture_environment(),
    )
    assert copied.returncode == 0, copied.stderr
    worktree = tmp_path / "hybrid-worktree"
    worktree.mkdir()
    _isolated_git(subject, "config", "core.bare", "false")
    _isolated_git(subject, "config", "core.worktree", str(worktree))
    checked_out = subprocess.run(
        ["git", "checkout", "-q", "-f", "main"], cwd=str(subject), capture_output=True, text=True,
        env=_fixture_environment({"GIT_DIR": str(subject), "GIT_WORK_TREE": str(worktree)}),
    )
    assert checked_out.returncode == 0, checked_out.stderr
    (worktree / "f.txt").write_text("changed\n")

    expected = _isolated_real_git(subject, "status", "--porcelain")
    assert expected.returncode == 0 and expected.stdout == " M f.txt\n", expected.stderr
    assert not _sterile._is_bare(subject)
    assert gitread._run(subject, "status", "--porcelain") == expected.stdout


def test_a_dangling_dot_git_link_does_not_make_a_directory_look_bare(tmp_path):
    """A dangling `.git` entry is not an absent `.git` entry.

    Reverting to ``Path.exists()`` makes this bare-shaped directory classify as
    bare and answer ``HEAD``; the repaired classification refuses the broken
    git-directory entry by name.
    """
    subject = tmp_path / "dangling-dot-git"
    subject.mkdir()
    _isolated_git(subject, "init", "-q", "--bare")
    (subject / ".git").symlink_to("missing-git-directory")

    assert not _sterile._is_bare(subject)
    with _pytest.raises(_GitRefusal) as raised:
        gitread._run(subject, "rev-parse", "HEAD")
    assert ".git entry" in str(raised.value.cause), raised.value.cause


def test_a_symlinked_head_is_materialised_without_detaching_it(tmp_path):
    """A symlinked HEAD becomes a plain symbolic-ref file in the build.

    Reverting symbolic-ref materialisation copies the target hash into HEAD,
    which makes this branch look detached and changes each branch-aware status
    form despite leaving no symlink in the constructed directory.
    """
    repo = _isolated_committed_repo(tmp_path, "head-link")
    head = repo / ".git" / "HEAD"
    head.unlink()
    head.symlink_to("refs/heads/main")
    expected = _isolated_real_git(repo, "status", "--porcelain=v2", "--branch")
    assert expected.returncode == 0 and "# branch.head main" in expected.stdout, expected.stderr

    read = _sterile.build(repo)
    try:
        rebuilt_head = read.gitdir / "HEAD"
        assert not rebuilt_head.is_symlink()
        assert rebuilt_head.read_text(encoding="utf-8") == "ref: refs/heads/main\n"
    finally:
        read.discard()
    assert gitread._run(repo, "status", "--porcelain=v2", "--branch") == expected.stdout


# O5 — a store this build cannot import refuses rather than answering -----------------

def test_a_ref_store_the_build_cannot_import_is_refused_not_answered(tmp_path):
    """Without this the worst failure available to a read happened: a `reftable`
    subject reported every tracked file as newly ADDED, at exit 0. Two unknowns
    comparing equal is not agreement."""
    repo = tmp_path / "reftable-subject"
    repo.mkdir()
    created = subprocess.run(["git", "init", "-q", "-b", "main", "--ref-format=reftable", "."],
                             cwd=str(repo), capture_output=True, text=True)
    if created.returncode != 0:
        pytest.skip("this git does not support the reftable ref store")
    _commit_all(repo)
    real = _real_git(repo, "status", "--porcelain")
    assert real.returncode == 0, "the fixture is not readable by real git, so it proves nothing"
    answer = gitread.probe(repo, "status", "--porcelain", negative_statuses=())
    assert not answer.answered, "a ref store this build cannot import was answered about"
    assert "HEAD" in answer.cause


def test_an_unborn_repository_is_answered_not_refused(tmp_path):
    """The other side of the same discrimination. An unborn branch is a repository
    with no commit; a ref store this build cannot read is one it must not answer
    about. Collapsing them is what let the wrong answer through."""
    repo = tmp_path / "unborn"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "new.txt").write_text("new\n")
    real = _real_git(repo, "status", "--porcelain")
    answer = gitread.probe(repo, "status", "--porcelain", negative_statuses=())
    assert answer.answered, answer.cause
    assert answer.value == real.stdout.strip()


# O6 — a read leaves the subject byte-identical ---------------------------------------

def _fingerprint(root):
    import hashlib

    digest = hashlib.sha256()
    for base, directories, files in os.walk(root):
        directories.sort()
        for name in sorted(files):
            path = os.path.join(base, name)
            digest.update(os.path.relpath(path, root).encode("utf-8", "surrogateescape"))
            try:
                with open(path, "rb") as handle:
                    digest.update(handle.read())
            except OSError:
                digest.update(b"<unreadable>")
    return digest.hexdigest()


def test_a_governed_read_leaves_the_subject_byte_identical(tmp_path):
    """The index is COPIED for this reason: a `status` refresh writes an index, and
    it must be ours. Asserted over the working tree AND the git directory."""
    script, _marker = _marker_script(tmp_path)
    repo = tmp_path / "subject"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _hostile(repo, script)
    _commit_all(repo)
    (repo / "f.txt").write_text("changed\n")
    before = _fingerprint(repo)
    for arguments in (("status", "--porcelain"), ("status", "-v"), ("diff",),
                      ("log", "-p", "-1"), ("ls-files", "-z")):
        gitread.probe(repo, *arguments, negative_statuses=())
    assert _fingerprint(repo) == before, "a governed read changed the repository it read"


# O7 — TRACE2 as a falsification oracle, never as the barrier -------------------------

def test_git_starts_no_child_process_during_a_governed_read(tmp_path):
    """`GIT_TRACE2_EVENT` reports every child process Git starts, so it can
    falsify the claim that none was started. **It is an oracle and not the
    barrier**: it observes after the fact, and detection after execution is not
    prevention. The design records it as rejected in that role."""
    script, marker = _marker_script(tmp_path)
    repo = tmp_path / "subject"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _hostile(repo, script)
    _commit_all(repo)
    (repo / "f.txt").write_text("changed\n")

    trace = tmp_path / "trace.json"
    # RESET AFTER THE FIXTURE, NOT BEFORE IT. Building the fixture runs `git add`,
    # which runs the repository's own clean filter — that is real git doing what
    # real git does, and counting it here would report a leak that is not one.
    marker.write_bytes(b"")
    read = _sterile.build(repo)
    try:
        environment = dict(read.environment)
        environment["GIT_TRACE2_EVENT"] = str(trace)
        subprocess.run(["git", "status", "-v"], cwd=str(read.cwd), env=environment,
                       capture_output=True, text=True)
    finally:
        read.discard()
    started = []
    if trace.exists():
        for line in trace.read_text(errors="replace").splitlines():
            try:
                event = _json.loads(line)
            except ValueError:
                continue
            if event.get("event") == "child_start":
                started.append(" ".join(event.get("argv", [])))
    assert trace.exists(), "no trace was written, so this oracle observed nothing"
    assert not any(str(script) in one for one in started), (
        f"git started the repository's own program: {started}"
    )
    assert _did_it_run(marker) == 0


# O8 / O9 — a projection reports, and no refusal depends on one -----------------------

def test_a_projection_reports_without_refusing(tmp_path):
    """`program_valued_config` used to decide whether a read happened. It reports
    now, and reporting must not make a repository unreadable — which is exactly
    the over-refusal that broke `workspace_report`."""
    repo = _repo_setting(tmp_path, "alias.x")
    assert gitread.program_valued_config(repo) == ["alias.x"]
    assert gitread.probe(repo, "status", "--porcelain", negative_statuses=()).answered


@pytest.mark.parametrize("key", [
    "alias.x", "merge.m.driver", "submodule.a.update", "protocol.ext.command",
    "remote.o.vcs", "trailer.t.command", "interactive.difffilter", "guitool.g.cmd",
    "filter.f.clean", "filter.f.smudge", "filter.f.process",
    "core.pager", "core.editor", "diff.external", "credential.helper",
])
def test_a_program_valued_key_is_reported_and_gets_its_declared_disposition(tmp_path, key):
    """Reporting stays passive while active content filters refuse by policy."""
    repo = _repo_setting(tmp_path, key)
    assert gitread.program_valued_config(repo) == [key.lower()]
    answer = gitread.probe(repo, "status", "--porcelain", negative_statuses=())
    if key.startswith("filter."):
        assert not answer.answered
        assert "content filter" in answer.cause
    else:
        assert answer.answered, answer.cause


def test_no_refusal_depends_on_a_projection(tmp_path, monkeypatch):
    """**The constraint the founder attached to keeping these names.** A projection
    is a view of what a repository declares; it must never be a second answer to
    the security question. Emptying every one of them must change no refusal and
    no answer."""
    script, marker = _marker_script(tmp_path)
    repo = tmp_path / "subject"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _hostile(repo, script)
    _commit_all(repo)
    (repo / "f.txt").write_text("changed\n")

    marker.write_bytes(b"")
    before = gitread.probe(repo, "status", "-v", negative_statuses=())
    assert _did_it_run(marker) == 0

    monkeypatch.setattr(gitread, "PROGRAM_VALUED_CONFIG", ())
    monkeypatch.setattr(gitread, "CLOSED_PROGRAM_KEYS", {})
    monkeypatch.setattr(gitread, "FLAG_BASED_CLOSURES", {})
    monkeypatch.setattr(gitread, "CONDITIONAL_CLOSURES", {})
    marker.write_bytes(b"")
    after = gitread.probe(repo, "status", "-v", negative_statuses=())
    assert after.answered == before.answered and after.value == before.value, (
        "emptying the projections changed a governed answer, so one of them is load-bearing"
    )
    assert _did_it_run(marker) == 0, (
        "emptying the projections let the repository's program run, so a projection was the "
        "barrier and the boundary is not what stops execution"
    )


# O15 — the operator's machine does not shape a governed answer -----------------------

def test_an_operators_home_does_not_shape_a_governed_answer(tmp_path, monkeypatch):
    """`GIT_CONFIG_GLOBAL` redirects the global CONFIG file and nothing else, so an
    operator's `~/.config/git/ignore` was still read and a governed `status`
    silently dropped an untracked file. Found by an independent design reading.
    `git config --show-scope` never lists that file, so the invariant's own check
    could not see it: the directory is empty instead. Reverting the `HOME` and
    `XDG_CONFIG_HOME` repair inherits this test's operator home and makes the
    untracked file disappear from the constructed `status` output."""
    home = tmp_path / "operator-home"
    (home / "git").mkdir(parents=True)
    (home / "git" / "ignore").write_text("secret-untracked.txt\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))

    repo = tmp_path / "subject"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit_all(repo)
    (repo / "secret-untracked.txt").write_text("this must still be reported\n")

    read = _sterile.build(repo)
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=read.cwd, env=read.environment,
            capture_output=True, text=True,
        )
    finally:
        read.discard()
    assert status.returncode == 0, status.stderr
    assert "secret-untracked.txt" in status.stdout, (
        "the operator's global ignore file suppressed a file from a governed answer"
    )


# O10 / O16 — the answer equals real Git's, wherever real Git answers ------------------

def test_a_governed_read_discards_its_construction_however_the_read_ends(tmp_path, monkeypatch):
    """THE CALL SITE, not the method.

    `SterileRead.discard` has its own coverage, and `_run` promises in a comment
    that the construction is discarded however the read ends. Deleting the call
    left every behavioural test in this file green: the only failures a full suite
    produced were the identity-and-digest ones that fail on ANY byte change, which
    say nothing about this guarantee. The same suite leaked thousands of
    directories into the system temp directory while staying green. A guarantee
    asserted in a comment is not pinned by anything, which is this pack's own
    recurrence class `oracle satisfied for a reason other than its claim`.
    """
    root = _repo(tmp_path)
    built: list = []
    real_build = _sterile.build

    def watched(*args, **kwargs):
        read = real_build(*args, **kwargs)
        built.append(Path(read.scratch))
        return read

    monkeypatch.setattr(gitread.sterile, "build", watched)

    gitread._run(root, "rev-parse", "HEAD")
    with _pytest.raises(_GitRefusal):
        gitread._run(root, "rev-parse", "--verify", "refs/heads/no-such-branch")

    # A POSITIVE CONTROL. Without this the test passes when nothing was ever
    # constructed, which is exactly how it would pass if `_run` stopped going
    # through the boundary at all.
    assert len(built) >= 2, f"the construction ran {len(built)} times, so this proves nothing"
    assert not [one for one in built if one.exists()], (
        f"a governed read left its construction behind: {[str(o) for o in built if o.exists()]}"
    )


def test_the_construction_refuses_by_name_rather_than_raising_whatever_it_hit(tmp_path, monkeypatch):
    """Anything the construction can raise reaches the caller as a REFUSAL.

    `errors.run_cli` catches `HxError` and `probe` catches `GitRefusal`, so an
    exception that is neither escapes both and reaches the operator as a traceback
    indistinguishable from a bug in the tool. That was repaired once, for one
    spelling — a `subprocess.TimeoutExpired` out of the construction — and a second
    spelling arrived anyway: a `FileExistsError` from the view builder. Spellings
    do not converge, so the class is pinned here instead of the instance.
    """
    root = _repo(tmp_path)

    def explode(*_args, **_kwargs):
        raise FileExistsError(17, "File exists")

    monkeypatch.setattr(_sterile, "_build_view", explode)
    # A nested repository is what sends the build through the view builder at all.
    (root / "nest").mkdir()
    _git(root / "nest", "init", "-q", "-b", "main")

    with _pytest.raises(_GitRefusal) as raised:
        gitread._run(root, "status", "--porcelain")
    assert "sterile construction" in str(raised.value.cause), raised.value.cause
    assert "FileExistsError" in raised.value.render(), raised.value.render()


def test_a_copied_view_keeps_every_mode(tmp_path, monkeypatch):
    """Copying a view preserves modes without changing source-file ctimes.

    This forces the historical cross-device path without requiring a second
    filesystem.  Reverting to the hard-link implementation with its old
    content-only fallback makes ``program.sh`` arrive as mode 644 and this
    comparison fails with a spurious modification.
    """
    root = _repo(tmp_path, "xdev")
    program = root / "program.sh"
    program.write_text("#!/bin/sh\ntrue\n")
    program.chmod(0o755)
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "exe")
    # a nested repository is what makes the build construct a view at all
    (root / "nest").mkdir()
    _git(root / "nest", "init", "-q", "-b", "main")

    def no_hardlinks(*_args, **_kwargs):
        raise OSError(18, "Cross-device link")

    monkeypatch.setattr(_sterile.os, "link", no_hardlinks)

    expected, got = _exactly_as_real_git(root, "status", "--porcelain")
    assert expected is not None, "real git refused the fixture, so this proves nothing"
    assert got == expected, (
        "a view built through the copy fallback disagreed with real git: "
        f"{got!r} against {expected!r}"
    )
    assert "program.sh" not in got, (
        "the executable arrived in the view without its mode, so the read called it modified"
    )


def test_a_constructed_view_does_not_make_nested_outer_paths_look_modified(tmp_path):
    """A prior governed read must not alter the next diff-index answer.

    Real Git reports this legacy outer-tracked file clean.  A hard-linked view
    changed the source ctime; the next view then made Git inspect beneath the
    nested repository and emit a false modification.
    """
    root = _repo(tmp_path, "nested-diff-index")
    nested = root / "inner"
    nested.mkdir()
    (nested / "data.txt").write_text("outer tracked data\n")
    _git(root, "add", "inner/data.txt")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "outer")
    _git(nested, "init", "-q", "-b", "main")
    (nested / "inner.txt").write_text("inner\n")
    _git(nested, "add", "inner.txt")
    _git(nested, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "inner")

    expected = _real_git(root, "diff-index", "HEAD")
    assert expected.returncode == 0 and expected.stdout == ""
    gitread._run(root, "rev-parse", "HEAD")
    assert gitread._run(root, "diff-index", "HEAD") == expected.stdout
    assert _real_git(root, "diff-index", "HEAD").stdout == expected.stdout


def test_a_governed_read_leaves_the_subject_untouched_down_to_its_inode_metadata(tmp_path):
    """The central promise of the constructed view, bound rather than described.

    "The index copied so a refresh never touches the subject" was true of the
    index and false of the working tree: the view hard-linked every regular
    file, and creating a hard link changes the SOURCE file's ctime. `st_nlink`
    is back to 1 once the view is discarded, so nothing on disk records that it
    happened — and ctime is exactly what Git's stat cache compares, which is how
    a later `diff-index` came to call a clean file modified.

    Content was never at risk, which is why every byte-comparing oracle stayed
    green through it. This one snapshots each regular source file's content,
    `st_mtime_ns`, `st_ctime_ns`, `st_ino`, `st_size`, and `st_mode` across a
    read instead, because that is where the damage was. `st_atime_ns` is
    deliberately excluded: reading a file can update it; restoring it would
    update `st_ctime_ns`; and every reader, including real Git, has that same
    read artifact. The asserted fields are the subject-mutation claim.

    Bounded deliberately: this asserts the property for an ORDINARY subject. A
    subject whose `.git/index` is an absolute symlink still gets written through,
    because git-directory state is carried with `symlinks=True` and the link
    arrives in the constructed directory still pointing outside it. That is a
    pre-existing defect frozen 2.4.0 shares, it is recorded in the manifest's
    known limitations, and it is not what this test is for.
    """
    root = _repo(tmp_path, "untouched")
    (root / "a.txt").write_text("a\n")
    (root / "dir").mkdir()
    (root / "dir" / "b.txt").write_text("b\n")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "c")
    # A nested repository is what makes the boundary construct a working-tree view
    # at all. Without one there is nothing to link and this test passes against the
    # very defect it exists to catch — which it did, on its first version.
    nested = root / "inner"
    nested.mkdir()
    _git(nested, "init", "-q", "-b", "main")
    (nested / "inner.txt").write_text("inner\n")
    _git(nested, "add", "inner.txt")
    _git(nested, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "inner")

    def snapshot():
        seen = {}
        for path in sorted(root.rglob("*")):
            if path.is_file() and not path.is_symlink():
                stat = path.lstat()
                seen[str(path.relative_to(root))] = (
                    path.read_bytes(),
                    stat.st_mtime_ns,
                    stat.st_ctime_ns,
                    stat.st_ino,
                    stat.st_size,
                    stat.st_mode,
                )
        return seen

    before = snapshot()
    assert before, "the fixture produced no files to compare"
    gitread._run(root, "status", "--porcelain")
    after = snapshot()

    assert set(after) == set(before), (
        "a governed read created or removed files in the subject: "
        f"created {sorted(set(after) - set(before))}, removed {sorted(set(before) - set(after))}"
    )
    changed = {name: (before[name], after[name]) for name in before if before[name] != after[name]}
    assert not changed, (
        "a governed read changed asserted subject content or metadata, which it must never do — "
        f"(content, mtime, ctime, inode, size, mode) moved for: {changed}"
    )


def test_a_public_overlay_cannot_retarget_the_subjects_index(tmp_path):
    """A caller cannot direct the construction refresh at the subject index.

    Reverting the overlay guard permits the future-mtime refresh below to update
    the subject's index before the local no-child barrier starts, so this
    byte-and-stat snapshot fails.
    """
    repo = _isolated_committed_repo(tmp_path, "subject-index")
    tracked = repo / "f.txt"
    future = time.time_ns() + 60_000_000_000
    os.utime(tracked, ns=(future, future))
    index = repo / ".git" / "index"
    before_bytes = index.read_bytes()
    before_stat = index.stat()

    refusal = None
    try:
        gitread._run(
            repo, "status", "--porcelain", env_overlay={"GIT_INDEX_FILE": str(index)},
        )
    except _GitRefusal as caught:
        refusal = caught

    after_bytes = index.read_bytes()
    after_stat = index.stat()
    assert after_bytes == before_bytes, "the refused read changed the subject index bytes"
    assert after_stat == before_stat, "the refused read changed the subject index stat"
    assert refusal is not None, "the public overlay did not refuse GIT_INDEX_FILE"
    assert "GIT_INDEX_FILE" in refusal.render()


def test_a_carried_git_state_link_is_materialised_before_index_refresh(tmp_path):
    """Carried git-directory state must be data, never a link back to the subject.

    Reverting materialisation preserves the scratch ``index`` symlink; the
    forced refresh then writes its ``real-index`` target and this inode check
    fails.  It invokes the governed boundary rather than the builder directly:
    a local barrier may fail closed on a host that cannot load it, but the
    construction and its refresh have still happened before that refusal.  The
    assertion is about the general copy mechanism, not an index-specific
    exception.
    """
    root = _isolated_committed_repo(tmp_path, "linked-state")
    nested = root / "nested"
    nested.mkdir()
    _isolated_git(nested, "init", "-q", "-b", "main")
    index = root / ".git" / "index"
    target = root / ".git" / "real-index"
    index.rename(target)
    index.symlink_to(target)
    before = target.stat()

    try:
        gitread._run(root, "status", "--porcelain")
    except _GitRefusal as refusal:
        # An unavailable Seatbelt profile is a named fail-closed local result,
        # not a reason to skip the write-through oracle.
        assert "local no-child barrier" in str(refusal.cause), refusal.render()

    after = target.stat()
    assert (after.st_ctime_ns, after.st_mtime_ns, after.st_size) == (
        before.st_ctime_ns, before.st_mtime_ns, before.st_size,
    ), "refresh followed a constructed path back to the subject"


def test_a_dangling_carried_git_state_link_refuses_by_name(tmp_path):
    """A carried link that cannot be materialised is a named refusal.

    Reverting to preserved links lets construction continue with the dangling
    scratch ``index`` link, so this read reaches Git rather than refusing at the
    materialisation boundary.
    """
    root = _isolated_committed_repo(tmp_path, "dangling-state")
    index = root / ".git" / "index"
    missing = root / ".git" / "missing-index"
    index.unlink()
    index.symlink_to(missing)

    with _pytest.raises(_GitRefusal) as raised:
        gitread._run(root, "rev-parse", "HEAD")
    assert "materialised" in str(raised.value.cause), raised.value.cause
    assert "symbolic link" in str(raised.value.cause), raised.value.cause
    assert not missing.exists(), "a failed construction must not create the link target"


def test_a_committed_symlink_is_a_symlink_in_the_constructed_view(tmp_path):
    """The view must BE the tree, and `os.link` quietly makes it not be.

    `os.link` follows symlinks by default, so it never fails on one — it succeeds
    and hard-links the TARGET. A committed symlink therefore arrived in the view as
    an ordinary file, Git compared mode 100644 with the 120000 in the index, and a
    governed `status` reported `T` for a typechange the subject does not have while
    `diff` invented a deleted file mode. The symlink handling existed the whole
    time, inside an `except OSError` the one case that needed it could never reach.

    Found by an independent certification. Pinned against real Git rather than
    against an expectation typed here, and over three verbs, because the wrong
    answer showed up differently in each.
    """
    root = _repo(tmp_path, "symlinked")
    (root / "target.txt").write_text("target\n")
    os.symlink("target.txt", root / "link-inside")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n")
    os.symlink(str(outside), root / "link-outside")
    os.symlink("nowhere-at-all", root / "link-dangling")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "links")
    # a nested repository is what makes the build construct a view at all
    (root / "nest").mkdir()
    _git(root / "nest", "init", "-q", "-b", "main")

    assert _git(root, "ls-files", "-s", "link-inside").split()[0] == "120000", (
        "the fixture did not commit a symlink, so this test would prove nothing"
    )
    for arguments in (("status", "--porcelain"), ("diff", "--name-status"), ("ls-files", "-s")):
        expected, got = _exactly_as_real_git(root, *arguments)
        assert expected is not None, f"real git refused {arguments}, so this proves nothing"
        assert got == expected, (
            f"the view disagreed with real git on `git {' '.join(arguments)}`: "
            f"{got!r} against {expected!r}"
        )


def test_a_directory_the_walk_cannot_read_refuses_instead_of_answering(tmp_path):
    """An inability to look must not become a smaller tree.

    `os.walk` swallows a directory it cannot read and simply yields less of the
    tree. The view built from it was missing a whole subtree, and Git answered
    confidently about what was left: a tracked file under an unreadable directory
    came back REPORTED AS DELETED while real Git said nothing about it. That is the
    pack's own `UNKNOWN coerced into an answer` class, arriving through a walk
    rather than through a comparison.
    """
    root = _repo(tmp_path, "unreadable")
    (root / "sub").mkdir()
    (root / "sub" / "tracked.txt").write_text("tracked\n")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "sub")
    (root / "nest").mkdir()
    _git(root / "nest", "init", "-q", "-b", "main")

    os.chmod(root / "sub", 0o000)
    try:
        with _pytest.raises(_GitRefusal) as raised:
            gitread._run(root, "status", "--porcelain")
        assert "could not be read" in str(raised.value.cause), raised.value.cause
    finally:
        os.chmod(root / "sub", 0o755)

    # AND THE BOUND: it must not refuse a tree it can read. Without this the repair
    # could be a blanket refusal and the test above would still pass.
    expected, got = _exactly_as_real_git(root, "status", "--porcelain")
    assert expected is not None and got == expected, (
        f"the same subject, readable, no longer answers as real git: {got!r} against {expected!r}"
    )


def test_the_nested_repository_discovery_walk_refuses_its_own_walk_error(tmp_path, monkeypatch):
    """The pre-view discovery walk must not turn an unreadable directory into none.

    This calls `nested_repository_paths` directly, so its own `os.walk` call
    site is pinned independently of the later view-copy walk.
    """
    root = tmp_path / "discovery-subject"
    root.mkdir()
    unreadable = root / "unreadable"

    def walk(path, *, followlinks, onerror):
        assert Path(path).resolve() == root.resolve()
        assert followlinks is False
        assert onerror is _sterile._refuse_unreadable
        onerror(PermissionError(13, "Permission denied", str(unreadable)))
        yield from ()

    monkeypatch.setattr(_sterile.os, "walk", walk)
    with _pytest.raises(_GitRefusal) as raised:
        _sterile.nested_repository_paths(root)
    assert "could not be read" in str(raised.value.cause), raised.value.cause


def test_the_view_copy_walk_refuses_its_own_walk_error(tmp_path, monkeypatch):
    """The view-copy walk independently refuses an unreadable directory.

    The first test cannot reach this call site: discovery normally happens
    first. Calling the builder directly makes deleting only its `onerror=`
    handler fail this oracle.
    """
    root = tmp_path / "view-subject"
    root.mkdir()
    unreadable = root / "unreadable"

    def walk(path, *, followlinks, onerror):
        assert Path(path).resolve() == root.resolve()
        assert followlinks is False
        assert onerror is _sterile._refuse_unreadable
        onerror(PermissionError(13, "Permission denied", str(unreadable)))
        yield from ()

    monkeypatch.setattr(_sterile.os, "walk", walk)
    with _pytest.raises(_GitRefusal) as raised:
        _sterile._build_view(root, tmp_path / "scratch")
    assert "could not be read" in str(raised.value.cause), raised.value.cause


def test_a_split_index_is_carried_rather_than_refused(tmp_path):
    """OVER-REFUSAL IS A FAILURE, NOT A SAFE DEFAULT.

    `core.splitIndex` leaves the bulk of the entries in a `sharedindex.<oid>` file
    and the `index` only references it. The build copied the index and not the file
    it names, so Git exited 128 with "unable to read sharedindex" and this boundary
    refused an ordinary repository real Git reads without complaint. The release
    before this one reached a convergence blocker holding an over-refusal in one
    hand and an under-refusal in the other, so a refusal is only correct when the
    read genuinely cannot be reproduced.

    Both files are index DATA and neither names a program, so carrying the second
    is the same decision as carrying the first.
    """
    root = _repo(tmp_path, "splitindex")
    _git(root, "update-index", "--split-index")
    shared = list((root / ".git").glob("sharedindex.*"))
    assert shared, "the fixture has no shared index, so this test would prove nothing"
    (root / "f.txt").write_text("changed\n")

    expected, got = _exactly_as_real_git(root, "status", "--porcelain")
    assert expected is not None, "real git refused the fixture, so this proves nothing"
    assert got == expected, (
        f"a split index disagreed with real git: {got!r} against {expected!r}"
    )


def _exactly_as_real_git(repo, *arguments):
    """Byte for byte, through `_run` rather than `probe`.

    `probe` strips its value, which would hide a trailing-whitespace difference —
    and this is the oracle that exists to catch a WRONG ANSWER, so it compares
    what Git actually emitted."""
    real = _real_git(repo, *arguments)
    if real.returncode != 0:
        return None, None
    return real.stdout, gitread._run(repo, *arguments)


@pytest.mark.parametrize("shape", [
    "autocrlf", "unborn", "detached", "symref chain", "packed refs",
    "assume unchanged", "filemode", "info exclude", "sparse checkout",
])
def test_the_sterile_answer_equals_real_gits_answer(tmp_path, shape):
    """Storage-descriptor and ref-shape cases, each of which produced a WRONG answer
    at some point in this design's construction rather than a refusal. A wrong
    answer is the worst thing a read can produce, so each is pinned against real
    Git rather than against an expectation typed here."""
    repo = tmp_path / shape.replace(" ", "-")
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")

    if shape == "autocrlf":
        _git(repo, "config", "core.autocrlf", "true")
        (repo / "f.txt").write_text("one\r\ntwo\r\n", newline="")
        _git(repo, "add", "-A")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "c")
        indexed_stat = (repo / "f.txt").stat()
        # REWRITTEN AFTER THE COMMIT, ON PURPOSE, WITH THE SAME BYTES.
        #
        # Git trusts the index's cached stat and does not re-read a file whose
        # mtime and size still match it, so whether this row exercises end-of-line
        # conversion AT ALL depended on landing inside Git's one-second "racily
        # clean" window. It usually did, and occasionally did not: the mutant that
        # drops the content-encoding descriptors was killed on its own every time
        # and SURVIVED intermittently inside a full mutation run. An oracle whose
        # discrimination depends on the clock is not an oracle. A mtime two seconds
        # before the indexed timestamp makes the stat cache stale on every host, so
        # Git must compare content every time.
        (repo / "f.txt").write_text("one\r\ntwo\r\n", newline="")
        os.utime(
            repo / "f.txt",
            ns=(indexed_stat.st_atime_ns, indexed_stat.st_mtime_ns - 2_000_000_000),
        )
    elif shape == "filemode":
        _git(repo, "config", "core.filemode", "false")
        (repo / "f.txt").write_text("one\n")
        _git(repo, "add", "-A")
        _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "c")
        (repo / "f.txt").chmod(0o755)
    elif shape == "unborn":
        (repo / "f.txt").write_text("x\n")
    else:
        _commit_all(repo)

    if shape == "detached":
        head = _git(repo, "rev-parse", "HEAD").strip()
        _git(repo, "checkout", "-q", "--detach", head)
    elif shape == "symref chain":
        _git(repo, "symbolic-ref", "refs/heads/middle", "refs/heads/main")
        _git(repo, "symbolic-ref", "HEAD", "refs/heads/middle")
    elif shape == "packed refs":
        _git(repo, "pack-refs", "--all")
    elif shape == "assume unchanged":
        _git(repo, "update-index", "--assume-unchanged", "f.txt")
        (repo / "f.txt").write_text("changed underneath\n")
    elif shape == "info exclude":
        (repo / ".git" / "info").mkdir(exist_ok=True)
        (repo / ".git" / "info" / "exclude").write_text("hidden.txt\n")
        (repo / "hidden.txt").write_text("h\n")
        (repo / "shown.txt").write_text("s\n")
    elif shape == "sparse checkout":
        _git(repo, "config", "core.sparseCheckout", "true")
        (repo / ".git" / "info").mkdir(exist_ok=True)
        (repo / ".git" / "info" / "sparse-checkout").write_text("/*\n")

    compared = 0
    for arguments in (("status", "--porcelain"), ("status", "--porcelain", "-uall"),
                      ("rev-parse", "HEAD"), ("diff",)):
        expected, got = _exactly_as_real_git(repo, *arguments)
        if expected is None:
            continue
        compared += 1
        assert got == expected, (
            f"{shape}: `git {' '.join(arguments)}` answered differently from real git"
        )
    assert compared, f"{shape}: real git answered nothing, so this row compared nothing"


def test_sparse_checkout_storage_from_config_worktree_reaches_long_status(tmp_path):
    """The sparse-checkout marker is controlled by a safe worktree descriptor."""
    repo = _isolated_committed_repo(tmp_path, "sparse")
    (repo / "dir").mkdir()
    (repo / "dir" / "tracked.txt").write_text("tracked\n")
    _isolated_git(repo, "add", "dir/tracked.txt")
    _isolated_git(repo, "commit", "-q", "-m", "add directory")
    _isolated_git(repo, "sparse-checkout", "init", "--cone")
    _isolated_git(repo, "sparse-checkout", "set", "dir")

    expected = _real_git(repo, "status")
    assert expected.returncode == 0, expected.stderr
    assert "sparse checkout" in expected.stdout
    assert gitread._run(repo, "status") == expected.stdout


def test_object_format_is_taken_only_from_the_common_configuration(tmp_path):
    """A worktree config cannot declare the common object store's hash format.

    Reverting to the merged declaration carries ``sha256`` from
    ``config.worktree`` into a SHA-1 constructed store, so the HEAD confirmation
    refuses instead of returning this real-Git object name.
    """
    repo = _isolated_committed_repo(tmp_path, "worktree-object-format")
    _isolated_git(repo, "config", "extensions.worktreeConfig", "true")
    (repo / ".git" / "config.worktree").write_text(
        "[extensions]\n\tobjectFormat = sha256\n", encoding="utf-8",
    )

    expected = _isolated_real_git(repo, "rev-parse", "HEAD")
    assert expected.returncode == 0, expected.stderr
    assert gitread._run(repo, "rev-parse", "HEAD") == expected.stdout


def test_an_include_in_active_config_worktree_refuses_instead_of_omitting_it(tmp_path):
    """An active worktree include is not a partial source of storage settings.

    Reverting the include refusal silently omits the included sparse-checkout
    descriptors, so this governed status answers without the long-status sparse
    checkout sentence that real Git emits.
    """
    repo = _isolated_committed_repo(tmp_path, "worktree-include")
    (repo / "dir").mkdir()
    (repo / "dir" / "tracked.txt").write_text("tracked\n")
    _isolated_git(repo, "add", "dir/tracked.txt")
    _isolated_git(repo, "commit", "-q", "-m", "add directory")
    _isolated_git(repo, "config", "extensions.worktreeConfig", "true")
    (repo / ".git" / "config.worktree").write_text(
        "[include]\n\tpath = wt-included\n", encoding="utf-8",
    )
    (repo / ".git" / "wt-included").write_text(
        "[core]\n\tsparseCheckout = true\n\tsparseCheckoutCone = true\n", encoding="utf-8",
    )
    (repo / ".git" / "info" / "sparse-checkout").write_text("d/\n", encoding="utf-8")

    expected = _isolated_real_git(repo, "status")
    assert expected.returncode == 0 and "sparse checkout" in expected.stdout, expected.stderr
    with _pytest.raises(_GitRefusal) as raised:
        gitread._run(repo, "status")
    assert "config.worktree includes" in str(raised.value.cause), raised.value.cause


def test_a_git_file_status_does_not_report_its_own_transient_index_lock(tmp_path, monkeypatch):
    """A governed read's scratch index cannot become a subject untracked file.

    The nested repository forces a constructed working-tree view, so the copied
    index must be refreshed.  Reverting that refresh leaves ``calls`` empty;
    the earlier no-nested fixture passed even though it never reached this path.
    """
    repo = _isolated_committed_repo(tmp_path, "git-file")
    actual = repo / "actual-gitdir"
    (repo / ".git").rename(actual)
    (repo / ".git").write_text("gitdir: actual-gitdir\n")
    nested = repo / "nested"
    nested.mkdir()
    _isolated_git(nested, "init", "-q", "-b", "main")

    calls = []
    original = _sterile._refresh_constructed_index

    def recording(subject, gitdir, environment, cwd, timeout):
        calls.append((subject, gitdir, cwd))
        return original(subject, gitdir, environment, cwd, timeout)

    monkeypatch.setattr(_sterile, "_refresh_constructed_index", recording)

    output = gitread._run(repo, "status", "--porcelain", "-uall")
    assert calls, "the fixture did not reach the constructed-index refresh"
    assert calls[0][2] != repo, "the refresh did not run against a constructed view"
    assert "actual-gitdir/index.lock" not in output
    assert not (actual / "index.lock").exists()


# R1/R2/R3 — repairs that preserve the frozen floor ---------------------------------

def test_the_constructed_index_refreshes_even_without_a_view(tmp_path, monkeypatch):
    """A copied index has copied stat data even when its tree is the subject.

    The old `constructed_view` guard made this test pass only when a nested
    directory happened to force a view.  This ordinary subject proves the
    owned index is refreshed in both layouts and that `diff-index` sees clean.
    """
    repo = _isolated_committed_repo(tmp_path, "refresh-without-view")
    calls = []
    original = _sterile._refresh_constructed_index

    def recording(*arguments):
        calls.append(arguments)
        return original(*arguments)

    monkeypatch.setattr(_sterile, "_refresh_constructed_index", recording)
    read = _sterile.build(repo)
    try:
        result = subprocess.run(
            ["git", "diff-index", "HEAD"], cwd=read.cwd, env=read.environment,
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == ""
    finally:
        read.discard()
    assert calls, "the ordinary subject bypassed the constructed-index refresh"


def test_branch_tracking_is_carried_into_a_constructed_status_answer(tmp_path):
    """The v2 branch fields come from branch.<name>.remote and .merge."""
    repo = _isolated_committed_repo(tmp_path, "branch-tracking")
    head = _isolated_git(repo, "rev-parse", "HEAD").strip()
    _isolated_git(repo, "remote", "add", "origin", str(repo))
    _isolated_git(repo, "update-ref", "refs/remotes/origin/main", head)
    _isolated_git(repo, "config", "branch.main.remote", "origin")
    _isolated_git(repo, "config", "branch.main.merge", "refs/heads/main")
    expected = _isolated_real_git(repo, "status", "--porcelain=v2", "--branch")
    assert "# branch.upstream origin/main" in expected.stdout, expected.stdout
    assert "# branch.ab +0 -0" in expected.stdout, expected.stdout

    read = _sterile.build(repo)
    try:
        actual = subprocess.run(
            ["git", "status", "--porcelain=v2", "--branch"], cwd=read.cwd,
            env=read.environment, capture_output=True, text=True,
        )
        assert actual.returncode == 0, actual.stderr
        assert actual.stdout == expected.stdout
    finally:
        read.discard()


def test_constructed_path_output_is_rebased_before_scratch_is_discarded(tmp_path):
    """One path relation covers Git's relative and absolute path answers."""
    repo = _isolated_committed_repo(tmp_path, "path-rebasing")
    read = _sterile.build(repo)
    try:
        relative = subprocess.run(
            ["git", "rev-parse", "--git-dir"], cwd=read.cwd, env=read.environment,
            capture_output=True, text=True, check=True,
        ).stdout
        common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"], cwd=read.cwd, env=read.environment,
            capture_output=True, text=True, check=True,
        ).stdout
        absolute = subprocess.run(
            ["git", "rev-parse", "--absolute-git-dir"], cwd=read.cwd, env=read.environment,
            capture_output=True, text=True, check=True,
        ).stdout
        git_path = subprocess.run(
            ["git", "rev-parse", "--git-path", "index"], cwd=read.cwd, env=read.environment,
            capture_output=True, text=True, check=True,
        ).stdout
        assert gitread._restore_subject_paths(relative, read, repo) == ".git\n"
        assert gitread._restore_subject_paths(common, read, repo) == ".git\n"
        assert gitread._restore_subject_paths(absolute, read, repo) == str(repo / ".git") + "\n"
        assert gitread._restore_subject_paths(git_path, read, repo) == ".git/index\n"
    finally:
        read.discard()

    nested = repo / "nested"
    nested.mkdir()
    _isolated_git(nested, "init", "-q", "-b", "main")
    read = _sterile.build(repo)
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=read.cwd, env=read.environment,
            capture_output=True, text=True, check=True,
        ).stdout
        assert gitread._restore_subject_paths(top, read, repo) == str(repo) + "\n"
    finally:
        read.discard()


def test_public_run_restores_constructed_gitdir_before_discard(tmp_path, monkeypatch):
    """The public entry point returns a usable subject path, not its scratch path.

    The direct helper test above establishes the substitution relation, but it
    does not establish that ``_run`` uses it.  This test replaces only the
    host-specific no-child launcher: it still builds the sterile read, invokes
    Git through the public entry point, discards the construction, then checks
    the returned answer.  Replacing the public return with ``result.stdout``
    returns the discarded scratch gitdir and fails both assertions below.
    """
    repo = _isolated_committed_repo(tmp_path, "public-path-rebasing")

    def launch(command, *, read, subject, timeout, text, input_value, barrier,
               trace, decoding, caller_arguments):
        return subprocess.run(
            command, cwd=read.cwd, env=read.environment, capture_output=True,
            check=False, timeout=timeout, text=text, input=input_value, **decoding,
        )

    monkeypatch.setattr(gitread, "_launch_local", launch)
    answer = gitread._run(repo, "rev-parse", "--git-dir")
    assert answer == ".git\n"
    returned = (repo / answer.strip()).resolve()
    assert returned == (repo / ".git").resolve()
    assert returned.is_dir(), "the public entry point returned a discarded scratch path"


# O-A71-3 — a local read has a proof-bearing no-child barrier -----------------

def test_a_local_read_creates_no_child(tmp_path):
    """A usable host yields Git's Trace2 evidence; an unusable one fails closed.

    The profile assertion makes removing the child denial a discriminating
    mutation even on an executor that is itself not allowed to load Seatbelt.
    Where the host can load it, the same test asks Git to write the Trace2
    witness and counts its child-start events rather than trusting zero from an
    absent file.
    """
    repo = _isolated_committed_repo(tmp_path, "no-child")
    read = _sterile.build(repo)
    try:
        profile = gitread._local_profile(read, repo, tmp_path)
    finally:
        read.discard()
    assert "(deny process-fork)" in profile

    unwitnessed = tmp_path / "unwitnessed.trace2.json"
    unwitnessed.write_text('{"event":"start"}\n', encoding="utf-8")
    with _pytest.raises(_GitRefusal) as raised:
        gitread._trace_has_no_children(unwitnessed)
    assert "lacks Git's version event" in str(raised.value.cause)

    trace = tmp_path / "local.trace2.json"
    try:
        assert gitread._run(
            repo, "status", "--porcelain", env_overlay={"GIT_TRACE2_EVENT": str(trace)},
        ) == ""
    except _GitRefusal as refusal:
        # This executor nests a Seatbelt sandbox, which macOS rejects before
        # Git starts.  A named refusal is the required result on that host.
        assert "local no-child barrier" in str(refusal.cause), refusal.render()
        return

    events = [json.loads(line) for line in trace.read_text().splitlines() if line]
    assert any(event.get("event") == "version" for event in events)
    assert not [event for event in events if event.get("event") == "child_start"]


def test_a_public_overlay_delegates_trace2_event(tmp_path):
    """The public overlay retains the one delegated Git variable, Trace2.

    Reverting the overlay guard leaves this delegated path working; this test
    establishes the intentionally narrow exception rather than discriminating
    the guard's rejection of every other Git name.
    """
    repo = _isolated_committed_repo(tmp_path, "delegated-trace2")
    trace = tmp_path / "delegated-trace2.json"
    try:
        assert gitread._run(
            repo, "status", "--porcelain", env_overlay={"GIT_TRACE2_EVENT": str(trace)},
        ) == ""
    except _GitRefusal as refusal:
        # This executor nests a Seatbelt sandbox, which macOS rejects before
        # Git starts.  It still proves the public overlay passed construction:
        # a closed Git namespace would instead name GIT_TRACE2_EVENT here.
        assert "local no-child barrier" in str(refusal.cause), refusal.render()
        return

    events = [json.loads(line) for line in trace.read_text().splitlines() if line]
    assert any(event.get("event") == "version" for event in events)


# O-A71-8 — routing and gitlink identity do not read subject declarations ----

def test_routing_does_not_consult_the_subject(tmp_path):
    """Backend choice and a gitlink's identity are both structural facts.

    The `.gitmodules` file deliberately disagrees with the stage-zero index.
    The runner supplies only the two structural Git reads; a mutant which asks
    configuration or `.gitmodules` for an identity has no response and fails.
    """
    # THE VERB IS THE CAPABILITY, and these hold it in both directions. An
    # earlier form asserted that `ls-remote` without `allow_transports` takes the
    # LOCAL backend, which is the defect rather than the property: the local
    # backend then saw `git-upload-pack` — the child a transport legitimately
    # starts — and refused a read the frozen floor answers. `allow_transports`
    # widens WHICH transports are permitted; it never decides which backend
    # serves the verb, because that would put a capability behind an argument.
    assert gitread._uses_local_backend("status", ())
    assert gitread._uses_local_backend("status", ("file",))
    assert not gitread._uses_local_backend("ls-remote", ())
    assert not gitread._uses_local_backend("ls-remote", ("file",))
    assert gitread._with_recursion_suppressed(("status", "--porcelain")) == (
        "status", "--porcelain", "--ignore-submodules=dirty",
    )
    assert gitread._with_recursion_suppressed(("diff", "--", "-path")) == (
        "diff", "--ignore-submodules=dirty", "--", "-path",
    )

    repo = tmp_path / "structural-gitlink"
    repo.mkdir()
    (repo / ".gitmodules").write_text(
        '[submodule "misleading"]\n\tpath = another-place\n\turl = nowhere\n', encoding="utf-8",
    )
    oid = b"1" * 40
    calls = []

    def structural_runner(_repository, *arguments, text=False, env_overlay=None):
        calls.append(arguments)
        if arguments == ("ls-files", "--stage", "-z"):
            return b"160000 " + oid + b" 0\tsub\0"
        if arguments == ("ls-files", "--stage"):
            return b"160000 " + oid + b" 0\tsub\n"
        if arguments == ("ls-tree", "-rz", "HEAD"):
            return b"160000 commit " + oid + b"\tsub\0"
        raise AssertionError(f"subject declaration was consulted: {arguments!r}")

    assert _has_gitlinks(repo, runner=structural_runner)
    assert calls == [
        ("ls-files", "--stage", "-z"),
        ("ls-files", "--stage"),
        ("ls-tree", "-rz", "HEAD"),
    ]


# preserved: the guarantees the removed tests carried ---------------------------------

def test_a_configuration_read_reports_the_subjects_settings_not_the_harnesss(tmp_path):
    """A config read under this boundary would otherwise consult the git directory
    the harness just built and answer confidently about the wrong repository —
    a silent wrong answer, which is worse than a refusal."""
    repo = tmp_path / "subject"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "notes.rewriteref", "refs/notes/commits")
    _commit_all(repo)
    entries = gitread.config_with_origin(repo)
    assert any(entry["key"] == "notes.rewriteref" for entry in entries), entries
    answer = gitread.probe(repo, "config", "--get", "notes.rewriteref", negative_statuses=(1,))
    assert answer.answered and answer.value.strip() == "refs/notes/commits"


def test_the_standing_transport_refusal_reaches_the_read(tmp_path, monkeypatch):
    """An ordinary transport read receives the standing `protocol.allow = never`.

    The external launch is replaced only after the real sterile construction, so
    this test neither contacts nor resolves the sample address.  It asks a
    second real constructed Git environment for the setting the first one was
    handed.  Reverting the `protocol.allow` repair removes that setting from the
    captured construction and the final `git config --get` assertion fails.
    """
    repo = _isolated_committed_repo(tmp_path, "ordinary-transport")
    captured = {}
    real_build = _sterile.build
    real_launch = gitread.instrument.launch

    def watch_build(repository, *, needs_working_tree=True, overlay=None, extra_config=None,
                    timeout=30.0, refuse_answer_shaping=False):
        captured.update(extra_config or {})
        return real_build(
            repository, needs_working_tree=needs_working_tree, overlay=overlay,
            extra_config=extra_config, timeout=timeout,
            refuse_answer_shaping=refuse_answer_shaping,
        )

    def stop_before_transport(command, **kwargs):
        if command[:2] == ("git", "ls-remote"):
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        return real_launch(command, **kwargs)

    monkeypatch.setattr(gitread.sterile, "build", watch_build)
    monkeypatch.setattr(gitread, "_uses_local_backend", lambda _verb, _allowed: False)
    monkeypatch.setattr(gitread.instrument, "launch", stop_before_transport)
    assert gitread._run(repo, "ls-remote", "ssh://not-contacted.invalid/example.git") == ""

    read = real_build(repo, extra_config=captured)
    try:
        setting = subprocess.run(
            ["git", "config", "--get", "protocol.allow"], cwd=read.cwd,
            env=read.environment, capture_output=True, text=True,
        )
    finally:
        read.discard()
    assert setting.returncode == 0, setting.stderr
    assert setting.stdout == "never\n"


def test_repository_location_is_taken_from_subject_files(tmp_path, monkeypatch):
    """Repository location comes from subject files, never from a governed read.

    The stand-in deliberately returns three distinct disposable locations a
    governed `rev-parse` could report.  Reverting the `sterile.where_is` repair
    makes `repository_location` return those constructed paths and this test
    fails before any answer can be mistaken for a subject location.
    """
    repo = _isolated_committed_repo(tmp_path, "location")
    constructed = tmp_path / "discarded-construction"
    calls = []

    def reads_the_construction(_repository, *arguments, **_kwargs):
        calls.append(arguments)
        return str(constructed / arguments[-1]) + "\n"

    monkeypatch.setattr(gitread, "_run", reads_the_construction)
    location = gitread.repository_location(repo)

    assert location == {
        "gitdir": str(repo / ".git"),
        "common": str(repo / ".git"),
        "toplevel": str(repo.resolve()),
        "linked_worktree": False,
        "bare": False,
    }
    assert calls == [], "repository location was asked of a governed Git read"


def test_a_repository_that_breaks_its_own_configuration_is_refused_not_read_as_empty(tmp_path):
    """`include.path` pointing at something unparseable makes every config read
    fail, so a repository could once disable the check that inspected it by
    breaking itself. Nothing is inspected now — but a configuration that cannot
    be read must still not be reported as *no settings*, because `notes.*` is a
    surface a gate watches."""
    repo = tmp_path / "broken"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit_all(repo)
    with open(repo / ".git" / "config", "a", encoding="utf-8") as handle:
        handle.write("[include]\n\tpath = /bin/sh\n")
    with pytest.raises(GitRefusal) as caught:
        gitread.config_with_origin(repo)
    assert "cannot be reported as the whole configuration" in caught.value.render(), \
        caught.value.render()
    assert "include.path" in caught.value.render()


def test_a_configuration_read_of_a_hostile_repository_runs_nothing(tmp_path):
    """Reading configuration executes nothing — which the whole boundary depends
    on, because `config_with_origin` parses the subject's own file with Git."""
    script, marker = _marker_script(tmp_path)
    repo = tmp_path / "subject"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _hostile(repo, script)
    _commit_all(repo)
    marker.write_bytes(b"")
    entries = gitread.config_with_origin(repo)
    assert any(entry["key"] == "diff.external" for entry in entries)
    assert _did_it_run(marker) == 0


def test_a_redirected_worktree_cannot_move_a_governed_answer(tmp_path):
    """`core.worktree` redirected reads to a sibling directory, so a workspace gate
    reported no unclassified files while one sat in the project it was asked
    about. The key is not read at all now; this holds that structurally."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "decoy.txt").write_text("decoy\n")
    repo = tmp_path / "subject"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit_all(repo)
    _git(repo, "config", "core.worktree", str(elsewhere))
    (repo / "the-file-that-matters.txt").write_text("here\n")
    answer = gitread.probe(repo, "status", "--porcelain", "-uall", negative_statuses=())
    assert answer.answered, answer.cause
    assert "the-file-that-matters.txt" in answer.value
    assert "decoy.txt" not in answer.value


@pytest.mark.parametrize("verb", [
    ("status", "--porcelain"), ("ls-files", "-z"), ("diff", "--check"),
    ("rev-parse", "HEAD"), ("log", "--oneline", "-1"), ("check-ignore", "-v", "x"),
])
def test_every_verb_answers_about_the_root_it_was_given(tmp_path, verb):
    """A release archive unpacked inside another checkout let Git discover the
    PARENT repository and answer about it. `GIT_DIR` is explicit here, so no
    discovery happens at all — asserted for every verb rather than for the ones
    an enumeration remembered."""
    outer = tmp_path / "outer"
    outer.mkdir()
    _git(outer, "init", "-q", "-b", "main")
    (outer / "outer-only.txt").write_text("outer\n")
    _git(outer, "add", "-A")
    _git(outer, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "o")
    inside = outer / "unpacked"
    inside.mkdir()
    (inside / "inner-only.txt").write_text("inner\n")
    answer = gitread.probe(inside, *verb, negative_statuses=(1, 128))
    # Not a repository of its own: the read must refuse rather than silently
    # answer about the repository above it.
    assert not answer.answered or "outer-only.txt" not in answer.value


def test_a_walk_that_cannot_look_refuses_rather_than_finding_nothing(tmp_path, monkeypatch):
    """A check that could not read its subject has not cleared it."""
    repo = tmp_path / "subject"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit_all(repo)
    locked = repo / "locked"
    locked.mkdir()
    (locked / "inner.txt").write_text("x\n")
    real_walk = _sterile.os.walk

    def walk(path, *, followlinks=False, onerror=None):
        if Path(path).resolve() == repo.resolve():
            assert onerror is _sterile._refuse_unreadable
            onerror(PermissionError(13, "Permission denied", str(locked)))
        yield from real_walk(path, followlinks=followlinks, onerror=onerror)

    monkeypatch.setattr(_sterile.os, "walk", walk)
    answer = gitread.probe(repo, "status", "--porcelain", negative_statuses=())
    assert not answer.answered, "an unreadable walk was answered as though it found nothing"
    assert "could not be read" in answer.cause, answer.cause


def test_concurrent_governed_reads_do_not_share_state(tmp_path):
    """The inspection this replaces carried a thread-local re-entrancy guard, and a
    module-level flag before that — a blind reader held one thread inside it and a
    second read skipped its inspection entirely. There is no shared mutable state
    now; each read builds and discards its own directory, and this is what holds
    that."""
    import threading

    script, marker = _marker_script(tmp_path)
    repos = []
    for index in range(4):
        repo = tmp_path / f"r{index}"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _hostile(repo, script, filters=False)
        _commit_all(repo)
        repos.append(repo)
    results = {}

    def read(index):
        results[index] = gitread.probe(repos[index], "status", "-v", negative_statuses=())

    marker.write_bytes(b"")
    threads = [threading.Thread(target=read, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == 4
    for index, answer in results.items():
        assert answer.answered, f"{index}: {answer.cause}"
    assert _did_it_run(marker) == 0


def test_the_view_builder_actually_runs_its_own_post_condition(tmp_path, monkeypatch):
    """The check exists and the builder must CALL it.

    Mutation found this gap rather than review: deleting the call site left the
    direct test of the check passing, because that test invokes the check itself.
    A guard nobody reaches is not a guard, so the wiring is pinned separately from
    the property."""
    calls = []
    original = _sterile._every_git_in_the_view_is_ours

    def recording(view, built):
        calls.append((Path(view), set(built)))
        return original(view, built)

    monkeypatch.setattr(_sterile, "_every_git_in_the_view_is_ours", recording)

    subject = tmp_path / "subject"
    subject.mkdir()
    _git(subject, "init", "-q", "-b", "main")
    _commit_all(subject)
    nested = subject / "nested"
    nested.mkdir()
    _git(nested, "init", "-q", "-b", "main")
    _commit_all(nested, "n.txt")

    read = _sterile.build(subject)
    try:
        assert calls, "the view was built without its post-condition being run"
        _view, built = calls[-1]
        assert built, "the post-condition was handed no built set, so it can accept anything"
        scratch = os.path.realpath(str(read.scratch))
        for made in built:
            assert os.path.realpath(str(made)).startswith(scratch), made
    finally:
        read.discard()


def test_a_hook_the_subject_wrote_is_never_run_by_a_governed_read(tmp_path):
    """The subject's own programs are not carried, so a governed read runs none.

    `hooks/` holds executables the SUBJECT wrote.  Carrying them into the
    constructed git directory made an ordinary read run one: refreshing the
    constructed index fires `post-index-change`, and that refresh happens
    before the local no-child barrier exists, so the hook ran unsandboxed with
    the subject's working tree as its working directory.

    Two independent repairs close this, so this test is the END-TO-END oracle
    and fails only when BOTH are reverted — measured, not assumed: with just the
    `_PROGRAM_ROOTS` omission reverted the programs are carried but
    `core.hooksPath` still points away from them, and with just `core.hooksPath`
    reverted there is no carried hook to find.  Each site is therefore pinned by
    its own structural oracle as well:
    `test_the_constructed_git_directory_excludes_only_its_root_hooks` for
    the omission, and
    `test_the_constructed_configuration_points_hooks_at_an_empty_harness_directory`
    for the configuration half.  Reverting both makes the witness file gain a
    line, puts the hook's write inside the subject, and turns the answer into a
    refusal, because the barrier then sees the child the hook started.  Frozen
    2.4.0 runs nothing here and answers, so that state is a floor regression
    rather than a new refusal.
    """
    repo = _isolated_committed_repo(tmp_path, "subject-hook")
    (repo / "untracked.txt").write_text("ordinary\n")
    witness = tmp_path / "hook-ran.txt"
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "post-index-change"
    hook.write_text(
        "#!/bin/sh\n"
        f"echo ran >> {witness}\n"
        'echo owned > "$PWD/HOOK-REACHED-THE-SUBJECT.txt"\n'
    )
    hook.chmod(0o755)
    # A stale stat entry is what makes Git rewrite the index during construction,
    # which is the event `post-index-change` fires on.
    future = time.time_ns() + 60_000_000_000
    os.utime(repo / "f.txt", ns=(future, future))

    answer = gitread._run(repo, "status", "--porcelain", text=False)

    assert not witness.exists(), "a governed read ran a program the subject wrote"
    assert not (repo / "HOOK-REACHED-THE-SUBJECT.txt").exists(), (
        "the subject's hook wrote into the subject during a governed read"
    )
    assert answer == b"?? untracked.txt\n", (
        "the ordinary answer regressed; frozen 2.4.0 answers this repository"
    )


def test_the_constructed_git_directory_excludes_only_its_root_hooks(tmp_path):
    """The hook search path is omitted by position, not by basename.

    Git's root `hooks/` is not carried because it is executable program state.
    A nested pathname is not that root and must remain ordinary carried state;
    treating it as an exclusion would also lose legal loose refs named `hooks`.
    """
    repo = _isolated_committed_repo(tmp_path, "program-free")
    for where in (repo / ".git" / "hooks", repo / ".git" / "modules" / "sub" / "hooks"):
        where.mkdir(parents=True, exist_ok=True)
        program = where / "post-index-change"
        program.write_text("#!/bin/sh\nexit 0\n")
        program.chmod(0o755)

    read = _sterile.build(repo)
    try:
        assert not (Path(read.gitdir) / "hooks").exists()
        assert (Path(read.gitdir) / "modules" / "sub" / "hooks" / "post-index-change").is_file()
    finally:
        read.discard()


def test_loose_refs_named_like_excluded_roots_match_real_git_byte_for_byte(tmp_path):
    """Root exclusions do not discard legal refs whose basename happens to match.

    The subject deliberately has `config`, `hooks`, and `objects` loose refs,
    plus an entry below `refs/heads/objects/`.  HEAD stays on `config`, so a
    basename-wide filter cannot pass construction by reproducing another ref.
    """
    repo = _isolated_committed_repo(tmp_path, "excluded-ref-names")
    _isolated_git(repo, "checkout", "-q", "-b", "config")
    (repo / "config.txt").write_text("second\n")
    _isolated_git(repo, "add", "config.txt")
    _isolated_git(repo, "commit", "-q", "-m", "config branch")
    _isolated_git(repo, "branch", "hooks")
    _isolated_git(repo, "branch", "objects/nested")
    _isolated_git(repo, "tag", "objects")

    commands = (
        ("rev-list", "--count", "--all"),
        ("show-ref",),
        ("log", "--oneline", "--all"),
    )
    for arguments in commands:
        expected = subprocess.run(
            ["git", *arguments], cwd=str(repo), capture_output=True, check=False,
            env=_fixture_environment(),
        )
        assert expected.returncode == 0, expected.stderr
        actual = gitread._run(repo, *arguments, text=False)
        assert actual == expected.stdout, f"governed {' '.join(arguments)} differs from real Git"

    shown = subprocess.run(
        ["git", "show-ref"], cwd=str(repo), capture_output=True, check=True,
        env=_fixture_environment(),
    ).stdout
    for ref in (b"refs/heads/config\n", b"refs/heads/hooks\n", b"refs/tags/objects\n",
                b"refs/heads/objects/nested\n"):
        assert ref in shown


def test_a_relative_alternate_reaches_the_same_history_as_real_git(tmp_path):
    """A relative alternate is resolved against the subject common objects root."""
    repo = _isolated_committed_repo(tmp_path, "relative-alternate")
    objects = repo / ".git" / "objects"
    alternate = tmp_path / "alternate-objects"
    alternate.mkdir()
    for entry in list(objects.iterdir()):
        if entry.name != "info":
            entry.rename(alternate / entry.name)
    info = objects / "info"
    info.mkdir(exist_ok=True)
    relative = os.path.relpath(alternate, objects)
    (info / "alternates").write_text(relative + "\n", encoding="utf-8")

    expected = subprocess.run(
        ["git", "log", "--oneline", "--all"], cwd=str(repo), capture_output=True,
        check=False, env=_fixture_environment(),
    )
    assert expected.returncode == 0, expected.stderr
    actual = gitread._run(repo, "log", "--oneline", "--all", text=False)
    assert actual == expected.stdout


def test_the_constructed_configuration_points_hooks_at_an_empty_harness_directory(tmp_path):
    """The other half of the hook closure, pinned on its own.

    Git looks for hooks in `core.hooksPath` and falls back to `$GIT_DIR/hooks`.
    Omitting the subject's programs closes the fallback; this closes the
    declared path, including one a subject plants under a state directory that
    `_copy_git_state` carries.  The declared directory must be empty and must
    live OUTSIDE the constructed git directory: otherwise a subject-owned
    `empty-hooks/post-index-change` is copied exactly where Git will execute
    it.  Moving the path back under `into` makes the copied file appear in the
    declared directory and fails this test.
    """
    repo = _isolated_committed_repo(tmp_path, "hooks-path")
    planted = repo / ".git" / "empty-hooks" / "post-index-change"
    planted.parent.mkdir()
    planted.write_text("subject data that must not reach the declared hooks path\n")

    read = _sterile.build(repo)
    try:
        declared = _sterile.config_as_data(Path(read.gitdir) / "config")
        where = declared.get("core.hookspath")
        assert where, "the constructed configuration declares no hooks path"
        where = Path(where)
        assert where.is_dir() and not any(where.iterdir()), (
            f"the constructed hooks path is not an empty directory: {where}"
        )
        assert where.resolve().parent == Path(read.scratch).resolve(), (
            f"the constructed hooks path is not a scratch sibling: {where}"
        )
        assert not where.resolve().is_relative_to(Path(read.gitdir).resolve()), (
            f"the constructed hooks path is inside copied subject state: {where}"
        )
        carried = Path(read.gitdir) / "empty-hooks" / "post-index-change"
        assert carried.read_text() == planted.read_text(), (
            "the fixture did not prove that copied subject state and the declared hooks path differ"
        )
        assert not (where / planted.name).exists(), (
            "a file the subject planted can reach the declared hooks directory"
        )
    finally:
        read.discard()


def test_a_subject_empty_hooks_program_cannot_run_during_sterile_construction(tmp_path):
    """Construction itself cannot run a program planted under `empty-hooks`.

    A nested repository forces the constructed working-tree view, and future
    stat data forces the copied index to be refreshed.  That refresh happens
    before the later no-child barrier, which is why this calls `sterile.build`
    directly.  With the hooks path inside `sterile.git`, the copied
    `post-index-change` writes both witnesses; with the scratch-sibling path it
    is copied as inert state but never selected for execution.
    """
    repo = _isolated_committed_repo(tmp_path, "empty-hooks-program")
    nested = _isolated_committed_repo(repo, "nested")
    witness = tmp_path / "empty-hooks-hook-ran.txt"
    subject_write = repo / "HOOK-WROTE-INTO-SUBJECT.txt"
    program = repo / ".git" / "empty-hooks" / "post-index-change"
    program.parent.mkdir()
    program.write_text(
        "#!/bin/sh\n"
        f"printf ran > {witness}\n"
        f"printf owned > {subject_write}\n",
    )
    program.chmod(0o755)
    future = time.time_ns() + 60_000_000_000
    os.utime(repo / "f.txt", ns=(future, future))

    read = _sterile.build(repo)
    try:
        assert nested.is_dir(), "the fixture did not create the nested repository that forces a view"
        assert (Path(read.gitdir) / "empty-hooks" / "post-index-change").is_file(), (
            "the fixture did not carry the subject state that used to populate core.hooksPath"
        )
        assert not witness.exists(), "sterile construction ran the subject's hook"
        assert not subject_write.exists(), "the subject's hook wrote into the subject during construction"
    finally:
        read.discard()


def test_a_remote_with_two_urls_is_fetched_from_the_first_like_real_git(tmp_path):
    """Git keeps every `remote.<name>.url` and fetches from the FIRST of them.

    Reading the URL through a single-valued answer took the LAST, so a subject
    declaring two URLs made `ls-remote origin` report a DIFFERENT repository's
    HEAD at exit 0 — a wrong answer rather than a refusal, and a regression
    against frozen 2.4.0, which agrees with Git here.

    Reverting `config_values_as_data` to a single-valued read, or taking
    `found[-1]` instead of `found[0]`, makes this test report the second
    repository's HEAD where Git reports the first.
    """
    one, two = tmp_path / "one.git", tmp_path / "two.git"
    for bare in (one, two):
        _git(tmp_path, "init", "-q", "--bare", str(bare))
    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init", "-q", "-b", "main")
    _git(seed, "config", "user.email", "t@e.invalid")
    _git(seed, "config", "user.name", "T")
    (seed / "f.txt").write_text("one\n")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "one")
    _git(seed, "push", "-q", str(one), "HEAD:refs/heads/main")
    (seed / "f.txt").write_text("two\n")
    _git(seed, "commit", "-q", "-am", "two")
    _git(seed, "push", "-q", str(two), "HEAD:refs/heads/main")

    subject = tmp_path / "subject"
    subject.mkdir()
    _git(subject, "init", "-q", "-b", "main")
    _git(subject, "remote", "add", "origin", f"file://{one}")
    _git(subject, "remote", "set-url", "--add", "origin", f"file://{two}")

    real = subprocess.run(["git", "ls-remote", "origin", "HEAD"], cwd=subject,
                          capture_output=True)
    governed = gitread._run(subject, "ls-remote", "origin", "HEAD", text=False)

    assert real.returncode == 0 and real.stdout, "the control did not answer"
    assert governed == real.stdout, (
        "the governed answer names a different remote from the one Git fetches"
    )


def test_a_leading_dash_remote_url_refuses_before_launch_and_stays_uncreated(tmp_path):
    """A subject URL is data, never an option; no executable payload is needed.

    The absent marker is deliberately the value an unsafe command line would
    select as its upload-pack program.  It is not executable and this test
    creates no program: the named pre-launch refusal, together with the absent
    marker, proves the subject value was not handed to Git as an option.
    """
    reader = _isolated_committed_repo(tmp_path, "leading-dash-reader")
    marker = tmp_path / "MARKER_MUST_NOT_BE_CREATED"
    with (reader / ".git" / "config").open("a", encoding="utf-8") as handle:
        handle.write(f'\n[remote "origin"]\n\turl = --upload-pack={marker}\n')

    with _pytest.raises(_GitRefusal) as raised:
        gitread._run(reader, "ls-remote", "origin", "HEAD", text=False)
    assert "resolved remote URL begins with `-`" in raised.value.render()
    assert raised.value.detail["remote"] == "origin"
    assert raised.value.detail["url"] == f"--upload-pack={marker}"
    assert not marker.exists(), "the subject-selected marker was created before refusal"


def test_ls_remote_origin_is_byte_identical_and_uses_a_positional_separator(
        tmp_path, monkeypatch):
    """The transport terminator preserves ordinary Git output and is structural.

    The real-Git comparison is the compatibility half.  The captured governed
    launch is the independent construction half: removing the terminator makes
    this assertion fail before any subject value could be reclassified as an
    option.  The capture returns successfully and launches no helper.
    """
    remote = _isolated_committed_repo(tmp_path, "separator-remote")
    reader = _isolated_committed_repo(tmp_path, "separator-reader")
    _isolated_git(reader, "remote", "add", "origin", str(remote))

    real = subprocess.run(["git", "ls-remote", "origin", "HEAD"], cwd=reader,
                          capture_output=True)
    governed = gitread._run(reader, "ls-remote", "origin", "HEAD", text=False)
    assert real.returncode == 0, real.stderr
    assert governed == real.stdout

    commands = []
    real_launch = gitread.instrument.launch

    def capture(command, **_kwargs):
        if command[:2] != ("git", "ls-remote"):
            return real_launch(command, **_kwargs)
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(gitread.instrument, "launch", capture)
    assert gitread._run(reader, "ls-remote", "origin", "HEAD", text=False) == b""
    assert commands == [
        ("git", "ls-remote", "--upload-pack=git-upload-pack", "--", str(remote), "HEAD"),
    ]


def test_a_repeated_fetch_refspec_still_finds_the_branchs_upstream(tmp_path):
    """`remote.<name>.fetch` is multi-valued and Git uses the whole list.

    Reconstructing the carried `[remote]` section from the single-valued view
    kept only the LAST refspec, so an ordinary `status --porcelain=v2 --branch`
    answered with no `branch.upstream` and no `branch.ab` at exit 0 — a false
    answer rather than a refusal, and a regression against frozen 2.4.0, which
    agrees with Git here.  This is the same class as the two-URL defect, in the
    neighbouring consumer.

    Reverting `_write_config` to write `all_declared`'s single-valued sibling
    drops the first refspec and this test loses both upstream lines.
    """
    repo = _committed(tmp_path, "repeated-fetch")
    head = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "update-ref", "refs/remotes/origin/main", head)
    _git(repo, "config", "branch.main.remote", "origin")
    _git(repo, "config", "branch.main.merge", "refs/heads/main")
    _git(repo, "config", "remote.origin.url", str(repo))
    _git(repo, "config", "--add", "remote.origin.fetch",
         "+refs/heads/*:refs/remotes/origin/*")
    _git(repo, "config", "--add", "remote.origin.fetch",
         "+refs/heads/other:refs/remotes/origin/other")

    real = subprocess.run(["git", "status", "--porcelain=v2", "--branch"],
                          cwd=repo, capture_output=True)
    governed = gitread._run(repo, "status", "--porcelain=v2", "--branch", text=False)

    assert b"# branch.upstream" in real.stdout, "the control found no upstream"
    assert governed == real.stdout, (
        "the governed answer lost a branch relation Git reports"
    )


def test_a_main_configuration_include_is_refused_rather_than_answered_around(tmp_path):
    """An include in the MAIN config is refused, as one in `config.worktree` is.

    The configuration root is REPLACED, not copied, so an `include.path` names a
    file whose contents never reach the constructed directory.  Its storage
    descriptors are then simply absent and Git answers about different storage
    semantics without saying so: declaring `core.autocrlf` through an include
    made a clean tracked file report as modified, at exit 0.  Frozen 2.4.0
    refuses such a repository, so refusing is the floor's own answer.

    Removing the refusal makes this test receive a porcelain record for a file
    real Git reports as clean.
    """
    repo = _committed(tmp_path, "main-include")
    included = repo / ".git" / "storage.inc"
    _git(repo, "config", "include.path", str(included))
    _git(repo, "config", "--file", str(included), "core.autocrlf", "true")

    real = subprocess.run(["git", "status", "--porcelain=v2"], cwd=repo,
                          capture_output=True)
    assert real.returncode == 0

    with _pytest.raises(_GitRefusal) as raised:
        gitread._run(repo, "status", "--porcelain=v2", text=False)
    assert "includes another configuration file" in raised.value.render()


@_pytest.mark.parametrize("hostile", [
    'true\n\thooksPath = .git/hooks',
    'true\n[include]\n\tpath = /etc/gitconfig',
    'a"b',
    'back\\slash',
    'tab\there',
])
def test_a_subject_value_cannot_write_a_line_into_the_generated_configuration(tmp_path, hostile):
    """Parsing and rendering a configuration value must be inverses.

    `_config_value_as_data` DECODES `\\n`, `\\t` and `\\b`.  Writing the decoded
    text back verbatim let a subject's value carry a real newline into the
    configuration root this build owns, so every line after it was a
    configuration line the SUBJECT wrote — including `core.hooksPath`, which is
    half the hook closure and sorts after the harness's own entry, so the
    subject's line won.  A blind certification drove that to `ls-remote`
    answering at exit 0 with the subject's program having run.

    Removing `_config_value_as_text` from the rendering makes real Git read a
    key this test never declared, and the round-trip assertion below fails.
    """
    repo = _committed(tmp_path, "rendered")
    encoded = (hostile.replace("\\", "\\\\").replace('"', '\\"')
                      .replace("\n", "\\n").replace("\t", "\\t"))
    # THROUGH A KEY THE BUILD ACTUALLY CARRIES. A key outside `STORAGE_KEYS` is
    # never rendered, so injecting through one tests nothing — the first version
    # of this test did exactly that and passed with the repair reverted.
    config = repo / ".git" / "config"
    text = config.read_text(encoding="utf-8").splitlines(True)
    text.insert(1, f'\tsymlinks = "{encoded}"\n')
    config.write_text("".join(text), encoding="utf-8")
    assert _git(repo, "config", "--get", "core.symlinks") == hostile + "\n"

    generated = tmp_path / "generated"
    generated.mkdir()
    _sterile._write_config(generated, repo / ".git", repo / ".git", bare=False)

    # Ask REAL Git what the generated file declares. Nothing the subject wrote
    # may appear as a KEY, and any value carried must come back whole.
    listed = subprocess.run(
        ["git", "config", "--file", str(generated / "config"), "--list", "-z"],
        capture_output=True, text=True, check=True,
    )
    declared = {}
    for record in listed.stdout.split("\0"):
        if not record:
            continue
        name, _, value = record.partition("\n")
        declared[name] = value
    assert "core.hookspath" in declared, "the hook closure vanished from the generated root"
    assert declared["core.hookspath"].endswith("empty-hooks"), (
        f"the subject moved the hooks path to {declared['core.hookspath']!r}"
    )
    assert "include.path" not in declared, "the subject wrote an include into the generated root"
    if "core.symlinks" in declared:
        assert declared["core.symlinks"] == hostile, (
            "the carried value did not survive the round trip whole"
        )


def test_a_repeated_key_declared_in_both_roots_keeps_both_values(tmp_path):
    """`config.worktree` LAYERS over `config`; it does not replace a value list.

    Merging the two roots with `dict.update` swapped the whole list, so a key
    declared in BOTH lost the main config's values — the third instance of the
    repeated-key class.  With the default refspec in `config` and a second one
    in `config.worktree`, upstream resolution needs both.

    Restoring `dict.update` here drops the first refspec and this test loses the
    branch relation real Git reports.
    """
    repo = _committed(tmp_path, "both-roots")
    head = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "update-ref", "refs/remotes/origin/main", head)
    _git(repo, "config", "branch.main.remote", "origin")
    _git(repo, "config", "branch.main.merge", "refs/heads/main")
    _git(repo, "config", "remote.origin.url", str(repo))
    _git(repo, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
    _git(repo, "config", "extensions.worktreeConfig", "true")
    (repo / ".git" / "config.worktree").write_text(
        '[remote "origin"]\n\tfetch = +refs/heads/other:refs/remotes/origin/other\n',
        encoding="utf-8")

    real = subprocess.run(["git", "status", "--porcelain=v2", "--branch"],
                          cwd=repo, capture_output=True)
    governed = gitread._run(repo, "status", "--porcelain=v2", "--branch", text=False)
    assert b"# branch.upstream" in real.stdout, "the control found no upstream"
    assert governed == real.stdout, "a value declared in the main root was dropped"
