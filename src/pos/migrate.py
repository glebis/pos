"""Workspace migration helper — DRY-RUN by default.

Reads cmux's live workspace list and proposes how each maps onto the
focus.toml taxonomy. It NEVER closes a workspace that has a running job:
quitting/closing a running agent loses work (cmux jobs die on close).
"""
import json
import subprocess
import sys
from pathlib import Path

from .cmux import CMUX_BIN


def is_running(ws: dict) -> bool:
    """True if a workspace shows an active process — must never be auto-closed."""
    # cmux marks activity via statusEntries / a running flag / a process title
    # that starts with the running glyph "✳".
    if ws.get("running") or ws.get("isRunning"):
        return True
    title = (ws.get("processTitle") or ws.get("title") or "")
    if title.startswith("✳"):
        return True
    for entry in ws.get("statusEntries", []) or []:
        state = (entry.get("state") or entry.get("kind") or "").lower()
        if state in ("running", "needs_input", "needsinput"):
            return True
    return False


def ws_title(ws: dict) -> str:
    return ws.get("customTitle") or ws.get("processTitle") or ws.get("title") or "?"


# ── proposal logic (pure; matches a workspace's cwds onto the manifest) ──
import re

from .manifest import Manifest, focus_order
from .paths import resolve_path

_PATH_RE = re.compile(r"(~?/[\w./@-]+)")


def paths_from_title(title: str) -> list:
    """Extract filesystem-path-looking substrings from a workspace/pane title."""
    if not title:
        return []
    return _PATH_RE.findall(title)


def project_index(m: Manifest) -> dict:
    """Map resolved absolute project path -> project name."""
    out = {}
    for name, proj in m.projects.items():
        out[str(resolve_path(proj.path, m.projects_base))] = name
    return out


def classify(candidate_paths: list, m: Manifest) -> dict:
    """Classify a workspace by the projects/focuses its paths resolve to."""
    idx = project_index(m)
    focus_homes = {str(resolve_path(f.home, m.projects_base)): name for name, f in m.focuses.items()}
    projects, focuses = [], []
    for p in candidate_paths:
        ap = str(resolve_path(p, m.projects_base))
        if ap in idx and idx[ap] not in projects:
            projects.append(idx[ap])
        elif ap in focus_homes and focus_homes[ap] not in focuses:
            focuses.append(focus_homes[ap])
    if len(projects) == 1:
        kind = "project"
    elif len(projects) > 1:
        kind = "grab-bag"
    elif focuses:
        kind = "focus"
    else:
        kind = "unmatched"
    # the focus a single project belongs to
    target_focus = m.projects[projects[0]].focus if len(projects) == 1 else (focuses[0] if focuses else None)
    return {"kind": kind, "projects": projects, "focuses": focuses, "target_focus": target_focus}


def list_workspaces() -> list:
    out = subprocess.run([CMUX_BIN, "--json", "list-workspaces"], capture_output=True, text=True)
    try:
        data = json.loads(out.stdout or "[]")
    except json.JSONDecodeError:
        return []
    # cmux may wrap the list under a key; accept both shapes
    if isinstance(data, dict):
        for k in ("workspaces", "items", "result"):
            if isinstance(data.get(k), list):
                return data[k]
        return []
    return data


SESSION_JSON = "~/Library/Application Support/cmux/session-com.cmuxterm.app.json"


def _candidate_paths(ws: dict) -> list:
    paths = []
    if ws.get("currentDirectory"):
        paths.append(ws["currentDirectory"])
    for panel in ws.get("panels", []) or []:
        for key in ("title", "customTitle"):
            paths.extend(paths_from_title(panel.get(key) or ""))
    paths.extend(paths_from_title(ws.get("title") or ""))
    # de-dup, preserve order
    seen, out = set(), []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def propose_from_session(session_path, m: Manifest) -> list:
    """Build a concrete migration proposal from cmux's persisted session JSON."""
    with open(Path(session_path).expanduser()) as f:
        data = json.load(f)
    rows = []
    for win in data.get("windows", []):
        for ws in win.get("tabManager", {}).get("workspaces", []):
            cands = _candidate_paths(ws)
            verdict = classify(cands, m)
            rows.append({"title": ws_title(ws), "running": is_running(ws), **verdict})
    return rows


def _proposal_report(m: Manifest) -> int:
    rows = propose_from_session(SESSION_JSON, m)
    print(f"MIGRATION PROPOSAL — {len(rows)} workspace(s) (from cmux session JSON):\n")
    for r in rows:
        guard = " 🔴RUNNING" if r["running"] else ""
        if r["kind"] == "project":
            action = f"→ project '{r['projects'][0]}' (focus: {r['target_focus']})"
        elif r["kind"] == "grab-bag":
            action = f"→ SPLIT into projects {r['projects']} — open each via `pos p <name>`"
        elif r["kind"] == "focus":
            action = f"→ focus context '{r['focuses'][0]}'"
        else:
            action = "→ UNMATCHED (add to focus.toml or leave as ad-hoc)"
        print(f"  • {r['title']!r:<42}{guard}\n      {action}")
    print("\n(read-only proposal. No renames or closes performed.)")
    return 0


def main(argv) -> int:
    if "--proposal" in argv:
        from .cli import _manifest_path
        from .manifest import load_manifest
        return _proposal_report(load_manifest(_manifest_path()))
    apply = "--apply" in argv
    workspaces = list_workspaces()
    if not workspaces:
        print("no cmux workspaces found (is cmux running? socket reachable?)")
        return 0
    print(f"{'APPLY' if apply else 'DRY-RUN'}: {len(workspaces)} workspace(s)\n")
    for ws in workspaces:
        guard = " [RUNNING — will never auto-close]" if is_running(ws) else ""
        print(f"  • {ws_title(ws)!r}{guard}  → review against focus.toml")
    if not apply:
        print("\n(dry-run; pass --apply to act. Running-job workspaces are always skipped.)")
    else:
        print("\n(apply mode: this build only reports — destructive ops intentionally not implemented)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
