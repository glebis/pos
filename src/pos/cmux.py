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


def rename_workspace_argv(title: str) -> list:
    return [CMUX_BIN, "rename-workspace", title]


def list_workspaces_argv() -> list:
    return [CMUX_BIN, "--json", "list-workspaces"]


def run(argv: list) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True)
