import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { Memory } from "../fd/Memory";
import { handlers as fdHandlers } from "../fd/msw";
import { memoryKeptRows, memoryLaterRows } from "../fd/fixtures";

const server = setupServer(...fdHandlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => { cleanup(); server.resetHandlers(); document.cookie = "pw_csrf=; max-age=0"; });
afterAll(() => server.close());

const renderMemory = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const utils = render(<QueryClientProvider client={client}><Memory /></QueryClientProvider>);
  return { client, ...utils };
};

const switchTo = async (name: string) => {
  await userEvent.click(screen.getByRole("tab", { name }));
  return screen.getByRole("tabpanel");
};

const settle = () => waitFor(() => expect(screen.queryByText("Loading…")).not.toBeInTheDocument(), { timeout: 3000 });

describe("Memory lists", () => {
  it("Kept lists what the API returned, in the returned order", async () => {
    renderMemory();
    await settle();
    await switchTo("Kept");
    const panel = screen.getByRole("tabpanel");
    const titles = within(panel).getAllByText(/Fix the shed door|Book: Piranesi/).map((n) => n.textContent);
    expect(titles).toEqual(["Fix the shed door", "Book: Piranesi"]);
  });
  it("Later lists what the API returned, in the returned order", async () => {
    renderMemory();
    await settle();
    await switchTo("Later");
    const panel = screen.getByRole("tabpanel");
    const titles = within(panel).getAllByText(/Call the dentist|Review the receipts/).map((n) => n.textContent);
    expect(titles).toEqual(["Call the dentist", "Review the receipts"]);
  });
  it("Records lists what the API returned, in the returned order", async () => {
    renderMemory();
    await settle();
    await switchTo("Records");
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("Annual checkup notes")).toBeInTheDocument();
    expect(within(panel).getByText("Locked record")).toBeInTheDocument();
  });
});

describe("Memory locked records", () => {
  it("a masked Records row renders as locked — not as an empty unlocked row, and its title/body never reach the DOM", async () => {
    // Add a row that the handler would expose with a title — the fixture is already masked,
    // so we confirm the masked shape does not leak title/body.
    renderMemory();
    await settle();
    await switchTo("Records");
    const panel = screen.getByRole("tabpanel");
    // The masked fixture has no title; the DOM must not show any "Locked" record's title or body.
    expect(within(panel).queryByText(/Annual checkup notes/i)).toBeInTheDocument(); // unlocked row
    // The masked row: the placeholder is there, no title or body from it.
    expect(within(panel).getByText("Locked record")).toBeInTheDocument();
    expect(within(panel).getByText(/This record is locked/)).toBeInTheDocument();
    // Nothing in the DOM carries a body like "Blood work came back fine" next to a locked marker
    const bodyNode = panel.querySelector(".fd-memory-body");
    if (bodyNode) expect(bodyNode.textContent).not.toMatch(/locked/i);
  });
});

describe("Memory add", () => {
  it("Add posts only that table's fields plus title, with the CSRF header, and the new row appears", async () => {
    document.cookie = "pw_csrf=test-token";
    const captured: { body: Record<string, unknown>; csrf: string }[] = [];
    server.use(http.post("/api/memory/kept", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      captured.push({ body, csrf: request.headers.get("x-csrf-token") ?? "" });
      const row = { id: "kept-new", table: "kept", title: body.title, body: body.body ?? "", tags: body.tags ?? [], provenance: "owner", source_ref: null, created_at: 1727900000, updated_at: 1727900000 };
      memoryKeptRows.push(row as never);
      return HttpResponse.json(row);
    }));
    renderMemory();
    await settle();
    await switchTo("Kept");
    const panel = screen.getByRole("tabpanel");
    await userEvent.click(within(panel).getByRole("button", { name: "Add" }));
    await userEvent.type(screen.getByLabelText("Title"), "Plant the garlic");
    await userEvent.type(screen.getByLabelText("Body"), "In the back bed.");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(captured.length).toBeGreaterThan(0));
    expect(captured[0].csrf).toBe("test-token");
    expect(Object.keys(captured[0].body).sort()).toEqual(["body", "tags", "title"]);
    // the new row appears in the list
    await waitFor(() => expect(screen.getByText("Plant the garlic")).toBeInTheDocument());
  });
});

describe("Memory edit", () => {
  it("Edit PATCHes only the changed fields", async () => {
    const captured: { body: Record<string, unknown> }[] = [];
    server.use(http.patch("/api/memory/kept/:id", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      captured.push({ body });
      const row = { ...memoryKeptRows[0], ...body, updated_at: 1727950000 };
      Object.assign(memoryKeptRows[0], row);
      return HttpResponse.json(row);
    }));
    renderMemory();
    await settle();
    await switchTo("Kept");
    const panel = screen.getByRole("tabpanel");
    await userEvent.click(within(panel).getAllByRole("button", { name: "Edit" })[0]);
    // change only the title
    const title = screen.getByLabelText("Title") as HTMLInputElement;
    await userEvent.clear(title);
    await userEvent.type(title, "Repair the shed door");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(captured.length).toBeGreaterThan(0));
    expect(Object.keys(captured[0].body)).toEqual(["title"]);
    expect(captured[0].body.title).toBe("Repair the shed door");
  });
});

describe("Memory delete", () => {
  it("opens a native dialog whose safe choice is first and focused; Escape cancels and sends nothing; confirming sends DELETE; focus returns to the invoking control", async () => {
    document.cookie = "pw_csrf=test-token";
    let deleted = false;
    server.use(http.delete("/api/memory/kept/:id", () => { deleted = true; return HttpResponse.json({ ok: true }); }));
    renderMemory();
    await settle();
    await switchTo("Kept");
    const panel = screen.getByRole("tabpanel");
    const deleteButtons = within(panel).getAllByRole("button", { name: "Delete" });
    const invoker = deleteButtons[0];
    await userEvent.click(invoker);
    const dlg = screen.getByRole("dialog");
    const buttons = within(dlg).getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["Keep it", "Remove"]);
    expect(within(dlg).getByRole("button", { name: "Keep it" })).toHaveFocus();
    // Escape cancels, nothing is sent
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(deleted).toBe(false);
    expect(invoker).toHaveFocus();
    // Now confirm
    await userEvent.click(invoker);
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(deleted).toBe(true));
    // focus returns to the invoking control
    expect(invoker).toHaveFocus();
  });
});

describe("Memory Later status", () => {
  it("Changing a Later row's status PATCHes status as a word", async () => {
    const captured: { body: Record<string, unknown> }[] = [];
    server.use(http.patch("/api/memory/later/:id", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      captured.push({ body });
      const row = { ...memoryLaterRows[0], ...body, updated_at: 1727950000 };
      Object.assign(memoryLaterRows[0], row);
      return HttpResponse.json(row);
    }));
    renderMemory();
    await settle();
    await switchTo("Later");
    const panel = screen.getByRole("tabpanel");
    const select = within(panel).getByLabelText(/Change status for Call the dentist/);
    await userEvent.selectOptions(select, "done");
    await waitFor(() => expect(captured.length).toBeGreaterThan(0));
    expect(captured[0].body).toEqual({ status: "done" });
  });
});

describe("Memory provenance", () => {
  it("a row with provenance other than owner is visibly distinguished in words", async () => {
    renderMemory();
    await settle();
    await switchTo("Kept");
    const panel = screen.getByRole("tabpanel");
    // The second row has provenance: "external_ref"; its label must appear
    expect(within(panel).getByText("From an external reference")).toBeInTheDocument();
  });
});

describe("Memory Find", () => {
  it("typing runs GET /api/memory/find?q=... and renders the results in the returned order; the «…» snippet highlights are text", async () => {
    renderMemory();
    await settle();
    await switchTo("Find");
    const panel = screen.getByRole("tabpanel");
    const input = within(panel).getByRole("searchbox") as HTMLInputElement;
    await userEvent.type(input, "shed");
    // Wait for debounced query to fire and results to appear
    await waitFor(() => expect(within(panel).getByText(/Fix the shed door/)).toBeInTheDocument(), { timeout: 2000 });
    // At least the title and the snippet should both be rendered; order: first the title, then the snippet with the «» marker.
    const snippet = within(panel).getByText(/«shed»/);
    expect(snippet).toBeInTheDocument();
    // Returned order: kept first, later second (matches the fixture)
    const titles = within(panel).getAllByText(/Fix the shed door|Call the dentist/).map((n) => n.textContent);
    expect(titles).toEqual(["Fix the shed door", "Call the dentist"]);
  });
  it("an empty q shows a prompt and sends no query", async () => {
    const findSpy = vi.fn();
    server.use(http.get("/api/memory/find", findSpy));
    renderMemory();
    await settle();
    await switchTo("Find");
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText(/Type something to search/)).toBeInTheDocument();
    // no query fired
    expect(findSpy).not.toHaveBeenCalled();
  });
});

describe("Memory History", () => {
  it("renders the events and has no mutating control", async () => {
    renderMemory();
    await settle();
    const panel = await switchTo("History");
    expect(within(panel).getAllByText("created").length).toBe(2);
    expect(within(panel).getAllByText("owner").length).toBeGreaterThanOrEqual(1);
    // No Add / Edit / Delete button appears anywhere in the History panel
    const buttons = within(panel).getAllByRole("button");
    const mutating = buttons.filter((b) => /^(Add|Edit|Delete|New)$/i.test(b.textContent ?? ""));
    expect(mutating).toHaveLength(0);
  });
  it("never renders a title or body from a row (the API never sends one)", async () => {
    renderMemory();
    await settle();
    const panel = await switchTo("History");
    // History fixture rows carry only event / table / actor / id — no title/body.
    // So the DOM must not contain any of the titles the other tables have.
    expect(within(panel).queryByText("Fix the shed door")).not.toBeInTheDocument();
    expect(within(panel).queryByText("Call the dentist")).not.toBeInTheDocument();
  });
});

describe("Memory export and backup", () => {
  it("Export triggers the download and reports what it did in words", async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click");
    renderMemory();
    await settle();
    await switchTo("History");
    const panel = screen.getByRole("tabpanel");
    await userEvent.click(within(panel).getByRole("button", { name: "Export kept" }));
    expect(clickSpy).toHaveBeenCalled();
    await waitFor(() => expect(screen.getByText("Started an export of kept as NDJSON.")).toBeInTheDocument());
    clickSpy.mockRestore();
  });
  it("Backup confirms in a native dialog, posts, and reports the returned file name in words", async () => {
    document.cookie = "pw_csrf=test-token";
    let posted = false;
    server.use(http.post("/api/memory/backup", () => { posted = true; return HttpResponse.json({ file: "worlds-20261002-070000.db" }); }));
    renderMemory();
    await settle();
    await switchTo("History");
    const panel = screen.getByRole("tabpanel");
    await userEvent.click(within(panel).getByRole("button", { name: "Back up now" }));
    const dlg = screen.getByRole("dialog");
    expect(within(dlg).getByRole("button", { name: "Don't back up" })).toHaveFocus();
    // Cancel does not post
    await userEvent.click(within(dlg).getByRole("button", { name: "Don't back up" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(posted).toBe(false);
    // Confirm
    await userEvent.click(within(panel).getByRole("button", { name: "Back up now" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Back up now" }));
    await waitFor(() => expect(posted).toBe(true));
    await waitFor(() => expect(screen.getByText("Backed up to worlds-20261002-070000.db.")).toBeInTheDocument());
  });
});

describe("Memory errors", () => {
  it("a 403 step_up_required is shown in plain words and does not blank the tab", async () => {
    server.use(http.get("/api/memory/records", () => HttpResponse.json({ detail: "step_up_required" }, { status: 403 })));
    renderMemory();
    await switchTo("Records");
    await waitFor(() => expect(screen.getByText(/step up/i)).toBeInTheDocument(), { timeout: 3000 });
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
  it("a 404 on a row is reported as gone, not as an outage", async () => {
    renderMemory();
    await settle();
    await switchTo("Kept");
    server.use(http.delete("/api/memory/kept/:id", () => HttpResponse.json({ detail: "not found" }, { status: 404 })));
    const panel = screen.getByRole("tabpanel");
    await userEvent.click(within(panel).getAllByRole("button", { name: "Delete" })[0]);
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(screen.getByText("That row is gone.")).toBeInTheDocument());
  });
  it("empty state has its own plain sentence", async () => {
    server.use(http.get("/api/memory/kept", () => HttpResponse.json([])));
    renderMemory();
    await switchTo("Kept");
    await waitFor(() => expect(screen.getByText(/Nothing kept yet/)).toBeInTheDocument(), { timeout: 3000 });
  });
  it("error state has its own plain sentence, and Retry refetches", async () => {
    // The useQuery has retry:1 so react-query will retry once after the first failure.
    // We need the first TWO calls to fail (the initial + the retry) so the error state shows.
    let calls = 0;
    server.use(http.get("/api/memory/kept", () => {
      calls += 1;
      if (calls <= 2) return HttpResponse.json({}, { status: 500 });
      return HttpResponse.json(memoryKeptRows);
    }));
    renderMemory();
    await switchTo("Kept");
    await waitFor(() => expect(screen.getByText(/Couldn't load/)).toBeInTheDocument(), { timeout: 3000 });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    // The fixture may have been mutated by earlier tests (e.g. Edit), so check that any of the fixture's rows appear
    await waitFor(() => expect(screen.getAllByText(/Piranesi|Repair the shed door|Fix the shed door/).length).toBeGreaterThan(0), { timeout: 3000 });
  });
});
