"""What an instrument must say about itself before its verdict means anything.

Every checker in this toolbelt answers a question. This module carries the
facts that decide whether the answer is interpretable, and refuses in the cases
where it is not. Each one is here because it was measured, and none of them is
about whether the underlying check is *correct*: a perfectly correct check can
still produce a sentence a reader will believe for the wrong reason.

Four failure shapes, and the fact that closes each:

*   **A gate with modes ran one of them and did not say which.** The same
    repository, the same vocabulary, two tiers: one printed `clean`, the other
    printed a leak count. A recorded limitation then quoted one of those numbers
    without stating the tier, and the remedy it proposed could not have cleared
    the hits the other tier finds. One word in the headline prevents it, which
    makes this the cheapest control in the pack and not the least important:
    the question it guards is the irreversible one.

*   **An instrument that examined nothing reported a result.** Zero is a
    measurement; *absent* is not zero. A scan whose range resolved to no
    commits rendered `clean (0 commits, 0 blobs)`, which is indistinguishable
    from a range that was read and found safe. `Examined` makes the count part
    of the verdict rather than a decoration beside it.

*   **A checker read a stale copy of its own rule.** Nine refusals reported
    against a rule that yields one; the other eight existed only because the
    checker was looking at an old copy of the rule in a working directory.
    Reproduced in this toolbelt against the frozen baseline: a project that
    declares a pack root, whose rule is not present under that root, silently
    gets whichever copy the search order reaches next — including one sitting
    beside its own contract — and no report says which file was read. **A copy
    in a working directory is a cache, and caches go stale silently.**

*   **A tool ran an external program nobody had declared it would.** One
    instance crossed a host security boundary by launching a browser. A blast
    radius that is a sentence in a document is a note; one that refuses an
    undeclared executable is a control.

And one that is not a refusal but an output requirement:

*   **An equivalence gate entered downstream of the difference.** A parity check
    compared already-decoded arguments across two transports, passed, and could
    not see that the two decoders disagreed about what the same request text
    meant. It survived six audit cycles in the capability whose subject *was*
    parity. Naming the layer each side is entered at, in the gate's own output,
    is what makes the gap visible to the reader rather than only to the author.

**None of this establishes that a check is right.** A mutant dying proves a
check can fail, not that it asks the right question — a pinned test was once
asserting the buggy value, so deleting it turned the suite red while the bug
lived. These facts make a verdict *readable*. Reading it is still somebody's
job.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from errors import GateRefusal, IntegrityError, PreconditionError

__all__ = [
    "Mode",
    "ModeSet",
    "Examined",
    "NOTHING_EXAMINED",
    "RuleSource",
    "read_rule",
    "EquivalenceLayers",
    "BlastRadius",
    "launch",
]


# --- modes -------------------------------------------------------------------


@dataclass(frozen=True)
class Mode:
    """One of the rule sets a gate can run under.

    ``name`` is what appears in the headline. It is short on purpose: a reader
    scanning stored evidence needs to see it without reading a sentence.
    """

    name: str
    describes: str

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise IntegrityError("a mode must have a name; an unnamed mode cannot appear in a headline")
        if not self.describes or not self.describes.strip():
            raise IntegrityError(
                "a mode must say what it does differently", mode=self.name
            )


class ModeSet:
    """The modes one gate declares, and which of them is running.

    A gate that declares fewer than two modes is refused rather than allowed to
    carry a decorative one: the whole point of the announcement is that a reader
    could otherwise not tell which of several answers they are looking at, and a
    set of one has no such reader problem.
    """

    def __init__(self, modes: Iterable[Mode]) -> None:
        collected = tuple(modes)
        if len(collected) < 2:
            raise IntegrityError(
                "a mode set describes a choice between rule sets and needs at least two",
                declared=len(collected),
            )
        names = [mode.name for mode in collected]
        if len(set(names)) != len(names):
            raise IntegrityError("two modes share a name", names=", ".join(sorted(names)))
        self._modes = {mode.name: mode for mode in collected}

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._modes)

    def select(self, name: str) -> Mode:
        """The named mode, or a refusal naming the ones that exist."""
        try:
            return self._modes[name]
        except KeyError:
            raise IntegrityError(
                "no such mode", requested=name, declared=", ".join(sorted(self._modes))
            ) from None

    def headline(self, subject: str, verdict: str, active: Mode | str) -> str:
        """``<subject> [<mode>]: <verdict>`` — the mode inside the headline.

        Not appended after the verdict, and not relegated to a provenance line
        below it. A reader who takes one line from a report takes the first one,
        and the measured failure is exactly that: a number quoted out of a
        headline that did not carry its tier.
        """
        mode = active if isinstance(active, Mode) else self.select(active)
        if mode.name not in self._modes:
            raise IntegrityError("that mode is not in this set", mode=mode.name)
        return f"{subject} [{mode.name}]: {verdict}"


# --- what was actually looked at ---------------------------------------------


@dataclass(frozen=True)
class Examined:
    """The counts an instrument actually reached, as part of its verdict.

    ``nothing`` is the state that matters. It is not a failure and it is not a
    pass: it is the answer *no observation was made*, and the reason it needs a
    name is that its rendering is otherwise byte-identical to a clean result.
    """

    counts: Mapping[str, int]

    def __post_init__(self) -> None:
        for unit, value in self.counts.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise IntegrityError("an examined count must be a whole number", unit=unit, value=repr(value))

    @property
    def nothing(self) -> bool:
        return not any(self.counts.values())

    def summary(self) -> str:
        return ", ".join(f"{value} {unit}" for unit, value in self.counts.items())

    def verdict_or_nothing(self, verdict: str) -> str:
        """``verdict``, unless nothing was examined — then say so instead.

        The caller keeps its own verdict vocabulary; this only refuses to let a
        positive one stand over an empty observation.
        """
        return NOTHING_EXAMINED if self.nothing else verdict


#: The verdict an instrument renders when it reached nothing. Distinct from
#: every clean verdict in the toolbelt, and deliberately loud: the overwhelming
#: cause in practice is a range, a ref or a path that is not the one the caller
#: meant, and a quiet `clean` sends them away satisfied.
NOTHING_EXAMINED = "NOTHING EXAMINED"


# --- where a rule came from ---------------------------------------------------


@dataclass(frozen=True)
class RuleSource:
    """The one file a rule was read from, and whether it was the canonical one.

    ``searched`` keeps every candidate in the order they were tried, because the
    interesting question after a surprising finding count is not only *which
    file won* but *what else was on the path*.
    """

    path: str
    digest: str
    canonical_root: str | None
    #: How the file was reached, and the three answers are not equivalent:
    #:
    #: ``canonical``  it won a search order and lies under the declared root;
    #: ``declared``   it was the only location given, so nothing was substituted
    #:                for anything — the project named this file and got it;
    #: ``unrooted``   it won a search order and no root was declared, so nobody
    #:                had said where the rule was supposed to live.
    how: str
    searched: tuple[str, ...] = ()

    @property
    def canonical(self) -> bool:
        return self.how in ("canonical", "declared")

    def summary(self) -> str:
        return f"{self.path} ({self.how}, sha256 {self.digest[:12]})"


def read_rule(
    candidates: Sequence[str | Path],
    *,
    canonical_root: str | Path | None,
    what: str = "rule",
) -> tuple[bytes, RuleSource]:
    """The first candidate that exists, refused if it is outside the canonical root.

    A search order is how a checker finds its rule when a caller has not said
    exactly where it is. It is also how a checker silently substitutes one rule
    for another: the winning candidate is invisible in the output, so a stale
    copy beside a working directory is indistinguishable from the pinned one.

    So: when a search order can substitute one file for another, the winner must
    lie under the declared root, and a resolution outside it is a **refusal**.

    **A single candidate is not a search order.** A project that names exactly
    one location — an absolute path, say — has not been substituted against; it
    asked for that file and got it, the choice is visible in its own contract,
    and the source below carries the digest of what was read. Refusing that
    would refuse correct work, which is the other way this class of control
    fails. The distinction is reported rather than flattened: `declared` and
    `canonical` are different answers.
    """
    searched = tuple(str(candidate) for candidate in candidates)
    if not searched:
        raise IntegrityError(f"no candidate location was given for the {what}")

    root = Path(canonical_root).resolve() if canonical_root else None
    only_one = len(searched) == 1
    for candidate in candidates:
        path = Path(candidate)
        if not path.is_file():
            continue
        resolved = path.resolve()
        inside = root is not None and root in resolved.parents
        if root is not None and not inside and not only_one:
            raise PreconditionError(
                f"the {what} resolved outside the declared root, and a copy in a working "
                f"directory is a cache rather than an authority",
                resolved=str(resolved),
                declared_root=str(root),
                searched=", ".join(searched),
            )
        try:
            data = resolved.read_bytes()
        except OSError as exc:
            raise PreconditionError(f"cannot read the {what}", path=str(resolved), error=str(exc)) from exc
        return data, RuleSource(
            path=str(resolved),
            digest=hashlib.sha256(data).hexdigest(),
            canonical_root=str(root) if root else None,
            how="canonical" if inside else ("declared" if only_one else "unrooted"),
            searched=searched,
        )

    raise PreconditionError(
        f"the {what} was not found at any declared location",
        searched=", ".join(searched),
    )


# --- equivalence ---------------------------------------------------------------


@dataclass(frozen=True)
class EquivalenceLayers:
    """The layer at which a comparison enters each of the two paths it compares.

    Both sides are required. A comparison that names neither reads as a
    comparison of the two systems, and the measured case is a gate that compared
    two decoders' *outputs* and was therefore structurally unable to see that
    the decoders disagreed.

    ``not_compared`` is the other half and is just as load-bearing: what the gate
    enters *above*, and therefore never reaches, is where the next defect of this
    shape will be.
    """

    left: str
    right: str
    not_compared: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for side, value in (("left", self.left), ("right", self.right)):
            if not value or not value.strip():
                raise IntegrityError(
                    "an equivalence gate states the layer it enters each path at, in its own "
                    "output; a side with no layer named makes the verdict unreadable",
                    side=side,
                )

    def summary(self) -> str:
        lines = [f"  compared at: {self.left}" if self.left == self.right else
                 f"  compared at: left {self.left}; right {self.right}"]
        lines.extend(f"  NOT compared: {item}" for item in self.not_compared)
        return "\n".join(lines)


# --- blast radius ---------------------------------------------------------------


@dataclass(frozen=True)
class BlastRadius:
    """What a tool touches outside itself, declared before it runs.

    Written as a control rather than a note because the version that was a note
    failed four times, the last of them across a host security boundary. The
    declaration is checked at the moment of the act, not read by a person
    afterwards.
    """

    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    launches: tuple[str, ...] = ()
    #: Why this tool needs what it declares. A radius with no stated purpose is
    #: a list somebody will widen without noticing.
    because: str = ""

    def __post_init__(self) -> None:
        if (self.writes or self.launches) and not self.because.strip():
            raise IntegrityError(
                "a blast radius that writes or launches states why",
                writes=", ".join(self.writes),
                launches=", ".join(self.launches),
            )

    def summary(self) -> str:
        parts = []
        for label, values in (("reads", self.reads), ("writes", self.writes), ("launches", self.launches)):
            parts.append(f"{label}: {', '.join(values) if values else 'nothing'}")
        return "; ".join(parts)

    def permits_launch(self, executable: str) -> bool:
        return Path(executable).name in {Path(entry).name for entry in self.launches}


def launch(
    command: Sequence[str],
    *,
    radius: BlastRadius,
    **kwargs,
) -> subprocess.CompletedProcess:
    """Run an external program the caller's blast radius names, or refuse.

    The check is on the executable, by basename, because a declaration listing a
    path and an invocation resolving through `PATH` are the same act and refusing
    one while allowing the other would teach callers to route around it.
    """
    if not command:
        raise IntegrityError("a launch needs a command")
    executable = str(command[0])
    if not radius.permits_launch(executable):
        raise GateRefusal(
            "this tool launched an external program its declared blast radius does not name",
            executable=executable,
            declared=", ".join(radius.launches) or "nothing",
        )
    return subprocess.run(list(command), **kwargs)
