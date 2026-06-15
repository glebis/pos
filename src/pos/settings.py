"""pos behaviour settings — small, flat, stdlib-only (tomllib read, hand-written
TOML on save so we keep the zero-dependency runtime).

Separate from the manifest (focus.toml = projects/focuses); this holds how pos
*behaves*: which window manager `pos tile` drives, the tiling layout, etc.
"""

import os
import tomllib
from pathlib import Path

DEFAULTS = {
    "window_manager": "aerospace",  # what `pos tile` drives; "none" = spread only
    "tile_layout": "tiles",         # aerospace layout used by `pos tile`
}

CHOICES = {
    "window_manager": ["aerospace", "none"],
    "tile_layout": ["tiles", "accordion", "horizontal", "vertical"],
}


def settings_path() -> Path:
    return Path(os.environ.get("POS_SETTINGS", "~/.config/personal-os/settings.toml")).expanduser()


def load() -> dict:
    """Current settings = defaults overlaid with the file (file wins)."""
    p = settings_path()
    data = {}
    if p.exists():
        try:
            data = tomllib.loads(p.read_text())
        except (OSError, tomllib.TOMLDecodeError):
            data = {}
    # only keep known keys, defaults fill the rest
    return {k: data.get(k, v) for k, v in DEFAULTS.items()}


def save(settings: dict) -> None:
    p = settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'{k} = "{settings[k]}"' for k in DEFAULTS if k in settings]
    p.write_text("\n".join(lines) + "\n")


def validate(key: str, value: str) -> str | None:
    """Return an error message if (key, value) is invalid, else None."""
    if key not in DEFAULTS:
        return f"unknown setting {key!r} (known: {', '.join(DEFAULTS)})"
    if key in CHOICES and value not in CHOICES[key]:
        return f"{key} must be one of: {', '.join(CHOICES[key])}"
    return None


def set_value(key: str, value: str) -> tuple[bool, str]:
    err = validate(key, value)
    if err:
        return False, err
    s = load()
    s[key] = value
    save(s)
    return True, f"{key} = {value}"
