# Worlds — Finish Line

> **Status:** Direction · **Verified:** 2026-09-26 · **Canonical for:** the target-experience detail where [`TRUE-NORTH.md`](./TRUE-NORTH.md) is silent · **Read this if:** you are planning toward "finished enough to live in every day" and need the experience-level target.

**In short:** what "finished enough to live in every day" means, at the
level of the experience rather than the code. It is direction, not a
promise that every idea ships. Where direction conflicts, newer wins:
[`.project/PLAN.md`](../.project/PLAN.md) (owner-approved 2026-09-25)
supersedes TRUE-NORTH on scope and sequencing, and TRUE-NORTH supersedes
this file; this file still does not override architecture, security,
accessibility, or human-reliability contracts. (Formerly "Personal World";
the filename and cross-links keep the historical identifier — technical
identifiers are unchanged.)

This document defines what “finished enough to live in every day” means for Worlds.

It is product intent, not a promise that every future idea belongs in the current release. When planning toward completion, this finish line outranks speculative roadmap items. Existing architecture, security, accessibility, and human-reliability contracts still apply.

> **First-release product language:** the section vocabulary below (Today, Journal, Vault, …) is refined for
> the first release by [`docs/PRODUCT-LANGUAGE.md`](./PRODUCT-LANGUAGE.md) (owner-approved 2026-09-21):
> *Today → Overview*, *Journal/Notes → Memory*, and **Records** (user information inside Memory) is distinct
> from **Vault** (secrets infrastructure). This finish line remains the target-experience authority; that
> contract is the current first-release language.

## Product goal

Worlds should be the place Rylee can stay in all day for the ordinary parts of her digital life.

It is not just a dashboard and not just a chat app. It is a personal operating environment that combines:

- a calm view of what needs attention and what Rylee was working on
- contextual chat everywhere
- lightweight native views of underlying systems
- deep technical detail on demand
- project and infrastructure management
- interests and discovery
- memory, journal, lore, and rewind/recovery
- a configurable vault and provider layer
- extensive customization without losing a coherent internal experience

The normal experience should feel simple, modern, cute, fun, and cohesive even when the machinery underneath is complex and replaceable.

## Core experience

### Today first

The home experience answers, in this order:

1. What needs me?
2. What was I working on?
3. What is coming up?

Deadlines, calendar items, important messages, failures, scheduled work, and active tasks should surface clearly.

Healthy systems should stay quiet. Overall status must always be easy to reach, but a happy system should not fill the home page with green noise.

Richer actions should be one click away.

### Main sections

The default information architecture is:

- Today
- Interests
- Media
- Projects
- Lab
- Journal / Memory
- Vault
- Settings

Sections should be hideable, reorderable, and extensible.

Chat is a layer across the product, not merely a single destination.

## Contextual chat and model routing

Every major surface should be able to provide its own chat context and tools.

A section may define a context profile or prompt template containing:

- the capability being used
- the current page/section
- the currently selected object, project, repo, service, artist, movie, etc.
- tools available in that context
- policies and approval rules
- preferred provider/model

Examples:

- Media chat understands and can use media capabilities such as Sonarr, Radarr, Lidarr, and Plex.
- Project chat understands the selected repository, CI state, runtime, logs, issues, and project docs.
- Lab chat understands services, health, deployments, and repair actions.

There should also be a global chat capable of crossing the entire Worlds when authorized.

Different capabilities may intentionally use different providers/models. Media discovery does not need the same brain as Git operations. Provider/model choice is backend policy and configuration, not hard-coded frontend behavior.

## Actions, approvals, and trusted automation

Worlds supports both:

- propose → explain → user approves → act
- user-defined trusted automation that may act within previously approved boundaries

When appropriate, the first approval flow may offer a clear “remember this setting” choice.

Remembered rules must be visible, editable, revocable, and journaled.

High-risk or destructive changes, access to sensitive vault material, and security-sensitive operations require stronger approval or step-up authentication. A remembered preference must not silently erase the security boundary for severe actions.

## Native mini-apps, not clones

Worlds should provide the useful everyday subset of the systems it integrates with.

Examples:

- source control, not a full Gitea/GitHub clone
- media management, not full Sonarr/Radarr/Plex clones
- health/status, not a Gatus clone
- deployment state, not a Komodo clone
- safe secret management, not a vault product clone

The native view should handle common daily work. Advanced or uncommon operations may open the original application.

Underlying systems should not be completely hidden. Worlds should make their important state understandable in an easy-to-digest form and expose the technical guts when requested.

## Projects workspace

Projects is a reusable mission-control shell.

Selecting a project or repository re-contextualizes the whole workspace to that project.

For the selected project, Worlds should be able to surface, when applicable:

- repository and branch state
- pull requests and issues
- current work and next tasks
- CI/test gates
- deployed version vs local/source version
- dependency and tool updates
- logs and runtime health
- releases
- relevant documentation and lore
- agent activity
- project-specific chat and tools
- safe build/test/deploy actions

Switching from Worlds to VEFR, Burrito Journalism, MUNR, or another project should reuse the same conceptual shell while loading that project’s own context and capabilities.

## Interests and Candy Dispenser

Worlds should contain a curated, non-critical discovery space for things Rylee enjoys.

This includes, for example:

- selected subreddits or community sources
- trans music discovery/pipelines
- new movies and music
- useful or interesting LLM/technology articles
- other explicit interests

The experience should support both:

- things Rylee explicitly follows/configures
- things Worlds predicts she may enjoy

Each item should support simple feedback such as thumbs up, thumbs down, save, and mute/not interested.

The system may learn from this feedback, but explicit preferences must remain inspectable and editable.

A chat surface should help build more complex interest rules or discovery feeds without requiring the user to hand-author every configuration detail.

## Lab and infrastructure

The Lab surface should provide a useful overview of the homelab without forcing Rylee into separate dashboards for ordinary work.

It should support:

- health and status overview
- attention/failure surfacing
- service details
- dependencies and topology where useful
- logs and diagnostics
- configuration/state inspection
- repair/restart/redeploy workflows
- add/change/remove services or integrations
- change where services/providers point
- clear links to the full underlying system when deeper work is required

Routine healthy infrastructure stays quiet; problems surface clearly.

Maintenance agents such as Tiny Gherkin should operate as bounded Worlds capabilities rather than as a separate destination.

## Memory, journal, lore, and rewind

Worlds must make it easy to recover context after time away.

Durable human-readable files, especially Markdown, are preferred as the canonical memory/lore layer where practical. Search indexes, vector stores, semantic caches, and derived indexes are acceleration and should be rebuildable rather than becoming hidden sources of truth.

The product should provide easy access to:

- journal/history
- memory and notes
- rylee_lore integration
- provenance
- “what changed?”
- “where was I?”
- tools for finding, correcting, superseding, or cleaning bad entries

The journal should make it possible to understand exactly what happened and why.

## Transparency and nerd mode

The default interface should be calm and easy to digest.

When requested, Worlds should become very technical.

Progressive disclosure may expose details such as:

- provider actually used
- model actually used
- selected capability/tool
- tool/API calls
- source and provenance
- latency and timing
- policies and approvals applied
- logs
- versions
- raw or near-raw responses where safe
- journal/audit events
- configuration lineage
- dependency relationships

Do not hide important uncertainty merely to preserve a clean UI.

## Vault and secrets

Worlds must include a usable native vault experience while preserving a provider-neutral secret boundary.

The UI should make it easy to use the built-in vault or connect/swap to an external vault provider without requiring an agent or manual code edits.

Secret values must remain protected from model context and ordinary UI rendering unless explicitly authorized for a secure workflow.

Sensitive vault access requires appropriate re-authentication/step-up behavior.

## Authentication and SSO

Authentication is a finish-line requirement, not a later nice-to-have.

Worlds should have a provider-neutral authentication layer capable of integrating with existing identity systems.

The first finished version must prove a secure real-world SSO path. Authelia may be one supported deployment, but the architecture must not depend on Authelia specifically.

The authentication boundary should be suitable for future clients, including a possible mobile app, rather than assuming browser-only access forever.

Requirements include:

- secure normal application sign-in
- external identity-provider compatibility
- step-up authentication for severe/destructive changes and sensitive vault/secure-note access
- recoverable bootstrap/break-glass access so an identity-provider outage cannot permanently lock out the owner
- session and authorization behavior that can later support other clients cleanly

Native multi-user operation, household sharing, and collaboration are not required for this finish line.

## Settings and extensibility

Settings is a first-class product surface, not an afterthought.

The product should expose coherent controls for as much of the Worlds as safely practical, including:

- section visibility/order/layout
- provider/model per capability or surface
- vault backend
- memory/search/index providers
- integrations
- themes
- companions
- visual layout and density
- accessibility preferences
- custom cards/widgets
- contextual prompt/templates
- automations
- approval policies
- trusted actions
- data sources
- notifications
- extension/component configuration

Extensibility itself is part of the product.

It should be possible to adapt useful interaction patterns or components from other tools into Worlds without turning the product into a pile of unrelated embedded web apps.

The user-facing experience should remain internally coherent even when implementation components are swapped.

## Visual and emotional requirement

Cuteness is non-negotiable.

Worlds should be:

- modern
- polished
- playful
- visually warm
- pleasant enough to want open all day
- technically dense when requested without feeling like a generic admin console

The companion system, artwork, motion rules, themes, typography, layout, and micro-interactions should make the application feel alive and personal while respecting the accessibility contract.

Pretty and capable are both requirements.

## Finish-line capabilities

The current major finish-line scope is:

- Today experience focused on attention, continuation, and upcoming work
- contextual chat across major sections
- global cross-system chat
- configurable provider/model routing per capability/surface
- interests/Candy Dispenser with explicit + learned curation
- Media native mini-app experience
- Lab/infrastructure management
- reusable project/repository mission-control workspace
- journal/memory/lore rewind and cleanup tools
- Markdown-first durable memory where practical, with rebuildable indexes/caches
- native vault UI plus external-vault provider support
- provider-neutral SSO/authentication with step-up security
- deep Settings/customization/extensibility
- safe approval + remembered-policy + trusted-automation model
- progressive disclosure into deep technical detail
- polished, cute, modern, accessibility-compliant UI
- green tests/CI and a verified deployable daily-use experience

## Explicitly allowed to wait

These do not block the current finish line:

- native mobile application
- household/general multi-user product experience
- public plugin marketplace

Voice is desirable. Include it in the finish-line implementation only if it can be added cleanly without destabilizing or significantly delaying the core experience; otherwise treat it as the first post-finish enhancement.

## Definition of done

Worlds is “finished enough” when Rylee can realistically choose it as her normal daily environment instead of routinely opening Homepage, source-control UIs, SOPS-over-SSH workflows, notes tools, separate media managers, infrastructure dashboards, and scattered project tools for ordinary tasks.

Opening a specialized upstream application should feel like an exception for deep or unique functionality, not the normal path.

The finished experience should make Rylee want to stay in it all day: calm when nothing needs attention, powerful when something does, deeply technical when she asks, flexible underneath, trustworthy about what happened, and cute enough to feel like hers.

## Guidance for planning agents

When asked to plan or finish Worlds:

1. Inspect the real current implementation before assuming roadmap items are missing.
2. Compare actual behavior to this finish line.
3. Do not redesign settled architecture without evidence that it blocks the finish line.
4. Prefer removing or consolidating infrastructure over adding layers.
5. Preserve provider-neutral boundaries and replaceability.
6. Break work into dependency-ordered, independently verifiable tasks.
7. Identify which tasks truly require frontier reasoning and which can be delegated to cheaper/faster implementation models.
8. Preserve accessibility, security, ownership, recovery, and human-reliability contracts.
9. Verify the running user experience, not only tests or successful commands.
10. Treat cuteness, polish, coherence, and desire-to-use as acceptance criteria, not optional finishing work.
