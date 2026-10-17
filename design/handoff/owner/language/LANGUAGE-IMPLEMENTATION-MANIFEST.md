# Project Worlds language implementation handoff

This manifest converts the audit into bounded changes. It is not authorization to change behavior. `Qwen-safe: yes` means an implementation model may make the exact isolated replacement and run the named checks. `No` means Sol/human review is required because copy and behavior are coupled, security-sensitive, destructive, or dependent on product intent.

## Final status — 2026-09-17 language pass closed (row-by-row audit)

Replaces the earlier interim status. Every row was re-verified against
the working tree on 2026-09-17 (search for the row's exact pre-change
text; changed files read; claims traced to commits). The table's
"current text" column remains the pre-change audit snapshot; the
per-row classification below is the post-pass truth:

**Implemented and verified (all LANG-):** 001–011 (station identity +
help terminology + shared labels; old strings absent repo-wide), 013
(manifest replacement verbatim at `api.js`), 014–017 (human-first
default with the old text retained only as technical detail — exactly
the manifest split), 018–020 (real source-control read; specimen
estate gone; `How project refresh would work` gate), 021 (specimen
panel unmounted `data-unused`; real API-005 read renders on the normal
route; the failure copy is verbatim in `real-data.js`), 022 (real
API-051 read; no specimen feed), 024–029 (browser-scope delete labels,
scoped confirmations, honest Vault-boundary wording; the scope-blind
"Clear everything" became "Delete everything saved in this browser"
behind a confirmation that lists the exact objects and the untouched
server side), 030–033 (030/031 evolved with the real chat wiring —
honest per-failure states instead of the preview-era copy; 032/033
verbatim), 034 (manifest reply + additive
`partial_findings` payload), 036–043 (backup step-up truth, CLI
disclosure, working-state prose, replace-labels, destructive modal with
Cancel-first focus per e2e), 044 (every documented OIDC failure family
mapped to what-happened + access-code fallback + operator detail; four
residual documented codes folded in at close), 045 (backup access-code
copy explains the OIDC-only limitation), 046–047 (presentation mapping
only; raw strings intentionally unchanged server-side), 050 (server-side
human message + operator code), 051 (client envelope split + backend
sanitized mapping; see residual note), 053 ("Open World assistant" —
decision taken: the trigger opens the real assistant), 054–057 (setup
prose verbatim), 059 (`rd-item-kind` rendered once per item; e2e bound).

**Already satisfied / superseded:** LANG-023 (the specimen dismissal
control it governed was removed entirely with 022's real surface; no
copy remains), LANG-048 and LANG-049 (provenance: no consumer — no
Station client calls `API-064-get` or the vault-unlock route, so the
raw server strings reach no user UI; the rows' "No" boundaries stand
unchanged and presentation mapping waits for a Vault UI), LANG-052
(owner wording applied at close after verifying packaging truth: the
container image COPYs the Station files and serves them at
`/station/`; "built SPA" is stale on both counts).

**Applied at close (small, verified completions of rows in flight):**
LANG-052 (station-not-installed copy), LANG-044 residual (4 remaining
documented codes), LANG-060 interests remainder (browser-local
interests add/remove now announces `Couldn't save this in your browser.
Nothing was saved…` instead of silently swallowing the failure;
journal and settings were already delivered).

**Intentionally unchanged (not skipped silently):**
- **LANG-012** — the actionable step-up gate (`api.js write()`) and the
  backup step-up failure both use "Confirm it's you…" copy; the generic
  403 fallback keeps its descriptive wording because a 403 with an
  unmapped detail cannot promise that confirmation would succeed.
  Owner call if they want a softer default there.
- **LANG-030/031 wording** evolved with the UX-01 wiring (real POST /
  per-failure honest states) rather than the preview-era replacement
  strings — the row's truth intent is met.
- **LANG-058 remainder** — absence strings for capabilities with no
  wired Station surface (chat/update) stay unmapped until those
  surfaces exist, per the lane's own consumer-first rule.
- **LANG-051 residual** — four `detail=str(ValueError-style)` answers
  remain on constrained admin/boundary surfaces (prefs value errors,
  identity user/agent creation, cemented-policy boundary); they are
  controlled prose, not raw provider exceptions. Per-domain human
  mapping of arbitrary backend exceptions stays open as the row
  intended.

**Open owner decisions (out of scope for copy work — smallest decision text):**
1. **Preferences authority** (LANG-035 beyond labels): keep the two
   labelled scopes, or design a single authority/bind-now model
   (API-030 has `gate: step-up`; server vocabulary is API-031).
2. **Interests authority model** (write path API-051-add is wired in
   the manifest but never called; the browser-local add forms and the
   server discovery list are two stores). Decide which store is
   authoritative and whether the estate wiring around API-036/079
   feeds it.
3. **Real OIDC step-up** (LANG-045's alternative path): implement an
   OIDC re-auth round-trip or keep the documented access-code-only
   limit. Related ops gap (recorded, deliberately not documented by
   this pass): the reverse-proxy step-up delegation env var
   (`PW_PROXY_STEPUP_SECRET`) and its fail-closed behavior are still
   undocumented in `env.example` / `docs/oidc.md`.
4. **Vault UI mapping** (LANG-048/049): when a Vault unlock/read UI
   exists, apply the manifest's human copy at its presentation layer.
5. **LANG-037 CLI instructions content**: disclosure exists; keeping
   its commands in sync is ongoing (CLI truth verified at close).

Severity glossary:

- **P0:** privacy/security wording may cause a person to trust a boundary that does not exist.
- **P1:** authority, destructive scope, product truth, or primary-task comprehension is materially wrong.
- **P2:** important consistency/recovery/progressive-disclosure problem.
- **P3:** polish.

## Replacement manifest

| ID | Severity | Surface / source | Exact current text or pattern | Proposed replacement | Reason | Qwen-safe |
|---|---|---|---|---|---|---|
| LANG-001 | P1 | Station shell; all six `design/opendesign-exploration/station/*.html` product headers | `Personal Worlds` | `Project Worlds` | Durable decision reserves Project Worlds for the product. | Yes |
| LANG-002 | P1 | Station document titles; all six Station HTML files | `<surface> — Personal Worlds` | `<surface> — Project Worlds` | Same identity contradiction in browser/history/tab text. | Yes |
| LANG-003 | P2 | `index.html` document title | `The Observation Deck — Personal Worlds` | `World — Project Worlds` | Identify the product/task first; keep Observation Deck inside the page if desired. | Yes |
| LANG-004 | P1 | Global help trigger; `station.js` | `Hail Assistant` | `Help & quiet mode` | The control opens help/low-demand choices, not assistant chat. | Yes |
| LANG-005 | P1 | Settings references to help trigger; `settings.html` | `Hail Assistant` and `I need help` | `Help & quiet mode` | Three labels currently refer to one control. | Yes |
| LANG-006 | P2 | Help dialog heading; `station.js` | `Okay. Less, for now. ✦` | `Choose a quieter view` | Say what the dialog does before tone. | Yes |
| LANG-007 | P1 | Help dialog reassurance; `station.js` | `Nothing is wrong and nothing is lost...` | `Choose the smallest view that helps right now. This changes what the Station shows; it does not delete your world.` | Avoid unchecked reassurance while preserving the useful consequence. | Yes |
| LANG-008 | P2 | Help restore action; `station.js` | `Bring my world back` | `Restore the normal view` | Name the actual display change. | Yes |
| LANG-009 | P2 | Shared unavailable label; `api.js` | `can’t reach it` | `can’t connect right now` | Avoid an unclear pronoun; surfaces should add the object. | Yes |
| LANG-010 | P2 | Shared stale label; `api.js` | `a while old` | `may be out of date` | “A while” is vague; every surface must also show last checked time. | Yes, label only |
| LANG-011 | P2 | Shared unknown label; `api.js` | `not sure yet` | `not known yet` | Preserve uncertainty without personifying the product. | Yes |
| LANG-012 | P1 | Shared 403; `api.js` | `That needs an elevation this session does not have.` | `Confirm it’s you before you continue.` | Human-first security action; “step-up” remains technical detail. | Yes only where confirmation can actually succeed |
| LANG-013 | P2 | Shared network error; `api.js` | `Could not reach the server.` | `Can’t connect to Project Worlds right now. Nothing on this screen was changed. Check the connection and try again.` | Add unchanged state and recovery. | Yes for read-only calls; review writes |
| LANG-014 | P2 | Unknown endpoint; `api.js` | `No endpoint called “<id>” is in the API manifest.` | `This feature is not available in this build.` Technical detail: `No endpoint called “<id>” is registered.` | Default copy should not require API vocabulary. | No; envelope needs human/detail fields |
| LANG-015 | P1 | Read/write guard; `api.js` | `<method> <path> is a write. Use PW_API.write() so the gate is checked.` | `This action was blocked before anything changed.` Technical detail retains the current message. | Internal developer instruction is exposed as user copy. | No; split default/detail fields |
| LANG-016 | P1 | Proposal execution guard; `api.js` | `This write only runs an already-approved proposal. Approve it first (PROP-approve)...` | `Approve this draft before running it. Nothing has changed.` | Preserve the authority boundary in human terms. | No; proposal UI must supply draft name and action |
| LANG-017 | P1 | Step-up guard; `api.js` | `This write needs an elevation (step-up). PW_API.elevate(token)...` | `Confirm it’s you before <action>. Nothing has changed.` | Remove implementation prose and bind the message to the requested action. | No |
| LANG-018 | P1 | Projects primary content; `projects-view.js` / `projects.html` | Entire specimen repository estate under `Your repositories` | Do not copy-edit. Replace the specimen estate with real API-backed states, or show one honest unavailable/not-set-up state with no sample repositories. | “As it actually is” currently fronts entirely fabricated sample repositories. | No |
| LANG-019 | P1 | Projects action; `projects-view.js` | `Propose refresh` / `gated · explains only` | Until wired: `How project refresh would work`. When wired: `Review refresh proposal`. | Current action label promises a proposal but opens only an explanation. | No; behavior/state dependent |
| LANG-020 | P2 | Projects reassurance; `projects-view.js` | `No command ran, no file changed, no repository was touched — not here and not anywhere.` | `This explanation did not run a command or change this repository.` | Scope certainty to what the handler can prove. | Yes |
| LANG-021 | P1 | Journal specimen panel; `journal-view.js` | `No journal is connected yet... specimen...` | Remove the specimen panel from the normal route. If the real journal call fails, show `Couldn’t load your journal. Your browser-only notes are still available below.` | Directly contradicts the live server journal above it. | No |
| LANG-022 | P1 | Interests specimen feed; `interests-view.js` | Specimen feed + `Preview state · prototype control` | Remove from normal use. Render real discovery data or the real `Not set up` / empty / unavailable state. | Prototype controls and sample discoveries leak into the product. | No |
| LANG-023 | P1 | Interests dismissal promise; `interests-view.js` | `In the real product, dismissed items stay away...` | `This removes the sample from this page only. It will return after a reload.` | Do not promise unimplemented durable behavior. | Yes while specimen remains |
| LANG-024 | P0 | Settings data statement; `settings.html` | `Everything is stored on this device. Nothing leaves unless you say so.` | `This section manages data saved by this browser. Server data and connected services are separate and are not cleared here.` | Current statement falsely describes the whole product’s storage/network boundary. | Yes as an interim safety correction |
| LANG-025 | P1 | Settings delete buttons; `settings.html` | `Clear journal entries`, `Clear interests`, `Clear chat log`, `Reset planet positions`, `Clear everything` | `Delete browser notes`, `Delete browser interests`, `Delete local chat history`, `Reset saved map positions`; remove `Clear everything` until exact scope is designed. | Labels hide browser-local scope and collide with real server data. | No; must confirm intended data model |
| LANG-026 | P1 | Settings confirmation; `settings.html` | `Clear <thing>? This cannot be undone.` | Pattern: `Delete <exact browser-local object>? This removes <scope>. It does not change <server data>. This cannot be undone.` Buttons: `Cancel` / `Delete <object>`. | Destructive confirmation lacks scope and unaffected-state truth. | No |
| LANG-027 | P1 | Settings success; `settings.html` | `✓ Cleared` | `<Exact object> deleted from this browser. <Relevant server data> was not changed.` | Result must name what changed and what did not. | No |
| LANG-028 | P0 | Journal local Vault tab/toggle/tag; `journal.html` | `Vault ✦`; `Keep this in the vault (private, not surfaced by the map)`; `✦ vault`; `Vault entries stay private` | Interim: `Notes on this device`; `Save only in this browser (not encrypted or synced)`; `browser-only`; `These notes are hidden from the map but are not encrypted.` | Browser `localStorage` is not the encrypted Vault; current copy creates a false security boundary. | No; human/Sol must decide whether to rename, encrypt, or remove |
| LANG-029 | P0 | Journal local save hint; `journal.html` | `Saved on this device. Nothing leaves unless you say so.` | `Saved in this browser only. This note is not encrypted or synced.` | State the actual boundary and remove absolute privacy certainty. | Yes as interim P0 correction |
| LANG-030 | P0 | Chat empty privacy text; `chat.js` | `Everything you say stays on this device. <companion> hears you, but replies come from the real capability...` | `Messages on this preview are saved in this browser. They are not sent to the World assistant.` | Current UI makes no chat API call yet; copy confuses preview storage with real provider behavior. | Yes as interim truth fix |
| LANG-031 | P1 | Chat send feedback; `chat.js` | `<companion> heard you. Replies bind to the real chat capability (API-010)...` | `Message saved in this browser. No assistant reply was requested.` | Current behavior only stores the message locally. | Yes as interim truth fix |
| LANG-032 | P1 | Ratatoskr greeting; `chat.js` | `Psst — I noticed some threads connecting lately. Want me to show you?` | `Want to look for connections between a few ideas?` | Do not claim an observation that was never made. | Yes |
| LANG-033 | P1 | Reminder template personality; `chat.js` | `Brisk and faithful; writes things down so you do not have to.` | `Helps draft reminder wording for you to review.` | The companion cannot persist a reminder without a proposal and approval. | Yes |
| LANG-034 | P2 | Tool-loop limit; `chat.py` | `I gathered some information but reached the tool call limit. Let me share what I found.` | `I reached the lookup limit before I could finish. I can share the partial results or try a narrower question.` | Current reply promises findings it does not include. | No; response payload should carry partial findings |
| LANG-035 | P1 | Preference split; `settings.html` / `real-data.js` | Device-only controls plus `What the server knows` mapping table | Do not copy-edit. Decide one authority or explicitly label two scopes: `This browser` and `Your Project Worlds account`, with separate save/results. | Copy exposes an unsynchronized behavior split that wording alone cannot repair. | No |
| LANG-036 | P1 | Backup auth failure; `backup-ui.js` | `Refused: this action needs step-up authentication — sign in again, then retry.` | `Confirm it’s you before creating or restoring a backup. Nothing was changed.` Then present the supported confirmation method. | “Refused” is blame-toned; “sign in again” is wrong for OIDC-only step-up. | No |
| LANG-037 | P2 | Backup unavailable; `backup-ui.js` | `Backup/restore is not available in this build... Use the CLI instead: ...` | `Backups are not available in this interface on this build.` Action: `Show command-line instructions`. | Human-first status, technical fallback on demand. | No; needs a disclosure/control |
| LANG-038 | P2 | Backup working state; `backup-ui.js` | `collecting the restore boundary and encrypting it` | `Collecting your world data and encrypting the backup. This may take a few seconds.` | Replace internal “restore boundary” vocabulary. | Yes |
| LANG-039 | P2 | Backup storage advice; `backup-ui.js` | `Copy it somewhere safe OFF this machine...` | `Save a copy on another device and keep the passphrase somewhere you can recover it.` | More concrete without manufactured urgency. | Yes |
| LANG-040 | P1 | Restore overwrite option; `backup-ui.js` | `Overwrite files that already exist here` | `Replace existing files during restore` plus a preview of affected categories/files. | “Overwrite” is technical and scope is opaque. | No |
| LANG-041 | P1 | Restore action; `backup-ui.js` | Always `Restore from archive…` | If overwrite off: `Restore missing files`. If on: `Review files to replace`, then confirmation action `Replace existing files and restore`. | One neutral button currently hides two materially different operations. | No |
| LANG-042 | P1 | Restore confirmation | No dedicated destructive confirmation when overwrite is selected | Add modal: `Replace existing files?` + exact preview + unaffected data + `Cancel` / `Replace <count> files and restore`; initial focus on Cancel. | Required by accessibility and destructive-action contracts. | No |
| LANG-043 | P2 | Restore working state; `backup-ui.js` | `the archive is authenticated BEFORE anything is written` | `Checking the archive before changing anything. A wrong passphrase will not change your world.` | Human wording first; retain authentication detail below. | Yes |
| LANG-044 | P1 | Login/OIDC error mapping; `login/index.html` | Only four OIDC codes have specific messages; all others use `Sign-in did not complete. Try again.` | Map every documented OIDC failure family to: what happened, access-code fallback, and operator detail code. | Security failures currently lose their recovery path. | No |
| LANG-045 | P1 | OIDC-only step-up | UI says `sign in again` or asks for an access code without explaining the limitation | `This action needs an access code. Signing in again with your provider cannot confirm this action yet.` | Preserve the current implementation limit honestly. | No; product decision may instead implement OIDC step-up |
| LANG-046 | P2 | Auth API session failure; `auth_routes.py` | `no session` | `Your sign-in expired. Sign in again.` | Human cause and next step. | Yes at presentation mapping, not raw API contract |
| LANG-047 | P1 | Auth API invalid step-up; `auth_routes.py` | `step-up credential invalid` | `That access code did not match. Nothing was changed.` | Plain, non-leaky, and confirms result. | Yes at presentation mapping |
| LANG-048 | P1 | Vault API client rejection; `api.py` | `vault GET is loopback-only (client=<address>)` | `Secret values can only be read from the Project Worlds host.` Technical logs may retain bounded diagnostic data. | Do not echo private topology/client address to the UI. | No; ensure logging remains safe |
| LANG-049 | P1 | Vault unlock; `vault.py` | `wrong passphrase or corrupt vault` | `The Vault could not be unlocked. The passphrase may not match, or the Vault file may be damaged. Nothing was changed.` | Separate causes without claiming which one and confirm unchanged state. | Yes at presentation mapping |
| LANG-050 | P2 | Backup one-time download; `worlds_backup.py` | `download token unknown, already used, or expired` | `This one-time download link is no longer available. Create a new backup to get another link.` | Human recovery first; token detail can remain technical. | Yes at presentation mapping |
| LANG-051 | P1 | Provider/backend exceptions; multiple API/provider files | Raw exception or provider reason passed into `detail` / first warning | `Couldn’t <action> <object>. <Unchanged state>. <Recovery>.` Put a sanitized code/class in technical details. | Raw errors can leak internals and rarely provide a usable next step. | No; requires per-domain mappings |
| LANG-052 | P1 | Station-not-installed failure; `station_ui.py` | `The packaged container image ships the API and the built SPA; the Station lives in the source tree's design directory.` | `This Project Worlds installation does not include the Station interface. The API is still available.` Operator details: `Set PW_STATION_DIST to the installed Station assets and restart.` | “Built SPA” is stale after the single-branch Station cutover. | Yes after verifying packaging truth |
| LANG-053 | P2 | Companion trigger accessible name; `station.js` | `Talk to <companion>, your companion — press to open chat` | If it opens assistant chat: `Open World assistant`. If it opens character chat only: `Open companion chat with <name>`. | Accessible name should name function, not contain operating instructions. | No; first decide assistant vs companion-chat semantics |
| LANG-054 | P1 | Setup welcome; `setup/index.html` | `Nothing is sent to anyone else's computer.` | `Setup information stays on this server. Services you connect later may receive the requests you choose to make.` | Absolute claim is incompatible with optional external providers. | Yes |
| LANG-055 | P1 | Setup footer; `setup/index.html` | `Everything you enter here stays on your own server.` | `The settings on this page are saved on your server. The sign-in server address is contacted only when you test or use that connection.` | Say when network contact occurs. | Yes |
| LANG-056 | P2 | Setup product description; `setup/index.html` | `Project Worlds is your own private dashboard.` | `Project Worlds is a self-hosted home for your projects, journal, tools, and connected services.` | Avoid promising a blanket privacy property; describe the product. | Yes |
| LANG-057 | P2 | Setup OIDC success; `setup_wizard.py` | `Success: that address is an OpenID Connect sign-in service and this server can talk to it.` | `Connection successful. This server can reach your sign-in provider.` Technical detail: `OpenID Connect discovery succeeded.` | Useful result first, protocol second. | Yes at presentation layer |
| LANG-058 | P2 | Provider “not configured” messages | `no <target/source/provider> configured` | `<Capability> is not set up.` Add `Set it up` only when a working path exists. | Canonical absence language and no developer noun leakage. | Yes with per-capability map |
| LANG-059 | P1 | Dynamic Needs-you list; `real-data.js` | The proposal kind line is rendered twice per item | Render it once. No copy replacement. | Duplicate reassurance/noise is a rendering defect discovered by the language audit. | Yes, but requires a focused regression test |
| LANG-060 | P1 | Settings/Journal/Interests local storage writes | Write helpers silently ignore storage failures but UI proceeds as if saved | On storage failure: `Couldn’t save this in your browser. Nothing was saved. Check browser storage settings and try again.` | Success must not be inferred when persistence failed. | No; behavior and error handling required |

## Behavior and UX problems exposed by copy

These are not solvable by prettier sentences:

1. The Station is the live product but Projects, Discoveries, parts of Journal, the map, and chat still run specimen/prototype behavior.
2. The browser-local journal and encrypted server Vault share the word **Vault** despite different security guarantees.
3. Settings destructive controls affect local storage only while visible labels imply product-wide data.
4. Device preferences and server preferences are two authorities with different vocabularies and no coherent save model.
5. Chat stores a message locally and then speaks as though a companion/real capability received it.
6. The overwrite restore path has no preview or dedicated destructive confirmation.
7. OIDC sign-in cannot perform step-up, but recovery copy commonly says to sign in again.
8. Multiple writes silently swallow browser-storage failures and can announce success anyway.
9. Technical disclosures are useful but often lead with API IDs, gate names, and implementation-stage registers rather than provenance a person can use.
10. Several live-region messages repeat reassurance already visible in the same component.

## Recommended implementation lanes

### Qwen mechanical lane

Only apply rows explicitly marked **Yes**, grouped into small commits:

1. Product identity: LANG-001–003.
2. Help terminology: LANG-004–008.
3. Low-risk state labels: LANG-009–011.
4. Interim truth/safety copy: LANG-023, LANG-024, LANG-029–033.
5. Backup prose polish: LANG-038, LANG-039, LANG-043.
6. Setup prose: LANG-054–057.
7. Presentation-layer mappings after exact call sites are confirmed: LANG-046, LANG-047, LANG-049, LANG-050, LANG-058.

Required checks for each lane: `node --check` for changed JavaScript, focused tests for the touched route/surface, `uv run pytest --timeout=30`, Playwright Station gates when a browser is available, and a diff review proving no behavior/semantics changed.

### Sol/human review lane

All P0 items and every row marked **No**, especially:

- local Vault naming/security boundary;
- local versus server deletion scope;
- specimen-to-real surface decisions;
- assistant authority and real chat wiring;
- server/device preference authority;
- restore overwrite preview/confirmation;
- OIDC step-up recovery;
- raw backend/provider error mapping.

Do not give these to a cheap model as global search-and-replace work.
