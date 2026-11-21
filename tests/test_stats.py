from datetime import date

import pytest

from conftest import c
from devpulse.stats import (
    build_report,
    facts,
    focus_sessions,
    language_of,
    longest_streak,
    period_for,
    streak_ending,
    window_start,
)

MON = date(2026, 3, 9)  # a Monday, ISO week 11


def d(day: int) -> date:
    return date(2026, 3, day)


def test_week_period_is_monday_to_sunday():
    p = period_for("week", date(2026, 3, 12))
    assert (p.start, p.end, p.label, p.title) == (MON, d(15), "2026-W11", "Week 11, 2026")
    assert p.span == "9 Mar – 15 Mar 2026"
    assert p.previous().label == "2026-W10"
    assert len(p.days) == 7


def test_iso_week_belongs_to_the_year_of_its_thursday():
    p = period_for("week", date(2026, 1, 1))
    assert (p.start, p.label) == (date(2025, 12, 29), "2026-W01")
    assert p.previous().label == "2025-W52"


def test_month_and_year_periods():
    feb = period_for("month", date(2024, 2, 10))
    assert (feb.start, feb.end, feb.label, feb.title) == (
        date(2024, 2, 1),
        date(2024, 2, 29),
        "2024-02",
        "February 2024",
    )
    assert period_for("month", date(2026, 1, 5)).previous().label == "2025-12"
    year = period_for("year", date(2026, 6, 1))
    assert (year.start, year.end, year.label) == (date(2026, 1, 1), date(2026, 12, 31), "2026")
    assert year.previous().label == "2025"
    with pytest.raises(ValueError):
        period_for("decade", MON)


def test_window_start_reaches_back_over_the_trend():
    assert window_start(period_for("week", MON)) == date(2026, 1, 19)  # 7 weeks earlier
    assert window_start(period_for("month", MON)) == date(2025, 10, 1)
    assert window_start(period_for("year", MON)) == date(2024, 1, 1)


def test_language_of():
    assert language_of("src/app.py") == "Python"
    assert language_of("web/App.TSX") == "TypeScript"
    assert language_of("Dockerfile") == "Docker"
    assert language_of("LICENSE") == "Other"
    assert language_of("notes.unknownext") == "Other"


def test_focus_sessions_split_on_long_gaps_and_span_repos():
    commits = [
        c("2026-03-09 09:00"),
        c("2026-03-09 10:30", repo="web"),  # exactly 90 minutes later: same session
        c("2026-03-09 12:01"),  # 91 minutes later: new session
        c("2026-03-10 20:00"),
    ]

    sessions = focus_sessions(commits[::-1])  # input order must not matter

    assert [(s.commits, s.minutes, s.repos) for s in sessions] == [
        (2, 120, ("api", "web")),  # 90 minutes between commits plus 30 assumed before the first
        (1, 30, ("api",)),
        (1, 30, ("api",)),
    ]


def test_sessions_compare_instants_across_time_zones():
    # 09:00 at UTC+3 and 07:30 at UTC+1 are 30 minutes apart
    assert len(focus_sessions([c("2026-03-09 09:00", offset_hours=3), c("2026-03-09 07:30", offset_hours=1)])) == 1


def test_streaks():
    days = {d(1), d(2), d(3), d(5), d(6)}
    assert longest_streak(days) == 3
    assert longest_streak(set()) == 0
    assert streak_ending(days, d(6)) == 2
    assert streak_ending(days, d(7)) == 0


def week_commits():
    return [
        c("2026-03-02 10:00", subject="previous week 1"),
        c("2026-03-03 10:00", subject="previous week 2"),
        c("2026-03-08 21:00", subject="previous sunday"),
        c("2026-03-09 09:15", files=(("app.py", 30, 5), ("README.md", 10, 0))),
        c("2026-03-09 09:45", repo="web", files=(("src/ui.ts", 100, 20),)),
        c("2026-03-09 23:10", files=(("app.py", 1, 1),)),
        c("2026-03-10 02:30", files=()),
        c("2026-03-14 11:00", repo="web", files=(("src/ui.ts", 5, 5),)),
        c("2026-03-16 10:00", subject="next week"),
    ]


def test_build_report_week():
    r = build_report(week_commits(), period_for("week", MON), today=d(20), repos_scanned=2)

    assert len(r.commits) == 5
    assert (r.added, r.deleted) == (146, 31)
    assert r.active_days == 3
    assert [(p.name, len(p.commits)) for p in r.projects] == [("api", 3), ("web", 2)]
    assert r.languages == [("TypeScript", 130), ("Python", 37), ("Markdown", 10)]
    assert r.heat[0][9] == 2 and r.heat[0][23] == 1 and r.heat[1][2] == 1 and r.heat[5][11] == 1
    assert sum(map(sum, r.heat)) == 5
    assert r.columns == [("Mon", 3), ("Tue", 1), ("Wed", 0), ("Thu", 0), ("Fri", 0), ("Sat", 1), ("Sun", 0)]
    assert r.longest_streak == 2
    assert r.biggest_days[0] == (d(9), 3, 167)
    assert r.late_night == pytest.approx(2 / 5)
    assert r.weekend == pytest.approx(1 / 5)
    assert r.peak_hour == 9
    assert [n for _, n in r.trend] == [0, 0, 0, 0, 0, 0, 3, 5]
    assert r.trend[-1][0].label == "2026-W11"
    assert r.delta == pytest.approx(2 / 3)
    assert not r.in_progress
    assert r.persona[0] == "Night owl"
    # sessions: Mon 09:15-09:45, then Mon 23:10 alone (02:30 is 200 minutes later), Tue 02:30, Sat 11:00
    assert [s.minutes for s in r.sessions] == [60, 30, 30, 30]
    assert r.focus_minutes == 150


def test_current_streak_counts_back_from_today_across_the_period_start():
    r = build_report(week_commits(), period_for("week", MON), today=d(10), repos_scanned=2)
    assert r.in_progress
    assert r.current_streak == 3  # Sun 8, Mon 9, Tue 10
    assert not r.streak_capped
    assert dict(facts(r))["vs previous week"] == "+67% (so far)"


def test_a_quiet_day_only_spares_the_streak_while_it_is_today():
    commits = [c("2026-03-13 10:00"), c("2026-03-14 10:00")]  # Friday and Saturday; Sunday is quiet
    period = period_for("week", MON)
    assert build_report(commits, period, today=d(15), repos_scanned=1).current_streak == 2  # Sunday is not over
    assert build_report(commits, period, today=d(16), repos_scanned=1).current_streak == 0  # it ended quiet


def test_streak_is_flagged_when_it_reaches_the_edge_of_the_history_read():
    period = period_for("week", MON)
    first = window_start(period)
    every_day = [c(f"{first.fromordinal(first.toordinal() + i)} 10:00") for i in range((d(15) - first).days + 1)]
    r = build_report(every_day, period, today=d(15), repos_scanned=1)
    assert r.streak_capped
    assert dict(facts(r))["Current streak"] == "56+ days"
    later = build_report(every_day, period, today=d(25), repos_scanned=1)
    assert dict(facts(later))["Streak at period end"] == "56+ days"


def test_month_and_year_columns():
    commits = [c("2026-03-01 10:00"), c("2026-03-31 10:00"), c("2026-03-31 11:00"), c("2026-07-04 10:00")]
    month = build_report(commits, period_for("month", MON), today=d(31), repos_scanned=1)
    assert len(month.columns) == 31
    assert (month.columns[0], month.columns[30]) == (("1", 1), ("31", 2))
    year = build_report(commits, period_for("year", MON), today=date(2026, 12, 31), repos_scanned=1)
    assert year.columns[2] == ("Mar", 3) and year.columns[6] == ("Jul", 1) and len(year.columns) == 12
    assert len(year.per_day) == 365


def test_empty_report_has_safe_defaults():
    r = build_report([], period_for("week", MON), today=MON, repos_scanned=3)
    assert r.commits == [] and r.sessions == [] and r.biggest_days == []
    assert (r.late_night, r.peak_hour, r.delta, r.current_streak) == (0.0, None, None, 0)
    labels = dict(facts(r))
    assert labels["Commits"] == "0" and "Peak hour" not in labels
