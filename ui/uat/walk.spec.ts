import { test, type Page, type Request } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

/**
 * The UAT walk (see playwright.uat.config.ts). One test per screen size.
 * It never fails on what it finds: it records, and the report says what's
 * wrong in plain words. It fails only if it can't reach Worlds at all, or the credential is rejected.
 */

type Finding = { level: "problem" | "note"; where: string; what: string };

const OUT = process.env.PW_UAT_OUT ?? "uat-out";
const SETTLE_MS = 2500;

function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "screen";
}

test("walk Worlds as the owner, read-only", async ({ page, request }, info) => {
  const size = info.project.name;
  const dir = join(OUT, size);
  mkdirSync(dir, { recursive: true });
  const findings: Finding[] = [];
  const blocked: string[] = [];
  let where = "start";

  // ── Guards and listeners ──────────────────────────────────────────
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    if (req.method() === "GET" || req.method() === "HEAD") return route.continue();
    const path = new URL(req.url()).pathname;
    blocked.push(`${req.method()} ${path} (on ${where})`);
    return route.abort("blockedbyclient");
  });
  page.on("console", (m) => {
    if (m.type() === "error" && !/net::ERR_BLOCKED_BY_CLIENT/.test(m.text()))
      findings.push({ level: "problem", where, what: `Console error: ${m.text().slice(0, 300)}` });
  });
  page.on("pageerror", (e) => findings.push({ level: "problem", where, what: `Page crashed: ${e.message.slice(0, 300)}` }));
  page.on("requestfailed", (r: Request) => {
    const f = r.failure()?.errorText ?? "";
    if (/BLOCKED_BY_CLIENT|ERR_ABORTED/.test(f)) return;
    findings.push({ level: "problem", where, what: `Request failed: ${r.method()} ${new URL(r.url()).pathname} (${f})` });
  });
  page.on("response", (r) => {
    const s = r.status();
    const path = new URL(r.url()).pathname;
    if (s >= 400 && path.startsWith("/api/"))
      findings.push({ level: s >= 500 ? "problem" : "note", where, what: `${r.request().method()} ${path} answered ${s}` });
  });

  const settle = async () => {
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(SETTLE_MS);
  };
  const shot = async (name: string) => {
    await page.screenshot({ path: join(dir, `${slug(name)}.png`), fullPage: true });
  };

  // ── Is this page the live build? ──────────────────────────────────
  const health = await (await request.get("/healthz")).json().catch(() => ({}));
  const live = typeof health.commit === "string" ? health.commit : null;
  // A rejected credential is not "can't reach": /healthz is public, so
  // only an authenticated call can tell the two apart.
  const probe = await request.get("/api/status").catch(() => null);
  const credentialRejected = probe !== null && (probe.status() === 401 || probe.status() === 403);
  await page.goto("/");
  await settle();
  where = "Home";
  const baked = await page.evaluate(() => {
    const s = Array.from(document.scripts).map((x) => x.src).find((x) => /\/assets\/index-/.test(x));
    return s ?? null;
  });
  if (!live) findings.push({ level: "note", where: "Version", what: "/healthz reports no commit, so staleness can't be checked." });
  await shot("home");

  // ── Every area in the world navigation ────────────────────────────
  const nav = page.getByRole("navigation", { name: "World navigation" });
  const labels = (await nav.getByRole("button").allTextContents()).map((t) => t.trim()).filter(Boolean);
  if (labels.length === 0) findings.push({ level: "problem", where: "Navigation", what: "No navigation buttons found." });
  const visited: { area: string; heading: string | null }[] = [];
  for (const label of labels) {
    where = label;
    try {
      await page.goto("/");
      await settle();
      await nav.getByRole("button", { name: label, exact: true }).first().click({ timeout: 10_000 });
      await settle();
      const heading = await page.locator("main h1, main h2").first().textContent({ timeout: 3000 }).catch(() => null);
      if (!heading) findings.push({ level: "note", where: label, what: "No heading found on this screen." });
      visited.push({ area: label, heading: heading?.trim() ?? null });
      await shot(`area-${label}`);
    } catch (e) {
      findings.push({ level: "problem", where: label, what: `Couldn't open this area: ${(e as Error).message.split("\n")[0]}` });
    }
  }

  // ── Every screen by its address (#memory, #library …) ────────────
  // Direct loads, like a bookmark. Each must stay on its address, show a
  // heading, never scroll sideways, and keep tap targets at least 44 px.
  const ADDRESSES = ["bridge", "memory", "chat", "settings", "interests", "projects", "computers",
    "crew", "people", "helpers", "rough-night", "library", "lore", "at-home"];
  const screens: { address: string; heading: string | null; small_targets: number; overflow_px: number }[] = [];
  for (const address of ADDRESSES) {
    where = `#${address}`;
    try {
      await page.goto(`/#${address}`);
      await settle();
      const hash = await page.evaluate(() => window.location.hash);
      if (hash !== `#${address}`)
        findings.push({ level: "problem", where, what: `Opening #${address} ended on "${hash || "(no address)"}".` });
      const heading = await page.locator("main h1").first().textContent({ timeout: 3000 }).catch(() => null);
      if (!heading) findings.push({ level: "note", where, what: "No main heading (h1) on this screen." });
      const layout = await page.evaluate(() => {
        const overflow = document.documentElement.scrollWidth - window.innerWidth;
        const small = Array.from(document.querySelectorAll("main button, main a[href], main [role=button]"))
          .filter((el) => {
            const r = (el as HTMLElement).getBoundingClientRect();
            const st = getComputedStyle(el as HTMLElement);
            if (r.width === 0 || r.height === 0 || st.visibility === "hidden") return false;
            // Inline text links inside a sentence are exempt (WCAG 2.5.8).
            if (el.tagName === "A" && st.display === "inline") return false;
            return r.height < 44 || r.width < 24;
          })
          .map((el) => ((el as HTMLElement).innerText || el.getAttribute("aria-label") || "").trim().slice(0, 40));
        return { overflow, small };
      });
      if (layout.overflow > 1)
        findings.push({ level: "problem", where, what: `The page scrolls sideways by ${layout.overflow}px.` });
      if (layout.small.length)
        findings.push({ level: "note", where, what: `${layout.small.length} tap target(s) under 44px: ${layout.small.slice(0, 5).map((t) => `"${t}"`).join(", ")}` });
      screens.push({ address, heading: heading?.trim() ?? null, small_targets: layout.small.length, overflow_px: layout.overflow });
      await shot(`address-${address}`);
    } catch (e) {
      findings.push({ level: "problem", where, what: `Couldn't open this address: ${(e as Error).message.split("\n")[0]}` });
    }
  }

  // ── Back and forward move between screens ─────────────────────────
  where = "Back/forward";
  try {
    await page.goto("/#memory");
    await settle();
    await page.goto("/#library");
    await settle();
    await page.goBack();
    await settle();
    const back = await page.evaluate(() => window.location.hash);
    if (back !== "#memory") findings.push({ level: "problem", where, what: `Back from #library landed on "${back}", not #memory.` });
  } catch (e) {
    findings.push({ level: "problem", where, what: `Back/forward check failed: ${(e as Error).message.split("\n")[0]}` });
  }

  // ── Every room drawer: does it show what the room says? ──────────
  const roomsRes = await request.get("/api/rooms");
  const rows: Array<Record<string, unknown>> = roomsRes.ok() ? ((await roomsRes.json()).data ?? []) : [];
  if (!roomsRes.ok()) findings.push({ level: "problem", where: "Rooms", what: `/api/rooms answered ${roomsRes.status()}` });
  const roomSummary: string[] = [];
  // The UI names a room room.name (else its id); match drawers by that name.
  const byName = new Map<string, Record<string, unknown>>();
  for (const row of rows) {
    const room = row.room as { name?: string } | undefined;
    byName.set((room?.name?.trim() || String(row.id)), row);
  }
  const openNeeds = (row: Record<string, unknown>) => {
    if (!row.reachable || row.status === "incompatible") return 0;
    const seen = new Set((row.needs_seen as string[] | undefined) ?? []);
    return ((row.needs_you as Array<{ id: string }> | undefined) ?? []).filter((n) => !seen.has(n.id)).length;
  };
  const checked = new Set<string>();
  await page.goto("/");
  await settle();
  const openerNames = (await page.getByRole("button", { name: /^Look inside / }).evaluateAll((els) =>
    els.map((e) => (e.getAttribute("aria-label") ?? "").replace(/^Look inside /, "")),
  )).filter((n, i, a) => n && a.indexOf(n) === i);
  for (const name of openerNames) {
    where = `Room: ${name}`;
    const row = byName.get(name);
    try {
      await page.goto("/");
      await settle();
      await page.getByRole("button", { name: `Look inside ${name}`, exact: true }).first().click({ timeout: 10_000 });
      const dialog = page.getByRole("dialog").first();
      await dialog.waitFor({ timeout: 5000 });
      await page.waitForTimeout(800);
      const text = await dialog.innerText();
      const m = text.match(/needs you · (\d+)/i);
      const shown = m ? Number(m[1]) : 0;
      if (!row) {
        findings.push({ level: "note", where, what: "A drawer opened for a room /api/rooms doesn't list." });
      } else {
        checked.add(String(row.id));
        const expected = openNeeds(row);
        roomSummary.push(`${name}: ${expected} open in the room, ${shown} in the drawer`);
        if (shown !== expected)
          findings.push({ level: "problem", where, what: `The room has ${expected} open needs; the drawer shows ${shown}.` });
      }
      const showAll = dialog.getByRole("button", { name: /^Show all \d+/ });
      if (await showAll.count()) await showAll.first().click();
      await shot(`room-${name}`);
      await dialog.getByRole("button", { name: /^Close .* details$/ }).click();
    } catch (e) {
      findings.push({ level: "problem", where, what: `Couldn't open or read this drawer: ${(e as Error).message.split("\n")[0]}` });
    }
  }
  for (const row of rows) {
    if (!checked.has(String(row.id)) && openNeeds(row) > 0)
      findings.push({ level: "note", where: `Room: ${String(row.id)}`, what: `Has ${openNeeds(row)} open needs, but Home has no "Look inside" for it.` });
  }

  // ── Report ─────────────────────────────────────────────────────────
  const report = {
    size,
    url: new URL(page.url()).origin,
    live_commit: live,
    bundle: baked ? new URL(baked).pathname : null,
    areas: visited,
    screens,
    rooms: roomSummary,
    blocked_writes: blocked,
    findings,
    at: new Date().toISOString(),
  };
  writeFileSync(join(dir, "report.json"), JSON.stringify(report, null, 2));
  if (credentialRejected)
    throw new Error("Credential rejected: Worlds answered but did not accept the UAT token (HTTP " + probe!.status() + ").");
  if (!live && labels.length === 0) throw new Error("Couldn't reach Worlds at all.");
});
