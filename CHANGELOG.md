# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `devpulse quarter` (round 15, feature): the calendar quarter (Q1 = January to March) in all four
  outputs, with `--last`, `--date`, `--md`, `--html`, `--json` and `--ai` like the other periods.
  Files are named `devpulse-2026-Q4.*`, the note's type and tag are `quarterly-review` and it links
  to the previous quarter's note. The terminal's second sparkline is per week; the dashboard shows the
  quarter as a one-grid day-by-day calendar beside the heatmap (90-odd day columns did not fit) and the
  last four quarters as the trend. Picked because a performance review or OKR check-in covers a
  quarter, and month plus year left no way to get one. Checked with Playwright at 1040, 390 and 360 px
  (light and dark): no overflow, no console errors, no requests. No README screenshot of it yet.
- Several folders at once (round 12, feature): `devpulse week ~/code ~/work` reviews the repos under
  every folder given as one report, and the config file's `path` takes a list (a plain string still
  works). A repo reached through two folders is read once; two repos with the same folder name are named
  by their path below their common folder (`code/api`, `work/api`). The folders can sit on either side of
  the options (`week ~/code --last ~/work`). An empty `path = []` is a config error. Picked because a
  newcomer whose repos are not all under one folder had no way to get one weekly note.

### Fixed

- Round 14 (launch): audited README, repo description/topics, CONTRIBUTING and issue templates; all present and accurate. Verified the README quickstart by installing from the GitHub URL into a clean venv and running `devpulse year` on the demo repos. No changes needed. Still unverified: pipx/uvx, Obsidian rendering, Windows UNC gitdir, a live `--ai` call. `week -- -dir --author x` reads later words as paths (argparse standard).

- Round 13 (tests): tried to break the CLI (empty, binary-heavy and 200 KB-subject commits, unicode, three
  timezones, case-different emails, four parallel runs, bad/odd paths, `--ai` with no/bad key, unwritable
  outputs). Found no bugs; added a regression test. A path starting with `-` works as `./-name`.
- Round 12: the Markdown note put commit subjects, the AI narrative and the "one thing" in raw, so a
  subject like `![](https://host/pixel.png)` or `<img src=...>` made Obsidian load a remote image when the
  note was opened, and `![[file]]` embedded a vault file (gap reported in round 11). `<`, `[`, `]` and `\`
  in that text are now backslash-escaped (`note.inert`); devpulse's own wikilinks are untouched.

### Security

Second security pass (round 11). Re-read every module and the workflow, probed the CLI with hostile
folder names and paths, scanned the git history, and ran `pip-audit --strict` locally on everything
installed (runtime, `[ai]` and dev): no known vulnerabilities. Fixed, each with a test that fails
without the fix:

- The "skipping REPO: ..." warning for a repo git cannot read printed the repo's full path raw, so a
  folder name holding escape sequences (say, inside an unpacked archive) reached the terminal. Round 3
  cleaned the short repo names but missed this one path; it now goes through `printable` too.
- The "Markdown note / HTML dashboard / JSON data" lines passed the output path to rich as markup:
  `--md "notes/[red]x[/red]"` printed `notes/x/...`, a file that does not exist, and a `[link=...]` in
  a path became a terminal hyperlink. The path is now escaped.
- CI pins `build` and `pip-audit` to exact versions (the actions were already pinned to commits).

Checked and left: the dashboard (every interpolation escaped, CSP with `default-src 'none'`), the
note (frontmatter is JSON-quoted, wikilinks cleaned), git hardening from round 3, workflow
permissions (`contents: read`, `persist-credentials: false`, no `pull_request_target`), no secrets or
personal addresses in the history. Not fixed: a `.git` file whose `gitdir:` names a UNC path would make
git on Windows open that share (untested; git itself does the same in a git-aware shell prompt).

### Fixed

- The terminal header split its dates over two lines under 64 columns (gap reported in round 10);
  the dates now move to their own line when the header does not fit.

### Changed

- Design pass (round 10). Looked at the terminal (piped and on a tty, 60/80/100 columns) and the
  dashboard in Playwright (1280 and 390 px, light and dark, week/month/year/empty, keyboard only).
  Fixed:
  - The report's table rows ended in rich's padding spaces when piped (the gap from round 9); output
    now goes through `terminal.NoTrailingSpaces`. On a tty, rich's highlighter coloured some numbers
    cyan (the period, the hour axis, language shares, standup dates); highlighting is off.
  - The year calendar drew days still to come like days without commits, so December looked like a
    break; they are now outlined squares, and the card's note says so while the year is in progress.
  - The empty dashboard suggested `--last` for a past period chosen with `--date`, but `--last` counts
    back from today; it now names the earlier period with `--date`.
  - The chart tables: numbers right-aligned under their headings, zeros dimmed, header row sticky.
  - `standup` printed "Today" without its date when nothing was committed yet.
  - README screenshots and the terminal sample retaken from the demo repos (`--date 2026-11-20`).
  Left alone: the layout, type and colours already held up at every size checked; no motion to
  reduce. Still unchecked: axe/Lighthouse (not installed), pipx/uvx, a live `--ai` run.
- First-run review (round 9). Cloned the repo fresh, installed it from GitHub into a clean venv
  (`pip install git+...`, standing in for pipx: neither pipx nor uv is on the build machine) and followed
  the README with an empty `HOME`: demo repos, `week`, `month`, `year`, `standup`, `--md/--html/--json`,
  `--json -`, `--exclude`, `--ai` without the SDK, and the error paths (missing folder, no repos, no git
  identity, bad `--date`). All behaved as documented; both dashboards render with no console errors,
  no requests and no horizontal scroll at 360 px. Fixed: `--depth -1` was accepted on the command line
  (and reported "within -1 levels") while the config file rejects it; it is now a usage error.
  Read the whole codebase as a reviewer and found nothing else wrong. Still unchecked: `uvx` and pipx
  themselves, a live `--ai` run, Windows by hand (CI runs the tests there). Known cosmetic: rich pads
  the terminal report's table lines with trailing spaces when piped to a file.
- Performance and accessibility pass (round 8, lens "perf-a11y"). Measured on 4 synthetic repos, 1,500
  days, about 1,400 commits in the year (`scripts/demo_repos.py --days 1500`): `devpulse --help` 0.26 s;
  `year` 8.5 s, all of it waiting on `git log --numstat` (Python itself under 0.3 s). Repos are now read
  in parallel threads (up to 8), in the same order, so the output is byte-identical: `year` 3.8 s.
  Single huge repos stay git-bound; there is nothing left to win in Python.
- Dashboard (year, 2,400 nodes, 84 KB): no console errors, no horizontal scroll at 360 px, one h1 and
  one main, every control named. Fixed: the `<summary>` toggles were 22.5 px tall, under the WCAG 2.2
  24 px target size; they are now 30 px. No Lighthouse or axe run (not installed); checked with a
  Playwright script. Nothing unused to delete: ruff is clean and there are two runtime dependencies.

### Added

- `--json PATH` for `week`, `month` and `year` (round 7, feature): the report as data, with raw
  numbers, projects, languages, per-day counts, the weekday-by-hour heatmap, trend, biggest days,
  focus sessions and every commit. `--json -` prints it instead of the terminal report, for `jq`.
  A `json` key in the config file sets a default folder. The output carries `"schema": 1`
  (`export.py`); bump it only when a key is renamed or removed.
- The dashboard's hour table now has a column per weekday and a total, so every heatmap cell can be
  reached with the keyboard and a screen reader (round 7; the hover tooltips were the only way before).

- Launch pass (round 6): CONTRIBUTING.md, issue templates, a README comparison with alternatives
  and a Contributing section. Checked the reported gaps: heatmap cells still have no keyboard focus
  (the hour table carries the same totals) and same-second identical empty commits still count once;
  both left as documented limits. Playwright e2e not added.
- Config file (round 4, feature): `~/.config/devpulse/config.toml` (or `$XDG_CONFIG_HOME/devpulse/`, or
  the file `DEVPULSE_CONFIG` names) sets defaults for `path`, `authors`, `exclude`, `depth`, `md` and
  `html`, so the weekly run is a bare `devpulse week`. Flags win over the file; `--exclude` adds to it.
  Relative paths are relative to the file. Unknown keys, wrong types and broken TOML stop the run with
  the file and key named. Python 3.10 reads it with `tomli`, the only new dependency (3.11+ use `tomllib`).
- `--exclude GLOB` (repeatable): skip folders whose name or path below `PATH` matches, with everything
  inside them. Matching is case-sensitive on every platform; `*` also crosses `/`.

### Fixed

- Reliability pass (round 5, lens "tests"). Tried to break the tool with odd repos (empty, binary-only,
  detached HEAD, bare, future-dated, +14:00 and -12:00 offsets, emoji and bidi subjects), 17,000
  commits in one repo (0.5 s), four runs writing one file, and odd flags and config files.
  Most of it held. Fixed, each with a test written first:
  - A config file saved by Windows Notepad (UTF-8 with a byte order mark) failed with
    "Invalid statement"; it now loads, and a file that is not UTF-8 is named in the error.
  - A commit with an empty message printed as a blank bullet; it now reads "(no message)". A commit
    subject of 100,000 characters (5,000 in the test: Windows caps a command line) went whole into the note, the dashboard, standup and the AI prompt;
    subjects are cut at 300 characters.
  - `--author ""` matched every commit; it is now a usage error.
  Known and left: two empty commits with the same subject in the same second count once (the
  cherry-pick de-duplication); the heatmap cells still have no keyboard focus (the hour table under
  it carries the same numbers); Windows and a live `--ai` run were not exercised.

### Security

A security pass over the whole repo (round 3). Findings fixed, each with a regression test:

- Commit subjects, folder names and the `--ai` text reached the terminal with their escape sequences
  intact, so a commit subject could retitle or clear the terminal, fake an OSC 8 link or write the
  clipboard (OSC 52). Control characters (C0 but tab, DEL, C1) and bidi overrides are now replaced
  with `�` when the text is read (`gitlog.printable`). The AI's "one thing" is kept to one line.
- On git older than 2.44 `GIT_NO_LAZY_FETCH` is ignored, so reading a partial clone could fetch, and
  run the `remote.*.uploadpack` or ssh command the repo's own config names. git now runs with an empty
  `GIT_ALLOW_PROTOCOL`, which blocks every transport on any git version; a repo's
  `protocol.<name>.allow` cannot loosen it (it can loosen `-c protocol.allow=never`, checked by hand).
  The test sets a command in the config for every hook-like key and checks that none runs.
- The dashboard has a Content-Security-Policy: `default-src 'none'` and a hash for its one script.
  Checked in Chromium: the tooltip still works, an injected inline script is blocked.
- CI actions are pinned to commit SHAs, and the build job runs `pip-audit --strict` on the runtime
  and `[ai]` dependencies.

Checked and found fine: HTML and rich-markup escaping, YAML frontmatter quoting, `--open`'s temp
folder (`mkdtemp`, private), `os.walk` not following symlinks, no secrets or personal addresses in the
git history, `pip-audit` clean locally, workflow permissions already `contents: read`. Not changed:
a commit subject in the Markdown note can still hold Markdown, HTML or an Obsidian plugin query
(Obsidian sanitizes HTML; Dataview inline JS is off by default); escaping it would mangle backticks.

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
- Still open after round 7: two empty commits with the same subject in the same second count once
  (the cherry-pick de-duplication key is author time, subject and files; telling them apart would need
  parent SHAs). Judged too rare to change. `--json -` writes no "written" lines for other files.
- Windows is covered by CI only (tests plus a piped run); nobody has used it there interactively.
- Config lives in `config.py` (lookup and validation) and `cli.apply_config` (merging with flags).
  The tests isolate `HOME`, `USERPROFILE`, `XDG_CONFIG_HOME` and `DEVPULSE_CONFIG`.
- The dashboard charts are plain HTML and CSS. Colours are a single-hue sequential ramp; text never
  carries the data colour. There is no animation, so there is nothing for reduced-motion to switch off.
- The dashboard was checked by eye and with Playwright scripts (overflow at ten widths, Tab order,
  hover tooltip, forced colours, print media). It has not been run through axe or Lighthouse, and not
  through a real screen reader. Hover tooltips on single heatmap cells are mouse-only by design; every
  cell's number is also in the "Commits per hour and weekday" table at the bottom.
- The README screenshots are cut from reports of `scripts/demo_repos.py` output with Playwright
  (1040 px wide for the desktop shots, 390 px for the phone shots, both at 2x). Retake them when the
  dashboard changes.

[Unreleased]: https://github.com/Habibeyilmazz/devpulse/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Habibeyilmazz/devpulse/releases/tag/v0.1.0
