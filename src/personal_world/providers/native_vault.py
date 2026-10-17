"""Native Vault provider: registers existing encrypted vault as secrets capability.

Project Worlds already owns encrypted vault functionality. This provider
registers that machinery as the native/default implementation of the
secrets capability. No external vault service required.
"""

from ..envelope import Result, fail, ok
from ..status import Status
from .registry import StatusContract


class NativeVaultProvider(StatusContract):
    """Native secrets capability backed by the existing encrypted vault."""

    def __init__(self, vault):
        """vault: an instance of personal_world.vault.Vault"""
        self._vault = vault

    def observe(self) -> Result:
        """Report vault status as the secrets capability."""
        try:
            is_unlocked = self._vault.is_unlocked if hasattr(self._vault, 'is_unlocked') else False
            names = []
            if is_unlocked and hasattr(self._vault, 'list_names'):
                try:
                    names = self._vault.list_names()
                except Exception:  # nosec B110  # an unreadable vault still reports its own status
                    pass
            return ok(Status.HEALTHY.value, data={
                "locked": not is_unlocked,
                "encrypted": True,
                "secret_count": len(names),
                "provider": "native_vault",
            })
        except Exception as e:
            return fail(Status.UNAVAILABLE.value, warnings=[f"vault: {e}"])

    def health(self) -> bool:
        """Vault is healthy if it exists."""
        return hasattr(self._vault, 'is_unlocked')
