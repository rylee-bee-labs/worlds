import { STATE_SHAPE } from "./types";
// The home-model Row clashes with the Row component in name only; alias it.
import type { Row as HomeRow } from "./home-model";
import "./fd.css";

export interface StripProps {
  /** Every source in board order. A source still loading is a tile that says so. */
  entries: StripEntry[];
  onSelect: (cardId: string) => void;
  /** Bad-day mode: show only the sources that need a look, plus one "quiet" tile that opens the rest in place. */
  condensed?: boolean;
  /** Whether the quiet tile has opened the full strip. */
  expanded?: boolean;
  onToggleQuiet?: () => void;
}

export type StripEntry = { row: HomeRow } | { pending: { card: string; title: string; icon: string } };

const TILE: Record<string, string> = {
  healthy: "s-ok", needs_attention: "s-warn", degraded: "s-warn", unavailable: "s-bad",
  stale: "s-stale", unknown: "s-unk", not_configured: "s-none",
};

/** Decorative glyph per source icon, matching the Row glyphs. Never focusable. */
const ICONS: Record<string, string> = {
  sun: "☀",
  book: "▤",
  bookmark: "❑",
  music: "♪",
  download: "⤓",
  archive: "▣",
  calendar: "▦",
  disk: "◔",
  check: "✓",
};

function glyph(icon: string): string {
  return ICONS[icon] ?? "◆";
}

/**
 * One source in the whole-world strip, in board order. A normal source is a button that opens its
 * drill-in; a not_configured source is a link into Connect; a source still loading is a disabled
 * tile. The accessible name carries the sentence ("Name: State. action"); the tile is shaped by state.
 */
function StripItem({ row, onSelect }: { row: HomeRow; onSelect: (cardId: string) => void }) {
  const { item, card } = row;
  const state = STATE_SHAPE[card.source_state];
  const notConfigured = card.source_state === "not_configured";
  // The accessible name starts with the visible text ("Downloads Unavailable") so voice control can say what it sees.
  const label = notConfigured ? `${item.title} ${state.word}. Set up in Connect` : `${item.title} ${state.word}. Show details`;
  const cls = `fd-strip-item ${TILE[card.source_state] ?? "s-unk"}`;

  const body = (
    <>
      <span className="fd-strip-top">
        <span className="fd-strip-icon" aria-hidden="true">
          {glyph(item.icon)}
        </span>
        <span className="fd-strip-name">{item.title}</span>
      </span>
      <span className="fd-strip-state">
        <span className="fd-strip-shape" aria-hidden="true">
          {state.shape}
        </span>
        <span className="fd-strip-word">{state.word}</span>
      </span>
    </>
  );

  if (notConfigured) {
    return (
      <a className={cls} href="#connect" aria-label={label}>
        {body}
      </a>
    );
  }
  return (
    <button type="button" className={cls} aria-label={label} onClick={() => onSelect(item.card)}>
      {body}
    </button>
  );
}

function PendingItem({ item }: { item: { title: string; icon: string } }) {
  return (
    <button type="button" className="fd-strip-item s-unk" disabled aria-label={`${item.title} Loading`}>
      <span className="fd-strip-top">
        <span className="fd-strip-icon" aria-hidden="true">
          {glyph(item.icon)}
        </span>
        <span className="fd-strip-name">{item.title}</span>
      </span>
      <span className="fd-strip-state">
        <span className="fd-strip-word">Loading</span>
      </span>
    </button>
  );
}

const isQuiet = (e: StripEntry) => "row" in e && (e.row.card.source_state === "healthy" || e.row.card.source_state === "not_configured") && e.row.card.freshness !== "stale";

/** The whole world at a glance, in board order, as one control per source. */
export function Strip({ entries, onSelect, condensed = false, expanded = false, onToggleQuiet }: StripProps) {
  const quiet = entries.filter(isQuiet);
  const showing = condensed && !expanded ? entries.filter((e) => !isQuiet(e)) : entries;
  return (
    <div className="fd-strip" role="group" aria-label="Whole world">
      {showing.map((e) =>
        "row" in e ? <StripItem key={e.row.item.card} row={e.row} onSelect={onSelect} /> : <PendingItem key={e.pending.card} item={e.pending} />,
      )}
      {condensed && quiet.length > 0 && (
        <button type="button" className="fd-strip-item s-ok fd-strip-quiet" aria-expanded={expanded} onClick={onToggleQuiet} aria-label={expanded ? "Show fewer sources" : `${quiet.length} quiet. Show all`}>
          <span className="fd-strip-state">
            <span className="fd-strip-shape" aria-hidden="true">
              ●
            </span>
            <span className="fd-strip-word">{expanded ? "Show fewer" : `${quiet.length} quiet`}</span>
          </span>
        </button>
      )}
    </div>
  );
}
