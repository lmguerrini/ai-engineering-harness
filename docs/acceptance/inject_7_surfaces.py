#!/usr/bin/env python3
"""Build a throwaway repository carrying a synthetic leak on all seven surfaces.

Coordinator-authored acceptance instrument for `tools/outgoing_scan.py`. It is
deliberately NOT written by the worker that extracted the scanner: an acceptance
case authored by the implementer tests the implementation's own assumptions.

Every injected value is synthetic. No real credential, key, token, or personal
datum appears here or is ever read from the environment. The repository is
created under a caller-supplied temporary directory and has no remote.

Usage:
    python3 inject_7_surfaces.py /path/to/throwaway-dir
Prints the repository path, the base SHA, the head SHA, and the branch name.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Synthetic, obviously-fake values. Assembled at runtime so this source file
# itself does not carry a literal that a scanner would flag.
#
# Each surface must carry a value that genuinely belongs to a rule class the
# scanner claims to enforce. An injection outside every rule class does not test
# the gate — it tests the test. A first draft of this file failed that way on
# five of seven surfaces: a malformed key shape, a repo-relative path with no
# machine root, and a neutral e-mail address that names nothing private.
FAKE_TOKEN = "AKIA" + "IOSFODNN7EXAMPLE"  # published documentation key: AKIA + 16
FAKE_UUID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
FAKE_HOME_PATH = "/Users/" + "exampleuser" + "/private/orchestration"
PRIVATE_TERM = "runtime-pack"  # stands in for a private operational vocabulary term

# surface -> the rule class that must catch it
SURFACES = {
    "blob-content": "universal / credential shape",
    "path-name": "vocabulary / private term",
    "commit-message": "universal / machine path",
    "author-identity": "vocabulary / private term",
    "tag-object": "universal / machine path + vocabulary / private term",
    "ref-name": "vocabulary / private term",
    "generated-identifier": "universal / UUID-shaped identifier",
}


def run(repo: Path, *args: str, env_extra: dict[str, str] | None = None) -> str:
    import os

    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def build(root: Path) -> dict[str, str]:
    repo = root / "leaky-fixture"
    repo.mkdir(parents=True)
    run(repo.parent, "init", "-q", "-b", "main", str(repo))
    run(repo, "config", "user.name", "Fixture Author")
    run(repo, "config", "user.email", "fixture@example.invalid")

    # Clean base commit — the scan range starts here, so the base must be clean.
    (repo / "README.md").write_text("# fixture\n\nA disposable repository.\n")
    run(repo, "add", "-A")
    run(repo, "commit", "-q", "-m", "Add a disposable fixture repository\n\n- Record what this repository is for\n- Keep the starting state clean")
    base = run(repo, "rev-parse", "HEAD")

    # Surface 6: ref name carries a private operational term.
    branch = f"feature/{PRIVATE_TERM}-internal-wiring"
    run(repo, "checkout", "-q", "-b", branch)

    # Surface 1: credential-shaped literal inside a tracked file.
    (repo / "config.py").write_text(f'API_TOKEN = "{FAKE_TOKEN}"\n')

    # Surface 7: generated identifier committed inside a tracked file.
    (repo / "session.json").write_text(json.dumps({"session_id": FAKE_UUID}) + "\n")

    # Surface 2: tracked file whose PATH NAME carries a private term. A path
    # inside a repository can never be machine-rooted, so the rule class that
    # applies to a path name is the vocabulary rule, not the machine-path rule.
    nested = repo / f"{PRIVATE_TERM}-internal"
    nested.mkdir(parents=True)
    (nested / "notes.txt").write_text("notes\n")

    run(repo, "add", "-A")
    # Surfaces 3 and 4: message names a machine path; author name carries the
    # private term. A merely unfamiliar e-mail address is not a leak and must
    # not be treated as one — that would be a false positive, not a catch.
    run(
        repo,
        "-c",
        f"user.name={PRIVATE_TERM} release bot",
        "-c",
        "user.email=bot@example.invalid",
        "commit",
        "-q",
        "-m",
        f"Wire the internal client\n\n- Read settings from {FAKE_HOME_PATH}\n- Record the session identifier for replay",
    )
    head = run(repo, "rev-parse", "HEAD")

    # Surface 5: annotated tag whose name and message carry a private term and a
    # machine path. The tag object only enters an outgoing range when the tag ref
    # is scanned, so the acceptance run must scan it explicitly.
    run(repo, "tag", "-a", f"{PRIVATE_TERM}-v0", "-m", f"Internal {PRIVATE_TERM} checkpoint at {FAKE_HOME_PATH}")

    return {"repo": str(repo), "base": base, "head": head, "branch": branch, "tag": f"{PRIVATE_TERM}-v0"}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    info = build(root)
    print(json.dumps(info, indent=2))
    print("\nsurfaces injected: " + ", ".join(SURFACES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
