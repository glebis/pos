"""`pos tmuxify` — make workspaces durable by backing their shell with tmux.

Why: UltraFocus (and crash recovery) can only restore a workspace losslessly if
it is backed by a tmux session — `tmux new-session -A -s <name>` reattaches the
live session. A raw cmux shell surface can't be reattached, so closing it loses
its state. This audits which workspaces are already tmux-backed and converts the
safe ones (an idle shell) in place.

Conversion is `exec tmux new-session -A -s <name> -c "$PWD"` sent INTO the shell:
`exec` replaces the shell with tmux (so the surface/workspace is preserved), and
the shell expands its own `$PWD`, so the new session keeps the current directory
— no external cwd guessing. Lossless for an idle shell.

Conservative by design (dry-run unless --apply): it converts only surfaces it can
classify as a plain shell, and NEVER the current workspace (never send into the
surface you're typing in) or a surface running an app (a dev server would die).
"""

import re

from . import cmux
from .label import strip_glyph

TMUX_RE = re.compile(r"-[ts]\s+(\S+)")


# ── pure classification ──────────────────────────────────────────────────
def tmux_session_of(surface_title: str) -> str | None:
    """tmux session a surface attaches, from 'tmux attach -t X' / 'new-session -s X'."""
    m = TMUX_RE.search(surface_title or "")
    return m.group(1) if m else None


def classify(surface_title: str) -> str:
    """'tmux' (already backed), 'shell' (safe to convert), or 'other' (skip)."""
    t = (surface_title or "").strip()
    if t.startswith("tmux"):
        return "tmux"
    # shell prompts / cwd-titled surfaces carry a path or user@host marker
    if "@" in t or "/" in t or t.startswith("~") or t.startswith("…"):
        return "shell"
    return "other"


def selected_surface(surfaces: list) -> dict:
    for s in surfaces:
        if s.get("selected"):
            return s
    return surfaces[0] if surfaces else {}


def audit_workspace(title: str, surfaces: list) -> dict:
    sel = selected_surface(surfaces)
    kind = classify(sel.get("title", ""))
    sess = tmux_session_of(sel.get("title", "")) if kind == "tmux" else None
    return {
        "title": title,
        "selected_title": sel.get("title", ""),
        "selected_ref": sel.get("ref"),
        "kind": kind,
        "session": sess,
        # only a tmux surface with a KNOWN session name is safely reattachable
        "backed": kind == "tmux" and sess is not None,
    }


def session_name_for(title: str) -> str:
    return cmux.session_name(strip_glyph(title))


def build_plan(audits: list, current_title: str | None) -> dict:
    """Split audited workspaces into convert / already-backed / skipped (other or current)."""
    convert, backed, skipped = [], [], []
    cur = strip_glyph(current_title or "")
    for a in audits:
        if a["backed"]:
            backed.append(a)
        elif strip_glyph(a["title"]) == cur:
            skipped.append({**a, "reason": "current workspace (don't touch your active shell)"})
        elif a["kind"] == "shell":
            convert.append(a)
        elif a["kind"] == "tmux":
            skipped.append({**a, "reason": "running tmux but session name unknown — can't guarantee reattach"})
        else:
            skipped.append({**a, "reason": f"surface looks like an app/unknown ({a['selected_title']!r})"})
    return {"convert": convert, "backed": backed, "skipped": skipped}


def convert_command(title: str) -> str:
    """The in-place conversion sent to a shell surface ($PWD expanded by the shell)."""
    return f'exec tmux new-session -A -s {session_name_for(title)} -c "$PWD"'


# ── live gather + apply (side effects) ────────────────────────────────────
import json


def _surfaces(ref: str) -> list:
    out = cmux.run([cmux.CMUX_BIN, "--json", "list-pane-surfaces", "--workspace", ref])
    try:
        return json.loads(out.stdout or "{}").get("surfaces", [])
    except json.JSONDecodeError:
        return []


def gather() -> tuple:
    """(current_title, [audit,...]) for every workspace in the current window."""
    win = cmux.window_workspaces()
    current = None
    audits = []
    for w in win["workspaces"]:
        if w.get("selected"):
            current = w.get("title")
        a = audit_workspace(w.get("title", ""), _surfaces(w["ref"]))
        a["ref"] = w["ref"]
        audits.append(a)
    return current, audits


def apply(convert: list) -> int:
    """Convert each target's selected shell surface to a tmux session, in place."""
    done = 0
    for a in convert:
        ref, sref = a["ref"], a.get("selected_ref")
        name = session_name_for(a["title"])
        cmux.run([cmux.CMUX_BIN, "send", "--workspace", ref, "--surface", sref, convert_command(a["title"])])
        cmux.run([cmux.CMUX_BIN, "send-key", "--workspace", ref, "--surface", sref, "Enter"])
        # cmux titles the tab with the launch command ('exec tmux new-session …');
        # set a clean tab title (the session name) instead.
        cmux.run([cmux.CMUX_BIN, "rename-tab", "--workspace", ref, "--surface", sref, name])
        done += 1
    if done:
        cmux.run([cmux.CMUX_BIN, "refresh-surfaces"])
    return done
