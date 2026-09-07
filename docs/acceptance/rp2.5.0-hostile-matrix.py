"""The hostile Git-configuration matrix for the 2.5.0 boundary, as a runnable file.

    python3 docs/acceptance/rp2.5.0-hostile-matrix.py [pack root]

An independent certification could reproduce the PROPERTY this measures but not
the figure the gate record cited, because the script lived in the author's
scratch directory and was not part of the release. A number a reader cannot
recompute is the thing this pack's own rule about figures exists to stop, so the
script ships.

Every row builds a real repository, points a real Git at it, and measures whether
a program ran by counting bytes a marker script appended. "Did it execute" is a
measurement here, never an inference.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools"))

import gitread                                                    # noqa: E402
from errors import GitRefusal, IntegrityError                     # noqa: E402

BASE = Path(tempfile.mkdtemp(prefix="rp250-matrix-"))
MARKER = BASE / "marker"
EVIL = BASE / "evil"
EVIL.write_text('#!/bin/sh\nprintf RAN >> "%s"\nif [ -n "${1:-}" ]; then cat "$1"; else cat; fi\n'
                % MARKER)
EVIL.chmod(0o755)
MARKER.write_bytes(b"")


def git(*arguments, cwd):
    return subprocess.run(["git", *arguments], cwd=str(cwd), capture_output=True, text=True)


def ran():
    return MARKER.stat().st_size if MARKER.exists() else 0


def reset():
    MARKER.write_bytes(b"")


def new_repo(name, *, at=None):
    repo = (at or BASE) / name
    repo.mkdir(parents=True)
    git("init", "-q", "-b", "main", ".", cwd=repo)
    return repo


def commit(repo, name="f.txt", body="hello\n"):
    (repo / name).write_text(body)
    git("add", "-A", cwd=repo)
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "c", cwd=repo)


def hostile(repo):
    """Every ordinary route by which a repository names a program for Git to run."""
    for key in ("filter.evil.clean", "filter.evil.smudge", "diff.evil.textconv",
                "diff.external", "core.fsmonitor", "core.alternateRefsCommand",
                "core.pager", "core.editor", "credential.helper", "gpg.program",
                "sequence.editor", "uploadpack.packObjectsHook", "core.gitProxy",
                "core.sshCommand", "core.askPass"):
        git("config", key, str(EVIL), cwd=repo)
    git("config", "core.hooksPath", str(EVIL.parent), cwd=repo)
    (repo / ".gitattributes").write_text("* diff=evil filter=evil\n")


ROWS = []


#: The invocation whose ANSWER every row is compared on. `status --porcelain`
#: reports repository STATE rather than file CONTENT, so a driver that rewrites
#: content does not change what a truthful answer looks like -- which is what
#: makes it a fair reference even on a row where the program did run. A content
#: verb like `diff` is not: there, real Git's output IS the driver's output, and
#: requiring the boundary to match it would assert the leak rather than refute it.
REFERENCE = ("status", "--porcelain")


def row(label, repo, *invocations, reference=REFERENCE):
    """Two measurements per row, because NOT EXECUTING IS ONLY HALF OF IT.

    A build that silently DROPPED every nested repository from the constructed
    view executes nothing at all -- and describes a repository that is not there.
    This script counted marker bytes and nothing else, so that mutant reported
    `0 execution leaks` at exit 0. The suite caught it; the evidence that ships
    did not, and the evidence that ships is what a reader recomputes.

    AND AN UNEXPECTED EXCEPTION IS A FAILURE, NOT A PRINTED OUTCOME. `Exception`
    was caught and rendered into the outcome column, where it read like a
    refusal, so a `FileExistsError` escaping the construction reported exit 0.
    """
    real_bytes = 0
    for arguments in invocations:
        reset()
        git(*arguments, cwd=repo)
        real_bytes = max(real_bytes, ran())
    guarded_bytes, outcome, escape = 0, "read", None
    for arguments in invocations:
        reset()
        try:
            answer = gitread.probe(repo, *arguments, negative_statuses=(1,))
            if not answer.answered:
                outcome = f"REFUSED: {answer.cause[:44]}"
        except (GitRefusal, IntegrityError) as refusal:
            outcome = f"REFUSED: {refusal.cause[:44]}"
        except Exception as exc:                                  # noqa: BLE001
            escape = f"{type(exc).__name__}: {exc}"
            outcome = f"ESCAPED: {escape}"[:60]
        guarded_bytes = max(guarded_bytes, ran())
    difference, compared = None, False
    if reference is not None and outcome == "read":
        expected = git(*reference, cwd=repo)
        # RESET BETWEEN THE REFERENCE AND THE MEASUREMENT. Real Git runs the
        # program on these fixtures -- that is the positive control -- so leaving
        # its marker bytes in place reported eight leaks that belonged to the
        # reference run. Caught by the pristine control, which is what one is for.
        reset()
        if expected.returncode == 0:
            try:
                answer = gitread.probe(repo, *reference, negative_statuses=(1,))
                if answer.answered and answer.ok:
                    compared = True
                    if answer.value.rstrip("\n") != expected.stdout.rstrip("\n"):
                        difference = (f"{' '.join(reference)}: "
                                      f"git={expected.stdout.rstrip(chr(10))!r} "
                                      f"boundary={answer.value.rstrip(chr(10))!r}")
            except Exception as exc:                              # noqa: BLE001
                escape = escape or f"{type(exc).__name__}: {exc}"
        guarded_bytes = max(guarded_bytes, ran())
    ROWS.append((label, real_bytes, guarded_bytes, outcome, difference, escape, compared))


VERBOSITY = [("status", spelling) for spelling in
             ("-v", "-vv", "-vvv", "--verbose", "--verb", "--verbo")]

flat = new_repo("flat")
hostile(flat)
commit(flat)
(flat / "f.txt").write_text("changed\n")
git("add", "-A", cwd=flat)
row("every verbosity spelling", flat, *VERBOSITY)
row("an explicitly requested driver", flat,
    ("diff", "--textconv", "--cached"), ("diff", "--ext-diff", "--cached"))
row("history verbs", flat, ("log", "-p", "-1"), ("show", "HEAD"), ("diff", "--cached"))

ignored = new_repo("ignored")
(ignored / ".gitignore").write_text("cache/\n")
commit(ignored, "keep.txt")
dependency = new_repo("dependency", at=ignored / "cache")
hostile(dependency)
commit(dependency, "d.txt")
(ignored / "untracked.py").write_text("y = 2\n")
row("an ignored, never-a-submodule checkout", ignored,
    ("status", "--porcelain"), ("status", "--porcelain", "-uall"), ("ls-files", "-z"))

inner = new_repo("inner")
(inner / ".gitattributes").write_text("* diff=evil filter=evil\n")
commit(inner, "i.txt")
for spelling in ("gitlink file", "symlink to directory", "symlink to gitlink file"):
    sup = new_repo(f"sup-{spelling.replace(' ', '-')}")
    commit(sup, "top.txt")
    git("-c", "protocol.file.allow=always", "submodule", "add", "-q", str(inner), "mod", cwd=sup)
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "sub", cwd=sup)
    module = sup / ".git" / "modules" / "mod"
    for key in ("filter.evil.clean", "diff.evil.textconv", "diff.external"):
        git("config", key, str(EVIL), cwd=module)
    entry = sup / "mod" / ".git"
    if spelling != "gitlink file":
        entry.unlink()
        if spelling == "symlink to directory":
            os.symlink(module, entry)
        else:
            pointer = sup / "pointer"
            pointer.write_text(f"gitdir: {module}\n")
            os.symlink(pointer, entry)
    (sup / "mod" / "i.txt").write_text("changed\n")
    row(f"nested .git as a {spelling}", sup,
        ("status", "--porcelain"), ("status", "-v"), ("diff", "--submodule=diff"))

# A CASE VARIANT OF THE NAME. `os.path.lexists(here / ".git")` is answered by the
# FILESYSTEM, and a case-insensitive volume answers it YES for `.Git`; comparing a
# walked name to the literal `".git"` answers NO. The build asked one question two
# ways, got two answers, copied the `.Git` into the view verbatim and then raised
# `FileExistsError` installing its own -- which reached the operator as a traceback
# out of a shipped tool rather than as a refusal. On a case-SENSITIVE volume Git
# does not find `.Git` either, so this row is an ordinary read there and honestly
# reports no positive control.
variant = new_repo("sup-case-variant")
commit(variant, "top.txt")
git("-c", "protocol.file.allow=always", "submodule", "add", "-q", str(inner), "mod", cwd=variant)
git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "sub", cwd=variant)
variant_module = variant / ".git" / "modules" / "mod"
for key in ("filter.evil.clean", "diff.evil.textconv", "diff.external"):
    git("config", key, str(EVIL), cwd=variant_module)
os.rename(variant / "mod" / ".git", variant / "mod" / ".Git")
(variant / "mod" / "i.txt").write_text("changed\n")
row("a nested .git spelled .Git", variant,
    ("status", "--porcelain"), ("status", "-v"), ("diff", "--submodule=diff"))

for kind in ("dangling symlink", "empty file", "fifo"):
    outer = new_repo(f"unbuildable-{kind.replace(' ', '-')}")
    commit(outer)
    nest = outer / "nest"
    nest.mkdir()
    entry = nest / ".git"
    if kind == "dangling symlink":
        os.symlink(BASE / "nothing-is-here", entry)
    elif kind == "empty file":
        entry.write_text("")
    else:
        os.mkfifo(entry)
    row(f"a nested .git that is a {kind}", outer, ("status", "--porcelain"))

for label, flag in (("sha256 object format", "--object-format=sha256"),
                    ("reftable ref storage", "--ref-format=reftable")):
    directory = BASE / label.replace(" ", "-")
    directory.mkdir()
    if git("init", "-q", "-b", "main", flag, ".", cwd=directory).returncode:
        continue
    hostile(directory)
    commit(directory)
    (directory / "f.txt").write_text("changed\n")
    row(label, directory, ("rev-parse", "HEAD"), ("status", "--porcelain"))

separate = BASE / "separate"
elsewhere = BASE / "elsewhere.git"
git("init", "-q", "-b", "main", "--separate-git-dir", str(elsewhere), str(separate), cwd=BASE)
hostile(separate)
commit(separate)
(separate / "f.txt").write_text("changed\n")
row("a .git that is a file (--separate-git-dir)", separate,
    ("status", "--porcelain"), ("status", "-v"), ("diff",))

width = max(len(label) for label, *_ in ROWS)
print(f"{'case':{width}}  real  guarded  outcome")
print("-" * (width + 34))
leaks = differing = escapes = compared = 0
for label, real_bytes, guarded_bytes, outcome, difference, escape, matched in ROWS:
    leaks += guarded_bytes > 0
    differing += difference is not None
    escapes += escape is not None
    compared += matched
    print(f"{label:{width}}  {real_bytes:>4}  {guarded_bytes:>7}  "
          f"{'*** LEAK *** ' if guarded_bytes else ''}"
          f"{'*** ANSWER DIFFERS *** ' if difference else ''}{outcome}")
    if difference:
        print(f"{'':{width}}    {difference}")
controls = sum(1 for _l, real_bytes, *_ in ROWS if real_bytes > 0)
print(f"\n{len(ROWS)} cases, {controls} of them carrying a positive control "
      f"(real git ran a program), {leaks} execution leaks, "
      f"{compared} rows whose answer was compared with real git, "
      f"{differing} of them differing, {escapes} escaped exceptions")
print(f"fixtures {BASE}")
# A COMPARISON THAT COMPARED NOTHING IS NOT A PASS, for the same reason a row
# without a positive control is not one: an oracle has to be shown able to fail.
sys.exit(1 if leaks or differing or escapes or compared == 0 else 0)
