# Founder authorisations for RP 2.4.0

Three decisions in this release are the founder's rather than this work's. Two
were granted in the pilot-run directive and are recorded here with the
conditions they carry. The third is not granted and is listed so that a reader
cannot mistake this document for a freeze.

Each authorisation names **what was authorised**, **what was not**, and **where
the condition is checked**. Conditions recorded only as prose are conditions
nobody will notice being broken, so every condition below that can be executed
is executed by `tools/tests/test_founder_authorisation.py`.

---

## 1. The history repair — GRANTED, and taken

**What was authorised.** The minimal history rewrite required to repair the one
local, unpushed commit whose message this pack's own gate refused: amend that
message, preserve the tree exactly, no squash, no rebase of unrelated commits,
no reorder, nothing else rewritten, no push, no tag, no publication, no remote
mutation, no consumer migration.

**What was done.** The offending message carried a private term because the
commit was created by a shell chain whose `&&` attached to `tail -1` rather than
to the gate — the gate ran, printed `VIOLATION`, exited non-zero, and the commit
happened anyway. The corrected message differs from the original in **one
phrase**; the rest is byte-identical.

The repair was performed with `git commit-tree` rather than `rebase`, so each
commit's tree object was **reused rather than reconstructed from a re-applied
diff**:

| | before | after |
|---|---|---|
| offending commit | `62386d4b26f32130af6edda8bd33a9e19e4f2ffe` | `5069b1c2af477120973deb1a3c594d14727d72a4` |
| its tree | `dc0b5ac108ad5fd4dbf94a4834854d00b2d183f9` | `dc0b5ac108ad5fd4dbf94a4834854d00b2d183f9` |
| child commit | `11dad7464221577dd6c7552a83f6813752c5d0e0` | `1dd2aa93ef89f0ea280f7565f353e6bc8327ee42` |
| its tree | `be8aaefe7e226e94bc3c379be8c8dec5c7712b4e` | `be8aaefe7e226e94bc3c379be8c8dec5c7712b4e` |

The child's identifier changed because a commit names its parent; its message
and its tree did not. Ten commits before, ten after, same order.

**Verified by execution, and reproducible:**

```
# PINNED TO THE AMEND, not to HEAD. Written against HEAD, these stopped
# reproducing the moment the next commit landed — a reader following them saw
# 25 files changed and concluded the repair had altered content. An independent
# reader ran them and reported exactly that.
git diff 11dad7464221577dd6c7552a83f6813752c5d0e0 \
         1dd2aa93ef89f0ea280f7565f353e6bc8327ee42 --stat    # empty: no content differs
git rev-list --count ab7dea97..1dd2aa93                     # 10, unchanged
git rev-parse 62386d4b^{tree} 5069b1c2^{tree}               # one tree, reused
git rev-parse 11dad746^{tree} 1dd2aa93^{tree}               # one tree, reused

# and the property that must hold at every later revision:
python3 tools/commit_gate.py --range HEAD --baseline ab7dea97 --repo . --default-terms .
```

The last of those printed one `VIOLATION` before the repair and
`VALID every commit message in ab7dea97..HEAD conforms` after it.

**The old identifier ceases to be authoritative.** It is retained as
`refs/pre-amend/rp2.4` in this working repository only, so that the amend is
itself auditable, and is not part of the release.

---

## 2. The row-7 governance narrowing (D26) — GRANTED, with ten conditions

**What was authorised.** The narrowing described in the audited proposal, now
recorded as `DECISIONS.md` D26. `policy/hitl-matrix.md` row 7 states its
application point as *before* any entry lands in `DECISIONS.md`; the
authorisation was given before this entry was written, which is that point.

**What was explicitly not authorised: broadening it.** The founder's instruction was
to promote only the already-designed semantics and not to broaden them, and the
entry in `DECISIONS.md` is the audited text with one sentence changed — the one
that said the narrowing was not yet authorised.

**The invariant the authorisation rests on:**

> (paraphrased) A newly discovered model or configuration does not inherit
> qualification merely because its family has prior evidence.

**The ten conditions, and where each is executed.** Every one of these is a
behavioural oracle. None reads this document, because a test that reads the
document authorising it agrees with it by construction.

| # | Condition | Oracle |
|---|---|---|
| 1 | dynamic discovery, no frozen model allowlist | `test_1_*` — an unseen identifier survives discovery; no Core module names a model |
| 2 | a newly discovered configuration begins `unprobed` | `test_2_*` |
| 3 | family history is advisory prior only | `test_3_*` — a confirmed family leaves a new model `unprobed`, with the prior visible |
| 4 | family history is never silently converted into a track record | `test_4_*` — the prior names itself; a declared alias moves no grade |
| 5 | `UNKNOWN` or unobserved identity cannot positively qualify | `test_5_*` — parametrised over all eight dimensions and every unobserved provenance marker, plus the backend record that returned `True` |
| 6 | the execution surface outranks the worker's self-report | `test_6_*` — over the dataclass **and** over the parser a real log row goes through |
| 7 | availability and qualification are separate axes | `test_7_*` — parametrised over all three purposes, probe included |
| 8 | the governed dimensions stay governed | `test_8_*` — the nine are written out rather than imported, and each is shown to separate two configurations |
| 9 | pooling stays bounded to `build` and `pool_id` | `test_9_*` — the pair is written out; a third field fails the suite |
| 10 | audit independence constraints intact | `test_10_*` — producer, session, provider, probe-in-a-mandatory-leg, and both directions of the key-equality error |

**Mutation evidence.** Fifteen well-formed mutants, each broadening D26 past
what was authorised, were applied to the subject and run against these oracles.
All fifteen were killed; none survived; none was ill-formed. Two survived a
first pass and both were **gaps in the oracle rather than in the subject** —
one tested the dataclass while the mutant was in the parser, and one tested only
`ROUTINE` where a second availability check masked the change. Both are now
covered, and the reason is written into the tests so the next reader does not
have to rediscover it. The harness is
`scratchpad/mutate_authorisation.py`, retained outside the release.

**What this authorisation does not settle.** Rows 12 and 16 keep their human.
D26 strengthens them in the direction they already point — the evidence behind a
critical-domain promotion is now per-configuration rather than per-family — and
an unavailable qualified worker is still never authorization to use an
unqualified one.

**Reverses on** what the decision says it reverses on: an A/B pair showing a
client version changing what a configuration can do, or an adopting project
finding the key so fine-grained that every real dispatch is a probe.

---

## 3. The freeze (row 2) — NOT GRANTED

The state transition to `QUALIFIED_AND_FROZEN` was explicitly withheld:

> (paraphrased) The final row-2 transition to QUALIFIED_AND_FROZEN was not to be executed.

`PACK_MANIFEST.json` therefore records `IN_PROGRESS`, and no project may pin
this candidate. The procedure the founder would run is at the end of
`docs/RP2.4-GATE.md`. Nothing in this release infers that authorisation, and
`tools/tests/test_release_integrity.py` fails if the state changes without one.
