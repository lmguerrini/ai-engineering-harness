"""Core qualification is not Core self-tests.

The release that this suite belongs to was green through four audit rounds while
the contract reader **raised** on the only real consumer that had a Project
Context — making that project's contract unreadable by every tool, for any
purpose. Nothing in the suite could see it, because nothing in the suite had the
shape of a real consumer.

So this module is the compatibility half of qualification: representative
project shapes, built from real ones with the substance removed, exercised end
to end against a real pack root built in a temporary directory. It depends on no
private path, no particular home directory and no personal project continuing to
exist — those were the primary evidence, and this is what was derived from them.

Every assertion here is about a **compatibility class**, listed in
`consumer_shapes.SHAPES` with the class it preserves. The class list is asserted
too: losing one silently is how a release forgets a lesson.
"""

import json
import subprocess

import pytest

import capability_open
import consumer_shapes
import pack_pin
import project_context
from project_contract import ContractError, ProjectContract


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)


@pytest.fixture(scope="module")
def release(tmp_path_factory):
    """A real pack root: a git repository with a manifest that verifies.

    Built rather than mocked. A fixture that faked `verify_pin` would prove the
    readiness checker calls something, not that a project can be verified
    against a release.
    """
    root = tmp_path_factory.mktemp("release") / "pack"
    root.mkdir()
    _git(root, "init", "--quiet", "--initial-branch", "main")
    _git(root, "config", "user.name", "Ordinary Human")
    _git(root, "config", "user.email", "human@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "VERSION").write_text("3.0.0\n")
    (root / "GATE.md").write_text("# gate\n")
    _git(root, "add", "VERSION", "GATE.md")
    _git(root, "commit", "--quiet", "-m", "release")

    digest, count = pack_pin.tree_digest(root)
    manifest = {
        "pack": "representative-release",
        "version": "3.0.0",
        "state": "QUALIFIED_AND_FROZEN",
        pack_pin.DIGEST_COUNT_KEY: count,
        "tree_digest_sha256": digest,
        "digest_excludes": pack_pin.MANIFEST_NAME,
        "digest_algorithm": pack_pin.DIGEST_ALGORITHM,
        "gate_record": "GATE.md",
        "tests": {"passed": 1},
    }
    (root / pack_pin.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    _git(root, "add", pack_pin.MANIFEST_NAME)
    _git(root, "commit", "--quiet", "-m", "manifest")

    digest, count = pack_pin.tree_digest(root)
    manifest[pack_pin.DIGEST_COUNT_KEY] = count
    manifest["tree_digest_sha256"] = digest
    (root / pack_pin.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")

    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True, check=True
    ).stdout.strip()
    assert pack_pin.verify_pin(
        root, expect_version="3.0.0", expect_sha=sha,
        expect_digest=digest, expect_state="QUALIFIED_AND_FROZEN",
    ) == [], "the representative release must itself verify, or nothing below means anything"
    return {"root": str(root), "version": "3.0.0", "sha": sha, "digest": digest,
            "state": "QUALIFIED_AND_FROZEN"}


@pytest.fixture
def context_tree(tmp_path):
    """A Project Context directory and its digest, built the way a project's is."""
    root = tmp_path / ".project_context"
    root.mkdir()
    (root / "D1.md").write_text("the product means this\n")
    (root / "OPEN.md").write_text("this is still open\n")
    digest, _count = project_context.tree_digest(root)
    return {"path": str(root), "digest": digest}


def _contract(tmp_path, shape, release, context_tree, **overrides):
    values = {
        "name": "representative",
        "repo": str(tmp_path / "repo"),
        "root": release["root"],
        "version": release["version"],
        "sha": release["sha"],
        "digest": release["digest"],
        "state": release["state"],
        "context": context_tree["path"],
        "context_digest": context_tree["digest"],
    }
    values.update(overrides)
    path = tmp_path / "PROJECT.yaml"
    path.write_text(consumer_shapes.render(shape, **values))
    return path


# --- the corpus itself is part of the guarantee -------------------------------

def test_every_compatibility_class_the_release_learned_is_still_listed():
    """A shape deleted quietly is a lesson lost quietly."""
    expected = {
        "legacy_pin_version_only",
        "full_pin_qualified_no_context",
        "full_pin_context_verified",
        "context_declared_without_digest",
        "context_required_and_absent",
        "context_required_and_verified",
        "pin_to_an_unqualified_release",
    }
    assert set(consumer_shapes.SHAPES) == expected
    for name, (description, template) in consumer_shapes.SHAPES.items():
        assert len(description) > 40, f"{name} does not say which class it preserves"
        assert "project:" in template


def test_no_shape_carries_a_personal_path_or_a_real_project_name():
    """The corpus must survive this machine, and must not import private data."""
    for name, (description, template) in consumer_shapes.SHAPES.items():
        blob = description + template
        assert "/Users/" not in blob and "/home/" not in blob, name
        assert "{" in template or "pack:" not in template  # paths are placeholders


# --- every shape loads, which is the failure that shipped ---------------------

@pytest.mark.parametrize("shape", sorted(consumer_shapes.SHAPES))
def test_every_representative_contract_loads(tmp_path, shape, release, context_tree):
    """The defect this whole module exists for: a real contract that would not
    load at all. A shape that cannot be read has no other behaviour to test."""
    contract = ProjectContract.load(_contract(tmp_path, shape, release, context_tree))
    assert contract.raw.get("project", {}).get("name") == "representative"


@pytest.mark.parametrize("shape", sorted(consumer_shapes.SHAPES))
def test_blocks_core_does_not_understand_never_stop_a_contract_loading(
    tmp_path, shape, release, context_tree
):
    """All three real consumers declare blocks Core never reads. A reader that
    refused them would have broken every real consumer at once."""
    contract = ProjectContract.load(_contract(tmp_path, shape, release, context_tree))
    for block in ("dimensions", "critical_domains", "mutation_policy", "validation_profiles"):
        assert block in contract.raw, f"{shape} lost {block}"


# --- readiness, per class -----------------------------------------------------

def test_a_legacy_pin_reads_as_legacy_and_stops_the_open_without_calling_it_broken(
    tmp_path, release, context_tree
):
    report = capability_open.open_capability(
        _contract(tmp_path, "legacy_pin_version_only", release, context_tree)
    )
    pin = report.component("pack_pin")

    assert pin.state == capability_open.LEGACY
    assert report.state == capability_open.NOT_READY
    # Distinct from a pin that was checked and failed, and from one nobody wrote.
    assert pin.state not in (capability_open.UNVERIFIABLE, capability_open.NOT_PRESENT)
    assert any("capability boundary" in note for note in pin.notes), "no remedy is stated"


def test_a_fully_identified_pin_against_a_qualified_release_is_ready(
    tmp_path, release, context_tree
):
    report = capability_open.open_capability(
        _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree)
    )
    assert report.state == capability_open.READY, report.render()
    assert report.ready
    assert report.component("pack_pin").state == capability_open.VERIFIED
    assert report.component("pack_release_state").state == capability_open.VERIFIED


def test_a_pin_to_an_unqualified_release_verifies_and_is_still_not_ready(
    tmp_path, release, context_tree
):
    """Two questions that were one. `verify_pin` answers *is this root what you
    pinned* — completely, and for an `IN_PROGRESS` release the answer is yes.
    Nothing answered *is what you pinned adoptable*."""
    unqualified = dict(release)
    unqualified["state"] = "IN_PROGRESS"
    manifest_path = f"{release['root']}/{pack_pin.MANIFEST_NAME}"
    manifest = json.loads(open(manifest_path).read())
    manifest["state"] = "IN_PROGRESS"
    open(manifest_path, "w").write(json.dumps(manifest, indent=2) + "\n")
    try:
        path = _contract(tmp_path, "pin_to_an_unqualified_release", unqualified, context_tree,
                         state="IN_PROGRESS")
        report = capability_open.open_capability(path)

        assert report.component("pack_pin").state == capability_open.VERIFIED, report.render()
        assert report.component("pack_release_state").state == capability_open.UNVERIFIABLE
        assert report.state == capability_open.NOT_READY
    finally:
        manifest["state"] = "QUALIFIED_AND_FROZEN"
        open(manifest_path, "w").write(json.dumps(manifest, indent=2) + "\n")


def test_a_context_declared_in_an_older_shape_is_unverifiable_and_stops_the_open(
    tmp_path, release, context_tree
):
    """The real consumer's shape. Not `NOT_PRESENT`, not clean, and not a
    crash — and blocking even though this project never declared it required,
    because a requirement governs absence and this context is declared."""
    report = capability_open.open_capability(
        _contract(tmp_path, "context_declared_without_digest", release, context_tree)
    )
    context = report.component("project_context")

    assert context.state == capability_open.UNVERIFIABLE
    assert context.required is False and context.blocking is True
    assert report.state == capability_open.NOT_READY
    assert any("digest" in finding for finding in context.findings)


def test_a_simple_project_may_omit_a_context_entirely(tmp_path, release, context_tree):
    report = capability_open.open_capability(
        _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree)
    )
    context = report.component("project_context")

    assert context.state == capability_open.NOT_REQUIRED
    assert context.blocking is False
    assert report.ready


def test_a_project_that_requires_a_context_and_has_none_is_not_ready(
    tmp_path, release, context_tree
):
    """The class that could not be expressed before 2.2.0: absence had to read
    as clean for every project, including products whose correctness depends on
    durable semantic authority."""
    report = capability_open.open_capability(
        _contract(tmp_path, "context_required_and_absent", release, context_tree)
    )
    context = report.component("project_context")

    assert context.state == capability_open.NOT_PRESENT
    assert context.required is True and context.blocking is True
    assert report.state == capability_open.NOT_READY


def test_the_same_requirement_satisfied_is_ready(tmp_path, release, context_tree):
    """So the requirement is a condition, not an unconditional refusal."""
    report = capability_open.open_capability(
        _contract(tmp_path, "context_required_and_verified", release, context_tree)
    )
    assert report.component("project_context").state == capability_open.VERIFIED, report.render()
    assert report.state == capability_open.READY


def test_a_verified_context_that_then_changes_stops_the_next_open(
    tmp_path, release, context_tree
):
    """Identity, checked against the filesystem rather than against the
    declaration's own claim about itself."""
    path = _contract(tmp_path, "context_required_and_verified", release, context_tree)
    assert capability_open.open_capability(path).ready

    (tmp_path / ".project_context" / "D2.md").write_text("a new durable decision\n")
    report = capability_open.open_capability(path)

    assert report.component("project_context").state == capability_open.UNVERIFIABLE
    assert report.state == capability_open.NOT_READY


# --- release selection: newer is information, never a block -------------------

def test_a_newer_qualified_release_is_reported_and_does_not_block(
    tmp_path, release, context_tree
):
    """`READY_WITH_UPDATE_AVAILABLE`, never `BLOCKED_BECAUSE_NOT_LATEST`.

    A project deliberately pinned to an older qualified immutable release is
    correctly pinned until it adopts at a capability boundary. Treating "not
    latest" as a failure would regress the multi-project architecture into one
    where every project must move whenever any release is cut.
    """
    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text(json.dumps({
        "releases": [
            {"version": "3.0.0", "root_path": release["root"], "sha": release["sha"],
             "digest": release["digest"], "state": "QUALIFIED_AND_FROZEN"},
            {"version": "4.0.0", "root_path": str(tmp_path / "future-release"),
             "sha": "b" * 40, "digest": "c" * 64, "state": "QUALIFIED_AND_FROZEN"},
        ]
    }, indent=2))

    report = capability_open.open_capability(
        _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree),
        release_index=index,
    )

    assert report.state == capability_open.READY_WITH_UPDATE_AVAILABLE, report.render()
    assert report.ready, "a newer release must never make a correctly pinned project unready"
    update = report.component("release_update")
    assert update.state == capability_open.UPDATE_AVAILABLE and update.blocking is False
    assert any("4.0.0" in note for note in update.notes)


def test_an_unreadable_release_index_leaves_availability_unknown_and_ready(
    tmp_path, release, context_tree
):
    """Availability is information. Failing to obtain information about
    something that is not a prerequisite cannot make a project unready."""
    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text("{not json")

    report = capability_open.open_capability(
        _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree),
        release_index=index,
    )
    assert report.component("release_update").state == capability_open.UNKNOWN
    assert report.ready


def test_no_newer_release_listed_is_plain_ready(tmp_path, release, context_tree):
    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text(json.dumps({"releases": [
        {"version": "3.0.0", "root_path": release["root"], "sha": release["sha"],
         "digest": release["digest"], "state": "QUALIFIED_AND_FROZEN"},
    ]}, indent=2))

    report = capability_open.open_capability(
        _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree),
        release_index=index,
    )
    assert report.state == capability_open.READY


def test_an_unqualified_newer_release_is_not_an_available_update(
    tmp_path, release, context_tree
):
    """A candidate is not an update. Announcing one as available would invite a
    project to adopt something no human has released."""
    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text(json.dumps({"releases": [
        {"version": "3.0.0", "root_path": release["root"], "sha": release["sha"],
         "digest": release["digest"], "state": "QUALIFIED_AND_FROZEN"},
        {"version": "4.0.0", "root_path": str(tmp_path / "candidate"), "sha": "b" * 40,
         "digest": "c" * 64, "state": "IN_PROGRESS"},
    ]}, indent=2))

    report = capability_open.open_capability(
        _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree),
        release_index=index,
    )
    assert report.component("release_update").state == capability_open.NOT_PRESENT
    assert report.state == capability_open.READY


# --- the capability being opened ----------------------------------------------

def test_opening_a_capability_the_project_never_declared_is_refused(
    tmp_path, release, context_tree
):
    path = _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree)
    assert capability_open.open_capability(path, capability="C1-first").state == capability_open.READY

    report = capability_open.open_capability(path, capability="C9-invented")
    assert report.component("capability").state == capability_open.UNVERIFIABLE
    assert report.state == capability_open.NOT_READY


# --- adoption mid-capability --------------------------------------------------

def test_adoption_is_refused_when_the_caller_cannot_say_it_is_at_a_boundary(
    tmp_path, release, context_tree
):
    """Only the caller knows. "The caller did not say" is not "yes", and an
    active capability silently changing release is the failure this prevents."""
    import pack_migration

    target = pack_migration.ReleaseEntry(
        version="4.0.0", root_path=str(tmp_path / "future"), sha="b" * 40,
        digest="c" * 64, state="QUALIFIED_AND_FROZEN",
    )
    path = _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree)

    report = capability_open.open_capability(path, proposed_release=target)
    migration = report.component("migration")
    assert migration.state == capability_open.UNKNOWN
    assert report.state == capability_open.NOT_READY

    mid = capability_open.open_capability(
        path, proposed_release=target, at_capability_boundary=False
    )
    assert any("capability boundary" in finding for finding in mid.component("migration").findings)


# --- the contract itself ------------------------------------------------------

def test_an_unreadable_contract_stops_everything_and_says_so(tmp_path):
    path = tmp_path / "PROJECT.yaml"
    path.write_text("project:\n  name: [unclosed\n")

    report = capability_open.open_capability(path)
    assert report.state == capability_open.NOT_READY
    assert report.component("project_contract").state == capability_open.UNVERIFIABLE
    assert len(report.components) == 1, "nothing may be assumed once the contract is unreadable"


def test_a_requirement_nothing_checks_is_refused_rather_than_ignored(tmp_path, release, context_tree):
    """A requirement silently ignored is worse than none: the project believes
    it is enforced."""
    path = _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree)
    path.write_text(path.read_text() + "\nrequires:\n  something_nobody_checks: true\n")

    with pytest.raises(ContractError) as caught:
        capability_open.open_capability(path)
    assert "nothing checks" in str(caught.value)


def test_a_non_boolean_requirement_is_refused(tmp_path, release, context_tree):
    path = _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree)
    path.write_text(path.read_text() + '\nrequires:\n  project_context: "yes please"\n')

    with pytest.raises(ContractError):
        capability_open.open_capability(path)


def test_a_project_declaring_no_requirements_gets_the_permissive_default():
    assert capability_open.requirements_from(None) == {"project_context": False}
    assert capability_open.requirements_from({}) == {"project_context": False}
    assert capability_open.requirements_from({"project_context": True})["project_context"] is True
