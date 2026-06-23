# pos — focus-aligned terminal cockpit

`pos` (point of service) is a thin CLI that drives **cmux** (`cmuxterm.app` — an interactive terminal multiplexer / window manager, built on [ghostty](https://github.com/ghostty-org/ghostty)) on top of [**tmux**](https://github.com/tmux/tmux/wiki), so your terminal workspaces mirror what you're actually focused on. It turns a pile of terminal tabs into a focus-organized cockpit: open projects by focus area, fan them across the screen, hide everything but the one thing, and keep [Claude Code](https://claude.com/claude-code) sessions alive across crashes and reboots.

- **Repo:** <https://github.com/glebis/pos>
- **Runtime:** Python ≥ 3.12, **stdlib-only** (uv-managed). macOS.
- **Status:** 193 tests green · v0.1.0

> Built for a personal setup, but the patterns (cmux socket scripting, tmux-backed durability, resume-aware Claude launch) are reusable.

## Contents

- [Concept](#concept)
- [Install](#install)
- [Commands](#commands)
  - [Interactive mode](#interactive-mode)
  - [Focus & projects](#focus--projects)
  - [Claude Code, with resume](#claude-code-with-resume)
  - [Window layout](#window-layout)
  - [Workspace CRUD](#workspace-crud)
  - [Durability & config](#durability--config)
- [Claude session recovery](#claude-session-recovery)
- [Screen tiling with AeroSpace](#screen-tiling-with-aerospace)
- [Shell completion](#shell-completion)
- [Settings](#settings)
- [Raycast extension](#raycast-extension)
- [Development](#development)
- [Related](#related)
- [License](#license)
- [More from Gleb](#more-from-gleb)

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

Run `pos --help` for the full list. Every command is also driveable from the [interactive TUI](#interactive-mode).

### Interactive mode

| Command | What it does |
|---|---|
| `pos i` (alias `pos interactive`) | full-screen `curses` cockpit: browse focuses → projects/sessions with the arrow keys, act on a selection with one keypress, and reach any command via a `:` palette |

Navigate with `↑↓`/`j k`, switch panes with `→`/`Tab`, quit with `q`. Keypress actions on the selection: `Enter` open · `l` load (confirms) · `c` Claude Code · `n` new workspace · `r` remove (confirms). Press `:` (or `p`) for a fuzzy command palette over the whole command table — anything without a hotkey runs from there. The project pane shows each repo's branch, a `*` dirty marker, and a `●` when it has a live session.

It's TTY-only by design: piped or agent invocation exits with a message, so the JSON output of the other commands is never disturbed. Destructive actions (`load`, `rm`) confirm before running, and each action shells out through the same code path as the CLI, so output is identical.

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
| `pos solo [name]` | UltraFocus: hide every workspace but one — the current one, or `[name]` if given (toggle) |
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

## Raycast extension

A [Raycast](https://raycast.com) front-end lives in [`raycast/`](raycast/). It's a thin client over the same JSON contract the CLI exposes (`pos` emits JSON whenever stdout isn't a TTY), so it just shells out and renders. Three commands:

- **Pos: Focuses** — browse focus areas; drill into a focus's projects.
- **Pos: Project Status** — every project grouped by focus, with git branch + dirty marker; open, launch Claude Code, load the focus, or copy the path.
- **Pos: Run Command** — fuzzy-pick any `pos` command and run it; commands taking arguments prompt for them.

It needs the `pos` CLI on your login shell's PATH (auto-detected via `zsh -lc 'command -v pos'`, overridable in the extension's **pos binary** preference) and Node ≥ 20.

### Install locally (before Store approval)

The extension is [pending review for the Raycast Store](https://github.com/raycast/extensions/pull/28944). Until it's accepted you can run it locally — Raycast loads it as a development extension:

```sh
git clone https://github.com/glebis/pos && cd pos/raycast
npm install
npm run dev          # builds, imports into Raycast, and watches for changes
```

Open Raycast and search "pos" — the three commands appear (tagged *Development*). Keep that `npm run dev` running while you use it; if Raycast asks for the dev server again after a restart, just re-run it. To stop, press `Ctrl-C` in that terminal.

Once the Store PR is merged, install it the normal way from the Raycast Store and you won't need the dev server. See [`raycast/README.md`](raycast/README.md) for development details.

## Development

```sh
uv run pytest -q        # 193 tests
```

Pure logic (argv builders, planners, parsers) is separated from side-effecting cmux calls so most of the surface is unit-tested without a live socket.

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose changes, [SECURITY.md](SECURITY.md) to report vulnerabilities, and [CHANGELOG.md](CHANGELOG.md) for release notes.

## Related

- **cmux** (`cmuxterm.app`, com.cmuxterm.app) — the terminal multiplexer `pos` drives (third-party app, built on [ghostty](https://github.com/ghostty-org/ghostty))
- [tmux](https://github.com/tmux/tmux) · [tmux-resurrect](https://github.com/tmux-plugins/tmux-resurrect) · [tmux-continuum](https://github.com/tmux-plugins/tmux-continuum)
- [AeroSpace](https://github.com/nikitabobko/AeroSpace) — tiling WM used by `pos tile`
- [Claude Code](https://claude.com/claude-code) — what `pos cc` launches with resume

## License

[Apache-2.0](LICENSE) © 2026 Gleb Kalinin. See [AUTHORSHIP.md](AUTHORSHIP.md) for the authorship record and [NOTICE](NOTICE) for attribution. The Raycast extension under [`raycast/`](raycast/) is MIT-licensed, as the Raycast Store requires.

## More from Gleb

I build focus tools, AI workflows, and write about creativity & tech.

- [claude-skills](https://github.com/glebis/claude-skills) — a library of Claude Code skills
