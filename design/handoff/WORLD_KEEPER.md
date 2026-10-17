# World Keeper Companion Specification

**The companion IS the world. "My little World lives here."**

---

## Identity

World Keeper is a teal globe companion — a tiny, stylized representation of the user's personal world. It provides visual personality and warmth. It is never system telemetry, never a health indicator, never a status badge.

---

## Semantic States

Six canonical states. Each has a static pose (first-class deliverable) and an optional animation (enrichment only — never required).

| State | Expression | When |
|---|---|---|
| **idle** | Calm, gentle presence | Default resting state |
| **hello** | Cheerful greeting | App launch, return after absence |
| **listening** | Attentive, tilted | Assistant input active |
| **thinking** | Contemplative | Assistant processing |
| **celebrate** | Joyful, sparkle | Task completion, positive event |
| **sleep** | Peaceful, eyes closed | Idle timeout, night mode |

---

## Visual Construction

### Palette

| Part | Token | Hex |
|---|---|---|
| Body | `companion.body` | `#72b1b1` |
| Patch/highlight | `companion.patch` | `#83bcc0` |
| Eyes | `companion.eye` | `#f0eaff` |
| Mouth | `companion.mouth` | `rgba(240, 234, 255, 0.6)` |
| Ambient ring | `companion.ring` | `rgba(114, 177, 177, 0.6)` |
| Ambient glow | `companion.glow` | `rgba(114, 177, 177, 0.1)` |
| Accent detail | `companion.accent` | `#f0eaff` |

### Shape Language

- Spherical base form (globe)
- Soft, rounded features — no sharp edges
- Continent-like patches on the surface for character
- Simple dot eyes, minimal curved mouth
- Optional ambient ring/glow behind the globe

### Size Rules

| Context | Size | Notes |
|---|---|---|
| Desktop nav | 32px | Alongside assistant trigger |
| Desktop greeting | 48px | In Today view greeting area |
| Mobile nav | 28px | Bottom navigation bar |
| Empty state | 64px | Centered, provides warmth |
| Onboarding | 80px | Hero moment |
| Standalone reference | 120px+ | Animation preview, handoff sheet |

---

## Renderer Independence

The companion must work across multiple rendering backends:

1. **SVG (canonical):** Inline SVG is the source of truth. Every pose is a complete, self-contained SVG. Works everywhere, no dependencies.

2. **Lottie / dotLottie (animation enrichment):** For smooth pose transitions and micro-animations. Feature-detect `lottie-player` or `dotlottie-player`. Falls back gracefully to static SVG pose.

3. **Rive (animation enrichment):** State-machine-driven animation for richer interactivity. Feature-detect Rive runtime. Falls back gracefully to static SVG pose.

### Fallback Chain

```
Rive available? → Use Rive state machine
  ↓ no
Lottie available? → Use Lottie animation
  ↓ no
SVG (always available) → Static pose
```

---

## Accessibility Rules

### Screen Reader Behavior

- When accompanying the assistant trigger button: the SVG artwork is `aria-hidden="true"`. The button's `aria-label` is "Open World assistant". A screen-reader user never encounters "World Keeper illustration" — they encounter a button.
- Standalone decorative display: `aria-hidden="true"`, `role="presentation"`.
- The companion never generates accessibility announcements for its own state changes.

### Motion

- Static poses are the canonical representation. Animation is optional enrichment.
- `prefers-reduced-motion: reduce` → show static pose only, no transitions.
- User motion preference `off` → static pose, no transitions.
- User motion preference `reduced` → instant pose swap (no transition animation).
- User motion preference `subtle` → pose transitions up to 300ms ease-out.

### Visibility

- Turning the companion off removes the visual only. The World assistant control remains as a standard labeled button.
- The companion is never required to understand or operate any feature.

---

## Animation Specifications

### Pose Transitions

| Transition | Duration (subtle) | Easing |
|---|---|---|
| Any → idle | 300ms | ease-out |
| idle → hello | 200ms | ease-out |
| idle → listening | 250ms | ease-out |
| listening → thinking | 200ms | ease-in-out |
| Any → celebrate | 300ms | ease-out |
| Any → sleep | 400ms | ease-out |

### Idle Loop (if animated)

- Subtle breathing/floating motion
- Period: 3–4 seconds
- Amplitude: ≤2px vertical drift
- No continuous rotation

### Celebrate

- Brief sparkle burst (0.5–1s)
- Returns to idle automatically
- No looping

---

## Placement Rules

### Desktop

- Primary: navigation sidebar, near assistant trigger
- Secondary: Today view greeting area
- Tertiary: empty states (centered)

### Tablet

- Primary: top navigation bar, near assistant trigger
- Secondary: greeting area

### Phone

- Primary: bottom navigation bar
- Secondary: greeting area (smaller)

### Never

- Inside data tables
- Overlapping interactive controls
- As a loading indicator
- As a status badge
- Floating over content that shifts layout

---

## High Contrast Adjustments

In high-contrast mode, the companion maintains its teal identity but with increased luminance:

| Part | High Contrast |
|---|---|
| Body | `#8dcfcf` |
| Eyes | `#ffffff` |
| Outline | 1px `#444444` border added |

The ambient glow is removed in high-contrast mode to avoid visual noise.
