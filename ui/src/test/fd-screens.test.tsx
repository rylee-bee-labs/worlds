import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { Connect } from "../fd/Connect";
import { handlers as fdHandlers } from "../fd/msw";
import { Memory } from "../fd/Memory";

const server = setupServer(
  ...fdHandlers,
  http.get("/api/auth/session", () => HttpResponse.json({ authenticated: true, bootstrap_available: false, oidc_available: false })),
  http.get("/api/push/public-key", () => HttpResponse.json({ detail: "not configured" }, { status: 409 })),
  http.get("/api/push/subscriptions", () => HttpResponse.json({ ok: true, data: [] })),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => { cleanup(); server.resetHandlers(); });
afterAll(() => server.close());

afterEach(cleanup);

const tabNames = () => screen.getAllByRole("tab").map((t) => t.textContent);

const renderConnect = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><Connect /></QueryClientProvider>);
};

describe("Connect", () => {
  it("has the six tabs and one panel", async () => {
    renderConnect();
    expect(tabNames()).toEqual(["Requests", "Providers", "Cards", "Recipes", "Actions", "Advanced"]);
    expect(screen.getAllByRole("tabpanel")).toHaveLength(1);
    await userEvent.click(screen.getByRole("tab", { name: "Actions" }));
    expect(screen.getByRole("tab", { name: "Actions" })).toHaveAttribute("aria-selected", "true");
  });
  it("each empty tab has its own sentence", async () => {
    renderConnect();
    const texts = new Set<string>();
    for (const name of ["Requests", "Providers", "Recipes"]) {
      await userEvent.click(screen.getByRole("tab", { name }));
      texts.add(screen.getByRole("tabpanel").textContent ?? "");
    }
    expect(texts.size).toBe(3);
  });
  it("Actions: lists the real API actions, read and write as words, and holds no Run control", async () => {
    server.use(
      http.get("/api/actions", () => HttpResponse.json([
        { id: "example.read", name: "Read the example queue", access: "read", scope: "example", exposed: false },
        { id: "example.restart", name: "Restart the example service", access: "write", scope: "example", exposed: true },
      ])),
      http.get("/api/receipts", () => HttpResponse.json([])),
    );
    renderConnect();
    await userEvent.click(screen.getByRole("tab", { name: "Actions" }));
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("Read the example queue")).toBeInTheDocument();
    expect(within(panel).getByText("Read")).toBeInTheDocument();
    expect(within(panel).getByText("Restart the example service")).toBeInTheDocument();
    expect(within(panel).getByText("Write")).toBeInTheDocument();
    expect(within(panel).getByText("needs an approved action")).toBeInTheDocument();
    expect(within(panel).getAllByText("scope: example")).toHaveLength(2);
    // Nothing in Connect dispatches an action, so there is no Run control and no confirmation dialog to test.
    expect(within(panel).queryByRole("button", { name: /Run|Execute|Approve/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it("an unconfirmed result is never shown bare", async () => {
    server.use(
      http.get("/api/actions", () => HttpResponse.json([])),
      http.get("/api/receipts", () => HttpResponse.json([
        { id: "rcpt-2", action: "example.backup", dispatch_state: "dispatched", outcome: "UNKNOWN", started_at: "2026-10-01T08:12:00Z" },
      ])),
    );
    renderConnect();
    await userEvent.click(screen.getByRole("tab", { name: "Actions" }));
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("Unknown: the result was not confirmed")).toBeInTheDocument();
    expect(panel.textContent).not.toContain("UNKNOWN");
  });
  it("Advanced: diagnostics list config kinds and errors, with no password input and no Replace control", async () => {
    server.use(
      http.get("/api/config/provider", () => HttpResponse.json({ items: [], errors: [{ file: "providers.yaml", reason: "bad yaml" }] })),
      http.get("/api/config/request", () => HttpResponse.json({ items: [{ id: "weather.now", etag: '"v1"', object: { id: "weather.now", provider: "weather", method: "GET", path: "/", effect: "auto" } }], errors: [] })),
      http.get("/api/config/card", () => HttpResponse.json({ items: [], errors: [] })),
    );
    renderConnect();
    await userEvent.click(screen.getByRole("tab", { name: "Advanced" }));
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("Providers")).toBeInTheDocument();
    expect(within(panel).getAllByText("0 objects").length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText("Requests")).toBeInTheDocument();
    expect(within(panel).getByText("1 object")).toBeInTheDocument();
    expect(within(panel).getByText("providers.yaml")).toBeInTheDocument();
    expect(within(panel).getByText("bad yaml")).toBeInTheDocument();
    expect(within(panel).getByText(/Worlds stores a reference to a secret/)).toBeInTheDocument();
    expect(within(panel).queryByRole("button", { name: /Replace/ })).not.toBeInTheDocument();
    expect(within(panel).queryByLabelText(/value/i)).not.toBeInTheDocument();
    expect(panel.querySelector("input[type='password']")).not.toBeInTheDocument();
  });
  it("Advanced: with no errors, says every config file loaded cleanly", async () => {
    server.use(
      http.get("/api/config/provider", () => HttpResponse.json({ items: [], errors: [] })),
      http.get("/api/config/request", () => HttpResponse.json({ items: [], errors: [] })),
      http.get("/api/config/card", () => HttpResponse.json({ items: [], errors: [] })),
    );
    renderConnect();
    await userEvent.click(screen.getByRole("tab", { name: "Advanced" }));
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("None. Every config file loaded cleanly.")).toBeInTheDocument();
    expect(panel.querySelector("input[type='password']")).not.toBeInTheDocument();
  });
});

describe("Memory", () => {
  const renderMemory = () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(<QueryClientProvider client={client}><Memory /></QueryClientProvider>);
  };
  it("has the five tabs and one visible panel with a landmark heading", async () => {
    renderMemory();
    expect(tabNames()).toEqual(["Kept", "Later", "Records", "History", "Find"]);
    expect(screen.getAllByRole("tabpanel")).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1, name: "Memory" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Records" }));
    expect(screen.getByRole("tab", { name: "Records" })).toHaveAttribute("aria-selected", "true");
  });
  it("Records shows a locked placeholder for masked rows; each tab has its own sentence", async () => {
    renderMemory();
    const texts = new Set<string>();
    for (const name of ["Kept", "Later", "Records", "History", "Find"]) {
      await userEvent.click(screen.getByRole("tab", { name }));
      texts.add(screen.getByRole("tabpanel").textContent ?? "");
    }
    expect(texts.size).toBe(5);
    await userEvent.click(screen.getByRole("tab", { name: "Records" }));
    expect(screen.getByRole("tabpanel")).toHaveTextContent(/locked/i);
  });
  it("arrow keys move between tabs", async () => {
    renderMemory();
    screen.getByRole("tab", { name: "Kept" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Later" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Later" })).toHaveAttribute("aria-selected", "true");
  });
});
