import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";
import { createBoardServer } from "../src/fd/board-server";
import { createCompanionServer, type CompanionServer } from "../src/fd/companion-server";
import { cards, needsYou } from "../src/fd/fixtures";
import type { CardEnvelope } from "../src/fd/types";

export type Scenario = "mixed" | "healthy" | "board-error";

export async function mockApi(page: Page, scenario: Scenario = "mixed", companion: CompanionServer = createCompanionServer()) {
  const healthy = (c: CardEnvelope): CardEnvelope => ({ ...c, source_state: c.source_state === "not_configured" ? c.source_state : "healthy", freshness: "current", evidence: { ...c.evidence, error_class: undefined, status_code: 200 }, ...(c.card_id === "malformed" ? { values: { count: { text: "3", raw: 3 } } } : {}) });
  const board = createBoardServer();
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (url.pathname.startsWith("/api/companion/")) {
      const raw = route.request().method() === "GET" || route.request().method() === "DELETE" ? null : route.request().postDataJSON();
      const r = companion.handle(route.request().method(), url.pathname, raw);
      return json(r.body, r.status);
    }
    if (scenario === "board-error" && url.pathname === "/api/boards/home") return json({ detail: "down" }, 500);
    if (url.pathname === "/api/boards/home") return json(board.display());
    if (url.pathname === "/api/config/board/home") {
      if (route.request().method() === "PUT") {
        const r = board.put(route.request().headers()["if-match"] ?? null, route.request().headers()["x-csrf-token"] ?? null, route.request().postDataJSON());
        return route.fulfill({ status: r.status, contentType: "application/json", headers: { etag: r.etag }, body: JSON.stringify(r.body) });
      }
      const g = board.getConfig();
      return route.fulfill({ status: 200, contentType: "application/json", headers: { etag: g.etag }, body: JSON.stringify(g.body) });
    }
    if (url.pathname === "/api/needs-you") return json(scenario === "healthy" ? [] : needsYou);
    const m = url.pathname.match(/^\/api\/cards\/(.+)$/);
    if (m && cards[m[1]]) return json(scenario === "healthy" ? healthy(cards[m[1]]) : cards[m[1]]);
    return json({ detail: "not found" }, 404);
  });
}

export async function open(page: Page, hash = "#home", scenario: Scenario = "mixed", companion?: CompanionServer) {
  await mockApi(page, scenario, companion);
  await page.goto(`/${hash}`);
  await expect(page.getByRole("main")).toBeVisible();
  if (hash === "#home" && scenario !== "board-error") {
    await page.getByRole("heading", { name: "Needs a look" }).waitFor();
    await expect(page.locator(".fd-home")).toHaveAttribute("data-ready", "true");
  }
}

export async function axe(page: Page) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  return r.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`);
}

export async function noHorizontalOverflow(page: Page) {
  const o = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
  expect(o.sw, `scrollWidth ${o.sw} > clientWidth ${o.cw}`).toBeLessThanOrEqual(o.cw);
}
