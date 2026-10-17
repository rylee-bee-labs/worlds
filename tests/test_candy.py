import json
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.app import build_registry  # noqa: E402
from personal_world.providers.adapters import CandyDispenser  # noqa: E402
from personal_world.providers.registry import Registry  # noqa: E402
from personal_world.status import Status  # noqa: E402
from personal_world.world import World  # noqa: E402


class FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status = status
        self._body = body

    def read(self):
        return json.dumps(self._body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestCandyDispenserHealth:
    def test_http_200_status_ok_returns_healthy(self, monkeypatch):
        dispenser = CandyDispenser("http://candy-dispenser:5126")

        def mock_urlopen(url, timeout=None):
            return FakeResponse(200, {"status": "ok"})

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        r = dispenser.health()
        assert r.ok
        assert r.status == Status.HEALTHY.value

    def test_http_200_status_not_ok_returns_needs_attention(self, monkeypatch):
        dispenser = CandyDispenser("http://candy-dispenser:5126")

        def mock_urlopen(url, timeout=None):
            return FakeResponse(200, {"status": "degraded"})

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        r = dispenser.health()
        assert not r.ok
        assert r.status == Status.NEEDS_ATTENTION.value
        assert r.data == {"service_status": "degraded"}

    def test_http_non_200_returns_needs_attention(self, monkeypatch):
        dispenser = CandyDispenser("http://candy-dispenser:5126")

        def mock_urlopen(url, timeout=None):
            return FakeResponse(500, {"error": "boom"})

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        r = dispenser.health()
        assert not r.ok
        assert r.status == Status.NEEDS_ATTENTION.value

    def test_connection_refused_returns_unavailable(self, monkeypatch):
        dispenser = CandyDispenser("http://candy-dispenser:5126")

        def mock_urlopen(url, timeout=None):
            raise ConnectionRefusedError("Connection refused")

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        r = dispenser.health()
        assert not r.ok
        assert r.status == Status.UNAVAILABLE.value


class TestCandyDispenserObserve:
    def test_observe_returns_minimal_fields_only(self, monkeypatch):
        """Deliberately EXCLUDE mam_indexer_name/ebook_download_client_name/phase_c."""
        dispenser = CandyDispenser("http://candy-dispenser:5126")
        full_payload = {
            "status": "ok",
            "notifications_sent": 5,
            "errors": 0,
            "grabs_accepted": 12,
            "grabs_refused": 2,
            "sources": ["reddit", "news"],
            "seen_count": 142,
            "mam_indexer_name": "private tracker",
            "ebook_download_client_name": "calibre",
            "phase_c": "secret internal detail",
        }

        def mock_urlopen(url, timeout=None):
            return FakeResponse(200, full_payload)

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        r = dispenser.observe()
        assert r.ok
        assert r.data["reachable"] is True
        assert r.data["service_status"] == "ok"
        assert r.data["notifications_sent"] == 5
        assert r.data["errors"] == 0
        assert r.data["grabs_accepted"] == 12
        assert r.data["grabs_refused"] == 2
        assert r.data["sources"] == ["reddit", "news"]
        assert r.data["seen_count"] == 142
        # Explicitly verify these are NOT included
        assert "mam_indexer_name" not in r.data
        assert "ebook_download_client_name" not in r.data
        assert "phase_c" not in r.data

    def test_observe_connection_error_returns_unreachable(self, monkeypatch):
        dispenser = CandyDispenser("http://candy-dispenser:5126")

        def mock_urlopen(url, timeout=None):
            raise urllib.error.URLError("no route")

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        r = dispenser.observe()
        assert not r.ok
        assert r.status == Status.UNAVAILABLE.value
        assert r.data["reachable"] is False

    def test_observe_status_not_ok_returns_needs_attention(self, monkeypatch):
        dispenser = CandyDispenser("http://candy-dispenser:5126")

        def mock_urlopen(url, timeout=None):
            return FakeResponse(200, {
                "status": "error",
                "notifications_sent": 0,
                "errors": 3,
                "grabs_accepted": 0,
                "grabs_refused": 0,
                "sources": [],
                "seen_count": 0,
            })

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        r = dispenser.observe()
        assert not r.ok
        assert r.status == Status.NEEDS_ATTENTION.value
        assert r.data["reachable"] is True
        assert r.data["service_status"] == "error"


class TestCandyConfigWiring:
    def test_build_registry_registers_candy_under_discovery(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "connections.json").write_text(json.dumps({
            "connections": [
                {
                    "type": "candy",
                    "name": "candy-dispenser",
                    "capability": "discovery",
                    "base_url": "http://candy-dispenser:5126",
                }
            ]
        }))

        w = World()
        reg = Registry()
        reg = build_registry(w, reg, config_dir)

        # Verify registered under discovery capability
        p = reg.provider_for("discovery")
        assert p is not None
        assert p.name == "candy-dispenser"
        assert p.capability == "discovery"

        # Verify impl is CandyDispenser
        impl = reg.impl("candy-dispenser")
        assert isinstance(impl, CandyDispenser)
        assert impl.base_url == "http://candy-dispenser:5126"
