"""Native Settings Reconciler: generic desired-state reconciliation.

This is the native Settings Reconciler product that ships with Project Worlds.
It provides generic capabilities for:
- Declaring desired state
- Observing actual state
- Computing drift
- Proposing reconciliation actions
- Recording evidence

Users configure their own services through site profiles.
The homelab settings-reconciler is one possible provider, not the only one.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..envelope import Result, fail, ok
from ..status import Status
from ..url_safety import http_urlopen
from .registry import StatusContract


class DesiredState:
    """Represents desired state for a service."""

    def __init__(self, service: str, config: dict[str, Any], source: Path | None = None):
        self.service = service
        self.config = config
        self.source = source
        self.loaded_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "config": self.config,
            "source": str(self.source) if self.source else None,
            "loaded_at": self.loaded_at.isoformat(),
        }


class ObservedState:
    """Represents observed actual state for a service."""

    def __init__(self, service: str, data: dict[str, Any], observed_at: datetime | None = None):
        self.service = service
        self.data = data
        self.observed_at = observed_at or datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "data": self.data,
            "observed_at": self.observed_at.isoformat(),
        }


class DriftItem:
    """Represents a single drift between desired and observed state."""

    def __init__(self, key: str, desired: Any, actual: Any, action: str = "update"):
        self.key = key
        self.desired = desired
        self.actual = actual
        self.action = action

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "desired": self.desired,
            "actual": self.actual,
            "action": self.action,
        }


class ReconciliationPlan:
    """Represents a plan to reconcile drift."""

    def __init__(self, service: str, drift: list[DriftItem], actions: list[dict[str, Any]]):
        self.service = service
        self.drift = drift
        self.actions = actions
        self.created_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "drift": [d.to_dict() for d in self.drift],
            "actions": self.actions,
            "created_at": self.created_at.isoformat(),
            "has_drift": len(self.drift) > 0,
        }


class NativeSettingsReconciler(StatusContract):
    """Native settings reconciliation engine."""

    def __init__(self, desired_path: Path | None = None):
        self.desired_path = desired_path or Path("~/.config/personal-world/reconciler/desired").expanduser()
        self._desired: dict[str, DesiredState] = {}
        self._load()

    def _load(self) -> None:
        """Load desired state from config."""
        if self.desired_path.exists():
            for f in self.desired_path.glob("*.yml"):
                try:
                    import yaml
                    config = yaml.safe_load(f.read_text())
                    self._desired[f.stem] = DesiredState(f.stem, config, f)
                except Exception:  # nosec B110  # one unparseable file must not hide the rest
                    pass
            for f in self.desired_path.glob("*.json"):
                try:
                    config = json.loads(f.read_text())
                    self._desired[f.stem] = DesiredState(f.stem, config, f)
                except Exception:  # nosec B110  # one unparseable file must not hide the rest
                    pass

    def desired_state(self, service: str) -> dict | None:
        """Public read of one service's desired state (config dict) or
        None. The public reader for tools/proposals so callers never
        reach into the private _desired mapping."""
        desired = self._desired.get(service)
        return desired.to_dict() if desired is not None else None

    def observe(self) -> Result:
        """Return current reconciliation status."""
        services = []
        for name, desired in self._desired.items():
            services.append({
                "name": name,
                "desired": desired.to_dict(),
                "source": str(desired.source) if desired.source else None,
            })

        return ok(
            Status.HEALTHY.value,
            data={
                "services": services,
                "count": len(services),
                "desired_path": str(self.desired_path),
            },
        )

    def diff(self, service: str, observed: dict[str, Any]) -> Result:
        """Compute drift between desired and observed state."""
        desired = self._desired.get(service)
        if not desired:
            return fail(
                Status.NOT_CONFIGURED.value,
                warnings=[f"no desired state for service '{service}'"],
            )

        drift = []
        for key, want in desired.config.items():
            have = observed.get(key)
            if have != want:
                drift.append(DriftItem(key, want, have))

        plan = ReconciliationPlan(service, drift, [])
        return ok(
            Status.HEALTHY.value if not drift else Status.NEEDS_ATTENTION.value,
            data=plan.to_dict(),
        )

    def propose(self, service: str, observed: dict[str, Any]) -> Result:
        """Propose reconciliation actions."""
        desired = self._desired.get(service)
        if not desired:
            return fail(
                Status.NOT_CONFIGURED.value,
                warnings=[f"no desired state for service '{service}'"],
            )

        drift = []
        actions = []
        for key, want in desired.config.items():
            have = observed.get(key)
            if have != want:
                drift.append(DriftItem(key, want, have))
                actions.append({
                    "type": "update",
                    "key": key,
                    "from": have,
                    "to": want,
                    "safe": True,  # Default to safe, override in adapters
                })

        plan = ReconciliationPlan(service, drift, actions)
        return ok(
            Status.HEALTHY.value,
            data=plan.to_dict(),
        )


class ServiceAdapter:
    """Base class for service-specific adapters."""

    def __init__(self, service: str, config: dict[str, Any]):
        self.service = service
        self.config = config

    def observe(self) -> Result:
        """Observe actual state of the service."""
        raise NotImplementedError

    def apply(self, actions: list[dict[str, Any]]) -> Result:
        """Apply reconciliation actions."""
        raise NotImplementedError

    def health(self) -> Result:
        """Check service health."""
        raise NotImplementedError


class GenericServiceAdapter(ServiceAdapter):
    """Generic adapter for HTTP-based services."""

    def __init__(self, service: str, config: dict[str, Any]):
        super().__init__(service, config)
        self.base_url = config.get("url", "")
        self.health_endpoint = config.get("health_endpoint", "/health")

    def observe(self) -> Result:
        """Observe actual state via HTTP."""

        try:
            url = f"{self.base_url}{self.health_endpoint}"
            with http_urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return ok(
                    Status.HEALTHY.value,
                    data={"service": self.service, "status": "healthy", "data": data},
                )
        except Exception as e:
            return fail(
                Status.UNAVAILABLE.value,
                warnings=[f"failed to observe {self.service}: {e}"],
            )

    def apply(self, actions: list[dict[str, Any]]) -> Result:
        """Apply actions (generic: log only)."""
        # Generic adapter doesn't apply changes - specific adapters override
        return ok(
            Status.HEALTHY.value,
            data={"service": self.service, "actions_logged": len(actions)},
        )

    def health(self) -> Result:
        """Check health."""
        return self.observe()
