"""Remember, recall, and the Later shelf: one place, nothing to chase.

- **Remember**: one line from anywhere lands in the person's own journal
  (source ``remember``), where every other part of Worlds already looks.
- **Recall**: ask in plain words. A simple word search (works with every model
  off) over the person's journal, lore, records and the ideas they've met,
  newest and best-matching first. It always says where each answer lives.
- **Later**: ideas kept safe (``later.json``). At most :data:`IN_PROGRESS_MAX`
  are in progress at once; starting a fourth asks to finish or swap one
  first. Nothing is ever dropped.
"""
from __future__ import annotations

import json
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

IN_PROGRESS_MAX = 3
TEXT_MAX = 2000
_WORD = re.compile(r"[\w']+", re.UNICODE)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def words(text: str) -> list[str]:
    return [w.casefold() for w in _WORD.findall(text or "") if len(w) > 1]


def score(query_words: list[str], text: str) -> int:
    """How many of the query's words appear in the text (0 = no match).
    Every word must match; a short query like "lantern door" finds entries
    with both words, in any order."""
    have = set(words(text))
    hits = [w for w in query_words if w in have or any(h.startswith(w) for h in have)]
    return len(hits) if len(hits) == len(query_words) else 0


def recall(query: str, sources: Iterable[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    """Rank ``sources`` ({kind, text, when, where}) for a plain-words query."""
    q = words(query)
    if not q:
        return []
    found = []
    for item in sources:
        s = score(q, item.get("text", "") + " " + item.get("title", ""))
        if s:
            found.append((s, item.get("when") or "", item))
    found.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [item for _, _, item in found[:limit]]


# ── Later shelf ────────────────────────────────────────────────────

def load_later(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        data = {"items": []}
    return data


def save_later(path: Path, data: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def add_later(data: dict[str, Any], text: str, source: str = "worlds") -> dict[str, Any]:
    item = {"id": secrets.token_hex(4), "text": text.strip()[:TEXT_MAX], "state": "later",
            "source": source[:40], "created": _now()}
    data["items"].append(item)
    return item


def in_progress(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [i for i in data["items"] if i.get("state") == "doing"]


def move(data: dict[str, Any], item_id: str, to: str) -> tuple[bool, str, dict[str, Any] | None]:
    """Move an item to later | doing | done. Returns (ok, plain words, item).
    Starting a fourth thing is refused with the three that are in progress."""
    item = next((i for i in data["items"] if i.get("id") == item_id), None)
    if item is None:
        return False, "That idea isn't on the shelf.", None
    if to not in ("later", "doing", "done"):
        return False, "That isn't a place an idea can go.", item
    if to == "doing" and item["state"] != "doing" and len(in_progress(data)) >= IN_PROGRESS_MAX:
        names = "; ".join(i["text"][:60] for i in in_progress(data))
        return False, f"Three things are already in progress ({names}). Finish or set one back first.", item
    item["state"] = to
    item[f"{to}_at"] = _now()
    return True, {"doing": "Started.", "done": "Done. Nice.", "later": "Back on the Later shelf."}[to], item
