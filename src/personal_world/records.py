"""Records: categorized structured user information that lives INSIDE Memory.

PRODUCT-LANGUAGE §Records ≠ Vault. Records are *person data* — medical
information, work history, identity documents, emergency contacts, and the
other durable structured facts a person chooses to keep. The Vault holds
*security material* (credentials, tokens, keys). The two are distinct by
contract and in code: this module never imports or touches ``vault``.

Storage — reuse, invent nothing
    A record is a World ``Fact`` (the core's structured key-value store),
    keyed under a namespace and persisted to the CALLER's own ``world.json``
    through the existing per-principal entry point (``api._user_paths`` →
    ``identity.principal_scoped_path``, decision #13). Facts are the right
    home because their disclosure profile already matches durable personal
    data: they are *excluded* from shareable exports (``export.world_export``
    carries intents/policies/lore only, never facts) and are present only in
    the encrypted backup artifact — exactly what personal records need.

    A category is itself a small World ``Fact`` (``records/category/<slug>``)
    carrying a display name and a per-principal ``locked`` flag.

    Every mutation also appends a ``JournalKind.SETTINGS_CHANGE`` event to the
    caller's own journal. This is the same state-plus-audit split
    ``PUT /api/sections`` uses: the record's *current* value is in the
    World, the append-only *history* of who changed what is in the Journal.
    No new storage mechanism is introduced.

Locking and step-up
    A locked category hides its *contents* behind a fresh step-up elevation.
    The elevation is enforced by the caller layer server-side (see
    ``api._step_up_authorized``); this module only reports whether a category
    is locked and reads/writes its state. The category name, its record count,
    and its locked flag are always visible (so a person knows what to unlock);
    the record titles and field values are not.
"""

from __future__ import annotations

import re
import secrets
from typing import Any

from .classification import Classification
from .model import Fact, Provenance
from .model import now as _now

#: World Fact key namespaces.
CATEGORY_PREFIX = "records/category/"
ITEM_PREFIX = "records/item/"

_MAX_TITLE = 200
_MAX_CATEGORY = 80
_MAX_FIELDS = 64
_MAX_FIELD_KEY = 64
_MAX_FIELD_VALUE = 2000


class RecordError(ValueError):
    """A record write failed validation. The caller turns this into an
    4xx; nothing is applied when it is raised."""


# ── keys ─────────────────────────────────────────────────────────────
def _slug(value: Any) -> str:
    """A stable, path-safe key segment from arbitrary display text."""
    s = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return s


def category_slug(category: Any) -> str:
    """The slug used to namespace a category, or '' when it is unusable."""
    return _slug(category)


def _category_key(slug: str) -> str:
    return CATEGORY_PREFIX + slug


def _item_key(slug: str, record_id: str) -> str:
    return f"{ITEM_PREFIX}{slug}/{record_id}"


# ── validation ───────────────────────────────────────────────────────
def _clean_fields(fields: Any) -> dict[str, Any]:
    """A record's key-value payload: a flat mapping of string keys to JSON
    scalars (str/int/float/bool/None). Anything richer is rejected — records
    are structured information, not arbitrary JSON blobs."""
    if fields is None:
        return {}
    if not isinstance(fields, dict):
        raise RecordError("fields must be an object of key -> value")
    if len(fields) > _MAX_FIELDS:
        raise RecordError(f"too many fields (max {_MAX_FIELDS})")
    out: dict[str, Any] = {}
    for key, value in fields.items():
        k = str(key).strip()
        if not k or len(k) > _MAX_FIELD_KEY:
            raise RecordError("field keys must be 1-64 chars")
        if isinstance(value, str):
            if len(value) > _MAX_FIELD_VALUE:
                raise RecordError(f"field '{k}' value too long (max {_MAX_FIELD_VALUE})")
        elif value is None or isinstance(value, (bool, int, float)):
            pass
        else:
            raise RecordError(
                f"field '{k}' must be a scalar (string, number, bool, or null)"
            )
        out[k] = value
    return out


# ── categories ───────────────────────────────────────────────────────
def get_category(world, category: Any) -> dict | None:
    """The category's stored metadata {slug, name, locked}, or None."""
    slug = category_slug(category)
    fact = world.facts.get(_category_key(slug)) if slug else None
    if fact is None or not isinstance(fact.value, dict):
        return None
    value = fact.value
    return {
        "slug": value.get("slug", slug),
        "name": value.get("name", slug),
        "locked": bool(value.get("locked", False)),
    }


def ensure_category(world, category: Any, *, locked: bool | None = None) -> dict:
    """Create the category metadata fact if absent; return its current value.
    ``locked`` only changes the flag when explicitly provided."""
    slug = category_slug(category)
    if not slug:
        raise RecordError("category is required")
    existing = get_category(world, slug)
    name = (existing or {}).get("name") or str(category).strip()[:_MAX_CATEGORY]
    if existing is None:
        cur_locked = bool(locked) if locked is not None else False
        value = {"slug": slug, "name": name, "locked": cur_locked}
        world.record_fact(
            Fact(
                key=_category_key(slug),
                value=value,
                provenance=Provenance(source="records", authority="reported"),
                classification=Classification.PRIVATE,
            )
        )
        return value
    if locked is not None and locked != existing["locked"]:
        value = {"slug": slug, "name": name, "locked": bool(locked)}
        world.record_fact(
            Fact(
                key=_category_key(slug),
                value=value,
                provenance=Provenance(source="records", authority="reported"),
                classification=Classification.PRIVATE,
            )
        )
        return value
    return existing


def set_category_locked(world, category: Any, locked: bool) -> dict:
    """Mark a category locked/unlocked for this principal."""
    return ensure_category(world, category, locked=bool(locked))


def is_locked(world, category: Any) -> bool:
    cat = get_category(world, category)
    return bool(cat and cat["locked"])


# ── record reads ─────────────────────────────────────────────────────
def list_categories(world) -> list[dict]:
    """Every category with its record count and a pinned count. Names,
    counts, and the locked flag are always disclosed; contents are not."""
    counts: dict[str, int] = {}
    pinned: dict[str, int] = {}
    for key, fact in world.facts.items():
        if not key.startswith(ITEM_PREFIX) or not isinstance(fact.value, dict):
            continue
        slug = key[len(ITEM_PREFIX) :].split("/", 1)[0]
        counts[slug] = counts.get(slug, 0) + 1
        if fact.value.get("pinned"):
            pinned[slug] = pinned.get(slug, 0) + 1

    cats: dict[str, dict] = {}
    for key, fact in world.facts.items():
        if key.startswith(CATEGORY_PREFIX) and isinstance(fact.value, dict):
            slug = key[len(CATEGORY_PREFIX) :]
            cats[slug] = {
                "slug": slug,
                "name": fact.value.get("name", slug),
                "locked": bool(fact.value.get("locked", False)),
                "count": counts.get(slug, 0),
                "pinned": pinned.get(slug, 0),
            }
    # a category with records but no metadata fact (defensive) still shows.
    for slug, n in counts.items():
        if slug not in cats:
            cats[slug] = {
                "slug": slug,
                "name": slug,
                "locked": False,
                "count": n,
                "pinned": pinned.get(slug, 0),
            }
    return [cats[s] for s in sorted(cats)]


def get_record(world, category: Any, record_id: Any) -> dict | None:
    """One record's current value by category + id, or None."""
    slug = category_slug(category)
    rid = _slug(record_id)
    if not slug or not rid:
        return None
    fact = world.facts.get(_item_key(slug, rid))
    return fact.value if fact is not None and isinstance(fact.value, dict) else None


def list_records(world, category: Any) -> list[dict]:
    """A category's records, oldest first. Caller-layer step-up gates whether
    a locked category's contents reach this far."""
    slug = category_slug(category)
    if not slug:
        return []
    prefix = f"{ITEM_PREFIX}{slug}/"
    items = [
        fact.value
        for key, fact in world.facts.items()
        if key.startswith(prefix) and isinstance(fact.value, dict)
    ]
    items.sort(key=lambda v: str(v.get("created", "")))
    return items


def _search_terms(q: Any) -> list[str]:
    """Lowercased whitespace-separated query terms; [] when there is
    nothing to search for."""
    return [t for t in re.split(r"\s+", str(q or "").strip().lower()) if t]


def _record_haystack(value: dict) -> str:
    """The deterministic, model-free text a record is matched against:
    its title, category name, and every field key and value."""
    parts = [
        str(value.get("title", "")),
        str(value.get("category_name", value.get("category", ""))),
    ]
    fields = value.get("fields")
    if isinstance(fields, dict):
        for key, val in fields.items():
            parts.append(str(key))
            parts.append("" if val is None else str(val))
    return "\n".join(parts).lower()


def search_records(
    world, q: Any, *, category: Any = None, include_locked: bool = False
) -> list[dict]:
    """Deterministic lexical record find — the G-memory door that works
    with every model off: no index, no provider, no embeddings, just
    case-insensitive substring matching over title, category name, and
    field keys/values. ALL whitespace-separated terms must match
    somewhere in the record (AND), the everyday filter behavior a
    person expects.

    Ordering is total and stable — ``updated`` desc, then ``id`` desc —
    so the same query over the same world always answers identically.

    Locked categories fail closed: their records contribute only when
    ``include_locked`` is True, which the caller layer sets exclusively
    from a server-verified step-up (``api._step_up_authorized``), never
    from client trust. ``category`` (a slug) narrows the search to one
    category for the combined browse+filter path.
    """
    terms = _search_terms(q)
    if not terms:
        return []
    only_slug = category_slug(category) if category is not None else None
    out: list[dict] = []
    for key, fact in world.facts.items():
        if not key.startswith(ITEM_PREFIX) or not isinstance(fact.value, dict):
            continue
        slug = key[len(ITEM_PREFIX) :].split("/", 1)[0]
        if only_slug is not None and slug != only_slug:
            continue
        if not include_locked and is_locked(world, slug):
            continue
        value = fact.value
        haystack = _record_haystack(value)
        if all(term in haystack for term in terms):
            out.append(value)
    out.sort(
        key=lambda v: (str(v.get("updated", "")), str(v.get("id", ""))),
        reverse=True,
    )
    return out


def pinned_records(world) -> list[dict]:
    """Pinned records across all NON-locked categories — the Overview feed.
    Locked categories are never surfaced here (an elevation-free view must
    not leak locked content); a locked record is surfaced only through an
    explicitly unlocked ``GET /api/records`` of its category."""
    out: list[dict] = []
    for key, fact in world.facts.items():
        if not key.startswith(ITEM_PREFIX) or not isinstance(fact.value, dict):
            continue
        if not fact.value.get("pinned"):
            continue
        slug = key[len(ITEM_PREFIX) :].split("/", 1)[0]
        if is_locked(world, slug):
            continue
        out.append(fact.value)
    out.sort(key=lambda v: str(v.get("updated", "")), reverse=True)
    return out


# ── record writes ────────────────────────────────────────────────────
def upsert_record(
    world,
    *,
    category: Any,
    title: Any,
    fields: Any = None,
    record_id: Any = None,
    locked: bool | None = None,
    source: str = "user",
) -> dict:
    """Create or update one record. ``record_id`` selects the row when given;
    otherwise a fresh id is minted from the title. ``locked`` (when present)
    sets the containing category's locked flag in the same step-up write."""
    slug = category_slug(category)
    if not slug:
        raise RecordError("category is required")
    ttl = str(title or "").strip()
    if not ttl or len(ttl) > _MAX_TITLE:
        raise RecordError("title must be 1-200 chars")
    clean = _clean_fields(fields)

    # Category is established (and optionally locked) before the item lands,
    # so a locked write is atomic with the elevation that authorized it.
    ensure_category(world, category, locked=locked)

    rid = _slug(record_id) if record_id else ""
    if record_id and not rid:
        raise RecordError("record id is not usable")
    key = _item_key(slug, rid) if rid else None
    existing = world.facts.get(key) if key else None
    prev = existing.value if existing and isinstance(existing.value, dict) else {}
    if not rid:
        rid = f"{_slug(ttl)[:40] or 'record'}-{secrets.token_hex(3)}"
        key = _item_key(slug, rid)

    iso = _now().isoformat()
    value = {
        "id": rid,
        "category": slug,
        "category_name": get_category(world, slug)["name"],
        "title": ttl,
        "fields": clean,
        "pinned": bool(prev.get("pinned", False)),
        "created": prev.get("created", iso),
        "updated": iso,
    }
    world.record_fact(
        Fact(
            key=key,
            value=value,
            provenance=Provenance(source=source, authority="reported"),
            classification=Classification.PRIVATE,
        )
    )
    return value


def set_pinned(world, category: Any, record_id: Any, pinned: bool) -> dict | None:
    """Pin or un-pin an existing record. Returns the updated value, or None
    when the record does not exist."""
    slug = category_slug(category)
    rid = _slug(record_id)
    if not slug or not rid:
        return None
    key = _item_key(slug, rid)
    fact = world.facts.get(key)
    if fact is None or not isinstance(fact.value, dict):
        return None
    value = dict(fact.value)
    value["pinned"] = bool(pinned)
    value["updated"] = _now().isoformat()
    world.record_fact(
        Fact(
            key=key,
            value=value,
            provenance=Provenance(source="records", authority="reported"),
            classification=Classification.PRIVATE,
        )
    )
    return value


def delete_record(world, category: Any, record_id: Any) -> bool:
    """Remove a record. Returns True when one was deleted, False otherwise.
    The category metadata is left in place so its locked flag and any other
    records survive."""
    slug = category_slug(category)
    rid = _slug(record_id)
    if not slug or not rid:
        return False
    key = _item_key(slug, rid)
    if key in world.facts:
        del world.facts[key]
        return True
    return False
