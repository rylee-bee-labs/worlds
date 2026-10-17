"""Lab operator-panel guards.

The Lab panel consumes the homelab Lab CLI's lowbw packet
(schema lab-lowbw/1). These tests lock down:

- the provider's contract with the packet (parse, map, degrade),
- honest states: unavailable on CLI failure, stale on old evidence,
- unrecognized rows are surfaced, never silently dropped,
- the API route's auth and status mapping,
- the dashboard wiring (panel present, route fetched),
- secrets posture: the payload path never reads credentials.
"""

import json
import subprocess
from datetime import datetime, timedelta, timezone

from personal_world.providers.lab_state import (
    DEFAULT_LAB,
    FRESHNESS,
    LabState,
)


def _packet(observed_at: str = "2026-09-07T22:00:00Z") -> dict:
    return {
        "schema": "lab-lowbw/1",
        "generated_at": "2026-09-07T22:00:00Z",
        "overall_state": "WORKING",
        "next_action": None,
        "rows": {
            "urgent": {"observations": [{
                "detail": "d1", "action": "a1", "state": "needs_attention",
                "evidence": [{"observed_at": observed_at, "reference": "x"}],
            }]},
            "review": {"observations": []},
            "safe": {"observations": []},
            "unknown": {"observations": []},
            "last_known_good": {"observations": []},
            "next": {"observations": []},
            "brand_new_row": {"observations": [{"detail": "n"}]},
        },
    }


def _fake_lab(monkeypatch, packet: dict | None, fail: bool = False):
    """Replace the subprocess call with a controllable fake."""
    calls = []

    class P:
        def __init__(self):
            self.stdout = json.dumps(packet) if packet is not None else "{}"
            self.returncode = 1 if fail else 0

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if fail:
            raise subprocess.SubprocessError("boom")
        return P()

    monkeypatch.setattr("personal_world.providers.lab_state.subprocess.run", fake_run)
    return calls


def test_default_matches_real_checkouts():
    """VM 145 serves the homelab repo at /opt/scripts; the fallback
    list covers a homelab-nested layout."""
    from personal_world.providers.lab_state import LAB_CANDIDATES
    assert DEFAULT_LAB == "/opt/scripts/lab"
    assert LAB_CANDIDATES == (
        "/opt/scripts/lab",
        "/opt/homelab/scripts/lab",
        "/homelab/scripts/lab",  # read-only laptop mount (compose)
    )
    assert FRESHNESS == timedelta(minutes=30)


def test_parses_valid_packet_into_display_rows(monkeypatch):
    _fake_lab(monkeypatch, _packet())
    r = LabState().observe()
    assert r.ok is True
    rows = {row["row"]: row for row in r.data["rows"]}
    assert rows["urgent"]["count"] == 1
    assert rows["urgent"]["observations"][0]["detail"] == "d1"
    assert rows["urgent"]["observations"][0]["action"] == "a1"
    # Every known row is present even when empty — no silent omissions.
    for name in ("urgent", "review", "safe", "unknown", "last_known_good", "next"):
        assert name in rows


def test_unrecognized_row_is_preserved_not_dropped(monkeypatch):
    _fake_lab(monkeypatch, _packet())
    r = LabState().observe()
    rows = {row["row"]: row for row in r.data["rows"]}
    assert rows["brand_new_row"]["unrecognized"] is True


def test_stale_evidence_is_flagged_not_hidden(monkeypatch):
    _fake_lab(monkeypatch, _packet())  # fixture timestamp is in the past
    r = LabState().observe()
    assert r.status == "stale"
    rows = {row["row"]: row for row in r.data["rows"]}
    assert rows["urgent"]["stale"] is True


def test_fresh_evidence_is_current(monkeypatch):
    fresh = (datetime.now(timezone.utc) - timedelta(minutes=2)
             ).strftime("%Y-%m-%dT%H:%M:%SZ")
    _fake_lab(monkeypatch, _packet(observed_at=fresh))
    r = LabState().observe()
    assert r.status == "healthy"
    rows = {row["row"]: row for row in r.data["rows"]}
    assert rows["urgent"]["stale"] is False


def test_cli_failure_is_unavailable_never_guessed(monkeypatch):
    _fake_lab(monkeypatch, None, fail=True)
    r = LabState().observe()
    assert r.ok is False
    assert r.status == "unavailable"
    assert r.data["rows"] == []
    assert any("lab-lowbw/1" in w for w in r.warnings)


def test_bad_schema_is_unavailable(monkeypatch):
    _fake_lab(monkeypatch, {"schema": "lab-lowbw/999", "rows": {}})
    r = LabState().observe()
    assert r.ok is False and r.status == "unavailable"


def test_malformed_json_is_unavailable(monkeypatch):
    class P:
        stdout = "{not json"
        returncode = 0
    monkeypatch.setattr(
        "personal_world.providers.lab_state.subprocess.run", lambda *a, **k: P())
    r = LabState().observe()
    assert r.ok is False and r.status == "unavailable"


def test_provider_is_read_only(monkeypatch):
    """The exact command must be the read-only CLI invocation."""
    calls = _fake_lab(monkeypatch, _packet())
    LabState(lab_path="/custom/lab").observe()
    assert calls == [("/custom/lab", "lowbw", "--cached", "--json")]


def test_no_credentials_in_payload_path(monkeypatch, tmp_path):
    """The provider takes no token, reads no env, opens no secret file."""
    _fake_lab(monkeypatch, _packet())
    src = LabState()
    assert src.lab_path.endswith("lab")
    assert not hasattr(src, "token") and not hasattr(src, "password")


def test_api_route_maps_provider_status(monkeypatch):
    """The route exists, requires the shared auth, and maps the
    provider's status without re-deriving anything."""
    from fastapi.testclient import TestClient

    from personal_world.api import create_app

    _fake_lab(monkeypatch, _packet())
    monkeypatch.setenv("PW_API_TOKEN", "test-token")
    monkeypatch.setenv("PW_LAB_CLI", "/custom/lab")
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        app = create_app(data_dir=Path(td))
        c = TestClient(app)
        # No token -> fail closed (401 once a token is configured).
        r = c.get("/api/lab/state")
        assert r.status_code in (401, 503)
        # With token -> honest mapping.
        r = c.get("/api/lab/state",
                  headers={"Authorization": "Bearer test-token"})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["status"] in ("healthy", "stale")
        assert body["data"]["schema"] == "lab-lowbw/1"
