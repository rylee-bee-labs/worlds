"""Secure API. One core; CLI, dashboard, and AI tools all consume it.

Auth: bearer token (private-notes Pattern C). Fail-closed: no token
configured -> protected routes 503; wrong token -> 401. The token is
compared with hmac.compare_digest and never logged.
"""

import asyncio
import datetime as _dt
import json
import logging
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from . import crew, export, journal_gate, prefs, rooms_visits, voice
from . import people as people_mod
from . import records as records_mod
from . import sections as sections_mod
from .app import build_registry, load_world, save_world
from .briefing import SYSTEM_IDS, build_briefing
from .chat import (
    build_chat_messages,
    chat_once,
    chat_with_tools_loop,
    extract_proposal,
)
from .chat_context import build_ui_context, build_world_context
from .chat_history import ChatHistory
from .connection_manager import ConnectionManager
from .envelope import Result
from .journal import AuditRenderer, Journal
from .loop import daily
from .provider_schemas import (
    CAPABILITY_SCHEMAS,
    get_capability_schema,
    get_capability_schemas,
)
from .providers.lab_state import DEFAULT_LAB, LabState
from .providers.project_home import ProjectHomeSource
from .providers.registry import Registry
from .roles import PERMISSIONS, ROLES, can
from .rooms import IDEMPOTENCY_HEADER as ROOMS_IDEMPOTENCY_HEADER
from .rooms import REGISTRY_STATE_FILENAME as ROOMS_REGISTRY_STATE_FILENAME
from .rooms import STATE_FILENAME as ROOMS_STATE_FILENAME
from .rooms import RoomsService
from .source_control import (
    discover_repositories,
    enrich_all_repositories,
    repository_history,
    repository_status,
    status_all,
)
from .template_registry import TemplateRegistry
from .world import MutationDenied, World

_logger = logging.getLogger("personal_world.api")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirects are never followed during adapter tests: the test must
    report the server it was pointed AT, never wherever a redirect
    chain leads (open-redirect / SSRF hardening)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)

#: One rooms reader per app process: it caches each 15 s snapshot and
#: remembers last-seen times in memory across refreshes (contract room/0
#: rule 12). Tests replace this attribute with a MockTransport-backed
#: service; production reads the network.
_ROOMS = RoomsService()

#: A helper acting for another person sends this header naming that
#: person. It is honored ONLY on the two routes that ask for
#: ``see_needs_of`` / ``act_for`` (the rooms needs list and a room
#: action); any other route refuses it (403) so "act as that person"
#: can never leak into another surface.
HELPING_HEADER = "X-Worlds-Helping"

#: Where the helping header is allowed: the rooms needs list (GET) and a
#: room action (POST, with two path parameters). Nothing else.
_HELPING_ALLOWED: tuple[tuple[str, str], ...] = (
    ("GET", r"^/api/rooms$"),
    ("POST", r"^/api/rooms/[^/]+/actions/[^/]+$"),
)
_HELPING_ALLOWED_RE = tuple(
    (method, re.compile(pattern)) for method, pattern in _HELPING_ALLOWED
)


def _helping_route_allowed(method: str, path: str) -> bool:
    """True only for the routes that ask see_needs_of / act_for."""
    return any(
        method == allowed_method and pattern.match(path)
        for allowed_method, pattern in _HELPING_ALLOWED_RE
    )


def _valid_http_url(url: str) -> bool:
    """Absolute http(s) URL only — non-http schemes and relative
    URLs are refused (fail closed)."""
    try:
        parts = urllib.parse.urlparse(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def _probe_url(
    url: str,
    *,
    method: str = "GET",
    headers: dict | None = None,
) -> dict:
    """Shared adapter probe: URL-validated, redirects never followed.

    2xx/3xx count as reachable — a refused redirect surfaces the 3xx
    status itself (), instead of silently chasing it.
    """
    if not _valid_http_url(url):
        return {
            "status": "invalid_configuration",
            "detail": "URL must be an absolute http(s) address",
        }
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with _OPENER.open(req, timeout=10) as resp:
            return {"status": "healthy", "code": resp.status}
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400:
            return {"status": "healthy", "code": e.code, "redirected": True}
        return {"status": "unavailable", "code": e.code}
    except urllib.error.URLError as e:
        return {"status": "unavailable", "reason": getattr(e, "reason", e)}


def _cached_file(
    request: Request, path: Path, media_type: str | None, cache_private: bool = False
) -> Response:
    """Serve a static file with explicit revalidation, no `immutable`.

    UAT contract (owner directive, 2026-09-12): the browser must never
    hold an asset it cannot revalidate. The ETag is computed from the
    file's own stat (mtime+size, matching Starlette's formula) so
    If-None-Match can be answered synchronously with an explicit 304 —
    this starlette version sets the header only at send time and has
    no native If-None-Match handling. A file that vanishes or becomes
    unreadable mid-request is answered 404 with a logged error rather
    than a half-response or a crash.
    """
    try:
        stat_result = path.stat()
        response = FileResponse(
            path,
            media_type=media_type,
            stat_result=stat_result,
            headers={
                "Cache-Control": ("private" if cache_private else "public")
                + ", max-age=0, must-revalidate",
            },
        )
    except OSError as exc:
        _logger.error("static file unreadable %s: %s", path.name, exc)
        raise HTTPException(status_code=404, detail="file unavailable") from exc
    etag = response.headers.get("etag")
    if_none_match = request.headers.get("if-none-match")
    if etag and if_none_match:
        candidates = [
            tag.strip().removeprefix("W/") for tag in if_none_match.split(",")
        ]
        if etag in candidates:
            return Response(status_code=304, headers={"ETag": etag})
    return response


def _token() -> str | None:
    return os.environ.get("PW_API_TOKEN")


#: git's own default abbreviation, and the widest short form a person
#: can reasonably compare against `main` by eye.
_SHORT_COMMIT_LEN = 7
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def _commit() -> str | None:
    """Short SHA of the commit this build runs, or None.

    publish-image.yml passes the validated main commit as the PW_COMMIT
    build arg and the Dockerfile bakes it into the image env; /healthz
    reports the short form so Project Home can compare what is live
    against main. Local/dev runs carry no value → null. Only a hex SHA
    (7–40 chars) is trusted — anything else is reported as unknown,
    never echoed back.
    """
    value = os.environ.get("PW_COMMIT", "").strip()
    if _SHORT_COMMIT_LEN <= len(value) <= 40 and all(c in _HEX_DIGITS for c in value):
        return value[:_SHORT_COMMIT_LEN]
    return None


def _reconcile_boot_token(data_dir: Path) -> None:
    """Survive a restart after first-run setup (P2 auth groundwork).

    POST /api/setup writes the token the human created to
    ``<data_dir>/.env`` and into the live process env — but nothing
    read that file at boot, so the next container restart restored the
    compose-supplied ``PW_API_TOKEN`` and the wizard-created access
    code 401'd: the owner was locked out of their own world until the
    infra token came back. (Observed live twice, 2026-09-12.)

    Semantics: the setup file is the human-facing credential store —
    the token a person created through the setup flow outranks the
    deployment-infra env at boot. If both exist and differ, the file
    wins and the process env is updated so every reader (healthz,
    auth, identity bootstrap) sees one coherent token. An operator who
    wants the compose token back deletes the file (documented in
    OPERATIONS) — a deliberate, visible act, never a silent one.

    Malformed/missing-file handling: unreadable file → leave the
    environment untouched (fail toward the deployment's token, never
    toward lockout); a file with no PW_API_TOKEN line → same.
    """
    env_file = data_dir / ".env"
    if not env_file.is_file():
        return
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("PW_API_TOKEN=") and not line.startswith("#"):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value and value != os.environ.get("PW_API_TOKEN"):
                    os.environ["PW_API_TOKEN"] = value
                return
    except OSError:
        return


def _set_principal(request: Request, principal: Any, source: str) -> None:
    """Attach the resolved principal and its credential source.

    ``auth_source`` lets step-up (and diagnostics) reason about which
    credential event authenticated the request instead of re-deriving it
    from cookies and headers a second time.
    """
    request.state.principal = principal
    request.state.auth_source = source


def _current_session(request: Request):
    """The validated browser session for this request, if any."""
    session_id = request.cookies.get("pw_session")
    if not session_id:
        return None
    auth = getattr(request.app.state, "auth", None)
    if auth is None:
        return None
    return auth.validate_session(session_id)


def _step_up_authorized(request: Request, principal: Any = None) -> bool:
    """Single step-up entry point: one ordering, three documented mechanisms.

    1. **Canonical elevation** — a live, time-bounded session grant
       minted by ``POST /api/auth/step-up`` after re-presenting a
       credential, bound to the authenticated principal. This is the
       finish-line mechanism.

    2. **Local-owner exception** — the request peer is true loopback
       (127.0.0.1 / ::1 only). The owner is on the machine; this is a
       deliberate, documented local-development exception, not a general
       network trust rule (RFC1918 LAN addresses do not qualify).

    3. **Delegated proxy header** — ``X-PW-StepUp: 1`` from a consumer
       behind a reverse proxy that performs its own authentication.
       The header grant is only honored when the request ALSO carries
       ``X-PW-Proxy-StepUp-Secret`` matching ``PW_PROXY_STEPUP_SECRET``
       (timing-safe compare) — something only the trusted proxy knows,
       never the browser client. When that env is unset or the secret
       is missing/wrong, the grant is DENIED (fail closed).

       Deliberately NOT proof of fresh authentication either: the proxy
       vouches for its own authentication.
    """
    if principal is None:
        principal = getattr(request.state, "principal", None)
    principal_id = principal.id if principal is not None else None
    if principal is not None and getattr(principal, "read_only", False):
        # A read-only credential never elevates: no session grant, no
        # loopback peer, no delegated header.
        return False

    session = _current_session(request)
    if session is not None and session.has_step_up(principal_id):
        return True

    if _is_true_loopback(request):
        return True

    if request.headers.get("X-PW-StepUp") == "1":
        proxy_secret = os.environ.get("PW_PROXY_STEPUP_SECRET")
        presented = request.headers.get("X-PW-Proxy-StepUp-Secret", "")
        if (
            proxy_secret
            and presented
            and secrets.compare_digest(presented, proxy_secret)
        ):
            return True
        # Fail closed: unset operator env, missing header, or a wrong
        # secret all deny the delegated grant.
    return False


async def require_step_up(request: Request) -> None:
    await require_auth(request)
    principal = getattr(request.state, "principal", None)
    # Step-up is a human elevation: an agent principal never acquires
    # it, even with a delegated header or a loopback peer. Agents that
    # need a write go through person-approved proposal execution.
    if principal is not None and principal.kind == "agent":
        raise HTTPException(status_code=403, detail="step-up is person-only")
    if principal is not None and getattr(principal, "read_only", False):
        raise HTTPException(status_code=403, detail="read-only token: step-up is not available")
    if not _step_up_authorized(request, principal):
        raise HTTPException(status_code=403, detail="write requires step-up auth")


async def require_estate_custody(request: Request) -> None:
    """Whole-instance export/import: owner or admin only.

    Backup and restore move every person's data and the vault in one
    archive, so a valid elevation alone is not enough: the caller must
    also hold ``estate_secrets`` (owner and admin bundles only; members,
    supervised and guest accounts and agent keys never carry it). Mounted
    next to ``require_step_up`` as a route dependency, so a refusal
    happens before any one-time download token is created or consumed.
    """
    principal = getattr(request.state, "principal", None)
    if not can(principal, "estate_secrets"):
        raise HTTPException(status_code=403, detail="estate custody required")


def _is_true_loopback(request: Request) -> bool:
    """True ONLY for 127.0.0.1, ::1, and the literal hostname
    'localhost' resolved to one of those. Deliberately NOT
    ip.is_private: an RFC1918 LAN address is not localhost, and a
    forwarded request must present its own real client — the bypass
    never trusts proxy-invented peers."""
    client = request.client.host if request.client else ""
    if client in ("testclient",):
        # FastAPI TestClient connects over the ASGI transport; its peer
        # is the test process itself (loopback by design).
        return True
    import ipaddress as _ipa

    try:
        ip = _ipa.ip_address(client)
    except ValueError:
        return False
    return ip.is_loopback


#: Agent scopes that confine a token to one set of routes. A token whose
#: scopes include a confining one may call only those routes: "learning" is a
#: project's key for the person's learning memory (VEFR's Fróði), and
#: nothing else — not even reads elsewhere.
CONFINING_SCOPES: dict[str, tuple[str, ...]] = {
    "learning": ("/api/learning",),
    # An app's sticker key: it may only report stickers found in that app.
    "stickers": ("/api/stickers/found",),
    # The journal gate (owner design, 2026-09-27): a closed-enum-only
    # door onto the private Journal. This scope reaches ONLY the gate
    # route below — never /api/journal or /api/recall, which stay
    # person-only via _require_person regardless of any scope a token
    # holds.
    "journal_gate": ("/api/journal/gate",),
}


def _confined_out(principal, path: str) -> bool:
    """True when an agent's confining scopes don't cover this path."""
    if principal is None or getattr(principal, "kind", "person") != "agent":
        return False
    scopes = set(getattr(principal, "scopes", ()) or ())
    # Any confining scope confines the whole key: adding an ordinary
    # scope such as "read" must not widen a project key to the estate.
    confining = scopes & set(CONFINING_SCOPES)
    if not confining:
        return False
    allowed = tuple(p for s in confining for p in CONFINING_SCOPES[s])
    return not any(path == p or path.startswith(p + "/") for p in allowed)


#: Reads a read-only viewer credential may never make: secret values and
#: names, raw personal material (journal, recall, chat history, records,
#: learning, world/backup exports), whole-instance archives, credential
#: administration and lab/infra configuration. Prefix match on path
#: segments; everything else that is a GET/HEAD/OPTIONS is allowed, so a
#: screen walk can see the app without holding any secret or raw entry.
VIEWER_DENIED_PREFIXES: tuple[str, ...] = (
    "/api/vault",
    "/api/secrets",
    "/api/lab/secrets",
    "/api/lab/settings",
    "/api/recall",
    "/api/journal",
    "/api/memory",
    "/api/records",
    "/api/learning",
    "/api/backup",
    "/api/worlds",
    "/api/exports",
    "/api/identity/agents",
    "/api/identity/users",
    "/api/identity/viewers",
    "/api/people/invites",
    "/api/push/subscriptions",
    "/api/connections/config",
)

#: Narrow, named exceptions to the prefixes above (exact path match only):
#: structure a viewer may read inside an otherwise denied area.
#: - ``/api/records/categories``: category names, counts and the locked flag,
#:   never a record's contents.
VIEWER_ALLOWED_EXACT: tuple[str, ...] = ("/api/records/categories",)

#: Chat history is a mixed route (structure plus what was said). A viewer
#: gets the structure only, by allow-list: each entry keeps just these keys,
#: so a content field added later is omitted by default.
VIEWER_CHAT_ENTRY_KEYS = ("ts", "role")

_VIEWER_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _viewer_refusal(principal, method: str, path: str) -> str | None:
    """Why a read-only viewer may not make this request, or ``None``."""
    if principal is None or not getattr(principal, "read_only", False):
        return None
    if method.upper() not in _VIEWER_SAFE_METHODS:
        return "read-only token: this credential can only read"
    if path in VIEWER_ALLOWED_EXACT:
        return None
    if any(path == p or path.startswith(p + "/") for p in VIEWER_DENIED_PREFIXES):
        return "read-only token: this route is not available to a read-only credential"
    return None


async def require_auth(request: Request) -> None:
    await _require_auth_base(request)
    refusal = _viewer_refusal(
        getattr(request.state, "principal", None), request.method, request.url.path
    )
    if refusal:
        raise HTTPException(status_code=403, detail=refusal)
    if _confined_out(getattr(request.state, "principal", None), request.url.path):
        raise HTTPException(status_code=403, detail="this key only reaches its own routes")


async def _require_auth_base(request: Request) -> None:
    """Gate + canonical principal resolution (the single entry point).

    Every accepted credential — bearer token, browser session (local or
    OIDC), or the explicit loopback development bypass — resolves to
    exactly one ``Principal`` on ``request.state.principal`` before
    handler code runs. Precedence is deliberate and documented:

    1. development bypass (opt-in, true loopback only),
    2. an explicit ``Authorization: Bearer`` credential,
    3. a ``pw_session`` cookie (re-resolved against the current enabled
       identity records, so disabling a user revokes their browser
       session like their token),
    4. otherwise fail closed: 503 when the instance has no credential
       store configured at all, 401 when it does but nothing matched.

    In "single" mode the bootstrap "primary" person is the only
    principal; "multi" resolves hashed user tokens from the local
    identity store. The session never becomes a parallel credential
    system: it lands on the same Principal a bearer request produces.
    """
    from .identity import (
        NoPrincipalError,
        dev_bypass_enabled,
        dev_bypass_principal,
        resolve_principal,
        resolve_session_principal,
    )

    identity = getattr(request.app.state, "identity", None)
    mode = identity["mode"] if identity else "single"
    store = identity["store"] if identity else None
    instance_token = _token()

    # 1. Explicit loopback development bypass (never implicit).
    if dev_bypass_enabled() and _is_true_loopback(request):
        _set_principal(request, dev_bypass_principal(), "dev-bypass")
        return

    # 2. Explicit bearer credential takes precedence over a cookie.
    header = request.headers.get("Authorization", "")
    supplied = header.removeprefix("Bearer ").strip()
    if supplied:
        if mode == "multi" or instance_token:
            try:
                principal = resolve_principal(
                    supplied, store, mode, instance_token, allow_read_only=True
                )
            except NoPrincipalError as _err:
                raise HTTPException(status_code=401, detail="unauthorized") from _err
            _set_principal(request, principal, principal.source)
            return
        # A bearer was presented but no credential store is configured:
        # fail closed instead of silently falling through to a cookie.
        raise HTTPException(status_code=503, detail="auth not configured")

    # 3. Browser session (local or OIDC), same entry point.
    session = _current_session(request)
    if session is not None:
        try:
            principal = resolve_session_principal(
                session.principal_id, store, mode, session.auth_method
            )
        except NoPrincipalError as _err:
            raise HTTPException(status_code=401, detail="unauthorized") from _err
        _set_principal(request, principal, principal.source)
        return

    # 4. Nothing usable.
    if not instance_token and mode != "multi":
        raise HTTPException(status_code=503, detail="auth not configured")
    raise HTTPException(status_code=401, detail="unauthorized")


def create_app(data_dir: Path | None = None, config_dir: Path | None = None) -> FastAPI:
    data_dir = Path(data_dir or os.environ.get("PW_DATA_DIR", "./data"))
    config_dir = Path(config_dir or os.environ.get("PW_CONFIG_DIR", "./config"))

    # Room health (last-seen / last-declared-status) persists under the
    # data dir so an unreachable room survives a restart with its real
    # last-seen time (room/0 rule 12). The last-known-good registry
    # payload persists next to it (rooms-registry.json) so a registry
    # outage still serves the estate the registry last named. The service
    # stays the one module-level reader; it just learns where to persist.
    _ROOMS.set_state_path(data_dir / ROOMS_STATE_FILENAME)
    _ROOMS.set_registry_state_path(data_dir / ROOMS_REGISTRY_STATE_FILENAME)

    # Vault: one instance per app, survives across requests
    from .vault import Vault

    _vault = Vault(data_dir / "vault.enc")
    from .secret_resolver import set_vault

    set_vault(_vault)
    # Serving boundary: the React rebuild IS the interface (owner
    # decision 2026-09-22). It is served at `/` by app_router (mounted at
    # the END of create_app, after every API route); the retired vanilla
    # Station and the /vnext side-by-side are gone — those paths only
    # redirect. `/login` and `/setup` stay server-rendered
    # (login_page.py / setup_wizard.py).

    # Identity entry point state (issue #8 phase 0/1, per multi-user review
    # 2026-09-09): local users as trust root, PW_IDENTITY_MODE picks
    # single (bootstrap-primary bypass) or multi (hashed-token users).
    # Boot-time token reconciliation FIRST so every reader below sees
    # the setup-created credential, not the stale infra one.
    _reconcile_boot_token(data_dir)
    from .identity import IdentityStore, dev_bypass_enabled

    _identity_mode = os.environ.get("PW_IDENTITY_MODE", "single")
    _identity_store = IdentityStore(data_dir)
    _app_instance_token = _token()
    # People screens' state (step 2): invites, helper grants, supervised
    # limits and the helper log. Identity-level metadata (like
    # users.json), never personal content. See people.py.
    _invites = people_mod.InviteStore(data_dir)
    _helper_store = people_mod.HelperStore(data_dir)
    _limits_store = people_mod.LimitsStore(data_dir)
    _helper_log = people_mod.HelperLog(data_dir)
    # Roles (owner-approved 2026-09-26): heal pre-roles records once at
    # boot (primary -> owner, legacy admin scope -> admin, else member).
    # Readers also fall back through identity.role_for_record, so a store
    # that cannot be written still authorizes correctly.
    try:
        _identity_store.migrate_roles()
    except Exception as exc:  # never block boot on this; fail toward reads
        _logger.warning("role migration skipped: %s", exc)
    # Temporary dev ergonomics: explicit opt-in, loopback-only. The
    # startup log line is the visible "this is on" state (human
    # reliability contract: visible state, not a silent default).
    if dev_bypass_enabled():
        _logger.warning(
            "DEV AUTH BYPASS ACTIVE — LOOPBACK ONLY "
            "(PW_DEV_AUTH_BYPASS=1; never for production or LAN access)"
        )
    world_path = data_dir / "world.json"
    journal = Journal(data_dir / "journal.ndjson")

    # Journal gate rate limit: in-process, per-caller sliding window
    # (same shape as PushHub.rate_limited). A restart clears it, which
    # is fine for a courtesy limit on a narrow, closed-enum route.
    _gate_rate_lock = threading.Lock()
    _gate_rate: dict[str, deque] = {}
    _GATE_RATE_LIMIT_PER_MINUTE = 20

    def _gate_rate_limited(caller_id: str) -> bool:
        now = time.monotonic()
        with _gate_rate_lock:
            window = _gate_rate.setdefault(caller_id, deque())
            while window and now - window[0] >= 60:
                window.popleft()
            if len(window) >= _GATE_RATE_LIMIT_PER_MINUTE:
                return True
            window.append(now)
            return False

    from .model import JournalKind

    app = FastAPI(title="Project Worlds", version="0.2.0")

    @app.middleware("http")
    async def _helping_scope_guard(request: Request, call_next):
        """The helping header is scoped to the rooms routes only.

        A helper may act for a person on the rooms needs list and on a
        room action; anywhere else the header is refused with a plain
        message, so "act as that person" can never reach a journal, a
        world or a secret. The grant itself is checked in the handler.
        """
        if request.headers.get(HELPING_HEADER) and not _helping_route_allowed(
            request.method.upper(), request.url.path
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "status": "forbidden",
                    "detail": (
                        "Helping only covers seeing needs and acting in rooms."
                    ),
                    "warnings": [
                        "Helping only covers seeing needs and acting in rooms."
                    ],
                },
            )
        return await call_next(request)

    # issue #8, phase 0: the identity entry point state is on app.state so
    # single-mode behavior is byte-identical and multi-mode lights up
    # without changing how the client calls the API.
    # Multi-mode bootstrap: the instance token remains the primary
    # person's credential so enabling multi mode never locks the
    # operator out. First-run in multi continues to work.
    if _identity_mode == "multi":
        try:
            _identity_store.legacy_primary(_token())
        except Exception:  # nosec B110  # legacy migration probe: never a reason to fail the request
            pass

    app.state.identity = {
        "mode": _identity_mode,
        "store": _identity_store,
        "instance_token": _app_instance_token,
    }

    # --- Native auth (session-cookie + OIDC) ---
    from .auth import AuthManager
    from .auth_routes import register_auth_routes

    # Pass the identity entry point state so browser local/OIDC logins resolve
    # to the same Principal the bearer path produces (D1 convergence).
    _auth = AuthManager(data_dir, config_dir, identity=app.state.identity)
    register_auth_routes(app, _auth)
    app.state.auth = _auth

    # --- First-run setup wizard (server-rendered, dependency-free) ---
    # Registered BEFORE the SPA routes so /setup wins during first-run.
    from .setup_wizard import register_setup_wizard, setup_needed

    register_setup_wizard(
        app, data_dir=data_dir, config_dir=config_dir, journal=journal
    )

    # --- Sign-in page (server-rendered, dependency-free) ---
    # The interface has no sign-in view of its own; login_page.py serves
    # it. Registered before the interface router so an unauthenticated
    # visit to / lands here.
    from .login_page import register_login_page

    register_login_page(app, data_dir=data_dir)

    # --- Invite accept page (server-rendered, signed-out like /login) ---
    # `/invite#<code>`: the invite code rides in the URL fragment and
    # never reaches the server; the page posts it to the existing
    # POST /api/invites/accept. invite_page.py copies the login serving
    # pattern (no-store static file, first-run redirects to /setup).
    from .invite_page import register_invite_page

    register_invite_page(app, data_dir=data_dir)

    # (The interface itself is mounted at the end of create_app —
    # app_router must come last so it never shadows an API route.)

    # --- Encrypted worlds backup/restore (SOS hatch, owner decision #4) ---
    # Step-up gated; fails closed without the crypto extra. Registered after
    # the Station so its /api/worlds/* routes sit with the other gated writes.
    from .worlds_backup import register_worlds_backup

    register_worlds_backup(
        app,
        data_dir=data_dir,
        config_dir=config_dir,
        step_up=require_step_up,
        owner_gate=require_estate_custody,
    )

    # --- Durable brain-proposal store (D3) ---
    # Server-held proposals + approval evidence persist to the data dir
    # so an owner approval survives a restart and is never re-derived
    # from a model argument.
    from .tool_registry import configure_proposal_store

    configure_proposal_store(data_dir, journal=journal)

    # --- Setup & Login ---

    @app.get("/healthz")
    async def healthz() -> dict:
        token = _token()
        # Shared first-run predicate (setup wizard): marker absent OR
        # FORCE_SETUP=1 — one meaning everywhere.
        first_run = setup_needed(data_dir)
        from .identity import dev_bypass_enabled

        return {
            "ok": True,
            "auth_configured": token is not None,
            "setup_needed": first_run,
            # Dev-only visibility so the SPA can show (and tests can
            # assert) that loopback dev bypass is on. Always false in
            # production defaults.
            "dev_bypass": dev_bypass_enabled(),
            # What this build is running (see _commit). A public repo's
            # commit is safe on this public route; null when unknown.
            "commit": _commit(),
        }

    @app.get("/api/setup/status")
    async def setup_status() -> dict:
        """Check if first-run setup is needed (missing marker, or a
        deliberate FORCE_SETUP=1 re-open)."""
        complete = not setup_needed(data_dir)
        return {"ok": True, "data": {"complete": complete}}

    @app.post("/api/setup")
    async def setup(request: Request) -> dict:
        """First-run setup: create API token and vault passphrase.

        Loopback-only (fail closed): this endpoint mints the instance
        credential, so a remote peer cannot take over a fresh,
        unauthenticated instance through this route. GET state routes
        stay readable.
        """
        if not _is_true_loopback(request):
            raise HTTPException(
                status_code=403,
                detail="setup is only available from the local machine",
            )
        if (data_dir / "setup-complete").exists():
            raise HTTPException(status_code=409, detail="setup already complete")
        body = await request.json()
        token = body.get("token", "").strip()
        if not token or len(token) < 8:
            raise HTTPException(status_code=400, detail="token must be >= 8 chars")
        # Write token to env file for the container to pick up.
        # Mirrors setup_wizard._write_env_token: O_CREAT|O_EXCL|0600 on
        # create; a pre-existing file is never world-readable either
        # (chmod after write covers a file created earlier with loose
        # perms). Never truncate other operators' content.
        env_path = data_dir / ".env"
        if env_path.exists():
            with env_path.open("a", encoding="utf-8") as fh:
                fh.write(f"PW_API_TOKEN={token}\n")
        else:
            fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(f"PW_API_TOKEN={token}\n")
        try:
            os.chmod(env_path, 0o600)
        except OSError:
            pass  # best-effort hardening; never fail setup over umask policy
        os.environ["PW_API_TOKEN"] = token
        # Mark setup complete
        (data_dir / "setup-complete").write_text("ok")
        # Initialize vault if passphrase provided
        vault_pass = body.get("vault_passphrase", "").strip()
        vault_initialized = False
        if vault_pass:
            r = _vault.unlock(vault_pass)
            if r.ok:
                _vault._save()
                vault_initialized = True
            else:
                # Vault unlock failed (e.g., no cryptography package).
                # Token setup still succeeds — vault is optional.
                _logger.warning("vault init failed: %s", r.warnings)
        return {
            "ok": True,
            "data": {"token_set": True, "vault_initialized": vault_initialized},  # nosec B105  # "token_set" is a boolean flag, not a credential
        }

    def _state() -> tuple[World, Registry]:
        world = load_world(world_path)
        registry = build_registry(
            world,
            Registry(),
            config_dir,
            vault=_vault,
            journal=journal,
            data_dir=data_dir,
        )
        return world, registry

    def _principal(request: Request):

        return getattr(request.state, "principal", None)

    def _scoped_path(principal, kind: str) -> Path:
        """Canonical per-principal data path (single entry point for storage
        partitioning — identity.principal_scoped_path, decision #13).

        Single mode (and background entry points with no principal) resolves to
        the legacy instance paths current installs already use; multi
        mode resolves each person — and each agent via its owner — into
        data/users/<id>/. See docs/IDENTITY-BOUNDARY.md.
        """
        from .identity import principal_scoped_path

        return principal_scoped_path(data_dir, principal, kind, mode=_identity_mode)

    def _journal_target(journal_path: Path) -> Journal:
        """The Journal for a resolved journal path (the shared instance
        journal when the path IS the legacy one — no second writer)."""
        return journal if journal_path == journal.path else Journal(journal_path)

    def _user_paths(request: Request) -> tuple[Path, Path]:
        """Per-user world/journal paths for the caller (multi mode).

        Returns the _global_ paths in single mode: the bootstrap
        person's state remains the instance state until multi mode is
        enabled (PW_IDENTITY_MODE multi), keeping single-user behavior
        byte-identical.
        """
        identity = getattr(request.app.state, "identity", {})
        if identity.get("mode") != "multi":
            return world_path, journal.path
        principal = getattr(request.state, "principal", None)
        if principal is None:
            raise HTTPException(status_code=409, detail="principal not resolved")
        return (_scoped_path(principal, "world"), _scoped_path(principal, "journal"))

    def _state_for(request: Request) -> tuple[World, Registry, Path]:
        """World + registry + the caller's own journal. Multi mode
        loads the caller-person's tree; single mode uses the
        bootstrap-shared paths (byte-identical legacy behavior)."""
        uw, uj = _user_paths(request)
        world = load_world(uw)
        registry = build_registry(
            world,
            Registry(),
            config_dir,
            vault=_vault,
            journal=journal,
            data_dir=data_dir,
        )
        return world, registry, uj

    def _journal_at(uj: Path) -> Journal:
        """The Journal object for a resolved journal path (the shared
        instance journal when it is that path)."""
        return journal if uj == journal.path else Journal(uj)

    def _proposal_store(request: Request):
        """The proposal store owning the CALLER's tree (decision #13).

        Single mode / legacy path resolves to the same instance-global
        store configure_proposal_store manages, so the chat tool loop
        and the /api/proposals lifecycle can never diverge.
        """
        from .tool_registry import proposal_store_for

        principal = _principal(request)
        return proposal_store_for(
            _scoped_path(principal, "proposals"),
            journal=_journal_target(_scoped_path(principal, "journal")),
        )

    @app.get("/api/status", dependencies=[Depends(require_auth)])
    async def status() -> dict:
        world, registry = _state()
        s = world.summary()
        # `capabilities` here is the provider capability-STATUS map (the
        # product contract the Station reads). The world's own
        # declared-capability COUNT travels as `declared_capabilities`
        # from world.summary() — one key, one meaning.
        s["capabilities"] = registry.status_map()
        s["actors"] = [a.model_dump(mode="json") for a in registry.actors()]
        return {"ok": True, "status": "healthy", "data": s}

    @app.get("/api/daily", dependencies=[Depends(require_auth)])
    async def daily_view(request: Request) -> dict:
        """Present the daily digest. Read-only: a page view never
        journals observations or records facts (that is the POST)."""
        world, registry, uj = _state_for(request)
        result = daily(world, registry, _journal_at(uj), record=False)
        return result.model_dump(mode="json")

    @app.post("/api/daily", dependencies=[Depends(require_auth)])
    async def daily_run(request: Request) -> dict:
        """Run the daily loop for real: journal observations, record
        capability facts, flag drift, save the world."""
        world, registry, uj = _state_for(request)
        result = daily(world, registry, _journal_at(uj), record=True)
        save_world(world, _user_paths(request)[0])
        return result.model_dump(mode="json")

    @app.get("/api/journal", dependencies=[Depends(require_auth)])
    async def journal_view(request: Request, n: int = 20, hide: str = "") -> dict:
        _require_person(getattr(request.state, "principal", None))
        _, _, uj = _state_for(request)
        target = journal if uj == journal.path else Journal(uj)
        # Calm view: each chain's CURRENT version only (superseded
        # originals stay in history + audit; the correction workflow
        # links them). n is clamped 1..500 like chat history.
        # ``hide`` = comma-separated kinds left out before the last n are
        # taken (e.g. settings_change: an import writes one per record).
        hidden = frozenset(k.strip() for k in hide.split(",") if k.strip())
        events = target.current_events(min(max(n, 1), 500), exclude_kinds=hidden)
        return {"ok": True, "data": [e.model_dump(mode="json") for e in events]}

    @app.get("/api/journal/last", dependencies=[Depends(require_auth)])
    async def journal_last(request: Request) -> dict:
        """Read-only: the caller's most recent CURRENT journal entry.

        The deep-link contract for the daily home loop's "Resume —
        yesterday's thread" beat (TRUE-NORTH): one deterministic answer
        with every model off, safe for Overview to link to. Never
        mutates anything. An empty journal is an ``entry: null``,
        not a 404 and not a fabrication. Superseded originals never
        surface. The contract is the CALM-VIEW TAIL: the answer always
        equals the newest entry GET /api/journal shows (same kinds, same
        ordering — a correction ACT appends the correction and then its
        APPROVAL audit line, and whichever is newest IS the last entry;
        consumers wanting narrative-only may filter by ``kind``).
        Person-only, caller-scoped, the same entry point as every other journal
        read.
        """
        _require_person(getattr(request.state, "principal", None))
        _, _, uj = _state_for(request)
        target = journal if uj == journal.path else Journal(uj)
        events = target.current_events(1)
        entry = events[-1] if events else None
        return {
            "ok": True,
            "status": "healthy",
            "data": {
                "entry": entry.model_dump(mode="json") if entry is not None else None,
            },
        }

    @app.post("/api/journal", dependencies=[Depends(require_auth)])
    async def journal_note(request: Request) -> dict:
        _require_person(getattr(request.state, "principal", None))
        """Write a personal note to the caller's own journal.

        Body: {"text": "<1-2000 chars>"}. Stored when the user is in
        multi mode; shared journal in single mode.
        """
        body = await request.json()
        text = (body or {}).get("text", "").strip()
        if not text or len(text) > 2000:
            raise HTTPException(status_code=422, detail="text must be 1-2000 chars")
        _, _, uj = _state_for(request)
        target = journal if uj == journal.path else Journal(uj)
        target.record(kind=JournalKind.OBSERVATION, summary=text, source="user")
        return {"ok": True, "data": {"written": len(text)}}

    # ── Journal DRAFTS — the lining rescue (owner D15: "Kept safe, synced") ──
    # Debounced client writes land here so a stopped mid-thought day
    # resumes on ANY device. Deliberate contract choices (spec:
    # DRAFT-SYNC-SPEC-2026-09-20): NOT elevation-gated (a draft mutates
    # nothing a publish doesn't), response NEVER echoes draft text,
    # storage rides the single per-principal entry point (decision #13).
    _DRAFT_MAX = 100_000

    def _draft_file(request: Request) -> Path:
        return _scoped_path(request.state.principal, "journal_draft")

    @app.put("/api/journal/draft", dependencies=[Depends(require_auth)])
    async def journal_draft_put(request: Request) -> dict:
        _require_person(getattr(request.state, "principal", None))
        body = await request.json()
        text = str((body or {}).get("text", ""))
        if len(text) > _DRAFT_MAX:
            raise HTTPException(status_code=422, detail="draft exceeds 100000 chars")
        path = _draft_file(request)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "text": text,
            "entry_id": str((body or {}).get("entry_id", ""))[:64],
            "device": str((body or {}).get("device", ""))[:64],
            "updated_at": stamp,
        }))
        tmp.chmod(0o600)
        os.replace(tmp, path)  # atomic: a crash never leaves half a draft
        return {"ok": True, "data": {"saved_at": stamp, "length": len(text)}}

    @app.get("/api/journal/draft", dependencies=[Depends(require_auth)])
    def journal_draft_get(request: Request) -> dict:
        _require_person(getattr(request.state, "principal", None))
        path = _draft_file(request)
        if not path.exists():
            return {"ok": True, "data": {"text": None, "updated_at": None}}
        d = json.loads(path.read_text())
        return {"ok": True, "data": {
            "text": d["text"], "entry_id": d["entry_id"],
            "device": d["device"], "updated_at": d["updated_at"],
            "length": len(d["text"]),
        }}

    @app.delete("/api/journal/draft", dependencies=[Depends(require_auth)])
    def journal_draft_delete(request: Request) -> dict:
        _require_person(getattr(request.state, "principal", None))
        _draft_file(request).unlink(missing_ok=True)
        return {"ok": True, "data": {"cleared": True}}

    # ── Journal EDIT-PAIR capture v0 (B5; lineage: DRAFT-SYNC-SPEC
    # §capture, Meeting #4 §B11 — Sol's nine fields). The capture
    # ENDPOINT only, no UI: one BOT→Rylee edit pair per NDJSON line on
    # the same per-principal scoped entry point as drafts. Same rules as the
    # draft entry point: the response reports {stored} and NEVER echoes
    # content, capture is automatic and therefore NOT an elevation
    # event (gate: none beyond authentication), and every field rides a
    # size cap so one render cannot bloat a personal store.
    _PAIR_TEXT_MAX = 20_000
    _PAIR_TAG_MAX = 64
    _PAIR_TAGS_MAX = 32

    @app.post("/api/journal/edit-pair", dependencies=[Depends(require_auth)])
    async def journal_edit_pair(request: Request) -> dict:
        _require_person(getattr(request.state, "principal", None))
        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="body must be an object")

        def _text(value: object) -> str:
            return str(value or "")[:_PAIR_TEXT_MAX]

        original = str(body.get("original") or "")
        edited = str(body.get("edited") or "")
        if not original.strip() or not edited.strip():
            raise HTTPException(
                status_code=422, detail="original and edited are required"
            )
        if (
            len(original) > _PAIR_TEXT_MAX
            or len(edited) > _PAIR_TEXT_MAX
            or len(str(body.get("diff") or "")) > _PAIR_TEXT_MAX
        ):
            raise HTTPException(
                status_code=422, detail=f"text fields exceed {_PAIR_TEXT_MAX} chars"
            )

        def _tags(value: object) -> list[str]:
            if value is None:
                return []
            if not isinstance(value, list) or len(value) > _PAIR_TAGS_MAX:
                raise HTTPException(
                    status_code=422,
                    detail=f"tag lists must be arrays of at most {_PAIR_TAGS_MAX} strings",
                )
            return [str(t)[:_PAIR_TAG_MAX] for t in value]

        warmth = body.get("warmth")
        if warmth is not None:
            if not isinstance(warmth, int) or isinstance(warmth, bool) \
                    or not 1 <= warmth <= 7:
                raise HTTPException(
                    status_code=422, detail="warmth must be an integer 1-7"
                )

        provenance = body.get("model_provenance")
        record = {
            # Exactly the nine §capture lineage fields, in spec order.
            # Absent optionals stay accurate: null / [] — never invented.
            "original": original,
            "edited": edited,
            "diff": _text(body.get("diff")) or None,
            "timestamp": str(body.get("timestamp") or "")[:64]
            or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "message_kind": str(body.get("message_kind") or "")[:64] or None,
            "context": _tags(body.get("context")),
            "active_packs": _tags(body.get("active_packs")),
            "warmth": warmth,
            "model_provenance": str(provenance)[:128] if provenance else None,
        }
        path = _scoped_path(request.state.principal, "journal_edit_pairs")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        path.chmod(0o600)  # personal data, private bits (same rule as drafts)
        # Anti-echo, the draft-entry point rule: report, never quote.
        return {"ok": True, "data": {"stored": True}}

    # ── Journal correction workflow (second propose→approve→act
    # workflow; same trust model as the repository-status refresh).
    # The UI proposes + explains + collects explicit approval BEFORE
    # this endpoint is called; the endpoint is the ACT (step-up
    # gated, same as every write). Append-only: the original entry is
    # never rewritten — the corrected entry links back via
    # `supersedes` and readers derive currency from those links.
    # Idempotency: a retry carrying the same target and the same
    # corrected text returns the ALREADY-CURRENT entry instead of
    # appending a duplicate (double-click/retry/refresh safe). ──
    @app.post("/api/journal/supersede", dependencies=[Depends(require_step_up)])
    async def journal_supersede(request: Request) -> dict:
        _require_person(getattr(request.state, "principal", None))
        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="body must be an object")
        target_ts = str(body.get("supersedes") or "").strip()
        corrected = str(body.get("text") or "").strip()
        reason = str(body.get("reason") or "").strip()
        # Provenance only: how this correction was DRAFTED. The value
        # is rendered in the audit event; it never grants or widens
        # authority (this endpoint stays step-up gated; the approval is
        # always the explicit human action behind the step-up call).
        drafted_by = str(body.get("drafted_by") or "").strip() or "the Journal screen"
        if drafted_by not in (
            "the Journal screen",
            "Personal World (assistant draft)",
        ):
            drafted_by = "the Journal screen"
        if not target_ts or not corrected:
            raise HTTPException(
                status_code=422,
                detail="supersedes (entry timestamp) and text are required",
            )
        if len(corrected) > 2000:
            raise HTTPException(status_code=422, detail="text must be 1-2000 chars")
        _, _, uj = _state_for(request)
        target = journal if uj == journal.path else Journal(uj)
        old = target.by_ts(target_ts)
        if old is None:
            # Missing/invalid entry: nothing changes; say so.
            return {
                "ok": False,
                "status": "not_configured",
                "warnings": [f"no journal entry found at {target_ts}"],
            }
        # Idempotent retry: the target's current replacement already
        # says exactly this → return it; no duplicate append.
        for later in target.events():
            if later.supersedes == old.ts:
                if later.summary == corrected:
                    return {
                        "ok": True,
                        "status": "healthy",
                        "data": {
                            "current": later.model_dump(mode="json"),
                            "superseded": old.model_dump(mode="json"),
                            "already_applied": True,
                        },
                    }
                break  # a different correction owns it → conflict below
        try:
            current, audit = target.supersede(
                target_ts,
                corrected,
                reason or None,
                proposed_by=drafted_by,
            )
        except ValueError as exc:
            return {
                "ok": False,
                "status": "unavailable",
                "warnings": [str(exc)],
            }
        return {
            "ok": True,
            "status": "healthy",
            "data": {
                "current": current.model_dump(mode="json"),
                "superseded": old.model_dump(mode="json"),
                "audit": audit.model_dump(mode="json"),
                "already_applied": False,
            },
        }

    @app.get("/api/journal/history", dependencies=[Depends(require_auth)])
    async def journal_history(request: Request, ts: str) -> dict:
        """Full correction chain for one entry (progressive disclosure
        backing store): oldest → newest, with reasons."""
        _, _, uj = _state_for(request)
        target = journal if uj == journal.path else Journal(uj)
        entry = target.by_ts(ts)
        if entry is None:
            return {
                "ok": False,
                "status": "not_configured",
                "warnings": [f"no journal entry found at {ts}"],
            }
        chain = target.history_of(entry)
        return {
            "ok": True,
            "status": "healthy",
            "data": {"entries": [e.model_dump(mode="json") for e in chain]},
        }

    @app.get("/api/journal/audit", dependencies=[Depends(require_auth)])
    async def journal_audit(request: Request) -> dict:
        _, _, uj = _state_for(request)
        target = journal if uj == journal.path else Journal(uj)
        return {"ok": True, "data": {"text": AuditRenderer().render(target)}}

    def _journal_gate_model_fn():
        """Real model when one is configured (PW_JOURNAL_GATE_MODEL_URL),
        else the deterministic mock. Env is read per-call so tests can
        set/clear it per-test; this is a courtesy config lookup, not a
        security boundary — ``journal_gate._validate`` enforces the
        schema regardless of which model_fn ran."""
        base_url = os.environ.get("PW_JOURNAL_GATE_MODEL_URL", "").strip()
        if not base_url:
            return journal_gate.mock_model, "mock"
        model_name = os.environ.get("PW_JOURNAL_GATE_MODEL_NAME", "resident-chat")

        def _bound(ask, hits):
            return journal_gate.real_model(ask, hits, base_url=base_url, model=model_name)

        return _bound, "real"

    def _journal_gate_denylist_path(request: Request) -> Path:
        return _scoped_path(request.state.principal, "journal_gate_denylist")

    @app.post("/api/journal/gate", dependencies=[Depends(require_auth)])
    async def journal_gate_ask(request: Request) -> dict:
        """The narrow, closed-enum door onto the private Journal (owner
        design, 2026-09-27). Reachable by ANY authenticated principal,
        including an agent holding only the ``journal_gate`` confining
        scope — that scope reaches nothing else (see
        CONFINING_SCOPES). This does not loosen ``/api/journal`` or
        ``/api/recall``: those still call ``_require_person`` and
        refuse every agent unconditionally, regardless of scope.

        The response is always exactly the closed Answer schema —
        never raw entries, never free text. See journal_gate.py for
        the validation that enforces this even against a misbehaving
        model.
        """
        principal = getattr(request.state, "principal", None)
        caller_id = f"{getattr(principal, 'kind', 'person')}:{getattr(principal, 'id', 'unknown')}"
        if _gate_rate_limited(caller_id):
            raise HTTPException(
                status_code=429, detail="too many journal-gate asks this minute; wait a moment"
            )
        try:
            body = await request.json()
        except Exception as _err:
            raise HTTPException(status_code=422, detail="body must be JSON") from _err
        body = body or {}
        _, _, uj = _state_for(request)
        target = _journal_target(uj)
        denylist = journal_gate.load_denylist(_journal_gate_denylist_path(request))
        model_fn, model_mode = _journal_gate_model_fn()
        result = journal_gate.gate(
            body, target, model_fn=model_fn, denylist=denylist, caller_id=caller_id
        )
        _logger.info(
            "journal_gate ask: caller=%s ask=%s topic=%r window_days=%s model=%s -> answer=%s",
            caller_id,
            body.get("ask"),
            body.get("topic"),
            body.get("window_days"),
            model_mode,
            result.get("answer"),
        )
        _gate_audit_log(
            uj,
            caller_id=caller_id,
            ask=body.get("ask"),
            topic=body.get("topic"),
            window_days=body.get("window_days"),
            answer=result.get("answer"),
            model_mode=model_mode,
        )
        return {"ok": True, "data": result, "meta": {"model_mode": model_mode}}

    def _gate_audit_log(
        uj: Path, *, caller_id: str, ask, topic, window_days, answer, model_mode
    ) -> None:
        """Structured, content-free audit trail for 'who asked what'
        (step 6): SECURITY-kind journal event, excluded from the gate's
        own retrieval corpus (journal_gate._NON_CONTENT_KINDS). Reuses
        the existing per-principal Journal — not a new storage system —
        and the structured fields ride the event's own ``payload``
        (ADR-0006), never parsed back out of prose."""
        from .classification import Classification
        from .model import JournalEvent, Provenance

        target = journal if uj == journal.path else Journal(uj)
        target.append(
            JournalEvent(
                kind=JournalKind.SECURITY,
                summary=f"journal_gate ask from {caller_id}: {ask} -> {answer}",
                provenance=Provenance(source="journal_gate"),
                classification=Classification.PRIVATE,
                payload={
                    "caller_id": caller_id,
                    "ask": ask,
                    "topic": topic,
                    "window_days": window_days,
                    "answer": answer,
                    "model_mode": model_mode,
                },
            )
        )

    @app.get("/api/journal/gate/log", dependencies=[Depends(require_auth)])
    async def journal_gate_log(request: Request, n: int = 20) -> dict:
        """Person-only: the gate's own audit trail, structured — 'who
        asked what, when, and what they got back'. Never raw entries."""
        _require_person(getattr(request.state, "principal", None))
        _, _, uj = _state_for(request)
        target = journal if uj == journal.path else Journal(uj)
        rows = [
            {"ts": e.ts.isoformat(), **(e.payload or {})}
            for e in target.events()
            if e.kind == JournalKind.SECURITY and e.provenance.source == "journal_gate"
        ]
        rows.sort(key=lambda r: r["ts"], reverse=True)
        return {"ok": True, "data": {"entries": rows[: max(1, min(n, 200))]}}

    @app.get("/api/journal/gate/denylist", dependencies=[Depends(require_auth)])
    async def journal_gate_denylist_get(request: Request) -> dict:
        """Person-only: the owner's own 'never answer about...' list."""
        _require_person(getattr(request.state, "principal", None))
        dl = journal_gate.load_denylist(_journal_gate_denylist_path(request))
        return {"ok": True, "data": dl.model_dump()}

    @app.put("/api/journal/gate/denylist", dependencies=[Depends(require_step_up)])
    async def journal_gate_denylist_put(request: Request) -> dict:
        """Person-only, step-up: editing what a scoped agent can never
        get an answer about is a security-relevant write, same
        elevation tier as other sensitive config in this file."""
        body = await request.json()
        try:
            dl = journal_gate.Denylist.model_validate(body or {})
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        journal_gate.save_denylist(_journal_gate_denylist_path(request), dl)
        return {"ok": True, "data": dl.model_dump()}

    @app.get("/api/memory/search", dependencies=[Depends(require_auth)])
    async def memory_search(request: Request, q: str, top_k: int = 5) -> dict:
        """Semantic recall through the memory provider. Private data
        class: results are personal context, never settings-exportable."""
        _, registry, _ = _state_for(request)
        provider = registry.provider_for("memory")
        if provider is None:
            return {
                "ok": False,
                "status": "unavailable",
                "warnings": ["no memory provider"],
            }
        impl = registry.impl(provider.name)
        if not hasattr(impl, "search"):
            return {
                "ok": False,
                "status": "unavailable",
                "warnings": [f"provider '{provider.name}' cannot search"],
            }
        result = impl.search(q, limit=top_k)
        return result.model_dump(mode="json")

    # ── Records: structured person data living INSIDE Memory ────────────
    # PRODUCT-LANGUAGE §Records ≠ Vault. Records are user information
    # (medical, work history, identity documents, …), NOT secrets — they
    # never touch vault.py. They are stored as World Facts on the caller's
    # own world.json (the core's existing structured-state store; see
    # records.py for the full rationale) and audited through the caller's
    # own append-only journal, so per-principal isolation and the
    # supersession/owner-approval machinery are reused, not re-invented.
    #
    # Backing: Records are a Memory feature, so every route checks the SAME
    # memory-capability provider /api/memory/search checks, and degrades to
    # the identical "no memory provider" envelope when it is absent —
    # never a fake-empty success (capability-grid truth: off / no provider).
    #
    # Writes: gated with require_step_up — the repo's human-approval entry point —
    # matching /api/world/fact and PUT /api/sections (the two closest
    # structured-state writers) and the journal supersede ACT. The elevation
    # is enforced server-side (_step_up_authorized), never from client trust;
    # agents are refused (person-only, like the journal/prefs surfaces).

    def _records_person_guard(request: Request):
        """Person-only + the Memory backing-provider check shared by every
        Records route. Returns ``(world, registry, uj, uw, degrade)``; when
        ``degrade`` is not None the caller returns it verbatim."""
        _require_person(getattr(request.state, "principal", None))
        world, registry, uj = _state_for(request)
        if registry.provider_for("memory") is None:
            return None, None, None, None, {
                "ok": False,
                "status": "unavailable",
                "warnings": ["no memory provider"],
            }
        uw, _uj = _user_paths(request)
        return world, registry, uj, uw, None

    def _records_audit(uj, summary: str) -> None:
        """Append a private, content-free audit line to the CALLER's own
        journal (shared journal in single mode). Field values are never
        copied here — the record content is in world.json, not the
        journal; the audit names the action and category only."""
        target = journal if uj == journal.path else Journal(uj)
        target.record(
            kind=JournalKind.SETTINGS_CHANGE,
            summary=summary,
            source="records",
        )

    @app.get("/api/records/categories", dependencies=[Depends(require_auth)])
    async def records_categories(request: Request) -> dict:
        """Names, counts, and the locked flag for every category. A locked
        category is LISTED (name + count + locked) without exposing contents
        — so a person always knows what to unlock."""
        world, _registry, _uj, _uw, degrade = _records_person_guard(request)
        if degrade is not None:
            return degrade
        cats = records_mod.list_categories(world)
        return {"ok": True, "status": "healthy", "data": {"categories": cats}}

    @app.get("/api/records", dependencies=[Depends(require_auth)])
    async def records_list(
        request: Request,
        category: str | None = None,
        pinned: bool = False,
        q: str | None = None,
    ) -> dict:
        """List records. With a category: a locked category yields a 409 'locked' envelope unless THIS request carries fresh step-up.
        Without a category: the unlocked browse view; ``?pinned=true`` narrows
        it to the Overview feed. A locked category is never aggregated in.

        ``?q=`` is the deterministic lexical find (G-memory: works with every
        model off — records.search_records, no index/provider/embeddings):
        case-insensitive AND-substring over title, category name, and field
        keys/values. Locked categories contribute to ``q`` results ONLY when
        this request carries a server-verified step-up (fail closed, same entry point
        as the locked-category read above); the pinned filter still applies.
        """
        world, _registry, _uj, _uw, degrade = _records_person_guard(request)
        if degrade is not None:
            return degrade
        query = q.strip() if isinstance(q, str) else ""
        if category is not None:
            slug = records_mod.category_slug(category)
            if not slug:
                raise HTTPException(status_code=422, detail="category is required")
            cat = records_mod.get_category(world, slug)
            if cat and cat["locked"] and not _step_up_authorized(
                request, getattr(request.state, "principal", None)
            ):
                return JSONResponse(
                    status_code=409,
                    content={
                        "ok": False,
                        "status": "locked",
                        "category": slug,
                        "warnings": [
                            f"category '{slug}' is locked: step-up required to read"
                        ],
                    },
                )
            if query:
                # The 409 gate above already decided elevation for THIS
                # category, so the search inside it may see it.
                recs = records_mod.search_records(
                    world, query, category=slug, include_locked=True
                )
            else:
                recs = records_mod.list_records(world, slug)
            if pinned:
                recs = [r for r in recs if r.get("pinned")]
            data = {
                "category": slug,
                "locked": bool(cat and cat["locked"]),
                "records": recs,
            }
            if query:
                data["query"] = query
            return {"ok": True, "status": "healthy", "data": data}
        if query:
            # Aggregate find: locked-category contents join the results only
            # behind a server-verified step-up — never client trust.
            elevated = _step_up_authorized(
                request, getattr(request.state, "principal", None)
            )
            recs = records_mod.search_records(world, query, include_locked=elevated)
            if pinned:
                recs = [r for r in recs if r.get("pinned")]
            return {
                "ok": True,
                "status": "healthy",
                "data": {"records": recs, "query": query},
            }
        # Aggregate browse view: never surfaces locked-category contents. The
        # pinned Overview feed is owned by records.pinned_records (same rule).
        if pinned:
            return {
                "ok": True,
                "status": "healthy",
                "data": {"records": records_mod.pinned_records(world)},
            }
        out: list[dict] = []
        for c in records_mod.list_categories(world):
            if c["locked"]:
                continue
            out.extend(records_mod.list_records(world, c["slug"]))
        out.sort(key=lambda r: str(r.get("created", "")), reverse=True)
        return {"ok": True, "status": "healthy", "data": {"records": out}}

    @app.post("/api/records", dependencies=[Depends(require_step_up)])
    async def records_write(request: Request) -> dict:
        """Create or update a record. Step-up gated (the human-approval ACT,
        same entry point as /api/world/fact and PUT /api/sections). Optional
        ``locked`` sets the category's lock in the same authorized write;
        records are stored as World Facts on the caller's own world.json."""
        _world, _registry, uj, uw, degrade = _records_person_guard(request)
        if degrade is not None:
            return degrade
        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="body must be an object")
        if "title" not in body:
            raise HTTPException(status_code=422, detail="title is required")
        locked = body.get("locked")
        if locked is not None and not isinstance(locked, bool):
            raise HTTPException(status_code=422, detail="locked must be a boolean")
        try:
            rec = records_mod.upsert_record(
                _world,
                category=body.get("category"),
                title=body.get("title"),
                fields=body.get("fields"),
                record_id=body.get("id"),
                locked=locked,
                source="records",
            )
        except records_mod.RecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        save_world(_world, uw)
        _records_audit(uj, f"record updated in category '{rec['category']}'")
        return {"ok": True, "status": "healthy", "data": rec}

    @app.post("/api/records/pin", dependencies=[Depends(require_step_up)])
    async def records_pin(request: Request) -> dict:
        """Pin a record for the Overview. Step-up gated, caller-scoped."""
        return await _records_pin_or_unpin(request, True)

    @app.post("/api/records/unpin", dependencies=[Depends(require_step_up)])
    async def records_unpin(request: Request) -> dict:
        """Remove a record's pin. Step-up gated, caller-scoped."""
        return await _records_pin_or_unpin(request, False)

    async def _records_pin_or_unpin(request: Request, pinned: bool) -> dict:
        _world, _registry, uj, uw, degrade = _records_person_guard(request)
        if degrade is not None:
            return degrade
        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="body must be an object")
        rec = records_mod.set_pinned(
            _world, body.get("category"), body.get("id"), pinned
        )
        if rec is None:
            return {
                "ok": False,
                "status": "not_found",
                "warnings": ["no such record"],
            }
        save_world(_world, uw)
        verb = "pinned" if pinned else "unpinned"
        _records_audit(uj, f"record {verb} in category '{rec['category']}'")
        return {"ok": True, "status": "healthy", "data": rec}

    @app.delete("/api/records", dependencies=[Depends(require_step_up)])
    async def records_delete(request: Request) -> dict:
        """Delete a record. Same approval discipline as every Records write:
        step-up gated and caller-scoped."""
        _world, _registry, uj, uw, degrade = _records_person_guard(request)
        if degrade is not None:
            return degrade
        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="body must be an object")
        slug = records_mod.category_slug(body.get("category"))
        removed = records_mod.delete_record(_world, body.get("category"), body.get("id"))
        if not removed:
            return {
                "ok": False,
                "status": "not_found",
                "warnings": ["no such record"],
            }
        save_world(_world, uw)
        _records_audit(uj, f"record deleted from category '{slug}'")
        return {"ok": True, "status": "healthy", "data": {"deleted": True}}

    # The tool-calling chat loop is in ``chat.chat_with_tools_loop``
    # (ONE loop for every provider; lenient small-model argument
    # handling; execution tools structurally blocked by the registry).

    @app.post("/api/chat", dependencies=[Depends(require_auth)])
    async def chat(request: Request) -> dict:
        """Conversational interface to Project Worlds.

        Read-only: the model observes a rendered world snapshot and
        returns text. No tool execution, no mutations. With no chat
        provider configured the endpoint answers 'not_configured' so
        the dashboard can report a degraded state."""
        body: dict
        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        message = (body.get("message") or "").strip() if isinstance(body, dict) else ""
        if not message:
            raise HTTPException(status_code=400, detail="message is required")
        history = body.get("history") if isinstance(body, dict) else None
        if not isinstance(history, list):
            history = []
        history = [
            {"role": m.get("role"), "content": m.get("content")}
            for m in history[-6:]
            if isinstance(m, dict) and m.get("content")
        ]
        # Per-user chat (decision #13): the conversation observes the
        # CALLER's own world/journal, proposes into the caller's own
        # proposal tree, and transcripts into the caller's own history.
        # Single mode resolves every one of those to the legacy instance
        # paths (byte-identical behavior).
        principal = _principal(request)
        world, registry, uj = _state_for(request)
        uw, _uj = _user_paths(request)
        caller_journal = _journal_target(uj)
        provider = registry.provider_for("reasoning")
        if provider is None:
            return {
                "ok": False,
                "status": "not_configured",
                "warnings": [
                    "no chat provider configured — add an ollama or "
                    "openai_compat connection to config"
                ],
            }
        impl = registry.impl(provider.name)
        context = await run_in_threadpool(
            build_world_context, world, registry, caller_journal, True, config_dir
        )
        # Brain templates (first-class): compose runtime instructions
        # from config/prompts/{core,personas,surfaces,tasks,formats}.
        # Surface is derived from the UI route (e.g. /lab -> lab). The
        # companion persona is only composed when the optional
        # personality pack is on (see the voice block below);
        # personality is a plain-markdown template, not code.
        templates = TemplateRegistry(config_dir, data_dir)
        ui = body.get("context") if isinstance(body, dict) else None
        surface = None
        if isinstance(ui, dict):
            route = str(ui.get("route") or "")
            if route.startswith("/"):
                surface = route[1:]  # /lab -> lab
        # One voice + tone registers (TRUE-NORTH § Voice, W1-B): the
        # default identity is the one Worlds voice at the person's tone
        # register; a companion persona rides along ONLY when the optional
        # personality pack is switched on (default residents) AND the
        # chosen `companion_id` names an entry in THIS caller's own crew
        # (owner decision 2026-09-25). Each read is guarded on its own so a
        # crew read that fails still leaves the person's tone register
        # intact, and resolve_voice fails safe to (one voice, warm).
        try:
            _pref_values = prefs.get_prefs(world)
        except Exception:
            _pref_values = None
        try:
            _, _chat_crew_state = _crew_state(request)
        except Exception:
            _chat_crew_state = None
        _voice = voice.resolve_voice(_pref_values, _chat_crew_state)
        template_instructions = templates.compose(
            surface=surface, persona=_voice.persona
        )
        # The companion's own naming line for a crew entry the shipped
        # persona tree does not speak for (Bolt, Hekek, a person's own
        # companion): the roster name, plus that companion's voice_label as
        # phrasing only. Empty for the one voice and for a drawn companion
        # whose canon persona template already speaks (Renai).
        companion_line = voice.companion_instruction(_voice)
        if companion_line:
            template_instructions = (
                f"{template_instructions}\n\n{companion_line}"
                if template_instructions
                else companion_line
            )
        # Contextual chat (Finish Line "Contextual chat and model
        # routing"): the caller may describe WHERE in the UI the person
        # is. Provenance, not truth: an unknown section_id degrades to
        # an "unknown" block rather than being trusted or
        # rejected — a stale tab must not break conversation.
        ui_block = None
        if isinstance(ui, dict):
            route = str(ui.get("route") or "") or None
            sid = str(ui.get("section_id") or "") or None
            spec = sections_mod.BY_ID.get(sid) if sid else None
            entity = str(ui.get("entity") or "") or None
            ui_block = build_ui_context(
                route=route,
                section_id=sid,
                section_label=(
                    spec.label if spec else str(ui.get("label") or "") or None
                ),
                section_status=(
                    sections_mod.section_status(spec, registry.status_map())
                    if spec
                    else None
                ),
                section_capabilities=(list(spec.capabilities) if spec else None),
                entity=entity,
            )
        if ui_block:
            context = context + "\n\n" + ui_block
        # Build tool registry from current state
        from .tool_registry import build_default_tools

        _memory_impl = None
        _memory_p = registry.provider_for("memory")
        if _memory_p is not None:
            _memory_impl = registry.impl(_memory_p.name)
        tool_reg = build_default_tools(
            world,
            registry,
            caller_journal,
            None,
            _vault,
            config_dir,
            data_dir=data_dir,
            world_path=uw,
            scheduler=_scheduler_for(principal),
            memory_provider=_memory_impl,
            proposal_store=_proposal_store(request),
        )
        tool_schemas = tool_reg.list_ollama_schemas()
        messages = build_chat_messages(
            message, context, history, persona=template_instructions,
            tone=_voice.tone,
        )
        # ONE chat loop: every provider implements chat_with_tools
        # (natively or through the ChatContract default with lenient
        # small-model parsing), so the tool loop always runs when tools
        # exist; chat_once remains the no-tools fallback.
        if hasattr(impl, "chat_with_tools") and tool_schemas:
            result = await run_in_threadpool(
                chat_with_tools_loop, impl, messages, tool_reg, tool_schemas
            )
        else:
            result = await run_in_threadpool(chat_once, impl, messages)
        if not result.ok:
            return result.model_dump(mode="json")
        # Assistant-drafted correction proposals (Play-Nice:
        # participation, not authority): strictly validate the extracted
        # block against the REAL journal — the entry must exist and not
        # already be superseded. A stale/imagined/malformed proposal
        # degrades to nothing; the visible reply always works.
        reply_text = (result.data or {}).get("reply", "")
        proposal_json, visible_reply = extract_proposal(reply_text)
        if proposal_json is not None:
            proposal = json.loads(proposal_json)
            entry = caller_journal.by_ts(proposal["entry_ts"])
            if entry is None or any(
                later.supersedes == entry.ts for later in caller_journal.events()
            ):
                proposal = None
        else:
            proposal = None
        if visible_reply != reply_text:
            result = result.model_copy(
                update={
                    "data": {
                        **(result.data or {}),
                        "reply": visible_reply or reply_text,
                        **({"proposal": proposal} if proposal else {}),
                    },
                }
            )
        caller_journal.record(
            "recommendation",
            f"chat exchange with {provider.name} ({len(message)} chars in)",
            source="chat",
        )
        # Durable per-principal transcript (append-only NDJSON; the
        # chat surface's memory, distinct from the journal's audit
        # stream). Best-effort: a transcript write failure must never
        # swallow the visible reply.
        try:
            transcript = ChatHistory(_scoped_path(principal, "chat_history"))
            transcript.append("user", message)
            transcript.append(
                "assistant",
                visible_reply or reply_text,
                provider=provider.name,
            )
        except OSError as exc:
            _logger.warning("chat history append failed: %s", exc)
        return result.model_dump(mode="json")

    @app.get("/api/chat/history", dependencies=[Depends(require_auth)])
    async def chat_history_view(request: Request, n: int = 50) -> dict:
        """The caller's own persisted chat transcript, oldest first
        (per-user, decision #13). Never another principal's."""
        transcript = ChatHistory(_scoped_path(_principal(request), "chat_history"))
        entries = transcript.recent(min(max(n, 1), 500))
        if getattr(_principal(request), "read_only", False):
            # Structure only for a read-only viewer: when and who, never
            # what was said.
            entries = [
                {k: e[k] for k in VIEWER_CHAT_ENTRY_KEYS if k in e} for e in entries
            ]
        return {"ok": True, "data": {"entries": entries, "count": len(entries)}}

    @app.get("/api/chat/providers", dependencies=[Depends(require_auth)])
    def chat_providers() -> dict:
        """List available chat providers and which is active."""
        _, registry = _state()
        providers = []
        active_name = None
        for p in registry._providers.values():
            if p.capability == "reasoning":
                impl = registry.impl(p.name)
                r = impl.observe() if impl else None
                providers.append(
                    {
                        "name": p.name,
                        "display_name": getattr(impl, "display_name", p.name),
                        "status": r.status if r else "unknown",
                        "ok": r.ok if r else False,
                    }
                )
                if active_name is None and (r and r.ok):
                    active_name = p.name
        # If there's a provider_for, it's the active one
        active = registry.provider_for("reasoning")
        return {
            "ok": True,
            "data": {
                "providers": providers,
                "active": active.name if active else None,
            },
        }

    @app.post("/api/chat/test", dependencies=[Depends(require_auth)])
    async def chat_test() -> dict:
        """Quick chat test — sends a simple message to verify the provider
        works. Authenticated: it spends provider quota and reveals which
        provider is wired, so it is never a public probe."""
        _, registry = _state()
        provider = registry.provider_for("reasoning")
        if provider is None:
            return {
                "ok": False,
                "status": "not_configured",
                "warnings": ["no chat provider"],
            }
        impl = registry.impl(provider.name)
        if impl is None:
            return {"ok": False, "status": "unavailable"}
        result = chat_once(
            impl,
            [
                {"role": "system", "content": "Reply with exactly one word: hello"},
                {"role": "user", "content": "hello"},
            ],
        )
        return {
            "ok": result.ok,
            "status": result.status,
            "data": result.data,
            "warnings": result.warnings,
        }

    @app.get("/api/tools", dependencies=[Depends(require_auth)])
    async def tools(request: Request) -> dict:
        """List tools the brain can invoke at runtime.

        Returns the actual callable tool registry, not just capability descriptions.
        Each tool has: id, capability, operation, description, read/write,
        parameters schema, availability, approval requirement.
        Wiring is scoped to the caller (decision #13), mirroring the
        chat handler: same world/journal/reminders/proposals/interests.
        """
        principal = _principal(request)
        world, registry, uj = _state_for(request)
        uw, _uj = _user_paths(request)
        from .tool_registry import build_default_tools

        _memory_impl = None
        _memory_p = registry.provider_for("memory")
        if _memory_p is not None:
            _memory_impl = registry.impl(_memory_p.name)
        tool_reg = build_default_tools(
            world,
            registry,
            _journal_target(uj),
            None,
            _vault,
            config_dir,
            data_dir=data_dir,
            world_path=uw,
            scheduler=_scheduler_for(principal),
            memory_provider=_memory_impl,
            proposal_store=_proposal_store(request),
        )
        return {
            "ok": True,
            "data": {
                "tools": tool_reg.list_metadata(),
                "count": len(tool_reg.list_tools()),
            },
        }

    # ── Proposal management (owner approval path) ──

    @app.get("/api/proposals", dependencies=[Depends(require_auth)])
    async def proposals_list(request: Request, status: str | None = None) -> dict:
        """List the CALLER's proposals, optionally filtered by status
        (per-user trees, decision #13)."""
        return {"ok": True, "data": _proposal_store(request).list(status)}

    @app.get("/api/proposals/{proposal_id}", dependencies=[Depends(require_auth)])
    async def proposals_get(proposal_id: str, request: Request) -> dict:
        """Get a single proposal by ID from the caller's own tree."""
        p = _proposal_store(request).get(proposal_id)
        if p is None:
            raise HTTPException(status_code=404, detail="proposal not found")
        return {"ok": True, "data": p}

    @app.post(
        "/api/proposals/{proposal_id}/approve", dependencies=[Depends(require_step_up)]
    )
    async def proposals_approve(proposal_id: str, request: Request) -> dict:
        """Approve a pending proposal. Step-up gated.

        This is the trusted owner approval path. The model cannot
        call this endpoint — it requires step-up authorization. The
        approval is recorded in (and only reaches) the caller's own
        proposal tree, and journals to the caller's own journal.
        """
        principal = getattr(request.state, "principal", None)
        actor = principal.id if principal else "unknown"
        store = _proposal_store(request)
        r = store.approve(
            proposal_id,
            actor,
            journal=_journal_target(_scoped_path(principal, "journal")),
        )
        return r.model_dump(mode="json")

    @app.post(
        "/api/proposals/{proposal_id}/reject", dependencies=[Depends(require_step_up)]
    )
    async def proposals_reject(proposal_id: str, request: Request) -> dict:
        """Reject a pending proposal. Step-up gated."""
        principal = getattr(request.state, "principal", None)
        actor = principal.id if principal else "unknown"
        store = _proposal_store(request)
        r = store.reject(
            proposal_id,
            actor,
            journal=_journal_target(_scoped_path(principal, "journal")),
        )
        return r.model_dump(mode="json")

    @app.post(
        "/api/proposals/{proposal_id}/execute", dependencies=[Depends(require_step_up)]
    )
    async def proposals_execute(proposal_id: str, request: Request) -> dict:
        """Execute an approved proposal. Step-up gated.

        Only proposals that have been approved through the trusted
        owner path can be executed. The approval evidence is checked
        server-side — the model cannot forge it. Execution mutates the
        CALLER's own world/journal/reminders tree.
        """
        store = _proposal_store(request)
        # Verify proposal exists and is approved before attempting execution
        p = store.get(proposal_id)
        if p is None:
            raise HTTPException(status_code=404, detail="proposal not found")
        if p.get("status") != "approved":
            return {
                "ok": False,
                "status": "invalid_state",
                "warnings": [f"proposal is {p.get('status')}, not approved"],
            }
        world, registry, uj = _state_for(request)
        uw, _uj = _user_paths(request)
        # world_path is part of the trusted execution act: the executor
        # persists world mutations through the authoritative save path
        # and reports what it changed (no redundant second save here).
        r = store.execute(
            _journal_target(uj),
            world,
            proposal_id,
            _scheduler_for(_principal(request)),
            world_path=uw,
        )
        return r.model_dump(mode="json")

    @app.get("/api/actors", dependencies=[Depends(require_auth)])
    async def actors() -> dict:
        _, registry = _state()
        return {
            "ok": True,
            "data": [a.model_dump(mode="json") for a in registry.actors()],
        }

    @app.get("/api/manifest", dependencies=[Depends(require_auth)])
    async def manifest() -> dict:
        """Machine-readable capability manifest (framework contract:
        see docs/NATIVE-BASELINE-AND-ENRICHMENT.md) plus the endpoint
        manifest (product decision #17: the API is the Lego box, so it
        has to be discoverable).

        ``data`` stays exactly the capability/provider manifest its
        existing consumers expect; ``endpoints`` is additive. It is
        curated in one place (``api_manifest.py``) and verified against
        the live route table, so it can never advertise a route that is
        not registered.
        """
        _, registry = _state()
        from .api_manifest import endpoint_manifest

        return {
            "ok": True,
            "data": registry.manifest(),
            "endpoints": endpoint_manifest(app.routes),
        }

    # ── Connections & Providers ──────────────────────────────────

    conn_mgr = ConnectionManager(config_dir)

    @app.get("/api/connections/schemas", dependencies=[Depends(require_auth)])
    async def connection_schemas() -> dict:
        """Return all provider schemas for the Connections & Providers UI."""
        return {"ok": True, "data": get_capability_schemas()}

    @app.get(
        "/api/connections/schema/{capability}", dependencies=[Depends(require_auth)]
    )
    async def connection_schema(capability: str) -> dict:
        """Return schema for a single capability."""
        schema = get_capability_schema(capability)
        if not schema:
            raise HTTPException(
                status_code=404, detail=f"Unknown capability: {capability}"
            )
        return {"ok": True, "data": schema}

    @app.get("/api/connections/config", dependencies=[Depends(require_auth)])
    async def connections_config() -> dict:
        """Return the full merged connection configuration."""
        return {"ok": True, "data": conn_mgr.get_all_config()}

    @app.get("/api/connections/overview", dependencies=[Depends(require_auth)])
    async def connections_overview() -> dict:
        """Return capability overview: status, config state, providers."""
        _, registry = _state()
        status_map = registry.status_map()
        config = conn_mgr.get_all_config()
        result = []
        for cs in CAPABILITY_SCHEMAS.values():
            cap = cs.capability
            status_info = status_map.get(cap, {})
            # Determine if configured — resolve flat UI config to
            # provider shape before checking
            from .connection_manager import resolve_native_config
            from .secret_resolver import secret_status

            if cap == "media":
                media_cfg = config.get("media", {})
                # Check both connections[] entries and flat UI config
                has_conn_entries = any(
                    c.get("type") in ("plex", "sonarr", "radarr", "lidarr")
                    for c in config.get("connections", [])
                )
                has_ui_config = bool(media_cfg.get("_adapter"))
                configured = has_conn_entries or has_ui_config
            elif cap in ("calendar", "notifications", "updates"):
                raw_cfg = config.get(cap, {})
                resolved = resolve_native_config(raw_cfg, cap)
                # Check the resolved wrapper key
                spec_map = {
                    "calendar": "sources",
                    "notifications": "targets",
                    "updates": "sources",
                }
                wrapper = spec_map.get(cap, "")
                items = resolved.get(wrapper, [])
                configured = len(items) > 0
            elif cap == "auth":
                oidc_path = config_dir / "oidc.json"
                configured = oidc_path.exists()
            elif cap == "reasoning":
                conns = config.get("connections", [])
                configured = any(c.get("capability") == "reasoning" for c in conns)
            else:
                configured = status_info.get("status") not in (None, "not_configured")
            result.append(
                {
                    "capability": cap,
                    "display_name": cs.display_name,
                    "description": cs.description,
                    "icon": cs.icon,
                    "status": status_info.get("status", "not_configured"),
                    "ok": status_info.get("ok", False),
                    "configured": configured,
                    "needs_setup": cs.needs_setup,
                    "help_text": cs.help_text,
                    "providers": [p.to_dict() for p in cs.providers],
                    # Plain words per secret field ("ready", "needs your
                    # vault unlocked", ...); never a value.
                    "secrets": secret_status(config.get(cap, {}) or {}),
                }
            )
        return {"ok": True, "data": result}

    @app.get("/api/connections", dependencies=[Depends(require_auth)])
    async def connections_list() -> dict:
        """Return all connections."""
        return {"ok": True, "data": conn_mgr.get_connections()}

    @app.put("/api/connections", dependencies=[Depends(require_step_up)])
    async def connections_save(request: Request) -> dict:
        """Save a connection (step-up required)."""
        body = await request.json()
        name = body.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        conn_mgr.save_connection(body)
        return {"ok": True, "data": {"saved": True, "name": name}}

    @app.delete("/api/connections/{name}", dependencies=[Depends(require_step_up)])
    async def connections_delete(name: str, request: Request) -> dict:
        """Delete a connection by name (step-up required)."""
        deleted = conn_mgr.delete_connection(name)
        return {"ok": True, "data": {"deleted": deleted}}

    @app.post("/api/connections/config/{key}", dependencies=[Depends(require_step_up)])
    async def save_native_config(key: str, request: Request) -> dict:
        """Save native provider config (calendar, notifications, etc.)."""
        body = await request.json()
        conn_mgr.save_native_config(key, body)
        return {"ok": True, "data": {"saved": True, "key": key}}

    @app.post("/api/connections/test", dependencies=[Depends(require_auth)])
    async def test_connection(request: Request) -> dict:
        """Test a connection configuration without saving it."""
        body = await request.json()
        capability = body.get("capability", "")
        adapter_type = body.get("adapter_type", "")
        config = body.get("config", {})
        result = _test_adapter(capability, adapter_type, config)
        return {"ok": True, "data": result}

    @app.post("/api/connections/validate", dependencies=[Depends(require_auth)])
    async def validate_connection(request: Request) -> dict:
        """Validate connection config (alias for test)."""
        body = await request.json()
        capability = body.get("capability", "")
        adapter_type = body.get("adapter_type", "")
        config = body.get("config", {})
        result = _test_adapter(capability, adapter_type, config)
        return {"ok": True, "data": result}

    def _test_adapter(capability: str, adapter_type: str, config: dict) -> dict:
        """Test an adapter connection. Returns structured state.

        Fetching branches share _probe_url: absolute http(s) URLs only,
        redirects never followed."""
        if adapter_type == "plex":
            url = config.get("base_url", "").rstrip("/")
            token = config.get("token", "")
            if not url:
                return {
                    "status": "invalid_configuration",
                    "detail": "Server URL is required",
                }
            r = _probe_url(url, headers={"X-Plex-Token": token} if token else None)
            if r["status"] == "invalid_configuration":
                return {
                    "status": "invalid_configuration",
                    "detail": "Server URL must be an absolute http(s) address",
                }
            if r["status"] == "healthy":
                note = " (redirect not followed)" if r.get("redirected") else ""
                return {
                    "status": "healthy",
                    "detail": f"Plex responded ({r.get('code')}){note}",
                }
            reason = r.get("reason") or f"HTTP {r.get('code')}"
            return {"status": "unavailable", "detail": f"Cannot reach Plex: {reason}"}
        elif adapter_type in ("sonarr", "radarr", "lidarr"):
            url = config.get("base_url", "").rstrip("/")
            api_key = config.get("api_key", "")
            if not url:
                return {
                    "status": "invalid_configuration",
                    "detail": "Server URL is required",
                }
            r = _probe_url(
                f"{url}/api/v3/system/status",
                headers={"X-Api-Key": api_key} if api_key else {},
            )
            if r["status"] == "invalid_configuration":
                return {
                    "status": "invalid_configuration",
                    "detail": "Server URL must be an absolute http(s) address",
                }
            if r["status"] == "healthy":
                note = " (redirect not followed)" if r.get("redirected") else ""
                return {
                    "status": "healthy",
                    "detail": (
                        f"{adapter_type.title()} responded ({r.get('code')}){note}"
                    ),
                }
            reason = r["reason"] if "reason" in r else f"HTTP {r.get('code')}"
            return {
                "status": "unavailable",
                "detail": f"Cannot reach {adapter_type.title()}: {reason}",
            }
        elif adapter_type == "ics":
            url = config.get("url", "")
            if not url:
                return {
                    "status": "invalid_configuration",
                    "detail": "URL is required",
                }
            r = _probe_url(url, method="HEAD")
            if r["status"] == "invalid_configuration":
                return {
                    "status": "invalid_configuration",
                    "detail": "URL must be an absolute http(s) address",
                }
            if r["status"] == "healthy":
                note = " (redirect not followed)" if r.get("redirected") else ""
                return {
                    "status": "healthy",
                    "detail": f"ICS feed reachable ({r.get('code')}){note}",
                }
            reason = r["reason"] if "reason" in r else f"HTTP {r.get('code')}"
            return {
                "status": "unavailable",
                "detail": f"Cannot reach ICS feed: {reason}",
            }
        elif adapter_type == "ntfy":
            server = config.get("server", "https://ntfy.sh").rstrip("/")
            topic = config.get("topic", "")
            if not topic:
                return {
                    "status": "invalid_configuration",
                    "detail": "Topic is required",
                }
            r = _probe_url(f"{server}/v1/health")
            if r["status"] == "invalid_configuration":
                return {
                    "status": "invalid_configuration",
                    "detail": "Server URL must be an absolute http(s) address",
                }
            if r["status"] == "healthy":
                note = " (redirect not followed)" if r.get("redirected") else ""
                return {
                    "status": "healthy",
                    "detail": f"ntfy server reachable ({r.get('code')}){note}",
                }
            reason = r["reason"] if "reason" in r else f"HTTP {r.get('code')}"
            return {"status": "unavailable", "detail": f"Cannot reach ntfy: {reason}"}
        elif adapter_type == "webhook":
            url = config.get("url", "")
            if not url:
                return {
                    "status": "invalid_configuration",
                    "detail": "URL is required",
                }
            return {
                "status": "validated",
                "detail": "Webhook URL accepted (not tested with a real request)",
            }
        elif adapter_type == "github_release":
            repo = config.get("repository", "")
            if not repo:
                return {
                    "status": "invalid_configuration",
                    "detail": "Repository is required",
                }
            try:
                req = urllib.request.Request(
                    f"https://api.github.com/repos/{repo}/releases/latest",
                    headers={"Accept": "application/vnd.github.v3+json"},
                )
                with _OPENER.open(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    tag = data.get("tag_name", "unknown")
                    return {"status": "healthy", "detail": f"Latest release: {tag}"}
            except urllib.error.URLError as e:
                return {
                    "status": "unavailable",
                    "detail": f"Cannot reach GitHub: {e.reason}",
                }
        elif adapter_type == "ollama":
            url = config.get("base_url", "").rstrip("/")
            if not url:
                return {
                    "status": "invalid_configuration",
                    "detail": "Server URL is required",
                }
            if not _valid_http_url(url):
                return {
                    "status": "invalid_configuration",
                    "detail": "Server URL must be an absolute http(s) address",
                }
            try:
                req = urllib.request.Request(f"{url}/api/tags", method="GET")
                with _OPENER.open(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    models = [m.get("name", "") for m in data.get("models", [])]
                    return {
                        "status": "healthy",
                        "detail": f"Ollama has {len(models)} model(s)",
                    }
            except urllib.error.URLError as e:
                return {
                    "status": "unavailable",
                    "detail": f"Cannot reach Ollama: {e.reason}",
                }
        elif adapter_type == "oidc":
            issuer = config.get("issuer_url", "")
            if not issuer:
                return {
                    "status": "invalid_configuration",
                    "detail": "Issuer URL is required",
                }
            r = _probe_url(f"{issuer.rstrip('/')}/.well-known/openid-configuration")
            if r["status"] == "invalid_configuration":
                return {
                    "status": "invalid_configuration",
                    "detail": "Issuer URL must be an absolute http(s) address",
                }
            if r["status"] == "healthy":
                note = " (redirect not followed)" if r.get("redirected") else ""
                return {
                    "status": "healthy",
                    "detail": f"OIDC discovery endpoint reachable ({r.get('code')})"
                    + note,
                }
            reason = r["reason"] if "reason" in r else f"HTTP {r.get('code')}"
            return {
                "status": "unavailable",
                "detail": f"Cannot reach OIDC issuer: {reason}",
            }
        elif adapter_type == "compose":
            path = config.get("compose_path", "")
            if not path:
                return {
                    "status": "invalid_configuration",
                    "detail": "Compose file path is required",
                }
            p = Path(path)
            if p.exists():
                return {
                    "status": "validated",
                    "detail": f"Compose file found at {path}",
                }
            return {
                "status": "unavailable",
                "detail": f"Compose file not found at {path}",
            }
        elif adapter_type == "systemd":
            service = config.get("service_name", "")
            if not service:
                return {
                    "status": "invalid_configuration",
                    "detail": "Service name is required",
                }
            return {
                "status": "validated",
                "detail": f"Service '{service}' accepted — no live check performed",
            }
        else:
            return {
                "status": "unknown",
                "detail": f"Test not implemented for {adapter_type}",
            }

    @app.get("/api/exports/settings", dependencies=[Depends(require_auth)])
    async def settings_export() -> dict:
        """Shareable settings blueprint: capabilities, provider mappings,
        packs, schedules — the bones of the installation, not the person."""
        world, _ = _state()
        return {"ok": True, "data": export.settings_export(world)}

    @app.get("/api/exports/world", dependencies=[Depends(require_auth)])
    async def world_export(request: Request) -> dict:
        """Portable personal configuration: world-classified state only;
        raw secrets are structurally absent (they are in the secret
        store, referenced by name at most). Treat the output as personal
        data."""
        world, _, _ = _state_for(request)
        return {"ok": True, "data": export.world_export(world)}

    @app.get("/api/exports/story", dependencies=[Depends(require_auth)])
    async def story_export() -> dict:
        """Human-readable journal story (entry summaries); private
        entries are excluded from the rendering."""
        return {"ok": True, "data": {"text": export.story_export(journal)}}

    @app.get("/api/backup", dependencies=[Depends(require_auth)])
    async def backup(request: Request) -> dict:
        """Full-state backup payload (world, journal, config) including
        private state. Meant for the operator's own encryption step; it
        is never shareable raw, and the API does not encrypt it."""
        world, _, uj = _state_for(request)
        return {"ok": True, "data": export.backup_payload(world, _journal_at(uj))}

    @app.get("/api/prefs", dependencies=[Depends(require_auth)])
    async def prefs_get(request: Request) -> dict:
        _require_person(getattr(request.state, "principal", None))
        world, _, _ = _state_for(request)
        return {"ok": True, "data": prefs.get_prefs(world)}

    async def _prefs_write(request: Request) -> dict:
        """The one preference-write body (PUT and PATCH are aliases).

        ``companion_id`` is validated against *this principal's* crew: the
        roster is the vocabulary, per person. An unknown or hidden id is a
        422 with a sentence, never a stored id that would silently fall back
        to the one voice; every other rejection keeps the 400 the
        minimum accessibility settings has always answered with.
        """
        _require_person(getattr(request.state, "principal", None))
        world, _, uj = _state_for(request)
        try:
            updates = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        _, crew_state = _crew_state(request)
        usable_ids = {
            entry["id"]
            for entry in crew_state["crew"]
            if not entry.get("hidden")
        }
        try:
            data = prefs.set_prefs(world, updates, companion_ids=usable_ids)
        except prefs.UnknownCompanionId as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except prefs.PrefsValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        uw, _uj = _user_paths(request)
        save_world(world, uw)
        return {"ok": True, "data": data}

    @app.put("/api/prefs", dependencies=[Depends(require_auth)])
    async def prefs_put(request: Request) -> dict:
        """Save preference updates.

        The handler has always applied exactly the keys it was given, so
        ``PATCH`` is registered as an alias for clients that name a partial
        update: same body, same validation, same gate.
        """
        return await _prefs_write(request)

    @app.patch("/api/prefs", dependencies=[Depends(require_auth)])
    async def prefs_patch(request: Request) -> dict:
        """Partial preference update — the PUT alias (see ``prefs_put``)."""
        return await _prefs_write(request)

    @app.get("/api/prefs/schema", dependencies=[Depends(require_auth)])
    async def prefs_schema() -> dict:
        """Read-only preference vocabulary (spec §2.5): the Settings
        surface can only offer values the server accepts.

        ``companion_id`` is the one row with no closed list — its vocabulary
        is the caller's own crew (GET /api/crew), stated in the row's note.
        """
        return {
            "ok": True,
            "data": {
                key: prefs.spec_schema(spec) for key, spec in prefs.PREFS.items()
            },
        }

    # -- sections: per-person navigation layout (spec §2) ---------------
    def _sections_payload(world: World, registry: Registry) -> dict:
        status_map = registry.status_map()
        stored = world.layout.get(sections_mod.LAYOUT_KEY)
        return {
            "ok": True,
            "data": {
                "schema": sections_mod.SCHEMA,
                "sections": sections_mod.resolve_sections(stored, status_map),
            },
        }

    @app.get("/api/sections", dependencies=[Depends(require_auth)])
    async def sections_get(request: Request) -> dict:
        _require_person(getattr(request.state, "principal", None))
        world, registry, _ = _state_for(request)
        return _sections_payload(world, registry)

    @app.put("/api/sections", dependencies=[Depends(require_step_up)])
    async def sections_put(request: Request) -> dict:
        _require_person(getattr(request.state, "principal", None))
        world, registry, uj = _state_for(request)
        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="body must be an object")
        current = world.layout.get(sections_mod.LAYOUT_KEY) or {}
        new_layout, errors = sections_mod.validate_layout_update(body, current)
        if errors:
            raise HTTPException(status_code=400, detail="; ".join(errors))
        world.layout[sections_mod.LAYOUT_KEY] = new_layout
        uw, _uj = _user_paths(request)
        save_world(world, uw)
        # Whose state is this? The caller's. The event goes to the
        # caller's own journal (shared journal in single mode).
        target = journal if uj == journal.path else Journal(uj)
        target.record(
            kind=JournalKind.SETTINGS_CHANGE,
            summary="sections layout updated",
            source="api",
        )
        return _sections_payload(world, registry)

    # -- source_control: native git baseline (zero providers required) --
    def _sc_paths() -> list[str]:
        from .source_control import configured_search_paths

        return configured_search_paths(config_dir)

    @app.get("/api/source-control/status", dependencies=[Depends(require_auth)])
    async def source_control_status() -> dict:
        paths = _sc_paths()
        if not paths:
            return {
                "ok": False,
                "status": "not_configured",
                "warnings": ["no source_control search paths configured"],
            }
        repos = [
            r
            for r in status_all(paths)
            if r.get("error") is None or r.get("branch") is not None
        ]
        if not repos:
            return {
                "ok": False,
                "status": "not_configured",
                "warnings": ["no git repositories found in configured search paths"],
            }
        return {"ok": True, "status": "healthy", "data": {"repos": repos}}

    @app.get("/api/source-control/history", dependencies=[Depends(require_auth)])
    async def source_control_history(repo: str, limit: int = 20) -> dict:
        """Newest-first commit history for ONE discovered repository
        (native git, read-only). Unconfigured search paths or an unknown
        repo name answer not_configured — a structured miss, not a crash."""
        paths = _sc_paths()
        if not paths:
            return {
                "ok": False,
                "status": "not_configured",
                "warnings": ["no source_control search paths configured"],
            }
        matches = [
            e
            for e in discover_repositories(paths)
            if e["is_repository"] and e["name"] == repo
        ]
        if not matches:
            return {
                "ok": False,
                "status": "not_configured",
                "warnings": [
                    f"repository '{repo}' not found in configured search paths"
                ],
            }
        commits = repository_history(matches[0]["path"], limit)
        return {
            "ok": True,
            "status": "healthy",
            "data": {"repo": repo, "commits": commits},
        }

    # ── First propose→approve→act workflow (Finish Line "Actions,
    # approvals, and trusted automation"). The FIRST action is
    # intentionally low-risk: re-run the native read-only git status
    # for ONE repository. Agreement is not authorization: the client
    # must show what/why/tool/risk/expected and collect an explicit
    # approval BEFORE this endpoint is called; the endpoint itself is
    # the act (step-up gated). The audit answer — who proposed (the UI
    # proposal), what was approved (the named repo refresh), what
    # happened, which tool (the native git baseline), what came back,
    # and when (provenance timestamp) — is journaled as a
    # PROVIDER_ACTION; no secrets, no paths beyond the repo name. ──
    @app.post("/api/source-control/refresh", dependencies=[Depends(require_step_up)])
    async def source_control_refresh(request: Request) -> dict:
        """Act step of the propose→approve→act refresh: re-runs the native
        read-only git status for ONE named repository. Requires step-up
        elevation; every outcome is journaled (a completed act as
        PROVIDER_ACTION, a rejection or git error as FAILURE — repo name
        and state bits only, no secrets, no filesystem paths)."""
        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        repo = (body.get("repo") or "").strip() if isinstance(body, dict) else ""
        if not repo:
            raise HTTPException(status_code=400, detail="repo is required")
        paths = _sc_paths()
        matches = [
            e
            for e in discover_repositories(paths)
            if e["is_repository"] and e["name"] == repo
        ]
        if not matches:
            journal.record(
                JournalKind.FAILURE,
                f"proposed repository status refresh rejected: "
                f"repository '{repo}' not found in configured search paths",
                source="projects",
            )
            return {
                "ok": False,
                "status": "not_configured",
                "warnings": [
                    f"repository '{repo}' not found in configured search paths"
                ],
            }
        status = repository_status(matches[0]["path"])
        if status.get("error"):
            journal.record(
                JournalKind.FAILURE,
                f"repository status refresh ran for '{repo}' but git "
                f"reported: {status['error']}",
                source="projects",
            )
            return {
                "ok": False,
                "status": "unavailable",
                "warnings": [str(status["error"])],
            }
        state_bits = [
            f"branch {status.get('branch') or 'unknown'}",
            "uncommitted changes" if status.get("dirty") else "clean",
        ]
        if status.get("ahead") or status.get("behind"):
            state_bits.append(
                f"{status.get('ahead') or 0} ahead / {status.get('behind') or 0} behind"
            )
        journal.record(
            JournalKind.PROVIDER_ACTION,
            f"approved action: repository status refresh for '{repo}' "
            f"(proposed by the Projects screen, approved explicitly, "
            f"executed by the native git baseline) — "
            f"{', '.join(state_bits)}",
            source="projects",
        )
        return {
            "ok": True,
            "status": "healthy",
            "data": {"repo": repo, "status": status},
        }

    @app.get("/api/lab/state", dependencies=[Depends(require_auth)])
    async def lab_state() -> dict:
        """Operator packet from the homelab Lab CLI (lab-lowbw/1).

        Presentation-only: the packet is produced by the lab layer;
        this route never derives homelab state itself.
        """
        provider = LabState(lab_path=os.environ.get("PW_LAB_CLI", DEFAULT_LAB))
        r = provider.observe()
        if not r.ok:
            # Worlds usually runs where the lab CLI isn't: read the same
            # packet through the Engine room (GET /room/views/lowbw).
            status, packet = await _ROOMS.view("engine-room", "lowbw")
            if status == 200 and isinstance(packet, dict):
                r = provider.observe(packet)
        payload = {
            "ok": r.ok,
            "status": r.status,
            "data": r.data or {"rows": [], "reason": r.status},
        }
        if r.warnings:
            payload["warnings"] = r.warnings
        return payload

    @app.get("/api/lab/settings", dependencies=[Depends(require_auth)])
    async def lab_settings() -> dict:
        """Settings Reconciler status via lab CLI."""
        from .providers.lab_settings import LabSettings

        provider = LabState(lab_path=os.environ.get("PW_LAB_CLI", DEFAULT_LAB))
        settings = LabSettings(lab_path=provider.lab_path)
        r = settings.observe()
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.get(
        "/api/lab/settings/inspect/{service}", dependencies=[Depends(require_auth)]
    )
    async def lab_settings_inspect(service: str) -> dict:
        """Inspect desired state for a specific service."""
        from .providers.lab_settings import LabSettings

        provider = LabState(lab_path=os.environ.get("PW_LAB_CLI", DEFAULT_LAB))
        settings = LabSettings(lab_path=provider.lab_path)
        r = settings.inspect(service)
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.get("/api/lab/settings/diff/{service}", dependencies=[Depends(require_auth)])
    async def lab_settings_diff(service: str) -> dict:
        """Drift between desired and live state for a service."""
        from .providers.lab_settings import LabSettings

        provider = LabState(lab_path=os.environ.get("PW_LAB_CLI", DEFAULT_LAB))
        settings = LabSettings(lab_path=provider.lab_path)
        r = settings.diff(service)
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.get("/api/lab/health", dependencies=[Depends(require_auth)])
    async def lab_health() -> dict:
        """Health check across all services via lab CLI."""
        from .providers.lab_health import LabHealth

        provider = LabState(lab_path=os.environ.get("PW_LAB_CLI", DEFAULT_LAB))
        health = LabHealth(lab_path=provider.lab_path)
        r = health.observe()
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.get("/api/lab/deploy", dependencies=[Depends(require_auth)])
    async def lab_deploy() -> dict:
        """Deploy status and history via lab CLI."""
        from .providers.lab_deploy import LabDeploy

        provider = LabState(lab_path=os.environ.get("PW_LAB_CLI", DEFAULT_LAB))
        deploy = LabDeploy(lab_path=provider.lab_path)
        r = deploy.observe()
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.get("/api/lab/secrets", dependencies=[Depends(require_auth)])
    async def lab_secrets() -> dict:
        """Secret audit (names only, no values) via lab CLI."""
        from .providers.lab_secrets import LabSecrets

        provider = LabState(lab_path=os.environ.get("PW_LAB_CLI", DEFAULT_LAB))
        secrets = LabSecrets(lab_path=provider.lab_path)
        r = secrets.observe()
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.get("/api/lab/resources", dependencies=[Depends(require_auth)])
    async def lab_resources() -> dict:
        """VM resource usage via lab CLI."""
        from .providers.lab_resources import LabResources

        provider = LabState(lab_path=os.environ.get("PW_LAB_CLI", DEFAULT_LAB))
        resources = LabResources(lab_path=provider.lab_path)
        r = resources.observe()
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    # ── Worlds briefing + place continuity (contract: worlds-briefing/1) ──
    # The briefing is what the world knows; place is where the person last
    # was, so a later visit can say "arrived while you were away". Both are
    # person-only (agents are refused) and both ride the per-principal
    # scoped entry point (decision #13) — place exactly mirrors the journal-draft
    # entry point: no step-up (it mutates nothing a visit doesn't already imply),
    # atomic os.replace, never a response echo of more than it stored.
    _PLACE_MAX_BYTES = 2048
    _PLACE_ITEM_MAX = 200

    def _place_path(request: Request) -> Path:
        return _scoped_path(request.state.principal, "last_place")

    def _read_place(request: Request) -> dict | None:
        """The stored place, or a None. A corrupt/foreign file is
        never guessed at: the caller sees no place rather than a false claim."""
        path = _place_path(request)
        if not path.exists():
            return None
        try:
            stored = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(stored, dict):
            return None
        system = stored.get("system")
        item_id = stored.get("item_id")
        if system is not None and system not in SYSTEM_IDS:
            return None
        if item_id is not None and not isinstance(item_id, str):
            return None
        updated_at = stored.get("updated_at")
        if not isinstance(updated_at, str) or not updated_at:
            return None
        return {"system": system, "item_id": item_id, "updated_at": updated_at}

    @app.get("/api/briefing", dependencies=[Depends(require_auth)])
    async def briefing_view(request: Request) -> dict:
        """The world's briefing: six systems, have_tos, arrivals, thread.

        Read-only: a view never journals and never writes the place. The
        stored place's updated_at becomes `since` (the previous visit).
        Person-only, caller-scoped.
        """
        principal = getattr(request.state, "principal", None)
        _require_person(principal)
        world, _, uj = _state_for(request)
        journal_target = journal if uj == journal.path else Journal(uj)
        place = _read_place(request)

        # One rooms read per request, sharing the same 15 s cache (and 2 s
        # per-room timeout) as GET /api/rooms — never a second HTTP round.
        # Caller-aware: forwarding rooms answer for THIS person, while
        # their health stays estate-wide. The snapshot never raises and
        # never claims a dead room healthy.
        rooms = await _ROOMS.snapshot_for_principal(principal)

        def _compose() -> dict:
            # Who is credited (the Keeper and each system's resident) is
            # resolved per caller from THIS person's prefs and crew. Each
            # read is guarded on its own so a failed read confirms nobody —
            # the fallback — rather than breaking the briefing.
            try:
                pref_values = prefs.get_prefs(world)
            except Exception:
                pref_values = None
            try:
                _, crew_state = _crew_state(request)
            except Exception:
                crew_state = None
            return build_briefing(
                project_home=ProjectHomeSource.from_env(),
                lab=LabState(lab_path=os.environ.get("PW_LAB_CLI", DEFAULT_LAB)),
                journal=journal_target,
                place=place,
                rooms=rooms,
                name_hint=getattr(principal, "display_name", None),
                crew_state=crew_state,
                pref_values=pref_values,
            )

        # Sources shell out / fetch; keep the event loop free.
        return await run_in_threadpool(_compose)

    def _rooms_visit_path(request: Request) -> Path:
        """The caller's own visit-state file (per-principal entry point)."""
        return _scoped_path(request.state.principal, "rooms_visits")

    def _room_configured(room_id: str) -> bool:
        """An id is addressable only if the resolved room list named it.

        The list is the registry's latest snapshot when one is
        configured, else ``PW_ROOMS`` (Gap 1: rooms are read at runtime).
        """
        return room_id in _ROOMS.known_ids()

    def _configured_room_ids() -> list[str]:
        """The resolved room ids, in snapshot (registry or env) order."""
        return _ROOMS.known_ids()

    def _crew_path(request: Request, principal=None) -> Path:
        """A person's crew registry file (per-principal entry point).

        Defaults to the caller; a helping request passes the person it
        acts for so the crew it reads is that person's own.
        """
        if principal is None:
            principal = request.state.principal
        return _scoped_path(principal, "crew")

    def _crew_state(request: Request, principal=None) -> tuple[Path, dict]:
        """``(path, state)`` for a person's crew, starter-seeded.

        The configured room ids ride along so the canon keeper defaults can
        be seeded for the rooms that name a system — and only those.
        """
        path = _crew_path(request, principal)
        return path, crew.read_crew(path, room_ids=_configured_room_ids())

    def _crew_text(
        body: dict, key: str, cap: int, *, required: bool = False
    ) -> str | None:
        """A bounded string field from a crew body, or 422.

        Strings only, trimmed; an omitted/empty optional field is None
        (never ``""``), and an over-length value is refused rather than
        silently truncated into a different one.
        """
        if key not in body:
            if required:
                raise HTTPException(status_code=422, detail=f"{key} is required")
            return None
        value = body[key]
        if value is None or value == "":
            if required:
                raise HTTPException(
                    status_code=422, detail=f"{key} must be a string"
                )
            return None
        if not isinstance(value, str):
            raise HTTPException(status_code=422, detail=f"{key} must be a string")
        value = value.strip()
        if not value:
            if required:
                raise HTTPException(
                    status_code=422, detail=f"{key} must not be empty"
                )
            return None
        if len(value) > cap:
            raise HTTPException(
                status_code=422,
                detail=f"{key} must be at most {cap} characters",
            )
        return value

    async def _json_body(request: Request) -> dict:
        """One JSON object as the request body, or 422 (never a 500)."""
        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=422, detail="body must be JSON") from _err
        if body is None:
            return {}
        if not isinstance(body, dict):
            raise HTTPException(status_code=422, detail="body must be an object")
        return body

    @app.get("/api/rooms", dependencies=[Depends(require_auth)])
    async def rooms_view(request: Request) -> dict:
        """The estate's rooms (contract: room/0) plus the caller's visit state.

        One row per configured room — its descriptor, cards, the
        needs it is charging attention for, whether it is reachable, and
        when it was last reached (persisted across restarts). Each row
        also carries the CALLER's private, Worlds-owned visit fields:
        ``last_visited_at``, ``needs_seen`` and ``changed_since_visit``,
        plus ``keeper`` — the companion the caller put on that room, or an
        ``null`` — and ``doorway`` — the presentation-only doorway
        id the caller chose, or a ``null``. Neither a keeper nor a
        doorway changes the room's status; status still comes only from
        the room. ``resume`` and ``summary`` travel
        as siblings of ``data`` so the existing list envelope stays
        byte-compatible. Fetching is concurrent with a 2 s per-request
        timeout and the snapshot is cached 15 s. This handler never raises
        on a room's behalf: an unreachable room is reported
        ``reachable: false`` with its last-seen time, never claimed
        healthy.

        A room whose registry entry opts in with ``forward_principal``
        (and that has its own token) also learns WHO is asking, so its
        cards and needs are fetched and cached per caller; another
        caller's forwarded cards/needs can never appear here, while the
        room's status/reachability/last-seen stay estate-wide.

        The room list itself is read at runtime: when a registry is
        configured (``PW_ROOMS_REGISTRY_URL``) it is refreshed on the
        snapshot cadence, so adding or removing a registry room takes
        effect on the next refresh with no restart. A new sibling
        ``registry`` states where the list came from and whether the
        registry read was ok, unreachable or not configured — additive:
        the existing ``data``/``resume``/``summary`` envelope is
        unchanged.

        With an ``X-Worlds-Helping: <person>`` header and a live grant,
        a helper sees THIS person's needs and their own visit state and
        crew; without a live grant the request is refused 403.
        """
        helping = _helping_target(request, need_act=False)
        effective = helping if helping is not None else (
            getattr(request.state, "principal", None)
        )
        rows = await _ROOMS.snapshot_for_principal(effective)
        # A helping request reads the helped person's own visit state and
        # crew, so the needs and resume are theirs, not the helper's.
        visit_path = (
            _scoped_path(effective, "rooms_visits")
            if helping is not None
            else _rooms_visit_path(request)
        )
        state = rooms_visits.read_visits(visit_path)
        _, crew_state = _crew_state(request, helping)
        decorated = [
            crew.decorate_row(rooms_visits.decorate_row(row, state), crew_state)
            for row in rows
        ]
        return {
            "ok": True,
            "data": decorated,
            "resume": rooms_visits.resume_of(state),
            "summary": rooms_visits.summarize(decorated, state),
            "registry": _ROOMS.registry_report(),
        }

    @app.post("/api/rooms/{room_id}/changed", dependencies=[Depends(require_auth)])
    async def rooms_changed(room_id: str, request: Request) -> dict:
        """A room says its data changed (the live half of a two-way room).

        Worlds forgets what it cached for that room and tells open
        screens (``GET /api/rooms/events``), so they re-read it within
        seconds instead of waiting for the next refresh. Callers: an
        agent token with the ``notify`` scope (a room's own sync job), or
        someone who may ``approve``. The body is ignored: a ping carries
        no content, so it can only cause a re-read. Unknown room → 404;
        pings closer than 2 s fold into one.
        """
        principal = _principal(request)
        allowed = principal is not None and (
            ("notify" in (principal.scopes or ()))
            if principal.kind == "agent"
            else can(principal, "approve")
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="the notify scope is required")
        if not await _ROOMS.room_changed(room_id):
            raise HTTPException(status_code=404, detail="unknown room")
        return {"ok": True, "data": {"room_id": room_id}}

    @app.get("/api/rooms/events", dependencies=[Depends(require_auth)])
    async def rooms_events(request: Request) -> StreamingResponse:
        """Server-sent events: ``room-changed`` with ``{room, at}`` whenever
        a room pings or an action in Worlds changes it. Room ids only,
        never content. A comment line every 20 s keeps proxies from
        closing the stream; the browser's EventSource reconnects on its
        own."""
        queue = _ROOMS.listen()

        async def stream():
            try:
                yield "retry: 5000\n\n"
                while True:
                    if await request.is_disconnected():
                        return
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=20)
                    except TimeoutError:
                        yield ": still here\n\n"
                        continue
                    yield f"event: room-changed\ndata: {json.dumps(event)}\n\n"
            finally:
                _ROOMS.unlisten(queue)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/library", dependencies=[Depends(require_auth)])
    async def library_home(request: Request) -> dict:
        """The Library's connected shelves: every room that keeps a library
        (Play-Nice ``library/0``), one row each, ``{room, status, library?,
        error?}``. Worlds' own books are bundled into the app, so they are
        not here. A library that can't be read is a row with plain words,
        never a missing shelf or a 500."""
        rows = await _ROOMS.libraries(getattr(request.state, "principal", None))
        return {"ok": True, "data": rows}

    @app.get("/api/rooms/{room_id}/art/{name}.webp", dependencies=[Depends(require_auth)])
    async def rooms_art(room_id: str, name: str) -> Response:
        """A room's picture (e.g. a Hive Works crew face), passed through
        because an image can't carry the room's token. WebP only, checked
        by its header bytes; anything else is a 404."""
        data = await _ROOMS.art(room_id, name)
        if data is None:
            raise HTTPException(status_code=404, detail="no such picture")
        return Response(
            data,
            media_type="image/webp",
            headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/api/rooms/{room_id}/views/{name}", dependencies=[Depends(require_auth)])
    @app.get("/api/rooms/{room_id}/views/{name}/{item}", dependencies=[Depends(require_auth)])
    async def rooms_view_one(
        room_id: str, name: str, request: Request, item: str | None = None
    ) -> JSONResponse:
        """A room's own read-only view, e.g. Hive Works' teams, projects,
        one project or crew (``GET /room/views/{name}[/{item}]`` on the
        room). Passed through as the room's JSON under ``data``; an
        unknown room or view is 404 and an unreadable one 502, with
        plain words. Links inside are the room's same-origin paths; the
        UI opens them on the room's own address."""
        status, payload = await _ROOMS.view(
            room_id, name, item, getattr(request.state, "principal", None)
        )
        if status == 200:
            return JSONResponse({"ok": True, "data": payload})
        return JSONResponse({"ok": False, "error": payload.get("error")}, status_code=status)

    @app.get("/api/secrets/overview", dependencies=[Depends(require_auth)])
    async def secrets_overview_view(request: Request) -> dict:
        """The Secrets board's read-only data source (Worlds side).

        Finds the room named ``workshop`` and reads its read-only
        ``GET /api/secrets/summary`` with that room's token/TLS policy
        (3 s timeout, cached 60 s). Names and health only — never a
        secret value. Nothing is invented: a missing, unreachable,
        refusing (401) or malformed station is reported as
        ``station.status: "unknown"`` with a plain-words detail and empty
        lists. This handler never raises, never carries a token, and
        never carries a key value.
        """
        # Secret names are the estate's business, not every household
        # member's: the `estate_secrets` permission (owner and admin).
        principal = getattr(request.state, "principal", None)
        if not can(principal, "estate_secrets"):
            raise HTTPException(status_code=403, detail="estate secrets required")
        data = await _ROOMS.secrets_overview()
        return {"ok": True, "data": data}

    @app.post("/api/rooms/{room_id}/visit", dependencies=[Depends(require_auth)])
    async def rooms_visit(room_id: str, request: Request) -> dict:
        """Record the caller's visit to a room (Worlds-owned, private).

        Updates the caller's ``last_visited_at`` for the room and the
        top-level ``resume``. Idempotent in effect: repeating converges
        on one stored visit. No step-up — a visit mutates nothing a
        visit doesn't already imply (same setting as drafts/place). An
        unconfigured room id is a 404; ``link`` must be a same-origin
        path or it is refused 422 rather than stored.
        """
        if not _room_configured(room_id):
            raise HTTPException(status_code=404, detail="unknown room")
        body = await _json_body(request)
        link = body.get("link")
        if link is not None and not rooms_visits.valid_same_origin_link(link):
            raise HTTPException(
                status_code=422, detail="link must be a same-origin path"
            )
        title = body.get("title")
        if title is not None:
            if not isinstance(title, str):
                raise HTTPException(status_code=422, detail="title must be a string")
            title = title.strip()[: rooms_visits.TITLE_MAX] or None
        # Full precision: a card observed later in the same second as the
        # visit must not count as "changed since your visit".
        at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="microseconds")
        path = _rooms_visit_path(request)
        state = rooms_visits.read_visits(path)
        rooms_visits.record_visit(state, room_id, at=at, link=link, title=title)
        rooms_visits.write_visits(path, state)
        return {
            "ok": True,
            "data": {
                "room_id": room_id,
                "last_visited_at": at,
                "resume": rooms_visits.resume_of(state),
            },
        }

    @app.post(
        "/api/rooms/{room_id}/needs/{need_id}/seen",
        dependencies=[Depends(require_auth)],
    )
    async def rooms_need_seen(room_id: str, need_id: str, request: Request) -> dict:
        """Mark one need seen for the caller (private, per room).

        Adds ``need_id`` to the caller's ``needs_seen`` list for the
        room, deduped and capped. Idempotent: marking twice changes
        nothing. Unconfigured room → 404; an empty/oversized id → 422.
        """
        if not _room_configured(room_id):
            raise HTTPException(status_code=404, detail="unknown room")
        need_id = need_id.strip()
        if not need_id or len(need_id) > rooms_visits.NEED_ID_MAX:
            raise HTTPException(
                status_code=422, detail="need_id must be 1-200 chars"
            )
        path = _rooms_visit_path(request)
        state = rooms_visits.read_visits(path)
        rooms_visits.mark_need_seen(state, room_id, need_id)
        rooms_visits.write_visits(path, state)
        return {
            "ok": True,
            "data": {
                "room_id": room_id,
                "need_id": need_id,
                "needs_seen": list(state["rooms"][room_id]["needs_seen"]),
            },
        }

    @app.post(
        "/api/rooms/{room_id}/actions/{action_id}",
        dependencies=[Depends(require_auth)],
    )
    async def rooms_action(
        room_id: str, action_id: str, request: Request
    ) -> JSONResponse:
        """Pass one room/0 action through to its room; return its receipt.

        A write needs the ``approve`` permission (the room's own ``GET
        /room/actions`` list, cached 60 s per room, says whether the
        action exists and whether it writes; 403 otherwise), and an
        unknown action is a 404 — both as a plain-words receipt. A valid
        ``Idempotency-Key`` header is required (400 when missing), the
        body is a JSON object of at most 16 KB (413/400 otherwise), and
        the call is forwarded to the room with the room's own token, the
        caller's ``X-Worlds-Principal``, and that key — never the human
        session or ``PW_API_TOKEN``. The room's answer is allow-listed to
        a receipt and returned with HTTP 200 whatever the room's status;
        a room that cannot answer yields an ``ok: false``
        "nothing changed" receipt, never a 500. A successful action drops
        the cached snapshot so the need disappears on the next
        ``GET /api/rooms``.

        With an ``X-Worlds-Helping: <person>`` header and a live
        ``can_act`` grant, a helper performs the action as that person
        and the action is recorded in that person's "helped by" log;
        without a live grant the request is refused 403.
        """
        caller = getattr(request.state, "principal", None)
        # A helper acting for someone needs `act_for`, not the person's
        # own `approve`; any other call is unchanged.
        helping = _helping_target(request, need_act=True)
        principal = helping if helping is not None else caller
        body = await request.body()
        status, receipt = await _ROOMS.perform_action(
            room_id=room_id,
            action_id=action_id,
            principal=principal,
            idempotency_key=request.headers.get(ROOMS_IDEMPOTENCY_HEADER),
            body=body,
            allow_write=helping is not None,
        )
        if helping is not None and receipt.get("ok"):
            # Every action a helper takes for a person is recorded in
            # that person's own "helped by" log. The receipt's own
            # `undoable` is false unless a room ever sends one.
            _helper_log.append(
                helping.id,
                {
                    "at": receipt.get("at"),
                    "helper_id": caller.id if caller is not None else None,
                    "action": action_id,
                    "summary": receipt.get("summary") or "",
                    "undoable": bool(receipt.get("undoable", False)),
                },
            )
        return JSONResponse(
            status_code=status,
            content={"ok": status == 200, "data": receipt},
        )

    # ── Crew: companions are user-owned (owner decision 2026-09-25) ─────
    # The person's own crew registry and keepers: private, per principal,
    # never sent to a room or a model. Stored on the same per-principal
    # JSON entry point as every other Worlds state file (kind "crew"). The drawn
    # crew is a STARTER set — add, rename, hide, delete; a room may have
    # no companion at all. Sol is the Worlds mark, never a crew entry.

    @app.get("/api/crew", dependencies=[Depends(require_auth)])
    async def crew_view(request: Request) -> dict:
        """The caller's own crew, starter-seeded on first read.

        roster: every entry is a companion the person has (drawn or
        their own), including hidden ones — the main app decides what to
        filter. An emptied roster stays empty.
        """
        _, state = _crew_state(request)
        return {"ok": True, "data": list(state["crew"])}

    @app.post("/api/crew", dependencies=[Depends(require_auth)])
    async def crew_add(request: Request) -> dict:
        """Add a companion of the caller's own (``source: "user"``).

        Body: ``{name, blurb?, voice_label?}``. The id is a slug of the
        name made unique against the caller's roster. Same auth setting as
        the other POST routes; no step-up — a roster entry mutates nothing
        a visit doesn't already imply.
        """
        body = await _json_body(request)
        name = _crew_text(body, "name", crew.NAME_MAX, required=True)
        blurb = _crew_text(body, "blurb", crew.BLURB_MAX)
        voice_label = _crew_text(body, "voice_label", crew.VOICE_LABEL_MAX)
        path, state = _crew_state(request)
        entry = crew.add(state, name=name, blurb=blurb, voice_label=voice_label)
        crew.write_crew(path, state)
        return {"ok": True, "data": entry}

    @app.patch("/api/crew/{companion_id}", dependencies=[Depends(require_auth)])
    async def crew_patch(companion_id: str, request: Request) -> dict:
        """Rename/reword/hide one companion (drawn crew included).

        Body may carry ``name``, ``blurb``, ``voice_label`` and ``hidden``;
        omitted keys are untouched and an explicit ``null`` clears an
        optional text field. Unknown id → 404. Hiding is a roster act: it
        never changes a room's status and never unassigns a keeper.
        """
        path, state = _crew_state(request)
        entry = crew.find(state, companion_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="unknown companion")
        body = await _json_body(request)
        if "name" in body:
            entry["name"] = _crew_text(body, "name", crew.NAME_MAX, required=True)
        if "blurb" in body:
            entry["blurb"] = _crew_text(body, "blurb", crew.BLURB_MAX)
        if "voice_label" in body:
            entry["voice_label"] = _crew_text(
                body, "voice_label", crew.VOICE_LABEL_MAX
            )
        if "hidden" in body:
            hidden = body["hidden"]
            if not isinstance(hidden, bool):
                raise HTTPException(
                    status_code=422, detail="hidden must be a boolean"
                )
            entry["hidden"] = hidden
        crew.write_crew(path, state)
        return {"ok": True, "data": entry}

    @app.delete("/api/crew/{companion_id}", dependencies=[Depends(require_auth)])
    async def crew_delete(companion_id: str, request: Request) -> dict:
        """Delete one of the caller's own companions, or refuse a starter.

        The drawn crew is kept: 409, hide it instead. Deleting a companion
        clears the keeper assignments it held (the rooms stay configured
        and simply have no companion) and removes its uploaded portrait.
        """
        path, state = _crew_state(request)
        entry = crew.find(state, companion_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="unknown companion")
        if crew.is_starter(entry):
            raise HTTPException(
                status_code=409,
                detail="starter companions cannot be deleted; hide it instead",
            )
        _, cleared = crew.remove(state, companion_id)
        crew.delete_portrait(path, companion_id)
        crew.write_crew(path, state)
        return {
            "ok": True,
            "data": {
                "id": companion_id,
                "deleted": True,
                "keepers_cleared": cleared,
            },
        }

    @app.put("/api/rooms/{room_id}/keeper", dependencies=[Depends(require_auth)])
    async def rooms_keeper(room_id: str, request: Request) -> dict:
        """Assign (or clear) the caller's keeper for one configured room.

        Body: ``{companion_id}`` — an existing companion id, or ``null``
        for "no companion". One keeper per room; a companion may keep
        several rooms. Unconfigured room → 404; unknown companion → 422.
        This records who the person put there and nothing else: the room's
        status is never touched by an assignment.
        """
        if not _room_configured(room_id):
            raise HTTPException(status_code=404, detail="unknown room")
        body = await _json_body(request)
        if "companion_id" not in body:
            raise HTTPException(
                status_code=422, detail="companion_id is required"
            )
        companion_id = body["companion_id"]
        if companion_id is not None and not isinstance(companion_id, str):
            raise HTTPException(
                status_code=422, detail="companion_id must be a string or null"
            )
        path, state = _crew_state(request)
        if companion_id is not None and crew.find(state, companion_id) is None:
            raise HTTPException(status_code=422, detail="unknown companion")
        state.setdefault("keepers", {})[room_id] = companion_id
        crew.write_crew(path, state)
        return {
            "ok": True,
            "data": {
                "room_id": room_id,
                "keeper": crew.keeper_of(state, room_id),
            },
        }

    @app.put("/api/rooms/{room_id}/doorway", dependencies=[Depends(require_auth)])
    async def rooms_doorway(room_id: str, request: Request) -> dict:
        """Choose (or clear) the caller's doorway for one configured room.

        Body: ``{doorway_id}`` — an id from the closed
        :data:`crew.DOORWAYS` list, or ``null`` for "no doorway". A
        doorway is presentation only: it records which door the person
        sees for the room and nothing else — private, per principal,
        never sent to the room and never a status. Unconfigured room →
        404; an id outside the closed list (or not a string/null) → 422.
        """
        if not _room_configured(room_id):
            raise HTTPException(status_code=404, detail="unknown room")
        body = await _json_body(request)
        if "doorway_id" not in body:
            raise HTTPException(status_code=422, detail="doorway_id is required")
        doorway_id = body["doorway_id"]
        if doorway_id is not None and not crew.is_doorway(doorway_id):
            raise HTTPException(
                status_code=422,
                detail="doorway_id must be one of: " + ", ".join(crew.DOORWAYS),
            )
        path, state = _crew_state(request)
        state.setdefault("doorways", {})[room_id] = doorway_id
        crew.write_crew(path, state)
        return {
            "ok": True,
            "data": {
                "room_id": room_id,
                "doorway": crew.doorway_of(state, room_id),
            },
        }

    @app.post(
        "/api/crew/{companion_id}/portrait",
        dependencies=[Depends(require_auth)],
    )
    async def crew_portrait_upload(companion_id: str, request: Request) -> dict:
        """Store a portrait for one companion (private, caller-scoped).

        Body: ``{content_type, data_base64}``. PNG/JPEG/WebP only, and the
        *bytes* must be that format — the declared type is checked against
        the magic numbers, so a fake extension is refused 415. Decoded
        size over 5 MB → 413. The bytes land in the caller's own scoped
        data directory (never a new store) and the entry's
        ``portrait_asset`` then points at the same-origin route below.
        """
        path, state = _crew_state(request)
        entry = crew.find(state, companion_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="unknown companion")
        body = await _json_body(request)
        content_type = body.get("content_type")
        if content_type not in crew.ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=415,
                detail="content_type must be one of "
                + ", ".join(crew.ALLOWED_IMAGE_TYPES),
            )
        data, error = crew.decode_portrait(body.get("data_base64"))
        if error == "too_large":
            raise HTTPException(
                status_code=413,
                detail=f"portrait exceeds {crew.PORTRAIT_MAX_BYTES} bytes",
            )
        if error is not None:
            raise HTTPException(
                status_code=422, detail="data_base64 must be valid base64"
            )
        if crew.sniff_image_type(data) != content_type:
            raise HTTPException(
                status_code=415, detail="image bytes do not match content_type"
            )
        # The stored id — a validated slug — is what touches the
        # filesystem; the raw path parameter never does.
        crew.write_portrait(
            path, entry["id"], data, crew.EXT_FOR_TYPE[content_type]
        )
        entry["portrait_asset"] = crew.PORTRAIT_ROUTE.format(id=entry["id"])
        crew.write_crew(path, state)
        return {"ok": True, "data": entry}

    @app.get(
        "/api/crew/{companion_id}/portrait",
        dependencies=[Depends(require_auth)],
    )
    async def crew_portrait_get(companion_id: str, request: Request) -> Response:
        """Serve an uploaded portrait same-origin, privately.

        ``Cache-Control: private`` and ``X-Content-Type-Options: nosniff``
        with the type the *stored bytes* are (never a declared one). No
        uploaded portrait, or an unknown companion → 404 — the shipped
        asset path is what the main app uses until someone uploads.
        """
        path, state = _crew_state(request)
        entry = crew.find(state, companion_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="unknown companion")
        stored = crew.find_portrait(path, entry["id"])
        if stored is None:
            raise HTTPException(status_code=404, detail="no uploaded portrait")
        return FileResponse(
            stored,
            media_type=crew.image_type_for_path(stored),
            headers={
                "Cache-Control": "private",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.delete(
        "/api/crew/{companion_id}/portrait",
        dependencies=[Depends(require_auth)],
    )
    async def crew_portrait_delete(companion_id: str, request: Request) -> dict:
        """Remove an uploaded portrait.

        A drawn companion falls back to its shipped portrait path; a
        person's own companion falls back to no portrait at all. Nothing
        uploaded → 404.
        """
        path, state = _crew_state(request)
        entry = crew.find(state, companion_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="unknown companion")
        if not crew.delete_portrait(path, entry["id"]):
            raise HTTPException(status_code=404, detail="no uploaded portrait")
        entry["portrait_asset"] = (
            crew.starter_portrait_asset(entry["id"])
            if crew.is_starter(entry)
            else None
        )
        crew.write_crew(path, state)
        return {"ok": True, "data": entry}

    @app.get("/api/place", dependencies=[Depends(require_auth)])
    def place_get(request: Request) -> dict:
        """The caller's last place, or a null."""
        _require_person(getattr(request.state, "principal", None))
        return {"ok": True, "data": {"place": _read_place(request)}}

    @app.put("/api/place", dependencies=[Depends(require_auth)])
    async def place_put(request: Request) -> dict:
        """Store the caller's last place. No step-up: continuity mutates
        nothing a visit doesn't already imply (same setting as drafts)."""
        _require_person(getattr(request.state, "principal", None))
        raw = await request.body()
        if len(raw) > _PLACE_MAX_BYTES:
            raise HTTPException(status_code=422, detail="place payload exceeds 2048 bytes")
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError as _err:
            raise HTTPException(status_code=422, detail="place body must be JSON") from _err
        if not isinstance(body, dict):
            raise HTTPException(status_code=422, detail="place body must be an object")
        system = body.get("system")
        if system is not None and system not in SYSTEM_IDS:
            raise HTTPException(status_code=422, detail="unknown system")
        item_id = body.get("item_id")
        if item_id is not None and not isinstance(item_id, str):
            raise HTTPException(status_code=422, detail="item_id must be a string or null")
        if isinstance(item_id, str) and len(item_id) > _PLACE_ITEM_MAX:
            raise HTTPException(status_code=422, detail="item_id exceeds 200 chars")
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        place = {"system": system, "item_id": item_id, "updated_at": stamp}
        path = _place_path(request)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(place))
        tmp.chmod(0o600)
        os.replace(tmp, path)  # atomic: a crash never leaves half a place
        return {"ok": True, "data": {"place": place}}

    # --- Native Reconciler endpoints ---

    # --- Media endpoints ---
    from .connection_manager import resolve_media_connections
    from .providers.native_media import (
        MEDIA_CONNECTION_TYPES,
        build_media_engine_from_connections,
    )

    def _build_media_engine():
        """Build media engine from MERGED connection config through the
        canonical construction helper (connection dicts, not adapters).

        Resolves both:
        - connections[] entries (tracked config, provider shape)
        - flat UI config (connections.local.json, schema-driven shape)
        """
        config = conn_mgr.get_all_config()
        connections = [
            conn
            for conn in config.get("connections", [])
            if isinstance(conn, dict) and conn.get("type") in MEDIA_CONNECTION_TYPES
        ]

        # Flat UI config saved under "media" key
        media_raw = config.get("media", {})
        if media_raw and media_raw.get("_adapter"):
            connections.extend(
                conn
                for conn in resolve_media_connections(media_raw)
                if isinstance(conn, dict) and conn.get("type") in MEDIA_CONNECTION_TYPES
            )

        return build_media_engine_from_connections(connections)

    @app.get("/api/media/status", dependencies=[Depends(require_auth)])
    async def media_status():
        engine = _build_media_engine()
        r = engine.status()
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.get("/api/media/library", dependencies=[Depends(require_auth)])
    async def media_library():
        engine = _build_media_engine()
        r = engine.library()
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.get("/api/media/recent", dependencies=[Depends(require_auth)])
    async def media_recent():
        engine = _build_media_engine()
        r = engine.recent()
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.get("/api/media/activity", dependencies=[Depends(require_auth)])
    async def media_activity():
        engine = _build_media_engine()
        r = engine.activity()
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.get("/api/media/search", dependencies=[Depends(require_auth)])
    async def media_search(q: str = ""):
        engine = _build_media_engine()
        r = engine.search(q)
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.get("/api/reconciler/status", dependencies=[Depends(require_auth)])
    async def reconciler_status() -> dict:
        """Native Reconciler status."""
        from .providers.native_reconciler import NativeSettingsReconciler

        reconciler = NativeSettingsReconciler()
        r = reconciler.observe()
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    async def _observed_from_request(request: Request) -> dict:
        """Best-effort applied-state body: absent/invalid JSON is an
        EMPTY observed state, not a 500."""
        try:
            body = await request.json()
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {}

    @app.get("/api/reconciler/diff/{service}", dependencies=[Depends(require_auth)])
    async def reconciler_diff(service: str, request: Request) -> dict:
        """Compute drift between desired and observed state."""
        from .providers.native_reconciler import NativeSettingsReconciler

        reconciler = NativeSettingsReconciler()
        observed = await _observed_from_request(request)
        r = reconciler.diff(service, observed)
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.get("/api/reconciler/propose/{service}", dependencies=[Depends(require_auth)])
    async def reconciler_propose(service: str, request: Request) -> dict:
        """Propose reconciliation actions."""
        from .providers.native_reconciler import NativeSettingsReconciler

        reconciler = NativeSettingsReconciler()
        observed = await _observed_from_request(request)
        r = reconciler.propose(service, observed)
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    # --- Vault endpoints ---

    @app.get("/api/vault/status", dependencies=[Depends(require_auth)])
    async def vault_status() -> dict:
        """Vault status: locked/unlocked, secret count. Never values.

        Reports actual encryption capability — not a hardcoded claim.
        """
        warning = _vault.warning
        data = {
            "locked": not _vault.is_unlocked,
            "encrypted": getattr(_vault, "_fernet", None) is not None,
        }
        if warning:
            data["warning"] = warning
        return {"ok": True, "data": data}

    @app.post("/api/vault/unlock", dependencies=[Depends(require_auth)])
    async def vault_unlock(request: Request) -> dict:
        """Unlock the vault with a master passphrase."""
        body = await request.json()
        passphrase = body.get("passphrase", "")
        if not passphrase:
            raise HTTPException(status_code=400, detail="passphrase required")
        r = _vault.unlock(passphrase)
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.post("/api/vault/lock", dependencies=[Depends(require_auth)])
    async def vault_lock() -> dict:
        """Lock the vault, clearing secrets from memory."""
        _vault.lock()
        return {"ok": True, "data": {"locked": True}}

    @app.get("/api/vault/names", dependencies=[Depends(require_auth)])
    async def vault_names() -> dict:
        """List secret names (never values). Requires unlocked vault."""
        try:
            return {"ok": True, "data": {"names": _vault.list_names()}}
        except RuntimeError as _err:
            raise HTTPException(status_code=409, detail="vault is locked") from _err

    @app.post(
        "/api/vault/set", dependencies=[Depends(require_auth), Depends(require_step_up)]
    )
    async def vault_set(request: Request) -> dict:
        """Store a secret. Body: {name, value}. Step-up gated (owner decision)."""
        body = await request.json()
        name = body.get("name")
        value = body.get("value")
        if not name or value is None:
            raise HTTPException(status_code=400, detail="name and value required")
        r = _vault.set(name, value)
        if not r.ok:
            return {"ok": r.ok, "status": r.status, "warnings": r.warnings}
        return {"ok": True, "data": {"name": name}}

    @app.get("/api/vault/{name}", dependencies=[Depends(require_auth)])
    async def vault_get(name: str, request: Request) -> dict:
        """Read a single secret value. True-loopback-host-only AND
        person-only: the requester must be a local person — requests
        from a non-loopback Remote-Addr are refused (RFC1918/Docker
        bridge addresses included), and agent principals are refused
        even on loopback — keeping secret-value extraction a local,
        human-owner operation (browser/keys never cross the wire to
        another host or an agent). Each retrieval audited to the
        journal with the NAME only."""
        principal = getattr(request.state, "principal", None)
        if not _is_true_loopback(request):
            client = request.client.host if request.client else "?"
            raise HTTPException(
                status_code=403,
                detail=f"vault GET is loopback-only (client={client})",
            )
        _require_person(principal)
        try:
            value = _vault.get(name)
        except RuntimeError as _err:
            raise HTTPException(status_code=409, detail="vault is locked") from _err
        if value is None:
            raise HTTPException(status_code=404, detail=f"{name} not found")
        journal.record(
            kind=JournalKind.OBSERVATION,
            summary=f"vault get (name-only): {name}",
            source="api",
        )

        return {"ok": True, "data": {"name": name, "value": value}}

    @app.delete(
        "/api/vault/{name}",
        dependencies=[Depends(require_auth), Depends(require_step_up)],
    )
    async def vault_delete(name: str) -> dict:
        """Delete a secret by name. Step-up gated (owner decision)."""
        r = _vault.delete(name)
        if not r.ok:
            return {"ok": r.ok, "status": r.status, "warnings": r.warnings}
        return {"ok": True, "data": {"name": name}}

    # --- Theme pack endpoints ---

    @app.get("/api/themes", dependencies=[Depends(require_auth)])
    async def themes_list() -> dict:
        """List available theme packs."""
        from .theme_pack import ThemePackRegistry

        registry = ThemePackRegistry(data_dir / "theme-packs")
        packs = registry.list_packs()
        return {
            "ok": True,
            "data": [p.model_dump(mode="json") for p in packs],
        }

    @app.get("/api/themes/{name}", dependencies=[Depends(require_auth)])
    async def themes_get(name: str) -> dict:
        """Get a specific theme pack manifest."""
        from .theme_pack import ThemePackRegistry

        registry = ThemePackRegistry(data_dir / "theme-packs")
        pack = registry.get_or_none(name)
        if pack is None:
            raise HTTPException(status_code=404, detail=f"no theme pack named {name}")
        return {"ok": True, "data": pack.model_dump(mode="json")}

    # --- Brain Template System ---

    @app.get("/api/brain/templates", dependencies=[Depends(require_auth)])
    async def brain_templates() -> dict:
        """List all brain templates with metadata."""
        templates = TemplateRegistry(config_dir, data_dir)
        return {"ok": True, "data": {"templates": templates.list_templates()}}

    @app.get("/api/brain/provenance", dependencies=[Depends(require_auth)])
    async def brain_provenance(
        surface: str | None = None, task: str | None = None
    ) -> dict:
        """Report template provenance for Nerd Mode."""
        templates = TemplateRegistry(config_dir, data_dir)
        return {"ok": True, "data": templates.provenance(surface=surface, task=task)}

    @app.get("/api/templates", dependencies=[Depends(require_auth)])
    async def templates_list() -> dict:
        """Read-only template discovery (first-class brain templates).

        One row per loaded template: ``{id, surface, role, description}``
        (role is the template kind: core/persona/surface/task/format).
        Templates are plain markdown under ``config/prompts/`` with
        optional private overrides in ``config/prompts.local/`` — see
        docs/brain-templates.md. Editing them never requires code
        changes; this endpoint reflects the current tree on every call.
        """
        templates = TemplateRegistry(config_dir, data_dir)
        return {"ok": True, "data": {"templates": templates.list_public()}}

    # --- Scheduler / Reminders ---

    # One scheduler lives per app (background thread + shared state);
    # per-request Scheduler instances would silently double-fire or
    # miss entirely. Started with the app; stops at FastAPI shutdown.
    from . import push as push_mod
    from .scheduler import Reminder, Scheduler

    _push = push_mod.PushHub(data_dir, mode=_identity_mode)
    if _identity_mode == "multi":
        _push.person_ids = lambda: [
            u.get("user_id")
            for u in _identity_store.list_users()
            if u.get("user_id") and u.get("enabled", False)
        ]

    def _deliver_reminder(
        title: str, body: str, person_id: str = "primary"
    ) -> Result | None:
        """Resolve the notifications provider per delivery so a runtime
        config change is honored and the scheduler stays decoupled from
        any transport. None = no notifications provider configured; the
        reminder still fires and journals (delivery is optional).

        Web push is ONE MORE TRANSPORT of the same capability: when it
        is configured, a fired reminder is also published to that
        person's devices through the normal notify path (prefs and quiet
        hours apply exactly as they do for any other source)."""
        result: Result | None = None
        _world, reg = _state()
        provider = reg.provider_for("notifications")
        impl = reg.impl(provider.name) if provider else None
        if impl is not None:
            result = impl.send(title, body)
        try:
            _push.notify(
                person_id,
                # A reminder is something the person asked to be told: it
                # pushes at the GOOD NEWS tier, which is on by default.
                tier="good_news",
                source="reminder",
                title=title,
                body=body,
                link="/",
            )
        except Exception as exc:  # a push problem never loses a reminder
            _logger.warning("reminder push transport failed: %s", type(exc).__name__)
        return result

    _reminders = Scheduler(
        data_dir / "reminders.json",
        journal=journal,
        notifier=_deliver_reminder,
    )

    # Per-user reminders (decision #13): in multi mode each person's
    # reminders are in their own tree (data/users/<id>/reminders.json)
    # and fire into their own journal. Single mode — and the legacy
    # instance file — keep using the one scheduler above, byte-identical.
    _scoped_schedulers: dict[str, Scheduler] = {}

    def _scheduler_for(principal) -> Scheduler:
        """The Scheduler owning the principal's own reminders file."""
        path = _scoped_path(principal, "reminders")
        if path == _reminders.path:
            return _reminders
        key = str(path)
        sched = _scoped_schedulers.get(key)
        if sched is None:
            # Deliver into the OWNER's notification space (an agent's
            # reminders are the owner's, per principal_scoped_path).
            person_id = (
                principal.owner_id
                if principal is not None and principal.kind == "agent" and principal.owner_id
                else (principal.id if principal is not None else "primary")
            )
            sched = Scheduler(
                path,
                journal=_journal_target(_scoped_path(principal, "journal")),
                notifier=lambda title, body: _deliver_reminder(title, body, person_id),
            )
            _scoped_schedulers[key] = sched
        return sched

    def _fire_scoped_reminders() -> None:
        """Tick every enabled person's own reminders (multi mode only).

        The legacy scheduler keeps its own thread; this covers the
        per-user trees so a second person's reminders fire — and journal
        into their own tree — exactly like the bootstrap person's. Trees
        without a reminders file are skipped, so a person's directory is
        never materialized just because the clock ticked.
        """
        if _identity_mode != "multi":
            return
        from .identity import Principal

        for u in _identity_store.list_users():
            uid = u.get("user_id")
            if not uid:
                continue
            person = Principal(id=uid, kind="person", source="scheduler")
            try:
                if not _scoped_path(person, "reminders").exists():
                    continue
                _scheduler_for(person).check_and_fire()
            except Exception as exc:  # one bad tick must not kill the loop
                _logger.warning("scoped reminder tick failed for %s: %s", uid, exc)

    # Use lifespan context manager instead of deprecated on_event
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app):
        _reminders.start()
        scoped_stop = threading.Event()
        scoped_thread = None
        if _identity_mode == "multi":

            def _scoped_tick():
                while not scoped_stop.wait(60):
                    _fire_scoped_reminders()

            scoped_thread = threading.Thread(target=_scoped_tick, daemon=True)
            scoped_thread.start()
        # Quiet hours ended → one "N things waited for you" per person
        # (push.py; a minute-granularity tick, like the scheduler's own).
        push_stop = threading.Event()

        def _push_summary_tick():
            while not push_stop.wait(60):
                try:
                    _push.quiet_summaries()
                except Exception as exc:  # never kill the thread on one bad tick
                    _logger.warning("push summary tick failed: %s", type(exc).__name__)

        push_thread = threading.Thread(target=_push_summary_tick, daemon=True)
        push_thread.start()
        yield
        scoped_stop.set()
        push_stop.set()
        _reminders.stop()

    # Re-create app with lifespan (FastAPI supports this pattern)
    # We attach lifespan to the app state so it's used
    app.router.lifespan_context = lifespan

    # -- identity admin + people & roles (issue #8; roles 2026-09-26) ------
    # Authorization is the permission model (roles.can), never a name or
    # a role string: admins manage accounts, not content.
    def _require_person(principal) -> None:
        """Person-only surfaces: prefs, journal, notes. Agents are
        refused even with valid tokens — narrow scope model, fail
        closed."""
        if principal is not None and principal.kind == "agent":
            raise HTTPException(status_code=403, detail="person-only surface")

    def _require_permission(principal, permission: str) -> None:
        """The HTTP form of ``can``: 403 with the permission named when
        the caller does not hold it (agents included — fail closed)."""
        if not can(principal, permission):
            raise HTTPException(status_code=403, detail=f"{permission} required")

    def _person_name(user_id: object) -> str | None:
        """The stored display name beside a person id, or ``None``.

        Names for the ``*_name`` fields are **read** from the identity
        store, never invented: an unknown or deleted id, or a record
        with no display name, gives ``None``. Identity-level metadata
        only (see people.py) — this says nothing about a person's
        content."""
        if not isinstance(user_id, str) or not user_id:
            return None
        return _identity_store.get_display_name(user_id)

    def _helping_target(request: Request, *, need_act: bool):
        """The person a helper's ``X-Worlds-Helping`` header names.

        Returns a Principal for that person, or ``None`` when no helping
        header is present. A present header must name a real person the
        caller holds a live grant for: any live grant answers
        ``see_needs_of``; only ``can_act`` answers ``act_for``. Anything
        else is a 403 with a plain message — never a hint about whether
        the person exists. Persons only: an agent never helps.
        """
        raw = request.headers.get(HELPING_HEADER, "").strip()
        if not raw:
            return None
        caller = getattr(request.state, "principal", None)
        if caller is None or getattr(caller, "kind", "person") != "person":
            raise HTTPException(
                status_code=403, detail="helping needs a person account"
            )
        from .identity import _SAFE_PRINCIPAL_ID as _safe
        from .identity import principal_from_record

        if not _safe.fullmatch(raw):
            raise HTTPException(
                status_code=403, detail="you do not have permission to help that person"
            )
        grants = _helper_store.live_for_helper(caller.id)
        permission = "act_for" if need_act else "see_needs_of"
        if not can(caller, permission, target=raw, grants=grants):
            raise HTTPException(
                status_code=403, detail="you do not have permission to help that person"
            )
        record = _identity_store.get_principal_record(raw)
        if record is None:
            raise HTTPException(
                status_code=403, detail="you do not have permission to help that person"
            )
        return principal_from_record(record, source=caller.source, store=_identity_store)

    @app.get("/api/identity/users", dependencies=[Depends(require_auth)])
    async def users_list(request: Request) -> dict:
        principal = getattr(request.state, "principal", None)
        _require_permission(principal, "manage_people")
        return {"ok": True, "data": _identity_store.list_users()}

    @app.post("/api/identity/users", dependencies=[Depends(require_step_up)])
    async def users_create(request: Request) -> dict:
        """Provision a person without touching internals.

        Body: {"user_id", "display_name"?, "token"?"}. Token is
        optional; if omitted the server generates one and returns it
        exactly once. Never stored in the clear.
        """
        principal = getattr(request.state, "principal", None)
        _require_permission(principal, "manage_people")
        body = await request.json()
        user_id = ((body or {}).get("user_id") or "").strip()
        from .identity import _SAFE_PRINCIPAL_ID as _safe_pid  # mirrored, single owner

        # Same pattern identity.principal_scoped_path enforces: rejecting
        # unicode ids ('héllo') here prevents a 500 on every scoped route
        # later, and ASCII '.'/ '-' ids stay valid.
        if not user_id or not _safe_pid.fullmatch(user_id):
            raise HTTPException(status_code=422, detail="user_id invalid")
        display = (body or {}).get("display_name") or user_id
        plain = (body or {}).get("token") or secrets.token_urlsafe(24)
        try:
            u = _identity_store.create_user(user_id, display, initial_plain_token=plain)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        journal.record(
            kind=JournalKind.SETTINGS_CHANGE,
            summary=f"user provisioned: {user_id}",
            source="admin",
        )
        return {
            "ok": True,
            "data": {
                "user_id": u["user_id"],
                "display_name": u.get("display_name"),
                "token": plain,
            },
        }

    @app.delete(
        "/api/identity/users/{user_id}", dependencies=[Depends(require_step_up)]
    )
    async def users_disable(request: Request, user_id: str) -> dict:
        """Revoke access (disable). Data is preserved, not deleted."""
        principal = getattr(request.state, "principal", None)
        _require_permission(principal, "manage_people")
        ok = _identity_store.disable_user(user_id)
        if not ok:
            raise HTTPException(status_code=404, detail="no such user")
        journal.record(
            kind=JournalKind.SETTINGS_CHANGE,
            summary=f"user disabled: {user_id}",
            source="admin",
        )
        return {"ok": True, "data": {"user_id": user_id, "disabled": True}}

    @app.get("/api/identity/agents", dependencies=[Depends(require_auth)])
    async def agents_list(request: Request) -> dict:
        """Mine (list) — agents owned by the caller; admins see all."""
        principal = getattr(request.state, "principal", None)
        if can(principal, "manage_people"):
            return {"ok": True, "data": _identity_store.list_agents()}
        owner = (
            principal.owner_id
            if (principal and principal.kind == "agent")
            else (principal.id if principal else None)
        )
        return {"ok": True, "data": _identity_store.list_agents(owner_id=owner)}

    @app.post("/api/identity/agents", dependencies=[Depends(require_step_up)])
    async def agents_create(request: Request) -> dict:
        """Register an agent principal owned by the caller.

        Body: {"agent_id", "display_name"?, "scopes"?}. Scopes subset
        of read/write/journal/apps/notify/learning/journal_gate. Returns
        the token exactly once. ``notify`` lets the agent publish to its
        owner's notifications (POST /api/notify) — nothing else.
        ``learning`` (alone) confines the token to /api/learning*: the
        owner's learning memory and nothing else. ``journal_gate``
        (alone) confines the token to POST /api/journal/gate only — a
        closed-enum question onto the owner's Journal, never raw entries
        (CONFINING_SCOPES). It does NOT grant /api/journal or
        /api/recall access; those stay person-only regardless of scope.
        """
        ALLOWED = {"read", "write", "journal", "apps", "notify", "learning", "journal_gate"}
        principal = getattr(request.state, "principal", None)
        if principal is None:
            raise HTTPException(status_code=403, detail="principal required")
        body = await request.json()
        agent_id = ((body or {}).get("agent_id") or "").strip()
        from .identity import _SAFE_PRINCIPAL_ID as _safe_pid  # mirrored, single owner

        if not agent_id or not _safe_pid.fullmatch(agent_id):
            raise HTTPException(status_code=422, detail="agent_id invalid")
        scopes = [
            s for s in ((body or {}).get("scopes") or ["read"]) if s in ALLOWED
        ] or ["read"]
        plain = secrets.token_urlsafe(24)
        try:
            a = _identity_store.create_agent(
                agent_id, principal.id, tuple(scopes), plain_token=plain
            )
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        journal.record(
            kind=JournalKind.SETTINGS_CHANGE,
            summary="agent registered: " + agent_id + " scopes=" + ",".join(scopes),
            source="admin",
        )
        return {
            "ok": True,
            "data": {
                "agent_id": a["user_id"],
                "owner_id": principal.id,
                "scopes": scopes,
                "token": plain,
            },
        }

    @app.delete(
        "/api/identity/agents/{agent_id}", dependencies=[Depends(require_step_up)]
    )
    async def agents_disable(request: Request, agent_id: str) -> dict:
        principal = getattr(request.state, "principal", None)
        ok = _identity_store.disable_agent(agent_id, principal.id)
        if not ok:
            raise HTTPException(status_code=404, detail="no such agent")
        journal.record(
            kind=JournalKind.SETTINGS_CHANGE,
            summary=f"agent disabled: {agent_id}",
            source="admin",
        )
        return {"ok": True, "data": {"agent_id": agent_id, "disabled": True}}

    # -- read-only viewer credentials (owner only, step-up to create/revoke) --
    def _require_owner_person(principal) -> None:
        if (
            principal is None
            or principal.kind != "person"
            or getattr(principal, "read_only", False)
            or not can(principal, "transfer_ownership")
        ):
            raise HTTPException(status_code=403, detail="owner required")

    @app.get("/api/identity/viewers", dependencies=[Depends(require_auth)])
    async def viewers_list(request: Request) -> dict:
        """The owner's read-only viewer credentials (no hashes, no tokens)."""
        principal = getattr(request.state, "principal", None)
        _require_owner_person(principal)
        return {"ok": True, "data": _identity_store.list_viewers(owner_id=principal.id)}

    @app.post("/api/identity/viewers", dependencies=[Depends(require_step_up)])
    async def viewers_create(request: Request) -> dict:
        """Mint a read-only viewer credential that acts as the owner for
        reads only. Body: {"viewer_id", "label"?}. Owner only. The token is
        returned exactly once and stored hashed."""
        principal = getattr(request.state, "principal", None)
        _require_owner_person(principal)
        body = await request.json()
        viewer_id = ((body or {}).get("viewer_id") or "").strip()
        from .identity import _SAFE_PRINCIPAL_ID as _safe_pid

        if not viewer_id or not _safe_pid.fullmatch(viewer_id):
            raise HTTPException(status_code=422, detail="viewer_id invalid")
        label = str((body or {}).get("label") or "")
        plain = "pwv_" + secrets.token_urlsafe(24)
        try:
            v = _identity_store.create_viewer(
                viewer_id, principal.id, plain, label=label
            )
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        journal.record(
            kind=JournalKind.SETTINGS_CHANGE,
            summary="read-only viewer registered: " + viewer_id,
            source="admin",
        )
        return {
            "ok": True,
            "data": {
                "viewer_id": v["user_id"],
                "owner_id": principal.id,
                "read_only": True,
                "token": plain,
            },
        }

    @app.delete(
        "/api/identity/viewers/{viewer_id}", dependencies=[Depends(require_step_up)]
    )
    async def viewers_disable(request: Request, viewer_id: str) -> dict:
        principal = getattr(request.state, "principal", None)
        _require_owner_person(principal)
        if not _identity_store.disable_viewer(viewer_id, principal.id):
            raise HTTPException(status_code=404, detail="no such viewer")
        journal.record(
            kind=JournalKind.SETTINGS_CHANGE,
            summary=f"read-only viewer disabled: {viewer_id}",
            source="admin",
        )
        return {"ok": True, "data": {"viewer_id": viewer_id, "disabled": True}}

    @app.get("/api/apps", dependencies=[Depends(require_auth)])
    async def apps_list(request: Request) -> dict:
        """Services launcher registry (config/data/apps.json).

        Each entry: {id, name, url, icon?, category?}. User-editable,
        optional; absent file = empty list.
        """
        path = data_dir / "apps.json"
        if not path.exists():
            return {"ok": True, "data": []}
        try:
            items = json.loads(path.read_text())
        except Exception:
            return {"ok": True, "data": []}
        return {"ok": True, "data": items}

    @app.put("/api/apps", dependencies=[Depends(require_step_up)])
    async def apps_put(request: Request) -> dict:
        """Replace the services registry (step-up gated, like prefs)."""
        body = await request.json()
        items = body.get("apps") if isinstance(body, dict) else None
        if not isinstance(items, list):
            raise HTTPException(status_code=422, detail="apps must be a list")
        path = data_dir / "apps.json"
        path.write_text(json.dumps(items, indent=2))
        journal.record(
            kind=JournalKind.SETTINGS_CHANGE,
            summary=f"apps registry updated: {len(items)} services",
            source="api",
        )
        return {"ok": True, "data": items}

    @app.get("/api/reminders", dependencies=[Depends(require_auth)])
    async def reminders_list(request: Request) -> dict:
        """List the caller's own reminders (per-user, decision #13)."""
        reminders = _scheduler_for(_principal(request)).list_reminders()
        return {"ok": True, "data": [r.model_dump(mode="json") for r in reminders]}

    @app.post("/api/reminders", dependencies=[Depends(require_step_up)])
    async def reminders_add(request: Request) -> dict:
        """Add a reminder to the caller's own tree.
        Body: {id, text, cron_hour, cron_minute, cron_day}."""
        body = await request.json()
        rid = body.get("id") or f"r-{int(time.time())}"
        text = body.get("text", "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="text required")
        reminder = Reminder(
            id=rid,
            text=text,
            cron_hour=body.get("cron_hour"),
            cron_minute=body.get("cron_minute"),
            cron_day=body.get("cron_day"),
        )
        r = _scheduler_for(_principal(request)).add(reminder)
        return {"ok": r.ok, "data": r.data, "warnings": r.warnings}

    @app.delete("/api/reminders/{rid}", dependencies=[Depends(require_step_up)])
    async def reminders_delete(rid: str, request: Request) -> dict:
        """Delete one of the caller's own reminders."""
        r = _scheduler_for(_principal(request)).remove(rid)
        return {"ok": r.ok, "data": r.data, "warnings": r.warnings}

    @app.patch("/api/reminders/{rid}", dependencies=[Depends(require_step_up)])
    async def reminders_toggle(rid: str, request: Request) -> dict:
        """Toggle one of the caller's own reminders. Body: {enabled: bool}."""
        body = await request.json()
        r = _scheduler_for(_principal(request)).toggle(rid, body.get("enabled", True))
        return {"ok": r.ok, "data": r.data, "warnings": r.warnings}

    # --- Web Push & notification history (the notifications transport) ---
    # Standards-based Web Push (VAPID) through the browsers' own push
    # services: the last transport of the "notifications" capability, so
    # Worlds — and iPhone Home Screen installs under Worlds' own name and
    # icon — is the hub. Stores are per person
    # (identity kinds "push_subscriptions" and "notifications"); the
    # VAPID private key lives only in the environment and never in a
    # response or a log. Device subscription writes are auth-only (not
    # step-up): a phone setting itself up has no session grant yet, and
    # the surface is the caller's own devices. Full guide:
    # docs/NOTIFICATIONS.md.

    _NOTIFY_SOURCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")

    def _push_caller(request: Request) -> str:
        """The person whose notification space this call touches."""
        principal = _principal(request)
        _require_person(principal)
        return principal.id

    @app.get("/api/push/public-key", dependencies=[Depends(require_auth)])
    async def push_public_key(request: Request) -> dict:
        """The VAPID public key the browser subscribes with, or 409
        not_configured when this server has no push key (everything
        else still works — the UI reads that as 'not configured')."""
        _push_caller(request)  # person-only surface; the key itself is public
        key = _push.public_key()
        if key is None or not _push.configured():
            raise HTTPException(
                status_code=409,
                detail="push is not configured on this server",
            )
        return {"ok": True, "data": {"public_key": key}}

    @app.post("/api/push/subscriptions", dependencies=[Depends(require_auth)])
    async def push_subscribe(request: Request) -> dict:
        """Register (or refresh) one device. Body: {subscription: <the
        JSON a browser PushSubscription produces>, device_label}.
        Upsert by endpoint, so re-subscribing never stacks devices."""
        caller = _push_caller(request)
        body = await request.json()
        try:
            sub_id, created = _push.add_subscription(
                caller,
                (body or {}).get("subscription") or {},
                str((body or {}).get("device_label") or ""),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"ok": True, "data": {"id": sub_id, "created": created}}

    @app.get("/api/push/subscriptions", dependencies=[Depends(require_auth)])
    async def push_subscriptions_list(request: Request) -> dict:
        """This person's devices: labels and times only. Endpoints and
        keys are credentials and never leave the store."""
        caller = _push_caller(request)
        return {"ok": True, "data": _push.list_subscriptions(caller)}

    @app.delete(
        "/api/push/subscriptions/{sub_id}", dependencies=[Depends(require_auth)]
    )
    async def push_subscription_delete(sub_id: str, request: Request) -> dict:
        caller = _push_caller(request)
        if not _push.remove_subscription(caller, sub_id):
            raise HTTPException(status_code=404, detail="no such device")
        return {"ok": True, "data": {"id": sub_id, "removed": True}}

    @app.get("/api/notifications", dependencies=[Depends(require_auth)])
    async def notifications_list(request: Request) -> dict:
        """The caller's notification history, newest first.
        Query: unread=1 to see only what has not been read; limit."""
        caller = _push_caller(request)
        unread = request.query_params.get("unread", "") in ("1", "true", "yes")
        try:
            limit = int(request.query_params.get("limit") or 20)
        except ValueError as _err:
            raise HTTPException(status_code=422, detail="limit must be a number") from _err
        items = _push.list_notifications(caller, unread, limit)
        return {"ok": True, "data": items}

    @app.get("/api/notifications/prefs", dependencies=[Depends(require_auth)])
    async def notifications_prefs_get(request: Request) -> dict:
        caller = _push_caller(request)
        return {"ok": True, "data": _push.get_prefs(caller)}

    @app.put("/api/notifications/prefs", dependencies=[Depends(require_auth)])
    async def notifications_prefs_put(request: Request) -> dict:
        """Replace the caller's notification preferences.
        Body: {tiers: {…on/off}, sources: {<source>: on/off},
        quiet_hours: {on, start, end, tz}}; partial bodies merge over
        the defaults."""
        caller = _push_caller(request)
        body = await request.json()
        try:
            prefs = _push.put_prefs(caller, body or {})
        except push_mod.PrefsError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"ok": True, "data": prefs}

    @app.post(
        "/api/notifications/read-all", dependencies=[Depends(require_auth)]
    )
    async def notifications_read_all(request: Request) -> dict:
        caller = _push_caller(request)
        return {"ok": True, "data": {"read": _push.read_all(caller)}}

    @app.post(
        "/api/notifications/{note_id}/read", dependencies=[Depends(require_auth)]
    )
    async def notifications_read(note_id: str, request: Request) -> dict:
        caller = _push_caller(request)
        if not _push.mark_read(caller, note_id):
            raise HTTPException(status_code=404, detail="no such notification")
        return {"ok": True, "data": {"id": note_id, "read": True}}

    @app.post("/api/notifications/test", dependencies=[Depends(require_auth)])
    async def notifications_test(request: Request) -> dict:
        """'Send me a test' — one known-good notification to every one
        of the caller's devices. Step-up is not required: this sends to
        the person's own phone, not to anything of value."""
        caller = _push_caller(request)
        return {"ok": True, "data": _push.test_push(caller)}

    @app.post("/api/notify", dependencies=[Depends(require_auth)])
    async def notify_publish(request: Request) -> dict:
        """The publishing door for people, agents and CLI tools.

        A signed-in person may notify themselves. An agent (service
        token) needs the ``notify`` scope and notifies its OWNER; it may
        name another person with ``to`` only when the owner can manage
        people. Every notification is stored in the recipient's history
        before anything is pushed; the response says what happened
        ({id, delivered, deferred, state}). Publishes are rate-limited
        per caller (30 a minute, plain 429) and idempotent on
        ``dedupe_key`` for a day. docs/NOTIFICATIONS.md has curl and CLI
        examples."""
        principal = _principal(request)
        if principal is None:
            raise HTTPException(status_code=403, detail="principal required")
        if principal.kind == "agent":
            if "notify" not in (principal.scopes or ()):
                raise HTTPException(
                    status_code=403, detail="the notify scope is required to publish"
                )
            owner = principal.owner_id
            if not owner:
                raise HTTPException(status_code=403, detail="agent has no owner")
            recipient = owner
        else:
            recipient = principal.id
        body = await request.json()
        to = (body or {}).get("to")
        if to and to != recipient:
            if not can(principal, "manage_people"):
                raise HTTPException(
                    status_code=403, detail="you may only notify yourself"
                )
            from .identity import _SAFE_PRINCIPAL_ID as _safe_pid

            if not _safe_pid.fullmatch(str(to)):
                raise HTTPException(status_code=422, detail="to is not a person id")
            recipient = str(to)
            if _identity_mode == "multi" and _identity_store.get_user(recipient) is None:
                raise HTTPException(status_code=404, detail="no such person")
        tier = (body or {}).get("tier")
        if tier not in push_mod.TIERS:
            raise HTTPException(
                status_code=422, detail="tier is good_news, update or when_ready"
            )
        source = str((body or {}).get("source") or "api")
        if not _NOTIFY_SOURCE.fullmatch(source):
            raise HTTPException(
                status_code=422, detail="source is a short plain id (vefr, candy, cli…)"
            )
        title = str((body or {}).get("title") or "").strip()
        text = str((body or {}).get("body") or "").strip()
        if not title or len(title) > 120:
            raise HTTPException(status_code=422, detail="title is needed (max 120)")
        if not text or len(text) > 4000:
            raise HTTPException(status_code=422, detail="body is needed (max 4000)")
        try:
            link = push_mod.valid_same_origin_link((body or {}).get("link"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        dedupe = (body or {}).get("dedupe_key")
        if dedupe is not None:
            dedupe = str(dedupe)[:120] or None
        if _push.rate_limited(f"{principal.kind}:{principal.id}"):
            raise HTTPException(
                status_code=429, detail="too many notifications this minute; wait a moment"
            )
        try:
            outcome = _push.notify(
                recipient,
                tier=tier,
                source=source,
                title=title,
                body=text,
                link=link,
                dedupe_key=dedupe,
                private=bool((body or {}).get("private")),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"ok": True, "data": outcome}

    # --- Source control enrichment ---

    @app.get("/api/source-control/enrichment", dependencies=[Depends(require_auth)])
    async def source_control_enrichment(repo: str = "") -> dict:
        """GitHub enrichment for one repository (remote-side facts
        local Git cannot know: canonical identity, open PRs, open
        issues, default branch, last remote push), or — when ``repo``
        is omitted — for EVERY repository discovered in the configured
        search paths, one entry per repository under
        ``data.repositories``.

        Local Git stays canonical — this only ADDS remote facts; the
        native status shape is unchanged. Quiet degradation is the
        contract: gh missing / unauthenticated / offline / non-GitHub
        remote each return their own status ('unavailable',
        'not_github', 'not_configured'), never a crash and never a
        guessed field. Read-only; no credentials are read, stored, or
        logged here — the gh CLI's own session is used as-is."""
        from .providers.github import GitHubEnrichment

        paths = _sc_paths()
        if not repo:
            entries = enrich_all_repositories(discover_repositories(paths))
            if not entries:
                return {
                    "ok": False,
                    "status": "not_configured",
                    "data": {"repositories": []},
                    "warnings": [
                        "no repositories found in configured search paths"
                    ],
                }
            first_bad = next((e for e in entries if not e["ok"]), None)
            return {
                "ok": first_bad is None,
                "status": (
                    "healthy" if first_bad is None else first_bad["status"]
                ),
                "data": {"repositories": entries},
                "warnings": [],
            }
        matches = [
            e
            for e in discover_repositories(paths)
            if e["is_repository"] and e["name"] == repo
        ]
        if not matches:
            return {
                "ok": False,
                "status": "not_configured",
                "warnings": [
                    f"repository '{repo}' not found in configured search paths"
                ],
            }
        status = repository_status(matches[0]["path"])
        r = GitHubEnrichment().enrich_repo(status.get("remote"))
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.get("/api/projects/status", dependencies=[Depends(require_auth)])
    async def projects_status() -> dict:
        """Project-estate status from the agent-sync sensor (read-only).

        agent-sync (the pickle project's adapter layer) is
        AUTHORITATIVE for repository publication state: it invokes
        this one `agent-sync status --all --format json` observation
        per call and normalizes the documented
        `play-nice/repo-status-v1` records. Project Worlds adds no
        Git-state computation of its own. Quiet degradation is the
        contract: command absent / timeout / malformed output each
        return an 'unavailable' envelope — Project Worlds
        stays fully useful without the sensor. The observation carries
        agent-sync's own `observed_at` so it stays visibly a dated
        observation, never timeless truth."""
        from .providers.agent_sync import AgentSyncProjectSensor

        r = AgentSyncProjectSensor().observe_projects()
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    @app.get("/api/identity/principal", dependencies=[Depends(require_auth)])
    async def identity_principal(request: Request) -> dict:
        """Read-only: who is calling. Useful for diagnostics and for a
        future onboarding / profiles surface."""
        p = getattr(request.state, "principal", None)
        if p is None:
            raise HTTPException(status_code=409, detail="principal not resolved")
        stored = _identity_store.get_display_name(p.id) if p.kind == "person" else None
        return {
            "ok": True,
            "data": {
                "id": p.id,
                "kind": p.kind,
                "display_name": stored or p.display_name,
                "role": p.role,
                "scopes": list(p.scopes),
                "source": p.source,
            },
        }

    @app.put("/api/identity/principal", dependencies=[Depends(require_auth)])
    async def identity_principal_update(request: Request) -> dict:
        """Set the caller's own display name. Persisted in private runtime
        state (data/users.json), never in tracked config. Persons only."""
        p = getattr(request.state, "principal", None)
        if p is None:
            raise HTTPException(status_code=409, detail="principal not resolved")
        _require_person(p)
        try:
            body = await request.json()
        except Exception as _err:
            raise HTTPException(status_code=400, detail="JSON body required") from _err
        name = str((body or {}).get("display_name", "")).strip()
        if not name or len(name) > 80:
            raise HTTPException(
                status_code=400, detail="display_name must be 1-80 characters"
            )
        _identity_store.set_display_name(p.id, name)
        journal.record(
            JournalKind.SETTINGS_CHANGE,
            f"display name updated for {p.id}",
            source="api",
        )
        return {
            "ok": True,
            "data": {
                "id": p.id,
                "kind": p.kind,
                "display_name": name,
                "role": p.role,
                "scopes": list(p.scopes),
                "source": p.source,
            },
        }

    # -- People & roles (owner-approved 2026-09-26) ---------------------
    # Admins manage accounts, not content: these routes carry identities,
    # roles and the ownership hand-off — never a journal, a secret or a
    # token. Every response is allow-listed field by field.

    @app.get("/api/me", dependencies=[Depends(require_auth)])
    async def me(request: Request) -> dict:
        """Who the caller is and what they may do.

        The one call the interface makes to show or hide affordances:
        ``{id, display_name, role, permissions}``. Permissions are the
        server's answer (``can``), never a client guess. A person also
        gets the People-screens facts (step 2): ``helpers_granted``,
        ``helping``, and — for a supervised person — their ``limits``,
        or ``guest_until`` for a guest. An agent gets the base fields.
        """
        p = getattr(request.state, "principal", None)
        if p is None:
            raise HTTPException(status_code=409, detail="principal not resolved")
        stored = (
            _identity_store.get_display_name(p.id) if p.kind == "person" else None
        )
        data = {
            "id": p.id,
            "display_name": stored or p.display_name,
            "role": p.role,
            "permissions": [perm for perm in PERMISSIONS if can(p, perm)],
        }
        if p.kind == "person":
            granted = _helper_store.list_granted_by(p.id)
            data["helpers_granted"] = sum(
                1 for g in granted if _helper_store.is_live(g)
            )
            data["helping"] = [
                {
                    "person_id": g.get("person_id"),
                    # Name beside id; unknown or deleted id → null.
                    "person_name": _person_name(g.get("person_id")),
                    "until": g.get("until"),
                    "can_act": bool(g.get("can_act")),
                }
                for g in _helper_store.live_for_helper(p.id)
            ]
            if p.role == "supervised":
                record = _limits_store.get(p.id)
                data["limits"] = (
                    {
                        "limits": record.get("limits", {}),
                        "set_by": record.get("set_by"),
                        "set_at": record.get("set_at"),
                    }
                    if record is not None
                    else {"limits": {}, "set_by": None, "set_at": None}
                )
            if p.role == "guest":
                record = _identity_store.get_user(p.id) or {}
                data["guest_until"] = record.get("guest_until")
        return {"ok": True, "data": data}

    @app.get("/api/people", dependencies=[Depends(require_auth)])
    async def people_list(request: Request) -> dict:
        """Everyone in the estate, with roles. ``manage_people`` only.

        Persons carry their role; agents carry ``role: null`` (an agent is
        a principal, not a role). No content, no secrets, no tokens — an
        allow-list of exactly id/display_name/role/kind/created_at.
        """
        from .identity import record_is_expired, role_for_record

        _require_permission(
            getattr(request.state, "principal", None), "manage_people"
        )

        def _person_row(u: dict) -> dict:
            row = {
                "id": u.get("user_id"),
                "display_name": u.get("display_name"),
                "role": role_for_record(u),
                "kind": "person",
                "created_at": u.get("created_at"),
            }
            if row["role"] == "guest":
                # A guest carries when they expire; after `until` their
                # credential no longer resolves (401) and this list says
                # so. Only guest rows gain fields, so every other row
                # keeps its allow-listed shape.
                row["guest_until"] = u.get("guest_until")
                row["expired"] = record_is_expired(u)
            return row

        people = [_person_row(u) for u in _identity_store.list_users()]
        people.extend(
            {
                "id": a.get("user_id"),
                "display_name": a.get("display_name"),
                "role": None,
                "kind": "agent",
                "created_at": a.get("created_at"),
            }
            for a in _identity_store.list_agents()
        )
        return {"ok": True, "data": people}

    @app.get("/api/people/directory", dependencies=[Depends(require_auth)])
    async def people_directory(request: Request) -> dict:
        """Who is here, by name — the picker list. Signed-in people only.

        ``[{id, display_name}]`` and nothing else: no roles, no emails,
        no expired guests, no agents, no content. Disabled people are
        out (an account that cannot sign in should not be picked).

        The gate is ``own_space``: people who live here (owner, admin,
        member, supervised) can list who else does, so they can pick a
        helper. Guests are refused: a visitor should not get a list of
        everyone in the household. Agents are refused too: a directory of
        people is a person's surface.
        """
        principal = getattr(request.state, "principal", None)
        _require_person(principal)
        _require_permission(principal, "own_space")

        from .identity import record_is_expired

        rows = [
            {"id": u.get("user_id"), "display_name": u.get("display_name")}
            for u in _identity_store.list_users()
            if u.get("enabled", False) and not record_is_expired(u)
        ]
        # Stable for a picker: by name, then id.
        rows.sort(key=lambda r: ((r["display_name"] or "").lower(), r["id"] or ""))
        return {"ok": True, "data": rows}

    @app.put("/api/people/{user_id}/role", dependencies=[Depends(require_step_up)])
    async def people_set_role(request: Request, user_id: str) -> dict:
        """Set a person's role. ``manage_people`` + step-up.

        An admin may set member/supervised/guest/admin but **never
        owner** (ownership moves only through transfer-ownership). An
        admin cannot change their own role, and nobody can change the
        owner's role here. Unknown role → 422.
        """
        principal = getattr(request.state, "principal", None)
        _require_permission(principal, "manage_people")
        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        role = (body or {}).get("role") if isinstance(body, dict) else None
        if not isinstance(role, str) or role not in ROLES:
            raise HTTPException(status_code=422, detail="unknown role")
        if role == "owner":
            raise HTTPException(
                status_code=422,
                detail="owner is not assignable here; use transfer-ownership",
            )
        if user_id == _identity_store.owner_id():
            raise HTTPException(
                status_code=403, detail="the owner's role cannot be changed here"
            )
        if user_id == principal.id:
            raise HTTPException(
                status_code=403, detail="admins cannot change their own role"
            )
        rec = _identity_store.set_role(user_id, role)
        if rec is None:
            raise HTTPException(status_code=404, detail="no such person")
        journal.record(
            JournalKind.SETTINGS_CHANGE,
            f"role changed for {user_id}: {role}",
            source="people",
        )
        return {
            "ok": True,
            "data": {
                "id": user_id,
                "display_name": rec.get("display_name"),
                "role": role,
            },
        }

    @app.post(
        "/api/people/transfer-ownership", dependencies=[Depends(require_step_up)]
    )
    async def people_transfer_ownership(request: Request) -> dict:
        """Hand ownership to an existing admin. Owner only + step-up.

        ``transfer_ownership`` is held by the owner alone. The target must
        already be an admin; the old owner becomes an admin. Journalled so
        the hand-off is visible, never silent.
        """
        principal = getattr(request.state, "principal", None)
        _require_permission(principal, "transfer_ownership")
        from .identity import _SAFE_PRINCIPAL_ID as _safe_pid

        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        to = str((body or {}).get("to") or "").strip() if isinstance(body, dict) else ""
        if not to or not _safe_pid.fullmatch(to):
            raise HTTPException(status_code=422, detail="to must be a valid id")
        owner = _identity_store.owner_id()
        if owner is None:
            # Single mode: the bootstrap person holds the permission and
            # may have no users.json record of their own yet.
            owner = principal.id if getattr(principal, "role", None) == "owner" else None
        if owner is None:
            raise HTTPException(status_code=409, detail="no owner to transfer from")
        if to == owner:
            raise HTTPException(status_code=422, detail="already the owner")
        if _identity_store.get_user(to) is None:
            raise HTTPException(status_code=404, detail="no such person")
        if _identity_store.role_for(to) != "admin":
            raise HTTPException(
                status_code=422, detail="ownership can only transfer to an admin"
            )
        _identity_store.set_role(owner, "admin")
        _identity_store.set_role(to, "owner")
        journal.record(
            JournalKind.SETTINGS_CHANGE,
            f"ownership transferred from {owner} to {to}",
            source="people",
        )
        return {"ok": True, "data": {"from": owner, "to": to}}

    # -- People screens step 2 (owner-approved 2026-09-26): invites,
    # helper grants, supervised limits. Identity-level metadata only:
    # these routes name people and permissions, never content.
    from .identity import _SAFE_PRINCIPAL_ID as _safe_pid

    def _grant_row(grant: dict) -> dict:
        """One helper grant, allow-listed; nothing else is exposed.

        Names ride beside ids (People step 2 handoff): ``helper_name``
        and ``person_name`` are read from the identity store — an
        unknown or deleted id gives ``null``, never an invented name."""
        return {
            "grant_id": grant.get("grant_id"),
            "helper_id": grant.get("helper_id"),
            "helper_name": _person_name(grant.get("helper_id")),
            "person_name": _person_name(grant.get("person_id")),
            "can_act": bool(grant.get("can_act")),
            "until": grant.get("until"),
            "created_at": grant.get("created_at"),
            "revoked_at": grant.get("revoked_at"),
            "revoked_by": grant.get("revoked_by"),
            "live": _helper_store.is_live(grant),
        }

    @app.get("/api/people/invites", dependencies=[Depends(require_auth)])
    async def invites_list(request: Request) -> dict:
        """Open invite links. ``manage_people`` only; no token material.

        A list row says the role, who it is for, when the link expires
        and whether it was used — never the token or its hash.
        """
        _require_permission(
            getattr(request.state, "principal", None), "manage_people"
        )
        return {"ok": True, "data": _invites.list()}

    @app.post("/api/people/invites", dependencies=[Depends(require_step_up)])
    async def invites_create(request: Request) -> dict:
        """Mint a one-time invite link. ``manage_people`` + step-up.

        Body: ``{role, display_name, expires_in_hours?, guest_until?}``.
        ``role`` is member/supervised/guest/admin; a guest needs a future
        ``guest_until``. Only the owner may invite an admin, and the owner
        is never invitable. The token is returned exactly once, here; only
        its hash is stored.
        """
        principal = getattr(request.state, "principal", None)
        _require_permission(principal, "manage_people")
        body = await _json_body(request)
        role = body.get("role")
        if not isinstance(role, str) or role not in people_mod.INVITE_ROLES:
            raise HTTPException(
                status_code=422,
                detail="role must be member, supervised, guest or admin",
            )
        if role == "admin" and getattr(principal, "role", None) != "owner":
            raise HTTPException(
                status_code=403, detail="only the owner can invite an admin"
            )
        display = str(body.get("display_name") or "").strip()
        if not display or len(display) > 80:
            raise HTTPException(
                status_code=422, detail="display_name must be 1-80 characters"
            )
        hours = body.get("expires_in_hours", people_mod.DEFAULT_INVITE_HOURS)
        if (
            not isinstance(hours, int)
            or isinstance(hours, bool)
            or not 1 <= hours <= people_mod.MAX_INVITE_HOURS
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "expires_in_hours must be 1-"
                    f"{people_mod.MAX_INVITE_HOURS}"
                ),
            )
        guest_until = body.get("guest_until")
        if role == "guest":
            expires = people_mod.parse_iso(guest_until)
            if expires is None or expires <= time.time():
                raise HTTPException(
                    status_code=422,
                    detail="guest_until is required for a guest and must be a future ISO time",
                )
        elif guest_until is not None:
            raise HTTPException(
                status_code=422, detail="guest_until only applies to a guest"
            )
        invite, token = _invites.create(
            role=role,
            display_name=display,
            expires_at=time.time() + hours * 3600,
            created_by=principal.id,
            guest_until=guest_until if role == "guest" else None,
        )
        journal.record(
            JournalKind.SETTINGS_CHANGE,
            f"invite created for role {role}",
            source="people",
        )
        return {
            "ok": True,
            "data": {
                "invite_id": invite["invite_id"],
                "role": role,
                "display_name": display,
                "expires_at": people_mod.to_iso(invite["expires_at"]),
                "guest_until": invite.get("guest_until"),
                "token": token,
                # Ready to send: the accept page reads the code from the
                # fragment, which never reaches the server.
                "link": f"{str(request.base_url).rstrip('/')}/invite#{token}",
            },
        }

    @app.delete(
        "/api/people/invites/{invite_id}",
        dependencies=[Depends(require_step_up)],
    )
    async def invites_delete(request: Request, invite_id: str) -> dict:
        """Cancel an invite link. ``manage_people`` + step-up."""
        _require_permission(
            getattr(request.state, "principal", None), "manage_people"
        )
        if not _invites.delete(invite_id):
            raise HTTPException(status_code=404, detail="no such invite")
        journal.record(
            JournalKind.SETTINGS_CHANGE,
            f"invite cancelled: {invite_id}",
            source="people",
        )
        return {"ok": True, "data": {"invite_id": invite_id, "deleted": True}}

    @app.post("/api/invites/accept")
    async def invites_accept(request: Request) -> dict:
        """Accept an invite. No sign-in: the one-time token is the proof.

        Body: ``{token}``. The link works once, before it expires, and
        creates a local account with the invite's role (a guest also gets
        the invite's ``guest_until``). The response carries the new
        person's sign-in key ONCE; only its hash is stored. A key, not a
        chosen password: stored credentials are unsalted hashes matched
        across all accounts, so they must be long and random. People who
        use SSO link their provider sign-in afterwards.
        """
        body = await _json_body(request)
        token = str(body.get("token") or "").strip()
        if not token:
            raise HTTPException(status_code=422, detail="token is required")
        invite = _invites.find_by_token(token)
        if invite is None or invite.get("used_at"):
            raise HTTPException(
                status_code=403, detail="this invite link is not valid"
            )
        expires_at = invite.get("expires_at")
        if not isinstance(expires_at, (int, float)) or expires_at <= time.time():
            raise HTTPException(
                status_code=403, detail="this invite link has expired"
            )
        role = invite.get("role")
        if role not in people_mod.INVITE_ROLES:
            raise HTTPException(
                status_code=403, detail="this invite link is not valid"
            )
        base = people_mod.slug_user_id(invite.get("display_name") or "")
        user_id = base
        if _identity_store.get_user(user_id) is not None:
            user_id = f"{base}-{secrets.token_hex(3)}"
        if _identity_store.get_user(user_id) is not None:
            raise HTTPException(
                status_code=409, detail="a person with that name already exists"
            )
        # Claim the link first so a double submit cannot create two
        # accounts; an already-used link fails closed.
        if not _invites.mark_used(invite["invite_id"]):
            raise HTTPException(
                status_code=403, detail="this invite link is not valid"
            )
        try:
            u = _identity_store.create_user(
                user_id,
                invite.get("display_name"),
                role=role,
                guest_until=invite.get("guest_until") if role == "guest" else None,
            )
            sign_in_key = secrets.token_urlsafe(32)
            _identity_store.attach_hashed_token(user_id, sign_in_key)
        except ValueError as _err:
            raise HTTPException(
                status_code=409, detail="an account already exists for that invite"
            ) from _err
        journal.record(
            JournalKind.SETTINGS_CHANGE,
            f"invite accepted: {user_id} joined as {role}",
            source="invites",
        )
        return {
            "ok": True,
            "data": {
                "user_id": user_id,
                "display_name": u.get("display_name"),
                "role": role,
                "guest_until": u.get("guest_until"),
                # Shown once; keep it somewhere safe.
                "sign_in_key": sign_in_key,
            },
        }

    @app.get("/api/me/helpers", dependencies=[Depends(require_auth)])
    async def helpers_list(request: Request) -> dict:
        """Grants the caller issued. Includes revoked ones, so a
        revocation the owner made in an emergency is visible."""
        principal = getattr(request.state, "principal", None)
        _require_person(principal)
        return {
            "ok": True,
            "data": [
                _grant_row(g) for g in _helper_store.list_granted_by(principal.id)
            ],
        }

    @app.post("/api/me/helpers", dependencies=[Depends(require_step_up)])
    async def helpers_grant(request: Request) -> dict:
        """A person grants someone helper access. Step-up.

        Body: ``{helper_id, can_act?, until?}``. ``until`` is a future
        ISO time within 30 days; the default is 7 days. Any live grant
        lets the helper see this person's room needs; ``can_act`` lets
        them act for this person. The grant belongs to the person, never
        to an admin.
        """
        principal = getattr(request.state, "principal", None)
        _require_person(principal)
        body = await _json_body(request)
        helper_id = str(body.get("helper_id") or "").strip()
        if not helper_id or not _safe_pid.fullmatch(helper_id):
            raise HTTPException(status_code=422, detail="helper_id is invalid")
        if helper_id == principal.id:
            raise HTTPException(
                status_code=422, detail="you cannot grant a helper to yourself"
            )
        if _identity_store.get_user(helper_id) is None:
            raise HTTPException(status_code=404, detail="no such person")
        can_act = body.get("can_act", False)
        if not isinstance(can_act, bool):
            raise HTTPException(
                status_code=422, detail="can_act must be true or false"
            )
        now = time.time()
        until_raw = body.get("until")
        if until_raw is None:
            until_ts = now + people_mod.DEFAULT_HELPER_DAYS * 86400
        else:
            until_ts = people_mod.parse_iso(until_raw)
            if until_ts is None or until_ts <= now:
                raise HTTPException(
                    status_code=422, detail="until must be a future ISO time"
                )
            if until_ts > now + people_mod.MAX_HELPER_DAYS * 86400:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "until must be within "
                        f"{people_mod.MAX_HELPER_DAYS} days"
                    ),
                )
        grant = _helper_store.create(
            person_id=principal.id,
            helper_id=helper_id,
            can_act=can_act,
            until=people_mod.to_iso(until_ts),
            created_by=principal.id,
        )
        journal.record(
            JournalKind.SETTINGS_CHANGE,
            f"helper granted for {principal.id}: {helper_id}"
            f" can_act={can_act}",
            source="people",
        )
        return {"ok": True, "data": _grant_row(grant)}

    @app.delete(
        "/api/me/helpers/{grant_id}", dependencies=[Depends(require_step_up)]
    )
    async def helpers_revoke(request: Request, grant_id: str) -> dict:
        """Revoke a helper grant, any time.

        The person who granted it, or the owner in an emergency. An
        owner's revocation is journalled and stays visible to the person
        in ``GET /api/me/helpers`` (``revoked_by`` is the owner's id).
        """
        principal = getattr(request.state, "principal", None)
        _require_person(principal)
        grant = _helper_store.get(grant_id)
        if grant is None:
            raise HTTPException(status_code=404, detail="no such grant")
        if grant.get("person_id") == principal.id:
            revoked = _helper_store.revoke(grant_id, principal.id)
        elif can(principal, "transfer_ownership"):
            revoked = _helper_store.revoke(grant_id, principal.id)
            journal.record(
                JournalKind.SETTINGS_CHANGE,
                f"owner revoked helper grant {grant_id} "
                f"for {grant.get('person_id')}",
                source="people",
            )
        else:
            raise HTTPException(
                status_code=403,
                detail="only the person or the owner can revoke this grant",
            )
        return {
            "ok": True,
            "data": {
                "grant_id": grant_id,
                "revoked": True,
                "revoked_by": (revoked or {}).get("revoked_by"),
            },
        }

    @app.get("/api/me/helped-by", dependencies=[Depends(require_auth)])
    async def helped_by(request: Request) -> dict:
        """What helpers did for the caller, newest first.

        Each row: ``{at, helper_id, helper_name, action, summary,
        undoable}``. ``undoable`` is false unless a room's own receipt
        says otherwise. ``helper_name`` rides beside the id — read from
        the identity store, ``null`` for a helper who is gone.
        """
        principal = getattr(request.state, "principal", None)
        _require_person(principal)
        rows = []
        for entry in _helper_log.list(principal.id):
            rows.append(
                {
                    "at": entry.get("at"),
                    "helper_id": entry.get("helper_id"),
                    "helper_name": _person_name(entry.get("helper_id")),
                    "action": entry.get("action"),
                    "summary": entry.get("summary"),
                    "undoable": bool(entry.get("undoable", False)),
                }
            )
        return {"ok": True, "data": rows}

    @app.put(
        "/api/people/{user_id}/limits", dependencies=[Depends(require_step_up)]
    )
    async def people_set_limits(request: Request, user_id: str) -> dict:
        """Set a person's supervised limits. Step-up.

        Allowed for ``manage_people`` or for a guardian — someone with a
        live ``can_act`` helper grant from this person. Body:
        ``{limits: [{key, value}]}`` with the closed key set
        (chat_quiet_hours, no_outside_sharing, content_boundary). The
        setter and time are stored.
        """
        principal = getattr(request.state, "principal", None)
        _require_person(principal)
        if principal is None:
            raise HTTPException(status_code=403, detail="principal required")
        allowed = can(principal, "manage_people")
        if not allowed:
            grants = _helper_store.live_for_helper(principal.id)
            allowed = can(principal, "act_for", target=user_id, grants=grants)
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail="manage_people or a guardian grant is required",
            )
        if _identity_store.get_user(user_id) is None:
            raise HTTPException(status_code=404, detail="no such person")
        if user_id == _identity_store.owner_id():
            raise HTTPException(
                status_code=403, detail="the owner's limits cannot be set here"
            )
        body = await _json_body(request)
        try:
            limits = people_mod.validate_limits(body.get("limits"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        record = _limits_store.set(user_id, limits, principal.id)
        journal.record(
            JournalKind.SETTINGS_CHANGE,
            f"limits set for {user_id}",
            source="people",
        )
        return {
            "ok": True,
            "data": {
                "id": user_id,
                "limits": record["limits"],
                "set_by": record["set_by"],
                "set_at": record["set_at"],
            },
        }

    @app.get("/api/me/limits", dependencies=[Depends(require_auth)])
    async def my_limits(request: Request) -> dict:
        """The caller's own limits and who set them (empty if none).

        ``set_by_name`` rides beside ``set_by``: the setter's display
        name read from the identity store, ``null`` if that person is
        gone. No name is ever invented for an id."""
        principal = getattr(request.state, "principal", None)
        _require_person(principal)
        record = _limits_store.get(principal.id)
        return {
            "ok": True,
            "data": {
                "limits": record.get("limits", {}) if record else {},
                "set_by": record.get("set_by") if record else None,
                "set_by_name": (
                    _person_name(record.get("set_by")) if record else None
                ),
                "set_at": record.get("set_at") if record else None,
            },
        }

    @app.get("/api/ingress/rollups", dependencies=[Depends(require_auth)])
    async def ingress_rollups() -> dict:
        """Traefik ingress route rollups (read-only over LAN).

        Optional provider: absent configuration is a known state, not
        a crash — an unconfigured router answers not_configured with
        context, matching the -degradation contract."""
        from .providers.traefik_ingress import (
            TRAEFIK_ENV,
            TraefikIngress,
        )

        base_url = os.environ.get(TRAEFIK_ENV)
        if not base_url:
            return {
                "ok": False,
                "status": "not_configured",
                "warnings": [
                    f"traefik not configured: set {TRAEFIK_ENV} "
                    "to enable ingress rollups",
                ],
            }
        try:
            traefik = TraefikIngress(base_url=base_url)
        except Exception as exc:
            return {
                "ok": False,
                "status": "unavailable",
                "warnings": [f"traefik provider unavailable: {exc}"],
            }
        r = traefik.observe()
        return {"ok": r.ok, "status": r.status, "data": r.data, "warnings": r.warnings}

    # --- Quick actions ---

    @app.post("/api/world/intent", dependencies=[Depends(require_step_up)])
    async def set_intent(request: Request) -> dict:
        """Set an intent. Body: {key, value}."""
        body = await request.json()
        key = body.get("key", "").strip()
        value = body.get("value")
        if not key:
            raise HTTPException(status_code=400, detail="key required")
        world, registry, _ = _state_for(request)
        from .model import Intent, Provenance

        intent = Intent(
            key=key,
            value=value,
            provenance=Provenance(source="dashboard-quick-action"),
        )
        world.set_intent(intent)
        save_world(world, _user_paths(request)[0])
        return {"ok": True, "data": {"key": key}}

    # ── Lore: sync from a room's `lore` view, list, confirm ─────────

    def _lore_view_item(key: str, lore) -> dict:
        v = lore.value if isinstance(lore.value, dict) else {"text": str(lore.value)}
        return {"key": key, "state": lore.state.value, **v,
                "source": lore.provenance.source,
                "observed_at": lore.provenance.observed_at.isoformat()}

    @app.get("/api/lore", dependencies=[Depends(require_auth)])
    async def lore_list(request: Request, source: str | None = None) -> dict:
        """The caller's lore, newest-source first, with counts by state and
        how many the source marked accepted but aren't confirmed yet."""
        from . import lore_sync

        if not can(_principal(request), "own_space"):
            raise HTTPException(status_code=403, detail="your own space is required")
        uw, _ = _user_paths(request)
        world = load_world(uw)
        items = [
            _lore_view_item(k, lo) for k, lo in world.lore.items()
            if source is None or k.startswith(source + ":")
        ]
        counts: dict[str, int] = {}
        for it in items:
            counts[it["state"]] = counts.get(it["state"], 0) + 1
        return {"ok": True, "data": {
            "items": items, "counts": counts,
            "accepted_waiting": len(lore_sync.accepted_keys(world, source or "rylee_lore")),
        }}

    @app.post("/api/lore/sync", dependencies=[Depends(require_auth)])
    async def lore_sync_route(request: Request) -> JSONResponse:
        """Sync lore from a room's read-only ``lore`` view (default: the
        Engine room, which serves rylee_lore). ``{"dry_run": true}`` says
        what would change without changing anything. Everything lands as
        *suggested*; confirmed lore is never touched."""
        from . import lore_sync

        principal = _principal(request)
        if not can(principal, "own_space"):
            raise HTTPException(status_code=403, detail="your own space is required")
        body = await _json_body(request)
        room = str(body.get("room") or "engine-room")
        dry = bool(body.get("dry_run"))
        status, doc = await _ROOMS.view(room, "lore", None, principal)
        if status != 200 or not isinstance(doc, dict):
            reason = (doc or {}).get("error") if isinstance(doc, dict) else None
            return JSONResponse({"ok": False, "error": reason or f"Couldn't read the lore from {room}."},
                                status_code=502 if status != 404 else 404)
        if doc.get("error"):
            return JSONResponse({"ok": False, "error": doc["error"]}, status_code=502)
        uw, _ = _user_paths(request)
        world = load_world(uw)
        if dry:
            report = lore_sync.plan(world, doc)
        else:
            report = lore_sync.apply(world, doc)
            save_world(world, uw)
        report = {k: v for k, v in report.items() if k not in ("new", "changed", "gone")}
        return JSONResponse({"ok": True, "data": {**report, "dry_run": dry, "room": room}})

    @app.post("/api/lore/confirm", dependencies=[Depends(require_step_up)])
    async def lore_confirm(request: Request) -> dict:
        """Confirm lore: ``{"keys": [...]}``, or ``{"accepted": true}`` for
        every suggested item its source marked accepted. A person's explicit
        act, so it needs a step-up ("Confirm it's you"); confirmed lore is
        what Worlds treats as true."""
        from . import lore_sync

        principal = _principal(request)
        if getattr(principal, "kind", None) == "agent" or not can(principal, "own_space"):
            raise HTTPException(status_code=403, detail="only you can confirm your lore")
        body = await _json_body(request)
        uw, _ = _user_paths(request)
        world = load_world(uw)
        if body.get("accepted") is True:
            keys = lore_sync.accepted_keys(world, str(body.get("source") or "rylee_lore"))
        else:
            keys = [k for k in body.get("keys") or [] if isinstance(k, str)][:2000]
        report = lore_sync.confirm(world, keys)
        save_world(world, uw)
        return {"ok": True, "data": report}

    # ── Remember, recall, Later (owner: "I can't stand chasing it down") ──

    def _later_path(request: Request) -> Path:
        principal = _principal(request)
        if not can(principal, "own_space"):
            raise HTTPException(status_code=403, detail="your own space is required")
        return _scoped_path(principal, "later")

    @app.post("/api/remember", dependencies=[Depends(require_auth)])
    async def remember(request: Request) -> dict:
        """Keep one thought: ``{text, later?: bool, source?}``. A person's
        thought goes into their own journal (or onto the Later shelf with
        ``later: true``). A tool or bee (agent token) can only put things on
        the Later shelf, labelled with where they came from. The journal
        stays person-only."""
        from . import memory

        principal = _principal(request)
        body = await _json_body(request)
        text = str(body.get("text", "")).strip()
        if not text or len(text) > memory.TEXT_MAX:
            raise HTTPException(status_code=422, detail="text must be 1-2000 chars")
        is_agent = getattr(principal, "kind", None) == "agent"
        if body.get("later") or is_agent:
            path = _later_path(request)
            data = memory.load_later(path)
            item = memory.add_later(data, text, str(body.get("source") or ("agent" if is_agent else "worlds")))
            memory.save_later(path, data)
            return {"ok": True, "data": {"kept": "later", "id": item["id"]}}
        _, _, uj = _state_for(request)
        target = journal if uj == journal.path else Journal(uj)
        target.record(kind=JournalKind.OBSERVATION, summary=text, source="remember")
        return {"ok": True, "data": {"kept": "journal"}}

    @app.get("/api/recall", dependencies=[Depends(require_auth)])
    async def recall_route(request: Request, q: str = "") -> dict:
        """Ask in plain words. Searches the caller's own journal, lore, Later
        shelf and the ideas they've met (no model needed), newest and
        best-matching first; each answer says where it lives."""
        from . import learning, memory

        principal = _principal(request)
        _require_person(principal)
        if not can(principal, "own_space"):
            raise HTTPException(status_code=403, detail="your own space is required")
        sources: list[dict] = []
        uw, uj = _user_paths(request)
        jr = journal if uj == journal.path else Journal(uj)
        for ev in jr.events():
            sources.append({"kind": "journal", "text": ev.summary, "when": ev.ts.isoformat(),
                            "where": "Journal"})
        world = load_world(uw)
        for lo in world.lore.values():
            v = lo.value if isinstance(lo.value, dict) else {"text": str(lo.value)}
            sources.append({"kind": "lore", "text": str(v.get("text", "")), "title": str(v.get("title", "")),
                            "when": lo.provenance.observed_at.isoformat(), "state": lo.state.value,
                            "where": f"Your lore · {v.get('title', '')}".strip(" ·")})
        for item in memory.load_later(_later_path(request))["items"]:
            sources.append({"kind": "later", "text": item["text"], "when": item.get("created", ""),
                            "state": item["state"], "where": "Later shelf"})
        for concept, entry in learning.load(_scoped_path(principal, "learning"))["concepts"].items():
            sources.append({"kind": "word", "text": f"{concept} {entry.get('first_context', '')}",
                            "when": entry.get("last_seen", ""), "where": "Words you've found"})
        return {"ok": True, "data": {"query": q, "results": memory.recall(q, sources)}}

    @app.get("/api/later", dependencies=[Depends(require_auth)])
    async def later_list(request: Request) -> dict:
        """The Later shelf: what's in progress (at most three), then the rest."""
        from . import memory

        data = memory.load_later(_later_path(request))
        items = data["items"]
        return {"ok": True, "data": {
            "in_progress": [i for i in items if i["state"] == "doing"],
            "later": [i for i in items if i["state"] == "later"],
            "done": [i for i in items if i["state"] == "done"][-20:],
            "max_in_progress": memory.IN_PROGRESS_MAX,
        }}

    @app.post("/api/later/{item_id}", dependencies=[Depends(require_auth)])
    async def later_move(item_id: str, request: Request) -> JSONResponse:
        """Move an idea: ``{to: "doing" | "done" | "later"}``. A fourth
        in-progress idea is refused in plain words (409), never dropped."""
        from . import memory

        body = await _json_body(request)
        path = _later_path(request)
        data = memory.load_later(path)
        ok, words, item = memory.move(data, item_id, str(body.get("to", "")))
        if ok:
            memory.save_later(path, data)
            return JSONResponse({"ok": True, "data": {"item": item, "said": words}})
        return JSONResponse({"ok": False, "error": words}, status_code=409 if item else 404)

    # ── Teach while building (Book Girl): the person's learning memory ──

    def _learning_path(request: Request) -> Path:
        principal = _principal(request)
        learning_key = (
            principal is not None
            and principal.kind == "agent"
            and "learning" in (principal.scopes or ())
        )
        if not learning_key and not can(principal, "own_space"):
            raise HTTPException(status_code=403, detail="your own space is required")
        # An agent's path resolves through its owner (identity boundary).
        return _scoped_path(principal, "learning")

    @app.get("/api/learning", dependencies=[Depends(require_auth)])
    async def learning_view(request: Request) -> dict:
        """The ideas this person has met: stage, where first met, and the
        teaching mode (build | occasional | plain)."""
        from . import learning

        data = learning.load(_learning_path(request))
        concepts = {
            k: {**v, "stage": learning.stage_of(v)} for k, v in data["concepts"].items()
        }
        return {"ok": True, "data": {"mode": data["mode"], "concepts": concepts}}

    @app.post("/api/learning/encounter", dependencies=[Depends(require_auth)])
    async def learning_encounter(request: Request) -> dict:
        """A project says the person just used an idea: ``{concept, project,
        context}`` (context: a few words about what they made, e.g. "the
        hidden door that needed the lantern"). Answers how to teach it now:
        ``first`` | ``again`` (with where it was first met) | ``familiar`` |
        ``off``. Only a concept id and that short phrase are kept."""
        from . import learning

        body = await _json_body(request)
        concept, project = str(body.get("concept", "")), str(body.get("project", ""))
        context = str(body.get("context", "")).strip()
        if not learning.CONCEPT.match(concept) or not learning.PROJECT.match(project):
            raise HTTPException(status_code=422, detail="concept and project must be short ids")
        path = _learning_path(request)
        data = learning.load(path)
        reply = learning.encounter(data, concept, project, context)
        learning.save(path, data)
        return {"ok": True, "data": reply}

    @app.post("/api/learning/got-it", dependencies=[Depends(require_auth)])
    async def learning_got_it(request: Request) -> dict:
        """The person tapped "Got it" on an idea."""
        from . import learning

        body = await _json_body(request)
        concept = str(body.get("concept", ""))
        if not learning.CONCEPT.match(concept):
            raise HTTPException(status_code=422, detail="concept must be a short id")
        path = _learning_path(request)
        data = learning.load(path)
        stage = learning.got_it(data, concept)
        learning.save(path, data)
        return {"ok": True, "data": {"concept": concept, "stage": stage}}

    @app.put("/api/learning/mode", dependencies=[Depends(require_auth)])
    async def learning_mode(request: Request) -> dict:
        """How this person likes to be taught: ``build`` (teach me as I build),
        ``occasional`` (at most one tip a day) or ``plain`` (just plain words)."""
        from . import learning

        body = await _json_body(request)
        mode = body.get("mode")
        if mode not in learning.MODES:
            raise HTTPException(status_code=422, detail="mode must be build, occasional or plain")
        path = _learning_path(request)
        data = learning.load(path)
        data["mode"] = mode
        learning.save(path, data)
        return {"ok": True, "data": {"mode": mode}}

    # ── The sticker album (contract stickers/0) ─────────────────────────

    def _stickers_path(principal) -> Path:
        return _scoped_path(principal, "stickers")

    async def _derive_stickers(request: Request, principal, data: dict) -> None:
        """Worlds stickers earned from real saved state. Never raises."""
        from . import learning, memory, stickers

        def give(sid: str, context: str = "") -> None:
            stickers.find(data, "worlds", sid, context)

        give("first-light")
        try:
            later = memory.load_later(_scoped_path(principal, "later"))
            items = later.get("items") or []
            if items:
                give("later-gator")
            if any(i.get("state") == "done" for i in items):
                give("done-dusted")
            if len(memory.in_progress(later)) == 3:
                give("juggler")
        except Exception:  # noqa: BLE001  # nosec B110  # a sticker never breaks the album
            pass
        try:
            uw, uj = _user_paths(request)
            world = load_world(uw)
            confirmed = sum(1 for k, lo in world.lore.items() if _lore_view_item(k, lo)["state"] == "confirmed")
            if confirmed >= 1:
                give("truth-teller")
            if confirmed >= 25:
                give("know-thyself")
            if any(e.supersedes is not None for e in _journal_target(uj).events()):
                give("second-draft")
        except Exception:  # noqa: BLE001  # nosec B110  # best-effort sticker award; the album still renders
            pass
        try:
            ld = learning.load(_scoped_path(principal, "learning"))
            concepts = ld.get("concepts") or {}
            n = len(concepts)
            for need, sid in ((1, "word-1"), (10, "word-10"), (25, "word-25")):
                if n >= need:
                    give(sid)
            if any("vefr" in (c.get("projects") or []) for c in concepts.values()):
                give("frodis-friend")
            if any(len(set(c.get("projects") or [])) >= 2 for c in concepts.values()):
                give("two-voices")
        except Exception:  # noqa: BLE001  # nosec B110  # best-effort sticker award; the album still renders
            pass
        try:
            visits = rooms_visits.read_visits(_scoped_path(principal, "rooms_visits"))
            seen = set((visits.get("rooms") or {}).keys())
            if seen:
                give("door-opener")
            configured = {r.get("id") for r in await _ROOMS.snapshot(os.environ) if isinstance(r, dict)}
            if configured and configured <= seen:
                give("all-doors")
        except Exception:  # noqa: BLE001  # nosec B110  # best-effort sticker award; the album still renders
            pass
        first = data["found"].get("worlds:first-light", {}).get("at", "")
        try:
            then = _dt.datetime.fromisoformat(first.replace("Z", "+00:00"))
            if first and (_dt.datetime.now(_dt.timezone.utc) - then).days >= 365:
                give("orbit")
        except ValueError:
            pass

    def _award(principal, sid: str, context: str = "") -> None:
        """Best-effort: a Worlds sticker for something that just happened."""
        from . import stickers

        try:
            path = _stickers_path(principal)
            data = stickers.load(path)
            if stickers.find(data, "worlds", sid, context):
                stickers.save(path, data)
        except Exception:  # noqa: BLE001 — never break the action that earned it
            _logger.warning("sticker award failed for %s", sid)

    # Moments that leave no trace in saved state earn their sticker as they
    # happen: path-only, after a successful response, never blocking it.
    _STICKER_MOMENTS = (
        (re.compile(r"^/api/remember$"), "tied-a-string"),
        (re.compile(r"^/api/rooms/[^/]+/actions/answer-decision$"), "tap-tap"),
        (re.compile(r"^/api/rooms/hive-works/actions/answer-decision$"), "honey-handshake"),
        (re.compile(r"^/api/rooms/[^/]+/actions/undo-answer$"), "changed-mind"),
        (re.compile(r"^/api/rooms/[^/]+/actions/start-riff$"), "riff-raff"),
        (re.compile(r"^/api/vault/unlock$"), "keeper-keys"),
    )

    @app.middleware("http")
    async def _sticker_moments(request: Request, call_next):
        response = await call_next(request)
        if request.method == "POST" and 200 <= response.status_code < 300:
            principal = getattr(request.state, "principal", None)
            if principal is not None and getattr(principal, "kind", "person") == "person":
                for pattern, sid in _STICKER_MOMENTS:
                    if pattern.match(request.url.path):
                        _award(principal, sid)
        return response

    @app.get("/api/stickers", dependencies=[Depends(require_auth)])
    async def stickers_album(request: Request) -> dict:
        """The caller's sticker album: Worlds' page (grouped by ``section``)
        and one page per connected app that offers ``stickers``. Unfound
        secrets are never listed, unfound riddles show only their riddle,
        and ``secrets_remain`` says only whether any are left."""
        from . import stickers

        principal = _principal(request)
        _require_person(principal)
        path = _stickers_path(principal)
        data = stickers.load(path)
        before = len(data["found"])
        await _derive_stickers(request, principal, data)
        if len(data["found"]) != before:
            stickers.save(path, data)
        pages = [stickers.page("worlds", "Worlds", "scifi-storybook", stickers.WORLDS, 0, data)]
        unavailable = []
        for row in await _ROOMS.sticker_sets(principal):
            if row["status"] != "ok":
                unavailable.append({"app": row["room"], "error": row.get("error")})
                continue
            st = row["set"]
            app_id = row["room"]
            pg = st.get("page") if isinstance(st.get("page"), dict) else {}
            pages.append(stickers.page(app_id, str(pg.get("title") or app_id), pg.get("look"),
                                       st.get("stickers") or [], int(st.get("secrets") or 0), data))
        return {"ok": True, "data": {"pages": pages, "unavailable": unavailable,
                                     "total_found": len(data["found"])}}

    @app.post("/api/stickers/found", dependencies=[Depends(require_auth)])
    async def stickers_found(request: Request) -> dict:
        """``{app, sticker, context?}``: a sticker was found. An app's sticker
        key may report only its own app; a person may report a Worlds sticker
        the UI saw them earn (a tap on Sol, finding Rough night). Repeats
        are harmless. ``context`` is a few plain words, never content."""
        from . import stickers

        principal = _principal(request)
        body = await _json_body(request)
        app_id, sid = str(body.get("app", "")), str(body.get("sticker", ""))
        if not stickers.APP.match(app_id) or not stickers.ID.match(sid):
            raise HTTPException(status_code=422, detail="app and sticker must be short ids")
        if principal is not None and principal.kind == "agent":
            if "stickers" not in (principal.scopes or ()) or principal.id != f"stickers-{app_id}":
                raise HTTPException(status_code=403, detail="this key reports only its own app's stickers")
        else:
            _require_person(principal)
            if app_id != "worlds" or sid not in stickers.WORLDS_BY_ID or sid in stickers.EARNED_ONLY:
                raise HTTPException(status_code=422, detail="not a sticker Worlds hands out this way")
        path = _stickers_path(principal)
        data = stickers.load(path)
        new = stickers.find(data, app_id, sid, str(body.get("context", "")))
        if new:
            stickers.save(path, data)
        return {"ok": True, "data": {"new": new}}

    @app.post("/api/stickers/place", dependencies=[Depends(require_auth)])
    async def stickers_place(request: Request) -> dict:
        """``{app, sticker, x, y, r}``: where a found sticker sits on its page
        (x, y in 0..1 of the page; r in degrees, -30..30)."""
        from . import stickers

        principal = _principal(request)
        _require_person(principal)
        body = await _json_body(request)
        app_id, sid = str(body.get("app", "")), str(body.get("sticker", ""))
        k = stickers.key(app_id, sid)
        path = _stickers_path(principal)
        data = stickers.load(path)
        if k not in data["found"]:
            raise HTTPException(status_code=404, detail="that sticker isn't in your album yet")
        try:
            x, y, r = (float(body.get("x", 0)), float(body.get("y", 0)), float(body.get("r", 0)))
        except (TypeError, ValueError) as _err:
            raise HTTPException(status_code=422, detail="x, y and r must be numbers") from _err
        data["placed"][k] = {"x": min(max(x, 0.0), 1.0), "y": min(max(y, 0.0), 1.0), "r": min(max(r, -30.0), 30.0)}
        stickers.save(path, data)
        return {"ok": True, "data": {"placed": data["placed"][k]}}

    @app.post("/api/world/fact", dependencies=[Depends(require_step_up)])
    async def record_fact(request: Request) -> dict:
        """Record a fact. Body: {key, value}."""
        body = await request.json()
        key = body.get("key", "").strip()
        value = body.get("value")
        if not key:
            raise HTTPException(status_code=400, detail="key required")
        world, registry, _ = _state_for(request)
        from .model import Fact, Provenance

        fact = Fact(
            key=key,
            value=value,
            provenance=Provenance(source="dashboard-quick-action"),
        )
        world.record_fact(fact)
        save_world(world, _user_paths(request)[0])
        return {"ok": True, "data": {"key": key}}

    @app.post("/api/world/policy", dependencies=[Depends(require_step_up)])
    async def add_policy(request: Request) -> dict:
        """Add a policy. Body: {key, effect}."""
        body = await request.json()
        key = body.get("key", "").strip()
        effect = body.get("effect", "allow")
        if not key:
            raise HTTPException(status_code=400, detail="key required")
        world, registry, _ = _state_for(request)
        from .model import Policy, PolicyEffect, Provenance

        try:
            policy = Policy(
                key=key,
                effect=PolicyEffect(effect),
                provenance=Provenance(source="dashboard-quick-action"),
            )
        except ValueError as _err:
            raise HTTPException(
                status_code=400, detail="effect must be 'allow' or 'deny'"
            ) from _err
        try:
            world.set_policy(policy)
        except MutationDenied as exc:
            # a cemented policy is only changeable by an explicit user
            # action through the CLI; the API reports the boundary, it
            # does not crash on it
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        save_world(world, _user_paths(request)[0])
        return {"ok": True, "data": {"key": key, "effect": effect}}

    # --- Entry point ---
    # `/` is served by app_router (the React interface), mounted at the
    # very end of create_app. /setup and /login are server-rendered
    # (setup_wizard.py / login_page.py) and win by registration order.

    companion_dir = Path(__file__).parent / "static" / "companions"
    _COMPANION_FILES = {
        "personal-world": "personal-world.svg",
        "mermaid": "mermaid.svg",
        "robot": "robot.svg",
        "world-tree-squirrel": "world-tree-squirrel.svg",
        "taco-news-truck": "taco-news-truck.svg",
    }

    @app.get("/companions/{name}.svg")
    async def companion_svg(name: str) -> Response:
        """Serve one allowlisted companion SVG — byte-identical copies of
        the design-owned rigs (see design/assets/companions/). UI asset
        route: public like any browser-fetched art, carries no world
        state, and is not part of the /api Lego box."""
        filename = _COMPANION_FILES.get(name)
        if filename is None or not companion_dir.exists():
            raise HTTPException(status_code=404, detail="unknown companion")
        path = companion_dir / filename
        if not path.exists():
            raise HTTPException(status_code=404, detail="companion art missing")
        return FileResponse(path, media_type="image/svg+xml")

    static_dir = Path(__file__).parent / "static"

    @app.get("/today/{name}.svg")
    async def today_art(name: str, request: Request) -> Response:
        """Serve one allowlisted Today artwork SVG — frame-specific
        decorative exports for Today (Workshop v3, design/assets/today/):
        the quiet-day settle gesture and waterline. UI asset route:
        decorative geometry, carries no world state, and is not part of
        the /api Lego box."""
        # Allowlist pattern matches /fonts and /companions: {name}.svg
        # binds the parameter WITHOUT the suffix.
        allowed = {
            "settle-gesture": "image/svg+xml",
            "waves-ladder": "image/svg+xml",
        }
        ctype = allowed.get(name)
        if ctype is None or "/" in name or ".." in name:
            raise HTTPException(status_code=404, detail="unknown artwork")
        path = static_dir / "today" / f"{name}.svg"
        if not path.exists():
            raise HTTPException(status_code=404, detail="artwork missing")
        return _cached_file(request, path, ctype)

    @app.get("/icons/sprite.svg")
    async def icon_sprite() -> Response:
        """Serve the 72-glyph production icon sprite
        (design/assets/icons/). UI asset route: decorative geometry,
        stroke=currentColor, carries no world state, and is not part of
        the /api Lego box."""
        path = static_dir / "icons" / "sprite.svg"
        if not path.exists():
            raise HTTPException(status_code=404, detail="sprite missing")
        return FileResponse(path, media_type="image/svg+xml")

    @app.get("/fonts/{name}")
    async def webfont(name: str, request: Request) -> Response:
        """Serve a self-hosted webfont from the allowlisted Figma-export
        families (design/tokens.json font.expressive / font.interface).
        UI asset route: OFL-licensed font binaries, carries no world
        state, and is not part of the /api Lego box."""
        allowed = {
            "young-serif-latin.woff2": "font/woff2",
            "instrument-sans-var-latin.woff2": "font/woff2",
        }
        ctype = allowed.get(name)
        if ctype is None or "/" in name or ".." in name:
            raise HTTPException(status_code=404, detail="unknown font")
        path = static_dir / "fonts" / name
        if not path.exists():
            raise HTTPException(status_code=404, detail="font missing")
        return _cached_file(request, path, ctype)

    # --- The push service worker (site-root scope) ---------------------
    # Browsers only let a service worker control the directory it is
    # served from; push must survive every path of the SPA, so /sw.js
    # is served AT THE ROOT with Service-Worker-Allowed: / — and never
    # cached (no-store): a stale worker is a notification that silently
    # stops. The script itself (ui/public/sw.js) carries no state and
    # needs no auth, like the other root assets. A missing build answers
    # 404 plainly.
    @app.get("/sw.js", include_in_schema=False)
    async def service_worker() -> Response:
        from .station_ui import default_app_dir

        path = default_app_dir() / "sw.js"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="service worker not built")
        return FileResponse(
            path,
            media_type="text/javascript; charset=utf-8",
            headers={"Cache-Control": "no-store", "Service-Worker-Allowed": "/"},
        )

    # --- The interface (owner decision 2026-09-22: the React rebuild IS
    # the product frontend). Mounted LAST so its SPA fallback can never
    # shadow an API route; it serves / and the staged build, redirects the
    # retired /station and /vnext paths, and answers reserved namespaces
    # with JSON 404. Same auth entry point as every other route.
    from .station_ui import app_router

    app.include_router(app_router(data_dir))

    return app
