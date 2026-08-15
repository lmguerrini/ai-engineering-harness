"""Publication safety as a ref-namespace contract, not a clean-tree check.

A repository can satisfy every authorship check a project performs — clean
commit messages, a single human author, no `Co-Authored-By` trailer anywhere in
full history — while simultaneously carrying machine-readable AI contribution
attribution, private orchestration identities and private session identifiers.
They live in `refs/notes/*`, which is not a commit on a branch, so `git log`,
`git status`, `git ls-files`, `git diff` and `git show` are all blind to it.
Those five commands were the entire hygiene surface.

This is observed, not hypothetical: notes written by an IDE provenance service
can hold, verbatim, per-file and per-line-range records naming an agent, a
model id and a session uuid. Three properties of that class of writer govern
the design here:

*   **Deleting the refs is a race, not a control.** A ref deleted and verified
    gone can be re-created within seconds, and again on the next cycle.
*   **It survives history rewriting.** A notes ref can come back annotating a
    commit that did not exist until a rebase created it minutes earlier.
*   **It rewrites repository-local `.git/config`.** Settings removed in one
    session can be back before the next push.

So safety cannot rest on the namespace being clean at some earlier instant. It
rests on four things together, checked in the same step as the push:

    an allowed source ref  +  reachability  +  an exact push refspec
                           +  a remote postcondition

The fourth matters because the first three are all local claims. And the gate
fails closed: a check that could not be performed is never a check that passed.

One methodological rule is enforced by this module's existence rather than by
its code. Two separate sessions inferred causation from configuration
correlation — `notes.rewriteRef` was present, it plausibly explained the
behaviour, and that explanation was recorded as an identification. An
intervention test falsified it: with the config removed and no amend or rebase
performed, the refs still reappeared. **A configuration that could
explain an effect is not evidence that it did.** Hence `config_with_origin`
reports settings and their source, and never concludes from them.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import gitread
import pathmatch

__all__ = [
    "PublicationReport",
    "RefFinding",
    "DEFAULT_PUBLISHABLE_REFS",
    "FORBIDDEN_PUSH_FORMS",
    "inspect_namespace",
    "check_push_command",
    "verify_remote",
]

#: What an ordinary public repository is allowed to carry. Everything else is
#: reported, including refs nobody has a name for — an unrecognised namespace
#: is the case this gate exists for.
DEFAULT_PUBLISHABLE_REFS = ("refs/heads/*", "refs/tags/*")

#: Push forms that carry `refs/notes/*` and every other ref regardless of the
#: allowlist. Named rather than described, so the check is mechanical.
FORBIDDEN_PUSH_FORMS = (
    ("--mirror", "pushes every ref, including notes and recovery refs"),
    ("--all", "pushes every branch, including feature and recovery branches"),
    ("--follow-tags", "pushes tags that were never named"),
    ("--tags", "pushes tags that were never named"),
)

# A note on what this gate deliberately does **not** do: it does not decode and
# scan note payloads. The observed payload was gzip inside base64, so a content
# scan that stops at the encoding boundary reports clean on it — but chasing
# that leads to an arms race against encodings. Refusing the whole ref is
# strictly stronger and does not depend on recognising a format: a `refs/notes/*`
# ref is refused whether its payload is AI attribution, commit-SHA bookkeeping,
# or empty. The only thing payload analysis could buy is permission to publish a
# non-allowlisted ref after inspecting it, which is not a case worth supporting.

#: `refs/notes/*` is the observed case; the others are namespaces a working
#: repository accumulates that no public repository has a reason to receive.
_KNOWN_PRIVATE_NAMESPACES = (
    ("refs/notes/", "provenance or annotation notes, invisible to git log and git status"),
    ("refs/stash", "local stash state"),
    ("refs/heads/worktree-agent-", "an agent worktree branch created inside the repository under review"),
    ("refs/heads/recovery/", "a recovery branch retained through implementation"),
    ("refs/original/", "history-rewrite backup refs"),
    ("refs/remotes/", "remote-tracking refs"),
)

_PUSH_REFSPEC = re.compile(r"^refs/heads/[^:*\s]+:refs/heads/[^:*\s]+$")


@dataclass(frozen=True)
class RefFinding:
    refname: str
    reason: str
    identity: str = ""
    reachable_from_public: bool = False


@dataclass
class PublicationReport:
    repository: str
    publishable: tuple[str, ...]
    refs_seen: int = 0
    findings: list[RefFinding] = field(default_factory=list)
    config_notes: list[str] = field(default_factory=list)
    identity_findings: list[str] = field(default_factory=list)
    #: Set when a check could not be performed. A gate that could not look must
    #: never render as a gate that found nothing.
    could_not_check: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.findings and not self.identity_findings and not self.could_not_check

    def render(self) -> str:
        if self.clean:
            lines = [
                f"publication namespace {self.repository}: clean "
                f"({self.refs_seen} refs, all within {', '.join(self.publishable)})"
            ]
            lines.extend(f"  note: {item}" for item in self.config_notes)
            return "\n".join(lines)
        lines = [f"publication namespace {self.repository}: NOT PUBLISHABLE"]
        for finding in self.findings:
            reach = "REACHABLE FROM THE PUBLIC REF" if finding.reachable_from_public else "not reachable from the public ref"
            lines.append(f"  {finding.refname}: {finding.reason}")
            lines.append(f"    {reach}{f' · authored by {finding.identity}' if finding.identity else ''}")
        for item in self.identity_findings:
            lines.append(f"  identity: {item}")
        for item in self.could_not_check:
            lines.append(f"  COULD NOT CHECK: {item}")
        for item in self.config_notes:
            lines.append(f"  note: {item}")
        return "\n".join(lines)


def inspect_namespace(
    repository: str | Path,
    *,
    public_ref: str,
    publishable: tuple[str, ...] = DEFAULT_PUBLISHABLE_REFS,
    human_identities: tuple[str, ...] = (),
) -> PublicationReport:
    """Enumerate every ref, classify it, and test what the public ref reaches.

    ``human_identities`` are the author/committer identities the project
    declares. An object authored by anything else is reported: the observed
    leak was authored by `chatter <observer@chatter.local>`, an identity no
    human ever typed.
    """
    report = PublicationReport(repository=str(repository), publishable=publishable)

    try:
        all_refs = gitread.refs(repository)
    except Exception as exc:
        report.could_not_check.append(f"the ref namespace could not be enumerated: {exc}")
        return report
    report.refs_seen = len(all_refs)

    for entry in all_refs:
        name = entry["refname"]
        # Known-private namespaces are checked BEFORE the allowlist, because
        # some of them live *inside* an allowed one: `refs/heads/worktree-agent-*`
        # is a plain branch and `refs/heads/*` admits it. Testing the allowlist
        # first let exactly the ref an agent creates inside the repository under
        # review pass as an ordinary branch — the same wrong-domain shape the
        # rest of this delta exists to close.
        reason = _classify(name)
        if reason is None:
            if pathmatch.matches_any(name, publishable):
                continue
            reason = (
                "outside the declared publishable allowlist, and not a namespace "
                "this gate recognises"
            )
        identity = f"{entry['authorname']} {entry['authoremail']}".strip()
        try:
            reachable = gitread.is_ancestor(repository, entry["objectname"], public_ref)
        except Exception:
            # An unreachable answer is not "not reachable". Say so.
            report.could_not_check.append(f"ancestry of {name} against {public_ref}")
            reachable = False
        report.findings.append(RefFinding(name, reason, identity, reachable))

    if human_identities:
        report.identity_findings.extend(
            _identity_findings(repository, public_ref, human_identities, report)
        )

    report.config_notes.extend(_config_notes(repository, report))
    return report


def _classify(refname: str) -> str | None:
    """Why this ref is private, or ``None`` if the allowlist should decide."""
    for prefix, reason in _KNOWN_PRIVATE_NAMESPACES:
        if refname.startswith(prefix):
            return reason
    return None


def _identity_findings(
    repository: str | Path, public_ref: str, human_identities: tuple[str, ...], report: PublicationReport
) -> list[str]:
    """Author and committer identities on the public ref that were not declared."""
    declared = {identity.strip().lower() for identity in human_identities}
    found: list[str] = []
    seen: set[str] = set()
    try:
        for sha, _ in gitread.objects_in_outgoing_range(repository, public_ref, None):
            if gitread.object_type(repository, sha) != "commit":
                continue
            metadata = gitread.commit_metadata(repository, sha)
            for role in ("author", "committer"):
                identity = f"{metadata[f'{role}_name']} <{metadata[f'{role}_email']}>"
                if identity.strip().lower() in declared or identity in seen:
                    continue
                seen.add(identity)
                found.append(f"{sha[:12]} {role} {identity} is not a declared human author")
    except Exception as exc:
        report.could_not_check.append(f"authorship of {public_ref}: {exc}")
    return found


def _config_notes(repository: str | Path, report: PublicationReport) -> list[str]:
    """Configuration that bears on publication, reported **with its origin**.

    Reported, never concluded from. These settings propagate notes across amend
    and rebase, which is one of three separable mechanisms — the process that
    originally writes provenance notes, git's rewrite propagation, and ref
    initialisation. They fail differently and are neutralised differently, and
    an earlier session lost a day to treating them as one.
    """
    notes: list[str] = []
    try:
        entries = gitread.config_with_origin(repository)
    except Exception as exc:
        report.could_not_check.append(f"git configuration could not be read: {exc}")
        return notes
    for entry in entries:
        key = entry["key"].lower()
        if key.startswith("notes.") or (key.startswith("remote.") and key.endswith(".mirror")):
            notes.append(f"{entry['key']}={entry['value']} (from {entry['origin']})")
    return notes


def check_push_command(command: str, *, publishable_branches: tuple[str, ...] = ()) -> list[str]:
    """Every reason this push command is not the supported publication form.

    The supported form is one exact refspec: ``refs/heads/main:refs/heads/main``.
    It is supported because it is *structurally* safe — it cannot carry
    `refs/notes/*` regardless of what the namespace holds at that instant — so
    it does not depend on winning a race against a writer that re-creates refs
    in under a minute.
    """
    problems: list[str] = []
    tokens = command.split()

    for flag, why in FORBIDDEN_PUSH_FORMS:
        if flag in tokens:
            problems.append(f"{flag} is forbidden: it {why}")

    refspecs = [token for token in tokens if ":" in token and token.startswith("refs/")]
    wildcard = [token for token in refspecs if "*" in token]
    if wildcard:
        problems.append(f"wildcard refspec {wildcard[0]!r} is forbidden: it carries whatever the namespace holds")

    explicit = [token for token in refspecs if _PUSH_REFSPEC.match(token)]
    if not explicit and not problems:
        problems.append(
            "no explicit refs/heads/<branch>:refs/heads/<branch> refspec found; "
            "a bare `git push` publishes whatever the branch's upstream names"
        )
    if publishable_branches:
        for spec in explicit:
            source = spec.split(":", 1)[0]
            if not pathmatch.matches_any(source, publishable_branches):
                problems.append(f"{source} is not a declared publishable ref")
    return problems


def verify_remote(
    repository: str | Path, remote: str, *, expected: dict[str, str]
) -> list[str]:
    """Every way the remote's namespace differs from what was intended.

    Runs **after** the push. The three local checks are all claims about what
    should have happened; this is the one observation of what did. It fails
    closed: an unreadable remote is a failure, not an absence of findings.
    """
    problems: list[str] = []
    # No declared negative: `ls-remote` printing nothing and exiting 0 is the
    # "no refs" answer, so every non-zero status here means nobody looked.
    answer = gitread.probe(repository, "ls-remote", remote, negative_statuses=())
    if not answer.answered or not answer.ok:
        return [f"the remote {remote!r} could not be read, so publication is unverified: {answer.cause}"]

    seen: dict[str, str] = {}
    for line in answer.value.splitlines():
        if not line.strip():
            continue
        sha, _, name = line.partition("\t")
        if name:
            seen[name.strip()] = sha.strip()

    for name, sha in sorted(seen.items()):
        if name.endswith("^{}") or name == "HEAD":
            continue
        if name not in expected:
            problems.append(f"the remote carries an unexpected ref {name} at {sha[:12]}")
            continue
        wanted = expected[name]
        # An empty expectation means "must exist, any revision" — the caller
        # knows the ref should be there but not yet which commit it lands on.
        if wanted and not _same_revision(sha, wanted):
            problems.append(f"{name} is at {sha[:12]} on the remote, expected {wanted[:12]}")
    for name in expected:
        if name not in seen:
            problems.append(f"the remote does not carry {name}, which the push was supposed to create")
    return problems


def _same_revision(left: str, right: str) -> bool:
    """Whether two revisions match, tolerating one being abbreviated."""
    shortest = min(len(left), len(right))
    if shortest < 7:
        return False
    return left[:shortest].lower() == right[:shortest].lower()


def _cli(argv: list[str]) -> int:
    """Enumerate a repository's ref namespace and judge a publication.

    Usage: ``publication_gate.py REPO --public-ref REF [--project PATH]
            [--publishable GLOB ...] [--author IDENTITY ...]
            [--push-command "git push ..."] [--verify-remote NAME]``
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="publication_gate.py",
        description="Check the full ref namespace, the push form, and the remote postcondition.",
    )
    parser.add_argument("repository", nargs="?")
    parser.add_argument("--project", help="path to PROJECT.yaml")
    parser.add_argument("--public-ref", help="the ref being published; defaults to the contract's release_ref")
    parser.add_argument("--publishable", action="append", default=[], metavar="GLOB")
    parser.add_argument("--author", action="append", default=[], metavar="IDENTITY")
    parser.add_argument("--push-command", help="the exact push command that would be run")
    parser.add_argument("--verify-remote", metavar="NAME", help="read this remote and check its namespace")
    args = parser.parse_args(argv)

    contract = None
    if args.project:
        from project_contract import ContractError, ProjectContract

        try:
            contract = ProjectContract.load(args.project)
        except ContractError as exc:
            print(f"CONTRACT UNREADABLE {exc}")
            return 2

    repository = args.repository or (contract.repository() if contract else None)
    public_ref = args.public_ref or (contract.release_ref if contract else None)
    if not repository or not public_ref:
        print("a repository and a public ref are required, positionally or via --project")
        return 2

    publishable = tuple(args.publishable) or (
        tuple(contract.publishable_refs) if contract and contract.publishable_refs else DEFAULT_PUBLISHABLE_REFS
    )

    report = inspect_namespace(
        repository, public_ref=public_ref, publishable=publishable,
        human_identities=tuple(args.author),
    )
    print(report.render())
    failed = not report.clean

    if args.push_command:
        problems = check_push_command(args.push_command, publishable_branches=publishable)
        if problems:
            failed = True
            print("push form: REFUSED")
            for problem in problems:
                print(f"  {problem}")
        else:
            print("push form: an explicit single-branch refspec, which cannot carry refs/notes/*")

    if args.verify_remote:
        problems = verify_remote(repository, args.verify_remote, expected={public_ref: ""})
        if problems:
            failed = True
            print(f"remote {args.verify_remote}: POSTCONDITION FAILED")
            for problem in problems:
                print(f"  {problem}")
        else:
            print(f"remote {args.verify_remote}: namespace matches what was published")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
