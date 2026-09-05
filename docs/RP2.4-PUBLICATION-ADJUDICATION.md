# The pack's own history, adjudicated

`PACK_MANIFEST.json` has carried, since 2.3.0, a limitation saying the pack's
complete reachable history holds occurrences that are **recorded as owed, not as
done**. This is the adjudication. It is owed before any first remote, and this
release still has none.

Reproduce either figure with the pack's own tool:

```bash
python3 tools/publication_history.py . --tiered     # the tier a governed project runs
python3 tools/publication_history.py .              # the strict tier, structural rules only
```

Neither figure is restated in a second place. `test_no_document_restates_a_count_of_things_the_repository_can_count` is why.

---

## Tier 1 — the tiered rules, which are the ones that govern a project

**One occurrence names a real machine account, and it is in history.** Blob
`36877b2a6b60c38e46f742ba83dfdc1ca6365fda`, a historical version of
`docs/WAVE-A-FINDINGS.md`, carries

    /Users/<the account this repository lives under>/.gitignore_global:60:*.jsonl

reachable from `refs/heads/evolution/rp2.4` — the release branch itself — and
from `evolution/rp2.2`, `evolution/rp2.3` and `refs/pre-amend/rp2.4`. The pack
knows the shape: an audit found this exact string, the **tree** was redacted to
`<home>` at RP2.2, and `test_no_tracked_file_carries_a_real_machine_path` was
added so the next one fails rather than ships. **The redaction does not reach
history**, and this document is explicitly about the complete reachable history.

**An earlier version of this document said no occurrence at this tier names a
person, a machine, an account, a session or a credential. That was false**, and
an independent reader falsified it by enumerating every matching string over
every reachable blob rather than reading the summary. It is corrected here
rather than softened: the claim was wrong in the one category the pack had
already cared enough about to redact and guard.

**It is remediable only by a history rewrite**, which is HITL rows 2 and 4, and
it is not taken. Nothing is published, so nothing is exposed; what was wrong was
the statement.

### The classes the tiered scan finds

**These are the classes, not the complete set of distinct strings.** An earlier
version presented the table as "the distinct matched strings are these", which
an independent reader falsified by recomputing them — there are far more, most
of them synthetic fixtures. A table that claims to be exhaustive and is not is
worse than one that says what kind of thing it lists, because the only thing a
reader wants from it is to know that the harmless ones are all of them.

| class | what it is | verdict |
|---|---|---|
| the tilde-home form (`~/.codex/`, `~/.claude/`) | says a user has a home directory, which is true of every Unix machine; names no user and no machine | not a leak |
| fixture paths that deliberately do not exist (`/nowhere/at/all`) | negative fixtures | not a leak |
| synthetic identifiers (`00000000-0000-4000-8000-000000000000`) | the nil-ish UUID a negative test uses | not a leak |
| temporary paths (`/tmp/...`, `/private/tmp/...`) | fixture scratch paths, no user component | not a leak |
| template placeholders (`/absolute/path/to/.project_context`) | literal prose in `templates/PROJECT.yaml.template` | not a leak |
| fragments of a documented form (`<pack-root>/tools/...`) | the tail of a path a document shows | not a leak |
| invented home directories (`/Users/alice/...`, `/Users/someone/...`) | scanner fixtures, exempted by name in the tree guard | not a leak |
| system paths (`/etc/passwd`, `/usr/bin/sandbox-exec`) | named in prose about sandboxing | not a leak |
| **the account this repository lives under** | **the historical blob above** | **a real occurrence, stated, not remediated** |

Enumerate them yourself rather than trusting this table:

```bash
python3 tools/publication_history.py . --tiered
```

## Tier 2 — the strict rules with the pack's own vocabulary: **structural, and explained**

Reproduce by passing the default vocabulary as `--term` / `--pattern`
arguments; the scan then reports thousands of occurrences over the complete
reachable object set, dominated by the pack's own governance words —
`coordinator`, `hitl`, `claude`, `envelope`, `codex`, `harness`, `runtime pack`,
`task class` — plus the model-generation pattern.

**The credential-shaped tokens are the class worth naming separately, and every
one of them is a fixture.** They appear in `tools/tests/test_commit_gate.py`,
`tools/tests/test_outgoing_scan.py` and `tools/tests/test_publication_gate.py` —
which exist to prove the scanner finds this shape, so a repository where they
were absent would be one where the check was untested — in `docs/RP2.2-GATE.md`,
whose token is `AKIAIOSFODNN7EXAMPLE`, the vendor's own published documentation
example, already adjudicated there in the same terms, and **in this document**,
which quotes that example and thereby adds occurrences of its own. **No live
credential is present.**

An earlier version of this paragraph gave a count. It was wrong by the time it
was committed, because writing it created the occurrences it was counting — the
pack's own rule about restating a figure the repository can compute, met by the
document that states the rule. Recount with the shipped scanner rather than
reading a number here.

**Everything else at this tier is the case `skills/core/public-safety.md`
describes, and it is a property of this repository rather than a defect in
it.** The strict tier exists
to apply bare common words to blob content; this repository's blob content *is*
the vocabulary those words come from, because its documentation is about them.
A repository whose subject is a private vocabulary cannot be scanned clean at a
tier designed to find that vocabulary in ordinary prose.

`policy/private-terms.default.json` states the measured rationale for the
tiering in its own `tiering_rationale` field: four findings, zero true
positives, one of which cost a history rebuild.

## What this settles, and what it does not

**Settled.** There is no unadjudicated release blocker in the pack's history.
Every tiered-tier occurrence is resolved above, and the strict-tier population
is accounted for by a structural property that is stated rather than discovered.

**Not settled, and not this release's to settle.** Whether this repository is
ever published at all. That is a founder decision about a repository whose
content is governance vocabulary, and it needs a publication profile — which
subset is published, at which tier, under which exemptions — rather than a
remediation list. `docs/RP2.4-GATE.md` records it as owed.

**Not attempted.** Remediating a historical object, which is a rewrite and
therefore HITL rows 2 and 4. The tool says so itself on every run:

> this is a finding list, NOT a remediation list.

## The current tree, which is where a guard can bite

History is scanned on demand; the working tree is checked every suite run.
`test_no_tracked_file_carries_a_real_machine_path` and
`test_no_tracked_file_carries_a_live_session_or_transcript_identifier` hold the
tree, and `commit_gate.py --range` holds every message in the 2.4.0 delta.
