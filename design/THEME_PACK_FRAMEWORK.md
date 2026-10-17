# Project Worlds — Theme Pack Framework

(Formerly "Personal World" — product renamed 2026-09-12; the companion
character named "Personal World" keeps its name.)

**Companion, Palette & Identity Packs — v1.0**

Project Worlds ships with a default companion (World Keeper globe) but supports swappable Theme Packs. A pack personalizes the experience without touching the accessibility contract.

---

## What a Theme Pack Contains

1. **Companion character** — 6 semantic state poses (SVG canonical + optional Lottie/Rive animations)
2. **Accent color overrides** — primary and secondary accent, must pass WCAG AA on dark aubergine
3. **Companion palette** — body, highlight, eye, detail colors
4. **Optional:** service icon family, favicon, brand mark

## What a Theme Pack Cannot Modify

The following are **invariant** — packs cannot change them:

- Surface colors (canvas, panel, elevated, divider)
- Text colors (primary, secondary, muted)
- Typography (Young Serif headings, Instrument Sans body)
- Spacing scale
- Focus ring behavior
- Touch target minimums (44px)
- Accessibility contract (all 9 sections)
- Semantic source order
- Drawer/dialog behavior
- Live region restraint rules

## Layer Architecture

```
┌─────────────────────────────┐
│   User Preferences          │  ← motion, contrast, density, targets, text_scale
├─────────────────────────────┤
│   Theme Pack Layer          │  ← companion, accent colors, optional icons
├─────────────────────────────┤
│   Invariant Core            │  ← surfaces, text, typography, spacing, a11y contract
└─────────────────────────────┘
```

A higher layer may customize within bounds. No layer may violate the invariant core.

---

## Theme Pack Manifest

```json
{
  "name": "rylee",
  "display_name": "the operator (Mermaid)",
  "author": "Example Person",
  "version": "1.0",
  "companion": {
    "idle": "companions/rylee/idle.svg",
    "hello": "companions/rylee/hello.svg",
    "listening": "companions/rylee/listening.svg",
    "thinking": "companions/rylee/thinking.svg",
    "celebrate": "companions/rylee/celebrate.svg",
    "sleep": "companions/rylee/sleep.svg",
    "animation": {
      "format": "dotlottie",
      "src": "companions/rylee/mermaid.lottie"
    }
  },
  "accent": {
    "primary": "#72B1B1",
    "secondary": "#F8C5E8"
  },
  "companion_palette": {
    "body": "#72B1B1",
    "highlight": "#A7F3D0",
    "eye": "#F0EAFF",
    "detail": "#F8C5E8"
  },
  "favicon": "companions/rylee/favicon.svg",
  "service_icons": "icons/rylee-lab/"
}
```

### Required Fields

- `name` — unique slug (kebab-case)
- `display_name` — shown in Settings > Theme selector
- `companion` — object with all 6 state SVG paths
- `accent.primary` — must pass 3:1 contrast ratio on `#0a0810` (canvas) and `#12101a` (panel)
- `accent.secondary` — must pass 3:1 contrast ratio on `#0a0810` and `#12101a`

### Optional Fields

- `companion.animation` — Lottie/dotLottie or Rive file for animated poses
- `favicon` — custom favicon SVG
- `service_icons` — directory of service-specific icons

---

## Companion Rules (All Packs)

Every companion character — regardless of theme — follows these rules:

1. **`aria-hidden="true"`** when accompanying the assistant trigger button
2. **Never generates accessibility announcements** for its own state changes
3. **Never system telemetry** — the companion is personality, not a health indicator
4. **Non-obstructive** — never blocks links, click bounds, or important UI
5. **Must scale cleanly** from 64px (full detail) down to 16px (simplified silhouette)
6. **Always kind** — expressions are gentle, cozy, and reassuring; never sarcastic or punitive
7. **Static poses are canonical** — animation is optional enrichment
8. **Turning the companion off removes no functionality**

---

## Animation Constraints (Migraine-Safety)

All animated companions must respect these constraints:

| Rule | Value | Reason |
|---|---|---|
| Max transition duration | 300ms | Reduce vestibular trigger risk |
| Easing | ease-out | Gentle deceleration, no bounce |
| Idle loop amplitude | ≤2px vertical | Minimal peripheral movement |
| Idle loop period | 3–4 seconds | Slow, calm rhythm |
| No flashing/strobing | Absolute | Photosensitive seizure prevention |
| No continuous rotation | Absolute | Vestibular trigger prevention |
| No bright white flashes | Absolute | Migraine trigger prevention |
| Celebrate sparkles | 0.5–1s, soft | Brief and desaturated |
| `prefers-reduced-motion` | Show static pose | OS override is unconditional |

---

## Creating Your Own Pack

1. **Design your companion** in 6 semantic states: idle, hello, listening, thinking, celebrate, sleep
2. **Define your accent colors** — both must pass WCAG AA (3:1) on dark aubergine surfaces (#0a0810, #12101a)
3. **Test at all sizes** — 64px (full detail), 48px, 32px, 24px (simplified), 16px (silhouette)
4. **Export SVG poses** — one self-contained SVG per state, transparent background
5. **Optional: animate** — export as dotLottie (.lottie) or Rive (.riv), respecting the migraine-safety constraints above
6. **Write your manifest** — fill in the JSON structure above
7. **Test on dark aubergine** — your companion lives on #0a0810; make sure it reads well
8. **Drop it in** — place your manifest and assets in the `companions/` directory

---

## Default Pack

The default pack ships with Project Worlds:

- **Companion:** World Keeper globe (teal, orbital ring, continent patches)
- **Primary accent:** `#72B1B1` (teal)
- **Secondary accent:** `#B57F8B` (rose)
- **Animation:** Lottie (designed by LottieFiles)
- **Identity:** "My little World lives here."
