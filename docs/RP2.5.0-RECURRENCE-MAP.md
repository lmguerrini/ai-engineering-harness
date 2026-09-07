# RP 2.5.0 — what fifteen repairs of one boundary were actually evidence of

Input to the 2.5.0 architecture, written before any 2.5.0 design. It reads the
2.4.0 audit blockers, the 2.4.1 repair cycles and the certification that stopped
them, and asks one question of the set rather than of each row: **what did every
one of these repairs assume?**

Sources, all independently produced. Three ship inside this release and are
inspectable from a checkout: `docs/RP2.4.1-GATE.md`, the eight frozen
`RP2.4.1-DESIGN-*` records, and the history of `evolution/rp2.4.1` at `71e24f8`.
Two do NOT ship and cannot be inspected from a checkout — the coordinator's
cycle-by-cycle handoff, and the whole-candidate certification of `71e24f8` that
returned `NOT_READY`; both are session records held outside the release envelope.
An earlier draft said every source was "on disk", which a reader with only this
release could not confirm, because the path it named is not in this tree.

## The map

| # | Symptom | Mechanism 2.4.1 assumed | Mechanism Git actually has | Why the oracle missed it | Implication |
|---|---|---|---|---|---|
| R4 | three keys excused as "reachable only through `--filters`" | a key is dangerous only on the paths this module thought of | ordinary `diff` applies them | the oracle exercised the paths the author listed | a closure's *reach* was never measured |
| B1–B4 | Git answered about a directory nobody asked about | `cwd` names the subject | Git discovers upward from `cwd` | no test asked from inside a different repository | the subject of a read was implicit |
| B5 | `extensions.worktreeConfig` applied but invisible to `git config --local --list` | scope can be inferred from the extension key's presence | `config.worktree` is a scope Git reports, not one you deduce | the inspection was tested against what it wrote, not against Git | the module inferred where a value came from |
| B5′ | then refused two repositories real Git reads | a failed second read means the extension is off | the extension and the file are independent facts | the fixture never had an enabled extension with no file | inference produced BOTH under- and over-refusal |
| B6 | a config subsection that is not valid UTF-8 raised `UnicodeEncodeError` | a config listing is text | Git reads it at rc=0 and hands back bytes | every other `-z` enumeration read bytes; this one did not, and nothing compared them | a refusal that names no cause is not a refusal |
| B7 | `core.sshCommand` excused "unless ssh is enabled" | a closure's condition is documentation | the transport code removed exactly that neutralisation | no oracle exercised the closure *with the condition true* | a conditional closure was asserted unconditionally |
| B8 | repository's `protocol.<name>.allow` beat the reader's `protocol.allow = never` | a general refusal contests a specific enablement | they are **different keys**; command scope only outranks the *same* key | the oracle set the general key and never the specific one | the subject chose the policy applied to it |
| B9 | `protocol.Review.allow` written, `protocol.review.allow` read | Git folds config names to lower case | it folds section and variable, and keeps the **subsection verbatim** | the fix read the key off its own lowercased copy, so subject and oracle agreed | a spelling was predicted rather than observed |
| B10 | `file` enabled, repository declared `File`, helper ran | two spellings of a transport are one transport | `git-remote-File` is a different program from `git-remote-file` | **found by mutation, not by review**: every test passed either way | case folding was predicted rather than observed |
| B12 | a nested repository's configuration applied and was never inspected | the subject of a read is one repository | Git opens every repository it reaches | the fixture had one repository in it | the inspection's subject was too small |
| B13 | a closure asserted where its mechanism does not reach | a flag added somewhere is a flag in force | a flag is in force on the command line it is on | closures were tested on the verbs they were written for | reach was a property of the module, not of Git |
| B14a | `diff.*.textconv` excused by `--no-textconv`; `git status -v` runs it | the flag covers the verbs that apply the driver | `status` does not accept `--no-textconv` **at all** | no oracle ran a closed key on a verb outside `EXTERNAL_PROGRAM_VERBS` | a closure named a mechanism that cannot reach its own claim |
| B14b | a nested repository absent from the index was never inspected | the index lists the nested repositories | Git opens `<path>/.git` **from the working tree** | `_gitlink_paths` was tested against repositories it had put in the index | the walk enumerated the wrong set |
| B15a | `-vv`, `--verb`, `--verbo` execute the textconv helper | option spellings are the two strings written down | Git accepts any unambiguous abbreviation and repeated short flags | the oracle used the two spellings the code matched | **an option spelling cannot be enumerated** |
| B15b | an ignored, never-a-submodule checkout makes the whole project unreadable | every directory containing `.git` is configuration Git will apply | Git applies the configuration of repositories it *opens*, which that is not | the fixture's nested repositories were all ones Git really opened | **over-refusal is the same defect as under-refusal** |

Independently reproduced in this session against Git 2.50.1 before being accepted:
B15a — and a **third** unenumerated spelling, `--verbo`, that no reader had reported;
B15b — `workspace_report.classify_workspace` raising `IntegrityError` where real Git
exits 0. The reproduction is `<scratch>/repro/b15.py`.

## The one assumption

Every row above is the same move. The module answered a question about **Git's
behaviour** by consulting **its own description of Git's behaviour** — a list of
keys, a list of verbs, a list of flags, a list of transports, a list of spellings,
a list of nested paths. Each repair corrected one description and added another.

Two properties of that architecture explain why eleven cycles did not converge:

1. **The lists are open sets.** Keys, remote-helper names, option abbreviations
   and repository layouts are all things Git can add without telling anyone. A
   proof of safety that requires one of them to be complete is not a proof.
2. **The failure mode is fail-open.** A denylist that misses an entry runs a
   program. So every incompleteness is a security defect, and every repair that
   narrows a list to stop over-refusing widens the hole — which is exactly the
   B5/B15 pair, under-refusal and over-refusal produced by the same edit.

## The hypothesis this release tests

> Enumerating or predicting Git's execution and configuration semantics is not a
> convergent security architecture. The authority boundary must rest on a smaller
> invariant that Git itself supplies or that an isolated execution environment
> enforces — one whose incompleteness makes a read **fail**, not **execute**.

The architecture tournament that tests it is `RP2.5.0-DESIGN-A1-sterile-execution.md`.
