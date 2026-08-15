"""Verify a pinned pack against its own manifest.

A project pins an exact pack version and revision. That pin is worth exactly as
much as a consumer's ability to check it, and the first version of this pack's
manifest could not be checked at all: the digest was computed over 81 tracked
files and the manifest then became the 82nd, so recomputing it produced a
different value forever after. Nothing failed and no test caught it, because the
manifest was written by different code than the code that would verify it —
which is the defect shape the pack's own oracle rules name (`recorded` and
`enforced` are different claims).

So the digest deliberately **excludes the manifest file itself**, that exclusion
is recorded inside the manifest, and this module is the verifier. One function
computes the digest and both writing and checking call it, so the two cannot
drift apart.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

__all__ = ["MANIFEST_NAME", "tree_digest", "verify_pin"]

#: Excluded from the digest it records. A manifest cannot contain its own hash.
MANIFEST_NAME = "PACK_MANIFEST.json"


def tracked_files(root: str | Path) -> list[str]:
    """Every file Git tracks, excluding the manifest."""
    result = subprocess.run(
        ["git", "ls-files"], cwd=str(root), capture_output=True, text=True, check=True
    )
    return sorted(p for p in result.stdout.split() if p and p != MANIFEST_NAME)


def tree_digest(root: str | Path) -> tuple[str, int]:
    """``(sha256, file_count)`` over the tracked tree, manifest excluded.

    Paths are hashed alongside contents, so a rename changes the digest — a
    digest over contents alone would call two different trees identical.
    """
    root = Path(root)
    files = tracked_files(root)
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.encode())
        digest.update((root / path).read_bytes())
    return digest.hexdigest(), len(files)


def verify_pin(root: str | Path, *, expect_version: str | None = None, expect_sha: str | None = None) -> list[str]:
    """Every way this checkout is not the pack the manifest claims.

    Returns an empty list only when the pack verifies. A manifest that cannot be
    read is a failure, never an absence of findings.
    """
    root = Path(root)
    manifest_path = root / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"the manifest at {manifest_path} could not be read: {exc}"]

    problems: list[str] = []
    try:
        actual_digest, actual_count = tree_digest(root)
    except (OSError, subprocess.CalledProcessError) as exc:
        return [f"the tracked tree could not be digested: {exc}"]

    if actual_digest != manifest.get("tree_digest_sha256"):
        problems.append(
            f"tree digest {actual_digest[:16]}… does not match the manifest's "
            f"{str(manifest.get('tree_digest_sha256'))[:16]}… — this checkout is not the pinned pack"
        )
    if actual_count != manifest.get("tracked_files"):
        problems.append(
            f"{actual_count} tracked files, manifest records {manifest.get('tracked_files')}"
        )
    if expect_version and manifest.get("version") != expect_version:
        problems.append(f"pinned version {expect_version!r}, manifest says {manifest.get('version')!r}")

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True
    )
    if head.returncode != 0:
        problems.append("HEAD could not be read, so the revision is unverified")
    else:
        actual_sha = head.stdout.strip()
        if expect_sha and not actual_sha.startswith(expect_sha[:40].rstrip()):
            problems.append(f"pinned revision {expect_sha[:12]}, checkout is at {actual_sha[:12]}")
    return problems


def _cli(argv: list[str]) -> int:
    """Verify a pack checkout against its manifest.

    Usage: ``pack_pin.py PACK_ROOT [--version V] [--sha SHA] [--write]``
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="pack_pin.py", description="Verify a pinned pack against its manifest."
    )
    parser.add_argument("root")
    parser.add_argument("--version", help="the version this project pinned")
    parser.add_argument("--sha", help="the revision this project pinned")
    parser.add_argument("--write", action="store_true", help="recompute and rewrite the digest fields")
    args = parser.parse_args(argv)

    if args.write:
        manifest_path = Path(args.root) / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest, count = tree_digest(args.root)
        manifest["tree_digest_sha256"] = digest
        manifest["tracked_files"] = count
        manifest["digest_excludes"] = MANIFEST_NAME
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"digest {digest} over {count} files (excluding {MANIFEST_NAME})")
        return 0

    problems = verify_pin(args.root, expect_version=args.version, expect_sha=args.sha)
    if not problems:
        print(f"pack pin verified: {args.root}")
        return 0
    print("PACK PIN NOT VERIFIED")
    for problem in problems:
        print(f"  {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
