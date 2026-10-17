"""First-run setup wizard: gating, invisible provisioning, honesty,
and the no-secrets contract.

Covers the P-universal deliverable: while `data/setup-complete` is
absent (or FORCE_SETUP=1), `/` redirects to `/setup`, the wizard is
served without auth, provisioning is create-if-absent and never
echoes the token, OIDC collection stores only an env var NAME for the
secret, and once setup is complete `/setup` refuses so the wizard can
never be re-run by accident.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world import crew as crew_mod  # noqa: E402


def _client(tmp_path, monkeypatch):
    """Fresh app over empty data/config dirs. PW_API_TOKEN is always
    monkeypatch-managed so the handler's in-process env write is
    undone at teardown (no leak into other tests)."""
    from personal_world.api import create_app

    monkeypatch.delenv("PW_API_TOKEN", raising=False)
    monkeypatch.delenv("FORCE_SETUP", raising=False)
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    app = create_app(data_dir, config_dir)
    return TestClient(app), data_dir, config_dir


@pytest.fixture
def wizard_env(tmp_path, monkeypatch):
    return _client(tmp_path, monkeypatch)


def _read_token(data_dir: Path) -> str:
    for line in (data_dir / ".env").read_text().splitlines():
        if line.startswith("PW_API_TOKEN="):
            return line.split("=", 1)[1]
    raise AssertionError("no PW_API_TOKEN line in data/.env")


class TestFirstRunGating:
    def test_root_redirects_to_wizard(self, wizard_env):
        client, _, _ = wizard_env
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/setup"

    def test_setup_serves_wizard_without_auth(self, wizard_env):
        client, _, _ = wizard_env
        r = client.get("/setup")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        assert "Set up Worlds" in r.text
        assert "Project Worlds" not in r.text
        # Landmarks + skip link are part of the a11y floor.
        assert 'href="#main"' in r.text
        assert "<main" in r.text

    def test_wizard_assets_served(self, wizard_env):
        client, _, _ = wizard_env
        css = client.get("/setup/styles.css")
        assert css.status_code == 200
        assert css.headers["content-type"].startswith("text/css")
        js = client.get("/setup/wizard.js")
        assert js.status_code == 200
        assert "javascript" in js.headers["content-type"]

    def test_unknown_asset_404s(self, wizard_env):
        client, _, _ = wizard_env
        assert client.get("/setup/nope.txt").status_code == 404

    def test_healthz_reports_setup_needed(self, wizard_env):
        client, data_dir, _ = wizard_env
        assert client.get("/healthz").json()["setup_needed"] is True
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "setup-complete").write_text("ok")
        assert client.get("/healthz").json()["setup_needed"] is False

    def test_setup_refuses_after_completion(self, wizard_env):
        client, data_dir, _ = wizard_env
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "setup-complete").write_text("ok")
        r = client.get("/setup", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"
        assert client.post("/api/setup-wizard/provision").status_code == 404
        assert client.post("/api/setup-wizard/finish").status_code == 404
        assert client.get("/api/setup-wizard/state").status_code == 404
        # / no longer hijacks into the wizard (it may gate to /login —
        # that is the interface's own gate, not a setup redirect)
        root = client.get("/", follow_redirects=False)
        assert root.headers.get("location") != "/setup"

    def test_force_setup_reopens_wizard(self, tmp_path, monkeypatch):
        client, data_dir, _ = _client(tmp_path, monkeypatch)
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "setup-complete").write_text("ok")
        assert client.get("/setup", follow_redirects=False).status_code == 303
        monkeypatch.setenv("FORCE_SETUP", "1")
        assert client.get("/setup").status_code == 200


class TestProvisioning:
    def test_creates_token_stores_and_index_without_marker(self, wizard_env):
        client, data_dir, config_dir = wizard_env
        r = client.post("/api/setup-wizard/provision")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["token_ready"] is True
        assert body["data"]["search_index"] == "ready"
        token = _read_token(data_dir)
        assert len(token) >= 32
        # The token is NEVER echoed in any response or page.
        assert token not in r.text
        assert token not in client.get("/setup").text
        assert token not in client.get("/api/setup-wizard/state").text
        # Restrictive perms on the credential file.
        assert data_dir.joinpath(".env").stat().st_mode & 0o777 == 0o600
        # Stores created.
        assert (data_dir / "world.json").is_file()
        assert (data_dir / "journal.ndjson").exists()
        assert (config_dir / "connections.json").is_file()
        assert (data_dir / "memory.fts5.db").is_file()
        # The marker belongs to the finish step only.
        assert not (data_dir / "setup-complete").exists()

    def test_idempotent_and_never_overwrites(self, wizard_env):
        client, data_dir, _ = wizard_env
        assert client.post("/api/setup-wizard/provision").json()["ok"]
        first = (data_dir / ".env").read_text()
        world_before = (data_dir / "world.json").read_text()
        again = client.post("/api/setup-wizard/provision")
        assert again.json()["ok"] is True
        assert (data_dir / ".env").read_text() == first
        assert first.count("PW_API_TOKEN=") == 1
        assert (data_dir / "world.json").read_text() == world_before

    def test_existing_env_token_is_kept(self, tmp_path, monkeypatch):
        client, data_dir, _ = _client(tmp_path, monkeypatch)
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / ".env").write_text('PW_API_TOKEN="kept-token-01"\n')
        r = client.post("/api/setup-wizard/provision")
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["token_state"] == "already-present"
        assert (data_dir / ".env").read_text() == 'PW_API_TOKEN="kept-token-01"\n'

    def test_existing_env_file_is_appended_not_clobbered(self, tmp_path, monkeypatch):
        client, data_dir, _ = _client(tmp_path, monkeypatch)
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / ".env").write_text("OTHER=keepme\n")
        r = client.post("/api/setup-wizard/provision")
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["token_state"] == "generated (appended data/.env)"
        text = (data_dir / ".env").read_text()
        assert "OTHER=keepme" in text
        assert "PW_API_TOKEN=" in text

    def test_environment_token_needs_no_file(self, tmp_path, monkeypatch):
        client, data_dir, _ = _client(tmp_path, monkeypatch)
        monkeypatch.setenv("PW_API_TOKEN", "compose-provided-token")
        r = client.post("/api/setup-wizard/provision")
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["token_state"] == "environment"
        assert not (data_dir / ".env").exists()
        assert "compose-provided-token" not in r.text


class TestAuthChoice:
    def _provision(self, client):
        assert client.post("/api/setup-wizard/provision").json()["ok"]

    def test_local_choice_zero_config(self, wizard_env):
        client, data_dir, config_dir = wizard_env
        self._provision(client)
        r = client.post("/api/setup-wizard/auth-choice", json={"choice": "local"})
        assert r.json()["ok"] is True
        assert not (config_dir / "oidc.json").exists()
        choices = json.loads((data_dir / "setup-choices.json").read_text())
        assert choices["auth_choice"] == "local"

    def test_unknown_choice_rejected_plainly(self, wizard_env):
        client, _, _ = wizard_env
        self._provision(client)
        r = client.post("/api/setup-wizard/auth-choice", json={"choice": "magic"})
        assert r.status_code == 422
        assert r.json()["ok"] is False
        assert "choose" in r.json()["warnings"][0].lower()

    def test_oidc_choice_stores_env_name_only(self, wizard_env):
        client, data_dir, config_dir = wizard_env
        self._provision(client)
        r = client.post(
            "/api/setup-wizard/auth-choice",
            json={
                "choice": "oidc",
                "issuer_url": "https://sso.example.invalid/",
                "client_id": "project-worlds",
                "client_secret_env": "MY_SSO_SECRET",
            },
        )
        body = r.json()
        assert body["ok"] is True
        # Blocking finding (owner decision 2026-09-22): the wizard
        # pauses for "Continue anyway" — env var not set qualifies
        # (SSO sign-in genuinely will not complete).
        assert any("MY_SSO_SECRET" in w and "not set" in w for w in body["blocking"])
        # The restart note stays informational — it never pauses.
        assert any("next restart" in w for w in body["warnings"])
        assert not any("not set" in w for w in body["warnings"])
        cfg = json.loads((config_dir / "oidc.json").read_text())
        assert cfg["issuer"] == "https://sso.example.invalid"
        assert cfg["client_id"] == "project-worlds"
        assert cfg["client_secret_env"] == "MY_SSO_SECRET"
        # Only the NAME is stored — no secret value anywhere.
        choices = json.loads((data_dir / "setup-choices.json").read_text())
        assert choices["oidc"]["client_secret_env"] == "MY_SSO_SECRET"
        assert set(choices["oidc"].keys()) == {
            "issuer",
            "client_id",
            "client_secret_env",
        }

    def test_oidc_config_never_overwritten(self, wizard_env):
        client, _, config_dir = wizard_env
        self._provision(client)
        first = {
            "choice": "oidc",
            "issuer_url": "https://first.example.invalid",
            "client_id": "one",
            "client_secret_env": "A_B",
        }
        assert client.post("/api/setup-wizard/auth-choice", json=first).json()["ok"]
        second = {
            "choice": "oidc",
            "issuer_url": "https://second.example.invalid",
            "client_id": "two",
            "client_secret_env": "C_D",
        }
        r = client.post("/api/setup-wizard/auth-choice", json=second)
        # Blocking: the existing oidc.json wins — the new answers are
        # record-only, so sign-in will NOT match what was just typed.
        assert any("left it untouched" in w for w in r.json()["blocking"])
        cfg = json.loads((config_dir / "oidc.json").read_text())
        assert cfg["issuer"] == "https://first.example.invalid"

    def test_oidc_validation_is_honest(self, wizard_env):
        client, _, _ = wizard_env
        self._provision(client)
        bad = [
            {
                "choice": "oidc",
                "issuer_url": "ftp://x.example.invalid",
                "client_id": "c",
                "client_secret_env": "S",
            },
            {
                "choice": "oidc",
                "issuer_url": "https://x.example.invalid",
                "client_id": "",
                "client_secret_env": "S",
            },
            {
                "choice": "oidc",
                "issuer_url": "https://x.example.invalid",
                "client_id": "c",
                "client_secret_env": "not a name!",
            },
        ]
        for payload in bad:
            r = client.post("/api/setup-wizard/auth-choice", json=payload)
            assert r.status_code == 422, payload
            assert r.json()["warnings"], payload


class TestDiscoveryTest:
    def test_bad_scheme_is_bad_config(self, wizard_env):
        client, _, _ = wizard_env
        r = client.post("/api/setup-wizard/test-oidc", json={"issuer_url": "not-a-url"})
        body = r.json()
        assert body["ok"] is False
        assert body["data"]["status"] == "bad_config"
        assert body["data"]["detail"]

    def test_unreachable_is_reported_as_unreachable(self, wizard_env):
        client, _, _ = wizard_env
        # Port 9 (discard) on loopback refuses connections; the wizard
        # must say so plainly instead of faking success.
        r = client.post(
            "/api/setup-wizard/test-oidc", json={"issuer_url": "http://127.0.0.1:9"}
        )
        body = r.json()
        assert body["ok"] is False
        assert body["data"]["status"] == "unreachable"
        assert "could not reach" in body["data"]["detail"].lower()

    def test_no_secrets_in_response(self, wizard_env):
        client, _, _ = wizard_env
        r = client.post(
            "/api/setup-wizard/test-oidc", json={"issuer_url": "http://127.0.0.1:9"}
        )
        text = r.text.lower()
        assert "client_secret" not in text
        token = os.environ.get("PW_API_TOKEN", "")
        assert not token or token not in r.text


class TestComfortAndFinish:
    def test_comfort_applies_validated_prefs(self, wizard_env):
        client, data_dir, _ = wizard_env
        client.post("/api/setup-wizard/provision")
        r = client.post(
            "/api/setup-wizard/comfort",
            json={"larger_text": True, "gentle_animations": False},
        )
        assert r.json()["ok"] is True
        assert r.json()["data"]["applied"]["text_scale"] == 1.25
        assert r.json()["data"]["applied"]["motion"] == "reduced"
        world = json.loads((data_dir / "world.json").read_text())
        assert world["accessibility"]["text_scale"] == 1.25

    def test_finish_writes_marker_and_signs_in(self, wizard_env):
        client, data_dir, _ = wizard_env
        client.post("/api/setup-wizard/provision")
        client.post("/api/setup-wizard/auth-choice", json={"choice": "local"})
        client.post("/api/setup-wizard/comfort", json={})
        r = client.post("/api/setup-wizard/finish")
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["redirect"] == "/"
        assert (data_dir / "setup-complete").is_file()
        # The person lands signed in: a real session cookie, no token.
        assert "pw_session=" in r.headers.get("set-cookie", "")
        assert _read_token(data_dir) not in r.text
        # The journal recorded the event.
        entries = [
            json.loads(line)
            for line in (data_dir / "journal.ndjson").read_text().splitlines()
            if line
        ]
        assert any("first-run setup completed" in e["summary"] for e in entries)
        # And the wizard now refuses to run again.
        assert client.get("/setup", follow_redirects=False).status_code == 303
        assert client.post("/api/setup-wizard/provision").status_code == 404

    def test_state_reports_progress(self, wizard_env):
        client, data_dir, _ = wizard_env
        state = client.get("/api/setup-wizard/state").json()["data"]
        assert state["setup_needed"] is True
        assert state["provisioned"]["env_file"] is False
        client.post("/api/setup-wizard/provision")
        client.post("/api/setup-wizard/auth-choice", json={"choice": "local"})
        state = client.get("/api/setup-wizard/state").json()["data"]
        assert state["provisioned"]["env_file"] is True
        assert state["choices"]["auth_choice"] == "local"
        assert _read_token(data_dir) not in client.get("/api/setup-wizard/state").text


class TestFirstRunWritesAreLoopbackOnly:
    """A REMOTE peer must never be able to claim a fresh instance
    through the setup write endpoints (fail closed). The TestClient's
    default ASGI peer is loopback; here we use a deliberately remote
    client address. GET state routes stay readable."""

    def _remote_client(self, tmp_path, monkeypatch):
        from personal_world.api import create_app

        monkeypatch.delenv("PW_API_TOKEN", raising=False)
        monkeypatch.setenv("PW_IDENTITY_MODE", "single")
        data_dir = tmp_path / "data"
        config_dir = tmp_path / "config"
        c = TestClient(create_app(data_dir, config_dir), client=("203.0.113.9", 5555))
        return c, data_dir, config_dir

    def test_remote_post_setup_refused(self, tmp_path, monkeypatch):
        c, data_dir, _ = self._remote_client(tmp_path, monkeypatch)
        r = c.post("/api/setup", json={"token": "longenough1"})
        assert r.status_code == 403, r.text
        # Nothing was claimed: no marker, no env file.
        assert not (data_dir / "setup-complete").exists()
        assert not (data_dir / ".env").exists()
        assert os.environ.get("PW_API_TOKEN") is None

    def test_remote_wizard_provision_refused_state_readable(
        self, tmp_path, monkeypatch
    ):
        c, data_dir, _ = self._remote_client(tmp_path, monkeypatch)
        r = c.post("/api/setup-wizard/provision")
        assert r.status_code == 403
        assert not (data_dir / ".env").exists()
        # State reads never gate on the peer.
        assert c.get("/api/setup-wizard/state").status_code == 200
        assert c.get("/api/setup/status").status_code == 200

    def test_loopback_provision_still_works(self, tmp_path, monkeypatch):
        """Sanity: the default TestClient peer keeps provisioning working."""
        client, data_dir, _ = _client(tmp_path, monkeypatch)
        r = client.post("/api/setup-wizard/provision")
        assert r.status_code == 200, r.text

    def test_setup_env_file_mode_0600(self, tmp_path, monkeypatch):
        from personal_world.api import create_app

        monkeypatch.delenv("PW_API_TOKEN", raising=False)
        monkeypatch.setenv("PW_IDENTITY_MODE", "single")
        data_dir = tmp_path / "data"
        config_dir = tmp_path / "config"
        c = TestClient(create_app(data_dir, config_dir))
        r = c.post("/api/setup", json={"token": "longenough1"})
        assert r.status_code == 200, r.text
        # The credential file is never world-readable.
        assert (data_dir / ".env").stat().st_mode & 0o777 == 0o600


def _remote_client(tmp_path, monkeypatch):
    """A deliberately remote ASGI peer (writes must fail closed)."""
    from personal_world.api import create_app

    monkeypatch.delenv("PW_API_TOKEN", raising=False)
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    c = TestClient(create_app(data_dir, config_dir), client=("203.0.113.9", 5555))
    return c, data_dir, config_dir


def _choices(data_dir: Path) -> dict:
    path = data_dir / "setup-choices.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _accessibility(data_dir: Path) -> dict:
    return json.loads((data_dir / "world.json").read_text())["accessibility"]


class TestComfortCrewOn:
    """``crew_on`` toggles the residents pack ("residents" | "off") on the
    comfort step; absent leaves the current choice (default: residents)."""

    def _provision(self, client):
        assert client.post("/api/setup-wizard/provision").json()["ok"]

    def test_true_enables_residents(self, wizard_env):
        client, data_dir, _ = wizard_env
        self._provision(client)
        r = client.post("/api/setup-wizard/comfort", json={"crew_on": True})
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["applied"]["personality_pack"] == "residents"
        assert body["data"]["comfort"]["crew_on"] is True
        assert _accessibility(data_dir)["personality_pack"] == "residents"
        assert _choices(data_dir)["comfort"]["crew_on"] is True

    def test_false_is_off(self, wizard_env):
        client, data_dir, _ = wizard_env
        self._provision(client)
        r = client.post("/api/setup-wizard/comfort", json={"crew_on": False})
        body = r.json()
        assert body["data"]["applied"]["personality_pack"] == "off"
        assert body["data"]["comfort"]["crew_on"] is False
        assert _accessibility(data_dir)["personality_pack"] == "off"
        assert _choices(data_dir)["comfort"]["crew_on"] is False

    def test_absent_keeps_the_shipped_default(self, wizard_env):
        client, data_dir, _ = wizard_env
        self._provision(client)
        body = client.post("/api/setup-wizard/comfort", json={}).json()
        assert body["data"]["applied"]["personality_pack"] == "residents"
        assert body["data"]["comfort"]["crew_on"] is True

    def test_absent_never_overwrites_an_explicit_choice(self, wizard_env):
        client, data_dir, _ = wizard_env
        self._provision(client)
        client.post("/api/setup-wizard/comfort", json={"crew_on": False})
        body = client.post("/api/setup-wizard/comfort", json={}).json()
        assert body["data"]["applied"]["personality_pack"] == "off"
        assert body["data"]["comfort"]["crew_on"] is False
        assert _accessibility(data_dir)["personality_pack"] == "off"


class TestWizardStarterCrew:
    """GET /api/setup-wizard/crew: the starter canon, nothing personal."""

    _SHAPE = {"id", "name", "blurb", "portrait_asset"}

    def test_lists_the_starter_crew(self, wizard_env):
        client, _, _ = wizard_env
        r = client.get("/api/setup-wizard/crew")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        offered = body["data"]
        assert isinstance(offered, list) and offered
        expected = [spec["id"] for spec in crew_mod.STARTER_CREW]
        assert [entry["id"] for entry in offered] == expected
        for entry in offered:
            assert set(entry) == self._SHAPE
            assert entry["name"] and entry["blurb"]
            assert entry["portrait_asset"].startswith("/assets/crew/")
        # Sol is the Worlds mark — never a companion, never offered.
        assert "sol" not in {entry["id"] for entry in offered}

    def test_stays_starter_only_after_a_choice(self, wizard_env):
        client, _, _ = wizard_env
        client.post("/api/setup-wizard/provision")
        client.post("/api/setup-wizard/companion", json={"companion_id": "bolt"})
        ids = {
            entry["id"]
            for entry in client.get("/api/setup-wizard/crew").json()["data"]
        }
        assert ids == {spec["id"] for spec in crew_mod.STARTER_CREW}

    def test_first_run_only(self, wizard_env):
        client, data_dir, _ = wizard_env
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "setup-complete").write_text("ok")
        assert client.get("/api/setup-wizard/crew").status_code == 404

    def test_readable_from_a_remote_peer(self, tmp_path, monkeypatch):
        """Read-only, like /state: no loopback gate."""
        c, _, _ = _remote_client(tmp_path, monkeypatch)
        assert c.get("/api/setup-wizard/crew").status_code == 200


class TestCompanionChoice:
    """POST /api/setup-wizard/companion: a starter id, or null."""

    def _provision(self, client):
        assert client.post("/api/setup-wizard/provision").json()["ok"]

    def test_valid_starter_id_is_saved(self, wizard_env):
        client, data_dir, _ = wizard_env
        self._provision(client)
        r = client.post(
            "/api/setup-wizard/companion", json={"companion_id": "bolt"}
        )
        assert r.status_code == 200
        assert r.json()["data"]["companion_id"] == "bolt"
        assert _accessibility(data_dir)["companion_id"] == "bolt"
        assert _choices(data_dir)["companion_id"] == "bolt"

    def test_null_is_the_plain_voice(self, wizard_env):
        client, data_dir, _ = wizard_env
        self._provision(client)
        r = client.post(
            "/api/setup-wizard/companion", json={"companion_id": None}
        )
        assert r.status_code == 200
        assert r.json()["data"]["companion_id"] is None
        assert _accessibility(data_dir)["companion_id"] is None
        assert _choices(data_dir)["companion_id"] is None

    def test_unknown_id_refused_plainly(self, wizard_env):
        client, data_dir, _ = wizard_env
        self._provision(client)
        r = client.post(
            "/api/setup-wizard/companion", json={"companion_id": "ghost"}
        )
        assert r.status_code == 422
        assert r.json()["ok"] is False
        assert "starter companion" in r.json()["warnings"][0].lower()
        assert "companion_id" not in _choices(data_dir)

    def test_sol_is_never_a_companion(self, wizard_env):
        client, data_dir, _ = wizard_env
        self._provision(client)
        r = client.post(
            "/api/setup-wizard/companion", json={"companion_id": "sol"}
        )
        assert r.status_code == 422
        assert "companion_id" not in _choices(data_dir)

    def test_non_string_id_refused(self, wizard_env):
        client, _, _ = wizard_env
        self._provision(client)
        r = client.post("/api/setup-wizard/companion", json={"companion_id": 7})
        assert r.status_code == 422

    def test_choice_persists_for_resume(self, wizard_env):
        client, _, _ = wizard_env
        self._provision(client)
        client.post(
            "/api/setup-wizard/companion", json={"companion_id": "renai"}
        )
        state = client.get("/api/setup-wizard/state").json()["data"]
        assert state["choices"]["companion_id"] == "renai"

    def test_remote_write_refused(self, tmp_path, monkeypatch):
        c, data_dir, _ = _remote_client(tmp_path, monkeypatch)
        r = c.post("/api/setup-wizard/companion", json={"companion_id": "bolt"})
        assert r.status_code == 403
        assert not (data_dir / "setup-choices.json").exists()

    def test_refused_after_completion(self, wizard_env):
        client, data_dir, _ = wizard_env
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "setup-complete").write_text("ok")
        r = client.post(
            "/api/setup-wizard/companion", json={"companion_id": "bolt"}
        )
        assert r.status_code == 404
        assert not (data_dir / "setup-choices.json").exists()
