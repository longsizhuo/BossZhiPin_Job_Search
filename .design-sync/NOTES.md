# design-sync notes — boss-tauri-ui

Repo-specific gotchas for syncing `tauri-ui/` to claude.ai/design. Read before re-syncing.

## What this DS actually is
- `tauri-ui/` is the **Tauri desktop app's own frontend**, not a reusable component library. `private: true` Vite + React 18 + Tailwind 3 app with CSS custom-property tokens (`var(--ink)`, `var(--paper)`, …).
- "Components" are app screens: `App`, `ConfigPage`, `HistoryPage`, `RunPage` (page-level), plus `UpdateBanner` (the one genuinely shared component). All discovered via synth-from-src (no library `dist`/`exports`).
- User explicitly chose to sync it anyway, **floor-cards-only** scope (no authored previews). The bundle ships fully importable regardless.

## Build invocation
- No library build exists. Run from repo root:
  `node .ds-sync/package-build.mjs --config .design-sync/config.json --node-modules tauri-ui/node_modules --out ./ds-bundle`
- `cfg.entry = "tauri-ui/dist/index.js"` is a **deliberately nonexistent path**: it exists only so the PKG_DIR walk-up lands on `tauri-ui/package.json` (so `srcDir`/`cssEntry`/`tsconfig` resolve against `tauri-ui/`). `resolveDistEntry(soft)` returns null for it → synth-from-src kicks in. Don't "fix" it to a real file — a real entry would disable synth discovery and emit ZERO_MATCH (no `.d.ts`).
- `--node-modules tauri-ui/node_modules` (pnpm-managed; react/react-dom/@tauri-apps/zustand all hoisted there).

## CSS must be COMPILED, not raw (critical)
- `src/index.css` is Tailwind **source** (`@tailwind`/`@apply`/`@layer`). Shipping it raw means browsers ignore those directives → `.btn`/`.panel`/`.field-input` expand to nothing and every design renders unstyled. The renders only *look* fine because the monochrome-serif aesthetic resembles browser defaults.
- Fix: `cfg.buildCmd` runs `tailwindcss` to compile `src/index.css` → `tauri-ui/.ds-compiled.css` (gitignored build artifact), and `cfg.cssEntry` points at the compiled file. The driver runs `buildCmd` before the converter, so re-syncs stay correct. **Never point `cssEntry` back at `src/index.css`.**
- Compiled file is ~16KB: Tailwind preflight + expanded component classes + token `:root` vars + the utility classes used in `src/`. Utilities NOT used in src won't be present — the durable vocabulary for new designs is the **component classes + token vars** (see conventions.md), not arbitrary Tailwind utilities.

## Fonts — system stacks by design (FONT_MISSING suppressed)
- The font stacks are intentionally system fonts (Georgia/Times serif, Consolas/Menlo mono; CJK falls back to Songti/宋体). No brand webfont exists to ship. `[FONT_MISSING]` flagged the CJK serif families; suppressed via `cfg.runtimeFontPrefixes` (`Source Han`, `Songti`, `宋体`, `Noto Sans Mono CJK`) because the OS serves them. Substitutes (system fonts) are the intended rendering — accepted deliberately, not a gap.

## The source-kit.mjs fork (`.design-sync/overrides/source-kit.mjs`)
Two repo-specific reasons, both about the synth entry:
1. **Default exports.** Every screen is `export default function <Name>()`. Bare `export * from` re-exports named bindings only, never `default` → nothing lands on `window.BossTauriUI` → validate `[BUNDLE_EXPORT]` fails 5/5. The fork adds `export { default as <Name> }` per file (name recovered via ts-morph).
2. **Bootstrap module.** `src/main.tsx` calls `createRoot(...).render(<App/>)` at module top-level. Bundling it runs that render during IIFE eval; with no `#root` it throws "Target container is not a DOM element", aborting the whole bundle (window.BossTauriUI never assigned). The fork filters out any module whose top-level matches `createRoot(`/`ReactDOM.render(`/`.render(<`.

If a future `tauri-ui` adds a real library build with named exports, this fork can be dropped (remove the `cfg.libOverrides` entry too).

## Render behavior (Tauri runtime absent in headless browser)
- `window.__TAURI_INTERNALS__` doesn't exist in the render-check / design browser, so any IPC call (`ipc.*`, `getCurrentWebview()`) rejects/throws.
- `ConfigPage` & `HistoryPage` render their **real styled chrome** but show their own inline "ERROR" state (the `Cannot read properties of undefined (reading 'invoke')` from the failed IPC). This is the component's genuine empty/error UI, not a sync defect. Not flagged `bad` by the render check.
- `App` & `RunPage` fall to the floor card (App loads config on mount; RunPage calls `getCurrentWebview()` → metadata throw).
- `UpdateBanner` returns `null` (no update available without IPC) → empty root → floor card. This is correct: it only renders when there's a newer GitHub release.

## Re-sync risks
- **Authoring previews would require mocking the entire Tauri IPC layer + the module-level zustand store + i18n** for whole-page screens. High effort, low value; these are app screens, not composable parts. If ever attempted, set `cfg.provider` and supply mocked `ipc`/store via `extraEntries` `$ref` modules.
- The bootstrap-exclusion heuristic in the fork is content-based. If a new screen legitimately calls `.render(<...>)` internally (unlikely here), it'd be wrongly excluded — revisit the regex then.
- Build assumes pnpm-hoisted `tauri-ui/node_modules`; on a fresh clone run `pnpm i --frozen-lockfile` in `tauri-ui/` first, and recreate the fork symlink: `ln -sfn ../.ds-sync/node_modules .design-sync/node_modules` (the fork imports `ts-morph` bare).
- No `.d.ts` ship, so `<Name>Props` interfaces are extracted from src by ts-morph — weaker contracts than a real typed build would give.

## Known render warns
- (none flagged by validate as of first sync — the ConfigPage/HistoryPage inline ERROR banners are component content, not validate warns.)
