"""Which gates ran, answered by something other than the party that ran them.

A closure record's gate block was prose. Somebody wrote down which checks had
passed, and nothing compared that sentence to anything — so two capabilities
closed green over red gates, and a profile that was never run and a profile that
passed left the record looking identical.

**The generator enumerates the contract's declared profiles, not the results.**
That is the whole mechanism and the reason it cannot be got around: a profile
the project declared and never ran is *enumerated and reported `UNRUN`*, because
the list being iterated is the declaration. Omission is not something an author
has to remember to avoid; it is unrepresentable.

`DECISIONS.md` D24 decides what follows from that:

*   **Generating the attestation is mandatory**, because no adopting project can
    fail to do it — the input is the `validation_profiles` block the contract
    already carries, so the generator always has what it needs.
*   **Refusing to close over an `UNRUN` profile is the project's declared
    policy, and it defaults to refusing.** A project that must close over a
    profile it cannot run says so once, in its contract, where a reader can see
    it — rather than by the attestation quietly not mentioning it.

## A figure inside a human decision decays into human authority

Separately measured, and worse than an ordinary stale number: a decision record
carried a measurement, a later commit falsified it, and the ruling a person had
made on that measurement went on standing. Nothing downstream questions a human
decision, which is exactly why the premise underneath one has to be re-derived
rather than re-read.

So a decision may declare the **command that produces its premise**, and closing
re-runs it. A premise that no longer reproduces does not report *a check
failed*: it **names the decision that now rests on nothing**, because that is
the thing a person has to be asked about again.

This strengthens human authority rather than automating it. Nothing here decides
anything; it establishes that a decision is being taken on a premise that still
holds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import instrument
from errors import IntegrityError, PreconditionError
from instrument import Examined

__all__ = [
    "ProfileState",
    "ProfileOutcome",
    "Attestation",
    "attest",
    "Premise",
    "PremiseOutcome",
    "re_derive",
    "close_gate",
]


class ProfileState:
    #: The profile ran and its checker exited zero.
    PASSED = "PASSED"
    #: The profile ran and its checker did not exit zero.
    FAILED = "FAILED"
    #: The profile ran and did not finish — a limit, a transport, a quota. Not
    #: a pass and not a failure, and collapsing it into either is how an
    #: interrupted run becomes a clean one.
    INCOMPLETE = "INCOMPLETE"
    #: **Declared and never run.** The state the prose form could not express.
    UNRUN = "UNRUN"

    ALL = (PASSED, FAILED, INCOMPLETE, UNRUN)
    #: What stops a close unless the project has declared otherwise.
    NOT_CLEAN = (FAILED, INCOMPLETE, UNRUN)


@dataclass(frozen=True)
class ProfileOutcome:
    """What happened to one declared validation profile."""

    profile: str
    state: str
    command: str = ""
    exit_status: int | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if self.state not in ProfileState.ALL:
            raise IntegrityError("no such profile state", found=repr(self.state),
                                 known=", ".join(ProfileState.ALL))

    def __str__(self) -> str:
        status = "" if self.exit_status is None else f" (exit {self.exit_status})"
        return f"{self.profile}: {self.state}{status}" + (f" — {self.detail}" if self.detail else "")


@dataclass(frozen=True)
class Attestation:
    """Generated. Never authored.

    Bound to an exact candidate, because a profile that passed against a
    different tree says nothing about this one — a capability's commits
    invalidate an earlier capability's evidence, and a record that does not
    carry the tree it was taken against cannot be told apart from one that does.
    """

    capability: str
    head_revision: str
    tree_digest: str
    outcomes: tuple[ProfileOutcome, ...]
    #: The project's declared policy. `True` — the default — means an `UNRUN`
    #: profile stops the close.
    refuses_on_unrun: bool = True

    @property
    def examined(self) -> Examined:
        return Examined({"declared profiles": len(self.outcomes)})

    @property
    def unrun(self) -> tuple[ProfileOutcome, ...]:
        return tuple(o for o in self.outcomes if o.state == ProfileState.UNRUN)

    @property
    def blocking(self) -> tuple[ProfileOutcome, ...]:
        blocking = [o for o in self.outcomes
                    if o.state in (ProfileState.FAILED, ProfileState.INCOMPLETE)]
        if self.refuses_on_unrun:
            blocking.extend(self.unrun)
        return tuple(blocking)

    def render(self) -> str:
        examined = self.examined
        verdict = examined.verdict_or_nothing(
            "every declared profile ran clean" if not self.blocking
            else f"{len(self.blocking)} declared profile(s) do not close")
        lines = [f"close attestation for {self.capability}: {verdict}",
                 f"  candidate: {self.head_revision[:12]} tree {self.tree_digest[:12]}",
                 f"  examined: {examined.summary()}"]
        lines.extend(f"  {outcome}" for outcome in self.outcomes)
        if self.unrun and not self.refuses_on_unrun:
            lines.append(
                "  the project declares that an UNRUN profile does not stop a close; the profiles "
                "above are still enumerated, because a step nobody ran must not be "
                "indistinguishable afterwards from a step that passed"
            )
        return "\n".join(lines)


def attest(
    capability: str,
    declared_profiles: list[str] | tuple[str, ...],
    results: dict[str, ProfileOutcome],
    *,
    head_revision: str,
    tree_digest: str,
    refuses_on_unrun: bool = True,
) -> Attestation:
    """Enumerate what the contract declared, and say what became of each.

    Iterating the **declarations** rather than the results is the mechanism. A
    generator that walked the results could only ever describe what somebody
    chose to record, which is the prose form with extra steps.

    A result for a profile the contract does not declare is a refusal rather
    than an extra line: it means the attestation and the contract disagree about
    what this project validates, and the contract is the authority.
    """
    if not declared_profiles:
        raise PreconditionError(
            "a close attestation enumerates the contract's declared validation profiles, and "
            "this contract declares none; there is nothing to attest to",
            capability=capability,
        )
    undeclared = sorted(set(results) - set(declared_profiles))
    if undeclared:
        raise PreconditionError(
            "a result was supplied for a profile the contract does not declare; the contract is "
            "the authority on what this project validates",
            capability=capability, undeclared=", ".join(undeclared),
            declared=", ".join(declared_profiles),
        )
    outcomes = tuple(
        results.get(name, ProfileOutcome(
            profile=name, state=ProfileState.UNRUN,
            detail="declared by the contract and never run",
        ))
        for name in declared_profiles
    )
    return Attestation(
        capability=capability, head_revision=head_revision, tree_digest=tree_digest,
        outcomes=outcomes, refuses_on_unrun=refuses_on_unrun,
    )


# --- the premise under a decision ---------------------------------------------------


@dataclass(frozen=True)
class Premise:
    """A measurement a decision was taken on, and how to obtain it again.

    ``decision`` is required and is what the report names when the premise stops
    reproducing. *A check failed* is not the finding; *this decision now rests
    on nothing* is.
    """

    decision: str
    measured: str
    command: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("decision", "measured"):
            if not (getattr(self, name) or "").strip():
                raise IntegrityError(f"a premise states its {name}")
        if not self.command or not all(isinstance(word, str) and word for word in self.command):
            raise PreconditionError(
                "a premise declares the command that produces it; a figure with no way to obtain "
                "it again is exactly the figure that decayed",
                decision=self.decision,
            )


@dataclass(frozen=True)
class PremiseOutcome:
    premise: Premise
    reproduced: bool | None
    observed: str = ""
    detail: str = ""

    def __str__(self) -> str:
        if self.reproduced is None:
            return (f"the premise under {self.premise.decision!r} COULD NOT BE RE-DERIVED: "
                    f"{self.detail}")
        if self.reproduced:
            return f"the premise under {self.premise.decision!r} still reproduces"
        return (f"{self.premise.decision!r} RESTS ON A PREMISE THAT NO LONGER REPRODUCES: "
                f"recorded {self.premise.measured!r}, now {self.observed!r}. "
                f"Put the decision to a person again")


def re_derive(premise: Premise, *, cwd: str | Path = ".") -> PremiseOutcome:
    """Run the premise's own command and compare, or say it could not be run.

    Generated, never re-read. The launch goes through a blast radius built from
    the command the premise declares, so a decision record cannot cause an
    arbitrary program to run by naming one.
    """
    radius = instrument.BlastRadius(
        launches=(premise.command[0],),
        because=f"re-deriving the premise under {premise.decision!r} means obtaining it again",
    )
    try:
        result = instrument.launch(list(premise.command), radius=radius, cwd=str(cwd),
                                   capture_output=True, text=True, timeout=120)
    except Exception as exc:
        return PremiseOutcome(premise, None, detail=f"{type(exc).__name__}: {exc}")
    observed = (result.stdout or "").strip()
    return PremiseOutcome(
        premise, premise.measured.strip() in observed, observed=observed[:200])


def close_gate(
    attestation: Attestation, premises: list[PremiseOutcome] | tuple[PremiseOutcome, ...] = ()
) -> list[str]:
    """Every reason this capability does not close. Empty is the clean answer."""
    problems = [str(outcome) for outcome in attestation.blocking]
    problems.extend(
        str(outcome) for outcome in premises if outcome.reproduced is not True
    )
    return problems


def _cli(argv: list[str]) -> int:
    """Generate a close attestation from a contract and the results in hand.

    Usage: ``close_attestation.py CAPABILITY --project PATH --head REV
                                  --tree-digest DIGEST
                                  [--passed PROFILE ...] [--failed PROFILE ...]
                                  [--incomplete PROFILE ...]``

    Every profile the contract declares appears, whether or not a result was
    supplied. Exit status: ``0`` closes, ``1`` does not, ``2`` the contract
    could not be read or declares no profiles.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="close_attestation.py",
        description="Enumerate every declared validation profile and say what became of each.")
    parser.add_argument("capability")
    parser.add_argument("--project", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--tree-digest", required=True)
    parser.add_argument("--passed", action="append", default=[], metavar="PROFILE")
    parser.add_argument("--failed", action="append", default=[], metavar="PROFILE")
    parser.add_argument("--incomplete", action="append", default=[], metavar="PROFILE")
    args = parser.parse_args(argv)

    from project_contract import ContractError, ProjectContract

    try:
        contract = ProjectContract.load(args.project)
    except ContractError as exc:
        print(f"CONTRACT UNREADABLE {exc}")
        return 2

    profiles = list((contract.raw.get("validation_profiles") or {}))
    results: dict[str, ProfileOutcome] = {}
    for names, state in ((args.passed, ProfileState.PASSED),
                         (args.failed, ProfileState.FAILED),
                         (args.incomplete, ProfileState.INCOMPLETE)):
        for name in names:
            results[name] = ProfileOutcome(profile=name, state=state)

    try:
        attestation = attest(
            args.capability, profiles, results,
            head_revision=args.head, tree_digest=args.tree_digest,
            refuses_on_unrun=bool((contract.raw.get("closure") or {}).get("refuses_on_unrun", True)),
        )
    except PreconditionError as exc:
        print(f"REFUSED {exc.render()}")
        return 2

    print(attestation.render())
    return 1 if attestation.blocking else 0


if __name__ == "__main__":
    import sys

    # Run the module, not a second copy of it. A file executed as a script is
    # `__main__`, and a sibling that imports it BY NAME gets a separate module
    # object with separate class objects — so an `isinstance` check across that
    # boundary is False for an object that is exactly that class. Imported
    # statically, by name, because a dynamic import would route around the
    # toolbelt's import-closure check.
    from errors import run_cli
    from close_attestation import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
