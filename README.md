# pos — focus-aligned terminal cockpit

`pos` is a thin CLI that drives **cmux** (`cmuxterm.app` — an interactive terminal multiplexer / window manager, built on [ghostty](https://github.com/ghostty-org/ghostty)) on top of [**tmux**](https://github.com/tmux/tmux/wiki), so your terminal workspaces mirror what you're actually focused on. It turns a pile of terminal tabs into a focus-organized cockpit: open projects by focus area, fan them across the screen, hide everything but the one thing, and keep [Claude Code](https://claude.com/claude-code) sessions alive across crashes and reboots.

- **Repo:** <https://github.com/glebis/pos>
- **Runtime:** Python ≥ 3.12, **stdlib-only** (uv-managed). macOS.
- **Status:** 146 tests green · v0.1.0

> Built for a personal setup, but the patterns (cmux socket scripting, tmux-backed durability, resume-aware Claude launch) are reusable.

## Contents

- [Concept](#concept)
- [Install](#install)
- [Commands](#commands)
  - [Focus & projects](#focus--projects)
  - [Claude Code, with resume](#claude-code-with-resume)
  - [Window layout](#window-layout)
  - [Workspace CRUD](#workspace-crud)
  - [Durability & config](#durability--config)
- [Claude session recovery](#claude-session-recovery)
- [Screen tiling with AeroSpace](#screen-tiling-with-aerospace)
- [Shell completion](#shell-completion)
- [Settings](#settings)
- [Development](#development)
- [Related](#related)
- [License](#license)

## Concept

```
┌─ cmux = COCKPIT ────────────────┐     ┌─ tmux = ENGINE ROOM ──────────┐
│ interactive, focus-organized     │  →  │ detached sessions that must    │
│ workspaces. You live here.       │     │ outlive the GUI (jobs, Claude).│
└──────────────────────────────────┘     └────────────────────────────────┘
```

Workspaces are backed by `tmux new-session -A` (attach-or-create), so re-opening re-attaches a live session and [tmux-resurrect](https://github.com/tmux-plugins/tmux-resurrect)/[continuum](https://github.com/tmux-plugins/tmux-continuum) restore them across reboots. A `focus.toml` manifest maps focus areas → projects.

## Install

```sh
git clone https://github.com/glebis/pos && cd pos
uv tool install --editable .          # installs `pos` and `pos-cc` on PATH
```

The manifest lives at `~/.config/personal-os/focus.toml` (override with `POS_MANIFEST`). `pos` must run **inside a cmux terminal** (cmux's socket control mode is cmux-processes-only).

## Commands

Run `pos --help` for the full list.

### Focus & projects

| Command | What it does |
|---|---|
| `pos` | list focus areas |
| `pos <focus>` | load a focus: open+pin its projects, close the rest (dry-run unless `--apply`) |
| `pos load <preset\|focus\|names…> [--apply]` | converge the workspace to a set (never closes running jobs or scratch) |
| `pos p [name]` | project index; or open project `<name>` |
| `pos open <path>` | open an ad-hoc workspace at `<path>` |
| `pos day [--date YYYYMMDD]` | hybrid daily pin: focus contexts + today's active projects from the daily note |
| `pos status [--json]` | git status across projects, grouped by focus |
| `pos sidecar [url]` | add a browser (url) or terminal sidecar to the current workspace |
| `pos yard run\|ls\|attach\|kill` | the tmux "yard": detached long-running jobs |

### Claude Code, with resume

| Command | What it does |
|---|---|
| `pos cc <focus>` | open a [Claude Code](https://claude.com/claude-code) workspace for `<focus>` that **resumes its conversation** after a cmux crash or reboot (see [recovery](#claude-session-recovery)) |
| `pos where` | print the current workspace + its backing tmux session |

### Window layout

| Command | What it does |
|---|---|
| `pos spread` | fan every workspace into its own dedicated cmux window |
| `pos tile` | spread, then grid the windows across the screen via [AeroSpace](#screen-tiling-with-aerospace) |
| `pos gather` | inverse of spread/tile — merge all windows back into one |
| `pos solo` | UltraFocus: hide every workspace but the current one (toggle) |
| `pos sort` | reorder the window so **pinned** workspaces sit at the top |

### Workspace CRUD

| Command | What it does |
|---|---|
| `pos new <name> [path]` | open a tmux-backed workspace (a known project uses its manifest path) |
| `pos rename <old> <new>` | rename a live workspace |
| `pos rm <name> [--force]` | close a live workspace; refuses a non-tmux-backed one without `--force` |

### Durability & config

| Command | What it does |
|---|---|
| `pos tmuxify [--apply]` | audit which workspaces are tmux-backed; convert idle shells in place (dry-run unless `--apply`) |
| `pos config [show \| <key> <value>]` | core settings; bare runs an interactive walk |
| `pos completions [zsh\|bash\|fish]` | print a shell completion script |

## Claude session recovery

`pos cc <focus>` launches Claude via the **`pos-cc`** wrapper instead of bare `claude`:

- It runs `claude --continue` when the cwd already has a stored conversation (under `~/.claude/projects/<cwd>/`), else a fresh `claude`. The **cwd is the resume key** — no session-id bookkeeping.
- It runs claude as a **child** (not `exec`), so [tmux-resurrect](https://github.com/tmux-plugins/tmux-resurrect)'s `ps` save-strategy captures `claude` (one level below the pane) rather than claude's MCP-server children.
- `@resurrect-processes` maps `"claude->pos-cc"`, so a restored Claude pane reruns `pos-cc` in its saved cwd → **the conversation resumes** instead of starting fresh.

Net effect: a reboot restores your tmux sessions *and* drops you back into the same Claude conversation, per project.

## Screen tiling with AeroSpace

Each cmux internal window is a real macOS window, so a tiling WM can arrange them. `pos tile` fans projects into windows and asks [**AeroSpace**](https://github.com/nikitabobko/AeroSpace) to grid them. AeroSpace is **optional** — `pos config window_manager none` makes `pos tile` spread-only. `pos gather` un-tiles.

> AeroSpace is a system-wide tiling WM; running it manages your whole desktop. Quit it anytime to return to normal window behaviour.

## Shell completion

```sh
pos completions zsh  > ~/.zfunc/_pos     # ensure ~/.zfunc is on fpath + compinit runs
pos completions bash > ~/.local/share/bash-completion/completions/pos
pos completions fish > ~/.config/fish/completions/pos.fish
```

Candidates are dynamic (live focuses, projects, open workspaces, settings) via a hidden `pos __list <kind>`.

## Settings

`~/.config/personal-os/settings.toml` (override with `POS_SETTINGS`):

| key | default | choices |
|---|---|---|
| `window_manager` | `aerospace` | `aerospace`, `none` |
| `tile_layout` | `tiles` | `tiles`, `accordion`, `horizontal`, `vertical` |

## Development

```sh
uv run pytest -q        # 146 tests
```

Pure logic (argv builders, planners, parsers) is separated from side-effecting cmux calls so most of the surface is unit-tested without a live socket.

## Related

- **cmux** (`cmuxterm.app`, com.cmuxterm.app) — the terminal multiplexer `pos` drives (third-party app, built on [ghostty](https://github.com/ghostty-org/ghostty))
- [tmux](https://github.com/tmux/tmux) · [tmux-resurrect](https://github.com/tmux-plugins/tmux-resurrect) · [tmux-continuum](https://github.com/tmux-plugins/tmux-continuum)
- [AeroSpace](https://github.com/nikitabobko/AeroSpace) — tiling WM used by `pos tile`
- [Claude Code](https://claude.com/claude-code) — what `pos cc` launches with resume

## License

[Apache-2.0](LICENSE) © 2026 Gleb Kalinin. See [AUTHORS](AUTHORS) for contributors.
