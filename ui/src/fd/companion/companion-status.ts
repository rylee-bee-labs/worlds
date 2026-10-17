import type { HealthView, Result } from "./types";

/** One honest answer to "is Companion working?", shared by the panel and by Settings. Every word comes from the
 * health call's own result; nothing here names a provider, an address or a person, and nothing is invented. */
export interface CompanionStatus {
  /** A fixed state word for a summary line: Checking, Up, Up (partly), Not set up, Unknown. */
  word: string;
  /** The sentence to show, worded exactly as the panel words it. */
  line: string;
  /** What to do next, or "" when there is nothing to do. */
  next: string;
}

/** The names a health body says are not answering. A body that is not the expected shape answers with nothing. */
function unavailable(v: unknown): string[] {
  if (!v || typeof v !== "object" || Array.isArray(v)) return [];
  return Object.entries(v as Record<string, unknown>).filter(([, s]) => s === "unavailable").map(([k]) => k);
}

/** The health sentence: up, or up with the parts that are not answering named. */
export function healthLine(data: Partial<HealthView> | undefined): string {
  const down = [...unavailable(data?.sources), ...unavailable(data?.models)];
  return down.length === 0 ? "Companion is up." : `Companion is up. Not answering: ${down.join(", ")}.`;
}

/** The same status, whatever a caller is showing it in. */
export function companionStatus(result: Result<HealthView> | null, loading = false): CompanionStatus {
  if (!result || loading) return { word: "Checking", line: "Checking Companion…", next: "" };
  if (!result.ok) {
    const f = result.failure;
    if (f.kind === "not_configured") return { word: "Not set up", line: f.text, next: "Set the Companion provider up in Connect, then check again." };
    if (f.kind === "unknown" && f.reason === "unauthorized") return { word: "Unknown", line: f.text, next: "Sign in as the owner, then check again." };
    return { word: "Unknown", line: f.text, next: "Open the Companion panel to try again." };
  }
  const data: Partial<HealthView> | undefined = result.data;
  const down = [...unavailable(data?.sources), ...unavailable(data?.models)];
  return down.length === 0
    ? { word: "Up", line: healthLine(data), next: "" }
    : { word: "Up, partly", line: healthLine(data), next: "Some parts aren't answering. Try again later." };
}