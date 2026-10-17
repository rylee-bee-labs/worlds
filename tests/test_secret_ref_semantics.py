"""Secret reference semantics tests.

Proves:
- A vault reference (e.g., "my-plex-token") is NOT passed upstream
  as though it were the actual secret value.
- Without vault resolution, adapters return None (not_configured).
- Env var indirection still works.
- Direct inline credentials from connections.json (non-UI path) work
  when explicitly configured with token_env/api_key_env.
"""

from personal_world.providers.native_media import _is_secret_ref, build_adapter


class TestSecretRefDetection:
    """_is_secret_ref detects unresolved secret references."""

    def test_token_without_env_is_ref(self):
        """token field without token_env → treated as reference."""
        config = {"type": "plex", "base_url": "http://plex:32400", "token": "my-plex-token"}
        assert _is_secret_ref(config, "token") is True

    def test_token_with_env_is_not_ref(self):
        """token field with token_env → env var is the credential path."""
        config = {"type": "plex", "base_url": "http://plex:32400", "token_env": "PLEX_TOKEN"}
        assert _is_secret_ref(config, "token") is False

    def test_api_key_without_env_is_ref(self):
        """api_key field without api_key_env → treated as reference."""
        config = {"type": "sonarr", "base_url": "http://sonarr:8989", "api_key": "my-sonarr-key"}
        assert _is_secret_ref(config, "api_key") is True

    def test_api_key_with_env_is_not_ref(self):
        """api_key field with api_key_env → env var is the credential path."""
        config = {"type": "sonarr", "base_url": "http://sonarr:8989", "api_key_env": "SONARR_API_KEY"}
        assert _is_secret_ref(config, "api_key") is False

    def test_empty_field_is_not_ref(self):
        """Empty/missing field is not a reference."""
        config = {"type": "plex", "base_url": "http://plex:32400"}
        assert _is_secret_ref(config, "token") is False


class TestBuildAdapterSecretRef:
    """build_adapter refuses to pass secret references as credentials."""

    def test_plex_ref_not_passed_as_credential(self):
        """A config with token="my-plex-token" (no token_env) returns None."""
        config = {
            "type": "plex",
            "base_url": "http://plex:32400",
            "token": "my-plex-token",
        }
        adapter = build_adapter(config)
        assert adapter is None

    def test_sonarr_ref_not_passed_as_credential(self):
        """A config with api_key="my-sonarr-key" (no api_key_env) returns None."""
        config = {
            "type": "sonarr",
            "base_url": "http://sonarr:8989",
            "api_key": "my-sonarr-key",
        }
        adapter = build_adapter(config)
        assert adapter is None

    def test_env_var_indirection_works(self, monkeypatch):
        """token_env pointing to a real env var works."""
        monkeypatch.setenv("PLEX_TOKEN", "actual-secret-value")
        config = {
            "type": "plex",
            "base_url": "http://plex:32400",
            "token_env": "PLEX_TOKEN",
        }
        adapter = build_adapter(config)
        assert adapter is not None

    def test_api_key_env_indirection_works(self, monkeypatch):
        """api_key_env pointing to a real env var works."""
        monkeypatch.setenv("SONARR_API_KEY", "actual-api-key")
        config = {
            "type": "sonarr",
            "base_url": "http://sonarr:8989",
            "api_key_env": "SONARR_API_KEY",
        }
        adapter = build_adapter(config)
        assert adapter is not None

    def test_default_env_var_works(self, monkeypatch):
        """Default env var (PLEX_TOKEN) works when no explicit env field."""
        monkeypatch.setenv("PLEX_TOKEN", "actual-secret-value")
        config = {
            "type": "plex",
            "base_url": "http://plex:32400",
        }
        adapter = build_adapter(config)
        assert adapter is not None

    def test_no_credential_returns_none(self):
        """No credential at all returns None."""
        config = {
            "type": "plex",
            "base_url": "http://plex:32400",
        }
        adapter = build_adapter(config)
        assert adapter is None

    def test_ref_value_never_reaches_adapter(self):
        """Regression: "my-plex-token" must NOT become X-Plex-Token header.

        The test proves that a value like "my-plex-token" (which could
        be a vault reference) is never passed to the adapter as a
        credential. If the adapter were created, it would send
        X-Plex-Token: my-plex-token to Plex — which is wrong.
        """
        config = {
            "type": "plex",
            "base_url": "http://plex:32400",
            "token": "my-plex-token",
        }
        adapter = build_adapter(config)
        # adapter is None → the reference was NOT passed as a credential
        assert adapter is None

    def test_missing_base_url_returns_none(self):
        """Missing base_url returns None."""
        config = {"type": "plex", "token_env": "PLEX_TOKEN"}
        assert build_adapter(config) is None

    def test_unknown_type_returns_none(self):
        """Unknown provider type returns None."""
        config = {"type": "unknown", "base_url": "http://x"}
        assert build_adapter(config) is None
