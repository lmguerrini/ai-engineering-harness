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
import subprocess

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
        "tracked_files": count,
        "tree_digest_sha256": digest,
        "digest_excludes": pack_pin.MANIFEST_NAME,
        "digest_algorithm": pack_pin.DIGEST_ALGORITHM,
        "gate_record": "GATE.md",
        "tests": {"passed": 3},
    }
    manifest.update(overrides)
    (root / pack_pin.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


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


def test_the_digest_is_reproducible_across_calls(pack):
    assert pack_pin.tree_digest(pack) == pack_pin.tree_digest(pack)


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
        ({"tracked_files": "many"}, "not a count"),
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
