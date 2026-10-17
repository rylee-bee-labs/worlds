# VoiceOver pass

> **Status:** Current · **Verified:** 2026-09-26 · **Canonical for:** the guided screen-reader check a person runs by hand · **Read this if:** you are about to check Worlds with VoiceOver, or you changed labels, focus or live regions in `ui/`.

**In short:** a 20-minute script for checking Worlds with VoiceOver on a Mac
or an iPhone. Each step says what to do and what you should hear. Tick it, or
write down what you heard instead.

The automated suite (axe, keyboard, focus and reduced-motion tests) already
runs on every change. This pass is for what only a person can judge: whether
it sounds right, in the right order, without noise. Use a made-up or test
World if you can; nothing here changes anything unless a step says so.

## Before you start

- **Mac:** Safari, VoiceOver on with Command-F5. Move with VO (Control-Option)
  plus the arrow keys, open the rotor with VO-U, press buttons with VO-Space.
- **iPhone:** Safari, VoiceOver on in Settings → Accessibility. Swipe right
  and left to move, double-tap to press, and use the rotor (two-finger turn)
  for headings.
- Speech rate as you like it. Keep a note open for anything that sounds wrong.

Wording can differ slightly between VoiceOver versions. What matters is the
**order**, that every control has a **name**, and that nothing is **noisy**.

## 1. Arriving (2 minutes)

- [ ] Load Worlds. The first thing reached is **"Skip to main content, link"**.
- [ ] Next: the navigation **"World navigation"**, with the list **"World
      landmarks"** (Bridge, Memory, Chat, Settings) and **"Personal
      sections"**. The current page says **"current page"**.
- [ ] Open the rotor's headings list. There is one level-1 heading for the page.
- [ ] Nothing is announced by itself while you sit still for 30 seconds (no
      clock, no polling).

## 2. Changing pages (2 minutes)

- [ ] Press **Memory**. Focus lands on the heading **"Memory"**, and reading
      carries on from there.
- [ ] Press **Settings**, then **Open your crew**, then **Back to Settings**.
      Each time you land on the new page's heading.

## 3. Rooms and the room drawer (5 minutes)

- [ ] On the Bridge, find **Rooms**. A room that needs you is read as an
      article named for the room, with "Needs you" and what's waiting.
- [ ] Press **"Look inside Workshop"** (or another room). You hear a dialog
      named for the room, and focus is on the room's heading.
- [ ] Links that leave Worlds say **"in a new tab"** (for example
      "Review "…" in a new tab"). The small arrow icon is **not** read.
- [ ] Press Escape. The drawer closes and focus returns to the **Look
      inside** button you used.
- [ ] A room that isn't answering says so in words, with when it last
      answered. The lantern picture is not read.

## 4. Approving (4 minutes, needs a Workshop request)

- [ ] On a request, press **"Approve or decline "…""**. You hear a group named
      **"Approve "…"?"** and focus is on **"Not now"**.
- [ ] Press **Not now**. Focus returns to **Approve or decline**. Nothing was
      sent.
- [ ] Only if it's safe to approve: press **Approve**. You hear
      **"Approving…"** once, then **"Approved"** once, with the room's summary.
      If the room refuses, you hear **"Nothing changed"** and the reason.

## 5. The first-day guide (3 minutes, on a new World or after "Show the first-day guide" in Settings)

- [ ] The guide is a region named by its heading ("Welcome aboard, …").
- [ ] Each of the four lines is read with its state in words ("Done · 3 rooms
      connected", "Not yet"). The ticks are not read.
- [ ] **Put this away** hides it, and focus goes somewhere sensible (the next
      part of the Bridge), not to the top of the page.

## 6. People and confirming it's you (4 minutes, owner or admin)

- [ ] Settings → **Open people**. Each person is read with their name and what
      they can do ("Helps run this World"), never a role word like "admin".
- [ ] Press **"Change what Alex can do"**: a group of radio buttons. Choose one
      and **Save for Alex**.
- [ ] If asked, **"Confirm it's you"** appears with focus in **"Your sign-in
      key"** (or a button to confirm with your sign-in). After confirming you
      hear **"Saved. Alex: …"** once, and focus is back on the Change button.
- [ ] Cancel instead of saving if you don't want to change anything.

## When you're done

Write down, for each step that didn't match: the step number, what you did,
and what you heard. Put it in the design handoff doc under "Asks for design",
or send it to whoever is working on Worlds. Nothing else is needed.
