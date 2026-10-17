# LottieFiles Animation Handoff — the operator's Mermaid Companion

**Project Worlds Theme Pack · Animation Brief**

---

## What We're Building

Project Worlds is a personal digital appliance with a companion character system. You already designed and animated the default **World Keeper globe** — it's beautiful and sets the quality bar. Now we need the same treatment for **the operator's personal mermaid companion**, a custom theme pack character.

The mermaid is based on the operator's real tattoo — a fine-tip pen doodle style character with flowing rainbow-gradient hair and a teal tail. She's warm, personal, and meaningful. She needs to feel like she belongs in the same world as the globe.

---

## Reference Files

The following frames are in the Figma file and should be shared alongside this document:

1. **Mermaid Character Sheet** — The source artwork. Contains the complete color system, all 6 core poses, the responsive scale hierarchy (64px → 16px), and placement rules. **This is your primary reference.**

2. **World Keeper Globe** — Your previous work. This is the quality bar and style reference. The mermaid should feel like she belongs in the same system.

3. **Mermaid Favicon (256px)** — Circular crop on navy background. Shows the character at small sizes and provides color reference.

4. **the operator Theme Spec Sheet** — Full theme specification with the mermaid integrated into the UI mockups. Shows the context of where she lives in the interface.

5. **Theme Pack Framework** — Technical framework document. Contains the animation constraints table and the full companion rules that all theme pack characters must follow.

---

## The 6 Animations to Build

The mermaid has **6 semantic states**. Each maps to a specific moment in the app. Every animation must loop cleanly or auto-return to idle.

### 1. Idle
- **Pose:** Sitting peacefully, soft smile, hair floating gently
- **Triggers:** Default resting state — this is where she lives most of the time
- **Animation:** Subtle breathing/floating loop, 3–4 second period, maximum 2px vertical drift. NO continuous rotation. This is the most important animation to get right — she'll be in this state 90% of the time.

### 2. Hello
- **Pose:** Waving greeting, friendly raised arm, cheerful expression
- **Triggers:** App launch, return after absence
- **Animation:** Quick friendly wave that settles back to idle. Brief and warm.

### 3. Listening
- **Pose:** Tilted head, attentive expression, hair slightly raised
- **Triggers:** Assistant input is active (user is typing/speaking)
- **Animation:** Gentle tilt + hold, maybe small hair sway to show she's paying attention.

### 4. Thinking
- **Pose:** Looking up or holding a tiny tool, contemplative
- **Triggers:** Assistant is processing a request
- **Animation:** Slow contemplative motion. Returns to idle when processing completes.

### 5. Celebrate
- **Pose:** Sparkles around her, joyful expression
- **Triggers:** Task completion, positive events
- **Animation:** Brief sparkle burst, 0.5–1 second. Sparkles must be **soft and desaturated** — never bright white flashes. Auto-returns to idle. **Does not loop.**

### 6. Sleep
- **Pose:** Curled up, eyes closed, hair draped peacefully
- **Triggers:** Idle timeout, night mode
- **Animation:** Slow ease-in over 400ms. Gentle breathing loop once settled.

---

## ⚠️ Hard Constraints — Migraine Safety

**These are medical necessities, not preferences.**

the product is built for people who need calm, flash-free visuals. Every constraint below exists to prevent triggering a neurological event. Please treat these as absolute requirements.

| Constraint | Requirement |
|---|---|
| **Max transition duration** | 300ms with ease-out easing |
| **Flashing / strobing** | NEVER — no rapid brightness changes of any kind |
| **Continuous rotation** | NEVER — no spinning or revolving motion |
| **Idle loop amplitude** | Maximum 2px vertical drift |
| **Celebrate sparkles** | 0.5–1s only, soft/desaturated, never bright white |
| **Background** | Transparent (she sits on dark aubergine #0A0810) |
| **prefers-reduced-motion** | When active, show static pose only — no animation plays at all |
| **Rapid direction changes** | Avoid — all motion should be smooth and predictable |
| **Parallax / depth effects** | Avoid — flat, gentle motion only |

---

## Pose Transition Timing

| From | To | Duration | Easing |
|---|---|---|---|
| Any state | Idle | 300ms | ease-out |
| Idle | Hello | 200ms | ease-out |
| Idle | Listening | 250ms | ease-out |
| Listening | Thinking | 200ms | ease-in-out |
| Any state | Celebrate | 300ms | ease-out |
| Any state | Sleep | 400ms | ease-out |

---

## Color Palette

The mermaid's canonical colors for animation:

| Name | Hex | Usage |
|---|---|---|
| Ink Line | `#5A2D35` | Contour strokes, outlines |
| Pastel Pink | `#F8C5E8` | Upper hair gradient |
| Lavender | `#E3D5F7` | Mid hair gradient |
| Soft Blue | `#BFD8FE` | Lower hair gradient |
| Mint Pastel | `#A7F3D0` | Highlight strands |
| Pale Gold | `#F6F0BA` | Warm accents, sparkles |
| Mascot Teal | `#72B1B1` | Tail, primary companion color |

**Background:** Always transparent. She composites onto dark surfaces (#0A0810 canvas, #12101A panels).

---

## Size Targets

Optimize for these display sizes:

| Size | Context |
|---|---|
| **48px** | Primary — nav companion slot, greeting area |
| **32px** | Secondary — compact nav |
| **64px** | Empty states, onboarding, first-run |

One master animation that scales cleanly across these sizes is ideal. At 32px and below, fine details (individual hair strands, small accessories) should simplify or disappear gracefully.

---

## Export Requirements

- **Format:** dotLottie (`.lottie`)
- **Background:** Transparent
- **One file per state** (6 total), or a single file with named segments/markers for each state
- **Fallback:** We have static SVGs as the base layer — the animations are an enhancement, not the only renderer

---

## What You Don't Need to Worry About

- **State machine logic** — handled in code, not in the animation files
- **Renderer fallback chain** — we handle Rive → Lottie → SVG in code
- **Separate files per display size** — one master animation scales
- **Accessibility markup** — handled in code (she's `aria-hidden`, announced via her button label)
- **Theme switching** — code handles swapping between globe and mermaid

---

## Notes

The globe you made is perfect — it set the bar for quality and feel. The mermaid should have that same level of polish and personality, just warmer and more personal. She's not a mascot for a brand — she's the operator's companion, based on a tattoo that means something to her.

The character sheet has everything you need for her visual identity. The constraints above keep her safe for the operator's neurological conditions. Within those boundaries, bring her to life however feels right.

Thank you! 💜
