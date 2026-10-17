"""P0.4: a firing reminder must land in the journal, not kill the thread.

Before this fix the scheduler called ``journal.append_raw`` — a method
that never existed — so the background thread died silently on the
first reminder that matched. Human Reliability contract: state must be
visible; a dead scheduler is a silent divergence between what the
person thinks is happening and what is.
"""
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.envelope import Result  # noqa: E402
from personal_world.journal import Journal  # noqa: E402
from personal_world.model import JournalKind  # noqa: E402
from personal_world.scheduler import Reminder, Scheduler  # noqa: E402


def _sched(tmp_path):
    journal = Journal(tmp_path / "journal.ndjson")
    return Scheduler(tmp_path / "reminders.json", journal=journal), journal


def test_fire_journals_an_observation(tmp_path):
    s, journal = _sched(tmp_path)
    # all-null cron == matches every tick
    s.add(Reminder(id="r1", text="drink water"))
    fired = s.check_and_fire()
    assert fired == ["drink water"]
    events = list(journal.events())
    assert len(events) == 1
    assert events[0].kind == JournalKind.OBSERVATION
    assert "drink water" in events[0].summary
    assert events[0].provenance.source == "scheduler"


def test_fire_dedupes_within_a_minute_and_persists_last_fired(tmp_path):
    s, journal = _sched(tmp_path)
    s.add(Reminder(id="r1", text="stretch"))
    assert s.check_and_fire() == ["stretch"]
    assert s.check_and_fire() == []          # same minute → no double fire
    assert len(list(journal.events())) == 1
    fresh = Scheduler(tmp_path / "reminders.json")
    assert fresh.list_reminders()[0].last_fired is not None


def test_disabled_reminders_do_not_fire(tmp_path):
    s, journal = _sched(tmp_path)
    s.add(Reminder(id="r1", text="nope", enabled=False))
    assert s.check_and_fire() == []
    assert list(journal.events()) == []


def test_background_thread_survives_a_failing_tick(tmp_path, monkeypatch):
    s, _ = _sched(tmp_path)
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise RuntimeError("bad tick")

    monkeypatch.setattr(s, "check_and_fire", boom)
    # make the loop tick quickly
    monkeypatch.setattr(s._stop, "wait", lambda _t: time.sleep(0.01))
    s.start()
    time.sleep(0.15)
    s.stop()
    s._thread.join(timeout=1)
    assert calls["n"] >= 2, "thread must keep ticking after an exception"
    assert s._last_error and "bad tick" in s._last_error


# ─ Notification delivery (issue #44): optional, injected, never fatal ──


def _notifier(calls, ok=True, status="healthy", raises=False):
    def send(title, body):
        if raises:
            raise RuntimeError("transport down")
        calls.append((title, body))
        return Result(ok=ok, status=status)

    return send


def test_due_reminder_delivers_through_the_injected_notifier(tmp_path):
    calls = []
    journal = Journal(tmp_path / "journal.ndjson")
    s = Scheduler(
        tmp_path / "reminders.json", journal=journal, notifier=_notifier(calls)
    )
    s.add(Reminder(id="r1", text="drink water"))
    assert s.check_and_fire() == ["drink water"]
    assert calls == [("Project Worlds reminder", "drink water")]
    summary = list(journal.events())[0].summary
    assert "Reminder: drink water" in summary
    assert "notification sent (healthy)" in summary


def test_delivery_failure_is_visible_and_never_kills_the_fire(tmp_path):
    calls = []
    journal = Journal(tmp_path / "journal.ndjson")
    s = Scheduler(
        tmp_path / "reminders.json",
        journal=journal,
        notifier=_notifier(calls, raises=True),
    )
    s.add(Reminder(id="r1", text="stretch"))
    assert s.check_and_fire() == ["stretch"]  # the fire still counted
    assert calls == []
    assert "notification failed (RuntimeError)" in list(journal.events())[0].summary


def test_unconfigured_delivery_is_reported_honestly(tmp_path):
    journal = Journal(tmp_path / "journal.ndjson")
    s = Scheduler(
        tmp_path / "reminders.json",
        journal=journal,
        notifier=_notifier([], ok=False, status="not_configured"),
    )
    s.add(Reminder(id="breathe", text="breathe"))
    s.check_and_fire()
    summary = list(journal.events())[0].summary
    assert "notification not delivered (not_configured)" in summary


def test_no_notifier_keeps_the_plain_reminder_entry(tmp_path):
    s, journal = _sched(tmp_path)
    s.add(Reminder(id="r1", text="plain"))
    assert s.check_and_fire() == ["plain"]
    events = list(journal.events())
    assert len(events) == 1
    assert events[0].summary == "Reminder: plain"  # no delivery suffix


# ── Missed-fire policy (issue #44): SKIP, never replay ──


def test_missed_fire_is_skipped_not_replayed(tmp_path):
    """A reminder fires only in its matching minute. An occurrence the
    process was not running for is missed, never delivered late."""
    s, journal = _sched(tmp_path)
    now = datetime.now(UTC)
    # Scheduled for an hour that is not the current one -> never matches.
    s.add(
        Reminder(
            id="r1",
            text="stale",
            cron_hour=(now.hour + 1) % 24,
            cron_minute=now.minute,
        )
    )
    assert s.check_and_fire() == []
    assert s.check_and_fire() == []  # still not replayed on a later tick
    assert list(journal.events()) == []
    assert s.list_reminders()[0].last_fired is None


# ── Durable store integrity: corrupt file visible, atomic save ──


def test_corrupt_file_is_logged_and_add_still_works(tmp_path, caplog):
    """A corrupt reminders.json must be VISIBLE (warning log), the
    scheduler must keep working in memory, and the next save must
    produce a valid file again — never a silent overwrite."""
    import logging

    (tmp_path / "reminders.json").write_text("{not json")
    s = Scheduler(tmp_path / "reminders.json", journal=Journal(tmp_path / "j.ndjson"))
    with caplog.at_level(logging.WARNING, logger="personal_world.scheduler"):
        s.add(Reminder(id="r1", text="still works"))
    assert any(
        "could not load" in rec.message and "reminders.json" in rec.message
        for rec in caplog.records
    )
    import json

    data = json.loads((tmp_path / "reminders.json").read_text())
    assert [r["id"] for r in data["reminders"]] == ["r1"]
    assert s._last_error and "unreadable" in s._last_error


def test_save_is_atomic_and_valid_json(tmp_path):
    import json

    s = Scheduler(tmp_path / "reminders.json")
    s.add(Reminder(id="r1", text="ok"))
    data = json.loads((tmp_path / "reminders.json").read_text())
    assert data["reminders"][0]["text"] == "ok"
    assert not (tmp_path / "reminders.json.tmp").exists()
