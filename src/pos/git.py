import subprocess
from pathlib import Path


def git_state(path: Path) -> dict:
    def _git(*args):
        return subprocess.run(
            ["git", *args], cwd=str(path), capture_output=True, text=True
        )

    head = _git("rev-parse", "--abbrev-ref", "HEAD")
    if head.returncode != 0:
        return {"branch": None, "dirty": False}
    branch = head.stdout.strip() or None
    status = _git("status", "--porcelain")
    dirty = bool(status.stdout.strip())
    return {"branch": branch, "dirty": dirty}
