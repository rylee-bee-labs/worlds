"""Critical-batch regression gates: setup/init, ingress degradation,
and portable source-control discovery.

- init: fresh data dir → setup-complete exists (healthz
  setup_needed=False); second init is idempotent and never clobbers
  user world state.
- ingress: without PW_TRAEFIK_BASE_URL the rollups endpoint answers
  the honest not_configured envelope — never HTTP 500.
- source control: the current checkout is discoverable portably (env
  override > explicit config > dev fallback), with real temp git
  repositories and no machine-specific paths.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world.init import init_world  # noqa: E402
from personal_world.source_control import (  # noqa: E402
    configured_search_paths,
    current_checkout_root,
)

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
        env={**GIT_ENV},
    )


def _client(tmp_path, monkeypatch, *, token: str = "t-token-1"):
    from personal_world.api import create_app

    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("PW_API_TOKEN", token)
    c = TestClient(create_app(tmp_path, tmp_path))
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c


class TestInitSetupContract:
    def test_init_satisfies_first_run(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PW_API_TOKEN", "t-token-1")
        init_world(tmp_path / "data", tmp_path / "config")
        assert (tmp_path / "data" / "setup-complete").exists()
        from personal_world.api import create_app

        c = TestClient(create_app(tmp_path / "data", tmp_path / "config"))
        health = c.get("/healthz").json()
        assert health["setup_needed"] is False

    def test_init_idempotent_and_safe(self, tmp_path):
        init_world(tmp_path, tmp_path / "config")
        wp = tmp_path / "world.json"
        payload = json.loads(wp.read_text())
        payload["facts"] = {"k": {"key": "k", "value": "v"}}
        wp.write_text(json.dumps(payload))
        journal = tmp_path / "journal.ndjson"
        before_journal = journal.read_text()
        r2 = init_world(tmp_path, tmp_path / "config")
        assert r2.status == "already-initialized"
        # user state untouched, marker untouched
        assert "k" in json.loads(wp.read_text())["facts"]
        assert (tmp_path / "setup-complete").exists()
        assert journal.read_text() == before_journal

    def test_init_never_overwrites_existing_world(self, tmp_path):
        # a pre-existing world with content survives init
        (tmp_path / "world.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "facts": {},
                    "intents": {},
                    "policies": {},
                    "lore": {},
                    "capabilities": {},
                    "providers": {},
                    "packs": {},
                }
            )
        )
        init_world(tmp_path, tmp_path / "config")
        assert "schema_version" in json.loads((tmp_path / "world.json").read_text())


class TestMediaStatusHonesty:
    def test_seeded_plex_no_500(self, tmp_path, monkeypatch):
        """Seeded plex connection → /api/media/status is an honest
        envelope (never a 500) even when the provider is unreachable."""
        (tmp_path / "connections.local.json").write_text(
            json.dumps(
                {
                    "connections": [
                        {
                            "name": "plex",
                            "type": "plex",
                            "base_url": "http://127.0.0.1:1",
                            "token": "PlexTokenAb12Cd34Ef56",
                        }
                    ]
                }
            )
        )
        c = _client(tmp_path, monkeypatch)
        r = c.get("/api/media/status")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("healthy", "unavailable", "not_configured")


class TestIngressDegradation:
    def test_no_config_honest_degraded(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PW_TRAEFIK_BASE_URL", raising=False)
        c = _client(tmp_path, monkeypatch)
        r = c.get("/api/ingress/rollups")
        assert r.status_code == 200  # never a 500
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "not_configured"
        assert "PW_TRAEFIK_BASE_URL" in body["warnings"][0]

    def test_bad_url_reports_unavailable_not_500(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PW_TRAEFIK_BASE_URL", "http://127.0.0.1:1")
        c = _client(tmp_path, monkeypatch)
        r = c.get("/api/ingress/rollups")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["status"] in ("unavailable", "degraded")


class TestSourceControlDiscovery:
    def test_env_override_wins(self, tmp_path, monkeypatch):
        """Precedence: explicit config > env override > checkout
        fallback — all dev-gated (bypass ON). Production (bypass OFF)
        is unchanged: unconfigured stays []."""
        monkeypatch.setenv("PW_DEV_AUTH_BYPASS", "1")
        monkeypatch.setenv("PW_SOURCE_CONTROL_ROOT", str(tmp_path / "envroot"))
        (tmp_path / "envroot").mkdir()
        assert configured_search_paths(tmp_path / "no-such-cfg") == [
            str(tmp_path / "envroot")
        ]

    def test_explicit_config_beats_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PW_DEV_AUTH_BYPASS", "1")
        monkeypatch.setenv("PW_SOURCE_CONTROL_ROOT", str(tmp_path / "envroot"))
        (tmp_path / "envroot").mkdir()
        config = tmp_path / "cfg"
        config.mkdir()
        (config / "connections.json").write_text(
            json.dumps(
                {
                    "connections": [],
                    "source_control": {"search_paths": ["/data/repos/x"]},
                }
            )
        )
        assert configured_search_paths(config) == ["/data/repos/x"]

    def test_explicit_config_wins_over_fallback(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PW_SOURCE_CONTROL_ROOT", raising=False)
        config = tmp_path / "cfg"
        config.mkdir()
        (config / "connections.json").write_text(
            json.dumps(
                {
                    "connections": [],
                    "source_control": {"search_paths": ["/data/repos/x"]},
                }
            )
        )
        assert configured_search_paths(config) == ["/data/repos/x"]

    def test_dev_bypass_off_unconfigured_is_empty(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PW_SOURCE_CONTROL_ROOT", raising=False)
        monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
        assert configured_search_paths(tmp_path) == []

    def test_dev_bypass_on_offers_current_checkout(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PW_SOURCE_CONTROL_ROOT", raising=False)
        monkeypatch.setenv("PW_DEV_AUTH_BYPASS", "1")
        paths = configured_search_paths(tmp_path)
        root = current_checkout_root()
        if root:  # running from a real checkout
            assert paths == [root]
        else:  # site-packages install: no fallback, honest empty
            assert paths == []

    def test_checkout_root_is_this_repo(self, monkeypatch):
        monkeypatch.delenv("PW_SOURCE_CONTROL_ROOT", raising=False)
        root = current_checkout_root()
        if root:
            assert (Path(root) / "pyproject.toml").exists()
            # and it must be the repo containing this very test file
            assert Path(root).resolve() in Path(__file__).resolve().parents

    def test_real_checkout_appears_in_status(self, tmp_path, monkeypatch):
        """End-to-end: a temporary real git repository, configured
        explicitly, yields real rows (no machine-specific paths)."""
        repo = tmp_path / "proj"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "master")
        _git(repo, "config", "user.email", "t@t")
        _git(repo, "config", "user.name", "t")
        (repo / "f.txt").write_text("hi\n")
        _git(repo, "add", "f.txt")
        _git(repo, "commit", "-q", "-m", "c0")
        config = tmp_path / "cfg"
        config.mkdir()
        (config / "connections.json").write_text(
            json.dumps(
                {
                    "connections": [],
                    "source_control": {"search_paths": [str(repo)]},
                }
            )
        )
        monkeypatch.delenv("PW_SOURCE_CONTROL_ROOT", raising=False)
        paths = configured_search_paths(config)
        assert paths == [str(repo)]
        from personal_world.source_control import status_all

        rows = status_all(paths)
        assert rows and rows[0]["name"] == "proj"
        assert rows[0]["dirty"] is False
