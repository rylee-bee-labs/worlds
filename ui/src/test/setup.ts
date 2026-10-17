import "@testing-library/jest-dom/vitest";

// jsdom provides localStorage; ensure window.location is writable for
// api.ts. Give it a real origin: openapi-fetch builds Request("/api/…")
// relative to location, and an empty href would throw "Failed to parse
// URL" in every fetch-level test. The 401-redirect tests assert on href.
if (typeof window !== "undefined") {
  Object.defineProperty(window, "location", {
    value: { href: "http://station.test/" },
    writable: true,
  });
}

// jsdom implements no matchMedia. Tests that exercise the applied-prefs
// path need a deterministic, environment-independent floor answer:
// "no OS reduced-motion preference" (firewall behaviour itself is
// covered by explicit ApplyPrefsOptions in prefs-dom.test.ts and by
// the Playwright reduced-motion spec, where a real browser emulates
// the media query).
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string): MediaQueryList => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  });
}

// jsdom has no modal <dialog>. A small stand-in: showModal opens it, focuses its autofocus control (as a browser
// would), and close() hands focus back to whatever had it, like the real element.
if (typeof HTMLDialogElement !== "undefined" && typeof HTMLDialogElement.prototype.showModal !== "function") {
  const opener = new WeakMap<HTMLDialogElement, Element | null>();
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    opener.set(this, document.activeElement);
    this.setAttribute("open", "");
    (this.querySelector<HTMLElement>("[autofocus]") ?? this.querySelector<HTMLElement>("button, [href], input"))?.focus();
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute("open");
    (opener.get(this) as HTMLElement | null)?.focus?.();
  };
}
