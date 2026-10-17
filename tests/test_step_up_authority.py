"""D2 — Real step-up authority.

Step-up is one coherent, time-bounded human elevation:

- a live session grant minted by ``POST /api/auth/step-up`` after
  re-presenting a credential is the canonical mechanism; it is
  time-bounded and bound to the authenticated principal
- the true-loopback peer is a documented local-owner exception (an
  RFC1918 LAN address is NOT loopback and does not qualify)
- ``X-PW-StepUp: 1`` remains explicit trusted-proxy/transitional
  delegation, but the grant now requires the proxy secret header
  matching ``PW_PROXY_STEPUP_SECRET`` (fail closed when unset)
- step-up is a person action: an agent principal never acquires it,
  even with a delegated header
- the elevation never outlives its window and cannot be spent by a
  different principal
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world.api import _step_up_authorized  # noqa: E402
from personal_world.auth import AuthManager  # noqa: E402
from personal_world.identity import Principal  # noqa: E402


class _Peer:
    def __init__(self, host):
        self.host = host


class _FakeApp:
    def __init__(self, auth):
        class _State:
            pass

        self.state = _State()
        self.state.auth = auth


class _FakeRequest:
    def __init__(self, auth, *, host, cookies=None, headers=None):
        self.app = _FakeApp(auth)
        self.client = _Peer(host)
        self.cookies = cookies or {}
        self.headers = headers or {}


@pytest.fixture
def auth(tmp_path):
    return AuthManager(tmp_path, tmp_path)


def _session_with_grant(auth, principal_id="primary", duration=300):
    session = auth.sessions.create(principal_id, "local")
    auth.sessions.grant_step_up(
        session.id, principal_id=principal_id, duration=duration
    )
    return session


PRIMARY = Principal(id="primary", kind="person")
OTHER = Principal(id="other", kind="person")


class TestStepUpSeam:
    def test_session_grant_allows_non_loopback(self, auth):
        s = _session_with_grant(auth)
        req = _FakeRequest(auth, host="203.0.113.9", cookies={"pw_session": s.id})
        assert _step_up_authorized(req, PRIMARY) is True

    def test_expired_grant_denied(self, auth):
        s = _session_with_grant(auth, duration=-1)
        req = _FakeRequest(auth, host="203.0.113.9", cookies={"pw_session": s.id})
        assert _step_up_authorized(req, PRIMARY) is False

    def test_grant_bound_to_principal(self, auth):
        s = _session_with_grant(auth, principal_id="primary")
        req = _FakeRequest(auth, host="203.0.113.9", cookies={"pw_session": s.id})
        # the elevation was issued to "primary"; a different identity
        # cannot spend it even holding the cookie
        assert _step_up_authorized(req, OTHER) is False
        assert _step_up_authorized(req, PRIMARY) is True

    def test_non_loopback_without_grant_denied(self, auth):
        req = _FakeRequest(auth, host="203.0.113.9")
        assert _step_up_authorized(req, PRIMARY) is False

    def test_loopback_is_documented_exception(self, auth):
        for host in ("127.0.0.1", "::1", "testclient"):
            req = _FakeRequest(auth, host=host)
            assert _step_up_authorized(req, PRIMARY) is True, host

    def test_private_lan_is_not_loopback(self, auth):
        for host in ("192.0.2.11", "10.0.0.5", "172.17.0.1"):  # pw-safety: synthetic
            req = _FakeRequest(auth, host=host)
            assert _step_up_authorized(req, PRIMARY) is False, host

    def test_delegated_header_allows_with_proxy_secret(self, auth, monkeypatch):
        monkeypatch.setenv("PW_PROXY_STEPUP_SECRET", "proxy-secret-1")
        req = _FakeRequest(
            auth,
            host="203.0.113.9",
            headers={"X-PW-StepUp": "1", "X-PW-Proxy-StepUp-Secret": "proxy-secret-1"},
        )
        assert _step_up_authorized(req, PRIMARY) is True

    def test_delegated_header_denied_when_proxy_secret_unset(self, auth, monkeypatch):
        monkeypatch.delenv("PW_PROXY_STEPUP_SECRET", raising=False)
        req = _FakeRequest(auth, host="203.0.113.9", headers={"X-PW-StepUp": "1"})
        assert _step_up_authorized(req, PRIMARY) is False

    def test_delegated_header_wrong_proxy_secret_denied(self, auth, monkeypatch):
        monkeypatch.setenv("PW_PROXY_STEPUP_SECRET", "proxy-secret-1")
        req = _FakeRequest(
            auth,
            host="203.0.113.9",
            headers={"X-PW-StepUp": "1", "X-PW-Proxy-StepUp-Secret": "wrong"},
        )
        assert _step_up_authorized(req, PRIMARY) is False

    def test_delegated_header_without_secret_header_denied(self, auth, monkeypatch):
        monkeypatch.setenv("PW_PROXY_STEPUP_SECRET", "proxy-secret-1")
        req = _FakeRequest(auth, host="203.0.113.9", headers={"X-PW-StepUp": "1"})
        assert _step_up_authorized(req, PRIMARY) is False


def _client(tmp_path, monkeypatch, token="tok-1"):
    from personal_world.api import create_app

    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("PW_API_TOKEN", token)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    return TestClient(create_app(tmp_path, tmp_path))


class TestStepUpEndpoint:
    def test_step_up_requires_a_credential(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        r = c.post("/api/auth/login", json={"token": "tok-1"})
        sid = r.json()["data"]["session_id"]
        # no credential re-presented → no elevation
        r2 = c.post("/api/auth/step-up", headers={"Cookie": f"pw_session={sid}"})
        assert r2.status_code == 403

    def test_step_up_with_credential_mints_bounded_grant(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        sid = c.post("/api/auth/login", json={"token": "tok-1"}).json()["data"][
            "session_id"
        ]
        r = c.post(
            "/api/auth/step-up",
            json={"token": "tok-1"},
            headers={"Cookie": f"pw_session={sid}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["has_step_up"] is True
        assert data["expires_in"] == 300
        assert data["principal_id"] == "primary"
        sess = c.get(
            "/api/auth/session", headers={"Cookie": f"pw_session={sid}"}
        ).json()["data"]
        assert sess["has_step_up"] is True

    def test_wrong_credential_does_not_elevate(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        sid = c.post("/api/auth/login", json={"token": "tok-1"}).json()["data"][
            "session_id"
        ]
        r = c.post(
            "/api/auth/step-up",
            json={"token": "not-the-token"},
            headers={"Cookie": f"pw_session={sid}"},
        )
        assert r.status_code == 403

    def test_step_up_grant_is_time_bounded(self, tmp_path):
        auth = AuthManager(tmp_path, tmp_path)
        s = _session_with_grant(auth, duration=300)
        assert s.has_step_up("primary")
        # expire the window explicitly
        auth.sessions._sessions[s.id].step_up_until = time.time() - 1
        assert not auth.sessions._sessions[s.id].has_step_up("primary")


class TestAgentCannotStepUp:
    def test_agent_step_up_write_is_refused(self, tmp_path, monkeypatch):
        from personal_world.api import create_app

        monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
        monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
        monkeypatch.setenv("PW_IDENTITY_MODE", "multi")
        monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
        c = TestClient(create_app(tmp_path, tmp_path))
        admin = {"Authorization": "Bearer instancetoken"}
        r = c.post(
            "/api/identity/agents",
            json={"agent_id": "bot", "scopes": ["read", "write"]},
            headers=admin,
        )
        atok = r.json()["data"]["token"]
        # even with the delegated header, an agent never acquires
        # step-up: human elevation is person-only.
        r2 = c.post(
            "/api/world/intent",
            json={"key": "k", "value": "v"},
            headers={"Authorization": f"Bearer {atok}", "X-PW-StepUp": "1"},
        )
        assert r2.status_code == 403

    def test_agent_step_up_error_names_the_boundary(self, tmp_path, monkeypatch):
        from personal_world.api import create_app

        monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
        monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
        monkeypatch.setenv("PW_IDENTITY_MODE", "multi")
        monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
        c = TestClient(create_app(tmp_path, tmp_path))
        admin = {"Authorization": "Bearer instancetoken"}
        atok = c.post(
            "/api/identity/agents",
            json={"agent_id": "bot", "scopes": ["write"]},
            headers=admin,
        ).json()["data"]["token"]
        r = c.post(
            "/api/world/intent",
            json={"key": "k", "value": "v"},
            headers={"Authorization": f"Bearer {atok}", "X-PW-StepUp": "1"},
        )
        assert "person-only" in r.json()["detail"]
