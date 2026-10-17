import { formatClock } from "./time";
import type { Board, BoardItem, CardEnvelope, NeedsYouEntry } from "./types";

export type SectionKey = "needs_you" | "needs_look" | "pick_up" | "your_life" | "quietly_working";
export interface Row { item: BoardItem; card: CardEnvelope }
export interface Sections {
  needs_you: NeedsYouEntry[];
  needs_look: Row[];
  your_life: Row[];
  quietly_working: Row[];
  /** not_configured sources: strip only, never a row. */
  not_configured: Row[];
}

const WORST: Record<string, number> = { unavailable: 0, degraded: 1, stale: 2, needs_attention: 3, unknown: 4 };
export const SECTION_TITLE: Record<SectionKey, string> = {
  needs_you: "Needs you",
  needs_look: "Needs a look",
  pick_up: "Pick up",
  your_life: "Your life",
  quietly_working: "Quietly working",
};

const rank = (c: CardEnvelope) => (c.source_state in WORST ? WORST[c.source_state] : WORST.stale);

/**
 * Place each visible item in exactly one section (C6). Needs a look: state in
 * {unavailable, degraded, stale, needs_attention, unknown} or freshness stale, worst first, stable for ties.
 * Your life: healthy + life. Quietly working: healthy + machine. not_configured: strip only.
 * Pure: callers must not re-run this while the user is focused in the list.
 */
export function buildSections(board: Board, cards: Record<string, CardEnvelope>, needsYou: NeedsYouEntry[] = []): Sections {
  const out: Sections = { needs_you: needsYou, needs_look: [], your_life: [], quietly_working: [], not_configured: [] };
  for (const item of board.items) {
    if (item.hidden) continue;
    const card = cards[item.card];
    if (!card) continue;
    const row = { item, card };
    if (card.source_state === "not_configured") out.not_configured.push(row);
    else if (card.source_state !== "healthy" || card.freshness === "stale") out.needs_look.push(row);
    else if (item.group === "life") out.your_life.push(row);
    else out.quietly_working.push(row);
  }
  out.needs_look = out.needs_look
    .map((r, i) => ({ r, i }))
    .sort((a, b) => rank(a.r.card) - rank(b.r.card) || a.i - b.i)
    .map((x) => x.r);
  return out;
}

const STATE_WORD: Record<string, string> = { unavailable: "unavailable", degraded: "degraded", needs_attention: "needs attention", stale: "stale", unknown: "unknown" };
const stateWord = (r: Row) => STATE_WORD[r.card.source_state] ?? "stale";

/** Terse briefing, in the same words as the badges: "2 for you · Downloads unavailable · rest quiet". */
export function briefing(sections: Sections): string {
  const parts: string[] = [];
  const n = sections.needs_you.length;
  if (n > 0) parts.push(`${n} for you`);
  const look = sections.needs_look;
  for (const r of look.slice(0, 2)) parts.push(`${r.item.title} ${stateWord(r)}`);
  if (look.length > 2) parts.push(`${look.length - 2} more to look at`);
  parts.push(parts.length === 0 ? "all quiet" : "rest quiet");
  return parts.join(" · ");
}

const NUMBER_WORDS = ["Nothing", "One thing needs you", "Two things need you", "Three things need you", "Four things need you", "Five things need you", "Six things need you", "Seven things need you", "Eight things need you", "Nine things need you"];

/** Words: Full. Whole sentences, same facts: "Two things need you. Downloads isn't answering; it last worked at 03:12. Everything else is quiet." */
export function briefingFull(sections: Sections, timeZone?: string): string {
  const out: string[] = [];
  const n = sections.needs_you.length;
  if (n > 0) out.push(`${n < NUMBER_WORDS.length ? NUMBER_WORDS[n] : `${n} things need you`}.`);
  const look = sections.needs_look;
  for (const r of look.slice(0, 2)) {
    const t = r.item.title;
    const at = r.card.last_good_at ?? r.card.observed_at;
    const clock = at ? formatClock(at, timeZone) : null;
    switch (r.card.source_state) {
      case "unavailable":
        out.push(clock ? `${t} isn't answering; it last worked at ${clock}.` : `${t} isn't answering, and it hasn't answered yet.`);
        break;
      case "degraded":
        out.push(`${t} is having trouble${clock ? `; it last worked at ${clock}` : ""}.`);
        break;
      case "needs_attention":
        out.push(`${t} needs attention.`);
        break;
      case "unknown":
        out.push(`${t} is unknown: it hasn't answered yet.`);
        break;
      default:
        out.push(`${t} is out of date${clock ? `; it last updated at ${clock}` : ""}.`);
    }
  }
  if (look.length > 2) {
    const more = look.length - 2;
    out.push(`${more} more ${more === 1 ? "needs" : "need"} a look.`);
  }
  out.push(out.length === 0 ? "All quiet." : "Everything else is quiet.");
  return out.join(" ");
}

export function greeting(now: Date, name?: string): string {
  const h = now.getHours();
  const part = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  return name ? `${part}, ${name}` : part;
}
