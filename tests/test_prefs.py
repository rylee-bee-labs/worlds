"""Presentation preference invariants (owner accessibility floor).

Every default satisfies the floor; every rejected value is rejected
with a clear error; compact density can never shrink hit targets
below 44px; the dashboard applies preferences server-side with zero
JavaScript.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world import prefs  # noqa: E402
from personal_world.world import World  # noqa: E402


class TestDefaultsSatisfyFloor:
    """Defaults must meet the accessibility floor by construction."""

    def test_default_target_size_at_floor(self):
        assert prefs.PREFS["target_size"].default >= 44

    def test_default_motion_reduced(self):
        assert prefs.PREFS["motion"].default == "reduced"

    def test_default_contrast_comfortable(self):
        assert prefs.PREFS["contrast"].default == "comfortable"

    def test_default_text_scale_never_shrinks(self):
        assert prefs.PREFS["text_scale"].default >= 1.0

    def test_get_prefs_on_empty_world(self):
        assert prefs.get_prefs(World()) == {
            "motion": "reduced",
            "contrast": "comfortable",
            "text_scale": 1.0,
            "density": "comfortable",
            "target_size": 44,
            "companion": "assistant",
            "companion_id": None,
            "accent": "world-keeper",
            "tone": "warm",
            "personality_pack": "residents",
        }

    def test_every_spec_default_equals_normalize(self):
        defaults = prefs.normalize_prefs(None)
        for key, spec in prefs.PREFS.items():
            assert defaults[key] == spec.default


class TestFloorEnforcement:
    """Values below the floor are rejected, never clamped."""

    @pytest.mark.parametrize("value,why", [
        (0.9, "shrinks text below readable baseline"),
        (0.5, "shrinks text below readable baseline"),
    ])
    def test_text_scale_below_floor_rejected(self, value, why):
        w = World()
        with pytest.raises(prefs.PrefsValueError, match="text_scale"):
            prefs.set_prefs(w, {"text_scale": value})

    def test_motion_full_rejected(self):
        w = World()
        with pytest.raises(prefs.PrefsValueError, match="motion"):
            prefs.set_prefs(w, {"motion": "full"})

    def test_motion_off_accepted(self):
        w = World()
        data = prefs.set_prefs(w, {"motion": "off"})
        assert data["motion"] == "off"

    def test_motion_subtle_accepted(self):
        w = World()
        data = prefs.set_prefs(w, {"motion": "subtle"})
        assert data["motion"] == "subtle"

    def test_default_motion_reduced(self):
        assert prefs.normalize_prefs({})["motion"] == "reduced"

    def test_motion_reduced_accepted(self):
        w = World()
        data = prefs.set_prefs(w, {"motion": "reduced"})
        assert data["motion"] == "reduced"

    def test_target_size_below_44_rejected(self):
        w = World()
        with pytest.raises(prefs.PrefsValueError, match="target_size"):
            prefs.set_prefs(w, {"target_size": 32})

    def test_unknown_contrast_rejected(self):
        w = World()
        with pytest.raises(prefs.PrefsValueError, match="contrast"):
            prefs.set_prefs(w, {"contrast": "low"})

    def test_high_contrast_accepted(self):
        w = World()
        data = prefs.set_prefs(w, {"contrast": "high"})
        assert data["contrast"] == "high"

    def test_unknown_key_rejected(self):
        w = World()
        with pytest.raises(prefs.PrefsValueError, match="unknown preference"):
            prefs.set_prefs(w, {"hue": "neon"})

    def test_invalid_text_scale_value_rejected(self):
        w = World()
        with pytest.raises(prefs.PrefsValueError, match="text_scale"):
            prefs.set_prefs(w, {"text_scale": 1.1})

    def test_rejection_leaves_state_untouched(self):
        w = World()
        with pytest.raises(prefs.PrefsValueError):
            prefs.set_prefs(w, {"text_scale": 0.9})
        assert w.accessibility["text_scale"] == 1.0


class TestDensityTargetInvariant:
    """Compact density must never shrink interactive hit targets."""

    def test_compact_keeps_target_var_at_floor(self):
        css = prefs.prefs_to_css_variables(
            {"density": "compact", "target_size": 44}
        )
        assert int(css["--pw-target-size"].removesuffix("px")) >= 44

    def test_compact_cannot_override_smaller_target(self):
        css = prefs.prefs_to_css_variables({"density": "compact"})
        assert css["--pw-target-size"] == "44px"

    def test_target_size_only_increases(self):
        for size in (44, 56):
            css = prefs.prefs_to_css_variables({"target_size": size})
            assert int(css["--pw-target-size"].removesuffix("px")) >= 44

    @pytest.mark.parametrize("size", [45, 48, 64])
    def test_off_vocabulary_target_sizes_rejected(self, size):
        with pytest.raises(prefs.PrefsValueError, match="target_size"):
            prefs.set_prefs(World(), {"target_size": size})


class TestTextScaleVocabulary:
    """text_scale may only increase, over the closed set {1.0, 1.25, 1.5}."""

    @pytest.mark.parametrize("scale", [1.0, 1.25, 1.5])
    def test_allowed_scales_accepted(self, scale):
        w = World()
        data = prefs.set_prefs(w, {"text_scale": scale})
        assert data["text_scale"] == scale

    @pytest.mark.parametrize("scale", [0.9, 1.1, 1.75, 2.0])
    def test_off_vocabulary_scales_rejected(self, scale):
        w = World()
        with pytest.raises(prefs.PrefsValueError, match="text_scale"):
            prefs.set_prefs(w, {"text_scale": scale})

    def test_css_var_round_trip(self):
        w = World()
        prefs.set_prefs(w, {"text_scale": 1.25})
        css = prefs.prefs_to_css_variables(prefs.get_prefs(w))
        assert css["--pw-text-scale"] == "1.25"


class TestRoundTrip:
    """CSS variables and data attributes mirror the effective state."""

    def test_css_variables_keys(self):
        css = prefs.prefs_to_css_variables({})
        for var in ("--pw-motion", "--pw-contrast", "--pw-text-scale",
                    "--pw-density", "--pw-target-size"):
            assert var in css

    def test_data_attributes_keys(self):
        attrs = prefs.prefs_to_data_attributes({})
        for attr in ("data-pw-motion", "data-pw-contrast",
                     "data-pw-text-scale", "data-pw-density",
                     "data-pw-target-size"):
            assert attr in attrs

    def test_set_then_read_round_trip(self):
        w = World()
        prefs.set_prefs(w, {"text_scale": 1.5, "target_size": 56})
        p = prefs.get_prefs(w)
        assert p["text_scale"] == 1.5
        assert p["target_size"] == 56
        attrs = prefs.prefs_to_data_attributes(p)
        assert attrs["data-pw-text-scale"] == "1.5"
        assert attrs["data-pw-target-size"] == "56"

    def test_below_floor_stored_value_falls_back_to_default(self):
        # A corrupt/legacy stored value never propagates below the floor.
        w = World()
        w.accessibility = {"text_scale": 0.8, "target_size": 20}
        p = prefs.get_prefs(w)
        assert p["text_scale"] == 1.0
        assert p["target_size"] == 44


class TestStyleBlock:
    """The server-rendered CSS block carries the OS fallback."""

    def test_block_contains_custom_properties(self):
        block = prefs.prefs_style_block({})
        assert "--pw-text-scale: 1;" in block
        assert "--pw-target-size: 44px;" in block

    def test_block_contains_os_motion_media_query(self):
        block = prefs.prefs_style_block({})
        assert "@media (prefers-reduced-motion: reduce)" in block

    def test_block_is_style_tag(self):
        assert prefs.prefs_style_block({}).startswith('<style id="pw-prefs">')


class TestMotionTiers:
    """Motion vocabulary off|reduced|subtle with tiered CSS emission
    (P1 spec §3): keyed per-tier rules plus the unconditional OS
    override, last."""

    @pytest.mark.parametrize("motion,duration,ambient", [
        ("off", "0ms", "0"),
        ("reduced", "0ms", "0"),
        ("subtle", "200ms", "1"),
    ])
    def test_css_variables_per_tier(self, motion, duration, ambient):
        css = prefs.prefs_to_css_variables({"motion": motion})
        assert css["--pw-motion"] == motion
        assert css["--pw-motion-duration"] == duration
        assert css["--pw-motion-ambient"] == ambient

    def test_style_block_contains_all_three_tier_rules(self):
        block = prefs.prefs_style_block({})
        for tier in ("off", "reduced", "subtle"):
            assert f'[data-pw-motion="{tier}"] *' in block

    def test_os_media_query_is_unconditional_and_last(self):
        block = prefs.prefs_style_block({"motion": "subtle"})
        media_at = block.index("@media (prefers-reduced-motion: reduce)")
        subtle_at = block.index('[data-pw-motion="subtle"] *')
        assert subtle_at < media_at
        assert media_at > block.index('[data-pw-motion="reduced"] *')
        assert block.rstrip().endswith("</style>")
        assert "--pw-motion-duration: 0ms" in block[media_at:]
        assert "--pw-motion-ambient: 0" in block[media_at:]

    def test_subtle_rule_bounded_and_never_infinite(self):
        block = prefs.prefs_style_block({"motion": "subtle"})
        subtle = block[
            block.index('[data-pw-motion="subtle"] *'):block.index(
                "@media (prefers-reduced-motion: reduce)")
        ]
        assert "infinite" not in subtle
        durations = re.findall(r"(\d+)ms", subtle)
        assert all(int(d) <= 300 for d in durations)
        assert "var(--pw-motion-duration)" in subtle
        assert "animation-iteration-count: 1" in subtle

    def test_whole_block_no_duration_over_300ms_and_no_infinite(self):
        block = prefs.prefs_style_block({"motion": "subtle"})
        assert "infinite" not in block
        assert all(int(d) <= 300 for d in re.findall(r"(\d+)ms", block))

    def test_off_rule_disables_transitions_reduced_zeros_them(self):
        block = prefs.prefs_style_block({})
        off = block[
            block.index('[data-pw-motion="off"] *'):block.index(
                '[data-pw-motion="reduced"] *')
        ]
        assert "transition: none !important" in off
        reduced = block[
            block.index('[data-pw-motion="reduced"] *'):block.index(
                '[data-pw-motion="subtle"] *')
        ]
        assert "transition-duration: 0s !important" in reduced


class TestApiPrefs:
    """GET/PUT /api/prefs follow the existing envelope conventions."""

    @pytest.fixture()
    def client(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        from personal_world.api import create_app
        monkeypatch.setenv("PW_API_TOKEN", "t")
        app = create_app(tmp_path, tmp_path)
        c = TestClient(app)
        c.headers.update({"Authorization": "Bearer t"})
        return c

    def test_get_returns_defaults_when_unset(self, client):
        r = client.get("/api/prefs")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["target_size"] == 44
        assert body["data"]["motion"] == "reduced"

    def test_put_updates_then_get_round_trips(self, client, tmp_path):
        r = client.put("/api/prefs", json={"text_scale": 1.25})
        assert r.status_code == 200
        assert r.json()["data"]["text_scale"] == 1.25
        # persisted to world.json on disk
        import json
        stored = json.loads((tmp_path / "world.json").read_text())
        assert stored["accessibility"]["text_scale"] == 1.25
        assert client.get("/api/prefs").json()["data"]["text_scale"] == 1.25

    def test_put_rejects_below_floor_with_400(self, client):
        r = client.put("/api/prefs", json={"text_scale": 0.9})
        assert r.status_code == 400
        assert "text_scale" in r.json()["detail"]

    def test_put_rejects_motion_full_with_400(self, client):
        r = client.put("/api/prefs", json={"motion": "full"})
        assert r.status_code == 400
        assert "motion" in r.json()["detail"]

    @pytest.mark.parametrize("value", ["subtle", "off"])
    def test_put_motion_tier_accepted_with_200(self, client, value):
        r = client.put("/api/prefs", json={"motion": value})
        assert r.status_code == 200
        assert r.json()["data"]["motion"] == value

    def test_put_rejects_unknown_key_with_400(self, client):
        r = client.put("/api/prefs", json={"hue": "neon"})
        assert r.status_code == 400

    def test_prefs_require_auth(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        from personal_world.api import create_app
        monkeypatch.setenv("PW_API_TOKEN", "t")
        c = TestClient(create_app(tmp_path, tmp_path))
        assert c.get("/api/prefs").status_code == 401
        assert c.put("/api/prefs", json={}).status_code == 401

