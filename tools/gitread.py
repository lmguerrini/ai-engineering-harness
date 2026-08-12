"""A deliberately small, read-only Git interface.

Frozen coordinator decision (D2): this is a subset of the kernel's
``hx/gitops.py`` (1,455 lines), not the whole module. Extracted here are
exactly the functions the toolbelt's read-only checkers call — ``_run``,
``probe``, ``commit_message``, ``commit_metadata``, ``whitespace_damage``,
``objects_in_outgoing_range``, ``paths_in_outgoing_range``, ``object_type``,
``object_size``, ``object_bytes``, ``tag_object`` — plus the module-level
environment hardening they depend on.

There is no Git *write* verb anywhere in this module, on purpose: a
report-only toolbelt must not carry the capability to change state, and
keeping the whole module would import write capability into a layer whose
defining property is that it cannot.
"""

from __future__ import annotations

import math
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from errors import GitRefusal

__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "ProbeAnswer",
    "probe",
    "commit_message",
    "commit_metadata",
    "whitespace_damage",
    "objects_in_outgoing_range",
    "paths_in_outgoing_range",
    "object_type",
    "object_size",
    "object_bytes",
    "tag_object",
]

DEFAULT_TIMEOUT_SECONDS = 30.0

# The wording is intentionally duplicated in the implementation, rather than
# left only to an architecture document, so future callers see the constraint
# at the operation boundary.
_INVARIANTS = (
    "There is no push, remote mutation, tag creation, force flag or history rewrite anywhere in this slice.",
    "A Git invocation that cannot be completed is a refusal, never a pass — including a timeout.",
    "A refusal names its cause.",
)


def _repository(repository: str | Path) -> str:
    return str(Path(repository))


#: Configuration whose value names a program Git will execute, neutralised for
#: *every* invocation rather than at the call sites somebody remembered.
#:
#: A repository-local setting cannot override an environment-supplied one, so
#: this holds even against a worker that writes whatever it likes into its own
#: config. Empty values are used where Git wants a command, because an empty
#: command is not run; `/dev/null` where Git wants a path to read.
_NEUTRALISED_CONFIG = {
    "core.hooksPath": "/dev/null",
    "core.attributesFile": "/dev/null",
    "core.fsmonitor": "",
    "core.sshCommand": "",
    "core.editor": "",
    "core.pager": "",
    # `diff.external` is deliberately absent. An empty value does not mean "no
    # external diff" — Git tries to run the empty string and every diff dies
    # with "cannot run". The diff family has its own switch for this.
    "sequence.editor": "",
    "uploadpack.packObjectsHook": "",
    # Signing runs a program of the repository's choosing.
    "commit.gpgSign": "false",
    "tag.gpgSign": "false",
    "gpg.program": "",
    "gpg.openpgp.program": "",
    "gpg.x509.program": "",
    "gpg.ssh.program": "",
    # Only the transports this module actually uses.
    "protocol.allow": "never",
    "protocol.file.allow": "always",
}


def _config_environment() -> dict[str, str]:
    """`_NEUTRALISED_CONFIG` in the form Git reads from the environment."""
    environment = {"GIT_CONFIG_COUNT": str(len(_NEUTRALISED_CONFIG))}
    for index, (key, value) in enumerate(sorted(_NEUTRALISED_CONFIG.items())):
        environment[f"GIT_CONFIG_KEY_{index}"] = key
        environment[f"GIT_CONFIG_VALUE_{index}"] = value
    return environment


#: Git reads its most fundamental arguments from the environment. `GIT_DIR`,
#: `GIT_WORK_TREE`, `GIT_OBJECT_DIRECTORY`, `GIT_CONFIG_GLOBAL` and their
#: relatives can point every invocation at a different repository, different
#: objects or a different configuration than the one the caller named.
#: Inheriting the whole environment and then setting two variables controlled
#: two variables. Every `GIT_*` value is supplied here and none is inherited.
_GIT_ENVIRONMENT = {
    "GIT_NO_REPLACE_OBJECTS": "1",
    # No ambient user or machine configuration is read. Git treats a missing
    # file as empty.
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    # No invocation of this module's Git may stop to ask a human for
    # credentials. This module is not interactive, so a prompt is a hang.
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ATTR_NOSYSTEM": "1",
    **_config_environment(),
}


def _environment(overlay: dict[str, str] | None) -> dict[str, str]:
    inherited = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    return {**inherited, **_GIT_ENVIRONMENT, **(overlay or {})}


def _run(
    repository: str | Path,
    *arguments: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    text: bool = True,
    input_value: str | bytes | None = None,
    env_overlay: dict[str, str] | None = None,
):
    """Run Git with a deadline, converting every operational failure to refusal."""
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise GitRefusal("git timeout must be a positive number", timeout=timeout)
    if isinstance(timeout, float) and not math.isfinite(timeout):
        # An infinite or NaN deadline is not a deadline. Without this it reaches
        # subprocess and escapes as an OverflowError, which is neither a named
        # refusal nor recognisable as one.
        raise GitRefusal("git timeout must be a finite number of seconds", timeout=repr(timeout))
    command = ("git", *arguments)
    environment = _environment(env_overlay)
    try:
        result = subprocess.run(
            command, cwd=_repository(repository), capture_output=True, check=False,
            timeout=timeout, text=text, input=input_value, env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitRefusal(
            "git invocation timed out", command=" ".join(command), timeout=timeout,
            stderr=_decode(exc.stderr),
        ) from exc
    except OSError as exc:
        raise GitRefusal("git invocation could not be started", command=" ".join(command), error=str(exc)) from exc
    if result.returncode != 0:
        # Some Git commands report their finding on stdout and signal it with a
        # non-zero exit — `diff --check` is the one that matters here. A refusal
        # that carried only stderr threw that finding away, leaving the caller
        # knowing something was wrong and not what.
        raise GitRefusal(
            "git invocation failed", command=" ".join(command), returncode=result.returncode,
            stderr=_decode(result.stderr), stdout=_decode(result.stdout)[:4000],
        )
    return result.stdout


def _decode(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "surrogateescape")
    return value or ""


def _line(
    repository: str | Path, *arguments: str, timeout: float = DEFAULT_TIMEOUT_SECONDS,
    env_overlay: dict[str, str] | None = None,
) -> str:
    return str(
        _run(repository, *arguments, timeout=timeout, env_overlay=env_overlay)
    ).rstrip("\n")


@dataclass(frozen=True)
class ProbeAnswer:
    """What Git said, and whether it said anything at all.

    Three states, because there are three:

    *   Git ran and answered — `answered`, `ok`, and the output;
    *   Git ran and said no — `answered`, not `ok`; an ordinary negative;
    *   **Git could not be asked** — not `answered`. A timeout, a missing
        binary, an unreadable directory. This is not a negative and must never
        be read as one.

    Deliberately not a tuple: a caller written against the old signature fails
    loudly rather than unpacking an unknown into a negative.
    """

    answered: bool
    ok: bool
    value: str = ""
    cause: str = ""
    #: The exit status, when Git ran. `None` when it did not.
    status: int | None = None
    #: Whether that status is one this *command* documents as a meaningful
    #: negative — `show-ref` exiting 1 for "no such ref", `config --get`
    #: exiting 1 for "not set". Any other non-zero exit is a failure, and the
    #: distinction is per command: there is no status that means "no" in
    #: general, which is why the caller declares it.
    negative: bool = False

    @property
    def unknown(self) -> bool:
        return not self.answered

    @property
    def failed(self) -> bool:
        """Git ran and could not answer the question that was asked."""
        return self.answered and not self.ok and not self.negative

    def require(self, question: str) -> str:
        """The output, or a refusal when Git did not answer the question.

        A declared negative is still an answer and is still returned: the
        point is not that non-zero is fatal, it is that only the statuses a
        command documents mean "no".
        """
        if self.unknown:
            raise GitRefusal(
                f"git could not be asked {question}, so there is no answer to act on",
                git_refusal=self.cause,
            )
        if self.failed:
            raise GitRefusal(
                f"git was asked {question} and could not answer, so there is no answer "
                "to act on",
                git_refusal=self.cause, returncode=self.status,
            )
        return self.value


def probe(
    cwd: str | Path, *arguments: str, timeout: float = DEFAULT_TIMEOUT_SECONDS,
    negative_statuses: tuple[int, ...] = (),
) -> ProbeAnswer:
    """Ask Git a read-only question, distinguishing "no" from "cannot ask".

    A non-zero exit means Git looked; a timeout or a missing binary means
    nobody looked, and the caller has to be able to tell the difference.
    """
    try:
        return ProbeAnswer(True, True, _line(cwd, *arguments, timeout=timeout))
    except GitRefusal as refusal:
        detail = getattr(refusal, "detail", {}) or {}
        if "returncode" in detail:
            # Git ran and reported. Whether that is a *negative* depends on the
            # command: `show-ref` exits 1 for "no such ref" and 128 for "the
            # packed-refs file is unreadable", and treating both as "no" is how
            # a corrupt repository reported an absence. Only the statuses the
            # caller declares are answers; every other one is a failure.
            status = int(detail["returncode"])
            return ProbeAnswer(
                True, False, "", str(refusal.cause), status,
                status in negative_statuses,
            )
        # Timed out, could not start, or the directory could not be entered.
        return ProbeAnswer(False, False, "", str(refusal.cause))


def commit_message(repository: str | Path, sha: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Return the commit object's message bytes without porcelain-added LF."""
    raw = _run(repository, "cat-file", "commit", sha, timeout=timeout, text=False)
    assert isinstance(raw, bytes)  # subprocess typing differs between Python versions
    _headers, separator, message = raw.partition(b"\n\n")
    if not separator:
        raise GitRefusal("git commit object has no header/message separator", sha=sha)
    return message.decode("utf-8", "surrogateescape")


def commit_metadata(repository: str | Path, sha: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, str]:
    raw = _run(repository, "cat-file", "commit", sha, timeout=timeout, text=False)
    assert isinstance(raw, bytes)
    headers, separator, _message = raw.partition(b"\n\n")
    if not separator:
        raise GitRefusal("git commit object has no header/message separator", sha=sha)
    found: dict[str, str] = {}
    for line in headers.splitlines():
        if line.startswith(b"author ") or line.startswith(b"committer "):
            role, value = line.split(b" ", 1)
            # Git's identity syntax ends in " <email> timestamp timezone".
            try:
                name, tail = value.rsplit(b" <", 1)
                email, date = tail.split(b"> ", 1)
            except ValueError as exc:
                raise GitRefusal("git commit identity header is malformed", sha=sha, header=_decode(line)) from exc
            prefix = role.decode("ascii")
            found[f"{prefix}_name"] = name.decode("utf-8", "surrogateescape")
            found[f"{prefix}_email"] = email.decode("utf-8", "surrogateescape")
            found[f"{prefix}_date"] = date.decode("ascii", "surrogateescape")
    expected = {"author_name", "author_email", "author_date", "committer_name", "committer_email", "committer_date"}
    if set(found) != expected:
        raise GitRefusal("git commit object lacks complete identity metadata", sha=sha)
    return found


def whitespace_damage(repository: str | Path, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    """The lines `git diff --check` objects to, or empty when there are none.

    Both the work tree and the index are checked. Staged damage is the case
    that matters most, because it is the damage about to become a commit.
    """
    findings: list[str] = []
    for arguments in (("diff", "--no-ext-diff", "--check"),
                      ("diff", "--no-ext-diff", "--cached", "--check")):
        try:
            _run(repository, *arguments, timeout=timeout)
        except GitRefusal as exc:
            # `git diff --check` reports what it found on stdout and exits
            # non-zero, so a refusal carrying output is an *answer*. A refusal
            # carrying none is not: Git never ran, and returning "" for that
            # meant "no whitespace damage" — an unread repository reporting
            # clean.
            if "returncode" not in (exc.detail or {}):
                raise GitRefusal(
                    "git could not be asked about whitespace damage, so there is no "
                    "answer to act on",
                    repository=str(repository), git_refusal=str(exc.cause),
                ) from exc
            reported = str(exc.detail.get("stdout") or "").strip()
            if not reported:
                # A non-zero exit carrying *nothing* is not a whitespace
                # finding, and appending the empty string made it one — which
                # then joined to `""` and read as "no damage".
                raise GitRefusal(
                    "git exited non-zero for the whitespace check without reporting "
                    "anything, so there is no answer to act on",
                    repository=str(repository), returncode=exc.detail.get("returncode"),
                    stderr=str(exc.detail.get("stderr") or "")[:400],
                ) from exc
            findings.append(reported)
    return "\n".join(item for item in findings if item)


def objects_in_outgoing_range(
    repository: str | Path,
    ref: str,
    baseline: str | None,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[tuple[str, str]]:
    """Every object that would be sent, as ``(sha, path)`` pairs.

    ``baseline`` of ``None`` means the whole history: a first push sends
    everything, and there is no earlier state to diff against. Git prints a
    path only for blobs and trees, so the second element is empty for commits.
    """
    arguments = ["rev-list", "--objects", ref]
    if baseline is not None:
        arguments += ["--not", baseline]
    output = _run(repository, *arguments, timeout=timeout)
    found: list[tuple[str, str]] = []
    for line in str(output).splitlines():
        if not line:
            continue
        sha, _, path = line.partition(" ")
        found.append((sha, path))
    return found


def paths_in_outgoing_range(
    repository: str | Path,
    ref: str,
    baseline: str | None,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[str]:
    """Every path the range introduces or changes, taken from the trees themselves.

    Not from `rev-list --objects`. That prints a path only beside an object it
    *lists*, and it does not list a blob already reachable from the baseline —
    so moving a file into a directory with a private name, without touching a
    byte of it, produced an object listing in which the new directory name
    never appeared at all. The path is carried by the tree, so the tree is
    what is read.
    """
    if baseline is None:
        output = _run(repository, "ls-tree", "-r", "--name-only", ref, timeout=timeout)
    else:
        output = _run(
            repository, "diff-tree", "-r", "--name-only", "--no-commit-id",
            "--diff-filter=ACMRT", baseline, ref, timeout=timeout,
        )
    return [line for line in str(output).splitlines() if line]


def object_type(repository: str | Path, sha: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    return _line(repository, "cat-file", "-t", sha, timeout=timeout)


def object_size(repository: str | Path, sha: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> int:
    return int(_line(repository, "cat-file", "-s", sha, timeout=timeout))


def object_bytes(repository: str | Path, sha: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> bytes:
    raw = _run(repository, "cat-file", object_type(repository, sha, timeout=timeout), sha, timeout=timeout, text=False)
    assert isinstance(raw, bytes)
    return raw


def tag_object(repository: str | Path, sha: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, str]:
    """The tagger identity and message of an annotated tag.

    A tag object carries its own message and its own identity, neither of
    which appears in any commit. A gate that reads commits alone never sees
    them.
    """
    raw = _run(repository, "cat-file", "tag", sha, timeout=timeout, text=False)
    assert isinstance(raw, bytes)
    headers, separator, message = raw.partition(b"\n\n")
    if not separator:
        raise GitRefusal("git tag object has no header/message separator", sha=sha)
    found = {"message": message.decode("utf-8", "surrogateescape"), "tagger": "", "tag": ""}
    for line in headers.splitlines():
        if line.startswith(b"tagger "):
            found["tagger"] = line.removeprefix(b"tagger ").decode("utf-8", "surrogateescape")
        elif line.startswith(b"tag "):
            found["tag"] = line.removeprefix(b"tag ").decode("utf-8", "surrogateescape")
    return found


def _cli(argv: list[str]) -> int:
    """A thin command-line front end over the read-only operations above.

    Usage: ``gitread.py REPO COMMAND [ARGS...]``, where COMMAND is one of
    ``commit-message SHA``, ``commit-metadata SHA``, ``whitespace-damage``,
    ``object-type SHA``, ``object-size SHA``, ``object-bytes SHA``,
    ``tag-object SHA``, ``objects-in-range REF [BASELINE]``,
    ``paths-in-range REF [BASELINE]``.
    """
    import sys as _sys

    if len(argv) < 2:
        print("usage: gitread.py REPO COMMAND [ARGS...]", file=_sys.stderr)
        return 64
    repository, command, *rest = argv
    try:
        if command == "commit-message" and len(rest) == 1:
            print(commit_message(repository, rest[0]), end="")
        elif command == "commit-metadata" and len(rest) == 1:
            for key, value in sorted(commit_metadata(repository, rest[0]).items()):
                print(f"{key}={value}")
        elif command == "whitespace-damage" and not rest:
            damage = whitespace_damage(repository)
            print(damage if damage else "clean")
        elif command == "object-type" and len(rest) == 1:
            print(object_type(repository, rest[0]))
        elif command == "object-size" and len(rest) == 1:
            print(object_size(repository, rest[0]))
        elif command == "object-bytes" and len(rest) == 1:
            _sys.stdout.buffer.write(object_bytes(repository, rest[0]))
        elif command == "tag-object" and len(rest) == 1:
            for key, value in sorted(tag_object(repository, rest[0]).items()):
                print(f"{key}={value}")
        elif command == "objects-in-range" and len(rest) in (1, 2):
            ref = rest[0]
            baseline = rest[1] if len(rest) == 2 else None
            for sha, path in objects_in_outgoing_range(repository, ref, baseline):
                print(f"{sha} {path}")
        elif command == "paths-in-range" and len(rest) in (1, 2):
            ref = rest[0]
            baseline = rest[1] if len(rest) == 2 else None
            for path in paths_in_outgoing_range(repository, ref, baseline):
                print(path)
        else:
            print(f"unknown command or wrong argument count: {command}", file=_sys.stderr)
            return 64
    except GitRefusal as exc:
        print(exc.render(), file=_sys.stderr)
        return exc.exit_status
    return 0


if __name__ == "__main__":
    import sys as _sys

    raise SystemExit(_cli(_sys.argv[1:]))
