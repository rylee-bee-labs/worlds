"""Web Push notifications: the push hub (push.py) and its API doors.

Proves the properties docs/NOTIFICATIONS.md promises:

* devices are per person, upserted by endpoint, listed WITHOUT their
  credentials (endpoints and browser keys never appear in a response);
* every notification is stored before anything is pushed;
* tiers, sources and quiet hours decide what pushes — "quiet by
  default": when_ready is history-only unless the person turns it on;
* the publishing door (POST /api/notify) honors the auth matrix (person
  self, agent with the notify scope, manage_people for ``to``), rate
  limits 30 a minute with a plain 429, and is idempotent on dedupe_key;
* a dead device (404/410) is pruned; any other failure keeps the device
  and records short plain words; nothing ever crashes a request;
* with no VAPID key in the environment push is not_configured and every
  other door keeps working;
* private key material appears in no response and no log line.

pywebpush's one outbound call is replaced throughout: no network.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient

from personal_world import push as push_mod

TOKEN = "pushtesttoken-1a2b"  # pw-safety: synthetic
AUTH = {"Authorization": f"Bearer {TOKEN}"}
STEP_UP = {**AUTH, "X-PW-StepUp": "1"}

#: Endpoints only ever seen by the fake transport: the safety scan in
#: test_public_safety wants no real push services in tracked files.
ENDPOINT_A = "https://push.example.invalid/v1/aaaa"
ENDPOINT_B = "https://push.example.invalid/v1/bbbb"
ENDPOINT_C = "https://push.example.invalid/v1/cccc"

SUB_A = {"endpoint": ENDPOINT_A, "keys": {"p256dh": "BKfakepubkeyA", "auth": "fakeauthA"}}
SUB_B = {"endpoint": ENDPOINT_B, "keys": {"p256dh": "BKfakepubkeyB", "auth": "fakeauthB"}}
SUB_C = {"endpoint": ENDPOINT_C, "keys": {"p256dh": "BKfakepubkeyC", "auth": "fakeauthC"}}

QUIET_MAILTO = "mailto:kit@example.invalid"


def _wall(y, m, d, hh, mm):
    """An epoch at local wall-clock time (quiet hours read the wall clock)."""
    return datetime(y, m, d, hh, mm).timestamp()


NOT_QUIET = _wall(2026, 9, 22, 15, 0)  # 15:00: outside the default window
QUIET = _wall(2026, 9, 22, 23, 0)  # 23:00: inside 21:00 → 08:00


@pytest.fixture(scope="module")
def vapid_pair():
    """A real key pair, generated at runtime (never a literal in a file)."""
    return push_mod.generate_keypair()


class FakePushService:
    """Stands in for pywebpush.webpush: records calls, optionally fails."""

    def __init__(self, error=None):
        self.calls: list[dict] = []
        self.error = error

    def __call__(self, subscription_info, data=None, **kwargs):
        self.calls.append(
            {"subscription_info": subscription_info, "data": data, **kwargs}
        )
        if self.error is not None:
            raise self.error
        return "sent"


def _service_error(status_code):
    """A real WebPushException carrying a push-service status code."""

    class _Response:
        def __init__(self, code):
            self.status_code = code

    return push_mod.WebPushException("service said no", response=_Response(status_code))


class _Clock:
    def __init__(self, start=NOT_QUIET):
        self.t = start

    def __call__(self):
        return self.t


@pytest.fixture
def hub(tmp_path, monkeypatch, vapid_pair):
    """A configured hub on a fake clock, with the wire replaced."""
    monkeypatch.delenv(push_mod.PRIVATE_KEY_ENV, raising=False)
    monkeypatch.delenv(push_mod.SUBJECT_ENV, raising=False)
    monkeypatch.setenv(push_mod.PRIVATE_KEY_ENV, vapid_pair["private_pem"])
    monkeypatch.setenv(push_mod.SUBJECT_ENV, QUIET_MAILTO)
    fake = FakePushService()
    monkeypatch.setattr(push_mod, "_webpush", fake)
    h = push_mod.PushHub(tmp_path)
    h.now = _Clock()
    h._fake = fake  # tests read calls off the hub
    return h


# ── VAPID keys ──────────────────────────────────────────────────────


class TestKeys:
    def test_keypair_public_is_derivable_from_private(self, vapid_pair):
        assert (
            push_mod.public_key_for(vapid_pair["private_pem"]) == vapid_pair["public_key"]
        )

    def test_load_vapid_accepts_pem_and_base64url(self, vapid_pair):
        import base64

        assert push_mod.load_vapid(vapid_pair["private_pem"]) is not None
        from cryptography.hazmat.primitives import serialization

        pem_key = serialization.load_pem_private_key(
            vapid_pair["private_pem"].encode(), password=None
        )
        raw = base64.urlsafe_b64encode(
            pem_key.private_numbers().private_value.to_bytes(32, "big")
        ).decode("ascii")
        assert push_mod.load_vapid(raw) is not None

    def test_garbage_key_refused_without_repeating_it(self):
        secret_value = "not-a-key-at-all"  # pw-safety: synthetic
        with pytest.raises(ValueError) as exc:
            push_mod.load_vapid(secret_value)
        assert secret_value not in str(exc.value)
        assert "unreadable" in str(exc.value)

    def test_subject_must_be_mailto_or_https(self):
        assert push_mod.subject_ok("mailto:kit@example.invalid")
        assert push_mod.subject_ok("https://worlds.example.invalid")
        assert not push_mod.subject_ok("ftp://somewhere")
        assert not push_mod.subject_ok("")


# ── small pure functions ────────────────────────────────────────────


class TestLinkAndQuiet:
    @pytest.mark.parametrize(
        "link",
        [
            "https://elsewhere.example/x",
            "http://elsewhere.example/x",
            "//elsewhere.example/x",
            "javascript:alert(1)",
            "/ok\\backslash",
            "/with\nnewline",
        ],
    )
    def test_offsite_links_refused(self, link):
        with pytest.raises(ValueError):
            push_mod.valid_same_origin_link(link)

    def test_paths_and_empty_pass(self):
        assert push_mod.valid_same_origin_link("/today") == "/today"
        assert push_mod.valid_same_origin_link("") is None
        assert push_mod.valid_same_origin_link(None) is None

    def test_quiet_hours_wrap_midnight(self):
        prefs = push_mod.DEFAULT_PREFS
        assert push_mod.in_quiet_hours(prefs, QUIET)
        assert not push_mod.in_quiet_hours(prefs, NOT_QUIET)
        off = json.loads(json.dumps(prefs))
        off["quiet_hours"]["on"] = False
        assert not push_mod.in_quiet_hours(off, QUIET)
        zero = json.loads(json.dumps(prefs))
        zero["quiet_hours"].update({"start": "08:00", "end": "08:00"})
        assert not push_mod.in_quiet_hours(zero, NOT_QUIET)

    def test_quiet_hours_honour_named_zone(self):
        prefs = json.loads(json.dumps(push_mod.DEFAULT_PREFS))
        prefs["quiet_hours"]["tz"] = "UTC"
        utc_late_night = datetime(2026, 9, 22, 23, 30, tzinfo=_utc()).timestamp()
        assert push_mod.in_quiet_hours(prefs, utc_late_night)


def _utc():
    from zoneinfo import ZoneInfo

    return ZoneInfo("UTC")


# ── subscriptions ───────────────────────────────────────────────────


class TestSubscriptions:
    def test_upsert_is_by_endpoint_not_by_call(self, hub, tmp_path):
        first_id, created = hub.add_subscription("sam", SUB_A, "iPhone")
        assert created
        second_id, re_created = hub.add_subscription("sam", SUB_A, "iPhone")
        assert second_id == first_id
        assert not re_created
        assert len(hub.list_subscriptions("sam")) == 1

    def test_list_never_shows_endpoint_or_keys(self, hub):
        hub.add_subscription("sam", SUB_A, "iPhone 17")
        rows = hub.list_subscriptions("sam")
        assert rows[0]["device_label"] == "iPhone 17"
        assert set(rows[0]) == {"id", "device_label", "created_at", "last_ok_at", "last_error"}
        blob = json.dumps(rows)
        assert ENDPOINT_A not in blob
        assert "p256dh" not in blob and "fakeauthA" not in blob

    def test_http_endpoint_and_missing_keys_refused(self, hub):
        with pytest.raises(ValueError):
            hub.add_subscription("sam", {"endpoint": "http://x.invalid/a", "keys": {}}, "")
        with pytest.raises(ValueError):
            hub.add_subscription("sam", {"endpoint": ENDPOINT_A, "keys": {"auth": "only"}}, "")

    def test_devices_are_per_person(self, hub, tmp_path):
        # multi mode: each person's devices live under their own space
        multi = push_mod.PushHub(tmp_path, mode="multi")
        multi.now = hub.now
        multi.add_subscription("sam", SUB_A, "sam phone")
        multi.add_subscription("jo", SUB_B, "jo phone")
        assert [r["device_label"] for r in multi.list_subscriptions("sam")] == ["sam phone"]
        assert [r["device_label"] for r in multi.list_subscriptions("jo")] == ["jo phone"]
        assert multi.remove_subscription("sam", multi.list_subscriptions("sam")[0]["id"])
        assert multi.list_subscriptions("jo")  # untouched


# ── prefs ───────────────────────────────────────────────────────────


class TestPrefs:
    def test_defaults_are_quiet_by_default(self, hub):
        prefs = hub.get_prefs("sam")
        assert prefs["tiers"] == {"good_news": True, "update": False, "when_ready": False}
        assert prefs["quiet_hours"] == {
            "on": True,
            "start": "21:00",
            "end": "08:00",
            "tz": None,
        }

    def test_put_merges_and_persists(self, hub, tmp_path):
        saved = hub.put_prefs("sam", {"tiers": {"when_ready": True}})
        assert saved["tiers"]["when_ready"] is True
        assert saved["tiers"]["good_news"] is True  # untouched default
        assert hub.get_prefs("sam")["tiers"]["when_ready"] is True

    @pytest.mark.parametrize(
        "bad",
        [
            {"tiers": {"nope": True}},
            {"tiers": {"update": "yes"}},
            {"sources": {"a" * 60: True}},
            {"quiet_hours": {"start": "11pm"}},
            {"quiet_hours": {"sideways": True}},
            {"quiet_hours": {"tz": "Mars/Olympus"}},
            {"quiet_hours": {"on": "off"}},
        ],
    )
    def test_bad_prefs_refused_in_plain_words(self, hub, bad):
        with pytest.raises(push_mod.PrefsError):
            hub.put_prefs("sam", bad)


# ── the publish path ────────────────────────────────────────────────


class TestNotify:
    def test_stores_first_then_pushes(self, hub):
        hub.add_subscription("sam", SUB_A, "phone")
        out = hub.notify("sam", tier="good_news", source="vefr", title="Tomatoes", body="ripened")
        assert out["state"] == "delivered"
        assert out["delivered"] == 1
        assert hub._fake.calls[0]["subscription_info"]["endpoint"] == ENDPOINT_A
        listing = hub.list_notifications("sam", unread=False, limit=10)
        assert listing[0]["id"] == out["id"]
        assert listing[0]["tier_words"] == "GOOD NEWS"

    def test_payload_shape_ttl_and_urgency(self, hub):
        hub.add_subscription("sam", SUB_A, "phone")
        hub.notify("sam", tier="good_news", source="vefr", title="Hi", body="There", link="/today")
        call = hub._fake.calls[0]
        payload = json.loads(call["data"])
        assert set(payload) == {
            "title",
            "body",
            "tier",
            "tier_words",
            "link",
            "id",
            "source",
            "sender",
        }
        assert payload["tier_words"] == "GOOD NEWS"
        assert call["ttl"] == 86400
        assert call["headers"] == {"Urgency": "normal"}
        assert call["vapid_claims"] == {"sub": QUIET_MAILTO}
        hub._fake.calls.clear()
        hub.put_prefs("sam", {**hub.get_prefs("sam"), "tiers": {"when_ready": True}})
        hub.notify("sam", tier="when_ready", source="candy", title="When ready", body="…")
        assert hub._fake.calls[0]["headers"] == {"Urgency": "low"}

    def test_when_ready_default_never_pushes(self, hub):
        hub.add_subscription("sam", SUB_A, "phone")
        out = hub.notify("sam", tier="when_ready", source="candy", title="Later", body="ok")
        assert out["state"] == "history_only"
        assert out["deferred"] is True
        assert hub._fake.calls == []
        assert hub.list_notifications("sam", unread=False, limit=5)[0]["title"] == "Later"

    def test_tier_and_source_off_history_only(self, hub):
        hub.add_subscription("sam", SUB_A, "phone")
        hub.put_prefs(
            "sam",
            {"tiers": {"good_news": False, "update": True}, "sources": {"vefr": False}},
        )
        assert hub.notify("sam", tier="good_news", source="cli", title="t", body="b")[
            "state"
        ] == "history_only"
        assert hub.notify("sam", tier="update", source="vefr", title="t", body="b")[
            "state"
        ] == "history_only"
        assert hub.notify("sam", tier="update", source="cli", title="t", body="b")[
            "state"
        ] == "delivered"
        assert hub._fake.calls and len(hub._fake.calls) == 1

    def test_quiet_hours_store_without_pushing(self, hub):
        hub.add_subscription("sam", SUB_A, "phone")
        hub.now.t = QUIET
        out = hub.notify("sam", tier="good_news", source="vefr", title="Night", body="…")
        assert out["state"] == "deferred" and out["deferred"] is True
        assert hub._fake.calls == []

    def test_summary_goes_out_when_quiet_hours_end(self, hub):
        hub.add_subscription("sam", SUB_A, "phone")
        hub.now.t = QUIET
        hub.notify("sam", tier="good_news", source="vefr", title="One", body="…")
        hub.notify("sam", tier="good_news", source="candy", title="Two", body="…")
        assert hub.quiet_summaries() == 0  # still inside the window
        hub.now.t = NOT_QUIET  # the window has passed
        assert hub.quiet_summaries() == 1
        summary = json.loads(hub._fake.calls[-1]["data"])
        assert summary["body"] == "2 things waited for you"
        assert summary["source"] == "quiet_summary"
        states = {r["source"]: r["state"] for r in hub.list_notifications("sam", False, 10)}
        assert states["vefr"] == "summarized" and states["candy"] == "summarized"
        assert hub.quiet_summaries() == 0  # nothing waits twice

    def test_not_configured_still_records_history(self, tmp_path, monkeypatch):
        monkeypatch.delenv(push_mod.PRIVATE_KEY_ENV, raising=False)
        monkeypatch.delenv(push_mod.SUBJECT_ENV, raising=False)
        fake = FakePushService()
        monkeypatch.setattr(push_mod, "_webpush", fake)
        plain = push_mod.PushHub(tmp_path)
        plain.now = _Clock()
        out = plain.notify("sam", tier="good_news", source="vefr", title="T", body="B")
        assert out["state"] == "not_configured"
        assert fake.calls == []
        assert plain.list_notifications("sam", unread=False, limit=5)[0]["title"] == "T"

    def test_no_devices_still_stores(self, hub):
        out = hub.notify("sam", tier="good_news", source="vefr", title="T", body="B")
        assert out["state"] == "no_devices" and out["delivered"] == 0
        assert hub.list_notifications("sam", unread=False, limit=5)

    def test_dedupe_collapses_repeats_for_a_day(self, hub):
        hub.add_subscription("sam", SUB_A, "phone")
        first = hub.notify(
            "sam", tier="good_news", source="vefr", title="T", body="B", dedupe_key="job-1"
        )
        again = hub.notify(
            "sam", tier="good_news", source="vefr", title="T", body="B", dedupe_key="job-1"
        )
        assert again["state"] == "duplicate" and again["id"] == first["id"]
        assert len(hub._fake.calls) == 1
        hub.now.t = NOT_QUIET + 25 * 3600  # outside the 24-hour window
        third = hub.notify(
            "sam", tier="good_news", source="vefr", title="T", body="B", dedupe_key="job-1"
        )
        assert third["state"] == "delivered" and third["id"] != first["id"]

    def test_rate_limit_is_thirty_a_minute_per_caller(self, hub):
        def limiter(person):
            return hub.rate_limited(f"agent:{person}")
        assert all(not limiter("kit") for _ in range(30))
        assert limiter("kit")  # 31st in the same minute
        assert not limiter("robin")  # a different caller has its own window
        hub.now.t = NOT_QUIET + 61
        assert not limiter("kit")  # the window slid past

    def test_dead_devices_pruned_others_kept(self, hub, monkeypatch, caplog):
        hub.add_subscription("sam", SUB_A, "left-410")
        hub.add_subscription("sam", SUB_B, "left-404")
        hub.add_subscription("sam", SUB_C, "grumpy")
        codes = {ENDPOINT_A: 410, ENDPOINT_B: 404, ENDPOINT_C: 500}

        def flaky(subscription_info, data=None, **kwargs):
            hub._fake.calls.append({"subscription_info": subscription_info})
            raise _service_error(codes[subscription_info["endpoint"]])

        monkeypatch.setattr(push_mod, "_webpush", flaky)
        with caplog.at_level(logging.INFO, logger="personal_world.push"):
            out = hub.notify("sam", tier="good_news", source="vefr", title="T", body="B")
        # 404/410 mean the device is gone: pruned. 500 keeps it, in words.
        assert out["state"] == "failed" and out["delivered"] == 0
        rows = hub.list_subscriptions("sam")
        assert [r["device_label"] for r in rows] == ["grumpy"]
        assert rows[0]["last_error"] == "push service refused (500)"
        # the pruning notice stays plain too: no endpoint in any log line
        assert "removed" in caplog.text
        assert ENDPOINT_A not in caplog.text and ENDPOINT_B not in caplog.text

    def test_other_errors_keep_device_with_plain_words(self, hub):
        hub.add_subscription("sam", SUB_A, "phone")
        hub._fake.error = _service_error(500)
        out = hub.notify("sam", tier="good_news", source="vefr", title="T", body="B")
        assert out["state"] == "failed"
        rows = hub.list_subscriptions("sam")
        assert len(rows) == 1
        assert rows[0]["last_error"] == "push service refused (500)"

    def test_transport_bugs_never_crash_the_call(self, hub):
        hub.add_subscription("sam", SUB_A, "phone")
        hub._fake.error = TypeError("deep bug")  # not a push-service error
        out = hub.notify("sam", tier="good_news", source="vefr", title="T", body="B")
        assert out["state"] == "failed"
        assert hub.list_subscriptions("sam")[0]["last_error"] == "push failed (transport)"

    def test_test_push_bypasses_tier_gates_and_quiet_hours(self, hub):
        hub.add_subscription("sam", SUB_A, "phone")
        hub.put_prefs("sam", {"tiers": {"good_news": False}})
        out = hub.test_push("sam")
        assert out["state"] == "delivered"
        payload = json.loads(hub._fake.calls[-1]["data"])
        assert payload["title"] == "Worlds"
        assert "World Tree" in payload["body"]
        # Pressing "Send me a test" at night still sends it: the press is
        # the consent, and a test that waits until morning looks broken.
        hub.now.t = QUIET
        assert hub.test_push("sam")["state"] == "delivered"

    def test_corrupt_store_reads_empty_and_says_so(self, tmp_path, caplog):
        path = tmp_path / "notifications.json"
        path.write_text("{ not json", encoding="utf-8")
        store = push_mod.NotificationStore(path)
        with caplog.at_level(logging.WARNING, logger="personal_world.push"):
            assert store.list(False, 10, NOT_QUIET) == []
        assert "unreadable" in caplog.text


# ── the API doors ───────────────────────────────────────────────────


def _make_client(tmp_path, monkeypatch, vapid_pair, configured=True, app_dist=None, mode="single"):
    from personal_world.api import create_app
    from personal_world.init import init_world

    monkeypatch.setenv("PW_API_TOKEN", TOKEN)
    monkeypatch.setenv("PW_IDENTITY_MODE", mode)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv(push_mod.PRIVATE_KEY_ENV, raising=False)
    monkeypatch.delenv(push_mod.SUBJECT_ENV, raising=False)
    if configured:
        monkeypatch.setenv(push_mod.PRIVATE_KEY_ENV, vapid_pair["private_pem"])
        monkeypatch.setenv(push_mod.SUBJECT_ENV, QUIET_MAILTO)
    if app_dist is not None:
        monkeypatch.setenv("PW_APP_DIST", str(app_dist))
    else:
        monkeypatch.delenv("PW_APP_DIST", raising=False)
    init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok", encoding="utf-8")
    fake = FakePushService()
    monkeypatch.setattr(push_mod, "_webpush", fake)
    client = TestClient(create_app(tmp_path, tmp_path))
    client.headers.update(AUTH)
    # quiet hours are clock-dependent; tests pin the shape, not the hour
    client.put("/api/notifications/prefs", json={"quiet_hours": {"on": False}})
    return client, fake


@pytest.fixture
def client(tmp_path, monkeypatch, vapid_pair):
    return _make_client(tmp_path, monkeypatch, vapid_pair)[0]


class TestPushApi:
    def test_public_key_roundtrip_and_never_the_private(self, tmp_path, monkeypatch, vapid_pair):
        c, _ = _make_client(tmp_path, monkeypatch, vapid_pair)
        r = c.get("/api/push/public-key")
        assert r.status_code == 200
        assert r.json()["data"]["public_key"] == vapid_pair["public_key"]
        assert vapid_pair["private_pem"] not in r.text

    def test_public_key_409_when_not_configured(self, tmp_path, monkeypatch, vapid_pair):
        c, _ = _make_client(tmp_path, monkeypatch, vapid_pair, configured=False)
        r = c.get("/api/push/public-key")
        assert r.status_code == 409
        assert "not configured" in r.json()["detail"]

    def test_every_door_needs_auth(self, client):
        client.headers.clear()
        assert client.get("/api/push/public-key").status_code == 401
        assert client.get("/api/notifications").status_code == 401
        assert client.post("/api/notify", json={}).status_code == 401

    def test_agents_cannot_touch_devices_or_history(self, tmp_path, monkeypatch, vapid_pair):
        # service tokens resolve in multi mode only (identity entry point)
        c, _ = _make_client(tmp_path, monkeypatch, vapid_pair, mode="multi")
        agent = c.post(
            "/api/identity/agents",
            json={"agent_id": "kit-helper", "scopes": ["notify"]},
            headers=STEP_UP,
        ).json()["data"]
        at = {"Authorization": f"Bearer {agent['token']}"}
        assert c.get("/api/push/subscriptions", headers=at).status_code == 403
        assert c.get("/api/notifications", headers=at).status_code == 403
        assert c.post("/api/push/subscriptions", json={}, headers=at).status_code == 403

    def test_subscription_lifecycle_and_privacy(self, client):
        r = client.post(
            "/api/push/subscriptions",
            json={"subscription": SUB_A, "device_label": "iPhone"},
        )
        assert r.status_code == 200 and r.json()["data"]["created"] is True
        sub_id = r.json()["data"]["id"]
        listed = client.get("/api/push/subscriptions").json()["data"]
        assert listed[0]["device_label"] == "iPhone"
        blob = json.dumps(listed)
        assert ENDPOINT_A not in blob and "fakeauthA" not in blob
        assert client.delete(f"/api/push/subscriptions/{sub_id}").json()["data"]["removed"]
        assert client.delete(f"/api/push/subscriptions/{sub_id}").status_code == 404
        assert client.post(
            "/api/push/subscriptions",
            json={"subscription": {"endpoint": "http://x.invalid/a"}, "device_label": ""},
        ).status_code == 422

    def test_history_read_and_unread_flow(self, client):
        out = client.post(
            "/api/notify", json={"tier": "good_news", "source": "vefr", "title": "Picked", "body": "tomatoes", "link": "/today"}
        ).json()["data"]
        items = client.get("/api/notifications?unread=1&limit=5").json()["data"]
        assert items[0]["id"] == out["id"] and items[0]["tier_words"] == "GOOD NEWS"
        assert client.post(f"/api/notifications/{out['id']}/read").status_code == 200
        assert client.get("/api/notifications?unread=1").json()["data"] == []
        assert client.post("/api/notifications/does-not-exist/read").status_code == 404
        client.post("/api/notify", json={"tier": "good_news", "source": "vefr", "title": "a", "body": "b"})
        client.post("/api/notify", json={"tier": "update", "source": "vefr", "title": "c", "body": "d"})
        assert client.post("/api/notifications/read-all").json()["data"]["read"] == 2
        assert client.get("/api/notifications?limit=abc").status_code == 422

    def test_prefs_roundtrip_and_rejection(self, client):
        prefs = client.get("/api/notifications/prefs").json()["data"]
        assert prefs["quiet_hours"]["on"] is False  # set by the fixture
        assert prefs["tiers"]["when_ready"] is False  # the untouched default
        saved = client.put(
            "/api/notifications/prefs", json={"tiers": {"when_ready": True}}
        ).json()["data"]
        assert saved["tiers"]["when_ready"] is True
        assert client.put("/api/notifications/prefs", json={"tiers": {"nope": 1}}).status_code == 422

    def test_notify_validations(self, client):
        assert client.post(
            "/api/notify", json={"tier": "whenever", "source": "vefr", "title": "t", "body": "b"}
        ).status_code == 422
        assert client.post(
            "/api/notify", json={"tier": "update", "source": "vefr", "body": "b"}
        ).status_code == 422
        assert client.post(
            "/api/notify",
            json={"tier": "update", "source": "vefr", "title": "t", "body": "b", "link": "https://elsewhere.example/"},
        ).status_code == 422
        assert client.post(
            "/api/notify", json={"tier": "update", "source": "a source with spaces", "title": "t", "body": "b"}
        ).status_code == 422

    def test_notify_rate_limit_plain_429(self, client):
        body = {"tier": "update", "source": "vefr", "title": "t", "body": "b"}
        codes = [client.post("/api/notify", json=body).status_code for _ in range(30)]
        assert codes == [200] * 30
        late = client.post("/api/notify", json=body)
        assert late.status_code == 429
        assert "wait a moment" in late.json()["detail"]

    def test_notify_dedupe_via_api(self, client):
        body = {"tier": "update", "source": "vefr", "title": "t", "body": "b", "dedupe_key": "k-1"}
        first = client.post("/api/notify", json=body).json()["data"]
        again = client.post("/api/notify", json=body).json()["data"]
        assert again["state"] == "duplicate" and again["id"] == first["id"]

    def test_agent_needs_the_notify_scope_and_lands_in_owner_space(self, tmp_path, monkeypatch, vapid_pair):
        c, _ = _make_client(tmp_path, monkeypatch, vapid_pair, mode="multi")
        plain = c.post(
            "/api/identity/agents",
            json={"agent_id": "vefr-bot", "scopes": ["read"]},
            headers=STEP_UP,
        ).json()["data"]
        at = {"Authorization": f"Bearer {plain['token']}"}
        refused = c.post(
            "/api/notify", json={"tier": "update", "source": "vefr", "title": "t", "body": "b"}, headers=at
        )
        assert refused.status_code == 403 and "notify scope" in refused.json()["detail"]
        scoped = c.post(
            "/api/identity/agents",
            json={"agent_id": "candy-bot", "scopes": ["notify"]},
            headers=STEP_UP,
        ).json()["data"]
        sat = {"Authorization": f"Bearer {scoped['token']}"}
        out = c.post(
            "/api/notify", json={"tier": "update", "source": "candy", "title": "Sweet", "body": "b"}, headers=sat
        )
        assert out.status_code == 200
        titles = [i["title"] for i in c.get("/api/notifications").json()["data"]]
        assert "Sweet" in titles  # the owner (this client) sees it
        offsite = c.post(
            "/api/notify",
            json={"tier": "update", "source": "candy", "title": "t", "body": "b", "to": "sam"},
            headers=sat,
        )
        assert offsite.status_code == 403 and "yourself" in offsite.json()["detail"]

    def test_a_person_may_only_notify_themselves_unless_owner(self, tmp_path, monkeypatch, vapid_pair):
        c, _ = _make_client(tmp_path, monkeypatch, vapid_pair)
        # single mode: this token is the owner, so `to` is allowed and the
        # notification lands in that person's space (same shared store in
        # single mode — the multi-mode test checks real separation).
        out = c.post(
            "/api/notify", json={"tier": "update", "source": "cli", "title": "Yours", "body": "b", "to": "sam"}
        )
        assert out.status_code == 200
        assert c.post(
            "/api/notify", json={"tier": "update", "source": "cli", "title": "t", "body": "b", "to": "not a person!"}
        ).status_code == 422

    def test_multi_mode_to_routing_and_permissions(self, tmp_path, monkeypatch, vapid_pair):
        c, _ = _make_client(tmp_path, monkeypatch, vapid_pair, mode="multi")
        kit = c.post(
            "/api/identity/users",
            json={"user_id": "kit", "display_name": "Kit"},
            headers=STEP_UP,
        ).json()["data"]["token"]
        kt = {"Authorization": f"Bearer {kit}"}
        c.put("/api/notifications/prefs", json={"quiet_hours": {"on": False}}, headers=kt)
        # kit is a member: no manage_people, so no `to`
        refused = c.post(
            "/api/notify",
            json={"tier": "update", "source": "cli", "title": "t", "body": "b", "to": "primary"},
            headers=kt,
        )
        assert refused.status_code == 403
        # the owner may notify kit, and it lands in kit's own history
        assert c.post(
            "/api/notify",
            json={"tier": "update", "source": "cli", "title": "For Kit", "body": "b", "to": "kit"},
            headers=AUTH,
        ).status_code == 200
        titles = [i["title"] for i in c.get("/api/notifications", headers=kt).json()["data"]]
        assert "For Kit" in titles
        assert "For Kit" not in [i["title"] for i in c.get("/api/notifications", headers=AUTH).json()["data"]]
        assert c.post(
            "/api/notify",
            json={"tier": "update", "source": "cli", "title": "t", "body": "b", "to": "ghost"},
            headers=AUTH,
        ).status_code == 404

    def test_test_endpoint_and_response_hygiene(self, client, vapid_pair):
        client.post(
            "/api/push/subscriptions", json={"subscription": SUB_A, "device_label": "Phone"}
        )
        r = client.post("/api/notifications/test")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["state"] == "delivered" and data["delivered"] == 1
        for call in (
            client.get("/api/push/public-key"),
            client.get("/api/push/subscriptions"),
            client.get("/api/notifications"),
            r,
        ):
            assert vapid_pair["private_pem"] not in call.text
            assert ENDPOINT_A not in call.text

    def test_no_private_material_in_logs(self, tmp_path, monkeypatch, vapid_pair, caplog):
        c, fake = _make_client(tmp_path, monkeypatch, vapid_pair)
        fake.error = _service_error(500)
        with caplog.at_level(logging.DEBUG, logger="personal_world.push"):
            c.post("/api/push/subscriptions", json={"subscription": SUB_A, "device_label": "Phone"})
            c.post("/api/notify", json={"tier": "update", "source": "vefr", "title": "t", "body": "b"})
            c.post("/api/notifications/test")
            c.get("/api/push/public-key")
            fake.error = _service_error(410)
            c.post("/api/notify", json={"tier": "update", "source": "vefr", "title": "t", "body": "b"})
        joined = caplog.text + "\n".join(r.getMessage() for r in caplog.records)
        assert vapid_pair["private_pem"] not in joined
        assert ENDPOINT_A not in joined

    def test_reminder_source_flows_through_notify(self, client):
        out = client.post(
            "/api/notify", json={"tier": "good_news", "source": "reminder", "title": "Grab laundry", "body": "in 10 min", "link": "/"}
        ).json()["data"]
        assert out["state"] == "no_devices"
        items = client.get("/api/notifications").json()["data"]
        assert items[0]["source"] == "reminder"


# ── the service worker door ─────────────────────────────────────────


class TestServiceWorkerRoute:
    def test_sw_served_at_root_with_scope_and_no_store(self, tmp_path, monkeypatch, vapid_pair):
        dist = tmp_path / "app"
        dist.mkdir()
        (dist / "sw.js").write_text("self.addEventListener('push', () => {});", encoding="utf-8")
        c, _ = _make_client(tmp_path, monkeypatch, vapid_pair, app_dist=dist)
        c.headers.clear()  # the sw must be reachable before anyone signs in
        r = c.get("/sw.js")
        assert r.status_code == 200
        assert r.headers["Cache-Control"] == "no-store"
        assert r.headers["Service-Worker-Allowed"] == "/"
        assert "push" in r.text

    def test_sw_404_when_not_built(self, tmp_path, monkeypatch, vapid_pair):
        dist = tmp_path / "empty-app"
        dist.mkdir()
        c, _ = _make_client(tmp_path, monkeypatch, vapid_pair, app_dist=dist)
        assert c.get("/sw.js").status_code == 404



class TestDesignDefaults:
    """Design boards, owner-approved 2026-09-26."""

    def test_only_good_news_pushes_by_default(self, hub):
        hub.subscriptions("sam").upsert(
            {"endpoint": "https://push.example.test/sub/1", "keys": {"p256dh": "x", "auth": "y"}},
            "iPhone", hub.now(),
        ) if hasattr(hub, "subscriptions") else None
        out = hub.notify("sam", tier="update", source="vefr", title="T", body="B")
        assert out["state"] != "delivered"

    def test_private_hides_words_on_the_lock_screen(self, hub):
        store = hub._sub_store("sam")
        store.upsert({"endpoint": "https://push.example.test/sub/2", "keys": {"p256dh": "x", "auth": "y"}},
                     "iPhone", hub.now())
        hub.notify("sam", tier="good_news", source="candy", title="Secret gift idea",
                   body="for jo", private=True)
        payload = json.loads(hub._fake.calls[-1]["data"])
        assert payload["title"] == "" and payload["body"] == "Open Worlds to read it."
        assert payload["sender"] == "Candy"
        assert "Secret" not in hub._fake.calls[-1]["data"]
