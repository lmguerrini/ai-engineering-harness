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


def _commit_manifest_if_changed(root):
    """Leave the manifest committed, the way a frozen release's manifest is.

    The recomputed digest used to be left in the working tree, which models a
    release half cut rather than one a project could pin. RP2.4.1 R5 compares
    the manifest with the commit it claims to come from, and this fixture was
    the only thing giving that comparison something to say. Conditional because
    for one of these fixtures the recomputation is a no-op, and `git commit`
    with nothing staged is an error rather than a success.
    """
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain",
                            "--", pack_pin.MANIFEST_NAME],
                           capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        _git(root, "add", pack_pin.MANIFEST_NAME)
        _git(root, "commit", "--quiet", "-m",
             "recompute the identity over the released tree")


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
    # COMMITTED, because a frozen release's manifest is. The recomputed digest
    # used to be left in the working tree, which models a release half cut
    # rather than one a project could pin: RP2.4.1 R5 compares the manifest with
    # the commit it claims to come from, and this fixture was the only reason
    # that comparison had anything to say. Re-committing the manifest does not
    # move the digest, which excludes it.
    _commit_manifest_if_changed(root)

    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True, check=True
    ).stdout.strip()
    assert pack_pin.verify_pin(
        root, expect_version="3.0.0", expect_sha=sha,
        expect_digest=digest, expect_state="QUALIFIED_AND_FROZEN",
    ) == [], "the representative release must itself verify, or nothing below means anything"
    return {"root": str(root), "version": "3.0.0", "sha": sha, "digest": digest,
            "state": "QUALIFIED_AND_FROZEN"}


def _build_release(root, version, state="QUALIFIED_AND_FROZEN"):
    root.mkdir(parents=True)
    _git(root, "init", "--quiet", "--initial-branch", "main")
    _git(root, "config", "user.name", "Ordinary Human")
    _git(root, "config", "user.email", "human@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "VERSION").write_text(f"{version}\n")
    (root / "GATE.md").write_text("# gate\n")
    _git(root, "add", "VERSION", "GATE.md")
    _git(root, "commit", "--quiet", "-m", "release")

    manifest = {
        "pack": "representative-release", "version": version, "state": state,
        "digest_excludes": pack_pin.MANIFEST_NAME,
        "digest_algorithm": pack_pin.DIGEST_ALGORITHM,
        "gate_record": "GATE.md", "tests": {"passed": 1},
        pack_pin.DIGEST_COUNT_KEY: 0, "tree_digest_sha256": "0" * 64,
    }
    (root / pack_pin.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    _git(root, "add", pack_pin.MANIFEST_NAME)
    _git(root, "commit", "--quiet", "-m", "manifest")

    digest, count = pack_pin.tree_digest(root)
    manifest[pack_pin.DIGEST_COUNT_KEY] = count
    manifest["tree_digest_sha256"] = digest
    (root / pack_pin.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    _commit_manifest_if_changed(root)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root),
                         capture_output=True, text=True, check=True).stdout.strip()
    return {"root": str(root), "version": version, "sha": sha, "digest": digest, "state": state}


@pytest.fixture(scope="module")
def newer_release(tmp_path_factory):
    """A REAL second qualified release, so "available" can mean verified.

    The first version of the availability test listed a release at a path that
    did not exist. It passed, because the checker took the index's word — which
    is the blocker an audit reproduced by putting an `IN_PROGRESS` release and a
    nonexistent root into an index that declared both qualified.
    """
    return _build_release(tmp_path_factory.mktemp("newer") / "pack", "4.0.0")


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
        "intent": "internal",
    }
    # A real adapter file, so the digest in the shape is the digest of bytes
    # that exist. A shape carrying an invented digest would test the refusal
    # path while claiming to test the verifying one.
    adapter = tmp_path / "adapter.md"
    if not adapter.exists():
        adapter.write_text("name: a-worker\n", encoding="utf-8")
    import hashlib

    values["adapter"] = str(adapter)
    values["adapter_digest"] = hashlib.sha256(adapter.read_bytes()).hexdigest()
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
        "full_pin_that_does_not_verify",
        # RP2.3
        "unchanged_since_2_2",
        "adapter_with_executable",
        "internal_intent",
        "public_intent",
    }
    assert set(consumer_shapes.SHAPES) == expected
    assert set(consumer_shapes.REFUSED_SHAPES) == {"legacy_flat_private_terms"}
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
    for block in ("dimensions", "critical_domains", "mutation_policy", "validation_profiles",
                  "private_terms", "workspace_classification", "publication"):
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
    tmp_path, context_tree
):
    """Two questions that were one. `verify_pin` answers *is this root what you
    pinned* — completely, and for an `IN_PROGRESS` release the answer is yes.
    Nothing answered *is what you pinned adoptable*.

    BUILT AS ITS OWN RELEASE rather than by editing the shared one in place.
    The state used to be flipped in the module-scoped fixture's working tree and
    flipped back in a `finally`, which models nothing: a release's state is a
    committed fact, and RP2.4.1 R5 now compares the manifest with the commit it
    claims to come from. `_build_release` already takes the state, which is what
    that parameter is for.
    """
    unqualified = _build_release(tmp_path / "unqualified" / "pack", "3.0.0",
                                 state="IN_PROGRESS")
    path = _contract(tmp_path, "pin_to_an_unqualified_release", unqualified, context_tree,
                     state="IN_PROGRESS")
    report = capability_open.open_capability(path)

    assert report.component("pack_pin").state == capability_open.VERIFIED, report.render()
    assert report.component("pack_release_state").state == capability_open.UNVERIFIABLE
    assert report.state == capability_open.NOT_READY


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
    tmp_path, release, context_tree, newer_release
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
            {"version": "4.0.0", "root_path": newer_release["root"], "sha": newer_release["sha"],
             "digest": newer_release["digest"], "state": "QUALIFIED_AND_FROZEN"},
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
    # EVERY known requirement, permissive — stated as the property rather than
    # as a literal dict, so adding a requirement cannot break this test while
    # adding one that defaults to *blocking* still does. Every real consumer
    # omits the block.
    for declared in (None, {}):
        defaults = capability_open.requirements_from(declared)
        assert set(defaults) == set(capability_open.REQUIREMENT_KEYS)
        assert all(value is False for value in defaults.values()), defaults
    assert capability_open.requirements_from({"project_context": True})["project_context"] is True
    assert capability_open.requirements_from({"design": True})["design"] is True


# --- undeclared is not declared-none ------------------------------------------

def test_an_absent_adapters_block_is_unknown_and_a_declared_empty_one_is_not(
    tmp_path, release, context_tree
):
    """`adapter_pin` refuses to read "nobody said" as "someone said none", and
    the readiness path keeps that distinction instead of flattening it. Neither
    blocks — a project that dispatches through nothing needs no adapters — but a
    reader is told which of the two they are looking at.

    Every real consumer omits the block, so this is the state they are actually
    in, and reporting it as a confident NOT_PRESENT would be a false answer
    about all three.
    """
    path = _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree)
    absent = capability_open.open_capability(path).component("adapters")
    assert absent.state == capability_open.UNKNOWN
    assert absent.blocking is False
    assert any("adapters: []" in note for note in absent.notes), "no remedy is stated"

    path.write_text(path.read_text() + "\nadapters: []\n")
    declared = capability_open.open_capability(path).component("adapters")
    assert declared.state == capability_open.NOT_PRESENT
    assert declared.blocking is False
    assert capability_open.open_capability(path).ready


# --- an index is untrusted input ---------------------------------------------

def test_an_index_entry_that_does_not_verify_is_listed_and_not_offered(
    tmp_path, release, context_tree
):
    """`pack_migration` calls the index untrusted input and verifies each entry
    against the release it names. This composed it and then offered entries on
    the index's word alone — an audit put an `IN_PROGRESS` release and a root
    that does not exist into an index declaring both qualified, and both were
    announced as available qualified releases.

    "The index lists it and it does not verify" is a true, useful sentence.
    "A newer qualified release is available" was not.
    """
    lying = _build_release(tmp_path / "unqualified", "4.0.0", state="IN_PROGRESS")

    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text(json.dumps({"releases": [
        {"version": "3.0.0", "root_path": release["root"], "sha": release["sha"],
         "digest": release["digest"], "state": "QUALIFIED_AND_FROZEN"},
        # The index CLAIMS qualified; the root itself says IN_PROGRESS.
        {"version": "4.0.0", "root_path": lying["root"], "sha": lying["sha"],
         "digest": lying["digest"], "state": "QUALIFIED_AND_FROZEN"},
        {"version": "5.0.0", "root_path": str(tmp_path / "not-there"), "sha": "b" * 40,
         "digest": "c" * 64, "state": "QUALIFIED_AND_FROZEN"},
    ]}, indent=2))

    report = capability_open.open_capability(
        _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree),
        release_index=index,
    )
    update = report.component("release_update")

    assert update.state == capability_open.UNKNOWN, update
    assert report.ready, "an index that lies must still not block a correctly pinned project"
    joined = " ".join(update.notes)
    assert "does not verify" in joined and "Listed, not offered" in joined
    assert "a newer qualified release is available" not in joined


def test_an_unorderable_pin_version_is_never_told_it_is_behind(
    tmp_path, release, context_tree, newer_release
):
    """A pin this cannot order sorted below everything, so a project pinned to
    `wave-a` was told a numbered release was newer. Unknown, not behind."""
    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text(json.dumps({"releases": [
        {"version": "4.0.0", "root_path": newer_release["root"], "sha": newer_release["sha"],
         "digest": newer_release["digest"], "state": "QUALIFIED_AND_FROZEN"},
    ]}, indent=2))

    path = _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree,
                     version="wave-a")
    update = capability_open.open_capability(path, release_index=index).component("release_update")

    assert update.state == capability_open.UNKNOWN
    assert any("cannot be ordered" in note for note in update.notes)
    assert not any("newer qualified release is available" in note for note in update.notes)


def test_a_security_advisory_on_an_offered_release_is_carried_into_the_note(
    tmp_path, release, context_tree, newer_release
):
    """It was parsed and then dropped by the one component a reader sees."""
    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text(json.dumps({"releases": [
        {"version": "4.0.0", "root_path": newer_release["root"], "sha": newer_release["sha"],
         "digest": newer_release["digest"], "state": "QUALIFIED_AND_FROZEN",
         "security_advisory": "CVE-0000-0000, a made-up one"},
    ]}, indent=2))

    report = capability_open.open_capability(
        _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree),
        release_index=index,
    )
    update = report.component("release_update")
    assert update.state == capability_open.UPDATE_AVAILABLE
    assert any("SECURITY ADVISORY" in note for note in update.notes)
    assert report.ready, "an advisory is a human decision about urgency, not a block here"


def test_a_complete_pin_pointing_at_a_different_release_does_not_verify(
    tmp_path, release, context_tree, newer_release
):
    """Every field present, none of them true of the root. Nothing in the suite
    constrained this path — an audit reverted `if problems:` to `if False:` and
    the whole suite stayed green while a project pointed at the wrong release
    reported READY.

    It is also the state a real consumer is in the moment anyone checks a branch
    out in the directory it pinned, which is why the release carries a decision
    about release roots being checkouts nobody works in.
    """
    path = _contract(tmp_path, "full_pin_that_does_not_verify", release, context_tree,
                     root=newer_release["root"])
    report = capability_open.open_capability(path)
    pin = report.component("pack_pin")

    assert pin.state == capability_open.UNVERIFIABLE, report.render()
    assert pin.state != capability_open.LEGACY, "a complete pin that fails is not a legacy pin"
    assert pin.blocking and report.state == capability_open.NOT_READY
    assert any("does not match" in finding or "manifest says" in finding
               for finding in pin.findings), pin.findings


def test_the_release_state_component_reads_the_root_not_the_projects_own_claim(
    tmp_path, release, context_tree, newer_release
):
    """It answered by re-reading `state_adopted` out of the contract — the
    project's claim, restated and called verification. An audit reproduced it
    against a real consumer: one line said the root holds `IN_PROGRESS`, the
    next said the release-state prerequisite was VERIFIED.
    """
    unqualified = _build_release(tmp_path / "candidate-release", "9.9.9", state="IN_PROGRESS")
    path = _contract(tmp_path, "pin_to_an_unqualified_release", release, context_tree,
                     root=unqualified["root"], version=unqualified["version"],
                     sha=unqualified["sha"], digest=unqualified["digest"],
                     state="QUALIFIED_AND_FROZEN")

    state = capability_open.open_capability(path).component("pack_release_state")
    assert state.state == capability_open.UNVERIFIABLE, state
    assert "IN_PROGRESS" in state.findings[0]


def test_the_release_state_of_a_root_that_cannot_be_found_is_unknown(
    tmp_path, release, context_tree
):
    """Never VERIFIED. The state of a release nobody can locate is unknown."""
    path = _contract(tmp_path, "full_pin_that_does_not_verify", release, context_tree,
                     root=str(tmp_path / "nowhere"))
    state = capability_open.open_capability(path).component("pack_release_state")
    assert state.state == capability_open.UNKNOWN, state
    assert state.blocking


def test_a_relative_pinned_root_is_refused_rather_than_resolved_against_the_cwd(
    tmp_path, release, context_tree
):
    """The same contract answered differently from different directories, which
    falsifies the module's own determinism claim.

    The root deliberately does not contain the word this asserts on. A first
    version used `../some/relative/root` and asserted `"relative" in finding` —
    satisfied by the PATH ITSELF, so removing the check left the test green.
    """
    path = _contract(tmp_path, "full_pin_that_does_not_verify", release, context_tree,
                     root="../elsewhere/pack")
    report = capability_open.open_capability(path)
    pin = report.component("pack_pin")

    assert pin.state == capability_open.UNVERIFIABLE
    assert any("depends on the current working directory" in finding
               for finding in pin.findings), pin.findings
    assert report.state == capability_open.NOT_READY


def test_a_context_the_project_switched_off_does_not_satisfy_a_requirement_for_one(
    tmp_path, release, context_tree
):
    """It verified, so the requirement read as satisfied and the aggregate was
    READY — while the module's own note says a deactivated context is verified
    AND NOT CONSULTED. The project said it needs one consulted."""
    path = _contract(tmp_path, "context_required_and_verified", release, context_tree)
    assert capability_open.open_capability(path).ready

    path.write_text(path.read_text().replace("activated: true", "activated: false"))
    report = capability_open.open_capability(path)

    assert report.component("project_context").state == capability_open.UNVERIFIABLE
    assert report.state == capability_open.NOT_READY
    assert any("NOT ACTIVATED" in finding for finding in report.component("project_context").findings)


def test_an_adapter_absent_by_permission_is_not_reported_as_verified(tmp_path, release, context_tree):
    """`clean` is the adapter verifier's judgement about whether to BLOCK, and a
    permitted absence is clean. Reporting the component VERIFIED on the strength
    of that put the word "verified" above a finding reading "declared and not
    installed" — a collapse of two of the seven states this module keeps apart.
    """
    home = tmp_path / "home"
    (home / ".claude" / "skills").mkdir(parents=True)
    installed = home / ".claude" / "skills" / "present.md"
    installed.write_text("# a skill\n")

    import adapter_pin
    digest = adapter_pin.file_digest(installed)

    path = _contract(tmp_path, "full_pin_qualified_no_context", release, context_tree)
    path.write_text(path.read_text() + f"""
adapters:
  - id: "present"
    locator: "~/.claude/skills/present.md"
    digest: "{digest}"
    required: true
  - id: "absent-but-permitted"
    locator: "~/.claude/skills/absent.md"
    digest: "{'0' * 64}"
    required: false
""")

    report = capability_open.open_capability(path, home=str(home))
    adapters = report.component("adapters")

    assert adapters.state == capability_open.UNKNOWN, adapters
    assert adapters.state != capability_open.VERIFIED, "a permitted absence is not a verification"
    assert adapters.blocking is False, "a permitted absence must not block"
    assert any("1 of 2" in note for note in adapters.notes), adapters.notes
    assert report.ready


# --- RP2.3: every key this release adds is optional, and the old shape is named
#
# The MINOR claim under `DECISIONS.md` D24 rests on the first of these: a
# contract written before this release loads and behaves exactly as it did.


def test_a_contract_from_before_this_release_behaves_exactly_as_it_did(
    tmp_path, release, context_tree
):
    """The MINOR claim, asserted rather than argued. Every key RP2.3 adds is
    absent here, and absence must be indistinguishable from the previous
    release rather than merely tolerated."""
    contract = ProjectContract.load(
        _contract(tmp_path, "unchanged_since_2_2", release, context_tree))

    assert contract.publication_intent is None
    assert contract.reproducible_by == ()
    assert contract.raw.get("closure") is None
    assert contract.default_terms, "the default vocabulary still resolves"
    assert contract.default_terms_source.canonical


def test_an_internal_project_is_not_walked_through_publication_ceremony(
    tmp_path, release, context_tree
):
    import publication_history

    contract = ProjectContract.load(
        _contract(tmp_path, "internal_intent", release, context_tree, intent="internal"))
    applicable, not_applicable, _why = publication_history.obligations(contract)

    assert contract.publication_intent == "internal"
    assert not_applicable, "an internal project carries fewer obligations, not more"
    assert set(applicable) == set(publication_history.UNIVERSAL_OBLIGATIONS)


def test_a_public_project_carries_both_halves_and_names_its_environments(
    tmp_path, release, context_tree
):
    import publication_history

    contract = ProjectContract.load(
        _contract(tmp_path, "public_intent", release, context_tree, intent="public"))
    applicable, not_applicable, _why = publication_history.obligations(contract)

    assert not not_applicable
    assert dict(contract.reproducible_by) == {
        "focused": "developer_machine", "full": "public_clone"}


def test_a_project_may_declare_that_an_unrun_profile_does_not_stop_it(
    tmp_path, release, context_tree
):
    import close_attestation

    contract = ProjectContract.load(
        _contract(tmp_path, "internal_intent", release, context_tree, intent="internal"))
    profiles = list(contract.raw.get("validation_profiles") or {})
    attestation = close_attestation.attest(
        "C1-first", profiles, {}, head_revision="a" * 40, tree_digest="b" * 64,
        refuses_on_unrun=bool((contract.raw.get("closure") or {}).get("refuses_on_unrun", True)),
    )
    assert attestation.unrun and not attestation.blocking
    assert "UNRUN" in attestation.render(), "the profiles are enumerated either way"


def test_an_adapter_declaring_its_executable_verifies_the_program_too(
    tmp_path, release, context_tree
):
    import adapter_pin

    contract = ProjectContract.load(
        _contract(tmp_path, "adapter_with_executable", release, context_tree))
    report = adapter_pin.verify_contract(contract)
    assert report.clean, report.render()
    assert report.executables_verified == ["a-worker"]
    assert "1 file(s), 1 executable(s)" in report.render()


def test_the_pre_2_1_contract_is_refused_with_its_migration_named(
    tmp_path, release, context_tree
):
    """Live on a real machine, unreadable by every tool since the schema
    changed, and told only that its file was the wrong type. A project a
    generation behind should learn that it is a generation behind."""
    path = _contract(tmp_path, "legacy_flat_private_terms", release, context_tree)
    with pytest.raises(ContractError) as caught:
        ProjectContract.load(path)

    message = str(caught.value)
    _description, _template, must_say = consumer_shapes.REFUSED_SHAPES["legacy_flat_private_terms"]
    assert must_say in message
    assert "default_set" in message and "project:" in message
    assert "NOT migrated automatically" in message, (
        "guessing which tier an entry belongs to would change what gets scanned"
    )


def test_every_refused_shape_names_what_its_refusal_has_to_say():
    """A refusal fixture whose expected message is not asserted is a fixture
    that passes on any refusal at all."""
    for name, (description, template, must_say) in consumer_shapes.REFUSED_SHAPES.items():
        assert len(description) > 40, name
        assert "project:" in template, name
        assert must_say.strip(), f"{name} does not say what its refusal must contain"


# --- adoption: a candidate is not adoptable, and the gate says so ------------------


def test_a_project_cannot_adopt_a_target_that_is_not_itself_qualified(tmp_path):
    """`DECISIONS.md` D21 reserves hard refusal for what is actually broken, and
    a migration target that is not itself qualified is on that list.

    **It builds the unqualified target it needs.** This used to point at the
    live pack and carried its own warning that it would stop meaning anything
    the moment the candidate was frozen — which is exactly what the founder
    freeze did. A test whose subject can be promoted out from under it is a
    test about a moment; the property is about any target.
    """
    import json

    import pack_migration

    candidate = _build_release(tmp_path / "candidate", "9.9.9", state="IN_PROGRESS")
    index = tmp_path / "RELEASE_INDEX.json"
    index.write_text(json.dumps({"releases": [{
        "version": candidate["version"], "root_path": candidate["root"],
        "sha": candidate["sha"], "digest": candidate["digest"], "state": candidate["state"],
    }]}))
    target = pack_migration.read_release_index(index)[0]
    assert target.state == "IN_PROGRESS", "the fixture did not build an unqualified target"

    pin = pack_migration.Pin(
        root_path=candidate["root"], version="2.2.0", sha="d" * 40, digest="4" * 64,
        state="QUALIFIED_AND_FROZEN",
    )
    report = pack_migration.migration_gate(pin, target, at_capability_boundary=True)
    assert report.findings, "an unqualified target must be refused, not offered"
    assert any("IN_PROGRESS" in finding or "QUALIFIED" in finding for finding in report.findings), (
        report.findings
    )

    #: and the pack this test runs inside, whatever state it is in, is offered
    #: only when that state is the adoptable one — the same rule, applied to the
    #: subject the old version of this test pointed at.
    import pathlib
    import subprocess

    root = pathlib.Path(pack_migration.__file__).parent.parent
    manifest = json.loads((root / "PACK_MANIFEST.json").read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root),
                          capture_output=True, text=True, check=True).stdout.strip()
    live_index = tmp_path / "LIVE_INDEX.json"
    live_index.write_text(json.dumps({"releases": [{
        "version": manifest["version"], "root_path": str(root), "sha": head,
        "digest": manifest["tree_digest_sha256"], "state": manifest["state"],
    }]}))
    live = pack_migration.read_release_index(live_index)[0]
    live_report = pack_migration.migration_gate(
        pack_migration.Pin(root_path=str(root), version="2.2.0", sha="d" * 40,
                           digest="4" * 64, state="QUALIFIED_AND_FROZEN"),
        live, at_capability_boundary=True)
    if manifest["state"] == "QUALIFIED_AND_FROZEN":
        assert not any("IN_PROGRESS" in f for f in live_report.findings), live_report.findings
    else:
        assert live_report.findings, "an unqualified live pack must be refused too"
