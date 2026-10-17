import { expect, test, type Page, type Route } from "@playwright/test";
import { axe, mockApi, noHorizontalOverflow, open } from "./helpers";

const SHOTS = process.env.PW_FD_SHOTS;
const NAME = process.env.PW_SHOT_NAME ?? "after";

/** A tired-day setup: Calm, Minimal, Larger text. */
async function badDay(page: Page, prefs = { density: "calm", words: "minimal", text: "larger" }) {
  await page.addInitScript((p) => window.localStorage.setItem("worlds.prefs.v2", JSON.stringify(p)), prefs);
  await mockApi(page);
  await page.goto("/#home");
  await page.getByRole("heading", { name: "Needs a look" }).waitFor();
  await expect(page.locator(".fd-home")).toHaveAttribute("data-ready", "true");
}

/**
 * The Memory screen reads /api/memory/*, which helpers.mockApi does not serve. Add just the one Kept
 * row this file needs (registered after mockApi, so its handler runs first).
 */
async function openMemoryWithRow(page: Page) {
  const json = (route: Route, body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  await mockApi(page);
  await page.route("**/api/memory/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/memory/kept") {
      return json(route, [{
        id: "kept-1", table: "kept", title: "Fix the shed door", body: "Hinges rusted, needs a new pin.",
        tags: ["house"], provenance: "owner", source_ref: null, created_at: 1727700000, updated_at: 1727700000,
      }]);
    }
    return json(route, []);
  });
  await page.goto("/#memory");
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("button", { name: "Delete" })).toBeVisible();
}

test("bad-day setup: Needs you first, a condensed strip, axe clean, no overflow", async ({ page }, info) => {
  await badDay(page);
  const needs = await page.getByRole("heading", { name: "Needs you" }).boundingBox();
  const strip = await page.getByRole("group", { name: "Whole world" }).boundingBox();
  expect(needs!.y).toBeLessThan(strip!.y);
  const tiles = await page.getByRole("group", { name: "Whole world" }).locator("button, a").evaluateAll((els) => els.map((e) => e.getAttribute("aria-label")));
  expect(tiles).toEqual(["Downloads Unavailable. Show details", "Backup Stale. Show details", "Calendar Unknown. Show details", "6 quiet. Show all"]);
  expect(await axe(page)).toEqual([]);
  await noHorizontalOverflow(page);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${NAME}-${info.project.name}.png`, fullPage: true });
});

test("a phone shows the condensed strip in any density", async ({ page }, info) => {
  test.skip(info.project.name !== "phone-390", "phone only");
  await badDay(page, { density: "standard", words: "short", text: "standard" });
  await expect(page.getByRole("button", { name: "6 quiet. Show all" })).toBeVisible();
  await page.getByRole("button", { name: "6 quiet. Show all" }).click();
  await expect(page.getByRole("button", { name: "Show fewer sources" })).toBeFocused();
});

for (const size of ["larger"] as const) {
  test(`Text size ${size}: no word is broken mid-word and nothing spills past a tile (every width)`, async ({ page }, info) => {
    await badDay(page, { density: "standard", words: "short", text: size });
    const quiet = page.getByRole("button", { name: /quiet\. Show all/ });
    if (await quiet.count()) await quiet.click(); // phones: open the folded sources too, so every tile is checked
    const probs = await page.getByRole("group", { name: "Whole world" }).locator("button, a").evaluateAll((tiles) =>
      tiles.flatMap((tile) => {
        const box = tile.getBoundingClientRect();
        const out: string[] = [];
        for (const c of Array.from(tile.querySelectorAll("*"))) {
          const s = getComputedStyle(c);
          if (s.overflowWrap === "anywhere" || s.overflowWrap === "break-word" || s.wordBreak === "break-all" || s.hyphens === "auto") out.push(`${tile.getAttribute("aria-label")}: ${c.className} may break mid-word`);
          const r = c.getBoundingClientRect();
          if (r.width > 0 && (r.right > box.right + 0.5 || r.left < box.left - 0.5)) out.push(`${tile.getAttribute("aria-label")}: ${c.className} spills`);
          // a word wider than its own box would have to break; the element must be able to hold its longest word
          if ((c as HTMLElement).scrollWidth > (c as HTMLElement).clientWidth + 1 && s.display !== "inline") out.push(`${tile.getAttribute("aria-label")}: ${c.className} clips`);
        }
        return out;
      }),
    );
    expect(probs, info.project.name).toEqual([]);
    await noHorizontalOverflow(page);
  });
}

test("each screen sets the page title", async ({ page }) => {
  await open(page, "#home");
  await expect(page).toHaveTitle("Home · Worlds");
  for (const [hash, title] of [["#connect", "Connect · Worlds"], ["#memory", "Memory · Worlds"], ["#settings", "Settings · Worlds"]]) {
    await page.goto(`/${hash}`);
    await expect(page).toHaveTitle(title);
  }
});

test("forced colours: tiles, rows and buttons keep their borders and the shapes stay visible", async ({ page }) => {
  await page.emulateMedia({ forcedColors: "active" });
  await open(page);
  const widths = await page.evaluate(() => {
    const w = (sel: string) => parseFloat(getComputedStyle(document.querySelector(sel)!).borderTopWidth);
    return { tile: w(".fd-strip-item"), row: w(".fd-row"), btn: w(".fd-btn") };
  });
  expect(widths.tile).toBeGreaterThan(0);
  expect(widths.row).toBeGreaterThan(0);
  expect(widths.btn).toBeGreaterThan(0);
  // state shapes are text, so they survive forced colours
  await expect(page.locator(".fd-row-shape").first()).toBeVisible();
});

test("the Memory delete dialog is modal: the page behind it cannot take focus", async ({ page }) => {
  await openMemoryWithRow(page);
  const remove = page.getByRole("button", { name: "Delete" }).first();
  await remove.click();
  const dialog = page.getByRole("dialog", { name: "Remove Fix the shed door?" });
  await expect(dialog).toBeVisible();
  // the safe choice has initial focus
  await expect(dialog.getByRole("button", { name: "Keep it" })).toBeFocused();
  for (let i = 0; i < 2; i++) {
    await page.keyboard.press("Tab");
    // inside the dialog, or on the browser itself (body): never on a control of the page behind it
    expect(await page.evaluate(() => !!document.activeElement?.closest("dialog") || document.activeElement === document.body)).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  // Escape takes the safe choice: focus returns to the control that opened the dialog
  await expect(remove).toBeFocused();
});

test("Station adds no space: the page is the same height with it on and off", async ({ page }) => {
  await open(page, "#home");
  const h = () => page.evaluate(() => document.querySelector("main")!.getBoundingClientRect().height);
  const off = await h();
  await page.evaluate(() => (document.documentElement.dataset.pack = "station"));
  expect(await h()).toBe(off);
});
