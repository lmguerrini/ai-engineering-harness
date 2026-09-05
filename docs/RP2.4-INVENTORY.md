# Every recorded limitation, classified

The founder's pilot-run directive asked for this explicitly, and asked that
the burden of proof sit on the answers that leave something unfixed:

> (paraphrased) A non-blocking finding is not automatically good enough, and
> nothing stays a limitation merely because it was previously called a
> limitation.

Four classes. **A** must be fixed before freeze. **B** should be fixed now
because it is practically solvable and would otherwise cost an adopting project
debugging time. **C** is a real bounded limitation that cannot honestly be
removed in 2.4.0. **D** is future evolution, outside this release's
architectural boundary.

Fifty-seven limitations were carried into this pass. **Two were A, eight were
B, and all ten are closed.** The rest are C or D, and each is stated below with
what still holds, which direction it fails in, whether an adopting project can
meet it, and what would reopen it.

---

## A — fixed before freeze

### A1. One commit in the candidate failed the public commit contract

`commit_gate.py --range` reported one violation: a message carrying a private
term, committed because a shell chain's `&&` attached to `tail -1` rather than
to the gate. The gate ran, printed `VIOLATION`, exited non-zero, and the commit
happened anyway.

**Closed** by the minimal history repair the founder authorised. Trees reused
rather than re-derived, ten commits before and after, same order; the complete
range now reports `VALID every commit message in ab7dea97..HEAD conforms`. The
evidence is in `docs/RP2.4-FOUNDER-AUTHORISATIONS.md`.

### A2. The row-7 governance narrowing was held outside the decision layer

**Closed** by founder authorisation, recorded before the entry was written —
which is row 7's application point — and bound to ten executable conditions in
`tools/tests/test_founder_authorisation.py`. Fifteen well-formed mutants, each
broadening D26 past what was authorised, all killed.

---

## B — practically solvable, and solved

### B1. A checkout on a machine that normalises line endings failed its own pin

`core.autocrlf=true` is the default on Git for Windows. Cloning this branch
under it rewrote LF to CRLF in every tracked file, and `pack_pin.py` reported
`PACK PIN NOT VERIFIED` **against a checkout of the correct revision** — the
first thing an adopting project would hit and the last thing it would attribute
to its own Git configuration.

**Closed** by `.gitattributes` declaring `* -text`, which fixes the cause rather
than compensating in the reader. Verified end to end: three clones under
`autocrlf=true`, `autocrlf=false`, and `autocrlf=input` produce **one identical
digest**. Held by an oracle that asks Git — not the file — whether any tracked
path still carries the `text` attribute.

### B2. A project's repository resolved against the process, not the project

**Found by running the application.** `ProjectContract.repository()` returned a
relative `repo_path` verbatim — `"."` in every rehearsal fixture in this pack,
and available to any project. Every caller that
falls back to it (`commit_gate --range`, `outgoing_scan`, `workspace_report`,
`publication_gate`, `publication_history`) therefore ran against whatever
repository the invoking shell was standing in. The multiproject history view
showed **the coordinator's own 165 commits under both consumers' names**, and
the panel that reports "same repository as a row above" said so correctly about
an answer that was wrong for both.

**Closed** at the contract, so every caller is correct at once rather than five
call sites each able to drift, plus the console's own resolver, which reads the
pin. Five mutants, all killed — including one that survived a first oracle
because `parent / absolute` already yields the absolute path, and `.resolve()`
would silently rewrite a declaration made through a symlink.

### B3. Availability had not been re-established on the current client

Every availability observation in the log was recorded on client `0.149.0`, and
the client moved to `0.153.3` because execution proved the older one could not
run the model under evaluation.

**Closed** by a live sweep through the subscription surface: every identifier
discovery offers, dispatched on the current client. Nine of nine started, and
the model the surface reported matched the model requested in every case. The
figures are in `docs/RP2.4-GATE.md`.

### B4. The pack's own history carried unadjudicated occurrences

**Closed as adjudicated** in `docs/RP2.4-PUBLICATION-ADJUDICATION.md`. At the
tier that governs a project, every occurrence resolves to a home-relative form,
a fixture path, a placeholder or a synthetic identifier — none names a person,
machine, account, session or credential. At the strict tier the population is
the pack's own vocabulary appearing in its own documentation, which is the case
`skills/core/public-safety.md` describes.

### B5. The executable half of the adapter contract was unexercised by any adopter

Every real contract on this machine declares files only, so every real report
read `0 executable(s)` and the version-checking half shipped untested by an
adopter.

**Closed** in `tools/tests/test_two_consumer_rehearsal.py`, where one of the two
projects declares an executable, a version command and a qualified version. The
report verifies it, a drifted qualified version is refused rather than warned
about, and a required adapter edited after qualification stops that project's
capability opening while leaving the other project's alone.

### B6. Two projects had never been run at once

Every rehearsal was single-project, and both roots in a real deployment pin one
pack. **Closed** by the same module: two roots differing in every declared way,
running real background workers concurrently, each reconciling its own producer,
one consuming its result without settling the other's, both reconstructed cold
by a fresh interpreter holding only the file.

### B7. The 2.3.0 linked-worktree incident was remembered as prose

A release root that is a linked Git worktree is not immutable — whoever owns the
main repository can move it — and it verifies perfectly while it happens to sit
on its pinned revision. That was recorded in two manifests and detected by
nothing.

**Closed** by `pack_pin.root_kind`, reported as a note beside a verified pin in
`capability_open` — never blocking, because a linked worktree on its pinned
revision is a correct checkout of the right tree and refusing it would refuse a
working adoption over a hazard that has not happened. Four mutants, all killed.
The hazard itself is executed in a test: the pin fails loudly with four separate
problems rather than quietly.

### B8. Three named vacuity shapes had no mechanical guard

`xfail(run=False)`, `xfail` without `strict`, and an unconditional `skip` all
report a non-failure without running the test, and the suite count still looks
right. **Closed** by a sweep over every test module, with its own positive and
negative cases so the sweep is known to be able to fail.

---

## C — real bounded limitations

These are stated in full in `PACK_MANIFEST.json`. What follows is why each one
stays, in the form the directive asked for.

**The trust boundary at the adapter.** An adapter that invents a provenance
marker, or records an outcome that did not happen, passes. The alternative is an
allowlist of admissible execution surfaces, which is a vocabulary that ages
exactly the way the model vocabulary this release removed aged. *Fails towards*
believing a false record. *A project can meet it* by qualifying its adapter.
*Reopens on* an execution surface that can attest its own output.

**A wait nobody declares is invisible.** The liveness model governs declared
waits. Seeing an undeclared one would mean policing the coordinator's own shell,
which is the thing this pack refuses to become. *Fails towards* an
under-reported job list, never an over-reported one. *Reopens on* a shell
integration a project asks for.

**The design gate checks that a design was made, never that it was good**, and
cannot stop a caller who declares a material change `TRIVIAL`. Change class is
the project's declaration because Core cannot know which of a project's changes
are material. *Fails towards* a recorded claim somebody can dispute rather than
a silent omission.

**Family-level history is nearly all this evidence base has.** A small number of
configurations carry a complete identity; every other answer is `unprobed` with
a prior beside it. **The number is not written here** — an earlier draft said
"eight configurations", which was eight OBSERVATIONS over fewer configurations,
and an independent reader caught it in the document that records the rule
against restating a count the repository can compute. Run
`python3 tools/qualification.py`. Nothing was fabricated to fill the table.
*Reopens* continuously, as dispatches record observed identities.

**Two dispatches at one configuration reach `confirmed` at that task class**,
including two bounded probes. This is the grading rule `backend_contract` has
always used, unchanged by D26 on purpose, and it is bounded by the task class:
evidence at `model_usability_probe` qualifies nothing at
`blind_release_authority_audit`, and rows 12 and 16 keep their human for a
critical-domain promotion. *Fails towards* treating a cheap probe and a
demanding dispatch at the same class as the same evidence, which is a question
about how a project chooses its task classes.

**Neither renderer has been watched during a real multi-hour run.** Both are
falsified against twelve synthetic states, five lenses, three viewports and this
session's own live record, and this release found and fixed a real defect by
rendering one over two projects. Whether the information architecture is right
for somebody four hours into a run is not establishable until somebody is.

**Held prose is over its target**, and the overage is the two installed adapter
files, which sit outside this envelope, are covered by no digest, and are
impossible for this pack to freeze — and are counted anyway, because they load
every session. The in-release half is under target.

**The evolution workspace is a linked worktree**, which is the D18 layout defect
2.2.0 named. This candidate now *reports* the hazard (B7) rather than removing
it; relocating the pinned root of a live project is the founder's decision and
was not taken.

**A test whose every assertion sits inside a loop over a computed iterable can
pass having asserted nothing.** Thirty-six such tests exist. All thirty-six were
traced under execution this pass and **every assertion in thirty-five of them
executed; the thirty-sixth executed two of four**, which is branch coverage
rather than vacuity. No guard prevents a thirty-seventh from being added with a
fixture that computes empty. *Fails towards* a passing test that claims nothing.
Recorded as an Evolution Candidate rather than guarded, because the measured
population is clean and a guard would force cosmetic edits on thirty-six honest
tests.

---

## D — future evolution

*   A durable event log, so that a capability opening, an audit being dispatched
    and a finding being recorded can be dated. Seven event classes ship because
    seven are what durable artifacts date.
*   A multi-year activity calendar. The 366-day default is a render-cost
    decision and `window_days=0` already reads all of it.
*   Relative yield between a same-family and a cross-vendor audit, which needs
    the two run as a comparison rather than counted.
*   An execution-trace oracle for the loop-only shape above, shipped as a tool
    rather than run once as a measurement.
*   A read-only way to enumerate a bundle's objects, which is what stands
    between `ANCHOR_UNCONFIRMED` and a bundle that can anchor.
