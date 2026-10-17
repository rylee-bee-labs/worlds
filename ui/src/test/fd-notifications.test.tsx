import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { Notifications } from "../fd/Notifications";

const server = setupServer(
  http.get("/api/auth/session", () => HttpResponse.json({ authenticated: true })),
  http.get("/api/push/public-key", () => HttpResponse.json({ detail: "not configured" }, { status: 409 })),
  http.get("/api/push/subscriptions", () => HttpResponse.json({ ok: true, data: [] })),
);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => { cleanup(); server.resetHandlers(); });
afterAll(() => server.close());

function browser({ permission = "default", supported = true, ios = false } = {}) {
  Object.defineProperty(window, "Notification", { configurable: true, value: { permission, requestPermission: async () => permission } });
  Object.defineProperty(window, "PushManager", { configurable: true, value: class PushManager {} });
  Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: supported ? { register: async () => ({}) } : undefined });
  Object.defineProperty(navigator, "userAgent", { configurable: true, value: ios ? "iPhone" : "Test browser" });
}

describe("front-door notifications", () => {
  it("shows off, blocked, not configured and unsupported in words", async () => {
    browser();
    const { unmount } = render(<Notifications />);
    expect(await screen.findByText("Status: not configured")).toBeInTheDocument();
    unmount();
    server.use(http.get("/api/push/public-key", () => HttpResponse.json({ ok: true, data: { public_key: "public" } })));
    render(<Notifications />);
    expect(await screen.findByText("Status: off")).toBeInTheDocument();
    cleanup();
    browser({ permission: "denied" });
    render(<Notifications />);
    expect(await screen.findByText("Status: blocked")).toBeInTheDocument();
    cleanup();
    browser({ supported: false });
    render(<Notifications />);
    expect(await screen.findByText("Status: unsupported")).toBeInTheDocument();
  });

  it("gives iPhone Safari directions outside standalone mode", async () => {
    browser({ ios: true });
    server.use(http.get("/api/push/public-key", () => HttpResponse.json({ ok: true, data: { public_key: "public" } })));
    render(<Notifications />);
    expect(await screen.findByText(/use Share, then Add to Home Screen/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Turn on for this device" })).not.toBeInTheDocument();
  });

  it("shows on when a device subscription is listed", async () => {
    browser();
    server.use(
      http.get("/api/push/public-key", () => HttpResponse.json({ ok: true, data: { public_key: "public" } })),
      http.get("/api/push/subscriptions", () => HttpResponse.json({ ok: true, data: [{ id: "device-1", device_label: "Phone" }] })),
    );
    render(<Notifications />);
    expect(await screen.findByText("Status: on")).toBeInTheDocument();
    expect(screen.getByText("Phone")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send me a test" })).toBeInTheDocument();
  });

  it("shows the signed-out panel and bootstrap-secret form", async () => {
    server.use(http.get("/api/auth/session", () => HttpResponse.json({ authenticated: false, bootstrap_available: true, oidc_available: true })));
    render(<Notifications />);
    expect(await screen.findByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/api/auth/oidc/login");
    expect(screen.getByLabelText("Bootstrap secret")).toHaveAttribute("type", "password");
  });

  it("requests permission only after pressing the device button", async () => {
    let asked = false;
    Object.defineProperty(window, "Notification", { configurable: true, value: { permission: "default", requestPermission: async () => { asked = true; return "denied"; } } });
    Object.defineProperty(window, "PushManager", { configurable: true, value: class PushManager {} });
    Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: { register: async () => ({}) } });
    server.use(http.get("/api/push/public-key", () => HttpResponse.json({ ok: true, data: { public_key: "public" } })));
    render(<Notifications />);
    const button = await screen.findByRole("button", { name: "Turn on for this device" });
    expect(asked).toBe(false);
    await userEvent.click(button);
    expect(asked).toBe(true);
  });
});
