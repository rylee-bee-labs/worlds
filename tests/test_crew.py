"""Crew registry — companions are user-owned (owner decision 2026-09-25).

The drawn crew is a **starter crew**: a person adds their own companion,
renames or hides a drawn one, deletes only what they created, and a room
may have no companion at all. Keepers record who the person put on a room;
they never change the room's status. Portraits are the person's own bytes,
stored privately on the existing per-principal seam and served same-origin.

Pinned here:

* the starter seed is the seven drawn residents — no Sol (she is the
  Worlds mark, not a crew entry) and no ``personal-world``;
* first read with no file seeds starters; a stored file is authoritative
  (an emptied roster stays empty);
* canon keeper defaults are seeded **only** for configured rooms whose id
  names a briefing system (workshop→Bolt, engine-room→Hekek, …); a room
  that names nothing gets no keeper;
* add → id is a unique slug of the name, the row carries its initial;
* assign → the room's keeper changes, the drawn crew is untouched, and the
  room's status never moves;
* delete → the companion is gone and its keeper assignments are cleared
  (the room reads ``keeper: null``);
* starters refuse deletion (409) but accept hiding and renaming;
* per-principal isolation: two people cannot see each other's crew;
* uploads: real PNG ok, fake PNG (wrong magic) 415, >5 MB 413, served
  with ``nosniff`` + ``Cache-Control: private`` and its real media type;
* ids that are not slugs (path traversal, unicode, slashes) are refused and
  never touch the filesystem.

No network: ``httpx.MockTransport`` feeds the room.
"""

import base64
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world import crew, rooms  # noqa: E402
from personal_world.rooms import RoomsService  # noqa: E402

#: Repo root, so a pinned asset PATH can be checked against the shipped file.
REPO_ROOT = Path(__file__).parent.parent

TOKEN = "instancetoken"  # pw-safety: synthetic

START_IDS = ["renai", "bolt", "hekek", "ratatoskr", "bruma", "mira", "scoop"]

DESCRIPTOR = {
    "contract": "room/0",
    "id": "workshop",
    "name": "Workshop",
    "icon": "wrench",
    "voice": "dry and precise",
    "version": "1.2.0",
    "commit": "a1b2c3d",
    "status": "healthy",
    "updated_at": "2026-09-25T13:05:48Z",
}

#: The smallest thing that is a PNG by its magic bytes.
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32


def _handler(descriptor=None):
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == rooms.ROOM_PATH:
            return httpx.Response(
                200, json=descriptor() if descriptor else DESCRIPTOR
            )
        if request.url.path == rooms.CARDS_PATH:
            return httpx.Response(200, json=[])
        if request.url.path == rooms.NEEDS_YOU_PATH:
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={"detail": "unknown"})

    return handle


def _install(monkeypatch, room_spec="workshop=http://room.test", handler=None):
    """Point the app at a mock room estate (no network)."""
    import personal_world.api as api_mod

    monkeypatch.setenv("PW_ROOMS", room_spec)
    monkeypatch.setattr(
        api_mod,
        "_ROOMS",
        RoomsService(transport=httpx.MockTransport(handler or _handler())),
    )


def _mk_app(tmp_path, monkeypatch, mode="single"):
    from personal_world.api import create_app
    from personal_world.init import init_world

    monkeypatch.setenv("PW_API_TOKEN", TOKEN)
    monkeypatch.setenv("PW_IDENTITY_MODE", mode)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok")
    return create_app(tmp_path, tmp_path)


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    return TestClient(_mk_app(tmp_path, monkeypatch, "single"))


def _auth(tok=TOKEN):
    return {"Authorization": f"Bearer {tok}"}


def _crew(client, tok=TOKEN):
    r = client.get("/api/crew", headers=_auth(tok))
    assert r.status_code == 200, r.text
    return {entry["id"]: entry for entry in r.json()["data"]}


def _rows(client, tok=TOKEN):
    r = client.get("/api/rooms", headers=_auth(tok))
    assert r.status_code == 200, r.text
    return {row["id"]: row for row in r.json()["data"]}


# ── unit: the registry helpers ────────────────────────────────────────


class TestStarterSeed:
    def test_seven_drawn_residents_and_no_sol(self):
        ids = [spec["id"] for spec in crew.STARTER_CREW]
        assert ids == START_IDS
        # Sol is the Worlds mark, not a crew entry; the server key for the
        # planet is never a companion id either.
        assert "sol" not in ids
        assert "personal-world" not in ids
        assert all(spec["name"] != "Sol" for spec in crew.STARTER_CREW)

    def test_portrait_paths_match_the_prescribed_asset_paths(self):
        for spec in crew.STARTER_CREW:
            if spec["id"] == "renai":
                assert spec["portrait_asset"] == "/assets/crew/512/renai-hello.webp"
            else:
                assert spec["portrait_asset"] == (
                    f"/assets/crew/512/{spec['id']}-portrait.webp"
                )

    def test_every_starter_portrait_path_is_a_shipped_file(self):
        """The seed names the web-sized art that actually ships.

        A path the front door would 404 on is a broken companion, so the
        PATH and the FILE are pinned together here: the owner export
        lives in ``ui/public/assets/crew/512/`` (masters stay in
        ``design/assets/crew/``) and this backend copies none of it.
        """
        for spec in crew.STARTER_CREW:
            asset = spec["portrait_asset"]
            assert asset.startswith("/assets/crew/512/"), asset
            assert asset.endswith(".webp"), asset
            shipped = REPO_ROOT / "ui" / "public" / asset.lstrip("/")
            assert shipped.is_file(), f"missing shipped art: {asset}"

    def test_full_body_stays_honestly_absent(self):
        """No canon full-body path is named for the starters, so the seed
        invents none — the front door falls back to the portrait."""
        assert all(
            entry["full_body_asset"] is None for entry in crew.starter_entries()
        )

    def test_starter_entries_are_private_copies(self):
        first = crew.starter_entries()
        first[0]["name"] = "Mutated"
        assert crew.starter_entries()[0]["name"] == "Renai"

    def test_missing_file_seeds_starters_and_no_more(self, tmp_path):
        state = crew.read_crew(tmp_path / "crew.json")
        assert [e["id"] for e in state["crew"]] == START_IDS
        assert state["keepers"] == {}  # no configured rooms → no keepers

    def test_unreadable_file_is_an_honest_starter_seed(self, tmp_path):
        path = tmp_path / "crew.json"
        path.write_text("{ not json")
        assert [e["id"] for e in crew.read_crew(path)["crew"]] == START_IDS

    def test_a_stored_file_is_authoritative_even_when_empty(self, tmp_path):
        path = tmp_path / "crew.json"
        crew.write_crew(path, {"crew": [], "keepers": {"workshop": None}})
        state = crew.read_crew(path, room_ids=["workshop"])
        assert state["crew"] == []
        assert state["keepers"] == {"workshop": None}


class TestKeeperDefaults:
    def test_seeded_only_for_rooms_that_name_a_canon_system(self):
        keepers = crew.default_keepers(
            ["workshop", "engine-room", "archive", "observatory",
             "newsstand", "world-tree", "studio", "", "sol"]
        )
        assert keepers == {
            "workshop": "bolt",
            "engine-room": "hekek",
            "archive": "bruma",
            "observatory": "mira",
            "newsstand": "scoop",
            "world-tree": "ratatoskr",
        }
        # Renai reports no system and is never seeded as a keeper.
        assert "renai" not in keepers.values()

    def test_system_ids_themselves_match(self):
        assert crew.default_keepers(["agents", "estate", "records"]) == {
            "agents": "bolt",
            "estate": "hekek",
            "records": "bruma",
        }

    def test_absent_keepers_key_is_seeded(self, tmp_path):
        path = tmp_path / "crew.json"
        path.write_text(json.dumps({"crew": crew.starter_entries()}))
        state = crew.read_crew(path, room_ids=["workshop", "studio"])
        assert state["keepers"] == {"workshop": "bolt"}

    def test_a_seeded_keeper_the_roster_no_longer_has_is_not_written(self, tmp_path):
        """A hand-edited file with an emptied roster gets no phantom
        keepers: the canon seed names a resident, never an id the person
        took out of their own crew."""
        path = tmp_path / "crew.json"
        path.write_text(json.dumps({"crew": []}))
        assert crew.read_crew(path, room_ids=["workshop"])["keepers"] == {}

    def test_present_keepers_key_is_never_reseeded(self, tmp_path):
        path = tmp_path / "crew.json"
        path.write_text(
            json.dumps({"crew": crew.starter_entries(), "keepers": {}})
        )
        state = crew.read_crew(path, room_ids=["workshop"])
        assert state["keepers"] == {}

    def test_unaddressable_stored_entries_are_dropped(self, tmp_path):
        """A hand-edited file cannot smuggle in a traversal id, a blank
        name, or a non-object entry — they are dropped, not guessed at."""
        path = tmp_path / "crew.json"
        path.write_text(
            json.dumps(
                {
                    "crew": [
                        {"id": "../evil", "name": "Traversal"},
                        {"id": "ok", "name": ""},
                        {"id": "also-ok", "name": "   "},
                        "not an object",
                        {"id": "keeper", "name": "Keeper"},
                    ],
                    "keepers": {},
                }
            )
        )
        state = crew.read_crew(path)
        assert [e["id"] for e in state["crew"]] == ["keeper"]
        assert state["crew"][0]["name"] == "Keeper"
        assert crew.initial_of(state["crew"][0]["name"]) == "K"

    def test_a_dangling_keeper_reads_as_no_keeper(self, tmp_path):
        path = tmp_path / "crew.json"
        path.write_text(
            json.dumps(
                {"crew": crew.starter_entries(), "keepers": {"workshop": "ghost"}}
            )
        )
        assert crew.read_crew(path)["keepers"] == {"workshop": None}


class TestRemove:
    def test_removing_a_user_companion_reports_the_rooms_it_kept(self):
        state = {"crew": crew.starter_entries(), "keepers": {"workshop": "bolt"}}
        entry = crew.add(state, name="Nova")
        state["keepers"]["studio"] = entry["id"]
        removed, cleared = crew.remove(state, entry["id"])
        assert removed is not None and removed["id"] == "nova"
        assert cleared == ["studio"]
        assert state["keepers"] == {"workshop": "bolt", "studio": None}
        assert crew.find(state, "nova") is None

    def test_a_starter_is_never_removed_here(self):
        state = {"crew": crew.starter_entries(), "keepers": {"workshop": "bolt"}}
        assert crew.remove(state, "bolt") == (None, [])
        assert len(state["crew"]) == len(START_IDS)
        assert state["keepers"] == {"workshop": "bolt"}


class TestIdsAndSlugs:
    @pytest.mark.parametrize(
        "bad",
        ["", "../evil", "..", "a/b", "a b", "Bolt", "-lead", "héllo", None, 7,
         "x" * 65],
    )
    def test_unsafe_ids_are_refused(self, bad):
        assert not crew.is_safe_id(bad)

    @pytest.mark.parametrize("good", ["bolt", "my-helper-2", "a", "x" * 64])
    def test_slug_ids_are_accepted(self, good):
        assert crew.is_safe_id(good)

    def test_an_unsafe_id_has_no_portrait_path(self, tmp_path):
        with pytest.raises(ValueError):
            crew.portrait_path(tmp_path / "crew.json", "../evil", "png")

    def test_slugify_and_uniqueness(self):
        assert crew.slugify("My Helper!") == "my-helper"
        assert crew.slugify("!!!") == ""
        state = {"crew": crew.starter_entries()}
        assert crew.unique_id(state, "bolt") == "bolt-2"
        entry = crew.add(state, name="Bolt")
        assert entry["id"] == "bolt-2"
        assert crew.add(state, name="Bolt")["id"] == "bolt-3"

    @pytest.mark.parametrize(
        "raw,expected",
        [(b"\x89PNG\r\n\x1a\n", "image/png"),
         (b"\xff\xd8\xff\xe0", "image/jpeg"),
         (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp")],
    )
    def test_magic_bytes_typing(self, raw, expected):
        assert crew.sniff_image_type(raw) == expected

    def test_non_images_and_truncated_webp_are_not_typed(self):
        assert crew.sniff_image_type(b"<html>hello") is None
        assert crew.sniff_image_type(b"") is None
        assert crew.sniff_image_type(b"RIFF\x00\x00\x00\x00") is None

    def test_oversized_base64_is_refused_before_decoding(self):
        # 5 MB + slack of base64 text: refuse without decoding it.
        huge = "A" * ((crew.PORTRAIT_MAX_BYTES // 3 + 1) * 4 + 4)
        assert crew.decode_portrait(huge) == (None, "too_large")

    def test_malformed_base64_is_refused(self):
        assert crew.decode_portrait("not base64!!") == (None, "not_base64")
        assert crew.decode_portrait(None) == (None, "not_base64")
        assert crew.decode_portrait(7) == (None, "not_base64")


# ── API: the roster ───────────────────────────────────────────────────


class TestCrewRoster:
    def test_route_requires_auth(self, client):
        assert client.get("/api/crew").status_code == 401

    def test_first_read_seeds_the_seven(self, client, monkeypatch):
        _install(monkeypatch)
        assert list(_crew(client)) == START_IDS

    def test_add_with_only_a_name(self, client, monkeypatch):
        _install(monkeypatch)
        r = client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        assert r.status_code == 200, r.text
        entry = r.json()["data"]
        assert entry["id"] == "nova"
        assert entry["name"] == "Nova"
        assert entry["source"] == "user"
        assert entry["hidden"] is False
        assert entry["blurb"] is None and entry["voice_label"] is None
        assert entry["portrait_asset"] is None

        roster = _crew(client)
        assert roster["nova"]["name"] == "Nova"
        assert len(roster) == 8

    def test_added_companion_shows_its_initial_on_a_room(self, client, monkeypatch):
        _install(monkeypatch)
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        client.put(
            "/api/rooms/workshop/keeper",
            json={"companion_id": "nova"},
            headers=_auth(),
        )
        keeper = _rows(client)["workshop"]["keeper"]
        assert keeper == {
            "id": "nova",
            "name": "Nova",
            "portrait_url": None,
            "initial": "N",
        }

    def test_add_is_per_principal_and_capped(self, client, monkeypatch):
        _install(monkeypatch)
        ok = client.post(
            "/api/crew",
            json={
                "name": "N" * crew.NAME_MAX,
                "blurb": "B" * crew.BLURB_MAX,
                "voice_label": "V" * crew.VOICE_LABEL_MAX,
            },
            headers=_auth(),
        )
        assert ok.status_code == 200, ok.text
        over = client.post(
            "/api/crew",
            json={
                "name": "N" * (crew.NAME_MAX + 1),
                "blurb": "B" * (crew.BLURB_MAX + 1),
                "voice_label": "V" * (crew.VOICE_LABEL_MAX + 1),
            },
            headers=_auth(),
        )
        assert over.status_code == 422

    @pytest.mark.parametrize(
        "body",
        [
            {},
            {"name": ""},
            {"name": "   "},
            {"name": 7},
            {"name": "Ok", "blurb": 7},
            {"name": "Ok", "voice_label": 7},
            {"name": "Ok", "blurb": "B" * (crew.BLURB_MAX + 1)},
            {"name": "Ok", "voice_label": "V" * (crew.VOICE_LABEL_MAX + 1)},
        ],
    )
    def test_add_validates_strings_and_lengths(self, client, monkeypatch, body):
        _install(monkeypatch)
        r = client.post("/api/crew", json=body, headers=_auth())
        assert r.status_code == 422, r.text
        assert list(_crew(client)) == START_IDS  # nothing was stored

    def test_starter_can_be_renamed_and_hidden(self, client, monkeypatch):
        _install(monkeypatch)
        r = client.patch(
            "/api/crew/bolt",
            json={"name": "Bolt Jr", "hidden": True, "blurb": "Still Bolt."},
            headers=_auth(),
        )
        assert r.status_code == 200, r.text
        entry = r.json()["data"]
        assert (entry["name"], entry["hidden"], entry["source"]) == (
            "Bolt Jr",
            True,
            "starter",
        )
        roster = _crew(client)
        assert roster["bolt"]["hidden"] is True
        assert roster["bolt"]["name"] == "Bolt Jr"

    def test_hidden_starter_stays_in_the_roster_not_removed(self, client, monkeypatch):
        _install(monkeypatch)
        client.patch("/api/crew/mira", json={"hidden": True}, headers=_auth())
        assert "mira" in _crew(client)
        assert len(_crew(client)) == len(START_IDS)

    def test_patch_clears_an_optional_field_with_null(self, client, monkeypatch):
        _install(monkeypatch)
        client.post(
            "/api/crew", json={"name": "Nova", "blurb": "watchful"}, headers=_auth()
        )
        r = client.patch("/api/crew/nova", json={"blurb": None}, headers=_auth())
        assert r.status_code == 200, r.text
        assert r.json()["data"]["blurb"] is None

    def test_patch_unknown_companion_is_404(self, client, monkeypatch):
        _install(monkeypatch)
        assert (
            client.patch(
                "/api/crew/ghost", json={"name": "Ghost"}, headers=_auth()
            ).status_code
            == 404
        )

    def test_patch_rejects_a_non_boolean_hidden(self, client, monkeypatch):
        _install(monkeypatch)
        r = client.patch("/api/crew/bolt", json={"hidden": "yes"}, headers=_auth())
        assert r.status_code == 422

    def test_starters_cannot_be_deleted_but_user_entries_can(self, client, monkeypatch):
        _install(monkeypatch)
        for starter in START_IDS:
            r = client.delete(f"/api/crew/{starter}", headers=_auth())
            assert r.status_code == 409, starter
        assert list(_crew(client)) == START_IDS  # all still there

        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        r = client.delete("/api/crew/nova", headers=_auth())
        assert r.status_code == 200, r.text
        assert "nova" not in _crew(client)

    def test_delete_unknown_companion_is_404(self, client, monkeypatch):
        _install(monkeypatch)
        assert client.delete("/api/crew/ghost", headers=_auth()).status_code == 404


# ── API: keepers ──────────────────────────────────────────────────────


class TestKeepers:
    def test_defaults_come_from_canon_and_nothing_else(self, client, monkeypatch):
        _install(
            monkeypatch,
            room_spec="workshop=http://room.test,studio=http://room.test",
        )
        rows = _rows(client)
        assert rows["workshop"]["keeper"]["id"] == "bolt"
        assert rows["workshop"]["keeper"]["initial"] == "B"
        # "studio" names no canon system → honestly no companion
        assert rows["studio"]["keeper"] is None

    def test_assigning_moves_the_room_but_not_the_crew(self, client, monkeypatch):
        _install(monkeypatch)
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        r = client.put(
            "/api/rooms/workshop/keeper",
            json={"companion_id": "nova"},
            headers=_auth(),
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["keeper"]["id"] == "nova"
        assert _rows(client)["workshop"]["keeper"]["name"] == "Nova"
        # Bolt kept the room, and stays in the crew.
        assert "bolt" in _crew(client)

    def test_one_keeper_per_room_and_a_companion_may_keep_several(
        self, client, monkeypatch
    ):
        _install(
            monkeypatch,
            room_spec="workshop=http://room.test,studio=http://room.test",
        )
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        client.put(
            "/api/rooms/workshop/keeper",
            json={"companion_id": "nova"},
            headers=_auth(),
        )
        client.put(
            "/api/rooms/studio/keeper",
            json={"companion_id": "nova"},
            headers=_auth(),
        )
        rows = _rows(client)
        assert rows["workshop"]["keeper"]["id"] == "nova"
        assert rows["studio"]["keeper"]["id"] == "nova"

    def test_clearing_a_keeper_is_sticky(self, client, monkeypatch):
        _install(monkeypatch)
        r = client.put(
            "/api/rooms/workshop/keeper",
            json={"companion_id": None},
            headers=_auth(),
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["keeper"] is None
        # Re-read: the person cleared it, so the default is not re-seeded.
        assert _rows(client)["workshop"]["keeper"] is None

    def test_delete_clears_the_rooms_the_companion_kept(self, client, monkeypatch):
        _install(
            monkeypatch,
            room_spec="workshop=http://room.test,studio=http://room.test",
        )
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        for room_id in ("workshop", "studio"):
            client.put(
                f"/api/rooms/{room_id}/keeper",
                json={"companion_id": "nova"},
                headers=_auth(),
            )
        r = client.delete("/api/crew/nova", headers=_auth())
        assert r.status_code == 200, r.text
        assert r.json()["data"]["keepers_cleared"] == ["studio", "workshop"]
        rows = _rows(client)
        assert rows["workshop"]["keeper"] is None
        assert rows["studio"]["keeper"] is None

    def test_keeper_never_changes_room_status(self, client, monkeypatch):
        _install(monkeypatch)
        before = _rows(client)["workshop"]
        assert before["status"] == "healthy" and before["reachable"] is True

        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        client.put(
            "/api/rooms/workshop/keeper",
            json={"companion_id": "nova"},
            headers=_auth(),
        )
        after = _rows(client)["workshop"]
        assert after["status"] == "healthy"
        assert after["reachable"] is True
        assert after["error"] is None
        assert after["last_status"] == before["last_status"]

    def test_keeper_never_changes_an_unreachable_room_either(
        self, client, monkeypatch
    ):
        def down(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down")

        _install(monkeypatch, handler=down)
        assert _rows(client)["workshop"]["status"] == "unreachable"
        client.put(
            "/api/rooms/workshop/keeper",
            json={"companion_id": "mira"},
            headers=_auth(),
        )
        row = _rows(client)["workshop"]
        assert row["status"] == "unreachable"
        assert row["keeper"]["id"] == "mira"  # the person's choice, not health

    def test_unconfigured_room_is_404(self, client, monkeypatch):
        _install(monkeypatch)
        r = client.put(
            "/api/rooms/nope/keeper",
            json={"companion_id": "bolt"},
            headers=_auth(),
        )
        assert r.status_code == 404

    @pytest.mark.parametrize(
        "body", [{}, {"companion_id": "ghost"}, {"companion_id": 7}, {"companion_id": ""}]
    )
    def test_unknown_or_malformed_companion_is_422(
        self, client, monkeypatch, body
    ):
        _install(monkeypatch)
        r = client.put("/api/rooms/workshop/keeper", json=body, headers=_auth())
        assert r.status_code == 422, r.text


# ── API: doorways ─────────────────────────────────────────────────────


class TestDoorways:
    def test_route_requires_auth(self, client, monkeypatch):
        _install(monkeypatch)
        r = client.put(
            "/api/rooms/workshop/doorway", json={"doorway_id": "garden"}
        )
        assert r.status_code == 401

    def test_no_default_doorway_is_ever_seeded(self, client, monkeypatch):
        _install(monkeypatch)
        assert _rows(client)["workshop"]["doorway"] is None

    @pytest.mark.parametrize("doorway_id", list(crew.DOORWAYS))
    def test_every_closed_list_id_can_be_set(self, client, monkeypatch, doorway_id):
        _install(monkeypatch)
        r = client.put(
            "/api/rooms/workshop/doorway",
            json={"doorway_id": doorway_id},
            headers=_auth(),
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["doorway"] == doorway_id
        assert _rows(client)["workshop"]["doorway"] == doorway_id

    def test_set_persists_across_reads_and_on_disk(self, client, monkeypatch, tmp_path):
        _install(monkeypatch)
        client.put(
            "/api/rooms/workshop/doorway",
            json={"doorway_id": "garden"},
            headers=_auth(),
        )
        assert _rows(client)["workshop"]["doorway"] == "garden"
        # the existing atomic write really stored it on the caller's file
        stored = json.loads((tmp_path / "crew.json").read_text())
        assert stored["doorways"] == {"workshop": "garden"}

    def test_clearing_returns_null_and_stays_cleared(self, client, monkeypatch):
        _install(monkeypatch)
        client.put(
            "/api/rooms/workshop/doorway",
            json={"doorway_id": "vault"},
            headers=_auth(),
        )
        r = client.put(
            "/api/rooms/workshop/doorway",
            json={"doorway_id": None},
            headers=_auth(),
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["doorway"] is None
        # Re-read: the person cleared it, and nothing re-seeds a doorway.
        assert _rows(client)["workshop"]["doorway"] is None

    @pytest.mark.parametrize(
        "body",
        [
            {},
            {"doorway_id": "attic"},
            {"doorway_id": "Garden"},
            {"doorway_id": ""},
            {"doorway_id": 7},
            {"doorway_id": ["garden"]},
            {"doorway_id": {"id": "garden"}},
        ],
    )
    def test_unknown_or_malformed_doorway_is_422(self, client, monkeypatch, body):
        _install(monkeypatch)
        r = client.put("/api/rooms/workshop/doorway", json=body, headers=_auth())
        assert r.status_code == 422, r.text
        assert _rows(client)["workshop"]["doorway"] is None  # nothing stored

    def test_unconfigured_room_is_404(self, client, monkeypatch):
        _install(monkeypatch)
        r = client.put(
            "/api/rooms/nope/doorway",
            json={"doorway_id": "garden"},
            headers=_auth(),
        )
        assert r.status_code == 404

    def test_doorway_never_changes_room_status(self, client, monkeypatch):
        _install(monkeypatch)
        before = _rows(client)["workshop"]
        assert before["status"] == "healthy" and before["reachable"] is True
        client.put(
            "/api/rooms/workshop/doorway",
            json={"doorway_id": "garden"},
            headers=_auth(),
        )
        after = _rows(client)["workshop"]
        assert after["status"] == "healthy"
        assert after["reachable"] is True
        assert after["error"] is None
        assert after["last_status"] == before["last_status"]
        # a keeper and a doorway are independent choices on one row
        assert after["keeper"]["id"] == "bolt"

    def test_doorway_never_changes_an_unreachable_room_either(
        self, client, monkeypatch
    ):
        def down(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down")

        _install(monkeypatch, handler=down)
        assert _rows(client)["workshop"]["status"] == "unreachable"
        client.put(
            "/api/rooms/workshop/doorway",
            json={"doorway_id": "lounge"},
            headers=_auth(),
        )
        row = _rows(client)["workshop"]
        assert row["status"] == "unreachable"
        assert row["doorway"] == "lounge"  # the person's choice, not health

    def test_an_unknown_stored_id_reads_as_null(self, client, monkeypatch, tmp_path):
        _install(monkeypatch)
        (tmp_path / "crew.json").write_text(
            json.dumps(
                {"crew": [], "keepers": {}, "doorways": {"workshop": "attic"}}
            )
        )
        assert _rows(client)["workshop"]["doorway"] is None


class TestDoorwayState:
    def test_no_file_has_no_doorways(self, tmp_path):
        assert crew.read_crew(tmp_path / "crew.json")["doorways"] == {}

    def test_a_non_dict_doorways_reads_as_empty(self, tmp_path):
        path = tmp_path / "crew.json"
        path.write_text(
            json.dumps(
                {"crew": crew.starter_entries(), "doorways": ["garden"]}
            )
        )
        assert crew.read_crew(path)["doorways"] == {}

    def test_unknown_stored_ids_read_as_absent(self, tmp_path):
        path = tmp_path / "crew.json"
        path.write_text(
            json.dumps(
                {
                    "crew": crew.starter_entries(),
                    "doorways": {"workshop": "attic", "studio": "garden"},
                }
            )
        )
        state = crew.read_crew(path)
        assert crew.doorway_of(state, "workshop") is None
        assert crew.doorway_of(state, "studio") == "garden"
        assert crew.doorway_of(state, "never-set") is None

    def test_a_round_trip_keeps_the_choice(self, tmp_path):
        path = tmp_path / "crew.json"
        crew.write_crew(
            path,
            {
                "crew": crew.starter_entries(),
                "keepers": {},
                "doorways": {"workshop": "garden"},
            },
        )
        assert crew.doorway_of(crew.read_crew(path), "workshop") == "garden"


# ── API: portraits ────────────────────────────────────────────────────


def _upload(client, companion_id="nova", content_type="image/png", data=PNG_BYTES):
    return client.post(
        f"/api/crew/{companion_id}/portrait",
        json={
            "content_type": content_type,
            "data_base64": base64.b64encode(data).decode(),
        },
        headers=_auth(),
    )


class TestPortraits:
    def test_png_upload_is_stored_privately_and_points_at_the_route(
        self, client, monkeypatch, tmp_path
    ):
        _install(monkeypatch)
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        r = _upload(client)
        assert r.status_code == 200, r.text
        assert r.json()["data"]["portrait_asset"] == "/api/crew/nova/portrait"

        stored = tmp_path / "crew-portraits" / "nova.png"
        assert stored.is_file()
        assert stored.read_bytes() == PNG_BYTES
        assert stored.stat().st_mode & 0o077 == 0  # private bits
        # the walkable portrait dir holds only this companion's file
        assert sorted(p.name for p in (tmp_path / "crew-portraits").iterdir()) == [
            "nova.png"
        ]

    def test_served_same_origin_with_nosniff_and_private_cache(
        self, client, monkeypatch
    ):
        _install(monkeypatch)
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        _upload(client)
        r = client.get("/api/crew/nova/portrait", headers=_auth())
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "image/png"
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["cache-control"] == "private"
        assert r.content == PNG_BYTES
        assert r.headers.get("content-disposition") in (None, "inline")

    def test_jpeg_round_trips_with_its_real_media_type(self, client, monkeypatch):
        _install(monkeypatch)
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        r = _upload(client, content_type="image/jpeg", data=JPEG_BYTES)
        assert r.status_code == 200, r.text
        served = client.get("/api/crew/nova/portrait", headers=_auth())
        assert served.headers["content-type"] == "image/jpeg"

    def test_fake_png_is_refused_by_magic_bytes(self, client, monkeypatch, tmp_path):
        _install(monkeypatch)
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        r = _upload(client, data=b"<html>definitely not a png</html>")
        assert r.status_code == 415, r.text
        assert not (tmp_path / "crew-portraits" / "nova.png").exists()

    def test_a_declared_type_that_disagrees_with_the_bytes_is_refused(
        self, client, monkeypatch
    ):
        _install(monkeypatch)
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        # real JPEG bytes declared as PNG → refused, never relabelled
        r = _upload(client, content_type="image/png", data=JPEG_BYTES)
        assert r.status_code == 415

    @pytest.mark.parametrize(
        "content_type", ["image/gif", "image/svg+xml", "text/html", "", None, 7]
    )
    def test_only_the_three_image_types_are_accepted(
        self, client, monkeypatch, content_type
    ):
        _install(monkeypatch)
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        r = client.post(
            "/api/crew/nova/portrait",
            json={
                "content_type": content_type,
                "data_base64": base64.b64encode(PNG_BYTES).decode(),
            },
            headers=_auth(),
        )
        assert r.status_code == 415, r.text

    def test_over_five_megabytes_is_413(self, client, monkeypatch, tmp_path):
        _install(monkeypatch)
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        too_big = PNG_BYTES + b"\x00" * crew.PORTRAIT_MAX_BYTES
        r = _upload(client, data=too_big)
        assert r.status_code == 413, r.text
        assert not (tmp_path / "crew-portraits").exists()

    def test_malformed_base64_is_422(self, client, monkeypatch):
        _install(monkeypatch)
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        r = client.post(
            "/api/crew/nova/portrait",
            json={"content_type": "image/png", "data_base64": "not base64!!"},
            headers=_auth(),
        )
        assert r.status_code == 422

    def test_unknown_companion_is_404_for_every_portrait_verb(
        self, client, monkeypatch
    ):
        _install(monkeypatch)
        assert _upload(client, companion_id="ghost").status_code == 404
        assert (
            client.get("/api/crew/ghost/portrait", headers=_auth()).status_code == 404
        )
        assert (
            client.delete("/api/crew/ghost/portrait", headers=_auth()).status_code
            == 404
        )

    def test_no_uploaded_portrait_serves_404(self, client, monkeypatch):
        _install(monkeypatch)
        assert (
            client.get("/api/crew/bolt/portrait", headers=_auth()).status_code == 404
        )
        assert (
            client.delete("/api/crew/bolt/portrait", headers=_auth()).status_code
            == 404
        )

    def test_delete_removes_it_and_restores_the_shipped_asset_for_a_starter(
        self, client, monkeypatch, tmp_path
    ):
        _install(monkeypatch)
        _upload(client, companion_id="bolt")
        assert (tmp_path / "crew-portraits" / "bolt.png").is_file()
        assert (
            _crew(client)["bolt"]["portrait_asset"] == "/api/crew/bolt/portrait"
        )

        r = client.delete("/api/crew/bolt/portrait", headers=_auth())
        assert r.status_code == 200, r.text
        assert (
            r.json()["data"]["portrait_asset"]
            == "/assets/crew/512/bolt-portrait.webp"
        )
        assert not (tmp_path / "crew-portraits" / "bolt.png").exists()
        assert (
            client.get("/api/crew/bolt/portrait", headers=_auth()).status_code == 404
        )

    def test_delete_on_a_user_companion_leaves_no_portrait_asset(
        self, client, monkeypatch
    ):
        _install(monkeypatch)
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        _upload(client)
        r = client.delete("/api/crew/nova/portrait", headers=_auth())
        assert r.status_code == 200, r.text
        assert r.json()["data"]["portrait_asset"] is None

    def test_a_new_upload_replaces_the_old_format(self, client, monkeypatch, tmp_path):
        _install(monkeypatch)
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        _upload(client, content_type="image/png", data=PNG_BYTES)
        _upload(client, content_type="image/jpeg", data=JPEG_BYTES)
        files = sorted(p.name for p in (tmp_path / "crew-portraits").iterdir())
        assert files == ["nova.jpg"]
        served = client.get("/api/crew/nova/portrait", headers=_auth())
        assert served.headers["content-type"] == "image/jpeg"

    def test_deleting_a_companion_removes_its_portrait(self, client, monkeypatch, tmp_path):
        _install(monkeypatch)
        client.post("/api/crew", json={"name": "Nova"}, headers=_auth())
        _upload(client)
        client.delete("/api/crew/nova", headers=_auth())
        assert not (tmp_path / "crew-portraits" / "nova.png").exists()


# ── path traversal ────────────────────────────────────────────────────


class TestNeverSentOutward:
    def test_a_room_never_learns_who_the_caller_put_there(self, client, monkeypatch):
        """Worlds-owned state stays Worlds-owned: the outbound room probe
        carries no companion id, name, or keeper — the room is told
        nothing about who is looking or who keeps it."""
        seen: list[httpx.Request] = []

        def recording(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return _handler()(request)

        _install(monkeypatch, handler=recording)
        client.post(
            "/api/crew",
            json={"name": "Secret Companion", "blurb": "private notes"},
            headers=_auth(),
        )
        client.put(
            "/api/rooms/workshop/keeper",
            json={"companion_id": "secret-companion"},
            headers=_auth(),
        )
        assert _rows(client)["workshop"]["keeper"]["id"] == "secret-companion"

        assert seen, "the room was probed"
        for request in seen:
            blob = f"{request.url} {request.headers} {request.content!r}"
            assert "secret" not in blob.lower()
            assert "keeper" not in blob.lower()
            assert "companion" not in blob.lower()

    def test_a_room_never_learns_the_caller_doorway(self, client, monkeypatch):
        """A doorway is presentation only and Worlds-private: the outbound
        room probe carries no doorway id and nothing about the choice."""
        seen: list[httpx.Request] = []

        def recording(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return _handler()(request)

        _install(monkeypatch, handler=recording)
        client.put(
            "/api/rooms/workshop/doorway",
            json={"doorway_id": "vault"},
            headers=_auth(),
        )
        assert _rows(client)["workshop"]["doorway"] == "vault"

        assert seen, "the room was probed"
        for request in seen:
            blob = f"{request.url} {request.headers} {request.content!r}"
            assert "doorway" not in blob.lower()
            assert "vault" not in blob.lower()


class TestTraversalRefused:
    @pytest.mark.parametrize(
        "raw", ["%2E%2E", "..%5C..%5Cwindows", "a%2Eb", "..%2E%2E"]
    )
    def test_single_segment_traversal_ids_are_refused_by_the_handler(
        self, client, monkeypatch, tmp_path, raw
    ):
        """Decoded, these are one path segment: the crew handler sees them
        and refuses them (404) before any filesystem work happens."""
        _install(monkeypatch)
        before = sorted(p.name for p in tmp_path.iterdir())
        assert client.get(f"/api/crew/{raw}", headers=_auth()).status_code == 404
        assert (
            client.patch(
                f"/api/crew/{raw}", json={"name": "x"}, headers=_auth()
            ).status_code
            == 404
        )
        assert client.delete(f"/api/crew/{raw}", headers=_auth()).status_code == 404
        assert (
            client.get(f"/api/crew/{raw}/portrait", headers=_auth()).status_code
            == 404
        )
        assert (
            client.delete(f"/api/crew/{raw}/portrait", headers=_auth()).status_code
            == 404
        )
        assert _upload(client, companion_id=raw).status_code == 404
        assert sorted(p.name for p in tmp_path.iterdir()) == before
        assert not (tmp_path / "crew-portraits").exists()

    @pytest.mark.parametrize(
        "raw",
        ["%2E%2E%2F%2E%2E%2Fetc%2Fpasswd", "..%2Fcrew.json", "a%2Fb"],
    )
    def test_slash_decoding_ids_never_reach_the_crew_handler(
        self, client, monkeypatch, tmp_path, raw
    ):
        """An id that decodes to several segments is not a matchable path,
        so the refusal happens at the route layer (404/405 — never a 2xx,
        never a handler) and nothing is written anywhere."""
        _install(monkeypatch)
        before = sorted(p.name for p in tmp_path.iterdir())
        assert client.get(f"/api/crew/{raw}", headers=_auth()).status_code in (
            400,
            404,
            405,
        )
        assert (
            client.patch(
                f"/api/crew/{raw}", json={"name": "x"}, headers=_auth()
            ).status_code
            in (400, 404, 405)
        )
        assert client.delete(f"/api/crew/{raw}", headers=_auth()).status_code in (
            400,
            404,
            405,
        )
        assert _upload(client, companion_id=raw).status_code in (400, 404, 405)
        assert sorted(p.name for p in tmp_path.iterdir()) == before
        assert not (tmp_path / "crew-portraits").exists()

    def test_a_traversal_id_never_reaches_the_filesystem(self, tmp_path):
        path = tmp_path / "crew.json"
        with pytest.raises(ValueError):
            crew.write_portrait(path, "../escaped", PNG_BYTES, "png")
        assert not (tmp_path.parent / "escaped.png").exists()
        assert crew.find_portrait(path, "../../crew.json") is None
        assert crew.delete_portrait(path, "../escaped") is False


# ── per-principal isolation ───────────────────────────────────────────


class TestPrincipalIsolation:
    def _two_people(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        app = _mk_app(tmp_path, monkeypatch, "multi")
        client = TestClient(app)
        _install(monkeypatch)
        r = client.post(
            "/api/identity/users",
            json={"user_id": "beta", "display_name": "Beta"},
            headers={**_auth(), "X-PW-StepUp": "1"},
        )
        assert r.status_code == 200, r.text
        return client, r.json()["data"]["token"]

    def test_crews_do_not_leak_between_principals(self, tmp_path, monkeypatch):
        client, beta = self._two_people(tmp_path, monkeypatch)

        client.post("/api/crew", json={"name": "Alpha Only"}, headers=_auth())
        assert "alpha-only" in _crew(client)
        assert "alpha-only" not in _crew(client, beta)
        assert list(_crew(client, beta)) == START_IDS

        # each person's roster is written on their own tree, never shared
        assert (tmp_path / "users" / "primary" / "crew.json").exists()
        assert not (tmp_path / "users" / "beta" / "crew.json").exists()

    def test_keepers_are_per_principal(self, tmp_path, monkeypatch):
        client, beta = self._two_people(tmp_path, monkeypatch)
        client.post("/api/crew", json={"name": "Alpha Only"}, headers=_auth())
        client.put(
            "/api/rooms/workshop/keeper",
            json={"companion_id": "alpha-only"},
            headers=_auth(),
        )
        assert _rows(client)["workshop"]["keeper"]["id"] == "alpha-only"
        # Beta still has the canon default and cannot see Alpha's companion.
        assert _rows(client, beta)["workshop"]["keeper"]["id"] == "bolt"

    def test_portraits_are_per_principal(self, tmp_path, monkeypatch):
        client, beta = self._two_people(tmp_path, monkeypatch)
        client.post("/api/crew", json={"name": "Alpha Only"}, headers=_auth())
        _upload(client, companion_id="alpha-only")
        assert (
            tmp_path / "users" / "primary" / "crew-portraits" / "alpha-only.png"
        ).is_file()
        # Beta cannot address Alpha's companion at all.
        assert (
            client.get("/api/crew/alpha-only/portrait", headers=_auth(beta)).status_code
            == 404
        )

    def test_hiding_a_starter_is_per_principal(self, tmp_path, monkeypatch):
        client, beta = self._two_people(tmp_path, monkeypatch)
        client.patch("/api/crew/bolt", json={"hidden": True}, headers=_auth())
        assert _crew(client)["bolt"]["hidden"] is True
        assert _crew(client, beta)["bolt"]["hidden"] is False

    def test_doorways_are_per_principal(self, tmp_path, monkeypatch):
        client, beta = self._two_people(tmp_path, monkeypatch)
        client.put(
            "/api/rooms/workshop/doorway",
            json={"doorway_id": "garden"},
            headers=_auth(),
        )
        assert _rows(client)["workshop"]["doorway"] == "garden"
        # Beta has no doorway at all — never Alpha's, and never a default.
        assert _rows(client, beta)["workshop"]["doorway"] is None

