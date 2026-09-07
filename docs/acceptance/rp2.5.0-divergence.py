"""Every reproduced case where a governed read disagrees with real Git.

    python3 divergence_corpus.py [pack root]

This is the evidence A3 is derived against. Each row builds an ORDINARY repository
-- none of them is hostile, none names a program -- runs real Git and the governed
read, and records whether the two agree. A row is a DIVERGENCE when both answer and
the answers differ, an OVER-REFUSAL when real Git answers and the boundary refuses,
and an UNDER-REFUSAL when the boundary answers and real Git refuses.

The point of collecting them in one place: they are not fifteen defects. They are
one class, and the design that replaces them has to be measured against all of it.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools"))
import gitread                                                        # noqa: E402

BASE = Path(tempfile.mkdtemp(prefix="rp250-divergence-"))
ROWS = []


def git(*arguments, cwd):
    return subprocess.run(["git", *arguments], cwd=str(cwd), capture_output=True, text=True)


def repo(name):
    d = BASE / name
    d.mkdir(parents=True)
    git("init", "-q", "-b", "main", ".", cwd=d)
    git("config", "user.email", "t@e.invalid", cwd=d)
    git("config", "user.name", "T", cwd=d)
    return d


def commit(d, name="a.txt", body="one\n"):
    (d / name).write_text(body)
    git("add", "-A", cwd=d)
    git("commit", "-qm", "c", cwd=d)


def row(label, d, *arguments, kind="config"):
    real = git(*arguments, cwd=d)
    try:
        got, refused = gitread._run(d, *arguments), None
    except Exception as exc:                                          # noqa: BLE001
        got, refused = None, f"{type(exc).__name__}"
    if refused is None and real.returncode == 0:
        verdict = "agree" if got.strip() == real.stdout.strip() else "DIVERGENCE"
    elif refused is not None and real.returncode == 0:
        verdict = "OVER-REFUSAL"
    elif refused is None and real.returncode != 0:
        verdict = "UNDER-REFUSAL"
    else:
        verdict = "agree (both refuse)"
    ROWS.append((label, kind, verdict,
                 (real.stdout.strip() if real.returncode == 0 else f"<rc={real.returncode}>")[:38],
                 (got.strip() if refused is None else f"<{refused}>")[:38]))


# --- repository-local configuration that changes what an answer SAYS -----------
for setting, arguments, prepare in (
    ("status.showUntrackedFiles=no", ("status", "--porcelain"), None),
    ("core.quotepath=false", ("status", "--porcelain"), None),
    ("core.abbrev=4", ("rev-parse", "--short", "HEAD"), None),
    ("diff.renames=false", ("diff", "--cached", "--name-status"), "rename"),
    ("diff.noprefix=true", ("diff",), "dirty"),
):
    key, value = setting.split("=")
    d = repo(key.replace(".", "_"))
    commit(d)
    if prepare == "rename":
        git("mv", "a.txt", "b.txt", cwd=d)
    elif prepare == "dirty":
        (d / "a.txt").write_text("two\n")
    else:
        (d / "café.txt").write_text("y\n")
    git("config", key, value, cwd=d)
    row(setting, d, *arguments)

# --- per-worktree git-directory state -----------------------------------------
d = repo("reflog")
for body in ("one\n", "two\n", "three\n"):
    commit(d, body=body)
row("reflog: log -g", d, "log", "-g", "-1", "--format=%s", kind="ref state")
row("reflog: rev-parse HEAD@{1}", d, "rev-parse", "HEAD@{1}", kind="ref state")

d = repo("merge")
commit(d, body="one\n")
git("checkout", "-q", "-b", "side", cwd=d)
commit(d, name="s.txt", body="side\n")
git("checkout", "-q", "main", cwd=d)
commit(d, body="two\n")
git("merge", "--no-commit", "--no-ff", "side", cwd=d)
row("pseudo-ref: rev-parse MERGE_HEAD", d, "rev-parse", "MERGE_HEAD", kind="ref state")

width = max(len(r[0]) for r in ROWS) + 2
print(f"{'case':{width}} {'kind':11} {'verdict':20} {'real git':40} boundary")
divergent = 0
for label, kind, verdict, real, got in ROWS:
    divergent += verdict != "agree" and not verdict.startswith("agree")
    print(f"{label:{width}} {kind:11} {verdict:20} {real!r:40} {got!r}")
print(f"\n{len(ROWS)} ordinary repositories, {divergent} where the governed read does not match "
      f"real Git. None of them is hostile and none names a program.")
print(f"fixtures {BASE}")
sys.exit(1 if divergent else 0)
