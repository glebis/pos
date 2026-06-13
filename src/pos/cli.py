import json
import os
import subprocess
import sys
from pathlib import Path

from . import cmux, day, status, yard
from .label import glyphed_title
from .manifest import focus_order, load_manifest, projects_by_focus
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
"""


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
    if cmd in m.focuses:
        return _cmd_focus(m, cmd)

    print(f"unknown command: {cmd}\n\n{USAGE}", file=sys.stderr)
    return 1
