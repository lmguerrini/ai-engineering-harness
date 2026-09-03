"""A record citing a commit nothing keeps alive, and the rewrite that hides it.

Rehearsal A1's fixtures: three commits, a record citing all three, a branch
rebuild that orphans the middle one, an anchor that restores it, and — added
because a reachability check shipped alone fails closed across a whole corpus
the first time anybody rewrites anything — a mapping that resolves the citation
a rewrite invalidated.
"""

import json
import subprocess

import pytest

import history_anchor
from errors import PreconditionError
from history_anchor import CitationState


def _git(repo, *args, **kwargs):
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True,
                          check=True, **kwargs).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    directory = tmp_path / "repo"
    directory.mkdir()
    _git(directory, "init", "--quiet", "--initial-branch", "main")
    _git(directory, "config", "user.name", "Throwaway Tester")
    _git(directory, "config", "user.email", "tester@example.invalid")
    _git(directory, "config", "commit.gpgsign", "false")
    shas = []
    for index in range(3):
        (directory / f"{index}.txt").write_text(f"content {index}\n")
        _git(directory, "add", ".")
        _git(directory, "commit", "--quiet", "-m", f"commit {index}")
        shas.append(_git(directory, "rev-parse", "HEAD"))
    return directory, shas


# --- the reachable case, which must not be a finding ---------------------------


def test_a_record_citing_reachable_commits_is_clean(repo):
    directory, shas = repo
    record = "\n".join(f"closed at {sha}" for sha in shas)
    report = history_anchor.check_reachability(directory, {"CLOSURE.md": record})
    assert report.blocking == []
    assert {c.state for c in report.citations} == {CitationState.REACHABLE}
    assert "every cited commit is reachable" in report.render()


def test_prose_that_happens_to_be_hexadecimal_is_not_a_lost_commit(repo):
    """A checker that called every unrecognised seven-character word a lost
    commit would produce a remediation list nobody could act on."""
    directory, _shas = repo
    report = history_anchor.check_reachability(
        directory, {"NOTES.md": "the deadbeef case and the c0ffee00 case"})
    assert report.blocking == []
    assert {c.state for c in report.citations} == {CitationState.NOT_A_COMMIT}


def test_reading_no_records_at_all_is_not_a_clean_verdict(repo):
    directory, _shas = repo
    report = history_anchor.check_reachability(directory, {})
    assert report.examined.nothing
    assert "NOTHING EXAMINED" in report.render()


# --- the orphaned commit, which is the finding ------------------------------------


def _orphan_the_middle_commit(directory, shas):
    """Rebuild the branch without the middle commit, leaving it unreferenced."""
    _git(directory, "checkout", "--quiet", "-B", "main", shas[0])
    (directory / "2.txt").write_text("content 2\n")
    _git(directory, "add", ".")
    _git(directory, "commit", "--quiet", "-m", "commit 2 again")
    return _git(directory, "rev-parse", "HEAD")


def test_a_cited_commit_no_ref_reaches_fails_closed_naming_the_record(repo):
    directory, shas = repo
    _orphan_the_middle_commit(directory, shas)

    report = history_anchor.check_reachability(
        directory, {"CLOSURE.md": f"the second capability closed at {shas[1]}"})

    assert len(report.blocking) == 1
    finding = report.blocking[0]
    assert finding.state == CitationState.UNREACHABLE
    assert finding.token == shas[1] and finding.where == "CLOSURE.md"
    assert "reflog" in finding.detail
    assert "NOT REACHABLE" in report.render()


def test_an_abbreviated_citation_is_resolved_like_a_full_one(repo):
    directory, shas = repo
    _orphan_the_middle_commit(directory, shas)
    report = history_anchor.check_reachability(
        directory, {"CLOSURE.md": f"closed at {shas[1][:10]}"})
    assert report.blocking and report.blocking[0].state == CitationState.UNREACHABLE


# --- the anchor -------------------------------------------------------------------


def test_a_verified_bundle_names_a_commit_without_proving_it_carries_it(repo, tmp_path):
    """This test asserted the opposite and the assertion was wrong.

    It read *a verified bundle anchor makes an unreachable commit durable*, and
    an independent reader disproved it in one fixture: edit a valid bundle's
    header to name an object the pack does not contain, and `git bundle verify`
    still exits zero while `bundle list-heads` prints the forged name. **A
    header is a claim inside the artifact being checked.**

    Establishing containment means indexing the pack, which is a write, so this
    release reports what it knows — the header names it — and blocks."""
    directory, shas = repo
    bundle = tmp_path / "orphan.bundle"
    # A bundle carries refs, not bare revisions, so the anchor is created as a
    # ref, bundled, and the ref then removed — which is the shape a fence that
    # forbids permanent refs in the repository actually forces.
    _git(directory, "update-ref", "refs/anchors/mid", shas[1])
    _git(directory, "bundle", "create", str(bundle), "refs/anchors/mid")
    _git(directory, "update-ref", "-d", "refs/anchors/mid")
    _orphan_the_middle_commit(directory, shas)

    report = history_anchor.check_reachability(
        directory, {"CLOSURE.md": f"closed at {shas[1]}"}, bundles=[bundle])

    # BLOCKING, and named: the header says the bundle carries it and nothing
    # here has read the pack. An edited header passed `bundle verify`.
    assert report.citations[0].state == CitationState.ANCHOR_UNCONFIRMED
    assert report.citations[0] in report.blocking
    assert report.anchors[0].verified


def test_a_bundle_that_does_not_verify_anchors_nothing(repo, tmp_path):
    """A bundle nobody has verified is a file."""
    directory, shas = repo
    broken = tmp_path / "broken.bundle"
    broken.write_bytes(b"not a bundle")
    _orphan_the_middle_commit(directory, shas)

    report = history_anchor.check_reachability(
        directory, {"CLOSURE.md": f"closed at {shas[1]}"}, bundles=[broken])

    assert report.blocking and report.blocking[0].state == CitationState.UNREACHABLE
    assert not report.anchors[0].verified
    assert "NOT VERIFIED" in report.render()


# --- the mapping, without which this check fails closed across a corpus ------------


def _mapping_file(tmp_path, pairs):
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"schema": history_anchor.MAPPING_SCHEMA, "map": pairs}))
    return path


def test_a_rewritten_citation_resolves_through_the_mapping(repo, tmp_path):
    """The reason this ships with the reachability check rather than after it:
    a rewrite invalidates every commit-shaped token in every record at once, so
    a check shipped alone fails closed on a corpus, not on a defect.

    Blocking, and this docstring has now been wrong twice. It first said the
    bundle made the mapping's claim checkable; a reader disproved that by
    pointing the mapping at an unrelated commit. It then said the bundle proved
    preservation; a reader disproved that by editing the bundle's header. **What
    a verified bundle establishes is that its header names a commit**, and the
    header is a claim inside the artifact being checked.
    """
    directory, shas = repo
    bundle = tmp_path / "original.bundle"
    _git(directory, "update-ref", "refs/anchors/mid", shas[1])
    _git(directory, "bundle", "create", str(bundle), "refs/anchors/mid")
    _git(directory, "update-ref", "-d", "refs/anchors/mid")
    rewritten = _orphan_the_middle_commit(directory, shas)
    mapping = history_anchor.load_mapping(_mapping_file(tmp_path, {shas[1]: rewritten}))

    report = history_anchor.check_reachability(
        directory, {"CLOSURE.md": f"closed at {shas[1]}"},
        mapping=mapping, bundles=[bundle])

    # BLOCKING now, and the docstring above is corrected with it: a bundle
    # header names a commit, and an independent reader edited one to name an
    # object the pack does not contain while `bundle verify` still exited zero.
    # A claim inside the artifact being checked is not evidence about it.
    citation = report.citations[0]
    assert citation.state == CitationState.ANCHOR_UNCONFIRMED
    assert citation in report.blocking
    assert citation.maps_to == rewritten
    assert "ASSERTS" in citation.detail


def test_a_mapping_alone_cannot_clear_a_citation_it_merely_asserts(repo, tmp_path):
    """The finding, from a blind cross-vendor reader: `{orphan: base}` — a
    mapping naming an UNRELATED reachable commit — cleared the orphan.

    Every reachable commit passes "the successor is reachable" equally, so that
    test distinguishes nothing. The mapping is the caller's assertion, and a
    checker that accepts the caller's assertion as its own evidence has asked
    the caller for the answer. Blocking now, and it names the two things that
    would settle it.
    """
    directory, shas = repo
    _orphan_the_middle_commit(directory, shas)
    unrelated = _git(directory, "rev-parse", "HEAD").strip()
    mapping = history_anchor.load_mapping(_mapping_file(tmp_path, {shas[1]: unrelated}))

    report = history_anchor.check_reachability(
        directory, {"CLOSURE.md": f"closed at {shas[1]}"}, mapping=mapping)

    citation = report.citations[0]
    assert citation.state == CitationState.REMAPPED_UNVERIFIED
    assert citation in report.blocking
    assert citation.maps_to == unrelated
    assert "CORROBORATES" in citation.detail


def test_an_in_memory_mapping_is_held_to_the_shape_the_loader_enforces(repo):
    """`load_mapping` refuses an abbreviated revision; the keyword argument beside
    it accepted one. A validated loader next to an unvalidated constructor is a
    validated PATH, and callers take the other one."""
    directory, shas = repo
    with pytest.raises(PreconditionError):
        history_anchor.check_reachability(
            directory, {"CLOSURE.md": "x"}, mapping={shas[1][:8]: shas[0]})


def test_a_mapping_whose_successor_is_also_unreachable_still_blocks(repo, tmp_path):
    directory, shas = repo
    _orphan_the_middle_commit(directory, shas)
    mapping = history_anchor.load_mapping(_mapping_file(tmp_path, {"a" * 40: "b" * 40}))
    report = history_anchor.check_reachability(
        directory, {"CLOSURE.md": f"closed at {'a' * 40}"}, mapping=mapping)
    assert report.blocking and report.blocking[0].maps_to == "b" * 40


def test_a_mapping_the_consumer_cannot_read_is_refused_rather_than_skipped(tmp_path):
    """A reachability check running with a mapping it silently failed to load
    reports every rewritten citation as lost — a corpus-sized false positive."""
    broken = tmp_path / "map.json"
    broken.write_text("{ not json")
    with pytest.raises(PreconditionError):
        history_anchor.load_mapping(broken)

    broken.write_text(json.dumps({"map": {}}))
    with pytest.raises(PreconditionError) as caught:
        history_anchor.load_mapping(broken)
    assert history_anchor.MAPPING_SCHEMA in caught.value.render()


def test_a_mapping_holding_abbreviations_is_refused(tmp_path):
    """An abbreviation is what makes a mapping ambiguous exactly when it
    matters."""
    path = _mapping_file(tmp_path, {"abc1234": "b" * 40})
    with pytest.raises(PreconditionError):
        history_anchor.load_mapping(path)


def test_no_mapping_at_all_is_an_empty_one_rather_than_a_refusal():
    assert history_anchor.load_mapping(None) == {}


# --- the invariants a rewrite must not break --------------------------------------


def test_a_rewrite_with_no_proven_rollback_is_a_finding(repo):
    directory, shas = repo
    findings = history_anchor.verify_rewrite(directory, directory, {}, rollback_proven=False)
    assert any(f.field == "rollback" for f in findings)


def test_a_rewrite_with_no_mapping_is_a_finding(repo):
    directory, _shas = repo
    findings = history_anchor.verify_rewrite(directory, directory, {}, rollback_proven=True)
    assert [f.field for f in findings] == ["mapping"]


def test_a_changed_committer_date_is_reported_and_the_field_is_named(repo, tmp_path):
    """`MUST GO RED` on a rewrite that changes a committer date — and the report
    must name the field, not merely fail."""
    directory, shas = repo
    after = tmp_path / "after"
    subprocess.run(["git", "clone", "--quiet", str(directory), str(after)],
                   check=True, capture_output=True)
    _git(after, "config", "user.name", "Throwaway Tester")
    _git(after, "config", "user.email", "tester@example.invalid")
    _git(after, "commit", "--quiet", "--amend", "--no-edit", "--date=2020-01-01T00:00:00Z")
    new_head = _git(after, "rev-parse", "HEAD")

    findings = history_anchor.verify_rewrite(
        directory, after, {shas[2]: new_head}, rollback_proven=True)

    named = {f.field for f in findings}
    assert "author date" in named or "committer date" in named, [str(f) for f in findings]
    assert all(str(f).startswith(f.field) for f in findings)


def test_an_identical_rewrite_breaks_no_invariant(repo):
    """The other side. A checker that reported findings against an unchanged
    pair would be refusing correct work."""
    directory, shas = repo
    findings = history_anchor.verify_rewrite(
        directory, directory, {sha: sha for sha in shas}, rollback_proven=True)
    assert findings == []


def test_a_mapping_naming_a_commit_neither_repository_has_is_reported(repo):
    directory, _shas = repo
    findings = history_anchor.verify_rewrite(
        directory, directory, {"a" * 40: "b" * 40}, rollback_proven=True)
    assert findings and all(f.field == "mapping" for f in findings)


def test_this_module_performs_no_rewrite_and_creates_no_ref():
    """Core detects, classifies and verifies. Executing a rewrite is a human
    decision, and a module that could perform one would be the authority D23
    clause 6 withholds."""
    names = set(dir(history_anchor))
    for forbidden in ("rewrite", "filter_branch", "create_ref", "prune", "gc", "expire",
                      "apply_mapping", "remediate"):
        assert forbidden not in names, f"history_anchor gained {forbidden!r}"


# --- the residue a rewrite tool leaves ------------------------------------------------


def test_the_publication_gate_names_the_rewrite_residue_namespace():
    """A history-rewrite tool leaves such refs behind, and `grep` over the
    entire governance corpus finds no record of them."""
    import publication_gate

    prefixes = {prefix for prefix, _ in publication_gate._KNOWN_PRIVATE_NAMESPACES}
    assert "refs/rewritten/" in prefixes
    assert "refs/replace/" in prefixes


# --- four cases the first mutation pass proved were not being reached ------------
#
# Each of these existed as an assertion the code satisfied for the wrong reason:
# the fixture never entered the branch, so breaking the branch changed nothing.


def test_a_real_unreachable_commit_whose_successor_is_also_unreachable_blocks(repo, tmp_path):
    """The earlier version of this test mapped one invented revision to another,
    so it exercised the not-an-object path and never the one it named."""
    directory, shas = repo
    _git(directory, "checkout", "--quiet", "-b", "side", shas[1])
    (directory / "side.txt").write_text("side\n")
    _git(directory, "add", ".")
    _git(directory, "commit", "--quiet", "-m", "a successor that will also be orphaned")
    successor = _git(directory, "rev-parse", "HEAD")
    _git(directory, "checkout", "--quiet", "main")
    _git(directory, "branch", "--quiet", "-D", "side")
    _orphan_the_middle_commit(directory, shas)

    mapping = history_anchor.load_mapping(_mapping_file(tmp_path, {shas[1]: successor}))
    report = history_anchor.check_reachability(
        directory, {"CLOSURE.md": f"closed at {shas[1]}"}, mapping=mapping)

    assert report.blocking, "a successor no ref reaches resolves nothing"
    assert report.blocking[0].state == CitationState.UNREACHABLE
    assert report.blocking[0].maps_to == successor


def test_a_bundle_whose_prerequisite_is_absent_anchors_nothing(repo, tmp_path):
    """A bundle that lists its head is not a bundle that can be restored.

    `git bundle verify` checks prerequisites, not pack contents — every
    corruption tried here verified clean — so the only construction that
    separates the two is a **range** bundle verified where its prerequisite is
    missing. A shallow clone provides exactly that: it holds the cited commit
    and not the commit the bundle is relative to.

    Two earlier fixtures failed to reach this guard. One used a file that was
    not a bundle at all, so every path refused it; one truncated a valid bundle,
    which verifies clean. **The guard was satisfied for the wrong reason both
    times**, and only a mutation showed it.
    """
    directory, shas = repo
    _git(directory, "update-ref", "refs/anchors/mid", shas[1])
    incomplete = tmp_path / "range.bundle"
    _git(directory, "bundle", "create", str(incomplete), f"{shas[0]}..refs/anchors/mid")
    _git(directory, "update-ref", "-d", "refs/anchors/mid")

    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "--quiet", "--depth", "2", f"file://{directory}", str(shallow)],
                   check=True, capture_output=True)
    _git(shallow, "config", "user.name", "Throwaway Tester")
    _git(shallow, "config", "user.email", "tester@example.invalid")
    # Orphan the cited commit here too: present as an object, reached by nothing.
    _git(shallow, "checkout", "--quiet", "--orphan", "fresh")
    _git(shallow, "commit", "--quiet", "--allow-empty", "-m", "a history that reaches nothing")
    _git(shallow, "branch", "--quiet", "-D", "main")
    # And the remote-tracking refs, which reach it too. `rev-list --all` means
    # every ref, and forgetting that is how a "no ref reaches this" fixture
    # quietly stops reproducing.
    _git(shallow, "remote", "remove", "origin")

    assert _git(shallow, "cat-file", "-t", shas[1]) == "commit", "the fixture must still hold it"
    verify = subprocess.run(["git", "bundle", "verify", str(incomplete)], cwd=shallow,
                            capture_output=True, text=True)
    heads = subprocess.run(["git", "bundle", "list-heads", str(incomplete)], cwd=shallow,
                           capture_output=True, text=True)
    assert verify.returncode != 0 and heads.returncode == 0, (
        "the fixture must fail verification while still listing its head"
    )

    report = history_anchor.check_reachability(
        shallow, {"CLOSURE.md": f"closed at {shas[1]}"}, bundles=[incomplete])

    assert not report.anchors[0].verified
    assert report.blocking and report.blocking[0].state == CitationState.UNREACHABLE, (
        "an unverified bundle anchored a commit"
    )


def test_an_abbreviation_matching_two_mapping_entries_resolves_to_neither(repo, tmp_path):
    """A mapping consulted ambiguously is worse than one not consulted, because
    it answers."""
    directory, _shas = repo
    prefix = "abcdef1"
    mapping = history_anchor.load_mapping(_mapping_file(tmp_path, {
        prefix + "0" * 33: "1" * 40,
        prefix + "1" * 33: "2" * 40,
    }))
    # Cited at exactly the shared prefix: an abbreviation is only ambiguous
    # when it is a prefix of more than one entry, and the first version of this
    # test cited a LONGER token that prefixed neither, so nothing was ambiguous
    # and the mutation went unobserved.
    report = history_anchor.check_reachability(
        directory, {"NOTES.md": f"see {prefix}"}, mapping=mapping)
    assert report.citations[0].state == CitationState.NOT_A_COMMIT
    assert report.citations[0].maps_to is None


def test_a_repository_git_cannot_read_is_unknown_and_blocks(tmp_path):
    """Not prose, and not clean. A checker that read "nobody looked" as "nothing
    found" is the defect this pack exists to refuse, and the mutation that
    turned this branch off changed no test until now."""
    not_a_repository = tmp_path / "plain"
    not_a_repository.mkdir()
    report = history_anchor.check_reachability(
        not_a_repository, {"CLOSURE.md": "closed at " + "a" * 40})
    assert report.citations[0].state == CitationState.UNKNOWN
    assert report.blocking, "UNKNOWN blocks; it is not a clean verdict"


def test_a_verified_bundle_anchors_only_the_commits_it_actually_carries(repo, tmp_path):
    """Otherwise one anchor would clear every finding in the corpus."""
    directory, shas = repo
    _git(directory, "checkout", "--quiet", "-b", "side", shas[0])
    (directory / "side.txt").write_text("side\n")
    _git(directory, "add", ".")
    _git(directory, "commit", "--quiet", "-m", "an unrelated commit")
    unrelated = _git(directory, "rev-parse", "HEAD")

    _git(directory, "update-ref", "refs/anchors/mid", shas[1])
    bundle = tmp_path / "mid-only.bundle"
    _git(directory, "bundle", "create", str(bundle), "refs/anchors/mid")
    _git(directory, "update-ref", "-d", "refs/anchors/mid")
    _git(directory, "checkout", "--quiet", "main")
    _git(directory, "branch", "--quiet", "-D", "side")
    _orphan_the_middle_commit(directory, shas)

    report = history_anchor.check_reachability(
        directory,
        {"CLOSURE.md": f"the anchored one is {shas[1]} and the other is {unrelated}"},
        bundles=[bundle],
    )

    assert report.anchors[0].verified
    states = {c.token: c.state for c in report.citations}
    assert states[shas[1]] == CitationState.ANCHOR_UNCONFIRMED
    assert states[unrelated] == CitationState.UNREACHABLE, (
        "a verified bundle anchored a commit it does not carry"
    )


# --- the verdict must not go green when the loss becomes irreversible ----------
#
# The worst defect this module had, found by an independent auditor who ran the
# prune: an orphaned commit reported UNREACHABLE and blocked, and once
# `gc --prune=now` destroyed it the same command over the same record reported
# `every cited commit is reachable or anchored`. The tool alarmed only while the
# citation was still recoverable.


def test_a_destroyed_citation_blocks_rather_than_reading_as_prose(repo):
    directory, shas = repo
    _orphan_the_middle_commit(directory, shas)
    record = {"CLOSURE.md": f"the second capability closed at {shas[1]}"}

    before = history_anchor.check_reachability(directory, record)
    assert before.blocking and before.blocking[0].state == CitationState.UNREACHABLE

    _git(directory, "reflog", "expire", "--expire=now", "--all")
    _git(directory, "gc", "--prune=now", "--quiet")

    after = history_anchor.check_reachability(directory, record)
    assert after.blocking, "the verdict went green exactly when the loss became irreversible"
    assert after.blocking[0].state == CitationState.DESTROYED
    assert "ARE GONE FROM THIS REPOSITORY" in after.render()
    assert "every cited commit is reachable" not in after.render()


def test_a_full_length_token_the_repository_never_had_is_destroyed_not_prose(repo):
    """A full-length token the repository never had: nobody writes forty
    hexadecimal characters into a closure record by accident."""
    directory, _shas = repo
    report = history_anchor.check_reachability(
        directory, {"CLOSURE.md": "closed at " + "a1b2c3d4" * 5})
    assert report.blocking and report.blocking[0].state == CitationState.DESTROYED


def test_a_short_hexadecimal_word_is_still_prose(repo):
    """The other side. A checker that called every unrecognised seven-character
    word a lost commit produces a list nobody can act on."""
    directory, _shas = repo
    report = history_anchor.check_reachability(
        directory, {"NOTES.md": "the deadbeef case and the c0ffee00 case"})
    assert report.blocking == []
    assert {c.state for c in report.citations} == {CitationState.NOT_A_COMMIT}


def test_the_cli_exits_non_zero_on_a_destroyed_citation(repo, capsys):
    directory, shas = repo
    _orphan_the_middle_commit(directory, shas)
    _git(directory, "reflog", "expire", "--expire=now", "--all")
    _git(directory, "gc", "--prune=now", "--quiet")
    record = directory / "CLOSURE.md"
    record.write_text(f"closed at {shas[1]}\n")
    assert history_anchor._cli([str(directory), "--record", str(record)]) == 1


def test_a_full_object_name_the_repository_holds_is_not_reported_as_gone(repo):
    """The length rule said "GONE FROM THIS REPOSITORY" about a blob the
    repository holds perfectly well, because it asked only whether the token
    resolved to a COMMIT. Found by an auditor pointing it at the repository's
    own blob."""
    directory, _shas = repo
    blob = _git(directory, "rev-parse", "HEAD:0.txt")
    tree = _git(directory, "rev-parse", "HEAD^{tree}")
    report = history_anchor.check_reachability(
        directory, {"NOTES.md": f"the blob {blob} and the tree {tree}"})

    states = {c.token: c.state for c in report.citations}
    assert states[blob] == CitationState.NOT_A_COMMIT
    assert states[tree] == CitationState.NOT_A_COMMIT
    assert report.blocking == []
    assert "GONE FROM THIS REPOSITORY" not in report.render()
    assert "rather than a commit" in " ".join(c.detail for c in report.citations)


def test_a_full_object_name_the_repository_does_not_hold_is_still_destroyed(repo):
    directory, _shas = repo
    report = history_anchor.check_reachability(
        directory, {"CLOSURE.md": "closed at " + "a1b2c3d4" * 5})
    assert report.blocking and report.blocking[0].state == CitationState.DESTROYED


def test_a_bundle_proves_preservation_and_never_the_mapping(repo, tmp_path):
    """A blind reader kept the original in a verified bundle, pointed the
    mapping at an UNRELATED reachable commit, and the citation went green as
    REMAPPED.

    A bundle proves the original is preserved. It says nothing about whether the
    asserted successor is that commit's rewrite. Preservation is the real
    remedy, so that is the state, and the mapping is reported beside it as the
    assertion it is."""
    directory, shas = repo
    bundle = tmp_path / "original.bundle"
    _git(directory, "update-ref", "refs/anchors/mid", shas[1])
    _git(directory, "bundle", "create", str(bundle), "refs/anchors/mid")
    _git(directory, "update-ref", "-d", "refs/anchors/mid")
    _orphan_the_middle_commit(directory, shas)
    unrelated = _git(directory, "rev-parse", "HEAD").strip()
    mapping = history_anchor.load_mapping(_mapping_file(tmp_path, {shas[1]: unrelated}))

    report = history_anchor.check_reachability(
        directory, {"CLOSURE.md": f"closed at {shas[1]}"}, mapping=mapping, bundles=[bundle])

    citation = report.citations[0]
    assert citation.state == CitationState.ANCHOR_UNCONFIRMED
    assert "ASSERTS" in citation.detail
    assert "nothing here checked either claim" in citation.detail


def test_a_sha256_repository_is_read_rather_than_reported_clean(tmp_path):
    """The token pattern stopped at 40 characters, so in a SHA-256 repository
    **every citation was invisible** and the report read `citations: 0,
    blocking: 0` — clean, about a corpus nobody looked at. Found by an
    independent reader who built one.

    The dangerous direction, and the reason this is a repair rather than a
    portability nicety."""
    repo = tmp_path / "sha256"
    repo.mkdir()
    made = subprocess.run(["git", "init", "-q", "--object-format=sha256", "-b", "main"],
                          cwd=repo, capture_output=True, text=True)
    if made.returncode != 0:
        pytest.skip("this Git does not build SHA-256 repositories")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "user.email", "t@example.invalid")
    (repo / "f").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    head = _git(repo, "rev-parse", "HEAD").strip()
    assert len(head) == 64

    report = history_anchor.check_reachability(repo, {"CLOSURE.md": f"closed at {head}"})
    assert report.citations, "a 64-character object name is a citation"
    assert report.citations[0].state == CitationState.REACHABLE


def test_a_commit_only_inside_a_bundle_blocks_rather_than_being_anchored(tmp_path):
    """The bounded guarantee for bundle containment, stated as what it is.

    **MAKES:** a cited commit that is gone from the repository and is not a head
    of any verified bundle BLOCKS. **DOES NOT MAKE:** that a commit reachable
    *within* a bundle is recognised — `_bundle_contains` compares
    `bundle list-heads` tips, and proving reachability inside a bundle means
    unbundling, which this release does not do because it does not write.

    **Unsafe acceptance?** No. The error reports `DESTROYED` and blocks a closure
    that could legitimately have proceeded: conservative, and the safe direction.
    **Revisit when:** a project's anchoring practice bundles ranges rather than
    the cited commits themselves, at which point the refusal starts costing.
    """
    repo = tmp_path / "pruned"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "user.email", "t@example.invalid")
    for content in ("one", "two"):
        (repo / "f").write_text(content)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", content)
    parent = _git(repo, "rev-parse", "HEAD~1").strip()
    bundle = tmp_path / "all.bundle"
    _git(repo, "bundle", "create", str(bundle), "main")

    _git(repo, "checkout", "-q", "--orphan", "fresh")
    (repo / "g").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "a fresh root")
    _git(repo, "branch", "-qD", "main")
    _git(repo, "reflog", "expire", "--expire=now", "--all")
    _git(repo, "gc", "--prune=now", "--quiet")

    report = history_anchor.check_reachability(
        repo, {"CLOSURE.md": f"closed at {parent}"}, bundles=[bundle])
    citation = report.citations[0]
    assert citation.state == CitationState.DESTROYED
    assert citation in report.blocking, "the safe direction: it blocks rather than anchoring"


def test_a_bundle_header_naming_a_commit_the_pack_lacks_does_not_anchor(repo, tmp_path):
    """The finding, and it broke a bound this release had already stated.

    An independent reader took a valid bundle, replaced the head SHA in its
    header with an object the pack does not contain, and: `git bundle verify`
    exited **zero**, `bundle list-heads` printed the forged name, and a citation
    of a commit present in neither the repository nor the pack came back
    `ANCHORED` and non-blocking.

    **A header is a claim inside the artifact being checked** — the one kind of
    evidence this pack refuses everywhere else, accepted here. Confirming
    containment means indexing the pack, which is a write, so the honest state
    is that the header names it and nothing has read the contents.
    """
    directory, shas = repo
    bundle = tmp_path / "forged.bundle"
    _git(directory, "bundle", "create", str(bundle), "HEAD")
    head = _git(directory, "rev-parse", "HEAD").strip()
    absent = "a1b2c3d4" * 5
    bundle.write_bytes(bundle.read_bytes().replace(head.encode(), absent.encode(), 1))

    verified = subprocess.run(["git", "bundle", "verify", str(bundle)],
                              cwd=directory, capture_output=True, text=True)
    assert verified.returncode == 0, "the premise: git still verifies the edited bundle"

    # Asserted as the PROPERTY rather than as one state: with no mapping the
    # forged name reaches `DESTROYED` first, and with one it reaches
    # `ANCHOR_UNCONFIRMED`. Both block, which is the thing that matters, and
    # pinning either state would make this test a claim about which branch runs.
    for mapping in (None, {absent: _git(directory, "rev-parse", "HEAD").strip()}):
        report = history_anchor.check_reachability(
            directory, {"CLOSURE.md": f"closed at {absent}"},
            bundles=[bundle], mapping=mapping)
        citation = report.citations[0]
        assert citation in report.blocking, (
            f"a forged header anchored a commit the pack lacks: {citation.state}")
        assert citation.state != CitationState.ANCHORED
