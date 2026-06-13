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


def open_and_label(cwd: str, label: str) -> str | None:
    """Create a workspace at cwd and rename THAT workspace to label.

    Captures the new workspace's ref from `new-workspace` output and targets
    the rename at it explicitly (renaming without a ref hits the wrong/current
    workspace). Returns the ref, or None if creation failed.
    """
    res = run(open_workspace_argv(title=label, cwd=cwd))
    ref = parse_new_workspace_ref(res.stdout)
    if ref:
        run(rename_workspace_argv(label, ref=ref))
    return ref
