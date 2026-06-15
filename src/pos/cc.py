"""`pos cc <focus>` — a Claude Code workspace per focus, with crash/reboot resume.

Two cooperating pieces:

1. ``pos cc <focus>`` opens a tmux-backed cmux workspace whose pane runs the
   ``pos-cc`` wrapper (NOT bare ``claude``). The command is baked into
   ``tmux new-session`` at creation, so there is no send-to-surface race.

2. ``pos-cc`` (the ``wrapper_main`` console script) is the resume layer. It
   launches ``claude --continue`` when this cwd already has a stored
   conversation, else a fresh ``claude``. Crucially it runs claude as a CHILD
   (``subprocess.run``, never ``exec``) — tmux-resurrect's ``ps`` save strategy
   records the pane process's *child*, so claude must sit one level below the
   pane to be captured as ``claude``/``claude --continue``. If the wrapper
   exec'd, claude would BE the pane process and resurrect would instead capture
   claude's own children (the MCP servers) and never restore the conversation.

Recovery loop: resurrect saves the pane's child command -> on restore, the
``@resurrect-processes`` inline rule ``"~claude->pos-cc"`` routes it back through
``pos-cc``, which re-decides resume-or-fresh from the restored cwd. The cwd is
the key; no session-id bookkeeping. Caveat: ``--continue`` resumes the *most
recent* conversation in the cwd, so one focus == one cwd.
"""

import os
import shlex
import subprocess
import sys
from pathlib import Path

from .cmux import (
    CMUX_BIN,
    find_workspace_ref,
    live_workspaces,
    parse_new_workspace_ref,
    rename_tab_argv,
    rename_workspace_argv,
    run,
    session_name,
)
from .label import glyphed_title

CLAUDE_HOME = "~/.claude"


# ── resume detection (pure) ──────────────────────────────────────────────
def encode_project_dir(cwd: str) -> str:
    """Encode a cwd the way Claude names its session dir: every '/' -> '-'."""
    return str(Path(cwd)).replace("/", "-")


def claude_session_dir(cwd: str, claude_home: str | None = None) -> Path:
    home = Path(claude_home or CLAUDE_HOME).expanduser()
    return home / "projects" / encode_project_dir(cwd)


def has_prior_session(cwd: str, claude_home: str | None = None) -> bool:
    """True if Claude has at least one stored conversation for this cwd."""
    d = claude_session_dir(cwd, claude_home)
    try:
        return any(d.glob("*.jsonl"))
    except OSError:
        return False


def claude_argv(cwd: str, claude_home: str | None = None, extra=()) -> list:
    """argv to launch claude: resume the cwd's latest conversation, else fresh."""
    base = ["claude", "--continue"] if has_prior_session(cwd, claude_home) else ["claude"]
    return base + list(extra)


# ── workspace launch (pure argv builders) ────────────────────────────────
def cc_session_name(focus: str) -> str:
    """Stable tmux session name for a focus's Claude workspace: 'cc-<focus>'."""
    return "cc-" + session_name(focus)


def cc_launch_command(focus: str, cwd: str) -> str:
    """tmux command (baked into new-workspace) that attaches-or-creates the
    focus's Claude session and runs the resume-aware wrapper.

    `-A` makes re-opening idempotent (re-attach the live session); the wrapper
    (pos-cc), not bare claude, is the pane command so resume survives restarts.
    """
    sess = cc_session_name(focus)
    return f"tmux new-session -A -s {shlex.quote(sess)} -c {shlex.quote(cwd)} pos-cc"


def cc_open_argv(focus: str, cwd: str) -> list:
    return [CMUX_BIN, "new-workspace", "--command", cc_launch_command(focus, cwd)]


def cc_label(focus: str, glyph: str) -> str:
    """Glyphed workspace title, e.g. '∴ cc-brain'."""
    return glyphed_title(glyph, cc_session_name(focus))


# ── liveness (so a stale husk doesn't block relaunch) ────────────────────
def tmux_session_alive(session: str) -> bool:
    """True if a tmux session of this name currently exists."""
    return run(["tmux", "has-session", "-t", session]).returncode == 0


def cwd_collision(session: str, cwd: str) -> str | None:
    """Name of another live `cc-*` tmux session already running in `cwd`, if any.

    `claude --continue` resumes the *newest* conversation in a cwd, so two cc
    sessions sharing a cwd would resume each other's history. Several focuses in
    this vault legitimately share `~/Brains/brain`, so we warn rather than block.
    """
    out = run(["tmux", "list-panes", "-a", "-F", "#{session_name}\t#{pane_current_path}"])
    if out.returncode != 0:
        return None
    target = str(Path(cwd))
    for line in (out.stdout or "").splitlines():
        name, _, path = line.partition("\t")
        if name != session and name.startswith("cc-") and str(Path(path)) == target:
            return name
    return None


# ── side-effecting open (idempotent) ─────────────────────────────────────
def open_cc(focus: str, cwd: str, glyph: str) -> str | None:
    """Open (or focus) the focus's Claude workspace. Returns its ref, or None on
    failure (so the CLI can exit non-zero).

    Idempotent: an existing workspace with this label is selected, not
    duplicated — backed by `tmux new-session -A`, the live claude session is
    re-attached rather than restarted. If the backing tmux session has DIED
    (clean /quit or crash), the stale cmux workspace is closed and recreated so
    `pos cc` always lands you in a live, resume-aware Claude.
    """
    label = cc_label(focus, glyph)
    sess = cc_session_name(focus)

    other = cwd_collision(sess, cwd)
    if other:
        print(
            f"warning: {other} is already running Claude in {cwd}; "
            f"--continue resumes the newest conversation there, so {sess} will share its history.",
            file=sys.stderr,
        )

    existing = find_workspace_ref(live_workspaces(), label)
    if existing:
        if tmux_session_alive(sess):
            res = run([CMUX_BIN, "select-workspace", "--workspace", existing])
            return existing if res.returncode == 0 else None
        # Stale husk: cmux workspace outlived its tmux session. Recreate it.
        run([CMUX_BIN, "close-workspace", "--workspace", existing])

    res = run(cc_open_argv(focus, cwd))
    if res.returncode != 0:
        print(f"pos cc: cmux new-workspace failed: {res.stderr.strip()}", file=sys.stderr)
        return None
    ref = parse_new_workspace_ref(res.stdout)
    if not ref:
        print(f"pos cc: could not parse new workspace ref from: {res.stdout.strip()!r}", file=sys.stderr)
        return None
    run(rename_workspace_argv(label, ref=ref))  # sidebar title
    run(rename_tab_argv(label, ref=ref))        # inner tab bar
    run([CMUX_BIN, "select-workspace", "--workspace", ref])
    return ref


# ── pos-cc console script (the resume wrapper) ───────────────────────────
def wrapper_main(argv=None) -> int:
    """Entry point for the `pos-cc` command run inside the tmux pane.

    Runs claude as a CHILD (subprocess.run, NOT exec) — do not "simplify" this
    to os.execvp: resurrect captures the pane process's child, so claude must
    remain a child to be saved as `claude`/`claude --continue` and restored.
    """
    argv = sys.argv[1:] if argv is None else list(argv)
    cmd = claude_argv(os.getcwd(), extra=argv)
    return subprocess.run(cmd).returncode
