"""What's live: /healthz reports the commit the running build came from.

publish-image.yml passes the validated main SHA to the image build as
PW_COMMIT (the same SHA the org.opencontainers.image.revision label
carries); Project Home reads the short form off /healthz to compare the
live Worlds against main. The route is public and the repo is public, so
the commit is safe to expose — but only a hex SHA is ever echoed back,
and nothing else about the build leaks.
"""
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

FULL_SHA = "0eb59a2f4c1d3e5a6b7c8d9e0f1a2b3c4d5e6f70"

BASELINE_KEYS = {"ok", "auth_configured", "setup_needed", "dev_bypass"}


def _healthz(tmp_path, monkeypatch, commit):
    """Boot an app with PW_COMMIT set to `commit` (or unset) and read
    /healthz with no credentials — the route is public."""
    from personal_world.api import create_app
    monkeypatch.setenv("PW_API_TOKEN", "healthz-commit-token")
    if commit is None:
        monkeypatch.delenv("PW_COMMIT", raising=False)
    else:
        monkeypatch.setenv("PW_COMMIT", commit)
    return TestClient(create_app(tmp_path, tmp_path)).get("/healthz")


class TestHealthzCommit:
    def test_full_sha_reports_first_seven(self, tmp_path, monkeypatch):
        r = _healthz(tmp_path, monkeypatch, FULL_SHA)
        assert r.status_code == 200, r.text
        assert r.json()["commit"] == FULL_SHA[:7]

    def test_already_short_sha_is_kept(self, tmp_path, monkeypatch):
        r = _healthz(tmp_path, monkeypatch, FULL_SHA[:7])
        assert r.json()["commit"] == FULL_SHA[:7]

    def test_unset_is_null(self, tmp_path, monkeypatch):
        assert _healthz(tmp_path, monkeypatch, None).json()["commit"] is None

    def test_empty_is_null(self, tmp_path, monkeypatch):
        assert _healthz(tmp_path, monkeypatch, "").json()["commit"] is None

    def test_garbage_is_null(self, tmp_path, monkeypatch):
        for bogus in ("garbage", "not-a-sha-0123456789", "  ", "zzzzzzz"):
            r = _healthz(tmp_path, monkeypatch, bogus)
            assert r.json()["commit"] is None, bogus

    def test_too_short_hex_is_null(self, tmp_path, monkeypatch):
        # A 6-char hex string is not an abbreviated commit.
        assert _healthz(tmp_path, monkeypatch, "0eb59a").json()["commit"] is None

    def test_local_build_default_is_null(self, tmp_path, monkeypatch):
        """The Dockerfile's ARG default is empty: a local build reports
        null rather than a fabricated commit."""
        assert _healthz(tmp_path, monkeypatch, "").json()["commit"] is None

    def test_existing_fields_unchanged_and_nothing_else_added(
        self, tmp_path, monkeypatch
    ):
        payload = _healthz(tmp_path, monkeypatch, FULL_SHA).json()
        assert payload["ok"] is True
        assert payload["auth_configured"] is True
        assert payload["setup_needed"] is True  # fresh data dir
        assert payload["dev_bypass"] is False
        assert set(payload) == BASELINE_KEYS | {"commit"}
