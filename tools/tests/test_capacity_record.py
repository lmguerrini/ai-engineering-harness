"""The only writer of CAPACITY.json, and the reader that quarantines (D36).

Round trip: what `write` puts on disk is what `check` reads back, with nothing
lost. Quarantine: a malformed entry is a sentence and a count while the rest
still load, and a writer asked to keep what it could not read refuses rather
than drops it. Read-only: `check`, `--help` and a `--dry-run` leave every byte
of a project untouched — asserted by hashing the tree, not by reading source.
"""

import hashlib
import json
import pathlib
import subprocess
import sys

import pytest

import capacity
import capacity_record
import resource_observation
from errors import IntegrityError

#: The tool as a subprocess sees it, derived from the module rather than from
#: any machine's layout.
ROOT = pathlib.Path(capacity_record.__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "capacity_record.py"

#: A fixed moment, so a verdict here is about the reading and never about when
#: the suite happened to run.
_NOW = 1789000000.0


def _quota_document(observed_at=_NOW - 60, windows=None):
    """A `runtime-pack-quota-1` document an adapter's observer might emit."""
    return {
        "schema": "runtime-pack-quota-1",
        "provider_id": "provider-a",
        "billing_pool_id": "pool-a",
        "observed_at": observed_at,
        "windows": windows if windows is not None else [
            {"name": "rolling_5h", "used_percentage": 62.5, "remaining_percentage": 37.5,
             "resets_at": observed_at + 3600},
        ],
    }


def _run(*argv):
    return subprocess.run([sys.executable, str(TOOL), *argv],
                          capture_output=True, text=True, timeout=120)


def _tree_digest(root):
    """Every file under a directory, by path and content."""
    digest = hashlib.sha256()
    for path in sorted(p for p in pathlib.Path(root).rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_pool(record, pool_id="pool-a", *, keep_existing=False, extra=()):
    """One CLI write of one pool from the standard quota document."""
    quota = pathlib.Path(str(record) + f".{pool_id}.quota.json")
    quota.write_text(json.dumps(_quota_document()), encoding="utf-8")
    argv = ["write", str(record), "--written-by", "the coordinator",
            "--pool-from", str(quota), "--pool-id", pool_id, "--kind", "independent",
            "--window", "rolling", "--window-name", "rolling_5h", "--now", str(_NOW)]
    if keep_existing:
        argv.append("--keep-existing")
    return _run(*argv, *extra), quota


def _two_pool_record(tmp_path):
    """A written record holding one observed pool and one 2.5.0-shaped pool."""
    record = tmp_path / "CAPACITY.json"
    observed = capacity.pool_from_observation(
        resource_observation.from_provider_quota(_quota_document()),
        pool_id="pool-a", kind="independent", window="rolling", window_name="rolling_5h")
    plain = capacity.Pool(pool_id="pool-b", remaining=340, unit="requests",
                          observed_at="2026-09-03T04:00:00Z")
    capacity_record.write(record, pools=[observed, plain], reserve=None,
                          written_by="the coordinator", now=_NOW)
    return record


# --- the round trip ----------------------------------------------------------------


def test_write_then_check_roundtrips_a_record(tmp_path):
    record = tmp_path / "CAPACITY.json"
    pool = capacity.pool_from_observation(
        resource_observation.from_provider_quota(_quota_document()),
        pool_id="pool-a", kind="independent", window="rolling", window_name="rolling_5h",
        billing_mode="subscription")
    document = capacity_record.write(
        record, pools=[pool], reserve=capacity.Reserve(coordinator=10),
        written_by="the coordinator at a capability boundary", now=_NOW)

    assert document["schema"] == capacity_record.SCHEMA
    assert document["written_at"] == "2026-09-10T00:26:40Z"
    assert document["written_by"] == "the coordinator at a capability boundary"
    assert json.loads(record.read_text(encoding="utf-8")) == document

    report = capacity_record.check(record, now=_NOW)
    assert report.schema_ok and report.pools_ok == 1 and not report.quarantined
    assert report.freshness == {"pool-a": "FRESH"}
    assert report.reserve == "declared"
    pools, quarantined = capacity_record.read_pools(record, now=_NOW)
    assert quarantined == [] and pools == [pool]


def test_keep_existing_roundtrips_the_other_pools(tmp_path):
    record = tmp_path / "CAPACITY.json"
    result, _quota = _write_pool(record, extra=["--reserve", "coordinator=10"])
    assert result.returncode == 0, result.stdout + result.stderr

    # A second pool from a document exposing a different window, keeping the
    # first: one pool per invocation is the rule, not the whole record at once.
    other = tmp_path / "quota-b.json"
    other.write_text(json.dumps(_quota_document(windows=[
        {"name": "monthly", "used_percentage": 10.0, "remaining_percentage": 90.0}])),
        encoding="utf-8")
    result = _run("write", str(record), "--written-by", "the coordinator",
                  "--pool-from", str(other), "--pool-id", "pool-b", "--kind", "independent",
                  "--window", "rolling", "--window-name", "monthly",
                  "--keep-existing", "--now", str(_NOW))
    assert result.returncode == 0, result.stdout + result.stderr
    pools, quarantined = capacity_record.read_pools(record, now=_NOW)
    assert quarantined == []
    assert sorted(p.pool_id for p in pools) == ["pool-a", "pool-b"]

    # The same pool_id again is a newer reading of THAT pool, not a duplicate.
    result, _quota = _write_pool(record, keep_existing=True)
    assert result.returncode == 0, result.stdout + result.stderr
    pools, quarantined = capacity_record.read_pools(record, now=_NOW)
    assert quarantined == []
    assert sorted(p.pool_id for p in pools) == ["pool-a", "pool-b"]

    # Without --keep-existing the record holds exactly the one pool written.
    lone = tmp_path / "lone.json"
    result, _quota = _write_pool(lone)
    assert result.returncode == 0, result.stdout + result.stderr
    pools, _ = capacity_record.read_pools(lone, now=_NOW)
    assert [p.pool_id for p in pools] == ["pool-a"]


def test_a_quota_document_roundtrips_onto_a_pool_with_its_provenance(tmp_path):
    record = tmp_path / "CAPACITY.json"
    result, _quota = _write_pool(record, extra=["--billing-mode", "subscription"])
    assert result.returncode == 0, result.stdout + result.stderr

    pools, quarantined = capacity_record.read_pools(record, now=_NOW)
    assert quarantined == []
    assert pools[0].observation["provenance"] == "provider_endpoint"
    assert pools[0].billing_mode == "subscription"
    # `--provider-id` absent: the reading's own attribution, not UNKNOWN beside
    # a figure that names its provider.
    assert pools[0].provider_id == "provider-a"


def test_a_duplicate_pool_id_refuses_the_roundtrip(tmp_path):
    """Two entries with one id are two readings racing to be the one a
    coordinator believes; the writer refuses before it opens anything."""
    record = tmp_path / "CAPACITY.json"
    pool = capacity.Pool(pool_id="pool-a", remaining=10, observed_at="2026-09-03T04:00:00Z")
    with pytest.raises(IntegrityError) as caught:
        capacity_record.write(record, pools=[pool, pool], reserve=None,
                              written_by="the coordinator", now=_NOW)
    assert "each pool once" in caught.value.render()
    with pytest.raises(IntegrityError):
        capacity_record.write(record, pools=[{"pool_id": "pool-a"}], reserve=None,
                              written_by="the coordinator", now=_NOW)
    assert not record.exists()


def test_a_blank_written_by_refuses_the_roundtrip(tmp_path):
    record = tmp_path / "CAPACITY.json"
    quota = tmp_path / "quota.json"
    quota.write_text(json.dumps(_quota_document()), encoding="utf-8")
    # A blank attribution is nobody, and a record nobody stands behind is the
    # shape this module exists to replace.
    blank = _run("write", str(record), "--written-by", "   ",
                 "--pool-from", str(quota), "--pool-id", "pool-a", "--kind", "independent",
                 "--window", "rolling", "--window-name", "rolling_5h", "--now", str(_NOW))
    assert blank.returncode == 2
    assert "blank attribution" in blank.stdout + blank.stderr
    assert not record.exists()


# --- quarantine: a sentence and a count, never a silent drop ------------------------


def test_a_hand_edited_entry_is_quarantined_while_the_rest_still_read(tmp_path):
    record = _two_pool_record(tmp_path)
    document = json.loads(record.read_text(encoding="utf-8"))
    document["pools"][0]["a_key_nobody_declared"] = True
    record.write_text(json.dumps(document, indent=2), encoding="utf-8")

    report = capacity_record.check(record, now=_NOW)
    assert report.pools_ok == 1 and len(report.quarantined) == 1
    sentence = report.quarantined[0]
    assert "pool entry 1" in sentence and "pool-a" in sentence
    assert "a_key_nobody_declared" in sentence
    # The untouched 2.5.0-shaped entry still reads — and is judged by this
    # module's own ceiling, a week-old reading with no observation of its own.
    assert report.freshness == {"pool-b": "STALE"}

    result = _run("check", str(record), "--now", str(_NOW))
    assert result.returncode == 1
    assert "1 quarantined" in result.stdout and sentence in result.stdout
    assert "Traceback" not in result.stderr


def test_a_writer_never_overwrites_a_quarantined_entry(tmp_path):
    """`--keep-existing` over a record holding an unreadable entry: refused,
    exit 2, and the file left byte-identical — because overwriting it would be
    deciding, silently, that the entry is gone."""
    record = _two_pool_record(tmp_path)
    document = json.loads(record.read_text(encoding="utf-8"))
    document["pools"][0]["a_key_nobody_declared"] = True
    record.write_text(json.dumps(document, indent=2), encoding="utf-8")
    quota = tmp_path / "quota.json"
    quota.write_text(json.dumps(_quota_document()), encoding="utf-8")
    before = record.read_bytes()

    result = _run("write", str(record), "--written-by", "the coordinator",
                  "--pool-from", str(quota), "--pool-id", "pool-b", "--kind", "independent",
                  "--window", "rolling", "--window-name", "rolling_5h",
                  "--keep-existing", "--now", str(_NOW))
    assert result.returncode == 2
    assert "never silently drops" in result.stdout + result.stderr
    assert record.read_bytes() == before


def test_a_document_without_a_pools_list_quarantines_rather_than_tracebacks(tmp_path):
    for shape in ({"pools": 1}, {"pools": {"pool_id": "x"}}, {}):
        record = tmp_path / "CAPACITY.json"
        record.write_text(json.dumps(shape), encoding="utf-8")
        result = _run("check", str(record), "--now", str(_NOW))
        assert result.returncode == 1, shape
        assert "carries no pools list" in result.stdout
        assert "Traceback" not in result.stderr
        pools, quarantined = capacity_record.read_pools(record, now=_NOW)
        assert pools == [] and len(quarantined) == 1


def test_a_record_with_no_schema_checks_as_a_250_document_without_quarantine(tmp_path):
    record = tmp_path / "CAPACITY.json"
    record.write_text(json.dumps({
        "pools": [{"pool_id": "shared", "kind": "shared_with_coordinator", "window": "rolling",
                   "remaining": "UNKNOWN", "active_workers": 1,
                   "observed_at": "2026-09-03T04:00Z"}],
        "reserve": {"coordinator": 10}}), encoding="utf-8")
    result = _run("check", str(record), "--now", str(_NOW))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no schema declared; read as a 2.5.0 document" in result.stdout

    report = capacity_record.check(record, now=_NOW)
    assert report.schema_ok and report.pools_ok == 1 and not report.quarantined
    assert report.freshness == {"shared": "UNKNOWN"}


def test_an_observation_past_its_horizon_checks_as_stale(tmp_path):
    """Freshness is computed at READ time: the same record asked inside the
    reading's horizon is FRESH and asked later is STALE, with nothing stored
    that could pre-decide which."""
    record = tmp_path / "CAPACITY.json"
    quota = tmp_path / "quota.json"
    quota.write_text(json.dumps(_quota_document(observed_at=_NOW - 3600)), encoding="utf-8")
    assert _run("write", str(record), "--written-by", "the coordinator",
                "--pool-from", str(quota), "--pool-id", "pool-a", "--kind", "independent",
                "--window", "rolling", "--window-name", "rolling_5h",
                "--now", str(_NOW)).returncode == 0

    report = capacity_record.check(record, now=_NOW)
    assert report.freshness == {"pool-a": "STALE"}
    assert "pool-a: STALE" in capacity_record.render(report)
    earlier = capacity_record.check(record, now=_NOW - 3500)
    assert earlier.freshness == {"pool-a": "FRESH"}


def test_the_template_checks_clean_and_reads_stale_by_construction():
    """The shipped example carries placeholder timestamps in 2000, so it can
    never look fresh to a reader — an example that read FRESH would be a
    reading nobody made."""
    report = capacity_record.check(ROOT / "templates" / "CAPACITY.json.template", now=_NOW)
    assert report.schema_ok and report.pools_ok == 1 and not report.quarantined
    assert report.freshness == {"pool-a": "STALE"}


# --- read-only by construction, asserted by hash ------------------------------------


def test_check_help_and_dry_run_are_readonly(tmp_path):
    record = tmp_path / "CAPACITY.json"
    result, _quota = _write_pool(record)
    assert result.returncode == 0, result.stdout + result.stderr
    before = _tree_digest(tmp_path)

    assert _run("--help").returncode == 0
    assert _run("check", str(record), "--now", str(_NOW)).returncode == 0
    dry = _run("write", str(record), "--dry-run", "--written-by", "the coordinator",
               "--pool-from", str(_quota), "--pool-id", "pool-a",
               "--kind", "independent", "--window", "rolling", "--window-name", "rolling_5h",
               "--keep-existing", "--now", str(_NOW))
    assert dry.returncode == 0, dry.stdout + dry.stderr
    assert json.loads(dry.stdout)["schema"] == capacity_record.SCHEMA

    assert _tree_digest(tmp_path) == before
    # And no residue: the atomic writer's temporary files are gone.
    assert sorted(path.name for path in tmp_path.iterdir()) == \
        ["CAPACITY.json", "CAPACITY.json.pool-a.quota.json"]
