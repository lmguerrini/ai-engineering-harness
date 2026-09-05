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

import hashlib
import pytest

import adapter_pin
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


# --- the executable behind the files ------------------------------------------
#
# RP3-1, live at this release's baseline: one adapter's definition files matched
# their digests exactly while the program they drive was a version ahead of the
# qualified one, and this module reported every adapter verified. The note
# beside the declaration said the qualified version was "verified installed at
# bootstrap"; nothing compared that sentence to the path.

import sys as _sys

from errors import PreconditionError as _PreconditionError


def _declaration(tmp_path, **overrides):
    path = tmp_path / "adapter.md"
    path.write_text("name: an-adapter\n", encoding="utf-8")
    fields = dict(
        id="an-adapter", locator=str(path),
        digest=adapter_pin.file_digest(path),
    )
    fields.update(overrides)
    return adapter_pin.AdapterDeclaration(**fields)


def test_a_report_says_what_it_verified_rather_than_how_many_of_them(tmp_path):
    """`4 of 4` over four definition files read as a statement about four
    running things, and one of those was drifting."""
    report = adapter_pin.verify([_declaration(tmp_path)])
    assert report.clean
    rendered = report.render()
    assert "4 of 4" not in rendered
    assert "1 file(s), 0 executable(s)" in rendered
    assert "executable NOT verified (none declared): an-adapter" in rendered


def test_a_matching_executable_version_is_verified_and_counted(tmp_path):
    declaration = _declaration(
        tmp_path, executable=_sys.executable,
        version_command=(_sys.executable, "-c", "print('the-qualified-version')"),
        qualified_version="the-qualified-version",
    )
    report = adapter_pin.verify([declaration])
    assert report.clean
    assert report.executables_verified == ["an-adapter"]
    assert "1 file(s), 1 executable(s)" in report.render()


def test_a_drifted_executable_blocks_even_though_every_file_matches(tmp_path):
    """The reproduced defect, as an oracle. The digests are correct; the binary
    is not the one that was qualified."""
    declaration = _declaration(
        tmp_path, executable=_sys.executable,
        version_command=(_sys.executable, "-c", "print('cli 0.149.0')"),
        qualified_version="0.148.0",
    )
    report = adapter_pin.verify([declaration])
    assert not report.clean
    problem = str(report.findings[0])
    assert "0.149.0" in problem and "0.148.0" in problem
    assert "digest over a file says nothing about the binary" in problem


def test_a_version_command_that_cannot_run_blocks_rather_than_passes(tmp_path):
    """Nobody could ask, so nothing was established. An executable that could
    not be interrogated is not an executable that matched."""
    declaration = _declaration(
        tmp_path, executable="no-such-program-anywhere",
        version_command=("no-such-program-anywhere", "--version"),
        qualified_version="1.0",
    )
    report = adapter_pin.verify([declaration])
    assert not report.clean
    assert "could not be run" in str(report.findings[0])


def test_a_version_command_naming_a_program_the_radius_does_not_is_refused(tmp_path):
    """The launch goes through the declared blast radius, so an adapter cannot
    quietly cause an arbitrary program to run."""
    declaration = _declaration(
        tmp_path, executable="codex",
        version_command=("open", "-a", "Safari"),
        qualified_version="1.0",
    )
    report = adapter_pin.verify([declaration])
    assert not report.clean
    assert "could not be run" in str(report.findings[0])


def test_half_an_executable_qualification_is_refused_rather_than_ignored(tmp_path):
    """A version nothing knows how to obtain is a requirement the project
    believes is enforced and nothing checks."""
    with pytest.raises(_PreconditionError):
        _declaration(tmp_path, qualified_version="0.148.0")
    with pytest.raises(_PreconditionError):
        _declaration(tmp_path, executable="codex", qualified_version="0.148.0")


def test_the_three_fields_parse_from_a_declaration_block(tmp_path):
    path = tmp_path / "adapter.md"
    path.write_text("name: an-adapter\n", encoding="utf-8")
    declarations = adapter_pin.declarations_from([{
        "id": "an-adapter", "locator": str(path), "digest": adapter_pin.file_digest(path),
        "executable": "codex", "version_command": "codex --version",
        "qualified_version": "0.148.0",
    }])
    assert declarations[0].version_command == ("codex", "--version")
    assert declarations[0].qualified_version == "0.148.0"


def test_a_version_command_that_is_not_a_command_is_refused(tmp_path):
    path = tmp_path / "adapter.md"
    path.write_text("name: a\n", encoding="utf-8")
    base = {"id": "a", "locator": str(path), "digest": adapter_pin.file_digest(path),
            "executable": "codex", "qualified_version": "1"}
    for bad in ([], "", 7, ["codex", 3]):
        with pytest.raises(IntegrityError):
            adapter_pin.declarations_from([{**base, "version_command": bad}])


# --- a declared locator names a file in the PROJECT, not in the caller's cwd ----


def test_a_relative_adapter_locator_is_resolved_against_the_contract(tmp_path, monkeypatch):
    """REPRODUCED BEFORE THE REPAIR by an independent reader: a project declaring
    `locator: adapter.md` had its MODIFIED adapter verify successfully from
    another directory that happened to hold the previously qualified bytes.

    The oracle needs both directories, because a check run from the project's own
    directory is right either way — which is why every earlier test missed it.
    """
    import project_contract

    project = tmp_path / "proj"
    decoy = tmp_path / "somewhere-else"
    project.mkdir()
    decoy.mkdir()
    qualified = "name: w\n\nthe bytes this project qualified\n"
    (project / "adapter.md").write_text(qualified, encoding="utf-8")
    (decoy / "adapter.md").write_text(qualified, encoding="utf-8")
    digest = hashlib.sha256(qualified.encode()).hexdigest()
    (project / "PROJECT.yaml").write_text(
        'project:\n  name: p\n  repo_path: "."\n'
        'pack:\n  root_path: "/nowhere"\n'
        "adapters:\n  - id: w\n    locator: adapter.md\n"
        f"    digest: {digest}\n    required: true\n"
        "capabilities:\n  - id: C1\n", encoding="utf-8")

    contract = project_contract.ProjectContract.load(project / "PROJECT.yaml")
    monkeypatch.chdir(decoy)
    assert adapter_pin.verify_contract(contract).clean, (
        "the unmodified adapter did not verify, so this fixture cannot show the defect")

    # The PROJECT's adapter changes. The decoy keeps the qualified bytes.
    (project / "adapter.md").write_text("name: w\n\nEDITED AFTER QUALIFICATION\n",
                                        encoding="utf-8")
    report = adapter_pin.verify_contract(contract)
    assert not report.clean, (
        "a project's modified adapter verified from another directory holding the qualified "
        "bytes; the locator was resolved against the process rather than against the contract:\n"
        + report.render())


def test_an_absolute_adapter_locator_is_untouched(tmp_path):
    """The repair must not rewrite a declaration that already names a place."""
    installed = tmp_path / "installed" / "adapter.md"
    installed.parent.mkdir()
    installed.write_text("name: w\n\nbytes\n", encoding="utf-8")
    declaration = adapter_pin.AdapterDeclaration(
        id="w", locator=str(installed),
        digest=hashlib.sha256(installed.read_bytes()).hexdigest(), required=True)
    assert declaration.resolved(relative_to=tmp_path / "unrelated") == installed


def test_the_version_command_runs_in_the_project_and_not_in_the_callers_directory(
        tmp_path, monkeypatch):
    """THE REPAIR OF THE LOCATOR MADE THIS NEWLY REACHABLE, which is why it is
    pinned here rather than assumed.

    Before the locator was resolved against the contract, a verification run from
    another directory failed on the missing definition FILE first. With the file
    half repaired, the executable half still inherited the process's directory —
    so a project's own `adapter.md` could be combined with a DECOY directory's
    `./tool`, and the report said one file and one executable verified. Found by
    a bounded reading of that repair.
    """
    import project_contract

    project = tmp_path / "proj"
    decoy = tmp_path / "decoy"
    project.mkdir()
    decoy.mkdir()
    definition = "name: w\n\nthe qualified definition\n"
    (project / "adapter.md").write_text(definition, encoding="utf-8")
    for root, version in ((project, "9.0"), (decoy, "1.0")):
        tool = root / "tool"
        tool.write_text(f"#!/bin/sh\necho tool {version}\n", encoding="utf-8")
        tool.chmod(0o755)

    (project / "PROJECT.yaml").write_text(
        'project:\n  name: p\n  repo_path: "."\n'
        'pack:\n  root_path: "/nowhere"\n'
        "adapters:\n  - id: w\n    locator: adapter.md\n"
        f"    digest: {hashlib.sha256(definition.encode()).hexdigest()}\n"
        "    required: true\n"
        "    executable: ./tool\n"
        "    version_command: ./tool --version\n"
        "    qualified_version: 1.0\n"
        "capabilities:\n  - id: C1\n", encoding="utf-8")

    contract = project_contract.ProjectContract.load(project / "PROJECT.yaml")

    monkeypatch.chdir(decoy)
    report = adapter_pin.verify_contract(contract)
    assert not report.clean, (
        "the project's own definition file was combined with the DECOY directory's "
        f"executable and the report was clean:\n{report.render()}")
    assert any("9.0" in finding.sentence() if hasattr(finding, "sentence") else "9.0" in str(finding)
               for finding in report.findings), (
        f"the refusal does not name the version the PROJECT's tool actually reports:\n"
        f"{report.render()}")

    # And from the project itself, the same declaration must still refuse — the
    # project's tool is 9.0 and it qualified against 1.0. A fixture that passed
    # here would be testing the directory rather than the version.
    monkeypatch.chdir(project)
    assert not adapter_pin.verify_contract(contract).clean


def test_a_matching_executable_in_the_project_verifies(tmp_path, monkeypatch):
    """The positive case, so the test above cannot pass by refusing everything."""
    import project_contract

    project = tmp_path / "proj"
    elsewhere = tmp_path / "elsewhere"
    project.mkdir()
    elsewhere.mkdir()
    definition = "name: w\n\nthe qualified definition\n"
    (project / "adapter.md").write_text(definition, encoding="utf-8")
    tool = project / "tool"
    tool.write_text("#!/bin/sh\necho tool 1.0\n", encoding="utf-8")
    tool.chmod(0o755)
    (project / "PROJECT.yaml").write_text(
        'project:\n  name: p\n  repo_path: "."\n'
        'pack:\n  root_path: "/nowhere"\n'
        "adapters:\n  - id: w\n    locator: adapter.md\n"
        f"    digest: {hashlib.sha256(definition.encode()).hexdigest()}\n"
        "    required: true\n"
        "    executable: ./tool\n"
        "    version_command: ./tool --version\n"
        "    qualified_version: 1.0\n"
        "capabilities:\n  - id: C1\n", encoding="utf-8")

    contract = project_contract.ProjectContract.load(project / "PROJECT.yaml")
    monkeypatch.chdir(elsewhere)
    report = adapter_pin.verify_contract(contract)
    assert report.clean, report.render()
    assert report.executables_verified == ["w"], report.render()
