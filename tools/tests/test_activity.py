"""Two histories, and the ways each could lie.

A history is easy to render and easy to get wrong: a pushed commit counted
twice, a remote nobody fetched painted as empty, a day that moves when somebody
opens the page in another timezone, an event invented because the present state
implies it must have happened. Each of those has a test here, and each fails
without the code that prevents it.
"""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import activity
import continuation


def _git(where, *args):
    subprocess.run(["git", "-C", str(where), *args], check=True, capture_output=True,
                   timeout=120)


@pytest.fixture
def repo(tmp_path):
    where = tmp_path / "work"
    where.mkdir()
    _git(where, "init", "--quiet", "--initial-branch", "main")
    _git(where, "config", "user.name", "Throwaway Tester")
    _git(where, "config", "user.email", "tester@example.invalid")
    _git(where, "config", "commit.gpgsign", "false")
    return where


def _commit(where, name, when=None):
    (where / name).write_text(name)
    _git(where, "add", "-A")
    if when:
        subprocess.run(["git", "-C", str(where), "commit", "-q", "-m", name],
                       check=True, capture_output=True, timeout=120,
                       env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(where),
                            "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when,
                            "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@e.invalid",
                            "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@e.invalid"})
    else:
        _git(where, "commit", "-qm", name)


def _origin(tmp_path, repo):
    bare = tmp_path / "origin.git"
    bare.mkdir()
    _git(bare, "init", "--bare", "--quiet")
    _git(repo, "remote", "add", "origin", str(bare))
    return bare


# --- what a repository can be ----------------------------------------------------------


def test_a_repository_with_nothing_in_it_is_zero_and_not_unreadable(repo):
    """An empty history is an answer. `rev-list` exits non-zero on one, and a
    caller that treats that as a failure reports *unreadable* about a repository
    it read perfectly well."""
    found = activity.repository_activity(repo)
    assert found.unreadable == "", found.unreadable
    assert found.days == [] and found.total_local == 0
    assert found.active_days == 0


def test_a_directory_that_is_not_a_repository_says_so(tmp_path):
    found = activity.repository_activity(tmp_path / "nowhere")
    assert found.unreadable
    assert found.remote_state == activity.Remote.UNREADABLE
    assert found.total_local == 0


def test_one_commit_is_one_commit(repo):
    _commit(repo, "a")
    found = activity.repository_activity(repo)
    assert found.total_local == 1 and len(found.days) == 1
    assert found.days[0].local == 1


def test_many_commits_on_one_day_are_one_day(repo):
    for name in "abcdef":
        _commit(repo, name)
    found = activity.repository_activity(repo)
    assert len(found.days) == 1
    assert found.days[0].local == 6 and found.total_local == 6


def test_a_commit_reachable_from_several_refs_is_counted_once(repo):
    """A branch, a tag and a merge all reach the same commit. It is one commit,
    and counting refs instead of commits turns branching into work."""
    _commit(repo, "a")
    _git(repo, "tag", "release")
    _git(repo, "branch", "second")
    _git(repo, "checkout", "--quiet", "-b", "third")
    _commit(repo, "b")
    _git(repo, "checkout", "--quiet", "main")
    _git(repo, "merge", "--quiet", "--no-ff", "third", "-m", "merge third")
    found = activity.repository_activity(repo)
    counted = subprocess.run(["git", "-C", str(repo), "rev-list", "--branches", "--tags",
                              "HEAD", "--count"], capture_output=True, text=True, timeout=120)
    assert found.total_local == int(counted.stdout.strip()), (
        "the walk and git disagree about how many commits there are")


# --- local, remote, and the relationship between them ------------------------------------


def test_a_repository_with_no_remote_says_so_rather_than_reporting_zero(repo):
    """*No remote configured* and *the remote has nothing* are different facts,
    and a bar at zero says the second."""
    _commit(repo, "a")
    found = activity.repository_activity(repo)
    assert found.remote_state == activity.Remote.NONE_CONFIGURED
    assert "declares no remote" in found.remote_note
    assert not found.remote_established


def test_a_remote_nobody_fetched_is_unknown_and_not_empty(tmp_path, repo):
    """**UNKNOWN is not zero.** A declared remote with no tracking ref has never
    been observed here, and this module does not fetch to find out — so every
    day is marked as a question rather than painted as an empty cell."""
    _commit(repo, "a")
    _origin(tmp_path, repo)
    found = activity.repository_activity(repo)
    assert found.remote_state == activity.Remote.NEVER_OBSERVED
    assert "does not fetch" in found.remote_note
    assert all(day.remote_unknown for day in found.days)
    assert found.total_remote == 0
    assert not found.remote_established, (
        "an unobserved remote must not be reported as an established zero")


def test_everything_pushed_is_represented_and_nothing_is_local_only(tmp_path, repo):
    for name in "abc":
        _commit(repo, name)
    _origin(tmp_path, repo)
    _git(repo, "push", "--quiet", "origin", "main")
    found = activity.repository_activity(repo)
    assert found.remote_state == activity.Remote.OBSERVED
    assert found.total_local == 3 and found.total_remote == 3
    assert found.total_local_only == 0


def test_local_total_contains_the_remote_and_is_never_their_sum(tmp_path, repo):
    """**The relationship, asserted.** Local total is remote-represented plus
    local-only. A page that added local and remote would show every push as two
    pieces of work."""
    for name in "abc":
        _commit(repo, name)
    _origin(tmp_path, repo)
    _git(repo, "push", "--quiet", "origin", "main")
    _commit(repo, "d")
    _commit(repo, "e")
    found = activity.repository_activity(repo)
    assert found.total_local == 5
    assert found.total_remote == 3
    assert found.total_local_only == 2
    assert found.total_remote + found.total_local_only == found.total_local
    for day in found.days:
        assert day.remote <= day.local, "a day claims more remote commits than it has commits"


def test_a_second_remote_does_not_double_count_a_shared_commit(tmp_path, repo):
    for name in "abc":
        _commit(repo, name)
    first = _origin(tmp_path, repo)
    second = tmp_path / "mirror.git"
    second.mkdir()
    _git(second, "init", "--bare", "--quiet")
    _git(repo, "remote", "add", "mirror", str(second))
    _git(repo, "push", "--quiet", "origin", "main")
    _git(repo, "push", "--quiet", "mirror", "main")
    found = activity.repository_activity(repo)
    assert found.total_remote == 3, "one commit on two remotes was counted twice"
    assert found.total_local == 3


def test_history_rewritten_under_the_remote_leaves_the_old_commits_unreachable(tmp_path, repo):
    """A rebase makes new commits; the old ones stop being reachable. The walk
    reads reachability, so it needs no special case — this asserts that."""
    for name in "abc":
        _commit(repo, name)
    _origin(tmp_path, repo)
    _git(repo, "push", "--quiet", "origin", "main")
    before = activity.repository_activity(repo).total_local
    _git(repo, "commit", "--quiet", "--amend", "-m", "amended")
    after = activity.repository_activity(repo)
    assert after.total_local == before, "an amend changed how many commits exist"
    assert after.total_local_only == 1, "the amended commit is not local-only"


# --- days, and the timezone they are counted in --------------------------------------


def test_a_day_is_a_utc_day_whatever_zone_the_commit_was_made_in(repo):
    """**Two commits eleven minutes apart, in two zones, on two sides of
    midnight UTC.** Bucketing in the committer's own offset would put them on
    the same local day; bucketing in the reader's would move them when the page
    is opened elsewhere. The view says UTC, and this is what that means."""
    _commit(repo, "late", when="2026-03-01T23:55:00+00:00")
    _commit(repo, "early", when="2026-03-02T00:06:00+00:00")
    _commit(repo, "shifted", when="2026-03-02T01:30:00+02:00")   # 23:30 UTC on the 1st
    found = activity.repository_activity(repo)
    days = {day.date: day.local for day in found.days}
    assert days == {"2026-03-01": 2, "2026-03-02": 1}, days
    assert activity.TIMEZONE == "UTC"


def test_a_commit_on_a_daylight_saving_boundary_lands_where_utc_puts_it(repo):
    """European clocks moved on 2026-03-29. UTC did not."""
    _commit(repo, "before", when="2026-03-29T01:30:00+01:00")    # 00:30 UTC
    _commit(repo, "after", when="2026-03-29T03:30:00+02:00")     # 01:30 UTC
    found = activity.repository_activity(repo)
    assert [day.date for day in found.days] == ["2026-03-29"]
    assert found.days[0].local == 2


def test_a_commit_with_an_unreadable_date_is_dropped_rather_than_dated_wrongly():
    assert activity._utc_day("not a time") == ""
    assert activity._utc_day("") == ""
    assert activity._utc_day("2026-03-01T12:00:00+00:00") == "2026-03-01"


# --- several projects ------------------------------------------------------------------


def test_one_repository_registered_twice_is_counted_once(tmp_path, repo):
    """A registry may name the same tree twice. A calendar that believed it
    would double a year of work."""
    for name in "abc":
        _commit(repo, name)
    twice = [activity.repository_activity(repo), activity.repository_activity(repo)]
    assert sum(day.local for day in activity.aggregate(twice)) == 3


def test_two_repositories_add_up_and_keep_their_days_apart(tmp_path, repo):
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "--quiet", "--initial-branch", "main")
    _git(other, "config", "user.name", "T")
    _git(other, "config", "user.email", "t@e.invalid")
    _git(other, "config", "commit.gpgsign", "false")
    _commit(repo, "a", when="2026-05-01T10:00:00+00:00")
    _commit(other, "b", when="2026-05-02T10:00:00+00:00")
    both = activity.aggregate([activity.repository_activity(repo),
                               activity.repository_activity(other)])
    assert {day.date: day.local for day in both} == {"2026-05-01": 1, "2026-05-02": 1}


def test_an_unknown_remote_in_one_repository_marks_only_its_own_days(tmp_path, repo):
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "--quiet", "--initial-branch", "main")
    _git(other, "config", "user.name", "T")
    _git(other, "config", "user.email", "t@e.invalid")
    _git(other, "config", "commit.gpgsign", "false")
    _commit(repo, "a", when="2026-05-01T10:00:00+00:00")
    _origin(tmp_path, repo)
    _commit(other, "b", when="2026-05-02T10:00:00+00:00")
    both = {day.date: day for day in activity.aggregate([
        activity.repository_activity(repo), activity.repository_activity(other)])}
    assert both["2026-05-01"].remote_unknown
    assert not both["2026-05-02"].remote_unknown


# --- what happened, and what did not ---------------------------------------------------


def _project(tmp_path, **fields):
    root = tmp_path / "project"
    root.mkdir(exist_ok=True)
    fields.setdefault("capability", "C1 — the first capability")
    fields.setdefault("updated_at", continuation.now())
    continuation.save(continuation.ContinuationRecord(**fields), root / "CONTINUATION.json")
    return root


def test_a_project_with_no_artifacts_produces_no_events(tmp_path):
    empty = tmp_path / "bare"
    empty.mkdir()
    assert activity.pack_events(empty) == []


def test_every_event_names_the_artifact_that_dates_it(tmp_path):
    """**The whole bound on this half.** An event with no attributable source is
    an event this module invented."""
    root = _project(tmp_path, waits=(continuation.Wait(
        job_id="survey", kind=continuation.WaitKind.HUMAN, expects="a decision",
        declared_at=continuation.now()),))
    events = activity.pack_events(root)
    assert events
    for event in events:
        assert event.source, f"{event.kind} has no source"
        assert event.kind in activity.EVIDENCED or event.kind == "unreadable", event.kind


def test_an_open_capability_produces_no_opened_event(tmp_path):
    """**Nothing is inferred from the present state.** The record plainly says a
    capability is open; nothing durable says when it opened, so no event claims
    to know."""
    root = _project(tmp_path, actionable=("do the work",))
    kinds = {event.kind for event in activity.pack_events(root)}
    assert kinds == {"reading written"}, kinds
    assert not any("open" in kind for kind in kinds)


def test_a_wait_past_its_deadline_produces_one_dated_event(tmp_path):
    root = _project(tmp_path, waits=(continuation.Wait(
        job_id="j", kind=continuation.WaitKind.PROCESS, pid=1, expects="a report",
        not_beyond_seconds=60, declared_at="2020-01-01T00:00:00+00:00"),))
    events = activity.pack_events(root)
    passed = [e for e in events if e.kind == "deadline passed"]
    assert len(passed) == 1
    assert passed[0].when.startswith("2020-01-01T00:01")
    assert passed[0].tone == "bad"


def test_a_wait_still_inside_its_deadline_produces_no_expiry(tmp_path):
    root = _project(tmp_path, waits=(continuation.Wait(
        job_id="j", kind=continuation.WaitKind.PROCESS, pid=1, expects="a report",
        not_beyond_seconds=86400, declared_at=continuation.now()),))
    assert not [e for e in activity.pack_events(root) if e.kind == "deadline passed"]


def test_output_artifacts_are_dated_by_the_file_that_holds_them(tmp_path):
    import task_output

    root = _project(tmp_path)
    out = root / "worker-output"
    contract = task_output.OutputContract("survey", out, max_bytes_per_write=64,
                                          expected_chunks=2)
    task_output.claim_root(contract)
    task_output.materialise(contract, 0, "a finding")
    _project(tmp_path, waits=(continuation.Wait(
        job_id="survey", kind=continuation.WaitKind.OUTPUT_ROOT, path=str(out),
        task_id="survey", max_bytes_per_write=64, expects="two chunks",
        not_beyond_seconds=3600, declared_at=continuation.now()),))
    events = activity.pack_events(root)
    written = [e for e in events if e.kind in ("output written", "output completed")]
    assert written, [e.kind for e in events]
    for event in written:
        assert "modification time" in event.source


def test_a_malformed_observation_row_is_reported_and_not_dropped(tmp_path):
    root = _project(tmp_path)
    log = root / "observations.jsonl"
    log.write_text('{"recorded_at": "2026-05-01", "subject": "a real row"}\n'
                   "{ this is not json\n"
                   '{"subject": "a row with no time"}\n', encoding="utf-8")
    events = activity.pack_events(root)
    unreadable = [e for e in events if e.kind == "unreadable"]
    assert len(unreadable) == 2, [e.detail for e in unreadable]
    assert any("not JSON" in e.detail for e in unreadable)
    assert any("states no time" in e.detail for e in unreadable)
    assert any(e.kind == "observation recorded" for e in events)


def test_an_unreadable_record_is_an_event_and_not_a_silence(tmp_path):
    root = tmp_path / "broken"
    root.mkdir()
    (root / "CONTINUATION.json").write_text("{ not json")
    events = activity.pack_events(root)
    assert len(events) == 1 and events[0].kind == "unreadable"
    assert events[0].tone == "unknown"


def test_one_projects_events_never_appear_under_another(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    for root, job in ((first, "alpha"), (second, "beta")):
        root.mkdir()
        continuation.save(continuation.ContinuationRecord(
            capability="C1", updated_at=continuation.now(),
            waits=(continuation.Wait(job_id=job, kind=continuation.WaitKind.HUMAN,
                                     expects="a decision", declared_at=continuation.now()),)),
            root / "CONTINUATION.json")
    for root, job, other in ((first, "alpha", "beta"), (second, "beta", "alpha")):
        events = activity.pack_events(root, name=root.name)
        assert {e.project for e in events} == {root.name}
        assert any(e.subject == job for e in events)
        assert not any(e.subject == other for e in events)


def test_events_come_back_in_the_order_they_happened(tmp_path):
    root = _project(tmp_path, waits=(
        continuation.Wait(job_id="early", kind=continuation.WaitKind.HUMAN, expects="x",
                          declared_at="2026-01-01T00:00:00+00:00"),
        continuation.Wait(job_id="late", kind=continuation.WaitKind.HUMAN, expects="y",
                          declared_at="2026-06-01T00:00:00+00:00")))
    events = [e for e in activity.pack_events(root) if e.kind == "wait declared"]
    assert [e.subject for e in events] == ["early", "late"]


def test_an_event_with_no_time_sorts_last_and_keeps_its_reason(tmp_path):
    root = _project(tmp_path)
    (root / "observations.jsonl").write_text('{"subject": "no time here"}\n', encoding="utf-8")
    events = activity.pack_events(root)
    assert events[-1].kind == "unreadable"
    assert events[-1].when == ""
    assert events[-1].day == ""


def test_a_reading_is_bounded_to_its_window_and_says_so(repo):
    """**A smaller correct query, not a complete traversal on every render.**

    A calendar shows a year, so walking every commit a repository ever had to
    draw one is work nobody asked for. The bound is real — a commit outside the
    window is not counted — and the page states the window beside the totals.
    """
    _commit(repo, "ancient", when="2019-01-01T12:00:00+00:00")
    _commit(repo, "recent")
    year = activity.repository_activity(repo, window_days=366)
    assert year.total_local == 1, "a commit from years ago is inside a one-year window"
    assert year.window_days == 366
    everything = activity.repository_activity(repo, window_days=0)
    assert everything.total_local == 2, "the unbounded reading lost a commit"
    assert everything.window_days == 0


def test_the_window_does_not_change_what_a_day_holds(repo):
    """Bounding the walk may drop old days. It may not change a day it keeps."""
    _commit(repo, "old", when="2019-06-01T12:00:00+00:00")
    _commit(repo, "a")
    _commit(repo, "b")
    bounded = {d.date: d.local for d in activity.repository_activity(repo).days}
    whole = {d.date: d.local for d in activity.repository_activity(repo, window_days=0).days}
    for day, count in bounded.items():
        assert whole[day] == count, f"{day} holds {count} bounded and {whole[day]} unbounded"
