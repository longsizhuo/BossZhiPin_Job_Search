// design-sync compile config: extends tauri-ui's Tailwind theme but safelists
// the full semantic component-class vocabulary so it ships even when no app
// screen currently uses a given class (Tailwind purges unreferenced @layer
// components rules otherwise — panel-invert / rule-* were getting dropped).
// Used by cfg.buildCmd; output → tauri-ui/.ds-compiled.css → cfg.cssEntry.
import base from '../tauri-ui/tailwind.config.js';

export default {
  ...base,
  content: ['tauri-ui/src/**/*.{ts,tsx}', 'tauri-ui/index.html'],
  safelist: [
    'btn', 'btn-outline', 'btn-ghost',
    'field-input', 'field-label',
    'panel', 'panel-invert',
    'rule-thick', 'rule-thin', 'rule-hair',
    'mono-tag', 'badge-invert', 'badge-outline',
  ],
};
