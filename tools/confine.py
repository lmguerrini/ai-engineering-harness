"""Operating-system confinement for a worker process, and the refusal when there is none.

This module makes confinement a property of the *dispatch* rather than of the
runtime, and makes its absence a refusal rather than a silence.

Four backends, and the important one is the last:

``seatbelt``        macOS's own sandbox, generated per dispatch from the writable
                    roots, the denied read set and the network policy.
``runtime_native``  the runtime confines itself, and **reports that it did**. A
                    request is not evidence; only an observation counts.
``none``            read-only work — an auditor reading an immutable head — where
                    there is nothing to contain and it is recorded as such.
``deny``            the default anywhere else. An implementation worker does not
                    run unconfined merely because confinement is unavailable.

HONEST BOUNDS, carried forward rather than papered over:

*   This is macOS-only. There is no confinement backend here for any other
    platform; the only alternatives are ``runtime_native`` (the runtime's own
    sandbox, only on its own report) and ``deny``.
*   A Seatbelt profile cannot be validated from inside a sandboxed worker —
    there is no introspection point from which a confined process can prove
    its own confinement held. Confidence comes from generating the profile
    correctly and from the caller's own environment, not from the worker.
*   Reads *inside* the private root are deny-by-default with per-dispatch
    allows. Reads *outside* the private root remain permissive except a short,
    enumerated set of sensitive subpaths (``SENSITIVE_READ_SUBPATHS``). A
    worker legitimately reads the interpreter, its standard library and the
    system's shared caches, so a global read allowlist would stop ordinary
    work — but that also means this profile does not deny reads of arbitrary
    files outside the private root that are not in the enumerated set.

STALE AUDIT NOTICE: this module's last adversarial audit is one round stale
relative to the toolbelt extraction. Reuse in a new context is gated on a
fresh adversarial re-derivation of the profile, not on this docstring's
description of the previous one.
"""

from __future__ import annotations

import platform
import shutil
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from errors import PreconditionError

__all__ = [
    "BACKENDS",
    "Confinement",
    "IsolationRefused",
    "available_backend",
    "confine",
    "describe",
    "seatbelt_profile",
]

BACKENDS = ("seatbelt", "runtime_native", "none", "deny")

#: Directories a worker never has a reason to read. Named explicitly rather
#: than derived, because "everything except the checkout" is unenforceable —
#: the interpreter, its standard library and the Git binary all live outside
#: it, so a pure allowlist over reads makes an ordinary task impossible.
#: Outside the private root, what can be denied is the set of places whose
#: contents are *secrets*, and that set is short and stable enough to
#: enumerate.
SENSITIVE_READ_SUBPATHS = (
    ".ssh",
    ".aws",
    ".gnupg",
    ".config/gh",
    ".config/gcloud",
    ".docker",
    ".kube",
    ".npmrc",
    ".pypirc",
    ".netrc",
    ".git-credentials",
)


class IsolationRefused(PreconditionError):
    """A worker that must be confined cannot be, so it does not run."""


@dataclass(frozen=True)
class Confinement:
    """How one dispatch will be confined, and how to launch under it."""

    backend: str
    #: Roots the worker may write to. Everything else is read-only at best.
    writable_roots: tuple[str, ...] = ()
    #: Paths whose contents are denied even to reads.
    denied_reads: tuple[str, ...] = ()
    #: Whether the worker may open outbound connections beyond the loopback.
    network: str = "denied"
    reason: str = ""
    profile: str = ""

    def wrap(self, command: Sequence[str]) -> tuple[str, ...]:
        """The command line that runs ``command`` under this confinement."""
        if self.backend == "seatbelt":
            return ("/usr/bin/sandbox-exec", "-p", self.profile, *command)
        if self.backend in {"runtime_native", "none"}:
            return tuple(command)
        raise IsolationRefused(
            "this dispatch has no confinement and will not be launched",
            backend=self.backend, reason=self.reason,
        )

    def as_configuration(self) -> str:
        """The part of a worker's evidence identity this contributes.

        Backend *and* network policy. Two runs of one model with the network
        open and shut are two configurations — the second cannot reach its
        service at all — so rendering only the backend made them share an
        envelope and pooled evidence that is not about the same thing.
        """
        return f"{self.backend}+network={self.network}"


def available_backend(*, allow_native: bool = False) -> str:
    """The strongest confinement this host can actually provide, right now.

    Probed rather than assumed. A profile that cannot be loaded is not
    confinement, and a host that reports the right operating system but has
    no working sandbox binary must fall through to a refusal rather than to a
    launch.
    """
    if allow_native:
        return "runtime_native"
    if platform.system() == "Darwin" and shutil.which("sandbox-exec"):
        return "seatbelt"
    return "deny"


def _seatbelt_path(path: str | Path) -> str:
    """Render one resolved path as a Seatbelt string literal.

    POSIX paths may contain quotes, backslashes, and newlines. Seatbelt uses
    Scheme-style string literals, so every dynamic path enters the profile
    through this serializer: backslashes are escaped first, then quotes and
    control characters. Parentheses need no special spelling once the string
    cannot be closed by path data.
    """
    value = str(Path(path).resolve())
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _seatbelt_subpath(path: str | Path) -> str:
    """Match a resolved path and all of its descendants."""
    return f"(subpath {_seatbelt_path(path)})"


def _seatbelt_literal(path: str | Path) -> str:
    """Match one resolved path, without granting anything below it."""
    return f"(literal {_seatbelt_path(path)})"


def _private_traversal_directories(
    private_root: Path, allowed_roots: Sequence[Path]
) -> tuple[Path, ...]:
    """The exact private-root ancestor closure needed to reach allowed roots.

    Full reads remain confined to ``allowed_roots`` and their descendants.
    This closure is only for metadata rules on the directories from the
    private boundary down to each allowed root, so resolving an authorised
    path does not also make its siblings listable or their content readable.
    """
    directories: dict[Path, None] = {}
    for allowed in allowed_roots:
        try:
            relative = allowed.relative_to(private_root)
        except ValueError:
            # Reads outside the private boundary are already covered by the
            # permissive global policy and need no carve-out from its deny.
            continue
        directory = private_root
        directories.setdefault(directory, None)
        for part in relative.parts:
            directory /= part
            directories.setdefault(directory, None)
    return tuple(directories)


def seatbelt_profile(
    *,
    writable_roots: Sequence[str | Path],
    denied_reads: Sequence[str | Path] = (),
    private_read_root: str | Path | None = None,
    allowed_read_roots: Sequence[str | Path] = (),
    allow_loopback: bool = False,
    allow_outbound: bool = False,
) -> str:
    """A macOS sandbox profile with generated write and private-read boundaries.

    Writes are an allowlist. Reads remain permissive everywhere except the
    private root: a worker legitimately reads the interpreter, its standard
    library, the Git binary and the system's shared caches, so a global read
    allowlist would stop ordinary work. The private root has the opposite
    trust shape — every present and future child is private unless this
    dispatch names it — so it is denied first and the dispatch-authorised
    roots are reopened for reads afterwards.
    """
    lines = [
        "(version 1)",
        "(allow default)",
        # Network first, so a later allow can carve out loopback for a local
        # model endpoint without reopening the whole stack.
        "(deny network*)",
        # Automation is not a filesystem operation and not a network one, so
        # denying both left it wide open: `osascript` drove Finder from
        # inside the first version of this profile and exited cleanly.
        "(deny appleevent-send)",
    ]
    if allow_outbound:
        # A worker whose entire function is a call to a remote service.
        lines.append("(allow network-outbound)")
    elif allow_loopback:
        lines.append('(allow network-outbound (remote ip "localhost:*"))')
        lines.append("(allow network-inbound (local ip \"localhost:*\"))")
    lines.append("(allow network-outbound (remote unix-socket))")
    lines.append("(deny file-write*)")

    # Resolved, always. The sandbox matches on the path the kernel *reaches*,
    # and on macOS `/var`, `/tmp` and `/etc` are symlinks into `/private`, so
    # an unresolved root names a path that does not exist as far as the
    # profile is concerned.
    permitted = [Path(root).resolve() for root in writable_roots]
    # The devices a process needs to be a process. Denying these does not
    # confine a worker, it prevents one from starting.
    device_terms = [
        '(literal "/dev/null")', '(literal "/dev/zero")', '(literal "/dev/dtracehelper")',
        '(literal "/dev/tty")', '(literal "/dev/random")', '(literal "/dev/urandom")',
        '(regex #"^/dev/fd/[0-9]+$")', '(regex #"^/dev/ttys[0-9]*$")',
    ]
    subpaths = " ".join(_seatbelt_subpath(path) for path in permitted)
    lines.append(f"(allow file-write* {subpaths} {' '.join(device_terms)})")

    if private_read_root is not None:
        private = Path(private_read_root).resolve()
        # Seatbelt is last-match-wins. Deny the generated parent first; the
        # dispatch's own and explicitly authorised roots then become the
        # complete private carve-out.
        lines.append(f"(deny file-read* {_seatbelt_subpath(private)})")
        readable = [*permitted, *(Path(root).resolve() for root in allowed_read_roots)]
        traversal = _private_traversal_directories(private, readable)
        if traversal:
            # A process such as Git discovers repository boundaries by
            # walking upward and inspecting each directory. Reopening only
            # the leaf roots leaves those intervening metadata reads denied.
            lines.append(
                "(allow file-read-metadata "
                + " ".join(_seatbelt_literal(path) for path in traversal)
                + ")"
            )
        if readable:
            lines.append(
                "(allow file-read* "
                + " ".join(_seatbelt_subpath(path) for path in dict.fromkeys(readable))
                + ")"
            )

    denied = [Path(path).resolve() for path in denied_reads]
    if denied:
        # These are independent denials, not private-root defaults. Keeping
        # them last means a mistakenly nested writable root cannot reopen a
        # credential store or the current project's durable authority.
        lines.append(
            "(deny file-read* " + " ".join(_seatbelt_subpath(path) for path in denied) + ")"
        )
    return "\n".join(lines) + "\n"


def confine(
    *,
    writable_roots: Sequence[str | Path],
    private_read_root: str | Path,
    denied_reads: Sequence[str | Path] = (),
    allowed_read_roots: Sequence[str | Path] = (),
    read_only: bool = False,
    runtime_confines_itself: bool = False,
    allow_loopback: bool = False,
    allow_outbound: bool = False,
    backend: str | None = None,
) -> Confinement:
    """Decide and build the confinement for one dispatch.

    ``runtime_confines_itself`` must come from an *observation* that the
    runtime applied its sandbox, never from having asked it to. The
    distinction is the whole difference between a confinement and a request,
    and a runtime that silently ignores the flag would otherwise be
    indistinguishable from one that honours it.
    """
    if private_read_root is None:
        # A caller that cannot name the shared private boundary has not
        # defined what it is confining. Do not guess from a writable root:
        # only the caller owns the sibling topology.
        raise IsolationRefused(
            "a confined dispatch must declare its private read root",
        )
    private = Path(private_read_root).resolve()
    if not private.is_dir():
        raise IsolationRefused(
            "the private read root must resolve to an existing directory",
            private_read_root=str(private),
        )

    chosen = backend or available_backend(allow_native=runtime_confines_itself)
    if chosen not in BACKENDS:
        raise PreconditionError("unknown isolation backend", backend=chosen)

    # Named once. The profile and the durable description are two renderings
    # of one decision, and a run whose record says `denied` while its profile
    # said otherwise would be the worst kind of evidence.
    policy = "outbound" if allow_outbound else ("loopback" if allow_loopback else "denied")

    if chosen == "none":
        if not read_only:
            # `none` exists for an auditor reading an immutable head. Letting
            # a writing worker select it would make the backend a way of
            # opting out of confinement, which is the opposite of what it is
            # for.
            raise IsolationRefused(
                "only read-only work may run without confinement",
                backend=chosen,
            )
        return Confinement(
            backend="none", reason="read-only work with nothing to contain",
            network=policy,
        )

    if chosen == "runtime_native":
        if not runtime_confines_itself:
            raise IsolationRefused(
                "this runtime has not been observed applying its own sandbox",
                backend=chosen,
            )
        return Confinement(
            backend="runtime_native",
            reason="the runtime reported that it applied its own sandbox",
            writable_roots=tuple(str(Path(root)) for root in writable_roots),
            network=policy,
        )

    if chosen == "seatbelt":
        if available_backend() != "seatbelt":
            raise IsolationRefused(
                "the seatbelt backend was requested on a host that cannot provide it",
                backend=chosen, host=platform.system(),
            )
        if not writable_roots:
            raise IsolationRefused(
                "a confined worker needs somewhere to write; none was declared",
                backend=chosen,
            )
        denied = tuple(str(Path(path)) for path in denied_reads)
        private_path = str(private)
        profile = seatbelt_profile(
            writable_roots=writable_roots, denied_reads=denied,
            private_read_root=private_path, allowed_read_roots=allowed_read_roots,
            allow_loopback=allow_loopback, allow_outbound=allow_outbound,
        )
        return Confinement(
            backend="seatbelt",
            writable_roots=tuple(str(Path(root)) for root in writable_roots),
            # One durable statement of the effective denied set. The profile
            # renders the private root separately only because its generated
            # allow carve-outs must follow it in Seatbelt's ordered language.
            denied_reads=(private_path,) + denied,
            network=policy,
            reason="confined by a generated sandbox profile",
            profile=profile,
        )

    # `deny`, and every path that fell through to it.
    raise IsolationRefused(
        "no isolation backend is available on this host, so an implementation "
        "worker will not be dispatched unconfined",
        backend="deny", host=platform.system(),
    )


def describe(confinement: Confinement) -> dict[str, object]:
    """What the durable record says about how this worker was confined."""
    return {
        "backend": confinement.backend,
        "network": confinement.network,
        "writable_roots": list(confinement.writable_roots),
        "denied_reads": list(confinement.denied_reads),
        "reason": confinement.reason,
    }


def sensitive_reads_for(home: str | Path) -> tuple[str, ...]:
    """The credential stores under one home directory, as absolute paths."""
    base = Path(home)
    return tuple(str(base / name) for name in SENSITIVE_READ_SUBPATHS)


def _cli(argv: list[str]) -> int:
    """Generate and report the confinement decision for one dispatch.

    Usage: ``confine.py --writable ROOT [--writable ROOT ...] --private-read-root ROOT [OPTIONS]``

    Prints the chosen backend, network policy, writable roots and denied
    reads; prints the generated Seatbelt profile when the backend is
    ``seatbelt``. Exits non-zero when confinement is refused.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="confine.py", description=_cli.__doc__.strip().splitlines()[0])
    parser.add_argument("--writable", action="append", default=[], metavar="ROOT")
    parser.add_argument("--private-read-root", required=True, metavar="ROOT")
    parser.add_argument("--denied-read", action="append", default=[], metavar="PATH")
    parser.add_argument("--allowed-read-root", action="append", default=[], metavar="ROOT")
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--runtime-confines-itself", action="store_true")
    parser.add_argument("--allow-loopback", action="store_true")
    parser.add_argument("--allow-outbound", action="store_true")
    parser.add_argument("--backend", choices=BACKENDS, default=None)
    parser.add_argument("--show-profile", action="store_true", help="print the generated Seatbelt profile, if any")
    args = parser.parse_args(argv)

    try:
        confinement = confine(
            writable_roots=args.writable,
            private_read_root=args.private_read_root,
            denied_reads=args.denied_read,
            allowed_read_roots=args.allowed_read_root,
            read_only=args.read_only,
            runtime_confines_itself=args.runtime_confines_itself,
            allow_loopback=args.allow_loopback,
            allow_outbound=args.allow_outbound,
            backend=args.backend,
        )
    except IsolationRefused as exc:
        print(exc.render(), file=sys.stderr)
        return exc.exit_status

    for key, value in describe(confinement).items():
        print(f"{key}={value}")
    if args.show_profile and confinement.profile:
        print("--- profile ---")
        print(confinement.profile, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
