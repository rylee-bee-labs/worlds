"""Secure secret vault: encrypted at rest, no external dependencies.

The vault stores secrets in an encrypted file using Fernet symmetric
encryption (AES-128-CBC with HMAC-SHA256). The key is derived from a
master passphrase using PBKDF2-SHA256 with 600,000 iterations.

No external services required. The vault works standalone. For users
who already have SOPS or OpenBao, provider adapters can delegate to
those systems instead.

Migration path:
  1. Start: built-in vault (this module)
  2. Later: connect SOPS provider (same VaultContract interface)
  3. Later: connect OpenBao provider (same VaultContract interface)

The vault never logs secret values. Audit entries record names only.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from .envelope import Result, fail, ok

# Real encryption uses `cryptography` (Fernet). The dependency stays
# optional for minimal installs, but without it the vault FAILS CLOSED:
# unlock returns `unavailable` and no secret is ever stored. There is no
# base64 fallback — base64 is not encryption (see unlock()).
try:
    from cryptography.fernet import Fernet, InvalidToken

    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False

PBKDF2_ITERATIONS = 600_000
"""OWASP-recommended minimum for PBKDF2-SHA256 (2024)."""


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 32-byte Fernet key from a passphrase and salt."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=32,
    )
    import base64

    return base64.urlsafe_b64encode(dk)


class Vault:
    """Encrypted secret store backed by a single file.

    The vault is unlocked with a master passphrase. Secrets are
    encrypted at rest and decrypted only in memory. The passphrase
    is never stored — only a derived key is in memory.
    """

    def __init__(self, path: Path, master_passphrase: str | None = None) -> None:
        self.path = path
        self._secrets: dict[str, str] = {}
        self._unlocked = False
        self._fernet: Any = None
        self._salt: bytes = b""
        self._warning: str | None = None

        if not _HAS_CRYPTO:
            self._warning = (
                "cryptography package not installed; vault is "
                "unavailable. Install with: pip install cryptography"
            )

        if master_passphrase:
            self.unlock(master_passphrase)

    @property
    def is_unlocked(self) -> bool:
        return self._unlocked

    @property
    def warning(self) -> str | None:
        return self._warning

    def unlock(self, passphrase: str) -> Result:
        """Unlock the vault with the master passphrase.

        If the vault file exists, decrypt it. If not, initialize a
        new vault with a fresh salt.

        Requires the cryptography package for real encryption.
        Without it, unlock fails closed — base64 is not encryption.
        """
        if not _HAS_CRYPTO:
            return fail(
                "unavailable",
                warnings=[
                    "cryptography package not installed; vault cannot "
                    "unlock without real encryption. Install with: "
                    "pip install cryptography"
                ],
            )

        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text())
                self._salt = bytes.fromhex(payload["salt"])
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                return fail("corrupt", warnings=[f"vault file corrupt: {e}"])

            key = _derive_key(passphrase, self._salt)
            self._fernet = Fernet(key)
            try:
                encrypted = payload["data"].encode()
                decrypted = self._fernet.decrypt(encrypted)
                self._secrets = json.loads(decrypted)
            except (InvalidToken, json.JSONDecodeError):
                return fail(
                    "unauthorized",
                    warnings=["wrong passphrase or corrupt vault"],
                )
        else:
            self._salt = os.urandom(16)
            key = _derive_key(passphrase, self._salt)
            self._fernet = Fernet(key)
            self._secrets = {}

        self._unlocked = True
        return ok("healthy", data={"secrets": len(self._secrets)})

    def lock(self) -> None:
        """Lock the vault, clearing decrypted secrets from memory."""
        self._secrets.clear()
        self._unlocked = False
        self._fernet = None

    def _require_unlocked(self) -> None:
        if not self._unlocked:
            raise RuntimeError("vault is locked")

    def get(self, name: str) -> str | None:
        """Get a secret value by name. Returns None if not found."""
        self._require_unlocked()
        return self._secrets.get(name)

    def set(self, name: str, value: str) -> Result:
        """Store a secret. Overwrites if exists."""
        self._require_unlocked()
        self._secrets[name] = value
        self._save()
        return ok("healthy", data={"name": name})

    def delete(self, name: str) -> Result:
        """Delete a secret by name."""
        self._require_unlocked()
        if name not in self._secrets:
            return fail("not_found", warnings=[f"secret '{name}' not found"])
        del self._secrets[name]
        self._save()
        return ok("healthy", data={"name": name})

    def list_names(self) -> list[str]:
        """List secret names (never values)."""
        self._require_unlocked()
        return sorted(self._secrets.keys())

    def audit(self) -> Result:
        """Audit: names, count, last modified. Never values.

        Reports actual encryption capability — not a hardcoded claim.
        """
        self._require_unlocked()
        return ok(
            "healthy",
            data={
                "count": len(self._secrets),
                "names": self.list_names(),
                "encrypted": _HAS_CRYPTO and self._fernet is not None,
            },
        )

    def _save(self) -> None:
        """Encrypt and save the vault to disk. Requires cryptography."""
        self._require_unlocked()
        if not _HAS_CRYPTO or not self._fernet:
            raise RuntimeError(
                "vault cannot save without cryptography package"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)

        data = json.dumps(self._secrets).encode()
        encrypted = self._fernet.encrypt(data).decode()

        payload = {
            "salt": self._salt.hex(),
            "data": encrypted,
            "version": 1,
            "secrets_count": len(self._secrets),
            "updated_at": time.time(),
        }
        self.path.write_text(json.dumps(payload, indent=2))


class VaultContract:
    """Provider contract for secret management.

    The built-in Vault implements this. SOPS and OpenBao adapters
    also implement this. The interface is the same — the user can
    swap providers without changing their workflow.
    """

    def get(self, name: str) -> str | None:
        raise NotImplementedError

    def set(self, name: str, value: str) -> Result:
        raise NotImplementedError

    def delete(self, name: str) -> Result:
        raise NotImplementedError

    def list_names(self) -> list[str]:
        raise NotImplementedError

    def audit(self) -> Result:
        raise NotImplementedError


class SOPSVaultAdapter(VaultContract):
    """Adapter for SOPS-encrypted secrets.

    Reads from a SOPS-encrypted YAML/JSON file. Writes are not
    supported (SOPS is the write path). This is a read-through
    provider for users who already have SOPS workflows.
    """

    def __init__(self, sops_file: Path) -> None:
        self.sops_file = sops_file
        self._cache: dict[str, str] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        import subprocess  # nosec B404  # drives the operator's own `sops` CLI, argument-list form only

        try:
            proc = subprocess.run(  # nosec  # B603 and B607 both apply to this call — argument list, no shell; `sops` is the operator's own binary on PATH
                ["sops", "-d", str(self.sops_file)],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            import yaml

            self._cache = yaml.safe_load(proc.stdout) or {}
        except Exception:
            self._cache = {}
        self._loaded = True

    def get(self, name: str) -> str | None:
        self._load()
        return self._cache.get(name)

    def set(self, name: str, value: str) -> Result:
        return fail(
            "unsupported",
            warnings=["SOPS adapter is read-only; use sops CLI to write"],
        )

    def delete(self, name: str) -> Result:
        return fail(
            "unsupported",
            warnings=["SOPS adapter is read-only; use sops CLI to delete"],
        )

    def list_names(self) -> list[str]:
        self._load()
        return sorted(self._cache.keys())

    def audit(self) -> Result:
        self._load()
        return ok(
            "healthy",
            data={
                "count": len(self._cache),
                "names": self.list_names(),
                "source": "sops",
                "file": str(self.sops_file),
            },
        )
