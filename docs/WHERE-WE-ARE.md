# Where we are

> **Status:** Current summary · **Canonical for:** nothing · **Current-state router:** [`.project/CURRENT.md`](../.project/CURRENT.md)

## The short version

Worlds has **two code lines on purpose** right now.

- `main` is the current/default pre-front-door application.
- `rebuild/front-door` is the clean next application.
- The rebuild is **not production** just because it is newer.

The new front door is far enough along that the remaining work is mostly
retirement, integration and cutover proof rather than "build the whole thing."

## What the new Worlds is

The stable landmarks are:

```text
Home · Connect · Memory · Settings
```

- **Home** brings useful things to you.
- **Connect** describes outside systems without making you learn their guts.
- **Memory** keeps what matters and can be searched/exported/restored without a
  model.
- **Settings** holds configuration and comfort.

Companions, Station and themes can change personality and presentation. They
do not get to rearrange the product underneath you.

Outside systems are providers. Worlds owns what they *mean*; the provider owns
how the mechanical call happens.

## What's true about production

The front-door rebuild has **not been cut over**.

A GitHub merge or published image is not enough to claim what is running.
The current live revision must be checked from the running instance.

If nobody has checked that evidence recently, live runtime state is
**UNKNOWN**, not "probably whatever main says."

## What's left

Two GitHub issues carry the current durable work:

- **#262** — finish the Phase 4 retirement/cutover-readiness work.
- **#263** — bring the applicable three `main` maintenance changes into the
  rebuild before cutover.

That is the work queue. Old handoffs and old PLAN sections are context, not
extra hidden chores.

## What needs your decision

**Nothing right now.**

The production cutover still needs your explicit approval when the rebuild is
actually ready and its checks are green.

Until then, agents can keep source work and verification bounded without
changing the running Worlds.
