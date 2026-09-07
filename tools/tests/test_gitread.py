"""gitread against a throwaway repository built fresh in a tmp dir.

No mocking: every function under test shells out to a real `git`, so the
throwaway repo is the fixture.
"""

import os
import subprocess
from pathlib import Path

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

    # The refusal this used to assert is gone; the MEASUREMENT it carried is the
    # half that mattered and is stronger without it. `cat-file --filters` is a
    # third route by which a subject names a program, and it now reads.
    answer = gitread.probe(repo, "cat-file", "--filters", "HEAD:f.txt", negative_statuses=())
    assert answer.answered, answer.cause
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


def _hostile(repo, script, *, attributes="* diff=evil filter=evil\n"):
    """Every ordinary route by which a repository names a program for Git to run."""
    for key in ("filter.evil.clean", "filter.evil.smudge", "diff.evil.textconv",
                "diff.external", "core.fsmonitor", "core.alternateRefsCommand",
                "core.pager", "core.editor", "credential.helper", "gpg.program",
                "sequence.editor", "uploadpack.packObjectsHook", "core.gitProxy"):
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
    (inner / ".gitattributes").write_text("* diff=evil filter=evil\n")
    _commit_all(inner, "i.txt")
    sup = tmp_path / "sup"
    sup.mkdir()
    _git(sup, "init", "-q", "-b", "main")
    _commit_all(sup, "top.txt")
    _git(sup, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(inner), "mod")
    _git(sup, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "sub")
    module = sup / ".git" / "modules" / "mod"
    for key in ("filter.evil.clean", "diff.evil.textconv", "diff.external"):
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
    fails this without anybody having to have thought of it."""
    script, _marker = _marker_script(tmp_path)
    repo = tmp_path / "subject"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _hostile(repo, script)
    (repo / ".git" / "extra").write_text(f'[diff "evil"]\n\ttextconv = {script}\n')
    _git(repo, "config", "include.path", "extra")
    _commit_all(repo)

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
    repo = _repo_setting(tmp_path, "filter.f.clean")
    assert gitread.program_valued_config(repo) == ["filter.f.clean"]
    assert gitread.probe(repo, "status", "--porcelain", negative_statuses=()).answered


@pytest.mark.parametrize("key", [
    "alias.x", "merge.m.driver", "submodule.a.update", "protocol.ext.command",
    "remote.o.vcs", "trailer.t.command", "interactive.difffilter", "guitool.g.cmd",
    "filter.f.clean", "filter.f.smudge", "filter.f.process",
    "core.pager", "core.editor", "diff.external", "credential.helper",
])
def test_a_program_valued_key_is_reported_and_the_repository_still_reads(tmp_path, key):
    """The same key set the removed refusal test carried, asserting the stronger
    property. Every one of these used to divide into "refused" and "closed"; the
    division is gone because neither outcome can execute anything now."""
    repo = _repo_setting(tmp_path, key)
    assert gitread.program_valued_config(repo) == [key.lower()]
    answer = gitread.probe(repo, "status", "--porcelain", negative_statuses=())
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
    could not see it: the directory is empty instead."""
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

    answer = gitread.probe(repo, "status", "--porcelain", negative_statuses=())
    assert answer.answered, answer.cause
    assert "secret-untracked.txt" in answer.value, (
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


def test_a_view_built_across_a_filesystem_boundary_keeps_every_mode(tmp_path, monkeypatch):
    """The subject does not have to be on the same filesystem as the scratch
    directory, and when it is not, `os.link` fails with EXDEV and the copy fallback
    runs. That fallback copied CONTENT ONLY: an executable arrived in the view as
    644, Git compared it with 100755 in the index, and a governed `status` reported
    a file MODIFIED that real Git said nothing about — a wrong answer at exit 0,
    from a subject nobody had to make hostile.

    Reproduced first on a real case-sensitive disk image, where the subject and the
    system temp directory genuinely are different devices. It is pinned here by
    making `os.link` fail instead, so the fallback is exercised on one filesystem
    and the oracle does not need two.
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
    "assume unchanged", "info exclude", "sparse checkout",
])
def test_the_sterile_answer_equals_real_gits_answer(tmp_path, shape):
    """Content-encoding and ref-shape cases, each of which produced a WRONG answer
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


def test_a_walk_that_cannot_look_refuses_rather_than_finding_nothing(tmp_path):
    """A check that could not read its subject has not cleared it."""
    repo = tmp_path / "subject"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit_all(repo)
    locked = repo / "locked"
    locked.mkdir()
    (locked / "inner.txt").write_text("x\n")
    locked.chmod(0o000)
    try:
        answer = gitread.probe(repo, "status", "--porcelain", negative_statuses=())
        # Either it refuses, or it answers exactly as real git does — what it must
        # not do is report a clean tree it could not look at.
        real = _real_git(repo, "status", "--porcelain")
        if answer.answered:
            assert answer.value == real.stdout.strip()
    finally:
        locked.chmod(0o755)


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
        _hostile(repo, script)
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
