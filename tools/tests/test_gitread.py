"""gitread against a throwaway repository built fresh in a tmp dir.

No mocking: every function under test shells out to a real `git`, so the
throwaway repo is the fixture.
"""

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

    def slow(repository, fnmatch, timeout):
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
