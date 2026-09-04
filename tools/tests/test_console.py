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
    """A lens may move every surface and no reading.

    The lens picker's own pressed state is the one thing that legitimately
    differs, so it is normalised away rather than patched around: the previous
    version replaced two particular strings and broke the moment the default
    lens changed, which is a test coupled to a value it is not about.
    """
    sites = console.survey(three)

    def body(page):
        page = re.sub(r"<style>.*?</style>", "", page, flags=re.S)
        page = re.sub(r"<html[^>]*>", "<html>", page)
        page = re.sub(r"(data-lens='[a-z]*' )aria-pressed='(true|false)'", r"\1aria-pressed=''",
                      page)
        return page

    assert body(console.render_console(sites)) == body(console.render_console(sites, theme=lens)), \
        f"the {lens} lens changed something other than the stylesheet"


def test_the_command_line_reads_projects_and_prints_a_page(three, tmp_path):
    roots = [str(r) for _n, r in three[:3]]
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "console.py"), *roots],
                         capture_output=True, text=True, timeout=180)
    assert out.stdout.startswith("<!doctype html>")
    assert out.stdout.rstrip().endswith("</html>")
    assert "Overview" in out.stdout


def test_grouping_identical_readings_loses_none_of_them(three):
    """Twelve projects reading through one unfrozen pack each marked the same
    sentence about it, and the list that exists to be scanned opened with twelve
    copies of one fact. Grouping is a change of shape: every reading and every
    project it belongs to must still be on the page."""
    sites = console.survey(three)
    page = console.render_console(sites)
    block = page[page.index("global:attention"):]
    block = block[:block.index("data-view=", 40)]
    for site in sites:
        for line in (site.view.attention if site.view is not None else []):
            assert projection._escape(line.text) in block, (
                f"{site.name}: the grouped list dropped {line.text!r}")
        assert projection._escape(site.name) in block or site.view is None or \
            not site.view.attention

    shared = [r for r in re.findall(r"<tr data-tone=.*?</tr>", block, re.S)
              if "projects</span>" in r]
    for row in shared:
        count = int(re.search(r"<span class=s>(\d+) projects", row).group(1))
        named = re.search(r"<small>([^<]*)</small>", row).group(1).split(", ")
        assert len(named) == count, (
            f"a grouped row says {count} projects and names {len(named)}")


# --- adversarial: what a project can be called, and where it can point ----------------


@pytest.mark.parametrize("name", [
    "<script>alert(1)</script>", "overview", "project:0", "a & b", '"quoted"',
    "'single'", "../escape", "a\nb", "  ", "é—ü", "x" * 120,
])
def test_a_project_can_be_called_anything_without_reaching_the_page(tmp_path, name):
    """A project's name is a directory name — which is to say, untrusted text
    somebody else chose. It reaches a table cell, a navigation button, a
    `data-goto` attribute and a heading, and none of those may become markup.
    """
    root = tmp_path / "roots" / str(abs(hash(name)))
    _project(root, actionable=("a thing",))
    sites = console.survey([(name, root)])
    page = console.render_console(sites)
    assert "<script>alert" not in page
    assert projection._escape(name) in page or not name.strip()
    # The navigation targets are indices, so a name cannot collide with a view.
    views = re.findall(r"<section class=view data-view='([^']+)'", page)
    assert len(views) == len(set(views)), f"a name collided with a view id: {views}"
    assert "overview" in views and "project:0" in views
    assert page.endswith("</html>")


def test_two_projects_with_one_name_stay_two_projects(tmp_path):
    """A registry may name two different trees the same thing. The console must
    not merge them, and a reader must be able to tell which row is which."""
    first, second = tmp_path / "a" / "api", tmp_path / "b" / "api"
    _project(first, actionable=("first thing",))
    _project(second, actionable=("second thing",))
    sites = console.survey([(None, first), (None, second)])
    assert len(sites) == 2 and not any(s.same_tree_as for s in sites)
    page = console.render_console(sites)
    assert "first thing" in page and "second thing" in page
    views = re.findall(r"<section class=view data-view='(project:[^']+)'", page)
    assert views == ["project:0", "project:1"]
    # and the rows are told apart by something, not left identical
    assert str(first) in page or str(first.parent.name) in page


def test_a_symlinked_root_is_recognised_as_the_tree_it_points_at(tmp_path):
    """Two names for one tree is a fact about the registry however it is
    spelled, and a symlink is the spelling that gets past a string comparison."""
    real = tmp_path / "real"
    _project(real, actionable=("a thing",))
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    sites = console.survey([(None, real), (None, link)])
    assert sites[1].same_tree_as == "real", (
        "a symlink to a project already in the registry was not recognised")
    assert "the same tree as real" in console.render_console(sites)


def test_a_record_that_is_a_directory_is_unreadable_and_not_absent(tmp_path):
    """`CONTINUATION.json` as a directory reads neither as a record nor as no
    record. It must not be the second: *nothing to do* is the one thing an
    unreadable position may never look like."""
    root = tmp_path / "p"
    root.mkdir()
    (root / "CONTINUATION.json").mkdir()
    sites = console.survey([(None, root)])
    assert sites[0].view is not None, "the whole project vanished"
    assert sites[0].state == projection.UNKNOWN, sites[0].state
    page = console.render_console(sites)
    assert "UNKNOWN" in page
    assert sum(sites[0].attention.values()) > 0


# --- the surfaces added in the final UX pass -------------------------------------------


def test_no_reading_any_projection_produced_is_missing_from_the_console(three):
    """**The bound on every presentation change.**

    A visual pass may move a reading, group it, fold it or draw it as a figure.
    It may not lose one. Every line, every label and every unknown that any
    project's projection produced is compared against the whole page — so a
    section quietly dropped in a redesign fails here rather than in front of
    somebody trying to diagnose an incident with it.
    """
    sites = console.survey(three)
    page = console.render_console(sites)
    missing = []
    for site in sites:
        if site.view is None:
            continue
        for panel in site.view.panels:
            if projection._escape(panel.title) not in page:
                missing.append(f"{site.name}: panel {panel.title!r}")
            for line in panel.rows():
                if projection._escape(line.text) not in page:
                    missing.append(f"{site.name}/{panel.title}: {line.text[:60]!r}")
                if line.label and projection._escape(line.label) not in page:
                    missing.append(f"{site.name}/{panel.title}: label {line.label!r}")
            for item in panel.unknown:
                if projection._escape(item) not in page:
                    missing.append(f"{site.name}/{panel.title}: UNKNOWN {item[:60]!r}")
    assert not missing, "the console dropped: " + "; ".join(missing[:6])


def test_only_decoration_and_vocabulary_can_be_folded_away(three):
    """The founder asked for control over what is on screen, with one floor: a
    defect, an unestablished reading, a blocker, a stale reading and a human
    decision have no switch. This reads the declared list and then checks the
    page agrees with it — a `data-optional` nobody declared is a switch nobody
    reviewed."""
    declared = {key for key, _label in console._OPTIONAL_SECTIONS}
    assert declared == {"identity", "footer", "questions"}, declared
    page = console.render_console(console.survey(three))
    used = set(re.findall(r"data-optional='([^']+)'", page))
    assert used, "nothing on the page is marked optional, so the controls do nothing"
    assert used <= declared, f"the page marks {used - declared} optional and nothing declared it"


def test_folding_a_section_moves_a_marked_line_and_never_removes_one(three):
    """The real rule, and it is not *a foldable section carries no finding*.

    The identity panel carries one whenever the pack is unfrozen. What makes it
    safe to fold is that everything urgent inside it is ALSO in the attention
    strip, which has no switch — so folding changes where a marked line is, not
    whether it is on the page.

    **The state vocabulary failed this and is no longer foldable.** `attention`
    deliberately skips legend panels, so `SILENT_IDLE: THIS ONE` is marked BAD
    there and hoisted nowhere; folding it away would have taken the mark with
    it. Found by writing the rule down and checking the page against it.
    """
    sites = console.survey(three)
    for site in sites:
        if site.view is None:
            continue
        hoisted = " ".join(line.text for line in site.view.attention)
        for panel in site.view.panels:
            if panel.group != "identity" or panel.legend:
                continue
            for line in panel.rows():
                if line.tone in (projection.Tone.BAD, projection.Tone.WARN,
                                 projection.Tone.UNKNOWN):
                    assert line.text in hoisted, (
                        f"{site.name}: folding {panel.title!r} would take {line.text[:60]!r} "
                        f"off the page")
            for item in panel.unknown:
                assert item in hoisted, (
                    f"{site.name}: folding {panel.title!r} would take an UNKNOWN off the page")


def test_the_state_vocabulary_is_not_foldable(three):
    """The half that would go quiet if somebody added it back to the list."""
    page = console.render_console(console.survey(three))
    assert "data-optional='legend'" not in page
    assert "legend" not in {key for key, _label in console._OPTIONAL_SECTIONS}


@pytest.mark.parametrize("token", [t for t, _l, _k in console._COLOUR_TOKENS]
                                  + [t for t, _l in console._SEMANTIC_TOKENS]
                                  + [t for t, *_r in console._SIZE_TOKENS])
def test_every_settable_token_has_a_control_and_a_way_back(three, token):
    """A token the script can set with no control is a setting nobody can reach;
    a control with no × is one nobody can undo."""
    page = console.render_console(console.survey(three))
    assert f"data-token='{token}'" in page
    assert f"data-clear='{token}'" in page


@pytest.mark.parametrize("token,low,high", [(t, lo, hi) for t, _l, lo, hi, *_r
                                            in console._SIZE_TOKENS])
def test_every_size_control_declares_the_range_it_stays_usable_in(three, token, low, high):
    """The bounds are the point of the settings panel. A range with no floor
    would let an operator set a state to nothing and then not find it."""
    page = console.render_console(console.survey(three))
    control = re.search(rf"<input type=range data-token='{token}'[^>]*>", page)
    assert control, token
    assert f"min='{low}'" in control.group(0) and f"max='{high}'" in control.group(0)
    assert low > 0 or token in ("pad-y", "gap"), f"{token} may be set to nothing"


def test_the_help_explains_every_state_the_reading_can_report(three):
    """A vocabulary a reader meets on the page and cannot look up is a
    vocabulary that gets guessed at."""
    import continuation as _c

    explained = {name for name, _text in console._STATES}
    page = console.render_console(console.survey(three))
    for state in (_c.State.WAITING_ON_IDENTIFIED_JOB, _c.State.COMPLETED_NOT_CONSUMED,
                  _c.State.ACTIONABLE_WORK_READY, _c.State.BLOCKED_ON_HUMAN,
                  _c.State.BLOCKED_ON_CAPACITY, _c.State.RECOVERY_REQUIRED,
                  _c.State.SILENT_IDLE, _c.State.TERMINAL):
        assert state in explained, f"the help does not explain {state}"
    assert {"STALLED", "UNKNOWN"} <= explained
    for name, text in console._STATES:
        assert projection._escape(text[:50]) in page, name


def test_every_question_the_help_answers_names_a_view_that_exists(three):
    """A *where to look* that points nowhere is worse than no answer."""
    views = {name for name, _t, _q in console._VIEWS}
    for question, _answer, where in console._QUESTIONS:
        assert where in views, f"{question!r} points at {where!r}, which is not a view"


def test_the_quick_find_reaches_only_places_that_exist(three):
    """It is a navigator, not a command surface: every entry's only verb is
    *go there*, and everywhere it can go is a view on this page."""
    page = console.render_console(console.survey(three))
    finder = page[page.index("<div class=finder"):]
    finder = finder[:finder.index("</ul>")]
    targets = set(re.findall(r"data-goto='([^']+)'", finder))
    views = set(re.findall(r"<section class=view data-view='([^']+)'", page))
    assert targets, "quick find offers nothing"
    assert targets <= views, f"quick find points at {targets - views}"
    assert len(re.findall(r"data-find='", finder)) >= 20


def test_the_control_room_and_all_systems_are_recomposed_and_not_concatenated(three):
    """Both are their own hierarchy. The check that they are not a copy of the
    other views is that they carry sections those views do not: a situation
    banner in one, an anchored index in the other."""
    page = console.render_console(console.survey(three))
    room = page[page.index("data-view='control'"):page.index("data-view='projects'")]
    assert "the situation" in room and room.count("<section class=setgroup") >= 6
    assert "what happens next, per project" in room
    everything = page[page.index("data-view='all'"):page.index("data-view='control'")]
    assert len(re.findall(r"data-anchor-target='all-[a-z]+'", everything)) >= 10
    assert len(re.findall(r"data-anchor='all-[a-z]+'", everything)) >= 10


def test_the_overview_offers_three_densities_and_hides_no_project_in_any(three):
    """Density chooses how much of a row is drawn. It may never choose which
    projects there are."""
    page = console.render_console(console.survey(three))
    for mode in ("minimal", "balanced", "full"):
        assert f"data-od='{mode}'" in page
    # THE OVERVIEW'S OWN TABLE. The project matrix is drawn in three views, so
    # counting rows across the page counts it three times — which is a fact
    # about the page and not about the density modes.
    overview = page[page.index("data-view='overview'"):page.index("data-view='all'")]
    rows = re.findall(r"<tr data-project='\d+'", overview)
    assert len(rows) == len(console.survey(three)), f"{len(rows)} rows"
    assert '[data-od="minimal"] tr' not in page, "a density rule reaches a whole row"
