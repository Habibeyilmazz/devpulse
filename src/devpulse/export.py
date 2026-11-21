"""Render a report as JSON, for scripts, jq and other tools. Numbers are raw, not formatted."""

from __future__ import annotations

import json
from datetime import date

from devpulse import __version__
from devpulse.dashboard import WEEKDAYS
from devpulse.stats import LATE_FROM, LATE_UNTIL, SESSION_GAP_MIN, SESSION_LEAD_MIN, Period, Report

SCHEMA = 1  # bump when a key is renamed or removed; adding keys keeps it


def _period(p: Period) -> dict:
    return {"kind": p.kind, "label": p.label, "start": p.start.isoformat(), "end": p.end.isoformat()}


def render(r: Report, generated: date) -> str:
    data = {
        "schema": SCHEMA,
        "generator": f"devpulse {__version__}",
        "generated": generated.isoformat(),
        "period": {**_period(r.period), "title": r.period.title, "in_progress": r.in_progress},
        "authors": r.authors,
        "repos_scanned": r.repos_scanned,
        "totals": {
            "commits": len(r.commits),
            "active_days": r.active_days,
            "days": len(r.per_day),
            "lines_added": r.added,
            "lines_deleted": r.deleted,
            "projects": len(r.projects),
            "change_vs_previous": None if r.delta is None else round(r.delta, 4),
            "longest_streak_days": r.longest_streak,
            "current_streak_days": r.current_streak,
            "current_streak_capped": r.streak_capped,  # the streak reaches back past the history read
            "focus_minutes": r.focus_minutes,
            "sessions": len(r.sessions),
            "peak_hour": r.peak_hour,
            "late_night_share": round(r.late_night, 4),
            "weekend_share": round(r.weekend, 4),
        },
        "settings": {
            "session_gap_minutes": SESSION_GAP_MIN,
            "session_lead_minutes": SESSION_LEAD_MIN,
            "late_night_hours": [LATE_FROM, LATE_UNTIL],
        },
        "projects": [
            {"name": p.name, "commits": len(p.commits), "lines_added": p.added, "lines_deleted": p.deleted}
            for p in r.projects
        ],
        "languages": [{"name": name, "lines_changed": n} for name, n in r.languages],
        "per_day": {d.isoformat(): n for d, n in r.per_day.items()},
        # commits by weekday and hour, in each commit's own time zone
        "heatmap": dict(zip(WEEKDAYS, r.heat, strict=True)),
        "trend": [{**_period(p), "commits": n} for p, n in r.trend],
        "biggest_days": [
            {"date": d.isoformat(), "commits": n, "lines_changed": lines} for d, n, lines in r.biggest_days
        ],
        "sessions": [
            {
                "start": s.start.isoformat(),
                "end": s.end.isoformat(),
                "minutes": s.minutes,
                "commits": s.commits,
                "projects": list(s.repos),
            }
            for s in r.sessions
        ],
        "commits": [
            {
                "project": c.repo,
                "sha": c.sha,
                "authored": c.when.isoformat(),
                "subject": c.subject,
                "lines_added": c.added,
                "lines_deleted": c.deleted,
            }
            for c in r.commits
        ],
        "summary": {"narrative": r.narrative, "improve": r.improve} if r.narrative or r.improve else None,
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
