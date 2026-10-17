import { expect, type Locator, type Page } from "@playwright/test";

/**
 * Navigate by the world-nav buttons only. Scoped to the navigation
 * landmark so same-named buttons elsewhere (Today's area links render
 * buttons too) can never trip Playwright's strict mode.
 */
export async function gotoArea(page: Page, name: string) {
  await page.goto("/");
  await page
    .getByRole("navigation", { name: "World navigation" })
    .getByRole("button", { name })
    .click();
}

/**
 * The live nav-bar button labels, top to bottom.
 *
 * ONE synchronous allTextContents read, not a nth(i) loop: the
 * personal sections can change count while /api/sections settles,
 * and a per-index locator would then hang waiting for a row that no
 * longer exists. Pair with expect.poll to assert the settled order
 * without racing the query.
 */
export async function navButtonLabels(page: Page): Promise<string[]> {
  const labels = await page
    .getByRole("navigation", { name: "World navigation" })
    .getByRole("button")
    .allTextContents();
  return labels.map((t) => t.trim());
}

/**
 * Shared e2e helpers for Track C specs (C7 focus ring / keyboard
 * paths). Kept honest to the a11y contract: rings are asserted only
 * after KEYBOARD arrival (Tab), because :focus-visible is a
 * keyboard-truth rule — programmatic focus() would test the wrong
 * thing.
 */

/**
 * The composed ring SHAPE for every production theme: 2px solid with
 * 2px offset — the same composition tests/test_design_tokens.py guards
 * at the token layer (docs/accessibility/ACCESSIBILITY_CONTRACT.md §2.4).
 *
 * The ring COLOR is deliberately NOT a literal here. world.css composes
 * the ring from var(--pw-accent-primary), and that token differs per
 * theme (station #72b1b1, moss #7AAA76, ocean #5AA8B8, plain #72B1B1,
 * starfield #D4A057). The old station hardcoding went permanently-red
 * the moment the first-run default stopped being station (L2, then D2)
 * — a permanent-red test teaches people to ignore red.
 * expectKeyboardFocusRing therefore resolves the ACTIVE theme's token
 * at runtime, from the page itself.
 */
export const RING = {
  width: "2px",
  style: "solid",
  offset: "2px",
};

/**
 * Resolve the ring colour the ACTIVE theme composes right now: a
 * throwaway element carries the same `outline-color:
 * var(--pw-accent-primary)` declaration world.css uses, and its
 * computed style yields the browser-normalised rgb() — no hand-picked
 * literals, no hex→rgb math to drift. (Under the OS
 * prefers-contrast:more override world.css forces #FFFFFF; the e2e
 * projects run with contrast no-preference, so the token is the
 * contract under test.)
 */
export async function activeRingColor(locator: Locator): Promise<string> {
  return locator.evaluate((el) => {
    const probe = document.createElement("span");
    probe.style.outlineColor = "var(--pw-accent-primary)";
    const parent = el.parentElement ?? document.body;
    parent.append(probe);
    const color = getComputedStyle(probe).outlineColor;
    probe.remove();
    return color;
  });
}

export async function focusRingOf(locator: Locator) {
  return locator.evaluate((el) => {
    const cs = getComputedStyle(el);
    return {
      width: cs.outlineWidth,
      style: cs.outlineStyle,
      color: cs.outlineColor,
      offset: cs.outlineOffset,
    };
  });
}

/**
 * Tab forward until the active element IS `locator`; then assert the
 * composed ring.
 *
 * expect.poll, not a single snapshot: `transition-colors` legitimately
 * includes outline-color, so a WorldButton's ring ANIMATES from the
 * text colour to the accent over the (colour-only, ≤150ms) transition.
 * Sampling once raced the animation; polling states the real contract
 * — the composed ring arrives — without weakening anything. Under
 * prefers-reduced-motion the arrival is instant (see reduced-motion
 * spec).
 */
export async function expectKeyboardFocusRing(
  page: Page,
  locator: Locator,
  label?: string,
  maxTabs = 160,
) {
  let reached = false;
  for (let i = 0; i < maxTabs; i++) {
    await page.keyboard.press("Tab");
    reached = await locator
      .evaluate((el) => el === document.activeElement)
      .catch(() => false);
    if (reached) break;
  }
  if (!reached) {
    throw new Error(
      `${label ?? "focus ring target"}: never reached by Tab within the budget`,
    );
  }
  await expect
    .poll(async () => focusRingOf(locator), {
      message: `${label ?? "focus ring"}: composed ring must arrive (a11y §2.4)`,
      timeout: 5_000,
    })
    .toEqual({ ...RING, color: await activeRingColor(locator) });
}
