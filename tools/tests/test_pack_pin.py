"""A pin is worth what a consumer can check about it.

The motivating defect is in this pack's own first manifest: the digest was
computed over 81 tracked files and the manifest then became the 82nd, so
recomputing it produced a different value forever after. Nothing failed and no
test caught it, because the manifest was written by different code than the code
that would verify it — the exact shape `oracle-discipline.md` names when it says
provenance must be reported by the component that did the work.
"""

import json
import subprocess

import pytest

import pack_pin


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)


@pytest.fixture
def pack(tmp_path):
    root = tmp_path / "pack"
    root.mkdir()
    _git(root, "init", "--quiet", "--initial-branch", "main")
    _git(root, "config", "user.name", "Ordinary Human")
    _git(root, "config", "user.email", "human@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "VERSION").write_text("2.1.0\n")
    (root / "tool.py").write_text("print('hi')\n")
    _git(root, "add", "VERSION", "tool.py")
    _git(root, "commit", "--quiet", "-m", "pack")

    digest, count = pack_pin.tree_digest(root)
    (root / pack_pin.MANIFEST_NAME).write_text(json.dumps({
        "version": "2.1.0", "tracked_files": count,
        "tree_digest_sha256": digest, "digest_excludes": pack_pin.MANIFEST_NAME,
    }, indent=2) + "\n")
    _git(root, "add", pack_pin.MANIFEST_NAME)
    _git(root, "commit", "--quiet", "-m", "manifest")
    return root


def test_a_manifest_verifies_after_being_committed_alongside_the_tree(pack):
    """The self-reference case, which the first real manifest failed.

    Committing the manifest changes the tracked file set. If the digest covered
    the manifest, this would fail — permanently, and only for someone who
    actually tried to check it.
    """
    assert pack_pin.verify_pin(pack) == []


def test_a_changed_file_breaks_the_pin(pack):
    (pack / "tool.py").write_text("print('tampered')\n")
    problems = pack_pin.verify_pin(pack)
    assert any("not the pinned pack" in p for p in problems)


def test_an_added_file_breaks_the_pin(pack):
    (pack / "extra.py").write_text("x = 1\n")
    _git(pack, "add", "extra.py")
    problems = pack_pin.verify_pin(pack)
    assert problems


def test_a_rename_breaks_the_pin(pack):
    """Paths are hashed with contents; a digest over contents alone would call
    two different trees identical."""
    _git(pack, "mv", "tool.py", "renamed.py")
    assert pack_pin.verify_pin(pack)


def test_a_wrong_pinned_version_is_reported(pack):
    problems = pack_pin.verify_pin(pack, expect_version="2.0.0")
    assert any("pinned version" in p for p in problems)


def test_a_wrong_pinned_revision_is_reported(pack):
    problems = pack_pin.verify_pin(pack, expect_sha="0" * 40)
    assert any("pinned revision" in p for p in problems)


def test_the_right_revision_verifies(pack):
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(pack), capture_output=True, text=True, check=True
    ).stdout.strip()
    assert pack_pin.verify_pin(pack, expect_version="2.1.0", expect_sha=head) == []


def test_an_unreadable_manifest_is_a_failure_not_an_absence_of_findings(tmp_path):
    problems = pack_pin.verify_pin(tmp_path)
    assert problems
    assert "could not be read" in problems[0]
