"""Journal correction/supersede workflow (second propose→approve→act
workflow). Append-only truth: the original entry is never rewritten;
currency is derived from supersedes links. Every test proves both the
happy path and the honesty of the failure/idempotency edges."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.journal import Journal  # noqa: E402
from personal_world.model import JournalKind  # noqa: E402


@pytest.fixture
def journal(tmp_path):
    return Journal(tmp_path / "journal.ndjson")


class TestJournalCore:
    def test_supersede_preserves_original_and_makes_new_current(self, journal):
        a = journal.record(JournalKind.OBSERVATION, "original text", source="user")
        current, audit = journal.supersede(a.ts, "corrected text", "typo")
        assert current.summary == "corrected text"
        assert current.supersedes == a.ts
        assert current.supersede_reason == "typo"
        # Original row is untouched and still in the log.
        raw = (journal.path).read_text().splitlines()
        assert sum(1 for line in raw if "original text" in line) == 1
        # Calm view shows only the corrected entry.
        view = journal.current_events(20)
        assert [e.summary for e in view if e.kind == JournalKind.OBSERVATION] == [
            "corrected text"
        ]
        # Audit answers the required questions.
        assert audit.kind == JournalKind.APPROVAL
        assert a.ts.isoformat() in audit.summary
        assert current.ts.isoformat() in audit.summary
        assert "approved by the owner" in audit.summary
        assert "typo" in audit.summary

    def test_chain_a_to_b_to_c_linear(self, journal):
        a = journal.record(JournalKind.OBSERVATION, "v1", source="user")
        b, _ = journal.supersede(a.ts, "v2", None)
        c, _ = journal.supersede(b.ts, "v3", None)
        chain = journal.history_of(c)
        assert [e.summary for e in chain] == ["v1", "v2", "v3"]
        view = journal.current_events(20)
        assert [e.summary for e in view if e.kind == JournalKind.OBSERVATION] == ["v3"]

    def test_double_supersede_rejected(self, journal):
        a = journal.record(JournalKind.OBSERVATION, "v1", source="user")
        journal.supersede(a.ts, "v2", None)
        with pytest.raises(ValueError):
            journal.supersede(a.ts, "v2-different", None)

    def test_missing_target_raises(self, journal):
        with pytest.raises(KeyError):
            journal.supersede("1999-01-01T00:00:00+00:00", "x", None)


class TestSupersedeEndpoint:
    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        from personal_world.api import create_app

        monkeypatch.setenv("PW_API_TOKEN", "t")
        app = create_app(tmp_path, tmp_path)
        c = TestClient(app)
        # Seed one entry through the real note endpoint.
        r = c.post(
            "/api/journal", json={"text": "original note"}, headers=self._headers()
        )
        assert r.status_code == 200
        return c, tmp_path

    def _headers(self):
        return {"Authorization": "Bearer t"}

    def _first_ts(self, tmp_path):
        j = Journal(tmp_path / "journal.ndjson")
        return j.recent(1)[0].ts.isoformat()

    def test_supersede_full_path(self, client):
        c, tmp = client
        ts = self._first_ts(tmp)
        r = c.post(
            "/api/journal/supersede",
            json={"supersedes": ts, "text": "corrected note", "reason": "typo"},
            headers=self._headers(),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["current"]["summary"] == "corrected note"
        assert body["data"]["superseded"]["summary"] == "original note"
        assert body["data"]["already_applied"] is False
        # The calm GET view shows the correction as current.
        view = c.get("/api/journal?n=20", headers=self._headers()).json()["data"]
        obs = [e for e in view if e["kind"] == "observation"]
        assert [e["summary"] for e in obs] == ["corrected note"]
        # History chain exposes the original.
        cur_ts = body["data"]["current"]["ts"]
        hist = c.get(
            f"/api/journal/history?ts={cur_ts}", headers=self._headers()
        ).json()["data"]["entries"]
        assert [e["summary"] for e in hist] == ["original note", "corrected note"]

    def test_idempotent_retry_does_not_duplicate(self, client):
        c, tmp = client
        ts = self._first_ts(tmp)
        payload = {"supersedes": ts, "text": "corrected note", "reason": "typo"}
        first = c.post(
            "/api/journal/supersede", json=payload, headers=self._headers()
        ).json()
        second = c.post(
            "/api/journal/supersede", json=payload, headers=self._headers()
        ).json()
        assert first["data"]["already_applied"] is False
        assert second["data"]["already_applied"] is True
        assert second["data"]["current"]["ts"] == first["data"]["current"]["ts"]
        # Exactly one corrected entry in the log.
        j = Journal(tmp / "journal.ndjson")
        corrected = [e for e in j.events() if e.summary == "corrected note"]
        assert len(corrected) == 1

    def test_conflicting_second_correction_is_honest_failure(self, client):
        c, tmp = client
        ts = self._first_ts(tmp)
        r1 = c.post(
            "/api/journal/supersede",
            json={"supersedes": ts, "text": "first correction"},
            headers=self._headers(),
        ).json()
        assert r1["ok"] is True
        # Different text against the SAME (now superseded) target.
        r2 = c.post(
            "/api/journal/supersede",
            json={"supersedes": ts, "text": "other correction"},
            headers=self._headers(),
        ).json()
        assert r2["ok"] is False
        assert r2["status"] == "unavailable"
        # Original truth unchanged by the failed attempt.
        view = c.get("/api/journal?n=20", headers=self._headers()).json()["data"]
        obs = [e for e in view if e["kind"] == "observation"]
        assert [e["summary"] for e in obs] == ["first correction"]

    def test_garbage_supersedes_not_configured_not_500(self, client):
        c, tmp = client
        r = c.post(
            "/api/journal/supersede",
            json={"supersedes": "totally-not-a-timestamp", "text": "x"},
            headers=self._headers(),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "not_configured"

    def test_garbage_history_ts_not_configured_not_500(self, client):
        c, tmp = client
        r = c.get("/api/journal/history?ts=garbage", headers=self._headers())
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "not_configured"

    def test_missing_entry_is_not_configured_and_changes_nothing(self, client):
        c, tmp = client
        r = c.post(
            "/api/journal/supersede",
            json={"supersedes": "1999-01-01T00:00:00+00:00", "text": "x"},
            headers=self._headers(),
        ).json()
        assert r["ok"] is False
        assert r["status"] == "not_configured"
        view = c.get("/api/journal?n=20", headers=self._headers()).json()["data"]
        obs = [e for e in view if e["kind"] == "observation"]
        assert [e["summary"] for e in obs] == ["original note"]

    def test_auth_required(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        from personal_world.api import create_app

        monkeypatch.setenv("PW_API_TOKEN", "t")
        c = TestClient(create_app(tmp_path, tmp_path))
        r = c.post("/api/journal/supersede", json={"supersedes": "x", "text": "y"})
        assert r.status_code in (401, 503)

    def test_validation_requires_fields(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        from personal_world.api import create_app

        monkeypatch.setenv("PW_API_TOKEN", "t")
        c = TestClient(create_app(tmp_path, tmp_path))
        r = c.post(
            "/api/journal/supersede",
            json={"text": "y"},
            headers={"Authorization": "Bearer t"},
        )
        assert r.status_code == 422

    def test_repeat_correction_of_the_corrected_entry(self, client):
        c, tmp = client
        ts = self._first_ts(tmp)
        r1 = c.post(
            "/api/journal/supersede",
            json={"supersedes": ts, "text": "second version"},
            headers=self._headers(),
        ).json()
        cur = r1["data"]["current"]["ts"]
        r2 = c.post(
            "/api/journal/supersede",
            json={"supersedes": cur, "text": "third version"},
            headers=self._headers(),
        ).json()
        assert r2["ok"] is True
        hist = c.get(
            f"/api/journal/history?ts={r2['data']['current']['ts']}",
            headers=self._headers(),
        ).json()["data"]["entries"]
        assert [e["summary"] for e in hist] == [
            "original note",
            "second version",
            "third version",
        ]
