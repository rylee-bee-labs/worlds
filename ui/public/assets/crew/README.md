# Crew art, web sizes

Web-sized WebP exports of the owner's crew art (2026-09-25). The full-size
masters live in `design/assets/crew/` (see its README); edit those, never these.

- `256/`: portholes, corridor thumbnails, pop-ups, nav marks (use for anything shown at 128 px or less)
- `512/`: doorways, drawer headers, empty states (anything shown larger than 128 px)

Contents: the Assistant (`assistant-portrait`, `assistant-listening`, `assistant-hello`; `assistant.svg` stays as a vector fallback), `sol-mark`, `sol-mark-mono`, `sol-badge`, Sol's moods (`sol-hello`, `sol-cheer`, `sol-reading` (the Library, 2026-09-27),
`sol-curious`, `sol-rest`); `renai-hello`, `renai-listening`, `renai-lantern`; portraits for
Bolt, Hekek, Ratatoskr, Bruma, Mira, Scoop; room interiors `room-worlds`, `workshop-doorway`,
`play-nice-doorway`, `vefr-doorway`, `memomancer-doorway`, `hive-works-doorway`.

The shared library (masters in `design/assets/library/`): 13 `doorway-*` interiors anyone can
choose for a room, and 16 `pick-*` faces anyone can give a companion they add.

This is the **starter crew**, not a fixed cast: people can add their own companions and
choose whether a room has one at all. Load from code with `import.meta.env.BASE_URL`
(see `ResidentPresence.tsx`) so a path-prefixed deploy still finds them. All art is
decorative: `alt=""` and `aria-hidden`, with the name in text beside it.

Sleepy night poses (Rough night page): `<key>-sleepy.webp` for renai, bolt, hekek, ratatoskr, bruma, mira, scoop and assistant, in 256/ and 512/. Masters: `design/assets/crew/sleepy/`.
