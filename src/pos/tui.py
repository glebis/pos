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


def filter_palette(items, query):
    q = (query or "").strip().lower()
    if not q:
        return list(items)
    return [c for c in items if q in c["name"].lower() or q in c.get("synopsis", "").lower()]


def palette_items():
    return poshelp.render_json()


def run(m) -> int:
    """Launch the interactive TUI. TTY-only; refuses when piped/agent-invoked."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("pos i requires an interactive terminal", file=sys.stderr)
        return 1
    import curses

    curses.wrapper(_loop, m)
    return 0


def _data(m):
    """Fetch live data for a render pass (best-effort; tolerates a dead socket)."""
    from . import cmux, status

    try:
        rows = status.build_status(m)
    except Exception:
        rows = []
    try:
        ws = cmux.live_workspaces()
    except Exception:
        ws = []
    return build_view(m, ws, rows)


def _loop(stdscr, m):
    import curses

    curses.curs_set(0)
    pane = "focus"          # "focus" | "project"
    fi = pi = 0             # selection indices
    view = _data(m)

    while True:
        focuses = view.focuses
        cur_focus = focuses[fi].name if focuses else None
        projects = view.projects.get(cur_focus, []) if cur_focus else []
        if pi >= len(projects):
            pi = max(0, len(projects) - 1)

        _render(stdscr, view, pane, fi, pi)
        try:
            ch = stdscr.get_wch()
        except curses.error:
            continue
        key = ch

        if key in ("q", "\x1b"):                       # q / Esc
            return
        if key == curses.KEY_RESIZE:
            continue
        if key in (curses.KEY_DOWN, "j"):
            if pane == "focus":
                fi = (fi + 1) % max(1, len(focuses)); pi = 0
            elif projects:
                pi = (pi + 1) % len(projects)
            continue
        if key in (curses.KEY_UP, "k"):
            if pane == "focus":
                fi = (fi - 1) % max(1, len(focuses)); pi = 0
            elif projects:
                pi = (pi - 1) % len(projects)
            continue
        if key in (curses.KEY_RIGHT, "\t"):
            pane = "project" if projects else "focus"; continue
        if key in (curses.KEY_LEFT, curses.KEY_BTAB):
            pane = "focus"; continue
        if key in (":", "p"):
            _palette(stdscr, m); view = _data(m); continue

        sel_project = projects[pi].name if (pane == "project" and projects) else None
        sel_pfocus = projects[pi].focus if (pane == "project" and projects) else None
        action = resolve_action(pane, key if isinstance(key, str) else "",
                                focus=cur_focus, project=sel_project, project_focus=sel_pfocus)
        if action:
            _act(stdscr, m, action)
            view = _data(m)


def _render(stdscr, view, pane, fi, pi):
    h, w = stdscr.getmaxyx()
    stdscr.erase()
    mid = max(16, w // 3)
    stdscr.addstr(0, 0, "pos interactive"[: w - 1])
    stdscr.addstr(1, 0, "FOCUSES"[: mid - 1])
    stdscr.addstr(1, mid, "PROJECTS · SESSIONS"[: w - mid - 1])

    for i, f in enumerate(view.focuses):
        marker = "▸ " if (pane == "focus" and i == fi) else "  "
        line = f"{marker}{f.emoji} {f.name}"
        if 2 + i < h - 1:
            stdscr.addstr(2 + i, 0, line[: mid - 1])

    cur_focus = view.focuses[fi].name if view.focuses else None
    projects = view.projects.get(cur_focus, []) if cur_focus else []
    for i, p in enumerate(projects):
        marker = "▸ " if (pane == "project" and i == pi) else "  "
        flags = ("*" if p.dirty else " ") + ("●" if p.live else " ")
        line = f"{marker}{p.name:<20} {p.branch or '-':<12} {flags}"
        if 2 + i < h - 1:
            stdscr.addstr(2 + i, mid, line[: w - mid - 1])

    footer = "↑↓ move  →/tab pane  ⏎ open  l load  c cc  n new  r rm  : palette  q quit"
    stdscr.addstr(h - 1, 0, footer[: w - 1])
    stdscr.refresh()


def _confirm(stdscr, label):
    import curses

    h, w = stdscr.getmaxyx()
    stdscr.addstr(h - 2, 0, f"{label}? [y/N]".ljust(w - 1))
    stdscr.refresh()
    try:
        ch = stdscr.get_wch()
    except curses.error:
        return False
    return ch in ("y", "Y")


def _prompt(stdscr, names):
    """Collect args via a simple echoed line per name. Returns list or None on abort."""
    import curses

    curses.echo()
    curses.curs_set(1)
    h, w = stdscr.getmaxyx()
    vals = []
    try:
        for nm in names:
            stdscr.addstr(h - 2, 0, f"{nm}: ".ljust(w - 1))
            stdscr.refresh()
            s = stdscr.getstr(h - 2, len(nm) + 2).decode("utf-8", "replace").strip()
            if not s:
                return None
            vals.append(s)
    finally:
        curses.noecho()
        curses.curs_set(0)
    return vals


def _act(stdscr, m, action):
    import curses

    from . import cli

    rest = list(action.rest)
    if action.prompt:
        vals = _prompt(stdscr, action.prompt)
        if vals is None:
            return
        rest += vals
    if action.confirm and not _confirm(stdscr, action.label or f"{action.cmd} {' '.join(rest)}"):
        return

    curses.def_prog_mode()          # save curses tty state
    curses.endwin()                 # drop to a normal terminal
    print(f"\n$ pos {action.cmd} {' '.join(rest)}\n")
    try:
        cli.dispatch(m, action.cmd, rest)
    except Exception as e:           # never let a command crash the TUI
        print(f"pos i: command failed: {e}", file=sys.stderr)
    input("\n[press Enter to return to pos]")
    curses.reset_prog_mode()        # restore curses
    stdscr.refresh()


def _palette(stdscr, m):
    """Overlay: filter the command registry, pick one, run it (with arg prompt)."""
    import curses

    items = palette_items()
    query = ""
    sel = 0
    while True:
        shown = filter_palette(items, query)
        if sel >= len(shown):
            sel = max(0, len(shown) - 1)
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        stdscr.addstr(0, 0, f"command> {query}"[: w - 1])
        for i, c in enumerate(shown):
            if 1 + i >= h - 1:
                break
            marker = "▸ " if i == sel else "  "
            stdscr.addstr(1 + i, 0, f"{marker}{c['name']:<12} {c['synopsis']}"[: w - 1])
        stdscr.refresh()
        try:
            ch = stdscr.get_wch()
        except curses.error:
            continue
        if ch == "\x1b":
            return
        if ch == curses.KEY_DOWN:
            sel = min(sel + 1, len(shown) - 1); continue
        if ch == curses.KEY_UP:
            sel = max(sel - 1, 0); continue
        if ch in (curses.KEY_BACKSPACE, "\x7f", "\b"):
            query = query[:-1]; continue
        if ch == "\n":
            if not shown:
                return
            chosen = shown[sel]
            args = []
            if chosen.get("args"):
                vals = _prompt(stdscr, ["args"])
                if vals is not None:
                    import shlex
                    args = shlex.split(vals[0])
            confirm = chosen["name"] in ("load", "rm")
            _act(stdscr, m, Action(chosen["name"], args, confirm=confirm, label=f"{chosen['name']} {' '.join(args)}"))
            return
        if isinstance(ch, str) and ch.isprintable():
            query += ch
