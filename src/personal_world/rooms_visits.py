"""Worlds-owned room visit state — private, per principal, never sent to rooms.

The Room contract (``room/0``) is a front-door interface: a room knows
nothing about who is looking. This module is the *Worlds* half of that
entry point — it remembers, for one principal, which room they last visited,
which needs they have already marked seen, and therefore what has
changed since. None of it is ever forwarded to a room, and it is stored
on the existing per-principal JSON entry point
(``identity.principal_scoped_path``, kind ``rooms_visits``) with the
same atomic write every other Worlds state file uses — no new store,
no new format family.

The stored shape (one file per principal)::

    {
      "last_visit": {"room_id": "...", "title": null, "link": "...", "at": "..."},
      "rooms": {"<room_id>": {"last_visited_at": "...", "needs_seen": ["..."]}}
    }

Accuracy rules:

* A never-visited room has ``last_visited_at: null`` and
  ``changed_since_visit: 0`` — never "everything changed".
* ``changed_since_visit`` counts a card only when its
  ``freshness.observed_at`` is strictly newer than the visit; an
  unparseable timestamp counts nothing (unknown stays unknown).
* A link is a same-origin path or it is rejected; the store never
  accepts a URL it might be tempted to follow later.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: Stored needs-seen ids per room are capped so one room cannot grow a
#: personal store without bound; the newest ids win.
NEEDS_SEEN_CAP = 500

#: A resume title is a short caption hint, never a payload.
TITLE_MAX = 200
#: A stored link is a path; anything longer is refused rather than
#: silently truncated into a different path.
LINK_MAX = 500
#: A need id address is short and opaque.
NEED_ID_MAX = 200


def empty_state() -> dict[str, Any]:
    """A fresh, empty state: no visit, no seen needs."""
    return {"last_visit": None, "rooms": {}}


def _parse_iso(value: Any) -> datetime | None:
    """RFC 3339-ish → aware UTC datetime, or None. Never raises."""
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def valid_same_origin_link(link: Any) -> bool:
    """True only for a same-origin path the main app may follow.

    Starts with ``/``, does not start with ``//``, carries no scheme, no
    backslash, and no control characters. ``//evil.com`` and
    ``https://x`` are both refused (contract rule 4)."""
    if not isinstance(link, str) or not link:
        return False
    if not link.startswith("/") or link.startswith("//"):
        return False
    if len(link) > LINK_MAX:
        return False
    if "\\" in link or any(ord(ch) < 0x20 or ch == "\x7f" for ch in link):
        return False
    return True


def read_visits(path: Path) -> dict[str, Any]:
    """Load one principal's visit state. Missing/corrupt → empty."""
    if not path.exists():
        return empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_state()
    if not isinstance(data, dict):
        return empty_state()

    state = empty_state()
    last_visit = data.get("last_visit")
    if (
        isinstance(last_visit, dict)
        and isinstance(last_visit.get("room_id"), str)
        and isinstance(last_visit.get("at"), str)
    ):
        title = last_visit.get("title")
        link = last_visit.get("link")
        state["last_visit"] = {
            "room_id": last_visit["room_id"],
            "title": title if isinstance(title, str) else None,
            "link": link if isinstance(link, str) else None,
            "at": last_visit["at"],
        }

    rooms = data.get("rooms")
    if isinstance(rooms, dict):
        for room_id, entry in rooms.items():
            if not isinstance(room_id, str) or not isinstance(entry, dict):
                continue
            visited = entry.get("last_visited_at")
            seen = entry.get("needs_seen")
            if not isinstance(seen, list):
                seen = []
            seen = [s for s in seen if isinstance(s, str)][-NEEDS_SEEN_CAP:]
            state["rooms"][room_id] = {
                "last_visited_at": visited if isinstance(visited, str) else None,
                "needs_seen": seen,
            }
    return state


def write_visits(path: Path, state: dict[str, Any]) -> None:
    """Persist atomically; private bits (0600), no half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    tmp.chmod(0o600)
    os.replace(tmp, path)


def _room_entry(state: dict[str, Any], room_id: str) -> dict[str, Any]:
    rooms = state.setdefault("rooms", {})
    entry = rooms.get(room_id)
    if not isinstance(entry, dict):
        entry = {"last_visited_at": None, "needs_seen": []}
        rooms[room_id] = entry
    if not isinstance(entry.get("needs_seen"), list):
        entry["needs_seen"] = []
    return entry


def record_visit(
    state: dict[str, Any],
    room_id: str,
    *,
    at: str,
    link: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Record a visit: one last-visited time per room plus the resume.

    Idempotent in effect — repeating a visit converges on one stored
    timestamp/resume rather than accumulating rows. ``link`` must have
    already passed :func:`valid_same_origin_link`.
    """
    entry = _room_entry(state, room_id)
    entry["last_visited_at"] = at
    state["last_visit"] = {
        "room_id": room_id,
        "title": title,
        "link": link,
        "at": at,
    }
    return state


def mark_need_seen(
    state: dict[str, Any], room_id: str, need_id: str
) -> dict[str, Any]:
    """Add a need id to the caller's seen list (deduped, capped)."""
    entry = _room_entry(state, room_id)
    seen: list[str] = entry["needs_seen"]
    if need_id not in seen:
        seen.append(need_id)
        if len(seen) > NEEDS_SEEN_CAP:
            del seen[: len(seen) - NEEDS_SEEN_CAP]
    return state


def resume_of(state: dict[str, Any]) -> dict[str, Any] | None:
    """The last visit, or a null."""
    last_visit = state.get("last_visit")
    return last_visit if isinstance(last_visit, dict) else None


def changed_since_visit(cards: Any, last_visited_at: Any) -> int:
    """Count cards observed strictly after the visit.

    Zero when never visited, when the visit time is unparseable, or when
    no card carries a parseable ``freshness.observed_at`` — unknown is
    not "changed".
    """
    visited = _parse_iso(last_visited_at)
    if visited is None or not isinstance(cards, list):
        return 0
    changed = 0
    for card in cards:
        if not isinstance(card, dict):
            continue
        freshness = card.get("freshness")
        if not isinstance(freshness, dict):
            continue
        observed = _parse_iso(freshness.get("observed_at"))
        if observed is not None and observed > visited:
            changed += 1
    return changed


def decorate_row(row: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a room row with the caller's visit fields added.

    The service's cached row is never mutated: this is per-person data
    laid over shared estate health.
    """
    room_id = row.get("id")
    entry = state.get("rooms", {}).get(room_id) if isinstance(room_id, str) else None
    if not isinstance(entry, dict):
        entry = {}
    last_visited = entry.get("last_visited_at")
    if not isinstance(last_visited, str):
        last_visited = None
    seen = entry.get("needs_seen")
    seen = [s for s in seen if isinstance(s, str)] if isinstance(seen, list) else []

    out = dict(row)
    out["last_visited_at"] = last_visited
    out["needs_seen"] = seen
    out["changed_since_visit"] = changed_since_visit(row.get("cards"), last_visited)
    return out


def summarize(rows: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, int]:
    """The attention roll-up over one caller's decorated rows.

    * ``needs_you`` — unseen needs across reachable, understood rooms.
    * ``changed`` — sum of ``changed_since_visit``.
    * ``can_wait`` — cards whose tone is ``when_ready`` (an absent or
      unknown tone is not ``when_ready``).
    * ``unknown`` — needs from unreachable/unknown/incompatible rooms;
      stale needs are never promoted to current.
    * ``unreachable`` — rooms that did not answer.
    """
    needs_you = changed = can_wait = unknown = unreachable = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        reachable = bool(row.get("reachable"))
        status = row.get("status")
        if not reachable:
            unreachable += 1

        room_id = row.get("id")
        entry = state.get("rooms", {}).get(room_id) if isinstance(room_id, str) else None
        seen = set()
        if isinstance(entry, dict) and isinstance(entry.get("needs_seen"), list):
            seen = {s for s in entry["needs_seen"] if isinstance(s, str)}

        needs = row.get("needs_you")
        if isinstance(needs, list):
            unseen = sum(
                1
                for need in needs
                if isinstance(need, dict) and need.get("id") not in seen
            )
        else:
            unseen = 0
        # Only a reachable room we understand contributes current needs;
        # an incompatible room's needs are never current (room/0 rule 14).
        if reachable and status not in ("unknown", "incompatible"):
            needs_you += unseen
        elif status in ("unknown", "incompatible") or not reachable:
            unknown += unseen

        value = row.get("changed_since_visit")
        changed += value if isinstance(value, int) and not isinstance(value, bool) else 0

        cards = row.get("cards")
        if isinstance(cards, list):
            can_wait += sum(
                1
                for card in cards
                if isinstance(card, dict) and card.get("tone") == "when_ready"
            )
    return {
        "needs_you": needs_you,
        "changed": changed,
        "can_wait": can_wait,
        "unknown": unknown,
        "unreachable": unreachable,
    }
