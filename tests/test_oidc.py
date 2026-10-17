"""OIDC relying-party tests: discovery, PKCE, id_token verification,
honest status, and the guarantee that local auth is untouched when OIDC
is absent.

The provider is a stub: no test reaches the network. Signatures are
produced with a synthetic, test-only RSA key (below) using nothing but
the standard library, so the security-critical path is exercised in CI,
which installs ``--extra test`` and not ``--extra crypto``. Where
``cryptography`` is available, extra tests cross-check the stdlib
verifier against it and cover an EC key.
"""

import base64
import hashlib
import json
import sys
import time
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world import oidc as oidc_module  # noqa: E402
from personal_world.oidc import (  # noqa: E402
    FlowCodec,
    OIDCClient,
    OIDCLoginError,
    OIDCMisconfigured,
    OIDCNotConfigured,
    OIDCService,
    OIDCUnreachable,
    PendingLogin,
    _verify_rsa_pkcs1_stdlib,
    code_challenge,
    load_settings,
    settings_from_dict,
    verify_signature,
)

_HAS_CRYPTO = oidc_module._HAS_CRYPTO

ISSUER = "https://auth.example.com"
CLIENT_ID = "project-worlds"
SECRET_ENV = "PW_TEST_OIDC_SECRET"
SECRET_VALUE = "synthetic-secret-value"

CONFIG = {
    "issuer": ISSUER,
    "client_id": CLIENT_ID,
    "client_secret_env": SECRET_ENV,
    "scopes": ["openid", "profile", "email"],
    "display_name": "Home SSO",
}

# ---------------------------------------------------------------------------
# Synthetic test-only RSA key. It guards nothing, signs nothing real, and must
# never be used outside this file. Base64url big-endian integers.
# ---------------------------------------------------------------------------
TEST_N = (  # pw-safety: synthetic
    "xMv-1SEWWWK14vVL6C5RE2kZCeuA5ELER3idW6DEcssphUp_rsZ8zU-KuE0iqbgP"
    "qdVSzmsPPRK5JO4AJAFq2J3X6a0GAgi-zkeyO54AoXl6ovoDU2hxmsOeuLagSPmt"
    "bIInDZXYQC_uNLKYBDeuZbdo7uN-mKfnn74vxTz650FV95PmlHKfPznRPU6fqrZq"
    "7UXh_Y7GAhoK7nVcndYlU9ymqrXknb-Xy4x_OtyNU_ucckmGdxko3G4FI0WyuGO3"
    "Pm9RP4NJngNgPmhInntx1imsLc9yeHUC8kjfT6vzsbkmrR1D6tXRSPiUos1kntAT"
    "vKx6U1qr4oBdWtxLC2YCzw"
)
TEST_E = "AQAB"  # pw-safety: synthetic
TEST_D = (  # pw-safety: synthetic
    "HGPrfva3gSym3beSfEvWQW0bgh1Z6lQhecgSN2pBfOgHNOXy9pVG4t2TPxRNqFtX"
    "0yHlwMacG6zsTcIR_h_AOMDIqbrez4NQd3TLZyNbpu_d-84CldFO9ks7Rh1-kRiH"
    "5sv9801HNbdUb4DGQnF_9MeZWUEzfbVXSmnG_XbXIW4_1iKIdWE28QYv9FyYslKMI"
    "eWqEm4uDHd8Oy5dRe94NY1ZbFY4vqb_lOFiRkKwvkoZntExHZPHTvrCCMHFnSir0v"
    "CSbEDtoyR1Q-_k9QNnGhQSjHymLJ70vl5NCd3B7edATRUjuWtqlFRTj16epLvwyY"
    "bEH-IvRAolG7T-KwWAzQ"
)
TEST_KID = "pw-test-key"


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _b64u_int(segment: str) -> int:
    return int.from_bytes(_b64u_decode(segment), "big")


_RSA_N = _b64u_int(TEST_N)
_RSA_E = _b64u_int(TEST_E)
_RSA_D = _b64u_int(TEST_D)

_PKCS1_PREFIX = {
    "RS256": bytes.fromhex("3031300d060960864801650304020105000420"),
    "RS384": bytes.fromhex("3041300d060960864801650304020205000430"),
    "RS512": bytes.fromhex("3051300d060960864801650304020305000440"),
}
_HASH = {"RS256": hashlib.sha256, "RS384": hashlib.sha384, "RS512": hashlib.sha512}


def jwks(*, kid: str = TEST_KID) -> dict:
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": kid,
                "n": TEST_N,
                "e": TEST_E,
            }
        ]
    }


def sign_jwt(
    claims: dict, *, alg: str = "RS256", kid: str = TEST_KID, header: dict | None = None
) -> str:
    """Sign a JWT with the synthetic key, standard library only."""
    head = header if header is not None else {"alg": alg, "typ": "JWT", "kid": kid}
    signing_input = (
        _b64u(json.dumps(head, separators=(",", ":")).encode())
        + "."
        + _b64u(json.dumps(claims, separators=(",", ":")).encode())
    ).encode("ascii")
    if alg == "none":
        return signing_input.decode() + "."
    digest = _HASH[alg](signing_input).digest()
    prefix = _PKCS1_PREFIX[alg]
    k = (_RSA_N.bit_length() + 7) // 8
    padded = (
        b"\x00\x01"
        + b"\xff" * (k - 3 - len(prefix) - len(digest))
        + b"\x00"
        + prefix
        + digest
    )
    signature = pow(int.from_bytes(padded, "big"), _RSA_D, _RSA_N).to_bytes(k, "big")
    return signing_input.decode() + "." + _b64u(signature)


def id_token_claims(**overrides) -> dict:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "sub": "authelia-sub-1",
        "exp": now + 600,
        "iat": now,
        "auth_time": now,
        "nonce": "test-nonce",
        "preferred_username": "sam",
        "email": "sam@example.invalid",
    }
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


# --- stub provider ------------------------------------------------------


class StubIdP:
    """A minimal in-memory OIDC provider with a recording transport."""

    def __init__(
        self,
        *,
        issuer: str = ISSUER,
        discovery: dict | None = None,
        jwks_payload: dict | None = None,
        token_status: int = 200,
        token_body: dict | None = None,
        token_signer=None,
        userinfo=None,
        userinfo_status: int = 200,
        discovery_status: int = 200,
        jwks_status: int = 200,
    ):
        self.issuer = issuer.rstrip("/")
        self.discovery_status = discovery_status
        self.jwks_status = jwks_status
        self.token_status = token_status
        self.token_body = token_body
        self.token_signer = token_signer or sign_jwt
        self.userinfo = userinfo
        self.userinfo_status = userinfo_status
        self.calls: list[str] = []
        self.token_requests: list[dict] = []
        self.token_headers: list[dict] = []
        self._discovery = (
            discovery
            if discovery is not None
            else {
                "issuer": self.issuer,
                "authorization_endpoint": f"{self.issuer}/api/oidc/authorization",
                "token_endpoint": f"{self.issuer}/api/oidc/token",
                "userinfo_endpoint": f"{self.issuer}/api/oidc/userinfo",
                "jwks_uri": f"{self.issuer}/jwks",
                "end_session_endpoint": f"{self.issuer}/logout",
                "scopes_supported": ["openid", "profile", "email", "groups"],
                "response_types_supported": ["code"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": [
                    "client_secret_post",
                    "client_secret_basic",
                    "none",
                ],
                "id_token_signing_alg_values_supported": ["RS256"],
            }
        )
        self._jwks = jwks_payload if jwks_payload is not None else jwks()
        # Filled in per login attempt by _start_login / the unit tests.
        self.nonce = "test-nonce"
        self.expected_challenge = None
        self.sub = "authelia-sub-1"
        self.claims_override: dict = {}
        self.pkce_verified = None

    def __call__(
        self,
        url: str,
        *,
        data: bytes | None = None,
        headers: dict | None = None,
        timeout: float = 10.0,
    ) -> tuple[int, bytes]:
        self.calls.append(url)
        if url == f"{self.issuer}/.well-known/openid-configuration":
            return self.discovery_status, json.dumps(self._discovery).encode()
        if url == self._discovery.get("jwks_uri"):
            return self.jwks_status, json.dumps(self._jwks).encode()
        if url == self._discovery.get("token_endpoint"):
            form = {
                k: v[0]
                for k, v in urllib.parse.parse_qs((data or b"").decode()).items()
            }
            self.token_requests.append(form)
            self.token_headers.append(dict(headers or {}))
            if self.expected_challenge is not None:
                verifier = form.get("code_verifier", "")
                self.pkce_verified = (
                    code_challenge(verifier) == self.expected_challenge
                    if verifier
                    else False
                )
            if self.token_status != 200 or self.token_body is not None:
                body = self.token_body if self.token_body is not None else {}
                return self.token_status, json.dumps(body).encode()
            token = self.token_signer(
                id_token_claims(nonce=self.nonce, sub=self.sub, **self.claims_override)
            )
            return 200, json.dumps(
                {
                    "access_token": "at-synthetic",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "id_token": token,
                    "scope": "openid profile email",
                }
            ).encode()
        if url == self._discovery.get("userinfo_endpoint"):
            if self.userinfo is None:
                return 404, b"{}"
            return self.userinfo_status, json.dumps(self.userinfo).encode()
        raise OIDCUnreachable(f"stub IdP has no route for {url}")


class DeadTransport:
    """Every call fails the way a dead network does."""

    def __init__(self, exc: Exception | None = None):
        self.calls: list[str] = []
        self.exc = exc

    def __call__(self, url, **kwargs):
        self.calls.append(url)
        raise self.exc or OIDCUnreachable(f"could not reach {url}: DNS failure")


# --- app helpers --------------------------------------------------------


def _app_client(
    tmp_path,
    monkeypatch,
    *,
    mode="single",
    token="tok-1",
    oidc_config=None,
    transport=None,
    base_url="https://pw.test",
):
    from personal_world.api import create_app

    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("PW_API_TOKEN", token)
    monkeypatch.setenv("PW_IDENTITY_MODE", mode)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    if oidc_config is not None:
        (tmp_path / "oidc.json").write_text(json.dumps(oidc_config))
    app = create_app(tmp_path, tmp_path)
    if oidc_config is not None:
        # The same seam the routes resolve, with the network stubbed out.
        app.state.oidc = OIDCService(tmp_path, transport=transport)
    return TestClient(app, base_url=base_url)


def _with_secret(monkeypatch, value: str = SECRET_VALUE) -> str:
    monkeypatch.setenv(SECRET_ENV, value)
    return value


def _start_login(client, stub):
    """Run the redirect half of the flow and return the authorize params.

    Never follows the redirect: the target is an external IdP.
    """
    r = client.get("/api/auth/oidc/login", follow_redirects=False)
    assert r.status_code == 303, r.text
    location = r.headers["location"]
    base, _, query = location.partition("?")
    params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
    assert base == stub._discovery["authorization_endpoint"]
    stub.nonce = params["nonce"]
    stub.expected_challenge = params["code_challenge"]
    return params


def _callback(client, params, *, code="auth-code-1", state=None, accept=""):
    query = {"code": code, "state": state if state is not None else params["state"]}
    headers = {"Accept": accept} if accept else {}
    return client.get(
        "/api/auth/oidc/callback", params=query, headers=headers, follow_redirects=False
    )


def _error_code(response) -> str:
    location = response.headers.get("location", "")
    query = urllib.parse.urlparse(location).query
    return dict(urllib.parse.parse_qsl(query)).get("pw_auth_error", "")


def _session_id(response) -> str:
    return response.headers["set-cookie"].split("pw_session=")[1].split(";")[0]


def _assert_session_dead(client, sid):
    """After logout the session id no longer resolves.

    The endpoint answers ``expired`` — a cookie was presented for a
    session that is gone — rather than ``unauthenticated``, which means
    no cookie at all. Both are honest "you are not signed in" states;
    this asserts the one a browser holding a stale cookie actually sees.
    """
    body = client.get(
        "/api/auth/session", headers={"Cookie": f"pw_session={sid}"}
    ).json()
    assert body["ok"] is False
    assert body["status"] == "expired"


def _pending(nonce="test-nonce") -> PendingLogin:
    return PendingLogin(
        "state-1",
        "verifier-1",
        nonce,
        "https://pw.test/api/auth/oidc/callback",
        time.time(),
    )


# ===========================================================================
# Configuration
# ===========================================================================


class TestConfig:
    def test_missing_file_is_not_configured(self, tmp_path):
        with pytest.raises(OIDCNotConfigured):
            load_settings(tmp_path)
        status = OIDCService(tmp_path).status()
        assert status["status"] == "not_configured"
        assert status["ok"] is False
        assert status["data"]["login_available"] is False

    def test_valid_file_parses(self, tmp_path):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        settings = load_settings(tmp_path)
        assert settings.issuer == ISSUER
        assert settings.client_id == CLIENT_ID
        assert settings.scopes == ("openid", "profile", "email")
        assert settings.display_name == "Home SSO"

    def test_documentation_keys_are_tolerated(self, tmp_path):
        """An annotated example must still load, never silently disable
        SSO because of a comment key."""
        annotated = dict(CONFIG)
        annotated["_comment"] = "issuer: your provider base URL"
        annotated["future_field"] = "ignored"
        (tmp_path / "oidc.json").write_text(json.dumps(annotated))
        settings = load_settings(tmp_path)
        assert settings.issuer == ISSUER
        assert any("future_field" in w for w in settings.warnings)
        assert not any("_comment" in w for w in settings.warnings)

    @pytest.mark.parametrize(
        "broken,reason",
        [
            ({}, "issuer"),
            ({"issuer": "auth.example.com", "client_id": CLIENT_ID}, "absolute http"),
            ({"issuer": ISSUER}, "client_id"),
            (
                {"issuer": ISSUER, "client_id": CLIENT_ID, "scopes": ["profile"]},
                "openid",
            ),
        ],
    )
    def test_invalid_config_is_misconfigured(self, tmp_path, broken, reason):
        (tmp_path / "oidc.json").write_text(json.dumps(broken))
        with pytest.raises(OIDCMisconfigured) as exc:
            load_settings(tmp_path)
        assert reason in exc.value.detail
        status = OIDCService(tmp_path).status()
        assert status["status"] == "misconfigured"
        assert status["ok"] is False

    def test_malformed_json_is_honest_not_silent(self, tmp_path):
        (tmp_path / "oidc.json").write_text("{ not json")
        with pytest.raises(OIDCMisconfigured):
            load_settings(tmp_path)
        assert OIDCService(tmp_path).status()["status"] == "misconfigured"

    def test_config_appearing_after_boot_is_picked_up(self, tmp_path):
        """The setup wizard writes oidc.json at runtime, after boot."""
        service = OIDCService(tmp_path, transport=StubIdP())
        assert service.status()["status"] == "not_configured"
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        assert service.settings().client_id == CLIENT_ID

    def test_config_removed_after_boot_is_picked_up(self, tmp_path):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        service = OIDCService(tmp_path, transport=StubIdP())
        assert service.settings().client_id == CLIENT_ID
        (tmp_path / "oidc.json").unlink()
        service.reload()
        assert service.status()["status"] == "not_configured"


class TestSecretHandling:
    def test_secret_comes_only_from_the_named_env_var(self, monkeypatch):
        settings = settings_from_dict(CONFIG)
        assert settings.client_secret == ""
        assert settings.client_secret_present is False
        monkeypatch.setenv(SECRET_ENV, SECRET_VALUE)
        assert settings.client_secret == SECRET_VALUE
        assert settings.client_secret_present is True

    def test_secret_in_the_config_file_is_ignored_not_adopted(self):
        settings = settings_from_dict({**CONFIG, "client_secret": "leaked"})
        assert "leaked" not in json.dumps(settings.public_dict())
        assert any("client_secret" in w for w in settings.warnings)

    def test_status_payload_carries_no_secret(self, tmp_path, monkeypatch):
        secret = _with_secret(monkeypatch, "a-much-longer-synthetic-secret")
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        status = OIDCService(tmp_path, transport=StubIdP()).status()
        assert status["data"]["client_secret_present"] is True
        assert status["data"]["client_secret_env"] == SECRET_ENV
        assert secret not in json.dumps(status)

    def test_provider_error_never_echoes_the_secret(self, tmp_path, monkeypatch):
        secret = _with_secret(monkeypatch, "a-much-longer-synthetic-secret")
        stub = StubIdP(
            token_status=400,
            token_body={
                "error": "invalid_client",
                "error_description": "unknown client",
            },
        )
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        client = OIDCClient(load_settings(tmp_path), transport=stub)
        with pytest.raises(OIDCLoginError) as exc:
            client.exchange_code("code", _pending(), client.discover())
        # the provider's own error code is surfaced for the operator ...
        assert "invalid_client" in exc.value.detail
        # ... and the secret is not repeated back to a human or a log
        assert secret not in exc.value.detail
        # the secret does go to the provider (that is its only job)
        assert stub.token_requests[0]["client_secret"] == secret


# ===========================================================================
# Discovery and status
# ===========================================================================


class TestDiscovery:
    def test_discovery_uses_provider_metadata(self, tmp_path):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        stub = StubIdP()
        client = OIDCClient(load_settings(tmp_path), transport=stub)
        d = client.discover()
        assert d.authorization_endpoint.endswith("/api/oidc/authorization")
        assert d.token_endpoint.endswith("/api/oidc/token")
        assert d.jwks_uri == f"{ISSUER}/jwks"
        assert d.end_session_endpoint == f"{ISSUER}/logout"
        assert stub.calls == [f"{ISSUER}/.well-known/openid-configuration"]

    def test_discovery_is_cached(self, tmp_path):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        stub = StubIdP()
        client = OIDCClient(load_settings(tmp_path), transport=stub)
        client.discover()
        client.discover()
        assert len(stub.calls) == 1

    def test_dead_provider_is_unreachable_and_the_failure_is_cached(self, tmp_path):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        dead = DeadTransport()
        service = OIDCService(tmp_path, transport=dead)
        first = service.status()
        assert first["status"] == "unreachable"
        assert first["ok"] is False
        assert first["data"]["login_available"] is False
        assert "could not reach" in first["data"]["detail"]
        service.status()
        # A down IdP must not turn every status call into a new timeout.
        assert len(dead.calls) == 1

    def test_wrong_issuer_echo_is_misconfigured(self, tmp_path):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        stub = StubIdP(
            discovery={
                "issuer": "https://evil.example.net",
                "authorization_endpoint": "https://evil.example.net/a",
                "token_endpoint": "https://evil.example.net/t",
                "jwks_uri": "https://evil.example.net/j",
            }
        )
        status = OIDCService(tmp_path, transport=stub).status()
        assert status["status"] == "misconfigured"
        assert "does not match configured issuer" in status["data"]["detail"]

    def test_missing_discovery_document_is_misconfigured(self, tmp_path):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        status = OIDCService(tmp_path, transport=StubIdP(discovery_status=404)).status()
        assert status["status"] == "misconfigured"
        assert "no discovery document" in status["data"]["detail"]

    def test_missing_required_endpoint_is_misconfigured(self, tmp_path):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        doc = StubIdP()._discovery
        doc.pop("jwks_uri")
        status = OIDCService(tmp_path, transport=StubIdP(discovery=doc)).status()
        assert status["status"] == "misconfigured"
        assert "jwks_uri" in status["data"]["detail"]

    def test_healthy_status_reports_discovery_without_secrets(
        self, tmp_path, monkeypatch
    ):
        secret = _with_secret(monkeypatch)
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        status = OIDCService(tmp_path, transport=StubIdP()).status()
        assert status["ok"] is True
        assert status["status"] == "configured"
        data = status["data"]
        assert data["login_available"] is True
        assert data["client_authentication"] == "client_secret_post"
        assert data["discovery"]["jwks_uri"] == f"{ISSUER}/jwks"
        assert data["discovery"]["checked_at"] > 0
        assert data["signature_verification"]["available"] is True
        assert data["pkce"] == "S256"
        assert secret not in json.dumps(status)

    def test_public_client_is_reported_honestly(self, tmp_path):
        public = {k: v for k, v in CONFIG.items() if k != "client_secret_env"}
        (tmp_path / "oidc.json").write_text(json.dumps(public))
        status = OIDCService(tmp_path, transport=StubIdP()).status()
        assert status["status"] == "configured"
        assert status["data"]["client_authentication"] == "none"
        assert any("public client" in w for w in status["warnings"])

    def test_missing_required_secret_is_misconfigured(self, tmp_path):
        """A configured secret env with an unset variable is never
        reported as working."""
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        stub = StubIdP()
        stub._discovery["token_endpoint_auth_methods_supported"] = [
            "client_secret_post"
        ]
        status = OIDCService(tmp_path, transport=stub).status()
        assert status["status"] == "misconfigured"
        assert status["data"]["client_secret_present"] is False
        assert "client_secret_env" in status["data"]["detail"]

    def test_named_but_unset_secret_warns_when_public_auth_is_allowed(self, tmp_path):
        """A secret env that names an unset variable is visible, not
        silently downgraded to public-client auth."""
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        status = OIDCService(tmp_path, transport=StubIdP()).status()
        assert status["status"] == "configured"  # provider allows "none"
        assert status["data"]["client_secret_present"] is False
        assert status["data"]["client_authentication"] == "none"
        assert any(SECRET_ENV in w and "not set" in w for w in status["warnings"]), (
            status["warnings"]
        )

    def test_unverifiable_signing_algorithm_is_honest(self, tmp_path):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        stub = StubIdP()
        stub._discovery["id_token_signing_alg_values_supported"] = ["ES512"]
        status = OIDCService(tmp_path, transport=stub).status()
        if _HAS_CRYPTO:
            assert status["status"] == "configured"
        else:
            assert status["status"] == "misconfigured"
            assert "cannot verify" in status["data"]["detail"]


class TestStatusRoute:
    def test_status_route_reports_configured(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=StubIdP())
        r = c.get("/api/auth/oidc/status")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["status"] == "configured"
        assert body["data"]["discovery"]["authorization_endpoint"].startswith(ISSUER)
        assert SECRET_VALUE not in r.text

    def test_status_route_reports_unreachable(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        c = _app_client(
            tmp_path, monkeypatch, oidc_config=CONFIG, transport=DeadTransport()
        )
        body = c.get("/api/auth/oidc/status").json()
        assert body["ok"] is False
        assert body["status"] == "unreachable"
        assert body["data"]["login_available"] is False

    def test_legacy_config_route_still_answers(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=StubIdP())
        body = c.get("/api/auth/oidc/config").json()
        assert body["ok"] is True
        data = body["data"]
        assert data["client_id"] == CLIENT_ID
        assert data["scopes"] == ["openid", "profile", "email"]
        assert data["display_name"] == "Home SSO"
        assert data["authorization_endpoint"].endswith("/api/oidc/authorization")
        assert data["login_url"] == "/api/auth/oidc/login"

    def test_legacy_config_route_when_unconfigured(self, tmp_path, monkeypatch):
        c = _app_client(tmp_path, monkeypatch)
        body = c.get("/api/auth/oidc/config").json()
        assert body["ok"] is False
        assert body["status"] == "not_configured"
        assert body["warnings"]


# ===========================================================================
# Local auth is unaffected when OIDC is absent
# ===========================================================================


class TestNoRegressionWithoutOIDC:
    def test_local_login_and_session_work(self, tmp_path, monkeypatch):
        c = _app_client(tmp_path, monkeypatch)
        r = c.post("/api/auth/login", json={"token": "tok-1"})
        assert r.status_code == 200, r.text
        sid = r.json()["data"]["session_id"]
        assert r.json()["data"]["auth_method"] == "local"
        cookie = {"Cookie": f"pw_session={sid}"}
        sess = c.get("/api/auth/session", headers=cookie).json()["data"]
        assert sess["principal_id"] == "primary"
        assert sess["auth_method"] == "local"
        assert "oidc" not in sess  # session reporting stays provider-free
        assert c.get("/api/status", headers=cookie).status_code == 200
        assert (
            c.get("/api/identity/principal", headers=cookie).json()["data"]["source"]
            == "session"
        )

    def test_oidc_status_is_not_configured(self, tmp_path, monkeypatch):
        c = _app_client(tmp_path, monkeypatch)
        body = c.get("/api/auth/oidc/status").json()
        assert body["ok"] is False
        assert body["status"] == "not_configured"
        assert body["data"]["login_available"] is False
        assert body["warnings"]

    def test_oidc_routes_degrade_without_config(self, tmp_path, monkeypatch):
        c = _app_client(tmp_path, monkeypatch)
        r = c.get(
            "/api/auth/oidc/login",
            headers={"Accept": "application/json"},
            follow_redirects=False,
        )
        assert r.status_code == 404
        assert r.json()["error_code"] == "oidc_not_configured"
        # browser flavour: a redirect to the login page, never a bare
        # JSON error dumped into a navigation
        r = c.get("/api/auth/oidc/login", follow_redirects=False)
        assert r.status_code == 303
        assert _error_code(r) == "oidc_not_configured"
        assert r.headers["cache-control"] == "no-store"

    def test_bad_token_still_rejected(self, tmp_path, monkeypatch):
        c = _app_client(tmp_path, monkeypatch)
        assert c.post("/api/auth/login", json={"token": "nope"}).status_code == 401

    def test_step_up_semantics_unchanged(self, tmp_path, monkeypatch):
        c = _app_client(tmp_path, monkeypatch)
        sid = c.post("/api/auth/login", json={"token": "tok-1"}).json()["data"][
            "session_id"
        ]
        cookie = {"Cookie": f"pw_session={sid}"}
        assert c.post("/api/auth/step-up", headers=cookie).status_code == 403
        r = c.post(
            "/api/auth/step-up", headers={"Authorization": "Bearer tok-1", **cookie}
        )
        assert r.status_code == 200
        assert r.json()["data"]["has_step_up"] is True

    def test_local_login_still_works_with_oidc_configured(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=StubIdP())
        r = c.post("/api/auth/login", json={"token": "tok-1"})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["auth_method"] == "local"

    def test_bearer_auth_still_works_with_oidc_configured(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=StubIdP())
        r = c.get("/api/status", headers={"Authorization": "Bearer tok-1"})
        assert r.status_code == 200, r.text


# ===========================================================================
# The login redirect
# ===========================================================================


class TestLoginRedirect:
    def test_authorize_request_is_pkce_and_nonce_bearing(self, tmp_path, monkeypatch):
        secret = _with_secret(monkeypatch)
        stub = StubIdP()
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        params = _start_login(c, stub)
        assert params["response_type"] == "code"
        assert params["client_id"] == CLIENT_ID
        assert params["scope"] == "openid profile email"
        assert params["redirect_uri"] == "https://pw.test/api/auth/oidc/callback"
        assert params["code_challenge_method"] == "S256"
        assert len(params["code_challenge"]) >= 43
        assert params["state"] and params["nonce"]
        # A secret never travels through the front channel.
        assert "client_secret" not in params
        assert secret not in urllib.parse.urlencode(params)

    def test_state_cookie_is_set_httponly(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=StubIdP())
        r = c.get("/api/auth/oidc/login", follow_redirects=False)
        cookie = r.headers["set-cookie"]
        assert "pw_oidc_state=" in cookie
        assert "HttpOnly" in cookie
        assert "Secure" in cookie
        assert "lax" in cookie.lower()

    def test_each_attempt_gets_fresh_state_and_verifier(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        stub = StubIdP()
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        first = _start_login(c, stub)
        second = _start_login(c, stub)
        assert first["state"] != second["state"]
        assert first["code_challenge"] != second["code_challenge"]
        assert first["nonce"] != second["nonce"]

    def test_unreachable_provider_degrades_to_login_page(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        c = _app_client(
            tmp_path, monkeypatch, oidc_config=CONFIG, transport=DeadTransport()
        )
        r = c.get("/api/auth/oidc/login", follow_redirects=False)
        assert r.status_code == 303
        assert _error_code(r) == "oidc_unreachable"
        assert "pw_session=" not in r.headers.get("set-cookie", "")


# ===========================================================================
# The callback: token exchange + id_token verification
# ===========================================================================


class TestCallbackHappyPath:
    def test_verified_id_token_creates_an_oidc_session(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        stub = StubIdP()
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        params = _start_login(c, stub)
        r = _callback(c, params)
        assert r.status_code == 303, r.text
        assert r.headers["location"] == "/"
        assert "pw_session=" in r.headers["set-cookie"]
        sid = _session_id(r)
        cookie = {"Cookie": f"pw_session={sid}"}

        sess = c.get("/api/auth/session", headers=cookie).json()["data"]
        assert sess["auth_method"] == "oidc"
        # single mode: a verified external identity is the owner
        assert sess["principal_id"] == "primary"

        principal = c.get("/api/identity/principal", headers=cookie).json()["data"]
        assert principal["source"] == "oidc"
        assert c.get("/api/status", headers=cookie).status_code == 200
        # the flow cookie is consumed, not left lying around
        assert "pw_oidc_state" in r.headers["set-cookie"]

    def test_token_request_carries_pkce_verifier_and_replays_redirect_uri(
        self, tmp_path, monkeypatch
    ):
        secret = _with_secret(monkeypatch)
        stub = StubIdP()
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        params = _start_login(c, stub)
        assert _callback(c, params).status_code == 303
        form = stub.token_requests[0]
        assert form["grant_type"] == "authorization_code"
        assert form["code"] == "auth-code-1"
        assert stub.pkce_verified is True
        assert form["redirect_uri"] == params["redirect_uri"]
        assert form["client_id"] == CLIENT_ID
        assert form["client_secret"] == secret

    def test_jwks_is_fetched_from_the_provider(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        stub = StubIdP()
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        params = _start_login(c, stub)
        _callback(c, params)
        assert f"{ISSUER}/jwks" in stub.calls

    def test_public_client_sends_no_secret(self, tmp_path, monkeypatch):
        stub = StubIdP()
        public = {k: v for k, v in CONFIG.items() if k != "client_secret_env"}
        c = _app_client(tmp_path, monkeypatch, oidc_config=public, transport=stub)
        params = _start_login(c, stub)
        assert _callback(c, params).status_code == 303
        assert "client_secret" not in stub.token_requests[0]
        assert stub.pkce_verified is True

    def test_basic_client_auth_is_used_when_the_provider_prefers_it(
        self, tmp_path, monkeypatch
    ):
        secret = _with_secret(monkeypatch)
        stub = StubIdP()
        stub._discovery["token_endpoint_auth_methods_supported"] = [
            "client_secret_basic"
        ]
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        params = _start_login(c, stub)
        assert _callback(c, params).status_code == 303
        assert "client_secret" not in stub.token_requests[0]
        # HTTP Basic is *standard* base64 with padding (RFC 6749 §2.3.1),
        # not the base64url form JWT and PKCE use. This input needs "=="
        # padding, so a urlsafe/unpadded encoding cannot pass.
        header = stub.token_headers[0]["Authorization"]
        assert header.startswith("Basic ")
        assert header.split(" ", 1)[1] == base64.b64encode(
            f"{CLIENT_ID}:{secret}".encode()
        ).decode("ascii")
        assert (
            base64.b64decode(header.split(" ", 1)[1]).decode()
            == f"{CLIENT_ID}:{secret}"
        )


class TestDisplayEnrichment:
    """Userinfo is cosmetics. The verified id_token is the identity."""

    def _client(self, tmp_path, stub):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        return OIDCClient(load_settings(tmp_path), transport=stub)

    def test_display_falls_back_to_userinfo(self, tmp_path):
        stub = StubIdP(
            userinfo={"sub": "authelia-sub-1", "preferred_username": "sam.p"}
        )
        stub.claims_override = {"preferred_username": None, "name": None, "email": None}
        client = self._client(tmp_path, stub)
        identity = client.complete_login("code", _pending())
        assert identity.sub == "authelia-sub-1"
        assert identity.display_name == "sam.p"

    def test_userinfo_about_another_subject_is_never_merged(self, tmp_path):
        stub = StubIdP(
            userinfo={"sub": "someone-else", "preferred_username": "intruder"}
        )
        stub.claims_override = {"preferred_username": None, "name": None, "email": None}
        client = self._client(tmp_path, stub)
        identity = client.complete_login("code", _pending())
        assert identity.sub == "authelia-sub-1"
        assert identity.display_name == "authelia-sub-1"

    def test_userinfo_failure_does_not_break_sign_in(self, tmp_path):
        stub = StubIdP(
            userinfo={"sub": "authelia-sub-1", "name": "Rylee"}, userinfo_status=500
        )
        stub.claims_override = {"preferred_username": None, "name": None, "email": None}
        client = self._client(tmp_path, stub)
        identity = client.complete_login("code", _pending())
        assert identity.sub == "authelia-sub-1"

    def test_verified_claims_are_preferred(self, tmp_path):
        stub = StubIdP(
            userinfo={"sub": "authelia-sub-1", "preferred_username": "attacker-chosen"}
        )
        client = self._client(tmp_path, stub)
        identity = client.complete_login("code", _pending())
        assert identity.display_name == "sam"
        assert identity.email == "sam@example.invalid"
        assert f"{ISSUER}/api/oidc/userinfo" not in stub.calls


class TestCallbackRejectsBadTokens:
    def _run(
        self,
        tmp_path,
        monkeypatch,
        *,
        claims=None,
        alg=None,
        token_status=200,
        token_body=None,
        jwks_payload=None,
        jwks_status=200,
        kid=None,
        header=None,
    ):
        _with_secret(monkeypatch)
        stub = StubIdP(
            token_status=token_status,
            token_body=token_body,
            jwks_payload=jwks_payload,
            jwks_status=jwks_status,
        )
        if claims or alg or header or kid:

            def signer(c, **kw):
                payload = dict(c)
                payload.update(claims or {})
                return sign_jwt(
                    payload, alg=alg or "RS256", kid=kid or TEST_KID, header=header
                )

            stub.token_signer = signer
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        params = _start_login(c, stub)
        return _callback(c, params, accept="application/json"), stub

    def _assert_rejected(self, response, code):
        assert response.status_code in (400, 403, 500, 502), response.text
        assert response.json()["error_code"] == code, response.text
        assert "pw_session=" not in response.headers.get("set-cookie", "")

    def test_wrong_audience(self, tmp_path, monkeypatch):
        r, _ = self._run(tmp_path, monkeypatch, claims={"aud": "some-other-client"})
        self._assert_rejected(r, "oidc_bad_audience")

    def test_wrong_issuer(self, tmp_path, monkeypatch):
        r, _ = self._run(
            tmp_path, monkeypatch, claims={"iss": "https://evil.example.net"}
        )
        self._assert_rejected(r, "oidc_bad_issuer")

    def test_expired(self, tmp_path, monkeypatch):
        r, _ = self._run(tmp_path, monkeypatch, claims={"exp": int(time.time()) - 3600})
        self._assert_rejected(r, "oidc_token_expired")

    def test_missing_exp(self, tmp_path, monkeypatch):
        r, _ = self._run(tmp_path, monkeypatch, claims={"exp": None})
        self._assert_rejected(r, "oidc_bad_expiry")

    def test_missing_subject(self, tmp_path, monkeypatch):
        r, _ = self._run(tmp_path, monkeypatch, claims={"sub": ""})
        self._assert_rejected(r, "oidc_no_subject")

    def test_clock_skew_within_tolerance_is_accepted(self, tmp_path, monkeypatch):
        r, _ = self._run(tmp_path, monkeypatch, claims={"exp": int(time.time()) - 30})
        assert r.status_code == 303, r.text

    def test_multiple_audiences_need_azp(self, tmp_path, monkeypatch):
        r, _ = self._run(tmp_path, monkeypatch, claims={"aud": [CLIENT_ID, "other"]})
        self._assert_rejected(r, "oidc_bad_audience")
        r, _ = self._run(
            tmp_path,
            monkeypatch,
            claims={"aud": [CLIENT_ID, "other"], "azp": CLIENT_ID},
        )
        assert r.status_code == 303, r.text

    def test_alg_none_is_refused(self, tmp_path, monkeypatch):
        r, _ = self._run(
            tmp_path, monkeypatch, header={"alg": "none", "typ": "JWT", "kid": TEST_KID}
        )
        self._assert_rejected(r, "oidc_alg_unsupported")

    def test_missing_alg_is_refused(self, tmp_path, monkeypatch):
        r, _ = self._run(tmp_path, monkeypatch, header={"typ": "JWT"})
        self._assert_rejected(r, "oidc_alg_unsupported")

    def test_unknown_kid_is_refused_after_a_jwks_refresh(self, tmp_path, monkeypatch):
        r, stub = self._run(tmp_path, monkeypatch, kid="rotated-key")
        self._assert_rejected(r, "oidc_key_not_found")
        # key rotation gets exactly one honest retry against fresh JWKS
        assert stub.calls.count(f"{ISSUER}/jwks") == 2

    def test_empty_jwks_is_refused(self, tmp_path, monkeypatch):
        r, _ = self._run(tmp_path, monkeypatch, jwks_payload={"keys": []})
        self._assert_rejected(r, "oidc_key_not_found")

    def test_jwks_endpoint_down_is_unreachable(self, tmp_path, monkeypatch):
        r, _ = self._run(tmp_path, monkeypatch, jwks_status=503)
        assert r.status_code == 502, r.text
        assert r.json()["status"] == "unreachable"

    def test_token_endpoint_rejection(self, tmp_path, monkeypatch):
        r, _ = self._run(
            tmp_path,
            monkeypatch,
            token_status=400,
            token_body={"error": "invalid_grant", "error_description": "code reused"},
        )
        self._assert_rejected(r, "oidc_token_exchange_failed")
        assert "invalid_grant" in r.json()["detail"]

    def test_no_id_token_in_response(self, tmp_path, monkeypatch):
        r, _ = self._run(
            tmp_path,
            monkeypatch,
            token_body={"access_token": "at", "token_type": "Bearer"},
        )
        self._assert_rejected(r, "oidc_no_id_token")

    def test_id_token_signature_is_checked_before_claims(self, tmp_path, monkeypatch):
        """A forged token with perfect claims is still refused."""
        r, _ = self._run(tmp_path, monkeypatch, alg="RS256", claims={"sub": "primary"})
        assert r.status_code == 303  # genuine signature: accepted
        # now break only the signature
        _with_secret(monkeypatch)
        stub = StubIdP()

        def bad_signer(claims, **kw):
            token = sign_jwt(claims)
            head, payload, sig = token.split(".")
            raw = bytearray(_b64u_decode(sig))
            raw[-1] ^= 0x01
            return f"{head}.{payload}.{_b64u(bytes(raw))}"

        stub.token_signer = bad_signer
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        params = _start_login(c, stub)
        r = _callback(c, params, accept="application/json")
        self._assert_rejected(r, "oidc_bad_signature")


class TestCallbackStateAndReplay:
    def test_state_mismatch_is_refused(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        stub = StubIdP()
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        params = _start_login(c, stub)
        r = _callback(c, params, state="forged-state", accept="application/json")
        assert r.status_code == 400
        assert r.json()["error_code"] == "oidc_state_mismatch"
        assert stub.token_requests == []

    def test_missing_state_cookie_is_refused(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        stub = StubIdP()
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        params = _start_login(c, stub)
        fresh = TestClient(c.app, base_url="https://pw.test")
        r = fresh.get(
            "/api/auth/oidc/callback",
            params={"code": "c", "state": params["state"]},
            headers={"Accept": "application/json"},
            follow_redirects=False,
        )
        assert r.status_code == 400
        assert r.json()["error_code"] == "oidc_missing_state"
        assert stub.token_requests == []

    def test_provider_denial_is_honest(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        stub = StubIdP()
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        params = _start_login(c, stub)
        r = c.get(
            "/api/auth/oidc/callback",
            params={
                "error": "access_denied",
                "error_description": "user said no",
                "state": params["state"],
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert _error_code(r) == "oidc_provider_denied"
        assert "user said no" not in r.headers["location"]

    def test_tampered_cookie_is_refused(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        stub = StubIdP()
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        params = _start_login(c, stub)
        cookie = c.cookies.get("pw_oidc_state")
        assert cookie
        payload, _, sig = cookie.rpartition(".")
        forged = ("x" + payload[1:]) + "." + sig
        other = TestClient(c.app, base_url="https://pw.test")
        r = other.get(
            "/api/auth/oidc/callback",
            params={"code": "c", "state": params["state"]},
            headers={"Accept": "application/json", "Cookie": f"pw_oidc_state={forged}"},
            follow_redirects=False,
        )
        assert r.status_code == 400
        assert r.json()["error_code"] == "oidc_state_invalid"

    def test_unmapped_identity_never_mints_an_account(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        stub = StubIdP()
        stub.sub = "stranger"
        c = _app_client(
            tmp_path, monkeypatch, mode="multi", oidc_config=CONFIG, transport=stub
        )
        params = _start_login(c, stub)
        r = _callback(c, params, accept="application/json")
        assert r.status_code == 403
        assert r.json()["error_code"] == "oidc_identity_not_mapped"
        assert "pw_session=" not in r.headers.get("set-cookie", "")

    def test_mapped_identity_in_multi_mode_signs_in(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        stub = StubIdP()
        stub.sub = "sam"
        c = _app_client(
            tmp_path, monkeypatch, mode="multi", oidc_config=CONFIG, transport=stub
        )
        from personal_world.identity import IdentityStore

        IdentityStore(tmp_path).create_user("sam", "Sam")
        params = _start_login(c, stub)
        r = _callback(c, params)
        assert r.status_code == 303, r.text
        sid = _session_id(r)
        sess = c.get(
            "/api/auth/session", headers={"Cookie": f"pw_session={sid}"}
        ).json()["data"]
        assert sess["principal_id"] == "sam"
        assert sess["auth_method"] == "oidc"

    def test_oidc_session_cannot_step_up_without_a_credential(
        self, tmp_path, monkeypatch
    ):
        """Step-up semantics stay intact: an OIDC sign-in is not a
        step-up grant."""
        _with_secret(monkeypatch)
        stub = StubIdP()
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        params = _start_login(c, stub)
        r = _callback(c, params)
        sid = _session_id(r)
        cookie = {"Cookie": f"pw_session={sid}"}
        assert c.post("/api/auth/step-up", headers=cookie).status_code == 403
        # the instance credential still elevates the same principal
        r = c.post(
            "/api/auth/step-up", headers={"Authorization": "Bearer tok-1", **cookie}
        )
        assert r.status_code == 200
        assert r.json()["data"]["principal_id"] == "primary"


class TestFlowCodec:
    def test_round_trip(self):
        codec = FlowCodec(key=b"k" * 32)
        pending = _pending()
        assert codec.decode(codec.encode(pending)) == pending

    def test_tampered_payload(self):
        codec = FlowCodec(key=b"k" * 32)
        blob = codec.encode(_pending())
        payload, _, sig = blob.rpartition(".")
        with pytest.raises(OIDCLoginError) as exc:
            codec.decode(("x" + payload[1:]) + "." + sig)
        assert exc.value.error_code == "oidc_state_invalid"

    def test_another_key_cannot_sign(self):
        blob = FlowCodec(key=b"a" * 32).encode(_pending())
        with pytest.raises(OIDCLoginError):
            FlowCodec(key=b"b" * 32).decode(blob)

    def test_expired_attempt(self):
        now = time.time()
        blob = FlowCodec(key=b"k" * 32, clock=lambda: now).encode(_pending())
        later = FlowCodec(key=b"k" * 32, clock=lambda: now + 601)
        with pytest.raises(OIDCLoginError) as exc:
            later.decode(blob)
        assert exc.value.error_code == "oidc_attempt_expired"

    def test_empty_cookie(self):
        with pytest.raises(OIDCLoginError) as exc:
            FlowCodec().decode(None)
        assert exc.value.error_code == "oidc_missing_state"


# ===========================================================================
# Logout
# ===========================================================================


class TestLogout:
    def _signed_in(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        stub = StubIdP()
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        params = _start_login(c, stub)
        r = _callback(c, params)
        assert r.status_code == 303, r.text
        return c, stub, _session_id(r)

    def test_oidc_logout_ends_both_sessions(self, tmp_path, monkeypatch):
        c, _stub, sid = self._signed_in(tmp_path, monkeypatch)
        r = c.get("/api/auth/oidc/logout", follow_redirects=False)
        assert r.status_code == 303
        location = r.headers["location"]
        assert location.startswith(f"{ISSUER}/logout?")
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(location).query))
        assert query["post_logout_redirect_uri"] == "https://pw.test/login"
        assert query["client_id"] == CLIENT_ID
        # the local session is dead before the provider is ever visited
        _assert_session_dead(c, sid)

    def test_logout_without_end_session_endpoint_stays_local(
        self, tmp_path, monkeypatch
    ):
        _with_secret(monkeypatch)
        stub = StubIdP()
        stub._discovery.pop("end_session_endpoint")
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        r = c.get("/api/auth/oidc/logout", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "https://pw.test/login"

    def test_logout_works_when_the_provider_is_down(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        c = _app_client(
            tmp_path, monkeypatch, oidc_config=CONFIG, transport=DeadTransport()
        )
        r = c.get("/api/auth/oidc/logout", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "https://pw.test/login"

    def test_logout_works_without_oidc_configured(self, tmp_path, monkeypatch):
        c = _app_client(tmp_path, monkeypatch)
        sid = c.post("/api/auth/login", json={"token": "tok-1"}).json()["data"][
            "session_id"
        ]
        r = c.get(
            "/api/auth/oidc/logout",
            headers={"Cookie": f"pw_session={sid}"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        _assert_session_dead(c, sid)

    def test_post_logout_offers_end_session_url_for_oidc_sessions(
        self, tmp_path, monkeypatch
    ):
        c, _stub, sid = self._signed_in(tmp_path, monkeypatch)
        r = c.post("/api/auth/logout", headers={"Cookie": f"pw_session={sid}"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["data"]["end_session_url"].startswith(f"{ISSUER}/logout?")
        _assert_session_dead(c, sid)

    def test_post_logout_for_a_local_session_has_no_provider_url(
        self, tmp_path, monkeypatch
    ):
        c = _app_client(tmp_path, monkeypatch)
        sid = c.post("/api/auth/login", json={"token": "tok-1"}).json()["data"][
            "session_id"
        ]
        r = c.post("/api/auth/logout", headers={"Cookie": f"pw_session={sid}"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["data"]["end_session_url"] is None


# ===========================================================================
# Signature verification internals
# ===========================================================================


class TestSignatureVerification:
    def _jwk(self):
        return jwks()["keys"][0]

    def test_stdlib_verifier_accepts_a_real_signature(self):
        token = sign_jwt(id_token_claims(), alg="RS256")
        head, payload, sig = token.split(".")
        assert (
            _verify_rsa_pkcs1_stdlib(
                "RS256", self._jwk(), f"{head}.{payload}".encode(), _b64u_decode(sig)
            )
            is True
        )

    def test_stdlib_verifier_rejects_tampering(self):
        token = sign_jwt(id_token_claims(), alg="RS256")
        head, payload, sig = token.split(".")
        raw = _b64u_decode(sig)
        good = f"{head}.{payload}".encode()
        bad = f"{head}.{_b64u(json.dumps({'sub': 'other'}).encode())}".encode()
        assert _verify_rsa_pkcs1_stdlib("RS256", self._jwk(), good, raw) is True
        assert _verify_rsa_pkcs1_stdlib("RS256", self._jwk(), bad, raw) is False
        flipped = bytes([raw[0] ^ 0x01]) + raw[1:]
        assert _verify_rsa_pkcs1_stdlib("RS256", self._jwk(), good, flipped) is False
        assert _verify_rsa_pkcs1_stdlib("RS256", self._jwk(), good, raw[:-1]) is False

    def test_stdlib_verifier_rejects_the_wrong_key(self):
        token = sign_jwt(id_token_claims(), alg="RS256")
        head, payload, sig = token.split(".")
        other = dict(self._jwk())
        other["n"] = _b64u(((_RSA_N + 2**33) % (2**2048)).to_bytes(256, "big"))
        assert (
            _verify_rsa_pkcs1_stdlib(
                "RS256", other, f"{head}.{payload}".encode(), _b64u_decode(sig)
            )
            is False
        )

    @pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
    def test_stdlib_verifier_agrees_with_cryptography(self):
        """The stdlib PKCS#1 path is not merely self-consistent: the
        reference library accepts exactly the signatures it accepts."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding, rsa

        key = rsa.RSAPublicNumbers(e=_RSA_E, n=_RSA_N).public_key()
        for alg, hasher in (
            ("RS256", hashes.SHA256),
            ("RS384", hashes.SHA384),
            ("RS512", hashes.SHA512),
        ):
            token = sign_jwt(id_token_claims(), alg=alg)
            head, payload, sig = token.split(".")
            signing_input = f"{head}.{payload}".encode()
            raw = _b64u_decode(sig)
            # raises InvalidSignature if the test signer is wrong
            key.verify(raw, signing_input, padding.PKCS1v15(), hasher())
            assert (
                _verify_rsa_pkcs1_stdlib(alg, self._jwk(), signing_input, raw) is True
            )

    @pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
    def test_ecdsa_provider_key(self, tmp_path):
        """An EC provider key verifies through the cryptography backend."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import (
            decode_dss_signature,
        )

        private = ec.generate_private_key(ec.SECP256R1())
        numbers = private.public_key().public_numbers()

        def es_signer(claims, **kw):
            head = {"alg": "ES256", "typ": "JWT", "kid": "ec-key"}
            signing_input = (
                _b64u(json.dumps(head, separators=(",", ":")).encode())
                + "."
                + _b64u(json.dumps(claims, separators=(",", ":")).encode())
            ).encode()
            r, s = decode_dss_signature(
                private.sign(signing_input, ec.ECDSA(hashes.SHA256()))
            )
            raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
            return signing_input.decode() + "." + _b64u(raw)

        ec_jwks = {
            "keys": [
                {
                    "kty": "EC",
                    "crv": "P-256",
                    "use": "sig",
                    "alg": "ES256",
                    "kid": "ec-key",
                    "x": _b64u(numbers.x.to_bytes(32, "big")),
                    "y": _b64u(numbers.y.to_bytes(32, "big")),
                }
            ]
        }
        stub = StubIdP(jwks_payload=ec_jwks, token_signer=es_signer)
        stub._discovery["id_token_signing_alg_values_supported"] = ["ES256"]
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        client = OIDCClient(load_settings(tmp_path), transport=stub)
        identity = client.verify_id_token(
            es_signer(id_token_claims(nonce="test-nonce")), _pending()
        )
        assert identity.sub == "authelia-sub-1"

    def test_without_cryptography_rsa_still_verifies(self, tmp_path, monkeypatch):
        """The minimal install (CI: --extra test only) is not a
        second-class citizen for RS256."""
        monkeypatch.setattr(oidc_module, "_HAS_CRYPTO", False)
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        client = OIDCClient(load_settings(tmp_path), transport=StubIdP())
        identity = client.verify_id_token(
            sign_jwt(id_token_claims(nonce="test-nonce")), _pending()
        )
        assert identity.sub == "authelia-sub-1"
        state = oidc_module.signature_verification_state()
        assert state["backend"] == "stdlib"
        assert state["algorithms"] == ["RS256", "RS384", "RS512"]

    def test_without_cryptography_ecdsa_fails_closed(self, monkeypatch):
        monkeypatch.setattr(oidc_module, "_HAS_CRYPTO", False)
        assert "ES256" not in oidc_module.supported_algorithms()
        with pytest.raises(OIDCLoginError) as exc:
            verify_signature("ES256", {"kty": "EC"}, b"input", b"sig")
        assert exc.value.error_code == "oidc_verification_unavailable"
        assert "uv sync --extra crypto" in exc.value.detail

    def test_encrypted_id_token_is_refused(self, tmp_path):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        client = OIDCClient(load_settings(tmp_path), transport=StubIdP())
        with pytest.raises(OIDCLoginError) as exc:
            client.verify_id_token("a.b.c.d.e", _pending())
        assert exc.value.error_code == "oidc_id_token_encrypted"

    def test_malformed_id_token_is_refused(self, tmp_path):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        client = OIDCClient(load_settings(tmp_path), transport=StubIdP())
        with pytest.raises(OIDCLoginError) as exc:
            client.verify_id_token("not-a-jwt", _pending())
        assert exc.value.error_code == "oidc_id_token_malformed"

    def test_wrong_nonce_is_refused(self, tmp_path):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        client = OIDCClient(load_settings(tmp_path), transport=StubIdP())
        token = sign_jwt(id_token_claims(nonce="a-different-nonce"))
        with pytest.raises(OIDCLoginError) as exc:
            client.verify_id_token(token, _pending("test-nonce"))
        assert exc.value.error_code == "oidc_bad_nonce"

    def test_missing_nonce_is_refused(self, tmp_path):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        client = OIDCClient(load_settings(tmp_path), transport=StubIdP())
        token = sign_jwt(id_token_claims(nonce=None))
        with pytest.raises(OIDCLoginError) as exc:
            client.verify_id_token(token, _pending("test-nonce"))
        assert exc.value.error_code == "oidc_bad_nonce"

    def test_bad_signature_is_refused(self, tmp_path):
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        client = OIDCClient(load_settings(tmp_path), transport=StubIdP())
        token = sign_jwt(id_token_claims(nonce="test-nonce"))
        head, payload, sig = token.split(".")
        raw = bytearray(_b64u_decode(sig))
        raw[-1] ^= 0x01
        with pytest.raises(OIDCLoginError) as exc:
            client.verify_id_token(f"{head}.{payload}.{_b64u(bytes(raw))}", _pending())
        assert exc.value.error_code == "oidc_bad_signature"

    def test_token_from_another_provider_is_refused(self, tmp_path):
        """Cross-provider token replay: right key shape, wrong issuer."""
        (tmp_path / "oidc.json").write_text(json.dumps(CONFIG))
        client = OIDCClient(load_settings(tmp_path), transport=StubIdP())
        token = sign_jwt(
            id_token_claims(nonce="test-nonce", iss="https://other.example.net")
        )
        with pytest.raises(OIDCLoginError) as exc:
            client.verify_id_token(token, _pending())
        assert exc.value.error_code == "oidc_bad_issuer"


class TestPKCE:
    def test_verifier_and_challenge_shapes(self):
        verifier = oidc_module.new_code_verifier()
        assert 43 <= len(verifier) <= 128
        assert code_challenge(verifier) == _b64u(
            hashlib.sha256(verifier.encode()).digest()
        )
        assert oidc_module.new_code_verifier() != verifier


# ===========================================================================
# Linking a provider sign-in to an existing account (multi mode)
# ===========================================================================


def _local_session_with_step_up(client, token="tok-1") -> str:
    r = client.post("/api/auth/login", json={"token": token})
    assert r.status_code == 200, r.text
    sid = r.cookies.get("pw_session") or _session_id(r)
    r = client.post(
        "/api/auth/step-up",
        json={"token": token},
        headers={"Cookie": f"pw_session={sid}"},
    )
    assert r.status_code == 200, r.text
    return sid


def _start_link(client, stub, sid, origin="https://pw.test"):
    headers = {"Cookie": f"pw_session={sid}"}
    if origin:
        headers["Origin"] = origin
    r = client.post("/api/auth/oidc/link", headers=headers, follow_redirects=False)
    if r.status_code != 303:
        return r, None
    params = {
        k: v[0]
        for k, v in urllib.parse.parse_qs(r.headers["location"].partition("?")[2]).items()
    }
    stub.nonce = params["nonce"]
    stub.expected_challenge = params["code_challenge"]
    return r, params


class TestLinkSignIn:
    def _client(self, tmp_path, monkeypatch, stub):
        _with_secret(monkeypatch)
        return _app_client(
            tmp_path, monkeypatch, mode="multi", oidc_config=CONFIG, transport=stub
        )

    def test_owner_links_then_signs_in_with_the_provider(self, tmp_path, monkeypatch):
        stub = StubIdP()
        stub.sub = "opaque-sub-owner"
        c = self._client(tmp_path, monkeypatch, stub)
        sid = _local_session_with_step_up(c)
        _, params = _start_link(c, stub, sid)
        c.cookies.set("pw_session", sid)
        r = _callback(c, params)
        assert r.status_code == 303, r.text
        c.cookies.clear()

        # A fresh provider sign-in now resolves to the owner.
        params = _start_login(c, stub)
        r = _callback(c, params)
        assert r.status_code == 303, r.text
        sess = c.get(
            "/api/auth/session", headers={"Cookie": f"pw_session={_session_id(r)}"}
        ).json()["data"]
        assert sess["principal_id"] == "primary"
        assert sess["auth_method"] == "oidc"

    def test_link_needs_step_up(self, tmp_path, monkeypatch):
        stub = StubIdP()
        c = self._client(tmp_path, monkeypatch, stub)
        r = c.post("/api/auth/login", json={"token": "tok-1"})
        sid = r.cookies.get("pw_session") or _session_id(r)
        r, _ = _start_link(c, stub, sid)
        assert r.status_code == 403

    def test_link_needs_same_origin(self, tmp_path, monkeypatch):
        stub = StubIdP()
        c = self._client(tmp_path, monkeypatch, stub)
        sid = _local_session_with_step_up(c)
        r, _ = _start_link(c, stub, sid, origin="https://evil.test")
        assert r.status_code == 403
        r, _ = _start_link(c, stub, sid, origin="")
        assert r.status_code == 403

    def test_link_needs_a_session(self, tmp_path, monkeypatch):
        stub = StubIdP()
        c = self._client(tmp_path, monkeypatch, stub)
        r = c.post(
            "/api/auth/oidc/link",
            headers={"Origin": "https://pw.test"},
            follow_redirects=False,
        )
        assert r.status_code == 401

    def test_callback_refuses_link_when_signed_out_meanwhile(
        self, tmp_path, monkeypatch
    ):
        stub = StubIdP()
        stub.sub = "opaque-sub-2"
        c = self._client(tmp_path, monkeypatch, stub)
        sid = _local_session_with_step_up(c)
        _, params = _start_link(c, stub, sid)
        c.cookies.delete("pw_session")
        r = _callback(c, params, accept="application/json")
        assert r.status_code == 403
        assert r.json()["error_code"] == "oidc_link_session_changed"
        from personal_world.identity import IdentityStore

        assert IdentityStore(tmp_path).find_by_oidc_subject("opaque-sub-2") is None

    def test_a_subject_links_to_one_account_only(self, tmp_path, monkeypatch):
        from personal_world.identity import IdentityStore

        store = IdentityStore(tmp_path)
        store.create_user("jo", "Jo")
        store.create_user("kit", "Kit")
        store.link_oidc_subject("jo", "sub-x")
        store.link_oidc_subject("jo", "sub-x")  # again: no-op
        with pytest.raises(ValueError):
            store.link_oidc_subject("kit", "sub-x")
        assert store.find_by_oidc_subject("sub-x")["user_id"] == "jo"
        store.disable_user("jo")
        assert store.find_by_oidc_subject("sub-x") is None


# ===========================================================================
# "Confirm it's you" by a fresh provider sign-in (step-up without a key)
# ===========================================================================


class TestOidcStepUp:
    def _signed_in(self, tmp_path, monkeypatch, stub, mode="single"):
        _with_secret(monkeypatch)
        c = _app_client(
            tmp_path, monkeypatch, mode=mode, oidc_config=CONFIG, transport=stub
        )
        params = _start_login(c, stub)
        r = _callback(c, params)
        assert r.status_code == 303, r.text
        sid = _session_id(r)
        c.cookies.set("pw_session", sid)
        return c, sid

    def _start_step_up(self, c, stub, return_to="/settings"):
        r = c.get(
            "/api/auth/oidc/step-up",
            params={"return_to": return_to},
            follow_redirects=False,
        )
        assert r.status_code == 303, r.text
        params = {
            k: v[0]
            for k, v in urllib.parse.parse_qs(
                r.headers["location"].partition("?")[2]
            ).items()
        }
        stub.nonce = params["nonce"]
        stub.expected_challenge = params["code_challenge"]
        return params

    def _session(self, c):
        return c.get("/api/auth/session").json()["data"]

    def test_fresh_sign_in_grants_step_up_and_returns(self, tmp_path, monkeypatch):
        stub = StubIdP()
        c, _ = self._signed_in(tmp_path, monkeypatch, stub)
        assert self._session(c)["has_step_up"] is False
        params = self._start_step_up(c, stub)
        assert params["prompt"] == "login"
        assert params["max_age"] == "0"
        stub.claims_override = {"auth_time": int(time.time())}
        r = _callback(c, params)
        assert r.status_code == 303, r.text
        assert r.headers["location"] == "/settings"
        assert self._session(c)["has_step_up"] is True

    def test_stale_sign_in_is_refused(self, tmp_path, monkeypatch):
        stub = StubIdP()
        c, _ = self._signed_in(tmp_path, monkeypatch, stub)
        params = self._start_step_up(c, stub)
        stub.claims_override = {"auth_time": int(time.time()) - 3600}
        r = _callback(c, params, accept="application/json")
        assert r.status_code == 403
        assert r.json()["error_code"] == "oidc_step_up_refused"
        assert self._session(c)["has_step_up"] is False

    def test_a_different_person_cannot_confirm(self, tmp_path, monkeypatch):
        from personal_world.identity import IdentityStore

        stub = StubIdP()
        stub.sub = "sub-jo"
        IdentityStore(tmp_path).create_user("jo", "Jo")
        IdentityStore(tmp_path).create_user("kit", "Kit")
        IdentityStore(tmp_path).link_oidc_subject("jo", "sub-jo")
        IdentityStore(tmp_path).link_oidc_subject("kit", "sub-kit")
        c, _ = self._signed_in(tmp_path, monkeypatch, stub, mode="multi")
        params = self._start_step_up(c, stub)
        stub.sub = "sub-kit"  # someone else signs in at the provider
        stub.claims_override = {"auth_time": int(time.time())}
        r = _callback(c, params, accept="application/json")
        assert r.status_code == 403
        assert self._session(c)["has_step_up"] is False

    def test_return_to_stays_on_this_site(self, tmp_path, monkeypatch):
        stub = StubIdP()
        c, _ = self._signed_in(tmp_path, monkeypatch, stub)
        for bad in ("https://evil.test/", "//evil.test/x", "/\\evil.test"):
            params = self._start_step_up(c, stub, return_to=bad)
            stub.claims_override = {"auth_time": int(time.time())}
            r = _callback(c, params)
            assert r.headers["location"] == "/", bad

    def test_needs_a_session(self, tmp_path, monkeypatch):
        _with_secret(monkeypatch)
        stub = StubIdP()
        c = _app_client(tmp_path, monkeypatch, oidc_config=CONFIG, transport=stub)
        r = c.get("/api/auth/oidc/step-up", follow_redirects=False)
        assert r.status_code == 401

    def test_session_lists_how_to_confirm(self, tmp_path, monkeypatch):
        from personal_world.identity import IdentityStore

        stub = StubIdP()
        stub.sub = "sub-jo"
        IdentityStore(tmp_path).create_user("jo", "Jo")
        IdentityStore(tmp_path).link_oidc_subject("jo", "sub-jo")
        c, _ = self._signed_in(tmp_path, monkeypatch, stub, mode="multi")
        # Jo signs in only through the provider: no key, but SSO works.
        assert self._session(c)["step_up_methods"] == ["sso"]
