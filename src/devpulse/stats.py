"""Turn a list of commits into the numbers the three reports show."""

from __future__ import annotations

import calendar
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from devpulse.gitlog import Commit

SESSION_GAP_MIN = 90  # a longer silence between commits starts a new focus session
SESSION_LEAD_MIN = 30  # assumed work before the first commit of a session
LATE_FROM, LATE_UNTIL = 22, 5  # late night is 22:00-04:59 in the commit's own time zone
TREND_PERIODS = {"week": 8, "month": 6, "year": 3}

LANGUAGES = {
    "py": "Python", "pyi": "Python", "ipynb": "Jupyter", "js": "JavaScript", "mjs": "JavaScript",
    "cjs": "JavaScript", "jsx": "JavaScript", "ts": "TypeScript", "tsx": "TypeScript",
    "go": "Go", "rs": "Rust", "java": "Java", "kt": "Kotlin", "kts": "Kotlin", "swift": "Swift",
    "c": "C", "h": "C", "cc": "C++", "cpp": "C++", "hpp": "C++", "cs": "C#", "rb": "Ruby",
    "php": "PHP", "scala": "Scala", "dart": "Dart", "ex": "Elixir", "exs": "Elixir",
    "hs": "Haskell", "lua": "Lua", "r": "R", "jl": "Julia", "zig": "Zig", "sh": "Shell",
    "bash": "Shell", "zsh": "Shell", "fish": "Shell", "ps1": "PowerShell", "sql": "SQL",
    "html": "HTML", "htm": "HTML", "css": "CSS", "scss": "CSS", "sass": "CSS", "less": "CSS",
    "vue": "Vue", "svelte": "Svelte", "astro": "Astro", "md": "Markdown", "mdx": "Markdown",
    "rst": "reStructuredText", "tex": "TeX", "json": "JSON", "yaml": "YAML", "yml": "YAML",
    "toml": "TOML", "xml": "XML", "tf": "Terraform", "proto": "Protobuf", "graphql": "GraphQL",
}  # fmt: skip
FILENAMES = {"Dockerfile": "Docker", "Makefile": "Make"}


def language_of(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    if name in FILENAMES:
        return FILENAMES[name]
    return LANGUAGES.get(name.rsplit(".", 1)[-1].lower(), "Other") if "." in name else "Other"


@dataclass(frozen=True)
class Period:
    kind: str  # "week" | "month" | "year"
    start: date
    end: date  # inclusive

    @property
    def label(self) -> str:
        """Sortable id, also the report file name: 2026-W47, 2026-11, 2026."""
        if self.kind == "week":
            iso = self.start.isocalendar()
            return f"{iso[0]}-W{iso[1]:02d}"
        return f"{self.start:%Y-%m}" if self.kind == "month" else f"{self.start:%Y}"

    @property
    def title(self) -> str:
        if self.kind == "week":
            iso = self.start.isocalendar()
            return f"Week {iso[1]}, {iso[0]}"
        return f"{self.start:%B %Y}" if self.kind == "month" else f"{self.start:%Y}"

    @property
    def span(self) -> str:
        return f"{self.start.day} {self.start:%b} – {self.end.day} {self.end:%b %Y}"

    @property
    def days(self) -> list[date]:
        return [self.start + timedelta(days=i) for i in range((self.end - self.start).days + 1)]

    def previous(self) -> Period:
        return period_for(self.kind, self.start - timedelta(days=1))


def period_for(kind: str, day: date) -> Period:
    """The ISO week (Mon-Sun), calendar month or calendar year that contains `day`."""
    if kind == "week":
        start = day - timedelta(days=day.weekday())
        return Period(kind, start, start + timedelta(days=6))
    if kind == "month":
        return Period(kind, day.replace(day=1), day.replace(day=calendar.monthrange(day.year, day.month)[1]))
    if kind == "year":
        return Period(kind, date(day.year, 1, 1), date(day.year, 12, 31))
    raise ValueError(f"unknown period: {kind}")


def window_start(period: Period) -> date:
    """First day of history a report on `period` needs (trend columns and current streak)."""
    for _ in range(TREND_PERIODS[period.kind] - 1):
        period = period.previous()
    return period.start


@dataclass(frozen=True)
class Session:
    start: datetime
    end: datetime
    commits: int
    repos: tuple[str, ...]

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60) + SESSION_LEAD_MIN


def focus_sessions(commits: list[Commit]) -> list[Session]:
    """Group commits (any repo) into sessions: runs with no gap longer than SESSION_GAP_MIN."""
    sessions: list[Session] = []
    run: list[Commit] = []
    for c in sorted(commits, key=lambda c: c.when):
        if run and c.when - run[-1].when > timedelta(minutes=SESSION_GAP_MIN):
            sessions.append(_session(run))
            run = []
        run.append(c)
    if run:
        sessions.append(_session(run))
    return sessions


def _session(run: list[Commit]) -> Session:
    return Session(run[0].when, run[-1].when, len(run), tuple(sorted({c.repo for c in run})))


def longest_streak(days: set[date]) -> int:
    best = 0
    for d in days:
        if d - timedelta(days=1) not in days:  # d starts a run
            n = 1
            while d + timedelta(days=n) in days:
                n += 1
            best = max(best, n)
    return best


def streak_ending(days: set[date], end: date) -> int:
    """Consecutive active days up to and including `end`."""
    n = 0
    while end - timedelta(days=n) in days:
        n += 1
    return n


@dataclass
class Project:
    name: str
    commits: list[Commit]

    @property
    def added(self) -> int:
        return sum(c.added for c in self.commits)

    @property
    def deleted(self) -> int:
        return sum(c.deleted for c in self.commits)


@dataclass
class Report:
    period: Period
    today: date
    repos_scanned: int
    commits: list[Commit]  # inside the period, oldest first
    projects: list[Project]  # most commits first
    languages: list[tuple[str, int]]  # (language, changed lines), most first
    heat: list[list[int]]  # commits by [weekday 0=Mon][hour]
    per_day: dict[date, int]  # every day of the period, zeros included
    columns: list[tuple[str, int]]  # commits per day, or per month for a year
    longest_streak: int
    current_streak: int
    streak_capped: bool  # the current streak reaches the start of the history we read
    sessions: list[Session]
    biggest_days: list[tuple[date, int, int]]  # (day, commits, changed lines), top three
    trend: list[tuple[Period, int]]  # oldest first, this period last
    narrative: str = ""  # optional AI text
    improve: str = ""
    authors: list[str] = field(default_factory=list)  # the identities commits were matched against
    added: int = field(init=False)
    deleted: int = field(init=False)

    def __post_init__(self) -> None:
        self.added = sum(c.added for c in self.commits)
        self.deleted = sum(c.deleted for c in self.commits)

    @property
    def active_days(self) -> int:
        return sum(1 for n in self.per_day.values() if n)

    @property
    def in_progress(self) -> bool:
        return self.today < self.period.end

    @property
    def focus_minutes(self) -> int:
        return sum(s.minutes for s in self.sessions)

    def share(self, test) -> float:
        return sum(1 for c in self.commits if test(c.when)) / len(self.commits) if self.commits else 0.0

    @property
    def late_night(self) -> float:
        return self.share(lambda w: w.hour >= LATE_FROM or w.hour < LATE_UNTIL)

    @property
    def weekend(self) -> float:
        return self.share(lambda w: w.weekday() >= 5)

    @property
    def peak_hour(self) -> int | None:
        by_hour = [sum(row[h] for row in self.heat) for h in range(24)]
        return by_hour.index(max(by_hour)) if self.commits else None

    @property
    def delta(self) -> float | None:
        """Change in commits against the previous period, as a fraction; None without a baseline."""
        if len(self.trend) < 2 or not self.trend[-2][1]:
            return None
        return (self.trend[-1][1] - self.trend[-2][1]) / self.trend[-2][1]

    @property
    def persona(self) -> tuple[str, str]:
        """A light-hearted label for when the commits happen."""
        early = self.share(lambda w: LATE_UNTIL <= w.hour < 9)
        if self.late_night >= 0.3:
            return "Night owl", f"{self.late_night:.0%} of commits landed between 22:00 and 05:00"
        if early >= 0.3:
            return "Early bird", f"{early:.0%} of commits landed before 09:00"
        if self.weekend >= 0.4:
            return "Weekend warrior", f"{self.weekend:.0%} of commits landed on a weekend"
        return "Daylight shipper", "most commits landed in ordinary working hours"


def build_report(commits: list[Commit], period: Period, today: date, repos_scanned: int) -> Report:
    """`commits` should reach back to `window_start(period)`; anything outside is ignored."""
    inside = sorted((c for c in commits if period.start <= c.day <= period.end), key=lambda c: c.when)

    by_repo: dict[str, list[Commit]] = {}
    for c in inside:
        by_repo.setdefault(c.repo, []).append(c)
    projects = sorted((Project(n, cs) for n, cs in by_repo.items()), key=lambda p: (-len(p.commits), p.name))

    langs: Counter[str] = Counter()
    heat = [[0] * 24 for _ in range(7)]
    per_day = dict.fromkeys(period.days, 0)
    lines_per_day: Counter[date] = Counter()
    for c in inside:
        for path, added, deleted in c.files:
            langs[language_of(path)] += added + deleted
        heat[c.when.weekday()][c.when.hour] += 1
        per_day[c.day] += 1
        lines_per_day[c.day] += c.added + c.deleted

    if period.kind == "year":
        months = Counter(c.day.month for c in inside)
        columns = [(calendar.month_abbr[m], months[m]) for m in range(1, 13)]
    else:
        columns = [(f"{d:%a}" if period.kind == "week" else str(d.day), n) for d, n in per_day.items()]

    first, as_of = window_start(period), min(period.end, today)
    history = {c.day for c in commits if first <= c.day <= as_of}
    # Today is not over: a day without commits so far does not break the streak yet.
    streak_last = as_of - timedelta(days=1) if as_of == today and as_of not in history else as_of
    current = streak_ending(history, streak_last)

    trend, p = [], period
    for _ in range(TREND_PERIODS[period.kind]):
        trend.append((p, sum(1 for c in commits if p.start <= c.day <= p.end)))
        p = p.previous()

    return Report(
        period=period,
        today=today,
        repos_scanned=repos_scanned,
        commits=inside,
        projects=projects,
        languages=[(lang, n) for lang, n in langs.most_common() if n],
        heat=heat,
        per_day=per_day,
        columns=columns,
        longest_streak=longest_streak({d for d, n in per_day.items() if n}),
        current_streak=current,
        streak_capped=current > 0 and streak_last - timedelta(days=current - 1) <= first,
        sessions=focus_sessions(inside),
        biggest_days=sorted(
            ((d, n, lines_per_day[d]) for d, n in per_day.items() if n),
            key=lambda t: (-t[1], -t[2], t[0]),
        )[:3],
        trend=trend[::-1],
    )


def fmt_minutes(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    return f"{hours}h {rest:02d}m" if hours else f"{rest}m"


def fmt_days(n: int, more: bool = False) -> str:
    return f"{n}{'+' if more else ''} {'day' if n == 1 else 'days'}"


def fmt_day(d: date | datetime) -> str:
    return f"{d:%a} {d.day} {d:%b}"


def tiles(r: Report) -> list[tuple[str, str, str]]:
    """The headline numbers as (label, value, detail); every output format starts from these."""
    out = [
        ("Commits", f"{len(r.commits):,}", ""),
        ("Active days", f"{r.active_days} of {len(r.per_day)}", ""),
        ("Lines changed", f"+{r.added:,} / −{r.deleted:,}", ""),
        ("Projects", str(len(r.projects)), ""),
        (
            f"vs previous {r.period.kind}",
            "no baseline" if r.delta is None else f"{r.delta:+.0%}",
            "so far" if r.in_progress else "",
        ),
        ("Longest streak", fmt_days(r.longest_streak), ""),
        (
            "Current streak" if r.today <= r.period.end else "Streak at period end",
            fmt_days(r.current_streak, r.streak_capped),
            "",
        ),
    ]
    if r.commits:
        longest = max(r.sessions, key=lambda s: s.minutes)
        day, n, _ = r.biggest_days[0]
        out += [
            (
                "Focus time (est.)",
                fmt_minutes(r.focus_minutes),
                f"{len(r.sessions)} session{'' if len(r.sessions) == 1 else 's'}",
            ),
            ("Longest session", fmt_minutes(longest.minutes), fmt_day(longest.start)),
            ("Biggest day", fmt_day(day), f"{n} commit{'' if n == 1 else 's'}"),
            ("Peak hour", f"{r.peak_hour:02d}:00", ""),
            ("Late-night commits", f"{r.late_night:.0%}", f"{LATE_FROM}:00–0{LATE_UNTIL}:00"),
            ("Weekend commits", f"{r.weekend:.0%}", ""),
        ]
    if r.languages:
        lang, n = r.languages[0]
        out.append(("Top language", lang, f"{n / sum(v for _, v in r.languages):.0%} of changed lines"))
    if r.commits and r.period.kind == "year":  # the recap lines
        month, n = max(r.columns, key=lambda col: col[1])
        out += [("Busiest month", month, f"{n:,} commits"), ("Your rhythm", *r.persona)]
    return out


def facts(r: Report) -> list[tuple[str, str]]:
    """`tiles` flattened to (label, text) for the plain-text outputs."""
    return [(label, f"{value} ({detail})" if detail else value) for label, value, detail in tiles(r)]
