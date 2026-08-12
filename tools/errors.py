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
