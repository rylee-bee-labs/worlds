"""Identity boundary (product decision #13): per-user state partitioning.

Proves the multi-user data boundary on the single path-resolution seam
(``identity.principal_scoped_path``):

- single mode — the default — maps EVERY kind to the legacy instance
  paths, so a current install keeps reading its own data (no silent
  migration loss)
- multi mode scopes world/journal/reminders/proposals/chat-history/
  interests into ``data/users/<id>/`` per person (agents via owner)
- two distinct principals cannot read (or delete) each other's
  journal / reminders / proposals / prefs / chat history / interests
- unsafe principal ids fail closed (no path traversal)
"""

import json
import sys
from pathlib import Path

import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from personal_world.identity import (  # noqa: E402
    SCOPED_PATH_FILENAMES,
    Principal,
    principal_scoped_path,
)

# ── unit: the single path-resolution seam ──────────────────────────────


class TestPrincipalScopedPath:
    def test_single_mode_maps_every_kind_to_legacy(self, tmp_path):
        p = Principal(id="primary")
        for kind, filename in SCOPED_PATH_FILENAMES.items():
            assert principal_scoped_path(tmp_path, p, kind) == tmp_path / filename
            assert (
                principal_scoped_path(tmp_path, p, kind, mode="single")
                == tmp_path / filename
            )

    def test_single_mode_maps_any_principal_to_legacy(self, tmp_path):
        # the single-user default has exactly one person; nothing ever
        # resolves into a user tree in single mode
        p = Principal(id="beta")
        assert (
            principal_scoped_path(tmp_path, p, "reminders", mode="single")
            == tmp_path / "reminders.json"
        )

    def test_no_principal_maps_to_legacy(self, tmp_path):
        # background seams (scheduler tick with no request) stay global
        assert (
            principal_scoped_path(tmp_path, None, "journal", mode="multi")
            == tmp_path / "journal.ndjson"
        )

    def test_multi_mode_scopes_every_kind_per_person(self, tmp_path):
        p = Principal(id="beta")
        for kind, filename in SCOPED_PATH_FILENAMES.items():
            assert principal_scoped_path(tmp_path, p, kind, mode="multi") == (
                tmp_path / "users" / "beta" / filename
            )

    def test_multi_mode_agent_scopes_to_owner_tree(self, tmp_path):
        a = Principal(id="loreling", kind="agent", owner_id="beta")
        assert (
            principal_scoped_path(tmp_path, a, "proposals", mode="multi")
            == tmp_path / "users" / "beta" / "proposals.json"
        )

    def test_unknown_kind_fails_closed(self, tmp_path):
        with pytest.raises(ValueError):
            principal_scoped_path(tmp_path, Principal(id="beta"), "vault", mode="multi")

    def test_traversal_id_rejected(self, tmp_path):
        for bad in ("../evil", "..", "a/b", ""):
            with pytest.raises(ValueError):
                principal_scoped_path(
                    tmp_path, Principal(id=bad), "world", mode="multi"
                )


# ── API: two principals, one instance ──────────────────────────────────


def _mk(tmp_path, monkeypatch, mode="multi"):
    from personal_world.api import create_app

    monkeypatch.setenv("PW_API_TOKEN", "instancetoken")
    monkeypatch.setenv("PW_IDENTITY_MODE", mode)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    return TestClient(create_app(tmp_path, tmp_path))


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "X-PW-StepUp": "1"}


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_principal_id_validation_matches_identity_safe_pattern(tmp_path, monkeypatch):
    """Create endpoints validate ids with the same pattern
    identity.principal_scoped_path enforces: unicode ids ('héllo',
    which would 500 every later scoped route) and whitespace are
    rejected 4xx; dotted ids ('a.b') identity accepts stay valid."""
    c = _mk(tmp_path, monkeypatch, mode="multi")

    # unicode id → 4xx, and never provisioned
    r = c.post(
        "/api/identity/users", json={"user_id": "héllo"}, headers=_h("instancetoken")
    )
    assert r.status_code == 422
    r = c.post(
        "/api/identity/agents", json={"agent_id": "ro/bot"}, headers=_h("instancetoken")
    )
    assert r.status_code == 422

    # whitespace id → 4xx
    r = c.post(
        "/api/identity/users", json={"user_id": " "}, headers=_h("instancetoken")
    )
    assert r.status_code == 422

    # dotted id — accepted by the safe pattern — provisions cleanly
    r = c.post(
        "/api/identity/users", json={"user_id": "a.b"}, headers=_h("instancetoken")
    )
    assert r.status_code == 200, r.text
    tok = r.json()["data"]["token"]
    # the scoped route for the dotted id must resolve, not 500
    r = c.get("/api/prefs", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    # previously-valid simple ids keep working
    r = c.post(
        "/api/identity/users",
        json={"user_id": "plain-id_2"},
        headers=_h("instancetoken"),
    )
    assert r.status_code == 200, r.text


def _provision(c, user_id="beta"):
    r = c.post(
        "/api/identity/users",
        json={"user_id": user_id, "display_name": "Beta"},
        headers=_h("instancetoken"),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["token"]


def test_journal_isolated_between_principals(tmp_path, monkeypatch):
    c = _mk(tmp_path, monkeypatch)
    tok_b = _provision(c)
    r = c.post(
        "/api/journal",
        json={"text": "alpha private note"},
        headers=_auth("instancetoken"),
    )
    assert r.status_code == 200, r.text
    alpha_texts = [
        e["summary"]
        for e in c.get("/api/journal", headers=_auth("instancetoken")).json()["data"]
    ]
    beta_texts = [
        e["summary"] for e in c.get("/api/journal", headers=_auth(tok_b)).json()["data"]
    ]
    assert "alpha private note" in alpha_texts
    assert "alpha private note" not in beta_texts


def test_reminders_isolated_between_principals(tmp_path, monkeypatch):
    c = _mk(tmp_path, monkeypatch)
    tok_b = _provision(c)
    r = c.post(
        "/api/reminders",
        json={"id": "r-alpha", "text": "alpha secret reminder"},
        headers=_h("instancetoken"),
    )
    assert r.status_code == 200, r.text
    mine = c.get("/api/reminders", headers=_auth("instancetoken")).json()["data"]
    theirs = c.get("/api/reminders", headers=_auth(tok_b)).json()["data"]
    assert [x["id"] for x in mine] == ["r-alpha"]
    assert theirs == []
    # beta cannot delete alpha's reminder (it is not in beta's tree)
    d = c.delete("/api/reminders/r-alpha", headers=_h(tok_b))
    assert d.json()["ok"] is False
    # stored in the caller's own tree, never the shared instance file
    assert (tmp_path / "users" / "primary" / "reminders.json").exists()
    assert not (tmp_path / "users" / "beta" / "reminders.json").exists()


def test_proposals_isolated_between_principals(tmp_path, monkeypatch):
    c = _mk(tmp_path, monkeypatch)
    tok_b = _provision(c)
    import personal_world.tool_registry as tr

    alpha_store = tr.proposal_store_for(
        tmp_path / "users" / "primary" / "proposals.json"
    )
    beta_store = tr.proposal_store_for(tmp_path / "users" / "beta" / "proposals.json")
    pid_a = tr._propose_journal_write(
        None, "alpha private proposal", store=alpha_store
    ).data["proposal_id"]
    pid_b = tr._propose_journal_write(
        None, "beta private proposal", store=beta_store
    ).data["proposal_id"]

    a_list = c.get("/api/proposals", headers=_auth("instancetoken")).json()["data"]
    b_list = c.get("/api/proposals", headers=_auth(tok_b)).json()["data"]
    assert [p["text"] for p in a_list] == ["alpha private proposal"]
    assert [p["text"] for p in b_list] == ["beta private proposal"]

    # ids are per-tree: even the SAME id resolves to the caller's own
    # proposal, never the other person's content
    a_get = c.get(f"/api/proposals/{pid_a}", headers=_auth("instancetoken")).json()[
        "data"
    ]
    b_get = c.get(f"/api/proposals/{pid_b}", headers=_auth(tok_b)).json()["data"]
    assert a_get["text"] == "alpha private proposal"
    assert b_get["text"] == "beta private proposal"

    # alpha approving its own proposal never touches beta's state
    ap = c.post(f"/api/proposals/{pid_a}/approve", headers=_h("instancetoken"))
    assert ap.status_code == 200 and ap.json()["ok"] is True
    b_after = c.get(f"/api/proposals/{pid_b}", headers=_auth(tok_b)).json()["data"]
    assert b_after["status"] == "pending"


def test_prefs_isolated_between_principals(tmp_path, monkeypatch):
    c = _mk(tmp_path, monkeypatch)
    tok_b = _provision(c)
    r = c.put("/api/prefs", json={"text_scale": 1.25}, headers=_h("instancetoken"))
    assert r.status_code == 200, r.text
    assert (
        c.get("/api/prefs", headers=_auth("instancetoken")).json()["data"]["text_scale"]
        == 1.25
    )
    assert c.get("/api/prefs", headers=_auth(tok_b)).json()["data"]["text_scale"] == 1.0


def test_chat_history_isolated_between_principals(tmp_path, monkeypatch):
    c = _mk(tmp_path, monkeypatch)
    tok_b = _provision(c)
    from personal_world.chat_history import ChatHistory

    ChatHistory(tmp_path / "users" / "beta" / "chat-history.ndjson").append(
        "user", "beta secret chat"
    )
    r_a = c.get("/api/chat/history", headers=_auth("instancetoken"))
    r_b = c.get("/api/chat/history", headers=_auth(tok_b))
    assert r_a.status_code == 200 and r_a.json()["data"]["entries"] == []
    contents = [e["content"] for e in r_b.json()["data"]["entries"]]
    assert "beta secret chat" in contents


# ── single-user default: legacy data keeps working ─────────────────────


def test_single_mode_reads_legacy_reminders_and_proposals(tmp_path, monkeypatch):
    # a pre-existing install: instance-root files, no users/ tree
    (tmp_path / "reminders.json").write_text(
        json.dumps(
            {
                "reminders": [
                    {"id": "legacy-1", "text": "legacy reminder", "enabled": True}
                ]
            }
        )
    )
    (tmp_path / "proposals.json").write_text(
        json.dumps(
            {
                "proposal-7": {
                    "type": "journal_write",
                    "text": "legacy proposal",
                    "status": "pending",
                    "created_at": 0,
                }
            }
        )
    )
    monkeypatch.delenv("PW_IDENTITY_MODE", raising=False)
    c = _mk(tmp_path, monkeypatch, mode="single")
    auth = _auth("instancetoken")

    rem = c.get("/api/reminders", headers=auth).json()["data"]
    assert [r["id"] for r in rem] == ["legacy-1"]
    props = c.get("/api/proposals", headers=auth).json()["data"]
    assert [p["proposal_id"] for p in props] == ["proposal-7"]
    assert [p["text"] for p in props] == ["legacy proposal"]

    # new writes stay on the legacy paths; no user tree appears
    r = c.post(
        "/api/reminders",
        json={"id": "new-1", "text": "new legacy reminder"},
        headers=_h("instancetoken"),
    )
    assert r.status_code == 200, r.text
    on_disk = json.loads((tmp_path / "reminders.json").read_text())
    assert {x["id"] for x in on_disk["reminders"]} == {"legacy-1", "new-1"}
    assert not (tmp_path / "users").exists()


def test_single_mode_reads_legacy_chat_history(tmp_path, monkeypatch):
    from personal_world.chat_history import ChatHistory

    ChatHistory(tmp_path / "chat-history.ndjson").append(
        "assistant", "legacy reply", provider="test"
    )
    monkeypatch.delenv("PW_IDENTITY_MODE", raising=False)
    c = _mk(tmp_path, monkeypatch, mode="single")
    entries = c.get("/api/chat/history", headers=_auth("instancetoken")).json()["data"][
        "entries"
    ]
    assert [e["content"] for e in entries] == ["legacy reply"]
    assert not (tmp_path / "users").exists()


def test_single_mode_journal_and_prefs_stay_on_legacy_files(tmp_path, monkeypatch):
    monkeypatch.delenv("PW_IDENTITY_MODE", raising=False)
    c = _mk(tmp_path, monkeypatch, mode="single")
    r = c.post(
        "/api/journal", json={"text": "legacy note"}, headers=_auth("instancetoken")
    )
    assert r.status_code == 200, r.text
    assert (tmp_path / "journal.ndjson").exists()
    assert "legacy note" in (tmp_path / "journal.ndjson").read_text()
    r = c.put("/api/prefs", json={"text_scale": 1.5}, headers=_h("instancetoken"))
    assert r.status_code == 200, r.text
    assert "text_scale" in (tmp_path / "world.json").read_text()
    assert not (tmp_path / "users").exists()
