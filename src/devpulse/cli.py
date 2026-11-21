"""Command line entry point: devpulse week | month | year | standup."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import webbrowser
from datetime import date, timedelta
from pathlib import Path

from rich.console import Console

from devpulse import __version__, ai, config, dashboard, export, note
from devpulse.gitlog import Commit, configured_author, enclosing_repo, find_repos, read_commits, repo_names
from devpulse.stats import build_report, period_for, window_start
from devpulse.terminal import print_report, print_standup


class UsageError(Exception):
    pass


def collect(
    root: Path, authors: list[str], depth: int, since: date, exclude: list[str] = ()
) -> tuple[list[Commit], int, list[str]]:
    """Commits since `since` from every repo under `root`, the number of repos read, and the identities matched."""
    root = root.expanduser()  # cmd.exe and PowerShell pass ~ through, and so does a quoted "~/code"
    if not root.is_dir():
        raise UsageError(f"not a folder: {root}")
    repos = find_repos(root, depth, exclude)
    if not repos and (inside := enclosing_repo(root)):
        repos = [inside]  # PATH is a subfolder of a single repo
    if not repos:
        hint = "--depth, --exclude" if exclude else "--depth"
        raise UsageError(f"no git repositories found within {depth} levels of {root} (see {hint})")
    names = repo_names(root, repos)
    commits: dict[str, Commit] = {}
    unknown, broken = [], []
    matched: dict[str, None] = {}  # an ordered set
    for repo in repos:
        who = authors or [a for a in [configured_author(repo)] if a]
        matched.update(dict.fromkeys(who))
        if who:
            for c in read_commits(repo, names[repo], who, since):
                commits.setdefault(c.sha, c)  # a linked work tree or second clone lists the same commits again
        elif enclosing_repo(repo):
            unknown.append(names[repo])
        else:  # a .git that points nowhere, e.g. the leftover of a removed work tree
            broken.append(names[repo])
    if broken:
        print(f"devpulse: not a readable git repository: {', '.join(broken)} (skipped)", file=sys.stderr)
    if len(broken) == len(repos):
        raise UsageError(f"no readable git repositories found within {depth} levels of {root}")
    if len(unknown) + len(broken) == len(repos):
        raise UsageError("git has no user.email or user.name configured; pass --author NAME_OR_EMAIL")
    if unknown:
        print(f"devpulse: no git identity configured in: {', '.join(unknown)} (skipped)", file=sys.stderr)
    return list(commits.values()), len(repos) - len(unknown) - len(broken), list(matched)


def target(path: Path, stem: str, suffix: str) -> Path:
    """`path` is the file itself when it ends in `suffix`, otherwise a folder to put `stem` in."""
    path = path.expanduser()
    file = path if path.suffix.lower() == suffix else path / f"{stem}{suffix}"
    file.parent.mkdir(parents=True, exist_ok=True)
    return file


def run_review(args: argparse.Namespace, console: Console) -> int:
    today = date.today()
    period = period_for(args.command, args.date or today)
    if args.last:
        period = period.previous()
    commits, n_repos, authors = collect(args.path, args.author, args.depth, window_start(period), args.exclude)
    report = build_report(commits, period, today, n_repos)
    report.authors = authors

    if args.ai and report.commits:
        try:
            report.narrative, report.improve = ai.narrate(report)
        except ai.AIUnavailable as e:
            print(f"devpulse: no AI summary: {e}", file=sys.stderr)

    # Write the files before printing: `devpulse week --html out | head` closes the pipe mid-report.
    stem, written = f"devpulse-{period.label}", []
    if args.md:
        file = target(args.md, stem, ".md")
        file.write_text(note.render(report), encoding="utf-8")
        written.append(("Markdown note ", file))
    if args.open and not args.html:
        args.html = Path(tempfile.mkdtemp(prefix="devpulse-"))
    if args.html:
        file = target(args.html, stem, ".html")
        file.write_text(dashboard.render(report, date.today()), encoding="utf-8")
        written.append(("HTML dashboard", file))
        if args.open:
            webbrowser.open(file.resolve().as_uri())
    if args.json:
        data = export.render(report, today)
        if str(args.json) == "-":  # JSON on stdout instead of the report, for a pipe into jq
            sys.stdout.write(data)
            return 0
        file = target(args.json, stem, ".json")
        file.write_text(data, encoding="utf-8")
        written.append(("JSON data     ", file))
    print_report(report, console)
    for label, file in written:
        console.print(f"{label} {file}", highlight=False, soft_wrap=True)
    return 0


def run_standup(args: argparse.Namespace, console: Console) -> int:
    today = args.date or date.today()
    commits, _, _ = collect(args.path, args.author, args.depth, today - timedelta(days=7), args.exclude)
    earlier = [c for c in commits if c.day < today]
    last_day = max((c.day for c in earlier), default=None)
    print_standup(
        today,
        [c for c in earlier if c.day == last_day],
        [c for c in commits if c.day == today],
        console,
    )
    return 0


def day(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a date; write it as YYYY-MM-DD") from None


def author(text: str) -> str:
    if not text.strip():
        raise argparse.ArgumentTypeError("needs a name or email, not empty text")
    return text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devpulse",
        description="Your personal engineering review, generated from local git history. Nothing is uploaded.",
        epilog=f"Defaults for PATH, --author, --exclude, --depth, --md, --html and --json can be set in {config.config_path()}",
    )
    parser.add_argument("--version", action="version", version=f"devpulse {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "path", nargs="?", type=Path, help="folder that contains your repos (default: `path` from the config, else .)"
    )
    common.add_argument(
        "--author", action="append", default=[], type=author, metavar="NAME_OR_EMAIL",
        help="count commits whose author contains this text; repeatable (default: each repo's git user.email)",
    )  # fmt: skip
    common.add_argument(
        "--exclude", action="append", default=[], metavar="GLOB",
        help="skip folders whose name or path below PATH matches this glob, e.g. 'forks/*'; repeatable",
    )  # fmt: skip
    common.add_argument(
        "--date",
        type=day,
        metavar="YYYY-MM-DD",
        help="report on the week, month, year or standup day that contains this day (default: today)",
    )
    common.add_argument("--depth", type=int, help="how many folder levels below PATH to search for repos (default: 3)")

    sub = parser.add_subparsers(dest="command", required=True, metavar="{week,month,year,standup}")
    helps = {
        "week": "this ISO week, Monday to Sunday",
        "month": "this calendar month",
        "year": "this calendar year, as a wrapped-style recap",
    }
    for kind, text in helps.items():
        p = sub.add_parser(kind, parents=[common], help=text, description=f"Review {text}.")
        p.add_argument("--last", action="store_true", help=f"report on the previous {kind} instead")
        p.add_argument(
            "--md",
            type=Path,
            metavar="PATH",
            help="write the Markdown note to this .md file or folder (e.g. your Obsidian vault)",
        )
        p.add_argument(
            "--html", type=Path, metavar="PATH", help="write the HTML dashboard to this .html file or folder"
        )
        p.add_argument(
            "--json",
            type=Path,
            metavar="PATH",
            help="write the numbers and commits as JSON to this .json file or folder; - prints it instead of the report",
        )
        p.add_argument(
            "--open",
            action="store_true",
            help="open the dashboard in your browser (written to a temp folder unless --html is given)",
        )
        p.add_argument(
            "--ai",
            action="store_true",
            help="add a narrative by Claude; sends commit subjects and stats to the Anthropic API",
        )
    sub.add_parser(
        "standup",
        parents=[common],
        help="what you did yesterday and today, as bullets",
        description="What you committed on your last active day and today.",
    )
    return parser


def apply_config(args: argparse.Namespace, settings: dict) -> None:
    """Fill what the command line left out from the config file. --exclude adds to the config's list."""
    args.path = args.path or settings.get("path", Path("."))
    args.author = args.author or settings.get("authors", [])
    args.exclude = settings.get("exclude", []) + args.exclude
    args.depth = settings.get("depth", 3) if args.depth is None else args.depth
    if args.command != "standup":
        args.md = args.md or settings.get("md")
        args.html = args.html or settings.get("html")
        args.json = args.json or settings.get("json")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        apply_config(args, config.load())
    except config.ConfigError as e:
        print(f"devpulse: config: {e}", file=sys.stderr)
        return 2
    for stream in (sys.stdout, sys.stderr):
        # A pipe on Windows (Git Bash, `> file`) gets the legacy code page, which has no sparkline blocks.
        if hasattr(stream, "reconfigure") and "utf" not in (stream.encoding or "").lower():
            stream.reconfigure(encoding="utf-8")
    console = Console()
    try:
        return run_standup(args, console) if args.command == "standup" else run_review(args, console)
    except UsageError as e:
        print(f"devpulse: {e}", file=sys.stderr)
        return 2
    except OverflowError:
        print("devpulse: --date is out of range", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:  # e.g. `devpulse standup | head -3`
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())  # keep the exit flush quiet
        return 1
    except OSError as e:  # an unwritable --md/--html target, or git missing from PATH
        print(f"devpulse: {e}", file=sys.stderr)
        return 1
