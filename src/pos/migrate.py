"""Workspace migration helper — DRY-RUN by default.

Reads cmux's live workspace list and proposes how each maps onto the
focus.toml taxonomy. It NEVER closes a workspace that has a running job:
quitting/closing a running agent loses work (cmux jobs die on close).
"""
import json
import subprocess
import sys

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


def main(argv) -> int:
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
