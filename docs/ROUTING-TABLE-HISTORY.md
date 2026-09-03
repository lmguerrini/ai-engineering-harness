# Routing table — what happened to it

Moved out of `policy/routing-table.md` in RP2.3. `policy/` holds what governs and `docs/`
holds what happened (`policy/BUDGETS.md`); a narrative held every session competes with the
rules for the same budget, and this one is read when a grade needs defending rather than
every time the table is consulted. Left exactly as written.

## Two grades in this table were wrong, and that is why the next section exists

`AUDIT_PRIMARY` and `READER` both read **`confirmed`** through 2.1.1. Neither was,
under the rule stated at the top of this file and applied by the command below:
`AUDIT_PRIMARY` had one validation, which is `provisional`; `READER` has two
dispatches at **two different task classes**, which is one each — and "grades are
per task class, never per worker" is this file's own rule, three lines up.

An independent audit found it by running the command printed here and reading
the table above it. Corrected, and now compared by a test rather than by a
reader — which is why `AUDIT_PRIMARY` reads `confirmed` again today and means it:
six more real closure audits happened during the RP2.2 evolution session, every
finding reproduced before it counted, and the grade follows the log rather than
the other way round.

