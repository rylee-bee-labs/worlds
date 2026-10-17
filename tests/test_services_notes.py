"""Services registry (/api/apps) and journal note composer (POST /api/journal)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402


def _mk(tmp_path, monkeypatch):
    from personal_world.api import create_app

    monkeypatch.setenv("PW_API_TOKEN", "tttttttt")
    app = create_app(tmp_path, tmp_path)
    return TestClient(app), tmp_path


def _headers():
    return {"Authorization": "Bearer tttttttt"}


def test_apps_empty_by_default(tmp_path, monkeypatch):
    c, _ = _mk(tmp_path, monkeypatch)
    r = c.get("/api/apps", headers=_headers())
    assert r.status_code == 200
    assert r.json()["data"] == []


def test_apps_put_then_get(tmp_path, monkeypatch):
    c, _ = _mk(tmp_path, monkeypatch)
    body = {"apps": [{"id": "gitea", "name": "Gitea", "url": "https://example.com"}]}
    r = c.put("/api/apps", json=body, headers=_headers())
    assert r.status_code == 200, r.text
    r2 = c.get("/api/apps", headers=_headers())
    assert r2.json()["data"][0]["name"] == "Gitea"


def test_apps_put_requires_list(tmp_path, monkeypatch):
    c, _ = _mk(tmp_path, monkeypatch)
    r = c.put("/api/apps", json={"apps": "nope"}, headers=_headers())
    assert r.status_code == 422


def test_journal_note_writes(tmp_path, monkeypatch):
    c, _ = _mk(tmp_path, monkeypatch)
    r = c.post("/api/journal", json={"text": "a small win today"}, headers=_headers())
    assert r.status_code == 200, r.text
    r2 = c.get("/api/journal", headers=_headers())
    texts = [e.get("summary") for e in r2.json()["data"]]
    assert "a small win today" in texts


def test_journal_note_rejects_empty(tmp_path, monkeypatch):
    c, _ = _mk(tmp_path, monkeypatch)
    r = c.post("/api/journal", json={"text": ""}, headers=_headers())
    assert r.status_code == 422
