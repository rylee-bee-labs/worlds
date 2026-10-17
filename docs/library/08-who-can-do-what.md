---
title: Who can do what
kind: book
order: 8
for: everyone
short: Each person has a role, a role is a bundle of permissions, and some things only humans may do.
---
Worlds can be shared by a household. Each person has a **role**, and a role
is a bundle of **permissions**.

| Role | Can |
|---|---|
| Owner | Everything, including handing ownership to someone else |
| Admin | Approve things, manage people and rooms, see secret names, install updates |
| Member | Their own space, and what's shared with them |
| Supervised | The same as a member, for now |
| Guest | Only what's shared with them |

* * *

Every check in the code asks one question: "can this person do this?"
(`can(person, "approve")`). No screen decides on its own. An unknown role is
treated as the smallest one.

Sign-in can come from your own sign-in service (for example Authelia). Its
groups map to Worlds roles, so you manage people in one place.

* * *

**Helpers:** one person can help another, for example to see what's waiting
for them. They can act for them only if that was granted. Every grant has an
end.

**Agents** (tools with a token) get narrow scopes like "read" or "notify".
Approving, managing people, secrets and updates stay human actions: no
agent token can ever carry them.

* * *

## Words to know

- **Role:** owner, admin, member, supervised or guest.
- **Permission:** one thing you may do, like *approve* or *manage people*.
- **Principal:** whoever is asking: a person or an agent. Official term used in security.
- **Scope:** the narrow permissions an agent's token carries, like *read* or *notify*.
- **SSO / OIDC:** signing in with one account everywhere (Authelia, for example). Official terms: *single sign-on*, *OpenID Connect*.
- **Grant:** permission for a helper to see or act for someone, with an end date.

* * *

## Under the hood

Permissions: `own_space`, `see_shared`, `approve`, `manage_people`, `manage_rooms`, `estate_secrets`, `updates`, `transfer_ownership`. Every check goes through `can(principal, permission)` in `src/personal_world/roles.py`. Identity groups map to roles with `PW_ROLE_GROUPS` (e.g. `admin=admin,family=member`). Agent scopes can never carry `approve`, `manage_*`, `estate_secrets`, `updates` or `transfer_ownership` (`AGENT_SCOPE_PERMISSIONS`). Helper grants expire (`people.py`). Canonical: `docs/IDENTITY-BOUNDARY.md`.
