#!/usr/bin/env python3
"""Contract drift check — READ-ONLY report, never writes repo files.

Re-expressed for the rebuild front door (``personal_world.worlds.production:create_app``;
the old ``personal_world.api:create_app`` is being deleted). It answers, without
mutating anything:

1. spec: does ui/src/generated/openapi.json match a fresh ``openapi()`` from the
   live new app? (gen-openapi.py is the writer; this is the watcher. The dumps
   call below is kept byte-identical to gen-openapi.py on purpose — if someone
   reformats the writer, this check goes red and points at the pair.)
2. inventory: does the committed route inventory (scripts/route-inventory.json)
   match the live new app? The inventory is generated from the live app and
   records every ``/api`` route plus ``/healthz`` as method + path + auth
   requirement, so an added, removed or renamed route — or a changed auth
   requirement — is drift.

Retired from the old check, because the old app's ``personal_world.api_manifest``
is deleted: the curated "ghosts" list (``curated_but_not_registered``) and the
report-only "uncurated" coverage tail. The new inventory is generated from the
live route table, so a curated-but-missing row or an uncurated live route cannot
exist by construction; there is no curation to drift from.

Exit codes: 0 no drift · 1 drift (spec mismatch or inventory mismatch) · 2 the
tool itself failed (app could not boot). No CI wiring: this gate is armed by
Rylee's tap, not by tonight (plan rails).

    uv run python scripts/contract-drift-check.py
    uv run python scripts/contract-drift-check.py --write   # regenerate the inventory
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "ui" / "src" / "generated" / "openapi.json"
INVENTORY = ROOT / "scripts" / "route-inventory.json"
sys.path.insert(0, str(ROOT / "src"))

#: The auth levels the inventory records, derived from the router, not curation.
AUTH_LEVELS = {
    "public": "no router-level principal dependency (a handler may still require a session)",
    "owner": "principal dependency is owner-only: an agent token is refused (403)",
    "any": "principal dependency accepts an owner session or a scoped agent token",
}


def _dump(obj: object) -> str:
    # kept byte-identical to scripts/gen-openapi.py's serialization
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _route_auth(route: object) -> str:
    """``public`` | ``owner`` | ``any`` from the route's principal dependency.

    The rebuild app's principal dependency is the closure ``principal_dependency.<locals>.dep``;
    ``owner_only`` is a bool in its closure. Reading it here is why the inventory can
    state the auth requirement without a hand-curated table.
    """
    owner = any_level = False

    def walk(dependant: object) -> None:
        nonlocal owner, any_level
        call = getattr(dependant, "call", None)
        if call is not None and getattr(call, "__qualname__", "").endswith("principal_dependency.<locals>.dep"):
            owner_only = False
            for cell in getattr(call, "__closure__", None) or ():
                try:
                    value = cell.cell_contents
                except ValueError:  # an empty cell: not the flag we are after
                    continue
                if isinstance(value, bool):
                    owner_only = value
            if owner_only:
                owner = True
            else:
                any_level = True
        for sub in getattr(dependant, "dependencies", []) or ():
            walk(sub)

    dependant = getattr(route, "dependant", None)
    if dependant is not None:
        walk(dependant)
    if owner:
        return "owner"
    if any_level:
        return "any"
    return "public"


def route_inventory(app: object) -> dict:
    """The committed route contract: every ``/api`` route plus ``/healthz``, method + path + auth."""
    routes: list[dict] = []
    for route in app.routes:  # type: ignore[attr-defined]
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or ()
        if not path or not methods:
            continue
        if path != "/healthz" and not path.startswith("/api/"):
            continue  # server machinery (docs/openapi/static) is not the API contract
        for method in sorted(methods):
            if method in ("HEAD", "OPTIONS"):
                continue
            routes.append({"method": method, "path": path, "auth": _route_auth(route)})
    routes.sort(key=lambda row: (row["path"], row["method"]))
    return {
        "format": "worlds-route-inventory/1",
        "source": "personal_world.worlds.production:create_app",
        "auth_levels": AUTH_LEVELS,
        "routes": routes,
    }


def main(argv: list[str]) -> int:
    write = "--write" in argv
    try:
        from personal_world.worlds.production import create_app
    except Exception as exc:  # import-time failure is a tool failure
        print(f"DRIFT-CHECK ERROR: cannot import app: {exc}", file=sys.stderr)
        return 2

    tmp = Path(tempfile.mkdtemp(prefix="pw-drift-"))
    try:
        app = create_app(tmp / "config", tmp / "data")
        fresh_inventory = _dump(route_inventory(app))
        fresh_spec = _dump(app.openapi())
    except Exception as exc:
        print(f"DRIFT-CHECK ERROR: create_app failed: {exc}", file=sys.stderr)
        return 2

    n_routes = len(json.loads(fresh_inventory)["routes"])
    if write:
        INVENTORY.write_text(fresh_inventory)
        print(f"wrote {INVENTORY} — {n_routes} routes")
        return 0

    committed_inventory = INVENTORY.read_text() if INVENTORY.exists() else ""
    committed_spec = SPEC.read_text() if SPEC.exists() else ""
    inventory_drift = fresh_inventory != committed_inventory
    spec_drift = fresh_spec != committed_spec

    def path_count(blob: str) -> str:
        try:
            return str(len(json.loads(blob)["paths"]))
        except (json.JSONDecodeError, KeyError):
            return "unparseable"

    def route_count(blob: str) -> str:
        try:
            return str(len(json.loads(blob)["routes"]))
        except (json.JSONDecodeError, KeyError):
            return "unparseable"

    print("contract drift check (read-only)")
    print(f"  spec       : {'DRIFT' if spec_drift else 'in sync'}"
          f" (live paths: {path_count(fresh_spec)},"
          f" committed: {path_count(committed_spec) if committed_spec else 'absent'})")
    print(f"  inventory  : {'DRIFT' if inventory_drift else 'in sync'}"
          f" (live routes: {n_routes},"
          f" committed: {route_count(committed_inventory) if committed_inventory else 'absent'})")

    if inventory_drift:
        print("               run `uv run python scripts/contract-drift-check.py --write`"
              " to regenerate the committed inventory and review the diff")
    if spec_drift:
        print("               run `uv run python scripts/gen-openapi.py`"
              " to regenerate the committed OpenAPI document")

    if inventory_drift or spec_drift:
        print("RESULT: DRIFT")
        return 1
    print("RESULT: CLEAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
