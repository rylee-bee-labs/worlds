# Personal World — Implementation Notes

**Platform-native web. No framework dependency.**

---

## Technology Stack

- **Markup:** Semantic HTML5 (`header`, `nav`, `main`, `aside`, `dialog`, `section`, `article`)
- **Styling:** CSS custom properties (design tokens), CSS Grid + Flexbox layout, `@media` queries for responsive adaptation
- **Scripting:** Vanilla JavaScript (ES modules). No build step required for development.
- **Companion renderer:** SVG inline (canonical). Lottie/dotLottie and Rive as optional enhancement renderers — feature-detect, don't require.

---

## CSS Custom Properties

Map every token from `DESIGN_TOKENS.json` to a CSS custom property on `:root`. High-contrast overrides swap the property values — components never branch on contrast mode.

```css
:root {
  --pw-surface-canvas: #0a0810;
  --pw-surface-panel: #12101a;
  --pw-surface-elevated: #1a1724;
  --pw-surface-divider: #2a2538;
  --pw-text-primary: #f0eaff;
  --pw-text-secondary: #a397b8;
  --pw-text-muted: #6b5f82;
  --pw-accent-primary: #72b1b1;
  --pw-accent-secondary: #b57f8b;
  --pw-focus-ring: #72b1b1;
  --pw-target-min: 44px;
  --pw-spacing-xs: 4px;
  --pw-spacing-sm: 8px;
  --pw-spacing-md: 16px;
  --pw-spacing-lg: 24px;
  --pw-spacing-xl: 32px;
  --pw-spacing-2xl: 48px;
}

[data-contrast="high"] {
  --pw-surface-canvas: #000000;
  --pw-surface-panel: #0a0a0a;
  --pw-surface-elevated: #1a1a1a;
  --pw-surface-divider: #444444;
  --pw-text-primary: #ffffff;
  --pw-text-secondary: #cccccc;
  --pw-text-muted: #999999;
  --pw-accent-primary: #8dcfcf;
  --pw-accent-secondary: #d4969f;
  --pw-focus-ring: #ffffff;
}
```

---

## Focus Management

```css
:focus-visible {
  outline: var(--pw-focus-ring) solid 2px;
  outline-offset: 2px;
}
```

Never remove focus indicators. `:focus-visible` (not `:focus`) ensures keyboard users see them while mouse users don't get visual noise.

---

## Motion

Default motion preference is `reduced`. Respect OS-level `prefers-reduced-motion` unconditionally.

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

When the user's PW preference is `subtle`, allow transitions up to 300ms with `ease-out`. When `off`, no transitions at all.

---

## Responsive Layout

Use CSS Grid as the primary page layout engine. No JavaScript device detection.

```css
/* Desktop: sidebar + main */
@media (min-width: 1200px) {
  .pw-layout { grid-template-columns: 260px 1fr; }
}

/* Compact: narrower sidebar */
@media (min-width: 900px) and (max-width: 1199px) {
  .pw-layout { grid-template-columns: 220px 1fr; }
}

/* Tablet: stacked, nav becomes top bar */
@media (min-width: 600px) and (max-width: 899px) {
  .pw-layout { grid-template-columns: 1fr; }
}

/* Phone: single column, bottom nav */
@media (max-width: 599px) {
  .pw-layout { grid-template-columns: 1fr; }
}
```

---

## Safe Areas (Phone/Tablet)

```css
.pw-bottom-nav {
  padding-bottom: env(safe-area-inset-bottom, 0px);
}
```

Never place interactive controls in the safe area inset zone.

---

## Dialog & Drawer Patterns

Use native `<dialog>` for modals (confirmation dialogs, mobile assistant sheet). Use `popover` attribute where supported.

```html
<!-- Confirmation dialog — modal -->
<dialog id="confirm-delete">
  <h2>Remove provider?</h2>
  <p>This will disconnect GitHub from your world.</p>
  <button autofocus>Cancel</button>
  <button class="destructive">Remove GitHub</button>
</dialog>
```

- `autofocus` on the cancel/safe action
- Escape always closes
- Focus returns to invoking control on close

For non-modal drawers (provenance, desktop assistant), use a side panel that doesn't trap focus.

---

## Skip Link

First focusable element on every page:

```html
<a href="#main" class="pw-skip-link">Skip to main content</a>
```

---

## Status Communication

Every status indicator includes a text label. Never rely on color alone.

```html
<span class="pw-status" data-status="healthy">
  <span class="pw-status-dot" aria-hidden="true"></span>
  healthy
</span>
```

---

## Progressive Disclosure

Four levels, all reachable via semantic markup:

1. **Glance** — status word + accent color
2. **Useful detail** — expanded row with timestamp, description
3. **Capability detail** — full provider/capability breakdown
4. **Technical provenance** — raw data, API response, refresh timestamp

Use `<details>`/`<summary>` or controlled disclosure with `aria-expanded`.

---

## Typography Loading

```css
@font-face {
  font-family: 'Young Serif';
  font-display: swap;
  /* ... */
}

@font-face {
  font-family: 'Instrument Sans';
  font-display: swap;
  /* ... */
}
```

`font-display: swap` ensures text is always visible during font load.

---

## Heading Hierarchy

Every page follows a strict heading hierarchy:

```
h1 — Page title (one per page)
  h2 — Major sections
    h3 — Subsections
```

No skipped levels. Headings are real `<h1>`–`<h3>` elements, not styled `<div>`s.

---

## Live Regions

```html
<div aria-live="polite" id="pw-announcer" class="sr-only"></div>
```

Update this element's `textContent` for meaningful status changes only. Throttle to ~1 announcement per 30 seconds. Batch burst events.

---

## World Keeper Integration

The companion is purely decorative when static:

```html
<button aria-label="Open World assistant" class="pw-world-trigger">
  <svg aria-hidden="true" class="pw-world-keeper"><!-- globe SVG --></svg>
</button>
```

The SVG artwork is `aria-hidden`. Only the button's accessible label matters to assistive tech.

---

## Build & Deployment

No build step is required for development. For production:

- Minify CSS/JS
- Subset fonts to used glyphs
- Inline critical CSS
- SVG companion can be inlined or loaded as an external asset
- Lottie/Rive animations are loaded lazily as enhancement

---

## Browser Support

Target modern evergreen browsers. Feature-detect `dialog`, `popover`, `CSS.supports()` for progressive enhancement. No polyfills for core functionality — semantic HTML works without JS.
