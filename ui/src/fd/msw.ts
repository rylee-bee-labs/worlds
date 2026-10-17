import { http, HttpResponse } from "msw";
import { createBoardServer } from "./board-server";
import { createCompanionServer } from "./companion-server";
import { cards, memoryKeptRows, memoryLaterRows, memoryRecordsRows, memoryHistoryRows, memoryFindRows, needsYou } from "./fixtures";
import type {
  ActionSummary,
  CardConfig,
  MemoryHistoryRow,
  MemoryKeptRow,
  MemoryLaterRow,
  MemoryLockedRow,
  MemoryRecordsRow,
  Provider,
  Receipt,
  Request as ConnRequest,
  TryResult,
  PreviewResult,
} from "./types";

/** The test board server: call boardServer.reset() between tests. */
export const boardServer = createBoardServer();
export const companionServer = createCompanionServer();

/** In-memory Connect config store for tests. Each entry carries its own etag. */
type AnyConfig = Provider | ConnRequest | CardConfig;
interface StoreEntry { object: AnyConfig; etag: string }
type Kind = "provider" | "request" | "card";

class ConnectStore {
  providers = new Map<string, StoreEntry>();
  requests = new Map<string, StoreEntry>();
  cardConfigs = new Map<string, StoreEntry>();
  actions: ActionSummary[] = [];
  receipts: Receipt[] = [];
  configErrors: { kind: Kind; file: string; reason: string }[] = [];
  /** Counter so the next PUT etag is always fresh. */
  private v = 0;

  reset() {
    this.providers.clear();
    this.requests.clear();
    this.cardConfigs.clear();
    this.actions = [];
    this.receipts = [];
    this.configErrors = [];
    this.v = 0;
  }

  private bump(): string {
    this.v += 1;
    return `"v${this.v}"`;
  }

  private mapFor(kind: Kind): Map<string, StoreEntry> {
    return kind === "provider" ? this.providers : kind === "request" ? this.requests : this.cardConfigs;
  }

  list(kind: Kind) {
    const map = this.mapFor(kind);
    const items = [...map.entries()].map(([id, e]) => ({ id, etag: e.etag, object: e.object }));
    const errors = this.configErrors.filter((e) => e.kind === kind).map((e) => ({ file: e.file, reason: e.reason }));
    return { items, errors };
  }

  get(kind: Kind, id: string): StoreEntry | undefined {
    return this.mapFor(kind).get(id);
  }

  put(kind: Kind, id: string, ifMatch: string | null, ifNoneMatch: string | null, object: AnyConfig) {
    const map = this.mapFor(kind);
    const existing = map.get(id);
    if (ifNoneMatch === "*" && existing) {
      return { status: 409, etag: existing.etag, body: { detail: "already exists" } };
    }
    if (ifMatch && existing && existing.etag !== ifMatch) {
      return { status: 409, etag: existing.etag, body: { detail: "changed somewhere else" } };
    }
    if (!existing && !ifNoneMatch) {
      return { status: 428, etag: "", body: { detail: "precondition required" } };
    }
    const etag = this.bump();
    map.set(id, { object, etag });
    return { status: 200, etag, body: object };
  }
}

export const connectStore = new ConnectStore();

/** Handlers for the Home read API and the board write API. Kept for tests once the real API is the default. */
const companion = async ({ request }: { request: Request }) => {
  const url = new URL(request.url);
  const body = request.method === "GET" || request.method === "DELETE" ? null : await request.json().catch(() => null);
  const r = companionServer.handle(request.method, url.pathname, body);
  return HttpResponse.json(r.body as Record<string, unknown>, { status: r.status });
};

export const handlers = [
  http.all("/api/companion/*", companion),
  http.get("/api/boards/home", () => HttpResponse.json(boardServer.display())),
  http.get("/api/needs-you", () => HttpResponse.json(needsYou)),
  http.get("/api/cards/:id", ({ params }) => {
    const card = cards[String(params.id)];
    return card ? HttpResponse.json(card) : HttpResponse.json({ detail: "not found" }, { status: 404 });
  }),
  http.get("/api/config/board/home", () => {
    const { body, etag } = boardServer.getConfig();
    return HttpResponse.json(body, { headers: { etag } });
  }),
  http.put("/api/config/board/home", async ({ request }) => {
    const r = boardServer.put(request.headers.get("if-match"), request.headers.get("x-csrf-token"), (await request.json()) as never);
    return HttpResponse.json(r.body as Record<string, unknown>, { status: r.status, headers: { etag: r.etag } });
  }),
  /** Connect: list each config kind. */
  http.get("/api/config/:kind", ({ params }) => {
    const kind = String(params.kind) as Kind;
    if (!["provider", "request", "card"].includes(kind)) {
      return HttpResponse.json({ detail: "unknown kind" }, { status: 404 });
    }
    return HttpResponse.json(connectStore.list(kind));
  }),
  /** Connect: get a single config object with its etag header. */
  http.get("/api/config/:kind/:id", ({ params }) => {
    const kind = String(params.kind) as Kind;
    const id = String(params.id);
    const entry = connectStore.get(kind, id);
    if (!entry) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    return HttpResponse.json(entry.object, { headers: { etag: entry.etag } });
  }),
  /** Connect: save a config object. Enforces preconditions and CSRF for writes. */
  http.put("/api/config/:kind/:id", async ({ request, params }) => {
    const kind = String(params.kind) as Kind;
    const id = String(params.id);
    const ifMatch = request.headers.get("if-match");
    const ifNoneMatch = request.headers.get("if-none-match");
    const body = (await request.json()) as Provider | ConnRequest | CardConfig;
    if ((body as { id?: string }).id !== id) {
      return HttpResponse.json({ detail: "id in body does not match URL" }, { status: 422 });
    }
    const r = connectStore.put(kind, id, ifMatch, ifNoneMatch, body);
    return HttpResponse.json(r.body as Record<string, unknown>, { status: r.status, headers: { etag: r.etag } });
  }),
  /** Connect: try a request against a provider. Never dispatches a write. */
  http.post("/api/connect/try", async ({ request }) => {
    const body = (await request.json()) as { provider: unknown; request: ConnRequest };
    const req = body.request;
    const method = req?.method ?? "GET";
    const effect = req?.effect;
    const knownSafe = req?.known_safe;
    // Write-like requests are refused by the server with 422.
    const isWrite =
      !(method === "GET" || method === "HEAD") && !(effect === "read" && knownSafe);
    if (isWrite) {
      return HttpResponse.json({ detail: "test write actions through an approved action" }, { status: 422 });
    }
    // A secret_ref that names a Worlds-owned secret is refused.
    const prov = body.provider as Provider | undefined;
    const ref = prov?.auth?.secret_ref;
    if (ref && (ref.startsWith("PW_") || ref.startsWith("OIDC_") || ref.includes("BOOTSTRAP"))) {
      return HttpResponse.json({ detail: "World-owned secrets cannot be used on the try endpoint" }, { status: 422 });
    }
    const result: TryResult = {
      ok: true,
      status_code: 200,
      duration_ms: 42,
      content_type: "application/json",
      sample: JSON.stringify({ hello: "example" }),
      truncated: false,
      suggested_fields: [{ label: "Hello", path: "$.hello", format: "text", sample: "example" }],
    };
    return HttpResponse.json(result);
  }),
  /** Connect: preview a card against a sample or saved read request. */
  http.post("/api/connect/preview", async ({ request }) => {
    const body = (await request.json()) as {
      card: CardConfig;
      sample?: string;
      request?: string;
    };
    // A saved write request is refused.
    if (body.request) {
      const entry = connectStore.requests.get(body.request);
      if (!entry) return HttpResponse.json({ detail: "request not found" }, { status: 404 });
      const r = entry.object as ConnRequest;
      const isWrite = !(r.method === "GET" || r.method === "HEAD") && !(r.effect === "read" && r.known_safe);
      if (isWrite) return HttpResponse.json({ detail: "test write actions through an approved action" }, { status: 422 });
    }
    const result: PreviewResult = {
      card_id: body.card.id,
      source_state: "healthy",
      freshness: "current",
      observed_at: "2026-10-01T09:30:00Z",
      fetched_at: "2026-10-01T09:30:00Z",
      last_good_at: "2026-10-01T09:30:00Z",
      values: { hello: { text: "example", raw: "example" } },
      meter: { type: "progress", text_equivalent: "100 percent", value: 1, max: 1 },
      meaning: { short: body.card.meaning.short, full: body.card.meaning.full },
      evidence: {
        request_id: body.card.request ?? body.request ?? "preview",
        method: "GET",
        path: "/v1/example",
        status_code: 200,
        duration_ms: 42,
      },
    };
    return HttpResponse.json(result);
  }),
  /** Actions list. */
  http.get("/api/actions", () => HttpResponse.json(connectStore.actions)),
  /** Receipts list. */
  http.get("/api/receipts", () => HttpResponse.json(connectStore.receipts)),
  /** Memory: list rows in a table, preserving server order and masked locked rows as-is. */
  http.get("/api/memory/find", ({ request }) => {
    const q = new URL(request.url).searchParams.get("q") ?? "";
    if (!q) return HttpResponse.json([]);
    return HttpResponse.json(memoryFindRows);
  }),
  http.get("/api/memory/history", () => HttpResponse.json(memoryHistoryRows as MemoryHistoryRow[])),
  http.get("/api/memory/export/:table", ({ params }) => {
    const table = String(params.table);
    const rows = table === "kept" ? memoryKeptRows : table === "later" ? memoryLaterRows : table === "records" ? memoryRecordsRows : [];
    const body = rows.map((r) => JSON.stringify(r)).join("\n") + "\n";
    return new HttpResponse(body, { status: 200, headers: { "content-type": "application/x-ndjson", "content-disposition": `attachment; filename="worlds-${table}.ndjson"` } });
  }),
  http.post("/api/memory/backup", () => HttpResponse.json({ file: "worlds-20261002-070000.db" })),
  http.get("/api/memory/:table", ({ params }) => {
    const table = String(params.table);
    if (table === "kept") return HttpResponse.json(memoryKeptRows);
    if (table === "later") return HttpResponse.json(memoryLaterRows);
    if (table === "records") return HttpResponse.json(memoryRecordsRows);
    return HttpResponse.json({ detail: "unknown table" }, { status: 404 });
  }),
  http.post("/api/memory/:table", async ({ params, request }) => {
    const table = String(params.table);
    const body = (await request.json()) as Record<string, unknown>;
    if (!body.title || typeof body.title !== "string") {
      return HttpResponse.json({ detail: "title is required" }, { status: 400 });
    }
    const allowed = new Set(["title", "body", "tags", "due_at", "kind", "sensitivity", "provenance", "source_ref"]);
    const extra = Object.keys(body).filter((k) => !allowed.has(k));
    if (extra.length) return HttpResponse.json({ detail: `unknown fields: ${extra.sort()}` }, { status: 400 });
    // a new later row is always open: the server rejects status on create
    if ("status" in body) return HttpResponse.json({ detail: "unknown fields: [status]" }, { status: 400 });
    const id = `new-${table}-1`;
    const row = { id, table, ...body, provenance: body.provenance ?? "owner", source_ref: body.source_ref ?? null, created_at: 1727800000, updated_at: 1727800000 };
    if (table === "kept") memoryKeptRows.push(row as MemoryKeptRow);
    else if (table === "later") memoryLaterRows.push({ ...(row as object), status: "open" } as MemoryLaterRow);
    else if (table === "records") memoryRecordsRows.push(row as MemoryRecordsRow);
    return HttpResponse.json(row, { status: 200 });
  }),
  http.patch("/api/memory/:table/:id", async ({ params, request }) => {
    const table = String(params.table);
    const id = String(params.id);
    const body = (await request.json()) as Record<string, unknown>;
    if (!Object.keys(body).length) return HttpResponse.json({ detail: "an update needs at least one field" }, { status: 400 });
    const list: (MemoryKeptRow | MemoryLaterRow | MemoryRecordsRow)[] = table === "kept" ? memoryKeptRows : table === "later" ? memoryLaterRows : table === "records" ? (memoryRecordsRows as (MemoryRecordsRow | MemoryLockedRow)[]).filter((r): r is MemoryRecordsRow => !("locked" in r)) : [];
    const existing = list.find((r) => r.id === id);
    if (!existing) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const merged = { ...existing, ...body, table, updated_at: 1727850000 };
    Object.assign(existing, merged);
    return HttpResponse.json(merged);
  }),
  http.delete("/api/memory/:table/:id", ({ params }) => {
    const table = String(params.table);
    const id = String(params.id);
    const list: (MemoryKeptRow | MemoryLaterRow | MemoryRecordsRow | MemoryLockedRow)[] = table === "kept" ? memoryKeptRows : table === "later" ? memoryLaterRows : table === "records" ? memoryRecordsRows : [];
    const idx = list.findIndex((r) => r.id === id);
    if (idx === -1) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    list.splice(idx, 1);
    return HttpResponse.json({ ok: true });
  }),
];
