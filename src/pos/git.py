import subprocess
from pathlib import Path


def git_state(path: Path) -> dict:
    def _git(*args):
        return subprocess.run(
            ["git", *args], cwd=str(path), capture_output=True, text=True
        )

    # Detect a work tree without relying on HEAD resolving (an unborn branch
    # — repo created, nothing committed — has no resolvable HEAD but is still
    # a repo that can be dirty with untracked files).
    inside = _git("rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return {"branch": None, "dirty": False}
    # branch --show-current returns the (possibly unborn) branch name.
    branch = _git("branch", "--show-current").stdout.strip() or None
    dirty = bool(_git("status", "--porcelain").stdout.strip())
    return {"branch": branch, "dirty": dirty}
