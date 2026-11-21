"""The config file: where it is looked up, what it accepts, and how the command line overrides it."""

import pytest

from conftest import BOB, make_repo
from devpulse import cli, config
from test_cli import workspace


def write_config(tmp_path, text):
    file = tmp_path / ".config" / "devpulse" / "config.toml"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding="utf-8")
    return file


def test_lookup_order(tmp_path, monkeypatch):
    assert config.config_path() == tmp_path / ".config" / "devpulse" / "config.toml"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert config.config_path() == tmp_path / "xdg" / "devpulse" / "config.toml"
    monkeypatch.setenv("DEVPULSE_CONFIG", str(tmp_path / "mine.toml"))
    assert config.config_path() == tmp_path / "mine.toml"


def test_no_file_is_no_settings_unless_named(tmp_path, monkeypatch):
    assert config.load() == {}
    monkeypatch.setenv("DEVPULSE_CONFIG", str(tmp_path / "missing.toml"))
    with pytest.raises(config.ConfigError, match="no such file"):
        config.load()


def test_paths_are_relative_to_the_file_and_expand_home(tmp_path):
    file = write_config(tmp_path, 'path = "code"\nmd = "~/vault/Reviews"\nauthors = ["ada@"]\ndepth = 2\n')
    assert config.load() == {
        "path": file.parent / "code",
        "md": tmp_path / "vault" / "Reviews",
        "authors": ["ada@"],
        "depth": 2,
    }


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("path = ", "config.toml"),  # malformed TOML names the file
        ('author = "ada"', "unknown setting 'author'"),
        ('authors = "ada"', "authors must be a list of non-empty strings"),
        ('exclude = ["ok", ""]', "exclude must be a list of non-empty strings"),
        ("depth = true", "depth must be a whole number"),
        ("depth = -1", "depth must be 0 or more"),
        ("md = 3", "md must be a string"),
    ],
)
def test_bad_settings_are_named(tmp_path, capsys, text, message):
    write_config(tmp_path, text)
    with pytest.raises(config.ConfigError, match=message):
        config.load()
    assert cli.main(["standup"]) == 2
    assert "devpulse: config:" in capsys.readouterr().err


def test_config_supplies_defaults_for_a_bare_run(tmp_path, capsys):
    root = workspace(tmp_path)
    make_repo(root / "forks" / "lib", [("2026-03-09T12:00:00+01:00", "Upstream fix", {"lib.py": "x\n"}, BOB)])
    write_config(
        tmp_path,
        f'path = "{root.as_posix()}"\nauthors = ["bob@example.com", "ada@"]\nexclude = ["clients"]\nmd = "vault"\n',
    )

    assert cli.main(["week", "--date", "2026-03-10"]) == 0

    assert "Markdown note" in capsys.readouterr().out
    note = (tmp_path / ".config" / "devpulse" / "vault" / "devpulse-2026-W11.md").read_text(encoding="utf-8")
    assert "Bob's refactor" in note and "Add pagination" in note  # both identities from `authors`
    assert "### [[api]]" in note and "[[web]]" not in note  # clients/web is excluded


def test_command_line_wins_and_exclude_adds_up(tmp_path, capsys):
    root = workspace(tmp_path)
    make_repo(root / "forks" / "lib", [("2026-03-09T12:00:00+01:00", "Upstream fix", {"lib.py": "x\n"})])
    write_config(tmp_path, f'path = "{tmp_path.as_posix()}/nowhere"\nauthors = ["bob@"]\nexclude = ["clients"]\n')

    assert cli.main(["standup", str(root), "--date", "2026-03-10", "--author", "ada@", "--exclude", "forks"]) == 0

    out = capsys.readouterr().out
    assert "api: Tidy README" in out and "Bob" not in out
    assert "Dark mode" not in out and "Upstream fix" not in out


def test_everything_excluded_points_at_the_flag(tmp_path, capsys):
    root = workspace(tmp_path)
    assert cli.main(["week", str(root), "--exclude", "*"]) == 2
    assert "(see --depth, --exclude)" in capsys.readouterr().err


def test_a_notepad_file_with_a_byte_order_mark_loads_and_a_binary_one_is_named(tmp_path):
    file = tmp_path / "c.toml"
    file.write_bytes(b"\xef\xbb\xbfdepth = 2\n")  # what Windows Notepad saves by default
    assert config.load(file) == {"depth": 2}

    file.write_bytes(b"depth = \xff\xfe\n")
    with pytest.raises(config.ConfigError, match="c.toml"):
        config.load(file)
