import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  MEMORY_ALL_KEYS,
  MEMORY_KEYS,
  createMemoryRow,
  deleteMemoryRow,
  findMemoryRows,
  patchMemoryRow,
  runMemoryBackup,
  startMemoryExport,
  useMemoryData,
} from "./api";
import { Tabs, type TabDef } from "./Tabs";
import type {
  MemoryBackupResult,
  MemoryFindRow,
  MemoryHistoryRow,
  MemoryKeptRow,
  MemoryLaterRow,
  MemoryLockedRow,
  MemoryRecordsRow,
  MemoryRow,
  MemoryTable,
} from "./types";
import { formatHistoryStamp, formatMemoryStamp } from "./time";
import "./fd.css";

/** A short, plain excerpt of a body: at most 140 chars, collapsed whitespace. */
function bodyExcerpt(body: string | null | undefined): string {
  if (!body) return "";
  const flat = body.replace(/\s+/g, " ").trim();
  return flat.length > 140 ? flat.slice(0, 137) + "…" : flat;
}

/** The row's title if it has one; otherwise the generic "this row". */
function rowTitle(row: MemoryRow): string {
  if ("title" in row && typeof (row as { title?: unknown }).title === "string") return (row as { title: string }).title;
  return "this row";
}

/** Human-readable provenance when it isn't the owner's deliberate keep. */
function provenanceLabel(provenance: string): string | null {
  if (provenance === "owner") return null;
  if (provenance === "external_ref") return "From an external reference";
  if (provenance === "suggestion") return "Suggestion";
  return provenance;
}

/** Plain words for a Later status. */
function statusLabel(status: string): string {
  if (status === "open") return "Open";
  if (status === "done") return "Done";
  if (status === "dropped") return "Dropped";
  return status;
}

/** A small labelled input used across the forms. */
function Field({ id, label, value, onChange, type = "text", placeholder, multiline }: {
  id: string; label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string; multiline?: boolean;
}) {
  return (
    <div className="fd-field">
      <label htmlFor={id} className="fd-label">{label}</label>
      {multiline ? (
        <textarea id={id} className="fd-input fd-textarea" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} rows={3} />
      ) : (
        <input id={id} type={type} className="fd-input" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} autoComplete="off" />
      )}
    </div>
  );
}

function Select({ id, label, value, onChange, options }: {
  id: string; label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[];
}) {
  return (
    <div className="fd-field">
      <label htmlFor={id} className="fd-label">{label}</label>
      <select id={id} className="fd-input" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

/** A delete or backup confirmation dialog. Follows RunDialog exactly. */
function ConfirmDialog({ id, title, consequence, safe, act, onConfirm, onCancel }: {
  id: string; title: string; consequence: string; safe: string; act: string;
  onConfirm: () => void; onCancel: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useLayoutEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
    return () => { if (d?.open) d.close(); };
  }, []);
  // jsdom does not fire the `cancel` event on Escape, so handle Escape explicitly.
  // On a real browser both paths run; the native cancel event still fires first and is harmless.
  const onKey = (e: KeyboardEvent<HTMLDialogElement>) => {
    if (e.key === "Escape") { e.preventDefault(); onCancel(); }
  };
  return (
    <dialog
      id={id}
      ref={ref}
      aria-labelledby={`${id}-title`}
      className="fd-dialog"
      onCancel={(event) => { event.preventDefault(); onCancel(); }}
      onKeyDown={onKey}
    >
      <h2 id={`${id}-title`} className="fd-dialog-title">{title}</h2>
      <p className="fd-dialog-consequence">{consequence}</p>
      <div className="fd-dialog-actions">
        <button type="button" className="fd-btn fd-btn--primary" autoFocus onClick={onCancel}>{safe}</button>
        <button type="button" className="fd-btn" onClick={onConfirm}>{act}</button>
      </div>
    </dialog>
  );
}

/**
 * The form for a Kept/Later/Records row. `initial` null means create.
 * Sends only that table's settable fields (and, on create, provenance/source_ref).
 */
function RowForm({ table, initial, onCancel, onSaved }: {
  table: MemoryTable;
  initial: MemoryKeptRow | MemoryLaterRow | MemoryRecordsRow | null;
  onCancel: () => void;
  onSaved: (row: MemoryRow) => void;
}) {
  const qc = useQueryClient();
  const creating = initial === null;

  const [title, setTitle] = useState(initial?.title ?? "");
  const [body, setBody] = useState(initial?.body ?? "");
  const [tagsText, setTagsText] = useState(initial?.table === "kept" ? (initial.tags ?? []).join(", ") : "");
  const [dueAtText, setDueAtText] = useState(initial?.table === "later" && initial.due_at ? formatMemoryStamp(initial.due_at) ?? "" : "");
  const [kind, setKind] = useState(initial?.table === "records" ? initial.kind ?? "" : "");
  const [sensitivity, setSensitivity] = useState<"normal" | "locked">(initial?.table === "records" ? (initial.sensitivity as "normal" | "locked") : "normal");
  const [provenance, setProvenance] = useState<string>(initial?.provenance ?? "owner");
  const [sourceRef, setSourceRef] = useState(initial?.source_ref ?? "");

  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const baseId = useId();
  const titleId = `${baseId}-title`;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) { setErr("A title is needed."); return; }
    setBusy(true); setErr(null);
    try {
      let row: MemoryRow;
      if (creating) {
        const payload: Record<string, unknown> = { title: title.trim(), body };
        if (table === "kept") payload.tags = tagsText.split(",").map((t) => t.trim()).filter(Boolean);
        if (table === "later" && dueAtText.trim()) {
          const parsed = Date.parse(dueAtText.trim());
          if (Number.isNaN(parsed)) throw new Error("due_at must be a date");
          payload.due_at = parsed / 1000;
        }
        if (table === "records") { payload.kind = kind || null; payload.sensitivity = sensitivity; }
        if (provenance !== "owner") {
          payload.provenance = provenance;
          if (provenance === "external_ref" && sourceRef.trim()) payload.source_ref = sourceRef.trim();
        }
        row = await createMemoryRow(table, payload);
      } else {
        // PATCH: send only the changed fields.
        const patch: Record<string, unknown> = {};
        if (title.trim() !== (initial?.title ?? "")) patch.title = title.trim();
        if (body !== (initial?.body ?? "")) patch.body = body;
        if (table === "kept") {
          const prev = (initial as MemoryKeptRow).tags ?? [];
          const next = tagsText.split(",").map((t) => t.trim()).filter(Boolean);
          if (JSON.stringify(prev) !== JSON.stringify(next)) patch.tags = next;
        }
        if (table === "later") {
          const prevDue = (initial as MemoryLaterRow).due_at;
          if (dueAtText.trim()) {
            const parsed = Date.parse(dueAtText.trim());
            if (!Number.isNaN(parsed) && parsed / 1000 !== prevDue) patch.due_at = parsed / 1000;
          } else if (prevDue != null) patch.due_at = null;
        }
        if (table === "records") {
          const rec = initial as MemoryRecordsRow;
          if ((kind || null) !== (rec.kind ?? null)) patch.kind = kind || null;
          if (sensitivity !== rec.sensitivity) patch.sensitivity = sensitivity;
        }
        if (!Object.keys(patch).length) { onCancel(); return; }
        row = await patchMemoryRow(table, initial!.id, patch);
      }
      await Promise.all(MEMORY_ALL_KEYS.map((k) => qc.invalidateQueries({ queryKey: k as string[] })));
      onSaved(row);
    } catch (e) {
      if (e instanceof ApiError) setErr(e.detail || `Couldn't save (${e.status ?? e.errorClass}).`);
      else setErr(e instanceof Error ? e.message : "Couldn't save.");
    } finally { setBusy(false); }
  };

  return (
    <form className="fd-connect-form fd-memory-form" onSubmit={submit}>
      <Field id={titleId} label="Title" value={title} onChange={setTitle} />
      <Field id={`${baseId}-body`} label="Body" value={body} onChange={setBody} multiline />
      {table === "kept" && <Field id={`${baseId}-tags`} label="Tags (comma separated)" value={tagsText} onChange={setTagsText} placeholder="house, weekend" />}
      {table === "later" && <Field id={`${baseId}-due`} label="Due (e.g. 2 Oct 2026)" value={dueAtText} onChange={setDueAtText} />}
      {table === "records" && (
        <>
          <Field id={`${baseId}-kind`} label="Kind" value={kind} onChange={setKind} placeholder="health" />
          <Select id={`${baseId}-sens`} label="Sensitivity" value={sensitivity} onChange={(v) => setSensitivity(v as "normal" | "locked")}
            options={[{ value: "normal", label: "normal" }, { value: "locked", label: "locked" }]} />
        </>
      )}
      {creating && (
        <>
          <Select id={`${baseId}-prov`} label="Provenance" value={provenance} onChange={(v) => setProvenance(v)}
            options={[{ value: "owner", label: "Owner" }, { value: "external_ref", label: "External reference" }, { value: "suggestion", label: "Suggestion" }]} />
          {provenance === "external_ref" && <Field id={`${baseId}-ref`} label="Source reference" value={sourceRef} onChange={setSourceRef} placeholder="https://example.test/..." />}
        </>
      )}
      {err && <p role="alert" className="fd-connect-err">{err}</p>}
      <div className="fd-connect-actions">
        <button type="submit" className="fd-btn fd-btn--primary" disabled={busy}>{creating ? "Add" : "Save"}</button>
        <button type="button" className="fd-btn" onClick={onCancel} disabled={busy}>Cancel</button>
      </div>
    </form>
  );
}

/**
 * One Memory row. Renders the title, the short body, the relevant fields (tags, status,
 * due_at, kind, sensitivity), the provenance label when it isn't `owner`, and the
 * updated_at stamp. Edit/Delete per row. Locked records render as a locked placeholder.
 */
function RowCard({ row, onEdit, onDelete, onStatusChange, invokeRef }: {
  row: MemoryRow;
  onEdit: (row: MemoryRow) => void;
  onDelete: (row: MemoryRow, invoke: HTMLButtonElement) => void;
  onStatusChange: (row: MemoryLaterRow, next: "open" | "done" | "dropped") => void;
  invokeRef: (el: HTMLButtonElement | null) => void;
}) {
  if (row.table === "records" && "locked" in row) {
    const locked = row as MemoryLockedRow;
    return (
      <li className="fd-memory-row fd-memory-row--locked">
        <div className="fd-memory-row-head">
          <span className="fd-memory-shape" aria-hidden="true">🔒</span>
          <span className="fd-memory-title">Locked record</span>
          <span className="fd-memory-sensitivity fd-memory-sensitivity--locked">Locked</span>
        </div>
        <p className="fd-sentence">This record is locked. It needs the owner to step up before it can be opened.</p>
        <p className="fd-memory-meta">Recorded {formatMemoryStamp(locked.created_at) ?? "unknown date"}</p>
      </li>
    );
  }

  const common = row as MemoryKeptRow | MemoryLaterRow | MemoryRecordsRow;
  const prov = provenanceLabel(common.provenance);
  return (
    <li className="fd-memory-row">
      <div className="fd-memory-row-head">
        <span className="fd-memory-title">{common.title}</span>
        {row.table === "records" && (
          <span className={`fd-memory-sensitivity fd-memory-sensitivity--${(row as MemoryRecordsRow).sensitivity}`}>
            {(row as MemoryRecordsRow).sensitivity === "locked" ? "🔒 Locked" : "Normal"}
          </span>
        )}
      </div>
      {common.body && <p className="fd-memory-body">{bodyExcerpt(common.body)}</p>}
      <div className="fd-memory-meta-row">
        {row.table === "kept" && (row as MemoryKeptRow).tags.length > 0 && (
          <span className="fd-memory-tags">{(row as MemoryKeptRow).tags.map((t) => <span key={t} className="fd-memory-tag">{t}</span>)}</span>
        )}
        {row.table === "later" && (
          <>
            <span className="fd-memory-status">Status: <strong>{statusLabel((row as MemoryLaterRow).status)}</strong></span>
            {(row as MemoryLaterRow).due_at && <span className="fd-memory-due">Due {formatMemoryStamp((row as MemoryLaterRow).due_at)}</span>}
          </>
        )}
        {row.table === "records" && (row as MemoryRecordsRow).kind && <span className="fd-memory-kind">Kind: {(row as MemoryRecordsRow).kind}</span>}
        {prov && <span className="fd-memory-provenance">{prov}</span>}
        <span className="fd-memory-stamp">Updated {formatMemoryStamp(common.updated_at) ?? "unknown"}</span>
      </div>
      <div className="fd-memory-actions">
        {row.table === "later" && (
          <label className="fd-memory-status-picker">
            <span className="fd-sr">Change status</span>
            <select
              aria-label={`Change status for ${common.title}`}
              value={(row as MemoryLaterRow).status}
              onChange={(e) => onStatusChange(row as MemoryLaterRow, e.target.value as "open" | "done" | "dropped")}
              className="fd-input fd-memory-status-select"
            >
              <option value="open">Open</option>
              <option value="done">Done</option>
              <option value="dropped">Dropped</option>
            </select>
          </label>
        )}
        <button type="button" className="fd-btn" onClick={() => onEdit(row)}>Edit</button>
        <button type="button" className="fd-btn" ref={invokeRef} onClick={(e) => onDelete(row, e.currentTarget)}>Delete</button>
      </div>
    </li>
  );
}

/**
 * A list panel for one of Kept / Later / Records. Owns its own Add + Edit state, the Delete
 * confirmation dialog, and the plain-words loading / error / empty states. A failed refetch
 * keeps the previous data on screen marked with its age — it never blanks the tab.
 */
function ListTab({ table, rows, status, error, retry, empty }: {
  table: MemoryTable;
  rows: MemoryRow[];
  status: "loading" | "ok" | "error";
  error?: string;
  retry: () => void;
  empty: string;
}) {
  const qc = useQueryClient();
  // Retry: invalidate the query (clears any cached error) AND refetch.
  const doRetry = () => {
    const key = MEMORY_ALL_KEYS.find((k) => k[2] === table) as readonly string[];
    void qc.invalidateQueries({ queryKey: key as string[] });
    retry();
  };
  const [editing, setEditing] = useState<MemoryKeptRow | MemoryLaterRow | MemoryRecordsRow | null>(null);
  const [creating, setCreating] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<{ row: MemoryRow; invoke: HTMLButtonElement } | null>(null);
  const [outcome, setOutcome] = useState<string | null>(null);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const outcomeRef = useRef<HTMLParagraphElement | null>(null);

  const announce = (text: string) => {
    setOutcome(text);
    // clear after a moment so the next outcome can take its place
    setTimeout(() => setOutcome((cur) => (cur === text ? null : cur)), 6000);
  };

  const save = async (row: MemoryRow) => {
    setSaveErr(null);
    const label = rowTitle(row);
    announce(editing ? `Saved ${label}.` : `Added ${label}.`);
    setEditing(null);
    setCreating(false);
  };

  const doDelete = async () => {
    if (!pendingDelete) return;
    const { row, invoke } = pendingDelete;
    setPendingDelete(null);
    try {
      // The actual table for a row is `row.table`, not the tab's table (defensive).
      await deleteMemoryRow(row.table as MemoryTable, row.id);
      await Promise.all(MEMORY_ALL_KEYS.map((k) => qc.invalidateQueries({ queryKey: k as string[] })));
      announce(`Removed ${rowTitle(row)}.`);
      // focus returns to the invoking control through the dialog's close() handler
      invoke.focus();
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 404) setSaveErr("That row is gone.");
        else if (e.status === 403 && e.detail === "step_up_required") setSaveErr("A locked record needs the owner to step up.");
        else setSaveErr(e.detail || "Couldn't delete.");
      } else setSaveErr("Couldn't delete.");
    }
  };

  const changeStatus = async (row: MemoryLaterRow, next: "open" | "done" | "dropped") => {
    if (next === row.status) return;
    setSaveErr(null);
    try {
      await patchMemoryRow("later", row.id, { status: next });
      await Promise.all(MEMORY_ALL_KEYS.map((k) => qc.invalidateQueries({ queryKey: k as string[] })));
      announce(`${row.title} marked ${next}.`);
    } catch (e) {
      if (e instanceof ApiError) setSaveErr(e.detail || "Couldn't change status.");
      else setSaveErr("Couldn't change status.");
    }
  };

  if (status === "loading" && rows.length === 0) return <p className="fd-sentence">Loading…</p>;

  return (
    <div className="fd-memory-list">
      <p role="status" ref={outcomeRef} aria-live="polite" className="fd-memory-outcome">{outcome ?? ""}</p>
      {saveErr && <p role="alert" className="fd-connect-err">{saveErr}</p>}
      {status === "error" && rows.length === 0 && (
        <div className="fd-connect-status">
          <p className="fd-sentence">{error ?? "Couldn't load."}</p>
          <button type="button" className="fd-btn" onClick={doRetry}>Retry</button>
        </div>
      )}
      {status === "error" && rows.length > 0 && (
        <p className="fd-connect-note">Couldn't refresh — showing the last known list.</p>
      )}
      {(creating || editing) && (
        <RowForm
          table={table}
          initial={editing}
          onCancel={() => { setEditing(null); setCreating(false); setSaveErr(null); }}
          onSaved={save}
        />
      )}
      {!creating && !editing && rows.length === 0 && status !== "error" && (
        <div>
          <p className="fd-sentence">{empty}</p>
          <button type="button" className="fd-btn fd-btn--primary" onClick={() => { setCreating(true); setEditing(null); setSaveErr(null); }}>Add</button>
        </div>
      )}
      {!creating && !editing && rows.length > 0 && (
        <ul className="fd-memory-rows">
          {rows.map((row) => (
            <RowCard
              key={row.id}
              row={row}
              onEdit={(r) => { setEditing(r as MemoryKeptRow | MemoryLaterRow | MemoryRecordsRow); setCreating(false); setSaveErr(null); }}
              onDelete={(r, invoke) => setPendingDelete({ row: r, invoke })}
              onStatusChange={changeStatus}
              invokeRef={() => { /* focus handled on delete */ }}
            />
          ))}
        </ul>
      )}
      {!creating && !editing && rows.length > 0 && (
        <button type="button" className="fd-btn fd-btn--primary" onClick={() => { setCreating(true); setEditing(null); setSaveErr(null); }}>Add</button>
      )}
      {pendingDelete && (
        <ConfirmDialog
          id="memory-delete-dialog"
          title={`Remove ${rowTitle(pendingDelete.row)}?`}
          consequence="It will be removed for good. There is no undo."
          safe="Keep it"
          act="Remove"
          onConfirm={doDelete}
          onCancel={() => { const inv = pendingDelete.invoke; setPendingDelete(null); inv.focus(); }}
        />
      )}
    </div>
  );
}

/**
 * History tab: an append-only log. No add/edit/delete, no mutating control at all.
 * Shows when it happened, the event, the table, the actor and the detail if any.
 * Export + Backup live here because they are about Memory as a whole.
 */
function HistoryTab({ rows, status, error, retry }: {
  rows: MemoryHistoryRow[];
  status: "loading" | "ok" | "error";
  error?: string;
  retry: () => void;
}) {
  const qc = useQueryClient();
  const doRetry = () => {
    void qc.invalidateQueries({ queryKey: MEMORY_KEYS.history as readonly string[] as string[] });
    retry();
  };
  const [exportNote, setExportNote] = useState<string | null>(null);
  const [backupNote, setBackupNote] = useState<string | null>(null);
  const [backupErr, setBackupErr] = useState<string | null>(null);
  const [askingBackup, setAskingBackup] = useState(false);
  const [busy, setBusy] = useState(false);
  const backupInvoke = useRef<HTMLButtonElement | null>(null);

  const doExport = (table: MemoryTable) => {
    const { href, filename } = startMemoryExport(table);
    const a = document.createElement("a");
    a.href = href;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setExportNote(`Started an export of ${table} as NDJSON.`);
    setTimeout(() => setExportNote((cur) => (cur?.startsWith(`Started an export of ${table}`) ? null : cur)), 6000);
  };

  const doBackup = async () => {
    setAskingBackup(false);
    setBusy(true); setBackupErr(null);
    try {
      const result: MemoryBackupResult = await runMemoryBackup();
      setBackupNote(`Backed up to ${result.file}.`);
    } catch (e) {
      if (e instanceof ApiError) setBackupErr(e.detail || "Couldn't back up.");
      else setBackupErr("Couldn't back up.");
    } finally {
      setBusy(false);
      backupInvoke.current?.focus();
    }
  };

  if (status === "loading" && rows.length === 0) return <p className="fd-sentence">Loading…</p>;

  return (
    <div className="fd-memory-history">
      <p className="fd-sentence">History is an append-only log of what happened. It cannot be edited.</p>
      {status === "error" && rows.length === 0 && (
        <div className="fd-connect-status">
          <p className="fd-sentence">{error ?? "Couldn't load."}</p>
          <button type="button" className="fd-btn" onClick={doRetry}>Retry</button>
        </div>
      )}
      {status === "error" && rows.length > 0 && (
        <p className="fd-connect-note">Couldn't refresh — showing the last known history.</p>
      )}
      {rows.length === 0 && status !== "error" && <p className="fd-sentence">No history yet.</p>}
      {rows.length > 0 && (
        <ul className="fd-memory-events">
          {rows.map((h) => (
            <li key={h.id} className="fd-memory-event">
              <span className="fd-memory-stamp">{formatHistoryStamp(h.at) ?? "unknown"}</span>
              <span className="fd-memory-event-name">{h.event}</span>
              {h.table && <span className="fd-memory-event-table">{h.table}</span>}
              <span className="fd-memory-event-actor">{h.actor}</span>
              {h.detail && <span className="fd-memory-event-detail">{JSON.stringify(h.detail)}</span>}
            </li>
          ))}
        </ul>
      )}
      <h2 className="fd-settings-section-title">Durability</h2>
      <p className="fd-sentence">Export one table as NDJSON, or take a dated backup of the whole memory database.</p>
      <div className="fd-memory-export-row">
        {(["kept", "later", "records"] as MemoryTable[]).map((t) => (
          <button key={t} type="button" className="fd-btn" onClick={() => doExport(t)}>Export {t}</button>
        ))}
      </div>
      {exportNote && <p role="status" aria-live="polite" className="fd-connect-note">{exportNote}</p>}
      <div className="fd-memory-backup-row">
        <button
          type="button"
          className="fd-btn fd-btn--primary"
          disabled={busy}
          ref={backupInvoke}
          onClick={() => setAskingBackup(true)}
        >
          Back up now
        </button>
      </div>
      {backupNote && <p role="status" aria-live="polite" className="fd-connect-note">{backupNote}</p>}
      {backupErr && <p role="alert" className="fd-connect-err">{backupErr}</p>}
      {askingBackup && (
        <ConfirmDialog
          id="memory-backup-dialog"
          title="Back up Memory now?"
          consequence="A dated copy of the memory database will be written to the backup directory."
          safe="Don't back up"
          act="Back up now"
          onConfirm={doBackup}
          onCancel={() => { setAskingBackup(false); backupInvoke.current?.focus(); }}
        />
      )}
    </div>
  );
}

/**
 * Find tab: a labelled search box. The server is the source of truth; results render in the
 * order returned and the «…» highlights are plain text. An empty query shows a prompt and
 * sends no request.
 */
function FindTab() {
  const [raw, setRaw] = useState("");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<MemoryFindRow[] | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [err, setErr] = useState<string | null>(null);
  const ctl = useRef<AbortController | null>(null);

  // Debounce: typing sets `raw`; 300ms later it becomes the actual `q`.
  useEffect(() => {
    const t = setTimeout(() => {
      const trimmed = raw.trim();
      setQ(trimmed);
    }, 300);
    return () => clearTimeout(t);
  }, [raw]);

  useEffect(() => {
    if (!q) { setRows(null); setStatus("idle"); setErr(null); return; }
    ctl.current?.abort();
    const c = new AbortController();
    ctl.current = c;
    setStatus("loading"); setErr(null);
    findMemoryRows(q).then((results) => {
      if (c.signal.aborted) return;
      setRows(results);
      setStatus("ok");
    }).catch((e) => {
      if (c.signal.aborted) return;
      if (e instanceof ApiError) setErr(e.detail || "Couldn't search.");
      else setErr("Couldn't search.");
      setStatus("error");
    });
    return () => c.abort();
  }, [q]);

  const inputId = useId();
  return (
    <div className="fd-find">
      <label htmlFor={inputId} className="fd-label">Search your Memory</label>
      <input
        id={inputId}
        type="search"
        className="fd-input"
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        placeholder="shed, call, health…"
        autoComplete="off"
      />
      {!q && <p className="fd-sentence">Type something to search. Results come from this device.</p>}
      {q && status === "loading" && <p className="fd-sentence">Searching…</p>}
      {q && status === "error" && <p role="alert" className="fd-connect-err">{err ?? "Couldn't search."}</p>}
      {q && status === "ok" && rows !== null && (
        <>
          {rows.length === 0 && <p className="fd-sentence">No matches.</p>}
          {rows.length > 0 && (
            <ul className="fd-memory-find-results">
              {rows.map((r) => (
                <li key={`${r.table}:${r.id}`} className="fd-memory-find-row">
                  <span className="fd-memory-find-table">{r.table}</span>
                  <span className="fd-memory-find-title">{r.title}</span>
                  <span className="fd-memory-find-snippet">{r.snippet}</span>
                  {r.sensitivity === "locked" && <span className="fd-memory-sensitivity fd-memory-sensitivity--locked">Locked</span>}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

/**
 * Memory: Kept, Later, Records, History, Find. Owner's own durable record — every tab talks
 * to /api/memory/*, with independent loads so one failure never hides the rest.
 */
export function Memory() {
  const data = useMemoryData();
  const tabs: TabDef[] = useMemo(() => ([
    {
      id: "kept", label: "Kept",
      panel: <ListTab table="kept" rows={data.kept} status={data.keptStatus} error={data.keptError} retry={data.refetchKept}
        empty="Nothing kept yet. Things you choose to keep will be here." />,
    },
    {
      id: "later", label: "Later",
      panel: <ListTab table="later" rows={data.later} status={data.laterStatus} error={data.laterError} retry={data.refetchLater}
        empty="Nothing set aside for later." />,
    },
    {
      id: "records", label: "Records",
      panel: <ListTab table="records" rows={data.records} status={data.recordsStatus} error={data.recordsError} retry={data.refetchRecords}
        empty="No records yet. Records you lock need step-up to open." />,
    },
    { id: "history", label: "History", panel: <HistoryTab rows={data.history} status={data.historyStatus} error={data.historyError} retry={data.refetchHistory} /> },
    { id: "find", label: "Find", panel: <FindTab /> },
  ]), [data]);

  return (
    <div className="fd-screen">
      <h1 className="fd-screen-title">Memory</h1>
      <Tabs label="Memory" tabs={tabs} />
    </div>
  );
}
