"""The facts an instrument must state about itself, and the cases it refuses.

Every test here has a fixture on which the guard must go red. A guard with no
such fixture is the artifact this module exists to prevent.
"""

import hashlib
import subprocess
import sys

import pytest

import instrument
from errors import GateRefusal, IntegrityError, PreconditionError


# --- modes ---------------------------------------------------------------------


def _two_modes():
    return instrument.ModeSet([
        instrument.Mode("tiered", "bare common words are not applied to blob content"),
        instrument.Mode("strict", "every rule applies to every surface"),
    ])


def test_a_mode_set_of_one_is_refused():
    """A single mode has no reader problem, so declaring one is decoration.

    The announcement exists because a reader cannot otherwise tell which of
    several answers they are looking at.
    """
    with pytest.raises(IntegrityError):
        instrument.ModeSet([instrument.Mode("only", "the one rule set")])


def test_a_mode_must_say_what_it_does_differently():
    with pytest.raises(IntegrityError):
        instrument.Mode("strict", "")
    with pytest.raises(IntegrityError):
        instrument.Mode("  ", "applies everything")


def test_two_modes_may_not_share_a_name():
    with pytest.raises(IntegrityError):
        instrument.ModeSet([
            instrument.Mode("strict", "one thing"),
            instrument.Mode("strict", "another thing"),
        ])


def test_the_mode_is_inside_the_headline_and_before_the_verdict():
    """Not appended after the verdict, and not on a provenance line below it.

    A reader who takes one line from a stored report takes the first one, and
    the measured failure is a leak count quoted out of a headline that did not
    carry its tier. Position is the whole control, so it is asserted.
    """
    headline = _two_modes().headline("outgoing range ROOT..HEAD", "clean", "tiered")
    assert headline == "outgoing range ROOT..HEAD [tiered]: clean"
    assert headline.index("[tiered]") < headline.index("clean")


def test_a_mode_the_set_does_not_declare_is_refused_by_name():
    with pytest.raises(IntegrityError) as caught:
        _two_modes().headline("subject", "clean", "lenient")
    assert "strict" in caught.value.render() and "tiered" in caught.value.render()


# --- what was examined -----------------------------------------------------------


def test_nothing_examined_is_not_a_clean_verdict():
    """The case that reads identically to a pass and is not one."""
    empty = instrument.Examined({"commits": 0, "blobs": 0})
    assert empty.nothing
    assert empty.verdict_or_nothing("clean") == instrument.NOTHING_EXAMINED


def test_a_verdict_stands_once_anything_was_examined():
    """The other half, and the reason this is not simply a refusal.

    A guard that refused every empty count would refuse correct work — a range
    with one commit and no blobs is a real observation.
    """
    seen = instrument.Examined({"commits": 1, "blobs": 0})
    assert not seen.nothing
    assert seen.verdict_or_nothing("clean") == "clean"


def test_a_count_that_is_not_a_count_is_refused():
    for bad in (-1, True, "3", 1.0):
        with pytest.raises(IntegrityError):
            instrument.Examined({"blobs": bad})


def test_the_summary_names_the_unit_of_every_count():
    assert instrument.Examined({"commits": 2, "blobs": 9}).summary() == "2 commits, 9 blobs"


# --- where a rule came from --------------------------------------------------------


@pytest.fixture
def rule_tree(tmp_path):
    """A canonical rule under a root, and a divergent copy outside it."""
    root = tmp_path / "pack"
    (root / "policy").mkdir(parents=True)
    canonical = root / "policy" / "rules.json"
    canonical.write_text('{"terms": ["canonical"]}', encoding="utf-8")
    stale = tmp_path / "project" / "rules.json"
    stale.parent.mkdir()
    stale.write_text('{"terms": ["stale"]}', encoding="utf-8")
    return root, canonical, stale


def test_a_search_order_that_lands_outside_the_declared_root_is_refused(rule_tree):
    """The reproduced defect: the canonical file is absent, so the next
    candidate wins silently and its rules are applied as though they were the
    pinned ones."""
    root, canonical, stale = rule_tree
    canonical.unlink()
    with pytest.raises(PreconditionError) as caught:
        instrument.read_rule([canonical, stale], canonical_root=root, what="rule set")
    rendered = caught.value.render()
    assert str(stale.resolve()) in rendered, "the refusal must name what it refused to use"
    assert str(root.resolve()) in rendered, "and the root it was measured against"
    assert str(canonical) in rendered, "and what else was on the path"


def test_the_canonical_file_wins_and_carries_its_digest(rule_tree):
    root, canonical, stale = rule_tree
    content, source = instrument.read_rule([canonical, stale], canonical_root=root, what="rule set")
    assert content == canonical.read_bytes()
    assert source.how == "canonical" and source.canonical
    assert source.digest == hashlib.sha256(canonical.read_bytes()).hexdigest()
    assert source.summary().startswith(str(canonical.resolve()))


def test_one_declared_location_is_not_a_substitution_and_is_not_refused(rule_tree):
    """The guard against refusing correct work.

    A project that names exactly one file has not been substituted against: it
    asked for that file, the choice is visible in its own contract, and the
    source below carries the digest of what was read. `declared` and
    `canonical` are different answers and both are reported as themselves.
    """
    root, _canonical, stale = rule_tree
    content, source = instrument.read_rule([stale], canonical_root=root, what="rule set")
    assert content == stale.read_bytes()
    assert source.how == "declared" and source.canonical
    assert "declared" in source.summary()


def test_a_search_order_with_no_declared_root_is_reported_unrooted(rule_tree):
    root, canonical, stale = rule_tree
    _content, source = instrument.read_rule([canonical, stale], canonical_root=None, what="rule set")
    assert source.how == "unrooted" and not source.canonical


def test_a_rule_that_exists_nowhere_names_everywhere_it_looked(rule_tree):
    root, canonical, stale = rule_tree
    canonical.unlink()
    stale.unlink()
    with pytest.raises(PreconditionError) as caught:
        instrument.read_rule([canonical, stale], canonical_root=root, what="rule set")
    assert str(canonical) in caught.value.render() and str(stale) in caught.value.render()


def test_no_candidate_at_all_is_a_refusal_rather_than_a_pass():
    with pytest.raises(IntegrityError):
        instrument.read_rule([], canonical_root=None)


# --- equivalence --------------------------------------------------------------------


def test_an_equivalence_gate_without_a_layer_on_each_side_is_refused():
    with pytest.raises(IntegrityError):
        instrument.EquivalenceLayers(left="parsed AST", right="")
    with pytest.raises(IntegrityError):
        instrument.EquivalenceLayers(left="   ", right="parsed AST")


def test_the_summary_states_both_the_layer_and_what_it_never_reaches():
    layers = instrument.EquivalenceLayers(
        left="decoded arguments", right="decoded arguments",
        not_compared=("the decoders themselves",),
    )
    summary = layers.summary()
    assert "compared at: decoded arguments" in summary
    assert "NOT compared: the decoders themselves" in summary


def test_two_different_layers_are_reported_separately_rather_than_collapsed():
    """The measured shape: one side entered above the other."""
    summary = instrument.EquivalenceLayers(left="raw request text", right="decoded arguments").summary()
    assert "left raw request text" in summary and "right decoded arguments" in summary


# --- blast radius --------------------------------------------------------------------


def test_a_radius_that_writes_or_launches_states_why():
    with pytest.raises(IntegrityError):
        instrument.BlastRadius(launches=("git",))
    with pytest.raises(IntegrityError):
        instrument.BlastRadius(writes=("/tmp/out",), because="   ")
    # Reading alone needs no justification, and requiring one would make the
    # declaration ceremony on the tools that need it least.
    assert instrument.BlastRadius(reads=("a repository",)).summary().startswith("reads: a repository")


def test_launching_an_undeclared_program_is_refused_by_name():
    radius = instrument.BlastRadius(launches=("git",), because="every read here is a git invocation")
    with pytest.raises(GateRefusal) as caught:
        instrument.launch(["open", "-a", "Safari"], radius=radius)
    rendered = caught.value.render()
    assert "open" in rendered and "git" in rendered


def test_a_declared_program_runs_and_is_matched_by_basename():
    """A declaration naming `git` and an invocation resolving through PATH are
    the same act; refusing one and allowing the other teaches callers to route
    around the control."""
    radius = instrument.BlastRadius(launches=("git",), because="a test invocation")
    result = instrument.launch(
        [sys.executable, "-c", "print('ran')"],
        radius=instrument.BlastRadius(launches=(sys.executable,), because="a test invocation"),
        capture_output=True, text=True,
    )
    assert result.stdout.strip() == "ran"
    assert radius.permits_launch("/usr/local/bin/git")
    assert not radius.permits_launch("gitk")


def test_an_empty_command_is_refused():
    with pytest.raises(IntegrityError):
        instrument.launch([], radius=instrument.BlastRadius(launches=("git",), because="x"))


# --- the toolbelt's own launch surface -------------------------------------------------


def test_the_read_only_git_layer_declares_git_and_nothing_else():
    """The toolbelt's entire launch surface, asserted rather than described.

    Every read in this toolbelt is a Git invocation through one function, so
    this declaration is the whole of what the pack can start.
    """
    import gitread

    assert gitread.BLAST_RADIUS.launches == ("git",)
    assert gitread.BLAST_RADIUS.because
    assert not gitread.BLAST_RADIUS.writes, "a read-only layer that declares a write is not read-only"
