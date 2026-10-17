"""The calm view can leave automatic kinds out before taking the last n,
so an import's burst of settings_change entries can't bury a person's notes
(UAT 2026-09-27: 226 of them hid three notes)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.journal import Journal  # noqa: E402
from personal_world.model import JournalKind  # noqa: E402


def test_hidden_kinds_are_dropped_before_the_window(tmp_path):
    j = Journal(tmp_path / "journal.ndjson")
    j.record(JournalKind.OBSERVATION, "note one", source="user")
    j.record(JournalKind.OBSERVATION, "note two", source="user")
    for i in range(30):
        j.record(JournalKind.SETTINGS_CHANGE, f"record updated {i}", source="import")
    # Without hiding, the last 10 are all automatic.
    assert {e.kind for e in j.current_events(10)} == {JournalKind.SETTINGS_CHANGE}
    # Hidden first, the notes are the window.
    kept = j.current_events(10, exclude_kinds=frozenset({"settings_change"}))
    assert [e.summary for e in kept] == ["note one", "note two"]
