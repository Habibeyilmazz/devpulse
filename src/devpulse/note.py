"""Render a report as a Markdown note with YAML frontmatter and Obsidian wikilinks."""

from __future__ import annotations

import json
import re

from devpulse.stats import Report, facts

MAX_SUBJECTS = 20


def wikilink(name: str) -> str:
    """[[name]], with the characters Obsidian reserves inside a link replaced."""
    return "[[" + re.sub(r"[\[\]|#^]", "-", name) + "]]"


def inert(text: str) -> str:
    """Commit or AI text with `<`, `[`, `]` and `\\` escaped, so it cannot pull in a remote image (`![](url)`,
    `<img>`), embed a vault file (`![[x]]`), start a wikilink or hide a link behind other words."""
    return re.sub(r"([\\<\[\]])", r"\\\1", text)


def render(r: Report) -> str:
    p = r.period
    frontmatter = {
        "title": f"What I shipped: {p.title}",
        "type": f"{p.kind}ly-review",
        "period": p.label,
        "start": p.start.isoformat(),
        "end": p.end.isoformat(),
        "commits": len(r.commits),
        "active_days": r.active_days,
        "lines_added": r.added,
        "lines_deleted": r.deleted,
        "focus_minutes": r.focus_minutes,
        "projects": [proj.name for proj in r.projects],
        "tags": ["devpulse", f"{p.kind}ly-review"],
    }
    # JSON scalars and flow lists are valid YAML, which keeps odd project names safely quoted.
    out = ["---", *(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in frontmatter.items()), "---", ""]
    out += [f"# What I shipped: {p.title}", "", f"{p.span} · previous: [[devpulse-{p.previous().label}]]", ""]
    if r.narrative:
        out += ["## Summary", "", inert(r.narrative), ""]
    out += ["## Highlights", "", *(f"- **{k}:** {v}" for k, v in facts(r)), ""]
    out += ["## Projects", ""]
    if not r.projects:
        out += ["No commits in this period.", ""]
    for proj in r.projects:
        n = len(proj.commits)
        out += [
            f"### {wikilink(proj.name)}",
            "",
            f"{n} commit{'' if n == 1 else 's'} · +{proj.added:,} / −{proj.deleted:,}",
            "",
        ]
        subjects = list(dict.fromkeys(c.subject for c in reversed(proj.commits)))  # newest first, no repeats
        out += [f"- {inert(s)}" for s in subjects[:MAX_SUBJECTS]]
        if len(subjects) > MAX_SUBJECTS:
            out.append(f"- … and {len(subjects) - MAX_SUBJECTS} more")
        out.append("")
    if r.improve:
        out += [f"## One thing for next {p.kind}", "", f"- [ ] {inert(r.improve)}", ""]
    return "\n".join(out)
