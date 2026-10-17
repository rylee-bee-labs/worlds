import { expect, test } from "@playwright/test";
import { createCompanionServer } from "../src/fd/companion-server";
import { axe, noHorizontalOverflow, open } from "./helpers";

const SHOTS = process.env.PW_FD_SHOTS;

test("the Companion button is a quiet control in the header, and the landmarks do not change", async ({ page }) => {
  await open(page);
  const nav = await page.getByRole("navigation", { name: "Main" }).getByRole("link").allTextContents();
  expect(nav).toEqual(["Home", "Connect", "Memory", "Settings"]);
  const btn = page.getByRole("button", { name: /^Companion/ });
  await expect(btn).toBeVisible();
  expect((await btn.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  expect(await page.getByRole("button", { name: /^Companion/ }).count()).toBe(1);
});

test("the open panel: axe clean, no overflow, a modal that traps focus, Escape closes and returns focus", async ({ page }, info) => {
  await open(page);
  const btn = page.getByRole("button", { name: /^Companion/ });
  await btn.click();
  const dialog = page.getByRole("dialog", { name: "Companion" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Companion is up. Not answering: ph.")).toBeVisible();
  expect(await axe(page)).toEqual([]);
  await noHorizontalOverflow(page);
  // desktop: a side panel; phone: a full-height sheet
  const box = (await dialog.boundingBox())!;
  const vp = page.viewportSize()!;
  expect(Math.round(box.height)).toBe(vp.height);
  if (info.project.name.includes("phone")) expect(Math.round(box.width)).toBe(vp.width);
  else expect(box.width).toBeLessThanOrEqual(480 + 1);
  // focus stays inside however many times Tab is pressed
  for (let i = 0; i < 4; i++) {
    await page.keyboard.press("Tab");
    expect(await page.evaluate(() => !!document.activeElement?.closest("dialog") || document.activeElement === document.body)).toBe(true);
  }
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${info.project.name}-companion-open.png` });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0).catch(() => undefined);
  await expect(page.getByRole("dialog", { name: "Companion" })).toBeHidden();
  await expect(btn).toBeFocused();
});

test("a conversation: thinking, the reply, what was withheld, and axe with replies showing", async ({ page }, info) => {
  await open(page);
  await page.getByRole("button", { name: /^Companion/ }).click();
  const dialog = page.getByRole("dialog", { name: "Companion" });
  await dialog.getByLabel("Message to Companion").fill("hello there");
  await dialog.getByRole("button", { name: "Send" }).click();
  await expect(dialog.getByText(/Here is a short answer to: hello there/)).toBeVisible();
  await expect(dialog.getByText("Some things were withheld: recall: withheld (tier)")).toBeVisible();
  await expect(dialog.getByText("Here with you")).toBeVisible();
  await dialog.getByText("What Companion sees").click();
  await expect(dialog.getByText("Reviewed 1 · Working 0 · Recall 0 · Live 1")).toBeVisible();
  expect(await axe(page)).toEqual([]);
  await noHorizontalOverflow(page);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${info.project.name}-companion-thread.png` });
});

test("Companion down: an honest unknown, the message kept, axe clean", async ({ page }, info) => {
  const server = createCompanionServer();
  server.setMode("down");
  await open(page, "#home", "mixed", server);
  await page.getByRole("button", { name: /^Companion/ }).click();
  const dialog = page.getByRole("dialog", { name: "Companion" });
  await dialog.getByLabel("Message to Companion").fill("are you there");
  await dialog.getByRole("button", { name: "Send" }).click();
  await expect(dialog.getByRole("button", { name: "Try again" })).toBeVisible();
  await expect(dialog.getByText("are you there")).toBeVisible();
  await expect(dialog.getByText(/short answer/)).toHaveCount(0);
  expect(await axe(page)).toEqual([]);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${info.project.name}-companion-down.png` });
});

test("Settings reports the same governed Companion and opens that panel from the keyboard", async ({ page }) => {
  await open(page, "#settings");
  const section = page.locator("main section", { has: page.getByRole("heading", { name: "Companion", exact: true }) });
  await expect(section.getByText("Companion is up. Not answering: ph.")).toBeVisible();
  await expect(page.getByText("Not installed")).toHaveCount(0);
  const openPanel = section.getByRole("button", { name: "Open the Companion panel" });
  await openPanel.focus();
  await expect(openPanel).toBeFocused();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Companion" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Companion is up. Not answering: ph.")).toBeVisible();
  expect(await axe(page)).toEqual([]);
  await noHorizontalOverflow(page);
});

test("Station on: the panel and the landmarks are identical", async ({ page }) => {
  await open(page, "#settings");
  await page.getByRole("group", { name: "Experience pack" }).getByLabel("Station").check();
  const snap = async () => ({
    nav: await page.getByRole("navigation", { name: "Main" }).getByRole("link").allTextContents(),
    companion: await page.getByRole("button", { name: /^Companion/ }).count(),
  });
  const on = await snap();
  await page.getByRole("group", { name: "Experience pack" }).getByLabel("None").check();
  expect(await snap()).toEqual(on);
});

test("Earlier conversations: axe clean, no overflow, keyboard path, read-only thread view", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: /^Companion/ }).click();
  const dialog = page.getByRole("dialog", { name: "Companion" });
  const summary = dialog.getByText("Earlier conversations");
  // Open the disclosure
  await summary.click();
  await expect(dialog.getByRole("button", { name: "Conversation 1" })).toBeVisible();
  // Keyboard: Tab through the list
  await page.keyboard.press("Tab");
  await expect(dialog.getByRole("button", { name: "Conversation 1" })).toBeFocused();
  await page.keyboard.press("Enter");
  // Read-only view
  await expect(dialog.getByRole("button", { name: /Back to the current conversation/ })).toBeVisible();
  await expect(dialog.getByText("What's the weather?")).toBeVisible();
  await expect(dialog.getByText("I don't have real-time data.")).toBeVisible();
  // No composer
  await expect(dialog.getByLabel("Message to Companion")).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: "Send" })).toHaveCount(0);
  expect(await axe(page)).toEqual([]);
  await noHorizontalOverflow(page);
  // Back: focus returns to the summary (the control the person used to get there).
  await dialog.getByRole("button", { name: /Back to the current conversation/ }).click();
  await expect(dialog.getByLabel("Message to Companion")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Send" })).toBeVisible();
  await expect(summary).toBeFocused();
});
