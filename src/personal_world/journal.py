"""Journal: one append-oriented event stream, many renderers.

V0 persistence: newline-delimited JSON in a volume-backed file. The file
is append-only; renderers (audit log, daily digest, story export) read it.
"""

from collections.abc import Iterator
from pathlib import Path

from .classification import Classification
from .model import JournalEvent, JournalKind, Provenance


class Journal:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: JournalEvent) -> JournalEvent:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")
        return event

    def record(
        self,
        kind: JournalKind,
        summary: str,
        source: str,
        classification: Classification = Classification.PRIVATE,
    ) -> JournalEvent:
        return self.append(
            JournalEvent(
                kind=kind,
                summary=summary,
                provenance=Provenance(source=source),
                classification=classification,
            )
        )

    def events(self) -> Iterator[JournalEvent]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield JournalEvent.model_validate_json(line)

    def recent(self, n: int = 20) -> list[JournalEvent]:
        return list(self.events())[-n:]

    def by_ts(self, ts) -> JournalEvent | None:
        """One entry by its UTC timestamp key, or None."""
        from datetime import datetime

        if isinstance(ts, datetime):
            key = ts
        else:
            try:
                key = datetime.fromisoformat(str(ts))
            except ValueError:
                return None
        for e in self.events():
            if e.ts == key:
                return e
        return None

    def supersede(
        self,
        target_ts,
        corrected_text: str,
        reason: str | None,
        proposed_by: str = "the Journal screen",
    ) -> tuple[JournalEvent, JournalEvent]:
        """Append-only correction: the record is never rewritten.

        Appends the corrected entry (supersedes=target, reason) AND an
        APPROVAL-kind audit event naming what changed, who proposed,
        what approved it, and when. The TARGET row itself is never
        mutated on disk; readers derive currency from superseded_by.

        Raises KeyError when the target does not exist, and ValueError
        when the target is already superseded (branching corrections
        are not supported — correct the current entry instead).
        """

        old = self.by_ts(target_ts)
        if old is None:
            raise KeyError(f"no journal entry at {target_ts}")
        # Append-only currency: an entry is superseded when any later
        # entry links to it. Branching corrections are rejected.
        for later in self.events():
            if later.supersedes == old.ts:
                raise ValueError(
                    f"entry at {target_ts} was already superseded — "
                    "correct the current entry instead"
                )
        current = JournalEvent(
            kind=old.kind,
            summary=corrected_text,
            provenance=Provenance(source=old.provenance.source, authority="reported"),
            classification=old.classification,
            supersedes=old.ts,
            supersede_reason=(reason or None),
        )
        self.append(current)
        # The APPROVAL audit event answers: what entry changed, old vs
        # new version, who proposed (the Journal screen), who approved
        # (the explicit human action), why (when supplied), mechanism,
        # when. IDs (timestamps) over content copies.
        audit = JournalEvent(
            kind=JournalKind.APPROVAL,
            summary=(
                f"journal correction approved: entry at {old.ts.isoformat()} "
                f"superseded by {current.ts.isoformat()} — proposed by "
                f"{proposed_by}, approved by the owner via the Journal "
                f"screen" + (f", reason: {reason}" if reason else "")
            ),
            provenance=Provenance(source="journal"),
            classification=old.classification,
        )
        self.append(audit)
        return current, audit

    def current_events(
        self, n: int = 20, exclude_kinds: frozenset[str] = frozenset()
    ) -> list[JournalEvent]:
        """The calm view: newest-last list of the latest n entries
        where each chain's CURRENT version only is shown. Superseded
        entries are filtered out; a corrected entry renders in its
        place with its own (later) timestamp. ``exclude_kinds`` drops
        those kinds BEFORE the last n are taken, so a burst of automatic
        entries can't push a person's notes out of the window."""
        superseded_keys = {
            e.supersedes for e in self.events() if e.supersedes is not None
        }
        out = []
        for e in self.events():
            if e.ts in superseded_keys:
                continue
            if exclude_kinds and str(getattr(e.kind, "value", e.kind)) in exclude_kinds:
                continue
            out.append(e)
        return out[-n:]

    def history_of(self, entry: JournalEvent) -> list[JournalEvent]:
        """Full linear supersession chain for one entry, oldest
        first: the entry itself back to the original it replaced
        (transitively), plus any later correction of it."""
        chain: list[JournalEvent] = [entry]
        # Walk back through supersedes links.
        cur = entry
        back = 0
        while cur.supersedes is not None and back < 100:
            prev = self.by_ts(cur.supersedes)
            if prev is None:
                break
            chain.insert(0, prev)
            cur = prev
            back += 1
        # Include any correction that replaced THIS entry later.
        evs = list(self.events())
        for cand in evs:
            if cand.supersedes == entry.ts and cand not in chain:
                chain.append(cand)
        return chain

    def for_story(
        self,
        include_private: bool = False,
        kinds: set[JournalKind] | None = None,
    ) -> list[JournalEvent]:
        """Story renderings use disclosure rules: PRIVATE events are
        excluded unless explicitly included; existence in the journal
        never automatically grants story inclusion."""
        out = []
        for e in self.events():
            if e.classification == Classification.PRIVATE and not include_private:
                continue
            if kinds is not None and e.kind not in kinds:
                continue
            out.append(e)
        return out


class AuditRenderer:
    """Technical audit log: provenance on every line."""

    def render(self, journal: Journal) -> str:
        lines = []
        for e in journal.events():
            lines.append(
                f"{e.ts.isoformat()} {e.kind.value} [{e.provenance.source}] "
                f"({e.classification.value}) {e.summary}"
            )
        return "\n".join(lines)


class StoryRenderer:
    """Human-readable journal rendering with disclosure/redaction."""

    NARRATIVE_KINDS = {
        JournalKind.OBSERVATION,
        JournalKind.DISCOVERY,
        JournalKind.HEALTH,
        JournalKind.RECONCILIATION,
        JournalKind.APPROVAL,
    }

    def render(self, journal: Journal, include_private: bool = False) -> str:
        events = journal.for_story(
            include_private=include_private, kinds=self.NARRATIVE_KINDS
        )
        lines = []
        for e in events:
            marker = "" if e.classification != Classification.PRIVATE else "(private) "
            lines.append(f"- {marker}{e.summary}")
        return "\n".join(lines) or "Nothing worth telling yet."
