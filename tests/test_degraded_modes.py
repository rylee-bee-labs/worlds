"""G-degrade matrix: honest degraded states, tested end-to-end.

Companion to ``docs/DEGRADED-MODES.md`` — every test id below is cited
by a matrix cell. The contract under test is the product-language floor
(docs/PRODUCT-LANGUAGE.md, principle 3: "warm in tone, exact in facts"):

  degraded must be HONEST — never fake-success, never blame, never a
  crash where a labeled state is promised. ``unavailable`` / ``stale`` /
  ``not_configured`` stated plainly.

Cells are proven with the app's OWN seams and fixtures (TestClient +
create_app + monkeypatched env, following test_dev_auth_bypass.py /
test_vault_fail_closed.py / test_step_up_authority.py). Unreachability
is real (a closed loopback port), not a monkeypatched lie. The
no-crypto cells patch the module flag exactly as test_vault_fail_closed
does — that flag is what a real install WITHOUT the crypto extra sets,
so this pins a genuine deployment variant, not a fiction.

Row map (see the matrix doc for full cells):
  A  brain absent (PW default)          -> TestBrainAbsent
  B  brain configured, unreachable      -> TestBrainUnreachable
  C  provider returns ok:false envelope -> TestProviderErrorEnvelope
  D  setup incomplete                   -> TestSetupIncomplete
  E  auth unconfigured                  -> TestAuthUnconfigured
  F  dev-bypass set, non-loopback peer  -> TestBypassNonLoopback
  G  journal/memory without provider    -> TestJournalMemoryWithoutProvider
  H  storage/backup boundary            -> TestStorageBackupBoundary
"""

import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world.api import create_app  # noqa: E402
from personal_world.chat_registry import ChatContract  # noqa: E402
from personal_world.envelope import Result, fail, ok  # noqa: E402

TOKEN = "degraded-matrix-token-1"  # pw-safety: synthetic


def _client(tmp_path, monkeypatch, *, token: str | None = TOKEN, bypass: bool = False):
    """The established env-driven fixture (test_dev_auth_bypass idiom):
    data dir == config dir == tmp_path, env strictly controlled."""
    monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
    monkeypatch.delenv("PW_API_TOKEN", raising=False)
    monkeypatch.delenv("FORCE_SETUP", raising=False)
    monkeypatch.delenv("PW_IDENTITY_MODE", raising=False)
    if token:
        monkeypatch.setenv("PW_API_TOKEN", token)
    if bypass:
        monkeypatch.setenv("PW_DEV_AUTH_BYPASS", "1")
    return TestClient(create_app(tmp_path, tmp_path))


def _auth(token: str = TOKEN):
    return {"Authorization": f"Bearer {token}"}


# ── real-unreachability helpers (no monkeypatched network lies) ──────


def _closed_brain_url() -> str:
    """A loopback URL whose port is almost certainly closed: bind a
    socket to get a port the OS just handed out, release it, point the
    provider at it. urlopen there gets an honest ConnectionRefusedError
    — the same failure a stopped Ollama produces."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"http://127.0.0.1:{port}"


def _configure_brain(tmp_path, base_url: str):
    """Write a connections.json the app itself reads at build time —
    the exact path a real operator's config takes."""
    (tmp_path / "connections.json").write_text(
        json.dumps(
            {
                "connections": [
                    {
                        "type": "ollama",
                        "name": "lab-brain",
                        "capability": "reasoning",
                        "base_url": base_url,
                        "model": "test-brain",
                    }
                ]
            }
        )
    )


class _NonLoopbackPeer:
    """ASGI wrapper that rewrites the transport peer address. This is
    the real client-field the app reads — honest simulation of a LAN
    peer, the same mechanism test_dev_auth_bypass pins at unit level
    via _is_true_loopback, taken to the whole request path here."""

    def __init__(self, inner, host: str):
        self.inner = inner
        self.host = host

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope = dict(scope)
            scope["client"] = (self.host, 55555)
        await self.inner(scope, receive, send)


class RejectBrain(ChatContract):
    """Alive and reachable, but refuses the request — exactly what a
    real provider returns on a bad/expired key (401-class). Returns the
    provider-shaped ok:false envelope the core must pass through."""

    display_name = "Rejecting Brain"

    def observe(self) -> Result:
        return ok("healthy", data={"endpoint": "reachable"})

    def chat(self, messages):
        return fail(
            "unauthorized",
            warnings=["provider rejected the request: api key not valid"],
        )


class HealthyBrain(ChatContract):
    """Cooperative provider for the storage-boundary cell (H3)."""

    display_name = "Healthy Brain"

    def observe(self) -> Result:
        return ok("healthy", data={"endpoint": "reachable"})

    def chat(self, messages):
        return ok("healthy", data={"reply": "the world is quiet today", "model": "fake"})


def _make_registry_patcher(provider):
    """Register a ChatContract impl under `reasoning` using the real
    registry seam (test_chat.py's patched-build_registry idiom)."""
    import personal_world.api as api_mod

    real = api_mod.build_registry

    def patched(world, registry, config_dir, **kwargs):
        reg = real(world, registry, config_dir, **kwargs)
        reg.register(
            "reasoning",
            "matrix-brain",
            provider,
            health_check=lambda: True,
            writes="none",
        )
        return reg

    return patched


def _client_with(monkeypatch, tmp_path, provider):
    """The standard client with one reasoning provider wired in."""
    import personal_world.api as api_mod

    monkeypatch.setattr(api_mod, "build_registry", _make_registry_patcher(provider))
    return _client(tmp_path, monkeypatch)


# ════════════════ A — brain absent (PW default) ══════════════════════


class TestBrainAbsent:
    """State (a): zero providers configured — the shipped default."""

    def test_a1_chat_reports_not_configured(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        r = c.post("/api/chat", json={"message": "hi"}, headers=_auth())
        assert r.status_code == 200  # degraded envelope, not an error
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "not_configured"
        assert "reply" not in (body.get("data") or {})  # never a fake answer

    def test_a2_chat_test_reports_not_configured(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        r = c.post("/api/chat/test", headers=_auth())
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "not_configured"

    def test_a3_chat_providers_active_is_none(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        r = c.get("/api/chat/providers", headers=_auth())
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["active"] is None
        assert data["providers"] == []

    def test_a4_grid_marks_reasoning_not_configured(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        caps = c.get("/api/status", headers=_auth()).json()["data"]["capabilities"]
        assert caps["reasoning"]["ok"] is False
        assert caps["reasoning"]["status"] == "not_configured"

    def test_a5_core_fully_works_without_any_brain(self, tmp_path, monkeypatch):
        """The contract: memory/journal/status/daily open instantly with
        every model off — AI absence degrades enrichment, not the core."""
        c = _client(tmp_path, monkeypatch)
        assert c.get("/api/status", headers=_auth()).status_code == 200
        daily = c.get("/api/daily", headers=_auth())
        assert daily.status_code == 200
        body = daily.json()
        assert body["ok"] is True
        # a vacancy is not an alert: not_configured never lands in attention
        assert not [a for a in body["data"]["attention"] if a.startswith("reasoning")]
        w = c.post("/api/journal", json={"text": "no brain today"}, headers=_auth())
        assert w.status_code == 200
        assert c.get("/api/sections", headers=_auth()).status_code == 200


# ════════════ B — brain configured, provider unreachable ═════════════


class TestBrainUnreachable:
    """State (b): a real connection to a model endpoint that is down."""

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        _configure_brain(tmp_path, _closed_brain_url())
        return _client(tmp_path, monkeypatch)

    def test_b1_overview_says_reasoning_unavailable(self, client):
        body = client.get("/api/daily", headers=_auth()).json()
        assert body["ok"] is True  # a down brain never breaks Overview itself
        reasoning = body["data"]["capabilities"]["reasoning"]
        assert reasoning["ok"] is False
        assert reasoning["status"] == "unavailable"
        # the honest attention line the Overview renders
        assert "reasoning: unavailable" in body["data"]["attention"]

    def test_b2_chat_says_unavailable_not_fake(self, client):
        r = client.post("/api/chat", json={"message": "hi"}, headers=_auth())
        assert r.status_code == 200  # labeled degraded state, not a 5xx crash
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "unavailable"
        assert "reply" not in (body.get("data") or {})

    def test_b3_provider_list_shows_the_truth(self, client):
        data = client.get("/api/chat/providers", headers=_auth()).json()["data"]
        assert len(data["providers"]) == 1
        entry = data["providers"][0]
        assert entry["name"] == "lab-brain"
        assert entry["ok"] is False
        assert entry["status"] in ("unavailable", "unhealthy")

    def test_b4_status_grid_and_core_stay_healthy(self, client):
        s = client.get("/api/status", headers=_auth())
        assert s.status_code == 200
        caps = s.json()["data"]["capabilities"]
        assert caps["reasoning"]["status"] == "unavailable"
        assert client.get("/healthz").json()["ok"] is True


# ═══════════ C — provider alive, returns ok:false envelope ═══════════


class TestProviderErrorEnvelope:
    """State (c): reachable provider that refuses (bad key, quota, 4xx)."""

    def test_c1_provider_status_flows_through_unchanged(self, tmp_path, monkeypatch):
        c = _client_with(monkeypatch, tmp_path, RejectBrain())
        r = c.post("/api/chat", json={"message": "hi"}, headers=_auth())
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        # the provider's OWN label passes through — no rewriting into
        # healthy, no laundering into a generic "sorry, try later"
        assert body["status"] == "unauthorized"
        assert any("api key" in w for w in body["warnings"])
        assert "reply" not in (body.get("data") or {})

    def test_c2_reply_survives_when_provider_succeeds(self, tmp_path, monkeypatch):
        """Control cell: the same harness with an ok:true provider
        DOES return a reply — proving c1's absence is honesty, not
        always-empty plumbing."""
        c = _client_with(monkeypatch, tmp_path, HealthyBrain())
        r = c.post("/api/chat", json={"message": "hi"}, headers=_auth())
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["reply"] == "the world is quiet today"


# ════════════════════ D — setup incomplete ═══════════════════════════


class TestSetupIncomplete:
    """State (d): no data/setup-complete marker (fresh install)."""

    def test_d1_visible_in_healthz_and_status(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch, token=None)
        assert not (tmp_path / "setup-complete").exists()
        hz = c.get("/healthz").json()
        assert hz["setup_needed"] is True
        ss = c.get("/api/setup/status").json()
        assert ss["data"]["complete"] is False

    def test_d2_root_lands_on_the_wizard(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch, token=None)
        r = c.get("/", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/setup"
        w = c.get("/setup")
        assert w.status_code == 200
        assert "text/html" in w.headers["content-type"]

    def test_d3_incomplete_setup_never_opens_the_api(self, tmp_path, monkeypatch):
        """Setup state and auth are separate axes; neither leaks."""
        c = _client(tmp_path, monkeypatch, token=None)
        assert c.get("/api/status", headers={}).status_code == 503

    def test_d4_marker_is_the_only_switch(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch)
        assert c.get("/healthz").json()["setup_needed"] is True
        (tmp_path / "setup-complete").write_text("ok")
        assert c.get("/healthz").json()["setup_needed"] is False
        assert c.get("/api/setup/status").json()["data"]["complete"] is True


# ════════════════════ E — auth unconfigured ══════════════════════════


class TestAuthUnconfigured:
    """State (e): no token in env, no data/.env — nothing to auth with."""

    def test_e1_protected_routes_fail_closed_503(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch, token=None)
        for path in ("/api/status", "/api/daily", "/api/sections", "/api/journal"):
            r = c.get(path)
            assert r.status_code == 503, path
            assert r.json()["detail"] == "auth not configured", path

    def test_e2_healthz_admits_auth_unconfigured(self, tmp_path, monkeypatch):
        c = _client(tmp_path, monkeypatch, token=None)
        hz = c.get("/healthz")
        assert hz.status_code == 200  # the one public diagnostic stays up
        assert hz.json()["auth_configured"] is False

    def test_e3_bearer_without_any_store_still_fails_closed(
        self, tmp_path, monkeypatch
    ):
        """A presented token with no credential store 503s — the gate
        never falls through silently toward a pass."""
        c = _client(tmp_path, monkeypatch, token=None)
        r = c.get("/api/status", headers=_auth("someone-elses-token"))
        assert r.status_code == 503

    def test_e4_first_run_path_stays_reachable(self, tmp_path, monkeypatch):
        """Recovery guarantee: with zero auth AND zero setup, the
        deterministic first-run path (wizard) is open — there is always
        a door that does not need a credential you do not have."""
        c = _client(tmp_path, monkeypatch, token=None)
        assert c.get("/setup").status_code == 200


# ═══════════════ F — dev-bypass set, non-loopback request ════════════


class TestBypassNonLoopback:
    """State (f): PW_DEV_AUTH_BYPASS=1 but the peer is a LAN address.
    The bypass is a loopback exception; from elsewhere it is as if it
    did not exist."""

    LAN = "203.0.113.9"  # pw-safety: synthetic TEST-NET peer

    def test_f1_no_token_lan_peer_fails_closed(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PW_IDENTITY_MODE", raising=False)
        monkeypatch.delenv("FORCE_SETUP", raising=False)
        app = create_app(tmp_path, tmp_path)
        monkeypatch.setenv("PW_DEV_AUTH_BYPASS", "1")
        monkeypatch.delenv("PW_API_TOKEN", raising=False)
        c = TestClient(_NonLoopbackPeer(app, self.LAN))
        assert c.get("/api/status").status_code == 503  # bypass not granted
        # contrast through the same app object: loopback peer IS granted
        loop = TestClient(app)
        assert loop.get("/api/status").status_code == 200

    def test_f2_bearer_gate_unchanged_from_lan_peer(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PW_DEV_AUTH_BYPASS", "1")
        monkeypatch.setenv("PW_API_TOKEN", TOKEN)
        monkeypatch.delenv("PW_IDENTITY_MODE", raising=False)
        app = create_app(tmp_path, tmp_path)
        c = TestClient(_NonLoopbackPeer(app, self.LAN))
        assert c.get("/api/status").status_code == 401  # nothing presented
        assert (
            c.get("/api/status", headers=_auth("wrong-" + TOKEN)).status_code == 401
        )
        assert c.get("/api/status", headers=_auth()).status_code == 200

    def test_f3_bypass_grants_no_step_up_from_lan(self, tmp_path, monkeypatch):
        """Even a CORRECT credential from a LAN peer gets auth but not
        step-up: the bypass is not a remote write door."""
        monkeypatch.setenv("PW_DEV_AUTH_BYPASS", "1")
        monkeypatch.setenv("PW_API_TOKEN", TOKEN)
        monkeypatch.delenv("PW_IDENTITY_MODE", raising=False)
        app = create_app(tmp_path, tmp_path)
        c = TestClient(_NonLoopbackPeer(app, self.LAN))
        r = c.post(
            "/api/world/intent", json={"key": "k", "value": "v"}, headers=_auth()
        )
        assert r.status_code == 403
        assert "step-up" in r.json()["detail"]

    def test_f4_setup_mint_endpoint_is_loopback_only(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PW_API_TOKEN", raising=False)
        monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
        app = create_app(tmp_path, tmp_path)
        c = TestClient(_NonLoopbackPeer(app, self.LAN))
        r = c.post("/api/setup", json={"token": "overthrow-attempt-1"})  # pw-safety: synthetic
        assert r.status_code == 403
        assert not (tmp_path / "setup-complete").exists()  # nothing minted

    def test_f5_healthz_still_admits_bypass_is_on(self, tmp_path, monkeypatch):
        """Visibility: the flag is truthy from any vantage; the app
        never hides the risky state from a LAN observer."""
        monkeypatch.setenv("PW_DEV_AUTH_BYPASS", "1")
        monkeypatch.delenv("PW_API_TOKEN", raising=False)
        app = create_app(tmp_path, tmp_path)
        c = TestClient(_NonLoopbackPeer(app, self.LAN))
        assert c.get("/healthz").json()["dev_bypass"] is True


# ═══════════════ G — journal/memory capability, no provider ══════════


class TestJournalMemoryWithoutProvider:
    """State (g): no EXTERNAL (AI) provider configured. The repo's
    truth: journal and memory both carry native baselines — memory is
    SQLite FTS5 over the journal, no model required. "Chat is a
    shortcut, never the only door" is enforced HERE, not by an
    ``unavailable`` label: the deterministic path must be fully live."""

    def test_g1_memory_search_finds_journal_note_with_zero_providers(
        self, tmp_path, monkeypatch
    ):
        """End-to-end deterministic memory: write a plain journal note,
        then semantic-looking search finds it — no model, no external
        provider, no connection of any kind configured."""
        c = _client(tmp_path, monkeypatch)
        w = c.post("/api/journal", json={"text": "violet kettle repair"}, headers=_auth())
        assert w.status_code == 200
        r = c.get(
            "/api/memory/search", params={"q": "violet"}, headers=_auth()
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["status"] == "healthy"
        texts = [hit["text"] for hit in body["data"]["results"]]
        assert any("violet kettle repair" in t for t in texts)

    def test_g2_grid_shows_memory_served_by_native_baseline(self, tmp_path, monkeypatch):
        """The capability grid states which slot is genuinely vacant
        (reasoning: not_configured) versus served natively (memory:
        healthy) — no provider is claimed for what isn't, and what
        works is not flatteringly called unavailable."""
        c = _client(tmp_path, monkeypatch)
        caps = c.get("/api/status", headers=_auth()).json()["data"]["capabilities"]
        assert caps["memory"]["ok"] is True
        assert caps["memory"]["status"] == "healthy"
        assert caps["reasoning"]["status"] == "not_configured"

    def test_g3_journal_works_with_zero_providers(self, tmp_path, monkeypatch):
        """Chat is a shortcut, never the only door: the deterministic
        journal path (write → read → audit) functions with nothing
        configured at all."""
        c = _client(tmp_path, monkeypatch)
        w = c.post("/api/journal", json={"text": "quiet entry"}, headers=_auth())
        assert w.status_code == 200
        events = c.get("/api/journal", params={"n": 5}, headers=_auth()).json()["data"]
        assert any(e["summary"] == "quiet entry" for e in events)
        audit = c.get("/api/journal/audit", headers=_auth())
        assert audit.status_code == 200
        assert "quiet entry" in audit.json()["data"]["text"]


# ═══════════════════ H — storage/backup boundary ═════════════════════


class TestStorageBackupBoundary:
    """State (h): the security/storage edge. The no-crypto cells set
    the module flag a cryptography-less install really has (same idiom
    as test_vault_fail_closed.TestVaultFailClosed). Literal ENOSPC is
    not producible here — see the matrix, cell h-4."""

    def test_h1_vault_reports_no_crypto_honestly(self, tmp_path, monkeypatch):
        import personal_world.vault as vault_mod

        c = _client(tmp_path, monkeypatch)
        monkeypatch.setattr(vault_mod, "_HAS_CRYPTO", False)
        r = c.post("/api/vault/unlock", json={"passphrase": "pw"}, headers=_auth())
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "unavailable"
        st = c.get("/api/vault/status", headers=_auth()).json()["data"]
        assert st["locked"] is True
        assert st["encrypted"] is False  # never claims encryption it lacks

    def test_h2_worlds_backup_fails_closed_without_crypto(self, tmp_path, monkeypatch):
        import personal_world.worlds_backup as wb_mod

        (tmp_path / "world.json").write_text("{}")
        c = _client(tmp_path, monkeypatch)
        monkeypatch.setattr(wb_mod, "_HAS_CRYPTO", False)
        r = c.post(
            "/api/worlds/backup",
            json={"passphrase": "matrix-passphrase-1", "include_vault": False},
            headers=_auth(),
        )
        # the route's labeled mapping: unavailable -> 503, never a
        # half-written archive and never a 200
        assert r.status_code == 503
        assert any("unavailable" in str(w).lower() for w in r.json()["detail"])

    def test_h3_unwritable_transcript_never_swallows_the_reply(
        self, tmp_path, monkeypatch
    ):
        """Storage-bound promise in api.py: transcript writes are
        best-effort — a failure must never eat the visible reply.
        Honest EROFS-class failure: the transcript path is occupied by
        a directory, so the real open() raises a real OSError (a
        read-only-mount stand-in; see matrix h-4 for why it is a
        stand-in)."""
        c = _client_with(monkeypatch, tmp_path, HealthyBrain())
        (tmp_path / "chat-history.ndjson").mkdir()  # IsADirectoryError on append
        r = c.post("/api/chat", json={"message": "hi"}, headers=_auth())
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["reply"] == "the world is quiet today"
        # ...while the failure is visible in logs, not silenced:
        # (handler logs "chat history append failed" — asserted via
        # caplog below)

    def test_h3b_transcript_failure_is_logged_not_hidden(
        self, tmp_path, monkeypatch, caplog
    ):
        import logging

        c = _client_with(monkeypatch, tmp_path, HealthyBrain())
        (tmp_path / "chat-history.ndjson").mkdir()
        with caplog.at_level(logging.WARNING, logger="personal_world.api"):
            r = c.post("/api/chat", json={"message": "hi"}, headers=_auth())
        assert r.status_code == 200
        assert any("chat history append failed" in rec.message for rec in caplog.records)

    def test_h4_corrupt_search_index_says_unavailable_not_crash(self, tmp_path, monkeypatch):
        """A genuinely damaged storage artifact: the disposable FTS5
        index file is garbage bytes (an honest on-disk condition — no
        monkeypatch lies). Memory search must report ``unavailable``
        plainly, and the canonical truth (the journal) must survive
        untouched: 'Markdown/files remain canonical truth; the index is
        rebuildable and disposable.'"""
        c = _client(tmp_path, monkeypatch)
        assert c.post(
            "/api/journal", json={"text": "durable canonical fact"}, headers=_auth()
        ).status_code == 200
        (tmp_path / "memory.fts5.db").write_bytes(b"not a database at all")
        r = c.get("/api/memory/search", params={"q": "durable"}, headers=_auth())
        assert r.status_code == 200  # labeled degraded state, not a 5xx
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "unavailable"
        # the capability grid carries the same honest label
        caps = c.get("/api/status", headers=_auth()).json()["data"]["capabilities"]
        assert caps["memory"]["ok"] is False
        assert caps["memory"]["status"] == "unavailable"
        # canonical data is untouched — the journal still reads back
        events = c.get("/api/journal", params={"n": 5}, headers=_auth()).json()["data"]
        assert any(e["summary"] == "durable canonical fact" for e in events)
