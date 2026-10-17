"""Secret references in connection config resolve from env or the unlocked vault."""

import pytest

from personal_world import secret_resolver
from personal_world.connection_manager import (
    resolve_media_connections,
    resolve_native_config,
)


class FakeVault:
    def __init__(self, secrets, unlocked=True):
        self._s = secrets
        self.is_unlocked = unlocked

    def get(self, name):
        if not self.is_unlocked:
            raise RuntimeError("vault is locked")
        return self._s.get(name)


@pytest.fixture(autouse=True)
def _reset():
    secret_resolver.set_vault(None)
    yield
    secret_resolver.set_vault(None)


def test_env_reference_resolves(monkeypatch):
    monkeypatch.setenv("TEST_PLEX_TOKEN", "tok-value-1")
    [conn] = resolve_media_connections(
        {"_adapter": "plex", "base_url": "http://media.test", "token": "env:TEST_PLEX_TOKEN"}
    )
    assert conn["token"] == "tok-value-1"


def test_vault_reference_resolves_when_unlocked():
    secret_resolver.set_vault(FakeVault({"sonarr-key": "abc123"}))
    [conn] = resolve_media_connections(
        {"_adapter": "sonarr", "base_url": "http://media.test", "api_key": "vault://sonarr-key"}
    )
    assert conn["api_key"] == "abc123"
    [conn] = resolve_media_connections(
        {"_adapter": "sonarr", "base_url": "http://media.test", "api_key": "sonarr-key"}
    )
    assert conn["api_key"] == "abc123"


def test_locked_vault_leaves_reference_and_says_so():
    secret_resolver.set_vault(FakeVault({"sonarr-key": "abc123"}, unlocked=False))
    raw = {"_adapter": "sonarr", "base_url": "http://media.test", "api_key": "sonarr-key"}
    [conn] = resolve_media_connections(raw)
    assert conn["api_key"] == "sonarr-key"
    assert secret_resolver.secret_status(raw) == {"api_key": "needs your vault unlocked"}


def test_status_never_contains_values(monkeypatch):
    monkeypatch.setenv("TEST_NTFY", "very-secret-value")
    secret_resolver.set_vault(FakeVault({"plex-token": "hidden-token"}))
    status = secret_resolver.secret_status(
        {"token": "plex-token", "api_key": "env:TEST_NTFY", "password": "env:MISSING_VAR_X"}
    )
    assert status == {
        "token": "ready",
        "api_key": "ready",
        "password": "not set in the environment (MISSING_VAR_X)",
    }
    assert "hidden-token" not in repr(status) and "very-secret-value" not in repr(status)


def test_inline_credential_untouched():
    secret_resolver.set_vault(FakeVault({}))
    [conn] = resolve_media_connections(
        {"_adapter": "plex", "base_url": "http://media.test", "token": "Zx9QpLmN4rT"}
    )
    assert conn["token"] == "Zx9QpLmN4rT"


def test_native_config_resolves_notification_token():
    secret_resolver.set_vault(FakeVault({"ntfy-token": "n-1"}))
    out = resolve_native_config(
        {"_adapter": "ntfy", "name": "phone", "server": "http://ntfy.test", "topic": "t", "token": "ntfy-token"},
        "notifications",
    )
    assert out["targets"][0]["token"] == "n-1"


def test_media_adapter_builds_from_vault_reference():
    from personal_world.providers.native_media import build_adapter

    secret_resolver.set_vault(FakeVault({"plex-token": "Zx9QpLmN4rT"}))
    [conn] = resolve_media_connections(
        {"_adapter": "plex", "base_url": "http://media.test", "token": "plex-token"}
    )
    assert build_adapter(conn) is not None
