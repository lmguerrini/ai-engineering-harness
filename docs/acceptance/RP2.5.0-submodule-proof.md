# Repaired no-child submodule-read proof

## Result

The repaired composition passes **183 byte-exact answer rows** and reproduces
**25 frozen refusals** exactly: **208/208 corpus rows**. Every composed answer
recorded zero Git Trace2 `child_start` events. Every governed primitive has a
fresh, bound Trace2 witness: `version`, `start.argv`, and terminal `exit`
share one session id. All 12 positive controls are detected. Each primitive is
run through frozen 2.4.0's `gitread` boundary, so these 208 rows and 12 controls
establish the production `compose()` differential, not this candidate's `_run()`
integration.

The production composition is [submodule_no_child.py](../../tools/submodule_no_child.py);
the fixture builder, differential oracle, and Trace2 binder are
[rp2.5.0-submodule-differential.py](rp2.5.0-submodule-differential.py). The
frozen behavioral floor is selected with `FLOOR_FROZEN_ROOT`.

```sh
FLOOR_FROZEN_ROOT=/path/to/rp240 \
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
  python3 docs/acceptance/rp2.5.0-submodule-differential.py
# PASS: 208 matrix rows and 12 positive controls
```

## Repaired composition rule

1. `ls-files --stage -z` supplies every stage-zero index gitlink `I` and its
   record position. `ls-tree -rz HEAD` supplies its HEAD-tree gitlink `H`.
   They remain independent structural inputs, so a staged superproject
   gitlink is `H != I` even when the child is clean.
2. A sibling `ls-files --stage` read is paired record-for-record with the
   NUL-form read. Its path field is Git's own measured newline-form rendering
   under the governed configuration, including C quoting. Newline porcelain
   and raw diff use it; NUL status uses the raw path. Diff prefixes go inside
   the already measured quoted representation; no quote algorithm is guessed.
3. `lstat`, not a following existence test, classifies each worktree. Missing
   is deletion; a real directory with no `.git` is uninitialised. A symbolic
   link delegates the requested frozen form: that measured childless call
   retains frozen refusal or typechange rather than inventing an answer.
4. A directory-backed populated child is separately composed as top-level
   porcelain-v2 plus `rev-parse HEAD`, recursively by this same rule. These
   supply worktree HEAD `W`, tracked `m`, and untracked `u`; v2 uses the
   measured `S<c><m><u>` field. `diff-index HEAD` emits `H I M` when `H != I`.
5. Parent reads use `--ignore-submodules=all`. Generated gitlink records merge
   before the next greater stage-zero index position. This one index-order rule
   is used for status, patches, submodule summaries, and raw `diff-index`;
   untracked status has no index position and is not a splice heuristic.
6. Status removes `-z` only to choose the same grammar. Its renderer receives
   the separator and path source as parameters (`\n` plus rendered path, or
   `\0` plus raw path); NUL forms are not separate dispatch cases.
7. `diff --submodule=diff` remains frozen's pre-invocation refusal, with no
   structural read or output bytes on either side.

No configuration or `.gitmodules` value is read to identify gitlinks.

## Reviewer states now covered

| state | fixture | exercised result |
| --- | --- | --- |
| usable child through symlink | `symlinked-submodule-worktree` | recursive forms refuse exactly; raw `diff-index` preserves `160000 -> 120000` typechange |
| staged superproject gitlink | `staged-superproject-gitlink` | clean child with `H != I` emits `:160000 160000 H I M\tpath\n` |
| NUL public status forms | all fixtures, focused `nul-status-forms` | v1, v2, and short preserve exact NUL separators and raw paths |
| tab in gitlink path | `quoted-gitlink-path` | newline forms use Git's `"sub\\tmodule"`; NUL forms retain a tab byte |
| parent sorted after link | `ordered-parent-after-gitlink` | `sub` precedes `zzz.txt` in status, patch, summary, and raw output |

## Differential matrix

`P` is an exact frozen byte match, including final newline or NUL separator,
with a bound trace and composed child count zero. `R` is an exact frozen
refusal, so no answer bytes exist. There are no `F` cells.

| fixture | SP | SV2 | SS | SU | SID | D | DSM | DSD | DC | DI | SPZ | SV2Z | SSZ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean populated | P | P | P | P | P | P | P | R | P | P | P | P | P |
| dirty tracked content | P | P | P | P | P | P | P | R | P | P | P | P | P |
| untracked content | P | P | P | P | P | P | P | R | P | P | P | P | P |
| staged child content | P | P | P | P | P | P | P | R | P | P | P | P | P |
| unstaged child content | P | P | P | P | P | P | P | R | P | P | P | P | P |
| new child commit | P | P | P | P | P | P | P | R | P | P | P | P | P |
| detached child HEAD | P | P | P | P | P | P | P | R | P | P | P | P | P |
| nested submodules | P | P | P | P | P | P | P | R | P | P | P | P | P |
| uninitialised submodule | P | P | P | P | P | P | P | R | P | P | P | P | P |
| deleted submodule worktree | P | P | P | P | P | P | P | R | P | P | P | P | P |
| moved submodule worktree | P | P | P | P | P | P | P | R | P | P | P | P | P |
| symlinked submodule worktree | R | R | R | R | P | R | R | R | P | P | R | R | R |
| staged superproject gitlink | P | P | P | P | P | P | P | R | P | P | P | P | P |
| NUL status forms | P | P | P | P | P | P | P | R | P | P | P | P | P |
| quoted gitlink path | P | P | P | P | P | P | P | R | P | P | P | P | P |
| ordered parent after gitlink | P | P | P | P | P | P | P | R | P | P | P | P | P |

Key: SP = `status --porcelain`; SV2 = `status --porcelain=v2`; SS =
`status --short`; SU = `status --porcelain -uall`; SID = `status --porcelain
--ignore-submodules=dirty`; D = `diff`; DSM = `diff --submodule`; DSD =
`diff --submodule=diff`; DC = `diff --cached`; DI = `diff-index HEAD`; final
columns append `-z` to SP, SV2, and SS.

## Trace and child-process measurement

Each direct frozen call has a fresh trace. The composed side passes through a
wrapper which first requires the caller's trace overlay, then gives each
primitive a fresh trace destination. A primitive passes only if one `sid` has:

- a `version` event;
- a `start` event with the frozen-boundary argv, including injected
  `--no-ext-diff --no-textconv` when applicable; and
- a terminal `exit` event.

The wrapper validates every primitive, not merely a trace file written earlier,
then counts `child_start`. This detects the trace-laundering mutant: nine valid
earlier traces cannot hide a recursive call which dropped the caller overlay.

| representative state/read | frozen children | composed children | bound composed traces |
| --- | ---: | ---: | ---: |
| populated status/diff/diff-index | 1 | 0 | 9 |
| populated `diff --submodule` after child advance | 1 | 0 | 10 |
| nested populated status/diff/diff-index | 2 | 0 | 14 |
| ignore-dirty, cached, uninitialised, deleted, moved | 0 | 0 | 4 or 9 |
| symlink refusal/typechange | 0 | 0 | 4 |

All 183 answer rows have zero composed child starts. The 25 refusal rows are
also bound when Git starts; the `--submodule=diff` API refusal is recorded as
pre-invocation on both sides.

## Positive controls

| deliberate mutation | detecting fixture/read | result |
| --- | --- | --- |
| discard child tracked state | dirty tracked / status v2 | detected |
| collapse child staged/unstaged observation | staged child / child v2 | detected |
| suppress `C` for advanced child HEAD | new child commit / status v2 | detected |
| discard child untracked state | untracked content / status v2 | detected |
| replace index gitlink identity | new child commit / diff | detected |
| make recursive parent status call | clean / status porcelain | detected: 1 child |
| skip non-following symlink classification | symlink / status porcelain | detected: refusal mismatch |
| omit `H != I` raw record | staged superproject / diff-index | detected |
| render NUL as newline mode | NUL forms / status porcelain `-z` | detected |
| use raw path instead of measured rendering | quoted path / status porcelain | detected |
| append after tracked parent record | ordered parent / status porcelain | detected |
| drop caller trace overlay | clean / status porcelain | detected: trace binding fails |

## General rules, special cases, and gaps

All five repairs are general: index position drives every record merge; paired
`ls-files` measures every rendered path; `-z` only parameterizes a renderer;
`lstat` classifies every gitlink worktree; and `H` and `I` are consumed
independently.

The symbolic-link branch is explicit but not a list of read-specific output
templates: every requested form delegates after non-following classification,
because the frozen floor refuses or reports a filesystem typechange and that
direct operation is measured childless. The unsupported `diff --submodule=diff`
form is a retained frozen API refusal, not a composed answer.

No corpus state is left uncomposed. There is no closest-byte substitute to
report: all answers have exact frozen bytes, and every frozen refusal is a
refusal on the composed side.
