"""`pos spread` / `pos gather` — layout each workspace as its own window, or merge.

cmux windows are top-level (OS-level) windows; the switcher shows one per window.
`spread` fans every workspace in the current window out into its own dedicated
window (good for window-manager / multi-monitor switching). `gather` is the
inverse — pulls every workspace back into a single window (also the way to undo a
spread or clean up leftover windows, e.g. a stray UltraFocus parking window).

new-window always auto-creates a throwaway default tab; spread disposes it so each
window ends up holding exactly its one project.
"""

import time

from . import cmux, settings

AEROSPACE = "aerospace"


def aerospace_running() -> bool:
    return cmux.run([AEROSPACE, "list-workspaces", "--focused"]).returncode == 0


def _default_workspace(window_id: str) -> str | None:
    for w in cmux.list_windows():
        if w["id"] == window_id:
            return w["selected_workspace"]
    return None


def spread() -> int:
    """Move every non-current workspace into its own new window. Returns count moved."""
    home = cmux.current_window_id()
    workspaces = cmux.window_workspaces()["workspaces"]
    targets = [w for w in workspaces if not w.get("selected")]  # current stays in home
    if not targets:
        print("pos spread: only one workspace here — nothing to fan out.")
        return 0

    moved = 0
    for w in targets:
        res = cmux.run([cmux.CMUX_BIN, "new-window"])
        win = cmux.parse_ok_uuid(res.stdout)
        if not win:
            continue
        default = _default_workspace(win)
        cmux.run([cmux.CMUX_BIN, "move-workspace-to-window", "--workspace", w["ref"], "--window", win])
        if default:
            cmux.run([cmux.CMUX_BIN, "close-workspace", "--workspace", default])
        moved += 1
    # return focus to the home window, then re-render
    cmux.run([cmux.CMUX_BIN, "focus-window", "--window", home])
    cmux.run([cmux.CMUX_BIN, "refresh-surfaces"])
    print(f"pos spread — {moved} workspace(s) each in their own window (current kept in place).")
    return moved


def tile() -> int:
    """`pos tile` — fan projects into their own OS windows, then have aerospace
    grid them across the screen. Each cmux internal window is a real OS window
    (verified), so the tiling WM arranges them. Falls back to a plain spread if
    aerospace isn't running."""
    cfg = settings.load()
    n = spread()
    if cfg["window_manager"] != "aerospace":
        print(f"  (window_manager = {cfg['window_manager']}: spread only, not tiled. "
              "`pos config` to enable aerospace.)")
        return n
    if not aerospace_running():
        print("  (aerospace not running — windows spread but not auto-tiled. "
              "`open -a AeroSpace`, grant Accessibility, then `pos tile` again.)")
        return n
    time.sleep(0.4)  # let aerospace register the freshly-created windows
    cmux.run([AEROSPACE, "flatten-workspace-tree"])      # clear nested splits
    cmux.run([AEROSPACE, "layout", cfg["tile_layout"]])  # configured layout
    print(f"pos tile — {n + 1} project window(s) tiled across the screen via aerospace ({cfg['tile_layout']}).")
    return n


def gather() -> int:
    """Merge every other window's workspaces into the current window. Returns count moved."""
    home = cmux.current_window_id()
    others = [w for w in cmux.list_windows() if w["id"] != home]
    if not others:
        print("pos gather: already a single window.")
        return 0

    moved = 0
    for win in others:
        cmux.run([cmux.CMUX_BIN, "focus-window", "--window", win["id"]])
        for w in cmux.window_workspaces()["workspaces"]:
            r = cmux.run([cmux.CMUX_BIN, "move-workspace-to-window", "--workspace", w["ref"], "--window", home])
            if r.returncode == 0:
                moved += 1
        cmux.run([cmux.CMUX_BIN, "close-window", "--window", win["id"]])
    cmux.run([cmux.CMUX_BIN, "focus-window", "--window", home])
    cmux.reorder_pinned_first()        # pinned workspaces back to the top
    cmux.run([cmux.CMUX_BIN, "refresh-surfaces"])
    print(f"pos gather — pulled {moved} workspace(s) into one window.")
    return moved
