import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { Settings } from "../fd/Settings";
import { companionApi } from "../fd/companion/api";
import { CompanionButton } from "../fd/companion/CompanionButton";
import { CompanionPanel } from "../fd/companion/CompanionPanel";
import { CompanionProvider } from "../fd/companion/CompanionProvider";
import { companionServer, handlers as fdHandlers } from "../fd/msw";
import { PrefsProvider } from "../fd/prefs";
import { usePrefs } from "../fd/prefs-core";

const server = setupServer(
  ...fdHandlers,
  http.get("/api/auth/session", () => HttpResponse.json({ authenticated: true, bootstrap_available: false, oidc_available: false })),
  http.get("/api/push/public-key", () => HttpResponse.json({ detail: "not configured" }, { status: 409 })),
  http.get("/api/push/subscriptions", () => HttpResponse.json({ ok: true, data: [] })),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  companionServer.reset();
  window.localStorage.clear();
});
afterAll(() => server.close());

function Probe() {
  const { prefs } = usePrefs();
  return <output aria-label="prefs">{`${prefs.pack}|${prefs.theme}|${prefs.density}|${prefs.words}|${prefs.text}`}</output>;
}
const renderSettings = () => render(<PrefsProvider><Settings /><Probe /></PrefsProvider>);

/** The Companion section, found by its own heading and never the panel's: both are titled "Companion". */
const companionSection = (c: HTMLElement) => {
  const heading = Array.from(c.querySelectorAll("h2")).find((h) => h.textContent === "Companion" && !h.closest("dialog"));
  if (!heading) throw new Error("no Companion section in this render");
  return heading.closest("section") as HTMLElement;
};
const healthOk = (sources: Record<string, string> = { lore: "ok" }, models: Record<string, string> = { local: "healthy" }) =>
  server.use(http.get("/api/companion/health", () => HttpResponse.json({ status: "ok", commit: "abc1234", sources, models })));

describe("Settings", () => {
  it("puts Comfort first, then Look, Experience, Companion and Notifications", () => {
    renderSettings();
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual(["Comfort", "Look", "Experience", "Companion", "Notifications"]);
  });
  it("offers each choice once, as a group named once, with no Plain theme", () => {
    renderSettings();
    const opts = (name: string) => within(screen.getByRole("group", { name })).getAllByRole("radio").map((r) => (r as HTMLInputElement).labels?.[0]?.textContent);
    expect(opts("Density")).toEqual(["Calm", "Standard", "Detailed"]);
    expect(opts("Words")).toEqual(["Minimal", "Short", "Full"]);
    expect(opts("Text size")).toEqual(["Standard", "Large", "Larger"]);
    expect(opts("Theme")).toEqual(["Mulberry & Mint", "Starfield", "Daylight"]);
    expect(opts("Experience pack")).toEqual(["None", "Station"]);
    expect(screen.queryAllByRole("radiogroup")).toHaveLength(0);          // the legend is announced once
    expect(screen.queryByRole("radio", { name: "Plain" })).not.toBeInTheDocument();
  });
  it("describes each option in one line", () => {
    renderSettings();
    expect(screen.getByRole("radio", { name: "Calm" })).toHaveAccessibleDescription("What needs you first, quiet things folded away.");
    expect(screen.getByRole("radio", { name: "Station" })).toHaveAccessibleDescription(/never changes what Worlds says or does/);
  });
  it("defaults to None, Mulberry & Mint, Standard, Short and changes preferences", async () => {
    renderSettings();
    expect(screen.getByLabelText("prefs")).toHaveTextContent("none|mulberry|standard|short|standard");
    await userEvent.click(screen.getByRole("radio", { name: "Station" }));
    await userEvent.click(screen.getByRole("radio", { name: "Full" }));
    await userEvent.click(screen.getByRole("radio", { name: "Detailed" }));
    await userEvent.click(screen.getByRole("radio", { name: "Daylight" }));
    await userEvent.click(screen.getByRole("radio", { name: "Larger" }));
    expect(screen.getByLabelText("prefs")).toHaveTextContent("station|daylight|detailed|full|larger");
  });
  it("a stored Plain theme falls back to Mulberry & Mint", () => {
    window.localStorage.setItem("worlds.prefs.v2", JSON.stringify({ theme: "plain" }));
    renderSettings();
    expect(screen.getByLabelText("prefs")).toHaveTextContent(/\|mulberry\|/);
  });
  it("an old save's Starfield was only the default, so it opens in Mulberry & Mint", () => {
    window.localStorage.setItem("worlds.prefs.v2", JSON.stringify({ theme: "starfield" }));
    renderSettings();
    expect(screen.getByLabelText("prefs")).toHaveTextContent(/\|mulberry\|/);
  });
  it("Starfield chosen after the switch is kept", () => {
    window.localStorage.setItem("worlds.prefs.v2", JSON.stringify({ theme: "starfield", themeV: 2 }));
    renderSettings();
    expect(screen.getByLabelText("prefs")).toHaveTextContent(/\|starfield\|/);
  });
  it("says motion follows the device", () => {
    renderSettings();
    expect(screen.getByText(/Motion follows your device setting/)).toBeInTheDocument();
  });
});

describe("Settings · the Companion section", () => {
  it("names one Companion, and never a missing Assistant", async () => {
    healthOk();
    const { container } = renderSettings();
    const section = companionSection(container);
    expect(within(section).getByText(/One Companion: the presence in the header\./)).toBeInTheDocument();
    expect(await within(section).findByText("Companion is up.")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Not installed/);
    expect(within(section).queryByText("Assistant")).not.toBeInTheDocument();
    expect(within(section).queryByRole("heading", { name: "Assistant" })).not.toBeInTheDocument();
  });

  it("says up while it is still checking, so nothing is claimed before it is measured", () => {
    const { container } = renderSettings();
    expect(within(companionSection(container)).getByRole("status")).toHaveTextContent("Checking Companion…");
  });

  it("names the parts that are not answering, and says to try again later", async () => {
    healthOk({ lore: "ok", ph: "unavailable" }, { local: "healthy" });
    const { container } = renderSettings();
    const section = companionSection(container);
    expect(await within(section).findByText("Companion is up. Not answering: ph.")).toBeInTheDocument();
    expect(within(section).getByText("Some parts aren't answering. Try again later.")).toBeInTheDocument();
  });

  it("not configured says it plainly and points at Connect", async () => {
    companionServer.setMode("not_configured");
    const { container } = renderSettings();
    const section = companionSection(container);
    expect(await within(section).findByText("Companion isn't set up.")).toBeInTheDocument();
    expect(within(section).getByText("Set the Companion provider up in Connect, then check again.")).toBeInTheDocument();
    expect(section.textContent).not.toMatch(/Not installed/);
  });

  it("an unreachable Companion is Unknown with a way to try again, not a claim that it is absent", async () => {
    companionServer.setMode("down");
    const { container } = renderSettings();
    const section = companionSection(container);
    expect(await within(section).findByText("Companion isn't answering.")).toBeInTheDocument();
    expect(within(section).getByText("Open the Companion panel to try again.")).toBeInTheDocument();
    expect(section.textContent).not.toMatch(/Not installed/);
  });

  it("a refused session says so instead of blaming the Companion", async () => {
    server.use(http.get("/api/companion/health", () => HttpResponse.json({ detail: "owner only" }, { status: 403 })));
    const { container } = renderSettings();
    const section = companionSection(container);
    expect(await within(section).findByText("Companion isn't answering.")).toBeInTheDocument();
    expect(within(section).getByText("Sign in as the owner, then check again.")).toBeInTheDocument();
  });

  it("reads health and nothing else: no thread, no context, no grant, no receipt", async () => {
    companionServer.setMode("ok");
    const { container } = renderSettings();
    await within(companionSection(container)).findByText(/Companion is up\./);
    await waitFor(() => expect(companionServer.calls.length).toBeGreaterThan(0));
    expect(companionServer.calls.map((c) => `${c.method} ${c.path}`)).toEqual(["GET /api/companion/health"]);
    // Nothing from another owner's context or a past conversation can appear here, because nothing asked for it.
    expect(container.textContent).not.toMatch(/Prefers short answers|What's the weather|Not active|audit/);
  });

  it("opens the same governed panel by keyboard, never a second Companion", async () => {
    const { container } = render(
      <PrefsProvider>
        <CompanionProvider>
          <Settings />
          <CompanionButton />
          <CompanionPanel />
        </CompanionProvider>
      </PrefsProvider>,
    );
    const section = companionSection(container);
    await within(section).findByText("Companion is up. Not answering: ph.");
    const open = within(section).getByRole("button", { name: "Open the Companion panel" });
    open.focus();
    expect(open).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    const dlg = await screen.findByRole("dialog", { name: "Companion" });
    expect(dlg).toHaveAttribute("open");
    expect(within(dlg).getByRole("heading", { name: "Companion" })).toBeInTheDocument();
    // The status Settings showed and the one the panel shows are the same sentence, from the same call.
    expect(await within(dlg).findByText("Companion is up. Not answering: ph.")).toBeInTheDocument();
  });

  it("a refusal is measured as unauthorized, so nothing downstream guesses why", async () => {
    for (const status of [401, 403]) {
      server.use(http.get("/api/companion/health", () => HttpResponse.json({ detail: "owner only" }, { status })));
      expect(await companionApi.health()).toEqual({ ok: false, failure: { kind: "unknown", text: "Companion isn't answering.", reason: "unauthorized" } });
    }
  });

  it("with no panel mounted there is still one status and no dead button", async () => {
    healthOk();
    const { container } = renderSettings();
    await within(companionSection(container)).findByText("Companion is up.");
    expect(within(companionSection(container)).queryByRole("button")).not.toBeInTheDocument();
  });
});