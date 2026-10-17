import { useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BOARD_KEY } from "./api";
import { applyEdits, fromItems, NO_EDITS, toItems, type ConfigItem, type Edits } from "./edit-model";
import type { Board } from "./types";

interface ConfigDoc { schema_version: number; id: string; title: string; home: boolean; items: ConfigItem[] }
export interface SaveError { kind: "conflict" | "invalid" | "other"; text: string; detail?: string }

class Fail extends Error {
  kind: SaveError["kind"];
  detail?: string;
  constructor(kind: SaveError["kind"], text: string, detail?: string) {
    super(text);
    this.kind = kind;
    this.detail = detail;
  }
}

/** The CSRF token for cookie-authenticated writes (empty when there is no cookie, e.g. the dev principal). */
function csrfHeaders(): Record<string, string> {
  const m = typeof document !== "undefined" ? document.cookie.match(/(?:^|;\s*)pw_csrf=([^;]+)/) : null;
  return m ? { "X-CSRF-Token": decodeURIComponent(m[1]) } : {};
}

async function detailOf(res: Response): Promise<string> {
  try {
    const d = (await res.json()) as { detail?: unknown };
    return typeof d.detail === "string" ? d.detail : "";
  } catch {
    return "";
  }
}

const norm = (items: ConfigItem[]) => JSON.stringify(items.map(({ card, size, hidden }) => ({ card, size, hidden })));
const lowerFirst = (s: string) => (s ? s[0].toLowerCase() + s.slice(1) : s);

/**
 * Edit Home as C1 board writes. Opening Edit mode reads the board file (document and ETag) and, if it differs
 * from what is displayed, shows the file first; every write is a PUT with that ETag, one per action, in order,
 * so another editor's change is either seen or refused (409), never overwritten. Undo is another write. After a
 * failure nothing more is sent until Reload; Reload drops anything still queued.
 */
export function useBoardEdit(board: Board | undefined) {
  const qc = useQueryClient();
  const [edits, setEdits] = useState<Edits>(NO_EDITS);
  const [past, setPast] = useState<{ items: ConfigItem[]; message: string }[]>([]);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<SaveError | null>(null);
  const cfg = useRef<{ doc: ConfigDoc; etag: string } | null>(null);
  const chain = useRef<Promise<void>>(Promise.resolve());
  const dead = useRef(false);
  const pending = useRef(0);
  const epoch = useRef(0);
  const lastMessage = useRef("");
  const arranged = useMemo(() => (board ? applyEdits(board, edits) : undefined), [board, edits]);

  const loadConfig = async (id: string) => {
    let res: Response;
    try {
      res = await fetch(`/api/config/board/${id}`, { headers: { accept: "application/json" } });
    } catch {
      throw new Fail("other", "Couldn't reach Worlds.");
    }
    if (!res.ok) throw new Fail("other", "Couldn't load Home's settings.");
    cfg.current = { doc: (await res.json()) as ConfigDoc, etag: res.headers.get("etag") ?? "" };
  };

  /** Read the board file for editing. False (with an error shown) when it can't be read. */
  const begin = async (): Promise<boolean> => {
    if (!board) return false;
    dead.current = false;
    setError(null);
    try {
      await loadConfig(board.id);
    } catch (e) {
      setError(e instanceof Fail ? { kind: e.kind, text: e.message } : { kind: "other", text: "Couldn't load Home's settings." });
      return false;
    }
    if (cfg.current && norm(cfg.current.doc.items) !== norm(toItems(board))) await qc.invalidateQueries({ queryKey: BOARD_KEY });
    return true;
  };

  const write = async (id: string, items: ConfigItem[]) => {
    if (!cfg.current) await loadConfig(id);
    const { doc, etag } = cfg.current!;
    let res: Response;
    try {
      res = await fetch(`/api/config/board/${id}`, {
        method: "PUT",
        headers: { "content-type": "application/json", "if-match": etag, ...csrfHeaders() },
        body: JSON.stringify({ ...doc, items }),
      });
    } catch {
      throw new Fail("other", "Couldn't reach Worlds. Your edit wasn't saved.");
    }
    if (res.status === 409) throw new Fail("conflict", "Home changed somewhere else, your edit wasn't saved.");
    if (res.status === 422) throw new Fail("invalid", "Couldn't save that change.", (await detailOf(res)) || undefined);
    if (!res.ok) throw new Fail("other", "Couldn't save your edit.");
    cfg.current = { doc: (await res.json()) as ConfigDoc, etag: res.headers.get("etag") ?? etag };
  };

  const enqueue = (id: string, items: ConfigItem[]) => {
    const mine = epoch.current;
    pending.current += 1;
    setSaving(true);
    chain.current = chain.current.then(async () => {
      try {
        if (dead.current || mine !== epoch.current) return;
        await write(id, items);
        await qc.invalidateQueries({ queryKey: BOARD_KEY });
      } catch (e) {
        if (mine !== epoch.current) return;
        dead.current = true;
        setError(e instanceof Fail ? { kind: e.kind, text: e.message, detail: e.detail } : { kind: "other", text: "Couldn't save your edit." });
        lastMessage.current = "";
      } finally {
        if (mine === epoch.current) {
          pending.current -= 1;
          if (pending.current === 0) {
            // Everything queued is confirmed (or abandoned): the board now shows the truth. Announce the result.
            setEdits(NO_EDITS);
            setSaving(false);
            setNote(lastMessage.current);
          }
        }
      }
    });
  };

  const apply = (next: Edits, message: string) => {
    if (!board || !arranged || dead.current) return;
    setPast((p) => [...p, { items: toItems(arranged), message }]);
    setEdits(next);
    lastMessage.current = message;
    setNote("Saving…");
    enqueue(board.id, toItems(applyEdits(board, next)));
  };

  const undo = () => {
    const last = past[past.length - 1];
    if (!last || !board || dead.current) return;
    setPast((p) => p.slice(0, -1));
    setEdits(fromItems(last.items));
    lastMessage.current = `Undid: ${lowerFirst(last.message)}`;
    setNote("Saving…");
    enqueue(board.id, last.items);
  };

  /** After a failed save: drop anything still queued, forget the optimistic state and history, and read the board again. */
  const reload = async (): Promise<boolean> => {
    epoch.current += 1;
    chain.current = Promise.resolve();
    pending.current = 0;
    dead.current = false;
    cfg.current = null;
    setEdits(NO_EDITS);
    setPast([]);
    setSaving(false);
    setNote("");
    setError(null);
    await qc.invalidateQueries({ queryKey: BOARD_KEY });
    return begin();
  };

  return { edits, arranged, note, saving, error, canUndo: past.length > 0, begin, apply, undo, reload, clearNote: () => setNote("") };
}
