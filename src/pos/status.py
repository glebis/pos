from concurrent.futures import ThreadPoolExecutor

from .git import git_state
from .manifest import Manifest, focus_order, projects_by_focus
from .paths import resolve_path


def build_status(m: Manifest, git_fn=None) -> list:
    # Resolve git_fn at call time (not as a def-time default) so that
    # monkeypatching pos.status.git_state takes effect.
    if git_fn is None:
        git_fn = git_state

    # Flatten to (focus, project, path) in display order first, then fan the
    # git probes out across a thread pool: each is an I/O-bound subprocess, so
    # they run concurrently instead of serially (~10x on a multi-repo manifest).
    # executor.map preserves input order, so rows stay grouped/ordered.
    grouped = projects_by_focus(m)
    items = [
        (focus, proj_name, resolve_path(m.projects[proj_name].path, m.projects_base))
        for focus in focus_order(m)
        for proj_name in grouped.get(focus, [])
    ]
    if not items:
        return []

    with ThreadPoolExecutor(max_workers=min(len(items), 32)) as pool:
        states = pool.map(lambda it: git_fn(it[2]), items)

    return [
        {
            "focus": focus,
            "project": proj_name,
            "path": str(path),
            "branch": st["branch"],
            "dirty": st["dirty"],
        }
        for (focus, proj_name, path), st in zip(items, states)
    ]
