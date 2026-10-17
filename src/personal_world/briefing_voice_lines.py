"""Voice lines for the Worlds briefing (contract v1, slice 1b "first light").

Pure data: the residents' situation templates and the World Keeper's mood
lines.  No I/O, no logic.  ``briefing_voice.py`` selects one line per
resident/situation (stable hash of date + system, so lines vary day to day
but not per refresh) and formats the two allowed placeholders.

Voice sources (read and followed faithfully)
--------------------------------------------
* ``docs/CHARACTER-HANDBOOK.md`` — §3 Ratatoskr (quick, mischievous, finds
  paths), §4 Bolt (plain, careful, allergic to shortcuts; no pronouns), §5
  Burrito Journalism (warm newsroom; background before breaking), §6 Personal
  World (the spirit of the place; expresses through light, distance, what has
  settled and what is waiting), §7 Hekek (plain, steady, maintenance as care),
  §8 Bruma (soft-spoken, deliberate, provenance, gentle memory), §9 Mira
  (bright, curious, forgetful, follows the clue), §10 the two voices, §11
  attention voices (GOOD NEWS · A SMALL UPDATE · WHEN YOU'RE READY).
* ``docs/COMPANION-CANON.md`` §1–§2 — resident display names and server keys
  (``robot``→Bolt, ``hekek``, ``bruma``, ``mira``, ``taco-news-truck``→Burrito
  Journalism, ``world-tree-squirrel``→Ratatoskr, ``personal-world``→Personal
  World, the World Keeper).
* ``docs/CREW-AND-STATION-THESIS.md`` §3 — family rules: companions never
  carry critical information (semantic state lives in UI text, these lines are
  flavor on top), quiet is a valid rendered state, urgency is not movement.
* ``docs/PRODUCT-LANGUAGE.md`` principle 3 — "warm in tone, exact in facts":
  a failure is stated plainly, never softened into "looks fine".
* ``../media_files/MEDIA_INDEX.md`` character notes (read-only) — per-character
  voice lines and the pronoun canon (Bolt: use the name, no pronouns).

Honesty floor
-------------
Only ``{arrivals}`` and ``{have_tos}`` may carry numbers, and only in the
situations where they are meaningful.  No line invents a fact, a time, or an
age.  ``not_configured`` says nothing is plugged in here yet; ``unavailable``
says the source could not be reached; ``stale`` says plainly that what is here
is old.  No guilt, no urgency theatre, no shame for having been away; every
line reads fine whether the count is 1 or many.
"""

LINES: dict[str, dict[str, list[str]]] = {
    # Bolt — Workshop (agents): Project Home bookmarks + attention items.
    # Plain and careful, allergic to shortcuts, competence without omniscience.
    # Bolt takes no pronouns, so these lines are recast around the name.
    "robot": {
        "arrivals": [
            "Bolt found {arrivals} new in the workshop while you were away.",
            "{arrivals} new since your last look. Bolt counted each one.",
            "The workshop shifted: {arrivals} new since you were here.",
            "Bolt counted {arrivals} new. Nothing urgent in the pile.",
        ],
        "have_tos": [
            "Bolt set {have_tos} aside for you. No rush on any of them.",
            "{have_tos} could use your call when you're ready.",
            "Bolt flagged {have_tos}. Wants them tidy, not lost.",
            "{have_tos} waiting on a choice. Bolt kept them tidy.",
        ],
        "quiet": [
            "Workshop is quiet. Bolt is just tinkering; nothing needs you.",
            "All clear here. Bolt is checking the same bolts twice, happily.",
            "Nothing new. Bolt is learning a new tool, if you're curious.",
            "Quiet in the workshop. Bolt is keeping busy anyway.",
        ],
        "not_configured": [
            "Nothing is plugged into the workshop yet, so there's nothing to read.",
            "No tools are hooked up here yet. Bolt is ready when they are.",
            "The bench is empty: nothing has been plugged in here yet.",
            "Bolt has no project feed yet. Once it's plugged in, Bolt reads it.",
        ],
        "unavailable": [
            "Couldn't reach the workshop just now. Bolt won't guess.",
            "No word from the workshop this time. Nothing invented to fill it.",
            "The workshop didn't answer. Bolt would rather say so than guess.",
            "Bolt couldn't reach the tools right now. That's all Bolt knows.",
        ],
        "unknown": [
            "Bolt isn't sure what's in the workshop yet. Still checking.",
            "No reading from the workshop yet. Bolt won't guess.",
            "The workshop is a bit murky. Bolt is looking into it.",
            "Bolt doesn't know this one yet. Asking again soon.",
        ],
        "stale": [
            "This is an old look at the workshop. Bolt hasn't refreshed it.",
            "Bolt's notes on the workshop are getting old. Take them loosely.",
            "What Bolt has is stale: true once, maybe not now.",
            "The workshop update is old. Bolt will re-check before trusting it.",
        ],
    },
    # Hekek — Engine room (estate): lab lowbw packet. Plain, steady, practical,
    # mildly gruff; maintenance as care, patch vs repair, no fuss.
    "hekek": {
        "arrivals": [
            "{arrivals} new in the engine room since your last walk-through.",
            "I logged {arrivals} new since you were down here last.",
            "{arrivals} came in while you were away. Nothing dramatic.",
            "The engine room picked up {arrivals} new. All logged properly.",
        ],
        "have_tos": [
            "{have_tos} for your eye, when you've the hands for it.",
            "I set {have_tos} aside for you. Steady does it.",
            "{have_tos} on the board for you. No rush at all.",
            "When you're ready: {have_tos} could use a decision.",
        ],
        "quiet": [
            "Engine room is steady. Just tending; nothing needs you.",
            "All quiet below. I'm oiling things that don't squeak yet.",
            "Nothing's asking for you. I like it that way.",
            "Everything's humming. I'm checking the joints anyway.",
        ],
        "not_configured": [
            "Nothing's hooked to the engine room yet. I'll tend it then.",
            "No machinery is wired in here yet. I can be patient.",
            "The bench is bare: nothing has been plugged in so far.",
            "No feed to the engine room yet. Nothing to read.",
        ],
        "unavailable": [
            "Couldn't reach the engine room this time. I won't pretend.",
            "The engine room didn't answer. Saying so beats guessing.",
            "No word from below just now. I'd rather be plain about it.",
            "I couldn't get a reading. That's the honest report.",
        ],
        "unknown": [
            "The engine room is unclear to me just now. Still looking.",
            "No reading yet. I won't dress it up.",
            "Something isn't reporting. I'm checking the wiring.",
            "I can't say yet what's below. Still listening.",
        ],
        "stale": [
            "This reading is old. I'd re-check before trusting it.",
            "My last look is getting stale. Take it gently.",
            "What I have is from earlier. Things may have moved since.",
            "Old numbers here. I'll refresh them when I can.",
        ],
    },
    # Bruma — Archive (records): the person's journal + pinned records.
    # Soft-spoken, deliberate, reassuring; provenance, gentle memory.
    "bruma": {
        "arrivals": [
            "{arrivals} new in the archive since your last visit.",
            "I shelved {arrivals} new since you were here.",
            "{arrivals} came to rest here while you were away.",
            "The archive gained {arrivals} new. All gently kept.",
        ],
        "have_tos": [
            "{have_tos} in the archive would like your eye, when ready.",
            "I set {have_tos} within reach for you.",
            "{have_tos} waiting on you. We can look gently.",
            "{have_tos} kept safe for when you have the time.",
        ],
        "quiet": [
            "The archive is restful. Nothing needs you right now.",
            "Everything here is settled. I'm reading quietly.",
            "Nothing is asking for you. We can just visit, if you like.",
            "All is calm in the archive. I kept it so.",
        ],
        "not_configured": [
            "Nothing is shelved here yet. I have an empty archive.",
            "No records are kept here so far; nothing is set up yet.",
            "The shelves are bare: nothing has been placed here yet.",
            "I have no archive here yet. It's ready when you are.",
        ],
        "unavailable": [
            "The archive didn't answer just now. I won't guess.",
            "I couldn't reach the records this time. Saying so plainly.",
            "No answer from the shelves. I won't invent what's on them.",
            "The archive is unreachable right now. I wish it otherwise.",
        ],
        "unknown": [
            "I'm not sure what's here yet. Looking carefully.",
            "No reading from the archive so far. I won't fill gaps.",
            "Some records aren't answering. I'm checking the index.",
            "I don't know yet, and I would rather say so.",
        ],
        "stale": [
            "These are older records. I'd check before trusting them.",
            "What I have is from an earlier chapter. True then, maybe not now.",
            "The archive's last note is stale. We can look another time.",
            "Old pages here. I still know where they came from.",
        ],
    },
    # Mira — Observatory (interests): discovery status. Bright, curious,
    # forgetful but never foolish; remembers the shape of an idea.
    "mira": {
        "arrivals": [
            "{arrivals} new in the observatory since you were last up here.",
            "Oh, {arrivals} new since your last look. Come see when you like.",
            "{arrivals} arrived while you were away. I nearly missed one.",
            "The sky moved: {arrivals} new. I made a note, mostly.",
        ],
        "have_tos": [
            "{have_tos} worth a look from you, when you're free.",
            "I found {have_tos} worth your eye. One's still tugging at me.",
            "{have_tos} waiting on you up here. No hurry at all.",
            "{have_tos} I want to show you. When you can.",
        ],
        "quiet": [
            "Nothing's pulling at me right now. The observatory is calm.",
            "All quiet up here. I'm watching a slow patch of sky.",
            "Nothing needs you. I'm tracing an old constellation anyway.",
            "The deck is still. I lost my notebook again, but it's calm.",
        ],
        "not_configured": [
            "No sources are set up here yet. Nothing to watch so far.",
            "The telescope has nothing to point at yet; nothing is configured.",
            "I've no interests hooked up yet. Show me and I'll follow.",
            "Nothing is plugged into the observatory yet. I'll wait.",
        ],
        "unavailable": [
            "Couldn't reach the observatory just now. I won't guess.",
            "The sources didn't answer. I'd rather say so than invent.",
            "No reading came through this time. Honest: I've got nothing.",
            "I couldn't get eyes on it. Saying so, not making it up.",
        ],
        "unknown": [
            "I'm not sure what's out there yet. Still looking.",
            "No reading so far. I remember the shape, not the facts.",
            "It's a bit foggy on the deck. I'm checking again.",
            "I don't know yet, but I wrote down where to look next.",
        ],
        "stale": [
            "This is an old look. The sky has likely moved since.",
            "What I have is stale: true a while back, maybe not now.",
            "My notes are getting old. Take the picture loosely.",
            "Old reading here. I'll re-check before I trust it.",
        ],
    },
    # Burrito Journalism (Scoop) — Newsstand (news): not wired in 1b.
    # Warm newsroom voice; background before breaking; the truck arrives.
    "taco-news-truck": {
        "arrivals": [
            "{arrivals} new since you were last at the newsstand.",
            "The truck rolled in with {arrivals} new. No shouting, promise.",
            "{arrivals} arrived while you were away. Paper's still warm.",
            "I parked with {arrivals} new stories for you.",
        ],
        "have_tos": [
            "{have_tos} worth a wander over, when you're ready.",
            "I set {have_tos} aside for you. Background first, always.",
            "{have_tos} waiting on you. No breaking-news energy here.",
            "{have_tos} for your eye. I'll keep the sign lit.",
        ],
        "quiet": [
            "Nothing worth interrupting you about. I'll just park nearby.",
            "Quiet newsstand today. Nothing's shouting, nothing's due.",
            "No stories need you. I'm restocking the snack shelf.",
            "All calm here. The paper can wait until you wander by.",
        ],
        "not_configured": [
            "No feed is plugged into this newsstand yet; nothing to report.",
            "I've no wire hooked up yet, so no stories to bring you.",
            "Nothing's connected here yet. The truck is parked, engine off.",
            "No news feed is set up for me yet, and I won't invent one.",
        ],
        "unavailable": [
            "Couldn't reach the wire just now. No paper today, honestly.",
            "The feed didn't come through. I won't make up headlines.",
            "No answer from the desk. I'd rather say so than guess.",
            "I couldn't get the story. That's the story right now.",
        ],
        "unknown": [
            "I don't know what's out there yet. Still checking the wire.",
            "No word so far. I won't print what I can't stand behind.",
            "The news is unclear just now. I'm waiting on the desk.",
            "I haven't a reading yet. Better empty than invented.",
        ],
        "stale": [
            "This paper's from a while back. Read it as history, not news.",
            "What I have is old. The world likely moved on since.",
            "Old edition here. True when printed, not necessarily now.",
            "My copy is stale. I'll get you a fresh one when I can.",
        ],
    },
    # Ratatoskr — World tree (threads): last place + last own journal thread.
    # Quick and a little mischievous; carries messages, finds paths.
    "world-tree-squirrel": {
        "arrivals": [
            "{arrivals} new along the branches since you last ran by.",
            "Quick: {arrivals} new since your last visit to the tree.",
            "{arrivals} arrived while you were away. I tracked each one down.",
            "The leaves turned up {arrivals} new. I carried each one down.",
        ],
        "have_tos": [
            "{have_tos} at the base of the tree, waiting on you.",
            "I stashed {have_tos} for you. A path runs through each one.",
            "{have_tos} waiting for a nudge from you, when ready.",
            "{have_tos} I've been carrying. Want a look?",
        ],
        "quiet": [
            "The branches are quiet. I'm just running laps for fun.",
            "Nothing needs you here. I'm napping in the high leaves.",
            "All still on the tree. I hid an acorn and forgot where.",
            "No messages today. Nice to just sit in the branches.",
        ],
        "not_configured": [
            "Nothing is tied to the tree yet. No threads to run along.",
            "No paths are hooked up here yet. I've nothing to carry.",
            "The tree's bare on this side: nothing is plugged in yet.",
            "No threads set up here yet. I'll perch till there are.",
        ],
        "unavailable": [
            "Couldn't reach the tree this run. I won't make up a path.",
            "The branches didn't answer. Better honest than clever.",
            "No word from the tree. I'd rather be plain about it.",
            "I couldn't get up there just now. That's all I've got.",
        ],
        "unknown": [
            "I don't know this part of the tree yet. Still climbing.",
            "No reading so far. I won't invent a path to fill it.",
            "The branches are foggy. I'm sniffing around.",
            "Haven't found it yet. Give me a moment to check.",
        ],
        "stale": [
            "This is an old path. It may not run the same way now.",
            "What I have is stale: true once, maybe grown over since.",
            "My map's gone a bit old. Let me re-run the branches.",
            "Old scent here. I'll double back before trusting it.",
        ],
    },
}

# The World Keeper — Personal World (server key ``personal-world``).
# The spirit of the place (CHARACTER-HANDBOOK §6): it speaks through light,
# distance, what has settled and what is waiting, and says little.  Keyed by
# the briefing's Keeper mood.  No numbers here: the Keeper's voice is
# atmosphere, and the counts live in the systems' own lines.
KEEPER_LINES: dict[str, list[str]] = {
    "greeting": [
        "Hello. This is yours, and everything here is where it belongs.",
        "Welcome. The world is quiet, and yours to wander.",
        "Here you are. Nothing is waiting on you yet.",
        "Good to see you. The place is calm and open.",
    ],
    "calm": [
        "All is quiet. What's near you is near; what can wait, can wait.",
        "Nothing needs you. The world is settled and warm.",
        "Everything has settled for now. Take your time.",
        "The world is still. Rest here a while, if you like.",
    ],
    "busy": [
        "A few things have settled near you, waiting when you're ready.",
        "There's some weight here, but no rush on any of it.",
        "The world holds a little for you. It will keep.",
        "A couple of things are waiting. Only when you want them.",
    ],
    "sleepy": [
        "It's late here. The lights are dim, and nothing can't wait.",
        "The world is dozing. Whatever's here will keep till morning.",
        "Quiet hours. Settle if you like; the place is still.",
        "Late and low-lit. Nothing is asking anything of you.",
    ],
    "celebrating": [
        "A few things drifted in while you were away. Nice to see them.",
        "The world gathered a little while you were gone. Welcome back.",
        "Something new has settled here. Glad you're seeing it.",
        "A little has arrived. The place feels a touch brighter.",
    ],
}
