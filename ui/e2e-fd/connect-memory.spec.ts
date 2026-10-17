import { expect, test, type Page, type Route } from "@playwright/test";
import { axe, mockApi, noHorizontalOverflow } from "./helpers";

/**
 * Connect and Memory against a mocked API. helpers.mockApi serves Home and the board; it does not
 * serve the Connect config/actions or the Memory routes, so this file adds them here (never by
 * editing src/). Every tab is checked in both an empty state and a server-error state for:
 * axe, no horizontal overflow, a visible focus ring, and >= 44px targets.
 *
 * Registered after mockApi(), so these handlers run first for the paths they name.
 */

type Mode = "empty" | "error" | "populated";

const CONNECT_TABS = ["Requests", "Providers", "Cards", "Recipes", "Actions", "Advanced"] as const;
const MEMORY_TABS = ["Kept", "Later", "Records", "History", "Find"] as const;

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

// ---- obviously-fake fixtures: example.test only, no secret value, no personal data

const PROVIDER = { id: "example", name: "Example", kind: "http", base_url: "https://example.test", auth: { type: "none" }, tls_verify: true };
const REQUEST = { id: "example.queue", provider: "example", method: "GET", path: "/v1/queue", effect: "auto" };
const CARD = { id: "example-card", title: "Example queue", icon: "list", group: "life", view: "stat", request: "example.queue", meaning: { short: "The example queue", full: "The example queue as a card." } };
const ACTIONS = [
  { id: "example.read", name: "Read the example queue", access: "read", scope: "example", exposed: false },
  { id: "example.restart", name: "Restart the example service", access: "write", scope: "example", exposed: true },
];
const RECEIPTS = [{ id: "rcpt-1", action: "example.restart", dispatch_state: "succeeded", outcome: "SUCCEEDED", started_at: "2026-10-01T09:30:00Z", finished_at: "2026-10-01T09:30:00Z" }];

const KEPT = [{ id: "kept-1", table: "kept", title: "Fix the shed door", body: "Hinges rusted, needs a new pin.", tags: ["house"], provenance: "owner", source_ref: null, created_at: 1727700000, updated_at: 1727700000 }];
const LATER = [{ id: "later-1", table: "later", title: "Call the dentist", body: "", due_at: null, status: "open", provenance: "owner", source_ref: null, created_at: 1727700000, updated_at: 1727700000 }];
const RECORDS = [{ id: "rec-1", table: "records", title: "Annual checkup notes", body: "", kind: "health", sensitivity: "normal", provenance: "owner", source_ref: null, created_at: 1727700000, updated_at: 1727700000 }];
const HISTORY = [{ id: 1, at: 1727700000, actor: "owner", event: "created", table: "kept", row_id: "kept-1", detail: null }];
const FIND = [{ table: "kept", id: "kept-1", title: "Fix the shed door", snippet: "…the «shed» door…", sensitivity: "normal" }];

async function mockConnect(page: Page, mode: Mode) {
  const populated: Record<string, unknown> = {
    provider: { items: [{ id: PROVIDER.id, etag: '"p1"', object: PROVIDER }], errors: [] },
    request: { items: [{ id: REQUEST.id, etag: '"r1"', object: REQUEST }], errors: [] },
    card: { items: [{ id: CARD.id, etag: '"c1"', object: CARD }], errors: [] },
  };
  for (const kind of ["provider", "request", "card"]) {
    // The item path (open one row) is a different route from the list path.
    await page.route(`**/api/config/${kind}/*`, (route) => {
      if (mode === "error") return json(route, { detail: `couldn't load that ${kind}` }, 500);
      if (mode !== "populated") return json(route, { detail: "not found" }, 404);
      const object = kind === "provider" ? PROVIDER : kind === "request" ? REQUEST : CARD;
      return route.fulfill({ status: 200, contentType: "application/json", headers: { etag: '"x1"' }, body: JSON.stringify(object) });
    });
    await page.route(`**/api/config/${kind}`, (route) => {
      if (mode === "error") return json(route, { detail: `couldn't load ${kind}s` }, 500);
      return json(route, mode === "populated" ? populated[kind] : { items: [], errors: [] });
    });
  }
  await page.route("**/api/actions", (route) => (mode === "error" ? json(route, { detail: "down" }, 500) : json(route, mode === "populated" ? ACTIONS : [])));
  await page.route("**/api/receipts**", (route) => (mode === "error" ? json(route, { detail: "down" }, 500) : json(route, mode === "populated" ? RECEIPTS : [])));
}

async function mockMemory(page: Page, mode: Mode) {
  const populated: Record<string, unknown[]> = { kept: KEPT, later: LATER, records: RECORDS };
  for (const table of ["kept", "later", "records"]) {
    await page.route(`**/api/memory/${table}`, (route) => (mode === "error" ? json(route, { detail: "" }, 500) : json(route, mode === "populated" ? populated[table] : [])));
  }
  await page.route("**/api/memory/history**", (route) => (mode === "error" ? json(route, { detail: "" }, 500) : json(route, mode === "populated" ? HISTORY : [])));
  await page.route("**/api/memory/find**", (route) => (mode === "error" ? json(route, { detail: "" }, 500) : json(route, mode === "populated" ? FIND : [])));
}

async function openScreen(page: Page, hash: "#connect" | "#memory", connectMode: Mode, memoryMode: Mode) {
  await mockApi(page);
  await mockConnect(page, connectMode);
  await mockMemory(page, memoryMode);
  await page.goto(`/${hash}`);
  await expect(page.getByRole("main")).toBeVisible();
}

/** Every focusable control in main shows a focus ring, drawn on ::after where the row name uses it. */
async function assertFocusRings(page: Page) {
  // The ring is drawn on :focus-visible, which a programmatic .focus() only matches while the last
  // input was the keyboard (the tab click above leaves the pointer modality). Mirror front-door.spec.ts:
  // one Tab establishes keyboard modality; every .focus() after it keeps matching.
  await page.keyboard.press("Tab");
  const controls = page.locator("main :is(a[href], button:not(:disabled), summary, input, select, [tabindex='0'])");
  const n = await controls.count();
  expect(n).toBeGreaterThan(0);
  const missing: string[] = [];
  for (let i = 0; i < n; i++) {
    const c = controls.nth(i);
    if (!(await c.isVisible())) continue;
    await c.focus();
    const outline = await c.evaluate((e) => {
      const ring = (s: CSSStyleDeclaration) => `${s.outlineStyle} ${s.outlineWidth}`;
      const own = ring(getComputedStyle(e));
      return /^none|\b0px$/.test(own) ? ring(getComputedStyle(e, "::after")) : own;
    });
    if (/^none|\b0px$/.test(outline)) missing.push((await c.evaluate((e) => e.outerHTML)).slice(0, 120));
  }
  expect(missing).toEqual([]);
}

/** Every interactive control in main is at least the 44px target minimum. */
async function assertTargetSizes(page: Page) {
  const controls = page.locator("main :is(button:not(:disabled), a[href], input:not([type='hidden']), select, summary)");
  const n = await controls.count();
  const small: string[] = [];
  for (let i = 0; i < n; i++) {
    const c = controls.nth(i);
    if (!(await c.isVisible())) continue;
    const box = await c.boundingBox();
    if (box && box.height < 43.5) small.push(`${(await c.evaluate((e) => e.outerHTML)).slice(0, 120)} height=${box.height}`);
  }
  expect(small).toEqual([]);
}

const CONNECT_WORDS: Record<(typeof CONNECT_TABS)[number], { empty: string[]; error: string[] }> = {
  Requests: { empty: ["No saved requests yet."], error: ["Couldn't load requests."] },
  Providers: { empty: ["No providers yet. A provider is a service Worlds can read."], error: ["Couldn't load providers."] },
  Cards: { empty: ["No cards yet. A card shapes a request into something you can read."], error: ["Couldn't load cards."] },
  Recipes: { empty: ["No recipes installed yet. A recipe sets up one service in a single step."], error: ["No recipes installed yet. A recipe sets up one service in a single step."] },
  Actions: { empty: ["Nothing connected yet.", "No activity yet. Nothing has run."], error: ["Couldn't load actions.", "Couldn't load recent activity."] },
  Advanced: {
    empty: ["None. Every config file loaded cleanly.", "There is no field on this screen that accepts a secret value."],
    error: ["None. Every config file loaded cleanly.", "There is no field on this screen that accepts a secret value."],
  },
};

const MEMORY_WORDS: Record<Exclude<(typeof MEMORY_TABS)[number], "Find">, { empty: string[]; error: string[] }> = {
  Kept: { empty: ["Nothing kept yet."], error: ["Couldn't load."] },
  Later: { empty: ["Nothing set aside for later."], error: ["Couldn't load."] },
  Records: { empty: ["No records yet."], error: ["Couldn't load."] },
  History: { empty: ["No history yet."], error: ["Couldn't load."] },
};

test.describe("Connect", () => {
  for (const mode of ["empty", "error"] as const) {
    test(`Connect ${mode} states: axe clean, no overflow, 44px targets, visible focus`, async ({ page }) => {
      await openScreen(page, "#connect", mode, "empty");
      for (const tab of CONNECT_TABS) {
        await page.getByRole("tab", { name: tab }).click();
        for (const word of CONNECT_WORDS[tab][mode]) {
          await expect(page.getByText(word, { exact: false }).first(), `${tab}: ${word}`).toBeVisible();
        }
        expect(await axe(page), `${tab} axe`).toEqual([]);
        await noHorizontalOverflow(page);
        await assertTargetSizes(page);
        await assertFocusRings(page);
      }
    });
  }

  test("populated: the Requests list opens a request, and Actions stays read-only", async ({ page }) => {
    await openScreen(page, "#connect", "populated", "empty");
    // Requests is the first tab: the saved request reads method + id and opens its form.
    await page.getByRole("button", { name: "GET example.queue" }).click();
    await expect(page.getByRole("button", { name: "Try" })).toBeEnabled();
    await page.getByRole("button", { name: "Cancel" }).click();

    await page.getByRole("tab", { name: "Actions" }).click();
    await expect(page.getByText("Restart the example service")).toBeVisible();
    await expect(page.getByText("needs an approved action")).toBeVisible();
    // the receipt shows its raw dispatch state and the humanised outcome, never the raw OUTCOME word
    await expect(page.getByText("succeeded", { exact: true })).toBeVisible();
    await expect(page.getByText("Succeeded", { exact: true })).toBeVisible();
    // the write action has no Run control anywhere on the screen
    await expect(page.getByRole("button", { name: /Run/ })).toHaveCount(0);
    expect(await axe(page)).toEqual([]);
    await noHorizontalOverflow(page);
  });
});

test.describe("Memory", () => {
  for (const mode of ["empty", "error"] as const) {
    test(`Memory ${mode} states: axe clean, no overflow, 44px targets, visible focus`, async ({ page }) => {
      await openScreen(page, "#memory", "empty", mode);
      for (const tab of MEMORY_TABS) {
        await page.getByRole("tab", { name: tab }).click();
        if (tab === "Find") {
          if (mode === "error") {
            await page.getByLabel("Search your Memory").fill("shed");
            await expect(page.getByRole("alert")).toContainText("Couldn't search.");
          } else {
            await expect(page.getByText("Type something to search.")).toBeVisible();
          }
        } else {
          for (const word of MEMORY_WORDS[tab][mode]) {
            await expect(page.getByText(word, { exact: false }).first(), `${tab}: ${word}`).toBeVisible();
          }
        }
        expect(await axe(page), `${tab} axe`).toEqual([]);
        await noHorizontalOverflow(page);
        await assertTargetSizes(page);
        await assertFocusRings(page);
      }
    });
  }

  test("populated: each list renders its rows and Find returns matches", async ({ page }) => {
    await openScreen(page, "#memory", "empty", "populated");
    await expect(page.getByText("Fix the shed door")).toBeVisible();
    await page.getByRole("tab", { name: "Later" }).click();
    await expect(page.getByText("Call the dentist")).toBeVisible();
    await page.getByRole("tab", { name: "Records" }).click();
    await expect(page.getByText("Annual checkup notes")).toBeVisible();
    await page.getByRole("tab", { name: "History" }).click();
    await expect(page.getByText("created")).toBeVisible();
    await page.getByRole("tab", { name: "Find" }).click();
    await page.getByLabel("Search your Memory").fill("shed");
    await expect(page.getByText("Fix the shed door")).toBeVisible();
    await expect(page.getByText("…the «shed» door…")).toBeVisible();
    expect(await axe(page)).toEqual([]);
    await noHorizontalOverflow(page);
  });
});
