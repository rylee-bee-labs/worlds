"""One voice with selectable tone registers (TRUE-NORTH § Voice, owner ruling 2026-09-22).

The product speaks with ONE default voice — the World's voice from
``docs/CHARACTER-HANDBOOK.md`` §10(1): calm, plain, warm, technically
— across chat and attention surfaces. What the person selects
is a *tone register* (``warm`` default · ``concise`` · ``playful`` ·
``formal``), persisted through the existing preferences schema
(``prefs.TONE``) and applied to model prompting here.

The companion a person chats with is their own crew-registry entry
(owner decision 2026-09-25, companions addendum item 4): ``resolve_voice``
takes the ``companion_id`` preference and resolves it against *this
principal's* roster. A user companion's ``voice_label`` is phrasing only —
it may flavor wording, and it can never weaken the accuracy rule (no
invented facts, status words unchanged, the same safety and tone rules as
the one voice). An id that names nothing usable — unknown, hidden, deleted,
malformed — resolves to the one voice, never to an invented persona.

The residents and the two-voice system (CHARACTER-HANDBOOK §10(2),
``docs/COMPANION-CANON.md``) are preserved as an optional *personality
pack*: the ``personality_pack`` preference (default ``residents`` since
2026-09-25; the person can switch it ``off``) gates whether a companion
persona rides along in the chat prompt at all. Companion identities are
kept canon: a drawn companion keeps the persona template its canon names
(``config/prompts/personas/``); the rest of the crew is spoken by name.
Code and canon are kept, never deleted; only the routing is flagged.

Accuracy minimum is register-independent (PRODUCT-LANGUAGE.md principle 3:
warm in tone, exact in facts): a tone — or a companion's voice label —
changes phrasing, never exactness. Every phrasing instruction therefore
carries the same truth sentence, and the built-in identity minimum in
``chat.build_chat_messages`` (truth rules, status vocabulary, never invent
state) stays below it — so no register, voice label, pack, or
empty/malformed template tree can remove the safety text. Degraded and
model-off states are labeled in whatever voice is active; this
module never produces a reply itself.
"""

from dataclasses import dataclass
from typing import Any

from . import crew as crew_registry
from . import prefs as prefs_mod

TONES = ("warm", "concise", "playful", "formal")
"""The starter tone-register set (TRUE-NORTH § Voice; owner reacts on
experience). Order is preference order, not rank: no tone is 'better'
or more accessible than another — they are phrasing registers over an
unchanged accuracy rule."""

DEFAULT_TONE = "warm"

PACK_OFF = "off"
# Sol (legacy companion key `personal-world`) is the Worlds mark and has no
# voice (owner, 2026-09-25): she never becomes a chat persona. She is not a
# crew entry either — `crew.STARTER_CREW` deliberately excludes her — so the
# legacy key migrates to "no companion" (prefs.LEGACY_COMPANION_IDS). This
# set records the canon and guards the legacy path.
VOICELESS_COMPANIONS = frozenset({"personal-world"})
PACK_RESIDENTS = "residents"
"""Personality-pack vocabulary (prefs.PERSONALITY_PACK). ``off`` (the
default) speaks as the one Worlds voice; ``residents`` enables the
optional character crew (kept canon: CHARACTER-HANDBOOK.md,
COMPANION-CANON.md) as flavor on top of the same minimum."""

#: Crew ids whose canon names a persona template that actually ships in
#: ``config/prompts/personas/`` — the drawn companion keeps the voice the
#: canon gave it (COMPANION-CANON.md §2: Renai's server key is ``mermaid``,
#: which is the shipped template's id; her display name is Renai).
#: Deliberately tiny: the other drawn companions (Bolt, Hekek, Ratatoskr,
#: Bruma, Mira, Scoop) have no persona copy in the repo, and writing some
#: here would be inventing character text. They are spoken by name instead.
#: Adding a key means adding a template file.
STARTER_PERSONA_TEMPLATES: dict[str, str] = {"renai": "mermaid"}

# Each register's phrasing instruction. The shared truth sentence is
# appended by tone_instruction() so no register can drift away from it.
_TONE_INSTRUCTIONS: dict[str, str] = {
    "warm": (
        "Friendly, gentle, human cadence, ordinary words. Warmth never "
        "costs exactness: names, numbers, statuses, and uncertainty stay "
        "exactly as the context shows them, and a failure is said "
        "plainly and kindly — never softened into 'looks fine'."
    ),
    "concise": (
        "The shortest complete answer. Lead with the fact; drop "
        "pleasantries and filler. Never drop a status, number, caveat, "
        "or uncertainty the answer depends on."
    ),
    "playful": (
        "Light, friendly energy and gentle whimsy in phrasing. "
        "Playfulness never costs exactness, and serious things become "
        "plainer, not more theatrical."
    ),
    "formal": (
        "Measured, precise, professional prose; no slang or whimsy. "
        "State statuses and uncertainty plainly; never soften a failure."
    ),
}

_TRUTH_SENTENCE = (
    " This tone changes phrasing only: facts, statuses, and uncertainty "
    "stay exact, degraded and unavailable states are still labeled as such, "
    "and the accuracy rules below are unchanged."
)

_COMPANION_TRUTH_SENTENCE = (
    " This companion changes phrasing only: facts, statuses, and uncertainty "
    "stay exact, degraded and unavailable states are still labeled as such, "
    "and the accuracy rules below are unchanged."
)


def tone_instruction(tone: str | None) -> str:
    """The prompt block for one tone register.

    Unknown, empty, or absent tones degrade to "" — the identity minimum
    in ``chat.build_chat_messages`` (which is register-neutral) then
    speaks on its own,, rather than with an invented register.
    """
    body = _TONE_INSTRUCTIONS.get(str(tone or ""))
    if body is None:
        return ""
    return f"Tone register: {tone}. {body}{_TRUTH_SENTENCE}"


@dataclass(frozen=True)
class CompanionVoice:
    """One resolved crew companion — the entry as the roster holds it.

    Never invented: every field is copied from the registry entry
    (``crew.read_crew``). ``voice_label`` belongs to a user companion and
    is phrasing only; ``starter`` says whether this is drawn canon.
    """

    id: str
    name: str
    voice_label: str | None = None
    starter: bool = False


@dataclass(frozen=True)
class VoiceSelection:
    """What the chat prompt speaks with, resolved from preferences.

    ``persona`` is the persona-template name handed to
    ``TemplateRegistry.compose`` (``persona.<name>``) — the kept canon
    template for a drawn companion whose canon names one, and ``None``
    otherwise. ``companion`` is the resolved crew entry (``None`` means the
    one plain voice, which is the default and every failure mode) — the
    caller uses it for the companion's name and phrasing. ``tone`` is always
    a member of ``TONES``.
    """

    persona: str | None
    tone: str
    companion: CompanionVoice | None = None


def _find_companion(
    crew_state: Any, companion_id: str
) -> dict[str, Any] | None:
    """The roster entry with this exact id, or None. Never a fuzzy match.

    Accepts the registry state (``crew.read_crew`` output) or a bare list of
    entries, because both shapes reach callers in practice; anything else
    resolves to no companion rather than to a guess.
    """
    if isinstance(crew_state, dict):
        return crew_registry.find(crew_state, companion_id)
    if isinstance(crew_state, list):
        for entry in crew_state:
            if isinstance(entry, dict) and entry.get("id") == companion_id:
                return entry
    return None


def _resolve_companion(
    values: dict[str, Any], crew_state: Any
) -> CompanionVoice | None:
    """The chosen companion from ``companion_id`` and this principal's crew.

    Fail-safe in every branch: no crew state, no id, an unknown id, a hidden
    entry, a deleted one, an entry the registry cannot describe (no name) —
    each yields None, the one voice. The legacy ``companion`` enum is read
    only through the canon mapping (``prefs.companion_id_from``), so an old
    stored value keeps working without ever inventing a persona.
    """
    companion_id = prefs_mod.companion_id_from(values)
    if companion_id is None or companion_id in VOICELESS_COMPANIONS:
        # The canon's voiceless key (Sol, the Worlds mark) never becomes a
        # persona — not even if a hand-edited roster somehow carries that id.
        return None
    entry = _find_companion(crew_state, companion_id)
    if entry is None or entry.get("hidden") is True:
        return None
    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    voice_label = entry.get("voice_label")
    return CompanionVoice(
        id=companion_id,
        name=name.strip(),
        voice_label=(
            voice_label.strip()
            if isinstance(voice_label, str) and voice_label.strip()
            else None
        ),
        starter=crew_registry.is_starter(entry),
    )


def resolve_voice(
    pref_values: dict[str, Any] | None, crew_state: Any = None
) -> VoiceSelection:
    """Resolve the active voice from (already normalized) preferences.

    ``crew_state`` is *this principal's* crew registry state (the output of
    ``crew.read_crew``); without it no companion can be confirmed to exist,
    so the one voice is what comes back — the fail-safe direction.

    Fail-safe in every branch: missing or malformed values land on the
    defaults (one voice, warm), never on an invented persona, companion, or
    tone. Accepts the output of ``prefs.get_prefs`` but does not trust it —
    callers may pass raw dicts.
    """
    values = pref_values if isinstance(pref_values, dict) else {}
    tone = str(values.get("tone") or DEFAULT_TONE)
    if tone not in TONES:
        tone = DEFAULT_TONE
    companion: CompanionVoice | None = None
    persona: str | None = None
    if str(values.get("personality_pack") or PACK_OFF) == PACK_RESIDENTS:
        companion = _resolve_companion(values, crew_state)
        if companion is not None and companion.starter:
            # A drawn companion keeps the persona template its canon names,
            # when one ships; the rest of the crew is spoken by name below.
            persona = STARTER_PERSONA_TEMPLATES.get(companion.id)
    return VoiceSelection(persona=persona, tone=tone, companion=companion)


def companion_instruction(selection: VoiceSelection | None) -> str:
    """The companion's own identity line for the chat prompt, or "".

    Empty for the one voice, and for a drawn companion whose canon persona
    template already speaks for it (the template tree carries the voice;
    adding a second naming line would be noise). A user companion has no
    shipped template, so it is named here — and its ``voice_label``, which
    the person wrote, rides along as *phrasing*: it is collapsed to one line
    (a multi-line or backticked label must not restructure the prompt) and
    it is followed by the same truth sentence every register carries, so no
    label can widen the accuracy rule.
    """
    companion = (
        selection.companion if isinstance(selection, VoiceSelection) else None
    )
    if companion is None:
        return ""
    parts: list[str] = []
    if not selection.persona:
        parts.append(f"You speak as {companion.name}.")
    if companion.voice_label:
        label = " ".join(companion.voice_label.split()).replace("`", "'")
        if label:
            parts.append(f"Phrasing: {label}.")
    if not parts:
        return ""
    return " ".join(parts) + _COMPANION_TRUTH_SENTENCE
