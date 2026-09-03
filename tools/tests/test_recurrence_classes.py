"""Every mandated recurrence class, proved against an oracle that runs.

`policy/recurrence-classes.json` names each class and the selector for its
oracle; `docs/RP2.3-REFALSIFICATION-MAP.md` is the prose beside it. This runs
them.

**It exists because the classes were previously proved by running a script by
hand.** That is how three of the selectors came to match no test at all and
report green by selecting nothing — a passing command and an empty claim. A
selector that selects nothing is the failure this module is built to notice, so
it counts what each one collected rather than trusting an exit status.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "policy" / "recurrence-classes.json"


def _classes():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))["classes"]


def _select(entry):
    files = [str(ROOT / "tools" / "tests" / f) for f in entry["files"]]
    command = [sys.executable, "-m", "pytest", *files, "-q", "--no-header",
               "-p", "no:cacheprovider"]
    if entry["keyword"]:
        command += ["-k", entry["keyword"]]
    return command


@pytest.mark.parametrize("entry", _classes(), ids=lambda e: e["class"][:48])
def test_each_recurrence_class_selects_the_oracle_it_names(entry):
    """That the selected tests PASS is established by this suite, which runs
    them; what this asserts is that the selector picks them out at all.

    The first version ran each oracle as well, which took the suite from under
    three minutes to over six and made two classes fail whenever the release pin
    was mid-edit — their selectors named a whole module including its
    identity-drift tests. **A check nobody can afford to run is a check somebody
    turns off**, and one that fails for a reason unrelated to its property is
    the anti-test this file exists to catch.
    """
    collected = subprocess.run(_select(entry) + ["--collect-only"],
                               capture_output=True, text=True, timeout=600, cwd=ROOT)
    tests = [line for line in collected.stdout.splitlines() if "::" in line]
    assert tests, (
        f"the oracle for {entry['class']!r} selects no test at all: "
        f"{entry['files']} -k {entry['keyword']!r}")


def test_the_map_and_its_machine_readable_twin_hold_the_same_classes():
    """The prose and the data are two copies of one list, and two copies drift.
    Checked by count and by name rather than by having written them together."""
    import re

    prose = (ROOT / "docs" / "RP2.3-REFALSIFICATION-MAP.md").read_text(encoding="utf-8")
    named = {row["class"] for row in _classes()}
    rows = re.findall(r"^\| ([^|]+?) \| (.+?) \|$", prose, re.M)
    in_prose = {c.strip() for c, o in rows
                if c.strip() not in ("Recurrence class", "---") and "`" in o}
    assert named == in_prose, (
        f"only in the data: {sorted(named - in_prose)}; only in the prose: "
        f"{sorted(in_prose - named)}")


def test_a_selector_that_matches_nothing_is_caught():
    """The bound. Three real selectors matched nothing and reported green, so
    this asserts the check notices rather than assuming it would."""
    broken = {"class": "a class nobody wrote an oracle for",
              "files": ["test_projection.py"], "keyword": "nothing_matches_this_at_all"}
    collected = subprocess.run(_select(broken) + ["--collect-only"],
                               capture_output=True, text=True, timeout=600, cwd=ROOT)
    assert not [line for line in collected.stdout.splitlines() if "::" in line]
