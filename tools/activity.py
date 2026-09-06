"""Two histories, read from durable artifacts, and neither of them a score.

**Repository activity** — when code actually changed, and how much of it the
remote represents. Derived from the local object graph and from remote-tracking
refs, with no network read of any kind: this module never fetches, and a remote
nobody has fetched is reported as never observed rather than as empty.

**Runtime Pack events** — what happened during governed execution, rebuilt from
artifacts that carry their own timestamps. Every event names the artifact it
came from. **Nothing is inferred from the current state**: a capability that is
obviously open produces no *opened* event, because nothing durable says when.

Neither is evidence of quality. A commit count measures that commits happened.
The word *productivity* does not appear in this module and the release contains
no test that would let it.

## The relationship, stated once

    LOCAL TOTAL
    ├── REMOTE-REPRESENTED   reachable from a remote-tracking ref
    └── LOCAL-ONLY           reachable from a local ref and no remote one

Not `local + remote`. A pushed commit is one commit that two refs reach, and
counting it twice would make every push look like work.

## Time

Days are UTC, always, and the view says so. The alternative — the reader's
local zone — moves a commit between days depending on which machine renders the
page, and a history that changes shape when you open it somewhere else is not a
history.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["Day", "Event", "RepositoryActivity", "Remote", "repository_activity",
           "pack_events", "TIMEZONE"]

#: The zone every day in this module is bucketed in, named where it is shown.
TIMEZONE = "UTC"

UNKNOWN = "UNKNOWN"


class Remote:
    """What can be established about the remote, without touching the network."""

    #: The repository declares no remote. A known fact, and not the same as
    #: *the remote has nothing*.
    NONE_CONFIGURED = "NO REMOTE CONFIGURED"
    #: A remote is declared and no remote-tracking ref exists, so nothing about
    #: what it holds has ever been observed here.
    NEVER_OBSERVED = "REMOTE NEVER OBSERVED"
    #: Remote-tracking refs exist. They are as of the last fetch, whenever that
    #: was — which this module reports when the repository records it and
    #: declines to guess when it does not.
    OBSERVED = "REMOTE OBSERVED"
    #: The repository could not be read at all.
    UNREADABLE = "UNREADABLE"


@dataclass
class Day:
    """One UTC day. `local` includes `remote`; they are not added together."""

    date: str
    local: int = 0
    remote: int = 0
    #: True when the remote side of this day could not be established. Such a
    #: day is not zero remote activity; it is an unanswered question, and the
    #: view must not paint it as an empty cell.
    remote_unknown: bool = False
    #: THE SAME COMMITS, BY UTC HOUR. A git commit carries a full timestamp, so
    #: an hour is read and not invented; anything without one is not counted
    #: here at all rather than being placed at midnight. `sum(hours) == local`
    #: and `sum(remote_hours) == remote`, asserted, because two views of one
    #: reading that disagree are two readings.
    hours: list = field(default_factory=lambda: [0] * 24)
    remote_hours: list = field(default_factory=lambda: [0] * 24)

    @property
    def local_only(self) -> int:
        return max(0, self.local - self.remote)

    @property
    def local_only_hours(self) -> list:
        return [max(0, a - b) for a, b in zip(self.hours, self.remote_hours)]

    @property
    def busiest_hour(self) -> int:
        return max(range(24), key=lambda h: self.hours[h]) if self.local else -1


@dataclass
class RepositoryActivity:
    repository: str
    name: str = ""
    days: list = field(default_factory=list)
    #: How far back this reading went. Every total below is *within it*.
    window_days: int = 0
    remote_state: str = Remote.UNREADABLE
    remote_note: str = ""
    fetched_at: str = ""
    unreadable: str = ""
    #: The identity two registry entries pointing at one repository share.
    identity: str = ""

    @property
    def established(self) -> bool:
        """Whether these totals are readings at all.

        A repository that would not open has no local count — it has an
        unanswered question — and rendering `0` there says the opposite of what
        is known. Found by an independent reader.
        """
        return not self.unreadable

    @property
    def total_local(self) -> int:
        return sum(day.local for day in self.days)

    @property
    def total_remote(self) -> int:
        return sum(day.remote for day in self.days)

    @property
    def total_local_only(self) -> int:
        return sum(day.local_only for day in self.days)

    @property
    def active_days(self) -> int:
        return sum(1 for day in self.days if day.local)

    @property
    def remote_established(self) -> bool:
        return self.remote_state == Remote.OBSERVED

    @property
    def latest_local(self) -> str:
        return max((day.date for day in self.days if day.local), default="")

    @property
    def latest_remote(self) -> str:
        if not self.remote_established:
            return ""
        return max((day.date for day in self.days if day.remote), default="")


def _utc_moment(stamp: str):
    """`(date, hour)` in UTC for an ISO-8601 instant, or `("", -1)`.

    Bucketing in the committer's own offset would put two commits a minute apart
    on different days depending on where each was made; bucketing in the
    reader's zone would move them depending on where the page is opened.
    """
    try:
        moment = datetime.fromisoformat(stamp.strip())
    except (TypeError, ValueError):
        return "", -1
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    return moment.date().isoformat(), moment.hour


def _utc_day(stamp: str) -> str:
    """The UTC date of an ISO-8601 instant, or `''` when it cannot be read."""
    return _utc_moment(stamp)[0]


def _walk(repository, *selectors: str, timeout: float) -> dict:
    """`{sha: (utc date, utc hour)}` for every commit the selectors reach.

    Deduplicated by sha, so a commit reachable from a branch, a tag and three
    remote-tracking refs is one commit — which is what it is.
    """
    import gitread

    output = gitread._run(repository, "rev-list", *selectors,
                          "--pretty=format:%H %cI", "--no-commit-header", timeout=timeout)
    found: dict = {}
    for line in (output or "").splitlines():
        sha, _, stamp = line.strip().partition(" ")
        if len(sha) < 7 or not stamp:
            continue
        day, hour = _utc_moment(stamp)
        if day:
            found[sha] = (day, hour)
    return found


#: How far back a reading goes by default. The calendar shows a year, so
#: walking every commit a repository ever had to draw one is work nobody asked
#: for — and on a large repository it is the difference between a page that
#: opens and one that does not. The window is stated wherever the numbers are.
DEFAULT_WINDOW_DAYS = 366


def repository_activity(repository, *, name: str = "", timeout: float = 60.0,
                        window_days: int = DEFAULT_WINDOW_DAYS) -> RepositoryActivity:
    """When this repository changed, and how much of it the remote represents.

    Bounded to `window_days` back from now: a smaller correct query rather than
    a complete traversal on every render. `window_days=0` reads all of it.
    """
    import gitread

    where = Path(repository)
    try:
        where = where.resolve()
    except OSError:
        pass
    activity = RepositoryActivity(repository=str(where), name=name or where.name or str(where),
                                  window_days=window_days)
    since = ()
    if window_days > 0:
        from datetime import timedelta

        edge = (datetime.now(timezone.utc) - timedelta(days=window_days)).date().isoformat()
        since = (f"--since={edge}",)
    try:
        # THE COMMON DIRECTORY, not this worktree's own. A linked worktree has
        # its own `.git/worktrees/<name>` directory and shares the object graph,
        # so identifying by the per-worktree path made one repository look like
        # two and doubled its year. Found by an independent reader.
        # ASKED OF THE SUBJECT, NOT OF THE READ. Under the sterile boundary
        # `rev-parse --git-common-dir` answers about the directory the harness
        # built for this one invocation, so identifying a repository by it made
        # every read a different repository — three counted as six.
        activity.identity = gitread.repository_location(where)["common"]
    except Exception as exc:
        # WHICH of the two it is. `git invocation failed` was true and told a
        # reader nothing: a directory that is not a repository and a repository
        # that cannot be read are different situations with different answers.
        if not where.is_dir():
            activity.unreadable = f"there is no directory at {where}"
        elif not (where / ".git").exists() and not (where / "HEAD").is_file():
            activity.unreadable = (
                f"{where} is not a git repository, and this project declares no other one — "
                f"so there is no repository history to read, which is not the same as a "
                f"repository with no history")
        else:
            activity.unreadable = f"{type(exc).__name__}: {exc}"[:200]
        return activity

    try:
        local = _walk(where, "--branches", "--tags", "HEAD", *since, timeout=timeout)
    except Exception as exc:
        # An empty repository is not an unreadable one: `rev-list` exits
        # non-zero on a history with nothing in it, and that is an answer.
        try:
            count = gitread._run(where, "rev-list", "--all", "--count", timeout=timeout).strip()
        except Exception:
            count = ""
        if count == "0":
            local = {}
        else:
            activity.unreadable = f"{type(exc).__name__}: {exc}"[:200]
            return activity

    remotes = []
    try:
        for row in gitread.config_with_origin(where):
            key = str(row.get("key", ""))
            if key.startswith("remote.") and key.endswith(".url"):
                remotes.append(key.split(".")[1])
    except Exception:
        remotes = []

    remote: dict = {}
    if not remotes:
        activity.remote_state = Remote.NONE_CONFIGURED
        activity.remote_note = ("this repository declares no remote, so there is nothing for a "
                                "remote to represent")
    else:
        tracking = []
        try:
            # `refname`, which is what the reader calls it. Reading a key it
            # does not return made every ref invisible, so a repository whose
            # commits were all pushed reported its remote as never observed —
            # a wrong answer that looked like a cautious one.
            tracking = [r for r in gitread.refs(where)
                        if str(r.get("refname", "")).startswith("refs/remotes/")]
        except Exception:
            tracking = []
        if not tracking:
            activity.remote_state = Remote.NEVER_OBSERVED
            activity.remote_note = (
                f"{len(remotes)} remote(s) declared and no remote-tracking ref here, so what "
                f"they hold has never been observed on this machine. This module does not "
                f"fetch: an unfetched remote is an unanswered question, not an empty one")
        else:
            try:
                remote = _walk(where, "--remotes", *since, timeout=timeout)
                activity.remote_state = Remote.OBSERVED
            except Exception as exc:
                activity.remote_state = Remote.NEVER_OBSERVED
                activity.remote_note = f"the remote-tracking refs could not be read: {exc}"[:160]
            marker = where / ".git" / "FETCH_HEAD"
            if not marker.is_file():
                marker = Path(activity.identity or where) / "FETCH_HEAD"
            if marker.is_file():
                activity.fetched_at = datetime.fromtimestamp(
                    marker.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
                activity.remote_note = (
                    f"remote-tracking refs as of the last fetch recorded here, "
                    f"{activity.fetched_at}")
            else:
                activity.remote_note = (
                    "remote-tracking refs exist and nothing here records when they were last "
                    "updated, so how current they are cannot be established")

    counted: dict = {}
    for sha, (day, hour) in local.items():
        entry = counted.setdefault(day, Day(date=day))
        entry.local += 1
        if 0 <= hour < 24:
            entry.hours[hour] += 1
        if sha in remote:
            entry.remote += 1
            if 0 <= hour < 24:
                entry.remote_hours[hour] += 1
        if activity.remote_state in (Remote.NEVER_OBSERVED, Remote.UNREADABLE):
            entry.remote_unknown = True
    activity.days = [counted[day] for day in sorted(counted)]
    return activity


def aggregate(activities) -> list:
    """Several repositories over one calendar, each commit counted once.

    Two registry entries naming one repository resolve to one git directory and
    contribute once. Without that, a project listed twice doubles a year.
    """
    seen, days = set(), {}
    for activity in activities:
        if activity.identity and activity.identity in seen:
            continue
        if activity.identity:
            seen.add(activity.identity)
        for day in activity.days:
            entry = days.setdefault(day.date, Day(date=day.date))
            entry.local += day.local
            entry.remote += day.remote
            for hour in range(24):
                entry.hours[hour] += day.hours[hour]
                entry.remote_hours[hour] += day.remote_hours[hour]
            entry.remote_unknown = entry.remote_unknown or day.remote_unknown
    return [days[day] for day in sorted(days)]


# --- what happened during governed execution ------------------------------------------


@dataclass
class Event:
    """One thing that happened, and the artifact that says so."""

    when: str
    kind: str
    subject: str
    detail: str = ""
    project: str = ""
    capability: str = ""
    #: WHERE THIS CAME FROM, always. An event with no attributable artifact is
    #: an event this module refuses to produce.
    source: str = ""
    #: RECORDED or DERIVED. A recorded event has an artifact that states its
    #: time; a derived one is arithmetic over durable fields and the clock —
    #: true, determined, and not written down anywhere. Mixing the two in one
    #: timeline without saying which is which is the misleading part, and an
    #: independent reader said so.
    basis: str = "recorded"
    tone: str = "plain"
    #: Which registry entry this belongs to, filled in by the caller that knows.
    #: Two projects may share a display name; an index cannot be shared.
    at: str = ""

    @property
    def day(self) -> str:
        return _utc_day(self.when)


#: The event classes this release can actually evidence, and the artifact behind
#: each. Everything else a governed run does — a capability opening, an audit
#: being dispatched, a finding recorded — happens in documents that carry no
#: durable timestamp for it, and this module will not date them by guessing.
#: A durable event log is recorded as an Evolution Candidate instead.
#: The one event class that is DERIVED rather than recorded. It is arithmetic
#: over two durable fields and the clock: the deadline did pass, and no artifact
#: says so. The timeline marks it, and the filter can exclude it.
DERIVED = {"deadline passed"}

EVIDENCED = {
    "reading written": "the continuation record's own updated_at",
    "wait declared": "a wait's declared_at in the continuation record",
    "deadline passed": "a wait's declared_at plus its declared limit",
    "output written": "the modification time of a chunk the worker wrote",
    "output completed": "the modification time of the completion marker",
    "evidence recorded": "the modification time of a file in an evidence directory",
    "observation recorded": "a timestamped row in an append-only observations log",
}


def pack_events(project_root, *, name: str = "", limit: int = 4000) -> list:
    """Rebuild what durable artifacts can actually date.

    Read-only, and deliberately incomplete: an event appears because something
    on disk carries its time, never because the present state implies it must
    have happened.
    """
    root = Path(project_root)
    project = name or root.name
    events: list = []

    record = None
    try:
        import continuation

        record_path = root / "CONTINUATION.json"
        if record_path.is_file():
            record = continuation.load(record_path)
    except Exception as exc:
        events.append(Event(when="", kind="unreadable", subject="continuation record",
                            detail=f"{type(exc).__name__}: {exc}"[:160], project=project,
                            source=str(root / "CONTINUATION.json"), tone="unknown"))

    if record is not None:
        capability = str(record.capability)
        if record.updated_at:
            events.append(Event(when=str(record.updated_at), kind="reading written",
                                subject="the coordinator's position",
                                detail="the record was last rewritten", project=project,
                                capability=capability,
                                source="CONTINUATION.json updated_at"))
        for wait in record.waits:
            if wait.declared_at:
                events.append(Event(
                    when=str(wait.declared_at), kind="wait declared", subject=str(wait.job_id),
                    detail=str(wait.expects or ""), project=project, capability=capability,
                    source="CONTINUATION.json waits[].declared_at"))
                if wait.not_beyond_seconds:
                    try:
                        moment = datetime.fromisoformat(str(wait.declared_at))
                        if moment.tzinfo is None:
                            moment = moment.replace(tzinfo=timezone.utc)
                        from datetime import timedelta

                        due = moment + timedelta(seconds=float(wait.not_beyond_seconds))
                        if due <= datetime.now(timezone.utc):
                            events.append(Event(
                                when=due.isoformat(timespec="seconds"), kind="deadline passed",
                                subject=str(wait.job_id),
                                detail="the declared limit ran out", project=project,
                                capability=capability, tone="bad", basis="derived",
                                source="derived from declared_at plus not_beyond_seconds; "
                                       "nothing recorded it happening"))
                    except (TypeError, ValueError, OverflowError):
                        pass
            root_path = Path(str(wait.path)) if wait.path else None
            if root_path is not None and not root_path.is_absolute():
                root_path = root / root_path
            if root_path is not None and root_path.is_dir():
                for artifact in sorted(root_path.rglob("*")):
                    if not artifact.is_file() or len(events) >= limit:
                        continue
                    when = datetime.fromtimestamp(artifact.stat().st_mtime,
                                                  tz=timezone.utc).isoformat(timespec="seconds")
                    complete = artifact.name.endswith(".complete") or "COMPLETE" in artifact.name
                    events.append(Event(
                        when=when,
                        kind="output completed" if complete else "output written",
                        subject=str(wait.task_id or wait.job_id), detail=artifact.name,
                        project=project, capability=capability,
                        source=f"file modification time: {artifact.name}",
                        tone="good" if complete else "plain"))

    for evidence in sorted(root.glob("capabilities/*/evidence/*")):
        if not evidence.is_file() or len(events) >= limit:
            continue
        when = datetime.fromtimestamp(evidence.stat().st_mtime,
                                      tz=timezone.utc).isoformat(timespec="seconds")
        events.append(Event(when=when, kind="evidence recorded", subject=evidence.name,
                            project=project, capability=evidence.parent.parent.name,
                            source=f"file modification time: {evidence}"))

    for log in sorted(root.glob("**/observations.jsonl")):
        try:
            for number, line in enumerate(log.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip() or len(events) >= limit:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    events.append(Event(when="", kind="unreadable",
                                        subject=f"{log.name}:{number}",
                                        detail="the row is not JSON", project=project,
                                        source=str(log), tone="unknown"))
                    continue
                when = str(row.get("recorded_at") or row.get("at") or "")
                if not when:
                    events.append(Event(when="", kind="unreadable",
                                        subject=f"{log.name}:{number}",
                                        detail="the row states no time", project=project,
                                        source=str(log), tone="unknown"))
                    continue
                events.append(Event(
                    when=when, kind="observation recorded",
                    subject=str(row.get("task_class") or row.get("subject") or log.name),
                    detail=str(row.get("configuration") or row.get("outcome") or "")[:140],
                    project=project, source=f"{log.name}:{number}"))
        except OSError as exc:
            events.append(Event(when="", kind="unreadable", subject=log.name,
                                detail=str(exc)[:120], project=project, source=str(log),
                                tone="unknown"))

    events.sort(key=lambda e: (e.when == "", e.when), reverse=False)
    return events
