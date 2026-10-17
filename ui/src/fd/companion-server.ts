/**
 * A stand-in for the Worlds Companion proxy routes (/api/companion/*), for tests only. Everything here is invented:
 * no real address, persona text, thread content or names. It mirrors the proxy's contract: honest 502 "Companion isn't
 * answering" when told to fail, idempotent turns by client_msg_id, and grants that start pending.
 */
export type Mode = "ok" | "down" | "not_configured";
export interface Reply { status: number; body: unknown }

export function createCompanionServer() {
  let mode: Mode = "ok";
  const replies = new Map<string, string>();
  const grants = new Map<string, { state: string; expires_at: string | null }>();
  const calls: { method: string; path: string; body: unknown }[] = [];
  // Fake stored threads for the "Earlier conversations" feature
  const storedThreads = new Map<string, { ts: string; visibility_tier: "ordinary" | "stepped"; user_text: string; assistant_text: string; client_msg_id: string }[]>([
    ["t-old-1", [
      { ts: "2026-09-15T10:30:00Z", visibility_tier: "ordinary", user_text: "What's the weather?", assistant_text: "I don't have real-time data.", client_msg_id: "m1" },
      { ts: "2026-09-15T10:31:00Z", visibility_tier: "ordinary", user_text: "Thanks anyway", assistant_text: "You're welcome.", client_msg_id: "m2" },
    ]],
    ["t-old-2", [
      { ts: "2026-09-20T14:00:00Z", visibility_tier: "ordinary", user_text: "Help me plan", assistant_text: "Sure, what for?", client_msg_id: "m3" },
    ]],
  ]);

  const down = (): Reply => ({ status: 502, body: { state: "unknown", text: "Companion isn't answering.", reason: "unreachable" } });

  return {
    calls,
    setMode(m: Mode) { mode = m; },
    reset() { mode = "ok"; replies.clear(); grants.clear(); calls.length = 0; },
    handle(method: string, path: string, body: unknown): Reply {
      calls.push({ method, path, body });
      if (mode === "not_configured") return { status: 503, body: { state: "not_configured", text: "Companion isn't set up." } };
      if (mode === "down") return down();
      if (method === "GET" && path === "/api/companion/health") {
        return { status: 200, body: { status: "ok", commit: "abc1234", sources: { lore: "ok", ph: "unavailable", hw: "ok" }, models: { local: "healthy" } } };
      }
      if (method === "POST" && path === "/api/companion/turn") {
        const b = body as { message?: string; client_msg_id?: string; thread_id?: string };
        if (!b?.message || !b.client_msg_id) return { status: 400, body: { detail: "message is required" } };
        if (!replies.has(b.client_msg_id)) replies.set(b.client_msg_id, `Here is a short answer to: ${b.message.slice(0, 40)}`);
        return {
          status: 200,
          body: {
            thread_id: b.thread_id ?? "t-1", reply: replies.get(b.client_msg_id), connection: "local", tier_sent: "ordinary", sections: { reviewed: 2, live: 1 },
            unknown: ["recall: withheld (tier)"], grant: null, audit_id: "a-1",
            presentation: { v: "presentation/1", state: "engaged", tone: "warm", gesture: "nod", speaking: true },
          },
        };
      }
      if (method === "GET" && path === "/api/companion/context") {
        return {
          status: 200,
          body: {
            tier: "ordinary", budget_chars: 6000, used_chars: 240,
            reviewed: [{ text: "Prefers short answers.", source: "notes", when: "2026-09-30", cls: "reviewed", tier: "ordinary" }],
            working: [], recall: [],
            live: [{ text: "2 things need you.", source: "home", when: null, cls: "live", tier: "ordinary" }],
            unknown: ["recall: withheld (tier)"],
          },
        };
      }
      if (method === "POST" && path === "/api/companion/grants") {
        grants.set("g-1", { state: "pending", expires_at: null });
        return { status: 200, body: { grant_id: "g-1", state: "pending", expires_at: null, approval_id: "ap-1", link: "/approvals/ap-1" } };
      }
      const g = path.match(/^\/api\/companion\/grants\/([A-Za-z0-9_-]+)$/);
      if (g && method === "GET") return { status: 200, body: { grant_id: g[1], ...(grants.get(g[1]) ?? { state: "unknown", expires_at: null }) } };
      if (g && method === "DELETE") { grants.set(g[1], { state: "revoked", expires_at: null }); return { status: 200, body: { grant_id: g[1], state: "revoked", expires_at: null } }; }
      if (method === "GET" && path === "/api/companion/threads") return { status: 200, body: { threads: ["t-old-1", "t-old-2", "t-1"] } };
      // Individual thread: /api/companion/threads/{id}?after=n
      const threadMatch = path.match(/^\/api\/companion\/threads\/([A-Za-z0-9_-]+)$/);
      if (threadMatch && method === "GET") {
        const id = threadMatch[1];
        const url = new URL(`http://x${path.includes("?") ? path.slice(path.indexOf("?")) : ""}`);
        const after = Number(url.searchParams.get("after") ?? "0");
        const turns = storedThreads.get(id) ?? [];
        const filtered = turns.slice(after);
        return { status: 200, body: { thread_id: id, turns: filtered } };
      }
      return { status: 404, body: { detail: "not found" } };
    },
  };
}
export type CompanionServer = ReturnType<typeof createCompanionServer>;
