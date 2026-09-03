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
import threading
from dataclasses import dataclass
from pathlib import Path

import instrument
from errors import GitRefusal, IntegrityError
from instrument import BlastRadius

__all__ = [
    "READ_ONLY_VERBS",
    "BUNDLE_SUBCOMMANDS",
    "TRANSPORT_VERBS",
    "DEFAULT_TIMEOUT_SECONDS",
    "ProbeAnswer",
    "probe",
    "nul_paths",
    "commit_message",
    "commit_metadata",
    "whitespace_damage",
    "objects_in_outgoing_range",
    "paths_in_outgoing_range",
    "staged_entries",
    "refs",
    "config_with_origin",
    "is_ancestor",
    "reachable_objects",
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
    "core.alternateRefsCommand": "",
    "credential.helper": "",
    # Runs a program to obtain a password. Neutralised for the same reason as
    # every other key in this table.
    "core.askPass": "",
    # A nested Git process is a second process, and the parent's command line
    # does not reach it. `diff --submodule=diff` ran the SUBMODULE's own
    # `diff.external` straight through the hardening that protects the parent —
    # found by a blind reader after the first hardening landed. The option is
    # refused and recursion is turned off in config, because two answers to
    # "will this recurse" are better than one when the cost of the wrong answer
    # is running somebody else's program.
    "submodule.recurse": "false",
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


#: Every Git command this module may run, and nothing else.
#:
#: `DECISIONS.md` D2 extracted this module precisely to leave the write verbs
#: behind — *"the discarded remainder is mostly Git write verbs, which a
#: report-only toolbelt must not carry at all"* — and then `probe` took a verb
#: as a parameter and put every one of them back. A cross-vendor auditor
#: created `refs/heads/illicit` through this module's public read API.
#:
#: An allowlist rather than a denylist: a denylist has to anticipate every verb
#: Git will ever add, and the failure mode of missing one is a write. Adding a
#: verb here is a deliberate act with a reviewer, which is what D2 asked for.
READ_ONLY_VERBS = frozenset({
    "bundle",        # list-heads and verify only; both are reads. See BUNDLE_SUBCOMMANDS.
    "cat-file",
    "check-ignore",
    "config",        # gated further by ARGUMENT SHAPE below: `git config k v` WRITES
    "diff",
    "diff-index",
    "diff-tree",
    "for-each-ref",
    "log",
    "ls-files",
    "ls-remote",
    "ls-tree",
    "merge-base",
    "rev-list",
    "rev-parse",
    "show",
    "show-ref",
    "status",
    "verify-pack",
})

#: `git bundle` has a write subcommand (`create`) and two read ones. The verb
#: alone is therefore not enough to decide, so the subcommand is checked too.
BUNDLE_SUBCOMMANDS = frozenset({"list-heads", "verify", "unbundle-dry-run"})

#: **The verb is not the unit of read-onlyness, and believing it was is how the
#: first version of this allowlist still wrote.** `git config audit.k v` sets a
#: key; `git config --unset user.name` removes one. Both were admitted, because
#: `config` sat on the list under a comment asserting that "a write needs a
#: value argument this module never passes" — while `probe(cwd, *arguments)` is
#: a public varargs API and the caller passes the arguments, not the module. An
#: auditor added `[audit] injected = yes` to a repository through the read-only
#: layer and removed `user.name` from it.
#:
#: So a verb whose read-onlyness depends on its arguments declares the forms it
#: may take, and everything else about it is refused.
READ_ONLY_ARGUMENT_FORMS = {
    "config": ("--get", "--get-all", "--get-regexp", "--list", "-l"),
}

#: Options that make an otherwise-read-only command write to the filesystem.
#: `git diff --output=FILE` creates FILE. Matched as a prefix so the `=` form
#: and the separated form are both caught.
WRITING_OPTIONS = ("--output", "-o=", "--out=")

#: Verbs that run a program **the repository itself names** unless told not to.
#:
#: A blind cross-vendor auditor put `diff.external = writer.sh` in a scratch
#: repository's own config and called `probe(repo, "diff", "--ext-diff", "HEAD")`
#: through the read-only API. The script ran. **And it ran without the flag
#: too**, because the config alone is enough — so the reachable surface was
#: every diff this module performs against any repository whose config an
#: attacker can set, which for a checker pointed at other people's repositories
#: is the whole point of the checker.
#:
#: The neutralised-config table says of `diff.external`: *"deliberately absent.
#: An empty value does not mean no external diff — Git tries to run the empty
#: string and every diff dies with cannot run. The diff family has its own
#: switch for this."* That reasoning is correct and the switch was never passed.
#: A comment naming the right answer is not the right answer.
#:
#: `--no-ext-diff` is used rather than a config key because it also disables the
#: per-driver `diff.<name>.command` that `.gitattributes` selects, which no
#: enumerable set of config keys can reach. `--no-textconv` closes the same
#: shape for `diff.<name>.textconv`.
EXTERNAL_PROGRAM_VERBS = frozenset({"diff", "diff-index", "diff-tree", "log", "show"})
_NO_EXTERNAL_PROGRAMS = ("--no-ext-diff", "--no-textconv")
#: The options through which a caller undoes the line above. Refused, because an
#: argument that re-enables repository-controlled execution is a write verb
#: wearing a read's name.
CODE_ENABLING_OPTIONS = ("--ext-diff", "--textconv", "--filters",
                         "--submodule=diff", "--recurse-submodules")

#: Verbs that may cross a network boundary, and the only ones for which
#: `allow_transports` means anything. `archive --remote` is a second network
#: read and was reachable through the generic API with `ssh` enabled — found by
#: a cross-vendor auditor. The scoped exception exists for the publication
#: postcondition, and it is scoped to the verb that performs it.
TRANSPORT_VERBS = frozenset({"ls-remote"})

#: Transports a caller may ask for, one operation at a time. Named rather than
#: free-form: `protocol.<anything>.allow` would let a caller re-enable a
#: transport nobody reviewed by spelling it, which is the widening this exists
#: to avoid.
#: `git` IS DELIBERATELY ABSENT, and this is a security repair rather than a
#: tidy-up.
#:
#: `core.gitProxy` names a program Git runs to open a `git://` connection, and a
#: blind reader set it in a scratch repository's own config and had it executed
#: through `ls-remote` with the transport enabled — the fourth route in this
#: release by which a repository being READ chose what ran, and the only one
#: that came through the single exception that exists to let one operation cross
#: a boundary.
#:
#: **It cannot be neutralised from the environment.** `core.gitProxy` is
#: multi-valued: `GIT_CONFIG_KEY_n` appends to the list rather than replacing
#: it, `git config --get-all` shows both entries, and Git uses the repository's.
#: Verified, not assumed — setting it to `none` and to the empty string each
#: left the program running.
#:
#: So the closure is that the protocol is not enablable. `git://` is
#: unauthenticated and unencrypted, nothing in this pack verifies a remote over
#: it, and a caller that names it now gets the same refusal as one naming a
#: protocol that does not exist. Narrowing the exception is the repair; there
#: was no way to keep the protocol and close the hole.
ALLOWABLE_TRANSPORTS = ("ssh", "https", "http", "file")


def _config_environment(allow_transports: tuple[str, ...] = ()) -> dict[str, str]:
    """`_NEUTRALISED_CONFIG` in the form Git reads from the environment.

    `allow_transports` re-enables **named** protocols for one invocation, and
    does so by adding `protocol.<name>.allow` entries beside the standing
    `protocol.allow = never` rather than by relaxing it. Git consults the
    specific key first and falls back to the general one, so every transport
    the caller did not name stays refused — which is the property that makes
    this narrow rather than a hole with a parameter in front of it.

    It exists because a check that must cross a boundary was disabled by the
    hardening that correctly protects every other read: the postcondition after
    a push could not read any real remote, so the one observation of what a
    push actually did was unavailable on every transport but `file`.
    """
    settings = dict(_NEUTRALISED_CONFIG)
    #: Transports that reach the network through an external program, and the
    #: neutralisation that has to be lifted with them.
    #:
    #: **Enabling the transport is not enough**, and finding that out is what
    #: makes this a second defect rather than a detail. `core.sshCommand = ""`
    #: does not mean "no ssh command": Git tries to run the empty string and
    #: dies with `cannot run :`. This module already recorded that exact lesson
    #: two entries above, for `diff.external`, and deliberately left that key
    #: absent for the same reason — and then set the ssh one to empty anyway.
    #: So a caller that enabled `ssh` got past the protocol refusal and into
    #: `unable to fork`, which is the same non-functional postcondition wearing
    #: a different error.
    #:
    #: Removed rather than set: absent, Git falls through to its own default,
    #: which is deterministic here because every ambient `GIT_*` variable is
    #: already stripped and the global and system files are `/dev/null`.
    for transport in allow_transports:
        if transport not in ALLOWABLE_TRANSPORTS:
            raise IntegrityError(
                "that transport is not one this module will enable for an operation",
                transport=transport, allowable=", ".join(ALLOWABLE_TRANSPORTS),
            )
        settings[f"protocol.{transport}.allow"] = "always"
        if transport == "ssh":
            settings.pop("core.sshCommand", None)
    environment = {"GIT_CONFIG_COUNT": str(len(settings))}
    for index, (key, value) in enumerate(sorted(settings.items())):
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
}


def _environment(
    overlay: dict[str, str] | None, allow_transports: tuple[str, ...] = ()
) -> dict[str, str]:
    inherited = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    return {
        **inherited, **_GIT_ENVIRONMENT, **_config_environment(allow_transports), **(overlay or {})
    }


#: Everything this module does outside itself, declared before it does any of
#: it. Every read in the toolbelt is a Git invocation and they all pass through
#: `_run`, so this is the toolbelt's entire launch surface.
#:
#: Written as a control rather than a note because the version that was a note
#: failed four times, the last of them by launching a browser and crossing a
#: host security boundary. `instrument.launch` refuses an executable this does
#: not name, so widening the surface means widening the declaration.
BLAST_RADIUS = BlastRadius(
    reads=("the named repository, through git, read-only",),
    launches=("git",),
    because=(
        "every read this toolbelt performs is a git invocation, and there is no "
        "supported Python binding for the questions it asks"
    ),
)


def _run(
    repository: str | Path,
    *arguments: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    text: bool = True,
    input_value: str | bytes | None = None,
    env_overlay: dict[str, str] | None = None,
    allow_transports: tuple[str, ...] = (),
):
    """Run Git with a deadline, converting every operational failure to refusal."""
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise GitRefusal("git timeout must be a positive number", timeout=timeout)
    if isinstance(timeout, float) and not math.isfinite(timeout):
        # An infinite or NaN deadline is not a deadline. Without this it reaches
        # subprocess and escapes as an OverflowError, which is neither a named
        # refusal nor recognisable as one.
        raise GitRefusal("git timeout must be a finite number of seconds", timeout=repr(timeout))
    verb = arguments[0] if arguments else ""
    # Raised as an IntegrityError rather than a GitRefusal, deliberately.
    # `probe` converts a GitRefusal into an answer-shaped result — that is its
    # whole job — so raising one here would turn "this module will not run a
    # write verb" into an ordinary negative the caller reads past.
    if verb not in READ_ONLY_VERBS:
        raise IntegrityError(
            "this module runs read-only Git commands only, and that verb is not one of them. "
            "It exists because the layer it was extracted from carried write verbs and a "
            "report-only toolbelt must not (DECISIONS.md D2)",
            verb=verb or "(none)",
            allowed=", ".join(sorted(READ_ONLY_VERBS)),
        )
    forms = READ_ONLY_ARGUMENT_FORMS.get(verb)
    if forms is not None and not any(str(a).split("=")[0] in forms for a in arguments[1:]):
        raise IntegrityError(
            f"`git {verb}` is read-only only in certain argument forms, and this is not one of "
            "them. The verb alone does not decide: this command writes when it is given a value",
            given=" ".join(str(a) for a in arguments[1:]) or "(no arguments)",
            read_only_forms=", ".join(forms),
        )
    previous = ""
    for argument in arguments[1:]:
        # NOT named `text`: that is this function's own parameter deciding
        # whether the read is decoded, and shadowing it turned every binary read
        # into a text one. Caught by the suite immediately, which is the only
        # reason it is a footnote rather than a finding.
        option_text = str(argument)
        if any(option_text == option.rstrip("=") or option_text.startswith(option)
               for option in WRITING_OPTIONS):
            raise IntegrityError(
                "this option makes an otherwise read-only command write to the filesystem",
                verb=verb, option=option_text,
            )
        # Both spellings. Git accepts `--submodule=diff` and `--submodule diff`,
        # and the first version of this check knew only the first — named by a
        # blind reader as its next probe before its own provider cut it off.
        # `previous` carries the option this argument might be the value of.
        if (any(option_text == form or option_text.startswith(form + "=")
                for form in CODE_ENABLING_OPTIONS)
                or f"{previous}={option_text}" in CODE_ENABLING_OPTIONS):
            raise IntegrityError(
                "this option lets the repository being read choose a program to run, and a "
                "read-only interface that executes the subject's code is not read-only",
                verb=verb, option=option_text,
            )
        previous = option_text
    if verb == "bundle":
        subcommand = arguments[1] if len(arguments) > 1 else ""
        if subcommand not in BUNDLE_SUBCOMMANDS:
            raise IntegrityError(
                "`git bundle` has a write subcommand and this module may run only its reads",
                subcommand=subcommand or "(none)",
                allowed=", ".join(sorted(BUNDLE_SUBCOMMANDS)),
            )
    if allow_transports and verb not in TRANSPORT_VERBS:
        raise IntegrityError(
            "a transport is enabled for the one operation that must cross a boundary, and this "
            "verb is not it. Enabling a protocol for a verb the exception was not scoped to is "
            "a second network read nobody reviewed",
            verb=verb, transports=", ".join(allow_transports),
            scoped_to=", ".join(sorted(TRANSPORT_VERBS)),
        )
    # Asked ONCE, before anything runs, and asked of the repository rather than
    # of this module's own list of tricks. `config --list` is itself read-only
    # and is invoked through the same guarded path, with the recursion stopped
    # by the verb: a `config` read does not re-enter this check.
    # `config` is exempt as well as re-entrant calls: a configuration READ
    # cannot execute anything, and a caller asking about a broken config is
    # entitled to the refusal that names the real problem rather than to this
    # check's opinion about it. Hijacking that refusal turned "your config does
    # not parse" into a security finding about a repository nobody could read.
    if not _inspecting() and verb != "config":
        executable = program_valued_config(repository, timeout=timeout)
        if executable:
            raise IntegrityError(
                "this repository's own configuration names a program for Git to run, by a key "
                "this module has NO NAMED CLOSURE FOR. Five separate routes to repository-chosen "
                "execution were found in four consecutive audit rounds, each where the previous "
                "repair could not see it, so the check is on the SHAPE of the key rather than on "
                "the routes anybody has thought of — and an unrecognised one refuses rather than "
                "waiting to be found",
                repository=str(repository), keys=", ".join(executable),
            )
    arguments = (
        (arguments[0], *_NO_EXTERNAL_PROGRAMS, *arguments[1:])
        if verb in EXTERNAL_PROGRAM_VERBS else arguments
    )
    if verb in TRANSPORT_VERBS:
        # `remote.<name>.uploadpack` names a program Git runs on the far side —
        # and with a `file://` remote the far side is this machine, so a
        # repository being read chose a program AND it ran with the reader's own
        # permissions. It wrote into the reader. **Fifth execution route in this
        # release**, found by a blind reader inside the one transport exception.
        #
        # No config key closes it: the setting is per-remote and remote names
        # cannot be enumerated in advance. The command-line form OVERRIDES the
        # config, which was verified rather than assumed — with the flag the
        # program does not run, without it it does.
        arguments = (arguments[0], "--upload-pack=git-upload-pack", *arguments[1:])
    command = ("git", *arguments)
    environment = _environment(env_overlay, allow_transports)
    # In text mode, decode with `surrogateescape`. A path is a byte string on
    # POSIX and need not be valid UTF-8; the default strict decode raises
    # `UnicodeDecodeError` from inside subprocess, which is neither a named
    # refusal nor recoverable, so a repository containing one undecodable path
    # takes down every text-mode read of it. Passed conditionally because
    # supplying `errors` at all forces text mode, which would break every
    # binary read.
    decoding = {"errors": "surrogateescape"} if text else {}
    try:
        result = instrument.launch(
            command, radius=BLAST_RADIUS,
            cwd=_repository(repository), capture_output=True, check=False,
            timeout=timeout, text=text, input=input_value, env=environment, **decoding,
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


def nul_paths(raw: bytes) -> list[str]:
    """Paths as Git emitted them under ``-z``.

    **Every** path enumeration in this toolbelt goes through `-z` and this
    function. Git's default, line-based output *C-quotes* any path it cannot
    print literally — non-ASCII, a newline, a quote, a backslash — so
    `plain.md` arrives as itself while `sessioné-private/notes.md` arrives as
    the eleven-character-longer literal `"session\303\251-private/notes.md"`,
    quotes included.

    That is not cosmetic. Reproduced against frozen 2.1.1: a repository
    containing a directory whose name was a **declared private term** scanned
    `clean`, because the leak scanner matched the term against the escaped
    form and the escaped form does not contain the term. The rule was applied,
    to the wrong bytes, and the report said so in no way a reader could see.

    `surrogateescape` rather than a strict decode: a path is a byte string on
    POSIX and need not be valid UTF-8. A path that cannot be decoded must still
    reach a checker — refusing to represent it is how it goes unexamined.
    """
    return [item.decode("utf-8", "surrogateescape") for item in raw.split(b"\x00") if item]


def _decode(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "surrogateescape")
    return value or ""


def _line(
    repository: str | Path, *arguments: str, timeout: float = DEFAULT_TIMEOUT_SECONDS,
    env_overlay: dict[str, str] | None = None,
    allow_transports: tuple[str, ...] = (),
) -> str:
    return str(
        _run(repository, *arguments, timeout=timeout, env_overlay=env_overlay,
             allow_transports=allow_transports)
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
    #: What Git actually printed when it failed. Carried because `cause` alone
    #: says only *that* the invocation failed, and two failures with the same
    #: `cause` can have opposite remedies: a refused transport and a host that
    #: does not resolve both arrive as "git invocation failed", and one is a
    #: configuration this pack controls while the other is the network.
    detail: str = ""

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
    allow_transports: tuple[str, ...] = (),
) -> ProbeAnswer:
    """Ask Git a read-only question, distinguishing "no" from "cannot ask".

    A non-zero exit means Git looked; a timeout or a missing binary means
    nobody looked, and the caller has to be able to tell the difference.
    """
    try:
        return ProbeAnswer(
            True, True,
            _line(cwd, *arguments, timeout=timeout, allow_transports=allow_transports),
        )
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
                detail=str(detail.get("stderr") or detail.get("stdout") or "").strip(),
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


#: Config key patterns WHOSE VALUE GIT EXECUTES. `fnmatch` globs, matched
#: case-insensitively against a repository's own local configuration.
#:
#: **This list is not complete and cannot be.** That is the point of it: five
#: separate routes by which a repository being read chose a program to run were
#: found in four consecutive audit rounds — `diff.external`, an attribute-
#: selected diff driver, a `.gitattributes` filter chain, `core.gitProxy`, and
#: `remote.<name>.uploadpack`. Each was closed where the previous repair could
#: not see it, and each time the next reader found another. Closing routes one
#: at a time was losing.
#:
#: So the defence stops being an enumeration of routes and becomes an
#: enumeration of SHAPES. A repository that sets a program-valued key is refused
#: before anything runs, whether or not this module knows how that key would
#: have been reached — and the sixth route is refused by a check written before
#: anybody found it.
PROGRAM_VALUED_CONFIG = (
    "core.gitproxy", "core.sshcommand", "core.askpass", "core.editor", "core.pager",
    "core.fsmonitor", "core.hookspath", "core.alternaterefscommand", "core.externaldiff",
    "credential.helper", "credential.*.helper",
    "diff.external", "diff.*.command", "diff.*.textconv",
    "filter.*.clean", "filter.*.smudge", "filter.*.process",
    "merge.*.driver", "merge.*.cmd",
    "remote.*.uploadpack", "remote.*.receivepack", "remote.*.vcs", "remote.*.proxy",
    "protocol.*.command", "uploadpack.packobjectshook",
    "sequence.editor", "gpg.program", "gpg.*.program",
    "trailer.*.command", "interactive.difffilter", "pager.*", "alias.*",
    "browser.*.cmd", "web.browser", "guitool.*.cmd", "difftool.*.cmd", "mergetool.*.cmd",
    "sendemail.smtpserver", "ssh.variant", "include.path", "includeif.*.path",
    "submodule.*.update", "fsmonitor.*",
)

#: The subset above that a NAMED mechanism in this module already closes, and
#: the mechanism. A repository is free to set these: the closure is what
#: protects, not the absence of the key, and refusing to read a repository whose
#: developer set a pager would be hardening in name and obstruction in fact.
#:
#: **Everything else matching a shape above is refused**, and that asymmetry is
#: the whole design. A key with a closure has been thought about; a key without
#: one has not, and the sixth execution route will arrive as a key nobody here
#: has heard of.
CLOSED_PROGRAM_KEYS = {
    "core.editor": "neutralised in the standing config",
    "core.pager": "neutralised in the standing config, and output is captured",
    "core.askpass": "neutralised in the standing config",
    "core.sshcommand": "neutralised, and removed only when ssh is deliberately enabled",
    "core.fsmonitor": "neutralised in the standing config",
    "core.hookspath": "neutralised to /dev/null",
    "core.alternaterefscommand": "neutralised in the standing config",
    "credential.helper": "neutralised in the standing config",
    "sequence.editor": "neutralised in the standing config",
    "gpg.program": "neutralised in the standing config",
    "uploadpack.packobjectshook": "neutralised in the standing config",
    "core.gitproxy": "unreachable: the git:// protocol is not enablable",
    "diff.external": "disabled by --no-ext-diff on every verb that accepts it",
    "remote.*.uploadpack": "overridden by --upload-pack on every transport read",
    "diff.*.command": "an attribute-selected driver, disabled by --no-ext-diff",
    "diff.*.textconv": "disabled by --no-textconv, and --textconv is refused as an argument",
    "filter.*.clean": "reachable only through --filters, which is refused as an argument",
    "filter.*.smudge": "reachable only through --filters, which is refused as an argument",
    "filter.*.process": "reachable only through --filters, which is refused as an argument",
}


#: Re-entrancy guard for the config inspection below. **Thread-local, and a
#: module-level flag was the first version.**
#:
#: A blind reader held one thread inside the inspection and issued a second
#: public read from another: the flag was set, so the second read skipped its
#: inspection entirely and ran against a repository nobody had checked. A guard
#: against a function calling ITSELF became a guard against anyone calling it,
#: which is a different and much larger claim.

#:
#: The inspection runs Git, and every Git run is inspected — so the first
#: version guarded only on the verb `config`, and its own fallback probe
#: (`rev-parse --git-dir`, reached whenever the config could not be read) was a
#: DIFFERENT verb and re-entered. Two test modules that take ten seconds ran for
#: over six minutes without finishing. A guard on the verb was a guard on one
#: of the paths the function takes.
_INSPECTION = threading.local()


def _inspecting() -> bool:
    return getattr(_INSPECTION, "active", False)


def program_valued_config(
    repository: str | Path, *, timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> list[str]:
    """Local config keys this repository sets whose value Git would execute.

    Read from the repository's OWN configuration only — the environment's
    hardening is this module's and is not what is being inspected.
    """
    import fnmatch

    if _inspecting():
        return []
    _INSPECTION.active = True
    try:
        return _program_valued_config(repository, fnmatch, timeout)
    finally:
        _INSPECTION.active = False


def _program_valued_config(repository, fnmatch, timeout) -> list[str]:
    try:
        listing = _run(repository, "config", "--local", "--list", "--name-only", "-z",
                       timeout=timeout)
    except GitRefusal as refusal:
        # A DEADLINE THE CALLER SET IS THE CALLER'S REFUSAL. This inspection runs
        # inside the caller's timeout, so an impatient caller expired here first
        # and got a configuration finding where it had asked for, and was owed,
        # a timeout. The message is this module's own literal, so matching it is
        # an internal contract rather than a foreign string.
        if "timed out" in str(refusal):
            raise
        # Two remaining failures wear the same exception, and only one of them
        # is this check's business.
        #
        # *The path is not a repository at all* belongs to the command the
        # caller actually asked for: it produces a `GitRefusal` naming the real
        # problem, and hijacking it here reported a missing directory as a
        # configuration finding.
        #
        # Asked of the FILESYSTEM and not of Git, because the discriminator has
        # to work in exactly the case where Git is what is failing. A repository
        # whose `include.path` points at a shell breaks every config read, and a
        # git-based discriminator broke with it and returned "not a repository"
        # — which is the fail-open this branch exists to prevent, restored by
        # the fix for it.
        here = Path(repository)
        looks_like_one = (here / ".git").exists() or (
            (here / "HEAD").is_file() and (here / "objects").is_dir())
        if not looks_like_one:
            return []
        # *The repository is fine and its configuration is not* is this check's
        # business, and it FAILS CLOSED — the first version did not, which is
        # how it was caught. `git config include.path /bin/sh` makes every
        # subsequent config read fail, so a repository could disable the check
        # that inspects it by breaking itself, and seven unrecognised
        # program-valued keys came back as none. A check that cannot read its
        # subject has not cleared it.
        raise IntegrityError(
            "this repository's own configuration could not be read, so whether it names a "
            "program for Git to run cannot be established. An unreadable configuration is not "
            "an empty one",
            repository=str(repository), refusal=str(refusal)[:160],
        ) from refusal
    found = []
    for key in nul_paths(listing.encode() if isinstance(listing, str) else listing):
        lowered = key.strip().lower()
        if not lowered:
            continue
        if not any(fnmatch.fnmatchcase(lowered, p) for p in PROGRAM_VALUED_CONFIG):
            continue
        if any(fnmatch.fnmatchcase(lowered, p) for p in CLOSED_PROGRAM_KEYS):
            continue
        found.append(lowered)
    return sorted(set(found))


def commit_messages(
    repository: str | Path,
    ref: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[tuple[str, str]]:
    """``(sha, message)`` for every commit reachable from ``ref``.

    A commit message is published with the repository and is not reachable
    through the object walk this module's blob scan performs, because a commit
    is not a blob. A private term written into one therefore scanned clean.

    **Read from the raw commit objects, by byte count.** The first version asked
    Git to format them — ``rev-list --format=%B%x00`` — and split the result on
    NUL, and an independent reader took it apart three ways in one paragraph:

    *   Git emits a newline after each formatted record, so **every message
        except the tip came back with a leading newline**. A pattern anchored to
        the start of a message stopped matching, and the scan reported clean.
    *   A message containing a NUL byte was **truncated at it**, which is
        precisely the byte the delimiter was.
    *   An empty message came back as ``"\n"`` rather than ``""``.

    `cat-file --batch` states each object's size and then emits exactly that
    many bytes, so the boundary is counted rather than searched for. Nothing in
    a message can be mistaken for the end of it.
    """
    revisions = _run(repository, "rev-list", ref, timeout=timeout).split()
    if not revisions:
        return []
    raw = _run(repository, "cat-file", "--batch", timeout=timeout, text=False,
               input_value=("\n".join(revisions) + "\n").encode())
    assert isinstance(raw, bytes)

    found: list[tuple[str, str]] = []
    at = 0
    while at < len(raw):
        newline = raw.find(b"\n", at)
        if newline < 0:
            break
        header = raw[at:newline].decode("utf-8", "surrogateescape").split()
        at = newline + 1
        if len(header) == 2 and header[1] == "missing":
            # `<sha> missing` — Git's documented answer for an object it cannot
            # produce. Dropping it silently let a caller certify a COMPLETE
            # history scan over commits nobody read, which is the whole claim.
            # An object `rev-list` named and `cat-file` cannot produce is a hole,
            # and a hole refuses.
            raise IntegrityError(
                "this repository named a commit its object store cannot produce, so the history "
                "cannot be read completely. A scan that skipped it would report clean about "
                "something nobody read",
                repository=str(repository), object=header[0],
            )
        if len(header) != 3 or header[1] != "commit":
            continue
        size = int(header[2])
        body = raw[at:at + size]
        at += size + 1  # the newline Git writes after the object
        # A commit object is headers, one blank line, then the message. Split
        # once on the FIRST blank line: a message may contain blank lines of its
        # own, and the header block may not.
        separator, _, message = body.partition(b"\n\n")
        if separator == body:
            # No blank line: this is not a commit object's shape, and calling its
            # message empty is a guess. An independent reader wrote one with
            # `hash-object --literally`.
            raise IntegrityError(
                "an object typed `commit` has a header block, a blank line and a message; this "
                "one has no blank line, so its message cannot be read rather than being empty",
                repository=str(repository), object=header[0],
            )
        found.append((header[0], message.decode("utf-8", "surrogateescape")))
    return found


def commit_objects(
    repository: str | Path,
    ref: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[tuple[str, str]]:
    """``(sha, the whole commit object)`` for every commit reachable from ``ref``.

    The message is only part of what a commit publishes. **The header carries
    the author and committer identities** — a name and an email address, written
    by whoever made the commit — and a scan that split the object and read only
    the message reported clean about a repository whose author name was the
    private term it was looking for.

    Same byte-counted read as `commit_messages`; this one simply does not
    discard the half above the blank line.
    """
    revisions = _run(repository, "rev-list", ref, timeout=timeout).split()
    if not revisions:
        return []
    raw = _run(repository, "cat-file", "--batch", timeout=timeout, text=False,
               input_value=("\n".join(revisions) + "\n").encode())
    assert isinstance(raw, bytes)
    found: list[tuple[str, str]] = []
    at = 0
    while at < len(raw):
        newline = raw.find(b"\n", at)
        if newline < 0:
            break
        header = raw[at:newline].decode("utf-8", "surrogateescape").split()
        at = newline + 1
        if len(header) == 2 and header[1] == "missing":
            raise IntegrityError(
                "this repository named a commit its object store cannot produce, so the history "
                "cannot be read completely",
                repository=str(repository), object=header[0],
            )
        if len(header) != 3 or header[1] != "commit":
            continue
        size = int(header[2])
        found.append((header[0], raw[at:at + size].decode("utf-8", "surrogateescape")))
        at += size + 1
    return found


def annotated_tags(
    repository: str | Path,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[tuple[str, str]]:
    """``(sha, type)`` for every annotated tag object this repository holds.

    A lightweight tag is a ref pointing straight at a commit and carries no
    message; an annotated tag is an OBJECT with a body somebody wrote, and that
    body is published with the repository. It is not reachable through the
    blob walk, which is why a tag message naming a private term scanned clean.
    """
    output = _run(repository, "for-each-ref", "--format=%(objecttype) %(objectname)",
                  "refs/tags/", timeout=timeout)
    found: list[tuple[str, str]] = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "tag":
            found.append((parts[1], parts[0]))
    return found


def every_name_in_history(
    repository: str | Path,
    ref: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[tuple[str, str]]:
    """Every ``(sha, path)`` a tree in this history ever gave an object.

    Separate from `objects_in_outgoing_range` because **`rev-list --objects`
    prints one name per object**. Two paths holding identical bytes are one
    blob, and git names it once — so a repository containing `notes.txt` and a
    second copy under a filename carrying a private word enumerated only the
    first, and the second name was never examined at all. Found by a blind
    auditor.

    Read from the trees, which is where names actually live: `ls-tree -r` over
    every commit, deduplicated by the pair rather than by the object. Costlier
    than the object walk and correct, and only names are collected here — the
    content scan still reads each blob once.
    """
    try:
        commits = _run(repository, "rev-list", ref, timeout=timeout).split()
    except GitRefusal:
        # A repository with no commits has no names, and that is an answer
        # rather than a failure: `rev-list HEAD` exits non-zero on one, and the
        # refusal reached callers who had asked a question with a correct empty
        # answer.
        #
        # THE QUESTION IS ABOUT THE REPOSITORY, NOT ABOUT THE REF. The first
        # version asked whether `ref` resolved — which is false both for an
        # empty repository and for a ref that simply does not exist, so *this
        # branch is not here* became *this history has no names*. A mutation
        # pass caught it: deleting the `raise` changed nothing, because nothing
        # ever reached it.
        empty = _run(repository, "rev-list", "--all", "--count", timeout=timeout).strip()
        if empty == "0":
            return []
        raise
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for commit in commits:
        output = _run(repository, "ls-tree", "-r", "-z", "--full-tree", commit,
                      timeout=timeout, text=False)
        assert isinstance(output, bytes)
        for record in nul_paths(output):
            if not record:
                continue
            # `<mode> SP <type> SP <sha> TAB <path>`
            meta, _, path = record.partition("\t")
            parts = meta.split()
            if len(parts) != 3 or not path:
                continue
            pair = (parts[2], path)
            if pair not in seen:
                seen.add(pair)
                found.append(pair)
    return found


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
    arguments = ["rev-list", "--objects", "-z", ref]
    if baseline is not None:
        arguments += ["--not", baseline]
    output = _run(repository, *arguments, timeout=timeout, text=False)
    assert isinstance(output, bytes)
    # Under `-z`, git emits `<sha>\0` for an object with no path and
    # `<sha>\0path=<path>\0` for one with a path. Line-splitting this was the
    # last enumeration in the toolbelt still doing so, which made `nul_paths`'
    # claim to cover *every* path enumeration untrue — found by an independent
    # audit. A path containing a newline split one object into three records.
    found: list[tuple[str, str]] = []
    pending: str | None = None
    for record in nul_paths(output):
        if record.startswith("path="):
            if pending is not None:
                found.append((pending, record[len("path="):]))
                pending = None
            continue
        if pending is not None:
            found.append((pending, ""))
        pending = record
    if pending is not None:
        found.append((pending, ""))
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
        output = _run(repository, "ls-tree", "-r", "--name-only", "-z", ref, timeout=timeout, text=False)
    else:
        output = _run(
            repository, "diff-tree", "-r", "--name-only", "--no-commit-id",
            "--diff-filter=ACMRT", "-z", baseline, ref, timeout=timeout, text=False,
        )
    assert isinstance(output, bytes)
    return nul_paths(output)


def staged_entries(
    repository: str | Path, *, timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> list[tuple[str, str]]:
    """``(path, blob_sha)`` for everything the index adds or modifies.

    Read from `ls-files --stage` rather than from the working tree: what a
    commit will contain is what the index holds, and the two differ precisely
    when a file was edited after being staged — which is the case where reading
    the wrong one produces a gate that passed on text nobody is committing.

    Deletions carry no blob and are not listed: there is no content to scan.
    """
    changed = _run(
        repository, "diff", "--no-ext-diff", "--cached", "--name-only",
        "--diff-filter=ACMR", "-z", timeout=timeout, text=False,
    )
    assert isinstance(changed, bytes)
    paths = nul_paths(changed)
    if not paths:
        return []

    listing = _run(repository, "ls-files", "--stage", "-z", "--", *paths, timeout=timeout, text=False)
    assert isinstance(listing, bytes)
    entries: list[tuple[str, str]] = []
    for record in listing.split(b"\x00"):
        if not record:
            continue
        metadata, separator, path = record.partition(b"\t")
        if not separator:
            continue
        fields = metadata.split()
        if len(fields) < 3:
            continue
        if fields[2] != b"0":
            # A non-zero stage is an unresolved merge conflict. Scanning one
            # side of it would report on text that is not what gets committed.
            raise GitRefusal(
                "the index holds an unmerged path; resolve the conflict before scanning",
                path=path.decode("utf-8", "surrogateescape"),
            )
        entries.append((path.decode("utf-8", "surrogateescape"), fields[1].decode("ascii")))
    return entries


def refs(repository: str | Path, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> list[dict[str, str]]:
    """Every ref in the repository, with its target and the identity behind it.

    `git log`, `git status`, `git ls-files`, `git diff` and `git show` all read
    the *branch history*. None of them can see `refs/notes/*`, and a repository
    can therefore carry machine-readable AI-contribution attribution, private
    session identifiers and non-human committer identities while every one of
    those commands reports clean. That is not hypothetical: it was found in a
    real repository.

    So publication safety needs the *namespace*, which is what this returns.
    """
    output = _run(
        repository, "for-each-ref",
        "--format=%(refname)%09%(objectname)%09%(objecttype)%09%(authorname)%09%(authoremail)",
        timeout=timeout,
    )
    found: list[dict[str, str]] = []
    for line in str(output).splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        while len(fields) < 5:
            fields.append("")
        found.append({
            "refname": fields[0], "objectname": fields[1], "objecttype": fields[2],
            "authorname": fields[3], "authoremail": fields[4],
        })
    return found


def config_with_origin(
    repository: str | Path, *, timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> list[dict[str, str]]:
    """Every config setting **with the file it came from**.

    Values alone cannot answer the question that matters — whether a setting is
    the user's global preference or something written into this repository's
    own `.git/config` by a process that was not the user. A forensic pass
    depended on exactly that distinction, and a reader that returns values only
    forces the reader to guess.
    """
    # `config --list` exits 1 when there is nothing to list, which is an
    # ordinary negative; anything else means nobody looked.
    answer = probe(
        repository, "config", "--list", "--show-origin", "--null",
        timeout=timeout, negative_statuses=(1,),
    )
    if not answer.answered:
        raise GitRefusal("could not read git configuration", git_refusal=answer.cause)
    # A repository whose `.git/config` cannot be parsed exits 128, and returning
    # `[]` for it reports "this repository has no settings" — including no
    # `notes.*` keys, which is the exact surface D7 exists to watch. Nothing was
    # read, so nothing may be concluded.
    if answer.failed:
        raise GitRefusal(
            "git configuration could not be read, so it must not be reported as empty",
            git_refusal=answer.cause, returncode=answer.status,
        )
    if not answer.ok:
        return []
    # Under `--null`, git emits `<origin>\0<key>\n<value>\0` — the origin is
    # its own NUL-terminated record, and key and value are newline-separated.
    # A value may itself contain newlines, so only the first one splits.
    records = [record for record in answer.value.split("\x00") if record]
    entries: list[dict[str, str]] = []
    for index in range(0, len(records) - 1, 2):
        origin = records[index]
        key, _, value = records[index + 1].partition("\n")
        entries.append({"origin": origin, "key": key, "value": value})
    return entries


def is_ancestor(
    repository: str | Path, candidate: str, descendant: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> bool:
    """Whether ``candidate`` is reachable from ``descendant``.

    Asked explicitly rather than inferred from how notes refs normally behave.
    "Normally" is not a safety property.
    """
    # `merge-base --is-ancestor` exits 0 for yes and 1 for no. A 128 means the
    # revision does not resolve, which is not an answer.
    answer = probe(
        repository, "merge-base", "--is-ancestor", candidate, descendant,
        timeout=timeout, negative_statuses=(1,),
    )
    if not answer.answered:
        raise GitRefusal("could not test ancestry", git_refusal=answer.cause)
    # `answered` only says git ran. The comment above declares 1 the sole
    # negative, and 128 — an unresolvable revision, a non-commit object, an
    # unreadable object store — was nevertheless returned as `False`, which
    # reads as "no, not an ancestor". `publication_gate` then printed that
    # guess as the sentence "CARRIES OBJECTS THE PUBLIC REF DOES NOT", and its
    # own guard against exactly this could not fire because the conversion had
    # already happened one layer down. Reproduced with a ref pointing at a
    # blob (DECISIONS.md D15).
    if answer.failed:
        raise GitRefusal(
            "git was asked whether one object is an ancestor of another and could not answer",
            git_refusal=answer.cause, returncode=answer.status,
            candidate=candidate, descendant=descendant,
        )
    return answer.ok


def reachable_objects(
    repository: str | Path, *revisions: str, timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> set[str]:
    """Every object reachable from the given revisions."""
    if not revisions:
        return set()
    output = _run(repository, "rev-list", "--objects", "--no-object-names", *revisions, timeout=timeout)
    return {line.strip() for line in str(output).splitlines() if line.strip()}


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
    from gitread import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
