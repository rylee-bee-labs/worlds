"""Owner policy: who the single owner is, and how they may sign in (``<config>/owner.yaml``).

::

    schema_version: 1
    public_origin: https://worlds.example.test     # the ONLY origin cookies/redirects are built for
    oidc:                                          # optional
      issuer: https://auth.example.test
      subject: <stable subject the provider asserts for the owner>
    bootstrap:                                     # optional local sign-in before/without OIDC
      enabled: true
      secret_ref: env:PW_BOOTSTRAP_TOKEN

The file holds no secret value. A missing or invalid file means nobody can sign in (fail closed).
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from .secrets import resolve_secret_ref

BOOTSTRAP_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{22,}$")  # >=32 hex or >=22 base64url chars (>=128 bits from a generator)


def strong_secret(value: str | None) -> bool:
    if not value or not BOOTSTRAP_SECRET_RE.match(value):
        return False
    return len(value) >= 32 if re.fullmatch(r"[0-9A-Fa-f]+", value) else True   # hex needs 32 chars (4 bits each)


class OwnerOIDC(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issuer: str
    subject: str


class Bootstrap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    secret_ref: str | None = None


class OwnerFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    public_origin: str
    oidc: OwnerOIDC | None = None
    bootstrap: Bootstrap = Bootstrap()

    @field_validator("public_origin")
    @classmethod
    def _origin(cls, v: str) -> str:
        p = urlsplit(v)
        if p.scheme not in ("http", "https") or not p.netloc or p.path not in ("", "/") or p.query or p.fragment or p.username:
            raise ValueError("public_origin must be scheme://host[:port] only")
        return f"{p.scheme}://{p.netloc}"


@dataclass(frozen=True)
class OwnerPolicy:
    file: OwnerFile | None
    error: str | None = None

    @property
    def public_origin(self) -> str | None:
        return self.file.public_origin if self.file else None

    def binding(self) -> str:
        """A hash of who the owner is. Sessions carry it; changing the identity ends every session."""
        if not self.file:
            return "none"
        o = self.file.oidc
        basis = f"{self.file.public_origin}|{o.issuer.rstrip('/')}|{o.subject}" if o else f"{self.file.public_origin}|bootstrap"
        return hashlib.sha256(basis.encode()).hexdigest()

    def is_owner_identity(self, issuer: str, subject: str) -> bool:
        o = self.file.oidc if self.file else None
        if o is None or not issuer or not subject:
            return False
        a = hmac.compare_digest(hashlib.sha256(issuer.rstrip("/").encode()).digest(), hashlib.sha256(o.issuer.rstrip("/").encode()).digest())
        b = hmac.compare_digest(hashlib.sha256(subject.encode()).digest(), hashlib.sha256(o.subject.encode()).digest())
        return bool(a and b)

    def bootstrap_matches(self, presented: str) -> bool:
        b = self.file.bootstrap if self.file else None
        if b is None or not b.enabled or not presented:
            return False
        secret = resolve_secret_ref(b.secret_ref)
        if not strong_secret(secret):   # a short secret is refused outright (fail closed)
            return False
        # compare fixed-length digests so the comparison cannot leak either length
        return hmac.compare_digest(hashlib.sha256(presented.encode()).digest(), hashlib.sha256(secret.encode()).digest())


def load_owner_policy(config_dir: str | Path) -> OwnerPolicy:
    path = Path(config_dir) / "owner.yaml"
    try:
        data: Any = yaml.safe_load(path.read_text("utf-8"))
        if not isinstance(data, dict):
            return OwnerPolicy(None, "owner.yaml must be a mapping")
        if data.get("schema_version") != 1:
            return OwnerPolicy(None, "owner.yaml schema_version must be 1")
        return OwnerPolicy(OwnerFile.model_validate(data))
    except FileNotFoundError:
        return OwnerPolicy(None, "owner.yaml not found")
    except Exception as exc:  # unreadable, bad yaml or schema: nobody signs in
        return OwnerPolicy(None, f"owner.yaml invalid: {type(exc).__name__}")
