"""Session store durability: the browser-session credential store is
written atomically with restrictive permissions, and an unreadable
sessions file is never silently swallowed — it is logged."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.auth import AuthManager  # noqa: E402


def _manager(tmp_path):
    return AuthManager(tmp_path, tmp_path)


class TestSessionsFileDurability:
    def test_saved_file_mode_0600(self, tmp_path):
        auth = _manager(tmp_path)
        auth.sessions.create("primary", "local")
        path = tmp_path / "sessions.json"
        assert path.is_file()
        assert path.stat().st_mode & 0o777 == 0o600

    def test_atomic_save_leaves_no_tmp_file(self, tmp_path):
        auth = _manager(tmp_path)
        auth.sessions.create("primary", "local")
        assert not (tmp_path / "sessions.json.tmp").exists()

    def test_reload_roundtrip(self, tmp_path):
        auth = _manager(tmp_path)
        session = auth.sessions.create("primary", "local")
        auth2 = AuthManager(tmp_path, tmp_path)
        assert auth2.sessions.get(session.id) is not None

    def test_corrupt_file_no_crash_and_logged(self, tmp_path, caplog):
        (tmp_path / "sessions.json").write_text("{not json at all")
        with caplog.at_level("WARNING", logger="personal_world.auth"):
            auth = _manager(tmp_path)
        assert auth.sessions._sessions == {}
        assert any(
            "sessions file unreadable" in record.message for record in caplog.records
        )

    def test_corrupt_session_entries_logged_not_crash(self, tmp_path, caplog):
        (tmp_path / "sessions.json").write_text(
            json.dumps({"s1": {"id": "s1", "unknown_key": True}})
        )
        with caplog.at_level("WARNING", logger="personal_world.auth"):
            auth = _manager(tmp_path)
        assert auth.sessions._sessions == {}
        assert caplog.records
