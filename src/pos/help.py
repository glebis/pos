"""Machine-readable command registry — the agent-facing view of `pos`.

`render_json()` is the structured source an agent reads (via `pos help --json`,
or any piped `pos help`). The human view stays the curated USAGE string in
cli.py; tests keep the two in sync so they never drift.
"""

# name, synopsis, args, example. `name` must match the dispatch arm in cli.main
# AND appear in cli.USAGE (both asserted by tests/test_help.py).
COMMANDS = [
    {
        "name": "p",
        "synopsis": "Project index: list all, or open project <name>.",
        "args": "[name]",
        "example": "pos p cenno",
    },
    {
        "name": "i",
        "synopsis": "Interactive TUI: browse focuses/projects/sessions and act with one keypress.",
        "args": "",
        "example": "pos i",
    },
    {
        "name": "cc",
        "synopsis": "Open a Claude Code workspace for <focus>; resumes its conversation after a cmux crash/reboot.",
        "args": "<focus>",
        "example": "pos cc business",
    },
    {
        "name": "new",
        "synopsis": "Open a tmux-backed workspace (a known project/focus uses its path + glyph).",
        "args": "<name> [path]",
        "example": "pos new meta",
    },
    {
        "name": "rename",
        "synopsis": "Rename a live workspace.",
        "args": "<old> <new>",
        "example": "pos rename meta meta-work",
    },
    {
        "name": "rm",
        "synopsis": "Close a live workspace (--force if it isn't tmux-backed).",
        "args": "<name> [--force]",
        "example": "pos rm meta",
    },
    {
        "name": "where",
        "synopsis": "Print the current workspace and its backing tmux session.",
        "args": "",
        "example": "pos where",
    },
    {
        "name": "solo",
        "synopsis": "UltraFocus: hide every workspace but one — the current one, or [name] if given (toggle; --off forces restore).",
        "args": "[name] [--off]",
        "example": "pos solo feature-factory",
    },
    {
        "name": "tmuxify",
        "synopsis": "Back idle workspaces with tmux so they survive close/restore (dry-run unless --apply).",
        "args": "[--apply]",
        "example": "pos tmuxify --apply",
    },
    {
        "name": "spread",
        "synopsis": "Fan every workspace out into its own dedicated window.",
        "args": "",
        "example": "pos spread",
    },
    {
        "name": "tile",
        "synopsis": "Spread, then grid the windows across the screen (aerospace window_manager only).",
        "args": "",
        "example": "pos tile",
    },
    {
        "name": "gather",
        "synopsis": "Inverse of spread/tile: merge all windows back into one.",
        "args": "",
        "example": "pos gather",
    },
    {
        "name": "sort",
        "synopsis": "Reorder the current window: pinned workspaces to the top.",
        "args": "",
        "example": "pos sort",
    },
    {
        "name": "open",
        "synopsis": "Open an ad-hoc workspace at <path>.",
        "args": "<path>",
        "example": "pos open ~/scratch",
    },
    {
        "name": "sidecar",
        "synopsis": "Add a browser (url) or terminal sidecar to the current workspace.",
        "args": "[url]",
        "example": "pos sidecar https://localhost:3000",
    },
    {
        "name": "config",
        "synopsis": "Core settings (window_manager, tile_layout); bare opens an interactive editor.",
        "args": "[show | <key> <value>]",
        "example": "pos config window_manager aerospace",
    },
    {
        "name": "completions",
        "synopsis": "Print a zsh/bash/fish shell-completion script.",
        "args": "[zsh|bash|fish]",
        "example": "pos completions zsh",
    },
    {
        "name": "yard",
        "synopsis": "Run/list/attach/kill detached background jobs.",
        "args": "run <name> -- <cmd> | ls | attach <name> | kill <name>",
        "example": "pos yard run crawl -- firecrawl go",
    },
    {
        "name": "status",
        "synopsis": "Git status across projects, grouped by focus. JSON when piped.",
        "args": "[--json | --human]",
        "example": "pos status --json",
    },
    {
        "name": "day",
        "synopsis": "Hybrid daily pin: focus contexts + today's active projects (from the daily note).",
        "args": "[--date YYYYMMDD] [--dry-run]",
        "example": "pos day --dry-run",
    },
    {
        "name": "load",
        "synopsis": "Converge the workspace: open+pin members, close the rest. A focus expands to its projects.",
        "args": "<preset|focus|names...> [--apply] [--force]",
        "example": "pos load revenue-sprint --apply",
    },
    {
        "name": "help",
        "synopsis": "Show usage. JSON command table when piped or with --json; `pos help agents` for the agent guide.",
        "args": "[agents] [--json | --human]",
        "example": "pos help --json",
    },
]


def render_json() -> list:
    """Return the command registry as a list of plain dicts (JSON-ready)."""
    return [dict(c) for c in COMMANDS]


def agents_doc() -> str:
    """Mental model + recipes for an agent driving `pos`."""
    return """pos — agent guide

MENTAL MODEL
  Two namespaces in the manifest (~/.config/personal-os/focus.toml):
    - focuses  : stable horizons (business, play, brain, health, life, meta).
                 Each has an emoji + a single-glyph icon prefixed to its tabs.
    - projects : concrete repos, each belongs to one focus.
    - presets  : named member lists for `pos load`.
  Live workspaces are cmux tabs; tmux-backed ones survive close/reboot.

OUTPUT FOR AGENTS
  pos auto-detects the terminal: piped/captured output is JSON, a real TTY gets
  pretty text. So when you (an agent) run `pos status` or `pos`, you already get
  JSON — no flag needed. Force it either way with --json / --human.

DISCOVERY (machine-readable)
  pos help --json        full command table (name, synopsis, args, example)
  pos status --json      git state per project, grouped by focus
  pos __list commands    bare command names (also: focuses | projects | live | settings)

COMMON RECIPES
  Open a project:           pos p <project>
  Open a CC workspace:      pos cc <focus>
  New scratch workspace:    pos new <name> [path]
  Focus down to a preset:   pos load <preset> --apply
  See what's dirty:         pos status --json | jq '.[] | select(.dirty)'
  Where am I:               pos where
"""
