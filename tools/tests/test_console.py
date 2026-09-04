"""The multi-project console: a reading of many projects, and nothing else.

Every property here is about the boundary between *arranging* and *deciding*.
The console may position, order, filter and count what the projections
produced; the moment it computes a project's condition it becomes a second
opinion about a thing that already has an owner, and the first disagreement
between them is unadjudicable.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import console
import continuation as _continuation
import projection
import task_output

ROOT = Path(__file__).resolve().parents[2]


def _project(root: Path, **fields):
    root.mkdir(parents=True, exist_ok=True)
    fields.setdefault("capability", "C1 — a capability")
    fields.setdefault("updated_at", _continuation.now())
    _continuation.save(_continuation.ContinuationRecord(**fields), root / "CONTINUATION.json")
    return root


@pytest.fixture
def three(tmp_path):
    """Three projects in genuinely different conditions, plus one that is not
    there and one that is named twice. The shape a registry actually has."""
    output = tmp_path / "b" / "worker-output"
    contract = task_output.OutputContract("survey", output, max_bytes_per_write=64,
                                          expected_chunks=2)
    output.parent.mkdir(parents=True, exist_ok=True)
    task_output.claim_root(contract)
    task_output.materialise(contract, 0, "a finding")
    _project(tmp_path / "a", actionable=("work nobody is doing",),
             budgets={"cycles": {"used": 9, "ceiling": 9}},
             evidence={"suite": "412 passing", "candidate": "demo at abcdef123456"})
    _project(tmp_path / "b",
             waits=(_continuation.Wait(job_id="survey", kind=_continuation.WaitKind.OUTPUT_ROOT,
                                       path=str(output), task_id="survey",
                                       max_bytes_per_write=64, expects="two chunks",
                                       subject_revision="abcdef123456" + "0" * 28,
                                       executor="a worker somewhere",
                                       not_beyond_seconds=3600,
                                       declared_at=_continuation.now()),),
             actionable=("consume the survey",),
             evidence={"candidate": "demo at abcdef123456"})
    _project(tmp_path / "c", actionable=("freeze",),
             blockers=(_continuation.Blocker(kind="human", hitl_row=2,
                                             detail="the founder's act", blocks=("freeze",)),))
    (tmp_path / "c" / "CAPACITY.json").write_text(json.dumps({
        "schema": "capacity-observation-v1",
        "pools": [{"pool_id": "independent", "kind": "independent", "window": "weekly",
                   "remaining": 40, "unit": "requests", "observed_at": _continuation.now(),
                   "active_workers": 1}]}))
    return [(None, tmp_path / "a"), (None, tmp_path / "b"), (None, tmp_path / "c"),
            (None, tmp_path / "gone"), ("a again", tmp_path / "a")]


# --- discovery ------------------------------------------------------------------------


def test_a_project_that_is_not_there_is_shown_and_not_dropped(three):
    sites = console.survey(three)
    missing = [s for s in sites if s.name == "gone"]
    assert missing, "a registry entry that does not resolve vanished from the console"
    assert missing[0].view is None and "no directory" in missing[0].unreadable
    page = console.render_console(sites)
    assert "gone" in page and "no directory" in page


def test_the_same_tree_named_twice_is_marked_rather_than_merged(three):
    """Two entries pointing at one project is a fact about the registry.
    Merging them silently makes the registry look right."""
    sites = console.survey(three)
    twice = [s for s in sites if s.same_tree_as]
    assert twice, "the duplicate was merged away"
    assert twice[0].same_tree_as == "a"
    assert "the same tree as a" in console.render_console(sites)


def test_no_project_named_is_not_an_empty_page():
    page = console.render_console(console.survey([]))
    assert "No project was named" in page
    assert page.endswith("</html>")


def test_a_registry_that_is_not_one_is_refused(tmp_path):
    bad = tmp_path / "registry.json"
    bad.write_text(json.dumps({"projects": [{"name": "no root here"}]}))
    with pytest.raises(ValueError):
        console.registry(bad)
    bad.write_text(json.dumps(["a", "b"]))
    with pytest.raises(ValueError):
        console.registry(bad)


def test_a_registry_names_where_to_look_and_never_what_is_true(tmp_path, three):
    """A stale registry can name a project that has moved. What it may never do
    is supply the state — that is read from the project, every time."""
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"schema": "project-registry-v1", "projects": [
        {"root": str(tmp_path / "a"), "name": "alpha", "state": "EVERYTHING IS FINE"}]}))
    sites = console.survey(console.registry(path))
    assert sites[0].name == "alpha"
    assert sites[0].state != "EVERYTHING IS FINE"
    assert "EVERYTHING IS FINE" not in console.render_console(sites)


# --- the boundary ---------------------------------------------------------------------


def test_the_console_asks_the_projection_and_derives_nothing(three, monkeypatch):
    """Asserted by watching the call, not by reading the source: a console that
    reached `continuation.derive` itself would be a second reader of the same
    question."""
    asked = []
    real = projection.project

    def watched(root, **kw):
        asked.append(str(root))
        return real(root, **kw)

    monkeypatch.setattr(projection, "project", watched)
    sites = console.survey(three)
    console.render_console(sites)
    assert len(asked) == 4, f"one reading per resolvable root, got {asked}"


def test_the_module_has_no_write_verb():
    names = set(dir(console))
    for forbidden in ("save", "write", "cache", "snapshot", "persist", "update", "store",
                      "serve", "watch", "run_server", "schedule", "wake", "terminate"):
        assert forbidden not in names, f"console gained {forbidden!r}"


def test_rendering_writes_nothing(three, tmp_path):
    before = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*") if p.is_file()}
    console.render_console(console.survey(three))
    after = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after, "the console wrote to the projects it was reading"


def test_every_figure_in_a_table_came_from_a_projection(three):
    """The whole anti-fabrication bound. Every value in every cross-project
    table is a `Cell` a panel made; a table that could carry anything else
    would be the page inventing telemetry."""
    sites = console.survey(three)
    page = console.render_console(sites)
    for site in sites:
        if site.view is None:
            continue
        for cell in site.view.situation + site.view.telemetry + site.view.identity:
            assert projection._escape(cell.value) in page
            for column, value in cell.fields.items():
                assert projection._escape(value) in page, (
                    f"{site.name}: the column {column} shows {value!r}, which is not on the page")


def test_one_project_never_shows_another_projects_work(three):
    """Cross-contamination, asserted per row rather than per page: every row of
    the workers table carries the project whose panel produced it."""
    sites = console.survey(three)
    page = console.render_console(sites)
    workers = page[page.index("data-view='workers'"):page.index("data-view='audits'")]
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", workers, re.S):
        named = [s.name for s in sites if f">{s.name}<" in row]
        assert len(named) <= 1, f"a worker row names {named}"
    # and the one job that exists is attributed to the project that declares it
    assert "survey" in workers
    owner = next(r for r in re.findall(r"<tr[^>]*>(.*?)</tr>", workers, re.S) if "survey" in r)
    assert ">b<" in owner, "the survey is attributed to the project that declares it"


# --- what the page must never do -------------------------------------------------------


def test_every_view_is_in_the_document_and_none_is_hidden(three):
    """**The page is complete with scripting switched off.** The script hides
    all but one view on load; nothing is hidden when the document is written,
    so no failure of that script can hide an UNKNOWN."""
    page = console.render_console(console.survey(three))
    views = re.findall(r"<section class=view data-view='([^']+)'", page)
    assert {"overview", "projects", "workers", "audits", "capacity", "history", "identity",
            "custom", "settings"} <= set(views)
    assert len([v for v in views if v.startswith("project:")]) == 5
    # The MARKUP, not the script: the script's job is to set `hidden`, so
    # searching the whole document finds the word every time and proves nothing.
    # The ATTRIBUTE, in a tag. Searching the text finds the word in the script
    # that sets it and in the comment explaining why the stylesheet has to
    # honour it, neither of which hides anything.
    markup = re.sub(r"<style>.*?</style>", "", page[:page.index("<script>")], flags=re.S)
    assert not re.search(r"<[^>]*\shidden[\s>=]", markup), (
        "a view is hidden in the delivered HTML")


def test_a_stall_is_never_reported_as_none(three):
    """A stall needs two independently observed flat signals over time and this
    page is one reading. `0` would be an answer; the column says the question
    is not answered here."""
    page = console.render_console(console.survey(three))
    shown = re.findall(r"data-label='stalled'>(.*?)</td>", page)
    assert shown, "there is no stalled column at all"
    assert set(shown) == {"·"}, f"a stall was answered rather than declined: {set(shown)}"
    assert "two readings" in page


def test_an_unreadable_project_still_counts_as_needing_attention(three):
    """No aggregate may be greener than its parts."""
    sites = console.survey(three)
    missing = next(s for s in sites if s.view is None)
    assert sum(missing.attention.values()) >= 1
    assert missing.tone == projection.Tone.UNKNOWN


def test_every_widget_offered_exists_on_the_page(three):
    """A catalogue entry with nothing behind it is a control that does nothing
    — and the reader cannot tell that from a widget that renders empty."""
    page = console.render_console(console.survey(three))
    sources = set(re.findall(r"data-widget='([^']+)'", page))
    offered = set(re.findall(r"data-pick='([^']+)'", page))
    assert offered, "the builder offers nothing"
    assert offered == sources, f"offered but absent: {offered - sources}"


def test_the_page_is_self_contained_and_reaches_no_network(three):
    page = console.render_console(console.survey(three))
    assert "http://" not in page.replace("http://www.w3.org", "")
    assert "https://" not in page
    for reach in ("fetch(", "XMLHttpRequest", "WebSocket", "import(", "<script src"):
        assert reach not in page, f"the page reaches out with {reach}"


def test_the_script_keeps_only_presentation_and_only_in_one_place(three):
    """The single storage key, and nothing else the browser can persist. A
    console that wrote a project's state anywhere would be a console with
    authority."""
    page = console.render_console(console.survey(three))
    script = page[page.index("<script>"):]
    assert script.count("localStorage") == 2, "storage is touched somewhere new"
    assert len(set(re.findall(r"localStorage\.[gs]etItem\((\w+)", script))) == 1
    for forbidden in ("sessionStorage", "indexedDB", "document.cookie", "navigator.sendBeacon"):
        assert forbidden not in script


@pytest.mark.parametrize("lens", [l for l in projection.LENSES if l])
def test_a_lens_changes_the_stylesheet_and_nothing_else(three, lens):
    sites = console.survey(three)
    plain = console.render_console(sites)
    themed = console.render_console(sites, theme=lens)

    def body(page):
        return re.sub(r"<style>.*?</style>", "", page, flags=re.S)

    assert body(plain).replace('<html lang="en">', "") == \
        body(themed).replace(f'<html lang="en" data-theme="{lens}">', "").replace(
            f'aria-pressed=\'true\'>{lens}', f'aria-pressed=\'false\'>{lens}').replace(
            "aria-pressed='false'>terminal", "aria-pressed='true'>terminal"), \
        f"the {lens} lens changed something other than the stylesheet"


def test_the_command_line_reads_projects_and_prints_a_page(three, tmp_path):
    roots = [str(r) for _n, r in three[:3]]
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "console.py"), *roots],
                         capture_output=True, text=True, timeout=180)
    assert out.stdout.startswith("<!doctype html>")
    assert out.stdout.rstrip().endswith("</html>")
    assert "Overview" in out.stdout
