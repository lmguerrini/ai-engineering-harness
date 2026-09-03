# Frozen budgets

**Frozen 2026-08-13, before Wave A execution.** Owner-approved defaults from the
governing prompt §3 and the architecture audit §3.0.5 / §11. These are counters,
not paragraphs: a capability that exceeds one stops and escalates (HITL row 8).
Changing a number here is a governance change and requires a recorded human
decision.

## Repair / audit budgets

| Counter | Bound | Scope | Set where |
|---|---|---|---|
| Repair attempts per finding | 3 | one finding | SCOPE.md, before the capability starts |
| Repair rounds per capability | 2 | one capability | SCOPE.md |
| Closure-audit cycles | 1 | one capability | SCOPE.md — no "one more round" |
| Oracle-correction cycles | 2 | per material invariant | SCOPE.md |
| Implementation attempts | 2 | per material invariant | SCOPE.md |
| Post-audit sibling-repair cycles | 1 | per material invariant | SCOPE.md |
| Auditor retries for external reasons | 1 | per audit cycle | SCOPE.md |

Rules that travel with the counters:

- **Identical retries do not consume budget.** A retry after an environmental or
  infrastructure failure (worker died at startup, quota exhausted, sandbox denied
  a write) is not a repair attempt. Classify first, then decide whether to charge.
- **An interrupted audit is INCOMPLETE, never clean.** It is re-run, and the
  re-run does not consume the audit cycle.
- **Exhausted budget with an open material finding is a stop** (HITL row 8), not
  a licence to continue at lower rigour.

## Bureaucracy budgets (two measures, one definition)

**(a) Held prose** — lines of skill + policy text the coordinator loads per
session. Templates, worked examples, and reference material are excluded because
they are pulled on demand, not held.

    Target: <= 2,000 lines
    Counted: skills/core/*.md + policy/*.md               <- inside the release
             + ~/.claude/skills/capability-closure/SKILL.md   <- adapters,
             + ~/.claude/skills/codex-worker/SKILL.md            outside it

The rule is unchanged, and the split is recorded rather than used to re-scope
the number: the two installed skills are loaded every session, so they count.
They are also **adapters, not authority** — outside the pinned release, covered
by no digest, and changeable without a pin noticing. So the pack can *measure*
them and cannot *freeze* them, and the measurement states both figures. Where an
adapter and the pinned pack disagree, the pinned pack wins.

**`policy/` holds what governs; `docs/` holds what happened.** Gate records, wave
results, audit and probe outcomes are read once, not held, so they live in
`docs/` — filing them here would inflate the count and pressure a coordinator to
delete live policy to make room for evidence. `observations.jsonl` is the
deliberate exception: `policy/` owns it because the routing table is regenerated
from it, and being non-`.md` it is not counted.

**(b) Overhead share** — tokens spent producing and consuming pack artifacts,
divided by total session tokens, measured per capability closure.

    Target: <= 15%

**On breach of either: delete before adding.** Measured at every capability
closure and at every pack-evolution session.

**Recorded in the measuring project's own `PROGRESS.md`**, never in a shared
file here. A per-project measurement written into the pack would be one mutable
file several concurrently-pinned projects wrote to — which breaks the pin (a
frozen release does not change during a run) and pools numbers from unrelated
work. RP2.1.0 pointed at `policy/overhead-measurements.md`, which never existed;
a pointer to a file nobody creates records nothing and reads as if it did. The
pack's own evolution sessions record theirs in the gate record for the version
they cut.

## Pack-construction cap

Waves A + B are capped at the pre-committed session budget in the governing
prompt. On breach: cut scope to toolbelt + existing skills + templates and start
the Pilot Run anyway (audit §11.1). If pack work is still ongoing with no real
project started after the cap, that is itself a mandatory HITL escalation with a
recommendation to ship as-is (§11.6).

## Session-scoped authorisation — pack-evolution sessions only (RP2.2)

The frozen table above is unchanged and continues to govern **project runtime**.
A recorded human decision may raise the repair and audit counters for a single
**pack-evolution session**, which is not a project run: it cuts a release rather
than delivering a capability against a pinned one, and it carries no consuming
project whose guarantees a longer repair loop could weaken.

Authorised sessions, each recorded in the gate record of the version it cut:

| Counter | RP2.2 | RP2.3 |
|---|---|---|
| Repair attempts per reproduced root cause | 12 | 12 |
| Repair rounds per capability | 8 | 8 |
| Closure / requalification cycles per capability | 4 | 4, raised to 8 mid-session |

RP2.3 repeated RP2.2's numbers rather than raising them, because RP2.2 did not
exhaust them and a ceiling nobody reaches records nothing. **Then RP2.3 reached
one.** The closure ceiling was raised to 8 part-way through, by recorded human
decision, after the fifth blind reading found that four of the fourth reading's
repairs were themselves defective — see `docs/RP2.3-GATE.md`. The raise is
spendable only to close a verified release-blocking defect or to delta-audit a
repair that changed a guarantee, never for reassurance, and it left the repair
counters alone.

That is the ceiling doing its job rather than failing: it stopped the loop and
put the decision to a person, which is what a number nobody can raise silently
is for.

Two rules survive the raise, because they are what makes the counters mean
anything:

- **Environmental and transient retries still do not charge budget**, and still
  have to be classified before that is decided.
- **Three consecutive failures on one root-cause hypothesis end that
  hypothesis.** Diagnosis reopens, the defect is reproduced again, and the next
  attempt uses a materially different strategy. A raised ceiling buys more
  distinct approaches, never more repetitions of one.

An authorisation is per session and is recorded in the gate record of the
version it cut. It does not carry forward, and it never applies to a project
running against a pinned release.
