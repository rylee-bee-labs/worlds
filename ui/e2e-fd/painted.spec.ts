import { expect, test, type Page } from "@playwright/test";
import { axe, noHorizontalOverflow, open } from "./helpers";

const SHOTS = process.env.PW_FD_SHOTS;
const station = (page: Page) =>
  page.addInitScript(() => window.localStorage.setItem("worlds.prefs.v2", JSON.stringify({ pack: "station" })));

async function allPaintedLoaded(page: Page) {
  const imgs = page.locator("img.fd-painted");
  expect(await imgs.count()).toBeGreaterThan(0);
  await expect.poll(() => imgs.evaluateAll((els) => els.every((e) => (e as HTMLImageElement).complete && (e as HTMLImageElement).naturalWidth > 0))).toBe(true);
}

test("Station on: painted nav, companion and rows load, stay decorative, axe clean, no overflow", async ({ page }, info) => {
  await station(page);
  await open(page);
  await allPaintedLoaded(page);
  expect(await page.locator("img.fd-painted:not([alt=''])").count()).toBe(0);
  expect(await page.locator("img.fd-painted:not([aria-hidden='true'])").count()).toBe(0);
  const nav = page.getByRole("navigation", { name: "Main" });
  expect(await nav.getByRole("link").allTextContents()).toEqual(["Home", "Connect", "Memory", "Settings"]);
  for (const link of await nav.getByRole("link").all()) expect((await link.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await expect(page.getByRole("button", { name: /^Companion/ }).locator("img.fd-painted")).toHaveCount(1);
  expect(await axe(page)).toEqual([]);
  await noHorizontalOverflow(page);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${info.project.name}-station-home.png`, fullPage: true });
});

test("Station on, nothing waiting: the empty state shows its picture beside the words", async ({ page }, info) => {
  await station(page);
  await open(page, "#home", "healthy");
  await expect(page.getByText("Nothing for you right now.")).toBeVisible();
  await expect(page.locator(".fd-home-empty img.fd-painted").first()).toBeVisible();
  expect(await axe(page)).toEqual([]);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${info.project.name}-station-empty.png`, fullPage: true });
});

test("Station on: keyboard reaches every landmark with a visible focus ring, reduced motion leaves nothing moving", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await station(page);
  await open(page);
  const names: string[] = [];
  for (let i = 0; i < 12 && names.length < 4; i++) {
    await page.keyboard.press("Tab");
    const el = await page.evaluate(() => {
      const a = document.activeElement as HTMLElement | null;
      if (!a?.closest("nav")) return null;
      const s = getComputedStyle(a);
      return { name: a.textContent?.trim() ?? "", ring: s.outlineStyle !== "none" || s.boxShadow !== "none" };
    });
    if (el) { names.push(el.name); expect(el.ring, `focus ring on ${el.name}`).toBe(true); }
  }
  expect(names).toEqual(["Home", "Connect", "Memory", "Settings"]);
  const moving = await page.locator("img.fd-painted").evaluateAll((els) => els.filter((e) => getComputedStyle(e).animationName !== "none" || getComputedStyle(e).transitionDuration.split(",").some((d) => parseFloat(d) > 0)).length);
  expect(moving).toBe(0);
});

test("Station off: the plain front door has no painted pictures", async ({ page }) => {
  await open(page);
  await expect(page.locator("img.fd-painted")).toHaveCount(0);
});
