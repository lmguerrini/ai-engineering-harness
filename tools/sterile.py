"""A Git execution in which nothing the subject wrote is configuration.

`docs/RP2.5.0-DESIGN-A1-sterile-execution.md` and its successor
`docs/RP2.5.0-DESIGN-A2-nested-and-ambient.md` are the frozen designs this
implements, and `docs/RP2.5.0-RECURRENCE-MAP.md` is why it exists.

Fifteen repairs across 2.4.0 and 2.4.1 answered "which of this repository's
settings are dangerous?" — a question whose answer is an open set of keys,
verbs, flags, transports, option spellings and nested layouts, and whose
incompleteness runs somebody's program. This module answers a different
question:

    Every configuration source Git consults during a governed read is a file
    this harness created.

`GIT_DIR` decides which files are local and worktree configuration, and the
caller chooses `GIT_DIR`. So the harness builds the git directory: its own
config from a blank slate, the subject's objects attached rather than copied,
refs and `HEAD` copied as plain files with no Git involved, the index copied so
that a refresh writes to ours.

**Everything here is built by ADDING what a read needs, never by REMOVING what
it must not have.** That polarity is the whole argument. Anything this module
fails to add makes a read *fail*; nothing it fails to remove can execute,
because nothing was inherited. 2.4.1's denylist had the opposite polarity, and
that is why narrowing it to stop over-refusing widened the hole.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import instrument
from errors import GitRefusal, IntegrityError
from instrument import BlastRadius

__all__ = [
    "STORAGE_KEYS",
    "where_is",
    "SterileRead",
    "build",
    "config_as_data",
    "nested_repository_paths",
]


#: `core.*` settings carried into the sterile config, because they describe how
#: the store and the working tree are ENCODED rather than what Git should run.
#:
#: This is an allowlist, and that is admissible here for a reason 2.4.1's
#: denylist could not claim: **a key missing from this set makes a read fail or
#: differ, and a key missing from a denylist runs a program.** None of these
#: values can name a program. Getting the set wrong is an availability or
#: answer-fidelity defect that the differential oracles catch by comparing
#: against real Git; it is never an execution.
#:
#: `core.autocrlf` and `core.eol` are here because an independent design reading
#: showed a clean CRLF working tree producing a full spurious diff without them.
STORAGE_KEYS = frozenset({
    "core.repositoryformatversion",
    "core.filemode",
    "core.symlinks",
    "core.ignorecase",
    "core.precomposeunicode",
    "core.bigfilethreshold",
    "core.autocrlf",
    "core.eol",
    "core.sparsecheckout",
    "core.sparsecheckoutcone",
})

#: Plain files carried from the subject's git directory because Git reads them as
#: DATA and a governed answer differs from real Git's without them. Each one is
#: here because a differential test established it, not because it seemed likely:
#: `info/exclude` is an ignore source, `info/sparse-checkout` decides which paths
#: the working tree is expected to hold, and `shallow` bounds the history.
#:
#: None of them can name a program: an attributes or ignore file selects a driver
#: by NAME, and the driver's program comes from configuration, which is ours.
CARRIED_DATA = ("info/exclude", "info/sparse-checkout", "info/attributes", "shallow")

#: What this module does outside itself. It writes, so it says why.
BLAST_RADIUS = BlastRadius(
    reads=("the named repository's git directory and working tree, as files",),
    writes=("a scratch directory this module creates and owns",),
    launches=("git",),
    because=(
        "a read that cannot be told to execute anything needs a git directory the "
        "subject did not write, and building one means writing files somewhere"
    ),
)


def _git_directory(subject: Path) -> Path:
    """Where Git keeps this repository's own state, whatever shape `.git` is in."""
    dot = subject / ".git"
    if dot.is_file():
        # A linked worktree and a submodule both spell it this way.
        raw = dot.read_text(encoding="utf-8", errors="surrogateescape")
        _, _, target = raw.partition(":")
        target = target.strip()
        if not target:
            raise GitRefusal("the .git file names no git directory", repository=str(subject))
        return Path(target) if os.path.isabs(target) else (subject / target).resolve()
    if dot.is_dir():
        return dot
    if (subject / "HEAD").is_file() and (subject / "objects").is_dir():
        return subject                       # a bare repository is its own git directory
    raise GitRefusal("that directory is not a git repository", repository=str(subject))


def _common_directory(gitdir: Path) -> Path:
    """The git directory whose refs and objects are shared, for a linked worktree."""
    marker = gitdir / "commondir"
    if not marker.is_file():
        return gitdir
    raw = marker.read_text(encoding="utf-8", errors="surrogateescape").strip()
    return Path(raw) if os.path.isabs(raw) else (gitdir / raw).resolve()


def where_is(repository) -> dict:
    """Where the SUBJECT's repository lives, answered from files rather than from Git.

    A governed read runs with `GIT_DIR` pointing at a directory this harness
    built, so `git rev-parse --git-dir`, `--git-common-dir` and `--show-toplevel`
    all answer about the BUILD. That is the correct answer to a different
    question, and three callers were asking this one: `activity` identifies a
    repository by its common directory in order to count it once, `pack_pin`
    separates a linked worktree from an ordinary checkout, and `design_record`
    locates a record inside the tree that governs it. Under the boundary all
    three would have got the scratch directory — `activity` counted one
    repository as six.

    So it is answered here, once, for all of them: the question is about the
    subject, so the subject is what is read. Nothing here runs a program.
    """
    subject = Path(repository).resolve()
    gitdir = _git_directory(subject)
    common = _common_directory(gitdir)
    return {
        "gitdir": str(gitdir),
        "common": str(common),
        "toplevel": str(subject),
        "linked_worktree": gitdir.resolve() != common.resolve(),
        "bare": _is_bare(subject),
    }


def config_as_data(path: Path) -> dict:
    """Parse a Git config FILE as text.

    Nothing read here is ever handed to Git, so nothing here can execute. This is
    how the storage descriptors are learned and how a caller reads a repository's
    own settings — a remote's URL, say — without Git resolving them.
    """
    values: dict = {}
    section = ""
    if not Path(path).is_file():
        return values
    text = Path(path).read_text(encoding="utf-8", errors="surrogateescape")
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(("#", ";")):
            continue
        line = line.split("#", 1)[0].split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            inner = line[1:-1].strip()
            head, _, tail = inner.partition(" ")
            # Git folds the SECTION and the VARIABLE to lower case and keeps a
            # SUBSECTION verbatim. 2.4.1 shipped a defect for not knowing that,
            # and this parser is only ever used to read, so it follows the same
            # rule rather than a convenient one.
            section = head.lower() if not tail else f"{head.lower()}.{tail.strip().strip(chr(34))}"
            continue
        key, sep, value = line.partition("=")
        name = f"{section}.{key.strip().lower()}" if section else key.strip().lower()
        values[name] = value.strip() if sep else "true"
    return values


def _head_as_data(gitdir: Path, common: Path, limit: int = 10) -> str | None:
    """Resolve HEAD by reading files, following a symbolic-ref chain.

    A chain is legal — `HEAD -> refs/heads/a -> refs/heads/b` — and refusing one
    was an availability loss with no safety gain. Running out of hops resolves to
    nothing, which the caller turns into a refusal rather than into an answer.
    """
    head = gitdir / "HEAD"
    if not head.is_file():
        return None
    raw = head.read_text(encoding="utf-8", errors="surrogateescape").strip()
    seen: set = set()
    for _ in range(limit):
        if not raw.startswith("ref:"):
            return raw or None
        ref = raw.split(":", 1)[1].strip()
        if ref in seen:
            return None                      # a cycle is not a resolution
        seen.add(ref)
        loose = common / ref
        if loose.is_file():
            raw = loose.read_text(encoding="utf-8", errors="surrogateescape").strip()
            continue
        packed = common / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8", errors="surrogateescape").splitlines():
                if line.startswith(("#", "^")):
                    continue
                parts = line.split(None, 1)
                if len(parts) == 2 and parts[1].strip() == ref:
                    return parts[0]
        return None
    return None


#: The ref backend this build imports by copying files. Git has one other today
#: (`reftable`), and a repository declares a non-default one with
#: `extensions.refstorage`.
REPRODUCIBLE_REF_STORAGE = "files"


def _ref_store_is_reproducible(gitdir: Path, common: Path) -> bool:
    """Whether copying `refs/`, `packed-refs` and `HEAD` reproduces this ref store.

    **This is the discrimination the HEAD round trip needs, and the first version
    got it wrong in both directions.** It asked whether the repository was
    "unborn", inferred from an absence — which let a `reftable` subject through
    (no `refs/` files, so it looked unborn) and later refused an ordinary
    repository whose HEAD points at a branch nobody has created, where the build
    reproduces the subject *exactly* and `ls-files` never needed HEAD at all.

    An absence is not evidence. What matters is whether the store this build
    knows how to copy is the store the subject uses, which the subject states.
    An unrecognised backend refuses, so a future one fails closed.
    """
    if (common / "reftable").exists() or (gitdir / "reftable").exists():
        return False
    declared = config_as_data(common / "config").get("extensions.refstorage")
    return declared is None or declared.strip().lower() == REPRODUCIBLE_REF_STORAGE


def _write_config(into: Path, common: Path, gitdir: Path) -> None:
    """The only configuration Git will read, written from a blank slate."""
    declared = config_as_data(common / "config")
    declared.update(config_as_data(gitdir / "config.worktree"))
    core = {
        name[len("core."):]: value
        for name, value in declared.items()
        if name in STORAGE_KEYS and name.startswith("core.")
    }
    core.setdefault("repositoryformatversion", "0")
    core["bare"] = "false"
    lines = ["[core]\n"] + [f"\t{key} = {value}\n" for key, value in sorted(core.items())]
    # EVERY `extensions.*` VERBATIM, and that needs no allowlist. An extension
    # changes how Git interprets the GIT DIRECTORY, and this git directory holds
    # only files this build created — so an extension can only ever point Git at
    # our own files. One naming a store this build did not import (`reftable`)
    # makes the read fail, which is the polarity this design is built on.
    extensions = {
        name[len("extensions."):]: value
        for name, value in declared.items()
        if name.startswith("extensions.")
    }
    if extensions:
        lines.append("[extensions]\n")
        lines += [f"\t{key} = {value}\n" for key, value in sorted(extensions.items())]
    (into / "config").write_text("".join(lines), encoding="utf-8")


def build_git_directory(subject: Path, into: Path) -> tuple:
    """Construct a git directory the harness owns over the subject's object store."""
    subject = Path(subject).resolve()
    gitdir = _git_directory(subject)
    common = _common_directory(gitdir)
    if into.exists():
        shutil.rmtree(into)
    (into / "objects" / "info").mkdir(parents=True)
    (into / "refs").mkdir(parents=True)
    (into / "info").mkdir(parents=True, exist_ok=True)
    _write_config(into, common, gitdir)
    # Objects are ATTACHED, never copied: a release-sized repository would
    # otherwise pay its whole size on every read.
    alternates = [str(common / "objects")]
    chained = common / "objects" / "info" / "alternates"
    if chained.is_file():
        alternates += [
            line for line in chained.read_text(encoding="utf-8", errors="surrogateescape").splitlines()
            if line.strip()
        ]
    (into / "objects" / "info" / "alternates").write_text("\n".join(alternates) + "\n", encoding="utf-8")
    for name, source in (("HEAD", gitdir / "HEAD"), ("packed-refs", common / "packed-refs")):
        if source.is_file():
            shutil.copyfile(source, into / name)
    if (common / "refs").is_dir():
        shutil.copytree(common / "refs", into / "refs", dirs_exist_ok=True, symlinks=True)
    # The index is COPIED, so that a `status` refresh writes to this build's copy
    # and the subject is left byte-identical by every governed read.
    if (gitdir / "index").is_file():
        shutil.copyfile(gitdir / "index", into / "index")
    for relative in CARRIED_DATA:
        source = gitdir / relative
        if not source.is_file():
            source = common / relative
        if source.is_file():
            destination = into / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    return into, _head_as_data(gitdir, common), _ref_store_is_reproducible(gitdir, common)


def nested_repository_paths(subject: Path) -> list:
    """Every directory under the subject that carries an entry named `.git`.

    **The NAME decides and the kind never does.** `.git` is the only name Git
    opens a repository from in a working tree; the other way in is `GIT_DIR`,
    which is ours. An earlier version asked whether `.git` was a directory or a
    file, and a `.git` that was a SYMLINK to a directory was classified as an
    ordinary directory symlink, copied into the view as it stood, and pointed Git
    straight back at the subject's own configuration — which Git ran. An
    independent design reading found that with a marker on disk before any of
    this was implemented.
    """
    subject = Path(subject).resolve()
    found: list = []
    for root, directories, files in os.walk(subject, followlinks=False):
        here = Path(root)
        relative = here.relative_to(subject)
        if ".git" in relative.parts:
            directories[:] = []
            continue
        if ".git" in directories:
            directories.remove(".git")
        if ".git" in files:
            files.remove(".git")
        if relative != Path(".") and os.path.lexists(here / ".git"):
            found.append(relative)
    return found


def _build_view(subject: Path, scratch: Path) -> Path:
    """A working tree in which no `.git` is one the subject wrote."""
    subject = Path(subject).resolve()
    view = scratch / "view"
    if view.exists():
        shutil.rmtree(view)
    view.mkdir(parents=True)
    nested: list = []
    for root, directories, files in os.walk(subject, followlinks=False):
        here = Path(root)
        relative = here.relative_to(subject)
        if ".git" in relative.parts:
            directories[:] = []
            continue
        (view / relative).mkdir(parents=True, exist_ok=True)
        # THE NAME FIRST, before anything classifies it, and removed from both
        # lists so that no later branch can reproduce it. The directory-symlink
        # branch below is exactly the branch that used to.
        if ".git" in directories:
            directories.remove(".git")
        if ".git" in files:
            files.remove(".git")
        if relative != Path(".") and os.path.lexists(here / ".git"):
            nested.append(relative)
        for name in list(directories):
            source = here / name
            if source.is_symlink():
                # A directory symlink is a symlink. Materialising it as a real
                # directory made the view lie about the tree it stands for.
                directories.remove(name)
                destination = view / relative / name
                if not os.path.lexists(destination):
                    os.symlink(os.readlink(source), destination)
        for name in files:
            source, destination = here / name, view / relative / name
            if os.path.lexists(destination):
                continue
            try:
                os.link(source, destination)          # a link, so no content is copied
            except OSError:
                if source.is_symlink():
                    os.symlink(os.readlink(source), destination)
                else:
                    shutil.copyfile(source, destination, follow_symlinks=False)
    built: set = set()
    for index, relative in enumerate(dict.fromkeys(nested)):
        try:
            inner, _, _ = build_git_directory(subject / relative, scratch / f"nested-{index}")
        except Exception as exc:                       # noqa: BLE001
            # A NESTED REPOSITORY THIS BUILD CANNOT REBUILD IS A REFUSAL. The
            # alternative leaves the subject's own git directory reachable from a
            # tree Git is about to read, which is the failure this design exists
            # to make impossible.
            raise GitRefusal(
                f"the repository at {relative} inside the working tree could not be rebuilt "
                f"sterile, so this read is refused rather than performed against configuration "
                f"the subject wrote. `probe` reports a refusal by its cause alone, so the path "
                f"is named there and not only in the detail",
                repository=str(subject), nested=str(relative),
                because=f"{type(exc).__name__}: {exc}",
            ) from exc
        os.symlink(inner, view / relative / ".git")
        built.add(inner.resolve())
    _every_git_in_the_view_is_ours(view, built)
    return view


def _every_git_in_the_view_is_ours(view: Path, built: set) -> None:
    """The post-condition, established by looking rather than by trusting the loop.

    The loop above is an argument; this is the evidence. If a `.git` reaches the
    view by a route nobody predicted, the read refuses instead of running whatever
    the configuration behind it names.
    """
    # MEMBERSHIP, NOT LOCATION. Checking only that a `.git` resolves somewhere
    # under the scratch directory passes a `.git` that was COPIED there with the
    # subject's own configuration inside it. The set of directories this build
    # actually made is the only thing that establishes what it claims.
    for root, directories, files in os.walk(view, followlinks=False):
        for name in list(directories) + list(files):
            if name != ".git":
                continue
            here = Path(root) / name
            try:
                resolved = here.resolve(strict=True)
            except OSError as exc:
                raise IntegrityError(
                    "a .git in the constructed working tree does not resolve, so this build "
                    "cannot establish that Git will not read configuration the subject wrote",
                    entry=str(here), because=str(exc),
                ) from exc
            if resolved not in built:
                raise IntegrityError(
                    "a .git in the constructed working tree is not one this build made, so Git "
                    "could read configuration the subject wrote",
                    entry=str(here), resolves_to=str(resolved),
                    built=", ".join(sorted(str(one) for one in built)) or "nothing",
                )
        if ".git" in directories:
            directories.remove(".git")


@dataclass
class SterileRead:
    """One constructed environment, and the directory a command should run in."""

    scratch: Path
    gitdir: Path
    worktree: Path | None
    cwd: Path
    environment: dict = field(default_factory=dict)
    head: str | None = None

    def discard(self) -> None:
        shutil.rmtree(self.scratch, ignore_errors=True)


def _environment(scratch: Path, gitdir: Path, worktree: Path | None, overlay: dict | None,
                 extra_config: dict | None) -> dict:
    empty_config = scratch / "empty-config"
    empty_config.write_text("", encoding="utf-8")
    # HOME AND XDG_CONFIG_HOME POINT AT AN EMPTY DIRECTORY THIS BUILD OWNS.
    # `GIT_CONFIG_GLOBAL` redirects the global CONFIG file and nothing else, so
    # the operator's `~/.config/git/ignore` and `~/.config/git/attributes` were
    # still read — files `git config --show-scope` never lists, so the invariant's
    # own check could not see them. An independent design reading showed a
    # governed `status` silently dropping an untracked file because of one.
    # Removing the directory they live in removes the class, including whatever a
    # later Git puts there, rather than naming two keys and waiting for a third.
    home = scratch / "empty-home"
    home.mkdir(exist_ok=True)
    environment = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    environment.update({
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home),
        # A real empty file rather than `/dev/null`, so the mechanism is the same
        # on a platform that has no such device.
        "GIT_CONFIG_GLOBAL": str(empty_config),
        "GIT_CONFIG_SYSTEM": str(empty_config),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_DIR": str(gitdir),
        "GIT_INDEX_FILE": str(gitdir / "index"),
    })
    if worktree is not None:
        environment["GIT_WORK_TREE"] = str(worktree)
    if extra_config:
        environment["GIT_CONFIG_COUNT"] = str(len(extra_config))
        for index, (key, value) in enumerate(sorted(extra_config.items())):
            environment[f"GIT_CONFIG_KEY_{index}"] = key
            environment[f"GIT_CONFIG_VALUE_{index}"] = value
    environment.update(overlay or {})
    return environment


def build(repository, *, needs_working_tree: bool = True, overlay: dict | None = None,
          extra_config: dict | None = None, timeout: float = 30.0) -> SterileRead:
    """Construct the environment a governed read runs in, or refuse.

    `needs_working_tree` is false for a question about objects, refs or history,
    which is the cheap path: no working tree is constructed and none is offered.
    """
    subject = Path(repository).resolve()
    scratch = Path(tempfile.mkdtemp(prefix="rp-sterile-"))
    try:
        gitdir, head, reproducible = build_git_directory(subject, scratch / "sterile.git")
        worktree: Path | None = None
        cwd = subject
        if needs_working_tree and not _is_bare(subject):
            # The view exists for one reason: Git opens a repository it finds in
            # the working tree. Where there is none to find, the subject's own
            # tree is used and the view costs nothing.
            if nested_repository_paths(subject):
                worktree = _build_view(subject, scratch)
                cwd = worktree
            else:
                worktree = subject
                cwd = subject
        environment = _environment(scratch, gitdir, worktree, overlay, extra_config)
        _confirm_head(subject, gitdir, environment, cwd, head, reproducible, timeout)
        return SterileRead(scratch=scratch, gitdir=gitdir, worktree=worktree, cwd=cwd,
                           environment=environment, head=head)
    except BaseException:
        shutil.rmtree(scratch, ignore_errors=True)
        raise


def _is_bare(subject: Path) -> bool:
    dot = subject / ".git"
    return not dot.exists() and (subject / "HEAD").is_file() and (subject / "objects").is_dir()


def _confirm_head(subject: Path, gitdir: Path, environment: dict, cwd: Path,
                  head: str | None, reproducible: bool, timeout: float) -> None:
    """The build must reproduce the subject, or refuse to answer about it.

    Without this a `reftable` subject — a ref store this build does not import —
    reported every tracked file as newly ADDED, at exit 0. That is the worst
    failure available to a read: not a refusal, an answer.
    """
    try:
        probe = instrument.launch(
            ("git", "rev-parse", "HEAD"), radius=BLAST_RADIUS, cwd=str(cwd), env=environment,
            capture_output=True, text=True, check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        # A REFUSAL NAMES ITS CAUSE, and this one escaped as `TimeoutExpired`
        # from inside the construction — neither of this pack's refusals, and not
        # recognisable as one by any caller. Caught by the deadline tests that
        # already existed, which is the only reason it is a footnote.
        raise GitRefusal(
            "the constructed git directory timed out being confirmed against the subject, so "
            "this read is refused rather than answered. The deadline is the caller's own and "
            "this refusal names it, because an impatient caller that is handed a finding about "
            "the repository instead has been told the wrong thing",
            repository=str(subject), timeout=timeout,
        ) from exc
    except OSError as exc:
        raise GitRefusal(
            "the constructed git directory could not be confirmed against the subject",
            repository=str(subject), error=str(exc),
        ) from exc
    reproduced = probe.stdout.strip() if probe.returncode == 0 else None
    if not reproducible:
        # TWO UNKNOWNS COMPARING EQUAL IS NOT AGREEMENT. Without this a `reftable`
        # subject — whose refs this build does not copy — reported every tracked
        # file as newly ADDED, at exit 0. The check is on whether the store could
        # be reproduced at all, NOT on whether both sides happened to resolve
        # nothing: an ordinary repository whose HEAD names a branch nobody created
        # resolves nothing on both sides and is reproduced perfectly.
        raise GitRefusal(
            "this repository keeps its refs in a store this build does not import, so the "
            "constructed git directory cannot be shown to reproduce it and its HEAD is not "
            "evidence of anything. Refused rather than answered",
            repository=str(subject), git_directory=str(gitdir),
        )
    if head != reproduced:
        raise GitRefusal(
            "the constructed git directory does not reproduce the subject's HEAD, so a governed "
            "read of it would be an answer about a different repository",
            repository=str(subject), subject_head=head or "unresolved",
            reproduced=reproduced or "unresolved",
        )
