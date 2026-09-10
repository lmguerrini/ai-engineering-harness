"""A measured, closed composition for submodule-sensitive local reads.

The exact grammar is deliberately small and is kept by the shipped acceptance
corpus.  Every Git observation is made through the supplied governing runner
(``gitread._run`` in production), and each observation has an
``--ignore-submodules=all`` counterpart or is made from the submodule as its
own top-level read.

The rule is derived from the frozen release's porcelain-v2 output, rather
than from an attempted implementation of Git's work-tree scan.  In particular
``S<c><m><u>`` means: the submodule HEAD differs from the recorded index
gitlink, it has tracked changes, and it has untracked content, respectively.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat
from typing import Any, Callable

from errors import GitRefusal


Run = Callable[..., str | bytes]
Overlay = dict[str, str] | None
ZERO_OID = b"0" * 40


class UnsupportedFrozenForm(ValueError):
    """The frozen boundary refuses this input before it invokes Git."""


@dataclass(frozen=True)
class Gitlink:
    """One stage-zero gitlink, in the index order Git gave us."""

    path: bytes
    rendered_path: bytes
    head_tree_oid: bytes
    index_oid: bytes
    index_position: int


@dataclass(frozen=True)
class IndexState:
    """Gitlink identity plus the index ordering used to render status."""

    gitlinks: tuple[Gitlink, ...]
    raw_positions: dict[bytes, int]
    rendered_positions: dict[bytes, int]


@dataclass(frozen=True)
class Submodule:
    """The structural gitlink and its independently observed work-tree state."""

    path: bytes
    rendered_path: bytes
    head_tree_oid: bytes
    index_oid: bytes
    index_position: int
    worktree_head: bytes | None
    tracked: bool
    untracked: bool
    observation_v2: bytes

    @property
    def missing(self) -> bool:
        return self.worktree_head is None and not self.observation_v2

    @property
    def uninitialised(self) -> bool:
        return self.worktree_head is None and bool(self.observation_v2)

    @property
    def commit_changed(self) -> bool:
        return self.worktree_head is not None and self.worktree_head != self.index_oid

    @property
    def dirty(self) -> bool:
        return self.tracked or self.untracked

    @property
    def changed(self) -> bool:
        return self.missing or self.commit_changed or self.dirty

    @property
    def sub_field(self) -> bytes:
        return b"S" + (b"C" if self.commit_changed else b".") + (
            b"M" if self.tracked else b"."
        ) + (b"U" if self.untracked else b".")


@dataclass(frozen=True)
class Composition:
    """Answer bytes plus the direct submodule observations used to form them."""

    value: bytes
    observations: dict[bytes, bytes]


def _bytes(value: str | bytes) -> bytes:
    return value if isinstance(value, bytes) else value.encode("utf-8", "surrogateescape")


def _read(
    runner: Run, repository: Path, *arguments: str, env_overlay: Overlay,
) -> bytes:
    """The only observation primitive used by this prototype."""
    return _bytes(runner(repository, *arguments, text=False, env_overlay=env_overlay))


def _gitlinks(runner: Run, repository: Path, *, env_overlay: Overlay) -> IndexState:
    """Read index order and Git's own non-``-z`` path rendering together.

    ``ls-files --stage -z`` is the structural source of truth.  Its ordinary
    sibling is deliberately read beside it: Git, under the same governed
    configuration, supplies the C-quoted representation used by its newline
    porcelain and raw-diff forms.  Nothing here guesses a quoting policy.
    """
    raw_records = [
        record for record in _read(
            runner, repository, "ls-files", "--stage", "-z", env_overlay=env_overlay,
        ).split(b"\0") if record
    ]
    rendered_records = [
        record for record in _read(
            runner, repository, "ls-files", "--stage", env_overlay=env_overlay,
        ).splitlines() if record
    ]
    if len(raw_records) != len(rendered_records):
        raise RuntimeError("ls-files changed while its structural and rendered views were read")

    indexed: dict[bytes, tuple[bytes, bytes, int]] = {}
    raw_positions: dict[bytes, int] = {}
    rendered_positions: dict[bytes, int] = {}
    for position, (raw_record, rendered_record) in enumerate(zip(raw_records, rendered_records)):
        meta, path = raw_record.split(b"\t", 1)
        rendered_meta, rendered_path = rendered_record.split(b"\t", 1)
        if meta != rendered_meta:
            raise RuntimeError("ls-files structural and rendered metadata disagree")
        mode, object_id, stage = meta.split()
        if stage == b"0":
            raw_positions[path] = position
            rendered_positions[rendered_path] = position
            if mode == b"160000":
                indexed[path] = (object_id, rendered_path, position)

    committed: dict[bytes, bytes] = {}
    # An unborn repository has no HEAD tree, but it cannot have a committed
    # gitlink either.  Do not turn an ordinary local read into a refusal merely
    # by asking for a tree only a gitlink needs.
    if indexed:
        for record in _read(runner, repository, "ls-tree", "-rz", "HEAD", env_overlay=env_overlay).split(b"\0"):
            if not record:
                continue
            meta, path = record.split(b"\t", 1)
            mode, kind, object_id = meta.split()
            if mode == b"160000" and kind == b"commit":
                committed[path] = object_id

    # A deleted-from-index gitlink is not among the required fixture states.
    # Retaining only stage-zero entries keeps the identity source exactly the
    # index gitlinks named by the proposed composition.
    return IndexState(
        tuple(
            Gitlink(path, rendered_path, committed.get(path, object_id), object_id, position)
            for path, (object_id, rendered_path, position) in indexed.items()
        ),
        raw_positions,
        rendered_positions,
    )


def has_gitlinks(repository: str | Path, *, runner: Run, env_overlay: Overlay = None) -> bool:
    """Whether stage-zero structural state contains a gitlink.

    This is deliberately structural: it neither opens `.gitmodules` nor asks a
    working tree or configuration whether it wants recursive semantics.
    """
    return bool(_gitlinks(runner, Path(repository), env_overlay=env_overlay).gitlinks)


def _refuse_declared_submodule_ignore(repository: Path, index: IndexState) -> None:
    """Refuse a local ``ignore`` declaration without parsing submodule grammar.

    Names and paths in ``.gitmodules`` use Git's full configuration grammar.
    Decoding them here made the previously qualified quoted-path fixture refuse.
    The bounded policy needs only the declaration's presence, and only when a
    gitlink is populated: an uninitialised gitlink has no child answer for the
    declaration to shape. A line whose key token is ``ignore`` is then enough
    to fail closed.
    """
    if not any(
        stat.S_ISDIR(os.lstat(repository / gitlink.path.decode(
            "utf-8", "surrogateescape",
        )).st_mode)
        and os.path.lexists(repository / gitlink.path.decode(
            "utf-8", "surrogateescape",
        ) / ".git")
        for gitlink in index.gitlinks
        if os.path.lexists(repository / gitlink.path.decode(
            "utf-8", "surrogateescape",
        ))
    ):
        return
    configuration = repository / ".gitmodules"
    try:
        mode = configuration.lstat().st_mode
    except FileNotFoundError:
        return
    if not stat.S_ISREG(mode):
        raise GitRefusal(
            "a populated submodule has a non-regular .gitmodules file, so ignore "
            "policy cannot be ruled out",
            configuration=str(configuration),
        )
    for number, line in enumerate(configuration.read_bytes().splitlines(), 1):
        stripped = line.lstrip(b" \t")
        if not stripped or stripped.startswith((b"#", b";", b"[")):
            continue
        key = stripped
        for separator in (b" ", b"\t", b"="):
            key = key.split(separator, 1)[0]
        if key.lower() == b"ignore":
            raise GitRefusal(
                "a populated submodule declares an ignore policy which the no-child "
                "composition cannot reproduce",
                configuration=str(configuration),
                line=number,
            )


def _v2_flags(value: bytes) -> tuple[bool, bool]:
    """Extract tracked and untracked state from Git's own v2 records."""
    tracked = False
    untracked = False
    for line in value.splitlines():
        if line.startswith(b"? "):
            untracked = True
            continue
        if not line[:2] in (b"1 ", b"2 ", b"u "):
            continue
        fields = line.split(b" ", 3)
        if len(fields) > 1 and fields[1] != b"..":
            tracked = True
        if len(fields) > 2 and fields[2].startswith(b"S") and len(fields[2]) == 4:
            untracked = untracked or fields[2][3:4] == b"U"
    return tracked, untracked


def _submodule(
    runner: Run,
    repository: Path,
    gitlink: Gitlink,
    *,
    env_overlay: Overlay,
    fault: str | None,
    observations: dict[bytes, bytes],
) -> Submodule:
    """Observe one populated submodule as a separate top-level repository."""
    path = gitlink.path
    rendered_path = path if fault == "raw-gitlink-path" else gitlink.rendered_path
    head_tree_oid = gitlink.head_tree_oid
    index_oid = gitlink.index_oid
    worktree = repository / path.decode("utf-8", "surrogateescape")
    dotgit = worktree / ".git"
    try:
        worktree_mode = os.lstat(worktree).st_mode
    except FileNotFoundError:
        return Submodule(path, rendered_path, head_tree_oid, index_oid,
                         gitlink.index_position, None, False, False, b"")
    if not stat.S_ISDIR(worktree_mode):
        raise RuntimeError("a gitlink worktree was not classified before observation")
    try:
        os.lstat(dotgit)
    except FileNotFoundError:
        # Git treats an empty, uninitialised gitlink directory as clean.  The
        # nonempty sentinel makes this distinct from a removed worktree.
        return Submodule(path, rendered_path, head_tree_oid, index_oid,
                         gitlink.index_position, None, False, False, b"uninitialised")

    # This recursive call is itself a composition.  Thus a nested populated
    # submodule never makes its parent Git invocation recurse into it.
    child_v2 = _status_v2(runner, worktree, env_overlay=env_overlay, fault=fault, observations=observations)
    observations[path] = child_v2
    head = _read(runner, worktree, "rev-parse", "HEAD", env_overlay=env_overlay).rstrip(b"\n")
    tracked, untracked = _v2_flags(child_v2)

    if fault == "missed-dirty-state":
        tracked = untracked = False
    elif fault == "omitted-untracked-state":
        untracked = False
    elif fault == "wrong-new-commit-classification":
        head = index_oid
    elif fault == "wrong-gitlink-identity":
        index_oid = ZERO_OID
    elif fault == "wrong-staged-versus-unstaged":
        # This control intentionally loses the X/Y distinction in the direct
        # observation.  The outer display coalesces it, so the corpus checks
        # the required child observation as well as the final parent answer.
        observations[path] = child_v2.replace(b"1 M.", b"1 .M", 1)

    return Submodule(path, rendered_path, head_tree_oid, index_oid,
                     gitlink.index_position, head, tracked, untracked, child_v2)


def _submodules(
    runner: Run, repository: Path, *, index: IndexState, env_overlay: Overlay, fault: str | None,
    observations: dict[bytes, bytes],
) -> list[Submodule]:
    return [
        _submodule(runner, repository, gitlink, env_overlay=env_overlay,
                   fault=fault, observations=observations)
        for gitlink in index.gitlinks
    ]


def _status_path(record: bytes, *, porcelain_v2: bool) -> bytes | None:
    """The path field of one already-separated status record, if tracked."""
    if porcelain_v2:
        return record.rsplit(b" ", 1)[-1] if record[:2] in (b"1 ", b"2 ", b"u ") else None
    if record.startswith((b"?? ", b"!! ")):
        return None
    return record[3:] if len(record) >= 4 else None


def _merge_status(
    body: bytes,
    additions: list[tuple[int, bytes]],
    *,
    index: IndexState,
    gitlink_paths: set[bytes],
    gitlink_renderings: set[bytes],
    porcelain_v2: bool,
    nul: bool,
    append: bool = False,
) -> bytes:
    """Replace gitlinks by merging records at their ``ls-files`` positions.

    The parent read already has Git's formatting for all ordinary records.  We
    retain that order and use only the stage-zero index position to place each
    composed gitlink before the next indexed path.  Thus an untracked marker
    is merely an unindexed record after which remaining indexed additions go;
    it is not an ordering rule of its own.
    """
    separator = b"\0" if nul else b"\n"
    rendered_positions = index.raw_positions if nul else index.rendered_positions
    records: list[tuple[bytes, int | None]] = []
    for plain in body.split(separator):
        if not plain:
            continue
        path = _status_path(plain, porcelain_v2=porcelain_v2)
        if path is not None and (
            path in (gitlink_paths if nul else gitlink_renderings)
        ):
            continue
        records.append((plain + separator, rendered_positions.get(path) if path is not None else None))

    pending = iter(sorted((item for item in additions if item[1]), key=lambda item: item[0]))
    next_addition = next(pending, None)
    if append:
        return b"".join(record for record, _ in records) + b"".join(
            addition for _, addition in sorted((item for item in additions if item[1]), key=lambda item: item[0])
        )
    merged: list[bytes] = []
    for record, position in records:
        if position is not None:
            while next_addition is not None and next_addition[0] < position:
                merged.append(next_addition[1])
                next_addition = next(pending, None)
        elif next_addition is not None:
            # An unindexed status record (for example ``??``) follows every
            # stage-zero entry, so all remaining index records precede it.
            while next_addition is not None:
                merged.append(next_addition[1])
                next_addition = next(pending, None)
        merged.append(record)
    while next_addition is not None:
        merged.append(next_addition[1])
        next_addition = next(pending, None)
    return b"".join(merged)


def _v2_line(sub: Submodule, *, nul: bool) -> bytes:
    path = sub.path if nul else sub.rendered_path
    separator = b"\0" if nul else b"\n"
    if sub.missing:
        return (b"1 .D S... 160000 160000 000000 " + sub.head_tree_oid + b" " + sub.index_oid
                + b" " + path + separator)
    assert sub.worktree_head is not None
    x = b"M" if sub.head_tree_oid != sub.index_oid else b"."
    y = b"M" if sub.changed else b"."
    if x + y == b"..":
        return b""
    return (b"1 " + x + y + b" " + sub.sub_field + b" 160000 160000 160000 "
            # Porcelain v2 carries hH and hI only; the third 160000 is mW.
            # Child-derived HEAD movement is represented by `S<C><m><u>`.
            + sub.head_tree_oid + b" " + sub.index_oid + b" "
            + path + separator)


def _status_v2(
    runner: Run, repository: Path, *, index: IndexState | None = None, env_overlay: Overlay, fault: str | None,
    nul: bool = False,
    observations: dict[bytes, bytes],
) -> bytes:
    """Compose porcelain v2 from a no-recursion parent plus child v2 reads."""
    actual_index = index or _gitlinks(runner, repository, env_overlay=env_overlay)
    subs = _submodules(runner, repository, index=actual_index, env_overlay=env_overlay,
                       fault=fault, observations=observations)
    arguments = ("status", "--porcelain=v2", *( ("-z",) if nul else () ), "--ignore-submodules=all")
    body = _read(runner, repository, *arguments, env_overlay=env_overlay)
    additions = [
        (sub.index_position, _v2_line(sub, nul=nul))
        for sub in subs if not sub.uninitialised
    ]
    return _merge_status(
        body, additions, index=actual_index, gitlink_paths={sub.path for sub in subs},
        gitlink_renderings={sub.rendered_path for sub in subs}, porcelain_v2=True, nul=nul,
        append=fault == "append-gitlinks",
    )


def _status_v1(
    runner: Run, repository: Path, arguments: tuple[str, ...], *, index: IndexState, env_overlay: Overlay,
    fault: str | None, observations: dict[bytes, bytes],
    nul: bool,
) -> bytes:
    """Compose the v1/short spellings using the v2-derived child state."""
    subs = _submodules(runner, repository, index=index, env_overlay=env_overlay,
                       fault=fault, observations=observations)
    body = _read(runner, repository, *arguments, "--ignore-submodules=all", env_overlay=env_overlay)
    hide_dirty = "--ignore-submodules=dirty" in arguments
    separator = b"\0" if nul else b"\n"
    additions: list[tuple[int, bytes]] = []
    for sub in subs:
        if sub.uninitialised:
            continue
        if sub.missing:
            additions.append((sub.index_position, b" D " + (sub.path if nul else sub.rendered_path) + separator))
            continue
        assert sub.worktree_head is not None
        x = b"M" if sub.head_tree_oid != sub.index_oid else b" "
        y = b"M" if sub.changed and not (hide_dirty and not sub.commit_changed) else b" "
        # `--short` is the one requested v1 spelling that preserves a little
        # more submodule detail: m means tracked dirt and ? means untracked
        # content, while porcelain v1 uses M for both.
        if tuple(argument for argument in arguments if argument != "-z") == ("status", "--short") and y == b"M" and not sub.commit_changed:
            y = b"m" if sub.tracked else b"?"
        if x + y != b"  ":
            additions.append((sub.index_position, x + y + b" " + (sub.path if nul else sub.rendered_path) + separator))
    return _merge_status(
        body, additions, index=index, gitlink_paths={sub.path for sub in subs},
        gitlink_renderings={sub.rendered_path for sub in subs}, porcelain_v2=False, nul=nul,
        append=fault == "append-gitlinks",
    )


def _prefixed_rendering(prefix: bytes, rendered_path: bytes) -> bytes:
    """Put a diff prefix inside the representation Git measured for a path."""
    if rendered_path.startswith(b'"') and rendered_path.endswith(b'"'):
        return b'"' + prefix + rendered_path[1:]
    return prefix + rendered_path


def _merge_index_records(
    records: list[tuple[bytes, int | None]], additions: list[tuple[int, bytes]],
) -> bytes:
    """Merge generated records at the stage-zero positions that Git supplied."""
    pending = iter(sorted((item for item in additions if item[1]), key=lambda item: item[0]))
    next_addition = next(pending, None)
    merged: list[bytes] = []
    for record, position in records:
        if position is not None:
            while next_addition is not None and next_addition[0] < position:
                merged.append(next_addition[1])
                next_addition = next(pending, None)
        merged.append(record)
    while next_addition is not None:
        merged.append(next_addition[1])
        next_addition = next(pending, None)
    return b"".join(merged)


def _merge_diff(body: bytes, additions: list[tuple[int, bytes]], index: IndexState) -> bytes:
    """Merge patch or summary groups using the same index order as status."""
    prefix = b"diff --git "
    headers = {
        prefix + _prefixed_rendering(b"a/", rendered) + b" " + _prefixed_rendering(b"b/", rendered): position
        for rendered, position in index.rendered_positions.items()
    }
    records: list[tuple[bytes, int | None]] = []
    for piece in body.split(prefix):
        if not piece:
            continue
        record = prefix + piece
        header = record.split(b"\n", 1)[0]
        records.append((record, headers.get(header)))
    return _merge_index_records(records, additions)


def _default_patch(sub: Submodule) -> bytes:
    a_path = _prefixed_rendering(b"a/", sub.rendered_path)
    b_path = _prefixed_rendering(b"b/", sub.rendered_path)
    if sub.missing:
        return (b"diff --git " + a_path + b" " + b_path + b"\n"
                + b"deleted file mode 160000\nindex " + sub.head_tree_oid[:7] + b"..0000000\n"
                + b"--- " + a_path + b"\n+++ /dev/null\n@@ -1 +0,0 @@\n"
                + b"-Subproject commit " + sub.head_tree_oid + b"\n")
    # The frozen parent reports untracked child content in status but does not
    # make it a diff or diff-index change.
    if not (sub.commit_changed or sub.tracked):
        return b""
    assert sub.worktree_head is not None
    suffix = b"-dirty" if sub.dirty else b""
    index = (b"index " + sub.index_oid[:7] + b".." + sub.worktree_head[:7] + b" 160000\n"
             if sub.index_oid != sub.worktree_head else b"")
    return (b"diff --git " + a_path + b" " + b_path + b"\n" + index
            + b"--- " + a_path + b"\n+++ " + b_path + b"\n@@ -1 +1 @@\n"
            + b"-Subproject commit " + sub.index_oid + b"\n+Subproject commit "
            + sub.worktree_head + suffix + b"\n")


def _submodule_summary(
    runner: Run, repository: Path, sub: Submodule, *, env_overlay: Overlay,
) -> bytes:
    if sub.missing:
        return b"Submodule " + sub.path + b" " + sub.head_tree_oid[:7] + b"...0000000 (submodule deleted)\n"
    if not (sub.commit_changed or sub.tracked):
        return b""
    assert sub.worktree_head is not None
    if sub.commit_changed:
        # Measured frozen format: its default `--submodule` summary is a
        # subject-only log of the child range, prefixed by `  > `.  The log is
        # a separate top-level governed read in the child, never parent
        # recursion.
        subjects = _read(
            runner, repository / sub.path.decode("utf-8", "surrogateescape"), "log",
            "--format=%s", f"{sub.index_oid.decode()}..{sub.worktree_head.decode()}",
            env_overlay=env_overlay,
        )
        details = b"".join(b"  > " + subject + b"\n" for subject in subjects.splitlines())
        return (b"Submodule " + sub.path + b" " + sub.index_oid[:7] + b".."
                + sub.worktree_head[:7] + b":\n" + details)
    if sub.tracked:
        return b"Submodule " + sub.path + b" contains modified content\n"
    return b"Submodule " + sub.path + b" contains untracked content\n"


def _diff(
    runner: Run, repository: Path, *, index: IndexState, summary: bool, env_overlay: Overlay,
    fault: str | None, observations: dict[bytes, bytes],
) -> bytes:
    arguments = ("diff", "--submodule", "--ignore-submodules=all") if summary else ("diff", "--ignore-submodules=all")
    body = _read(runner, repository, *arguments, env_overlay=env_overlay)
    subs = _submodules(runner, repository, index=index, env_overlay=env_overlay,
                       fault=fault, observations=observations)
    rendered = [
        (sub.index_position, _submodule_summary(runner, repository, sub, env_overlay=env_overlay))
        if summary else (sub.index_position, _default_patch(sub))
        for sub in subs
    ]
    return _merge_diff(body, rendered, index)


def _diff_index(
    runner: Run, repository: Path, *, index: IndexState, env_overlay: Overlay, fault: str | None,
    observations: dict[bytes, bytes],
) -> bytes:
    body = _read(runner, repository, "diff-index", "HEAD", "--ignore-submodules=all", env_overlay=env_overlay)
    subs = _submodules(runner, repository, index=index, env_overlay=env_overlay,
                       fault=fault, observations=observations)
    additions: list[tuple[int, bytes]] = []
    for sub in subs:
        if fault == "omit-staged-gitlink" and sub.head_tree_oid != sub.index_oid:
            continue
        if sub.uninitialised or not (
            sub.head_tree_oid != sub.index_oid or sub.missing or sub.commit_changed or sub.tracked
        ):
            continue
        if sub.missing:
            additions.append((sub.index_position, b":160000 000000 " + sub.head_tree_oid + b" " + ZERO_OID + b" D\t" + sub.rendered_path + b"\n"))
        else:
            assert sub.worktree_head is not None
            # diff-index's raw work-tree value is the all-zero sentinel when
            # the gitlink HEAD moved; for dirt at the recorded commit Git
            # repeats the recorded OID.  This is measured output, not a
            # substitute identity.
            observed = (
                sub.index_oid if sub.head_tree_oid != sub.index_oid
                else ZERO_OID if sub.commit_changed else sub.index_oid
            )
            additions.append((sub.index_position, b":160000 160000 " + sub.head_tree_oid + b" " + observed + b" M\t" + sub.rendered_path + b"\n"))
    gitlink_renderings = {sub.rendered_path for sub in subs}
    records = [
        (line + b"\n", index.rendered_positions.get(line.rsplit(b"\t", 1)[-1]))
        for line in body.splitlines()
        if line.rsplit(b"\t", 1)[-1] not in gitlink_renderings
    ]
    return _merge_index_records(records, additions)


def compose(
    repository: str | Path,
    *arguments: str,
    runner: Run,
    env_overlay: Overlay = None,
) -> Composition:
    """Return the frozen-form answer without allowing Git to recurse.

    This is the production composition interface. Deliberate broken variants
    belong to the acceptance harness, not to callers of the governed toolbelt.
    """
    return _compose_for_control(
        repository, *arguments, runner=runner, env_overlay=env_overlay, fault=None,
    )


def _compose_for_control(
    repository: str | Path,
    *arguments: str,
    runner: Run,
    env_overlay: Overlay = None,
    fault: str | None = None,
) -> Composition:
    """Acceptance-only composition entry point for the corpus's positive controls."""
    repo = Path(repository)
    observations: dict[bytes, bytes] = {}
    if arguments == ("diff", "--submodule=diff"):
        # This is the frozen pre-invocation refusal, so it must remain before
        # even the harmless structural reads below.
        raise UnsupportedFrozenForm("frozen gitread refuses --submodule=diff before Git runs")
    if fault == "accidental-child-process":
        # Deliberately broken control: this is precisely the child-producing
        # parent read that the composition replaces.
        _read(runner, repo, "status", "--porcelain=v2", "-uno", env_overlay=env_overlay)
    elif fault == "dropped-trace-child-process":
        # Positive-control mutant: a recursive parent call whose caller trace
        # overlay is deliberately omitted.  The corpus's runner wrapper must
        # reject the missing overlay even if earlier calls wrote valid traces.
        _read(runner, repo, "status", "--porcelain=v2", "-uno", env_overlay=None)

    index = _gitlinks(runner, repo, env_overlay=env_overlay)
    _refuse_declared_submodule_ignore(repo, index)
    # ``lstat`` is the classification boundary: unlike Path.exists(), it does
    # not follow the gitlink worktree.  Git itself refuses a symlinked
    # submodule for recursive forms and gives a typechange for raw diff-index.
    # Delegating that one childless parent invocation reproduces both frozen
    # outcomes exactly rather than manufacturing a competing interpretation.
    for gitlink in index.gitlinks:
        worktree = repo / gitlink.path.decode("utf-8", "surrogateescape")
        try:
            if stat.S_ISLNK(os.lstat(worktree).st_mode) and fault != "omit-symlink-classification":
                return Composition(_read(runner, repo, *arguments, env_overlay=env_overlay), observations)
        except FileNotFoundError:
            pass

    normalised = tuple(argument for argument in arguments if argument != "-z")
    nul = len(normalised) != len(arguments)
    rendered_nul = nul and fault != "newline-for-nul"
    if normalised == ("status", "--porcelain=v2"):
        value = _status_v2(runner, repo, index=index, env_overlay=env_overlay,
                           fault=fault, nul=rendered_nul, observations=observations)
    elif normalised in {
        ("status", "--porcelain"),
        ("status", "--short"),
        ("status", "--porcelain", "-uall"),
        ("status", "--porcelain", "--ignore-submodules=dirty"),
    }:
        value = _status_v1(runner, repo, arguments, index=index, env_overlay=env_overlay,
                           fault=fault, observations=observations, nul=rendered_nul)
    elif arguments == ("diff",):
        value = _diff(runner, repo, index=index, summary=False, env_overlay=env_overlay,
                      fault=fault, observations=observations)
    elif arguments == ("diff", "--submodule"):
        value = _diff(runner, repo, index=index, summary=True, env_overlay=env_overlay,
                      fault=fault, observations=observations)
    elif arguments == ("diff", "--cached"):
        value = _read(runner, repo, *arguments, env_overlay=env_overlay)
    elif arguments == ("diff-index", "HEAD"):
        value = _diff_index(runner, repo, index=index, env_overlay=env_overlay,
                            fault=fault, observations=observations)
    else:
        raise ValueError(f"prototype does not cover: {' '.join(arguments)}")
    return Composition(value, observations)
