# Why the build drifted from Figma — and what to change in future packs

> **Superseded in part by [ADR-0008](../adr/0008-front-door.md) (2026-10-01):** the Worlds interface was replaced by the front door (`ui/src/fd`: Home · Connect · Memory · Settings). Screen, component, route and test names in this document describe the old interface; read them as history. The current map is [FRONTEND-INVENTORY.md](../../FRONTEND-INVENTORY.md).

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see `.project/design/CURRENT.md`) · **Read this if:** you are writing a design/implementation handoff and want the 2026-09-11 postmortem on composition drift. · **Superseded by:** `.project/design/CURRENT.md`.

**In short:** a postmortem of why the built screens drifted from the Figma packs, and the process fixes proposed for later handoffs. Kept for provenance; it describes the pre-2026-09-22 `frontend/` tree, which has since been replaced by `ui/` and the retired server-rendered Station (now a theme package).

Written after a T14 UAT/recovery pass (2026-09-11). This is for you to hand to
the Figma AI (or any future design/implementation handoff) so the same drift
doesn't happen again. It is a postmortem, not a criticism of any one pass —
this is a known, common failure mode in iterative, multi-agent builds, and it
is fixable with process, not blame.

## The short version

Your **tokens** (color, spacing, type family names) survived perfectly —
`tokens:check` proves `frontend/src/tokens.css` matches `design/tokens.json`
byte for byte, right now. What did **not** survive was **composition**: the
shape/rhythm of a screen (list + divider vs. card-per-datum), density
("healthy stays quiet"), and personality placement (greeting-area companion).
Nothing enforces composition the way `tokens:check` enforces color. That gap
is the whole story.

## Root causes, specifically

1. **Only tokens were machine-checked. Composition was not.**
   `scripts/gen-tokens.mjs --check` fails a build if a color drifts. Nothing
   equivalent exists for "does this screen still look like its Figma frame."
   A rule like DESIGN-HANDOFF.md's "N.7: Do not turn every datum into a
   card" was written down, but nothing *runs* to catch a violation. Written
   rules without an automated or required visual check get lost over many
   build passes, especially across different implementers/sessions.

2. **A generic component library was sitting right there.**
   `frontend/src/components/ui/card.tsx` is an unmodified shadcn/ui `Card`.
   It's an extremely common, well-known pattern (especially in AI training
   data) — when someone (human or agent) needs to build a "section" quickly,
   reaching for `Card` is the path of least resistance, even when the design
   intent explicitly said not to. This is not malicious; it's gravity. The
   fix is either banning it via lint for status/summary sections, or naming
   in the handoff exactly which components `Card` may legitimately wrap
   (e.g., "only actionable feed items," never "any section with a heading").

3. **Multiple, differently-dated "canonical" documents existed at once.**
   `docs/DESIGN-HANDOFF.md` (V0.1 baseline, explicitly superseded in places),
   `docs/PERSONAL-WORLD-FINISH-LINE.md` (target, prose only, no images),
   `design/handoff/` (archived Figma export), and now the freshly re-exported
   Figma PNGs (which lived outside the repo entirely, in a separate folder,
   until this pass). An implementer or agent picking up work mid-stream has
   to guess which one is "the" reference *right now*. Prose rules survive
   this confusion much better than visual composition does, because prose
   gets read even when the picture doesn't get looked at.

4. **The written rules described intent, not pixels.**
   "Don't turn every datum into a card" tells you what NOT to do. It doesn't
   show you what the replacement should look like pixel-for-pixel (a heading
   + a quiet divider + a plain list). The Figma frames show that, but only
   if someone actually opens them at build time next to the code — and
   nothing in the process *required* that side-by-side comparison before
   merging.

5. **AI coding agents specifically need the visual reference inline, not
   just linked.** A rule buried in a markdown doc three files away gets
   missed. A rule paired with the literal reference image, named identically
   to the file being built, sitting where the agent is told to look first —
   that gets followed. This pass (mine) worked specifically because I was
   instructed to drive a real browser and compare against the Figma exports
   *before* delegating any implementation — that requirement should be
   standard for every future pass, not special to this one.

## What actually still needs the fix (the honest current state)

- **Today**: fixed this session — no more card chrome, real headings, quiet
  capability grouping, greeting + companion.
- **Lab**: already fine structurally — it renders a real `<table>`, not
  cards. Only worth a lighter check for "healthy stays quiet" density.
- **Journal, Vault, World**: still wrap sections in `Card` (3, 3, and 7
  usages respectively) — this is what I'm fixing next.
- **Settings**: intentionally denser/tabular per the Finish Line's own
  density guidance for that surface — not the same "mechanical" complaint.

## Concrete recommendations for future Figma packs / handoffs

1. **Ship a "wrong vs. right" composition board per screen type**, the way
   `today-generic-theme.png` vs. `today-rylee-theme.png` already did for
   theme — but explicitly for layout: one frame showing the card-per-datum
   anti-pattern, one showing the divider/list pattern, labeled as such.
2. **Name which components are load-bearing for "personality" vs. which are
   forbidden for status content.** e.g. "`Card` is reserved for Discovery
   feed items only. A status/summary section that uses `Card` is a build
   defect, not a style choice."
3. **Pair every screen's Figma export with a same-named file next to the
   code** (e.g., `design/screens/today.png` next to
   `frontend/src/screens/TodayScreen.tsx`) so an implementer/agent doesn't
   have to go hunting for "the current reference."
4. **Add a lightweight visual-regression gate** (even a simple Playwright
   screenshot saved to a reviewed folder, not necessarily a paid VRT tool)
   so composition drift gets flagged the same mechanical way color drift
   already does.
5. **Consolidate the "canonical right now" pointer to one place.** Right
   now three documents claim partial canonical status at different dates.
   One line at the top of the newest one — "this supersedes all of the
   above for visual composition, full stop" — removes the guessing.
6. **For any AI-agent implementation pass specifically**: require, as a
   hard step before writing code, "open the browser, open the Figma
   reference, compare, write down the differences" — exactly the process
   used for this pass. Bake that into the handoff instructions themselves,
   not just this one conversation.

None of this was a memory failure on your part — it's a process gap that
would trip up anyone managing a multi-session, multi-agent build. The fix is
structural (checkable composition contracts), not "try to remember better."
