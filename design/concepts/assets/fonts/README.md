# Fonts (self-hosted)

Subsetted Latin `woff2` files, served locally — no external font CDN. All are
under the **SIL Open Font License, Version 1.1**, which permits bundling and
self-hosting.

| File | Family | Weight | Role | Package |
|---|---|---|---|---|
| `cormorant-600.woff2` | Cormorant | 600 | room names — calligraphic display | `@fontsource/cormorant-garamond` |
| `spectral-400/500/600.woff2` | Spectral | 400 · 500 · 600 | reading text — literary serif | `@fontsource/spectral` |
| `plex-mono-400/500.woff2` | IBM Plex Mono | 400 · 500 | the technical depths only | `@fontsource/ibm-plex-mono` |

The split is deliberate: the **surface is written** (Cormorant + Spectral), and the
**machinery is a different hand** (Plex Mono, used only inside the depth panel).

Fetched from the Fontsource CDN (`cdn.jsdelivr.net/npm/@fontsource/...`) on
2026-09-18. Cormorant © its authors; Spectral © Production Type; IBM Plex © IBM.
Keep this notice with the files.