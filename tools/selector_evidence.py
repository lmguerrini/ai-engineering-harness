"""Whether a targeted test run is evidence that the intended check ran.

The measured failure, in this release's own session: a command of the form

    python3 -m pytest <file> -q -k "never_prints_a_traceback"

exited **0** in 0.56 seconds and was very nearly read as a forty-five-fold
speed-up over the same guard's 25.7 seconds. It had selected **zero tests** —
the real name contains `ever_prints`, not `never_prints` — so the run proved
nothing at all and said so only in a line nobody had to read.

**`exit status 0` is not evidence that the intended check ran.** That is the
whole module. A selector used as evidence records what it intended, what it
collected, what it executed, what it skipped and how it exited, and answers
`NOT_EVIDENCE` when fewer tests ran than the caller said to expect.

The rule binds performance work with particular force, because that is where it
was nearly believed: **a comparison between two runs is admissible only if both
ran the same test population.** A faster run over fewer tests is not a faster
run, and an optimization that quietly changes what is executed is not an
optimization.

Related and deliberately separate: `tools/tests/test_no_oracle_is_vacuous.py`
attacks the CONTENT of a test — self-comparison, asserted constants, empty
parametrisation. This attacks whether a test RAN. A test can be perfectly
written and still be no evidence, because nothing selected it.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "NOT_EVIDENCE",
    "EVIDENCE",
    "SelectorRun",
    "read_summary",
    "read_collection",
    "run_selector",
    "problems",
    "comparison_problems",
]

#: The run does not establish that the intended check happened.
NOT_EVIDENCE = "NOT_EVIDENCE"
#: It does.
EVIDENCE = "EVIDENCE"

#: Outcomes that mean a test BODY ran. `skipped` and `deselected` are counted
#: and are deliberately not here: a skipped test is a test that did not run, and
#: a deselected one was never chosen. Both are the shapes that produce a green
#: command with nothing behind it.
_EXECUTED = ("passed", "failed", "error", "errors", "xpassed", "xfailed")
_COUNTED = _EXECUTED + ("skipped", "deselected")

_SUMMARY = re.compile(r"(\d+)\s+(" + "|".join(_COUNTED) + r")\b")

#: `--collect-only -q` ends with `N tests collected in Xs`, or
#: `N/M tests collected (K deselected) in Xs`. Read explicitly, because a
#: collection reports what a selector NAMES and that is a different question
#: from what ran — and answering the first with the second is how a guard comes
#: to believe a selector resolves when nothing would execute.
_COLLECTED = re.compile(r"(\d+)(?:/\d+)?\s+tests? collected(?:\s+\((\d+) deselected\))?")
_COLLECTED_NONE = re.compile(r"no tests collected|collected 0 items")


@dataclass(frozen=True)
class SelectorRun:
    """One targeted run, and everything needed to decide whether it is evidence."""

    #: What the caller intended to run, verbatim, so a typo is visible in the record.
    selector: str
    collected: int = 0
    executed: int = 0
    skipped: int = 0
    deselected: int = 0
    exit_status: int = 0
    #: Present when the summary could not be read at all, which is not zero.
    unreadable: str = ""

    def verdict(self, *, expect_at_least: int = 1) -> str:
        return NOT_EVIDENCE if problems(self, expect_at_least=expect_at_least) else EVIDENCE

    def sentence(self, *, expect_at_least: int = 1) -> str:
        return (
            f"{self.verdict(expect_at_least=expect_at_least)}: {self.selector!r} collected "
            f"{self.collected}, executed {self.executed}, skipped {self.skipped}, deselected "
            f"{self.deselected}, exit {self.exit_status}"
        )


def read_collection(text: str, *, selector: str = "", exit_status: int = 0) -> SelectorRun:
    """Read a `--collect-only` summary. What a selector NAMES, not what ran.

    Reported through `executed` so one refusal rule serves both: for a
    collection, *executing* is *being collected*, and a selector that collects
    nothing names nothing whatever the command's exit status was.
    """
    if _COLLECTED_NONE.search(text or ""):
        return SelectorRun(selector=selector, exit_status=exit_status)
    found = _COLLECTED.search(text or "")
    if not found:
        return SelectorRun(selector=selector, exit_status=exit_status,
                           unreadable="pytest printed no collection summary this could read, so "
                                      "what the selector names is unknown — which is not the "
                                      "same as nothing")
    collected = int(found.group(1))
    deselected = int(found.group(2) or 0)
    return SelectorRun(selector=selector, collected=collected + deselected, executed=collected,
                       deselected=deselected, exit_status=exit_status)


def read_summary(text: str, *, selector: str = "", exit_status: int = 0) -> SelectorRun:
    """Read pytest's own summary line into counts.

    Parsed rather than inferred: `collected` is the sum of everything the run
    accounted for, so a selector that deselected the whole suite reports a real
    collection with zero executed rather than looking like an empty repository.
    """
    counts = {name: 0 for name in _COUNTED}
    for line in reversed((text or "").splitlines()):
        found = _SUMMARY.findall(line)
        if found and (" in " in line or "no tests ran" in line):
            for number, name in found:
                counts[name] += int(number)
            break
    else:
        if "no tests ran" not in (text or ""):
            return SelectorRun(selector=selector, exit_status=exit_status,
                               unreadable="pytest printed no summary this could read, so what "
                                          "ran is unknown — which is not the same as nothing")
    executed = sum(counts[name] for name in _EXECUTED)
    return SelectorRun(
        selector=selector,
        collected=executed + counts["skipped"] + counts["deselected"],
        executed=executed,
        skipped=counts["skipped"],
        deselected=counts["deselected"],
        exit_status=exit_status,
    )


def run_selector(argv, *, cwd=None, timeout: int = 600,
                 collect_only: bool = False) -> SelectorRun:
    """Run one pytest selector and record what it actually did.

    `collect_only` answers the cheaper question — *does this selector name any
    test* — for a caller that cannot afford to execute what it names. It is a
    weaker claim and the result says so by reporting a collection.
    """
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
               *(["--collect-only"] if collect_only else []), *argv]
    result = subprocess.run(command, capture_output=True, text=True,
                            cwd=str(cwd) if cwd else None, timeout=timeout)
    read = read_collection if collect_only else read_summary
    return read(result.stdout + result.stderr, selector=" ".join(str(a) for a in argv),
                exit_status=result.returncode)


def problems(run: SelectorRun, *, expect_at_least: int = 1) -> tuple[str, ...]:
    """Every reason this run is not evidence that the intended check happened.

    `expect_at_least` is the CALLER'S claim about what should have run. It is
    never read back out of the result, because a threshold derived from the
    thing it is checking cannot fail.
    """
    found = []
    if run.unreadable:
        found.append(run.unreadable)
        return tuple(found)
    if run.executed < expect_at_least:
        found.append(
            f"{run.executed} test(s) executed where at least {expect_at_least} was expected"
            + (f", with {run.deselected} deselected — the selector {run.selector!r} does not "
               f"name what it meant to" if run.deselected else "")
            + (f" and {run.skipped} skipped" if run.skipped else "")
            + (f". Exit status {run.exit_status} says the COMMAND succeeded, not that the check "
               f"ran" if run.exit_status == 0 else
               f". The command exited {run.exit_status}, which a shell pipeline can hide — this "
               f"answers from what ran rather than from how it exited")
        )
    return tuple(found)


def comparison_problems(before: SelectorRun, after: SelectorRun) -> tuple[str, ...]:
    """Every reason these two runs cannot be compared.

    A performance claim between runs over different populations is not a
    performance claim. This is the rule that was nearly broken: 25.7 seconds
    against 0.56 seconds, where the second executed nothing.
    """
    found = []
    for run, which in ((before, "before"), (after, "after")):
        found.extend(f"the {which} run is not evidence: {problem}" for problem in problems(run))
    if before.collected != after.collected:
        found.append(
            f"the runs collected different populations ({before.collected} then "
            f"{after.collected}), so they are not measuring the same thing")
    if before.executed != after.executed:
        found.append(
            f"the runs executed different numbers of tests ({before.executed} then "
            f"{after.executed}); a faster run over fewer tests is not a faster run")
    return tuple(found)


def _cli(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="selector_evidence.py",
        description="Run a pytest selector and say whether it is evidence that anything ran.")
    parser.add_argument("--expect-at-least", type=int, default=1)
    parser.add_argument("--cwd", default=None)
    parser.add_argument("selector", nargs=argparse.REMAINDER,
                        help="the pytest arguments, after --")
    args = parser.parse_args(argv)

    selector = [a for a in args.selector if a != "--"]
    if not selector:
        print("nothing to run: give the pytest arguments after --", file=sys.stderr)
        return 2
    run = run_selector(selector, cwd=args.cwd)
    print(run.sentence(expect_at_least=args.expect_at_least))
    for problem in problems(run, expect_at_least=args.expect_at_least):
        print(f"  {problem}")
    return 0 if run.verdict(expect_at_least=args.expect_at_least) == EVIDENCE else 1


if __name__ == "__main__":
    import sys as _sys

    from errors import run_cli
    from selector_evidence import _cli as _entry

    raise SystemExit(run_cli(_entry, _sys.argv[1:]))
