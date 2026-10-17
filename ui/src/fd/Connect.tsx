import { useId, useMemo, useRef, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  CONFIG_KEYS,
  fetchConfigItem,
  isWriteRequest,
  previewCard,
  saveConfigItem,
  tryConnect,
  useConnectData,
} from "./api";
import { Tabs, type TabDef } from "./Tabs";
import type {
  CardConfig,
  CardGroup,
  ConfigItem,
  ConfigKind,
  PreviewResult,
  Provider,
  Request as ConnRequest,
  RequestEffect,
  TryResult,
} from "./types";
import "./fd.css";

/**
 * Validation: C1 ids are lowercase alphanumerics plus hyphens, 1..63 chars, first char non-hyphen.
 * A request id is dotted <provider>.<name>, each segment validated separately.
 */
const ID_RE = /^[a-z0-9][a-z0-9-]{0,62}$/;
const SECRET_REF_RE = /^(env|vault):[A-Z_][A-Z0-9_]*$/;

function validId(id: string): boolean { return ID_RE.test(id); }
function validRequestId(id: string): boolean {
  const parts = id.split(".");
  return parts.length === 2 && parts.every((p) => ID_RE.test(p));
}

function outcomeText(outcome: string): string {
  if (outcome === "UNKNOWN") return "Unknown: the result was not confirmed";
  return outcome.charAt(0) + outcome.slice(1).toLowerCase();
}

/** Plain words for a source state + its shape. Never colour alone. */
function stateText(state: string): string {
  const table: Record<string, string> = {
    healthy: "Healthy",
    needs_attention: "Needs attention",
    degraded: "Degraded",
    unavailable: "Unavailable",
    stale: "Stale",
    unknown: "Unknown",
    not_configured: "Not configured",
  };
  return table[state] ?? "Unknown";
}

/**
 * Actions tab: the real GET /api/actions list and GET /api/receipts activity, both read-only.
 * Nothing here dispatches: a write action is named and marked, never offered a Run control.
 */
function ActionsPanel() {
  const data = useConnectData();

  return (
    <div className="fd-actions">
      <h2 className="fd-settings-section-title">Actions</h2>
      {data.actionsStatus === "loading" ? (
        <p className="fd-sentence">Loading actions…</p>
      ) : data.actionsStatus === "error" ? (
        <div className="fd-connect-status">
          <p className="fd-sentence">Couldn't load actions.</p>
          <button type="button" className="fd-btn" onClick={data.refetchActions}>Retry</button>
        </div>
      ) : data.actions.length === 0 ? (
        <p className="fd-sentence">Nothing connected yet.</p>
      ) : (
        <ul className="fd-bindings">
          {data.actions.map((action) => (
            <li key={action.id} className="fd-binding">
              <span className="fd-binding-name">{action.name}</span>
              <span className="fd-binding-access">{action.access === "read" ? "Read" : "Write"}</span>
              {action.scope !== undefined && <span className="fd-binding-access">scope: {action.scope}</span>}
              {action.exposed !== undefined && <span className="fd-binding-access">{action.exposed ? "Exposed" : "Not exposed"}</span>}
              {action.access === "write" && <span className="fd-connect-disabled-reason">needs an approved action</span>}
            </li>
          ))}
        </ul>
      )}

      <h2 className="fd-settings-section-title">Recent activity</h2>
      {data.receiptsStatus === "loading" ? (
        <p className="fd-sentence">Loading recent activity…</p>
      ) : data.receiptsStatus === "error" ? (
        <div className="fd-connect-status">
          <p className="fd-sentence">Couldn't load recent activity.</p>
          <button type="button" className="fd-btn" onClick={data.refetchReceipts}>Retry</button>
        </div>
      ) : data.receipts.length === 0 ? (
        <p className="fd-sentence">No activity yet. Nothing has run.</p>
      ) : (
        <ul className="fd-bindings">
          {data.receipts.map((receipt) => (
            <li key={receipt.id} className="fd-binding">
              <span className="fd-binding-name">{receipt.action}</span>
              <span className="fd-binding-access">{receipt.dispatch_state}</span>
              <span className="fd-binding-access">{outcomeText(receipt.outcome)}</span>
              {receipt.started_at && <span className="fd-binding-access">started {receipt.started_at}</span>}
              {receipt.finished_at && <span className="fd-binding-access">finished {receipt.finished_at}</span>}
              {receipt.redacted && <span className="fd-binding-access">Redacted</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** The secret_ref row: shows the reference NAME only, plus "Reference set" / "No reference". Never a value. */
function SecretRefRow({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  const id = useId();
  return (
    <div className="fd-secret-row">
      <span className="fd-secret-name">auth.secret_ref</span>
      <span className="fd-secret-state">{value ? "Reference set" : "No reference"}</span>
      <label htmlFor={id} className="fd-label">Reference (env:NAME or vault:NAME)</label>
      <input
        id={id}
        type="text"
        autoComplete="off"
        className="fd-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="env:EXAMPLE_TOKEN"
      />
    </div>
  );
}

/** A small labelled text field used in every form. */
function Field({ id, label, value, onChange, type = "text", placeholder }: {
  id: string; label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string;
}) {
  return (
    <div className="fd-field">
      <label htmlFor={id} className="fd-label">{label}</label>
      <input id={id} type={type} className="fd-input" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} autoComplete="off" />
    </div>
  );
}

function Checkbox({ id, label, checked, onChange }: { id: string; label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="fd-field">
      <label htmlFor={id} className="fd-label">
        <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} /> {label}
      </label>
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

/** Provider form. */
function ProviderForm({ initial, onSave, onCancel, creating }: {
  initial: Provider; onSave: (p: Provider) => Promise<void>; onCancel: () => void; creating: boolean;
}) {
  const [p, setP] = useState<Provider>(initial);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const setAuth = <K extends keyof Provider["auth"]>(k: K, v: Provider["auth"][K]) =>
    setP({ ...p, auth: { ...p.auth, [k]: v } });
  const setNetwork = (lan: boolean) => setP({ ...p, network: { ...(p.network ?? {}), lan } });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validId(p.id)) { setErr("Id must be lowercase alphanumerics plus hyphens, 1..63 chars."); return; }
    if (p.auth.secret_ref && !SECRET_REF_RE.test(p.auth.secret_ref)) {
      setErr("secret_ref must look like env:NAME or vault:NAME."); return;
    }
    if (p.auth.type === "header" && !p.auth.header_name) { setErr("Header auth needs a header name."); return; }
    setBusy(true); setErr(null);
    try { await onSave(p); }
    catch (e) { setErr(e instanceof Error ? e.message : "Couldn't save."); }
    finally { setBusy(false); }
  };

  return (
    <form className="fd-connect-form" onSubmit={submit}>
      <Field id="pf-id" label="Id" value={p.id} onChange={(v) => setP({ ...p, id: v })} />
      <Field id="pf-name" label="Name" value={p.name} onChange={(v) => setP({ ...p, name: v })} />
      <Select id="pf-kind" label="Kind" value={p.kind} onChange={(v) => setP({ ...p, kind: v as Provider["kind"] })}
        options={[{ value: "http", label: "http" }, { value: "room0", label: "room0" }, { value: "reference", label: "reference" }]} />
      <Field id="pf-base" label="base_url" value={p.base_url} onChange={(v) => setP({ ...p, base_url: v })} placeholder="https://example.test" />
      <Field id="pf-prefix" label="path_prefix" value={p.path_prefix ?? ""} onChange={(v) => setP({ ...p, path_prefix: v || undefined })} />
      <Select id="pf-auth-type" label="auth.type" value={p.auth.type} onChange={(v) => setAuth("type", v as Provider["auth"]["type"])}
        options={[
          { value: "none", label: "none" },
          { value: "bearer", label: "bearer" },
          { value: "header", label: "header" },
          { value: "basic", label: "basic" },
        ]} />
      {p.auth.type === "header" && (
        <Field id="pf-auth-header" label="auth.header_name" value={p.auth.header_name ?? ""} onChange={(v) => setAuth("header_name", v || undefined)} />
      )}
      <SecretRefRow value={p.auth.secret_ref ?? ""} onChange={(v) => setAuth("secret_ref", v || undefined)} />
      <Checkbox id="pf-lan" label="network.lan" checked={p.network?.lan ?? false} onChange={setNetwork} />
      <Checkbox id="pf-tls" label="tls_verify" checked={p.tls_verify ?? true} onChange={(v) => setP({ ...p, tls_verify: v })} />
      <Field id="pf-timeout" label="timeout_s" value={p.timeout_s?.toString() ?? ""} onChange={(v) => setP({ ...p, timeout_s: v ? Number(v) : undefined })} />
      {err && <p role="alert" className="fd-connect-err">{err}</p>}
      <div className="fd-connect-actions">
        <button type="submit" className="fd-btn fd-btn--primary" disabled={busy}>{creating ? "Create" : "Save"}</button>
        <button type="button" className="fd-btn" onClick={onCancel} disabled={busy}>Cancel</button>
      </div>
    </form>
  );
}

/** Request form with Try. Write-like requests disable Try and say why. */
function RequestForm({ initial, providers, onSave, onCancel, creating }: {
  initial: ConnRequest; providers: ConfigItem<Provider>[];
  onSave: (r: ConnRequest) => Promise<void>; onCancel: () => void; creating: boolean;
}) {
  const [r, setR] = useState<ConnRequest>(initial);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tryResult, setTryResult] = useState<TryResult | null>(null);
  const [tryErr, setTryErr] = useState<string | null>(null);
  const [trying, setTrying] = useState(false);
  const [rateWait, setRateWait] = useState<string | null>(null);
  const outcomeRef = useRef<HTMLDivElement | null>(null);

  const writeLike = useMemo(() => isWriteRequest(r), [r]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validRequestId(r.id)) { setErr("Request id must be <provider>.<name>, lowercase alphanumerics and hyphens."); return; }
    setBusy(true); setErr(null);
    try { await onSave(r); }
    catch (e) { setErr(e instanceof Error ? e.message : "Couldn't save."); }
    finally { setBusy(false); }
  };

  const doTry = async () => {
    if (!r.id || !r.provider || writeLike) return;
    setTrying(true); setTryResult(null); setTryErr(null); setRateWait(null);
    try {
      const provider = providers.find((p) => p.id === r.provider)?.object;
      const result = await tryConnect(provider ?? r.provider, r);
      setTryResult(result);
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setTryErr(e.detail || "This request needs an approved action.");
      } else if (e instanceof ApiError && e.status === 429) {
        setRateWait("Too many tries. Wait a moment.");
      } else {
        setTryErr("Couldn't try that request.");
      }
    } finally {
      setTrying(false);
    }
  };

  return (
    <form className="fd-connect-form" onSubmit={submit}>
      <Field id="rf-id" label="Id (<provider>.<name>)" value={r.id} onChange={(v) => setR({ ...r, id: v })} />
      <Select id="rf-provider" label="Provider" value={r.provider} onChange={(v) => setR({ ...r, provider: v })}
        options={[{ value: "", label: "—" }, ...providers.map((p) => ({ value: p.id, label: p.object.name || p.id }))]} />
      <Select id="rf-method" label="method" value={r.method} onChange={(v) => setR({ ...r, method: v as ConnRequest["method"] })}
        options={["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"].map((m) => ({ value: m, label: m }))} />
      <Field id="rf-path" label="path" value={r.path} onChange={(v) => setR({ ...r, path: v })} placeholder="/v1/queue" />
      <Select id="rf-effect" label="effect" value={r.effect} onChange={(v) => setR({ ...r, effect: v as RequestEffect })}
        options={[{ value: "auto", label: "auto" }, { value: "read", label: "read" }, { value: "write", label: "write" }]} />
      <Checkbox id="rf-known-safe" label="known_safe" checked={r.known_safe ?? false} onChange={(v) => setR({ ...r, known_safe: v })} />
      <Field id="rf-ttl" label="ttl_s" value={r.ttl_s?.toString() ?? ""} onChange={(v) => setR({ ...r, ttl_s: v ? Number(v) : undefined })} />
      <Field id="rf-timeout" label="timeout_s" value={r.timeout_s?.toString() ?? ""} onChange={(v) => setR({ ...r, timeout_s: v ? Number(v) : undefined })} />
      {err && <p role="alert" className="fd-connect-err">{err}</p>}
      <div className="fd-connect-actions">
        <button type="submit" className="fd-btn fd-btn--primary" disabled={busy}>{creating ? "Create" : "Save"}</button>
        <button type="button" className="fd-btn" onClick={onCancel} disabled={busy}>Cancel</button>
        {writeLike ? (
          <span className="fd-connect-disabled-reason" aria-label="Try unavailable">
            needs an approved action
          </span>
        ) : (
          <button type="button" className="fd-btn" onClick={doTry} disabled={trying || !r.provider}>
            {trying ? "Trying…" : "Try"}
          </button>
        )}
      </div>
      <TryOutcome result={tryResult} err={tryErr} rateWait={rateWait} ref={outcomeRef} />
    </form>
  );
}

/** Try outcome: plain words, sample as text, never HTML. */
const TryOutcome = ({ result, err, rateWait, ref }: {
  result: TryResult | null; err: string | null; rateWait: string | null; ref: React.RefObject<HTMLDivElement | null>;
}) => {
  if (rateWait) return <p role="status" className="fd-connect-note">{rateWait}</p>;
  if (err) return <p role="alert" className="fd-connect-err">{err}</p>;
  if (!result) return null;
  return (
    <div ref={ref} aria-live="polite" className="fd-try-outcome">
      <p className="fd-connect-note">
        {result.ok ? "Worked" : "Did not work"}
        {result.status_code !== undefined && <> · status {result.status_code}</>}
        {result.duration_ms !== undefined && <> · {result.duration_ms} ms</>}
      </p>
      {result.error_class && <p className="fd-connect-note">Error: {result.error_class.replace(/_/g, " ")}</p>}
      {result.note && <p className="fd-connect-note">{result.note}</p>}
      {result.truncated && <p className="fd-connect-note">Sample was cut short.</p>}
      {result.sample !== undefined && (
        <pre className="fd-try-sample">{result.sample}</pre>
      )}
      {result.suggested_fields && result.suggested_fields.length > 0 && (
        <div className="fd-try-suggested">
          <p className="fd-label">Suggested fields</p>
          <ul>
            {result.suggested_fields.map((f) => (
              <li key={f.path}><strong>{f.label}</strong> — <code>{f.path}</code>{f.format ? <> ({f.format})</> : null}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

/** Card form with Preview. Preview sends {card, sample} or {card, request: id}, never both. */
function CardForm({ initial, requests, onSave, onCancel, creating }: {
  initial: CardConfig; requests: ConfigItem<ConnRequest>[];
  onSave: (c: CardConfig) => Promise<void>; onCancel: () => void; creating: boolean;
}) {
  const [c, setC] = useState<CardConfig>(initial);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [previewErr, setPreviewErr] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [sampleInput, setSampleInput] = useState("");
  const previewRef = useRef<HTMLDivElement | null>(null);

  const readRequests = useMemo(
    () => requests.filter((r) => !isWriteRequest(r.object)),
    [requests],
  );

  const setMeaning = <K extends keyof CardConfig["meaning"]>(k: K, v: CardConfig["meaning"][K]) =>
    setC({ ...c, meaning: { ...c.meaning, [k]: v } });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validId(c.id)) { setErr("Id must be lowercase alphanumerics plus hyphens, 1..63 chars."); return; }
    setBusy(true); setErr(null);
    try { await onSave(c); }
    catch (e) { setErr(e instanceof Error ? e.message : "Couldn't save."); }
    finally { setBusy(false); }
  };

  const doPreview = async (mode: "sample" | "request") => {
    setPreviewing(true); setPreview(null); setPreviewErr(null);
    try {
      let result: PreviewResult;
      if (mode === "sample") {
        if (!sampleInput) { setPreviewErr("Paste a sample first."); setPreviewing(false); return; }
        result = await previewCard(c, { sample: sampleInput });
      } else {
        if (!c.request) { setPreviewErr("Pick a saved read request."); setPreviewing(false); return; }
        result = await previewCard(c, { request: c.request });
      }
      setPreview(result);
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 413) setPreviewErr("Sample is too large to preview.");
        else if (e.status === 422) setPreviewErr(e.detail || "That preview was refused.");
        else setPreviewErr("Couldn't preview that card.");
      } else {
        setPreviewErr("Couldn't preview that card.");
      }
    } finally { setPreviewing(false); }
  };

  return (
    <form className="fd-connect-form" onSubmit={submit}>
      <Field id="cf-id" label="Id" value={c.id} onChange={(v) => setC({ ...c, id: v })} />
      <Field id="cf-title" label="Title" value={c.title} onChange={(v) => setC({ ...c, title: v })} />
      <Field id="cf-icon" label="Icon" value={c.icon} onChange={(v) => setC({ ...c, icon: v })} />
      <Select id="cf-group" label="Group" value={c.group} onChange={(v) => setC({ ...c, group: v as CardGroup })}
        options={[{ value: "life", label: "life" }, { value: "machine", label: "machine" }]} />
      <Select id="cf-request" label="Request (saved id)" value={c.request ?? ""} onChange={(v) => setC({ ...c, request: v || undefined })}
        options={[{ value: "", label: "—" }, ...readRequests.map((r) => ({ value: r.id, label: r.id }))]} />
      <Select id="cf-view" label="View" value={c.view} onChange={(v) => setC({ ...c, view: v as CardConfig["view"] })}
        options={["stat", "list", "table", "status", "meter", "link", "markdown"].map((v) => ({ value: v, label: v }))} />
      <Field id="cf-concept" label="meaning.concept" value={c.meaning.concept ?? ""} onChange={(v) => setMeaning("concept", v || undefined)} />
      <Field id="cf-short" label="meaning.short" value={c.meaning.short} onChange={(v) => setMeaning("short", v)} />
      <Field id="cf-full" label="meaning.full" value={c.meaning.full} onChange={(v) => setMeaning("full", v)} />
      {err && <p role="alert" className="fd-connect-err">{err}</p>}
      <div className="fd-connect-actions">
        <button type="submit" className="fd-btn fd-btn--primary" disabled={busy}>{creating ? "Create" : "Save"}</button>
        <button type="button" className="fd-btn" onClick={onCancel} disabled={busy}>Cancel</button>
      </div>
      <div className="fd-preview-panel">
        <h3 className="fd-label">Preview card</h3>
        <p className="fd-sentence">Send the latest sample you fetched, or ask for a saved read request to run once.</p>
        <div className="fd-preview-controls">
          <label htmlFor="cf-sample" className="fd-label">Sample (text)</label>
          <textarea id="cf-sample" className="fd-input fd-textarea" rows={4} value={sampleInput} onChange={(e) => setSampleInput(e.target.value)} placeholder="Paste JSON here" />
          <div className="fd-connect-actions">
            <button type="button" className="fd-btn" onClick={() => doPreview("sample")} disabled={previewing}>
              {previewing ? "Previewing…" : "Preview with sample"}
            </button>
            <button type="button" className="fd-btn" onClick={() => doPreview("request")} disabled={previewing || !c.request}>
              {previewing ? "Previewing…" : "Preview from request"}
            </button>
          </div>
        </div>
        {previewErr && <p role="alert" className="fd-connect-err">{previewErr}</p>}
        {preview && <PreviewPanel result={preview} ref={previewRef} />}
      </div>
    </form>
  );
}

/** Preview panel: renders the C2 envelope. Unknown values become the word "unknown", never 0. */
const PreviewPanel = ({ result, ref }: { result: PreviewResult; ref: React.RefObject<HTMLDivElement | null> }) => {
  const stateWord = stateText(result.source_state);
  const valueText = (v: { text: string }) => (v.text === "" || v.text == null ? "unknown" : v.text);
  return (
    <div ref={ref} aria-live="polite" className="fd-preview-result">
      <p className="fd-connect-note">
        {stateWord} · {result.freshness}
        {result.last_good_at && <> · last good {result.last_good_at}</>}
      </p>
      {result.meter && <p className="fd-connect-note">Meter: {result.meter.text_equivalent}</p>}
      <dl className="fd-preview-values">
        {Object.entries(result.values).map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{valueText(v)}</dd>
          </div>
        ))}
        {Object.keys(result.values).length === 0 && <p className="fd-connect-note">No values.</p>}
      </dl>
      <details className="fd-preview-evidence">
        <summary>Evidence</summary>
        <ul>
          <li>request_id: {result.evidence.request_id}</li>
          <li>method: {result.evidence.method}</li>
          <li>path: {result.evidence.path}</li>
          {result.evidence.status_code !== undefined && <li>status_code: {result.evidence.status_code}</li>}
          {result.evidence.duration_ms !== undefined && <li>duration_ms: {result.evidence.duration_ms}</li>}
          {result.evidence.error_class && <li>error_class: {result.evidence.error_class}</li>}
          {result.evidence.note && <li>note: {result.evidence.note}</li>}
        </ul>
      </details>
    </div>
  );
};

/** A generic list editor: rows open a form, plus a New row. */
function ListPanel<T extends { id: string }>({ kind, items, status, error, retry, empty, label, extract, renderForm }: {
  kind: ConfigKind;
  items: ConfigItem<T>[];
  status: "loading" | "ok" | "error";
  error?: string;
  retry: () => void;
  empty: string;
  label: string;
  extract: (entry: T) => string;
  renderForm: (entry: ConfigItem<T> | null, onSave: (obj: T, creating: boolean) => Promise<void>, onCancel: () => void) => React.ReactNode;
}) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [heldEtag, setHeldEtag] = useState<string | null>(null);
  const [heldEntry, setHeldEntry] = useState<ConfigItem<T> | null>(null);

  const onSave = async (obj: T, isCreating: boolean) => {
    setSaveErr(null);
    try {
      const precondition = isCreating || !heldEtag ? { ifNoneMatch: true } : { ifMatch: heldEtag };
      const res = await saveConfigItem<T>(kind, obj.id, obj, precondition);
      setHeldEtag(res.etag);
      await qc.invalidateQueries({ queryKey: CONFIG_KEYS[kind] });
      setCreating(false);
      setEditing(null);
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 409) setSaveErr("Changed somewhere else. Reload to continue.");
        else if (e.status === 422) setSaveErr(e.detail || "Couldn't save that change.");
        else setSaveErr("Couldn't save.");
      } else {
        setSaveErr("Couldn't save.");
      }
    }
  };

  const openEdit = async (id: string) => {
    setSaveErr(null);
    try {
      const res = await fetchConfigItem<T>(kind, id);
      setEditing(id);
      setCreating(false);
      setHeldEtag(res.etag);
      setHeldEntry({ id, etag: res.etag, object: res.object });
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setSaveErr("That object is gone.");
      } else {
        setSaveErr("Couldn't load that object.");
      }
    }
  };

  const currentEntry = creating ? null : items.find((i) => i.id === editing) ?? heldEntry;

  if (status === "loading") return <p className="fd-sentence">Loading {label}s…</p>;
  if (status === "error") {
    return (
      <div className="fd-connect-status">
        <p className="fd-sentence">{error ?? "Couldn't load."}</p>
        <button type="button" className="fd-btn" onClick={retry}>Retry</button>
      </div>
    );
  }
  if (items.length === 0 && editing === null && !creating) {
    return (
      <div>
        <p className="fd-sentence">{empty}</p>
        <button type="button" className="fd-btn fd-btn--primary" onClick={() => { setCreating(true); setEditing(null); setSaveErr(null); }}>New</button>
      </div>
    );
  }

  return (
    <div className="fd-connect-list">
      {(editing !== null || creating) && currentEntry !== null && (
        <div>
          {saveErr && <p role="alert" className="fd-connect-err">{saveErr}</p>}
          {renderForm(
            currentEntry,
            async (obj, isCreating) => onSave(obj, isCreating),
            () => { setEditing(null); setCreating(false); setSaveErr(null); setHeldEntry(null); setHeldEtag(null); },
          )}
        </div>
      )}
      {editing === null && !creating && (
        <>
          <ul className="fd-bindings">
            {items.map((i) => (
              <li key={i.id} className="fd-binding">
                <button type="button" className="fd-binding-name fd-btn--link" onClick={() => openEdit(i.id)}>
                  {extract(i.object)}
                </button>
                <span className="fd-binding-access">{label}</span>
              </li>
            ))}
          </ul>
          <button type="button" className="fd-btn fd-btn--primary" onClick={() => { setCreating(true); setEditing(null); setSaveErr(null); setHeldEtag(null); setHeldEntry(null); }}>New</button>
        </>
      )}
    </div>
  );
}

/**
 * Advanced: honest diagnostics. Config kinds and counts, config errors from the API, and the one-line
 * note that Worlds stores a secret reference and never its value. No password field, no Replace control.
 */
function AdvancedPanel() {
  const data = useConnectData();
  const counts: { kind: string; count: number }[] = [
    { kind: "Providers", count: data.providers.items.length },
    { kind: "Requests", count: data.requests.items.length },
    { kind: "Cards", count: data.cards.items.length },
  ];
  return (
    <div className="fd-advanced">
      <h2 className="fd-settings-section-title">Config kinds</h2>
      <ul className="fd-bindings">
        {counts.map((c) => (
          <li key={c.kind} className="fd-binding">
            <span className="fd-binding-name">{c.kind}</span>
            <span className="fd-binding-access">{c.count} {c.count === 1 ? "object" : "objects"}</span>
          </li>
        ))}
      </ul>
      <h2 className="fd-settings-section-title">Config errors</h2>
      {data.allErrors.length === 0 ? (
        <p className="fd-sentence">None. Every config file loaded cleanly.</p>
      ) : (
        <ul className="fd-bindings">
          {data.allErrors.map((e, i) => (
            <li key={`${e.file}-${i}`} className="fd-binding">
              <span className="fd-binding-name">{e.file}</span>
              <span className="fd-binding-access">{e.reason}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="fd-sentence">
        Worlds stores a reference to a secret (env:NAME or vault:NAME) and never its value. There is no field on this screen that accepts a secret value.
      </p>
    </div>
  );
}

/** Connect: the six front-door tabs. Providers, Requests, Cards are wired to the real config API. */
export function Connect() {
  const data = useConnectData();

  const providersPanel = (
    <ListPanel<Provider>
      kind="provider"
      items={data.providers.items}
      status={data.providersStatus}
      error={data.providersError}
      retry={data.refetchProviders}
      empty="No providers yet. A provider is a service Worlds can read."
      label="provider"
      extract={(p) => p.name || p.id}
      renderForm={(entry, onSave, onCancel) => {
        const initial: Provider = entry?.object ?? {
          id: "", name: "", kind: "http", base_url: "", auth: { type: "none" }, tls_verify: true,
        };
        return (
          <ProviderForm
            initial={initial}
            creating={!entry}
            onSave={async (p) => onSave(p, !entry)}
            onCancel={onCancel}
          />
        );
      }}
    />
  );

  const requestsPanel = (
    <ListPanel<ConnRequest>
      kind="request"
      items={data.requests.items}
      status={data.requestsStatus}
      error={data.requestsError}
      retry={data.refetchRequests}
      empty="No saved requests yet. They will run here once Connect is wired up."
      label="request"
      extract={(r) => `${r.method} ${r.id}`}
      renderForm={(entry, onSave, onCancel) => {
        const initial: ConnRequest = entry?.object ?? {
          id: "", provider: "", method: "GET", path: "", effect: "auto",
        };
        return (
          <RequestForm
            initial={initial}
            providers={data.providers.items}
            creating={!entry}
            onSave={async (r) => onSave(r, !entry)}
            onCancel={onCancel}
          />
        );
      }}
    />
  );

  const cardsPanel = (
    <ListPanel<CardConfig>
      kind="card"
      items={data.cards.items}
      status={data.cardsStatus}
      error={data.cardsError}
      retry={data.refetchCards}
      empty="No cards yet. A card shapes a request into something you can read."
      label="card"
      extract={(c) => `${c.title || c.id} · ${c.group}`}
      renderForm={(entry, onSave, onCancel) => {
        const initial: CardConfig = entry?.object ?? {
          id: "", title: "", icon: "", group: "life", view: "stat", meaning: { short: "", full: "" },
        };
        return (
          <CardForm
            initial={initial}
            requests={data.requests.items}
            creating={!entry}
            onSave={async (c) => onSave(c, !entry)}
            onCancel={onCancel}
          />
        );
      }}
    />
  );

  const tabs: TabDef[] = [
    { id: "requests", label: "Requests", panel: requestsPanel },
    { id: "providers", label: "Providers", panel: providersPanel },
    { id: "cards", label: "Cards", panel: cardsPanel },
    { id: "recipes", label: "Recipes", panel: <p className="fd-sentence">No recipes installed yet. A recipe sets up one service in a single step.</p> },
    { id: "actions", label: "Actions", panel: <ActionsPanel /> },
    { id: "advanced", label: "Advanced", panel: <AdvancedPanel /> },
  ];

  return (
    <div className="fd-screen">
      <h1 className="fd-screen-title">Connect</h1>
      <Tabs label="Connect" tabs={tabs} />
    </div>
  );
}
