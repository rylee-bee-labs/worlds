/** What the Worlds proxy returns (already whitelisted server side). Nothing here names a real address or persona. */
export type Tier = "ordinary" | "stepped";

export interface PresentationJson {
  v?: string;
  state?: string;
  tone?: string;
  gesture?: string;
  speaking?: boolean;
}

export type GrantState = "pending" | "active" | "denied" | "expired" | "revoked" | "unknown";
export interface GrantView {
  grant_id?: string | null;
  state: GrantState;
  expires_at?: string | null;
  approval_id?: string | null;
  link?: string | null;
}

export interface TurnResponse {
  thread_id: string | null;
  reply: string;
  connection: string;
  tier_sent: Tier;
  sections: Record<string, number>;
  unknown: string[];
  grant: { state: GrantState; expires_at: string | null } | null;
  audit_id: string;
  presentation: PresentationJson | null;
}

export interface StoredTurn {
  ts: string | null;
  visibility_tier: Tier;
  user_text: string;
  assistant_text: string;
  client_msg_id: string | null;
}

export interface ContextItem { text: string; source: string; when: string | null; cls: string; tier: Tier }
export interface ContextView {
  tier: Tier;
  budget_chars: number | null;
  used_chars: number | null;
  reviewed: ContextItem[];
  working: ContextItem[];
  recall: ContextItem[];
  live: ContextItem[];
  unknown: string[];
}

export interface HealthView {
  status: "ok" | "unknown";
  commit: string;
  sources: Record<string, "ok" | "unavailable">;
  models: Record<string, "healthy" | "unavailable">;
}

/** A call that did not produce data. `unknown` is the honest "Companion isn't answering". */
export type CompanionFailure =
  | { kind: "unknown"; text: string; reason: string }
  | { kind: "not_configured"; text: string }
  | { kind: "invalid"; text: string };
export type Result<T> = { ok: true; data: T } | { ok: false; failure: CompanionFailure };
