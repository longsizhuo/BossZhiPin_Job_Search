# boss-tauri-ui — Minimalist Monochrome

A pure black-and-white **editorial** system: serif body and headings, monospace uppercase wide-tracked small-caps for labels/metadata, **zero border-radius and zero box-shadow anywhere**. Only five colors exist (below). Build on-brand UI by composing the semantic component classes and token variables — do NOT reach for colors, rounded corners, or shadows outside this vocabulary.

## What the bundle exports
`window.BossTauriUI` holds whole **application screens** — `App`, `ConfigPage`, `HistoryPage`, `RunPage`, `UpdateBanner`. These are the BossZhipin desktop app's own pages: they call a Tauri IPC backend (`window.__TAURI_INTERNALS__`) and a module-level store on mount, so outside the desktop app they render their static chrome and then show an inline error/empty state. **Treat them as reference screens, not drop-in widgets.** To build new UI, compose the class vocabulary below — that is what makes a design on-brand here.

## Tokens (the only colors)
Use as `var(--token)`:
- `--ink` `#000` — all foreground, borders, fills, accents
- `--paper` `#fff` — background
- `--muted` `#f5f5f5` — light fill block
- `--muted-fg` `#525252` — secondary text
- `--border-light` `#e5e5e5` — faint dividers

## Component classes (the styling idiom)
Apply these directly as `className`. All ship in `_ds_bundle.css`:

| Class | Use |
|---|---|
| `btn` | Primary button — ink fill, paper text; hover inverts to paper fill |
| `btn-outline` | Secondary — transparent w/ 2px ink border; hover fills ink |
| `btn-ghost` | Text-only action; hover shows ink underline |
| `field-input` | Input/select/textarea — bottom border only, no box; focus thickens border. Add `select.field-input` for selects. |
| `field-label` | Field label — 11px mono uppercase, wide tracking, muted-fg |
| `panel` | Standard container — 1px ink border, paper bg, padding, no radius/shadow |
| `panel-invert` | Emphasis container — ink bg, paper text |
| `rule-thick` / `rule-thin` / `rule-hair` | Horizontal dividers (4px ink / 1px ink / 1px border-light) |
| `mono-tag` | Small mono uppercase metadata tag (muted-fg) |
| `badge-invert` / `badge-outline` | Inline status badges (ink fill / ink outline), 10px mono uppercase |

Typography is automatic via base styles: `<h1>`–`<h4>` and body render serif with tight tracking; `<pre>/<code>/<kbd>/<samp>` render mono. Keep labels mono+uppercase+wide-tracked; keep prose serif.

**Utilities:** the bundle is Tailwind-derived, but only the utility classes the app already uses are present in the shipped CSS — do not rely on arbitrary Tailwind utilities resolving. For anything beyond the classes above, use plain CSS with the token vars (e.g. `style={{ borderTop: '2px solid var(--ink)' }}`), and never introduce a non-monochrome color, a border-radius, or a shadow.

## Where the truth lives
Read the bound stylesheet before styling: `_ds/<folder>/styles.css` → it `@import`s `_ds_bundle.css`, which carries every class above plus the `:root` token definitions. Per-screen API/usage docs are in `_ds/<folder>/components/<group>/<Name>/<Name>.prompt.md`.

## Idiomatic snippet
```jsx
// On-brand form panel built from the class vocabulary (no library screen needed)
<div className="panel" style={{ maxWidth: 480 }}>
  <h2>Settings</h2>
  <hr className="rule-thick" style={{ margin: '12px 0 20px' }} />
  <label className="field-label" htmlFor="endpoint">API Endpoint</label>
  <input id="endpoint" className="field-input" placeholder="https://…" />
  <div style={{ marginTop: 24, display: 'flex', gap: 12 }}>
    <button className="btn">Save</button>
    <button className="btn-ghost">Cancel</button>
  </div>
</div>
```
