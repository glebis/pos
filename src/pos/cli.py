import json
import os
import subprocess
import sys
from pathlib import Path

from . import cc, cmux, completions, day, help as poshelp, projects, settings, solo, spread, status, tmuxify, yard
from .output import resolve_mode
from .label import GLYPHS, glyphed_title, strip_glyph
from .manifest import (
    expand_focus_members,
    focus_order,
    load_manifest,
    projects_by_focus,
    resolve_preset,
)
from .paths import resolve_path

DEFAULT_MANIFEST = "~/.config/personal-os/focus.toml"

USAGE = """pos — focus-aligned terminal cockpit

  pos                     list focuses
  pos <focus>             load a focus: open+pin its projects, close the rest
                          (dry-run unless --apply; same engine as `pos load`)
  pos p [name]            project index: list, or open project <name>
  pos i                   interactive TUI: browse focuses/projects, act by keypress
  pos cc <focus>          open a Claude Code workspace for <focus>; resumes its
                          conversation after a cmux crash / reboot (pos-cc wrapper)
  pos new <name> [path]   open a tmux-backed workspace (known project → its path)
  pos rename <old> <new>  rename a live workspace
  pos rm <name> [--force] close a live workspace (--force if not tmux-backed)
  pos where               print the current workspace + its tmux session
  pos solo [name]         UltraFocus: hide every workspace but one (the current
                          one, or [name] if given). Toggle; --off forces restore.
  pos tmuxify [--apply]   back workspaces with tmux so they survive close/restore.
                          Dry-run audit unless --apply; converts only idle shells.
  pos spread              fan every workspace out into its own dedicated window
  pos tile                spread, then grid the windows across the screen (if the
                          window_manager setting is aerospace; else spread only)
  pos gather              inverse of spread/tile: merge all windows back into one
  pos config [show|k v]   core settings (window_manager, tile_layout); bare = interactive
  pos completions [shell]  print a zsh/bash/fish completion script (default zsh)
  pos sort                reorder the current window: pinned workspaces to the top
  pos open <path>         open an ad-hoc workspace at <path>
  pos sidecar [url]       add a browser (url) or terminal sidecar to current workspace
  pos yard run <name> -- <cmd> | ls | attach <name> | kill <name>
  pos status [--json]     status across projects, grouped by focus
  pos day [--date YYYYMMDD] [--dry-run]
                          hybrid daily pin: focus contexts + today's active projects (from daily note)
  pos load <preset|focus|names...> [--apply] [--force]
                          converge the workspace: open+pin members, close the rest.
                          A focus name expands to its projects. Dry-run unless --apply.
                          NEVER closes: the tab you launched from, running jobs
                          (live tmux + cmux sidebar badges), or scratch.
                          --force ignores stale running badges when you've verified live.
  pos help [agents]       this usage; `--json` prints the machine-readable command
                          table; `pos help agents` prints the agent guide.
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

    # A preset's members stay literal (as authored); a bare focus name typed
    # directly expands to that focus's projects ("load my business projects").
    is_preset = len(names) == 1 and names[0] in m.presets
    members = resolve_preset(m, names)
    if not is_preset:
        members = expand_focus_members(m, members)
    unknown = [x for x in members if x not in m.focuses and x not in m.projects]
    if unknown:
        print(f"unknown member(s): {', '.join(unknown)}", file=sys.stderr)
        return 1

    wanted = {member for member in members}  # match by name (glyph-stripped) on live tabs
    ws = cmux.live_workspaces()
    # SAFETY: the live socket exposes no running-state, so layer in protection
    # before reconcile decides what to close. --force drops the running layers
    # (cmux persists STALE badges; use when you've verified live state yourself).
    # The launching/focused tab is ALWAYS guarded, even under --force — losing the
    # session you started from is the one unrecoverable mistake.
    guard = cmux.current_workspace_refs()
    cur = cmux.current_tmux_session()
    if cur:
        for w in ws:
            if cmux.tmux_session_for_title(w.get("title", "")) == cur:
                guard.add(w["ref"])
    if not force:
        ws = cmux.mark_running(ws, _running_titles())            # cmux sidebar badges
        ws = cmux.mark_running_tmux(ws, cmux.live_busy_sessions())  # live tmux jobs
    ws = cmux.mark_running_refs(ws, guard)                       # launching/focused tab
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
    if resolve_mode(rest) == "json":
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


def _cmd_completions(m, rest) -> int:
    """pos completions [zsh|bash|fish] — print a shell completion script."""
    shell = rest[0] if rest else "zsh"
    sc = completions.script(shell)
    if not sc:
        print(f"pos completions: unknown shell {shell!r} (zsh|bash|fish)", file=sys.stderr)
        return 1
    # hint to stderr so `pos completions zsh > _pos` yields a clean script
    # whose first line is `#compdef pos` (required for zsh autoload).
    print(completions.INSTALL_HINT[shell], file=sys.stderr)
    print(sc)
    return 0


def _cmd_list(m, rest) -> int:
    """pos __list <kind> — hidden: emit completion candidates, one per line."""
    kind = rest[0] if rest else ""
    if kind == "commands":
        print("\n".join(completions.COMMANDS))
    elif kind == "focuses":
        print("\n".join(m.focuses))
    elif kind == "projects":
        print("\n".join(m.projects))
    elif kind == "settings":
        print("\n".join(settings.DEFAULTS))
    elif kind == "workspaces":
        print("\n".join(strip_glyph(w.get("title", "")) for w in cmux.live_workspaces()))
    else:
        return 1
    return 0


def _cmd_config(m, rest, input_fn=input) -> int:
    """pos config              interactive: step through core settings
    pos config show          print current settings
    pos config <key> <value> set one setting non-interactively
    """
    if rest and rest[0] in ("show", "--show", "ls"):
        for k, v in settings.load().items():
            print(f"{k} = {v}")
        return 0
    if len(rest) >= 2:
        ok, msg = settings.set_value(rest[0], rest[1])
        print(msg if ok else f"pos config: {msg}", file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1
    # interactive walk
    print("pos config — Enter keeps the current value")
    for key in settings.DEFAULTS:
        cur = settings.load()[key]
        choices = settings.CHOICES.get(key)
        hint = f" ({'/'.join(choices)})" if choices else ""
        try:
            val = input_fn(f"  {key}{hint} [{cur}]: ").strip()
        except EOFError:
            val = ""
        if val:
            ok, msg = settings.set_value(key, val)
            if not ok:
                print(f"    {msg}", file=sys.stderr)
    print("saved: " + ", ".join(f"{k}={v}" for k, v in settings.load().items()))
    return 0


def _cmd_new(m, rest) -> int:
    """pos new <name> [path] — open a tmux-backed workspace. If <name> is a known
    project/focus, its manifest path + glyph are used; else path defaults to ~."""
    if not rest:
        print("usage: pos new <name> [path]", file=sys.stderr)
        return 1
    name = rest[0]
    glyph = ""
    if len(rest) > 1:
        cwd = str(Path(rest[1]).expanduser())
    elif name in m.projects or name in m.focuses:
        cwd = _cwd_for(m, name)
        mark = _label_for(m, name)[:1]
        glyph = mark if mark in GLYPHS else ""
    else:
        cwd = str(Path("~").expanduser())
    ref = projects.create(name, cwd, glyph)
    print(f"opened {strip_glyph(name)} at {cwd}" if ref else "pos new: failed to open", file=sys.stderr if not ref else sys.stdout)
    return 0 if ref else 1


def _cmd_rename(m, rest) -> int:
    """pos rename <old> <new> — rename a live workspace."""
    if len(rest) < 2:
        print("usage: pos rename <old> <new>", file=sys.stderr)
        return 1
    ref = projects.rename(rest[0], rest[1])
    if not ref:
        print(f"pos rename: no workspace labelled {rest[0]!r}", file=sys.stderr)
        return 1
    print(f"renamed {rest[0]} → {rest[1]}")
    return 0


def _cmd_rm(m, rest) -> int:
    """pos rm <name> [--force] — close a live workspace (refuses non-tmux without --force)."""
    args = [a for a in rest if not a.startswith("--")]
    if not args:
        print("usage: pos rm <name> [--force]", file=sys.stderr)
        return 1
    name = args[0]
    ref, status = projects.remove(name, force="--force" in rest)
    if status == "not-found":
        print(f"pos rm: no workspace labelled {name!r}", file=sys.stderr)
        return 1
    if status == "unbacked":
        print(f"pos rm: {name!r} has no live tmux session — closing it loses its state. "
              f"Re-run with --force to close anyway.", file=sys.stderr)
        return 1
    print(f"closed {strip_glyph(name)} (tmux session, if any, survives — reopen with `pos`)")
    return 0


def _cmd_where(m, rest) -> int:
    """pos where — print the current workspace and its tmux session."""
    win = cmux.window_workspaces()
    cur = next((w for w in win["workspaces"] if w.get("selected")), None)
    if not cur:
        print("pos where: no current workspace (socket unreachable?)", file=sys.stderr)
        return 1
    title = cur.get("title", "")
    # the session backing THIS workspace comes from its title; $TMUX would instead
    # be wherever `pos` was invoked from, which need not be the current workspace.
    sess = cmux.tmux_session_for_title(title)
    alive = cc.tmux_session_alive(sess) if sess else False
    print(f"workspace: {cur.get('ref')}  {title}")
    print(f"tmux:      {sess or '(none)'}{'  (not live)' if sess and not alive else ''}")
    here = cmux.current_tmux_session()
    if here and here != sess:
        print(f"(invoked from tmux session {here})")
    if solo.is_active():
        print("UltraFocus: ON (other workspaces parked — `pos solo` to restore)")
    return 0


def _cmd_tmuxify(m, rest) -> int:
    """pos tmuxify — back workspaces with tmux so they survive close/restore.
    Dry-run audit unless --apply; converts only safe idle shells."""
    apply = "--apply" in rest
    current, audits = tmuxify.gather()
    plan = tmuxify.build_plan(audits, current)

    backed = ", ".join(f"{strip_glyph(a['title'])}→{a['session']}" for a in plan["backed"])
    print(f"pos tmuxify  {'(APPLY)' if apply else '(dry-run)'}")
    print(f"  already tmux-backed ({len(plan['backed'])}): {backed or '(none)'}")
    print(f"  would convert ({len(plan['convert'])}):")
    for a in plan["convert"]:
        print(f"    {strip_glyph(a['title']):<22} {tmuxify.convert_command(a['title'])}")
    if plan["skipped"]:
        print(f"  skipped ({len(plan['skipped'])}):")
        for a in plan["skipped"]:
            print(f"    {strip_glyph(a['title']):<22} {a['reason']}")
    if not apply:
        print("\n(dry-run; pass --apply to convert the idle shells above.)")
        return 0
    n = tmuxify.apply(plan["convert"])
    print(f"\n  converted {n} workspace(s) to tmux-backed.")
    return 0


def _cmd_solo(m, rest) -> int:
    """pos solo [name] — UltraFocus: hide every workspace but one (toggle).

    With no name, keeps the currently-selected workspace. With a name, keeps that
    workspace instead — handy when driving pos from another workspace's shell.
    """
    name = next((a for a in rest if not a.startswith("-")), None)
    if "--off" in rest:
        return solo.restore()
    if "--on" in rest:
        return solo.engage(name) if not solo.is_active() else 0
    return solo.toggle(name)


def _cmd_cc(m, rest) -> int:
    """pos cc <focus> — open a Claude Code workspace for <focus> that resumes
    its conversation after a cmux crash or reboot."""
    if not rest:
        print("usage: pos cc <focus>", file=sys.stderr)
        return 1
    focus = rest[0]
    if focus not in m.focuses:
        print(f"unknown focus: {focus}", file=sys.stderr)
        return 1
    ref = cc.open_cc(focus=focus, cwd=_cwd_for(m, focus), glyph=m.focuses[focus].glyph)
    return 0 if ref else 1


def _cmd_open(m, rest) -> int:
    if not rest:
        print("usage: pos open <path>", file=sys.stderr)
        return 1
    path = Path(rest[0]).expanduser()
    cmux.open_and_label(cwd=str(path), label=path.name)
    return 0


def _cmd_sidecar(m, rest) -> int:
    """pos sidecar [url] [name] — add a browser (url) or terminal sidecar to the
    current workspace, naming its tab after the current folder (a numeric suffix
    disambiguates repeats). A non-url positional arg overrides the name."""
    url = next((a for a in rest if "://" in a), None)
    explicit = next((a for a in rest if "://" not in a and not a.startswith("-")), None)

    ws = cmux.current_workspace_ref()
    if not ws:
        print("pos sidecar: no current workspace (socket unreachable?)", file=sys.stderr)
        return 1

    existing = {s["title"] for s in cmux.workspace_surfaces(ws)}
    name = cmux.unique_sidecar_name(Path.cwd().name, existing, explicit)

    res = cmux.run(cmux.sidecar_argv(url, ws_ref=ws))
    surface = cmux.parse_new_surface_ref(res.stdout)
    if surface:
        cmux.run(cmux.rename_surface_tab_argv(ws, surface, name))
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


def dispatch(m, cmd, rest) -> int:
    if cmd in ("i", "interactive"):
        from . import tui
        return tui.run(m)
    if cmd in ("-h", "--help", "help"):
        if rest and rest[0] == "agents":
            print(poshelp.agents_doc())
        elif resolve_mode(rest) == "json":
            print(json.dumps(poshelp.render_json(), ensure_ascii=False))
        else:
            print(USAGE)
        return 0
    if cmd == "status":
        return _cmd_status(m, rest)
    if cmd == "p":
        return _cmd_p(m, rest)
    if cmd == "cc":
        return _cmd_cc(m, rest)
    if cmd == "config":
        return _cmd_config(m, rest)
    if cmd == "completions":
        return _cmd_completions(m, rest)
    if cmd == "__list":
        return _cmd_list(m, rest)
    if cmd == "new":
        return _cmd_new(m, rest)
    if cmd == "rename":
        return _cmd_rename(m, rest)
    if cmd == "rm":
        return _cmd_rm(m, rest)
    if cmd == "where":
        return _cmd_where(m, rest)
    if cmd == "solo":
        return _cmd_solo(m, rest)
    if cmd == "tmuxify":
        return _cmd_tmuxify(m, rest)
    if cmd == "spread":
        return spread.spread()
    if cmd == "tile":
        return 0 if spread.tile() >= 0 else 1
    if cmd == "gather":
        return 0 if spread.gather() >= 0 else 1
    if cmd == "sort":
        n = cmux.reorder_pinned_first()
        print(f"pos sort — pinned workspaces to top ({n} repositioned)." if n else "pos sort — already in order.")
        return 0
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
        # `pos business` == `pos load business` (focus expands to its projects)
        return _cmd_load(m, [cmd] + rest)

    print(f"unknown command: {cmd}\n\n{USAGE}", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    m = load_manifest(_manifest_path())

    if not argv:
        if resolve_mode([]) == "json":
            print(json.dumps(
                [{"name": f, "emoji": m.focuses[f].emoji, "tier": m.focuses[f].tier}
                 for f in focus_order(m)],
                ensure_ascii=False,
            ))
        else:
            for f in focus_order(m):
                fo = m.focuses[f]
                print(f"{fo.emoji} {f}  [{fo.tier}]")
        return 0

    cmd, rest = argv[0], argv[1:]
    return dispatch(m, cmd, rest)
