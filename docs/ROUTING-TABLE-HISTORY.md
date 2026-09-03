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



## RP2.3 — what this evolution's own routing produced

Recorded as observation, not as policy. Nothing here is a percentage, a provider
preference or a subscription in Core; the routing table holds task classes.

**The cross-vendor route failed twice and the cause was not the vendor.** Two
dispatches held a named wait for 5h39m and 6h42m at roughly a third of a second
of CPU each. The third dispatch, identical but with **stdin closed**, produced
120KB of progress in three minutes. `codex exec` was reading stdin and waiting
for input that was never coming. The reading that mattered — no session rollout
was ever created — was available in minute one and read in hour six, because
nothing was watching for it.

Two things follow, and they point in opposite directions.

The first is that a route's observed unreliability may be the dispatcher's
defect, and attributing it to the provider would have been wrong twice. A
routing table that recorded *cross-vendor is unreliable* from those two runs
would have recorded a false fact about somebody else's software.

The second is that it did not matter. **Every wait carries a deadline, so the
cost of a route that never starts is bounded by the deadline and not by the
cause** — which is the property to keep, because the next cause will be
different and will also not be understood at the time.

**Same-family delta re-audit, chosen deliberately over cross-vendor:** a bounded
re-audit of specific repairs, where independence is satisfied by a fresh blind
context and the value of a different derivation is low. Cross-vendor was
reserved for the final release-authority read, where independence of derivation
IS the value. The reservation held; the final read was cross-vendor.

**Expiring capacity, observed once:** part of a periodic allowance due to
reset soon, spent preferentially on same-family implementation,
falsification and repair. It did not buy a cross-vendor audit's worth of
independence and was not allowed to substitute for one. Recorded here because
the shape recurs; the numbers do not belong in Core, and are not there.
