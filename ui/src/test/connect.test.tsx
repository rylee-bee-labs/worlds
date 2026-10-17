import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { Connect } from "../fd/Connect";
import { actionRows, receiptRows } from "../fd/fixtures";
import { connectStore, handlers as fdHandlers } from "../fd/msw";
import type { CardConfig, Provider, Request as ConnRequest } from "../fd/types";

const server = setupServer(...fdHandlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => { cleanup(); server.resetHandlers(); connectStore.reset(); document.cookie = "pw_csrf=; max-age=0"; });
afterAll(() => server.close());

const renderConnect = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><Connect /></QueryClientProvider>);
};

const waitForSettled = () => waitFor(() => expect(screen.queryByText(/Loading/)).not.toBeInTheDocument(), { timeout: 2000 });

const sampleProvider: Provider = {
  id: "weather", name: "Weather", kind: "http", base_url: "https://example.test/weather",
  auth: { type: "bearer", secret_ref: "env:EXAMPLE_TOKEN" }, tls_verify: true,
};
const sampleReadRequest: ConnRequest = {
  id: "weather.now", provider: "weather", method: "GET", path: "/v1/now", effect: "auto",
};
const sampleWriteRequest: ConnRequest = {
  id: "weather.set", provider: "weather", method: "POST", path: "/v1/set", effect: "auto",
};
const sampleCard: CardConfig = {
  id: "weather-now", title: "Current weather", icon: "sun", group: "life",
  request: "weather.now", view: "stat", meaning: { short: "Right now", full: "Current conditions." },
};

describe("Connect: config listing", () => {
  it("providers, requests and cards list what the API returns, by id", async () => {
    connectStore.providers.set("weather", { object: sampleProvider, etag: '"v1"' });
    connectStore.requests.set("weather.now", { object: sampleReadRequest, etag: '"v1"' });
    connectStore.cardConfigs.set("weather-now", { object: sampleCard, etag: '"v1"' });
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Providers" }));
    expect(screen.getByRole("button", { name: "Weather" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Requests" }));
    expect(screen.getByRole("button", { name: "GET weather.now" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Cards" }));
    expect(screen.getByRole("button", { name: "Current weather · life" })).toBeInTheDocument();
  });

  it("empty is a distinct sentence per kind, not an error", async () => {
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Providers" }));
    expect(screen.getByText(/No providers yet/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Requests" }));
    expect(screen.getByText(/No saved requests yet/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Cards" }));
    expect(screen.getByText(/No cards yet/)).toBeInTheDocument();
  });

  it("error state shows plain words and a Retry button that refetches", async () => {
    server.use(http.get("/api/config/provider", () => HttpResponse.json({}, { status: 500 })));
    renderConnect();
    await userEvent.click(screen.getByRole("tab", { name: "Providers" }));
    expect(await screen.findByText("Couldn't load providers.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    server.use(http.get("/api/config/provider", () => HttpResponse.json({ items: [], errors: [] })));
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(/No providers yet/)).toBeInTheDocument();
  });
});

describe("Connect: try", () => {
  it("a write-like request: Try is disabled, 'needs an approved action' is visible, and the msw try handler is not called", async () => {
    connectStore.providers.set("weather", { object: sampleProvider, etag: '"v1"' });
    connectStore.requests.set("weather.set", { object: sampleWriteRequest, etag: '"v1"' });
    const trySpy = vi.fn(() => HttpResponse.json({ ok: true, status_code: 200 }));
    server.use(http.post("/api/connect/try", trySpy));
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Requests" }));
    await userEvent.click(screen.getByRole("button", { name: "POST weather.set" }));
    expect(await screen.findByText("needs an approved action")).toBeInTheDocument();
    const tryBtn = screen.queryByRole("button", { name: "Try" });
    expect(tryBtn).not.toBeInTheDocument();
    expect(trySpy).not.toHaveBeenCalled();
  });

  it("a read request: Try posts, then shows the status code, the duration and the sample as text", async () => {
    connectStore.providers.set("weather", { object: sampleProvider, etag: '"v1"' });
    connectStore.requests.set("weather.now", { object: sampleReadRequest, etag: '"v1"' });
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Requests" }));
    await userEvent.click(screen.getByRole("button", { name: "GET weather.now" }));
    await userEvent.click(await screen.findByRole("button", { name: "Try" }));
    expect(await screen.findByText(/Worked/)).toBeInTheDocument();
    expect(screen.getByText(/status 200/)).toBeInTheDocument();
    expect(screen.getByText(/42 ms/)).toBeInTheDocument();
    expect(screen.getByText(/"hello":"example"/)).toBeInTheDocument();
  });

  it("the sample is TEXT, not HTML — a sample containing markup must not create elements", async () => {
    connectStore.providers.set("weather", { object: sampleProvider, etag: '"v1"' });
    connectStore.requests.set("weather.now", { object: sampleReadRequest, etag: '"v1"' });
    server.use(http.post("/api/connect/try", () => HttpResponse.json({
      ok: true, status_code: 200, sample: '<p class="fake">xss</p>', truncated: false,
    })));
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Requests" }));
    await userEvent.click(screen.getByRole("button", { name: "GET weather.now" }));
    await userEvent.click(await screen.findByRole("button", { name: "Try" }));
    await screen.findByText(/Worked/);
    expect(document.querySelector(".fake")).not.toBeInTheDocument();
    expect(screen.getByText(/<p class="fake">xss<\/p>/)).toBeInTheDocument();
  });

  it("suggested_fields are listed", async () => {
    connectStore.providers.set("weather", { object: sampleProvider, etag: '"v1"' });
    connectStore.requests.set("weather.now", { object: sampleReadRequest, etag: '"v1"' });
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Requests" }));
    await userEvent.click(screen.getByRole("button", { name: "GET weather.now" }));
    await userEvent.click(await screen.findByRole("button", { name: "Try" }));
    expect(await screen.findByText("Suggested fields")).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("$.hello")).toBeInTheDocument();
  });

  it("429 from try is a plain 'wait a moment' message and no automatic retry fires", async () => {
    connectStore.providers.set("weather", { object: sampleProvider, etag: '"v1"' });
    connectStore.requests.set("weather.now", { object: sampleReadRequest, etag: '"v1"' });
    const trySpy = vi.fn(() => HttpResponse.json({ detail: "too many" }, { status: 429, headers: { "Retry-After": "60" } }));
    server.use(http.post("/api/connect/try", trySpy));
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Requests" }));
    await userEvent.click(screen.getByRole("button", { name: "GET weather.now" }));
    await userEvent.click(await screen.findByRole("button", { name: "Try" }));
    expect(await screen.findByText(/Too many tries\. Wait a moment\./)).toBeInTheDocument();
    expect(trySpy).toHaveBeenCalledTimes(1);
  });
});

describe("Connect: preview card", () => {
  it("posts {card, sample} and renders the envelope's field text, text_equivalent and evidence", async () => {
    connectStore.providers.set("weather", { object: sampleProvider, etag: '"v1"' });
    connectStore.requests.set("weather.now", { object: sampleReadRequest, etag: '"v1"' });
    connectStore.cardConfigs.set("weather-now", { object: sampleCard, etag: '"v1"' });
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Cards" }));
    await userEvent.click(screen.getByRole("button", { name: "Current weather · life" }));
    const sampleInput = await screen.findByRole("textbox", { name: "Sample (text)" });
    await userEvent.clear(sampleInput);
    await userEvent.type(sampleInput, "hello example");
    await userEvent.click(screen.getByRole("button", { name: "Preview with sample" }));
    expect(await screen.findByText(/Healthy/)).toBeInTheDocument();
    expect(screen.getByText(/Meter: 100 percent/)).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(screen.getByText("example")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Evidence"));
    expect(screen.getByText(/request_id:/)).toBeInTheDocument();
    expect(screen.getByText(/method: GET/)).toBeInTheDocument();
  });

  it("a values entry of {'text':'unknown'} renders the word unknown, not 0", async () => {
    connectStore.requests.set("weather.now", { object: sampleReadRequest, etag: '"v1"' });
    connectStore.cardConfigs.set("weather-now", { object: sampleCard, etag: '"v1"' });
    server.use(http.post("/api/connect/preview", () => HttpResponse.json({
      card_id: "weather-now", source_state: "unknown", freshness: "stale",
      observed_at: null, fetched_at: "2026-10-01T09:30:00Z", last_good_at: null,
      values: { count: { text: "unknown" } }, meter: null,
      meaning: { short: "x", full: "y" },
      evidence: { request_id: "weather.now", method: "GET", path: "/v1/now" },
    })));
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Cards" }));
    await userEvent.click(screen.getByRole("button", { name: "Current weather · life" }));
    const sampleInput = await screen.findByRole("textbox", { name: "Sample (text)" });
    await userEvent.clear(sampleInput);
    await userEvent.type(sampleInput, "x");
    await userEvent.click(screen.getByRole("button", { name: "Preview with sample" }));
    expect(await screen.findByText("unknown")).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("preview with {card, request} against a saved read request renders the envelope", async () => {
    connectStore.providers.set("weather", { object: sampleProvider, etag: '"v1"' });
    connectStore.requests.set("weather.now", { object: sampleReadRequest, etag: '"v1"' });
    connectStore.cardConfigs.set("weather-now", { object: { ...sampleCard, request: "weather.now" }, etag: '"v1"' });
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Cards" }));
    await userEvent.click(screen.getByRole("button", { name: "Current weather · life" }));
    await userEvent.click(await screen.findByRole("button", { name: "Preview from request" }));
    expect(await screen.findByText(/Healthy/)).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
  });
});

describe("Connect: save", () => {
  it("save does PUT with if-match and the CSRF header when pw_csrf is set; on 200 the new etag is used for the next save", async () => {
    document.cookie = "pw_csrf=tok123";
    connectStore.providers.set("weather", { object: sampleProvider, etag: '"v1"' });
    const puts: { ifMatch: string | null; csrf: string | null }[] = [];
    server.use(http.put("/api/config/provider/:id", async ({ request }) => {
      puts.push({ ifMatch: request.headers.get("if-match"), csrf: request.headers.get("x-csrf-token") });
      const r = connectStore.put("provider", String(request.url).split("/").pop()!, request.headers.get("if-match"), null, (await request.json()) as Provider);
      return HttpResponse.json(r.body, { status: r.status, headers: { etag: r.etag } });
    }));
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Providers" }));
    await userEvent.click(screen.getByRole("button", { name: "Weather" }));
    const nameField = await screen.findByLabelText("Name");
    await userEvent.clear(nameField);
    await userEvent.type(nameField, "Weather (updated)");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0].ifMatch).toBe('"v1"');
    expect(puts[0].csrf).toBe("tok123");
  });

  it("409 on save says it changed elsewhere and shows the error", async () => {
    connectStore.providers.set("weather", { object: sampleProvider, etag: '"v1"' });
    server.use(http.put("/api/config/provider/:id", () => HttpResponse.json({ detail: "changed" }, { status: 409 })));
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Providers" }));
    await userEvent.click(screen.getByRole("button", { name: "Weather" }));
    await userEvent.click(await screen.findByRole("button", { name: "Save" }));
    expect(await screen.findByText(/Changed somewhere else/)).toBeInTheDocument();
  });

  it("422 shows the server's detail", async () => {
    connectStore.providers.set("weather", { object: sampleProvider, etag: '"v1"' });
    server.use(http.put("/api/config/provider/:id", () => HttpResponse.json({ detail: "provider weather: invalid base_url" }, { status: 422 })));
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Providers" }));
    await userEvent.click(screen.getByRole("button", { name: "Weather" }));
    await userEvent.click(await screen.findByRole("button", { name: "Save" }));
    expect(await screen.findByText("provider weather: invalid base_url")).toBeInTheDocument();
  });
});

describe("Connect: secret_ref", () => {
  it("auth.secret_ref with a value present shows 'Reference set'; with none shows 'No reference'. The screen shows the reference NAME only", async () => {
    connectStore.providers.set("weather", { object: sampleProvider, etag: '"v1"' });
    connectStore.providers.set("local", { object: { ...sampleProvider, id: "local", name: "Local", auth: { type: "none" } }, etag: '"v1"' });
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Providers" }));
    await userEvent.click(screen.getByRole("button", { name: "Weather" }));
    expect(await screen.findByText("Reference set")).toBeInTheDocument();
    expect(screen.getByDisplayValue("env:EXAMPLE_TOKEN")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await userEvent.click(screen.getByRole("button", { name: "Local" }));
    expect(await screen.findByText("No reference")).toBeInTheDocument();
  });
});

describe("Connect: Advanced diagnostics", () => {
  it("shows config errors from the API with their reasons, and there is no password input", async () => {
    server.use(
      http.get("/api/config/provider", () => HttpResponse.json({ items: [], errors: [{ file: "providers.yaml", reason: "bad yaml" }] })),
      http.get("/api/config/request", () => HttpResponse.json({ items: [], errors: [] })),
      http.get("/api/config/card", () => HttpResponse.json({ items: [], errors: [] })),
    );
    renderConnect();
    await userEvent.click(screen.getByRole("tab", { name: "Advanced" }));
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("providers.yaml")).toBeInTheDocument();
    expect(within(panel).getByText("bad yaml")).toBeInTheDocument();
    expect(within(panel).getByText(/Worlds stores a reference to a secret/)).toBeInTheDocument();
    expect(panel.querySelector("input[type='password']")).not.toBeInTheDocument();
    expect(within(panel).queryByRole("button", { name: /Replace/ })).not.toBeInTheDocument();
  });
});

describe("Connect: Advanced panel assertions (real content)", () => {
  it("the diagnostics panel exists and shows config kinds and the secret-reference note", async () => {
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Advanced" }));
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("Config kinds")).toBeInTheDocument();
    expect(within(panel).getByText("Providers")).toBeInTheDocument();
    expect(within(panel).getByText("Requests")).toBeInTheDocument();
    expect(within(panel).getByText("Cards")).toBeInTheDocument();
    expect(within(panel).getByText("Config errors")).toBeInTheDocument();
    expect(within(panel).getByText(/Worlds stores a reference to a secret/)).toBeInTheDocument();
  });
});

describe("Connect: actions and receipts", () => {
  it("lists the real actions with read/write words, scope and exposure, and no Run control", async () => {
    connectStore.actions = actionRows;
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Actions" }));
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("Read the example queue")).toBeInTheDocument();
    expect(within(panel).getByText("Read")).toBeInTheDocument();
    expect(within(panel).getByText("Restart the example service")).toBeInTheDocument();
    expect(within(panel).getByText("Write")).toBeInTheDocument();
    expect(within(panel).getByText("needs an approved action")).toBeInTheDocument();
    expect(within(panel).getAllByText("scope: example")).toHaveLength(2);
    expect(within(panel).getByText("Exposed")).toBeInTheDocument();
    expect(within(panel).getByText("Not exposed")).toBeInTheDocument();
    // Nothing in Connect dispatches an action: no Run control, no dialog.
    expect(within(panel).queryByRole("button", { name: /Run|Execute|Approve/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows recent activity read-only: action, dispatch state, outcome and timestamps", async () => {
    connectStore.receipts = receiptRows;
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Actions" }));
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("example.restart")).toBeInTheDocument();
    expect(within(panel).getByText("succeeded")).toBeInTheDocument();
    expect(within(panel).getByText("Succeeded")).toBeInTheDocument();
    expect(within(panel).getByText("started 2026-10-01T09:30:00Z")).toBeInTheDocument();
    expect(within(panel).getByText("finished 2026-10-01T09:30:00Z")).toBeInTheDocument();
  });

  it("an unconfirmed outcome is never shown bare", async () => {
    connectStore.receipts = receiptRows;
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Actions" }));
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("Unknown: the result was not confirmed")).toBeInTheDocument();
    expect(panel.textContent).not.toContain("UNKNOWN");
  });

  it("empty actions and receipts each have their own plain sentence", async () => {
    renderConnect();
    await waitForSettled();
    await userEvent.click(screen.getByRole("tab", { name: "Actions" }));
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("Nothing connected yet.")).toBeInTheDocument();
    expect(within(panel).getByText("No activity yet. Nothing has run.")).toBeInTheDocument();
  });

  it("an actions error shows plain words and a Retry that refetches", async () => {
    server.use(http.get("/api/actions", () => HttpResponse.json({}, { status: 500 })));
    renderConnect();
    await userEvent.click(screen.getByRole("tab", { name: "Actions" }));
    const panel = screen.getByRole("tabpanel");
    expect(await within(panel).findByText("Couldn't load actions.")).toBeInTheDocument();
    server.use(http.get("/api/actions", () => HttpResponse.json(actionRows)));
    await userEvent.click(within(panel).getByRole("button", { name: "Retry" }));
    expect(await within(panel).findByText("Read the example queue")).toBeInTheDocument();
  });
});
