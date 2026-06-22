# pos Raycast extension (Surface 2) Implementation Plan

**Goal:** A Raycast extension that drives `pos` from the launcher, consuming the same JSON contract the TUI uses (`pos` → focuses, `pos status --json` → projects+git, `pos help --json` → palette).

**Architecture:** Thin TS/React extension on `@raycast/api` + `@raycast/utils`. All `pos` integration funnels through `src/lib/pos.ts`; pure logic (palette filtering, arg splitting, command classification) lives in `src/lib/palette.ts` so it is unit-testable without the Raycast runtime. Reads go through `usePromise(runPosJSON)`; mutating actions through `runPosAction` wrapped in a Toast. `pos` runs with stdout not a TTY, so it emits JSON automatically.

**Tech Stack:** TypeScript, React (`react-jsx`), `@raycast/api`, `@raycast/utils`, Node `child_process`. Tests via `node --test` with type stripping.

## Global Constraints
- Lives in `raycast/` (its own npm package); does not touch the Python package.
- `pos` binary resolved via a `posBin` preference, else a login-shell `command -v pos`, else common locations — so it works under Raycast's minimal PATH.
- Destructive actions (`load`, `rm`) confirm via `confirmAlert`.
- TTY-only commands (`i`, `interactive`) are excluded from the palette.

## Files
- `raycast/package.json` — manifest: 3 commands (focuses, status, commands), `posBin` preference.
- `raycast/tsconfig.json`, `raycast/.gitignore`, `raycast/README.md`, `raycast/assets/icon.png`.
- `raycast/src/lib/palette.ts` — pure: types, `filterPalette`, `paletteCommands`, `needsArgs`, `isDestructive`, `splitArgs`.
- `raycast/src/lib/pos.ts` — `resolvePosBin`, `runPosJSON`, `runPosAction` (re-exports types).
- `raycast/src/lib/actions.ts` — `toastRun`, `confirmAndLoad`, `runRegistryCommand` (Raycast-side action helpers).
- `raycast/src/components/ProjectList.tsx` — shared project list (optional focus filter) with per-row actions.
- `raycast/src/focuses.tsx`, `raycast/src/status.tsx`, `raycast/src/commands.tsx` — the 3 commands.
- `raycast/src/lib/palette.test.ts` — unit tests for the pure layer.

## Commands
1. **pos: Focuses** — list focuses; push to projects of that focus; load/cc actions.
2. **pos: Project Status** — flat project list grouped by focus, git accessories, open/load/cc/copy-path.
3. **pos: Run Command** — palette over `pos help --json`; arg Form when the command takes args; load/rm confirm.

## Verification
- `npm install` then `npm run lint` and `npm run build` (ray) — type-checks + validates the manifest.
- `npm test` — pure-layer unit tests.
- Manual: `npm run dev`, exercise the three commands in Raycast.

## Out of scope (YAGNI)
- Publishing to the Raycast Store. Live-session management beyond open/load/cc/rm. Real-time refresh (rely on revalidate-on-mount).
