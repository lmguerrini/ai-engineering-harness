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

ONE READ IS THE DELIBERATE EXCEPTION, AND IT IS THE POINT OF THAT READ. A
`config` read's SUBJECT MATTER is the repository's own configuration: the
boundary directs Git at the subject's `config` on purpose, `--show-origin`
reports that file as the origin, and `config_with_origin` exists to say which
file each setting came from. What the sentence above governs is the
configuration that can change HOW GIT BEHAVES while answering, and no part of
the subject's configuration reaches that. Two independent certifications read
the sentence as universal and falsified it on this route, so the scope is
written here rather than left to be re-derived from `tools/gitread.py`.

`GIT_DIR` decides which files are local and worktree configuration, and the
caller chooses `GIT_DIR`. So the harness builds the git directory: its own
configuration root from a blank slate, the subject's objects attached rather
than copied, and every other git-directory entry carried as plain data.

**This build omits two categories by name: configuration roots, and the
subject's own programs.** Every route Git has for extending repository
configuration is declared from the subject's own `config`, so replacing that
root removes the whole graph. The complement is carried by enumerating the
directory, not by guessing which state the next Git feature will need. 2.4.1's
denylist and this module's former short state list both failed by growing one
missed name at a time.

Enumerating the directory is the right rule for STATE and the wrong rule for
PROGRAMS. `hooks/` holds executables the subject wrote, and carrying them made
an ordinary governed read run one: refreshing the constructed index fired
`post-index-change` outside the no-child barrier, with the subject's working
tree as its working directory. A program is not state, and this is the whole
of the exception — `_PROGRAM_ROOTS`.
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

#: Branch tracking is data about the subject's ref relationship, not a choice of
#: program or transport.  `status --porcelain=v2 --branch` asks Git to render it,
#: so replacing configuration without carrying these two values made the
#: constructed answer silently lose `branch.upstream` and `branch.ab`.  As with
#: STORAGE_KEYS, a missing entry can only make a read differ; it cannot execute.
BRANCH_TRACKING_KEYS = frozenset({"remote", "merge"})

#: A branch's remote name is resolved to its tracking ref through this mapping.
#: `remote.<name>.fetch` is refspec data, not an address or a program setting;
#: retaining just it lets porcelain render branch.upstream without handing Git a
#: URL, helper, or any other remote behaviour.
REMOTE_TRACKING_KEYS = frozenset({"fetch"})

#: These are configuration ROOTS, rather than ordinary git-directory state.
#:
#: Git only opens `config.worktree` after `extensions.worktreeConfig` in `config`
#: tells it to, and `include.path` and `includeIf` can only name another file from
#: `config`.  In other words every route by which the subject's configuration can
#: enter is declared in that one subject-owned root.  Replacing both roots with
#: the harness's generated `config` therefore excludes the whole graph; copying a
#: list of include keys could never make that claim.  The names are ignored at
#: every level because `modules/` and `worktrees/` contain the same Git layouts.
CONFIGURATION_ROOTS = frozenset({"config", "config.worktree"})

#: Executable programs the SUBJECT wrote, which are not state to reproduce.
#: `hooks/` holds programs, and a program carried into the constructed git
#: directory is a program Git will RUN — `post-index-change` fires when the
#: constructed index is refreshed, before the local no-child barrier exists.
#: Frozen 2.4.0 neutralised this with `core.hooksPath`; that closure was deleted
#: with the environment layer and nothing replaced it.  Enumerating the
#: directory is the right rule for STATE and the wrong rule for PROGRAMS.
#: `shutil.ignore_patterns` is applied at every directory level, so this also
#: covers `modules/*/hooks` for a subject carrying submodule git directories.
_PROGRAM_ROOTS = frozenset({"hooks"})

#: `commondir` is a layout pointer, not state to reproduce verbatim.  A linked
#: worktree's common and private directories are merged into one sterile directory;
#: carrying the pointer would send Git back to the subject's common directory.
_LAYOUT_MARKERS = frozenset({"commondir"})

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
    if os.path.lexists(dot):
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
        # `Path.exists()` is false for a dangling symlink.  Treating that as an
        # absent `.git` made a directory that happened also to have `HEAD` and
        # `objects/` look bare, even though Git will first open the broken entry.
        raise GitRefusal(
            "the .git entry does not resolve to a git directory",
            repository=str(subject), entry=str(dot),
        )
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


def _without_config_comment(text: str) -> str:
    """Return the part before Git's next unquoted comment introducer."""
    quoted = False
    index = 0
    while index < len(text):
        character = text[index]
        if quoted and character == "\\":
            # The following quote, if any, is escaped.  Whether the escape is
            # valid is the value decoder's concern; it cannot end this run.
            index += 2
            continue
        if character == '"':
            quoted = not quoted
        elif not quoted and character in "#;":
            return text[:index]
        index += 1
    return text


def _config_value_as_data(text: str) -> str:
    """Decode one Git configuration VALUE without asking Git to read it.

    Git strips whitespace only when it is outside quoted runs.  Keeping the
    provenance of each character until that trim is complete is important:
    applying ``str.strip`` after decoding loses whitespace that a pair of
    quotes deliberately preserved.
    """
    characters: list[tuple[str, bool]] = []
    quoted = False
    index = 0
    escapes = {'"': '"', "\\": "\\", "n": "\n", "t": "\t", "b": "\b"}
    while index < len(text):
        character = text[index]
        if not quoted:
            if character in "#;":
                break
            if character == '"':
                quoted = True
            else:
                characters.append((character, False))
            index += 1
            continue
        if character == '"':
            quoted = False
            index += 1
            continue
        if character == "\\" and index + 1 < len(text):
            escaped = text[index + 1]
            # Git accepts precisely these escapes in a quoted configuration
            # value.  Valid repository configuration reaches this parser; keep
            # an invalid escape literal here so the caller does not mistake its
            # spelling for a different, valid value.
            characters.append((escapes.get(escaped, "\\" + escaped), True))
            index += 2
            continue
        characters.append((character, True))
        index += 1

    while characters and not characters[0][1] and characters[0][0] in " \t":
        characters.pop(0)
    while characters and not characters[-1][1] and characters[-1][0] in " \t":
        characters.pop()
    return "".join(character for character, _quoted in characters)


def config_as_data(path: Path) -> dict:
    """Parse a Git config FILE as text, including Git's VALUE syntax.

    Nothing read here is ever handed to Git, so nothing here can execute. This is
    how the storage descriptors are learned and how a caller reads a repository's
    own settings — a remote's URL, say — without Git resolving them.  Values use
    Git's quoting, escaping and comment rules so these answer-bearing reads agree
    with ``git config --get`` rather than with an approximation of it.

    A repeated key collapses to its LAST value, which is what Git resolves for a
    single-valued setting.  A MULTI-valued key is a different question and this
    answer cannot carry it: use `config_values_as_data`.  A certification found
    `ls-remote origin` reporting the wrong repository's HEAD at exit 0 because
    the first of two `remote.origin.url` values was lost here.
    """
    return {name: found[-1] for name, found in config_values_as_data(path).items()}


def config_values_as_data(path: Path) -> dict:
    """Every value of every key, in file order, under the same value syntax.

    Git keeps repeated keys rather than overwriting them, and which one it
    resolves depends on the key: the LAST for a single-valued setting, the FIRST
    of `remote.<name>.url` for the address a fetch contacts.  Deciding that is
    the caller's business, so this reports all of them and decides nothing.
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
        if not line:
            continue
        header = _without_config_comment(line).strip() if line.startswith("[") else line
        if header.startswith("[") and header.endswith("]"):
            inner = header[1:-1].strip()
            head, _, tail = inner.partition(" ")
            # Git folds the SECTION and the VARIABLE to lower case and keeps a
            # SUBSECTION verbatim. 2.4.1 shipped a defect for not knowing that,
            # and this parser is only ever used to read, so it follows the same
            # rule rather than a convenient one.
            section = head.lower() if not tail else f"{head.lower()}.{tail.strip().strip(chr(34))}"
            continue
        key, sep, value = line.partition("=")
        name = f"{section}.{key.strip().lower()}" if section else key.strip().lower()
        values.setdefault(name, []).append(
            _config_value_as_data(value) if sep else "true")
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


def _enabled(value: str | None) -> bool:
    """The Git boolean spellings relevant to configuration-root selection."""
    return (value or "").strip().lower() in {"true", "yes", "on", "1"}


def _write_config(into: Path, common: Path, gitdir: Path, *, bare: bool) -> None:
    """The only configuration Git will read, written from a blank slate.

    ``config.worktree`` is a configuration root, not a file to copy.  Its
    storage descriptors nevertheless describe the subject's working tree, and
    Git layers them after the common configuration when that root is enabled.
    Carry those safe descriptors in the same order while leaving every other
    setting outside the constructed configuration.
    """
    common_declared = config_as_data(common / "config")
    declared = dict(common_declared)
    # The same declarations, keeping every value a repeated key carries. The
    # single-valued view above still decides what is PRESENT and what a storage
    # descriptor resolves to; this one is what the carried-verbatim sections are
    # written from, so a multi-valued setting reaches Git whole.
    all_declared = config_values_as_data(common / "config")
    if _enabled(common_declared.get("extensions.worktreeconfig")):
        worktree_declared = config_as_data(gitdir / "config.worktree")
        if any(
            name == "include.path"
            or (name.startswith("includeif.") and name.endswith(".path"))
            for name in worktree_declared
        ):
            raise GitRefusal(
                "the active config.worktree includes another configuration file, so its "
                "storage descriptors cannot be copied as a partial configuration",
                configuration=str(gitdir / "config.worktree"),
            )
        declared.update(worktree_declared)
        all_declared.update(config_values_as_data(gitdir / "config.worktree"))
    core = {
        name[len("core."):]: value
        for name, value in declared.items()
        if name in STORAGE_KEYS and name.startswith("core.")
    }
    core.setdefault("repositoryformatversion", "0")
    # A bare subject has no working tree.  Giving its constructed git directory
    # ``core.bare = false`` makes Git reinterpret the subject's metadata as a
    # working tree, refusing history reads and inventing untracked internals.
    core["bare"] = "true" if bare else "false"
    # Git looks for hooks in `core.hooksPath`, falling back to `$GIT_DIR/hooks`.
    # `_PROGRAM_ROOTS` keeps the subject's programs out of the constructed
    # directory; this closes the other half, so a `hooksPath` the subject
    # declared cannot reach outside it either.  An empty directory this build
    # owns, rather than `/dev/null`, for the same reason the empty config file
    # is a real file: the mechanism is then the same on a platform without it.
    empty_hooks = into / "empty-hooks"
    empty_hooks.mkdir(parents=True, exist_ok=True)
    core["hookspath"] = str(empty_hooks)
    lines = ["[core]\n"] + [f"\t{key} = {value}\n" for key, value in sorted(core.items())]
    # `objectFormat` describes the common object store's encoding.  It is read
    # from `config`, not `config.worktree`, so only the common declaration may
    # describe the alternates attached below.  `worktreeConfig` does NOT belong
    # here: it declares a second configuration root.  Carrying it would make our
    # generated `config` ask Git to read the subject's `config.worktree`,
    # defeating replacement of the root before an include or key-level check
    # could help.
    extensions = {
        name[len("extensions."):]: value
        for name, value in common_declared.items()
        if name == "extensions.objectformat"
    }
    if extensions:
        lines.append("[extensions]\n")
        lines += [f"\t{key} = {value}\n" for key, value in sorted(extensions.items())]
    branch_tracking: dict[str, dict[str, str]] = {}
    for name, value in declared.items():
        if not name.startswith("branch."):
            continue
        branch, separator, setting = name[len("branch."):].rpartition(".")
        if separator and setting in BRANCH_TRACKING_KEYS:
            branch_tracking.setdefault(branch, {})[setting] = all_declared.get(name, [value])
    for branch, settings in sorted(branch_tracking.items()):
        lines.append(f'[branch "{branch}"]\n')
        lines += [f"\t{key} = {one}\n"
                  for key, found in sorted(settings.items()) for one in found]
    # CARRIED VERBATIM MEANS EVERY VALUE, IN FILE ORDER.
    #
    # `remote.<name>.fetch` is multi-valued: Git uses the WHOLE refspec list to
    # decide a branch's upstream. Reconstructing this section from the
    # single-valued view kept only the last one, and an ordinary
    # `status --porcelain=v2 --branch` then answered with no `branch.upstream`
    # and no `branch.ab` at exit 0 — a false answer, not a refusal, and a
    # regression against the floor. A certification found it in the neighbour of
    # the `remote.<name>.url` repair, which is where a second instance of a
    # class this shape belongs. `core` and `extensions` above stay single-valued
    # deliberately: they are storage descriptors this build OWNS, and Git
    # resolves the last value for them, which is what it is given.
    remote_tracking: dict[str, dict[str, list]] = {}
    for name, value in declared.items():
        if not name.startswith("remote."):
            continue
        remote, separator, setting = name[len("remote."):].rpartition(".")
        if separator and setting in REMOTE_TRACKING_KEYS:
            remote_tracking.setdefault(remote, {})[setting] = all_declared.get(name, [value])
    for remote, settings in sorted(remote_tracking.items()):
        lines.append(f'[remote "{remote}"]\n')
        lines += [f"\t{key} = {one}\n"
                  for key, found in sorted(settings.items()) for one in found]
    (into / "config").write_text("".join(lines), encoding="utf-8")


def _copy_git_state(source: Path, into: Path) -> None:
    """Carry every git-directory file except configuration roots and objects.

    The object database is carried by attachment below: copying it would make
    every governed read proportional to repository size.  Every other entry is
    copied by the directory's own enumeration, not by a growing list of names.
    That is why reflogs, pseudorefs, grafts, and state Git adds later arrive
    without this boundary having to predict them.
    """
    if not source.is_dir():
        return
    try:
        # State is copied as data, not as topology.  In particular an index
        # symlink would otherwise remain a route from the scratch pathname to
        # a subject-owned target when the constructed index is refreshed.
        # `symlinks=False` follows every carried link and writes a regular file
        # or directory in `into`; a dangling or unreadable target makes
        # copytree fail instead of being silently omitted.
        shutil.copytree(
            source,
            into,
            dirs_exist_ok=True,
            symlinks=False,
            ignore=shutil.ignore_patterns(
                *CONFIGURATION_ROOTS,
                *_PROGRAM_ROOTS,
                *_LAYOUT_MARKERS,
                "objects",
            ),
        )
        _materialise_symbolic_refs(source, into)
    except (OSError, shutil.Error) as exc:
        raise GitRefusal(
            "the git-directory state could not be materialised as plain files; a dangling "
            "or unreadable symbolic link is refused rather than skipped",
            source=str(source), because=f"{type(exc).__name__}: {exc}",
        ) from exc


def _materialise_symbolic_refs(source: Path, into: Path) -> None:
    """Preserve a symlinked symbolic ref without preserving the symlink.

    A symlinked ``HEAD`` or loose ref is a symbolic reference in Git's state,
    not merely an alternate spelling for the target file's bytes.  Dereferencing
    it into a hash makes a branch look detached.  Its ordinary-file equivalent
    is ``ref: <target>``, which carries the same reference relationship while
    keeping every entry in the constructed directory materialised.
    """
    source_root = source.resolve()
    for root, directories, files in os.walk(source, followlinks=False):
        for name in [*directories, *files]:
            original = Path(root) / name
            if not original.is_symlink():
                continue
            relative = original.relative_to(source)
            if relative != Path("HEAD") and relative.parts[:1] != ("refs",):
                continue
            try:
                target = original.resolve(strict=True)
                reference = target.relative_to(source_root)
            except (OSError, ValueError):
                continue
            if target.is_file():
                (into / relative).write_text(
                    f"ref: {reference.as_posix()}\n", encoding="utf-8",
                )


def build_git_directory(subject: Path, into: Path) -> tuple:
    """Construct a git directory the harness owns over the subject's object store."""
    subject = Path(subject).resolve()
    gitdir = _git_directory(subject)
    common = _common_directory(gitdir)
    if into.exists():
        shutil.rmtree(into)
    (into / "objects" / "info").mkdir(parents=True)
    # A linked worktree divides its state between `common` and `gitdir`.  The
    # sterile directory deliberately has no such division, so carry both in the
    # order Git layers them: common state first, then this worktree's state.
    _copy_git_state(common, into)
    if gitdir.resolve() != common.resolve():
        _copy_git_state(gitdir, into)
    _write_config(into, common, gitdir, bare=_is_bare(subject))
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
    return into, _head_as_data(gitdir, common), _ref_store_is_reproducible(gitdir, common)


#: The name Git opens a repository from in a working tree. Compared through the
#: FILESYSTEM rather than as a string, because the two are not the same question.
DOT_GIT = ".git"


def dot_git_name(here: Path, names) -> "str | None":
    """The on-disk spelling of the entry Git will open as `.git` in `here`.

    `os.path.lexists(here / ".git")` is answered by the filesystem, and a
    case-insensitive volume answers it YES for `.GIT` and `.Git` as well. Asking
    the same question a second way, by comparing a walked name to the literal
    `".git"`, gave a different answer -- so the detector saw a nested repository
    that the copier then reproduced into the view verbatim, and the build tried
    to install its own `.git` over a name that already existed. One question, one
    answer, and the answer comes from the filesystem that Git will itself consult.

    Returns None where Git would not find a repository here at all, which on a
    case-SENSITIVE volume is exactly what `.GIT` means.
    """
    probe = here / DOT_GIT
    if not os.path.lexists(probe):
        return None
    try:
        target = os.lstat(probe)
    except OSError:
        return DOT_GIT
    for name in names:
        try:
            if os.path.samestat(os.lstat(here / name), target):
                return name
        except OSError:
            continue
    return DOT_GIT


def _refuse_unreadable(error: OSError) -> None:
    """`os.walk` swallows a directory it cannot read and simply yields less.

    A view built from a walk that skipped one is a SMALLER TREE than the subject,
    and Git answers confidently about it: a tracked file under an unreadable
    directory came back reported as DELETED while real Git said nothing. That is a
    wrong answer at exit 0 produced by an inability to look, which is the state this
    design refuses rather than answers.
    """
    raise GitRefusal(
        "a directory inside the working tree could not be read, so the view would be a "
        "smaller tree than the subject and every answer taken from it would describe a "
        "repository that is not there",
        path=str(getattr(error, "filename", "") or "(unknown)"),
        because=f"{type(error).__name__}: {error}",
    )


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
    for root, directories, files in os.walk(subject, followlinks=False,
                                            onerror=_refuse_unreadable):
        here = Path(root)
        relative = here.relative_to(subject)
        if ".git" in relative.parts:
            directories[:] = []
            continue
        entry = dot_git_name(here, list(directories) + list(files))
        if entry in directories:
            directories.remove(entry)
        if entry in files:
            files.remove(entry)
        if relative != Path(".") and entry is not None:
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
    for root, directories, files in os.walk(subject, followlinks=False,
                                            onerror=_refuse_unreadable):
        here = Path(root)
        relative = here.relative_to(subject)
        if ".git" in relative.parts:
            directories[:] = []
            continue
        (view / relative).mkdir(parents=True, exist_ok=True)
        # THE NAME FIRST, before anything classifies it, and removed from both
        # lists so that no later branch can reproduce it. The directory-symlink
        # branch below is exactly the branch that used to. The name is resolved
        # through the filesystem, so a case-insensitive volume's `.GIT` is removed
        # here rather than copied and then collided with.
        entry = dot_git_name(here, list(directories) + list(files))
        if entry in directories:
            directories.remove(entry)
        if entry in files:
            files.remove(entry)
        if relative != Path(".") and entry is not None:
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
            if source.is_symlink():
                # THE SYMLINK BRANCH RUNS FIRST, BECAUSE `os.link` NEVER FAILS ON ONE.
                #
                # `os.link` follows symlinks by default, so it succeeded and made a
                # hard link to the TARGET -- a committed symlink arrived in the view
                # as an ordinary file. Git compared mode 100644 against the 120000
                # in the index and reported `T` for a typechange the subject does
                # not have, and `diff` invented a deleted file mode. The handling
                # was already written, and it sat in an `except OSError` that the
                # one case needing it could never reach. Deciding by what the entry
                # IS, before attempting anything, is the same order the `.git` name
                # check uses above, and for the same reason.
                os.symlink(os.readlink(source), destination)
                continue
            # A hard link changes the source file's ctime.  In a tree that also
            # contains a nested repository, that makes a later Git read re-stat
            # an outer-tracked path below the nested boundary and report it
            # modified even though its bytes never changed.  The view must not
            # perturb the subject it represents, so regular files are copied with
            # their metadata rather than attached to it.
            shutil.copyfile(source, destination, follow_symlinks=False)
            shutil.copystat(source, destination, follow_symlinks=False)
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
        # The SAME predicate the build used. Comparing the walked name to the
        # literal `".git"` here would skip the spelling a case-insensitive volume
        # resolves, which is the one route by which a `.git` the build did not
        # make could sit in the view unexamined.
        name = dot_git_name(Path(root), list(directories) + list(files))
        if name is not None:
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
            if name in directories:
                directories.remove(name)


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


def _environment(scratch: Path, gitdir: Path, worktree: Path | None, cwd: Path, overlay: dict | None,
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
        # Git preserves the spelling it was handed for `--git-dir`, while
        # `--absolute-git-dir` resolves it.  A relative scratch spelling gives
        # `_run` one general pathname-rebasing rule for both answers instead of
        # a growing list of rev-parse option spellings.
        "GIT_DIR": os.path.relpath(gitdir, cwd),
        "GIT_INDEX_FILE": str(gitdir / "index"),
    })
    if worktree is not None:
        environment["GIT_WORK_TREE"] = str(worktree)
    if extra_config:
        environment["GIT_CONFIG_COUNT"] = str(len(extra_config))
        for index, (key, value) in enumerate(sorted(extra_config.items())):
            environment[f"GIT_CONFIG_KEY_{index}"] = key
            environment[f"GIT_CONFIG_VALUE_{index}"] = value
    # An overlay may ADD an ordinary environment variable, but it must never
    # replace a value this build constructed.  Take the protected names from
    # the finished mapping, rather than duplicating the environment above: a
    # new harness-owned variable is protected as soon as it is added there.
    #
    # Git names are closed by default even when this build did not set one.
    # Trace2 is the one deliberate exception: `_run` validates its path before
    # supplying the no-child witness, and composed reads carry that same
    # caller-requested witness through every primitive.
    overlay = overlay or {}
    replaced = sorted(name for name in overlay if name in environment)
    undelegated_git = sorted(
        name for name in overlay
        if name.startswith("GIT_") and name != "GIT_TRACE2_EVENT"
    )
    if replaced or undelegated_git:
        reasons = []
        if replaced:
            reasons.append("replaces harness-owned " + ", ".join(replaced))
        if undelegated_git:
            reasons.append("sets undelegated Git name " + ", ".join(undelegated_git))
        raise GitRefusal(
            "the environment overlay is refused: " + "; ".join(reasons),
            replaced=", ".join(replaced) or "(none)",
            undelegated_git=", ".join(undelegated_git) or "(none)",
        )
    environment.update(overlay)
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
        constructed_view = False
        if needs_working_tree and not _is_bare(subject):
            source_worktree = _declared_worktree(subject) or subject
            # The view exists for one reason: Git opens a repository it finds in
            # the working tree. Where there is none to find, the subject's own
            # tree is used and the view costs nothing.
            if nested_repository_paths(source_worktree):
                worktree = _build_view(source_worktree, scratch)
                cwd = worktree
                constructed_view = True
            else:
                worktree = source_worktree
                cwd = source_worktree
        environment = _environment(scratch, gitdir, worktree, cwd, overlay, extra_config)
        # The scratch index is a copy even when the working tree is the subject.
        # Its cached stat data is therefore stale in both layouts.  Refreshing
        # only when a view existed left `diff-index` calling clean files modified;
        # refreshing this owned copy is the one rule that fixes ordinary, nested,
        # and linked-worktree reads without touching the subject.
        #
        # A BARE SUBJECT HAS NO WORKING TREE TO REFRESH AGAINST, and asking Git
        # to do it there is not a stale-stat problem but a category error: Git
        # reports a real failure, which this build correctly treats as a refusal,
        # and an ordinary history read of a bare repository refused. The rule is
        # about aligning an index with the tree it describes, so where there is
        # no tree there is nothing to align.
        if worktree is not None:
            _refresh_constructed_index(subject, gitdir, environment, cwd, timeout)
        _confirm_head(subject, gitdir, environment, cwd, head, reproducible, timeout)
        return SterileRead(scratch=scratch, gitdir=gitdir, worktree=worktree, cwd=cwd,
                           environment=environment, head=head)
    except (GitRefusal, IntegrityError):
        shutil.rmtree(scratch, ignore_errors=True)
        raise
    except (KeyboardInterrupt, SystemExit):
        shutil.rmtree(scratch, ignore_errors=True)
        raise
    except BaseException as exc:
        # EVERY WAY THIS CONSTRUCTION CAN FAIL IS A REFUSAL, NOT A TRACEBACK.
        #
        # `errors.run_cli` catches `HxError` and `gitread.probe` catches
        # `GitRefusal`, so anything else escapes both and reaches the operator as
        # an unhandled traceback indistinguishable from a bug in the tool -- the
        # exact defect this pack recorded when three tools crashed identically.
        # It was repaired once for ONE spelling, a `subprocess.TimeoutExpired`
        # escaping the construction, and a second spelling then arrived: an
        # ordinary directory named `.Git` on a case-insensitive volume raised
        # `FileExistsError` out of the view builder. Repairing spellings does not
        # converge, so the CLASS is closed here instead.
        shutil.rmtree(scratch, ignore_errors=True)
        raise GitRefusal(
            "the sterile construction could not be completed, so this read is refused rather "
            "than performed against configuration the subject wrote",
            repository=str(subject), because=f"{type(exc).__name__}: {exc}",
        ) from exc


def _is_bare(subject: Path) -> bool:
    subject = Path(subject).resolve()
    dot = subject / ".git"
    return (
        not os.path.lexists(dot)
        and (subject / "HEAD").is_file()
        and (subject / "objects").is_dir()
        and _declared_worktree(subject) is None
    )


def _declared_worktree(subject: Path) -> Path | None:
    """The worktree of a bare-shaped git directory that explicitly has one.

    A conventional bare repository is identified by its own ``HEAD`` and
    ``objects/`` entries.  Git also supports that shape as a git directory for
    a separate worktree: it declares both ``core.bare = false`` and
    ``core.worktree`` in the common configuration.  The latter is layout data,
    not a setting copied into the constructed configuration; the harness uses
    it only to select the tree whose contents it mirrors.
    """
    subject = Path(subject).resolve()
    dot = subject / ".git"
    if os.path.lexists(dot) or not (subject / "HEAD").is_file() or not (subject / "objects").is_dir():
        return None
    declared = config_as_data(subject / "config")
    bare = (declared.get("core.bare") or "").strip().lower()
    raw = (declared.get("core.worktree") or "").strip()
    if bare not in {"false", "no", "off", "0"} or not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else (subject / path).resolve()


def _refresh_constructed_index(subject: Path, gitdir: Path, environment: dict, cwd: Path,
                               timeout: float) -> None:
    """Match the copied index's stat cache to the constructed working tree.

    A copied file necessarily has a new ctime.  The copied index still names the
    source ctime, so Git can report a clean file as modified before it compares
    contents; paths below a nested repository are especially affected because
    Git will not descend to establish equality.  Refresh only the scratch index
    after the complete view exists.  Nothing in this invocation addresses the
    subject's git directory, index, or working tree.
    """
    try:
        refreshed = instrument.launch(
            ("git", "update-index", "--refresh"), radius=BLAST_RADIUS, cwd=str(cwd),
            env=environment, capture_output=True, text=True, check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitRefusal(
            "the constructed index timed out being refreshed against its constructed working "
            "tree, so this read is refused rather than answered",
            repository=str(subject), timeout=timeout,
        ) from exc
    except OSError as exc:
        raise GitRefusal(
            "the constructed index could not be refreshed against its constructed working tree",
            repository=str(subject), git_directory=str(gitdir), error=str(exc),
        ) from exc
    # `update-index --refresh` EXITS NON-ZERO WHEN ENTRIES DIFFER, and that is
    # information rather than failure: it is how Git says "these paths need
    # updating", which is the ordinary state of any repository with a modified
    # file. A first version treated the exit status as a refusal, and because
    # this refresh now runs for every constructed read, **every governed read of
    # an ordinary dirty repository refused** — 39 suite failures, including the
    # pin's own machinery, from one over-refusal.
    #
    # `fail-closed is the correct polarity and it is not a licence to
    # over-refuse` is already this record's own conclusion from the split-index
    # repair. So a real failure is distinguished from a report: Git writes
    # `fatal:` or `error:` to stderr when it could not do the work, and says
    # nothing there when it merely has paths to report.
    #
    # Failing to align the stat cache is not a correctness problem either way.
    # Git still compares content when the stat data disagrees, so an unrefreshed
    # index costs a comparison, never an answer.
    trouble = (refreshed.stderr or "")
    if refreshed.returncode != 0 and ("fatal:" in trouble or "error:" in trouble):
        raise GitRefusal(
            "the constructed index could not be refreshed against its constructed working tree",
            repository=str(subject), git_directory=str(gitdir), returncode=refreshed.returncode,
            stderr=trouble, stdout=refreshed.stdout or "",
        )


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
