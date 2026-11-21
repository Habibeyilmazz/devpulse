#!/usr/bin/env python3
"""Create synthetic git repositories to try devpulse on, without touching real ones.

    python scripts/demo_repos.py /tmp/devpulse-demo
    devpulse week /tmp/devpulse-demo --open

The history is invented (a fictional "Ada Example") and deterministic for a given end date.
It is written with `git fast-import`, so a year of commits takes about a second.
"""

from __future__ import annotations

import argparse
import os
import random
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

NAME, EMAIL = "Ada Example", "ada@example.com"
TZ = timezone(timedelta(hours=1))
REPOS = {  # name: (weight, files, things worked on)
    "ledger-api": (5, ["app/invoices.py", "app/accounts.py", "app/export.py", "tests/test_invoices.py", "README.md"],
                   ["invoice totals", "account import", "CSV export", "webhook retries", "currency rounding"]),
    "ledger-web": (4, ["src/App.tsx", "src/InvoiceTable.tsx", "src/theme.css", "src/api.ts"],
                   ["invoice table", "dark theme", "date picker", "empty states", "keyboard shortcuts"]),
    "notes-cli": (2, ["main.go", "store/store.go", "store/store_test.go"],
                  ["search", "tag filter", "sync command", "config file"]),
    "infra": (1, ["deploy/main.tf", "ci/build.yaml", "scripts/backup.sh"],
              ["staging deploy", "backup job", "CI cache"]),
}  # fmt: skip
VERBS = ["Add", "Fix", "Refactor", "Test", "Speed up", "Simplify", "Document", "Polish"]
START_HOURS = [8, 9, 9, 10, 10, 10, 11, 13, 14, 14, 15, 16, 17, 20, 21, 22, 23]


def history(end: date, days: int, rng: random.Random):
    """Yield (repo, datetime, subject) for an invented working rhythm."""
    for offset in range(days, -1, -1):
        day = end - timedelta(days=offset)
        vacation = day.month == 8 and 3 <= day.day <= 16
        if vacation or rng.random() > (0.9 if day.weekday() < 5 else 0.3):
            continue
        for _ in range(rng.choice([1, 2, 2, 3, 3])):
            repo = rng.choices(list(REPOS), weights=[w for w, _, _ in REPOS.values()])[0]
            when = datetime(day.year, day.month, day.day, rng.choice(START_HOURS), rng.randrange(60), tzinfo=TZ)
            for _ in range(rng.choice([1, 2, 2, 3, 4, 6])):
                if when.date() != day:
                    break
                yield repo, when, f"{rng.choice(VERBS)} {rng.choice(REPOS[repo][2])}"
                when += timedelta(minutes=rng.randrange(8, 55))


def write_repo(path: Path, files: list[str], commits: list[tuple[datetime, str]], rng: random.Random) -> None:
    path.mkdir(parents=True)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True, env=env)
    for key, value in (("user.name", NAME), ("user.email", EMAIL)):
        subprocess.run(["git", "-C", str(path), "config", key, value], check=True, env=env)
    content: dict[str, list[str]] = {}
    stream = []
    for n, (when, subject) in enumerate(commits):
        who = f"{NAME} <{EMAIL}> {int(when.timestamp())} +0100"
        message = subject.encode()
        stream.append(
            f"commit refs/heads/main\nauthor {who}\ncommitter {who}\ndata {len(message)}\n".encode() + message + b"\n"
        )
        for file in rng.sample(files, k=rng.randint(1, min(3, len(files)))):
            body = content.setdefault(file, [])
            del body[: rng.randint(0, min(len(body), 12))]
            body += [f"{file} change {n} line {i}" for i in range(rng.randint(2, 60))]
            data = ("\n".join(body) + "\n").encode()
            stream.append(f"M 100644 inline {file}\ndata {len(data)}\n".encode() + data + b"\n")
    subprocess.run(["git", "-C", str(path), "fast-import", "--quiet"], input=b"".join(stream), check=True, env=env)
    subprocess.run(["git", "-C", str(path), "reset", "-q", "--hard", "main"], check=True, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="folder to create; must not exist yet")
    parser.add_argument("--until", type=date.fromisoformat, default=date.today(), metavar="YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=500, help="days of history (default: 500)")
    args = parser.parse_args()
    if args.folder.exists():
        parser.error(f"{args.folder} already exists")
    rng = random.Random(f"devpulse {args.until}")
    per_repo: dict[str, list[tuple[datetime, str]]] = {name: [] for name in REPOS}
    for repo, when, subject in history(args.until, args.days, rng):
        per_repo[repo].append((when, subject))
    for name, commits in per_repo.items():
        write_repo(args.folder / name, REPOS[name][1], commits, rng)
        print(f"{name}: {len(commits)} commits")
    print(f'\nNow run: devpulse week "{args.folder}" --open')


if __name__ == "__main__":
    main()
