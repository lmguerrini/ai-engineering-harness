# RP2.1.1 — gate record

**Date:** 2026-08-15. **Pack VERSION:** 2.1.1. **State:** QUALIFIED_AND_FROZEN.
**Assessed by:** COORDINATOR, by execution, single session, zero delegation.
Every claim below was re-run before it counted.

Baseline: VERSION `2.1.0`, HEAD `c400e3c`, working tree clean including
untracked files, no remote, no tag, `refs/heads/main` the only ref, **175 tests
passing**. Final: **237 tests passing**, +62.

**Trigger.** An independent cross-vendor audit of the frozen 2.1.0 release
returned NOT_READY on release integrity. That audit was treated as **input, not
truth**: every material claim was reproduced mechanically against pack source
before anything was changed, and one was rejected on reproduction (below).

**Scope.** A PATCH release (`DECISIONS.md` D11) — backward-compatible fixes,
metadata corrections, and enforcement of guarantees 2.1.0 already promised. No
new capability, no architecture change, no contract migration. `DECISIONS.md`
D1–D10 are untouched and were not reopened.

## Why the qualified revision is not printed here

A gate record cannot name the commit that contains it, for the same reason a
manifest cannot contain its own hash. The release identity is **version +
revision + digest**: `VERSION` and `PACK_MANIFEST.json` carry two of the three
in-tree, and the revision is observed at freeze and recorded by each consuming
project in its `PROJECT.yaml` `pack.sha_adopted`. The digest already pins tree
*content* exactly; the revision adds provenance. Verify all three at once:

```bash
python3 tools/pack_pin.py . --version 2.1.1 --sha <full 40-char revision> \
    --digest <PACK_MANIFEST.json tree_digest_sha256> --state QUALIFIED_AND_FROZEN
```

## Reproduction before repair

Nine finding families were reported. Each was reproduced by execution against
the 2.1.0 tree at `c400e3c` before any file was edited.

| # | Claim | Verdict | How it was reproduced |
|---|---|---|---|
| D1 | Release identity drift | **CONFIRMED** | `README.md:1` read `# Runtime Pack 2.0` under `VERSION` 2.1.0; `CHANGELOG.md:8` and `PACK_MANIFEST.json:11` recorded 167 where `pytest -q` returned **175 passed** and `docs/RP2.1-GATE.md` said 175 throughout; no machine-readable state field existed |
| D2 | `pack_pin.py` false confidence | **CONFIRMED, 6 of 6** | executed, all six accepted: `--sha` of one character; manifest `version` 9.9.9 against `VERSION` 2.1.0; an untracked `SMUGGLED.py` present; `sha256("ab"+"c") == sha256("a"+"bc")`; `a file.md` enumerated as `['a', 'file.md']` then `FileNotFoundError`; `tests.passed` 99999 with a nonexistent `gate_record` |
| D3 | Publication-gate exactness | **CONFIRMED, 5 of 5** | executed, all accepted: `git log refs/…:refs/…`, `rm -rf / refs/…:refs/…`, a second refspec under the default allowlist, `main:other`, `--receive-pack=…`. The empty remote expectation is at `publication_gate.py:425` and skipped at `:349` |
| D4 | EC-S / EC-X contradictions | **CONFIRMED, 3 of 4** | `audit-strategy.md:7-8` vs `:23-24`; `audit-brief.template.md:18` vs `:37-38`; the same file's mandatory reviewer worktree vs `worker-contract.md:50`. **`worker-contract.md` itself was already correct** — its durable-file rule was conditioned in 2.1.0 |
| D5 | EC-U silently unimplemented | **CONFIRMED** | `grep -rniE "chflags\|uchg\|immutable flag\|schg"` over the whole pack returned exactly one hit: the delta-audit row saying IMPLEMENT_NOW |
| D6 | Multi-project pinning incomplete | **CONFIRMED, 3 of 3** | `PROJECT.yaml.template:16-18` carried `version_adopted` alone; bootstrap:132 gave an out-of-envelope skill authority over the pinned pack; `BUDGETS.md:56` pointed at `policy/overhead-measurements.md`, which does not exist |
| D7 | Stale routing grade | **CONFIRMED** | `auditor-strategy.md:38-40` asserted both audit roles `unprobed`; `routing-table.md:24-25` graded both `confirmed` from the same evidence log |
| D8 | Version semantics not cold-readable | **CONFIRMED** | no PATCH/MINOR/MAJOR statement anywhere in the tree |
| D9 | Held-prose count mismatch | **CONFIRMED** | `wc -l` under the rule `BUDGETS.md` declares: **2,256**, not the recorded 2,204 |

**Rejected on reproduction:** the read-only durable-output contradiction was
reported against `skills/core/worker-contract.md`, which already carried the
conditioned rule ("This applies to mutating dispatches only") from 2.1.0. The
contradiction was real but lived in three *other* files. Repairing the file
named would have closed nothing.

**Also verified before repair:** 175 tests collected and passed; 84 tracked
files, 83 under the digest, matching the manifest; the recorded digest
recomputed and `pack_pin.py . --version 2.1.0 --sha <HEAD>` exited 0; all 32
EC-A…EC-AF dispositions present in `docs/RP2.1-DELTA-AUDIT.md`; and — checked
one candidate at a time — **EC-U is the only IMPLEMENT_NOW candidate with no
implementation at all**, with EC-S and EC-X landed in Core and missed in the
templates.

## Gate conditions

| # | Gate condition | Result | Evidence |
|---|---|---|---|
| 1 | All tests green | GREEN | `python3 -m pytest tools/tests/ -q` → **237 passed**, and again from a clean clone into a scratch directory |
| 2 | Collection is unfiltered and matches the manifest | GREEN | `--collect-only -q` → 237, compared to `tests.passed` by `test_release_integrity.py`, in a subprocess, at every run |
| 3 | Every tool standalone, imports contained | GREEN | 10 tools run `--help`; stdlib + `tools/` siblings only |
| 4 | No stateful authority reintroduced | GREEN | no component added; `pack_pin` and `publication_gate` still report and refuse |
| 5 | No Git write verbs added | GREEN | `pack_pin` gained `ls-files --others --exclude-standard` and `-z`; `publication_gate` gained `rev-parse --verify`. All read |
| 6 | Pack-pin falsification | GREEN | 30 tests; **every case the 2.1.0 verifier accepted now fails**, including the ones that motivated it |
| 7 | Publication-gate falsification | GREEN | 48 tests; 14 previously-accepted push forms refused, plus an end-to-end stale-remote case |
| 8 | Release integrity against the **real** repository | GREEN | 18 tests reading this checkout, not a fixture — the surface that was green while `README.md` said 2.0 |
| 9 | Commit-range drift regression | GREEN | `validate_range` shipped in 2.1.0 with a measured result and **zero tests**; 4 now, on a branch whose drift point is known |
| 10 | Manifest domain, NUL-safe | GREEN | `git ls-files -z` → **86** tracked, **85** digested, manifest excluded and recorded as excluded. Baseline was 84/83 |
| 11 | Digest independently recomputed | GREEN | recomputed by a separate implementation written from the docstring, not by calling `tree_digest` — see below |
| 12 | Clean-clone qualification | GREEN | `git clone` into a scratch path, suite green, `pack_pin` verified there |
| 13 | README tree matches the tracked tree | GREEN | every path the tree claims is parsed back out by depth and checked to exist; every tracked top-level directory appears |
| 14 | The pack's own ref namespace | GREEN | `refs/heads/main` only. No remote, no tag, nothing pushed (D5) |
| 15 | Derived views are not authority | GREEN | the duplicated grade deleted from `auditor-strategy.md`; `routing-table.md` regenerated from all 19 observations, unchanged in content |
| 16 | Held prose measured, not re-scoped | **QUALIFIED — over, recorded** | see below |

## Gate 11 — the digest, recomputed by different code

The 2.1.0 manifest's defect was that the record was written by different code
than any code that would check it. The repair — one function serving both — has
the mirror risk: a single implementation is self-consistent by construction and
would agree with itself even if the framing were wrong. So the digest was
recomputed at qualification by a **separate implementation written from the
docstring**, in a scratch script that does not import `pack_pin`, and the two
values compared. They match.

## Gate 16 — held prose, measured and over

    skills/core/*.md + policy/*.md                    inside the release   1,301
    + the two installed adapter skills                outside it             997
    ------------------------------------------------------------------------------
    total under the rule BUDGETS.md declares                               2,298
    target                                                                ~2,000

**14.9% over.** 2.1.0 recorded 2,204 under a rule that actually yielded 2,256;
the figure had never been recomputed. It is recorded, not shaved, and the
counting rule is **unchanged** — re-scoping the rule to fit the number is the
move `docs/RP2.1-GATE.md` explicitly declined, and it would be worse here
because the number is the disclosure.

Deletions were taken first: the duplicated routing grade in
`policy/auditor-strategy.md` and the reviewer-worktree rationale duplicated
between `worker-contract.md` and the audit brief. Net additions are the EC-U
lesson (7 lines), the conditioned capture-channel rules, and the pin semantics.

**997 of the 2,298 lines are outside the release envelope** — the two installed
skills are adapters the pack can measure and cannot freeze (`DECISIONS.md` D12).
The in-envelope figure, 1,301, is the part a pinned release actually governs.

## What this release does not do

- **It does not rewrite history.** `docs/RP2.1-GATE.md` and
  `docs/RP2.1-DELTA-AUDIT.md` are left exactly as written, including the figures
  this release corrects. A gate record describes the pass that produced it;
  correcting one after the fact destroys the evidence that the drift happened.
  The corrections are in `CHANGELOG.md` as errata against 2.1.0.
- **It does not change a routing grade.** No observation was added, removed or
  re-graded. `policy/observations.jsonl` is byte-identical at 19 rows.
- **It does not reopen a disposition.** EC-O and EC-T stay deferred with their
  triggers; EC-Z stays rejected for Core.
- **It creates no tag and pushes nothing.** D5 is unchanged.

## Budgets consumed

    implementation passes                1 of 1
    qualification repair passes          1 of 1  (2 findings, both in this pass's own work)
    final verification pass              1 of 1
    HITL stops                           0  (none genuine; none false)
    delegated dispatches                 0  (single coordinator, by instruction)

Both qualification findings were in this pass's own work and both came from
executing it: a `pack_pin` test asserted a fabricated test count would be
refused, which is outside that tool's domain — the boundary is now stated and
tested — and a `VERSION`-absent case was asserted against the wrong failure
path. The pack's central claim about green meaning "no known defect" reproduced
on the pack for a fourth wave running.

## Still deferred, unchanged

- **EC-O** (machine-path rule fires on fixed platform locations) — trigger: a
  second project blocked by it where the workaround is not better engineering.
- **EC-T** (certify a binary rather than exempt it) — trigger: a project
  shipping enough unscannable blobs that the exemption total stops being
  readable.
- **EC-Z** — rejected for Core; a project-code lesson.

## Known limitations carried into 2.1.1

- Held prose is 14.9% over target, 997 lines of it outside the release envelope.
- Installed adapter skills are outside the digest by construction. The boundary
  is now stated (D12) rather than closed; closing it means vendoring them, which
  is a MINOR change and is not this release.
- Relative *yield* between AUDIT_PRIMARY and AUDIT_CROSS is still unmeasured.
  Three audits is not a rate.
- **No durable routing evidence exists for any configuration beyond the 19
  recorded observations.** Where a family has not been dispatched under this
  pack, the record says `unprobed` and no observation was invented to fill it.
