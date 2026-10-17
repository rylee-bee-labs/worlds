import type { Board, Size } from "./types";

/**
 * Edit Home overlay: the owner's order, visibility and sizes on top of the served board, shown while a save
 * is in flight. The source of truth is the board file (PUT /api/config/board/{id}); the overlay is dropped
 * once the server confirms.
 */
export interface Edits {
  /** Card ids in the owner's order. Cards not listed keep board order after the listed ones. */
  order: string[];
  /** Per-card visibility override: false = hidden by the owner, true = shown although the board hides it. */
  visible: Record<string, boolean>;
  sizes: Record<string, Size>;
}
export const NO_EDITS: Edits = { order: [], visible: {}, sizes: {} };

export const isEdited = (e: Edits) => e.order.length > 0 || Object.keys(e.visible).length > 0 || Object.keys(e.sizes).length > 0;

/** The board as the owner arranged it: ordered, with visibility and sizes applied. */
export function applyEdits(board: Board, e: Edits): Board {
  const rank = new Map(e.order.map((id, i) => [id, i]));
  const items = board.items
    .map((item, i) => ({ item, i }))
    .sort((a, b) => (rank.get(a.item.card) ?? Infinity) - (rank.get(b.item.card) ?? Infinity) || a.i - b.i)
    .map(({ item }) => ({
      ...item,
      hidden: e.visible[item.card] === undefined ? item.hidden : !e.visible[item.card],
      size: e.sizes[item.card] ?? item.size,
    }));
  return { ...board, items };
}

/** Move a card one place earlier (-1) or later (+1) among `siblings` (the cards of its section, in order). */
export function move(board: Board, e: Edits, card: string, dir: -1 | 1, siblings: string[]): Edits {
  const at = siblings.indexOf(card);
  const other = siblings[at + dir];
  if (at < 0 || other === undefined) return e;
  const full = applyEdits(board, e).items.map((i) => i.card);
  const a = full.indexOf(card);
  const b = full.indexOf(other);
  [full[a], full[b]] = [full[b], full[a]];
  return { ...e, order: full };
}

export const setVisible = (e: Edits, card: string, visible: boolean): Edits => ({ ...e, visible: { ...e.visible, [card]: visible } });
export const setSize = (e: Edits, card: string, size: Size): Edits => ({ ...e, sizes: { ...e.sizes, [card]: size } });

/** One item as the C1 board file stores it. */
export interface ConfigItem { card: string; size: Size; hidden: boolean }

/** The arrangement as C1 board items, in display order. */
export const toItems = (board: Board): ConfigItem[] => board.items.map(({ card, size, hidden }) => ({ card, size, hidden }));

/** An overlay that shows exactly these items (used to show an arrangement before the server confirms it). */
export function fromItems(items: ConfigItem[]): Edits {
  return {
    order: items.map((i) => i.card),
    visible: Object.fromEntries(items.map((i) => [i.card, !i.hidden])),
    sizes: Object.fromEntries(items.map((i) => [i.card, i.size])),
  };
}
