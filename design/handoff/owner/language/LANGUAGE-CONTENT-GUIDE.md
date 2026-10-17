# Project Worlds language and content-design guide

Status: proposed canonical language system for the current product. This guide does not change product behavior, historical records, API schemas, or internal status values.

## The voice in one sentence

Project Worlds speaks like a calm, capable person who says the useful thing first, tells the truth about uncertainty, and leaves the technical door open without making someone walk through it.

## Voice principles

1. **Useful first.** Lead with what happened, what changed or did not change, and what the person can do next.
2. **Human first, sysadmin second.** Use ordinary language in the default view. Put provider names, routes, API IDs, gates, schemas, and raw evidence behind a clearly named technical disclosure.
3. **Calm, not falsely reassuring.** “No action needed” is good. “Nothing is wrong” is only valid after the relevant checks succeeded.
4. **Warm, not patronizing.** Invite; do not coach feelings, praise basic actions, or imply fragility.
5. **Technically honest.** Distinguish saved from validated, approved from run, observed from current, unavailable from empty, and unknown from healthy.
6. **Low pressure.** Quiet is a valid state. Never turn backlog size, sample content, or unfinished work into urgency.
7. **Specific recovery.** An error says what failed, what did not change, and the next useful step.

## Product and surface names

| Meaning | Canonical term | Do not use for this meaning |
|---|---|---|
| The product/environment | **Project Worlds** | Personal Worlds, Personal World |
| The spatial product interface | **the Station** after first use; otherwise “Project Worlds” | Observation Deck as the only identifying name |
| The overview route | **World** | Worlds, systems console |
| The decorative companion character reserved by the durable decision | **Personal World** | Project Worlds |
| The assistant function | **World assistant** | AI, brain, model, companion when authority matters |
| Character-flavored chat | **companion chat** | help, system status, authorization |
| The low-bandwidth help/quiet control | **Help & quiet mode** | Hail Assistant, I need help, assistant |
| Encrypted secret storage | **Vault** | browser-local private notes |
| Browser-only journal area, if retained | **Notes on this device** | Journal, Vault |

“Station,” “world,” “constellation,” and companion names may add atmosphere after the task is clear. They must not replace the noun a person needs to understand an action.

## Canonical state vocabulary

Internal enums remain unchanged. The first phrase below is the default human label; the second sentence gives the required meaning.

| Internal state | Human label | Required explanation |
|---|---|---|
| `healthy` | **All good** | “Checked <time>. No action needed.” |
| `needs_attention` | **Needs you** | Name the decision or action that only the person can take. |
| `warning` | **Worth a look** | Say what may matter and why it can wait. |
| `unknown` | **Not known yet** | Say what was not observed and how to check again. |
| `unavailable` | **Can’t connect right now** | Name the capability or service; confirm what still works. |
| `stale` | **May be out of date** | Always show “Last checked <time>.” Never replace the observed state with stale. |
| `not_configured` | **Not set up** | Absence is not failure. Offer setup only when a real setup path exists. |
| `disabled` | **Off** | Say whether the person turned it off or the reason is unknown. |
| loading | **Checking…** | Name the object when useful: “Checking your projects…” |
| empty | Context-specific: **No entries yet**, **Nothing needs you right now** | Claim emptiness only after the relevant source answered successfully. |
| working | **Working…** | Say what is being done and whether it is safe to leave. |
| blocked | **One more step is needed** | Name the step in human terms. |
| success | Past-tense result: **Backup created**, **Entry saved** | Include the scope/location when ambiguity is possible. |
| failure | **Couldn’t <action>** | Follow with unchanged state and recovery. |

Rules:

- Reserve **Needs you** for a real action or decision. A warning, stale observation, or unavailable provider does not automatically need the person.
- Use **quiet** only for a verified no-action or genuinely empty state. Unknown and unavailable are not quiet.
- Do not use multiple labels for the same state on the same screen.
- Do not show canonical enum names such as `not_configured` in the default reading layer.

## Action labels

Use `verb + object`, and add the scope when two stores or providers exist.

Good:

- Save note on this device
- Add interest to this device
- Delete local chat history
- Reset saved map positions
- Create encrypted backup
- Restore missing files
- Restore and replace existing files
- Review draft
- Approve draft
- Approve and run
- Confirm it’s you

Avoid:

- Enter, Proceed, OK, Yes
- Clear, Remove, Reset, Restore without an object or scope
- Propose refresh when the control only explains a future proposal
- “Real,” “live,” or “safe” as a substitute for saying where data came from and when it was checked

After an action, name the result: “Local chat history deleted. Server journal entries were not changed.” Do not use “✓ Cleared” alone.

## Errors and recovery

Use this order:

1. **What failed:** “Couldn’t create the backup.”
2. **What did not change:** “No backup was saved.” or “Nothing in your world was changed.”
3. **What to do next:** “Check the connection and try again.”
4. **Technical details:** error code, endpoint, provider response, exception class, or CLI command behind disclosure.

Do not expose raw exceptions, client addresses, private topology, secret identifiers, stack concepts, or provider payloads in the default message. Never blame the person with “refused,” “invalid,” or “bad” when “did not match,” “could not be verified,” or “is not supported” is accurate.

## Authentication and security language

- Use **Sign in**, not authenticate.
- Use **sign-in provider** first; put **OpenID Connect (OIDC)** in setup help or technical details.
- Translate step-up as **Confirm it’s you**. Example: “Confirm it’s you before replacing existing files.” Technical detail: “This uses a five-minute step-up grant.”
- A 401 is normally: “Your sign-in expired. Sign in again.”
- A 403 is action-specific: “You can view this, but you can’t <action> with this account.” If fresh confirmation can resolve it, say so.
- For OIDC failures, say whether the access-code fallback still works. Do not tell an OIDC-only user to “sign in again” when the actual action requires an instance access code.
- Security failures are plain and serious. No sparkles, mascots, jokes, or soft euphemisms.
- Never echo a client IP, host path, secret name, token, issuer topology, or raw provider error into ordinary UI copy.

## Destructive actions

Before the action, state:

1. the exact object and storage boundary;
2. what will be deleted or replaced;
3. what will not be affected;
4. whether undo or a backup exists;
5. the safe/cancel action first.

Example:

> Delete local chat history?
>
> This deletes messages saved by this browser. It does not delete server journal entries or provider history. This cannot be undone.
>
> Cancel · Delete local chat history

Never use **Clear everything**. Never make an overwrite checkbox silently change the meaning of a neutral **Restore** button. When overwrite is selected, the action label and confirmation must both say **replace existing files** and ideally show a preview.

## Assistant, model, and proposal authority

The assistant may:

- read the bounded context it is given;
- explain an observation and its timestamp;
- suggest a next step;
- draft a proposal;
- report that a tool returned a specific result.

The assistant must not imply that it:

- saw information that was not in context;
- remembers data not actually persisted;
- “hears” or processed a message when the UI only stored it locally;
- wrote, fixed, scheduled, approved, or ran something when it only drafted a proposal;
- has authorization because a person agreed in chat;
- can guarantee state outside the observed surface.

Canonical proposal sequence:

1. **Drafted** — “The assistant drafted a journal entry.”
2. **Waiting for your decision** — “Nothing changes until you approve it.”
3. **Approved, not run** — approval and execution remain separate.
4. **Running** — name the one approved action.
5. **Completed / Couldn’t complete** — state the observed result and evidence.

Use “Based on the last project check…” when freshness matters. Use “I don’t have that information” rather than guessing.

## Cute versus serious

Whimsy is welcome in:

- onboarding and orientation;
- true empty/quiet states;
- companion names and greetings;
- optional success flourishes;
- map atmosphere.

Whimsy stops at:

- sign-in and permissions;
- passphrases, secrets, and the Vault;
- destructive actions and overwrite;
- failures, degraded state, and unavailable services;
- approvals, execution, and authority boundaries;
- accessibility instructions.

Sparkles are decoration, never the only signal, and should not appear on dangerous actions or serious errors.

## Accessibility wording

- Visible and accessible labels must name the same action. Extra screen-reader context may add scope, not change meaning.
- Do not put operating instructions such as “press to open” inside a control’s accessible name.
- Decorative companion art remains hidden. The control is named for its function: “Open World assistant.”
- Live regions announce meaningful results, not routine polls, timestamps, companion moods, or every repeated reassurance.
- Loading text is static and concise.
- Placeholders are examples, never the only label.
- Avoid directional-only instructions such as “below” when responsive layout can change. Prefer “in Needs you” or “open Settings.”
- Use sentence case. Read symbols and emoji as decoration; hide them when they add noise.

## Progressive disclosure: human first, nerd second

Every complex surface should support four layers:

1. **Glance:** state and whether anything needs the person.
2. **Useful detail:** what happened, what changed, when it was observed, and the next action.
3. **Provenance:** provider/source name, observation time, decision history, and scope.
4. **Technical details:** endpoint, API ID, gate, canonical enum, raw bounded evidence, CLI recovery.

Example:

- Glance: “Projects may be out of date.”
- Detail: “Last checked 2 hours ago. Your last observed project state is still shown.”
- Provenance: “Observed by agent-sync from 5 repositories.”
- Technical: `API-079 GET /api/projects/status`; canonical state `stale`.

Technical depth stays available; it simply stops interrupting the first sentence.

## Content review checklist

- Does the first sentence say the useful thing?
- Are empty, unknown, unavailable, stale, disabled, and not set up distinct?
- Does “Needs you” correspond to a real decision or action?
- Does the copy name where data is stored?
- Does an action label name its object and scope?
- Does a destructive confirmation name consequences and unaffected data?
- Does success say what actually changed?
- Does failure say what did not change and what to do next?
- Is technical precision available without leading with jargon?
- Do visible and accessible labels agree?
- Does assistant language stay inside observed evidence and actual authority?
- Is whimsy absent from security, destructive actions, and failures?
- Is quiet allowed to remain quiet?
