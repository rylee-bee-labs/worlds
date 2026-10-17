"""Live-IdP (Authelia) integration harness — the other half of the OIDC proof.

``tests/test_oidc.py`` runs against an in-process stub provider: fast,
hermetic, CI-safe. This module drives a REAL OpenID provider — the
throwaway Authelia container from ``compose.authelia-test.yaml`` —
through the full discovery → authorize → callback → session round-trip,
using the production code paths (real HTTP transport, real JWKS, real
signature verification).

It is strictly opt-in and never touches the network in CI:

    PW_TEST_AUTHELIA=1 \
    PW_TEST_AUTHELIA_USER=testuser \
    PW_TEST_AUTHELIA_PASSWORD='…' \
    PW_TEST_AUTHELIA_CLIENT_SECRET='…' \
        uv run pytest tests/test_oidc_live.py -q

Without ``PW_TEST_AUTHELIA=1`` and the three credential variables, every
test here skips with an actionable reason. Full procedure (generating
the throwaway IdP config, bringing the container up, teardown):
``docs/oidc-live-test.md``.

Security: credentials come from the environment only. This file embeds
no secrets and no private topology — loopback defaults plus the
fictional RFC 6761 hosts ``pw.test`` / ``example.invalid`` only.

The module doubles as the config generator for the throwaway IdP::

    uv run python tests/test_oidc_live.py --write-authelia-config [DIR]
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import httpx
except ImportError:  # pragma: no cover - httpx ships with --extra test
    httpx = None

# --- what this harness targets -------------------------------------------

CLIENT_ID = "project-worlds"
CALLBACK_PATH = "/api/auth/oidc/callback"

DEFAULT_IDP_URL = "https://127.0.0.1:9091"
"""Loopback default for the throwaway container. Authelia >= 4.38
requires an https portal URL, and its session-cookie domain must be an
IP or a dotted hostname — so the harness serves a generated self-signed
TLS cert on the loopback IP. Override with ``PW_TEST_AUTHELIA_URL`` if
it is published elsewhere."""

BACKEND_BASE_URL = "https://pw.test"
"""The backend under test runs in-process (FastAPI TestClient); pw.test
is a fictional RFC 6761 host that never resolves. The IdP only ever
*redirects* there — the harness intercepts that redirect and replays it
against the in-process app, so no listening backend port is needed.
https keeps the Secure flow/session cookies alive inside TestClient."""

CALLBACK_URI = f"{BACKEND_BASE_URL}{CALLBACK_PATH}"

CLIENT_SECRET_ENV = "PW_TEST_AUTHELIA_CLIENT_SECRET"
_REQUIRED_ENV = (
    "PW_TEST_AUTHELIA_USER",
    "PW_TEST_AUTHELIA_PASSWORD",
    CLIENT_SECRET_ENV,
)

_DOC = "docs/oidc-live-test.md"

ENABLED = os.environ.get("PW_TEST_AUTHELIA") == "1"
_MISSING = [name for name in _REQUIRED_ENV if not os.environ.get(name)]

pytestmark = [
    pytest.mark.skipif(
        not ENABLED,
        reason=(
            "live-IdP harness is opt-in: set PW_TEST_AUTHELIA=1 against a "
            "running compose.authelia-test.yaml IdP and export "
            "PW_TEST_AUTHELIA_USER / _PASSWORD / _CLIENT_SECRET "
            f"(see {_DOC})"
        ),
    ),
    pytest.mark.skipif(
        httpx is None,
        reason="httpx is not installed; the live harness needs it "
        "(uv sync --extra test)",
    ),
    pytest.mark.timeout(120),
]

if ENABLED and _MISSING:
    pytest.skip(
        "PW_TEST_AUTHELIA=1 but these credential env vars are missing: "
        + ", ".join(_MISSING)
        + f". Secrets come from the environment only — export them per {_DOC}.",
        allow_module_level=True,
    )


def _idp_url() -> str:
    return os.environ.get("PW_TEST_AUTHELIA_URL", DEFAULT_IDP_URL).rstrip("/")


def _trust_generated_tls_cert() -> None:
    """Teach this process to trust the throwaway IdP's self-signed cert.

    Authelia >= 4.38 insists on an https portal URL, so the generator
    creates a self-signed certificate. Pointing ``SSL_CERT_FILE`` at it
    covers both HTTP stacks in play: urllib (the app's OIDC transport)
    via OpenSSL's default verify paths, and httpx (the IdP-driving leg),
    which honours ``SSL_CERT_FILE`` when ``trust_env`` is on. Applied
    only when the generated cert exists and the operator has not pinned
    their own trust anchor.
    """
    cert = (
        Path(__file__).resolve().parent.parent
        / "build"
        / "authelia-test"
        / "config"
        / "tls.crt"
    )
    if (
        _idp_url().startswith("https://")
        and cert.is_file()
        and not os.environ.get("SSL_CERT_FILE")
    ):
        os.environ["SSL_CERT_FILE"] = str(cert)


if ENABLED:
    _trust_generated_tls_cert()


# --- fixtures --------------------------------------------------------------


@pytest.fixture(scope="module")
def discovery() -> dict:
    """The provider's real discovery document, fetched over the network.

    ``PW_TEST_AUTHELIA=1`` is an explicit opt-in, so an unreachable IdP
    is a failure with an actionable message — never a silent skip.
    """
    url = f"{_idp_url()}/.well-known/openid-configuration"
    try:
        response = httpx.get(url, timeout=10.0)
    except httpx.HTTPError as exc:
        pytest.fail(
            f"cannot reach the live IdP at {url} ({type(exc).__name__}: {exc}). "
            "Is the throwaway container up? "
            f"docker compose -f compose.authelia-test.yaml up -d --wait (see {_DOC})"
        )
    assert response.status_code == 200, (
        f"discovery at {url} returned HTTP {response.status_code}"
    )
    doc = response.json()
    published = str(doc.get("issuer") or "").rstrip("/")
    assert published == _idp_url(), (
        f"discovery issuer {published!r} does not match PW_TEST_AUTHELIA_URL "
        f"{_idp_url()!r} — regenerate the IdP config or fix the URL ({_DOC})"
    )
    return doc


@pytest.fixture()
def backend(tmp_path, monkeypatch):
    """The real app, in-process, wired to the live IdP.

    Same shape as the stub tests in ``test_oidc.py``, with one crucial
    difference: ``OIDCService`` keeps the default transport, so
    discovery, token exchange and JWKS fetches are real network calls.
    """
    from fastapi.testclient import TestClient

    from personal_world.api import create_app
    from personal_world.oidc import OIDCService

    (tmp_path / "oidc.json").write_text(
        json.dumps(
            {
                "issuer": _idp_url(),
                "client_id": CLIENT_ID,
                "client_secret_env": CLIENT_SECRET_ENV,
                "scopes": ["openid", "profile", "email"],
                "display_name": "Authelia (live test)",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("PW_API_TOKEN", "tok-live")
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    app = create_app(tmp_path, tmp_path)
    app.state.oidc = OIDCService(tmp_path)
    return TestClient(app, base_url=BACKEND_BASE_URL)


# --- driving the real IdP headlessly ----------------------------------------

_REDIRECTS = (301, 302, 303, 307, 308)


def _follow_idp_redirects(idp, url: str) -> str | None:
    """Follow IdP-side redirects until the flow either lands on a page
    (the portal → ``None``) or redirects to the registered callback
    (→ that absolute URL). Bounded: a redirect loop is a bug, not a test.

    The callback host (pw.test) never resolves by design, so httpx must
    never be allowed to follow that hop — it is the handoff point back
    to the in-process backend.
    """
    for _ in range(6):
        response = idp.get(url, follow_redirects=False)
        if response.status_code not in _REDIRECTS:
            return None
        location = response.headers.get("location", "")
        if location.startswith(CALLBACK_URI):
            return location
        url = urllib.parse.urljoin(url, location)
    return None


def _sign_in_at_idp(authorize_url: str) -> str:
    """Complete a real login at the live IdP; return the callback URL.

    Drives Authelia's portal over plain HTTP (its first-factor API), no
    browser needed. If the IdP does not expose that API (a future
    Authelia, or a different provider), the interactive leg skips with
    an honest reason instead of failing: the non-interactive tests still
    prove discovery, JWKS, status and the login redirect live.
    """
    with httpx.Client(timeout=15.0) as idp:
        already = _follow_idp_redirects(idp, authorize_url)
        if already:
            return already  # an IdP session was still alive; fine for a test
        login = idp.post(
            f"{_idp_url()}/api/firstfactor",
            json={
                "username": os.environ["PW_TEST_AUTHELIA_USER"],
                "password": os.environ["PW_TEST_AUTHELIA_PASSWORD"],
                "keepMeLoggedIn": False,
            },
        )
        if login.status_code in (404, 405):
            pytest.skip(
                "the live IdP does not expose POST /api/firstfactor for "
                f"headless sign-in (HTTP {login.status_code}); the interactive "
                "leg would need a browser-driven login this environment does "
                "not have. The discovery/JWKS/status/login-redirect legs "
                "still ran."
            )
        try:
            accepted = login.status_code == 200 and login.json().get("status") == "OK"
        except ValueError:
            accepted = False
        if not accepted:
            # Never echo the password; Authelia's own message is safe.
            pytest.fail(
                "IdP first-factor sign-in failed "
                f"(HTTP {login.status_code}: {login.text[:200]}). Check that "
                "PW_TEST_AUTHELIA_USER / PW_TEST_AUTHELIA_PASSWORD match the "
                f"generated users database ({_DOC})."
            )
        callback_url = _follow_idp_redirects(idp, authorize_url)
        assert callback_url, (
            "after a successful sign-in the IdP did not redirect to the "
            f"registered callback ({CALLBACK_URI}) within the portal flow"
        )
        return callback_url


def _signed_in_session(backend) -> str:
    """Full round-trip: login redirect → IdP sign-in → callback → session.

    Returns the ``pw_session`` id. This is the leg the stub tests can
    only simulate: a real authorization code from a real IdP, exchanged
    over the network, with the id_token signature verified against the
    provider's live JWKS.
    """
    secret = os.environ[CLIENT_SECRET_ENV]
    response = backend.get("/api/auth/oidc/login", follow_redirects=False)
    assert response.status_code == 303, response.text
    authorize_url = response.headers["location"]

    callback_url = _sign_in_at_idp(authorize_url)
    # The front channel carries an authorization code — never a token,
    # never the client secret.
    query = urllib.parse.urlparse(callback_url).query
    assert "code=" in query, f"callback carries no authorization code: {query!r}"
    assert "id_token" not in query and "access_token" not in query
    assert secret not in callback_url

    params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
    response = backend.get(CALLBACK_PATH, params=params, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/"
    set_cookie = response.headers.get("set-cookie", "")
    assert "pw_session=" in set_cookie
    assert secret not in response.text
    return set_cookie.split("pw_session=")[1].split(";")[0]


# --- live provider surface --------------------------------------------------


class TestLiveProviderSurface:
    def test_discovery_document_is_live_and_consistent(self, discovery):
        for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            value = str(discovery.get(key) or "")
            assert value.startswith(_idp_url()), (
                f"discovery '{key}' ({value!r}) is not served by the IdP base URL"
            )

    def test_provider_advertises_s256_pkce(self, discovery):
        methods = discovery.get("code_challenge_methods_supported") or []
        assert "S256" in methods, (
            f"the live IdP must advertise S256 PKCE (advertised: {methods})"
        )

    def test_jwks_is_live_and_this_install_can_verify_it(self, discovery):
        from personal_world.oidc import supported_algorithms

        response = httpx.get(discovery["jwks_uri"], timeout=10.0)
        assert response.status_code == 200
        keys = response.json().get("keys") or []
        assert keys, "the live JWKS published no keys"
        for key in keys:
            assert key.get("kty") in ("RSA", "EC", "OKP"), key.get("kty")
            assert key.get("use", "sig") == "sig"
            assert key.get("kid"), "every signing key needs a kid for selection"
        advertised = discovery.get("id_token_signing_alg_values_supported") or []
        assert set(advertised) & set(supported_algorithms()), (
            f"the IdP advertises {advertised} but this install can verify "
            f"only {list(supported_algorithms())} — uv sync --extra crypto"
        )


# --- backend wiring against the live provider -------------------------------


class TestLiveBackendWiring:
    def test_status_reports_configured_from_real_discovery(self, backend, discovery):
        secret = os.environ[CLIENT_SECRET_ENV]
        response = backend.get("/api/auth/oidc/status")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True, body
        assert body["status"] == "configured", body.get("data", {}).get("detail")
        data = body["data"]
        assert data["login_available"] is True
        assert data["client_secret_env"] == CLIENT_SECRET_ENV
        assert data["client_secret_present"] is True
        assert data["discovery"]["token_endpoint"] == discovery["token_endpoint"]
        # The status endpoint reports the secret's NAME and presence,
        # never its value.
        assert secret not in response.text

    def test_login_redirects_to_the_live_authorize_endpoint(self, backend, discovery):
        secret = os.environ[CLIENT_SECRET_ENV]
        response = backend.get("/api/auth/oidc/login", follow_redirects=False)
        assert response.status_code == 303, response.text
        location = response.headers["location"]
        base, _, query = location.partition("?")
        assert base == discovery["authorization_endpoint"]
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        assert params["response_type"] == "code"
        assert params["client_id"] == CLIENT_ID
        assert params["redirect_uri"] == CALLBACK_URI
        assert params["code_challenge_method"] == "S256"
        assert len(params["code_challenge"]) >= 43
        assert params["state"] and params["nonce"]
        # No credential ever travels through the front channel.
        assert secret not in location
        assert "client_secret" not in params


# --- the real round-trip ----------------------------------------------------


class TestLiveRoundTrip:
    def test_authorize_callback_session_round_trip(self, backend, discovery):
        session_id = _signed_in_session(backend)
        body = backend.get(
            "/api/auth/session", headers={"Cookie": f"pw_session={session_id}"}
        ).json()
        assert body["ok"] is True, body
        assert body["data"]["auth_method"] == "oidc"
        # single mode: a verified external identity signs in as the owner
        assert body["data"]["principal_id"] == "primary"

    def test_logout_ends_the_local_session(self, backend, discovery):
        session_id = _signed_in_session(backend)
        response = backend.get(
            "/api/auth/oidc/logout",
            headers={"Cookie": f"pw_session={session_id}"},
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
        location = response.headers["location"]
        # Either the provider's end-session endpoint (RP-initiated
        # logout) or the local login page — both are honest logouts. The
        # local page is absolute (built from the request base URL), so
        # accept both the relative and the absolute form.
        local_login = f"{BACKEND_BASE_URL}/login"
        assert (
            location.startswith(_idp_url())
            or location.startswith("/login")
            or location == local_login
        ), location
        dead = backend.get(
            "/api/auth/session", headers={"Cookie": f"pw_session={session_id}"}
        ).json()
        assert dead["ok"] is False


# --- throwaway-IdP config generator -----------------------------------------
#
# ``python tests/test_oidc_live.py --write-authelia-config [DIR]`` writes the
# Authelia configuration that compose.authelia-test.yaml mounts (default:
# ``build/authelia-test/config`` — already excluded by .gitignore, as is
# ``*.pem``), including a throwaway self-signed TLS pair (Authelia >= 4.38
# requires an https portal URL). Secrets enter ONLY from the environment:
#
# - The OIDC client secret is never written anywhere: the generated
#   configuration.yml renders it with Authelia's config templating
#   (`{{ mustEnv "PW_TEST_AUTHELIA_CLIENT_SECRET" }}`, enabled by
#   X_AUTHELIA_CONFIG_FILTERS=template), reading it from the container
#   environment the compose file passes through.
# - Authelia-internal secrets (session/storage/JWT) are random per
#   generation unless pinned via env.
# - The throwaway login password lands in the users database as an
#   argon2id digest hashed by the Authelia image itself (4.38 dropped
#   plaintext passwords; docker is already a prerequisite). The file is
#   untracked, gitignored, 0600, sourced from the environment, never
#   echoed, destroyed at teardown.

_CONFIG_HEADER = """\
# GENERATED throwaway Authelia config for the Project Worlds live OIDC
# harness. Untracked and gitignored; regenerate freely:
#   uv run python tests/test_oidc_live.py --write-authelia-config
# Procedure and env vars: docs/oidc-live-test.md
"""

_CONFIGURATION = """\
theme: light

server:
  address: 'tcp://0.0.0.0:9091'
  tls:
    certificate: /config/tls.crt
    key: /config/tls.key

log:
  level: 'info'

identity_validation:
  reset_password:
    jwt_secret: '{jwt_secret}'

authentication_backend:
  password_reset:
    disable: true
  file:
    path: /config/users_database.yml

access_control:
  default_policy: one_factor

session:
  secret: '{session_secret}'
  cookies:
    - domain: '{cookie_domain}'
      authelia_url: '{authelia_url}'

storage:
  encryption_key: '{storage_key}'
  local:
    path: /config/authelia.db

notifier:
  filesystem:
    filename: /config/notifications.txt

identity_providers:
  oidc:
    jwks:
      - algorithm: 'RS256'
        key: |
{issuer_key_block}
    clients:
      - client_id: '{client_id}'
        client_name: 'Project Worlds (live test)'
        client_secret: '$plaintext${{{{ mustEnv "{client_secret_env}" }}}}'
        redirect_uris:
          - '{callback_uri}'
        scopes: ['openid', 'profile', 'email', 'groups']
        grant_types: ['authorization_code']
        response_types: ['code']
        token_endpoint_auth_method: 'client_secret_post'
        authorization_policy: 'one_factor'
        consent_mode: 'implicit'
        require_pkce: true
        pkce_challenge_method: 'S256'
"""

_USERS_DATABASE = """\
users:
  {username}:
    displayname: 'Live Test User'
    email: '{username}@example.invalid'
    password: '{password_digest}'
    groups: []
"""

AUTH_IMAGE = "authelia/authelia:4.38"
"""Pinned in lockstep with compose.authelia-test.yaml."""


def _require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        sys.exit(
            f"{name} must be set before generating the throwaway IdP config; "
            f"secrets come from the environment only (see {_DOC})"
        )
    return value


def _run_openssl(args: list[str], failure: str) -> None:
    try:
        subprocess.run(["openssl", *args], check=True, capture_output=True)
    except FileNotFoundError:
        sys.exit(f"openssl is required to generate throwaway keys ({failure})")
    except subprocess.CalledProcessError as exc:
        sys.exit(
            f"openssl could not {failure}: " + exc.stderr.decode(errors="replace")[:200]
        )


def _write_issuer_key(path: Path) -> None:
    """A throwaway RSA key, generated locally, never printed.

    Authelia 4.38+ requires an explicit OIDC issuer key; RS256 is its
    default id_token algorithm and verifies with the Python standard
    library alone, so the harness works on a minimal install.
    """
    if path.exists():
        return
    _run_openssl(
        [
            "genpkey",
            "-algorithm",
            "RSA",
            "-pkeyopt",
            "rsa_keygen_bits:2048",
            "-out",
            str(path),
        ],
        "generate the OIDC issuer key",
    )
    path.chmod(0o600)


def _issuer_key_block(dest: Path) -> str:
    """The throwaway issuer key as an indented YAML block scalar.

    Authelia 4.38 parses ``jwks[].key`` as inline PEM content (not a
    file path), so the generated configuration carries the throwaway
    key directly. Same posture as the users database: an untracked,
    gitignored file holding only throwaway material, destroyed at
    teardown.
    """
    path = dest / "oidc_issuer_key.pem"
    _write_issuer_key(path)
    pem = path.read_text(encoding="ascii").strip()
    return "\n".join(" " * 10 + line for line in pem.splitlines())


def _write_tls_pair(dest: Path) -> None:
    """A throwaway self-signed TLS cert/key for the IdP portal.

    Authelia >= 4.38 refuses a non-https ``authelia_url``, so even the
    loopback test IdP serves TLS. The cert covers the loopback IP and
    ``localhost``; the test module trusts it via ``SSL_CERT_FILE``.
    """
    crt, key = dest / "tls.crt", dest / "tls.key"
    if crt.exists() and key.exists():
        return
    _run_openssl(
        [
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(crt),
            "-days",
            "2",
            "-subj",
            "/CN=pw-authelia-test",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1",
        ],
        "generate the self-signed TLS pair",
    )
    crt.chmod(0o600)
    key.chmod(0o600)


def _password_digest(password: str) -> str:
    """Hash the throwaway user password with the IdP's own CLI.

    Authelia 4.38 dropped plaintext passwords from its file backend, so
    the users database needs a real argon2id digest. Generating it with
    the Authelia image itself guarantees the exact format the IdP
    parses, and adds no Python crypto dependency. The password is
    throwaway — valid only inside the container that teardown destroys;
    it travels via argv of this one local command and is never echoed.
    """
    try:
        proc = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint",
                "authelia",
                AUTH_IMAGE,
                "crypto",
                "hash",
                "generate",
                "argon2",
                "--password",
                password,
                "--no-confirm",
            ],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError:
        sys.exit(f"docker is required to hash the throwaway user password (see {_DOC})")
    except subprocess.CalledProcessError as exc:
        sys.exit(
            "authelia could not hash the throwaway password: "
            + exc.stderr.decode(errors="replace")[:200]
        )
    for line in proc.stdout.decode().splitlines():
        if "Digest:" in line:
            return line.split("Digest:", 1)[1].strip()
    sys.exit(f"unexpected authelia hash output: {proc.stdout[:120]!r}")


def write_authelia_config(dest: Path) -> None:
    authelia_url = os.environ.get("PW_TEST_AUTHELIA_URL", DEFAULT_IDP_URL).rstrip("/")
    host = urllib.parse.urlparse(authelia_url).hostname or "localhost"
    username = _require_env("PW_TEST_AUTHELIA_USER")
    password = _require_env("PW_TEST_AUTHELIA_PASSWORD")
    _require_env(CLIENT_SECRET_ENV)  # consumed by Authelia via env, not written

    dest.mkdir(parents=True, exist_ok=True)
    _write_tls_pair(dest)
    (dest / "configuration.yml").write_text(
        _CONFIG_HEADER
        + _CONFIGURATION.format(
            jwt_secret=os.environ.get("PW_TEST_AUTHELIA_JWT_SECRET")
            or secrets.token_urlsafe(32),
            session_secret=os.environ.get("PW_TEST_AUTHELIA_SESSION_SECRET")
            or secrets.token_urlsafe(32),
            storage_key=os.environ.get("PW_TEST_AUTHELIA_STORAGE_KEY")
            or secrets.token_urlsafe(32),
            cookie_domain=host,
            authelia_url=authelia_url,
            client_id=CLIENT_ID,
            client_secret_env=CLIENT_SECRET_ENV,
            callback_uri=CALLBACK_URI,
            issuer_key_block=_issuer_key_block(dest),
        ),
        encoding="utf-8",
    )
    users = dest / "users_database.yml"
    users.write_text(
        _USERS_DATABASE.format(
            username=username, password_digest=_password_digest(password)
        ),
        encoding="utf-8",
    )
    users.chmod(0o600)
    print(
        f"wrote throwaway Authelia config to {dest} "
        "(untracked; secrets sourced from the environment only)"
    )


def _main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "--write-authelia-config":
        default = (
            Path(__file__).resolve().parent.parent
            / "build"
            / "authelia-test"
            / "config"
        )
        write_authelia_config(Path(argv[2]) if len(argv) > 2 else default)
        return 0
    print("usage: python tests/test_oidc_live.py --write-authelia-config [DIR]")
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
