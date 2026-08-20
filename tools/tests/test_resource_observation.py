"""Resource truth: what a reading establishes, and what it must not imply.

The payload shape below is the one the installed Claude Code client documents
for its `statusLine` command. It was read out of the client rather than assumed,
and it is **version-fragile**: `rate_limits` is documented as optional, present
only for subscribers and only after a first API response, with each window
independently optional. So the absent case is the normal case, and most of these
tests are about it.
"""

import json

import pytest

from resource_observation import (
    DEFAULT_STALE_AFTER_SECONDS,
    SOURCE_STATUS_LINE,
    UNKNOWN,
    from_status_line,
)

NOW = 1_800_000_000.0

FULL = {
    "session_id": "5e551011-0000-4000-8000-000000000001",
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
