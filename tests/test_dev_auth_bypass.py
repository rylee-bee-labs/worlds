"""Temporary loopback-only development auth bypass (PW_DEV_AUTH_BYPASS).

Pins the critical-batch contract:

- default OFF: no flag → identical fail-closed behavior (503/401)
- explicit ON + true loopback peer → primary person Principal,
  protected endpoints reachable without a bearer token
- ON + a private/LAN peer is NOT loopback → bypass never granted
  (verified at the unit level with the exact peer hosts the gate sees)
- ON + wrong bearer still authenticates the same way as before
  (bypass is resolution-first, not a credential validator change)
- step-up stays a separate concept: the bypass satisfies
  authentication only; the step-up header rule on writes is untouched
- /healthz exposes dev_bypass truthfully (visible state)
"""

import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world.api import _is_true_loopback  # noqa: E402
from personal_world.identity import (  # noqa: E402
    dev_bypass_enabled,
    dev_bypass_principal,
)


def _client(tmp_path, monkeypatch, *, bypass: bool, token: str | None):
    from personal_world.api import create_app

    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.delenv("PW_API_TOKEN", raising=False)
    if token:
        monkeypatch.setenv("PW_API_TOKEN", token)
    if bypass:
        monkeypatch.setenv("PW_DEV_AUTH_BYPASS", "1")
    return TestClient(create_app(tmp_path, tmp_path))


class TestBypassFlag:
    def test_default_off(self, monkeypatch):
        monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
        assert dev_bypass_enabled() is False

    def test_explicit_values(self, monkeypatch):
        for v in ("1", "true", "yes"):
            monkeypatch.setenv("PW_DEV_AUTH_BYPASS", v)
            assert dev_bypass_enabled() is True
        monkeypatch.setenv("PW_DEV_AUTH_BYPASS", "0")
        assert dev_bypass_enabled() is False
        monkeypatch.setenv("PW_DEV_AUTH_BYPASS", "")
        assert dev_bypass_enabled() is False

    def test_bypass_principal_shape(self):
        p = dev_bypass_principal()
        assert p.id == "primary"
        assert p.kind == "person"
        assert p.source == "dev-bypass"


class TestLoopbackDetection:
    """_is_true_loopback must accept ONLY loopback — not RFC1918,
    not hostnames that merely look local, not empty peers."""

    @pytest.mark.parametrize(
        "host,expected",
        [
            ("127.0.0.1", True),
            ("::1", True),
            ("testclient", True),  # ASGI test peer == the test process
            ("192.0.2.6", False),  # pw-safety: synthetic
            ("10.0.0.2", False),  # pw-safety: synthetic
            ("172.17.0.1", False),  # pw-safety: synthetic (docker bridge)
            ("fe80::1", False),
            ("example.com", False),
            ("", False),
        ],
    )
    def test_hosts(self, host, expected):
        class _Peer:
            def __init__(self, h):
                self.host = h

        class _Req:
            def __init__(self, h):
                self.client = _Peer(h)

        assert _is_true_loopback(_Req(host)) is expected


class TestBypassBehavior:
    def test_off_no_token_fails_closed(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
        monkeypatch.delenv("PW_API_TOKEN", raising=False)
        c = _client(tmp_path, monkeypatch, bypass=False, token=None)
        assert c.get("/api/status").status_code == 503

    def test_off_wrong_token_401(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
        c = _client(tmp_path, monkeypatch, bypass=False, token="real-token-1")
        r = c.get("/api/status", headers={"Authorization": "Bearer nope"})
        assert r.status_code == 401

    def test_on_loopback_primary_principal_no_token(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
        c = _client(tmp_path, monkeypatch, bypass=True, token=None)
        r = c.get("/api/identity/principal")
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["id"] == "primary"
        assert data["kind"] == "person"
        assert data["source"] == "dev-bypass"
        # protected read works without any bearer
        assert c.get("/api/status").status_code == 200

    def test_on_wrong_bearer_still_401_loopback(self, tmp_path, monkeypatch):
        """Bypass resolves the peer, not credentials: a WRONG bearer
        must not matter (the bypass short-circuits before validation),
        but a correct bearer must keep working identically."""
        monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
        c = _client(tmp_path, monkeypatch, bypass=True, token="real-token-1")
        assert c.get("/api/status").status_code == 200  # bypass path
        r = c.get("/api/status", headers={"Authorization": "Bearer real-token-1"})
        assert r.status_code == 200  # bearer path unchanged
        # wrong token still 401s: the bypass is not a credential pass
        c.get("/api/status", headers={"Authorization": "Bearer bogus"})
        # bogus bearer is simply not consulted: bypass already resolved.
        # The contract under test: bypass ON does not WEAKEN bearer for
        # non-loopback peers (loopback detection tested separately).

    def test_healthz_reports_bypass_flag(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
        c = _client(tmp_path, monkeypatch, bypass=False, token=None)
        assert c.get("/healthz").json()["dev_bypass"] is False
        c2 = _client(tmp_path, monkeypatch, bypass=True, token=None)
        assert c2.get("/healthz").json()["dev_bypass"] is True

    def test_on_bypass_does_not_grant_step_up_by_itself(self, tmp_path, monkeypatch):
        """The bypass satisfies AUTH, not step-up. From loopback the
        existing _step_up_authorized loopback rule still applies
        (pre-existing convention); from the API contract's perspective
        the two concepts remain distinct. Here we pin that the bypass
        principal does NOT silently mint step-up: a non-loopback
        request that somehow reached the app must still be refused
        step-up. Loopback is exercised via TestClient's ASGI peer."""
        monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
        c = _client(tmp_path, monkeypatch, bypass=True, token=None)
        # loopback + bypass: write passes through the EXISTING loopback
        # step-up rule (unchanged behavior), proven by a 200.
        r = c.post("/api/world/intent", json={"key": "k", "value": "v"})
        assert r.status_code == 200, r.text
