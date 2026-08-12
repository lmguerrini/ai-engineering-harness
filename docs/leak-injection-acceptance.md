# Leak-injection acceptance case (7 surfaces)

**Status:** Wave-A gate artifact. **Applied by:** COORDINATOR, at Wave-A close and
again as the Wave-B injected exercise. **Tool under test:** `tools/outgoing_scan.py`.

The public-safety gate is the pack's highest-value asset — it caught real leaks in
production, including its own repository's vendor-named paths. A gate that has
never been attacked is not a gate. This case attacks it on every surface it claims
to cover, and it must block **7 of 7**.

## Safety rules for this exercise

- **No real secret, credential, token, key, or personal datum is ever used.**
  Every injected value is synthetic and obviously so.
- The injection is performed on a **disposable fixture repository**, never on a
  real project and never on the frozen Kernel archive.
- The fixture branch is deleted after the exercise. Nothing is ever pushed —
  there is no remote to push to.

## The seven surfaces

Each row is a separate injection attempt. The scan must report the surface as a
finding and exit non-zero. A surface that passes silently is a Wave-A failure.

| # | Surface | Synthetic injection | Rule class |
|---|---|---|---|
| 1 | **Blob content** | a credential-shaped literal inside a tracked source file | universal — never exemptable |
| 2 | **File path** | a tracked file whose path contains a real machine home path component | universal — never exemptable |
| 3 | **Commit message** | a commit body naming a private orchestration path | universal + vocabulary |
| 4 | **Author / committer identity** | a commit whose author email is a non-project identity | universal |
| 5 | **Tag name and tag message** | an annotated tag whose message carries a private term | universal + vocabulary |
| 6 | **Ref name** | a branch name carrying a private operational term | vocabulary |
| 7 | **Generated identifier** | a UUID-shaped identifier committed inside a tracked file | universal |

## Required properties beyond "it blocked"

These are the two recorded fixes the scanner must demonstrate, and the tri-state
rule. They are as load-bearing as the seven blocks.

1. **The reviewed baseline is exempt from its own scan.** Record a match in the
   baseline file, then re-scan. The baseline must not trip on having recorded the
   match. (This exact loop cost real time in production.)
2. **Blobs enter the baseline at commit time**, not by re-walking all history
   inside a test. Assert the baseline is written on the commit path.
3. **Anything skipped yields `clean=False`.** A scan that could not read an
   object reports *not clean* — never *clean*. Absent ≠ zero; incomplete ≠ clean.
4. **Redaction does not reproduce the finding.** The report describes the match
   without writing the matched value into the file that records it. (This is what
   Kernel commit `042c1b9` was for; the property is carried, the code is not.)

## Verdict recording

Result goes to the capability's `evidence/` as a content-addressed file via
`evidence_put`, and one line to `policy/observations.jsonl`. A partial run is
recorded as INCOMPLETE, never as passed.
