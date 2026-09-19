# DESIGN — RP2.6.0 P0: a third provider as a pool with billing on the pool (SUPERSEDED)

**Change class:** MATERIAL
**Base revision:** aa55575b614df3ed4454df87f33c8796dc602258
**Frozen:** yes

Falsified before any implementation and superseded by `RP2.6.0-DESIGN-P1-provider-registry-and-billing-safety.md`; kept exactly as written, as history.

## What this design proposed

The read-only audit that opened this release found the cross-vendor audit leg qualified on exactly one
configuration, drawing on one shared account-level pool that consuming projects exhaust,
while another pool stood partly unspent. P0 answered with the smallest change that adds a third
pool: a provider-specific adapter skill for the new vendor, `Derivation.vendor` for independence, and a
`billing_mode` field on `capacity.Pool` so a pool could say whether it is subscription-billed.

## The mechanism

A provider is added by writing an adapter for it and declaring a pool whose `billing_mode` names how it
is billed; the eligibility report joins qualification and capacity and the coordinator chooses.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | hardcode the new vendor as "the" cross-vendor leg beside the existing one | REJECTED | a name in Core is what the single-sourced leg already is; a second name is a second `use_sol()` |
| 2 | a provider-specific adapter plus `billing_mode` on the pool (this record) | SELECTED | the smallest change that adds a pool — selected at freeze, falsified before implementation (below) |

## What falsified it

Two founder rulings, both recorded in `DECISIONS.md` (D29–D32), reached the design before a line of it was
built:

*   **A fixed slot is a count.** An adapter per provider and a pool per adapter is `provider_3`, and the next
    provider is a Core release. The registry must be a declared record of unbounded N with no ordinal.
*   **Billing on the pool is a claim, not a proof.** A pool that *says* `subscription` does not establish that
    the exact route the worker will take — provider, gateway, endpoint or client, credential source, billing
    pool, plan — cannot create charges beyond the authorised subscription. A worker environment carrying a
    metered credential beside the subscription one would be routable under P0; the founder's invariant makes
    it NOT ROUTABLE.

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | a metered credential present in the worker environment beside the subscription route | nothing in P0 — `billing_mode` was a pool attribute and no reader looked at the environment; this is the mode that falsified the design |
| 2 | a second gateway re-hosting the same vendor's model treated as a distinct vendor | only an adapter that happened to write `vendor`; no manifest bound gateway to vendor — falsifying mode two |
| 3 | a fourth provider needing Core changes | nothing — the adapter *was* the registry; falsifying mode three |

## Authority boundaries

Unchanged from what P1 states; this record decides nothing.

## Oracles, frozen before implementation

P0 froze three; none was implemented under P0. P1 carries them forward under new identifiers, and the
selectors below name the tests P1 owns, so that a reader following this record reaches the evidence.

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O1 | ACCEPTANCE | a third pool with `billing_mode: subscription` is eligible for a cross-provider leg | test_routing.py -k vendor |
| O2 | NEGATIVE | a pool whose billing mode is metered is refused | test_capacity.py -k cost_policy |
| O3 | MUTATION | the vendor-equality guard, deliberately broken, fails its oracle | test_routing.py -k mutation |
