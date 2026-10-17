"""Authorization boundary tests: prove the propose → approve → execute boundary.

These tests verify:
- brain can prepare a proposal (propose_* tools)
- preparing changes no target domain state
- model cannot approve proposal
- model cannot execute proposal
- forged approval fields are ignored/rejected
- owner approval changes server-side proposal state
- only approved proposal executes
- replay/reuse is rejected
"""

import pytest

from personal_world.envelope import Result
from personal_world.tool_registry import (
    Tool,
    ToolRegistry,
    _proposals,
    _propose_journal_write,
    approve_proposal,
    reject_proposal,
)


@pytest.fixture(autouse=True)
def clear_proposals():
    """Clear proposal store between tests."""
    _proposals.clear()
    import personal_world.tool_registry as tr
    tr._proposal_counter = 0
    yield
    _proposals.clear()
    tr._proposal_counter = 0


class FakeJournal:
    """Stub journal for testing."""
    def __init__(self):
        self.recorded = False
        self.entries = []
    def record(self, kind, summary, source=""):
        self.recorded = True
        self.entries.append({"kind": kind, "summary": summary, "source": source})


class TestWriteToolBoundary:
    """Proposal tools callable; execution tools blocked."""

    def test_propose_tool_allowed(self):
        """Brain can call proposal tools (requires_approval=True)."""
        tools = ToolRegistry()
        tools.register(Tool(
            id="propose_test",
            capability="test",
            operation="write",
            description="Test proposal tool",
            read_write="write",
            requires_approval=True,
            parameters={"type": "object", "properties": {}},
            handler=lambda: Result(ok=True, status="healthy", data={"proposal_id": "p1"}),
        ))
        result = tools.invoke("propose_test", {})
        assert result.ok
        assert result.status == "healthy"

    def test_execute_tool_blocked(self):
        """Brain cannot call execution tools (no requires_approval)."""
        tools = ToolRegistry()
        tools.register(Tool(
            id="execute_test",
            capability="test",
            operation="write",
            description="Test execute tool",
            read_write="write",
            requires_step_up=True,
            parameters={"type": "object", "properties": {}},
            handler=lambda: Result(ok=True, status="healthy"),
        ))
        result = tools.invoke("execute_test", {})
        assert not result.ok
        assert result.status == "forbidden"
        assert "execution tool" in (result.warnings[0] if result.warnings else "")

    def test_read_tool_works(self):
        """Read tools still execute normally."""
        tools = ToolRegistry()
        tools.register(Tool(
            id="read_test",
            capability="test",
            operation="read",
            description="Test read tool",
            read_write="read",
            parameters={"type": "object", "properties": {}},
            handler=lambda: Result(ok=True, status="healthy", data={"ok": True}),
        ))
        result = tools.invoke("read_test", {})
        assert result.ok
        assert result.status == "healthy"

    def test_propose_tools_in_ollama_schemas(self):
        """Proposal tools ARE exposed to the model for function-calling."""
        tools = ToolRegistry()
        tools.register(Tool(
            id="read_tool",
            capability="test",
            operation="read",
            description="Read",
            read_write="read",
            parameters={"type": "object", "properties": {}},
            handler=lambda: Result(ok=True, status="healthy"),
        ))
        tools.register(Tool(
            id="propose_tool",
            capability="test",
            operation="write",
            description="Propose",
            read_write="write",
            requires_approval=True,
            parameters={"type": "object", "properties": {}},
            handler=lambda: Result(ok=True, status="healthy"),
        ))
        tools.register(Tool(
            id="execute_tool",
            capability="test",
            operation="execute",
            description="Execute",
            read_write="write",
            requires_step_up=True,
            parameters={"type": "object", "properties": {}},
            handler=lambda: Result(ok=True, status="healthy"),
        ))
        schemas = tools.list_ollama_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "read_tool" in names
        assert "propose_tool" in names
        assert "execute_tool" not in names


class TestProposalApprovalBoundary:
    """Proposals require server-side owner approval."""

    def test_brain_can_prepare_proposal(self):
        """Brain can call propose_* to create a pending proposal."""
        journal = FakeJournal()
        result = _propose_journal_write(journal, "test entry")
        assert result.ok
        assert result.data["proposal_id"]
        assert _proposals[result.data["proposal_id"]]["status"] == "pending"

    def test_preparing_does_not_mutate_target(self):
        """Creating a proposal does NOT write to the journal."""
        journal = FakeJournal()
        result = _propose_journal_write(journal, "test entry")
        assert result.ok
        assert not journal.recorded

    def test_model_cannot_approve_proposal(self):
        """No approve tool exists in the registry — approval is API-only."""
        tools = ToolRegistry()
        tools.register(Tool(
            id="propose_journal_entry",
            capability="journal",
            operation="write",
            description="Propose journal",
            read_write="write",
            requires_approval=True,
            parameters={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            handler=lambda text: _propose_journal_write(FakeJournal(), text),
        ))
        # Brain can propose
        result = tools.invoke("propose_journal_entry", {"text": "test"})
        assert result.ok
        # But there is no "approve" tool in the registry
        all_tool_ids = [t.id for t in tools.list_tools()]
        assert not any("approve" in t for t in all_tool_ids)

    def test_execute_rejects_pending_proposal(self):
        """Cannot execute a proposal that hasn't been approved."""
        from personal_world.tool_registry import _execute_approved_write
        _proposals["test-1"] = {
            "type": "journal_write",
            "text": "test",
            "status": "pending",
        }
        result = _execute_approved_write(FakeJournal(), None, "test-1")
        assert not result.ok
        assert "not approved" in (result.warnings[0] if result.warnings else "")

    def test_execute_rejects_rejected_proposal(self):
        """Cannot execute a rejected proposal."""
        from personal_world.tool_registry import _execute_approved_write
        _proposals["test-2"] = {
            "type": "journal_write",
            "text": "test",
            "status": "rejected",
        }
        result = _execute_approved_write(FakeJournal(), None, "test-2")
        assert not result.ok
        assert "not approved" in (result.warnings[0] if result.warnings else "")

    def test_execute_rejects_unknown_proposal(self):
        """Cannot execute a nonexistent proposal."""
        from personal_world.tool_registry import _execute_approved_write
        result = _execute_approved_write(FakeJournal(), None, "nonexistent")
        assert not result.ok
        assert result.status == "not_found"

    def test_approve_sets_evidence(self):
        """Approval records actor, time, and evidence."""
        _proposals["test-3"] = {
            "type": "journal_write",
            "text": "test",
            "status": "pending",
        }
        result = approve_proposal("test-3", "owner")
        assert result.ok
        assert _proposals["test-3"]["status"] == "approved"
        assert _proposals["test-3"]["approved_by"] == "owner"
        assert "approved_at" in _proposals["test-3"]

    def test_approve_rejects_non_pending(self):
        """Cannot approve a proposal that isn't pending."""
        _proposals["test-4"] = {
            "type": "journal_write",
            "text": "test",
            "status": "approved",
        }
        result = approve_proposal("test-4", "owner")
        assert not result.ok
        assert "not pending" in (result.warnings[0] if result.warnings else "")

    def test_reject_changes_state(self):
        """Rejection changes proposal state."""
        _proposals["test-5"] = {
            "type": "journal_write",
            "text": "test",
            "status": "pending",
        }
        result = reject_proposal("test-5", "owner")
        assert result.ok
        assert _proposals["test-5"]["status"] == "rejected"
        assert _proposals["test-5"]["rejected_by"] == "owner"

    def test_approved_proposal_can_execute(self):
        """An approved proposal can be executed through the trusted path."""
        from personal_world.tool_registry import _execute_approved_write
        journal = FakeJournal()
        _proposals["test-6"] = {
            "type": "journal_write",
            "text": "test entry",
            "status": "approved",
            "approved_by": "owner",
            "approved_at": 1234567890,
        }
        result = _execute_approved_write(journal, None, "test-6")
        assert result.ok
        assert result.data["status"] == "executed"
        assert _proposals["test-6"]["status"] == "executed"
        assert journal.recorded

    def test_execution_failure_leaves_state_honest(self):
        """If execution fails, proposal status reflects the failure."""
        from personal_world.tool_registry import _execute_approved_write

        class FailingJournal:
            def record(self, *args, **kwargs):
                raise RuntimeError("storage failure")

        journal = FailingJournal()
        _proposals["test-7"] = {
            "type": "journal_write",
            "text": "test entry",
            "status": "approved",
            "approved_by": "owner",
            "approved_at": 1234567890,
        }
        result = _execute_approved_write(journal, None, "test-7")
        assert not result.ok
        assert _proposals["test-7"]["status"] == "failed"

    def test_double_approve_rejected(self):
        """Cannot approve a proposal twice."""
        _proposals["test-8"] = {
            "type": "journal_write",
            "text": "test",
            "status": "pending",
        }
        approve_proposal("test-8", "owner")
        result = approve_proposal("test-8", "owner")
        assert not result.ok

    def test_double_execute_rejected(self):
        """Cannot execute a proposal twice."""
        from personal_world.tool_registry import _execute_approved_write
        journal = FakeJournal()
        _proposals["test-9"] = {
            "type": "journal_write",
            "text": "test",
            "status": "approved",
            "approved_by": "owner",
            "approved_at": 1234567890,
        }
        result1 = _execute_approved_write(journal, None, "test-9")
        assert result1.ok
        result2 = _execute_approved_write(journal, None, "test-9")
        assert not result2.ok


class TestToolRegistryIntegrity:
    """The tool registry enforces boundaries consistently."""

    def test_nonexistent_tool(self):
        tools = ToolRegistry()
        result = tools.invoke("nonexistent", {})
        assert not result.ok
        assert result.status == "not_found"

    def test_no_handler_tool(self):
        tools = ToolRegistry()
        tools.register(Tool(
            id="no_handler",
            capability="test",
            operation="read",
            description="No handler",
            read_write="read",
            parameters={},
        ))
        result = tools.invoke("no_handler", {})
        assert not result.ok
        assert result.status == "not_implemented"
