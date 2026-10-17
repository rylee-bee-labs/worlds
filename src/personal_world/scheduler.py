"""Scheduler: reminders and scheduled observations.

The scheduler is a simple in-process timer that checks a JSON file
of reminders every minute. Reminders fire into the journal as
JournalKind.OBSERVATION entries. No external cron, no external deps.

Delivery is optional and provider-neutral: on each fire the scheduler
calls an INJECTED notifier callable and never imports a transport
itself, so notification delivery stays replaceable (webhook/ntfy/
future). With no notifier configured, reminders still fire and journal;
delivery outcome is recorded in the same entry so a failure is visible
rather than silent.

Missed fires are SKIPPED, never replayed: a reminder fires only in its
matching minute, and an occurrence the process was not running for is
missed rather than delivered late. Reminders are prompts, not durable
obligations, and replaying a stale batch on boot would surprise. (If
reminders ever gain obligation semantics, the alternative — fire on the
first tick after a missed window — is an explicit owner decision; see
issue #44.)

Schema (from ROADMAP.md): the schema exists; this is the runner.
"""

import json
import logging
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

from .envelope import Result, fail, ok
from .journal import Journal
from .model import JournalKind

# A notifier is any callable taking (title, body) and returning a
# Result (or None when no transport is available). The scheduler never
# learns what transport that is.
Notifier = Callable[[str, str], Result | None]

logger = logging.getLogger(__name__)


class Reminder(BaseModel):
    """A scheduled reminder."""

    id: str
    text: str
    cron_hour: int | None = None
    cron_minute: int | None = None
    cron_day: str | None = None  # "mon", "tue", etc. or None for daily
    enabled: bool = True
    last_fired: float | None = None
    created_at: float = Field(default_factory=time.time)


class Scheduler:
    """Simple reminder engine backed by a JSON file."""

    def __init__(
        self,
        path: Path,
        journal: Journal | None = None,
        notifier: Notifier | None = None,
    ) -> None:
        self.path = path
        self.journal = journal
        self.notifier = notifier
        self._reminders: dict[str, Reminder] = {}
        self._lock = threading.RLock()
        self._loaded = False
        self._thread: threading.Thread | None = None
        self._last_error: str | None = None  # visible state, not a silent death
        self._stop = threading.Event()

    def _ensure_loaded(self) -> None:
        with self._lock:
            if self._loaded:
                return
            if self.path.exists():
                try:
                    data = json.loads(self.path.read_text())
                    for item in data.get("reminders", []):
                        r = Reminder.model_validate(item)
                        self._reminders[r.id] = r
                except Exception as exc:
                    # Corrupt store: keep in-memory state empty, but the
                    # failure must be visible — especially because the
                    # next save would overwrite the damaged file.
                    logger.warning(
                        "scheduler: could not load %s (%s: %s) — starting "
                        "from an empty reminder set; the file will be "
                        "overwritten on the next save",
                        self.path,
                        type(exc).__name__,
                        exc,
                    )
                    self._last_error = (
                        f"reminders file unreadable: {type(exc).__name__}"
                    )
            self._loaded = True

    def _save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "reminders": [
                    r.model_dump(mode="json") for r in self._reminders.values()
                ]
            }
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(data, indent=2))
            os.replace(tmp, self.path)

    def add(self, reminder: Reminder) -> Result:
        with self._lock:
            self._ensure_loaded()
            self._reminders[reminder.id] = reminder
            self._save()
            return ok("healthy", data={"id": reminder.id})

    def remove(self, reminder_id: str) -> Result:
        with self._lock:
            self._ensure_loaded()
            if reminder_id not in self._reminders:
                return fail(
                    "not_found", warnings=[f"reminder '{reminder_id}' not found"]
                )
            del self._reminders[reminder_id]
            self._save()
            return ok("healthy", data={"id": reminder_id})

    def list_reminders(self) -> list[Reminder]:
        with self._lock:
            self._ensure_loaded()
            return list(self._reminders.values())

    def toggle(self, reminder_id: str, enabled: bool) -> Result:
        with self._lock:
            self._ensure_loaded()
            r = self._reminders.get(reminder_id)
            if r is None:
                return fail(
                    "not_found", warnings=[f"reminder '{reminder_id}' not found"]
                )
            r.enabled = enabled
            self._save()
            return ok("healthy", data={"id": reminder_id, "enabled": enabled})

    def _deliver(self, text: str) -> str | None:
        """Attempt delivery through the injected notifier.

        Returns a short, outcome string for the journal record, or
        None when no notifier is configured (the reminder is still
        journaled). Never raises: a delivery problem must not kill a tick
        or lose the reminder record.
        """
        if self.notifier is None:
            return None
        try:
            result = self.notifier("Project Worlds reminder", text)
        except Exception as exc:  # delivery is best-effort, never fatal
            return f"notification failed ({type(exc).__name__})"
        if result is None:
            return "notification not delivered (not_configured)"
        status = getattr(result, "status", "unknown")
        if getattr(result, "ok", False):
            return f"notification sent ({status})"
        return f"notification not delivered ({status})"

    def check_and_fire(self) -> list[str]:
        """Check all reminders and fire any that match the current time.

        Missed-fire policy (explicit): only the matching minute fires.
        An occurrence the process was not running for is skipped, not
        replayed on a later tick (see the module docstring).
        """
        with self._lock:
            self._ensure_loaded()
            now = datetime.now(UTC)
            fired = []
            for r in self._reminders.values():
                if not r.enabled:
                    continue
                if r.cron_hour is not None and now.hour != r.cron_hour:
                    continue
                if r.cron_minute is not None and now.minute != r.cron_minute:
                    continue
                if r.cron_day is not None:
                    day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
                    if day_names[now.weekday()] != r.cron_day:
                        continue
                # Don't fire twice in the same minute
                if r.last_fired and (time.time() - r.last_fired) < 60:
                    continue
                r.last_fired = time.time()
                fired.append(r.text)
                outcome = self._deliver(r.text)
                if self.journal:
                    summary = f"Reminder: {r.text}"
                    if outcome is not None:
                        summary = f"{summary} — {outcome}"
                    self.journal.record(
                        JournalKind.OBSERVATION,
                        summary,
                        source="scheduler",
                    )
            if fired:
                self._save()
        return fired

    def start(self) -> None:
        """Start the background scheduler thread."""

        def run():
            while not self._stop.is_set():
                try:
                    self.check_and_fire()
                except Exception as exc:  # never let one bad tick kill the thread
                    self._last_error = f"{type(exc).__name__}: {exc}"
                self._stop.wait(60)

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
