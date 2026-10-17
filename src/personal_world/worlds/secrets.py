"""Strict secret-reference resolution for the front door: ``env:NAME``, ``vault:NAME`` and ``file:NAME`` only.

``file:NAME`` is for mounted secret files: the environment variable NAME holds the PATH of a file whose content
is the secret (the value itself is never in the environment).

No bare-name guessing and no ``${NAME}`` form (the old implicit rules are gone). A value is
returned only to the caller that must send it; it is never logged here.
"""

from __future__ import annotations

import os
import re
from typing import Any

_REF = re.compile(r"^(env|vault|file):([A-Za-z_][A-Za-z0-9_.-]*)$")
_MAX_SECRET_FILE = 4096
_vault: Any = None


def set_vault(vault: Any) -> None:
    """Register the process vault (an object with ``is_unlocked`` and ``get(name)``)."""
    global _vault
    _vault = vault


def resolve_secret_ref(ref: str | None) -> str | None:
    """Return the secret value, or None when the reference is malformed, unset or locked."""
    if not isinstance(ref, str):
        return None
    m = _REF.match(ref)
    if not m:
        return None
    kind, name = m.groups()
    if kind == "env":
        return os.environ.get(name) or None
    if kind == "file":
        path = os.environ.get(name)
        if not path:
            return None
        try:
            with open(path, "rb") as handle:
                raw = handle.read(_MAX_SECRET_FILE + 1)
        except OSError:
            return None
        if len(raw) > _MAX_SECRET_FILE:
            return None  # a secret file is a token, not a document
        return raw.decode("utf-8", "replace").strip() or None
    if _vault is None or not getattr(_vault, "is_unlocked", False):
        return None
    try:
        return _vault.get(name) or None
    except Exception:
        return None
