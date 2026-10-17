import { expect, test } from "@playwright/test";
import { axe, noHorizontalOverflow, open } from "./helpers";

const SHOTS = process.env.PW_FD_SHOTS;
const shot = async (page: import("@playwright/test").Page, name: string, info: import("@playwright/test").TestInfo) => {
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${info.project.name}-${name}.png`, fullPage: true });
};

test.describe("axe and overflow", () => {
  for (const [name, hash, scenario] of [
    ["home-mixed", "#home", "mixed"], ["home-healthy", "#home", "healthy"], ["home-board-error", "#home", "board-error"],
    ["connect", "#connect", "mixed"], ["memory", "#memory", "mixed"], ["settings", "#settings", "mixed"],
  ] as const) {
    test(name, async ({ page }, info) => {
      await open(page, hash, scenario === "board-error" ? "board-error" : scenario);
      if (scenario === "board-error") await page.getByText("Home could not load.").waitFor();
      expect(await axe(page)).toEqual([]);
      await noHorizontalOverflow(page);
      await shot(page, name, info);
    });
  }

  test("drill-in open", async ({ page }, info) => {
    await open(page);
    await page.getByRole("button", { name: /^Downloads/ }).first().click();
    await expect(page.getByRole("region", { name: "Downloads details" })).toBeVisible();
    expect(await axe(page)).toEqual([]);
    await noHorizontalOverflow(page);
    await shot(page, "home-drill-in", info);
  });

  test("Words minimal and full, density detailed, Station on", async ({ page }, info) => {
    for (const [group, option] of [["Words", "Minimal"], ["Words", "Full"], ["Density", "Detailed"], ["Experience pack", "Station"]]) {
      await open(page, "#settings");
      await page.getByRole("group", { name: group }).getByLabel(option).check();
      await page.getByRole("link", { name: "Home" }).first().click();
      await page.getByRole("heading", { name: "Needs a look" }).waitFor();
      await expect(page.locator(".fd-home")).toHaveAttribute("data-ready", "true");
      expect(await axe(page), `${group} ${option}`).toEqual([]);
      await noHorizontalOverflow(page);
      await shot(page, `home-${option.toLowerCase()}`, info);
    }
  });
});

test("reflows at 320px and 200% zoom equivalent", async ({ page }) => {
  for (const width of [320, 195]) {
    await page.setViewportSize({ width, height: 700 });
    await open(page);
    await noHorizontalOverflow(page);
  }
});

test("keyboard path: skip link, nav, strip, drill-in; focus ring on every control", async ({ page }) => {
  await open(page);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  // every control gets a visible outline when focused by keyboard
  const controls = page.locator("main :is(a[href], button:not(:disabled), summary, input, [tabindex='0'])");
  const n = await controls.count();
  expect(n).toBeGreaterThan(8);
  for (let i = 0; i < Math.min(n, 12); i++) {
    await controls.nth(i).focus();
    // a row's name button draws its ring on the ::after that stretches over the whole row
    const outline = await controls.nth(i).evaluate((e) => {
      const ring = (s: CSSStyleDeclaration) => `${s.outlineStyle} ${s.outlineWidth}`;
      const own = ring(getComputedStyle(e));
      return /^none|\b0px$/.test(own) ? ring(getComputedStyle(e, "::after")) : own;
    });
    expect(outline, `control ${i}`).not.toMatch(/^none|\b0px$/);
  }
  const btn = page.getByRole("button", { name: /^Downloads/ }).first();
  await btn.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: "Downloads details" })).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: "Downloads details" })).toHaveCount(0);
});

test("targets are at least 44px (strip at least 56px)", async ({ page }) => {
  await open(page);
  const strip = page.getByRole("group", { name: "Whole world" }).locator("button, a");
  for (let i = 0; i < (await strip.count()); i++) expect((await strip.nth(i).boundingBox())!.height).toBeGreaterThanOrEqual(56);
  // the whole row is the click target: the name button stretches over it
  const rows = page.locator("main li.fd-row");
  for (let i = 0; i < (await rows.count()); i++) expect((await rows.nth(i).boundingBox())!.height).toBeGreaterThanOrEqual(44);
});

test("reduced motion: nothing animates", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page);
  const animated = await page.evaluate(() => Array.from(document.querySelectorAll("*")).filter((e) => { const s = getComputedStyle(e); return s.animationName !== "none" && s.animationDuration !== "0s"; }).length);
  expect(animated).toBe(0);
});

test("Station invariance: same nav, headings, controls and row order on all four screens", async ({ page }) => {
  const snap = () => page.evaluate(() => ({
    nav: Array.from(document.querySelectorAll("nav a")).map((a) => a.textContent),
    headings: Array.from(document.querySelectorAll("main h1, main h2, main h3")).map((h) => h.textContent),
    controls: Array.from(document.querySelectorAll("main :is(a, button, input, summary)")).map((e) => (e.getAttribute("aria-label") ?? e.textContent ?? "").trim()),
    rows: Array.from(document.querySelectorAll("main li")).map((li) => li.querySelector("button")?.textContent?.slice(0, 40) ?? ""),
    layoutHeight: document.querySelector("main")!.getBoundingClientRect().height,
  }));
  for (const hash of ["#home", "#connect", "#memory", "#settings"]) {
    await open(page, "#settings");
    await page.getByRole("group", { name: "Experience pack" }).getByLabel("None").check();
    await page.goto(`/${hash}`);
    await page.getByRole("main").waitFor();
    if (hash === "#home") {
      await page.getByRole("heading", { name: "Needs a look" }).waitFor();
      await expect(page.locator(".fd-home")).toHaveAttribute("data-ready", "true");
    }
    const off = await snap();
    await page.goto("/#settings");
    await page.getByRole("group", { name: "Experience pack" }).getByLabel("Station").check();
    await page.goto(`/${hash}`);
    await page.getByRole("main").waitFor();
    if (hash === "#home") {
      await page.getByRole("heading", { name: "Needs a look" }).waitFor();
      await expect(page.locator(".fd-home")).toHaveAttribute("data-ready", "true");
    }
    const on = await snap();
    expect(on, hash).toEqual(off);
  }
});

test("Edit Home: keyboard-operable, axe clean, 44px controls, no overflow", async ({ page }, info) => {
  await open(page);
  await page.getByRole("button", { name: "Edit Home" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Done" })).toBeVisible();
  const reading = page.getByRole("button", { name: "Move Reading earlier" });
  await reading.focus();
  await page.keyboard.press("Enter");
  const titles = () => page.locator("section:has(> h2:text('Your life')) li.fd-row .fd-row-title").allTextContents();
  await expect.poll(titles).toEqual(["Reading", "Weather", "Later"]);
  // focus stays on a control of the moved row (Earlier is now disabled, so it lands on Later)
  await expect(page.getByRole("button", { name: "Move Reading later" })).toBeFocused();
  for (const b of await page.locator(".fd-row-edit button").all()) expect((await b.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await page.getByRole("button", { name: "+ Add to Home" }).click();
  expect(await axe(page)).toEqual([]);
  await noHorizontalOverflow(page);
  await shot(page, "home-edit", info);
  await page.getByRole("button", { name: "Undo" }).click();
  await expect.poll(titles).toEqual(["Weather", "Reading", "Later"]);
});

test("Text size Larger: no overflow, axe clean", async ({ page }, info) => {
  await open(page, "#settings");
  await page.getByRole("group", { name: "Text size" }).getByLabel("Larger").check();
  await page.getByRole("link", { name: "Home" }).first().click();
  await page.getByRole("heading", { name: "Needs a look" }).waitFor();
  await expect(page.locator(".fd-home")).toHaveAttribute("data-ready", "true");
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).fontSize)).toBe("20.8px");
  expect(await axe(page)).toEqual([]);
  await noHorizontalOverflow(page);
  await shot(page, "home-text-larger", info);
});

test("phone: strip tiles are all the same height", async ({ page }, info) => {
  test.skip(info.project.name !== "phone-390", "phone layout only");
  await open(page);
  const heights = await page.getByRole("group", { name: "Whole world" }).locator("button, a").evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().height)));
  expect(new Set(heights).size, JSON.stringify(heights)).toBe(1);
});

test("phone: the bottom bar clears the home indicator and never covers content", async ({ page }, info) => {
  test.skip(info.project.name !== "phone-390", "phone layout only");
  await open(page);
  // Headless Chromium reports env(safe-area-inset-bottom) as 0, so pin the variable the CSS reads.
  await page.addStyleTag({ content: ":root { --fd-safe-bottom: 34px !important; }" });
  const m = await page.evaluate(() => {
    const nav = document.querySelector(".fd-nav")!.getBoundingClientRect();
    const navPad = parseFloat(getComputedStyle(document.querySelector(".fd-nav")!).paddingBottom);
    const mainPad = parseFloat(getComputedStyle(document.querySelector(".fd-main")!).paddingBottom);
    return { navPad, mainPad, navH: nav.height, bottom: Math.round(nav.bottom), vh: window.innerHeight };
  });
  expect(m.navPad).toBe(6 + 34);
  expect(m.bottom).toBe(m.vh);
  expect(m.mainPad).toBeGreaterThanOrEqual(m.navH);
  // scrolled to the end, the last row sits above the bar
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  const gap = await page.evaluate(() => {
    const rows = document.querySelectorAll("li.fd-row");
    return document.querySelector(".fd-nav")!.getBoundingClientRect().top - rows[rows.length - 1].getBoundingClientRect().bottom;
  });
  expect(gap).toBeGreaterThanOrEqual(0);
});

for (const size of ["Large", "Larger"]) {
  test(`Text size ${size}: nothing in a strip tile spills past its border`, async ({ page }, info) => {
    test.skip(info.project.name !== "phone-390", "phone layout only");
    await open(page, "#settings");
    await page.getByRole("group", { name: "Text size" }).getByLabel(size, { exact: true }).check();
    await page.getByRole("link", { name: "Home" }).first().click();
    await page.getByRole("heading", { name: "Needs a look" }).waitFor();
    await expect(page.locator(".fd-home")).toHaveAttribute("data-ready", "true");
    const spills = await page.getByRole("group", { name: "Whole world" }).locator("button, a").evaluateAll((tiles) =>
      tiles.flatMap((tile) => {
        const box = tile.getBoundingClientRect();
        return Array.from(tile.querySelectorAll("*"))
          .filter((c) => { const r = c.getBoundingClientRect(); return r.width > 0 && (r.right > box.right + 0.5 || r.left < box.left - 0.5); })
          .map((c) => `${tile.getAttribute("aria-label")} > ${c.className}`);
      }),
    );
    expect(spills).toEqual([]);
    await noHorizontalOverflow(page);
    await shot(page, `home-text-${size.toLowerCase()}`, info);
  });
}
