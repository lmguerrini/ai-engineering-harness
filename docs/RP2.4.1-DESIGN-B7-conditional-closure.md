# DESIGN — RP2.4.1: a closure that holds only sometimes is not a closure

**Change class:** MATERIAL
**Base revision:** 351f597865a9cd14dd16edeaf82af95e286d1900
**Frozen:** yes

Read by `tools/design_record.py`. This record authorises nothing.

## The reproduced defect

`CLOSED_PROGRAM_KEYS` excuses a program-valued key from the safety inspection
when this module can show Git will never run it. One entry excuses itself on a
condition and is then applied unconditionally:

    "core.sshcommand": "neutralised, and removed only when ssh is deliberately enabled"

The standing configuration does neutralise it. But `_transport_settings` **pops
that neutralisation** when a caller enables the `ssh` transport, which exposes
the repository's own value — and the inspection still skips the key, because the
closure does not know the condition it names.

Reproduced against real Git, with no network, no socket and no ssh binary: a
repository configuring `core.sshCommand` to a local program had that program
executed through this module's own hardened reader by
`publication_gate.verify_remote`, while `program_valued_config` reported `[]`.
An independent certification reproduced the same path and showed the fabricated
answer can additionally be read as a clean publication verification.

This is the class this release already closed three times: a key called closed on
a premise that does not hold on every path. The earlier three claimed
reachability "only through `--filters`", which ordinary `diff` disproved.

## Scope, established mechanically

- `core.sshCommand` is the ONLY conditionally-removed override (one `pop`).
- It is the ONLY closure whose stated reason contains a condition.
- Exactly one caller enables the transport: `publication_gate.py:511`.

Every other closure is unconditional: neutralised in the standing config, or
structurally unreachable.

## The mechanism

`_run` already receives `allow_transports` and already calls the inspection; it
simply does not pass one to the other. The enabled transports are handed to
`program_valued_config`, which drops from `CLOSED_PROGRAM_KEYS` any entry whose
neutralisation this invocation removes — today exactly `core.sshcommand`, and
only while `ssh` is enabled. The key then falls to the ordinary rule that an
unclosed program-valued key refuses the read, naming the key and the transport.

## Designs considered

| # | Design | Verdict | Why |
|---|---|---|---|
| 1 | Stop popping; pin `core.sshCommand` to Git's default `ssh` instead | REJECTED | Makes the closure true, but silently discards a legitimate per-repository SSH wrapper. The operator's configured command stops running with nothing said, which trades an execution defect for a silent behaviour change — and this module reports rather than alters |
| 2 | Remove `core.sshcommand` from `CLOSED_PROGRAM_KEYS` outright | REJECTED | Over-refuses. Every ordinary local read of a repository that merely has an SSH wrapper configured would be refused, though the override is applied there and the program genuinely cannot run. That is the refuse-what-Git-reads-fine defect this release has already repaired twice |
| 3 | Make the closure conditional exactly where its own reason says it is: the inspection learns which transports this invocation enables, and `core.sshcommand` is closed only while its neutralisation is actually applied | SELECTED | The condition is already written in the closure's reason and already known at the call site — `_run` receives `allow_transports` and does not pass it on. A repository declaring the key is refused for the SSH operation, with a cause naming it, and reads normally otherwise. Nothing is silently altered and nothing correct is refused |

## Failure modes of the selected design

| # | Failure mode | What keeps it from being silent |
|---|---|---|
| 1 | A future caller enables ssh without routing through this parameter | The parameter is the same one that enables the transport, so there is no second path to forget; enabling ssh is what informs the inspection |
| 2 | Another override becomes conditional later | The closure reason and the condition live together, and a test asserts that the only conditionally-removed override is the one this design covers |
| 3 | The refusal is mistaken for a network failure | It is an `IntegrityError` naming the key and the transport, not a probe answer, so it cannot be read as "the remote said no" |
| 4 | Ordinary reads start refusing | An acceptance oracle keeps a repository with `core.sshCommand` reading normally when ssh is not enabled |

## Authority boundaries

Reports and refuses. It opens nothing, weakens no row of `policy/hitl-matrix.md`,
and changes no contract key or CLI input. Behaviour that previously executed a
repository's program and now refuses is the repair, not an incompatibility.

## Oracles, frozen before implementation

| ID | Kind | The property it settles | Selector |
|---|---|---|---|
| O1 | NEGATIVE | a repository's `core.sshCommand` is not executed when ssh is enabled | tools/tests/test_gitread.py::test_an_ssh_command_is_refused_when_ssh_is_actually_enabled |
| O2 | ACCEPTANCE | the same repository reads normally when ssh is not enabled | tools/tests/test_gitread.py::test_an_ssh_command_does_not_refuse_an_ordinary_read |
| O3 | NEGATIVE | the publication gate's remote verification cannot be answered by the repository's own program | tools/tests/test_publication_gate.py::test_remote_verification_refuses_a_repository_supplied_ssh_program |
| O4 | STRUCTURAL | no closure claims a condition the inspection cannot see | tools/tests/test_gitread.py::test_every_conditional_closure_is_known_to_the_inspection |
| O5 | MUTATION | restoring the unconditional closure — leaving `core.sshcommand` closed while ssh is enabled — must fail O1 and O3, and must not be survivable by O2 alone | tools/tests/test_gitread.py::test_an_ssh_command_is_refused_when_ssh_is_actually_enabled |
| O6 | MUTATION | passing no transports to the inspection, so the condition is never seen, must fail O1 | tools/tests/test_gitread.py::test_an_ssh_command_is_refused_when_ssh_is_actually_enabled |
