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

## Tier 1 — the tiered rules, which are the ones that govern a project: **clean**

Every occurrence was resolved to the text that matched it, and the distinct
matched strings are these:

| matched | what it actually is | verdict |
|---|---|---|
| `"~/.`, ` ~/.`, `(~/.` | the tilde-home form, as in `~/.codex/` — it says a user has a home directory, which is true of every Unix machine, and names no user and no machine | not a leak |
| ` /nowhere/at/all` | a fixture path chosen because it does not exist | not a leak |
| `00000000-0000-4000-8000-000000000000` | the synthetic nil-ish UUID a negative test uses | not a leak |
| ` /tmp/s`, ` /tmp/x`, ` /tmp/o`, ` /tmp/out`, `"/tmp/r`, `"/tmp/a`, `"/tmp/x`, `"/tmp/report.md` | fixture temporary paths, no user component | not a leak |
| ` /absolute/path/to/.project_context` | literal placeholder prose in `templates/PROJECT.yaml.template` | not a leak |
| `>/tools/adapter_pin.py`, `>/tools/pack_migration.py` | the tail of `<pack-root>/tools/…` in that same template | not a leak |

**No occurrence at this tier names a person, a machine, an account, a session or
a credential.** The rule that produced most of them — `~/.` reads as a
home-rooted path — is deliberately conservative and is working as designed.

## Tier 2 — the strict rules with the pack's own vocabulary: **structural, and explained**

Reproduce by passing the default vocabulary as `--term` / `--pattern`
arguments; the scan then reports thousands of occurrences over the complete
reachable object set, dominated by the pack's own governance words —
`coordinator`, `hitl`, `claude`, `envelope`, `codex`, `harness`, `runtime pack`,
`task class` — plus the model-generation pattern.

**The credential-shaped tokens are the class worth naming separately, and every
one of them is a fixture.** Forty-one occurrences, in four objects:
`tools/tests/test_commit_gate.py`, `tools/tests/test_outgoing_scan.py` and
`tools/tests/test_publication_gate.py` — which exist to prove the scanner finds
this shape, so a repository where they were absent would be one where the check
was untested — and `docs/RP2.2-GATE.md`, whose single token is
`AKIAIOSFODNN7EXAMPLE`, the vendor's own published documentation example, and
which that record already adjudicated in the same terms. **No live credential
is present.**

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
