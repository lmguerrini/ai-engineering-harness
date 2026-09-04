# DESIGN — C40 qualification identity, dynamic discovery and design-audit routing

**Change class:** MATERIAL
**Base revision:** ab7dea97a12c699e8123bcb5d5be976cd05c075e
**Frozen:** yes

Frozen against the 2.3.0 release commit, which contains none of the work this
governs. **Revision 2**, after two independent cross-vendor falsification reads
of revision 1 returned NOT SOUND — four blockers and nine majors between them,
every factual claim reproduced by execution before it was accepted. What those
readings changed is recorded in `docs/RP2.4-GATE.md`; what they changed *here*
is the key, the availability axis, the equivalence rule, the independence
predicate and all thirteen oracles. Verified with:

    python3 tools/capability_open.py <contract> --capability C40 \
        --change-class MATERIAL --mutation-begins-at <first implementation commit>

## The mechanism

`backend_contract.grades_from_observations` keys every qualification on
`(family, task_class)`, so an observation recorded against one model raises the
grade of every other model sharing its family string; this release adds a second
derivation keyed on an **evidence-relevant configuration identity** read from the
observation's own fields, adds a separate **availability** axis fed only by
observed dispatch outcomes, makes the coordinator's eligibility answer require
both, and leaves the family-keyed derivation in place as display-only prior
evidence that can never answer an eligibility question.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Leave the key at `(family, task_class)` and forbid pooling in prose | REJECTED | `policy/routing-policy.md` has forbidden pooling across configuration strings for two releases while `backend_contract.py` pooled across them. Executed against the shipped log and the shipped module, a model that has never run returns `qualified_for('blind_closure_audit_cross_vendor') == True` on seven observations, none of which recorded any observed model at all. Prose is not the mechanism here |
| 2 | `(family, exact model, task_class)` | REJECTED | Closes new-model-in-known-family and nothing else. Rows 37 and 38 of the shipped log are the same family, the same model, the same effort and the same isolation, and differ only in a dispatch precondition: one never started, the other validated. This key answers both from one observation |
| 3 | `(execution surface, family, exact model, task_class)` | REJECTED | Adds the surface, which is worth adding, and still pools effort, isolation and the adapter's tool contract. It also asserts that surface and family are separable in the existing log, where every recorded `family=` value names a client, so splitting them retroactively would invent a field the observations do not carry |
| 4 | Full evidence-relevant configuration identity over an OPEN dimension set | REJECTED | A key that grows whenever somebody thinks of a dimension fragments without bound. Including the client build alone would reset every qualification at each patch release, and neither falsification read could produce an A/B pair from this log where a build change altered an outcome — so that dimension would be fragmentation bought with no evidence |
| 5 | A CLOSED, REASONED nine-dimension qualification key, a SEPARATE availability axis carrying dispatch preconditions, and family history kept as display-only prior | SELECTED | It is the smallest key that separates every difference this evidence base has measured or already declared normative, and it puts each difference on the axis that difference actually belongs to: what a configuration *can do* is qualification, whether it *can start* is availability, and conflating them is what let one non-startable dispatch borrow a startable one's success |

### The two axes, and why the split is the repair

Revision 1 had one axis and put everything on it. Both readings broke it from
opposite directions: one showed a dimension excluded from the key that provably
changes whether a dispatch runs at all, the other showed the key being used as an
availability gate. They are different questions.

**QUALIFICATION — what this configuration can do once it is running.** Keyed on
nine dimensions:

| Dimension | Why it is in the key |
|---|---|
| `task_class` | D8 and `policy/routing-table.md`: a grade at one class is unprobed at every other. Already normative |
| `family` | Measured: one family is `contradicted` at analytical review and `provisional` at mechanical extraction |
| `surface` | The mechanism execution is reached through. `UNKNOWN` on every historical row, because the log's `family=` values name clients and no row can be split without inventing a value |
| `client` | The adapter, and with it the tool contract. A text-only adapter and a file-reading one can share every other dimension and differ in whether the task is performable at all |
| `observed model` | The defect this release exists for. Read from what the execution surface confirmed, never from what the dispatch requested |
| `effort` | Structural, not merely deeper: one rung on this surface turns on the vendor's own internal task delegation, which `policy/routing-policy.md` bans outright. A run at that rung is a different execution architecture |
| `isolation` | Measured: six of the eight confinement-ladder configurations failed environmentally under kernel confinement without reaching a model, and two validated. The same profile, different outcomes by family — which is why isolation and family are both in the key and neither is a proxy for the other |
| `network` | Recorded on all 41 observations, nearly determined by isolation on this surface, cheap to keep separate, and the alternative is silently merging a networked run with an airgapped one |
| `authentication class` | `policy/execution-boundaries.md` boundary 4 already says a mode that changes it is a *different backend* that does not inherit the other's qualification |

**AVAILABILITY — whether this configuration can start, here, now, under these
preconditions.** Keyed on the qualification identity **plus the declared dispatch
preconditions**, and fed only by observed dispatch outcomes. `stdin` is a
precondition, not a capability: rows 37 and 38 differ in nothing else, and one
never started. Discovery is an **input** to this axis and never a verdict on it —
measured live while writing this design, a model listed in the local discovery
cache was refused by the provider, and the same account listed a different model
set under each client version.

**Excluded from both keys on purpose.** `build` (client version): no A/B pair in
this evidence base shows a build change altering an outcome, and including it
resets every qualification at every update. Carried on the observation, reported
beside every grade, and reachable by a governed invalidation (below) rather than
by fragmentation. `pool_id`: a fact about capacity, which says nothing about
capability. The narrow claim is *no evidence in this base*, not *version
irrelevance*; the falsifier is named in the failure-mode table.

### The four rules that do the actual work

**COMPLETENESS.** An identity in which any keyed dimension is `UNKNOWN` is
INCOMPLETE, and so is one whose `identity_method` is not an admissible
observation method — `requested_only` is a declaration that the identity was NOT
observed, and an adapter that copies the requested slug into the observed field
has recorded a non-observation in an observation's shape. An incomplete identity
holds observations, is reported, and can never answer a qualification question
for a concrete configuration. No historical row records an observed model, an
authentication class or a surface, so **all 41 become prior evidence and none
becomes a track record**. Nothing is fabricated and nothing is deleted.

**ADVISORY IS DISPLAY-ONLY.** The family-level prior is printed beside an
unprobed answer and enters no ranking, satisfies no eligibility test and breaks
no tie. A prior that could rank is the family bucket back under a new name.

**EQUIVALENCE NEVER MERGES.** A declared alias surfaces the other identity's
evidence *as prior*, labelled, and never transfers a grade. Both readings found
the same laundering path through revision 1's reason-string rule, from opposite
directions; the repair is to remove the transfer rather than to police it.

**INDEPENDENCE IS DERIVATION, NOT CONFIGURATION.** Auditor independence is
checked on who produced the work — producer identity, session freshness, and
provider where a cross-vendor leg is required — never on qualification-key
equality. Key equality is wrong in both directions: the same session auditing its
own work has a *different* key once the task class changes, and two genuinely
fresh blind sessions have an *identical* one, which is exactly what
`AUDIT_PRIMARY` is.

### The cold start, stated rather than left implicit

An empty concrete table cannot acquire its first observation if qualification is
required before every dispatch. So an unprobed identity is selectable **only
through a declared probe**, whose outcome becomes evidence for the identity it
actually tested and for no other. A probe may not stand as a mandatory
independent audit leg (HITL row 12) and may not promote a worker into a critical
domain (row 16). Both rows keep their human.

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | A caller writes the requested model into the observed field and a configuration that never ran acquires a track record | Completeness requires an admissible `identity_method`, so a copied slug carrying `requested_only` is refused as loudly as an absent one; O4 supplies both shapes |
| 2 | Fragmentation leaves every configuration unprobed forever and a later release quietly widens the key | The dimension set is closed in code with a stated reason per dimension, so widening is a visible edit; and the probe path means unprobed is a starting state rather than a dead end |
| 3 | A declared alias launders evidence onto an unobserved model | Removed rather than policed: an equivalence produces prior evidence and never a grade. O7 asserts the grade does not move |
| 4 | A configuration is permanently `contradicted` by a client defect that has since been repaired, and can never be requalified | A governed invalidation declaration names a client version boundary and drops every observation before it. It is capped at `provisional`, so adverse evidence can never be deleted into a `confirmed`, and the report names the invalidation, its reason and how many observations it removed |
| 5 | Discovery is read as availability and a model in a stale cache is routed to, or one absent from it is wrongly excluded | Measured live in both directions during this design. Availability is observed dispatch outcomes only; discovery is advisory input. O5 asserts both halves: discovered-and-refused is ineligible, absent-from-discovery-and-currently-running is not excluded on that ground |
| 6 | A dispatch is selected under preconditions nobody observed it start under | Preconditions are part of the availability key, so `/dev/null` evidence cannot answer for `INHERITED` |
| 7 | The coordinator picks an "independent" auditor that produced the work | Independence is checked on derivation; O6 asserts both directions — same producer with a changed task class is refused, and a fresh session with an identical key is not refused merely for that |
| 8 | The dashboard renders a derived route as a stored fact and goes stale | Derived from the same functions in the same process on every render; nothing is stored; `UNKNOWN` renders as `UNKNOWN` |
| 9 | A future model generation ages the private vocabulary out, as `gpt-5` did | A generation-agnostic pattern replaces the literal, falsified against a corpus of current slugs, synthetic future slugs and legitimate public prose |
| 10 | An advisory prior is read as measured | Every candidate carries its evidence basis and its identity completeness, and an advisory-only candidate is labelled wherever it is printed |
| 11 | A client version really does change capability and this key pools it | Named rather than closed. The decisive falsifier: two otherwise identical complete configurations at builds v1 and v2 where v1 validates and v2 is contradicted. The invalidation declaration is the response when it appears; the exclusion is provisional on that evidence not existing |

## Authority boundaries

**It may decide:** which derivation answers a qualification question; whether an
identity is complete; what disposition a candidate carries; the order of a ranked
candidate list and the reason for it.

**It must never decide:** that a candidate is good; that a model may be used;
that a dispatch may happen; that a release may be cut. It reports, exactly as
`design_record` and `capability_open` report. It never launches a worker, never
contacts a network, and never writes the observation log on a worker's behalf.

**HITL row 7 IS ENGAGED, and revision 1 wrongly said it was not.** An independent
reader falsified the blanket claim and it is withdrawn.
`policy/routing-policy.md` states that evidence is never pooled across distinct
configuration strings. This design pools across two named non-identity fields —
the client build and the capacity pool — so it narrows a stated governance
control, in a release that widens the key from one dimension to nine. Net
tightening is still a change to a control, and the narrowing is recorded, named
and carried into the freeze procedure as a decision the founder takes, not one
this work takes. Rows 12 and 16 keep their human and are strengthened in the
direction they already point: the evidence behind a promotion becomes
per-configuration rather than per-family.

The new `requires.routing` contract key defaults to **false**, so no existing
project's capability open changes behaviour.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O1 | ACCEPTANCE | One validation grades `provisional`; two grade `confirmed`; two validations plus one same-key contradiction grade `contradicted` — and none of it reaches another task class | `tools/tests/test_qualification.py -k grades_and_stays_at_its_own_class` |
| O2 | ACCEPTANCE | A previously unknown identifier, including Unicode and punctuation forms, reaches a route report with no Core edit and no model vocabulary anywhere in the toolbelt | `tools/tests/test_model_discovery.py -k previously_unknown` |
| O3 | NEGATIVE | For EACH keyed dimension independently, changing only that dimension away from a twice-validated identity yields `unprobed` and no inherited grade | `tools/tests/test_qualification.py -k does_not_inherit_across` |
| O4 | NEGATIVE | Setting EACH keyed dimension independently to `UNKNOWN`, and separately recording `identity_method=requested_only` with the observed field populated, both yield no concrete qualification | `tools/tests/test_qualification.py -k incomplete` |
| O5 | NEGATIVE | Discovered-and-refused is ineligible; absent-from-discovery with a current successful run is NOT refused on that ground | `tools/tests/test_routing.py -k discovery_is_not_availability` |
| O6 | NEGATIVE | The producer of the work is refused as its own auditor even when the task class differs; a fresh independent session with an identical key is not refused merely for that; a same-provider pair is refused for a leg declared cross-provider | `tools/tests/test_routing.py -k independence` |
| O7 | NEGATIVE | A declared alias moves no grade — the target stays `unprobed` and receives labelled prior; an equivalence crossing family, surface, client or any non-model dimension is refused | `tools/tests/test_qualification.py -k equivalence` |
| O8 | MUTATION | Dropping ANY ONE of the nine keyed dimensions from the identity is caught — one mutant per dimension, each killed by a collision fixture built for that dimension | `tools/tests/test_qualification.py -k mutation_per_dimension` |
| O9 | MUTATION | Removing the availability axis from eligibility is caught, and so is substituting discovery membership for it | `tools/tests/test_routing.py -k mutation` |
| O10 | NEGATIVE | An advisory family prior never ranks a candidate, never satisfies eligibility and never breaks a tie; an unprobed identity is selectable only through a declared probe, and never as a mandatory independent audit leg | `tools/tests/test_routing.py -k advisory_never_ranks` |
| O11 | ACCEPTANCE | The publication vocabulary matches current and synthetic future generation slugs, covers everything the literal it replaces covered, and leaves legitimate public prose alone | `tools/tests/test_scan_vocabulary.py -k generation` |
| O12 | REHEARSAL | Starting from exactly the shipped 41 observations and zero complete identities, a synthetic consumer opens a capability, classifies design risk, discovers models, routes a design audit, probes, records, is interrupted, reconstructs from durable records alone with vendor continuation deleted, and closes | `tools/tests/test_adoption_rehearsal.py` |
| O13 | REHEARSAL | The same rehearsal closes with the newest model unavailable, unprobed, provisional, and outranked by an older one; and vendor continuation contradicting the durable record loses | `tools/tests/test_adoption_rehearsal.py -k without_the_newest or vendor` |
