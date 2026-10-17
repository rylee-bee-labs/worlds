# Worlds Kit

The **Worlds design language**, packaged for other tool UIs (Project Home's
React + Tailwind web app, Studio's plain ES-module pages, the static
dev-gallery site). It is plain CSS built on the Worlds design tokens — no
build step, no framework, no Tailwind.

- **Version:** `0.1.0+c87ed71c66`
- **Built:** `not recorded (content-addressed)`
- **Source:** Personal Worlds (`ui/kit/src/base.css`, `design/tokens.json`,
  `design/themes/*.json`)
- **Default theme:** `starfield`

## What's in here

| File | What it is |
| --- | --- |
| `tokens.css` | The generated design tokens — every theme, all `--pw-*` custom properties. Immutable contract constants (`--pw-targets-*`, `--pw-focus-ring_*`) live here too. |
| `base.css` | The Worlds look as plain CSS classes (the `wk-` vocabulary). References only `var(--pw-*)` tokens. |
| `fonts/` | The `.woff2` faces `base.css` loads (`@font-face`), relative to `base.css`. |
| `preview.html` | A static page showing every component in every variant, with a switcher for all themes. Served next to the CSS, it is the living reference. |
| `kit.json` | Machine-readable provenance: name, version, build time, themes. |

## Vendor it

Copy this directory into your project (for example `vendor/worlds-kit`). Keep
`base.css`, `tokens.css` and `fonts/` together — `base.css` loads the fonts by
relative path.

## Use it

```html
<!doctype html>
<html lang="en" data-theme="starfield">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <!-- order matters: tokens first, then the kit -->
    <link rel="stylesheet" href="worlds-kit/tokens.css" />
    <link rel="stylesheet" href="worlds-kit/base.css" />
  </head>
  <body>
    <a class="wk-skip-link" href="#main">Skip to main content</a>
    <main id="main" class="wk-page wk-stack">
      <h1>Your tool</h1>
      <button class="wk-btn wk-btn--primary">Do the thing</button>
      <span class="wk-status wk-status--healthy">Healthy</span>
    </main>
  </body>
</html>
```

### Themes

Set `data-theme="<name>"` on `<html>`. The available themes are:

- `station`
- `daylight`
- `doorways`
- `moss`
- `ocean`
- `plain`
- `starfield` — Worlds product default

`station` is the `:root` fallback (no attribute needed); `starfield` is the
Worlds product default. Switching the attribute re-themes the page instantly.

## Icons

`icons.svg` is the Worlds icon library as one sprite: 24px line glyphs in
the text colour (see the list in `design/assets/icons/manifest.json` in
personal-world). Draw one with the `wk-icon` class, always beside words:

```html
<a class="wk-btn" href="https://room.example/">
  Open Studio <svg class="wk-icon wk-icon--sm" aria-hidden="true"><use href="icons.svg#icon-actions-external"/></svg>
</a>
```

Ids are `icon-<category>-<name>`, for example `icon-actions-close`,
`icon-navigation-back`, `icon-navigation-chevron-right`,
`icon-status-feedback-check`, `icon-world-content-sparkle`.

## Minimum accessibility

Every `wk-` component keeps Worlds' accessibility contract:

- interactive targets are never smaller than **44px** (`--pw-targets-minimum`);
- focus is always visible (`:focus-visible` accent ring, 2px + 2px offset);
- status is carried **in words**, never by colour alone;
- motion is reduced to nothing under `prefers-reduced-motion`.

Do not override these when adapting the kit. They are the minimum, not a
suggestion.

## Keeping it current

`base.css` is authored at `ui/kit/src/base.css` and published by
`npm run kit:build` (writes `ui/dist-kit/`). `npm run kit:check` fails if the
committed `dist-kit` differs from a fresh build. Do not hand-edit a vendored
copy — run `node scripts/stamp-kit.mjs <target-dir>` to copy the built kit with
a `STAMP` recording its version.