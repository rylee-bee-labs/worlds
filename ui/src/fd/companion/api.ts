import type { CompanionFailure, ContextView, GrantView, HealthView, Result, StoredTurn, TurnResponse } from "./types";

/** The CSRF token for cookie-authenticated writes (the pw_csrf cookie; empty when there is none). */
function csrf(): Record<string, string> {
  const m = typeof document !== "undefined" ? document.cookie.match(/(?:^|;\s*)pw_csrf=([^;]+)/) : null;
  return m ? { "X-CSRF-Token": decodeURIComponent(m[1]) } : {};
}

const NOT_ANSWERING = "Companion isn't answering.";

async function call<T>(path: string, init: RequestInit & { json?: unknown } = {}, timeoutMs = 60_000): Promise<Result<T>> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  const method = init.method ?? "GET";
  try {
    let res: Response;
    try {
      res = await fetch(path, {
        method,
        credentials: "same-origin",
        signal: ctl.signal,
        headers: { accept: "application/json", ...(init.json !== undefined ? { "content-type": "application/json" } : {}), ...(method === "GET" ? {} : csrf()) },
        body: init.json !== undefined ? JSON.stringify(init.json) : undefined,
      });
    } catch {
      return { ok: false, failure: { kind: "unknown", text: NOT_ANSWERING, reason: ctl.signal.aborted ? "timeout" : "unreachable" } };
    }
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      /* no body */
    }
    if (res.ok) return { ok: true, data: body as T };
    const b = (body ?? {}) as { state?: string; text?: string; reason?: string; detail?: string };
    let failure: CompanionFailure;
    if (res.status === 503 && b.state === "not_configured") failure = { kind: "not_configured", text: "Companion isn't set up." };
    // A refused session is its own reason, so nothing downstream has to guess that "unreachable" meant "not you".
    else if (res.status === 401 || res.status === 403) failure = { kind: "unknown", text: NOT_ANSWERING, reason: "unauthorized" };
    else if (res.status === 400) failure = { kind: "invalid", text: typeof b.detail === "string" ? b.detail : "That wasn't something Companion could take." };
    else failure = { kind: "unknown", text: NOT_ANSWERING, reason: typeof b.reason === "string" ? b.reason : "unreachable" };
    return { ok: false, failure };
  } finally {
    clearTimeout(timer);
  }
}

export const companionApi = {
  turn: (message: string, clientMsgId: string, threadId: string | null, quiet = false) =>
    call<TurnResponse>("/api/companion/turn", { method: "POST", json: { message, client_msg_id: clientMsgId, ...(threadId ? { thread_id: threadId } : {}), ...(quiet ? { ui_context: { quiet: true } } : {}) } }),
  threads: () => call<{ threads: string[] }>("/api/companion/threads"),
  thread: (id: string, after = 0) => call<{ thread_id: string | null; turns: StoredTurn[] }>(`/api/companion/threads/${encodeURIComponent(id)}?after=${after}`),
  context: (q = "") => call<ContextView>(`/api/companion/context?q=${encodeURIComponent(q)}`),
  health: () => call<HealthView>("/api/companion/health"),
  requestGrant: (reason: string, ttlS = 900) => call<GrantView>("/api/companion/grants", { method: "POST", json: { ttl_s: ttlS, reason } }),
  grant: (id: string) => call<GrantView>(`/api/companion/grants/${encodeURIComponent(id)}`),
  revokeGrant: (id: string) => call<GrantView>(`/api/companion/grants/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

/** A fresh idempotency key for one send. A retry of the SAME message must reuse it. */
export function newClientMsgId(): string {
  const rnd = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `w-${rnd.replace(/[^A-Za-z0-9_-]/g, "")}`.slice(0, 100);
}
