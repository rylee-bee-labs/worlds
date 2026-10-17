# the operator Theme Pack — Mermaid Companion

**"She is not optional. She is the resident. The lab wouldn't be the operator's without her. <3"**

---

## Identity

the operator's Mermaid is a personal mascot based on the operator's real tattoo. She serves as the digital resident, comforting companion, and status indicator across all personal servers, services, and homelab portals. In Project Worlds, she replaces the default World Keeper globe as the companion character.

**Style:** Delicate, fine-tip pen doodle feel. Clean, continuous lines (1.5px–2px strokes) paired with soft, desaturated pastels. Never loud or neon.

---

## Mermaid Color System

| Part | Name | Hex | Usage |
|---|---|---|---|
| Contour | Ink Line | `#5A2D35` | Primary contour stroke |
| Hair (upper) | Pastel Pink | `#F8C5E8` | Bangs & upper hair flow |
| Hair (mid) | Lavender | `#E3D5F7` | Middle hair gradient |
| Hair (lower) | Soft Blue | `#BFD8FE` | Lower hair layer |
| Hair (accent) | Mint Pastel | `#A7F3D0` | Highlight bang strands |
| Detail | Pale Gold | `#F6F0BA` | Warm detail accent |
| Tail | Mascot Teal | `#72B1B1` | Mermaid tail base fill |

---

## Accent Overrides

When the the operator pack is active, Project Worlds' accent tokens change:

| Token | Default (World Keeper) | the operator (Mermaid) |
|---|---|---|
| `accent.primary` | `#72B1B1` (teal) | `#72B1B1` (same — continuity) |
| `accent.secondary` | `#B57F8B` (rose) | `#F8C5E8` (pastel pink — personal warmth) |

All other tokens (surfaces, text, focus, targets, spacing, typography) remain **identical** to the default theme.

---

## Semantic States

| State | Mermaid Pose | Trigger |
|---|---|---|
| **idle** | Sitting peacefully, soft smile, hair floating gently | Default resting state |
| **hello** | Waving greeting, friendly raised arm | App launch, return after absence |
| **listening** | Tilted head, attentive expression, hair slightly raised | Assistant input active |
| **thinking** | Looking intently, holding a tiny stylized repair tool | Assistant processing, background tasks |
| **celebrate** | Sparkles around her, joyful expression | Task completion, positive event |
| **sleep** | Curled up peacefully, eyes closed, hair draped | Idle timeout, night mode |

---

## Responsive Scale Hierarchy

| Size | Detail Level | Usage |
|---|---|---|
| 64px | Full detail — all hair colors, facial features, tail details | Empty states, onboarding |
| 48px | Full detail | Desktop nav companion, greeting area |
| 32px | Full detail | Compact nav, browser tab favicons |
| 24px | Simple — reduced hair detail, basic silhouette | Small inline indicators |
| 16px | Stroke silhouette with single pastel pink/teal hair streak | Favicons, compact menu button marks |

*Note: At 16px, she is reduced to a clean geometric silhouette with a single pastel pink/teal hair streak. This fits neatly as a standard browser favicon or compact menu button mark.*

---

## Placement Rules

### Where She Lives

| Context | Size | Notes |
|---|---|---|
| Homepage Header | 20px accent | Beside "the operator Lab · active services (14)" |
| Footer | Inline | "the town keeps..." warm presence |
| Empty Search | 48px | Centered, provides warmth |
| Loading Tasks | 32px | Accompanies loading state |
| 404 Errors | 64px | "Something needs attention..." comfort |

### Mascot Rules

1. **[01] Safety & Presence** — Appears everywhere EXCEPT destructive alert dialogs and critical system crashes. We do not panic when servers are actually burning.
2. **[02] Non-Obstructive** — Must never block links, click bounds, or important system status overlays. She sits beside text or inside empty canvas panels.
3. **[03] Micro-Scaling** — Must scale cleanly to a 16px silhouette when in busy tables or navbars. Rainbow hair streak remains the anchor visual identifier.
4. **[04] Always Kind** — Her expressions are always gentle, cozy, and reassuring. Never sarcastic or punitive.
5. **[05] Workshop Friends** — She coexists beautifully with the LRW robot ecosystem. They are friends running the home workshop together.
6. **[06] Resident Status** — She is not optional. She is the resident. The lab wouldn't be the operator's without her. <3

---

## Animation Specifications

### For Lottie/dotLottie Export

| Constraint | Value |
|---|---|
| Format | dotLottie (`.lottie`) |
| Background | Transparent |
| Max transition | 300ms ease-out |
| Idle loop | 3–4s period, ≤2px vertical drift |
| Celebrate | 0.5–1s sparkle burst, soft/desaturated, auto-returns to idle |
| Sleep entry | 400ms ease-out |
| No flashing | Absolute — migraine safety requirement |
| No continuous rotation | Absolute — vestibular safety requirement |
| `prefers-reduced-motion` | Falls back to static SVG pose |

### Pose Transitions

| Transition | Duration | Easing |
|---|---|---|
| Any → idle | 300ms | ease-out |
| idle → hello | 200ms | ease-out |
| idle → listening | 250ms | ease-out |
| listening → thinking | 200ms | ease-in-out |
| Any → celebrate | 300ms | ease-out |
| Any → sleep | 400ms | ease-out |

---

## Renderer Fallback

```
Rive available? → Use Rive state machine
  ↓ no
dotLottie available? → Use Lottie animation
  ↓ no
SVG (always available) → Static pose
```

---

## Favicon

Circular crop of the mermaid on navy background (`#2B3A67`). Available at:
- 256px — high-DPI app icon
- 128px — standard app icon
- 64px — large favicon
- 32px — standard favicon
- 16px — legacy favicon (geometric silhouette with hair streak)

---

## Accessibility

Identical to the default World Keeper companion contract:

- `aria-hidden="true"` when accompanying the assistant trigger
- Button label: "Open World assistant" (NOT "Open Mermaid assistant")
- Never generates announcements for her own state changes
- Turning her off removes no functionality
- She is personality, never telemetry

---

## Manifest

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
    "ink": "#5A2D35",
    "pastel_pink": "#F8C5E8",
    "lavender": "#E3D5F7",
    "soft_blue": "#BFD8FE",
    "mint": "#A7F3D0",
    "pale_gold": "#F6F0BA",
    "teal": "#72B1B1"
  },
  "favicon": "companions/rylee/favicon.svg",
  "service_icons": "icons/rylee-lab/"
}
```

---

*© 2026 the operator Lab. Designed with care. Deeply personal, forever cozy.*
