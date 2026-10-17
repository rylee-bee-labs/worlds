# Project Worlds — Theme & Token System

> **Superseded in part by [ADR-0008](../docs/adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../FRONTEND-INVENTORY.md).

How the design system works, for humans and agents.

---

## Architecture

```
design/tokens.json              ← Semantic names (the contract)
design/themes/station.json      ← Default theme values
design/themes/ocean.json        ← Alternative theme
design/themes/moss.json         ← Alternative theme
        ↓
ui/scripts/generate-tokens.mjs  ← Combines tokens + theme → CSS
        ↓
ui/src/generated/tokens.css     ← CSS custom properties consumed by React
        ↓
React components                 ← Reference var(--pw-*)
```

**Single source of truth:** `design/tokens.json` defines what tokens exist.
**Theme files** provide the actual values.
**The generator** combines them into CSS.

---

## For Humans: Creating a Theme

### 1. Copy an existing theme

```bash
cp design/themes/station.json design/themes/mytheme.json
```

### 2. Edit the values

Open `design/themes/mytheme.json` and change the colors. Every key maps to a semantic token:

```json
{
  "surface": {
    "void":     "#080B14",     ← deepest background
    "canvas":   "#0C101C",     ← page background
    "hull":     "#131926",     ← mid-level surface
    "panel":    "#1E2636",     ← content panels
    "elevated": "#273144",     ← popovers, drawers
    "raised":   "#2D3A4E"      ← buttons, inputs
  },
  "accent": {
    "primary":  "#72b1b1",     ← links, focus rings
    "warm":     "#D4A057",     ← amber/gold
    "teal":     "#5A9E9E",     ← calm, reliable
    ...
  },
  "text": {
    "primary":  "#EDE7DB",     ← headings, body
    "secondary": "#CDC6B8",    ← descriptions
    "muted":    "#A29A8C"      ← labels, timestamps
  }
}
```

**Rules:**
- All interactive targets ≥ 44×44px (non-negotiable)
- WCAG AA contrast minimum (4.5:1 normal text, 3:1 large text)
- Status is communicated by TEXT, never color alone
- Focus ring must be visible (2px solid)

### 3. Generate the CSS

```bash
cd ui
node scripts/generate-tokens.mjs --all
```

This generates `src/generated/tokens.css` with all themes.

### 4. Switch themes in the app

Set the `data-theme` attribute on `<html>`:

```html
<html data-theme="mytheme">
```

Or from JavaScript:

```js
document.documentElement.setAttribute("data-theme", "mytheme");
```

The Station theme is the CSS base (lives in `:root`). Since L2 the
first-run **product** default is Starfield: with no stored device choice
the app boots with `data-theme="starfield"` applied (`DEFAULT_THEME`,
`ui/src/app/prefs-dom.ts`), and the Settings switcher can still pick any
theme, remembered per device.

---

## For Agents: Token Reference

### Semantic Token Names

Use these in Tailwind via `var(--pw-*)`:

| Token | Purpose |
|-------|---------|
| `--pw-surface-void` | Deepest background |
| `--pw-surface-canvas` | Page background |
| `--pw-surface-hull` | Mid-level surface |
| `--pw-surface-panel` | Content panels |
| `--pw-surface-elevated` | Popovers, drawers |
| `--pw-surface-raised` | Buttons, inputs |
| `--pw-accent-primary` | Links, active states |
| `--pw-accent-warm` | Amber/gold accent |
| `--pw-accent-warm_soft` | Warm at low opacity |
| `--pw-accent-green` | Healthy, natural |
| `--pw-accent-coral` | Alerts, distress |
| `--pw-accent-teal` | Calm, focused |
| `--pw-accent-lavender` | Creative, AI |
| `--pw-text-primary` | Headings, body |
| `--pw-text-secondary` | Descriptions |
| `--pw-text-muted` | Labels, timestamps |
| `--pw-border-subtle` | Default borders |
| `--pw-border-strong` | Emphasized borders |
| `--pw-radius-sm/md/lg/full` | Border radii |
| `--pw-shadow-soft/warm/glow` | Box shadows |
| `--pw-spacing-xs/sm/md/lg/xl/2xl/3xl/4xl` | Spacing scale |
| `--pw-targets-minimum` | 44px (immutable) |

### Pattern: Using Tokens in Tailwind

```tsx
// ✅ Correct — semantic tokens
<div className="bg-[var(--pw-surface-panel)] text-[var(--pw-text-primary)]">

// ❌ Wrong — hard-coded colors
<div className="bg-slate-900 text-gray-100">
```

### Pattern: Theme-Aware Components

```tsx
// Accent colors adapt to the active theme
<button className="bg-[var(--pw-accent-warm)] text-[var(--pw-surface-void)]">
  Click me
</button>
```

### Pattern: Density-Aware Spacing

```tsx
// Use spacing tokens, not hard-coded px
<div className="p-[var(--pw-spacing-lg)] gap-[var(--pw-spacing-md)]">
```

---

## File Structure

```
design/
├── tokens.json                 ← Semantic token definitions (THE contract)
├── themes/
│   ├── starfield.json          ← First-run default (DEFAULT_THEME)
│   ├── station.json            ← Optional; the generator's :root fallback
│   ├── daylight.json           ← The one light pack (warm paper, deep amber)
│   ├── ocean.json              ← Cool, deep, focused
│   └── moss.json               ← Earthy, grounded, natural
└── opendesign-exploration/
    └── station/                ← Existing Station (uses its own CSS variables)
```

---

## Adding a New Token

1. Add the semantic definition to `design/tokens.json`:

```json
"my_category": {
  "my_token": { "_type": "color", "_desc": "What it's for" }
}
```

2. Add the value to each theme file:

```json
"my_category": {
  "my_token": "#HEXVALUE"
}
```

3. Run the generator:

```bash
node scripts/generate-tokens.mjs --all
```

4. Use in components:

```tsx
<div className="bg-[var(--pw-my_category-my_token)]">
```

---

## Constraints (Non-Negotiable)

These come from the Accessibility Contract and never change:

- **44px minimum hit area** on all interactive elements
- **WCAG AA contrast** (4.5:1 normal, 3:1 large text)
- **Status by text, never color alone** — every status has a word
- **Focus ring always visible** — 2px solid, never removed for aesthetics
- **Reduced motion by default** — respect `prefers-reduced-motion`
- **No pure-white large surfaces** — low-glare for migraine safety
- **Luminance-only rank encoding** — more contrast with the page = more urgent, never hue alone (light ink on the dark packs; dark ink on Daylight)

**Daylight** (the light pack, 2026-09-26) is the one exception to dark-by-default: dark stays the default, and Daylight is a choice. It uses warm paper, never white, and puts primary-button labels (`surface.void`) on a deep amber, so `accent.warm` is dark in this pack only.

Themes may restyle atmosphere, accent, and density WITHIN these floors.
A theme that violates an accessibility constraint is broken, not creative.
