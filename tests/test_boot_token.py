"""Boot-time token reconciliation (P2 auth groundwork, 2026-09-12).

POST /api/setup writes the human-created token to ``<data_dir>/.env``
and the live process env; before the fix, a restart restored the
compose-supplied ``PW_API_TOKEN`` and locked the owner out of their
own world (observed live twice, 2026-09-12). These tests pin the
restart-survivable semantics: the setup file is the human-facing
credential store and outranks deployment-infra env at boot.
"""
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402


def _client(tmp_path, monkeypatch, env_token: str):
    from personal_world.api import create_app
    monkeypatch.setenv("PW_API_TOKEN", env_token)
    return TestClient(create_app(tmp_path, tmp_path))


def _hdr(tok: str):
    return {"Authorization": f"Bearer {tok}"}


def _setup(c: TestClient, tok: str) -> None:
    r = c.post("/api/setup", json={"token": tok, "vault_passphrase": ""},
               headers=_hdr(tok))
    assert r.status_code == 200, r.text


def test_setup_token_survives_recreate(tmp_path, monkeypatch):
    """The wizard-created token still authenticates after a restart
    (fresh process + fresh create_app over the same data dir)."""
    wizard_tok = "wizard-token-01"
    c = _client(tmp_path, monkeypatch, "compose-token-01")
    _setup(c, wizard_tok)
    # in-process replacement happened at setup time
    assert c.get("/healthz").json()["auth_configured"] is True

    # RESTART: new app instance, compose env token back in the env —
    # the boot reconciliation must prefer the setup file.
    c2 = _client(tmp_path, monkeypatch, "compose-token-01")
    r = c2.get("/api/sections", headers=_hdr(wizard_tok))
    assert r.status_code == 200, r.text
    # and the stale infra token is no longer accepted
    # (/api/setup/status is deliberately unauthenticated — SPA pre-login
    # needs it; the real auth gate is /api/sections).
    assert c2.get("/api/sections",
                  headers=_hdr("compose-token-01")).status_code == 401


def test_matching_tokens_are_a_noop(tmp_path, monkeypatch):
    """File token == env token: nothing changes, boot stays quiet."""
    c = _client(tmp_path, monkeypatch, "same-token-01")
    _setup(c, "same-token-01")
    c2 = _client(tmp_path, monkeypatch, "same-token-01")
    assert c2.get("/api/sections",
                  headers=_hdr("same-token-01")).status_code == 200


def test_malformed_env_file_leaves_env_untouched(tmp_path, monkeypatch):
    """An unreadable or token-less .env fails toward the deployment's
    token, never toward lockout."""
    from personal_world.api import create_app
    monkeypatch.setenv("PW_API_TOKEN", "compose-token-02")
    # .env exists but carries no PW_API_TOKEN line
    (tmp_path / ".env").write_text("# something else\nOTHER=1\n")
    c = TestClient(create_app(tmp_path, tmp_path))
    assert c.get("/api/sections",
                 headers=_hdr("compose-token-02")).status_code == 200
    # wizard path never ran: setup still needed
    assert c.get("/healthz").json()["setup_needed"] is True


def test_quoted_value_is_stripped(tmp_path, monkeypatch):
    """A quoted file value is accepted unquoted (defensive parsing)."""
    from personal_world.api import create_app
    monkeypatch.setenv("PW_API_TOKEN", "compose-token-03")
    (tmp_path / ".env").write_text('PW_API_TOKEN="wizard-token-03"\n')
    c = TestClient(create_app(tmp_path, tmp_path))
    assert c.get("/api/sections",
                 headers=_hdr("wizard-token-03")).status_code == 200
    assert c.get("/api/sections",
                 headers=_hdr("compose-token-03")).status_code == 401


def test_no_env_file_is_a_noop(tmp_path, monkeypatch):
    """Fresh deployment without a setup file: compose token rules."""
    from personal_world.api import create_app
    monkeypatch.setenv("PW_API_TOKEN", "compose-token-04")
    c = TestClient(create_app(tmp_path, tmp_path))
    assert c.get("/api/sections",
                 headers=_hdr("compose-token-04")).status_code == 200
