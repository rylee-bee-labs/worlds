/** Only relative, http or https links from the API become links. javascript:, data: and the like are dropped. */
export function safeHref(href: string | undefined | null): string | null {
  if (!href) return null;
  const h = href.trim();
  if (h.startsWith("#") || (h.startsWith("/") && !h.startsWith("//"))) return h;
  try {
    const u = new URL(h);
    return u.protocol === "https:" || u.protocol === "http:" ? h : null;
  } catch {
    return null;
  }
}
