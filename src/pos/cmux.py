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


def rename_tab_argv(title: str, ref: str) -> list:
    """Rename the INNER tab bar of a workspace (separate from the sidebar title).

    cmux titles a new tab with its launch command (e.g. 'tmux new-session …');
    setting a custom tab title here is what makes the tab read 'cenno' instead.
    """
    return [CMUX_BIN, "rename-tab", "--workspace", ref, title]


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


def current_window_id() -> str | None:
    """UUID of the window the socket considers current, else None."""
    out = run([CMUX_BIN, "current-window"])
    wid = (out.stdout or "").strip().split()[0] if out.stdout else ""
    return wid or None


def window_workspaces() -> dict:
    """Workspaces in the CURRENT window (list-workspaces is window-scoped).

    Returns {window_id, workspaces:[{id,ref,title,selected,pinned}]}; empty on
    socket failure. Uses `--id-format both` so each workspace carries its stable
    UUID (`id`) for state that must survive across separate `pos` invocations.
    """
    import json

    out = run([CMUX_BIN, "--json", "--id-format", "both", "list-workspaces"])
    try:
        data = json.loads(out.stdout or "{}")
    except json.JSONDecodeError:
        return {"window_id": None, "workspaces": []}
    return {
        "window_id": data.get("window_id") or data.get("window_ref"),
        "workspaces": data.get("workspaces", []),
    }


def parse_ok_uuid(stdout: str) -> str | None:
    """Extract the UUID from an `OK <uuid>` reply (e.g. new-window)."""
    parts = (stdout or "").strip().split()
    return parts[1] if len(parts) >= 2 and parts[0] == "OK" else None


def parse_windows(text: str) -> list:
    """Parse `list-windows` lines into [{id, selected_workspace, count, selected}].

    A line looks like: `* 0: <uuid> selected_workspace=<uuid> workspaces=11`
    (the leading `*` marks the current window).
    """
    out = []
    for line in (text or "").splitlines():
        s = line.strip()
        sel = s.startswith("*")
        s = s.lstrip("* ")
        m = re.match(r"\d+:\s+(\S+)\s+selected_workspace=(\S+)\s+workspaces=(\d+)", s)
        if m:
            out.append({"id": m.group(1), "selected_workspace": m.group(2),
                        "count": int(m.group(3)), "selected": sel})
    return out


def list_windows() -> list:
    return parse_windows(run([CMUX_BIN, "list-windows"]).stdout or "")


def pinned_first_order(workspaces: list) -> list:
    """Refs of `workspaces` reordered so pinned ones lead, each group stable."""
    pinned = [w["ref"] for w in workspaces if w.get("pinned")]
    rest = [w["ref"] for w in workspaces if not w.get("pinned")]
    return pinned + rest


def reorder_pinned_first() -> int:
    """Reorder the current window so pinned workspaces sit at the top. Returns the
    number of moves issued (0 if already in order)."""
    ws = window_workspaces()["workspaces"]
    desired = pinned_first_order(ws)
    current = [w["ref"] for w in ws]
    if desired == current:
        return 0
    for i, ref in enumerate(desired):
        run([CMUX_BIN, "reorder-workspace", "--workspace", ref, "--index", str(i)])
    return len(desired)


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
        run(rename_tab_argv(label, ref=existing))  # normalize a stale inner tab title
        return existing
    res = run(open_workspace_argv(title=label, cwd=cwd))
    ref = parse_new_workspace_ref(res.stdout)
    if ref:
        run(rename_workspace_argv(label, ref=ref))  # sidebar title
        run(rename_tab_argv(label, ref=ref))        # inner tab bar
    return ref


# ── live running-state protection (so `pos load` never closes a busy tab) ──
# Shells that mean "idle prompt"; anything else in the foreground = a live job.
SHELL_CMDS = {"zsh", "bash", "sh", "fish", "-zsh", "-bash", "-sh", "login", "tmux"}


def tmux_session_for_title(title: str) -> str | None:
    """Best-effort tmux session name that a workspace title maps to.

    Handles pos's tmux-backed tabs (glyphed label, e.g. '∴ brain' -> 'brain',
    '◆ unknowing.community' -> 'unknowing-community') AND raw attach/new-session
    command titles ('tmux attach-session -t Exploration' -> 'Exploration').
    """
    m = re.search(r"-[ts]\s+(\S+)", title)
    if m:
        return m.group(1)
    return session_name(title) or None


def busy_sessions_from_panes(lines) -> set:
    """Given '<session> <foreground-cmd>' lines, return the sessions running a
    non-shell job. Pure — `live_busy_sessions` feeds it real `tmux` output."""
    busy = set()
    for line in lines:
        parts = line.strip().split(None, 1)
        if len(parts) < 2:
            continue
        sess, cmd = parts[0], parts[1].strip()
        if cmd not in SHELL_CMDS:
            busy.add(sess)
    return busy


def live_busy_sessions() -> set:
    """tmux sessions with a live (non-shell) foreground process, queried live.

    This is the reliable running signal — the cmux socket exposes none, and
    cmux's persisted badges go stale. Empty set if tmux is unreachable."""
    out = run(["tmux", "list-panes", "-a", "-F", "#{session_name} #{pane_current_command}"])
    if out.returncode != 0:
        return set()
    return busy_sessions_from_panes((out.stdout or "").splitlines())


def mark_running_tmux(workspaces: list, busy_sessions: set) -> list:
    """Overlay running=True on workspaces whose backing tmux session is busy."""
    out = []
    for w in workspaces:
        w = dict(w)
        sess = tmux_session_for_title(w.get("title", ""))
        if sess and sess in busy_sessions:
            w["running"] = True
        out.append(w)
    return out


def mark_running_refs(workspaces: list, refs: set) -> list:
    """Overlay running=True on workspaces whose ref is in `refs` (the launching
    / focused tab — never close the session an operation was started from)."""
    out = []
    for w in workspaces:
        w = dict(w)
        if w.get("ref") in refs:
            w["running"] = True
        out.append(w)
    return out


def current_workspace_refs() -> set:
    """Refs of the workspace the operation was launched from — the caller pane
    and the focused tab (per `cmux identify`). These must never be closed."""
    import json

    refs = set()
    out = run([CMUX_BIN, "--json", "identify"])
    try:
        data = json.loads(out.stdout or "{}")
    except json.JSONDecodeError:
        return refs
    for key in ("caller", "focused"):
        node = data.get(key)
        if isinstance(node, dict) and node.get("workspace_ref"):
            refs.add(node["workspace_ref"])
    return refs


def current_tmux_session() -> str | None:
    """Name of the tmux session this process runs in ($TMUX), else None."""
    import os

    if not os.environ.get("TMUX"):
        return None
    out = run(["tmux", "display-message", "-p", "#{session_name}"])
    name = (out.stdout or "").strip()
    return name or None
