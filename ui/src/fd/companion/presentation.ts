import type { PresentationJson } from "./types";

/**
 * presentation/1 is semantics only: a state, a tone, a gesture and whether a reply is being delivered. This file is
 * Worlds' own map from those words to a static pose word and a decorative mark. Companion never says how anything
 * looks; unknown or missing values fall back to the defaults, exactly as the contract requires.
 */
export const DEFAULT_PRESENTATION = { state: "rest", tone: "neutral", gesture: "none", speaking: false } as const;
export type Presentation = { state: string; tone: string; gesture: string; speaking: boolean };

const STATES = ["rest", "attentive", "thinking", "engaged", "giving_space"];
const TONES = ["neutral", "warm", "good_news", "concerned"];
const GESTURES = ["none", "wave", "nod", "shrug", "celebrate"];

/** Tolerant: never throws. Unknown version, unknown value, wrong type or a non-object all read as the defaults. */
export function parsePresentation(value: unknown): Presentation {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return { ...DEFAULT_PRESENTATION };
  const o = value as PresentationJson;
  if (typeof o.v === "string" && !/^presentation\/1$/.test(o.v)) return { ...DEFAULT_PRESENTATION };   // a major version we do not know
  const pick = (v: unknown, allowed: string[], d: string) => (typeof v === "string" && allowed.includes(v) ? v : d);
  return {
    state: pick(o.state, STATES, DEFAULT_PRESENTATION.state),
    tone: pick(o.tone, TONES, DEFAULT_PRESENTATION.tone),
    gesture: pick(o.gesture, GESTURES, DEFAULT_PRESENTATION.gesture),
    speaking: typeof o.speaking === "boolean" ? o.speaking : false,
  };
}

const STATE_WORD: Record<string, string> = {
  rest: "Resting",
  attentive: "Listening",
  thinking: "Thinking",
  engaged: "Here with you",
  giving_space: "Giving you space",
};
const STATE_MARK: Record<string, string> = { rest: "◌", attentive: "◎", thinking: "…", engaged: "●", giving_space: "◦" };
const TONE_WORD: Record<string, string> = { neutral: "", warm: "warmly", good_news: "with good news", concerned: "concerned" };
const GESTURE_MARK: Record<string, string> = { none: "", wave: "✋", nod: "▾", shrug: "⌒", celebrate: "✧" };

/**
 * A static pose: one plain word (read out) and one decorative mark (aria-hidden). Nothing moves, whatever the device
 * setting; "thinking" is synthesized locally while a request is in flight, as the contract says.
 */
export function poseFor(p: Presentation): { word: string; mark: string } {
  const state = STATE_WORD[p.state] ?? STATE_WORD.rest;
  const tone = TONE_WORD[p.tone] ?? "";
  const word = p.state === "rest" && tone === "" ? state : tone ? `${state}, ${tone}` : state;
  return { word, mark: `${STATE_MARK[p.state] ?? STATE_MARK.rest}${GESTURE_MARK[p.gesture] ?? ""}` };
}
