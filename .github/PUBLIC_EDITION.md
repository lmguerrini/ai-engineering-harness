# About this public edition

`ai-engineering-harness` publishes the development history of Runtime Pack, the versioned core of the AI Engineering
Harness, from its first commit (2026-08-13) through the frozen **2.5.0** release (2026-09-10) and the **2.6.0**
development line that followed it, up to the checkpoint where that line was paused (2026-09-20). It was prepared from
the private canonical repository by a reviewed, deterministic history rewrite, followed by a small number of new
commits on each branch that add this documentation, update `.gitignore`, adapt the release self-checks to the
rewritten history and, later, rewrite the landing README and add its images.

## Branches

| Branch | Contents | State |
|---|---|---|
| `main` (default) | the history up to the 2.5.0 release commit, the nine commits of the 2.6.0 line, plus this edition's six commits | development HEAD: 2.6.0 `IN_PROGRESS`, paused at a checkpoint; not a release |
| `stable/2.5.0` | the history up to the 2.5.0 release commit, plus this edition's six commits | 2.5.0 `QUALIFIED_AND_FROZEN` — the latest stable release |

The two branches share the history up to the 2.5.0 release commit and diverge after it; there are no merge commits.
2.6.0 is published as development history. It is **not** a release: it is not qualified, not frozen and must not be
pinned or adopted.

## What was preserved

- **Every commit of the 2.5.0 line and of the canonical 2.6.0 line, in its original order** — 261
  commits up to 2.5.0 and 9 after it, 270 in all, each with its original parent (the first has
  none), no squashing, no reordering, nothing dropped from either line.
- **Original authorship, dates, times and time zones** of every historical commit: author and committer names,
  dates, times and time-zone offsets byte for byte; in both, the email is the author's GitHub noreply address in
  place of a personal address. New commits added for this edition carry their real dates.
- **The code, tests and records themselves.** Sanitization replaced text only in prose, comments, docstrings,
  fixture strings and free-text record fields. No executable logic was changed by the rewrite.

Not included: provisional worker-branch commits whose work was re-run and re-landed by the coordinator in the
canonical 2.6.0 commits (publishing them would duplicate that work), two commits superseded by amended versions of
themselves, and every other private ref, stash, note and unreachable object.

## What changed, and why

| Change | Scope | Reason |
|---|---|---|
| Commit messages normalised to Conventional Commits (`type(scope): subject` + 2–4 bullets) | all historical commits | one consistent, professional history; each message was rewritten from the original message and verified against its diff |
| Names and identifiers of the author's other private projects replaced by neutral pseudonyms (`consumer-a` … `consumer-d`, "Pilot Run Project") | every version of every file where they occurred, plus one template file name | those projects are private |
| Records about those projects — their domain, data, files, history, configuration, events and audit findings — reduced to what the pack did with them and, in general terms, the risks they exposed; where findings were dropped, the record says so | records, comments and docstrings | private project substance |
| One absolute home-directory path, one client session identifier, two branch names from another repository | historical versions where they occurred | machine, session and repository identifiers |
| Observed account-capacity snapshots generalised; two verbatim quotations of the author's instructions paraphrased | records | private operational data and prompts |
| Provider account specifics generalised: plan and billing details, account limits and reset times, references to private session records, and figures about what consuming projects did | the 2.6.0 line's decisions, designs, gate record, changelog, routing evidence and one test | private subscription and operational data |
| Author and committer email set to the author's GitHub noreply address | every commit | keeps a personal address out of the history; in the historical commits, names, dates, times and zones are unchanged |

Nothing else was rewritten. Vendor, model and gateway names that are publicly documented were kept.

## Identifiers in historical records

The rewrite gives every commit a new id, and sanitizing file contents changes release tree digests. **Commit ids,
tree digests and branch names quoted inside historical documents therefore refer to the private repository and do not
resolve here**, and a historical commit's `PACK_MANIFEST.json` does not verify against that commit's sanitized tree.
The public commits of each version are:

| Version | State | Public commit |
|---|---|---|
| 2.0.0 | superseded | `afd8fd546d25` |
| 2.1.0 | superseded | `1991a1431e5d` |
| 2.1.1 | QUALIFIED_AND_FROZEN | `271d10ee393a` |
| 2.2.0 | QUALIFIED_AND_FROZEN | `9b883f964bf7` |
| 2.3.0 | QUALIFIED_AND_FROZEN | `e96fc4e9ce01` |
| 2.4.0 | QUALIFIED_AND_FROZEN | `a0c8d9bc7a48` |
| 2.4.1 | never released (IN_PROGRESS) | `262ed9f9392b` |
| 2.5.0 | QUALIFIED_AND_FROZEN — latest stable | `c2fcf9cedf17` |
| 2.6.0 checkpoint | IN_PROGRESS — development, not a release | `b7f85623ebe7` |

On each branch, the first edition commit adds this documentation and names it where the pack's own release checks
require (the current version's changelog entry and the release README's repository tree). The second updates
`.gitignore` with rules for local environment, editor and tool state; it prevents future accidents and is not how the
history was sanitized. The third records the public tree's own digest and rebinds the machine-read revision
references — the release baseline the self-checks compare against, two test fixtures that name a release commit, and
the base revision each design record declares — to public commit ids. Prose references are left as they were written. The fourth (2026-10-16) rewrites the landing
README (`.github/README.md`) for first-time readers and updates this note; it records the tree's digest again and
changes no tool. On `main` only, it also adds the row for `design-falsification.md` that the skills index
(`skills/core/README.md`) had lacked since that skill arrived in 2.3.0, and raises the held-prose figure in the 2.6.0
gate record (`docs/RP2.6.0-GATE.md`) by the one line this adds, as the release checks require. The frozen 2.5.0 is
left as it was frozen, so the index on `stable/2.5.0` still lists 13 of its 14 skills.
Likewise, records that describe the private history — for example `docs/RP2.4-PUBLICATION-ADJUDICATION.md` and the
2.6.0 gate record, which report that a historical file there still names a real machine account — are true of the
private repository and were kept as written; in this edition that file was sanitized in every version. Three policy files (`policy/auditor-strategy.md`,
`policy/execution-boundaries.md`, `policy/routing-policy.md`) still open with the "Classification: PRIVATE" label
they carried in the private repository; they are published here as part of the engineering record, with the
operational figures they once held generalised. The fifth (2026-10-17) replaces the landing README's Mermaid
diagram with a static black-and-white drawing of the six roles, adds a drawing of the repository layout (both in
`.github/assets/`, and named in the current version's changelog entry as the release checks require), revises the
README for first-time readers, adds the section on timing-sensitive tests below, and records the tree's digest
again. The sixth (2026-10-18) redraws that diagram to the full width of the page, with narrower versions of both
drawings for phones; adds an illustration of the read-only dashboard, in greys with invented data; rewrites the
README's explanations for readers without a technical background, with a short list of key terms and a note on the
Git identity the test suite expects; names the new images in the changelog entry; and records the tree's digest
again. These commits change no tool.

The private repository's 2.5.0 range reported twelve commit-contract violations over four commits, and
`docs/RP2.5.0-GATE.md` keeps that record as it was written. After normalisation, the same range here reports:

    COMMIT CONTRACT OVER THE 2.5.0 RANGE: 0 VIOLATIONS OVER 0 COMMITS (STRICT); 0 VIOLATIONS OVER 0 COMMITS (DEFAULT VOCABULARY)

On the stable branch, `tools/tests/test_release_integrity.py` derives those figures from the history and checks this
sentence against them. On the development branch the same test measures the 2.6.0 range against its own gate record,
which states that the range reports no violation; it holds for the public messages too.

## Verification performed before publication

- History scanned in full (every object, message, identity, ref and path) by an automated scanner, and every line that
  ever existed in it read by fresh-context reviewers whose findings were adjudicated one by one; the 2.6.0 line was
  audited to the same standard, commit by commit. No credential was found at any point in the history
  (credential-shaped values in tests are published examples or synthetic fixtures).
- The rewrite was verified mechanically, commit by commit, on both lines: parents, author and committer identities,
  dates and time zones unchanged; every file equal to the declared transformation of its original; no extra or
  missing paths.
- The exported repository contains exactly the two branches above and no tags, notes, replacement refs, stashes or
  unreachable objects, and none of the original versions of any sanitized file.
- An independent review by a different vendor's model attempted to falsify all of the above.
- Before publication the complete history was audited again (2026-10-16): the strict publication gate, a second
  scanner written independently of the first, a check of every commit message, and fresh-context reviewers who
  read the records of both final trees, every line that exists only in earlier versions, and the comments, docstrings
  and string literals of the tool sources and tests. No blocker was found.
- The full test suite was run on the tip of each branch as it stood after the fourth edition commit (2026-10-16):
  stable branch 3,011 of 3,011 passed; development branch 3,317 of 3,319 passed and 2 were skipped by the line's own
  conditions; none failed; on macOS with Python 3.14.0 and Git 2.50.1. The fifth and sixth commits change no tool
  and no test.
  Two tests are timing-sensitive; see the next section.

## Known timing-sensitive tests

Two tests can fail by chance, on both branches: `test_disposition_orphaned_waiter`
(`tools/tests/test_background_governance.py`) and
`test_the_rehearsal_declares_its_background_work_and_reconstructs_it_cold` (`tools/tests/test_adoption_rehearsal.py`).
Each writes the file a wait is waiting for before it declares the wait. The pack records a declaration only to the
whole second, so when both steps fall within the same second the file does not look older than its wait and the test
passes. When a second boundary falls between them, the pack sees that the file is older than its wait, which it is,
and refuses it, correctly, answering `UNKNOWN` (`tools/continuation.py`: a path must not predate its own wait); the
test then fails. A heavily loaded machine makes this more likely.

While this edition was being prepared, on 2026-10-16, the full stable suite was started 21 times on its candidate
commits. Of the 19 runs that finished, 17 passed every test; the other two, on the same commit under Python 3.14 and
3.12, each failed one of these tests once, and when that commit was run again in full under both versions, all 3,011
tests passed each time.
One of the two runs that were stopped before finishing had also failed one of them. All 17 complete runs of the
development suite passed, and in isolation each of the two tests passed six times out of six.

The fault is in the tests' order of work, not in the pack. It is unresolved: the fix, declaring the wait before
writing the file, belongs on the development line, for a future release, and the frozen 2.5.0 is not changed after
its freeze. Until then, this section is where it is tracked.
