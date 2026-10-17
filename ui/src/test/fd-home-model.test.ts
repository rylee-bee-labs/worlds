import { describe, expect, it } from "vitest";
import { briefing, briefingFull, buildSections } from "../fd/home-model";
import { cards, homeBoard, needsYou } from "../fd/fixtures";

describe("home model", () => {
  const s = buildSections(homeBoard, cards, needsYou);
  const ids = (rows: { item: { card: string } }[]) => rows.map((r) => r.item.card);

  it("puts each fixture in one section (C6)", () => {
    expect(s.needs_you.map((n) => n.id)).toEqual(["ny-1", "ny-2"]);
    expect(ids(s.needs_look)).toEqual(["downloads", "backup", "malformed"]);
    expect(ids(s.your_life)).toEqual(["weather", "reading", "later"]);
    expect(ids(s.quietly_working)).toEqual(["disk", "checks"]);
    expect(ids(s.not_configured)).toEqual(["music"]);
  });
  it("treats a healthy card with stale freshness as Needs a look", () => {
    const stale = { ...cards, disk: { ...cards.disk, freshness: "stale" as const } };
    expect(ids(buildSections(homeBoard, stale, []).needs_look)).toContain("disk");
  });
  it("skips hidden items and items with no card", () => {
    const b = { ...homeBoard, items: homeBoard.items.map((i) => (i.card === "disk" ? { ...i, hidden: true } : i)) };
    expect(ids(buildSections(b, cards, []).quietly_working)).toEqual(["checks"]);
    expect(buildSections(b, {}, []).your_life).toEqual([]);
  });
  it("orders Needs a look worst first", () => {
    const b = { ...homeBoard, items: [homeBoard.items.find((i) => i.card === "backup")!, homeBoard.items.find((i) => i.card === "downloads")!] };
    expect(ids(buildSections(b, cards, []).needs_look)).toEqual(["downloads", "backup"]);
  });
  it("writes a terse briefing", () => {
    expect(briefing(s)).toBe("2 for you · Downloads unavailable · Backup stale · 1 more to look at · rest quiet");
    expect(briefing({ needs_you: [], needs_look: [], your_life: [], quietly_working: [], not_configured: [] })).toBe("all quiet");
  });
  it("uses the badge words in the terse briefing", () => {
    const all = (state: "degraded" | "needs_attention" | "unknown") =>
      briefing(buildSections({ ...homeBoard, items: homeBoard.items.filter((i) => i.card === "disk") }, { disk: { ...cards.disk, source_state: state } }, []));
    expect(all("degraded")).toBe("Disk degraded · rest quiet");
    expect(all("needs_attention")).toBe("Disk needs attention · rest quiet");
    expect(all("unknown")).toBe("Disk unknown · rest quiet");
  });
  it("Words Full: whole sentences with the same facts", () => {
    const text = briefingFull(s, "UTC");
    expect(text).toBe("Two things need you. Downloads isn't answering; it last worked at 08:12. Backup is out of date; it last updated at 08:12. 1 more needs a look. Everything else is quiet.");
    expect(briefingFull({ needs_you: [], needs_look: [], your_life: [], quietly_working: [], not_configured: [] })).toBe("All quiet.");
  });
});
