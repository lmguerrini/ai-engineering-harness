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

*   **No push, remote, tag or publication has been prepared.** The freeze
    procedure below is written and has not been run.
*   **No push, remote, tag or publication.** Nothing left this machine.
*   **No project was migrated, and no project's files were modified.** The three
    real contracts were read; one of them is refused, correctly and now
    informatively, and repairing it is that project's to do.
*   **The 2.2.0 and 2.1.1 releases are untouched.** Both still verify.

## What the independent readings cost, and what the arithmetic says

Every closure audit was blind: an immutable snapshot at a named revision, a
reader barred from the design documents, and an instruction to falsify. **Every
one returned NOT READY**, and the arithmetic is the most decision-relevant fact
in this packet. The rounds below are the ones this table was written for; the
gate record carries the later ones, and `PACK_MANIFEST.json` records how many
cycles have run.

| Round | Reader | Findings | Of which were defects in the PREVIOUS round's repairs |
|---|---|---|---|
| 1 | blind, same family | 15 | — |
| 2 | blind delta re-audit | 5 blockers + 6 decorative tests | **3 of 5** |
| 3 | blind, cross-vendor | 8 | 0 — but 6 were about a snapshot two rounds old |
| 4 | cross-vendor, release authority | 6 blockers + 4 others | 1 |
| 5 | cross-vendor delta re-audit | 7 | **4 of 7** |
| 6 | cross-vendor — **killed by its provider mid-run** | 5, recovered from its stderr | 3 of 5 |
| 7 | cross-vendor property read | 8 + a vacuous test | 2 |
| 8 | cross-vendor, final | *see the gate record* | — |
| 9 onwards | cross-vendor, delta-bounded | *see the gate record* | — |

**A repair has been about as likely to carry a defect as the code it repaired.**
About a quarter of all findings were defects in the previous round's repairs,
and that ratio never improved across the rounds. It is not an argument for one
more round: it is the reason this release treats *all findings closed* as a
statement about what was looked for, and the reason each later cycle was
delta-bounded to the repairs the one before it made.

**The later rounds found what the earlier ones could not.** A published
submodule reference certified a history clean; a record field of the wrong
shape made the view raise; two of the forty-nine dashboard markers matched the
sentence that denies them; a sweep for oracles that cannot fail missed a shape;
and a reader adopting the release in a clean room found that it shipped a
reader for the coordinator's record and no way to write one. Each is repaired
at the boundary it arrived through, with an oracle that fails without the
repair.

Two patterns are worth more than the count.

**Five separate routes by which a repository being read could run a program of
its choosing**, found in rounds 4, 5, 6 and 7 — each closed where the previous
repair could not see it. Round 7's response was not a sixth patch but a check on
the *shape* of the config key, so the sixth route refuses without anyone having
traced it. Whether that holds is the single most load-bearing question left, and
every round from the eighth was pointed at it.

**Six tests that passed for reasons they did not state**, four found by someone
other than their author and two by mutation passes over 25 guards. One searched
source text and survived its subject being deleted; one looped over the very
constant a mutant emptied; two compared a pure function with itself. The lesson
this release would offer another project is not *write more tests* — it is that
a test nobody has tried to break is a claim, not evidence.

### Round 3, which cost the most for the least

Six of its eight findings were already repaired and its report could not say so,
because it never stated which revision it read. The wasted direction was
harmless. The other direction — a clean audit of an old tree reading as clean
for a new one — is a green gate over a tree nobody examined, and
`close_gate(..., against=(revision, digest))` now refuses it. Every brief since
has opened with the revision and digest the reader actually read.

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

## Evolution Candidates, deferred out of this release

Each is a real observation with the evidence that produced it. None is a defect
in this release: each would be a **new guarantee**, and adding one tonight would
be starting the next release inside this one.

**An archive cannot verify its own identity.** *Evidence:* unpacking the release
with `git archive` into a clean room and adopting it — `IDENTITY COULD NOT BE
ESTABLISHED`, because the digest is defined over the tracked tree and an archive
has none. *Value:* a consumer who vendors the pack rather than cloning it could
check what it has. *Trigger:* the first consumer that vendors. *Layer:*
`pack_pin` and the manifest — a per-path inventory in the manifest would make
the tracked set knowable without Git. *Deferred because:* the documented
delivery is a checkout, and a second identity mechanism is a new promise rather
than a repair to this one. This release says which question it cannot answer.

**A published submodule's history is not read.** *Evidence:* an independent
reader built a superproject whose dependency's committer identity carried a
private term and the scan reported clean. It reports INCOMPLETE now and names
the submodule. *Value:* actually reading it. *Trigger:* the first consumer with
a submodule it must publish. *Layer:* `publication_history` and `gitread`.
*Deferred because:* resolving and fetching another repository is a network act
with an authority question of its own, and refusing to certify is the correct
answer until that question is decided.

**Nothing wakes a coordinator.** *Evidence:* `COORDINATOR_WAKE_REQUIRED` is
derived and reported, and acted on by nothing. *Value:* the liveness model would
close rather than merely detect. *Trigger:* a qualified first-party session
primitive plus a governance rule authorising its use. *Layer:* outside the pack.
*Deferred because:* creating or waking a session is out of scope by declaration,
and the deadline ends the wait regardless.

**The console cannot refresh itself.** *Evidence:* the page is exactly as old as
the reading times it shows, and re-reading means running the command again.
*Value:* an operator watching a long run would not have to. *Trigger:* an
operator asking. *Layer:* presentation. *Deferred because:* every honest way to
do it adds something that runs — a server, a scheduler, a poll — and this
release ships nothing that runs. A page that reloaded itself from disk without
re-deriving would be showing a stale reading with a fresh timestamp, which is
worse than the reading being old and saying so.

**A stall still needs two readings, so the console declines to answer it.**
*Evidence:* the overview's `stalled` column shows `·` and says why. *Value:* an
operator would see stalls where they look for everything else. *Trigger:* a
coordinator that runs `progress.classify` on a schedule and records its verdict
in the record — at which point the console can show it, because it would be
reading an answer somebody else owns rather than computing one. *Layer:* project
practice first, then the projection. *Deferred because:* the page must not
become the second place a state is decided.

**The widget catalogue grows with the number of projects.** *Evidence:* twelve
projects offer a hundred and thirty widgets; the catalogue is grouped and folded
per project and is still long. *Value:* an operator with many projects could
find one. *Trigger:* an operator with many projects. *Layer:* presentation.

**The complete-history scan costs about a second per commit.** *Evidence:*
measured at 125 seconds over this repository's history. It is intentionally
expensive — it reads every tree of every commit — and its cadence is
pre-publication, not per-commit. *Value:* an incremental scan against a
last-scanned marker. *Trigger:* a consumer repository large enough that the cost
is a reason to skip the gate, which is the failure this would exist to prevent.
*Layer:* `publication_history`. *Deferred because:* *unchanged since* is a new
claim and needs an oracle of its own before anything may rely on it.

## The freeze, prepared and not performed

Moving the state is the founder's act — HITL row 2, and this session stops
short of it deliberately. What follows is the procedure derived from what the
2.2.0 freeze actually did, so the decision is a decision and not also a
research task.

**1. State the release identity identically on every surface that carries it.**
The 2.2.0 freeze touched exactly five files, and the reason it touched five is
that a release whose manifest says one thing and whose README says another has
no identity at all:

    PACK_MANIFEST.json          state, tree_digest_sha256, supersedes, the
                                adoption note
    README.md                   the verification command and the state it names
    CHANGELOG.md                the release line
    docs/RP2.3-GATE.md          the closure record's own statement of state
    docs/RP2.3-RELEASE-PACKET.md   this file

**2. Recompute the digest over the frozen tree, and verify it twice.** Once with
the shipped verifier and once with an independent implementation of the framing
algorithm — the pack ships both, and the second exists because a digest checked
only by the code that produced it is a checksum of itself:

    python3 tools/pack_pin.py . --write
    python3 -m pytest tools/tests/test_release_integrity.py -q

**3. Commit, on the branch, with no tag and no remote.** The commit gate runs
against the pack's own published vocabulary:

    python3 tools/commit_gate.py --default-terms . <message-file>

**4. Give the release a root nobody works in**, and only then list it:

    cp -R <this worktree> <harness>/releases/runtime-pack-2.3.0
    # then add the entry to releases/RELEASE_INDEX.json

The order matters and the index says why: **only releases with a root nobody
works in are listed.** 2.1.1 is deliberately absent from that index because it
lives in the checkout the next version is developed in — the D18 defect this
release detects and does not fix, because fixing it moves a live project's pin
and that is the founder's call too.

**5. Nothing adopts automatically.** A project pins by root path, version, full
forty-character revision, tree digest and state, and adopts at its own next
capability boundary. `consumer-c-v1` stays on 2.2.0 until it decides otherwise, and
a project that never moves is correctly pinned rather than out of date.

## READY_FOR_FOUNDER_FREEZE

    version   2.3.0
    revision  NOT WRITTEN HERE, deliberately — see below
    digest    PACK_MANIFEST.json, `tree_digest_sha256`
    state     IN_PROGRESS — and it stays there until a person moves it
    tests     PACK_MANIFEST.json, `tests.passed`

**The revision is absent for the same reason the manifest gives for its own:** a
document cannot name the commit that contains it, any more than it can contain
its own hash. The first draft of this section wrote one in, and committing the
draft made it wrong — which is the drift this release spent eight rounds
teaching itself to refuse, arriving at the last page.

The identity is version + revision + digest + state. Two of those are in the
tree, the third is the commit you are reading, and the consuming project records
it in its own pin and verifies rather than copies:

    cd <this checkout>
    python3 tools/pack_pin.py . --version 2.3.0 \
        --sha "$(git rev-parse HEAD)" \
        --digest "$(python3 -c "import json;print(json.load(open('PACK_MANIFEST.json'))['tree_digest_sha256'])")" \
        --state IN_PROGRESS
    python3 -m pytest tools/tests/ -q

If both exit zero, the tree in front of you is the candidate this document
describes. If either does not, believe them and not this.

### What is green

**Every count in this section was removed rather than updated.** Four of them
were stale when an outside reader compared this document against what the
release ships — a test total, a mechanism total, a recurrence total and an
audit total, each typed beside a fact the repository can compute. Two of the
four had wrapped across a line, which is how they got past the guard that
exists to catch exactly this. The guard reads whole documents now, and this
section names the command instead of the number.

    python3 -m pytest tools/tests/ -q                      # the suite
    python3 tools/pack_pin.py . --version 2.3.0 --state IN_PROGRESS
    python3 tools/publication_history.py .                 # the history scan
    python3 -c "import json;print(len(json.load(open('policy/recurrence-classes.json'))['classes']))"
    grep -cE '^\| M-[0-9]' docs/RP2.3-FAILURE-MODE-CLOSURE.md

What holds, in words that cannot go stale:

*   Every blind closure audit run against this candidate returned NOT READY,
    and every finding was consumed and repaired. The table above lists them by
    round with what each cost.
*   Every mechanism in the closure matrix is PREVENTED, DETECTED_AND_BLOCKED or
    SAFELY_RECOVERABLE, and none is uncovered. A guard asserts the dispositions
    are from that set and that every named oracle selects at least one real test.
*   Every mandated recurrence class is proved against an oracle that was
    executed rather than cited, and the prose and the policy file are asserted
    to hold the same list.
*   The commit gate reports VALID over every message from the 2.2.0 freeze to
    this revision, checked against the pack's own published vocabulary.
*   The complete-history scan reads paths, blobs, ref names, tag messages and
    whole commit objects, with **zero unscanned**. A repository that publishes a
    submodule reference makes the report INCOMPLETE rather than clean, because
    that history is not read here.
*   The live rehearsal against the projects that pin this pack: `VERIFIED_PIN`,
    read-only, nothing in any of them changed.
*   The assembled system runs end to end against real processes, in a clean room
    built from `git archive` and from a fresh clone, with the console and the
    phone layout measured rather than eyeballed.
*   2.2.0 verifies. 2.1.1 verifies. Zero remotes, zero tags, nothing pushed or
    published, no history rewritten, `main` unmoved.

### What is not, and will not be before a person acts

**Round 8's repairs are unaudited, and the closure ceiling is reached.** The
founder raised it from 4 to 8 mid-session; all 8 are spent. A ninth reading is
HITL row 8. The three repairs it would examine are the thread-local inspection
guard, commit-message scanning, and the write-bound check — each reproduced,
repaired, regressed and mutation-killed by the coordinator, and none read by
anybody else.

That matters more here than the sentence usually does. **Thirteen of roughly
fifty findings across eight rounds were defects in the previous round's
repairs.** On that base rate, a ninth reading would probably find something. It
is the founder's call whether the marginal finding is worth the cycle.

**Two readings were killed mid-run by their provider's content
filter** and wrote nothing; their findings were recovered from stderr, and both
sets mattered. Neither completed its sweep, so rounds 6 and 8 are partial by
construction.

The other standing limitations are in `PACK_MANIFEST.json` under
`known_limitations`, and the ones a reader should not skip are: the
program-valued config list is not complete and cannot be; no project declares an
adapter executable, so that verification path is exercised only against the live
installation; the capacity gate has never seen a real provider reading; and the
projection has never been watched during a real multi-hour run.

### The remaining human actions

1. **Decide whether to spend a ninth closure cycle** on round 8's repairs. Row 8.
2. **Freeze**, if you choose to: the procedure is in *The freeze, prepared and
   not performed* above — five surfaces to make say one thing, two independent
   digest verifications, a commit, then a root nobody works in and only then the
   index entry.
3. Everything else — push, remote, tag, publication — remains a separate human
   action and none of it is required to qualify this candidate.

The coordinator stops here. Moving the state is not its act.
