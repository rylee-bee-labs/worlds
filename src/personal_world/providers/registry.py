"""Capability contracts and the provider registry.

A provider is registered against a capability and implements whatever
subset of the contract it supports. The registry fails closed: a missing
or unhealthy provider yields 'unavailable', never an exception, and
never a silently wrong value.

Capabilities are core-owned (framework invariant): a provider may
implement or enrich a capability, never define it. See
docs/NATIVE-BASELINE-AND-ENRICHMENT.md.
"""

from collections.abc import Callable
from typing import Any

from ..envelope import Result, fail
from ..model import Actor, Provider
from ..status import Status


class Contract:
    """Base contract. Providers implement observe() and may implement
    act(). act() without explicit approval is a policy violation."""


class StatusContract(Contract):
    """Observe health/status of something."""

    def observe(self) -> Result:
        raise NotImplementedError


class SourceControlContract(StatusContract):
    """The provider-substitution proof capability: a real forge adapter
    (HTTP API) and the fake-reference both satisfy this same contract."""


class MemoryContract(Contract):
    def search(self, query: str) -> Result:
        raise NotImplementedError


class Registry:
    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}
        self._contracts: dict[str, type[Contract]] = {}
        self._impls: dict[str, Contract] = {}
        self._health_checks: dict[str, Callable[[], bool]] = {}
        #: Short-lived cache of the last health check result per provider,
        #: populated by provider_for() and consumed by observe() to avoid
        #: a redundant impl.observe() call when the health check already
        #: failed.
        self._health_cache: dict[str, bool] = {}
        #: capability keys whose native baseline ships with the core
        self.native_baselines: set[str] = set()

    def define_capability(self, key: str, contract: type[Contract]) -> None:
        self._contracts[key] = contract

    def register(
        self,
        capability: str,
        name: str,
        impl: Contract,
        health_check: Callable[[], bool] | None = None,
        **provider_kwargs,
    ) -> Provider:
        provider = Provider(capability=capability, name=name, **provider_kwargs)
        self._providers[name] = provider
        self._impls[name] = impl
        if health_check is not None:
            self._health_checks[name] = health_check
        return provider

    def provider_for(self, capability: str) -> Provider | None:
        """First healthy provider for a capability, else the first
        registered (marked degraded), else None.

        Populates _health_cache so observe() can short-circuit when the
        health check already proved the provider is unhealthy.
        """
        candidates = [
            p for p in self._providers.values() if p.capability == capability
        ]
        if not candidates:
            return None
        for p in candidates:
            check = self._health_checks.get(p.name)
            if check is None:
                self._health_cache[p.name] = True
                return p
            try:
                healthy = check()
            except Exception:
                healthy = False
            self._health_cache[p.name] = healthy
            if healthy:
                return p
        return candidates[0]

    def impl(self, name: str) -> Contract | None:
        return self._impls.get(name)

    def observe(self, capability: str) -> Result:
        """Fail-closed observation: unavailable providers report
        'unavailable', never raise."""
        p = self.provider_for(capability)
        if p is None:
            return fail(
                Status.NOT_CONFIGURED.value,
                warnings=[f"no provider for capability '{capability}'"],
            )
        # Short-circuit: if provider_for() already ran a health check
        # and it failed, skip the redundant impl.observe() round-trip.
        cached = self._health_cache.get(p.name)
        if cached is False:
            return Result(
                ok=False,
                status="unavailable",
                warnings=[f"provider '{p.name}' health check failed"],
            )
        impl = self._impls.get(p.name)
        try:
            result = impl.observe()
        except Exception as e:  # provider down must never crash the core
            return Result(
                ok=False,
                status="unavailable",
                warnings=[f"provider '{p.name}' failed: {e}"],
            )
        if not isinstance(result, Result):
            result = Result(ok=False, status="unavailable",
                            warnings=[f"provider '{p.name}' returned invalid result"])
        return result

    def actors(self) -> list[Actor]:
        """Staff-directory view of every registered provider."""
        out = []
        for p in self._providers.values():
            status = Status.UNKNOWN.value
            check = self._health_checks.get(p.name)
            if check is not None:
                try:
                    status = Status.HEALTHY.value if check() else Status.NEEDS_ATTENTION.value
                except Exception:
                    status = Status.NEEDS_ATTENTION.value
            out.append(
                Actor(
                    name=p.name,
                    role=p.capability,
                    provider=p.name,
                    capabilities=[p.capability],
                    status=status,
                    secrets="brokered" if p.requires_secrets else "none",
                    writes=p.writes,
                )
            )
        return out

    def status_map(self) -> dict[str, Any]:
        out = {}
        import datetime as _dt
        now = _dt.datetime.now(_dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        for cap in self._contracts:
            r = self.observe(cap)
            out[cap] = {
                "ok": r.ok, "status": r.status, "warnings": r.warnings,
                # "last observed" timestamp the dashboard renders as a
                # relative "age" hint (ROADMAP: stale-surfacing item).
                "last_observed": now,
            }
        return out

    def manifest(self) -> dict[str, Any]:
        """Machine-readable capability manifest (framework contract).

        Answers, per capability: does it exist, does the core provide a
        native baseline, which providers can implement/enrich it, which
        is currently active, and what happens if that provider
        disappears. Provider entries carry mode and replaceability so
        CLI, dashboard, settings-export, and future onboarding all read
        the same truth instead of re-deriving it.
        """
        from ..model import ProviderMode

        out: dict[str, Any] = {}
        for cap, contract in self._contracts.items():
            providers = [
                p for p in self._providers.values() if p.capability == cap
            ]
            has_native_baseline = cap in self.native_baselines
            active = self.provider_for(cap)
            entry = {
                "capability": cap,
                "contract": contract.__name__,
                "native_baseline": has_native_baseline,
                "active_provider": active.name if active else None,
                "providers": [
                    {
                        "name": p.name,
                        "mode": p.mode.value,
                        "replaceable": p.mode != ProviderMode.NATIVE,
                        "required": p.required,
                    }
                    for p in providers
                ],
            }
            if not providers and not has_native_baseline:
                entry["on_last_provider_removed"] = "not_configured"
            elif providers and not has_native_baseline:
                entry["on_last_provider_removed"] = (
                    "unavailable; capability concept remains, connect "
                    "another provider or the native baseline"
                )
            else:
                entry["on_last_provider_removed"] = (
                    "degrades to native baseline"
                )
            out[cap] = entry
        return out
