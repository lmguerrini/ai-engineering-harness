"""gitread against a throwaway repository built fresh in a tmp dir.

No mocking: every function under test shells out to a real `git`, so the
throwaway repo is the fixture.
"""

import os
import subprocess

import pytest

import gitread
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


def test_probe_distinguishes_cannot_ask_from_no(repo, tmp_path):
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    answer = gitread.probe(not_a_repo, "rev-parse", "--verify", "HEAD")
    # Git ran, found no repository, and exited non-zero for an undeclared
    # status: this must be a failure, not a silent negative.
    assert answer.answered
    assert answer.failed


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


@pytest.mark.parametrize("option", ["--ext-diff", "--textconv"])
def test_the_option_that_re_enables_it_is_refused(tmp_path, option):
    """The options are NAMED here rather than read from
    `gitread.CODE_ENABLING_OPTIONS`, and that is the point.

    The first version looped over the constant, so emptying the constant made
    the loop run zero times and the test pass — it survived that mutant in this
    release's own mutation pass. **A test that iterates its subject's
    configuration tests nothing when the configuration is emptied**, which is
    the same anti-test an auditor had already found twice in this release under
    a different disguise."""
    repo, marker = _repo_that_runs_a_program(tmp_path, "diff.external")
    assert option in gitread.CODE_ENABLING_OPTIONS, "the refusal list still names it"
    with pytest.raises(_IntegrityError):
        gitread.probe(repo, "diff", option, "HEAD", negative_statuses=())
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

    with pytest.raises(_IntegrityError):
        gitread.probe(repo, "cat-file", "--filters", "HEAD:f.txt", negative_statuses=())
    assert not (repo / "FILTER_RAN").exists()


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

    with pytest.raises(_IntegrityError):
        gitread.probe(sup, "diff", "--submodule=diff", negative_statuses=())
    assert not (tmp_path / "SUBMODULE_DIFF_RAN").exists()


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


def test_an_option_and_its_value_written_apart_are_still_that_option(tmp_path):
    """Git accepts `--submodule=diff` and `--submodule diff`. The first version
    of the refusal knew only the first spelling — named by a blind reader as its
    next probe, in the last thing it wrote before its own provider stopped it."""
    repo, _ = _repo_that_runs_a_program(tmp_path, "diff.external")
    with pytest.raises(_IntegrityError):
        gitread.probe(repo, "diff", "--submodule", "diff", "HEAD", negative_statuses=())
    # And the word `diff` as an ordinary argument is still an ordinary argument.
    assert gitread.probe(repo, "diff", "--stat", "HEAD", negative_statuses=()).ok


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


@pytest.mark.parametrize("key", [
    "alias.x", "merge.m.driver", "submodule.a.update", "protocol.ext.command",
    "remote.o.vcs", "trailer.t.command", "interactive.difffilter", "guitool.g.cmd",
    "filter.f.clean", "filter.f.smudge", "filter.f.process",
])
def test_a_program_valued_key_with_no_named_closure_refuses(tmp_path, key):
    """Five separate routes by which a repository being read chose a program to
    run were found in four consecutive audit rounds — `diff.external`, an
    attribute-selected driver, a filter chain, `core.gitProxy`, and
    `remote.<name>.uploadpack`. Each was closed where the previous repair could
    not see it, and each time the next reader found another.

    **Closing routes one at a time was losing**, so the check moved to the shape
    of the key. None of the keys below has a route anybody here has traced; all
    of them refuse."""
    repo = _repo_setting(tmp_path, key)
    assert gitread.program_valued_config(repo) == [key.lower()]
    with pytest.raises(_IntegrityError):
        gitread.probe(repo, "status", "--porcelain", negative_statuses=())


@pytest.mark.parametrize("key", ["core.pager", "core.editor", "diff.external",
                                 "credential.helper"])
def test_a_program_valued_key_this_module_actually_closes_is_allowed(tmp_path, key):
    """The bound, and it matters more than the test above. Refusing to read a
    repository because its developer set a pager is hardening in name and
    obstruction in fact — the closure is what protects, not the absence of the
    key.

    **`filter.f.smudge` used to be in this list and has moved to the one above.**
    Its closure said the filter chain was "reachable only through --filters,
    which is refused as an argument", and that was not true: an ordinary `diff`
    converts the worktree through the clean filter, and a whole-candidate
    reading watched one run twice while this module reported nothing to see. A
    closure that is merely asserted is worse than an absent one, because the key
    is then exempt from the shape rule that catches everything nobody has
    traced."""
    repo = _repo_setting(tmp_path, key)
    assert gitread.program_valued_config(repo) == []
    assert gitread.probe(repo, "status", "--porcelain", negative_statuses=()).answered


def test_a_repository_cannot_hide_a_key_by_breaking_its_own_configuration(tmp_path):
    """The check FAILS CLOSED, and the first version did not.

    `git config include.path /bin/sh` makes every subsequent config read fail,
    so a repository could disable the check that inspects it by breaking itself
    — seven unrecognised program-valued keys came back as none. The
    discriminator that tells "not a repository" from "unreadable config" asks
    the FILESYSTEM, because it has to work in exactly the case where Git is what
    is failing.
    """
    repo = _repo_setting(tmp_path, "include.path")
    with pytest.raises(_IntegrityError):
        gitread.program_valued_config(repo)
    with pytest.raises(_IntegrityError):
        gitread.probe(repo, "status", "--porcelain", negative_statuses=())


def test_a_path_that_is_not_a_repository_is_still_the_callers_own_refusal(tmp_path):
    """A missing directory is not a configuration finding, and reporting it as
    one hid what was actually wrong."""
    assert gitread.program_valued_config(tmp_path / "nowhere") == []


def test_a_configuration_read_is_exempt_because_reading_config_runs_nothing(tmp_path):
    """A caller asking about a broken config is entitled to the refusal that
    names the real problem. Hijacking it turned *your config does not parse*
    into a security finding about a repository nobody could read."""
    repo = _repo_setting(tmp_path, "include.path")
    with pytest.raises(GitRefusal):
        gitread.config_with_origin(str(repo))


def test_the_inspection_does_not_re_enter_itself(tmp_path):
    """The inspection runs Git, and every Git run is inspected. The first guard
    was on the verb `config` — and the function's own fallback probe was a
    DIFFERENT verb, so it re-entered: two test modules that take ten seconds ran
    for over six minutes without finishing."""
    repo = _repo_setting(tmp_path, "merge.m.driver")
    import time

    started = time.monotonic()
    with pytest.raises(_IntegrityError):
        gitread.probe(repo, "status", "--porcelain", negative_statuses=())
    assert time.monotonic() - started < 10, "the inspection is recursing"


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


def test_the_inspection_guard_is_per_thread_and_not_per_module(tmp_path):
    """A blind reader held one thread inside the inspection and issued a second
    public read from another. The guard was a module-level flag, so the second
    read skipped its inspection entirely and ran against a repository nobody had
    checked.

    **A guard against a function calling itself became a guard against anyone
    calling it** — a different and much larger claim, made by accident."""
    import threading

    repo = _repo_setting(tmp_path, "merge.m.driver")
    entered, release = threading.Event(), threading.Event()
    original = gitread._program_valued_config

    # `**_` so this stays a test of thread-locality: the inspection's own
    # parameters are not this oracle's subject, and pinning them here would make
    # it fail whenever they change for unrelated reasons.
    def slow(repository, fnmatch, timeout, **_):
        entered.set()
        release.wait(5)
        return original(repository, fnmatch, timeout)

    gitread._program_valued_config = slow
    def _held():
        # This read refuses too, once released — expected, and swallowed so the
        # thread does not surface it as an unhandled exception that reads like a
        # defect in the test.
        try:
            gitread.probe(repo, "status", "--porcelain", negative_statuses=())
        except _IntegrityError:
            pass

    held = threading.Thread(target=_held)
    held.start()
    try:
        assert entered.wait(5), "the first read never reached the inspection"
        with pytest.raises(_IntegrityError):
            gitread.probe(repo, "status", "--porcelain", negative_statuses=())
    finally:
        release.set()
        held.join()
        gitread._program_valued_config = original


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

def test_a_configured_clean_filter_is_refused_rather_than_run(tmp_path):
    """O1/O9. The closure said a filter chain was reachable only through
    `--filters`, which this module refuses as an argument. An ordinary `diff`
    converts the worktree through the clean filter regardless, and a
    whole-candidate reading watched one run twice while `program_valued_config`
    reported nothing to see."""
    repo = tmp_path / "filtered"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@e.invalid")
    _git(repo, "config", "user.name", "T")
    marker = tmp_path / "the-filter-ran"
    program = tmp_path / "filter.sh"
    program.write_text(f"#!/bin/sh\necho ran >> {marker}\ncat\n")
    program.chmod(0o755)
    (repo / "f.txt").write_text("hello\n")
    (repo / ".gitattributes").write_text("f.txt filter=evil\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "config", "filter.evil.clean", str(program))
    (repo / "f.txt").write_text("hello\nchanged\n")

    assert gitread.program_valued_config(repo) == ["filter.evil.clean"]
    with pytest.raises(_IntegrityError):
        gitread._run(repo, "diff", "HEAD", timeout=30)
    assert not marker.exists(), "the repository's own program ran during a read"


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


def test_a_redirected_worktree_is_refused_for_every_caller(tmp_path):
    """O4. `core.worktree` sent reads to a sibling directory, so a workspace
    gate reported no unclassified files while one sat in the project it was
    asked about. The binding lives here so no caller has to remember it."""
    repo = tmp_path / "project"
    repo.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@e.invalid")
    _git(repo, "config", "user.name", "T")
    (repo / "tracked.txt").write_text("t\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    (repo / "unreviewed.py").write_text("u\n")
    assert "unreviewed.py" in gitread._run(repo, "ls-files", "--others", timeout=30)

    _git(repo, "config", "core.worktree", str(elsewhere))
    with pytest.raises(_IntegrityError, match="different directory"):
        gitread._run(repo, "ls-files", "--others", timeout=30)


def test_a_directory_inside_another_repository_is_refused(tmp_path):
    """O5. A release unpacked into an ignored vendor directory is not a checkout
    of its own: Git discovers the enclosing repository and answers about that."""
    outer = tmp_path / "adopter"
    outer.mkdir()
    _git(outer, "init", "-q", "-b", "main")
    _git(outer, "config", "user.email", "t@e.invalid")
    _git(outer, "config", "user.name", "T")
    (outer / "README.md").write_text("the adopter\n")
    _git(outer, "add", "-A")
    _git(outer, "commit", "-q", "-m", "base")
    vendored = outer / "vendor"
    vendored.mkdir()
    (vendored / "VERSION").write_text("2.4.1\n")
    with pytest.raises(_IntegrityError, match="different directory"):
        gitread._run(vendored, "ls-files", timeout=30)


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


def test_a_program_declared_in_the_worktree_config_is_seen_and_refused(tmp_path):
    """`--local` reads exactly one file and Git applies more than one.

    With `extensions.worktreeConfig`, Git also applies `config.worktree`, which
    `--local` never lists — so a `filter.x.clean` declared there was invisible to
    this inspection while Git ran it on every worktree conversion. An independent
    reading configured one with two `git config` calls and watched it execute
    seven times through this module. The marker below is the whole assertion: it
    must not exist.
    """
    marker = tmp_path / "the-program-ran"
    program = tmp_path / "p.sh"
    program.write_text(f"#!/bin/sh\necho ran >> {marker}\ncat\n")
    program.chmod(0o755)
    repo = _worktree_config_repo(tmp_path, "wtcfg", program)

    local_listing = _git(repo, "config", "--local", "--list", "--name-only")
    assert "filter.x.clean" not in str(getattr(local_listing, "stdout", local_listing)), (
        "the fixture does not mean what it says: --local already lists the key")
    assert gitread.program_valued_config(repo) == ["filter.x.clean"]
    for verb in (("diff", "--stat"), ("status", "--porcelain"), ("ls-files", "--others")):
        with pytest.raises(_IntegrityError):
            gitread._run(repo, *verb, timeout=30)
    assert not marker.exists(), "the repository's own program ran during a read"


def test_a_worktree_config_program_in_a_linked_worktree_is_seen_too(tmp_path):
    """The layout this pack develops in, where the file lives under the main
    repository's `worktrees/<name>/` rather than beside `config`."""
    marker = tmp_path / "linked-ran"
    program = tmp_path / "q.sh"
    program.write_text(f"#!/bin/sh\necho ran >> {marker}\ncat\n")
    program.chmod(0o755)
    main = _worktree_config_repo(tmp_path, "mainwt", program)
    linked = tmp_path / "linked"
    _git(main, "worktree", "add", "-q", "--detach", str(linked))
    _git(linked, "config", "--worktree", "filter.x.clean", str(program))
    assert gitread.program_valued_config(linked) == ["filter.x.clean"]
    with pytest.raises(_IntegrityError):
        gitread._run(linked, "status", "--porcelain", timeout=30)
    assert not marker.exists()


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


def test_a_disabled_extension_hides_nothing_because_git_ignores_it(tmp_path):
    """O4. The other side of O3: a `config.worktree` that Git does not apply is
    not a finding. Reporting it would refuse a repository over a program Git
    will never run, and this check reports what Git applies."""
    repo = _committed(tmp_path, "disabled_withfile")
    _git(repo, "config", "extensions.worktreeConfig", "true")
    _git(repo, "config", "--worktree", "filter.x.clean", "/bin/cat")
    assert gitread.program_valued_config(repo) == ["filter.x.clean"]
    _git(repo, "config", "extensions.worktreeConfig", "false")
    assert (repo / ".git" / "config.worktree").exists()
    assert gitread.program_valued_config(repo) == []
    assert gitread._run(repo, "ls-files", timeout=30).strip() == "f.txt"


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


def test_an_unparseable_scope_listing_is_refused_not_read_as_empty(tmp_path):
    """O7. An answer this function cannot parse is not an answer of `nothing`.

    `--show-scope -z` frames its reply as strictly alternating scope and key. If
    a future Git framed it differently — keys alone, say — the pairing would
    read every second key as a scope, match none of them against the repository
    scopes, and return `[]`. That is the fail-open this whole check exists to
    prevent, arriving through the parser instead of through a swallowed error,
    and mutation scoring found it: deleting the parity guard changed no test.

    Driven at the seam because Git cannot be made to emit the malformed framing;
    what is under test is this function's reading of the reply, not Git's.
    """
    repo = _committed(tmp_path, "oddframing")
    real = gitread._run

    def odd_listing(repository, *args, **kwargs):
        if args[:1] == ("config",):
            # Bytes, because that is what the inspection now asks `_run` for; a
            # fake that answers in the wrong type would be testing the seam
            # rather than the parsing.
            return b"\0".join([b"filter.x.clean", b"core.pager", b"gpg.program"]) + b"\0"
        return real(repository, *args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(gitread, "_run", odd_listing)
        with pytest.raises(_IntegrityError) as refused:
            gitread.program_valued_config(repo)
    assert "not an empty one" in str(refused.value)


def test_a_configuration_git_cannot_decode_is_still_read_and_still_inspected(tmp_path):
    """O8. A configuration key need not be valid UTF-8, and Git reads one that
    is not without complaint.

    `_run` decodes text with `surrogateescape` and `nul_paths` decodes the same
    way, both deliberately: a byte string that cannot be decoded must still
    reach a checker, because refusing to represent it is how it goes unexamined.
    Handing `nul_paths` a str meant re-encoding it, and a bare `.encode()`
    cannot invert a `surrogateescape` decode — so a repository carrying a
    non-UTF-8 subsection name raised `UnicodeEncodeError` out of every governed
    read: a denial naming no cause, which is neither of this module's refusals.
    Found by an independent reading, and it predated the scope repair on the
    line the repair rewrote.

    Both directions are asserted. The harmless case must READ, and the
    program-valued case must still be FOUND — a fix that made the undecodable
    key merely disappear would pass the first half and open the hole the whole
    check exists to close.
    """
    harmless = _committed(tmp_path, "undecodable")
    (harmless / ".git" / "config").write_bytes(
        (harmless / ".git" / "config").read_bytes()
        + b'[remote "caf\xe9"]\n\turl = https://example.invalid/x\n')
    assert gitread.program_valued_config(harmless) == []
    assert gitread._run(harmless, "ls-files", timeout=30).strip() == "f.txt"

    declared = _committed(tmp_path, "undecodable_program")
    (declared / ".git" / "config").write_bytes(
        (declared / ".git" / "config").read_bytes()
        + b'[filter "caf\xe9"]\n\tclean = /bin/cat\n')
    assert gitread.program_valued_config(declared) == ["filter.caf\udce9.clean"]
    with pytest.raises(_IntegrityError):
        gitread._run(declared, "ls-files", timeout=30)


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


def test_an_ssh_command_is_refused_when_ssh_is_actually_enabled(tmp_path):
    """O1. `core.sshcommand` is excused from the inspection because the standing
    configuration neutralises it — but `_transport_settings` POPS that
    neutralisation when a caller enables `ssh`, handing the repository's value
    straight back to Git. The closure said so in its own words and was applied
    anyway, so a repository's program ran through this module's hardened reader
    with no network, no socket and no ssh binary involved.

    The marker is the assertion. A test that only checked the refusal would pass
    against a version that refused *after* running the program.
    """
    repo, marker = _ssh_program_repo(tmp_path, "sshprog")
    enabled = ("ssh", "https", "file")
    assert gitread.program_valued_config(repo, allow_transports=enabled) == ["core.sshcommand"]
    with pytest.raises(_IntegrityError):
        gitread.probe(repo, "ls-remote", "origin", negative_statuses=(),
                      allow_transports=enabled)
    assert not marker.exists(), "the repository's own ssh program was executed"


def test_an_ssh_command_does_not_refuse_an_ordinary_read(tmp_path):
    """O2. The other half. While `ssh` is not enabled the neutralisation IS
    applied, the program genuinely cannot run, and refusing the repository would
    be the over-refusal this release has already repaired twice."""
    repo, marker = _ssh_program_repo(tmp_path, "sshprog_local")
    assert gitread.program_valued_config(repo) == []
    assert gitread._run(repo, "ls-files", timeout=30).strip() == "f.txt"
    assert not marker.exists()


def test_every_conditional_closure_is_known_to_the_inspection(tmp_path):
    """O4. Asked of the behaviour, not of the source: enabling each allowable
    transport and seeing which neutralisation disappears is what actually
    decides whether a closure still holds. A future override removed on the same
    condition arrives here as a failure rather than as a silent exemption."""
    baseline = set(gitread._config_environment(()))
    for transport in gitread.ALLOWABLE_TRANSPORTS:
        removed = baseline - set(gitread._config_environment((transport,)))
        for key in removed:
            assert gitread.CONDITIONAL_CLOSURES.get(key.lower()) == transport, (
                f"enabling {transport} removes the neutralisation of {key}, so any closure "
                f"claimed for it stops holding — declare it in CONDITIONAL_CLOSURES")


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


def test_a_mixed_case_transport_name_is_pinned_in_the_repositorys_own_spelling(tmp_path):
    """O8. Git folds a config section and variable name to lower case but keeps a
    SUBSECTION verbatim, so `protocol.Review.allow` and `protocol.review.allow`
    are different keys to it.

    The first version of this pinning named the key from its own lowercased copy,
    which wrote a setting the repository had never made and left the one it had
    made in force. An independent certification reproduced it with an installed
    remote helper whose transport name carries a capital: the helper ran, and the
    publication verification accepted the namespace it invented.

    The marker counts invocations, so a repair that merely refuses later still
    fails this.
    """
    repo = _committed(tmp_path, "mixedcase")
    marker = tmp_path / "HELPER_INVOKED"
    helpers = tmp_path / "helpers"
    helpers.mkdir()
    helper = helpers / "git-remote-Review"
    helper.write_text(
        "#!/bin/sh\n"
        f"printf 'x' >> {marker}\n"
        "echo\n")
    helper.chmod(0o755)
    _git(repo, "config", "protocol.Review.allow", "always")
    _git(repo, "remote", "add", "origin", "Review::example")

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PATH", f"{helpers}:{os.environ.get('PATH', '')}")
        found, protocols = gitread._inspect(repo, 30, ())
        assert protocols == ("Review",), "the repository's own spelling was not carried"
        answer = gitread.probe(repo, "ls-remote", "origin", negative_statuses=())
        assert answer.answered and not answer.ok
    assert not marker.exists(), "the repository re-enabled a mixed-case transport and its helper ran"


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


@pytest.mark.parametrize("verb", [
    ("ls-files",), ("status", "--porcelain"), ("diff", "--stat"),
    ("log", "--oneline", "-1"), ("cat-file", "-t", "HEAD"), ("for-each-ref",),
])
def test_the_root_binding_covers_every_verb_not_only_the_enumeration(tmp_path, verb):
    """M4. Every binding test drove `ls-files`, so *for every caller, every verb*
    was enforced by code and pinned by nothing. A redirect must refuse whatever
    the caller happened to ask for."""
    repo = tmp_path / "bound"
    repo.mkdir()
    elsewhere = tmp_path / "away"
    elsewhere.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@e.invalid")
    _git(repo, "config", "user.name", "T")
    (repo / "f.txt").write_text("hello\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    assert gitread._run(repo, *verb, timeout=30) is not None

    _git(repo, "config", "core.worktree", str(elsewhere))
    with pytest.raises(_IntegrityError, match="different directory"):
        gitread._run(repo, *verb, timeout=30)


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


def test_a_worktree_inspection_that_times_out_does_not_clear_the_read(tmp_path):
    """A deadline the caller set is the caller's refusal, not a clean bill of health.

    The first version of the worktree inspection wrapped its read in
    `except GitRefusal: pass`, reasoning that it errors when the extension is
    off. It does — and it also errors when it TIMES OUT. So a per-worktree
    configuration large enough to outlast a caller-supplied deadline cleared the
    inspection and the governed read proceeded, with `filter.x.clean` applied by
    Git the whole time. Reproduced by an independent reading against real Git.
    """
    repo = _slow_worktree_config(tmp_path, "slowwt")
    assert gitread.program_valued_config(repo, timeout=30) == ["filter.x.clean"], (
        "the fixture does not mean what it says: the key is not configured")

    # Calibrated against the read the inspection actually performs. An earlier
    # version timed `--local` and `--worktree` separately and set a deadline
    # between them, which stopped meaning anything the moment the inspection
    # stopped being two reads: the single scope-labelled read finished inside
    # that budget and the oracle passed without ever reaching a timeout.
    cost = _timed(repo)
    # Capped as well as scaled. The budget came from one warm measurement, so a
    # transient inflation of that measurement alone would raise the deadline
    # above the real read and the oracle would stop biting. A smaller budget can
    # only make the timeout more certain, which is the direction this test wants.
    budget = min(cost / 4, 0.02)
    if budget <= 0:
        pytest.skip("this host reads the configuration too fast to time")

    # NOT `== []`. The failure being guarded is precisely an inspection that
    # cannot finish and reports nothing found, so an empty list here is the
    # defect and must not be mistaken for a pass.
    with pytest.raises(GitRefusal) as refusal:
        gitread.program_valued_config(repo, timeout=budget)
    assert "timed out" in str(refusal.value)
    with pytest.raises((GitRefusal, _IntegrityError)):
        gitread._run(repo, "ls-files", timeout=budget)


def _timed(repository):
    """How long the inspection's own read of this repository takes, warm."""
    import time
    gitread._run(repository, "config", "--list", "--name-only", "--show-scope", "-z",
                 timeout=30)
    start = time.monotonic()
    gitread._run(repository, "config", "--list", "--name-only", "--show-scope", "-z",
                 timeout=30)
    return time.monotonic() - start


def test_an_unreadable_worktree_configuration_is_refused_not_cleared(tmp_path):
    """A check that cannot read its subject has not cleared it.

    Answered by the handler that already owns every failure of this read, not by
    a second one beside it: Git validates `config.worktree` during the LOCAL
    read as well, so a malformed file fails before the worktree listing is even
    attempted. Written first as its own `except`, and a mutation showed that
    half of it was unreachable.
    """
    repo = tmp_path / "brokenwt"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@e.invalid")
    _git(repo, "config", "user.name", "T")
    (repo / "f.txt").write_text("hello\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "config", "extensions.worktreeConfig", "true")
    (repo / ".git" / "config.worktree").write_text("[broken\nnot valid config\n")
    with pytest.raises(_IntegrityError):
        gitread.program_valued_config(repo, timeout=30)
    with pytest.raises(_IntegrityError):
        gitread._run(repo, "ls-files", timeout=30)


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
