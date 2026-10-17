"""`inspect_vault_status` truthfulness (TOOL-018).

The brain tool must report encryption capability from real state, not a
hardcoded claim. Regression for the stale base64-fallback logic that
treated any warning as "still encrypted": without the `cryptography`
extra the vault fails closed and this tool must say so.

Uses fake vault objects so the assertions hold with or without the
crypto extra installed (CI runs `--extra test` only).
"""

from personal_world.tool_registry import _vault_status


class _FakeVault:
    def __init__(self, *, fernet=None, warning=None, unlocked=False):
        self._fernet = fernet
        self._warning = warning
        self._unlocked = unlocked

    @property
    def warning(self):
        return self._warning

    @property
    def is_unlocked(self):
        return self._unlocked


def test_reports_encrypted_when_fernet_active():
    vault = _FakeVault(fernet=object(), unlocked=True)
    result = _vault_status(vault)
    assert result.ok
    assert result.data["encrypted"] is True
    assert result.data["locked"] is False
    assert "warning" not in result.data


def test_reports_not_encrypted_when_crypto_unavailable():
    vault = _FakeVault(
        fernet=None,
        warning="cryptography package not installed; vault is unavailable.",
    )
    result = _vault_status(vault)
    assert result.ok
    assert result.data["encrypted"] is False
    assert result.data["locked"] is True
    # The warning is carried through verbatim; no secret material.
    assert "unavailable" in result.data["warning"]


def test_not_encrypted_without_warning_text():
    # A vault that simply has no fernet must not be reported encrypted,
    # even when no explanatory warning string is present.
    result = _vault_status(_FakeVault(fernet=None))
    assert result.ok
    assert result.data["encrypted"] is False


def test_unavailable_when_vault_raises():
    class _Broken:
        @property
        def is_unlocked(self):
            raise RuntimeError("boom")

    result = _vault_status(_Broken())
    assert not result.ok
    assert result.status == "unavailable"
