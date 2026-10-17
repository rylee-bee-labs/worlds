"""The dev server: loopback refusal, and the Memory + Connect routes it now serves.

These build the same app the dev entrypoint builds, but in-process, so the live browser tests have a
backend contract to rely on: Memory Kept/Find work, Connect Try goes to the reference provider, and a
write-like Connect try is refused without ever reaching the network.
"""
import pytest
from fastapi.testclient import TestClient

from personal_world.worlds.dev import DEV_TOKEN, assert_loopback, build_dev_app
from personal_world.worlds.reference_provider import ReferenceServer


def test_dev_server_refuses_non_loopback():
    assert_loopback("127.0.0.1")
    assert_loopback("::1")
    for host in ("0.0.0.0", "::", "localhost", "example.com", ""):
        with pytest.raises(SystemExit):
            assert_loopback(host)


@pytest.fixture
def dev(tmp_path):
    """The dev app in-process, seeded, with the reference provider running."""
    with ReferenceServer(token=DEV_TOKEN) as reference:
        app, _created = build_dev_app(tmp_path, reference)
        # base_url 127.0.0.1 is required: the dev HostGuard allows only loopback names.
        yield TestClient(app, base_url="http://127.0.0.1"), reference


def test_dev_server_keeps_and_finds_memory(dev):
    client, _ = dev
    created = client.post("/api/memory/kept", json={"title": "Dev kept", "body": "a findable body"})
    assert created.status_code == 200, created.text
    assert created.json()["title"] == "Dev kept"

    found = client.get("/api/memory/find", params={"q": "findable"})
    assert found.status_code == 200, found.text
    assert any(row["title"] == "Dev kept" for row in found.json())


def test_dev_server_tries_connect_against_the_reference(dev):
    client, reference = dev
    r = client.post("/api/connect/try", json={"provider": "reference", "request": {"path": "/status"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["status_code"] == 200 and body["error_class"] is None
    assert reference.calls_to("/status") == 1  # it really went to the reference server, once


def test_dev_server_refuses_a_connect_write(dev):
    client, reference = dev
    r = client.post("/api/connect/try", json={"provider": "reference", "request": {"method": "POST", "path": "/write"}})
    assert r.status_code == 422, r.text
    assert r.json()["detail"] == "test write actions through an approved action"
    assert reference.calls == []  # refused before the seam, nothing sent
