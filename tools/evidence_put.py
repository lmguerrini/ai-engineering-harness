"""A minimal SHA-256 content-addressed evidence put.

Evidence is private material — reproductions, scan output, worker reports, the
contents of a failure. RP2.2 found it being written **world-readable**: the
directory arrived `0o755` and every entry `0o644`, because `mkdir` and `open`
take the process umask and nothing afterwards ever looked. Reproduced by
execution. On a shared machine that is a disclosure, and the tool that promised
durable custody of the material was the thing that published it.

So evidence is created **owner-only** and the mode is then **verified from the
filesystem**, not assumed from the argument that requested it: a umask, a mount
option, or a directory somebody else created can all defeat a requested mode
silently, and a permission you did not read is a permission you do not have.
An existing directory is *tightened* rather than refused — tightening cannot
open a hole, and refusing would strand every evidence directory an earlier
version created — but if it still verifies as reachable by group or other after
that, the put refuses rather than writing into it.

Modelled on the kernel's object store (``hx/objects.py``), scaled down to the
single operation the toolbelt needs: copy one file into an evidence directory
under a name that names its own content, and never silently replace a
reference whose stored bytes have drifted from what its name promises.

Write order: content is written to a temporary file, fsynced, and only after
being re-read and verified against its own digest is it renamed into its
permanent reference path — and only then is the reference returned. A file
already present at that reference is verified rather than retrusted; a
mismatch there is refused, never silently overwritten.
"""

from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path

from errors import IntegrityError

__all__ = ["put", "DIRECTORY_MODE", "FILE_MODE"]

#: Owner-only. Evidence is private material and nothing else needs to read it.
DIRECTORY_MODE = 0o700
FILE_MODE = 0o600

#: Any bit in this mask means somebody other than the owner can reach it.
_SHARED_BITS = 0o077


def _verify_mode(path: Path, expected: int, *, what: str) -> None:
    """Read the mode back and refuse anything reachable beyond the owner.

    Read back rather than trusted: `mkdir(mode=...)` and `open(..., mode)` are
    both masked by the process umask, so the mode a call *requests* and the mode
    a file *has* are different facts, and only one of them is a permission.
    """
    try:
        actual = stat.S_IMODE(path.lstat().st_mode)
    except OSError as exc:
        raise IntegrityError(
            f"{what} mode could not be read, so it cannot be relied on",
            path=str(path), error=str(exc),
        ) from exc
    if actual & _SHARED_BITS:
        raise IntegrityError(
            f"{what} is readable beyond its owner",
            path=str(path), mode=oct(actual), required=oct(expected),
        )


def put(evidence_dir: str | Path, source: str | Path) -> str:
    """Copy ``source`` into ``evidence_dir`` and return its content-addressed reference."""
    source_path = Path(source)
    try:
        data = source_path.read_bytes()
    except OSError as exc:
        raise IntegrityError("evidence source cannot be read", path=str(source_path), error=str(exc)) from exc

    digest = hashlib.sha256(data).hexdigest()
    reference = f"sha256-{digest}-{source_path.name}"
    directory = Path(evidence_dir)
    destination = directory / reference

    if destination.exists():
        if destination.is_symlink() or not destination.is_file():
            raise IntegrityError("evidence path is not an immutable regular file", path=str(destination))
        _verify_mode(destination, FILE_MODE, what="the existing evidence entry")
        existing = destination.read_bytes()
        if hashlib.sha256(existing).hexdigest() != digest:
            raise IntegrityError(
                "an evidence entry already exists at this reference with different content",
                reference=reference, path=str(destination),
            )
        return reference

    try:
        directory.mkdir(parents=True, exist_ok=True, mode=DIRECTORY_MODE)
        # `mkdir` applies the mode only when it creates, and applies the umask
        # to it even then. Both are why this second call exists rather than
        # being redundant with the first.
        os.chmod(directory, DIRECTORY_MODE)
    except OSError as exc:
        raise IntegrityError("evidence directory cannot be created", path=str(directory), error=str(exc)) from exc
    _verify_mode(directory, DIRECTORY_MODE, what="the evidence directory")

    temporary = directory / f".{reference}.tmp-{os.getpid()}"
    try:
        # `os.open` with an explicit mode and `O_EXCL`, not `open(..., "wb")`:
        # the builtin creates `0o666 & ~umask`, so the bytes were readable by
        # everyone for the whole window between creation and any later chmod.
        # There is no such window here.
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, FILE_MODE)
        with open(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, FILE_MODE)
        _verify_mode(temporary, FILE_MODE, what="the evidence entry")
        # Re-read rather than trust the bytes just written: write-then-verify
        # is the whole point of a write-then-reference ordering.
        written = temporary.read_bytes()
        if hashlib.sha256(written).hexdigest() != digest:
            raise IntegrityError("evidence write did not verify against its own digest", path=str(temporary))
        os.rename(temporary, destination)
        # Rename preserves the mode, so this confirms rather than repairs — but
        # confirming is the point: the guarantee is about the file a reader will
        # open, not about the one that was written.
        _verify_mode(destination, FILE_MODE, what="the evidence entry")
    except OSError as exc:
        raise IntegrityError("evidence cannot be written durably", path=str(destination), error=str(exc)) from exc
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass

    return reference


def _cli(argv: list[str]) -> int:
    """Put one file into an evidence directory and print its reference.

    Usage: ``evidence_put.py EVIDENCE_DIR SOURCE_FILE``
    """
    import argparse

    parser = argparse.ArgumentParser(prog="evidence_put.py", description="Store one file content-addressed in an evidence directory.")
    parser.add_argument("evidence_dir")
    parser.add_argument("source")
    args = parser.parse_args(argv)

    try:
        reference = put(args.evidence_dir, args.source)
    except IntegrityError as exc:
        print(exc.render(), file=sys.stderr)
        return exc.exit_status
    print(reference)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
