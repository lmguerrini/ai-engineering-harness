# RP2.3 — founder release packet

**The manifest declares `IN_PROGRESS`.** No project may adopt this candidate.
Moving it to `QUALIFIED_AND_FROZEN` is a human decision (`policy/hitl-matrix.md`
row 2) and the coordinator did not take it. Everything below is the record that
decision would be taken on.

## Read this before deciding

This release closes failure classes that were **measured on a real project after
2.2.0 froze**, and every one of them was reproduced by execution against the
frozen baseline before anything was written. Twenty-six reproductions are listed
in `docs/RP2.3-CAPABILITY-MAP.md`, each with how it was produced.

**What was destroying work, and is now bounded.** One write too large to land
left no artifact at all — twenty-seven records, and the absence looked exactly
like never having started. A wave of eight workers on the coordinator's own
rolling window lost eighty-one records, three of them from workers that had left
usable bytes nobody looked at. Both now have a mechanism: bounded chunks
materialised by a rename, and a four-valued classification read from the
artifacts rather than from a worker's status label.

**What was invisible, and now has a name.** Four situations produced one
observable — nothing happening — and only one of them was a defect. The decisive
recorded instance declared its wait correctly, named the job, the process and
the log, and then went silent for two hours and twenty-one minutes after the job
exited. Coordinator state is now **derived from artifacts rather than stored**,
so it advances whether or not anyone is watching, and `SILENT_IDLE` is
representable as a defect rather than as a resting state.

**What closes on its own.** A commit that records cite can be orphaned by a
rewrite, and the window to recover it is roughly a month that ends the instant
anyone expires a reflog.

**What no shipped invocation ever asked.** Whether the *complete reachable
history* is public-safe at the *strict* tier. A term committed and then deleted
survives in a blob the working tree, the index and every tip-shaped scan miss.

## What this release deliberately does not do

*   **It does not rewrite history**, and no part of it can. It detects,
    classifies, prepares and verifies; executing a rewrite is rows 2 and 4
    (`DECISIONS.md` D23 clause 6). The invariants ship in the same release as
    the gate that produces a remediation list, because such a list authorises a
    rewrite by consequence.
*   **It does not terminate a worker.** A stall is classified and a person
    decides. The false-positive rate is measured, not theoretical: a healthy
    worker produced no log output for over four minutes while its processor time
    climbed.
*   **It does not restart a coordinator.** It can report that one is needed.
    D23 clause 4, and the substrate primitive that would close the loop was
    established not to exist.
*   **It schedules nothing.** The capacity component is a pre-dispatch refusal
    with no queue and no dispatch verb, and a test asserts it never acquires one.
*   **It invents no number.** No universal reserve, no vendor grade, no scalar
    for semantic quality. `UNKNOWN` is a first-class reading throughout, and
    where capacity is unknown the gate becomes conservative rather than precise.

## Why this is MINOR

`DECISIONS.md` D24 decides it, and the decision was the founder's at the session
freeze rather than the coordinator's afterwards: **an obligation an adopting
project cannot fail to satisfy is mandatory; one that needs new project
capability is declared.** Generating a close attestation is mandatory because
its input is a block every contract already carries. Refusing to close over an
unrun profile is the project's declared policy, defaulting to refusing.

The claim is a test rather than an argument. `unchanged_since_2_2` is a
representative contract carrying **none** of the keys this release adds, and the
probes assert it loads and behaves exactly as it did.

## The history that is most decision-relevant

**Nine of this release's mutants survived their first pass, and every one was
the same shape: an assertion the code satisfied for a reason the test did not
name.** The pattern is worth more than the count.

*   A progress report could list a signal as flat that nobody had compared. The
    verdict was unaffected, so seven of eight mutants died and this one lived —
    **a test that checks only the verdict passes while the report lies.**
*   The remote postcondition's repair proved the *mechanism* worked while
    nothing asserted the *caller used it*. That is *a control with no caller is
    not implemented*, arriving as a live mutation rather than as a maxim.
*   Three separate fixtures failed to reach the bundle-verification guard. One
    used a file that was not a bundle; one truncated a valid bundle, and `git
    bundle verify` checks prerequisites rather than pack contents so every
    corruption verified clean; the third deleted a branch and left
    `refs/remotes/origin/main` still reaching the commit.
*   A length comparison in the surface differ turned out to guard **nothing** —
    every path it covered was refused earlier — and was deleted rather than left
    as decoration.
*   One assertion compared a set literal with itself.

**And one mutation taught nothing, which is also a result.** `return None or (…)`
evaluates to the same expression, so a "survivor" was an instrument defect rather
than a gap in the oracle.

**The coordinator's own instrument was wrong once.** A hand-written substring
check reported a private term inside the word *resolves*; the shipped scanner
word-bounds a bare term and reported the same message clean. Every commit on the
branch was re-validated with the shipped scanner, all conform, and the reason a
substitute existed — this repository had no way to check itself with its own
published vocabulary — is closed rather than worked around.

## What has NOT happened

*   **No independent audit has seen this candidate.** That is the next step and
    it is not optional for a final gate.
*   **No push, remote, tag or publication.** Nothing left this machine.
*   **No project was migrated, and no project's files were modified.** The three
    real contracts were read; one of them is refused, correctly and now
    informatively, and repairing it is that project's to do.
*   **The 2.2.0 and 2.1.1 releases are untouched.** Both still verify.

## What four independent readings cost, and what they say about the fifth

Four blind closure audits, each against an immutable snapshot, each barred from
the design documents, each instructed to falsify. **All four returned NOT
READY**, and the arithmetic is the most decision-relevant fact in this packet:

| Round | Reader | Findings | Of which were defects IN THE PREVIOUS ROUND'S REPAIRS |
|---|---|---|---|
| 1 | blind, same family | 15 | — |
| 2 | blind delta re-audit | 5 blockers + 6 decorative tests | **3 of 5** |
| 3 | blind, cross-vendor | 8 | 0 — but 6 were about a snapshot two rounds old |
| 4 | blind cross-vendor, release authority | 6 blockers + 4 others | 1 (the blocker-union defect, one level up from round 2's) |

**A repair has been roughly as likely to contain a defect as the code it
repaired.** That is not an argument for a fifth round; it is the reason the
release records that its own final repairs are unaudited by construction, and
the reason a reader should treat "all findings closed" as a statement about what
was looked for rather than about what is there.

Round 3 is the instructive one. Six of its eight findings were already repaired,
and its report could not say so because it never stated which revision it read.
The wasted direction was harmless. The other direction — a clean audit of an old
tree reading as clean for a new one — is a green gate over a tree nobody
examined, and `close_gate(..., against=(revision, digest))` now refuses it.

## The finding that most deserves a decision

**The D18 layout defect is unchanged and it is live.** One real project pins the
pack's *working* checkout by root path. It verifies today only because that
checkout happens to sit on its pinned revision, and ordinary development in it
would break the pin — which is why this whole release was built in a worktree
rather than in that directory. The mechanism to notice it ships; the layout move
does not, because it affects a live project and is the founder's to make.

The release index created by this session omits 2.1.1 for the same reason:
listing a working checkout as a release root would enshrine the defect rather
than record it.

## Verifying this candidate

    cd <this checkout>
    python3 tools/pack_pin.py . --version 2.3.0 --sha <full 40-char revision> \
        --digest <PACK_MANIFEST.json tree_digest_sha256> --state IN_PROGRESS
    python3 -m pytest tools/tests/ -q
    python3 tools/commit_gate.py --default-terms . --range HEAD \
        --baseline d70d72fbcadb98cb8a2979f9c63ed84e595662e8 --repo .

The state is `IN_PROGRESS` and that is what the command above must pass. A
project may only adopt `QUALIFIED_AND_FROZEN`.
