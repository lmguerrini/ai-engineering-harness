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
    never replaces the universal rules below with it.
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
exemption, it is a hole.
