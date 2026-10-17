"""Presentation preference state: the accessibility contract.

Every preference carries a default that satisfies the owner's
minimum accessibility settings, a closed set of allowed values (only >= minimum),
and the minimum itself. Values below the minimum are rejected, never
silently clamped. Application is native construction: the server
renders preferences into CSS custom properties and data-* attributes
so the dashboard honors them with JavaScript disabled.

Motion vocabulary (owner decision 2, P1 spec §3): "off" = no
nonessential animation, no ambient/idle movement, no decorative pose
transitions; "reduced" (default) = no continuous/ambient animation,
instant state/pose changes allowed; "subtle" = opt-in, transitions
<=300ms, never infinite. The OS prefers-reduced-motion setting always
overrides any application preference.
"""

import json
from dataclasses import dataclass
from typing import Any, Iterable

from . import crew

TARGET_SIZE_FLOOR = 44
"""Interactive targets >= 44x44 CSS px (WCAG 2.5.5 + Apple HIG)."""

MOTION_FLOOR = "off"


class PrefsValueError(ValueError):
    """Preference value below the minimum accessibility settings or outside the
    allowed vocabulary."""


class UnknownCompanionId(PrefsValueError):
    """``companion_id`` names no usable companion in this principal's crew.

    A distinct type because the write surfaces answer it differently from a
    below-minimum value: an unknown or hidden id is a 422 ("the roster is the
    vocabulary, and it does not have that"), not a 400. Resolution never
    relies on it — an id that stops resolving falls back to the one voice.
    """


@dataclass(frozen=True)
class EnumPref:
    key: str
    default: str
    allowed: tuple[str, ...]
    floor: str
    css_var: str
    data_attr: str

    def validate(self, value: Any) -> str:
        if isinstance(value, bool) or not isinstance(value, str):
            raise PrefsValueError(
                f"{self.key}: expected one of {list(self.allowed)}, "
                f"got {value!r}"
            )
        if value not in self.allowed:
            raise PrefsValueError(
                f"{self.key}: {value!r} is not an allowed value "
                f"(allowed: {list(self.allowed)})"
            )
        if self.allowed.index(value) < self.allowed.index(self.floor):
            raise PrefsValueError(
                f"{self.key}: {value!r} is below the minimum allowed value "
                f"({self.floor!r})"
            )
        return value


@dataclass(frozen=True)
class NumberPref:
    key: str
    default: float
    floor: float
    css_var: str
    data_attr: str
    allowed: tuple[float, ...] | None = None
    integer: bool = False
    unit: str = ""

    def validate(self, value: Any) -> float | int:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PrefsValueError(
                f"{self.key}: expected a number, got {value!r}"
            )
        num = float(value)
        if num < self.floor:
            raise PrefsValueError(
                f"{self.key}: {value!r} is below the minimum allowed value "
                f"({self.floor:g})"
            )
        if self.allowed is not None and num not in self.allowed:
            raise PrefsValueError(
                f"{self.key}: {value!r} is not an allowed value "
                f"(allowed: {[f'{v:g}' for v in self.allowed]})"
            )
        if self.integer:
            if num != int(num):
                raise PrefsValueError(
                    f"{self.key}: {value!r} must be a whole number "
                    f">= {self.floor:g}"
                )
            return int(num)
        return num

    def format(self, value: float | int) -> str:
        return f"{value:g}{self.unit}"


@dataclass(frozen=True)
class CompanionIdPref:
    """The chosen companion: a crew id, or ``None`` for the one voice.

    Companions are user-owned (owner decision 2026-09-25): the registry is
    per-person (``crew.py``), so this preference has no closed vocabulary of
    its own — the allowed values are *this principal's* roster, which is why
    the registry check lives here as an optional argument rather than in a
    frozen tuple. The shape check always applies: an id must be a slug
    (``crew.is_safe_id``), so a value that no roster could ever hold is
    rejected rather than stored.

    There is no below-minimum direction: ``None`` (no companion → the plain one
    voice) is the fail-safe default, and every failure — an unknown id, a
    hidden one, a deleted one, a malformed stored value — resolves to it.
    ``floor`` is carried as ``None`` for the shared schema shape only.
    """

    key: str
    default: str | None
    floor: str | None
    css_var: str
    data_attr: str

    def validate(
        self, value: Any, *, known_ids: Iterable[str] | None = None
    ) -> str | None:
        """``None`` or a crew id. ``known_ids`` = the principal's usable ids.

        ``known_ids is None`` means "the registry was not consulted" (the CLI
        validates shape at file time, with no principal in hand): the id is
        then only required to be shaped like a companion id. Resolution stays
        fail-safe either way — an id no roster holds yields the one voice.
        """
        if value is None:
            return None
        if (
            isinstance(value, bool)
            or not isinstance(value, str)
            or not crew.is_safe_id(value)
        ):
            raise PrefsValueError(
                f"{self.key}: expected null (the one voice) or a companion id "
                f"(a lowercase slug), got {value!r}"
            )
        if known_ids is not None and value not in set(known_ids):
            raise UnknownCompanionId(
                f"{self.key}: {value!r} is not a companion in your crew — "
                "choose an existing, unhidden companion (GET /api/crew), or "
                "null for the one voice"
            )
        return value


MOTION = EnumPref(
    key="motion", default="reduced",
    allowed=("off", "reduced", "subtle"), floor="off",
    css_var="--pw-motion", data_attr="data-pw-motion",
)
MOTION_TIERS: dict[str, dict[str, str]] = {
    "off":     {"duration": "0ms",   "ambient": "0"},
    "reduced": {"duration": "0ms",   "ambient": "0"},
    "subtle":  {"duration": "200ms", "ambient": "1"},
}
CONTRAST = EnumPref(
    key="contrast", default="comfortable",
    allowed=("comfortable", "high"), floor="comfortable",
    css_var="--pw-contrast", data_attr="data-pw-contrast",
)
TEXT_SCALE = NumberPref(
    key="text_scale", default=1.0, floor=1.0,
    allowed=(1.0, 1.25, 1.5),
    css_var="--pw-text-scale", data_attr="data-pw-text-scale",
)
DENSITY = EnumPref(
    key="density", default="comfortable",
    allowed=("comfortable", "compact"), floor="compact",
    css_var="--pw-density", data_attr="data-pw-density",
)
TARGET_SIZE = NumberPref(
    key="target_size", default=44, floor=44, integer=True, unit="px",
    allowed=(44, 56),
    css_var="--pw-target-size", data_attr="data-pw-target-size",
)
# `assistant` (owner, 2026-09-25) is the plain default helper with a
# screen for a face. `personal-world` is Sol, the Worlds mark: she has no
# voice, so choosing her means "no companion persona" (one plain voice).
COMPANION = EnumPref(
    key="companion", default="assistant",
    allowed=(
        "assistant", "personal-world", "mermaid", "robot",
        "world-tree-squirrel", "taco-news-truck",
    ),
    floor="assistant",
    css_var="--pw-companion", data_attr="data-pw-companion",
)
#: The chosen companion, by crew id (owner decision 2026-09-25, companions
#: addendum item 4). Supersedes the closed ``companion`` enum above: the
#: companion a person has is their own crew-registry entry, not one of six
#: fixed keys. ``None`` is the default and the fail-safe — no companion
#: persona, i.e. the plain one voice. ``companion`` stays readable and is
#: never rewritten or deleted in this slice (see
#: :data:`LEGACY_COMPANION_IDS` for the lazy one-time migration).
COMPANION_ID = CompanionIdPref(
    key="companion_id", default=None, floor=None,
    css_var="--pw-companion-id", data_attr="data-pw-companion-id",
)
#: Old ``companion`` enum value → crew id, where the canon has an equivalent
#: (COMPANION-CANON.md §1–§2: display name ↔ server key) and the starter crew
#: actually has that entry (crew.STARTER_CREW). Renai's canon key is
#: ``mermaid``, Bolt's is ``robot``, Ratatoskr's ``world-tree-squirrel``,
#: Scoop's ``taco-news-truck``. ``assistant`` (the plain default helper) and
#: ``personal-world`` (Sol, the Worlds mark, who has no voice — and is not a
#: crew entry) name no companion at all: they map to ``None``, the one voice.
#: A value absent from this map names nothing either — never an invented
#: persona.
LEGACY_COMPANION_IDS: dict[str, str | None] = {
    "assistant": None,
    "personal-world": None,
    "mermaid": "renai",
    "robot": "bolt",
    "world-tree-squirrel": "ratatoskr",
    "taco-news-truck": "scoop",
}
ACCENT = EnumPref(
    key="accent", default="world-keeper",
    allowed=("world-keeper", "rylee"),
    floor="world-keeper",
    css_var="--pw-accent", data_attr="data-pw-accent",
)
# Voice prefs (TRUE-NORTH § Voice, owner ruling 2026-09-22). These are
# phrasing/comfort prefs, not accessibility prefs: every value sits at
# or above the accuracy rule (warmth never costs exactness) and none
# touches the minimum accessibility settings. `tone` selects the register of the
# ONE Worlds voice; `personality_pack` gates the optional residents /
# two-voice character pack (kept canon: docs/CHARACTER-HANDBOOK.md,
# docs/COMPANION-CANON.md), ON by default since 2026-09-25 (owner:
# "turn it on"; PLAN.md 1b, personality ships now). The `floor` slot carries
# the default-safe first value (EnumPref requires one); there is no
# below-minimum direction here.
TONE = EnumPref(
    key="tone", default="warm",
    allowed=("warm", "concise", "playful", "formal"), floor="warm",
    css_var="--pw-tone", data_attr="data-pw-tone",
)
PERSONALITY_PACK = EnumPref(
    key="personality_pack", default="residents",
    allowed=("off", "residents"), floor="off",
    css_var="--pw-personality-pack", data_attr="data-pw-personality-pack",
)
PREFS: dict[str, EnumPref | NumberPref | CompanionIdPref] = {
    p.key: p
    for p in (MOTION, CONTRAST, TEXT_SCALE, DENSITY, TARGET_SIZE,
              COMPANION, COMPANION_ID, ACCENT, TONE, PERSONALITY_PACK)
}


def migrate_legacy_companion(legacy: Any) -> str | None:
    """The crew id an old ``companion`` enum value names, or ``None``.

    ``None`` here means "no companion — the one voice": both for a value the
    canon maps to nothing (``assistant``, ``personal-world``) and for a value
    the canon does not know at all. Never an invented persona.
    """
    if not isinstance(legacy, str):
        return None
    return LEGACY_COMPANION_IDS.get(legacy)


def companion_id_from(stored: dict[str, Any] | None) -> str | None:
    """The companion id a stored preferences dict names, or ``None``.

    The lazy one-time migration (companions addendum item 4): when
    ``companion_id`` is **absent**, the old ``companion`` enum is translated
    through :data:`LEGACY_COMPANION_IDS`. An explicit ``companion_id`` always
    wins — including an explicit ``null``, which is a person saying "the one
    voice", not a value to be overwritten by the old key. Nothing is written
    here: the old key is kept readable this slice, and the migration is
    materialized only when some other preferences write persists the
    effective state.
    """
    if not isinstance(stored, dict):
        return None
    if "companion_id" in stored:
        value = stored["companion_id"]
        return value if isinstance(value, str) else None
    return migrate_legacy_companion(stored.get("companion"))


def spec_schema(spec: EnumPref | NumberPref | CompanionIdPref) -> dict[str, Any]:
    """One preference spec as the read-only schema row both write surfaces
    publish (``GET /api/prefs/schema`` and ``personal-world do prefs
    schema``) — one implementation, so the two can never drift."""
    if isinstance(spec, NumberPref):
        return {
            "type": "number",
            "default": spec.default,
            "floor": spec.floor,
            "allowed": (list(spec.allowed) if spec.allowed is not None else None),
            "integer": spec.integer,
            "unit": spec.unit,
        }
    if isinstance(spec, CompanionIdPref):
        return {
            "type": "companion_id",
            "default": spec.default,
            "floor": spec.floor,
            "allowed": None,
            "integer": False,
            "unit": "",
            "note": (
                "a companion id from the caller's own crew (GET /api/crew), "
                "or null for no companion (the one plain voice). The "
                "vocabulary is the person's roster, so it is not a closed "
                "list here; an unknown or hidden id is refused."
            ),
        }
    return {
        "type": "enum",
        "default": spec.default,
        "floor": spec.floor,
        "allowed": list(spec.allowed),
    }


def coerce_value(key: str, raw: Any) -> Any:
    """Coerce a raw input (CLI string or JSON value) toward its type.
    Numbers arrive as strings from the CLI; anything unparseable stays
    a string and is rejected by the spec validator."""
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def normalize_prefs(prefs: dict[str, Any] | None = None) -> dict[str, Any]:
    """Effective preferences: absent or invalid stored values fall back
    to the accessible defaults, never to below-minimum values.

    ``companion_id`` additionally applies the lazy legacy migration
    (:func:`companion_id_from`) — but only for a stored dict that has no
    ``companion_id`` at all, so an explicit ``null`` is respected.
    """
    stored = prefs if isinstance(prefs, dict) else {}
    out: dict[str, Any] = {}
    for key, spec in PREFS.items():
        raw = companion_id_from(stored) if key == "companion_id" else stored.get(key)
        if raw is None:
            out[key] = spec.default
            continue
        try:
            out[key] = spec.validate(coerce_value(key, raw))
        except PrefsValueError:
            out[key] = spec.default
    return out


def get_prefs(world: Any) -> dict[str, Any]:
    """Effective presentation preferences for a World (settings absent
    -> defaults). Reads the world's accessibility settings; anything
    outside the contract falls back to the minimum-satisfying default."""
    stored = getattr(world, "accessibility", None)
    return normalize_prefs(stored if isinstance(stored, dict) else None)


def set_prefs(
    world: Any,
    updates: dict[str, Any],
    *,
    companion_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Validate and apply preference updates. Raises PrefsValueError on
    any unknown key, below-minimum value, or out-of-vocabulary value;
    nothing is applied unless every key validates.

    ``companion_ids`` is the caller's *usable* crew ids (existing and not
    hidden). The write surfaces that know the principal pass it, so an
    unknown or hidden ``companion_id`` is refused instead of stored; it is
    raised as :class:`UnknownCompanionId` (a PrefsValueError) so the API can
    answer 422 rather than 400. Callers with no principal in hand (the CLI)
    leave it ``None``: the shape is still checked, and resolution stays
    fail-safe. Unknown keys and other errors aggregate into one message, so
    the companion-id type is lost only when a companion-id error travels
    with an unrelated one.
    """
    if not isinstance(updates, dict):
        raise PrefsValueError("prefs must be an object of key -> value")
    stored = getattr(world, "accessibility", None)
    stored = stored if isinstance(stored, dict) else {}
    effective = normalize_prefs(stored)
    errors: list[str] = []
    unknown_companion = False
    for key, value in updates.items():
        spec = PREFS.get(key)
        if spec is None:
            errors.append(f"unknown preference {key!r}")
            continue
        coerced = coerce_value(key, value)
        try:
            if isinstance(spec, CompanionIdPref):
                effective[key] = spec.validate(coerced, known_ids=companion_ids)
            else:
                effective[key] = spec.validate(coerced)
        except UnknownCompanionId as e:
            unknown_companion = True
            errors.append(str(e))
        except PrefsValueError as e:
            errors.append(str(e))
    if errors:
        message = "; ".join(errors)
        if unknown_companion:
            raise UnknownCompanionId(message)
        raise PrefsValueError(message)
    if "companion_id" not in updates and "companion_id" not in stored:
        # Lazy legacy migration, post-update: a write that sets the old
        # `companion` key decides the new one too. It applies only when
        # neither the store nor this write has spoken about `companion_id` —
        # an explicit id (or an explicit null) always wins, and is never
        # overwritten by a legacy key the person may never have seen.
        effective["companion_id"] = migrate_legacy_companion(
            effective.get("companion")
        )
    store = dict(stored)
    store.update(effective)
    world.accessibility = store
    return dict(effective)


def prefs_to_css_variables(prefs: dict[str, Any] | None = None) -> dict[str, str]:
    """CSS custom properties (--pw-*). The target-size variable is
    clamped to the 44px minimum regardless of density, so compact can
    never shrink hit targets.

    An unset ``companion_id`` emits an empty value (valid for a custom
    property, and read as "no companion" rather than a name that is not
    there): the value is an id, never a presentation token.
    """
    p = normalize_prefs(prefs)
    out: dict[str, str] = {}
    for key, spec in PREFS.items():
        if isinstance(spec, NumberPref):
            value = p[key]
            if key == "target_size":
                value = max(int(value), TARGET_SIZE_FLOOR)
            out[spec.css_var] = spec.format(value)
        elif p[key] is None:
            out[spec.css_var] = ""
        else:
            out[spec.css_var] = str(p[key])
    tier = MOTION_TIERS[p["motion"]]
    out["--pw-motion-duration"] = tier["duration"]
    out["--pw-motion-ambient"] = tier["ambient"]
    return out


def prefs_to_data_attributes(prefs: dict[str, Any] | None = None) -> dict[str, str]:
    """data-* attributes for the document root element."""
    p = normalize_prefs(prefs)
    out: dict[str, str] = {}
    for key, spec in PREFS.items():
        value = p[key]
        if value is None:
            out[spec.data_attr] = ""
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            out[spec.data_attr] = f"{value:g}"
        else:
            out[spec.data_attr] = str(value)
    return out


def prefs_style_block(prefs: dict[str, Any] | None = None) -> str:
    """Server-rendered <style id="pw-prefs"> block: CSS custom
    properties, one keyed rule per motion tier (only the tier matching
    the effective data-pw-motion attribute applies), and the
    unconditional OS-level prefers-reduced-motion override, last. No
    JavaScript anywhere."""
    p = normalize_prefs(prefs)
    variables = prefs_to_css_variables(p)
    lines = "\n".join(f"  {k}: {v};" for k, v in variables.items())
    return (
        '<style id="pw-prefs">\n'
        ":root {\n"
        f"{lines}\n"
        "}\n"
        '[data-pw-motion="off"] * {'
        " animation: none !important; transition: none !important; }\n"
        '[data-pw-motion="reduced"] * {'
        " animation: none !important;"
        " transition-duration: 0s !important; }\n"
        '[data-pw-motion="subtle"] * {'
        " transition-duration: var(--pw-motion-duration) !important;"
        " animation-iteration-count: 1 !important; }\n"
        "@media (prefers-reduced-motion: reduce) {\n"
        "  :root { --pw-motion-duration: 0ms; --pw-motion-ambient: 0; }\n"
        "  * { animation: none !important; transition: none !important; }\n"
        "}\n"
        "</style>"
    )
