"""App wiring: build a World + Registry + Journal from a config dir.

V0 persistence: the world is a JSON file (facts/intents/policies/lore/
capabilities/providers/packs/accessibility); the journal is NDJSON.
Both live under PW_DATA_DIR (volume-backed in compose).
"""

import json
from pathlib import Path
from typing import Any

from .chat_registry import build_chat_provider
from .model import (
    SCHEMA_VERSION,
    Capability,
    Fact,
    Intent,
    Lore,
    Pack,
    Policy,
    Provider,
    ProviderMode,
)
from .providers.adapters import (
    CandyDispenser,
    FakeSourceControl,
    Gitea,
    HttpStatus,
    LangGraphMemory,
)
from .providers.lab_deploy import LabDeploy
from .providers.lab_health import LabHealth
from .providers.lab_resources import LabResources
from .providers.lab_secrets import LabSecrets
from .providers.lab_settings import LabSettings
from .providers.registry import Registry, StatusContract
from .providers.workbench import WorkbenchPodman, workbench_enabled
from .source_control import NativeGit, configured_search_paths
from .world import World

# key, description, native_baseline (framework Rule 2: does the core
# itself give this capability useful local meaning with zero providers?)
STANDARD_CAPABILITIES: list[tuple[str, str, bool]] = [
    ("source_control", "Read repositories, issues, pull requests", True),
    ("secrets", "Broker secret material to consumers", False),
    ("calendar", "Observe calendar events", False),
    ("settings_validation", "Validate settings against intent", True),
    ("service_validation", "Validate service health", False),
    ("update_discovery", "Discover available updates", False),
    ("memory", "Search long-term memory", False),
    ("journal", "Read structured history", True),
    ("reasoning", "Optional AI interpretation", False),
    ("notifications", "Send notifications", False),
    ("scheduler", "Run tasks on a schedule", False),
    ("homelab_settings", "Homelab settings reconciliation", False),
    ("homelab_health", "Homelab service health monitoring", False),
    ("homelab_deploy", "Homelab deployment status", False),
    ("homelab_secrets", "Homelab secret management", False),
    ("homelab_resources", "Homelab VM resource monitoring", False),
    ("workbench", "Attach container workspaces (podman/distrobox)", False),
]


def define_standard_capabilities(registry: Registry) -> None:
    for key, _doc, _native in STANDARD_CAPABILITIES:
        registry.define_capability(key, StatusContract)


def native_baseline_capabilities() -> set[str]:
    """Capability keys whose native baseline ships with the core
    (framework Rule 2). The manifest reads this; the registry's
    native_baseline answer is 'core provides meaning without any
    provider', which is exactly this set."""
    return {key for key, _doc, native in STANDARD_CAPABILITIES if native}


def save_world(world: World, path: Path) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "facts": {k: f.model_dump(mode="json") for k, f in world.facts.items()},
        "intents": {k: i.model_dump(mode="json") for k, i in world.intents.items()},
        "policies": {k: p.model_dump(mode="json") for k, p in world.policies.items()},
        "lore": {k: entry.model_dump(mode="json") for k, entry in world.lore.items()},
        "capabilities": {
            k: c.model_dump(mode="json") for k, c in world.capabilities.items()
        },
        "providers": {
            k: [p.model_dump(mode="json") for p in v]
            for k, v in world.providers.items()
        },
        "packs": {k: p.model_dump(mode="json") for k, p in world.packs.items()},
        "accessibility": world.accessibility,
        "layout": world.layout,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def load_world(path: Path) -> World:
    world = World()
    if not path.exists():
        return world
    payload: dict[str, Any] = json.loads(path.read_text())
    version = payload.get("schema_version")
    if version is not None and version != SCHEMA_VERSION:
        raise ValueError(
            f"world.json schema_version {version!r} != {SCHEMA_VERSION!r}; "
            "explicit migration required (see docs/NATIVE-BASELINE-AND-"
            "ENRICHMENT.md, Initialization)"
        )
    for k, v in payload.get("facts", {}).items():
        world.facts[k] = Fact.model_validate(v)
    for k, v in payload.get("intents", {}).items():
        world.intents[k] = Intent.model_validate(v)
    for k, v in payload.get("policies", {}).items():
        world.policies[k] = Policy.model_validate(v)
    for k, v in payload.get("lore", {}).items():
        world.lore[k] = Lore.model_validate(v)
    for k, v in payload.get("capabilities", {}).items():
        world.capabilities[k] = Capability.model_validate(v)
    for k, items in payload.get("providers", {}).items():
        world.providers[k] = [Provider.model_validate(v) for v in items]
    for k, v in payload.get("packs", {}).items():
        world.packs[k] = Pack.model_validate(v)
    if payload.get("accessibility"):
        world.accessibility = payload["accessibility"]
    if payload.get("layout"):
        world.layout = payload["layout"]
    return world


def _read_extra_config(config_dir: Path, key: str) -> dict:
    """Read extra configuration from connections.json or connections.local.json.

    Resolves flat UI config into the nested shape native providers expect.
    """
    from .connection_manager import resolve_native_config

    raw = {}
    for name in ("connections.local.json", "connections.json"):
        path = config_dir / name
        if path.exists():
            try:
                data = json.loads(path.read_text())
                if key in data:
                    raw = data[key]
                    break
            except Exception:  # nosec B110  # probing each candidate source; a miss is the normal path
                pass
    return resolve_native_config(raw, key)


def build_registry(
    world: World,
    registry: Registry,
    config_dir: Path,
    vault=None,
    journal=None,
    data_dir: Path = None,
) -> Registry:
    """Wire providers from config/connections.json. Unknown provider
    types are skipped with a warning; the core still boots. The
    source_control native baseline is registered when no provider for
    the capability is configured (zero-provider boot); a configured
    enrichment provider takes the active slot and removal degrades back
    to this baseline on the next boot."""
    define_standard_capabilities(registry)
    registry.native_baselines = native_baseline_capabilities()

    # Load connections from tracked config + optional private override
    conn_path = config_dir / "connections.json"
    local_conn_path = config_dir / "connections.local.json"
    conns: dict[str, Any] = {}
    if conn_path.exists():
        try:
            conns = json.loads(conn_path.read_text())
        except json.JSONDecodeError:
            conns = {}
    # Merge private connections (local overrides)
    if local_conn_path.exists():
        try:
            local_conns = json.loads(local_conn_path.read_text())
            existing = conns.get("connections", [])
            local = [
                c for c in local_conns.get("connections", []) if isinstance(c, dict)
            ]
            conns["connections"] = existing + local
        except json.JSONDecodeError:
            pass
    connections = [c for c in conns.get("connections", []) if isinstance(c, dict)]

    # Native baseline (see comment above)
    if not any(c.get("capability") == "source_control" for c in connections):
        try:
            from .source_control import config_recursive_flag

            git_impl = NativeGit(
                configured_search_paths(config_dir),
                recurse=config_recursive_flag(config_dir),
            )
            registry.register(
                "source_control",
                "native-git",
                git_impl,
                health_check=git_impl.git_available,
                writes="none",
                mode=ProviderMode.NATIVE,
                required=False,
            )
        except Exception:  # native baseline must never block boot
            registry.native_baselines.discard("source_control")

    # Traefik ingress rollups (ROADMAP Next): read-only over the LAN
    # router API; reports a degraded state when the API is missing.
    try:
        from .providers.traefik_ingress import TraefikIngress

        traefik = TraefikIngress()
        registry.register(
            "ingress",
            "traefik",
            traefik,
            health_check=lambda: True,
            writes="none",
            mode=ProviderMode.NATIVE,
            required=False,
        )
    except Exception:  # nosec B110  # an optional capability that is simply not configured
        pass

    for conn in connections:
        ptype = conn.get("type")
        name = conn.get("name")
        capability = conn.get("capability")
        if not all([ptype, name, capability]):
            continue
        mode = ProviderMode(conn.get("mode", ProviderMode.ENRICHMENT.value))
        required = bool(conn.get("required", False))
        if ptype == "http_status":
            url = conn.get("url")
            if url:
                impl = HttpStatus(name, url, conn.get("expected", 200))
                registry.register(
                    capability,
                    name,
                    impl,
                    health_check=impl.probe,
                    writes="none",
                    mode=mode,
                    required=required,
                )
        elif ptype == "gitea":
            base = conn.get("base_url")
            if base:
                impl = Gitea(base, conn.get("token_env", ""))
                registry.register(
                    capability,
                    name,
                    impl,
                    health_check=lambda impl=impl: impl.observe().ok,
                    writes="none",
                    mode=mode,
                    required=required,
                )
                # Generic forge adapter (enrichment): adds remote-side
                # richness on top of the native git baseline; the native
                # canonical shape (source_control.py) is unchanged by it.
                # Supported live source-control enrichment today is
                # GitHub via the gh CLI (providers/github.py); this
                # adapter stays as substitution-proof machinery.
        elif ptype == "langgraph":
            base = conn.get("base_url")
            if base:
                impl = LangGraphMemory(base, conn.get("api_key_env"))
                registry.register(
                    capability,
                    name,
                    impl,
                    health_check=impl.health,
                    writes="none",
                    mode=mode,
                    required=required,
                )
        elif ptype in ("ollama", "openai_compat", "opencode", "openai", "anthropic"):
            # Chat/reasoning providers use the same fail-closed registry:
            # an unreachable local model is 'unavailable', never a crash.
            built = build_chat_provider(conn)
            if built is not None:
                cname, impl = built
                registry.register(
                    capability or "reasoning",
                    cname,
                    impl,
                    health_check=lambda i=impl: i.observe().ok,
                    writes="none",
                    mode=mode,
                    required=required,
                )
        elif ptype == "fake_source_control":
            # Reference provider for substitution proofs (framework E):
            # same SourceControlContract, deterministic, no external
            # system. Never a production dependency.
            impl = FakeSourceControl(conn.get("version", "fake-1.0"))
            registry.register(
                capability,
                name,
                impl,
                health_check=lambda: True,
                writes="none",
                mode=mode,
                required=required,
            )
        elif ptype == "candy":
            base = conn.get("base_url")
            if base:
                impl = CandyDispenser(base)
                registry.register(
                    capability,
                    name,
                    impl,
                    health_check=lambda impl=impl: impl.health().ok,
                    writes="none",
                    mode=mode,
                    required=required,
                )
        elif ptype == "lab_api":
            # Lab API provider: connects to the lab API server for
            # homelab operator data. Registers multiple capabilities
            # from a single connection.
            base = conn.get("base_url")
            lab_path = conn.get("lab_path", "/opt/scripts/lab")
            if base:
                # Settings
                settings_impl = LabSettings(lab_path)
                registry.register(
                    "homelab_settings",
                    f"{name}-settings",
                    settings_impl,
                    health_check=lambda settings_impl=settings_impl: (
                        settings_impl.observe().ok
                    ),
                    writes="none",
                    mode=mode,
                    required=required,
                )
                # Health
                health_impl = LabHealth(lab_path)
                registry.register(
                    "homelab_health",
                    f"{name}-health",
                    health_impl,
                    health_check=lambda health_impl=health_impl: (
                        health_impl.observe().ok
                    ),
                    writes="none",
                    mode=mode,
                    required=required,
                )
                # Deploy
                deploy_impl = LabDeploy(lab_path)
                registry.register(
                    "homelab_deploy",
                    f"{name}-deploy",
                    deploy_impl,
                    health_check=lambda deploy_impl=deploy_impl: (
                        deploy_impl.observe().ok
                    ),
                    writes="none",
                    mode=mode,
                    required=required,
                )
                # Secrets
                secrets_impl = LabSecrets(lab_path)
                registry.register(
                    "homelab_secrets",
                    f"{name}-secrets",
                    secrets_impl,
                    health_check=lambda secrets_impl=secrets_impl: (
                        secrets_impl.observe().ok
                    ),
                    writes="none",
                    mode=mode,
                    required=required,
                )
                # Resources
                resources_impl = LabResources(lab_path)
                registry.register(
                    "homelab_resources",
                    f"{name}-resources",
                    resources_impl,
                    health_check=lambda resources_impl=resources_impl: (
                        resources_impl.observe().ok
                    ),
                    writes="none",
                    mode=mode,
                    required=required,
                )
        # unknown types: skipped, not fatal -- standalone deployments
        # boot with zero providers

    # Auto-register native providers that always ship with Project Worlds
    # These don't require connections.json entries — they are native baselines

    # native_vault: secrets capability backed by encrypted vault
    if vault is not None:
        from .providers.native_vault import NativeVaultProvider

        vault_provider = NativeVaultProvider(vault)
        registry.register(
            "secrets",
            "native-vault",
            vault_provider,
            health_check=vault_provider.health,
            writes="none",
            mode=ProviderMode.NATIVE,
            required=False,
        )

    # native_memory: memory capability via SQLite FTS5 (journal search)
    from .providers.native_memory import NativeMemoryProvider

    memory_provider = NativeMemoryProvider(data_dir or Path("./data"), journal=journal)
    registry.register(
        "memory",
        "native-memory",
        memory_provider,
        health_check=memory_provider.health,
        writes="none",
        mode=ProviderMode.NATIVE,
        required=False,
    )

    # content_db: cross-repo content database via agent-config's ContentMaster
    import os

    from .providers.content_db import ContentDBProvider

    _master_db = Path(
        os.environ.get(
            "PW_CONTENT_MASTER_DB",
            str(Path.home() / ".local/share/agent-config/content.master.db"),
        )
    )
    _code_root = Path(
        os.environ.get(
            "PW_CODE_ROOT",
            str(Path.home() / "code/Rylee-Bee"),
        )
    )
    content_provider = ContentDBProvider(
        master_db_path=_master_db, code_root=_code_root
    )
    registry.register(
        "memory",
        "content-db",
        content_provider,
        health_check=content_provider.health,
        writes="none",
        mode=ProviderMode.NATIVE,
        required=False,
    )

    # native_calendar: calendar capability via ICS/CalDAV
    from .providers.native_calendar import NativeCalendarProvider

    calendar_config = _read_extra_config(config_dir, "calendar")
    calendar_provider = NativeCalendarProvider(calendar_config)
    registry.register(
        "calendar",
        "native-calendar",
        calendar_provider,
        health_check=calendar_provider.health,
        writes="none",
        mode=ProviderMode.NATIVE,
        required=False,
    )

    # native_notifications: notification dispatcher (webhook/ntfy)
    from .providers.native_notifications import NativeNotificationsProvider

    notif_config = _read_extra_config(config_dir, "notifications")
    notifications_provider = NativeNotificationsProvider(notif_config)
    registry.register(
        "notifications",
        "native-notifications",
        notifications_provider,
        health_check=notifications_provider.health,
        writes="none",
        mode=ProviderMode.NATIVE,
        required=False,
    )

    # native_updates: version/update discovery
    from .providers.native_updates import NativeUpdatesProvider

    updates_config = _read_extra_config(config_dir, "updates")
    updates_provider = NativeUpdatesProvider(updates_config)
    registry.register(
        "update_discovery",
        "native-updates",
        updates_provider,
        health_check=updates_provider.health,
        writes="none",
        mode=ProviderMode.NATIVE,
        required=False,
    )

    # workbench: podman/distrobox attached environments (ADR-0003
    # spike). OFF BY DEFAULT — PW_WORKBENCH=1 registers the provider;
    # without it the capability reports not_configured
    # (zero-provider boot preserved). run_task fails closed unless an
    # allowlist is configured (connections.json "workbench" or
    # PW_WORKBENCH_CONTAINERS). Findings: docs/adr/WORKBENCH-SPIKE-FINDINGS.md.
    if workbench_enabled():
        workbench = WorkbenchPodman(
            config=_read_extra_config(config_dir, "workbench"),
            journal=journal,
        )
        registry.register(
            "workbench",
            "workbench-podman",
            workbench,
            # the status is in observe() (not_configured /
            # unavailable / healthy); a failing health check here would
            # mask the specific reason with a generic 'unavailable'
            health_check=lambda: True,
            writes="exec",
            mode=ProviderMode.ENRICHMENT,
            required=False,
        )


    # Chat/reasoning native baseline: absent a configured provider the
    # capability is not_configured (zero-AI boot is supported).
    if not any(c.get("capability") == "reasoning" for c in connections):
        registry.define_capability("reasoning", StatusContract)

    for cap in world.capabilities.values():
        if cap.key not in registry._contracts:
            registry.define_capability(cap.key, StatusContract)
    return registry
