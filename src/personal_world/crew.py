"""The crew registry — companions are user-owned (owner decision 2026-09-25).

The drawn crew ships as a **starter crew**, not as a fixed cast. A person
can add a companion, rename one, hide one, delete one they created, and a
room may have no companion at all. Sol stays the Worlds mark (the primary
logo) and is deliberately *not* a crew entry; Worlds is a place, not a
companion (owner canon 2026-09-25).

This is the Worlds half of the entry point: private, per principal, never sent to
a room and never sent to a model. It rides the existing per-principal JSON
entry point (``identity.principal_scoped_path``, kind ``crew``) with the same
atomic write every other Worlds state file uses — no new store, no new
format family. Portrait *bytes* are the one addition, and they are files
under the principal's own scoped data directory (a sibling of this state
file), written with the same atomic-replace pattern as the JSON. No new
storage system, no new dependency.

The stored shape (one file per principal)::

    {
      "crew": [
        {"id": "bolt", "name": "Bolt", "blurb": "...", "voice_label": null,
         "portrait_asset": "/assets/crew/512/bolt-portrait.webp",
         "full_body_asset": null, "source": "starter", "hidden": false}
      ],
      "keepers": {"workshop": "bolt"},
      "doorways": {"workshop": "garden"}
    }

Accuracy rules:

* First read with no file (or an unreadable one) seeds the starter crew —
  the drawn crew — and nothing else. A stored file is authoritative: an
  emptied ``crew`` list stays empty, because the person meant it.
* ``keepers`` is seeded from the canon **only** for configured rooms whose
  id names a briefing system (``briefing.system_id_for_room_id``): Bolt
  keeps Workshop, Hekek the Engine room, Bruma the Archive, Mira the
  Observatory, Scoop the Newsstand, Ratatoskr the World tree — and only
  for a companion the roster actually has. A room id that matches nothing
  gets no keeper — never a guess.
* Once ``keepers`` exists in the file, it is authoritative: an explicit
  ``null`` (the person cleared the room) is never re-seeded.
* A keeper never changes a room's status. Status comes only from the room;
  this module only records who the person put there.
* Hiding a companion is a roster act, not an unassignment: the assignment
  is cleared by deleting the companion (the only thing the owner decision
  names as clearing it) or by clearing it from the room.

Portrait uploads (``image/png`` | ``image/jpeg`` | ``image/webp``) are
typed by **magic bytes**, never by the declared content type alone, capped
at :data:`PORTRAIT_MAX_BYTES` decoded, stored 0600, and served same-origin
with ``X-Content-Type-Options: nosniff``. They never travel to a room or a
model.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

#: Field caps (owner decision 2026-09-25). Strings only; over-length input
#: is refused rather than silently truncated into a different value.
NAME_MAX = 60
BLURB_MAX = 280
VOICE_LABEL_MAX = 60

#: A companion id is a slug: safe as a URL segment and as a file name.
ID_MAX = 64
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

SOURCE_STARTER = "starter"
SOURCE_USER = "user"

#: Portrait uploads. The declared type is checked against the sniffed type;
#: a mismatch is refused (a ".png" whose bytes are not PNG is not accepted).
PORTRAIT_MAX_BYTES = 5 * 1024 * 1024
EXT_FOR_TYPE = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
ALLOWED_IMAGE_TYPES = tuple(EXT_FOR_TYPE)

#: The suffix the portrait route serves; the URL is the same for every
#: uploaded format, so its paths are stable while the bytes can change.
PORTRAIT_ROUTE = "/api/crew/{id}/portrait"

#: The drawn crew — the starter set every principal begins with. Names are
#: capitalized from the canon (COMPANION-CANON.md §1, CHARACTER-HANDBOOK.md
#: §1); ``portrait_asset`` is a frontend asset PATH into the web-sized
#: art shipped under ``ui/public/assets/crew/512/`` (owner export
#: 2026-09-25; the masters stay in design/assets/crew) — Renai's is her
#: full-body greeting, the round porthole busts for the rest. This module
#: copies no art and owns no file under design/ or ui/. ``full_body_asset``
#: stays null: the owner decision names no canon full-body path, and an
#: invented one would be a fabrication. Sol is absent on purpose — she is
#: the Worlds mark.
STARTER_CREW: tuple[dict[str, Any], ...] = (
    {
        "id": "renai",
        "name": "Renai",
        "blurb": "Personal companion — curiosity, imagination, "
                 "personal presence.",
        "portrait_asset": "/assets/crew/512/renai-hello.webp",
    },
    {
        "id": "bolt",
        "name": "Bolt",
        "blurb": "Lab and development helper — making things together, "
                 "learning by doing.",
        "portrait_asset": "/assets/crew/512/bolt-portrait.webp",
    },
    {
        "id": "hekek",
        "name": "Hekek",
        "blurb": "Systems — builder, maintainer, steward; "
                 "maintenance as care.",
        "portrait_asset": "/assets/crew/512/hekek-portrait.webp",
    },
    {
        "id": "ratatoskr",
        "name": "Ratatoskr",
        "blurb": "Worlds, lore and memory keeper — the messenger squirrel.",
        "portrait_asset": "/assets/crew/512/ratatoskr-portrait.webp",
    },
    {
        "id": "bruma",
        "name": "Bruma",
        "blurb": "Records — archivist, keeper, witness; preservation "
                 "with provenance.",
        "portrait_asset": "/assets/crew/512/bruma-portrait.webp",
    },
    {
        "id": "mira",
        "name": "Mira",
        "blurb": "Interests — observer, note-taker, pattern seeker.",
        "portrait_asset": "/assets/crew/512/mira-portrait.webp",
    },
    {
        "id": "scoop",
        "name": "Scoop",
        "blurb": "Burrito Journalism — news, stories and city life, at a "
                 "wander-over pace.",
        "portrait_asset": "/assets/crew/512/scoop-portrait.webp",
    },
)

#: Which canon resident reports which briefing system. Seeded as keepers
#: only for rooms whose configured id names that system (see the module
#: docstring). Condensed from COMPANION-CANON.md §1 / STATION-MAP.md §1 /
#: briefing.SYSTEM_SPECS — the six fixed systems, nothing else.
SYSTEM_RESIDENT: dict[str, str] = {
    "agents": "bolt",       # Workshop
    "estate": "hekek",      # Engine room
    "records": "bruma",     # Archive
    "interests": "mira",    # Observatory
    "news": "scoop",        # Newsstand (Burrito Journalism)
    "threads": "ratatoskr",  # World tree
}

#: The closed list of doorways a room may be given (owner request
#: 2026-09-26). A doorway is **presentation only**: the door a person
#: chooses to see for a room. It is private, per principal, and never
#: sent to a room. An id outside this list is refused at the API and read
#: as absent from a stored file (never guessed); non-dict stored state
#: reads as ``{}``. No doorway is ever seeded — there are no defaults.
DOORWAYS: tuple[str, ...] = (
    "study",
    "archive",
    "garden",
    "kitchen",
    "lounge",
    "music",
    "observatory",
    "post",
    "travel",
    "vault",
    "wellness",
    "hallway",
    "servers",
)


def is_doorway(value: Any) -> bool:
    """True for an id in the closed doorway list, and nothing else."""
    return isinstance(value, str) and value in DOORWAYS


def _entry(
    companion_id: str,
    name: str,
    *,
    blurb: str | None = None,
    voice_label: str | None = None,
    portrait_asset: str | None = None,
    full_body_asset: str | None = None,
    source: str = SOURCE_USER,
    hidden: bool = False,
) -> dict[str, Any]:
    """One crew entry in its stable public shape."""
    return {
        "id": companion_id,
        "name": name,
        "blurb": blurb,
        "voice_label": voice_label,
        "portrait_asset": portrait_asset,
        "full_body_asset": full_body_asset,
        "source": source,
        "hidden": hidden,
    }


def starter_entries() -> list[dict[str, Any]]:
    """A fresh copy of the starter crew (callers may mutate their own)."""
    return [
        _entry(
            spec["id"],
            spec["name"],
            blurb=spec["blurb"],
            portrait_asset=spec["portrait_asset"],
            source=SOURCE_STARTER,
        )
        for spec in STARTER_CREW
    ]


def starter_portrait_asset(companion_id: str) -> str | None:
    """The shipped portrait path for a starter, or None for a user entry."""
    for spec in STARTER_CREW:
        if spec["id"] == companion_id:
            return spec["portrait_asset"]
    return None


def is_starter(entry: dict[str, Any]) -> bool:
    """True for the drawn crew: rename/hide allowed, delete refused."""
    return entry.get("source") == SOURCE_STARTER


def is_safe_id(value: Any) -> bool:
    """A slug short enough to be a path segment — no traversal, no slashes."""
    return (
        isinstance(value, str)
        and 0 < len(value) <= ID_MAX
        and bool(_ID_RE.match(value))
    )


def slugify(name: str) -> str:
    """A companion id derived from a display name.

    Empty when the name carries no usable characters (the caller falls
    back to a constant base); casing and punctuation fold to ``-``.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug[:ID_MAX].strip("-")


def unique_id(state: dict[str, Any], base: str) -> str:
    """``base``, or ``base-2``/``base-3``… so a slug never collides."""
    taken = {e["id"] for e in state.get("crew", []) if isinstance(e, dict)}
    candidate = base or "companion"
    suffix = 2
    while candidate in taken:
        tail = f"-{suffix}"
        candidate = f"{base[: ID_MAX - len(tail)] or 'companion'}{tail}"
        suffix += 1
    return candidate


def initial_of(name: str) -> str:
    """The avatar letter for a name: its first letter, upper-cased."""
    return name.strip()[:1].upper()


# ── state ────────────────────────────────────────────────────────────


def empty_state() -> dict[str, Any]:
    """An empty crew: no companions, no keepers, no doorways."""
    return {"crew": [], "keepers": {}, "doorways": {}}


def default_keepers(room_ids: Iterable[str]) -> dict[str, str]:
    """Canon keeper assignments for the configured rooms that name a system.

    The room id is folded exactly as the briefing folds it
    (``briefing.system_id_for_room_id``), so ``workshop`` and
    ``engine-room`` match; anything else is left without a keeper.
    """
    from .briefing import system_id_for_room_id

    out: dict[str, str] = {}
    for room_id in room_ids:
        if not isinstance(room_id, str) or not room_id:
            continue
        system_id = system_id_for_room_id(room_id)
        companion_id = SYSTEM_RESIDENT.get(system_id or "")
        if companion_id:
            out[room_id] = companion_id
    return out


def read_crew(path: Path, *, room_ids: Iterable[str] = ()) -> dict[str, Any]:
    """Load one principal's crew. Missing/unreadable → the starter crew.

    A stored file is authoritative (an emptied list stays empty); only a
    file that is absent or unreadable falls back to the starter seed. The
    ``keepers`` key is seeded from the canon when it is absent — never
    when it is present, so a cleared assignment is never re-seeded.
    ``doorways`` is never seeded: it holds only a person's own choices.
    """
    def _seeded() -> dict[str, Any]:
        return {
            "crew": starter_entries(),
            "keepers": default_keepers(room_ids),
            "doorways": {},
        }

    if not path.exists():
        return _seeded()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _seeded()
    if not isinstance(data, dict):
        return _seeded()

    state = empty_state()
    raw_crew = data.get("crew")
    if isinstance(raw_crew, list):
        for item in raw_crew:
            entry = _normalize_entry(item)
            if entry is not None:
                state["crew"].append(entry)

    known = {e["id"] for e in state["crew"]}
    raw_keepers = data.get("keepers")
    if isinstance(raw_keepers, dict):
        for room_id, companion_id in raw_keepers.items():
            if not isinstance(room_id, str) or not room_id:
                continue
            # A keeper that no longer exists reads as no keeper — never as
            # a dangling id the main app would have to guess at.
            state["keepers"][room_id] = (
                companion_id
                if isinstance(companion_id, str) and companion_id in known
                else None
            )
    else:
        # Seeded only for a companion this roster actually has: a
        # hand-edited file with an emptied crew gets no phantom keepers
        # (the canon seed names a resident, never an id the person
        # removed from their own roster).
        state["keepers"] = {
            room_id: companion_id
            for room_id, companion_id in default_keepers(room_ids).items()
            if companion_id in known
        }

    # Doorways: presentation only, never seeded. A stored id outside the
    # closed list reads as absent (never guessed); a non-dict reads as {}.
    raw_doorways = data.get("doorways")
    if isinstance(raw_doorways, dict):
        for room_id, doorway_id in raw_doorways.items():
            if not isinstance(room_id, str) or not room_id:
                continue
            state["doorways"][room_id] = (
                doorway_id if is_doorway(doorway_id) else None
            )
    return state


def _normalize_entry(item: Any) -> dict[str, Any] | None:
    """A stored entry in public shape, or None when it is not addressable."""
    if not isinstance(item, dict):
        return None
    companion_id = item.get("id")
    name = item.get("name")
    if not is_safe_id(companion_id) or not isinstance(name, str):
        return None
    # A nameless companion has no initial and cannot be rendered: a
    # hand-edited file that blanks the name drops the entry,.
    name = name.strip()[:NAME_MAX]
    if not name:
        return None
    blurb = item.get("blurb")
    voice_label = item.get("voice_label")
    portrait = item.get("portrait_asset")
    full_body = item.get("full_body_asset")
    return _entry(
        companion_id,
        name,
        blurb=blurb.strip()[:BLURB_MAX] if isinstance(blurb, str) and blurb else None,
        voice_label=(
            voice_label.strip()[:VOICE_LABEL_MAX]
            if isinstance(voice_label, str) and voice_label
            else None
        ),
        portrait_asset=portrait if isinstance(portrait, str) and portrait else None,
        full_body_asset=(
            full_body if isinstance(full_body, str) and full_body else None
        ),
        source=(
            SOURCE_STARTER if item.get("source") == SOURCE_STARTER else SOURCE_USER
        ),
        hidden=item.get("hidden") is True,
    )


def write_crew(path: Path, state: dict[str, Any]) -> None:
    """Persist atomically; private bits (0600), no half-written file."""
    payload = {
        "crew": list(state.get("crew") or []),
        "keepers": dict(state.get("keepers") or {}),
        "doorways": dict(state.get("doorways") or {}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.chmod(0o600)
    os.replace(tmp, path)


def find(state: dict[str, Any], companion_id: Any) -> dict[str, Any] | None:
    """The entry with this exact id, or None. Never a prefix/fuzzy match."""
    if not is_safe_id(companion_id):
        return None
    for entry in state.get("crew", []):
        if isinstance(entry, dict) and entry.get("id") == companion_id:
            return entry
    return None


def add(
    state: dict[str, Any],
    *,
    name: str,
    blurb: str | None = None,
    voice_label: str | None = None,
) -> dict[str, Any]:
    """Add a user companion; its id is a unique slug of the name."""
    entry = _entry(
        unique_id(state, slugify(name)),
        name.strip(),
        blurb=blurb,
        voice_label=voice_label,
        source=SOURCE_USER,
    )
    state.setdefault("crew", []).append(entry)
    return entry


def clear_keepers_for(state: dict[str, Any], companion_id: str) -> list[str]:
    """Clear every room this companion kept; returns the room ids."""
    keepers = state.get("keepers")
    if not isinstance(keepers, dict):
        return []
    cleared = [room for room, kept in keepers.items() if kept == companion_id]
    for room in cleared:
        keepers[room] = None
    return sorted(cleared)


def remove(
    state: dict[str, Any], companion_id: str
) -> tuple[dict[str, Any] | None, list[str]]:
    """Drop a user entry, with the rooms it kept (starters: ``(None, [])``).

    Deleting a companion clears the keeper assignments it held; the rooms
    stay configured and simply have no companion. Starters are not
    deleted here — refusing that is the caller's 409 to raise.
    """
    entry = find(state, companion_id)
    if entry is None or is_starter(entry):
        return None, []
    state["crew"] = [e for e in state["crew"] if e is not entry]
    return entry, clear_keepers_for(state, companion_id)


def keeper_of(state: dict[str, Any], room_id: Any) -> dict[str, Any] | None:
    """The keeper summary for one room row, or a null."""
    keepers = state.get("keepers")
    if not isinstance(keepers, dict) or not isinstance(room_id, str):
        return None
    companion_id = keepers.get(room_id)
    if not isinstance(companion_id, str):
        return None
    entry = find(state, companion_id)
    if entry is None:
        return None
    return {
        "id": entry["id"],
        "name": entry["name"],
        "portrait_url": entry.get("portrait_asset"),
        "initial": initial_of(entry["name"]),
    }


def doorway_of(state: dict[str, Any], room_id: Any) -> str | None:
    """The caller's doorway id for one room row, or a null.

    A stored id that is not in the closed list (or an explicit clear)
    reads as no doorway — never a guess the main app would have to
    render.
    """
    doorways = state.get("doorways")
    if not isinstance(doorways, dict) or not isinstance(room_id, str):
        return None
    doorway_id = doorways.get(room_id)
    return doorway_id if is_doorway(doorway_id) else None


def decorate_row(row: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """A room row copy with the caller's ``keeper`` and ``doorway`` added.

    The service's cached row is never mutated, and nothing else about the
    row changes: neither a keeper nor a doorway is a status — both are
    who/what the person put there, never a claim about the room's health.
    """
    out = dict(row)
    out["keeper"] = keeper_of(state, row.get("id"))
    out["doorway"] = doorway_of(state, row.get("id"))
    return out


# ── portraits ────────────────────────────────────────────────────────


def sniff_image_type(data: bytes) -> str | None:
    """The image type the *bytes* are, or None. Magic numbers only.

    PNG signature, JPEG SOI, and the RIFF/WEBP container — a declared
    content type is a claim, these are the bytes themselves.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def image_type_for_path(path: Path) -> str:
    """The media type for a stored portrait file,.

    Derived from the extension this module wrote, and never guessed past
    it: an unknown suffix serves as ``application/octet-stream`` rather
    than being labelled an image it may not be.
    """
    ext = path.suffix.lstrip(".").lower()
    for media_type, candidate in EXT_FOR_TYPE.items():
        if candidate == ext:
            return media_type
    return "application/octet-stream"


def decode_portrait(data_base64: Any) -> tuple[bytes | None, str | None]:
    """``(bytes, error)`` for an upload payload. Exactly one is set.

    ``error`` is a short machine-readable reason the caller maps to a
    status: ``"not_base64"`` (malformed) or ``"too_large"`` (over the
    decoded cap, checked both before and after decoding so an oversized
    payload is refused without being fully decoded).
    """
    if not isinstance(data_base64, str) or not data_base64:
        return None, "not_base64"
    # Cheap pre-check: base64 is 4 chars per 3 bytes, so a payload longer
    # than this can never decode under the cap.
    if len(data_base64) > (PORTRAIT_MAX_BYTES // 3 + 1) * 4:
        return None, "too_large"
    compact = "".join(data_base64.split())
    try:
        data = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError):
        return None, "not_base64"
    if len(data) > PORTRAIT_MAX_BYTES:
        return None, "too_large"
    return data, None


def portrait_dir(crew_path: Path) -> Path:
    """The portrait directory: a sibling of the principal's crew file.

    Derived from the scoped path the caller already resolved, so it lands
    inside the same per-principal tree (single mode: the data dir) with no
    second path rule to keep in sync.
    """
    return crew_path.parent / "crew-portraits"


def portrait_path(crew_path: Path, companion_id: str, ext: str) -> Path:
    """The portrait file for one companion. A non-slug id has no path."""
    if not is_safe_id(companion_id):
        raise ValueError(f"unsafe companion id: {companion_id!r}")
    if ext not in set(EXT_FOR_TYPE.values()):
        raise ValueError(f"unsupported portrait extension: {ext!r}")
    return portrait_dir(crew_path) / f"{companion_id}.{ext}"


def find_portrait(crew_path: Path, companion_id: str) -> Path | None:
    """The stored portrait for a companion, whatever format it is."""
    if not is_safe_id(companion_id):
        return None
    for ext in EXT_FOR_TYPE.values():
        candidate = portrait_dir(crew_path) / f"{companion_id}.{ext}"
        if candidate.is_file():
            return candidate
    return None


def write_portrait(crew_path: Path, companion_id: str, data: bytes, ext: str) -> Path:
    """Store portrait bytes atomically (0600), replacing any other format.

    The new file is written first and the superseded formats removed
    after, so a failed write never leaves the companion with no portrait.
    """
    target = portrait_path(crew_path, companion_id, ext)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(f".{ext}.tmp")
    tmp.write_bytes(data)
    tmp.chmod(0o600)
    os.replace(tmp, target)
    for other in EXT_FOR_TYPE.values():
        if other == ext:
            continue
        stale = portrait_dir(crew_path) / f"{companion_id}.{other}"
        try:
            stale.unlink()
        except OSError:
            pass
    return target


def delete_portrait(crew_path: Path, companion_id: str) -> bool:
    """Remove every stored format for a companion. True if one was there."""
    removed = False
    for ext in EXT_FOR_TYPE.values():
        path = portrait_dir(crew_path) / f"{companion_id}.{ext}"
        try:
            path.unlink()
            removed = True
        except OSError:
            pass
    return removed
