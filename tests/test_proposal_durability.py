"""D3 — Durable human proposal authority.

The reconciled approval architecture is preserved (server-held
approval evidence; ``approve_proposal``/``reject_proposal``; the
``/api/proposals`` lifecycle; the model cannot self-approve). This
suite proves the missing durability:

- proposals and their approval evidence persist to
  ``<data_dir>/proposals.json`` and survive a process restart
- the id counter resumes above the highest persisted id
- an approved proposal can still be executed after reload, while a
  model-supplied boolean never satisfies the gate
- the trusted approval/rejection is journalled when a journal is wired
- the API execute path persists world mutations through the
  authoritative save path (no dropped ``world_path``)
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

import personal_world.tool_registry as tr  # noqa: E402
from personal_world.journal import Journal  # noqa: E402
from personal_world.tool_registry import (  # noqa: E402
    _execute_approved_write,
    _proposals,
    _propose_journal_write,
    _propose_world_intent,
    approve_proposal,
    configure_proposal_store,
    reject_proposal,
)


@pytest.fixture(autouse=True)
def _reset_store(tmp_path):
    tr._proposals.clear()
    tr._proposal_path = None
    tr._proposal_journal = None
    tr._proposal_counter = 0
    yield
    tr._proposals.clear()
    tr._proposal_path = None
    tr._proposal_journal = None
    tr._proposal_counter = 0


class FakeJournal:
    def __init__(self):
        self.entries = []

    def record(self, kind, summary, source=""):
        self.entries.append({"kind": kind, "summary": summary, "source": source})


class TestDurableStore:
    def test_propose_persists_pending(self, tmp_path):
        configure_proposal_store(tmp_path)
        r = _propose_journal_write(FakeJournal(), "durable note")
        assert r.ok
        pid = r.data["proposal_id"]
        on_disk = json.loads((tmp_path / "proposals.json").read_text())
        assert on_disk[pid]["status"] == "pending"
        assert on_disk[pid]["type"] == "journal_write"

    def test_approval_evidence_persists(self, tmp_path):
        configure_proposal_store(tmp_path)
        pid = _propose_journal_write(FakeJournal(), "note").data["proposal_id"]
        assert approve_proposal(pid, "owner").ok
        on_disk = json.loads((tmp_path / "proposals.json").read_text())
        p = on_disk[pid]
        assert p["status"] == "approved"
        assert p["approved_by"] == "owner"
        assert p["approved_at"]
        assert p["approval_evidence"]["method"] == "trusted-api-approval"

    def test_rejection_persists(self, tmp_path):
        configure_proposal_store(tmp_path)
        pid = _propose_journal_write(FakeJournal(), "note").data["proposal_id"]
        assert reject_proposal(pid, "owner").ok
        on_disk = json.loads((tmp_path / "proposals.json").read_text())
        assert on_disk[pid]["status"] == "rejected"
        assert on_disk[pid]["rejected_by"] == "owner"

    def test_survives_restart_and_executes(self, tmp_path):
        configure_proposal_store(tmp_path)
        journal = FakeJournal()
        pid = _propose_journal_write(journal, "survives restart").data["proposal_id"]
        assert approve_proposal(pid, "owner").ok

        # simulate a process restart: a brand new app over the same dir
        configure_proposal_store(tmp_path)
        assert _proposals[pid]["status"] == "approved"
        assert _proposals[pid]["approved_by"] == "owner"

        ex = _execute_approved_write(journal, None, pid)
        assert ex.ok and ex.data["status"] == "executed"
        # executed status is durable too
        on_disk = json.loads((tmp_path / "proposals.json").read_text())
        assert on_disk[pid]["status"] == "executed"

    def test_counter_resumes_above_highest_id(self, tmp_path):
        configure_proposal_store(tmp_path)
        first = _propose_journal_write(FakeJournal(), "one").data["proposal_id"]
        assert first == "proposal-1"
        configure_proposal_store(tmp_path)  # reload
        second = _propose_journal_write(FakeJournal(), "two").data["proposal_id"]
        assert second == "proposal-2"

    def test_fresh_dir_loads_no_prior_state(self, tmp_path):
        configure_proposal_store(tmp_path)
        _propose_journal_write(FakeJournal(), "one")
        configure_proposal_store(tmp_path / "other")
        assert _proposals == {}

    def test_no_store_configured_stays_in_memory_only(self, tmp_path):
        # unit tests and embedded use without a data dir must not write
        r = _propose_journal_write(FakeJournal(), "memory only")
        assert r.ok
        assert not (tmp_path / "proposals.json").exists()


class TestApprovalEvidenceBoundary:
    def test_model_supplied_flag_cannot_execute(self, tmp_path):
        configure_proposal_store(tmp_path)
        journal = FakeJournal()
        pid = _propose_journal_write(journal, "note").data["proposal_id"]
        # a model argument is not approval: still pending, execution refused
        ex = _execute_approved_write(journal, None, pid)
        assert not ex.ok
        assert "not approved" in ex.warnings[0]
        assert _proposals[pid]["status"] == "pending"
        assert not journal.entries

    def test_trusted_approval_is_journalled(self, tmp_path):
        journal = Journal(tmp_path / "journal.ndjson")
        configure_proposal_store(tmp_path, journal=journal)
        pid = _propose_world_intent(journal, None, "k", "v").data["proposal_id"]
        assert approve_proposal(pid, "owner").ok
        summaries = [e.summary for e in journal.events()]
        assert any("approved by owner" in s and pid in s for s in summaries)

    def test_rejection_is_journalled(self, tmp_path):
        journal = Journal(tmp_path / "journal.ndjson")
        configure_proposal_store(tmp_path, journal=journal)
        pid = _propose_journal_write(journal, "note").data["proposal_id"]
        assert reject_proposal(pid, "owner").ok
        summaries = [e.summary for e in journal.events()]
        assert any("rejected by owner" in s and pid in s for s in summaries)


class TestApiExecutePersistence:
    def test_api_execute_saves_world(self, tmp_path, monkeypatch):
        from personal_world.api import create_app
        from personal_world.app import load_world

        monkeypatch.delenv("PW_DEV_AUTH_BYPASS", raising=False)
        monkeypatch.setenv("PW_API_TOKEN", "t-token")
        monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
        c = TestClient(create_app(tmp_path, tmp_path))
        # the app configured the store to this data dir; propose through
        # the same server-held store
        journal = Journal(tmp_path / "journal.ndjson")
        world = load_world(tmp_path / "world.json")
        pid = _propose_world_intent(
            journal, world, "durable/intent", "sunny").data["proposal_id"]

        auth = {"Authorization": "Bearer t-token"}
        assert c.post(f"/api/proposals/{pid}/approve",
                      headers=auth).status_code == 200
        ex = c.post(f"/api/proposals/{pid}/execute", headers=auth).json()
        assert ex["ok"] is True, ex
        assert ex["data"]["status"] == "executed"

        # a fresh load sees the persisted intent (world_path was wired)
        fresh = load_world(tmp_path / "world.json")
        assert "durable/intent" in fresh.intents

    def test_api_approve_is_step_up_gated(self, tmp_path, monkeypatch):
        from personal_world.api import create_app

        monkeypatch.setenv("PW_API_TOKEN", "t-token")
        monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
        c = TestClient(create_app(tmp_path, tmp_path))
        pid = _propose_journal_write(
            Journal(tmp_path / "journal.ndjson"), "note").data["proposal_id"]
        # no auth at all → 401
        assert c.post(f"/api/proposals/{pid}/approve").status_code == 401
