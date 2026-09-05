"""Project Context: declared, located, verified — and never adjudicated here.

Not to be confused with `project_contract.py`, which reads `PROJECT.yaml`. This
module is about a different object entirely: a project's **durable semantic and
product authority** — what the product means, what it has decided, what is still
open. A real project already runs one and proves
non-mutation across a capability by showing the same digest before and after.

The Core's job here is deliberately small, and the smallness is the design.

**Core does not adjudicate product meaning.** Nothing in this module reads the
context's contents, and nothing in it can. It verifies *identity* — is the thing
at the declared locator the revision the project declared, unchanged since the
capability opened — and says nothing whatever about whether what it contains is
right. Product meaning is the project's authority; a governance layer that
started grading it would be holding state it also judged, which is the one thing
D1 forbids.

So five things are contract-level, and everything else is project-local:

*   a **declaration** in the project contract, so a capability cannot use a
    context nobody declared;
*   a **canonical locator**, resolved and checked, for the same reason
    `pack.root_path` exists — an identity without a location cannot be confirmed;
*   a **revision and a state**, so "not present", "declared but unverified" and
    "verified" are three answers rather than one absence;
*   a **digest**, so non-mutation is a fact rather than an assurance;
*   a **proposal/adoption boundary**, so a suggestion cannot become authority by
    being written down.

## Why the digest is computed over the filesystem, not over git

A Project Context need not be a git repository, and the one that motivated this
is a directory. So the framing is the same discipline `pack_pin` applies —
length-framed path and content, sorted, with the algorithm named — over a
filesystem walk instead of an index. Framing is not decoration: without it, path
`ab` with content `c` and path `a` with content `bc` hash identically, and a
rename that moves one byte across the boundary becomes invisible.

## What "no silent mutation during a capability" means operationally

It means the digest is taken when the capability opens and recomputed when it
closes, and the two are compared. A context that changed mid-capability is a
finding, not a refresh: the capability's evidence was produced against a
semantic authority that no longer exists, which makes the evidence
uninterpretable rather than merely stale.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from errors import GateRefusal

__all__ = [
    "DIGEST_ALGORITHM",
    "NOT_PRESENT",
    "DECLARED",
    "CURRENTLY_VERIFIED",
    "STALE",
    "UNVERIFIABLE",
    "CONTEXT_STATES",
    "ContextDeclaration",
    "UnreadableDeclaration",
    "ContextReport",
    "tree_digest",
    "declaration_from",
    "report_declared",
    "verify",
    "assert_unchanged",
]

#: Named, and distinct from the pack's own `sha256-framed-v1`, which is computed
#: over a git index. A declaration carrying an algorithm this module does not
#: implement fails as a version mismatch rather than as tampering.
DIGEST_ALGORITHM = "sha256-framed-tree-v1"

#: The project declares no context. A capability may proceed; it simply has no
#: semantic authority to consult, and says so.
NOT_PRESENT = "NOT_PRESENT"
#: Declared, and not yet verified in this session. Not a failure and not a pass.
DECLARED = "DECLARED"
#: Located, and matching the declared revision and digest.
CURRENTLY_VERIFIED = "CURRENTLY_VERIFIED"
#: Located and readable, and not what the declaration describes. The context
#: moved, or the declaration did.
STALE = "STALE"
#: Could not be located or read. **Not** `NOT_PRESENT`: "nobody declared one"
#: and "one was declared and cannot be found" are different facts, and the
#: second is a stop.
UNVERIFIABLE = "UNVERIFIABLE"

CONTEXT_STATES = (NOT_PRESENT, DECLARED, CURRENTLY_VERIFIED, STALE, UNVERIFIABLE)

#: Names and directory names never walked. Volatile, machine-local, and none of
#: it is semantic authority — including it would make the digest change for
#: reasons that are not changes to the context.
_SKIP_DIRECTORIES = frozenset({".git", "__pycache__", ".pytest_cache", ".DS_Store"})
_SKIP_NAMES = frozenset({".DS_Store"})


class ContextError(GateRefusal):
    """The Project Context declaration could not be read, or does not verify.

    A refusal in the toolbelt's hierarchy, for the same reason `ContractError`
    is: outside it, `errors.run_cli` cannot report it and the caller gets a
    traceback where a stated cause was written.
    """

    code = "HX_PROJECT_CONTEXT"


def tree_digest(root: str | Path) -> tuple[str, int]:
    """``(sha256, file_count)`` over a directory, framed and sorted.

    Symlinks are **not followed**: a link is recorded as its target string
    rather than as the bytes it points at, so a context cannot be changed from
    outside itself by repointing a link, and a link out of the tree cannot
    silently pull unrelated bytes into the identity.
    """
    root = Path(root)
    entries: list[tuple[str, bytes]] = []
    for path in sorted(root.rglob("*")):
        if any(part in _SKIP_DIRECTORIES for part in path.relative_to(root).parts):
            continue
        if path.name in _SKIP_NAMES:
            continue
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append((relative, b"symlink:" + str(path.readlink()).encode("utf-8")))
        elif path.is_file():
            entries.append((relative, path.read_bytes()))
        # Directories contribute nothing of their own: their existence is
        # implied by the paths beneath them, and an empty directory carries no
        # semantic content.

    digest = hashlib.sha256()
    digest.update(f"{DIGEST_ALGORITHM}\n".encode("ascii"))
    for relative, content in sorted(entries):
        path_bytes = relative.encode("utf-8")
        digest.update(f"{len(path_bytes)} {len(content)}\n".encode("ascii"))
        digest.update(path_bytes)
        digest.update(content)
    digest.update(f"{len(entries)}\n".encode("ascii"))
    return digest.hexdigest(), len(entries)


@dataclass(frozen=True)
class ContextDeclaration:
    """What a project declared about its Project Context."""

    context_id: str
    reference_path: str
    control_revision: int
    digest: str
    #: What this context is authoritative *for*, in the project's own words.
    #: Recorded and never interpreted — Core does not adjudicate product meaning.
    authority_role: str = ""
    #: Whether the project has activated it. A declared-but-inactive context is
    #: verified and not consulted, which is a different thing from absent.
    activated: bool = True
    digest_algorithm: str = DIGEST_ALGORITHM
    #: A pending proposal does **not** change the context. Recorded so that
    #: "somebody suggested this" cannot be read as "the context says this".
    proposals_pending: int = 0

    #: The directory a RELATIVE `reference_path` is relative to — the contract's
    #: own. Empty when the declaration was built without one, in which case a
    #: relative path is returned as given rather than resolved against the
    #: process, because guessing the process's directory is the defect.
    declared_in: str = ""

    def resolved(self) -> Path:
        """The context root, resolved against the CONTRACT and never the process.

        This was `Path(reference_path).expanduser().resolve()`, so a relative
        declaration resolved against whatever directory the tool ran in. An
        independent reader verified a contract from another directory and got
        `CURRENTLY_VERIFIED` over a DIFFERENT project's context — a silent
        affirmative on the project's declared semantic authority, which is
        exactly the state `capability_open` treats as a stop.
        """
        path = Path(self.reference_path).expanduser()
        if not path.is_absolute() and self.declared_in:
            path = Path(self.declared_in) / path
        return path.resolve()


#: What this verifier needs before it can check a context's identity at all.
#: Absence of any of them is a shape it cannot read; presence with the wrong
#: value is an error.
_IDENTITY_KEYS = ("context_id", "reference_path", "control_revision", "digest")


@dataclass(frozen=True)
class UnreadableDeclaration:
    """A `project_context:` block whose identity fields are ABSENT.

    Not an error and not a declaration: the project said it has a context and
    did not say it in the form this verifier can check. Distinguished from a
    malformed value, which still raises — somebody who wrote `control_revision:
    "twelve"` meant to declare a revision, and silence about a typo is the
    dangerous kind. An absent field is more often an older shape, and refusing
    to load the ENTIRE contract over one optional block would deny every
    unrelated tool a project's contract to punish an omission in this one.

    Found against the only real Project Context in existence, which records its
    digest in prose rather than in a field: this verifier refused to load that
    project's contract at all.
    """

    context_id: str | None
    missing: tuple[str, ...]


@dataclass
class ContextReport:
    state: str
    declaration: ContextDeclaration | None = None
    findings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    observed_digest: str | None = None
    observed_files: int | None = None

    @property
    def clean(self) -> bool:
        """Verified, or honestly absent. Never "declared and unchecked"."""
        return not self.findings and self.state in (CURRENTLY_VERIFIED, NOT_PRESENT)

    def render(self) -> str:
        lines = [f"project context: {self.state}"]
        if self.declaration is not None:
            lines.append(
                f"  {self.declaration.context_id} revision {self.declaration.control_revision}"
                f"{'' if self.declaration.activated else ' (declared, NOT activated)'}"
            )
            if self.declaration.authority_role:
                lines.append(f"  authority (project's own words, not interpreted here): "
                             f"{self.declaration.authority_role}")
            if self.declaration.proposals_pending:
                lines.append(
                    f"  {self.declaration.proposals_pending} proposal(s) pending — a proposal "
                    "is not an adoption and changes nothing about what the context says"
                )
        if self.observed_digest:
            lines.append(f"  observed {self.observed_files} file(s), digest {self.observed_digest[:16]}…")
        lines.extend(f"  {item}" for item in self.findings)
        lines.extend(f"  note: {item}" for item in self.notes)
        return "\n".join(lines)


def declaration_from(value: object, *, declared_in: str | Path = "") -> ContextDeclaration | None:
    """Parse a `project_context:` block.

    Three outcomes, and the difference between them is the point:

    *   `None` — the project declared no context. A clean state.
    *   :class:`UnreadableDeclaration` — it declared one and left out a field
        this verifier needs, so its identity cannot be checked. Reported as
        `UNVERIFIABLE`, never as verified and never as absent.
    *   :class:`ContextDeclaration` — every identity field is present.

    A field that is present and MALFORMED still raises. A declaration that
    half-parses is the worst outcome available: the capability would proceed
    believing it had a verified semantic authority.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ContextError("`project_context:` must be a mapping")

    absent = tuple(key for key in _IDENTITY_KEYS if key not in value)
    if absent:
        identifier = value.get("context_id")
        return UnreadableDeclaration(
            context_id=identifier if isinstance(identifier, str) else None,
            missing=absent,
        )

    def required(key: str, kind: type, description: str):
        item = value.get(key)
        if isinstance(item, bool) and kind is not bool:
            raise ContextError(f"project_context.{key} must be {description}")
        if not isinstance(item, kind) or (kind is str and not item.strip()):
            raise ContextError(f"project_context.{key} is missing or is not {description}")
        return item

    context_id = required("context_id", str, "an identifier")
    reference = required("reference_path", str, "a path")
    control_revision = required("control_revision", int, "an integer revision")
    if control_revision < 0:
        raise ContextError("project_context.control_revision must not be negative")
    digest = required("digest", str, "a digest")
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ContextError("project_context.digest is not a 64-character lowercase sha256 digest")

    algorithm = value.get("digest_algorithm", DIGEST_ALGORITHM)
    if algorithm != DIGEST_ALGORITHM:
        raise ContextError(
            f"project_context.digest_algorithm is {algorithm!r}; this verifier implements "
            f"{DIGEST_ALGORITHM!r}"
        )

    activated = value.get("activated", True)
    if not isinstance(activated, bool):
        raise ContextError("project_context.activated must be true or false")

    pending = value.get("proposals_pending", 0)
    if not isinstance(pending, int) or isinstance(pending, bool) or pending < 0:
        raise ContextError("project_context.proposals_pending must be a count")

    role = value.get("authority_role", "")
    if not isinstance(role, str):
        raise ContextError("project_context.authority_role must be a string")

    return ContextDeclaration(
        context_id=context_id, reference_path=reference, control_revision=control_revision,
        digest=digest, authority_role=role, activated=activated,
        digest_algorithm=algorithm, proposals_pending=pending,
        declared_in=str(declared_in),
    )


def report_declared(declaration: ContextDeclaration | None) -> ContextReport:
    """The state a contract is in once read and before anything is verified.

    `DECLARED` existed as a constant and as a line in the template and was
    returned by no code path — found by an independent audit, and a state
    nothing can reach is a state nobody can act on. This is what reaches it:
    the contract loader produces a declaration, and until the verifier has run
    against the filesystem the honest answer is "declared, not established".

    It is deliberately **not clean**. A capability that read the contract and
    never verified has not verified, and must not read as though it had.
    """
    if declaration is None:
        return ContextReport(state=NOT_PRESENT)
    if isinstance(declaration, UnreadableDeclaration):
        return _unreadable_report(declaration)
    return ContextReport(
        state=DECLARED,
        declaration=declaration,
        notes=["declared and not yet verified in this session; run the verifier at capability open"],
    )


def _unreadable_report(declaration: "UnreadableDeclaration") -> ContextReport:
    """One rendering of an unreadable block, so the two entry points agree."""
    named = f" {declaration.context_id}" if declaration.context_id else ""
    return ContextReport(
        state=UNVERIFIABLE,
        findings=[
            f"the declared project context{named} does not record "
            + ", ".join(declaration.missing)
            + ", so its identity cannot be checked. This is NOT `NOT_PRESENT`: a context "
            "was declared. It is not repaired by recording today's values — that would "
            "produce a declaration that verifies and establishes nothing"
        ],
    )


def verify(declaration: ContextDeclaration | None) -> ContextReport:
    """Locate the declared context and check its identity. Only its identity."""
    if declaration is None:
        return ContextReport(state=NOT_PRESENT)
    if isinstance(declaration, UnreadableDeclaration):
        return _unreadable_report(declaration)

    root = declaration.resolved()
    if not root.is_dir():
        return ContextReport(
            state=UNVERIFIABLE,
            declaration=declaration,
            findings=[
                f"the declared reference_path {declaration.reference_path!r} does not resolve "
                f"to a directory ({root}). This is not NOT_PRESENT: a context was declared "
                "and cannot be found, which is a stop"
            ],
        )

    try:
        observed, count = tree_digest(root)
    except OSError as exc:
        return ContextReport(
            state=UNVERIFIABLE, declaration=declaration,
            findings=[f"the declared context could not be read: {exc}"],
        )

    report = ContextReport(
        state=CURRENTLY_VERIFIED, declaration=declaration,
        observed_digest=observed, observed_files=count,
    )
    if observed != declaration.digest:
        report.state = STALE
        report.findings.append(
            f"the context at {declaration.reference_path} digests to {observed[:16]}…, "
            f"and the declaration records {declaration.digest[:16]}… at revision "
            f"{declaration.control_revision}. Either the context moved or the declaration did; "
            "nothing here can tell which, and neither is repaired by copying the new digest in"
        )
    if not declaration.activated:
        report.notes.append(
            "declared but NOT activated: it is verified and is not consulted. That is a "
            "different state from absent, and a capability that needs it must say so"
        )
    return report


def assert_unchanged(
    declaration: ContextDeclaration, opened_digest: str, *, capability: str
) -> list[str]:
    """Recompute at capability close and compare with the opening digest.

    This is the whole of "no silent mutation during a capability", and it is a
    comparison rather than an assurance. A context that changed mid-capability
    makes that capability's evidence **uninterpretable**, not merely stale: the
    evidence was produced against a semantic authority that no longer exists.
    """
    root = declaration.resolved()
    if not root.is_dir():
        return [
            f"capability {capability}: the Project Context declared at "
            f"{declaration.reference_path} is no longer present at close"
        ]
    observed, _count = tree_digest(root)
    if observed != opened_digest:
        return [
            f"capability {capability}: the Project Context changed while the capability was "
            f"open ({opened_digest[:16]}… at open, {observed[:16]}… at close). The evidence "
            "this capability produced was made against a semantic authority that no longer "
            "exists, so it cannot be interpreted — this is a stop, not a refresh"
        ]
    return []


def _cli(argv: list[str]) -> int:
    """Verify the Project Context a contract declares, or observe a digest."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="project_context.py",
        description="Verify a declared Project Context. Reads its identity, never its contents.",
    )
    parser.add_argument("--project", help="path to PROJECT.yaml")
    parser.add_argument(
        "--observe", metavar="PATH",
        help="print the current digest of a context directory; this is not a verification",
    )
    args = parser.parse_args(argv)

    if args.observe:
        digest, count = tree_digest(args.observe)
        print(
            "OBSERVATION ONLY — what this directory contains now, not a statement that it is "
            "the revision anyone declared.",
            file=sys.stderr,
        )
        print(f"{digest}  {count} file(s)  {args.observe}")
        return 0

    if not args.project:
        parser.error("one of --project or --observe is required")

    import project_contract

    try:
        contract = project_contract.ProjectContract.load(args.project)
        declaration = contract.project_context
    except (ContextError, project_contract.ContractError) as exc:
        print(f"the Project Context declaration could not be read: {exc}", file=sys.stderr)
        return 2

    report = verify(declaration)
    print(report.render())
    return 0 if report.clean else 1


if __name__ == "__main__":
    import sys

    # Run the module, not a second copy of it. A file executed as a script is
    # `__main__`, and a sibling that imports it BY NAME gets a separate module
    # object with separate class objects — so an `isinstance` check across that
    # boundary is False for an object that is exactly that class. It crashed
    # `project_context.py --project` against a real consumer's contract, on a
    # shape the suite covers completely: tests import the module and never run
    # it as a script. Imported statically, by name, because a dynamic import
    # would route around the toolbelt's import-closure check.
    from errors import run_cli
    from project_context import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
