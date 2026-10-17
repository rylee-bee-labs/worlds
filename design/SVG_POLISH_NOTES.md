# Personal World SVG polish — 2026-09-07

Base: `5214ea113e89903f36ca3791268f33de6b48c266`. Scope: existing exports and icon packs only.

## Before / after

- Combined import library and sprite had lost inherited presentation attributes. Restore fill, stroke, width, rounded caps and joins for all 72 symbols. Interface glyphs retain `currentColor`; companion marks retain their existing palette.
- Nine Chat screens and four Today state screens contained incomplete navigation geometry. Restore calendar details, globe meridians, journal details and the Settings gear using the intact desktop sibling export.
- All 21 product screens: replace the overlapping Chat rectangle/oval with one rounded speech-bubble contour and consistent 2px stroke, in its existing slot.
- Memory: replace irregular stepped outline with an evenly spaced chip silhouette. Sources: remove document/magnifier overlaps.
- Five compact companion marks: lighter 1.5px outline and simpler internal details. Remove the planet stripe crossing its face, truck awning clutter, and redundant tree struts; retain the characters and their overall composition.
- Synchronize the two QA SVG boards, cover, import/contact sheets, sprite, and four existing PNG previews. PNG dimensions and icon ordering are preserved; actual-size preview interface glyphs now use the visible foreground instead of black on dark.

## Verified

- Repository suite: **289 passed**, two dependency deprecation warnings; `uv run pytest --timeout=30`.
- Framework: **PASS**, zero violations; `uv run personal-world framework validate --json`.
- All **122 SVGs parse**; original dimensions/viewBoxes, titles/descriptions and embedded image bytes preserved.
- All **21 product screens** are pixel-identical outside the 72px navigation rail. Structural comparison confirms that only the specified icon nodes changed.
- **432 sprite/master render comparisons** pass: 72 icons × 3 sizes (16/20/24px) × 2 themes.
- **72 icon bounds checks** pass, with no drawing outside the 24px source frame.
- Visual inspection: before/after screen renders, selected icon closeups, dark/light actual-size sheets, all screen compositions. CairoSVG and resvg used; CairoSVG misrenders some existing image patterns, while resvg resolves the intact embedded companion images. Those source images and patterns were preserved.
- `git diff --check`: PASS.

## Contracts and limits

- Accessibility preservation: **PASS** for this asset-only change. Existing semantic labels, colors on the screens, reading order, selection backgrounds, dimensions and motion behavior remain unchanged. No controls or UI were added.
- Full interactive accessibility certification: **N/A** to static exports. Keyboard, screen-reader and responsive runtime behavior were not tested or changed.
- Human Reliability: **PASS** — bounded changes, explicit evidence, reversible patch and file record.
- Public Repository Boundary: **PASS** — existing public design assets only; no credentials, private data, external dependencies or deployment details added.
- Provider-Neutral Baseline: **N/A** to artwork changes; existing framework validation passes.
- Figma reimport and live application rendering: **UNKNOWN**, not performed. No deployment or remote publication performed.

## Intentionally unchanged

The other **65 icon masters** already have clear geometry and remain byte-identical. Their copies in the combined packs received only the missing presentation attributes. Full-size companion source rigs, Mermaid Lottie master and parts, embedded character images, tokens, archived handoff contracts and product code remain unchanged. Screen copy, content spacing, panels and overall composition remain unchanged.

## Modified files

- `media_files/designs/personal-world/icons/contact-sheet-16px.png` — Refresh existing raster preview from corrected SVG masters.
- `media_files/designs/personal-world/icons/contact-sheet-20px.png` — Refresh existing raster preview from corrected SVG masters.
- `media_files/designs/personal-world/icons/contact-sheet-24px.png` — Refresh existing raster preview from corrected SVG masters.
- `media_files/designs/personal-world/icons/contact-sheet.png` — Refresh existing raster preview from corrected SVG masters.
- `media_files/designs/personal-world/icons/figma-icon-library.svg` — Restore inherited fill/stroke/cap/join for all 72 imported glyphs and sync revised masters.
- `media_files/designs/personal-world/icons/figma-icon-library.svg` — Restore inherited fill/stroke/cap/join for all 72 imported glyphs and sync revised masters.
- `design/assets/icons/sprite.svg` — Restore per-symbol presentation and synchronize revised masters; currentColor remains inheritable.
- `media_files/designs/personal-world/icons/svg/chat-ai--sources.svg` — Open the document outline around the magnifier; remove crossing lines.
- `media_files/designs/personal-world/icons/svg/companion--little-helper.svg` — Simplify compact companion detail and use a lighter 1.5px silhouette stroke; preserve character and palette.
- `media_files/designs/personal-world/icons/svg/companion--personal-world.svg` — Simplify compact companion detail and use a lighter 1.5px silhouette stroke; preserve character and palette.
- `media_files/designs/personal-world/icons/svg/companion--rylee-mermaid.svg` — Simplify compact companion detail and use a lighter 1.5px silhouette stroke; preserve character and palette.
- `media_files/designs/personal-world/icons/svg/companion--tacos-morning-paper.svg` — Simplify compact companion detail and use a lighter 1.5px silhouette stroke; preserve character and palette.
- `media_files/designs/personal-world/icons/svg/companion--world-tree-squirrel.svg` — Simplify compact companion detail and use a lighter 1.5px silhouette stroke; preserve character and palette.
- `media_files/designs/personal-world/icons/svg/world-content--memory.svg` — Regularize memory chip: square body, evenly spaced pins, clear center.
- `design/screens/chat/chat-active-conversation.svg` — Unify Chat bubble and tail into one rounded 2px contour. Restore calendar bindings, globe meridians, journal bookmark/spine, and Settings gear from the intact sibling screen. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/chat/chat-contextual-vefr.svg` — Unify Chat bubble and tail into one rounded 2px contour. Restore calendar bindings, globe meridians, journal bookmark/spine, and Settings gear from the intact sibling screen. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/chat/chat-empty-new.svg` — Unify Chat bubble and tail into one rounded 2px contour. Restore calendar bindings, globe meridians, journal bookmark/spine, and Settings gear from the intact sibling screen. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/chat/chat-error-partial.svg` — Unify Chat bubble and tail into one rounded 2px contour. Restore calendar bindings, globe meridians, journal bookmark/spine, and Settings gear from the intact sibling screen. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/chat/chat-long-dense.svg` — Unify Chat bubble and tail into one rounded 2px contour. Restore calendar bindings, globe meridians, journal bookmark/spine, and Settings gear from the intact sibling screen. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/chat/chat-narrow-responsive.svg` — Unify Chat bubble and tail into one rounded 2px contour. Restore calendar bindings, globe meridians, journal bookmark/spine, and Settings gear from the intact sibling screen. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/chat/chat-source-provenance.svg` — Unify Chat bubble and tail into one rounded 2px contour. Restore calendar bindings, globe meridians, journal bookmark/spine, and Settings gear from the intact sibling screen. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/chat/chat-thinking-working.svg` — Unify Chat bubble and tail into one rounded 2px contour. Restore calendar bindings, globe meridians, journal bookmark/spine, and Settings gear from the intact sibling screen. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/chat/chat-tool-capability.svg` — Unify Chat bubble and tail into one rounded 2px contour. Restore calendar bindings, globe meridians, journal bookmark/spine, and Settings gear from the intact sibling screen. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/companion-family-portrait.svg` — Unify Chat bubble and tail into one rounded 2px contour. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/icon-library/cover.svg` — Sync two revised companion marks in the existing 32px cover cells.
- `design/screens/icon-library/qa-dark-24px.svg` — Sync seven simplified icon masters in their existing QA cells; retain labels and other 65 icons.
- `design/screens/icon-library/qa-light-24px.svg` — Sync seven simplified icon masters in their existing QA cells; retain labels and other 65 icons.
- `design/screens/journal-screen.svg` — Unify Chat bubble and tail into one rounded 2px contour. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/settings-refined.svg` — Unify Chat bubble and tail into one rounded 2px contour. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/today-generic-theme.svg` — Unify Chat bubble and tail into one rounded 2px contour. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/today-hybrid-desktop-1440.svg` — Unify Chat bubble and tail into one rounded 2px contour. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/today-hybrid-narrow-900.svg` — Unify Chat bubble and tail into one rounded 2px contour. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/today-rylee-theme.svg` — Unify Chat bubble and tail into one rounded 2px contour. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/today-state-attention.svg` — Unify Chat bubble and tail into one rounded 2px contour. Restore calendar bindings, globe meridians, journal bookmark/spine, and Settings gear from the intact sibling screen. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/today-state-empty.svg` — Unify Chat bubble and tail into one rounded 2px contour. Restore calendar bindings, globe meridians, journal bookmark/spine, and Settings gear from the intact sibling screen. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/today-state-loading.svg` — Unify Chat bubble and tail into one rounded 2px contour. Restore calendar bindings, globe meridians, journal bookmark/spine, and Settings gear from the intact sibling screen. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/today-state-partial.svg` — Unify Chat bubble and tail into one rounded 2px contour. Restore calendar bindings, globe meridians, journal bookmark/spine, and Settings gear from the intact sibling screen. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.
- `design/screens/world-capability-first.svg` — Unify Chat bubble and tail into one rounded 2px contour. Preserve screen layout, copy, colors, selection backgrounds, and companion image data.

This record is the only added repository document.
