# Public-safe by construction

The invariant: no private information ever enters version-control history —
**even if the eventual repository is private.** Private is an access control,
not a property of the content, and access controls change.

## What must never be committed

Credentials and tokens. Absolute filesystem paths naming a machine or an
account. Personal identifiers. Prompts and conversations. Runtime databases and
session state. Model usage and quota history. Worker-performance and routing
history. Logs carrying any of the above. Datasets not explicitly cleared.

## Two rule sets, and why the distinction matters

*   **Vocabulary rules** are a project's own declaration of what is private to
    it. They are project-specific by nature: a harness names harness concepts
    throughout its source and is right to, while the same words in a product's
    history would be orchestration leaking out. The pack's own default set is
    `policy/private-terms.default.json`; a project extends it in PROJECT.yaml,
    never replaces the universal rules below with it. Pass `--project` and each
    tool reads that declaration itself: a rule set retyped as a flag is one that
    can be forgotten, and forgetting it produced `clean` over a range holding
    seven leaks.

    **Test a term against your own tree before adopting it.** Private
    vocabularies are chosen by process people and collide with domain
    vocabularies chosen by nobody — a project declared `bootstrap` and its own
    domain use of the word tripped the gate. Prefer multi-word terms
    (`runtime pack`) over single common words. The asymmetry matters: a term
    that is too broad produces noise that pressures a team into exempting whole
    directories, which is worse than a term that is slightly too narrow.
*   **Universal rules** — credentials, machine paths, generated identifiers —
    hold for every project, because what they find is private whoever wrote it.

Keeping them separate matters because the exemption a repository legitimately
needs for the first is not an exemption it may take for the second. A project
whose product is a harness cannot scan its own source for harness vocabulary;
that is not a reason to stop scanning it for credentials, and writing the
exemption as "skip blob content" takes both out at once.

## Paths travel further than contents

A file's *path* is visible in listings, in diffs, in error messages and in
anything that indexes a repository. A private identifier in a directory name is
the same leak as one in a commit message, and it is harder to notice.

## Before a first remote

The gate is not "does the head look clean". It is, applied by the `outgoing-scan`
toolbelt check over the full outgoing range, at capability close and again
before any push:

*   the universal rules, over the **entire** outgoing history including blob
    content;
*   commit messages, author and committer identities, ref and tag names;
*   ignored, untracked and generated artifacts classified by `workspace-report`;
*   the README read as a stranger would read it;
*   and an explicit human authorization, separately — HITL row 2.

Exceptions are recorded by exact object identity, with a note saying what was
read and why it is safe. An exemption that names a *class* of check is not an
exemption, it is a hole. A content exemption is also **re-argued against real
bytes**: a capability whose mutation boundary includes an exempt path cannot
close without an evidence entry saying what actually landed there. Exemptions
are declared before the files exist and their scope grows silently otherwise.

**A blob finding is repaired by rebuilding the branch, not by amending.**
Amending moves only the tip, so when the same term is also in an earlier commit
the finding count drops and the range stays dirty — and a smaller number reads
as progress. The scan names how many distinct blobs of an offending path are
reachable; more than one means rebuild.

## A closure names a commit; a ref is what keeps it

Git keeps an object alive because a ref reaches it and for no other reason, so a
rebuild, a rebase or a squash can orphan a commit half a dozen records cite
while every citation goes on looking authoritative. A cited head can be
unreachable, or absent entirely, while records still cite it, and the window to
recover it is about a month, ending the instant anyone expires a reflog.
`tools/history_anchor.py` reads the project's own records and answers per
citation; an anchor is a ref, or a bundle **that has been verified**, because a
bundle nobody restored is a file. A rewrite emits an old-to-new revision map and
the check consults it, or the first rewrite makes every citation in the corpus
unresolvable at once.

## Publication is a ref-namespace contract

The history being clean is not the repository being publishable. `git log`,
`git status`, `git ls-files`, `git diff` and `git show` all read *branch
history*, and a repository can carry AI contribution attribution, private
orchestration identities and session identifiers in `refs/notes/*` while every
one of them reports clean. This is observed, not hypothetical.

**IDE and provenance services are a known class of external `.git` mutator.**
One writes notes refs, re-creates them within seconds of deletion, survives
history rewriting, and rewrites repository-local `.git/config` between sessions.
Deletion is therefore a race, not a control: safety cannot rest on the namespace
being clean at some earlier instant. It rests on four things together, checked
by `publication-gate` **in the same step as the push**:

    an allowed source ref  +  reachability  +  an exact push refspec
                           +  a remote postcondition verified after

Publish with `refs/heads/<branch>:refs/heads/<branch>` and nothing else — never
`--mirror`, `--all`, `--tags` or a wildcard `refs/*`, each of which carries
whatever the namespace holds at that instant. The full sequence, including the
bounded stop-clean-publish-verify-resume mode for a live writer, is
`templates/publication-gate.template.md`.

**A filesystem immutable flag is not a control against a live writer.** Making
`.git` or a ref file immutable (`chflags uchg` and its equivalents) looks like a
lock and is not one: the writer is a separate live process that can clear the
flag, recreate the path, or write before the flag is set, and a coordinator that
sets one has bought a belief rather than a guarantee. The same applies to any
in-repository control against an out-of-repository mutator. The guarantee stays
where it is checkable — **ref namespace + reachability + exact refspec + remote
postcondition** — and stopping the writer stays a human step (`hitl-matrix.md`).

**Never infer causation from configuration correlation.** Two sessions
identified the writer from `notes.rewrite*` settings that plausibly explained
the behaviour; an intervention test falsified it, the refs reappearing
with the config removed and no amend or rebase performed. Where
a safety decision rests on a causal claim, run the intervention when it is safe
to. Configuration is reported with its origin, never concluded from.
