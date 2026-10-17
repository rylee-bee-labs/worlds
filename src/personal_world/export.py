"""Export contracts.

Four distinct artifacts (see docs/ARCHITECTURE.md):

- settings-export: shareable blueprint. STRUCTURALLY INCAPABLE of
  carrying private/secret-classified data: only fields whose model
  metadata marks them ``exportable: true`` are serialized. This is a
  whitelist walk, not redact-after-export.
- world-export: portable personal configuration (world-classified
  user state; no raw secrets ever).
- backup: encrypted disaster-recovery artifact (delegated to the
  operator's SOPS/age mechanism; the core only defines the payload).
- story-export: human-readable journal rendering with disclosure rules.
"""

from typing import Any

from pydantic import BaseModel

from .classification import Classification, field_meta
from .journal import StoryRenderer
from .world import World


def _walk_exportable(model: BaseModel) -> dict[str, Any]:
    """Whitelist walk: emit only fields marked exportable in model
    metadata. Anything else (private, secret, or simply not cleared for
    blueprints) is structurally absent from the result."""
    out: dict[str, Any] = {}
    for name, field in model.model_fields.items():
        cls, exportable = field_meta(field)
        value = getattr(model, name)
        if not exportable:
            continue
        if isinstance(value, BaseModel):
            out[name] = _walk_exportable(value)
        elif isinstance(value, list) and value and isinstance(value[0], BaseModel):
            out[name] = [_walk_exportable(v) for v in value]
        elif isinstance(value, dict):
            out[name] = {
                k: _walk_exportable(v) if isinstance(v, BaseModel) else v
                for k, v in value.items()
            }
        else:
            out[name] = value
    return out


def settings_export(world: World) -> dict[str, Any]:
    """The bones of the installation: capabilities, provider mappings,
    packs, schedules, safe policy defaults. Never the person."""
    caps = []
    for cap in world.capabilities.values():
        entry = {"key": cap.key}
        if cap.description:
            entry["description"] = cap.description
        providers = []
        for p in world.providers_for(cap.key):
            providers.append(
                {
                    "capability": p.capability,
                    "name": p.name,
                    "mode": p.mode.value,
                    "replaceable": p.mode.value != "native",
                    "writes": p.writes,
                    "required": p.required,
                }
            )
        if providers:
            entry["providers"] = providers
        caps.append(entry)
    packs = []
    for pack in world.packs.values():
        packs.append(
            {
                "key": pack.key,
                "version": pack.version,
                "capabilities": list(pack.capabilities),
                "schedule": pack.schedule,
                "policies": pack.policies,
                "presentation": pack.presentation,
                "compatibility": pack.compatibility,
            }
        )
    policies = []
    for p in world.policies.values():
        policies.append(
            {
                "key": p.key,
                "effect": p.effect.value,
                "override": p.override.value,
                "mutability": p.mutability.value,
            }
        )
    return {
        "schema": "personal-world/settings-export/1",
        "capabilities": caps,
        "packs": packs,
        "policies": policies,
        "accessibility": dict(world.accessibility),
    }


def world_export(world: World) -> dict[str, Any]:
    """Portable personal configuration. World-classified state only;
    raw secrets are structurally absent (they are in the secret store,
    referenced by name at most). Treat the output as personal data."""
    def clean_private(items: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in items.items()
                if not str(k).startswith("_")}

    return {
        "schema": "personal-world/world-export/1",
        "intents": clean_private(
            {k: {"key": i.key, "value": i.value} for k, i in world.intents.items()}
        ),
        "policies": {
            k: {
                "key": p.key,
                "effect": p.effect.value,
                "override": p.override.value,
                "mutability": p.mutability.value,
            }
            for k, p in world.policies.items()
        },
        "lore": {
            k: {
                "key": entry.key,
                "value": entry.value,
                "state": entry.state.value,
            }
            for k, entry in world.lore.items()
            if entry.classification == Classification.WORLD
        },
        "packs": [pack.key for pack in world.packs.values()],
        "accessibility": dict(world.accessibility),
        "layout": dict(world.layout),
    }


def story_export(journal, include_private: bool = False) -> str:
    return StoryRenderer().render(journal, include_private=include_private)


def backup_payload(world: World, journal) -> dict[str, Any]:
    """Full-state payload for the encrypted backup artifact. The core
    hands this to the operator's encryption mechanism (SOPS/age); it is
    never shareable and the core never encrypts it itself."""
    return {
        "schema": "personal-world/backup/1",
        "world": {
            "facts": {k: f.model_dump() for k, f in world.facts.items()},
            "intents": {k: i.model_dump() for k, i in world.intents.items()},
            "policies": {k: p.model_dump() for k, p in world.policies.items()},
            "lore": {k: entry.model_dump() for k, entry in world.lore.items()},
            "capabilities": {k: c.model_dump() for k, c in world.capabilities.items()},
            "providers": {k: [p.model_dump() for p in v] for k, v in world.providers.items()},
            "packs": {k: p.model_dump() for k, p in world.packs.items()},
            "accessibility": world.accessibility,
        },
        "journal": [e.model_dump() for e in journal.events()],
    }
