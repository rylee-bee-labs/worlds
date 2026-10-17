import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { CompanionButton } from "../fd/companion/CompanionButton";
import { CompanionPanel } from "../fd/companion/CompanionPanel";
import { CompanionProvider } from "../fd/companion/CompanionProvider";
import { DEFAULT_PRESENTATION, parsePresentation, poseFor } from "../fd/companion/presentation";
import { companionServer, handlers } from "../fd/msw";

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => { cleanup(); server.resetHandlers(); companionServer.reset(); document.cookie = "pw_csrf=; max-age=0"; });
afterAll(() => server.close());

const mount = () => render(<CompanionProvider><CompanionButton /><CompanionPanel /></CompanionProvider>);
const openPanel = async () => {
  await userEvent.click(screen.getByRole("button", { name: /^Companion/ }));
  return screen.getByRole("dialog", { name: "Companion" });
};
const say = async (dlg: HTMLElement, text: string) => {
  await userEvent.type(within(dlg).getByLabelText("Message to Companion"), text);
  await userEvent.click(within(dlg).getByRole("button", { name: "Send" }));
};

describe("presentation/1 (semantics only, degrade safely)", () => {
  it("maps the contract's own example to a pose word and a mark", () => {
    const p = parsePresentation({ v: "presentation/1", state: "attentive", tone: "warm", gesture: "nod", speaking: true });
    expect(p).toEqual({ state: "attentive", tone: "warm", gesture: "nod", speaking: true });
    expect(poseFor(p)).toEqual({ word: "Listening, warmly", mark: "◎▾" });
  });
  it("unknown version, unknown values, missing fields, extra keys, wrong types and non-objects read as the defaults", () => {
    for (const bad of [null, undefined, 5, "x", [], {}, { v: "presentation/2", state: "engaged" }, { state: "dancing", tone: "furious", gesture: "backflip", speaking: "yes" }, { state: 3, tone: null }]) {
      expect(parsePresentation(bad)).toEqual(DEFAULT_PRESENTATION);
    }
    expect(parsePresentation({ state: "engaged", css: "bounce", anim: "x", px: 4 })).toEqual({ ...DEFAULT_PRESENTATION, state: "engaged" });
  });
  it("a partly known object keeps what it knows and defaults the rest", () => {
    expect(parsePresentation({ state: "engaged", tone: "mystery" })).toEqual({ ...DEFAULT_PRESENTATION, state: "engaged" });
  });
  it("poses are words plus a decorative mark: no animation vocabulary, whatever the input", () => {
    for (const state of ["rest", "attentive", "thinking", "engaged", "giving_space"]) for (const tone of ["neutral", "warm", "good_news", "concerned"]) {
      const { word, mark } = poseFor(parsePresentation({ state, tone }));
      expect(word).not.toMatch(/anim|sprite|frame|css|bone|colou?r|\bms\b|\bpx\b/i);
      expect(mark.length).toBeGreaterThan(0);
    }
    expect(poseFor(DEFAULT_PRESENTATION).word).toBe("Resting");
  });
});

describe("the Companion panel", () => {
  it("is a quiet button and a modal dialog, not a landmark", async () => {
    mount();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Companion/ })).toHaveAttribute("aria-haspopup", "dialog");
    const dlg = await openPanel();
    expect(dlg).toHaveAttribute("open");
    expect(within(dlg).getByRole("heading", { name: "Companion" })).toBeInTheDocument();
  });
  it("shows the presence as a word with an aria-hidden mark", async () => {
    mount();
    const dlg = await openPanel();
    expect(within(dlg).getByText("Resting")).toBeInTheDocument();
    expect(dlg.querySelector(".fd-companion-mark")).toHaveAttribute("aria-hidden", "true");
  });
  it("Close and Escape close it and return focus to the button", async () => {
    mount();
    const btn = screen.getByRole("button", { name: /^Companion/ });
    const dlg = await openPanel();
    await userEvent.click(within(dlg).getByRole("button", { name: "Close" }));
    expect(screen.getByRole("dialog", { hidden: true })).not.toHaveAttribute("open");
    expect(btn).toHaveFocus();
    await userEvent.click(btn);
    // jsdom has no Escape handling for a modal dialog; a browser fires `cancel`, which Playwright covers for real.
    fireEvent(screen.getByRole("dialog"), new Event("cancel", { cancelable: true }));
    await waitFor(() => expect(screen.getByRole("dialog", { hidden: true })).not.toHaveAttribute("open"));
    expect(btn).toHaveFocus();
  });
  it("sends a turn with a client_msg_id, shows 'thinking' while it is in flight, then the reply", async () => {
    server.use(http.post("/api/companion/turn", async ({ request }) => {
      await delay(80);
      const body = (await request.json()) as { message: string; client_msg_id: string };
      return HttpResponse.json({ thread_id: "t-1", reply: `Heard: ${body.message}`, connection: "local", tier_sent: "ordinary", sections: {}, unknown: [], grant: null, audit_id: "a", presentation: { v: "presentation/1", state: "engaged", tone: "neutral", gesture: "none", speaking: true } });
    }));
    mount();
    const dlg = await openPanel();
    await say(dlg, "hello");
    expect(within(dlg).getByText("Companion is thinking…")).toBeInTheDocument();                   // polite live region, in flight
    expect(within(dlg).getByRole("button", { name: "Send" })).toBeDisabled();
    expect(within(dlg).getByText("Thinking")).toBeInTheDocument();                                  // the pose word, synthesized locally
    expect(await within(dlg).findByText(/Heard: hello/)).toBeInTheDocument();
    expect(within(dlg).queryByText("Companion is thinking…")).not.toBeInTheDocument();
    expect(within(dlg).getByText("Here with you")).toBeInTheDocument();                             // settled pose from the response
    expect(within(dlg).getByLabelText("Message to Companion")).toHaveValue("");
  });
  it("renders what was withheld and the level honestly", async () => {
    mount();
    const dlg = await openPanel();
    await say(dlg, "what do you know");
    await within(dlg).findByText(/Here is a short answer/);
    expect(within(dlg).getByText("Some things were withheld: recall: withheld (tier)")).toBeInTheDocument();
    expect(within(dlg).getByText("Level: ordinary")).toBeInTheDocument();
  });
  it("unknown is an answer: a down Companion says so, keeps the message, and Try again re-sends the SAME key", async () => {
    companionServer.setMode("down");
    mount();
    const dlg = await openPanel();
    await say(dlg, "are you there");
    await waitFor(() => expect(within(dlg).getAllByText("Companion isn't answering.").length).toBeGreaterThanOrEqual(2));   // the health line and the failed turn
    expect(within(dlg).getAllByText("Unknown").length).toBeGreaterThanOrEqual(1);
    expect(within(dlg).queryByText(/Here is a short answer/)).not.toBeInTheDocument();             // no made-up reply
    expect(within(dlg).getByText("are you there")).toBeInTheDocument();                              // the person's words are still there
    companionServer.setMode("ok");
    await userEvent.click(within(dlg).getByRole("button", { name: "Try again" }));
    expect(await within(dlg).findByText(/Here is a short answer to: are you there/)).toBeInTheDocument();
    const turns = companionServer.calls.filter((c) => c.method === "POST" && c.path === "/api/companion/turn");
    expect(turns).toHaveLength(2);
    expect((turns[0].body as { client_msg_id: string }).client_msg_id).toBe((turns[1].body as { client_msg_id: string }).client_msg_id);
    await waitFor(() => expect(within(dlg).getAllByText("Companion isn't answering.")).toHaveLength(1));   // only the (now stale) health line remains
  });
  it("not configured is said plainly", async () => {
    companionServer.setMode("not_configured");
    mount();
    const dlg = await openPanel();
    expect(await within(dlg).findByText(/Companion isn't set up\./)).toBeInTheDocument();
  });
  it("sends the CSRF token from the cookie on a write, and none on a read", async () => {
    document.cookie = "pw_csrf=tok-abc";
    const seen: Record<string, string | null> = {};
    server.use(
      http.post("/api/companion/turn", ({ request }) => { seen.post = request.headers.get("x-csrf-token"); return HttpResponse.json({ thread_id: "t", reply: "ok", connection: "", tier_sent: "ordinary", sections: {}, unknown: [], grant: null, audit_id: "", presentation: null }); }),
      http.get("/api/companion/health", ({ request }) => { seen.get = request.headers.get("x-csrf-token"); return HttpResponse.json({ status: "ok", commit: "x", sources: {}, models: {} }); }),
    );
    mount();
    const dlg = await openPanel();
    await within(dlg).findByText("Companion is up.");
    await say(dlg, "hi");
    await within(dlg).findByText("ok");
    expect(seen.post).toBe("tok-abc");
    expect(seen.get).toBeNull();
  });
  it("never sends a token or a persona: only the message, the key and the thread", async () => {
    mount();
    const dlg = await openPanel();
    await say(dlg, "x");
    await within(dlg).findByText(/short answer/);
    const body = companionServer.calls.find((c) => c.path === "/api/companion/turn")!.body as Record<string, unknown>;
    expect(Object.keys(body).sort()).toEqual(["client_msg_id", "message"]);
  });
  it("shows the health line and an honest unknown when Companion is down", async () => {
    mount();
    let dlg = await openPanel();
    expect(await within(dlg).findByText(/Companion is up\. Not answering: ph\./)).toBeInTheDocument();
    cleanup();
    companionServer.setMode("down");
    mount();
    dlg = await openPanel();
    expect(await within(dlg).findByText("Companion isn't answering.")).toBeInTheDocument();
  });
  it("What Companion sees: section counts, items and every UNKNOWN line", async () => {
    mount();
    const dlg = await openPanel();
    const summary = within(dlg).getByText("What Companion sees");
    await userEvent.click(summary);
    expect(await within(dlg).findByText("Reviewed 1 · Working 0 · Recall 0 · Live 1")).toBeInTheDocument();
    expect(within(dlg).getByText("Prefers short answers.")).toBeInTheDocument();
    expect(within(dlg).getByText("2 things need you.")).toBeInTheDocument();
    expect(within(within(dlg).getByRole("region", { name: "Unknown" })).getByText("recall: withheld (tier)")).toBeInTheDocument();
    expect(within(within(dlg).getByRole("region", { name: "Working" })).getByText("Nothing.")).toBeInTheDocument();
  });
  it("What Companion sees: an unreachable Companion is Unknown, not an empty list", async () => {
    companionServer.setMode("down");
    mount();
    const dlg = await openPanel();
    await userEvent.click(within(dlg).getByText("What Companion sees"));
    await waitFor(() => expect(within(dlg).getAllByText("Companion isn't answering.").length).toBeGreaterThan(1));
    expect(within(dlg).queryByText("Nothing is unknown.")).not.toBeInTheDocument();
  });
  it("Deeper access: Worlds asks and shows state; approval is in Project Home", async () => {
    mount();
    const dlg = await openPanel();
    expect(within(dlg).getByText("Not active.")).toBeInTheDocument();
    await userEvent.type(within(dlg).getByLabelText("Why do you want Companion to see more?"), "plan the week");
    await userEvent.click(within(dlg).getByRole("button", { name: "Ask for deeper access" }));
    expect(await within(dlg).findByText("Waiting for you to approve it.")).toBeInTheDocument();
    expect(within(dlg).getByRole("link", { name: "Approve it in Project Home" })).toHaveAttribute("href", "/approvals/ap-1");
    const ask = companionServer.calls.find((c) => c.method === "POST" && c.path === "/api/companion/grants")!;
    expect(ask.body).toEqual({ ttl_s: 900, reason: "plan the week" });
    expect(within(dlg).queryByRole("button", { name: /approve$/i })).not.toBeInTheDocument();       // Worlds never decides a grant
    await userEvent.click(within(dlg).getByRole("button", { name: "Stop it" }));
    expect(await within(dlg).findByText("Not active (revoked).")).toBeInTheDocument();
  });
  it("Deeper access: an active grant says when it ends", async () => {
    server.use(http.post("/api/companion/grants", () => HttpResponse.json({ grant_id: "g-9", state: "active", expires_at: "2026-10-02T10:30:00Z", approval_id: null, link: null })));
    mount();
    const dlg = await openPanel();
    await userEvent.type(within(dlg).getByLabelText("Why do you want Companion to see more?"), "x");
    await userEvent.click(within(dlg).getByRole("button", { name: "Ask for deeper access" }));
    expect(await within(dlg).findByText(/^Active until \d\d:\d\d\.$/)).toBeInTheDocument();
  });
  it("Deeper access: an unsafe approval link is not a link", async () => {
    server.use(http.post("/api/companion/grants", () => HttpResponse.json({ grant_id: "g-9", state: "pending", expires_at: null, approval_id: "x", link: "javascript:alert(1)" })));
    mount();
    const dlg = await openPanel();
    await userEvent.type(within(dlg).getByLabelText("Why do you want Companion to see more?"), "x");
    await userEvent.click(within(dlg).getByRole("button", { name: "Ask for deeper access" }));
    await within(dlg).findByText("Waiting for you to approve it.");
    expect(within(dlg).queryByRole("link")).not.toBeInTheDocument();
    expect(within(dlg).getByText("Approve it in Project Home.")).toBeInTheDocument();
  });
  it("a Companion without grants yet says so plainly", async () => {
    server.use(http.post("/api/companion/grants", () => HttpResponse.json({ state: "unknown", text: "Companion isn't answering.", reason: "refused" }, { status: 502 })));
    mount();
    const dlg = await openPanel();
    await userEvent.type(within(dlg).getByLabelText("Why do you want Companion to see more?"), "x");
    await userEvent.click(within(dlg).getByRole("button", { name: "Ask for deeper access" }));
    expect(await within(dlg).findByText("Deeper access isn't available yet.")).toBeInTheDocument();
  });
  it("New conversation clears the thread view and resets the pose", async () => {
    mount();
    const dlg = await openPanel();
    await say(dlg, "first");
    await within(dlg).findByText(/short answer/);
    await userEvent.click(within(dlg).getByRole("button", { name: "New conversation" }));
    expect(within(dlg).queryByText(/short answer/)).not.toBeInTheDocument();
    expect(within(dlg).getByText("Resting")).toBeInTheDocument();
  });
});

describe("Earlier conversations", () => {
  it("loads lazily only when the disclosure is opened", async () => {
    mount();
    const dlg = await openPanel();
    // The disclosure is present but not open
    const disclosure = within(dlg).getByText("Earlier conversations").closest("details");
    expect(disclosure).not.toHaveAttribute("open");
    // No threads request yet
    expect(companionServer.calls.filter((c) => c.path === "/api/companion/threads")).toHaveLength(0);
    // Open it
    await userEvent.click(within(dlg).getByText("Earlier conversations"));
    await waitFor(() => expect(within(dlg).getByText("Conversation 1")).toBeInTheDocument());
    // Now the request was made
    expect(companionServer.calls.filter((c) => c.path === "/api/companion/threads")).toHaveLength(1);
  });

  it("shows an empty state when there are no old threads", async () => {
    // Override to return only the current thread
    server.use(http.get("/api/companion/threads", () => HttpResponse.json({ threads: ["t-1"] })));
    mount();
    const dlg = await openPanel();
    // Send a turn so the response's thread_id ("t-1") becomes the live thread
    await say(dlg, "hello");
    await within(dlg).findByText(/short answer/);
    await userEvent.click(within(dlg).getByText("Earlier conversations"));
    expect(await within(dlg).findByText("No earlier conversations.")).toBeInTheDocument();
  });

  it("shows Unknown when Companion is down, with a Try again button", async () => {
    companionServer.setMode("down");
    mount();
    const dlg = await openPanel();
    await userEvent.click(within(dlg).getByText("Earlier conversations"));
    await waitFor(() => expect(within(dlg).getAllByText("Companion isn't answering.").length).toBeGreaterThanOrEqual(2));
    expect(within(dlg).getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("Try again re-requests the list", async () => {
    companionServer.setMode("down");
    mount();
    const dlg = await openPanel();
    await userEvent.click(within(dlg).getByText("Earlier conversations"));
    await waitFor(() => expect(within(dlg).getAllByText("Companion isn't answering.").length).toBeGreaterThanOrEqual(2));
    companionServer.setMode("ok");
    await userEvent.click(within(dlg).getByRole("button", { name: "Try again" }));
    expect(await within(dlg).findByText("Conversation 1")).toBeInTheDocument();
  });

  it("shows not configured when Companion is not set up", async () => {
    companionServer.setMode("not_configured");
    mount();
    const dlg = await openPanel();
    await userEvent.click(within(dlg).getByText("Earlier conversations"));
    await waitFor(() => expect(within(dlg).getAllByText(/Companion isn't set up/).length).toBeGreaterThanOrEqual(2));
  });

  it("opens an old thread read-only with no composer", async () => {
    mount();
    const dlg = await openPanel();
    await userEvent.click(within(dlg).getByText("Earlier conversations"));
    await waitFor(() => expect(within(dlg).getByText("Conversation 1")).toBeInTheDocument());
    await userEvent.click(within(dlg).getByText("Conversation 1"));
    // The old thread view is shown
    expect(await within(dlg).findByText(/Back to the current conversation/)).toBeInTheDocument();
    expect(within(dlg).getByText("What's the weather?")).toBeInTheDocument();
    expect(within(dlg).getByText("I don't have real-time data.")).toBeInTheDocument();
    // No composer
    expect(within(dlg).queryByLabelText("Message to Companion")).not.toBeInTheDocument();
    expect(within(dlg).queryByRole("button", { name: "Send" })).not.toBeInTheDocument();
  });

  it("Back restores the live view and returns focus to the Earlier conversations summary", async () => {
    mount();
    const dlg = await openPanel();
    const summary = within(dlg).getByText("Earlier conversations");
    await userEvent.click(summary);
    await waitFor(() => expect(within(dlg).getByText("Conversation 1")).toBeInTheDocument());
    await userEvent.click(within(dlg).getByText("Conversation 1"));
    await within(dlg).findByText(/Back to the current conversation/);
    const backBtn = within(dlg).getByRole("button", { name: /Back to the current conversation/ });
    expect(backBtn).toHaveFocus();
    await userEvent.click(backBtn);
    // Live view is restored
    expect(within(dlg).getByLabelText("Message to Companion")).toBeInTheDocument();
    expect(within(dlg).getByRole("button", { name: "Send" })).toBeInTheDocument();
    expect(within(dlg).queryByText(/What's the weather/)).not.toBeInTheDocument();
    // Focus lands on the summary (the control the person used to get there).
    await waitFor(() => expect(within(dlg).getByText("Earlier conversations")).toHaveFocus());
  });

  it("before any turn, every thread from the server is listed", async () => {
    mount();
    const dlg = await openPanel();
    await userEvent.click(within(dlg).getByText("Earlier conversations"));
    // Server returns ["t-old-1", "t-old-2", "t-1"]; with no live thread yet, none is excluded.
    await waitFor(() => expect(within(dlg).getByText("Conversation 1")).toBeInTheDocument());
    expect(within(dlg).getByText("Conversation 2")).toBeInTheDocument();
    expect(within(dlg).getByText("Conversation 3")).toBeInTheDocument();
  });

  it("after a reply, the reply's thread_id is excluded from the Earlier list and the others remain", async () => {
    mount();
    const dlg = await openPanel();
    // Default server reply carries thread_id "t-1".
    await say(dlg, "hello");
    await within(dlg).findByText(/short answer/);
    await userEvent.click(within(dlg).getByText("Earlier conversations"));
    await waitFor(() => expect(within(dlg).getByText("Conversation 1")).toBeInTheDocument());
    expect(within(dlg).getByText("Conversation 2")).toBeInTheDocument();
    // The live thread "t-1" is excluded, so only the two old threads remain.
    expect(within(dlg).queryByText("Conversation 3")).not.toBeInTheDocument();
  });

  it("a thread literally named 't-1' is listed when it is not the live thread", async () => {
    // Give the live thread a different id so the literal "t-1" from the list isn't the live one.
    server.use(http.post("/api/companion/turn", () => HttpResponse.json({
      thread_id: "t-live-other", reply: "ok", connection: "local", tier_sent: "ordinary",
      sections: {}, unknown: [], grant: null, audit_id: "a",
      presentation: { v: "presentation/1", state: "engaged", tone: "neutral", gesture: "none", speaking: true },
    })));
    mount();
    const dlg = await openPanel();
    await say(dlg, "hi");
    await within(dlg).findByText("ok");
    await userEvent.click(within(dlg).getByText("Earlier conversations"));
    // Server returns ["t-old-1", "t-old-2", "t-1"]; live is "t-live-other" (not in list), so all three are listed.
    await waitFor(() => expect(within(dlg).getByText("Conversation 1")).toBeInTheDocument());
    expect(within(dlg).getByText("Conversation 2")).toBeInTheDocument();
    expect(within(dlg).getByText("Conversation 3")).toBeInTheDocument();
  });
});
