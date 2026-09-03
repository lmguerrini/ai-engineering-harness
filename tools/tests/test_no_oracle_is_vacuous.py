"""The suite, checked for oracles that cannot fail — mechanically, over itself.

Eleven separate instances of *a check that asks its subject what to check* were
found in this release. Four were found by independent readers, seven by mutation
passes, **and none by writing them.** The shapes recur because they are
invisible at the moment of writing: a selector that matches nothing, a
comparison of a pure function with itself, a parametrisation over a set that
computes to empty. Each is a passing command and an empty claim.

So the suite reads itself. This is not a substitute for mutation testing — it
catches shapes, and a test can be vacuous in ways no shape reveals — but every
shape it does catch was previously found by somebody else, late.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parents[1]


def _modules():
    return sorted(p for p in TESTS.glob("test_*.py"))


def _functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [(path, n) for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]


ALL = [pair for path in _modules() for pair in _functions(path)]

#: Parametrised PER MODULE rather than per test. Per test was the first version
#: and it added some two thousand cases to a suite of fourteen hundred — a
#: sweep that more than doubles the number the release states about itself is
#: misrepresenting what the suite is, and the count is a figure this pack
#: publishes. A module's failure names the function inside it, so nothing is
#: lost but the arithmetic.


def test_the_sweep_actually_reads_the_suite():
    """Its own bound. Every assertion below passes trivially over an empty list,
    which is the very shape it exists to catch."""
    assert len(ALL) > 500, f"the sweep found only {len(ALL)} tests to read"
    assert len(_modules()) > 20


@pytest.mark.parametrize("module", _modules(), ids=lambda p: p.name)
def test_no_test_compares_a_thing_with_itself(module):
    """`f(x) == f(x)` calls a pure function twice and tests the language. Three
    instances: two digest tautologies found by an independent reader, and one in
    the routing view found by this sweep."""
    for path, node in _functions(module):
        for check in (n for n in ast.walk(node) if isinstance(n, ast.Assert)):
            if isinstance(check.test, ast.Compare) and len(check.test.comparators) == 1:
                left = ast.dump(check.test.left)
                right = ast.dump(check.test.comparators[0])
                assert left != right, (
                    f"{path.name}::{node.name} compares an expression with itself at line "
                    f"{check.lineno}")


@pytest.mark.parametrize("module", _modules(), ids=lambda p: p.name)
def test_no_test_asserts_a_constant(module):
    for path, node in _functions(module):
        for check in (n for n in ast.walk(node) if isinstance(n, ast.Assert)):
            assert not (isinstance(check.test, ast.Constant) and check.test.value), (
                f"{path.name}::{node.name} asserts a literal at line {check.lineno}")


def test_every_parametrised_test_collected_at_least_one_case():
    """**The boundary, rather than the seven instances.**

    Seven parametrisations in this suite take a computed set — a comprehension
    over a policy file, a filtered contract, a glob. Each is correct today and
    each becomes a silently passing no-op the day its set computes to empty,
    which is exactly how three matrix selectors and three recurrence selectors
    came to report green by selecting nothing.

    Asked of the collector rather than of the source: a parametrised function
    that contributed no test ids collected nothing, whatever the expression
    looked like.
    """
    parametrised = set()
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
                continue
            for decorator in node.decorator_list:
                call = decorator.func if isinstance(decorator, ast.Call) else decorator
                if isinstance(call, ast.Attribute) and call.attr == "parametrize":
                    parametrised.add(f"{path.name}::{node.name}")

    assert parametrised, "no parametrised tests found, so this check reads nothing"

    collected = subprocess.run(
        [sys.executable, "-m", "pytest", str(TESTS), "--collect-only", "-q",
         "-p", "no:cacheprovider"],
        capture_output=True, text=True, timeout=900, cwd=ROOT)
    ids = [line for line in collected.stdout.splitlines() if "::" in line]
    assert ids, "the collection produced nothing"

    # pytest does NOT drop an empty parametrisation — it collects one item, ids
    # it `[NOTSET]`, and SKIPS it with *got empty parameter set*. So the function
    # appears in the collection and the run is green while the test never ran,
    # which is the shape exactly. Checked for by name, because a skip nobody
    # reads is indistinguishable from a pass.
    notset = sorted({line.split("::")[-1] for line in ids if "[NOTSET]" in line})
    assert not notset, (
        f"these parametrised tests collected an EMPTY parameter set, so pytest skips them and "
        f"the run is green with nothing run: {notset}")

    seen = set()
    for line in ids:
        module, _, rest = line.partition("::")
        function = rest.split("[")[0]
        seen.add(f"{Path(module).name}::{function}")

    empty = sorted(parametrised - seen)
    assert not empty, (
        f"these parametrised tests collected no cases at all, so they pass by running "
        f"nothing: {empty}")
