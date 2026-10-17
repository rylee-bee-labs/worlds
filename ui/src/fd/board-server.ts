import { cards, homeBoard } from "./fixtures";
import type { Board } from "./types";
import type { ConfigItem } from "./edit-model";

interface ConfigDoc { schema_version: 1; id: string; title: string; home: boolean; items: ConfigItem[] }
export interface PutResult { status: 200 | 409 | 412 | 422; body: unknown; etag: string }

/**
 * An in-memory stand-in for GET /api/boards/home and GET/PUT /api/config/board/{id} with the same rules as
 * the real server: If-Match required, a stale tag is 409, an unknown card is 422. For tests only.
 */
export function createBoardServer() {
  const fresh = (): ConfigDoc => ({ schema_version: 1, id: "home", title: "Home", home: true, items: homeBoard.items.map(({ card, size, hidden }) => ({ card, size, hidden })) });
  let doc = fresh();
  let version = 1;
  const etag = () => `"v${version}"`;
  /** Every PUT received, newest last. */
  const puts: { ifMatch: string | null; csrf: string | null; body: ConfigDoc }[] = [];
  return {
    puts,
    reset() { doc = fresh(); version = 1; puts.length = 0; },
    /** Another editor changed the board: the next PUT with the old tag gets 409. */
    bump() { version += 1; },
    /** Another editor saved this arrangement. */
    external(items: ConfigItem[]) { doc = { ...doc, items }; version += 1; },
    items(): ConfigItem[] { return doc.items; },
    display(): Board {
      const byCard = new Map(homeBoard.items.map((i) => [i.card, i]));
      return { ...homeBoard, items: doc.items.map((c) => ({ ...byCard.get(c.card)!, size: c.size, hidden: c.hidden })) };
    },
    getConfig() { return { body: doc, etag: etag() }; },
    put(ifMatch: string | null, csrf: string | null, body: ConfigDoc): PutResult {
      puts.push({ ifMatch, csrf, body });
      if (ifMatch === null) return { status: 412, body: { detail: "If-Match required" }, etag: etag() };
      if (ifMatch !== etag()) return { status: 409, body: { detail: "board home etag is stale" }, etag: etag() };
      const unknown = body.items.filter((i) => !(i.card in cards)).map((i) => i.card);
      if (unknown.length) return { status: 422, body: { detail: `board home: unknown card(s) ${unknown.join(", ")}` }, etag: etag() };
      doc = { ...body };
      version += 1;
      return { status: 200, body: doc, etag: etag() };
    },
  };
}
export type BoardServer = ReturnType<typeof createBoardServer>;
