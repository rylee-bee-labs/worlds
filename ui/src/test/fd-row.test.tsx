import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Meter } from "../fd/Meter";
import { Row } from "../fd/Row";
import { cards, homeBoard } from "../fd/fixtures";

const item = (id: string) => homeBoard.items.find((i) => i.card === id)!;
const row = (id: string, props: Partial<Parameters<typeof Row>[0]> = {}) =>
  render(<Row item={item(id)} card={cards[id]} words="short" density="standard" timeZone="UTC" expanded={false} onToggle={() => undefined} {...props} />);

afterEach(cleanup);

describe("Meter", () => {
  it("exposes the text equivalent as the accessible name", () => {
    render(<Meter meter={cards.disk.meter} frozen={false} />);
    expect(screen.getByRole("img", { name: "61 percent used" })).toBeInTheDocument();
  });
  it("renders nothing for a null meter", () => {
    const { container } = render(<Meter meter={null} frozen={false} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("draws nothing when the API sends a meter with no data to draw", () => {
    const bare = { type: "progress", text_equivalent: "Uptime: 1h 2m" } as const;
    const { container } = render(<Meter meter={bare} frozen={false} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("an explicit 0 is real and draws; a missing number does not", () => {
    const { container, rerender } = render(<Meter meter={{ type: "progress", value: 0, max: 1, text_equivalent: "0 of 1" }} frozen={false} />);
    expect(container.querySelector(".fd-fill")).not.toBeNull();
    rerender(<Meter meter={{ type: "progress", max: 1, text_equivalent: "x" }} frozen={false} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("drops day items with an impossible time", () => {
    render(<Meter meter={{ type: "day", items: ["25:00 Never", "10:75 Nope", "09:00 Walk"], text_equivalent: "day" }} frozen={false} />);
    expect(screen.getByText("Walk")).toBeInTheDocument();
    expect(screen.queryByText("Never")).not.toBeInTheDocument();
    expect(screen.queryByText("Nope")).not.toBeInTheDocument();
  });
  it("a real 0 bar draws as 0, not a minimum", () => {
    const { container } = render(<Meter meter={{ type: "bars", items: [0, 4], text_equivalent: "bars" }} frozen={false} />);
    const bars = container.querySelectorAll<HTMLElement>(".fd-bars i");
    expect(bars[0].style.height).toBe("0%");
    expect(bars[1].style.height).toBe("100%");
  });
  it("dots are on only for true or a number above 0", () => {
    const { container } = render(<Meter meter={{ type: "dots", items: [true, 2, false, 0, "false", "0"], text_equivalent: "dots" }} frozen={false} />);
    expect(Array.from(container.querySelectorAll(".fd-dots i")).map((e) => e.classList.contains("on"))).toEqual([true, true, false, false, false, false]);
  });
  it("marks a frozen meter", () => {
    render(<Meter meter={cards.downloads.meter} frozen />);
    expect(screen.getByRole("img")).toHaveAttribute("data-frozen", "true");
  });
  it("shows only waiting marks plus +N more", () => {
    render(<Meter meter={{ type: "marks", items: ["a", "b", "c", "d", "e", "f", "g", "h"], text_equivalent: "8 waiting" }} frozen={false} />);
    expect(screen.getByText("+2 more")).toBeInTheDocument();
  });
  it("puts day labels under the track as text", () => {
    render(<Meter meter={cards.weather.meter} frozen={false} />);
    expect(screen.getByText("Walk")).toBeInTheDocument();
    expect(screen.getByText("Call")).toBeInTheDocument();
  });
});

describe("Row anatomy", () => {
  it("healthy: name, meaning, value with unit, state shape and word", () => {
    row("disk");
    expect(screen.getByText("Disk")).toBeInTheDocument();
    expect(screen.getByText("Disk space")).toBeInTheDocument();
    expect(screen.getByText("61")).toBeInTheDocument();
    expect(screen.getByText("%")).toBeInTheDocument();
    expect(screen.getByText("●")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
  });
  it("unavailable keeps last-good, frozen, with 'as of' time", () => {
    row("downloads");
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByText("■")).toBeInTheDocument();
    expect(screen.getByText("Last good 08:12")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAttribute("data-frozen", "true");
  });
  it("a value of text \"unknown\" with no raw shows a dash, never 0 or the word, and no meter", () => {
    row("malformed");
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
    expect(screen.queryByText("unknown")).not.toBeInTheDocument();   // the card is Unknown: its state word says so once
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
  it("an empty list is healthy and says so in plain words, not as a big value", () => {
    row("later");
    expect(screen.getByText("Nothing kept")).toBeInTheDocument();
    expect(screen.getByText("Nothing kept")).toHaveClass("fd-row-meaning--plain");
    expect(screen.queryByText("none")).not.toBeInTheDocument();
    expect(document.querySelector(".fd-row-value")).toBeEmptyDOMElement();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
  });
  it("Words: Minimal drops meaning; Full shows the long meaning and freshness", () => {
    const { unmount } = row("disk", { words: "minimal" });
    expect(screen.queryByText("Disk space")).not.toBeInTheDocument();
    expect(screen.getByText("61")).toBeInTheDocument();
    unmount();
    row("disk", { words: "full" });
    expect(screen.getByText("How full the main disk is.")).toBeInTheDocument();
    expect(screen.getByText("Current")).toBeInTheDocument();
  });
  it("a problem row always says when it was last good; one that never answered says so", () => {
    row("malformed");
    expect(screen.getByText("Never answered")).toBeInTheDocument();
    expect(screen.queryByText(/Last good/)).not.toBeInTheDocument();
  });
  it("a card that is already Unknown does not also say a hidden 'unknown' for its dash", () => {
    row("malformed");
    expect(screen.queryByText("unknown")).not.toBeInTheDocument();
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });
  it("a healthy card with a missing value keeps the hidden unknown", () => {
    const card = { ...cards.disk, values: { used: { text: "unknown" } } };
    render(<Row item={item("disk")} card={card} words="short" density="standard" timeZone="UTC" expanded={false} onToggle={() => undefined} />);
    expect(screen.getByText("unknown")).toHaveClass("fd-sr");
  });
  it("does not repeat the name as its meaning", () => {
    row("malformed");
    expect(screen.getAllByText("Calendar")).toHaveLength(1);
    expect(screen.getByText("Today's events")).toBeInTheDocument();
  });
  it("the drill-in keeps units next to the value", () => {
    row("backup", { expanded: true });
    expect(within(screen.getByRole("region", { name: "Backup details" })).getByText("26 h ago")).toBeInTheDocument();
  });
  it("the drill-in shows field labels, never keys", () => {
    row("downloads", { expanded: true });
    const region = screen.getByRole("region", { name: "Downloads details" });
    expect(within(region).getByText("Active")).toBeInTheDocument();
    expect(within(region).queryByText("active")).not.toBeInTheDocument();
  });
  it("the whole row is one disclosure button", async () => {
    const onToggle = vi.fn();
    row("disk", { onToggle });
    const btn = screen.getByRole("button", { name: /Disk/ });
    expect(btn).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(btn);
    expect(onToggle).toHaveBeenCalled();
  });
  it("drill-in order: meaning, state, detail, freshness, evidence disclosure, Connect", () => {
    row("downloads", { expanded: true });
    const region = screen.getByRole("region", { name: "Downloads details" });
    const text = region.textContent ?? "";
    const at = (s: string) => text.indexOf(s);
    expect(at("The queue Sonarr")).toBeGreaterThanOrEqual(0);
    expect(at("The queue Sonarr")).toBeLessThan(at("Unavailable"));
    expect(at("Unavailable")).toBeLessThan(at("Last good 08:12"));
    const ev = within(region).getByText("Technical evidence");
    expect(ev.closest("summary")).not.toBeNull();
    expect(at("Last good 08:12")).toBeLessThan(text.indexOf("Technical evidence"));
    expect(within(region).getByRole("link", { name: "Open in Connect" })).toHaveAttribute("href", "#connect");
    expect(region.querySelector("details")).toHaveTextContent("Request: sonarr.queue");
    expect(region.querySelector("details")).toHaveTextContent("Error: Server error");
    expect(region.querySelector("details")).toHaveTextContent("Status code: 500");
    expect(region.querySelector("details")).not.toHaveTextContent(/http_5xx|status_code|error_class/);
  });
  it("Detailed density opens the evidence", () => {
    row("downloads", { expanded: true, density: "detailed" });
    expect(screen.getByRole("region").querySelector("details")).toHaveAttribute("open");
  });
});
