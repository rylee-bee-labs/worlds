"""G-memory — the TRUE-NORTH recut alpha gate, backend half (Wave 1 Lane C).

Gate text (docs/TRUE-NORTH.md, owner-approved 2026-09-22):
    "pin + find a record with all models off; layout stable; locked
    categories need step-up"

Proven here, against a REAL app booted with zero providers configured
(the init_world default — no chat/reasoning model, no enrichment):

- the environment genuinely has every model off (chat answers
  ``not_configured``, never a hidden dependency)
- PIN + FIND: create → pin → find by title / field / category through
  ``GET /api/records?q=`` — the deterministic lexical door
  (records.search_records: substring AND-match, no index, no provider,
  no embeddings), byte-identical answers on repeat calls
- the journal half of Memory also finds with models off (the native
  SQLite FTS5 memory index)
- locked categories FAIL CLOSED against search: contents never leak
  into ``q`` results without a server-verified step-up, the locked
  category read stays a hard 409, writes stay 403 — and a real session
  grant (the canonical mechanism) is what opens the door
- ``GET /api/journal/last`` — the read-only deep-link contract for the
  daily home loop's "Resume — yesterday's thread" beat: honest null on
  an empty journal, always equal to the GET /api/journal calm-view tail
  (superseded originals never resurface), caller-scoped in multi mode,
  person-only, and strictly read-only on disk

Fixtures mirror tests/test_records.py (same lane) idioms exactly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

TOKEN = "instancetoken"  # pw-safety: synthetic
AUTH = {"Authorization": f"Bearer {TOKEN}"}
# The loopback dev peer (TestClient) is accepted by _step_up_authorized, so
# the header is belt-and-braces — the same idiom test_records.py uses.
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
    through a real session grant — the red-path idiom from test_records.py."""
    import personal_world.api as api_mod

    monkeypatch.setattr(api_mod, "_is_true_loopback", lambda request: False)


def _create(c, headers, *, title, category=None, fields=None, **extra):
    body = {
        "category": category or title,
        "title": title,
        "fields": {"penicillin": "hives"} if fields is None else fields,
    }
    body.update(extra)
    return c.post("/api/records", json=body, headers=headers)


def _no_memory(monkeypatch):
    from personal_world.providers.registry import Registry

    real = Registry.provider_for

    def no_memory(self, capability):
        return None if capability == "memory" else real(self, capability)

    monkeypatch.setattr(Registry, "provider_for", no_memory)


# ── the environment IS models-off (never a hidden dependency) ─────────

class TestEveryModelIsOff:
    def test_chat_reports_not_configured_in_this_environment(self, tmp_path, monkeypatch):
        """Proof the gate runs with all models off: zero providers are
        configured (init_world default), so the reasoning capability
        honestly answers not_configured — nothing below rides a model."""
        c = _client(tmp_path, monkeypatch)
        r = c.post("/api/chat", json={"message": "hello"}, headers=AUTH)
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "not_configured"

    def test_journal_find_is_the_native_fts_index_not_a_model(self, tmp_path, monkeypatch):
        """The journal half of Memory's find door: the native SQLite FTS5
        index answers with every model off, deterministically."""
        c = _client(tmp_path, monkeypatch)
        assert c.post("/api/journal", json={"text": "Fixed the trellis wiring"},
                      headers=AUTH).status_code == 200
        r1 = c.get("/api/memory/search", params={"q": "trellis"}, headers=AUTH)
        r2 = c.get("/api/memory/search", params={"q": "trellis"}, headers=AUTH)
        assert r1.json()["ok"] is True
        hits = r1.json()["data"]["results"]
        assert any("trellis" in h["text"] for h in hits)
        # deterministic: same query, same world → byte-identical answer
        assert r1.text == r2.text


# ── G-memory: PIN + FIND with all models off ──────────────────────────

class TestPinAndFindModelsOff:
    def test_pin_then_find_by_title(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        rec = _create(c, STEP, category="Medical", title="Allergy list").json()["data"]
        pin = c.post("/api/records/pin",
                     json={"category": "medical", "id": rec["id"]}, headers=STEP)
        assert pin.status_code == 200 and pin.json()["ok"] is True

        found = c.get("/api/records", params={"q": "allergy"}, headers=AUTH)
        assert found.status_code == 200
        body = found.json()
        assert body["ok"] is True
        assert body["data"]["query"] == "allergy"
        assert [r["id"] for r in body["data"]["records"]] == [rec["id"]]
        assert body["data"]["records"][0]["pinned"] is True

    def test_find_is_deterministic_repeat_calls_identical(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, category="Medical", title="Allergy list")
        r1 = c.get("/api/records", params={"q": "allergy"}, headers=AUTH)
        r2 = c.get("/api/records", params={"q": "allergy"}, headers=AUTH)
        assert r1.text == r2.text

    def test_find_matches_field_keys_values_and_category_names(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        rec = _create(c, STEP, category="Medical", title="Allergy list",
                      fields={"penicillin": "hives"}).json()["data"]
        for term in ("penicillin", "hives", "medical"):
            body = c.get("/api/records", params={"q": term}, headers=AUTH).json()
            assert [r["id"] for r in body["data"]["records"]] == [rec["id"]], term

    def test_find_is_case_insensitive_and_terms_are_and_matched(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        rec = _create(c, STEP, category="Medical", title="Allergy list",
                      fields={"penicillin": "hives"}).json()["data"]
        hit = c.get("/api/records", params={"q": "  ALLERGY   Hives "}, headers=AUTH).json()
        assert [r["id"] for r in hit["data"]["records"]] == [rec["id"]]
        miss = c.get("/api/records", params={"q": "allergy zzz"}, headers=AUTH).json()
        # honest zero — ok:true with an empty list, never an error, never a pad
        assert miss["ok"] is True and miss["data"]["records"] == []

    def test_blank_q_is_the_plain_browse_view(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, category="Medical", title="Allergy list")
        a = c.get("/api/records", params={"q": "   "}, headers=AUTH).json()
        b = c.get("/api/records", headers=AUTH).json()
        assert a["data"]["records"] == b["data"]["records"]
        assert "query" not in a["data"]

    def test_pinned_filter_combines_with_find(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        pinned = _create(c, STEP, category="Medical", title="Allergy list").json()["data"]
        _create(c, STEP, category="Medical", title="Allergy appointment notes",
                fields={"when": "March"})
        c.post("/api/records/pin",
               json={"category": "medical", "id": pinned["id"]}, headers=STEP)
        body = c.get("/api/records",
                     params={"q": "allergy", "pinned": "true"}, headers=AUTH).json()
        assert [r["id"] for r in body["data"]["records"]] == [pinned["id"]]

    def test_find_inside_one_category(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        inside = _create(c, STEP, category="Medical", title="Allergy list").json()["data"]
        _create(c, STEP, category="Work history", title="Allergy clinic internship")
        body = c.get("/api/records",
                     params={"category": "medical", "q": "allergy"}, headers=AUTH).json()
        assert body["data"]["category"] == "medical"
        assert [r["id"] for r in body["data"]["records"]] == [inside["id"]]

    def test_find_degrades_honestly_without_the_memory_backing(self, tmp_path, monkeypatch):
        """No backing provider → the server's own unavailable envelope,
        never a fake-empty success (capability-grid truth)."""
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, category="Medical", title="Allergy list")
        _no_memory(monkeypatch)
        body = c.get("/api/records", params={"q": "allergy"}, headers=AUTH).json()
        assert body["ok"] is False
        assert body["status"] == "unavailable"
        assert body["warnings"] == ["no memory provider"]


# ── locked categories: step-up or nothing (fail closed) ───────────────

class TestLockedCategoriesFailClosedAgainstFind:
    def test_locked_contents_never_leak_into_find(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, category="Identity documents", title="Passport",
                fields={"number": "Z999"}, locked=True)
        _step_up_denied(monkeypatch)
        for term in ("passport", "z999", "identity"):
            r = c.get("/api/records", params={"q": term}, headers=AUTH)
            assert r.status_code == 200
            assert r.json()["data"]["records"] == []
            assert "Z999" not in r.text and "Passport" not in r.text

    def test_locked_category_read_with_q_is_still_the_hard_409(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, category="Identity documents", title="Passport", locked=True)
        _step_up_denied(monkeypatch)
        r = c.get("/api/records",
                  params={"category": "identity-documents", "q": "passport"},
                  headers=AUTH)
        assert r.status_code == 409
        assert r.json()["status"] == "locked"

    def test_find_includes_locked_only_after_a_real_session_grant(self, tmp_path, monkeypatch):
        """The canonical elevation mechanism (a session step-up grant) — not
        the loopback convenience — is what opens locked contents to find."""
        c = _client(tmp_path, monkeypatch)
        rec = _create(c, STEP, category="Identity documents", title="Passport",
                      fields={"number": "Z999"}, locked=True).json()["data"]
        sid = c.post("/api/auth/login", json={"token": TOKEN}).json()["data"]["session_id"]
        cookie = {"Cookie": f"pw_session={sid}"}
        _step_up_denied(monkeypatch)
        # before the grant: the honest zero, contents withheld
        assert c.get("/api/records", params={"q": "passport"},
                     headers=cookie).json()["data"]["records"] == []
        # mint the principal-bound, time-bounded grant
        up = c.post("/api/auth/step-up", json={"token": TOKEN}, headers=cookie)
        assert up.status_code == 200 and up.json()["data"]["has_step_up"] is True
        # after the grant: the same find now reveals the record
        body = c.get("/api/records", params={"q": "passport"}, headers=cookie).json()
        assert [r["id"] for r in body["data"]["records"]] == [rec["id"]]

    def test_a_wrong_credential_does_not_open_find(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        _create(c, STEP, category="Identity documents", title="Passport", locked=True)
        sid = c.post("/api/auth/login", json={"token": TOKEN}).json()["data"]["session_id"]
        cookie = {"Cookie": f"pw_session={sid}"}
        _step_up_denied(monkeypatch)
        bad = c.post("/api/auth/step-up", json={"token": "wrong"}, headers=cookie)
        assert bad.status_code == 403
        assert c.get("/api/records", params={"q": "passport"},
                     headers=cookie).json()["data"]["records"] == []

    def test_writes_and_pins_stay_denied_without_step_up(self, tmp_path, monkeypatch):
        """The step-up denial half of the gate: with the loopback exception
        off and no grant, every Records write is refused — nothing is
        written, pinned, or deleted."""
        c = _client(tmp_path, monkeypatch)
        rec = _create(c, STEP, category="Medical", title="Allergy list").json()["data"]
        _step_up_denied(monkeypatch)
        assert c.post("/api/records", json={"category": "Medical", "title": "Smuggled"},
                      headers=AUTH).status_code == 403
        assert c.post("/api/records/pin",
                      json={"category": "medical", "id": rec["id"]},
                      headers=AUTH).status_code == 403
        assert c.request("DELETE", "/api/records",
                         json={"category": "medical", "id": rec["id"]},
                         headers=AUTH).status_code == 403
        # and the refused pin really did not apply
        body = c.get("/api/records", params={"q": "allergy"}, headers=STEP).json()
        assert body["data"]["records"][0]["pinned"] is False

    def test_agent_principal_is_refused_by_find(self, tmp_path, monkeypatch):
        """Records are person-only; an agent token never reaches the door —
        administrative capability does not imply routine access."""
        c = _client(tmp_path, monkeypatch, mode="multi")
        r = c.post("/api/identity/agents",
                   json={"agent_id": "scribe", "scopes": ["read", "write"]}, headers=STEP)
        bot = {"Authorization": f"Bearer {r.json()['data']['token']}"}
        assert c.get("/api/records", params={"q": "anything"},
                     headers=bot).status_code == 403


# ── the "Resume — yesterday's thread" deep-link contract ──────────────

class TestJournalLastDeepLink:
    def test_empty_journal_answers_an_honest_null(self, tmp_path, monkeypatch):
        c, _ = _app(tmp_path, monkeypatch)
        listing = c.get("/api/journal", headers=AUTH).json()["data"]
        r = c.get("/api/journal/last", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True and body["status"] == "healthy"
        if listing == []:
            assert body["data"]["entry"] is None
        else:
            # boot wrote something (single shared journal): last agrees
            # with the list's newest CURRENT entry, never a fabrication
            assert body["data"]["entry"]["ts"] == max(e["ts"] for e in listing)

    def test_last_is_the_most_recent_entry(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        c.post("/api/journal", json={"text": "first thought"}, headers=AUTH)
        c.post("/api/journal", json={"text": "second thought"}, headers=AUTH)
        entry = c.get("/api/journal/last", headers=AUTH).json()["data"]["entry"]
        assert entry["summary"] == "second thought"

    def test_last_agrees_with_the_calm_view_tail_after_a_correction(self, tmp_path, monkeypatch):
        """After a supersede the endpoint must not disagree with the list:
        whatever GET /api/journal shows as its newest CURRENT entry IS the
        last entry (the supersede ACT appends the correction and then its
        APPROVAL audit line — both are real journal entries, and the
        deep-link contract is the calm-view tail, never a second notion of
        "last"). The superseded original never resurfaces."""
        c = _client(tmp_path, monkeypatch)
        c.post("/api/journal", json={"text": "first thought"}, headers=AUTH)
        second = c.post("/api/journal", json={"text": "second thought"}, headers=AUTH)
        assert second.status_code == 200
        listing = c.get("/api/journal", headers=AUTH).json()["data"]
        second_ts = [e for e in listing if e["summary"] == "second thought"][-1]["ts"]
        sup = c.post("/api/journal/supersede",
                     json={"supersedes": second_ts, "text": "corrected thought",
                           "reason": "misremembered"}, headers=STEP)
        assert sup.status_code == 200, sup.text

        entry = c.get("/api/journal/last", headers=AUTH).json()["data"]["entry"]
        listing = c.get("/api/journal", headers=AUTH).json()["data"]
        # one calm view, one tail — the deep link can never contradict Memory
        assert entry == listing[-1]
        summaries = [e["summary"] for e in listing]
        assert "corrected thought" in summaries
        # the superseded original is filtered out of the current view…
        assert "second thought" not in summaries
        # …and the correction carries the chain link itself
        corrected = [e for e in listing if e["summary"] == "corrected thought"][0]
        assert corrected["supersedes"] == second_ts

    def test_last_is_strictly_read_only(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        c.post("/api/journal", json={"text": "a thought"}, headers=AUTH)
        journal_file = Path(tmp_path) / "journal.ndjson"
        before = journal_file.read_bytes()
        c.get("/api/journal/last", headers=AUTH)
        c.get("/api/journal/last", headers=AUTH)
        assert journal_file.read_bytes() == before

    def test_last_is_caller_scoped_in_multi_mode(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch, mode="multi")
        prov = c.post("/api/identity/users",
                      json={"user_id": "beta", "display_name": "Beta"}, headers=STEP)
        tok_b = prov.json()["data"]["token"]
        beta = {"Authorization": f"Bearer {tok_b}"}
        c.post("/api/journal", json={"text": "alpha's private thread"}, headers=AUTH)
        # beta's own journal is empty — an honest null, never alpha's entry
        assert c.get("/api/journal/last", headers=beta).json()["data"]["entry"] is None
        assert c.get("/api/journal/last",
                     headers=AUTH).json()["data"]["entry"]["summary"] == "alpha's private thread"

    def test_last_is_person_only(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch, mode="multi")
        r = c.post("/api/identity/agents",
                   json={"agent_id": "scribe", "scopes": ["read", "write"]}, headers=STEP)
        bot = {"Authorization": f"Bearer {r.json()['data']['token']}"}
        assert c.get("/api/journal/last", headers=bot).status_code == 403

    def test_last_requires_auth(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        assert c.get("/api/journal/last").status_code == 401
