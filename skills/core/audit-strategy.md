# Audit strategy

## What makes an audit worth having

*   **Fresh context.** An auditor that inherits a conclusion reviews the
    conclusion, not the work.
*   **Read-only.** An auditor that can edit can make the thing it is reviewing
    pass, after which its verdict describes its own work.
*   **An exact, immutable revision.** A clean review of one revision certifies
    nothing about a later one.
*   **Blind to each other**, when there is more than one. Two auditors who can
    see each other's findings produce one auditor and an echo.
*   **Instructed to falsify.** "Review this" invites agreement. "Here are eight
    claims this system makes about itself; try to break them" invites the thing
    you actually want.
*   **Bounded turns**, and a bound that is *known* — so that stopping early is
    visible rather than looking like completion.
*   **Required "what I attacked and could not break."** The only defence
    against a padded finding list, and the most informative section in a
    report.
*   **Barred from the design documents and the repair reports.** An auditor who
    reads the design reviews somebody else's conclusions instead of the artifact.
*   **Findings written incrementally to a durable file**, never held until a
    final message. An auditor that dies mid-run must still leave what it found.

## Cross-vendor diversity

Two independent implementations disagree in different places, which is the whole
value. A second opinion from the same family is a second sample, not a second
perspective — useful for variance, not for blind spots.

## Scarce capacity

Some auditors draw on capacity that is shared with the coordinator dispatching
them. Spending it is not free even when it succeeds: an audit that leaves
nothing to read the result with has cost more than it produced.

Treat a scarce high-value auditor as a specialist — a decisive final review, an
unresolved dispute between two others, a genuinely hard question — rather than a
default. This is an *economic* judgement about capacity, and it must never be
recorded as a judgement about capability: the two are different, and conflating
them narrows a standing on evidence that says nothing about competence.

Which configuration to use, and how many auditors a given closure requires, is
operational policy and lives in the private policy set, not here — it names
products and it changes when they do. See `oracle-discipline.md` for the
separate question of whether an oracle's domain actually reaches what it claims
to test; a clean audit of a wrongly-scoped oracle certifies nothing.

## An interrupted audit is not a clean audit

An audit stopped by a quota, session or turn limit is **incomplete**. It found
nothing because it stopped. Recording it as clean is the most consequential form
of reading an unknown as an answer, because everything downstream then treats
the review as done. A skipped audit is never recorded as passed either — the two
failure modes look different and must be refused the same way.

## Disagreement

Two auditors disagreeing is information, not a problem to average away.
Reconcile the *facts*, once, in bounded fashion: reproduce what each claims.
Usually one is looking at something the other did not. If bounded reconciliation
cannot settle it, that is a human decision — and it is a small one compared to
the cost of reopening a whole improvement loop over it.
