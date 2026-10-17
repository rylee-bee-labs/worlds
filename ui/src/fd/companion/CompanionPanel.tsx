import { useEffect, useId, useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { safeHref } from "../safe-href";
import { formatClock } from "../time";
import { companionApi } from "./api";
import { useCompanion } from "./companion-core";
import { healthLine } from "./companion-status";
import { poseFor } from "./presentation";
import type { CompanionFailure, ContextItem, ContextView, GrantView, HealthView, Result, StoredTurn } from "./types";
import "../fd.css";

const SECTIONS: { key: "reviewed" | "working" | "recall" | "live"; label: string }[] = [
  { key: "reviewed", label: "Reviewed" },
  { key: "working", label: "Working" },
  { key: "recall", label: "Recall" },
  { key: "live", label: "Live" },
];

function useFetch<T>(load: () => Promise<Result<T>>, when: boolean): { result: Result<T> | null; loading: boolean; reload: () => void } {
  const [result, setResult] = useState<Result<T> | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!when) return;
    let live = true;
    setLoading(true);
    void load().then((r) => {
      if (live) {
        setResult(r);
        setLoading(false);
      }
    });
    return () => {
      live = false;
    };
    // `load` is stable by construction at each call site (a bound api call).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [when, tick]);
  return { result, loading, reload: () => setTick((n) => n + 1) };
}

/** The honest unknown line: a state word, never a guess. */
function Unknown({ failure }: { failure: CompanionFailure }) {
  return (
    <p className="fd-companion-unknown" role="status">
      <span aria-hidden="true">○ </span>
      <span className="fd-companion-unknown-word">Unknown</span>
      {" · "}
      <span>{failure.text}</span>
    </p>
  );
}

function Health({ open }: { open: boolean }) {
  const { result, loading } = useFetch<HealthView>(() => companionApi.health(), open);
  if (loading && !result) return <p className="fd-companion-health">Checking Companion…</p>;
  if (!result) return null;
  if (!result.ok) return <Unknown failure={result.failure} />;
  return (
    <p className="fd-companion-health">
      <span aria-hidden="true">● </span>
      {healthLine(result.data)}
    </p>
  );
}

function ItemList({ items }: { items: ContextItem[] }) {
  if (items.length === 0) return <p className="fd-companion-none">Nothing.</p>;
  return (
    <ul className="fd-companion-items">
      {items.map((i, n) => (
        <li key={n}>
          <span>{i.text}</span> <span className="fd-companion-src">{i.source}{i.when ? ` · ${i.when}` : ""}</span>
        </li>
      ))}
    </ul>
  );
}

/** What Companion would see right now: section counts, then the items, then every UNKNOWN line. Read-only. */
function Sees() {
  const [open, setOpen] = useState(false);
  const { result, loading } = useFetch<ContextView>(() => companionApi.context(""), open);
  const data = result && result.ok ? result.data : null;
  return (
    <details className="fd-companion-sees" onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary>What Companion sees</summary>
      {loading && !result && <p>Looking…</p>}
      {result && !result.ok && <Unknown failure={result.failure} />}
      {data && (
        <div className="fd-companion-sees-body">
          <p className="fd-companion-counts">{SECTIONS.map((s) => `${s.label} ${data[s.key].length}`).join(" · ")}</p>
          {SECTIONS.map((s) => (
            <section key={s.key} aria-label={s.label}>
              <h4 className="fd-companion-h4">{s.label}</h4>
              <ItemList items={data[s.key]} />
            </section>
          ))}
          <section aria-label="Unknown">
            <h4 className="fd-companion-h4">Unknown</h4>
            {data.unknown.length === 0 ? <p className="fd-companion-none">Nothing is unknown.</p> : <ul className="fd-companion-items">{data.unknown.map((u, n) => <li key={n}>{u}</li>)}</ul>}
          </section>
        </div>
      )}
    </details>
  );
}

/** Deeper access. Worlds only asks and shows state; approving happens in Project Home and Worlds never decides it. */
function Grants() {
  const { grant, setGrant } = useCompanion();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const reasonId = useId();

  const apply = (r: Result<GrantView>) => {
    if (r.ok) {
      setGrant(r.data);
      setNote("");
    } else setNote(r.failure.kind === "unknown" && r.failure.reason === "refused" ? "Deeper access isn't available yet." : r.failure.text);
  };
  const ask = async (e: FormEvent) => {
    e.preventDefault();
    if (!reason.trim() || busy) return;
    setBusy(true);
    apply(await companionApi.requestGrant(reason.trim()));
    setBusy(false);
  };

  const active = grant?.state === "active";
  const when = active && grant?.expires_at ? formatClock(grant.expires_at) : null;
  const link = safeHref(grant?.link);
  return (
    <section className="fd-companion-grants" aria-label="Deeper access">
      <h3 className="fd-companion-h3">Deeper access</h3>
      <p className="fd-companion-grant-state" role="status">
        {active ? (when ? `Active until ${when}.` : "Active.") : grant?.state === "pending" ? "Waiting for you to approve it." : grant && ["denied", "expired", "revoked"].includes(grant.state) ? `Not active (${grant.state}).` : "Not active."}
      </p>
      {grant?.state === "pending" && (
        <p>
          {link ? (
            <a className="fd-btn" href={link}>
              Approve it in Project Home
            </a>
          ) : (
            "Approve it in Project Home."
          )}
        </p>
      )}
      {(grant?.state === "pending" || active) && grant?.grant_id && (
        <div className="fd-companion-row">
          <button type="button" className="fd-btn fd-btn--quiet" disabled={busy} onClick={async () => { setBusy(true); apply(await companionApi.grant(grant.grant_id!)); setBusy(false); }}>
            Check again
          </button>
          <button type="button" className="fd-btn fd-btn--quiet" disabled={busy} onClick={async () => { setBusy(true); apply(await companionApi.revokeGrant(grant.grant_id!)); setBusy(false); }}>
            Stop it
          </button>
        </div>
      )}
      {!active && grant?.state !== "pending" && (
        <form onSubmit={ask} className="fd-companion-ask">
          <label htmlFor={reasonId} className="fd-label">
            Why do you want Companion to see more?
          </label>
          <input id={reasonId} className="fd-input" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} />
          <button type="submit" className="fd-btn" disabled={busy || !reason.trim()}>
            Ask for deeper access
          </button>
        </form>
      )}
      <p className="fd-companion-note" role="status">{note}</p>
    </section>
  );
}

/** Read-only view of an old thread: same turn components, no composer. */
function OldThreadView({ threadId, onBack, backRef }: { threadId: string; onBack: () => void; backRef: React.RefObject<HTMLButtonElement | null> }) {
  const [turns, setTurns] = useState<StoredTurn[] | null>(null);
  const [failure, setFailure] = useState<CompanionFailure | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let live = true;
    setLoading(true);
    void companionApi.thread(threadId).then((r) => {
      if (!live) return;
      setLoading(false);
      if (r.ok) {
        setTurns(r.data.turns);
        setFailure(null);
      } else {
        setTurns(null);
        setFailure(r.failure);
      }
    });
    return () => { live = false; };
  }, [threadId]);

  return (
    <section className="fd-companion-readonly" aria-label="Earlier conversation">
      <div className="fd-companion-readonly-head">
        <button type="button" className="fd-btn fd-btn--quiet" ref={backRef} onClick={onBack}>
          ← Back to the current conversation
        </button>
      </div>
      {loading && <p className="fd-companion-readonly-status">Loading conversation…</p>}
      {failure && <Unknown failure={failure} />}
      {turns && turns.length === 0 && <p className="fd-companion-readonly-status">This conversation has no turns.</p>}
      {turns && turns.length > 0 && (
        <ol className="fd-companion-thread" aria-label="Earlier conversation">
          {turns.map((t, i) => (
            <li key={i} className="fd-companion-turn">
              <p className="fd-companion-you"><span className="fd-companion-who">You</span> {t.user_text}</p>
              <div className="fd-companion-reply">
                <p><span className="fd-companion-who">Companion</span> {t.assistant_text}</p>
                {t.visibility_tier && <p className="fd-companion-tier">Level: {t.visibility_tier}</p>}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

/**
 * "Earlier conversations": a native <details> that loads thread ids on open (lazily, once).
 * Shows a plain label for each thread ("Conversation N"). Choosing one shows that thread
 * read-only in the same turn components. The live thread is excluded from the list using
 * the id the turn response carried; before any turn, nothing is excluded.
 */
function EarlierConversations({
  onViewThread,
  viewingOldThread,
  summaryRef,
}: {
  onViewThread: (id: string) => void;
  viewingOldThread: boolean;
  summaryRef: React.RefObject<HTMLElement | null>;
}) {
  const { liveThreadId } = useCompanion();
  const [open, setOpen] = useState(false);
  const [threads, setThreads] = useState<string[] | null>(null);
  const [failure, setFailure] = useState<CompanionFailure | null>(null);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!open || loaded) return;
    let live = true;
    setLoading(true);
    void companionApi.threads().then((r) => {
      if (!live) return;
      setLoading(false);
      setLoaded(true);
      if (r.ok) {
        // Exclude only the live conversation's id (carried by the turn response).
        // Before any turn, liveThreadId is null so nothing is excluded.
        const oldThreads = liveThreadId ? r.data.threads.filter((id) => id !== liveThreadId) : r.data.threads;
        setThreads(oldThreads);
        setFailure(null);
      } else {
        setThreads(null);
        setFailure(r.failure);
      }
    });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, loaded]);

  // If the live id changes AFTER we loaded (a new turn landed, or New conversation),
  // refresh the list so the filter stays honest. The first-run ref keeps us from
  // re-fetching on the initial transition into the loaded state.
  const firstRunRef = useRef(true);
  useEffect(() => {
    if (firstRunRef.current) {
      firstRunRef.current = false;
      return;
    }
    if (!loaded || threads === null) return;
    void companionApi.threads().then((r) => {
      if (!r.ok) return;
      const oldThreads = liveThreadId ? r.data.threads.filter((id) => id !== liveThreadId) : r.data.threads;
      setThreads(oldThreads);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveThreadId]);

  if (viewingOldThread) return null;

  return (
    <details className="fd-companion-earlier" onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary ref={summaryRef as React.RefObject<HTMLElement>}>Earlier conversations</summary>
      {loading && !threads && <p className="fd-companion-earlier-status">Loading…</p>}
      {failure && (
        <div className="fd-companion-earlier-problem">
          <Unknown failure={failure} />
          <button type="button" className="fd-btn fd-btn--quiet" onClick={() => { setLoaded(false); setFailure(null); }}>
            Try again
          </button>
        </div>
      )}
      {threads && threads.length === 0 && <p className="fd-companion-earlier-status">No earlier conversations.</p>}
      {threads && threads.length > 0 && (
        <ul className="fd-companion-earlier-list">
          {threads.map((id, i) => (
            <li key={id}>
              <button type="button" className="fd-companion-earlier-item" onClick={() => onViewThread(id)}>
                <span className="fd-companion-earlier-label">Conversation {i + 1}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}

/**
 * The Companion panel: a native modal dialog (the page behind it is inert, focus is trapped and returned by the browser,
 * Escape closes it). A side panel on a desktop, a full-height sheet on a phone. It is not a landmark.
 */
export function CompanionPanel() {
  const { open, setOpen, presentation, thinking, turns, failure, pending, send, retry, newConversation } = useCompanion();
  const ref = useRef<HTMLDialogElement>(null);
  const [draft, setDraft] = useState("");
  const titleId = useId();
  const fieldId = useId();
  const listRef = useRef<HTMLOListElement>(null);
  const [oldThreadId, setOldThreadId] = useState<string | null>(null);
  const backBtnRef = useRef<HTMLButtonElement>(null);
  const earlierSummaryRef = useRef<HTMLElement>(null);
  const wasViewingOldRef = useRef(false);

  // Layout effect: close before React removes the node, so focus goes back to the button that opened it.
  useLayoutEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  useEffect(() => {
    listRef.current?.lastElementChild?.scrollIntoView?.({ block: "nearest" });
  }, [turns.length]);

  // Focus the back button when switching to an old thread; focus the Earlier
  // conversations summary when coming back (the summary is the control the
  // person used to get there; the <details> may have re-closed, that's fine).
  useEffect(() => {
    if (oldThreadId) {
      wasViewingOldRef.current = true;
      backBtnRef.current?.focus();
    } else if (wasViewingOldRef.current) {
      wasViewingOldRef.current = false;
      // Wait a tick so the summary is in the DOM after EarlierConversations re-renders.
      const id = setTimeout(() => {
        earlierSummaryRef.current?.focus();
      }, 0);
      return () => clearTimeout(id);
    }
  }, [oldThreadId]);

  // Reset old thread view when closing the panel
  useEffect(() => {
    if (!open) {
      setOldThreadId(null);
      wasViewingOldRef.current = false;
    }
  }, [open]);

  const pose = poseFor(presentation);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text || thinking) return;
    setDraft("");
    await send(text);
  };

  return (
    <dialog ref={ref} className="fd-companion" aria-labelledby={titleId} onCancel={(e) => { e.preventDefault(); setOpen(false); }} onClose={() => setOpen(false)}>
      <div className="fd-companion-inner">
        <header className="fd-companion-head">
          <h2 id={titleId} className="fd-companion-title">
            Companion
          </h2>
          <button type="button" className="fd-btn fd-btn--quiet" onClick={() => setOpen(false)}>
            Close
          </button>
        </header>

        {oldThreadId ? (
          <OldThreadView threadId={oldThreadId} onBack={() => setOldThreadId(null)} backRef={backBtnRef} />
        ) : (
          <>
            <p className="fd-companion-pose">
              <span className="fd-companion-mark" aria-hidden="true">
                {pose.mark}
              </span>
              <span>{pose.word}</span>
            </p>
            <Health open={open} />

            <ol ref={listRef} className="fd-companion-thread" aria-label="Conversation">
              {turns.length === 0 && <li className="fd-companion-empty">Say hello. Nothing is kept here: the conversation lives with Companion.</li>}
              {turns.map((t) => (
                <li key={t.key} className="fd-companion-turn">
                  <p className="fd-companion-you"><span className="fd-companion-who">You</span> {t.user}</p>
                  {t.reply !== null && (
                    <div className="fd-companion-reply">
                      <p><span className="fd-companion-who">Companion</span> {t.reply}</p>
                      {t.unknown.length > 0 && <p className="fd-companion-withheld">Some things were withheld: {t.unknown.join("; ")}</p>}
                      {t.tier && <p className="fd-companion-tier">Level: {t.tier}</p>}
                    </div>
                  )}
                </li>
              ))}
            </ol>

            <p className="fd-sr" role="status">{thinking ? "Companion is thinking…" : ""}</p>
            {thinking && <p className="fd-companion-thinking" aria-hidden="true">Thinking…</p>}
            {failure && failure.kind !== "invalid" && (
              <div className="fd-companion-problem">
                <Unknown failure={failure} />
                {pending && (
                  <button type="button" className="fd-btn" onClick={() => void retry()}>
                    Try again
                  </button>
                )}
              </div>
            )}
            {failure?.kind === "invalid" && <p className="fd-companion-problem" role="alert">{failure.text}</p>}

            <form onSubmit={submit} className="fd-companion-composer">
              <label htmlFor={fieldId} className="fd-label">
                Message to Companion
              </label>
              <textarea id={fieldId} className="fd-input fd-companion-field" rows={3} value={draft} maxLength={8000} onChange={(e) => setDraft(e.target.value)} />
              <div className="fd-companion-row">
                <button type="submit" className="fd-btn fd-btn--primary" disabled={thinking || !draft.trim()}>
                  Send
                </button>
                <button type="button" className="fd-btn fd-btn--quiet" onClick={newConversation} disabled={thinking || turns.length === 0}>
                  New conversation
                </button>
              </div>
            </form>

            <Sees />
            <Grants />
            <EarlierConversations onViewThread={setOldThreadId} viewingOldThread={!!oldThreadId} summaryRef={earlierSummaryRef} />
          </>
        )}
      </div>
    </dialog>
  );
}
