"""The dashboard's required readings, checked against the implementation.

`policy/dashboard-readings.json` is the contract: the things a human watching a
long autonomous run must be able to get from the projection. This renders
representative states and asserts every row of it appears.

**It exists because the completeness figure was previously established by
running a script by hand and writing the number down.** That produced a report
saying *48 of 49* which was already stale when it was written — the
manually-transcribed-count defect this pack refuses everywhere else, in the
report about the thing that refuses it.

The check is presence, not meaning: it proves each reading is REACHABLE, and the
module's own tests prove each is CORRECT. Presence is the property that drifts,
because a reading is lost by a panel being removed or a key being renamed, and
neither breaks a test that never looked for it.
"""

import json
import os
from pathlib import Path

import pytest

import continuation
import projection
import task_output

CONTRACT = Path(__file__).resolve().parents[2] / "policy" / "dashboard-readings.json"


def _states(root: Path) -> list[Path]:
    """Representative states, public-safe, built here rather than fetched.

    No single state shows every reading — a run cannot be both waiting and
    idle — so the contract is satisfied across the set, which is the honest
    shape of the requirement.
    """
    now = continuation.now()
    common = dict(
        budgets={"closure cycles": {"used": 9, "ceiling": 10, "authorised_by": "a person"},
                 "repair rounds": {"used": 6, "ceiling": 8}},
        evidence={"candidate": "demo 1.4.0 IN_PROGRESS at 0f1e2d3c4b5a digest 9a8b7c6d",
                  "suite": "412 passing", "gates": "commit gate VALID",
                  "latest_audit": "cycle 3 READY at 0f1e2d3c4b5a",
                  "closure": "24 mechanisms, none uncovered",
                  "recurrence_classes": "18 of 18 against an executing oracle",
                  "real_consumers": "2 pinned projects, both verified, read-only",
                  "adapters": "4 files verified, 0 executables declared",
                  "continuation": "reconstruct rehearsal green in a separate process",
                  "public_safety": "history scan clean, zero unscanned",
                  "evolution_candidates": "2 open and declared"},
    )
    made = []

    waiting = root / "waiting"
    waiting.mkdir()
    output = waiting / "worker-output"
    contract = task_output.OutputContract("survey", output, max_bytes_per_write=4096,
                                          expected_chunks=3)
    task_output.claim_root(contract)
    task_output.materialise(contract, 0, json.dumps({"finding": "one"}))
    contract.part_path(1).write_text('{"partial')
    continuation.save(continuation.ContinuationRecord(
        capability="C7 — durable output recovery", updated_at=now,
        waits=(continuation.Wait(
            job_id="survey", kind=continuation.WaitKind.OUTPUT_ROOT, path=str(output),
            task_id="survey", max_bytes_per_write=4096, expects="three chunks",
            subject_revision="0f1e2d3c4b5a" + "0" * 28, subject_digest="9a8b7c6d" + "0" * 56,
            executor="independent-vendor model=x effort=high", attempt=2,
            retry_reason="ended without writing anything",
            routing_qualification="confirmed for this task class",
            not_beyond_seconds=3600, declared_at=now),),
        actionable=("consume the survey",), **common),
        waiting / "CONTINUATION.json")
    (waiting / "CAPACITY.json").write_text(json.dumps({
        "schema": "capacity-observation-v1",
        "pools": [{"pool_id": "independent", "kind": "independent", "window": "weekly",
                   "remaining": 340, "unit": "requests", "observed_at": now,
                   "resets_at": "2026-01-01T00:00:00+00:00", "active_workers": 1}],
        "reserve": {"coordinator": 20, "result_consumption": 10, "repair_and_audit": 10}}))
    made.append(waiting)

    idle = root / "idle"
    idle.mkdir()
    continuation.save(continuation.ContinuationRecord(
        capability="C7 — durable output recovery", updated_at=now,
        actionable=("repair the finding", "re-run the suite"),
        blockers=(continuation.Blocker(kind="human", hitl_row=4,
                                       detail="ending a stalled worker is a human action",
                                       blocks=("repair the finding",)),), **common),
        idle / "CONTINUATION.json")
    made.append(idle)

    done = root / "done"
    done.mkdir()
    sentinel = done / "audit.status"
    wait = continuation.Wait(job_id="audit", kind=continuation.WaitKind.PATH_EXISTS,
                             path=str(sentinel), expects="a verdict",
                             subject_revision="deadbeefcafe" + "0" * 28,
                             executor="same-family model=y", not_beyond_seconds=3600,
                             declared_at=now)
    sentinel.write_text("0\n")
    continuation.save(continuation.ContinuationRecord(
        capability="C7 — durable output recovery", updated_at=now, waits=(wait,),
        actionable=("consume the verdict",), **common), done / "CONTINUATION.json")
    made.append(done)

    live = root / "live"
    live.mkdir()
    continuation.save(continuation.ContinuationRecord(
        capability="C7 — durable output recovery", updated_at=now,
        waits=(continuation.Wait(job_id="watcher", kind=continuation.WaitKind.PROCESS, pid=1,
                                 expects="a report", executor="independent-vendor model=x",
                                 not_beyond_seconds=1, declared_at="2020-01-01T00:00:00+00:00"),),
        actionable=("consume the report",), **common), live / "CONTINUATION.json")
    made.append(live)
    return made


def _page_as_text(page: str) -> str:
    """The page's readings in the text view's shape.

    The two renderers serialise one reading differently — `capability: C7` in
    text, `<span class=k>capability</span><span class=v>C7</span>` in the page —
    so a marker sharp enough to discriminate in one does not literally occur in
    the other. Rather than weaken the markers back to words that match anything,
    the page is normalised into the shape the marker is written in.

    Deliberately crude: it is a test helper comparing two serialisations of the
    same data, not a parser, and it must not become one.
    """
    import re

    text = page.replace("</span><span class=v>", ": ").replace("</h2>", ": ")
    text = re.sub(r"<[^>]+>", "", text)
    return text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    root = tmp_path_factory.mktemp("dashboard-contract")
    text = [projection.project(state).render() for state in _states(root)]
    page = [_page_as_text(projection.render_html(projection.project(state))) for state in _states(
        tmp_path_factory.mktemp("dashboard-contract-html"))]
    return "\n".join(text), "\n".join(page)


def _contract():
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


@pytest.mark.parametrize("row", _contract()["readings"], ids=lambda r: r["reading"])
def test_every_required_reading_is_reachable_in_the_text_view(row, rendered):
    text, _ = rendered
    assert row["marker"].lower() in text.lower(), (
        f"the projection no longer shows {row['reading']!r} — {row['why']}")


@pytest.mark.parametrize("row", _contract()["readings"], ids=lambda r: r["reading"])
def test_every_required_reading_is_reachable_in_the_page(row, rendered):
    _, page = rendered
    assert row["marker"].lower() in page.lower(), (
        f"the page no longer shows {row['reading']!r} — {row['why']}")


def test_the_contract_and_the_count_cannot_drift_apart():
    """The number is derived here and stated nowhere else. A report that says
    *48 of 49* is a number somebody wrote down, and it was already stale when it
    was written."""
    rows = _contract()["readings"]
    assert len(rows) == len({r["reading"] for r in rows}), "a reading is listed twice"
    assert all(r["marker"].strip() and r["why"].strip() for r in rows)
    # THE COUNT ITSELF. The previous version guarded uniqueness and non-empty
    # fields and not the number, so a reading could be dropped from the contract
    # and every check would still pass — the file would simply require less of
    # the implementation. An independent reader pointed that out.
    assert len(rows) == 49, (
        f"the contract holds {len(rows)} readings. Changing that is a decision about what a "
        f"reader of a long autonomous run must be able to see, so it changes here and in this "
        f"number together")


def test_a_reading_removed_from_the_projection_fails_this_contract(tmp_path):
    """The bound. Every assertion above passes trivially if the markers are
    things no projection could avoid printing, so one is removed here and the
    check must notice."""
    state = _states(tmp_path)[0]
    full = projection.project(state).render()
    assert "NEXT AUTHORISED ACTION" in full

    without = "\n".join(line for line in full.splitlines()
                        if "NEXT AUTHORISED ACTION" not in line)
    row = next(r for r in _contract()["readings"] if r["reading"] == "next authorised action")
    assert row["marker"].lower() not in without.lower()


#: Readings whose marker legitimately appears with no project record at all —
#: the pack's own manifest, the page's fixed vocabulary, the panel titles, and
#: the header. Everything else must come from the record.
_FROM_THE_PACK_OR_THE_CHROME = {
    "pack version", "pack state", "pack digest", "pack revision", "adoptability",
    "UNKNOWN", "projection versus authority", "coordinator state",
    "project identity and pin", "durable output",
    "freshness of the reading", "budgets used and remaining",
    "outstanding evolution candidates", "public-safety state", "continuation health",
    "recurrence-class status", "real-consumer compatibility", "adapter qualification",
    "latest audit verdict", "failure-mode closure status", "deterministic gate status",
    "STALLED", "ORPHANED", "SUPERSEDED", "context reconstruction",
}


@pytest.mark.parametrize(
    "row", [r for r in _contract()["readings"]
            if r["reading"] not in _FROM_THE_PACK_OR_THE_CHROME],
    ids=lambda r: r["reading"])
def test_a_marker_must_come_from_the_record_and_not_from_the_page(row, tmp_path):
    """Every marker must DISCRIMINATE its own reading.

    The first version removed every line containing the marker and asserted the
    marker was gone — **which it is, by construction.** An independent reader
    said so: the test could not detect its own claimed failure mode.

    What actually distinguishes a marker from chrome is where it comes from. A
    projection of a directory with **nothing declared** renders the pack's own
    identity, the fixed vocabulary, the panel titles and the header, and nothing
    else; a marker appearing there is produced by the page rather than by the
    reading it names. The readings that legitimately do appear are listed above
    by name, so adding one is a decision somebody makes in the open rather than
    a marker quietly going slack.
    """
    empty = projection.project(tmp_path).render()
    assert row["marker"].lower() not in empty.lower(), (
        f"the marker {row['marker']!r} for {row['reading']!r} appears with no record at all, so "
        f"it is matching the page rather than the reading")



@pytest.mark.parametrize("row", _contract()["readings"], ids=lambda r: r["reading"])
def test_no_marker_matches_the_sentence_that_denies_it(row, rendered):
    """**A marker that also matches the opposite state discriminates nothing.**

    `adoptability` was the bare word `ADOPTABLE`, and the only place the
    projection used it was `NOT ADOPTABLE: only QUALIFIED_AND_FROZEN may be
    pinned` — so the contract for *this release may be adopted* was satisfied,
    in every state, by the sentence saying it may not. An independent reader
    printed the surrounding characters.

    The class is mechanical even though the general question is not: whatever a
    reading means, a marker preceded by a negation in the rendered text is
    matching both answers at once.
    """
    text, page = rendered
    marker = row["marker"].lower().strip()
    #: Phrases that begin with a negation and the marker, and deny a DIFFERENT
    #: reading. Declared per row, by name, with the reason in `why` — an
    #: exception somebody makes in the open rather than a guard going slack.
    # And each one must still occur: an exception for a sentence the projection
    # no longer renders is an exception nobody re-examined, so a stale entry
    # here goes red rather than quietly widening the marker.
    allowed = [p.lower() for p in row.get("not_a_denial", [])]
    for phrase in allowed:
        assert phrase in text.lower(), (
            f"{row['reading']!r} declares {phrase!r} is not a denial, and the projection no "
            f"longer renders it. Re-examine the marker rather than keeping the exception")
    for negation in ("not ", "no ", "never ", "cannot "):
        for where, rendered_text in (("text view", text.lower()), ("page", page.lower())):
            hunted = rendered_text
            for phrase in allowed:
                hunted = hunted.replace(phrase, " ")
            assert negation + marker not in hunted, (
                f"{row['reading']!r} matches {negation + marker!r} in the {where}, so it is "
                f"satisfied by the sentence that denies it")
