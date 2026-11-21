# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

Changes from two passes. A first-run review: a fresh clone, the README followed to the letter (pipx,
uvx, the demo, the development setup), and a read of the whole codebase. Then a design pass: every
output looked at as rendered (dashboard at 320 to 1440 pixels, light, dark, forced colours and print;
terminal at 80 and 120 columns), with synthetic repos for the awkward cases (one commit, no commits,
eleven projects, a repo name and a commit subject that do not fit).

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
- `devpulse week --html out | head -3` (or quitting a pager early) ended the run before the note and
  the dashboard were written. The files are now written before the report is printed.
- A `.git` file that points nowhere (the leftover of a removed work tree) stopped the whole run with
  "git has no user.email or user.name configured". Such a folder is now skipped and named as "not a
  readable git repository".
- A period with fewer commits than the one before was shown with a hyphen (`-18%`) next to the real
  minus sign of "Lines changed". Both are `−` now.
- "vs previous week" read `no baseline (so far)` in a period that is still running.
- On a phone the heatmap rows were as tall as their labels, not their squares, which left wide gaps
  between rows. The year calendar had the same fault once it stopped scrolling sideways.

### Changed

- The headline numbers are listed in one column when the terminal is narrower than 100 columns
  (two columns wrapped nearly every value at the default 80).
- "No commits found" names the identity that was searched, for example
  `No commits by ada@example.com found in 4 repos`.
- Dashboard layout: the commit count and its tiles sit on the page under a rule instead of inside a
  card, and drop below the number on a tablet instead of squeezing beside it. The year calendar is
  two half-year grids that sit side by side on a wide screen and stack on a phone (it used to be one
  strip that scrolled sideways). Focus sessions are a list that reflows, not a five-column table.
  The recap card shows one, two or four items per row, never three and an orphan.
- Dashboard for a period without commits: says how many repos were read and for whom, lists three
  commands to try (`--last`, `--author`, `--depth`), and shows the trend chart when earlier periods
  have commits. No big zero.
- Dashboard contrast: the grey bars of earlier periods are 3:1 against the card, the first step of
  the dark heatmap ramp can be told from an empty cell, and small grey labels pass 4.5:1 in light mode.
- Dashboard for assistive technology: charts of up to twelve bars read their values out, the heatmap
  names the busiest weekday and hour, commits per hour join commits per day as a table that can be
  focused and scrolled with the keyboard, and the charts keep their colours in Windows high-contrast
  mode and in print.
- Terminal sparklines mark an hour or day without commits with a dot, so the bars keep their place:
  `········▅▆█▆▂·▂▃▂▅▂·▃▂··` instead of blanks.
- A malformed `--date` says `'22.11.2026' is not a date; write it as YYYY-MM-DD` instead of
  argparse's "invalid fromisoformat value".
- README screenshots retaken from the current dashboard, with two phone shots added, and the terminal
  and Markdown samples replaced with current output.

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
  a commit subject containing the byte 0x1E is cut at that byte.
- Windows is covered by CI only (tests plus a piped run); nobody has used it there interactively.
- The config file and exclude patterns are still roadmap items, not built.
- The dashboard charts are plain HTML and CSS. Colours are a single-hue sequential ramp; text never
  carries the data colour. There is no animation, so there is nothing for reduced-motion to switch off.
- The dashboard was checked by eye and with Playwright scripts (overflow at ten widths, Tab order,
  hover tooltip, forced colours, print media). It has not been run through axe or Lighthouse, and not
  through a real screen reader. Hover tooltips on single heatmap cells have no keyboard equivalent; the
  per-day and per-hour totals are in the tables at the bottom, the weekday-by-hour split is not.
- The README screenshots are cut from reports of `scripts/demo_repos.py` output with Playwright
  (1040 px wide for the desktop shots, 390 px for the phone shots, both at 2x). Retake them when the
  dashboard changes.

[Unreleased]: https://github.com/Habibeyilmazz/devpulse/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Habibeyilmazz/devpulse/releases/tag/v0.1.0
