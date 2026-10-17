"""Brain Template Registry: composes runtime instructions from small pieces.

Templates are durable artifacts with Git history. The registry loads,
validates, and composes templates for the reasoning brain.
"""

from pathlib import Path
from typing import Any


class Template:
    """A single template with metadata."""

    def __init__(
        self,
        id: str,
        version: int,
        kind: str,
        content: str,
        surface: str | None = None,
        max_tokens: int = 400,
        source: str = "shipped",
        description: str | None = None,
    ):
        self.id = id
        self.version = version
        self.kind = kind
        self.content = content
        self.surface = surface
        self.max_tokens = max_tokens
        self.source = source
        self.description = description or self._derive_description(content)

    @staticmethod
    def _derive_description(content: str) -> str:
        """First meaningful line of the body, bounded — a template
        without an explicit ``description:`` front-matter field still
        gets an one-line summary for listings."""
        for line in (content or "").splitlines():
            line = line.strip()
            if line:
                return line[:200]
        return ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "kind": self.kind,
            "surface": self.surface,
            "max_tokens": self.max_tokens,
            "source": self.source,
            "description": self.description,
            "content_length": len(self.content),
        }

    def to_public_dict(self) -> dict[str, Any]:
        """Read-only public shape served by GET /api/templates."""
        return {
            "id": self.id,
            "surface": self.surface,
            "role": self.kind,
            "description": self.description,
        }


class TemplateRegistry:
    """Loads and composes templates for the reasoning brain."""

    def __init__(self, config_dir: Path, data_dir: Path | None = None):
        self._config_dir = config_dir
        self._data_dir = data_dir or Path("./data")
        self._templates: dict[str, Template] = {}
        self._overrides: dict[str, str] = {}  # id -> override content
        self._packs: dict[str, dict[str, Any]] = {}  # pack_id -> metadata
        self._load_shipped()
        self._load_overrides()

    def _load_shipped(self):
        """Load shipped templates from config/prompts/."""
        prompts_dir = self._config_dir / "prompts"
        if not prompts_dir.exists():
            return
        for md_file in prompts_dir.rglob("*.md"):
            template = self._parse_template(md_file, source="shipped")
            if template:
                self._templates[template.id] = template

    def _load_overrides(self):
        """Load private overrides from config.local/prompts/."""
        local_dir = self._config_dir / "prompts.local"
        if not local_dir.exists():
            return
        for md_file in local_dir.rglob("*.md"):
            template = self._parse_template(md_file, source="private")
            if template:
                self._overrides[template.id] = template.content

    def _parse_template(self, path: Path, source: str = "shipped") -> Template | None:
        """Parse a template file with YAML front matter."""
        try:
            text = path.read_text()
            if not text.startswith("---"):
                return None
            parts = text.split("---", 2)
            if len(parts) < 3:
                return None
            # Simple YAML-like parsing (avoid pydantic dependency)
            meta = {}
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    meta[key.strip()] = val.strip()
            content = parts[2].strip()
            return Template(
                id=meta.get("id", path.stem),
                version=int(meta.get("version", 1)),
                kind=meta.get("kind", "unknown"),
                content=content,
                surface=meta.get("surface"),
                max_tokens=int(meta.get("max_tokens", 400)),
                source=source,
                description=meta.get("description") or None,
            )
        except Exception:
            return None

    def get(self, template_id: str) -> Template | None:
        """Get a template, with private override applied."""
        template = self._templates.get(template_id)
        if not template:
            return None
        if template_id in self._overrides:
            # Return with override content
            return Template(
                id=template.id,
                version=template.version,
                kind=template.kind,
                content=self._overrides[template_id],
                surface=template.surface,
                max_tokens=template.max_tokens,
                source="private",
            )
        return template

    def list_templates(self) -> list[dict[str, Any]]:
        """List all templates with metadata."""
        result = []
        for tid, t in self._templates.items():
            d = t.to_dict()
            d["has_override"] = tid in self._overrides
            result.append(d)
        return result

    def list_public(self) -> list[dict[str, Any]]:
        """Read-only listing for GET /api/templates:
        ``{id, surface, role, description}`` per template (overrides
        applied — the listing describes what the brain will actually
        use). Sorted by id for a stable response."""
        return [
            self.get(tid).to_public_dict() for tid in sorted(self._templates.keys())
        ]

    def compose(
        self,
        surface: str | None = None,
        task: str | None = None,
        format: str | None = None,
        packs: list[str] | None = None,
        persona: str | None = None,
    ) -> str:
        """Compose runtime instructions from templates.

        Order matters for small models: core identity/truth rules first,
        then the companion persona (``persona.<name>``, e.g. the
        configured companion pref), then packs, surface focus, task,
        and format.
        """
        parts = []

        # Core templates (always included)
        for tid in sorted(self._templates.keys()):
            if tid.startswith("core."):
                t = self.get(tid)
                if t:
                    parts.append(t.content)

        # Companion persona (optional; an absent persona template is a
        # no-op, never an error)
        if persona:
            t = self.get(f"persona.{persona}")
            if t:
                parts.append(t.content)

        # Selected packs
        if packs:
            for pack_id in packs:
                pack_templates = self._load_pack(pack_id)
                parts.extend(pack_templates)

        # Surface template
        if surface:
            t = self.get(f"surface.{surface}")
            if t:
                parts.append(t.content)

        # Task template
        if task:
            t = self.get(f"task.{task}")
            if t:
                parts.append(t.content)

        # Format template
        if format:
            t = self.get(f"format.{format}")
            if t:
                parts.append(t.content)

        return "\n\n".join(parts)

    def _load_pack(self, pack_id: str) -> list[str]:
        """Load templates from a template pack."""
        pack_dir = self._data_dir / "template-sources" / pack_id
        if not pack_dir.exists():
            return []
        parts = []
        for md_file in pack_dir.rglob("*.md"):
            template = self._parse_template(md_file, source=f"pack:{pack_id}")
            if template:
                parts.append(template.content)
        return parts

    def provenance(
        self,
        surface: str | None = None,
        task: str | None = None,
        packs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Report template provenance for Nerd Mode."""
        result = {
            "core": [],
            "surface": None,
            "task": None,
            "packs": [],
            "overrides": [],
        }
        for tid in sorted(self._templates.keys()):
            if tid.startswith("core."):
                t = self.get(tid)
                if t:
                    result["core"].append(
                        {"id": t.id, "version": t.version, "source": t.source}
                    )
        if surface:
            t = self.get(f"surface.{surface}")
            if t:
                result["surface"] = {
                    "id": t.id,
                    "version": t.version,
                    "source": t.source,
                }
        if task:
            t = self.get(f"task.{task}")
            if t:
                result["task"] = {"id": t.id, "version": t.version, "source": t.source}
        if packs:
            for pack_id in packs:
                result["packs"].append({"id": pack_id, "status": "loaded"})
        for tid in self._overrides:
            result["overrides"].append({"id": tid, "source": "private"})
        return result
