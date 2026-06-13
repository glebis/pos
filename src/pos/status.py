from .git import git_state
from .manifest import Manifest, focus_order, projects_by_focus
from .paths import resolve_path


def build_status(m: Manifest, git_fn=None) -> list:
    # Resolve git_fn at call time (not as a def-time default) so that
    # monkeypatching pos.status.git_state takes effect.
    if git_fn is None:
        git_fn = git_state
    rows = []
    grouped = projects_by_focus(m)
    for focus in focus_order(m):
        for proj_name in grouped.get(focus, []):
            proj = m.projects[proj_name]
            path = resolve_path(proj.path, m.projects_base)
            st = git_fn(path)
            rows.append(
                {
                    "focus": focus,
                    "project": proj_name,
                    "path": str(path),
                    "branch": st["branch"],
                    "dirty": st["dirty"],
                }
            )
    return rows
