# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

Changes from a first-run review: a fresh clone, the README followed to the letter (pipx, uvx, the
demo, the development setup), and a read of the whole codebase.

### Fixed

- `--ai` without credentials ended in a traceback instead of the report. The SDK signals missing
  credentials with a `TypeError`, which was not caught.
- A `~` in `PATH` that the shell did not expand (cmd.exe, PowerShell, a quoted argument) was
  reported as "not a folder".
- Output piped through a legacy code page (Git Bash or `> file` on Windows) crashed on the
  sparkline characters. Such a pipe now gets UTF-8.
- Moving or renaming a file counted every line in it as deleted and added again, which inflated
  "Lines changed" and the language shares. Renames are now detected (`git log -M`).
- The demo script's "Now run" hint did not quote a folder with spaces.
- Ctrl-C printed a traceback.

### Changed

- The headline numbers are listed in one column when the terminal is narrower than 100 columns
  (two columns wrapped nearly every value at the default 80).
- "No commits found" names the identity that was searched, for example
  `No commits by ada@example.com found in 4 repo(s)`.

### Added

- CI runs the tests and a piped smoke run on Windows (Python 3.12, Git Bash).

## [0.1.0] - 2026-11-21

First release.

### Added

- `devpulse week`, `month` and `year`: review of the ISO week, calendar month or calendar year,
  printed to the terminal with rich.
- `--md`: Markdown note with YAML frontmatter, per-project commit bullets, project wikilinks and a
  link to the previous period's note.
- `--html` and `--open`: self-contained HTML dashboard (no network requests, light and dark theme,
  phone layout) with weekday-by-hour heatmap, commits per day or month, projects, languages by
  changed lines, trend against previous periods, biggest days and longest focus sessions. The
  `year` dashboard adds a recap card and a day-by-day calendar.
- `devpulse standup`: bullets for the last active day and today.
- `--author`, `--date`, `--last`, `--depth`.
- Commits are counted once across cherry-picks, linked work trees and second clones. A `PATH`
  inside a repo reports on that repo.
- git is run read-only with diff drivers, text converters, signature checks, prompts and lazy
  fetching switched off.
- `--ai`: optional narrative and "one thing for next week" from the Anthropic API. Opt-in per run;
  needs the `anthropic` package (`devpulse[ai]`) and credentials.
- `scripts/demo_repos.py`: generates synthetic repositories to try the tool on.
- CI: ruff, pytest on Python 3.10, 3.12 and 3.13, and a wheel build that is installed and run.

### Notes for the next contributor

- Layout: `gitlog.py` (find repos, parse `git log`), `stats.py` (periods and every number),
  `terminal.py`, `note.py`, `dashboard.py` (the three outputs), `ai.py` (the only network code),
  `cli.py` (argparse wiring). All headline numbers come from `stats.tiles()`.
- Tests must only read repositories they create (`tests/conftest.py` isolates git config and HOME).
- The `--ai` path is tested with a fake client, with the real SDK without credentials, and (by hand)
  with the real SDK against a local stub of `/v1/messages`. It has still not been run against the
  live API: no key was available. `--ai` is deliberately opt-in per run; a key in the environment
  alone never triggers an upload.
- Known limits: history is bounded with `git log --since` (commit date, see README "How it works");
  a commit subject containing the byte 0x1E is cut at that byte; a `.git` file that points nowhere
  (a stale work tree) is reported as "no git identity configured" rather than as broken.
- Windows is covered by CI only (tests plus a piped run); nobody has used it there interactively.
- The config file and exclude patterns are still roadmap items, not built.
- The dashboard charts are plain HTML and CSS. Colours are a single-hue sequential ramp; text never
  carries the data colour.

[Unreleased]: https://github.com/Habibeyilmazz/devpulse/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Habibeyilmazz/devpulse/releases/tag/v0.1.0
