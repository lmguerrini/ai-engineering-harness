"""Resource truth: what a reading establishes, and what it must not imply.

The payload shape below is the one the installed Claude Code client documents
for its `statusLine` command. It was read out of the client rather than assumed,
and it is **version-fragile**: `rate_limits` is documented as optional, present
only for subscribers and only after a first API response, with each window
independently optional. So the absent case is the normal case, and most of these
tests are about it.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import resource_observation as ro
from errors import IntegrityError
from resource_observation import (
    DEFAULT_STALE_AFTER_SECONDS,
    QUOTA_SCHEMA,
    SOURCE_HUMAN_READING,
    SOURCE_PROVIDER_QUOTA,
    SOURCE_STATUS_LINE,
    UNKNOWN,
    from_human_reading,
    from_provider_quota,
    from_record,
    from_status_line,
)

NOW = 1_800_000_000.0

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "resource_observation.py"


def _quota(**overrides):
    """A minimal well-formed quota document, overridable field by field.

    The vendor-neutral spellings (`provider-a`, `pool-a`) are the ones the rest
    of this pack uses: no real vendor or model name belongs in Core or a test.
    """
    document = {
        "schema": QUOTA_SCHEMA,
        "provider_id": "provider-a",
        "billing_pool_id": "pool-a",
        "observed_at": NOW,
        "windows": [
            {"name": "rolling_5h", "used_percentage": 40.0, "resets_at": NOW + 3600}
        ],
    }
    document.update(overrides)
    return document


def _human(minutes_old=0, **overrides):
    """A minimal human reading, `minutes_old` before NOW unless told otherwise."""
    reading = {
        "provider_id": "provider-a",
        "billing_pool_id": "pool-a",
        "windows": {"rolling_5h": 40.0},
        "observed_at": NOW - minutes_old * 60,
    }
    reading.update(overrides)
    return from_human_reading(**reading)

FULL = {
    "session_id": "00000000-0000-4000-8000-000000000000",  # fictional; a real one is private runtime state
    "transcript_path": "/Users/someone/.claude/projects/x/session.jsonl",
    "cwd": "/Users/someone/private/project",
    "model": {"id": "claude-opus-5", "display_name": "Opus 5"},
    "workspace": {"current_dir": "/Users/someone/private", "project_dir": "/Users/someone/private"},
    "version": "2.1.236",
    "effort": {"level": "xhigh"},
    "context_window": {"used_percentage": 12.5, "remaining_percentage": 87.5},
    "rate_limits": {
        "five_hour": {"used_percentage": 41.2, "resets_at": NOW + 3600},
        "seven_day": {"used_percentage": 63.8, "resets_at": NOW + 86400},
    },
}

#: Documented as the case for a non-subscriber, or before the first response.
NO_LIMITS = {
    "model": {"id": "claude-opus-5"},
    "version": "2.1.236",
    "effort": {"level": "xhigh"},
    "context_window": {"used_percentage": None},
}


def test_a_full_payload_reads_every_documented_field():
    observation = from_status_line(FULL, observed_at=NOW)
    assert observation.source == SOURCE_STATUS_LINE
    assert observation.client_version == "2.1.236"
    assert observation.model_observed == "claude-opus-5"
    assert observation.effort_observed == "xhigh"
    assert observation.context_used_percentage == 12.5
    assert observation.window("five_hour").used_percentage == 41.2
    assert observation.window("seven_day").used_percentage == 63.8


# --- the allowlist ------------------------------------------------------------


def test_the_record_carries_no_path_no_session_id_and_no_working_directory():
    """Not fastidiousness: routing observations are scanned by this pack's own
    leak gate, and a transcript path is a local path while a session id is a
    UUID — two of the three universal leak kinds."""
    record = json.dumps(from_status_line(FULL, observed_at=NOW).as_record())
    assert "5e551011" not in record
    assert "/Users/" not in record
    assert "transcript" not in record
    assert "cwd" not in record


def test_the_projection_is_an_allowlist_and_a_new_field_does_not_leak_through():
    """A redaction pass fails open the first time the payload grows a field.
    This one is asked to survive exactly that."""
    grown = dict(FULL, some_future_field="/Users/someone/secret", another={"nested": "value"})
    record = json.dumps(from_status_line(grown, observed_at=NOW).as_record())
    assert "secret" not in record
    assert "some_future_field" not in record


def test_the_rendered_report_carries_nothing_private_either():
    rendered = from_status_line(FULL, observed_at=NOW).render(NOW)
    assert "/Users/" not in rendered
    assert "5e551011" not in rendered


# --- absence is not zero -------------------------------------------------------


def test_an_absent_rate_limit_is_unknown_and_not_zero_used():
    """A missing quota reading rendered as `0% used` is an invitation to spend."""
    observation = from_status_line(NO_LIMITS, observed_at=NOW)
    assert observation.window("five_hour").used_percentage == UNKNOWN
    assert observation.window("seven_day").used_percentage == UNKNOWN
    assert not observation.any_quota_known


def test_the_report_says_that_unknown_quota_is_not_available_quota():
    rendered = from_status_line(NO_LIMITS, observed_at=NOW).render(NOW)
    assert "quota: UNKNOWN" in rendered
    assert "not a statement that quota is available" in rendered


def test_each_window_is_independently_optional():
    partial = dict(FULL, rate_limits={"five_hour": {"used_percentage": 10.0}})
    observation = from_status_line(partial, observed_at=NOW)
    assert observation.window("five_hour").used_percentage == 10.0
    assert observation.window("five_hour").resets_at == UNKNOWN
    assert observation.window("seven_day").used_percentage == UNKNOWN
    assert "rate_limits.seven_day" in observation.absent
    assert observation.any_quota_known


def test_a_null_context_percentage_is_unknown():
    assert from_status_line(NO_LIMITS, observed_at=NOW).context_used_percentage == UNKNOWN


def test_a_boolean_is_not_read_as_a_number():
    odd = dict(FULL, rate_limits={"five_hour": {"used_percentage": True}})
    assert from_status_line(odd, observed_at=NOW).window("five_hour").used_percentage == UNKNOWN


# --- a broken adapter must not read as "nothing to worry about" ---------------


def test_an_unreadable_payload_produces_an_all_unknown_observation_with_the_reason():
    observation = from_status_line("not json at all", observed_at=NOW)
    assert observation.model_observed == UNKNOWN
    assert observation.client_version == UNKNOWN
    assert not observation.any_quota_known
    assert observation.notes and "could not be read" in observation.notes[0]


def test_an_unreadable_payload_is_not_reported_as_a_non_subscriber():
    """Two different reasons for absent quota, and naming the wrong one is the
    same defect this module exists to avoid."""
    rendered = from_status_line("not json", observed_at=NOW).render(NOW)
    assert "could not be read" in rendered
    assert "non-subscriber" not in rendered


def test_a_payload_that_is_not_an_object_is_handled(tmp_path):
    observation = from_status_line("[1, 2, 3]", observed_at=NOW)
    assert observation.notes and "not a JSON object" in observation.notes[0]


# --- a reading is about a moment ------------------------------------------------


def test_age_and_staleness_are_explicit():
    observation = from_status_line(FULL, observed_at=NOW)
    assert observation.age_seconds(NOW) == 0
    assert not observation.stale(NOW)
    assert observation.age_seconds(NOW + 60) == 60
    assert observation.stale(NOW + DEFAULT_STALE_AFTER_SECONDS + 1)


def test_a_stale_reading_says_so_in_its_report():
    observation = from_status_line(FULL, observed_at=NOW)
    assert "STALE" in observation.render(NOW + DEFAULT_STALE_AFTER_SECONDS + 1)
    assert "STALE" not in observation.render(NOW)


def test_the_report_refuses_to_be_read_as_a_forecast():
    assert "does not predict" in from_status_line(FULL, observed_at=NOW).render(NOW)


def test_the_clock_is_an_input_so_the_same_payload_gives_the_same_observation():
    """Wall-clock time is an input, not an ambient fact — otherwise a test of
    this module is a race and two readings of one payload differ."""
    first = from_status_line(FULL, observed_at=NOW)
    second = from_status_line(FULL, observed_at=NOW)
    assert first == second
    assert first.as_record() == second.as_record()


def test_seconds_until_reset_never_goes_negative():
    observation = from_status_line(FULL, observed_at=NOW)
    assert observation.window("five_hour").seconds_until_reset(NOW) == 3600
    assert observation.window("five_hour").seconds_until_reset(NOW + 999_999) == 0


# --- the capture path -----------------------------------------------------------


def test_an_observation_appends_as_one_json_line(tmp_path):
    from resource_observation import append_observation

    target = tmp_path / "routing" / "resource.jsonl"
    assert append_observation(target, from_status_line(FULL, observed_at=NOW)) is True
    assert len(target.read_text().strip().splitlines()) == 1
    assert json.loads(target.read_text())["model_observed"] == "claude-opus-5"


def test_an_identical_reading_is_not_appended_again(tmp_path):
    """A status line runs on every render. An unconditional append turns a
    routing record into a log of how often the terminal repainted, and a file
    that large stops being read."""
    from resource_observation import append_observation

    target = tmp_path / "resource.jsonl"
    append_observation(target, from_status_line(FULL, observed_at=NOW))
    assert append_observation(target, from_status_line(FULL, observed_at=NOW + 900)) is False
    assert len(target.read_text().strip().splitlines()) == 1


def test_a_changed_reading_is_appended(tmp_path):
    from resource_observation import append_observation

    target = tmp_path / "resource.jsonl"
    append_observation(target, from_status_line(FULL, observed_at=NOW))

    moved = dict(FULL)
    moved["rate_limits"] = {
        "five_hour": {"used_percentage": 55.0, "resets_at": NOW + 3600},
        "seven_day": {"used_percentage": 63.8, "resets_at": NOW + 86400},
    }
    assert append_observation(target, from_status_line(moved, observed_at=NOW + 60)) is True
    assert len(target.read_text().strip().splitlines()) == 2


def test_a_timestamp_alone_is_not_an_observation(tmp_path):
    """Only `observed_at` differs between two identical readings, and a
    timestamp is not something observed."""
    from resource_observation import append_observation

    target = tmp_path / "resource.jsonl"
    append_observation(target, from_status_line(FULL, observed_at=NOW))
    for offset in (1, 10, 10_000):
        assert append_observation(target, from_status_line(FULL, observed_at=NOW + offset)) is False


def test_an_unreadable_last_line_does_not_drop_the_reading(tmp_path):
    """Appending is the safe direction: a corrupt tail must not silently
    swallow an observation."""
    from resource_observation import append_observation

    target = tmp_path / "resource.jsonl"
    target.write_text("{not json\n")
    assert append_observation(target, from_status_line(FULL, observed_at=NOW)) is True


def test_the_appended_record_carries_nothing_private(tmp_path):
    from resource_observation import append_observation

    target = tmp_path / "resource.jsonl"
    append_observation(target, from_status_line(FULL, observed_at=NOW))
    written = target.read_text()
    assert "5e551011" not in written
    assert "/Users/" not in written


def test_a_json_object_that_is_not_this_client_is_not_attributed_to_it():
    """`if document` attributed *any* non-empty JSON object on stdin to this
    vendor — a claim about provenance made from nothing. Found by an
    independent audit."""
    from resource_observation import from_status_line as read

    assert read({"something": "else"}, observed_at=NOW).backend_family == UNKNOWN
    assert read({"version": "2.1.236"}, observed_at=NOW).backend_family == UNKNOWN
    assert read({"model": {"id": "x"}}, observed_at=NOW).backend_family == UNKNOWN
    assert read(FULL, observed_at=NOW).backend_family == "claude-cli"


# --- O6 / -k frozen: a reading past its horizon is never fresh -----------------


def test_a_frozen_quota_document_sixteen_minutes_old_is_stale_never_fresh():
    """A provider quota document carries a 15-minute horizon. Sixteen minutes
    is past it, and a stale reading must not be presentable as live — the
    figures it carries are still figures, and still about a moment."""
    observation = from_provider_quota(_quota(observed_at=NOW - 16 * 60))
    assert observation.freshness(NOW) == "STALE"
    window = observation.window("rolling_5h")
    assert window.used_percentage == 40.0
    assert window.resets_at == NOW + 3600
    rendered = observation.render(NOW)
    assert "16 min old" in rendered
    assert "FRESH" not in rendered


def test_a_frozen_quota_document_fourteen_minutes_old_is_fresh():
    assert from_provider_quota(_quota(observed_at=NOW - 14 * 60)).freshness(NOW) == "FRESH"


def test_a_frozen_status_line_thirty_one_minutes_old_is_stale_and_twenty_nine_is_fresh():
    assert from_status_line(FULL, observed_at=NOW - 31 * 60).freshness(NOW) == "STALE"
    assert from_status_line(FULL, observed_at=NOW - 29 * 60).freshness(NOW) == "FRESH"


def test_a_frozen_document_keeps_its_own_observed_at_whenever_it_is_read():
    """O6's other half: a re-emitted old sample does not advance observed_at.
    The document's moment is the document's; the clock only ages it."""
    observation = from_provider_quota(_quota(observed_at=NOW - 3600))
    for later in (NOW, NOW + 900, NOW + 100_000):
        assert observation.freshness(later) == "STALE"
        assert observation.observed_at == NOW - 3600


def test_a_frozen_human_reading_two_hours_old_is_stale_and_just_under_is_fresh():
    assert _human(minutes_old=121).freshness(NOW) == "STALE"
    assert _human(minutes_old=119).freshness(NOW) == "FRESH"


def test_a_frozen_reading_from_the_future_is_unknown_and_the_reason_says_why():
    """A moment that has not happened cannot establish anything about this
    one; negative age is UNKNOWN, not fresh-by-overflow."""
    observation = from_provider_quota(_quota(observed_at=NOW + 60))
    assert observation.freshness(NOW) == "UNKNOWN"
    assert "future" in observation.freshness_reason(NOW)


def test_a_frozen_document_of_only_unavailable_windows_is_unavailable_at_any_age():
    observation = from_provider_quota(
        _quota(observed_at=NOW - 100_000,
               windows=[{"name": "monthly", "availability": "UNAVAILABLE"}])
    )
    assert observation.freshness(NOW) == "UNAVAILABLE"
    assert observation.freshness(NOW + 10_000_000) == "UNAVAILABLE"


# --- O7 / -k window: natives, denominators, availability ----------------------


def test_a_window_with_both_natives_derives_its_percentages_and_notes_it():
    observation = from_provider_quota(_quota(windows=[
        {"name": "rolling_5h", "native_remaining": 30.0, "native_limit": 100.0},
    ]))
    window = observation.window("rolling_5h")
    assert window.used_percentage == 70.0
    assert window.remaining_percentage == 30.0
    assert any("derived" in note for note in observation.notes)


def test_a_window_whose_stated_percentage_disagrees_with_its_natives_loses_to_them():
    """A provider's stated percentage may be coarse; its own counts win, and
    the stated figure survives in a note rather than in the number."""
    observation = from_provider_quota(_quota(windows=[
        {"name": "rolling_5h", "used_percentage": 50.0,
         "native_remaining": 30.0, "native_limit": 100.0},
    ]))
    assert observation.window("rolling_5h").used_percentage == 70.0
    stated = [note for note in observation.notes if "stated" in note]
    assert stated and "50%" in stated[0] and "70%" in stated[0]


def test_a_window_with_one_native_only_keeps_unknown_percentages_and_the_native():
    observation = from_provider_quota(_quota(windows=[
        {"name": "rolling_5h", "used_percentage": 40.0, "native_remaining": 30.0},
    ]))
    window = observation.window("rolling_5h")
    assert window.used_percentage == UNKNOWN
    assert window.remaining_percentage == UNKNOWN
    assert window.native_remaining == 30.0
    assert window.native_limit == UNKNOWN


def test_a_window_declared_unavailable_is_not_known_and_says_so():
    observation = from_provider_quota(
        _quota(windows=[{"name": "monthly", "availability": "UNAVAILABLE"}])
    )
    window = observation.window("monthly")
    assert not window.known
    assert window.describe(NOW) == "monthly: UNAVAILABLE (not exposed by the source)"


def test_a_percentage_on_an_unavailable_window_is_refused():
    with pytest.raises(IntegrityError):
        from_provider_quota(_quota(windows=[
            {"name": "monthly", "availability": "UNAVAILABLE", "used_percentage": 10.0},
        ]))


def test_a_window_whose_stated_percentages_do_not_sum_to_100_is_refused():
    with pytest.raises(IntegrityError):
        from_provider_quota(_quota(windows=[
            {"name": "rolling_5h", "used_percentage": 60.0, "remaining_percentage": 50.0},
        ]))


def test_a_window_used_percentage_over_100_is_refused():
    with pytest.raises(IntegrityError):
        from_provider_quota(_quota(windows=[{"name": "rolling_5h", "used_percentage": 101.0}]))


def test_a_window_native_remaining_above_its_limit_is_refused():
    with pytest.raises(IntegrityError):
        from_provider_quota(_quota(windows=[
            {"name": "rolling_5h", "native_remaining": 120.0, "native_limit": 100.0},
        ]))


def test_a_quota_document_with_zero_windows_is_freshness_unavailable():
    assert from_provider_quota(_quota(windows=[])).freshness(NOW) == "UNAVAILABLE"


def test_a_window_resets_at_that_is_a_bool_is_refused():
    with pytest.raises(IntegrityError):
        from_provider_quota(_quota(windows=[{"name": "rolling_5h", "resets_at": True}]))


def test_the_two_new_source_names_are_in_the_declared_observer_vocabulary():
    """D33: the reader names a manifest's `capacity_observer.source` can
    declare. Coined here, they would be names no manifest can name."""
    from provider_manifest import OBSERVER_SOURCES

    assert SOURCE_PROVIDER_QUOTA in OBSERVER_SOURCES
    assert SOURCE_HUMAN_READING in OBSERVER_SOURCES


# --- O12 / -k mutation: the horizon and the derivation, each broken -----------


def test_mutation_inflating_every_horizon_flips_the_stale_oracle(monkeypatch):
    document = _quota(observed_at=NOW - 16 * 60)
    assert from_provider_quota(document).freshness(NOW) == "STALE"

    monkeypatch.setattr(ro, "SOURCE_HORIZONS", {
        ro.SOURCE_STATUS_LINE: 10**9,
        ro.SOURCE_PROVIDER_QUOTA: 10**9,
        ro.SOURCE_HUMAN_READING: 10**9,
    })
    relaxed = from_provider_quota(document)
    with pytest.raises(AssertionError):
        assert relaxed.freshness(NOW) == "STALE"


def test_mutation_deriving_percentages_from_one_native_flips_the_unknown_oracle(monkeypatch):
    document = _quota(windows=[{"name": "rolling_5h", "native_remaining": 30.0}])
    assert from_provider_quota(document).window("rolling_5h").used_percentage == UNKNOWN

    def _derive_from_remaining_alone(fields):
        derived = dict(fields)
        notes = []
        if derived.get("native_remaining") != UNKNOWN:
            derived["used_percentage"] = 50.0
            notes.append("mutated: a percentage derived from one native alone")
        return derived, notes

    monkeypatch.setattr(ro, "_derive_percentages", _derive_from_remaining_alone)
    mutated = from_provider_quota(document)
    with pytest.raises(AssertionError):
        assert mutated.window("rolling_5h").used_percentage == UNKNOWN


# --- records round-trip through every reader -----------------------------------


def test_every_readers_record_round_trips_through_from_record():
    status = from_status_line(FULL, observed_at=NOW)
    quota = from_provider_quota(_quota(windows=[
        {"name": "rolling_5h", "native_remaining": 30.0, "native_limit": 100.0},
    ]))
    human = _human(resets={"rolling_5h": NOW + 600})
    for observation in (status, quota, human):
        rebuilt = from_record(observation.as_record())
        assert rebuilt == observation
        assert rebuilt is not observation


def test_the_record_carries_no_key_outside_the_declared_allowlist():
    top = {
        "source", "observed_at", "backend_family", "client_version", "model_observed",
        "effort_observed", "context_used_percentage", "provider_id", "billing_pool_id",
        "provenance", "freshness_horizon_s", "windows", "absent", "notes",
    }
    per_window = {
        "name", "used_percentage", "resets_at", "remaining_percentage",
        "native_remaining", "native_limit", "native_unit", "availability",
    }
    for observation in (
        from_status_line(FULL, observed_at=NOW),
        from_provider_quota(_quota()),
        _human(),
    ):
        record = observation.as_record()
        assert set(record) <= top
        for window in record["windows"]:
            assert set(window) <= per_window


def test_from_record_refuses_an_unknown_top_level_key_naming_it():
    record = from_provider_quota(_quota()).as_record()
    record["surprise"] = "a field no reader implements"
    with pytest.raises(IntegrityError) as refusal:
        from_record(record)
    assert "surprise" in refusal.value.render()


def test_from_record_refuses_an_unknown_window_key_naming_it():
    record = from_provider_quota(_quota()).as_record()
    record["windows"][0]["surprise"] = 1
    with pytest.raises(IntegrityError) as refusal:
        from_record(record)
    assert "surprise" in refusal.value.render()


# --- the CLI: a document that cannot be read is a refusal, never a traceback ---


def _run_tool(arguments):
    return subprocess.run(
        [sys.executable, str(TOOL), *arguments],
        capture_output=True, text=True, timeout=60,
    )


def _nine_levels_deep():
    nested = {"name": "rolling_5h"}
    for _ in range(6):
        nested = {"nested": nested}
    return json.dumps({"schema": QUOTA_SCHEMA, "windows": [nested]}).encode("utf-8")


#: Each an unreadable quota document: a refusal with one sentence and no
#: traceback, because a document that cannot be read must not become a reading.
UNREADABLE_QUOTA_DOCUMENTS = [
    pytest.param(b"\xff\xfe not text at all", id="non-utf8-bytes"),
    pytest.param(_nine_levels_deep(), id="nine-level-nesting"),
    pytest.param(
        ('{"schema": "runtime-pack-quota-1", "observed_at": ' + "1" * 5000 + "}").encode("utf-8"),
        id="five-thousand-digit-integer",
    ),
    pytest.param(
        json.dumps(dict(_quota(), notes=["padding " * (2 * 1024 * 1024 // 8)])).encode("utf-8"),
        id="two-mebibyte-document",
    ),
    pytest.param(
        json.dumps(dict(_quota(), surprise="a field no reader implements")).encode("utf-8"),
        id="unknown-key",
    ),
]


@pytest.mark.parametrize("payload", UNREADABLE_QUOTA_DOCUMENTS)
def test_the_cli_refuses_an_unreadable_quota_document(tmp_path, payload):
    document = tmp_path / "quota.json"
    document.write_bytes(payload)
    result = _run_tool(["--provider-quota", str(document)])
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    first_line = result.stdout.splitlines()[0]
    assert first_line.startswith("REFUSED HX_INTEGRITY: ")
    # The sentence is one line; only its bounded details may follow it.
    assert len(result.stdout.strip().splitlines()) <= 5


def test_the_cli_help_exits_zero_within_five_seconds_without_reading_stdin():
    result = subprocess.run(
        [sys.executable, str(TOOL), "--help"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_the_cli_refuses_provider_quota_together_with_human_reading(tmp_path):
    document = tmp_path / "quota.json"
    document.write_text(json.dumps(_quota()), encoding="utf-8")
    result = _run_tool([
        "--provider-quota", str(document),
        "--human-reading", "--provider-id", "provider-a", "--pool-id", "pool-a",
        "--window", "rolling_5h=40", "--observed-at", "1800000000",
    ])
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "REFUSED" in result.stdout


def test_the_cli_human_reading_round_trips_through_json():
    result = _run_tool([
        "--human-reading", "--provider-id", "provider-a", "--pool-id", "pool-a",
        "--window", "rolling_5h=40", "--window", "seven_day=60",
        "--observed-at", "1800000000", "--resets", "rolling_5h=1800003600",
        "--json",
    ])
    # Exit 1, not 0: the observation carries the advisory note, and a --json
    # consumer reads the exit status (the same rule the status-line path set).
    assert result.returncode == 1
    record = json.loads(result.stdout)
    assert record["source"] == "human-reading"
    assert record["provenance"] == "human_reading"
    assert [window["name"] for window in record["windows"]] == ["rolling_5h", "seven_day"]
    assert [window["used_percentage"] for window in record["windows"]] == [40.0, 60.0]
    assert record["windows"][0]["resets_at"] == 1800003600.0
    assert "advisory, human-reported" in record["notes"]


def test_the_cli_accepts_an_iso8601_observed_at():
    result = _run_tool([
        "--human-reading", "--provider-id", "provider-a", "--pool-id", "pool-a",
        "--window", "rolling_5h=40", "--observed-at", "2027-01-15T08:00:00+00:00",
        "--json",
    ])
    assert json.loads(result.stdout)["observed_at"] == 1800000000.0
