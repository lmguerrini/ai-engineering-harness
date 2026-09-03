"""A closure block generated from the contract, so a declared gate cannot be omitted.

**What this establishes and what it does not.** It does not run a profile,
launch a checker, or verify that a recorded outcome happened — the outcomes are
supplied by the caller, and a caller that records a falsehood records a
falsehood. What it makes impossible is **silence**: a profile the contract
declares and nobody mentions cannot be absent from the record, because the
record is built from the declaration and refuses to exist without covering all
of it. An earlier draft of this sentence promised independent verification of
what ran, which the mechanism does not provide.


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
        # `PASSED` is documented as *the profile ran and its checker exited
        # zero*, and the type accepted it with no exit status at all — so the
        # word meant only that somebody typed it. An auditor built a clean
        # attestation for three profiles that never ran.
        if self.state in (ProfileState.PASSED, ProfileState.FAILED) and self.exit_status is None:
            raise PreconditionError(
                f"{self.state} says a checker ran and reported; record the exit status it "
                "reported, or use INCOMPLETE for a run that did not finish and UNRUN for one "
                "that never started",
                profile=self.profile,
            )
        if self.state == ProfileState.PASSED and self.exit_status != 0:
            raise IntegrityError(
                "PASSED means the checker exited zero; a non-zero status recorded as a pass is "
                "the reinterpretation this pack's evidence layer makes unrepresentable",
                profile=self.profile, exit_status=self.exit_status,
            )

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
    #: What the contract declared. Carried on the record rather than only used
    #: by the generator, because the generator was the only thing enforcing the
    #: guarantee and this class is exported: an auditor built an `Attestation`
    #: directly, omitted a declared profile, and `close_gate` returned clean.
    declared: tuple[str, ...] = ()
    #: The project's declared policy. `True` — the default — means an `UNRUN`
    #: profile stops the close.
    refuses_on_unrun: bool = True

    def __post_init__(self) -> None:
        if not self.declared:
            raise PreconditionError(
                "an attestation carries the set of profiles the contract declared. Without it "
                "there is nothing for the outcomes to be complete against, and completeness is "
                "the only thing this record is for",
                capability=self.capability,
            )
        covered = [outcome.profile for outcome in self.outcomes]
        missing = [name for name in self.declared if name not in covered]
        if missing:
            raise PreconditionError(
                "these declared profiles have no outcome at all. An omission is not an UNRUN: "
                "UNRUN is a statement, and silence is the thing this record exists to make "
                "impossible",
                capability=self.capability, missing=", ".join(missing),
            )
        duplicated = sorted({name for name in covered if covered.count(name) > 1})
        if duplicated:
            raise PreconditionError(
                "a declared profile has more than one outcome. Two answers to one question is no "
                "answer, and the evidence count would overstate itself",
                capability=self.capability, duplicated=", ".join(duplicated),
            )
        stray = [name for name in covered if name not in self.declared]
        if stray:
            raise PreconditionError(
                "an outcome names a profile the contract does not declare; the contract is the "
                "authority on what this project validates",
                capability=self.capability, undeclared=", ".join(stray),
            )

    @property
    def examined(self) -> Examined:
        return Examined({"declared profiles": len(self.declared)})

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
        outcomes=outcomes, declared=tuple(declared_profiles),
        refuses_on_unrun=refuses_on_unrun,
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
    # Compared EXACTLY, not as a substring. `"10" in "100"` is true, so a
    # measurement that drifted from ten to a hundred reported as still
    # reproducing and the ruling resting on it stood. Found by an independent
    # auditor — and it is the same naive-substring defect this pack reproduced
    # and repaired in its own term scanner, made again one release later.
    return PremiseOutcome(
        premise, premise.measured.strip() == observed, observed=observed[:200])


#: Passed as `against` by a caller that genuinely cannot name the tree. Explicit
#: on purpose: the gap is then in the caller's code where a reader can see it,
#: rather than in an argument nobody passed.
UNSTATED = "IDENTITY-UNSTATED"


def close_gate(
    attestation: Attestation,
    premises: list[PremiseOutcome] | tuple[PremiseOutcome, ...] = (),
    *,
    against: tuple[str, str] | None | str = None,
) -> list[str]:
    """Every reason this capability does not close. Empty is the clean answer.

    ``against`` is ``(head_revision, tree_digest)`` — the identity of the tree
    being closed. Supply it and evidence gathered about a DIFFERENT tree stops
    the close.

    It exists because a blind cross-vendor audit of this release returned eight
    findings and six of them were already repaired: the auditor had read a
    snapshot taken before two repair rounds, and its report never said which
    revision it read, so nothing could tell. Six hours of independent reading
    produced two usable findings and six that had to be re-executed one at a
    time to discover they were about a tree that no longer existed.

    An audit is evidence about one tree. Which tree is part of the finding, and
    a gate that does not ask cannot tell stale evidence from current evidence —
    in either direction. The dangerous direction is not the false alarm above:
    it is an audit of an OLD tree reading as clean for a new one.
    """
    problems = [str(outcome) for outcome in attestation.blocking]
    problems.extend(
        str(outcome) for outcome in premises if outcome.reproduced is not True
    )
    # REQUIRED, after a blind reader observed that an optional identity check is
    # a check nobody performs: the unconditional claim was *evidence about one
    # tree does not close another*, and the default did exactly that.
    #
    # `UNSTATED` exists so a caller with genuinely no identity to compare must
    # SAY so rather than reach it by omission. That is the difference between a
    # disclosed gap and a silent one.
    if against is None:
        problems.append(
            "THIS GATE WAS NOT TOLD WHICH TREE IT IS CLOSING, so it cannot tell current evidence "
            "from evidence gathered before the last repair. Pass `against=(revision, digest)`, or "
            f"`against={UNSTATED!r}` to record that the identity is genuinely unavailable"
        )
    elif against != UNSTATED:
        revision, digest = against
        for name, recorded, current in (("revision", attestation.head_revision, revision),
                                        ("tree digest", attestation.tree_digest, digest)):
            if recorded != current:
                problems.append(
                    f"THIS EVIDENCE IS ABOUT A DIFFERENT TREE: it records {name} "
                    f"{recorded!r} and the tree being closed is {current!r}. A finding is about "
                    f"the tree it was gathered from; re-run the evidence against this one"
                )
    return problems


def _cli(argv: list[str]) -> int:
    """Generate a close attestation from a contract and the results in hand.

    Usage: ``close_attestation.py CAPABILITY --project PATH --head REV
                                  --tree-digest DIGEST
                                  [--result PROFILE=STATUS ...]
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
    # The STATE IS DERIVED from the recorded exit status, never asserted. A
    # `--passed PROFILE` flag let a caller record a pass with no number behind
    # it, which is the reinterpretation `evidence_index` already makes
    # unrepresentable: *`passed` is a derived property of the recorded exit
    # status, not a field anybody can set.*
    parser.add_argument("--result", action="append", default=[], metavar="PROFILE=STATUS",
                        help="a profile and the exit status its checker actually returned")
    parser.add_argument("--incomplete", action="append", default=[], metavar="PROFILE",
                        help="a profile whose run did not finish: neither a pass nor a failure")
    args = parser.parse_args(argv)

    from project_contract import ContractError, ProjectContract

    try:
        contract = ProjectContract.load(args.project)
    except ContractError as exc:
        print(f"CONTRACT UNREADABLE {exc}")
        return 2

    profiles = list((contract.raw.get("validation_profiles") or {}))
    results: dict[str, ProfileOutcome] = {}
    for entry in args.result:
        name, _, raw = entry.partition("=")
        try:
            status = int(raw)
        except ValueError:
            print(f"REFUSED --result takes PROFILE=STATUS; {entry!r} carries no exit status, and "
                  "a pass with no number behind it is an assertion rather than a reading")
            return 2
        results[name] = ProfileOutcome(
            profile=name,
            state=ProfileState.PASSED if status == 0 else ProfileState.FAILED,
            exit_status=status,
        )
    for name in args.incomplete:
        results[name] = ProfileOutcome(profile=name, state=ProfileState.INCOMPLETE)

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
