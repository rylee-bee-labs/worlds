"""Sync lore from a room's ``lore`` view into the caller's world.

The Engine room serves rylee_lore as plain items (homelab
``scripts/lab_lore_export.py``). A sync turns each item into *suggested*
lore, keyed ``<source>:<item key>``:

- a new item is added as suggested;
- a suggested item whose words changed is updated; the same words are left
  alone;
- **confirmed lore is never touched**. Only the owner confirms (the world's
  promotion rule), and nothing here holds a ``UserAction``;
- an imported item that is no longer in the source is marked ``gone`` (if
  still suggested), never deleted.

``plan`` says what a sync would do without changing anything (the dry run
behind the "Sync lore" preview); ``apply`` does it. ``confirm`` promotes
chosen suggested items for the owner, and it is called only from a
person's step-up-guarded request.
"""
from __future__ import annotations

from typing import Any

from .model import Lore, LoreState, Provenance
from .world import MutationDenied, UserAction, World

VALUE_FIELDS = ("text", "title", "section", "status", "kind", "file")


def _value(item: dict[str, Any]) -> dict[str, Any]:
    return {k: item.get(k) for k in VALUE_FIELDS if item.get(k) is not None}


def _key(source: str, item: dict[str, Any]) -> str:
    return f"{source}:{item['key']}"


def _items(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        i for i in doc.get("items") or []
        if isinstance(i, dict) and isinstance(i.get("key"), str) and i["key"]
        and isinstance(i.get("text"), str) and i["text"].strip()
    ]


def plan(world: World, doc: dict[str, Any]) -> dict[str, Any]:
    """What a sync would do: counts plus the keys in each group."""
    source = str(doc.get("source") or "lore")
    incoming = {_key(source, i): i for i in _items(doc)}
    new, changed, same, kept = [], [], [], []
    for key, item in incoming.items():
        have = world.lore.get(key)
        if have is None:
            new.append(key)
        elif have.state == LoreState.CONFIRMED:
            kept.append(key)
        elif (have.value or {}) != _value(item):
            changed.append(key)
        else:
            same.append(key)
    gone = [
        k for k, lore in world.lore.items()
        if k.startswith(source + ":") and k not in incoming and lore.state != LoreState.CONFIRMED
        and not (lore.value or {}).get("gone")
    ]
    accepted_waiting = [
        k for k in new + changed + same
        if (incoming[k].get("status") == "accepted")
    ]
    return {
        "source": source,
        "revision": doc.get("revision"),
        "counts": {"new": len(new), "changed": len(changed), "unchanged": len(same),
                   "confirmed_kept": len(kept), "gone": len(gone),
                   "accepted_waiting": len(accepted_waiting)},
        "skipped": doc.get("skipped") or {},
        "new": new, "changed": changed, "gone": gone,
    }


def apply(world: World, doc: dict[str, Any]) -> dict[str, Any]:
    """Do the sync; returns the same report as ``plan`` (made before applying)."""
    report = plan(world, doc)
    source, revision = report["source"], report["revision"] or "unknown"
    incoming = {_key(source, i): i for i in _items(doc)}
    for key in report["new"] + report["changed"]:
        item = incoming[key]
        world.add_lore(Lore(
            key=key, value=_value(item), state=LoreState.SUGGESTED,
            provenance=Provenance(source=f"{source}@{revision}:{item.get('file', '')}", authority="reported"),
        ))
    for key in report["gone"]:
        lore = world.lore[key]
        world.lore[key] = lore.model_copy(update={"value": {**(lore.value or {}), "gone": True}})
    return report


def confirm(world: World, keys: list[str]) -> dict[str, Any]:
    """Promote the chosen suggested/derived lore to confirmed (owner only)."""
    done, skipped = [], []
    for key in keys:
        lore = world.lore.get(key)
        if lore is None or lore.state == LoreState.CONFIRMED:
            skipped.append(key)
            continue
        try:
            world.promote_lore(key, LoreState.CONFIRMED, UserAction(confirmed=True))
            done.append(key)
        except MutationDenied:
            skipped.append(key)
    return {"confirmed": len(done), "skipped": len(skipped), "keys": done}


def accepted_keys(world: World, source: str = "rylee_lore") -> list[str]:
    """Suggested items the source itself marked accepted: the one-tap set."""
    return [
        k for k, lore in world.lore.items()
        if k.startswith(source + ":") and lore.state != LoreState.CONFIRMED
        and (lore.value or {}).get("status") == "accepted" and not (lore.value or {}).get("gone")
    ]
