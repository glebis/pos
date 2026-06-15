"""`pos new` / `pos rename` / `pos rm` — live workspace CRUD over cmux.

These act on the live cmux workspaces (the same things spread/gather/solo move
around), not the persistent manifest. `new` is tmux-backed (durable + idempotent);
`rm` refuses to close a workspace that ISN'T tmux-backed unless --force, since a
non-backed workspace can't be reopened losslessly.
"""

from . import cmux, tmuxify
from .label import glyphed_title, strip_glyph


def create(name: str, cwd: str, glyph: str = "") -> str | None:
    """Open (or focus) a tmux-backed workspace labelled `name` at `cwd`."""
    label = glyphed_title(glyph, name) if glyph else name
    return cmux.open_and_label(cwd=cwd, label=label)


def rename(old: str, new: str, glyph: str = "") -> str | None:
    """Rename the workspace currently labelled `old` to `new`. Returns ref or None."""
    ref = cmux.find_workspace_ref(cmux.live_workspaces(), old)
    if not ref:
        return None
    label = glyphed_title(glyph, new) if glyph else new
    cmux.run(cmux.rename_workspace_argv(label, ref=ref))  # sidebar
    cmux.run(cmux.rename_tab_argv(label, ref=ref))        # inner tab
    return ref


def backing_session(ref: str) -> str | None:
    """The tmux session backing a workspace, read from its SELECTED surface
    (e.g. 'tmux attach -t brain'). Robust to renames — unlike deriving from the
    label, which diverges from the session name once a workspace is renamed."""
    sel = tmuxify.selected_surface(tmuxify._surfaces(ref))
    return tmuxify.tmux_session_of(sel.get("title", ""))


def is_backed(ref: str) -> bool:
    """True if the workspace's actual backing tmux session is live (safe to reopen)."""
    sess = backing_session(ref)
    return bool(sess) and cmux.run(["tmux", "has-session", "-t", sess]).returncode == 0


def remove(name: str, force: bool = False) -> tuple:
    """Close the workspace labelled `name`. Returns (ref, status).

    status: 'not-found' | 'unbacked' (refused, needs --force) | 'closed'.
    """
    ref = cmux.find_workspace_ref(cmux.live_workspaces(), name)
    if not ref:
        return None, "not-found"
    if not is_backed(ref) and not force:
        return ref, "unbacked"
    cmux.run([cmux.CMUX_BIN, "close-workspace", "--workspace", ref])
    return ref, "closed"
