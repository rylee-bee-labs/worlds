"""Parity between the documented preference schema and the backend
preference vocabulary (P1 spec §3 / T2).

Known, out-of-scope drift (T2 does not reconcile these): the schema's
"density" vocabulary (compact|comfortable|relaxed) and "targets"
(standard|large) differ from the backend's density (comfortable|compact)
and target_size numbers — reconciling them belongs to a later task, and
the frontend Settings UI is fed by GET /api/prefs/schema, not this file.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world import prefs  # noqa: E402

_SCHEMA_PATH = (
    Path(__file__).parent.parent / "docs" / "accessibility"
    / "PREFERENCES_SCHEMA.json"
)


def _schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text())


def test_motion_values_match_backend():
    schema = _schema()
    assert schema["schema"]["motion"]["values"] == list(prefs.MOTION.allowed)
    assert schema["schema"]["motion"]["default"] == prefs.MOTION.default


def test_contrast_values_match_backend():
    schema = _schema()
    assert schema["schema"]["contrast"]["values"] == list(prefs.CONTRAST.allowed)
    assert schema["schema"]["contrast"]["default"] == prefs.CONTRAST.default


def test_motion_floor_is_off_and_admits_all_tiers():
    # Ordered most-restrictive -> least, so the index-based floor check
    # admits every value in the vocabulary.
    assert prefs.MOTION_FLOOR == "off"
    allowed = prefs.MOTION.allowed
    assert allowed.index(prefs.MOTION.floor) == 0
    for value in allowed:
        assert prefs.MOTION.validate(value) == value
