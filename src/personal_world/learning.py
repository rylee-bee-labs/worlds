"""Teach while building (Book Girl): the person's own learning memory.

Any project may tell Worlds "the person just used an idea" (an
*encounter*). Worlds answers how to teach it this time, from very little
state per concept: how many times it was offered, where it was first met,
and how often the person said "Got it".

- ``first``: offer it ("There's a name for part of what you just made…").
- ``again``: connect it ("You've seen this idea before…" plus the first context).
- ``familiar``: don't offer; just use the word (tappable).
- ``off``: the person chose plain words, or "occasional tips" and one was
  already offered today.

Forgetting is not a failure: a familiar idea is still on the shelf. The
file is private to the person (identity scoped path ``learning``).
"""
from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MODES = ("build", "occasional", "plain")
CONCEPT = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
PROJECT = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
AGAIN_UNTIL = 3  # offers before an idea counts as familiar
GOT_IT_FAMILIAR = 2


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("mode", "build")
    data.setdefault("concepts", {})
    return data


def save(path: Path, data: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def stage_of(entry: dict[str, Any] | None) -> str:
    if not entry:
        return "first"
    if entry.get("got_it", 0) >= GOT_IT_FAMILIAR or entry.get("offered", 0) >= AGAIN_UNTIL:
        return "familiar"
    return "again" if entry.get("offered", 0) >= 1 else "first"


def encounter(data: dict[str, Any], concept: str, project: str, context: str) -> dict[str, Any]:
    """Record that the person used ``concept``; say how to teach it now."""
    entry = data["concepts"].get(concept)
    stage = stage_of(entry)
    mode = data.get("mode", "build")
    if mode == "plain":
        stage = "off" if stage != "familiar" else stage
    elif mode == "occasional" and stage in ("first", "again") and data.get("last_offer_day") == _today():
        stage = "off"
    if entry is None:
        entry = {"offered": 0, "got_it": 0, "first_project": project, "first_context": context[:120],
                 "first_seen": _today(), "projects": []}
        data["concepts"][concept] = entry
    if project not in entry["projects"]:
        entry["projects"] = (entry["projects"] + [project])[-20:]
    entry["last_seen"] = _today()
    if stage in ("first", "again"):
        entry["offered"] += 1
        data["last_offer_day"] = _today()
    reply = {"concept": concept, "stage": stage}
    if stage == "again":
        reply.update(first_context=entry["first_context"], first_project=entry["first_project"])
    return reply


def got_it(data: dict[str, Any], concept: str) -> str:
    entry = data["concepts"].get(concept)
    if entry is None:
        return "first"
    entry["got_it"] = entry.get("got_it", 0) + 1
    return stage_of(entry)
