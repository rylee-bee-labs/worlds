# Common rules for every L-experience worker

Repo: React 19 + TypeScript + Vite, in `ui/`. New code lives only in `ui/src/fd/`. Tests live in `ui/src/test/fd-*.test.tsx` and are the spec: read them first.

Already written, read-only for you: `ui/src/fd/{types,fixtures,msw,api,route,prefs,home-model}.ts(x)` and every `ui/src/test/fd-*.test.*`. Do not edit them. If a test contradicts this brief, stop and say so in your final message.

Rules:
- Plain React function components, named exports, no new dependencies, no `any`, no default exports.
- Styling goes in `ui/src/fd/fd.css` (plain CSS, class prefix `fd-`). Use the existing tokens: `--pw-surface-*`, `--pw-text-primary|secondary|muted`, `--pw-border-*`, `--pw-spacing-*`, `--pw-radius-*`, `--pw-accent-*`. Never hard-code colours.
- Accessibility floors: body text 16px, labels at least 13px, interactive targets at least 44px (strip buttons at least 56px), a visible `:focus-visible` outline on every control, sentence-case headings, state is always shape + word (never colour alone), no animation unless inside `@media (prefers-reduced-motion: no-preference)`.
- Copy is plain and sparse. Use exactly: "Needs you", "Needs a look", "Pick up", "Your life", "Quietly working", "+ Add to Home", "Set up", "Optional", "Current", "Healthy".
- Missing values show "—", never 0. Never reorder content while the user is focused in it.
- Do not touch anything outside `ui/src/fd/` except where the brief names it.
- Acceptance command is in your brief. Run it before you finish and report its last lines verbatim.
