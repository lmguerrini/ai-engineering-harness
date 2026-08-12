#!/usr/bin/env python3
"""Requirement-coverage gate: no grouping may erase an individual requirement.

Stdlib only, deliberately tiny — a project-instantiated check, not toolbelt
authority.

**One authority per fact.** REQUIREMENTS.md is the verbatim transcription of the
official specification and is the sole authority for *which* requirements exist.
REQUIREMENT_COVERAGE.md is a derived view of how each one is being met. This gate
compares the view against the authority by **identifier**, never against a count
the view declares about itself.

An earlier version read only the coverage file and trusted a
`<!-- requirement_count: N -->` comment inside it. A requirement dropped from the
table *and* from that comment passed the gate green. That is the same defect
class as deriving a test's domain from a symptom instead of the mechanism: the
check enumerated rows in a derived view and called it completeness.

Usage:
    validate_requirement_coverage.py REQUIREMENTS.md REQUIREMENT_COVERAGE.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

COLUMNS = [
    "ID", "Source", "Capability", "Task",
    "Implementation status", "Required validation", "Evidence", "Status",
]

#: A requirement id: R1, R12, R3a. Anchored so prose cannot contribute one.
_ID = re.compile(r"^(R\d+[a-z]?)$")

#: Statuses that are a decision somebody took. A requirement whose status is not
#: one of these, and which carries no evidence, is the condition that means
#: nobody decided — the case the test-or-stated-gap rule exists to refuse.
_DECIDED = {"PASSED", "N/A", "N/A-with-reason", "HITL_ACCEPTED_LIMITATION", "BLOCKED"}


def _table_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or cells[0] == "ID" or set(cells[0]) <= {"-", ":", ""}:
            continue  # header or separator
        rows.append(cells)
    return rows


def authority_ids(text: str) -> list[str]:
    """Every requirement id declared by REQUIREMENTS.md, in order."""
    found = []
    for cells in _table_rows(text):
        if _ID.match(cells[0]):
            found.append(cells[0])
    return found


def check(authority_text: str, coverage_text: str) -> list[str]:
    errors: list[str] = []

    declared = authority_ids(authority_text)
    if not declared:
        return ["REQUIREMENTS.md declares no requirements — refusing to pass vacuously"]

    seen_authority = [x for x in declared if declared.count(x) > 1]
    if seen_authority:
        errors.append(f"duplicate ids in REQUIREMENTS.md: {', '.join(sorted(set(seen_authority)))}")

    rows = _table_rows(coverage_text)
    covered: list[str] = []
    for index, cells in enumerate(rows, start=1):
        label = cells[0] if cells else "?"
        if len(cells) != len(COLUMNS):
            errors.append(f"row {index} ({label}): expected {len(COLUMNS)} columns, found {len(cells)}")
            continue
        covered.append(label)
        for name, value in zip(COLUMNS, cells):
            if not value:
                errors.append(f"row {index} ({label}): missing {name}")
        status, evidence = cells[7], cells[6]
        if status and status not in _DECIDED and not evidence:
            errors.append(
                f"row {index} ({label}): status {status!r} with no evidence and no stated gap"
            )

    # The load-bearing comparison: identifiers, both directions.
    missing = [x for x in declared if x not in covered]
    if missing:
        errors.append(f"requirements with no coverage row: {', '.join(missing)}")

    invented = [x for x in covered if x not in declared]
    if invented:
        errors.append(f"coverage rows for requirements the specification does not declare: {', '.join(invented)}")

    duplicated = sorted({x for x in covered if covered.count(x) > 1})
    if duplicated:
        errors.append(f"duplicate coverage rows: {', '.join(duplicated)}")

    # Secondary tripwire only. Never the authority.
    stated = re.search(r"<!--\s*requirement_count:\s*(\d+)\s*-->", coverage_text)
    if stated and int(stated.group(1)) != len(declared):
        errors.append(
            f"declared requirement_count {stated.group(1)} disagrees with "
            f"REQUIREMENTS.md ({len(declared)}) — the specification wins"
        )

    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        raise SystemExit(
            "usage: validate_requirement_coverage.py REQUIREMENTS.md REQUIREMENT_COVERAGE.md"
        )
    authority = Path(argv[1]).read_text(encoding="utf-8")
    coverage = Path(argv[2]).read_text(encoding="utf-8")
    errors = check(authority, coverage)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Requirement coverage: OK ({len(authority_ids(authority))} requirements, each independently covered)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
