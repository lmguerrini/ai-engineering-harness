"""Verify the executable adapters a project's workflow dispatches to.

An adapter is material that *runs* — an installed agent definition, a worker
skill, a dispatch template — and that lives **outside** the pinned release. The
pack cannot freeze it (D12) and must not vendor it by default (D14 clause 10),
which leaves exactly one honest option: the project declares which adapter it
qualified against, and something checks that claim before the adapter is used.

The defect that produced this module was live in the installation, not
hypothetical. `skills/core/worker-contract.md` and
`templates/audit-brief.template.md` both state that a reviewer never creates a
ref, a branch or a worktree, and say why: a reviewer that cannot write has
nothing to isolate, and isolating one anyway cost 1.4 GB and put an
agent-named branch inside the repository under review. The installed reviewer
adapter nonetheless declared `isolation: worktree`. Reproduced end to end: the
isolation mode lands `refs/heads/worktree-agent-*` in the audited repository,
and `publication_gate.py` exits 1 on exactly that ref, calling it "an agent
worktree branch created inside the repository under review". So a pinned,
verified pack, all of whose own tests passed, dispatched every audit through a
worker configured to violate the contract the pack enforces — and nothing could
notice, because nothing was looking at the adapter at all.

What this module does **not** do is as load-bearing as what it does:

*   **It never writes an adapter, and never updates a digest.** A verifier that
    refreshes its own expectation on mismatch is a verifier that always passes.
    `observe` prints what a file currently hashes to, labels that output as not
    a verification, and leaves the decision to record it with a person.
*   **It holds no adapter state.** The declaration lives in the project
    contract, the bytes live wherever the adapter is installed, and this module
    is the checker in between. Adapter state stays outside Core authority (D1:
    nothing both holds authoritative state and adjudicates it).
*   **It does not guess identity from a filename.** A path is a locator, not an
    identity. Where a declaration says which name the adapter must declare, the
    file's own frontmatter is read and compared.

`required` governs **absence only.** A declared adapter that is present and does
not match its digest is blocking whether or not it is required, because the
project recorded a digest for it: "optional" is a statement that the workflow
can proceed without the adapter, never a statement that any bytes will do.

## When a repair to an adapter takes effect

**At the next session, not the current one** — and this was reproduced during
the release that added this module, which is the reason it is stated here rather
than assumed.

The reviewer adapter's `isolation: worktree` was removed and the corrected file
was on disk. Two reviewers dispatched afterwards, in the same session, were
nonetheless given worktrees, and two `refs/heads/worktree-agent-*` refs appeared
inside the audited repository — where `publication_gate.py` refused them, by
name, exactly as it is supposed to.

The harness had loaded the definition when the session started. Editing the file
later changed the file and not the behaviour.

Two consequences, both load-bearing:

*   **Verification belongs at capability open, before the first dispatch.** An
    adapter verified afterwards has already run, and an adapter *repaired*
    afterwards has not. Neither report describes the session it was produced in.
*   **A verified digest describes the file, not the loaded configuration.** They
    agree only across a session boundary. So a repair is followed by a new
    session, and the pin is what makes the two comparable at all.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from errors import IntegrityError

__all__ = [
    "DIGEST_ALGORITHM",
    "AdapterDeclaration",
    "AdapterFinding",
    "AdapterReport",
    "declarations_from",
    "file_digest",
    "verify",
]

#: Named so a declaration carrying a digest this module did not compute fails
#: as an algorithm mismatch rather than as tampering — the same rule
#: `pack_pin` applies to the tree digest.
DIGEST_ALGORITHM = "sha256"

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

#: The frontmatter key an agent or skill definition uses to declare the name the
#: harness dispatches on. Read only when a declaration asks for it.
_NAME_KEY = re.compile(r"(?m)^name:[ \t]*(?P<name>\S.*?)[ \t]*$")

_KNOWN_FIELDS = frozenset({"id", "locator", "digest", "required", "declares", "note"})


def file_digest(path: str | Path) -> str:
    """The SHA-256 of a file's bytes, or a stated failure.

    Read in one shot rather than streamed: an adapter is a definition file, and
    a definition too large to hold is a finding in itself rather than a case to
    optimise for.
    """
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise IntegrityError("adapter cannot be read", path=str(path), error=str(exc)) from exc


@dataclass(frozen=True)
class AdapterDeclaration:
    """One adapter a project declares it qualified against."""

    id: str
    locator: str
    digest: str
    required: bool = True
    declares: str | None = None
    note: str | None = None

    def resolved(self, *, home: str | Path | None = None) -> Path:
        """The locator as an absolute path, with `~` expanded.

        `~` is expanded against ``home`` when given, so a test can point the
        expansion somewhere other than the invoking user's home directory
        without setting an environment variable for the whole process.
        """
        text = self.locator
        if text.startswith("~"):
            if home is None:
                return Path(text).expanduser()
            remainder = text[1:].lstrip("/")
            return Path(home) / remainder
        return Path(text)


@dataclass(frozen=True)
class AdapterFinding:
    """One way an adapter is not what the project declared."""

    adapter: str
    problem: str
    #: `False` for a *permitted* absence — the one condition `required: false`
    #: exists to allow. Everything else blocks.
    blocking: bool = True

    def __str__(self) -> str:
        return f"{self.adapter}: {self.problem}"


@dataclass
class AdapterReport:
    findings: list[AdapterFinding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    verified: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        """No blocking finding. A permitted absence is not a failure."""
        return not any(finding.blocking for finding in self.findings)

    def render(self) -> str:
        if self.clean and not self.findings:
            head = f"adapters verified: {len(self.verified)} of {len(self.verified)}"
        elif self.clean:
            head = (
                f"adapters verified: {len(self.verified)}; "
                f"{len(self.findings)} permitted absence(s)"
            )
        else:
            head = "adapters NOT VERIFIED"
        lines = [head]
        for finding in self.findings:
            marker = "  " if finding.blocking else "  (permitted) "
            lines.append(f"{marker}{finding}")
        lines.extend(f"  note: {item}" for item in self.notes)
        return "\n".join(lines)


def declarations_from(value: object) -> tuple[AdapterDeclaration, ...]:
    """Parse an `adapters:` block, refusing anything it cannot read exactly.

    Every malformed declaration raises. A checker that skips a declaration it
    could not parse reports "every adapter verified" while having verified
    fewer than were declared, which is the shape of failure the whole toolbelt
    is built against.
    """
    if value is None:
        return ()
    if not isinstance(value, list):
        raise IntegrityError(
            "`adapters:` must be a list of declarations", found=type(value).__name__
        )

    seen: set[str] = set()
    out: list[AdapterDeclaration] = []
    for position, entry in enumerate(value, start=1):
        where = f"adapters[{position}]"
        if not isinstance(entry, dict):
            raise IntegrityError(f"{where} is not a mapping", found=type(entry).__name__)

        unknown = sorted(set(entry) - _KNOWN_FIELDS)
        if unknown:
            # An unread field is a declaration the project believes it made.
            raise IntegrityError(
                f"{where} declares field(s) this verifier does not implement",
                unknown=", ".join(unknown),
                known=", ".join(sorted(_KNOWN_FIELDS)),
            )

        identifier = entry.get("id")
        if not isinstance(identifier, str) or not _IDENTIFIER.match(identifier):
            raise IntegrityError(f"{where}.id is missing or not an identifier", found=repr(identifier))
        if identifier in seen:
            raise IntegrityError(f"{where}.id is declared twice", id=identifier)
        seen.add(identifier)

        locator = entry.get("locator")
        if not isinstance(locator, str) or not locator.strip():
            raise IntegrityError(f"{where}.locator is missing", id=identifier)

        digest = entry.get("digest")
        if not isinstance(digest, str) or not _DIGEST.match(digest):
            raise IntegrityError(
                f"{where}.digest is not a 64-character lowercase {DIGEST_ALGORITHM} digest",
                id=identifier,
                found=repr(digest),
            )

        required = entry.get("required", True)
        if not isinstance(required, bool):
            raise IntegrityError(
                f"{where}.required must be true or false", id=identifier, found=repr(required)
            )

        declares = entry.get("declares")
        if declares is not None and not isinstance(declares, str):
            raise IntegrityError(f"{where}.declares must be a string", id=identifier)

        note = entry.get("note")
        if note is not None and not isinstance(note, str):
            raise IntegrityError(f"{where}.note must be a string", id=identifier)

        out.append(
            AdapterDeclaration(
                id=identifier,
                locator=locator.strip(),
                digest=digest,
                required=required,
                declares=declares,
                note=note,
            )
        )
    return tuple(out)


def verify(
    declarations: tuple[AdapterDeclaration, ...] | list[AdapterDeclaration],
    *,
    home: str | Path | None = None,
) -> AdapterReport:
    """Every way the installed adapters are not what the project declared."""
    report = AdapterReport()

    for declaration in declarations:
        path = declaration.resolved(home=home)

        if not path.exists():
            report.findings.append(
                AdapterFinding(
                    declaration.id,
                    f"declared at {declaration.locator} and not installed there",
                    blocking=declaration.required,
                )
            )
            continue

        if path.is_symlink():
            # Not refused: the digest is over the bytes actually read, so the
            # integrity claim holds through a link. Recorded because the
            # *locator* claim is weaker than it looks — the name checked and
            # the file checked are two different objects.
            try:
                target = path.resolve()
            except OSError:
                target = path
            report.notes.append(f"{declaration.id}: {declaration.locator} is a symlink to {target}")

        if not path.is_file():
            report.findings.append(
                AdapterFinding(declaration.id, f"{declaration.locator} is not a regular file")
            )
            continue

        try:
            actual = file_digest(path)
        except IntegrityError as exc:
            # Unreadable is not "absent" and is not "unchanged". It is a
            # failure to look, and it blocks whether or not the adapter is
            # required, because nothing was established either way.
            report.findings.append(
                AdapterFinding(declaration.id, f"{declaration.locator} could not be read: {exc.cause}")
            )
            continue

        if actual != declaration.digest:
            report.findings.append(
                AdapterFinding(
                    declaration.id,
                    f"{declaration.locator} does not match the declared digest "
                    f"(declared {declaration.digest[:12]}…, found {actual[:12]}…). "
                    "Re-qualify the adapter and record the new digest deliberately; "
                    "this checker will not update it",
                )
            )
            continue

        if declaration.declares is not None:
            match = _NAME_KEY.search(path.read_text(encoding="utf-8", errors="replace"))
            found = match.group("name") if match else None
            if found != declaration.declares:
                report.findings.append(
                    AdapterFinding(
                        declaration.id,
                        f"declares name {found!r}, expected {declaration.declares!r}",
                    )
                )
                continue

        report.verified.append(declaration.id)

    return report


def verify_contract(contract: object, *, home: str | Path | None = None) -> AdapterReport:
    """Verify the adapters a loaded :class:`ProjectContract` declares.

    Kept separate from :func:`verify` so this module stays usable — and
    testable — without a contract on disk.
    """
    declared = getattr(contract, "adapters", None)
    if declared is None:
        raise IntegrityError("the project contract carries no adapters declaration to verify")
    return verify(declared, home=home)


def _observe(paths: list[str]) -> int:
    """Print what each file currently hashes to. **Not a verification.**"""
    print(
        "OBSERVATION ONLY — this is what these files contain now, not a statement\n"
        "that they are correct. Qualify the adapter first, then record the digest.",
        file=sys.stderr,
    )
    status = 0
    for path in paths:
        try:
            print(f"{file_digest(path)}  {path}")
        except IntegrityError as exc:
            print(exc.render(), file=sys.stderr)
            status = exc.exit_status
    return status


def _cli(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="adapter_pin.py",
        description="Verify declared executable adapters, or observe their current digests.",
    )
    parser.add_argument("--project", help="path to PROJECT.yaml carrying the adapters declaration")
    parser.add_argument(
        "--observe",
        nargs="+",
        metavar="PATH",
        help="print the current digest of each path; this is not a verification",
    )
    args = parser.parse_args(argv)

    if args.observe:
        return _observe(args.observe)
    if not args.project:
        parser.error("one of --project or --observe is required")

    import project_contract

    try:
        contract = project_contract.ProjectContract.load(args.project)
        report = verify_contract(contract)
    except (IntegrityError, project_contract.ContractError) as exc:
        rendered = exc.render() if isinstance(exc, IntegrityError) else f"HX_CONTRACT: {exc}"
        print(rendered, file=sys.stderr)
        return 2

    print(report.render())
    return 0 if report.clean else 1


if __name__ == "__main__":
    import sys

    from errors import run_cli

    raise SystemExit(run_cli(_cli, sys.argv[1:]))
