"""Theme pack system: swappable companions and accent overrides.

A theme pack is a directory containing a manifest.json and SVG/Lottie
assets. The globe is the default; the mermaid, robot, squirrel, and
taco truck are optional packs.

Layer architecture (from design/THEME_PACK_FRAMEWORK.md):
  User Preferences > Theme Pack > Invariant Core

Packs never modify surfaces, text colors, typography, spacing,
focus behavior, touch targets, or the accessibility contract.
"""

import json
from pathlib import Path

from pydantic import BaseModel, Field


class CompanionStates(BaseModel):
    """Six semantic states for a companion character."""

    idle: str
    hello: str
    listening: str
    thinking: str
    celebrate: str
    sleep: str


class CompanionAnimation(BaseModel):
    """Optional Lottie/Rive animation."""

    format: str = "dotlottie"
    src: str


class ThemePack(BaseModel):
    """A theme pack manifest."""

    name: str
    display_name: str
    author: str = ""
    version: str = "1.0"
    companion: CompanionStates
    animation: CompanionAnimation | None = None
    accent: dict[str, str] = Field(default_factory=dict)
    companion_palette: dict[str, str] = Field(default_factory=dict)
    favicon: str | None = None
    service_icons: str | None = None


DEFAULT_PACK = ThemePack(
    name="world-keeper",
    display_name="World Keeper (Globe)",
    author="Project Worlds",
    companion=CompanionStates(
        idle="/static/companions/personal-world.svg",
        hello="/static/companions/personal-world.svg",
        listening="/static/companions/personal-world.svg",
        thinking="/static/companions/personal-world.svg",
        celebrate="/static/companions/personal-world.svg",
        sleep="/static/companions/personal-world.svg",
    ),
    accent={"primary": "#72B1B1", "secondary": "#B57F8B"},
)


class ThemePackRegistry:
    """Loads and serves theme packs from a directory."""

    def __init__(self, packs_dir: Path | None = None) -> None:
        self.packs_dir = packs_dir or Path("/data/theme-packs")
        self._packs: dict[str, ThemePack] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._packs[DEFAULT_PACK.name] = DEFAULT_PACK
        if self.packs_dir.exists():
            for manifest_path in self.packs_dir.glob("*/manifest.json"):
                try:
                    data = json.loads(manifest_path.read_text())
                    pack = ThemePack.model_validate(data)
                    self._packs[pack.name] = pack
                except Exception:  # nosec B112  # skip this pack file, load the rest
                    continue
        self._loaded = True

    def get(self, name: str) -> ThemePack:
        """Get a pack by name. Falls back to default if not found."""
        self._ensure_loaded()
        return self._packs.get(name, DEFAULT_PACK)

    def get_or_none(self, name: str) -> ThemePack | None:
        """Get a pack by name, or None when unknown (lookup)."""
        self._ensure_loaded()
        return self._packs.get(name)

    def list_packs(self) -> list[ThemePack]:
        """List all available packs."""
        self._ensure_loaded()
        return list(self._packs.values())

    def resolve_companion(self, pack_name: str, state: str) -> str:
        """Resolve a companion SVG path for a given pack and state."""
        pack = self.get(pack_name)
        states = pack.companion
        return getattr(states, state, states.idle)
