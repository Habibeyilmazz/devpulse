"""Shared fixtures. Every repository the tests read is synthetic and lives in a temp folder."""

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from devpulse.gitlog import Commit

ADA = ("Ada Example", "ada@example.com")
BOB = ("Bob Sample", "bob@example.com")


@pytest.fixture(autouse=True)
def isolated_git(monkeypatch, tmp_path):
    """Keep git and devpulse away from the real user and system config, and make sure no API key leaks in."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # what Path.home() reads on Windows
    monkeypatch.setenv("COLUMNS", "200")
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "DEVPULSE_MODEL", "DEVPULSE_CONFIG", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(var, raising=False)


def git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env={**os.environ, **(env or {})})


def make_repo(path: Path, commits=(), identity=ADA) -> Path:
    """Create a repo. `commits` are (iso datetime, subject, {file: content}[, (name, email)])."""
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    if identity:
        git(path, "config", "user.name", identity[0])
        git(path, "config", "user.email", identity[1])
    for when, subject, files, *who in commits:
        commit(path, when, subject, files, who[0] if who else identity or ADA)
    return path


def commit(repo: Path, when: str, subject: str, files: dict, who=ADA) -> None:
    for name, content in files.items():
        file = repo / name
        file.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            file.write_bytes(content)
        else:
            file.write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    env = {
        "GIT_AUTHOR_NAME": who[0], "GIT_AUTHOR_EMAIL": who[1], "GIT_AUTHOR_DATE": when,
        "GIT_COMMITTER_NAME": who[0], "GIT_COMMITTER_EMAIL": who[1], "GIT_COMMITTER_DATE": when,
    }  # fmt: skip
    git(repo, "commit", "-q", "--allow-empty", "--allow-empty-message", "-m", subject, env=env)


def lines(n: int) -> str:
    return "".join(f"line {i}\n" for i in range(n))


def c(when: str, repo="api", subject="work", files=(("app.py", 10, 2),), offset_hours=0) -> Commit:
    """An in-memory commit for the stats tests; `when` is 'YYYY-MM-DD HH:MM'."""
    tz = timezone(timedelta(hours=offset_hours))
    return Commit(
        repo, f"sha-{when}-{repo}-{subject}", datetime.fromisoformat(when).replace(tzinfo=tz), subject, tuple(files)
    )
