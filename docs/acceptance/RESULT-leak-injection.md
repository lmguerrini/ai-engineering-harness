# Leak-injection acceptance — RESULT

**Date:** 2026-08-13. **Instrument:** `docs/acceptance/inject_7_surfaces.py`
(coordinator-authored, not authored by the worker that extracted the scanner).
**Tool under test:** `tools/outgoing_scan.py`. **Verdict: 7 / 7 BLOCKED.**

## Result

Two scans were required, because an annotated tag object only enters an outgoing
range when the tag ref itself is scanned. Both exited non-zero.

| # | Surface | Rule class | Reported as | Blocked |
|---|---|---|---|---|
| 1 | blob content | universal / credential shape | `blob config.py: credential-shaped token (aws access key)` | yes |
| 2 | path name | vocabulary / private term | `path runtime-pack-internal/notes.txt` | yes |
| 3 | commit message | universal / machine path | `commit_message 823973362838: a local filesystem path` | yes |
| 4 | author + committer identity | vocabulary / private term | `author …` and `committer …` | yes |
| 5 | tag name + tag message | universal + vocabulary | `tag_name`, `tag_message` ×2 | yes |
| 6 | ref name | vocabulary / private term | `ref_name feature/…` | yes |
| 7 | generated identifier | universal / UUID shape | `blob session.json: a UUID-shaped private identifier` | yes |

Exit status 1 on both runs. 7 findings on the branch ref, 10 on the tag ref.

## Redaction property — verified

Every private-term finding is rendered `declared private term 'r**********k'`.
The report **describes the match without reproducing it** in the file that
records it. This is the property Kernel commit `042c1b9` existed to establish;
the property is carried, the Kernel code is not.

## The instrument was wrong first, and that is the finding worth keeping

The first draft of this acceptance case reported **2 / 7** and was wrong on five
surfaces. Every one of those five was a defect in the *instrument*, not the tool:

- the synthetic AWS key was malformed — `AKIA` + 19 characters, where the real
  shape is `AKIA` + exactly 16, so the trailing word-boundary never matched;
- the "machine path" was injected as a *repository-relative* path, which can
  never be machine-rooted — the rule class that applies to a path name is the
  vocabulary rule, not the machine-path rule;
- the "foreign identity" was a neutral e-mail address naming nothing private.
  Blocking it would have been a **false positive**, not a catch;
- the branch name was never scanned because the run passed `HEAD`, which the
  scanner deliberately declines to treat as a name;
- the tag object was never enumerated because the run scanned the branch, not
  the tag.

**An injection that falls outside every rule class does not test the gate; it
tests the test.** This is the same failure the whole pivot is about, in
miniature: a domain derived from the wrong abstraction, producing a confident
red where the mechanism was never reached. It is recorded here rather than
quietly fixed, because the corrected instrument is only trustworthy if the
correction is visible.

Coordinator note: the initial run also appeared to exit 0. It did not — the
exit status being read was `head`'s, downstream of a pipe. Verified separately.

## Properties still to verify at the Wave-A gate

- reviewed baseline is exempt from its own scan;
- blobs enter the baseline at commit time, not by re-walking history in a test;
- anything skipped yields `clean=False`.
