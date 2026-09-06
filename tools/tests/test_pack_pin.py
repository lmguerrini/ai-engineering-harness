"""A pin is worth what a consumer can check about it.

Two rounds of motivating defects, both in this pack's own manifest.

RP2.1: the digest was computed over 81 tracked files and the manifest then
became the 82nd, so recomputing it produced a different value forever after.
Nothing failed and no test caught it, because the manifest was written by
different code than the code that would verify it.

RP2.1.1: the verifier ran, printed `pack pin verified`, and meant six things
less than that sentence. Everything under "falsification" below was **accepted**
by the previous implementation and reproduced by execution before repair. They
are the tests that would have failed then, which is the only kind worth adding
after the fact.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import pack_pin


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)


def _write_manifest(root, **overrides):
    digest, count = pack_pin.tree_digest(root)
    manifest = {
        "pack": "test-pack",
        "version": (root / "VERSION").read_text().strip(),
        "state": "QUALIFIED_AND_FROZEN",
        pack_pin.DIGEST_COUNT_KEY: count,
        "tree_digest_sha256": digest,
        "digest_excludes": pack_pin.MANIFEST_NAME,
        "digest_algorithm": pack_pin.DIGEST_ALGORITHM,
        "gate_record": "GATE.md",
        "tests": {"passed": 3},
    }
    manifest.update(overrides)
    (root / pack_pin.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def _commit_manifest(root, why="manifest"):
    """Commit the manifest a test just wrote.

    RP2.4.1 R5 compares the manifest on disk with the one at HEAD, because it is
    the single file the digest cannot cover. These tests are about what the
    manifest's FIELDS mean, and they used to establish that by editing the file
    and leaving it uncommitted — a shape no shipped release has. Committing it
    keeps each test's real subject and stops it also asserting, incidentally,
    that an uncommitted manifest verifies.
    """
    _git(root, "add", pack_pin.MANIFEST_NAME)
    _git(root, "commit", "--quiet", "-m", why)


def _head(root):
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def pack(tmp_path):
    root = tmp_path / "pack"
    root.mkdir()
    _git(root, "init", "--quiet", "--initial-branch", "main")
    _git(root, "config", "user.name", "Ordinary Human")
    _git(root, "config", "user.email", "human@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "VERSION").write_text("2.1.1\n")
    (root / "GATE.md").write_text("# gate\n")
    (root / "tool.py").write_text("print('hi')\n")
    (root / ".gitignore").write_text("*.log\n")
    _git(root, "add", "VERSION", "GATE.md", "tool.py", ".gitignore")
    _git(root, "commit", "--quiet", "-m", "pack")

    _write_manifest(root)
    _git(root, "add", pack_pin.MANIFEST_NAME)
    _git(root, "commit", "--quiet", "-m", "manifest")
    return root


# --- the pin verifies at all -------------------------------------------------

def test_a_manifest_verifies_after_being_committed_alongside_the_tree(pack):
    """The self-reference case, which the first real manifest failed.

    Committing the manifest changes the tracked file set. If the digest covered
    the manifest, this would fail — permanently, and only for someone who
    actually tried to check it.
    """
    assert pack_pin.verify_pin(pack) == []


def test_the_right_version_revision_digest_and_state_verify_together(pack):
    manifest = json.loads((pack / pack_pin.MANIFEST_NAME).read_text())
    assert pack_pin.verify_pin(
        pack,
        expect_version="2.1.1",
        expect_sha=_head(pack),
        expect_digest=manifest["tree_digest_sha256"],
        expect_state="QUALIFIED_AND_FROZEN",
    ) == []


def test_the_digest_is_of_the_content_and_not_of_the_filesystem(pack):
    """Calling a pure function twice and comparing the answers was the whole of
    this test, and a blind auditor named it: it cannot fail, so it establishes
    nothing about the digest.

    The property actually worth pinning is that the digest is CONTENT-addressed.
    Rewriting a file with the same bytes moves its mtime, its inode and its
    ctime; if any of those reached the hash, a release would fail to verify
    after a checkout that changed nothing — which is the failure this digest
    exists to make impossible."""
    import os
    import time

    before = pack_pin.tree_digest(pack)
    target = pack / "tool.py"
    content = target.read_bytes()
    time.sleep(0.01)
    target.unlink()
    target.write_bytes(content)
    os.utime(target, (0, 0))
    assert pack_pin.tree_digest(pack) == before, "the digest moved without the content moving"

    # SAME LENGTH, deliberately. Appending bytes changes the framed length, so
    # a digest that framed the length and never hashed the content would still
    # pass — a blind reader removed `digest.update(content)` and said so. One
    # byte flipped in place is the change only a content hash can see.
    flipped = bytearray(content)
    flipped[0] ^= 0x20
    target.write_bytes(bytes(flipped))
    assert len(bytes(flipped)) == len(content)
    assert pack_pin.tree_digest(pack) != before, "the digest held while the content moved"


# --- the tree ---------------------------------------------------------------

def test_a_changed_file_breaks_the_pin(pack):
    (pack / "tool.py").write_text("print('tampered')\n")
    problems = pack_pin.verify_pin(pack)
    assert any("not the pinned pack" in p for p in problems)


def test_an_added_file_breaks_the_pin(pack):
    (pack / "extra.py").write_text("x = 1\n")
    _git(pack, "add", "extra.py")
    assert pack_pin.verify_pin(pack)


def test_a_rename_breaks_the_pin(pack):
    """Paths are hashed with contents; a digest over contents alone would call
    two different trees identical."""
    _git(pack, "mv", "tool.py", "renamed.py")
    assert pack_pin.verify_pin(pack)


# --- falsification: every case the RP2.1.0 verifier accepted ----------------

def test_an_abbreviated_revision_is_refused(pack):
    """`startswith` accepted a seven-character prefix — and a one-character one.

    An abbreviation is not a weaker pin, it is a different claim: it names a set
    of revisions, and an immutable release is one revision.
    """
    head = _head(pack)
    for abbreviated in (head[:7], head[:12], head[:1], "   ", ""):
        problems = pack_pin.verify_pin(pack, expect_sha=abbreviated)
        assert any("full 40-character" in p for p in problems), f"{abbreviated!r} was accepted"


def test_the_exact_revision_is_compared_not_merely_prefixed(pack):
    head = _head(pack)
    wrong = ("0" * 39) + "1"
    assert any("pinned revision" in p for p in pack_pin.verify_pin(pack, expect_sha=wrong))
    assert pack_pin.verify_pin(pack, expect_sha=head.upper()) == []


def test_a_manifest_version_diverging_from_the_VERSION_file_is_refused(pack):
    """VERSION is the single machine-readable authority; the manifest restates it.

    Nothing compared them, so the manifest could claim any version at all and a
    consumer pinning that claimed version got `pack pin verified`.
    """
    _write_manifest(pack, version="9.9.9")
    problems = pack_pin.verify_pin(pack, expect_version="9.9.9")
    assert any("VERSION is the authority" in p for p in problems)


def test_an_untracked_non_ignored_file_is_refused(pack):
    """A pinned release is a claim about a directory, not only about an index."""
    (pack / "SMUGGLED.py").write_text("import os\n")
    problems = pack_pin.verify_pin(pack)
    assert any("untracked non-ignored" in p for p in problems)
    assert any("SMUGGLED.py" in p for p in problems)


def test_an_ignored_file_is_not_reported(pack):
    """The check is about unreviewed material, not about a clean desk."""
    (pack / "debug.log").write_text("noise\n")
    assert pack_pin.verify_pin(pack) == []


def test_the_digest_frames_the_path_content_boundary(pack, tmp_path):
    """Unframed, path `ab` + content `c` hashes identically to `a` + `bc`.

    Two different trees, one digest. Demonstrated on real trees rather than
    asserted about the framing, because the framing is the implementation and
    the property is what matters.
    """
    def build(name, path, content):
        root = tmp_path / name
        root.mkdir()
        _git(root, "init", "--quiet", "--initial-branch", "main")
        _git(root, "config", "user.name", "H")
        _git(root, "config", "user.email", "h@example.invalid")
        _git(root, "config", "commit.gpgsign", "false")
        (root / path).write_text(content)
        _git(root, "add", path)
        _git(root, "commit", "--quiet", "-m", "x")
        return pack_pin.tree_digest(root)[0]

    assert build("left", "ab", "c") != build("right", "a", "bc")


def test_a_tracked_path_containing_a_space_is_enumerated_as_one_path(pack):
    """`git ls-files` output was split on whitespace, so `a file.md` became two
    entries naming nothing, and the digest raised instead of digesting."""
    (pack / "a file.md").write_text("x\n")
    _git(pack, "add", "a file.md")
    _git(pack, "commit", "--quiet", "-m", "spaced")

    assert "a file.md" in pack_pin.tracked_files(pack)
    assert "a" not in pack_pin.tracked_files(pack)
    digest, count = pack_pin.tree_digest(pack)  # must not raise
    assert count == len(pack_pin.tracked_files(pack))


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"gate_record": "docs/DOES-NOT-EXIST.md"}, "does not name a file"),
        ({"state": "SHIPPED"}, "is not one of"),
        ({"digest_excludes": "nothing"}, "digest_excludes"),
        ({"digest_algorithm": "sha256"}, "digest_algorithm"),
        ({"tree_digest_sha256": "short"}, "64-character"),
        ({pack_pin.DIGEST_COUNT_KEY: "many"}, "not a count"),
        ({"pack": ""}, "does not name the pack"),
    ],
)
def test_altered_manifest_metadata_is_refused(pack, overrides, expected):
    """The manifest is excluded from the digest that protects the rest of the
    tree. That leaves its own fields unguarded unless something checks them —
    and nothing did, so a fabricated test count and a gate record naming a file
    that does not exist both verified.
    """
    _write_manifest(pack, **overrides)
    problems = pack_pin.verify_pin(pack)
    assert problems, f"{overrides!r} was accepted"
    if expected:
        assert any(expected in p for p in problems)


def test_a_malformed_test_count_is_refused(pack):
    for bad in ({"passed": 0}, {"passed": -1}, {"passed": "many"}, {}, "none"):
        _write_manifest(pack, tests=bad)
        assert any(
            "not a count of passing tests" in p for p in pack_pin.verify_pin(pack)
        ), f"{bad!r} was accepted"


def test_a_plausible_but_untrue_test_count_is_not_this_tool_s_domain(pack):
    """Deliberate boundary, stated so it is not mistaken for an oversight.

    `pack_pin` checks that manifest metadata is well-*formed*; it does not run
    the suite, so it cannot tell 175 from 99,999. Whether the recorded count is
    *true* is checked against real collection by
    `test_release_integrity.py`, which is the component that does the work —
    `oracle-discipline.md` on provenance being reported by the executing
    component. Recording the split here keeps a reader from believing this tool
    covers it.
    """
    _write_manifest(pack, tests={"passed": 99999})
    _commit_manifest(pack, "an untrue but well-formed count")
    assert pack_pin.verify_pin(pack) == []


def test_a_pinned_digest_that_cannot_discriminate_is_refused(pack):
    for useless in ("", "   ", "abc", "0" * 63):
        problems = pack_pin.verify_pin(pack, expect_digest=useless)
        assert any("not a 64-character" in p for p in problems), f"{useless!r} was accepted"


def test_a_wrong_pinned_digest_is_reported(pack):
    problems = pack_pin.verify_pin(pack, expect_digest="0" * 64)
    assert any("checkout digests to" in p for p in problems)


def test_a_wrong_pinned_state_is_reported(pack):
    problems = pack_pin.verify_pin(pack, expect_state="QUALIFIED_AND_FROZEN")
    assert problems == []
    _write_manifest(pack, state="IN_PROGRESS")
    problems = pack_pin.verify_pin(pack, expect_state="QUALIFIED_AND_FROZEN")
    assert any("pinned state" in p for p in problems)


# --- fails closed ------------------------------------------------------------

def test_a_wrong_pinned_version_is_reported(pack):
    problems = pack_pin.verify_pin(pack, expect_version="2.0.0")
    assert any("pinned version" in p for p in problems)


def test_an_unreadable_manifest_is_a_failure_not_an_absence_of_findings(tmp_path):
    problems = pack_pin.verify_pin(tmp_path)
    assert problems
    assert "could not be read" in problems[0]


def test_a_manifest_that_is_not_an_object_is_a_failure(pack):
    (pack / pack_pin.MANIFEST_NAME).write_text("[]\n")
    assert any("not a JSON object" in p for p in pack_pin.verify_pin(pack))


def test_a_tracked_file_missing_from_the_worktree_is_a_failure(pack):
    """Fails closed on the digest, before any later check gets a chance to
    report the tree as fine."""
    (pack / "VERSION").unlink()
    problems = pack_pin.verify_pin(pack)
    assert any("could not be digested" in p for p in problems)


def test_a_checkout_with_no_VERSION_authority_at_all_is_a_failure(tmp_path):
    """The version authority is a file, so its absence is a finding.

    Reachable without deleting a tracked path: a checkout where `VERSION` was
    never committed digests cleanly and has nothing to compare the manifest's
    restated version against.
    """
    root = tmp_path / "no-version"
    root.mkdir()
    _git(root, "init", "--quiet", "--initial-branch", "main")
    _git(root, "config", "user.name", "H")
    _git(root, "config", "user.email", "h@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "GATE.md").write_text("# gate\n")
    _git(root, "add", "GATE.md")
    _git(root, "commit", "--quiet", "-m", "x")

    digest, count = pack_pin.tree_digest(root)
    (root / pack_pin.MANIFEST_NAME).write_text(json.dumps({
        "pack": "test-pack", "version": "2.1.1", "state": "QUALIFIED_AND_FROZEN",
        "tracked_files": count, "tree_digest_sha256": digest,
        "digest_excludes": pack_pin.MANIFEST_NAME,
        "digest_algorithm": pack_pin.DIGEST_ALGORITHM, "gate_record": "GATE.md",
    }, indent=2) + "\n")

    problems = pack_pin.verify_pin(root)
    assert any("VERSION could not be read" in p for p in problems)


# --- the digest-covered file count, under either spelling --------------------

def test_a_manifest_written_by_2_1_1_still_verifies(pack):
    """The rename must not break the case it exists to serve: a 2.2.0 verifier
    reading an OLDER pinned root during migration."""
    manifest = _write_manifest(pack)
    count = manifest.pop(pack_pin.DIGEST_COUNT_KEY)
    manifest[pack_pin.LEGACY_COUNT_KEY] = count
    (pack / pack_pin.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    _commit_manifest(pack, "a 2.1.1-shaped manifest")

    assert pack_pin.verify_pin(pack) == []
    assert pack_pin.manifest_file_count(manifest) == (count, [])


def test_a_manifest_that_records_two_different_counts_is_refused(pack):
    """Not resolved by preference. A manifest that answers the same question
    twice, in two ways, has no answer — and silently preferring one spelling
    would let a stale legacy count sit unread beside a fresh one."""
    manifest = _write_manifest(pack)
    manifest[pack_pin.LEGACY_COUNT_KEY] = manifest[pack_pin.DIGEST_COUNT_KEY] + 1
    (pack / pack_pin.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")

    problems = pack_pin.verify_pin(pack)
    assert any("cannot record two file counts" in problem for problem in problems), problems


def test_a_manifest_that_records_no_count_at_all_is_refused(pack):
    manifest = _write_manifest(pack)
    manifest.pop(pack_pin.DIGEST_COUNT_KEY)
    (pack / pack_pin.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")

    problems = pack_pin.verify_pin(pack)
    assert any("neither" in problem for problem in problems), problems


def test_the_agreeing_counts_are_accepted_and_a_wrong_one_is_not(pack):
    """Both spellings, agreeing, is the shape a mid-migration manifest has."""
    manifest = _write_manifest(pack)
    manifest[pack_pin.LEGACY_COUNT_KEY] = manifest[pack_pin.DIGEST_COUNT_KEY]
    (pack / pack_pin.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    _commit_manifest(pack, "both spellings, agreeing")
    assert pack_pin.verify_pin(pack) == []

    manifest[pack_pin.DIGEST_COUNT_KEY] = manifest[pack_pin.LEGACY_COUNT_KEY] = 999
    (pack / pack_pin.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    _commit_manifest(pack, "both spellings, wrong")
    problems = pack_pin.verify_pin(pack)
    assert any("the digest covers" in problem for problem in problems), problems


def test_writing_the_digest_leaves_exactly_one_spelling_behind(pack):
    """A rewrite that left the legacy key in place would produce the disagreeing
    manifest the reader above refuses, the moment the file count changed."""
    manifest = _write_manifest(pack)
    manifest[pack_pin.LEGACY_COUNT_KEY] = 1
    (pack / pack_pin.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")

    assert pack_pin._cli([str(pack), "--write"]) == 0
    rewritten = json.loads((pack / pack_pin.MANIFEST_NAME).read_text())
    assert pack_pin.LEGACY_COUNT_KEY not in rewritten
    assert rewritten[pack_pin.DIGEST_COUNT_KEY] == pack_pin.tree_digest(pack)[1]


def test_a_copy_that_is_not_a_checkout_cannot_be_decided_rather_than_failed(tmp_path):
    """**Found by unpacking the release into a clean room and adopting it.**

    The digest is defined over the TRACKED tree, so outside a checkout there is
    no way to know which files belong to the release. A copy delivered as an
    archive, or vendored into another repository, reported `PIN DOES NOT
    VERIFY` — the same sentence a tampered pack reports — and a consumer was
    left choosing between alarm and learning to ignore the check.

    *Cannot be decided here* and *decided, and wrong* are different answers.
    """
    root = Path(__file__).resolve().parents[2]
    archive = tmp_path / "vendored"
    archive.mkdir()
    tar = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=root,
                         capture_output=True, timeout=600)
    assert tar.returncode == 0
    subprocess.run(["tar", "-x", "-f", "-", "-C", str(archive)], input=tar.stdout, check=True,
                   timeout=600)
    assert not (archive / ".git").exists()

    manifest = json.loads((archive / "PACK_MANIFEST.json").read_text(encoding="utf-8"))
    problems = pack_pin.verify_pin(
        archive, expect_version=manifest["version"],
        expect_digest=manifest["tree_digest_sha256"], expect_state=manifest["state"])
    assert problems, "an unverifiable copy reported nothing at all"
    assert any(p.startswith(pack_pin.UNESTABLISHED) for p in problems), problems
    assert not any("is not the pinned pack" in p for p in problems), (
        "a copy that could not be checked was reported as one that failed the check")


def test_a_real_mismatch_is_still_reported_as_one(tmp_path):
    """The other half. If *could not be decided* swallowed *decided and wrong*,
    the repair above would have turned the identity check off."""
    root = Path(__file__).resolve().parents[2]
    problems = pack_pin.verify_pin(root, expect_version="2.3.0",
                                   expect_digest="0" * 64, expect_state="IN_PROGRESS")
    assert any("does not match" in p or "pinned digest" in p for p in problems), problems
    assert not any(p.startswith(pack_pin.UNESTABLISHED) for p in problems), problems


def test_the_projection_shows_an_undecidable_pin_as_unknown_and_not_as_a_defect(tmp_path):
    """A view that renders *could not be checked* in the colour of *checked and
    wrong* has decided something the checker declined to."""
    import projection

    project = tmp_path / "project"
    project.mkdir()
    (project / "PROJECT.yaml").write_text(
        'project:\n  name: "p"\n  publication_intent: "internal"\n'
        'pack:\n  root_path: "%s"\n  version_adopted: "2.3.0"\n'
        '  sha_adopted: "%s"\n  tree_digest_sha256: "%s"\n  state_adopted: "IN_PROGRESS"\n'
        '  adopted_at: "2026-09-04"\n'
        '  adoption_boundary: "at a capability boundary"\nadapters: []\n'
        % (tmp_path / "not-a-checkout", "a" * 40, "b" * 64))
    (tmp_path / "not-a-checkout").mkdir()
    (tmp_path / "not-a-checkout" / "PACK_MANIFEST.json").write_text(json.dumps({
        "version": "2.3.0", "state": "IN_PROGRESS", "tree_digest_sha256": "b" * 64,
        "digest_algorithm": "sha256-framed-v1", "digest_file_count": 1,
        "tests": {"passed": 1}}))
    view = projection.project(project)
    pin = next(l for panel in view.panels for l in panel.rows() if l.label == "pin")
    assert pin.tone == projection.Tone.UNKNOWN, f"{pin.tone}: {pin.text[:90]}"
    assert "PIN DOES NOT VERIFY" not in view.render()


# --- the 2.3.0 linked-worktree incident, as an executable property ---------------


def _repo_with_a_linked_worktree(tmp_path):
    """A main checkout and a linked worktree of it, both at one revision."""
    main = tmp_path / "main"
    main.mkdir()

    def git(*args, cwd=main, check=True):
        result = subprocess.run(["git", "-C", str(cwd), *args],
                                capture_output=True, text=True, timeout=120)
        assert not (check and result.returncode), f"git {args}: {result.stderr}"
        return result

    git("init", "-q", "--initial-branch", "main")
    git("config", "user.name", "Ordinary Human")
    git("config", "user.email", "human@example.invalid")
    git("config", "commit.gpgsign", "false")
    (main / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    (main / "PACK_MANIFEST.json").write_text(json.dumps({
        "pack": "p", "version": "9.9.9", "state": "QUALIFIED_AND_FROZEN",
        "tree_digest_sha256": "", "digest_excludes": "PACK_MANIFEST.json",
        "digest_algorithm": "sha256-framed-v1"}), encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    digest, count = pack_pin.tree_digest(main)
    manifest = json.loads((main / "PACK_MANIFEST.json").read_text(encoding="utf-8"))
    manifest.update({"tree_digest_sha256": digest, "digest_file_count": count})
    (main / "PACK_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "record the digest")
    sha = git("rev-parse", "HEAD").stdout.strip()
    linked = tmp_path / "linked"
    git("worktree", "add", "-q", "--detach", str(linked), sha)
    return main, linked, sha, digest, git


def test_a_release_root_that_is_a_linked_worktree_is_reported_as_one(tmp_path):
    """THE 2.3.0 INCIDENT. The pack's own evolution workspaces are linked
    worktrees, one was a pinned root, and it verified only because it happened
    to be sitting on its pinned revision. That was recorded as prose in two
    manifests and detected by nothing."""
    main, linked, _sha, _digest, _git = _repo_with_a_linked_worktree(tmp_path)

    kind, why = pack_pin.root_kind(linked)
    assert kind == "linked-worktree", f"a linked worktree read as {kind!r}: {why}"
    assert "immutable" in why and "move" in why, why

    assert pack_pin.root_kind(main)[0] == "checkout", (
        "an ordinary checkout was reported as a linked worktree, which would make the "
        "report noise and get it ignored")


def test_a_directory_that_is_not_a_checkout_is_named_as_a_copy(tmp_path):
    """A vendored or unpacked release. Its digest still answers; its revision cannot."""
    plain = tmp_path / "unpacked"
    plain.mkdir()
    kind, why = pack_pin.root_kind(plain)
    assert kind == "not-a-checkout", kind
    assert "copy" in why


def test_the_hazard_is_real_and_the_pin_fails_loudly_rather_than_quietly(tmp_path):
    """What the report is warning about, executed.

    The pin does NOT silently accept a moved root — it reports four separate
    problems — so the cost of the layout is a project blocked for a reason it
    did not cause, which is exactly what a note at adoption time prevents.
    """
    main, linked, sha, digest, git = _repo_with_a_linked_worktree(tmp_path)
    assert pack_pin.verify_pin(linked, expect_version="9.9.9", expect_sha=sha,
                               expect_digest=digest,
                               expect_state="QUALIFIED_AND_FROZEN") == []

    (main / "VERSION").write_text("9.9.10\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "ordinary development, by somebody else")
    moved = git("rev-parse", "HEAD").stdout.strip()
    git("checkout", "-q", "--detach", moved, cwd=linked)

    problems = pack_pin.verify_pin(linked, expect_version="9.9.9", expect_sha=sha,
                                   expect_digest=digest,
                                   expect_state="QUALIFIED_AND_FROZEN")
    assert problems, (
        "a release root moved out from under its pin still verified; the whole hazard is "
        "that this root is movable, and a movable root that verifies anyway is worse")
    assert any("digest" in problem for problem in problems), problems


# --- RP2.4.1 R4/R5/R6: the pin's own integrity boundary ----------------------

def _hook(tmp_path, marker):
    """A program Git would run, which records that it ran."""
    script = tmp_path / "hook.sh"
    script.write_text(f"#!/bin/sh\necho ran >> {marker}\nexit 0\n")
    script.chmod(0o755)
    return script


def test_a_repository_local_program_valued_config_is_not_executed(pack, tmp_path):
    """R4. Verifying a pin must not run a program the verified repository names.

    `gitread` neutralises `core.fsmonitor` for every invocation it makes, and
    said so; `pack_pin` called Git directly and so was a call site the promise
    never reached. Verification is the act that establishes a checkout can be
    trusted, and it ran the checkout's own program while reporting `verified`.
    """
    marker = tmp_path / "ran"
    _git(pack, "config", "core.fsmonitor", str(_hook(tmp_path, marker)))
    pack_pin.verify_pin(pack)
    assert not marker.exists(), "verifying the pin executed a program the repository named"


def test_a_global_program_valued_config_is_not_executed(pack, tmp_path, monkeypatch):
    """R4, and the reachable half: no write to the release root is needed."""
    marker = tmp_path / "ran-global"
    config = tmp_path / "gitconfig"
    config.write_text(f"[core]\n\tfsmonitor = {_hook(tmp_path, marker)}\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    pack_pin.verify_pin(pack)
    assert not marker.exists(), "a global configuration reached the pin verifier"


def test_a_program_valued_config_does_not_break_an_ordinary_verification(pack, tmp_path):
    """The repair must refuse execution, not refuse the answer."""
    marker = tmp_path / "ran-ordinary"
    _git(pack, "config", "core.fsmonitor", str(_hook(tmp_path, marker)))
    assert pack_pin.verify_pin(pack) == []


def test_a_manifest_edited_away_from_its_commit_is_reported(pack):
    """R5. The one file the digest cannot cover is the one nothing compared.

    `PACK_MANIFEST.json` is excluded from its own digest of necessity, and
    2.4.0 compared it to nothing else — so a root could claim any test
    population and any set of known limitations and still verify.
    """
    manifest = pack / pack_pin.MANIFEST_NAME
    claimed = json.loads(manifest.read_text())
    claimed["tests"] = {"command": "python3 -m pytest", "passed": 999999}
    manifest.write_text(json.dumps(claimed, indent=2))
    problems = pack_pin.verify_pin(pack)
    assert problems, "an edited manifest verified"
    assert any("manifest" in problem.lower() for problem in problems)


def test_an_unedited_manifest_is_not_reported(pack):
    """R5's positive control: the ordinary frozen release still verifies."""
    assert pack_pin.verify_pin(pack) == []


def test_a_global_exclude_cannot_hide_untracked_material(pack, tmp_path, monkeypatch):
    """R6. An operator's machine-level ignore file cannot hide release material.

    **What this establishes, precisely:** the global excludes file does not
    reach the enumeration. It is held by the hardened Git boundary, which points
    the global configuration at nothing, rather than by the enumeration itself —
    so restoring `--exclude-standard` leaves this test passing, which an
    independent reader demonstrated. Recorded rather than left implied: the
    enumeration's own rule is discriminated by its two siblings below.
    """
    excludes = tmp_path / "globalignore"
    excludes.write_text("*.evil\n")
    config = tmp_path / "gitconfig"
    config.write_text(f"[core]\n\texcludesFile = {excludes}\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    (pack / "unreviewed.evil").write_text("payload\n")
    problems = pack_pin.verify_pin(pack)
    assert any("unreviewed.evil" in problem for problem in problems), problems


def test_a_repository_local_info_exclude_cannot_hide_untracked_material(pack):
    """R6, the second half: `.git/info/exclude` is not the release's rule either."""
    (pack / ".git" / "info").mkdir(parents=True, exist_ok=True)
    (pack / ".git" / "info" / "exclude").write_text("hidden.py\n")
    (pack / "hidden.py").write_text("payload\n")
    problems = pack_pin.verify_pin(pack)
    assert any("hidden.py" in problem for problem in problems), problems


def test_the_releases_own_ignore_rules_are_still_honoured(pack):
    """R6's positive control: the pack's own `.gitignore` still governs."""
    (pack / "build.log").write_text("noise\n")
    assert pack_pin.verify_pin(pack) == []


def test_an_untracked_ignore_file_cannot_exempt_itself_or_anything_else(pack):
    """The enumeration's own rule, and the sharpest test of it.

    `--exclude-per-directory=.gitignore` reads the `.gitignore` files present in
    the WORKING TREE, tracked or not. So an untracked `unreviewed/.gitignore`
    containing `*` hid itself and an unreviewed module while the pin verified —
    the first repair's comment claimed it read only tracked rules and was
    simply wrong. The rules now come from the files the release TRACKS.
    """
    unreviewed = pack / "unreviewed"
    unreviewed.mkdir()
    (unreviewed / ".gitignore").write_text("*\n")
    (unreviewed / "payload.py").write_text("print('unreviewed')\n")
    strays = pack_pin.untracked_files(pack)
    assert "unreviewed/payload.py" in strays, strays
    assert "unreviewed/.gitignore" in strays, strays
    problems = pack_pin.verify_pin(pack)
    assert any("untracked" in problem for problem in problems), problems


def test_a_cache_directory_the_release_ignores_is_still_ignored(pack):
    """The other direction, and the reason the rule is not *refuse on sight*.

    `pytest` writes `.pytest_cache/.gitignore` into any root the suite has run
    in. An implementation that refused wholesale whenever an untracked ignore
    file existed reported the entire cache of every release that had ever been
    tested — measured against the frozen 2.4.0 root before it was rejected.
    """
    (pack / ".gitignore").write_text("*.log\n.pytest_cache/\n")
    _git(pack, "add", ".gitignore")
    _git(pack, "commit", "--quiet", "-m", "ignore the cache")
    cache = pack / ".pytest_cache"
    cache.mkdir()
    (cache / ".gitignore").write_text("*\n")
    (cache / "CACHEDIR.TAG").write_text("Signature: 8a477f597d28d172789f06886806bc55\n")
    assert pack_pin.untracked_files(pack) == []


# --- the enumeration's rules are the release's, and the MATCHING is Git's -----

@pytest.mark.parametrize("rule,present,expected_reported", [
    ("/payload.py", ("payload.py", "nested/payload.py"), ("nested/payload.py",)),
    ("payload.py", ("payload.py", "nested/payload.py"), ()),
    ("*.py", ("keep.py",), ()),
    ("sub/", ("sub/a.txt",), ()),
    ("*.py\n!keep.py", ("keep.py", "other.py"), ("keep.py",)),
    ("*.py\n!/keep.py", ("keep.py", "sub/keep.py"), ("keep.py",)),
    (" payload.py", ("payload.py",), ("payload.py",)),
    ("payload.py\t", ("payload.py",), ("payload.py",)),
])
def test_the_enumeration_agrees_with_real_git_about_the_release_rules(
        tmp_path, rule, present, expected_reported):
    """A differential against `git ls-files --others --exclude-standard`.

    The enumeration once matched the release's rules in Python and was wrong in
    BOTH directions — an anchored root rule silently matched at every depth and
    hid material, a nested rule lost its bare-name recursion, and whitespace Git
    treats as significant was normalised away. An independent reader proved it
    against Git. Git is the only correct reader of a `.gitignore`, so these
    cases are asked of Git and of this module and the answers must agree.
    """
    root = tmp_path / "release"
    root.mkdir()
    _git(root, "init", "--quiet", "--initial-branch", "main")
    for key, value in (("user.name", "T"), ("user.email", "t@e.invalid"),
                       ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    (root / ".gitignore").write_text(rule + "\n")
    (root / "VERSION").write_text("1.0.0\n")
    _git(root, "add", ".gitignore", "VERSION")
    _git(root, "commit", "--quiet", "-m", "rules")
    for relative in present:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n")

    git_says = sorted(entry for entry in subprocess.run(
        ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True, check=True).stdout.split() if entry)
    assert git_says == sorted(expected_reported), (
        f"the fixture does not mean what it says: git reports {git_says}")
    assert pack_pin.untracked_files(root) == git_says


def test_a_nested_tracked_ignore_declaration_is_refused_not_approximated(pack):
    """`--exclude-from` is root-relative, so a nested declaration's per-directory
    meaning cannot be expressed. Refused, with the reason, rather than guessed."""
    nested = pack / "sub"
    nested.mkdir()
    (nested / ".gitignore").write_text("*.log\n")
    _git(pack, "add", "sub/.gitignore")
    _git(pack, "commit", "--quiet", "-m", "a nested declaration")
    with pytest.raises(ValueError, match="nested ignore declarations"):
        pack_pin.untracked_files(pack)
    problems = pack_pin.verify_pin(pack)
    assert any("nested ignore declarations" in problem for problem in problems), problems


@pytest.mark.parametrize("ignore_name", [
    ".gitignore",
    ".gitignore-not-tracked-by-this-release",
    ".zz-anything-at-all",
])
def test_no_untracked_ignore_file_anywhere_can_hide_material(pack, ignore_name):
    """An ignore file nobody reviewed has no say, WHATEVER it is called.

    Two repairs failed here for the same reason. `--exclude-per-directory` reads
    working-tree ignore files, so an untracked `.gitignore` hid a payload; and
    pointing the option at a name the tree "does not contain" was that hole with
    a different filename, because the option makes Git look for that name in
    EVERY directory it walks, and a root-only existence check cannot see a
    nested one. No chosen name is safe: the name is in the source. So there is
    no per-directory discovery at all, and this asks with the exact name the
    implementation once trusted.
    """
    unreviewed = pack / "unreviewed"
    unreviewed.mkdir()
    (unreviewed / ignore_name).write_text("*\n")
    (unreviewed / "payload.py").write_text("print('unreviewed')\n")
    strays = pack_pin.untracked_files(pack)
    assert f"unreviewed/{ignore_name}" in strays, strays
    assert "unreviewed/payload.py" in strays, strays
    assert any("untracked" in problem for problem in pack_pin.verify_pin(pack))


def test_a_relative_root_with_a_path_component_verifies(pack, monkeypatch):
    """`--exclude-from` is resolved by Git against the directory it is launched
    in, which is the root itself, so a root spelled relatively became
    `root/root/.gitignore` and the enumeration failed — a real release refused
    for the way its path was written."""
    (pack / "build.log").write_text("ignored by the release's own rule\n")
    monkeypatch.chdir(pack.parent)
    assert pack_pin.untracked_files(pack.name) == []
    assert pack_pin.untracked_files(f"./{pack.name}") == []
    assert pack_pin.untracked_files(f"{pack.name}/") == []


def test_the_manifest_comparison_is_over_bytes(pack):
    """Claimed byte-for-byte, and it compared decoded text until a reader said so."""
    manifest = pack / pack_pin.MANIFEST_NAME
    manifest.write_bytes(manifest.read_bytes().replace(b"\n", b"\r\n"))
    assert any("differs from the one committed at HEAD" in problem
               for problem in pack_pin.verify_pin(pack))


def test_a_redirected_working_tree_is_refused_not_answered_about(pack, tmp_path):
    """`core.worktree` points Git at a different directory, and the enumeration
    then described that one: an unreviewed module sat in the named release root
    while `pack pin verified` printed. It is a path rather than a program, so the
    hardened reader's program-valued neutralisation does not cover it. Asked
    rather than neutralised, because a linked worktree sets it legitimately."""
    (pack / "unreviewed_module.py").write_text("print('unreviewed')\n")
    assert "unreviewed_module.py" in pack_pin.untracked_files(pack)
    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    _git(pack, "config", "core.worktree", str(elsewhere))
    # REFUSED BY THE SHARED READER NOW, not by this module. The local copy this
    # function grew is gone: binding the answer to the directory asked about is
    # one question, and `gitread` answers it for all twelve callers rather than
    # for whichever ones remembered.
    with pytest.raises(Exception, match="different directory"):
        pack_pin.untracked_files(pack)
    problems = pack_pin.verify_pin(pack)
    assert any("different directory" in problem for problem in problems), problems


def test_an_archive_inside_another_checkout_cannot_be_decided(pack, tmp_path):
    """O8. A release unpacked into an ignored vendor directory inside another
    project's checkout is not a checkout of its own. Git discovered the PARENT
    repository and returned zero tracked paths scoped to the archive, so the pin
    digested an empty tree and said confidently that a byte-identical release
    was not the pinned pack. An adopting project meets this by vendoring the
    release, with no tampering at all."""
    outer = tmp_path / "adopter"
    outer.mkdir()
    _git(outer, "init", "--quiet", "--initial-branch", "main")
    for key, value in (("user.name", "T"), ("user.email", "t@e.invalid"),
                       ("commit.gpgsign", "false")):
        _git(outer, "config", key, value)
    (outer / "README.md").write_text("the adopting project\n")
    (outer / ".gitignore").write_text("vendor/\n")
    _git(outer, "add", "-A")
    _git(outer, "commit", "--quiet", "-m", "the adopter's own repository")

    vendored = outer / "vendor"
    vendored.mkdir()
    for entry in sorted(pack.iterdir()):
        if entry.name == ".git":
            continue
        target = vendored / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target)
        else:
            shutil.copy2(entry, target)

    problems = pack_pin.verify_pin(vendored)
    assert problems, "a non-checkout inside another repository verified"
    assert not any("is not the pinned pack" in problem for problem in problems), problems
    assert not any("covers 0 files" in problem for problem in problems), problems
    assert any(problem.startswith(pack_pin.UNESTABLISHED) or "different directory" in problem
               for problem in problems), problems


def test_a_checkout_whose_head_does_not_resolve_reports_rather_than_raises(pack):
    """A refusal that is not an integrity finding must keep the shape its callers
    already handle.

    The translation that preserves an integrity refusal's words was written to
    test the module an exception came from, which caught `GitRefusal` too — so an
    unresolvable HEAD, previously reported as `HEAD could not be read, so the
    revision is unverified`, raised out of `verify_pin` as an uncaught
    `ValueError`. `run_cli` promises refusals are reported rather than raised,
    and `verify_pin` promises every check it cannot perform is a finding. Both
    were falsified by the repair that preserved the reason.
    """
    _git(pack, "symbolic-ref", "HEAD", "refs/heads/gone")
    problems = pack_pin.verify_pin(pack, expect_version="2.1.1",
                                   expect_sha="0" * 40, expect_state="QUALIFIED_AND_FROZEN")
    assert problems, "an unresolvable HEAD produced no finding at all"
    assert any("HEAD could not be read" in problem for problem in problems), problems


def test_the_bytes_reader_also_keeps_an_integrity_refusal_readable(pack, tmp_path):
    """`_git_bytes` carries the same translation as `_git`, and nothing pinned it.

    Reverting only the bytes helper left the unresolved-HEAD test green, because
    that test reaches its finding through the manifest branch either way. So the
    manifest comparison is driven here against a root the reader refuses, where
    the reason is the whole point of the report.
    """
    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    _git(pack, "config", "core.worktree", str(elsewhere))
    with pytest.raises(ValueError, match="different directory"):
        pack_pin._git_bytes(pack, "show", f"HEAD:{pack_pin.MANIFEST_NAME}")
    problems = pack_pin.verify_pin(pack)
    assert any("different directory" in problem for problem in problems), problems
