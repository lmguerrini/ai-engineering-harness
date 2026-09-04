"""Many projects, one page. A READING of all of them, and nothing else.

`projection.py` answers *what is the position of this one project*. This
answers *which project should I open* — and it answers it by asking
`projection` once per project and arranging what comes back. It derives no
state, holds no state, and reaches no module a projection does not.

THE SAME RULE, ONE LEVEL UP. A console that computed a project's condition
would be a second opinion about a thing that already has an owner, and the
first disagreement between them would be unadjudicable. So every figure in
every table here is a `projection.Cell` some panel made, and the console's
only additions are position, order, and counts of the rows it is itself
showing.

**Complete with scripting switched off.** Every view is in the document and
none is hidden when it is written; the navigation adds `hidden` to the ones
it is not showing, on load. A reader whose browser runs nothing sees a long
page with everything on it, which is the only failure mode a projection may
have. Nothing here can hide an UNKNOWN by failing.

Usage::

    console.py ROOT [ROOT ...] [--registry FILE] [--theme LENS] [--accent CSS]

Exit status: ``0`` when every project was read, ``1`` when any could not be —
never non-zero because a project is in a bad state, which is the project's
business and this only reports it.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path

import activity
import projection
from projection import Cell, Tone, UNKNOWN

__all__ = ["Site", "survey", "render_console"]


@dataclass
class Site:
    """One project as this console sees it.

    `view` is the projection, or `None` when the root could not be read at all
    — which is a state this page shows rather than an entry it drops. **A
    project that vanishes from a console is worse than one shown as
    unreadable**, because nobody notices what is not there.
    """

    root: Path
    name: str
    view: "projection.Projection | None" = None
    #: Why this project could not be read at all, if it could not be.
    unreadable: str = ""
    #: The name of the earlier entry that resolves to this same tree, if any.
    same_tree_as: str = ""
    #: Registry entries that named this root.
    named_by: list = field(default_factory=list)

    @property
    def state(self) -> str:
        """The state NAME, not the sentence that explains it.

        A headline is `NAME: sentence` for a derived state and `NAME — reason`
        for one that could not be derived, and taking everything before the
        first colon put a paragraph in a table cell for the second shape.
        """
        if self.view is None:
            return UNKNOWN
        head = (self.view.headline or UNKNOWN).partition(":")[0]
        return head.partition(" — ")[0].strip() or UNKNOWN

    @property
    def sentence(self) -> str:
        """The rest of the headline: why the state is what it is."""
        if self.view is None:
            return self.unreadable
        headline = self.view.headline or ""
        return (headline[len(self.state):].lstrip(" —:").strip() or headline)

    @property
    def tone(self) -> str:
        if self.view is None:
            return Tone.UNKNOWN
        return projection._verdict_tone(self.view.headline)

    @property
    def attention(self) -> dict:
        """How many things this project's own panels marked, by tone."""
        if self.view is None:
            return {Tone.UNKNOWN: 1}
        found: dict = {}
        for line in self.view.attention:
            found[line.tone] = found.get(line.tone, 0) + 1
        return found

    def figures(self, kind: str) -> list:
        return [] if self.view is None else self.view.figure_of(kind)

    def one(self, kind: str):
        return next(iter(self.figures(kind)), None)


def survey(roots, *, contract: str = "PROJECT.yaml",
           continuation_record: str = "CONTINUATION.json",
           capacity_observation: str = "CAPACITY.json") -> list:
    """Read every named project, in the order named.

    Four things a registry does that a list of directories does not:

    * **it can name the same tree twice** — resolved and marked, never merged,
      because two entries pointing at one project is a fact about the registry
      and merging them hides it;
    * **it can name a directory that is not there** — shown as unreadable;
    * **it can name something unreadable** — likewise, with the reason;
    * **it can name projects pinning different releases** — which is legal, and
      visible in the identity view rather than averaged away.
    """
    sites: list = []
    by_tree: dict = {}
    for entry in roots:
        name, root = (entry if isinstance(entry, tuple) else (None, entry))
        root = Path(root)
        label = str(name or root.name or root)
        try:
            resolved = str(root.resolve())
        except OSError:
            resolved = str(root)
        site = Site(root=root, name=label, named_by=[str(root)])
        if resolved in by_tree:
            site.same_tree_as = by_tree[resolved]
        else:
            by_tree[resolved] = label
        if not root.is_dir():
            site.unreadable = (f"no directory at {root} — a registry entry names a project that "
                               f"is not there, which is not the same as a project with nothing "
                               f"to do")
            sites.append(site)
            continue
        try:
            site.view = projection.project(
                root, contract=contract, continuation_record=continuation_record,
                capacity_observation=capacity_observation)
        except Exception as exc:  # a projection is guarded throughout; this is the last net
            site.unreadable = f"{type(exc).__name__}: {exc}"[:300]
        sites.append(site)
    return sites


def registry(path) -> list:
    """Read a list of projects from a file. The file is data, never authority.

    A registry says WHERE to look. It never says what a project's state is —
    that comes from the project's own durable artifacts, every time this page
    is built. A stale registry can therefore name a project that has moved or
    gone, and both are shown as such.
    """
    path = Path(path)
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("projects"), list):
        raise ValueError(f"{path} is not a project registry: it declares no projects list")
    entries = []
    for row in document["projects"]:
        if isinstance(row, str):
            entries.append((None, Path(row)))
        elif isinstance(row, dict) and row.get("root"):
            entries.append((row.get("name"), Path(str(row["root"]))))
        else:
            raise ValueError(f"{path} holds a project entry with no root: {row!r}")
    return entries


# --- the application shell ------------------------------------------------------------
#
# One file, no network, no server. The pack is stdlib-only and a console that
# fetched anything would fail differently depending on where it was opened.
#
# It writes nothing: the page goes to stdout, and a caller redirecting that to a
# file is the caller writing. The only thing the page itself keeps is the
# reader's own presentation preference, in their own browser, under one key —
# which never reaches a record, a project, or this process.

_ESC = projection._escape

#: Every section of the application, and the question each one answers. A view
#: that answers no question a reader has is a route, not a view.
_VIEWS = (
    ("overview", "Overview", "which project should I open?"),
    ("all", "All systems", "everything worth knowing, on one page"),
    ("control", "Control room", "one screen to leave up while the work runs"),
    ("projects", "Projects", "what is in the registry, and can it be read?"),
    ("workers", "Workers", "what is running, what finished, what is overdue?"),
    ("audits", "Audits & evidence", "is the evidence current, and about the right tree?"),
    ("capacity", "Capacity", "can anything be dispatched?"),
    ("history", "History & public safety", "what would publishing this expose?"),
    ("identity", "Identity & release", "what release is each project actually on?"),
    ("custom", "Custom views", "the arrangement this operator wants, kept in this browser"),
    ("settings", "Settings", "lens, accent, density — and what this page is not"),
    ("help", "Help", "what this is, what the words mean, and where to find things"),
)

_SHELL_STYLE = """
/* ---- the application shell ------------------------------------------------ */
body{min-height:100vh}
.app{display:grid;grid-template-columns:1fr;min-height:100vh}
@media(min-width:1000px){.app{grid-template-columns:var(--rail) 1fr}}
.rail{background:var(--panel-2);border-right:1px solid var(--rule-strong);
display:flex;flex-direction:column;gap:2px;padding:0 0 10px;min-width:0}
.brand{padding:11px 14px 9px;border-bottom:1px solid var(--rule)}
.brand b{display:block;font-size:var(--fs-forensic);letter-spacing:.2em;text-transform:uppercase;color:var(--ink)}
.brand span{display:block;font-size:var(--fs-micro);letter-spacing:.16em;text-transform:uppercase;
color:var(--faint);margin-top:2px}
.rail h4{margin:11px 14px 3px;font-size:var(--fs-micro);letter-spacing:.2em;text-transform:uppercase;
color:var(--faint);font-weight:700}
.go{display:flex;align-items:center;gap:8px;width:100%;text-align:left;background:none;
border:0;border-left:2px solid transparent;color:var(--dim);font:inherit;font-size:var(--fs-forensic);
padding:5px 14px;cursor:pointer}
.go:hover{color:var(--ink);background:var(--panel-3)}
.go[aria-current="true"]{color:var(--ink);border-left-color:var(--accent);background:var(--panel-3)}
.go .n{margin-left:auto;font-size:var(--fs-micro);color:var(--faint)}
.go .dot{width:7px;height:7px;flex:0 0 auto;border-radius:50%;background:var(--rule-strong)}
.go .dot.bad{background:var(--bad)} .go .dot.warn{background:var(--warn)}
.go .dot.unknown{background:var(--unknown)} .go .dot.good{background:var(--good)}
.surface{min-width:0}

.gbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;padding:7px 16px;
background:var(--panel);border-bottom:1px solid var(--rule-strong);font-size:var(--fs-forensic)}
.gbar .t{color:var(--faint);text-transform:uppercase;letter-spacing:.13em;font-size:var(--fs-micro)}
.gbar .lens{margin-left:auto;display:flex;gap:1px;background:var(--rule);flex-wrap:wrap}
.lens button{background:var(--panel-2);border:0;color:var(--dim);font:inherit;font-size:var(--fs-forensic);
letter-spacing:.1em;text-transform:uppercase;padding:3px 9px;cursor:pointer}
.lens button:hover{color:var(--ink)}
.lens button[aria-pressed="true"]{background:var(--accent);color:var(--ground);font-weight:700}

.view{display:block}
/* `hidden` is an attribute the UA stylesheet turns into `display:none`, and the
   rule above outranked it — so the navigation set the attribute on every other
   view and every other view stayed on screen. It failed SAFE, which is why no
   assertion about content caught it: nothing was hidden, including the thing
   that should have been. Found by looking at a screenshot. */
.view[hidden]{display:none}
.view>h2.vh{margin:0;padding:12px 16px 4px;font-size:calc(var(--fs) + 2px);letter-spacing:-.01em;color:var(--ink)}
.view>p.vq{margin:0;padding:0 16px 11px;font-size:var(--fs-forensic);color:var(--dim);
border-bottom:1px solid var(--rule)}

/* ---- tables: the cross-project views -------------------------------------- */
.tw{overflow-x:auto;border-bottom:1px solid var(--rule)}
table{border-collapse:collapse;width:100%;font-size:var(--fs-forensic);min-width:640px}
th{text-align:left;font-size:var(--fs-micro);letter-spacing:.15em;text-transform:uppercase;
color:var(--faint);font-weight:700;padding:7px 10px;background:var(--panel-2);
border-bottom:1px solid var(--rule-strong);white-space:nowrap;position:sticky;top:0}
th[data-sort]{cursor:pointer} th[data-sort]:hover{color:var(--ink)}
td{padding:6px 10px;border-bottom:1px solid var(--rule);vertical-align:top;
background:var(--panel);max-width:34ch;overflow-wrap:anywhere}
tr:hover td{background:var(--panel-2)}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td .s{font-weight:700}
td.bad .s,.s.bad{color:var(--bad)} td.warn .s,.s.warn{color:var(--warn)}
td.unknown .s,.s.unknown{color:var(--unknown)} td.good .s,.s.good{color:var(--good)}
.s.bad::before{content:"✕ "} .s.warn::before{content:"▲ "}
.s.unknown::before{content:"? "} .s.good::before{content:"✓ "}
td small{display:block;color:var(--faint);font-size:var(--fs-forensic);
overflow-wrap:normal;word-break:normal}
/* Long prose in a table cell: clamped, never cut. The whole string stays in the
   document and in the element's title, so nothing is removed — a row simply
   stops being able to push every other row off the screen. */
.nw{white-space:nowrap}
/* an instrument's rows: the same fields a table would carry, flowing across the
   whole cell instead of into columns none of them fits */
.rows{list-style:none;margin:0;padding:0;font-size:var(--fs-forensic)}
.rows>li{display:flex;flex-wrap:wrap;gap:0 10px;align-items:baseline;
padding:4px var(--pad-x);border-bottom:1px solid var(--rule)}
.rows>li:last-child{border-bottom:0}
.rows .t{color:var(--faint);font-variant-numeric:tabular-nums}
.rows .who{font-weight:700}
.rows .what{color:var(--dim);flex:1 1 14ch;min-width:0;overflow-wrap:anywhere}
.clamp{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
line-clamp:2}
.clamp1{-webkit-line-clamp:1;line-clamp:1}
.pill{display:inline-block;padding:0 6px;border:1px solid var(--rule-strong);color:var(--dim);
font-size:var(--fs-forensic);margin-right:3px;white-space:nowrap}
.pill.bad{color:var(--bad);border-color:var(--bad);background:var(--bad-bg)}
.pill.warn{color:var(--warn);border-color:var(--warn);background:var(--warn-bg)}
.pill.unknown{color:var(--unknown);border-color:var(--unknown);background:var(--unknown-bg)}
.pill.good{color:var(--good);border-color:var(--good)}
.none{padding:10px 16px;color:var(--faint);font-size:var(--fs-forensic)}

/* ---- filters -------------------------------------------------------------- */
.filters{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:8px 16px;
background:var(--panel-2);border-bottom:1px solid var(--rule)}
.filters input[type=search],.filters input[type=text]{background:var(--ground);
border:1px solid var(--rule-strong);color:var(--ink);font:inherit;font-size:var(--fs-forensic);
padding:3px 8px;min-width:170px}
.filters button{background:var(--panel);border:1px solid var(--rule-strong);color:var(--dim);
font:inherit;font-size:var(--fs-forensic);letter-spacing:.08em;text-transform:uppercase;padding:3px 9px;
cursor:pointer}
.filters button:hover{color:var(--ink);border-color:var(--accent)}
.filters button[aria-pressed="true"]{background:var(--accent);color:var(--ground);
border-color:var(--accent);font-weight:700}
.filters .t{color:var(--faint);text-transform:uppercase;letter-spacing:.13em;font-size:var(--fs-micro)}

/* ---- the custom view builder ---------------------------------------------- */
.builder{display:grid;grid-template-columns:1fr;gap:1px;background:var(--rule)}
@media(min-width:1000px){.builder{grid-template-columns:262px 1fr}}
.catalog{background:var(--panel);padding:10px 14px;max-height:78vh;overflow-y:auto}
.catalog details>summary{cursor:pointer;list-style:none;font-size:var(--fs-forensic);color:var(--dim);
padding:4px 0;border-top:1px solid var(--rule);user-select:none}
.catalog details>summary::-webkit-details-marker{display:none}
.catalog details>summary::before{content:"▸ "}
.catalog details[open]>summary::before{content:"▾ "}
.catalog details>summary .n{color:var(--faint);font-size:var(--fs-micro)}
@media(max-width:999px){.catalog{max-height:none}}
.catalog h5{margin:9px 0 5px;font-size:var(--fs-micro);letter-spacing:.18em;text-transform:uppercase;
color:var(--faint)}
.catalog label{display:flex;gap:7px;align-items:baseline;font-size:var(--fs-forensic);padding:2px 0;
cursor:pointer;color:var(--dim)}
.catalog label:hover{color:var(--ink)}
.catalog .ord{margin-left:auto;display:flex;gap:2px}
.catalog .ord button{background:var(--panel-2);border:1px solid var(--rule);color:var(--faint);
font:inherit;font-size:var(--fs-forensic);line-height:1;padding:1px 5px;cursor:pointer}
.canvas{background:var(--ground);padding:10px;display:grid;gap:10px;
grid-template-columns:repeat(var(--cols,2),minmax(0,1fr));align-content:start}
@media(max-width:760px){.canvas{grid-template-columns:1fr}}
.canvas>*{grid-column:span var(--span,1);grid-row:span var(--tall,1);
overflow:auto;min-height:0;min-width:0}
/* A table in a narrow cell squeezed its columns until values wrapped mid-word.
   It scrolls sideways inside its own cell instead — the page does not. */
.canvas table{min-width:760px}
.canvas .tw{overflow-x:auto}
.canvas .empty{grid-column:1/-1;color:var(--faint);font-size:var(--fs-forensic);padding:16px;
border:1px dashed var(--rule-strong);text-align:center}

/* ---- settings: a control surface, not a debug form ------------------------- */
.settings{display:grid;gap:var(--gap);background:var(--rule);
grid-template-columns:repeat(auto-fit,minmax(min(100%,330px),1fr));align-items:start}
.setgroup{background:var(--panel);min-width:0}
.setbody{padding:8px var(--pad-x) 12px}
label.set{display:grid;grid-template-columns:1fr auto auto;gap:8px;align-items:center;
padding:3px 0;font-size:var(--fs);color:var(--dim);min-width:0}
label.set>span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
label.set.changed>span:first-child{color:var(--ink)}
label.set.changed>span:first-child::after{content:" •";color:var(--accent)}
label.set em{font-style:normal;color:var(--faint);font-size:var(--fs-forensic);
min-width:5ch;text-align:right}
label.set input[type=color]{inline-size:34px;block-size:20px;padding:0;border:1px solid
var(--rule-strong);background:none;cursor:pointer}
label.set input[type=range]{inline-size:100%;accent-color:var(--accent);cursor:pointer;
grid-column:1/-1}
label.set:has(input[type=range]){grid-template-columns:1fr auto auto}
label.set input[type=checkbox]{accent-color:var(--accent);cursor:pointer}
label.set select,#preset-name,.filters select{background:var(--ground);
border:1px solid var(--rule-strong);color:var(--ink);font:inherit;font-size:var(--fs);
padding:2px 6px;max-width:20ch}
label.set button{background:var(--panel-2);border:1px solid var(--rule);color:var(--faint);
font:inherit;font-size:var(--fs-forensic);line-height:1;padding:2px 6px;cursor:pointer}
label.set button:hover{color:var(--ink);border-color:var(--accent)}
.setgroup .note{margin:9px 0 0;color:var(--faint);font-size:var(--fs-forensic);max-width:56ch}
#refusals li.bad .k{color:var(--bad)}
[data-density="compact"] li{padding-top:1px;padding-bottom:1px}
[data-density="compact"] .state{font-size:calc(var(--fs-state) * 0.78)}
[data-density="comfortable"] li{padding-top:5px;padding-bottom:5px;line-height:1.6}
[data-density="comfortable"] .state{font-size:calc(var(--fs-state) * 1.15)}


/* ---- one page for everything, and one screen to leave up ------------------- */
.stack{display:grid;gap:var(--gap);background:var(--rule)}
.filters.index{gap:4px}
/* a section's own answer, before its rows */
.summary{display:flex;flex-wrap:wrap;gap:0 14px;padding:6px var(--pad-x) 7px;
border-bottom:1px solid var(--rule);font-size:var(--fs-forensic);color:var(--dim)}
.summary span{white-space:nowrap}
/* ---- the instrument band ---------------------------------------------------- */
.instruments{display:grid;gap:var(--gap);background:var(--rule);
grid-template-columns:repeat(auto-fit,minmax(min(100%,270px),1fr));
border-bottom:1px solid var(--rule)}
.instruments-wide .instruments{border-bottom:0}
.room .instruments-wide{max-height:34vh;overflow:auto}
.room .instruments{grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr))}
.instrument{min-width:0}
/* AN INSTRUMENT THAT DRAWS ROWS OR A STRIP NEEDS MORE THAN A LEGEND'S COLUMN.
   One column of the band gave the event rows ~385px at 3840 and the browser
   broke words down the middle — `readi/ng writt/en`. Found by looking at the
   ultrawide screenshot, which is the only place it was visible. The marker is
   derived from what the instrument actually rendered, not from a list of names
   somebody has to remember to extend. */
@media (min-width:1500px){.instruments>[data-wide]{grid-column:span 2}}
.nodata{margin:2px 0 4px;color:var(--faint);font-size:var(--fs-forensic)}
.onlyminimal{display:none}
[data-od="minimal"] .onlyminimal{display:block}
[data-od="minimal"] .notminimal{display:none}
.c-jobs b{font-weight:700;display:inline-block;min-width:1.6ch;text-align:right}
.c-jobs{white-space:nowrap;color:var(--dim)}
.summary .bad{color:var(--bad)} .summary .warn{color:var(--warn)}
.summary .unknown{color:var(--unknown)} .summary .good{color:var(--good)}
.summary .bad::before{content:"✕ "} .summary .warn::before{content:"▲ "}
.summary .unknown::before{content:"? "}
.jump{background:none;border:1px solid transparent;color:var(--accent);font:inherit;
font-size:inherit;padding:0 3px;cursor:pointer;text-align:left}
.jump:hover{border-color:var(--accent)}
td .jump{font-weight:700}
.filters .jump{border-color:var(--rule-strong);color:var(--dim);padding:3px 9px;
font-size:var(--fs-forensic);letter-spacing:.08em;text-transform:uppercase}
.filters .jump:hover{color:var(--ink);border-color:var(--accent)}
.guide{display:grid;gap:var(--gap);background:var(--rule);
grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));align-items:start}
.guide .setgroup ul{padding:6px 0 10px}
.guide table td:first-child{white-space:normal;max-width:26ch}

.room{display:grid;gap:var(--gap);background:var(--rule);grid-template-columns:1fr;
align-items:start}
.room-wide{grid-column:1/-1}
.room .sit{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.room table{min-width:0}
.room .setbody{padding:8px var(--pad-x) 10px}
/* EACH PANEL IS BOUNDED, so the room stays a room. Unbounded, the attention
   list — which is honestly long — grew past the screen and pushed every other
   section below the fold, leaving half an ultrawide display empty and the
   operating picture off it. Bounded, every section is on one screen and the
   long ones scroll where they are. Nothing is hidden: a scrollbar is not a
   disclosure. Found by rendering it at 3840 and looking. */
@media(min-width:1100px){
  .room{grid-template-columns:repeat(2,minmax(0,1fr));align-content:start}
  .room>section{max-height:46vh;overflow:auto;overscroll-behavior:contain}
  .room>section.room-wide{max-height:none}
  .room>section>.head{position:sticky;top:0;z-index:1}
}
@media(min-width:1800px){.room{grid-template-columns:repeat(3,minmax(0,1fr))}}
/* ULTRAWIDE. At this width a single column would be a very tall page nobody
   scrolls; four columns put the whole operating picture on one screen without
   shrinking the type to do it. */
/* ---- the readability floor -------------------------------------------------
   A wide screen is for seeing MORE, not for seeing the same thing smaller. The
   founder's review of the first ultrawide capture was that it fitted a great
   deal and could not be read from a normal desk distance — so the type grows
   with the screen instead of shrinking to fit, and what the extra width buys
   is more columns and shorter summaries rather than more rows of small text. */
@media(min-width:1900px){
  body{--fs:13.5px;--fs-micro:9.5px;--fs-forensic:12.5px;--fs-state:33px}
}
@media(min-width:2400px){
  body{--fs:15px;--fs-micro:10.5px;--fs-forensic:13.5px;--fs-state:37px;--pad-x:20px}
  .room{grid-template-columns:repeat(3,minmax(0,1fr))}
  .room>section{max-height:44vh}
  .room-wide{grid-column:1/-1}
  main{grid-template-columns:repeat(3,minmax(0,1fr))}
  .settings,.guide{grid-template-columns:repeat(auto-fit,minmax(min(100%,520px),1fr))}
}
@media(min-width:3400px){
  body{--fs:16px;--fs-micro:11px;--fs-forensic:14.5px;--fs-state:42px;--pad-x:22px}
  .room{grid-template-columns:repeat(4,minmax(0,1fr))}
  .room>section{max-height:40vh}
  .room-wide{grid-column:1/-1}
  .room>section.room-wide:first-child{max-height:none}
  /* attention and the health matrix are the two an operator reads most, so they
     get the width; everything else is a summary beside them. */
  .room>section.wide2{grid-column:span 2}
}
/* the chrome folds away, and comes back with the same key */
body[data-chrome="off"] .rail{display:none}
body[data-chrome="off"] .app{grid-template-columns:1fr}
body[data-chrome="off"] .view>h2.vh,body[data-chrome="off"] .view>p.vq{display:none}
body[data-chrome="off"] footer{display:none}

/* all systems: two depths, and the shallower one drops only what has its own view */
[data-ad="minimal"] .later{display:none}

/* the overview's three densities */
.onlyfull{display:none}
[data-od="full"] .onlyfull{display:block}
[data-od="minimal"] .c-running,[data-od="minimal"] .c-complete,
[data-od="minimal"] .c-unknown,[data-od="minimal"] .c-stalled,
[data-od="minimal"] th[data-sort="num"]:not(:last-child){display:none}
[data-od="minimal"] #attention-widget{display:none}

/* ---- the activity calendar --------------------------------------------------
   Five luminance steps, and the hue says which population a day belongs to:
   neutral for what is only here, green for what the remote represents, a split
   cell where a day holds both, and the UNKNOWN tone where the remote has never
   been observed. A cell is never blank for an unanswered question — blank means
   an established zero and nothing else. */
.calendar{padding:8px var(--pad-x) 4px;overflow-x:auto}
.calendar .months{display:grid;grid-auto-flow:column;grid-auto-columns:13px;
font-size:var(--fs-micro);color:var(--faint);letter-spacing:.1em;text-transform:uppercase;
margin-bottom:3px;min-width:min-content}
.calendar .grid{display:grid;grid-template-rows:repeat(7,11px);grid-auto-flow:column;
grid-auto-columns:11px;gap:2px;min-width:min-content}

/* A cell's FILL says how much happened; its OUTLINE says whether the remote
   side of that day is established. They are two different facts and the fill
   used to be replaced by the uncertainty — so a day with real work on it and an
   unfetched remote was painted as though nothing were known about it. */
.cell{display:block;width:11px;height:11px;background:var(--panel-2);
border:1px solid var(--rule)}
.cell:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.cell.k-local.s1{background:color-mix(in srgb,var(--ink) 34%,var(--panel-2));border-color:transparent}
.cell.k-local.s2{background:color-mix(in srgb,var(--ink) 56%,var(--panel-2));border-color:transparent}
.cell.k-local.s3{background:color-mix(in srgb,var(--ink) 78%,var(--panel-2));border-color:transparent}
.cell.k-local.s4{background:var(--ink);border-color:transparent}
.cell.k-remote.s1{background:color-mix(in srgb,var(--good) 38%,var(--panel-2));
border-color:transparent}
.cell.k-remote.s2{background:color-mix(in srgb,var(--good) 60%,var(--panel-2));
border-color:transparent}
.cell.k-remote.s3{background:color-mix(in srgb,var(--good) 80%,var(--panel-2));
border-color:transparent}
.cell.k-remote.s4{background:var(--good);border-color:transparent}
.cell.k-split.s1,.cell.k-split.s2,.cell.k-split.s3,.cell.k-split.s4{border-color:transparent;
background:linear-gradient(135deg,var(--good) 0 50%,var(--ink) 50% 100%)}
/* A day with NOTHING local and a remote nobody has observed: the question is
   all there is, so the hatch is the whole cell. */
/* Scoped to a CELL. Unscoped, the class painted the legend's own label with the
   hatch it was there to explain. */
.cell.k-unknown{background:repeating-linear-gradient(45deg,var(--unknown-bg) 0 3px,
var(--unknown) 3px 4px);border-color:transparent}
/* A day that DOES have local activity and an unresolved remote keeps its fill
   and wears a ring. */
.cell.q{box-shadow:inset 0 0 0 1.5px var(--unknown)}
.calendar-legend{padding:2px var(--pad-x) 10px;align-items:center;gap:4px 16px}
.calendar-legend>span{gap:6px}
.calendar-legend .cell{width:11px;height:11px;flex:0 0 auto}
.calendar-legend .t{margin-left:6px}
.calendar-legend .k-local i{background:var(--ink)}
.calendar-legend .k-remote i{background:var(--good)}
.calendar-legend .k-split i{background:linear-gradient(135deg,var(--good) 0 50%,
var(--ink) 50% 100%)}
.calendar-legend .k-unknown i{background:repeating-linear-gradient(45deg,var(--unknown-bg)
0 3px,var(--unknown) 3px 4px)}
.calendar.recent{padding:2px 0 6px;overflow-x:auto}
.calendar.recent .grid{grid-template-rows:repeat(7,11px);grid-auto-columns:11px;gap:2px}
.calendar.recent .cell{width:11px;height:11px}
.actmode{display:none}
.actmode.on{display:block}
.inspector{padding:8px var(--pad-x) 12px;border-top:1px solid var(--rule);
background:var(--panel-2)}
.inspector h4{margin:0 0 5px;font-size:var(--fs-micro);letter-spacing:.16em;
text-transform:uppercase;color:var(--faint)}

/* ---- quick find ------------------------------------------------------------- */
.finder{display:none;position:fixed;inset:0;z-index:20;background:rgba(0,0,0,.62);
padding:8vh 16px 16px}
.finder.open{display:block}
.finderbox{display:flex;gap:1px;max-width:720px;margin:0 auto;background:var(--rule)}
.finderbox input{flex:1;background:var(--panel);border:0;color:var(--ink);font:inherit;
font-size:calc(var(--fs) + 2px);padding:11px 14px}
.finderbox button{background:var(--panel-2);border:0;color:var(--faint);font:inherit;
font-size:var(--fs-forensic);letter-spacing:.12em;text-transform:uppercase;padding:0 12px;cursor:pointer}
#find-list{max-width:720px;margin:1px auto 0;background:var(--panel);max-height:62vh;
overflow-y:auto;padding:0}
#find-list li{padding:6px 14px;gap:10px;cursor:pointer;border-bottom:1px solid var(--rule)}
#find-list li:hover,#find-list li.on{background:var(--panel-3)}
#find-list li .k{flex:0 0 6.5ch;color:var(--faint);text-transform:uppercase;
font-size:var(--fs-micro);letter-spacing:.1em}
#find-list li .k::after{content:""}
#find-list li .v{flex:1 1 auto;color:var(--ink)}
#find-list li .hint{color:var(--faint);font-size:var(--fs-forensic);
overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:34ch}

/* ---- narrow: the rail becomes a bar ---------------------------------------- */
@media(max-width:999px){
  .app{grid-template-columns:1fr;min-width:0}
  .surface{min-width:0}
  .gbar{gap:6px 12px;font-size:var(--fs-forensic)}
  .gbar .lens{margin-left:0;width:100%;overflow-x:auto;scrollbar-width:none}
  .gbar .lens::-webkit-scrollbar{display:none}
  .rail{position:sticky;bottom:0;order:2;flex-direction:row;overflow-x:auto;gap:0;
  border-right:0;border-top:1px solid var(--rule-strong);padding:0;
  scrollbar-width:none;z-index:5}
  .rail::-webkit-scrollbar{display:none}
  .brand,.rail h4{display:none}
  .go{width:auto;white-space:nowrap;border-left:0;border-top:2px solid transparent;
  padding:8px 12px;font-size:var(--fs-forensic)}
  .go[aria-current="true"]{border-left-color:transparent;border-top-color:var(--accent)}
  .surface{order:1}
  .view>h2.vh{padding-top:10px;font-size:calc(var(--fs) + 2px)}
  /* A TABLE IS THE WRONG SHAPE FOR A PHONE. Twelve columns squeezed into
     390px wrapped every value mid-word — the "stacked desktop" this layout
     exists not to be. Below the breakpoint each row becomes a card and each
     cell carries its own header, from the `data-label` the cell was written
     with. One document, two layouts: rendering the readings twice and hoping
     the copies stay equal is how a phone ends up showing something the desktop
     does not. */
  table,tbody,tr,td{display:block;min-width:0}
  thead{display:none}
  .tw{overflow-x:visible}
  tr{padding:9px 12px;border-bottom:1px solid var(--rule-strong);background:var(--panel);
  display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px 8px}
  tr:hover td{background:none}
  td{border:0;padding:0;max-width:none;background:none;grid-column:1/-1;
  overflow-wrap:anywhere}
  td::before{content:attr(data-label);display:block;font-size:var(--fs-micro);letter-spacing:.14em;
  text-transform:uppercase;color:var(--faint);margin-bottom:1px}
  td.num{text-align:left}
  td:empty{display:none}
  /* the overview's own hierarchy: who, then what, then the counters */
  /* A state name is one long unbreakable token. Sharing a line with the
     project name pushed it past the viewport — the one thing a phone layout
     may not do — so each gets its own. */
  .c-project,.c-state{grid-column:1/-1}
  .c-running,.c-complete,.c-unknown,.c-stalled{grid-column:span 1}
  .c-project .s{font-size:calc(var(--fs) + 2px)} .c-state .s{font-size:var(--fs)}
  .c-attention .s,.c-attention{font-weight:700}
}
"""


def _pill(text: str, tone: str = Tone.PLAIN) -> str:
    return f"<span class='pill {tone}'>{_ESC(text)}</span>"


def _td(column: str, body: str, tone: str = "", extra: str = "") -> str:
    """One cell that knows which column it is in.

    A narrow screen has no room for a header row, so the header comes with the
    cell — `data-label` is what the stylesheet prints in front of it below the
    breakpoint. One document, two layouts: the alternative is rendering the
    same readings twice and hoping they stay the same.
    """
    slug = "".join(c if c.isalnum() else "-" for c in column).strip("-")
    return f"<td class='c-{slug} {tone}'{extra} data-label='{_ESC(column)}'>{body}</td>"


#: Where each project sits in the page, so a name anywhere can open it.
_INDEX: dict = {}


def _project_cell(site: "Site") -> str:
    """WHO this row is about, and a way to go there.

    The state has its own column; putting it here too made the first column
    repeat the second and pushed the name into a footnote. The name is a
    control now — an operator who has found a project in any table should not
    have to go back to the sidebar to open it.
    """
    where = site.root.name or str(site.root)
    at = _INDEX.get(id(site))
    name = (f"<button class=jump data-goto='project:{at}'>{_ESC(site.name)}</button>"
            if at is not None else f"<span class=s>{_ESC(site.name)}</span>")
    return _td("project", name + (f"<small>{_ESC(where)}</small>" if where != site.name else ""))


def _overview(sites: list) -> str:
    """Every project in one table: state, next action, workers, audit, freshness,
    capacity, who is blocked, and how old the reading is.

    **No aggregate can be greener than its parts.** Every column below is a
    figure some project's own panel produced; the only arithmetic is counting
    rows already on this page, and a count is never shown where the underlying
    reading is UNKNOWN — `·` means *this single reading cannot establish it*,
    which is not zero.
    """
    head = ("<div class=tw><table><thead><tr>"
            "<th data-sort=text>project</th><th data-sort=text>state</th>"
            "<th data-sort=text>next authorised action</th>"
            "<th data-sort=num title='a job whose owner can be observed to exist'>running</th>"
            "<th data-sort=num>complete</th>"
            "<th data-sort=num title='outstanding, and nothing here can observe it'>unknown</th>"
            "<th data-sort=num title='a stall needs two readings over time'>stalled</th>"
            "<th data-sort=text>audit subject</th><th data-sort=text>read</th>"
            "<th data-sort=text>capacity</th><th data-sort=text>needs a person</th>"
            "<th data-sort=num>attention</th></tr></thead><tbody>")
    rows = []
    for index, site in enumerate(sites):
        if site.view is None:
            rows.append(
                f"<tr data-project='{index}' data-state='{UNKNOWN}' data-tone='unknown' "
                f"data-attention='1'>"
                + _project_cell(site)
                + _td("state", "<span class='s unknown'>unreadable</span>"
                      f"<small class=clamp title='{_ESC(site.unreadable)}'>"
                      f"{_ESC(site.unreadable)}</small>", "unknown",
                      " colspan=10")
                + _td("attention", "1", "num unknown") + "</tr>")
            continue
        jobs = site.figures("job")
        counted = {}
        for cell in jobs:
            counted[cell.value] = counted.get(cell.value, 0) + 1
        audit = site.one("audit")
        fresh = site.one("freshness")
        pools = site.figures("capacity")
        block = site.one("intervention")
        marked = site.attention
        total = sum(marked.values())
        worst = next((t for t in (Tone.BAD, Tone.WARN, Tone.UNKNOWN) if marked.get(t)),
                     Tone.PLAIN)
        rows.append(
            f"<tr data-project='{index}' data-state='{_ESC(site.state)}' "
            f"data-tone='{site.tone}' data-attention='{total}'>"
            + _project_cell(site)
            + _td("state", f"<span class='s {site.tone}'>{_ESC(site.state)}</span>"
                  f"<small class='clamp clamp1' title='{_ESC(site.sentence)}'>"
                  f"{_ESC(site.sentence)}</small>", site.tone)
            + _td("next authorised action",
                  f"<span class=clamp>{_ESC(site.view.next_action or '—')}</span>", "",
                  f" title='{_ESC(site.view.next_action)}'")
            + _td("running", str(counted.get("RUNNING", 0)), "num")
            + _td("complete", str(counted.get("COMPLETE", 0)), "num")
            + _td("unknown", str(counted.get(UNKNOWN, 0)), "num unknown")
            # NOT A ZERO. A stall needs two independently observed flat signals
            # over time and this page is one reading, so the honest cell says
            # the question is not answered here rather than answering it `0`.
            + _td("stalled", "·", "num",
                  " title='a stall needs two readings over time; `progress.classify` answers it'")
            + (_td("audit subject",
                   f"<span class='s {audit.tone}'>{_ESC(audit.value)}</span>"
                   f"<small>{_ESC(audit.note or '')}</small>", audit.tone) if audit else
               _td("audit subject", f"<span class='s unknown'>no audit declared</span>",
                   "unknown"))
            + (_td("read", _ESC(fresh.value)
                   + (f"<small>{_ESC(fresh.note)}</small>" if fresh.note else ""), fresh.tone)
               if fresh else
               _td("read", f"<span class='s unknown'>{UNKNOWN}</span>", "unknown"))
            + (_td("capacity", _ESC(pools[0].value)
                   + f"<small>{_ESC(pools[0].fields.get('pool', 'no observation'))}</small>",
                   pools[0].tone) if pools else
               _td("capacity", f"<span class='s unknown'>{UNKNOWN}</span>", "unknown"))
            + (_td("needs a person",
                   f"<span class=clamp title='{_ESC(block.value)}'>{_ESC(block.value)}</span>",
                   block.tone) if block else
               _td("needs a person", f"<span class='s unknown'>{UNKNOWN}</span>", "unknown"))
            + _td("attention", str(total), f"num {worst}") + "</tr>")
    if not rows:
        return ("<p class=none>No project was named. This console reads projects it is given "
                "and discovers none on its own — a page that went looking would be a page that "
                "could be wrong about what exists.</p>")
    return head + "".join(rows) + "</tbody></table></div>"


def _projects(sites: list) -> str:
    """The registry itself: what was named, whether it resolved, what it pins."""
    rows = []
    for site in sites:
        pin = site.one("pin")
        pack = site.one("pack")
        trouble = []
        if site.unreadable:
            trouble.append(_pill("unreadable", Tone.UNKNOWN))
        if site.same_tree_as:
            trouble.append(_pill(f"the same tree as {site.same_tree_as}", Tone.WARN))
        rows.append(
            f"<tr><td><span class=s>{_ESC(site.name)}</span>"
            f"<small>{_ESC(str(site.root))}</small></td>"
            + (f"<td class='{pin.tone}'>{_ESC(pin.value)}<small>{_ESC(pin.note)}</small></td>"
               if pin else f"<td class=unknown><span class='s unknown'>no pin readable</span></td>")
            + (f"<td>{_ESC(pack.fields.get('version', UNKNOWN))}"
               f"<small>{_ESC(pack.fields.get('state', UNKNOWN))}</small></td>" if pack else
               "<td class=unknown><span class='s unknown'>UNKNOWN</span></td>")
            + f"<td>{''.join(trouble) or '—'}</td>"
            + f"<td>{_ESC(pin.fields.get('publication', UNKNOWN)) if pin else UNKNOWN}</td></tr>")
    if not rows:
        return "<p class=none>No project was named.</p>"
    return ("<div class=tw><table><thead><tr><th>project</th><th>pinned release</th>"
            "<th>pack in that root</th><th>registry trouble</th><th>publication intent</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


def _kind_table(sites: list, kind: str, columns, empty: str) -> str:
    """One cross-project table over figures of a single kind.

    Columns are named here and read out of `Cell.fields`, which every panel
    fills from lines it also shows. A column with nothing behind it renders
    UNKNOWN rather than blank: an empty cell in an operations table reads as
    *nothing to report*, and this page may never say that about an absence.
    """
    rows = []
    for site in sites:
        for cell in site.figures(kind):
            values = "".join(
                _td(title,
                    (f"<span class='s {cell.tone}'>{_ESC(cell.value)}</span>"
                     if name == "·state" else
                     (_ESC(cell.fields.get(name) or UNKNOWN) if cell.fields.get(name)
                      else f"<span class='s unknown'>{UNKNOWN}</span>")),
                    cell.tone if name == "·state" else "")
                for name, title in columns)
            at = _INDEX.get(id(site))
            named = (f"<button class=jump data-goto='project:{at}'>{_ESC(site.name)}</button>"
                     if at is not None else f"<span class=s>{_ESC(site.name)}</span>")
            rows.append(f"<tr data-tone='{cell.tone}'>"
                        + _td("project", named + f"<small>{_ESC(cell.label)}</small>")
                        + values + "</tr>")
    if not rows:
        return f"<p class=none>{_ESC(empty)}</p>"
    heads = "".join(f"<th data-sort=text>{_ESC(title)}</th>" for _, title in columns)
    return ("<div class=tw><table><thead><tr><th data-sort=text>project</th>" + heads +
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


# --- history: when code changed, and what the governed run was doing ------------------
#
# One experience, not two charts. The repository half answers *when was code
# actually changed and how much of it is still only here*; the pack half answers
# *what happened while it was*. They share a calendar so the two can be read
# together, and nothing on this page claims one caused the other.
#
# Every cell is rendered from `activity.py`, which reads the local object graph
# and durable artifacts and never touches the network. Three rules:
#
#   * **Local contains remote.** A pushed commit is one commit two refs reach.
#   * **An unobserved remote is a question**, drawn as such and never as zero.
#   * **A count is not a score.** More commits is not better and nothing here
#     says otherwise.


def _activity_scale(count: int, most: int) -> int:
    """Which of five luminance steps a day falls in. Zero is its own step."""
    if count <= 0 or most <= 0:
        return 0
    return min(4, 1 + int(3.99 * (count - 1) / max(1, most)))


def _calendar(days, *, mode: str, most: int, label: str) -> str:
    """A year of days as a contribution calendar.

    A cell carries its exact counts in its label, so the numbers are available
    to a reader who cannot see the shading and to one who has no pointer.
    """
    if not days:
        return ("<p class=none>No commit in this period. That is a reading of this "
                "repository, not a claim about anybody's week.</p>")
    by_date = {day.date: day for day in days}
    first = datetime.date.fromisoformat(min(by_date))
    last = datetime.date.fromisoformat(max(by_date))
    start = first - datetime.timedelta(days=first.weekday())
    cells, months, at = [], [], start
    while at <= last:
        key = at.isoformat()
        day = by_date.get(key)
        local = day.local if day else 0
        remote = day.remote if day else 0
        only = day.local_only if day else 0
        unknown = bool(day and day.remote_unknown)
        if mode == "remote":
            shown, kind = (0 if unknown else remote), ("unknown" if unknown else "remote")
        elif mode == "local":
            shown, kind = local, "local"
        else:
            shown, kind = local, ("split" if remote and only else
                                  ("remote" if remote else
                                   ("unknown" if unknown and not local else "local")))
        step = _activity_scale(shown, most)
        told = (f"{key}: {local} local"
                + (f", {remote} represented by the remote" if not unknown else
                   ", the remote has never been observed here")
                + (f", {only} only here" if only else ""))
        cells.append(
            f"<i class='cell s{step} k-{kind}{' q' if unknown else ''}' "
            f"data-day='{key}' data-local='{local}' data-remote='{remote}' "
            f"data-only='{only}' title='{_ESC(told)}' role=img "
            f"aria-label='{_ESC(told)}' tabindex=0></i>")
        if at.day <= 7 and at.weekday() == 0:
            months.append((len(cells) - 1, at.strftime("%b")))
        at += datetime.timedelta(days=1)
    ruler = "".join(
        f"<span style='grid-column:{1 + index // 7}'>{_ESC(name)}</span>"
        for index, name in months)
    return (f"<div class=calendar aria-label='{_ESC(label)}'>"
            f"<div class=months>{ruler}</div>"
            f"<div class=grid>{''.join(cells)}</div></div>")


def _activity_legend(mode: str) -> str:
    if mode == "remote":
        parts = [("represented by the remote", "remote"),
                 ("never observed here", "unknown")]
    elif mode == "local":
        parts = [("commits in this repository", "local")]
    else:
        parts = [("only here", "local"), ("represented by the remote", "remote"),
                 ("both, on one day", "split"), ("remote never observed", "unknown")]
    return ("<div class='legend calendar-legend'>"
            + "".join(f"<span class=k-{key}><i></i>{_ESC(text)}</span>" for text, key in parts)
            + "<span class=t>a ring marks a day whose remote side is unresolved</span>"
            + "<span class=t>less</span>"
            + "".join(f"<i class='cell s{n} k-{parts[0][1]}'></i>" for n in range(5))
            + "<span class=t>more</span></div>")


def _period_of(scale: str, days):
    """The window a scale shows, ending at the most recent day with anything in
    it — so a page opened after a quiet fortnight still opens on the work."""
    dates = [datetime.date.fromisoformat(day.date) for day in days] or [
        datetime.datetime.now(datetime.timezone.utc).date()]
    end = max(dates)
    span = {"year": 365, "month": 31, "week": 7, "day": 1}.get(scale, 365)
    return end - datetime.timedelta(days=span - 1), end


def _history(sites: list) -> str:
    """Publication intent and public safety, per project — kept as it was."""
    rows = []
    for site in sites:
        pin = site.one("pin")
        readings = {c.label: c for c in site.figures("evidence")}
        safety = readings.get("public safety")
        gates = readings.get("gates")
        at = _INDEX.get(id(site))
        named = (f"<button class=jump data-goto='project:{at}'>{_ESC(site.name)}</button>"
                 if at is not None else f"<span class=s>{_ESC(site.name)}</span>")
        rows.append(
            f"<tr>{_td('project', named)}"
            + _td("publication intent",
                  _ESC(pin.fields.get("publication", UNKNOWN)) if pin else UNKNOWN)
            + (_td("public-safety reading", f"<span class=clamp>{_ESC(safety.value)}</span>",
                   safety.tone) if safety else
               _td("public-safety reading", f"<span class='s unknown'>{UNKNOWN}</span>",
                   "unknown", " title='no public-safety reading is declared'"))
            + (_td("gates", f"<span class=clamp>{_ESC(gates.value)}</span>", gates.tone)
               if gates else _td("gates", f"<span class='s unknown'>{UNKNOWN}</span>", "unknown"))
            + "</tr>")
    if not rows:
        return "<p class=none>No project was named.</p>"
    return ("<div class=tw><table><tbody>" + "".join(rows) + "</tbody></table></div>")


def _repository_summary(activities, days) -> str:
    """The exact values for the period, and not one of them a score."""
    total = sum(day.local for day in days)
    represented = sum(day.remote for day in days)
    only = sum(day.local_only for day in days)
    unresolved = [a for a in activities if not a.remote_established]
    unknown_days = sum(1 for day in days if day.remote_unknown)
    latest_local = max((day.date for day in days if day.local), default="")
    latest_remote = max((day.date for day in days if day.remote), default="")

    def cell(label, value, tone="plain", note=""):
        return (f"<div class='sit {tone}'><i>{_ESC(label)}</i><em>{_ESC(str(value))}</em>"
                + (f"<u>{_ESC(note)}</u>" if note else "") + "</div>")

    return ("<div class=sit>"
            + cell("local commits", total,
                   note=f"every commit a local ref reaches, in the last "
                        f"{activity.DEFAULT_WINDOW_DAYS} days")
            + cell("represented by the remote",
                   UNKNOWN if unknown_days and not represented else represented,
                   "unknown" if unknown_days and not represented else "plain",
                   note="a subset of the local total, never added to it")
            + cell("only here", only, "warn" if only else "plain",
                   note="reachable from no remote ref")
            + cell("active days", sum(1 for day in days if day.local))
            + cell("projects with activity",
                   len([a for a in activities if a.total_local]))
            + cell("latest local", latest_local or UNKNOWN,
                   "plain" if latest_local else "unknown")
            + cell("latest represented", latest_remote or UNKNOWN,
                   "plain" if latest_remote else "unknown",
                   note="" if latest_remote else "nothing observed")
            + cell("remote", f"{len(unresolved)} of {len(activities)} unresolved"
                   if unresolved else "observed everywhere",
                   "unknown" if unresolved else "plain")
            + cell("days counted in", activity.TIMEZONE,
                   note="a commit belongs to its UTC day, wherever it was made")
            + "</div>")


def _repository_table(activities) -> str:
    """Every repository the registry names, and what each contributes.

    Two things an independent reader found here. A repository that would not
    open rendered `0` local and `0` only-here — **established zeroes about a
    reading nobody could take**. And two entries naming one repository each
    listed their own totals while the calendar above counted them once, so the
    table and the summary disagreed about the same number.
    """
    rows, seen = [], set()
    for one in activities:
        counted = not (one.identity and one.identity in seen)
        if one.identity:
            seen.add(one.identity)
        tone = ("unknown" if one.unreadable or not one.remote_established else "plain")

        def number(value, known=one.established):
            return (str(value) if known else f"<span class='s unknown'>{UNKNOWN}</span>")

        note = one.unreadable or one.remote_note
        if not counted:
            note = ("the same repository as a row above; the calendar and the summary count it "
                    "once. " + note)
        rows.append(
            "<tr>" + _td("repository", f"<span class=s>{_ESC(one.name)}</span>"
                         f"<small>{_ESC(one.repository)}</small>")
            + _td("local", number(one.total_local),
                  "num" if one.established else "num unknown")
            + _td("represented",
                  str(one.total_remote) if one.remote_established and one.established
                  else f"<span class='s unknown'>{UNKNOWN}</span>",
                  "num" if one.remote_established and one.established else "num unknown")
            + _td("only here", number(one.total_local_only),
                  "num" if one.established else "num unknown")
            + _td("counted", "yes" if counted else "once, above",
                  "" if counted else "unknown")
            + _td("remote", f"<span class='s {tone}'>{_ESC(one.remote_state)}</span>", tone)
            + _td("what is known", f"<span class=clamp>{_ESC(note)}</span>")
            + "</tr>")
    if not rows:
        return "<p class=none>No project declares a repository this console can read.</p>"
    return f"<div class=tw><table><tbody>{''.join(rows)}</tbody></table></div>"


def _event_timeline(events, *, limit: int = 400) -> str:
    if not events:
        return ("<p class=none>No durable artifact in these projects carries a timestamp for "
                "anything that happened. That is a statement about what is recorded, not about "
                "what was done.</p>")
    rows = []
    for event in events[:limit]:
        rows.append(
            # THE INDEX, not the name. Two registry entries may be called the
            # same thing, and filtering by the label then showed both projects'
            # events under either one. Found by an independent reader.
            f"<tr data-tone='{event.tone}' data-kind='{_ESC(event.kind)}' "
            f"data-project='{_ESC(event.project)}' "
            f"data-at='{_ESC(str(getattr(event, 'at', '')))}' "
            f"data-basis='{_ESC(event.basis)}' data-day='{_ESC(event.day)}'>"
            + _td("when", _ESC(event.when or UNKNOWN),
                  "" if event.when else "unknown")
            + _td("project", f"<span class=s>{_ESC(event.project)}</span>")
            + _td("event", f"<span class='s {event.tone}'>{_ESC(event.kind)}</span>"
                  + ("<small>derived, not recorded</small>"
                     if event.basis == "derived" else ""), event.tone)
            + _td("subject", _ESC(event.subject))
            + _td("capability", _ESC(event.capability or "—"))
            + _td("detail", f"<span class=clamp>{_ESC(event.detail)}</span>")
            + _td("from", f"<span class=clamp>{_ESC(event.source)}</span>")
            + "</tr>")
    more = ("" if len(events) <= limit else
            f"<p class=none>{len(events) - limit} further events are not listed here; "
            f"narrow the period or the filter.</p>")
    return f"<div class=tw><table><tbody>{''.join(rows)}</tbody></table></div>{more}"


def _event_shape(events) -> str:
    tally: dict = {}
    for event in events:
        tally[(event.kind, event.tone)] = tally.get((event.kind, event.tone), 0) + 1
    return _distribution([(kind, count, tone) for (kind, tone), count in
                          sorted(tally.items(), key=lambda row: -row[1])],
                         "Nothing durable dates an event in these projects.")


#: One read per project per page. The history view, the control room's band, the
#: full overview and each project's own detail all draw the same two histories;
#: reading them four times would be four chances to disagree, and the page would
#: be slower for the privilege. Cleared at the top of every render, so nothing
#: survives into a page that did not read it.
_READINGS: dict = {}


def _repository_of(site) -> str:
    """The repository a project declares, or the project root it lives in."""
    pin = site.one("pin")
    where = (pin.fields.get("repository") if pin else "") or ""
    return where if where and where != UNKNOWN and Path(where).is_dir() else str(site.root)


def _reading(kind: str, site, read):
    """Cache one project's history for the length of one page.

    The site itself is held beside the reading. `id()` is only unique among
    objects that are alive, and a cache keyed by the identity of something it
    does not keep would hand a recycled address somebody else's history.
    """
    key = (kind, id(site))
    if key not in _READINGS:
        _READINGS[key] = (site, read())
    return _READINGS[key][1]


def _activity_of(site):
    return _reading("activity", site,
                    lambda: activity.repository_activity(_repository_of(site), name=site.name))


def _events_of(site) -> list:
    return _reading("events", site, lambda: activity.pack_events(site.root, name=site.name))


def _history_view(sites: list) -> str:
    """Repository activity and governed events, on one calendar."""
    activities, events = [], []
    for at, site in enumerate(sites):
        activities.append(_activity_of(site))
        for event in _events_of(site):
            event.at = str(at)
            events.append(event)
    events.sort(key=lambda e: (e.when == "", e.when))
    days = activity.aggregate(activities)
    most = max((day.local for day in days), default=0)

    scales = "".join(
        f"<button data-scale='{key}'{' aria-pressed=true' if key == 'year' else ''}>"
        f"{_ESC(key)}</button>" for key in ("year", "month", "week", "day"))
    modes = "".join(
        f"<button data-actmode='{key}'{' aria-pressed=true' if key == 'combined' else ''}>"
        f"{_ESC(label)}</button>" for key, label in
        (("local", "local git"), ("remote", "remote"), ("combined", "local ↔ remote")))
    projects = "".join(
        f"<option value='{at}'>{_ESC(site.name)}</option>" for at, site in enumerate(sites))
    kinds = "".join(
        f"<button data-eventkind='{_ESC(kind)}'>{_ESC(kind)}</button>"
        for kind in sorted({event.kind for event in events}))

    return (
        "<div class=filters><span class=t>scale</span>" + scales
        # A SCALE IS A WINDOW ENDING AT THE MOST RECENT DAY, which is the
        # question a reader asks most and not the only one. These two are plain
        # UTC dates compared against the day a cell already carries, so the
        # range needs no conversion and cannot disagree with the calendar.
        + "<span class=t>range</span>"
        "<input type=date id=history-from aria-label='from, UTC'>"
        "<span class=t>to</span>"
        "<input type=date id=history-to aria-label='to, UTC'>"
        + "<span class=t>show</span>" + modes
        + f"<span class=t>project</span><select id=history-project>"
        f"<option value=all>all projects</option>{projects}</select>"
        "<button data-scale='year' id=history-today>most recent</button>"
        # WHICH WINDOW IS IN FORCE, in words, wherever it came from. Four
        # buttons and two date boxes can disagree about which one is chosen;
        # a sentence cannot.
        "<span class=t>showing</span><b id=history-period>year</b>"
        f"<span class=t>days are {activity.TIMEZONE}</span></div>"
        "<div class=stack>"
        + f"<section class=setgroup id=history-repository><div class=head>"
        f"<h2>repository activity</h2>"
        f"<span class=chip>{len(activities)} repositories</span></div>"
        f"<div class=setbody>{_repository_summary(activities, days)}</div>"
        + "".join(
            f"<div class=actmode data-actmode='{mode}'>"
            + _calendar(days, mode=mode, most=most,
                        label=f"repository activity, {mode}")
            + _activity_legend(mode) + "</div>"
            for mode in ("local", "remote", "combined"))
        + _repository_table(activities) + "</section>"
        + f"<section class=setgroup id=history-events><div class=head>"
        f"<h2>runtime pack events</h2><span class=chip>{len(events)} dated</span></div>"
        f"<div class=setbody>{_event_shape(events)}</div>"
        "<div class=filters><span class=t>only</span>"
        "<button data-eventkind='' aria-pressed=true>all events</button>"
        + kinds + "</div>"
        # NOT hidden. Nothing in this document is written hidden — an empty
        # panel says it is empty instead, which is also what a reader needs.
        + "<div class=inspector id=day-inspector><h4>a day</h4>"
        "<p class=none style='padding:0'>Choose a cell above — with a pointer or with the "
        "keyboard — and this says what both histories hold for that day.</p></div>"
        + _event_timeline(events) + "</section>"
        + "<section class=setgroup id=history-safety><div class=head>"
        "<h2>publication intent and public safety</h2></div>"
        + _history(sites) + "</section>"
        + "<section class=setgroup id=history-what><div class=head>"
        "<h2>what these two histories are</h2></div><ul>"
        "<li><span class=k>local git</span><span class=v>every commit a local ref reaches, "
        "counted once however many refs reach it.</span></li>"
        "<li><span class=k>represented by the remote</span><span class=v>the subset of those "
        "commits a remote-tracking ref also reaches. A subset — never added to the local "
        "total, because a pushed commit is one commit.</span></li>"
        "<li><span class=k>only here</span><span class=v>the rest: reachable from a local ref "
        "and from no remote one.</span></li>"
        "<li class=unknown><span class=k>never observed</span><span class=v>a remote is "
        "declared and nothing here has ever seen what it holds. This page does not fetch, so "
        "that stays an open question rather than becoming a zero.</span></li>"
        f"<li><span class=k>days</span><span class=v>{activity.TIMEZONE}. A commit belongs to "
        "its UTC day wherever it was made, so the calendar does not change shape when it is "
        "opened somewhere else.</span></li>"
        "<li><span class=k>events</span><span class=v>rebuilt from artifacts that carry their "
        "own timestamps, each naming the artifact. Nothing is dated by inference: a capability "
        "that is plainly open produces no *opened* event, because nothing durable says "
        "when.</span></li>"
        "<li class=action><span class=k>what a count is not</span><span class=v>evidence that "
        "commits happened. Not of pace, not of quality, and not a verdict on anybody's "
        "week.</span></li>"
        "</ul></section></div>")


def _identity(sites: list) -> str:
    """Which release each project is actually on, and whether its pin verifies."""
    rows = []
    for site in sites:
        pack, pin = site.one("pack"), site.one("pin")
        rows.append(
            f"<tr><td><span class=s>{_ESC(site.name)}</span></td>"
            + (f"<td class='{pack.tone}'><span class='s {pack.tone}'>"
               f"{_ESC(pack.fields.get('version', UNKNOWN))}</span>"
               f"<small>{_ESC(pack.fields.get('state', UNKNOWN))}</small></td>"
               f"<td>{_ESC(pack.fields.get('digest', UNKNOWN))}</td>" if pack else
               f"<td class=unknown><span class='s unknown'>{UNKNOWN}</span></td>"
               f"<td class=unknown>{UNKNOWN}</td>")
            + (f"<td class='{pin.tone}'>{_ESC(pin.value)}</td>"
               f"<td class='{pin.tone}'><span class='s {pin.tone}'>{_ESC(pin.note)}</span></td>"
               f"<td>{_ESC(pin.fields.get('repository', UNKNOWN))}</td>" if pin else
               f"<td class=unknown>{UNKNOWN}</td><td class=unknown>{UNKNOWN}</td>"
               f"<td class=unknown>{UNKNOWN}</td>") + "</tr>")
    if not rows:
        return "<p class=none>No project was named.</p>"
    return ("<div class=tw><table><thead><tr><th>project</th><th>pack in the root</th>"
            "<th>digest</th><th>pinned</th><th>pin verifies</th><th>repository</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


#: The widget catalogue, derived from what the projections actually produced.
#: Nothing here is a widget somebody would like to have: a row exists because a
#: panel exists, and a panel exists because a module answered a question.
def _widgets(sites: list) -> list:
    found = [("global:overview", "Project matrix", "global"),
             ("global:attention", "Attention across projects", "global"),
             ("global:workers", "Workers", "global"),
             ("global:output", "Durable output", "global"),
             ("global:audits", "Audit status", "global"),
             ("global:evidence", "Standing evidence", "global"),
             ("global:capacity", "Capacity", "global"),
             ("global:history", "History & public safety", "global"),
             ("global:identity", "Identity & release", "global"),
             ("global:projects", "Registry", "global"),
             ("global:full-workers", "Every job, in detail", "global"),
             ("global:full-output", "Durable output, in detail", "global"),
             ("global:full-audits", "Audits, in detail", "global"),
             ("global:full-budgets", "Budgets", "global"),
             ("global:full-capacity", "Capacity, compact", "global"),
             ("global:full-evidence", "Standing evidence, compact", "global"),
             ("global:full-history", "History and public safety", "global"),
             ("global:full-identity", "Identity and release, compact", "global"),
             ("global:viz-projects", "Project states", "global"),
             ("global:viz-workers", "Worker states", "global"),
             ("global:viz-attention", "Attention", "global"),
             ("global:viz-audits", "Audit status", "global"),
             ("global:viz-capacity", "Capacity overview", "global"),
             ("global:viz-freshness", "Freshness overview", "global"),
             ("global:viz-budgets", "Budget shape", "global"),
             ("global:viz-budget-meters", "Budget meters", "global"),
             ("global:viz-recent-activity", "Recent repository activity", "global"),
             ("global:viz-recent-events", "Recent runtime pack events", "global")]
    for index, site in enumerate(sites):
        if site.view is None:
            continue
        found.append((f"p{index}:command", f"{site.name} — state & next action", site.name))
        for order, panel in enumerate(site.view.panels):
            found.append((f"p{index}:{order}", f"{site.name} — {panel.title}", site.name))
    return found


def _attention_across(sites: list) -> str:
    """Everything every project marked, with identical readings said once.

    **Grouped, never dropped.** Twelve projects reading through the same
    unfrozen pack each marked the same sentence about it, and the list that is
    supposed to be scannable opened with twelve copies of one fact. A reading
    that several projects share is shown once with every project that has it
    named beside it — the count is on the page and so are the names, so nothing
    is smaller than it was, only less repetitive.
    """
    grouped: dict = {}
    for site in sites:
        if site.view is None:
            grouped.setdefault((Tone.UNKNOWN, f"unreadable — {site.unreadable}"),
                               []).append(site.name)
            continue
        for line in site.view.attention:
            grouped.setdefault((line.tone, line.text), []).append(site.name)
    order = (Tone.BAD, Tone.WARN, Tone.UNKNOWN)
    rows = []
    for (tone, text), names in sorted(
            grouped.items(), key=lambda item: (order.index(item[0][0])
                                               if item[0][0] in order else 9,
                                               -len(item[1]), item[0][1])):
        shared = (f"<span class=s>{_ESC(names[0])}</span>" if len(names) == 1 else
                  f"<span class=s>{len(names)} projects</span>"
                  f"<small>{_ESC(', '.join(names))}</small>")
        rows.append(f"<tr data-tone='{tone}'>" + _td("project", shared)
                    + _td("tone", f"<span class='s {tone}'>{_ESC(tone)}</span>", tone)
                    + _td("what it says", _ESC(text)) + "</tr>")
    if not rows:
        return ("<p class=none>Nothing in any project is marked wrong, unknown or waiting on a "
                "person. That is a reading of these records, not a promise about the runs.</p>")
    return ("<div class=tw><table><thead><tr><th data-sort=text>project</th>"
            "<th data-sort=text>tone</th><th data-sort=text>what it says</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table></div>")


def _widget(node_id: str, title: str, body: str, scope: str = "") -> str:
    return (f"<section data-widget='{_ESC(node_id)}' data-widget-name='{_ESC(title)}'"
            f"{f' data-widget-scope=' + chr(39) + _ESC(scope) + chr(39) if scope else ''}>"
            f"<div class=head><h2>{_ESC(title)}</h2></div>{body}</section>")


def _view(name: str, title: str, question: str, body: str) -> str:
    return (f"<section class=view data-view='{_ESC(name)}'>"
            f"<h2 class=vh>{_ESC(title)}</h2>"
            f"<p class=vq data-optional='questions'>{_ESC(question)}</p>{body}</section>")


_SCRIPT = r"""
// Presentation only. This script reads the page, arranges it, and remembers the
// reader's preference in their own browser under one key. It reaches no record,
// no project, no network and no clock: everything it can show was already in the
// document when the document was written.
//
// Every view is VISIBLE in the delivered HTML. This hides the ones it is not
// showing, on load — so a browser that runs nothing shows a long page with
// everything on it, and no failure of this file can hide an UNKNOWN.
(function () {
  var KEY = 'runtime-pack-console-v1';
  var root = document.documentElement;
  function saved() {
    try {
      var raw = JSON.parse(localStorage.getItem(KEY) || '{}');
      return (raw && typeof raw === 'object' && !Array.isArray(raw)) ? raw : {};
    } catch (e) { return {}; }          // corrupt, absent or refused: defaults
  }
  function keep(next) {
    try { localStorage.setItem(KEY, JSON.stringify(next)); } catch (e) {}
  }
  var prefs = saved();
  function set(key, value) { prefs[key] = value; keep(prefs); }

  // ---- navigation -----------------------------------------------------------
  var views = [].slice.call(document.querySelectorAll('[data-view]'));
  var buttons = [].slice.call(document.querySelectorAll('.go'));
  function show(name) {
    var known = views.some(function (v) { return v.dataset.view === name; });
    if (!known) { name = views.length ? views[0].dataset.view : ''; }
    views.forEach(function (v) { v.hidden = v.dataset.view !== name; });
    buttons.forEach(function (b) {
      b.setAttribute('aria-current', String(b.dataset.goto === name));
    });
    set('view', name);
    // The address names the view, so a view can be linked to and returned to.
    // A hash is presentation: it selects which section of one page is on
    // screen and reaches nothing else.
    try { if (location.hash.slice(1) !== name) { location.hash = name; } } catch (e) {}
    if (window.scrollTo) { window.scrollTo(0, 0); }
  }
  buttons.forEach(function (b) {
    b.addEventListener('click', function () { show(b.dataset.goto); });
  });

  // ---- lens -----------------------------------------------------------------
  var lenses = [].slice.call(document.querySelectorAll('[data-lens]'));
  function lens(name) {
    var known = lenses.some(function (l) { return l.dataset.lens === name; });
    if (!known) { name = ''; }
    if (name) { root.setAttribute('data-theme', name); }
    else { root.removeAttribute('data-theme'); }
    lenses.forEach(function (l) {
      l.setAttribute('aria-pressed', String(l.dataset.lens === name));
    });
    set('lens', name);
  }
  lenses.forEach(function (l) {
    l.addEventListener('click', function () { lens(l.dataset.lens); });
  });

  // ---- presentation settings, and the bounds on them --------------------------
  // Everything here writes a CSS variable and a key in this browser. None of it
  // reaches a record, a project, an evidence file or an authority. The bounds
  // are the interesting part: an operator may make the interface theirs and may
  // not make it lie, so a colour that cannot be read on its surface, and a set
  // of state colours a reader could not tell apart, are refused with a reason.
  var REFUSALS = [];
  function hexish(value) { return /^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$/.test(value || ''); }
  function rgb(value) {
    var v = String(value).replace('#', '');
    if (v.length === 3) { v = v[0]+v[0]+v[1]+v[1]+v[2]+v[2]; }
    return [0, 2, 4].map(function (i) { return parseInt(v.slice(i, i + 2), 16) / 255; });
  }
  function luminance(value) {
    var c = rgb(value).map(function (x) {
      return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }
  function contrast(a, b) {
    var x = luminance(a), y = luminance(b);
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
  }
  function hue(value) {
    var c = rgb(value), hi = Math.max.apply(null, c), lo = Math.min.apply(null, c);
    if (hi === lo) { return null; }
    var s = hi - lo, h;
    if (hi === c[0]) { h = (60 * ((c[1] - c[2]) / s)) % 360; }
    else if (hi === c[1]) { h = 60 * ((c[2] - c[0]) / s) + 120; }
    else { h = 60 * ((c[0] - c[1]) / s) + 240; }
    return (h + 360) % 360;
  }
  function separable(a, b) {
    var ha = hue(a), hb = hue(b);
    var bright = contrast(a, b);
    if (ha === null || hb === null) { return bright >= 1.6; }
    var turn = Math.abs(ha - hb); turn = Math.min(turn, 360 - turn);
    return turn >= 22 || bright >= 1.6;
  }
  function shown(token) {
    return getComputedStyle(root).getPropertyValue('--' + token).trim();
  }
  function refuse(what, why) {
    REFUSALS.push([what, why]);
    var host = document.getElementById('refusals');
    var count = document.getElementById('refusal-count');
    if (host) {
      if (REFUSALS.length === 1) { host.innerHTML = ''; }
      var li = document.createElement('li');
      li.className = 'bad';
      li.innerHTML = '<span class=k></span><span class=v></span>';
      li.querySelector('.k').textContent = what;
      li.querySelector('.v').textContent = why;
      host.appendChild(li);
    }
    if (count) { count.textContent = REFUSALS.length + ' refused'; count.className = 'chip bad'; }
  }

  function settings() {
    var s = prefs.settings;
    return (s && typeof s === 'object' && !Array.isArray(s)) ? s : {};
  }
  function applyOne(token, value) {
    if (value === null || value === undefined || value === '') {
      root.style.removeProperty('--' + token);
    } else {
      root.style.setProperty('--' + token, value);
    }
  }
  //: The bound for one proposed value, decided against what the page would
  //: actually look like with it. Returns '' when it may be applied.
  function objection(token, value) {
    var kinds = {};
    [].forEach.call(document.querySelectorAll('[data-token]'), function (input) {
      kinds[input.dataset.token] = input.dataset.kind || 'size';
    });
    var kind = kinds[token] || 'size';
    if (kind === 'text' || kind === 'surface' || kind === 'line' || kind === 'semantic') {
      if (!hexish(value)) { return 'that is not a colour this page can use'; }
    }
    var MEANINGS = ['bad', 'warn', 'unknown', 'good'];
    if (kind === 'text' || kind === 'semantic') {
      var surfaces = ['panel', 'panel-2', 'ground'].map(shown).filter(hexish);
      for (var i = 0; i < surfaces.length; i++) {
        if (contrast(value, surfaces[i]) < 4.5) {
          return 'unreadable on the panels it is drawn on (' +
                 contrast(value, surfaces[i]).toFixed(2) + ':1, and 4.5 is the floor)';
        }
      }
    }
    if (kind === 'surface') {
      // EVERYTHING DRAWN ON IT, not only the two neutral texts. Checking a new
      // panel against ink and dim alone accepted `#333333`, on which all four
      // state colours fell below the floor — the page then drew a defect, a
      // warning and an unestablished reading nobody could read, and said
      // nothing. Found by an independent reader.
      var drawn = ['ink', 'dim', 'accent'].concat(MEANINGS).map(shown).filter(hexish);
      for (var j = 0; j < drawn.length; j++) {
        if (contrast(value, drawn[j]) < 4.5) {
          return 'what is drawn on it would be unreadable (' +
                 contrast(value, drawn[j]).toFixed(2) + ':1 against one of the state colours, ' +
                 'and 4.5 is the floor)';
        }
      }
    }
    if (kind === 'semantic' || token === 'accent') {
      // THE ACCENT TOO. It was checked for contrast and never for confusion, so
      // it could be set to exactly the defect red and every selected control
      // then looked like a defect.
      var others = MEANINGS.concat(['action', 'accent']);
      for (var k = 0; k < others.length; k++) {
        if (others[k] === token || (token === 'accent' && others[k] === 'action')) { continue; }
        var other = shown(others[k]);
        if (hexish(other) && !separable(value, other)) {
          return 'a reader could not tell it from ' + others[k] +
                 ', and those are the colours they look for';
        }
      }
    }
    return '';
  }
  function applySettings() {
    var chosen = settings();
    Object.keys(chosen).forEach(function (token) {
      var value = chosen[token];
      var input = document.querySelector('[data-token="' + token + '"]');
      if (input && input.type === 'range') {
        var low = Number(input.min), high = Number(input.max);
        var number = Number(String(value).replace(/[^0-9.\-]/g, ''));
        if (!isFinite(number)) { refuse(token, 'not a number'); return; }
        var held = Math.min(high, Math.max(low, number));
        if (held !== number) {
          refuse(token, 'outside the range this page stays usable in (' + low + '–' + high +
                        '), held at ' + held);
        }
        applyOne(token, held + (input.dataset.unit || ''));
        return;
      }
      applyOne(token, value);
    });
    // Judge colours AFTER the surfaces are in place, so a pair is checked as it
    // will actually be drawn rather than against the lens it replaced.
    Object.keys(chosen).forEach(function (token) {
      var input = document.querySelector('[data-token="' + token + '"]');
      if (!input || input.type === 'range') { return; }
      var why = objection(token, chosen[token]);
      if (why) { refuse(token, why); applyOne(token, null); }
    });
  }
  function setSetting(token, value) {
    var chosen = settings();
    if (value === null) { delete chosen[token]; } else { chosen[token] = value; }
    prefs.settings = chosen;
    keep(prefs);
    root.removeAttribute('style');
    REFUSALS = [];
    var host = document.getElementById('refusals');
    var count = document.getElementById('refusal-count');
    if (host) {
      host.innerHTML = '<li class=muted><span class=v>A setting this page would not accept '
        + 'appears here with the reason. Nothing is applied silently and nothing is discarded '
        + 'silently.</span></li>';
    }
    if (count) { count.textContent = 'none'; count.className = 'chip'; }
    applySettings();
    syncControls();
  }
  function syncControls() {
    var chosen = settings();
    [].forEach.call(document.querySelectorAll('[data-token]'), function (input) {
      var token = input.dataset.token;
      var live = shown(token);
      if (input.type === 'color') {
        input.value = hexish(live) ? (live.length === 4
          ? '#' + live[1] + live[1] + live[2] + live[2] + live[3] + live[3] : live) : '#000000';
      } else if (input.type === 'range') {
        input.value = parseFloat(live) || input.value;
        var echo = document.querySelector('[data-shows="' + token + '"]');
        if (echo) { echo.textContent = live || '—'; }
      } else if (input.tagName === 'SELECT') {
        input.value = chosen[token] || input.value;
      }
      input.closest('.set') && input.closest('.set').classList.toggle('changed', token in chosen);
    });
  }
  [].forEach.call(document.querySelectorAll('[data-token]'), function (input) {
    var event = input.type === 'range' ? 'input' : 'change';
    input.addEventListener(event, function () {
      setSetting(input.dataset.token,
                 input.value + (input.type === 'range' ? (input.dataset.unit || '') : ''));
    });
  });
  [].forEach.call(document.querySelectorAll('[data-clear]'), function (b) {
    b.addEventListener('click', function () { setSetting(b.dataset.clear, null); });
  });

  // ---- optional sections ------------------------------------------------------
  // Only what the page declared optional. There is no control here for anything
  // that carries a defect, an unestablished reading, a blocker, a stale reading
  // or a human decision, and the page is rendered without one.
  function applyHidden() {
    var hidden = Array.isArray(prefs.hidden) ? prefs.hidden : [];
    [].forEach.call(document.querySelectorAll('[data-optional]'), function (node) {
      node.hidden = hidden.indexOf(node.dataset.optional) >= 0;
    });
    [].forEach.call(document.querySelectorAll('[data-show]'), function (box) {
      box.checked = hidden.indexOf(box.dataset.show) < 0;
    });
  }
  [].forEach.call(document.querySelectorAll('[data-show]'), function (box) {
    box.addEventListener('change', function () {
      var hidden = Array.isArray(prefs.hidden) ? prefs.hidden.slice() : [];
      var at = hidden.indexOf(box.dataset.show);
      if (box.checked && at >= 0) { hidden.splice(at, 1); }
      if (!box.checked && at < 0) { hidden.push(box.dataset.show); }
      prefs.hidden = hidden; keep(prefs); applyHidden();
    });
  });

  // ---- presets: a whole look, saved and switched ------------------------------
  function presets() {
    var all = prefs.presets;
    return (all && typeof all === 'object' && !Array.isArray(all)) ? all : {};
  }
  function anyLook(name) {
    var saved = presets();
    return Object.prototype.hasOwnProperty.call(saved, name) ? saved[name]
                                                             : BUILT_IN_LOOKS[name];
  }
  function paintPresets() {
    var host = document.getElementById('preset-list');
    if (!host) { return; }
    host.innerHTML = '';
    var names = Object.keys(BUILT_IN_LOOKS).concat(Object.keys(presets()))
      .filter(function (n, i, a) { return a.indexOf(n) === i; });
    names.forEach(function (name) {
      var b = document.createElement('button');
      b.textContent = name;
      b.setAttribute('aria-pressed', String(name === prefs.preset));
      b.addEventListener('click', function () {
        var one = anyLook(name) || {};
        prefs.settings = (one.settings && typeof one.settings === 'object') ? one.settings : {};
        prefs.lens = typeof one.lens === 'string' ? one.lens : '';
        prefs.density = typeof one.density === 'string' ? one.density : 'normal';
        prefs.hidden = Array.isArray(one.hidden) ? one.hidden : [];
        prefs.preset = name;
        keep(prefs);
        root.removeAttribute('style');
        lens(prefs.lens); density(prefs.density); applySettings(); applyHidden();
        syncControls(); paintPresets();
      });
      host.appendChild(b);
    });
    var current = document.getElementById('preset-current');
    if (current) { current.textContent = prefs.preset || 'unsaved'; }
  }
  function savePreset(name) {
    var all = presets();
    all[name] = { settings: settings(), lens: prefs.lens || '',
                  density: prefs.density || 'normal',
                  hidden: Array.isArray(prefs.hidden) ? prefs.hidden : [] };
    prefs.presets = all; prefs.preset = name; keep(prefs); paintPresets();
  }
  var namer = document.getElementById('preset-name');
  var saver = document.getElementById('preset-save');
  if (saver && namer) {
    saver.addEventListener('click', function () {
      savePreset((namer.value || '').trim().slice(0, 40) || 'untitled');
    });
  }
  var duper = document.getElementById('preset-dup');
  if (duper) {
    duper.addEventListener('click', function () {
      savePreset(((prefs.preset || 'untitled') + ' copy').slice(0, 40));
    });
  }
  var dropper = document.getElementById('preset-del');
  if (dropper) {
    dropper.addEventListener('click', function () {
      var all = presets(); delete all[prefs.preset];
      prefs.presets = all; prefs.preset = ''; keep(prefs); paintPresets();
    });
  }
  var lensReset = document.getElementById('lens-reset');
  if (lensReset) {
    lensReset.addEventListener('click', function () {
      prefs.settings = {}; prefs.hidden = []; keep(prefs);
      root.removeAttribute('style');
      REFUSALS = []; applySettings(); applyHidden(); syncControls();
    });
  }
  var allReset = document.getElementById('all-reset');
  if (allReset) {
    allReset.addEventListener('click', function () {
      prefs = {}; keep(prefs);
      root.removeAttribute('style');
      REFUSALS = [];
      lens(''); density('normal'); applySettings(); applyHidden(); syncControls();
      paintPresets(); rebuildLayoutPresets(); paint(); show('overview');
    });
  }
  var lensDefault = document.getElementById('lens-default');
  if (lensDefault) {
    lensDefault.addEventListener('change', function () { lens(lensDefault.value); });
  }
  var densitySelect = document.getElementById('density-set');
  if (densitySelect) {
    densitySelect.addEventListener('change', function () { density(densitySelect.value); });
  }

  // ---- density and accent ---------------------------------------------------
  function density(name) {
    if (['compact', 'normal', 'comfortable'].indexOf(name) < 0) { name = 'normal'; }
    document.body.setAttribute('data-density', name);
    [].forEach.call(document.querySelectorAll('[data-density-set]'), function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.densitySet === name));
    });
    var picker = document.getElementById('density-set');
    if (picker && picker.value !== name) { picker.value = name; }
    set('density', name);
  }
  [].forEach.call(document.querySelectorAll('[data-density-set]'), function (b) {
    b.addEventListener('click', function () { density(b.dataset.densitySet); });
  });
  function accent(colour) {
    // A CSS colour and nothing else: anything the browser does not parse is
    // dropped rather than written into a style attribute.
    if (!/^#[0-9a-fA-F]{3,8}$/.test(colour || '')) { colour = ''; }
    if (colour) { root.style.setProperty('--accent', colour); }
    else { root.style.removeProperty('--accent'); }
    set('accent', colour);
  }
  [].forEach.call(document.querySelectorAll('[data-accent]'), function (b) {
    b.addEventListener('click', function () { accent(b.dataset.accent); });
  });

  // ---- filtering and sorting the tables --------------------------------------
  function filterRows() {
    var box = document.getElementById('overview-search');
    var needle = (box && box.value || '').toLowerCase();
    var tone = document.querySelector('[data-tone-filter][aria-pressed="true"]');
    var want = tone ? tone.dataset.toneFilter : '';
    [].forEach.call(document.querySelectorAll('#overview-table tbody tr'), function (tr) {
      var text = tr.textContent.toLowerCase();
      var toneOk = !want || tr.dataset.tone === want ||
        (want === 'attention' && Number(tr.dataset.attention || 0) > 0);
      tr.hidden = !(text.indexOf(needle) >= 0 && toneOk);
    });
  }
  var search = document.getElementById('overview-search');
  if (search) { search.addEventListener('input', filterRows); }
  [].forEach.call(document.querySelectorAll('[data-tone-filter]'), function (b) {
    b.addEventListener('click', function () {
      var on = b.getAttribute('aria-pressed') === 'true';
      [].forEach.call(document.querySelectorAll('[data-tone-filter]'), function (o) {
        o.setAttribute('aria-pressed', 'false');
      });
      b.setAttribute('aria-pressed', String(!on));
      filterRows();
    });
  });
  [].forEach.call(document.querySelectorAll('th[data-sort]'), function (th) {
    th.addEventListener('click', function () {
      var table = th.closest('table');
      var body = table.tBodies[0];
      var index = [].indexOf.call(th.parentNode.children, th);
      var numeric = th.dataset.sort === 'num';
      var down = th.getAttribute('data-dir') === 'down';
      [].forEach.call(table.querySelectorAll('th'), function (o) {
        o.removeAttribute('data-dir');
      });
      th.setAttribute('data-dir', down ? 'up' : 'down');
      var rows = [].slice.call(body.rows);
      rows.sort(function (a, b) {
        var x = (a.cells[index] || {}).textContent || '';
        var y = (b.cells[index] || {}).textContent || '';
        var out = numeric ? (parseFloat(x) || 0) - (parseFloat(y) || 0)
                          : x.localeCompare(y);
        return down ? -out : out;
      });
      rows.forEach(function (r) { body.appendChild(r); });
    });
  });

  // ---- custom views ----------------------------------------------------------
  // A layout is a list of widget ids and spans. It is a preference in this
  // browser: it selects and arranges sections that are already on this page,
  // and it can neither invent one nor change what one says. A widget id that no
  // longer exists is dropped; an impossible span is clamped; a layout that will
  // not parse is replaced by the default. None of that can fail loudly, because
  // a broken preference must never cost a reader the page.
  var canvas = document.getElementById('canvas');
  function layouts() {
    var all = prefs.layouts;
    return (all && typeof all === 'object' && !Array.isArray(all)) ? all : {};
  }
  function anyLayout(name) {
    var saved = layouts();
    return Object.prototype.hasOwnProperty.call(saved, name) ? saved[name] : BUILT_IN[name];
  }
  // An arrangement to start from, used only when this browser has never been
  // given one. Choosing to have none is a choice and is kept.
  var OPENING = [{ id: 'global:overview', span: 2 }, { id: 'global:attention', span: 2 }];
  // Arrangements worth starting from. They are presentation and nothing else:
  // each is a list of sections already on this page, in an order somebody found
  // useful. An operator may switch to one, edit it, and save it under their own
  // name; the built-in stays where it was.
  // A look the founder can always get back to in one click. It is not an
  // example: it is exactly what the release ships in — monochrome, warm
  // graphite, a restrained amber accent — named so that any amount of
  // customising has a way home.
  var BUILT_IN_LOOKS = {
    'founder': { settings: {}, lens: '', density: 'normal', hidden: [] }
  };
  var BUILT_IN = {
    'founder control room': { cols: 3, scope: 'all', density: 'normal', widgets: [
      { id: 'global:overview', span: 3 }, { id: 'global:attention', span: 2 },
      { id: 'global:workers', span: 1 }, { id: 'global:audits', span: 1 },
      { id: 'global:capacity', span: 1 }, { id: 'global:output', span: 1 },
      { id: 'global:identity', span: 3 }] },
    'minimal overview': { cols: 1, widgets: [
      { id: 'global:overview', span: 1 }] },
    'daily operations': { cols: 2, widgets: [
      { id: 'global:overview', span: 2 }, { id: 'global:attention', span: 2 },
      { id: 'global:workers', span: 1 }, { id: 'global:capacity', span: 1 }] },
    'full control room': { cols: 3, widgets: [
      { id: 'global:overview', span: 3 }, { id: 'global:attention', span: 2 },
      { id: 'global:workers', span: 1 }, { id: 'global:output', span: 1 },
      { id: 'global:audits', span: 1 }, { id: 'global:capacity', span: 1 },
      { id: 'global:full-budgets', span: 1 }, { id: 'global:identity', span: 2 }] },
    'audit and release': { cols: 2, widgets: [
      { id: 'global:audits', span: 2 }, { id: 'global:evidence', span: 1 },
      { id: 'global:identity', span: 1 }, { id: 'global:history', span: 2 }] },
    'worker operations': { cols: 2, widgets: [
      { id: 'global:workers', span: 2 }, { id: 'global:output', span: 2 },
      { id: 'global:capacity', span: 1 }, { id: 'global:attention', span: 1 }] },
    'multi-project health': { cols: 2, widgets: [
      { id: 'global:overview', span: 2 }, { id: 'global:full-evidence', span: 1 },
      { id: 'global:full-budgets', span: 1 }, { id: 'global:history', span: 1 },
      { id: 'global:identity', span: 1 }] }
  };
  function current() {
    var name = typeof prefs.layout === 'string' ? prefs.layout : 'default';
    var all = layouts();
    var one = anyLayout(name);
    var chosen = Array.isArray(one && one.widgets) ? one.widgets
               : (prefs.layouts === undefined ? OPENING : []);
    return { name: name, widgets: chosen,
             cols: Math.min(6, Math.max(1, Number(one && one.cols) || 2)),
             scope: typeof (one && one.scope) === 'string' ? one.scope : 'all',
             density: typeof (one && one.density) === 'string' ? one.density : 'normal',
             filter: typeof (one && one.filter) === 'string' ? one.filter : '' };
  }
  function paint() {
    if (!canvas) { return; }
    var view = current();
    canvas.style.setProperty('--cols', String(view.cols));
    canvas.innerHTML = '';
    var placed = 0;
    view.widgets.forEach(function (entry) {
      var id = typeof entry === 'string' ? entry : (entry && entry.id);
      var span = Math.min(view.cols, Math.max(1, Number(entry && entry.span) || 1));
      var source = document.querySelector('[data-widget="' + String(id).replace(/"/g, '') + '"]');
      if (!source) { return; }                      // a widget that is no longer here
      var copy = source.cloneNode(true);
      copy.removeAttribute('data-widget');
      copy.style.setProperty('--span', String(span));
      var tall = Math.min(3, Math.max(1, Number(entry && entry.tall) || 1));
      copy.style.setProperty('--tall', String(tall));
      // SCOPE AND FILTER ARE PRESENTATION. They hide rows in this copy; the
      // rows are still in the widget they were copied from, in its own view.
      // Nothing is removed from the page, and nothing marked as a defect, an
      // unestablished reading or a blocker is hidden anywhere.
      var needle = (view.filter || '').toLowerCase().trim();
      var only = view.scope && view.scope !== 'all' ? view.scope : null;
      [].forEach.call(copy.querySelectorAll('tbody tr'), function (tr) {
        var text = tr.textContent.toLowerCase();
        var urgent = ['bad', 'warn', 'unknown'].indexOf(tr.dataset.tone) >= 0;
        var scoped = only === null || tr.dataset.project === only ||
                     tr.querySelector('[data-goto="project:' + only + '"]') !== null;
        tr.hidden = !urgent && (!scoped || (needle && text.indexOf(needle) < 0));
      });
      canvas.appendChild(copy);
      placed += 1;
    });
    if (!placed) {
      var note = document.createElement('div');
      note.className = 'empty';
      note.textContent = 'No widget is selected. Tick one on the left; the arrangement is kept '
        + 'in this browser and is not part of any project’s state.';
      canvas.appendChild(note);
    }
    [].forEach.call(document.querySelectorAll('[data-pick]'), function (box) {
      box.checked = view.widgets.some(function (e) {
        return (typeof e === 'string' ? e : e && e.id) === box.dataset.pick;
      });
    });
    canvas.setAttribute('data-density', view.density || 'normal');
    var label = document.getElementById('layout-name');
    if (label) { label.textContent = view.name; }
    var scopeBox = document.getElementById('layout-scope');
    if (scopeBox && scopeBox.value !== (view.scope || 'all')) {
      scopeBox.value = view.scope || 'all';
    }
    var densityBox = document.getElementById('layout-density');
    if (densityBox && densityBox.value !== (view.density || 'normal')) {
      densityBox.value = view.density || 'normal';
    }
    var filterBox = document.getElementById('layout-filter');
    if (filterBox && filterBox.value !== (view.filter || '')) {
      filterBox.value = view.filter || '';
    }
  }
  function edit(change) {
    var view = current();
    var all = layouts();
    all[view.name] = change({ widgets: view.widgets.slice(), cols: view.cols,
                              scope: view.scope, density: view.density,
                              filter: view.filter });
    prefs.layouts = all;
    prefs.layout = view.name;
    keep(prefs);
    paint();
  }
  [].forEach.call(document.querySelectorAll('[data-pick]'), function (box) {
    box.addEventListener('change', function () {
      edit(function (v) {
        var id = box.dataset.pick;
        var at = v.widgets.map(function (e) {
          return typeof e === 'string' ? e : e && e.id;
        }).indexOf(id);
        if (box.checked && at < 0) { v.widgets.push({ id: id, span: 1 }); }
        if (!box.checked && at >= 0) { v.widgets.splice(at, 1); }
        return v;
      });
    });
  });
  [].forEach.call(document.querySelectorAll('[data-move]'), function (b) {
    b.addEventListener('click', function () {
      edit(function (v) {
        var id = b.dataset.move;
        var by = Number(b.dataset.by) || 0;
        var at = v.widgets.map(function (e) {
          return typeof e === 'string' ? e : e && e.id;
        }).indexOf(id);
        if (at < 0) { return v; }
        var to = Math.min(v.widgets.length - 1, Math.max(0, at + by));
        v.widgets.splice(to, 0, v.widgets.splice(at, 1)[0]);
        return v;
      });
    });
  });
  [].forEach.call(document.querySelectorAll('[data-span]'), function (b) {
    b.addEventListener('click', function () {
      edit(function (v) {
        var id = b.dataset.span;
        v.widgets = v.widgets.map(function (e) {
          var entry = typeof e === 'string' ? { id: e, span: 1 } : e;
          if (entry.id === id) {
            entry.span = (Number(entry.span) || 1) % Math.max(1, v.cols) + 1;
          }
          return entry;
        });
        return v;
      });
    });
  });
  [].forEach.call(document.querySelectorAll('[data-tall]'), function (b) {
    b.addEventListener('click', function () {
      edit(function (v) {
        v.widgets = v.widgets.map(function (e) {
          var entry = typeof e === 'string' ? { id: e, span: 1 } : e;
          if (entry.id === b.dataset.tall) {
            entry.tall = (Number(entry.tall) || 1) % 3 + 1;
          }
          return entry;
        });
        return v;
      });
    });
  });
  var scope = document.getElementById('layout-scope');
  if (scope) {
    scope.addEventListener('change', function () {
      edit(function (v) { v.scope = scope.value; return v; });
    });
  }
  var canvasDensity = document.getElementById('layout-density');
  if (canvasDensity) {
    canvasDensity.addEventListener('change', function () {
      edit(function (v) { v.density = canvasDensity.value; return v; });
    });
  }
  var layoutFilter = document.getElementById('layout-filter');
  if (layoutFilter) {
    layoutFilter.addEventListener('input', function () {
      edit(function (v) { v.filter = layoutFilter.value; return v; });
    });
  }
  var dupLayout = document.getElementById('layout-dup');
  if (dupLayout) {
    dupLayout.addEventListener('click', function () {
      var view = current();
      var all = layouts();
      all[(view.name + ' copy').slice(0, 40)] = {
        cols: view.cols, widgets: view.widgets.slice(), scope: view.scope,
        density: view.density, filter: view.filter };
      prefs.layouts = all; prefs.layout = (view.name + ' copy').slice(0, 40);
      keep(prefs); rebuildLayoutPresets(); paint();
    });
  }
  var renameLayout = document.getElementById('layout-rename');
  if (renameLayout && naming) {
    renameLayout.addEventListener('click', function () {
      var to = (naming.value || '').trim().slice(0, 40);
      if (!to) { return; }
      var view = current();
      var all = layouts();
      all[to] = { cols: view.cols, widgets: view.widgets.slice(), scope: view.scope,
                  density: view.density, filter: view.filter };
      delete all[view.name];
      prefs.layouts = all; prefs.layout = to; keep(prefs);
      rebuildLayoutPresets(); paint();
    });
  }
  [].forEach.call(document.querySelectorAll('[data-cols]'), function (b) {
    b.addEventListener('click', function () {
      edit(function (v) { v.cols = Math.min(6, Math.max(1, Number(b.dataset.cols) || 2));
                          return v; });
    });
  });
  var naming = document.getElementById('layout-new');
  var making = document.getElementById('layout-create');
  if (making && naming) {
    making.addEventListener('click', function () {
      var name = (naming.value || '').trim().slice(0, 40) || 'untitled';
      var all = layouts();
      all[name] = { widgets: current().widgets.slice(), cols: current().cols };
      prefs.layouts = all; prefs.layout = name; keep(prefs);
      rebuildLayoutPresets(); paint();
    });
  }
  function rebuildLayoutPresets() {
    var host = document.getElementById('layout-presets');
    if (!host) { return; }
    host.innerHTML = '';
    Object.keys(BUILT_IN).concat(Object.keys(layouts())).concat(['default'])
      .filter(function (n, i, a) { return a.indexOf(n) === i; }).forEach(function (name) {
      var b = document.createElement('button');
      b.textContent = name;
      b.setAttribute('aria-pressed', String(name === current().name));
      b.addEventListener('click', function () {
        prefs.layout = name; keep(prefs); rebuildLayoutPresets(); paint();
      });
      host.appendChild(b);
    });
  }
  var dropping = document.getElementById('layout-delete');
  if (dropping) {
    dropping.addEventListener('click', function () {
      var all = layouts();
      delete all[current().name];
      prefs.layouts = all; prefs.layout = 'default'; keep(prefs);
      rebuildLayoutPresets(); paint();
    });
  }
  var resetting = document.getElementById('layout-reset');
  if (resetting) {
    resetting.addEventListener('click', function () {
      prefs = {}; keep(prefs);
      lens(''); density('normal'); accent('');
      rebuildLayoutPresets(); paint(); show('overview');
    });
  }

  // ---- the overview's three densities -----------------------------------------
  function overviewDensity(name) {
    if (['minimal', 'balanced', 'full'].indexOf(name) < 0) { name = 'balanced'; }
    var host = document.querySelector('[data-view="overview"]');
    if (host) { host.setAttribute('data-od', name); }
    [].forEach.call(document.querySelectorAll('[data-od]'), function (b) {
      if (b.tagName === 'BUTTON') {
        b.setAttribute('aria-pressed', String(b.dataset.od === name));
      }
    });
    set('od', name);
  }
  [].forEach.call(document.querySelectorAll('button[data-od]'), function (b) {
    b.addEventListener('click', function () { overviewDensity(b.dataset.od); });
  });
  function allDepth(name) {
    if (['minimal', 'full'].indexOf(name) < 0) { name = 'full'; }
    var host = document.querySelector('[data-view="all"]');
    if (host) { host.setAttribute('data-ad', name); }
    [].forEach.call(document.querySelectorAll('button[data-ad]'), function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.ad === name));
    });
    set('ad', name);
  }
  [].forEach.call(document.querySelectorAll('button[data-ad]'), function (b) {
    b.addEventListener('click', function () { allDepth(b.dataset.ad); });
  });

  // ---- the control room's chrome, and the screen it wants ----------------------
  function chrome(on) {
    document.body.setAttribute('data-chrome', on ? 'on' : 'off');
    var b = document.getElementById('chrome-toggle');
    if (b) { b.textContent = on ? 'hide the chrome' : 'bring the chrome back'; }
    set('chrome', on ? 'on' : 'off');
  }
  var chromeButton = document.getElementById('chrome-toggle');
  if (chromeButton) {
    chromeButton.addEventListener('click', function () {
      chrome(document.body.getAttribute('data-chrome') === 'off');
    });
  }
  var full = document.getElementById('fullscreen');
  if (full) {
    full.addEventListener('click', function () {
      // A convenience. Everything works in an ordinary window, and a browser
      // that refuses this changes nothing about what is on the page.
      try {
        if (document.fullscreenElement) { document.exitFullscreen(); }
        else if (document.documentElement.requestFullscreen) {
          document.documentElement.requestFullscreen();
        }
      } catch (e) {}
    });
  }

  // ---- anchors inside the one-page views ---------------------------------------
  [].forEach.call(document.querySelectorAll('[data-anchor]'), function (b) {
    b.addEventListener('click', function () {
      var target = document.getElementById(b.dataset.anchor);
      if (target && target.scrollIntoView) { target.scrollIntoView({block: 'start'}); }
    });
  });

  // ---- quick find ---------------------------------------------------------------
  var finder = document.getElementById('finder');
  var findInput = document.getElementById('find-input');
  var findList = document.getElementById('find-list');
  function openFinder(on) {
    if (!finder) { return; }
    finder.classList.toggle('open', !!on);
    if (on && findInput) { findInput.value = ''; filterFind(); findInput.focus(); }
  }
  function rows() { return [].slice.call(findList ? findList.children : []); }
  function filterFind() {
    var needle = (findInput && findInput.value || '').toLowerCase().trim();
    var shownCount = 0;
    rows().forEach(function (li) {
      var hit = !needle || (li.dataset.find || '').indexOf(needle) >= 0;
      li.hidden = !hit || shownCount >= 40;
      li.classList.remove('on');
      if (hit) { shownCount += 1; }
    });
    var first = rows().filter(function (li) { return !li.hidden; })[0];
    if (first) { first.classList.add('on'); }
  }
  function goFirst() {
    var on = rows().filter(function (li) { return li.classList.contains('on'); })[0]
          || rows().filter(function (li) { return !li.hidden; })[0];
    if (on) { show(on.dataset.goto); openFinder(false); }
  }
  if (findInput) {
    findInput.addEventListener('input', filterFind);
    findInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { goFirst(); }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        var open = rows().filter(function (li) { return !li.hidden; });
        var at = open.findIndex(function (li) { return li.classList.contains('on'); });
        var to = Math.min(open.length - 1, Math.max(0, at + (e.key === 'ArrowDown' ? 1 : -1)));
        open.forEach(function (li) { li.classList.remove('on'); });
        if (open[to]) { open[to].classList.add('on'); open[to].scrollIntoView({block: 'nearest'}); }
      }
    });
  }
  rows().forEach(function (li) {
    li.addEventListener('click', function () { show(li.dataset.goto); openFinder(false); });
  });
  var findClose = document.getElementById('find-close');
  if (findClose) { findClose.addEventListener('click', function () { openFinder(false); }); }
  document.addEventListener('keydown', function (e) {
    var typing = /^(INPUT|SELECT|TEXTAREA)$/.test((e.target || {}).tagName || '');
    if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !typing)) {
      e.preventDefault(); openFinder(true);
    }
    if (e.key === 'Escape') {
      if (finder && finder.classList.contains('open')) { openFinder(false); }
      else if (document.body.getAttribute('data-chrome') === 'off') { chrome(true); }
    }
  });

  // ---- the two histories --------------------------------------------------------
  // The scale chooses how much of the calendar to show and the mode chooses
  // which population it colours. Both are presentation: neither changes a
  // count, and the exact numbers are in the cell's own label either way.
  function activityMode(name) {
    if (['local', 'remote', 'combined'].indexOf(name) < 0) { name = 'combined'; }
    [].forEach.call(document.querySelectorAll('.actmode'), function (block) {
      block.classList.toggle('on', block.dataset.actmode === name);
    });
    [].forEach.call(document.querySelectorAll('button[data-actmode]'), function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.actmode === name));
    });
    set('actmode', name);
  }
  [].forEach.call(document.querySelectorAll('button[data-actmode]'), function (b) {
    b.addEventListener('click', function () { activityMode(b.dataset.actmode); });
  });

  var SPAN = { year: 366, month: 31, week: 7, day: 1 };
  var period = { scale: 'year', from: '', to: '' };
  var fromBox = document.getElementById('history-from');
  var toBox = document.getElementById('history-to');

  // ONE WINDOW, whichever control set it. A scale is the last N days ending at
  // the most recent one; a range is two UTC dates. Both narrow the calendar and
  // the timeline together, because two histories on one page that disagree
  // about the period are two pages.
  function applyPeriod() {
    var custom = !!(period.from || period.to);
    var from = period.from, to = period.to;
    if (!custom) {
      var days = [].slice.call(document.querySelectorAll('.calendar .cell[data-day]'))
        .map(function (c) { return c.dataset.day; }).filter(Boolean).sort();
      var last = days[days.length - 1];
      if (last) {
        var end = new Date(last + 'T00:00:00Z');
        end.setUTCDate(end.getUTCDate() - (SPAN[period.scale] - 1));
        from = end.toISOString().slice(0, 10);
      }
    }
    [].forEach.call(document.querySelectorAll('.calendar .cell[data-day]'), function (cell) {
      var day = cell.dataset.day;
      cell.hidden = !!(from && day < from) || !!(to && day > to);
    });
    [].forEach.call(document.querySelectorAll('button[data-scale]'), function (b) {
      // `most recent` is an action and not a period: it never reads as chosen.
      b.setAttribute('aria-pressed',
        String(b.id !== 'history-today' && !custom && b.dataset.scale === period.scale));
    });
    var says = document.getElementById('history-period');
    if (says) {
      says.textContent = custom
        ? (from || 'the beginning') + ' to ' + (to || 'the most recent day')
        : period.scale;
    }
    // At a day or a week a calendar is the wrong shape; the timeline under it
    // is what a reader wants, so the events narrow to the same window.
    filterEvents(from, to);
  }

  function activityScale(name) {
    if (!SPAN[name]) { name = 'year'; }
    period.scale = name;
    period.from = period.to = '';
    if (fromBox) { fromBox.value = ''; }
    if (toBox) { toBox.value = ''; }
    set('scale', name);
    set('from', '');
    set('to', '');
    applyPeriod();
  }
  [].forEach.call(document.querySelectorAll('button[data-scale]'), function (b) {
    b.addEventListener('click', function () { activityScale(b.dataset.scale); });
  });
  function activityRange() {
    period.from = fromBox ? fromBox.value : '';
    period.to = toBox ? toBox.value : '';
    set('from', period.from);
    set('to', period.to);
    applyPeriod();
  }
  [fromBox, toBox].forEach(function (box) {
    if (box) { box.addEventListener('change', activityRange); }
  });

  var eventKind = '';
  function filterEvents(from, to) {
    var project = document.getElementById('history-project');
    // BY INDEX. Two projects may share a name, and comparing the label then
    // showed both of them under either one.
    var only = project && project.value !== 'all' ? project.value : '';
    [].forEach.call(document.querySelectorAll('#history-events tbody tr'), function (tr) {
      var byKind = !eventKind || tr.dataset.kind === eventKind;
      var byProject = !only || tr.dataset.at === only;
      // An event with no readable time is never hidden by a period: it has no
      // period, and dropping it would be the page losing a reading.
      var day = tr.dataset.day;
      var byDay = !day || ((!from || day >= from) && (!to || day <= to));
      tr.hidden = !(byKind && byProject && byDay);
    });
  }
  [].forEach.call(document.querySelectorAll('button[data-eventkind]'), function (b) {
    b.addEventListener('click', function () {
      eventKind = b.dataset.eventkind;
      [].forEach.call(document.querySelectorAll('button[data-eventkind]'), function (o) {
        o.setAttribute('aria-pressed', String(o.dataset.eventkind === eventKind));
      });
      applyPeriod();
    });
  });
  var historyProject = document.getElementById('history-project');
  if (historyProject) {
    historyProject.addEventListener('change', function () {
      applyPeriod();
      set('historyProject', historyProject.value);
    });
  }

  // ---- the day inspector ----------------------------------------------------------
  // Selecting a day says what happened on it, from both histories. A tooltip
  // with a number in it is not an inspector.
  function inspect(day) {
    var host = document.getElementById('day-inspector');
    if (!host || !day) { return; }
    var cells = [].slice.call(document.querySelectorAll('.calendar .cell[data-day="' + day
                                                        + '"]'));
    var local = 0, remote = 0, only = 0;
    cells.forEach(function (c) {
      local = Math.max(local, Number(c.dataset.local) || 0);
      remote = Math.max(remote, Number(c.dataset.remote) || 0);
      only = Math.max(only, Number(c.dataset.only) || 0);
    });
    var events = [].slice.call(document.querySelectorAll('#history-events tbody tr'))
      .filter(function (tr) { return tr.dataset.day === day; });
    var kinds = {};
    events.forEach(function (tr) {
      kinds[tr.dataset.kind] = (kinds[tr.dataset.kind] || 0) + 1;
    });
    var listed = Object.keys(kinds).map(function (k) {
      return k + ' ' + kinds[k]; }).join(' · ') || 'nothing durable dates an event on this day';
    host.innerHTML = '';
    var title = document.createElement('h4');
    title.textContent = day + ' (UTC)';
    var repo = document.createElement('p');
    repo.className = 'none';
    repo.style.padding = '0';
    repo.textContent = 'repository: ' + local + ' local, ' + remote
      + ' represented by the remote, ' + only + ' only here';
    var pack = document.createElement('p');
    pack.className = 'none';
    pack.style.padding = '0';
    pack.textContent = 'runtime pack: ' + listed;
    host.appendChild(title); host.appendChild(repo); host.appendChild(pack);
  }
  [].forEach.call(document.querySelectorAll('.calendar .cell[data-day]'), function (cell) {
    cell.addEventListener('click', function () { inspect(cell.dataset.day); });
    cell.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); inspect(cell.dataset.day); }
    });
  });

  // ---- restore ---------------------------------------------------------------
  lens(typeof prefs.lens === 'string' ? prefs.lens : root.getAttribute('data-theme') || '');
  var picked = document.getElementById('lens-default');
  if (picked) { picked.value = prefs.lens || ''; }
  density(typeof prefs.density === 'string' ? prefs.density : 'normal');
  accent(typeof prefs.accent === 'string' ? prefs.accent : '');
  applySettings();
  applyHidden();
  syncControls();
  paintPresets();
  overviewDensity(typeof prefs.od === 'string' ? prefs.od : 'balanced');
  allDepth(typeof prefs.ad === 'string' ? prefs.ad : 'full');
  activityMode(typeof prefs.actmode === 'string' ? prefs.actmode : 'combined');
  period.scale = typeof prefs.scale === 'string' && SPAN[prefs.scale] ? prefs.scale : 'year';
  period.from = typeof prefs.from === 'string' ? prefs.from : '';
  period.to = typeof prefs.to === 'string' ? prefs.to : '';
  if (fromBox) { fromBox.value = period.from; }
  if (toBox) { toBox.value = period.to; }
  applyPeriod();
  chrome(prefs.chrome !== 'off');
  rebuildLayoutPresets();
  paint();
  var asked = '';
  try { asked = decodeURIComponent(location.hash.slice(1)); } catch (e) { asked = ''; }
  show(asked || (typeof prefs.view === 'string' ? prefs.view : 'overview'));
  window.addEventListener('hashchange', function () {
    var next = '';
    try { next = decodeURIComponent(location.hash.slice(1)); } catch (e) { next = ''; }
    if (next) { show(next); }
  });
})();
"""


def _rail(sites: list) -> str:
    """Navigation. Each project carries the worst tone its own panels produced,
    so the rail cannot look calmer than the pages behind it."""
    out = ["<aside class=rail><div class=brand><b>Runtime Pack</b><span>console</span></div>",
           "<h4>views</h4>"]
    for name, title, _question in _VIEWS:
        out.append(f"<button class=go data-goto='{name}'><span class=dot></span>"
                   f"{_ESC(title)}</button>")
    out.append(f"<h4>projects<span class=n> {len(sites)}</span></h4>")
    for index, site in enumerate(sites):
        marked = site.attention
        worst = next((t for t in (Tone.BAD, Tone.WARN, Tone.UNKNOWN) if marked.get(t)),
                     Tone.GOOD if site.view is not None else Tone.UNKNOWN)
        total = sum(marked.values())
        out.append(f"<button class=go data-goto='project:{index}'>"
                   f"<span class='dot {worst}'></span>{_ESC(site.name)}"
                   f"<span class=n>{total or ''}</span></button>")
    out.append("</aside>")
    return "".join(out)


def _global_bar(sites: list, lens: str) -> str:
    readable = [s for s in sites if s.view is not None]
    flagged = sum(sum(s.attention.values()) for s in sites)
    #: THE OLDEST, BY NUMBER. Comparing the formatted strings put `9 min ago`
    #: above `120 min ago`, so the summary of how stale the page is reported the
    #: freshest record on it. And if any reading cannot be dated, the oldest
    #: cannot be established — which is a different answer from a large number.
    ages, undatable = [], False
    for site in sites:
        found = site.figures("freshness")
        if site.view is None or not found:
            undatable = True
            continue
        for cell in found:
            try:
                ages.append((int(cell.fields["minutes"]), cell.value))
            except (KeyError, TypeError, ValueError):
                undatable = True
    lenses = "".join(
        f"<button data-lens='{l}' aria-pressed='{str(l == lens).lower()}'>"
        f"{_ESC(l or 'monochrome')}</button>" for l in projection.LENSES)
    return ("<div class=gbar>"
            f"<span class=t>projects</span><span>{len(sites)}</span>"
            f"<span class=t>readable</span><span>{len(readable)}</span>"
            f"<span class=t>marked</span><span>{flagged}</span>"
            f"<span class=t>oldest reading</span>"
            f"<span class='{'unknown' if undatable else ''}'>"
            f"{_ESC(UNKNOWN if undatable or not ages else max(ages)[1])}</span>"
            f"<span class=lens>{lenses}</span></div>")


def _custom_view(sites: list) -> str:
    #: GROUPED BY SCOPE. A hundred and thirty widgets in one flat list is a
    #: catalogue nobody reads — found by looking at it. The cross-project ones
    #: are open; each project folds, because a reader arranging a view is
    #: thinking about one project at a time.
    catalogue = _widgets(sites)
    groups: dict = {}
    for node_id, title, scope in catalogue:
        groups.setdefault(scope, []).append((node_id, title))

    def pick(node_id, title, scope):
        label = title[len(scope) + 3:] if scope != "global" and title.startswith(scope) else title
        return (f"<label><input type=checkbox data-pick='{_ESC(node_id)}'>"
                f"<span>{_ESC(label)}</span><span class=ord>"
                f"<button data-move='{_ESC(node_id)}' data-by='-1' title='earlier'>↑</button>"
                f"<button data-move='{_ESC(node_id)}' data-by='1' title='later'>↓</button>"
                f"<button data-span='{_ESC(node_id)}' title='wider'>⇔</button>"
                f"<button data-tall='{_ESC(node_id)}' title='taller'>⇕</button>"
                f"</span></label>")

    picks = []
    for scope, rows in groups.items():
        inner = "".join(pick(node_id, title, scope) for node_id, title in rows)
        if scope == "global":
            picks.append(f"<h5>across every project</h5>{inner}")
        else:
            picks.append(f"<details><summary>{_ESC(scope)}"
                         f"<span class=n> {len(rows)}</span></summary>{inner}</details>")
    return (
        "<div class=filters><span class=t>columns</span>"
        + "".join(f"<button data-cols='{n}'>{n}</button>" for n in (1, 2, 3, 4, 5, 6))
        + "<span class=t>projects</span><select id=layout-scope>"
        + "<option value=all>all of them</option>"
        + "".join(f"<option value='{at}'>{_ESC(site.name)}</option>"
                  for at, site in enumerate(sites))
        + "</select>"
        + "<span class=t>density</span><select id=layout-density>"
        "<option value=compact>compact</option><option value=normal>normal</option>"
        "<option value=comfortable>comfortable</option></select>"
        + "<input type=search id=layout-filter placeholder='filter what the widgets show'>"
        + "</div>"
        "<div class=filters><span class=t>layout</span>"
        + "<span id=layout-presets class=lens></span>"
        + "<input type=text id=layout-new placeholder='name a new layout' maxlength=40>"
        + "<button id=layout-create>save as</button>"
        + "<button id=layout-dup>duplicate</button>"
        + "<button id=layout-rename>rename</button>"
        + "<button id=layout-delete>delete</button>"
        + "<button id=layout-reset>reset everything</button>"
        + "<span class=t>current</span><span id=layout-name>default</span></div>"
        "<div class=builder><div class=catalog>" + "".join(picks) +
        "<h5>what this is</h5><p class=none style='padding:0'>A layout selects and arranges "
        "sections that are already on this page. It is kept in this browser, under one key, and "
        "it is not part of any project's state: deleting it changes no record, no evidence and "
        "no authority. A widget that is no longer here is dropped, an impossible width is "
        "clamped, and a preference that will not parse is replaced by the default.</p>"
        "</div><div class=canvas id=canvas><div class=empty>Tick a widget on the left. "
        "With scripting off this canvas stays empty and every widget remains visible in its own "
        "view — nothing is only here.</div></div></div>")


# --- what an operator may change, and how far ------------------------------------------
#
# Declared once, in one table, and read by both halves: the controls are
# rendered from it and the script that applies and bounds them reads the same
# `data-` attributes. A settings panel whose inputs and whose validator were
# written separately is a settings panel that will one day accept something the
# validator rejects, or reject something no control can produce.

#: Presentation colours. `text` says whether a token is drawn ON a surface, so
#: the contrast rule knows which pairs to check.
_COLOUR_TOKENS = (
    ("ground", "app background", "surface"),
    ("panel", "panel", "surface"),
    ("panel-2", "raised panel", "surface"),
    ("panel-3", "panel header", "surface"),
    ("rule", "divider", "line"),
    ("rule-strong", "strong divider", "line"),
    ("ink", "primary text", "text"),
    ("dim", "secondary text", "text"),
    ("faint", "muted text", "text"),
    ("accent", "interaction accent", "text"),
    ("select", "selection highlight", "surface"),
)

#: Semantic colours. Changeable, and bounded by the rule that they must stay
#: four answers a reader can tell apart — from each other and from the accent.
#: The founder asked for control over presentation; a control that could merge
#: BAD with GOOD would be control over meaning.
_SEMANTIC_TOKENS = (
    ("bad", "defect"), ("warn", "warning"), ("unknown", "not established"),
    ("good", "established good"),
)

#: Sizes and spaces, each with the range outside which the interface stops
#: being usable. The bounds are the point: an operator may make the type large
#: or the page dense, and may not make a state invisible.
_SIZE_TOKENS = (
    ("fs", "body and telemetry", 10, 20, 0.5, "px"),
    ("fs-state", "the primary state", 18, 56, 1, "px"),
    ("fs-micro", "field labels", 7.5, 13, 0.5, "px"),
    ("fs-forensic", "forensic detail", 9, 18, 0.5, "px"),
    ("lh", "line height", 1.2, 2.2, 0.05, ""),
    ("rail", "sidebar width", 150, 380, 2, "px"),
    ("pad-x", "horizontal padding", 6, 40, 1, "px"),
    ("pad-y", "row padding", 0, 10, 0.5, "px"),
    ("gap", "space between zones", 0, 10, 1, "px"),
)

_FONT_CHOICES = (
    ("var(--mono)", "monospace (data)"),
    ("var(--ui)", "system UI"),
    ("ui-monospace,SFMono-Regular,Menlo,monospace", "SF Mono / Menlo"),
    ("'JetBrains Mono',ui-monospace,monospace", "JetBrains Mono, if installed"),
    ("'IBM Plex Mono',ui-monospace,monospace", "IBM Plex Mono, if installed"),
    ("Inter,-apple-system,BlinkMacSystemFont,sans-serif", "Inter, if installed"),
    ("Georgia,'Times New Roman',serif", "serif"),
)

#: Sections an operator may fold away. **Nothing that carries a defect, an
#: unestablished reading, a blocker, a stale reading or a human decision is on
#: this list, and the test that says so reads this tuple** — so adding one is a
#: decision somebody makes here, in the open, rather than in a stylesheet.
_OPTIONAL_SECTIONS = (
    ("identity", "identity and pin panels"),
    ("footer", "the page's own disclaimer"),
    ("questions", "the view's question line"),
)


def _settings(sites: list) -> str:
    """Presentation, under the operator's hand — and nothing else under it."""
    colours = "".join(
        f"<label class=set><span>{_ESC(label)}</span>"
        f"<input type=color data-token='{token}' data-kind='{kind}'>"
        f"<button data-clear='{token}' title='back to the lens'>×</button></label>"
        for token, label, kind in _COLOUR_TOKENS)
    semantic = "".join(
        f"<label class=set><span>{_ESC(label)}</span>"
        f"<input type=color data-token='{token}' data-kind='semantic'>"
        f"<button data-clear='{token}' title='back to the lens'>×</button></label>"
        for token, label in _SEMANTIC_TOKENS)
    sizes = "".join(
        f"<label class=set><span>{_ESC(label)}</span>"
        f"<input type=range data-token='{token}' min='{low}' max='{high}' step='{step}'"
        f" data-unit='{unit}'><em data-shows='{token}'>—</em>"
        f"<button data-clear='{token}' title='back to the lens'>×</button></label>"
        for token, label, low, high, step, unit in _SIZE_TOKENS)
    fonts = "".join(
        f"<option value=\"{_ESC(value)}\">{_ESC(label)}</option>" for value, label in _FONT_CHOICES)
    optional = "".join(
        f"<label class=set><input type=checkbox data-show='{key}' checked>"
        f"<span>{_ESC(label)}</span></label>" for key, label in _OPTIONAL_SECTIONS)
    lenses = "".join(
        f"<option value='{l}'>{_ESC(l or 'monochrome (default)')}</option>"
        for l in projection.LENSES)
    return (
        "<div class=filters><span class=t>preset</span><span id=preset-list class=lens></span>"
        "<input type=text id=preset-name placeholder='name this look' maxlength=40>"
        "<button id=preset-save>save as</button><button id=preset-dup>duplicate</button>"
        "<button id=preset-del>delete</button>"
        "<button id=lens-reset>back to lens defaults</button>"
        "<button id=all-reset>reset everything</button>"
        "<span class=t>saved</span><span id=preset-current>—</span></div>"
        "<div class=settings>"
        "<section class=setgroup><div class=head><h2>lens</h2></div><div class=setbody>"
        f"<label class=set><span>opens in</span><select id=lens-default>{lenses}</select></label>"
        "<label class=set><span>density</span><select id=density-set>"
        "<option value=compact>compact</option><option value=normal>normal</option>"
        "<option value=comfortable>comfortable</option></select></label>"
        "<p class=note>A lens moves surfaces and never meanings. Whatever you change below "
        "sits on top of the lens you pick; the × beside a control puts that one back.</p>"
        "</div></section>"
        f"<section class=setgroup><div class=head><h2>colour</h2></div>"
        f"<div class=setbody>{colours}</div></section>"
        f"<section class=setgroup><div class=head><h2>state colour</h2>"
        f"<span class=chip>bounded</span></div><div class=setbody>{semantic}"
        "<p class=note>These four are what a reader looks for. A choice that makes any two of "
        "them — or any one of them and the accent — hard to tell apart is refused, and the "
        "control says why. That is not a presentation preference; it is what the colours are "
        "for.</p></div></section>"
        f"<section class=setgroup><div class=head><h2>type</h2></div><div class=setbody>"
        f"<label class=set><span>interface font</span><select data-token='font'>{fonts}"
        "</select><button data-clear='font'>×</button></label>"
        f"{sizes}</div></section>"
        f"<section class=setgroup><div class=head><h2>sections</h2></div><div class=setbody>"
        f"{optional}"
        "<p class=note>Only these. A defect, an unestablished reading, a blocker, a stale "
        "reading and a human decision have no switch, in any view, at any density — they are "
        "the reasons the page exists.</p></div></section>"
        "<section class=setgroup><div class=head><h2>what this page is</h2></div><ul>"
        "<li><span class=k>a reading</span><span class=v>rebuilt from durable artifacts every "
        "time it is generated. It is exactly as old as the reading times beside each project, "
        "and re-reading means running the command again.</span></li>"
        "<li><span class=k>what it keeps</span><span class=v>one key in this browser, holding "
        "the lens, these settings, the layouts and the presets. Nothing else, nowhere else, and "
        "never in any project.</span></li>"
        "<li><span class=k>what it cannot do</span><span class=v>authorise, schedule, wake, end "
        "a worker, change a record, alter evidence, or infer an authority nobody granted. "
        "Deleting this page breaks no checker.</span></li>"
        "<li class=action><span class=k>where the authority is</span><span class=v>the durable "
        "artifacts each project owns. Where this page and those disagree, THIS is the defect."
        "</span></li></ul></section>"
        "<section class=setgroup><div class=head><h2>refusals</h2>"
        "<span class=chip id=refusal-count>none</span></div>"
        "<ul id=refusals><li class=muted><span class=v>A setting this page would not accept "
        "appears here with the reason. Nothing is applied silently and nothing is discarded "
        "silently.</span></li></ul></section>"
        "</div>")


_STATES = (
    ("WAITING_ON_IDENTIFIED_JOB",
     "A named job is running and its deadline is recorded. The coordinator is right to be "
     "waiting: there is something outstanding and it can be observed."),
    ("COMPLETED_NOT_CONSUMED",
     "A job finished and nobody has taken up its result. The work is done and the answer is "
     "sitting there — this is the state four of five recorded liveness failures were in."),
    ("ACTIONABLE_WORK_READY",
     "Nothing is in the way and nothing is outstanding, so the coordinator decides what is "
     "next. Not a resting state: a turn to take."),
    ("BLOCKED_ON_HUMAN",
     "Every outstanding item waits on a person. Unavailability never implies authorisation, "
     "so the work waits — and a blocker that only stops SOME items does not put the "
     "capability here."),
    ("BLOCKED_ON_CAPACITY",
     "No window is available for the outstanding work. Distinct from a human block because "
     "it resolves by itself, at a time the record can name."),
    ("RECOVERY_REQUIRED",
     "Something is wrong with the record or with a job — an expired deadline, two waits "
     "holding one obligation, a field that cannot be read. It names which."),
    ("SILENT_IDLE",
     "There is work to do, nothing is outstanding and nothing is in the way. **This is the "
     "defect this release exists to close**, not a resting state: it is what a coordinator "
     "that has quietly stopped looks like from outside."),
    ("TERMINAL",
     "Nothing is outstanding and nothing is authorised. The capability is finished."),
    ("STALLED",
     "A job that is not progressing. **One reading cannot establish it** — a stall needs two "
     "independently observed flat signals over time — so this page shows `·` in that column "
     "rather than answering it. `progress.classify` is the module that answers it."),
    ("UNKNOWN",
     "Could not be established. Never the same as *nothing*, and never rendered as a resting "
     "state: an absent record means the coordinator's position cannot be read, which is a "
     "much worse thing than having nothing to do."),
)

_QUESTIONS = (
    ("What is the difference between local git and remote?",
     "Local is every commit a ref in your own clone reaches. Remote is the part of that a "
     "remote-tracking ref also reaches — a subset, never a second population. The rest is "
     "*only here*.", "history"),
    ("Why does the remote say UNKNOWN rather than zero?",
     "Because nothing on this machine has ever seen what that remote holds. This page does not "
     "fetch, so it leaves the question open instead of answering it with a zero that would look "
     "like an empty remote.", "history"),
    ("Which day does a commit belong to?",
     "Its UTC day, wherever in the world it was made. Bucketing by the committer's own offset "
     "would split two commits a minute apart; bucketing by yours would move them when somebody "
     "else opens the page.", "history"),
    ("How do I look at a period that is not year, month, week or day?",
     "The two date boxes beside the scales. They are UTC days, the same days the calendar "
     "counts in, and either one on its own is an open end: a start with no end runs to the "
     "most recent day, an end with no start runs from the beginning. Choosing a scale clears "
     "them, and the page always says which window is in force.", "history"),
    ("Does a busy calendar mean a good week?",
     "No. A count is evidence that commits happened. It is not pace, not quality and not a "
     "verdict on anybody's week, and nothing here scores it.", "history"),
    ("What is Runtime Pack event history?",
     "What durable artifacts can actually date: a reading written, a wait declared, a deadline "
     "passed, output written, evidence recorded. Each row names the artifact it came from, and "
     "nothing is dated by inference.", "history"),
    ("Why is there no *capability opened* event?",
     "Because nothing durable records when it opened. The release will show what an artifact "
     "timestamps and will not date an event from the fact that the state implies it happened.",
     "history"),
    ("How do the year, month, week and day views differ?",
     "Year and month are a calendar — the rhythm. Week narrows it. Day stops being a calendar "
     "and becomes the timeline underneath, which is what you want for one day.", "history"),
    ("How do I see what happened on one day?",
     "Choose a cell in the calendar, with a pointer or with the keyboard. The inspector under "
     "it gives both histories for that day rather than a number in a tooltip.", "history"),
    ("Where do I see everything at once?",
     "Control room, or All systems. The first is built to be left up on a wide screen; the "
     "second is one scrollable page with a section index.", "control"),
    ("Which project needs me?",
     "Overview, sorted by the attention column, or filtered with *needs attention*. The "
     "sidebar carries the same count beside each project.", "overview"),
    ("Where do I see everything that is running?",
     "Workers. Every job in every project, with its owner, its subject revision, its deadline "
     "and when it last did something observable.", "workers"),
    ("Why does something say UNKNOWN?",
     "Because a reading could not be established — not because the answer is nothing. The row "
     "says which reading and why; the project page says it in full.", "overview"),
    ("How do I know an audit is about the right tree?",
     "Audits & evidence compares each audit's subject revision against the candidate the "
     "record declares. An audit of another tree is evidence about another tree, and the row "
     "says so.", "audits"),
    ("Where is the next action?",
     "At the top of every project page, in its own bordered block, and in the overview's own "
     "column. It is the record's first unblocked item, not a choice this page made.", "overview"),
    ("Where is a human decision shown?",
     "In the *needs a person* column, on the project page under the coordinator state, and in "
     "the attention list. It carries the HITL row it sits on and exactly what it blocks.",
     "overview"),
    ("How do I read the forensic detail?",
     "Every panel keeps its prose behind *N more*. Nothing marked as a defect, a warning or an "
     "unestablished reading is ever put there — only detail.", "overview"),
    ("How do I change the look?",
     "Settings. Lens, then colours, type, spacing and density on top of it. Every control has "
     "a × that puts that one thing back.", "settings"),
    ("Will my settings still be here tomorrow?",
     "Yes, in this browser. They are kept under one key and reach no project, no record and no "
     "evidence. Clearing your browser data clears them, and the page comes back at its "
     "defaults.", "settings"),
    ("How do I build my own screen?",
     "Custom views. Tick widgets, order them, set their width, choose a column count, save it "
     "under a name. Presets switch between whole arrangements.", "custom"),
    ("Why can I not hide this warning?",
     "Because a defect, an unestablished reading, a blocker, a stale reading and a human "
     "decision are the reasons this page exists. Only decoration and vocabulary can be folded "
     "away, and Settings lists exactly which.", "settings"),
    ("What does IN_PROGRESS mean on the pack?",
     "The release is not frozen. Only a QUALIFIED_AND_FROZEN release may be pinned by a "
     "project, so a pack in this state is not adoptable — and every project page says so.",
     "identity"),
    ("Why is this reading old?",
     "Because the page is a reading, taken when it was generated. The age is in the top bar "
     "and beside every project; over an hour it is marked STALE. Re-reading means running the "
     "command again.", "overview"),
    ("What does this page decide?",
     "Nothing. It reads, arranges and shows. Where it and the durable record disagree, this "
     "page is the defect.", "settings"),
)


# --- instruments -----------------------------------------------------------------
#
# Each one answers a question faster than the rows under it, and none of them is
# the only place its numbers appear. Three rules hold them honest:
#
#   * **Only counts of things this page is already showing.** A distribution is
#     a tally of rows, in the same way the attention badge is; nothing here
#     computes a condition, and nothing invents a denominator.
#   * **UNKNOWN is a segment, never an absence.** An unestablished reading gets
#     its own band in its own tone. It is never folded into a total, never drawn
#     as zero, and never left out because it would spoil the picture.
#   * **The exact numbers are beside the picture, always.** A reader who
#     distrusts a bar can read the count without hovering anything.


def _distribution(parts, empty: str = "nothing to count") -> str:
    """A categorical tally as one segmented bar plus its exact counts.

    `parts` is `[(name, count, tone)]`. A part with a count of zero keeps its
    entry in the legend — *none of these* is a reading — and takes no width in
    the bar.
    """
    # A count of `None` is a question this reading cannot answer. It keeps its
    # place in the legend and shows `·`, because a `0` beside *two readings
    # needed* reads as *none stalled* — an answer, from a page that has just
    # said it cannot give one.
    counted = [(name, None if count is None else int(count), tone)
               for name, count, tone in parts]
    total = sum(count for _n, count, _t in counted if count)
    if not counted:
        return f"<p class=none>{_ESC(empty)}</p>"
    bar = "".join(
        f"<span class='{tone}' style='flex:{count}' title='{_ESC(f'{name}: {count}')}'></span>"
        for name, count, tone in counted if count)
    legend = "".join(
        f"<span class='{tone}'><i></i>{_ESC(name)} "
        f"<b>{'·' if count is None else count}</b></span>"
        for name, count, tone in counted)
    return (f"<div class=instrument>"
            + (f"<div class=dist>{bar}</div>" if total else
               "<p class=nodata>nothing is outstanding</p>")
            + f"<div class=legend>{legend}</div></div>")


def _project_states(sites: list) -> str:
    tally: dict = {}
    for site in sites:
        tally[(site.state, site.tone)] = tally.get((site.state, site.tone), 0) + 1
    return _distribution([(state, count, tone) for (state, tone), count in
                          sorted(tally.items(), key=lambda row: -row[1])],
                         "No project was named.")


def _worker_states(sites: list) -> str:
    jobs = [c for s in sites for c in s.figures("job")]
    overdue = [c for c in jobs if "EXPIRED" in c.fields.get("deadline", "")]
    return _distribution([
        ("running", len([c for c in jobs if c.value == "RUNNING" and c not in overdue]),
         Tone.PLAIN),
        ("complete, unconsumed", len([c for c in jobs if c.value == "COMPLETE"]), Tone.WARN),
        ("past a deadline", len(overdue), Tone.BAD),
        ("nobody can observe", len([c for c in jobs if c.value == UNKNOWN]), Tone.UNKNOWN),
        # NOT ZERO. One reading cannot establish a stall, so the tally declines
        # to answer rather than answering none.
        ("stalled — two readings needed", None, Tone.PLAIN),
    ], "No project declares an outstanding job.")


def _attention_shape(sites: list) -> str:
    tally = {Tone.BAD: 0, Tone.WARN: 0, Tone.UNKNOWN: 0}
    for site in sites:
        for tone, count in site.attention.items():
            tally[tone] = tally.get(tone, 0) + count
    return _distribution([("marked as a defect", tally.get(Tone.BAD, 0), Tone.BAD),
                          ("marked to look at", tally.get(Tone.WARN, 0), Tone.WARN),
                          ("could not be established", tally.get(Tone.UNKNOWN, 0),
                           Tone.UNKNOWN)],
                         "Nothing is marked.")


def _audit_shape(sites: list) -> str:
    audits = [c for s in sites for c in s.figures("audit")]
    return _distribution([
        ("about the candidate", len([c for c in audits if c.tone == Tone.GOOD]), Tone.GOOD),
        ("about another tree", len([c for c in audits if c.tone == Tone.BAD]), Tone.BAD),
        ("cannot be compared", len([c for c in audits if c.tone == Tone.UNKNOWN]),
         Tone.UNKNOWN),
        ("projects with no audit in flight",
         len([s for s in sites if s.view is not None and not s.figures("audit")]), Tone.PLAIN),
    ], "No audit states a subject.")


def _capacity_shape(sites: list) -> str:
    pools = [c for s in sites for c in s.figures("capacity")]
    return _distribution([
        ("measured", len([c for c in pools if c.tone != Tone.UNKNOWN]), Tone.PLAIN),
        # UNKNOWN IS NOT EMPTY AND IS NOT ZERO. An unmeasured window is its own
        # answer and gets its own band.
        ("unmeasured", len([c for c in pools if c.tone == Tone.UNKNOWN]), Tone.UNKNOWN),
    ], "No project declares a capacity observation.")


def _freshness_shape(sites: list) -> str:
    ages = [c for s in sites for c in s.figures("freshness")]
    return _distribution([
        ("read within the hour",
         len([c for c in ages if c.tone != Tone.WARN and c.tone != Tone.UNKNOWN]), Tone.PLAIN),
        ("stale", len([c for c in ages if c.note == "STALE"]), Tone.WARN),
        ("cannot be dated", len([c for c in ages if c.tone == Tone.UNKNOWN]), Tone.UNKNOWN),
        ("unreadable", len([s for s in sites if s.view is None]), Tone.UNKNOWN),
    ], "Nothing to date.")


def _budget_shape(sites: list) -> str:
    """Where every declared budget stands, as one distribution.

    The per-project meters are a table and belong in a section; in the
    instrument band they filled the screen and pushed the room off it. A shape
    first, the meters on demand.
    """
    exhausted = near = room = unbounded = 0
    for site in sites:
        for cell in site.figures("budget"):
            if cell.share is None:
                unbounded += 1
            else:
                used, ceiling = cell.share
                if used >= ceiling:
                    exhausted += 1
                elif used / ceiling >= 0.75:
                    near += 1
                else:
                    room += 1
    return _distribution([("exhausted", exhausted, Tone.BAD),
                          ("three quarters spent", near, Tone.WARN),
                          ("with room", room, Tone.PLAIN),
                          ("counted against no ceiling", unbounded, Tone.UNKNOWN)],
                         "No project declares a budget.")


def _budget_meters(sites: list) -> str:
    """Every declared budget, as a consumption meter with its exact position.

    Consumption only. The evidence readings a project writes — coverage,
    mechanisms, recurrence classes — are sentences it chose, not numbers with a
    denominator, and turning `87/87 covered` into a bar would mean this page
    parsing prose to find a fraction. It says the sentence instead.
    """
    rows = []
    for site in sites:
        for cell in site.figures("budget"):
            at = _INDEX.get(id(site))
            named = (f"<button class=jump data-goto='project:{at}'>{_ESC(site.name)}</button>"
                     if at is not None else _ESC(site.name))
            rows.append(f"<tr data-tone='{cell.tone}'>" + _td("project", named)
                        + _td("budget", _ESC(cell.label))
                        + _td("used", projection._cell(cell, "fact"), cell.tone) + "</tr>")
    if not rows:
        return "<p class=none>No project declares a budget.</p>"
    return f"<div class=tw><table><tbody>{''.join(rows)}</tbody></table></div>"


def _recent_activity(sites: list, *, weeks: int = 10) -> str:
    """The last few weeks, compactly — for a screen somebody leaves up.

    A year of calendar belongs in History; what a control room needs is whether
    anything has happened lately, where, and how much of it is still only here.
    The horizon is stated rather than implied.
    """
    activities = [_activity_of(site) for site in sites]
    days = activity.aggregate(activities)
    if not days:
        return ("<p class=none>No project declares a repository this console can read, so "
                "there is no repository history here. That is not the same as no work.</p>")
    horizon = datetime.date.today() - datetime.timedelta(days=weeks * 7 - 1)
    recent = [day for day in days if day.date >= horizon.isoformat()]
    most = max((day.local for day in recent), default=0)
    total = sum(day.local for day in recent)
    only = sum(day.local_only for day in recent)
    unresolved = [a for a in activities if a.total_local and not a.remote_established]
    live = [a for a in activities
            if any(day.date >= horizon.isoformat() and day.local for day in a.days)]
    latest = max((day.date for day in days if day.local), default="")
    strip = "".join(
        f"<i class='cell s{_activity_scale(day.local, most)} k-local"
        f"{' q' if day.remote_unknown else ''}' title='{_ESC(day.date)}: {day.local} local, "
        f"{day.local_only} only here'></i>" for day in recent)
    return ("<div class=instrument>"
            f"<div class='calendar recent'><div class=grid>{strip}</div></div>"
            "<div class=legend>"
            f"<span><b>{total}</b> commits in {weeks} weeks</span>"
            f"<span class='{'warn' if only else ''}'><b>{only}</b> only here</span>"
            f"<span><b>{len(live)}</b> projects active</span>"
            f"<span class='{'unknown' if unresolved else ''}'>"
            f"<b>{len(unresolved)}</b> remotes unresolved</span>"
            f"<span>latest <b>{_ESC(latest or UNKNOWN)}</b></span>"
            "</div></div>")


def _clock(when: str) -> str:
    """A timestamp a narrow column can print on one line.

    The full ISO string is what the timeline and the day inspector show, and
    it is the right answer there. In a band cell it broke across four lines
    with a `T` in the middle of one of them, so this drops the year and the
    zone and keeps the two fields somebody scanning a control room reads.
    Anything that is not an ISO timestamp is returned as it arrived: guessing
    at the shape of a string is how a reading becomes a decoration.
    """
    text = str(when)
    if len(text) >= 16 and text[4] == "-" and text[10] == "T":
        return f"{text[5:10]} {text[11:16]}"
    return text[:16]


def _recent_events(sites: list, *, limit: int = 8) -> str:
    """The last few things any durable artifact can date."""
    events = []
    for site in sites:
        events.extend(_events_of(site))
    dated = sorted((e for e in events if e.when), key=lambda e: e.when, reverse=True)[:limit]
    if not dated:
        return ("<p class=none>Nothing durable in these projects carries a timestamp for "
                "anything that happened.</p>")
    # ROWS, NOT A TABLE. Four columns inside a band cell gave each field about
    # 140 pixels, and `overflow-wrap:anywhere` — which is there so a long path
    # cannot force the page sideways — then broke words down the middle of
    # themselves. A row that flows across the whole cell has the same fields in
    # the same order and does not need a column to be wide enough for its
    # longest value.
    rows = "".join(
        f"<li data-tone='{e.tone}'>"
        f"<span class='nw t'>{_ESC(_clock(e.when))}</span>"
        f"<span class='nw who'>{_ESC(e.project)}</span>"
        f"<span class='s {e.tone} nw'>{_ESC(e.kind)}</span>"
        f"<span class=what>{_ESC(e.subject)}</span></li>"
        for e in dated)
    return f"<ul class='rows events'>{rows}</ul>"


def _telemetry(sites: list, *, kinds=()) -> str:
    """The instrument band. `kinds` chooses which, so a density can carry a few
    and a control room can carry all of them."""
    every = {
        "projects": ("project states", _project_states),
        "workers": ("worker states", _worker_states),
        "attention": ("attention", _attention_shape),
        "audits": ("audits", _audit_shape),
        "capacity": ("capacity", _capacity_shape),
        "freshness": ("freshness", _freshness_shape),
        "budgets": ("budgets", _budget_shape),
        "budget-meters": ("every budget", _budget_meters),
        "recent-activity": ("recent repository activity", _recent_activity),
        "recent-events": ("recent runtime pack events", _recent_events),
    }
    chosen = [key for key in (kinds or every) if key in every]
    out = []
    for key in chosen:
        title, build = every[key]
        body = build(sites)
        # WHAT IT DREW decides how much of the band it gets. A legend of three
        # counted lines fits a column; a table of rows or a strip of days does
        # not, and asking each instrument to declare its own width is a list
        # that goes stale the first time somebody adds one.
        wide = " data-wide=1" if ("<table" in body or "class=rows" in body
                                  or "class='rows" in body or "class=calendar" in body
                                  or "class='calendar" in body) else ""
        out.append(f"<section class=setgroup data-widget='global:viz-{key}' "
                   f"data-widget-name='{_ESC(title)}' data-widget-scope='global'{wide}>"
                   f"<div class=head><h2>{_ESC(title)}</h2></div>"
                   f"<div class=setbody>{body}</div></section>")
    return "<div class=instruments>" + "".join(out) + "</div>"


def _finder(sites: list) -> str:
    """Quick find: a way to reach anything on this page by typing part of it.

    It searches what is already here — views, projects, jobs, audits, pools,
    settings and help topics — and its only verb is *go there*. A palette that
    could run something would be a command surface, and this page has no
    commands.
    """
    entries = [{"label": title, "kind": "view", "goto": name, "hint": question}
               for name, title, question in _VIEWS]
    for at, site in enumerate(sites):
        entries.append({"label": site.name, "kind": "project", "goto": f"project:{at}",
                        "hint": site.state})
        for cell in site.figures("job"):
            entries.append({"label": cell.fields.get("job", cell.label), "kind": "job",
                            "goto": "workers", "hint": f"{site.name} — {cell.value}"})
        for cell in site.figures("audit"):
            entries.append({"label": cell.fields.get("audit", cell.label), "kind": "audit",
                            "goto": "audits", "hint": f"{site.name} — {cell.value}"})
        for cell in site.figures("capacity"):
            entries.append({"label": cell.fields.get("pool", cell.label), "kind": "pool",
                            "goto": "capacity", "hint": f"{site.name} — {cell.value}"})
    for token, label, _kind in _COLOUR_TOKENS:
        entries.append({"label": label, "kind": "setting", "goto": "settings", "hint": token})
    for token, label, *_rest in _SIZE_TOKENS:
        entries.append({"label": label, "kind": "setting", "goto": "settings", "hint": token})
    for question, _answer, where in _QUESTIONS:
        entries.append({"label": question, "kind": "help", "goto": where, "hint": "help"})
    for name, _text in _STATES:
        entries.append({"label": name, "kind": "state", "goto": "help", "hint": "what it means"})
    rows = "".join(
        f"<li data-find='{_ESC((e['label'] + ' ' + e['kind'] + ' ' + e['hint']).lower())}' "
        f"data-goto='{_ESC(e['goto'])}'><span class=k>{_ESC(e['kind'])}</span>"
        f"<span class=v>{_ESC(e['label'])}</span>"
        f"<span class=hint>{_ESC(e['hint'])}</span></li>" for e in entries)
    return ("<div class=finder id=finder>"
            "<div class=finderbox><input type=search id=find-input autocomplete=off "
            "placeholder='find a project, a job, an audit, a setting, a state…'>"
            "<button id=find-close>esc</button></div>"
            f"<ul id=find-list>{rows}</ul></div>")


def _all_systems(sites: list) -> str:
    """Everything worth knowing, recomposed as one surface.

    Not a concatenation of the other views: the sections are ordered the way an
    operator reads a morning — what needs me, what is running, what is
    established, what it is spending, what it is — with an index at the top and
    every section anchored so a link can land on one.
    """
    sections = (
        ("attention", "what needs a person or a look", _attention_across(sites)),
        ("matrix", "every project", _overview(sites)),
        ("workers", "every job", _kind_table(
            sites, "job",
            [("·state", "state"), ("job", "job"), ("expects", "expects"), ("owner", "owner"),
             ("subject", "subject"), ("deadline", "deadline"),
             ("progress", "last observable progress")],
            "No project declares an outstanding job.")),
        ("output", "durable output and recovery", _kind_table(
            sites, "output",
            [("·state", "recovery state"), ("task", "task"), ("root", "output root"),
             ("examined", "what is there")],
            "No project declares an output root.")),
        ("audits", "audits against the candidate", _kind_table(
            sites, "audit",
            [("·state", "subject vs candidate"), ("audit", "audit"),
             ("subject", "subject revision"), ("candidate", "declared candidate"),
             ("owner", "executor")],
            "No project has an audit in flight that states a subject.")),
        ("evidence", "standing evidence", _kind_table(
            sites, "evidence", [("·state", "reading")],
            "No project declares standing evidence.")),
        ("budgets", "what is being spent", _kind_table(
            sites, "budget", [("·state", "used")], "No project declares a budget.")),
        ("capacity", "windows", _kind_table(
            sites, "capacity",
            [("·state", "remaining"), ("pool", "pool"), ("provider", "provider"),
             ("window", "window"), ("resets", "resets"), ("observed", "observed")],
            "No project declares a capacity observation.")),
        ("history", "history and public safety", _history(sites)),
        ("identity", "identity and release", _identity(sites)),
        ("registry", "the registry itself", _projects(sites)),
    )
    #: MINIMAL is the first four: what needs a person, every project, every job,
    #: every audit. The rest are `later` — and every one of them is also its own
    #: view in the sidebar, so choosing minimal changes what this page shows and
    #: never what the console holds.
    minimal = {"attention", "matrix", "workers", "audits"}
    index = "".join(
        f"<button class=jump data-anchor='all-{key}'>{_ESC(title)}</button>"
        for key, title, _body in sections)
    #: EACH DOMAIN LEADS WITH ITS OWN ANSWER. The first version put every
    #: table at equal weight and read as a diagnostic log — complete, and
    #: nothing in it stood out. A summary line per domain, then its rows.
    counted = {
        "attention": [(f"{sum(sum(s.attention.values()) for s in sites)} readings marked",
                       Tone.WARN if any(s.attention for s in sites) else "")],
        "matrix": [(f"{len(sites)} projects", ""),
                   (f"{len([s for s in sites if s.view is None])} unreadable",
                    Tone.UNKNOWN if any(s.view is None for s in sites) else "")],
        "workers": [(f"{sum(1 for s in sites for c in s.figures('job'))} jobs", ""),
                    (f"{sum(1 for s in sites for c in s.figures('job') if 'EXPIRED' in
                            c.fields.get('deadline', ''))} past a deadline",
                     Tone.BAD if any('EXPIRED' in c.fields.get('deadline', '')
                                     for s in sites for c in s.figures('job')) else "")],
        "output": [(f"{sum(1 for s in sites for c in s.figures('output'))} output roots", "")],
        "audits": [(f"{sum(1 for s in sites for c in s.figures('audit'))} audits", ""),
                   (f"{sum(1 for s in sites for c in s.figures('audit')
                           if c.tone == Tone.BAD)} about another tree",
                    Tone.BAD if any(c.tone == Tone.BAD for s in sites
                                    for c in s.figures('audit')) else "")],
        "capacity": [(f"{sum(1 for s in sites for c in s.figures('capacity'))} pools", ""),
                     (f"{sum(1 for s in sites for c in s.figures('capacity')
                             if c.tone == Tone.UNKNOWN)} unmeasured",
                      Tone.UNKNOWN if any(c.tone == Tone.UNKNOWN for s in sites
                                          for c in s.figures('capacity')) else "")],
    }

    def line(key):
        parts = [(text, tone) for text, tone in counted.get(key, []) if text]
        return ("<div class=summary>"
                + "".join(f"<span class='{tone}'>{_ESC(text)}</span>" for text, tone in parts)
                + "</div>") if parts else ""

    body = "".join(
        f"<section class='setgroup{"" if key in minimal else " later"}' id='all-{key}' "
        f"data-anchor-target='all-{key}'>"
        f"<div class=head><h2>{_ESC(title)}</h2></div>{line(key)}{content}</section>"
        for key, title, content in sections)
    return ("<div class=filters><span class=t>show</span>"
            "<button data-ad='minimal'>minimal</button>"
            "<button data-ad='full' aria-pressed='true'>full</button>"
            "<span class=t>everything here is also its own view</span></div>"
            f"<div class='filters index'>{index}</div><div class=stack>{body}</div>")


def _control_room(sites: list) -> str:
    """One screen to leave up while the work runs.

    Recomposed around the questions an operator actually asks, in the order
    they ask them: what is the shape of all of it, what needs me, how is each
    project, what are the workers doing, is the evidence current, can anything
    be dispatched, and what is the release. Each section leads with a
    **summary** and carries only its notable rows; the complete table for every
    one of them is its own view in the sidebar.

    The first version put whole tables here and, on an ultrawide, fitted a
    great deal of text nobody could read from a desk. Width buys columns and
    summaries now, not smaller type.
    """
    readable = [s for s in sites if s.view is not None]
    jobs = [(s, c) for s in sites for c in s.figures("job")]
    running = [pair for pair in jobs if pair[1].value == "RUNNING"]
    complete = [pair for pair in jobs if pair[1].value == "COMPLETE"]
    unobserved = [pair for pair in jobs if pair[1].value == UNKNOWN]
    overdue = [pair for pair in jobs if "EXPIRED" in pair[1].fields.get("deadline", "")]
    outputs = [(s, c) for s in sites for c in s.figures("output")]
    partial = [pair for pair in outputs if "PARTIAL" in pair[1].value]
    audits = [(s, c) for s in sites for c in s.figures("audit")]
    mismatched = [pair for pair in audits if pair[1].tone == Tone.BAD]
    pools = [(s, c) for s in sites for c in s.figures("capacity")]
    unmeasured = [pair for pair in pools if pair[1].tone == Tone.UNKNOWN]
    blocked = [s for s in readable
               if (s.one("intervention") or Cell("", "none declared")).value != "none declared"]
    stale = [(s, c) for s in sites for c in s.figures("freshness") if c.note == "STALE"]
    unreadable = [s for s in sites if s.view is None]
    marked = [(s, line) for s in readable for line in s.view.attention]

    def cell(label, value, tone=Tone.PLAIN, note=""):
        return (f"<div class='sit {tone}'><i>{_ESC(label)}</i><em>{_ESC(str(value))}</em>"
                + (f"<u>{_ESC(note)}</u>" if note else "") + "</div>")

    banner = ("<div class=sit>"
              + cell("projects", len(sites), note=f"{len(readable)} readable")
              + cell("running", len(running))
              + cell("complete, unconsumed", len(complete),
                     Tone.WARN if complete else Tone.PLAIN)
              + cell("past a deadline", len(overdue), Tone.BAD if overdue else Tone.PLAIN)
              + cell("nobody can observe", len(unobserved),
                     Tone.UNKNOWN if unobserved else Tone.PLAIN)
              + cell("stalled", "·", note="two readings needed")
              + cell("waiting on a person", len(blocked), Tone.WARN if blocked else Tone.PLAIN)
              + cell("stale readings", len(stale), Tone.WARN if stale else Tone.PLAIN)
              + cell("unreadable", len(unreadable),
                     Tone.UNKNOWN if unreadable else Tone.PLAIN)
              + cell("marked", len(marked), Tone.WARN if marked else Tone.PLAIN)
              + "</div>")

    def summary(*parts):
        shown = [(text, tone) for text, tone in parts if text]
        return ("<div class=summary>"
                + "".join(f"<span class='{tone}'>{_ESC(text)}</span>" for text, tone in shown)
                + "</div>") if shown else ""

    def project_link(site):
        at = _INDEX.get(id(site))
        return (f"<button class=jump data-goto='project:{at}'>{_ESC(site.name)}</button>"
                if at is not None else f"<span class=s>{_ESC(site.name)}</span>")

    acting = []
    for site in readable:
        block = site.one("intervention")
        if block is not None and block.value != "none declared":
            acting.append((site, Tone.WARN, block.value))
    for site, line in marked:
        if line.tone == Tone.BAD:
            acting.append((site, Tone.BAD, line.text))
    seen, attention_rows = set(), []
    for site, tone, text in sorted(acting, key=lambda row: 0 if row[1] == Tone.BAD else 1):
        if (site.name, text) in seen:
            continue
        seen.add((site.name, text))
        fresh = site.one("freshness")
        attention_rows.append(
            f"<tr data-tone='{tone}'>" + _td("project", project_link(site))
            + _td("severity", f"<span class='s {tone}'>{_ESC(tone)}</span>", tone)
            + _td("what it says", f"<span class=clamp>{_ESC(text)}</span>")
            + _td("next authorised action",
                  f"<span class=clamp>{_ESC(site.view.next_action or '—')}</span>")
            + _td("read", _ESC(fresh.value if fresh else UNKNOWN),
                  fresh.tone if fresh else Tone.UNKNOWN) + "</tr>")
    attention = (f"<div class=tw><table><tbody>{''.join(attention_rows)}</tbody></table></div>"
                 if attention_rows else
                 "<p class=none>Nothing is marked and nobody is waiting on a person.</p>")

    health = []
    for site in sites:
        if site.view is None:
            health.append("<tr data-tone=unknown>" + _td("project", project_link(site))
                          + _td("state", "<span class='s unknown'>unreadable</span>", "unknown")
                          + _td("next authorised action",
                                f"<span class=clamp>{_ESC(site.unreadable)}</span>", "unknown")
                          + _td("jobs", "—") + _td("audit", "—")
                          + _td("capacity", "—") + _td("read", "—")
                          + _td("needs a person", "—") + "</tr>")
            continue
        counted = {}
        for figure in site.figures("job"):
            counted[figure.value] = counted.get(figure.value, 0) + 1
        audit = site.one("audit")
        fresh = site.one("freshness")
        pool = next(iter(site.figures("capacity")), None)
        block = site.one("intervention")
        health.append(
            f"<tr data-tone='{site.tone}'>" + _td("project", project_link(site))
            + _td("state", f"<span class='s {site.tone}'>{_ESC(site.state)}</span>", site.tone)
            + _td("next authorised action",
                  f"<span class=clamp>{_ESC(site.view.next_action or '—')}</span>")
            + _td("jobs", " ".join(
                f"<b>{counted.get(k, 0)}</b>" for k in ("RUNNING", "COMPLETE", UNKNOWN)) + " ·",
                  extra=" title='running, complete, nobody can observe, and a stall this "
                        "single reading cannot establish'")
            + (_td("audit", f"<span class='s {audit.tone}'>{_ESC(audit.value)}</span>",
                   audit.tone) if audit else
               _td("audit", "<span class='s unknown'>none</span>", "unknown"))
            + (_td("capacity", _ESC(pool.value), pool.tone) if pool else
               _td("capacity", f"<span class='s unknown'>{UNKNOWN}</span>", "unknown"))
            + (_td("read", _ESC(fresh.value), fresh.tone) if fresh else
               _td("read", f"<span class='s unknown'>{UNKNOWN}</span>", "unknown"))
            + _td("needs a person",
                  f"<span class=clamp>{_ESC(block.value)}</span>" if block else "—",
                  block.tone if block else "")
            + "</tr>")

    def compact(rows, empty):
        return (f"<div class=tw><table><tbody>{''.join(rows)}</tbody></table></div>"
                if rows else f"<p class=none>{_ESC(empty)}</p>")

    notable = overdue + [p for p in complete if p not in overdue] + \
        [p for p in running if p not in overdue]
    job_rows = [
        f"<tr data-tone='{c.tone}'>" + _td("project", project_link(s))
        + _td("job", f"<span class=s>{_ESC(c.fields.get('job', c.label))}</span>")
        + _td("state", f"<span class='s {c.tone}'>{_ESC(c.value)}</span>", c.tone)
        + _td("deadline",
              f"<span class=clamp>{_ESC(c.fields.get('deadline', UNKNOWN))}</span>",
              Tone.BAD if "EXPIRED" in c.fields.get("deadline", "") else "")
        + "</tr>" for s, c in notable]
    output_rows = [
        f"<tr data-tone='{c.tone}'>" + _td("project", project_link(s))
        + _td("recovery", f"<span class='s {c.tone}'>{_ESC(c.value)}</span>", c.tone)
        + _td("what is there", _ESC(c.fields.get("examined", UNKNOWN))) + "</tr>"
        for s, c in outputs]
    audit_rows = [
        f"<tr data-tone='{c.tone}'>" + _td("project", project_link(s))
        + _td("subject vs candidate",
              f"<span class='s {c.tone}'>{_ESC(c.value)}</span>", c.tone)
        + _td("subject", _ESC(c.fields.get("subject", UNKNOWN))) + "</tr>"
        for s, c in audits]
    pool_rows = [
        f"<tr data-tone='{c.tone}'>" + _td("project", project_link(s))
        + _td("pool", _ESC(c.fields.get("pool", c.label)))
        + _td("remaining", f"<span class='s {c.tone}'>{_ESC(c.value)}</span>", c.tone)
        + _td("resets", _ESC(c.fields.get("resets", UNKNOWN))) + "</tr>"
        for s, c in pools]
    release_rows = []
    for site in readable:
        pack, pin = site.one("pack"), site.one("pin")
        safety = {c.label: c for c in site.figures("evidence")}.get("public safety")
        release_rows.append(
            "<tr>" + _td("project", project_link(site))
            + (_td("pinned", f"<span class='s {pin.tone}'>{_ESC(pin.value)}</span>", pin.tone)
               if pin else
               _td("pinned", f"<span class='s unknown'>{UNKNOWN}</span>", "unknown"))
            + (_td("pack in the root", _ESC(pack.fields.get("state", UNKNOWN)), pack.tone)
               if pack else _td("pack in the root", UNKNOWN, "unknown"))
            + (_td("public safety",
                   f"<span class=clamp>{_ESC(safety.value)}</span>", safety.tone) if safety else
               _td("public safety", f"<span class='s unknown'>{UNKNOWN}</span>", "unknown"))
            + "</tr>")

    def section(title, chip, body, span=""):
        return (f"<section class='setgroup {span}'><div class=head><h2>{_ESC(title)}</h2>"
                + (f"<span class=chip>{_ESC(chip)}</span>" if chip else "")
                + f"</div>{body}</section>")

    defects = len([1 for _s, tone, _t in acting if tone == Tone.BAD])
    return (
        "<div class='filters index'>"
        "<button id=fullscreen>full screen</button>"
        "<button id=chrome-toggle>hide the chrome</button>"
        "<span class=t>the sidebar comes back with the same button, or Escape</span></div>"
        "<div class=room>"
        + section("the situation", f"{len(sites)} projects",
                  f"<div class=setbody>{banner}</div>", "room-wide")
        + "<div class='room-wide instruments-wide'>"
        + _telemetry(sites, kinds=("projects", "workers", "attention", "audits", "capacity",
                                   "freshness", "budgets", "recent-activity",
                                   "recent-events"))
        + "</div>"
        + section("needs a person or a look",
                  f"{len(attention_rows)}" if attention_rows else "clear",
                  summary((f"{len(blocked)} waiting on a person", Tone.WARN if blocked else ""),
                          (f"{defects} marked as a defect", Tone.BAD if defects else ""))
                  + attention, "wide2")
        + section("every project", f"{len(sites)}",
                  compact(health, "No project was named."), "wide2")
        + section("workers", f"{len(jobs)}",
                  summary((f"{len(running)} running", ""),
                          (f"{len(complete)} complete, unconsumed",
                           Tone.WARN if complete else ""),
                          (f"{len(overdue)} past a deadline", Tone.BAD if overdue else ""),
                          (f"{len(unobserved)} nobody can observe",
                           Tone.UNKNOWN if unobserved else ""))
                  + compact(job_rows, "No project declares an outstanding job."))
        + section("durable output", f"{len(outputs)}",
                  summary((f"{len(partial)} partially written", Tone.WARN if partial else ""))
                  + compact(output_rows, "No project declares an output root."))
        + section("audits", f"{len(audits)}",
                  summary((f"{len(mismatched)} about another tree",
                           Tone.BAD if mismatched else ""))
                  + compact(audit_rows, "No audit states a subject."))
        + section("capacity", f"{len(pools)}",
                  summary((f"{len(unmeasured)} unmeasured",
                           Tone.UNKNOWN if unmeasured else ""))
                  + compact(pool_rows, "No project declares a capacity observation."))
        + section("release and safety", "",
                  compact(release_rows, "No project was named."), "wide2")
        + "</div>")


def _help(sites: list) -> str:
    """What this is, what the words mean, and where things are."""
    states = "".join(
        f"<tr>{_td('state', f'<span class=s>{_ESC(name)}</span>')}"
        f"{_td('what it means', _ESC(text))}</tr>" for name, text in _STATES)
    questions = "".join(
        f"<tr>{_td('question', f'<span class=s>{_ESC(q)}</span>')}"
        f"{_td('answer', _ESC(a))}"
        f"{_td('where', f'<button class=jump data-goto=&#39;{where}&#39;>open</button>')}</tr>"
        for q, a, where in _QUESTIONS)
    return (
        "<div class=guide>"
        "<section class=setgroup><div class=head><h2>what this is</h2></div><ul>"
        "<li><span class=k>Mission Control</span><span class=v>one read-only page over every "
        "project that has adopted this release. It reads their durable artifacts, arranges "
        "what it finds, and shows it.</span></li>"
        "<li><span class=k>what it is not</span><span class=v>an authority. It does not "
        "authorise, schedule, wake anything, end a worker, change a record or alter evidence. "
        "It has no opinion of its own: every answer here belongs to the module that owns the "
        "question, and this page is a change of position, never of judgement.</span></li>"
        "<li><span class=k>how fresh it is</span><span class=v>exactly as old as the reading "
        "times it shows. It is generated, not live.</span></li>"
        "<li><span class=k>switching project</span><span class=v>the sidebar lists every "
        "project with the worst tone its own panels produced. Any project name anywhere on "
        "the page opens that project.</span></li>"
        "<li class=action><span class=k>if this page and the record disagree</span>"
        "<span class=v>believe the record. This page is the defect.</span></li>"
        "</ul></section>"
        "<section class=setgroup><div class=head><h2>the states, and what each one means</h2>"
        "</div><div class=tw><table><thead><tr><th>state</th><th>what it means</th></tr>"
        "</thead><tbody>" + states + "</tbody></table></div></section>"
        "<section class=setgroup><div class=head><h2>the words that are easy to misread</h2>"
        "</div><ul>"
        "<li><span class=k>next authorised action</span><span class=v>the record's own first "
        "outstanding item that nothing is blocking. Not advice, and not a plan — the thing the "
        "coordinator is expected to be doing.</span></li>"
        "<li><span class=k>subject vs candidate</span><span class=v>the subject is the tree an "
        "audit is ABOUT; the candidate is the tree the record is qualifying. When they differ, "
        "the audit's findings describe something else.</span></li>"
        "<li><span class=k>durable output</span><span class=v>what a worker actually wrote, "
        "classified from the artifacts rather than from the worker's own claim: complete, "
        "partial, nothing useful, or unknown.</span></li>"
        "<li><span class=k>capacity</span><span class=v>what the project last OBSERVED about "
        "its windows. A reading about a moment, licensing no claim about the next dispatch — "
        "and no observation means unknown, never zero.</span></li>"
        "<li><span class=k>freshness</span><span class=v>how old the record is. Every state "
        "above it is derived from artifacts and so is current; the OBLIGATIONS are as the "
        "coordinator last wrote them.</span></li>"
        "<li><span class=k>the pin</span><span class=v>a project names one release by root, "
        "version, revision, digest and state. The pin is checked here, not believed.</span>"
        "</li>"
        "<li><span class=k>a lens</span><span class=v>a stylesheet. It moves surfaces and "
        "never a word of the reading, and every lens keeps the four state colours "
        "separable.</span></li>"
        "</ul></section>"
        "<section class=setgroup><div class=head><h2>where do I find…?</h2></div>"
        "<div class=tw><table><thead><tr><th>question</th><th>answer</th><th>where</th></tr>"
        "</thead><tbody>" + questions + "</tbody></table></div></section>"
        "<section class=setgroup><div class=head><h2>what needs a person</h2></div><ul>"
        "<li><span class=k>freezing a release</span><span class=v>moving a pack to "
        "QUALIFIED_AND_FROZEN is a human act. This release ships no verb that promotes "
        "itself.</span></li>"
        "<li><span class=k>ending a worker</span><span class=v>classifying a stalled worker is "
        "shipped; ending one is escalated. There is no termination verb in this release."
        "</span></li>"
        "<li><span class=k>publishing anything</span><span class=v>a push, a tag, a remote, a "
        "release — every one is a human decision with a numbered row in the HITL matrix."
        "</span></li>"
        "<li><span class=k>accepting a finding</span><span class=v>a material finding may be "
        "closed, refuted, or accepted by a person. The third is recorded as a human decision."
        "</span></li></ul></section>"
        "</div>")


def render_console(sites: list, title: str = "Runtime Pack — console", *,
                   theme: str = "", accent: str = "") -> str:
    """The whole application as one self-contained page.

    Every view is written visible. The script hides all but one on load, so a
    browser that runs nothing shows every view stacked — long, and complete.
    """
    root_attrs = f' data-theme="{_ESC(theme)}"' if theme else ""
    accent_rule = f"<style>:root{{--accent:{_ESC(accent)}}}</style>" if accent else ""
    _INDEX.clear()
    _READINGS.clear()
    for at, site in enumerate(sites):
        _INDEX[id(site)] = at
    body = [_rail(sites), "<div class=surface>", _global_bar(sites, theme), _finder(sites)]

    body.append(_view("overview", "Overview", "which project should I open?",
                      "<div class=filters><span class=t>show</span>"
                      "<button data-od='minimal'>minimal</button>"
                      "<button data-od='balanced' aria-pressed='true'>balanced</button>"
                      "<button data-od='full'>full</button></div>"
                      "<div class=filters>"
                      "<input type=search id=overview-search placeholder='filter projects'>"
                      "<span class=t>show</span>"
                      "<button data-tone-filter='attention'>needs attention</button>"
                      "<button data-tone-filter='bad'>defect</button>"
                      "<button data-tone-filter='warn'>blocked or waiting</button>"
                      "<button data-tone-filter='unknown'>unknown</button></div>"
                      + "<div class=onlyminimal>"
                      + _telemetry(sites, kinds=("attention", "projects")) + "</div>"
                      + "<div class=notminimal>"
                      + _telemetry(sites, kinds=("projects", "workers", "attention",
                                                 "freshness")) + "</div>"
                      + _widget("global:overview", "Project matrix",
                                _overview(sites).replace("<table>", "<table id=overview-table>",
                                                          1), "global")
                      + _widget("global:attention", "Attention across projects",
                                _attention_across(sites), "global").replace(
                          "<section ", "<section id=attention-widget ", 1)
                      + "<div class=onlyfull>"
                      + _telemetry(sites, kinds=("audits", "capacity", "budgets",
                                                "recent-activity", "recent-events"))
                      + _telemetry(sites, kinds=("budget-meters",))
                      + _widget("global:full-workers", "Every job", _kind_table(
                          sites, "job",
                          [("·state", "state"), ("job", "job"), ("owner", "owner"),
                           ("subject", "subject"), ("deadline", "deadline"),
                           ("progress", "last observable progress")],
                          "No project declares an outstanding job."), "global")
                      + _widget("global:full-output", "Durable output", _kind_table(
                          sites, "output",
                          [("·state", "recovery state"), ("task", "task"),
                           ("examined", "what is there")],
                          "No project declares an output root."), "global")
                      + _widget("global:full-audits", "Audits", _kind_table(
                          sites, "audit",
                          [("·state", "subject vs candidate"), ("audit", "audit"),
                           ("subject", "subject"), ("candidate", "candidate")],
                          "No audit states a subject."), "global")
                      + _widget("global:full-budgets", "Budgets", _kind_table(
                          sites, "budget", [("·state", "used")],
                          "No project declares a budget."), "global")
                      + _widget("global:full-capacity", "Capacity", _kind_table(
                          sites, "capacity",
                          [("·state", "remaining"), ("pool", "pool"), ("resets", "resets")],
                          "No project declares a capacity observation."), "global")
                      + _widget("global:full-evidence", "Standing evidence", _kind_table(
                          sites, "evidence", [("·state", "reading")],
                          "No project declares standing evidence."), "global")
                      + _widget("global:full-history", "History and public safety",
                                _history(sites), "global")
                      + _widget("global:full-identity", "Identity and release",
                                _identity(sites), "global")
                      + "</div>"))
    body.append(_view("all", "All systems", "everything worth knowing, on one page",
                      _all_systems(sites)))
    body.append(_view("control", "Control room",
                      "one screen to leave up while the work runs", _control_room(sites)))
    body.append(_view("projects", "Projects", "what is in the registry, and can it be read?",
                      _widget("global:projects", "Registry", _projects(sites), "global")))
    body.append(_view(
        "workers", "Workers", "what is running, what finished, what is overdue?",
        _widget("global:workers", "Workers", _kind_table(sites, "job",
                    [("·state", "state"), ("job", "job"), ("expects", "expects"),
                     ("owner", "owner"), ("subject", "subject"), ("deadline", "deadline"),
                     ("progress", "last observable progress")],
                    "No project declares an outstanding job."), "global")
        + _widget("global:output", "Durable output", _kind_table(sites, "output",
                      [("·state", "recovery state"), ("task", "task"), ("root", "output root"),
                       ("examined", "what is there")],
                      "No project declares an output root."), "global")))
    body.append(_view(
        "audits", "Audits & evidence", "is the evidence current, and about the right tree?",
        _widget("global:audits", "Audit status", _kind_table(sites, "audit",
                    [("·state", "subject vs candidate"), ("audit", "audit"),
                     ("subject", "subject revision"), ("candidate", "declared candidate"),
                     ("owner", "executor")],
                    "No project has an audit in flight that states a subject."), "global")
        + _widget("global:evidence", "Standing evidence",
                  _kind_table(sites, "evidence", [("·state", "reading")],
                              "No project declares standing evidence."), "global")))
    body.append(_view("capacity", "Capacity", "can anything be dispatched?",
                      _widget("global:capacity", "Capacity", _kind_table(sites, "capacity",
                                  [("·state", "remaining"), ("pool", "pool"),
                                   ("provider", "provider"), ("window", "window"),
                                   ("resets", "resets"), ("observed", "observed")],
                                  "No project declares a capacity observation."), "global")))
    body.append(_view("history", "History & public safety",
                      "when did code change, what was the run doing, and what would "
                      "publishing this expose?",
                      _widget("global:history", "History & public safety",
                              _history_view(sites), "global")))
    body.append(_view("identity", "Identity & release",
                      "what release is each project actually on?",
                      _widget("global:identity", "Identity & release", _identity(sites),
                              "global")))

    for index, site in enumerate(sites):
        if site.view is None:
            inner = (f"<ul><li class=unknown><span class=k>{UNKNOWN}</span><span class=v>"
                     f"{_ESC(site.unreadable)}</span></li>"
                     f"<li class=muted><span class=k>named</span><span class=v>"
                     f"{_ESC(str(site.root))}</span></li></ul>")
        else:
            inner = projection.render_body(site.view, f"{site.name} — project detail",
                                           widget_prefix=f"p{index}")
            # ONE PROJECT'S OWN SHAPE, above its panels. The same instruments,
            # scoped to it, so the reader sees the shape before the detail.
            inner = inner.replace(
                "<main>",
                "<div class=instruments-wide>"
                + _telemetry([site], kinds=("workers", "attention", "audits", "capacity",
                                            "budgets", "freshness", "budget-meters",
                                            "recent-activity", "recent-events"))
                + "</div><main>", 1)
        body.append(_view(f"project:{index}", site.name,
                          "the whole position of one project", inner))

    body.append(_view("custom", "Custom views",
                      "the arrangement this operator wants, kept in this browser",
                      _custom_view(sites)))
    body.append(_view("settings", "Settings", "lens, accent, density — and what this page is not",
                      _settings(sites)))
    body.append(_view("help", "Help",
                      "what this is, what the words mean, and where to find things",
                      _help(sites)))

    #: The widget sources. Every one is a section already rendered above; these
    #: are the global ones, which have no other home, and they are written into
    #: the views that show them rather than duplicated.
    body.append("</div>")
    return "\n".join([
        "<!doctype html>", f"<html lang=\"en\"{root_attrs}>", "<head>",
        "<meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
        f"<title>{_ESC(title)}</title>",
        f"<style>{projection._STYLE}{_SHELL_STYLE}</style>", accent_rule,
        "</head>", "<body>", "<div class=app>", *body, "</div>",
        f"<script>{_SCRIPT}</script>", "</body></html>"])


def _cli(argv: list) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="console.py",
        description="One read-only page over many projects. Writes nothing.")
    parser.add_argument("roots", nargs="*", help="project roots to read")
    parser.add_argument("--registry", default="", help="a JSON file naming the projects")
    parser.add_argument("--contract", default="PROJECT.yaml")
    parser.add_argument("--continuation", default="CONTINUATION.json")
    parser.add_argument("--capacity", default="CAPACITY.json")
    parser.add_argument("--title", default="Runtime Pack — console")
    parser.add_argument("--theme", default="", choices=list(projection.LENSES),
                        help="the lens this page opens in; presentation only")
    parser.add_argument("--accent", default="", help="a CSS colour for the presentation accent")
    args = parser.parse_args(argv)

    entries = [(None, Path(r)) for r in args.roots]
    if args.registry:
        entries = registry(args.registry) + entries
    sites = survey(entries, contract=args.contract, continuation_record=args.continuation,
                   capacity_observation=args.capacity)
    print(render_console(sites, args.title, theme=args.theme, accent=args.accent))
    return 1 if any(s.view is None or s.view.unknowns for s in sites) else 0


if __name__ == "__main__":
    import sys

    from errors import run_cli
    from console import _cli as _entry

    raise SystemExit(run_cli(_entry, sys.argv[1:]))
