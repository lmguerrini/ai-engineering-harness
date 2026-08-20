"""The release surfaces of **this repository**, not of a fixture.

Every other test in this directory builds a synthetic repository and asserts
about it, which is the right shape for a checker and is exactly why RP2.1.0
shipped with `README.md` announcing "Runtime Pack 2.0" under `VERSION` 2.1.0, a
manifest recording 167 tests where the suite collected 175, and a gate record
that said 175 throughout. Every one of those files was green: no test read them,
because reading the real repository is not what a tool test does.

So this file does. It is small, it is the only test that knows where it lives,
and it fails on a drift a fixture cannot see.

**On the test count and self-reference.** The manifest records how many tests
the suite has, and this file is in the suite, so adding a test here changes the
number it checks. That is not a paradox, it is an ordering constraint: the
manifest is written *after* the test set is frozen, by `pack_pin.py --write` and
the count recorded from real collection. The check below collects the suite in a
subprocess (`--collect-only`, which executes nothing) rather than guessing, so
the number is measured by the same means at write time and at check time — the
provenance rule `oracle-discipline.md` states, applied to this file's own
oracle.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import pack_pin

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def manifest():
    return json.loads((ROOT / pack_pin.MANIFEST_NAME).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def version():
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


@pytest.fixture(scope="module")
def readme():
    return (ROOT / "README.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def changelog():
    return (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def _current_changelog_section(changelog: str) -> str:
    """The topmost release entry only.

    Older entries are history and are deliberately left as written, including
    the figures 2.1.1 corrects — so a check that scanned the whole file would
    fire on the erratum that exists to disclose the drift.
    """
    sections = changelog.split("\n## ")
    return sections[1] if len(sections) > 1 else ""


# --- one version authority ---------------------------------------------------

def test_the_manifest_version_matches_the_VERSION_file(manifest, version):
    assert manifest["version"] == version


def test_the_readme_announces_the_current_version(readme, version):
    assert readme.startswith(f"# Runtime Pack {version}\n"), readme.splitlines()[0]
    assert f"**{version}**" in readme


def test_the_current_changelog_entry_is_the_current_version(changelog, version):
    assert _current_changelog_section(changelog).startswith(f"{version} —")


def test_no_superseded_release_identity_survives_on_an_active_surface(readme, manifest, version):
    """2.1.0 shipped `README.md` titled 2.0. The check is scoped to *active*
    surfaces: `docs/` gate records and older CHANGELOG entries describe the pass
    that produced them and are never rewritten."""
    for stale in ("Runtime Pack 2.0", "Runtime Pack 2.1.0"):
        assert stale not in readme, f"README still carries {stale!r}"
    assert json.dumps(manifest).count(version) >= 1


# --- the state and its gate --------------------------------------------------

def test_the_manifest_declares_a_known_state(manifest):
    assert manifest["state"] in pack_pin.KNOWN_STATES


def test_the_gate_record_the_manifest_names_exists(manifest):
    gate = manifest["gate_record"]
    assert (ROOT / gate).is_file(), f"{gate} is named by the manifest and is not on disk"


def test_the_gate_record_names_this_version(manifest, version):
    gate_text = (ROOT / manifest["gate_record"]).read_text(encoding="utf-8")
    assert version in gate_text


def test_the_readme_agrees_with_the_manifest_about_state_and_gate(readme, manifest):
    assert manifest["state"] in readme
    assert manifest["gate_record"] in readme


# --- the digest and the tree -------------------------------------------------

def test_the_recorded_digest_recomputes_from_this_checkout(manifest):
    digest, count = pack_pin.tree_digest(ROOT)
    assert digest == manifest["tree_digest_sha256"]
    assert count == manifest[pack_pin.DIGEST_COUNT_KEY]


def test_the_release_identity_fields_are_well_formed(manifest):
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["tree_digest_sha256"])
    assert manifest["digest_excludes"] == pack_pin.MANIFEST_NAME
    assert manifest["digest_algorithm"] == pack_pin.DIGEST_ALGORITHM
    assert isinstance(manifest[pack_pin.DIGEST_COUNT_KEY], int) and manifest[pack_pin.DIGEST_COUNT_KEY] > 0


def test_this_checkout_verifies_against_its_own_manifest(manifest, version):
    assert pack_pin.verify_pin(
        ROOT,
        expect_version=version,
        expect_digest=manifest["tree_digest_sha256"],
        expect_state=manifest["state"],
    ) == []


def test_the_manifest_is_the_only_thing_excluded_from_its_own_digest(manifest):
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=str(ROOT), capture_output=True, text=True, check=True
    ).stdout.split("\0")
    tracked = [path for path in tracked if path]
    assert manifest[pack_pin.DIGEST_COUNT_KEY] == len(tracked) - 1


# --- the recorded test count, measured rather than asserted -----------------

def test_the_recorded_test_count_is_the_count_the_suite_actually_collects(manifest):
    """Unfiltered collection over the whole suite, in a subprocess.

    `--collect-only` executes nothing, so this does not recurse. Filtering by
    node id or by keyword would let a test that stopped being collected keep
    its place in the total, which is the failure mode the count exists to
    catch.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tools/tests/", "--collect-only", "-q",
         "-p", "no:cacheprovider"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    match = re.search(r"^(\d+) tests? collected", result.stdout, re.MULTILINE)
    assert match, f"could not read a collection count from:\n{result.stdout[-2000:]}"
    collected = int(match.group(1))
    assert collected == manifest["tests"]["passed"], (
        f"the suite collects {collected} tests, the manifest records "
        f"{manifest['tests']['passed']} — regenerate the manifest after freezing the test set"
    )


def test_the_manifest_records_the_command_that_produces_that_count(manifest):
    assert manifest["tests"]["command"] == "python3 -m pytest tools/tests/ -q"


# --- the README's repository tree, against the tracked tree -----------------

def _tree_paths(readme: str) -> list[str]:
    """Every path the README's repository tree claims, reconstructed by depth.

    Indented list entries do not show nesting, so the pack's own convention
    (`templates/repository-layout.template.md`) requires a real tree — derived
    from `git ls-files`, because a hand-maintained layout had silently dropped
    six real modules through four review rounds. Deriving it is only half the
    benefit; this is the other half.
    """
    lines = readme.split("    runtime-pack-2/\n", 1)[1].splitlines()
    stack: list[str] = []
    paths: list[str] = []
    for line in lines:
        if not line.startswith("    "):
            break
        body = line[4:]
        match = re.match(r"^((?:(?:│   )|(?:    ))*)(?:├── |└── )(\S+)", body)
        if not match:
            continue
        depth, name = len(match.group(1)) // 4, match.group(2)
        if name == "…":  # a declared elision, not a claim about a path
            continue
        stack = stack[:depth] + [name.rstrip("/")]
        paths.append("/".join(stack))
    return paths


def test_the_readme_tree_is_a_tree_and_not_an_aligned_list(readme):
    assert "    runtime-pack-2/\n" in readme
    assert "├── " in readme and "└── " in readme and "│   " in readme


def test_every_path_the_readme_tree_claims_exists(readme):
    claimed = _tree_paths(readme)
    assert len(claimed) > 20, f"the tree parsed to only {len(claimed)} entries"
    missing = [path for path in claimed if not (ROOT / path).exists()]
    assert missing == [], f"the README tree names paths that do not exist: {missing}"


def test_the_readme_tree_reaches_every_tracked_top_level_directory(readme):
    """A layout section that quietly drops a directory is the defect the
    convention exists to prevent."""
    claimed = set(_tree_paths(readme))
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=str(ROOT), capture_output=True, text=True, check=True
    ).stdout.split("\0")
    directories = {path.split("/")[0] for path in tracked if path and "/" in path}
    assert directories <= {entry.split("/")[0] for entry in claimed}


# --- the pin instruction the README gives actually works --------------------

def test_the_verification_command_the_readme_prints_is_the_real_one(readme, manifest, version):
    assert "tools/pack_pin.py" in readme
    for flag in ("--version", "--sha", "--digest", "--state"):
        assert flag in readme
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True, text=True, check=True
    ).stdout.strip()
    assert pack_pin.verify_pin(
        ROOT, expect_version=version, expect_sha=head,
        expect_digest=manifest["tree_digest_sha256"], expect_state=manifest["state"],
    ) == []


# --- CA-AMD-7: one canonical refspec across planning, gating and execution ---


#: Surfaces a person READS THE FORM FROM in order to run it: the runbook, the
#: contract template, the procedure skills, the policy, the README. Deliberately
#: not `tools/tests/` (whose whole job is to carry wrong forms as negative
#: cases), not `CHANGELOG.md` and not `docs/` (history, left as written), and not
#: `tools/` itself (where the constant is defined and exercised).
_INSTRUCTIONAL_GLOBS = ("templates/*.md", "templates/*.template", "skills/core/*.md",
                        "policy/*.md", "README.md")


def _instructional_files():
    seen = set()
    for pattern in _INSTRUCTIONAL_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            yield path, path.read_text(encoding="utf-8")


def test_every_documented_push_form_is_the_one_the_gate_checks():
    """The gate holds the form as a constant; the runbook and the contract
    restate it for a human to run. A restatement nothing compares is a second
    authority — the defect D11 named for release identity, applied to the push
    form. Planning, gating and execution now read one canonical string.
    """
    import publication_gate

    canonical = publication_gate.SUPPORTED_PUSH_FORM
    drifted = []
    for path, text in _instructional_files():
        for number, line in enumerate(text.splitlines(), 1):
            if "git push " not in line or canonical in line:
                continue
            # A line that names a form in order to FORBID it is not a
            # restatement of the supported one.
            if any(word in line for word in ("Never", "never", "forbidden", "refus", "not `")):
                continue
            drifted.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert not drifted, "these state a push form that is not the canonical one: " + "; ".join(drifted)


def test_the_canonical_form_is_actually_restated_somewhere():
    """Guards the check above from passing vacuously: a scan that finds no
    occurrences would report agreement about nothing."""
    import publication_gate

    occurrences = sum(
        text.count(publication_gate.SUPPORTED_PUSH_FORM) for _, text in _instructional_files()
    )
    assert occurrences >= 2, f"only {occurrences} restatement(s) found to compare"


def test_the_canonical_form_is_what_the_checker_accepts():
    """Binds the constant to behaviour, not just to text. A canonical string
    every document agrees on is worth nothing if the checker refuses it."""
    import publication_gate

    concrete = publication_gate.SUPPORTED_PUSH_FORM.replace("<remote>", "origin").replace(
        "<branch>", "main"
    )
    assert publication_gate.check_push_command(concrete, expected_remote="origin") == []


def test_a_near_miss_of_the_canonical_form_is_refused():
    import publication_gate

    for wrong in (
        "git push origin main",                                   # implicit refspec
        "git push origin refs/heads/*:refs/heads/*",              # wildcard
        "git push --mirror origin",                               # whole namespace
        "git push origin refs/heads/main:refs/heads/main refs/tags/v1:refs/tags/v1",
    ):
        assert publication_gate.check_push_command(wrong, expected_remote="origin"), wrong


def test_the_readme_tree_names_every_tool_module(readme):
    """Caught in RP2.2 by accident and worth a check.

    Five new tool modules shipped while the README tree still listed the
    original five, because the edits that were supposed to add them silently
    matched nothing. Nothing failed: the existing README tests assert that every
    path the tree *claims* exists and that every top-level directory is reached,
    and both stay true when the tree simply says less than the release contains.
    A document that omits is harder to notice than one that lies.
    """
    claimed = set(_tree_paths(readme))
    listing = subprocess.run(
        ["git", "ls-files", "-z", "tools/*.py"], cwd=str(ROOT), capture_output=True, check=True
    ).stdout
    modules = sorted(
        entry.decode("utf-8")
        for entry in listing.split(b"\0")
        if entry and b"/tests/" not in entry
    )
    assert modules, "no tool modules found to compare"
    missing = [path for path in modules if path not in claimed]
    assert not missing, f"the README tree does not name these tool modules: {missing}"


# --- the derived view must agree with the file that presents it ---------------


def test_the_routing_table_grades_are_the_derived_ones():
    """`policy/routing-table.md` calls itself a derived view and restated grades
    that nothing compared. Two of them were contradicted by the command printed
    twelve lines below them — found by an independent audit. This is the
    comparison, so "checkable rather than promised" is true.
    """
    import re

    import backend_contract

    graded = backend_contract.grades_from_observations(ROOT / "policy" / "observations.jsonl")
    table = (ROOT / "policy" / "routing-table.md").read_text(encoding="utf-8")

    checked = 0
    for line in table.splitlines():
        if not line.startswith("| ") or "|" not in line[2:]:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        role = cells[0]
        if role not in backend_contract.ROLE_OBSERVATION_CLASSES:
            continue
        stated = re.findall(r"`([a-z-]+)`", cells[-1])
        assert stated, f"{role} states no grade"
        expected = backend_contract.role_grade(role, graded)
        assert stated[0] == expected, (
            f"{role} states {stated[0]!r}; the observation log derives {expected!r}"
        )
        checked += 1
    assert checked >= 5, f"only {checked} role rows compared; the parser is not seeing the table"


def test_every_count_the_routing_table_states_is_the_number_of_rows_behind_it():
    """The grade was bound; the counts beside it were not, and went stale twice
    — `7 real closure audits` outlived two more audits, and `3 RP2 dispatches`
    never matched the log at all. A derived view whose numbers are typed is a
    record wearing a derived view's disclaimer.

    The rule is the LEADING count in each role's evidence cell, because that is
    the one a reader takes as the weight behind the grade.
    """
    import json
    import re

    import backend_contract

    rows = [
        json.loads(line)
        for line in (ROOT / "policy" / "observations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    def family(row):
        for token in row["configuration"].split():
            if token.startswith("family="):
                return token.split("=", 1)[1]
        return None

    behind = {role: 0 for role in backend_contract.ROLE_OBSERVATION_CLASSES}
    for row in rows:
        key = (family(row), row["task_class"])
        for role, classes in backend_contract.ROLE_OBSERVATION_CLASSES.items():
            if key in {tuple(observation) for observation in classes}:
                behind[role] += 1

    table = (ROOT / "policy" / "routing-table.md").read_text(encoding="utf-8")
    checked = 0
    for line in table.splitlines():
        if not line.startswith("| ") or "|" not in line[2:]:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        role = cells[0]
        if role not in behind:
            continue
        stated = re.search(r"(\d+)", cells[-1])
        assert stated, f"{role} states no count; the log has {behind[role]} rows behind it"
        assert int(stated.group(1)) == behind[role], (
            f"{role} states {stated.group(1)} where the observation log has "
            f"{behind[role]} rows — regenerate the table from the log"
        )
        checked += 1
    assert checked >= 5, f"only {checked} role rows compared; the parser is not seeing the table"


#: The frozen release this candidate must not regress against. Not read from a
#: document — the digest and state of that revision are what `pack_pin` checks,
#: and this is the same revision by name.
QUALIFIED_BASELINE = "4495e61850c08027e47eac6d0db84b4b3380e300"


def test_no_tool_removed_a_public_name_or_changed_a_signature_since_the_baseline():
    """The non-regression claim, measured against the WORKING TREE rather than
    against `HEAD`.

    The gate record asserted this in prose from an audit snapshot, and it went
    stale the moment a test function gained a parameter — harmlessly, but a
    reader cannot tell a harmless staleness from a real removal without
    re-running the tool, which is the whole objection this release keeps
    meeting. Tests are excluded deliberately: `tools/tests/` is not a surface
    anything imports, and parametrising a test is not a compatibility event.
    """
    import subprocess

    import surface_diff

    removals = []
    for path in sorted(ROOT.glob("tools/*.py")):
        name = f"tools/{path.name}"
        before = subprocess.run(
            ["git", "show", f"{QUALIFIED_BASELINE}:{name}"],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        if before.returncode != 0:
            continue  # a module this release adds has nothing to regress against
        module = surface_diff._module_name(name)
        changes = surface_diff.compare(
            surface_diff.surface(before.stdout, module),
            surface_diff.surface(path.read_text(encoding="utf-8"), module),
        )
        removals.extend(
            f"{name}: {change.kind} {change.name}"
            for change in changes
            if change.kind.startswith("removed") or change.kind.startswith("changed")
        )
    assert not removals, (
        "the qualified baseline's callers would break on:\n  " + "\n  ".join(removals)
    )


# --- a refusal is reported, never raised at the caller ------------------------

def test_every_tool_cli_reports_a_refusal_instead_of_raising_it():
    """Structural half. Every tool exited on an unhandled traceback when git
    could not answer — found by pointing the toolbelt at real projects rather
    than at fixtures, where three tools crashed identically and the crash was
    indistinguishable from a bug in the tool.

    Checked by shape rather than by running sixteen CLIs, so a NEW tool that
    forgets the wrapper fails here rather than the first time git refuses it.
    """
    unwrapped = []
    for path in sorted(ROOT.glob("tools/*.py")):
        source = path.read_text(encoding="utf-8")
        if 'if __name__ == "__main__":' not in source:
            continue
        entry = source.split('if __name__ == "__main__":', 1)[1]
        if "run_cli(" not in entry:
            unwrapped.append(f"tools/{path.name}")
    assert not unwrapped, (
        "these CLIs raise a refusal at the caller instead of reporting it: " + ", ".join(unwrapped)
    )


def test_a_refusal_becomes_a_stated_code_a_cause_and_an_exit_status(capsys):
    """Behavioural half, on the wrapper itself."""
    import errors

    def refuses(argv):
        raise errors.GitRefusal("git invocation failed", command="git ls-tree bad", returncode=128)

    status = errors.run_cli(refuses, [])
    printed = capsys.readouterr().out

    assert status == errors.GitRefusal.exit_status and status != 0
    assert "REFUSED" in printed and "HX_GIT_REFUSAL" in printed
    assert "git invocation failed" in printed          # the cause
    assert "git ls-tree bad" in printed                # the detail that locates it


def test_the_wrapper_does_not_swallow_an_exit_or_an_interrupt():
    """`argparse` exits by raising `SystemExit`, and a user interrupting is not
    a refusal. Catching either would turn a bad command line into a success and
    a Ctrl-C into a report."""
    import errors
    import pytest as _pytest

    with _pytest.raises(SystemExit):
        errors.run_cli(lambda argv: (_ for _ in ()).throw(SystemExit(2)), [])
    with _pytest.raises(KeyboardInterrupt):
        errors.run_cli(lambda argv: (_ for _ in ()).throw(KeyboardInterrupt()), [])


def test_a_tool_given_a_ref_git_cannot_resolve_prints_no_traceback(tmp_path):
    """End to end through a real subprocess, because the defect was that a
    traceback reached the terminal — which nothing testing return values would
    have caught."""
    import subprocess

    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", "."], cwd=repository, check=True)

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "workspace_report.py"), str(repository), "--ref", "no-such-ref"],
        capture_output=True, text=True,
    )
    if "unrecognized arguments" in result.stderr:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "outgoing_scan.py"), str(repository), "no-such-ref"],
            capture_output=True, text=True,
        )

    assert result.returncode != 0, result.stdout
    assert "Traceback" not in result.stderr, result.stderr
    assert "REFUSED" in result.stdout, result.stdout + result.stderr


# --- qualification is not self-tests --------------------------------------

def test_qualification_includes_probes_against_representative_consumer_shapes():
    """The failure class this release was caught by, made structural.

    Four audit rounds passed while the contract reader refused a real
    consumer's contract outright. Repository self-tests were green; the release
    was broken for the only consumer that had a Project Context. So a candidate
    may not claim qualification from self-tests alone: the suite must carry
    representative consumer shapes, and each must name the compatibility class
    it preserves.

    Deliberately checks the corpus is SUBSTANTIAL rather than merely present.
    An empty module satisfying an import would restore exactly the state this
    exists to prevent.
    """
    import consumer_shapes

    assert len(consumer_shapes.SHAPES) >= 5, (
        f"only {len(consumer_shapes.SHAPES)} representative consumer shapes; the corpus has "
        "been reduced to the point where it no longer stands in for real consumers"
    )
    for name, (description, template) in consumer_shapes.SHAPES.items():
        assert "project:" in template, f"{name} is not a project contract"
        assert len(description) > 40, f"{name} does not say which compatibility class it preserves"

    module = (ROOT / "tools" / "tests" / "test_consumer_compatibility.py")
    assert module.is_file(), "the consumer compatibility probes are gone"
    body = module.read_text(encoding="utf-8")
    assert body.count("def test_") >= 10, "the consumer probes have been hollowed out"


def test_no_representative_consumer_shape_depends_on_this_machine():
    """The corpus must outlive these particular personal directories, and must
    never carry private project content into the release."""
    import consumer_shapes

    for name, (description, template) in consumer_shapes.SHAPES.items():
        blob = description + template
        for forbidden in ("/Users/", "/home/", "C:\\\\"):
            assert forbidden not in blob, f"{name} carries an absolute personal path"


# --- the pin field set, bound the way D17 bound the push form ------------------


def test_the_documented_pin_field_set_is_the_one_the_verifier_requires():
    """D18 made `root_path` required, and three instructional surfaces still said
    "all three fields" — so following the bootstrap produced the exact state the
    release calls `UNVERIFIABLE_LEGACY_PIN`. Found by an independent audit. D17
    built this comparison for the push form and not for the field set, which is
    the very thing D18 changed.
    """
    import pack_migration

    required = pack_migration._REQUIRED_FOR_VERIFICATION
    spelled = {3: "three", 4: "four", 5: "five", 6: "six"}[len(required)]

    offenders = []
    #: `PACK_MANIFEST.json` included. It is the machine-readable identity
    #: document a consuming project is directed to read, and it was the one
    #: surface of four that the round-1 repair missed — found by round 3, in the
    #: field the repair itself had added.
    for name in ("README.md", "templates/PILOT_RUN_PROJECT_BOOTSTRAP.md",
                 "templates/PROJECT.yaml.template", "PACK_MANIFEST.json"):
        text = (ROOT / name).read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            lowered = line.lower()
            if "pin" not in lowered and "identified by" not in lowered:
                continue
            for word, count in (("three", 3), ("four", 4), ("five", 5)):
                if f"all {word}" in lowered and count != len(required):
                    offenders.append(f"{name}:{number}: says 'all {word}'")
    assert not offenders, (
        f"the pin requires {len(required)} fields ({', '.join(required)}), so these are wrong: "
        + "; ".join(offenders)
    )
    assert spelled  # the expected word, so a future change to the set is visible here


def test_root_path_is_among_the_fields_the_verifier_requires():
    import pack_migration

    assert "root_path" in pack_migration._REQUIRED_FOR_VERIFICATION


# --- the held-prose budget, measured rather than asserted ----------------------


def _held_prose_lines():
    """The in-release half of the `BUDGETS.md` count, measured."""
    total = 0
    for pattern in ("skills/core/*.md", "policy/*.md"):
        for path in sorted(ROOT.glob(pattern)):
            total += len(path.read_text(encoding="utf-8").splitlines())
    return total


def test_the_held_prose_figure_the_gate_record_states_is_the_measured_one():
    """`BUDGETS.md` requires this measured at every pack-evolution session, and
    the disclosure is the number. An independent audit found the release over
    budget with no measurement recorded and the previous release's disclosure
    deleted from the manifest — which is the one move the prior gate record says
    must not happen, because re-scoping the rule to fit the number is worse than
    the number.
    """
    import re

    measured = _held_prose_lines()
    gate = (ROOT / "docs" / "RP2.2-GATE.md").read_text(encoding="utf-8")
    stated = re.search(r"in-release \(skills/core/\*\.md \+ policy/\*\.md\)\s+([\d,]+)", gate)
    assert stated, "the gate record states no in-release held-prose figure"
    assert int(stated.group(1).replace(",", "")) == measured, (
        f"the gate record states {stated.group(1)}; the tree measures {measured}"
    )


def test_the_manifest_discloses_the_held_prose_breach_while_there_is_one(manifest):
    measured = _held_prose_lines()
    limitations = " ".join(manifest.get("known_limitations") or [])
    # The adapter half is read from the manifest's own disclosure rather than
    # guessed at — it was the one number in this file that was neither measured
    # nor bound.
    declared_adapters = re.search(r"(\d+) of\s+those lines are the two installed adapters", limitations)
    adapters = int(declared_adapters.group(1)) if declared_adapters else 0
    if measured + adapters > 2000:
        assert "held prose" in limitations, (
            "the release is over the held-prose target and the manifest does not say so"
        )


# --- D3 import closure, enforced rather than performed once by hand ------------


def test_every_tool_imports_only_the_standard_library_and_its_siblings():
    """D3, checked mechanically for the first time.

    `docs/RP2.1-GATE.md` records a one-off AST check performed by a person at
    2.1. Nine modules and three deliberately lazy imports landed after that with
    no permanent oracle — named as negative space by an independent audit. The
    walk covers function-local imports, which is where the lazy ones are.
    """
    import ast
    import sys

    tools = ROOT / "tools"
    siblings = {path.stem for path in tools.glob("*.py")}
    standard = set(sys.stdlib_module_names)

    violations = []
    for path in sorted(tools.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    violations.append(f"{path.name}:{node.lineno}: relative import")
                    continue
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                if name and name not in standard and name not in siblings:
                    violations.append(f"{path.name}:{node.lineno}: imports {name!r}")
    assert not violations, "D3 (import-closed toolbelt) is violated: " + "; ".join(violations)


def test_no_tool_reaches_a_module_by_name_at_runtime():
    """`__import__` and `importlib` would route around the check above."""
    import ast

    offenders = []
    for path in sorted((ROOT / "tools").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "__import__":
                    offenders.append(f"{path.name}:{node.lineno}")
            if isinstance(node, ast.Attribute) and node.attr == "import_module":
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, "dynamic imports route around D3: " + "; ".join(offenders)


def test_every_git_path_enumeration_in_the_toolbelt_asks_for_nul_separation():
    """`nul_paths` claims to cover **every** path enumeration in the toolbelt.
    It did not — `objects_in_outgoing_range` still split on lines, found by an
    independent audit. A universal claim needs a universal check.
    """
    import ast

    #: Git commands that emit paths and support `-z`.
    enumerating = {"ls-files", "ls-tree", "diff-tree", "diff", "rev-list", "for-each-ref",
                   "check-ignore", "status"}

    def string_literals(node):
        """Every string constant this call *passes to git*, however it is spelled.

        Three shapes reach git in this toolbelt, and the first version of this
        check saw only one — which made it structurally blind to
        `objects_in_outgoing_range`, the very function it was written for. An
        independent audit removed the `-z` the repair had added and this test
        still passed. A universal claim needs a check that is universal about
        *syntax* too:

        *   `_run(repo, "ls-files", "-z")`      — positional constants;
        *   `arguments = [...]` then `_run(repo, *arguments)` — a list built
            above the call and splatted into it;
        *   `subprocess.run(["git", "ls-files", "-z"])` — a list literal
            argument, which is how `pack_pin` spells it.
        """
        found = []
        for argument in list(node.args) + [
            keyword.value for keyword in node.keywords if keyword.arg is None
        ]:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                found.append(argument.value)
            elif isinstance(argument, (ast.List, ast.Tuple)):
                found.extend(
                    element.value for element in argument.elts
                    if isinstance(element, ast.Constant) and isinstance(element.value, str)
                )
            elif isinstance(argument, ast.Starred) and isinstance(argument.value, ast.Name):
                found.extend(splatted.get(argument.value.id, []))
        return found

    offenders = []
    for path in sorted((ROOT / "tools").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        # Every list assigned to a plain name, so a splat can be resolved back to
        # the literals it carries.
        splatted: dict[str, list[str]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, (ast.List, ast.Tuple)):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        splatted.setdefault(target.id, []).extend(
                            element.value for element in node.value.elts
                            if isinstance(element, ast.Constant) and isinstance(element.value, str)
                        )
            if isinstance(node, ast.AugAssign) and isinstance(node.value, (ast.List, ast.Tuple)):
                if isinstance(node.target, ast.Name):
                    splatted.setdefault(node.target.id, []).extend(
                        element.value for element in node.value.elts
                        if isinstance(element, ast.Constant) and isinstance(element.value, str)
                    )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            literals = string_literals(node)
            if not literals:
                continue
            if literals[0] == "git":
                if len(literals) < 2:
                    continue
                command = literals[1]
            else:
                command = literals[0]
            if command not in enumerating:
                continue
            if "--no-object-names" in literals:
                # `rev-list --objects --no-object-names` emits SHAs and no paths,
                # so there is nothing for `-z` to separate. A true negative, and
                # excluding it is more honest than adding a flag the command
                # does not need.
                continue
            emits_paths = command != "for-each-ref" and any(
                token in literals for token in ("--name-only", "--objects", "--cached",
                                                "--others", "--stage")
            ) or command in ("ls-files", "ls-tree")
            if emits_paths and "-z" not in literals:
                offenders.append(f"{path.name}:{node.lineno}: `git {command}` without -z")
    assert not offenders, (
        "these enumerate paths without NUL separation, so a path git C-quotes reaches a "
        "checker as an escaped literal: " + "; ".join(offenders)
    )


def test_no_document_states_a_pathmatch_divergence_figure_of_its_own():
    """The figure is computed in `test_pathmatch.py` and stated nowhere else.

    It was written from memory twice and was wrong twice — 13 on a grid that had
    been replaced, then 29 on the replaced grid in the commit that widened it
    again. Two independent audits caught it. The durable repair is not a better
    number: it is that no prose carries one, so there is nothing left to drift.
    """
    import re

    #: Every shape a hand-written divergence count takes. The first version
    #: required a digit immediately followed by the word, so
    #: `95 (88 under, 7 over)` — the only real restatement in the tree — sailed
    #: past it, and a third audit round shipped a fabricated `400 (390 under, 10
    #: over)` green to prove it. A guard that cannot see the thing it was
    #: written for is worse than the unbound number it replaced.
    number = r"(?:\d+|thirteen|twenty-?nine|ninety-?five|forty|fifty|sixty|seventy|eighty|ninety|hundred)"
    pattern = re.compile(
        rf"(?<![\d.])(?:"
        rf"{number}\s+(?:[\w/-]+\s+){{0,3}}(?:diverg|disagree|under-match|over-match)"
        rf"|{number}\s*\(\s*{number}\s+(?:under|over)"
        rf"|(?:left|leaving|remaining|remained)\s+(?:only\s+)?{number}\b"
        rf"|{number}\s+(?:under|over)-?match"
        rf")",
        re.IGNORECASE,
    )
    #: **This is a heuristic over prose and it is not complete.** It kills every
    #: restatement shape that has actually occurred, and a determined sentence
    #: can evade it. That is why the durable repair is the *computation* in
    #: `test_pathmatch.BASELINE_DIVERGENCES`, not this — this only stops the
    #: figure being copied back out into a document, which is what happened
    #: three times.
    #:
    #: No exemptions by phrasing. A list of "this line is historical" markers was
    #: the first attempt and it is the wrong shape: it has to be extended every
    #: time somebody writes a sentence the list did not anticipate, which is the
    #: same failure as a hand-written grid. **No prose states a divergence count
    #: at all** — the history is told without numbers, and the numbers live in
    #: the two test modules that compute them.

    #: **Every tracked file**, not a hand-written list. The sibling machine-path
    #: guard already worked this way; this one did not, so a restatement in a
    #: file nobody had listed was invisible. `tools/tests/test_pathmatch.py` is
    #: the one exemption: it is where the figure legitimately lives.
    import subprocess

    #: Only what this release wrote. A prior release's gate record is history,
    #: left as written — the same rule `_current_changelog_section` applies —
    #: and a convention introduced now cannot retroactively govern it. Derived
    #: from the diff rather than from a hand-written list of filenames, which is
    #: the shape that let a restatement hide in the first place.
    changed = subprocess.run(
        ["git", "diff", "--name-only", "-z",
         "4495e61850c08027e47eac6d0db84b4b3380e300", "HEAD"],
        cwd=str(ROOT), capture_output=True, check=True,
    ).stdout
    touched = [entry.decode("utf-8") for entry in changed.split(b"\0") if entry]
    assert touched, "the diff against the baseline is empty; the scan would cover nothing"

    offenders = []
    for name in touched:
        # Exempted by *line*, not by filename. Exempting the whole file let the
        # refuted `13` survive in that module's own prose — the hand-written
        # filename list this rule elsewhere says it rejects. Only the assignment
        # that carries the computed figure, and this rule's own description of
        # itself, are allowed to contain one.
        exempt_line = ("BASELINE_DIVERGENCES = (", "number = r", "rf\"")
        if name == "tools/tests/test_release_integrity.py":
            continue        # where this rule lives and describes itself
        if not (ROOT / name).exists():
            continue        # deleted in the delta
        try:
            text = (ROOT / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):  # pragma: no cover - environment
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if pattern.search(line) and not any(
                marker in line for marker in exempt_line
            ):
                offenders.append(f"{name}:{number}: {line.strip()[:90]}")
    assert not offenders, (
        "these state a divergence count in prose; the figure is computed by "
        "test_pathmatch.BASELINE_DIVERGENCES and must not be restated: " + "; ".join(offenders)
    )


def test_the_gate_record_qualification_figures_are_measured(manifest):
    """Every number in the gate record's qualification section, against reality.

    Round 2 of the closure audits found *four* stale figures in this one section
    — the suite count twice, the falsification count and the delta — all written
    fresh in the repair commit and all carried from the revision before it. Both
    auditors reached the same conclusion independently: **every number this
    release binds to a test is correct, and every number it does not is stale.**
    So these are bound.
    """
    import re
    import subprocess

    gate = (ROOT / "docs" / "RP2.2-GATE.md").read_text(encoding="utf-8")

    # The suite count must NOT be restated here. Adding a test changes it, and a
    # figure this document's own edit invalidates is one it must not carry — the
    # same rule the delta below follows, and the same reason the manifest does
    # not name its own revision. Four stale figures in this one section is what
    # taught it.
    counts = re.findall(r"\*\*(\d+) passed\*\*", gate)
    assert not counts, (
        f"the gate record restates a suite count ({counts}); it must point at "
        "PACK_MANIFEST.json tests.passed instead"
    )
    assert "PACK_MANIFEST.json` `tests.passed" in gate, (
        "the gate record does not say where the suite count lives"
    )
    assert manifest["tests"]["passed"] > 0

    # The delta must NOT be stated as a literal. Editing this file changes it,
    # so any number written there is wrong from the moment it is committed —
    # the manifest's own-revision problem, in prose. The document gives the
    # command instead, and this asserts that it still does.
    assert re.search(r"Delta against the frozen baseline: \*\*not stated here\.\*\*", gate), (
        "the gate record states a literal delta; it must give the command instead"
    )
    assert "git diff --shortstat" in gate, "the gate record gives no way to measure the delta"
    assert not re.search(r"\d+ files changed, [\d,]+ insertions", gate), (
        "a literal delta reappeared in the gate record"
    )
    subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True, check=True)


def test_the_release_packet_and_the_manifest_agree_on_the_prose_breach():
    """The packet is what a returning release authority reads first, and it
    under-stated the release's only recorded budget breach because it was
    computed with the *previous* release's adapter line count. Found by an
    independent audit."""
    import json
    import re

    manifest = json.loads((ROOT / "PACK_MANIFEST.json").read_text(encoding="utf-8"))
    limitations = " ".join(manifest.get("known_limitations") or [])
    manifest_percentage = re.search(r"\(([\d.]+)% over", limitations)
    assert manifest_percentage, "the manifest states no held-prose percentage"

    for name in ("docs/RP2.2-GATE.md", "docs/RP2.2-RELEASE-PACKET.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        stated = set(re.findall(r"([\d.]+)% over the ~2,000|([\d.]+)% over, recorded", text))
        for pair in stated:
            value = pair[0] or pair[1]
            assert value == manifest_percentage.group(1), (
                f"{name} states {value}% over; the manifest states "
                f"{manifest_percentage.group(1)}%"
            )


def test_no_tracked_file_carries_a_real_machine_path():
    """The pack's own rule, applied to the pack.

    An independent audit found `/Users/<name>/.gitignore_global` shipped in a
    findings document — pre-existing, and refused by this release's own
    `contains_local_path`. Redacted to `<home>`, and pinned here so the next one
    fails rather than ships.

    Synthetic fixtures are exempt by name. They exist *because* the scanner must
    find this shape, and a check that refused them would refuse the tests that
    prove the scanner works.
    """
    import re
    import subprocess

    #: Names that only ever appear as synthetic fixtures. Two plausible-looking
    #: words were on this list and should not have been: exempting a name a real
    #: person might use means a real home directory under that name passes the
    #: guard. An audit pointed it out. The list is now the smallest set that
    #: still lets the scanner's own negative fixtures live in the tree, and the
    #: fixtures that used the removed words were renamed rather than exempted.
    fixture_names = ("someone", "alice", "exampleuser")
    real = re.compile(r"/(?:Users|home)/(?!(?:%s)\b)[\w.\-]+" % "|".join(fixture_names))

    listing = subprocess.run(
        ["git", "ls-files", "-z"], cwd=str(ROOT), capture_output=True, check=True
    ).stdout
    offenders = []
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        path = ROOT / entry.decode("utf-8", "surrogateescape")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):  # pragma: no cover - environment
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if real.search(line):
                offenders.append(f"{entry.decode()}:{number}: {line.strip()[:80]}")
    assert not offenders, "these ship a real machine path: " + "; ".join(offenders)


def test_no_tracked_file_carries_a_live_session_or_transcript_identifier():
    """Session and transcript identifiers are private runtime state.

    One shipped: a fixture payload in the resource-observation tests carried the
    real session id of the session that wrote it. Harmless in isolation, and
    exactly the category a private remote is not permission to store — which is
    why it is pinned rather than argued about.

    Deliberately narrow. A bare UUID is not evidence of anything, and banning
    the shape would refuse every legitimate identifier fixture in the tree. What
    is refused is a UUID sitting in the position of a session or transcript
    identifier, unless it is the one obviously-fictional value reserved for that
    use.
    """
    import re
    import subprocess

    #: A UUID whose shape announces it is not real. Anything else in this
    #: position came from somewhere.
    FICTIONAL = "00000000-0000-4000-8000-000000000000"
    suspicious = re.compile(
        r"(session_id|transcript_path|conversation_id)\W{0,4}"
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        re.IGNORECASE,
    )

    listing = subprocess.run(
        ["git", "ls-files", "-z"], cwd=str(ROOT), capture_output=True, check=True
    ).stdout
    offenders = []
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        name = entry.decode("utf-8", "surrogateescape")
        try:
            text = (ROOT / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):  # pragma: no cover - environment
            continue
        for number, line in enumerate(text.splitlines(), 1):
            match = suspicious.search(line)
            if match and match.group(2).lower() != FICTIONAL:
                offenders.append(f"{name}:{number}: {match.group(1)}")
    assert not offenders, (
        "these carry what looks like a live session identifier: " + "; ".join(offenders)
    )


def test_the_routing_table_states_the_observation_count_it_was_derived_from():
    """A count in prose beside a derived view is a number nothing checks — the
    defect this release spent three audit rounds on. Bound here."""
    import re

    table = (ROOT / "policy" / "routing-table.md").read_text(encoding="utf-8")
    log = (ROOT / "policy" / "observations.jsonl").read_text(encoding="utf-8")
    rows = len([line for line in log.splitlines() if line.strip()])

    stated = re.search(r"from \*\*(\d+)\*\* observations", table)
    assert stated, "the routing table does not say how many observations it was derived from"
    assert int(stated.group(1)) == rows, (
        f"the routing table says {stated.group(1)} observations; the log holds {rows}"
    )
