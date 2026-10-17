import { describe, expect, it } from "vitest";
import { applyEdits, move, NO_EDITS, setSize, setVisible } from "../fd/edit-model";
import { homeBoard } from "../fd/fixtures";

const ids = (b: typeof homeBoard) => b.items.map((i) => i.card);

describe("edit model", () => {
  it("no edits leaves the board as served", () => {
    expect(applyEdits(homeBoard, NO_EDITS)).toEqual(homeBoard);
  });
  it("moves a card earlier or later among its section's cards, by swapping", () => {
    const siblings = ["weather", "reading", "later"];
    const e = move(homeBoard, NO_EDITS, "reading", -1, siblings);
    expect(ids(applyEdits(homeBoard, e)).slice(0, 3)).toEqual(["reading", "weather", "later"]);
    const e2 = move(homeBoard, e, "reading", 1, ["reading", "weather", "later"]);
    expect(ids(applyEdits(homeBoard, e2)).slice(0, 3)).toEqual(["weather", "reading", "later"]);
  });
  it("does nothing at the ends", () => {
    expect(move(homeBoard, NO_EDITS, "weather", -1, ["weather", "reading"])).toBe(NO_EDITS);
    expect(move(homeBoard, NO_EDITS, "reading", 1, ["weather", "reading"])).toBe(NO_EDITS);
  });
  it("hides and shows without touching the served board", () => {
    const hidden = applyEdits(homeBoard, setVisible(NO_EDITS, "disk", false));
    expect(hidden.items.find((i) => i.card === "disk")!.hidden).toBe(true);
    expect(homeBoard.items.find((i) => i.card === "disk")!.hidden).toBe(false);
    const back = applyEdits(homeBoard, setVisible(setVisible(NO_EDITS, "disk", false), "disk", true));
    expect(back.items.find((i) => i.card === "disk")!.hidden).toBe(false);
  });
  it("sets a size", () => {
    expect(applyEdits(homeBoard, setSize(NO_EDITS, "disk", "L")).items.find((i) => i.card === "disk")!.size).toBe("L");
  });
});
