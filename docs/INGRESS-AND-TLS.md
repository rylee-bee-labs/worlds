# Ingress & TLS — serving Worlds over HTTPS (internal-only pattern)

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** the reverse-proxy / forwarded-headers pattern for serving Worlds over HTTPS · **Read this if:** you are putting Worlds behind Traefik, nginx, or Caddy and need cookies and OIDC redirects to work.

**In short:** Worlds speaks plain HTTP on `:8000` behind your own TLS-terminating reverse proxy, and trusts `X-Forwarded-*` so session cookies and OIDC redirect URIs come out `https://`. This page is the sanitized pattern — substitute your own host and network values.

*Sanitized: no private hostnames or addresses live in this repo. Substitute your
own values where you see `<worlds-host>`, `<lan-ip>`, `<wildcard-domain>`.*

Worlds terminates TLS at your existing reverse proxy (Traefik, nginx,
Caddy — anything that sets `X-Forwarded-Proto`). The app itself speaks plain
HTTP on `:8000` inside your network and **trusts forwarded proto**, so:

- session cookies (`Secure`) persist correctly over HTTPS;
- OIDC `redirect_uri` is computed as `https://…`, matching your IdP registration;
- LAN clients use a normal hostname with no port in the URL.

## What the app needs (already in the image)
`uvicorn --proxy-headers --forwarded-allow-ips='*'` — set in the Dockerfile CMD.
Only enable this behind a proxy you control; it makes the app trust
`X-Forwarded-*` headers.

## Traefik pattern (file provider)
```yaml
routers:
  worlds:
    rule: "Host(`<worlds-host>`)"
    entryPoints: [websecure]
    middlewares: [secure]          # your existing header-hardening chain
    service: worlds
    tls:
      certResolver: letsencrypt    # or your internal CA / cert files
      domains:
        - main: "<wildcard-domain>"
          sans: ["<apex-domain>"]
services:
  worlds:
    loadBalancer:
      servers:
        - url: "http://<lan-ip>:8000"
```
Notes:
- Worlds brings its **own auth** (local session or OIDC). Do not put a
  forward-auth login chain in front of it unless you want double login; if you
  do, register the proxy URL as an OIDC redirect target too.
- With a wildcard DNS record pointing at the proxy, adding the router is the
  only change needed (no zone edit).
- Keep it **internal-only** by not publishing the entryPoint externally and/or
  firewalling the proxy port to your LAN.

## DNS
- Internal-only: an internal zone record (or split-horizon) for `<worlds-host>`
  pointing at the proxy's LAN address.
- Dynamic-DNS homes: a wildcard `*.<apex-domain>` A record at the proxy works
  and needs no per-service change.

## Verify
```bash
curl -sI https://<worlds-host>/healthz            # 200
curl -sI https://<worlds-host>/                   # 200 interface, or 303 -> /setup on first-run
curl -s  https://<worlds-host>/api/auth/oidc/status   # not_configured | configured
```
Then sign in once; the session cookie should persist across restarts (Secure +
HTTPS). If login bounces forever, the proxy is not sending `X-Forwarded-Proto`
— check `--proxy-headers` and the proxy's forwarded-headers config.

## Content-Security-Policy (report-only)
The interface page is served with `Content-Security-Policy-Report-Only`
(`station_ui.CSP_REPORT_ONLY`): it blocks nothing, and the browser console
lists what a stricter policy would refuse. Tighten it from that evidence,
then switch the header to enforcing.

Which security headers your reverse proxy adds on top (HSTS, frame options,
its own CSP, referrer policy) is **not recorded in this repo yet and is
UNVERIFIED**. Record the real header set here, with placeholders for hosts,
once someone has checked the running proxy.

## Sanitization rule
Private hostnames, LAN addresses, and IdP URLs belong in your **private**
infra repo only. This repo ships the pattern with placeholders, and
`tests/test_public_safety.py` guards tracked config from private topology.
