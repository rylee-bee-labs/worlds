# Design deviations

This file records intentional deviations from the approved Figma
composition, kept by date, with the reason and verification.

---

## 2026-09-13 — Vault screen decorative ornament contrast

**Source:** Workshop v3 frame 17:1014 (Vault screen), guardian
corner marks (17:corner) and sea-charm line (17:1136).

**Original composition:**
- Guardian corner marks `° ◦ ✦` rendered as text at
  `accent.primary_bright` (`#a5dbd7`) with `opacity-50`.
- Sea-charm line `·  the sea keeps what it is told  ·` rendered at
  `accent.gold` (`#e4c58d`) with `opacity: 0.44`.

**Both elements are aria-hidden.** They are decorative frame-
composition ornaments, not informational.

**Why changed:**
- Guardian marks: rendered contrast was 3.86:1 against
  `surface.canvas` (`#0a0810`) — serious WCAG 2 AA failure on 16px
  text (needs 4.5:1).
- Sea-charm line: rendered contrast was 3.06:1 against the rendered
  `vault.store_panel` (`rgba(26,23,36,0.91)` over canvas =
  `#191622`) — serious WCAG 2 AA failure on 14px text.

**Change:** removed the opacity multiplier on both elements. The
canonical tokens themselves remain unchanged.

**Verification:**
- Guardian marks: now 13.0:1 against canvas (well above 4.5:1).
- Sea-charm line: now 12.01:1 against rendered store-panel (well
  above 4.5:1).

**Impact:** the two ornament elements read more strongly than the
original frame intended. The aria-hidden attribute still keeps them
out of the assistive-technology reading order. The frame's overall
warmth-and-faintness mood is slightly more presentational.

**Decision authority:** accessibility floor outranks literal visual
matching (skill `personal-world-implement-figma` §"Preserve the
accessibility contract in each pass"; user instruction: "If exact
Figma appearance conflicts with the accessibility floor:
ACCESSIBILITY WINS. Record the deviation/reservation.")

**Restoration path:** if the frame intent is recovered (e.g. via
`prefers-reduced-motion` or a higher-contrast theme variant), the
opacity reductions can return with documentation; axe-core does not
flag aria-hidden text in some configurations, so the strict
re-addition may also require a deliberate exemption record.
