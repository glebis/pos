"""pos interactive TUI — a curses cockpit over the same commands as the CLI.

The curses shell (run/_loop/_act/_palette) is intentionally thin; all decision
logic lives in pure, unit-tested helpers (build_view, resolve_action,
filter_palette) so behavior is testable without a terminal. `curses` is imported
inside run() only, so this module imports cleanly in headless tests.
"""
import sys
from dataclasses import dataclass, field

from . import help as poshelp
from .label import strip_glyph
from .manifest import focus_order


@dataclass
class Action:
    cmd: str
    rest: list
    confirm: bool = False
    label: str = ""
    prompt: list = field(default_factory=list)


@dataclass
class FocusRow:
    name: str
    emoji: str


@dataclass
class ProjectRow:
    name: str
    focus: str
    branch: str | None
    dirty: bool
    live: bool


@dataclass
class View:
    focuses: list
    projects: dict   # focus name -> list[ProjectRow]
    live: list       # glyph-stripped live workspace titles


def build_view(m, workspaces, status_rows) -> View:
    live = [strip_glyph(w.get("title", "")) for w in workspaces]
    live_set = set(live)
    focuses = [FocusRow(f, m.focuses[f].emoji) for f in focus_order(m)]
    projects = {f.name: [] for f in focuses}
    for r in status_rows:
        projects.setdefault(r["focus"], []).append(
            ProjectRow(
                name=r["project"],
                focus=r["focus"],
                branch=r.get("branch"),
                dirty=bool(r.get("dirty")),
                live=r["project"] in live_set,
            )
        )
    return View(focuses=focuses, projects=projects, live=live)


def resolve_action(pane, key, *, focus=None, project=None, project_focus=None):
    """Map a keypress in a pane+selection to an Action, or None for non-action
    keys (navigation/quit are handled by the loop, not here). Enter is "\\n"."""
    if pane == "focus":
        if not focus:
            return None
        if key in ("\n", "l"):
            return Action("load", [focus, "--apply"], confirm=True, label=f"load {focus}")
        if key == "c":
            return Action("cc", [focus], label=f"cc {focus}")
        if key == "n":
            return Action("new", [], label="new workspace", prompt=["name"])
        return None
    if pane == "project":
        if not project:
            return None
        if key == "\n":
            return Action("p", [project], label=f"open {project}")
        if key == "l":
            return Action("load", [project, "--apply"], confirm=True, label=f"load {project}")
        if key == "c":
            return Action("cc", [project_focus], label=f"cc {project_focus}") if project_focus else None
        if key == "n":
            return Action("new", [], label="new workspace", prompt=["name"])
        if key == "r":
            return Action("rm", [project], confirm=True, label=f"rm {project}")
        return None
    return None


def palette_items():
    return poshelp.render_json()


def filter_palette(items, query):
    q = (query or "").strip().lower()
    if not q:
        return list(items)
    return [c for c in items if q in c["name"].lower() or q in c.get("synopsis", "").lower()]
