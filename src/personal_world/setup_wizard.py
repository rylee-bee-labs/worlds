"""First-run setup wizard: a server-rendered, dependency-free flow.

A brand-new user runs ``docker compose up``, opens the app, and is met
by ``/setup`` instead of an auth wall. The wizard:

1. welcomes and explains, in plain language, what this is;
2. provisions INVISIBLY (create-if-absent only): an access token in
   ``data/.env``, the world/journal/connections stores (``init_stores``),
   and the FTS search index. The token is never returned, echoed, or
   logged — the UI only ever sees "ready";
3. asks how the person wants to sign in: local (just me on this device)
   or their own SSO (OIDC). OIDC collection stores the issuer, client
   id, and the NAME of the env var holding the client secret — never a
   secret value. "Test connection" fetches the issuer's OIDC discovery
   document and reports (reachable / unreachable / bad
   config);
4. offers comfort defaults (larger text, gentle animation, and the
   residents/companion pack) applied through the validated prefs
   vocabulary, and lets the person pick a companion from the drawn
   starter crew — or none, the plain Assistant. The theme stays
   device-local (``localStorage``); it is not a server setting.
5. writes ``data/setup-complete``, mints a browser session so the
   person lands signed in, and redirects into the app.

Gating: every wizard route answers 404 once setup is complete (or
redirects, for the page) so it can never be re-run by accident.
``FORCE_SETUP=1`` re-opens the wizard deliberately (operator escape
hatch). Provisioning NEVER overwrites existing data.
"""

import json
import logging
import os
import re
import secrets
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from .url_safety import http_urlopen

_logger = logging.getLogger("personal_world.setup_wizard")

SETUP_MARKER = "setup-complete"
CHOICES_FILE = "setup-choices.json"
SECRET_ENV_DEFAULT = "PW_OIDC_CLIENT_SECRET"  # nosec B105  # the NAME of the env var holding the secret

_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

# Wizard assets: allowlist keyed by file name (no user-controlled value
# ever constructs a filesystem path; traversal misses the dict).
_SETUP_ASSETS = {
    "styles.css": "text/css; charset=utf-8",
    "wizard.js": "text/javascript; charset=utf-8",
}


def setup_needed(data_dir: Path | str) -> bool:
    """First-run predicate: no ``data/setup-complete`` marker, or the
    operator explicitly forced setup mode with ``FORCE_SETUP=1``."""
    forced = os.environ.get("FORCE_SETUP", "").strip().lower()
    if forced in ("1", "true", "yes", "on"):
        return True
    return not (Path(data_dir) / SETUP_MARKER).exists()


# ── provisioning primitives (create-if-absent, secret-safe) ──────────


def _read_env_token(env_file: Path) -> str | None:
    """The PW_API_TOKEN value already stored in the env file, if any."""
    if not env_file.is_file():
        return None
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith("PW_API_TOKEN="):
                value = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                return value or None
    except OSError:
        return None
    return None


def _write_env_token(env_file: Path, token: str) -> str:
    """Persist the token create-if-absent: a new file gets 0600 perms;
    an existing file without the key keeps every other line (append).
    Returns how the token was stored ("created" | "appended")."""
    env_file.parent.mkdir(parents=True, exist_ok=True)
    line = f"PW_API_TOKEN={token}\n"
    if not env_file.exists():
        fd = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(line)
        return "created"
    with env_file.open("a", encoding="utf-8") as fh:
        if env_file.stat().st_size > 0:
            fh.write("\n" if not _ends_with_newline(env_file) else "")
        fh.write(line)
    try:
        os.chmod(env_file, 0o600)
    except OSError:
        pass  # best-effort hardening; never fail setup over umask policy
    return "appended"


def _ends_with_newline(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            fh.seek(-1, os.SEEK_END)
            return fh.read(1) == b"\n"
    except OSError:
        return True


def provision(data_dir: Path, config_dir: Path, journal=None) -> dict:
    """The invisible step. Idempotent; never overwrites; never returns
    or logs the token — only the fact that one is ready."""
    data_dir = Path(data_dir)
    config_dir = Path(config_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    env_file = data_dir / ".env"

    # 1. Access token: file wins (matches boot reconciliation in
    #    api.py), then the live environment, then generate.
    token_state = "already-present"  # nosec B105  # a state label, not a credential
    token = _read_env_token(env_file)
    if token is None:
        token = os.environ.get("PW_API_TOKEN") or None
        if token is not None:
            token_state = "environment"  # nosec B105  # a state label, not a credential
    if token is None:
        token = secrets.token_urlsafe(32)
        try:
            how = _write_env_token(env_file, token)
            token_state = f"generated ({how} data/.env)"
        except OSError as exc:
            raise RuntimeError(
                f"could not write the access token file: {exc.strerror or exc}"
            ) from exc
    os.environ["PW_API_TOKEN"] = token

    # 2. Stores: the same create-if-absent init the CLI uses, WITHOUT
    #    the setup-complete marker (that belongs to the finish step).
    from .init import init_stores

    try:
        changed, skipped = init_stores(data_dir, config_dir)
    except Exception as exc:  # failure, plain words
        raise RuntimeError(f"could not initialize the data stores: {exc}") from exc

    # 3. Full-text search index: rebuildable and disposable by design;
    #    a failure here is a warning, never a setup blocker.
    search_index = "ready"
    try:
        from .providers.native_memory import NativeMemoryProvider

        memory = NativeMemoryProvider(data_dir, journal=journal)
        memory.index_journal()
    except Exception as exc:
        search_index = "unavailable"
        warnings.append(
            "The search index could not be built yet "
            f"({type(exc).__name__}). Setup can continue; search will "
            "build itself later."
        )

    return {
        "token_ready": True,  # nosec B105  # a boolean readiness flag, not a credential
        "token_state": token_state,
        "stores_created": changed,
        "stores_already_present": skipped,
        "search_index": search_index,
        "warnings": warnings,
    }


# ── OIDC collection + discovery test ──────────────────────────


def _normalize_issuer(raw: Any) -> tuple[str | None, str | None]:
    """Validate an issuer URL shape. Returns (url, error)."""
    url = str(raw or "").strip().rstrip("/")
    if not url:
        return None, "Please enter the sign-in server address (the issuer URL)."
    if not re.match(r"^https?://[A-Za-z0-9.\-:_@%]+", url):
        return None, (
            "That address does not look like a web address. It should "
            "start with https:// (or http:// for a lab server)."
        )
    return url, None


def test_oidc_discovery(issuer_url: str) -> dict:
    """Fetch ``{issuer}/.well-known/openid-configuration`` and report
    the result. Never includes a secret (none is involved); never claims
    success it did not observe."""
    url, err = _normalize_issuer(issuer_url)
    if err:
        return {"status": "bad_config", "detail": err}
    discovery = f"{url}/.well-known/openid-configuration"
    try:
        req = urllib.request.Request(discovery, headers={"Accept": "application/json"})
        with http_urlopen(req, timeout=10) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        return {
            "status": "unreachable",
            "detail": (
                f"The address answered, but with error {exc.code} "
                f"({exc.reason}). Check that this is the sign-in "
                "server's base address, and that this server is "
                "allowed to talk to it."
            ),
        }
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return {
            "status": "unreachable",
            "detail": (
                f"We could not reach that address ({reason}). Check the "
                "spelling, make sure the sign-in server is running, and "
                "that this container can reach it on your network."
            ),
        }
    except Exception as exc:  # timeout, TLS problem, …
        return {
            "status": "unreachable",
            "detail": (
                f"The connection failed ({type(exc).__name__}). Check "
                "the address and the sign-in server, then try again."
            ),
        }
    try:
        doc = json.loads(body)
    except ValueError:
        return {
            "status": "bad_config",
            "detail": (
                "We reached the address, but it did not return a "
                "sign-in service description. Double-check this is the "
                "issuer URL (the base address of your SSO server, "
                "without extra path)."
            ),
        }
    if (
        not isinstance(doc, dict)
        or not doc.get("authorization_endpoint")
        or not doc.get("token_endpoint")
    ):
        return {
            "status": "bad_config",
            "detail": (
                "We reached the address, but it is missing the parts a "
                "sign-in service must have (authorization and token "
                "endpoints). It is probably not an OpenID Connect "
                "issuer."
            ),
        }
    return {
        "status": "reachable",
        "detail": (
            "Connection successful. This server can reach your "
            "sign-in provider. (Technical detail: OpenID Connect "
            "discovery succeeded.)"
        ),
        "discovered_issuer": str(doc.get("issuer", ""))[:255],
        "has_userinfo_endpoint": bool(doc.get("userinfo_endpoint")),
    }


def save_auth_choice(data_dir: Path, config_dir: Path, body: dict) -> dict:
    """Record the sign-in choice. For SSO, also seed
    ``config/oidc.json`` create-if-absent (the file the existing
    AuthManager reads) — never overwrite an existing one. Only an env
    var NAME for the client secret is stored; never a secret value."""
    choice = str(body.get("choice", "")).strip().lower()
    warnings: list[str] = []
    # Blocking = the next step genuinely won't work as chosen (owner
    # decision 2026-09-22): the wizard pauses for an explicit
    # "Continue anyway". Informational notes stay in `warnings` and
    # never pause. See docs: .project/DECISIONS.md owner queue.
    blocking: list[str] = []
    record: dict[str, Any] = {"auth_choice": choice}

    if choice == "local":
        pass  # zero-config: the provisioned token + session is the auth
    elif choice == "oidc":
        issuer, err = _normalize_issuer(body.get("issuer_url"))
        if err:
            raise ValueError(err)
        client_id = str(body.get("client_id", "")).strip()
        if not client_id or len(client_id) > 255:
            raise ValueError(
                "Please enter the client ID from your sign-in server "
                "(1-255 characters)."
            )
        secret_env = (
            str(body.get("client_secret_env", "")).strip() or SECRET_ENV_DEFAULT
        )
        if not _ENV_NAME_RE.match(secret_env):
            raise ValueError(
                f"{secret_env!r} is not a valid environment variable "
                "name (letters, digits, underscore; not starting with "
                "a digit). Enter the NAME of the variable that holds "
                "the client secret — never the secret itself."
            )
        record["oidc"] = {
            "issuer": issuer,
            "client_id": client_id,
            "client_secret_env": secret_env,
        }
        if not os.environ.get(secret_env):
            blocking.append(
                f"The environment variable {secret_env} is not set on "
                "this server right now. SSO sign-in will not complete "
                "until it holds your client secret (set it in your "
                "compose/host environment, then restart)."
            )
        oidc_path = Path(config_dir) / "oidc.json"
        if oidc_path.exists():
            blocking.append(
                "An SSO configuration file already exists on this "
                "server, so we left it untouched. Your answers were "
                "saved to the setup record only — sign-in will keep "
                "using the existing file."
            )
        else:
            oidc_path.parent.mkdir(parents=True, exist_ok=True)
            oidc_path.write_text(
                json.dumps(
                    {
                        "issuer": issuer,
                        "client_id": client_id,
                        "client_secret_env": secret_env,
                        "scopes": ["openid", "profile"],
                        "display_name": "My SSO",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            warnings.append(
                "SSO details saved. Sign-in through your SSO server "
                "becomes available after the app next restarts."
            )
    else:
        raise ValueError("Please choose how you want to sign in.")

    _save_choices(data_dir, record)
    return {"auth_choice": choice, "warnings": warnings, "blocking": blocking}


def apply_comfort(data_dir: Path, body: dict) -> dict:
    """Three plain toggles, mapped onto the validated prefs vocabulary:
    larger text (text_scale 1.25), gentle animation (motion subtle), and
    the residents/companion pack (personality_pack "residents" | "off").
    Comfort defaults (off) are the accessibility-minimum values; the crew
    default is on ("residents", owner decision 2026-09-25).

    ``crew_on`` is opt-in to *change*: absent leaves whatever pack is
    already chosen (and the shipped default, ``residents``) untouched.
    """
    from . import prefs
    from .app import load_world, save_world

    world_path = Path(data_dir) / "world.json"
    try:
        world = load_world(world_path)
    except Exception as exc:
        raise RuntimeError(
            "Your world file could not be read, so comfort settings "
            f"were not saved ({type(exc).__name__}). The 'getting "
            "things ready' step may not have finished — go back a step "
            "and try again."
        ) from exc
    updates = {
        "text_scale": 1.25 if body.get("larger_text") else 1.0,
        "motion": "subtle" if body.get("gentle_animations") else "reduced",
    }
    if "crew_on" in body:
        # "residents" is the crew of companions reporting their systems;
        # "off" is the one plain voice. Absent is left alone.
        updates["personality_pack"] = (
            "residents" if body.get("crew_on") else "off"
        )
    effective = prefs.set_prefs(world, updates)
    save_world(world, world_path)
    comfort = {
        "larger_text": bool(body.get("larger_text")),
        "gentle_animations": bool(body.get("gentle_animations")),
        "crew_on": effective["personality_pack"] == "residents",
    }
    _save_choices(data_dir, {"comfort": comfort})
    return {
        "applied": {
            k: effective[k]
            for k in ("text_scale", "motion", "personality_pack")
        },
        "comfort": comfort,
    }


# ── the starter crew + the companion choice ──────────────────────────


def starter_crew() -> list[dict[str, Any]]:
    """The drawn starter crew as the wizard presents it.

    Starter data only — id, name, blurb, portrait_asset — never a
    principal's roster and never anything personal. Sol is deliberately
    absent: she is the Worlds mark, never a companion.
    """
    from . import crew

    return [
        {
            "id": spec["id"],
            "name": spec["name"],
            "blurb": spec["blurb"],
            "portrait_asset": spec["portrait_asset"],
        }
        for spec in crew.STARTER_CREW
    ]


def _starter_ids() -> set[str]:
    from . import crew

    return {spec["id"] for spec in crew.STARTER_CREW}


def apply_companion(data_dir: Path, body: dict) -> dict:
    """Record the chosen starter companion in prefs, or ``null`` for the
    plain voice (the Assistant), and in the setup record so a resumed
    wizard shows it.

    The vocabulary is the *starter* crew and nothing else: this early,
    no principal's roster exists, Sol is never a companion, and an id
    outside the drawn set is refused with a plain sentence (422).
    """
    from . import prefs
    from .app import load_world, save_world

    companion_id = body.get("companion_id")
    if companion_id is not None and not isinstance(companion_id, str):
        raise ValueError(
            "companion_id must be a companion id from the starter crew, "
            "or null for the plain voice (the Assistant)."
        )
    world_path = Path(data_dir) / "world.json"
    try:
        world = load_world(world_path)
    except Exception as exc:
        raise RuntimeError(
            "Your world file could not be read, so the companion choice "
            f"was not saved ({type(exc).__name__}). The 'getting things "
            "ready' step may not have finished — go back a step and try "
            "again."
        ) from exc
    try:
        effective = prefs.set_prefs(
            world, {"companion_id": companion_id}, companion_ids=_starter_ids()
        )
    except prefs.PrefsValueError as exc:
        raise ValueError(
            f"{companion_id!r} is not one of the starter companions. "
            "Choose a companion from the list, or null for the plain "
            "voice (the Assistant)."
        ) from exc
    save_world(world, world_path)
    chosen = effective["companion_id"]
    _save_choices(data_dir, {"companion_id": chosen})
    return {"companion_id": chosen}


def _choices_path(data_dir: Path) -> Path:
    return Path(data_dir) / CHOICES_FILE


def _load_choices(data_dir: Path) -> dict:
    try:
        data = json.loads(_choices_path(data_dir).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_choices(data_dir: Path, update: dict) -> None:
    """Merge update into the setup record (no secrets are ever part of
    it — only the SSO env var NAME)."""
    choices = _load_choices(data_dir)
    choices.update(update)
    path = _choices_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(choices, indent=2), encoding="utf-8")


def finish(data_dir: Path, journal=None) -> None:
    """Write the marker (create-if-absent) and journal the event."""
    marker = Path(data_dir) / SETUP_MARKER
    if not marker.exists():
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("ok", encoding="utf-8")
    if journal is not None:
        from .model import JournalKind

        journal.record(
            kind=JournalKind.SETTINGS_CHANGE,
            summary="first-run setup completed (setup wizard)",
            source="setup-wizard",
        )


# ── routes ───────────────────────────────────────────────────────────


def _require_local_peer(request: Request) -> None:
    """First-run setup WRITES are loopback-only (fail closed).

    The wizard provisions the instance credential and stores, so a
    remote peer must never be able to claim a fresh, unauthenticated
    instance. GET state routes stay readable; the TestClient's ASGI
    peer ("testclient") is loopback by design, so tests that
    exercise the wizard keep working.
    """
    from .api import _is_true_loopback

    if not _is_true_loopback(request):
        raise HTTPException(
            status_code=403,
            detail="setup is only available from the local machine",
        )


def register_setup_wizard(
    app: FastAPI, *, data_dir: Path, config_dir: Path, journal=None
) -> None:
    """Mount the wizard. Additive: registers /setup, /setup/{asset}
    and /api/setup-wizard/* only. Must be registered BEFORE any
    catch-all route so the wizard wins during first-run."""
    data_dir = Path(data_dir)
    config_dir = Path(config_dir)
    static_dir = Path(__file__).parent / "static" / "setup"

    def _require_first_run() -> None:
        if not setup_needed(data_dir):
            raise HTTPException(
                status_code=404,
                detail="setup is not available — this instance is already set up",
            )

    @app.get("/setup", include_in_schema=False)
    async def setup_page() -> Any:
        if not setup_needed(data_dir):
            # Refuse after setup so the wizard can never be re-run by
            # accident; the redirect lands the person in their app.
            return RedirectResponse("/", status_code=303)
        index = static_dir / "index.html"
        if not index.is_file():
            return JSONResponse(
                {
                    "ok": False,
                    "warnings": [
                        "the setup wizard files are missing from this installation"
                    ],
                },
                status_code=503,
            )
        return FileResponse(
            index,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/setup/{asset}", include_in_schema=False)
    async def setup_asset(asset: str) -> Any:
        ctype = _SETUP_ASSETS.get(asset)
        if ctype is None or "/" in asset or ".." in asset:
            raise HTTPException(status_code=404, detail="unknown asset")
        path = static_dir / asset
        if not path.is_file():
            raise HTTPException(status_code=404, detail="asset missing")
        return FileResponse(
            path, media_type=ctype, headers={"Cache-Control": "no-store"}
        )

    @app.get("/api/setup-wizard/state")
    async def wizard_state() -> dict:
        _require_first_run()
        choices = _load_choices(data_dir)
        return {
            "ok": True,
            "data": {
                "setup_needed": True,
                "provisioned": {
                    "env_file": (data_dir / ".env").is_file(),
                    "world": (data_dir / "world.json").is_file(),
                },
                "choices": choices,
            },
        }

    @app.post("/api/setup-wizard/provision")
    async def wizard_provision(request: Request) -> dict:
        _require_local_peer(request)
        _require_first_run()
        try:
            result = await run_in_threadpool(provision, data_dir, config_dir, journal)
        except RuntimeError as exc:
            # Plain words + what to do; no stack, no secrets.
            return JSONResponse(
                {
                    "ok": False,
                    "status": "unavailable",
                    "warnings": [
                        f"{exc}. Check that the data folder is "
                        "writable by this app, then press Retry."
                    ],
                },
                status_code=500,
            )
        warnings = result.pop("warnings", [])
        return {"ok": True, "data": result, "warnings": warnings}

    @app.post("/api/setup-wizard/test-oidc")
    async def wizard_test_oidc(request: Request) -> dict:
        _require_local_peer(request)
        _require_first_run()
        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        issuer = (body or {}).get("issuer_url", "")
        result = await run_in_threadpool(test_oidc_discovery, issuer)
        return {"ok": result["status"] == "reachable", "data": result}

    @app.post("/api/setup-wizard/auth-choice")
    async def wizard_auth_choice(request: Request) -> dict:
        _require_local_peer(request)
        _require_first_run()
        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="body must be an object")
        try:
            result = save_auth_choice(data_dir, config_dir, body)
        except ValueError as exc:
            return JSONResponse(
                {"ok": False, "status": "invalid_state", "warnings": [str(exc)]},
                status_code=422,
            )
        return {
            "ok": True,
            "data": {"auth_choice": result["auth_choice"]},
            "warnings": result["warnings"],
            "blocking": result["blocking"],
        }

    @app.post("/api/setup-wizard/comfort")
    async def wizard_comfort(request: Request) -> dict:
        _require_local_peer(request)
        _require_first_run()
        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        if not isinstance(body, dict):
            body = {}
        try:
            result = await run_in_threadpool(apply_comfort, data_dir, body)
        except RuntimeError as exc:
            return JSONResponse(
                {"ok": False, "status": "unavailable", "warnings": [str(exc)]},
                status_code=500,
            )
        return {"ok": True, "data": result}

    @app.get("/api/setup-wizard/crew")
    async def wizard_crew() -> dict:
        """The starter crew the wizard may offer (first-run only).

        Exactly the drawn canon — id, name, blurb, portrait_asset — and
        nothing personal. Read-only like ``/state``; no loopback gate.
        """
        _require_first_run()
        return {"ok": True, "data": starter_crew()}

    @app.post("/api/setup-wizard/companion")
    async def wizard_companion(request: Request) -> dict:
        """Set the chosen companion: a starter id, or null for the plain
        voice (the Assistant). Loopback + first-run only, like the other
        wizard writes. Unknown or non-starter id → 422 with a sentence.
        """
        _require_local_peer(request)
        _require_first_run()
        try:
            body = await request.json()
        except ValueError as _err:
            raise HTTPException(status_code=400, detail="body must be JSON") from _err
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="body must be an object")
        try:
            result = await run_in_threadpool(apply_companion, data_dir, body)
        except RuntimeError as exc:
            return JSONResponse(
                {"ok": False, "status": "unavailable", "warnings": [str(exc)]},
                status_code=500,
            )
        except ValueError as exc:
            return JSONResponse(
                {
                    "ok": False,
                    "status": "invalid_state",
                    "detail": str(exc),
                    "warnings": [str(exc)],
                },
                status_code=422,
            )
        return {"ok": True, "data": result}

    @app.post("/api/setup-wizard/finish")
    async def wizard_finish(request: Request) -> Any:
        _require_local_peer(request)
        _require_first_run()
        await run_in_threadpool(finish, data_dir, journal)
        response = JSONResponse({"ok": True, "data": {"redirect": "/"}})
        # "Just me on this device": land the person signed in. Mint a
        # real browser session through the existing AuthManager using
        # the provisioned token — the token itself never leaves the
        # server, and the cookie mirrors auth_routes' settings.
        auth = getattr(request.app.state, "auth", None)
        token = os.environ.get("PW_API_TOKEN")
        if auth is not None and token:
            try:
                session = auth.login_local(token)
            except Exception:
                session = None
            if session is not None:
                response.set_cookie(
                    "pw_session",
                    session.id,
                    httponly=True,
                    secure=True,
                    samesite="lax",
                    max_age=86400,
                )
        return response
