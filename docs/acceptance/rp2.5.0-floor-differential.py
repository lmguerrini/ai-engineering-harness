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

# The original release corpus is intentionally retained byte-for-byte as a
# subset.  Keeping the widening labels explicit lets the generated report say
# how often a newly added spelling was refused by Git on both sides.
FLOOR_FIXTURE_COUNT = 25
FLOOR_FORM_COUNT = 153
ADDED_FORM_LABELS = frozenset({
    "cat-file/batch-check-format", "cat-file/batch-check-nul", "cat-file/batch-nul",
    "check-ignore/stdin-verbose-nul",
    "diff/pathspec", "diff/pathspec-nul", "diff/pathspec-glob",
    "diff-index/pathspec", "diff-index/pathspec-nul",
    "diff-tree/pathspec", "diff-tree/pathspec-nul",
    "for-each-ref/format-nul-atoms", "for-each-ref/format-peeled",
    "for-each-ref/points-at", "for-each-ref/merged", "for-each-ref/contains",
    "for-each-ref/stdin",
    "log/pathspec", "log/pathspec-nul",
    "ls-files/others-nul", "ls-files/ignored-nul", "ls-files/eol-nul",
    "ls-files/pathspec", "ls-files/pathspec-nul",
    "ls-remote/get-url", "ls-remote/symref-refs",
    "ls-tree/nul", "ls-tree/pathspec", "ls-tree/pathspec-nul",
    "merge-base/is-ancestor-reverse", "merge-base/octopus",
    "rev-list/range", "rev-list/range-count", "rev-list/max-count", "rev-list/skip",
    "rev-list/reverse", "rev-list/no-merges", "rev-list/objects-nul",
    "show/pathspec", "show/pathspec-nul",
    "show-ref/head", "show-ref/dereference", "show-ref/quiet-verify",
    "status/ignored", "status/uall-nul",
    "verify-pack/no-verbose", "verify-pack/no-stat-only",
})


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


def run_git_input(
    *args: str | Path, input_value: bytes, cwd: Path | None = None, check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a deterministic setup command whose input is repository data.

    This is only used to construct two Git trees which a checkout cannot
    represent on this filesystem: an empty directory in a tree and two paths
    which differ only in Unicode normalisation.  It does not run a helper or
    inspect the host; it gives Git literal object/tree records.
    """
    return subprocess.run(
        ["git", *(str(arg) for arg in args)], cwd=str(cwd) if cwd else None,
        env=env_for_git(), input=input_value, stdout=subprocess.PIPE,
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


def build_core_worktree(root: Path) -> Context:
    """A normal Git directory whose configured worktree is a sibling tree."""
    ctx = ordinary(root / "repo", worktree_changes=False)
    redirected = root / "redirected-worktree"
    shutil.copytree(ctx.subject, redirected, ignore=shutil.ignore_patterns(".git"))
    write(redirected / "redirected-only.txt", "this is the configured worktree\n")
    run_git("config", "core.worktree", str(redirected), cwd=ctx.subject)
    return ctx


def build_moved_main_worktree(root: Path) -> Context:
    """A linked worktree still valid after its main checkout was renamed."""
    main = ordinary(root / "main", worktree_changes=False)
    linked = root / "linked"
    run_git("worktree", "add", "-q", "-b", "moved-linked", linked, main.head, cwd=main.subject)
    moved = root / "main-moved"
    main.subject.rename(moved)
    gitfile = linked / ".git"
    old_gitdir = str(root / "main" / ".git" / "worktrees" / "linked")
    new_gitdir = str(moved / ".git" / "worktrees" / "linked")
    text = gitfile.read_text(encoding="utf-8")
    if old_gitdir not in text:
        raise RuntimeError("linked worktree gitfile did not name its original main worktree")
    write(gitfile, text.replace(old_gitdir, new_gitdir))
    return Context(linked, branch="moved-linked", parent=f"{main.head}^", remote=moved)


def build_worktree_config(root: Path) -> Context:
    """A linked worktree with a safe, non-sparse per-worktree setting."""
    main = ordinary(root / "main", worktree_changes=False)
    linked = root / "linked"
    run_git("worktree", "add", "-q", "-b", "configured", linked, main.head, cwd=main.subject)
    run_git("config", "extensions.worktreeConfig", "true", cwd=main.subject)
    # This is ordinary configuration data, not a filter/diff/transport/helper
    # setting.  It makes config.worktree a genuine second configuration root.
    run_git("config", "--worktree", "feature.manyFiles", "true", cwd=linked)
    return Context(linked, branch="configured", parent=f"{main.head}^", remote=main.subject)


def build_nested_three_levels(root: Path) -> Context:
    """Three independently initialised repositories nested in one another."""
    outer = init_repo(root / "repo")
    write(outer / "level-one" / "outer.txt", "outer\n")
    commit(outer, "outer")
    middle = init_repo(outer / "level-one")
    write(middle / "level-two" / "middle.txt", "middle\n")
    commit(middle, "middle")
    leaf = init_repo(middle / "level-two")
    write(leaf / "leaf.txt", "leaf\n")
    commit(leaf, "leaf")
    return Context(outer, paths={"nested": "level-one/outer.txt"})


def build_detached_tag(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    run_git("tag", "detached-release", ctx.head, cwd=ctx.subject)
    run_git("checkout", "-q", "--detach", "detached-release", cwd=ctx.subject)
    ctx.head = "HEAD"
    ctx.tags = ["detached-release"]
    return ctx


def build_tag_chain(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    run_git("tag", "-a", "annotated", "-m", "annotated release", ctx.head, cwd=ctx.subject)
    tag_object = run_git("rev-parse", "annotated^{tag}", cwd=ctx.subject).stdout.decode().strip()
    # update-ref deliberately makes a ref to the tag object itself rather than
    # peeling it, which is the tag-of-a-tag shape Git's porcelain elides.
    run_git("update-ref", "refs/tags/tag-of-tag", tag_object, cwd=ctx.subject)
    ctx.tags = ["annotated", "tag-of-tag"]
    return ctx


def build_empty_tree_commit(root: Path) -> Context:
    repo = init_repo(root / "repo")
    run_git("commit", "--allow-empty", "-qm", "empty tree", cwd=repo)
    return Context(repo)


def build_merge_after_merge(root: Path) -> Context:
    """Keep a conflict in progress after an earlier merge commit with two parents."""
    repo = init_repo(root / "repo")
    write(repo / "conflict.txt", "base\n")
    commit(repo, "base")
    run_git("checkout", "-q", "-b", "merge-side", cwd=repo)
    write(repo / "side.txt", "side\n")
    commit(repo, "side")
    run_git("checkout", "-q", "main", cwd=repo)
    write(repo / "main.txt", "main\n")
    commit(repo, "main")
    run_git("merge", "--no-ff", "-qm", "two-parent merge", "merge-side", cwd=repo)
    run_git("checkout", "-q", "-b", "conflict-side", cwd=repo)
    write(repo / "conflict.txt", "side conflict\n")
    commit(repo, "conflict side")
    run_git("checkout", "-q", "main", cwd=repo)
    write(repo / "conflict.txt", "main conflict\n")
    commit(repo, "main conflict")
    run_git("merge", "conflict-side", cwd=repo, check=False)
    return Context(repo, side="conflict-side", paths={"merge": "conflict.txt"})


def build_binary_and_long_name(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    write(ctx.subject / "binary.bin", b"binary\x00content\n")
    write(ctx.subject / ("long-" + "x" * 220 + ".txt"), "long name\n")
    commit(ctx.subject, "binary and long path")
    ctx.head, ctx.parent = "HEAD", "HEAD^"
    return ctx


def build_unicode_normalisation(root: Path) -> Context:
    """Put NFC and NFD names in one tree even on normalising filesystems."""
    repo = init_repo(root / "repo")
    nfc = "caf\u00e9.txt"
    nfd = "cafe\u0301.txt"
    write(repo / nfc, "normalised name\n")
    blob = run_git("hash-object", "-w", nfc, cwd=repo).stdout.decode().strip()
    for name in (nfc, nfd):
        run_git("update-index", "--add", "--cacheinfo", f"100644,{blob},{name}", cwd=repo)
    tree = run_git("write-tree", cwd=repo).stdout.decode().strip()
    revision = run_git("commit-tree", tree, "-m", "NFC and NFD names", cwd=repo).stdout.decode().strip()
    run_git("update-ref", "refs/heads/main", revision, cwd=repo)
    return Context(repo, paths={"normal": nfc})


def build_empty_directory_tree(root: Path) -> Context:
    """An empty directory is representable in a tree though not a checkout."""
    repo = init_repo(root / "repo")
    empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    tree = run_git_input(
        "mktree", input_value=f"040000 tree {empty_tree}\tempty-dir\n".encode(), cwd=repo,
    ).stdout.decode().strip()
    revision = run_git("commit-tree", tree, "-m", "tree has empty directory", cwd=repo).stdout.decode().strip()
    run_git("update-ref", "refs/heads/main", revision, cwd=repo)
    return Context(repo)


def build_ignore_case(root: Path, enabled: bool) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    write(ctx.subject / "CaseName.txt", "case-sensitive spelling\n")
    commit(ctx.subject, "case spelling")
    run_git("config", "core.ignoreCase", "true" if enabled else "false", cwd=ctx.subject)
    ctx.head, ctx.parent = "HEAD", "HEAD^"
    return ctx


def build_attributes(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    write(ctx.subject / ".gitattributes", "binary.bin -text\ntext.txt text\ncrlf.txt text eol=crlf\n")
    write(ctx.subject / "binary.bin", b"binary\x00data\n")
    write(ctx.subject / "text.txt", "text\n")
    write(ctx.subject / "crlf.txt", "CRLF by attribute\n")
    commit(ctx.subject, "attributes")
    write(ctx.subject / "text.txt", "changed text\n")
    ctx.head, ctx.parent = "HEAD", "HEAD^"
    return ctx


def build_answer_shaping(root: Path, key: str) -> Context:
    """A subject declaration whose omission changes an ordinary read answer."""
    ctx = ordinary(root / "repo", worktree_changes=False)
    if key == "core.excludesFile":
        declaration = ctx.subject / "declared-ignore"
        write(declaration, "*.tmp\n")
        run_git("config", key, str(declaration), cwd=ctx.subject)
        write(ctx.subject / "hidden.tmp", "hidden\n")
        write(ctx.subject / "visible", "visible\n")
        status = run_git("status", "--porcelain", cwd=ctx.subject).stdout
        assert b"hidden.tmp" not in status and b"visible" in status
    elif key == "status.showUntrackedFiles":
        run_git("config", key, "no", cwd=ctx.subject)
        write(ctx.subject / "hidden", "hidden\n")
        assert run_git("status", "--porcelain", cwd=ctx.subject).stdout == b""
    elif key == "core.attributesFile":
        declaration = ctx.subject / "declared-attributes"
        write(declaration, "*.txt -diff\n")
        run_git("config", key, str(declaration), cwd=ctx.subject)
        write(ctx.subject / "dir" / "alpha.txt", "answer shaped by attributes\n")
        assert b"Binary files" in run_git("diff", cwd=ctx.subject).stdout
    elif key == "core.abbrev":
        run_git("config", key, "12", cwd=ctx.subject)
        abbreviated = run_git("rev-parse", "--short", "HEAD", cwd=ctx.subject).stdout.strip()
        assert len(abbreviated) == 12
    else:
        raise ValueError(key)
    ctx.head, ctx.parent = "HEAD", "HEAD^"
    return ctx


def build_content_filter(root: Path) -> Context:
    """An active clean filter which makes the committed worktree genuinely clean."""
    ctx = ordinary(root / "repo", worktree_changes=False)
    run_git("config", "filter.redact.clean", "sed s/SECRET/REDACTED/", cwd=ctx.subject)
    write(ctx.subject / ".gitattributes", "filtered.txt filter=redact\n")
    write(ctx.subject / "filtered.txt", "value=SECRET\n")
    commit(ctx.subject, "filtered content")
    assert run_git("status", "--porcelain", cwd=ctx.subject).stdout == b""
    ctx.head, ctx.parent = "HEAD", "HEAD^"
    return ctx


def build_shallow_clone(root: Path) -> Context:
    source = ordinary(root / "source", worktree_changes=False)
    repo = root / "repo"
    run_git("clone", "-q", "--depth=1", f"file://{source.subject}", repo)
    return Context(repo, head="HEAD", parent="HEAD^", remote=repo)


def build_partial_clone(root: Path) -> Context:
    source = ordinary(root / "source", worktree_changes=False)
    run_git("config", "uploadpack.allowFilter", "true", cwd=source.subject)
    repo = root / "repo"
    run_git("clone", "-q", "--no-local", "--filter=blob:none", f"file://{source.subject}", repo)
    return Context(repo, head="HEAD", parent="HEAD^", remote=repo)


def build_many_untracked(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    for index in range(512):
        write(ctx.subject / "untracked" / f"entry-{index:04d}.txt", "untracked\n")
    return ctx


def build_literal_dotgit(root: Path) -> Context:
    ctx = ordinary(root / "repo", worktree_changes=False)
    # This is data, not a nested repository: it has no config, HEAD, or Git
    # metadata beyond a directory whose spelling is significant to walkers.
    write(ctx.subject / "ordinary-directory" / ".git" / "marker", "not a repository\n")
    return ctx


def set_git_state_read_only(ctx: Context, read_only: bool) -> None:
    """Lock the ordinary fixture's Git state, or make it removable again."""
    gitdir = ctx.subject / ".git"
    paths = [gitdir, *gitdir.rglob("*")]
    ordered = sorted(paths, key=lambda item: len(item.parts), reverse=read_only)
    for path in ordered:
        if path.is_symlink():
            continue
        if read_only:
            path.chmod(0o555 if path.is_dir() else 0o444)
        else:
            current = path.stat().st_mode
            path.chmod(current | 0o700 if path.is_dir() else current | 0o600)


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
        "core-worktree": lambda: build_core_worktree(root),
        "moved-main-worktree": lambda: build_moved_main_worktree(root),
        "worktree-config": lambda: build_worktree_config(root),
        "nested-three-levels": lambda: build_nested_three_levels(root),
        "detached-at-tag": lambda: build_detached_tag(root),
        "tag-chain": lambda: build_tag_chain(root),
        "empty-tree-commit": lambda: build_empty_tree_commit(root),
        "merge-after-merge": lambda: build_merge_after_merge(root),
        "binary-and-long-name": lambda: build_binary_and_long_name(root),
        "unicode-normalisation": lambda: build_unicode_normalisation(root),
        "empty-directory-tree": lambda: build_empty_directory_tree(root),
        "ignorecase-true": lambda: build_ignore_case(root, True),
        "ignorecase-false": lambda: build_ignore_case(root, False),
        "attributes-eol": lambda: build_attributes(root),
        "config-core-excludesfile": lambda: build_answer_shaping(root, "core.excludesFile"),
        "config-status-showuntrackedfiles": lambda: build_answer_shaping(
            root, "status.showUntrackedFiles",
        ),
        "config-core-attributesfile": lambda: build_answer_shaping(root, "core.attributesFile"),
        "config-core-abbrev": lambda: build_answer_shaping(root, "core.abbrev"),
        "config-content-filter": lambda: build_content_filter(root),
        "shallow-clone": lambda: build_shallow_clone(root),
        "partial-clone": lambda: build_partial_clone(root),
        "many-untracked": lambda: build_many_untracked(root),
        "literal-dotgit-directory": lambda: build_literal_dotgit(root),
        "read-only-git-state": lambda: ordinary(root / "repo", worktree_changes=False),
    }
    ctx = builders[name]()
    add_pack_and_bundle(ctx)
    if name == "read-only-git-state":
        set_git_state_read_only(ctx, True)
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
        ("cat-file/batch-check-format", (
            "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        )),
        ("cat-file/batch-check-nul", ("cat-file", "--batch-check", "-z")),
        ("cat-file/batch-nul", ("cat-file", "--batch", "-z")),
        ("check-ignore/path", ("check-ignore", ignored)),
        ("check-ignore/no-index", ("check-ignore", "--no-index", ignored)),
        ("check-ignore/verbose", ("check-ignore", "-v", ignored)),
        ("check-ignore/nul", ("check-ignore", "-z", ignored)),
        ("check-ignore/stdin", ("check-ignore", "--stdin")),
        ("check-ignore/stdin-nul", ("check-ignore", "--stdin", "-z")),
        ("check-ignore/stdin-verbose-nul", ("check-ignore", "--stdin", "-v", "-z")),
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
        ("diff/pathspec", ("diff", h, "--", normal)),
        ("diff/pathspec-nul", ("diff", "--name-status", "-z", h, "--", normal)),
        ("diff/pathspec-glob", ("diff", "--name-only", h, "--", ":(glob)**/*.txt")),
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
        ("diff-index/pathspec", ("diff-index", "--name-status", h, "--", normal)),
        ("diff-index/pathspec-nul", ("diff-index", "--name-status", "-z", h, "--", normal)),
        ("diff-tree/plain", ("diff-tree", "-r", h)),
        ("diff-tree/root", ("diff-tree", "--root", "-r", h)),
        ("diff-tree/stat", ("diff-tree", "--stat", "-r", h)),
        ("diff-tree/name-only", ("diff-tree", "--name-only", "-r", h)),
        ("diff-tree/name-only-nul", ("diff-tree", "--name-only", "-z", "-r", h)),
        ("diff-tree/name-status-nul", ("diff-tree", "--name-status", "-z", "-r", h)),
        ("diff-tree/numstat", ("diff-tree", "--numstat", "-r", h)),
        ("diff-tree/raw-nul", ("diff-tree", "--raw", "-z", "-r", h)),
        ("diff-tree/pathspec", ("diff-tree", "--root", "-r", "--name-status", h, "--", normal)),
        ("diff-tree/pathspec-nul", (
            "diff-tree", "--root", "-r", "--name-status", "-z", h, "--", normal,
        )),
        ("for-each-ref/all", ("for-each-ref",)),
        ("for-each-ref/format", ("for-each-ref", "--format=%(objectname) %(refname)")),
        ("for-each-ref/count", ("for-each-ref", "--count=3")),
        ("for-each-ref/sort", ("for-each-ref", "--sort=-refname")),
        ("for-each-ref/heads", ("for-each-ref", "refs/heads")),
        ("for-each-ref/format-nul-atoms", (
            "for-each-ref", "--format=%(refname)%00%(objectname)%00%(objecttype)",
        )),
        ("for-each-ref/format-peeled", (
            "for-each-ref", "--format=%(refname) %(objecttype) %(*objecttype) %(subject)",
        )),
        ("for-each-ref/points-at", ("for-each-ref", "--points-at", h)),
        ("for-each-ref/merged", ("for-each-ref", "--merged", h)),
        ("for-each-ref/contains", ("for-each-ref", "--contains", h)),
        ("for-each-ref/stdin", ("for-each-ref", "--stdin", "--format=%(refname)")),
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
        ("log/pathspec", ("log", "--oneline", h, "--", normal)),
        ("log/pathspec-nul", ("log", "--name-status", "-z", h, "--", normal)),
        ("ls-files/cached", ("ls-files", "--cached")),
        ("ls-files/stage", ("ls-files", "--stage")),
        ("ls-files/deleted", ("ls-files", "--deleted")),
        ("ls-files/modified", ("ls-files", "--modified")),
        ("ls-files/others", ("ls-files", "--others", "--exclude-standard")),
        ("ls-files/ignored", ("ls-files", "--ignored", "--exclude-standard")),
        ("ls-files/eol", ("ls-files", "--eol")),
        ("ls-files/nul", ("ls-files", "-z")),
        ("ls-files/stage-nul", ("ls-files", "--stage", "-z")),
        ("ls-files/others-nul", ("ls-files", "--others", "--exclude-standard", "-z")),
        ("ls-files/ignored-nul", ("ls-files", "--ignored", "--exclude-standard", "-z")),
        ("ls-files/eol-nul", ("ls-files", "--eol", "-z")),
        ("ls-files/pathspec", ("ls-files", "--cached", "--", normal)),
        ("ls-files/pathspec-nul", ("ls-files", "--cached", "-z", "--", normal)),
        ("ls-remote/plain", ("ls-remote", remote)),
        ("ls-remote/heads", ("ls-remote", "--heads", remote)),
        ("ls-remote/tags", ("ls-remote", "--tags", remote)),
        ("ls-remote/refs", ("ls-remote", "--refs", remote)),
        ("ls-remote/symref", ("ls-remote", "--symref", remote)),
        ("ls-remote/get-url", ("ls-remote", "--get-url", remote)),
        ("ls-remote/symref-refs", ("ls-remote", "--symref", "--refs", remote)),
        ("ls-tree/plain", ("ls-tree", h)),
        ("ls-tree/recursive", ("ls-tree", "-r", h)),
        ("ls-tree/name-only", ("ls-tree", "-r", "--name-only", h)),
        ("ls-tree/name-status-nul", ("ls-tree", "-r", "--name-status", "-z", h)),
        ("ls-tree/long", ("ls-tree", "-r", "--long", h)),
        ("ls-tree/object-only", ("ls-tree", "-r", "--object-only", h)),
        ("ls-tree/nul", ("ls-tree", "-r", "-z", h)),
        ("ls-tree/pathspec", ("ls-tree", "-r", h, "--", normal)),
        ("ls-tree/pathspec-nul", ("ls-tree", "-r", "-z", h, "--", normal)),
        ("merge-base/plain", ("merge-base", h, par)),
        ("merge-base/all", ("merge-base", "--all", h, par)),
        ("merge-base/is-ancestor", ("merge-base", "--is-ancestor", par, h)),
        ("merge-base/is-ancestor-reverse", ("merge-base", "--is-ancestor", h, par)),
        ("merge-base/octopus", ("merge-base", "--octopus", h, par, ctx.side)),
        ("rev-list/plain", ("rev-list", h)),
        ("rev-list/count", ("rev-list", "--count", h)),
        ("rev-list/objects", ("rev-list", "--objects", h)),
        ("rev-list/all", ("rev-list", "--all")),
        ("rev-list/parents", ("rev-list", "--parents", h)),
        ("rev-list/timestamp", ("rev-list", "--timestamp", h)),
        ("rev-list/header", ("rev-list", "--header", h)),
        ("rev-list/disk-usage", ("rev-list", "--disk-usage", h)),
        ("rev-list/stdin", ("rev-list", "--stdin")),
        ("rev-list/range", ("rev-list", f"{par}..{h}")),
        ("rev-list/range-count", ("rev-list", "--count", f"{par}..{h}")),
        ("rev-list/max-count", ("rev-list", "--max-count=1", h)),
        ("rev-list/skip", ("rev-list", "--skip=1", h)),
        ("rev-list/reverse", ("rev-list", "--reverse", h)),
        ("rev-list/no-merges", ("rev-list", "--no-merges", h)),
        ("rev-list/objects-nul", ("rev-list", "--objects", "-z", h)),
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
        ("show/pathspec", ("show", "--name-status", h, "--", normal)),
        ("show/pathspec-nul", ("show", "--name-status", "-z", h, "--", normal)),
        ("show-ref/all", ("show-ref",)),
        ("show-ref/heads", ("show-ref", "--heads")),
        ("show-ref/tags", ("show-ref", "--tags")),
        ("show-ref/hash", ("show-ref", "--hash")),
        ("show-ref/verify", ("show-ref", "--verify", "refs/heads/main")),
        ("show-ref/missing", ("show-ref", "--verify", "refs/heads/missing")),
        ("show-ref/head", ("show-ref", "--head")),
        ("show-ref/dereference", ("show-ref", "--dereference")),
        ("show-ref/quiet-verify", ("show-ref", "--quiet", "--verify", "refs/heads/main")),
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
        ("status/ignored", ("status", "--porcelain", "--ignored")),
        ("status/uall-nul", ("status", "--porcelain", "-uall", "-z")),
        ("verify-pack/verbose", ("verify-pack", "-v", pack)),
        ("verify-pack/stat-only", ("verify-pack", "--stat-only", pack)),
        ("verify-pack/no-verbose", ("verify-pack", "--no-verbose", pack)),
        ("verify-pack/no-stat-only", ("verify-pack", "--no-stat-only", pack)),
    ]


def input_for(ctx: Context, label: str) -> bytes | None:
    h = ctx.head
    ignored = p(ctx, "ignored", "ignored.tmp")
    if label in {"cat-file/batch-check-input", "cat-file/batch-check-format"}:
        return (h + "\n").encode()
    if label in {"cat-file/batch-check-nul", "cat-file/batch-nul"}:
        return (h + "\0").encode()
    if label == "cat-file/batch-input":
        return (h + "\n").encode()
    if label == "check-ignore/stdin":
        return (ignored + "\n").encode()
    if label in {"check-ignore/stdin-nul", "check-ignore/stdin-verbose-nul"}:
        return (ignored + "\0").encode()
    if label == "rev-list/stdin":
        return (h + "\n").encode()
    if label == "for-each-ref/stdin":
        return b"refs/heads\n"
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


def rejected_by_git(outcome: dict) -> bool:
    """Whether `_run` reached Git and Git rejected this spelling."""
    return (
        outcome.get("kind") == "refusal"
        and outcome.get("type") == "GitRefusal"
        and outcome.get("message") == "git invocation failed"
    )


def write_report(rows: list[dict], fixture_names: list[str]) -> None:
    differences = [row for row in rows if not row["same"]]
    forms_per_fixture = len(rows) // len(fixture_names) if fixture_names else 0
    both_git_rejected_new_forms = [
        row for row in rows
        if row["form"] in ADDED_FORM_LABELS
        and rejected_by_git(row["candidate"])
        and rejected_by_git(row["frozen"])
    ]
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
        f"- Widening: **{len(fixture_names) - FLOOR_FIXTURE_COUNT}** fixtures and "
        f"**{forms_per_fixture - FLOOR_FORM_COUNT}** forms beyond the original floor.",
        f"- Newly added-form rows Git rejects on both sides: "
        f"**{len(both_git_rejected_new_forms)}**.",
        "- Submodules: none.",
        "- Repository configuration naming a helper program: the controlled active-filter "
        "fixture only; its real-Git clean-tree positive control fires before either release "
        "is invoked, and the candidate then refuses before that program can launch.",
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
        "many refs, sparse checkout, and a symlinked HEAD. The widening adds redirected "
        "and moved worktrees, worktree configuration, three repository nesting levels, "
        "tag-chain and detached-tag states, an empty-tree commit, a two-parent merge plus "
        "a later unresolved conflict, binary/long/Unicode names, an explicit empty tree "
        "directory, both ignoreCase settings, attributes/eol, shallow and partial local "
        "clones, 512 untracked files, a non-repository nested `.git` directory, four "
        "answer-shaping configuration keys, one active content filter, and read-only "
        "git-directory state. Each answer-shaping fixture asserts the corresponding "
        "real-Git positive control during setup.",
        "",
        "## Forms and limits",
        "",
        "The form catalogue covers every candidate `READ_ONLY_VERBS` member: bundle "
        "read subcommands, cat-file object and batch reads, check-ignore ordinary/NUL/stdin "
        "reads, config read-only shapes, diff/diff-index/diff-tree patch/stat/name/numstat/raw "
        "and NUL/ignore-submodule forms, for-each-ref, log, ls-files, ls-remote, ls-tree, "
        "merge-base, rev-list (including stdin), rev-parse, show, show-ref, status porcelain "
        "v1/v2/short/untracked/ignore-submodule/branch/long/NUL forms, and verify-pack. "
        "The widening adds pathspec and `--` spellings, batch and object-list NUL protocols, "
        "format-atom and stdin ref enumeration, range/limit rev-list forms, merge-base "
        "octopus, show-ref variants, ls-remote URL forms, and verify-pack negated switches.",
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
        "- Platform-specific case-insensitive filesystem spellings and fully unreadable "
        "permission fixtures were not portable to this checkout; the corpus records read-only "
        "git-directory state plus the portable `.git` file, symlink, and HEAD-symlink forms.",
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
        "core-worktree", "moved-main-worktree", "worktree-config", "nested-three-levels",
        "detached-at-tag", "tag-chain", "empty-tree-commit", "merge-after-merge",
        "binary-and-long-name", "unicode-normalisation", "empty-directory-tree",
        "ignorecase-true", "ignorecase-false", "attributes-eol",
        "config-core-excludesfile", "config-status-showuntrackedfiles",
        "config-core-attributesfile", "config-core-abbrev", "config-content-filter",
        "shallow-clone",
        "partial-clone", "many-untracked", "literal-dotgit-directory",
        "read-only-git-state",
    ]
    requested = tuple(filter(None, os.environ.get("RP250_FIXTURES", "").split(",")))
    if requested:
        unknown = sorted(set(requested) - set(fixture_names))
        if unknown:
            raise SystemExit(f"unknown fixture(s): {', '.join(unknown)}")
        fixture_names = [name for name in fixture_names if name in requested]
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
            if fixture == "read-only-git-state":
                set_git_state_read_only(candidate_context, False)
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
            if fixture == "read-only-git-state":
                set_git_state_read_only(frozen_context, False)
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
