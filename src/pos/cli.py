import json
import os
import subprocess
import sys
from pathlib import Path

from . import cmux, day, status, yard
from .label import glyphed_title
from .manifest import focus_order, load_manifest, projects_by_focus, resolve_preset
from .paths import resolve_path

DEFAULT_MANIFEST = "~/.config/personal-os/focus.toml"

USAGE = """pos — focus-aligned terminal cockpit

  pos                     list focuses
  pos <focus>             open/focus a focus context (business, play, brain, health, life)
  pos p [name]            project index: list, or open project <name>
  pos open <path>         open an ad-hoc workspace at <path>
  pos sidecar [url]       add a browser (url) or terminal sidecar to current workspace
  pos yard run <name> -- <cmd> | ls | attach <name> | kill <name>
  pos status [--json]     status across projects, grouped by focus
  pos day [--date YYYYMMDD] [--dry-run]
                          hybrid daily pin: focus contexts + today's active projects (from daily note)
  pos load <preset|names...> [--apply] [--force]
                          converge workspace to a preset: open+pin members, close the rest
                          (dry-run unless --apply; never closes running jobs or scratch;
                           --force ignores stale running badges when you've verified live)
"""

PROTECTED = {"scratch"}  # never auto-closed by `pos load`


def _running_titles() -> set:
    """Glyph-stripped titles of workspaces with a running job (from session JSON)."""
    from .label import strip_glyph
    from .migrate import is_running, propose_from_session, SESSION_JSON, ws_title
    import json
    from pathlib import Path

    try:
        with open(Path(SESSION_JSON).expanduser()) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return set()
    out = set()
    for win in data.get("windows", []):
        for w in win.get("tabManager", {}).get("workspaces", []):
            if is_running(w):
                out.add(strip_glyph(ws_title(w)))
    return out


def _label_for(m, member: str) -> str:
    """Glyphed label for a focus or project member name."""
    if member in m.focuses:
        return glyphed_title(m.focuses[member].glyph, member)
    if member in m.projects:
        foc = m.projects[member].focus
        glyph = m.focuses[foc].glyph if foc in m.focuses else ""
        return glyphed_title(glyph, member)
    return member


def _cwd_for(m, member: str) -> str:
    if member in m.focuses:
        return str(resolve_path(m.focuses[member].home, m.projects_base))
    if member in m.projects:
        return str(resolve_path(m.projects[member].path, m.projects_base))
    return str(Path("~").expanduser())


def _cmd_load(m, rest) -> int:
    apply = "--apply" in rest
    force = "--force" in rest  # ignore stale running-state badges (verified live)
    names = [a for a in rest if not a.startswith("--")]
    if not names:
        if m.presets:
            print("presets:")
            for name, members in m.presets.items():
                print(f"  {name}: {', '.join(members)}")
        else:
            print("usage: pos load <preset|names...> [--apply]")
        return 0

    members = resolve_preset(m, names)
    unknown = [x for x in members if x not in m.focuses and x not in m.projects]
    if unknown:
        print(f"unknown member(s): {', '.join(unknown)}", file=sys.stderr)
        return 1

    wanted = {member for member in members}  # match by name (glyph-stripped) on live tabs
    ws = cmux.live_workspaces()
    # SAFETY: live socket has no running-state; overlay it from session JSON so
    # reconcile never closes a workspace with a running job. --force skips this
    # (cmux persists STALE badges; use when you've verified live state yourself).
    if not force:
        ws = cmux.mark_running(ws, _running_titles())
    plan = cmux.reconcile_plan(ws, wanted=wanted, protect=PROTECTED)

    ref_title = {w["ref"]: w["title"] for w in ws}
    print(f"pos load: {', '.join(members)}  {'(APPLY)' if apply else '(dry-run)'}")
    print(f"  open+pin: {', '.join(members)}")
    if plan["open"]:
        print(f"    └ to create: {', '.join(sorted(plan['open']))}")
    print(f"  close: {', '.join(ref_title[r] for r in plan['close']) or '(none)'}")
    if plan["skip_running"]:
        print(f"  skip (running): {', '.join(ref_title[r] for r in plan['skip_running'])}")

    if not apply:
        print("\n(dry-run; pass --apply to converge. Running jobs + scratch are never closed.)")
        return 0

    # 1. open/focus + pin every member (tmux-backed, idempotent)
    for member in members:
        ref = cmux.open_and_label(cwd=_cwd_for(m, member), label=_label_for(m, member))
        if ref:
            cmux.run([cmux.CMUX_BIN, "workspace-action", "--workspace", ref, "--action", "pin"])
    # 2. close the rest (unpin first so closing pinned ones is clean)
    for ref in plan["close"]:
        cmux.run([cmux.CMUX_BIN, "workspace-action", "--workspace", ref, "--action", "unpin"])
        cmux.run([cmux.CMUX_BIN, "close-workspace", "--workspace", ref])
    print(f"\n  converged: {len(members)} member(s) open+pinned, {len(plan['close'])} closed, {len(plan['skip_running'])} running kept.")
    return 0


def _manifest_path() -> Path:
    return Path(os.environ.get("POS_MANIFEST", DEFAULT_MANIFEST)).expanduser()


def _cmd_status(m, rest) -> int:
    rows = status.build_status(m)
    if "--json" in rest:
        print(json.dumps(rows, ensure_ascii=False))
    else:
        for r in rows:
            flag = "*" if r["dirty"] else " "
            print(f"{r['focus']:>9} · {r['project']:<24} {r['branch'] or '-':<14}{flag}")
    return 0


def _cmd_p(m, rest) -> int:
    if not rest:
        grouped = projects_by_focus(m)
        for f in focus_order(m):
            print(f"{m.focuses[f].emoji} {f}")
            for proj in grouped.get(f, []):
                print(f"    {proj}")
        return 0
    name = rest[0]
    if name not in m.projects:
        print(f"unknown project: {name}", file=sys.stderr)
        return 1
    proj = m.projects[name]
    path = resolve_path(proj.path, m.projects_base)
    glyph = m.focuses[proj.focus].glyph if proj.focus in m.focuses else ""
    cmux.open_and_label(cwd=str(path), label=glyphed_title(glyph, name))
    return 0


def _cmd_open(m, rest) -> int:
    if not rest:
        print("usage: pos open <path>", file=sys.stderr)
        return 1
    path = Path(rest[0]).expanduser()
    cmux.open_and_label(cwd=str(path), label=path.name)
    return 0


def _cmd_sidecar(m, rest) -> int:
    target = rest[0] if rest else None
    url = target if (target and "://" in target) else None
    cmux.run(cmux.sidecar_argv(url))
    return 0


def _cmd_yard(m, rest) -> int:
    if not rest:
        print("usage: pos yard run|ls|attach|kill ...", file=sys.stderr)
        return 1
    action = rest[0]
    if action == "run":
        # pos yard run <name> -- <cmd...>   (the -- is optional)
        args = rest[1:]
        if "--" in args:
            sep = args.index("--")
            # require exactly one token (the name) before --, and a non-empty command after
            if sep != 1 or sep + 1 >= len(args):
                print("usage: pos yard run <name> -- <cmd>", file=sys.stderr)
                return 1
            name, command = args[0], " ".join(args[sep + 1 :])
        elif len(args) >= 2:
            name, command = args[0], " ".join(args[1:])
        else:
            print("usage: pos yard run <name> -- <cmd>", file=sys.stderr)
            return 1
        yard.run(name, command)
        return 0
    if action == "ls":
        subprocess.run(yard.list_argv())
        return 0
    if action in ("attach", "kill") and len(rest) >= 2:
        argv = yard.attach_argv(rest[1]) if action == "attach" else yard.kill_argv(rest[1])
        subprocess.run(argv)
        return 0
    print(f"usage: pos yard run|ls|attach|kill ... (got {action!r})", file=sys.stderr)
    return 1


def _cmd_day(m, rest) -> int:
    from datetime import datetime

    date_str = None
    if "--date" in rest:
        date_str = rest[rest.index("--date") + 1]
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    dry = "--dry-run" in rest

    daily_text = day.read_daily(date_str)
    plan = day.build_pin_plan(m, daily_text)
    # titles to pin: focus context names + active project names (glyph-stripped match)
    wanted = set(plan["focuses"]) | set(plan["projects"])

    print(f"pos day {date_str} — hybrid pin plan")
    print(f"  focuses (spine): {', '.join(plan['focuses'])}")
    print(f"  active projects: {', '.join(plan['projects']) or '(none found in daily note)'}")
    if dry:
        print("\n(dry-run; pass without --dry-run to pin)")
        return 0
    pinned = day._pin_workspace_by_title(wanted)  # unpins all others first
    print(f"\n  (unpinned everything else first)")
    print(f"  pinned {len(pinned)} live workspace(s): {', '.join(pinned) or '(none matched open tabs)'}")
    from .label import strip_glyph

    missing = wanted - {strip_glyph(t) for t in pinned}
    if missing:
        print(f"  not open (open via `pos`): {', '.join(sorted(missing))}")
    return 0


def _cmd_focus(m, focus) -> int:
    fo = m.focuses[focus]
    cmux.open_and_label(cwd=str(resolve_path(fo.home, m.projects_base)), label=glyphed_title(fo.glyph, focus))
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    m = load_manifest(_manifest_path())

    if not argv:
        for f in focus_order(m):
            fo = m.focuses[f]
            print(f"{fo.emoji} {f}  [{fo.tier}]")
        return 0

    cmd, rest = argv[0], argv[1:]

    if cmd in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    if cmd == "status":
        return _cmd_status(m, rest)
    if cmd == "p":
        return _cmd_p(m, rest)
    if cmd == "open":
        return _cmd_open(m, rest)
    if cmd == "sidecar":
        return _cmd_sidecar(m, rest)
    if cmd == "yard":
        return _cmd_yard(m, rest)
    if cmd == "day":
        return _cmd_day(m, rest)
    if cmd == "load":
        return _cmd_load(m, rest)
    if cmd in m.focuses:
        return _cmd_focus(m, cmd)

    print(f"unknown command: {cmd}\n\n{USAGE}", file=sys.stderr)
    return 1
