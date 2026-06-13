import re
import shlex
import subprocess

from .label import strip_glyph

CMUX_BIN = "/Applications/cmux.app/Contents/Resources/bin/cmux"


def session_name(label: str) -> str:
    """Derive a tmux-safe session name from a workspace label.

    tmux session names must not contain '.' or ':'; we also drop the focus
    glyph and collapse whitespace, so `pos <name>` always maps to the SAME
    session (attach-or-create idempotency + durability).
    """
    base = strip_glyph(label)
    base = re.sub(r"[\s.:]+", "-", base.strip())
    base = re.sub(r"-{2,}", "-", base).strip("-")
    return base or "session"


def open_workspace_argv(title: str, cwd: str) -> list:
    """Open a workspace backed by a durable tmux session (attach-or-create).

    `tmux new-session -A -s <name>` attaches an existing session of that name
    or creates it — so the workspace survives cmux quitting/crashing, and
    re-opening via `pos` re-attaches the same live session (resurrect/continuum
    restore it across reboots).
    """
    sess = session_name(title)
    command = f"tmux new-session -A -s {shlex.quote(sess)} -c {shlex.quote(cwd)}"
    return [CMUX_BIN, "new-workspace", "--command", command]


def sidecar_argv(url) -> list:
    if url:
        return [CMUX_BIN, "new-surface", "--type", "browser", "--url", url]
    return [CMUX_BIN, "new-pane", "--type", "terminal"]


def rename_workspace_argv(title: str, ref: str | None = None) -> list:
    if ref:
        return [CMUX_BIN, "rename-workspace", "--workspace", ref, title]
    return [CMUX_BIN, "rename-workspace", title]


def parse_new_workspace_ref(stdout: str) -> str | None:
    """Extract the workspace UUID from `new-workspace` output ('OK <uuid>')."""
    parts = (stdout or "").strip().split()
    if len(parts) >= 2 and parts[0] == "OK":
        return parts[1]
    return None


def list_workspaces_argv() -> list:
    return [CMUX_BIN, "--json", "list-workspaces"]


def run(argv: list) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True)


def live_workspaces() -> list:
    """Return the live cmux workspace list (empty if socket unreachable)."""
    import json

    out = run([CMUX_BIN, "--json", "list-workspaces"])
    try:
        ws = json.loads(out.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return ws if isinstance(ws, list) else ws.get("workspaces", ws)


def find_workspace_ref(workspaces: list, label: str) -> str | None:
    """Ref of the workspace whose glyph-stripped title equals label, else None."""
    target = strip_glyph(label)
    for w in workspaces:
        if strip_glyph(w.get("title", "")) == target:
            return w["ref"]
    return None


def is_running_ws(ws: dict) -> bool:
    """True if a workspace shows an active job — must never be auto-closed."""
    if ws.get("running") or ws.get("isRunning"):
        return True
    title = ws.get("processTitle") or ws.get("title") or ""
    if title.startswith("✳"):
        return True
    for entry in ws.get("statusEntries", []) or []:
        state = (entry.get("state") or entry.get("kind") or "").lower()
        if state in ("running", "needs_input", "needsinput"):
            return True
    return False


def mark_running(workspaces: list, running_titles: set) -> list:
    """Return workspaces with running=True set for any whose glyph-stripped
    title is in running_titles.

    The live socket `list-workspaces` does NOT expose running state (only title/
    ref/pinned), so running jobs must be detected from cmux's session JSON and
    overlaid here — otherwise reconcile_plan would close a busy workspace.
    """
    out = []
    for w in workspaces:
        w = dict(w)
        if strip_glyph(w.get("title", "")) in running_titles:
            w["running"] = True
        out.append(w)
    return out


def reconcile_plan(workspaces: list, wanted: set, protect: set) -> dict:
    """Pure converge-plan: given live workspaces and a wanted label set, decide
    which to keep, open, close, or skip (running). `protect` = labels never closed.

    Returns {keep: [refs], close: [refs], skip_running: [refs], open: [labels]}.
    """
    present = {strip_glyph(w.get("title", "")) for w in workspaces}
    keep, close, skip_running = [], [], []
    for w in workspaces:
        label = strip_glyph(w.get("title", ""))
        if label in wanted:
            keep.append(w["ref"])
        elif is_running_ws(w):
            skip_running.append(w["ref"])
        elif label in protect:
            continue  # protected: leave alone, neither keep-list nor close
        else:
            close.append(w["ref"])
    to_open = [lbl for lbl in wanted if lbl not in present]
    return {"keep": keep, "close": close, "skip_running": skip_running, "open": to_open}


def open_and_label(cwd: str, label: str) -> str | None:
    """Open (or focus) a workspace for label at cwd, backed by a tmux session.

    Idempotent: if a workspace with this label already exists, select it instead
    of creating a duplicate. Otherwise create + rename. Returns the ref.
    """
    existing = find_workspace_ref(live_workspaces(), label)
    if existing:
        run([CMUX_BIN, "select-workspace", "--workspace", existing])
        return existing
    res = run(open_workspace_argv(title=label, cwd=cwd))
    ref = parse_new_workspace_ref(res.stdout)
    if ref:
        run(rename_workspace_argv(label, ref=ref))
    return ref
