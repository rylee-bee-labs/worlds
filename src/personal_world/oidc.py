"""Generic OIDC relying party: discovery, PKCE, id_token verification.

Project Worlds is a self-hosted, provider-neutral product: an owner
points it at THEIR OWN identity provider. Authelia is the reference
provider in the wild, but nothing in this module knows Authelia's URL
shapes — every endpoint comes from the provider's own discovery
document (``/.well-known/openid-configuration``), so any conformant
OIDC IdP works.

Truth boundaries (deliberate, and the reason this file exists):

- ``config/oidc.json`` holds non-secret wiring only:
  ``{issuer, client_id, client_secret_env, scopes, display_name}``.
- The client secret is read **only** from the environment variable
  named by ``client_secret_env``, at call time. It is never stored on
  an object, never written to disk, never logged, never echoed into a
  response.
- Identity mapping stays in ``identity.py`` (``resolve_oidc_principal``)
  and the browser session stays in ``auth.py`` (``SessionStore``). This
  module verifies what the IdP asserted and hands back a subject; it
  never invents a parallel auth model.
- Signature verification uses the optional ``cryptography`` extra when
  it is installed (the shipped container installs it) and a strict
  stdlib RSA PKCS#1 v1.5 verifier otherwise, so RS256/384/512 — what
  Authelia and most IdPs use by default — still verify on a minimal
  install. Algorithms that need ``cryptography`` fail closed with an
  reason; an unverified id_token is never accepted.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from .url_safety import http_urlopen

_logger = logging.getLogger("personal_world.oidc")

# Optional extra, same convention as vault.py: present in the shipped
# image and in a `--extra crypto` dev install, absent in the minimal
# test install. Absence reports a degraded state, never silently.
try:  # pragma: no cover - depends on the install
    from cryptography.exceptions import InvalidSignature as _InvalidSignature
    from cryptography.hazmat.primitives import hashes as _hashes
    from cryptography.hazmat.primitives.asymmetric import ec as _ec
    from cryptography.hazmat.primitives.asymmetric import ed25519 as _ed25519
    from cryptography.hazmat.primitives.asymmetric import padding as _padding
    from cryptography.hazmat.primitives.asymmetric import rsa as _rsa
    from cryptography.hazmat.primitives.asymmetric.utils import (
        encode_dss_signature as _encode_dss_signature,
    )

    _HAS_CRYPTO = True
except ImportError:  # pragma: no cover - depends on the install
    _HAS_CRYPTO = False

# --- names and tunables -------------------------------------------------

CONFIG_FILENAME = "oidc.json"
DISCOVERY_PATH = "/.well-known/openid-configuration"

FLOW_COOKIE = "pw_oidc_state"
"""HttpOnly cookie carrying the signed, in-flight login (state, PKCE
verifier, nonce, redirect_uri). Same-site + HttpOnly + signed, so a
third party cannot forge or swap a login attempt."""

LOGIN_MAX_AGE = 600.0
"""A login attempt is valid for ten minutes, then it must be restarted."""

DISCOVERY_TTL = 300.0
DISCOVERY_ERROR_TTL = 60.0
"""A failed probe is cached too. Without it, an anonymous visitor to the
login page could make every request block on a 10s timeout to a dead
IdP; with it, recovery is visible within a minute."""

JWKS_TTL = 3600.0
"""Cache windows. The status endpoint is unauthenticated, so caching is
also what keeps an anonymous caller from using us to hammer an IdP."""

CLOCK_SKEW = 120.0
"""Tolerance for exp/nbf on a small self-hosted box with drifting time."""

MAX_FUTURE_IAT = 300.0

DISCOVERY_TIMEOUT = 10.0
TOKEN_TIMEOUT = 15.0
JWKS_TIMEOUT = 10.0
USERINFO_TIMEOUT = 10.0

# status vocabulary for GET /api/auth/oidc/status.
NOT_CONFIGURED = "not_configured"
CONFIGURED = "configured"
UNREACHABLE = "unreachable"
MISCONFIGURED = "misconfigured"

_USER_AGENT = "project-worlds/oidc-rp"

# JWS algorithms we can verify. RS* work with the standard library
# alone; PS*/ES*/EdDSA need `cryptography`.
_RSA_ALGS = ("RS256", "RS384", "RS512")
_CRYPTO_ONLY_ALGS = ("PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA")

# RFC 8017 DigestInfo prefixes: the exact bytes that must precede the
# hash inside a PKCS#1 v1.5 signature. Whole-EM comparison against these
# is what makes the stdlib verifier strict rather than forgery-friendly.
_PKCS1_DIGEST_INFO = {
    "RS256": bytes.fromhex("3031300d060960864801650304020105000420"),
    "RS384": bytes.fromhex("3041300d060960864801650304020205000430"),
    "RS512": bytes.fromhex("3051300d060960864801650304020305000440"),
}

_HASH_FOR_ALG: dict[str, Callable[[], Any]] = {
    "RS256": hashlib.sha256,
    "RS384": hashlib.sha384,
    "RS512": hashlib.sha512,
    "PS256": hashlib.sha256,
    "PS384": hashlib.sha384,
    "PS512": hashlib.sha512,
    "ES256": hashlib.sha256,
    "ES384": hashlib.sha384,
    "ES512": hashlib.sha512,
}

_ECDSA_SIG_LEN = {"ES256": 32, "ES384": 48, "ES512": 66}


def supported_algorithms() -> tuple[str, ...]:
    """Algorithms this install can actually verify right now."""
    return _RSA_ALGS + (_CRYPTO_ONLY_ALGS if _HAS_CRYPTO else ())


def signature_verification_state() -> dict[str, Any]:
    """capability report — never a promise we cannot keep."""
    if _HAS_CRYPTO:
        return {
            "available": True,
            "algorithms": list(supported_algorithms()),
            "backend": "cryptography",
        }
    return {
        "available": True,
        "algorithms": list(supported_algorithms()),
        "backend": "stdlib",
        "reason": (
            "the 'cryptography' package is not installed; RS256/"
            "RS384/RS512 verify with the standard library, other "
            "algorithms fail closed. Install with: "
            "uv sync --extra crypto"
        ),
    }


# --- errors -------------------------------------------------------------


class OIDCError(Exception):
    """Base class. Every message is written for a human operator and is
    guaranteed secret-free: it may name the provider, the config field
    and the failure, never a credential, token or identity claim."""

    status = MISCONFIGURED
    http_status = 500
    error_code = "oidc_error"

    def __init__(self, detail: str, *, warnings: list[str] | None = None):
        super().__init__(detail)
        self.detail = detail
        self.warnings = list(warnings or [])


class OIDCNotConfigured(OIDCError):
    """No ``config/oidc.json``. A healthy default state, not a fault:
    local token auth is the product's built-in path."""

    status = NOT_CONFIGURED
    http_status = 404
    error_code = "oidc_not_configured"


class OIDCMisconfigured(OIDCError):
    """Configuration or provider metadata is unusable. Operator action
    required; retrying will not help."""

    status = MISCONFIGURED
    http_status = 500
    error_code = "oidc_misconfigured"


class OIDCUnreachable(OIDCError):
    """The provider did not answer (DNS, TLS, timeout, 5xx). The
    configuration may be fine; the network or the IdP is not."""

    status = UNREACHABLE
    http_status = 502
    error_code = "oidc_unreachable"


class OIDCLoginError(OIDCError):
    """A single login attempt failed after configuration checked out:
    bad state, expired attempt, rejected code, unverifiable id_token.

    This is not one of the four configuration states — the provider
    config may be perfectly fine and this browser's attempt still
    failed — so it reports its own status instead of borrowing
    ``configured``.
    """

    status = "login_failed"
    http_status = 400
    error_code = "oidc_login_failed"

    def __init__(
        self,
        detail: str,
        *,
        error_code: str = "oidc_login_failed",
        http_status: int = 400,
        warnings: list[str] | None = None,
    ):
        super().__init__(detail, warnings=warnings)
        self.error_code = error_code
        self.http_status = http_status


# --- base64url / JWT plumbing ------------------------------------------


def _b64u_decode(segment: str) -> bytes:
    pad = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + pad)


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_int(segment: str) -> int:
    return int.from_bytes(_b64u_decode(segment), "big")


def _normalize_issuer(issuer: str) -> str:
    return (issuer or "").strip().rstrip("/")


def _decode_json_body(body: bytes, *, what: str) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise OIDCUnreachable(f"{what} returned a body that is not valid JSON ({exc})") from exc


# --- configuration ------------------------------------------------------


@dataclass(frozen=True)
class OIDCSettings:
    """The non-secret half of an OIDC client.

    Exactly the documented ``config/oidc.json`` shape. The client secret
    is not a field: ``client_secret_env`` names the environment variable
    that holds it, and the value is read at call time only.
    """

    issuer: str
    client_id: str
    client_secret_env: str = ""
    scopes: tuple[str, ...] = ("openid", "profile")
    display_name: str = "SSO"
    warnings: tuple[str, ...] = ()

    @property
    def client_secret(self) -> str:
        """The secret value, read from the named env var on every call.

        Never cached on the object, never logged, never serialised. An
        unset variable yields ``""`` so callers can report the
        'secret not set' state instead of crashing mid-login.
        """
        if not self.client_secret_env:
            return ""
        return os.environ.get(self.client_secret_env, "") or ""

    @property
    def client_secret_present(self) -> bool:
        return bool(self.client_secret_env) and bool(self.client_secret)

    def public_dict(self) -> dict[str, Any]:
        """Safe to hand to an unauthenticated caller: wiring, not
        secrets. The env var *name* is operator configuration and is
        already documented; its value never leaves the process."""
        return {
            "issuer": self.issuer,
            "client_id": self.client_id,
            "client_secret_env": self.client_secret_env,
            "client_secret_present": self.client_secret_present,
            "scopes": list(self.scopes),
            "display_name": self.display_name,
        }


_KNOWN_SETTINGS_KEYS = (
    "issuer",
    "client_id",
    "client_secret_env",
    "scopes",
    "display_name",
)


def settings_from_dict(data: Any) -> OIDCSettings:
    """Parse and validate the config shape. Raises ``OIDCMisconfigured``
    with a specific, actionable reason rather than a stack trace."""
    if not isinstance(data, dict):
        raise OIDCMisconfigured(f"{CONFIG_FILENAME} must contain a JSON object")
    warnings: list[str] = []
    for key in data:
        if key.startswith("_"):
            continue  # documentation keys ("_comment": ...) are allowed
        if key not in _KNOWN_SETTINGS_KEYS:
            warnings.append(f"{CONFIG_FILENAME}: ignoring unknown key '{key}'")

    issuer = _normalize_issuer(str(data.get("issuer") or ""))
    client_id = str(data.get("client_id") or "").strip()
    secret_env = str(data.get("client_secret_env") or "").strip()
    raw_scopes = data.get("scopes")
    if raw_scopes is None:
        scopes_list: list[str] = ["openid", "profile"]
    elif isinstance(raw_scopes, str):
        scopes_list = raw_scopes.split()
    elif isinstance(raw_scopes, (list, tuple)):
        scopes_list = [str(s).strip() for s in raw_scopes]
    else:
        raise OIDCMisconfigured(f"{CONFIG_FILENAME}: 'scopes' must be a list")
    scopes = tuple(dict.fromkeys(s for s in scopes_list if s))
    display_name = str(data.get("display_name") or "SSO").strip() or "SSO"

    problems: list[str] = []
    if not issuer:
        problems.append("'issuer' is required")
    elif not issuer.startswith(("https://", "http://")):
        problems.append("'issuer' must be an absolute http(s) URL")
    if not client_id:
        problems.append("'client_id' is required")
    if "openid" not in scopes:
        problems.append("'scopes' must include 'openid'")
    if problems:
        raise OIDCMisconfigured(f"{CONFIG_FILENAME} is invalid: " + "; ".join(problems))

    if issuer.startswith("http://"):
        warnings.append(
            "issuer is plain HTTP; acceptable for a loopback test IdP "
            "only, never for a reachable deployment"
        )
    if not secret_env:
        warnings.append(
            "no 'client_secret_env': treated as a public client, "
            "authenticated by PKCE alone"
        )

    return OIDCSettings(
        issuer=issuer,
        client_id=client_id,
        client_secret_env=secret_env,
        scopes=scopes,
        display_name=display_name,
        warnings=tuple(warnings),
    )


def load_settings(config_dir: Path | str) -> OIDCSettings:
    """Read ``<config_dir>/oidc.json``.

    A missing file is the healthy default (``OIDCNotConfigured``): local
    bearer/session auth keeps working exactly as before. A present but
    broken file is ``OIDCMisconfigured`` — never silently ignored,
    because a silent 'OIDC just isn't there' is how an owner ends up
    believing SSO is on when it is not.
    """
    path = Path(config_dir) / CONFIG_FILENAME
    if not path.is_file():
        raise OIDCNotConfigured(
            f"no OIDC provider configured ({path.name} "
            "not present in the config directory)"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OIDCError:
        raise
    except Exception as exc:
        raise OIDCMisconfigured(f"{CONFIG_FILENAME} is not valid JSON: {exc}") from exc
    return settings_from_dict(data)


# --- discovery ----------------------------------------------------------


@dataclass(frozen=True)
class Discovery:
    """Provider metadata, exactly as the IdP published it."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    userinfo_endpoint: str | None = None
    end_session_endpoint: str | None = None
    scopes_supported: tuple[str, ...] = ()
    code_challenge_methods_supported: tuple[str, ...] = ()
    token_endpoint_auth_methods_supported: tuple[str, ...] = ()
    id_token_signing_alg_values_supported: tuple[str, ...] = ()
    fetched_at: float = 0.0
    warnings: tuple[str, ...] = ()

    def public_dict(self) -> dict[str, Any]:
        """Discovery metadata minus anything secret. Everything here is
        published by the provider at an unauthenticated URL by design.
        ``checked_at`` says how fresh the answer is, so a stale result
        from cache is never mistaken for a live one."""
        return {
            "issuer": self.issuer,
            "authorization_endpoint": self.authorization_endpoint,
            "token_endpoint": self.token_endpoint,
            "userinfo_endpoint": self.userinfo_endpoint,
            "jwks_uri": self.jwks_uri,
            "end_session_endpoint": self.end_session_endpoint,
            "scopes_supported": list(self.scopes_supported),
            "code_challenge_methods_supported": list(
                self.code_challenge_methods_supported
            ),
            "token_endpoint_auth_methods_supported": list(
                self.token_endpoint_auth_methods_supported
            ),
            "id_token_signing_alg_values_supported": list(
                self.id_token_signing_alg_values_supported
            ),
            "checked_at": self.fetched_at,
        }


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value)
    return ()


def _require_endpoint(doc: dict, key: str, url: str) -> str:
    value = str(doc.get(key) or "").strip()
    if not value:
        raise OIDCMisconfigured(f"discovery document at {url} has no '{key}'")
    if not value.startswith(("https://", "http://")):
        raise OIDCMisconfigured(f"discovery '{key}' is not an absolute http(s) URL")
    return value


def parse_discovery(
    doc: Any, settings: OIDCSettings, *, url: str, fetched_at: float
) -> Discovery:
    """Validate a discovery document against the configured issuer.

    The issuer echo check is not ceremony: it is what stops a redirected
    or spoofed discovery document from being accepted for a different
    provider.
    """
    if not isinstance(doc, dict):
        raise OIDCMisconfigured(f"discovery document at {url} is not a JSON object")
    published = _normalize_issuer(str(doc.get("issuer") or ""))
    if not published:
        raise OIDCMisconfigured(f"discovery document at {url} has no 'issuer'")
    if published != settings.issuer:
        raise OIDCMisconfigured(
            f"discovery issuer '{published}' does not match configured "
            f"issuer '{settings.issuer}'"
        )

    discovery = Discovery(
        issuer=published,
        authorization_endpoint=_require_endpoint(doc, "authorization_endpoint", url),
        token_endpoint=_require_endpoint(doc, "token_endpoint", url),
        jwks_uri=_require_endpoint(doc, "jwks_uri", url),
        userinfo_endpoint=str(doc.get("userinfo_endpoint") or "").strip() or None,
        end_session_endpoint=(
            str(doc.get("end_session_endpoint") or "").strip() or None
        ),
        scopes_supported=_as_str_tuple(doc.get("scopes_supported")),
        code_challenge_methods_supported=_as_str_tuple(
            doc.get("code_challenge_methods_supported")
        ),
        token_endpoint_auth_methods_supported=_as_str_tuple(
            doc.get("token_endpoint_auth_methods_supported")
        ),
        id_token_signing_alg_values_supported=_as_str_tuple(
            doc.get("id_token_signing_alg_values_supported")
        ),
        fetched_at=fetched_at,
    )

    warnings: list[str] = []
    methods = discovery.code_challenge_methods_supported
    if methods and "S256" not in methods:
        warnings.append(
            "provider does not advertise S256 PKCE support "
            f"(advertised: {', '.join(methods)})"
        )
    if discovery.scopes_supported:
        missing = [s for s in settings.scopes if s not in discovery.scopes_supported]
        if missing:
            warnings.append(
                "configured scopes not advertised by the provider: "
                + ", ".join(missing)
            )
    if not discovery.end_session_endpoint:
        warnings.append(
            "provider does not advertise an end_session_endpoint; logout "
            "ends the local session only"
        )
    algs = discovery.id_token_signing_alg_values_supported
    if algs and not set(algs) & set(supported_algorithms()):
        warnings.append(
            "provider advertises only id_token signing algorithms this "
            f"install cannot verify ({', '.join(algs)}); sign-in will fail "
            "closed"
        )
    secret = settings.client_secret
    auth_methods = discovery.token_endpoint_auth_methods_supported
    if not secret and auth_methods and "none" not in auth_methods:
        warnings.append(
            "provider requires a client secret but no secret is set: "
            "export the variable named by 'client_secret_env'"
        )
    if (
        not secret
        and settings.client_secret_env
        and (not auth_methods or "none" in auth_methods)
    ):
        # Named a secret variable, then left it unset. The provider will
        # accept a public client, so this must be visible rather than
        # silently downgrading the client's authentication.
        warnings.append(
            f"the variable named by 'client_secret_env' "
            f"({settings.client_secret_env}) is not set; the provider allows "
            "public-client auth, so sign-in will be attempted without a secret"
        )
    return replace(discovery, warnings=tuple(warnings))


# --- HTTP entry point ----------------------------------------------------------

Transport = Callable[..., tuple[int, bytes]]


def default_transport(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> tuple[int, bytes]:
    """One boring HTTP call on the standard library.

    Returns ``(status, body)`` for any HTTP response — including 4xx/5xx,
    so provider error payloads stay readable — and raises
    ``OIDCUnreachable`` for DNS/TLS/timeout failures. Tests inject a stub
    transport instead of reaching the network.
    """
    request_headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    request_headers.update(headers or {})
    request = urllib.request.Request(
        url, data=data, headers=request_headers, method="POST" if data else "GET"
    )
    try:
        with http_urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:  # a real HTTP answer
        try:
            return exc.code, exc.read()
        except Exception:
            return exc.code, b""
    except Exception as exc:
        raise OIDCUnreachable(f"could not reach {url}: {type(exc).__name__}: {exc}") from exc


# --- PKCE ---------------------------------------------------------------


def new_code_verifier() -> str:
    """RFC 7636 verifier: 43-128 chars from the unreserved set."""
    return _b64u_encode(secrets.token_bytes(32))


def code_challenge(verifier: str) -> str:
    return _b64u_encode(hashlib.sha256(verifier.encode("ascii")).digest())


# --- in-flight login state ---------------------------------------------


@dataclass(frozen=True)
class PendingLogin:
    """One in-flight authorization-code login."""

    state: str
    code_verifier: str
    nonce: str
    redirect_uri: str
    issued_at: float
    # Set only when a signed-in person started "link my sign-in": the
    # local principal id the verified subject will be linked to.
    link_to: str | None = None
    # Set only for "Confirm it's you" by a fresh provider sign-in: the
    # local principal whose session gets the step-up, and the same-site
    # path to return to afterwards.
    step_up_for: str | None = None
    return_to: str | None = None


class FlowCodec:
    """Encodes a ``PendingLogin`` into an HttpOnly cookie value.

    Signed with a per-process key so a cookie tossed by a subdomain or a
    proxy cannot substitute someone else's state/verifier. The payload
    holds no credential — a PKCE verifier and a nonce are single-use
    public-flow values — and it expires with the login attempt.
    """

    def __init__(
        self,
        key: bytes | None = None,
        max_age: float = LOGIN_MAX_AGE,
        clock: Callable[[], float] = time.time,
    ):
        self._key = key or secrets.token_bytes(32)
        self._max_age = max_age
        self._clock = clock

    def encode(self, pending: PendingLogin) -> str:
        payload = _b64u_encode(
            json.dumps(
                {
                    "state": pending.state,
                    "code_verifier": pending.code_verifier,
                    "nonce": pending.nonce,
                    "redirect_uri": pending.redirect_uri,
                    "issued_at": pending.issued_at,
                    "link_to": pending.link_to,
                    "step_up_for": pending.step_up_for,
                    "return_to": pending.return_to,
                },
                separators=(",", ":"),
            ).encode("utf-8")
        )
        return f"{payload}.{self._sign(payload)}"

    def decode(self, blob: str | None) -> PendingLogin:
        if not blob or "." not in blob:
            raise OIDCLoginError(
                "no sign-in attempt in progress; start again from the login page",
                error_code="oidc_missing_state",
            )
        payload, _, signature = blob.rpartition(".")
        if not hmac.compare_digest(self._sign(payload), signature):
            raise OIDCLoginError(
                "the sign-in attempt cookie failed its integrity check; "
                "start again from the login page",
                error_code="oidc_state_invalid",
            )
        try:
            data = json.loads(_b64u_decode(payload).decode("utf-8"))
            pending = PendingLogin(
                state=str(data["state"]),
                code_verifier=str(data["code_verifier"]),
                nonce=str(data["nonce"]),
                redirect_uri=str(data["redirect_uri"]),
                issued_at=float(data["issued_at"]),
                link_to=(str(data["link_to"]) if data.get("link_to") else None),
                step_up_for=(
                    str(data["step_up_for"]) if data.get("step_up_for") else None
                ),
                return_to=(str(data["return_to"]) if data.get("return_to") else None),
            )
        except Exception as _err:
            raise OIDCLoginError(
                "the sign-in attempt cookie is unreadable; start again "
                "from the login page",
                error_code="oidc_state_invalid",
            ) from _err
        if self._clock() - pending.issued_at > self._max_age:
            raise OIDCLoginError(
                "that sign-in attempt expired; start again from the login page",
                error_code="oidc_attempt_expired",
            )
        return pending

    def _sign(self, payload: str) -> str:
        return _b64u_encode(
            hmac.new(self._key, payload.encode("ascii"), hashlib.sha256).digest()
        )


# --- id_token verification ---------------------------------------------


@dataclass(frozen=True)
class VerifiedIdentity:
    """What the IdP asserted, after signature and claim validation.

    Holds no raw claim payload and no tokens: there is nothing here to
    leak into a log line or a response body.
    """

    sub: str
    display_name: str | None = None
    email: str | None = None
    issuer: str = ""
    auth_time: float | None = None
    claim_names: tuple[str, ...] = ()
    #: Group names the provider asserted (Authelia's ``groups`` claim,
    #: id_token or userinfo). Used ONLY to look up a role in
    #: ``PW_ROLE_GROUPS``; never authorization by itself, and never a
    #: role the IdP can hand out (owner is not mappable).
    groups: tuple[str, ...] = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"VerifiedIdentity(sub={self.sub!r}, "
            f"display_name={self.display_name!r}, "
            f"issuer={self.issuer!r}, claims={len(self.claim_names)})"
        )


def _kty_for_alg(alg: str) -> str:
    if alg.startswith(("RS", "PS")):
        return "RSA"
    if alg.startswith("ES"):
        return "EC"
    if alg == "EdDSA":
        return "OKP"
    raise OIDCLoginError(
        f"unsupported id_token algorithm '{alg}'", error_code="oidc_alg_unsupported"
    )


class _KeyNotFound(Exception):
    """Internal: no JWKS key matches; the caller may refresh once."""


def _select_jwk(jwks: Any, header: dict, alg: str) -> dict:
    if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
        raise OIDCUnreachable("provider JWKS is not a valid JWK Set")
    want_kty = _kty_for_alg(alg)
    candidates = [
        k
        for k in jwks["keys"]
        if isinstance(k, dict)
        and k.get("kty") == want_kty
        and k.get("use", "sig") == "sig"
    ]
    kid = header.get("kid")
    if kid is not None:
        matched = [k for k in candidates if k.get("kid") == kid]
        if not matched:
            raise _KeyNotFound()
        candidates = matched
    if not candidates:
        raise _KeyNotFound()
    if len(candidates) > 1 and kid is None:
        raise OIDCLoginError(
            "provider JWKS holds several signing keys and the id_token "
            "carries no 'kid' to choose between them",
            error_code="oidc_key_ambiguous",
        )
    return candidates[0]


def _verify_rsa_pkcs1_stdlib(
    alg: str, jwk: dict, signing_input: bytes, signature: bytes
) -> bool:
    """Strict PKCS#1 v1.5 verification with the standard library only.

    The expected encoded message is built in full and compared whole
    (``hmac.compare_digest``), so the lax-parsing forgeries that a
    'find the prefix' implementation invites do not apply.
    """
    try:
        n = _b64u_int(jwk["n"])
        e = _b64u_int(jwk["e"])
    except Exception:
        return False
    k = (n.bit_length() + 7) // 8
    prefix = _PKCS1_DIGEST_INFO[alg]
    digest = _HASH_FOR_ALG[alg](signing_input).digest()
    padding_len = k - 3 - len(prefix) - len(digest)
    if e < 3 or padding_len < 8 or len(signature) != k:
        return False
    try:
        encoded = pow(int.from_bytes(signature, "big"), e, n).to_bytes(k, "big")
    except Exception:
        return False
    expected = b"\x00\x01" + b"\xff" * padding_len + b"\x00" + prefix + digest
    return hmac.compare_digest(encoded, expected)


def _public_key_from_jwk(jwk: dict, alg: str) -> Any:
    kty = jwk.get("kty")
    try:
        if kty == "RSA":
            return _rsa.RSAPublicNumbers(
                e=_b64u_int(jwk["e"]), n=_b64u_int(jwk["n"])
            ).public_key()
        if kty == "EC":
            curves = {
                "P-256": _ec.SECP256R1(),
                "P-384": _ec.SECP384R1(),
                "P-521": _ec.SECP521R1(),
            }
            curve = curves.get(str(jwk.get("crv")))
            if curve is None:
                raise OIDCLoginError(
                    f"unsupported JWKS curve '{jwk.get('crv')}'",
                    error_code="oidc_key_unsupported",
                )
            return _ec.EllipticCurvePublicNumbers(
                x=_b64u_int(jwk["x"]), y=_b64u_int(jwk["y"]), curve=curve
            ).public_key()
        if kty == "OKP" and jwk.get("crv") == "Ed25519":
            return _ed25519.Ed25519PublicKey.from_public_bytes(_b64u_decode(jwk["x"]))
    except OIDCLoginError:
        raise
    except Exception as exc:
        raise OIDCLoginError(
            f"provider JWKS key could not be loaded ({type(exc).__name__})",
            error_code="oidc_key_unsupported",
        ) from exc
    raise OIDCLoginError(
        f"unsupported JWKS key type '{kty}'", error_code="oidc_key_unsupported"
    )


def _crypto_hash(alg: str) -> Any:
    return {"256": _hashes.SHA256, "384": _hashes.SHA384, "512": _hashes.SHA512}[
        alg[-3:]
    ]()


def _verify_with_cryptography(
    alg: str, jwk: dict, signing_input: bytes, signature: bytes
) -> bool:
    key = _public_key_from_jwk(jwk, alg)
    try:
        if alg.startswith("RS"):
            key.verify(signature, signing_input, _padding.PKCS1v15(), _crypto_hash(alg))
        elif alg.startswith("PS"):
            key.verify(
                signature,
                signing_input,
                _padding.PSS(
                    mgf=_padding.MGF1(_crypto_hash(alg)), salt_length=_padding.PSS.AUTO
                ),
                _crypto_hash(alg),
            )
        elif alg.startswith("ES"):
            width = _ECDSA_SIG_LEN[alg]
            if len(signature) != 2 * width:
                return False
            der = _encode_dss_signature(
                int.from_bytes(signature[:width], "big"),
                int.from_bytes(signature[width:], "big"),
            )
            key.verify(der, signing_input, _ec.ECDSA(_crypto_hash(alg)))
        elif alg == "EdDSA":
            key.verify(signature, signing_input)
        else:  # pragma: no cover - guarded by supported_algorithms()
            return False
        return True
    except _InvalidSignature:
        return False
    except Exception as exc:
        _logger.warning(
            "oidc: signature check errored (%s): %s", type(exc).__name__, exc
        )
        return False


def verify_signature(
    alg: str, jwk: dict, signing_input: bytes, signature: bytes
) -> bool:
    """Verify a JWS signature with the best backend this install has."""
    if _HAS_CRYPTO:
        return _verify_with_cryptography(alg, jwk, signing_input, signature)
    if alg in _RSA_ALGS:
        return _verify_rsa_pkcs1_stdlib(alg, jwk, signing_input, signature)
    raise OIDCLoginError(
        f"verifying '{alg}' needs the 'cryptography' package, which is not "
        "installed; refusing an unverified id_token. Install with: "
        "uv sync --extra crypto",
        error_code="oidc_verification_unavailable",
    )


def _split_jwt(token: str) -> tuple[dict, dict, bytes, bytes]:
    parts = token.split(".")
    if len(parts) == 5:
        raise OIDCLoginError(
            "the provider returned an encrypted (JWE) id_token; encrypted "
            "id_tokens are not supported",
            error_code="oidc_id_token_encrypted",
        )
    if len(parts) != 3:
        raise OIDCLoginError(
            "id_token is not a well-formed JWS", error_code="oidc_id_token_malformed"
        )
    try:
        header = json.loads(_b64u_decode(parts[0]).decode("utf-8"))
        claims = json.loads(_b64u_decode(parts[1]).decode("utf-8"))
        signature = _b64u_decode(parts[2])
    except Exception as _err:
        raise OIDCLoginError(
            "id_token segments are not valid base64url JSON",
            error_code="oidc_id_token_malformed",
        ) from _err
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise OIDCLoginError(
            "id_token header/claims are not JSON objects",
            error_code="oidc_id_token_malformed",
        )
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    return header, claims, signing_input, signature


def validate_claims(
    claims: dict,
    *,
    settings: OIDCSettings,
    nonce: str | None,
    clock: Callable[[], float] = time.time,
    skew: float = CLOCK_SKEW,
) -> None:
    """OIDC Core 3.1.3.7 validation, fail closed on every rule.

    ``iss``/``aud``/``exp`` are mandatory; ``nonce`` is mandatory
    whenever we sent one (we always do), because it is what binds this
    id_token to this browser's login attempt.
    """
    now = clock()
    issuer = _normalize_issuer(str(claims.get("iss") or ""))
    if issuer != settings.issuer:
        raise OIDCLoginError(
            f"id_token issuer '{issuer}' does not match the configured "
            f"issuer '{settings.issuer}'",
            error_code="oidc_bad_issuer",
        )

    aud = claims.get("aud")
    if isinstance(aud, str):
        audiences = [aud]
    elif isinstance(aud, (list, tuple)):
        audiences = [str(a) for a in aud]
    else:
        audiences = []
    if settings.client_id not in audiences:
        raise OIDCLoginError(
            "id_token audience does not include this client_id",
            error_code="oidc_bad_audience",
        )
    if len(audiences) > 1 and str(claims.get("azp") or "") != settings.client_id:
        raise OIDCLoginError(
            "id_token has multiple audiences but no matching 'azp'",
            error_code="oidc_bad_audience",
        )

    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        raise OIDCLoginError(
            "id_token has no usable 'exp' claim", error_code="oidc_bad_expiry"
        )
    if now > float(exp) + skew:
        raise OIDCLoginError("id_token has expired", error_code="oidc_token_expired")

    nbf = claims.get("nbf")
    if isinstance(nbf, (int, float)) and now + skew < float(nbf):
        raise OIDCLoginError(
            "id_token is not valid yet ('nbf' in the future)",
            error_code="oidc_token_not_yet_valid",
        )

    iat = claims.get("iat")
    if isinstance(iat, (int, float)) and float(iat) > now + MAX_FUTURE_IAT:
        raise OIDCLoginError(
            "id_token was issued in the future; check the server and provider clocks",
            error_code="oidc_bad_iat",
        )

    if nonce is not None:
        presented = str(claims.get("nonce") or "")
        # compare_digest on bytes: a claim may carry non-ASCII, and the
        # str form raises TypeError instead of simply not matching.
        if not presented or not hmac.compare_digest(
            presented.encode("utf-8"), nonce.encode("utf-8")
        ):
            raise OIDCLoginError(
                "id_token nonce does not match this sign-in attempt",
                error_code="oidc_bad_nonce",
            )

    if not str(claims.get("sub") or ""):
        raise OIDCLoginError(
            "id_token has no 'sub' claim", error_code="oidc_no_subject"
        )


def _string_groups(value: Any) -> tuple[str, ...]:
    """A ``groups`` claim as a tuple of non-empty strings.

    Anything else (a bare string, numbers, nested objects, a missing
    claim) yields ``()`` — never a guessed group. These are only ever
    looked up in the operator's own ``PW_ROLE_GROUPS`` mapping, so an
    over-eager value can at most name a group the operator listed.
    """
    if not isinstance(value, list):
        return ()
    return tuple(str(g) for g in value if isinstance(g, str) and g)


def identity_from_claims(claims: dict) -> VerifiedIdentity:
    """Pick a display name from ordinary profile claims. ``sub`` stays
    the identity that ``identity.py`` maps; the display name is
    cosmetic and never authorization."""
    sub = str(claims["sub"])
    display = (
        claims.get("preferred_username")
        or claims.get("name")
        or claims.get("email")
        or sub
    )
    auth_time = claims.get("auth_time")
    return VerifiedIdentity(
        sub=sub,
        display_name=str(display) or None,
        email=str(claims["email"]) if claims.get("email") else None,
        issuer=_normalize_issuer(str(claims.get("iss") or "")),
        auth_time=float(auth_time) if isinstance(auth_time, (int, float)) else None,
        claim_names=tuple(sorted(claims)),
        groups=_string_groups(claims.get("groups")),
    )


# --- the client ---------------------------------------------------------


@dataclass
class _Cached:
    value: Any
    at: float


class OIDCClient:
    """One configured provider: discovery, login, token exchange,
    verification. Stateless about users — it returns a verified subject
    and the caller (``auth.py``/``identity.py``) owns the session."""

    def __init__(
        self,
        settings: OIDCSettings,
        *,
        transport: Transport = default_transport,
        discovery_ttl: float = DISCOVERY_TTL,
        jwks_ttl: float = JWKS_TTL,
        flow_codec: FlowCodec | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.settings = settings
        self._transport = transport
        self._discovery_ttl = discovery_ttl
        self._jwks_ttl = jwks_ttl
        self._codec = flow_codec or FlowCodec(clock=clock)
        self._clock = clock
        self._discovery: _Cached | None = None
        self._discovery_error: tuple[OIDCError, float] | None = None
        self._jwks: _Cached | None = None
        self._jwks_uri: str | None = None

    # -- discovery / jwks ------------------------------------------------

    @property
    def discovery_url(self) -> str:
        return f"{self.settings.issuer}{DISCOVERY_PATH}"

    def discover(self, *, force: bool = False) -> Discovery:
        """Fetch (or reuse) provider metadata.

        Successes are cached for ``DISCOVERY_TTL``; failures for
        ``DISCOVERY_ERROR_TTL``, so a dead IdP cannot make every login
        page load block on a network timeout, and recovery still shows
        up within a minute.
        """
        now = self._clock()
        cached = self._discovery
        if cached and not force and now - cached.at < self._discovery_ttl:
            return cached.value
        failure = self._discovery_error
        if failure and not force and now - failure[1] < DISCOVERY_ERROR_TTL:
            raise failure[0]
        try:
            discovery = self._fetch_discovery()
        except OIDCError as exc:
            self._discovery_error = (exc, now)
            raise
        self._discovery_error = None
        self._discovery = _Cached(discovery, now)
        self._jwks_uri = discovery.jwks_uri
        return discovery

    def _fetch_discovery(self) -> Discovery:
        status, body = self._transport(self.discovery_url, timeout=DISCOVERY_TIMEOUT)
        if status == 404:
            raise OIDCMisconfigured(
                f"no discovery document at {self.discovery_url} — is "
                "'issuer' the provider's base URL (no path, no trailing "
                "slash)?"
            )
        if status >= 500:
            raise OIDCUnreachable(f"provider discovery returned HTTP {status}")
        if status != 200:
            raise OIDCMisconfigured(f"provider discovery returned HTTP {status}")
        doc = _decode_json_body(body, what="discovery document")
        return parse_discovery(
            doc, self.settings, url=self.discovery_url, fetched_at=self._clock()
        )

    def cached_discovery(self) -> Discovery | None:
        return self._discovery.value if self._discovery else None

    def jwks(self, *, force: bool = False) -> Any:
        discovery = self.discover()
        cached = self._jwks
        if (
            cached
            and not force
            and self._jwks_uri == discovery.jwks_uri
            and self._clock() - cached.at < self._jwks_ttl
        ):
            return cached.value
        status, body = self._transport(discovery.jwks_uri, timeout=JWKS_TIMEOUT)
        if status != 200:
            kind = OIDCUnreachable if status >= 500 else OIDCMisconfigured
            raise kind(f"provider JWKS endpoint returned HTTP {status}")
        value = _decode_json_body(body, what="JWKS")
        self._jwks = _Cached(value, self._clock())
        self._jwks_uri = discovery.jwks_uri
        return value

    # -- login ------------------------------------------------------------

    def start_login(
        self,
        redirect_uri: str,
        link_to: str | None = None,
        step_up_for: str | None = None,
        return_to: str | None = None,
    ) -> tuple[str, PendingLogin, str]:
        """Build the authorization redirect for one fresh login attempt.

        Returns ``(authorization_url, pending, cookie_value)``. PKCE S256
        and a nonce are always sent: PKCE binds the code to this browser
        and the nonce binds the id_token to this attempt.
        """
        discovery = self.discover()
        pending = PendingLogin(
            state=secrets.token_urlsafe(24),
            code_verifier=new_code_verifier(),
            nonce=secrets.token_urlsafe(24),
            redirect_uri=redirect_uri,
            issued_at=self._clock(),
            link_to=link_to,
            step_up_for=step_up_for,
            return_to=return_to,
        )
        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "scope": " ".join(self.settings.scopes),
            "redirect_uri": redirect_uri,
            "state": pending.state,
            "nonce": pending.nonce,
            "code_challenge": code_challenge(pending.code_verifier),
            "code_challenge_method": "S256",
        }
        if step_up_for:
            # Make the provider ask again, even inside its own session.
            params["prompt"] = "login"
            params["max_age"] = "0"
        url = f"{discovery.authorization_endpoint}?{urllib.parse.urlencode(params)}"
        return url, pending, self._codec.encode(pending)

    def read_pending(self, cookie_value: str | None) -> PendingLogin:
        return self._codec.decode(cookie_value)

    def client_authentication(self, discovery: Discovery) -> str:
        """How we will authenticate to the token endpoint, decided from
        the provider's own metadata rather than a guess."""
        methods = discovery.token_endpoint_auth_methods_supported
        if self.settings.client_secret:
            if not methods or "client_secret_post" in methods:
                return "client_secret_post"
            if "client_secret_basic" in methods:
                return "client_secret_basic"
            return "client_secret_post"
        if not methods or "none" in methods:
            return "none"
        raise OIDCMisconfigured(
            "the provider requires a client secret "
            f"(advertised: {', '.join(methods)}) but the variable named by "
            f"'client_secret_env' ({self.settings.client_secret_env or 'unset'}) "
            "is not set"
        )

    def exchange_code(
        self, code: str, pending: PendingLogin, discovery: Discovery
    ) -> dict[str, Any]:
        """Authorization-code + PKCE token exchange."""
        if not code:
            raise OIDCLoginError(
                "the provider returned no authorization code", error_code="oidc_no_code"
            )
        method = self.client_authentication(discovery)
        form: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": pending.redirect_uri,
            "client_id": self.settings.client_id,
            "code_verifier": pending.code_verifier,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        secret = self.settings.client_secret
        if method == "client_secret_post":
            form["client_secret"] = secret
        elif method == "client_secret_basic":
            # RFC 6749 §2.3.1: HTTP Basic uses *standard* base64 with
            # padding, not the base64url form JWT/PKCE use.
            headers["Authorization"] = "Basic " + base64.b64encode(
                f"{self.settings.client_id}:{secret}".encode("utf-8")
            ).decode("ascii")
        body = urllib.parse.urlencode(form).encode("ascii")
        status, raw = self._transport(
            discovery.token_endpoint, data=body, headers=headers, timeout=TOKEN_TIMEOUT
        )
        if status != 200:
            raise OIDCLoginError(
                "the provider rejected the authorization code "
                f"(HTTP {status}{_provider_error_suffix(raw)})",
                error_code="oidc_token_exchange_failed",
            )
        tokens = _decode_json_body(raw, what="token endpoint")
        if not isinstance(tokens, dict):
            raise OIDCLoginError(
                "token endpoint returned a non-object body",
                error_code="oidc_token_exchange_failed",
            )
        if not tokens.get("id_token"):
            raise OIDCLoginError(
                "the provider returned no id_token, so the identity cannot be verified",
                error_code="oidc_no_id_token",
            )
        return tokens

    def verify_id_token(self, id_token: str, pending: PendingLogin) -> VerifiedIdentity:
        """Signature first, claims second — never the other way round."""
        header, claims, signing_input, signature = _split_jwt(id_token)
        if header.get("crit"):
            raise OIDCLoginError(
                "id_token has critical headers we cannot honour ('crit')",
                error_code="oidc_id_token_unsupported",
            )
        if header.get("enc"):
            raise OIDCLoginError(
                "id_token is encrypted; not supported",
                error_code="oidc_id_token_encrypted",
            )
        alg = str(header.get("alg") or "")
        if not alg:
            raise OIDCLoginError(
                "id_token has no 'alg' header; an unsigned token is never accepted",
                error_code="oidc_alg_unsupported",
            )
        if alg.lower() == "none" or alg not in supported_algorithms():
            raise OIDCLoginError(
                f"id_token algorithm '{alg}' is not accepted by this install "
                f"(supported: {', '.join(supported_algorithms())})",
                error_code="oidc_alg_unsupported",
            )

        try:
            jwk = _select_jwk(self.jwks(), header, alg)
        except _KeyNotFound:
            # Key rotation: refresh once, then fail.
            try:
                jwk = _select_jwk(self.jwks(force=True), header, alg)
            except _KeyNotFound as _err:
                raise OIDCLoginError(
                    "no key in the provider JWKS matches this id_token "
                    f"(kid={header.get('kid')!r}, alg={alg})",
                    error_code="oidc_key_not_found",
                ) from _err
        if not verify_signature(alg, jwk, signing_input, signature):
            raise OIDCLoginError(
                "id_token signature is invalid", error_code="oidc_bad_signature"
            )
        validate_claims(
            claims, settings=self.settings, nonce=pending.nonce, clock=self._clock
        )
        return identity_from_claims(claims)

    def complete_login(self, code: str, pending: PendingLogin) -> VerifiedIdentity:
        """Full callback path: exchange the code, verify the id_token.

        ``sub`` comes only from the verified id_token. The userinfo
        endpoint is optional cosmetics: if it fails, or is absent, the
        verified identity still stands.
        """
        discovery = self.discover()
        tokens = self.exchange_code(code, pending, discovery)
        identity = self.verify_id_token(str(tokens["id_token"]), pending)
        return self._enrich_display(identity, tokens, discovery)

    def _enrich_display(
        self, identity: VerifiedIdentity, tokens: dict[str, Any], discovery: Discovery
    ) -> VerifiedIdentity:
        if (
            (identity.display_name and identity.display_name != identity.sub)
            or not discovery.userinfo_endpoint
            or not tokens.get("access_token")
        ):
            return identity
        try:
            status, raw = self._transport(
                discovery.userinfo_endpoint,
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                timeout=USERINFO_TIMEOUT,
            )
            if status != 200:
                return identity
            info = _decode_json_body(raw, what="userinfo endpoint")
        except OIDCError as exc:
            _logger.warning("oidc: userinfo enrichment skipped (%s)", exc.detail)
            return identity
        if not isinstance(info, dict) or str(info.get("sub") or "") != identity.sub:
            # A userinfo body about a different subject is never merged.
            return identity
        display = info.get("preferred_username") or info.get("name")
        email = info.get("email")
        # Groups may live only on userinfo; only fill a gap the verified
        # id_token left, and never replace what it asserted.
        groups = identity.groups or _string_groups(info.get("groups"))
        if not display and not email and groups == identity.groups:
            return identity
        return VerifiedIdentity(
            sub=identity.sub,
            display_name=str(display) if display else identity.display_name,
            email=str(email) if email else identity.email,
            issuer=identity.issuer,
            auth_time=identity.auth_time,
            claim_names=identity.claim_names,
            groups=groups,
        )

    def end_session_url(self, post_logout_redirect_uri: str) -> str | None:
        """RP-initiated logout URL, when the provider advertises one.

        We deliberately do not retain the id_token, so no
        ``id_token_hint`` is sent: the provider may ask the person to
        confirm logout. That is the trade for never storing a
        credential we do not need.
        """
        try:
            discovery = self.discover()
        except OIDCError as exc:
            _logger.warning("oidc: logout discovery failed (%s)", exc.detail)
            return None
        if not discovery.end_session_endpoint:
            return None
        params = {
            "client_id": self.settings.client_id,
            "post_logout_redirect_uri": post_logout_redirect_uri,
        }
        return f"{discovery.end_session_endpoint}?{urllib.parse.urlencode(params)}"


def _provider_error_suffix(raw: bytes) -> str:
    """The provider's own error code, if it sent a readable one.

    Only ``error``/``error_description`` are extracted; the rest of a
    token-endpoint body is not repeated, because we cannot promise it
    holds nothing sensitive.
    """
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    parts = [str(data[k])[:160] for k in ("error", "error_description") if data.get(k)]
    return f": {', '.join(parts)}" if parts else ""


# --- service: config file + caches for one process ----------------------


class OIDCService:
    """Owns config loading and provider caches for one process.

    The setup wizard can write ``config/oidc.json`` after boot, so the
    file is re-read whenever it changes (mtime + size) instead of being
    frozen at startup. The flow-signing key survives a reload, so an
    in-flight login is not broken by an unrelated config edit.
    """

    def __init__(
        self,
        config_dir: Path | str,
        *,
        transport: Transport = default_transport,
        flow_key: bytes | None = None,
        discovery_ttl: float = DISCOVERY_TTL,
        jwks_ttl: float = JWKS_TTL,
        clock: Callable[[], float] = time.time,
    ):
        self.config_dir = Path(config_dir)
        self.path = self.config_dir / CONFIG_FILENAME
        self._transport = transport
        self._flow_key = flow_key or secrets.token_bytes(32)
        self._discovery_ttl = discovery_ttl
        self._jwks_ttl = jwks_ttl
        self._clock = clock
        self._stamp: tuple[int, int] | None = None
        self._settings: OIDCSettings | None = None
        self._client: OIDCClient | None = None
        self._load_error: OIDCError | None = None
        self._sync()

    # -- config ------------------------------------------------------------

    def _sync(self) -> None:
        try:
            info = self.path.stat()
            stamp: tuple[int, int] | None = (info.st_mtime_ns, info.st_size)
        except OSError:
            stamp = None
        if stamp == self._stamp:
            return
        self._stamp = stamp
        self._client = None
        try:
            self._settings = load_settings(self.config_dir)
            self._load_error = None
        except OIDCError as exc:
            self._settings = None
            self._load_error = exc

    def settings(self) -> OIDCSettings:
        """Current settings, or the reason there are none."""
        self._sync()
        if self._load_error is not None:
            raise self._load_error
        if self._settings is None:  # pragma: no cover - _sync sets one or error
            raise OIDCNotConfigured("no OIDC provider configured")
        return self._settings

    def client(self) -> OIDCClient:
        self._sync()
        settings = self.settings()
        if self._client is None or self._client.settings != settings:
            self._client = OIDCClient(
                settings,
                transport=self._transport,
                discovery_ttl=self._discovery_ttl,
                jwks_ttl=self._jwks_ttl,
                flow_codec=FlowCodec(key=self._flow_key, clock=self._clock),
                clock=self._clock,
            )
        return self._client

    def reload(self) -> None:
        """Force a config re-read (used after a setup-wizard write)."""
        self._stamp = (-1, -1)
        self._sync()

    # -- status -----------------------------------------------------

    def status(self) -> dict[str, Any]:
        """The state an owner or a setup wizard can act on.

        Four states, no optimistic blending:

        - ``not_configured`` — no ``config/oidc.json``; local auth is the
          whole story. Healthy, not an error.
        - ``configured`` — settings parse, the provider answered
          discovery, and this install can verify what it advertises.
        - ``unreachable`` — settings parse but the provider did not
          answer. Configuration may be fine; the network or the IdP is
          not.
        - ``misconfigured`` — settings are unusable, the discovery
          document contradicts them, or the provider requires something
          this install does not have (an unset client secret, an
          unverifiable signing algorithm).

        Contains no secret values. Discovery results are cached (both
        success and failure), so an unauthenticated caller cannot use
        this endpoint to make us hammer the IdP.
        """
        try:
            settings = self.settings()
        except OIDCError as exc:
            return {
                "ok": False,
                "status": exc.status,
                "warnings": [exc.detail],
                "data": {
                    "status": exc.status,
                    "login_available": False,
                    "detail": exc.detail,
                },
            }

        client = self.client()
        data: dict[str, Any] = {
            "status": CONFIGURED,
            "login_available": False,
            **settings.public_dict(),
        }
        warnings = list(settings.warnings)
        verification = signature_verification_state()
        data["signature_verification"] = verification
        if verification.get("reason"):
            warnings.append(verification["reason"])
        data["pkce"] = "S256"
        data["login_path"] = "/api/auth/oidc/login"
        data["callback_path"] = "/api/auth/oidc/callback"
        data["logout_path"] = "/api/auth/oidc/logout"

        def _degrade(exc: OIDCError) -> None:
            data["status"] = exc.status
            data["detail"] = exc.detail
            if exc.detail not in warnings:
                warnings.append(exc.detail)

        discovery: Discovery | None = None
        try:
            discovery = client.discover()
        except OIDCError as exc:
            _degrade(exc)
            discovery = client.cached_discovery()
            if discovery is not None:
                # about provenance: this metadata is what the
                # provider said earlier, not what it says now.
                data["discovery_stale"] = True
        data["discovery"] = discovery.public_dict() if discovery else None

        if discovery is not None:
            warnings.extend(w for w in discovery.warnings if w not in warnings)
            try:
                data["client_authentication"] = client.client_authentication(discovery)
            except OIDCError as exc:
                _degrade(exc)
            advertised = set(discovery.id_token_signing_alg_values_supported)
            if advertised and not advertised & set(supported_algorithms()):
                _degrade(
                    OIDCMisconfigured(
                        "the provider only advertises id_token signing "
                        "algorithms this install cannot verify "
                        f"({', '.join(sorted(advertised))}); sign-in would "
                        "fail closed"
                    )
                )

        data["login_available"] = data["status"] == CONFIGURED
        return {
            "ok": data["status"] == CONFIGURED,
            "status": data["status"],
            "warnings": warnings,
            "data": data,
        }
