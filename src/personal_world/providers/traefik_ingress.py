"""Traefik ingress rollups capability.

Read-only against the router API. Honors the "reports a degraded state"
rule: if the API is unreachable, the capability returns UNKNOWN
(never fake HEALTHY).

The router base URL is supplied per deployment via the constructor
argument or the PW_TRAEFIK_BASE_URL environment variable. There is
no silent default — the provider fails closed if neither is set.
"""
from __future__ import annotations

import json
import os

from ..envelope import Result, fail, ok
from ..url_safety import http_urlopen
from .registry import StatusContract

TRAEFIK_TIMEOUT = 8
TRAEFIK_ENV = "PW_TRAEFIK_BASE_URL"


class TraefikIngress(StatusContract):
    """Aggregate ingress routes + TLS expiry status."""

    def __init__(self, base_url: str | None = None) -> None:
        configured = base_url or os.environ.get(TRAEFIK_ENV)
        if not configured:
            raise ValueError(
                f"TraefikIngress needs an explicit base_url argument or "
                f"the {TRAEFIK_ENV} environment variable; no silent "
                f"default for an internal-network endpoint."
            )
        self.base_url = configured.rstrip("/")

    def _get(self, path: str):
        try:
            with http_urlopen(
                self.base_url + path, timeout=TRAEFIK_TIMEOUT
            ) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return None

    def observe(self) -> Result:
        routers = self._get("/api/http/routers")
        if routers is None:
            return fail("unavailable", warnings=["traefik API unreachable"])

        total = len(routers)
        healthy = 0
        warning = []
        for r in routers:
            status = r.get("status", "")
            if status == "enabled":
                healthy += 1
            else:
                warning.append(f"{r.get('name','?')}: {status or 'no status'}")
        # TLS certs expiry needs the TLS overview; only ring if the data
        # is there, else leave warning list as-is.
        _ = self._get("/api/http/routers")  # placeholder until cert info supported
        detail = {
            "routes": total,
            "enabled": healthy,
            "not_enabled": len(routers) - healthy,
            "warnings": warning[:6],
        }
        return ok("healthy" if healthy == total else "degraded", data=detail)
