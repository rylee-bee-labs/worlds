"""Lane R-BE — Records: structured person data living INSIDE Memory.

Contract law (PRODUCT-LANGUAGE §Records ≠ Vault): Records are user
information kept as categories inside Memory, sensitive categories are
LOCKED (step-up), and the Vault (secrets) is a different thing entirely.

Proven here:
- storage reuses the existing machinery — World Facts on the caller's own
  world.json + an append-only journal audit line (no new store invented)
- create / update (same id) / pin / unpin / delete, all step-up gated like
  every structured-state write in the repo (the human-approval ACT)
- locked categories: name + count + locked flag always visible, contents
  return an honest 409 "locked" envelope unless THIS request carries
  server-side step-up (never client trust)
- the step-up-required RED path (loopback exception off, no elevation)
- multi-user isolation: user A never sees user B's records, mirrors
  test_multiuser_phase23.py idioms
- honest degrade when the backing memory provider is absent
- Records never import the Vault and never leak into shareable exports
"""

import ast
import json
import sys
from pathlib import Path

import pytest  # noqa: E402  (pytest collected via file)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

TOKEN = "instancetoken"  # pw-safety: synthetic
AUTH = {"Authorization": f"Bearer {TOKEN}"}
# The loopback dev peer (TestClient) is accepted by _step_up_authorized, so
# the header is belt-and-braces: it mirrors how every other write test in
# this repo presents its elevation.
STEP = {**AUTH, "X-PW-StepUp": "1"}


def _app(tmp_path, monkeypatch, mode="single", token=TOKEN):
    from personal_world.api import create_app
    from personal_world.init import init_world

    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.delenv("PW_PROXY_STEPUP_SECRET", raising=False)
    monkeypatch.setenv("PW_API_TOKEN", token)
    monkeypatch.setenv("PW_IDENTITY_MODE", mode)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok")
    return TestClient(create_app(tmp_path, tmp_path)), tmp_path


def _client(tmp_path, monkeypatch, mode="single"):
    c, _ = _app(tmp_path, monkeypatch, mode=mode)
    return c


def _step_up_denied(monkeypatch):
    """Turn off the documented loopback exception so step-up must be earned
    through a real session grant — the only mechanism left is the delegated
    proxy header, which we withhold in the red tests."""
    import personal_world.api as api_mod

    monkeypatch.setattr(api_mod, "_is_true_loopback", lambda request: False)


def _create(c, headers, *, title="Allergy list", category=None,
            fields=None, **extra):
    body = {
        "category": category or title,
        "title": title,
        "fields": {"penicillin": "hives"} if fields is None else fields,
    }
    body.update(extra)
    return c.post("/api/records", json=body, headers=headers)


# ── storage: reuse the existing machinery, invent no new store ───────

class TestStorageReusesExistingMachinery:
    def test_record_is_a_world_fact_on_the_callers_world_json(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        r = _create(c, STEP)
        assert r.status_code == 200, r.text
        rec = r.json()["data"]
        world = json.loads((tmp_path / "world.json").read_text())
        fact_key = f"records/item/{rec['category']}/{rec['id']}"
        assert fact_key in world["facts"]
        assert world["facts"][fact_key]["value"]["title"] == "Allergy list"
        # records are private-class facts (never settings/world exportable)
        assert world["facts"][fact_key]["classification"] == "private"

    def test_mutation_appends_a_journal_audit_line(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, title="Work history")
        events = [json.loads(x) for x in
                  (tmp_path / "journal.ndjson").read_text().splitlines() if x.strip()]
        hits = [e for e in events
                if e["kind"] == "settings_change" and e["provenance"]["source"] == "records"]
        assert hits, events
        # content-free: the audit names the category, never the field values
        assert all("hives" not in e["summary"] for e in hits)

    def test_records_never_leak_into_shareable_exports(self, tmp_path, monkeypatch):
        from personal_world.app import load_world
        from personal_world.export import settings_export, world_export

        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, title="Passport number", fields={"number": "X1234567"})
        world = load_world(tmp_path / "world.json")
        assert "X1234567" not in json.dumps(settings_export(world))
        assert "X1234567" not in json.dumps(world_export(world))


# ── categories listing (names + counts + locked flag) ─────────────────

class TestCategories:
    def test_counts_and_locked_flag_visible_without_step_up(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, category="music", title="Favourites")
        _create(c, STEP, category="medical", title="Meds", locked=True)
        data = c.get("/api/records/categories", headers=AUTH).json()
        assert data["ok"] is True
        cats = {x["slug"]: x for x in data["data"]["categories"]}
        assert cats["music"] == {
            "slug": "music", "name": "music", "locked": False, "count": 1, "pinned": 0,
        }
        assert cats["medical"]["locked"] is True
        assert cats["medical"]["count"] == 1

    def test_categories_never_carry_record_contents(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, category="id", title="ID docs", fields={"secret": "ssn-111"})
        blob = c.get("/api/records/categories", headers=AUTH).text
        assert "ssn-111" not in blob
        assert "ID docs" not in blob


# ── the record lifecycle: create / update / pin / delete ─────────────

class TestRecordLifecycle:
    def test_create_then_list(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        created = _create(c, STEP, category="insurance", title="Insurance",
                          fields={"plan": "PPO"}).json()["data"]
        got = c.get("/api/records?category=insurance", headers=STEP).json()
        assert got["ok"] is True
        assert [r["id"] for r in got["data"]["records"]] == [created["id"]]
        assert got["data"]["records"][0]["fields"]["plan"] == "PPO"

    def test_update_same_id_is_not_a_duplicate(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        rec = _create(c, STEP, category="address", title="Home",
                      fields={"city": "Portland"}).json()["data"]
        r2 = c.post("/api/records", json={
            "category": "address", "title": "Home",
            "id": rec["id"], "fields": {"city": "Salem"},
        }, headers=STEP).json()
        assert r2["ok"] is True
        assert r2["data"]["id"] == rec["id"]
        # value replaced (current view), created stamp preserved
        assert r2["data"]["fields"]["city"] == "Salem"
        assert r2["data"]["created"] == rec["created"]
        listing = c.get("/api/records?category=address", headers=STEP).json()
        assert len(listing["data"]["records"]) == 1

    def test_pin_surfaces_in_the_overview_view(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        rec = _create(c, STEP, category="emergency", title="ICE").json()["data"]
        r = c.post("/api/records/pin", json={"category": "emergency", "id": rec["id"]},
                   headers=STEP)
        assert r.status_code == 200 and r.json()["data"]["pinned"] is True
        # the Overview feed (?pinned=true) surfaces exactly the pinned record
        feed = c.get("/api/records?pinned=true", headers=AUTH).json()
        assert [x["id"] for x in feed["data"]["records"]] == [rec["id"]]
        # categories reports the pinned count
        cats = {x["slug"]: x for x in
                c.get("/api/records/categories", headers=AUTH).json()["data"]["categories"]}
        assert cats["emergency"]["pinned"] == 1
        # unpin removes it from the feed, though browse still lists it
        c.post("/api/records/unpin", json={"category": "emergency", "id": rec["id"]},
               headers=STEP)
        assert c.get("/api/records?pinned=true", headers=AUTH).json()["data"]["records"] == []
        assert [x["id"] for x in
                c.get("/api/records", headers=AUTH).json()["data"]["records"]] == [rec["id"]]

    def test_delete_removes_it(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        rec = _create(c, STEP, category="notes", title="Old note").json()["data"]
        d = c.request("DELETE", "/api/records",
                      json={"category": "notes", "id": rec["id"]}, headers=STEP)
        assert d.status_code == 200 and d.json()["ok"] is True
        assert c.get("/api/records?category=notes",
                     headers=STEP).json()["data"]["records"] == []

    def test_pin_and_delete_of_unknown_record_are_honest(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        p = c.post("/api/records/pin", json={"category": "nope", "id": "missing"},
                   headers=STEP).json()
        assert p["ok"] is False and p["status"] == "not_found"
        d = c.request("DELETE", "/api/records",
                      json={"category": "nope", "id": "missing"}, headers=STEP).json()
        assert d["ok"] is False and d["status"] == "not_found"


# ── approval discipline: every write is the step-up ACT ───────────────

class TestWriteGateIsStepUp:
    def test_route_declares_step_up_dependency(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        gates = {}
        for route in c.app.routes:
            path = getattr(route, "path", "")
            if path.startswith("/api/records"):
                methods = getattr(route, "methods", set()) or set()
                deps = [d.dependency.__name__ for d in route.dependencies]
                for m in methods:
                    gates[(m, path)] = deps
        assert "require_step_up" in gates[("POST", "/api/records")]
        assert "require_step_up" in gates[("DELETE", "/api/records")]
        assert "require_step_up" in gates[("POST", "/api/records/pin")]
        assert "require_step_up" in gates[("POST", "/api/records/unpin")]
        assert "require_auth" in gates[("GET", "/api/records")]
        assert "require_step_up" not in gates[("GET", "/api/records")]

    def test_write_without_elevation_is_denied(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        _step_up_denied(monkeypatch)
        r = c.post("/api/records", json={"category": "medical", "title": "X"},
                   headers=AUTH)
        assert r.status_code == 403

    def test_unauthenticated_is_401(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        assert c.get("/api/records/categories").status_code == 401
        assert c.post("/api/records", json={}).status_code == 401


# ── locked categories: server-side step-up, never client trust ────────

class TestLockedCategories:
    def test_locked_read_denied_without_step_up(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, category="identity", title="Passport",
                fields={"number": "Z999"}, locked=True)
        _step_up_denied(monkeypatch)
        r = c.get("/api/records?category=identity", headers=AUTH)
        assert r.status_code == 409
        body = r.json()
        assert body["ok"] is False and body["status"] == "locked"
        assert "Z999" not in r.text and "Passport" not in r.text

    def test_locked_read_allowed_with_step_up(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, category="identity", title="Passport",
                fields={"number": "Z999"}, locked=True)
        r = c.get("/api/records?category=identity", headers=STEP)
        assert r.status_code == 200 and r.json()["ok"] is True
        assert r.json()["data"]["records"][0]["fields"]["number"] == "Z999"

    def test_locked_flag_persists_server_side(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, category="health", title="Notes", locked=True)
        cats = {x["slug"]: x for x in
                c.get("/api/records/categories", headers=AUTH).json()["data"]["categories"]}
        assert cats["health"]["locked"] is True
        # a second, unrelated unlocked category is unaffected
        _create(c, STEP, category="hobbies", title="Gardening")
        cats = {x["slug"]: x for x in
                c.get("/api/records/categories", headers=AUTH).json()["data"]["categories"]}
        assert cats["health"]["locked"] is True
        assert cats["hobbies"]["locked"] is False

    def test_unlock_via_a_step_up_write(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        rec = _create(c, STEP, category="papers", title="Kept", locked=True).json()["data"]
        c.post("/api/records", json={"category": "papers", "title": "Kept",
                                     "id": rec["id"], "locked": False}, headers=STEP)
        cats = {x["slug"]: x for x in
                c.get("/api/records/categories", headers=AUTH).json()["data"]["categories"]}
        assert cats["papers"]["locked"] is False

    def test_locked_pinned_record_not_in_overview(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        rec = _create(c, STEP, category="military", title="Dossier",
                      fields={"code": "delta"}, locked=True).json()["data"]
        c.post("/api/records/pin", json={"category": "military", "id": rec["id"]},
               headers=STEP)
        # neither the browse aggregate nor the pinned Overview feed may carry
        # locked content
        browse = c.get("/api/records", headers=AUTH).json()
        feed = c.get("/api/records?pinned=true", headers=AUTH).json()
        assert browse["data"]["records"] == []
        assert feed["data"]["records"] == []
        assert "delta" not in json.dumps(browse) and "delta" not in json.dumps(feed)

    def test_locked_read_unlocked_by_a_real_session_grant(self, tmp_path, monkeypatch):
        """The finish-line elevation mechanism (a session step-up grant), not
        the loopback convenience, is what unlocks a locked category."""
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, category="identity", title="Passport",
                fields={"number": "Z999"}, locked=True)
        sid = c.post("/api/auth/login", json={"token": TOKEN}).json()["data"]["session_id"]
        cookie = {"Cookie": f"pw_session={sid}"}
        _step_up_denied(monkeypatch)
        # before the grant: honest locked envelope
        assert c.get("/api/records?category=identity", headers=cookie).status_code == 409
        # mint the canonical, principal-bound, time-bounded grant
        up = c.post("/api/auth/step-up", json={"token": TOKEN}, headers=cookie)
        assert up.status_code == 200 and up.json()["data"]["has_step_up"] is True
        # after the grant: the same request now reveals the contents
        r = c.get("/api/records?category=identity", headers=cookie)
        assert r.status_code == 200
        assert r.json()["data"]["records"][0]["fields"]["number"] == "Z999"

    def test_delegated_header_alone_without_secret_is_not_trusted(self, tmp_path, monkeypatch):
        """X-PW-StepUp without a matching proxy secret is client trust: the
        locked read stays denied (fail closed)."""
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, category="identity", title="P", locked=True)
        _step_up_denied(monkeypatch)
        r = c.get("/api/records?category=identity", headers={**AUTH, "X-PW-StepUp": "1"})
        assert r.status_code == 409


# ── multi-user isolation (mirrors test_multiuser_phase23) ─────────────

class TestCrossUserIsolation:
    def test_user_a_never_sees_user_b_records(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch, mode="multi")
        prov = c.post("/api/identity/users",
                      json={"user_id": "beta", "display_name": "Beta"}, headers=STEP)
        assert prov.status_code == 200, prov.text
        tok_b = prov.json()["data"]["token"]
        b = {"Authorization": f"Bearer {tok_b}"}
        b_step = {**b, "X-PW-StepUp": "1"}

        # alpha (instance token) writes a normal + a locked record
        _create(c, STEP, category="alpha-private", title="Alpha only",
                fields={"note": "alpha-secret"}, locked=True)
        _create(c, STEP, category="alpha-open", title="Shared-name",
                fields={"note": "alpha-open"})

        # beta's own world is empty — no cross-profile leak
        assert c.get("/api/records/categories", headers=b).json()["data"]["categories"] == []
        assert c.get("/api/records", headers=b).json()["data"]["records"] == []
        # beta asking alpha's category directly sees nothing of alpha's
        got2 = c.get("/api/records?category=alpha-open", headers=b_step).json()
        assert got2["data"]["records"] == []
        assert "alpha-secret" not in json.dumps(got2)

    def test_agent_principal_is_refused(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch, mode="multi")
        r = c.post("/api/identity/agents",
                   json={"agent_id": "scribe", "scopes": ["read", "write"]}, headers=STEP)
        atok = r.json()["data"]["token"]
        bot = {"Authorization": f"Bearer {atok}", "X-PW-StepUp": "1"}
        assert c.get("/api/records/categories", headers=bot).status_code == 403
        assert c.post("/api/records",
                      json={"category": "x", "title": "y"}, headers=bot).status_code == 403


# ── honest degradation: no backing provider ───────────────────────────

class TestHonestDegradation:
    def _no_memory(self, monkeypatch):
        from personal_world.providers.registry import Registry

        real = Registry.provider_for

        def no_memory(self, capability):
            return None if capability == "memory" else real(self, capability)

        monkeypatch.setattr(Registry, "provider_for", no_memory)

    def test_no_memory_provider_is_reported_not_faked_empty(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, title="Keep me")
        self._no_memory(monkeypatch)
        cats = c.get("/api/records/categories", headers=AUTH)
        assert cats.status_code == 200
        assert cats.json()["ok"] is False
        assert cats.json()["status"] == "unavailable"
        assert cats.json()["warnings"] == ["no memory provider"]
        lst = c.get("/api/records", headers=AUTH).json()
        assert lst["ok"] is False and lst["status"] == "unavailable"

    def test_write_also_degrades_honestly_without_the_backing(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        self._no_memory(monkeypatch)
        r = c.post("/api/records", json={"category": "x", "title": "y"}, headers=STEP)
        assert r.status_code == 200
        assert r.json()["ok"] is False and r.json()["status"] == "unavailable"


# ── validation ───────────────────────────────────────────────────────

class TestValidation:
    def test_title_required_and_bounded(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        assert c.post("/api/records", json={"category": "x"},
                      headers=STEP).status_code == 422
        assert c.post("/api/records",
                      json={"category": "x", "title": "z" * 201},
                      headers=STEP).status_code == 422

    def test_category_required(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        assert c.post("/api/records", json={"title": "!!!"},
                      headers=STEP).status_code == 422

    def test_fields_must_be_scalars(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        r = c.post("/api/records", json={
            "category": "x", "title": "t", "fields": {"nested": {"a": 1}},
        }, headers=STEP)
        assert r.status_code == 422

    def test_locked_must_be_boolean(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        assert c.post("/api/records",
                      json={"category": "x", "title": "t", "locked": "yes"},
                      headers=STEP).status_code == 422

    def test_malformed_json_is_400(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        r = c.post("/api/records", content=b"not json",
                   headers={**STEP, "Content-Type": "application/json"})
        assert r.status_code == 400


# ── boundary: Records is not the Vault ────────────────────────────────

class TestRecordsAreNotVault:
    def test_records_module_does_not_import_vault(self):
        import inspect

        import personal_world.records as records_mod

        tree = ast.parse(inspect.getsource(records_mod))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(n.name for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any("vault" in name.lower() for name in imported), imported


# ── module-level store semantics (no HTTP; mirrors TestJournalCore) ───

class TestRecordsModuleStore:
    def _world(self):
        from personal_world.world import World

        return World()

    def test_upsert_update_delete_round_trip(self):
        import personal_world.records as r

        w = self._world()
        rec = r.upsert_record(w, category="Medical", title="Allergies",
                              fields={"peanut": "epi pen"})
        assert rec["category"] == "medical"  # slugified
        assert r.list_records(w, "medical")[0]["id"] == rec["id"]
        rec2 = r.upsert_record(w, category="medical", title="Allergies",
                               fields={"peanut": "watch"}, record_id=rec["id"])
        assert rec2["id"] == rec["id"]
        assert len(r.list_records(w, "medical")) == 1
        assert r.delete_record(w, "medical", rec["id"]) is True
        assert r.delete_record(w, "medical", rec["id"]) is False
        assert r.list_records(w, "medical") == []

    def test_lock_is_category_level_and_persists(self):
        import personal_world.records as r

        w = self._world()
        r.upsert_record(w, category="identity", title="License", locked=True)
        assert r.is_locked(w, "identity") is True
        assert r.get_category(w, "identity")["locked"] is True
        r.set_category_locked(w, "identity", False)
        assert r.is_locked(w, "identity") is False

    def test_pinned_records_excludes_locked_categories(self):
        import personal_world.records as r

        w = self._world()
        pub = r.upsert_record(w, category="notes", title="Groceries")
        r.set_pinned(w, "notes", pub["id"], True)
        secret = r.upsert_record(w, category="health", title="Rx", locked=True)
        r.set_pinned(w, "health", secret["id"], True)
        feed = r.pinned_records(w)
        assert [x["id"] for x in feed] == [pub["id"]]

    def test_validation_rejects_bad_input(self):
        import personal_world.records as r

        w = self._world()
        with pytest.raises(r.RecordError):
            r.upsert_record(w, category="", title="x")
        with pytest.raises(r.RecordError):
            r.upsert_record(w, category="c", title="")
        with pytest.raises(r.RecordError):
            r.upsert_record(w, category="c", title="t", fields={"k": {"bad": 1}})

    def test_category_names_and_counts_disclose_without_contents(self):
        import personal_world.records as r

        w = self._world()
        r.upsert_record(w, category="music", title="Jazz", fields={"note": "blue"})
        cats = r.list_categories(w)
        assert cats == [{
            "slug": "music", "name": "music", "locked": False, "count": 1, "pinned": 0,
        }]
        assert "blue" not in str(cats)
