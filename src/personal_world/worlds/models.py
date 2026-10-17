"""C1 config models (docs/rebuild/CONTRACTS.md). Every file carries schema_version: 1."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

ID_RE = r"^[a-z0-9][a-z0-9-]{0,62}$"
REQUEST_ID_RE = r"^[a-z0-9][a-z0-9-]{0,62}\.[a-z0-9][a-z0-9-]{0,62}$"
SECRET_REF_RE = re.compile(r"^(env|vault|file):[A-Za-z_][A-Za-z0-9_.-]*$")
# Request headers are an ALLOW-list (C1). Credentials come only from the provider's auth block.
ALLOWED_HEADERS = {
    "accept", "accept-language", "content-type", "user-agent", "if-none-match", "if-modified-since",
    "idempotency-key",  # required by C3 for actions that declare idempotency
}

Id = Annotated[str, StringConstraints(pattern=ID_RE)]
RequestId = Annotated[str, StringConstraints(pattern=REQUEST_ID_RE)]


def _check_path(path: str | None) -> str | None:
    """Reject a path outside the JSONPath subset at save time, not at first render."""
    if path is not None:
        from .mapping import MappingError, parse_path

        try:
            parse_path(path)
        except MappingError as exc:
            raise ValueError(str(exc)) from None
    return path


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1


# Header names a credential may NOT be placed in: framing, hop-by-hop, proxy and forwarding headers.
FORBIDDEN_AUTH_HEADERS = {
    "host", "cookie", "set-cookie", "transfer-encoding", "content-length", "content-type", "connection", "upgrade",
    "te", "trailer", "keep-alive", "expect", "authorization", "proxy-authorization", "proxy-authenticate",
    "proxy-connection", "forwarded", "via", "x-real-ip", "origin", "referer", "accept", "user-agent", "range",
    "idempotency-key", "if-match", "if-none-match", "if-modified-since", "content-encoding", "accept-encoding",
}
_TOKEN_HEADER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$")


def check_auth_header_name(name: str) -> str:
    """A credential header must be a plain token name outside the framing/forwarding set."""
    low = name.lower()
    if not _TOKEN_HEADER.match(name):
        raise ValueError("header_name must be letters, digits and hyphens only")
    if low in FORBIDDEN_AUTH_HEADERS or low.startswith(("x-forwarded-", "proxy-", "sec-")):
        raise ValueError(f"header_name {name!r} cannot carry a credential (use auth.type bearer for Authorization)")
    return name


def check_auth_path(value: str | None, *, field: str) -> str | None:
    """A credential endpoint path: relative to the provider, with no scheme, host, query or ``..``.

    Shared by the login/token paths a provider's own auth flow POSTs to. The sender joins the path
    under ``base_url`` + ``path_prefix``, so it must not be able to escape them — the same rule C1
    applies to a request path.
    """
    if value is None:
        return value
    if (not value.startswith("/") or value.startswith("//") or "://" in value or "\\" in value
            or "?" in value or ".." in value.split("/")):
        raise ValueError(f"{field} must be a plain path starting with /")
    return value


class Auth(BaseModel):
    """How a provider authenticates. Values are never here: ``secret_ref`` names them.

    ``cookie_session`` describes a login POST whose ``Set-Cookie`` answer is held in memory by
    the sender (C1). A username is not strictly a secret, but every credential-ish value in this
    repo travels by ``secret_ref``, so the login takes the whole pair from one secret
    (``username:password``, the same convention ``basic`` uses) rather than write a literal
    username into config. Thus ``cookie_session`` needs only ``secret_ref`` and ``login_path``.
    ``login_path`` is where the credential is POSTed; ``username_field``/``password_field`` name
    the form fields that carry it. A cookie can never be a request header:
    :data:`FORBIDDEN_AUTH_HEADERS` keeps ``cookie``/``set-cookie`` out of ``header_name``, and the
    sender attaches the session internally instead.

    ``password_grant`` describes an OAuth2-style resource-owner-password grant (deliberately not
    named after the OAuth2 grant name): the sender POSTs the same ``username:password`` secret to
    ``token_path`` and sends the token the endpoint returns as ``Authorization: Bearer ...``.
    ``token_path`` is the token endpoint; ``token_field`` names the response key that carries the
    token (default ``access_token``). The username travels with the password in the one
    ``secret_ref`` (``username:password``) — the same convention as ``basic`` and
    ``cookie_session`` — so no literal username is written to config and no second secret is
    introduced. The token is held in the sender's memory only and never becomes config.
    """

    model_config = ConfigDict(extra="forbid")
    type: Literal["none", "bearer", "header", "basic", "cookie_session", "password_grant"] = "none"
    header_name: str | None = None
    secret_ref: str | None = None
    # cookie_session only: the login endpoint and the form fields it reads.
    login_path: str | None = None
    username_field: str = "username"
    password_field: str = "password"
    # password_grant only: the token endpoint and the response key that carries the token.
    token_path: str | None = None
    token_field: str = "access_token"
    # Capabilities (the <name> half of a request id, ``<provider>.<name>``) that may receive this credential.
    # ``None`` is the legacy unscoped state: the credential is for the whole provider. ``[]`` allows none.
    scope: list[Id] | None = None

    @field_validator("header_name")
    @classmethod
    def _header(cls, v: str | None) -> str | None:
        return check_auth_header_name(v) if v is not None else v

    @field_validator("login_path")
    @classmethod
    def _login_path(cls, v: str | None) -> str | None:
        return check_auth_path(v, field="login_path")

    @field_validator("token_path")
    @classmethod
    def _token_path(cls, v: str | None) -> str | None:
        return check_auth_path(v, field="token_path")

    @field_validator("username_field", "password_field", "token_field")
    @classmethod
    def _form_field(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", v or ""):
            raise ValueError("auth form field names must be simple names")
        return v

    @model_validator(mode="after")
    def _check(self) -> "Auth":
        if self.type == "none":
            if self.secret_ref:
                raise ValueError("auth.type none must not have secret_ref")
            if self.login_path:
                raise ValueError("login_path is only for auth.type cookie_session")
            if self.token_path:
                raise ValueError("token_path is only for auth.type password_grant")
            return self
        if not self.secret_ref or not SECRET_REF_RE.match(self.secret_ref):
            raise ValueError("secret_ref must be env:NAME, vault:NAME or file:NAME")
        if self.type == "header" and not self.header_name:
            raise ValueError("auth.type header needs header_name")
        if self.type == "cookie_session":
            if not self.login_path:
                raise ValueError("auth.type cookie_session needs login_path")
        elif self.login_path:
            raise ValueError("login_path is only for auth.type cookie_session")
        if self.type == "password_grant":
            if not self.token_path:
                raise ValueError("auth.type password_grant needs token_path")
        elif self.token_path:
            raise ValueError("token_path is only for auth.type password_grant")
        return self


class Network(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lan: bool = False


class Provider(_Strict):
    id: Id
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["http", "room0", "reference"]
    base_url: str
    path_prefix: str = ""
    auth: Auth = Field(default_factory=Auth)
    network: Network = Field(default_factory=Network)
    # Who approves operations on this provider. None: room0 providers are governed by Project Home
    # (fail closed), everything else by Worlds.
    governance: Literal["worlds", "project_home"] | None = None
    # room0 providers only: who Worlds speaks for (sent as X-Worlds-Principal, never a free header), the
    # room's public origin (to build links), and the lane its cards land in.
    principal_id: str | None = None
    public_url: str | None = None
    group: Literal["life", "machine"] = "machine"
    tls_verify: bool = True
    timeout_s: float = Field(default=5, gt=0, le=15)
    max_bytes: int = Field(default=2 * 1024 * 1024, gt=0, le=8 * 1024 * 1024)

    @model_validator(mode="after")
    def _room_fields(self) -> "Provider":
        if self.principal_id is not None:
            if self.kind != "room0":
                raise ValueError("principal_id is only for room0 providers")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.principal_id):
                raise ValueError("principal_id must match [A-Za-z0-9_-]{1,64}")
        if self.public_url is not None:
            if self.kind != "room0":
                raise ValueError("public_url is only for room0 providers")
            parts = urlsplit(self.public_url)
            if parts.scheme not in ("http", "https") or not parts.hostname or parts.path not in ("", "/") \
                    or parts.query or parts.fragment or parts.username is not None:
                raise ValueError("public_url must be scheme://host[:port] only")
        return self

    def governed_by_project_home(self) -> bool:
        return self.governance == "project_home" or (self.governance is None and self.kind == "room0")

    @field_validator("base_url")
    @classmethod
    def _base(cls, v: str) -> str:
        if not re.match(r"^https?://[^/\s@]+(/[^\s]*)?$", v):
            raise ValueError("base_url must be http(s)://host[:port][/path] without userinfo")
        parts = urlsplit(v)
        if parts.username is not None or parts.password is not None or parts.query or parts.fragment:
            raise ValueError("base_url must not carry userinfo, query or fragment")
        return v

    @field_validator("path_prefix")
    @classmethod
    def _prefix(cls, v: str) -> str:
        if v and (not v.startswith("/") or ".." in v.split("/") or "://" in v):
            raise ValueError("path_prefix must be an absolute path without ..")
        return v


class Assertion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: int | None = None
    path: str | None = None
    exists: bool | None = None
    is_list: bool | None = None
    equals: Any = None

    @model_validator(mode="after")
    def _check(self) -> "Assertion":
        if self.status is None and self.path is None:
            raise ValueError("assertion needs status or path")
        _check_path(self.path)
        return self


class Request(_Strict):
    id: RequestId
    provider: Id
    method: Literal["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    path: str
    query: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    body: Any = None
    effect: Literal["auto", "read", "write"] = "auto"
    known_safe: bool = False
    ttl_s: int = Field(default=60, ge=0, le=86400)
    timeout_s: float | None = Field(default=None, gt=0, le=15)
    assertions: list[Assertion] = Field(default_factory=list)
    # Where this read shape came from, and whether a read-only check vouched for it. The defaults claim least.
    provenance: Literal["owner", "discovered", "provider_declared"] = "owner"
    verified: bool = False

    @field_validator("path")
    @classmethod
    def _path(cls, v: str) -> str:
        if not v.startswith("/") or "://" in v or v.startswith("//") or "\\" in v:
            raise ValueError("path must be relative to the provider (start with /, no scheme or host)")
        if ".." in v.split("?")[0].split("/") or "%2e" in v.lower() or "%2f" in v.lower():
            raise ValueError("path must not contain .. or encoded separators")
        from .templates import has_template

        if has_template(v):
            raise ValueError("templates like {today} are only allowed in query values")
        return v

    @field_validator("query")
    @classmethod
    def _query(cls, v: dict[str, str]) -> dict[str, str]:
        from .templates import check_query_value

        for value in v.values():
            check_query_value(value)
        return v

    @field_validator("headers")
    @classmethod
    def _headers(cls, v: dict[str, str]) -> dict[str, str]:
        bad = [h for h in v if h.lower() not in ALLOWED_HEADERS]
        if bad:
            raise ValueError(f"headers not allowed (allow-list: {sorted(ALLOWED_HEADERS)}): {bad}")
        from .templates import has_template

        for name, value in v.items():
            if any(c in f"{name}{value}" for c in ("\r", "\n", "\x00")):
                raise ValueError("header contains a control character")
            if has_template(value):
                raise ValueError("templates like {today} are only allowed in query values")
        return v

    @model_validator(mode="after")
    def _prefix(self) -> "Request":
        if not self.id.startswith(self.provider + "."):
            raise ValueError("request id must be <provider>.<name>")
        return self

    def resolved_effect(self) -> Literal["read", "write"]:
        base = "read" if self.method in ("GET", "HEAD") else "write"
        if self.effect == "write":
            return "write"
        if self.effect == "read":
            if base == "write" and not self.known_safe:
                return "write"  # never lower write to read without known_safe
            return "read"
        return base


class Field_(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    label: str
    format: Literal["number", "percent", "bytes", "duration", "relative_time", "text", "count"] = "text"
    unit: str | None = None

    @field_validator("path")
    @classmethod
    def _jsonpath(cls, v: str) -> str:
        return _check_path(v) or v


class Meaning(BaseModel):
    model_config = ConfigDict(extra="forbid")
    concept: str
    short: str
    full: str = ""


class Above(BaseModel):
    """A threshold (C1.3): when the first extracted value is a number above ``value``, the card is in ``state``."""

    model_config = ConfigDict(extra="forbid")
    value: float
    state: Literal["needs_attention", "degraded"]

    @field_validator("value")
    @classmethod
    def _finite(cls, v: float) -> float:
        import math

        if isinstance(v, bool) or not math.isfinite(v):
            raise ValueError("above.value must be a finite number")
        return v


class StatusMap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str

    @field_validator("path")
    @classmethod
    def _jsonpath(cls, v: str) -> str:
        return _check_path(v) or v

    healthy: list[Any] = Field(default_factory=list)
    needs_attention: list[Any] = Field(default_factory=list)
    # first: the first extracted value decides. all / any: every extracted value counts (C1.3).
    mode: Literal["first", "all", "any"] = "first"
    # What an EXISTING but empty list means (e.g. a health list with no problems). A missing path is always unknown.
    empty: Literal["unknown", "healthy"] = "unknown"
    # A numeric threshold, checked before the healthy / needs_attention lists.
    above: Above | None = None


_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _check_ref(v: Any, *, allow_number: bool) -> Any:
    """A meter source: a number, a JSONPath ($...), or the key of one of the card's fields."""
    if v is None:
        return v
    if isinstance(v, bool):
        raise ValueError("meter source must be a number, a $ path or a field key")
    if isinstance(v, (int, float)):
        if not allow_number:
            raise ValueError("this meter source cannot be a literal number")
        return v
    if isinstance(v, str):
        if v.startswith("$"):
            _check_path(v)
            return v
        if _KEY_RE.match(v):
            return v
    raise ValueError("meter source must be a number, a $ path or a field key")


class Meter(BaseModel):
    """Which card data feeds the meter (C1). The envelope carries the resolved numbers (C2)."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["segments", "bars", "progress", "marks", "dots", "day", "shelf"]
    value: Any = None      # progress: field key or path
    max: Any = None        # progress: number, field key or path
    count: Any = None      # segments: number, field key or path
    filled: Any = None     # segments: number, field key or path
    items: str | None = None  # bars/marks/dots/day/shelf: path to a list

    @field_validator("value")
    @classmethod
    def _v(cls, v: Any) -> Any:
        return _check_ref(v, allow_number=False)

    @field_validator("max", "count", "filled")
    @classmethod
    def _n(cls, v: Any) -> Any:
        return _check_ref(v, allow_number=True)

    @field_validator("items")
    @classmethod
    def _i(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("$"):
            raise ValueError("meter items must be a $ path to a list")
        return _check_path(v)

    @model_validator(mode="after")
    def _shape(self) -> "Meter":
        if self.type == "progress" and self.value is None:
            raise ValueError("a progress meter needs value")
        if self.type == "segments" and (self.count is None or self.filled is None):
            raise ValueError("a segments meter needs count and filled")
        return self


class Card(_Strict):
    id: Id
    title: str = Field(min_length=1, max_length=120)
    icon: str = "circle"
    group: Literal["life", "machine"] = "machine"
    request: RequestId | None = None
    requests: list[RequestId] = Field(default_factory=list)
    view: Literal["stat", "list", "table", "status", "meter", "link", "markdown"] = "stat"
    meaning: Meaning
    fields: list[Field_] = Field(default_factory=list)
    meter: Meter | None = None
    status: StatusMap | None = None

    @model_validator(mode="after")
    def _one_source(self) -> "Card":
        if bool(self.request) == bool(self.requests):
            raise ValueError("card needs exactly one of request or requests")
        return self

    def request_ids(self) -> list[str]:
        return [self.request] if self.request else list(self.requests)


class BoardItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    card: Id
    size: Literal["S", "M", "L"] = "M"
    hidden: bool = False


class Board(_Strict):
    id: Id
    title: str = Field(min_length=1, max_length=120)
    home: bool = False
    items: list[BoardItem] = Field(default_factory=list)


class Action(_Strict):
    id: Id
    request: RequestId
    name: str = Field(min_length=1, max_length=120)
    access: Literal["read", "write"] = "write"
    approval: Literal["never", "always"] = "always"
    scope: str = ""
    idempotency: Literal["required", "optional", "none"] = "optional"
    exposed: bool = False
    # Anything but "adopted" is inert: not visible to an agent, never authorized, never consumed.
    state: Literal["proposed", "adopted", "refused", "expired"] = "adopted"
    # Only an owner (config writes are owner-only) can waive approval for a request that WRITES.
    owner_waives_approval: bool = False

    @model_validator(mode="after")
    def _waiver_needs_never(self) -> "Action":
        if self.owner_waives_approval and self.approval != "never":
            raise ValueError("owner_waives_approval only makes sense with approval: never")
        return self


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def scope_allows(provider: Provider, request: Request) -> bool:
    """May this provider's credential go to this request's capability? ``scope`` None is unscoped: yes.

    A decision about capabilities, so it lives with Worlds' models and is made at the call site, never in the transport.
    """
    scope = getattr(provider.auth, "scope", None)
    return scope is None or str(request.id).partition(".")[2] in scope


def send_scoped(send: Any, provider: Provider, request: Request, *, effect: str) -> Any:
    """Call ``send``, handing it the scope verdict. Only a refusal is passed, so a sender that predates it still works."""
    if scope_allows(provider, request):
        return send(provider, request, effect=effect)
    return send(provider, request, effect=effect, in_scope=False)


def action_version(action: Action, request: Request, provider: Provider) -> str:
    """sha256 of the canonicalized resolved action + request + provider destination.

    Computed, never written. Covers destination and credential ref (not the secret value).
    """
    action_d, request_d, auth_d = (action.model_dump(mode="json"), request.model_dump(mode="json"),
                                   provider.auth.model_dump(mode="json"))
    # Fields added later are left out at their defaults, so a version computed before they existed still matches.
    if action.state == "adopted":
        action_d.pop("state")
    if request.provenance == "owner" and not request.verified:
        request_d.pop("provenance")
        request_d.pop("verified")
    if provider.auth.scope is None:
        auth_d.pop("scope")
    payload = {
        "action": action_d,
        "request": request_d,
        "provider": {
            "id": provider.id,
            "kind": provider.kind,
            "base_url": provider.base_url,
            "path_prefix": provider.path_prefix,
            "auth": auth_d,
            "network": provider.network.model_dump(mode="json"),
            "tls_verify": provider.tls_verify,
        },
    }
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()
