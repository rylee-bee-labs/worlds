# Brain Templates — plain-markdown editing guide

> **Status:** Reference · **Verified:** 2026-09-26 · **Canonical for:** how brain/chat prompt templates are written, composed, and overridden · **Read this if:** you are editing chat prompt text or adding a persona/surface/task template.

**In short:** chat prompts are plain markdown files, not code. This page shows where they live (`config/prompts/`), the front-matter format, how `POST /api/chat` composes them, the read-only discovery API, and the edit workflow (edit the file, commit it — no restart, no code change).

First-class agent templates (decision #18): a small local brain (Qwen3
1.7B, ADR 0002) is kept on-task by the tool registry (hands) and these
templates (focus). **Templates are plain markdown files. Editing,
adding, or overriding one never requires a code change** — the registry
re-reads the tree on every chat call and every `GET /api/templates`.

## Where templates live

```text
config/prompts/
  core/       always composed, in sorted id order (identity, truth rules,
              tool-use discipline, uncertainty handling)
  personas/   companion personalities — composed as `persona.<name>`
              (e.g. `persona.mermaid`) only when the `personality_pack`
              preference is on (it is on by default) and the chosen
              companion has canon persona copy
  surfaces/   per-UI-route focus (surface.lab is composed when the chat
              caller reports route "/lab")
  tasks/      per-task focus (task.inspect, task.search, …), selected by
              compose(task=…) callers
  formats/    output-shape templates, selected by compose(format=…)
```

Private overrides: drop a file with the **same `id`** under
`config/prompts.local/` (git-ignored by convention). The override
replaces the shipped content; `/api/templates` and provenance report
what is actually in effect.

User template packs: additional markdown under
`data/template-sources/<pack-id>/` is composed when a caller selects
`packs=[<pack-id>]`.

## File format

YAML-ish front matter, then the markdown body that goes to the model:

```markdown
---
id: surface.lab
version: 1
kind: surface
surface: lab
description: One line for listings (optional; derived from the body otherwise)
max_tokens: 400
---
Prioritize:
1. what needs attention
2. why
...
```

Rules the registry applies:

- Files without `---` front matter are ignored (they are not templates).
- `id` defaults to the file stem; ids are the composition keys
  (`core.*` always, `persona.<companion>`, `surface.<route>`,
  `task.<name>`, `format.<name>`).
- `kind` is the template's role: `core`, `persona`, `surface`, `task`,
  `format`.
- Malformed front matter (e.g. non-integer `version`) is skipped, never
  fatal.
- Keep bodies small — `max_tokens` is a budget hint for a 1.7B context
  window, not an enforcement.

## How the chat loop consumes them

`POST /api/chat` composes:

```text
core.* (sorted)  →  persona.<companion pref>  →  surface.<route from the
chat context envelope>
```

and passes the result as the **persona lead** of the system prompt
(`build_chat_messages(..., persona=…)`). The built-in identity/truth
floor in `chat.py` always follows, so an empty or broken template tree
can never remove the safety text (status vocabulary, "never invent
state", the proposal-block contract).

## Read-only discovery API

```text
GET /api/templates          → {"ok": true, "data": {"templates": [
                                 {"id": "core.identity",
                                  "surface": null,
                                  "role": "core",
                                  "description": "…"}, …]}}
GET /api/brain/templates    → full metadata (version, max_tokens,
                              source, has_override, content_length)
GET /api/brain/provenance   → which templates composed, from where
                              (Nerd Mode)
```

All three are read-only and auth-gated. There is deliberately no write
API: templates are durable artifacts with Git history, edited as files.

## Editing workflow (no code, no restart)

1. Edit or add `config/prompts/<kind>/<name>.md` (or override it in
   `config/prompts.local/`).
2. `curl -H "Authorization: Bearer $PW_API_TOKEN" /api/templates` —
   the change is visible immediately.
3. Send a chat message; the next round-trip uses the new text.
4. Commit the file — Git is the template version history.
