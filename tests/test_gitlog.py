import os
from datetime import date

from conftest import ADA, BOB, commit, git, lines, make_repo
from devpulse import gitlog
from devpulse.gitlog import configured_author, find_repos, is_ignored, read_commits, repo_names

SINCE = date(2026, 1, 1)


def test_find_repos_prunes_and_limits_depth(tmp_path):
    for rel in ["a/.git", "group/b/.git", "group/b/sub/.git", "x/y/z/w/.git", "node_modules/pkg/.git", ".cache/c/.git"]:
        (tmp_path / rel).mkdir(parents=True)
    (tmp_path / "worktree").mkdir()
    (tmp_path / "worktree" / ".git").write_text("gitdir: elsewhere\n")

    found = [p.relative_to(tmp_path.resolve()).as_posix() for p in find_repos(tmp_path, depth=3)]

    assert found == ["a", "group/b", "group/b/sub", "worktree"]  # nested repos count too
    assert [p.name for p in find_repos(tmp_path, depth=4)] == ["a", "b", "sub", "worktree", "w"]


def test_find_repos_excludes_by_name_or_path(tmp_path):
    for rel in ["a/.git", "forks/b/.git", "forks/b/sub/.git", "work/client-x/.git", "work/api/.git"]:
        (tmp_path / rel).mkdir(parents=True)

    def found(*patterns):
        return [p.relative_to(tmp_path.resolve()).as_posix() for p in find_repos(tmp_path, exclude=list(patterns))]

    assert found("forks") == ["a", "work/api", "work/client-x"]  # a folder takes everything below it
    assert found("forks/*", "client-*") == ["a", "work/api"]  # a path glob, and a name glob at any level
    assert found("work/api/") == ["a", "forks/b", "forks/b/sub", "work/client-x"]
    assert found("Forks") == found()  # case-sensitive on every platform


def test_find_repos_accepts_a_repo_as_root(tmp_path):
    (tmp_path / ".git").mkdir()
    assert find_repos(tmp_path) == [tmp_path.resolve()]


def test_repo_names_disambiguate_duplicates(tmp_path):
    root = tmp_path.resolve()
    repos = [root / "work" / "api", root / "home" / "api", root / "web"]
    assert list(repo_names(tmp_path, repos).values()) == ["work/api", "home/api", "web"]


def test_is_ignored():
    assert is_ignored("package-lock.json")
    assert is_ignored("web/yarn.lock")
    assert is_ignored("static/app.min.js")
    assert is_ignored("vendor/lib/thing.go")
    assert not is_ignored("src/build_tools.py")
    assert not is_ignored("docs/vendor.md")


def test_read_commits_filters_author_and_counts_lines(tmp_path):
    repo = make_repo(
        tmp_path / "api",
        [
            ("2026-03-09T10:00:00+01:00", "Add app", {"app.py": lines(10), "package-lock.json": lines(500)}),
            ("2026-03-09T11:00:00+01:00", "Bob's change", {"bob.py": lines(99)}, BOB),
            (
                "2026-03-10T23:30:00-05:00",
                "[wip] trim app & add logo",
                {"app.py": lines(4), "logo.png": b"\x00\x01\x02\xff"},
            ),
        ],
    )

    commits = sorted(read_commits(repo, "api", ["ada@example.com"], SINCE), key=lambda c: c.when)

    assert [c.subject for c in commits] == ["Add app", "[wip] trim app & add logo"]
    assert commits[0].files == (("app.py", 10, 0),)  # the lock file is left out
    assert (commits[1].added, commits[1].deleted) == (0, 6)
    assert ("logo.png", 0, 0) in commits[1].files  # binary: no line counts
    # hour and day are the author's local ones, whatever time zone the report runs in
    assert (commits[1].when.hour, commits[1].day) == (23, date(2026, 3, 10))
    assert commits[0].repo == "api" and len(commits[0].sha) == 40


def test_author_match_is_a_case_insensitive_fixed_substring(tmp_path):
    plus = ("Ada Example", "1234+ada.x@users.noreply.example.com")
    repo = make_repo(
        tmp_path / "r",
        [
            ("2026-03-09T10:00:00+00:00", "one", {"a.txt": "1\n"}, plus),
            ("2026-03-09T11:00:00+00:00", "two", {"a.txt": "2\n"}, ("Adax", "1234+adaXx@users.noreply.example.com")),
        ],
    )
    assert [c.subject for c in read_commits(repo, "r", ["1234+ADA.x@users"], SINCE)] == ["one"]
    assert len(read_commits(repo, "r", ["ada example", "adax"], SINCE)) == 2
    assert read_commits(repo, "r", ["nobody"], SINCE) == []


def test_since_cuts_off_older_commits(tmp_path):
    repo = make_repo(
        tmp_path / "r",
        [
            ("2025-12-31T23:59:00+00:00", "old", {"a.txt": "1\n"}),
            ("2026-01-01T00:01:00+00:00", "new", {"a.txt": "2\n"}),
        ],
    )
    assert [c.subject for c in read_commits(repo, "r", [ADA[1]], SINCE)] == ["new"]


def test_side_branches_count_but_cherry_picks_count_once(tmp_path):
    repo = make_repo(tmp_path / "r", [("2026-03-09T10:00:00+00:00", "base", {"a.txt": "1\n"})])
    git(repo, "checkout", "-q", "-b", "feature")
    commit(repo, "2026-03-09T11:00:00+00:00", "feature work", {"f.txt": "1\n"})
    git(repo, "checkout", "-q", "main")
    git(repo, "cherry-pick", "feature", env={"GIT_COMMITTER_NAME": ADA[0], "GIT_COMMITTER_EMAIL": ADA[1]})
    commit(repo, "2026-03-09T12:00:00+00:00", "main work", {"m.txt": "1\n"})

    subjects = sorted(c.subject for c in read_commits(repo, "r", [ADA[1]], SINCE))

    assert subjects == ["base", "feature work", "main work"]

    # same second and subject but a different change: two commits, not one
    for name in ("x.txt", "y.txt"):
        commit(repo, "2026-03-09T13:00:00+00:00", "Update", {name: "1\n"})
    assert sum(c.subject == "Update" for c in read_commits(repo, "r", [ADA[1]], SINCE)) == 2


def test_merge_commits_are_skipped(tmp_path):
    repo = make_repo(tmp_path / "r", [("2026-03-09T10:00:00+00:00", "base", {"a.txt": "1\n"})])
    git(repo, "checkout", "-q", "-b", "side")
    commit(repo, "2026-03-09T11:00:00+00:00", "side", {"s.txt": "1\n"})
    git(repo, "checkout", "-q", "main")
    commit(repo, "2026-03-09T12:00:00+00:00", "main", {"m.txt": "1\n"})
    env = {
        "GIT_COMMITTER_NAME": ADA[0],
        "GIT_COMMITTER_EMAIL": ADA[1],
        "GIT_AUTHOR_NAME": ADA[0],
        "GIT_AUTHOR_EMAIL": ADA[1],
    }
    git(repo, "merge", "-q", "--no-ff", "-m", "Merge side", "side", env=env)

    assert sorted(c.subject for c in read_commits(repo, "r", [ADA[1]], SINCE)) == ["base", "main", "side"]


def test_empty_repo_and_unicode_paths(tmp_path, capsys):
    empty = make_repo(tmp_path / "empty")
    assert read_commits(empty, "empty", [ADA[1]], SINCE) == []
    assert capsys.readouterr().err == ""

    # git would quote and escape this path without -z; Windows does not allow such a file name at all
    odd = 'ta\tb "quoted".py' if os.name != "nt" else "spa ce.py"
    files = {"docs/café notes.md": lines(3), f"src/{odd}": lines(2), f"vendor/{odd}": lines(9)}
    repo = make_repo(tmp_path / "r", [("2026-03-09T10:00:00+00:00", "Añade café ☕", files)])
    commit(repo, "2026-03-09T11:00:00+00:00", "nothing changed", {})
    first, second = sorted(read_commits(repo, "r", [ADA[1]], SINCE), key=lambda c: c.when)
    assert first.subject == "Añade café ☕"
    assert first.files == (("docs/café notes.md", 3, 0), (f"src/{odd}", 2, 0))
    assert (second.subject, second.files) == ("nothing changed", ())


def test_separator_bytes_in_a_subject_do_not_crash_the_parser(tmp_path):
    repo = make_repo(
        tmp_path / "r",
        [
            ("2026-03-09T10:00:00+00:00", "odd \x1eaaaa\x1fnot-a-date\x1fboom", {"a.txt": "1\n"}),
            ("2026-03-09T11:00:00+00:00", "fine", {"a.txt": "2\n"}),
        ],
    )
    assert "fine" in [c.subject for c in read_commits(repo, "r", [ADA[1]], SINCE)]


def test_orphan_branch_does_not_hide_the_other_branches(tmp_path):
    repo = make_repo(tmp_path / "r", [("2026-03-09T10:00:00+00:00", "on main", {"a.txt": "1\n"})])
    git(repo, "switch", "-q", "--orphan", "scratch")
    assert [c.subject for c in read_commits(repo, "r", [ADA[1]], SINCE)] == ["on main"]


def test_git_is_run_without_lazy_fetch_or_prompts(tmp_path, monkeypatch):
    seen = {}
    real_run = gitlog.subprocess.run
    monkeypatch.setattr(gitlog.subprocess, "run", lambda *a, **kw: seen.update(kw["env"]) or real_run(*a, **kw))
    read_commits(make_repo(tmp_path / "r"), "r", [ADA[1]], SINCE)
    assert (seen["GIT_NO_LAZY_FETCH"], seen["GIT_ALLOW_PROTOCOL"], seen["GIT_TERMINAL_PROMPT"]) == ("1", "", "0")


def test_configured_author(tmp_path):
    assert configured_author(make_repo(tmp_path / "a")) == ADA[1]
    assert configured_author(make_repo(tmp_path / "b", identity=None)) is None


def test_a_moved_file_counts_only_the_lines_edited_in_it(tmp_path):
    repo = make_repo(tmp_path / "r", [("2026-03-09T10:00:00+00:00", "Add", {"old/app.py": lines(200), "b.txt": "1\n"})])
    git(repo, "mv", "old", "new")
    commit(repo, "2026-03-09T11:00:00+00:00", "Move", {"new/app.py": lines(200) + "one more\n", "b.txt": "2\n"})

    move = max(read_commits(repo, "r", [ADA[1]], SINCE), key=lambda c: c.when)

    assert sorted(move.files) == [("b.txt", 1, 1), ("new/app.py", 1, 0)]


def test_an_empty_or_enormous_subject_is_readable_in_every_output(tmp_path):
    repo = make_repo(
        tmp_path / "r",
        [
            ("2026-03-09T09:00:00+00:00", "", {"a.py": lines(1)}),
            ("2026-03-09T10:00:00+00:00", "x" * 50_000, {"b.py": lines(1)}),
        ],
    )

    subjects = {c.subject for c in read_commits(repo, "r", [ADA[1]], SINCE)}

    assert "(no message)" in subjects
    assert max(map(len, subjects)) <= gitlog.MAX_SUBJECT
    assert any(s.endswith("…") for s in subjects)
