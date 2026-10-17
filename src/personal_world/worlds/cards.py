"""C2 card envelope: map fetched data onto the words a card shows.

Two shapes live here and they are deliberately different:

* :meth:`CardService.build` produces the C2 result envelope - values, freshness,
  source state, meaning, redacted evidence. It carries request facts (ids,
  paths, status codes) because that is what evidence is for.
* :func:`home_board_defs` produces *display definitions only*: the board the UI
  lays out. No request ids, no paths, no JSONPath, no provider data ever
  reaches it. The UI fetches values separately and renders them here.

The rules that shape both:

* **Missing is not 0.** A field with no match is ``{"text": "unknown"}`` with no
  ``raw`` key at all. An empty list is a real value (``raw`` is ``[]``), not an
  error, and it renders as ``"none"``.
* **Availability and freshness are separate.** A failure still returns an
  envelope, marked ``stale``, keeping the last-good values with ``last_good_at``
  so the reader knows what they are looking at.
* **Play-Nice words only.** ``source_state`` is one of the C2 words; the
  ``error_class`` words stay inside the evidence.
"""

from __future__ import annotations

import datetime as dt
import logging
import math
import re
import time
from typing import Any, Callable

from . import mapping
from .models import Board, Card
from .runner import Fetch, Runner

__all__ = ["CardService", "home_board_defs", "slug", "SOURCE_STATE_FOR_ERROR"]

logger = logging.getLogger(__name__)

UNKNOWN = mapping.UNKNOWN
_NO_MATCH = {"text": UNKNOWN}

#: C2 ``source_state`` for a fetch that failed, keyed by ``error_class``.
#: Missing is its own word, so it is not in this table.
SOURCE_STATE_FOR_ERROR: dict[str, str] = {
    "timeout": "unavailable",
    "connection": "unavailable",
    "http_5xx": "unavailable",
    "redirect_refused": "unavailable",
    "too_large": "unavailable",
    "confinement_denied": "unavailable",
    "auth_failed": "needs_attention",
    "http_4xx": "degraded",
    "malformed": "degraded",
}

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slug(label: str) -> str:
    """``"CPU load" -> "cpu-load"``. The one key function both modules use."""
    return _SLUG_STRIP.sub("-", str(label).strip().lower()).strip("-")


def _unique_slug(label: str, taken: dict[str, int]) -> str:
    """A slug for ``label`` that is unique within one card (-2, -3, ...)."""
    base = slug(label) or "field"
    count = taken.get(base, 0)
    taken[base] = count + 1
    return base if count == 0 else f"{base}-{count + 1}"


def _iso(epoch: float | None) -> str | None:
    """ISO-8601 UTC, or None. ``None`` is "we do not know", never a guess."""
    if not isinstance(epoch, (int, float)):
        return None
    moment = dt.datetime.fromtimestamp(float(epoch), tz=dt.timezone.utc)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


class CardService:
    """Build the C2 envelope for a card, from the runner's classified fetches."""

    def __init__(self, store: Any, runner: Runner, *, clock: Callable[[], float] = time.time) -> None:
        self._store = store
        self._runner = runner
        self._clock = clock

    # ---------------------------------------------------------------- build

    def build(self, card_id: str) -> dict[str, Any] | None:
        """The C2 envelope for one card, or None when the card is not configured."""
        card = self._get("card", card_id)
        if card is None:
            return None
        return self.build_for(card)

    def preview(self, card: Card, document: Any) -> dict[str, Any]:
        """The envelope ``card`` WOULD produce from ``document`` (a sample). No network, nothing stored."""
        now = _iso(self._clock())
        values = self._values(card, document)
        return {
            "card_id": card.id, "source_state": self._source_state_from_status(card, document), "freshness": "current",
            "observed_at": now, "fetched_at": now, "last_good_at": now, "values": values,
            "meter": self._meter(card, values, document),
            "meaning": {"short": card.meaning.short, "full": card.meaning.full},
            "evidence": {"request_id": card.request or (card.requests[0] if card.requests else "preview"), "method": "GET",
                         "path": "(sample)", "status_code": None, "duration_ms": None, "error_class": None},
        }

    def build_for(self, card: Card) -> dict[str, Any]:
        """The C2 envelope for a card object (saved or not): reads its requests through the runner."""
        request_ids = card.request_ids()
        fetches: dict[str, Fetch] = {}
        for request_id in request_ids:
            fetches[request_id] = self._runner.fetch(request_id)

        first_failure: Fetch | None = None
        for request_id in request_ids:
            if not fetches[request_id].ok:
                first_failure = fetches[request_id]
                break
        evidence_fetch = first_failure or fetches[request_ids[0]]

        unconfigured = any(
            fetches[rid].error_class == "confinement_denied"
            and self._not_configured(rid)
            for rid in request_ids
        )

        if unconfigured:
            source_state, freshness = "not_configured", "stale"
            document: Any = None
            last_good_at = None
        elif first_failure is not None:
            source_state = SOURCE_STATE_FOR_ERROR.get(
                first_failure.error_class or "", "unknown"
            )
            freshness = "stale"
            document = self._last_good_document(card, fetches)
            last_good_at = self._last_good_at(request_ids)
        else:
            source_state = self._source_state_from_status(card, self._document(card, fetches))
            freshness = "current"
            document = self._document(card, fetches)
            last_good_at = self._last_good_at(request_ids)

        values = self._values(card, document)

        return {
            "card_id": card.id,
            "source_state": source_state,
            "freshness": freshness,
            "observed_at": _iso(self._clock()),
            "fetched_at": _iso(evidence_fetch.fetched_at),
            "last_good_at": _iso(last_good_at),
            "values": values,
            "meter": self._meter(card, values, document),
            "meaning": {"short": card.meaning.short, "full": card.meaning.full},
            "evidence": evidence_fetch.as_evidence(),
        }

    # ------------------------------------------------------------- internal

    def _get(self, kind: str, obj_id: Any) -> Any:
        try:
            return self._store.get(kind, obj_id)
        except Exception:
            logger.exception("worlds store refused a lookup for %s %r", kind, obj_id)
            return None

    def _not_configured(self, request_id: str) -> bool:
        """True when the request or its provider is absent from the config."""
        request = self._get("request", request_id)
        if request is None:
            return True
        return self._get("provider", request.provider) is None

    def _document(self, card: Card, fetches: dict[str, Fetch]) -> Any:
        """The document fields are read against.

        One ``request`` card maps straight onto its data. An aggregating
        ``requests`` card maps onto ``{"<name>": data}``, keyed by the part of
        each request id after the dot.
        """
        if card.request:
            return fetches[card.request].data
        return {
            request_id.partition(".")[2] or request_id: fetch.data
            for request_id, fetch in fetches.items()
        }

    def _last_good_document(self, card: Card, fetches: dict[str, Fetch]) -> Any:
        """The same shape, but from last-good data wherever this fetch failed."""
        if card.request:
            good = self._runner.last_good(card.request)
            return good[0] if good else None
        document: dict[str, Any] = {}
        for request_id, fetch in fetches.items():
            key = request_id.partition(".")[2] or request_id
            if fetch.ok:
                document[key] = fetch.data
                continue
            good = self._runner.last_good(request_id)
            if good is not None:
                document[key] = good[0]
        return document

    def _last_good_at(self, request_ids: list[str]) -> float | None:
        """The oldest last-good time across the card's requests (None when there is none)."""
        stamps = [t for t in (self._runner.last_good(rid) for rid in request_ids) if t]
        return min((stamp[1] for stamp in stamps if stamp[1] is not None), default=None)

    def _source_state_from_status(self, card: Card, document: Any) -> str:
        """``healthy`` / ``needs_attention`` / ``unknown``, from the card's status map.

        A card with no status map is healthy: the fetch worked and nothing in the
        config says otherwise.
        """
        status = card.status
        if status is None:
            return "healthy"
        try:
            res = mapping.resolve(document, status.path)
        except mapping.MappingError:
            logger.warning("card %s has an unparseable status path %r", card.id, status.path)
            return "unknown"
        found = res.values
        if not found:
            # Nothing matched is never healthy, unless the card says an existing empty list means "no problems".
            return "healthy" if res.found and status.empty == "healthy" else "unknown"
        healthy = status.healthy or []
        attention = status.needs_attention or []
        if status.above is not None:
            first = found[0]
            # A real number above the threshold decides before the lists (a bool or text never counts as a number).
            if isinstance(first, (int, float)) and not isinstance(first, bool) and first > status.above.value:
                return status.above.state
        if status.mode == "first":
            value = found[0]
            if value in healthy:
                return "healthy"
            if value in attention:
                return "needs_attention"
            return "unknown"
        # all / any (C1.3): every extracted value counts. Any value in needs_attention wins in both modes.
        # all: healthy only when EVERY value is healthy (an unrecognised value makes it unknown).
        # any: healthy when AT LEAST ONE value is healthy (unrecognised values are tolerated, e.g. redundant endpoints).
        if any(v in attention for v in found):
            return "needs_attention"
        if status.mode == "all":
            return "healthy" if all(v in healthy for v in found) else "unknown"
        return "healthy" if any(v in healthy for v in found) else "unknown"

    def _values(self, card: Card, document: Any) -> dict[str, dict[str, Any]]:
        """Field key -> ``{"text", "raw"?}``. No match means unknown, never 0."""
        values: dict[str, dict[str, Any]] = {}
        taken: dict[str, int] = {}
        now = dt.datetime.fromtimestamp(self._clock(), tz=dt.timezone.utc)
        for field in card.fields:
            key = _unique_slug(field.label, taken)
            values[key] = self._field_value(document, field, now)
        return values

    def _field_value(self, document: Any, field: Any, now: dt.datetime) -> dict[str, Any]:
        try:
            res = mapping.resolve(document, field.path)
        except mapping.MappingError as exc:
            logger.warning("card field %r has an unparseable path: %s", field.label, exc)
            return dict(_NO_MATCH)
        found = res.values
        if not res.found:
            return dict(_NO_MATCH)  # the path does not exist: unknown, never none or 0
        if field.format == "count":
            n = mapping.count_of(res, field.path)
            if n is None:
                return dict(_NO_MATCH)  # not a list: unknown, never 0
            return {"text": mapping.format_value(n, "number", field.unit, now=now), "raw": n}
        if _is_wildcard(field.path):
            # A wildcard over a list that exists but is empty is a real value:
            # it reads as "none", not "unknown".
            text = ", ".join(mapping.format_value(v, field.format, field.unit, now=now) for v in found)
            return {"text": text or "none", "raw": list(found)}
        if not found:
            return dict(_NO_MATCH)  # missing is not 0: there is no raw to show
        value = found[0] if len(found) == 1 else found
        return {"text": mapping.format_value(value, field.format, field.unit, now=now), "raw": value}

    def _meter(self, card: Card, values: dict[str, dict[str, Any]], document: Any) -> dict[str, Any] | None:
        """The meter: its type, the numbers it draws, and the text a screen reader reads out.

        A number that cannot be resolved is OMITTED (never 0), so the UI draws nothing for it.
        """
        if card.meter is None:
            return None
        keys = _field_keys(card)
        spoken = "; ".join(
            f"{field.label}: {values.get(key, _NO_MATCH)['text']}"
            for field, key in zip(card.fields, keys, strict=True)
        )
        meter: dict[str, Any] = {"type": card.meter.type, "text_equivalent": spoken}
        spec = card.meter
        for name in ("value", "max", "count", "filled"):
            number = self._meter_number(getattr(spec, name), values, document)
            if number is not None:
                meter[name] = number
        if spec.items is not None:
            items = self._meter_items(spec.items, document)
            if items is not None:
                meter["items"] = items
        return meter

    @staticmethod
    def _meter_number(ref: Any, values: dict[str, dict[str, Any]], document: Any) -> int | float | None:
        if ref is None:
            return None
        if isinstance(ref, (int, float)) and not isinstance(ref, bool):
            return ref if math.isfinite(ref) else None
        if isinstance(ref, str) and ref.startswith("$"):
            try:
                res = mapping.resolve(document, ref)
            except mapping.MappingError:
                return None
            raw = res.values[0] if len(res.values) == 1 else None
        else:
            raw = (values.get(ref) or {}).get("raw")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
            return None
        return raw

    @staticmethod
    def _meter_items(path: str, document: Any) -> list[Any] | None:
        try:
            res = mapping.resolve(document, path)
        except mapping.MappingError:
            return None
        if not res.found:
            return None
        items: list[Any] = []
        for value in res.values[:200]:
            if isinstance(value, bool):
                items.append(value)
            elif isinstance(value, (int, float)) and math.isfinite(value):
                items.append(value)
            elif isinstance(value, str):
                items.append(value[:80])
        return items


def _field_keys(card: Card) -> list[str]:
    """Keys for a card's fields: the one keying used by the envelope, the meter and board defs."""
    taken: dict[str, int] = {}
    return [_unique_slug(f.label, taken) for f in card.fields]


def _is_wildcard(path: str) -> bool:
    """True when a path selects a set of items rather than one value.

    Any ``[*]`` step counts, not just a trailing one: ``$.items[*].name`` reads a
    column out of a list, so it is a list of values like ``$.items[*]`` is.
    """
    return "[*]" in path


def home_board_defs(store: Any) -> dict[str, Any] | None:
    """Display definitions for the home board, or None when there is no home board.

    Display only. A request id, a path, a JSONPath, a provider name or any
    fetched data would all be leaks; the UI asks for values through the envelope.
    """
    board = _home_board(store)
    if board is None:
        return None
    items = []
    for item in board.items:
        card = _get_card(store, item.card)
        if card is None:
            continue  # a card that was deleted is skipped, not rendered broken
        items.append(_item_defs(card, item))
    return {"id": board.id, "title": board.title, "items": items}


def _home_board(store: Any) -> Board | None:
    for board in _boards(store):
        if board.home:
            return board
    return None


def _item_defs(card: Card, item: Any) -> dict[str, Any]:
    return {
        "card": card.id,
        "size": item.size,
        "hidden": item.hidden,
        "title": card.title,
        "icon": card.icon,
        "group": card.group,
        "view": card.view,
        "fields": [
            {"key": key, "label": f.label, "format": f.format, "unit": f.unit}
            for f, key in zip(card.fields, _field_keys(card), strict=True)
        ],
        "meter_type": card.meter.type if card.meter else None,
    }


def _boards(store: Any) -> list[Board]:
    try:
        snapshot = store.snapshot()
    except Exception:
        logger.exception("worlds store snapshot failed")
        return []
    return sorted(snapshot.get("board", {}).values(), key=lambda b: b.id)


def _get_card(store: Any, card_id: str) -> Card | None:
    try:
        card = store.get("card", card_id)
    except Exception:
        logger.exception("worlds store refused a lookup for card %r", card_id)
        return None
    return card
