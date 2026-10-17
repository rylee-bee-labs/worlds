"""The core daily loop. Deterministic; correct with no AI attached.

OBSERVE -> VALIDATE -> RECONCILE -> DISCOVER -> POLICY -> JOURNAL -> PRESENT
"""

from .envelope import Result, ok
from .journal import Journal
from .model import Fact, JournalKind, Provenance
from .providers.registry import Registry
from .world import World


def daily(world: World, registry: Registry, journal: Journal,
          *, record: bool = True) -> Result:
    """Run the loop. ``record=True`` (the explicit daily run) journals
    observations and records facts; ``record=False`` presents the same
    digest read-only so a page view never mutates the world."""
    actions: list[str] = []
    warnings: list[str] = []

    # OBSERVE + VALIDATE: every capability through its provider.
    # not_configured is a known-optional state, not an attention
    # item -- the digest lists what matters, not every vacancy.
    statuses = registry.status_map()
    for cap, s in statuses.items():
        if not s["ok"] and s["status"] != "not_configured":
            warnings.append(f"{cap}: {s['status']}")
        elif s["status"] == "not_configured":
            continue
        if not record:
            continue
        journal.record(
            JournalKind.OBSERVATION,
            f"capability {cap}: {s['status']}",
            source="daily-loop",
        )
        world.record_fact(
            Fact(
                key=f"capability.{cap}.status",
                value=s["status"],
                provenance=Provenance(source="daily-loop", provider="registry"),
            )
        )

    # RECONCILE: report drift candidates (intent keys without matching facts)
    for key, intent in world.intents.items():
        fact = world.facts.get(key)
        if fact is not None and fact.value != intent.value:
            actions.append(f"drift: {key}: {fact.value!r} != intent {intent.value!r}")
            if not record:
                continue
            journal.record(
                JournalKind.DRIFT,
                f"{key}: observed {fact.value!r}, intent {intent.value!r}",
                source="daily-loop",
            )

    # DISCOVER: providers newly available but not enabled
    for actor in registry.actors():
        if actor.status == "healthy" and actor.writes == "none":
            actions.append(
                f"available: {actor.name} ({actor.role}) — not enabled for writes"
            )

    # POLICY: nothing to surface that is denied; unknowns stay unknown
    # (surfacing decisions live with presenters, which must call
    # world.check_policy and treat 'unknown' as not-safe)

    # PRESENT
    digest = {
        "world": world.summary(),
        "capabilities": statuses,
        "attention": warnings + actions,
    }
    return ok("healthy", changed=False, warnings=warnings, actions=actions, data=digest)
