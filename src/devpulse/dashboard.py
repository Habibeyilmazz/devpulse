"""Render a report as one self-contained HTML file: inline CSS, no network requests."""

from __future__ import annotations

import base64
import calendar
import hashlib
import math
from datetime import date, timedelta
from html import escape as esc

from devpulse import __version__
from devpulse.stats import SESSION_GAP_MIN, SESSION_LEAD_MIN, Period, Report, fmt_day, fmt_minutes, tiles

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
BAR_AREA_PX = 132
MAX_ROWS = 8  # bars per list before the rest folds into one row
MAX_SUBJECTS = 50

CSS = """
:root{color-scheme:light;--plane:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#6f6e68;
--grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.10);--accent:#2a78d6;--rest:#94938a;
--q0:#eeede8;--q1:#b7d3f6;--q2:#86b6ef;--q3:#5598e7;--q4:#256abf;--q5:#104281}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--plane:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;
--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--accent:#3987e5;
--rest:#6b6a66;--q0:#262624;--q1:#184f95;--q2:#256abf;--q3:#3d82d6;--q4:#6ba6ea;--q5:#a9ccf5}}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;overflow-wrap:break-word}
main{max-width:1120px;margin:0 auto;padding:32px 16px 48px}
h1{font-size:clamp(28px,5vw,40px);line-height:1.1;margin:4px 0 6px;letter-spacing:-.02em}
h2{font-size:15px;font-weight:600;margin:0 0 2px}
p{margin:0}
.eyebrow{font-size:13px;color:var(--ink2)}
.eyebrow b{color:var(--ink);font-weight:650;margin-right:.4em}
code{font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:normal}
.sub{color:var(--ink2)}
.note{color:var(--ink2);font-size:13px;margin-bottom:14px}
.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:16px;margin-top:16px}
.card{grid-column:span 12;background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;min-width:0}
@media (min-width:860px){.w7{grid-column:span 7}.w6{grid-column:span 6}.w5{grid-column:span 5}}
.hero{display:flex;flex-wrap:wrap;gap:20px 48px;align-items:center;margin-top:20px;padding:24px 0 8px;border-top:2px solid var(--ink)}
.figure{font-size:clamp(64px,11vw,96px);font-weight:650;line-height:.9;letter-spacing:-.04em;font-variant-numeric:tabular-nums}
.figure small{display:block;font-size:15px;line-height:1.4;font-weight:400;letter-spacing:0;color:var(--ink2);margin-top:12px}
.tiles{flex:1 1 560px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px 20px;margin:0}
.tiles div{border-top:1px solid var(--grid);padding-top:8px}
@media (min-width:700px){.tiles{grid-template-columns:repeat(4,minmax(0,1fr))}}
.tiles dt{font-size:12.5px;color:var(--ink2)}
.tiles dd{margin:0;font-size:17px;font-weight:600;font-variant-numeric:tabular-nums}
.tiles small{display:block;font-size:12.5px;font-weight:400;color:var(--ink2)}
.tiles div:nth-child(-n+4) small{display:inline;margin-left:4px}
.wrapped{display:grid;gap:20px 28px;margin:0}
/* 1, 2 or 4 across: never three with the fourth alone on a row */
@media (min-width:560px){.wrapped{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (min-width:980px){.wrapped{grid-template-columns:repeat(4,minmax(0,1fr))}}
.wrapped dt{font-size:12.5px;color:var(--ink2)}
.wrapped dd{margin:2px 0 0;font-size:clamp(22px,3vw,28px);font-weight:650;letter-spacing:-.02em;line-height:1.15}
.wrapped small{display:block;margin-top:4px;font-size:13px;font-weight:400;letter-spacing:0;color:var(--ink2)}
.heat{display:grid;grid-template-columns:2.4rem repeat(24,minmax(0,1fr));gap:2px;align-items:center}
.heat span,.cal span{font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap}
.heat i,.cal i{display:block;aspect-ratio:1;border-radius:3px;background:var(--q0)}
@media (max-width:480px){.heat i{aspect-ratio:auto;height:14px}}
/* weekday labels take no height: on a phone the squares are smaller than the text and must still set the row */
.heat span:nth-child(25n+1),.cal span:nth-child(n+2):nth-child(-n+8){display:flex;align-items:center;align-self:center;height:0;min-height:0}
.q1{background:var(--q1)!important}.q2{background:var(--q2)!important}.q3{background:var(--q3)!important}
.q4{background:var(--q4)!important}.q5{background:var(--q5)!important}
.scale{display:flex;gap:3px;align-items:center;justify-content:flex-end;margin-top:12px;font-size:11px;color:var(--muted)}
.scale i{width:11px;height:11px;border-radius:3px;background:var(--q0)}
.scroll{overflow-x:auto}
.cals{display:flex;flex-direction:column;gap:14px}
.cal{display:grid;grid-template-rows:auto repeat(7,minmax(0,1fr));grid-template-columns:2rem;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);gap:2px}
.cal i.out{background:none}
.cal i.later{background:none;box-shadow:inset 0 0 0 1px var(--grid)}
.cal span{display:flex;align-items:center;min-height:16px}
.cal span:nth-last-child(8){justify-content:flex-end}
@media (min-width:820px){.cals{display:grid;grid-template-rows:auto repeat(7,minmax(0,1fr));grid-template-columns:2rem;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);gap:2px}
.cal{display:contents}.cal+.cal span:nth-child(-n+8){display:none}}
.cols{display:flex;gap:2px;align-items:flex-end;border-bottom:1px solid var(--axis);height:150px}
.cols>div{flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}
.cols b{font-size:11px;font-weight:600;color:var(--ink2);font-variant-numeric:tabular-nums}
.cols i{display:block;width:100%;max-width:24px;border-radius:4px 4px 0 0;background:var(--accent)}
.cols i.rest{background:var(--rest)}
.xs{display:flex;gap:2px;margin-top:6px}
.xs span{flex:1;min-width:0;text-align:center;font-size:11px;color:var(--muted);white-space:nowrap}
.bars{display:grid;grid-template-columns:minmax(4.5rem,max-content) minmax(0,1fr) max-content;gap:10px 12px;align-items:center}
.bars .name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:14rem}
.bars .track{display:block}
.bars .track i{display:block;height:12px;min-width:2px;border-radius:0 4px 4px 0;background:var(--accent)}
.bars .num{font-size:13px;color:var(--ink2);font-variant-numeric:tabular-nums;text-align:right}
ol.big{margin:0;padding:0;list-style:none}
ol.big li{display:grid;grid-template-columns:auto 1fr auto;gap:2px 14px;align-items:baseline;padding:8px 0;border-top:1px solid var(--grid)}
ol.big li:first-child{border-top:0;padding-top:0}
ol.big b{font-weight:600;white-space:nowrap}
ol.big span,ol.big time{font-variant-numeric:tabular-nums;white-space:nowrap}
ol.big span{grid-column:3;color:var(--ink2)}
ol.big small{grid-column:1/-1;min-width:0;font-size:13px;color:var(--ink2)}
@media (min-width:700px){ol.sessions li{grid-template-columns:7rem 8rem 1fr auto}ol.sessions small{grid-column:3;grid-row:1}ol.sessions span{grid-column:4}}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{text-align:left;font-weight:500;color:var(--ink2);font-size:12.5px}
th,td{padding:7px 12px 7px 0;border-top:1px solid var(--grid);vertical-align:top}
tr:first-child th{border-top:0;padding-top:0}
.scroll tr:first-child th{position:sticky;top:0;background:var(--surface);box-shadow:0 1px 0 var(--grid)}
td.n,th.n{font-variant-numeric:tabular-nums;white-space:nowrap}
td.n,th[scope=col].n{text-align:right}
th[scope=row]{font-size:inherit}
td.z{color:var(--muted)}
details{border-top:1px solid var(--grid);padding:10px 0}
details:first-of-type{border-top:0}
summary{cursor:pointer;font-weight:600;padding:4px 0}
summary span{font-weight:400;color:var(--ink2);margin-left:8px;font-size:13px}
details ul{margin:8px 0 4px;padding-left:20px;color:var(--ink2);columns:2 320px;column-gap:40px}
details li{break-inside:avoid}
details .scroll{max-height:320px;overflow:auto;margin-top:10px}
.ai p{max-width:70ch;margin-top:8px}
.ai .next{margin-top:14px;padding-top:12px;border-top:1px solid var(--grid)}
footer{margin-top:24px;color:var(--muted);font-size:12.5px}
#tip{position:fixed;left:0;top:0;z-index:9;pointer-events:none;background:var(--ink);color:var(--surface);
font-size:12.5px;padding:5px 9px;border-radius:6px;white-space:nowrap}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}
.empty p{max-width:70ch;color:var(--ink2);margin-top:6px}
.empty dl{display:grid;grid-template-columns:max-content 1fr;gap:8px 20px;margin:14px 0 0;align-items:baseline}
.empty dd{margin:0;color:var(--ink2)}
@media (max-width:560px){.empty dl{grid-template-columns:1fr;gap:2px}.empty dd{margin-bottom:10px}}
@media (forced-colors:active){.heat i,.cal i,.scale i,.cols i,.bars i{forced-color-adjust:none}}
@media print{*{-webkit-print-color-adjust:exact;print-color-adjust:exact}body{background:none}.card{break-inside:avoid}#tip{display:none}}
"""

# Hover text comes from data-tip attributes; the same numbers are in the tables below the charts.
JS = """
const tip=document.getElementById('tip');
function show(e){const t=e.target.closest&&e.target.closest('[data-tip]');
if(!t){tip.hidden=true;return}
tip.textContent=t.dataset.tip;tip.hidden=false;
const x=Math.max(8,Math.min(e.clientX+12,innerWidth-tip.offsetWidth-8));
const y=e.clientY+18+tip.offsetHeight>innerHeight?e.clientY-tip.offsetHeight-10:e.clientY+18;
tip.style.transform='translate('+x+'px,'+y+'px)'}
addEventListener('pointermove',show);addEventListener('pointerdown',show);
addEventListener('scroll',()=>{tip.hidden=true},true);
"""

# The browser enforces what the footer promises: no requests, and no script but the one above,
# even if some text were ever left unescaped.
CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; "
    f"script-src 'sha256-{base64.b64encode(hashlib.sha256(JS.encode()).digest()).decode()}'"
)


def plural(n: int, word: str) -> str:
    return f"{n:,} {word}" if n == 1 else f"{n:,} {word}s"


def level(n: int, top: int) -> int:
    """Quantise a count into the five steps of the sequential ramp (0 = empty)."""
    return 0 if n <= 0 else max(1, math.ceil(n / top * 5))


def _scale() -> str:
    steps = "".join(f'<i class="q{q}"></i>' for q in range(1, 6))
    return f'<div class="scale" aria-hidden="true">Fewer&nbsp;<i></i>{steps}&nbsp;More</div>'


def _heat(r: Report) -> str:
    top = max(max(row) for row in r.heat)
    cells = ["<span></span>"] + [f"<span>{h:02d}</span>" if h % 3 == 0 else "<span></span>" for h in range(24)]
    for wd, row in enumerate(r.heat):
        cells.append(f"<span>{WEEKDAYS[wd]}</span>")
        for hour, n in enumerate(row):
            tip = f"{WEEKDAYS[wd]} {hour:02d}:00–{hour:02d}:59 · {plural(n, 'commit')}"
            cells.append(f'<i class="q{level(n, top)}" data-tip="{esc(tip)}"></i>')
    busiest = WEEKDAYS[max(range(7), key=lambda wd: sum(r.heat[wd]))]
    return (
        '<div class="heat" role="img" aria-label="Commits by weekday and hour of day. '
        f'Busiest weekday is {busiest}, busiest hour starts at {r.peak_hour:02d}:00.">{"".join(cells)}</div>{_scale()}'
    )


def _calendar(r: Report) -> str:
    """A quarter as one grid; a year as two half-year grids: side by side they read as one, on a phone they stack."""
    top = max(r.per_day.values())
    day = r.period.start - timedelta(days=r.period.start.weekday())
    # a grid's first column: a blank corner, then a label on every other weekday row
    labels = "<span></span>" + "".join(f"<span>{name if i % 2 == 0 else ''}</span>" for i, name in enumerate(WEEKDAYS))
    weeks = []
    while day <= r.period.end:
        week = [day + timedelta(days=i) for i in range(7)]
        firsts = [d for d in week if d.day == 1 and d in r.per_day]
        cells = [f"<span>{calendar.month_abbr[firsts[0].month]}</span>" if firsts else "<span></span>"]
        for d in week:
            if d > r.today and d in r.per_day:  # still to come: an outline, not an empty day
                cells.append('<i class="later"></i>')
            elif d in r.per_day:
                n = r.per_day[d]
                tip = f"{d:%a} {d.day} {d:%b} · {plural(n, 'commit')}"
                cells.append(f'<i class="q{level(n, top)}" data-tip="{esc(tip)}"></i>')
            else:
                cells.append('<i class="out"></i>')
        weeks.append("".join(cells))
        day += timedelta(days=7)
    half = (len(weeks) + 1) // 2
    parts = (weeks[:half], weeks[half:]) if r.period.kind == "year" else (weeks,)
    grids = "".join(f'<div class="cal">{labels}{"".join(part)}</div>' for part in parts)
    return f'<div class="cals" role="img" aria-label="Commits on each day of {r.period.title}.">{grids}</div>{_scale()}'


def _columns(items: list[tuple[str, int, str]], label: str, accent_last_only: bool = False) -> str:
    """Column chart. `items` are (x label, value, tooltip); only the peak (and the last, for a trend) is labelled."""
    top = max((n for _, n, _ in items), default=0) or 1
    peak = max(range(len(items)), key=lambda i: items[i][1])
    cols, xs = [], []
    for i, (x, n, tip) in enumerate(items):
        marked = n and (i == peak or (accent_last_only and i == len(items) - 1))
        cls = ' class="rest"' if accent_last_only and i < len(items) - 1 else ""
        bar = f'<i{cls} style="height:{max(2, round(BAR_AREA_PX * n / top))}px"></i>' if n else ""
        value = f"<b>{n:,}</b>" if marked else ""
        cols.append(f'<div data-tip="{esc(tip)}">{value}{bar}</div>')
        xs.append(f"<span>{esc(x)}</span>")
    if len(items) <= 12:  # short enough to read out; longer ones have the table below
        label += ": " + ", ".join(f"{x} {n:,}" for x, n, _ in items)
    return (
        f'<div class="cols" role="img" aria-label="{esc(label)}">{"".join(cols)}</div>'
        f'<div class="xs" aria-hidden="true">{"".join(xs)}</div>'
    )


def _activity(r: Report) -> str:
    if r.period.kind == "year":
        return _columns([(x, n, f"{x} · {plural(n, 'commit')}") for x, n in r.columns], "Commits per month")
    items = []
    for (x, n), d in zip(r.columns, r.per_day, strict=True):
        # a month only has room for the 1st and every fifth day on the axis
        shown = x if r.period.kind == "week" or d.day == 1 or d.day % 5 == 0 else ""
        items.append((shown, n, f"{d:%a} {d.day} {d:%b} · {plural(n, 'commit')}"))
    return _columns(items, "Commits per day")


def _short(p: Period) -> str:
    return {"week": p.label[5:], "month": f"{p.start:%b}", "quarter": p.label[5:], "year": p.label}[p.kind]


def _trend(r: Report) -> str:
    items = [(_short(p), n, f"{p.title} · {plural(n, 'commit')}") for p, n in r.trend]
    return _columns(items, f"Commits per {r.period.kind}, oldest first", accent_last_only=True)


def _bars(rows: list[tuple[str, int, str]], fold: str) -> str:
    """Horizontal bars. `rows` are (name, value, text shown at the bar's tip)."""
    if len(rows) > MAX_ROWS:
        rest = rows[MAX_ROWS - 1 :]
        rows = rows[: MAX_ROWS - 1] + [(f"{len(rest)} more {fold}", sum(n for _, n, _ in rest), "")]
    top = max((n for _, n, _ in rows), default=0) or 1
    out = []
    for name, n, text in rows:
        text = text or f"{n:,}"
        out.append(
            f'<span class="name" title="{esc(name)}">{esc(name)}</span>'
            f'<span class="track" data-tip="{esc(name)} · {esc(text)}"><i style="width:{100 * n / top:.1f}%"></i></span>'
            f'<span class="num">{esc(text)}</span>'
        )
    return f'<div class="bars">{"".join(out)}</div>'


def _sessions(r: Report) -> str:
    rows = []
    for s in sorted(r.sessions, key=lambda s: -s.minutes)[:5]:
        span = f"{s.start:%H:%M}–{s.end:%H:%M}" if s.commits > 1 else f"{s.start:%H:%M}"
        rows.append(
            f"<li><b>{fmt_day(s.start)}</b><time>{span}</time><span>{fmt_minutes(s.minutes)}</span>"
            f"<small>{plural(s.commits, 'commit')} in {esc(', '.join(s.repos))}</small></li>"
        )
    return f'<ol class="big sessions">{"".join(rows)}</ol>'


def _shipped(r: Report) -> str:
    out = []
    for i, p in enumerate(r.projects):
        subjects = list(dict.fromkeys(c.subject for c in reversed(p.commits)))
        items = "".join(f"<li>{esc(s)}</li>" for s in subjects[:MAX_SUBJECTS])
        if len(subjects) > MAX_SUBJECTS:
            items += f"<li>… and {len(subjects) - MAX_SUBJECTS} more</li>"
        out.append(
            f"<details{' open' if i == 0 and r.period.kind != 'year' else ''}><summary>{esc(p.name)}<span>{plural(len(p.commits), 'commit')}"
            f" · +{p.added:,} / −{p.deleted:,}</span></summary><ul>{items}</ul></details>"
        )
    return "".join(out)


def _tables(r: Report) -> str:
    """The charts' numbers as text, for a screen reader, a keyboard or a copy and paste."""
    per_day = [(d.isoformat(), [n]) for d, n in r.per_day.items()]
    # the heatmap's cells as rows of hours, so its weekday-by-hour split is reachable without a mouse
    per_hour = [(f"{h:02d}:00", [*(row[h] for row in r.heat), sum(row[h] for row in r.heat)]) for h in range(24)]
    out = []
    for unit, first, heads, rows in (
        ("day", "Date", ["Commits"], per_day),
        ("hour", "Hour", [*WEEKDAYS, "All"], per_hour),
    ):
        head = "".join(f'<th scope="col" class="n">{h}</th>' for h in heads)
        body = "".join(
            f'<tr><th scope="row" class="n">{x}</th>'
            + "".join(f'<td class="n{"" if n else " z"}">{n}</td>' for n in ns)
            + "</tr>"
            for x, ns in rows
        )
        title = "Commits per day" if unit == "day" else "Commits per hour and weekday"
        out.append(
            f"<details><summary>{title} as a table</summary>"
            f'<div class="scroll" tabindex="0" role="group" aria-label="{title}">'
            f'<table><tr><th scope="col">{first}</th>{head}</tr>{body}</table></div></details>'
        )
    return "".join(out)


def _wrapped(r: Report) -> str:
    """The four lines a year is remembered by."""
    month, n = max(r.columns, key=lambda col: col[1])
    top = r.projects[0]
    share = len(top.commits) / len(r.commits)
    name, why = r.persona
    day, most, _ = r.biggest_days[0]
    rows = [
        ("Busiest month", calendar.month_name[list(calendar.month_abbr).index(month)], plural(n, "commit")),
        ("Top project", top.name, f"{plural(len(top.commits), 'commit')} · {share:.0%} of the year"),
        ("Biggest day", f"{day.day} {day:%B}", f"{plural(most, 'commit')} on a {day:%A}"),
        ("Your rhythm", name, why),
    ]
    items = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}<small>{esc(d)}</small></dd></div>" for k, v, d in rows)
    return f'<dl class="wrapped">{items}</dl>'


def _card(width: str, title: str, note: str, body: str) -> str:
    return f'<section class="card {width}"><h2>{esc(title)}</h2><p class="note">{esc(note)}</p>{body}</section>'


def _empty(r: Report) -> str:
    """Nothing to chart: say what was searched and what to try next."""
    kind = r.period.kind
    who = esc(", ".join(r.authors)) if r.authors else "you"
    # --last counts back from today, so a past period (from --date) names the earlier one by date
    current = r.period.start <= r.today <= r.period.end
    earlier = "--last" if current else f"--date {r.period.previous().start.isoformat()}"
    tries = [
        (f"devpulse {kind} {earlier}", f"The {kind} before this one."),
        (f'devpulse {kind} --author "Your Name"', "If you commit under another name or email."),
        (f"devpulse {kind} --depth 5", "If your repos sit more than three folders below the path you gave."),
    ]
    rows = "".join(f"<dt><code>{esc(cmd)}</code></dt><dd>{esc(why)}</dd>" for cmd, why in tries)
    return (
        '<section class="card empty"><h2>No commits in this period</h2>'
        f"<p>devpulse read {plural(r.repos_scanned, 'repo')} and found no commits by {who} "
        f"in this {kind} ({esc(r.period.span)}).</p><dl>{rows}</dl></section>"
    )


def render(r: Report, generated: date) -> str:
    kind, title = r.period.kind, r.period.title
    heading = f"Your {title} in code" if kind == "year" else title
    # "Commits" is the big figure; the year's recap lines have their own card
    rest = [t for t in tiles(r) if t[0] not in ("Commits", "Biggest day", "Busiest month", "Your rhythm")]
    # the first four, then the ones that carry a second line, then the rest: every grid row is one height
    ordered = rest[:4] + [t for t in rest[4:] if t[2]] + [t for t in rest[4:] if not t[2]]
    stats = "".join(
        f"<div><dt>{esc(k)}</dt><dd>{esc(v)}{f' <small>{esc(detail)}</small>' if detail else ''}</dd></div>"
        for k, v, detail in ordered
    )
    hero = (
        f'<section class="hero"><div class="figure">{len(r.commits):,}<small>{"commit" if len(r.commits) == 1 else "commits"}'
        f' in {plural(len(r.projects), "project")}</small></div><dl class="tiles">{stats}</dl></section>'
    )
    cards = []
    if r.narrative or r.improve:
        text = "".join(f"<p>{esc(p)}</p>" for p in r.narrative.split("\n\n") if p.strip())
        if r.improve:
            text += f'<p class="next"><strong>One thing for next {kind}:</strong> {esc(r.improve)}</p>'
        cards.append(
            f'<section class="card ai"><h2>Summary</h2><p class="note">Written by Claude from the numbers and commit subjects in this report.</p>{text}</section>'
        )
    if not r.commits:
        hero = ""
        cards.append(_empty(r))
        if any(n for _, n in r.trend):
            cards.append(
                _card("", f"{kind.capitalize()} over {kind}", f"Commits in the last {len(r.trend)} {kind}s.", _trend(r))
            )
    else:
        if kind == "year":
            cards.append(f'<section class="card">{_wrapped(r)}</section>')
            cards.append(
                _card(
                    "",
                    f"{title}, day by day",
                    "One square per day, one column per week."
                    + (" Outlined squares are days still to come." if r.in_progress else ""),
                    _calendar(r),
                )
            )
        days_note = f"{r.active_days} of {len(r.per_day)} days had at least one commit."
        cards += [
            _card("w7", "When you commit", "Commits by weekday and hour, in each commit's own time zone.", _heat(r)),
            # a quarter's 90-odd days are too many bars; its calendar fits the same card
            _card("w5", "Commits per day", f"{days_note} One square per day, one column per week.", _calendar(r))
            if kind == "quarter"
            else _card("w5", "Commits per month" if kind == "year" else "Commits per day", days_note, _activity(r)),
            _card(
                "w6",
                "Projects",
                "Commits per repository.",
                _bars([(p.name, len(p.commits), "") for p in r.projects], "projects"),
            ),
        ]
        total = sum(n for _, n in r.languages) or 1
        langs = [(lang, n, f"{n:,} lines · {n / total:.0%}") for lang, n in r.languages]
        cards.append(
            _card(
                "w6",
                "Languages",
                "Added plus deleted lines by file type. Lock files and vendored folders are left out.",
                _bars(langs, "languages") if langs else '<p class="sub">No text changes.</p>',
            )
        )
        big = "".join(
            f"<li><b>{fmt_day(d)}</b><span>{plural(n, 'commit')} · {plural(lines, 'line')}</span></li>"
            for d, n, lines in r.biggest_days
        )
        cards += [
            _card(
                "w6",
                f"{kind.capitalize()} over {kind}",
                f"Commits in the last {len(r.trend)} {kind}s."
                + (" The current one is still in progress." if r.in_progress else ""),
                _trend(r),
            ),
            _card("w6", "Biggest days", "Ranked by commits, then by changed lines.", f'<ol class="big">{big}</ol>'),
            _card(
                "",
                "Longest focus sessions",
                f"First to last commit of a run with no gap over {SESSION_GAP_MIN} minutes. The length adds {SESSION_LEAD_MIN} minutes for the work before the first commit: an estimate, not a time sheet.",
                _sessions(r),
            ),
            _card("", "What shipped", "Commit subjects per project, newest first.", _shipped(r) + _tables(r)),
        ]
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light dark">'
        f'<meta name="robots" content="noindex"><title>devpulse · {esc(title)}</title><style>{CSS}</style></head>\n'
        f'<body><main><header><p class="eyebrow"><b>devpulse</b>{kind}ly review</p><h1>{esc(heading)}</h1>'
        f'<p class="sub">{esc(r.period.span)}{" · in progress" if r.in_progress else ""}</p></header>\n'
        f'{hero}<div class="grid">{"".join(cards)}</div>\n'
        f"<footer>Generated on {generated.isoformat()} by devpulse {__version__} from local git history in "
        f"{plural(r.repos_scanned, 'repo')}. This file makes no network requests.</footer></main>\n"
        f'<div id="tip" role="tooltip" hidden></div><script>{JS}</script></body></html>\n'
    )
