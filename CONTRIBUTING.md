# Contributing

Bug reports, fixes and small features are welcome. For anything bigger than a fix, open an issue first so we can agree on the shape before you write code.

## Setup

```sh
git clone https://github.com/Habibeyilmazz/devpulse && cd devpulse
python3 -m venv .venv && .venv/bin/pip install -e ".[ai,dev]"
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

You need Python 3.10+ and `git`. To see output on invented data: `python3 scripts/demo_repos.py /tmp/devpulse-demo`, then `.venv/bin/devpulse week /tmp/devpulse-demo`.

## Ground rules

- **Tests only read repositories they create** in temp folders (`tests/conftest.py` isolates git config, `HOME` and the config file). Never point a test at a real repo, and never paste real names, emails or commit subjects into fixtures or issues.
- **Standard library first.** `rich` is the only runtime dependency (plus `tomli` on Python 3.10). A new dependency needs a reason in the PR.
- **Nothing leaves the machine** except `--ai`, which is opt-in per run. The dashboard makes no network requests; a test checks that.
- Anything that parses, counts or branches gets a test. Write the failing test first for bugs.
- Keep git read-only: new `git` calls go through the same hardened runner in `gitlog.py`.
- If you change the dashboard, retake the README screenshots from `scripts/demo_repos.py` output.
- Add a line to `CHANGELOG.md` under Unreleased.

## Layout

`gitlog.py` finds repos and parses `git log`; `stats.py` computes every number; `terminal.py`, `note.py` and `dashboard.py` are the three outputs; `ai.py` is the only network code; `cli.py` wires arguments; `config.py` reads the config file.

## Pull requests

Small, one concern each, with CI green (ruff, tests on Linux and Windows). Describe what you ran to check it.
