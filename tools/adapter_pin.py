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

import instrument
from errors import IntegrityError, PreconditionError

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

_KNOWN_FIELDS = frozenset({
    "id", "locator", "digest", "required", "declares", "note",
    # RP2.3. A digest describes the FILE an adapter is made of; these describe
    # the EXECUTABLE those files drive, which is a different object and was
    # drifting unnoticed while this module reported every adapter verified.
    "executable", "version_command", "qualified_version",
})

#: Fields that only mean anything together. A version this module was never
#: told how to obtain is a requirement nothing checks, which D22 refuses rather
#: than ignores: a requirement silently unread is worse than none, because the
#: project believes it is enforced.
_EXECUTABLE_FIELDS = ("executable", "version_command", "qualified_version")


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
    #: The program these files drive. A digest over a definition file says
    #: nothing about the binary that reads it, and the two drift independently:
    #: live at this release's baseline, one adapter's installed executable was a
    #: version ahead of the qualified one while this module reported it verified.
    executable: str | None = None
    #: How to ask that program its version. Run through the declared blast
    #: radius, so an adapter cannot quietly cause an arbitrary launch.
    version_command: tuple[str, ...] | None = None
    #: The version the project qualified against. Compared as a substring of
    #: the command's output, because version banners carry more than a number
    #: and pinning the whole banner would fail on a cosmetic change.
    qualified_version: str | None = None

    def __post_init__(self) -> None:
        declared = [name for name in _EXECUTABLE_FIELDS if getattr(self, name) is not None]
        if declared and len(declared) != len(_EXECUTABLE_FIELDS):
            raise PreconditionError(
                "an executable qualification needs all three of executable, version_command and "
                "qualified_version; a version nothing knows how to obtain is a requirement the "
                "project believes is enforced and nothing checks",
                adapter=self.id, declared=", ".join(declared),
            )

    def resolved(self, *, home: str | Path | None = None,
                 relative_to: str | Path | None = None) -> Path:
        """The locator as an absolute path, with `~` expanded.

        `~` is expanded against ``home`` when given, so a test can point the
        expansion somewhere other than the invoking user's home directory
        without setting an environment variable for the whole process.

        **A RELATIVE LOCATOR IS RELATIVE TO THE CONTRACT**, supplied as
        ``relative_to``. It was returned unchanged, so a project declaring
        `locator: adapter.md` had its adapter verified against whatever directory
        the tool ran in — and an independent reader showed a project's MODIFIED
        adapter verifying successfully from another directory that happened to
        hold the previously qualified bytes. Without ``relative_to`` the locator
        is returned as given, because a caller that knows no contract directory
        has nothing better to offer and guessing the process's would be the
        defect again.
        """
        text = self.locator
        if text.startswith("~"):
            if home is None:
                return Path(text).expanduser()
            remainder = text[1:].lstrip("/")
            return Path(home) / remainder
        path = Path(text)
        if not path.is_absolute() and relative_to is not None:
            return Path(relative_to) / path
        return path


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
    #: Adapters whose executable version was checked against the declared one.
    executables_verified: list[str] = field(default_factory=list)
    #: Adapters that declared no executable, so nothing about the program they
    #: drive was established. Reported, because "4 of 4" over four files read
    #: as a statement about four running things and was not one.
    executables_undeclared: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        """No blocking finding. A permitted absence is not a failure."""
        return not any(finding.blocking for finding in self.findings)

    def render(self) -> str:
        # The headline states WHAT was verified. Saying "4 of 4" over four
        # definition files read as a statement about the four things that run,
        # and one of those was a version ahead of the qualified one at the time.
        scope = f"{len(self.verified)} file(s), {len(self.executables_verified)} executable(s)"
        if self.clean and not self.findings:
            head = f"adapters verified: {scope}"
        elif self.clean:
            head = f"adapters verified: {scope}; {len(self.findings)} permitted absence(s)"
        else:
            head = "adapters NOT VERIFIED"
        lines = [head]
        if self.executables_undeclared:
            lines.append(
                "  executable NOT verified (none declared): "
                + ", ".join(self.executables_undeclared)
            )
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

        executable = entry.get("executable")
        if executable is not None and (not isinstance(executable, str) or not executable.strip()):
            raise IntegrityError(f"{where}.executable must be a program name", id=identifier)

        version_command = entry.get("version_command")
        if version_command is not None:
            if isinstance(version_command, str):
                # A single string is the common shape and is read as one word
                # per space. Anything needing a quoted argument writes a list.
                version_command = version_command.split()
            if (not isinstance(version_command, list) or not version_command
                    or not all(isinstance(word, str) and word for word in version_command)):
                raise IntegrityError(
                    f"{where}.version_command must be a command, as a string or a list of words",
                    id=identifier, found=repr(entry.get("version_command")),
                )
            version_command = tuple(version_command)

        qualified_version = entry.get("qualified_version")
        if qualified_version is not None and (
                not isinstance(qualified_version, str) or not qualified_version.strip()):
            raise IntegrityError(f"{where}.qualified_version must be a version string", id=identifier)

        out.append(
            AdapterDeclaration(
                id=identifier,
                locator=locator.strip(),
                digest=digest,
                required=required,
                declares=declares,
                note=note,
                executable=executable.strip() if executable else None,
                version_command=version_command,
                qualified_version=qualified_version.strip() if qualified_version else None,
            )
        )
    return tuple(out)


def verify(
    declarations: tuple[AdapterDeclaration, ...] | list[AdapterDeclaration],
    *,
    home: str | Path | None = None,
    relative_to: str | Path | None = None,
) -> AdapterReport:
    """Every way the installed adapters are not what the project declared.

    ``relative_to`` is the directory a RELATIVE locator is resolved against —
    the contract's own, supplied by :func:`verify_contract`.
    """
    report = AdapterReport()

    for declaration in declarations:
        path = declaration.resolved(home=home, relative_to=relative_to)

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

        if declaration.executable is None:
            report.executables_undeclared.append(declaration.id)
        else:
            problem = _executable_problem(declaration, relative_to=relative_to)
            if problem is not None:
                report.findings.append(AdapterFinding(declaration.id, problem))
                continue
            report.executables_verified.append(declaration.id)

        report.verified.append(declaration.id)

    return report


def _executable_problem(declaration: AdapterDeclaration,
                        *, relative_to: str | Path | None = None) -> str | None:
    """Whether the program this adapter drives is the qualified one.

    A **property** check rather than a shape one: the version is obtained by
    asking the program, not by reading a sentence in a note beside it. One such
    note said a particular version was "verified installed at bootstrap" while a
    later one was on the path, and nothing compared them.

    **THE COMMAND RUNS IN THE PROJECT'S DIRECTORY**, supplied as ``relative_to``.
    It inherited the process's, so a declaration naming `./tool` asked whichever
    directory the caller happened to be in — and once the FILE half of the
    locator was repaired to look in the project, a verification run from
    elsewhere could combine the project's own definition file with another
    directory's executable and report both verified. A bounded reading of that
    repair found it, and found that the repair had made the combination newly
    reachable: before it, the missing definition file refused the fixture first.
    """
    radius = instrument.BlastRadius(
        launches=(declaration.executable,),
        because=(
            f"the {declaration.id} adapter declares that it drives {declaration.executable}, and "
            "the only way to learn a program's version is to ask it"
        ),
    )
    try:
        result = instrument.launch(
            list(declaration.version_command), radius=radius,
            capture_output=True, text=True, timeout=30,
            **({"cwd": str(relative_to)} if relative_to is not None else {}),
        )
    except Exception as exc:  # OSError, timeout, and the refusal above
        return (
            f"declares executable {declaration.executable!r} and its version command could not "
            f"be run ({type(exc).__name__}: {exc}); an executable nobody could ask about is not "
            "an executable that matched"
        )
    output = f"{result.stdout}\n{result.stderr}"
    if declaration.qualified_version in output:
        return None
    observed = next((line.strip() for line in output.splitlines() if line.strip()), "")
    return (
        f"drives {declaration.executable!r} at {observed!r}, and the project qualified against "
        f"{declaration.qualified_version!r}. The definition files match; the program they drive "
        "does not, and a digest over a file says nothing about the binary that reads it"
    )


def verify_contract(contract: object, *, home: str | Path | None = None) -> AdapterReport:
    """Verify the adapters a loaded :class:`ProjectContract` declares.

    Kept separate from :func:`verify` so this module stays usable — and
    testable — without a contract on disk.
    """
    declared = getattr(contract, "adapters", None)
    if declared is None:
        raise IntegrityError(
            "the project contract carries no adapters declaration to verify. This is not "
            "the same as declaring none: write `adapters: []` to state that this project "
            "dispatches through no adapter, and this will verify that claim instead of "
            "refusing to guess"
        )
    # THE CONTRACT'S OWN DIRECTORY, so a relative locator names a file in the
    # project rather than in whatever directory the tool was invoked from.
    contract_path = getattr(contract, "path", None)
    return verify(declared, home=home,
                  relative_to=Path(contract_path).parent if contract_path else None)


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

    # Run the module, not a second copy of it. A file executed as a script is
    # `__main__`, and a sibling that imports it BY NAME gets a separate module
    # object with separate class objects — so an `isinstance` check across that
    # boundary is False for an object that is exactly that class. It crashed
    # `project_context.py --project` against a real consumer's contract, on a
    # shape the suite covers completely: tests import the module and never run
    # it as a script. Imported statically, by name, because a dynamic import
    # would route around the toolbelt's import-closure check.
    from errors import run_cli
    from adapter_pin import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
