"""The World: durable structured state, plus its in-memory store.

The store is deliberately simple for V0 (SQLite file persistence is added
in store.py; this module holds the model container and the mutation gates
that enforce the security rules regardless of caller).
"""

from datetime import UTC, timedelta
from typing import Any

from . import model
from .envelope import Result, ok
from .model import (
    PROMOTION_PATH,
    Fact,
    Intent,
    Lore,
    LoreState,
    Mutability,
    Override,
    Pack,
    Policy,
    PolicyEffect,
    Provenance,
    now,
)


class MutationDenied(Exception):
    """Raised when a caller tries to mutate state it may not touch."""


class UserAction:
    """Explicit, interactive user action. Only this may mutate cemented
    policies. AI inference, automation, imports, discovery, packs, and
    derived lore must go through the observer path, which never holds one."""

    def __init__(self, confirmed: bool = True) -> None:
        self.confirmed = confirmed


class World:
    def __init__(self) -> None:
        self.facts: dict[str, Fact] = {}
        self.intents: dict[str, Intent] = {}
        self.policies: dict[str, Policy] = {}
        self.lore: dict[str, Lore] = {}
        self.capabilities: dict[str, model.Capability] = {}
        self.providers: dict[str, list[model.Provider]] = {}
        self.packs: dict[str, Pack] = {}
        self.accessibility: dict[str, Any] = model.Accessibility().model_dump()
        # Per-person presentation layout (sections order/hidden). World-
        # classified private runtime state; additive, schema unchanged.
        self.layout: dict[str, Any] = {}

    # -- facts -----------------------------------------------------------
    def record_fact(self, fact: Fact) -> Fact:
        self.facts[fact.key] = fact
        return fact

    # -- intent ----------------------------------------------------------
    def set_intent(self, intent: Intent) -> Intent:
        self.intents[intent.key] = intent
        return intent

    # -- policy ----------------------------------------------------------
    def set_policy(self, policy: Policy, actor: UserAction | None = None) -> Policy:
        existing = self.policies.get(policy.key)
        if existing and existing.mutability == Mutability.CEMENTED:
            if actor is None or not actor.confirmed:
                raise MutationDenied(
                    f"policy '{policy.key}' is cemented; only an explicit "
                    "user action may change it"
                )
        self.policies[policy.key] = policy
        return policy

    def cement(self, key: str) -> Policy:
        p = self.policies[key]
        self.policies[key] = p.model_copy(update={"mutability": Mutability.CEMENTED})
        return self.policies[key]

    def check_policy(self, key: str) -> str:
        """Return the effective ruling for a content key.

        'deny' (cemented or normal), 'allow', or 'unknown'.
        Unknown must NEVER silently become allow downstream.
        """
        p = self.policies.get(key)
        if p is None:
            return "unknown"
        return p.effect.value

    # -- lore ------------------------------------------------------------
    def add_lore(self, lore: Lore) -> Lore:
        self.lore[lore.key] = lore
        return lore

    def promote_lore(
        self, key: str, to: LoreState, actor: UserAction | None = None
    ) -> Lore:
        """Suggested/derived lore may only become confirmed through an
        explicit user action. Promotion never happens silently."""
        lore = self.lore[key]
        if to == LoreState.CONFIRMED and (actor is None or not actor.confirmed):
            raise MutationDenied(
                f"lore '{key}' may only be confirmed by an explicit user action"
            )
        if to not in PROMOTION_PATH[lore.state]:
            raise MutationDenied(
                f"lore '{key}' cannot move {lore.state} -> {to}"
            )
        self.lore[key] = lore.model_copy(update={"state": to})
        return self.lore[key]

    # -- capabilities / providers ----------------------------------------
    def register_capability(self, cap: model.Capability) -> model.Capability:
        self.capabilities[cap.key] = cap
        return cap

    def map_provider(self, provider: model.Provider) -> model.Provider:
        self.providers.setdefault(provider.capability, []).append(provider)
        return provider

    def providers_for(self, capability: str) -> list[model.Provider]:
        return list(self.providers.get(capability, []))

    # -- packs -------------------------------------------------------------
    def install_pack(self, pack: Pack, actor: UserAction | None = None) -> Pack:
        """Pack installs never overwrite user state (intent/policy/lore).
        Pack-provided policies land as NORMAL mutability defaults, and a
        cemented user policy always wins."""
        self.packs[pack.key] = pack
        for pkey, pdef in (pack.policies or {}).items():
            existing = self.policies.get(pkey)
            if existing is not None:
                continue  # user state wins
            effect = PolicyEffect(pdef.get("effect", "allow"))
            override = Override(pdef.get("override", "none"))
            self.policies[pkey] = Policy(
                key=pkey,
                effect=effect,
                override=override,
                mutability=Mutability.NORMAL,
                provenance=Provenance(source=f"pack:{pack.key}"),
            )
        return pack

    def uninstall_pack(self, key: str, actor: UserAction | None = None) -> None:
        pack = self.packs.get(key)
        if pack is None:
            return
        del self.packs[key]
        for pkey in (pack.policies or {}):
            p = self.policies.get(pkey)
            if (
                p is not None
                and p.provenance.source == f"pack:{key}"
                and p.mutability != Mutability.CEMENTED
            ):
                del self.policies[pkey]

    # -- staleness ---------------------------------------------------------
    def stale_capabilities(self, max_age_seconds: int | None = None) -> list[str]:
        """Capability keys whose latest observed status is older than
        max_age_seconds. None disables staleness checking (fresh by
        definition) -- observations must never be silently represented
        as current without an explicit freshness contract."""
        if max_age_seconds is None:
            return []
        cutoff = now() - timedelta(seconds=max_age_seconds)
        stale: list[str] = []
        for key, fact in self.facts.items():
            if not key.startswith("capability."):
                continue
            if not key.endswith(".status"):
                continue
            observed = fact.provenance.observed_at
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=UTC)
            if observed < cutoff:
                stale.append(key)
        return sorted(stale)

    # -- summary -----------------------------------------------------------
    def summary(self) -> dict:
        return {
            "facts": len(self.facts),
            "intents": len(self.intents),
            "policies": len(self.policies),
            "cemented_policies": sum(
                1 for p in self.policies.values()
                if p.mutability == Mutability.CEMENTED
            ),
            "lore": {
                s.value: sum(1 for entry in self.lore.values() if entry.state == s)
                for s in LoreState
            },
            # The world's own declared capabilities (a count). Distinct from
            # the provider capability-status map the API serves under
            # `capabilities` — see api.status(); the two used to share one
            # key with different types.
            "declared_capabilities": len(self.capabilities),
            "providers": sum(len(v) for v in self.providers.values()),
            "packs": len(self.packs),
        }


def status(world: World) -> Result:
    return ok("healthy", data=world.summary())
