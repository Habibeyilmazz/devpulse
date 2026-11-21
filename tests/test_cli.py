"""End-to-end runs of the CLI against synthetic repositories."""

import os
import subprocess
import sys

import pytest

from conftest import ADA, BOB, commit, git, lines, make_repo
from devpulse import ai, cli


def workspace(tmp_path):
    root = tmp_path / "code"
    make_repo(
        root / "api",
        [
            ("2026-03-06T16:00:00+01:00", "Add health endpoint", {"app.py": lines(20)}),
            ("2026-03-09T09:15:00+01:00", "Add pagination", {"app.py": lines(60), "README.md": lines(5)}),
            ("2026-03-09T09:50:00+01:00", "Fix off-by-one in pagination", {"app.py": lines(58)}),
            ("2026-03-09T10:00:00+01:00", "Bob's refactor", {"bob.py": lines(300)}, BOB),
            ("2026-03-10T08:05:00+01:00", "Tidy README", {"README.md": lines(9)}),
        ],
    )
    make_repo(root / "clients" / "web", [("2026-03-09T23:40:00+01:00", "Dark mode <toggle>", {"src/ui.ts": lines(40)})])
    make_repo(root / "empty")
    return root


def test_week_writes_note_and_dashboard(tmp_path, capsys):
    root, out = workspace(tmp_path), tmp_path / "out"

    code = cli.main(
        ["week", str(root), "--date", "2026-03-10", "--md", str(out / "vault"), "--html", str(out / "report.html")]
    )

    assert code == 0
    printed = capsys.readouterr()
    assert printed.err == ""
    assert "Week 11, 2026" in printed.out and "Tidy README" in printed.out
    md = (out / "vault" / "devpulse-2026-W11.md").read_text(encoding="utf-8")
    assert "commits: 4" in md and "### [[api]]" in md and "### [[web]]" in md
    assert "Bob's refactor" not in md and "Add health endpoint" not in md
    html = (out / "report.html").read_text(encoding="utf-8")
    assert "Dark mode &lt;toggle&gt;" in html and "Bob" not in html
    assert "TypeScript" in html and "in progress" not in html  # --date picks the week; it is long over


def test_last_month_year_and_explicit_author(tmp_path, capsys):
    root = workspace(tmp_path)

    assert cli.main(["week", str(root), "--date", "2026-03-10", "--last"]) == 0
    out = capsys.readouterr().out
    assert "Week 10, 2026" in out and "Add health endpoint" in out and "Add pagination" not in out

    assert cli.main(["month", str(root), "--date", "2026-03-31", "--author", "bob@example.com"]) == 0
    out = capsys.readouterr().out
    assert "March 2026" in out and "Bob's refactor" in out and "Add pagination" not in out

    assert cli.main(["year", str(root), "--date", "2026-12-31", "--html", str(tmp_path)]) == 0
    assert "Your 2026 in code" in (tmp_path / "devpulse-2026.html").read_text(encoding="utf-8")


def test_standup(tmp_path, capsys):
    root = workspace(tmp_path)

    assert cli.main(["standup", str(root), "--date", "2026-03-10"]) == 0
    out = capsys.readouterr().out
    assert "Yesterday (Mon 9 Mar)" in out and "web: Dark mode <toggle>" in out
    assert "Today (Tue 10 Mar)" in out and "api: Tidy README" in out
    assert "Bob" not in out and "health" not in out

    assert cli.main(["standup", str(root), "--date", "2026-03-09"]) == 0
    out = capsys.readouterr().out
    assert "Last active day (Fri 6 Mar)" in out and "Add health endpoint" in out


def test_linked_work_trees_and_second_clones_do_not_double_count(tmp_path, capsys):
    root = workspace(tmp_path)
    git(root / "api", "worktree", "add", "-q", "-b", "feature", str(root / "api-feature"))
    git(root, "clone", "-q", str(root / "api"), str(root / "api-copy"))
    git(root / "api-copy", "config", "user.email", ADA[1])

    assert cli.main(["week", str(root), "--date", "2026-03-10", "--md", str(tmp_path / "n.md")]) == 0
    text = (tmp_path / "n.md").read_text(encoding="utf-8")
    assert "commits: 4" in text and 'projects: ["api", "web"]' in text


def test_path_inside_a_repo_reports_on_that_repo(tmp_path, capsys):
    root = workspace(tmp_path)
    (root / "api" / "docs").mkdir()

    assert cli.main(["standup", str(root / "api" / "docs"), "--date", "2026-03-10"]) == 0
    assert "api: Tidy README" in capsys.readouterr().out


def test_tilde_in_path_is_expanded_even_when_the_shell_did_not(tmp_path, capsys, monkeypatch):
    workspace(tmp_path)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows; conftest already points HOME here

    assert cli.main(["standup", "~/code", "--date", "2026-03-10"]) == 0
    assert "api: Tidy README" in capsys.readouterr().out


def test_no_commits_names_the_identity_that_was_searched(tmp_path, capsys):
    root = workspace(tmp_path)

    assert cli.main(["week", str(root), "--date", "2025-06-01"]) == 0
    assert "No commits by ada@example.com found in 3 repos" in capsys.readouterr().out
    assert cli.main(["week", str(root), "--date", "2025-06-01", "--author", "Zed", "--author", "zed@example.com"]) == 0
    assert "No commits by Zed, zed@example.com found" in capsys.readouterr().out


def test_output_survives_a_pipe_with_a_legacy_code_page(tmp_path):
    """Git Bash and `> file` on Windows hand Python a cp1252 pipe, which cannot encode the sparklines."""
    root = workspace(tmp_path)

    done = subprocess.run(
        [sys.executable, "-m", "devpulse", "week", str(root), "--date", "2026-03-10"],
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
    )

    assert done.returncode == 0, done.stderr.decode(errors="replace")
    assert "+40 / −0" in done.stdout.decode("utf-8") and "█" in done.stdout.decode("utf-8")


def test_usage_errors(tmp_path, capsys):
    (tmp_path / "plain").mkdir()
    assert cli.main(["week", str(tmp_path / "plain")]) == 2
    assert "no git repositories found" in capsys.readouterr().err
    assert cli.main(["week", str(tmp_path / "missing")]) == 2
    assert "not a folder" in capsys.readouterr().err
    assert cli.main(["week", str(workspace(tmp_path / "w")), "--date", "0001-01-01"]) == 2
    assert "out of range" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        cli.main(["week", "--date", "10/03/2026"])
    assert "'10/03/2026' is not a date; write it as YYYY-MM-DD" in capsys.readouterr().err
    with pytest.raises(SystemExit):  # an empty author text matches every commit, which is never what was meant
        cli.main(["week", "--author", " "])
    assert "--author" in capsys.readouterr().err
    (tmp_path / "file.txt").write_text("not a folder")
    assert cli.main(["week", str(workspace(tmp_path)), "--md", str(tmp_path / "file.txt" / "notes")]) == 1
    assert "file.txt" in capsys.readouterr().err
    make_repo(tmp_path / "anon" / "r", identity=None)
    assert cli.main(["week", str(tmp_path / "anon")]) == 2
    assert "pass --author" in capsys.readouterr().err


def test_ai_is_off_by_default_and_failures_do_not_break_the_report(tmp_path, capsys, monkeypatch):
    root = workspace(tmp_path)
    calls = []

    def narrate(report):
        calls.append(report)
        raise ai.AIUnavailable("could not reach the API")

    monkeypatch.setattr(ai, "narrate", narrate)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")

    assert cli.main(["week", str(root), "--date", "2026-03-10"]) == 0
    assert calls == []  # a key in the environment is not consent to upload

    assert cli.main(["week", str(root), "--date", "2026-03-10", "--ai"]) == 0
    printed = capsys.readouterr()
    assert len(calls) == 1 and "no AI summary: could not reach the API" in printed.err
    assert "Week 11, 2026" in printed.out

    monkeypatch.setattr(ai, "narrate", lambda report: ("Solid week.", "Sleep more."))
    assert cli.main(["week", str(root), "--date", "2026-03-10", "--ai", "--md", str(tmp_path / "n.md")]) == 0
    text = (tmp_path / "n.md").read_text(encoding="utf-8")
    assert "Solid week." in text and "- [ ] Sleep more." in text


def test_stale_git_pointer_is_named_as_broken_not_as_a_missing_identity(tmp_path, capsys):
    root = workspace(tmp_path)
    (root / "gone").mkdir()
    (root / "gone" / ".git").write_text("gitdir: /nowhere/worktrees/gone\n", encoding="utf-8")

    assert cli.main(["week", str(root), "--date", "2026-03-10"]) == 0
    printed = capsys.readouterr()
    assert "not a readable git repository: gone" in printed.err and "identity" not in printed.err
    assert "Tidy README" in printed.out

    only = tmp_path / "only"
    (only / "gone").mkdir(parents=True)
    (only / "gone" / ".git").write_text("gitdir: /nowhere/worktrees/gone\n", encoding="utf-8")
    assert cli.main(["week", str(only)]) == 2
    err = capsys.readouterr().err
    assert "no readable git repositories" in err and "identity" not in err


def test_files_are_written_even_when_the_terminal_pipe_closes(tmp_path):
    """`devpulse week --html out | head -3`: the reader goes away before the report is printed."""
    out = tmp_path / "out"
    cmd = [sys.executable, "-m", "devpulse", "week", str(workspace(tmp_path)), "--date", "2026-03-10"]
    proc = subprocess.Popen(
        [*cmd, "--md", str(out), "--html", str(out)], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    proc.stdout.close()
    proc.wait(timeout=60)
    proc.stderr.close()
    assert (out / "devpulse-2026-W11.md").exists() and (out / "devpulse-2026-W11.html").exists()


def test_escape_sequences_in_subjects_and_folder_names_never_reach_the_terminal(tmp_path, capsys):
    # A commit subject is text anyone can write: OSC 0 retitles the terminal, CSI 2J clears it,
    # OSC 8 fakes a link, OSC 52 writes the clipboard, U+202E reorders what is shown.
    evil = "Fix \x1b]0;pwned\x07 \x1b[2J \x1b]8;;https://example.invalid\x1b\\link\x1b]8;;\x1b\\ \x1b]52;c;cm0gLXJm\x07 ‮ok \x9b31m"
    root = tmp_path / "code"
    make_repo(root / "api", [("2026-03-09T09:15:00+01:00", evil, {"app.py": lines(3)})])
    folder = "web" if os.name == "nt" else "web\x1b[31m"  # Windows cannot create such a folder
    make_repo(root / folder, [("2026-03-09T10:15:00+01:00", "Plain", {"a.py": lines(3)})])

    for argv in (
        ["week", str(root), "--date", "2026-03-10", "--md", str(tmp_path / "o")],
        ["standup", str(root), "--date", "2026-03-10"],
    ):
        assert cli.main(argv) == 0
        out = capsys.readouterr().out
        assert "Fix" in out and "Plain" in out
        assert not any(ch in out for ch in "\x1b\x07\x9b‮"), repr(out)
    md = (tmp_path / "o" / "devpulse-2026-W11.md").read_text(encoding="utf-8")
    assert "\x1b" not in md and "‮" not in md


@pytest.mark.skipif(os.name == "nt", reason="the hostile commands are POSIX shell")
def test_a_hostile_repo_config_runs_nothing(tmp_path, capsys, monkeypatch):
    """A repo copied from someone else carries its own .git/config; reading it must not run its commands."""
    marker = tmp_path / "ran"
    run = f"touch '{marker.as_posix()}'"
    src = make_repo(tmp_path / "src", [("2026-03-09T09:15:00+01:00", "Add", {"app.py": lines(20)})])
    commit(src, "2026-03-09T10:15:00+01:00", "Edit", {"app.py": lines(25), ".gitattributes": "*.py diff=evil\n"})
    git(src, "config", "uploadpack.allowFilter", "true")
    root = tmp_path / "code"
    root.mkdir()
    # a partial clone fetches missing blobs on demand, through whatever upload-pack command its config names
    git(root, "clone", "-q", "--filter=blob:none", "--no-checkout", src.resolve().as_uri(), "repo")
    repo = root / "repo"
    for key, value in {
        "remote.origin.uploadpack": f"{run}; git-upload-pack",
        "protocol.file.allow": "always",
        "protocol.allow": "always",
        "diff.external": run,
        "diff.evil.textconv": run,
        "diff.evil.command": run,
        "log.showSignature": "true",
        "gpg.program": run,
        "core.fsmonitor": run,
        "core.pager": run,
        "core.hooksPath": str(tmp_path),
        "user.email": ADA[1],
    }.items():
        git(repo, "config", key, value)
    # Prove the transport guard alone holds, as on git older than 2.44 that ignores GIT_NO_LAZY_FETCH.
    real_run = subprocess.run

    def without_lazy_fetch_switch(cmd, **kw):
        kw["env"] = {k: v for k, v in kw["env"].items() if k != "GIT_NO_LAZY_FETCH"}
        return real_run(cmd, **kw)

    monkeypatch.setattr(subprocess, "run", without_lazy_fetch_switch)

    for argv in (["week", str(root), "--date", "2026-03-10"], ["standup", str(root), "--date", "2026-03-10"]):
        cli.main(argv)
    capsys.readouterr()
    assert not marker.exists()
