"""Sign-in, sign-out, step-up and session routes for the single owner (fail closed).

* The redirect URI and cookie origin come from ``owner.yaml`` ``public_origin``, never from the
  Host header (no host-header poisoning of the OIDC redirect).
* OIDC sign-in succeeds only for the allow-listed ``issuer`` + ``subject``. A verified identity
  that is not the owner gets 403 and no session.
* Local bootstrap sign-in uses a secret from a ``secret_ref``; failures are rate limited.
* Step-up needs a FRESH proof: an OIDC re-login with ``auth_time`` inside the window for the same
  subject, or the bootstrap secret again. A token never confers step-up.
* Every POST here also requires an allowed Origin (login CSRF), even with no session yet.
"""

from __future__ import annotations

import ipaddress
import logging
from collections import deque
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from ..oidc import FLOW_COOKIE, OIDCError, OIDCLoginError
from .authn import CSRF_COOKIE, SESSION_COOKIE, Auth
from .owner import OwnerPolicy

_log = logging.getLogger(__name__)
FRESH_AUTH_SECONDS = 120
FREE_FAILURES = 3          # per client: this many wrong guesses cost nothing
MAX_BACKOFF = 900.0        # per client: exponential back-off is capped at 15 minutes
FAILURE_WINDOW = 600.0
GLOBAL_CEILING = 30        # failures in the window, across everybody, before the whole endpoint slows
GLOBAL_GAP = 2.0           # ...to one attempt per this many seconds. It slows; it never locks.
OIDC_LOGIN_KEY = "oidc_login_binding"
ESCAPE_SUCCESS_GAP = 900.0  # in back-off, the correct secret passes at most once per 15 minutes
EVAL_GAP = 2.0             # in back-off, at most one guess is even compared per client key per this many seconds


class _Limiter:
    """Per-client exponential back-off plus a global slow-down (never a global lock-out).

    The client key is the peer address as the server reports it; behind a reverse proxy run uvicorn
    with proxy headers limited to the proxy's address (``--forwarded-allow-ips``) so it is the real
    client, not the proxy. A client in back-off is refused WITHOUT its secret being checked, so
    back-off cannot be used to keep guessing.
    """

    def __init__(self, clock: Callable[[], float]):
        self._clock = clock
        self._clients: dict[str, tuple[int, float, float]] = {}   # key -> (fails, blocked_until, last_fail)
        self._last_eval: dict[str, float] = {}
        self._global = deque()
        self._last_attempt = -1e18

    def check(self, client: str) -> float:
        """Seconds the caller must wait (0 = go ahead). Records the attempt time for the global gap."""
        now = self._clock()
        while self._global and now - self._global[0] > FAILURE_WINDOW:
            self._global.popleft()
        for key in [k for k, v in self._clients.items() if now - v[2] > FAILURE_WINDOW * 3 and v[1] <= now]:
            del self._clients[key]
        _fails, blocked_until, _last = self._clients.get(client, (0, 0.0, 0.0))
        wait = max(blocked_until - now, 0.0)
        if not wait and len(self._global) >= GLOBAL_CEILING:
            wait = max(GLOBAL_GAP - (now - self._last_attempt), 0.0)
        if not wait:
            self._last_attempt = now
        return wait

    def fail(self, client: str) -> None:
        now = self._clock()
        fails, _blocked, _last = self._clients.get(client, (0, 0.0, 0.0))
        fails = min(fails + 1, 10_000)   # a capped count can never overflow the delay below
        delay = 0.0 if fails <= FREE_FAILURES else min(5.0 * 2 ** min(fails - FREE_FAILURES - 1, 16), MAX_BACKOFF)
        self._clients[client] = (fails, now + delay, now)
        self._global.append(now)

    def clear(self, client: str) -> None:
        self._clients.pop(client, None)

    # The owner's way out of a back-off they did not cause (a shared proxy address, an attacker holding the
    # key). EVERY guess is evaluated (the comparison is made on every request anyway), so nothing an
    # attacker sends can occupy a slot the owner needs: a correct secret passes whenever the 15-minute
    # success slot is free, regardless of any back-off. Wrong guesses in back-off lengthen it further.
    _escape_passed = -1e18

    def eval_slot(self, client: str) -> bool:
        """In back-off a key gets one evaluated guess per EVAL_GAP; others are refused WITHOUT comparing, so
        back-off still throttles guessing. Keys are independent: nobody can use up another key's slot."""
        now = self._clock()
        if now - self._last_eval.get(client, -1e18) < EVAL_GAP:
            return False
        self._last_eval[client] = now
        if len(self._last_eval) > 10_000:
            self._last_eval = {k: v for k, v in self._last_eval.items() if now - v < FAILURE_WINDOW}
        return True

    def escape_pass_slot(self) -> bool:
        return self._clock() - self._escape_passed >= ESCAPE_SUCCESS_GAP

    def escape_passed(self) -> None:
        self._escape_passed = self._clock()


def parse_trusted_proxies(value: str | None) -> tuple[Any, ...]:
    """``PW_TRUSTED_PROXIES``: comma-separated IPs/CIDRs of the reverse proxies in front of Worlds."""
    nets = []
    for part in (value or "").split(","):
        part = part.strip()
        if part:
            nets.append(ipaddress.ip_network(part, strict=False))   # raises ValueError on junk: fail at startup
    return tuple(nets)


_warned = {"xff": False}


def _strip_port(hop: str) -> str:
    """``1.2.3.4:5678`` -> ``1.2.3.4``; ``[::1]:80`` / ``[::1]`` -> ``::1``; a bare IPv6 stays as it is."""
    if hop.startswith("["):
        return hop[1:hop.index("]")] if "]" in hop else hop
    if hop.count(":") == 1:
        return hop.split(":", 1)[0]
    return hop


def client_key(request: Request, trusted: tuple[Any, ...]) -> str:
    """Who to rate-limit. Behind trusted proxies: the right-most X-Forwarded-For hop that is NOT a trusted
    proxy. A peer that is not a trusted proxy is never believed about X-Forwarded-For. With no trusted
    proxies configured the peer address is used, and a warning is logged once if requests arrive with
    X-Forwarded-For from a non-loopback peer (everyone then shares the proxy's key)."""
    peer = request.client.host if request.client else "unknown"
    xff = ",".join(request.headers.getlist("x-forwarded-for")) or None   # every header line, in order
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    if not trusted:
        if xff and not peer_ip.is_loopback and not _warned["xff"]:
            _warned["xff"] = True
            _log.warning("X-Forwarded-For seen from %s but PW_TRUSTED_PROXIES is unset: all clients behind it share one "
                         "sign-in rate-limit key. Set PW_TRUSTED_PROXIES to the proxy's address.", peer)
        return peer
    if not xff or not any(peer_ip in net for net in trusted):
        return peer
    for hop in reversed([h.strip() for h in xff.split(",")]):
        try:
            ip = ipaddress.ip_address(_strip_port(hop))
        except ValueError:
            return peer                      # garbage in the chain: do not trust any of it
        if not any(ip in net for net in trusted):
            return str(ip)
    return peer


def _safe_return(path: str | None) -> str:
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path or "\n" in path or "\r" in path:
        return "/"
    return path


def register_auth_routes(app: FastAPI, auth: Auth, policy_loader: Callable[[], OwnerPolicy], oidc_service: Any | None = None,
                         trusted_proxies: tuple[Any, ...] = ()) -> None:
    limiter = _Limiter(auth.clock)

    def policy() -> OwnerPolicy:
        return policy_loader()

    def bootstrap_open() -> bool:
        """Bootstrap sign-in/step-up works while enabled, until OIDC is configured AND has worked once."""
        pol = policy()
        if not (pol.file and pol.file.bootstrap.enabled):
            return False
        if pol.file.oidc and auth.get_state(OIDC_LOGIN_KEY) == pol.binding():
            return False
        return True

    def require_origin(request: Request) -> None:
        origin = request.headers.get("origin")
        if origin is None or origin.rstrip("/") not in auth.allowed_origins:
            raise HTTPException(status_code=403, detail="origin not allowed")

    def start_session(response: JSONResponse | RedirectResponse, method: str) -> str:
        sid = auth.sessions.create("owner", method)
        response.set_cookie(SESSION_COOKIE, sid, httponly=True, secure=True, samesite="lax", max_age=7 * 24 * 3600, path="/")
        response.set_cookie(CSRF_COOKIE, auth.csrf_token(sid), httponly=False, secure=True, samesite="strict", max_age=7 * 24 * 3600, path="/")
        return sid

    def redirect_uri(pol: OwnerPolicy) -> str:
        if not pol.public_origin:
            raise HTTPException(status_code=503, detail="owner policy is not configured")
        return f"{pol.public_origin}/api/auth/oidc/callback"

    @app.get("/api/auth/session")
    def session_info(request: Request) -> JSONResponse:
        sid = request.cookies.get(SESSION_COOKIE)
        row = auth.sessions.get(sid)
        pol = policy()
        base = {"oidc_available": bool(pol.file and pol.file.oidc), "bootstrap_available": bootstrap_open()}
        if row is None:
            return JSONResponse({"authenticated": False, **base}, headers={"Cache-Control": "no-store"})
        step = row["step_up_at"] is not None and auth.clock() - row["step_up_at"] <= 300
        body = {"authenticated": True, "principal": row["principal"], "step_up": step, "csrf_token": auth.csrf_token(sid), **base}
        resp = JSONResponse(body, headers={"Cache-Control": "no-store"})
        resp.set_cookie(CSRF_COOKIE, auth.csrf_token(sid), httponly=False, secure=True, samesite="strict", path="/")
        return resp

    def check_bootstrap(client: str, token: str) -> bool:
        """True when this attempt is the owner. Always does the same work (the secret comparison)."""
        wait = limiter.check(client)
        if not wait:
            matches = bootstrap_open() and policy().bootstrap_matches(token)      # constant-time
            if matches:
                limiter.clear(client)
                return True
            limiter.fail(client)
            raise HTTPException(status_code=401, detail="that did not work")
        # In back-off: this key may test one guess per EVAL_GAP (over the rate: refused without comparing);
        # the correct secret then passes, at most once per 15 minutes, so the owner is never locked out.
        if limiter.eval_slot(client):
            matches = bootstrap_open() and policy().bootstrap_matches(token)
            if matches and limiter.escape_pass_slot():
                limiter.escape_passed()
                limiter.clear(client)
                return True
            if not matches:
                limiter.fail(client)        # a wrong guess lengthens the back-off (the escape ignores it)
        raise HTTPException(status_code=429, detail="too many attempts; wait and try again",
                            headers={"Retry-After": str(int(wait) + 1)})

    @app.post("/api/auth/bootstrap")
    async def bootstrap(request: Request) -> JSONResponse:
        require_origin(request)
        body = await _json(request)
        check_bootstrap(client_key(request, trusted_proxies), str(body.get("token", "")))
        resp = JSONResponse({"ok": True})
        start_session(resp, "bootstrap")
        return resp

    @app.post("/api/auth/step-up")
    async def step_up(request: Request) -> JSONResponse:
        principal = auth.authenticate(request)  # session + CSRF checked here
        if not principal.is_owner or principal.via != "session":
            raise HTTPException(status_code=403, detail="owner session required")
        body = await _json(request)
        check_bootstrap(client_key(request, trusted_proxies), str(body.get("token", "")))
        auth.sessions.mark_step_up(request.cookies.get(SESSION_COOKIE) or "")
        return JSONResponse({"ok": True})

    @app.post("/api/auth/logout")
    def logout(request: Request) -> JSONResponse:
        principal = auth.authenticate(request)
        sid = request.cookies.get(SESSION_COOKIE)
        if sid and principal.via == "session":
            auth.sessions.invalidate(sid)
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(SESSION_COOKIE, path="/")
        resp.delete_cookie(CSRF_COOKIE, path="/")
        return resp

    def _flow_redirect(url: str, cookie: str) -> RedirectResponse:
        resp = RedirectResponse(url, status_code=303, headers={"Cache-Control": "no-store"})
        resp.set_cookie(FLOW_COOKIE, cookie, httponly=True, secure=True, samesite="lax", max_age=600, path="/")
        return resp

    def _oidc_client(pol: OwnerPolicy):
        if oidc_service is None or not (pol.file and pol.file.oidc):
            raise HTTPException(status_code=503, detail="OIDC sign-in is not configured")
        try:
            return oidc_service.client()
        except OIDCError as exc:
            raise HTTPException(status_code=503, detail=f"OIDC unavailable: {exc.error_code}") from None

    @app.get("/api/auth/oidc/login")
    def oidc_login() -> RedirectResponse:
        pol = policy()
        client = _oidc_client(pol)
        url, _pending, cookie = client.start_login(redirect_uri(pol))
        return _flow_redirect(url, cookie)

    @app.get("/api/auth/oidc/step-up")
    def oidc_step_up(request: Request, return_to: str = "/") -> RedirectResponse:
        row = auth.sessions.get(request.cookies.get(SESSION_COOKIE))
        if row is None:
            raise HTTPException(status_code=401, detail="sign in first")
        pol = policy()
        client = _oidc_client(pol)
        url, _pending, cookie = client.start_login(redirect_uri(pol), step_up_for=row["principal"], return_to=_safe_return(return_to))
        return _flow_redirect(url, cookie)

    @app.get("/api/auth/oidc/callback")
    def oidc_callback(request: Request, code: str = "", state: str = "", error: str = "") -> Any:
        pol = policy()
        if error:
            raise HTTPException(status_code=403, detail="the identity provider refused the sign-in")
        client = _oidc_client(pol)
        try:
            import secrets as _s

            pending = client.read_pending(request.cookies.get(FLOW_COOKIE))
            if not state or not _s.compare_digest(state, pending.state):
                raise OIDCLoginError("sign-in response does not match this browser's attempt", error_code="oidc_state_mismatch")
            identity = client.complete_login(code, pending)
        except OIDCError as exc:
            raise HTTPException(status_code=exc.http_status if hasattr(exc, "http_status") and exc.http_status in (400, 401, 403) else 403,
                                detail=f"sign-in failed ({exc.error_code})") from None
        if not pol.is_owner_identity(identity.issuer, identity.sub):
            raise HTTPException(status_code=403, detail="this identity is not the owner")
        if pending.step_up_for:
            sid = request.cookies.get(SESSION_COOKIE)
            row = auth.sessions.get(sid)
            fresh = identity.auth_time is not None and 0 <= auth.clock() - identity.auth_time <= FRESH_AUTH_SECONDS
            if row is None or row["principal"] != pending.step_up_for or not fresh:
                raise HTTPException(status_code=403, detail="step-up needs a fresh sign-in by the owner")
            auth.sessions.mark_step_up(sid)
            resp = RedirectResponse(_safe_return(pending.return_to), status_code=303, headers={"Cache-Control": "no-store"})
            resp.delete_cookie(FLOW_COOKIE, path="/")
            return resp
        auth.set_state(OIDC_LOGIN_KEY, pol.binding())   # OIDC works: bootstrap may now switch itself off
        resp = RedirectResponse("/", status_code=303, headers={"Cache-Control": "no-store"})
        start_session(resp, "oidc")
        resp.delete_cookie(FLOW_COOKIE, path="/")
        return resp


async def _json(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="body must be JSON") from None
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    return data
