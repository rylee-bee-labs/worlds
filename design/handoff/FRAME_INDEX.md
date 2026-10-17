# Personal World — Figma Frame Index

**File:** `VATVojyJZT9HKx0CrDS0yr`

The canvas is organized into 10 labeled rows. Frames are listed in implementation reading order.

---

## Row 1: HANDOFF — START HERE

Start here. These frames define the contract.

| Node ID | Name | Status | Purpose |
|---|---|---|---|
| `16:157` | Implementation Handoff Index | **Authoritative** | Master index of all deliverables, reading order, and implementation guidance |
| `16:5` | Accessibility Contract v1 Final | **Authoritative** | Visual reference of the accessibility contract (see `ACCESSIBILITY_CONTRACT.md` for canonical text) |

---

## Row 2: CORE SCREENS

Primary screen designs. Implement these.

| Node ID | Name | Status | Purpose |
|---|---|---|---|
| `4:5` | Today Hybrid Desktop 1440 | **Authoritative** | Primary Today view — desktop layout at 1440px |
| `6:4` | World Capability First | **Authoritative** | World/capability detail view |
| `3:445` | Journal Screen | **Authoritative** | Journal entry and history view |
| `5:4` | Settings Refined | **Authoritative** | Settings / Reading & Interaction preferences |

---

## Row 3: RESPONSIVE CASCADE

Shows how core screens adapt across breakpoints.

| Node ID | Name | Status | Purpose |
|---|---|---|---|
| `14:472` | Today Responsive Cascade | **Authoritative** | Today view at desktop → compact → tablet → phone |
| `4:135` | Today Hybrid Narrow 900 | **Authoritative** | Today view at compact breakpoint (900px) |

---

## Row 4: TODAY STATES

Today view in different content states. Implement all states.

| Node ID | Name | Status | Purpose |
|---|---|---|---|
| `3:722` | Empty State | **Authoritative** | No capabilities configured yet |
| `3:779` | Attention State | **Authoritative** | Items needing user attention |
| `3:941` | Partial State | **Authoritative** | Some capabilities healthy, some degraded |
| `3:1044` | Loading State | **Authoritative** | Initial data loading (static, no shimmer) |

---

## Row 5: ACCESSIBILITY & PLATFORM RULES

Design specifications for accessibility and platform behavior.

| Node ID | Name | Status | Purpose |
|---|---|---|---|
| `14:5` | Responsive Platform Rules | **Authoritative** | Breakpoint specifications, token grids, platform rules |
| `14:914` | Accessibility Stress Tests | **Authoritative** | Edge-case accessibility scenarios tested |
| `4:266` | Accessibility Stress Variants | **Authoritative** | Additional a11y test variants |

---

## Row 6: PATTERNS & FEATURES

Reusable patterns and feature-specific designs.

| Node ID | Name | Status | Purpose |
|---|---|---|---|
| `5:283` | Pattern Sheet 1 | **Authoritative** | Reusable component patterns |
| `5:449` | Pattern Sheet 2 | **Authoritative** | Additional patterns |
| `5:587` | Pattern Sheet 3 | **Authoritative** | Additional patterns |
| `7:4` | Feature Detail 1 | **Authoritative** | Feature-specific interaction design |
| `7:192` | Feature Detail 2 | **Authoritative** | Feature-specific interaction design |

---

## Row 7: WORLD KEEPER COMPANION

Companion character specification and poses.

| Node ID | Name | Status | Purpose |
|---|---|---|---|
| `11:4` | World Keeper Construction | **Authoritative** | Globe companion visual construction, palette, anatomy |
| `13:4` | World Keeper Poses | **Authoritative** | All 6 semantic state poses (idle, hello, listening, thinking, celebrate, sleep) |
| `13:295` | World Keeper Contexts | **Authoritative** | Companion placement in different UI contexts and sizes |

---

## Row 8: THEMES

Color and theme specifications.

| Node ID | Name | Status | Purpose |
|---|---|---|---|
| `3:2005` | Comfortable Theme | **Authoritative** | Default dark aubergine theme (comfortable contrast) |
| `3:2147` | High Contrast Theme | **Authoritative** | High contrast variant |

---

## Row 9: DIRECTION & REFERENCE

Design direction and exploration. Reference only — not direct implementation targets.

| Node ID | Name | Status | Purpose |
|---|---|---|---|
| `3:1268` | Design Direction | **Reference** | Early design exploration and direction-setting |
| `6:230` | Reference Studies | **Reference** | Comparative reference material |

---

## Row 10: SUPERSEDED — DO NOT IMPLEMENT

Earlier iterations replaced by frames above. Kept for historical context only.

| Node ID | Name | Status | Purpose |
|---|---|---|---|
| `3:1438` | Superseded 1 | **Superseded** | Earlier iteration — do not implement |
| `7:565` | Superseded 2 | **Superseded** | Earlier iteration — do not implement |
| `9:5` | Superseded 3 | **Superseded** | Earlier iteration — do not implement |
| `14:1147` | Superseded 4 | **Superseded** | Earlier iteration — do not implement |
| `7:371` | Superseded 5 | **Superseded** | Earlier iteration — do not implement |

---

## Reading Order for Implementation

1. `ACCESSIBILITY_CONTRACT.md` — non-negotiable rules
2. `DESIGN_TOKENS.json` — build the token layer
3. `IMPLEMENTATION_NOTES.md` — platform patterns
4. `RESPONSIVE_RULES.md` — breakpoints and adaptation
5. Row 1 handoff frames — visual contract reference
6. Row 2 core screens — build these
7. Row 3 responsive cascade — verify adaptation
8. Row 4 today states — implement all states
9. Row 7 World Keeper — companion integration
10. Rows 5–6 — patterns and stress tests for QA
