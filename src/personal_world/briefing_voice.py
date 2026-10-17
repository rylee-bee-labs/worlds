"""Resident voice: deterministic, in-character one-line reports.

Pure functions: no I/O, no clock beyond the current UTC date, which is
used only to pick a stable variant so lines vary day to day but not per
refresh.

The full, curated line tables are in ``briefing_voice_lines.py`` (owned
separately). When that module is present its ``LINES`` /
``KEEPER_LINES`` are used; otherwise this module falls back to a minimal
built-in table of plain lines so a briefing never lacks a voice.

Accuracy minimum (outranks every voice rule, per docs/CHARACTER-HANDBOOK.md):
a line may only state a status and, where the table asks for one, a count
that came from a source. Nothing is invented; counts are the only numbers.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

#: The situation vocabulary every resident table must cover.
SITUATIONS = (
    "arrivals",
    "have_tos",
    "quiet",
    "not_configured",
    "unavailable",
    "unknown",
    "stale",
)

#: Fixed system id -> resident key (contract: worlds-briefing/1 systems).
SYSTEM_RESIDENTS: dict[str, str] = {
    "agents": "robot",
    "estate": "hekek",
    "records": "bruma",
    "interests": "mira",
    "news": "taco-news-truck",
    "threads": "world-tree-squirrel",
}

#: Minimal built-in fallback: plain and accurate, in no particular character.
#: Used only when the curated table module is absent (or a key is missing).
_FALLBACK_LINES: dict[str, list[str]] = {
    "arrivals": [
        "Something new came in: {arrivals}.",
        "{arrivals} new since you were last here.",
        "A few things arrived — {arrivals} in all.",
    ],
    "have_tos": [
        "{have_tos} waiting on you.",
        "A small pile wants a decision: {have_tos}.",
        "{have_tos} to look at when you're ready.",
    ],
    "quiet": [
        "All quiet here.",
        "Nothing needs you right now.",
        "Steady — nothing new here.",
    ],
    "not_configured": [
        "Nothing is plugged in here yet.",
        "No source connected yet.",
        "I have no feed to read yet.",
    ],
    "unavailable": [
        "I can't reach this right now.",
        "No answer from here just now.",
        "This isn't reachable at the moment.",
    ],
    "unknown": [
        "I don't know yet.",
        "No reading yet — I'll keep looking.",
        "Still finding my bearings here.",
    ],
    "stale": [
        "My last look here is a day old.",
        "This reading has gone stale.",
        "I haven't had a fresh look in a while.",
    ],
}

_FALLBACK_KEEPER: dict[str, list[str]] = {
    "greeting": [
        "Welcome in. Your world kept watch.",
        "Hello again — everything's where you left it.",
    ],
    "calm": [
        "All calm. Nothing needs you yet.",
        "Quiet day; I'll keep an eye out.",
    ],
    "busy": [
        "A few things want you when you're ready.",
        "{have_tos} waiting — no rush.",
    ],
    "sleepy": [
        "It's late. The world is resting.",
        "Quiet hours; rest easy.",
    ],
    "celebrating": [
        "{arrivals} new while you were away.",
        "Welcome back to {arrivals} new things.",
    ],
}

try:  # the curated table is written by a separate worker
    from .briefing_voice_lines import KEEPER_LINES as _KEEPER_LINES
    from .briefing_voice_lines import LINES as _LINES
except ImportError:  # pragma: no cover - exercised when the module is absent
    _LINES = _FALLBACK_LINES
    _KEEPER_LINES = _FALLBACK_KEEPER


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _variant(variants, key: str, date: str) -> str | None:
    if not variants:
        return None
    digest = hashlib.sha256(f"{date}:{key}".encode("utf-8")).hexdigest()
    return variants[int(digest, 16) % len(variants)]


def _resident_variants(resident_key: str, situation: str) -> list[str] | None:
    for table in (_LINES, _FALLBACK_LINES):
        if not isinstance(table, dict):
            continue
        by_resident = table.get(resident_key)
        if isinstance(by_resident, dict):
            variants = by_resident.get(situation)
            if isinstance(variants, list) and variants:
                return variants
        # fallback tables may be keyed by situation only
        variants = table.get(situation)
        if isinstance(variants, list) and variants:
            return variants
    return None


def _keeper_variants(mood: str) -> list[str] | None:
    for table in (_KEEPER_LINES, _FALLBACK_KEEPER):
        if not isinstance(table, dict):
            continue
        variants = table.get(mood)
        if isinstance(variants, list) and variants:
            return variants
    return None


def _fill(template: str, counts: dict) -> str:
    return (
        template.replace("{arrivals}", str(counts.get("arrivals", 0)))
        .replace("{have_tos}", str(counts.get("have_tos", 0)))
        .replace("{name}", str(counts.get("name", "")))
    )


def _situation(status, counts: dict) -> str:
    """Status vocabulary first, then counts; everything else is quiet."""
    value = str(status or "")
    if value == "not_configured":
        return "not_configured"
    if value == "unavailable":
        return "unavailable"
    if value == "unknown":
        return "unknown"
    if value == "stale":
        return "stale"
    if counts.get("have_tos", 0) > 0:
        return "have_tos"
    if counts.get("arrivals", 0) > 0:
        return "arrivals"
    return "quiet"


def resident_line(system_id: str, status, counts: dict | None, since_is_set: bool) -> str:
    """One accurate, in-character line for a system's resident."""
    counts = counts or {}
    situation = _situation(status, counts)
    resident_key = SYSTEM_RESIDENTS.get(system_id, system_id)
    variants = _resident_variants(resident_key, situation)
    template = _variant(variants, f"resident:{resident_key}:{situation}", _today())
    if template is None:
        return "Nothing to report."
    return _fill(template, counts)


def keeper_line(mood: str, totals: dict | None, name_hint: str | None = None) -> str:
    """One line from the Keeper, in its voice."""
    totals = dict(totals or {})
    if name_hint:
        totals["name"] = name_hint
    variants = _keeper_variants(mood)
    template = _variant(variants, f"keeper:{mood}", _today())
    if template is None:
        return "The world is here when you need it."
    return _fill(template, totals)
