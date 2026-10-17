# Companion in Worlds

> **Status:** WIP (L-companion, spec slice 7) · **Verified:** 2026-10-15 against a fake Companion only · **Canonical for:** how Worlds talks to the private Companion service · **Read this if:** you are wiring Companion into Worlds or changing the panel

**In short:** Companion is a separate private service that owns the conversation. Worlds only proxies to it and shows the answers. Worlds is public, so nothing here names Companion's address, persona, threads or people.

**Conversation identity is independent of model/session identity.** A conversation must remain resumable when the underlying model, harness, or inference session is replaced, restarted, or rotated. Model/session identifiers are implementation details and must not become user-facing conversation identity or canonical storage keys.

## Setup (in your own config, never in git)

1. Mount Companion's client token for Worlds as a file, and give Worlds its path: `PW_COMPANION_TOKEN_FILE=/run/secrets/<file>`. The token is never in an environment value and never reaches the browser.
2. Add one provider file `worlds/providers/companion.yaml` in your config directory (the address below is a placeholder shape; use your real one):

```yaml
schema_version: 1
id: companion
name: Companion
kind: http
base_url: http://companion.lan.example:7600
auth:
  type: bearer
  secret_ref: file:PW_COMPANION_TOKEN_FILE
network:
  lan: true
```

`file:NAME` is a secret reference: the environment variable NAME holds the PATH of a file whose content is the secret. All calls go through the same confinement as every other provider (deadline, size cap, address checks; the LAN is allowed only because the provider says `lan: true`).

## What Worlds exposes (owner session only)

`POST /api/companion/turn`, `GET /api/companion/threads[/{id}?after=n]`, `GET /api/companion/context?q=`, `GET /api/companion/changes?since=`, `POST/GET/DELETE /api/companion/grants[/{id}]`, `GET /api/companion/health`.

- **Owner only.** An agent token gets 403. A cookie session also needs the CSRF header and an allowed Origin to change anything.
- **Whitelist both ways.** A request is rebuilt from the few fields the spec allows (a turn: `message`, `client_msg_id`, optional `thread_id`, optional `ui_context` with `quiet` and item text only). A response is rebuilt the same way: a stored turn's `context_items` and `context_canaries` are never forwarded.
- **`client_msg_id` is the idempotency key** and is passed through unchanged. Worlds neither retries nor caches.
- **No second chat store.** Nothing is written. Only counts are logged (message length, reply length), never text.
- **Unknown is an answer.** If Companion cannot answer, the reply is `502 {"state":"unknown","text":"Companion isn't answering.","reason":…}` with a fixed reason word; never a made-up reply, never upstream text. "Not set up" is `503`.
- **Worlds never decides a grant.** It forwards a request (always the `stepped` tier, 60 to 3600 seconds, with a reason) and shows the state; approval happens in Project Home.

## The panel

A quiet "Companion" button in the header opens a native modal dialog: a side panel on a desktop, a full-height sheet on a phone. It is not a fifth landmark. It shows the thread and a composer (sends `client_msg_id`; "thinking" is shown locally while a turn is in flight), each reply's withheld lines ("Some things were withheld: …") and level, "What Companion sees" (section counts, items, UNKNOWN lines), deeper access (state, "Approve it in Project Home" link, check, stop), and "Earlier conversations" (a list of old threads, newest last, shown read-only when opened).

`presentation/1` is mapped to a static pose word and an aria-hidden mark only (`ui/src/fd/companion/presentation.ts`); unknown values fall back to the defaults. Nothing animates.

**Earlier conversations:** The disclosure loads thread ids lazily on open (once per panel open). Each thread is shown as "Conversation N" with no invented titles. Choosing one shows that thread read-only in the same turn components; there is no composer for old threads. A "Back to the current conversation" button restores the live view and focus. Honest states: loading, empty ("No earlier conversations"), Companion down (Unknown + Try again), not configured. Nothing is stored in the browser or Worlds.

## One meaning of "Companion" (Settings)

**There is one Companion and it has one name.** It is the presence in the header, the panel it opens, and the
`/api/companion/*` routes behind both. Settings has a "Companion" section that reports that same thing from the
same `GET /api/companion/health` call, worded exactly as the panel words it, and (where the panel is mounted) one
button that opens that panel. Nothing else in the front door is an assistant, a persona or an install step.

The old Settings line "Assistant: Not installed" (from `docs/rebuild/foreman/briefs/T4.md`) came from the deleted
Station *World Assistant* drawer (`ui/src/components/WorldAssistant.tsx`, on the old-ui delete list). It described a
different, removed feature and was wrong to imply that the working Companion was missing. It is retired. The
Station-era "Assistant" in [`COMPANION-CANON.md`](COMPANION-CANON.md) — the plain default voice when
`companion_id: null` — is a character/crew concept, not the governed Companion of this document, and the front
door does not offer it.

What Settings shows, all of it measured, nothing invented (`ui/src/fd/companion/companion-status.ts`):

| State | Line | Next step |
|---|---|---|
| still checking | `Checking Companion…` | — |
| up | `Companion is up.` | — |
| up, some parts down | `Companion is up. Not answering: <names>.` | "Some parts aren't answering. Try again later." |
| no `companion` provider or token (503) | `Companion isn't set up.` | "Set the Companion provider up in Connect, then check again." |
| unreachable, refused or timed out | `Companion isn't answering.` | "Open the Companion panel to try again." |
| 401/403 (no owner session, agent token) | `Companion isn't answering.` | "Sign in as the owner, then check again." |

Settings makes **one** read (`GET /api/companion/health`) on open. It never asks for threads, context, grants or
receipts, so it cannot show anyone's content or imply a permission it was refused; the read/write boundary and
Project Home's authority over approvals are unchanged. The status line is a polite live region; the pose words and
marks stay decorative and `aria-hidden`, and the button is a native button (keyboard, focus, reduced motion) — no
Companion-only announcement is added.

Tests: `ui/src/test/fd-settings.test.tsx` (`npm --prefix ui run test -- Settings`). The permission side is already
regression-tested in `tests/worlds/test_companion.py` (`test_no_session_is_401_and_an_agent_token_is_403`, which
covers `/api/companion/health` and asserts nothing was sent upstream).
