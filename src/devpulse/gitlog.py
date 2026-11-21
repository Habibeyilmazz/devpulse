"""Find git repositories under a folder and read commits from them.

Read-only: the only git commands run are `git log`, `git rev-parse` and `git config --get`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

SKIP_DIRS = {"node_modules", "venv", "__pycache__", "vendor", "target", "dist", "build"}

# Generated or vendored files would drown real work in the line counts.
IGNORED_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock",
    "Pipfile.lock", "Cargo.lock", "go.sum", "composer.lock", "Gemfile.lock",
}  # fmt: skip
IGNORED_SUFFIXES = (".min.js", ".min.css", ".map", ".lock")
IGNORED_PARTS = {"node_modules", "vendor", "dist", "build", "__pycache__"}


@dataclass(frozen=True)
class Commit:
    repo: str
    sha: str
    when: datetime  # aware, in the author's own UTC offset at commit time
    subject: str
    files: tuple[tuple[str, int, int], ...]  # (path, added, deleted)

    @property
    def added(self) -> int:
        return sum(f[1] for f in self.files)

    @property
    def deleted(self) -> int:
        return sum(f[2] for f in self.files)

    @property
    def day(self) -> date:
        return self.when.date()


def is_ignored(path: str) -> bool:
    parts = path.split("/")
    return parts[-1] in IGNORED_NAMES or path.endswith(IGNORED_SUFFIXES) or not IGNORED_PARTS.isdisjoint(parts[:-1])


def find_repos(root: Path, depth: int = 3) -> list[Path]:
    """Return every git work tree at most `depth` folders below `root` (root itself is level 0)."""
    root = Path(root).expanduser().resolve()
    repos: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):  # does not follow symlinks
        # `.git` is a file in linked work trees and submodules
        if ".git" in dirnames or ".git" in filenames:
            repos.append(Path(dirpath))
            dirnames[:] = []
            continue
        if len(Path(dirpath).relative_to(root).parts) >= depth:
            dirnames[:] = []
        else:
            dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS)
    return repos


def repo_names(root: Path, repos: list[Path]) -> dict[Path, str]:
    """Folder name, or the path relative to `root` when two repos share a folder name."""
    root = Path(root).expanduser().resolve()
    counts: dict[str, int] = {}
    for r in repos:
        counts[r.name] = counts.get(r.name, 0) + 1
    return {r: r.name if counts[r.name] == 1 or r == root else r.relative_to(root).as_posix() for r in repos}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "core.quotepath=off", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "LC_ALL": "C"},
        check=False,
    )


def configured_author(repo: Path) -> str | None:
    """The email (or else name) git would commit with in this repo."""
    for key in ("user.email", "user.name"):
        value = _git(repo, "config", "--get", key).stdout.strip()
        if value:
            return value
    return None


def read_commits(repo: Path, name: str, authors: list[str], since: date) -> list[Commit]:
    """Non-merge commits on local branches by `authors`, authored on or after `since`.

    `authors` are matched as case-insensitive substrings of "Name <email>".
    """
    if _git(repo, "rev-parse", "--quiet", "--verify", "HEAD").returncode != 0:
        return []  # a repo without commits
    proc = _git(
        repo, "log", "--branches", "HEAD", "--no-merges", "--no-renames",
        # never run helper programs that a repo's own config could name (diff drivers, gpg)
        "--no-ext-diff", "--no-textconv", "--no-show-signature", "--numstat", "-F", "-i",
        *(f"--author={a}" for a in authors),
        # --since tests the committer date, which is never earlier than the author date we
        # filter on below; two days of slack covers time zones.
        f"--since={since - timedelta(days=2)}T00:00:00",
        "--format=%x1e%H%x1f%aI%x1f%s",
    )  # fmt: skip
    if proc.returncode != 0:
        print(f"devpulse: skipping {repo}: {proc.stderr.strip()[:200]}", file=sys.stderr)
        return []
    commits: dict[tuple[datetime, str], Commit] = {}
    for record in proc.stdout.split("\x1e")[1:]:
        head, _, body = record.partition("\n")
        fields = head.split("\x1f", 2)
        if len(fields) != 3:
            continue
        sha, when_text, subject = fields
        # git writes UTC as "Z", which fromisoformat only accepts from Python 3.11
        when = datetime.fromisoformat(when_text.replace("Z", "+00:00"))
        if when.date() < since:
            continue
        files = []
        for line in body.splitlines():
            parts = line.split("\t", 2)
            if len(parts) == 3 and not is_ignored(parts[2]):
                added, deleted, path = parts
                # binary files report "-" for both counts
                files.append((path, int(added) if added.isdigit() else 0, int(deleted) if deleted.isdigit() else 0))
        # A cherry-pick or rebase keeps author date and subject: count the work once.
        commits.setdefault((when, subject), Commit(name, sha, when, subject, tuple(files)))
    return list(commits.values())
