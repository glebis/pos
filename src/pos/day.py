"""`pos day` — hybrid daily pinning.

Stable spine: pin every focus context (business/play/brain/health/life).
Dynamic: pin the projects mentioned in today's daily note.
"""
import re
import subprocess
from pathlib import Path

from .cmux import CMUX_BIN, run
from .label import strip_glyph
from .manifest import Manifest, focus_order

DAILY_DIR = "~/Brains/brain/Daily"


def active_projects_from_text(text: str, m: Manifest) -> list:
    """Return manifest project names whose name appears in the text.

    Matches on word boundaries so 'cenno' matches but a substring of a larger
    word does not. Preserves manifest order, de-duplicated.
    """
    found = []
    for name in m.projects:
        # project names may contain . and - — escape, bound by non-word edges
        pattern = r"(?<![\w-])" + re.escape(name) + r"(?![\w-])"
        if re.search(pattern, text):
            found.append(name)
    return found


def build_pin_plan(m: Manifest, daily_text: str) -> dict:
    """Hybrid plan: all focus contexts + today's active projects."""
    return {
        "focuses": list(focus_order(m)),
        "projects": active_projects_from_text(daily_text, m),
    }


def daily_note_path(date_str: str) -> Path:
    """Path to the daily note for a YYYYMMDD date string."""
    return Path(DAILY_DIR).expanduser() / f"{date_str}.md"


def read_daily(date_str: str) -> str:
    p = daily_note_path(date_str)
    return p.read_text() if p.exists() else ""


def _live_workspaces() -> list:
    import json

    out = subprocess.run([CMUX_BIN, "--json", "list-workspaces"], capture_output=True, text=True)
    try:
        ws = json.loads(out.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return ws if isinstance(ws, list) else ws.get("workspaces", ws)


def _unpin_all(workspaces) -> list:
    """Unpin every currently-pinned workspace. Returns titles unpinned."""
    unpinned = []
    for w in workspaces:
        if w.get("pinned"):
            run([CMUX_BIN, "workspace-action", "--workspace", w["ref"], "--action", "unpin"])
            unpinned.append(w["title"])
    return unpinned


def _pin_workspace_by_title(wanted_titles: set, unpin_others: bool = True) -> list:
    """Pin live workspaces matching wanted_titles.

    With unpin_others=True (default), first unpins ALL currently-pinned
    workspaces so the resulting pinned set is exactly today's plan.
    """
    ws = _live_workspaces()
    if unpin_others:
        _unpin_all(ws)
    pinned = []
    for w in ws:
        if strip_glyph(w.get("title", "")) in wanted_titles:
            run([CMUX_BIN, "workspace-action", "--workspace", w["ref"], "--action", "pin"])
            pinned.append(w["title"])
    return pinned
