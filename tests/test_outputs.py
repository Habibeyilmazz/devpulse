import io
import re
from datetime import date

from rich.console import Console

from conftest import c
from devpulse import dashboard, note
from devpulse.stats import build_report, facts, period_for
from devpulse.terminal import print_report, print_standup, spark
from test_stats import MON, week_commits

HOSTILE = '<script>alert("x")</script> [bold]not markup[/bold] [[link]]'


def report(kind="week", extra=(), today=date(2026, 3, 20)):
    return build_report([*week_commits(), *extra], period_for(kind, MON), today, repos_scanned=2)


def test_note_has_frontmatter_wikilinks_and_bullets():
    r = report(extra=[c("2026-03-11 10:00", repo="odd|name#1", subject="Fix: the thing")])
    r.narrative, r.improve = "A steady week.", "Commit earlier in the day."

    text = note.render(r)

    front, body = text.split("---\n")[1:3]
    assert 'period: "2026-W11"' in front
    assert "commits: 6" in front and "lines_added: 156" in front
    assert 'projects: ["api", "web", "odd|name#1"]' in front
    assert 'tags: ["devpulse", "weekly-review"]' in front
    assert "previous: [[devpulse-2026-W10]]" in body
    assert "### [[api]]" in body and "### [[odd-name-1]]" in body
    assert "- Fix: the thing" in body
    assert "## Summary\n\nA steady week." in body
    assert "- [ ] Commit earlier in the day." in body


def test_note_lists_each_subject_once_and_caps_long_lists():
    many = [c(f"2026-03-11 {h:02d}:{m:02d}", subject=f"change {h}-{m}") for h in range(8, 12) for m in range(0, 60, 10)]
    text = note.render(report(extra=[*many, c("2026-03-12 10:00"), c("2026-03-12 10:05")]))
    assert text.count("- work\n") == 2  # once under api, once under web
    assert "- … and " in text


def test_dashboard_is_self_contained_and_escapes_everything():
    r = report(extra=[c("2026-03-11 10:00", repo='we"b<b>', subject=HOSTILE)])
    r.narrative, r.improve = HOSTILE, HOSTILE

    page = dashboard.render(r, date(2026, 3, 20))

    assert page.startswith("<!doctype html>")
    assert "<script>alert" not in page and "&lt;script&gt;alert" in page
    assert 'we"b<b>' not in page and "we&quot;b&lt;b&gt;" in page
    # no external resources: nothing is fetched, nothing is uploaded
    assert not re.search(r"""(?:src|href)\s*=|url\(|@import|https?://|fetch\(|XMLHttpRequest""", page)
    assert page.count("<script>") == 1
    assert 'data-tip="Mon 09:00–09:59 · 2 commits"' in page
    assert '<td class="n">09:00</td><td class="n">2</td>' in page  # the heatmap's hours are also a table
    assert "Week 11, 2026" in page and "9 Mar – 15 Mar 2026" in page


def test_dashboard_renders_every_period_kind_and_the_empty_case():
    for kind in ("week", "month", "year"):
        page = dashboard.render(report(kind, today=date(2026, 12, 31)), date(2026, 12, 31))
        assert f"{kind}ly review" in page
        assert page.count('class="cal"') == (2 if kind == "year" else 0)  # the year as two half-year grids
    year = dashboard.render(report("year"), MON)
    assert "Your 2026 in code" in year and "Busiest month" in year and "Your rhythm" in year
    empty = build_report([], period_for("week", MON), MON, repos_scanned=4)
    page = dashboard.render(empty, MON)
    assert "No commits in this period" in page and "4 repos" in page and "in this week (9 Mar – 15 Mar 2026)" in page
    assert "devpulse week --last" in page and 'class="figure"' not in page  # what to try next, and no big zero


def test_dashboard_for_a_quiet_period_still_shows_the_trend_and_the_searched_identity():
    quiet = build_report([c("2026-03-03 10:00")], period_for("week", MON), MON, repos_scanned=1)
    quiet.authors = ["ada@example.com"]
    page = dashboard.render(quiet, MON)
    assert "read 1 repo and found no commits by ada@example.com" in page
    assert "Week over week" in page and "Week 10, 2026 · 1 commit" in page
    assert "When you commit" not in page


def test_heat_levels():
    assert [dashboard.level(n, 10) for n in (0, 1, 2, 3, 5, 9, 10)] == [0, 1, 1, 2, 3, 5, 5]
    assert dashboard.level(1, 1) == 5


def test_terminal_report_prints_hostile_subjects_verbatim():
    out = io.StringIO()
    r = report(extra=[c("2026-03-15 10:00", subject=HOSTILE)])
    r.narrative = "[red]narrative[/red]"

    print_report(r, Console(file=out, width=200))

    text = out.getvalue()
    assert HOSTILE in text and "[red]narrative[/red]" in text
    assert "Week 11, 2026" in text and "Focus time (est.)" in text and "3h 00m (5 sessions)" in text


def test_terminal_report_uses_one_column_in_a_narrow_terminal():
    r = report()
    labels = [label for label, _ in facts(r)]
    for width, most in ((80, 1), (120, 2)):
        out = io.StringIO()
        print_report(r, Console(file=out, width=width))
        text = out.getvalue()
        assert max(sum(label in line for label in labels) for line in text.splitlines()) == most
        assert all(value in text for _, value in facts(r))  # nothing wrapped mid-value


def test_terminal_report_without_commits():
    out = io.StringIO()
    print_report(build_report([], period_for("week", MON), MON, repos_scanned=1), Console(file=out, width=100))
    assert "No commits found" in out.getvalue()


def test_spark():
    assert spark([0, 1, 4, 8]) == "·▁▄█"
    assert spark([]) == "" and spark([0, 0]) == "··"


def test_standup_labels_the_last_active_day():
    out = io.StringIO()
    friday = [c("2026-03-06 10:00", subject="Ship [v2]"), c("2026-03-06 11:00", subject="Ship [v2]")]
    print_standup(MON, friday, [], Console(file=out, width=100))
    text = out.getvalue()
    assert "Last active day (Fri 6 Mar)" in text
    assert text.count("api: Ship [v2]") == 1
    assert "No commits yet." in text
