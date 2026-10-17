"""Reminder execution state tests.

Proves:
- successful scheduling => proposal executed
- scheduler failure => proposal failed
- no duplicate scheduling/replay
"""

import pytest

from personal_world.envelope import Result
from personal_world.tool_registry import (
    _execute_approved_write,
    _proposals,
)


@pytest.fixture(autouse=True)
def clear_proposals():
    _proposals.clear()
    import personal_world.tool_registry as tr
    tr._proposal_counter = 0
    yield
    _proposals.clear()
    tr._proposal_counter = 0


class FakeScheduler:
    """Stub scheduler for testing."""
    def __init__(self, should_fail: bool = False):
        self.added = []
        self.should_fail = should_fail

    def add(self, reminder):
        if self.should_fail:
            return Result(ok=False, status="unavailable", warnings=["scheduler offline"])
        self.added.append(reminder)
        return Result(ok=True, status="healthy", data={"id": reminder.id})


class FakeJournal:
    def record(self, *a, **kw):
        pass


class FakeWorld:
    pass


class TestReminderExecution:

    def test_successful_scheduling_marks_executed(self):
        """Scheduler add succeeds → proposal status = executed."""
        scheduler = FakeScheduler()
        _proposals["r-1"] = {
            "type": "reminder",
            "text": "Buy groceries",
            "status": "approved",
            "approved_by": "owner",
            "approved_at": 1234567890,
        }
        r = _execute_approved_write(FakeJournal(), FakeWorld(), "r-1", scheduler)
        assert r.ok
        assert r.data["status"] == "executed"
        assert _proposals["r-1"]["status"] == "executed"
        assert len(scheduler.added) == 1
        assert scheduler.added[0].text == "Buy groceries"

    def test_scheduler_failure_marks_failed(self):
        """Scheduler add fails → proposal status = failed."""
        scheduler = FakeScheduler(should_fail=True)
        _proposals["r-2"] = {
            "type": "reminder",
            "text": "Buy groceries",
            "status": "approved",
            "approved_by": "owner",
            "approved_at": 1234567890,
        }
        r = _execute_approved_write(FakeJournal(), FakeWorld(), "r-2", scheduler)
        assert not r.ok
        assert _proposals["r-2"]["status"] == "failed"

    def test_no_scheduler_marks_failed(self):
        """No scheduler available → proposal status = failed."""
        _proposals["r-3"] = {
            "type": "reminder",
            "text": "Buy groceries",
            "status": "approved",
            "approved_by": "owner",
            "approved_at": 1234567890,
        }
        r = _execute_approved_write(FakeJournal(), FakeWorld(), "r-3", None)
        assert not r.ok
        assert _proposals["r-3"]["status"] == "failed"

    def test_no_duplicate_scheduling(self):
        """Cannot execute the same reminder twice."""
        scheduler = FakeScheduler()
        _proposals["r-4"] = {
            "type": "reminder",
            "text": "Buy groceries",
            "status": "approved",
            "approved_by": "owner",
            "approved_at": 1234567890,
        }
        r1 = _execute_approved_write(FakeJournal(), FakeWorld(), "r-4", scheduler)
        assert r1.ok
        assert len(scheduler.added) == 1
        # Second attempt should fail (status is now "executed")
        r2 = _execute_approved_write(FakeJournal(), FakeWorld(), "r-4", scheduler)
        assert not r2.ok
        assert len(scheduler.added) == 1  # No duplicate

    def test_reminder_id_is_proposal_based(self):
        """Reminder ID is derived from proposal ID."""
        scheduler = FakeScheduler()
        _proposals["r-5"] = {
            "type": "reminder",
            "text": "Test",
            "status": "approved",
            "approved_by": "owner",
            "approved_at": 1234567890,
        }
        _execute_approved_write(FakeJournal(), FakeWorld(), "r-5", scheduler)
        assert scheduler.added[0].id == "proposal-r-5"
