import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Shell } from "../fd/Shell";
import { PrefsProvider } from "../fd/prefs";
import { PaintedIcon, companionArt } from "../fd/PaintedIcon";

afterEach(cleanup);

const shell = (pack: "none" | "station") =>
  render(
    <PrefsProvider initial={{ pack }}>
      <Shell current="home" onNavigate={vi.fn()} boards={[]}>
        <h1>Body</h1>
      </Shell>
    </PrefsProvider>,
  );

describe("painted icons (Station pack)", () => {
  it("adds nothing when the pack is off", () => {
    const { container } = shell("none");
    expect(container.querySelectorAll("img")).toHaveLength(0);
  });

  it("puts a decorative picture beside each landmark word with Station on", () => {
    const { container } = shell("station");
    const nav = within(screen.getByRole("navigation", { name: "Main" }));
    expect(nav.getAllByRole("link").map((a) => a.textContent)).toEqual(["Home", "Connect", "Memory", "Settings"]);
    expect(nav.getByRole("link", { name: "Home" })).toBeInTheDocument();
    const imgs = Array.from(container.querySelectorAll("nav img"));
    expect(imgs).toHaveLength(4);
    for (const img of imgs) {
      expect(img).toHaveAttribute("alt", "");
      expect(img).toHaveAttribute("aria-hidden", "true");
    }
    expect(imgs[0].getAttribute("src")).toMatch(/assets\/painted\/action-home-64\.webp$/);
  });

  it("asks for the 2x file above 32 px and reserves its size", () => {
    const { container } = render(
      <PrefsProvider initial={{ pack: "station" }}>
        <PaintedIcon name="object-lantern" size={48} />
      </PrefsProvider>,
    );
    const img = container.querySelector("img")!;
    expect(img.getAttribute("src")).toMatch(/object-lantern-128\.webp$/);
    expect(img).toHaveAttribute("width", "48");
    expect(img).toHaveAttribute("height", "48");
  });

  it("maps companion presence to a crew pose, never to a status", () => {
    expect(companionArt("rest", "neutral")).toBe("crew-renai-hello");
    expect(companionArt("engaged", "neutral")).toBe("crew-renai-wink");
    for (const s of ["rest", "attentive", "thinking", "engaged", "giving_space"]) expect(companionArt(s, "concerned")).toMatch(/^crew-/);
  });
});
