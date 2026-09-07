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

import instrument
import sterile
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
    "repository_location",
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

#: Options that enable repository-chosen execution ON ONE VERB and mean something
#: harmless elsewhere. `git status -v` prints a patch, which applies the
#: repository's textconv drivers, and `status` accepts no `--no-textconv` to undo
#: it — the driver ran twice under an ordinary `probe(repo, "status", "-v")`.
#: `-v` on `check-ignore` merely names the matching rule, and this pack's own
#: workspace report asks for it, so refusing the spelling everywhere refused a
#: reader that executes nothing. Scoped to the verb it is dangerous on.
VERB_ENABLING_OPTIONS = {"status": ("-v", "--verbose")}

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
#:
#: Transports a caller may deliberately enable for the one operation that must
#: cross a boundary. **NOT a projection.** The names below are a bound on what a
#: CALLER may ask for, and `_run` refuses one that is not here — a caller-capability
#: allowlist, which is a different question from the one this release replaced. The
#: subject's own `protocol.<name>.allow` is not read at all, so nothing a repository
#: writes is consulted here. An independent certification read the design's list of
#: projections as covering this name; it does not, and the design says so now.
ALLOWABLE_TRANSPORTS = ("ssh", "https", "http", "file")


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
        # NO OPTION IS REFUSED FOR ENABLING A DRIVER ANY MORE.
        #
        # `--textconv`, `--ext-diff`, `--filters` and `status -v` were refused
        # because they let the repository choose a program. They cannot: the
        # driver they enable is not defined in the configuration Git reads.
        # Refusing them was a proxy, and the proxy was where B15a lived — the
        # refusal matched `-v` and `--verbose` exactly, while Git also accepts
        # `-vv`, `--verb` and `--verbo`, each of which ran the helper. An option
        # spelling cannot be enumerated, so nothing enumerates one now.
        #
        # `WRITING_OPTIONS` above is untouched: an option that makes a read WRITE
        # is a different guarantee, and sterile execution does not provide it.
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
    # NOTHING IS INSPECTED HERE ANY MORE.
    #
    # Until 2.5.0 this asked the repository which of its settings named a program
    # and refused the ones no closure covered. The read now happens in a git
    # directory this harness built (`tools/sterile.py`), so the repository's
    # configuration is not a configuration source for it — which is a smaller
    # claim than "no dangerous key is set", and one Git itself can be asked to
    # confirm. The lists that decision needed survive as published names and
    # decide nothing.
    #
    # The checks that remain above are about WRITE CAPABILITY — a verb that
    # writes, an option that makes a read write. Sterile execution does not stop
    # `git update-ref`, so those are a different guarantee and stay exactly where
    # they were.
    # A CONFIG READ MUST READ THE SUBJECT'S CONFIGURATION, NOT THE HARNESS'S.
    #
    # Under this boundary `git config --get k` would consult the git directory
    # this module just built, and answer confidently about the wrong repository.
    # That is a silent wrong answer, which is the worst thing a read can produce,
    # so a source-less config read is pointed at the subject's own file.
    #
    # And where the subject also has a `config.worktree`, ONE file cannot answer:
    # the read is refused by name rather than answered from half the sources.
    # `config_with_origin` reads both and is what a caller wanting the whole
    # picture should use.
    if verb == "config" and not any(
        str(argument).split("=")[0] in ("--file", "-f", "--global", "--system", "--blob",
                                        "--local", "--worktree")
        for argument in arguments[1:]
    ):
        sources = _configuration_files_of(repository)
        if len(sources) > 1:
            raise IntegrityError(
                "this repository keeps settings in more than one file, so a single config read "
                "cannot answer about it. Use config_with_origin, which reads every source, or "
                "name a --file",
                repository=str(repository), sources=", ".join(str(one) for one in sources),
            )
        if sources:
            arguments = (arguments[0], "--file", str(sources[0]), *arguments[1:])
    # A REMOTE NAME IS A CONFIGURATION LOOKUP, AND THE CONFIGURATION IS NOT READ.
    #
    # `ls-remote origin` resolves `origin` through `remote.origin.url` in the
    # repository's own configuration — which this boundary deliberately keeps out
    # of Git's hands, so the name stopped resolving and every publication
    # post-condition failed with "'origin' does not appear to be a git
    # repository". The compensation belongs here, at the boundary that caused it,
    # rather than in each caller.
    #
    # The URL is read from the subject's configuration as DATA and passed
    # explicitly. That is strictly more truthful than what Git did before:
    # `url.<base>.insteadOf` rewriting is not applied, so the address contacted
    # is the one written in the file and visible to the caller, not one the
    # repository rewrote on the way out.
    if verb in TRANSPORT_VERBS:
        resolved: list[str] = []
        declared = sterile.config_as_data(_config_file_of(repository))
        for argument in arguments[1:]:
            url = declared.get(f"remote.{argument}.url")
            resolved.append(url if url else str(argument))
        if resolved != [str(one) for one in arguments[1:]]:
            arguments = (arguments[0], *resolved)
    # STANDING, NOT ONLY WHEN A TRANSPORT IS ENABLED. Pinning `protocol.allow`
    # only for invocations that already named a transport left every other read
    # on Git's defaults, which permit ssh, http and git:// — so the posture this
    # module has always had, that a read reaches no network unless a caller
    # deliberately opened one, would have been quietly dropped by the rewrite.
    #
    # Harness policy in the harness's own config file, and no longer contested by
    # anything: the subject's `protocol.<name>.allow` is not read at all, so the
    # key that once let a repository re-enable `ext::` and run its own helper is
    # not in the picture.
    transport_config: dict[str, str] = {"protocol.allow": "never"}
    if allow_transports:
        for transport in allow_transports:
            if transport not in ALLOWABLE_TRANSPORTS:
                raise IntegrityError(
                    "that transport is not one this module will enable for an operation",
                    transport=transport, allowable=", ".join(ALLOWABLE_TRANSPORTS),
                )
            transport_config[f"protocol.{transport}.allow"] = "always"
    # `--no-ext-diff --no-textconv` are not added. They suppressed drivers the
    # repository defined, and the repository no longer defines any that Git can
    # see — verified rather than assumed: an explicit `--textconv` and an explicit
    # `--ext-diff` both execute nothing through this boundary.
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
    # THE ONE BOUNDARY. Every read in this toolbelt reaches Git through here, and
    # every one of them runs in a directory this harness constructed.
    #
    # NOT SCOPED BY VERB. A first draft chose the cheap path from a list of verbs
    # that "do not need a working tree", which is the enumeration this release
    # exists to stop writing — and it bought nothing: where the tree holds no
    # other repository the subject's own tree is used and no copy is made.
    # `sterile.build` decides from the tree, and refuses — rather than answering —
    # when it cannot reproduce the subject.
    read = sterile.build(
        repository, overlay=env_overlay,
        extra_config=transport_config or None, timeout=timeout,
    )
    environment = read.environment
    decoding = {"errors": "surrogateescape"} if text else {}
    try:
        result = instrument.launch(
            command, radius=BLAST_RADIUS,
            cwd=str(read.cwd), capture_output=True, check=False,
            timeout=timeout, text=text, input=input_value, env=environment, **decoding,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitRefusal(
            "git invocation timed out", command=" ".join(command), timeout=timeout,
            stderr=_decode(exc.stderr),
        ) from exc
    except OSError as exc:
        raise GitRefusal("git invocation could not be started", command=" ".join(command), error=str(exc)) from exc
    finally:
        # The construction is scratch state and is discarded however this ends,
        # so that a suite of thousands of reads leaves nothing behind. Phase 11
        # asks for zero residual scratch and this is where that is kept true.
        read.discard()
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
    # CONDITIONAL. The condition is real and is enforced by CONDITIONAL_CLOSURES
    # below; this entry alone is not a closure, and reading it as one is how a
    # repository's own ssh program came to run through this module.
    "core.sshcommand": "neutralised, and removed only when ssh is deliberately enabled",
    "core.fsmonitor": "neutralised in the standing config",
    "core.hookspath": "neutralised to /dev/null",
    "core.alternaterefscommand": "neutralised in the standing config",
    "credential.helper": "neutralised in the standing config",
    "sequence.editor": "neutralised in the standing config",
    "gpg.program": "neutralised in the standing config",
    "uploadpack.packobjectshook": "neutralised in the standing config",
    "core.gitproxy": "unreachable: git:// is refused at command scope and a repository cannot re-enable it, because its own protocol.*.allow keys are pinned there too",
    "diff.external": "disabled by --no-ext-diff on every verb that accepts it",
    "remote.*.uploadpack": "overridden by --upload-pack on every transport read",
    "diff.*.command": "an attribute-selected driver, disabled by --no-ext-diff",
    "diff.*.textconv": "disabled by --no-textconv, and --textconv is refused as an argument",
}

# A CLOSURE THAT HOLDS ONLY SOMETIMES IS NOT A CLOSURE WHILE THE CONDITION FAILS.
#
# `_transport_settings` removes a neutralisation when a caller deliberately
# enables the matching transport, which hands the repository's own value back to
# Git. The closure above says so in words; this says so in a way the inspection
# can act on. Reproduced before it was written: `publication_gate.verify_remote`
# enabled `ssh`, the override was popped, and a repository's `core.sshCommand`
# ran through this module's own reader while the inspection reported nothing —
# no network, no socket, no ssh binary involved.
CONDITIONAL_CLOSURES = {"core.sshcommand": "ssh"}

# A CLOSURE REACHES ONLY AS FAR AS ITS MECHANISM DOES.
#
# The standing configuration travels as `GIT_CONFIG_*` and IS inherited by a
# process Git launches for itself — a marker written from inside a submodule
# reported `GIT_CONFIG_COUNT=20`. A command-line flag is not: the nested command
# line is Git's, not this module's. So these four are closed for the repository
# the flags were passed to and OPEN for every nested one, which is how a
# submodule's `diff.external` ran under a table that called it handled.
# Mapped to the verbs whose command line actually carries the flag, because the
# flags are not one set: `--no-ext-diff --no-textconv` go on the diff-producing
# verbs, `--upload-pack` on the transport reads. Treating them as one set closed
# `remote.*.uploadpack` for `diff` and opened it for `ls-remote`, which is the
# reverse of the truth in both directions.
FLAG_BASED_CLOSURES = {
    "diff.external": EXTERNAL_PROGRAM_VERBS,
    "diff.*.command": EXTERNAL_PROGRAM_VERBS,
    "diff.*.textconv": EXTERNAL_PROGRAM_VERBS,
    "remote.*.uploadpack": TRANSPORT_VERBS,
}

#: **THEY WERE NEVER CLOSED.** `filter.*.clean`, `filter.*.smudge` and
#: `filter.*.process` sat in the table above claiming to be "reachable only
#: through --filters, which is refused as an argument". That is not true: an
#: ordinary `diff` converts the worktree through the clean filter, and neither
#: `--no-ext-diff` nor `--no-textconv` suppresses it. A whole-candidate reading
#: configured one and watched it run twice while `program_valued_config`
#: reported nothing to see.
#:
#: They are not listed here at all now, so they fall to this module's standing
#: rule — a program-valued key with no named closure REFUSES. Neutralising them
#: instead was considered and rejected: filter names are arbitrary, so it would
#: mean enumerating and blanking each, and an empty clean command makes Git fail
#: rather than proceed, which is breakage wearing the costume of neutralisation.
#:
#: **The cost, stated rather than discovered:** a repository that legitimately
#: uses clean or smudge filters — Git-LFS is the common one — is refused by this
#: reader. Fail-closed is the direction that cannot run somebody else's program,
#: and a project needing those filters governs that as its own decision.


#: How deep a walk into nested repositories went before it refused. Kept as a
#: published name; nothing decides anything with it any more, because the walk it
#: bounded is gone.
MAXIMUM_NESTED_DEPTH = 32


def program_valued_config(
    repository: str | Path, *, timeout: float = DEFAULT_TIMEOUT_SECONDS,
    allow_transports: tuple[str, ...] = (), verb: str = "",
) -> list[str]:
    """Program-valued keys this repository declares. **A REPORT, NOT A BARRIER.**

    Until 2.5.0 this decided whether a read happened: a key with no named closure
    refused the repository. Fifteen repairs across two releases were corrections
    to the lists behind that decision — keys, verbs, flags, transports, option
    spellings, nested layouts — and the last of them produced an under-refusal and
    an over-refusal in the same edit. `docs/RP2.5.0-RECURRENCE-MAP.md` has the set.

    The decision is gone. A governed read now runs in a git directory this harness
    built, where the repository's configuration is not a source at all, so a key
    declared here cannot be executed and refusing over one would only reproduce
    the over-refusal that broke `workspace_report`.

    What remains is the observation, for a caller that wants to know what a
    repository declares. It reads the configuration as DATA — no Git, no
    repository opened, nothing executed — and **no refusal in this pack depends on
    it**, which `test_no_refusal_depends_on_a_projection` is what establishes.
    """
    import fnmatch

    del timeout, allow_transports, verb          # a report is not scoped by them
    declared = sterile.config_as_data(_config_file_of(repository))
    found = [
        key for key in sorted(declared)
        if any(fnmatch.fnmatchcase(key, shape) for shape in PROGRAM_VALUED_CONFIG)
    ]
    return found


def repository_location(repository: str | Path) -> dict:
    """Where the subject repository is, as distinct from where this read runs.

    `sterile.where_is` is the one place that answers it; this is the name the
    toolbelt's callers use. Three of them asked Git instead, and under the
    sterile boundary Git answers about the constructed directory — correctly,
    and about the wrong repository.
    """
    return sterile.where_is(_repository(repository))


def _config_file_of(repository: str | Path) -> Path:
    """The repository's own config file, located without asking Git to open it."""
    subject = Path(_repository(repository)).resolve()
    dot = subject / ".git"
    if dot.is_file():
        raw = dot.read_text(encoding="utf-8", errors="surrogateescape")
        _, _, target = raw.partition(":")
        target = target.strip()
        gitdir = Path(target) if os.path.isabs(target) else (subject / target).resolve()
    elif dot.is_dir():
        gitdir = dot
    else:
        gitdir = subject
    marker = gitdir / "commondir"
    if marker.is_file():
        raw = marker.read_text(encoding="utf-8", errors="surrogateescape").strip()
        gitdir = Path(raw) if os.path.isabs(raw) else (gitdir / raw).resolve()
    return gitdir / "config"


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


def tree_entries_in_history(
    repository: str | Path,
    ref: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[tuple[str, str, str]]:
    """Every ``(type, sha, path)`` a tree in this history ever held.

    The typed form of `every_name_in_history`, which is a filter over it. The
    type matters for one entry kind: a **gitlink** — mode ``160000``, type
    ``commit`` — is a pointer into a repository this one does not contain, and
    a caller that cannot tell it from a blob cannot know it did not read it.
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
    found: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
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
            entry = (parts[1], parts[2], path)
            if entry not in seen:
                seen.add(entry)
                found.append(entry)
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
    seen: set[tuple[str, str]] = set()
    found: list[tuple[str, str]] = []
    for _type, sha, path in tree_entries_in_history(repository, ref, timeout=timeout):
        if (sha, path) not in seen:
            seen.add((sha, path))
            found.append((sha, path))
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


def blobs_at_paths_in_outgoing_range(
    repository: str | Path,
    ref: str,
    baseline: str | None,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[tuple[str, str]]:
    """Every ``(path, blob sha)`` the range introduces or changes, from the trees.

    The companion to :func:`paths_in_outgoing_range`, which returns the paths
    without saying what is at them. Both read the TREES rather than
    ``rev-list --objects``, and for the same measured reason: that listing prints
    one path per object and does not list a blob already reachable from the
    baseline. So a scanner driven by it decided a blob's exemption from whichever
    of its paths Git happened to name, and never re-read content that arrived at
    a new path without changing.
    """
    if baseline is None:
        output = _run(repository, "ls-tree", "-r", "-z", ref, timeout=timeout, text=False)
    else:
        # EVERY COMMIT IN THE RANGE, not the two endpoints. Comparing the
        # endpoints misses content that appeared and was removed WITHIN the
        # range — an independent reader committed private content at a
        # non-exempt path and deleted it in a later outgoing commit, and the
        # endpoint comparison reported clean while the intermediate commit still
        # carries it. Every commit that would be sent is scanned, because every
        # one of them would be.
        output = _run(
            repository, "diff-tree", "-r", "-m", "--no-commit-id", "--diff-filter=ACMRT",
            "-z", "--stdin", timeout=timeout, text=False,
            # BYTES, because this call reads bytes: `text=False` puts the pipe
            # in binary mode in both directions.
            input_value=("\n".join(_run(repository, "rev-list", ref, "--not", baseline,
                                         timeout=timeout).split()) + "\n").encode("ascii"),
        )
    assert isinstance(output, bytes)
    records = [chunk for chunk in output.split(b"\0") if chunk]
    found: list[tuple[str, str]] = []
    if baseline is None:
        # `ls-tree -z`: "<mode> <type> <sha>\t<path>" per record.
        for record in records:
            head, _, path = record.partition(b"\t")
            fields = head.split()
            # `blob` EXCLUDES A GITLINK by type already in this shape.
            if len(fields) == 3 and fields[1] == b"blob" and path:
                found.append((path.decode("utf-8", "surrogateescape"),
                              fields[2].decode("ascii")))
        return found
    # `diff-tree -z`: ":<srcmode> <dstmode> <srcsha> <dstsha> <status>" then the
    # path as its own record.
    index = 0
    while index < len(records):
        record = records[index]
        if record.startswith(b":"):
            fields = record[1:].split()
            if len(fields) >= 5 and index + 1 < len(records):
                destination_mode = fields[1].decode("ascii")
                destination = fields[3].decode("ascii")
                path = records[index + 1].decode("utf-8", "surrogateescape")
                # A GITLINK IS NOT A BLOB. `diff-tree` reports a submodule
                # pointer with mode 160000 and the sha of a commit that lives in
                # ANOTHER repository, so asking this one for its size refused —
                # an ordinary submodule bump aborted the scan, which the
                # pre-repair scan completed. Found by an independent reading.
                if destination_mode == "160000":
                    index += 2
                    continue
                if set(destination) != {"0"}:
                    found.append((path, destination))
                index += 2
                continue
        index += 1
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
    """Every setting **this repository's own configuration file** declares, with its origin.

    Values alone cannot answer the question that matters — whether a setting is
    the user's global preference or something written into this repository's own
    `.git/config` by a process that was not the user. A forensic pass depended on
    exactly that distinction.

    **It reads the FILE, not the repository.** Under the sterile boundary
    `git config --list` reports the harness's own configuration, which is the
    correct answer to a different question and useless for this one. `--file`
    makes Git parse a named file without opening a repository around it: Git's
    own parser, so subsection case and quoting are Git's rules rather than a
    hand-written imitation of them, and no repository semantics are in play.
    Parsing configuration executes nothing — which is the property the whole
    boundary rests on, and it is pinned by an oracle rather than assumed.

    The ambient global and system files are no longer reported, because they are
    no longer read: a governed answer must not depend on the operator's machine.
    """
    entries: list[dict[str, str]] = []
    for path in _configuration_files_of(repository):
        # AN INCLUDE THIS READ DID NOT FOLLOW IS A REFUSAL, NOT A SHORTER LIST.
        #
        # `GIT_DIR` is explicit under this boundary, so Git does not discover the
        # repository around the file — and measured rather than assumed, that
        # means `git config --file` does NOT follow `include.path` here, while the
        # same command from inside the repository does. A repository could
        # therefore hide `notes.*` behind an include and be reported as not having
        # it, which is the surface `DECISIONS.md` D7 exists to watch.
        #
        # Following includes here was rejected: `includeIf` conditions are
        # evaluated against repository state, and predicting which ones match is
        # the habit this release exists to stop. Refusing names the problem
        # instead, and a caller that needs the included values reads that file.
        declared = sterile.config_as_data(path)
        includes = sorted(
            key for key in declared
            if key == "include.path" or (key.startswith("includeif.") and key.endswith(".path"))
        )
        if includes:
            raise GitRefusal(
                "this repository's configuration includes another file, and a read that did not "
                "follow the include cannot be reported as the whole configuration",
                repository=str(repository), file=str(path), includes=", ".join(includes),
            )
        answer = probe(
            repository, "config", "--file", str(path), "--list", "--show-origin", "--null",
            timeout=timeout, negative_statuses=(1,),
        )
        if not answer.answered:
            raise GitRefusal("could not read git configuration", git_refusal=answer.cause)
        if answer.failed:
            # A configuration that cannot be parsed exits non-zero, and returning
            # `[]` for it reports "this repository has no settings" — including no
            # `notes.*` keys, which is the exact surface D7 exists to watch.
            # Nothing was read, so nothing may be concluded.
            raise GitRefusal(
                "git configuration could not be read, so it must not be reported as empty",
                git_refusal=answer.cause, returncode=answer.status, file=str(path),
            )
        if not answer.ok:
            continue
        records = [record for record in answer.value.split("\x00") if record]
        for index in range(0, len(records) - 1, 2):
            origin = records[index]
            key, _, value = records[index + 1].partition("\n")
            entries.append({"origin": origin, "key": key, "value": value})
    return entries


def _configuration_files_of(repository: str | Path) -> list[Path]:
    """The repository's own configuration files, in the order Git layers them."""
    main = _config_file_of(repository)
    found = [main] if main.is_file() else []
    subject = Path(_repository(repository)).resolve()
    dot = subject / ".git"
    gitdir = dot if dot.is_dir() else main.parent
    if dot.is_file():
        raw = dot.read_text(encoding="utf-8", errors="surrogateescape")
        _, _, target = raw.partition(":")
        target = target.strip()
        gitdir = Path(target) if os.path.isabs(target) else (subject / target).resolve()
    worktree_config = gitdir / "config.worktree"
    if worktree_config.is_file():
        found.append(worktree_config)
    return found


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
