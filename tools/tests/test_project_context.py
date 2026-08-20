"""Project Context: identity is checked, meaning is not.

Two claims are under test, and the second is as important as the first.

1.  A declared context is *located and verified*, and every way it can fail to
    be has its own name — "nobody declared one" and "one was declared and cannot
    be found" must never collapse into the same answer.
2.  The Core **does not adjudicate product meaning.** The tests below change the
    context's content in ways that are semantically enormous and ways that are
    semantically nothing, and the module behaves identically: it reports that
    the bytes differ. That is the whole of its opinion.
"""

import pytest

from project_context import (
    CURRENTLY_VERIFIED,
    DIGEST_ALGORITHM,
    NOT_PRESENT,
    STALE,
    UNVERIFIABLE,
    ContextDeclaration,
    ContextError,
    assert_unchanged,
    declaration_from,
    tree_digest,
    verify,
)


@pytest.fixture
def context(tmp_path):
    root = tmp_path / ".project_context"
    (root / "decisions").mkdir(parents=True)
    (root / "decisions" / "D1.md").write_text("the product means this\n")
    (root / "open").mkdir()
    (root / "open" / "Q1.md").write_text("still open\n")
    (root / "MANIFEST.md").write_text("revision 12\n")
    return root


def _declare(root, **overrides):
    digest, _count = tree_digest(root)
    fields = {
        "context_id": "PROJECT-CONTEXT-001",
        "reference_path": str(root),
        "revision": 12,
        "digest": digest,
        "authority_role": "DURABLE_SEMANTIC_PRODUCT_AUTHORITY",
    }
    fields.update(overrides)
    return ContextDeclaration(**fields)


# --- the digest ----------------------------------------------------------------


def test_the_digest_is_stable_across_recomputation(context):
    assert tree_digest(context) == tree_digest(context)


def test_the_digest_counts_the_files_it_covered(context):
    _digest, count = tree_digest(context)
    assert count == 3


def test_a_content_change_changes_the_digest(context):
    before, _ = tree_digest(context)
    (context / "decisions" / "D1.md").write_text("the product means something else\n")
    assert tree_digest(context)[0] != before


def test_a_rename_changes_the_digest(context):
    """Path and content are hashed together, so a rename is a change."""
    before, _ = tree_digest(context)
    (context / "decisions" / "D1.md").rename(context / "decisions" / "D2.md")
    assert tree_digest(context)[0] != before


def test_the_framing_stops_a_byte_moving_across_the_path_boundary(tmp_path):
    """Unframed, path `ab` + content `c` and path `a` + content `bc` hash the
    same, so a rename that moves one byte across the boundary is invisible."""
    first = tmp_path / "first"
    first.mkdir()
    (first / "ab").write_text("c")
    second = tmp_path / "second"
    second.mkdir()
    (second / "a").write_text("bc")
    assert tree_digest(first)[0] != tree_digest(second)[0]


def test_a_symlink_is_recorded_as_its_target_not_followed(tmp_path, context):
    """A context must not be changeable from outside itself by repointing a
    link, and a link out of the tree must not pull unrelated bytes into the
    identity."""
    outside = tmp_path / "outside.md"
    outside.write_text("original\n")
    (context / "linked.md").symlink_to(outside)
    before, _ = tree_digest(context)

    outside.write_text("rewritten from outside the context\n")
    assert tree_digest(context)[0] == before


def test_volatile_directories_do_not_enter_the_identity(context):
    before, _ = tree_digest(context)
    (context / "__pycache__").mkdir()
    (context / "__pycache__" / "x.pyc").write_bytes(b"\x00\x01")
    (context / ".DS_Store").write_bytes(b"junk")
    assert tree_digest(context)[0] == before


# --- the states are distinct ----------------------------------------------------


def test_no_declaration_is_not_present_and_is_clean():
    report = verify(None)
    assert report.state == NOT_PRESENT
    assert report.clean


def test_a_matching_context_is_currently_verified(context):
    report = verify(_declare(context))
    assert report.state == CURRENTLY_VERIFIED
    assert report.clean


def test_a_declared_context_that_cannot_be_found_is_unverifiable_not_absent(tmp_path):
    """The distinction that matters: "nobody declared one" is fine, "one was
    declared and is missing" is a stop."""
    declaration = ContextDeclaration(
        context_id="X", reference_path=str(tmp_path / "gone"), revision=1, digest="0" * 64
    )
    report = verify(declaration)
    assert report.state == UNVERIFIABLE
    assert not report.clean
    assert "not NOT_PRESENT" in report.render()


def test_a_changed_context_is_stale_and_is_not_repaired_by_copying_the_digest(context):
    declaration = _declare(context)
    (context / "MANIFEST.md").write_text("revision 13\n")

    report = verify(declaration)
    assert report.state == STALE
    assert not report.clean
    assert "neither is repaired by copying the new digest in" in report.render()


def test_a_declared_but_inactive_context_is_verified_and_disclosed(context):
    report = verify(_declare(context, activated=False))
    assert report.state == CURRENTLY_VERIFIED
    assert report.clean
    assert "NOT activated" in report.render()


# --- Core does not adjudicate product meaning -----------------------------------


def test_a_semantically_enormous_change_and_a_trivial_one_are_reported_identically(context):
    """The module's entire opinion is "the bytes differ". If it ever grows one
    about *what* differs, it has started holding product authority."""
    declaration = _declare(context)

    (context / "decisions" / "D1.md").write_text("THE PRODUCT NOW MEANS THE OPPOSITE\n")
    enormous = verify(declaration)

    (context / "decisions" / "D1.md").write_text("the product means this \n")  # one space
    trivial = verify(declaration)

    assert enormous.state == trivial.state == STALE
    assert len(enormous.findings) == len(trivial.findings) == 1


def test_the_authority_role_is_recorded_and_not_interpreted(context):
    report = verify(_declare(context, authority_role="WHATEVER THE PROJECT SAYS IT IS"))
    assert "WHATEVER THE PROJECT SAYS IT IS" in report.render()
    assert "not interpreted here" in report.render()


# --- proposal is not adoption ----------------------------------------------------


def test_a_pending_proposal_changes_nothing_about_what_the_context_says(context):
    """A suggestion must not become authority by being written down."""
    with_proposal = verify(_declare(context, proposals_pending=3))
    without = verify(_declare(context))
    assert with_proposal.state == without.state == CURRENTLY_VERIFIED
    assert with_proposal.observed_digest == without.observed_digest
    assert "not an adoption" in with_proposal.render()


# --- no silent mutation during a capability ---------------------------------------


def test_an_unchanged_context_passes_the_close_check(context):
    declaration = _declare(context)
    opened, _ = tree_digest(context)
    assert assert_unchanged(declaration, opened, capability="C1") == []


def test_a_context_that_changed_mid_capability_is_a_stop(context):
    declaration = _declare(context)
    opened, _ = tree_digest(context)
    (context / "open" / "Q1.md").write_text("answered, during the capability\n")

    problems = assert_unchanged(declaration, opened, capability="C1")
    assert problems
    assert "cannot be interpreted" in problems[0]
    assert "not a refresh" in problems[0]


def test_a_context_that_disappeared_mid_capability_is_a_stop(context):
    declaration = _declare(context)
    opened, _ = tree_digest(context)
    for path in sorted(context.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    context.rmdir()

    assert assert_unchanged(declaration, opened, capability="C1")


# --- the declaration itself --------------------------------------------------------


def test_an_absent_block_is_no_context():
    assert declaration_from(None) is None


@pytest.mark.parametrize(
    "block, expected",
    [
        ({"reference_path": "/x", "revision": 1, "digest": "a" * 64}, "context_id"),
        ({"context_id": "X", "revision": 1, "digest": "a" * 64}, "reference_path"),
        ({"context_id": "X", "reference_path": "/x", "digest": "a" * 64}, "revision"),
        ({"context_id": "X", "reference_path": "/x", "revision": 1}, "digest"),
        ({"context_id": "X", "reference_path": "/x", "revision": 1, "digest": "short"}, "digest"),
        ({"context_id": "X", "reference_path": "/x", "revision": -1, "digest": "a" * 64}, "revision"),
    ],
)
def test_a_malformed_declaration_raises_rather_than_half_parsing(block, expected):
    """A declaration that half-parses is the worst outcome available: the
    capability proceeds believing it has a verified semantic authority."""
    with pytest.raises(ContextError) as caught:
        declaration_from(block)
    assert expected in str(caught.value)


def test_a_digest_algorithm_this_verifier_does_not_implement_is_refused():
    with pytest.raises(ContextError) as caught:
        declaration_from({
            "context_id": "X", "reference_path": "/x", "revision": 1,
            "digest": "a" * 64, "digest_algorithm": "blake3-something",
        })
    assert DIGEST_ALGORITHM in str(caught.value)


def test_a_boolean_is_not_accepted_as_a_revision():
    with pytest.raises(ContextError):
        declaration_from({
            "context_id": "X", "reference_path": "/x", "revision": True, "digest": "a" * 64
        })


def test_a_well_formed_block_parses(context):
    digest, _ = tree_digest(context)
    declaration = declaration_from({
        "context_id": "PROJECT-CONTEXT-001",
        "reference_path": str(context),
        "revision": 12,
        "digest": digest,
        "authority_role": "DURABLE_SEMANTIC_PRODUCT_AUTHORITY",
        "activated": True,
        "proposals_pending": 0,
    })
    assert verify(declaration).state == CURRENTLY_VERIFIED


def test_the_contract_loader_parses_the_declaration(tmp_path):
    """`ProjectContract.load` parsed `adapters:` and not `project_context:`, so
    a declaration had to be handed to the verifier by hand and nothing failed
    at load. Found by an independent audit."""
    import project_contract

    root = tmp_path / ".project_context"
    root.mkdir()
    (root / "D1.md").write_text("the product means this\n")
    digest, _count = tree_digest(root)

    contract_path = tmp_path / "PROJECT.yaml"
    contract_path.write_text(
        "project:\n  name: x\n"
        "project_context:\n"
        f"  context_id: C1\n  reference_path: {root}\n  revision: 1\n  digest: {digest}\n"
    )
    contract = project_contract.ProjectContract.load(contract_path)
    assert contract.project_context is not None
    assert contract.project_context.context_id == "C1"
    assert verify(contract.project_context).state == CURRENTLY_VERIFIED


def test_a_malformed_declaration_fails_at_contract_load(tmp_path):
    import project_contract

    contract_path = tmp_path / "PROJECT.yaml"
    contract_path.write_text(
        "project:\n  name: x\nproject_context:\n  context_id: C1\n  revision: 1\n"
    )
    with pytest.raises(project_contract.ContractError):
        project_contract.ProjectContract.load(contract_path)


def test_a_contract_with_no_context_block_reports_none(tmp_path):
    import project_contract

    contract_path = tmp_path / "PROJECT.yaml"
    contract_path.write_text("project:\n  name: x\n")
    assert project_contract.ProjectContract.load(contract_path).project_context is None


def test_declared_is_reachable_and_is_not_clean(context):
    """It existed as a constant, as a line in the template, and in no code path.
    A state nothing can reach is a state nobody can act on."""
    from project_context import DECLARED, report_declared

    report = report_declared(_declare(context))
    assert report.state == DECLARED
    assert not report.clean
    assert "not yet verified" in report.render()


def test_report_declared_on_no_declaration_is_not_present():
    from project_context import report_declared

    assert report_declared(None).state == NOT_PRESENT
