import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Shell } from "../fd/Shell";
import { hashFor, parseHash } from "../fd/route";

afterEach(cleanup);

describe("routing", () => {
  it("parses the four landmarks and falls back to home", () => {
    expect(parseHash("#connect")).toBe("connect");
    expect(parseHash("#memory/later")).toBe("memory");
    expect(parseHash("#/Settings")).toBe("settings");
    for (const old of ["#overview", "#bridge", "#chat", "", "#nope"]) expect(parseHash(old)).toBe("home");
    expect(hashFor("memory")).toBe("#memory");
  });
});

describe("Shell", () => {
  const boards = [{ id: "reading", title: "Reading" }, { id: "garden", title: "Garden" }];
  const setup = (current: "home" | "memory" = "home", onNavigate = vi.fn()) => {
    render(<Shell current={current} onNavigate={onNavigate} boards={boards}><h1>Body</h1></Shell>);
    return onNavigate;
  };

  it("keeps a fixed DOM order: skip link, header, nav, main", () => {
    setup();
    const order = Array.from(document.body.querySelectorAll("a[href='#main'], header, nav, main")).map((e) => e.tagName.toLowerCase());
    expect(order).toEqual(["a", "header", "nav", "main"]);
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute("href", "#main");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main");
    expect(screen.getAllByRole("navigation")).toHaveLength(1);
  });
  it("lists exactly Home, Connect, Memory, Settings, then personal boards", () => {
    setup("memory");
    const nav = within(screen.getByRole("navigation", { name: "Main" }));
    const links = nav.getAllByRole("link").map((a) => a.textContent);
    expect(links).toEqual(["Home", "Connect", "Memory", "Settings", "Reading", "Garden"]);
    expect(nav.getByRole("link", { name: "Memory" })).toHaveAttribute("aria-current", "page");
    expect(nav.getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
    expect(nav.getByRole("link", { name: "Connect" })).toHaveAttribute("href", "#connect");
  });
  it("navigates on click without a page load", async () => {
    const onNavigate = setup();
    await userEvent.click(screen.getByRole("link", { name: "Connect" }));
    expect(onNavigate).toHaveBeenCalledWith("connect");
  });
  it("renders its children inside main", () => {
    setup();
    expect(within(screen.getByRole("main")).getByRole("heading", { name: "Body" })).toBeInTheDocument();
  });
});
