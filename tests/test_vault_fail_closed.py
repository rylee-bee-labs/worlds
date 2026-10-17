"""Vault fail-closed tests.

Proves:
- crypto present → encrypted, vault works
- crypto unavailable → vault refuses to unlock
- status reports actual encryption capability
- no secret values enter logs
- existing secret-name-only audit behavior preserved
"""

from unittest.mock import patch

import pytest

from personal_world.vault import _HAS_CRYPTO, Vault

pytestmark = pytest.mark.skipif(
    not _HAS_CRYPTO,
    reason="cryptography package not installed (CI uses --extra test, not --extra crypto)",
)


class TestVaultCryptoPresent:
    """With cryptography installed, vault works normally."""

    def test_unlock_with_crypto(self, tmp_path):
        vault = Vault(tmp_path / "vault.enc")
        result = vault.unlock("test-passphrase")
        assert result.ok
        assert vault.is_unlocked

    def test_set_and_get(self, tmp_path):
        vault = Vault(tmp_path / "vault.enc")
        vault.unlock("test-passphrase")
        vault.set("my-secret", "secret-value")
        assert vault.get("my-secret") == "secret-value"

    def test_audit_no_values(self, tmp_path):
        vault = Vault(tmp_path / "vault.enc")
        vault.unlock("test-passphrase")
        vault.set("my-secret", "secret-value")
        result = vault.audit()
        assert result.ok
        assert "my-secret" in result.data["names"]
        # Value never appears in audit
        assert "secret-value" not in str(result.data)

    def test_encrypted_at_rest(self, tmp_path):
        path = tmp_path / "vault.enc"
        vault = Vault(path)
        vault.unlock("test-passphrase")
        vault.set("key", "value")
        # Read the raw file — value should not be plaintext
        raw = path.read_text()
        assert "value" not in raw

    def test_survives_reload(self, tmp_path):
        path = tmp_path / "vault.enc"
        v1 = Vault(path)
        v1.unlock("pass")
        v1.set("key", "value")
        # Reload
        v2 = Vault(path)
        v2.unlock("pass")
        assert v2.get("key") == "value"


class TestVaultFailClosed:
    """Without cryptography, vault refuses to operate."""

    def test_unlock_fails_without_crypto(self, tmp_path):
        vault = Vault(tmp_path / "vault.enc")
        with patch("personal_world.vault._HAS_CRYPTO", False):
            result = vault.unlock("test-passphrase")
        assert not result.ok
        assert result.status == "unavailable"
        assert not vault.is_unlocked

    def test_warning_when_no_crypto(self, tmp_path):
        with patch("personal_world.vault._HAS_CRYPTO", False):
            vault = Vault(tmp_path / "vault.enc")
        assert vault.warning is not None
        assert "unavailable" in vault.warning.lower()

    def test_set_fails_when_locked(self, tmp_path):
        vault = Vault(tmp_path / "vault.enc")
        # Don't unlock
        with pytest.raises(RuntimeError, match="locked"):
            vault.set("key", "value")

    def test_get_fails_when_locked(self, tmp_path):
        vault = Vault(tmp_path / "vault.enc")
        with pytest.raises(RuntimeError, match="locked"):
            vault.get("key")


class TestVaultStatusHonesty:
    """Status surfaces report actual encryption state."""

    def test_status_reflects_crypto_state(self, tmp_path):
        vault = Vault(tmp_path / "vault.enc")
        vault.unlock("pass")
        assert vault.is_unlocked
        # With real crypto, fernet should be set
        assert vault._fernet is not None

    def test_audit_reports_encrypted_with_crypto(self, tmp_path):
        vault = Vault(tmp_path / "vault.enc")
        vault.unlock("pass")
        result = vault.audit()
        assert result.ok
        assert result.data["encrypted"] is True


class TestVaultSecretNamesOnly:
    """Secret names appear in audit, never values."""

    def test_list_names_no_values(self, tmp_path):
        vault = Vault(tmp_path / "vault.enc")
        vault.unlock("pass")
        vault.set("api-token", "super-secret-123")
        vault.set("db-password", "hunter2")
        names = vault.list_names()
        assert "api-token" in names
        assert "db-password" in names
        assert "super-secret-123" not in str(names)
        assert "hunter2" not in str(names)

    def test_delete_by_name(self, tmp_path):
        vault = Vault(tmp_path / "vault.enc")
        vault.unlock("pass")
        vault.set("key", "value")
        result = vault.delete("key")
        assert result.ok
        assert vault.get("key") is None

    def test_delete_nonexistent(self, tmp_path):
        vault = Vault(tmp_path / "vault.enc")
        vault.unlock("pass")
        result = vault.delete("nope")
        assert not result.ok
        assert result.status == "not_found"
