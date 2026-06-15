"""UltraFocus — hide every workspace except the current one.

cmux has no `hide`/`archive` action, only windows. So UltraFocus parks the other
workspaces in a separate (hidden) cmux window, leaving the current window showing
only the focused workspace. It is a toggle: running `pos solo` again moves the
parked workspaces back and disposes the parking window.

State (which workspaces were parked, the home + parking window UUIDs) is written
to a small JSON file so the second invocation can restore exactly what it hid —
tracked by stable UUID, never the parking window's own throwaway default tab.
"""

import json
import os
from pathlib import Path

from . import cmux


def state_path() -> Path:
    base = os.environ.get("POS_STATE", "~/.config/personal-os/solo.json")
    return Path(base).expanduser()


def is_active() -> bool:
    return state_path().exists()


# ── pure ──────────────────────────────────────────────────────────────────
def park_targets(workspaces: list) -> list:
    """UUIDs of every workspace except the selected one (what UltraFocus hides)."""
    return [w["id"] for w in workspaces if not w.get("selected")]


def selected_id(workspaces: list) -> str | None:
    for w in workspaces:
        if w.get("selected"):
            return w["id"]
    return None


# ── side effects ───────────────────────────────────────────────────────────
def _save(state: dict) -> None:
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state))


def engage() -> int:
    win = cmux.window_workspaces()
    workspaces = win["workspaces"]
    home = win["window_id"]
    targets = park_targets(workspaces)
    focused = selected_id(workspaces)
    if not targets:
        print("UltraFocus: only one workspace here — nothing to hide.")
        return 0

    res = cmux.run([cmux.CMUX_BIN, "new-window"])
    parked_win = cmux.parse_ok_uuid(res.stdout)
    if not parked_win:
        print(f"UltraFocus: could not create parking window: {res.stdout.strip()!r}")
        return 1

    moved = []
    for wid in targets:
        r = cmux.run([cmux.CMUX_BIN, "move-workspace-to-window", "--workspace", wid, "--window", parked_win])
        if r.returncode == 0:
            moved.append(wid)
    # NOTE: do NOT label the parking window — `rename-window --workspace <ws>`
    # renames the WORKSPACE's title, not the window (cmux footgun), corrupting it.
    # The parking window is hidden anyway.
    # stay looking at the focused workspace in the home window
    if focused:
        cmux.run([cmux.CMUX_BIN, "select-workspace", "--workspace", focused])
    # moved surfaces don't re-render until forced — clears the stuck loading spinner
    cmux.run([cmux.CMUX_BIN, "refresh-surfaces"])

    _save({"home_window": home, "parked_window": parked_win, "parked": moved})
    print(f"UltraFocus on — hid {len(moved)} workspace(s). Run `pos solo` again to restore.")
    return 0


def restore() -> int:
    try:
        state = json.loads(state_path().read_text())
    except (OSError, json.JSONDecodeError):
        print("UltraFocus: no saved state to restore.")
        return 1
    home = state.get("home_window")
    restored = 0
    for wid in state.get("parked", []):
        r = cmux.run([cmux.CMUX_BIN, "move-workspace-to-window", "--workspace", wid, "--window", home])
        if r.returncode == 0:
            restored += 1
    if state.get("parked_window"):
        cmux.run([cmux.CMUX_BIN, "close-window", "--window", state["parked_window"]])
    cmux.reorder_pinned_first()        # restore pinned-at-top ordering
    # re-render the workspaces just moved back (else they sit on a loading spinner)
    cmux.run([cmux.CMUX_BIN, "refresh-surfaces"])
    state_path().unlink(missing_ok=True)
    print(f"UltraFocus off — restored {restored} workspace(s).")
    return 0


def toggle() -> int:
    return restore() if is_active() else engage()
