"""Journal gate route + scope wiring (step 3-4 of the journal-gate
design, 2026-09-27). Proves the isolation property end to end over
real HTTP: a token holding ONLY the ``journal_gate`` scope reaches the
gate and nothing else; the existing hard wall on /api/journal and
/api/recall stays exactly as strict as before for every agent,
scoped or not.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world.api import create_app  # noqa: E402
from personal_world.init import init_world  # noqa: E402


def _multi_client(tmp_path, monkeypatch):
    monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", "multi")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok")
    return TestClient(create_app(tmp_path, tmp_path))


def _make_user_and_agent(c, scopes):
    tok = {"Authorization": "Bearer instancetoken"}
    r = c.post("/api/identity/users", json={"user_id": "beta"}, headers=tok)
    assert r.status_code == 200, r.text
    user_tok = r.json()["data"]["token"]
    r = c.post(
        "/api/identity/agents",
        json={"agent_id": "gatebot", "scopes": scopes},
        headers={"Authorization": f"Bearer {user_tok}", "X-PW-StepUp": "1"},
    )
    assert r.status_code == 200, r.text
    return user_tok, r.json()["data"]["token"]


ASK = {"ask": "relates_to", "topic": "rent argument", "window_days": 7}


class TestGateAuth:
    def test_auth_required(self, tmp_path, monkeypatch):
        c = _multi_client(tmp_path, monkeypatch)
        assert c.post("/api/journal/gate", json=ASK).status_code == 401

    def test_person_can_ask(self, tmp_path, monkeypatch):
        c = _multi_client(tmp_path, monkeypatch)
        user_tok, _ = _make_user_and_agent(c, ["journal_gate"])
        r = c.post(
            "/api/journal/gate", json=ASK, headers={"Authorization": f"Bearer {user_tok}"}
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert set(data.keys()) == {"answer", "strength", "when", "count"}
        assert data["answer"] in ("yes", "no", "unsure")


class TestScopeIsolation:
    def test_journal_gate_scoped_agent_can_ask(self, tmp_path, monkeypatch):
        c = _multi_client(tmp_path, monkeypatch)
        _, agent_tok = _make_user_and_agent(c, ["journal_gate"])
        r = c.post(
            "/api/journal/gate", json=ASK, headers={"Authorization": f"Bearer {agent_tok}"}
        )
        assert r.status_code == 200, r.text
        assert set(r.json()["data"].keys()) == {"answer", "strength", "when", "count"}

    def test_journal_gate_scoped_agent_cannot_read_journal(self, tmp_path, monkeypatch):
        """The existing hard wall is untouched: this scope does not
        unlock /api/journal, only the gate."""
        c = _multi_client(tmp_path, monkeypatch)
        _, agent_tok = _make_user_and_agent(c, ["journal_gate"])
        headers = {"Authorization": f"Bearer {agent_tok}"}
        assert c.get("/api/journal", headers=headers).status_code == 403
        assert c.get("/api/journal/last", headers=headers).status_code == 403
        assert c.get("/api/journal/audit", headers=headers).status_code == 403

    def test_journal_gate_scoped_agent_cannot_read_recall(self, tmp_path, monkeypatch):
        c = _multi_client(tmp_path, monkeypatch)
        _, agent_tok = _make_user_and_agent(c, ["journal_gate"])
        r = c.get("/api/recall", params={"q": "rent argument"}, headers={"Authorization": f"Bearer {agent_tok}"})
        assert r.status_code == 403

    def test_journal_gate_scoped_agent_cannot_reach_other_confined_routes(self, tmp_path, monkeypatch):
        c = _multi_client(tmp_path, monkeypatch)
        _, agent_tok = _make_user_and_agent(c, ["journal_gate"])
        headers = {"Authorization": f"Bearer {agent_tok}"}
        assert c.get("/api/memory/search", params={"q": "x"}, headers=headers).status_code == 403
        assert c.post("/api/stickers/found", json={}, headers=headers).status_code in (403, 422, 404)

    def test_learning_scoped_agent_cannot_reach_gate(self, tmp_path, monkeypatch):
        """Confinement runs both directions: a token scoped to a
        DIFFERENT narrow door does not fall through to this one."""
        c = _multi_client(tmp_path, monkeypatch)
        _, agent_tok = _make_user_and_agent(c, ["learning"])
        r = c.post(
            "/api/journal/gate", json=ASK, headers={"Authorization": f"Bearer {agent_tok}"}
        )
        assert r.status_code == 403

    def test_full_person_journal_access_unaffected(self, tmp_path, monkeypatch):
        """Regression: adding the gate route/scope does not change
        ordinary person access to their own journal."""
        c = _multi_client(tmp_path, monkeypatch)
        user_tok, _ = _make_user_and_agent(c, ["journal_gate"])
        headers = {"Authorization": f"Bearer {user_tok}"}
        r = c.post("/api/journal", json={"text": "testing the gate did not break normal journaling"}, headers=headers)
        assert r.status_code == 200, r.text
        r = c.get("/api/journal", headers=headers)
        assert r.status_code == 200, r.text


class TestGateRateLimit:
    def test_rate_limit_returns_429_after_threshold(self, tmp_path, monkeypatch):
        c = _multi_client(tmp_path, monkeypatch)
        _, agent_tok = _make_user_and_agent(c, ["journal_gate"])
        headers = {"Authorization": f"Bearer {agent_tok}"}
        statuses = [
            c.post("/api/journal/gate", json=ASK, headers=headers).status_code
            for _ in range(25)
        ]
        assert 200 in statuses
        assert 429 in statuses


class TestModelMode:
    def test_defaults_to_mock_when_unconfigured(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PW_JOURNAL_GATE_MODEL_URL", raising=False)
        c = _multi_client(tmp_path, monkeypatch)
        user_tok, _ = _make_user_and_agent(c, ["journal_gate"])
        r = c.post(
            "/api/journal/gate", json=ASK, headers={"Authorization": f"Bearer {user_tok}"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["meta"]["model_mode"] == "mock"

    def test_real_model_used_when_configured(self, tmp_path, monkeypatch):
        from personal_world import journal_gate as jg

        class _FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                import json

                content = json.dumps(
                    {"answer": "no", "strength": None, "when": None, "count": "0"}
                )
                return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

        monkeypatch.setattr(jg._urlreq, "urlopen", lambda *a, **k: _FakeResp())
        monkeypatch.setenv("PW_JOURNAL_GATE_MODEL_URL", "http://example.invalid/v1")
        monkeypatch.setenv("PW_JOURNAL_GATE_MODEL_NAME", "test-model")
        c = _multi_client(tmp_path, monkeypatch)
        user_tok, _ = _make_user_and_agent(c, ["journal_gate"])
        r = c.post(
            "/api/journal/gate", json=ASK, headers={"Authorization": f"Bearer {user_tok}"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["meta"]["model_mode"] == "real"

    def test_real_model_endpoint_down_fails_closed_to_unsure(self, tmp_path, monkeypatch):
        from personal_world import journal_gate as jg

        def boom(*a, **k):
            raise jg._urlerr.URLError("connection refused")

        monkeypatch.setattr(jg._urlreq, "urlopen", boom)
        monkeypatch.setenv("PW_JOURNAL_GATE_MODEL_URL", "http://example.invalid/v1")
        c = _multi_client(tmp_path, monkeypatch)
        user_tok, _ = _make_user_and_agent(c, ["journal_gate"])
        r = c.post(
            "/api/journal", json={"text": "a rent argument day, resting"}, headers={"Authorization": f"Bearer {user_tok}"}
        )
        assert r.status_code == 200, r.text
        r = c.post(
            "/api/journal/gate", json=ASK, headers={"Authorization": f"Bearer {user_tok}"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["answer"] == "unsure"
        assert r.json()["meta"]["model_mode"] == "real"


class TestGateLog:
    def test_person_sees_structured_log_entry_after_ask(self, tmp_path, monkeypatch):
        c = _multi_client(tmp_path, monkeypatch)
        user_tok, _ = _make_user_and_agent(c, ["journal_gate"])
        headers = {"Authorization": f"Bearer {user_tok}"}
        c.post("/api/journal/gate", json=ASK, headers=headers)
        r = c.get("/api/journal/gate/log", headers=headers)
        assert r.status_code == 200, r.text
        entries = r.json()["data"]["entries"]
        assert len(entries) == 1
        row = entries[0]
        assert row["ask"] == "relates_to"
        assert row["topic"] == "rent argument"
        assert row["caller_id"].startswith("person:")
        assert "answer" in row

    def test_log_entries_do_not_leak_into_gate_retrieval(self, tmp_path, monkeypatch):
        """The audit trail itself must never become answerable content —
        otherwise asking about a topic would match its own past asks."""
        c = _multi_client(tmp_path, monkeypatch)
        user_tok, _ = _make_user_and_agent(c, ["journal_gate"])
        headers = {"Authorization": f"Bearer {user_tok}"}
        for _ in range(5):
            c.post("/api/journal/gate", json=ASK, headers=headers)
        r = c.post("/api/journal/gate", json=ASK, headers=headers)
        # If audit entries fed back into retrieval, 5 prior asks about the
        # exact same topic would eventually show as "yes" evidence even
        # with zero real journal content about it.
        assert r.json()["data"]["answer"] == "no"

    def test_agent_cannot_read_the_log(self, tmp_path, monkeypatch):
        c = _multi_client(tmp_path, monkeypatch)
        _, agent_tok = _make_user_and_agent(c, ["journal_gate"])
        r = c.get("/api/journal/gate/log", headers={"Authorization": f"Bearer {agent_tok}"})
        assert r.status_code == 403


class TestGateDenylistRoute:
    def test_person_can_view_and_set_denylist(self, tmp_path, monkeypatch):
        c = _multi_client(tmp_path, monkeypatch)
        user_tok, _ = _make_user_and_agent(c, ["journal_gate"])
        headers = {"Authorization": f"Bearer {user_tok}", "X-PW-StepUp": "1"}
        r = c.get("/api/journal/gate/denylist", headers=headers)
        assert r.status_code == 200
        assert r.json()["data"] == {"blocked_agents": [], "blocked_topics": []}
        r = c.put(
            "/api/journal/gate/denylist",
            json={"blocked_agents": [], "blocked_topics": ["rent argument"]},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        r = c.get("/api/journal/gate/denylist", headers={"Authorization": f"Bearer {user_tok}"})
        assert r.json()["data"]["blocked_topics"] == ["rent argument"]

    def test_denylisted_topic_forces_unsure_end_to_end(self, tmp_path, monkeypatch):
        c = _multi_client(tmp_path, monkeypatch)
        user_tok, agent_tok = _make_user_and_agent(c, ["journal_gate"])
        c.put(
            "/api/journal/gate/denylist",
            json={"blocked_agents": [], "blocked_topics": ["rent argument"]},
            headers={"Authorization": f"Bearer {user_tok}", "X-PW-StepUp": "1"},
        )
        r = c.post(
            "/api/journal/gate", json=ASK, headers={"Authorization": f"Bearer {agent_tok}"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["answer"] == "unsure"

    def test_agent_cannot_view_or_edit_denylist(self, tmp_path, monkeypatch):
        c = _multi_client(tmp_path, monkeypatch)
        _, agent_tok = _make_user_and_agent(c, ["journal_gate"])
        headers = {"Authorization": f"Bearer {agent_tok}"}
        assert c.get("/api/journal/gate/denylist", headers=headers).status_code == 403
        assert (
            c.put(
                "/api/journal/gate/denylist",
                json={"blocked_agents": [], "blocked_topics": []},
                headers=headers,
            ).status_code
            == 403
        )

    def test_denylist_write_requires_step_up(self, tmp_path, monkeypatch):
        """TestClient's peer is loopback (a documented local-owner
        exception), so step-up always passes over TestClient — the
        real check is structural, same pattern as test_sections.py's
        test_route_gates_are_declared."""
        c = _multi_client(tmp_path, monkeypatch)
        gates: dict[str, list[str]] = {}
        for route in c.app.routes:
            if getattr(route, "path", None) == "/api/journal/gate/denylist":
                for m in route.methods:
                    gates[m] = [d.dependency.__name__ for d in route.dependencies]
        assert "require_step_up" in gates["PUT"]
        assert "require_step_up" not in gates["GET"]
        assert "require_auth" in gates["GET"]
