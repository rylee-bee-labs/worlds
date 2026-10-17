"""Recipe templates: sanitized C1 config for a homelab service, installed into the owner's config.

A recipe is a directory under ``config/recipes/<name>/``::

    recipe.yaml            name, title, summary, status (ready | room | planned), note, env (secret NAMES the provider uses)
    provider.yaml          C1 provider with a placeholder base_url (``*.lan.example``) and an ``env:NAME`` secret_ref
    requests/<name>.yaml   C1 requests (read-only; the one exception is a request an action points at)
    cards/<id>.yaml        C1 cards
    actions/<id>.yaml      C1 actions (approval: always, exposed: false)

Real hostnames, domains and keys never live in a recipe. ``install`` writes the objects through the same
:class:`ConfigStore` the API uses, so they get the same validation, references and etags.

``status`` has three values, not two:

* ``ready`` - an ordinary HTTP service: the provider, requests, cards and actions are installed.
* ``room`` - a ``kind: room0`` provider with no card files: the room maps its own cards through C8, so
  ``install`` writes the provider only and invents no request/card/action files. It is listed and
  installable, but it is deliberately not a member of the HTTP-shaped ``ready`` set (an HTTP recipe always
  ships cards), so this honest third marker keeps the two kinds apart.
* ``planned`` - listed but not installable yet; ``note`` says what it waits for.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config_store import ConfigStore
from .models import Action, Card, Id, Provider, Request, check_auth_header_name

__all__ = [
    "Recipe",
    "RecipeError",
    "RecipeInfo",
    "from_openapi",
    "install",
    "list_recipes",
    "load_recipe",
    "recipes_dir",
]

PLACEHOLDER_SUFFIXES = (".example", ".example.com", ".example.org", ".example.net")
#: The only real internet hosts a shipped recipe may name (Rylee, 2026-10-17: "Let Worlds read GitHub directly",
#: for Buzzby's release card). See ``is_public_read_only``; everything else stays a LAN template.
PUBLIC_READ_ONLY_HOSTS = ("api.github.com",)


class RecipeError(Exception):
    """A recipe cannot be loaded or installed; the message is safe to show."""


class RecipeInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    name: Id
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=400)
    #: ready = HTTP service, installable; room = room0 provider, installable provider-only;
    #: planned = listed, cannot be installed yet (``note`` says why).
    status: str = Field(default="ready", pattern="^(ready|room|planned)$")
    note: str = ""
    #: True only once a foreman has checked the shapes read-only against a real service. Recipes start unverified.
    verified: bool = False
    #: The secret NAMES the provider reads (never values).
    env: list[str] = Field(default_factory=list)


@dataclass
class Recipe:
    info: RecipeInfo
    provider: Provider | None = None
    requests: list[Request] = field(default_factory=list)
    cards: list[Card] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)


def recipes_dir() -> Path:
    """``$PW_RECIPES_DIR``, else ``config/recipes`` next to the source tree."""
    env = os.environ.get("PW_RECIPES_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config" / "recipes").is_dir():
            return parent / "config" / "recipes"
    return Path("config/recipes")


def _read(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RecipeError(f"{path.name}: unreadable ({type(exc).__name__})") from None
    if not isinstance(data, dict):
        raise RecipeError(f"{path.name}: top level must be a mapping")
    return data


def _model(model: type[BaseModel], path: Path) -> Any:
    try:
        return model.model_validate(_read(path))
    except RecipeError:
        raise
    except Exception as exc:  # pydantic ValidationError: keep it short, never echo values
        raise RecipeError(f"{path.parent.name}/{path.name}: invalid ({str(exc).splitlines()[0][:160]})") from None


def list_recipes(root: Path | None = None) -> list[RecipeInfo]:
    base = root or recipes_dir()
    out: list[RecipeInfo] = []
    if not base.is_dir():
        return out
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        if (d / "recipe.yaml").is_file():
            out.append(_model(RecipeInfo, d / "recipe.yaml"))
    return out


def load_recipe(name: str, root: Path | None = None) -> Recipe:
    base = root or recipes_dir()
    d = base / name
    if not (d / "recipe.yaml").is_file() or "/" in name or ".." in name:
        raise RecipeError(f"no recipe named {name!r}")
    info = _model(RecipeInfo, d / "recipe.yaml")
    if info.name != name:
        raise RecipeError(f"recipe.yaml name {info.name!r} does not match its directory {name!r}")
    recipe = Recipe(info=info)
    if (d / "provider.yaml").is_file():
        recipe.provider = _model(Provider, d / "provider.yaml")
    for sub, model, bucket in (("requests", Request, recipe.requests), ("cards", Card, recipe.cards), ("actions", Action, recipe.actions)):
        folder = d / sub
        if folder.is_dir():
            for f in sorted(folder.glob("*.yaml")):
                bucket.append(_model(model, f))
    return recipe


# ---------------------------------------------------------------- OpenAPI import
#
# ``from_openapi`` turns an already-parsed OpenAPI 3.x document into a *skeleton*: a C1 provider and
# GET/HEAD-only request objects the owner reviews before saving. It is pure (no file, network or
# environment access) and defensive, because the document is untrusted input:
#
# * only GET and HEAD operations become requests; every other method is listed in ``skipped``;
# * every id, path and parameter name is validated against the C1 patterns and dropped (and reported)
#   if it does not fit - a bad id can never become a config path;
# * path templates (``/pets/{petId}``) are documented, never substituted;
# * ``servers[]`` is ignored; the skeleton carries a synthetic placeholder address the owner replaces;
# * only local ``#/`` refs are followed; a remote ref is skipped and reported;
# * the document is bounded (size, nesting, node count, operation count) so a hostile file cannot hang
#   the loader or exhaust memory;
# * auth schemes map only to C1's bearer/header/basic; anything else (oauth2, openIdConnect, a cookie
#   or query apiKey) becomes a TODO note and the result carries ``needs_auth: "unknown"`` - ``none`` is
#   never chosen silently for an auth scheme the skeleton did not understand. Secret values never appear.

#: A synthetic address, never copied from ``servers[]``. The owner supplies the real one at install time.
PLACEHOLDER_BASE_URL = "https://example.invalid"

#: Bounds; a document past any of these is refused with a plain :class:`RecipeError`.
MAX_OPERATIONS = 200
MAX_DOC_BYTES = 2_000_000
MAX_DEPTH = 40
MAX_NODES = 200_000

_METHOD_KEYS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
_READ_METHODS = frozenset({"get", "head"})
_WRITE_METHODS = frozenset({"post", "put", "patch", "delete"})
_WRITE_REASON = "write-like: needs an approved action"
_PARAM_RE = re.compile(r"\{([^{}]+)\}")
_PARAM_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_REQUEST_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    """A C1 id body from free text: lowercase, runs of anything else become one ``-``, max 63 chars."""
    return _SLUG_RE.sub("-", text.lower()).strip("-")[:63].strip("-")


def _hostile_name(raw: Any) -> bool:
    """True for a name that looks like an injection/traversal attempt rather than an identifier."""
    if not isinstance(raw, str):
        return True
    if any(ord(c) < 32 or ord(c) == 127 for c in raw):
        return True
    return "/" in raw or "\\" in raw or ".." in raw


def _check_bounds(doc: Any) -> None:
    """Refuse a document that is too large, nests too deeply or holds too many nodes."""
    try:
        encoded = json.dumps(doc, default=str)
    except RecursionError:
        raise RecipeError("openapi: the document nests too deeply") from None
    except (TypeError, ValueError):
        raise RecipeError("openapi: the document is not plain JSON data") from None
    if len(encoded) > MAX_DOC_BYTES:
        raise RecipeError(f"openapi: the document is too large ({len(encoded)} bytes; limit {MAX_DOC_BYTES})")
    stack: list[tuple[Any, int]] = [(doc, 1)]
    nodes = 0
    while stack:
        node, depth = stack.pop()
        nodes += 1
        if nodes > MAX_NODES:
            raise RecipeError("openapi: the document has too many nested values")
        if depth > MAX_DEPTH:
            raise RecipeError("openapi: the document nests too deeply")
        children = node.values() if isinstance(node, dict) else node if isinstance(node, list) else ()
        for child in children:
            if isinstance(child, (dict, list)):
                stack.append((child, depth + 1))


def _check_version(doc: dict[str, Any]) -> None:
    """Only OpenAPI 3.x is understood; a Swagger 2.0 or unknown version is refused, not guessed."""
    version = doc.get("openapi")
    if isinstance(version, str):
        if not version.startswith("3."):
            raise RecipeError(f"openapi: only OpenAPI 3.x documents are supported (found {version!r})")
    elif "swagger" in doc:
        raise RecipeError("openapi: only OpenAPI 3.x documents are supported (this looks like Swagger 2.0)")


def _resolve_local_ref(doc: dict[str, Any], ref: Any) -> tuple[Any, str | None]:
    """Follow a local ``#/...`` JSON pointer; any other ref is not resolved. Returns (node, reason)."""
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return None, "external $ref not resolved"
    node: Any = doc
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None, "local $ref target not found"
    return node, None


def _deref(doc: dict[str, Any], node: Any) -> tuple[Any, str | None]:
    """Resolve a node that is itself a ``$ref`` (path item or operation)."""
    if isinstance(node, dict) and "$ref" in node:
        return _resolve_local_ref(doc, node.get("$ref"))
    return node, None


def _template_names(path: str) -> list[str]:
    return _PARAM_RE.findall(path)


def _secret_ref(provider_id: str, scheme_name: str) -> str:
    """A safe placeholder ``env:NAME`` for an auth scheme. A name only, never a value."""
    safe = re.sub(r"[^A-Z0-9_]", "_", f"{provider_id}_{scheme_name}".upper())
    safe = re.sub(r"_{2,}", "_", safe).strip("_")
    if not safe or not re.match(r"^[A-Za-z_]", safe):
        safe = "OPENAPI_" + (safe or "TOKEN")
    return f"env:{safe}"


def _map_scheme(scheme: dict[str, Any], provider_id: str, scheme_name: str) -> dict[str, Any] | None:
    """Map one security scheme to a C1 auth block, or None when it is not one C1 understands."""
    kind = scheme.get("type")
    ref = _secret_ref(provider_id, scheme_name)
    if kind == "http":
        sub = scheme.get("scheme")
        if isinstance(sub, str) and sub.lower() == "bearer":
            return {"type": "bearer", "secret_ref": ref}
        if isinstance(sub, str) and sub.lower() == "basic":
            return {"type": "basic", "secret_ref": ref}
        return None
    if kind == "apiKey" and scheme.get("in") == "header":
        header = scheme.get("name")
        if not isinstance(header, str):
            return None
        try:
            check_auth_header_name(header)
        except ValueError:
            return None
        return {"type": "header", "header_name": header, "secret_ref": ref}
    return None


def _security_order(doc: dict[str, Any]) -> list[str]:
    """Scheme names named by the top-level ``security`` requirement, in order."""
    order: list[str] = []
    security = doc.get("security")
    if isinstance(security, list):
        for requirement in security:
            if isinstance(requirement, dict):
                order.extend(k for k in requirement if isinstance(k, str))
    return order


def _map_auth(doc: dict[str, Any], provider_id: str) -> tuple[dict[str, Any], str, list[str]]:
    """Return (auth block, needs_auth word, notes). An unknown scheme is never silently ``none``."""
    components = doc.get("components")
    schemes = components.get("securitySchemes") if isinstance(components, dict) else None
    if not isinstance(schemes, dict) or not schemes:
        return {"type": "none"}, "none", []
    order = _security_order(doc)
    names = [n for n in order if n in schemes] + [n for n in schemes if n not in order]
    notes: list[str] = []
    mapped: dict[str, Any] | None = None
    unknown = False
    for scheme_name in names:
        scheme = schemes.get(scheme_name)
        if not isinstance(scheme, dict):
            unknown = True
            notes.append(f"TODO: security scheme {scheme_name!r} is malformed; set auth by hand (needs_auth unknown)")
            continue
        auth = _map_scheme(scheme, provider_id, scheme_name)
        if auth is None:
            unknown = True
            notes.append(
                f"TODO: security scheme {scheme_name!r} (type {scheme.get('type')!r}) is not mapped to C1 "
                f"auth; set auth by hand (needs_auth unknown)"
            )
            continue
        if mapped is None:
            mapped = auth
        else:
            notes.append(f"security scheme {scheme_name!r} is an alternative that was not mapped")
    if mapped is None:
        return {"type": "none"}, "unknown", notes
    return mapped, ("unknown" if unknown else "configured"), notes


def _provider_identity(doc: dict[str, Any]) -> tuple[str, str, str]:
    """Return (provider id, display name, note explaining the id)."""
    info = doc.get("info")
    title = info.get("title") if isinstance(info, dict) else None
    if isinstance(title, str) and title.strip():
        slug = _slug(title)
        name = title.strip()[:120]
    else:
        slug = ""
        name = "Imported API"
    provider_id = slug or "imported"
    return provider_id, name, f"provider id {provider_id!r} was derived from the document title; rename it before saving"


def _collect_parameters(
    doc: dict[str, Any], owners: tuple[Any, ...], skipped: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Documented parameters from path-item and operation level; local refs followed, remote refs skipped."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for owner in owners:
        raw = owner.get("parameters") if isinstance(owner, dict) else None
        if not isinstance(raw, list):
            continue
        for entry in raw:
            if not isinstance(entry, dict):
                skipped.append({"reason": "parameter must be a mapping"})
                continue
            if "$ref" in entry:
                ref = entry.get("$ref")
                resolved, reason = _resolve_local_ref(doc, ref)
                if reason:
                    skipped.append({"ref": str(ref), "reason": reason})
                    continue
                entry = resolved
                if not isinstance(entry, dict):
                    skipped.append({"ref": str(ref), "reason": "ref target is not a mapping"})
                    continue
            name = entry.get("name")
            location = entry.get("in")
            if not isinstance(name, str) or not _PARAM_NAME_RE.fullmatch(name):
                skipped.append({"name": str(name), "reason": "invalid parameter name"})
                continue
            if location not in ("path", "query", "header", "cookie"):
                skipped.append({"name": name, "reason": "invalid parameter location"})
                continue
            key = (name, location)
            if key in seen:
                continue
            seen.add(key)
            out.append({"name": name, "in": location, "required": bool(entry.get("required"))})
    return out


def _document_parameters(notes: list[str], method: str, path: str, params: list[dict[str, Any]]) -> None:
    for param in params:
        name, location = param["name"], param["in"]
        if location == "path":
            notes.append(
                f"{method} {path}: path parameter {name!r} is documented; the template is kept as written - "
                f"supply a value before use"
            )
        elif location == "query":
            notes.append(
                f"{method} {path}: query parameter {name!r} is documented but not filled; add it with a literal "
                f"value or a known template such as {{today}}"
            )
        else:
            notes.append(
                f"{method} {path}: {location} parameter {name!r} was not copied (credentials come only from "
                f"the provider auth block)"
            )


def _request_name(raw_operation_id: Any, method: str, path: str) -> str | None:
    """A safe ``<name>`` for ``<provider>.<name>``; None when the source is missing or hostile."""
    if raw_operation_id is None:
        source = f"{method}-{path}"
    elif isinstance(raw_operation_id, str):
        if _hostile_name(raw_operation_id):
            return None
        source = raw_operation_id
    else:
        return None
    slug = _slug(source)
    return slug if _REQUEST_NAME_RE.fullmatch(slug) else None


def _build_request(
    doc: dict[str, Any],
    provider_id: str,
    method: str,
    path: str,
    path_item: dict[str, Any],
    operation: dict[str, Any],
    skipped: list[dict[str, Any]],
    notes: list[str],
) -> dict[str, Any] | None:
    raw_operation_id = operation.get("operationId")
    name = _request_name(raw_operation_id, method, path)
    if name is None:
        skipped.append({"method": method, "path": path, "reason": "operationId is missing or not a safe id"})
        return None
    request_id = f"{provider_id}.{name}"
    for template in _template_names(path):
        if not _PARAM_NAME_RE.fullmatch(template):
            skipped.append({"method": method, "path": path, "reason": f"invalid path parameter name {template!r}"})
            return None

    params = _collect_parameters(doc, (path_item, operation), skipped)
    declared = {(p["name"], p["in"]) for p in params}
    for template in _template_names(path):
        if (template, "path") not in declared:
            params.append({"name": template, "in": "path", "required": True})
    _document_parameters(notes, method.upper(), path, params)

    candidate = {
        "schema_version": 1,
        "id": request_id,
        "provider": provider_id,
        "method": method.upper(),
        "path": path,
        "effect": "read",
        "ttl_s": 60,
    }
    try:
        Request.model_validate(candidate)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(part) for part in first.get("loc", ())) or "request"
        skipped.append({"method": method, "path": path, "id": request_id, "reason": f"invalid request: {loc} {first.get('msg', 'is invalid')}"})
        return None
    return candidate


def from_openapi(doc: dict[str, Any]) -> dict[str, Any]:
    """Turn an OpenAPI 3.x document (already parsed) into a sanitised C1 provider + read-only request skeletons.

    Returns ``{provider, requests, skipped, notes, needs_auth}``. ``provider`` and each entry of
    ``requests`` are plain dicts in the C1 shapes, so both validate as :class:`Provider` / :class:`Request`
    (and install through :class:`ConfigStore`). Anything dropped is in ``skipped`` with a reason; anything
    the owner should know (derived ids, documented path parameters, an unmapped auth scheme) is in ``notes``.

    Pure: nothing is read from disk, the network or the environment. A document that is not a mapping,
    is not OpenAPI 3.x, or is too large / too deep / too complex raises :class:`RecipeError` with a plain
    message.
    """
    if not isinstance(doc, dict):
        raise RecipeError("openapi: the document must be a mapping")
    _check_bounds(doc)
    _check_version(doc)

    notes: list[str] = []
    skipped: list[dict[str, Any]] = []
    provider_id, name, id_note = _provider_identity(doc)
    notes.append(id_note)
    notes.append(
        f"base_url is a synthetic placeholder ({PLACEHOLDER_BASE_URL}); servers[] is ignored - pass the real "
        f"address at install time"
    )
    auth, needs_auth, auth_notes = _map_auth(doc, provider_id)
    notes.extend(auth_notes)

    provider = {
        "schema_version": 1,
        "id": provider_id,
        "name": name,
        "kind": "http",
        "base_url": PLACEHOLDER_BASE_URL,
        "auth": auth,
        "network": {"lan": False},
    }

    paths = doc.get("paths")
    if not isinstance(paths, dict):
        notes.append("openapi: no paths section; nothing was imported")
        paths = {}

    requests: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    processed = 0
    truncated = False
    for path, raw_item in paths.items():
        if processed >= MAX_OPERATIONS:
            truncated = True
            break
        if not isinstance(path, str):
            skipped.append({"id": repr(path), "reason": "path key must be a string"})
            continue
        item, reason = _deref(doc, raw_item)
        if reason:
            skipped.append({"path": path, "reason": reason})
            continue
        if not isinstance(item, dict):
            skipped.append({"path": path, "reason": "path item must be a mapping"})
            continue
        for method in _METHOD_KEYS:
            if method not in item or processed >= MAX_OPERATIONS:
                if method in item:
                    truncated = True
                continue
            operation, reason = _deref(doc, item[method])
            processed += 1
            if reason:
                skipped.append({"method": method, "path": path, "reason": reason})
                continue
            if not isinstance(operation, dict):
                skipped.append({"method": method, "path": path, "reason": "operation must be a mapping"})
                continue
            if method not in _READ_METHODS:
                why = _WRITE_REASON if method in _WRITE_METHODS else "unsupported method: only GET and HEAD are imported"
                skipped.append({"method": method.upper(), "path": path, "reason": why})
                continue
            request = _build_request(doc, provider_id, method, path, item, operation, skipped, notes)
            if request is None:
                continue
            if request["id"] in seen_ids:
                skipped.append({"id": request["id"], "path": path, "reason": "duplicate request id"})
                continue
            seen_ids.add(request["id"])
            requests.append(request)
        if truncated:
            break
    if truncated:
        notes.append(f"only the first {MAX_OPERATIONS} operations were read; the rest were not imported")

    return {"provider": provider, "requests": requests, "skipped": skipped, "notes": notes, "needs_auth": needs_auth}


def _is_placeholder(base_url: str) -> bool:
    host = (urlsplit(base_url).hostname or "").lower()
    return host.endswith(PLACEHOLDER_SUFFIXES)


def is_public_read_only(recipe: Recipe) -> bool:
    """True for the narrow internet exception: https, an allowlisted host, no auth, not LAN, reads only."""
    p = recipe.provider
    if p is None or p.network.lan:
        return False
    parts = urlsplit(p.base_url)
    return (
        parts.scheme == "https"
        and (parts.hostname or "").lower() in PUBLIC_READ_ONLY_HOSTS
        and p.auth.type == "none"
        and not recipe.actions
        and all(r.method in ("GET", "HEAD") and r.resolved_effect() == "read" for r in recipe.requests)
    )


def install(
    store: ConfigStore,
    recipe: Recipe,
    *,
    base_url: str | None = None,
    secret_ref: str | None = None,
    overwrite: bool = False,
) -> list[str]:
    """Write the recipe into ``store``. Returns the ids written. Existing objects are kept unless ``overwrite``.

    ``ready`` and ``room`` recipes are installable; a ``planned`` one is not. A ``room`` recipe has a
    ``room0`` provider and no card files, so only the provider is written - the room maps its own cards
    through C8 and the install must not invent request/card/action files for it.

    The provider's placeholder ``base_url`` is never installed: the owner supplies the real one here, at install
    time, and it goes only into their own config directory. A room provider keeps its ``your-person-id``
    ``principal_id`` placeholder; the owner replaces it in their own config.
    """
    if recipe.info.status not in ("ready", "room") or recipe.provider is None:
        raise RecipeError(f"{recipe.info.name} cannot be installed yet: {recipe.info.note or 'not ready'}")
    provider = recipe.provider.model_copy(deep=True)
    if base_url:
        provider = Provider.model_validate({**provider.model_dump(mode="json"), "base_url": base_url})
    if _is_placeholder(provider.base_url):
        raise RecipeError(f"{recipe.info.name}: pass --base-url with the real address of this service (the recipe only has a placeholder)")
    if secret_ref:
        auth = {**provider.auth.model_dump(mode="json"), "secret_ref": secret_ref}
        provider = Provider.model_validate({**provider.model_dump(mode="json"), "auth": auth})

    written: list[str] = []

    def put(kind: str, obj: BaseModel) -> None:
        existing = store.etag(kind, obj.id)  # type: ignore[attr-defined]
        if existing is not None and not overwrite:
            return
        store.save(kind, obj, etag=existing)
        written.append(f"{kind}:{obj.id}")

    put("provider", provider)
    for request in recipe.requests:
        put("request", request)
    for card in recipe.cards:
        put("card", card)
    for action in recipe.actions:
        put("action", action)
    return written
