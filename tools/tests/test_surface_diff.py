"""surface_diff: what it catches, and the documented gap it honestly does not."""

import subprocess

import pytest

import surface_diff


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)


def _head(repo):
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    directory = tmp_path / "throwaway"
    directory.mkdir()
    _git(directory, "init", "--quiet", "--initial-branch", "main")
    _git(directory, "config", "user.name", "Throwaway Tester")
    _git(directory, "config", "user.email", "tester@example.invalid")
    _git(directory, "config", "commit.gpgsign", "false")
    return directory


def test_added_public_name_detected():
    before = surface_diff.surface("def existing(): pass\n", "mod")
    after = surface_diff.surface("def existing(): pass\ndef added(): pass\n", "mod")
    changes = surface_diff.compare(before, after)
    kinds = {(c.kind, c.name) for c in changes}
    assert ("added_public_name", "mod.added") in kinds


def test_removed_public_name_detected():
    before = surface_diff.surface("def gone(): pass\n", "mod")
    after = surface_diff.surface("", "mod")
    changes = surface_diff.compare(before, after)
    kinds = {(c.kind, c.name) for c in changes}
    assert ("removed_public_name", "mod.gone") in kinds


def test_changed_signature_detected():
    before = surface_diff.surface("def f(a, b): pass\n", "mod")
    after = surface_diff.surface("def f(a, *, b): pass\n", "mod")
    changes = surface_diff.compare(before, after)
    kinds = {c.kind for c in changes}
    assert "changed_signature" in kinds


def test_private_name_exported_across_module_boundary_detected():
    before = surface_diff.surface("import os\n", "mod")
    after = surface_diff.surface("from other import _private_helper\n", "mod")
    changes = surface_diff.compare(before, after)
    kinds = {(c.kind, c.name) for c in changes}
    assert ("private_name_exported", "other._private_helper") in kinds


def test_reformatted_annotation_is_not_a_change():
    before = surface_diff.surface('def f(x: "int|None") -> None: pass\n', "mod")
    after = surface_diff.surface("def f(x: int | None) -> None: pass\n", "mod")
    changes = surface_diff.compare(before, after)
    assert changes == []


def test_documented_gap_dataclass_field_change_is_not_detected():
    """Honesty pin: a change confined to a dataclass field is invisible here.

    The module docstring and --help both say class attributes and dataclass
    field types are not compared. This test exists so that gap cannot regress
    silently into being described as fixed when it is not: if this ever starts
    failing, `compare` began detecting field changes and the docstring/--help
    claim must be corrected, not this test.
    """
    before = surface_diff.surface(
        "from dataclasses import dataclass\n\n"
        "@dataclass\n"
        "class Point:\n"
        "    x: int\n"
        "    y: int\n",
        "mod",
    )
    after = surface_diff.surface(
        "from dataclasses import dataclass\n\n"
        "@dataclass\n"
        "class Point:\n"
        "    x: int\n"
        "    y: str\n"  # field type changed, and a field was effectively renamed in shape
        "    z: int\n",
        "mod",
    )
    changes = surface_diff.compare(before, after)
    assert changes == []


def test_diff_refs_over_a_real_repo_detects_growth_and_relocation(repo):
    (repo / "a.py").write_text("def keep(): pass\n\n\ndef will_move(): pass\n")
    (repo / "b.py").write_text("")
    _git(repo, "add", "a.py", "b.py")
    _git(repo, "commit", "--quiet", "-m", "first commit")
    before_ref = _head(repo)

    (repo / "a.py").write_text("def keep(): pass\n\n\ndef added(): pass\n")
    (repo / "b.py").write_text("def will_move(): pass\n")
    _git(repo, "add", "a.py", "b.py")
    _git(repo, "commit", "--quiet", "-m", "second commit")
    after_ref = _head(repo)

    changes_by_module, relocations = surface_diff.diff_refs(repo, before_ref, after_ref)

    a_changes = {(c.kind, c.name) for c in changes_by_module.get("a.py", [])}
    assert ("added_public_name", "a.added") in a_changes

    assert ("will_move", "a.py", "b.py") in relocations


# --- the layer this equivalence gate enters each path at ----------------------
#
# The class: a parity gate compared two transports' already-decoded arguments,
# passed, and was structurally unable to see that the two decoders disagreed
# about what the same request text meant. One request, two answers, in the
# capability whose subject was parity. The gap is not the defect; the gap being
# invisible in the gate's own output is.


def test_the_report_names_the_layer_on_a_clean_run(repo, capsys):
    """A reader who has just been told `clean` is the one who most needs to know
    what was never looked at. Before RP2.3 the gap lived in `--help` and in a
    module docstring, neither of which is stored beside the verdict."""
    (repo / "mod.py").write_text("def stable(): pass\n")
    _git(repo, "add", "mod.py")
    _git(repo, "commit", "--quiet", "-m", "first")
    first = _head(repo)
    (repo / "mod.py").write_text("def stable(): pass\n# a comment changes nothing\n")
    _git(repo, "commit", "--quiet", "-a", "-m", "second")

    assert surface_diff._cli([str(repo), first, _head(repo)]) == 0
    out = capsys.readouterr().out
    assert "clean: no public-surface changes" in out
    assert "compared at:" in out
    assert "NOT compared: class-level attributes and dataclass field types" in out


def test_the_declared_layers_are_well_formed():
    """A side with no layer named is refused at construction, so the constant
    below cannot silently lose half of its statement."""
    assert surface_diff.LAYERS.left and surface_diff.LAYERS.right
    assert surface_diff.LAYERS.not_compared
    assert "AST" in surface_diff.LAYERS.left
