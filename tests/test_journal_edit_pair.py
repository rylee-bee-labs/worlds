"""Journal edit-pair capture v0 (B5; DRAFT-SYNC-SPEC §capture lineage).

The capture ENDPOINT only — no UI yet. Mirrors test_journal_draft.py
because it is the same seam with the same promises: it stores (one
NDJSON line per BOT→Rylee edit pair, per principal), it never echoes
content back, the record carries exactly the nine fields Sol's review
adopted, and honest auth (require_auth + person-only) gates every call.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world.api import create_app  # noqa: E402
from personal_world.init import init_world  # noqa: E402

AUTH = {"Authorization": "Bearer pairtoken"}

PAIR = {
    "original": "The deployment finished successfully at 03:12.",
    "edited": "Deploy finished 03:12 — green.",
    "diff": "shortened, de-robotised",
    "timestamp": "2026-09-20T03:20:11Z",
    "message_kind": "status-update",
    "context": ["journal", "late-night"],
    "active_packs": ["plain-language-v0"],
    "warmth": 3,
    "model_provenance": "qwen3.8-flash",
}

NINE_FIELDS = {
    "original", "edited", "diff", "timestamp", "message_kind",
    "context", "active_packs", "warmth", "model_provenance",
}


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("PW_API_TOKEN", "pairtoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok")
    return TestClient(create_app(tmp_path, tmp_path))


def _lines(tmp_path):
    hits = list(tmp_path.rglob("journal-edit-pairs.ndjson"))
    assert len(hits) == 1, hits
    return [json.loads(line) for line in hits[0].read_text().splitlines() if line], hits[0]


class TestEditPairs:
    def test_auth_required(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        assert c.post("/api/journal/edit-pair", json=PAIR).status_code == 401

    def test_agent_principal_403_person_only(self, tmp_path, monkeypatch):
        """Capture is Rylee's own lining: agents are refused (fail
        closed, same rule as the vault's person-only reads)."""
        monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
        monkeypatch.setenv("PW_IDENTITY_MODE", "multi")
        monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
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
        r = c.post(
            "/api/journal/edit-pair", json=PAIR,
            headers={"Authorization": f"Bearer {agent_tok}"},
        )
        assert r.status_code == 403
        assert "person-only" in r.json()["detail"]

    def test_store_reports_stored_only(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        r = c.post("/api/journal/edit-pair", json=PAIR, headers=AUTH)
        assert r.status_code == 200
        # THE contract: the response is {stored:true} and nothing else.
        assert r.json()["data"] == {"stored": True}

    def test_never_echoes_content(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        r = c.post("/api/journal/edit-pair", json=PAIR, headers=AUTH)
        assert "deployment finished" not in r.text
        assert "de-robotised" not in r.text
        assert "qwen" not in r.text

    def test_record_carries_exactly_nine_fields(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        c.post("/api/journal/edit-pair", json=PAIR, headers=AUTH)
        records, _ = _lines(tmp_path)
        assert len(records) == 1
        assert set(records[0]) == NINE_FIELDS
        assert records[0]["original"] == PAIR["original"]
        assert records[0]["warmth"] == 3

    def test_minimal_pair_stays_honest(self, tmp_path, monkeypatch):
        """Only original+edited required; absent optionals are null/[]
        — never invented, and the nine fields are still exactly nine."""
        c = _client(tmp_path, monkeypatch)
        r = c.post(
            "/api/journal/edit-pair",
            json={"original": "robot says", "edited": "my words"},
            headers=AUTH,
        )
        assert r.status_code == 200
        records, _ = _lines(tmp_path)
        rec = records[0]
        assert set(rec) == NINE_FIELDS
        assert rec["diff"] is None and rec["message_kind"] is None
        assert rec["context"] == [] and rec["active_packs"] == []
        assert rec["warmth"] is None and rec["model_provenance"] is None
        # No client timestamp → the server stamps its own clock honestly.
        assert rec["timestamp"].endswith("Z")

    def test_original_and_edited_required(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        r = c.post("/api/journal/edit-pair", json={"original": "   "}, headers=AUTH)
        assert r.status_code == 422
        assert "   " not in r.text

    def test_oversize_is_422_without_echo(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        big = "z" * 20_001
        r = c.post(
            "/api/journal/edit-pair",
            json={"original": big, "edited": "ok"},
            headers=AUTH,
        )
        assert r.status_code == 422
        assert "zzz" not in r.text

    def test_warmth_must_be_one_to_seven(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        for bad in (0, 8, "3", True, 3.5):
            body = {**PAIR, "warmth": bad}
            r = c.post("/api/journal/edit-pair", json=body, headers=AUTH)
            assert r.status_code == 422, f"warmth={bad!r} accepted"

    def test_tag_lists_must_be_arrays_bounded(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        r = c.post(
            "/api/journal/edit-pair", json={**PAIR, "context": "not-a-list"},
            headers=AUTH,
        )
        assert r.status_code == 422
        r = c.post(
            "/api/journal/edit-pair", json={**PAIR, "active_packs": ["p"] * 33},
            headers=AUTH,
        )
        assert r.status_code == 422

    def test_appends_in_order_one_line_each(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        c.post("/api/journal/edit-pair", json={**PAIR, "edited": "first"}, headers=AUTH)
        c.post("/api/journal/edit-pair", json={**PAIR, "edited": "second"}, headers=AUTH)
        records, _ = _lines(tmp_path)
        assert [r["edited"] for r in records] == ["first", "second"]

    def test_storage_rides_the_scoped_seam(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        c.post("/api/journal/edit-pair", json=PAIR, headers=AUTH)
        _, path = _lines(tmp_path)
        assert path.stat().st_mode & 0o777 == 0o600  # personal data, private bits

    def test_bad_body_is_400(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        r = c.post(
            "/api/journal/edit-pair",
            content=b"not json",
            headers={**AUTH, "Content-Type": "application/json"},
        )
        assert r.status_code == 400
