# pos interactive mode — design

**Date:** 2026-06-19
**Spec source:** `~/jtbd/pos-interactive-mode/jtbd.json`
**Status:** proposed

## Goal

Two interactive surfaces over `pos`, sharing one backend:

1. **`pos i`** — a full-screen `curses` TUI in the terminal.
2. **Raycast extension** — the same browse-and-act flow from Raycast's launcher.

Both let the user browse focuses, projects and live sessions, act on a selection
with one gesture, and reach any command — without recalling command names or
re-typing arguments read from output.

## Shared backend = the pos JSON contract

The critical insight: **`pos` already emits JSON when stdout is not a TTY**
(`output.resolve_mode`). That auto-JSON is the API both surfaces consume — no
separate backend, no divergence. The three endpoints that cover the whole
navigation+action flow already exist:

| Need | Command | Output |
|---|---|---|
| Focuses | `pos` (piped) | `[{name, emoji, tier}]` |
| Projects + git status | `pos status --json` | `[{focus, project, branch, dirty, path}]` |
| Command palette | `pos help --json` | `[{name, synopsis, args, example}]` |
| Live workspaces | `pos __list workspaces` | newline list (parseable) |

Actions on both surfaces shell out to the same command strings
(`pos p <name>`, `pos load <focus> --apply`, `pos cc <focus>`, `pos new …`,
`pos rm <name>`). `pos` drives cmux via its own socket/CLI, so actions work
identically whether invoked from a terminal, the TUI, or Raycast.

**Contract guarantee:** these JSON shapes are now a stable interface, not an
implementation detail. Changing them is a breaking change for the Raycast
extension. Keep them in sync with `tests/test_help.py`'s registry checks.

---

# Surface 1 — `pos i` curses TUI

## Goal

A full-screen `curses` TUI for `pos` so the user can browse focuses, projects and
live sessions, act on a selection with one keypress, and reach any of the 24
commands via a palette — without recalling command names or re-typing arguments
read from output.

## Decisions (locked)

| Fork | Decision |
|---|---|
| Interface | Full-screen `curses` TUI (stdlib only, no new deps) |
| Scope | Navigation-first (focuses → projects/sessions → actions), escalating to a command palette for all commands |
| Entry point | `pos i` (alias `pos interactive`). Bare `pos` and every `pos <cmd>` stay byte-for-byte unchanged. Bare-pos-launches-TUI deferred. |
| Action exec | Shell-out: suspend curses, run the command via shared `dispatch()`, show its normal output, pause for a keypress, resume |
| Dispatch | Extract `dispatch(m, cmd, rest) -> int` from `cli.main()`; both `main()` and the TUI call it |
| Safety | Destructive actions (`rm`, `load`) confirm via a y/N modal before running |
| Agent contract | `pos i` engages only on a real TTY; piped/agent invocation errors out. JSON contract of other commands untouched. |

## Module structure

### `src/pos/cli.py` (refactor + new arm)
- Extract the `main()` if-chain into `dispatch(m, cmd, rest) -> int`. `main()`
  becomes: parse argv, load manifest, handle the no-arg focus list, then
  `return dispatch(m, cmd, rest)`.
- New arm in `dispatch`: `cmd in ("i", "interactive")` → `from . import tui; return tui.run(m)` (lazy import avoids a cli↔tui cycle).
- Add `pos i` to `USAGE`.

### `src/pos/help.py`
- Add an `i` entry to `COMMANDS` (keeps `tests/test_help.py` green: every
  registry command must be in USAGE and dispatched).

### `src/pos/tui.py` (new — thin curses shell + pure helpers)
Pure, curses-free, unit-tested:
- `@dataclass Action { cmd: str, rest: list[str], confirm: bool, label: str }`
- `build_view(m, workspaces, status_rows) -> View` — assembles:
  - `focuses`: `focus_order(m)` with emoji.
  - `projects`: per-focus list from `projects_by_focus(m)`, each annotated with
    `branch` + `dirty` from `status.build_status(m)` rows.
  - `live`: glyph-stripped titles from `cmux.live_workspaces()` (the session
    column; empty/"socket down" tolerated).
- `resolve_action(view, pane, sel, key) -> Action | None` — maps a keypress on
  the current selection to an `Action`. Pure lookup table; the single source of
  truth for keybindings.
- `palette_items()` — derived from `help.COMMANDS`.
- `filter_palette(items, query) -> list` — substring/fuzzy filter.

Curses shell (not unit-tested; thin):
- `run(m) -> int` — TTY guard, then `curses.wrapper(_loop, m)`.
- `_loop(stdscr, m)` — render panes + footer, read keys, dispatch via
  `resolve_action`, run actions through `_act`.
- `_act(stdscr, m, action)` — if `action.confirm`, show y/N modal; then suspend
  curses (`def_prog_mode`/`endwin`), `dispatch(m, action.cmd, action.rest)`,
  "press any key", resume (`reset_prog_mode`/`refresh`).
- `_palette(stdscr, m)` — overlay; type-to-filter; Enter selects; if the chosen
  command takes args, prompt for them (suspended), then run via `_act`.

### `tests/test_tui.py` (new)
- `build_view` with a fake manifest + fake workspaces + fake status rows →
  asserts focuses/projects/dirty/live wiring.
- `resolve_action` table: each key → expected `Action` (incl. `confirm=True`
  for `load`/`rm`).
- `filter_palette` substring behavior.
- `run(m)` returns non-zero (and prints a clear message) when stdin/stdout is
  not a TTY (monkeypatch `isatty`). No curses is entered in that path.

## Layout

```
┌ pos interactive ──────────────────────────────────┐
│ FOCUSES          PROJECTS · SESSIONS               │
│▸💼 business      ▸ cenno      main      *          │
│ 🎮 play            pos         main                 │
│ 🧠 brain           skills      feat/x   *          │
│ ────────────────────────────────────────────────  │
│ ↑↓ move  →/tab pane  ⏎ open  l load  c cc  n new   │
│ r rm  : palette  q quit                            │
└────────────────────────────────────────────────────┘
```

- Left pane: focuses (selected focus drives the right pane).
- Right pane: projects of the selected focus, annotated with branch + dirty
  marker (`*`); a project that matches a live workspace is marked as a session.
- Footer: contextual keybindings.

## Keybindings (the `resolve_action` table)

| Key | Focus pane | Project pane |
|---|---|---|
| ↑/↓, j/k | move selection | move selection |
| →/Tab | switch to project pane | (wrap to focus pane) |
| ←/Shift-Tab | (stay) | switch to focus pane |
| Enter | `load <focus> --apply` (confirm) | `p <project>` (open) |
| l | `load <focus> --apply` (confirm) | `load <project> --apply` (confirm) |
| c | `cc <focus>` | `cc <focus-of-project>` |
| n | `new` (prompt name/path) | `new` (prompt) |
| r | — | `rm <project>` (confirm) |
| : or p | open command palette | open command palette |
| q / Esc | quit | quit |

`confirm=True` ⇒ y/N modal before the action runs.

## Command palette

Overlay listing all `help.COMMANDS` (`name` — `synopsis`). Type to fuzzy-filter.
Enter selects: if the command's `args` is non-empty, suspend curses and prompt
for the argument string (`input()`), split with `shlex`, then run via `_act`
(so `rm`/`load` still confirm). No-arg commands run immediately.

## Error handling

- **Not a TTY:** `run` prints `pos i requires an interactive terminal` to stderr,
  returns 1. Never enters curses.
- **Socket down:** `live_workspaces()` returns `[]`; the session column shows
  `(no live workspaces)`. Focus/project navigation still works.
- **Resize:** handle `KEY_RESIZE` by recomputing layout each loop iteration.
- **curses init failure:** `curses.wrapper` restores the terminal on any
  exception; let it propagate to a clean message + non-zero exit.

## Files

- New: `src/pos/tui.py`, `tests/test_tui.py`
- Edit: `src/pos/cli.py` (extract `dispatch`, add `i` arm, USAGE), `src/pos/help.py` (registry entry)

## TUI out of scope (YAGNI)

- Bare `pos` launching the TUI (deferred; explicitly reversible).
- Project creation that edits `focus.toml` (the `new` action opens a workspace;
  manifest editing stays a manual/file concern for now).
- Mouse support, themes, persistent TUI state.

---

# Surface 2 — Raycast extension

## Goal

The same browse-and-act flow from Raycast's launcher: type a focus or project,
see git status inline, hit Enter to open / load / cc. A TypeScript + React
extension built on `@raycast/api` + `@raycast/utils`, consuming the pos JSON
contract above.

## Stack & data flow

- `@raycast/api` (List, Detail, ActionPanel, Action, showToast, confirmAlert).
- `@raycast/utils` `useExec(bin, args, { parseOutput })` for **reads** — runs
  `pos` (stdout not a TTY ⇒ JSON automatically), parses, caches, revalidates.
- Node `execFile` (promisified) for one-shot **actions**, wrapped in
  `showToast` for success/failure.
- `pos` binary path resolved via a preference (`posBin`), defaulting to a
  `which pos` lookup through a login shell (Raycast's PATH is minimal). `cmux`
  is already an absolute path inside pos, so actions reach cmux fine.

## Commands (root-search entries in `package.json`)

1. **pos: Focuses** (`focuses.tsx`) — List from `pos` (JSON). Enter pushes to a
   project List for that focus.
2. **pos: Status** (`status.tsx`) — flat List from `pos status --json`; each item
   shows project, branch, and a dirty accessory; section-grouped by focus.
   Primary action Open (`pos p <name>`); secondary Load focus
   (`pos load <focus> --apply`, destructive ⇒ `confirmAlert`), Open CC
   (`pos cc <focus>`), Copy path.
3. **pos: Run Command** (`commands.tsx`) — List from `pos help --json`; the
   command palette. Commands with `args` push a `Form` to collect arguments,
   then run; no-arg commands run on Enter. `rm`/`load` confirm.

## Module structure

```
raycast/                       (extension root — its own npm package)
  package.json                 manifest: name, commands[], preferences[posBin]
  tsconfig.json
  src/
    lib/pos.ts                 resolvePosBin(), runPosJSON(args), runPosAction(args), types
    focuses.tsx                command 1
    status.tsx                 command 2
    commands.tsx               command 3 (palette + Form)
```

`lib/pos.ts` is the single integration point — every view imports its typed
readers/actions from here, mirroring how the TUI funnels everything through
`dispatch()`. Types (`Focus`, `StatusRow`, `Command`) match the JSON contract.

## Safety / parity with the TUI

- Destructive actions (`load`, `rm`) use `confirmAlert` + `Action.Style.Destructive`.
- Read failures surface via `useExec`'s `failureToastOptions` (retry action).
- Action failures show a failure Toast with stderr.

## Raycast out of scope (YAGNI)

- Publishing to the Raycast Store (local/dev install only for now).
- Live-session management beyond open/close (no rename/spread/tile from Raycast).
- Real-time refresh; rely on `useExec` revalidate-on-mount + manual refresh.

## Open question — repo location

The Raycast extension is TypeScript and self-contained. Default: a top-level
`raycast/` directory in this repo (mono-repo, one place to evolve the shared
contract). Alternative: a separate repo. **Decision: `raycast/` in this repo**
unless the user prefers otherwise.

---

# Decomposition & build order

Two independent build cycles over a shared contract. Recommended order:

1. **`pos i` TUI first.** Building it forces the JSON contract to be complete and
   stable (it's the stricter consumer — it needs the live-workspace data too).
2. **Raycast extension second**, against the now-frozen contract.

Each gets its own implementation plan. This spec is the shared design; the
writing-plans step will produce a plan for Surface 1 first.

## Evidence weaknesses (from JTBD)

n-of-1: the actor is the tool's sole user/author; no external validation. No
verbatim incident quote — triggers are self-reported.
