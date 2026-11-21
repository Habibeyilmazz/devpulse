"""Find git repositories under a folder and read commits from them.

Read-only: the only git commands run are `git log`, `git rev-parse` and `git config --get`,
with lazy fetching and prompts switched off.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from fnmatch import fnmatchcase
from pathlib import Path

SKIP_DIRS = {"node_modules", "venv", "site-packages", "__pycache__"}  # big, and never where you keep repos

# Generated or vendored files would drown real work in the line counts.
IGNORED_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock",
    "Pipfile.lock", "Cargo.lock", "go.sum", "composer.lock", "Gemfile.lock",
}  # fmt: skip
IGNORED_SUFFIXES = (".min.js", ".min.css", ".map", ".lock")
IGNORED_PARTS = {"node_modules", "vendor", "dist", "build", "__pycache__"}

# Terminal control codes (C0 but tab, DEL, C1) and bidi overrides. A commit subject or folder name is
# text anyone can write; printed raw, ESC sequences could retitle the terminal, clear it, fake links
# or write the clipboard (OSC 52), and bidi overrides could reorder what is shown.
_UNPRINTABLE = re.compile("[\x00-\x08\x0a-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")


def printable(text: str) -> str:
    return _UNPRINTABLE.sub("\ufffd", text)


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


def is_excluded(rel: str, patterns: list[str]) -> bool:
    """`rel` is a folder's path below the root, with `/`. A pattern matches the whole path or the folder name."""
    name = rel.rsplit("/", 1)[-1]
    return any(fnmatchcase(rel, p.strip("/")) or fnmatchcase(name, p.strip("/")) for p in patterns)


def find_repos(root: Path, depth: int = 3, exclude: list[str] = ()) -> list[Path]:
    """Return every git work tree at most `depth` folders below `root` (root itself is level 0).

    The walk continues inside a repo, so nested repos and submodules are found too. A folder that
    matches an `exclude` glob is skipped with everything below it.
    """
    root = Path(root).expanduser().resolve()
    repos: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):  # does not follow symlinks
        rel = Path(dirpath).relative_to(root).as_posix()
        if rel != "." and is_excluded(rel, exclude):
            dirnames[:] = []
            continue
        # `.git` is a file in linked work trees and submodules
        if ".git" in dirnames or ".git" in filenames:
            repos.append(Path(dirpath))
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
    return {r: printable(r.name if counts[r.name] == 1 or r == root else r.relative_to(root).as_posix()) for r in repos}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        # A partial clone would otherwise fetch missing blobs for --numstat: network access, and
        # whatever ssh or upload-pack command the repo's config names. GIT_NO_LAZY_FETCH needs git 2.44+;
        # an empty GIT_ALLOW_PROTOCOL blocks every transport on older git too, and unlike
        # `-c protocol.allow=never` a repo's own `protocol.<name>.allow` cannot loosen it.
        env={
            **os.environ,
            "LC_ALL": "C",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_ALLOW_PROTOCOL": "",
            "GIT_TERMINAL_PROMPT": "0",
        },
        check=False,
    )


def enclosing_repo(path: Path) -> Path | None:
    """The work tree that `path` is inside, if any."""
    top = _git(path, "rev-parse", "--show-toplevel")
    return Path(top.stdout.strip()) if top.returncode == 0 and top.stdout.strip() else None


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
    proc = _git(
        # --ignore-missing: HEAD does not resolve in an empty repo or on a fresh orphan branch
        # -M: a moved file counts for the lines edited in it, not as a whole file deleted and added
        repo, "log", "--ignore-missing", "--branches", "HEAD", "--no-merges", "-M",
        # never run helper programs that a repo's own config could name (diff drivers, gpg)
        "--no-ext-diff", "--no-textconv", "--no-show-signature", "--numstat", "-z", "-F", "-i",
        *(f"--author={a}" for a in authors),
        # --since tests the committer date, which is never earlier than the author date we
        # filter on below; two days of slack covers time zones.
        f"--since={since - timedelta(days=2)}T00:00:00",
        "--format=%x1e%H%x1f%aI%x1f%s",
    )  # fmt: skip
    if proc.returncode != 0:
        print(f"devpulse: skipping {repo}: {printable(proc.stderr.strip()[:200])}", file=sys.stderr)
        return []
    commits: dict[tuple, Commit] = {}
    for record in proc.stdout.split("\x1e")[1:]:
        head, _, body = record.partition("\0")  # -z: NUL-terminated fields, paths verbatim
        fields = head.split("\x1f", 2)
        if len(fields) != 3:
            continue
        sha, when_text, subject = fields
        subject = printable(subject)
        try:
            # git writes UTC as "Z", which fromisoformat only accepts from Python 3.11
            when = datetime.fromisoformat(when_text.replace("Z", "+00:00"))
        except ValueError:
            continue  # a subject containing our separator bytes; not a record we wrote the format for
        if when.date() < since:
            continue
        files = []
        entries = iter(body.split("\0"))
        for entry in entries:
            parts = entry.lstrip("\n").split("\t", 2)
            if len(parts) != 3:
                continue
            added, deleted, path = parts
            if not path:  # a rename: -z writes the counts, then the old path and the new one as separate fields
                next(entries, None)
                path = next(entries, "")
            if not is_ignored(path):
                # binary files report "-" for both counts
                files.append((path, int(added) if added.isdigit() else 0, int(deleted) if deleted.isdigit() else 0))
        # A cherry-pick or rebase keeps author date, subject and the change: count the work once.
        commits.setdefault((when, subject, *files), Commit(name, sha, when, subject, tuple(files)))
    return list(commits.values())
