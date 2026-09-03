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

import fnmatch
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import gitread
from errors import PreconditionError

__all__ = [
    "PublicationReport",
    "RefFinding",
    "DEFAULT_PUBLISHABLE_REFS",
    "FORBIDDEN_PUSH_FORMS",
    "SUPPORTED_PUSH_FORM",
    "matches_ref_glob",
    "inspect_namespace",
    "check_push_command",
    "verify_remote",
    "REMOTE_VERIFICATION_TRANSPORTS",
    "expectation_from_refspec",
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
    # A rewrite tool leaves a
    # namespace nobody records, and the gate that would have caught it ran
    # before the tool created it.
    ("refs/rewritten/", "residue a history-rewrite tool left behind"),
    ("refs/replace/", "object replacement refs, which change what a clone sees"),
    ("refs/remotes/", "remote-tracking refs"),
)

_PUSH_REFSPEC = re.compile(r"^refs/heads/[^:*\s]+:refs/heads/[^:*\s]+$")

#: The whole supported publication form, as a token shape: `git push`, one
#: remote, one refspec, nothing else. Written as a constant so the refusal
#: message and the check cannot drift apart.
SUPPORTED_PUSH_FORM = "git push <remote> refs/heads/<branch>:refs/heads/<branch>"

#: The transports the remote postcondition may cross, and the only widening of
#: the read-only layer's hardening anywhere in this pack.
#:
#: `gitread` refuses every protocol by default, correctly: nothing else in the
#: toolbelt has any business leaving the machine. The one exception is this
#: check, which exists *to* leave it — it is the single observation of what a
#: push actually did, and it was measured non-functional on every real remote
#: because the hardening that protects every other read also disabled it.
#:
#: Scoped to this operation and enumerated by name. The widening is per
#: invocation, adds `protocol.<name>.allow` beside the standing
#: `protocol.allow = never` rather than relaxing it, and every transport not
#: listed here stays refused everywhere including here.
REMOTE_VERIFICATION_TRANSPORTS = ("ssh", "https", "file")

#: Git answers `ls-remote` and `rev-parse` with full object names. Anything
#: shorter reaching the postcondition comparison is a caller defect.
_FULL_OBJECT_NAME = re.compile(r"^[0-9a-f]{40}$")


#: What a ref's containment in the public ref actually is. Four states, because
#: there are four — and collapsing them to a boolean is how this gate printed a
#: sentence nobody had established.
#:
#: `CONTAINED` — the ref's object is reachable from the public ref. Untidy,
#: carries nothing extra.
#: `NOT_CONTAINED` — it holds material outside the published graph. The case
#: that matters.
#: `NOT_APPLICABLE` — the ref does not name a commit at all. Ancestry is not a
#: question that can be asked of a blob or a tree, and answering it anyway
#: produced "CARRIES OBJECTS THE PUBLIC REF DOES NOT" as a statement of fact
#: from a call that had exited 128.
#: `UNKNOWN` — git was asked and could not answer.
CONTAINED = "CONTAINED"
NOT_CONTAINED = "NOT_CONTAINED"
NOT_APPLICABLE = "NOT_APPLICABLE"
UNKNOWN = "UNKNOWN"

#: The sentence printed for each. An annotated tag gets its own, because it is
#: the case that reported in the *reassuring* direction: `merge-base` peels a
#: tag to its commit, so a tag whose commit is published answered "contained"
#: — while the tag object itself is an object the public ref does not carry,
#: and it holds a tagger name, a tagger email and a message.
_CONTAINMENT_SENTENCE = {
    CONTAINED: "already contained in the public ref — untidy, carries no extra object",
    NOT_CONTAINED: "CARRIES OBJECTS THE PUBLIC REF DOES NOT",
    NOT_APPLICABLE: "not a commit, so containment does not apply — this ref names an object outside commit history",
    UNKNOWN: "CONTAINMENT UNKNOWN — git was asked and could not answer",
}

_TAG_SENTENCE = (
    "an ANNOTATED TAG: the public ref carries the commit this tag points at, but not "
    "the tag object itself, which is an extra object carrying a tagger identity and message"
)


@dataclass(frozen=True)
class RefFinding:
    refname: str
    reason: str
    identity: str = ""
    #: One of the four constants above. Was a `bool` through 2.1.1, which had
    #: no way to say "not applicable" or "not established" and therefore said
    #: "CARRIES OBJECTS THE PUBLIC REF DOES NOT" for both.
    containment: str = NOT_CONTAINED
    #: The ref's git object type, as `for-each-ref` reports it. Already
    #: available and previously unread.
    objecttype: str = ""

    @property
    def contained_in_public(self) -> bool:
        """Retained for callers written against the 2.1.1 field.

        Deliberately true only for `CONTAINED`: every other state — including
        the two that did not exist before — is not a statement that the ref
        carries nothing extra.
        """
        return self.containment == CONTAINED

    def __post_init__(self) -> None:
        # The 4th positional changed type in RP2.2 (`bool` -> one of four
        # strings). A caller written against the 2.1.1 signature would have
        # stored `True` here and silently reported the UNKNOWN sentence, since
        # `contained_in_public` compares against a constant. Refuse instead.
        if self.containment not in _CONTAINMENT_SENTENCE:
            raise ValueError(
                f"containment {self.containment!r} is not one of "
                f"{', '.join(sorted(_CONTAINMENT_SENTENCE))}; RP2.2 replaced the boolean "
                "with a four-state value, and a bool passed here is a caller written "
                "against the older signature"
            )

    def sentence(self) -> str:
        if self.objecttype == "tag" and self.containment in (CONTAINED, NOT_CONTAINED):
            return _TAG_SENTENCE
        return _CONTAINMENT_SENTENCE.get(self.containment, _CONTAINMENT_SENTENCE[UNKNOWN])


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
            lines.append(f"  {finding.refname}: {finding.reason}")
            lines.append(
                f"    {finding.sentence()}"
                f"{f' · authored by {finding.identity}' if finding.identity else ''}"
            )
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
            if matches_ref_glob(name, publishable):
                continue
            reason = "outside the declared publishable allowlist"
        identity = f"{entry['authorname']} {entry['authoremail']}".strip()
        objecttype = entry.get("objecttype", "")
        if objecttype in ("blob", "tree"):
            # Ancestry is not a question that can be asked of these. Asking it
            # anyway exited 128, and 2.1.1 rendered that as the definite
            # sentence "CARRIES OBJECTS THE PUBLIC REF DOES NOT".
            containment = NOT_APPLICABLE
        else:
            try:
                answered = gitread.is_ancestor(repository, entry["objectname"], public_ref)
            except Exception as exc:
                # Not knowing is not "not contained". An unanswerable ancestry
                # question must not render as the reassuring answer — nor as the
                # alarming one, which is still a claim nobody established.
                report.could_not_check.append(
                    f"ancestry of {name} against {public_ref}: {exc}"
                )
                containment = UNKNOWN
            else:
                containment = CONTAINED if answered else NOT_CONTAINED
        report.findings.append(RefFinding(name, reason, identity, containment, objecttype))

    if human_identities:
        report.identity_findings.extend(
            _identity_findings(repository, public_ref, human_identities, report)
        )

    report.config_notes.extend(_config_notes(repository, report))
    return report


def matches_ref_glob(refname: str, globs: tuple[str, ...]) -> bool:
    """Whether a refname matches a declared ref glob, under **git's** semantics.

    Not `pathmatch`. A refname is not a filesystem path, and the difference is
    load-bearing: in a git refspec `*` crosses `/`, so `refs/heads/*` covers
    `refs/heads/feature/x` — which is exactly what a push with that refspec
    would carry. Borrowing the gitignore matcher here would report every nested
    feature branch as an unrecognised namespace, which is both wrong and noisy
    enough to train a reader past the findings that matter.

    A project that publishes only one branch says so: `["refs/heads/main"]`.
    """
    return any(fnmatch.fnmatchcase(refname, glob) for glob in globs)


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


def check_push_command(
    command: str,
    *,
    publishable_branches: tuple[str, ...] = (),
    expected_remote: str | None = None,
) -> list[str]:
    """Every reason this push command is not the supported publication form.

    The supported form is exactly `SUPPORTED_PUSH_FORM`: `git push`, one remote,
    one refspec whose source and destination are the same branch, and no other
    token. It is supported because it is *structurally* safe — it cannot carry
    `refs/notes/*` regardless of what the namespace holds at that instant — so
    it does not depend on winning a race against a writer that re-creates refs
    in under a minute.

    This check is a **whitelist of one shape**, and RP2.1.1 rewrote it as one
    after the previous blacklist was falsified five ways by execution. It
    accepted ``git log refs/heads/main:refs/heads/main`` (any command at all,
    provided a refspec-shaped token appeared somewhere in it), a second refspec
    alongside the first, a destination branch different from the source, a
    remote nobody declared, and a trailing ``--receive-pack=…``. Each was
    reported as "an explicit single-branch refspec, which cannot carry
    refs/notes/*" — a sentence about a command that was not being run. A gate
    that enumerates bad forms passes everything its author did not think of;
    one that names the single good form does not.
    """
    problems: list[str] = []
    tokens = command.split()

    for flag, why in FORBIDDEN_PUSH_FORMS:
        if flag in tokens:
            problems.append(f"{flag} is forbidden: it {why}")

    if tokens[:2] != ["git", "push"]:
        problems.append(
            f"the command is not a push: expected {SUPPORTED_PUSH_FORM!r}, got {command.strip()!r}"
        )
        return problems

    rest = tokens[2:]
    options = [token for token in rest if token.startswith("-")]
    for option in options:
        if not any(option == flag for flag, _ in FORBIDDEN_PUSH_FORMS):
            problems.append(
                f"{option!r} is not part of the supported form: any option can change what the "
                f"push carries or where it lands. The whole form is {SUPPORTED_PUSH_FORM}"
            )

    positional = [token for token in rest if not token.startswith("-")]
    refspecs = [token for token in positional if ":" in token]
    remotes = [token for token in positional if ":" not in token]

    for spec in refspecs:
        if "*" in spec:
            problems.append(
                f"wildcard refspec {spec!r} is forbidden: it carries whatever the namespace holds"
            )

    if len(refspecs) != 1:
        problems.append(
            f"{len(refspecs)} refspecs; the supported form carries exactly one. "
            "A bare `git push` publishes whatever the branch's upstream names, and a second "
            "refspec publishes a ref nobody judged"
        )
    if len(remotes) != 1:
        problems.append(
            f"{len(remotes)} non-refspec positional tokens; the supported form names exactly one "
            f"remote. Extra positionals alter the publication set: {positional!r}"
        )
    if expected_remote is not None and remotes[:1] != [expected_remote]:
        problems.append(
            f"the push names remote {(remotes[:1] or ['<none>'])[0]!r}, expected {expected_remote!r}"
        )

    if len(refspecs) == 1 and "*" not in refspecs[0]:
        spec = refspecs[0]
        if not _PUSH_REFSPEC.match(spec):
            problems.append(
                f"{spec!r} is not a refs/heads/<branch>:refs/heads/<branch> refspec; tags, notes "
                "and abbreviated names are all outside the supported form"
            )
        else:
            source, _, destination = spec.partition(":")
            if source != destination:
                problems.append(
                    f"{spec!r} publishes {source} as {destination}: source and destination must be "
                    "the same ref, or the remote carries a branch whose name nobody reviewed"
                )
            if publishable_branches and not matches_ref_glob(source, publishable_branches):
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
    # An expectation with no revision cannot detect the case this check exists
    # for. The RP2.1.0 CLI passed `{public_ref: ""}` and every caller inherited
    # it, so a remote still carrying last week's commit under the right name
    # returned "namespace matches what was published". Refused, not tolerated:
    # after a push the local revision is known, so there is no honest caller
    # that does not have it.
    for name, wanted in sorted(expected.items()):
        if not wanted.strip():
            problems.append(
                f"the expectation for {name} carries no revision, so a stale remote would pass; "
                "supply the exact revision that was pushed"
            )
    if problems:
        return problems

    # No declared negative: `ls-remote` printing nothing and exiting 0 is the
    # "no refs" answer, so every non-zero status here means nobody looked.
    answer = gitread.probe(
        repository, "ls-remote", remote, negative_statuses=(),
        allow_transports=REMOTE_VERIFICATION_TRANSPORTS,
    )
    if not answer.answered or not answer.ok:
        # The detail is part of the finding, not decoration. Without it a
        # refused transport and a host that does not resolve are the same
        # sentence — "git invocation failed" — and one is a setting this pack
        # controls while the other is the network. A reader who cannot tell
        # them apart cannot act on either.
        because = f"{answer.cause}: {answer.detail}" if answer.detail else answer.cause
        return [f"the remote {remote!r} could not be read, so publication is unverified: {because}"]

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
        if not _same_revision(sha, wanted):
            problems.append(f"{name} is at {sha[:12]} on the remote, expected {wanted[:12]}")
    for name in expected:
        if name not in seen:
            problems.append(f"the remote does not carry {name}, which the push was supposed to create")
    return problems


def expectation_from_refspec(refspec: str, revision: str) -> dict[str, str]:
    """The refs a push was authorised to create, derived from the refspec it used.

    Derived rather than hand-typed. A hand-authored expectation set is the shape
    the checker-hygiene rules refuse in terms — *never hand-type an identifier a
    mapping already holds* — and the mapping here is the refspec, which the push
    form already constrains to exactly one source and one destination.

    A push whose form is not the supported one has no derivable expectation, and
    is refused rather than given a guessed one.
    """
    if not _PUSH_REFSPEC.match(refspec.strip()):
        raise PreconditionError(
            "an expectation is derived from the authorised refspec, and this is not the "
            f"supported push form ({SUPPORTED_PUSH_FORM})",
            refspec=refspec,
        )
    if not _FULL_OBJECT_NAME.match(revision.strip().lower()):
        raise PreconditionError(
            "the expectation carries the exact revision that was pushed; without it a remote "
            "still holding last week's commit under the right name verifies clean",
            revision=revision,
        )
    _, _, destination = refspec.strip().partition(":")
    return {destination: revision.strip().lower()}


def _same_revision(left: str, right: str) -> bool:
    """Whether two revisions are the same full revision.

    `ls-remote` always answers with full object names and the caller always has
    the local one, so there is no case here that needs abbreviation tolerance —
    and tolerating it is how a comparison starts accepting prefixes short
    enough to match by accident.
    """
    left, right = left.strip().lower(), right.strip().lower()
    if not _FULL_OBJECT_NAME.match(left) or not _FULL_OBJECT_NAME.match(right):
        return False
    return left == right


def _cli(argv: list[str]) -> int:
    """Enumerate a repository's ref namespace and judge a publication.

    Usage: ``publication_gate.py REPO --public-ref REF [--project PATH]
            [--publishable GLOB ...] [--author IDENTITY ...]
            [--push-command "git push ..."] [--remote NAME]
            [--verify-remote NAME]``
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
    parser.add_argument("--remote", metavar="NAME", help="the remote the push command must name")
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
        problems = check_push_command(
            args.push_command,
            publishable_branches=publishable,
            expected_remote=args.verify_remote or args.remote,
        )
        if problems:
            failed = True
            print("push form: REFUSED")
            for problem in problems:
                print(f"  {problem}")
        else:
            print(f"push form: exactly {SUPPORTED_PUSH_FORM}, which cannot carry refs/notes/*")

    if args.verify_remote:
        # The expectation is the local public ref, resolved here. Passing an
        # empty one — which this CLI used to do — asks only "does a ref with
        # that name exist", which a remote stuck on an older commit answers
        # yes to.
        local = gitread.probe(repository, "rev-parse", "--verify", f"{public_ref}^{{commit}}")
        if not local.answered or not local.ok:
            failed = True
            print(f"remote {args.verify_remote}: POSTCONDITION FAILED")
            print(f"  {public_ref} could not be resolved locally, so there is nothing to compare "
                  f"the remote against: {local.cause}")
        else:
            problems = verify_remote(
                repository, args.verify_remote, expected={public_ref: local.value.strip()}
            )
            if problems:
                failed = True
                print(f"remote {args.verify_remote}: POSTCONDITION FAILED")
                for problem in problems:
                    print(f"  {problem}")
            else:
                print(
                    f"remote {args.verify_remote}: carries {public_ref} at "
                    f"{local.value.strip()[:12]} and nothing else"
                )

    return 1 if failed else 0


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
    from publication_gate import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
