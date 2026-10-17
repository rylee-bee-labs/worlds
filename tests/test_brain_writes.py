"""Brain write-path coherence (critical batch, reconciled with the
merged approval-evidence boundary).

The other lane's design (merged to origin/main) is authoritative for
the approval mechanism: proposals are server-held state; the owner
approves through the trusted API path (`approve_proposal` records
actor/time evidence); `_execute_approved_write` requires the
'approved' state with that evidence — a model-supplied boolean alone
executes nothing. This suite re-proves the critical-batch outcomes on
top of that design:

- TOOL-004: journal search resolves through the canonical FTS memory
  provider (same source as /api/memory/search) and finds known phrases.
- TOOL-025/026: an APPROVED execution persists to world.json; a
  brand-new load sees the intent/fact.
- TOOL-027: an APPROVED reminder execution goes through the live
  Scheduler (reminders.json); it survives a fresh Scheduler instance.
- TOOL-028: reconciler apply without an adapter answers
  ok=False / unsupported and consumes nothing.
- TOOL-029 truthfulness: unwired paths fail honestly; proposals stay
  pending until server-held approval evidence exists.
"""

import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.app import load_world  # noqa: E402
from personal_world.journal import Journal  # noqa: E402
from personal_world.providers.native_memory import (  # noqa: E402
    NativeMemoryProvider,
)
from personal_world.scheduler import Scheduler  # noqa: E402
from personal_world.tool_registry import (  # noqa: E402
    _execute_approved_write,
    _proposals,
    _propose_reconciler_apply,
    _propose_reminder,
    _propose_world_fact,
    _propose_world_intent,
    _search_journal,
    approve_proposal,
)


def _world_env(tmp_path):
    world_path = tmp_path / "world.json"
    world = load_world(world_path)
    journal = Journal(tmp_path / "journal.ndjson")
    memory = NativeMemoryProvider(tmp_path, journal=journal)
    return world, world_path, journal, memory


def _approved(proposal_id: str) -> None:
    r = approve_proposal(proposal_id, "owner")
    assert r.ok, r.warnings


class TestJournalSearch:
    def test_search_via_memory_fts(self, tmp_path):
        world, world_path, journal, memory = _world_env(tmp_path)
        journal.record(
            "observation", "the lantern festival is on Friday", source="test"
        )
        memory.index_journal()
        r = _search_journal(journal, "lantern", memory)
        assert r.ok, r.warnings
        entries = r.data["entries"]
        assert entries, "known phrase must be found"
        assert any("lantern festival" in (e.get("summary") or "") for e in entries)

    def test_no_memory_provider_is_honest(self, tmp_path):
        world, world_path, journal, _ = _world_env(tmp_path)
        r = _search_journal(journal, "anything", None)
        assert not r.ok
        assert r.status == "unavailable"


class TestWorldWrites:
    def test_intent_persists_across_fresh_load(self, tmp_path):
        world, world_path, journal, memory = _world_env(tmp_path)
        r = _propose_world_intent(journal, world, "wishes/weather", "sunny tomorrow")
        assert r.ok and r.data["status"] == "pending"
        _approved(r.data["proposal_id"])
        ex = _execute_approved_write(
            journal,
            world,
            r.data["proposal_id"],
            world_path=world_path,
        )
        assert ex.ok and ex.data["status"] == "executed"
        assert ex.data["persisted"] == "world.json"
        fresh = load_world(world_path)
        assert "wishes/weather" in fresh.intents

    def test_fact_persists_across_new_api_request(self, tmp_path):
        world, world_path, journal, memory = _world_env(tmp_path)
        r = _propose_world_fact(journal, world, "tea/brewed", "yes")
        assert r.ok
        _approved(r.data["proposal_id"])
        ex = _execute_approved_write(
            journal,
            world,
            r.data["proposal_id"],
            world_path=world_path,
        )
        assert ex.ok and ex.data["status"] == "executed"
        # simulate a completely new request: load world from disk
        fresh = load_world(world_path)
        assert fresh.facts["tea/brewed"].value == "yes"


class TestReminderWrites:
    def test_authorized_execution_creates_real_reminder(self, tmp_path):
        world, world_path, journal, memory = _world_env(tmp_path)
        sched = Scheduler(tmp_path / "reminders.json", journal=journal)
        r = _propose_reminder(journal, "water the ferns")
        assert r.ok and r.data["status"] == "pending"
        _approved(r.data["proposal_id"])
        ex = _execute_approved_write(
            journal,
            world,
            r.data["proposal_id"],
            world_path=world_path,
            scheduler=sched,
        )
        assert ex.ok and ex.data["status"] == "executed"
        assert ex.data["persisted"] == "reminders.json"
        # fresh Scheduler over the same path sees it (survives restart)
        sched2 = Scheduler(tmp_path / "reminders.json")
        texts = [x.text for x in sched2.list_reminders()]
        assert "water the ferns" in texts

    def test_unwired_scheduler_leaves_pending(self, tmp_path):
        world, world_path, journal, memory = _world_env(tmp_path)
        r = _propose_reminder(journal, "check the mail")
        _approved(r.data["proposal_id"])
        ex = _execute_approved_write(
            journal,
            world,
            r.data["proposal_id"],
            world_path=world_path,
        )
        assert not ex.ok
        # merged authority: scheduler refusal marks the proposal FAILED
        # (honest non-execution — a retry re-proposes)
        assert _proposals[r.data["proposal_id"]]["status"] == "failed"


class TestReconcilerApply:
    def test_unsupported_without_adapter(self, tmp_path):
        world, world_path, journal, memory = _world_env(tmp_path)
        r = _propose_reconciler_apply(journal, "no-such-service")
        # service has no desired state → honest not_found
        assert not r.ok
        assert r.status == "not_found"

    def test_execution_reports_unsupported_not_success(
        self,
        tmp_path,
        monkeypatch,
    ):
        world, world_path, journal, memory = _world_env(tmp_path)
        # create desired state where the reconciler actually reads it
        monkeypatch.setenv("HOME", str(tmp_path))
        desired_dir = tmp_path / ".config/personal-world/reconciler/desired"
        desired_dir.mkdir(parents=True)
        (desired_dir / "svc.yml").write_text("image: nginx\n")
        r = _propose_reconciler_apply(journal, "svc")
        assert r.ok and r.data["status"] == "pending"
        pid = r.data["proposal_id"]
        _approved(pid)
        ex = _execute_approved_write(journal, world, pid, world_path=world_path)
        assert not ex.ok
        assert ex.status == "unsupported"
        assert _proposals[pid]["status"] == "pending"


class TestProposalAudit:
    def test_creation_recorded_in_proposal_store(self, tmp_path):
        world, world_path, journal, memory = _world_env(tmp_path)
        r = _propose_world_intent(journal, world, "audit-key", "audit-val")
        assert r.data["status"] == "pending"
        # merged authority: the proposal store itself is the audit of
        # preparation — list/get expose id, type, and pending status
        from personal_world.tool_registry import list_proposals

        listed = list_proposals("pending")
        assert any(
            p["proposal_id"] == r.data["proposal_id"] and p["type"] == "world_intent"
            for p in listed
        )

    def test_no_fake_approval_journaled(self, tmp_path):
        world, world_path, journal, memory = _world_env(tmp_path)
        r = _propose_world_intent(journal, world, "k4", "v4")
        pid = r.data["proposal_id"]
        before = journal.recent(100)
        # model-supplied 'approval evidence' cannot satisfy the gate:
        # the proposal is still pending and execution refuses
        ex = _execute_approved_write(journal, world, pid)
        assert not ex.ok
        after = journal.recent(len(before) + 50)
        # no new journal event may claim an approval/execution
        new_events = after[len(before) :]
        assert not any("approved" in e.summary.lower() for e in new_events)

    def test_preparing_does_not_mutate_target(self, tmp_path):
        world, world_path, journal, memory = _world_env(tmp_path)
        r = _propose_world_fact(journal, world, "pkey", "pval")
        assert r.ok
        fresh = load_world(world_path)
        assert "pkey" not in fresh.facts
        assert "pkey" not in fresh.intents


class TestExecuteUnderLock:
    def test_double_execution_is_rejected(self, tmp_path):
        """execute() takes the approved check + status transition under
        the store lock: a second execution of the same proposal is
        refused, never replayed."""
        import json

        from personal_world.tool_registry import ProposalStore

        path = tmp_path / "proposals.json"
        store = ProposalStore(path=path)
        r = store.propose(
            {"type": "journal_write", "text": "hi"}, journal=None, description="d"
        )
        pid = r.data["proposal_id"]
        store.approve(pid, "owner")
        from personal_world.journal import Journal

        journal = Journal(tmp_path / "j.ndjson")
        world = object()
        result = store.execute(journal, world, pid)
        assert result.ok is True
        # Persisted status is terminal and non-replayable.
        data = json.loads(path.read_text())
        assert data[pid]["status"] == "executed"
        second = store.execute(journal, world, pid)
        assert second.ok is False
        assert second.status == "invalid_state"


class TestInvokeLogging:
    def test_handler_failure_keeps_envelope_and_logs_exception(self, tmp_path, caplog):
        """A failing tool handler still answers the honest envelope;
        the server log keeps the exception trace (COR-09)."""
        import logging

        from personal_world.tool_registry import Tool, ToolRegistry

        reg = ToolRegistry()

        def boom():
            raise RuntimeError("upstream exploded")

        reg.register(
            Tool(
                id="boom",
                capability="test",
                operation="test",
                description="x",
                read_write="read",
                handler=boom,
            )
        )
        r = reg.invoke("boom", {})
        assert r.ok is False and r.status == "unavailable"
        assert "upstream exploded" in (r.warnings[0] if r.warnings else "")
        with caplog.at_level(logging.ERROR, logger="personal_world.tool_registry"):
            reg.invoke("boom", {})
        assert any(
            "RuntimeError" in rec.getMessage()
            or "upstream exploded" in rec.getMessage()
            for rec in caplog.records
        )
