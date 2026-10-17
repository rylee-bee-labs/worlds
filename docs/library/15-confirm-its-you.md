---
title: Confirm it's you
kind: book
order: 15
for: everyone
short: Before something important, Worlds asks you to prove it's really you, then trusts that for five minutes.
---
Being signed in proves you were you when you signed in. That might have
been days ago, on a phone someone else can now pick up.

So before something important (changing a secret, adding a person,
changing who can do what), Worlds asks once more: **Confirm it's you.**

* * *

There are two ways, and Worlds offers the ones that work for you:

- **Your sign-in service:** Worlds sends you to sign in again, fresh. It
  accepts that only if the sign-in happened in the last two minutes, and
  only if it's the same person.
- **Your key:** type the key Worlds gave you.

After that, you're confirmed for **five minutes**, and then it asks again
next time.

* * *

**Only people can confirm.** An agent (a tool with a token) can never
confirm it's someone. So nothing important can happen by script alone.

When confirming sends you away to sign in, Worlds brings you back to the
page you were on, with one line saying you're confirmed.

* * *

## Words to know

- **Step-up:** asking for proof again before something important. Official terms: *step-up authentication*, *re-authentication*.
- **Session:** the time you stay signed in after signing in.
- **MFA:** proving it's you with more than one thing (a password plus a phone). Official term: *multi-factor authentication*. Your sign-in service may ask for it.
- **auth_time:** the time the sign-in service says you last really signed in.

* * *

## Under the hood

`require_step_up` guards writes to preferences, the Apps registry, identity and people, and vault `set`/`delete`. A step-up is a session grant bound to the person: `POST /api/auth/step-up` with the key, or the SSO path (`grant_oidc_step_up` in `auth.py`), which needs the provider's `auth_time` within the last 120 s and the same subject. It lasts 300 s. `step_up_methods` tells the UI which ways the person has (`key`, `sso`). Agents are refused ("step-up is person-only"). Canonical: `docs/ARCHITECTURE.md` (Auth).
