"""Vault endpoint contract (issue #15): true-loopback-only, person-only
read of a secret value with name-only journal audits. Values never render
in exports or chat context.

TestClient requests carry client.host == "testclient" — accepted as the
ASGI test peer (the test process itself, loopback by construction),
matching api._is_true_loopback. A remote peer (RFC1918/Docker bridge
included) and an agent principal are both refused: secret-value
extraction is a local, human-owner operation only.
"""

import json  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world.vault import _HAS_CRYPTO  # noqa: E402


def _mk(tmp_path, monkeypatch):
    """Deployed app on tmp dirs; token bypass; yields bound client."""
    from personal_world.api import create_app

    monkeypatch.setenv("PW_API_TOKEN", "tttttttt")
    app = create_app(tmp_path, tmp_path)
    return TestClient(app), tmp_path


def _headers():
    return {"Authorization": "Bearer tttttttt"}


def test_get_409_when_locked(tmp_path, monkeypatch):
    c, _ = _mk(tmp_path, monkeypatch)
    r = c.get("/api/vault/k", headers=_headers())
    assert r.status_code == 409
    assert "locked" in r.json()["detail"]


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_get_after_unlock(tmp_path, monkeypatch):
    c, _ = _mk(tmp_path, monkeypatch)
    c.post(
        "/api/setup",
        json={"token": "tttttttt", "vault_passphrase": "pp"},
        headers=_headers(),
    )
    r = c.post("/api/vault/set", json={"name": "k", "value": "v"}, headers=_headers())
    assert r.status_code == 200, r.text
    r = c.get("/api/vault/k", headers=_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] and body["data"]["value"] == "v"
    # journal has name-only vault-get observation
    jr = c.get("/api/journal", headers=_headers()).json()
    assert "vault get" in json.dumps(jr)


def test_remote_client_403(tmp_path, monkeypatch):
    """A non-loopback peer (RFC1918/Docker bridge included) is refused
    even with a valid bearer: the vault guard is true-loopback only."""
    monkeypatch.setenv("PW_API_TOKEN", "tttttttt")
    from personal_world.api import create_app

    c = TestClient(
        create_app(tmp_path, tmp_path), client=("172.20.0.5", 5555)  # pw-safety: synthetic
    )  # pw-safety: synthetic
    r = c.get("/api/vault/k", headers=_headers())
    assert r.status_code == 403
    assert "loopback-only" in r.json()["detail"]


def test_true_loopback_predicate_matches_api_helper():
    """The vault guard reuses api._is_true_loopback: bridge/LAN hosts
    are NOT local; loopback and the ASGI test peer are."""
    from personal_world.api import _is_true_loopback

    class _Peer:
        def __init__(self, host):
            self.host = host

    class _Req:
        def __init__(self, host):
            self.client = _Peer(host)

    assert _is_true_loopback(_Req("127.0.0.1")) is True
    assert _is_true_loopback(_Req("::1")) is True
    assert _is_true_loopback(_Req("testclient")) is True
    assert _is_true_loopback(_Req("172.20.0.5")) is False  # pw-safety: synthetic
    assert _is_true_loopback(_Req("192.0.2.6")) is False  # pw-safety: synthetic


@pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
def test_missing_name_404_after_unlock(tmp_path, monkeypatch):
    c, _ = _mk(tmp_path, monkeypatch)
    c.post(
        "/api/setup",
        json={"token": "tttttttt", "vault_passphrase": "pp"},
        headers=_headers(),
    )
    r = c.get("/api/vault/void", headers=_headers())
    assert r.status_code == 404


def test_agent_principal_403_person_only(tmp_path, monkeypatch):
    """An agent principal is refused even on loopback: secret-value
    reads are person-only (fail closed, even for a 409-locked vault —
    the person gate runs before any vault access)."""
    monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", "multi")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    from personal_world.api import create_app

    c = TestClient(create_app(tmp_path, tmp_path))
    tok = {"Authorization": "Bearer instancetoken"}
    r = c.post("/api/identity/users", json={"user_id": "beta"}, headers=tok)
    assert r.status_code == 200, r.text
    tok_b = r.json()["data"]["token"]
    r = c.post(
        "/api/identity/agents",
        json={"agent_id": "bot", "scopes": ["read"]},
        headers={"Authorization": f"Bearer {tok_b}", "X-PW-StepUp": "1"},
    )
    assert r.status_code == 200, r.text
    agent_tok = r.json()["data"]["token"]
    r = c.get("/api/vault/k", headers={"Authorization": f"Bearer {agent_tok}"})
    assert r.status_code == 403
    assert "person-only" in r.json()["detail"]


def test_setup_graceful_without_crypto(tmp_path, monkeypatch):
    """Setup succeeds even if vault init fails (no crypto)."""
    from personal_world.vault import _HAS_CRYPTO

    c, _ = _mk(tmp_path, monkeypatch)
    r = c.post(
        "/api/setup",
        json={"token": "tttttttt", "vault_passphrase": "pp"},
        headers=_headers(),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"]
    assert body["data"]["token_set"] is True
    # vault_initialized reflects actual crypto availability
    assert body["data"]["vault_initialized"] == _HAS_CRYPTO
