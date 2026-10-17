"""D1 — Auth convergence.

Bearer, browser session (local), OIDC, and the explicit loopback
development bypass all resolve through the canonical Principal seam.
The contract:

- a browser session stores only a resolved principal id; it grants the
  same API rights as the bearer token that created it
- single mode resolves every in-app login to the bootstrap primary
  person; multi mode resolves the owning user and re-checks the enabled
  record each request (disabling a user revokes their session)
- an explicit bearer takes precedence over a cookie
- OIDC is mapped onto the same seam; an unmapped identity never mints
  an account (fail closed)
- no credential at all still fails closed (503 with no store, 401 with
  one)
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world.identity import (  # noqa: E402
    IdentityStore,
    NoPrincipalError,
    resolve_oidc_principal,
    resolve_session_principal,
)


def _client(tmp_path, monkeypatch, *, mode="single", token="tok-1"):
    from personal_world.api import create_app
    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("PW_API_TOKEN", token)
    monkeypatch.setenv("PW_IDENTITY_MODE", mode)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    return TestClient(create_app(tmp_path, tmp_path))


def _login(c, token):
    r = c.post("/api/auth/login", json={"token": token})
    assert r.status_code == 200, r.text
    return r.json()["data"]["session_id"]


def _cookie(sid):
    return {"Cookie": f"pw_session={sid}"}


class TestSessionPrincipalResolution:
    def test_login_local_resolves_primary_in_single_mode(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        sid = _login(c, "tok-1")
        # session principal id is the canonical principal, not "owner"
        sess = c.get("/api/auth/session", headers=_cookie(sid)).json()["data"]
        assert sess["principal_id"] == "primary"
        assert sess["auth_method"] == "local"

    def test_session_cookie_authenticates_without_bearer(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        sid = _login(c, "tok-1")
        # a fresh client with no bearer: the cookie alone is a credential
        r = c.get("/api/status", headers=_cookie(sid))
        assert r.status_code == 200, r.text
        p = c.get("/api/identity/principal", headers=_cookie(sid)).json()["data"]
        assert p["id"] == "primary"
        assert p["source"] == "session"

    def test_bearer_takes_precedence_over_session(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        sid = _login(c, "tok-1")
        # bogus bearer alongside a valid session must NOT be rescued by
        # the cookie: the explicit credential is authoritative.
        r = c.get("/api/status",
                  headers={"Authorization": "Bearer bogus", **_cookie(sid)})
        assert r.status_code == 401

    def test_invalid_session_fails_closed(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        r = c.get("/api/status", headers=_cookie("not-a-real-session"))
        assert r.status_code == 401

    def test_no_credential_no_store_is_503(self, tmp_path, monkeypatch):
        from personal_world.api import create_app
        monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
        monkeypatch.delenv("PW_API_TOKEN", raising=False)
        c = TestClient(create_app(tmp_path, tmp_path))
        assert c.get("/api/status").status_code == 503

    def test_session_resolution_unit_single_mode(self):
        p = resolve_session_principal("anything", None, "single", "local")
        assert p.id == "primary" and p.source == "session"
        p = resolve_session_principal("sub-123", None, "single", "oidc")
        assert p.id == "primary" and p.source == "oidc"
        with pytest.raises(NoPrincipalError):
            resolve_session_principal("", None, "single", "local")

    def test_session_resolution_unit_multi_mode(self, tmp_path):
        store = IdentityStore(tmp_path)
        store.create_user("alpha", "Alpha", initial_plain_token="a-tok")
        p = resolve_session_principal("alpha", store, "multi", "local")
        assert p.id == "alpha" and p.source == "session"
        with pytest.raises(NoPrincipalError):
            resolve_session_principal("ghost", store, "multi", "local")


class TestMultiUserSession:
    def test_session_resolves_owning_person(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch, mode="multi", token="instancetoken")
        r = c.post("/api/identity/users",
                   json={"user_id": "beta", "display_name": "Beta"},
                   headers={"Authorization": "Bearer instancetoken"})
        assert r.status_code == 200, r.text
        beta = r.json()["data"]["token"]
        sid = _login(c, beta)
        p = c.get("/api/identity/principal", headers=_cookie(sid)).json()["data"]
        assert p["id"] == "beta"

    def test_disabling_user_revokes_their_session(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch, mode="multi", token="instancetoken")
        r = c.post("/api/identity/users",
                   json={"user_id": "beta"},
                   headers={"Authorization": "Bearer instancetoken"})
        beta = r.json()["data"]["token"]
        sid = _login(c, beta)
        assert c.get("/api/status", headers=_cookie(sid)).status_code == 200
        d = c.delete("/api/identity/users/beta",
                     headers={"Authorization": "Bearer instancetoken"})
        assert d.status_code == 200
        # the browser session is revoked on the next request, like a token
        assert c.get("/api/status", headers=_cookie(sid)).status_code == 401


class TestOidcMapping:
    def test_single_mode_oidc_maps_to_primary(self):
        p = resolve_oidc_principal("some-sub", None, "single", "someone")
        assert p.id == "primary" and p.source == "oidc"

    def test_multi_mode_oidc_requires_local_account(self, tmp_path):
        store = IdentityStore(tmp_path)
        store.create_user("rylee", "Ry", initial_plain_token="r-tok")
        p = resolve_oidc_principal("rylee", store, "multi")
        assert p.id == "rylee" and p.source == "oidc"
        with pytest.raises(NoPrincipalError):
            resolve_oidc_principal("stranger", store, "multi")

    def test_multi_mode_oidc_never_creates_account(self, tmp_path):
        store = IdentityStore(tmp_path)
        with pytest.raises(NoPrincipalError):
            resolve_oidc_principal("nobody", store, "multi", "Nobody")
        assert store.list_users() == []
