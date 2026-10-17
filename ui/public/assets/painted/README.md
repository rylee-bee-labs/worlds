# Painted icons (Station pack)

Copies of the B Classic sticker icon set from the private `design-system`
repo, `assets/icon-set/delivery/` at 63990f1 (Rylee-Bee's own art, cut from her
media library). Edit them there and copy again; never edit these.

`<id>-64.webp` is used up to 32 px, `<id>-128.webp` above it. Ids and meanings
come from `assets/icon-set/vocabulary.json` there.

Shown only with the Station experience pack, through `ui/src/fd/PaintedIcon.tsx`:
always beside a word, `alt=""` and `aria-hidden`, still images. Companion
presence uses Renai poses; status is always the word, never a picture.
