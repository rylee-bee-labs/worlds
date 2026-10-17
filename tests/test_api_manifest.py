"""The endpoint manifest — product decision #17: the API is the Lego box.

`GET /api/manifest` gained an additive `endpoints` key curated in
`api_manifest.py` and verified against the live route table. These tests
guard the properties that make it trustworthy to compose against:

* it never advertises a route that is not registered (no drift);
* the vocabulary stays closed — no invented gate or kind;
* a route the code gates with `require_step_up` is reported as `step-up`;
* a write is either gated or named, in the open, as not elevated;
* the existing capability manifest in `data` is untouched, so the SPA and
  the framework contract keep working;
* the payload carries no credential material and no filesystem path;
* the route stays authenticated.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world.api_manifest import (  # noqa: E402
    AUTH_LEVELS,
    GATES,
    KINDS,
    Endpoint,
    endpoint_manifest,
)

TOKEN = "instancetoken-do-not-leak-4c1b"  # pw-safety: synthetic
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from personal_world.api import create_app
    from personal_world.init import init_world

    monkeypatch.setenv("PW_API_TOKEN", TOKEN)
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok")
    app = create_app(tmp_path, tmp_path)
    return TestClient(app), app, tmp_path


def _manifest(client):
    response = client.get("/api/manifest", headers=AUTH)
    assert response.status_code == 200
    return response.json()


def _live_gates(app) -> dict[tuple[str, str], set[str]]:
    """(method, path) → declared auth dependency names, read from code."""

    def walk(dep, into: set[str]) -> None:
        call = getattr(dep, "call", None)
        if call is not None:
            into.add(getattr(call, "__name__", ""))
        for sub in getattr(dep, "dependencies", []) or ():
            walk(sub, into)

    index: dict[tuple[str, str], set[str]] = {}
    for route in app.routes:
        methods = getattr(route, "methods", None)
        dependant = getattr(route, "dependant", None)
        if not methods or dependant is None:
            continue
        names: set[str] = set()

        walk(dependant, names)
        for method in methods:
            index[(method.upper(), route.path)] = names
    return index


class TestContractIsAdditive:
    def test_capability_manifest_still_in_data(self, client):
        c, app, _ = client
        payload = _manifest(c)
        assert payload["ok"] is True
        # `data` is the registry manifest the SPA and the framework
        # contract already consume; it must keep its shape.
        assert isinstance(payload["data"], dict)
        assert "source_control" in payload["data"]
        assert "endpoints" in payload

    def test_route_requires_auth(self, client):
        c, _, _ = client
        assert c.get("/api/manifest").status_code == 401


class TestNoDrift:
    def test_every_curated_endpoint_is_registered(self, client):
        _, app, _ = client
        payload = endpoint_manifest(app.routes)
        assert payload["curated_but_not_registered"] == []
        assert all(row["present"] for row in payload["endpoints"])

    def test_coverage_counts_match_the_rows(self, client):
        _, app, _ = client
        payload = endpoint_manifest(app.routes)
        coverage = payload["coverage"]
        assert coverage["curated"] == len(payload["endpoints"])
        assert coverage["uncurated"] == len(payload["uncurated"])
        assert coverage["curated_present"] == sum(
            1 for row in payload["endpoints"] if row["present"]
        )

    def test_uncurated_reports_every_live_api_route_not_curated(self, client):
        """The manifest states its own coverage rather than implying it."""
        _, app, _ = client
        payload = endpoint_manifest(app.routes)
        curated = {(r["method"], r["path"]) for r in payload["endpoints"]}
        live = _live_gates(app)
        expected = {
            key
            for key in live
            if key[1].startswith("/api/")
            and key not in curated
            and key[0] not in ("HEAD", "OPTIONS")
        }
        reported = {(r["method"], r["path"]) for r in payload["uncurated"]}
        assert reported == expected
        assert all(row["id"] is None for row in payload["uncurated"])


class TestVocabularyIsClosed:
    def test_required_keys_and_enums(self, client):
        _, app, _ = client
        payload = endpoint_manifest(app.routes)
        required = {
            "id",
            "method",
            "path",
            "capability",
            "kind",
            "gate",
            "auth",
            "present",
        }
        for row in payload["endpoints"] + payload["uncurated"]:
            assert required <= set(row), row
            assert row["kind"] in KINDS, row
            assert row["gate"] in GATES, row
            assert row["auth"] in AUTH_LEVELS, row
            assert isinstance(row["present"], bool), row

    def test_documented_vocabulary_is_served(self, client):
        c, _, _ = client
        payload = _manifest(c)["endpoints"]
        assert payload["vocabulary"]["gate"] == list(GATES)
        assert payload["vocabulary"]["kind"] == list(KINDS)
        assert set(payload["vocabulary"]["gate_meaning"]) == set(GATES)

    def test_a_mutating_verb_is_never_labelled_a_read(self, client):
        _, app, _ = client
        payload = endpoint_manifest(app.routes)
        for row in payload["endpoints"] + payload["uncurated"]:
            if row["method"] in ("PUT", "PATCH", "DELETE"):
                assert row["kind"] == "write", row
            if row["method"] == "POST" and row["kind"] == "read":
                # only an explicitly justified probe (no local mutation)
                assert row.get("note"), row

    def test_ids_and_routes_are_unique(self):
        from personal_world.api_manifest import ENDPOINTS

        ids = [row.id for row in ENDPOINTS]
        assert len(ids) == len(set(ids)), "duplicate manifest id"
        routes = [(row.method, row.path) for row in ENDPOINTS]
        assert len(routes) == len(set(routes)), "duplicate method+path row"


class TestGateHonesty:
    def test_code_declared_step_up_is_never_reported_ungated(self, client):
        """Code outranks curation: a route the server gates with
        `require_step_up` can never be advertised as gate "none". It may
        be reported as the stricter "proposal" gate, which includes that
        elevation plus approved-proposal evidence."""
        _, app, _ = client
        live = _live_gates(app)
        payload = endpoint_manifest(app.routes)
        for row in payload["endpoints"] + payload["uncurated"]:
            deps = live.get((row["method"], row["path"]), set())
            if "require_step_up" in deps:
                assert row["gate"] in ("step-up", "proposal"), row

    def test_public_rows_really_have_no_auth_dependency(self, client):
        _, app, _ = client
        live = _live_gates(app)
        payload = endpoint_manifest(app.routes)
        for row in payload["endpoints"]:
            if row["auth"] != "public":
                continue
            deps = live.get((row["method"], row["path"]), set())
            assert "require_auth" not in deps, row
            assert "require_step_up" not in deps, row

    def test_writes_are_gated_or_named(self, client):
        """Decision #17: never unrestricted mutation. A write that needs
        no elevation must be listed by name, not quietly normalized."""
        _, app, _ = client
        payload = endpoint_manifest(app.routes)
        named = set(payload["writes_without_elevation"])
        for row in payload["endpoints"] + payload["uncurated"]:
            if row["kind"] != "write" or row["gate"] != "none":
                continue
            if row["capability"] in ("auth", "setup"):
                continue  # credential lifecycle, documented exclusion
            if row["path"].startswith(("/api/auth/", "/api/setup")):
                continue
            assert f"{row['method']} {row['path']}" in named, row

    def test_the_proposal_gate_is_the_execute_route(self, client):
        _, app, _ = client
        payload = endpoint_manifest(app.routes)
        proposal = [r for r in payload["endpoints"] if r["gate"] == "proposal"]
        assert [r["path"] for r in proposal] == ["/api/proposals/{proposal_id}/execute"]

    def test_vault_writes_are_step_up_gated(self, client):
        """Owner decision 2026-09-16: Vault set/delete require step-up, not
        bearer-only. The manifest must report the gate the code enforces and
        must NOT list them as writes-without-elevation."""
        _, app, _ = client
        payload = endpoint_manifest(app.routes)
        named = payload["writes_without_elevation"]
        assert "POST /api/vault/set" not in named
        assert "DELETE /api/vault/{name}" not in named
        rows = {f"{r['method']} {r['path']}": r for r in payload["endpoints"]}
        assert rows["POST /api/vault/set"]["gate"] == "step-up"
        assert rows["DELETE /api/vault/{name}"]["gate"] == "step-up"


class TestNoSecrets:
    def test_payload_carries_no_credential_or_path(self, client):
        c, _, tmp_path = client
        response = c.get("/api/manifest", headers=AUTH)
        blob = response.text
        assert TOKEN not in blob
        assert "Bearer" not in blob
        assert str(tmp_path) not in blob
        assert "/home/" not in blob
        payload = response.json()
        assert payload["endpoints"]["source"].startswith(
            "src/personal_world/api_manifest.py"
        )

    def test_serialized_manifest_is_json_clean(self, client):
        _, app, _ = client
        payload = endpoint_manifest(app.routes)
        # round-trips, and every value is a plain JSON scalar/list/dict
        assert json.loads(json.dumps(payload)) == payload


class TestCuratedRowValidation:
    def test_get_cannot_be_a_write(self):
        with pytest.raises(ValueError, match="cannot be a write"):
            Endpoint(
                id="X",
                method="GET",
                path="/x",
                capability="x",
                kind="write",
                gate="none",
            )

    def test_mutating_verb_needs_a_reason_to_be_a_read(self):
        with pytest.raises(ValueError, match="justify kind='read'"):
            Endpoint(
                id="X",
                method="POST",
                path="/x",
                capability="x",
                kind="read",
                gate="none",
            )
        # …and an explicit note is that reason (a probe, not a mutation).
        row = Endpoint(
            id="X",
            method="POST",
            path="/x",
            capability="x",
            kind="read",
            gate="none",
            note="outbound probe",
        )
        assert row.kind == "read"

    def test_closed_enums(self):
        with pytest.raises(ValueError, match="gate must be"):
            Endpoint(
                id="X", method="GET", path="/x", capability="x", kind="read", gate="mfa"
            )
        with pytest.raises(ValueError, match="kind must be"):
            Endpoint(
                id="X",
                method="GET",
                path="/x",
                capability="x",
                kind="mutate",
                gate="none",
            )
        with pytest.raises(ValueError, match="auth must be"):
            Endpoint(
                id="X",
                method="GET",
                path="/x",
                capability="x",
                kind="read",
                gate="none",
                auth="bearer",
            )
