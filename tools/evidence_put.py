"""A minimal SHA-256 content-addressed evidence put.

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
import sys
from pathlib import Path

from errors import IntegrityError

__all__ = ["put"]


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
        existing = destination.read_bytes()
        if hashlib.sha256(existing).hexdigest() != digest:
            raise IntegrityError(
                "an evidence entry already exists at this reference with different content",
                reference=reference, path=str(destination),
            )
        return reference

    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IntegrityError("evidence directory cannot be created", path=str(directory), error=str(exc)) from exc

    temporary = directory / f".{reference}.tmp-{os.getpid()}"
    try:
        with open(temporary, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        # Re-read rather than trust the bytes just written: write-then-verify
        # is the whole point of a write-then-reference ordering.
        written = temporary.read_bytes()
        if hashlib.sha256(written).hexdigest() != digest:
            raise IntegrityError("evidence write did not verify against its own digest", path=str(temporary))
        os.rename(temporary, destination)
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
