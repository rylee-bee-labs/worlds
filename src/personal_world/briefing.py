"""Worlds briefing: what the world knows, composed from its sources.

Contract: ``worlds-briefing/1``. Six fixed systems (agents / estate /
records / interests / news / threads), each with a resident who reports
it. Who is credited is resolved per caller from the person's own crew
(``crew.py``): the Keeper is the chosen companion (or the Assistant, or
Worlds when the personality pack is off), and each system's resident is
that system's starter companion as this person's roster holds it.
Residents are presentation only — never a status, never invented.

Design rules enforced here:

* **Failure isolation.** One failing source makes only its own system
  ``unavailable``; the briefing is still returned, never a 500.
* **Accuracy.** Nothing is invented. Counts and titles come only from the
  sources; a missing configuration is ``not_configured``; an answer older
  than 24h is ``stale``.
* **Purity where possible.** No I/O of its own: sources are injected and
  each is asked only to observe. ``build_briefing`` also accepts ``now``
  and ``since``-bearing place data so it is deterministic in tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import crew as crew_registry
from . import voice as voice_mod
from .briefing_voice import keeper_line, resident_line
from .status import Status, worst

BRIEFING_SCHEMA = "worlds-briefing/1"

#: A read older than this is stale, not fresh (contract rule).
STALE_AFTER = timedelta(hours=24)
#: On a return visit, bookmarks touched since the last visit count as
#: arrivals only while they are still inside this window.
ARRIVAL_WINDOW = timedelta(hours=72)
#: On a first visit there is no "since" to bound the range, so arrivals
#: fall back to this tighter window instead of the 72h return window.
FIRST_VISIT_WINDOW = timedelta(hours=24)
#: Project Home attention kinds that are "things to do".
HAVE_TO_KINDS = frozenset({"owner_decision", "tool_failure"})
#: Relative importance for the cross-system have_tos list (lower first).
HAVE_TO_RANK = {"owner_decision": 0, "tool_failure": 1}
#: A room's needs-you is the room asking the person; rank it with tool
#: failures — below an owner decision, above an unranked source item.
ROOM_NEED_RANK = 1

#: A room (contract room/0) mapping a system onto a room's own status
#: vocabulary. ``unreachable`` maps to the existing ``unavailable`` word
#: — never ``healthy``. ``degraded``/``unhealthy`` reuse the words the
#: UI already carries (``warning`` / ``needs_attention``); no new words.
#: ``incompatible`` (a contract this main app does not support) maps to
#: ``needs_attention`` — the existing not-healthy word the UI renders as
#: "Needs attention": a definite mismatch the person should act on, not
#: the softer "unknown".
ROOM_STATUS_TO_SYSTEM_STATUS = {
    "healthy": Status.HEALTHY.value,
    "degraded": Status.WARNING.value,
    "unhealthy": Status.NEEDS_ATTENTION.value,
    "unknown": Status.UNKNOWN.value,
    "unreachable": Status.UNAVAILABLE.value,
    "incompatible": Status.NEEDS_ATTENTION.value,
}

#: Room ids are operator-chosen; folding every non-alphanumeric run to
#: one ``_`` (and lower-casing) lets ``workshop`` match the "Workshop"
#: system while ``engine-room`` matches "Engine room".
_ROOM_KEY_UNSAFE = re.compile(r"[^a-z0-9]+")

#: Fixed systems for v1 (contract table). A system carries no resident of
#: its own: who reports it is resolved per caller from that person's crew
#: (``crew.SYSTEM_RESIDENT``, the canonical system → starter companion
#: map), so a renamed companion is credited by its new name and a hidden
#: or deleted one reads as null rather than a stale hard-coded name.
SYSTEM_SPECS: tuple[dict, ...] = (
    {"id": "agents", "name": "Workshop", "source_name": "Project Home"},
    {"id": "estate", "name": "Engine room", "source_name": "Lab"},
    {"id": "records", "name": "Archive", "source_name": "Journal"},
    {"id": "interests", "name": "Observatory", "source_name": "Discovery"},
    {"id": "news", "name": "Newsstand", "source_name": "Media"},
    {"id": "threads", "name": "World tree", "source_name": "Place"},
)

SYSTEM_IDS: frozenset[str] = frozenset(spec["id"] for spec in SYSTEM_SPECS)

#: statuses that mean "we looked and have an answer"
_OK_STATUSES = frozenset({"healthy", "warning", "needs_attention"})
_FRESH_STATUSES = frozenset({"healthy", "warning", "stale", "needs_attention"})

_FAILED = object()


# ── small helpers ────────────────────────────────────────────────────
def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


def _parse_dt(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _clip(value, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def _sort_key(item: dict):
    dt = _parse_dt(item.get("at"))
    floor = datetime.min.replace(tzinfo=timezone.utc)
    return (dt is not None, dt or floor)


def _newest(items: list[dict]) -> list[dict]:
    return sorted(items, key=_sort_key, reverse=True)


def _mk_item(
    *,
    system: str,
    sid: str,
    kind: str,
    title,
    detail=None,
    at=None,
    link=None,
    rank: int | None = None,
) -> dict:
    item = {
        "id": f"{system}:{sid}",
        "system": system,
        "kind": kind,
        "title": _clip(title, 120) or "Untitled",
        "detail": _clip(detail, 600),
        "at": _iso(at),
        "new": False,
        "link": link,
    }
    if rank is not None:
        item["_rank"] = rank
    return item


#: The keeper resident when the personality pack is off: Worlds itself —
#: the place, never a companion and never a voice (owner canon 2026-09-25).
WORLDS_RESIDENT: dict = {"key": None, "name": "Worlds", "portrait": None}

#: The keeper resident when the pack is on but no usable companion is
#: chosen (none, unknown, hidden, deleted, voiceless, malformed): the
#: Assistant — the plain default helper with a screen for a face.
ASSISTANT_RESIDENT: dict = {
    "key": "assistant",
    "name": "Assistant",
    "portrait": "/assets/crew/256/assistant-portrait.webp",
}


def _resident_summary(entry: dict) -> dict:
    """A crew entry as a briefing resident: its current name and portrait.

    ``portrait`` is the entry's own ``portrait_asset`` or a null;
    nothing is substituted. The key is the crew id — the legacy
    ``personal-world`` key is never emitted.
    """
    portrait = entry.get("portrait_asset")
    return {
        "key": entry.get("id"),
        "name": entry.get("name"),
        "portrait": portrait if isinstance(portrait, str) and portrait else None,
    }


def keeper_resident(pref_values: dict | None, crew_state: dict | None) -> dict:
    """Who speaks the briefing, resolved for this caller.

    Mirrors ``voice.resolve_voice``: pack ``off`` (or absent/unknown) is
    Worlds; a pack-on companion resolves through *this* principal's crew
    and falls back to the Assistant for every non-usable id (none,
    unknown, hidden, deleted, voiceless). ``personal-world`` is never
    emitted. A crew read that is absent or failed confirms nothing, so it
    resolves to the one fallback, never an invented person.
    """
    values = pref_values if isinstance(pref_values, dict) else {}
    if str(values.get("personality_pack") or voice_mod.PACK_OFF) != (
        voice_mod.PACK_RESIDENTS
    ):
        return dict(WORLDS_RESIDENT)
    companion = voice_mod.resolve_voice(values, crew_state).companion
    if companion is None:
        return dict(ASSISTANT_RESIDENT)
    entry = (
        crew_registry.find(crew_state, companion.id)
        if isinstance(crew_state, dict)
        else None
    )
    if entry is None:
        # resolve_voice confirmed the entry; the roster changed between
        # the two reads. fallback, never a guess.
        return dict(ASSISTANT_RESIDENT)
    return _resident_summary(entry)


def system_resident(system_id: str, crew_state: dict | None) -> dict | None:
    """The starter companion who reports one system, from this caller's crew.

    The id comes only from the canon map (``crew.SYSTEM_RESIDENT``); the
    name and portrait are the roster's current ones, so a rename is
    credited. Hidden, deleted, unnamed, or an unconfirmable crew reads as
    a null (the plain emblem) — never an invented resident.
    """
    companion_id = crew_registry.SYSTEM_RESIDENT.get(system_id)
    if not companion_id:
        return None
    entry = (
        crew_registry.find(crew_state, companion_id)
        if isinstance(crew_state, dict)
        else None
    )
    if entry is None or entry.get("hidden") is True:
        return None
    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    return _resident_summary(entry)


@dataclass
class _System:
    spec: dict
    status: str
    source: dict
    items: list[dict] = field(default_factory=list)
    have_tos: list[dict] = field(default_factory=list)
    arrivals: list[dict] = field(default_factory=list)

    @property
    def counts(self) -> dict:
        return {"arrivals": len(self.arrivals), "have_tos": len(self.have_tos)}


def _spec(system_id: str) -> dict:
    for spec in SYSTEM_SPECS:
        if spec["id"] == system_id:
            return spec
    raise KeyError(system_id)


# ── rooms (contract room/0) ──────────────────────────────────────────
# A configured room whose id names a briefing system (by id or by the
# human name shown on the map — e.g. "workshop" names the Workshop /
# ``agents`` system) becomes that system's source. A room with no
# matching system contributes only to the top-level needs-you pool.
def _room_key(value) -> str:
    return _ROOM_KEY_UNSAFE.sub("_", str(value or "").lower()).strip("_")


def _system_id_for_room(row: dict) -> str | None:
    """The briefing system a room row names, or None. First match wins."""
    key = _room_key(row.get("id"))
    if not key:
        return None
    for spec in SYSTEM_SPECS:
        if key in (_room_key(spec["id"]), _room_key(spec["name"])):
            return spec["id"]
    return None


def system_id_for_room_id(room_id: str) -> str | None:
    """The briefing system a configured room id names, or None.

    The one public entry point over the fold above, so a second reader (the crew
    registry's canon keeper defaults) resolves a room id exactly as the
    briefing does instead of growing a parallel rule.
    """
    return _system_id_for_room({"id": room_id})


def _room_need_items(system_id, row: dict) -> list[dict]:
    """A room's ``needs_you`` as briefing have_to items. Never invented:
    an entry that is not an object is skipped, ``why`` is the detail."""
    items: list[dict] = []
    for i, need in enumerate(row.get("needs_you") or []):
        if not isinstance(need, dict):
            continue
        items.append(_mk_item(
            system=system_id,
            sid=str(need.get("id") or f"need-{i}"),
            kind="have_to",
            title=need.get("title") or "Needs you",
            detail=need.get("why"),
            at=need.get("created_at"),
            rank=ROOM_NEED_RANK,
        ))
    return items


def _room_system(spec: dict, row: dict, now: datetime) -> _System:
    """The system as its room reports it: status from the room word
    (``unreachable`` -> ``unavailable``, never ``healthy``) and
    needs-you from the room's own list. Rooms report no arrivals, so
    there are none."""
    status = ROOM_STATUS_TO_SYSTEM_STATUS.get(
        str(row.get("status") or ""), Status.UNKNOWN.value
    )
    have_tos = _room_need_items(spec["id"], row)
    descriptor = row.get("room") if isinstance(row.get("room"), dict) else {}
    observed = _parse_dt(row.get("checked_at"))
    source_name = (
        str(descriptor.get("name") or "").strip()
        or str(row.get("id") or "").strip()
        or spec["source_name"]
    )
    return _System(
        spec=spec,
        status=status,
        source={
            "name": source_name,
            "observed_at": _iso(observed),
            "freshness": _freshness(observed, now),
        },
        items=_newest(have_tos)[:8],
        have_tos=_newest(have_tos),
        arrivals=[],
    )


def _empty(system_id: str, status: str, observed=None) -> _System:
    spec = _spec(system_id)
    return _System(
        spec=spec,
        status=status,
        source={
            "name": spec["source_name"],
            "observed_at": _iso(observed),
            "freshness": _freshness(observed),
        },
    )


def _freshness(observed, now: datetime | None = None) -> str:
    if observed is None:
        return "unknown"
    now = now or datetime.now(timezone.utc)
    return "stale" if (now - observed) > STALE_AFTER else "fresh"


def _age_status(status: str, observed, now: datetime) -> str:
    """A healthy answer older than 24h is 'stale', not fresh."""
    if observed is not None and (now - observed) > STALE_AFTER:
        if status in _FRESH_STATUSES or status in _OK_STATUSES:
            return Status.STALE.value
    return status


def _arrival_in_window(at, since: datetime | None, now: datetime) -> bool:
    """Whether a timestamped item counts as an arrival.

    On a return visit (``since`` set) it must be newer than ``since`` and
    still inside the 72h window; on a first visit there is nothing to
    compare against, so only the tighter 24h window applies. An item with
    no timestamp is left in (there is nothing to judge it by).
    """
    dt = _parse_dt(at)
    if dt is None:
        return True
    if since is not None:
        if dt <= since:
            return False
        return (now - dt) <= ARRIVAL_WINDOW
    return (now - dt) <= FIRST_VISIT_WINDOW


def _observe(source):
    """Ask an injected source to observe. Returns its result or _FAILED."""
    if source is None:
        return _FAILED
    try:
        if hasattr(source, "observe"):
            return source.observe()
        if callable(source):
            return source()
    except Exception:  # noqa: BLE001 — one dead source must not break the briefing
        return _FAILED
    return _FAILED


# ── system builders ──────────────────────────────────────────────────
def _agents(source, now: datetime, since: datetime | None = None) -> _System:
    result = _observe(source)
    if result is _FAILED or result is None:
        return _empty("agents", Status.UNAVAILABLE.value)
    status = str(_get(result, "status") or "")
    if status == Status.NOT_CONFIGURED.value:
        return _empty("agents", Status.NOT_CONFIGURED.value)
    snapshot = _get(result, "snapshot")
    if status == Status.UNAVAILABLE.value or not isinstance(snapshot, dict):
        return _empty("agents", Status.UNAVAILABLE.value)

    observed = _parse_dt(_get(result, "observed_at")) or _parse_dt(
        snapshot.get("observed_at")
    )
    have_tos: list[dict] = []
    arrivals: list[dict] = []

    for a in snapshot.get("attention_items") or []:
        if not isinstance(a, dict):
            continue
        kind = str(a.get("kind") or "")
        title = a.get("title") or a.get("detail") or "Attention item"
        detail = a.get("consequence") or a.get("detail")
        sid = str(a.get("id") or f"attention-{len(have_tos) + len(arrivals)}")
        if kind in HAVE_TO_KINDS:
            have_tos.append(_mk_item(
                system="agents", sid=sid, kind="have_to", title=title,
                detail=detail, at=a.get("raised_at"),
                rank=HAVE_TO_RANK.get(kind, 9),
            ))
        elif kind == "maintenance" and not a.get("stale"):
            arrivals.append(_mk_item(
                system="agents", sid=sid, kind="arrival", title=title,
                detail=detail, at=a.get("raised_at"),
            ))

    for b in snapshot.get("bookmarks") or []:
        if not isinstance(b, dict):
            continue
        updated = _parse_dt(b.get("updated_at"))
        if updated is None or not _arrival_in_window(updated, since, now):
            continue
        pretty = _pretty_name(b.get("project_id"))
        working = str(b.get("working_on") or "").splitlines()
        first = working[0].strip() if working and working[0].strip() else ""
        title = f"{pretty}: {first}" if first else pretty
        arrivals.append(_mk_item(
            system="agents", sid=str(b.get("project_id") or f"bookmark-{len(arrivals)}"),
            kind="arrival", title=title, detail=b.get("next_action"),
            at=b.get("updated_at"),
        ))

    return _System(
        spec=_spec("agents"),
        status=_age_status(status, observed, now),
        source={
            "name": "Project Home",
            "observed_at": _iso(observed),
            "freshness": _freshness(observed, now),
        },
        items=_newest(have_tos + arrivals)[:8],
        have_tos=_newest(have_tos),
        arrivals=_newest(arrivals),
    )


def _pretty_name(project_id) -> str:
    raw = str(project_id or "").strip()
    if raw.lower().startswith("proj-"):
        raw = raw[5:]
    return raw.replace("-", " ").replace("_", " ").strip().title() or "Project"


def _rows_map(data: dict) -> dict:
    rows = data.get("rows")
    if isinstance(rows, dict):
        return rows
    if isinstance(rows, list):
        return {
            r.get("row"): r for r in rows
            if isinstance(r, dict) and r.get("row")
        }
    return {}


def _evidence_at(observation: dict):
    evidence = observation.get("evidence")
    if isinstance(evidence, list) and evidence and isinstance(evidence[0], dict):
        return evidence[0].get("observed_at")
    return None


#: "verdict=pass", "key=value", ... — machine noise, never a title.
_KV_FRAGMENT = re.compile(r"\b[A-Za-z_][\w.-]*\s*=\s*(?:\"[^\"]*\"|'[^']*'|\S+)")
#: A few raw lab concept ids that need a human head noun to read well.
_CONCEPT_TITLES = {"last_known_good": "Last known good deploy"}


def _strip_kv_noise(detail: str) -> str:
    return " ".join(_KV_FRAGMENT.sub(" ", detail).split()).strip(" ,;:-")


def _first_sentence(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        return ""
    match = re.match(r"(.+?[.!?])(?:\s|$)", text)
    return match.group(1) if match else text


def _human_concept_title(concept) -> str:
    """A short human title from a raw concept id (``last_known_good``)."""
    raw = str(concept or "").strip()
    if not raw:
        return ""
    known = _CONCEPT_TITLES.get(raw.lower())
    if known:
        return known
    words = [w for w in re.split(r"[_\-.]+", raw) if w]
    text = " ".join(words)
    return text[:1].upper() + text[1:] if text else ""


def _observation_title(obs: dict) -> str:
    """A human title for an estate observation.

    Prose details yield their first sentence; key=value noise is stripped
    and, when nothing readable remains, the title is built from the
    concept. Never the bare word "Observation" or the raw concept id.
    """
    concept = str(obs.get("concept") or "").strip()
    # Most specific words first: the observation's own detail, then its
    # summary, then what its first piece of evidence says.
    evidence = obs.get("evidence")
    first_evidence = (
        evidence[0].get("detail")
        if isinstance(evidence, list) and evidence and isinstance(evidence[0], dict)
        else None
    )
    detail = obs.get("detail") or obs.get("summary") or first_evidence
    cleaned = _strip_kv_noise(" ".join(str(detail).split())) if detail else ""
    title = _first_sentence(cleaned) if cleaned else _human_concept_title(concept)
    if not title or title.lower() == "observation" or title == concept:
        title = _human_concept_title(concept)
    if not title or title.lower() == "observation":
        title = "Lab note"
    return title


def _observation_detail(obs: dict) -> str | None:
    """Everything the observation says, for the expanded view: its detail
    or summary plus each piece of evidence with its source."""
    parts = []
    for key in ("detail", "summary"):
        value = obs.get(key)
        if value and value not in parts:
            parts.append(str(value))
    for ev in obs.get("evidence") or []:
        if isinstance(ev, dict) and ev.get("detail"):
            line = str(ev["detail"])
            if ev.get("source"):
                line += f" ({ev['source']})"
            if line not in parts and ev["detail"] not in parts:
                parts.append(line)
    return _clip(" · ".join(parts), 600) if parts else None


def _observation_items(system: str, row_name: str, row, kind: str) -> list[dict]:
    observations = row.get("observations") if isinstance(row, dict) else None
    if not isinstance(observations, list):
        return []
    out = []
    for i, obs in enumerate(observations):
        if not isinstance(obs, dict):
            continue
        at = obs.get("observed_at") or _evidence_at(obs)
        out.append(_mk_item(
            system=system, sid=f"{row_name}:{i}", kind=kind,
            title=_observation_title(obs), detail=_observation_detail(obs), at=at,
        ))
    return out


def _estate(source, now: datetime, since: datetime | None = None) -> _System:
    result = _observe(source)
    if result is _FAILED or result is None:
        return _empty("estate", Status.UNAVAILABLE.value)
    status = str(_get(result, "status") or "")
    if status == Status.NOT_CONFIGURED.value:
        return _empty("estate", Status.NOT_CONFIGURED.value)
    data = _get(result, "data")
    if status == Status.UNAVAILABLE.value or not isinstance(data, dict):
        return _empty("estate", Status.UNAVAILABLE.value)

    rows = _rows_map(data)
    overall = str(data.get("overall_state") or "").upper()
    have_tos = _observation_items("estate", "urgent", rows.get("urgent"), "have_to")
    arrivals = [
        i for i in _observation_items("estate", "review", rows.get("review"), "arrival")
        if _arrival_in_window(i.get("at"), since, now)
    ]
    observed = _parse_dt(data.get("generated_at"))
    if observed is None:
        observed = max(
            (_parse_dt(i.get("at")) for i in have_tos + arrivals
             if _parse_dt(i.get("at")) is not None),
            default=None,
        )
    if overall == "UNKNOWN":
        resolved = Status.UNKNOWN.value
    elif status in _OK_STATUSES or status == Status.STALE.value:
        resolved = _age_status(status, observed, now)
    else:
        resolved = Status.UNKNOWN.value

    return _System(
        spec=_spec("estate"),
        status=resolved,
        source={
            "name": "Lab",
            "observed_at": _iso(observed),
            "freshness": _freshness(observed, now),
        },
        items=_newest(have_tos + arrivals)[:8],
        have_tos=_newest(have_tos),
        arrivals=_newest(arrivals),
    )


def _interests() -> _System:
    # Discovery moved to the Candy room (2026-10-04). Until a room names
    # "interests", the Observatory is simply not configured.
    return _empty("interests", Status.NOT_CONFIGURED.value)


def _news(now: datetime) -> _System:
    # Media capability is not wired in slice 1b: not_configured.
    return _empty("news", Status.NOT_CONFIGURED.value)


def _journal_events(journal):
    """(events, failed) from a Journal, an events() object, or a list."""
    if journal is None:
        return [], False
    try:
        if isinstance(journal, (list, tuple)):
            return list(journal), False
        if hasattr(journal, "current_events"):
            return list(journal.current_events(500)), False
        if hasattr(journal, "events"):
            return list(journal.events()), False
    except Exception:  # noqa: BLE001
        return [], True
    return [], True


def _event_source(event) -> str:
    return str(_get(_get(event, "provenance", {}), "source") or "")


def _event_ts(event):
    return _get(event, "ts")


def _personal_events(events) -> list:
    personal = [e for e in events if _event_source(e) == "user"]
    return sorted(
        personal,
        key=lambda e: _parse_dt(_event_ts(e))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )


def _thread_item(event) -> dict:
    ts = _event_ts(event)
    return _mk_item(
        system="records", sid=str(_iso(ts) or "thread"), kind="thread",
        title=_get(event, "summary"), detail=None, at=ts,
    )


def _records(journal, now: datetime) -> tuple[_System, dict | None]:
    events, failed = _journal_events(journal)
    if failed:
        return _empty("records", Status.UNAVAILABLE.value), None
    personal = _personal_events(events)
    items = [_thread_item(e) for e in personal][:8]
    thread = items[0] if items else None
    observed = _parse_dt(_event_ts(personal[0])) if personal else None
    # A readable journal is healthy even with no personal entries yet:
    # only an actual read failure is unknown/unavailable. With no new
    # entries the resident's voice falls through to its "quiet".
    status = Status.HEALTHY.value
    return _System(
        spec=_spec("records"),
        status=status,
        source={
            "name": "Journal",
            "observed_at": _iso(observed),
            "freshness": _freshness(observed, now),
        },
        items=items,
    ), thread


def _threads(place, thread: dict | None, now: datetime) -> _System:
    items: list[dict] = []
    observed = None
    if isinstance(place, dict):
        observed = _parse_dt(place.get("updated_at"))
        system_id = place.get("system")
        item_id = place.get("item_id")
        title = f"Last place: {system_id}" if system_id else "Last place"
        items.append(_mk_item(
            system="threads",
            sid=f"{system_id or 'place'}:{item_id or 'last'}",
            kind="thread", title=title, detail=item_id,
            at=place.get("updated_at"),
        ))
    if thread is not None:
        items.append(thread)
    status = Status.HEALTHY.value if items else Status.UNKNOWN.value
    return _System(
        spec=_spec("threads"),
        status=status,
        source={
            "name": "Place",
            "observed_at": _iso(observed),
            "freshness": _freshness(observed, now),
        },
        items=_newest(items)[:8],
    )


# ── composition ──────────────────────────────────────────────────────
def _mark_new(data: dict, since: datetime | None) -> None:
    seen: set[int] = set()

    def visit(item):
        if not isinstance(item, dict):
            return
        if id(item) in seen:
            return
        seen.add(id(item))
        at = _parse_dt(item.get("at"))
        item["new"] = bool(since is not None and at is not None and at > since)

    for system in data.get("systems", []):
        for item in system.get("items", []):
            visit(item)
    for item in data.get("have_tos", []):
        visit(item)
    for item in data.get("arrivals", []):
        visit(item)
    visit(data.get("thread"))


def _strip_private(node) -> None:
    if isinstance(node, dict):
        for key in [k for k in node if isinstance(k, str) and k.startswith("_")]:
            del node[key]
        for value in node.values():
            _strip_private(value)
    elif isinstance(node, list):
        for value in node:
            _strip_private(value)


def _keeper_mood(
    now: datetime, have_tos_total: int, arrivals_total: int, since: datetime | None
) -> str:
    if now.hour >= 22 or now.hour < 5:
        return "sleepy"
    if have_tos_total > 0:
        return "busy"
    if arrivals_total > 0 and have_tos_total == 0:
        return "celebrating"
    if since is None:
        return "greeting"
    return "calm"


def _greeting(now: datetime) -> str:
    """Time-of-day greeting from the server clock ``now`` (local time)."""
    hour = now.hour
    if 5 <= hour <= 11:
        return "Good morning"
    if 12 <= hour <= 16:
        return "Good afternoon"
    if 17 <= hour <= 21:
        return "Good evening"
    return "Hello"


PLACEHOLDER_NAMES = frozenset({"primary person"})


def build_briefing(
    *,
    project_home=None,
    lab=None,
    journal=None,
    place=None,
    rooms: list[dict] | None = None,
    now: datetime | None = None,
    name_hint: str | None = None,
    crew_state: dict | None = None,
    pref_values: dict | None = None,
) -> dict:
    """Compose the briefing. Returns the full ``{ok, status, data}`` body.

    Sources are injected so tests (and the route) can pass fakes or real
    providers; each is observed under its own failure isolation.

    ``rooms`` is one row per configured room (contract room/0),
    already read once by the caller. A room that names a system is that
    system's source — its status and needs-you replace the older direct
    provider's for that system; every room's needs-you also joins the
    top-level list. No rooms means the briefing is exactly as before.

    ``crew_state`` is *this caller's* crew registry (``crew.read_crew``)
    and ``pref_values`` their normalized preferences; together they
    resolve who is credited on each row (see :func:`keeper_resident` and
    :func:`system_resident`). Presentation only: no status, count, or
    item is affected. Absent crew or prefs confirms no one, so the
    briefing credits the fallback rather than inventing a resident.
    """
    now = now or datetime.now().astimezone()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # The previous visit bounds arrivals; computed before the systems so
    # each can apply the since/window rule while it builds its pools.
    since_dt = _parse_dt(place.get("updated_at")) if isinstance(place, dict) else None

    systems = [
        _agents(project_home, now, since_dt),
        _estate(lab, now, since_dt),
        _interests(),
        _news(now),
    ]
    records, thread = _records(journal, now)
    systems.insert(2, records)
    systems.append(_threads(place, thread, now))

    # Rooms override the older direct providers for any system they name.
    if rooms:
        by_system: dict[str, dict] = {}
        for row in rooms:
            if not isinstance(row, dict):
                continue
            sid = _system_id_for_room(row)
            if sid is not None and sid not in by_system:
                by_system[sid] = row
        systems = [
            _room_system(s.spec, by_system[s.spec["id"]], now)
            if s.spec["id"] in by_system
            else s
            for s in systems
        ]

    # Cross-system pools. Every room's needs-you joins the top-level
    # list, whichever system (if any) it names — deduped by item id so a
    # matched room is counted once, not twice.
    have_tos_pool = [i for s in systems for i in s.have_tos]
    for row in rooms or []:
        if not isinstance(row, dict):
            continue
        system_id = _system_id_for_room(row) or str(row.get("id") or "room")
        have_tos_pool.extend(_room_need_items(system_id, row))
    seen_ids: set[str] = set()
    deduped: list[dict] = []
    for item in have_tos_pool:
        if item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])
        deduped.append(item)
    have_tos_pool = deduped
    have_tos_pool.sort(key=_sort_key, reverse=True)          # newest first
    have_tos_pool.sort(key=lambda i: i.get("_rank", 9))       # importance (stable)
    arrivals_pool = _newest([i for s in systems for i in s.arrivals])

    have_tos_total = len(have_tos_pool)
    if have_tos_total > 0:
        overall = Status.NEEDS_ATTENTION.value
    else:
        considered = [s.status for s in systems
                      if s.status != Status.NOT_CONFIGURED.value]
        overall = worst(considered) if considered else Status.HEALTHY.value

    since = _iso(since_dt) if since_dt is not None else None
    arrivals_total = len(arrivals_pool)
    mood = _keeper_mood(now, have_tos_total, arrivals_total, since_dt)
    keeper_name = (name_hint or "").strip() or None
    # The identity layer's built-in owner label is a placeholder, not a
    # name: the Keeper never greets someone as "Primary person".
    if keeper_name is not None and keeper_name.casefold() in PLACEHOLDER_NAMES:
        keeper_name = None

    system_rows = []
    for s in systems:
        counts = s.counts
        system_rows.append({
            "id": s.spec["id"],
            "name": s.spec["name"],
            "resident": system_resident(s.spec["id"], crew_state),
            "status": s.status,
            "voice": resident_line(
                s.spec["id"], s.status, counts, since_dt is not None
            ),
            "counts": counts,
            "source": s.source,
            "items": s.items,
        })

    data = {
        "schema": BRIEFING_SCHEMA,
        "generated_at": _iso(now),
        "since": since,
        "keeper": {
            "line": keeper_line(
                mood,
                {"arrivals": arrivals_total, "have_tos": have_tos_total},
                keeper_name,
            ),
            "greeting": _greeting(now),
            "name": keeper_name,
            "mood": mood,
            "resident": keeper_resident(pref_values, crew_state),
        },
        "systems": system_rows,
        "have_tos": have_tos_pool[:3],
        "have_tos_total": have_tos_total,
        "arrivals": arrivals_pool[:5],
        "thread": thread,
    }

    _mark_new(data, since_dt)
    _strip_private(data)
    return {"ok": True, "status": overall, "data": data}
