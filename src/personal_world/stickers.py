"""The sticker album: Worlds' achievements, gathered from every app.

Contract ``stickers/0`` (see docs/STICKERS.md). Stickers reward learning,
trying and finding things, never volume, streaks or health. Each person has
one album; every app (Worlds itself and each room that offers ``stickers``)
has a page in it.

Kinds:
  * ``open``   — name, picture and how to earn it are shown from day one;
  * ``riddle`` — only a riddle shows until it's found; a riddle with
    ``whisper`` stays hidden until that neighbour sticker is found;
  * ``secret`` — never shown until found; a page reports only whether
    secrets remain, never how many or which.

Album on disk (per person): ``{"found": {"<app>:<id>": {at, context}},
"placed": {"<app>:<id>": {x, y, r}}}``. Found is forever.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
APP = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
KINDS = ("open", "riddle", "secret")
SHINES = ("paper", "foil", "holo")
MAX_CONTEXT = 120

# Worlds' own set. Art: /assets/stickers/<id>.webp.
_W = [
    # page, id, name, kind, shine, shape, earn-or-riddle, whisper
    ("First steps", "first-light", "First Light", "open", "paper", "circle", "Open Worlds for the very first time.", None),
    ("First steps", "hello-crew", "Hello, Crew", "open", "paper", "star", "Choose your companion.", None),
    ("First steps", "pen-to-paper", "Pen to Paper", "open", "paper", "circle", "Write your first journal note.", None),
    ("First steps", "tied-a-string", "Tied a String", "open", "paper", "circle", "Remember something with the Remember button.", None),
    ("First steps", "found-it", "Found It", "open", "paper", "circle", "Recall finds something you kept.", None),
    ("First steps", "soft-landing", "Soft Landing", "open", "paper", "circle", "Find the Rough night page.", None),
    ("First steps", "pocket", "Pocket Worlds", "riddle", "paper", "circle", "Worlds fits in a place you carry everywhere.", None),
    ("First steps", "sol-hi", "Sol Says Hi", "secret", "holo", "star", "", None),
    ("Rooms", "door-opener", "Door Opener", "open", "paper", "tag", "Look inside a room.", None),
    ("Rooms", "all-doors", "All the Doors", "open", "foil", "tag", "Look inside every connected room.", None),
    ("Rooms", "tap-tap", "Tap, Tap", "open", "paper", "circle", "Answer a room's question with a tap.", None),
    ("Rooms", "own-words", "In My Own Words", "open", "paper", "circle", "Answer a room's question in your own words.", None),
    ("Rooms", "changed-mind", "Changed My Mind", "riddle", "paper", "circle", "Ten minutes is long enough to think again.", None),
    ("Rooms", "outside-door", "From the Outside", "riddle", "paper", "circle", "Some doors open from the outside.", None),
    ("Rooms", "one-more-door", "The Other Door", "riddle", "foil", "circle", "You opened every door. There's one more.", "all-doors"),
    ("Rooms", "bee-visit", "A Bee in the Story", "secret", "holo", "circle", "", None),
    ("Library", "bookworm", "Bookworm", "open", "paper", "book", "Open a book in the Library.", None),
    ("Library", "word-1", "First Word", "open", "paper", "book", "Find your first word with Book Girl.", None),
    ("Library", "word-10", "Word Collector", "open", "foil", "book", "Find 10 words.", None),
    ("Library", "word-25", "Lexicon", "open", "holo", "book", "Find 25 words.", None),
    ("Library", "cover-to-cover", "Cover to Cover", "riddle", "paper", "book", "Every book has a first page and a last page.", None),
    ("Library", "shelf-complete", "Full Shelf", "open", "foil", "book", "Read every book on one shelf.", None),
    ("Library", "two-voices", "Two Voices, One Idea", "riddle", "foil", "circle", "Two voices, one idea.", None),
    ("Library", "behind-curtain", "Behind the Curtain", "secret", "holo", "book", "", None),
    ("Library", "wake-up", "Wake Up, Sleepyhead", "secret", "foil", "circle", "", None),
    ("Memory", "truth-teller", "Truth Teller", "open", "paper", "circle", "Confirm your first lore item.", None),
    ("Memory", "know-thyself", "Know Thyself", "open", "foil", "circle", "Confirm 25 lore items.", None),
    ("Memory", "later-gator", "Later, Gator", "open", "paper", "circle", "Put something on the Later shelf.", None),
    ("Memory", "done-dusted", "Done and Dusted", "open", "paper", "circle", "Finish something from Later.", None),
    ("Memory", "second-draft", "Second Draft", "riddle", "paper", "circle", "Not every correction is a mistake.", None),
    ("Memory", "time-traveller", "Time Traveller", "riddle", "foil", "circle", "Every entry remembers who it used to be.", "second-draft"),
    ("Memory", "juggler", "Juggler", "secret", "foil", "circle", "", None),
    ("The ship", "homebody", "Homebody", "open", "paper", "circle", "Browse what's At home.", None),
    ("The ship", "cartographer", "Cartographer", "open", "paper", "circle", "Open the Computers map.", None),
    ("The ship", "keeper-keys", "Keeper of Keys", "open", "paper", "circle", "Unlock your vault.", None),
    ("The ship", "riff-raff", "Riff Raff", "open", "paper", "circle", "Start a riff with the bees.", None),
    ("The ship", "quiet-hours", "Quiet Is a Feature", "riddle", "paper", "circle", "Quiet is a feature.", None),
    ("The ship", "in-the-dark", "Seen in the Dark", "riddle", "paper", "circle", "Some things are better seen in the dark.", None),
    ("The ship", "ask-a-room", "Ask the Room", "riddle", "paper", "circle", "Ask the right one, and it answers.", None),
    ("The ship", "make-a-wish", "Make a Wish", "secret", "holo", "star", "", None),
    ("The ship", "wishing-star", "Wishing Star", "secret", "holo", "star", "", None),
    ("The ship", "good-manners", "Good Manners", "secret", "paper", "circle", "", None),
    ("The ship", "orbit", "Orbit", "secret", "holo", "circle", "", None),
    ("Constellation", "constellation", "Constellation", "open", "foil", "star", "Find a sticker in three different apps.", None),
    ("Constellation", "honey-handshake", "Honey Handshake", "open", "paper", "circle", "Hive Works: answer your first decision.", None),
    ("Constellation", "frodis-friend", "Fróði's Friend", "open", "paper", "circle", "VEFR: meet a word while building.", None),
    ("Constellation", "stargazer", "Stargazer", "secret", "holo", "star", "", None),
    ("Constellation", "sticker-room", "The Sticker Room", "open", "foil", "circle", "Find 12 stickers.", None),
]

WORLDS: list[dict[str, Any]] = [
    {
        "id": i, "name": n, "kind": k, "shine": sh, "shape": shape, "section": page,
        **({"earn": text} if k == "open" else {"riddle": text} if k == "riddle" else {}),
        **({"whisper": w} if w else {}),
        "art": f"/assets/stickers/{i}.webp",
    }
    for page, i, n, k, sh, shape, text, w in _W
]
WORLDS_BY_ID = {s["id"]: s for s in WORLDS}
#: Earned only from other stickers or saved state, never reported by a tap.
EARNED_ONLY = frozenset({"sticker-room", "constellation", "stargazer", "orbit", "first-light",
                         "later-gator", "done-dusted", "juggler", "truth-teller", "know-thyself",
                         "second-draft", "word-1", "word-10", "word-25", "frodis-friend", "two-voices",
                         "door-opener", "all-doors"})


def load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("found", {})
    data.setdefault("placed", {})
    return data


def save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(path)


def key(app: str, sticker: str) -> str:
    return f"{app}:{sticker}"


def find(data: dict[str, Any], app: str, sticker: str, context: str = "") -> bool:
    """Mark found. True when it's new (found is forever; repeats are no-ops)."""
    k = key(app, sticker)
    if k in data["found"]:
        return False
    data["found"][k] = {
        "at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "context": str(context or "").strip()[:MAX_CONTEXT],
    }
    _cascade(data)
    return True


def _cascade(data: dict[str, Any]) -> None:
    """Stickers earned by other stickers (count milestones, crossovers)."""
    found = data["found"]
    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    total = len(found)
    apps = {k.split(":", 1)[0] for k in found}
    worlds_secrets = [s["id"] for s in WORLDS if s["kind"] == "secret" and s["id"] != "stargazer"]
    earned = []
    if total >= 12:
        earned.append("sticker-room")
    if len(apps) >= 3:
        earned.append("constellation")
    if all(key("worlds", s) in found for s in worlds_secrets):
        earned.append("stargazer")
    for s in earned:
        found.setdefault(key("worlds", s), {"at": now, "context": ""})


def page(app: str, title: str, look: str | None, stickers: list[dict[str, Any]],
         secrets: int, data: dict[str, Any]) -> dict[str, Any]:
    """One album page as the person may see it. Unfound secrets are never
    listed; unfound riddles show only their riddle; whispered riddles stay
    hidden until their neighbour is found."""
    found = data["found"]
    placed = data["placed"]
    shown: list[dict[str, Any]] = []
    unfound_secrets = 0
    for s in stickers:
        sid = s.get("id")
        if not isinstance(sid, str) or not ID.match(sid):
            continue
        k = key(app, sid)
        is_found = k in found
        kind = s.get("kind") if s.get("kind") in KINDS else "open"
        if kind == "secret" and not is_found:
            unfound_secrets += 1
            continue
        whisper = s.get("whisper")
        if kind == "riddle" and not is_found and whisper and key(app, str(whisper)) not in found:
            continue
        item: dict[str, Any] = {
            "id": sid, "kind": kind,
            "shine": s.get("shine") if s.get("shine") in SHINES else "paper",
            "shape": s.get("shape") or "circle",
            "section": s.get("section"),
            "found": is_found,
        }
        if is_found:
            item.update(name=s.get("name"), art=s.get("art"), earn=s.get("earn"),
                        found_at=found[k].get("at"), context=found[k].get("context") or None,
                        placed=placed.get(k))
        elif kind == "riddle":
            item.update(riddle=s.get("riddle"))
        else:
            item.update(name=s.get("name"), art=s.get("art"), earn=s.get("earn"))
        shown.append(item)
    # A room may send secrets as a count only; its found secrets arrive as
    # found keys the room never listed.
    listed = {s.get("id") for s in stickers}
    for k, v in found.items():
        a, sid = k.split(":", 1)
        if a == app and sid not in listed:
            shown.append({"id": sid, "kind": "secret", "found": True, "shine": "holo",
                          "found_at": v.get("at"), "context": v.get("context") or None,
                          "placed": placed.get(k)})
    remaining = unfound_secrets or max(0, int(secrets or 0) - sum(
        1 for k in found if k.startswith(app + ":") and k.split(":", 1)[1] not in listed))
    return {
        "app": app, "title": title, "look": look,
        "stickers": shown,
        "found": sum(1 for s in shown if s["found"]),
        "shown": len(shown),
        "secrets_remain": remaining > 0,
    }
