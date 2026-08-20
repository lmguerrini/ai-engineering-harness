"""Moving between releases: what must be checkable, and what must stay refused.

The releases below are real ones — built as actual git repositories with real
manifests and real digests — because every claim under test is about
verification, and a fixture that stubs the verifier tests nothing.
"""

import json
import subprocess

import pytest

import pack_pin
from pack_migration import (
    UNVERIFIABLE_LEGACY_PIN,
    VERIFIED_PIN,
    Pin,
    ReleaseEntry,
    canonical_root,
    classify_pin,
    migration_gate,
    read_release_index,
    rollback_targets,
    unaccounted_candidates,
    verify_pinned_root,
)


def _build_release(root, version, *, state="QUALIFIED_AND_FROZEN", extra=""):
    """A real, verifiable release root."""
    root.mkdir(parents=True)
    (root / "VERSION").write_text(f"{version}\n")
    (root / "README.md").write_text(f"# Runtime Pack {version}\n{extra}")
    (root / "GATE.md").write_text("gate record\n")
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
    for key, value in (("user.email", "a@b.c"), ("user.name", "T")):
        subprocess.run(["git", "config", key, value], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "release"], cwd=root, check=True)

    digest, count = pack_pin.tree_digest(root)
    (root / "PACK_MANIFEST.json").write_text(json.dumps({
        "pack": "runtime-pack-2", "version": version, "state": state,
        pack_pin.DIGEST_COUNT_KEY: count, "tree_digest_sha256": digest,
        "digest_excludes": "PACK_MANIFEST.json", "digest_algorithm": pack_pin.DIGEST_ALGORITHM,
        "gate_record": "GATE.md", "tests": {"passed": 1},
    }, indent=2) + "\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "manifest"], cwd=root, check=True)

    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                         capture_output=True, text=True, check=True).stdout.strip()
    return ReleaseEntry(version=version, root_path=str(root), sha=sha, digest=digest, state=state)


@pytest.fixture
def releases(tmp_path):
    current = _build_release(tmp_path / "rp-2.1.1", "2.1.1")
    target = _build_release(tmp_path / "rp-2.2.0", "2.2.0", extra="newer\n")
    return current, target


def _pin(entry, **overrides):
    fields = {
        "version": entry.version, "sha": entry.sha, "digest": entry.digest,
        "state": entry.state, "root_path": entry.root_path,
    }
    fields.update(overrides)
    return Pin(**fields)


# --- pack.root_path -----------------------------------------------------------


def test_a_complete_pin_verifies_against_its_declared_root(releases):
    current, _ = releases
    assert classify_pin(_pin(current)) == VERIFIED_PIN
    assert verify_pinned_root(_pin(current)) == []


def test_a_root_that_is_not_the_release_it_claims_is_refused(releases):
    current, target = releases
    wrong = _pin(current, root_path=target.root_path)
    assert verify_pinned_root(wrong)


def test_the_root_is_canonicalised_so_a_symlink_cannot_hide_a_shared_directory(tmp_path, releases):
    """D13 requires distinct immutable roots. A symlink is how two declarations
    that look distinct become one directory — including one being edited."""
    current, _ = releases
    link = tmp_path / "link-to-current"
    link.symlink_to(current.root_path)
    assert canonical_root(link) == canonical_root(current.root_path)


def test_a_symlinked_target_is_caught_as_the_same_root(releases, tmp_path):
    current, _ = releases
    link = tmp_path / "alias"
    link.symlink_to(current.root_path)
    entry = ReleaseEntry(version="2.2.0", root_path=str(link), sha=current.sha,
                         digest=current.digest, state="QUALIFIED_AND_FROZEN")
    report = migration_gate(_pin(current), entry, at_capability_boundary=True)
    assert not report.clean
    assert any("same root" in finding for finding in report.findings)


# --- the legacy pin -----------------------------------------------------------


def test_a_version_only_pin_is_named_rather_than_repaired():
    pin = Pin(version="2.1.0")
    assert classify_pin(pin) == UNVERIFIABLE_LEGACY_PIN
    problems = verify_pinned_root(pin)
    assert problems and UNVERIFIABLE_LEGACY_PIN in problems[0]
    assert "sha_adopted" in problems[0] and "root_path" in problems[0]


def test_the_legacy_pin_report_says_why_it_is_not_repairable():
    """Recording today's values would produce a pin that verifies and describes
    nothing, which is worse than one that admits it cannot."""
    assert "verifies and describes nothing" in verify_pinned_root(Pin(version="2.1.0"))[0]


def test_a_partial_pin_is_legacy_not_verified():
    """Three of four fields is not "nearly checkable"."""
    assert classify_pin(Pin(version="2.1.0", sha="a" * 40, digest="b" * 64)) == UNVERIFIABLE_LEGACY_PIN


def test_migrating_away_from_a_legacy_pin_is_permitted_and_disclosed(releases):
    _, target = releases
    report = migration_gate(Pin(version="2.1.0"), target, at_capability_boundary=True)
    assert report.clean, report.render()
    assert any(UNVERIFIABLE_LEGACY_PIN in note for note in report.notes)
    assert any("nothing can be concluded about what is being left behind" in note
               for note in report.notes)


# --- the migration gate -------------------------------------------------------


def test_a_clean_migration_is_permitted(releases):
    current, target = releases
    report = migration_gate(_pin(current), target, at_capability_boundary=True)
    assert report.clean, report.render()
    assert "not an adoption" in report.render()


def test_migration_mid_capability_is_refused(releases):
    current, target = releases
    report = migration_gate(_pin(current), target, at_capability_boundary=False)
    assert not report.clean
    assert any("capability boundary" in finding for finding in report.findings)


def test_a_target_that_is_not_qualified_and_frozen_is_refused(tmp_path, releases):
    current, _ = releases
    candidate = _build_release(tmp_path / "rp-2.3.0", "2.3.0", state="IN_PROGRESS")
    report = migration_gate(_pin(current), candidate, at_capability_boundary=True)
    assert not report.clean
    assert any("QUALIFIED_AND_FROZEN" in finding for finding in report.findings)


def test_a_target_whose_digest_does_not_match_is_refused(releases):
    current, target = releases
    tampered = ReleaseEntry(version=target.version, root_path=target.root_path,
                            sha=target.sha, digest="0" * 64, state=target.state)
    report = migration_gate(_pin(current), tampered, at_capability_boundary=True)
    assert not report.clean
    assert any(finding.startswith("target:") for finding in report.findings)


def test_a_current_pin_that_stopped_verifying_blocks_migration(releases):
    """A frozen release does not mutate during a run. If it did, that is a stop
    — and it is a stop before moving somewhere else, too."""
    current, target = releases
    (canonical_root(current.root_path) / "README.md").write_text("edited after freezing\n")
    report = migration_gate(_pin(current), target, at_capability_boundary=True)
    assert not report.clean
    assert any("CURRENT pin does not verify" in finding for finding in report.findings)


def test_a_missing_target_directory_is_refused(releases, tmp_path):
    current, _ = releases
    ghost = ReleaseEntry(version="9.9.9", root_path=str(tmp_path / "absent"),
                         sha="a" * 40, digest="b" * 64, state="QUALIFIED_AND_FROZEN")
    report = migration_gate(_pin(current), ghost, at_capability_boundary=True)
    assert not report.clean


# --- security urgency does not remove authority --------------------------------


def test_a_security_advisory_is_disclosed_and_authorises_nothing(releases):
    current, target = releases
    urgent = ReleaseEntry(version=target.version, root_path=target.root_path, sha=target.sha,
                          digest=target.digest, state=target.state,
                          security_advisory="leak in the publication gate")
    report = migration_gate(_pin(current), urgent, at_capability_boundary=True)
    assert any("SECURITY ADVISORY" in note for note in report.notes)
    assert any("human authority" in note for note in report.notes)


def test_a_security_advisory_does_not_bypass_the_capability_boundary(releases):
    current, target = releases
    urgent = ReleaseEntry(version=target.version, root_path=target.root_path, sha=target.sha,
                          digest=target.digest, state=target.state, security_advisory="urgent")
    report = migration_gate(_pin(current), urgent, at_capability_boundary=False)
    assert not report.clean


# --- the release index --------------------------------------------------------


def test_the_release_index_reads(tmp_path, releases):
    current, target = releases
    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text(json.dumps({"releases": [
        {"version": e.version, "root_path": e.root_path, "sha": e.sha,
         "digest": e.digest, "state": e.state} for e in (current, target)
    ]}))
    entries = read_release_index(index)
    assert [e.version for e in entries] == ["2.1.1", "2.2.0"]


def test_an_incomplete_index_entry_is_refused_not_skipped(tmp_path):
    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text(json.dumps({"releases": [{"version": "2.2.0", "root_path": "/x"}]}))
    with pytest.raises(ValueError) as caught:
        read_release_index(index)
    assert "missing" in str(caught.value)


def test_two_index_entries_sharing_a_root_are_refused(tmp_path, releases):
    """One directory moved between revisions makes both pins unverifiable at
    once, which is exactly what D13 forbids."""
    current, _ = releases
    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text(json.dumps({"releases": [
        {"version": "2.1.1", "root_path": current.root_path, "sha": current.sha,
         "digest": current.digest, "state": current.state},
        {"version": "2.2.0", "root_path": current.root_path, "sha": current.sha,
         "digest": current.digest, "state": current.state},
    ]}))
    with pytest.raises(ValueError) as caught:
        read_release_index(index)
    assert "cannot both be pinned" in str(caught.value)


def test_a_duplicate_version_in_the_index_is_refused(tmp_path, releases):
    current, target = releases
    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text(json.dumps({"releases": [
        {"version": "2.2.0", "root_path": current.root_path, "sha": current.sha,
         "digest": current.digest, "state": current.state},
        {"version": "2.2.0", "root_path": target.root_path, "sha": target.sha,
         "digest": target.digest, "state": target.state},
    ]}))
    with pytest.raises(ValueError):
        read_release_index(index)


def test_an_index_entry_is_a_claim_and_the_gate_is_the_verification(tmp_path, releases):
    """An index that says a release is at a path does not make it so."""
    current, _ = releases
    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text(json.dumps({"releases": [
        {"version": "9.9.9", "root_path": str(tmp_path / "nothing-here"),
         "sha": "a" * 40, "digest": "b" * 64, "state": "QUALIFIED_AND_FROZEN"}
    ]}))
    entry = read_release_index(index)[0]
    assert not migration_gate(_pin(current), entry, at_capability_boundary=True).clean


# --- rollback -----------------------------------------------------------------


def test_a_retained_root_that_still_verifies_is_offered(releases):
    current, target = releases
    pin = _pin(target, retained_roots=(current.root_path,))
    available, unavailable = rollback_targets(pin)
    assert available == [str(canonical_root(current.root_path))]
    assert unavailable == []


def test_a_retained_root_that_was_edited_is_not_offered(releases):
    """Retention is not a guarantee. Offering it would be offering a directory
    nobody has checked since it stopped being the release it claims to be."""
    current, target = releases
    (canonical_root(current.root_path) / "README.md").write_text("edited\n")
    available, unavailable = rollback_targets(_pin(target, retained_roots=(current.root_path,)))
    assert available == []
    assert len(unavailable) == 1
    assert current.root_path in unavailable[0]
    assert "digest" in unavailable[0].lower()


def test_a_retained_root_that_was_deleted_is_reported(tmp_path, releases):
    _, target = releases
    pin = _pin(target, retained_roots=(str(tmp_path / "gone"),))
    available, unavailable = rollback_targets(pin)
    assert available == []
    assert "no longer a directory" in unavailable[0]


# --- candidate accounting ------------------------------------------------------


def test_a_candidate_with_no_disposition_is_reported():
    assert unaccounted_candidates(["EC-A", "EC-B", "EC-C"], ["EC-A", "EC-C"]) == ["EC-B"]


def test_a_candidate_arriving_after_the_inbox_was_read_is_the_one_that_is_found():
    """The append-only inbox means the late arrival is at the end, and it is
    exactly the one a session that read the inbox early would skip."""
    assert unaccounted_candidates(["EC-A", "EC-B", "EC-LATE"], ["EC-A", "EC-B"]) == ["EC-LATE"]


def test_full_accounting_reports_nothing():
    assert unaccounted_candidates(["EC-A"], ["EC-A"]) == []
    assert unaccounted_candidates([], []) == []


def test_unaccounted_candidates_block_a_migration(releases):
    current, target = releases
    report = migration_gate(_pin(current), target, at_capability_boundary=True,
                            candidates_accounted=False)
    assert not report.clean
    assert any("must be answered, not skipped" in finding for finding in report.findings)


def test_an_index_entry_declaring_an_unknown_state_is_refused(tmp_path, releases):
    """An index is what a consumer reads to decide what is adoptable; an entry
    naming a state no release can declare is not a complete entry."""
    current, _ = releases
    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text(json.dumps({"releases": [
        {"version": "2.1.1", "root_path": current.root_path, "sha": current.sha,
         "digest": current.digest, "state": "PROBABLY_FINE"},
    ]}))
    with pytest.raises(ValueError) as caught:
        read_release_index(index)
    assert "a release states one of" in str(caught.value)


def test_an_in_progress_entry_is_readable_and_still_not_adoptable(tmp_path, releases):
    """`IN_PROGRESS` is a real state, so the index may carry it — and the gate
    must still refuse to adopt it."""
    current, _ = releases
    candidate = _build_release(tmp_path / "rp-2.3.0", "2.3.0", state="IN_PROGRESS")
    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text(json.dumps({"releases": [
        {"version": candidate.version, "root_path": candidate.root_path, "sha": candidate.sha,
         "digest": candidate.digest, "state": candidate.state},
    ]}))
    entry = read_release_index(index)[0]
    assert not migration_gate(_pin(current), entry, at_capability_boundary=True).clean
