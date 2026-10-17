"""Seed config: a working example that exercises every state a card can show.

Contract: docs/rebuild/CONTRACTS.md (C1). The seed is ordinary C1 config -
providers, requests, cards and a home board - written through the same
:meth:`~personal_world.worlds.config_store.ConfigStore.save` the API uses, so it
gets the same validation, references and etags as anything the owner edits.

It points at a **reference provider** (an in-process loopback server, see
:mod:`personal_world.worlds.reference_provider`), which makes the home board
show the whole C2 vocabulary rather than a happy path only:

===============================  ==========================  =================
card                             what it proves             source_state
===============================  ==========================  =================
``reference-status``             status map + meter          healthy
``reference-items``              a list and a total          healthy
``reference-empty``              an empty list reads "none"  healthy
``reference-down``               the provider is failing     unavailable
``reference-bad-data``           the body is not JSON        degraded
``reference-locked``             a credential is missing     needs_attention
===============================  ==========================  =================

Every request is seeded with ``ttl_s: 0``: no caching, no last-good surprise,
each card render is a real fetch against the reference server. That is a
development convenience, not something to copy into a real config.

Idempotent: anything already present is left exactly as it is, so re-seeding an
existing config directory (or one the owner has edited) is safe. Only a secret
*name* (``env:REF_TOKEN``) is written - a secret value never enters a file.
"""

from __future__ import annotations

from typing import Any

from .config_store import ConfigStore
from .models import Board, Card, Provider, Request

__all__ = ["seed_reference_config"]

#: The secret name the seed's bearer provider refers to. The value is supplied
#: by whatever runs the sender; it is never written to disk here.
SECRET_REF = "env:REF_TOKEN"  # nosec B105  # an env-indirection reference; the value itself is never in this file


def seed_reference_config(store: ConfigStore, base_url: str) -> list[str]:
    """Write the reference example into ``store``. Returns the ids it created.

    Objects already in the store are skipped, so this is safe to call on every
    start-up against a directory the owner may have edited.
    """
    created: list[str] = []

    def put(kind: str, obj: Any) -> None:
        if store.get(kind, obj.id) is not None:
            return  # already configured: never overwrite an owner's edit
        store.save(kind, obj)
        created.append(obj.id)

    # -- providers --------------------------------------------------------

    put(
        "provider",
        Provider(
            id="reference",
            name="Reference",
            kind="reference",
            base_url=base_url,
            auth={"type": "bearer", "secret_ref": SECRET_REF},
            network={"lan": True},
        ),
    )
    put(
        "provider",
        Provider(
            id="reference-nokey",
            name="Reference (no key)",
            kind="reference",
            base_url=base_url,
            network={"lan": True},
        ),
    )

    # -- requests ---------------------------------------------------------

    put(
        "request",
        Request(id="reference.status", provider="reference", path="/status", ttl_s=0,
                assertions=[{"status": 200}, {"path": "$.state", "exists": True}]),
    )
    put(
        "request",
        Request(id="reference.items", provider="reference", path="/items", ttl_s=0,
                assertions=[{"path": "$.items", "is_list": True}]),
    )
    put(
        "request",
        Request(id="reference.empty", provider="reference", path="/empty", ttl_s=0,
                assertions=[{"status": 200}]),
    )
    put("request", Request(id="reference.down", provider="reference", path="/boom", ttl_s=0))
    put("request", Request(id="reference.bad", provider="reference", path="/malformed", ttl_s=0))
    put(
        "request",
        Request(id="reference-nokey.locked", provider="reference-nokey", path="/secret", ttl_s=0),
    )

    # -- cards ------------------------------------------------------------

    put(
        "card",
        Card(
            id="reference-status",
            title="Reference status",
            icon="activity",
            request="reference.status",
            view="stat",
            status={"path": "$.state", "healthy": ["ok"]},
            meter={"type": "progress", "value": "cpu", "max": 1.0},
            meaning={
                "concept": "How the reference provider is doing right now.",
                "short": "Is the reference provider answering?",
                "full": (
                    "Reads the reference provider's own status document. The card "
                    "reads healthy while the provider reports its state as ok, and "
                    "needs attention for anything else it reports. The meter is "
                    "the provider's own progress figure, not a guess made here."
                ),
            },
            fields=[
                {"path": "$.uptime", "label": "Uptime", "format": "duration"},
                {"path": "$.cpu", "label": "CPU", "format": "percent"},
                {"path": "$.disk.used", "label": "Disk used", "format": "bytes"},
            ],
        ),
    )
    put(
        "card",
        Card(
            id="reference-items",
            title="Reference items",
            icon="list",
            request="reference.items",
            view="list",
            meaning={
                "concept": "The items the reference provider currently holds.",
                "short": "What is on the reference provider's list?",
                "full": (
                    "Lists the names the reference provider returns, with the total "
                    "it reports itself. The total comes from the provider, so a list "
                    "that looks short of its total is the provider's answer, not a "
                    "truncation here."
                ),
            },
            fields=[
                {"path": "$.items[*].name", "label": "Names", "format": "text"},
                {"path": "$.total", "label": "Total", "format": "number"},
            ],
        ),
    )
    put(
        "card",
        Card(
            id="reference-empty",
            title="Reference empty",
            icon="list",
            request="reference.empty",
            view="list",
            meaning={
                "concept": "A provider that is up and has nothing to say.",
                "short": "The reference provider is answering with an empty list.",
                "full": (
                    "The provider answered normally and returned no items. That is a "
                    "real answer, not a failure: the card reads none and stays "
                    "healthy. A missing value would read unknown instead, which is a "
                    "different thing."
                ),
            },
            fields=[{"path": "$.items[*].name", "label": "Names", "format": "text"}],
        ),
    )
    put(
        "card",
        Card(
            id="reference-down",
            title="Reference down",
            icon="alert",
            request="reference.down",
            view="stat",
            meaning={
                "concept": "The provider is there but is failing.",
                "short": "The reference provider answered with an error.",
                "full": (
                    "The reference provider could not answer this request. The card "
                    "says unavailable and keeps whatever it last saw, marked stale, "
                    "so an old number is never shown as a current one."
                ),
            },
            fields=[{"path": "$.error", "label": "Error", "format": "text"}],
        ),
    )
    put(
        "card",
        Card(
            id="reference-bad-data",
            title="Reference bad data",
            icon="alert",
            request="reference.bad",
            view="stat",
            meaning={
                "concept": "The provider answered with something unreadable.",
                "short": "The reference provider replied, but not with usable data.",
                "full": (
                    "The reference provider answered successfully, but the body was "
                    "not usable JSON. Nothing is invented from it: the card reads "
                    "degraded and every field reads unknown."
                ),
            },
            fields=[{"path": "$.value", "label": "Value", "format": "text"}],
        ),
    )
    put(
        "card",
        Card(
            id="reference-locked",
            title="Reference locked",
            icon="lock",
            request="reference-nokey.locked",
            view="stat",
            meaning={
                "concept": "A provider that needs a credential this config does not have.",
                "short": "The reference provider needs a token that is not set.",
                "full": (
                    "This card asks a provider configured without a credential, and "
                    "the provider refused. It needs attention rather than being "
                    "unavailable: the provider is reachable, it just will not answer "
                    "until the token is available."
                ),
            },
            fields=[{"path": "$.ok", "label": "Unlocked", "format": "text"}],
        ),
    )

    # -- board ------------------------------------------------------------

    put(
        "board",
        Board(
            id="home",
            title="Home",
            home=True,
            items=[
                {"card": "reference-status", "size": "L"},
                {"card": "reference-items", "size": "M"},
                {"card": "reference-empty", "size": "S"},
                {"card": "reference-down", "size": "S"},
                {"card": "reference-bad-data", "size": "M"},
                {"card": "reference-locked", "size": "S"},
            ],
        ),
    )

    return created
