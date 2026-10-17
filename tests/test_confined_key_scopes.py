"""A key with a confining scope reaches only that scope's routes, even
when it also carries an ordinary scope such as "read"."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

TOKEN = "instancetoken"  # pw-safety: synthetic
OWNER = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def make_key(tmp_path, monkeypatch):
    from personal_world.api import create_app

    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("PW_API_TOKEN", TOKEN)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    client = TestClient(create_app(tmp_path, tmp_path))
    n = {"i": 0}

    def make(scopes):
        n["i"] += 1
        r = client.post(
            "/api/identity/agents",
            json={"agent_id": f"key-{n['i']}", "scopes": scopes},
            headers=OWNER,
        )
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['data']['token']}"}

    return client, make


def test_plain_read_key_is_unchanged(make_key):
    client, make = make_key
    assert client.get("/api/manifest", headers=make(["read"])).status_code == 200


@pytest.mark.parametrize(
    "scopes",
    [["learning"], ["read", "learning"], ["write", "read", "learning"]],
)
def test_learning_key_stays_on_its_route(make_key, scopes):
    client, make = make_key
    h = make(scopes)
    r = client.get("/api/manifest", headers=h)
    assert r.status_code == 403 and "own routes" in r.text
    assert client.get("/api/crew", headers=h).status_code == 403
    assert "own routes" not in client.get("/api/learning", headers=h).text


def test_journal_gate_key_with_read_stays_on_its_route(make_key):
    client, make = make_key
    h = make(["journal_gate", "read"])
    assert client.get("/api/manifest", headers=h).status_code == 403
