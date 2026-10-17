# Preserved branch: `preserve/worlds-push-2026-10-13`

Status: **decided — no draft PR.** The branch is superseded by `main`. **Do not delete the branch.**

## Decision

Do not open a draft PR from `preserve/worlds-push-2026-10-13` (tip `37340cf`). Everything it adds
for the front door's Web Push, notify door and PWA is already on `main` through PR #310. The one
remaining line of difference would roll `main` back to an older Play-Nice pin, so it must not be
merged.

Governing decisions:

- 2026-10-13 issue #321: "Preserve legacy code until dependency/rollback evidence allows removal."
- Mission rule: "Never delete the branch." `preserve/worlds-push-2026-10-13` must survive this mission untouched.
- 2026-10-13 Rylee: "Not yet. Wanna get it cleaned up first then we design."

The branch stays as a rollback reference. Removing it is out of scope and needs the evidence that
issue #321 asks for.

## Comparison

Commit ranges (receipts from the coordinator, reproduced locally in the clone against `HEAD` = `786f506`,
which is the default-branch tip; this clone has no `origin` remote, so `origin/main` does not resolve):

- `git log --oneline HEAD..37340cf` (preserved commits not on main):
  - `37340cf fix(worlds): finish the front door's push, notify door and PWA`
  - `be324ac test(worlds): traversal tests assert nothing outside the static dir leaks`
  - `890edbf feat(worlds): the front door keeps Web Push, the notify door and the PWA`
- `git log --oneline 37340cf..HEAD` (main commits not on the branch):
  - `786f506 chore(contracts): re-pin Play-Nice to 3282097 (#311)`
  - `77e15a7 Front door: Web Push, the notify door and the PWA (#310)`
- merge-base: `0feda5d`
- `git diff --stat HEAD 37340cf`: one file, `.project/contracts/adoption.yaml | 2 +-`

So the three preserved commits are fully represented on main by #310, and `git diff HEAD 37340cf`
shows that all nine files they touch are byte-identical to main.

## Residual delta

The only difference is `.project/contracts/adoption.yaml`, line 11:

- branch (`37340cf`): `revision: 4805592360b777f89ddc789c85d8be0bd2c7b671` (2026-10-12 re-pin)
- main (`786f506`): `revision: 3282097ef51f53559bec5158fe42d5137b6917ee` (2026-10-13 re-pin, #311)

The branch's pin is the older one. Taking it would roll back #311 and is the reason this branch must
not be merged. Main's pin is newer and should be kept.

## File evidence on main

Read from `HEAD` (`786f506`):

- `src/personal_world/push.py:33-49`: no import of the old identity or auth layer. The module's
  imports are stdlib plus `.status`.
- `src/personal_world/push.py:116`, `:242`: quiet hours on by default, with `in_quiet_hours`.
- `src/personal_world/worlds/push_routes.py:1-5`: Web Push and notification routes for the front
  door, reusing `personal_world.push`.
- `src/personal_world/worlds/production.py:145`: `PW_STATIC_DIR` default.
- `src/personal_world/worlds/static_routes.py:12`: static directory resolved and confined.
- `tests/worlds/test_production.py:296`: `test_new_app_does_not_use_the_old_auth_stack`.
- `tests/test_compose_env.py:31`: `PW_STATIC_DIR` documented as the image's built-in UI.
- `ui/src/fd/Notifications.tsx:18`, `:45`: `navigator.serviceWorker` checked for support and used
  for registration.
- `ui/public/manifest.webmanifest:7-8`: Mulberry & Mint colours (`#291d30`).
- `.project/contracts/adoption.yaml:11`: the newer Play-Nice pin (see above).

## Next steps

- Keep `preserve/worlds-push-2026-10-13` untouched. Do not delete it.
- Do not merge or cherry-pick anything from it.
- Removal waits on the dependency and rollback evidence that issue #321 asks for.
