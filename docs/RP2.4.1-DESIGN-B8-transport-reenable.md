# DESIGN — RP2.4.1: the subject of a read must not choose the transport policy

**Change class:** MATERIAL
**Base revision:** 19565cad519bdbb0665969913e1a58fe093e3345
**Frozen:** yes

Read by `tools/design_record.py`. This record authorises nothing.

## The reproduced defect

`_config_environment` refuses transports with `protocol.allow = never` at command
scope and names the ones a caller enables. Its docstring reasons:

> Git consults the specific key first and falls back to the general one, so every
> transport the caller did not name stays refused

The first clause is true and the conclusion does not follow, because **the
repository can set the specific key too**. `protocol.allow` and
`protocol.ext.allow` are different keys, so command scope never contests the one
Git actually consults.

Reproduced against real Git, marker on disk, with **no transport enabled by the
caller at all** and `ext` not even in `ALLOWABLE_TRANSPORTS`:

    git config protocol.ext.allow always
    git remote add origin "ext::/path/to/program %S"
    gitread.probe(repo, "ls-remote", "origin")   -> the program RAN

`program_valued_config` reported `[]`, because `PROGRAM_VALUED_CONFIG` describes
keys whose *value* is a program and never a key that *re-enables a transport*.
An independent certification reproduced the same route through
`publication_gate.verify_remote` with a program that speaks the protocol, so the
repository being verified answered its own publication postcondition.

It also falsifies a closure stated as unconditional:
`"core.gitproxy": "unreachable: the git:// protocol is not enablable"`. The
repository enables it.

Present in frozen 2.4.0 as well, so this is a standing hole rather than a 2.4.1
regression — but it is reachable in this candidate, it is undisclosed, and the
records state it as closed.

## The mechanism

Command scope wins for the **same** key; confirmed against real Git
(`protocol.ext.allow=never` at command scope over repository `always` gives
`fatal: transport 'ext' not allowed`). The repository's own `protocol.*.allow`
keys are already visible, by scope, in the listing the inspection reads. So every
such key the repository sets is pinned to `never` at command scope, except a
transport the caller deliberately enabled.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Add `protocol.*.allow` to `PROGRAM_VALUED_CONFIG` so a repository setting it is refused | REJECTED | Fails closed, but refuses every governed read of a repository that merely records a transport preference, including ones where nothing could execute. That is the over-refusal class this release has already repaired twice, and it answers a policy question with a refusal when the policy can simply be enforced |
| 2 | Pin `protocol.<name>.allow = never` at command scope for a fixed list of known transport names | REJECTED | Closes the reproduced cases and leaves the shape open: `protocol.<name>.allow` accepts any remote-helper name, so the list is a guess about what Git will accept next. The same enumerate-what-might-exist mistake this release removed from the configuration inspection |
| 3 | Pin at command scope exactly the `protocol.*.allow` keys the **repository itself** sets, minus the transports the caller enabled | SELECTED | Uses Git's own precedence rather than reasoning about it, needs no list of transport names because the names come from the subject, refuses nothing that was legitimate, and makes the docstring's claim and the `core.gitProxy` closure true instead of aspirational. The keys are read from the listing the inspection already takes, so no extra read is added |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | A transport is enabled by a mechanism other than `protocol.*.allow` | Out of this design's claim; the general `protocol.allow = never` still applies, and an oracle pins that an unenabled transport stays refused |
| 2 | The pinning is applied to the enabled transport too, so a legitimate caller is broken | An acceptance oracle keeps `publication_gate` verification working over an enabled transport |
| 3 | The repository sets the key in `config.worktree` rather than `config` | The keys are taken from the scope-labelled listing, which already covers both, and an oracle places one there |
| 4 | The extra reads cost a second inspection per call | The protocol keys come from the same listing as the program-valued keys; a regression here shows as a second `config` invocation |

## Authority boundaries

Reports and refuses; opens nothing, weakens no row of `policy/hitl-matrix.md`,
adds no contract key or CLI input. It removes an execution route the records
already claimed was closed, so it enforces a promise rather than making one.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O1 | NEGATIVE | a repository re-enabling `ext` cannot make Git run its program | tools/tests/test_gitread.py::test_a_repository_cannot_re_enable_a_transport_the_reader_refuses |
| O2 | NEGATIVE | the same, declared in `config.worktree` | tools/tests/test_gitread.py::test_a_worktree_declared_transport_re_enable_is_pinned_too |
| O3 | NEGATIVE | `git://` stays unenablable, which `core.gitproxy`'s closure asserts | tools/tests/test_gitread.py::test_the_git_protocol_closure_is_true_because_the_repository_cannot_enable_it |
| O4 | ACCEPTANCE | a transport the caller enables still works | tools/tests/test_publication_gate.py::test_remote_verification_still_reads_an_enabled_transport |
| O5 | NEGATIVE | the publication path cannot be answered by a repository-chosen program | tools/tests/test_publication_gate.py::test_remote_verification_refuses_a_repository_re_enabled_transport |
| O6 | MUTATION | dropping the pinning restores the reproduced execution and must fail O1, O3 and O5 | tools/tests/test_gitread.py::test_a_repository_cannot_re_enable_a_transport_the_reader_refuses |
| O7 | MUTATION | pinning every transport, including the enabled one, must fail O4 | tools/tests/test_publication_gate.py::test_remote_verification_still_reads_an_enabled_transport |
