"""Whole-instance backup and restore belong to the owner and admins.

The three routes (create, one-time download, restore) already need a
step-up; these tests pin the second condition, that the caller is the
owner or an admin, for every caller kind, with and without elevation, and
that a refused caller neither creates nor uses a one-time download link.
"""

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

pytest.importorskip("cryptography")

OWNER_TOKEN = "instancetoken"  # pw-safety: synthetic
PASSPHRASE = "correct horse battery staple"  # pw-safety: synthetic
OWNER = {"Authorization": f"Bearer {OWNER_TOKEN}"}


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    import personal_world.api as api_mod
    from personal_world.api import create_app

    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.delenv("PW_PROXY_STEPUP_SECRET", raising=False)
    monkeypatch.setenv("PW_API_TOKEN", OWNER_TOKEN)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("PW_IDENTITY_MODE", "multi")
    client = TestClient(create_app(tmp_path, tmp_path))

    def provision(user_id, role=None):
        r = client.post(
            "/api/identity/users",
            json={"user_id": user_id, "display_name": "Made up person"},
            headers=OWNER,
        )
        assert r.status_code == 200, r.text
        if role:
            assert (
                client.put(
                    f"/api/people/{user_id}/role", json={"role": role}, headers=OWNER
                ).status_code
                == 200
            )
        return r.json()["data"]["token"]

    def agent():
        r = client.post(
            "/api/identity/agents",
            json={"agent_id": "helper-bot", "scopes": ["read", "write"]},
            headers=OWNER,
        )
        assert r.status_code == 200, r.text
        return r.json()["data"]["token"]

    # The test peer counts as local, so elevation is on by default; the
    # "not elevated" cases switch it off explicitly.
    def elevated(on):
        monkeypatch.setattr(api_mod, "_is_true_loopback", lambda request: on)

    elevated(True)
    return client, provision, agent, elevated


def _archive_body(client):
    r = client.post(
        "/api/worlds/backup",
        headers=OWNER,
        json={"passphrase": PASSPHRASE, "include_vault": True},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _restore(client, headers, archive=b"not-an-archive"):
    return client.post(
        "/api/worlds/restore",
        headers=headers,
        json={
            "passphrase": PASSPHRASE,
            "archive_b64": base64.b64encode(archive).decode(),
        },
    )


@pytest.mark.parametrize("role", ["member", "supervised", "guest"])
@pytest.mark.parametrize("elevated_on", [True, False])
def test_members_and_below_are_refused_all_three_routes(env, role, elevated_on):
    client, provision, _agent, elevated = env
    token = provision(f"person-{role}", role)
    elevated(elevated_on)
    h = _h(token)
    assert client.post(
        "/api/worlds/backup", headers=h, json={"passphrase": PASSPHRASE}
    ).status_code == 403
    assert client.get("/api/worlds/backup/download/anything", headers=h).status_code == 403
    assert _restore(client, h).status_code == 403


@pytest.mark.parametrize("elevated_on", [True, False])
def test_agents_are_refused_all_three_routes(env, elevated_on):
    client, _provision, agent, elevated = env
    token = agent()
    elevated(elevated_on)
    h = _h(token)
    assert client.post(
        "/api/worlds/backup", headers=h, json={"passphrase": PASSPHRASE}
    ).status_code == 403
    assert client.get("/api/worlds/backup/download/anything", headers=h).status_code == 403
    assert _restore(client, h).status_code == 403


def test_owner_without_elevation_is_still_refused(env):
    client, _p, _a, elevated = env
    elevated(False)
    r = client.post(
        "/api/worlds/backup", headers=OWNER, json={"passphrase": PASSPHRASE}
    )
    assert r.status_code == 403


def test_owner_still_gets_a_full_backup(env):
    client, *_ = env
    body = _archive_body(client)
    assert body["vault_included"] is True
    assert body["one_time"] is True


def test_refused_caller_does_not_consume_the_one_time_link(env):
    client, provision, _a, _e = env
    body = _archive_body(client)
    link = body["download"]
    token = provision("person-member", "member")
    assert client.get(link, headers=_h(token)).status_code == 403
    # The owner's link is still there: the refusal did not pop it.
    got = client.get(link, headers=OWNER)
    assert got.status_code == 200, got.text
    assert client.get(link, headers=OWNER).status_code == 404


def test_admin_gets_a_backup_and_may_download_it(env):
    client, provision, _a, elevated = env
    token = provision("person-admin", "admin")
    h = _h(token)
    r = client.post(
        "/api/worlds/backup",
        headers=h,
        json={"passphrase": PASSPHRASE, "include_vault": True},
    )
    assert r.status_code == 200, r.text
    assert client.get(r.json()["download"], headers=h).status_code == 200
    elevated(False)
    assert client.post(
        "/api/worlds/backup", headers=h, json={"passphrase": PASSPHRASE}
    ).status_code == 403
