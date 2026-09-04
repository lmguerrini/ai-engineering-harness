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

import activity
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
    safe to fold is that everything urgent inside it is ALSO somewhere with no
    switch — so folding changes where a marked line is, not whether it is on
    the page.

    **Checked against the rendered page, with the foldable sections removed.**
    The first version compared panel lines with `view.attention` and never
    looked at any HTML: an independent reader deleted three renderers and it
    still passed while the marked line was absent from the page it describes.
    """
    sites = console.survey(three)
    page = console.render_console(sites)
    #: The page as it is with every foldable section folded away.
    folded = re.sub(r"<section[^>]*data-optional='[^']*'.*?</section>", "", page, flags=re.S)
    folded = re.sub(r"<p class=vq data-optional='questions'>.*?</p>", "", folded, flags=re.S)
    folded = re.sub(r"<footer data-optional='footer'>.*?</footer>", "", folded, flags=re.S)
    missing = []
    for site in sites:
        if site.view is None:
            continue
        for panel in site.view.panels:
            if panel.group != "identity" or panel.legend:
                continue
            for line in panel.rows():
                if line.tone in (projection.Tone.BAD, projection.Tone.WARN,
                                 projection.Tone.UNKNOWN):
                    if projection._escape(line.text) not in folded:
                        missing.append(f"{site.name}: {line.text[:60]}")
            for item in panel.unknown:
                if projection._escape(item) not in folded:
                    missing.append(f"{site.name}: UNKNOWN {item[:60]}")
    assert not missing, ("folding the optional sections took these off the page: "
                         + "; ".join(missing[:4]))


def test_the_folding_check_would_notice_a_renderer_that_stopped_hoisting(three):
    """The bound, by mutating the page the check reads.

    Take one long marked line from an identity panel, delete every copy of it
    that is NOT inside a foldable section, fold, and the check must find it
    gone. Without this, the check above is a loop over a page that happens to
    be right — which is exactly how it passed while three renderers were
    missing.
    """
    sites = console.survey(three)
    page = console.render_console(sites)
    marked = [line.text for s in sites if s.view is not None
              for panel in s.view.panels
              if panel.group == "identity" and not panel.legend
              for line in panel.rows()
              if line.tone in (projection.Tone.BAD, projection.Tone.WARN,
                               projection.Tone.UNKNOWN) and len(line.text) > 40]
    marked += [item for s in sites if s.view is not None
               for panel in s.view.panels
               if panel.group == "identity" and not panel.legend
               for item in panel.unknown if len(item) > 40]
    assert marked, "the fixture has no long marked identity reading, so this proves nothing"
    subject = projection._escape(marked[0])

    #: Everything the identity panels themselves hold, kept aside; the rest of
    #: the page loses the line, which is what *nothing else repeats it* means.
    keep = re.findall(r"<section[^>]*data-optional='identity'.*?</section>", page, re.S)
    elsewhere = re.sub(r"<section[^>]*data-optional='identity'.*?</section>", "\x00", page,
                       flags=re.S).replace(subject, "")
    crippled = elsewhere
    for block in keep:
        crippled = crippled.replace("\x00", block, 1)

    folded = re.sub(r"<section[^>]*data-optional='identity'.*?</section>", "", crippled,
                    flags=re.S)
    assert subject in crippled, "the mutation removed the line from its own panel too"
    assert subject not in folded, (
        "with nothing outside the identity panels repeating it, folding still appears to keep "
        "the line — the check cannot fail")


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
    assert "the situation" in room and room.count("<section class='setgroup") >= 7
    # Each section leads with a summary, which is what makes it a recomposition
    # rather than the other views stacked: the tables here are the notable rows.
    assert room.count("<div class=summary>") >= 4, "the sections do not summarise"
    for question in ("needs a person or a look", "every project", "workers", "durable output",
                     "audits", "capacity", "release and safety"):
        assert question in room, question
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
    # THE STYLESHEET, not one literal selector. An independent reader appended
    # `[data-od="minimal"] #overview-table tbody tr{display:none}` and the check
    # passed while minimal mode hid every project. No density rule may reach a
    # row, a body or a table at all.
    style = projection._STYLE + console._SHELL_STYLE
    for rule in re.findall(r"\[data-od=\"[a-z]+\"\][^{]*\{[^}]*\}", style):
        selector = rule.split("{")[0]
        assert not re.search(r"\b(tr|tbody|table)\b|#overview-table", selector), (
            f"a density rule reaches whole rows: {rule.strip()}")
    for rule in re.findall(r"\[data-ad=\"[a-z]+\"\][^{]*\{[^}]*\}", style):
        selector = rule.split("{")[0]
        assert not re.search(r"\b(tr|tbody|table)\b", selector), (
            f"a depth rule reaches whole rows: {rule.strip()}")


# --- the instruments: a picture may transform a value, never derive another one -------


def test_every_instrument_counts_only_rows_the_page_is_showing(three):
    """**Source agreement.** A distribution is a tally of the same figures the
    tables list — not a second reading, not a computed condition. Each one is
    recomputed here from the projections and compared against what the bar
    says, so a chart that drifted from its own data fails rather than
    reassuring somebody."""
    sites = console.survey(three)
    page = console.render_console(sites)
    jobs = [c for s in sites for c in s.figures("job")]
    audits = [c for s in sites for c in s.figures("audit")]
    pools = [c for s in sites for c in s.figures("capacity")]

    #: THE ROWS THE PAGE LISTS, not the collection the instrument reads. Both
    #: sides came from `figures("audit")`, so an audit missing its kind was
    #: absent from the table AND from the tally, and the comparison agreed with
    #: itself. An independent reader found exactly that.
    def listed(widget):
        """How many rows the page actually lists in one widget."""
        block = page[page.index(f"data-widget='{widget}'"):]
        block = block[:block.index("</section>")]
        return len(re.findall(r"<tr data-tone=", block))

    def counts(html):
        return {name.strip(): int(n) for name, n in
                re.findall(r"<i></i>([^<]+?)\s*<b>(\d+)</b>", html)}   # `·` is not a count

    workers = counts(console._worker_states(sites))
    assert workers["complete, unconsumed"] == len([c for c in jobs if c.value == "COMPLETE"])
    assert workers["nobody can observe"] == len([c for c in jobs
                                                 if c.value == projection.UNKNOWN])
    assert sum(v for k, v in workers.items()
               if k != "stalled — two readings needed") == len(jobs)

    audit = counts(console._audit_shape(sites))
    placed = (audit["about the candidate"] + audit["about another tree"]
              + audit["cannot be compared"])
    assert placed == len(audits), f"{placed} audits in the tally, {len(audits)} figures"
    assert placed == listed("global:audits"), (
        "the tally and the audits table disagree about how many audits there are")
    assert audit["about another tree"] == len([c for c in audits
                                               if c.tone == projection.Tone.BAD])

    capacity = counts(console._capacity_shape(sites))
    assert capacity["measured"] + capacity["unmeasured"] == len(pools)
    assert capacity["measured"] + capacity["unmeasured"] == listed("global:capacity"), (
        "the tally and the capacity table disagree about how many pools there are")

    states = counts(console._project_states(sites))
    assert sum(states.values()) == len(sites), "a project is missing from the distribution"

    attention = counts(console._attention_shape(sites))
    assert sum(attention.values()) == sum(sum(s.attention.values()) for s in sites)


def test_a_stall_is_declined_in_the_instrument_too(three):
    """One reading cannot establish a stall, so the tally says so rather than
    saying none. A `0` there would be an answer this page cannot give."""
    html = console._worker_states(console.survey(three))
    assert "stalled — two readings needed" in html
    #: `·`, not `0`. A zero there is an answer, from a page that has just said
    #: it cannot give one.
    assert re.search(r"stalled — two readings needed\s*<b>·</b>", html), html
    assert not re.search(r"stalled[^<]*<b>0</b>", html)


def test_an_unmeasured_window_is_a_band_and_never_an_empty_bar(three):
    """UNKNOWN → empty, UNKNOWN → 0%, UNKNOWN → healthy: three ways to say
    *fine* about something nobody measured. It gets its own segment in its own
    tone."""
    sites = console.survey(three)
    html = console._capacity_shape(sites)
    unmeasured = len([c for s in sites for c in s.figures("capacity")
                      if c.tone == projection.Tone.UNKNOWN])
    assert unmeasured, "the fixture measures every window, so this proves nothing"
    #: THE SEGMENT, not the word. Replacing the count with zero left the legend
    #: text and the class in place and the check passed — an independent reader
    #: did exactly that.
    assert re.search(rf"unmeasured\s*<b>{unmeasured}</b>", html), html
    bar = re.search(r"<div class=dist>(.*?)</div>", html, re.S)
    assert bar and "class='unknown'" in bar.group(1), (
        "an unmeasured window has no segment in the bar")


@pytest.mark.parametrize("used,ceiling,drawn", [
    (0, 8, True), (1, 8, True), (8, 8, True), (9, 8, True), (10 ** 9, 8, True),
    (0, 0, False), (5, 0, False), (5, -1, False), (-1, 8, False),
    (5, float("inf"), False), (float("inf"), 8, False), (float("nan"), 8, False),
    (5, float("nan"), False),
])
def test_a_meter_survives_every_shape_of_fraction(tmp_path, used, ceiling, drawn):
    """Zero, one, over, enormous, no denominator, a negative one. No division by
    nothing, no NaN, no bar wider than its track, and the exact value said in
    every case."""
    cell = projection.Cell("cycles", f"{used}/{ceiling}", share=(used, ceiling),
                           sense="consumption")
    assert (cell.share is not None) == drawn, f"{used}/{ceiling}"
    html = projection._cell(cell, "fact")
    assert f"{used}/{ceiling}" in html, "the exact value is not beside the picture"
    if drawn:
        width = float(re.search(r"width:([0-9.]+)%", html).group(1))
        assert 0.0 <= width <= 100.0, width
    else:
        assert "class='meter" not in html


def test_a_spent_budget_and_complete_coverage_are_not_drawn_the_same(tmp_path):
    """**Both are full, and they mean opposite things.**

    A console that colours an exhausted budget the way it colours complete
    coverage is telling an operator that running out is an achievement. The
    sense decides the bar, and this is the test that says the two senses cannot
    be merged.
    """
    spent = projection._cell(projection.Cell("cycles", "9/9", projection.Tone.WARN,
                                             share=(9, 9), sense="consumption"), "fact")
    covered = projection._cell(projection.Cell("chunks", "9/9", projection.Tone.GOOD,
                                               share=(9, 9), sense="coverage"), "fact")
    assert re.search(r"<i class='bad'", spent), "a spent budget is not marked as one"
    assert re.search(r"<i class='good'", covered), "complete coverage is not marked as one"
    assert spent != covered


@pytest.mark.parametrize("sense,at,expected", [
    ("consumption", (9, 9), "bad"), ("consumption", (7, 8), "warn"),
    ("coverage", (4, 4), "good"), ("coverage", (1, 4), "plain"),
    ("age", (3600, 3600), "warn"), ("age", (60, 3600), "plain"),
    ("deadline", (3600, 3600), "bad"), ("deadline", (3550, 3600), "warn"),
    ("deadline", (60, 3600), "plain"),
])
def test_each_sense_colours_its_bar_by_what_being_full_means(sense, at, expected):
    html = projection._cell(projection.Cell("x", "v", share=at, sense=sense), "fact")
    assert f"<i class='{expected}'" in html, html


def test_an_instrument_never_becomes_the_only_place_a_number_is(three):
    """A picture may be the fastest way to a number. It may not be the only
    way — a reader who distrusts a bar, or cannot see it, reads the count."""
    sites = console.survey(three)
    for html in (console._project_states(sites), console._worker_states(sites),
                 console._attention_shape(sites), console._audit_shape(sites),
                 console._capacity_shape(sites), console._freshness_shape(sites)):
        assert "<b>" in html, "a distribution shows a bar and no counts"
        bar = re.search(r"<div class=dist>(.*?)</div>", html, re.S)
        if bar:
            assert len(re.findall(r"<b>\d+</b>", html)) >= len(re.findall(r"<span", bar.group(1)))


def test_the_instruments_read_the_same_lens_tokens_as_everything_else():
    """A chart with its own palette is a chart that stops meaning what the rest
    of the page means when a lens changes."""
    style = projection._STYLE + console._SHELL_STYLE
    block = style[style.index(".dist{"):style.index(".legend b{")]
    for hard in re.findall(r"#[0-9a-fA-F]{3,6}", block):
        raise AssertionError(f"an instrument hard-codes {hard} instead of a token")
    flat = style.replace(" ", "")
    for tone in ("bad", "warn", "unknown", "good"):
        assert f".dist.{tone}{{background:var(--{tone})}}" in flat, tone


def test_the_oldest_reading_is_the_oldest_and_not_the_longest_string(tmp_path):
    """**Found by an independent reader.** The global bar compared the formatted
    ages as text, so `9 min ago` sorted above `120 min ago` and the summary of
    how stale the page is reported the freshest record on it — a stale reading
    claiming freshness, in the one line a reader glances at."""
    from datetime import datetime, timedelta, timezone

    def aged(name, minutes):
        root = tmp_path / name
        root.mkdir()
        when = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        _continuation.save(_continuation.ContinuationRecord(
            capability="c", updated_at=when, actionable=("x",)), root / "CONTINUATION.json")
        return (None, root)

    sites = console.survey([aged("fresh", 9), aged("old", 120)])
    bar = console._global_bar(sites, "")
    assert "120 min ago" in bar, bar
    assert ">9 min ago<" not in bar, "the bar reports the freshest record as the oldest"


def test_a_reading_that_cannot_be_dated_makes_the_oldest_unknown(tmp_path):
    """The other half. With one undatable record the oldest cannot be
    established, and a large number would be a claim about records this page
    could not read."""
    good = tmp_path / "good"
    good.mkdir()
    _continuation.save(_continuation.ContinuationRecord(
        capability="c", updated_at=_continuation.now(), actionable=("x",)),
        good / "CONTINUATION.json")
    sites = console.survey([(None, good), (None, tmp_path / "gone")])
    bar = console._global_bar(sites, "")
    assert "UNKNOWN" in bar, bar


#: The colour rule, in Python, so the portable suite can decide whether a value
#: SHOULD be refused. Whether the page actually refuses it is a different
#: question, answered by driving a browser — see the note on the third test.
def _would_refuse(token, value, tokens):
    from test_projection import _contrast, _hue_and_luminance

    surfaces = [tokens[name] for name in ("panel", "panel-2", "ground")]
    meanings = [tokens[name] for name in ("bad", "warn", "unknown", "good")]
    if token in ("ink", "dim", "faint", "accent", "bad", "warn", "unknown", "good"):
        if any(_contrast(value, surface) < 4.5 for surface in surfaces):
            return "unreadable on the panels it is drawn on"
    if token in ("ground", "panel", "panel-2", "panel-3", "select"):
        drawn = [tokens["ink"], tokens["dim"], tokens["accent"], *meanings]
        if any(_contrast(value, colour) < 4.5 for colour in drawn):
            return "what is drawn on it would be unreadable"
    if token in ("bad", "warn", "unknown", "good", "accent"):
        for name in ("bad", "warn", "unknown", "good", "accent"):
            if name == token:
                continue
            hue_a, lum_a = _hue_and_luminance(value)
            hue_b, lum_b = _hue_and_luminance(tokens[name])
            brighter = (max(lum_a, lum_b) + 0.05) / (min(lum_a, lum_b) + 0.05)
            if hue_a is None or hue_b is None:
                apart = brighter >= 1.6
            else:
                turn = abs(hue_a - hue_b)
                apart = min(turn, 360 - turn) >= 22 or brighter >= 1.6
            if not apart:
                return f"a reader could not tell it from {name}"
    return ""


@pytest.mark.parametrize("token,value,why", [
    ("panel", "#333333", "a surface the state colours cannot be read on"),
    ("accent", "#f2635c", "an accent that is exactly the defect red"),
    ("ground", "#808080", "a ground nothing readable sits on"),
    ("ink", "#0a0a0a", "text nobody could read on the panel it sits on"),
    ("bad", "#c9821f", "a defect colour a reader could not tell from a warning"),
])
def test_a_setting_a_reader_could_not_use_is_one_the_rule_rejects(token, value, why):
    """**Two of these were accepted, and the test meant to catch them searched
    the script for strings.**

    An independent reader changed `if (why)` to `if (false && why)` — turning
    the refusal off entirely — and all three cases still passed, because a grep
    for a phrase is not a check on behaviour.

    This decides the RULE, in Python, against the lens the page actually draws.
    Whether the page enforces it is a separate question with a separate answer:
    the browser driver sets each of these through the real control and asserts
    the value is not applied and a refusal is shown. Neither test is the whole
    property, and saying which is which is the honest part.
    """
    from test_projection import _theme_tokens

    assert _would_refuse(token, value, _theme_tokens("")), f"{why} is not rejected by the rule"


@pytest.mark.parametrize("token,value", [
    ("accent", "#39c0ff"), ("ink", "#f5f2ed"), ("panel", "#0e0d0c"), ("bad", "#ff5a4d"),
])
def test_a_setting_a_reader_could_use_is_one_the_rule_accepts(token, value):
    """The other half. A rule that refuses everything is a settings panel nobody
    can use, and it would pass the test above."""
    from test_projection import _theme_tokens

    assert not _would_refuse(token, value, _theme_tokens("")), f"{token}={value} is refused"


def test_the_page_wires_the_rule_to_the_control_and_not_only_to_a_comment():
    """What the portable suite cannot do, named rather than implied.

    This asserts the enforcement path exists and is reached from the control;
    the browser driver asserts it works, by setting each value through the real
    input and reading back what the page draws. A machine with no browser gets
    the first; the release evidence carries both.
    """
    import console as _console

    script = _console._SCRIPT
    assert "function objection(" in script
    assert "if (why) { refuse(token, why); applyOne(token, null); }" in script, (
        "the refusal path is not wired to the control")
    assert "['ink', 'dim', 'accent'].concat(MEANINGS)" in script, (
        "a surface is not checked against the state colours drawn on it")
    assert "kind === 'semantic' || token === 'accent'" in script, (
        "the accent is not put through the separability check")


# --- the two histories, on the page ------------------------------------------------------


@pytest.fixture
def with_repository(tmp_path, three):
    """A registry where one project's contract points at a real repository."""
    import subprocess

    repo = tmp_path / "code"
    repo.mkdir()
    for command in (("init", "--quiet", "--initial-branch", "main"),
                    ("config", "user.name", "T"), ("config", "user.email", "t@e.invalid"),
                    ("config", "commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(repo), *command], check=True, capture_output=True)
    for n in range(4):
        (repo / f"f{n}.txt").write_text(str(n))
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", f"c{n}"], check=True,
                       capture_output=True)
    root = three[0][1]
    (root / "PROJECT.yaml").write_text(
        'project:\n  name: "a"\n  publication_intent: "internal"\n'
        f'  repo_path: "{repo}"\n'
        'pack:\n  root_path: "%s"\n  version_adopted: "2.3.0"\n'
        '  state_adopted: "IN_PROGRESS"\n  adopted_at: "2026-09-04"\n'
        '  adoption_boundary: "at a capability boundary"\nadapters: []\n'
        % Path(__file__).resolve().parents[2], encoding="utf-8")
    return three, repo


@pytest.fixture
def with_pushed_repository(tmp_path, three):
    """A project whose repository has a remote that has actually been observed,
    with some commits pushed and some not."""
    import subprocess

    repo = tmp_path / "pushed"
    bare = tmp_path / "origin.git"
    repo.mkdir()
    bare.mkdir()
    subprocess.run(["git", "-C", str(bare), "init", "--bare", "--quiet"], check=True,
                   capture_output=True)
    for command in (("init", "--quiet", "--initial-branch", "main"),
                    ("config", "user.name", "T"), ("config", "user.email", "t@e.invalid"),
                    ("config", "commit.gpgsign", "false"),
                    ("remote", "add", "origin", str(bare))):
        subprocess.run(["git", "-C", str(repo), *command], check=True, capture_output=True)
    for n in range(3):
        (repo / f"p{n}.txt").write_text(str(n))
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", f"p{n}"], check=True,
                       capture_output=True)
    subprocess.run(["git", "-C", str(repo), "push", "--quiet", "origin", "main"], check=True,
                   capture_output=True)
    for n in range(2):
        (repo / f"a{n}.txt").write_text(str(n))
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", f"a{n}"], check=True,
                       capture_output=True)
    root = three[0][1]
    (root / "PROJECT.yaml").write_text(
        'project:\n  name: "a"\n  publication_intent: "internal"\n'
        f'  repo_path: "{repo}"\n'
        'pack:\n  root_path: "%s"\n  version_adopted: "2.3.0"\n'
        '  state_adopted: "IN_PROGRESS"\n  adopted_at: "2026-09-04"\n'
        '  adoption_boundary: "at a capability boundary"\nadapters: []\n'
        % Path(__file__).resolve().parents[2], encoding="utf-8")
    return three, repo


def test_a_repository_that_will_not_open_shows_no_totals_on_the_page(three):
    """`0 local, 0 only here` about a repository nobody could read is an
    established zero where there is a question."""
    page = console.render_console(console.survey(three))
    block = page[page.index("data-view='history'"):]
    block = block[:block.index("data-view=", 40)]
    rows = re.findall(r"<tr>(?:(?!</tr>).)*is not a git repository.*?</tr>", block, re.S)
    assert rows, "the fixture has no unreadable repository"
    for row in rows:
        cells = re.findall(r"data-label='(local|only here|represented)'[^>]*>(.*?)</td>", row)
        for label, body in cells:
            assert "UNKNOWN" in body, f"{label} reads {body!r} for a repository nobody read"


def test_two_entries_for_one_repository_are_counted_once_and_said_so(tmp_path, three):
    """The calendar deduplicated and the table did not, so the same page gave
    two answers to *how many commits are there*."""
    import subprocess

    repo = tmp_path / "shared"
    repo.mkdir()
    for command in (("init", "--quiet", "--initial-branch", "main"),
                    ("config", "user.name", "T"), ("config", "user.email", "t@e.invalid"),
                    ("config", "commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(repo), *command], check=True, capture_output=True)
    (repo / "one.txt").write_text("1")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "one"], check=True,
                   capture_output=True)
    contract = ('project:\n  name: "%s"\n  publication_intent: "internal"\n'
                f'  repo_path: "{repo}"\n'
                'pack:\n  root_path: "%s"\n  version_adopted: "2.3.0"\n'
                '  state_adopted: "IN_PROGRESS"\n  adopted_at: "2026-09-04"\n'
                '  adoption_boundary: "at a capability boundary"\nadapters: []\n')
    for at in (0, 1):
        root = three[at][1]
        (root / "PROJECT.yaml").write_text(
            contract % (f"p{at}", Path(__file__).resolve().parents[2]), encoding="utf-8")
    page = console.render_console(console.survey(three))
    block = page[page.index("data-view='history'"):]
    block = block[:block.index("data-view=", 40)]
    stated = int(re.search(r"<i>local commits</i><em>(\d+)</em>", block).group(1))
    assert stated == 1, f"the summary counted the same repository twice: {stated}"
    assert "the same repository as a row above" in block, (
        "the table lists a duplicate without saying it is one")


def test_the_calendar_and_the_summary_state_the_same_total(with_repository):
    """**Source agreement.** The cells carry per-day counts and the summary
    carries a total; a page where they disagree is a page with two answers."""
    three, _repo = with_repository
    sites = console.survey(three)
    page = console.render_console(sites)
    block = page[page.index("data-view='history'"):]
    block = block[:block.index("data-view=", 40)]
    per_day = sum(int(n) for n in re.findall(r"data-local='(\d+)'", block)) // 3  # three modes
    stated = re.search(r"<i>local commits</i><em>(\d+)</em>", block)
    assert stated, "the summary states no local total"
    assert per_day == int(stated.group(1)), (
        f"{per_day} in the cells and {stated.group(1)} in the summary")


def test_every_calendar_cell_carries_its_exact_counts(with_repository):
    """A picture is never the only place a number is: the counts are in the
    cell's own attributes and in the label a screen reader gets."""
    three, _repo = with_repository
    page = console.render_console(console.survey(three))
    cells = re.findall(r"<i class='cell[^>]*data-day='[^']+'[^>]*>", page)
    assert cells, "the calendar has no cells"
    for cell in cells[:40]:
        assert "data-local='" in cell and "data-remote='" in cell and "data-only='" in cell
        assert "aria-label='" in cell and "local" in cell


def test_the_history_view_states_the_zone_its_days_are_counted_in(with_repository):
    three, _repo = with_repository
    page = console.render_console(console.survey(three))
    assert f"days are {activity.TIMEZONE}" in page
    assert "belongs to its UTC day" in page


def test_a_repository_the_console_cannot_read_says_which_of_the_two_it_is(three):
    """*Not a repository* and *a repository that would not open* are different
    answers, and `git invocation failed` was neither."""
    page = console.render_console(console.survey(three))
    assert "is not a git repository" in page
    assert "git invocation failed" not in page


def test_the_control_room_carries_recent_activity_and_not_a_year(with_repository):
    """A year of calendar in a screen somebody leaves up is a year of calendar
    nobody reads."""
    three, _repo = with_repository
    page = console.render_console(console.survey(three))
    room = page[page.index("data-view='control'"):page.index("data-view='projects'")]
    assert "global:viz-recent-activity" in room
    assert "data-day=" not in room, "the control room carries a dated calendar"
    assert "commits in 10 weeks" in room


def test_the_history_never_adds_local_and_remote_together(with_pushed_repository):
    """The relationship, on the page. A summary that added them would show every
    push as two pieces of work.

    **With a remote that has actually been observed.** The first version used a
    repository with no remote, so `represented` was UNKNOWN and the arithmetic
    was never exercised: an independent reader made a mutant that adds the two
    together whenever a remote IS observed, and the test passed.
    """
    three, _repo = with_pushed_repository
    sites = console.survey(three)
    page = console.render_console(sites)
    block = page[page.index("data-view='history'"):]
    block = block[:block.index("data-view=", 40)]
    local = int(re.search(r"<i>local commits</i><em>(\d+)</em>", block).group(1))
    only = int(re.search(r"<i>only here</i><em>(\d+)</em>", block).group(1))
    remote = re.search(r"<i>represented by the remote</i><em>([^<]+)</em>", block).group(1)
    assert only <= local
    assert remote.isdigit(), f"the fixture's remote was never observed: {remote}"
    assert int(remote) > 0, "the fixture pushed nothing, so nothing is represented"
    assert int(remote) + only == local, f"{remote} + {only} != {local}"
    assert int(remote) <= local, "more commits are represented than exist"
    assert "a subset of the local total, never added to it" in block


def test_no_word_in_the_console_scores_the_work(with_repository):
    """A hard one. Activity is evidence that commits happened; a console that
    called it productivity would be making a claim nobody can support."""
    three, _repo = with_repository
    page = console.render_console(console.survey(three)).lower()
    for word in ("productivity", "velocity", "performance score", "quality score",
                 "developer score", "good day", "streak"):
        assert word not in page, f"the console says {word!r}"
    assert "not pace, not quality" in page


def _band(page: str) -> list:
    """Every instrument in the control room's band, as (key, wide, body).

    Sliced by the instruments themselves rather than by guessing where the band
    ends: the first version bounded it with a selector the page does not always
    contain and silently read half the document.
    """
    import re

    room = page[page.index("data-view='control'"):page.index("data-view='projects'")]
    band = room[room.index("<div class=instruments>"):]
    found = re.findall(
        r"<section class=setgroup data-widget='global:viz-([a-z-]+)'[^>]*?"
        r"(\sdata-wide=1)?>(.*?)</section>", band, re.S)
    assert found, "the control room drew no instrument band"
    return found


def test_an_instrument_that_draws_rows_or_a_strip_is_given_room_for_them(with_repository):
    """The band's columns are sized for a legend, and two of its instruments
    are not legends.

    At 3840 the event instrument got one column of about 385 pixels and the
    browser broke words down the middle of themselves — `readi/ng writt/en`.
    Nothing that reads source text could see it; the ultrawide screenshot
    could. The repair marks an instrument wide **from what it rendered**, so
    the eleventh instrument gets the same treatment without anybody
    remembering to add it to a list.
    """
    three, _repo = with_repository
    page = console.render_console(console.survey(three))

    drawn, legends = [], []
    for key, wide, body in _band(page):
        needs = ("<table" in body or "class=rows" in body or "class='rows" in body
                 or "class=calendar" in body or "class='calendar" in body)
        (drawn if needs else legends).append(key)
        assert bool(wide) == needs, (
            f"instrument {key!r} renders {'rows or a strip' if needs else 'a legend'} "
            f"and is marked {'wide' if wide else 'narrow'}")

    # NOT VACUOUS IN EITHER DIRECTION: if every instrument were a legend the
    # assertion above would hold while proving nothing, and if every one were
    # wide the rule would just be the band's own column width.
    assert drawn, "no instrument in the band draws rows or a strip"
    assert legends, "every instrument in the band draws rows or a strip"

    rule = "@media (min-width:1500px){.instruments>[data-wide]{grid-column:span 2}}"
    assert rule in console._SHELL_STYLE, "nothing gives a wide instrument its second column"
    assert rule in page, "the rule is declared and never delivered to the page"


def test_a_band_cell_never_carries_a_timestamp_it_cannot_print_on_one_line(with_repository):
    """`2026-09-04T14:27` in a 385-pixel column is four lines with a `T` in the
    middle of one of them. The timeline and the day inspector show the whole
    stamp, because they have the width for it."""
    import re

    three, _repo = with_repository
    page = console.render_console(console.survey(three))
    band = "".join(body for _key, _wide, body in _band(page))

    stamps = re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", band)
    assert not stamps, f"the instrument band prints full ISO timestamps: {stamps[:3]}"
    assert re.search(r"class='nw t'>\d{2}-\d{2} \d{2}:\d{2}<", band), \
        "the band prints no event time at all, so this proves nothing"


def test_the_clock_returns_what_it_was_given_when_it_is_not_a_timestamp():
    """Guessing at the shape of a string is how a reading becomes a decoration."""
    assert console._clock("2026-09-04T14:27:55.121372+00:00") == "09-04 14:27"
    assert console._clock("") == ""
    assert console._clock("not a time") == "not a time"
    assert console._clock("2026-09-04 14:27:55") == "2026-09-04 14:27"


def test_the_history_offers_a_period_of_the_readers_own_choosing(with_repository):
    """Four scales answer *the last N days*. A range answers *those days*, and
    the two must not be able to disagree about which is in force.

    The document's part of that is what this asserts: both bounds exist, they
    are dates rather than free text, the page carries a place to say which
    window it is showing, and every event the timeline could narrow carries the
    UTC day it would be narrowed by. The behaviour itself is a browser
    property, exercised in `rp2.3-session/SMOKE-REPORT.md`.
    """
    import re

    three, _repo = with_repository
    page = console.render_console(console.survey(three))
    view = page[page.index("data-view='history'"):]
    view = view[:view.index("<section class=view")] if "<section class=view" in view else view

    assert "<input type=date id=history-from" in view, "no lower bound"
    assert "<input type=date id=history-to" in view, "no upper bound"
    assert "id=history-period" in view, "nothing says which window is in force"
    for scale in ("year", "month", "week", "day"):
        assert f"data-scale='{scale}'" in view, f"the {scale} scale is gone"

    rows = re.findall(r"<tr data-tone='[a-z]+' data-kind='[^']*' [^>]*data-day='([^']*)'", view)
    assert rows, "the timeline has no rows, so this proves nothing about narrowing them"
    dated = [day for day in rows if day]
    assert dated, "no event carries a day, so no period could ever narrow one"
    for day in dated:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", day), f"{day!r} is not a UTC day"


def test_a_project_page_carries_its_own_two_histories_and_nobody_elses(with_repository,
                                                                       tmp_path):
    """The history view answers *across every project*. A project's own page has
    to answer *this one*, or a reader has to leave it to find out when its code
    last changed.

    **Two repositories of different sizes**, because with one the aggregate and
    the project agree and a band drawn from every site passes anyway. That
    mutant survived the first version of this test.
    """
    import re
    import subprocess

    three, _repo = with_repository
    second = tmp_path / "other-code"
    second.mkdir()
    for command in (("init", "--quiet", "--initial-branch", "main"),
                    ("config", "user.name", "T"), ("config", "user.email", "t@e.invalid"),
                    ("config", "commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(second), *command], check=True, capture_output=True)
    for n in range(2):
        (second / f"g{n}.txt").write_text(str(n))
        subprocess.run(["git", "-C", str(second), "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(second), "commit", "-qm", f"g{n}"], check=True,
                       capture_output=True)
    (tmp_path / "c" / "PROJECT.yaml").write_text(
        'project:\n  name: "c"\n  publication_intent: "internal"\n'
        f'  repo_path: "{second}"\n'
        'pack:\n  root_path: "%s"\n  version_adopted: "2.3.0"\n'
        '  state_adopted: "IN_PROGRESS"\n  adopted_at: "2026-09-04"\n'
        '  adoption_boundary: "at a capability boundary"\nadapters: []\n'
        % Path(__file__).resolve().parents[2], encoding="utf-8")

    sites = console.survey(three)
    page = console.render_console(sites)

    totals = {site.name: console._activity_of(site).total_local for site in sites}
    assert len({n for n in totals.values() if n}) >= 2, (
        f"the fixture gave every repository the same size: {totals}")

    mine, readable = None, 0
    for index, site in enumerate(sites):
        view = page[page.index(f"data-view='project:{index}'"):]
        view = view[:view.index("<section class=view")] if "<section class=view" in view else view
        if site.view is None:
            # A project that could not be read says why, and draws no
            # instruments over a reading it does not have.
            assert "global:viz-" not in view, f"{site.name} is unreadable and drew instruments"
            continue
        readable += 1
        assert "global:viz-recent-activity" in view, f"{site.name} has no repository activity"
        assert "global:viz-recent-events" in view, f"{site.name} has no event history"
        commits = console._activity_of(site).total_local
        # EACH PROJECT STATES ITS OWN COUNT, not the registry's. A band drawn
        # from every site would put the same total on every page, and with one
        # repository in the fixture that was indistinguishable from the truth.
        if commits:
            mine = (site, view)
            assert re.search(r"<b>%d</b> commits in \d+ weeks" % commits, view), (
                f"{site.name}'s own page does not state its own {commits} commits")
        else:
            # NOT ZERO. A project with no repository this console can read is a
            # question nobody answered, and an empty calendar would answer it.
            assert "no repository this console can read" in view.lower() \
                or "commits in" not in view, (
                    f"{site.name} has no readable repository and drew a count anyway")
    assert readable, "every project in the fixture is unreadable, so this proves nothing"
    assert mine, "no project in the fixture has a repository with any commit in it"


def test_one_page_reads_each_project_history_once(with_repository):
    """The same two histories are drawn in four places. Reading them four times
    is four chances to disagree, and it is slower for the privilege."""
    three, _repo = with_repository
    sites = console.survey(three)

    calls = []
    real = console.activity.repository_activity

    def counted(where, **rest):
        calls.append(str(where))
        return real(where, **rest)

    console.activity.repository_activity = counted
    try:
        page = console.render_console(sites)
    finally:
        console.activity.repository_activity = real

    # ONE PER PROJECT, not one per repository: two projects may legitimately
    # point at the same repository, and the aggregate deduplicates them by the
    # repository's own identity afterwards. What must not happen is the same
    # project being read again because a second part of the page wanted it.
    assert len(calls) == len(sites), (
        f"{len(calls)} reads for {len(sites)} projects: {calls}")
    # and the page really did draw it in more than one place
    assert page.count("global:viz-recent-activity") > len(sites)
