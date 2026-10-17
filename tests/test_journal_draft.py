"""Journal drafts — the lining rescue contract (D15: kept safe, synced).

Pins the three promises the draft endpoint exists for: it saves (so the
world can resume across devices), it never echoes draft text back in write
responses, and clearing works — plus honest auth on every verb.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world.api import create_app  # noqa: E402
from personal_world.init import init_world  # noqa: E402

AUTH = {"Authorization": "Bearer drafttoken"}


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("PW_API_TOKEN", "drafttoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok")
    return TestClient(create_app(tmp_path, tmp_path))


class TestDrafts:
    def test_auth_required_on_every_verb(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        assert c.put("/api/journal/draft", json={"text": "x"}).status_code == 401
        assert c.get("/api/journal/draft").status_code == 401
        assert c.delete("/api/journal/draft").status_code == 401

    def test_put_then_get_roundtrip(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        r = c.put("/api/journal/draft", json={"text": "half a thought…", "device": "tablet"},
                  headers=AUTH)
        assert r.status_code == 200
        # THE contract: the write response reports, never echoes
        assert "half a thought" not in r.text
        assert r.json()["data"]["length"] == len("half a thought…")
        g = c.get("/api/journal/draft", headers=AUTH).json()["data"]
        assert g["text"] == "half a thought…"
        assert g["device"] == "tablet"

    def test_empty_state_is_honest(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        g = c.get("/api/journal/draft", headers=AUTH).json()["data"]
        assert g["text"] is None and g["updated_at"] is None

    def test_oversize_is_422_without_echo(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        big = "z" * 100_001
        r = c.put("/api/journal/draft", json={"text": big}, headers=AUTH)
        assert r.status_code == 422
        assert "zzz" not in r.text

    def test_delete_clears(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        c.put("/api/journal/draft", json={"text": "temp"}, headers=AUTH)
        assert c.delete("/api/journal/draft", headers=AUTH).status_code == 200
        assert c.get("/api/journal/draft", headers=AUTH).json()["data"]["text"] is None

    def test_storage_rides_the_scoped_seam(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        c.put("/api/journal/draft", json={"text": "somewhere safe"}, headers=AUTH)
        hits = list(tmp_path.rglob("journal-draft.json"))
        assert len(hits) == 1
        assert hits[0].stat().st_mode & 0o777 == 0o600  # personal data, private bits
