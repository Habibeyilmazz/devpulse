# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

Nothing yet. Ideas that are not built are listed under Roadmap in the README.

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
- The `--ai` path is tested with a fake client only. It has not been run against the live API.
- Known limits: history is bounded with `git log --since` (commit date, see README "How it works");
  a commit subject containing the byte 0x1E is cut at that byte; Windows is untested.
- The dashboard charts are plain HTML and CSS. Colours are a single-hue sequential ramp; text never
  carries the data colour.

[Unreleased]: https://github.com/Habibeyilmazz/devpulse/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Habibeyilmazz/devpulse/releases/tag/v0.1.0
