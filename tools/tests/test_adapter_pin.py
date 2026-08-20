"""Adapter pinning, and the reproduction that made it necessary.

The claim under test is narrow and worth stating exactly: *a project cannot
dispatch through an executable adapter it did not qualify, without something
saying so.* Every test here tries to obtain a clean report from an installation
that is not the declared one.

The first test is the live defect. The installed reviewer adapter declared
`isolation: worktree` while the pinned reviewer contract forbids a reviewer from
creating a ref, a branch or a worktree — and the pack's own publication gate
refuses exactly the ref that mode creates. Nothing failed, because nothing
looked at adapters at all.
"""

import pytest

from adapter_pin import (
    AdapterDeclaration,
    declarations_from,
    file_digest,
    verify,
    verify_contract,
)
from errors import IntegrityError

AUDITOR = """---
name: capability-auditor
model: opus
tools: Read, Grep
---

The auditor never creates a ref, a branch or a worktree.
"""

#: The same file with the isolation mode the reviewer contract forbids. Byte
#: difference, therefore digest difference — which is the whole mechanism.
AUDITOR_WITH_WORKTREE = AUDITOR.replace("model: opus", "model: opus\nisolation: worktree")


@pytest.fixture
def home(tmp_path):
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    return tmp_path


def _install(home, text, name="capability-auditor.md"):
    path = home / ".claude" / "agents" / name
    path.write_text(text)
    return path


def _declare(digest, **overrides):
    fields = {
        "id": "capability-auditor",
        "locator": "~/.claude/agents/capability-auditor.md",
        "digest": digest,
        "required": True,
    }
    fields.update(overrides)
    return declarations_from([fields])


def test_the_reviewer_isolation_contradiction_is_caught(home):
    """EC/B2 reproduced: the qualified adapter is replaced by one that declares
    an isolation mode the reviewer contract forbids, and the pin refuses it."""
    qualified = _install(home, AUDITOR)
    declared = _declare(file_digest(qualified))

    assert verify(declared, home=home).clean

    _install(home, AUDITOR_WITH_WORKTREE)
    report = verify(declared, home=home)
    assert not report.clean
    assert "does not match the declared digest" in report.render()


def test_a_matching_adapter_verifies(home):
    path = _install(home, AUDITOR)
    report = verify(_declare(file_digest(path)), home=home)
    assert report.clean
    assert report.verified == ["capability-auditor"]


def test_a_required_adapter_that_is_absent_blocks(home):
    report = verify(_declare("0" * 64), home=home)
    assert not report.clean
    assert "not installed there" in report.render()


def test_an_optional_adapter_may_be_absent(home):
    report = verify(_declare("0" * 64, required=False), home=home)
    assert report.clean
    assert report.findings and not report.findings[0].blocking


def test_optional_governs_absence_only_not_content(home):
    """`required: false` says the workflow can proceed without the adapter. It
    does not say any bytes will do — a present adapter still has to match."""
    _install(home, AUDITOR_WITH_WORKTREE)
    report = verify(_declare("0" * 64, required=False), home=home)
    assert not report.clean


def test_the_declared_name_is_checked_not_inferred_from_the_filename(home):
    """A path is a locator, not an identity."""
    swapped = AUDITOR.replace("name: capability-auditor", "name: something-else")
    path = _install(home, swapped)
    report = verify(_declare(file_digest(path), declares="capability-auditor"), home=home)
    assert not report.clean
    assert "expected 'capability-auditor'" in report.render()


def test_an_unreadable_adapter_is_a_failure_not_an_absence(home):
    """Unreadable is neither "absent" nor "unchanged": nothing was established,
    so it blocks even when the adapter is optional."""
    path = _install(home, AUDITOR)
    declared = _declare(file_digest(path), required=False)
    path.chmod(0o000)
    try:
        report = verify(declared, home=home)
        assert not report.clean
        assert "could not be read" in report.render()
    finally:
        path.chmod(0o644)


def test_a_directory_at_the_locator_is_refused(home):
    (home / ".claude" / "agents" / "capability-auditor.md").mkdir()
    report = verify(_declare("0" * 64), home=home)
    assert not report.clean
    assert "not a regular file" in report.render()


def test_a_symlinked_adapter_verifies_but_is_disclosed(home):
    """The digest is over the bytes read, so integrity holds through a link.
    The locator claim is weaker than it looks, so the report says so."""
    real = home / "elsewhere.md"
    real.write_text(AUDITOR)
    link = home / ".claude" / "agents" / "capability-auditor.md"
    link.symlink_to(real)

    report = verify(_declare(file_digest(real)), home=home)
    assert report.clean
    assert any("symlink" in note for note in report.notes)


# --- the declaration itself -------------------------------------------------


@pytest.mark.parametrize(
    "entry, expected",
    [
        ({"locator": "p", "digest": "0" * 64}, "id is missing"),
        ({"id": "x", "digest": "0" * 64}, "locator is missing"),
        ({"id": "x", "locator": "p"}, "digest is not a 64-character"),
        ({"id": "x", "locator": "p", "digest": "abc"}, "digest is not a 64-character"),
        ({"id": "x", "locator": "p", "digest": "0" * 64, "required": "yes"}, "must be true or false"),
        ({"id": "x", "locator": "p", "digest": "0" * 64, "declares": 7}, "declares must be a string"),
    ],
)
def test_a_malformed_declaration_raises_rather_than_being_skipped(entry, expected):
    with pytest.raises(IntegrityError) as caught:
        declarations_from([entry])
    assert expected in caught.value.cause


def test_an_unknown_field_is_refused():
    """The field that would have carried this defect is exactly the shape of
    field a permissive parser drops on the floor."""
    with pytest.raises(IntegrityError) as caught:
        declarations_from([{"id": "x", "locator": "p", "digest": "0" * 64, "isolation": "worktree"}])
    assert "does not implement" in caught.value.cause


def test_a_duplicate_id_is_refused():
    with pytest.raises(IntegrityError):
        declarations_from(
            [
                {"id": "x", "locator": "a", "digest": "0" * 64},
                {"id": "x", "locator": "b", "digest": "1" * 64},
            ]
        )


def test_a_non_list_adapters_block_is_refused():
    with pytest.raises(IntegrityError):
        declarations_from({"id": "x"})


def test_an_absent_block_is_not_an_empty_one():
    assert declarations_from(None) == ()


def test_verify_contract_refuses_a_contract_that_declares_nothing():
    """"Nobody said" must not be read as "someone said none"."""

    class Contract:
        adapters = None

    with pytest.raises(IntegrityError):
        verify_contract(Contract())


def test_verify_contract_accepts_a_deliberately_empty_declaration():
    class Contract:
        adapters = ()

    assert verify_contract(Contract()).clean


# --- the thing this module must never do ------------------------------------


def test_verification_never_rewrites_the_declaration(home):
    """A verifier that refreshes its own expectation always passes."""
    _install(home, AUDITOR_WITH_WORKTREE)
    declared = _declare("0" * 64)
    verify(declared, home=home)
    verify(declared, home=home)
    assert declared[0].digest == "0" * 64
    assert isinstance(declared[0], AdapterDeclaration)


def test_verification_does_not_touch_the_adapter_on_disk(home):
    path = _install(home, AUDITOR)
    before = path.read_bytes(), path.stat().st_mode
    verify(_declare("0" * 64), home=home)
    assert (path.read_bytes(), path.stat().st_mode) == before
