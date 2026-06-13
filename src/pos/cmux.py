import shlex
import subprocess

CMUX_BIN = "/Applications/cmux.app/Contents/Resources/bin/cmux"


def open_workspace_argv(title: str, cwd: str) -> list:
    """Open a new workspace whose shell starts in cwd (rename happens separately)."""
    command = f"cd {shlex.quote(cwd)} && exec ${{SHELL:-/bin/zsh}}"
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
