# DESIGN — RP2.6.0 P1: an N-provider registry of declared manifests, billing safety as a route proof, and capacity that says how fresh it is

**Change class:** MATERIAL
**Base revision:** c2fcf9cedf178dd00491c52748e6897e5d4fe9be
**Frozen:** yes

Written before the implementation it governs; read by `tools/design_record.py`. It reports; it authorises
nothing. It supersedes `RP2.6.0-DESIGN-P0-third-provider-slot.md`, whose falsification it records.

## The evidence this design answers

Read at the release boundary, not summarised: the cross-vendor audit leg is qualified on one
configuration on one shared account-level pool; every failover was a human decision; cross-pool routing
was being re-implemented outside the pack; projects extended the pack's capacity record with the
freshness and provenance fields they needed and the frozen reader refused the record, so the shared
console showed capacity and coordinator positions UNKNOWN; the pack's only official capacity observer
never produced a machine reading in the desktop workflow, and a client-local file that stops sampling
when idle cost hours of critical path while an old percentage read as current.

## The mechanism

**A provider is one declared manifest; Core validates, joins and reports; the coordinator chooses.**

*   A project declares each provider it may route to as a manifest file (`PROJECT.yaml providers:`),
    schema `runtime-pack-provider-1`, closed vocabularies, unknown keys refused, digest-pinned the way an
    adapter is. The manifest binds `provider_id` (the gateway/account one contracts with) to `vendor` (whose
    model it is), the execution surfaces and their protocol (`anthropic-compatible` or `openai-compatible`;
    a protocol outside this vocabulary is refused, and adding one is a Core change stated here rather than
    hidden), the adapter id, the credential *reference* (never a value), the billing pool and mode, the
    capacity observer configuration and the private terms the publication scan must learn.
*   **Independence is computed on the producer's derivation, by vendor.** `Derivation` gains `vendor` and
    `gateway`; a leg declared cross-provider is refused when both sides share a vendor, whatever gateway
    served them, and when either side's vendor is unknown. The nine keyed qualification dimensions are
    untouched; `family` is read as the model vendor by convention and `client` carries the gateway, so a
    re-hosted model keys a different configuration and the same vendor.
*   **Billing safety is a proof about the exact route, not an attribute.** A route is routable as
    `subscription` only when every field of its fingerprint — provider, gateway, endpoint or client,
    credential reference, billing pool, billing mode, the authorising decision, and the three negative
    facts `overage_enabled = false`, `auto_topup_enabled = false`, `metered_fallback_enabled = false` — is
    positively established. `billing_mode ∈ {subscription, local, prepaid_existing, metered_api}`; anything
    else is UNKNOWN and UNKNOWN is HARD DENY. The project's `cost_policy` names the authorised pools and the
    disposition of each mode; `capacity.gate` checks it before any arithmetic; no reroute may name a metered
    pool; exhausted quota lists only authorised subscription or local alternatives, or PARK.
*   **Capacity says how fresh it is.** One normalised observation shape for every pool — source, provenance,
    horizon, `freshness ∈ {FRESH, STALE, UNKNOWN, UNAVAILABLE}` computed at read time, and every window the
    source exposes with a percentage only where the denominator is established and native units otherwise.
    `capacity_record.py` is the only writer of `CAPACITY.json`; `resource_observation.py` reads the
    documented sources; a bounded `--refresh-claude` renders the official client once at a boundary so the
    status-line hook can append a reading, and reports UNAVAILABLE when it cannot. Nothing polls.
*   **Readers quarantine instead of refusing the whole record.** A malformed observation row or a wait the
    reader cannot trust is reported, counted and BLOCKS closure; the rest of the record derives. A wait of a
    gate kind must carry a deadline and a cadence; a stopped process derives PAUSED, not RUNNING. An adapter
    whose driven binary drifted from its qualified version reports PROBE_REQUIRED when a function-probe basis
    is declared, and the probe is a declared dispatch. Sterile scratch is removed on every path, immutable
    flags included, and a sweep reports what it removed.
*   **The dashboard renders what the projects publish.** Five documented evidence keys a project authors
    from its own governed metrics become one card per active project; the normalised capacity figures become
    one strip; anything unsupported is UNKNOWN. The console decides no figure.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | P0: a provider-specific adapter and `billing_mode` on the pool | REJECTED | a fixed slot; billing as a claim; a fourth provider is a Core release (falsification recorded in P0) |
| 2 | a generic provider runtime in the pack that dispatches, cancels and meters workers | REJECTED | D14 clause 11; the pack would have to know every provider, and a runtime that meters is a runtime that decides |
| 3 | vendor and gateway as keyed qualification dimensions | REJECTED | founder conditions 8 and 9 (`docs/RP2.4-FOUNDER-AUTHORISATIONS.md`) forbid a tenth dimension and a third pooled field; the derivation already carries independence |
| 4 | a machine-level registry directory every project reads | REJECTED | global mutable state shared by concurrently pinned projects (D13, D14 clause 7); a project declares what it may route to |
| 5 | declared manifests, vendor independence on the derivation, billing as a route fingerprint checked before dispatch, one capacity contract with freshness, quarantining readers, a rendering-only dashboard (this record) | SELECTED | every piece is a validation, a join or a refusal over records the project already owns; N is unbounded because each provider is data; the coordinator keeps every choice |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | a manifest names a protocol or a billing mode outside the vocabulary | refused at validation (O2) |
| 2 | a metered credential is present beside the subscription route | fingerprint field `metered_fallback_enabled` cannot be established false → NOT ROUTABLE (O5) |
| 3 | a registered provider is treated as routable because it is registered | `authorised_by`, credential reference, observer and qualification are each required; the dormant fixture proves NOT_ROUTABLE (O1, O3) |
| 4 | two gateways of one vendor pass as cross-vendor | vendor equality refuses (O4) |
| 5 | an old capacity sample renders as current | freshness computed at read time against the horizon; frozen-source oracle (O6) |
| 6 | a window whose denominator is unknown is shown as a percentage | percentage emitted only with a denominator; native values otherwise (O7) |
| 7 | a bad row or wait hides the whole position | quarantine with a blocking count (O8) |
| 8 | a stopped job reads as progressing | state T → PAUSED (O9) |
| 9 | a helper's `--help` rewrites a record | read-only-mode oracle over every touched tool (O10) |
| 10 | the dashboard invents a completion figure | it renders declared keys or UNKNOWN; a legibility oracle checks both (O11) |
| 11 | a status-line render cannot be produced headlessly | bounded limitation: the path reports UNAVAILABLE and the Desktop file or a human reading, each with its horizon, is what remains — stated, not hidden |

## Authority boundaries

This design may: validate a manifest, derive eligibility, independence, freshness and cost-policy
compliance, refuse a dispatch the policy or the window cannot carry, quarantine a record element, and
render. It must never: dispatch, end or restart a worker; choose among eligible candidates; substitute a
provisional configuration into a mandatory leg; derive a completion or an ETA; enforce a priority between
projects; or run as a daemon. It weakens no row of `policy/hitl-matrix.md`: row 3 keeps credentials and any
spending human, row 12 keeps the mandatory certification source human, row 4 keeps ending a worker human.
Rows touched as governance changes are recorded in `DECISIONS.md` D29–D36 (row 7), each with the founder's
decision of 2026-09-19.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O1 | ACCEPTANCE | a manifest of a family Core has never seen registers unchanged and is UNPROBED + NOT_ROUTABLE until authorised, credentialed, observed and qualified | test_provider_manifest.py -k dormant |
| O2 | NEGATIVE | a manifest with an unknown key, a protocol or billing mode outside the vocabulary, or a billing pool equal to its provider id is refused | test_provider_manifest.py -k refuse |
| O3 | NEGATIVE | registration alone routes nothing; `authorised_by: null` → NOT_ROUTABLE for PROBE, ROUTINE and CRITICAL | test_routing.py -k not_routable |
| O4 | NEGATIVE | two gateways of one vendor are refused for a cross-provider leg; UNKNOWN on either side refuses; distinct vendors pass | test_routing.py -k vendor |
| O5 | NEGATIVE | poisoned environments: generic and PAYG credentials present never make a denied or unauthorised route eligible; a missing subscription credential fails closed; a reroute to a metered pool is refused before arithmetic | test_provider_manifest.py -k poisoned; test_capacity.py -k cost_policy |
| O6 | NEGATIVE | a frozen source past its horizon derives STALE/UNKNOWN for every window, never FRESH; a re-emitted old sample does not advance observed_at | test_resource_observation.py -k frozen |
| O7 | ACCEPTANCE | a window with a native limit and remaining yields percentages; one without a denominator yields UNKNOWN percentages and preserved native values; an unexposed window is UNAVAILABLE | test_resource_observation.py -k window |
| O8 | ACCEPTANCE | a malformed row or wait is quarantined and counted, the rest derives, and a non-zero count blocks closure | test_qualification.py -k quarantine; test_background_governance.py -k quarantine |
| O9 | ACCEPTANCE | a gate-kind wait without a deadline is refused; a stopped process derives PAUSED | test_background_governance.py -k paused |
| O10 | NEGATIVE | every touched tool's read-only modes and one unrecognised flag leave a fixture governance tree byte-identical | test_readonly_modes.py |
| O11 | ACCEPTANCE | the Overview renders the five declared keys and the capacity strip, and UNKNOWN wherever a key is absent or malformed | test_dashboard_contract.py -k overview |
| O12 | MUTATION | the vendor-equality guard, the fingerprint's UNKNOWN-is-deny rule and the freshness horizon, each deliberately broken, are demonstrated to fail their oracle | test_routing.py -k mutation; test_provider_manifest.py -k mutation; test_resource_observation.py -k mutation |
| O13 | REHEARSAL | an adopting project with three families runs open → eligibility → capacity → closure without a vendor name in Core | test_adoption_rehearsal.py -k third_family |
