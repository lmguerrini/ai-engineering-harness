"""What is true about an execution backend, and what is merely believed.

`policy/observations.jsonl` already records real dispatches, and
`policy/routing-table.md` is a derived view over them that is regenerated
wholesale rather than patched. Both work. What neither had was a **shape**: the
backend a dispatch ran on was a free-form string —
`family=claude-cli agent=capability-auditor effort=unknown isolation=git-worktree
network=allowed` — so no checker could tell whether a field was absent because
nobody looked or absent because there was nothing to see, and nothing prevented
a reader from concluding "available, therefore usable".

This module gives that string a structure and makes three inferences
impossible to write rather than merely discouraged:

*   **availability is never qualification** (`DECISIONS.md` D8). A backend that
    answers is a backend that answers.
*   **permission is never capability.** `read-only` describes what a worker
    *may* do. It says nothing about what it *can* do, and the pack has a
    measured case: a family validated for mechanical extraction, dispatched on
    analytical review, produced seven findings it asserted and then retracted.
*   **a grade at one task class is `unprobed` at every other.** Not inherited,
    not averaged, not assumed.

`UNKNOWN` is a first-class value on **every** field. A backend contract whose
fields must be filled in is a contract that will be filled in with guesses, and
a guess recorded in the same shape as an observation is indistinguishable from
one a week later.

## Adding a backend

A future subscription-native backend is added by writing an **observation
source** for it — something that produces `BackendIdentity` and dispatch
outcomes — not by changing anything here. That is the point of the split: this
module holds the rules, the adapters hold the vendors, and no vendor's absence
breaks the rules.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

__all__ = [
    "UNKNOWN",
    "QUALIFICATION_GRADES",
    "AUTHENTICATION_CLASSES",
    "BackendIdentity",
    "TaskClassGrade",
    "BackendRecord",
    "parse_configuration",
    "grades_from_observations",
    "ROLE_OBSERVATION_CLASSES",
    "role_grade",
]

#: Not a sentinel to be replaced later. A field that is `UNKNOWN` has been
#: *reported as not established*, which is a different claim from a field that
#: happens to be empty, and the difference is the whole reason this constant
#: exists rather than `None`.
UNKNOWN = "UNKNOWN"

#: Ordinal only, and deliberately not numeric — the evidence base is small
#: enough that a number would invite arithmetic it cannot support. How small is
#: `policy/observations.jsonl`, counted there rather than restated here: this
#: module's whole purpose is deriving from that log instead of repeating it, and
#: it carried a stale count of its own for a release.
#:
#: `unprobed` nothing has been dispatched. `provisional` some evidence, not
#: enough to rely on. `confirmed` repeated real dispatches with reproduced
#: findings. `contradicted` evidence against. `environmental-unknown` the
#: runtime never started, so nothing about capability was learned either way —
#: which is emphatically not `contradicted`.
QUALIFICATION_GRADES = (
    "unprobed",
    "provisional",
    "confirmed",
    "contradicted",
    "environmental-unknown",
)

#: How execution is paid for and authenticated. Recorded because a mode that
#: changes this is a **different backend** and does not inherit the other's
#: qualification (`policy/execution-boundaries.md`). `api_key` is present so it
#: can be *named and refused*, not so it can be used: provider API-key billing
#: is not an allowed architectural dependency (D14 clause 12).
AUTHENTICATION_CLASSES = ("subscription", "api_key", "local", UNKNOWN)

#: Grades that assert something positive about capability. Reaching one
#: requires observations; the rest are reachable with none.
_EVIDENCE_BEARING = ("provisional", "confirmed", "contradicted")


class BackendContractError(Exception):
    """A backend record claims something its evidence does not support."""


@dataclass(frozen=True)
class BackendIdentity:
    """Which backend this is, as far as anything actually observed it."""

    family: str = UNKNOWN
    client: str = UNKNOWN
    client_version: str = UNKNOWN
    #: What the dispatch **asked for**.
    model_requested: str = UNKNOWN
    #: What the execution surface **confirmed**. Left `UNKNOWN` unless a
    #: documented surface reported it: a requested model is not an observed
    #: model, and recording the request in this field is how a routing table
    #: comes to describe a configuration that never ran.
    model_observed: str = UNKNOWN
    #: How `model_observed` was established, named so a reader can weigh it.
    identity_method: str = UNKNOWN
    authentication_class: str = UNKNOWN
    #: What the worker was *permitted* to do. Never read as capability.
    permission_state: str = UNKNOWN
    sandbox_state: str = UNKNOWN
    network_state: str = UNKNOWN
    effort_requested: str = UNKNOWN
    effort_observed: str = UNKNOWN

    def __post_init__(self) -> None:
        if self.authentication_class not in AUTHENTICATION_CLASSES:
            raise BackendContractError(
                f"authentication_class {self.authentication_class!r} is not one of "
                f"{', '.join(AUTHENTICATION_CLASSES)}"
            )

    @property
    def model(self) -> str:
        """The model, only where it was observed.

        Deliberately does **not** fall back to `model_requested`. A convenience
        that quietly substitutes the request for the observation is how the two
        stop being distinguishable.
        """
        return self.model_observed


@dataclass(frozen=True)
class TaskClassGrade:
    """A qualification, at one task class, with the count behind it."""

    task_class: str
    grade: str = "unprobed"
    observations: int = 0
    validated: int = 0
    contradicted: int = 0
    environmental: int = 0

    def __post_init__(self) -> None:
        if self.grade not in QUALIFICATION_GRADES:
            raise BackendContractError(
                f"grade {self.grade!r} is not one of {', '.join(QUALIFICATION_GRADES)}"
            )
        if self.grade in _EVIDENCE_BEARING and self.observations <= 0:
            raise BackendContractError(
                f"{self.task_class!r} is graded {self.grade!r} with no observation behind it; "
                "a grade is a claim about evidence, and availability is not evidence"
            )


@dataclass(frozen=True)
class BackendRecord:
    """One backend, its qualifications, and everything not established."""

    identity: BackendIdentity
    #: Keyed by task class. **Absence means `unprobed`**, and is answered that
    #: way rather than by falling through to another class's grade.
    capability: dict[str, TaskClassGrade] = field(default_factory=dict)
    known_limitations: tuple[str, ...] = ()
    #: What happens to work in flight when the run is interrupted, and whether
    #: partial output is distinguishable from complete output.
    interruption_semantics: str = UNKNOWN
    #: How results come back, and whether the backend can write evidence at all
    #: — the difference between a read-only dispatch that returns a report and
    #: one that discovers at the end that it cannot write it.
    evidence_return_semantics: str = UNKNOWN
    #: Whether the backend answers **right now**. Carried so it can be reported
    #: and so it can be kept away from `grade_for`.
    availability: str = UNKNOWN
    #: A timestamped resource reading, where a documented surface produced one.
    resource_truth: object | None = None

    def grade_for(self, task_class: str) -> TaskClassGrade:
        """This backend's qualification at one task class.

        An unobserved class is `unprobed`. It is not inherited from a class
        that was observed, however similar the two look: `EXTRACT` and `REVIEW`
        differ by whether the worker must *discard* a hypothesis, and one family
        in this evidence base does the first and demonstrably not the second.
        """
        return self.capability.get(task_class, TaskClassGrade(task_class))

    def qualified_for(self, task_class: str) -> bool:
        """Whether evidence supports dispatching this class here.

        Reads only the grade. It cannot consult `availability`, and it cannot
        consult `permission_state`, because those are the two inferences the
        module exists to prevent — a checker that *could* reach them would
        eventually be edited to.
        """
        return self.grade_for(task_class).grade == "confirmed"

    def unknown_fields(self) -> list[str]:
        """Every field that is not established, named.

        Reported rather than omitted: a record printed without its gaps reads
        as a complete description of the backend.
        """
        missing = [
            f"identity.{name}"
            for name, value in vars(self.identity).items()
            if value == UNKNOWN
        ]
        missing.extend(
            name
            for name in ("interruption_semantics", "evidence_return_semantics", "availability")
            if getattr(self, name) == UNKNOWN
        )
        return missing


def parse_configuration(text: str) -> BackendIdentity:
    """Read the free-form `configuration` string an observation already carries.

    The observations already in the log are primary evidence and are not
    rewritten to fit a new shape. They are *read* into it, and every key the string does not
    carry stays `UNKNOWN` — including the several that are literally recorded as
    the word `unknown`, which meant the same thing and could not be told apart
    from a key nobody wrote.
    """
    fields: dict[str, str] = {}
    for token in text.split():
        if "=" not in token:
            continue
        key, _, value = token.partition("=")
        value = value.strip()
        fields[key.strip()] = UNKNOWN if value.lower() in ("", "unknown") else value

    authentication = fields.get("auth", UNKNOWN)
    if authentication not in AUTHENTICATION_CLASSES:
        authentication = UNKNOWN

    return BackendIdentity(
        family=fields.get("family", UNKNOWN),
        client=fields.get("agent", fields.get("client", UNKNOWN)),
        client_version=fields.get("build", UNKNOWN),
        model_requested=fields.get("model", UNKNOWN),
        # Never filled from `model`. The observations record what was asked for.
        model_observed=fields.get("model_observed", UNKNOWN),
        identity_method=fields.get("identity_method", UNKNOWN),
        authentication_class=authentication,
        permission_state=fields.get("permission", UNKNOWN),
        sandbox_state=fields.get("isolation", UNKNOWN),
        network_state=fields.get("network", UNKNOWN),
        effort_requested=fields.get("effort", UNKNOWN),
        effort_observed=fields.get("effort_observed", UNKNOWN),
    )


def grades_from_observations(source: str | Path) -> dict[tuple[str, str], TaskClassGrade]:
    """Derive per-(family, task class) grades from the observation log.

    A **derived view**, in the sense `routing-table.md` already uses: computed
    from the whole log every time, never patched, never a rolling summary that
    can overwrite adverse evidence.

    The derivation is deliberately conservative and stated here rather than
    tuned: any contradiction grades `contradicted`; observations that only ever
    failed environmentally grade `environmental-unknown`, because the runtime
    never started and nothing was learned about capability; two or more
    validations grade `confirmed`; one grades `provisional`; none grades
    `unprobed`.
    """
    counts: dict[tuple[str, str], dict[str, int]] = {}
    for line in Path(source).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        identity = parse_configuration(row.get("configuration", ""))
        key = (identity.family, row.get("task_class", UNKNOWN))
        bucket = counts.setdefault(key, {"validated": 0, "contradicted": 0, "environmental": 0})
        outcome = row.get("outcome")
        if outcome == "validated":
            bucket["validated"] += 1
        elif outcome == "contradicted":
            bucket["contradicted"] += 1
        elif outcome == "environmental_failure":
            bucket["environmental"] += 1
        else:
            # An `else` here counted every unrecognised string as
            # `environmental-unknown` — "the runtime never started, nothing was
            # learned" — so a case variant of `contradicted` silently became
            # adverse evidence that had been overwritten. In the module whose
            # thesis is that these inferences are impossible to write. Found by
            # an independent audit.
            raise BackendContractError(
                f"observation records outcome {outcome!r}, which this derivation does not "
                f"recognise. Known: validated, contradicted, environmental_failure. An "
                "unrecognised outcome must not be counted as any of them"
            )

    graded: dict[tuple[str, str], TaskClassGrade] = {}
    for (family, task_class), bucket in counts.items():
        total = sum(bucket.values())
        if bucket["contradicted"]:
            grade = "contradicted"
        elif bucket["validated"] >= 2:
            grade = "confirmed"
        elif bucket["validated"] == 1:
            grade = "provisional"
        else:
            grade = "environmental-unknown"
        graded[(family, task_class)] = TaskClassGrade(
            task_class=task_class,
            grade=grade,
            observations=total,
            validated=bucket["validated"],
            contradicted=bucket["contradicted"],
            environmental=bucket["environmental"],
        )
    return graded


#: Which observed (family, task class) pairs stand behind each **role** in
#: `policy/routing-table.md`. Written here, machine-readable, because the table
#: restated grades that nothing compared — and an independent audit found two of
#: them contradicted by the very command the file printed beside them.
#:
#: A role that spans several task classes takes the **weakest** of them. "Grades
#: are per task class, never per worker" is the rule the table itself states, and
#: a role cannot be stronger than its weakest evidenced class without averaging
#: adverse or absent evidence away.
ROLE_OBSERVATION_CLASSES: dict[str, tuple[tuple[str, str], ...]] = {
    "AUDIT_PRIMARY": (("claude-cli", "blind_closure_audit_primary"),),
    "AUDIT_CROSS": (("codex-cli", "blind_closure_audit_cross_vendor"),),
    "IMPL_SUBSTANTIVE": (
        ("claude-cli", "tool_extraction"),
        ("claude-cli", "documentation_and_policy_authoring"),
    ),
    "IMPL_ROUTINE": (("claude-cli", "bounded_repair"),),
    "IMPL_BOUNDED": (
        ("codex-cli", "confinement dispatch qualification (worker configuration ladder, 8 configs)"),
    ),
    "EXTRACT_LOCAL": (
        ("local-mlx", "read_only_extraction_and_classification"),
        ("local-mlx", "absence_reporting_under_leading_prompt"),
    ),
    "REVIEW_LOCAL": (("local-mlx", "analytical_code_review"),),
    "READER": (
        ("codex-cli", "reader_evidence_sweep"),
        ("codex-cli", "reader_consistency_sweep_against_supplied_ground_truth"),
    ),
}

#: Weakest first. Adverse evidence outranks absence, and absence outranks any
#: positive grade — so a role spanning several classes can never read stronger
#: than its worst one.
_GRADE_PRECEDENCE = (
    "contradicted",
    "unprobed",
    "environmental-unknown",
    "provisional",
    "confirmed",
)


def role_grade(role: str, graded: dict[tuple[str, str], TaskClassGrade]) -> str:
    """The grade a role carries, derived from its task classes. Weakest wins."""
    classes = ROLE_OBSERVATION_CLASSES.get(role)
    if not classes:
        raise BackendContractError(f"no observed task classes are recorded for role {role!r}")
    grades = [
        graded.get(key, TaskClassGrade(key[1])).grade for key in classes
    ]
    return min(grades, key=_GRADE_PRECEDENCE.index)


def record_for(
    family: str,
    graded: dict[tuple[str, str], TaskClassGrade],
    *,
    identity: BackendIdentity | None = None,
    **overrides: object,
) -> BackendRecord:
    """Assemble one backend's record from a derived grade table."""
    capability = {
        task_class: grade for (owner, task_class), grade in graded.items() if owner == family
    }
    base = identity or BackendIdentity(family=family)
    return BackendRecord(identity=replace(base, family=family), capability=capability, **overrides)


def _cli(argv: list[str]) -> int:
    """Print the derived grade table. A view over the log, never a record."""
    import argparse
    import sys
    from pathlib import Path as _Path

    parser = argparse.ArgumentParser(
        prog="backend_contract.py",
        description="Derive per-backend, per-task-class qualification from the observation log.",
    )
    parser.add_argument(
        "observations", nargs="?",
        default=str(_Path(__file__).resolve().parent.parent / "policy" / "observations.jsonl"),
        help="path to observations.jsonl",
    )
    args = parser.parse_args(argv)

    try:
        graded = grades_from_observations(args.observations)
    except Exception as exc:
        print(f"the observation log could not be read: {exc}", file=sys.stderr)
        return 2

    print(f"derived from {args.observations} — a view, not a record; the log wins")
    for (family, task_class), grade in sorted(graded.items()):
        counts = (
            f"{grade.validated} validated, {grade.contradicted} contradicted, "
            f"{grade.environmental} environmental"
        )
        print(f"  {family:14} {task_class:48} {grade.grade:22} ({counts})")
    print("  availability is never qualification; a grade at one class is unprobed at every other")
    return 0


if __name__ == "__main__":
    import sys

    from errors import run_cli

    raise SystemExit(run_cli(_cli, sys.argv[1:]))
