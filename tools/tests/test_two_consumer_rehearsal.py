"""Two adopting projects at once, each on the contracts it will actually use.

The single-project rehearsal in `test_adoption_rehearsal.py` answers *does the
lifecycle converge*. This answers a different question, and it is the one that
decides whether the next work is a project rather than this pack:

    **would two real projects start tomorrow without debugging the harness?**

So the two roots here differ in the ways two real projects differ — one declares
an executable adapter and one declares none, one runs background work and one
does not, one is a Git repository with local activity and one is not, one pins a
frozen release and one pins a candidate — and they run INTERLEAVED, because a
harness that is correct for one project at a time is not the harness either of
them gets.

Nothing here dispatches a worker to a provider. The workers are real processes
doing real work with real durable output; what they compute is arithmetic. The
provider-facing half is proved once, live, outside the suite, and recorded in
`docs/RP2.4-GATE.md` — a suite that needs a subscription to pass is a suite that
stops being run.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import adapter_pin
import capability_open
import continuation
import model_discovery
import pack_pin
import progress
import projection
import qualification as q
import routing as r
import task_output
from continuation import ContinuationRecord, State, Wait, WaitKind

PACK = Path(__file__).resolve().parent.parent.parent


# =============================================================================
# two consumer roots that differ in the ways two real projects differ
# =============================================================================


def _frozen_pack(tmp_path):
    """The rehearsal's pinned pack, built by the helper that already builds one.

    Written as a delegation rather than a second implementation: a fixture that
    constructs a release root by hand gets the manifest keys subtly wrong, which
    is exactly what the first draft of this module did — four `verify_pin`
    problems on a root it had just built.
    """
    from test_adoption_rehearsal import _frozen_release

    return _frozen_release(tmp_path)


def _consumer(tmp_path, *, name, pack, sha, digest, adapters, git, discovery_slugs,
              observations=()):
    root = tmp_path / name
    root.mkdir()
    lines = [
        "project:", f"  name: {name}", '  repo_path: "."',
        "pack:", f'  root_path: "{pack}"', '  version_adopted: "9.9.9"',
        f'  sha_adopted: "{sha}"', f'  tree_digest_sha256: "{digest}"',
        '  state_adopted: "QUALIFIED_AND_FROZEN"',
        "requires:", "  routing: true",
        "routing:", "  observations: observations.jsonl", "  discovery: discovery.json",
        '  dispatching_client: "1.0.0"',
    ]
    if adapters:
        lines.append("adapters:")
        for adapter in adapters:
            lines.append(f"  - id: {adapter['id']}")
            lines.append(f"    locator: {adapter['locator']}")
            lines.append(f"    digest: {adapter['digest']}")
            lines.append(f"    required: {'true' if adapter['required'] else 'false'}")
            for optional in ("executable", "version_command", "qualified_version"):
                if adapter.get(optional):
                    lines.append(f"    {optional}: {adapter[optional]}")
    else:
        lines.append("adapters: []")
    lines += ["capabilities:", "  - id: C1"]
    (root / "PROJECT.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "observations.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in observations), encoding="utf-8")
    (root / "discovery.json").write_text(json.dumps(
        {"client_version": "1.0.0",
         "models": [{"slug": slug} for slug in discovery_slugs]}), encoding="utf-8")
    if git:
        subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
        (root / "README.md").write_text(f"# {name}\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=a",
                        "commit", "-q", "-m", "first"], cwd=root, check=True)
    return root


@pytest.fixture
def two_projects(tmp_path):
    """One with an executable adapter and a Git repository, one with neither."""
    pack, sha, digest = _frozen_pack(tmp_path)

    # PROJECT A declares an executable adapter, which is the surface no real
    # project on this machine declares — so it is exercised here or nowhere.
    skill = tmp_path / "installed-adapter" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("name: bounded-worker\n\nA worker definition.\n", encoding="utf-8")
    a = _consumer(
        tmp_path, name="consumer-a", pack=pack, sha=sha, digest=digest, git=True,
        discovery_slugs=["model-new", "model-old"],
        adapters=[{"id": "bounded-worker", "locator": str(skill),
                   "digest": hashlib.sha256(skill.read_bytes()).hexdigest(),
                   "required": True,
                   "executable": sys.executable, "version_command": f"{sys.executable} -V",
                   "qualified_version": f"{sys.version_info.major}.{sys.version_info.minor}"}])
    b = _consumer(
        tmp_path, name="consumer-b", pack=pack, sha=sha, digest=digest, git=False,
        discovery_slugs=["model-new"], adapters=[])
    return {"pack": pack, "sha": sha, "digest": digest, "a": a, "b": b, "skill": skill}


# =============================================================================
# the rehearsal
# =============================================================================


def test_both_projects_open_a_capability_against_one_pinned_pack(two_projects):
    """Neither project's readiness is affected by the other's."""
    for key in ("a", "b"):
        report = capability_open.open_capability(
            two_projects[key] / "PROJECT.yaml", capability="C1")
        assert report.ready, f"consumer-{key} did not open:\n{report.render()}"
        routing_component = report.component("routing")
        assert routing_component is not None
        assert routing_component.state == capability_open.VERIFIED


def test_the_project_that_declares_an_executable_adapter_verifies_the_program(two_projects):
    """CLOSES THE GAP THAT NO REAL CONSUMER EXERCISES. Every contract on this
    machine declares files only, so every real report reads `0 executable(s)` and
    the executable half of the mechanism ships unexercised by an adopter."""
    import project_contract

    def _report(path):
        return adapter_pin.verify_contract(project_contract.ProjectContract.load(path))

    contract_path = two_projects["a"] / "PROJECT.yaml"
    report = _report(contract_path)
    rendered = report.render()
    assert "0 executable(s)" not in rendered, (
        "the adapter report still counts no executables in a project that declares one:\n"
        + rendered)
    assert report.clean, rendered
    assert report.executables_verified == ["bounded-worker"], (
        f"the declared executable was not among those verified:\n{rendered}")

    # AND IT ACTUALLY ASKS THE PROGRAM. A version the program does not report is
    # a refusal, not a warning — otherwise the declaration is decorative.
    original = contract_path.read_text(encoding="utf-8")
    contract_path.write_text(
        original.replace(
            f"qualified_version: {sys.version_info.major}.{sys.version_info.minor}",
            "qualified_version: 0.0.0-never-shipped"), encoding="utf-8")
    drifted = _report(contract_path)
    assert not drifted.clean, (
        "an executable whose version does not match the qualified one verified:\n"
        + drifted.render())
    contract_path.write_text(original, encoding="utf-8")
    assert _report(contract_path).clean, "the fixture did not restore"


def test_a_capability_does_not_open_when_the_adapter_it_dispatches_through_moved(two_projects):
    """A required adapter that changed is a STOP: it has already run by the time
    anybody reads a warning."""
    two_projects["skill"].write_text("name: bounded-worker\n\nEdited after qualification.\n",
                                     encoding="utf-8")
    report = capability_open.open_capability(
        two_projects["a"] / "PROJECT.yaml", capability="C1")
    assert not report.ready, (
        "the capability opened over an adapter that no longer matches what was qualified:\n"
        + report.render())
    # AND THE OTHER PROJECT IS UNAFFECTED. One project's broken declaration must
    # not stop another's work; they share only the pack.
    other = capability_open.open_capability(two_projects["b"] / "PROJECT.yaml", capability="C1")
    assert other.ready, other.render()


def test_the_two_projects_do_not_read_each_others_evidence(two_projects):
    """Each project's routing evidence is its own file, and a grade in one is
    not a grade in the other. Obvious, and the reason it is asserted is that
    both roots pin ONE pack — so a module that resolved the log relative to the
    pack rather than the project would pass every single-project rehearsal."""
    identity = q.ConfigurationIdentity(
        surface="surface-a", family="family-a", client="client-a",
        model_observed="model-new", effort="high", isolation="read-only", network="none",
        authentication_class="subscription", identity_method="execution_surface_turn_record",
        build="1.0.0")
    row = {"recorded_at": "2026-09-05", "task_class": "review", "outcome": "validated",
           "qualification_basis": "field",
           "configuration": ("surface=surface-a family=family-a agent=client-a "
                             "model=model-new model_observed=model-new "
                             "identity_method=execution_surface_turn_record auth=subscription "
                             "effort_observed=high isolation=read-only network=none build=1.0.0")}
    with (two_projects["a"] / "observations.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
        handle.write(json.dumps(row) + "\n")

    graded_a = q.qualifications_from_observations(two_projects["a"] / "observations.jsonl")
    graded_b = q.qualifications_from_observations(two_projects["b"] / "observations.jsonl")
    assert q.grade_for(identity, "review", graded_a, {})[0].grade == "confirmed"
    assert q.grade_for(identity, "review", graded_b, {})[0].grade == "unprobed", (
        "a configuration qualified in one project answered qualified in another"
    )


def test_both_projects_run_background_work_at_once_and_neither_blocks_the_other(two_projects):
    """Real processes, real output, and the pack's OWN waiter for both.

    The failure this exists to catch is not arithmetic: it is one project's
    reconciliation reading the other's process, which is what a liveness model
    keyed on anything but the recorded pid would do.
    """
    from dataclasses import replace as _replace

    from continuation import Disposition

    workers = {}
    for key in ("a", "b"):
        root = two_projects[key]
        out = root / "work"
        out.mkdir()
        script = root / "worker.py"
        script.write_text(
            "import json, sys\n"
            "root = sys.argv[1]\n"
            "total = sum(range(200000))\n"
            "open(root + '/result.json','w').write("
            f"json.dumps({{'project': {key!r}, 'total': total}}))\n",
            encoding="utf-8")
        workers[key] = (subprocess.Popen([sys.executable, str(script), str(out)]), out)

    paths = {}
    for key, (process, out) in workers.items():
        result = out / "result.json"
        wait = Wait(job_id=f"work-{key}", kind=WaitKind.PATH_EXISTS,
                    expects="the computed result", path=str(result),
                    not_beyond_seconds=600, declared_at=continuation.now(),
                    waiter=" ".join(progress.waiter_command(
                        f"work-{key}", process.pid, sentinel=str(result))))
        assert progress.is_governed_waiter(wait.waiter), wait.waiter
        paths[key] = two_projects[key] / "CONTINUATION.json"
        continuation.save(ContinuationRecord(
            capability=f"C1-{key}", updated_at=continuation.now(), waits=(wait,)), paths[key])

    for _key, (process, _out) in workers.items():
        process.wait(timeout=120)

    for key, (_process, out) in workers.items():
        assert json.loads((out / "result.json").read_text())["project"] == key, (
            "a project consumed another project's output")
        record = continuation.load(paths[key])
        assert continuation.ungoverned_waits(record) == (), (
            f"consumer-{key} declared a wait with no governed waiter")
        reconciled = continuation.reconcile(record, relative_to=two_projects[key])
        assert [item.disposition for item in reconciled] == [Disposition.COMPLETED_UNCONSUMED], (
            f"consumer-{key}: {[(i.disposition, i.why) for i in reconciled]}")

    # ONE PROJECT TAKING UP ITS RESULT DOES NOT SETTLE THE OTHER'S.
    record = continuation.load(paths["a"])
    continuation.save(ContinuationRecord(
        capability="C1-a", updated_at=continuation.now(),
        waits=(_replace(record.waits[0], consumed=True),)), paths["a"])
    settled = continuation.reconcile(continuation.load(paths["a"]),
                                     relative_to=two_projects["a"])
    still = continuation.reconcile(continuation.load(paths["b"]),
                                   relative_to=two_projects["b"])
    assert not settled[0].blocks, "consumer-a held its capability open after consuming"
    assert still[0].blocks, (
        "consumer-b's outstanding result settled because consumer-a consumed its own")


def test_a_cold_restart_reconstructs_both_projects_and_invents_no_work(two_projects):
    """A pid that no longer exists must not reconstruct as live work.

    Read back by a FRESH INTERPRETER holding nothing but the file, because the
    property is that the position survives the process that recorded it.
    """
    written = {}
    for key, pid in (("a", 999_001), ("b", 999_002)):
        missing = two_projects[key] / "never-written.md"
        wait = Wait(job_id=f"gone-{key}", kind=WaitKind.PATH_EXISTS,
                    expects="a result nothing produced", path=str(missing),
                    not_beyond_seconds=600, declared_at=continuation.now(), pid=pid,
                    waiter=" ".join(progress.waiter_command(
                        f"gone-{key}", pid, sentinel=str(missing))))
        written[key] = two_projects[key] / "COLD.json"
        continuation.save(ContinuationRecord(
            capability=f"C1-{key}", updated_at=continuation.now(), waits=(wait,)), written[key])

    for key, path in written.items():
        cold = subprocess.run(
            [sys.executable, "-c",
             "import sys, json; sys.path.insert(0, sys.argv[1]); import continuation;"
             "r = continuation.load(sys.argv[2]);"
             "print(json.dumps([(x.job_id, x.disposition, x.blocks)"
             " for x in continuation.reconcile(r, relative_to=sys.argv[3])]))",
             str(PACK / "tools"), str(path), str(two_projects[key])],
            capture_output=True, text=True, check=True, timeout=120)
        (job, disposition, _blocks), = json.loads(cold.stdout)
        assert job == f"gone-{key}"
        assert disposition != continuation.Disposition.LIVE_AND_PROGRESSING, (
            f"consumer-{key} reconstructed a pid that does not exist as live work: {disposition}")


def test_one_console_reading_shows_both_projects_and_confuses_neither(two_projects):
    """The multiproject surface, over two roots that differ in every declared way."""
    import console

    sites = console.survey([two_projects["a"], two_projects["b"]])
    assert len(sites) == 2, f"the survey returned {len(sites)} site(s) for two roots"
    names = {getattr(site, "name", None) for site in sites}
    assert names == {"consumer-a", "consumer-b"}, names
    # AND EACH SITE'S FACTS ARE ITS OWN. A survey that resolved anything relative
    # to the first root would give both sites the same answer here.
    roots = {site.name: str(getattr(site, "root", "")) for site in sites}
    assert roots["consumer-a"] != roots["consumer-b"]


def test_the_pin_verifies_from_both_projects_and_a_moved_pack_stops_both(two_projects):
    """The last thing either project does before dispatching anything."""
    for key in ("a", "b"):
        problems = pack_pin.verify_pin(
            two_projects["pack"], expect_version="9.9.9", expect_sha=two_projects["sha"],
            expect_digest=two_projects["digest"], expect_state="QUALIFIED_AND_FROZEN")
        assert problems == [], f"consumer-{key} could not verify the pack it pins: {problems}"

    (two_projects["pack"] / "tools" / "placeholder.py").write_text("# edited\n", encoding="utf-8")
    for key in ("a", "b"):
        problems = pack_pin.verify_pin(
            two_projects["pack"], expect_version="9.9.9", expect_sha=two_projects["sha"],
            expect_digest=two_projects["digest"], expect_state="QUALIFIED_AND_FROZEN")
        assert problems, (
            f"consumer-{key} verified a pack whose tree had been edited underneath it"
        )


def test_a_project_pinned_to_a_linked_worktree_is_told_so_at_adoption(two_projects, tmp_path):
    """THE 2.3.0 LAYOUT INCIDENT, as the thing a consumer actually reads.

    A linked worktree sitting on its pinned revision verifies completely and
    correctly. It is still a root whose owner can move it, and the project that
    pinned it finds out on the morning its capability stops opening. The report
    says it at adoption instead.
    """
    import pack_pin

    pack = two_projects["pack"]
    linked = tmp_path / "pack-as-a-linked-worktree"
    result = subprocess.run(
        ["git", "-C", str(pack), "worktree", "add", "-q", "--detach",
         str(linked), two_projects["sha"]],
        capture_output=True, text=True, timeout=120)
    assert not result.returncode, result.stderr
    assert pack_pin.root_kind(linked)[0] == "linked-worktree", "the fixture is not the hazard"
    assert pack_pin.verify_pin(
        linked, expect_version="9.9.9", expect_sha=two_projects["sha"],
        expect_digest=two_projects["digest"], expect_state="QUALIFIED_AND_FROZEN") == [], (
        "the fixture must be a root that VERIFIES; a broken one proves nothing here")

    contract = two_projects["a"] / "PROJECT.yaml"
    contract.write_text(
        contract.read_text(encoding="utf-8").replace(f'root_path: "{pack}"',
                                                     f'root_path: "{linked}"'),
        encoding="utf-8")
    report = capability_open.open_capability(contract, capability="C1")
    pin = report.component("pack_pin")
    assert pin is not None and pin.state == capability_open.VERIFIED, report.render()
    assert any("LINKED GIT WORKTREE" in note for note in pin.notes), (
        "the pin verified and said nothing about sitting on a root somebody else can move:\n"
        + report.render())
    assert report.ready, (
        "the note blocked the capability. A linked worktree on its pinned revision is a "
        "correct checkout of the right tree, and refusing it would refuse a working adoption "
        "over a hazard that has not happened:\n" + report.render())
