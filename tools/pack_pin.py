"""Verify a pinned pack against its own manifest.

A project pins an exact pack version, revision and digest. That pin is worth
exactly as much as a consumer's ability to check it, and this module has now
been wrong about that twice.

The first manifest could not be checked at all: the digest was computed over 81
tracked files and the manifest then became the 82nd, so recomputing it produced
a different value forever after. Nothing failed and no test caught it, because
the manifest was written by different code than the code that would verify it —
the defect shape `oracle-discipline.md` names when it says provenance must be
reported by the component that did the work. Fixed by excluding the manifest
from its own digest and shipping one function that both writing and checking
call.

The second failure was subtler and is what RP2.1.1 repairs: the checker ran, said
`pack pin verified`, and **meant less than the sentence a reader would take from
it**. Six ways, each reproduced by execution before it was repaired:

*   a one-character `--sha` passed, because the comparison was `startswith`;
*   `PACK_MANIFEST.json` could claim any version at all, because nothing
    compared it to `VERSION`, the single machine-readable authority;
*   an untracked, non-ignored file could sit in the checkout unmentioned,
    because the digest only ever looked at tracked paths;
*   the digest concatenated path and content with no framing, so path `ab` with
    content `c` and path `a` with content `bc` hash identically;
*   tracked paths were split on whitespace, so a committed `a file.md` became
    two nonexistent entries and the digest raised or silently changed;
*   every other manifest field — the test count, the gate record, the state —
    was outside the digest by design and checked by nothing, so altering it was
    free.

The rule those six share: **a verifier must mean exactly what the documentation
around it claims.** A check that passes for a reason weaker than its message is
worse than no check, because it is believed.

The digest framing is release-local and named in the manifest
(`digest_algorithm`). A release is verified with the `pack_pin.py` that ships
*inside it*; a manifest naming an algorithm this module does not implement is
refused loudly rather than reported as tampering.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

__all__ = [
    "MANIFEST_NAME",
    "VERSION_NAME",
    "DIGEST_ALGORITHM",
    "KNOWN_STATES",
    "DIGEST_COUNT_KEY",
    "LEGACY_COUNT_KEY",
    "manifest_file_count",
    "tracked_files",
    "untracked_files",
    "tree_digest",
    "verify_pin",
]

#: Excluded from the digest it records. A manifest cannot contain its own hash.
MANIFEST_NAME = "PACK_MANIFEST.json"

#: How many files the digest covers — which is every git-tracked file EXCEPT the
#: manifest. Named `tracked_files` through 2.1.1, where it read as the number of
#: files git tracks and was always one fewer than that. Renamed rather than
#: re-explained: a label a reader has to be corrected about is the defect this
#: pack exists to refuse.
DIGEST_COUNT_KEY = "digest_file_count"

#: The 2.1.1 spelling. Still accepted, because a 2.2.0 verifier is used to check
#: an OLDER pinned root during migration, and refusing that manifest would make
#: the rename break the thing it was supposed to clarify.
LEGACY_COUNT_KEY = "tracked_files"

#: The single machine-readable version authority. The manifest restates it and
#: must agree with it; nothing else may.
VERSION_NAME = "VERSION"

#: Names the framing below. Recorded in the manifest so a checkout carrying a
#: different scheme fails as a version mismatch rather than as tampering.
DIGEST_ALGORITHM = "sha256-framed-v1"

#: The release states a manifest may declare. `QUALIFIED_AND_FROZEN` is the only
#: one a project may adopt.
KNOWN_STATES = ("QUALIFIED_AND_FROZEN", "IN_PROGRESS")

_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _git(root: str | Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=str(root), capture_output=True, text=True, check=True
    )
    return result.stdout


def _nul_separated(output: str) -> list[str]:
    """Paths as Git emitted them under ``-z``.

    Not ``.split()``. A tracked path may contain a space, and splitting on
    whitespace turns one real file into two absent ones — which either raises
    on read or, for a path whose halves both happen to exist, changes the
    digest without changing the tree.
    """
    return sorted(entry for entry in output.split("\0") if entry)


def tracked_files(root: str | Path) -> list[str]:
    """Every file Git tracks, excluding the manifest. NUL-separated."""
    return [
        path
        for path in _nul_separated(_git(root, "ls-files", "-z"))
        if path != MANIFEST_NAME
    ]


def untracked_files(root: str | Path) -> list[str]:
    """Files present in the checkout that Git neither tracks nor ignores.

    A pinned release is a claim about a *directory*, not only about an index.
    An untracked, non-ignored file is inside the tree a consumer will read,
    contributes nothing to the digest, and is exactly how an unreviewed module
    reaches a checkout that reports as verified.
    """
    return _nul_separated(_git(root, "ls-files", "--others", "--exclude-standard", "-z"))


def tree_digest(root: str | Path) -> tuple[str, int]:
    """``(sha256, file_count)`` over the tracked tree, manifest excluded.

    Paths are hashed alongside contents, so a rename changes the digest — a
    digest over contents alone would call two different trees identical.

    Each entry is **framed**: a header declaring the byte length of the path and
    of the content precedes them both. Without it the stream is ambiguous, and
    ambiguity in a digest is not a theoretical complaint — an unframed
    ``update(path); update(content)`` gives path `ab` + content `c` and path `a`
    + content `bc` the same hash, so a rename that moves one byte across the
    boundary is invisible to the pin.
    """
    root = Path(root)
    files = tracked_files(root)
    digest = hashlib.sha256()
    digest.update(f"{DIGEST_ALGORITHM}\n".encode("ascii"))
    for path in files:
        path_bytes = path.encode("utf-8")
        content = (root / path).read_bytes()
        digest.update(f"{len(path_bytes)} {len(content)}\n".encode("ascii"))
        digest.update(path_bytes)
        digest.update(content)
    digest.update(f"{len(files)}\n".encode("ascii"))
    return digest.hexdigest(), len(files)


def manifest_file_count(manifest: dict) -> tuple[int | None, list[str]]:
    """How many files the manifest says its digest covers, and what is wrong.

    Accepts either spelling. Both present and disagreeing is a refusal rather
    than a preference: a manifest that answers the same question twice, in two
    ways, has no answer.
    """
    problems: list[str] = []
    present = {key: manifest[key] for key in (DIGEST_COUNT_KEY, LEGACY_COUNT_KEY) if key in manifest}
    if not present:
        problems.append(f"neither {DIGEST_COUNT_KEY} nor {LEGACY_COUNT_KEY} is recorded")
        return None, problems

    counts = {}
    for key, value in present.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            problems.append(f"{key} is {value!r}, not a count")
        else:
            counts[key] = value
    if len(counts) == 2 and counts[DIGEST_COUNT_KEY] != counts[LEGACY_COUNT_KEY]:
        problems.append(
            f"{DIGEST_COUNT_KEY} is {counts[DIGEST_COUNT_KEY]} and {LEGACY_COUNT_KEY} is "
            f"{counts[LEGACY_COUNT_KEY]} — a manifest cannot record two file counts"
        )
        return None, problems
    if DIGEST_COUNT_KEY in counts:
        return counts[DIGEST_COUNT_KEY], problems
    return counts.get(LEGACY_COUNT_KEY), problems


def _manifest_problems(root: Path, manifest: dict) -> list[str]:
    """Every way the manifest's own authoritative metadata is not well-formed.

    The manifest is excluded from the digest that protects the rest of the
    tree, which is unavoidable and leaves its own fields unguarded. So they are
    checked here instead: a field nothing validates is a field anybody may
    write, and the RP2.1.0 manifest could carry a fabricated test count and a
    gate record naming a file that does not exist while the pin verified.
    """
    problems: list[str] = []

    algorithm = manifest.get("digest_algorithm")
    if algorithm != DIGEST_ALGORITHM:
        problems.append(
            f"the manifest records digest_algorithm {algorithm!r}; this verifier implements "
            f"{DIGEST_ALGORITHM!r}. Verify a release with the pack_pin.py that ships inside it"
        )

    if manifest.get("digest_excludes") != MANIFEST_NAME:
        problems.append(
            f"digest_excludes is {manifest.get('digest_excludes')!r}, must be {MANIFEST_NAME!r}"
        )

    if not isinstance(manifest.get("pack"), str) or not manifest["pack"].strip():
        problems.append("the manifest does not name the pack it describes")

    if not isinstance(manifest.get("version"), str) or not manifest["version"].strip():
        problems.append("the manifest carries no version")

    state = manifest.get("state")
    if state not in KNOWN_STATES:
        problems.append(f"state {state!r} is not one of {', '.join(KNOWN_STATES)}")

    if not isinstance(manifest.get("tree_digest_sha256"), str) or not _DIGEST.match(
        manifest.get("tree_digest_sha256") or ""
    ):
        problems.append("tree_digest_sha256 is not a 64-character lowercase hex digest")

    count, count_problems = manifest_file_count(manifest)
    problems.extend(count_problems)

    gate_record = manifest.get("gate_record")
    if gate_record is not None:
        if not isinstance(gate_record, str) or not (root / gate_record).is_file():
            problems.append(f"gate_record {gate_record!r} does not name a file in this checkout")

    tests = manifest.get("tests")
    if tests is not None:
        passed = tests.get("passed") if isinstance(tests, dict) else None
        if not isinstance(passed, int) or isinstance(passed, bool) or passed <= 0:
            problems.append(f"tests.passed is {passed!r}, not a count of passing tests")

    return problems


def verify_pin(
    root: str | Path,
    *,
    expect_version: str | None = None,
    expect_sha: str | None = None,
    expect_digest: str | None = None,
    expect_state: str | None = None,
) -> list[str]:
    """Every way this checkout is not the pack the manifest claims.

    Returns an empty list only when the pack verifies, and every check that
    could not be performed is a finding rather than an absence of one. A
    manifest that cannot be read is a failure. An expectation that cannot
    discriminate — an abbreviated revision, an empty digest — is refused
    instead of being satisfied.
    """
    root = Path(root)
    manifest_path = root / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"the manifest at {manifest_path} could not be read: {exc}"]
    if not isinstance(manifest, dict):
        return [f"the manifest at {manifest_path} is not a JSON object"]

    problems = _manifest_problems(root, manifest)

    try:
        actual_digest, actual_count = tree_digest(root)
    except (OSError, subprocess.CalledProcessError) as exc:
        return problems + [f"the tracked tree could not be digested: {exc}"]

    if actual_digest != manifest.get("tree_digest_sha256"):
        problems.append(
            f"tree digest {actual_digest[:16]}… does not match the manifest's "
            f"{str(manifest.get('tree_digest_sha256'))[:16]}… — this checkout is not the pinned pack"
        )
    recorded_count, count_problems = manifest_file_count(manifest)
    problems.extend(problem for problem in count_problems if problem not in problems)
    if recorded_count is not None and actual_count != recorded_count:
        problems.append(
            f"the digest covers {actual_count} files, the manifest records {recorded_count}"
        )

    try:
        strays = untracked_files(root)
    except (OSError, subprocess.CalledProcessError) as exc:
        problems.append(f"untracked files could not be enumerated: {exc}")
    else:
        if strays:
            shown = ", ".join(strays[:5]) + (f", +{len(strays) - 5} more" if len(strays) > 5 else "")
            problems.append(
                f"{len(strays)} untracked non-ignored file(s) in the checkout ({shown}) — "
                "a pinned release is a claim about the directory, not only about the index"
            )

    # `VERSION` is the single machine-readable version authority. The manifest
    # restates it for consumers that read one file; a restatement that nothing
    # compares is a second authority, and two authorities are one bug.
    try:
        declared = (root / VERSION_NAME).read_text(encoding="utf-8").strip()
    except OSError as exc:
        problems.append(f"{VERSION_NAME} could not be read, so the version is unverified: {exc}")
    else:
        if manifest.get("version") != declared:
            problems.append(
                f"{VERSION_NAME} says {declared!r}, manifest says {manifest.get('version')!r} — "
                f"{VERSION_NAME} is the authority"
            )

    if expect_version is not None:
        if manifest.get("version") != expect_version:
            problems.append(
                f"pinned version {expect_version!r}, manifest says {manifest.get('version')!r}"
            )
    if expect_state is not None:
        if manifest.get("state") != expect_state:
            problems.append(
                f"pinned state {expect_state!r}, manifest says {manifest.get('state')!r}"
            )
    if expect_digest is not None:
        if not _DIGEST.match(expect_digest.strip().lower()):
            problems.append(
                f"pinned digest {expect_digest!r} is not a 64-character lowercase sha256 — "
                "a pin that cannot discriminate is not a pin"
            )
        elif expect_digest.strip().lower() != actual_digest:
            problems.append(
                f"pinned digest {expect_digest.strip()[:16]}…, checkout digests to {actual_digest[:16]}…"
            )

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True
    )
    if head.returncode != 0:
        problems.append("HEAD could not be read, so the revision is unverified")
    elif expect_sha is not None:
        wanted = expect_sha.strip().lower()
        actual_sha = head.stdout.strip()
        if not _FULL_SHA.match(wanted):
            # An abbreviation is not a weaker pin, it is a different claim. The
            # previous `startswith` comparison accepted a single character.
            problems.append(
                f"pinned revision {expect_sha!r} is not a full 40-character lowercase sha — "
                "an abbreviated revision cannot pin an immutable release"
            )
        elif wanted != actual_sha:
            problems.append(f"pinned revision {wanted[:12]}, checkout is at {actual_sha[:12]}")
    return problems


def _cli(argv: list[str]) -> int:
    """Verify a pack checkout against its manifest.

    Usage: ``pack_pin.py PACK_ROOT [--version V] [--sha SHA] [--digest D]
            [--state S] [--write]``
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="pack_pin.py", description="Verify a pinned pack against its manifest."
    )
    parser.add_argument("root")
    parser.add_argument("--version", help="the version this project pinned")
    parser.add_argument("--sha", help="the full 40-character revision this project pinned")
    parser.add_argument("--digest", help="the tree digest this project pinned")
    parser.add_argument("--state", help="the release state this project pinned")
    parser.add_argument("--write", action="store_true", help="recompute and rewrite the digest fields")
    args = parser.parse_args(argv)

    if args.write:
        manifest_path = Path(args.root) / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest, count = tree_digest(args.root)
        manifest["tree_digest_sha256"] = digest
        manifest[DIGEST_COUNT_KEY] = count
        manifest.pop(LEGACY_COUNT_KEY, None)
        manifest["digest_excludes"] = MANIFEST_NAME
        manifest["digest_algorithm"] = DIGEST_ALGORITHM
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        print(f"digest {digest} over {count} files (excluding {MANIFEST_NAME}), {DIGEST_ALGORITHM}")
        return 0

    problems = verify_pin(
        args.root,
        expect_version=args.version,
        expect_sha=args.sha,
        expect_digest=args.digest,
        expect_state=args.state,
    )
    if not problems:
        print(f"pack pin verified: {args.root}")
        return 0
    print("PACK PIN NOT VERIFIED")
    for problem in problems:
        print(f"  {problem}")
    return 1


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
    from pack_pin import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
