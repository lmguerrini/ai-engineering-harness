"""Seven defects an independent reading found in what the pack DOES.

Three earlier readings of this release were scoped to deltas, so they read the
code the last repair touched and nothing else. Their findings moved from the
release into the repairs and then into the oracles, and that looked like
convergence. It was convergence of the deltas. The modules a consuming project
actually calls had not been read for behaviour since the first round, and when
one reading was pointed at them it returned seven — every one reproduced, none
of them a test-only finding.

They are grouped here rather than scattered because their origin is the point:
what a delta-scoped reading cannot see is everything the delta did not touch.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

import adapter_pin
import capability_open
import continuation
import gitread
import outgoing_scan
import progress
import projection
import project_contract
import qualification as q
import routing as r
from continuation import Blocker, ContinuationRecord, Wait, WaitKind

ROOT = Path(__file__).resolve().parents[2]


# --- 1. readiness verified an adapter from the caller's directory ----------------


def test_a_capability_does_not_open_over_another_directorys_adapter(tmp_path, monkeypatch):
    """`verify_contract` was taught to resolve a relative locator against the
    project; `capability_open` called `verify` directly and was not.

    So the readiness path — the one thing a project runs before its first
    dispatch — reported READY with adapters VERIFIED while `verify_contract` on
    the same contract refused, because the qualified bytes happened to be in the
    directory the tool was invoked from.
    """
    from test_adoption_rehearsal import _frozen_release

    pack, sha, digest = _frozen_release(tmp_path)
    project, decoy = tmp_path / "proj", tmp_path / "decoy"
    project.mkdir()
    decoy.mkdir()
    qualified = "name: w\n\nthe qualified bytes\n"
    (decoy / "worker.md").write_text(qualified, encoding="utf-8")
    (project / "worker.md").write_text("name: w\n\nNOT what was qualified\n", encoding="utf-8")
    (project / "PROJECT.yaml").write_text(
        'project:\n  name: p\n  repo_path: "."\n'
        f'pack:\n  root_path: "{pack}"\n  version_adopted: "9.9.9"\n'
        f'  sha_adopted: "{sha}"\n  tree_digest_sha256: "{digest}"\n'
        '  state_adopted: "QUALIFIED_AND_FROZEN"\n'
        "adapters:\n  - id: w\n    locator: worker.md\n"
        f"    digest: {hashlib.sha256(qualified.encode()).hexdigest()}\n    required: true\n"
        "capabilities:\n  - id: C1\n", encoding="utf-8")

    contract = project_contract.ProjectContract.load(project / "PROJECT.yaml")
    monkeypatch.chdir(decoy)
    assert not adapter_pin.verify_contract(contract).clean, (
        "the fixture is inert: the adapter verifier does not refuse this project's adapter")

    report = capability_open.open_capability(project / "PROJECT.yaml", capability="C1")
    component = report.component("adapters")
    assert component is not None and component.state != capability_open.VERIFIED, (
        "readiness reported the adapters VERIFIED over another directory's bytes:\n"
        + report.render())
    assert not report.ready, (
        "a capability opened over an adapter that is not the project's:\n" + report.render())


# --- 2. an exemption covered a path it was not written for ----------------------


def _repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args],
                                capture_output=True, text=True, timeout=120)
        assert not result.returncode, f"git {args}: {result.stderr}"
        return result

    git("init", "-q", "--initial-branch", "main")
    git("config", "user.name", "Ordinary Human")
    git("config", "user.email", "human@example.invalid")
    git("config", "commit.gpgsign", "false")
    return root, git


def _scanner():
    return outgoing_scan.Scanner(outgoing_scan.TermSet(terms=("zzprivatezz",)), strict=True)


def test_one_blob_at_two_paths_is_exempt_only_where_the_exemption_was_written(tmp_path):
    """`rev-list --objects` prints ONE path per blob, so the exemption was decided
    from whichever Git happened to name."""
    root, git = _repository(tmp_path)
    (root / "seed.txt").write_text("nothing\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    baseline = git("rev-parse", "HEAD").stdout.strip()
    for name in ("a-exempt.txt", "z-unexempt.txt"):
        (root / name).write_text("zzprivatezz\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "one blob, two paths")

    report = outgoing_scan.scan_outgoing(
        root, ref="HEAD", baseline=baseline, scanner=_scanner(),
        content_exempt_paths=("a-exempt.txt",))
    subjects = {leak.subject for leak in report.leaks}
    assert "z-unexempt.txt" in subjects, (
        f"the private content at a NON-exempt path was not reported; leaks: {subjects}")
    assert "a-exempt.txt" not in subjects, (
        "the exemption stopped applying where it was written")


def test_a_baselined_blob_arriving_at_a_new_path_is_scanned_there(tmp_path):
    """A blob already reachable from the baseline is not listed at all, so copying
    an exempt one to a non-exempt path examined zero blobs and reported clean."""
    root, git = _repository(tmp_path)
    (root / "a-exempt.txt").write_text("zzprivatezz\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    baseline = git("rev-parse", "HEAD").stdout.strip()
    (root / "z-unexempt.txt").write_text("zzprivatezz\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "copied, byte for byte")

    report = outgoing_scan.scan_outgoing(
        root, ref="HEAD", baseline=baseline, scanner=_scanner(),
        content_exempt_paths=("a-exempt.txt",))
    assert report.blobs_examined >= 1, "the scan examined no blobs at all"
    assert any(leak.subject == "z-unexempt.txt" for leak in report.leaks), (
        f"content that arrived at a non-exempt path was not scanned there; "
        f"leaks: {[leak.subject for leak in report.leaks]}")


def test_an_exemption_still_exempts_the_path_it_names(tmp_path):
    """The control. Without it the two tests above would pass against a scanner
    that had simply stopped exempting anything."""
    root, git = _repository(tmp_path)
    (root / "seed.txt").write_text("nothing\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    baseline = git("rev-parse", "HEAD").stdout.strip()
    (root / "a-exempt.txt").write_text("zzprivatezz\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "only the exempt path")

    report = outgoing_scan.scan_outgoing(
        root, ref="HEAD", baseline=baseline, scanner=_scanner(),
        content_exempt_paths=("a-exempt.txt",))
    assert not report.leaks, f"the exemption did not apply: {report.leaks}"
    assert "a-exempt.txt" in report.exempted


def test_the_tree_enumeration_reports_every_path_a_blob_is_reachable_at(tmp_path):
    """The mechanism under the two tests above, on its own."""
    root, git = _repository(tmp_path)
    (root / "one.txt").write_text("shared\n", encoding="utf-8")
    (root / "two.txt").write_text("shared\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    found = gitread.blobs_at_paths_in_outgoing_range(root, "HEAD", None)
    paths = {path for path, _sha in found}
    assert {"one.txt", "two.txt"} <= paths, paths
    shas = {sha for path, sha in found if path in {"one.txt", "two.txt"}}
    assert len(shas) == 1, "the fixture is inert: the two paths do not share a blob"


# --- 3. two answers to one liveness question, again ------------------------------


def _ended_producer():
    worker = subprocess.Popen([sys.executable, "-c", "pass"])
    worker.wait()
    return worker.pid


def test_an_ended_producer_with_no_result_does_not_read_as_waiting(tmp_path):
    """`reconcile` consulted the recorded pid here and `derive` did not, so one
    record produced two answers — and the state machine's was *keep waiting*,
    until the deadline. In the module whose repair was to have one answer."""
    sentinel = tmp_path / "result.md"
    pid = _ended_producer()
    wait = Wait(job_id="j", kind=WaitKind.PATH_EXISTS, expects="a result",
                path=str(sentinel), pid=pid, not_beyond_seconds=99999,
                declared_at=continuation.now(),
                waiter=" ".join(progress.waiter_command("j", pid, sentinel=str(sentinel))))
    record = ContinuationRecord(capability="C", updated_at=continuation.now(), waits=(wait,))

    state = continuation.derive(record, relative_to=tmp_path).state
    assert state != continuation.State.WAITING_ON_IDENTIFIED_JOB, (
        "a producer that has exited without producing reads as a job still running")
    assert state == continuation.State.RECOVERY_REQUIRED, state

    dispositions = [item.disposition for item in
                    continuation.reconcile(record, relative_to=tmp_path)]
    assert continuation.State.WAITING_ON_IDENTIFIED_JOB not in dispositions
    assert dispositions == [continuation.Disposition.UNKNOWN], dispositions


def test_a_live_producer_with_no_result_still_reads_as_waiting(tmp_path):
    """The control: the repair must not turn every unfinished job into recovery."""
    worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        sentinel = tmp_path / "result.md"
        wait = Wait(job_id="j", kind=WaitKind.PATH_EXISTS, expects="a result",
                    path=str(sentinel), pid=worker.pid, not_beyond_seconds=99999,
                    declared_at=continuation.now(),
                    waiter=" ".join(progress.waiter_command(
                        "j", worker.pid, sentinel=str(sentinel))))
        record = ContinuationRecord(capability="C", updated_at=continuation.now(), waits=(wait,))
        assert continuation.derive(record, relative_to=tmp_path).state == \
            continuation.State.WAITING_ON_IDENTIFIED_JOB
    finally:
        worker.kill()
        worker.wait(timeout=30)


# --- 4 and 5. the projection disagreeing with its own record ---------------------


def test_the_headline_resolves_artifacts_where_the_record_was_loaded_from(tmp_path,
                                                                          monkeypatch):
    """`record_path` is optional and defaults to empty, so the headline fell back
    to the PROCESS's directory: one page said WAITING while its own liveness
    panel, which resolves correctly, said the result was waiting to be read."""
    work, elsewhere = tmp_path / "proj", tmp_path / "elsewhere"
    work.mkdir()
    elsewhere.mkdir()
    pid = _ended_producer()
    wait = Wait(job_id="j", kind=WaitKind.PATH_EXISTS, expects="a result",
                path="result.md", pid=pid, not_beyond_seconds=99999,
                declared_at=continuation.now(),
                waiter=" ".join(progress.waiter_command("j", pid, sentinel="result.md")))
    # THE ARTIFACT IS WRITTEN AFTER THE WAIT IS DECLARED, WHICH IS BOTH THE REAL
    # ORDER AND THE ONLY DETERMINISTIC ONE -- the same rule the sibling test in
    # test_background_governance.py states. `declared_at` is truncated to whole
    # seconds while the artifact's mtime is fractional, so writing first compares
    # as "written before the wait was declared" whenever the two straddle a
    # second boundary, and this test failed intermittently under load. A blind
    # certification caught it; the rule had been applied to the sibling and
    # missed here.
    (work / "result.md").write_text("done\n", encoding="utf-8")
    path = work / "CONTINUATION.json"
    continuation.save(ContinuationRecord(capability="C", updated_at=continuation.now(),
                                         waits=(wait,)), path)

    monkeypatch.chdir(elsewhere)
    headline = projection._headline(continuation.load(path), path)
    # Matched on the STATE NAME, not on the word "waiting" — the correct sentence
    # for a finished job is "A RESULT IS WAITING TO BE READ", which contains it.
    assert not headline.startswith("WAITING"), (
        f"the headline reports a finished job as running when read from elsewhere: {headline}")
    assert "COMPLETED_NOT_CONSUMED" in headline, headline


def test_the_page_does_not_offer_work_an_unscoped_human_blocker_covers(tmp_path):
    """`Blocker.blocks` empty means everything, and `derive` returns
    BLOCKED_ON_HUMAN for it. The page read `b.blocks` alone, so an unscoped
    blocker contributed no names and the page offered the work anyway."""
    work = tmp_path / "proj"
    work.mkdir()
    record = ContinuationRecord(
        capability="C", updated_at=continuation.now(),
        actionable=("publish the release",),
        blockers=(Blocker(kind="human", detail="row 2 — the founder freezes",
                          hitl_row=2, blocks=()),))
    path = work / "CONTINUATION.json"
    continuation.save(record, path)
    assert continuation.derive(continuation.load(path), relative_to=work).state == \
        continuation.State.BLOCKED_ON_HUMAN, "the fixture is inert"

    panel, _ = projection._liveness_panel(path)
    offered = [row.text for row in panel.rows() if row.label == "NEXT AUTHORISED ACTION"]
    assert offered, "the panel names no next action at all, so this asserts nothing"
    assert "publish the release" not in " ".join(str(text) for text in offered), (
        f"the page offered work its own record says is blocked: {offered}")


def test_the_page_still_offers_work_a_scoped_blocker_does_not_cover(tmp_path):
    """The control: an unscoped blocker covers everything, a scoped one does not."""
    work = tmp_path / "proj"
    work.mkdir()
    record = ContinuationRecord(
        capability="C", updated_at=continuation.now(),
        actionable=("write the report", "publish the release"),
        blockers=(Blocker(kind="human", detail="row 2", hitl_row=2,
                          blocks=("publish the release",)),))
    path = work / "CONTINUATION.json"
    continuation.save(record, path)
    panel, _ = projection._liveness_panel(path)
    offered = " ".join(str(row.text) for row in panel.rows()
                       if row.label == "NEXT AUTHORISED ACTION")
    assert "write the report" in offered, (
        f"a scoped blocker suppressed work it does not name: {offered!r}")


# --- 6. a JSON null became an established dimension ------------------------------


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_an_absent_structured_value_leaves_its_dimension_unknown(empty):
    """`str(value)` turned a JSON null into the string `'None'`, which is not the
    UNKNOWN sentinel — so an observation with `authentication_class: null`
    produced a COMPLETE identity whose authentication class was `'None'`, and two
    of them graded `confirmed` for a configuration whose authentication was never
    established."""
    identity = q.identity_from_observation({"configuration": "", "identity": {
        "surface": "s", "family": "f", "client": "c", "model_observed": "m",
        "effort": "high", "isolation": "read-only", "network": "none",
        "authentication_class": empty, "identity_method": "rollout"}})
    assert identity.authentication_class == q.UNKNOWN, (
        f"an absent value became the established dimension "
        f"{identity.authentication_class!r}")
    assert not identity.complete


def test_a_null_dimension_cannot_reach_a_grade(tmp_path):
    row = {"configuration": "", "task_class": "review", "outcome": "validated",
           "qualification_basis": "field",
           "identity": {"surface": "s", "family": "f", "client": "c", "model_observed": "m",
                        "effort": "high", "isolation": "read-only", "network": "none",
                        "authentication_class": None, "identity_method": "rollout"}}
    log = tmp_path / "observations.jsonl"
    log.write_text("\n".join([json.dumps(row)] * 3) + "\n", encoding="utf-8")
    assert q.qualifications_from_observations(log) == {}, (
        "three validated rows whose authentication class was null produced a grade")


def test_a_supplied_value_is_still_used():
    """The control, so the repair is a refusal of absence and not of everything."""
    identity = q.identity_from_observation({"configuration": "", "identity": {
        "surface": "s", "family": "f", "client": "c", "model_observed": "m",
        "effort": "high", "isolation": "read-only", "network": "none",
        "authentication_class": "subscription", "identity_method": "rollout"}})
    assert identity.authentication_class == "subscription"
    assert identity.complete, identity.incompleteness()


# --- 7. availability ordered as text rather than as time ------------------------


def _identity():
    return q.ConfigurationIdentity(
        surface="s", family="f", client="c", model_observed="m", effort="high",
        isolation="read-only", network="none", authentication_class="subscription",
        identity_method="rollout", build="1.0")


def test_a_later_refusal_outranks_an_earlier_success_across_time_zones():
    """Sorted as text, a `+02:00` success came after a `Z` refusal that happened an
    hour LATER, so an older success answered for a dispatch since refused."""
    identity = _identity()
    observations = (
        r.AvailabilityObservation(identity=identity, state=r.UNAVAILABLE, build="1.0",
                                  observed_at="2026-09-05T09:00:00Z", detail="refused"),
        r.AvailabilityObservation(identity=identity, state=r.AVAILABLE, build="1.0",
                                  observed_at="2026-09-05T10:00:00+02:00",
                                  detail="an hour EARLIER in real time"),
    )
    state, why = r.availability_for(identity, frozenset(), observations, build="1.0")
    assert state == r.UNAVAILABLE, (
        f"a success at 08:00 UTC answered for a configuration refused at 09:00 UTC: {why}")


def test_plain_dates_still_order_and_the_later_one_wins():
    identity = _identity()
    observations = (
        r.AvailabilityObservation(identity=identity, state=r.UNAVAILABLE, build="1.0",
                                  observed_at="2026-09-05"),
        r.AvailabilityObservation(identity=identity, state=r.AVAILABLE, build="1.0",
                                  observed_at="2026-09-06"),
    )
    assert r.availability_for(identity, frozenset(), observations, build="1.0")[0] == r.AVAILABLE


def test_an_unreadable_timestamp_never_outranks_a_readable_one():
    """It sorts first rather than being refused: the log is primary evidence and is
    not rewritten to suit a reader."""
    identity = _identity()
    observations = (
        r.AvailabilityObservation(identity=identity, state=r.AVAILABLE, build="1.0",
                                  observed_at="whenever"),
        r.AvailabilityObservation(identity=identity, state=r.UNAVAILABLE, build="1.0",
                                  observed_at="2026-09-05T09:00:00Z"),
    )
    assert r.availability_for(identity, frozenset(), observations, build="1.0")[0] == r.UNAVAILABLE


def test_a_same_instant_refusal_still_wins_the_tie():
    """The tie-break the ordering repair must not disturb."""
    identity = _identity()
    observations = (
        r.AvailabilityObservation(identity=identity, state=r.AVAILABLE, build="1.0",
                                  observed_at="2026-09-05T09:00:00Z"),
        r.AvailabilityObservation(identity=identity, state=r.UNAVAILABLE, build="1.0",
                                  observed_at="2026-09-05T11:00:00+02:00"),
    )
    assert r.availability_for(identity, frozenset(), observations, build="1.0")[0] == r.UNAVAILABLE


# =============================================================================
# What a bounded reading of the FIRST repairs found: every one of these was a
# defect in a repair made hours earlier, and three were the identical mistake
# one module over.
# =============================================================================


def test_content_that_appears_and_is_deleted_inside_the_range_is_still_scanned(tmp_path):
    """Comparing the two endpoints misses what lived only in between.

    Private content committed at a non-exempt path and deleted in a later
    outgoing commit scanned CLEAN, while the intermediate commit — which would be
    sent — still carries it.
    """
    root, git = _repository(tmp_path)
    (root / "a-exempt.txt").write_text("zzprivatezz\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    baseline = git("rev-parse", "HEAD").stdout.strip()
    (root / "public.txt").write_text("zzprivatezz\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "it appears")
    (root / "public.txt").unlink()
    git("add", "-A")
    git("commit", "-q", "-m", "and it is deleted")

    report = outgoing_scan.scan_outgoing(
        root, ref="HEAD", baseline=baseline, scanner=_scanner(),
        content_exempt_paths=("a-exempt.txt",))
    assert any(leak.subject == "public.txt" for leak in report.leaks), (
        f"content that existed only inside the range was not scanned; "
        f"leaks: {[leak.subject for leak in report.leaks]}")


def test_an_ordinary_submodule_change_does_not_abort_the_scan(tmp_path):
    """A gitlink is mode 160000 and its sha names a commit in ANOTHER repository,
    so asking this one for its size refuses. The pre-repair scan completed this
    case; the first version of the repair did not."""
    (tmp_path / "dep-holder").mkdir()
    (tmp_path / "sup-holder").mkdir()
    dependency, dep_git = _repository(tmp_path / "dep-holder")
    (dependency / "lib.txt").write_text("ordinary\n", encoding="utf-8")
    dep_git("add", "-A")
    dep_git("commit", "-q", "-m", "the dependency")

    superproject, sup_git = _repository(tmp_path / "sup-holder")
    (superproject / "seed.txt").write_text("nothing\n", encoding="utf-8")
    sup_git("add", "-A")
    sup_git("commit", "-q", "-m", "seed")
    baseline = sup_git("rev-parse", "HEAD").stdout.strip()
    sup_git("-c", "protocol.file.allow=always", "submodule", "add", "-q",
            str(dependency), "vendor")
    sup_git("commit", "-q", "-m", "add a submodule")

    report = outgoing_scan.scan_outgoing(superproject, ref="HEAD", baseline=baseline,
                                         scanner=_scanner())
    assert report is not None, "the scan did not complete over a submodule addition"


def test_an_ended_producer_is_seen_through_an_output_root_wait_too(tmp_path):
    """The first repair covered the two path kinds and left this one, so the same
    disagreement between `derive` and `reconcile` stayed reachable.

    **THE ROOT MUST BE CLAIMED.** A first version of this oracle used a bare
    directory, which `task_output.classify` reports UNKNOWN for — no owner
    marker — so the observation short-circuited before the producer was ever
    consulted and the test passed against the unrepaired code. Vacuous for the
    property it names, which is the shape this suite has its own sweep for.
    """
    import task_output

    root = tmp_path / "out"
    contract = task_output.OutputContract(task_id="t", output_root=root,
                                          max_bytes_per_write=1024)
    task_output.claim_root(contract)
    # A CLAIMED ROOT WITH NOTHING DURABLE IN IT: the producer started, took the
    # root, and stopped. A loose file the contract does not describe classifies
    # UNKNOWN — which is a different, correct refusal — so the fixture leaves
    # the root as the claim made it.
    state_without_a_producer = task_output.classify(contract).state
    assert state_without_a_producer != task_output.RecoveryState.UNKNOWN, (
        f"the fixture is inert: the root classifies {state_without_a_producer}, so the "
        f"observation never reaches the producer check this test is about")
    assert state_without_a_producer != task_output.RecoveryState.COMPLETED_WITH_DURABLE_OUTPUT

    pid = _ended_producer()
    wait = Wait(job_id="j", kind=WaitKind.OUTPUT_ROOT, expects="the output",
                path=str(root), task_id="t", max_bytes_per_write=1024, pid=pid,
                not_beyond_seconds=99999, declared_at=continuation.now(),
                waiter=" ".join(progress.waiter_command("j", pid, sentinel=str(root))))
    record = ContinuationRecord(capability="C", updated_at=continuation.now(), waits=(wait,))
    report = continuation.derive(record, relative_to=tmp_path)
    assert report.state != continuation.State.WAITING_ON_IDENTIFIED_JOB, (
        f"an output root whose producer has ended still reads as a running job: "
        f"{[o.how for o in report.observations]}")
    assert any("has ended" in observation.how for observation in report.observations), (
        f"the observation does not say the producer ended, so this is reaching the right "
        f"state for the wrong reason: {[o.how for o in report.observations]}")


@pytest.mark.parametrize("pid,keeps_waiting", [
    ("live-int", True), ("live-string", True),
    ("ended-int", False), ("ended-string", False),
    (None, True), ("not-a-pid", True), (True, True),
])
def test_a_numeric_string_producer_is_read_the_way_a_process_wait_reads_one(pid, keeps_waiting):
    """`WaitKind.PROCESS` has always accepted a numeric string. Treating one as
    unaskable turned a LIVE producer into recovery for the artifact kinds and
    left it waiting for the process kind — the same record giving two answers,
    one type over."""
    alive = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
    try:
        ended = _ended_producer()
        actual = {"live-int": alive.pid, "live-string": str(alive.pid),
                  "ended-int": ended, "ended-string": str(ended)}.get(pid, pid)
        wait = Wait.__new__(Wait)
        object.__setattr__(wait, "pid", actual)
        object.__setattr__(wait, "job_id", "j")
        gone = continuation._producer_gone(wait, "the artifact has not appeared")
        assert (gone is None) is keeps_waiting, (
            f"pid {actual!r}: {'kept waiting' if gone is None else gone.how}")
    finally:
        alive.kill()
        alive.wait(timeout=30)


def test_naming_a_test_module_does_not_cover_the_module_it_tests():
    """Substring membership is not naming, and this pack has the shape in its own
    recurrence classes. `evolution_evidence.py` counted as named because it
    occurs inside `test_evolution_evidence.py`."""
    import release_delta

    assert not release_delta._names("see test_evolution_evidence.py",
                                    "evolution_evidence.py")
    assert release_delta._names("see `tools/evolution_evidence.py` here",
                                "evolution_evidence.py")
    assert not release_delta._names("recorded D90", "D9")
    assert release_delta._names("recorded D9 and D10", "D9")


def test_a_prerelease_entry_does_not_stand_in_for_the_release_entry():
    """`\\b` accepts a hyphen, so `## 9.9.9-rc.1` satisfied a request for 9.9.9."""
    import release_delta

    with pytest.raises(ValueError, match="no `## 9.9.9` entry"):
        release_delta.entry_for("# C\n\n## 9.9.9-rc.1 — pre\n\nbody\n", "9.9.9")
    assert release_delta.entry_for("# C\n\n## 9.9.9 — real\n\nbody\n", "9.9.9").strip() == "body"


@pytest.mark.parametrize("absent", [None, False, [], {}, (), "", "   ", "none", "NULL"])
def test_an_absent_distinction_is_absent_however_it_is_spelled(absent):
    """`str(None).strip()` is `"None"` — four characters of nothing that pass
    every emptiness test. The identical defect this release had fixed in
    `qualification` hours earlier, made again in a new module."""
    import evolution_evidence as ee

    classes = ee.load(ROOT / "policy" / "recurrence-classes.json")
    evidence = ee.Evidence(
        recurrence_class="superseded or orphaned or stale waiter",
        occurrence=ee.Occurrence(project="p", release="r", revision="v",
                                 reproduction="x"),
        distinct_because=absent)
    assert ee.classify(evidence, classes).outcome == ee.NEEDS_DISTINCTION, (
        f"distinct_because={absent!r} was accepted as a stated distinction")


@pytest.mark.parametrize("field", ["project", "release", "revision", "reproduction"])
def test_absent_provenance_is_refused_however_it_is_spelled(field):
    import evolution_evidence as ee

    classes = ee.load(ROOT / "policy" / "recurrence-classes.json")
    evidence = ee.Evidence(
        recurrence_class="false RUNNING from process existence",
        occurrence=ee.Occurrence(**{**dict(project="p", release="r", revision="v",
                                           reproduction="x"), field: None}))
    with pytest.raises(ValueError, match=field):
        ee.classify(evidence, classes)


def test_replaying_one_piece_of_evidence_does_not_invent_a_second_occurrence():
    """A class's strength is how many separate times it was hit. A retry, a
    re-import or a re-run must not add to it."""
    import evolution_evidence as ee

    classes = ee.load(ROOT / "policy" / "recurrence-classes.json")
    evidence = ee.Evidence(
        recurrence_class="false RUNNING from process existence",
        occurrence=ee.Occurrence(project="p", release="r", revision="v", reproduction="x"))
    once = ee.reinforce(classes, evidence)
    with pytest.raises(ValueError, match="already recorded"):
        ee.reinforce(once, evidence)
    assert len(ee.occurrences_of(once, "false RUNNING from process existence")) == 1


def test_a_distinction_against_the_class_you_submit_under_is_refused():
    """Returning RECURRENCE and discarding the explanation silently merged a
    submission that had said it was different."""
    import evolution_evidence as ee

    classes = ee.load(ROOT / "policy" / "recurrence-classes.json")
    evidence = ee.Evidence(
        recurrence_class="false RUNNING from process existence",
        occurrence=ee.Occurrence(project="p", release="r", revision="v", reproduction="x"),
        distinct_because="it is about an artifact's owner, not about liveness")
    with pytest.raises(ValueError, match="cannot both be true"):
        ee.classify(evidence, classes)
