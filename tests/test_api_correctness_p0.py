"""P0.5 correctness pins for pre-existing API/auth defects.

- POST /api/chat/test was an unauthenticated provider probe
- POST /api/world/policy crashed (500) on a cemented key
- GET /api/daily mutated and saved the world on every page view
- reminder writes needed only plain auth, not the write-path gate
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def env(tmp_path, monkeypatch):
    from personal_world.api import create_app
    from personal_world.init import init_world

    monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok")
    return TestClient(create_app(tmp_path, tmp_path)), tmp_path


AUTH = {"Authorization": "Bearer instancetoken"}
# The current step-up gate accepts this header from the test client;
# P2 replaces it with real session-level step-up. Tests pin the *route
# requirement*, not the gate's strength.
STEP = {**AUTH, "X-PW-StepUp": "1"}


class TestChatProbe:
    def test_chat_test_requires_auth(self, env):
        c, _ = env
        assert c.post("/api/chat/test").status_code == 401

    def test_chat_test_honest_when_not_configured(self, env):
        c, _ = env
        r = c.post("/api/chat/test", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["status"] == "not_configured"


class TestPolicyBoundary:
    def test_cemented_policy_reports_409_not_500(self, env):
        c, tmp = env
        from personal_world.app import load_world, save_world
        from personal_world.model import Policy, PolicyEffect, Provenance

        world = load_world(tmp / "world.json")
        world.set_policy(Policy(key="never.delete", effect=PolicyEffect.DENY,
                                provenance=Provenance(source="test")))
        world.cement("never.delete")
        save_world(world, tmp / "world.json")

        r = c.post("/api/world/policy",
                   json={"key": "never.delete", "effect": "allow"},
                   headers=STEP)
        assert r.status_code == 409
        assert "cemented" in r.json()["detail"]
        # the cemented policy is untouched
        again = load_world(tmp / "world.json")
        assert again.policies["never.delete"].effect == PolicyEffect.DENY

    def test_bad_effect_is_400(self, env):
        c, _ = env
        r = c.post("/api/world/policy",
                   json={"key": "x", "effect": "maybe"}, headers=STEP)
        assert r.status_code == 400


class TestDailyIsReadOnlyOnGet:
    def test_get_daily_does_not_write(self, env):
        c, tmp = env
        world_before = (tmp / "world.json").read_bytes()
        journal_before = (tmp / "journal.ndjson").read_bytes()
        r = c.get("/api/daily", headers=AUTH)
        assert r.status_code == 200
        assert "capabilities" in r.json()["data"]
        assert (tmp / "world.json").read_bytes() == world_before
        assert (tmp / "journal.ndjson").read_bytes() == journal_before

    def test_post_daily_runs_and_saves(self, env):
        c, tmp = env
        r = c.post("/api/daily", headers=AUTH)
        assert r.status_code == 200
        assert "capabilities" in r.json()["data"]
        # zero-provider install: everything not_configured, so no facts
        # are recorded — but the route must be reachable and return the
        # same digest shape as the GET
        assert r.json()["data"].keys() == c.get(
            "/api/daily", headers=AUTH).json()["data"].keys()

    def test_post_daily_requires_auth(self, env):
        c, _ = env
        assert c.post("/api/daily").status_code == 401


class TestStatusContract:
    """`capabilities` has exactly one meaning per surface.

    `world.summary()` reports the world's OWN declared capabilities as a
    count; `GET /api/status` serves the provider capability-STATUS map
    under `capabilities`. They used to share the key `capabilities` with
    different types, and the API silently overwrote the summary value.
    """

    def test_api_status_capabilities_is_the_status_map(self, env):
        c, _ = env
        data = c.get("/api/status", headers=AUTH).json()["data"]
        assert isinstance(data["capabilities"], dict)
        # zero-provider install still declares each known capability
        for entry in data["capabilities"].values():
            assert {"ok", "status", "warnings", "last_observed"} <= set(entry)

    def test_api_status_keeps_declared_capability_count(self, env):
        c, _ = env
        data = c.get("/api/status", headers=AUTH).json()["data"]
        assert isinstance(data["declared_capabilities"], int)

    def test_world_summary_no_longer_uses_the_ambiguous_key(self, env):
        from personal_world.app import load_world
        _, tmp = env
        summary = load_world(tmp / "world.json").summary()
        assert "capabilities" not in summary
        assert "declared_capabilities" in summary

    def test_cli_and_api_agree_on_the_key_meaning(self, env):
        """The CLI emits world.summary(); the API adds the status map.
        Neither reuses the other's key for a different type."""
        c, tmp = env
        from personal_world.app import load_world
        cli_payload = load_world(tmp / "world.json").summary()
        api_payload = c.get("/api/status", headers=AUTH).json()["data"]
        assert cli_payload["declared_capabilities"] == api_payload["declared_capabilities"]
        assert isinstance(api_payload["capabilities"], dict)
        assert isinstance(cli_payload["declared_capabilities"], int)


class TestReminderWritesAreWritePath:
    def test_reads_need_auth_only(self, env):
        c, _ = env
        assert c.get("/api/reminders", headers=AUTH).status_code == 200

    def test_writes_need_step_up(self, env):
        c, _ = env
        r = c.post("/api/reminders", json={"text": "hi"}, headers=STEP)
        assert r.status_code == 200, r.text
        rid = r.json()["data"]["id"]
        assert c.patch(f"/api/reminders/{rid}", json={"enabled": False},
                       headers=STEP).status_code == 200
        assert c.delete(f"/api/reminders/{rid}",
                        headers=STEP).status_code == 200

    def test_write_routes_declare_step_up_dependency(self, env):
        """Structural pin until P2 replaces the gate: every reminder
        write route must depend on require_step_up, not require_auth."""
        c, _ = env
        for route in c.app.routes:
            path = getattr(route, "path", "")
            if not path.startswith("/api/reminders"):
                continue
            methods = getattr(route, "methods", set()) or set()
            deps = [d.dependency.__name__ for d in route.dependencies]
            if methods & {"POST", "PATCH", "DELETE"}:
                assert "require_step_up" in deps, (path, methods, deps)
            else:
                assert "require_auth" in deps, (path, methods, deps)
