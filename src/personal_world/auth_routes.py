"""Auth HTTP routes: login, logout, callback, session management.

Two sign-in paths share one session model. Local token login and the
generic OIDC login both end at ``AuthManager``/``identity.py``, which
resolve a canonical ``Principal``; neither route invents its own
credential system.

OIDC specifics are in ``oidc.py`` (discovery, PKCE, id_token
verification). This file only speaks HTTP: where to redirect, which
cookie to set, and how to fail.
"""

import logging
import os
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .auth import AuthManager
from .identity import NoPrincipalError
from .oidc import (
    FLOW_COOKIE,
    NOT_CONFIGURED,
    OIDCError,
    OIDCLoginError,
    OIDCService,
)

_logger = logging.getLogger("personal_world.auth_routes")

SESSION_COOKIE = "pw_session"
SESSION_MAX_AGE = 86400
LOGIN_PATH = "/login"


def _set_session_cookie(response, session_id: str) -> None:
    # Secure by default. The ONLY opt-down is an explicit development pair:
    # PW_DEV_AUTH_BYPASS=1 (true-loopback) AND PW_COOKIE_SECURE=false, so a
    # plain-HTTP loopback/e2e run can hold a session. Production can never
    # reach the insecure branch because the bypass itself is dev-only.
    insecure_dev = (
        os.environ.get("PW_DEV_AUTH_BYPASS") == "1"
        and os.environ.get("PW_COOKIE_SECURE", "true").lower() == "false"
    )
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        httponly=True,
        secure=not insecure_dev,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )


def _failure_response(request: Request, exc: OIDCError):
    """Degrade gracefully in both directions.

    A browser navigating the sign-in flow gets a redirect to the login
    page with a short, non-secret error code (the SPA presents it). An
    API caller that asked for JSON gets the reason in the body.
    Neither ever receives a credential, a token, or an identity claim,
    and the detail is logged once server-side for the operator.
    """
    _logger.warning("oidc sign-in failed (%s): %s", exc.error_code, exc.detail)
    accept = request.headers.get("accept", "")
    wants_json = "application/json" in accept and "text/html" not in accept
    if wants_json:
        return JSONResponse(
            {
                "ok": False,
                "status": exc.status,
                "error_code": exc.error_code,
                "detail": exc.detail,
                "warnings": exc.warnings,
            },
            status_code=exc.http_status,
            headers={"Cache-Control": "no-store"},
        )
    response = RedirectResponse(
        f"{LOGIN_PATH}?pw_auth_error={exc.error_code}",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )
    response.delete_cookie(FLOW_COOKIE)
    return response


def register_auth_routes(app: FastAPI, auth: AuthManager):

    def _oidc(request: Request) -> OIDCService:
        """The process-wide OIDC service, resolved off ``app.state``.

        Kept on app.state (not closed over) for two reasons: the
        setup wizard can call ``reload()`` after it writes
        ``config/oidc.json``, and tests can substitute a stub transport
        without reaching into module globals.
        """
        service = getattr(app.state, "oidc", None)
        if service is None:
            config_dir = Path(
                getattr(auth, "_config_dir", None)
                or os.environ.get("PW_CONFIG_DIR", "./config")
            )
            service = OIDCService(config_dir)
            app.state.oidc = service
        return service

    @app.post("/api/auth/login")
    async def auth_login(request: Request):
        """Local/bootstrap login."""
        body = await request.json()
        token = (body or {}).get("token", "").strip()
        if not token:
            raise HTTPException(400, "token required")
        session = auth.login_local(token)
        if not session:
            raise HTTPException(401, "invalid token")
        response = JSONResponse(
            {
                "ok": True,
                "data": {
                    "session_id": session.id,
                    "auth_method": session.auth_method,
                },
            }
        )
        _set_session_cookie(response, session.id)
        return response

    @app.get("/api/auth/oidc/status")
    async def auth_oidc_status(request: Request) -> dict:
        """OIDC state for the login screen and the setup wizard.

        Read-only and unauthenticated by necessity (it is consulted
        before anyone can sign in), and therefore deliberately bounded:
        it never accepts a target from the caller — the provider comes
        from the operator's own ``config/oidc.json`` — and discovery
        results are cached, success and failure alike, so an anonymous
        caller cannot turn this into a probe loop against the IdP.

        ``status`` is one of ``not_configured`` (no OIDC file; local
        auth is the whole story — healthy, not broken), ``configured``
        (usable), ``unreachable`` (provider did not answer), or
        ``misconfigured`` (settings or provider metadata unusable).
        Payload carries wiring and discovery metadata; the client secret
        is represented only by the *name* of the env var that holds it
        and a boolean saying whether that variable is set.
        """
        return _oidc(request).status()

    @app.get("/api/auth/oidc/config")
    async def auth_oidc_config(request: Request) -> dict:
        """Legacy alias of ``/api/auth/oidc/status``.

        Same payload, plus the flat keys the earlier shape used.
        ``/api/auth/oidc/login`` is the canonical entry point for a
        browser: the server owns the discovery-derived authorize URL, so
        no client needs to construct one (or to know PKCE exists).
        """
        result = _oidc(request).status()
        data = dict(result.get("data") or {})
        discovery = data.get("discovery") or {}
        payload = {
            "status": data.get("status", NOT_CONFIGURED),
            "login_available": bool(data.get("login_available")),
            "client_id": data.get("client_id"),
            "scopes": data.get("scopes") or [],
            "display_name": data.get("display_name"),
            "login_url": "/api/auth/oidc/login",
            "logout_url": "/api/auth/oidc/logout",
            "pkce": data.get("pkce"),
            "end_session_endpoint": discovery.get("end_session_endpoint"),
        }
        # Only published when we actually know it: a guessed endpoint is
        # worse than an absent one.
        if discovery.get("authorization_endpoint"):
            payload["authorization_endpoint"] = discovery["authorization_endpoint"]
        if not result["ok"]:
            return {
                "ok": False,
                "status": result["status"],
                "warnings": result.get("warnings") or [],
                "data": payload,
            }
        return {"ok": True, "data": payload}

    @app.get("/api/auth/oidc/login")
    async def auth_oidc_login(request: Request):
        """Start a sign-in: redirect to the provider's authorize URL.

        Authorization-code flow with PKCE (S256) and a nonce. The
        in-flight state — CSRF ``state``, PKCE verifier, nonce, and the
        exact ``redirect_uri`` the token exchange must replay — is held
        in a signed HttpOnly cookie, so the callback can verify the
        attempt belongs to this browser without storing anything
        server-side.
        """
        service = _oidc(request)
        redirect_uri = f"{str(request.base_url).rstrip('/')}/api/auth/oidc/callback"
        try:
            client = service.client()
            url, _pending, cookie = client.start_login(redirect_uri)
        except OIDCError as exc:
            return _failure_response(request, exc)
        response = RedirectResponse(
            url, status_code=303, headers={"Cache-Control": "no-store"}
        )
        response.set_cookie(
            FLOW_COOKIE,
            cookie,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=600,
        )
        return response

    @app.get("/api/auth/oidc/step-up")
    async def auth_oidc_step_up(request: Request, return_to: str = "/"):
        """"Confirm it's you" by signing in to the provider again.

        For people with no sign-in key (SSO or passkey only). Sends the
        browser to the provider with ``prompt=login`` and ``max_age=0``;
        the callback grants the usual 5-minute step-up to this session
        only if the same person signed in just now, then returns to
        ``return_to`` (a path on this site).
        """
        if not return_to.startswith("/") or return_to.startswith("//") or "\\" in return_to:
            return_to = "/"
        session_id = request.cookies.get(SESSION_COOKIE)
        session = auth.validate_session(session_id) if session_id else None
        if session is None:
            raise HTTPException(401, "sign in first")
        service = _oidc(request)
        redirect_uri = f"{str(request.base_url).rstrip('/')}/api/auth/oidc/callback"
        try:
            client = service.client()
            url, _pending, cookie = client.start_login(
                redirect_uri, step_up_for=session.principal_id, return_to=return_to
            )
        except OIDCError as exc:
            return _failure_response(request, exc)
        response = RedirectResponse(
            url, status_code=303, headers={"Cache-Control": "no-store"}
        )
        response.set_cookie(
            FLOW_COOKIE,
            cookie,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=600,
        )
        return response

    @app.post("/api/auth/oidc/link")
    async def auth_oidc_link(request: Request):
        """Start linking a provider sign-in to the signed-in person.

        Needed in multi mode, where a provider sign-in only works for an
        account it is linked to. The caller must be signed in, have
        confirmed it's them in the last few minutes (step-up), and call
        from this site (the ``Origin`` header must match). The person to
        link is carried in the signed flow cookie; the callback links
        the verified subject only if the same person is still signed in.
        """
        origin = request.headers.get("origin", "")
        if not origin or origin.rstrip("/") != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "link must be started from this site")
        session_id = request.cookies.get(SESSION_COOKIE)
        session = auth.validate_session(session_id) if session_id else None
        if session is None:
            raise HTTPException(401, "sign in first")
        if not session.has_step_up(session.principal_id):
            raise HTTPException(403, "confirm it's you first")
        service = _oidc(request)
        redirect_uri = f"{str(request.base_url).rstrip('/')}/api/auth/oidc/callback"
        try:
            client = service.client()
            url, _pending, cookie = client.start_login(
                redirect_uri, link_to=session.principal_id
            )
        except OIDCError as exc:
            return _failure_response(request, exc)
        response = RedirectResponse(
            url, status_code=303, headers={"Cache-Control": "no-store"}
        )
        response.set_cookie(
            FLOW_COOKIE,
            cookie,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=600,
        )
        return response

    @app.get("/api/auth/oidc/callback")
    async def auth_oidc_callback(
        request: Request,
        code: str = "",
        state: str = "",
        error: str = "",
        error_description: str = "",
    ):
        """Finish a sign-in: exchange the code, verify the id_token.

        Trust order matters. The ``state`` cookie is checked first
        (CSRF), then the authorization code is exchanged with the PKCE
        verifier, then the id_token's signature is verified against the
        provider's JWKS and its ``iss``/``aud``/``exp``/``nonce`` claims
        are validated. Only then is the verified ``sub`` handed to
        ``identity.py`` to resolve a Principal. Nothing about the
        provider's assertion is trusted before it is verified, and no
        id_token or access_token is ever stored.
        """
        service = _oidc(request)
        if error:
            # The provider itself refused (user cancelled, policy, ...).
            # and specific, without echoing its prose into a URL.
            _logger.warning(
                "oidc provider returned an error: %s (%s)",
                error,
                error_description[:200],
            )
            return _failure_response(
                request,
                OIDCLoginError(
                    f"the identity provider refused the sign-in: {error}",
                    error_code="oidc_provider_denied",
                ),
            )
        try:
            client = service.client()
            pending = client.read_pending(request.cookies.get(FLOW_COOKIE))
            if not state or not secrets.compare_digest(state, pending.state):
                raise OIDCLoginError(
                    "the sign-in response does not match the attempt this "
                    "browser started",
                    error_code="oidc_state_mismatch",
                )
            identity = client.complete_login(code, pending)
            if pending.step_up_for:
                current_id = request.cookies.get(SESSION_COOKIE) or ""
                current = auth.validate_session(current_id) if current_id else None
                if current is None or current.principal_id != pending.step_up_for:
                    raise OIDCLoginError(
                        "the person who asked to confirm is no longer signed in",
                        error_code="oidc_step_up_session_changed",
                        http_status=403,
                    )
                if not auth.grant_oidc_step_up(
                    current_id, identity.sub, identity.auth_time, time.time()
                ):
                    raise OIDCLoginError(
                        "that sign-in was not a fresh sign-in by the same person",
                        error_code="oidc_step_up_refused",
                        http_status=403,
                    )
                response = RedirectResponse(
                    pending.return_to or "/",
                    status_code=303,
                    headers={"Cache-Control": "no-store"},
                )
                response.delete_cookie(FLOW_COOKIE)
                return response
            if pending.link_to:
                current_id = request.cookies.get(SESSION_COOKIE)
                current = auth.validate_session(current_id) if current_id else None
                if current is None or current.principal_id != pending.link_to:
                    raise OIDCLoginError(
                        "the person who started linking is no longer signed in",
                        error_code="oidc_link_session_changed",
                        http_status=403,
                    )
                try:
                    auth.link_oidc(pending.link_to, identity.sub)
                except ValueError as _err:
                    raise OIDCLoginError(
                        "this sign-in is already linked to another account",
                        error_code="oidc_identity_in_use",
                        http_status=409,
                    ) from _err
            try:
                session = auth.login_oidc(
                    identity.sub,
                    display_name=identity.display_name,
                    groups=identity.groups,
                )
            except NoPrincipalError as _err:
                # Verified by the IdP but not mapped onto a local
                # principal: never silently mint an account. Fail closed
                # with a reason the operator can act on.
                raise OIDCLoginError(
                    "this identity is not mapped to a local account",
                    error_code="oidc_identity_not_mapped",
                    http_status=403,
                ) from _err
        except OIDCError as exc:
            return _failure_response(request, exc)

        response = RedirectResponse(
            "/", status_code=303, headers={"Cache-Control": "no-store"}
        )
        _set_session_cookie(response, session.id)
        response.delete_cookie(FLOW_COOKIE)
        return response

    @app.get("/api/auth/oidc/logout")
    async def auth_oidc_logout(request: Request):
        """End the local session, then the provider session if it offers
        RP-initiated logout.

        The local session is always invalidated first, so a provider
        that is unreachable can never leave a signed-in session behind.
        We do not retain the id_token, so no ``id_token_hint`` is sent —
        some providers then ask the person to confirm, which is the
        cost of not storing a credential we do not need.
        """
        session_id = request.cookies.get(SESSION_COOKIE)
        if session_id:
            auth.logout(session_id)
        post_logout = f"{str(request.base_url).rstrip('/')}{LOGIN_PATH}"
        target = post_logout
        try:
            client = _oidc(request).client()
            target = client.end_session_url(post_logout) or post_logout
        except OIDCError as exc:
            _logger.warning("oidc: provider logout unavailable (%s)", exc.detail)
        response = RedirectResponse(
            target, status_code=303, headers={"Cache-Control": "no-store"}
        )
        response.delete_cookie(SESSION_COOKIE)
        response.delete_cookie(FLOW_COOKIE)
        return response

    @app.post("/api/auth/logout")
    async def auth_logout(request: Request):
        """Logout: invalidate session.

        For an OIDC-created session the response also carries the
        provider's end-session URL, so a client can offer a real "sign
        out everywhere" instead of silently leaving the IdP session
        alive. The local session is gone either way.
        """
        session_id = request.cookies.get(SESSION_COOKIE)
        end_session_url = None
        if session_id:
            session = auth.validate_session(session_id)
            auth.logout(session_id)
            if session is not None and session.auth_method == "oidc":
                try:
                    client = _oidc(request).client()
                    end_session_url = client.end_session_url(
                        f"{str(request.base_url).rstrip('/')}{LOGIN_PATH}"
                    )
                except OIDCError as exc:
                    _logger.warning(
                        "oidc: provider logout unavailable (%s)", exc.detail
                    )
        response = JSONResponse(
            {
                "ok": True,
                "data": {
                    "end_session_url": end_session_url,
                },
            }
        )
        response.delete_cookie(SESSION_COOKIE)
        return response

    @app.get("/api/auth/session")
    async def auth_session(request: Request) -> dict:
        """Check current session.

        Deliberately free of provider calls: the UI polls this endpoint,
        so it must never block on an identity provider. Sign-in options
        come from ``/api/auth/oidc/status``.
        """
        session_id = request.cookies.get(SESSION_COOKIE)
        if not session_id:
            return {"ok": False, "status": "unauthenticated"}
        session = auth.validate_session(session_id)
        if not session:
            return {"ok": False, "status": "expired"}
        return {
            "ok": True,
            "data": {
                "principal_id": session.principal_id,
                "auth_method": session.auth_method,
                "has_step_up": session.has_step_up(session.principal_id),
                "step_up_methods": auth.step_up_methods(session.principal_id),
            },
        }

    @app.post("/api/auth/step-up")
    async def auth_step_up(request: Request) -> dict:
        """Elevate the current session for a bounded window.

        Step-up is a credential event, not a bare flag: the caller must
        re-present a credential (the instance token as a bearer header
        or ``{"token": ...}`` in the body) that resolves to the same
        principal the session belongs to. The resulting elevation is
        time-bounded and bound to that principal; it is the grant
        ``require_step_up`` consumes.

        An OIDC sign-in proves identity to the provider but does not by
        itself mint a step-up grant. People with no sign-in key use the
        other path, ``GET /api/auth/oidc/step-up``, a fresh provider
        sign-in whose callback grants the same window.
        """
        session_id = request.cookies.get(SESSION_COOKIE)
        if not session_id:
            raise HTTPException(401, "no session")
        token = ""  # nosec B105  # an empty starting value, not a credential
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header.removeprefix("Bearer ").strip()
        if not token:
            try:
                body = await request.json()
            except Exception:
                body = {}
            token = str((body or {}).get("token", "")).strip()
        session = auth.request_step_up(session_id, credential=token or None)
        if not session:
            # Either the session is unknown or the credential did not
            # match its principal. Fail closed without leaking which.
            raise HTTPException(403, "step-up credential invalid")
        return {
            "ok": True,
            "data": {
                "has_step_up": True,
                "expires_in": 300,
                "principal_id": session.principal_id,
            },
        }
