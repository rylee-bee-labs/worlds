/**
 * PROJECT WORLDS — Generated Design Token Types
 *
 * ⚠️  THIS FILE IS GENERATED. Do not edit by hand.
 * Source: design/tokens.json + design/themes/station.json
 * Generator: scripts/generate-tokens.mjs
 *
 * Usage:
 *   import { TOKENS } from "./generated/tokens";
 *   element.style.color = TOKENS["--pw-text-primary"];
 */

/** All available CSS custom property names */
export type TokenName = "--pw-targets-minimum"
  | "--pw-targets-large"
  | "--pw-focus-ring_width"
  | "--pw-focus-ring_offset"
  | "--pw-motion-default"
  | "--pw-surface-void"
  | "--pw-surface-canvas"
  | "--pw-surface-hull"
  | "--pw-surface-panel"
  | "--pw-surface-elevated"
  | "--pw-surface-raised"
  | "--pw-accent-primary"
  | "--pw-accent-on_primary"
  | "--pw-accent-secondary"
  | "--pw-accent-warm"
  | "--pw-accent-warm_soft"
  | "--pw-accent-gold"
  | "--pw-accent-gold_soft"
  | "--pw-accent-green"
  | "--pw-accent-green_soft"
  | "--pw-accent-coral"
  | "--pw-accent-coral_soft"
  | "--pw-accent-teal"
  | "--pw-accent-teal_soft"
  | "--pw-accent-lavender"
  | "--pw-accent-lavender_soft"
  | "--pw-text-primary"
  | "--pw-text-secondary"
  | "--pw-text-muted"
  | "--pw-border-subtle"
  | "--pw-border-strong"
  | "--pw-border-hover"
  | "--pw-spacing-xs"
  | "--pw-spacing-sm"
  | "--pw-spacing-md"
  | "--pw-spacing-lg"
  | "--pw-spacing-xl"
  | "--pw-spacing-2xl"
  | "--pw-spacing-3xl"
  | "--pw-spacing-4xl"
  | "--pw-radius-sm"
  | "--pw-radius-md"
  | "--pw-radius-lg"
  | "--pw-radius-full"
  | "--pw-shadow-soft"
  | "--pw-shadow-warm"
  | "--pw-shadow-glow"
  | "--pw-typography-font_sans"
  | "--pw-typography-font_serif"
  | "--pw-typography-font_mono"
  | "--pw-typography-size_h1"
  | "--pw-typography-size_lead"
  | "--pw-typography-size_body"
  | "--pw-typography-size_small"
  | "--pw-typography-size_micro"
  | "--pw-typography-size_label";

/** Token values keyed by CSS variable name */
export const TOKENS: Record<TokenName, string> = {
  "--pw-targets-minimum": "var(--pw-targets-minimum)",
  "--pw-targets-large": "var(--pw-targets-large)",
  "--pw-focus-ring_width": "var(--pw-focus-ring_width)",
  "--pw-focus-ring_offset": "var(--pw-focus-ring_offset)",
  "--pw-motion-default": "var(--pw-motion-default)",
  "--pw-surface-void": "var(--pw-surface-void)",
  "--pw-surface-canvas": "var(--pw-surface-canvas)",
  "--pw-surface-hull": "var(--pw-surface-hull)",
  "--pw-surface-panel": "var(--pw-surface-panel)",
  "--pw-surface-elevated": "var(--pw-surface-elevated)",
  "--pw-surface-raised": "var(--pw-surface-raised)",
  "--pw-accent-primary": "var(--pw-accent-primary)",
  "--pw-accent-on_primary": "var(--pw-accent-on_primary)",
  "--pw-accent-secondary": "var(--pw-accent-secondary)",
  "--pw-accent-warm": "var(--pw-accent-warm)",
  "--pw-accent-warm_soft": "var(--pw-accent-warm_soft)",
  "--pw-accent-gold": "var(--pw-accent-gold)",
  "--pw-accent-gold_soft": "var(--pw-accent-gold_soft)",
  "--pw-accent-green": "var(--pw-accent-green)",
  "--pw-accent-green_soft": "var(--pw-accent-green_soft)",
  "--pw-accent-coral": "var(--pw-accent-coral)",
  "--pw-accent-coral_soft": "var(--pw-accent-coral_soft)",
  "--pw-accent-teal": "var(--pw-accent-teal)",
  "--pw-accent-teal_soft": "var(--pw-accent-teal_soft)",
  "--pw-accent-lavender": "var(--pw-accent-lavender)",
  "--pw-accent-lavender_soft": "var(--pw-accent-lavender_soft)",
  "--pw-text-primary": "var(--pw-text-primary)",
  "--pw-text-secondary": "var(--pw-text-secondary)",
  "--pw-text-muted": "var(--pw-text-muted)",
  "--pw-border-subtle": "var(--pw-border-subtle)",
  "--pw-border-strong": "var(--pw-border-strong)",
  "--pw-border-hover": "var(--pw-border-hover)",
  "--pw-spacing-xs": "var(--pw-spacing-xs)",
  "--pw-spacing-sm": "var(--pw-spacing-sm)",
  "--pw-spacing-md": "var(--pw-spacing-md)",
  "--pw-spacing-lg": "var(--pw-spacing-lg)",
  "--pw-spacing-xl": "var(--pw-spacing-xl)",
  "--pw-spacing-2xl": "var(--pw-spacing-2xl)",
  "--pw-spacing-3xl": "var(--pw-spacing-3xl)",
  "--pw-spacing-4xl": "var(--pw-spacing-4xl)",
  "--pw-radius-sm": "var(--pw-radius-sm)",
  "--pw-radius-md": "var(--pw-radius-md)",
  "--pw-radius-lg": "var(--pw-radius-lg)",
  "--pw-radius-full": "var(--pw-radius-full)",
  "--pw-shadow-soft": "var(--pw-shadow-soft)",
  "--pw-shadow-warm": "var(--pw-shadow-warm)",
  "--pw-shadow-glow": "var(--pw-shadow-glow)",
  "--pw-typography-font_sans": "var(--pw-typography-font_sans)",
  "--pw-typography-font_serif": "var(--pw-typography-font_serif)",
  "--pw-typography-font_mono": "var(--pw-typography-font_mono)",
  "--pw-typography-size_h1": "var(--pw-typography-size_h1)",
  "--pw-typography-size_lead": "var(--pw-typography-size_lead)",
  "--pw-typography-size_body": "var(--pw-typography-size_body)",
  "--pw-typography-size_small": "var(--pw-typography-size_small)",
  "--pw-typography-size_micro": "var(--pw-typography-size_micro)",
  "--pw-typography-size_label": "var(--pw-typography-size_label)"
} as const;

/** Get a token value as a CSS string */
export function token(name: TokenName): string {
  return `var(${name})`;
}

/** Theme names available (generated from design/themes/*.json) */
export type ThemeName = "station" | "daylight" | "doorways" | "moss" | "ocean" | "plain" | "starfield";

/** All theme selectors (station is the :root fallback) */
export const THEMES: Record<ThemeName, string> = {
  "station": ":root",
  "daylight": '[data-theme="daylight"]',
  "doorways": '[data-theme="doorways"]',
  "moss": '[data-theme="moss"]',
  "ocean": '[data-theme="ocean"]',
  "plain": '[data-theme="plain"]',
  "starfield": '[data-theme="starfield"]',
} as const;
