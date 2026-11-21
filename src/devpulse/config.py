"""Defaults from a TOML file, so a weekly run needs no flags.

Looked up at $DEVPULSE_CONFIG, else $XDG_CONFIG_HOME/devpulse/config.toml, else ~/.config/devpulse/config.toml.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

# key: (type the value must have, whether it names a path)
KEYS: dict[str, tuple[type, bool]] = {
    "path": (str, True),
    "authors": (list, False),
    "exclude": (list, False),
    "depth": (int, False),
    "md": (str, True),
    "html": (str, True),
}


class ConfigError(Exception):
    pass


def config_path() -> Path:
    if explicit := os.environ.get("DEVPULSE_CONFIG"):
        return Path(explicit).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "devpulse" / "config.toml"


def load(file: Path | None = None) -> dict:
    """The validated settings; {} when there is no file (unless DEVPULSE_CONFIG names one)."""
    file = file or config_path()
    try:
        with open(file, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        if os.environ.get("DEVPULSE_CONFIG"):
            raise ConfigError(f"{file}: no such file (named by DEVPULSE_CONFIG)") from None
        return {}
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{file}: {e}") from None
    except OSError as e:
        raise ConfigError(f"{file}: {e.strerror or e}") from None
    settings = {}
    for key, value in data.items():
        if key not in KEYS:
            raise ConfigError(f"{file}: unknown setting {key!r} (known: {', '.join(KEYS)})")
        kind, is_path = KEYS[key]
        # bool is an int to Python, but `depth = true` is a mistake
        if not isinstance(value, kind) or isinstance(value, bool) or (kind is list and not all(
            isinstance(v, str) and v for v in value
        )):  # fmt: skip
            want = {str: "a string", int: "a whole number", list: "a list of non-empty strings"}[kind]
            raise ConfigError(f"{file}: {key} must be {want}")
        if key == "depth" and value < 0:
            raise ConfigError(f"{file}: depth must be 0 or more")
        # a relative path means relative to the config file, not to wherever devpulse is run from
        settings[key] = file.parent / Path(value).expanduser() if is_path else value
    return settings
