"""A closure that omits a profile, and a decision resting on a stale figure.

Rehearsal B4 and B5. The assertion that matters in the first is not that a
failing gate is caught — that was already true — but that **omission is
impossible**, because the generator iterates the contract's declarations rather
than the results somebody chose to record.
"""

import sys

import pytest

import close_attestation
from close_attestation import (
    Attestation,
    Premise,
    ProfileOutcome,
    ProfileState,
    attest,
    close_gate,
    re_derive,
)
from errors import IntegrityError, PreconditionError

DECLARED = ("focused", "integration", "full")
CANDIDATE = dict(head_revision="a" * 40, tree_digest="b" * 64)


def _passed(name):
    return ProfileOutcome(profile=name, state=ProfileState.PASSED, exit_status=0)


def _attest(capability, declared, results, **kwargs):
    return attest(capability, declared, results, **{**CANDIDATE, **kwargs})


# --- omission is unrepresentable ------------------------------------------------


def test_a_profile_that_was_never_run_is_enumerated_and_reported_unrun():
    """The whole mechanism. A closure that simply does not mention a profile is
    what let two capabilities close green over red gates."""
    attestation = attest("CAP-1", DECLARED, {"focused": _passed("focused")}, **CANDIDATE)

    assert [o.profile for o in attestation.outcomes] == list(DECLARED)
    assert {o.profile for o in attestation.unrun} == {"integration", "full"}
    assert "UNRUN" in attestation.render()


def test_the_generator_iterates_the_declarations_and_not_the_results():
    """Asserted structurally: with no results at all, every declared profile
    still appears. A generator walking the results could only describe what
    somebody chose to record."""
    attestation = attest("CAP-1", DECLARED, {}, **CANDIDATE)
    assert len(attestation.outcomes) == len(DECLARED)
    assert all(o.state == ProfileState.UNRUN for o in attestation.outcomes)


def test_a_result_for_a_profile_the_contract_does_not_declare_is_refused():
    """The attestation and the contract disagree about what this project
    validates, and the contract is the authority."""
    with pytest.raises(PreconditionError) as caught:
        attest("CAP-1", DECLARED, {"invented": _passed("invented")}, **CANDIDATE)
    assert "invented" in caught.value.render()


def test_a_contract_declaring_no_profiles_has_nothing_to_attest_to():
    with pytest.raises(PreconditionError):
        attest("CAP-1", (), {}, **CANDIDATE)


# --- what stops a close ------------------------------------------------------------


def test_an_unrun_profile_stops_a_close_by_default():
    """D24: refusing on UNRUN is the project's declared policy, and it defaults
    to refusing."""
    attestation = attest("CAP-1", DECLARED, {"focused": _passed("focused")}, **CANDIDATE)
    assert attestation.refuses_on_unrun
    assert attestation.blocking
    assert close_gate(attestation)


def test_a_project_may_declare_that_an_unrun_profile_does_not_stop_it():
    """And the profiles are still enumerated. The obligation that is
    unconditional is that a step nobody ran must not be indistinguishable
    afterwards from a step that passed — not that every project must run
    everything."""
    attestation = attest("CAP-1", DECLARED, {"focused": _passed("focused")},
                         refuses_on_unrun=False, **CANDIDATE)
    assert not attestation.blocking
    assert attestation.unrun, "the profiles are still enumerated"
    assert "UNRUN" in attestation.render()
    assert "must not be indistinguishable" in attestation.render()


def test_a_failed_or_incomplete_profile_stops_a_close_whatever_the_policy_says():
    """The declared policy governs absence, and nothing else. An interrupted
    run did not pass and did not fail: it did not finish."""
    for state in (ProfileState.FAILED, ProfileState.INCOMPLETE):
        results = {name: _passed(name) for name in DECLARED}
        results["full"] = ProfileOutcome(
            profile="full", state=state, exit_status=1 if state == ProfileState.FAILED else None)
        attestation = attest("CAP-1", DECLARED, results, refuses_on_unrun=False, **CANDIDATE)
        assert attestation.blocking, state


def test_every_profile_clean_closes():
    attestation = attest("CAP-1", DECLARED, {name: _passed(name) for name in DECLARED},
                         **CANDIDATE)
    assert close_gate(attestation) == []
    assert "every declared profile ran clean" in attestation.render()


def test_the_attestation_carries_the_candidate_it_was_taken_against():
    """A capability's commits invalidate an earlier capability's evidence, and a
    record that does not carry its tree cannot be told apart from one that
    does."""
    attestation = attest("CAP-1", DECLARED, {}, **CANDIDATE)
    assert CANDIDATE["head_revision"][:12] in attestation.render()
    assert CANDIDATE["tree_digest"][:12] in attestation.render()


def test_an_unknown_profile_state_is_refused_by_name():
    with pytest.raises(IntegrityError) as caught:
        ProfileOutcome(profile="focused", state="probably fine")
    assert "UNRUN" in caught.value.render()


# --- the premise under a decision ----------------------------------------------------


def _premise(measured, command):
    return Premise(decision="whether to accept the limitation", measured=measured, command=command)


def test_a_premise_that_still_reproduces_is_clean():
    outcome = re_derive(_premise("42", (sys.executable, "-c", "print('42')")))
    assert outcome.reproduced is True
    assert "still reproduces" in str(outcome)


def test_a_premise_that_no_longer_reproduces_names_the_decision_rather_than_the_check():
    """Not *a check failed*. The finding is that a person's ruling now rests on
    nothing, and that is the thing they have to be asked about again."""
    outcome = re_derive(_premise("42", (sys.executable, "-c", "print('415')")))
    assert outcome.reproduced is False
    rendered = str(outcome)
    assert "whether to accept the limitation" in rendered
    assert "RESTS ON A PREMISE THAT NO LONGER REPRODUCES" in rendered
    assert "Put the decision to a person again" in rendered


def test_a_premise_that_cannot_be_re_derived_is_neither_clean_nor_broken():
    outcome = re_derive(_premise("42", ("no-such-program-at-all", "--x")))
    assert outcome.reproduced is None
    assert "COULD NOT BE RE-DERIVED" in str(outcome)


def test_a_premise_that_could_not_be_re_derived_still_stops_the_close():
    """Nobody established it, which is not the same as it holding."""
    attestation = attest("CAP-1", DECLARED, {name: _passed(name) for name in DECLARED},
                         **CANDIDATE)
    unknown = re_derive(_premise("42", ("no-such-program-at-all",)))
    assert close_gate(attestation, [unknown])


def test_a_decision_with_no_command_to_reproduce_it_is_refused():
    """A figure with no way to obtain it again is exactly the figure that
    decayed."""
    with pytest.raises(PreconditionError):
        Premise(decision="a ruling", measured="42", command=())
    with pytest.raises(IntegrityError):
        Premise(decision="  ", measured="42", command=("echo", "42"))


def test_the_launch_radius_is_derived_from_the_command_the_premise_declares(monkeypatch):
    """A decision record cannot name one program and cause another to run.

    Observed rather than asserted about: the radius is captured at the call, and
    the first version of this test compared a set literal with itself, which is
    the decoration this release spends its time deleting.
    """
    captured = {}

    def _capture(command, *, radius, **kwargs):
        captured["command"] = list(command)
        captured["radius"] = radius
        raise OSError("not actually run")

    monkeypatch.setattr(close_attestation.instrument, "launch", _capture)
    outcome = re_derive(Premise(decision="a ruling", measured="x", command=("echo", "x")))

    assert captured["command"] == ["echo", "x"]
    assert captured["radius"].launches == ("echo",)
    assert not captured["radius"].permits_launch("open")
    assert "a ruling" in captured["radius"].because
    assert outcome.reproduced is None


def test_the_close_gate_is_clean_only_when_both_halves_are():
    attestation = attest("CAP-1", DECLARED, {name: _passed(name) for name in DECLARED},
                         **CANDIDATE)
    good = re_derive(_premise("42", (sys.executable, "-c", "print('42')")))
    assert close_gate(attestation, [good]) == []

    stale = re_derive(_premise("42", (sys.executable, "-c", "print('415')")))
    assert close_gate(attestation, [stale])


# --- the command line -----------------------------------------------------------------


def test_the_cli_enumerates_the_contracts_profiles_and_exits_on_the_verdict(tmp_path, capsys):
    contract = tmp_path / "PROJECT.yaml"
    contract.write_text(
        "project:\n  repo_path: .\n"
        "validation_profiles:\n"
        "  focused:\n    command: pytest -q\n"
        "  full:\n    command: pytest\n"
    )
    base = ["CAP-1", "--project", str(contract), "--head", "a" * 40, "--tree-digest", "b" * 64]

    assert close_attestation._cli(base + ["--result", "focused=0"]) == 1
    out = capsys.readouterr().out
    assert "full: UNRUN" in out and "focused: PASSED" in out

    assert close_attestation._cli(base + ["--result", "focused=0", "--result", "full=0"]) == 0
    assert "every declared profile ran clean" in capsys.readouterr().out

    # A non-zero status is a failure however the caller would prefer to label it.
    assert close_attestation._cli(base + ["--result", "focused=1", "--result", "full=0"]) == 1
    assert "focused: FAILED (exit 1)" in capsys.readouterr().out

    # And a result with no status at all is refused rather than assumed clean.
    assert close_attestation._cli(base + ["--result", "focused"]) == 2
    assert "an assertion rather than a reading" in capsys.readouterr().out


def test_the_cli_refuses_a_contract_that_declares_no_profiles(tmp_path, capsys):
    contract = tmp_path / "PROJECT.yaml"
    contract.write_text("project:\n  repo_path: .\n")
    status = close_attestation._cli(
        ["CAP-1", "--project", str(contract), "--head", "a" * 40, "--tree-digest", "b" * 64])
    assert status == 2 and "REFUSED" in capsys.readouterr().out
