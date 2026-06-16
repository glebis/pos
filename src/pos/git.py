import subprocess
from pathlib import Path


def git_state(path: Path) -> dict:
    """Branch + dirtiness of a repo in a single git invocation.

    `git status --porcelain --branch` emits a leading `## <branch>` header
    (covering unborn branches via `## No commits yet on <branch>` and detached
    HEAD via `## HEAD (no branch)`) followed by one line per change. One spawn
    gives us both signals; a non-zero exit means the path isn't a work tree.
    """
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--branch"],
        cwd=str(path),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return {"branch": None, "dirty": False}

    lines = proc.stdout.splitlines()
    header = lines[0][3:] if lines and lines[0].startswith("## ") else ""
    dirty = any(line.strip() for line in lines[1:])

    if header.startswith("No commits yet on "):
        branch = header[len("No commits yet on ") :] or None
    elif header.startswith("HEAD ("):  # detached HEAD: '## HEAD (no branch)'
        branch = None
    else:
        branch = header.split("...", 1)[0] or None

    return {"branch": branch, "dirty": dirty}
