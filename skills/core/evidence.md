# Evidence

## The claim ladder

    planned < bounded < implemented < integrated < validated < demonstrated

No claim may be stronger than the evidence supporting it. Nothing enforces this
but the coordinator, at every commit and at capability closure, refusing to
record a stronger claim than the evidence in hand supports.

What each kind of evidence can carry:

*   **Coordinator-observed** — the coordinator ran it and watched. The
    strongest available, and still bounded by *where* it ran: a suite executed
    in a checkout built and then discarded is real evidence about the code and
    no evidence at all about the real system.
*   **External service observed** — something outside the coordinator's own run
    reported it, and the report was captured rather than summarised.
*   **Fixture-derived** — true of the fixture. Says nothing about production
    data, production scale, or anything the fixture does not contain.
*   **Human-supplied** — someone said so. Not independently verified, and the
    ceiling reflects that.
*   **Worker-reported** — the thing being judged reported on itself. Weakest,
    for a reason that has nothing to do with honesty: an implementer cannot see
    the failure mode it did not think of. Never gate-consumable alone — see
    `worker-contract.md`.
*   **Derived** — computed from other records. No stronger than its inputs.

## Unknown is a third answer

The failure this exists to prevent: an operation whose outcome nobody observed,
recorded as a zero, a false, or a success.

*   A number nobody measured is **absent**, never zero. Zero is a measurement.
*   A check that could not run is **not run**, never passed.
*   An outcome nobody could determine is **unknown**, never failed. Retrying on
    "unknown" is how one task acquires two workers and one piece of work enters
    history twice.
*   An audit cut short by a limit is **incomplete**, never clean. It found
    nothing because it stopped, not because there was nothing.

When you cannot tell, say so and stop. "Could not verify" recorded as "verified"
is the defect that survives longest, because everything downstream then treats
it as settled.

## Reading an auditor

Findings are not equal, and treating them as a queue to burn down produces bad
repairs. Separate:

*   a **finding** — something is wrong, here is why;
*   a **limitation re-report** — a known, documented, accepted bound, found
    again. Not a defect, and closing it as one would mean changing something
    that was deliberate;
*   a **scope disagreement** — the auditor and the contract disagree about what
    was being built. Resolve the disagreement, do not implement it;
*   a **proposed improvement** — real, and not evidence of a defect.

**Reproduce a finding before repairing it.** An auditor can be wrong, and a
"fix" for something that was never broken changes working code on the strength
of an assertion. A finding that will not reproduce should be refuted explicitly,
with the reason, rather than quietly dropped.
