"""Exact byte/refusal differential corpus for the Git read boundary.

This is deliberately a small test runner rather than a pytest module.  Each
comparison makes the fixture twice at the same pathname, once for each
checkout, and calls the public ``gitread._run`` entry point in a fresh Python
process.  The two runs therefore cannot share an index, stat cache, ref store,
or sterile-build scratch directory.

The corpus contains no submodules and no repository configuration which names
a program.  It is intended to be run from the candidate checkout::

    python3 docs/acceptance/rp2.5.0-floor-differential.py

The optional first argument is the candidate checkout.  The frozen checkout is
the path recorded in ``FROZEN_TOOLS`` below, matching the acceptance brief.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


CANDIDATE_ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
FROZEN_ROOT = Path(os.environ["FLOOR_FROZEN_ROOT"]).resolve()
FROZEN_TOOLS = FROZEN_ROOT / "tools"

PINNED_DATE = "2020-01-02T03:04:05+0000"
BASE_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_AUTHOR_DATE": PINNED_DATE,
    "GIT_COMMITTER_DATE": PINNED_DATE,
    "GIT_TERMINAL_PROMPT": "0",
    "LC_ALL": "C",
    "LANG": "C",
}


@dataclass
class Context:
    subject: Path
    head: str = "HEAD"
    parent: str = "HEAD^"
    branch: str = "main"
    side: str = "side"
    bundle: Path | None = None
    pack_index: Path | None = None
    remote: Path | None = None
    paths: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


def env_for_git() -> dict[str, str]:
    env = os.environ.copy()
    env.update(BASE_ENV)
    return env


def run_git(*args: str | Path, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *(str(arg) for arg in args)], cwd=str(cwd) if cwd else None,
        env=env_for_git(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=check,
    )


def init_repo(path: Path, *, bare: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if bare:
        run_git("init", "-q", "--bare", path)
        run_git("config", "user.email", "t@e.invalid", cwd=path)
        run_git("config", "user.name", "T", cwd=path)
    else:
        run_git("init", "-q", "-b", "main", path)
        run_git("config", "user.email", "t@e.invalid", cwd=path)
        run_git("config", "user.name", "T", cwd=path)
    return path


def write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")


def commit(repo: Path, message: str) -> str:
    run_git("add", "-A", cwd=repo)
    run_git("commit", "-qm", message, cwd=repo)
    return run_git("rev-parse", "HEAD", cwd=repo).stdout.decode().strip()


def ordinary(repo: Path, *, worktree_changes: bool = True, history: bool = True) -> Context:
    init_repo(repo)
    write(repo / "README.md", "first\n")
    write(repo / "dir" / "alpha.txt", "alpha\n")
    write(repo / "modified.txt", "before\n")
    write(repo / "staged.txt", "before-stage\n")
    write(repo / "deleted.txt", "delete-me\n")
    write(repo / "exec.sh", "#!/bin/sh\necho ok\n")
    (repo / "exec.sh").chmod(0o755)
    write(repo / "typechange", "ordinary\n")
    write(repo / "target.txt", "target\n")
    os.symlink("target.txt", repo / "tracked-link")
    write(repo / "tab\tname.txt", "tab\n")
    write(repo / "line\nname.txt", "newline\n")
    write(repo / 'back\\slash"name.txt', "quote\n")
    write(repo / "café.txt", "non-ascii\n")
    write(repo / ".gitignore", "ignored*.tmp\nignored-dir/\n")
    first = commit(repo, "first")
    if history:
        write(repo / "README.md", "first\nsecond\n")
        write(repo / "history.txt", "history\n")
        second = commit(repo, "second")
    else:
        second = first
    ctx = Context(repo, paths={
        "ignored": "ignored.tmp", "normal": "README.md", "tracked": "modified.txt",
        "odd": "line\nname.txt", "type": "typechange", "deleted": "deleted.txt",
    })
    if worktree_changes:
        write(repo / "modified.txt", "after\n")
        write(repo / "staged.txt", "after-stage\n")
        run_git("add", "staged.txt", cwd=repo)
        (repo / "deleted.txt").unlink()
        (repo / "exec.sh").chmod(0o644)
        (repo / "typechange").unlink()
        os.symlink("target.txt", repo / "typechange")
        write(repo / "untracked.txt", "untracked\n")
        write(repo / "ignored.tmp", "ignored\n")
        write(repo / "ignored-dir" / "file.tmp", "ignored directory\n")
        write(repo / "tab\tname.txt", "tab changed\n")
    ctx.head = second
    ctx.parent = f"{second}^"
    return ctx


def build_empty(root: Path) -> Context:
    return Context(init_repo(root / "repo"))


def build_unborn(root: Path) -> Context:
    repo = init_repo(root / "repo")
    run_git("checkout", "-q", "-b", "unborn", cwd=repo)
    return Context(repo, branch="unborn")


def build_detached(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    run_git("checkout", "-q", "--detach", ctx.parent, cwd=ctx.subject)
    ctx.head = "HEAD"
    return ctx


def build_merge(root: Path, *, conflict: bool) -> Context:
    repo = init_repo(root / "repo")
    write(repo / "merge.txt", "base\n")
    commit(repo, "base")
    run_git("checkout", "-q", "-b", "side", cwd=repo)
    write(repo / "merge.txt", "side\n" if conflict else "side-only\n")
    commit(repo, "side")
    run_git("checkout", "-q", "main", cwd=repo)
    write(repo / "merge.txt", "main\n" if conflict else "main-only\n")
    commit(repo, "main")
    if conflict:
        run_git("merge", "side", cwd=repo, check=False)
    else:
        run_git("merge", "--no-commit", "--no-ff", "side", cwd=repo, check=False)
    return Context(repo, side="side", paths={"merge": "merge.txt"})


def build_stale(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    target = ctx.subject / "modified.txt"
    stat = target.stat()
    write(target, "change!\n")
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    return ctx


def build_split(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    run_git("update-index", "--split-index", cwd=ctx.subject)
    return ctx


def build_alternates(root: Path) -> Context:
    source = ordinary(root / "source", worktree_changes=False)
    repo = init_repo(root / "repo")
    alternate = source.subject / ".git" / "objects"
    write(repo / ".git" / "objects" / "info" / "alternates", str(alternate) + "\n")
    run_git("update-ref", "refs/heads/main", source.head, cwd=repo)
    return Context(repo, paths=source.paths)


def build_bare(root: Path) -> Context:
    source = ordinary(root / "source", worktree_changes=False)
    bare = init_repo(root / "repo.git", bare=True)
    run_git("--git-dir", bare, "fetch", "-q", source.subject, f"{source.head}:refs/heads/main")
    run_git("--git-dir", bare, "symbolic-ref", "HEAD", "refs/heads/main")
    return Context(bare, head="HEAD", parent=f"{source.head}^", remote=bare)


def build_linked(root: Path) -> Context:
    main = ordinary(root / "main", worktree_changes=False)
    linked = root / "linked"
    run_git("worktree", "add", "-q", "-b", "linked", linked, main.head, cwd=main.subject)
    return Context(linked, branch="linked", parent=f"{main.head}^", remote=main.subject)


def build_git_file(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    gitdir = ctx.subject / ".git"
    moved = ctx.subject / "actual-gitdir"
    gitdir.rename(moved)
    write(ctx.subject / ".git", "gitdir: actual-gitdir\n")
    return ctx


def build_nested(root: Path) -> Context:
    repo = init_repo(root / "repo")
    write(repo / "inner" / "data.txt", "outer tracked data\n")
    commit(repo, "outer")
    inner = init_repo(repo / "inner")
    write(inner / "inner.txt", "inner\n")
    commit(inner, "inner")
    return Context(repo, paths={"nested": "inner/data.txt"})


def build_reflog(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    for index in range(3):
        write(ctx.subject / "reflog.txt", f"reflog {index}\n")
        commit(ctx.subject, f"reflog {index}")
    ctx.head = "HEAD"
    ctx.parent = "HEAD@{1}"
    return ctx


def build_grafts(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    for index in range(2):
        write(ctx.subject / f"graft-{index}.txt", f"graft {index}\n")
        commit(ctx.subject, f"graft {index}")
    head = run_git("rev-parse", "HEAD", cwd=ctx.subject).stdout.decode().strip()
    info = ctx.subject / ".git" / "info"
    info.mkdir(exist_ok=True)
    write(info / "grafts", head + "\n")
    return ctx


def build_packed_refs(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    ctx.tags = []
    for index in range(4):
        tag = f"release-{index}"
        run_git("tag", tag, cwd=ctx.subject)
        ctx.tags.append(tag)
    run_git("pack-refs", "--all", "--prune", cwd=ctx.subject)
    return ctx


def build_many_refs(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    for index in range(80):
        run_git("update-ref", f"refs/heads/topic/{index:03d}", ctx.head, cwd=ctx.subject)
    ctx.tags = []
    for index in range(40):
        tag = f"tag-{index:03d}"
        run_git("tag", tag, ctx.head, cwd=ctx.subject)
        ctx.tags.append(tag)
    return ctx


def build_sparse(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    run_git("sparse-checkout", "init", "--cone", cwd=ctx.subject)
    run_git("sparse-checkout", "set", "dir", cwd=ctx.subject)
    return ctx


def build_head_symlink(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    head = ctx.subject / ".git" / "HEAD"
    head.unlink()
    os.symlink("refs/heads/main", head)
    return ctx


def add_pack_and_bundle(ctx: Context) -> None:
    """Give every populated fixture the same two object-read surfaces."""
    if not (ctx.subject / "HEAD").exists() and not (ctx.subject / "refs").exists():
        # A bare repository always has HEAD; an empty worktree has no commit.
        pass
    result = run_git("rev-parse", "--git-dir", cwd=ctx.subject, check=False)
    if result.returncode != 0:
        return
    gitdir = Path(result.stdout.decode().strip())
    if not gitdir.is_absolute():
        gitdir = (ctx.subject / gitdir).resolve()
    head = run_git("rev-parse", "--verify", "HEAD", cwd=ctx.subject, check=False)
    if head.returncode != 0:
        return
    bundle = ctx.subject.parent / "all.bundle"
    made = run_git("bundle", "create", bundle, "--all", cwd=ctx.subject, check=False)
    if made.returncode == 0:
        ctx.bundle = bundle
    run_git("repack", "-ad", cwd=ctx.subject, check=False)
    indexes = sorted((gitdir / "objects" / "pack").glob("*.idx"))
    if indexes:
        ctx.pack_index = indexes[0]


def make_fixture(name: str, root: Path) -> Context:
    builders = {
        "ordinary": lambda: ordinary(root / "repo"),
        "paths-c-quoted": lambda: ordinary(root / "repo"),
        "symlink-path": lambda: ordinary(root / "repo", worktree_changes=False),
        "executable-change": lambda: ordinary(root / "repo"),
        "type-change": lambda: ordinary(root / "repo"),
        "deleted-file": lambda: ordinary(root / "repo"),
        "ignored-file": lambda: ordinary(root / "repo"),
        "empty": lambda: build_empty(root),
        "detached-head": lambda: build_detached(root),
        "unborn-branch": lambda: build_unborn(root),
        "merge-in-progress": lambda: build_merge(root, conflict=False),
        "conflicted-index": lambda: build_merge(root, conflict=True),
        "stale-stat": lambda: build_stale(root),
        "split-index": lambda: build_split(root),
        "object-alternates": lambda: build_alternates(root),
        "bare-repository": lambda: build_bare(root),
        "linked-worktree": lambda: build_linked(root),
        "git-as-file": lambda: build_git_file(root),
        "nested-repository": lambda: build_nested(root),
        "reflogs": lambda: build_reflog(root),
        "info-grafts": lambda: build_grafts(root),
        "packed-refs": lambda: build_packed_refs(root),
        "many-refs": lambda: build_many_refs(root),
        "sparse-checkout": lambda: build_sparse(root),
        "head-symlink": lambda: build_head_symlink(root),
    }
    ctx = builders[name]()
    add_pack_and_bundle(ctx)
    if ctx.remote is None:
        ctx.remote = ctx.subject
    return ctx


def p(ctx: Context, key: str, default: str) -> str:
    return ctx.paths.get(key, default)


def forms(ctx: Context) -> list[tuple[str, tuple[str, ...]]]:
    """The read-form catalogue, applied to every fixture where Git accepts it."""
    h, par = ctx.head, ctx.parent
    ignored = p(ctx, "ignored", "ignored.tmp")
    normal = p(ctx, "normal", "README.md")
    odd = p(ctx, "odd", "line\nname.txt")
    bundle = str(ctx.bundle or ctx.subject.parent / "missing.bundle")
    pack = str(ctx.pack_index or ctx.subject.parent / "missing.idx")
    remote = str(ctx.remote or ctx.subject)
    return [
        ("bundle/list-heads", ("bundle", "list-heads", bundle)),
        ("bundle/verify", ("bundle", "verify", bundle)),
        ("bundle/unbundle-dry-run", ("bundle", "unbundle-dry-run", bundle)),
        ("cat-file/type", ("cat-file", "-t", h)),
        ("cat-file/size", ("cat-file", "-s", h)),
        ("cat-file/exists", ("cat-file", "-e", h)),
        ("cat-file/commit", ("cat-file", "commit", h)),
        ("cat-file/pretty", ("cat-file", "-p", h)),
        ("cat-file/all-batch-check", ("cat-file", "--batch-all-objects", "--batch-check")),
        ("cat-file/batch-check-input", ("cat-file", "--batch-check")),
        ("cat-file/batch-input", ("cat-file", "--batch")),
        ("check-ignore/path", ("check-ignore", ignored)),
        ("check-ignore/no-index", ("check-ignore", "--no-index", ignored)),
        ("check-ignore/verbose", ("check-ignore", "-v", ignored)),
        ("check-ignore/nul", ("check-ignore", "-z", ignored)),
        ("check-ignore/stdin", ("check-ignore", "--stdin")),
        ("check-ignore/stdin-nul", ("check-ignore", "--stdin", "-z")),
        ("config/list", ("config", "--list")),
        ("config/list-short", ("config", "-l")),
        ("config/list-nul", ("config", "--null", "--list")),
        ("config/get-user", ("config", "--get", "user.name")),
        ("config/get-all-user", ("config", "--get-all", "user.name")),
        ("config/get-regexp", ("config", "--get-regexp", "^user\\.")),
        ("config/get-missing", ("config", "--get", "does.not.exist")),
        ("config/local-list", ("config", "--local", "--list")),
        ("diff/plain", ("diff", h)),
        ("diff/cached", ("diff", "--cached")),
        ("diff/stat", ("diff", "--stat", h)),
        ("diff/name-only", ("diff", "--name-only", h)),
        ("diff/name-status", ("diff", "--name-status", h)),
        ("diff/numstat", ("diff", "--numstat", h)),
        ("diff/raw", ("diff", "--raw", h)),
        ("diff/raw-nul", ("diff", "--raw", "-z", h)),
        ("diff/name-only-nul", ("diff", "--name-only", "-z", h)),
        ("diff/name-status-nul", ("diff", "--name-status", "-z", h)),
        ("diff/shortstat", ("diff", "--shortstat", h)),
        ("diff/summary", ("diff", "--summary", h)),
        ("diff/ignore-submodules-none", ("diff", "--ignore-submodules=none", h)),
        ("diff/ignore-submodules-untracked", ("diff", "--ignore-submodules=untracked", h)),
        ("diff/ignore-submodules-dirty", ("diff", "--ignore-submodules=dirty", h)),
        ("diff/ignore-submodules-all", ("diff", "--ignore-submodules=all", h)),
        ("diff-index/plain", ("diff-index", h)),
        ("diff-index/cached", ("diff-index", "--cached", h)),
        ("diff-index/stat", ("diff-index", "--stat", h)),
        ("diff-index/name-status", ("diff-index", "--name-status", h)),
        ("diff-index/numstat", ("diff-index", "--numstat", h)),
        ("diff-index/raw-nul", ("diff-index", "--raw", "-z", h)),
        ("diff-index/name-only-nul", ("diff-index", "--name-only", "-z", h)),
        ("diff-index/name-status-nul", ("diff-index", "--name-status", "-z", h)),
        ("diff-index/ignore-submodules-untracked", ("diff-index", "--ignore-submodules=untracked", h)),
        ("diff-index/ignore-submodules-dirty", ("diff-index", "--ignore-submodules=dirty", h)),
        ("diff-index/ignore-submodules", ("diff-index", "--ignore-submodules=all", h)),
        ("diff-tree/plain", ("diff-tree", "-r", h)),
        ("diff-tree/root", ("diff-tree", "--root", "-r", h)),
        ("diff-tree/stat", ("diff-tree", "--stat", "-r", h)),
        ("diff-tree/name-only", ("diff-tree", "--name-only", "-r", h)),
        ("diff-tree/name-only-nul", ("diff-tree", "--name-only", "-z", "-r", h)),
        ("diff-tree/name-status-nul", ("diff-tree", "--name-status", "-z", "-r", h)),
        ("diff-tree/numstat", ("diff-tree", "--numstat", "-r", h)),
        ("diff-tree/raw-nul", ("diff-tree", "--raw", "-z", "-r", h)),
        ("for-each-ref/all", ("for-each-ref",)),
        ("for-each-ref/format", ("for-each-ref", "--format=%(objectname) %(refname)")),
        ("for-each-ref/count", ("for-each-ref", "--count=3")),
        ("for-each-ref/sort", ("for-each-ref", "--sort=-refname")),
        ("for-each-ref/heads", ("for-each-ref", "refs/heads")),
        ("log/oneline", ("log", "--oneline")),
        ("log/format-nul", ("log", "--format=%H%x00%P%x00%s")),
        ("log/stat", ("log", "--stat")),
        ("log/name-only", ("log", "--name-only")),
        ("log/name-status", ("log", "--name-status")),
        ("log/numstat", ("log", "--numstat")),
        ("log/raw", ("log", "--raw")),
        ("log/raw-nul", ("log", "--raw", "-z")),
        ("log/name-only-nul", ("log", "--name-only", "-z")),
        ("log/name-status-nul", ("log", "--name-status", "-z")),
        ("ls-files/cached", ("ls-files", "--cached")),
        ("ls-files/stage", ("ls-files", "--stage")),
        ("ls-files/deleted", ("ls-files", "--deleted")),
        ("ls-files/modified", ("ls-files", "--modified")),
        ("ls-files/others", ("ls-files", "--others", "--exclude-standard")),
        ("ls-files/ignored", ("ls-files", "--ignored", "--exclude-standard")),
        ("ls-files/eol", ("ls-files", "--eol")),
        ("ls-files/nul", ("ls-files", "-z")),
        ("ls-files/stage-nul", ("ls-files", "--stage", "-z")),
        ("ls-remote/plain", ("ls-remote", remote)),
        ("ls-remote/heads", ("ls-remote", "--heads", remote)),
        ("ls-remote/tags", ("ls-remote", "--tags", remote)),
        ("ls-remote/refs", ("ls-remote", "--refs", remote)),
        ("ls-remote/symref", ("ls-remote", "--symref", remote)),
        ("ls-tree/plain", ("ls-tree", h)),
        ("ls-tree/recursive", ("ls-tree", "-r", h)),
        ("ls-tree/name-only", ("ls-tree", "-r", "--name-only", h)),
        ("ls-tree/name-status-nul", ("ls-tree", "-r", "--name-status", "-z", h)),
        ("ls-tree/long", ("ls-tree", "-r", "--long", h)),
        ("ls-tree/object-only", ("ls-tree", "-r", "--object-only", h)),
        ("merge-base/plain", ("merge-base", h, par)),
        ("merge-base/all", ("merge-base", "--all", h, par)),
        ("merge-base/is-ancestor", ("merge-base", "--is-ancestor", par, h)),
        ("rev-list/plain", ("rev-list", h)),
        ("rev-list/count", ("rev-list", "--count", h)),
        ("rev-list/objects", ("rev-list", "--objects", h)),
        ("rev-list/all", ("rev-list", "--all")),
        ("rev-list/parents", ("rev-list", "--parents", h)),
        ("rev-list/timestamp", ("rev-list", "--timestamp", h)),
        ("rev-list/header", ("rev-list", "--header", h)),
        ("rev-list/disk-usage", ("rev-list", "--disk-usage", h)),
        ("rev-list/stdin", ("rev-list", "--stdin")),
        ("rev-parse/verify", ("rev-parse", "--verify", h)),
        ("rev-parse/short", ("rev-parse", "--short", h)),
        ("rev-parse/symbolic", ("rev-parse", "--symbolic", h)),
        ("rev-parse/full-name", ("rev-parse", "--symbolic-full-name", h)),
        ("rev-parse/abbrev-ref", ("rev-parse", "--abbrev-ref", h)),
        ("rev-parse/toplevel", ("rev-parse", "--show-toplevel")),
        ("rev-parse/git-dir", ("rev-parse", "--git-dir")),
        ("rev-parse/common-dir", ("rev-parse", "--git-common-dir")),
        ("rev-parse/worktree", ("rev-parse", "--is-inside-work-tree")),
        ("rev-parse/bare", ("rev-parse", "--is-bare-repository")),
        ("rev-parse/all", ("rev-parse", "--all")),
        ("rev-parse/heads", ("rev-parse", "--branches")),
        ("show/plain", ("show", h)),
        ("show/stat", ("show", "--stat", h)),
        ("show/name-only", ("show", "--name-only", h)),
        ("show/name-status", ("show", "--name-status", h)),
        ("show/numstat", ("show", "--numstat", h)),
        ("show/raw", ("show", "--raw", h)),
        ("show/raw-nul", ("show", "--raw", "-z", h)),
        ("show/name-only-nul", ("show", "--name-only", "-z", h)),
        ("show/name-status-nul", ("show", "--name-status", "-z", h)),
        ("show/numstat-nul", ("show", "--numstat", "-z", h)),
        ("show/no-patch-format", ("show", "--no-patch", "--format=%s", h)),
        ("show-ref/all", ("show-ref",)),
        ("show-ref/heads", ("show-ref", "--heads")),
        ("show-ref/tags", ("show-ref", "--tags")),
        ("show-ref/hash", ("show-ref", "--hash")),
        ("show-ref/verify", ("show-ref", "--verify", "refs/heads/main")),
        ("show-ref/missing", ("show-ref", "--verify", "refs/heads/missing")),
        ("status/plain", ("status",)),
        ("status/short", ("status", "--short")),
        ("status/porcelain-v1", ("status", "--porcelain")),
        ("status/porcelain-v2", ("status", "--porcelain=v2")),
        ("status/uall", ("status", "--porcelain", "-uall")),
        ("status/uno", ("status", "--porcelain", "-uno")),
        ("status/ignore-none", ("status", "--porcelain", "--ignore-submodules=none")),
        ("status/ignore-untracked", ("status", "--porcelain", "--ignore-submodules=untracked")),
        ("status/ignore-dirty", ("status", "--porcelain", "--ignore-submodules=dirty")),
        ("status/ignore-all", ("status", "--porcelain", "--ignore-submodules=all")),
        ("status/branch", ("status", "--porcelain=v2", "--branch")),
        ("status/long", ("status", "--long")),
        ("status/nul-v1", ("status", "--porcelain", "-z")),
        ("status/nul-v2", ("status", "--porcelain=v2", "-z")),
        ("status/ignored-nul", ("status", "--porcelain=v2", "--ignored", "-z")),
        ("verify-pack/verbose", ("verify-pack", "-v", pack)),
        ("verify-pack/stat-only", ("verify-pack", "--stat-only", pack)),
    ]


def input_for(ctx: Context, label: str) -> bytes | None:
    h = ctx.head
    ignored = p(ctx, "ignored", "ignored.tmp")
    if label == "cat-file/batch-check-input":
        return (h + "\n").encode()
    if label == "cat-file/batch-input":
        return (h + "\n").encode()
    if label == "check-ignore/stdin":
        return (ignored + "\n").encode()
    if label == "check-ignore/stdin-nul":
        return (ignored + "\0").encode()
    if label == "rev-list/stdin":
        return (h + "\n").encode()
    return None


CHILD = r'''
import base64, json, sys
sys.path.insert(0, sys.argv[1])
import gitread
input_value = base64.b64decode(sys.argv[3]) if sys.argv[3] else None
try:
    value = gitread._run(sys.argv[2], *sys.argv[4:], text=False, input_value=input_value)
    if not isinstance(value, bytes):
        value = str(value).encode("utf-8", "surrogateescape")
    result = {"kind": "answer", "bytes": base64.b64encode(value).decode("ascii")}
except BaseException as exc:
    result = {"kind": "refusal", "type": type(exc).__name__, "message": str(exc)}
print(json.dumps(result, ensure_ascii=True, sort_keys=True))
'''


def invoke(tools: Path, subject: Path, arguments: tuple[str, ...], input_value: bytes | None = None) -> dict:
    env = env_for_git()
    env["PYTHONUNBUFFERED"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", CHILD, str(tools), str(subject),
         base64.b64encode(input_value or b"").decode("ascii"), *arguments],
        cwd=str(subject), env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return {
            "kind": "runner-failure", "returncode": result.returncode,
            "stdout": result.stdout.decode("utf-8", "backslashreplace"),
            "stderr": result.stderr.decode("utf-8", "backslashreplace"),
        }
    try:
        return json.loads(result.stdout.decode("utf-8"))
    except Exception as exc:  # pragma: no cover - makes a broken runner visible
        return {"kind": "runner-failure", "returncode": result.returncode,
                "stdout": result.stdout.decode("utf-8", "backslashreplace"),
                "stderr": f"invalid child JSON: {exc}: {result.stderr!r}"}


def build_and_invoke(name: str, tools: Path, root: Path, label: str) -> tuple[dict, tuple[str, ...]]:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    ctx = make_fixture(name, root)
    # The form catalogue is built from this same pathname.  Both sides get the
    # same generated bundle/pack spelling because each side is rebuilt at the
    # same path after the previous side has been discarded.
    arguments = dict(forms(ctx))[label]
    return invoke(tools, ctx.subject, arguments), arguments


def render_bytes(outcome: dict) -> str:
    if outcome.get("kind") == "answer":
        raw = base64.b64decode(outcome["bytes"])
        return repr(raw)
    if outcome.get("kind") == "refusal":
        return f"{outcome['type']}: {outcome['message']}"
    return json.dumps(outcome, sort_keys=True)


def exact_outcome(outcome: dict) -> str:
    """A lossless, human-readable representation for REPORT.md."""
    if outcome.get("kind") == "answer":
        return f"answer bytes: {base64.b64decode(outcome['bytes'])!r}"
    if outcome.get("kind") == "refusal":
        return f"refusal type: {outcome['type']}\nrefusal message: {outcome['message']!r}"
    return "runner failure: " + json.dumps(outcome, ensure_ascii=True, sort_keys=True)


def write_report(rows: list[dict], fixture_names: list[str]) -> None:
    differences = [row for row in rows if not row["same"]]
    forms_per_fixture = len(rows) // len(fixture_names) if fixture_names else 0
    lines = [
        "# RP 2.5.0 frozen-floor differential corpus",
        "",
        "This report is generated by `docs/acceptance/rp2.5.0-floor-differential.py`.",
        "The candidate and frozen release were run in separate child processes with",
        "`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_SYSTEM=/dev/null`, pinned commit",
        "dates, and `text=False`. Answers below are Python `repr(bytes)` values; refusals",
        "include the exact exception type and `str(exception)` message.",
        "",
        f"- Total comparisons: **{len(rows)}** ({len(fixture_names)} fixtures × "
        f"{forms_per_fixture} read forms).",
        f"- Exact differences: **{len(differences)}**.",
        "- Submodules: none.",
        "- Repository configuration naming a helper program: none.",
        "",
        "## Result",
        "",
    ]
    if differences:
        lines.extend([
            "The candidate is **not strictly non-regressive** against the frozen release "
            "for this measured population. Each row below is an exact answer/refusal "
            "difference and is not normalized or waived.",
            "",
        ])
        for index, row in enumerate(differences, 1):
            lines.extend([
                f"### Difference {index}: `{row['fixture']}` / `{row['form']}`",
                "",
                f"Arguments: `{row['arguments']!r}`",
                "",
                "Candidate:",
                "```text",
                exact_outcome(row["candidate"]),
                "```",
                "",
                "Frozen previous release:",
                "```text",
                exact_outcome(row["frozen"]),
                "```",
                "",
            ])
    else:
        lines.extend([
            "No differences found. This establishes equality only for the measured "
            f"population of {len(rows)} comparisons: {len(fixture_names)} independently "
            f"built fixtures and {forms_per_fixture} forms per fixture. It is not evidence "
            "about omitted forms or fixtures listed below.",
            "",
        ])
    lines.extend([
        "## Fixture population",
        "",
        ", ".join(f"`{name}`" for name in fixture_names) + ".",
        "",
        "The ordinary-family fixtures include C-quoted paths (tab, newline, backslash, "
        "quote, and non-ASCII), a symlink, executable-bit change, type change, deletion, "
        "and ignored files. Separate rows cover empty/unborn/detached state, merge and "
        "conflict state, stale stat data, split index, alternates, bare and linked "
        "repositories, `.git` as a file, nested repository, reflog, grafts, packed and "
        "many refs, sparse checkout, and a symlinked HEAD.",
        "",
        "## Forms and limits",
        "",
        "The form catalogue covers every candidate `READ_ONLY_VERBS` member: bundle "
        "read subcommands, cat-file object and batch reads, check-ignore ordinary/NUL/stdin "
        "reads, config read-only shapes, diff/diff-index/diff-tree patch/stat/name/numstat/raw "
        "and NUL/ignore-submodule forms, for-each-ref, log, ls-files, ls-remote, ls-tree, "
        "merge-base, rev-list (including stdin), rev-parse, show, show-ref, status porcelain "
        "v1/v2/short/untracked/ignore-submodule/branch/long/NUL forms, and verify-pack.",
        "",
        "Not covered, with reasons:",
        "",
        "- `cat-file --batch-command` and its flush protocol: it is an interactive command "
        "stream rather than a single read form; the single-request `--batch` and "
        "`--batch-check` forms are covered.",
        "- `check-ignore --stdin` and the single-request cat-file/rev-list stdin forms are "
        "covered; pathspec or object forms requiring a caller-managed interactive stream "
        "beyond one request are not separately enumerated.",
        "- Transport-enabled `ls-remote` calls (`allow_transports=...`) are not invoked: the "
        "specified oracle is `_run(repo, *args)` and the corpus is offline; ordinary local "
        "target forms are covered and refusals are compared.",
        "- Git features requiring submodules are intentionally omitted per the task (the "
        "separate submodule corpus owns them).",
        "- Platform-specific case-insensitive filesystem spellings and unreadable-permission "
        "fixtures were not portable to this checkout; the corpus records the portable `.git` "
        "file, symlink, and HEAD-symlink forms.",
        "",
    ])
    # NOT into the checkout: this script ships, and a run that leaves a 100 KB
    # untracked file at the root makes `pack_pin.py` report the tree unpinned.
    # Default beside the system temp directory; `FLOOR_REPORT` overrides.
    report = Path(os.environ.get(
        "FLOOR_REPORT", Path(tempfile.gettempdir()) / "rp2.5.0-floor-differential-REPORT.md"))
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"report: {report}")


def main() -> int:
    fixture_names = [
        "ordinary", "empty", "detached-head", "unborn-branch", "merge-in-progress",
        "conflicted-index", "stale-stat", "split-index", "object-alternates",
        "bare-repository", "linked-worktree", "git-as-file", "nested-repository",
        "reflogs", "info-grafts", "packed-refs", "many-refs", "paths-c-quoted",
        "symlink-path", "executable-change", "type-change", "deleted-file", "ignored-file",
        "sparse-checkout", "head-symlink",
    ]
    rows: list[dict] = []
    stop_after = int(os.environ.get("RP250_STOP_AFTER", "0"))
    with tempfile.TemporaryDirectory(prefix="rp250-floor-", dir="/private/tmp") as temp:
        scratch = Path(temp)
        for fixture in fixture_names:
            # The candidate and frozen populations are built independently at
            # the same pathname.  Each side then runs the complete form list
            # against its own fixture, so a frozen read that refreshes an
            # index cannot alter the candidate's fixture (or vice versa).
            comparison_root = scratch / "fixture"
            comparison_root.mkdir()
            candidate_context = make_fixture(fixture, comparison_root)
            candidate_forms = forms(candidate_context)
            candidate_results = {
                label: invoke(
                    CANDIDATE_ROOT / "tools", candidate_context.subject, arguments,
                    input_for(candidate_context, label),
                )
                for label, arguments in candidate_forms
            }
            shutil.rmtree(comparison_root)
            frozen_context = make_fixture(fixture, comparison_root)
            frozen_forms = forms(frozen_context)
            frozen_results = {
                label: invoke(
                    FROZEN_TOOLS, frozen_context.subject, arguments,
                    input_for(frozen_context, label),
                )
                for label, arguments in frozen_forms
            }
            if [label for label, _ in candidate_forms] != [label for label, _ in frozen_forms]:
                raise RuntimeError(f"fixture form catalogue changed between builds: {fixture}")
            for label, arguments in candidate_forms:
                candidate = candidate_results[label]
                frozen = frozen_results[label]
                same = candidate == frozen
                row = {
                    "fixture": fixture, "form": label, "arguments": list(arguments),
                    "candidate": candidate, "frozen": frozen, "same": same,
                }
                rows.append(row)
                print(
                    f"{'PASS' if same else 'DIFF':4} {fixture:20} {label:32}"
                    + (f" candidate={render_bytes(candidate)} frozen={render_bytes(frozen)}" if not same else ""),
                    flush=True,
                )
            if stop_after and len(rows) >= stop_after:
                    differences = [item for item in rows if not item["same"]]
                    print(f"\ncomparisons: {len(rows)}")
                    print(f"differences: {len(differences)}")
                    return 1 if differences else 0
            shutil.rmtree(comparison_root)
    differences = [row for row in rows if not row["same"]]
    write_report(rows, fixture_names)
    print(f"\ncomparisons: {len(rows)}")
    print(f"differences: {len(differences)}")
    if differences:
        print("The candidate is regressive for at least one exact answer/refusal row.")
    else:
        print("No differences found in this corpus.")
    return 1 if differences else 0


if __name__ == "__main__":
    raise SystemExit(main())
