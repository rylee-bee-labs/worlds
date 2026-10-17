import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.app import load_world, save_world  # noqa: E402
from personal_world.model import (  # noqa: E402
    Policy,
    PolicyEffect,
    Provenance,
)
from personal_world.world import World  # noqa: E402


class TestPersistence:
    def test_world_survives_roundtrip(self, tmp_path):
        w = World()
        w.set_policy(Policy(
            key="content.animal_cruelty",
            effect=PolicyEffect.DENY,
            provenance=Provenance(source="user"),
        ))
        save_world(w, tmp_path / "world.json")
        w2 = load_world(tmp_path / "world.json")
        assert w2.policies["content.animal_cruelty"].effect == PolicyEffect.DENY


class TestApi:
    def _app(self, tmp_path, monkeypatch, token="secret-token-1"):
        from personal_world.api import create_app
        monkeypatch.setenv("PW_API_TOKEN", token)
        monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
        return create_app(tmp_path, tmp_path)

    def test_healthz_reports_auth_configured(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        app = self._app(tmp_path, monkeypatch)
        c = TestClient(app)
        r = c.get("/healthz")
        assert r.status_code == 200
        assert r.json()["auth_configured"] is True

    def test_protected_route_rejects_anonymous(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        app = self._app(tmp_path, monkeypatch)
        c = TestClient(app)
        assert c.get("/api/status").status_code == 401

    def test_protected_route_rejects_wrong_token(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        app = self._app(tmp_path, monkeypatch)
        c = TestClient(app)
        r = c.get("/api/status", headers={"Authorization": "Bearer nope"})
        assert r.status_code == 401

    def test_protected_route_accepts_correct_token(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        app = self._app(tmp_path, monkeypatch)
        c = TestClient(app)
        r = c.get("/api/status", headers={"Authorization": "Bearer secret-token-1"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_fail_closed_when_no_token_configured(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        monkeypatch.delenv("PW_API_TOKEN", raising=False)
        from personal_world.api import create_app
        app = create_app(tmp_path, tmp_path)
        c = TestClient(app)
        assert c.get("/api/status").status_code == 503


    def test_settings_export_via_api_leaks_nothing(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        app = self._app(tmp_path, monkeypatch)
        c = TestClient(app)
        r = c.get("/api/exports/settings",
                  headers={"Authorization": "Bearer secret-token-1"})
        blob = r.text
        for bad in ("rylee-bee-labs", "sk-live", "ghp_", "password"):
            assert bad not in blob, f"LEAK via API: {bad}"


class TestIntegrationLeakage:
    """New V0.1 integrations must not leak auth or personal data
    through exports or the API surface."""

    def test_settings_export_has_no_auth_material(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        app = self._app(tmp_path, monkeypatch)
        c = TestClient(app)
        r = c.get("/api/exports/settings",
                  headers={"Authorization": "Bearer secret-token-1"})
        blob = r.text
        for bad in ("secret-token-1", "Bearer", "Authorization",
                    "Remote-User", "Remote-Groups", "session"):
            assert bad not in blob, f"auth material in settings-export: {bad}"

    def test_backup_has_no_auth_material(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        app = self._app(tmp_path, monkeypatch)
        c = TestClient(app)
        r = c.get("/api/backup",
                  headers={"Authorization": "Bearer secret-token-1"})
        assert "secret-token-1" not in r.text

    def test_candy_observation_minimal_fields(self, monkeypatch):
        import io
        import urllib.request

        from personal_world.providers.adapters import CandyDispenser
        fake_health = {
            "status": "ok", "notifications_sent": 3, "errors": 0,
            "grabs_accepted": 1, "grabs_refused": 2,
            "sources": ["mam_rss"], "seen_count": 100,
            "mam_indexer_name": "PrivateIndexer",
            "ebook_download_client_name": "PrivateClient",
            "phase_c": {"bandcamp_tag": "personal-tag"},
        }

        class _Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            return _Resp(json.dumps(fake_health).encode())

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        candy = CandyDispenser("http://candy.test:5126")
        result = candy.observe()
        blob = json.dumps(result.data)
        for bad in ("PrivateIndexer", "PrivateClient", "personal-tag"):
            assert bad not in blob, f"candy observation leaked: {bad}"
        assert result.data["reachable"] is True
        assert result.data["notifications_sent"] == 3

    def test_forged_forwarded_identity_does_not_auth(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        app = self._app(tmp_path, monkeypatch)
        c = TestClient(app)
        r = c.get("/api/status",
                  headers={"Remote-User": "rylee", "Remote-Groups": "users",
                           "Authorization": "Bearer wrong"})
        assert r.status_code == 401

    def _app(self, tmp_path, monkeypatch):
        from personal_world.api import create_app
        monkeypatch.setenv("PW_API_TOKEN", "secret-token-1")
        return create_app(data_dir=tmp_path, config_dir=tmp_path)


class TestEntrypointTokenGuard:
    """Papercut: compose must parse without PW_API_TOKEN present, so
    the loud failure moved to runtime. The container entrypoint (sh -c
    guard in Dockerfile CMD) must refuse to boot with an empty token,
    and hand off to uvicorn otherwise. Tests parse the real Dockerfile
    so the guard cannot drift from this test."""

    @staticmethod
    def _entrypoint_script() -> str:
        import json
        raw = (Path(__file__).parent.parent / "Dockerfile").read_text()
        start = raw.index("\nCMD ") + 1
        cmd_block = raw[start:]
        # Join Dockerfile line continuations.
        while True:
            joined = cmd_block.replace("\\\n", " ", 1)
            if joined == cmd_block:
                break
            cmd_block = joined
        lines = cmd_block.split("\n")
        kept = [lines[0].removeprefix("CMD ")]
        for line in lines[1:]:
            if not line.startswith(("    ", "\t")):
                break
            kept.append(line)
        argv = json.loads(" ".join(k.strip() for k in kept))
        assert argv[0] == "sh" and argv[1] == "-c", \
            "entrypoint must be a sh -c guard"
        return argv[2]

    def test_entrypoint_refuses_empty_token(self):
        import subprocess
        script = self._entrypoint_script()
        guard, _, tail = script.partition("exec ")
        assert "uvicorn" in tail, "entrypoint must still exec uvicorn"
        probe = guard + 'echo BOOTTED'
        proc = subprocess.run(
            ["sh", "-c", probe],
            env={"PW_API_TOKEN": ""}, capture_output=True, text=True,
        )
        assert proc.returncode != 0, "empty token must fail the guard"
        assert "PW_API_TOKEN" in proc.stderr
        assert proc.stdout == "", "nothing may run after refusal"

    def test_entrypoint_hands_off_with_token(self):
        import subprocess
        script = self._entrypoint_script()
        guard, _, tail = script.partition("exec ")
        assert tail, "entrypoint must exec the server, not run inline"
        probe = guard + 'echo BOOTTED'
        proc = subprocess.run(
            ["sh", "-c", probe],
            env={"PW_API_TOKEN": "t"}, capture_output=True, text=True,
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == "BOOTTED"
