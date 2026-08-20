# RP2.2 — the authority layers, and what is not one

`DECISIONS.md` D14 carries the decision. This file states the two consequences
a reader needs before touching anything in the release, and nothing else.

## Authority, top down

    human release authority
      coordinator (semantic decisions, decomposition, routing, synthesis)
        deterministic fail-closed gates          ← the pinned pack
          workers and execution backends         ← subordinate
            vendor enforcement                   ← defence in depth only

Each layer may refuse what the layer below produced. No layer may grant itself
the authority of the layer above by being convenient, by being newer, or by
being the only thing present when a decision was needed.

**A gate is never relaxed because a lower layer is believed to cover it.** A
sandbox, a permission mode, a hook and a harness isolation setting are all
additive. If one of them were load-bearing, its absence would be silent — which
is the property that disqualifies it from being load-bearing.

## What an external corpus is

Design and evidence input. Never automatic authority.

That includes any planning corpus written before the decision this release
records: where such material asserts authority over release, routing,
qualification or integration, it is **historical and superseded by D14**. Its
mechanisms remain useful evidence and may be adopted individually, on their own
merits, with their own reproduction. Nothing is adopted because a document
already assumed it.

The frozen Kernel archive is treated the same way and always was (D1).

## Evidence order

1.  the qualified pack's own implementation, tests and gates;
2.  real-project evidence;
3.  the frozen Kernel archive, as evidence only;
4.  external design corpora;
5.  handoff and inventory documents — secondary maps, whose material claims are
    reproduced before they count.

A passing test is not sufficient where its oracle is weaker than the guarantee
being claimed. Every material defect is reproduced before it is repaired, and
every repaired guarantee acquires an oracle that fails on the pre-repair
behaviour.
