import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { csrfHeaders } from "./api";

type Device = { id: string; device_label?: string; created_at?: string };
type Session = { authenticated: boolean; bootstrap_available?: boolean; oidc_available?: boolean };

const ios = () => /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

export function Notifications() {
  const [session, setSession] = useState<Session | null>(null);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [message, setMessage] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const standalone = (window.navigator as Navigator & { standalone?: boolean }).standalone === true || window.matchMedia("(display-mode: standalone)").matches;
  const supported = "Notification" in window && "PushManager" in window && !!navigator.serviceWorker;

  async function loadDevices() {
    const response = await fetch("/api/push/subscriptions");
    if (response.ok) setDevices(((await response.json()) as { data: Device[] }).data);
  }

  useEffect(() => {
    void (async () => {
      const response = await fetch("/api/auth/session");
      const value = (await response.json()) as Session;
      setSession(value);
      if (!value.authenticated) return;
      const key = await fetch("/api/push/public-key");
      setConfigured(key.ok);
      await loadDevices();
    })().catch(() => setMessage("Notification settings could not be loaded."));
  }, []);

  async function enable() {
    setBusy(true); setMessage("");
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") { setMessage(permission === "denied" ? "Notifications are blocked in this browser." : "Notifications are off."); return; }
      const keyResponse = await fetch("/api/push/public-key");
      if (!keyResponse.ok) { setConfigured(false); setMessage("Notifications are not configured on this server."); return; }
      const { data } = await keyResponse.json() as { data: { public_key: string } };
      const registration = await navigator.serviceWorker.register("/sw.js");
      const subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: Uint8Array.from(atob(data.public_key.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0)) });
      const response = await fetch("/api/push/subscriptions", { method: "POST", headers: { "content-type": "application/json", ...csrfHeaders() }, body: JSON.stringify({ subscription: subscription.toJSON(), device_label: navigator.userAgent.includes("iPhone") ? "iPhone" : "This device" }) });
      if (!response.ok) throw new Error("Device registration failed.");
      setConfigured(true); await loadDevices(); setMessage("Notifications are on for this device.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Notifications could not be turned on."); }
    finally { setBusy(false); }
  }

  async function remove(id: string) {
    const response = await fetch(`/api/push/subscriptions/${encodeURIComponent(id)}`, { method: "DELETE", headers: csrfHeaders() });
    if (response.ok) { await loadDevices(); setMessage("Device removed."); }
  }
  async function sendTest() {
    const response = await fetch("/api/notifications/test", { method: "POST", headers: csrfHeaders() });
    setMessage(response.ok ? "Test notification sent." : "The test notification could not be sent.");
  }
  async function bootstrap(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try {
      const response = await fetch("/api/auth/bootstrap", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ token }) });
      if (!response.ok) throw new Error("Sign-in did not work.");
      window.location.reload();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Sign-in did not work."); }
    finally { setBusy(false); }
  }

  if (session === null) return <section className="fd-settings-section"><h2 className="fd-settings-section-title">Notifications</h2><p className="fd-settings-value">Checking sign-in…</p></section>;
  if (!session.authenticated) return <section className="fd-settings-section"><h2 className="fd-settings-section-title">Sign in</h2><p className="fd-settings-note">Sign in to manage this device and its notifications.</p>{session.oidc_available && <p><a href="/api/auth/oidc/login">Sign in</a></p>}{session.bootstrap_available && <form className="fd-notify-form" onSubmit={bootstrap}><label htmlFor="bootstrap-token">Bootstrap secret</label><input id="bootstrap-token" type="password" autoComplete="current-password" value={token} onChange={(event) => setToken(event.target.value)} /><button className="fd-btn" disabled={busy || !token}>Sign in</button></form>}<p role="status">{message}</p></section>;

  const state = !supported ? "unsupported" : configured === false ? "not configured" : Notification.permission === "denied" ? "blocked" : devices.length ? "on" : "off";
  return <section className="fd-settings-section"><h2 className="fd-settings-section-title">Notifications</h2>
    <p className="fd-settings-value">Status: {state}</p>
    {supported && configured !== false && !(ios() && !standalone) && <button className="fd-btn" onClick={() => void enable()} disabled={busy}>Turn on for this device</button>}
    {supported && configured !== false && ios() && !standalone && <p className="fd-settings-note">To turn on notifications on iPhone, use Share, then Add to Home Screen. Open Worlds from your Home Screen to continue.</p>}
    {configured === false && <p className="fd-settings-note">Notifications are not configured on this server.</p>}
    {!supported && <p className="fd-settings-note">This browser does not support push notifications.</p>}
    {devices.length > 0 && <div><h3 className="fd-notify-title">This device and others</h3><ul className="fd-notify-devices">{devices.map((device) => <li key={device.id}><span>{device.device_label || "Device"}</span><button className="fd-btn" onClick={() => void remove(device.id)}>Remove</button></li>)}</ul><button className="fd-btn" onClick={() => void sendTest()}>Send me a test</button></div>}
    <p role="status" aria-live="polite">{message}</p>
  </section>;
}
