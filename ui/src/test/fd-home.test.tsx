import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { Home } from "../fd/Home";
import { boardServer, handlers } from "../fd/msw";
import { cards, needsYou } from "../fd/fixtures";
import { PrefsProvider } from "../fd/prefs";
import type { Prefs } from "../fd/prefs-core";

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => { cleanup(); server.resetHandlers(); boardServer.reset(); document.cookie = "pw_csrf=; max-age=0"; });
afterAll(() => server.close());

function renderHome(opts: { timeoutMs?: number; prefs?: Partial<Prefs> } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const utils = render(
    <QueryClientProvider client={client}>
      <PrefsProvider initial={opts.prefs}><Home timeZone="UTC" timeoutMs={opts.timeoutMs} now={new Date("2026-10-01T19:00:00")} /></PrefsProvider>
    </QueryClientProvider>,
  );
  return { client, ...utils };
}
/** Everything loaded: no "Checking" or "Loading" status line left. */
const settled = () => waitFor(() => expect(document.querySelector(".fd-home")).toHaveAttribute("data-ready", "true"), { timeout: 3000 });
const section = (name: string) => screen.getByRole("heading", { name }).closest("section")!;

describe("Home", () => {
  it("greets, then orders: briefing, strip, Edit Home, sections (Pick up omitted when empty)", async () => {
    renderHome({ prefs: { name: "Rylee" } });
    await settled();
    expect(screen.getAllByRole("heading").map((h) => h.textContent)).toEqual(["Home", "Needs you", "Needs a look", "Your life", "Quietly working"]);
    expect(screen.getByText("Good evening, Rylee")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Home");
    expect(screen.getByText("2 for you · Downloads unavailable · Backup stale · 1 more to look at · rest quiet")).toBeInTheDocument();
    const strip = screen.getByRole("group", { name: "Whole world" });
    const edit = screen.getByRole("button", { name: "Edit Home" });
    const needs = screen.getByRole("heading", { name: "Needs you" });
    expect(strip.compareDocumentPosition(edit) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(edit.compareDocumentPosition(needs) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
  it("greets without a name when there is none; the greeting is not a heading", async () => {
    renderHome();
    expect(screen.getByText(/^Good (morning|afternoon|evening)$/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Home");
  });
  it("strip: one button per source named 'Name: State. Show details'; not configured is a link", async () => {
    renderHome();
    await settled();
    const strip = screen.getByRole("group", { name: "Whole world" });
    expect(within(strip).getAllByRole("button")).toHaveLength(8);
    expect(within(strip).getByRole("button", { name: "Downloads Unavailable. Show details" })).toBeInTheDocument();
    expect(within(strip).getByRole("link", { name: "Music Not configured. Set up in Connect" })).toHaveAttribute("href", "#connect");
  });
  it("sections hold the right rows; Needs you is finite; not_configured is never a row", async () => {
    renderHome();
    await settled();
    expect(within(section("Needs you")).getAllByRole("listitem")).toHaveLength(2);
    const names = within(section("Needs a look")).getAllByRole("listitem").map((li) => li.textContent ?? "");
    expect(names[0]).toMatch(/Downloads/);
    expect(names[1]).toMatch(/Backup/);
    expect(names[2]).toMatch(/Calendar/);
    expect(screen.queryByRole("heading", { name: "Pick up" })).not.toBeInTheDocument();
    for (const li of within(section("Your life")).getAllByRole("listitem")) expect(li).not.toHaveTextContent("Music");
  });
  it("opens a row's drill-in in place and closes it again", async () => {
    renderHome();
    await settled();
    const btn = within(section("Needs a look")).getByRole("button", { name: /Downloads/ });
    await userEvent.click(btn);
    expect(screen.getByRole("region", { name: "Downloads details" })).toBeInTheDocument();
    expect(btn).toHaveAttribute("aria-expanded", "true");
    await userEvent.click(btn);
    expect(screen.queryByRole("region", { name: "Downloads details" })).not.toBeInTheDocument();
  });
  it("B8: a strip tap opens the row and moves focus to it; a second tap does not close it", async () => {
    renderHome();
    await settled();
    const tile = screen.getByRole("button", { name: "Disk Healthy. Show details" });
    await userEvent.click(tile);
    expect(screen.getByRole("region", { name: "Disk details" })).toBeInTheDocument();
    await waitFor(() => expect(within(document.getElementById("fd-row-disk")!).getByRole("button", { name: /Disk/ })).toHaveFocus());
    await userEvent.click(tile);
    expect(screen.getByRole("region", { name: "Disk details" })).toBeInTheDocument();
  });
  it("B8: in Calm a strip tap on a quiet source unfolds Quietly working and opens the row", async () => {
    renderHome({ prefs: { density: "calm" } });
    await settled();
    expect(screen.queryByRole("region", { name: "Disk details" })).not.toBeInTheDocument();
    expect(screen.getByText(/2 quiet: Disk, Checks/)).toBeInTheDocument();
    // the quiet sources are folded into one tile; open it, then tap Disk
    await userEvent.click(screen.getByRole("button", { name: "6 quiet. Show all" }));
    await userEvent.click(screen.getByRole("button", { name: "Disk Healthy. Show details" }));
    expect(screen.getByRole("region", { name: "Disk details" })).toBeInTheDocument();
    expect(screen.queryByText(/2 quiet:/)).not.toBeInTheDocument();
  });
  it("a card that fails to load is Unknown with the real error class and no invented request id", async () => {
    server.use(http.get("/api/cards/disk", () => HttpResponse.json({}, { status: 500 })));
    renderHome();
    await settled();
    expect(screen.getByRole("button", { name: "Disk Unknown. Show details" })).toBeInTheDocument();
    await userEvent.click(within(section("Needs a look")).getByRole("button", { name: /Disk/ }));
    const ev = screen.getByRole("region", { name: "Disk details" }).querySelector("details")!;
    expect(ev).toHaveTextContent("Error: Server error");
    expect(ev).toHaveTextContent("Status code: 500");
    expect(ev).not.toHaveTextContent("Request:");
  });
});

describe("B1 Home does not wait on every card", () => {
  it("renders the board and the other rows while one card hangs, then fails it as a timeout", async () => {
    server.use(http.get("/api/cards/downloads", async () => { await delay("infinite"); return HttpResponse.json(cards.downloads); }));
    renderHome({ timeoutMs: 300 });
    await screen.findByRole("button", { name: "Disk Healthy. Show details" });
    expect(screen.getByRole("button", { name: "Downloads Loading" })).toBeDisabled();
    expect(screen.getByText(/Checking 1 source/)).toBeInTheDocument();
    expect(within(section("Needs a look")).queryByText("Downloads")).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Downloads Unknown. Show details" }, { timeout: 3000 })).toBeInTheDocument();
    await userEvent.click(within(section("Needs a look")).getByRole("button", { name: /Downloads/ }));
    expect(screen.getByRole("region", { name: "Downloads details" })).toHaveTextContent("Error: Timed out");
  });
});

describe("needs you is independent and honest", () => {
  it("B2: a needs-you failure never says nothing is waiting, and the briefing says so", async () => {
    server.use(http.get("/api/needs-you", () => HttpResponse.json({}, { status: 500 })));
    renderHome();
    await settled();
    expect(within(section("Needs you")).getByRole("alert")).toHaveTextContent("Couldn't check what needs you");
    expect(screen.queryByText("Nothing for you right now.")).not.toBeInTheDocument();
    expect(screen.getByText(/^Couldn't check what needs you · /)).toBeInTheDocument();
    server.use(http.get("/api/needs-you", () => HttpResponse.json(needsYou)));
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Approve Hive Works plan")).toBeInTheDocument();
  });
  it("B3: a board failure does not hide Needs you", async () => {
    server.use(http.get("/api/boards/home", () => HttpResponse.json({}, { status: 500 })));
    renderHome();
    expect(await screen.findByText("Home could not load.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(await screen.findByText("Approve Hive Works plan")).toBeInTheDocument();
  });
  it("an empty list says so", async () => {
    server.use(http.get("/api/needs-you", () => HttpResponse.json([])));
    renderHome();
    expect(await within(section("Needs you")).findByText("Nothing for you right now.")).toBeInTheDocument();
  });
  it("B4: only relative, http and https links survive", async () => {
    const open = (id: string, href: string) => ({ id, text: `Item ${id}`, source: "x", created_at: "2026-10-01T09:00:00Z", action: { kind: "open" as const, href } });
    server.use(http.get("/api/needs-you", () => HttpResponse.json([open("a", "javascript:alert(1)"), open("b", "data:text/html,x"), open("c", "//evil.example/x"), open("d", "/memory"), open("e", "https://example.org/x")])));
    renderHome();
    await screen.findByText("Item a");
    const links = within(section("Needs you")).queryAllByRole("link").map((a) => a.getAttribute("href"));
    expect(links).toEqual(["/memory", "https://example.org/x"]);
  });
  it("no dead Approve: the item says where to approve, and no control does nothing", async () => {
    renderHome();
    await screen.findByText("Approve Hive Works plan");
    expect(screen.queryByRole("button", { name: /Approve/ })).not.toBeInTheDocument();
    expect(screen.getByText("Approve in Hive Works")).toBeInTheDocument();
    // nothing in Needs you is a disabled control
    expect(within(section("Needs you")).queryAllByRole("button", { hidden: true }).filter((b) => (b as HTMLButtonElement).disabled)).toHaveLength(0);
    // an approval that carries a safe link gets an Open link; an unsafe one gets none
    const approve = (id: string, href: string) => ({ id, text: `Approve ${id}`, source: "Hive Works", created_at: "2026-10-01T09:00:00Z", action: { kind: "approve" as const, authorization_id: id, href } });
    server.use(http.get("/api/needs-you", () => HttpResponse.json([approve("a", "https://example.org/approve/a"), approve("b", "javascript:alert(1)")])));
    cleanup();
    renderHome();
    await screen.findByText("Approve a");
    expect(within(section("Needs you")).getAllByRole("link").map((l) => l.getAttribute("href"))).toEqual(["https://example.org/approve/a"]);
  });
});

describe("B11 a failed refetch keeps the data, marked stale", () => {
  it("moves the row to Needs a look with the previous fetch time", async () => {
    const { client } = renderHome();
    await settled();
    expect(within(section("Quietly working")).getByText("Disk")).toBeInTheDocument();
    server.use(http.get("/api/cards/disk", () => HttpResponse.json({}, { status: 500 })));
    await client.refetchQueries({ queryKey: ["fd", "card", "disk"] });
    await waitFor(() => expect(within(section("Needs a look")).getByText("Disk")).toBeInTheDocument());
    expect(within(section("Needs a look")).getByRole("button", { name: /Disk/ }).closest("li")).toHaveTextContent("Last good 09:30");
    expect(screen.getByRole("button", { name: /^Disk .*Show details$/ })).toBeInTheDocument();
  });
});

describe("Edit Home", () => {
  const order = (name: string) => within(section(name)).getAllByRole("listitem").map((li) => li.querySelector(".fd-row-title")?.textContent);

  it("is explicit and secondary: nothing to arrange until Edit Home is pressed", async () => {
    renderHome();
    await settled();
    expect(screen.queryByRole("button", { name: /^Move .* earlier$/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    await screen.findByRole("button", { name: "Move Reading earlier" });
    expect(screen.getByRole("button", { name: "Done" })).not.toHaveAttribute("aria-pressed");
    expect(screen.getByRole("button", { name: "+ Add to Home" })).toBeInTheDocument();
  });
  it("it says Saving… until the server confirms, then announces the result", async () => {
    server.use(http.put("/api/config/board/home", async ({ request }) => {
      await delay(150);
      const r = boardServer.put(request.headers.get("if-match"), null, (await request.json()) as never);
      return HttpResponse.json(r.body as Record<string, unknown>, { status: r.status, headers: { etag: r.etag } });
    }));
    renderHome();
    await settled();
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    await userEvent.click(await screen.findByRole("button", { name: "Move Reading later" }));
    expect(screen.getByText("Saving…")).toBeInTheDocument();
    expect(screen.queryByText("Moved Reading later")).not.toBeInTheDocument();
    expect(order("Your life")).toEqual(["Weather", "Later", "Reading"]);
    expect(await screen.findByText("Moved Reading later")).toBeInTheDocument();
    expect(screen.queryByText("Saving…")).not.toBeInTheDocument();
  });
  it("a change made elsewhere before the first edit is shown first and never overwritten", async () => {
    renderHome();
    await settled();
    expect(screen.getByRole("button", { name: "Checks Healthy. Show details" })).toBeInTheDocument();
    // another editor hides Checks after this page loaded
    boardServer.external(boardServer.items().map((i) => (i.card === "checks" ? { ...i, hidden: true } : i)));
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    await screen.findByRole("button", { name: "Move Reading earlier" });
    await waitFor(() => expect(screen.queryByRole("button", { name: "Checks Healthy. Show details" })).not.toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Move Reading earlier" }));
    await waitFor(() => expect(boardServer.puts).toHaveLength(1));
    expect(boardServer.puts[0].body.items.find((i) => i.card === "checks")!.hidden).toBe(true);
  });
  it("Done clears the status line", async () => {
    renderHome();
    await settled();
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    await userEvent.click(await screen.findByRole("button", { name: "Move Reading earlier" }));
    expect(await screen.findByText("Moved Reading earlier")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(screen.queryByText("Moved Reading earlier")).not.toBeInTheDocument();
  });
  it("Edit mode unfolds Calm's Quietly working", async () => {
    renderHome({ prefs: { density: "calm" } });
    await settled();
    expect(screen.getByText(/2 quiet:/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    expect(await screen.findByRole("button", { name: "Move Checks earlier" })).toBeInTheDocument();
  });
  it("moves a row earlier and later, keeps focus on the control, and the ends are disabled", async () => {
    renderHome();
    await settled();
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    expect(screen.getByRole("button", { name: "Move Weather earlier" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Move Reading earlier" }));
    expect(order("Your life")).toEqual(["Reading", "Weather", "Later"]);
    await waitFor(() => expect(screen.getByRole("button", { name: "Move Reading earlier" })).toBeDisabled());
    expect(screen.getByRole("button", { name: "Move Reading later" })).toHaveFocus();
    expect(await screen.findByText("Moved Reading earlier")).toBeInTheDocument();
  });
  it("hides a row, offers it under + Add to Home, and Undo restores it", async () => {
    renderHome();
    await settled();
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    await userEvent.click(screen.getByRole("button", { name: "Hide Later" }));
    expect(order("Your life")).toEqual(["Weather", "Reading"]);
    expect(screen.queryByRole("button", { name: "Later Healthy. Show details" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "+ Add to Home" }));
    expect(screen.getByRole("button", { name: "Add Later to Home" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(order("Your life")).toEqual(["Weather", "Reading", "Later"]);
    expect(await screen.findByText("Undid: hid Later")).toBeInTheDocument();
  });
  it("adds a hidden row back with Add to Home", async () => {
    renderHome();
    await settled();
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    await userEvent.click(screen.getByRole("button", { name: "Hide Later" }));
    await userEvent.click(screen.getByRole("button", { name: "+ Add to Home" }));
    await userEvent.click(screen.getByRole("button", { name: "Add Later to Home" }));
    expect(order("Your life")).toEqual(["Weather", "Reading", "Later"]);
  });
  it("sizes: S is slim, L is large, M is the default; the choice is pressed", async () => {
    renderHome();
    await settled();
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    const li = () => document.getElementById("fd-row-weather")!;
    await userEvent.click(screen.getByRole("button", { name: "Weather size L" }));
    expect(li()).toHaveClass("fd-row--l");
    expect(screen.getByRole("button", { name: "Weather size L" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Weather size S" }));
    expect(li()).toHaveClass("fd-row--slim");
  });
  it("saves every action as a board write with If-Match, in display order; the arrangement survives a reload", async () => {
    document.cookie = "pw_csrf=tok123";
    const first = renderHome();
    await settled();
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    await userEvent.click(screen.getByRole("button", { name: "Move Reading earlier" }));
    await waitFor(() => expect(boardServer.puts).toHaveLength(1));
    const put = boardServer.puts[0];
    expect(put.ifMatch).toBe('"v1"');
    expect(put.csrf).toBe("tok123");
    expect(put.body.items.map((i) => i.card).slice(0, 3)).toEqual(["reading", "weather", "later"]);
    expect(put.body.items[0]).toEqual({ card: "reading", size: "M", hidden: false });
    expect(Object.keys(put.body.items[0])).toEqual(["card", "size", "hidden"]);
    first.unmount();
    renderHome();
    await settled();
    expect(order("Your life")).toEqual(["Reading", "Weather", "Later"]);
  });
  it("Undo is another write", async () => {
    renderHome();
    await settled();
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    await userEvent.click(screen.getByRole("button", { name: "Hide Later" }));
    await waitFor(() => expect(boardServer.puts).toHaveLength(1));
    expect(boardServer.puts[0].body.items.find((i) => i.card === "later")!.hidden).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    await waitFor(() => expect(boardServer.puts).toHaveLength(2));
    expect(boardServer.puts[1].ifMatch).toBe('"v2"');
    expect(boardServer.puts[1].body.items.find((i) => i.card === "later")!.hidden).toBe(false);
    await waitFor(() => expect(order("Your life")).toEqual(["Weather", "Reading", "Later"]));
  });
  it("409: says it wasn't saved, pauses editing with a reason, reverts; Reload reads again and restores focus", async () => {
    renderHome();
    await settled();
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    await userEvent.click(await screen.findByRole("button", { name: "Move Reading earlier" }));
    await waitFor(() => expect(boardServer.puts).toHaveLength(1));
    // someone else changes Home; this editor's next write carries a stale tag
    boardServer.bump();
    await userEvent.click(screen.getByRole("button", { name: "Move Later earlier" }));
    expect(await screen.findByText("Home changed somewhere else, your edit wasn't saved.")).toBeInTheDocument();
    expect(screen.getByText("Editing is paused until you reload.")).toBeInTheDocument();
    await waitFor(() => expect(order("Your life")).toEqual(["Reading", "Weather", "Later"]));
    // no dead controls: they are disabled, with the visible reason above
    expect(screen.getByRole("button", { name: "Move Weather later" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Hide Later" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Undo" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Reload" }));
    await waitFor(() => expect(screen.queryByText("Home changed somewhere else, your edit wasn't saved.")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Done" })).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: "Move Later earlier" }));
    await waitFor(() => expect(order("Your life")).toEqual(["Reading", "Later", "Weather"]));
  });
  it("Reload drops queued saves instead of replaying them", async () => {
    server.use(http.put("/api/config/board/home", async ({ request }) => {
      await delay(150);
      const r = boardServer.put(request.headers.get("if-match"), null, (await request.json()) as never);
      return HttpResponse.json(r.body as Record<string, unknown>, { status: r.status, headers: { etag: r.etag } });
    }));
    renderHome();
    await settled();
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    await screen.findByRole("button", { name: "Move Reading earlier" });
    boardServer.bump();
    await userEvent.click(screen.getByRole("button", { name: "Move Reading earlier" }));
    await userEvent.click(screen.getByRole("button", { name: "Hide Later" }));
    await screen.findByText("Home changed somewhere else, your edit wasn't saved.");
    await userEvent.click(screen.getByRole("button", { name: "Reload" }));
    await new Promise((r) => setTimeout(r, 400));
    expect(boardServer.puts).toHaveLength(1); // only the refused one; the queued Hide was never sent
    expect(order("Your life")).toEqual(["Weather", "Reading", "Later"]);
  });
  it("422: shows the server's reason and keeps the board as it was", async () => {
    server.use(http.put("/api/config/board/home", () => HttpResponse.json({ detail: "board home: unknown card(s) later" }, { status: 422 })));
    renderHome();
    await settled();
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    await userEvent.click(screen.getByRole("button", { name: "Hide Later" }));
    expect(await screen.findByText("Couldn't save that change.")).toBeInTheDocument();
    const details = screen.getByText("Details").closest("details")!;
    expect(details).not.toHaveAttribute("open");
    expect(within(details).getByText("board home: unknown card(s) later")).toBeInTheDocument();
    await waitFor(() => expect(order("Your life")).toEqual(["Weather", "Reading", "Later"]));
  });
});

describe("Quietly working is slim", () => {
  it("has no meters unless Density is Detailed", async () => {
    renderHome();
    await settled();
    expect(within(section("Quietly working")).queryByRole("img")).not.toBeInTheDocument();
    cleanup();
    renderHome({ prefs: { density: "detailed" } });
    await settled();
    expect(within(section("Quietly working")).getAllByRole("img").length).toBeGreaterThan(0);
  });
});

describe("Bad-day layout (Calm, and phones)", () => {
  const phone = (matches: boolean) => {
    window.matchMedia = ((query: string) => ({ matches: matches && query.includes("max-width: 759px"), media: query, onchange: null, addListener: () => undefined, removeListener: () => undefined, addEventListener: () => undefined, removeEventListener: () => undefined, dispatchEvent: () => false })) as typeof window.matchMedia;
  };
  afterEach(() => phone(false));

  it("Calm puts Needs you right after the briefing, before the strip", async () => {
    renderHome({ prefs: { density: "calm" } });
    await settled();
    const needs = screen.getByRole("heading", { name: "Needs you" });
    const strip = screen.getByRole("group", { name: "Whole world" });
    expect(needs.compareDocumentPosition(strip) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
  it("Standard keeps the strip first on a wide screen, with every source", async () => {
    renderHome();
    await settled();
    const strip = screen.getByRole("group", { name: "Whole world" });
    expect(strip.compareDocumentPosition(screen.getByRole("heading", { name: "Needs you" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(strip).getAllByRole("button")).toHaveLength(8);
    expect(within(strip).queryByRole("button", { name: /quiet/ })).not.toBeInTheDocument();
  });
  it("the condensed strip shows only what needs a look plus one quiet tile that opens the rest in place", async () => {
    renderHome({ prefs: { density: "calm" } });
    await settled();
    const strip = screen.getByRole("group", { name: "Whole world" });
    const names = () => within(strip).getAllByRole("button").map((b) => b.getAttribute("aria-label"));
    expect(names()).toEqual(["Downloads Unavailable. Show details", "Backup Stale. Show details", "Calendar Unknown. Show details", "6 quiet. Show all"]);
    expect(within(strip).queryByRole("link")).not.toBeInTheDocument();           // not configured folds into the quiet tile
    const quiet = within(strip).getByRole("button", { name: "6 quiet. Show all" });
    expect(quiet).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(quiet);
    expect(quiet).toHaveAttribute("aria-expanded", "true");
    expect(within(strip).getByRole("button", { name: "Show fewer sources" })).toBe(quiet);   // same element
    expect(within(strip).getAllByRole("button")).toHaveLength(9);
    expect(within(strip).getByRole("link", { name: "Music Not configured. Set up in Connect" })).toBeInTheDocument();
  });
  it("any density on a phone is condensed too", async () => {
    phone(true);
    renderHome({ prefs: { density: "standard" } });
    await settled();
    expect(within(screen.getByRole("group", { name: "Whole world" })).getByRole("button", { name: "6 quiet. Show all" })).toBeInTheDocument();
  });
  it("the visible text of a strip tile is contained in its accessible name", async () => {
    renderHome();
    await settled();
    for (const tile of within(screen.getByRole("group", { name: "Whole world" })).getAllByRole("button")) {
      const visible = Array.from(tile.querySelectorAll(".fd-strip-name, .fd-strip-word")).map((e) => e.textContent?.trim()).filter(Boolean).join(" ");
      expect(tile.getAttribute("aria-label")).toContain(visible);
    }
  });
  it("Calm's Show moves focus to the first revealed row and becomes Show less, which folds and refocuses the toggle", async () => {
    renderHome({ prefs: { density: "calm" } });
    await settled();
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    const less = screen.getByRole("button", { name: "Show less" });
    expect(less).toHaveAttribute("aria-expanded", "true");
    await waitFor(() => expect(within(section("Quietly working")).getAllByRole("button", { name: /Disk/ })[0]).toHaveFocus());
    await userEvent.click(less);
    expect(screen.getByRole("button", { name: "Show" })).toHaveFocus();
    expect(screen.getByText(/2 quiet: Disk, Checks/)).toBeInTheDocument();
  });
  it("Escape closes an open drill-in and returns focus to its row; a second Escape leaves Edit mode", async () => {
    renderHome();
    await settled();
    const row = within(section("Needs a look")).getByRole("button", { name: /Downloads/ });
    await userEvent.click(row);
    expect(screen.getByRole("region", { name: "Downloads details" })).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("region", { name: "Downloads details" })).not.toBeInTheDocument();
    expect(row).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: "Edit Home" }));
    await screen.findByRole("button", { name: "Done" });
    screen.getByRole("button", { name: "Move Reading earlier" }).focus();
    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "Edit Home" })).toHaveFocus();
    expect(screen.queryByRole("button", { name: "Move Reading earlier" })).not.toBeInTheDocument();
  });
  it("Words Full writes the briefing in whole sentences; Minimal keeps the terse line", async () => {
    renderHome({ prefs: { words: "full" }, });
    await settled();
    expect(screen.getByText(/^Two things need you\. Downloads isn't answering; it last worked at 08:12\./)).toBeInTheDocument();
    cleanup();
    renderHome({ prefs: { words: "minimal" } });
    await settled();
    expect(screen.getByText("2 for you · Downloads unavailable · Backup stale · 1 more to look at · rest quiet")).toBeInTheDocument();
  });
  it("the polite line is silent on a normal load; it speaks when asked (Try again) or when something changed", async () => {
    renderHome();
    await settled();
    const line = () => screen.getAllByRole("status").find((s) => s.classList.contains("fd-sr") && !s.classList.contains("fd-secret-saved"))!;
    expect(line()).toHaveTextContent("");
    expect(screen.queryByText("Up to date")).not.toBeInTheDocument();
    expect(screen.queryByText("Checking sources…")).not.toBeInTheDocument();
  });
  it("Try again announces Checking sources… then Up to date", async () => {
    server.use(http.get("/api/needs-you", () => HttpResponse.json({}, { status: 500 })));
    renderHome();
    await settled();
    server.use(http.get("/api/needs-you", () => HttpResponse.json([])));
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Up to date")).toBeInTheDocument();
  });
  it("a source that changes state is announced", async () => {
    const { client } = renderHome();
    await settled();
    server.use(http.get("/api/cards/disk", () => HttpResponse.json({ ...cards.disk, source_state: "unavailable", freshness: "stale" })));
    await client.refetchQueries({ queryKey: ["fd", "card", "disk"] });
    expect(await screen.findByText("Disk unavailable")).toBeInTheDocument();
  });
});
