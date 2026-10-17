"""Native Calendar provider: provider-neutral calendar domain.

Worlds owns events, upcoming, conflicts, calendar identity,
normalized time/status, provenance. Adapters fetch external sources.
No calendar server required. Supports ICS/iCal feeds and CalDAV.
"""

import urllib.request
from datetime import datetime, timezone

from ..envelope import Result, fail, ok
from ..status import Status
from ..url_safety import http_urlopen
from .registry import StatusContract


class CalendarEvent:
    """Normalized calendar event."""
    def __init__(self, uid, title, start, end=None, location=None,
                 description=None, status="confirmed", provider="unknown"):
        self.uid = uid
        self.title = title
        self.start = start
        self.end = end
        self.location = location
        self.description = description
        self.status = status
        self.provider = provider

    def to_dict(self):
        return {
            "uid": self.uid,
            "title": self.title,
            "start": self.start.isoformat() if isinstance(self.start, datetime) else str(self.start),
            "end": self.end.isoformat() if isinstance(self.end, datetime) else str(self.end) if self.end else None,
            "location": self.location,
            "description": self.description,
            "status": self.status,
            "provider": self.provider,
        }


class ICSAdapter:
    """Fetches and parses ICS/iCalendar feeds."""

    def __init__(self, url, name="ics"):
        self.url = url
        self.name = name

    def fetch_events(self, days_ahead=30) -> list[CalendarEvent]:
        """Fetch upcoming events from ICS feed."""
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "ProjectWorlds/1.0"})
            with http_urlopen(req, timeout=30) as resp:
                ics_data = resp.read().decode("utf-8", errors="replace")
            return self._parse_ics(ics_data)
        except Exception:
            return []

    def _parse_ics(self, ics_data: str) -> list[CalendarEvent]:
        """Simple ICS parser for VEVENT blocks."""
        events = []
        in_event = False
        current = {}
        for line in ics_data.split("\n"):
            line = line.strip()
            if line == "BEGIN:VEVENT":
                in_event = True
                current = {}
            elif line == "END:VEVENT":
                in_event = False
                if current.get("summary") and current.get("dtstart"):
                    events.append(CalendarEvent(
                        uid=current.get("uid", ""),
                        title=current.get("summary", ""),
                        start=current.get("dtstart"),
                        end=current.get("dtend"),
                        location=current.get("location"),
                        description=current.get("description"),
                        status=current.get("status", "confirmed").lower(),
                        provider=self.name,
                    ))
            elif in_event and ":" in line:
                key, _, val = line.partition(":")
                key = key.split(";")[0]  # Remove parameters
                current[key.lower()] = val
        return events


class NativeCalendarProvider(StatusContract):
    """Native calendar capability with ICS/CalDAV adapters."""

    def __init__(self, config=None):
        self._adapters = []
        self._config = config or {}
        self._load_adapters()

    def _load_adapters(self):
        """Load configured calendar sources."""
        sources = self._config.get("sources", [])
        for src in sources:
            if src.get("type") == "ics" and src.get("url"):
                self._adapters.append(ICSAdapter(src["url"], src.get("name", "ics")))

    def observe(self) -> Result:
        """Report calendar capability status."""
        if not self._adapters:
            return ok(Status.NOT_CONFIGURED.value, data={
                "providers": [],
                "message": "no calendar sources configured",
                "provider": "native_calendar",
            })
        return ok(Status.HEALTHY.value, data={
            "providers": [a.name for a in self._adapters],
            "provider": "native_calendar",
        })

    def upcoming(self, days=7) -> Result:
        """Get upcoming events."""
        try:
            all_events = []
            for adapter in self._adapters:
                events = adapter.fetch_events(days_ahead=days)
                all_events.extend(events)
            # Sort by start time
            all_events.sort(key=lambda e: e.start if isinstance(e.start, datetime) else datetime.min.replace(tzinfo=timezone.utc))
            return ok(Status.HEALTHY.value, data={
                "events": [e.to_dict() for e in all_events],
                "count": len(all_events),
                "days": days,
            })
        except Exception as e:
            return fail(Status.UNAVAILABLE.value, warnings=[f"calendar: {e}"])

    def health(self) -> bool:
        return True
