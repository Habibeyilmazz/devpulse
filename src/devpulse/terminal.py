"""Print a report or a standup to the terminal with rich."""

from __future__ import annotations

from datetime import date

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from devpulse.gitlog import Commit
from devpulse.stats import Report, facts, fmt_day

BLOCKS = "·▁▂▃▄▅▆▇█"  # a dot keeps an empty hour or day in its place on the axis


def spark(values: list[int]) -> str:
    top = max(values, default=0)
    return "".join(BLOCKS[0 if not v else max(1, round(v / top * 8))] for v in values)


def print_report(r: Report, console: Console) -> None:
    p = r.period
    console.print(f"\n[bold]devpulse[/bold] · {p.kind}ly review · [bold]{p.title}[/bold] [dim]({p.span})[/dim]\n")
    if not r.commits:
        who = f" by {escape(', '.join(r.authors))}" if r.authors else ""
        repos = "1 repo" if r.repos_scanned == 1 else f"{r.repos_scanned} repos"
        console.print(f"No commits{who} found in {repos} for this period.", highlight=False)
        console.print("[dim]If that is wrong, pass --author with the name or email you commit with.[/dim]\n")
        return

    grid = Table.grid(padding=(0, 3))
    pairs = facts(r)
    # two columns need about 100 characters; a default 80-column terminal gets one
    half = (len(pairs) + 1) // 2 if console.width >= 100 else len(pairs)
    for i in range(half):
        row = [f"[dim]{pairs[i][0]}[/dim]", f"[bold]{pairs[i][1]}[/bold]"]
        if i + half < len(pairs):
            row += [f"[dim]{pairs[i + half][0]}[/dim]", f"[bold]{pairs[i + half][1]}[/bold]"]
        grid.add_row(*row)
    console.print(grid)

    by_hour = [sum(row[h] for row in r.heat) for h in range(24)]
    console.print(f"\n[dim]Hours 00–23[/dim]  [blue]{spark(by_hour)}[/blue]")
    console.print(
        f"[dim]{'Per month  ' if p.kind == 'year' else 'Per day    '}[/dim]  [blue]{spark([n for _, n in r.columns])}[/blue]\n"
    )

    table = Table(box=None, pad_edge=False, header_style="dim")
    table.add_column("Project")
    table.add_column("Commits", justify="right")
    table.add_column("Lines", justify="right")
    table.add_column("Latest")
    for proj in r.projects:
        table.add_row(
            escape(proj.name),
            str(len(proj.commits)),
            f"+{proj.added:,} / −{proj.deleted:,}",
            escape(proj.commits[-1].subject),
        )
    console.print(table)

    if r.languages:
        total = sum(n for _, n in r.languages)
        top = ", ".join(f"{lang} {n / total:.0%}" for lang, n in r.languages[:5])
        console.print(f"\n[dim]Languages by changed lines[/dim]  {escape(top)}")
    if r.narrative:
        console.print(f"\n[bold]Summary[/bold]\n{escape(r.narrative)}")
    if r.improve:
        console.print(f"\n[bold]One thing for next {p.kind}[/bold]\n{escape(r.improve)}")
    console.print()


def print_standup(today: date, previous: list[Commit], current: list[Commit], console: Console) -> None:
    """`previous` holds the commits of the last active day before `today`."""
    if previous:
        day = previous[0].day
        label = "Yesterday" if (today - day).days == 1 else "Last active day"
        _bullets(f"{label} ({fmt_day(day)})", previous, console)
    else:
        console.print("[bold]Yesterday[/bold]\n  [dim]No commits in the last 7 days.[/dim]")
    console.print()
    if current:
        _bullets(f"Today ({fmt_day(today)})", current, console)
    else:
        console.print("[bold]Today[/bold]\n  [dim]No commits yet.[/dim]")


def _bullets(title: str, commits: list[Commit], console: Console) -> None:
    console.print(f"[bold]{title}[/bold]")
    by_repo: dict[str, list[str]] = {}
    for c in sorted(commits, key=lambda c: c.when):
        subjects = by_repo.setdefault(c.repo, [])
        if c.subject not in subjects:
            subjects.append(c.subject)
    for repo, subjects in by_repo.items():
        for s in subjects:
            # soft_wrap: a pasted bullet must stay one line however narrow the terminal is
            console.print(f"  - [cyan]{escape(repo)}[/cyan]: {escape(s)}", highlight=False, soft_wrap=True)
