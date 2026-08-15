# Oracle discipline

**Applies to:** every material invariant. Applied by the COORDINATOR when
freezing SCOPE.md, and re-checked by AUDIT_PRIMARY at closure.

A material invariant is one whose violation is silent, expensive, or
irreversible: data integrity, concurrency, migration, security boundaries,
public contracts, money, anything a human would have to accept as a limitation.
Routine work does not need this ceremony. Do not spend it where it does not pay.

---

## The rule this exists for

> A frozen, mutation-tested oracle over the **wrong domain** is worse than no
> oracle, because it is believed.

Four consecutive audit rounds passed a green gate while material defects
survived. The controls did not fail to execute — they executed and were
insufficient. Every surviving bypass lived where the oracle's **domain
derivation** was wrong, not where its assertions were weak.

Mutation testing cannot detect this. Mutating code the domain never reaches
changes nothing, so the oracle stays green and the gate reports success.
**Coverage of a domain the oracle never enters is not coverage.**

### The failure shape, three times

| Domain was derived from | The actual mechanism | Consequence |
|---|---|---|
| functions that split a cursor's metadata from its rows | identical query text sharing one connection | ~40 readers sat outside the tested domain |
| probes run with site initialisation disabled | interpreter startup hooks | the breaking route was unreachable by construction |
| cases with two initialised owners | the single-owner fallback branch | the discriminating branch never executed |

Each enumeration was mechanically flawless **over the wrong question.**

---

## The sequence — in this order, no steps merged

1. **Name the MECHANISM.** One sentence, in terms of what the machine actually
   does, before any test is written. Not the symptom. Not the site the auditor
   named. If you cannot state the mechanism without naming a file, you have a
   symptom, not a mechanism.
2. **Derive the domain FROM the mechanism.** The domain is every construct that
   can exercise that mechanism — not every construct that resembles the example.
3. **Enumerate the domain mechanically** where the mechanism admits it (an AST
   sweep, a query over the build graph). Hand-written lists are for domains too
   small to be wrong about. Record the enumeration's own question verbatim, so a
   reader can check it is the right one.
4. **PROVE BY EXECUTION that the oracle reaches the mechanism.** This step is
   mandatory and is the one the Kernel never had. Inject a deliberate fault *at
   the mechanism* and require the oracle to go **RED**. A coverage probe or a hit
   counter at the mechanism site is acceptable evidence. If injecting a fault at
   the mechanism does not turn the oracle red, the oracle does not test the
   mechanism — however green, however frozen, however mutation-tested.
5. **Establish RED on the unrepaired condition.** Run the oracle against the
   current, unrepaired code and capture the failure output as evidence. An
   oracle that has never been red has never been shown to be able to fail.
6. **Freeze the oracle by content digest.** sha256 the test file; record it in
   the capability's evidence. This makes "the implementer edited the test"
   structurally impossible to do accidentally. Cheap; it worked every time.
7. **Repair.** The implementer never touches the oracle. Repair the **class**,
   not the site — and the class is the one you named in step 1.
8. **GREEN, with the digest re-verified unchanged.** Green with a changed digest
   is not a pass; it is a finding.
9. **Sibling mutation.** Re-introduce the *named-site-only* repair — the fix that
   would have been made if the class had been read as the symptom — and require
   the oracle to go red. This directly targets the historical failure and caught
   it 3/3 in both directions. It is a hard rule, not a habit.
10. **Independent falsification.** A different actor, barred from the design
    documents and repair reports, attempts to write an **obviously-wrong
    implementation that passes the oracle**. This is cheap and load-bearing: it
    is how an unguarded failure clause was found in a test that was green,
    frozen, and reviewed.

---

## Standing rules

- **A surviving mutation may be correct.** Redundant mechanisms legitimately
  absorb some mutations. Analyse each survivor and record why it survived. Never
  chase a score. The only mutation report worth reading is the one that explains
  the mutations that did **not** fire.
- **State the class before enumerating it.** Repair the class; do not enumerate a
  symptom and call the result completeness.
- **Green is "no known defect", never "no defect."** A passing gate never
  substitutes for an adversarial reader.
- **A consumer may never re-derive a fact the authority declined to answer.** If
  the authority says "I cannot tell", the consumer refuses or asks a different
  question. It does not compute its own answer.
- **Implementer-authored tests are never sole acceptance**, and pre-existing
  contract tests must run. Some defects — a plain unhandled index error in
  delegated code — are caught by no tool and no prompt. They are caught by this
  rule.
- **Enumerate a guard's dependency edges as a table before writing its tests,
  including the edges the current change does not exercise.** An invalidation or
  cache guard is naturally demonstrated on the change its author has in hand,
  and that change is by construction one the guard already handles — otherwise
  the author would have noticed. A freshness guard was demonstrated live and
  correctly while **three of four dependency edges were missing**, and the
  demonstration passed anyway. Three successive passes over that subsystem each
  looked right and each left a real hole. The table is the design; the
  demonstration is not.
- **Provenance is reported by the component that did the work, or verified
  against it.** A field assembled from configuration describes an *intention*; a
  field reported by the executing code describes a *run*. Model revisions were
  recorded as pinned in every provenance seal while only one of three was
  actually passed to a loader — nothing failed, no test caught it, and the drift
  made the record read *stronger*. The same shape reported the machine's best
  accelerator, because the seal asked the machine rather than the stage.
- **"Recorded" and "enforced" are different claims**, and the gap between them
  is invisible precisely because the record reads as confirmation.

## Evidence package (per material invariant)

One Markdown file under the capability's `evidence/`, stated generically: the
invariant; the **mechanism**; the derived domain and the question the enumeration
asked; the fault-injection proof that the domain reaches the mechanism; who
played designer / writer / implementer / auditor; the frozen digest before and
after; the RED evidence; mutation results **including the mutations that did not
fire and why**; budget consumed.

## Right-sizing (do not over-apply)

Separation of actors costs real tokens — one 18-line repair once consumed a
959-line frozen oracle, five probes and eighty-five calibration trials. Scale it:
**always**, implementer-authored tests are never sole acceptance; **material
invariants only**, independent oracle design and write, the
domain-reaches-mechanism proof, sibling mutation on repairs; **deferred**, the
full four-actor ceremony, until a real project shows it pays.

In the recorded history the dominant error source was the **coordinator's own
specification**, not the workers. Catching that is separation's real value.
