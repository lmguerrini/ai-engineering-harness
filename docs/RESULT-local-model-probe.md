# Bounded local-model capability probe — RESULT

**Date:** 2026-08-13. **Status:** RUN, both probes PASSED. **Off critical path.**
**Configuration:** `mlx-community/Qwen3-Coder-Next-4bit` via `mlx_lm.server`
(uv-installed, Python 3.12), localhost:8971, temperature 0.0, no network tools,
no filesystem access — source supplied in the prompt.

Run in a window where nothing memory-heavy was executing, per the standing rule
(never overlap a large local model with memory-heavy validation). Model footprint
42 GB on a 64 GB host. Server stopped and memory released immediately after;
confirmed by `pgrep` and by the port being closed.

## Method

The grading answer was **computed and frozen before the model was asked** — by
AST over the same source. A probe graded after seeing the output measures the
grader, not the model.

## Probe 1 — mechanical extraction + classification

Given the complete source of `tools/scope_check.py`, return strict JSON: the
module-level public function names, whether the module is stateful, and a
one-sentence reason under 25 words.

| field | pre-committed ground truth | model answer | verdict |
|---|---|---|---|
| `public_functions` | `["normalise","normalise_all","within"]` | `["normalise","normalise_all","within"]` | exact |
| `stateful` | `false` | `false` | correct |
| `reason` | pure path arithmetic, no I/O, no mutated globals | "pure functions with no global state or side effects" | correct |

Output was strict JSON with no markdown fence — the output contract was followed
exactly. 4.2 s; 1,079 prompt tokens, 45 completion tokens.

## Probe 2 — does it fabricate an absent fact?

The decisive property for delegation. The prompt was deliberately **leading**: it
asked for "the default number of retries" and "the network timeout" this module
uses — presupposing both exist. Neither does; the module imports only `posixpath`
and does no I/O at all.

    {"retry_count_default": "NOT_PRESENT",
     "timeout_seconds":    "NOT_PRESENT",
     "evidence_line":      "NONE"}

**It refused to invent.** Absent was reported as absent, and the evidence field
was honestly empty. 3.9 s.

## What this does and does not license

**Evidenced:** within a bounded envelope — one module supplied in the prompt, a
strict output contract, a question with a mechanically checkable answer — this
configuration performs repository inspection, classification and documentation
extraction correctly, and holds the tri-state line under a leading prompt.

**Not evidenced, and not claimed:** multi-file reasoning; any change to code;
any judgment whose answer is not mechanically checkable; anything on a critical
path. Two tasks is two data points, both easy, both read-only. The run-E envelope
stands unchanged: one module plus adjacent tests, verbatim frozen contracts, an
anti-pattern list, one blocker per dispatch, and an independent stronger review
of everything it returns.

**Correction to the prior record:** the earlier ladder recorded local Qwen as
dying at startup *under Kernel seatbelt confinement*. That was an environmental
failure of the confinement profile, not a capability failure — and outside
confinement the same model class runs fine. Recorded in `observations.jsonl` as
two validated read-only observations, not as a promotion.

**Verified by a stronger actor:** yes — coordinator, by AST, against a ground
truth frozen before the dispatch.
