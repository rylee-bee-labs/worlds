"""Section registry and per-person layout (docs/p1/FOUNDATION-SPEC.md §2).

The registry (``SECTIONS``) is tracked code: defaults only, never the
owner's state. The owner's layout (order + hidden) is in the
caller's ``world.json`` under ``World.layout["sections"]`` and is
world-classified (in ``world-export``, never in ``settings-export``).

Status vocabulary is owned by ``status.py``. A section with no
capability dependency reports ``status=None`` — never an invented
value. A failing or unconfigured provider never removes a section;
``configured``/``status`` only inform how the route renders.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .status import Status, worst

SCHEMA = "personal-world/sections/1"
LAYOUT_KEY = "sections"


@dataclass(frozen=True)
class SectionSpec:
    id: str
    label: str
    icon: str                         # sprite symbol id (must exist in icons/manifest.json)
    default_order: int
    default_visible: bool = True
    pinned: bool = False              # cannot be hidden; may be reordered
    kind: Literal["core", "transitional", "extension"] = "core"
    capabilities: tuple[str, ...] = ()  # informs `configured`/`status`; never hides


# Spec §2.1 names glyphs the icon library does not ship
# (navigation--discover, navigation--media, navigation--lab,
# navigation--vault). P1 adds no artwork; the closest existing glyph
# stands in. Keyed by section id -> substituted manifest icon id.
ICON_SUBSTITUTIONS: dict[str, str] = {
    "media": "world-content--story",          # spec: navigation--media
    "lab": "system-device--desktop",          # spec: navigation--lab
    "vault": "system-device--lock",           # spec: navigation--vault
}

SECTIONS: tuple[SectionSpec, ...] = (
    SectionSpec("today",     "Today",            "navigation--today",        0),
    SectionSpec("media",     "Media",            "world-content--story",     1, capabilities=("media",)),
    SectionSpec("projects",  "Projects",         "navigation--projects",     2, capabilities=("source_control",)),
    SectionSpec("lab",       "Lab",              "system-device--desktop",   3, capabilities=("homelab_health",)),
    SectionSpec("journal",   "Journal & Memory", "navigation--journal",      4, capabilities=("journal",)),
    SectionSpec("vault",     "Vault",            "system-device--lock",      5, capabilities=("secrets",)),
    SectionSpec("chat",      "Chat",             "navigation--chat",         6, kind="transitional",
                                                                                capabilities=("reasoning",)),
    SectionSpec("settings",  "Settings",         "navigation--settings",     7, pinned=True),
)

BY_ID: dict[str, SectionSpec] = {s.id: s for s in SECTIONS}
PINNED_IDS: frozenset[str] = frozenset(s.id for s in SECTIONS if s.pinned)

_UNCONFIGURED = (Status.NOT_CONFIGURED.value, Status.DISABLED.value)


def manifest_icon_ids(path: Path | str) -> set[str]:
    """Icon ids (``<category>--<name>``) present in an icon manifest."""
    payload = json.loads(Path(path).read_text())
    icons = payload.get("icons", []) if isinstance(payload, dict) else payload
    return {
        f"{i['category']}--{i['name']}"
        for i in icons
        if isinstance(i, dict) and "category" in i and "name" in i
    }


def default_order() -> list[str]:
    return [s.id for s in sorted(SECTIONS, key=lambda s: s.default_order)]


def _stored_lists(layout: dict | None) -> tuple[list[str], list[str]]:
    """Stored order/hidden as string lists; anything malformed reads as
    empty (defaults) rather than crashing the navigation surface."""
    if not isinstance(layout, dict):
        return [], []
    order = layout.get("order")
    hidden = layout.get("hidden")
    order = [x for x in order if isinstance(x, str)] if isinstance(order, list) else []
    hidden = [x for x in hidden if isinstance(x, str)] if isinstance(hidden, list) else []
    return order, hidden


def section_status(spec: SectionSpec, status_map: dict[str, dict]) -> str | None:
    """Public alias of the per-section worst-of status (kept for the
    chat path; the historical _section_status name remains below)."""
    if not spec.capabilities:
        return None
    statuses: list[str] = []
    for cap in spec.capabilities:
        entry = status_map.get(cap)
        raw = entry.get("status") if isinstance(entry, dict) else None
        statuses.append(str(raw) if raw else Status.NOT_CONFIGURED.value)
    return worst(statuses)


_section_status = section_status


def resolve_sections(layout: dict | None, status_map: dict[str, dict]) -> list[dict]:
    """Merge the stored layout with the registry (spec §2.3).

    Start from stored ``order`` (unknown ids dropped), append registry
    ids missing from it by ``default_order``. ``hidden`` is the stored
    set ∩ known ids, minus pinned. A section not mentioned anywhere in
    the stored layout falls back to ``default_visible``.
    """
    order, hidden = _stored_lists(layout)
    has_layout = isinstance(layout, dict)

    final: list[str] = []
    seen: set[str] = set()
    for sid in order:
        if sid in BY_ID and sid not in seen:
            final.append(sid)
            seen.add(sid)
    for sid in default_order():
        if sid not in seen:
            final.append(sid)
            seen.add(sid)

    hidden_set = {h for h in hidden if h in BY_ID and h not in PINNED_IDS}
    mentioned = set(order) | set(hidden)

    out: list[dict] = []
    for position, sid in enumerate(final):
        spec = BY_ID[sid]
        if spec.pinned:
            visible = True
        elif sid in hidden_set:
            visible = False
        elif has_layout and sid in mentioned:
            visible = True
        else:
            visible = spec.default_visible
        status = _section_status(spec, status_map)
        out.append({
            "id": sid,
            "label": spec.label,
            "icon": spec.icon,
            "order": position,
            "visible": visible,
            "pinned": spec.pinned,
            "kind": spec.kind,
            "configured": status is None or status not in _UNCONFIGURED,
            "status": status,
        })
    return out


def validate_layout_update(body: dict, current: dict | None) -> tuple[dict, list[str]]:
    """Validate a ``PUT /api/sections`` body against the registry
    (spec §2.4). Either key optional (omitted keeps the stored value).
    Every error is collected; the caller returns them as one 400.
    ``{"order": [], "hidden": []}`` resets to defaults."""
    errors: list[str] = []
    cur_order, cur_hidden = _stored_lists(current)
    new_order: list[str] = list(cur_order)
    new_hidden: list[str] = list(cur_hidden)

    if not isinstance(body, dict):
        return ({"schema": SCHEMA, "order": new_order, "hidden": new_hidden},
                ["body must be an object"])

    if "order" in body:
        order = body["order"]
        if not isinstance(order, list) or not all(isinstance(x, str) for x in order):
            errors.append("order must be a list of section ids")
        else:
            seen: set[str] = set()
            for sid in order:
                if sid not in BY_ID:
                    errors.append(f"unknown section id in order: {sid!r}")
                elif sid in seen:
                    errors.append(f"duplicate section id in order: {sid!r}")
                seen.add(sid)
            new_order = list(order)

    if "hidden" in body:
        hidden = body["hidden"]
        if not isinstance(hidden, list) or not all(isinstance(x, str) for x in hidden):
            errors.append("hidden must be a list of section ids")
        else:
            for sid in hidden:
                if sid not in BY_ID:
                    errors.append(f"unknown section id in hidden: {sid!r}")
                elif sid in PINNED_IDS:
                    errors.append(
                        f"section {sid!r} is pinned and cannot be hidden")
            new_hidden = list(dict.fromkeys(hidden))

    return {"schema": SCHEMA, "order": new_order, "hidden": new_hidden}, errors
