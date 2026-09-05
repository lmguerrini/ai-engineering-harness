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


def _release_doc_prefix() -> str:
    """`RP2.3` for a release whose manifest names `docs/RP2.3-GATE.md`.

    Derived, never typed. Three guards below scoped themselves to a literal
    `docs/RP2.2-*.md`, and the moment a decision was appended for the next
    release one of them demanded that a **superseded release's own gate record**
    be edited to satisfy a rule invented after it was written — the one move
    this pack's policy forbids outright. Its sibling guard already exempted
    prior releases for exactly that reason, so the two disagreed about whose
    documents they were checking.

    The manifest already declares the gate record, and a checker that read the
    declaration could not have disagreed with it. So this reads it.
    """
    import json

    gate = json.loads((ROOT / "PACK_MANIFEST.json").read_text(encoding="utf-8"))["gate_record"]
    stem = Path(gate).stem
    assert "-" in stem, f"the gate record {gate!r} does not carry a release prefix"
    return stem.split("-", 1)[0]


def _owned_release_docs() -> tuple[str, ...]:
    """The `docs/` glob for the release under construction, and only it."""
    return (f"docs/{_release_doc_prefix()}-*.md",)


def _current_gate_record() -> Path:
    import json

    return ROOT / json.loads((ROOT / "PACK_MANIFEST.json").read_text(encoding="utf-8"))["gate_record"]


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
    """**NOT A MUTATION ORACLE.** This fails on ANY byte change to the tree,
    including a semantically null one, because it compares a recorded identity
    against the checkout. Exclude it when scoring mutants: two independent
    readers recorded spurious "killed" verdicts from this test and had to
    re-run their passes."""
    digest, count = pack_pin.tree_digest(ROOT)
    assert digest == manifest["tree_digest_sha256"]
    assert count == manifest[pack_pin.DIGEST_COUNT_KEY]


def test_the_release_identity_fields_are_well_formed(manifest):
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["tree_digest_sha256"])
    assert manifest["digest_excludes"] == pack_pin.MANIFEST_NAME
    assert manifest["digest_algorithm"] == pack_pin.DIGEST_ALGORITHM
    assert isinstance(manifest[pack_pin.DIGEST_COUNT_KEY], int) and manifest[pack_pin.DIGEST_COUNT_KEY] > 0


def test_this_checkout_verifies_against_its_own_manifest(manifest, version):
    """**NOT A MUTATION ORACLE.** This fails on ANY byte change to the tree,
    including a semantically null one, because it compares a recorded identity
    against the checkout. Exclude it when scoring mutants: two independent
    readers recorded spurious "killed" verdicts from this test and had to
    re-run their passes."""
    assert pack_pin.verify_pin(
        ROOT,
        expect_version=version,
        expect_digest=manifest["tree_digest_sha256"],
        expect_state=manifest["state"],
    ) == []


def test_the_manifest_is_the_only_thing_excluded_from_its_own_digest(manifest):
    """**NOT A MUTATION ORACLE.** This compares a COUNT of tracked files, so a
    semantically null edit that adds or removes one fails it. Exclude it when
    scoring mutants: independent readers recorded spurious "killed" verdicts from
    this family and had to re-run. (Two earlier versions of this note were wrong
    about what it compares — first "a digest", then "either count" — each caught
    by a bounded reading.)"""
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

    **NOT A MUTATION ORACLE.** This compares a COUNT of collected tests, so
    adding or removing a test fails it whatever else the edit did. Exclude it
    when scoring mutants. (Two earlier versions of this note were wrong about
    what it compares — first "a digest", then "either count" — each caught by a
    bounded reading.)
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
    """**NOT A MUTATION ORACLE.** This fails on ANY byte change to the tree,
    including a semantically null one, because it compares a recorded identity
    against the checkout. Exclude it when scoring mutants: two independent
    readers recorded spurious "killed" verdicts from this test and had to
    re-run their passes."""
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
QUALIFIED_BASELINE = "ab7dea97a12c699e8123bcb5d5be976cd05c075e"


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


def test_no_tool_cli_ever_prints_a_traceback_for_an_input_it_refuses(tmp_path):
    """Every CLI, actually EXECUTED, against inputs designed to be refused.

    The structural check below greps the `__main__` block for the wrapper. An
    independent audit showed that is vacuous with respect to the guarantee it
    names: two tools contained the wrapper and still printed tracebacks, because
    the exceptions they raised were not in the hierarchy the wrapper catches and
    because only five of seventeen CLIs were ever executed anywhere in the suite.

    So this runs all of them, as subprocesses, and asserts the invariant that
    actually matters: **a traceback never reaches the caller.** It does not need
    to know each tool's refusal vocabulary — every argv below is either refused,
    rejected by argparse, or handled, and none of those may traceback.
    """
    import subprocess

    malformed = tmp_path / "PROJECT.yaml"
    malformed.write_text(
        "project:\n  name: x\n  repo_path: /nowhere/at/all\n"
        "requires:\n  a_key_nothing_checks: true\n"
    )
    unreadable_context = tmp_path / "context.yaml"
    unreadable_context.write_text(
        "project:\n  name: x\n"
        "project_context:\n  context_id: C1\n  reference_path: /x\n  control_revision: 12\n"
    )
    scalar_pack = tmp_path / "scalar.yaml"
    scalar_pack.write_text("project:\n  name: x\npack: 2.2.0\n")
    unquoted_version = tmp_path / "unquoted.yaml"
    unquoted_version.write_text(
        "project:\n  name: x\npack:\n  root_path: /x\n  version_adopted: 3\n"
        "  sha_adopted: aaaa\n  tree_digest_sha256: bbbb\n  state_adopted: QUALIFIED_AND_FROZEN\n"
    )
    # Bytes, not text. The first version of this corpus was entirely UTF-8, so
    # it could not constrain the invariant its own docstring states — an audit
    # falsified that invariant in one command, on a class of input this list
    # simply did not contain. `read_text` signals undecodable bytes with a
    # `ValueError`, which is not an `OSError`, which is how it escaped.
    not_utf8 = tmp_path / "not-utf8.yaml"
    not_utf8.write_bytes(b'project:\n  name: "\xff\xfe\x00"\n')
    binary = tmp_path / "binary.bin"
    binary.write_bytes(bytes(range(256)) * 4)

    empty = tmp_path / "not-a-repo"
    empty.mkdir()
    missing = tmp_path / "does-not-exist"

    argv_forms = [
        ["--project", str(malformed)],
        ["--project", str(unreadable_context)],
        ["--project", str(scalar_pack)],
        ["--project", str(unquoted_version)],
        ["--project", str(not_utf8)],
        [str(malformed)],
        [str(scalar_pack)],
        [str(unquoted_version)],
        [str(not_utf8)],
        [str(binary)],
        [str(unreadable_context)],
        [str(missing)],
        [str(empty), "no-such-ref"],
        [str(empty)],
    ]

    # EVERY CLI × EVERY FORM, run concurrently. The work is hundreds of
    # interpreter startups against refusal paths that write nothing, so the wall
    # time was startup rather than anything the test verifies. Nothing about
    # WHAT is executed or asserted changes: the same argv reach the same tools
    # with the same working directory, and the counting is done after the fact
    # rather than by incrementing shared state, so the result does not depend on
    # the order they finish in.
    from concurrent.futures import ThreadPoolExecutor

    invocations = [
        (path, argv)
        for path in sorted(ROOT.glob("tools/*.py"))
        if 'if __name__ == "__main__":' in path.read_text(encoding="utf-8")
        for argv in argv_forms
    ]

    def invoke(invocation):
        path, argv = invocation
        result = subprocess.run(
            [sys.executable, str(path), *argv],
            capture_output=True, text=True, cwd=str(tmp_path), timeout=120,
        )
        traceback = None
        if "Traceback (most recent call last)" in result.stderr:
            first = [
                line for line in result.stderr.strip().splitlines()
                if line and not line.startswith(" ")
            ]
            traceback = f"tools/{path.name} {' '.join(argv[:2])}: {first[-1][:70]}"
        refused = "REFUSED" in result.stdout or "REFUSED" in result.stderr
        return traceback, refused

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(invoke, invocations))

    tracebacks = [traceback for traceback, _refused in outcomes if traceback]
    refusals = sum(1 for _traceback, refused in outcomes if refused)

    assert not tracebacks, "these printed a traceback instead of a refusal:\n  " + "\n  ".join(
        sorted(set(tracebacks))
    )
    assert refusals >= 5, (
        f"only {refusals} invocations reached a stated refusal; this test is not exercising "
        "the refusal path it exists to check"
    )


# --- a CLI must run the module, not a second copy of it -----------------------

def test_every_cli_entry_runs_the_canonical_module():
    """A file executed as a script is `__main__`. A sibling that imports it by
    name gets a SEPARATE module object with SEPARATE class objects, so an
    `isinstance` check across that boundary is False for an object that is
    exactly that class.

    It crashed `project_context.py --project` against a real consumer's
    contract, with a traceback, on a shape the suite covers completely — because
    tests import the module and never run it as a script. Structural, so a new
    tool that reintroduces the split fails here rather than the first time
    somebody runs it.
    """
    offenders = []
    for path in sorted(ROOT.glob("tools/*.py")):
        source = path.read_text(encoding="utf-8")
        if 'if __name__ == "__main__":' not in source:
            continue
        entry = source.split('if __name__ == "__main__":', 1)[1]
        if "import _cli as _entry" not in entry or "run_cli(_entry" not in entry:
            offenders.append(f"tools/{path.name}")
    assert not offenders, (
        "these run a second copy of themselves, so an isinstance across a sibling "
        "boundary is False: " + ", ".join(offenders)
    )


def test_a_cli_and_an_import_agree_about_a_type_that_crosses_a_sibling_boundary(tmp_path):
    """The behavioural half, through a real subprocess, on the exact shape that
    crashed: a context declaration built by `project_contract` and classified by
    `project_context`."""
    import subprocess

    contract = tmp_path / "PROJECT.yaml"
    contract.write_text(
        "project:\n  name: x\n"
        "project_context:\n  context_id: C1\n  reference_path: /x\n  control_revision: 12\n"
    )

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "project_context.py"), "--project", str(contract)],
        capture_output=True, text=True,
    )
    assert "Traceback" not in result.stderr, result.stderr
    assert "UNVERIFIABLE" in result.stdout, result.stdout + result.stderr
    assert result.returncode != 0


def test_the_baseline_figure_this_release_quotes_is_the_baselines_own():
    """A release comparing itself to its predecessor must quote the
    predecessor, not itself.

    The manifest pasted **this** release's percentage onto the baseline's line
    count, so the two read as identical on a budget where held prose had in fact
    grown. An independent audit caught it; the existing guard could not, because
    its regex takes the FIRST `(N% over)` on the line and never reaches the
    restated one. Read from the frozen commit rather than from anywhere a
    later edit can reach.
    """
    import json
    import re
    import subprocess

    baseline = json.loads(
        subprocess.run(
            ["git", "show", f"{QUALIFIED_BASELINE}:PACK_MANIFEST.json"],
            cwd=str(ROOT), capture_output=True, text=True, check=True,
        ).stdout
    )
    recorded = next(
        entry for entry in baseline["known_limitations"] if entry.startswith("held prose ")
    )
    lines = re.search(r"held prose (\d+) lines", recorded).group(1)
    percent = re.search(r"\(([\d.]+)% over", recorded).group(1)

    manifest = json.loads((ROOT / "PACK_MANIFEST.json").read_text(encoding="utf-8"))
    quoting = next(
        entry for entry in manifest["known_limitations"] if entry.startswith("held prose ")
    )
    baseline_version = subprocess.run(
        ["git", "show", f"{QUALIFIED_BASELINE}:VERSION"],
        cwd=str(ROOT), capture_output=True, text=True, check=True,
    ).stdout.strip()
    stated = re.search(rf"{re.escape(baseline_version)} was {lines} \(([\d.]+)% over\)", quoting)
    assert stated, (
        f"this release does not quote the baseline's own figure "
        f"({baseline_version}: {lines} lines, {percent}% over)"
    )
    assert stated.group(1) == percent, (
        f"this release says {baseline_version} was {stated.group(1)}% over; that release's "
        f"own manifest records {percent}%"
    )


def test_every_pointer_at_the_decision_layer_reaches_the_last_decision():
    """`DECISIONS.md` is append-only, so every range naming its end goes stale
    the next time a decision is added — and two did: the README said `D1-D19`
    and the packet said `D14-D19` while the file held D22, routing a reader
    away from the three decisions that govern the capability this release adds.

    Bound rather than corrected, because correcting it is what was done last
    time. Any range whose upper bound is a decision number must name the highest
    decision the file actually contains.
    """
    import re

    decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    numbers = [int(match) for match in re.findall(r"(?m)^## D(\d+)", decisions)]
    assert numbers, "DECISIONS.md declares no decisions"
    last = max(numbers)

    #: `D<n>` followed by any dash and `D<m>` — the shape a range takes here.
    ranges = re.compile(r"\bD(\d+)\s*[-\u2010-\u2015]\s*D(\d+)\b")
    offenders = []
    scanned = 0
    for pattern in ("README.md", *_owned_release_docs(), "PACK_MANIFEST.json", "CHANGELOG.md"):
        for path in sorted(ROOT.glob(pattern)):
            if not path.is_file():
                continue
            name = str(path.relative_to(ROOT))
            scanned += 1
            body = path.read_text(encoding="utf-8")
            # A previous release's entry is history and is left as written; the
            # rule applies to the entry this release is adding.
            if name == "CHANGELOG.md":
                body = _current_changelog_section(body)
            for number, line in enumerate(body.splitlines(), 1):
                # A range describing a CLOSED historical set — "D1-D13 are
                # unchanged" — is not a pointer at the decision layer and must
                # not be dragged forward every time a decision is added. The
                # exemption is by the words that make the line say so, so it
                # stays visible in the text instead of hiding in a list here.
                if any(word in line.lower() for word in ("unchanged", "inherited", "prior")):
                    continue
                for low, high in ranges.findall(line):
                    if int(high) != last:
                        offenders.append(f"{name}:{number}: D{low}-D{high}, but the file ends at D{last}")

    assert scanned >= 3, f"only {scanned} documents scanned; the globs are not matching"
    assert not offenders, (
        "these point at a decision range that stops short of the last decision: "
        + "; ".join(offenders)
    )


#: The count shapes no release document may restate, and the scan that finds
#: them. Lifted out of the guard so the guard and the test that proves the guard
#: can fail read the same code — a bound that reimplemented the pattern would
#: pass while the guard used a different one.
_RESTATED = re.compile(
    r"\b\d+\s+(?:tool\s+)?modules\b"
    r"|\bacross\s+\d+\s+modules\b"
    r"|\b\d+\s+CLIs?\b"
    r"|\b\d+\s+(?:passing\s+)?tests\b"
    # AND THE THREE THE MATRIX AND THE POLICY FILES COMPUTE. A packet
    # claiming sixty-three mechanisms beside a matrix holding ninety, and
    # thirty-nine recurrence classes beside a policy file holding
    # forty-seven, is the same defect wearing a different noun. Both were
    # found by an outside reader, not by this guard.
    r"|\b\d+\s+(?:verified\s+)?failure\s+mechanisms\b"
    r"|\b\d+\s+(?:mandated\s+)?recurrence\s+classes\b"
    r"|\b\d+\s+(?:blind\s+)?closure\s+audits\b"
    # SPELLED OUT, TOO — but only where the sentence asserts a RUNNING
    # TOTAL. `Eight blind closure audits` and `what eight independent
    # readings cost` sailed past a guard that only knew digits, in the
    # heading of the section about how many there had been; found by the
    # second reader to adopt the release in a clean room.
    #
    # Deliberately not every spelled-out number near the word `audit`. A
    # release record is full of true sentences about the past — *unread by
    # twelve audits*, *abandoned after four audit rounds* — and those do not
    # go stale when another one runs. A guard that forbade them would be
    # turned off, which is worse than a guard that catches three shapes.
    r"|\b(?:\d+|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen)\s+"
    r"blind\s+closure\s+audits\b"
    r"|\bwhat\s+(?:\d+|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen)\s+"
    r"(?:independent\s+)?readings\b"
    r"|\b(?:one|two|three|\d+)\s+of\s+the\s+"
    r"(?:\d+|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen)\s+readings\b",
    re.IGNORECASE,
)


#: A count of something FROZEN cannot drift, so it is not this rule's business.
#: The exemption is by the words that make the line say so, which keeps it
#: visible in the text rather than hidden in a list here.
_EXEMPT = ("baseline", "frozen", "tests.passed", "collect-only")


def _restated_counts(text: str) -> list:
    """Every restated count in one document, as ``(line number, what)``.

    **Over the whole document, not a line at a time.** `1207` ended one line and
    `tests` began the next, so the guard written to catch a hand-typed test
    count could not see one for as long as the sentence happened to wrap there.
    """
    found = []
    for match in _RESTATED.finditer(text):
        number = text.count("\n", 0, match.start()) + 1
        spans = text[text.rfind("\n", 0, match.start()) + 1:
                     text.find("\n", match.end()) + 1 or None].lower()
        if not any(marker in spans for marker in _EXEMPT):
            found.append((number, match.group(0)))
    return found


def test_no_document_restates_a_count_of_things_the_repository_can_count():
    """The unbound-figure class, closed structurally rather than corrected again.

    This release has now shipped seven figures of this shape: a divergence
    count, a routing-table audit count, a held-prose percentage quoted from the
    wrong release, a module count that said 19 when there were 20, and then a
    test total, a mechanism total and a recurrence total in the packet a founder
    reads to decide. Every one was typed by hand beside a fact the repository
    can compute, and every one went stale the moment the thing it counted
    changed.

    So no document may restate them. Each is one command away, and a reader who
    wants the number should run that command rather than trust a sentence.

    Deliberately narrow. A release record is full of legitimate counts —
    findings, rounds, occurrences, and true sentences about the past like
    *unread by twelve audits* — and a guard broad enough to catch those would be
    turned off, which is worse than one that catches the shapes that drift.
    """
    owned = (*_owned_release_docs(), "README.md", "CHANGELOG.md", "policy/*.md",
             "templates/*.md", "skills/core/*.md")
    offenders = []
    seen = set()
    for pattern in owned:
        for path in sorted(ROOT.glob(pattern)):
            name = str(path.relative_to(ROOT))
            if name in seen or not path.is_file():
                continue
            seen.add(name)
            for number, what in _restated_counts(path.read_text(encoding="utf-8")):
                offenders.append(f"{name}:{number}: {what!r}")
    assert len(seen) >= 6, f"only {len(seen)} owned documents scanned; the globs are not matching"

    assert not offenders, (
        "these restate a count the repository can compute, which is how the last seven "
        "stale figures got in: " + "; ".join(offenders)
    )


@pytest.mark.parametrize("shape,text", [
    ("a test total", "the suite holds 412 tests and they all pass"),
    ("a test total that wraps", "the suite holds 412\ntests and they all pass"),
    ("a module count", "there are 21 tool modules in this release"),
    ("a mechanism total", "the matrix holds 63 verified failure mechanisms"),
    ("a mechanism total that wraps", "the matrix holds 63 verified\nfailure mechanisms"),
    ("a recurrence total", "39 mandated recurrence classes, each with an oracle"),
    ("a spelled-out running total", "Eight blind closure audits, all NOT READY"),
    ("a spelled-out heading", "## What eight independent readings cost"),
])
def test_the_count_guard_catches_the_shapes_it_claims_to(shape, text):
    """**The guard had no negative case, and a mutant proved it.**

    Making it read only the first line of every document changed nothing that
    any test could see, because the documents happen to be clean — a check that
    finds nothing passes whether it looked everywhere or nowhere. These are the
    shapes it has actually let through, planted.
    """
    assert _restated_counts(text), f"the guard does not catch {shape}"


@pytest.mark.parametrize("shape,text", [
    ("a true sentence about the past", "unread by twelve audits, and found by the thirteenth"),
    ("a budget ceiling", "four audit rounds per capability, raised only by a person"),
    ("a finding count", "the round returned 15 findings, 3 of them in the previous repairs"),
    ("a frozen baseline", "the frozen 2.2.0 baseline recorded 1207 tests"),
    ("the manifest key", "tests.passed is 1799 in the manifest"),
])
def test_the_count_guard_leaves_an_honest_sentence_alone(shape, text):
    """The other half. A guard that flagged these would be turned off within a
    week, and a guard nobody runs catches nothing at all."""
    assert not _restated_counts(text), f"the guard wrongly flags {shape}"


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
    gate = _current_gate_record().read_text(encoding="utf-8")
    stated = re.search(r"in-release \(skills/core/\*\.md \+ policy/\*\.md\)\s+([\d,]+)", gate)
    assert stated, "the gate record states no in-release held-prose figure"
    assert int(stated.group(1).replace(",", "")) == measured, (
        f"the gate record states {stated.group(1)}; the tree measures {measured}"
    )


def test_the_held_prose_guard_refuses_rather_than_passing_when_it_cannot_measure():
    """The guard above must fail on a manifest with no adapter figure, rather
    than treating the absence as zero and skipping its own assertion."""
    import re as _re

    for wording in ("held prose 9999 lines against a ~2000 target (400% over)", ""):
        found = _re.search(r"(\d+)\D{0,80}?installed adapters", wording,
                           _re.IGNORECASE | _re.DOTALL)
        assert found is None, "a disclosure with no adapter figure must not satisfy the pattern"

    real = ("held prose 2576 lines against a ~2000 target (28.8% over ...). the 1023 that put "
            "the total over are the two installed adapters, outside this envelope")
    found = _re.search(r"(\d+)\D{0,80}?installed adapters", real, _re.IGNORECASE | _re.DOTALL)
    assert found and int(found.group(1)) == 1023, (
        "the pattern must read the figure out of the wording the manifest actually uses"
    )


def test_the_manifest_discloses_the_held_prose_breach_while_there_is_one(manifest):
    measured = _held_prose_lines()
    limitations = " ".join(manifest.get("known_limitations") or [])
    # The adapter half is read from the manifest's own disclosure rather than
    # guessed at — it was the one number in this file that was neither measured
    # nor bound.
    # REFUSED, never defaulted. This regex was written against 2.2.0's wording;
    # 2.3.0 rewrote the sentence and the match became `None`, `adapters` became
    # `0`, the `if` below became unreachable, and the guard passed vacuously —
    # it would have passed with the entire disclosure deleted, which is the
    # exact regression its sibling records having happened once. Found by an
    # independent auditor. A fallback to zero in a guard is the guard's own
    # off switch.
    declared_adapters = re.search(
        r"(\d+)\D{0,80}?installed adapters", limitations, re.IGNORECASE | re.DOTALL)
    assert declared_adapters, (
        "the manifest states no adapter line count, so this guard cannot compute the total it "
        "exists to check. It refuses rather than assuming zero: assuming zero is how it stopped "
        "binding the last time the sentence was reworded"
    )
    adapters = int(declared_adapters.group(1))
    assert adapters > 0, "an adapter count of zero would make the total unmeasurable"
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

    gate = _current_gate_record().read_text(encoding="utf-8")

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

    prefix = _release_doc_prefix()
    surfaces = [_current_gate_record(), ROOT / "docs" / f"{prefix}-RELEASE-PACKET.md"]
    present = [path for path in surfaces if path.is_file()]
    assert _current_gate_record() in present, "the gate record the manifest names does not exist"
    for path in present:
        name = str(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8")
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


# --- the closure matrix is an artifact, and artifacts drift -------------------------


def _matrix_rows():
    import pathlib

    rows = []
    for line in (ROOT / "docs" / "RP2.3-FAILURE-MODE-CLOSURE.md").read_text(
            encoding="utf-8").split("\n"):
        if line.startswith("| M-"):
            rows.append([c.strip() for c in line.strip().strip("|").split(" | ")])
    return rows


def test_every_mechanism_identifier_names_one_mechanism():
    """Sixteen identifiers once named two mechanisms each, because the table grew
    in two places and both reused the same numbers. A closure matrix whose
    identifiers do not identify is not a matrix, and it is this release's central
    evidence artifact."""
    rows = _matrix_rows()
    seen = {}
    for row in rows:
        assert row[0] not in seen, f"{row[0]} names both {seen.get(row[0])!r} and {row[1]!r}"
        seen[row[0]] = row[1]
    assert len(rows) > 60, "the matrix lost rows"


def test_every_row_has_the_four_columns_the_table_declares():
    """`M-18e` had three, with its oracle folded into the disposition cell — so a
    check that read the fourth column found no oracle and reported a gate
    failure about a row that had one. The shape is checked because the readers of
    this table are programs as well as people."""
    for row in _matrix_rows():
        assert len(row) == 4, f"{row[0]} has {len(row)} columns, not four: {row}"


def test_every_disposition_is_one_the_release_authorised():
    vocabulary = ("PREVENTED", "DETECTED_AND_BLOCKED", "SAFELY_RECOVERABLE",
                  "ALREADY_COVERED", "DEFERRED")
    for row in _matrix_rows():
        stated = row[2].strip("* ")
        assert any(stated.startswith(word) for word in vocabulary), \
            f"{row[0]} is dispositioned {stated!r}, which is not one of {vocabulary}"


def test_every_non_deferred_mechanism_names_an_oracle():
    """A description of a mechanism is evidence about the design, not a
    demonstration that it holds today. Fifty-one rows described their closure and
    named nothing runnable until the final evidence-completeness audit."""
    for row in _matrix_rows():
        if row[2].strip("* ").startswith("DEFERRED"):
            continue
        # The SAME spelling the selector parser requires. The two guards read
        # different syntax — this one accepted any `Oracle:` and the parser
        # required `**Oracle:**` — so a non-bold entry satisfied the presence
        # check and was silently skipped by the one that actually runs it. Found
        # by an independent reader building a table with one of each.
        assert "**Oracle:**" in row[3], f"{row[0]} names no oracle: {row[3][:80]}"


def test_every_oracle_the_matrix_names_selects_at_least_one_test():
    """A selector that matches nothing is a passing command and an empty claim.
    Four of the selectors written first matched no test at all and reported green
    by selecting nothing."""
    import re
    import subprocess
    import sys

    selectors = []
    for row in _matrix_rows():
        found = re.search(r"\*\*Oracle:\*\*\s*(.+)$", row[3])
        if not found:
            continue
        parts = re.findall(r"`([^`]+)`", found.group(1))
        if not parts:
            continue
        # Rows written at different times name the file either bare or with its
        # directory, so both are resolved. The first version built
        # `<pack>/test_continuation.py`, which exists nowhere, and reported that
        # EVERY oracle selected nothing — a check that fails on all inputs is as
        # uninformative as one that passes on all of them.
        files = []
        for piece in parts[0].split():
            if not piece.endswith(".py"):
                continue
            files.append(piece if "/" in piece else f"tools/tests/{piece}")
        keyword = None
        for piece in parts[1:]:
            if piece.startswith("-k "):
                keyword = piece[3:].strip().strip('"')
        if files:
            selectors.append((row[0], files, keyword))

    # EVERY ROW THAT NAMES ONE, counted rather than a floor — a floor passes
    # while rows go unparsed, which is exactly how a non-bold entry hid.
    #
    # Compared against the rows that NAME an oracle, not against the non-deferred
    # rows: both deferred mechanisms name one too, and a deferred mechanism with
    # a bounded oracle behind it is better than one without. The first version
    # compared against non-deferred and reported two rows missing that were
    # present and correct.
    expected = [r[0] for r in _matrix_rows() if "**Oracle:**" in r[3]]
    assert len(selectors) == len(expected), (
        f"{len(expected) - len(selectors)} row(s) name an oracle the parser did not read: "
        f"{sorted(set(expected) - {s[0] for s in selectors})}")

    # THE SAME COMMANDS, THE SAME ASSERTION, RUN CONCURRENTLY AND ONCE EACH.
    # This was the slowest check in the suite by a factor of two, spending its
    # time in interpreter startup rather than in anything it verifies.
    #
    # Reimplementing pytest's `-k` expression in-process would collapse it to a
    # single collection and was rejected: the guard exists to be trustworthy
    # about whether a selector resolves, and a second implementation of the
    # selector language makes the guard's own correctness the new risk. Nothing
    # about WHAT is checked changes here — only when the processes run, and how
    # many times an identical selector is run at all.
    from concurrent.futures import ThreadPoolExecutor

    import selector_evidence

    def collects(selector):
        files, keyword = selector
        # THROUGH `selector_evidence`, so this guard answers in the vocabulary
        # the release now requires of any targeted run used as evidence: a
        # selector that names nothing is NOT_EVIDENCE, whatever the command's
        # exit status was. Reading `::` out of stdout was the same check written
        # by hand, and a hand-written version of a rule is how the rule comes to
        # have two meanings.
        run = selector_evidence.run_selector(
            [str(ROOT / f) for f in files] + (["-k", keyword] if keyword else []),
            cwd=ROOT, timeout=300, collect_only=True)
        return not selector_evidence.problems(run, expect_at_least=1)

    # Sorted on a total order: `keyword` is None for a file-only selector and
    # None does not compare with str, so the key states the absence explicitly.
    distinct = sorted(
        {(tuple(files), keyword) for _mechanism, files, keyword in selectors},
        key=lambda pair: (pair[0], pair[1] or ""))
    with ThreadPoolExecutor(max_workers=4) as pool:
        resolved = dict(zip(distinct, pool.map(collects, distinct)))

    empty = [
        (mechanism, files, keyword)
        for mechanism, files, keyword in selectors
        if not resolved[(tuple(files), keyword)]
    ]
    assert not empty, f"these oracles select no test at all: {empty}"


#: Every Git attribute that can make a checkout's bytes differ from the stored
#: blob's. `text` and `eol` do end-of-line conversion; `filter` runs a smudge
#: program over the content; `ident` substitutes `$Id$`; `working-tree-encoding`
#: transcodes it. Checking `text` alone was not enough, and that is measured:
#: a smudge filter took a file from 14 bytes to 17 while `git check-attr text`
#: still said `unset` and this oracle passed. Found by an independent reader.
_REWRITING_ATTRIBUTES = ("text", "eol", "filter", "ident", "working-tree-encoding")


def test_no_tracked_path_is_rewritten_between_the_blob_and_the_checkout():
    """A digest over working-tree bytes is broken by anything that rewrites them.

    REPRODUCED, not hypothetical. `core.autocrlf=true` is the default on Git for
    Windows; cloning this branch under it rewrote LF to CRLF in every tracked
    file and `pack_pin.py` reported PACK PIN NOT VERIFIED against a checkout of
    the correct revision — the exact failure an adopting project would hit first
    and have no reason to attribute to its own Git configuration.

    The oracle asks GIT, not the file. A test that read `.gitattributes` and
    looked for `* -text` would pass against a file Git ignores — wrong section,
    wrong precedence, a later overriding pattern — and would be checking that
    somebody typed a string rather than that the property holds.

    **What this establishes and what it does not.** It establishes that no
    tracked path in THIS repository carries an attribute that rewrites its bytes
    at checkout. It does not establish that no checkout anywhere can differ: a
    consumer can define a smudge filter in its own configuration and attach it
    through an attributes file of its own, and Git will run it. That is outside
    anything this repository can declare, and the release states it as a bound
    rather than claiming otherwise.
    """
    paths = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split("\0")
    paths = [p for p in paths if p]
    assert len(paths) > 100, f"only {len(paths)} tracked path(s); this oracle is inert"

    rewritten = []
    for attribute in _REWRITING_ATTRIBUTES:
        reported = subprocess.run(
            ["git", "check-attr", "--stdin", "-z", attribute],
            cwd=ROOT, input="\0".join(paths), capture_output=True, text=True, check=True,
        ).stdout
        fields = reported.split("\0")
        for index in range(0, len(fields) - 2, 3):
            path, named, value = fields[index], fields[index + 1], fields[index + 2]
            assert named == attribute, f"unexpected attribute {named!r} in check-attr output"
            if value != "unset" and value != "unspecified":
                rewritten.append(f"{path}: {attribute}={value}")
            elif attribute == "text" and value == "unspecified":
                rewritten.append(
                    f"{path}: text is unspecified, so core.autocrlf decides and a checkout "
                    f"on another machine may not digest to the same bytes")
    assert not rewritten, (
        "these tracked paths may be rewritten between the stored blob and the checkout, so "
        "the pin will not verify on a machine configured that way: " + "; ".join(rewritten[:10])
    )


#: The fact a summary must carry, in the forms a writer would naturally use.
#: An exact-phrase requirement refused "identifies a real machine account", which
#: is true and says the same thing, and a bounded reading was right to call that
#: an exact-wording restriction rather than a check.
_THE_OCCURRENCE = ("names a real machine account", "identifies a real machine account",
                   "carries a real machine account", "names a real account")

#: A record is discussing the adjudication's subject if it names the document or
#: the tier the document is about.
_THE_SUBJECT = ("publication adjudication", "tier that governs a project",
                "tier a governed project runs")

#: The records that summarise this conclusion, NAMED rather than counted. A
#: floor of three was met by a different three: a bounded reading rewrote the
#: inventory to drop the subject phrases and added a compliant mention to the
#: capability map, and the count was satisfied while the contradictory record
#: went unexamined.
_MUST_AGREE = ("PACK_MANIFEST.json", "-GATE.md", "-INVENTORY.md")


def _normalised(text: str) -> str:
    """Case, whitespace and hyphenation flattened, so a line break inside a claim
    is the same claim. The original denial survived an earlier version of this
    guard by being wrapped across two lines, and an equivalent spelling survived
    it by using a non-breaking hyphen."""
    for dash in ("-", "\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        text = text.replace(dash, " ")
    return " ".join(text.lower().split())


def test_every_release_record_that_summarises_the_adjudication_carries_its_occurrence():
    """A conclusion has one owner, and a summary that drops its exception is wrong.

    `docs/RP2.4-PUBLICATION-ADJUDICATION.md` originally claimed that no
    occurrence at the tiered tier names a person, a machine or an account. An
    independent reader falsified it against a historical blob; the document was
    corrected; and three release records went on repeating the original claim, so
    the release shipped a public-safety conclusion and its own contradiction at
    once.

    **WHAT THIS CATCHES: AN OMISSION. WHAT IT DOES NOT CATCH: A LIE.** Three
    bounded readings defeated three successive versions of this guard, and the
    last one settles the question rather than losing it: a record can carry the
    required words inside their own negation and satisfy any substring check.
    Deciding whether prose is truthful is not something a test does, and an
    arms race of denial phrases is one this file has already lost twice.

    So the claim is scoped to what a machine can establish: every record that
    summarises this conclusion mentions its exception. That is exactly the defect
    that occurred — a correction in one place and three stale summaries — and it
    is not a substitute for a reader, which is how the original was found and how
    a deliberate negation would be.
    """
    import json

    prefix = _release_doc_prefix()
    adjudication = ROOT / "docs" / f"{prefix}-PUBLICATION-ADJUDICATION.md"
    if not adjudication.is_file():
        pytest.skip("this release ships no publication adjudication")

    owner = _normalised(adjudication.read_text(encoding="utf-8"))
    # NOT A SKIP. Removing the fact from the owner disabled an earlier version of
    # this guard entirely, including its own coverage assertion — so a document
    # edit could switch the check off without remediating anything.
    assert any(form in owner for form in _THE_OCCURRENCE), (
        f"{adjudication.name} no longer records the occurrence this guard exists for. If the "
        f"history was genuinely remediated — which is a rewrite, HITL rows 2 and 4 — remove "
        f"this guard in the same change that remediates it, and say so in the gate record")

    surfaces = [ROOT / "PACK_MANIFEST.json"]
    surfaces += sorted((ROOT / "docs").glob(f"{prefix}-*.md"))
    named = {}
    silent = []
    for path in surfaces:
        if path == adjudication:
            continue
        raw = path.read_text(encoding="utf-8")
        if path.name == "PACK_MANIFEST.json":
            raw = " ".join(json.loads(raw).get("known_limitations") or [])
        text = _normalised(raw)
        for marker in _MUST_AGREE:
            if path.name == marker or path.name.endswith(marker):
                named[marker] = path.name
        discusses = any(subject in text for subject in _THE_SUBJECT)
        required = any(path.name == m or path.name.endswith(m) for m in _MUST_AGREE)
        if not (discusses or required):
            continue
        if not any(form in text for form in _THE_OCCURRENCE):
            silent.append(path.name)

    missing = [marker for marker in _MUST_AGREE if marker not in named]
    assert not missing, (
        f"these records are named as summarising the adjudication and do not exist: {missing}. "
        f"A guard whose subjects are absent passes having checked nothing")
    assert not silent, (
        "these release records summarise the publication adjudication and do not carry the "
        "occurrence it records, so they state a conclusion by dropping its only known "
        f"exception: {', '.join(silent)}")


# --- the release delta is the changelog, and it must account for the release ------


def _baseline_revision(manifest) -> str:
    """The revision this release states its delta from, read rather than typed."""
    import re

    declared = manifest.get("baseline_revision") or ""
    found = re.match(r"\b([0-9a-f]{40})\b", declared.strip())
    assert found, (
        "PACK_MANIFEST.json records no `baseline_revision` beginning with a full 40-character "
        "revision. The release delta is measured from it, and a delta with no baseline is a "
        "description rather than a delta")
    return found.group(1)


def test_the_baseline_this_release_measures_its_delta_from_is_a_real_ancestor(manifest):
    revision = _baseline_revision(manifest)
    resolved = subprocess.run(["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
                              cwd=ROOT, capture_output=True, text=True)
    assert resolved.returncode == 0, (
        f"the recorded baseline {revision[:12]} does not resolve in this repository")
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", revision, "HEAD"],
                              cwd=ROOT, capture_output=True, text=True)
    assert ancestor.returncode == 0, (
        f"the recorded baseline {revision[:12]} is not an ancestor of HEAD, so the range it "
        f"names is not this release's")
    assert revision != subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                      capture_output=True, text=True).stdout.strip(), (
        "the baseline is HEAD, so the delta is empty by construction")

    # AND IT MUST BE OUTSIDE THIS RELEASE. Ancestry and a count floor both use
    # the baseline, so neither can tell a previous release from a commit in the
    # middle of this one — an independent reader set it to a revision whose
    # VERSION was already 2.4.0, which hid 24 additions, and BOTH guards passed.
    # The release boundary is a fact in the repository: at the previous release,
    # `VERSION` said something else.
    at_baseline = subprocess.run(["git", "show", f"{revision}:VERSION"], cwd=ROOT,
                                 capture_output=True, text=True)
    assert at_baseline.returncode == 0, (
        f"the recorded baseline {revision[:12]} has no VERSION file, so whether it is a "
        f"previous release cannot be established")
    assert at_baseline.stdout.strip() != manifest["version"], (
        f"the recorded baseline {revision[:12]} already declares VERSION "
        f"{at_baseline.stdout.strip()}, which is this release's own. A delta measured from "
        f"inside the release hides everything before that point, and every other check here "
        f"is measured from the same place, so none of them can see it")


def test_this_versions_changelog_entry_names_what_this_release_added(manifest):
    """The canonical per-release delta, checked against the release itself.

    `CHANGELOG.md` has been this pack's release-delta record since 2.0.0 — one
    section per version, describing that version against the one before it. This
    does not add a second one. It asks whether the section accounts for what the
    range actually changed.

    **It exists because the 2.4.0 entry stopped being updated partway through.**
    By the end it named one of four new tools, none of eight new test modules,
    two of fourteen new tracked files and one of two new decisions, so *what
    changed from 2.3.0 to 2.4.0* could only be answered by reading the commit
    range — which is the work a changelog exists to make unnecessary.

    **What it cannot do**, and `tools/release_delta.py` says so in its own
    docstring: judge whether the entry describes a change well, or notice a
    change that added no file. A repair inside an existing module is invisible to
    it. It covers the half a diff can name, which is the half that went missing.
    """
    import release_delta

    baseline = _baseline_revision(manifest)
    report = release_delta.coverage(ROOT, version=manifest["version"], baseline=baseline)

    # AN INDEPENDENT FLOOR, computed here rather than taken from the tool. Two
    # mutants survived a first version of this guard: one made the tool report
    # every addition as named, the other made it find no additions at all. Both
    # passed, because the guard asked the tool whether the tool was satisfied.
    added = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=A", f"{baseline}..HEAD"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    assert len(report.named) + len(report.omitted) >= len(added), (
        f"the delta tool accounted for {len(report.named) + len(report.omitted)} additions "
        f"while this range added {len(added)} files; it is not looking at the whole range")
    # THE FLOOR IS ZERO, NOT FIVE. The guard is vacuous only when the range adds
    # NOTHING — then `report.complete` has no addition to check and would be
    # green for the reason a broken guard is green. One addition is enough for it
    # to establish something, and it establishes exactly as much about two as
    # about twenty.
    #
    # It was written as `> 5` against a release that added fourteen files, and
    # that number then made a bounded repair release — which legitimately adds a
    # design record and a gate record and nothing else — impossible to ship
    # without deleting the guard. A rule a legitimate case cannot satisfy is a
    # rule that gets routed around, and this pack's own scaling rule says so.
    # Rebound rather than removed: the property it protects is unchanged.
    assert added, (
        "this range added no files at all, so this guard can establish nothing about the "
        "entry; a release that genuinely adds nothing must say so in its entry")
    assert report.complete, (
        "this version's changelog entry does not account for what the release added:\n"
        + report.render())
