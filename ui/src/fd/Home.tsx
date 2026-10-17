import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type FocusEvent, type KeyboardEvent, type ReactNode } from "react";
import { DEFAULT_TIMEOUT_MS, useHomeData, type CardFailure } from "./api";
import { usePrefs } from "./prefs-core";
import { briefing, briefingFull, buildSections, greeting, SECTION_TITLE, type Row as HomeRow, type Sections } from "./home-model";
import { move, setSize, setVisible } from "./edit-model";
import { useBoardEdit } from "./use-board-edit";
import { Row } from "./Row";
import { safeHref } from "./safe-href";
import { Strip, type StripEntry } from "./Strip";
import { STATE_SHAPE, type Board, type BoardItem, type CardEnvelope, type NeedsYouEntry, type Size } from "./types";
import { PaintedIcon } from "./PaintedIcon";
import "./fd.css";

export interface HomeProps {
  timeZone?: string;
  /** Per-request timeout; a card that exceeds it becomes a failed row. Default 10s. */
  timeoutMs?: number;
  /** For tests: the clock the greeting reads. */
  now?: Date;
}

/**
 * A card that never loaded: unknown + stale, no values, no meter, never 0. The evidence carries only
 * what really happened (the failure class and any status), never an invented request id.
 */
function failedEnvelope(item: BoardItem, failure: CardFailure): CardEnvelope {
  return {
    card_id: item.card,
    source_state: "unknown",
    freshness: "stale",
    observed_at: null,
    fetched_at: "",
    last_good_at: null,
    values: {},
    meter: null,
    meaning: { short: "", full: "" },
    evidence: { request_id: "", method: "", path: "", error_class: failure.errorClass, status_code: failure.status },
  };
}

interface Snapshot {
  sections: Sections | null;
  entries: StripEntry[];
}


function snapshot(
  board: Board | undefined,
  cards: Record<string, CardEnvelope>,
  failures: Record<string, CardFailure>,
  pending: string[],
  needsYou: NeedsYouEntry[],
): Snapshot {
  if (!board) return { sections: null, entries: [] };
  const merged: Record<string, CardEnvelope> = { ...cards };
  for (const item of board.items) if (failures[item.card] && !merged[item.card]) merged[item.card] = failedEnvelope(item, failures[item.card]);
  const entries: StripEntry[] = [];
  for (const item of board.items) {
    if (item.hidden) continue;
    const card = merged[item.card];
    if (card) entries.push({ row: { item, card } });
    else if (pending.includes(item.card)) entries.push({ pending: { card: item.card, title: item.title, icon: item.icon } });
  }
  return { sections: buildSections(board, merged, needsYou), entries };
}

function Section({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={`fd-home-section${className ? ` ${className}` : ""}`}>
      <h2 className="fd-home-section-title">{title}</h2>
      {children}
    </section>
  );
}

function NeedsYouList({ entries }: { entries: NeedsYouEntry[] }) {
  return (
    <ul className="fd-home-needs-you">
      {entries.map((entry) => {
        // An approval is done in its source until the approve flow lands here: the item names where, and links there if it can.
        const href = safeHref(entry.action.href);
        return (
          <li key={entry.id} className="fd-home-needs-you-item">
            <span className="fd-home-needs-you-text">{entry.text}</span>
            <span className="fd-home-needs-you-source">{entry.action.kind === "approve" ? `Approve in ${entry.source}` : entry.source}</span>
            {href && (
              <a className="fd-btn fd-btn--primary fd-home-action" href={href} aria-label={`Open: ${entry.text}`}>
                Open
              </a>
            )}
          </li>
        );
      })}
    </ul>
  );
}

interface Raw {
  board: Board | undefined;
  cards: Record<string, CardEnvelope>;
  failures: Record<string, CardFailure>;
  pending: string[];
  needsYou: NeedsYouEntry[];
}

type EditAction = "earlier" | "later" | "hide" | "size-S" | "size-M" | "size-L";

/** The arrange controls for one row: keyboard operable, 44px targets, every name says which row. */
function EditControls({ item, index, count, disabled, onAction }: { item: BoardItem; index: number; count: number; disabled: boolean; onAction: (a: EditAction) => void }) {
  const t = item.title;
  const key = (a: EditAction) => `${item.card}:${a}`;
  return (
    <div className="fd-row-edit" role="group" aria-label={`Arrange ${t}`}>
      <button type="button" className="fd-btn fd-btn--quiet" data-edit={key("earlier")} disabled={disabled || index === 0} aria-label={`Move ${t} earlier`} onClick={() => onAction("earlier")}>
        Earlier
      </button>
      <button type="button" className="fd-btn fd-btn--quiet" data-edit={key("later")} disabled={disabled || index === count - 1} aria-label={`Move ${t} later`} onClick={() => onAction("later")}>
        Later
      </button>
      <button type="button" className="fd-btn fd-btn--quiet" data-edit={key("hide")} disabled={disabled} aria-label={`Hide ${t}`} onClick={() => onAction("hide")}>
        Hide
      </button>
      <span className="fd-row-edit-sizes" role="group" aria-label={`Size of ${t}`}>
        {(["S", "M", "L"] as Size[]).map((s) => (
          <button key={s} type="button" className="fd-btn fd-btn--quiet" data-edit={key(`size-${s}` as EditAction)} disabled={disabled} aria-pressed={item.size === s} aria-label={`${t} size ${s}`} onClick={() => onAction(`size-${s}` as EditAction)}>
            {s}
          </button>
        ))}
      </span>
    </div>
  );
}

/** True on a phone-sized window (under 760px). Re-reads when the window changes. */
function usePhone(): boolean {
  const query = "(max-width: 759px)";
  const [phone, setPhone] = useState(() => typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(query).matches);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(query);
    const on = () => setPhone(mq.matches);
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, []);
  return phone;
}

/**
 * The front door. Greeting and briefing first, the whole-world strip, then the finite Needs you and
 * the row sections. The board, the needs-you list and every card load independently. Pick up is omitted
 * until it has data. Sections are not rebuilt while focus is inside them.
 */
export function Home({ timeZone, timeoutMs = DEFAULT_TIMEOUT_MS, now }: HomeProps) {
  const data = useHomeData(timeoutMs);
  const { board, boardStatus, needsYou, needsYouStatus, cards, failures, pending } = data;
  const { prefs } = usePrefs();
  const [openId, setOpenId] = useState<string | null>(null);
  const [quietOpen, setQuietOpen] = useState(false);
  const [stripOpen, setStripOpen] = useState(false);
  const quietFocus = useRef<"first" | "toggle" | null>(null);
  const [quietTick, setQuietTick] = useState(0);
  const phone = usePhone();
  const [revealTick, setRevealTick] = useState(0);
  const revealRef = useRef<string | null>(null);
  // While focus is inside Home, served data holds the snapshot taken when focus arrived, so nothing moves
  // under the user. The owner's own arrangement (edits) always applies at once.
  const [focusIn, setFocusIn] = useState(false);
  const [heldRaw, setHeldRaw] = useState<Raw | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const [editing, setEditing] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [opening, setOpening] = useState(false);
  const edit = useBoardEdit(board);
  // The polite line stays empty on a normal load. It speaks when the person asked (Try again) or when a source changed state.
  const [announce, setAnnounce] = useState("");
  const qc = useQueryClient();
  const lastState = useRef(new Map<string, string>());
  const titles = useRef(new Map<string, string>());
  useEffect(() => {
    titles.current = new Map((board?.items ?? []).map((i) => [i.card, i.title]));
  }, [board]);
  useEffect(
    () =>
      qc.getQueryCache().subscribe((e) => {
        if (e.type !== "updated" || e.action.type !== "success") return;
        const key = e.query.queryKey;
        if (key[0] !== "fd" || key[1] !== "card") return;
        const data = e.query.state.data as CardEnvelope | undefined;
        if (!data) return;
        const id = String(key[2]);
        const before = lastState.current.get(id);
        lastState.current.set(id, data.source_state);
        if (before !== undefined && before !== data.source_state) setAnnounce(`${titles.current.get(id) ?? id} ${STATE_SHAPE[data.source_state].word.toLowerCase()}`);
      }),
    [qc],
  );
  const { edits, arranged, note } = edit;
  const focusRef = useRef<string | null>(null);
  const [focusTick, setFocusTick] = useState(0);

  const liveRaw = useMemo<Raw>(() => ({ board, cards, failures, pending, needsYou }), [board, cards, failures, pending, needsYou]);
  // The board is the owner's own arrangement, so it is never held; everything that updates by itself is.
  const raw = focusIn && heldRaw?.board ? heldRaw : liveRaw;
  const snap = useMemo(() => snapshot(arranged, raw.cards, raw.failures, raw.pending, raw.needsYou), [arranged, raw]);
  const onFocus = () => {
    if (!focusIn) {
      setHeldRaw(liveRaw);
      setFocusIn(true);
    }
  };
  const onBlur = (e: FocusEvent) => {
    if (!(e.relatedTarget instanceof Node && rootRef.current?.contains(e.relatedTarget))) setFocusIn(false);
  };

  // A strip tap opens the row, unfolds Calm's quiet line if needed, scrolls to it and moves focus to it.
  useEffect(() => {
    const id = revealRef.current;
    if (!id) return;
    const el = document.getElementById(`fd-row-${id}`);
    if (!el) return;
    revealRef.current = null;
    const reduce = typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView?.({ block: "nearest", behavior: reduce ? "auto" : "smooth" });
    el.querySelector<HTMLElement>("button.fd-row-name")?.focus({ preventScroll: true });
  }, [revealTick, quietOpen, openId]);

  // After an arrange action the moved control keeps focus (its element is re-inserted by the reorder).
  useEffect(() => {
    const want = focusRef.current;
    if (!want) return;
    focusRef.current = null;
    const q = (k: string) => rootRef.current?.querySelector<HTMLElement>(`[data-edit="${k}"]`);
    const [card, action] = want.split(":");
    const el = q(want);
    const fallback = action === "earlier" ? q(`${card}:later`) : action === "later" ? q(`${card}:earlier`) : null;
    const target = el && !(el as HTMLButtonElement).disabled ? el : fallback ?? rootRef.current?.querySelector<HTMLElement>("[data-edit-add]");
    target?.focus();
  }, [focusTick]);

  // Calm's Show moves focus to the first revealed row; Show less puts it back on the toggle.
  useEffect(() => {
    const want = quietFocus.current;
    if (!want) return;
    quietFocus.current = null;
    const root = rootRef.current;
    if (want === "toggle") root?.querySelector<HTMLElement>("[data-quiet-toggle]")?.focus();
    else root?.querySelector<HTMLElement>(".fd-home-quiet-rows li.fd-row button.fd-row-name")?.focus();
  }, [quietTick]);

  const change = (next: typeof edits, message: string, focusKey: string) => {
    edit.apply(next, message);
    focusRef.current = focusKey;
    setFocusTick((n) => n + 1);
  };
  const undo = () => {
    edit.undo();
    focusRef.current = "undo";
    setFocusTick((n) => n + 1);
  };

  const sections = snap.sections;
  const { words, density } = prefs;
  const calm = density === "calm";
  const calmQuiet = calm && !quietOpen && !editing;
  // Bad-day layout: Calm at every width, and any density on a phone, shows only what needs a look plus one quiet tile.
  const condensed = calm || phone;

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key !== "Escape" || e.defaultPrevented) return;
    if (openId) {
      const id = openId;
      setOpenId(null);
      document.getElementById(`fd-row-${id}`)?.querySelector<HTMLElement>("button.fd-row-name")?.focus();
      e.preventDefault();
    } else if (editing) {
      setEditing(false);
      setAddOpen(false);
      edit.clearNote();
      rootRef.current?.querySelector<HTMLElement>(".fd-home-edit")?.focus();
      e.preventDefault();
    }
  };

  const reveal = (cardId: string) => {
    setOpenId(cardId);
    if (sections?.quietly_working.some((r) => r.item.card === cardId)) setQuietOpen(true);
    revealRef.current = cardId;
    setRevealTick((n) => n + 1);
  };
  const toggle = (cardId: string) => setOpenId((cur) => (cur === cardId ? null : cardId));

  const failedCheck = needsYouStatus === "error";
  const forBriefing = sections ? { ...sections, needs_you: failedCheck ? [] : needsYou } : null;
  const base = forBriefing
    ? words === "full"
      ? briefingFull(forBriefing, timeZone)
      : briefing(forBriefing)
    : needsYou.length > 0
      ? `${needsYou.length} for you`
      : "";
  const ledeText = failedCheck ? [words === "full" ? "Couldn't check what needs you." : "Couldn't check what needs you", base].filter(Boolean).join(words === "full" ? " " : " · ") : base;

  const act = (row: HomeRow, list: HomeRow[], a: EditAction) => {
    if (!arranged) return;
    const { card, title } = row.item;
    const key = `${card}:${a}`;
    if (a === "earlier" || a === "later") {
      const next = move(arranged, edits, card, a === "earlier" ? -1 : 1, list.map((r) => r.item.card));
      if (next !== edits) change(next, `Moved ${title} ${a}`, key);
    } else if (a === "hide") change(setVisible(edits, card, false), `Hid ${title}`, key);
    else change(setSize(edits, card, a.slice(5) as Size), `Set ${title} to size ${a.slice(5)}`, key);
  };

  const renderRow = (tier: 1 | 2 | 3, list: HomeRow[]) => (row: HomeRow, index: number) => (
    <Row
      key={row.item.card}
      item={row.item}
      card={row.card}
      words={words}
      density={density}
      timeZone={timeZone}
      expanded={openId === row.item.card}
      onToggle={() => toggle(row.item.card)}
      tier={tier}
      controls={editing ? <EditControls item={row.item} index={index} count={list.length} disabled={!!edit.error} onAction={(a) => act(row, list, a)} /> : undefined}
    />
  );
  const hiddenItems = arranged?.items.filter((i) => i.hidden) ?? [];

  const checking = boardStatus === "loading" || pending.length > 0 || needsYouStatus === "loading";

  const needsYouNode = (
    <Section title={SECTION_TITLE.needs_you} className="fd-needs-band">
      {needsYouStatus === "error" ? (
        <div className="fd-home-problem">
          <p className="fd-home-error" role="alert">
            Couldn't check what needs you.
          </p>
          <button type="button" className="fd-btn fd-home-retry" onClick={async () => { setAnnounce("Checking sources…"); await data.refetchNeedsYou(); setAnnounce("Up to date"); }}>
            <PaintedIcon name="action-refresh" size={24} />
            Try again
          </button>
        </div>
      ) : needsYouStatus === "loading" ? (
        <p className="fd-home-loading">Checking what needs you</p>
      ) : needsYou.length === 0 ? (
        <p className="fd-home-empty">
          <PaintedIcon name="object-lantern" size={48} className="fd-empty-art" />
          Nothing for you right now.
        </p>
      ) : (
        <NeedsYouList entries={needsYou} />
      )}
    </Section>
  );

  const stripNode = sections && (
    <>
      <Strip entries={snap.entries} onSelect={reveal} condensed={condensed} expanded={stripOpen} onToggleQuiet={() => setStripOpen((o) => !o)} />
      {pending.length > 0 && <p className="fd-home-checking">{`Checking ${pending.length} ${pending.length === 1 ? "source" : "sources"}`}</p>}
      <div className="fd-home-editrow">
        <button
          type="button"
          className="fd-btn fd-btn--quiet fd-home-edit"
          aria-busy={opening}
          onClick={async () => {
            if (editing) {
              setEditing(false);
              setAddOpen(false);
              edit.clearNote();
            } else if (!opening) {
              // Read the board file first: what you edit is what is saved, never an older copy.
              setOpening(true);
              const ok = await edit.begin();
              setOpening(false);
              if (ok) setEditing(true);
            }
          }}
        >
          {editing ? "Done" : "Edit Home"}
        </button>
        {editing && (
          <>
            <button type="button" className="fd-btn fd-btn--quiet" data-edit-add="" disabled={!!edit.error} aria-expanded={addOpen} onClick={() => setAddOpen((o) => !o)}>
              + Add to Home
            </button>
            <button type="button" className="fd-btn fd-btn--quiet" data-edit="undo" disabled={!edit.canUndo || !!edit.error} onClick={undo}>
              Undo
            </button>
          </>
        )}
      </div>
      {editing && addOpen && (
        <div className="fd-home-add" role="group" aria-label="Add to Home">
          {hiddenItems.length === 0 ? (
            <p className="fd-home-empty">Everything is on Home.</p>
          ) : (
            <ul className="fd-home-add-list">
              {hiddenItems.map((i) => (
                <li key={i.card}>
                  <button type="button" className="fd-btn" onClick={() => change(setVisible(edits, i.card, true), `Added ${i.title} to Home`, `${i.card}:size-${i.size}`)}>
                    {`Add ${i.title} to Home`}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {edit.error && (
        <div className="fd-home-problem">
          <div>
            <p className="fd-home-error" role="alert">
              {edit.error.text}
            </p>
            {edit.error.detail && (
              <details className="fd-home-detail">
                <summary>Details</summary>
                <p>{edit.error.detail}</p>
              </details>
            )}
            <p className="fd-home-note">Editing is paused until you reload.</p>
          </div>
          <button
            type="button"
            className="fd-btn fd-home-retry"
            onClick={async () => {
              await edit.reload();
              rootRef.current?.querySelector<HTMLElement>(".fd-home-edit")?.focus();
            }}
          >
            Reload
          </button>
        </div>
      )}
      <p className="fd-home-editnote" role="status">{note}</p>
    </>
  );

  const restNode = sections && (
    <>
      <Section title={SECTION_TITLE.needs_look}>
        {sections.needs_look.length === 0 ? (
          <p className="fd-home-empty">
            <PaintedIcon name="object-treasure" size={48} className="fd-empty-art" />
            Nothing needs a look. Everything is answering.
          </p>
        ) : (
          <ul className="fd-home-rows">{sections.needs_look.map(renderRow(1, sections.needs_look))}</ul>
        )}
      </Section>

      {sections.your_life.length > 0 && (
        <Section title={SECTION_TITLE.your_life}>
          <ul className="fd-home-rows">{sections.your_life.map(renderRow(2, sections.your_life))}</ul>
        </Section>
      )}

      {sections.quietly_working.length > 0 && (
        <Section title={SECTION_TITLE.quietly_working}>
          {calm && !editing ? (
            <>
              <p className="fd-home-quiet">
                <span className="fd-home-quiet-line">{calmQuiet ? `${sections.quietly_working.length} quiet: ${sections.quietly_working.map((row) => row.item.title).join(", ")}` : `${sections.quietly_working.length} quiet`}</span>{" "}
                <button
                  type="button"
                  className="fd-btn fd-btn--quiet fd-home-quiet-toggle"
                  data-quiet-toggle=""
                  aria-expanded={!calmQuiet}
                  onClick={() => {
                    quietFocus.current = calmQuiet ? "first" : "toggle";
                    setQuietOpen(calmQuiet);
                    setQuietTick((n) => n + 1);
                  }}
                >
                  {calmQuiet ? "Show" : "Show less"}
                </button>
              </p>
              {!calmQuiet && <ul className="fd-home-rows fd-home-quiet-rows">{sections.quietly_working.map(renderRow(3, sections.quietly_working))}</ul>}
            </>
          ) : (
            <ul className="fd-home-rows">{sections.quietly_working.map(renderRow(3, sections.quietly_working))}</ul>
          )}
        </Section>
      )}
    </>
  );

  return (
    <div className="fd-home" ref={rootRef} data-ready={checking ? "false" : "true"} data-saving={edit.saving ? "true" : "false"} data-condensed={condensed ? "true" : "false"} onFocus={onFocus} onBlur={onBlur} onKeyDown={onKeyDown}>
      <p role="status" className="fd-sr">
        {announce}
      </p>
      <header className="fd-home-head">
        <h1 className="fd-home-eyebrow">Home</h1>
        <p className="fd-home-greeting">{greeting(now ?? new Date(), prefs.name)}</p>
        {ledeText && <p className="fd-home-briefing">{ledeText}</p>}
      </header>

      {boardStatus === "error" && (
        <div className="fd-home-problem">
          <p className="fd-home-error" role="alert">
            Home could not load.
          </p>
          <button type="button" className="fd-btn fd-home-retry" onClick={async () => { setAnnounce("Checking sources…"); await data.refetchBoard(); setAnnounce("Up to date"); }}>
            Try again
          </button>
        </div>
      )}
      {boardStatus === "loading" && <p className="fd-home-loading">Loading Home</p>}

      {/* Bad-day order (Calm): what needs you comes first, then the condensed strip. Otherwise the strip leads. */}
      {calm ? (
        <>
          {needsYouNode}
          {stripNode}
        </>
      ) : (
        <>
          {stripNode}
          <div className="fd-home-body">{needsYouNode}</div>
        </>
      )}
      <div className="fd-home-body">{restNode}</div>
    </div>
  );
}
