# Authorship

*Last updated: 2026-06-15*

This file documents the **human creative contribution** behind pos. Copyright
protection for AI-assisted works depends on human authorship and
jurisdiction-specific originality standards; this record distinguishes human
architecture, selection, arrangement, judgment, and direction from
machine-assisted implementation. See [Why This File Exists](#why-this-file-exists).

## Human Author

**Gleb Kalinin** (Berlin, Germany) — Architecture, design, product decisions, and creative direction.
Contact: glebis@gmail.com

## Decisions

Significant human-made decisions and the reasoning behind them. (Evidence:
commit history, README.)

- **stdlib-only Python** (zero runtime dependencies), `src` layout, uv-managed —
  chosen for a durable, low-maintenance personal tool.
- Two-layer architecture: **cmux as the interactive cockpit, tmux as the engine
  room** — detached sessions that must outlive the GUI.
- **Resume-aware Claude launch** — the working directory is the resume key, so no
  session-id bookkeeping is needed.
- **tmux-backed durability** (`new-session -A`, attach-or-create idempotent) so
  workspaces survive crashes and reboots.
- Workspace migrations **protect running jobs** and default to dry-run.

## Exercise of Judgment

Where human judgment shaped, rejected, or refined the work.

- **Test-driven development discipline** throughout (146 tests) — tests written
  before implementation.
- A safety bar: never close or clobber a running workspace silently.
- Incorporated external review — a **Codex finding** on `yard run --` argument
  parsing — after human evaluation.
- Deliberately chose a **zero-dependency** constraint over short-term convenience.

## Goal Setting & Direction

- **Problem:** terminal-tab sprawl; the workspace should mirror what the user is
  actually focused on.
- **Users:** primarily a personal setup, with patterns intended to be reusable by
  others.
- **Non-goals / constraints:** macOS-only, stdlib-only, must survive crashes and
  reboots.

## Art Direction

- **Typographic focus glyphs** — per-focus symbols carried in the manifest.
- The **cockpit / engine-room** conceptual framing and its ASCII diagram.
- A terse, focus-organized UX vocabulary (pin, spread, solo / UltraFocus).

## AI Implementation

Code implementation was assisted by **Claude Code (Anthropic)** and **Codex
(OpenAI)**. The AI generated syntax, function bodies, and boilerplate under human
architectural direction and iterative, test-driven review. The human author
provided the specifications, constraints, review and refinement, and all
debugging and integration decisions. Commits record AI co-authorship; AI session
logs are retained locally as contemporaneous evidence of the creative direction
process.

## Legal & Copyright

Architecture and design copyright (c) 2026-present Gleb Kalinin.

Operating jurisdiction: **Germany / European Union.** Under EU law, a work is
protected where it is the author's **own intellectual creation** reflecting
**free and creative choices** (*Infopaq*, *Painer*); German law (UrhG) requires a
**persönliche geistige Schöpfung** (personal intellectual creation). The
decisions, judgment, direction, and art-direction recorded above are the human
creative choices that meet this standard. AI-assisted implementation was produced
in service of these human-set goals and reviewed as source code.

Provider output terms are recorded for transparency only — they are not a
substitute for source provenance or license-compatibility review:

- **OpenAI** — terms state that, as between user and OpenAI and to the extent
  permitted by law, the user owns the Output.
- **Anthropic** — commercial terms let customers retain ownership rights over
  generated outputs.

This project does not intentionally vendor GPL, AGPL, or LGPL code, and
AI-generated output is reviewed — not pasted blindly — to avoid reproducing
public code without compatible licensing and required notices.

> This section is general information, **not legal advice**. Confirm with
> qualified counsel before relying on it commercially.

## Why This File Exists

Copyright protection for AI-assisted works depends on human authorship and
jurisdiction-specific originality standards. This file documents the human
creative process behind pos so the project can distinguish human architecture,
selection, arrangement, and review from machine-assisted implementation details —
and so authorship can be evidenced if ever questioned.
