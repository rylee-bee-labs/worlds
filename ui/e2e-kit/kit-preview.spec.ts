/**
 * Worlds kit preview — the exportable kit's accessibility floor.
 *
 * Runs against the static dist-kit/preview.html (see playwright.kit.config.ts)
 * at the two widths tool UIs actually ship at, in the two themes the first
 * migrations target (starfield, doorways). Like the app's own axe.spec.ts,
 * the FULL default rule set runs — no .disableRules() — and every interactive
 * target must clear 44px (§2.1) with a visible focus ring (§2.4).
 */
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { expectKeyboardFocusRing } from "../e2e/helpers";

const THEMES = ["starfield", "doorways"] as const;
const VIEWPORTS = [
  { name: "phone", width: 390, height: 844 },
  { name: "desk", width: 1440, height: 900 },
] as const;

/** Anything a pointer/keyboard can activate, per the accessibility contract. */
const INTERACTIVE = 'button, a[href], select, input, textarea, [role="tab"]';
const MIN = 43.5; // sub-pixel tolerance around the 44px floor

for (const theme of THEMES) {
  for (const vp of VIEWPORTS) {
    test(`preview ${theme} @ ${vp.width}px: axe, targets, focus`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/preview.html");
      await page.selectOption("#theme-picker", theme);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);

      // 1. axe — no serious/critical violations.
      const results = await new AxeBuilder({ page }).analyze();
      const bad = results.violations.filter(
        (v) => v.impact === "serious" || v.impact === "critical",
      );
      expect(
        bad.map((v) => `${v.id}: ${v.nodes.length} node(s)`),
        `axe violations on kit preview (${theme} @ ${vp.width}px)`,
      ).toEqual([]);

      // 1b. nothing scrolls sideways at this width.
      const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
      expect(scrollWidth, `horizontal overflow at ${vp.width}px`).toBeLessThanOrEqual(vp.width);

      // 2. every visible interactive target is at least 44×44.
      const targets = page.locator(INTERACTIVE);
      const count = await targets.count();
      expect(count).toBeGreaterThan(0);
      const tooSmall: string[] = [];
      for (let i = 0; i < count; i++) {
        const el = targets.nth(i);
        if (!(await el.isVisible())) continue;
        const box = await el.boundingBox();
        if (!box) continue;
        if (box.width < MIN || box.height < MIN) {
          const label = await el.evaluate((node) => {
            const tag = node.tagName.toLowerCase();
            const id = (node as HTMLElement).id ? `#${(node as HTMLElement).id}` : "";
            const cls = (node as HTMLElement).className
              ? `.${String((node as HTMLElement).className).trim().split(/\s+/)[0]}`
              : "";
            return `${tag}${id}${cls}`;
          });
          tooSmall.push(`${label} ${Math.round(box.width)}×${Math.round(box.height)}`);
        }
      }
      expect(tooSmall, `targets under 44px (${theme} @ ${vp.width}px)`).toEqual([]);

      // 3. keyboard focus composes the Worlds ring (2px solid, 2px offset,
      //    accent-coloured — the shape shared by every theme).
      await expectKeyboardFocusRing(
        page,
        page.getByRole("button", { name: "Primary" }),
        `kit ${theme} primary button`,
      );
    });
  }
}

test("drawer opens non-modally and stays accessible", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/preview.html");
  await page.selectOption("#theme-picker", "starfield");

  await page.getByRole("button", { name: "Open drawer" }).click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  const bad = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(bad.map((v) => `${v.id}: ${v.nodes.length} node(s)`), "axe violations with drawer open").toEqual([]);

  const close = page.getByRole("button", { name: "Close drawer" });
  const box = await close.boundingBox();
  expect(box && box.width >= MIN && box.height >= MIN).toBeTruthy();

  // Escape closes it, focus returns to the opener.
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  await expect(page.getByRole("button", { name: "Open drawer" })).toBeFocused();
});