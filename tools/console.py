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

import json
from dataclasses import dataclass, field
from pathlib import Path

import projection
from projection import Tone, UNKNOWN

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
    ("projects", "Projects", "what is in the registry, and can it be read?"),
    ("workers", "Workers", "what is running, what finished, what is overdue?"),
    ("audits", "Audits & evidence", "is the evidence current, and about the right tree?"),
    ("capacity", "Capacity", "can anything be dispatched?"),
    ("history", "History & public safety", "what would publishing this expose?"),
    ("identity", "Identity & release", "what release is each project actually on?"),
    ("custom", "Custom views", "the arrangement this operator wants, kept in this browser"),
    ("settings", "Settings", "lens, accent, density — and what this page is not"),
)

_SHELL_STYLE = """
/* ---- the application shell ------------------------------------------------ */
body{min-height:100vh}
.app{display:grid;grid-template-columns:1fr;min-height:100vh}
@media(min-width:1000px){.app{grid-template-columns:216px 1fr}}
.rail{background:var(--panel-2);border-right:1px solid var(--rule-strong);
display:flex;flex-direction:column;gap:2px;padding:0 0 10px;min-width:0}
.brand{padding:11px 14px 9px;border-bottom:1px solid var(--rule)}
.brand b{display:block;font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--ink)}
.brand span{display:block;font-size:9.5px;letter-spacing:.16em;text-transform:uppercase;
color:var(--faint);margin-top:2px}
.rail h4{margin:11px 14px 3px;font-size:8.5px;letter-spacing:.2em;text-transform:uppercase;
color:var(--faint);font-weight:700}
.go{display:flex;align-items:center;gap:8px;width:100%;text-align:left;background:none;
border:0;border-left:2px solid transparent;color:var(--dim);font:inherit;font-size:11.5px;
padding:5px 14px;cursor:pointer}
.go:hover{color:var(--ink);background:var(--panel-3)}
.go[aria-current="true"]{color:var(--ink);border-left-color:var(--accent);background:var(--panel-3)}
.go .n{margin-left:auto;font-size:9.5px;color:var(--faint)}
.go .dot{width:7px;height:7px;flex:0 0 auto;border-radius:50%;background:var(--rule-strong)}
.go .dot.bad{background:var(--bad)} .go .dot.warn{background:var(--warn)}
.go .dot.unknown{background:var(--unknown)} .go .dot.good{background:var(--good)}
.surface{min-width:0}

.gbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;padding:7px 16px;
background:var(--panel);border-bottom:1px solid var(--rule-strong);font-size:11px}
.gbar .t{color:var(--faint);text-transform:uppercase;letter-spacing:.13em;font-size:9px}
.gbar .lens{margin-left:auto;display:flex;gap:1px;background:var(--rule);flex-wrap:wrap}
.lens button{background:var(--panel-2);border:0;color:var(--dim);font:inherit;font-size:10px;
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
.view>h2.vh{margin:0;padding:12px 16px 4px;font-size:15px;letter-spacing:-.01em;color:var(--ink)}
.view>p.vq{margin:0;padding:0 16px 11px;font-size:11.5px;color:var(--dim);
border-bottom:1px solid var(--rule)}

/* ---- tables: the cross-project views -------------------------------------- */
.tw{overflow-x:auto;border-bottom:1px solid var(--rule)}
table{border-collapse:collapse;width:100%;font-size:11.5px;min-width:640px}
th{text-align:left;font-size:8.5px;letter-spacing:.15em;text-transform:uppercase;
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
td small{display:block;color:var(--faint);font-size:10px}
/* Long prose in a table cell: clamped, never cut. The whole string stays in the
   document and in the element's title, so nothing is removed — a row simply
   stops being able to push every other row off the screen. */
.clamp{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
line-clamp:2}
.clamp1{-webkit-line-clamp:1;line-clamp:1}
.pill{display:inline-block;padding:0 6px;border:1px solid var(--rule-strong);color:var(--dim);
font-size:10px;margin-right:3px;white-space:nowrap}
.pill.bad{color:var(--bad);border-color:var(--bad);background:var(--bad-bg)}
.pill.warn{color:var(--warn);border-color:var(--warn);background:var(--warn-bg)}
.pill.unknown{color:var(--unknown);border-color:var(--unknown);background:var(--unknown-bg)}
.pill.good{color:var(--good);border-color:var(--good)}
.none{padding:10px 16px;color:var(--faint);font-size:11.5px}

/* ---- filters -------------------------------------------------------------- */
.filters{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:8px 16px;
background:var(--panel-2);border-bottom:1px solid var(--rule)}
.filters input[type=search],.filters input[type=text]{background:var(--ground);
border:1px solid var(--rule-strong);color:var(--ink);font:inherit;font-size:11.5px;
padding:3px 8px;min-width:170px}
.filters button{background:var(--panel);border:1px solid var(--rule-strong);color:var(--dim);
font:inherit;font-size:10px;letter-spacing:.08em;text-transform:uppercase;padding:3px 9px;
cursor:pointer}
.filters button:hover{color:var(--ink);border-color:var(--accent)}
.filters button[aria-pressed="true"]{background:var(--accent);color:var(--ground);
border-color:var(--accent);font-weight:700}
.filters .t{color:var(--faint);text-transform:uppercase;letter-spacing:.13em;font-size:9px}

/* ---- the custom view builder ---------------------------------------------- */
.builder{display:grid;grid-template-columns:1fr;gap:1px;background:var(--rule)}
@media(min-width:1000px){.builder{grid-template-columns:262px 1fr}}
.catalog{background:var(--panel);padding:10px 14px;max-height:78vh;overflow-y:auto}
.catalog details>summary{cursor:pointer;list-style:none;font-size:11px;color:var(--dim);
padding:4px 0;border-top:1px solid var(--rule);user-select:none}
.catalog details>summary::-webkit-details-marker{display:none}
.catalog details>summary::before{content:"▸ "}
.catalog details[open]>summary::before{content:"▾ "}
.catalog details>summary .n{color:var(--faint);font-size:9.5px}
@media(max-width:999px){.catalog{max-height:none}}
.catalog h5{margin:9px 0 5px;font-size:8.5px;letter-spacing:.18em;text-transform:uppercase;
color:var(--faint)}
.catalog label{display:flex;gap:7px;align-items:baseline;font-size:11.5px;padding:2px 0;
cursor:pointer;color:var(--dim)}
.catalog label:hover{color:var(--ink)}
.catalog .ord{margin-left:auto;display:flex;gap:2px}
.catalog .ord button{background:var(--panel-2);border:1px solid var(--rule);color:var(--faint);
font:inherit;font-size:10px;line-height:1;padding:1px 5px;cursor:pointer}
.canvas{background:var(--ground);padding:10px;display:grid;gap:10px;
grid-template-columns:repeat(var(--cols,2),minmax(0,1fr));align-content:start}
@media(max-width:760px){.canvas{grid-template-columns:1fr}}
.canvas>*{grid-column:span var(--span,1)}
.canvas .empty{grid-column:1/-1;color:var(--faint);font-size:11.5px;padding:16px;
border:1px dashed var(--rule-strong);text-align:center}
[data-density="compact"] li{padding-top:1px;padding-bottom:1px}
[data-density="compact"] .state{font-size:22px}
[data-density="expanded"] li{padding-top:5px;padding-bottom:5px;line-height:1.6}
[data-density="expanded"] .state{font-size:34px}

/* ---- narrow: the rail becomes a bar ---------------------------------------- */
@media(max-width:999px){
  .app{grid-template-columns:1fr;min-width:0}
  .surface{min-width:0}
  .gbar{gap:6px 12px;font-size:10.5px}
  .gbar .lens{margin-left:0;width:100%;overflow-x:auto;scrollbar-width:none}
  .gbar .lens::-webkit-scrollbar{display:none}
  .rail{position:sticky;bottom:0;order:2;flex-direction:row;overflow-x:auto;gap:0;
  border-right:0;border-top:1px solid var(--rule-strong);padding:0;
  scrollbar-width:none;z-index:5}
  .rail::-webkit-scrollbar{display:none}
  .brand,.rail h4{display:none}
  .go{width:auto;white-space:nowrap;border-left:0;border-top:2px solid transparent;
  padding:8px 12px;font-size:11px}
  .go[aria-current="true"]{border-left-color:transparent;border-top-color:var(--accent)}
  .surface{order:1}
  .view>h2.vh{padding-top:10px;font-size:14px}
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
  td::before{content:attr(data-label);display:block;font-size:8px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--faint);margin-bottom:1px}
  td.num{text-align:left}
  td:empty{display:none}
  /* the overview's own hierarchy: who, then what, then the counters */
  /* A state name is one long unbreakable token. Sharing a line with the
     project name pushed it past the viewport — the one thing a phone layout
     may not do — so each gets its own. */
  .c-project,.c-state{grid-column:1/-1}
  .c-running,.c-complete,.c-unknown,.c-stalled{grid-column:span 1}
  .c-project .s{font-size:14.5px} .c-state .s{font-size:13px}
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


def _project_cell(site: "Site") -> str:
    """WHO this row is about. The state has its own column; putting it here too
    made the first column repeat the second and pushed the name into a
    footnote."""
    where = site.root.name or str(site.root)
    return _td("project", f"<span class=s>{_ESC(site.name)}</span>"
               + (f"<small>{_ESC(where)}</small>" if where != site.name else ""))


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
            rows.append(f"<tr data-tone='{cell.tone}'>"
                        + _td("project", f"<span class=s>{_ESC(site.name)}</span>"
                              f"<small>{_ESC(cell.label)}</small>") + values + "</tr>")
    if not rows:
        return f"<p class=none>{_ESC(empty)}</p>"
    heads = "".join(f"<th data-sort=text>{_ESC(title)}</th>" for _, title in columns)
    return ("<div class=tw><table><thead><tr><th data-sort=text>project</th>" + heads +
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


def _history(sites: list) -> str:
    """What publishing each project would expose, as its own record states it."""
    rows = []
    for site in sites:
        pin = site.one("pin")
        readings = {c.label: c for c in site.figures("evidence")}
        safety = readings.get("public safety")
        gates = readings.get("gates")
        rows.append(
            f"<tr><td><span class=s>{_ESC(site.name)}</span></td>"
            + f"<td>{_ESC(pin.fields.get('publication', UNKNOWN)) if pin else UNKNOWN}</td>"
            + (f"<td class='{safety.tone}'>{_ESC(safety.value)}</td>" if safety else
               f"<td class=unknown><span class='s unknown'>{UNKNOWN}</span>"
               f"<small>no public-safety reading is declared</small></td>")
            + (f"<td class='{gates.tone}'>{_ESC(gates.value)}</td>" if gates else
               f"<td class=unknown><span class='s unknown'>{UNKNOWN}</span></td>") + "</tr>")
    if not rows:
        return "<p class=none>No project was named.</p>"
    return ("<div class=tw><table><thead><tr><th>project</th><th>publication intent</th>"
            "<th>public-safety reading</th><th>gates</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table></div>")


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
             ("global:projects", "Registry", "global")]
    for index, site in enumerate(sites):
        if site.view is None:
            continue
        found.append((f"p{index}:command", f"{site.name} — state & next action", site.name))
        for order, panel in enumerate(site.view.panels):
            found.append((f"p{index}:{order}", f"{site.name} — {panel.title}", site.name))
    return found


def _attention_across(sites: list) -> str:
    rows = []
    for site in sites:
        if site.view is None:
            rows.append(f"<tr data-tone=unknown><td><span class=s>{_ESC(site.name)}</span></td>"
                        f"<td class=unknown><span class='s unknown'>unreadable</span></td>"
                        f"<td>{_ESC(site.unreadable)}</td></tr>")
            continue
        for line in site.view.attention:
            rows.append(f"<tr data-tone='{line.tone}'><td><span class=s>{_ESC(site.name)}</span>"
                        f"</td><td class='{line.tone}'><span class='s {line.tone}'>"
                        f"{_ESC(line.tone)}</span></td><td>{_ESC(line.text)}</td></tr>")
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
            f"<h2 class=vh>{_ESC(title)}</h2><p class=vq>{_ESC(question)}</p>{body}</section>")


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

  // ---- density and accent ---------------------------------------------------
  function density(name) {
    if (['compact', 'normal', 'expanded'].indexOf(name) < 0) { name = 'normal'; }
    document.body.setAttribute('data-density', name);
    [].forEach.call(document.querySelectorAll('[data-density-set]'), function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.densitySet === name));
    });
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
  // An arrangement to start from, used only when this browser has never been
  // given one. Choosing to have none is a choice and is kept.
  var OPENING = [{ id: 'global:overview', span: 2 }, { id: 'global:attention', span: 2 }];
  function current() {
    var name = typeof prefs.layout === 'string' ? prefs.layout : 'default';
    var all = layouts();
    var one = all[name];
    var chosen = Array.isArray(one && one.widgets) ? one.widgets
               : (prefs.layouts === undefined ? OPENING : []);
    return { name: name, widgets: chosen,
             cols: Math.min(4, Math.max(1, Number(one && one.cols) || 2)) };
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
    var label = document.getElementById('layout-name');
    if (label) { label.textContent = view.name; }
  }
  function edit(change) {
    var view = current();
    var all = layouts();
    all[view.name] = change({ widgets: view.widgets.slice(), cols: view.cols });
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
  [].forEach.call(document.querySelectorAll('[data-cols]'), function (b) {
    b.addEventListener('click', function () {
      edit(function (v) { v.cols = Math.min(4, Math.max(1, Number(b.dataset.cols) || 2));
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
      rebuildPresets(); paint();
    });
  }
  function rebuildPresets() {
    var host = document.getElementById('layout-presets');
    if (!host) { return; }
    host.innerHTML = '';
    Object.keys(layouts()).concat(['default']).filter(function (n, i, a) {
      return a.indexOf(n) === i;
    }).forEach(function (name) {
      var b = document.createElement('button');
      b.textContent = name;
      b.setAttribute('aria-pressed', String(name === current().name));
      b.addEventListener('click', function () {
        prefs.layout = name; keep(prefs); rebuildPresets(); paint();
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
      rebuildPresets(); paint();
    });
  }
  var resetting = document.getElementById('layout-reset');
  if (resetting) {
    resetting.addEventListener('click', function () {
      prefs = {}; keep(prefs);
      lens(''); density('normal'); accent('');
      rebuildPresets(); paint(); show('overview');
    });
  }

  // ---- restore ---------------------------------------------------------------
  lens(typeof prefs.lens === 'string' ? prefs.lens : root.getAttribute('data-theme') || '');
  density(typeof prefs.density === 'string' ? prefs.density : 'normal');
  accent(typeof prefs.accent === 'string' ? prefs.accent : '');
  rebuildPresets();
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
    ages = [c.value for s in readable for c in s.figures("freshness")]
    lenses = "".join(
        f"<button data-lens='{l}' aria-pressed='{str(l == lens).lower()}'>"
        f"{_ESC(l or 'terminal')}</button>" for l in projection.LENSES)
    return ("<div class=gbar>"
            f"<span class=t>projects</span><span>{len(sites)}</span>"
            f"<span class=t>readable</span><span>{len(readable)}</span>"
            f"<span class=t>marked</span><span>{flagged}</span>"
            f"<span class=t>oldest reading</span><span>{_ESC(max(ages) if ages else UNKNOWN)}</span>"
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
                f"<button data-span='{_ESC(node_id)}' title='width'>⇔</button>"
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
        + "".join(f"<button data-cols='{n}'>{n}</button>" for n in (1, 2, 3, 4))
        + "<span class=t>preset</span><span id=layout-presets class=lens></span>"
        + "<input type=text id=layout-new placeholder='name a new view' maxlength=40>"
        + "<button id=layout-create>save as</button>"
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


def _settings(sites: list) -> str:
    swatches = ("", "#38bdf8", "#2bf58d", "#f0b429", "#c4a2ff", "#ff6b8b", "#cfd6dd")
    return (
        "<div class=filters><span class=t>density</span>"
        + "".join(f"<button data-density-set='{d}'>{d}</button>"
                  for d in ("compact", "normal", "expanded"))
        + "<span class=t>accent</span>"
        + "".join(f"<button data-accent='{a}' style=\"{'color:' + a if a else ''}\">"
                  f"{_ESC(a or 'lens default')}</button>" for a in swatches)
        + "</div>"
        "<ul><li><span class=k>what this page is</span><span class=v>a reading of "
        "durable state, rebuilt from artifacts every time it is generated. It is not live: it "
        "is as old as the reading times shown beside each project, and re-reading means running "
        "the command again.</span></li>"
        "<li><span class=k>what it stores</span><span class=v>one key in this browser, holding "
        "the lens, the density, the accent and the custom layouts. Nothing else, nowhere else."
        "</span></li>"
        "<li><span class=k>what it cannot do</span><span class=v>authorise, schedule, wake, "
        "end a worker, change a record, alter evidence, or infer an authority nobody granted. "
        "Deleting this page breaks no checker.</span></li>"
        "<li class=action><span class=k>where the authority is</span><span class=v>the durable "
        "artifacts each project owns. Where this page and those disagree, THIS is the defect."
        "</span></li></ul>")


def render_console(sites: list, title: str = "Runtime Pack — console", *,
                   theme: str = "", accent: str = "") -> str:
    """The whole application as one self-contained page.

    Every view is written visible. The script hides all but one on load, so a
    browser that runs nothing shows every view stacked — long, and complete.
    """
    root_attrs = f' data-theme="{_ESC(theme)}"' if theme else ""
    accent_rule = f"<style>:root{{--accent:{_ESC(accent)}}}</style>" if accent else ""
    body = [_rail(sites), "<div class=surface>", _global_bar(sites, theme)]

    body.append(_view("overview", "Overview", "which project should I open?",
                      "<div class=filters>"
                      "<input type=search id=overview-search placeholder='filter projects'>"
                      "<span class=t>show</span>"
                      "<button data-tone-filter='attention'>needs attention</button>"
                      "<button data-tone-filter='bad'>defect</button>"
                      "<button data-tone-filter='warn'>blocked or waiting</button>"
                      "<button data-tone-filter='unknown'>unknown</button></div>"
                      + _widget("global:overview", "Project matrix",
                                _overview(sites).replace("<table>", "<table id=overview-table>",
                                                          1), "global")
                      + _widget("global:attention", "Attention across projects",
                                _attention_across(sites), "global")))
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
                      "what would publishing this expose?",
                      _widget("global:history", "History & public safety", _history(sites),
                              "global")))
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
        body.append(_view(f"project:{index}", site.name,
                          "the whole position of one project", inner))

    body.append(_view("custom", "Custom views",
                      "the arrangement this operator wants, kept in this browser",
                      _custom_view(sites)))
    body.append(_view("settings", "Settings", "lens, accent, density — and what this page is not",
                      _settings(sites)))

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
