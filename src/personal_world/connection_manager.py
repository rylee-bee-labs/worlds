"""Connection manager: CRUD for private runtime configuration.

Writes to connections.local.json (never the tracked connections.json).
Provides canonical resolution between UI-saved flat config and the
nested shapes native providers expect.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .secret_resolver import resolve_secrets

# ── Canonical config resolver ──
#
# The Connections UI saves flat key-value pairs with `_adapter` as the
# discriminator. Native providers expect nested structures (sources[],
# targets[], etc.) with `type` as the discriminator.
#
# This resolver transforms between the two representations so that
# ONE save path (UI → connections.local.json) feeds ALL consumers
# (provider constructors, API endpoints, brain tools).

_NATIVE_CONFIG_MAP: dict[str, dict[str, Any]] = {
    "calendar": {
        "wrapper_key": "sources",
        "adapter_to_type": {"ics": "ics", "caldav": "caldav"},
        "field_map": {"name": "name", "url": "url"},
    },
    "notifications": {
        "wrapper_key": "targets",
        "adapter_to_type": {"webhook": "webhook", "ntfy": "ntfy"},
        "field_map": {"name": "name", "url": "url", "topic": "topic",
                      "server": "server", "token": "token"},  # nosec B105  # a config field-name map, not a credential
    },
    "updates": {
        "wrapper_key": "sources",
        "adapter_to_type": {"github_release": "github",
                            "version_url": "url"},
        "field_map": {"name": "name", "repository": "repo",
                      "current_version": "current_version", "url": "url"},
    },
}

# Fields the UI adds that are not provider config
_UI_META_FIELDS = {"_adapter", "name"}


def resolve_native_config(raw: dict[str, Any], capability: str) -> dict[str, Any]:
    """Transform flat UI config into the shape native providers expect.

    The UI saves: {"_adapter": "ics", "url": "...", "name": "..."}
    Calendar expects: {"sources": [{"type": "ics", "url": "...", "name": "..."}]}

    If the config is already in the provider shape (has the expected
    wrapper key), it is returned unchanged — this handles configs
    written directly to connections.json (not through the UI).

    Secret references (token, api_key, ...) are resolved from the
    environment or the unlocked vault (see secret_resolver); ones that
    cannot be resolved stay references, which providers refuse.
    """
    spec = _NATIVE_CONFIG_MAP.get(capability)
    if spec is None:
        return raw

    wrapper = spec["wrapper_key"]

    # Already in provider shape — pass through
    if wrapper in raw and isinstance(raw[wrapper], list):
        return raw

    adapter = raw.get("_adapter")
    if not adapter:
        return raw

    provider_type = spec["adapter_to_type"].get(adapter, adapter)

    item: dict[str, Any] = {"type": provider_type}
    for ui_field, provider_field in spec["field_map"].items():
        val = raw.get(ui_field)
        if val is not None and val != "":
            item[provider_field] = val

    return {wrapper: [resolve_secrets(item)]}


def resolve_media_connections(
    raw: dict[str, Any],
) -> list[dict[str, Any]]:
    """Transform flat UI media config into connections[] entries.

    The UI saves: {"_adapter": "plex", "base_url": "...", "token": "ref"}
    Media engine expects: connections[] entries with "type" key.

    Returns a list of connection entries suitable for build_adapter().
    If the config already has a "connections" key, those entries are
    returned (provider shape passthrough).
    """
    if "connections" in raw and isinstance(raw["connections"], list):
        return [resolve_secrets(c) if isinstance(c, dict) else c
                for c in raw["connections"]]

    adapter = raw.get("_adapter")
    if not adapter:
        return []

    entry: dict[str, Any] = {"type": adapter}
    for k, v in raw.items():
        if k not in _UI_META_FIELDS and v is not None and v != "":
            entry[k] = v

    return [resolve_secrets(entry)]


class ConnectionManager:
    """Manages private connection configuration."""

    def __init__(self, config_dir: Path):
        self._config_dir = config_dir
        self._local_path = config_dir / "connections.local.json"

    def _read_local(self) -> dict[str, Any]:
        if self._local_path.exists():
            try:
                return json.loads(self._local_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _write_local(self, data: dict[str, Any]) -> None:
        self._local_path.parent.mkdir(parents=True, exist_ok=True)
        self._local_path.write_text(json.dumps(data, indent=2))

    def _read_all(self) -> dict[str, Any]:
        """Read merged config (tracked + local)."""
        result: dict[str, Any] = {}
        for name in ("connections.json", "connections.local.json"):
            path = self._config_dir / name
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    # Merge connections arrays
                    if "connections" in data:
                        existing = result.get("connections", [])
                        new = [c for c in data["connections"] if isinstance(c, dict)]
                        result["connections"] = existing + new
                    # Other keys: local overrides tracked
                    for k, v in data.items():
                        if k not in ("connections", "$schema"):
                            result[k] = v
                except (json.JSONDecodeError, OSError):
                    pass
        return result

    def get_connections(self) -> list[dict[str, Any]]:
        """Get all connections (merged tracked + local)."""
        data = self._read_all()
        return data.get("connections", [])

    def get_native_config(self, key: str) -> dict[str, Any]:
        """Get native provider config (e.g., 'calendar', 'notifications')."""
        data = self._read_all()
        return data.get(key, {})

    def save_native_config(self, key: str, config: dict[str, Any]) -> None:
        """Save native provider config to connections.local.json."""
        local = self._read_local()
        local[key] = config
        self._write_local(local)

    def save_connection(self, conn: dict[str, Any]) -> None:
        """Save or update a connection entry in connections.local.json.

        If a connection with the same name exists, it's replaced.
        Otherwise it's appended.
        """
        local = self._read_local()
        connections = local.get("connections", [])
        name = conn.get("name", "")
        # Replace existing or append
        connections = [c for c in connections if c.get("name") != name]
        connections.append(conn)
        local["connections"] = connections
        self._write_local(local)

    def delete_connection(self, name: str) -> bool:
        """Delete a connection by name from connections.local.json."""
        local = self._read_local()
        connections = local.get("connections", [])
        before = len(connections)
        connections = [c for c in connections if c.get("name") != name]
        if len(connections) == before:
            return False
        local["connections"] = connections
        self._write_local(local)
        return True

    def get_connection(self, name: str) -> dict[str, Any] | None:
        """Get a single connection by name."""
        for c in self.get_connections():
            if c.get("name") == name:
                return c
        return None

    def get_all_config(self) -> dict[str, Any]:
        """Get the full merged config for inspection."""
        return self._read_all()
