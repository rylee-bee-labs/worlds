# Worlds — Screen Reader Walkthrough

> **Status:** Current · **Verified:** 2026-09-26 · **Canonical for:** what a screen reader hears in the Worlds interface · **Read this if:** you use a screen reader, or you are changing labels, landmarks or focus in `ui/`.

**In short:** a walk through every screen as a screen reader announces it,
using the real labels from the code.

This walkthrough describes the current Worlds interface in `ui/` (the React
app that became the interface on 2026-09-22), at `main` `d9e9546` plus
"Ask about … in Chat" (#106) and "Find a room" (#107). It replaces the
walkthrough of the retired server-rendered dashboard.

Labels are **source labels**, read from the code, not a transcript of a manual
screen-reader session; announcement wording varies by browser and assistive
technology. The [Accessibility contract](ACCESSIBILITY_CONTRACT.md) remains
mandatory, and the Playwright suite (`cd ui && npx playwright test`: axe with
colour contrast on, keyboard, focus, reflow and reduced motion) is the
regression gate.

## Entry and landmarks

1. **Skip to main content** is the first focusable element and targets
   `#main-content`.
2. The **header** holds Sol's mark (decorative, hidden from assistive tech),
   the word **Worlds**, and navigation named **World navigation**. Inside it,
   the list **World landmarks** holds the stable skeleton (**Bridge**,
   **Memory**, **Chat**, **Settings**) and **Personal sections** holds the
   person's own sections (for example Interests, Projects). They are buttons;
   the current one carries `aria-current="page"`.
3. **main** is labelled with the page's name (**Bridge**, **Memory**,
   **Chat**, **Settings**, **Your crew**), and each page has one h1 (the
   Bridge's is visually hidden).
4. A **footer** status strip says the connection state in words ("Scanner
   online…").

Changing page swaps the main region and moves focus to the new page's h1, so
the reader starts at the top of what you chose. The first load leaves focus
alone (Skip to main content comes first), and a page that places focus itself
keeps it (Ask about a room in Chat lands in the message box). On a phone the
personal sections wrap onto their own row under the landmarks.

## Bridge (home)

Reading order follows the source: strip → first-day guide → lenses → star
map → needs panel → rooms.

- **Date strip**: date, local time, "since you were here", and the overall
  status in words (for example "1 system can't be reached", never a lone
  alarm word).
- **First day aboard** (a region named by its heading, "Welcome aboard, …"):
  spoken by the chosen companion ("Renai: …") or Worlds' plain voice. An
  ordered list of four lines; each says its state in words ("Done · 3 rooms
  connected", "4 of 6 answering", "Not yet"). **Put this away** hides it on
  this device; Settings brings it back. When everything is done, a region
  **You're all settled in.** appears once, then can be put away.
- **World lenses**: one button per system, each with its status word.
- **Star map** (region, visually hidden h2): each system is a button with a
  spoken label, never a URL. Artwork is decorative.
- **Needs you**: up to three items, then "and N more, quietly waiting".
- **Briefing panel**: the selected system's keeper line as text.

### Rooms

- A summary line in words ("1 room needs you · 2 quiet"). On a quiet day Sol
  rests beside it (decorative).
- **Doorway cards** (articles named by the room): "Needs you", the first need,
  "waiting since …", and the actions **Review "…" in a new tab**, **Open <room>
  in a new tab**, **Look inside <room>** and **Mark "…" as seen**.
- **Corridor** groups, each with its own heading: Also needs you · Unknown,
  unreachable or incompatible · Other rooms. Quiet rooms fold behind a button
  ("3 quiet rooms, all healthy · Show", `aria-expanded`).
- **Find a room** (12 or more rooms): a labelled search field. Its result is a
  status line tied to the field ("2 of 13 rooms below match "st"").
- Empty: "No rooms yet" with a **How rooms connect** disclosure.

### Room drawer

**Look inside <room>** opens a non-modal dialog named by the room, portalled
above the page. Focus moves to the room's heading; **Escape** closes it and
focus returns to the button that opened it (or to the Rooms heading if that
button is gone); the page behind stays usable. Sections, each with a heading:

- Needs you: each need with **Review "…"** and **Mark "…" as seen**. A
  Workshop approval also has **Approve or decline "…"**: a group named
  "Approve "…"?" opens with focus on **Not now**, then **Decline** and
  **Approve**. Sending says "Approving…" (status, static); only the room's
  receipt brings **Approved** (status, focused, under "Decided just now"). A
  refusal is an alert, "Nothing changed", with the room's reason and
  **Review again**.
- Changed since you last looked, then What <room> is showing, where the tone
  is a word: Good news · A small update · When you're ready.
- **Secrets** (Workshop only, the owner only): station health in words; asks
  from agents with **Enter <name> in Project Home, in a new tab**; key names in
  groups behind buttons with `aria-expanded`; what changed, in words. There is
  never a value field.
- Where this comes from, with **Technical detail** as a disclosure.
- Footer: **Open <room>** and **Ask about <room> in Chat**. The second opens
  Chat with an editable question in the message box; it is never sent for the
  person.

## Memory

h1 **Memory** with a one-line explanation, then the **journal** (write, draft
recovery with a conflict chooser that takes focus, and history) and
**records** (categories, matching records, and a record editor whose trigger
gets focus back when it closes).

## Chat

h1 **Chat**, the **Chat messages** log, the **Message input** textarea and
**Send message**. Errors are an alert with **Dismiss error**; a failed history
load offers **Retry loading conversation**. The chosen companion's picture is
decorative. A question from another screen arrives in the message box with
focus there, unsent.

## Settings and your crew

- h1 **Settings**, then the preference room, **Your crew** (with **Open your
  crew**), the first-day guide toggle, theme choice, and **Advanced** (the
  Vault tool). Toggle rows are real checkboxes with visible labels.
- **Your crew** (main labelled "Your crew"): the list of companions (each
  editable, hideable, and deletable if the person added it), a status line for
  saves and an alert for failures, **Your rooms** (a keeper select and a
  doorway select per room, named "Keeper for Studio", "Doorway for Studio"), and
  an "About your crew" complement (your companion, Sol, the rules). Portraits
  are decorative; names are always written.

### People

Only for people who run or help run the World (Settings shows **Open
people** only then). main is labelled **People**, h1 **People in this
World**. Each person is a list item: name (and "(you)"), then their role in
plain words ("Runs this World", "Helps run this World", "Has their own
space", "Has their own space, with limits", "Visiting"). **Change what
{name} can do** opens a group of that name with radio buttons, **Not now**
and **Save for {name}**; nobody sees a Change button for the owner or
themselves. A write that needs it shows **Confirm it's you** in place. People who sign in
through the provider get **Confirm with your sign-in** (focus on the "Confirm
it's you" line); it signs them in again and brings them back to the same page
with a status line, "You're confirmed for the next few minutes." People with a
sign-in key get focus on **Your sign-in key** (or **Use your sign-in key
instead** when they have both). Results are a status line ("Saved. Alex:
Helps run this World."); focus returns to the Change button. **Hand this
World over** (owner only) needs the new owner's name typed exactly before
**Hand over to {name}** is enabled. Programs are in a separate disclosure,
**Programs that act here**.

## First Light (first-run setup)

A separate page before the app: six steps, each with its own heading (Welcome
to your World · Getting things ready · How will you sign in? · Make yourself
comfortable · Pick a companion, or don't · Welcome aboard). Progress is
static text and dots; errors are inline next to the control they concern.
Its structure is covered by `tests/test_setup_wizard.py`.

## Live regions and restraint

Status lines use `role="status"` (saves, search results, loading words) and
failures use `role="alert"`. Nothing announces on a timer: no poll, clock or
companion announcements. Contract section 8's cadence (meaningful events only,
about one announcement per 30 seconds, bursts batched) is a requirement, not
a proven property of every region; verify cadence with real assistive
technology.

## Still to verify manually

- Real screen-reader output (VoiceOver, NVDA) for the drawer, the Find a room
  status and the first-day guide.
- Real VoiceOver output: follow `VOICEOVER_PASS.md` and note anything that
  differs from this page.
- Mobile sheets that trap focus and dangerous-action confirmations (contract
  sections 3 and 7) as they are added: they start on the safe action and say
  the consequence.
