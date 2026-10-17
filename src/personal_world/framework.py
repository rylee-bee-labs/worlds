"""Framework conformance validator for the front door (ADR-0008 decision 3).

After ADR-0008 retired ADR-0001's capability registry for front-door providers,
this module validates the *new* product instead of the old world model. The gate
it drives (``personal-world framework validate``) checks:

- every config object loads through the real
  :class:`~personal_world.worlds.config_store.ConfigStore` (schema, ids,
  cross-references, ``extra=forbid``), read-only, with a plain violation per
  invalid object and the last-valid-config semantics untouched;
- no inline secret material anywhere in config: only a symbolic ``secret_ref``
  (``env:`` / ``vault:`` / ``file:``); a defence-in-depth key/value scan backs up
  the C1 models;
- every shipped recipe under ``config/recipes/`` loads through the recipe loader,
  declares ``verified`` and ``status``, uses only synthetic hosts, and carries no
  secret value;
- the zero-provider baseline: the app boots with an EMPTY config dir and answers
  ``/healthz`` and ``GET /api/boards/home`` (200, ``first_run`` true) with no
  provider and no model;
- the core compose file has no provider boot dependency;
- shareable Memory exports (``/api/memory/export/{table}``) carry no secret-bearing
  key/value.

It also keeps the Play-Nice participant-pack gate, which ADR-0008 does not touch.

It imports only ``personal_world.worlds.*`` modules (plus the standard library and
``yaml``). The old ``personal_world.{app,model,world,init,journal,providers,api,
auth,identity,chat,vault}`` modules are never imported here, so this gate survives
their deletion. The old-rule mapping lives in ``docs/rebuild/FRAMEWORK-GATE.md``.
"""

from __future__ import annotations

import json
import re
import tempfile
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

from .worlds.config_store import ConfigInvalid, ConfigStore
from .worlds.models import SECRET_REF_RE
from .worlds.recipes import RecipeError, _is_placeholder, is_public_read_only, load_recipe, recipes_dir

SECRET_KEY_RE = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|credential|private[_-]?key)$"
)
ALLOWED_REF_KEYS = {
    "token_env", "api_key_env", "secret_ref", "password_env", "env",
}
# Compose dependency keys that, when pointing at a provider service,
# would make that provider a core boot dependency.
COMPOSE_DEP_KEYS = ("depends_on", "links", "volumes_from", "network_mode")


@dataclass
class Violation:
    rule: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover -- display only
        return f"[{self.rule}] {self.detail}"


@dataclass
class ValidationResult:
    ok: bool = True
    violations: list[Violation] = field(default_factory=list)

    def add(self, rule: str, detail: str) -> None:
        self.ok = False
        self.violations.append(Violation(rule=rule, detail=detail))

    def extend(self, other: "ValidationResult") -> None:
        if not other.ok:
            self.ok = False
        self.violations.extend(other.violations)


def _scan_secretish(value: Any, path: str, out: ValidationResult) -> None:
    """Recursively reject inline secret material and non-symbolic secret refs.

    A key that looks like secret material is refused unless it is one of the
    allowed symbolic reference keys; a ``secret_ref`` value must itself be an
    ``env:`` / ``vault:`` / ``file:`` reference. This is a defence in depth on
    top of the C1 models (which use ``extra=forbid``), because a model may still
    allow a free-form mapping such as a request's ``query``.
    """
    if isinstance(value, dict):
        for k, v in value.items():
            key_path = f"{path}.{k}"
            key = str(k)
            if key in ALLOWED_REF_KEYS:
                if key == "secret_ref" and v is not None and not _is_secret_ref(v):
                    out.add(
                        "secret-rule",
                        f"'{key_path}' must be a symbolic reference "
                        "(env:NAME, vault:NAME or file:NAME)",
                    )
                continue
            if SECRET_KEY_RE.search(key):
                out.add(
                    "secret-rule",
                    f"field '{key_path}' looks like inline secret material; use "
                    "a symbolic reference (env:NAME, vault:NAME or file:NAME)",
                )
                continue
            _scan_secretish(v, key_path, out)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _scan_secretish(v, f"{path}[{i}]", out)


def _is_secret_ref(value: Any) -> bool:
    return isinstance(value, str) and bool(SECRET_REF_RE.match(value))


# ---------------------------------------------------------------------------
# 1 + 2. config: real ConfigStore load, cross-references, no inline secrets
# ---------------------------------------------------------------------------


def validate_config(store: ConfigStore) -> ValidationResult:
    """Validate an already-loaded C1 config store, read-only.

    ``ConfigStore`` validates each file's schema, id and ``extra=forbid`` on
    load; files that fail are reported through ``store.errors()`` and keep the
    last valid object active (the store's own semantics, untouched here).
    Cross-references (request.provider, card requests, board cards,
    action.request and the action/request policy) are validated through the
    store's authoritative reference check, which a read-only load does not run
    by itself. The returned result never writes to the config dir.
    """
    out = ValidationResult()
    for err in store.errors():
        where = err.get("path") or err.get("id") or "config"
        out.add("config-invalid", f"{where}: {err.get('message', 'invalid config')}")
    for kind, obj in store.iter_all():
        try:
            store._check_references(kind, obj)  # the store's own reference rules
        except ConfigInvalid as exc:
            out.add("config-reference", str(exc))
        _scan_secretish(obj.model_dump(mode="json"), f"{kind}[{obj.id}]", out)
    return out


def validate_config_dir(config_dir: str | Path) -> ValidationResult:
    """Load ``config_dir`` through the real ``ConfigStore`` and validate it."""
    return validate_config(ConfigStore(config_dir))


# ---------------------------------------------------------------------------
# 3. shipped recipes
# ---------------------------------------------------------------------------

#: The literal secret-shaped strings the existing room-recipe test rejects.
_ROOM_SECRET_MARKERS = ("Bearer ", "password", "api_key")


def _check_room_recipe(directory: Path, recipe: Any, out: ValidationResult) -> None:
    """The existing ``test_room_recipes`` oracle, reused for room recipes."""
    provider = recipe.provider
    ref = provider.auth.secret_ref or ""
    if not ref.startswith("env:"):
        out.add(
            "recipe-room-secret-ref",
            f"room recipe '{directory.name}' auth.secret_ref must be an env: name",
        )
    if provider.principal_id != "your-person-id":
        out.add(
            "recipe-room-principal",
            f"room recipe '{directory.name}' must keep the your-person-id placeholder",
        )
    if ref.startswith("env:") and recipe.info.env != [ref.split(":", 1)[1]]:
        out.add(
            "recipe-room-env",
            f"room recipe '{directory.name}' info.env must list only its secret name",
        )
    text = ""
    for name in ("provider.yaml", "recipe.yaml"):
        path = directory / name
        if path.is_file():
            text += path.read_text(encoding="utf-8")
    for marker in _ROOM_SECRET_MARKERS:
        if marker in text:
            out.add(
                "recipe-room-secret",
                f"room recipe '{directory.name}' contains secret-shaped text {marker!r}",
            )


def validate_recipes(root: str | Path | None = None) -> ValidationResult:
    """Validate every shipped recipe under ``root`` (default ``config/recipes``)."""
    out = ValidationResult()
    base = Path(root) if root is not None else recipes_dir()
    if not base.is_dir():
        out.add("recipe-discovery", f"recipes directory '{base}' does not exist")
        return out

    found = False
    for directory in sorted(p for p in base.iterdir() if p.is_dir()):
        if not (directory / "recipe.yaml").is_file():
            continue
        found = True
        try:
            raw = yaml.safe_load((directory / "recipe.yaml").read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            out.add("recipe-invalid", f"{directory.name}/recipe.yaml is unreadable")
            continue
        if not isinstance(raw, dict):
            out.add(
                "recipe-invalid",
                f"{directory.name}/recipe.yaml top level must be a mapping",
            )
            continue
        for key in ("verified", "status"):
            if key not in raw:
                out.add(
                    f"recipe-{key}",
                    f"recipe '{directory.name}' does not declare '{key}'",
                )
        try:
            recipe = load_recipe(directory.name, base)
        except RecipeError as exc:
            out.add("recipe-invalid", str(exc))
            continue
        provider = recipe.provider
        if provider is None:
            out.add("recipe-invalid", f"recipe '{directory.name}' has no provider.yaml")
        else:
            if not _is_placeholder(provider.base_url) and not is_public_read_only(recipe):
                out.add(
                    "recipe-placeholder",
                    f"recipe '{directory.name}' base_url is not a synthetic host",
                )
            if provider.public_url and not _is_placeholder(provider.public_url):
                out.add(
                    "recipe-placeholder",
                    f"recipe '{directory.name}' public_url is not a synthetic host",
                )
            if recipe.info.status == "room":
                _check_room_recipe(directory, recipe, out)
            _scan_secretish(
                provider.model_dump(mode="json"),
                f"recipe:{directory.name}:provider",
                out,
            )
        _scan_secretish(
            recipe.info.model_dump(mode="json"), f"recipe:{directory.name}", out
        )
        for bucket, label in (
            (recipe.requests, "request"),
            (recipe.cards, "card"),
            (recipe.actions, "action"),
        ):
            for obj in bucket:
                _scan_secretish(
                    obj.model_dump(mode="json"),
                    f"recipe:{directory.name}:{label}:{obj.id}",
                    out,
                )
    if not found:
        out.add("recipe-discovery", f"no recipes found under '{base}'")
    return out


# ---------------------------------------------------------------------------
# 4. zero-provider / zero-model baseline boot
# ---------------------------------------------------------------------------


def _build_empty_app(config_dir: str | Path) -> Any:
    """The smallest front-door app: a fixed principal, an empty config dir."""
    from .worlds.server import build_app

    return build_app(config_dir, principal_dependency=lambda: "owner")


def validate_zero_provider_boot(
    *, app_factory: Callable[[str | Path], Any] | None = None
) -> ValidationResult:
    """Boot with an EMPTY config dir and prove the baseline answers.

    ``/healthz`` must be 200/ok and ``GET /api/boards/home`` must be 200 with
    ``first_run`` true: the front door works with zero providers and no model
    (ADR-0008 decision 2). ``app_factory`` is injectable so the failing fixture
    can supply a broken app without touching the real one.
    """
    out = ValidationResult()
    build = app_factory or _build_empty_app
    with tempfile.TemporaryDirectory(prefix="pw-framework-boot-") as directory:
        app = build(directory)
        with warnings.catch_warnings():
            # fastapi.testclient/starlette emit a deprecation notice on httpx;
            # the gate's stdout stays clean.
            warnings.simplefilter("ignore")
            from fastapi.testclient import TestClient

            client = TestClient(app)
            health = client.get("/healthz")
            if health.status_code != 200 or not health.json().get("ok"):
                out.add(
                    "boot-baseline",
                    f"/healthz answered {health.status_code} with an empty config dir",
                )
            home = client.get("/api/boards/home")
            if home.status_code != 200:
                out.add(
                    "boot-baseline",
                    f"GET /api/boards/home answered {home.status_code} with an empty config dir",
                )
            elif home.json().get("first_run") is not True:
                out.add(
                    "boot-baseline",
                    "GET /api/boards/home did not report first_run true with an empty config dir",
                )
    return out


# ---------------------------------------------------------------------------
# 5. compose: no provider boot dependency (unchanged meaning)
# ---------------------------------------------------------------------------


def validate_compose_file(path: Path, provider_service_names: set[str]) -> ValidationResult:
    """Reject core compose boot dependencies on provider services.

    A service listed in ``provider_service_names`` is an optional provider; no
    other core service may depend on it. Provider-side services may depend on
    each other or the core; the constraint under test is the core's freedom.
    """
    out = ValidationResult()
    if not path.exists():
        return out
    compose = yaml.safe_load(path.read_text()) or {}
    for svc_name, svc in compose.get("services", {}).items():
        if svc_name in provider_service_names:
            continue
        for dep_key in COMPOSE_DEP_KEYS:
            deps = svc.get(dep_key)
            if deps is None:
                continue
            targets = list(deps.keys()) if isinstance(deps, dict) else list(deps)
            for target in targets:
                if target in provider_service_names:
                    out.add(
                        "compose-additive",
                        f"core service '{svc_name}' has {dep_key} on "
                        f"provider service '{target}'; optional providers "
                        "must be additive, not boot dependencies",
                    )
    return out


def _default_compose_path() -> Path:
    return Path(__file__).resolve().parents[2] / "compose.yaml"


# ---------------------------------------------------------------------------
# 6. shareable Memory exports carry no secret-bearing key/value
# ---------------------------------------------------------------------------


def validate_export_rows(rows: Iterable[Any]) -> ValidationResult:
    """Scan export rows (dicts) for secret-looking keys/values."""
    out = ValidationResult()
    for i, row in enumerate(rows):
        _scan_secretish(row, f"export[{i}]", out)
    return out


def validate_memory_exports() -> ValidationResult:
    """Run the real C4 export path over a throwaway store and scan every row."""
    from .worlds.db import Database
    from .worlds.memory_store import MemoryStore

    out = ValidationResult()
    with tempfile.TemporaryDirectory(prefix="pw-framework-export-") as directory:
        db = Database.in_dir(directory)
        try:
            store = MemoryStore(db)
            for table in ("kept", "later", "records", "history"):
                rows = [json.loads(line) for line in store.export_ndjson(table, actor="owner")]
                out.extend(validate_export_rows(rows))
        finally:
            db.close()
    return out


# ---------------------------------------------------------------------------
# 6b. participant packs (Play-Nice gate; ADR-0008 does not touch it)
# ---------------------------------------------------------------------------

PACK_REQUIRED_TOP_KEYS = (
    "schema",
    "id",
)


def validate_participant_packs(
    participants_dir: Path,
    project_root: Path | None = None,
) -> ValidationResult:
    """Validate participant packs under ``participants_dir``.

    This is the canonical Play-Nice participant-pack gate for Project
    Worlds. It is intentionally project-neutral (is in the
    ``personal_world`` package, not in any harness config) so it can be
    driven from any agent harness, CI, or a human running pytest.

    Scope: only files named ``participant.yaml`` are treated as the
    participant record itself. Sidecar files
    (``capabilities.yaml``, ``help-routing.yaml``, ``attestation.yaml``,
    ``interaction.md``, ``ONBOARDING.md``) live alongside the
    participant record and are referenced from it via
    ``capabilities_file``, ``interaction_file``, etc.; they are NOT
    participant records and are out of scope for this validator.
    Concretely: a participant pack is one directory containing one
    ``participant.yaml`` plus optional sidecars.

    Checks (deterministic, fail-closed):

    - every ``participant.yaml`` under ``participants_dir`` parses with
      ``yaml.safe_load``; malformed YAML is a hard violation
      (``pack-parse``).
    - every pack declares at minimum the ``schema`` and ``id`` keys
      (``pack-shape``); missing keys fail closed.
    - no two packs may share the same ``id`` (``pack-id-collision``).
    - the ``schema`` value, if present, must be a string starting with
      ``play-nice/`` (``pack-schema-namespace``). This is a coarse
      shape check; per-schema structural validation lives upstream in
      ``play-nice-contracts`` and is not duplicated here.

    The function does NOT validate cross-pack contracts, run contract
    attestation, or interpret semantics beyond the schema string. That
    is the role of the canonical ``play-nice-contracts`` library and
    belongs upstream, not in this project.

    The function is pure and side-effect free; it does not write any
    file under ``participants_dir``.
    """
    out = ValidationResult()
    root = Path(participants_dir)
    if not root.exists():
        out.add("pack-discovery", f"participants directory '{root}' does not exist")
        return out
    if not root.is_dir():
        out.add("pack-discovery", f"participants path '{root}' is not a directory")
        return out

    yaml_files = sorted(p for p in root.rglob("participant.yaml") if p.is_file())
    if not yaml_files:
        out.add(
            "pack-discovery",
            f"no participant.yaml files found under '{root}' "
            f"(a participant pack is one directory containing "
            f"participant.yaml plus optional sidecars)",
        )
        return out

    seen_ids: dict[str, Path] = {}
    for path in yaml_files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            out.add("pack-read", f"could not read '{path}': {exc}")
            continue
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            msg = str(exc).splitlines()[0] if exc else "unknown"
            out.add("pack-parse", f"'{path}' is not valid YAML: {msg}")
            continue
        if not isinstance(data, dict):
            out.add(
                "pack-shape",
                f"'{path}' top-level YAML is not a mapping "
                f"(got {type(data).__name__})",
            )
            continue
        for required_key in PACK_REQUIRED_TOP_KEYS:
            if required_key not in data:
                out.add(
                    "pack-shape",
                    f"'{path}' is missing required top-level key "
                    f"'{required_key}'",
                )
        schema_val = data.get("schema")
        if schema_val is not None:
            if not isinstance(schema_val, str) or not schema_val.startswith("play-nice/"):
                out.add(
                    "pack-schema-namespace",
                    f"'{path}' schema must be a string starting with "
                    f"'play-nice/' (got {schema_val!r})",
                )
        pack_id = data.get("id")
        if isinstance(pack_id, str):
            if pack_id in seen_ids:
                out.add(
                    "pack-id-collision",
                    f"participant id '{pack_id}' is declared in both "
                    f"'{seen_ids[pack_id]}' and '{path}'",
                )
            else:
                seen_ids[pack_id] = path
    return out


# ---------------------------------------------------------------------------
# the whole gate
# ---------------------------------------------------------------------------


def validate_framework(
    config_dir: str | Path,
    *,
    recipes_root: str | Path | None = None,
    compose_path: str | Path | None = None,
) -> ValidationResult:
    """Run every retained framework rule for the front door.

    Read-only with respect to ``config_dir``; the only writes are to private
    temporary directories used by the boot and export probes.
    """
    out = ValidationResult()
    store = ConfigStore(config_dir)
    out.extend(validate_config(store))
    out.extend(validate_recipes(recipes_root))
    provider_names = {obj.id for kind, obj in store.iter_all() if kind == "provider"}
    path = Path(compose_path) if compose_path is not None else _default_compose_path()
    out.extend(validate_compose_file(path, provider_names))
    out.extend(validate_zero_provider_boot())
    out.extend(validate_memory_exports())
    return out
