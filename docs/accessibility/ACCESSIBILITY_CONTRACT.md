# Worlds Accessibility Contract

> **Superseded in part by [ADR-0008](../adr/0008-front-door.md) (2026-10-01):** §5.2 Bridge reading order now applies to Home; §9.2 "Customize" becomes Settings + Edit Home; §2.4 focus teal must reach ≥3:1 per theme. All other requirements are unchanged.

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the accessibility floor every screen, component, token and theme must meet · **Read this if:** you are designing, building or reviewing anything a person perceives or operates.

**In short:** the non-negotiable accessibility floor for Worlds — contrast, 44px targets, keyboard and focus, drawer/dialog behaviour, headings and landmarks, live-region restraint, companion rules. It is a contract, not a description of the current build: components must satisfy it, and no theme or preference may lower it.

(Formerly "Personal World" — product renamed 2026-09-12; technical identifiers unchanged.)

**Version 1.0 -- September 2026**

Canonical. Commit to repository. Engineering preserves these rules regardless of design tooling.

---

## 1. Perception

1.1. Default presentation ("comfortable") meets WCAG 2.1 AA contrast minimums (4.5:1 normal text, 3:1 large text) while maintaining low-glare, restrained luminance appropriate for prolonged use and migraine-sensitive users.

1.2. Optional high-contrast presentation increases luminance separation, adds explicit panel borders, and brightens accent colors. It must remain aesthetically coherent -- not merely "maximum contrast everywhere." Accessibility requirements are a floor; individual comfort may require different accessible presentations.

1.3. Status is never communicated through color alone. Every status has an explicit text label: `healthy`, `needs_attention`, `unavailable`, `stale`, `unknown`, `disabled`, `not_configured`.

1.4. No information is communicated solely through icon, position, animation, glow, or companion expression.

1.5. Default loading indicators are static. No shimmer, pulse, or animated skeleton.

1.6. No pure-white large surfaces. No neon accents. No bright saturated blue. The interface is usable for long periods in dim-room conditions without glare discomfort.

---

## 2. Operation

2.1. All interactive elements have a minimum hit area of 44x44 CSS px. Visual icons may be smaller; hit areas may not.

2.2. Every function is reachable and operable by keyboard alone.

2.3. No essential interaction requires hover, drag, double-click, right-click, or fine motor precision. If drag exists as convenience, a button/menu alternative is provided.

2.4. Focus is always visible: 2px solid indicator with sufficient contrast, never removed for aesthetics. In comfortable mode: teal (`#72b1b1`). In high-contrast mode: white (`#FFFFFF`).

2.5. Focus order follows semantic source/reading order.

2.6. A skip-to-main-content link is the first focusable element on every page.

2.7. Phone/tablet layouts respect platform safe areas (`env(safe-area-inset-bottom)` and equivalent). No important controls are placed underneath browser/device UI.

---

## 3. Drawers, Sheets & Dialogs

3.1. **Provenance drawer:** non-modal. Focus moves into drawer on open. Escape closes. Focus returns to invoking control. Background remains interactive.

3.2. **World assistant:** non-modal side drawer (desktop) or modal sheet (mobile). On mobile: focus trapped, Escape closes, explicit close button provided, focus returns to trigger. Heading: "World Assistant".

3.3. **Confirmation dialog (dangerous actions):** modal. Focus trapped. Initial focus on cancel/safe action. Escape cancels. Explicit close control. Background inert (`aria-hidden` on content behind). Focus returns to invoking control.

3.4. **Detail/provenance drawer:** non-modal. Focus moves in. Escape closes. Focus returns.

3.5. **Mobile bottom sheet:** modal when it covers >50% viewport. Focus trapped. Explicit close. Escape dismisses. Focus returns.

3.6. Native `dialog` and `popover` semantics are preferred. Do not invent custom interaction patterns where platform primitives suffice.

---

## 4. Understanding

4.1. Real heading hierarchy (`h1`, `h2`, `h3`). No skipped levels.

4.2. Landmarks: `header`, `navigation`, `main`, `complementary`.

4.3. Every meaningful interactive element has an accessible name that communicates its purpose.

4.4. Destructive actions: name the verb, describe the consequence, identify the provider, require confirmation. Never use vague labels (OK, Yes, Proceed).

4.5. Error messages are specific: name what failed, confirm what still works.

4.6. Progressive disclosure available: Level 1 (glance) is comprehensible alone; Level 4 (technical) is always reachable.

---

## 5. Semantic Source Order

5.1. The canonical DOM/source order is: skip-link, navigation, main, complementary.

5.2. Within `main`, the screen's own reading order is the source order. The home screen (the **Bridge**) reads: first-day summary, world lenses, the star map, what needs you, the briefing panel, rooms, keeper. A screen that changes this order must record the change where the screen is defined.

5.3. This source order supports desktop, tablet, mobile, screen reader, keyboard, and 200% zoom without separate semantic versions.

5.4. CSS may change visual placement. CSS may NOT create a nonsensical semantic order. Do not use CSS ordering to repair an incorrect DOM sequence.

---

## 6. Platform Preferences

6.1. Preference resolution hierarchy (higher layer wins):

```
PLATFORM / ASSISTIVE REQUIREMENT
        |
PROJECT WORLDS ACCESSIBILITY FLOOR
        |
USER COMFORT PREFERENCE
        |
DECORATIVE ENHANCEMENT
```

A lower layer may never violate a requirement above it.

6.2. OS `prefers-reduced-motion` is respected unconditionally. It overrides Worlds animation preferences.

6.3. Browser zoom is never disabled. User text scaling is never prevented.

6.4. Layout survives 200% zoom/reflow without clipping, truncation, or horizontal page scroll.

6.5. The interface never requires a specific orientation.

6.6. Forced-colors / platform high-contrast mode: do not override in ways that destroy platform accessibility. Worlds' high-contrast treatment is additive, not a replacement for OS-level forced colors.

6.7. Worlds preferences may increase comfort but may never lower the accessibility floor.

---

## 7. World Keeper Companion

7.1. The World Keeper is decorative personality. It is never system telemetry.

7.2. When the companion accompanies or contains the assistant trigger, the visual artwork is `aria-hidden="true"`. The actionable control exposes only the useful semantic label: "Open World assistant".

7.3. A screen-reader user never encounters "World Keeper illustration" as a navigation concept. They encounter "Open World assistant (button)".

7.4. Turning the companion off removes no functionality. The World assistant remains accessible through a labeled control.

7.5. The companion never generates accessibility announcements for its own state changes (idle, hello, listening, thinking, celebrate, sleep). Only the underlying assistant/system event generates announcements when independently warranted.

---

## 8. Live Region Restraint

8.1. Use `aria-live="polite"` only for meaningful, user-relevant status changes (e.g., world health change, attention item resolved).

8.2. Do NOT announce: individual poll results, routine health refreshes, provider observations, timestamp updates, animation states, companion state changes, or background discovery events.

8.3. Announcement frequency must not exceed approximately one per 30 seconds under normal operation. Burst events should be batched: "3 capabilities updated" rather than three sequential announcements.

---

## 9. Preferences

9.1. Accessibility preferences tune an already-accessible product. They do not create accessibility.

9.2. No "accessibility mode" exists. The preference section is named "Customize" (`ui/src/screens/Settings/SettingsRoom.tsx`), not a separate accessibility mode.

9.3. "Standard" targets are already >=44px. "Comfortable" contrast is already WCAG AA. Motion is already restrained.
