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
    assert count == manifest["tracked_files"]


def test_the_release_identity_fields_are_well_formed(manifest):
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["tree_digest_sha256"])
    assert manifest["digest_excludes"] == pack_pin.MANIFEST_NAME
    assert manifest["digest_algorithm"] == pack_pin.DIGEST_ALGORITHM
    assert isinstance(manifest["tracked_files"], int) and manifest["tracked_files"] > 0


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
    assert manifest["tracked_files"] == len(tracked) - 1


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
