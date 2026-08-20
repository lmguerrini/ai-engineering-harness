"""Toolbelt error hierarchy.

Trimmed from the kernel's error module (``hx/errors.py``) to the classes the
extracted tools actually raise. Every refusal carries a stable machine-readable
``code`` and a specific ``cause``: a bare exception type is not a cause.
"""

from __future__ import annotations


class HxError(Exception):
    """Base class for every condition a tool raises."""

    code = "HX_ERROR"
    exit_status = 1

    def __init__(self, cause: str, **detail: object) -> None:
        super().__init__(cause)
        self.cause = cause
        self.detail = detail

    def render(self) -> str:
        parts = [f"{self.code}: {self.cause}"]
        for key in sorted(self.detail):
            parts.append(f"  {key}: {self.detail[key]}")
        return "\n".join(parts)


class GateRefusal(HxError):
    """A deterministic gate refused a proposed transition or operation.

    Refusals are normal control flow, not faults. There is no override for any
    subclass of this.
    """

    code = "HX_GATE_REFUSAL"
    exit_status = 2


class IntegrityError(GateRefusal):
    """Object-store, source-parse or projection integrity failed."""

    code = "HX_INTEGRITY"


class CommitContractError(GateRefusal):
    """A commit message violates the public commit contract."""

    code = "HX_COMMIT_CONTRACT"


class PreconditionError(GateRefusal):
    """A transition's preconditions are not satisfied."""

    code = "HX_PRECONDITION"


class GitRefusal(GateRefusal):
    """Git could not perform a requested, bounded repository operation."""

    code = "HX_GIT_REFUSAL"


def run_cli(entry, argv: "list[str]") -> int:
    """Run a tool's CLI so that a refusal is REPORTED rather than raised.

    Every tool exited on an unhandled traceback when git could not answer — a
    ref that does not resolve, a repository that cannot be read. Found by
    pointing the toolbelt at the three real projects on this machine rather
    than at fixtures: three tools crashed identically, and the crash was
    indistinguishable from a bug in the tool.

    A refusal is an answer this pack has a word for, and printing a stack trace
    instead loses the two things the caller needs — the stable code and the
    specific cause — behind the one thing they do not.

    `SystemExit` and `KeyboardInterrupt` pass through untouched: argparse exits
    that way, and a user interrupting is not a refusal.
    """
    try:
        return entry(argv)
    except HxError as refusal:
        print(f"REFUSED {refusal.render()}")
        return refusal.exit_status
