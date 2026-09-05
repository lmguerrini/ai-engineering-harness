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


#: RP2.4.1 R4. Every Git read this module makes goes through `gitread`, which
#: neutralises the configuration keys whose values Git executes and refuses the
#: ones it has no named closure for. `gitread` said it did this "for *every*
#: invocation rather than at the call sites somebody remembered", and this
#: module was the call site nobody remembered: it ran `subprocess` directly, so
#: a `core.fsmonitor` in the verified repository — or in the operator's global
#: configuration, needing no write to the release at all — was executed by the
#: act of verifying the pin, which then printed `pack pin verified`.
#:
#: Verification is what establishes that a checkout can be trusted. Doing it by
#: running that checkout's own program is the wrong order, and a second
#: neutralisation table here would have been a second answer to one question.
def _git(root: str | Path, *arguments: str) -> str:
    import gitread

    try:
        return gitread._run(root, *arguments, timeout=60)
    except Exception as exc:
        # Translated, so every caller's existing handling of "Git could not
        # answer" keeps working — including the branch that reports a copy
        # outside a checkout as UNDECIDABLE rather than as a failed pin.
        raise subprocess.CalledProcessError(
            1, ["git", *arguments], output="", stderr=str(exc)) from exc


def _git_bytes(root: str | Path, *arguments: str) -> bytes:
    """The same hardened boundary, answering in bytes.

    The manifest comparison claims byte-for-byte and compared decoded text, so a
    line-ending rewrite passed a check that exists to establish the file has not
    moved since its commit.
    """
    import gitread

    try:
        return gitread._run(root, *arguments, timeout=60, text=False)
    except Exception as exc:
        raise subprocess.CalledProcessError(
            1, ["git", *arguments], output="", stderr=str(exc)) from exc


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
    """Files present in the checkout that Git neither tracks nor the release ignores.

    A pinned release is a claim about a *directory*, not only about an index.
    An untracked, non-ignored file is inside the tree a consumer will read,
    contributes nothing to the digest, and is exactly how an unreviewed module
    reaches a checkout that reports as verified.

    **The rules are the release's, and the MATCHING is Git's.** Three attempts
    were needed to make that sentence true, and each failure is why the shape
    below is what it is.

    `--exclude-standard` honours `core.excludesFile` and `.git/info/exclude`,
    which the release neither ships nor can see, so an operator's machine-level
    ignore file could hide material.

    `--exclude-per-directory=.gitignore` reads the ignore files PRESENT in the
    working tree, tracked or not, so an untracked `unreviewed/.gitignore`
    containing `*` hid itself and an unreviewed module.

    Reading the tracked rules and matching them in Python was wrong in BOTH
    directions against real Git — an anchored root rule stripped of its `/` hid
    material at every depth, a nested rule lost bare-name recursion, and
    whitespace Git treats as significant was normalised away.

    Pointing `--exclude-per-directory` at a name the tree "does not contain" was
    the same hole with a different filename: **that option makes Git look for
    that name in EVERY directory it walks**, so a nested
    `anywhere/<that-name>` containing `*` handed the authority straight back
    while the pin still verified. A root-only existence check could not see it,
    and no chosen name is safe, because the name is in the source.

    So there is no per-directory discovery at all. Omitting the option entirely
    makes Git read no working-tree ignore file anywhere — tracked or not — and
    the release's own tracked `.gitignore` is supplied by absolute path with
    `--exclude-from`. Git does the matching; the release supplies the rules; a
    file nobody reviewed has no say, whatever it is called and wherever it sits.

    A nested tracked `.gitignore` cannot be expressed this way, because
    `--exclude-from` is root-relative. It is REFUSED rather than approximated —
    approximating it is what produced the third failure above.
    """
    # ABSOLUTE, because `--exclude-from` is resolved by Git against the process
    # working directory it is launched in, which is the root itself. Built from
    # the caller's spelling, a relative root with a path component became
    # `root/root/.gitignore` and the enumeration failed — a real release
    # refused for the way it was named.
    root = Path(root).resolve()
    declared = [path for path in tracked_files(root)
                if path == ".gitignore" or path.endswith("/.gitignore")]
    nested = [path for path in declared if path != ".gitignore"]
    if nested:
        raise ValueError(
            f"this release tracks nested ignore declarations ({', '.join(nested)}), and the "
            f"enumeration supplies rules to Git root-relatively, so their per-directory meaning "
            f"cannot be expressed here. Refused rather than approximated")
    arguments = ["ls-files", "--others", "-z"]
    if declared:
        arguments.append(f"--exclude-from={root / '.gitignore'}")
    return _nul_separated(_git(root, *arguments))


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


#: The prefix of a problem that means *this check could not be performed*,
#: rather than *this check failed*. Named rather than matched as prose, because
#: a caller distinguishing the two by reading a sentence is a caller that
#: stops distinguishing them the day the sentence is reworded.
UNESTABLISHED = "IDENTITY COULD NOT BE ESTABLISHED"


def root_kind(root: str | Path) -> "tuple[str, str]":
    """What kind of directory this release root is, and why that matters.

    **THE 2.3.0 INCIDENT, MADE EXECUTABLE.** A release root that is a LINKED
    GIT WORKTREE is not immutable: whoever owns the main repository can move it
    to another revision, and the pin then stops verifying for a reason the
    adopting project did not cause and cannot see coming. That happened here —
    the pack's own evolution workspaces are linked worktrees, one of them was a
    pinned root, and it verified only because it happened to be sitting on its
    pinned revision.

    Reported, never blocking. A linked worktree that IS on its pinned revision
    is a correct checkout of the right tree, and refusing it would refuse a
    working adoption over a hazard that has not happened. What the project gets
    is the sentence at adoption time instead of at breakage time.

    Returns ``(kind, why)`` where kind is one of ``checkout``,
    ``linked-worktree`` or ``not-a-checkout``.
    """
    root = Path(root)
    marker = root / ".git"
    if marker.is_dir():
        return "checkout", "the release root is an ordinary checkout with its own repository"
    if marker.is_file():
        # A linked worktree's `.git` is a FILE holding `gitdir: <path>`. A
        # submodule's is too, so the two are separated by asking Git rather than
        # by reading the file — `--path-format` is not needed because what is
        # wanted is only whether this is the main worktree.
        try:
            common = _git(root, "rev-parse", "--git-common-dir").strip()
            own = _git(root, "rev-parse", "--git-dir").strip()
        except (OSError, subprocess.SubprocessError):
            return "not-a-checkout", f"{root}/.git is a file and Git could not be asked about it"
        if common and own and Path(common).resolve() != Path(own).resolve():
            return "linked-worktree", (
                f"the release root is a LINKED GIT WORKTREE of {common}. It is not an "
                f"immutable root: whoever owns that repository can move this checkout to "
                f"another revision, and this pin would stop verifying for a reason this "
                f"project did not cause. Adopt a root nothing else moves"
            )
        return "checkout", "the release root is an ordinary checkout"
    return "not-a-checkout", (
        f"{root} carries no .git, so it is a copy rather than a checkout; the digest still "
        f"answers about its bytes and the revision cannot be established here"
    )


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
        # NOT A MISMATCH. The digest is defined over the TRACKED tree, so
        # outside a checkout there is no way to know which files belong to the
        # release — and the answer to *is this the pinned pack* is that it
        # cannot be established here, which is a different sentence from *this
        # is not the pinned pack*.
        #
        # It read as the second. A copy delivered as an archive or vendored
        # into another repository reported PIN DOES NOT VERIFY, which is what a
        # tampered pack reports, so a consumer had to choose between alarm and
        # learning to ignore the check. Found by unpacking the release into a
        # clean room and adopting it the way a consumer would.
        return problems + [
            f"{UNESTABLISHED}: the tracked tree could not be digested here, so whether this "
            f"copy is the pinned pack cannot be decided. Identity is defined over the tracked "
            f"tree and is checkable in a checkout of the release ({exc})"]

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

    # RP2.4.1 R5. THE ONE FILE THE DIGEST CANNOT COVER.
    #
    # `PACK_MANIFEST.json` is excluded from its own digest of necessity — it
    # records that digest — and 2.4.0 compared it to nothing else. So every
    # claim it carries that is not `version` or `state` sat outside every
    # check: a root could say it had 999999 passing tests, or replace seventy
    # known limitations with "nothing is wrong with this release", and still
    # print `pack pin verified` to the consumer reading those very fields.
    #
    # WHAT THIS ESTABLISHES, EXACTLY: that the manifest in this directory is
    # byte-for-byte the manifest committed at the pinned revision. It does NOT
    # establish that the manifest's claims are TRUE — no mechanism here can
    # count a release's tests or audit its own limitations, and pretending
    # otherwise would be the kind of check whose message outruns its reason
    # that this module exists to refuse. What it removes is the gap between
    # what a reader verified and what a reader read.
    try:
        committed = _git_bytes(root, "show", f"HEAD:{MANIFEST_NAME}")
    except (OSError, subprocess.CalledProcessError) as exc:
        problems.append(
            f"{UNESTABLISHED}: the committed manifest could not be read, so whether this "
            f"directory's manifest is the one at the pinned revision cannot be decided ({exc})")
    else:
        if committed != manifest_path.read_bytes():
            problems.append(
                f"{MANIFEST_NAME} differs from the one committed at HEAD. It is excluded from "
                f"its own digest, so every claim it makes — the test population, the known "
                f"limitations, the gate records — is only as good as this comparison")

    try:
        strays = untracked_files(root)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
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

    try:
        actual_head = _git(root, "rev-parse", "HEAD").strip()
    except (OSError, subprocess.CalledProcessError):
        actual_head = ""
    if not actual_head:
        problems.append("HEAD could not be read, so the revision is unverified")
    elif expect_sha is not None:
        wanted = expect_sha.strip().lower()
        actual_sha = actual_head
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
