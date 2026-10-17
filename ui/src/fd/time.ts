/** "HH:MM" (24h) for an ISO time in the given zone (default: the host's), or null when it can't be read. */
export function formatClock(iso: string, timeZone?: string): string | null {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone }).format(date);
}

/**
 * A readable date for a Memory epoch-seconds timestamp: "2 Oct", "14 Sep". Short because Memory
 * rows crowd the page. Returns null only when the number is not a valid time.
 */
export function formatMemoryStamp(epochSeconds: number | null | undefined): string | null {
  if (epochSeconds == null) return null;
  const d = new Date(epochSeconds * 1000);
  if (Number.isNaN(d.getTime())) return null;
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" }).format(d);
}

/** Same as above but for History's `at`, with the clock too. */
export function formatHistoryStamp(epochSeconds: number | null | undefined): string | null {
  if (epochSeconds == null) return null;
  const d = new Date(epochSeconds * 1000);
  if (Number.isNaN(d.getTime())) return null;
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(d);
}
