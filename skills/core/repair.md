# Repair discipline

Ten steps, in order. The order is the content: most of the ways a repair goes
wrong are ways of skipping one of the first five.

1. **Reproduce it.** Before anything changes. A finding you cannot reproduce is
   a finding you cannot tell you have fixed, and "the test passes now" is not
   the same claim.
2. **Separate the root cause from the symptom.** The symptom is where it
   surfaced; the cause is why it was possible. Fixing the first makes the
   second surface somewhere else, usually later and usually in a worse place.
3. **State the invariant.** In one sentence, as something that must always be
   true. If you cannot write it, you do not yet know what you are fixing.
4. **Write a discriminating oracle.** A test that fails now, for the stated
   reason, and would pass when the invariant holds. See `oracle-discipline.md`
   for deriving its domain from the mechanism, not the symptom.
5. **Mutation-check the oracle.** Break the guard deliberately and confirm the
   test fails. This is the step that is always tempting to skip and never safe
   to: a test that cannot fail is not evidence, and it will be cited as evidence
   for years.
6. **Implement the smallest fix at the root.** Smallest *at the root*, not
   smallest overall — a narrower patch to the symptom is not the smaller change,
   it is the one that has to be made again.
7. **Focused regression.** The tests around what you touched.
8. **Broader regression only when the mutation surface justifies it.** Changing
   a schema, an authority or a shared boundary justifies it. A local fix does
   not, and running everything after every change teaches you to ignore it.
9. **Update the documentation that is now wrong, in the same change.** A record
   that overstates what is enforced is a defect; one that *understates* it is
   also a defect, because the next reader will build a second guard.
10. **Targeted independent re-audit** where the contract calls for it, and stop
    when the bound says to.

## What a green test does not mean

*   **A skip is not a pass.** A check that could not run is not a check that
    passed, and counting it as one is how a suite reports on work nobody did.
*   **A control with no caller is not implemented.** Correct, tested, and
    nothing in the real flow reaches it. If the only caller is "the tests," it
    is not wired.
*   **A recorded failure nobody consults is not enforcement.** A note in a log
    is not a gate.
*   **A rule enforced only on replay is worse than no rule.** It has to hold at
    the point of writing, not be discovered on a later read.

## Two consecutive regressions

If two repairs in a row have caused adjacent breakage, stop repairing. The
repairs are the problem — each one is individually reasonable, which is exactly
why nobody notices the pattern from inside it. Strengthen the root invariant so
the class cannot recur, or escalate. The budget counters in `policy/BUDGETS.md`
bound this; you should reach the bound having already decided the same thing.
