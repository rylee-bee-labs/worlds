"""Resolve secret references in connection config.

A connection field marked ``secret_ref`` holds a reference, never a value:

- ``env:NAME`` or ``${NAME}``: an environment variable of the Worlds process.
- ``vault://NAME``, ``vault:NAME`` or a bare name like ``plex-token``: a
  secret in the native vault, readable only while the vault is unlocked.

Resolution never logs or returns a value to a caller other than the
provider that needs it. ``secret_status`` reports, in plain words, whether
each reference can be used, so the UI can say "needs your vault unlocked"
instead of failing quietly.
"""

from __future__ import annotations

import os
import re
from typing import Any

_vault: Any = None

_ENV_RE = re.compile(r"^(?:env:([A-Za-z_][A-Za-z0-9_]*)|\$\{([A-Za-z_][A-Za-z0-9_]*)\})$")
_VAULT_RE = re.compile(r"^(?:vault://|vault:)([A-Za-z0-9_.-]+)$")
_NAME_RE = re.compile(r"^[a-z0-9]+([-_][a-z0-9]+)+$")

# Fields that may carry a reference, by convention across providers.
SECRET_FIELDS = ("token", "api_key", "password", "client_secret")


def set_vault(vault: Any) -> None:
    """Register the process vault (called once when the API starts)."""
    global _vault
    _vault = vault


def _parse(value: str) -> tuple[str, str] | None:
    m = _ENV_RE.match(value)
    if m:
        return "env", m.group(1) or m.group(2)
    m = _VAULT_RE.match(value)
    if m:
        return "vault", m.group(1)
    if _NAME_RE.fullmatch(value):
        return "vault", value
    return None


def _lookup(kind: str, name: str) -> tuple[str | None, str]:
    """Return (value, state). state is a short plain phrase."""
    if kind == "env":
        value = os.environ.get(name, "")
        return (value, "ready") if value else (None, f"not set in the environment ({name})")
    if _vault is None:
        return None, "no vault on this Worlds"
    if not getattr(_vault, "is_unlocked", False):
        return None, "needs your vault unlocked"
    value = _vault.get(name)
    return (value, "ready") if value else (None, f"not in your vault ({name})")


def resolve_secrets(entry: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``entry`` with resolvable secret references filled in.

    Unresolvable references are left as they are; providers already refuse
    reference-shaped values, so an unresolved field degrades to "not
    configured" rather than sending the reference upstream.
    """
    out = dict(entry)
    for field in SECRET_FIELDS:
        value = entry.get(field)
        if not isinstance(value, str) or not value or entry.get(f"{field}_env"):
            continue
        ref = _parse(value)
        if ref is None:
            continue
        resolved, _state = _lookup(*ref)
        if resolved:
            out[field] = resolved
    return out


def secret_status(entry: dict[str, Any]) -> dict[str, str]:
    """Plain status per secret field; never includes a value."""
    status: dict[str, str] = {}
    for field in SECRET_FIELDS:
        env_name = entry.get(f"{field}_env")
        if isinstance(env_name, str) and env_name:
            status[field] = "ready" if os.environ.get(env_name) else f"not set in the environment ({env_name})"
            continue
        value = entry.get(field)
        if not isinstance(value, str) or not value:
            continue
        ref = _parse(value)
        status[field] = "ready" if ref is None else _lookup(*ref)[1]
    return status
