"""Roles and permissions (owner-approved 2026-09-26).

Step 1 of the roles plan: code asks ``roles.can(principal, permission)``
instead of checking a role name; each person carries a ``role``; sign-in
maps Authelia groups to roles; and the owner-only checks (identity admin,
room writes, secrets overview) become permissions.

Everything here uses **made-up people** — no real name, username or email
appears in this repo. Step 2 (helpers, guest shares, supervised limits)
is deliberately not built: supervised == member and guest == see_shared
for now, with the per-person grants reserved on ``can(target=...)``.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient

from personal_world.identity import (
    IdentityStore,
    Principal,
    apply_group_role,
    is_admin,
    principal_from_record,
    role_for_record,
)
from personal_world.roles import (
    PERMISSIONS,
    ROLE_PERMISSIONS,
    ROLES,
    can,
    permissions_for,
    role_for_groups,
)

#: The plan's table, exactly. If this changes, the plan changed.
EXPECTED_BUNDLE = {
    "owner": set(PERMISSIONS),
    "admin": {
        "own_space",
        "see_shared",
        "approve",
        "manage_people",
        "manage_rooms",
        "estate_secrets",
    },
    "member": {"own_space", "see_shared"},
    "supervised": {"own_space", "see_shared"},
    "guest": {"see_shared"},
}


# ── can(): the bundle, and fail-closed ───────────────────────────────


class TestPermissionBundles:
    def test_role_bundles_are_exactly_the_plan_table(self):
        assert {r: set(ROLE_PERMISSIONS[r]) for r in ROLES} == EXPECTED_BUNDLE

    def test_roles_and_permissions_are_closed_sets(self):
        assert ROLES == ("owner", "admin", "member", "supervised", "guest")
        assert PERMISSIONS == (
            "own_space",
            "see_shared",
            "approve",
            "manage_people",
            "manage_rooms",
            "estate_secrets",
            "transfer_ownership",
        )

    @pytest.mark.parametrize("role", ROLES)
    def test_can_matches_the_bundle_for_every_role(self, role):
        p = Principal(id="made-up-person", role=role)
        for perm in PERMISSIONS:
            assert can(p, perm) is (perm in EXPECTED_BUNDLE[role]), (role, perm)
        assert set(permissions_for(p)) == EXPECTED_BUNDLE[role]

    def test_unknown_permission_fails_closed(self):
        # Never raises, never widens — a typo is a denial.
        assert can(Principal(id="someone", role="owner"), "everything") is False
        assert can(Principal(id="someone", role="owner"), "") is False
        assert can(Principal(id="someone", role="owner"), "OWN_SPACE") is False

    def test_no_principal_is_denied(self):
        assert can(None, "see_shared") is False
        assert can(None, "transfer_ownership") is False

    def test_only_owner_has_transfer_ownership(self):
        for role in ROLES:
            expected = role == "owner"
            assert can(Principal(id="p", role=role), "transfer_ownership") is expected


class TestAgentLesserOf:
    """An agent gets the lesser of its scopes and its owner's permissions."""

    def test_owner_permission_and_scope_both_required(self):
        # Owner is an owner AND the agent holds `write`.
        agent = Principal(id="bot", kind="agent", owner_id="o", scopes=("write",), role="owner")
        assert can(agent, "own_space") is True  # owner has it + scope maps
        assert can(agent, "see_shared") is False  # scope `write` is not `read`
        assert can(agent, "approve") is False  # no agent mapping at all

    def test_owner_lacking_permission_denies_the_agent(self):
        # Owner is a guest: the agent is no more than its owner.
        agent = Principal(id="bot", kind="agent", owner_id="o", scopes=("write",), role="guest")
        assert can(agent, "own_space") is False

    def test_read_scope_sees_shared_but_not_own_space(self):
        agent = Principal(id="bot", kind="agent", owner_id="o", scopes=("read",), role="member")
        assert can(agent, "see_shared") is True
        assert can(agent, "own_space") is False

    def test_agent_never_gets_human_only_permissions(self):
        for perm in (
            "approve",
            "manage_people",
            "manage_rooms",
            "estate_secrets",
            "transfer_ownership",
        ):
            agent = Principal(id="bot", kind="agent", owner_id="o", scopes=("write", "read"), role="owner")
            assert can(agent, perm) is False, perm

    def test_target_is_accepted_and_ignored_for_now(self):
        # The step-2 helper-grant argument must not change today's answer.
        p = Principal(id="p", role="member")
        assert can(p, "see_shared", target="someone") is True
        assert can(p, "approve", target="someone") is False


class TestLegacyAdminScope:
    """The old `admin` scope is still read as admin; new code writes role."""

    def test_admin_scope_reads_as_admin(self):
        p = Principal(id="carol", scopes=("admin",))
        assert can(p, "approve") is True
        assert can(p, "manage_people") is True
        assert can(p, "transfer_ownership") is False

    def test_is_admin_wrapper_is_the_approve_permission(self):
        assert is_admin(Principal(id="primary", role="owner")) is True
        assert is_admin(Principal(id="p", role="admin")) is True
        assert is_admin(Principal(id="p", role="member")) is False
        assert is_admin(None) is False
        # Agents are never admins.
        assert is_admin(Principal(id="bot", kind="agent", scopes=("admin",))) is False


# ── role_for_groups: SSO group → role mapping ────────────────────────

MAPPING = "admin=admin,users=member,kids=supervised,guests=guest"


class TestRoleForGroups:
    def test_single_group_maps(self):
        assert role_for_groups(["users"], MAPPING) == "member"
        assert role_for_groups(["kids"], MAPPING) == "supervised"
        assert role_for_groups(["guests"], MAPPING) == "guest"

    def test_highest_privilege_match_wins(self):
        assert role_for_groups(["users", "kids"], MAPPING) == "member"
        assert role_for_groups(["kids", "guests"], MAPPING) == "supervised"
        assert role_for_groups(["admin", "users", "kids"], MAPPING) == "admin"

    def test_no_match_returns_none(self):
        assert role_for_groups(["nobody"], MAPPING) is None
        assert role_for_groups([], MAPPING) is None
        assert role_for_groups(["users"], "") is None
        assert role_for_groups(["users"], None) is None

    def test_owner_can_never_come_from_a_group(self, caplog):
        mapping = "bosses=owner,staff=admin"
        with caplog.at_level("WARNING", logger="personal_world.roles"):
            assert role_for_groups(["bosses"], mapping) is None
            assert role_for_groups(["bosses", "staff"], mapping) == "admin"
        assert any("owner" in r.message for r in caplog.records)

    def test_malformed_entries_are_ignored(self):
        mapping = " , =x,users=member,weird=changeling,kids=supervised"
        assert role_for_groups(["users"], mapping) == "member"
        assert role_for_groups(["kids"], mapping) == "supervised"
        assert role_for_groups(["weird"], mapping) is None


class TestGroupRoleAtSignIn:
    """PW_ROLE_GROUPS updates the stored role; the owner is never demoted."""

    @pytest.fixture
    def store(self, tmp_path):
        s = IdentityStore(tmp_path)
        s.create_user("person-one", "Person one", initial_plain_token="tok-one")
        return s

    def test_group_role_is_stored(self, store):
        p = principal_from_record(store.get_principal_record("person-one"))
        out = apply_group_role(store, p, ["kids"], "kids=supervised")
        assert out.role == "supervised"
        assert store.role_for("person-one") == "supervised"

    def test_no_groups_or_no_mapping_keeps_stored_role(self, store):
        p = principal_from_record(store.get_principal_record("person-one"))
        assert apply_group_role(store, p, [], MAPPING).role == "member"
        assert apply_group_role(store, p, ["kids"], "").role == "member"
        assert store.role_for("person-one") == "member"

    def test_owner_is_never_demoted(self, tmp_path):
        s = IdentityStore(tmp_path)
        s.create_user("primary", "Primary person", initial_plain_token="tok-p", role="owner")
        p = principal_from_record(s.get_principal_record("primary"))
        out = apply_group_role(s, p, ["kids"], "kids=supervised")
        assert out.role == "owner"
        assert s.role_for("primary") == "owner"

    def test_auth_manager_login_oidc_applies_the_mapping(
        self, tmp_path, monkeypatch
    ):
        from personal_world.auth import AuthManager

        monkeypatch.setenv("PW_ROLE_GROUPS", "kids=supervised,staff=admin")
        s = IdentityStore(tmp_path)
        s.create_user("person-two", "Person two", initial_plain_token="tok-two")
        am = AuthManager(
            tmp_path,
            tmp_path,
            identity={"mode": "multi", "store": s, "instance_token": "insttok"},
        )
        session = am.login_oidc("person-two", display_name="Person two", groups=["kids"])
        assert session.principal_id == "person-two"
        assert s.role_for("person-two") == "supervised"
        # A later sign-in with a higher group raises it (highest wins).
        am.login_oidc("person-two", display_name="Person two", groups=["staff"])
        assert s.role_for("person-two") == "admin"
        # And a sign-in with no groups keeps the stored role.
        am.login_oidc("person-two", display_name="Person two", groups=None)
        assert s.role_for("person-two") == "admin"


class TestOidcGroupsClaim:
    def test_identity_from_claims_reads_groups(self):
        from personal_world.oidc import identity_from_claims

        ident = identity_from_claims(
            {"sub": "s1", "groups": ["kids", "users", 7, None]}
        )
        assert ident.groups == ("kids", "users")

    def test_identity_from_claims_without_groups_is_empty(self):
        from personal_world.oidc import identity_from_claims

        assert identity_from_claims({"sub": "s1"}).groups == ()
        assert identity_from_claims({"sub": "s1", "groups": "kids"}).groups == ()


# ── record migration ─────────────────────────────────────────────────


class TestRoleMigration:
    def test_migrates_legacy_records(self, tmp_path):
        (tmp_path / "users.json").write_text(
            json.dumps(
                {
                    "users": [
                        {"user_id": "primary", "display_name": "Primary person"},
                        {
                            "user_id": "legacy-admin",
                            "display_name": "Legacy admin",
                            "scopes": ["admin"],
                        },
                        {"user_id": "plain", "display_name": "Plain person"},
                    ]
                }
            )
        )
        store = IdentityStore(tmp_path)
        changed = store.migrate_roles()
        assert changed == 3
        assert store.role_for("primary") == "owner"
        assert store.role_for("legacy-admin") == "admin"
        assert store.role_for("plain") == "member"

    def test_migration_is_idempotent(self, tmp_path):
        store = IdentityStore(tmp_path)
        store.create_user("primary", "Primary person", role="owner")
        store.create_user("person-three", "Person three")
        assert store.migrate_roles() == 0
        assert store.migrate_roles() == 0

    def test_demoting_a_legacy_admin_sticks(self, tmp_path):
        """A demoted legacy admin loses the old scope, so they stay demoted,
        even after the boot-time migration runs again."""
        (tmp_path / "users.json").write_text(
            json.dumps({"users": [{"user_id": "legacy-admin", "display_name": "Legacy admin", "scopes": ["admin", "read"]}]})
        )
        store = IdentityStore(tmp_path)
        store.migrate_roles()
        assert store.role_for("legacy-admin") == "admin"
        store.set_role("legacy-admin", "member")
        assert store.role_for("legacy-admin") == "member"
        store.migrate_roles()
        assert store.role_for("legacy-admin") == "member"
        rec = store.get_user("legacy-admin")
        assert "admin" not in (rec.get("scopes") or [])
        assert rec.get("scopes") == ["read"]

    def test_role_for_record_back_compat_without_migration(self):
        assert role_for_record({"user_id": "primary"}) == "owner"
        assert role_for_record({"user_id": "x", "scopes": ["admin"]}) == "admin"
        assert role_for_record({"user_id": "x"}) == "member"
        assert role_for_record({"user_id": "x", "role": "guest"}) == "guest"

    def test_principal_from_record_carries_role(self):
        p = principal_from_record({"user_id": "x", "scopes": ["admin"]})
        assert p.role == "admin" and can(p, "manage_people") is True

    def test_provisioned_people_default_to_member(self, tmp_path):
        store = IdentityStore(tmp_path)
        store.create_user("fresh", "Fresh person")
        assert store.role_for("fresh") == "member"

    def test_set_role_rejects_unknown_role(self, tmp_path):
        store = IdentityStore(tmp_path)
        store.create_user("fresh", "Fresh person")
        with pytest.raises(ValueError):
            store.set_role("fresh", "wizard")
        assert store.role_for("fresh") == "member"

    def test_owner_id_finds_the_owner(self, tmp_path):
        store = IdentityStore(tmp_path)
        store.create_user("primary", "Primary person", role="owner")
        store.create_user("other", "Other person")
        assert store.owner_id() == "primary"


# ── the migrated routes, and the people API (integration) ────────────

OWNER_TOKEN = "instancetoken"
OWNER = {"Authorization": f"Bearer {OWNER_TOKEN}", "X-PW-StepUp": "1"}


def _app(tmp_path, monkeypatch, mode="multi"):
    from personal_world.api import create_app

    monkeypatch.setenv("PW_API_TOKEN", OWNER_TOKEN)
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    if mode is None:
        monkeypatch.delenv("PW_IDENTITY_MODE", raising=False)
    else:
        monkeypatch.setenv("PW_IDENTITY_MODE", mode)
    return TestClient(create_app(tmp_path, tmp_path))


def _h(token):
    return {"Authorization": f"Bearer {token}", "X-PW-StepUp": "1"}


def _provision(c, user_id):
    r = c.post(
        "/api/identity/users",
        json={"user_id": user_id, "display_name": "Made up person"},
        headers=OWNER,
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["token"]


def _set_role(c, user_id, role):
    return c.put(f"/api/people/{user_id}/role", json={"role": role}, headers=OWNER)


class TestMigratedRoutes:
    @pytest.mark.parametrize("role", ["member", "supervised", "guest"])
    def test_non_admins_are_refused_every_manage_surface(
        self, tmp_path, monkeypatch, role
    ):
        c = _app(tmp_path, monkeypatch)
        tok = _provision(c, f"person-{role}")
        assert _set_role(c, f"person-{role}", role).status_code == 200
        headers = _h(tok)
        assert c.get("/api/identity/users", headers=headers).status_code == 403
        assert c.get("/api/people", headers=headers).status_code == 403
        assert c.get("/api/secrets/overview", headers=headers).status_code == 403
        # /api/identity/agents is "mine (list)": a non-admin may keep
        # agents of their own, but never sees anyone else's.
        assert c.post(
            "/api/identity/agents",
            json={"agent_id": "owner-bot", "scopes": ["read"]},
            headers=OWNER,
        ).status_code == 200
        mine = c.get("/api/identity/agents", headers=headers)
        assert mine.status_code == 200
        assert mine.json()["data"] == []
        assert (
            c.post(
                "/api/identity/users",
                json={"user_id": "should-not-exist", "display_name": "Made up person"},
                headers=headers,
            ).status_code
            == 403
        )
        assert c.delete("/api/identity/users/primary", headers=headers).status_code == 403
        # Even with step-up, a non-admin may not set a role or transfer.
        assert (
            c.put(
                "/api/people/primary/role", json={"role": "member"}, headers=headers
            ).status_code
            == 403
        )
        assert (
            c.post(
                "/api/people/transfer-ownership", json={"to": "primary"}, headers=headers
            ).status_code
            == 403
        )
        assert IdentityStore(tmp_path).get_user("should-not-exist") is None

    @pytest.mark.parametrize("role", ["member", "supervised"])
    def test_non_admin_still_owns_their_own_space(self, tmp_path, monkeypatch, role):
        """`manage_people` is not a key to anyone's journal: the migrated
        routes must not have narrowed a person's own space."""
        c = _app(tmp_path, monkeypatch)
        tok = _provision(c, f"own-space-{role}")
        _set_role(c, f"own-space-{role}", role)
        headers = _h(tok)
        assert c.get("/api/prefs", headers=headers).status_code == 200
        assert c.put("/api/prefs", json={"text_scale": 1.25}, headers=headers).status_code == 200
        assert c.get("/api/rooms", headers=headers).status_code in (200, 503)

    def test_guest_still_sees_shared_rooms(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        tok = _provision(c, "guest-visitor")
        _set_role(c, "guest-visitor", "guest")
        assert c.get("/api/rooms", headers=_h(tok)).status_code in (200, 503)

    def test_owner_is_allowed(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        assert c.get("/api/identity/users", headers=OWNER).status_code == 200
        assert c.get("/api/identity/agents", headers=OWNER).status_code == 200
        assert c.get("/api/people", headers=OWNER).status_code == 200
        assert c.get("/api/secrets/overview", headers=OWNER).status_code == 200

    def test_admin_is_allowed_for_accounts_but_not_transfer(
        self, tmp_path, monkeypatch
    ):
        c = _app(tmp_path, monkeypatch)
        # Provision, then promote. The token was issued before promotion,
        # but the record's role is what counts at request time.
        admin_tok = _provision(c, "admin-person")
        assert _set_role(c, "admin-person", "admin").status_code == 200
        h = _h(admin_tok)
        assert c.get("/api/identity/users", headers=h).status_code == 200
        assert c.get("/api/people", headers=h).status_code == 200
        assert c.get("/api/secrets/overview", headers=h).status_code == 200
        # An admin cannot transfer ownership away from the owner.
        assert (
            c.post(
                "/api/people/transfer-ownership",
                json={"to": "admin-person"},
                headers=h,
            ).status_code
            == 403
        )

    def test_legacy_admin_scope_still_grants_the_routes(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        tok = _provision(c, "legacy-admin-person")
        store = IdentityStore(tmp_path)
        payload = store._load()
        for u in payload["users"]:
            if u["user_id"] == "legacy-admin-person":
                u.pop("role", None)
                u["scopes"] = ["admin"]
        store._save(payload)
        assert c.get("/api/identity/users", headers=_h(tok)).status_code == 200


class TestPeopleApi:
    def test_owner_can_list_people_and_roles(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        _provision(c, "listed-person")
        r = c.get("/api/people", headers=OWNER)
        assert r.status_code == 200
        by_id = {p["id"]: p for p in r.json()["data"]}
        assert by_id["primary"]["role"] == "owner"
        assert by_id["listed-person"]["role"] == "member"
        assert by_id["listed-person"]["kind"] == "person"
        assert set(by_id["listed-person"]) == {
            "id",
            "display_name",
            "role",
            "kind",
            "created_at",
        }
        assert "token" not in json.dumps(r.json())

    def test_admin_can_change_another_persons_role(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        tok = _provision(c, "promote-me")
        _set_role(c, "promote-me", "admin")
        assert c.get("/api/people", headers=_h(tok)).status_code == 200
        r = _set_role(c, "primary", "member")  # target the owner — protected
        assert r.status_code == 403
        # An admin CAN demote another member/supervised person.
        _provision(c, "to-demote")
        r2 = c.put(
            "/api/people/to-demote/role", json={"role": "guest"}, headers=_h(tok)
        )
        assert r2.status_code == 200
        assert IdentityStore(tmp_path).role_for("to-demote") == "guest"

    def test_unknown_role_is_422(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        _provision(c, "someone")
        assert _set_role(c, "someone", "wizard").status_code == 422
        assert _set_role(c, "someone", 123).status_code == 422

    def test_owner_is_not_assignable_here(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        _provision(c, "someone")
        assert _set_role(c, "someone", "owner").status_code == 422

    def test_owner_record_is_protected(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        assert _set_role(c, "primary", "member").status_code == 403
        assert IdentityStore(tmp_path).role_for("primary") == "owner"

    def test_admin_cannot_change_own_role(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        tok = _provision(c, "self-admin")
        _set_role(c, "self-admin", "admin")
        r = c.put("/api/people/self-admin/role", json={"role": "member"}, headers=_h(tok))
        assert r.status_code == 403
        assert IdentityStore(tmp_path).role_for("self-admin") == "admin"

    def test_unknown_person_is_404(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        assert _set_role(c, "not-a-person", "member").status_code == 404

    def test_role_change_requires_step_up_in_the_manifest(self, tmp_path, monkeypatch):
        """TestClient is loopback (step-up satisfied), so verify the
        declared gate instead: both people writes are step-up."""
        from personal_world.api_manifest import endpoint_manifest

        c = _app(tmp_path, monkeypatch)
        app = c.app
        rows = {
            (r["method"], r["path"]): r
            for r in endpoint_manifest(app.routes)["endpoints"]
        }
        assert rows[("PUT", "/api/people/{user_id}/role")]["gate"] == "step-up"
        assert rows[("POST", "/api/people/transfer-ownership")]["gate"] == "step-up"


class TestTransferOwnership:
    def test_owner_hands_ownership_to_an_admin(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        _provision(c, "heir-apparent")
        _set_role(c, "heir-apparent", "admin")
        r = c.post(
            "/api/people/transfer-ownership",
            json={"to": "heir-apparent"},
            headers=OWNER,
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"] == {"from": "primary", "to": "heir-apparent"}
        store = IdentityStore(tmp_path)
        assert store.role_for("heir-apparent") == "owner"
        assert store.role_for("primary") == "admin"
        # The old owner's token now resolves as admin, not owner.
        me = c.get("/api/me", headers=_h(OWNER_TOKEN)).json()["data"]
        assert me["role"] == "admin"

    def test_target_must_already_be_an_admin(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        _provision(c, "not-admin")
        r = c.post(
            "/api/people/transfer-ownership", json={"to": "not-admin"}, headers=OWNER
        )
        assert r.status_code == 422
        assert IdentityStore(tmp_path).role_for("primary") == "owner"

    def test_cannot_transfer_to_self(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        r = c.post(
            "/api/people/transfer-ownership", json={"to": "primary"}, headers=OWNER
        )
        assert r.status_code == 422

    def test_unknown_target_is_404(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        r = c.post(
            "/api/people/transfer-ownership", json={"to": "nobody"}, headers=OWNER
        )
        assert r.status_code == 404

    def test_non_owner_cannot_transfer(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        tok = _provision(c, "plain-member")
        r = c.post(
            "/api/people/transfer-ownership", json={"to": "primary"}, headers=_h(tok)
        )
        assert r.status_code == 403


class TestApiMe:
    def test_owner_has_every_permission(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        data = c.get("/api/me", headers=_h(OWNER_TOKEN)).json()["data"]
        assert data["id"] == "primary"
        assert data["role"] == "owner"
        assert data["permissions"] == list(PERMISSIONS)

    def test_member_permissions(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        tok = _provision(c, "member-person")
        data = c.get("/api/me", headers=_h(tok)).json()["data"]
        assert data["role"] == "member"
        assert data["permissions"] == ["own_space", "see_shared"]

    def test_supervised_matches_member_for_now(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        tok = _provision(c, "kid-person")
        _set_role(c, "kid-person", "supervised")
        data = c.get("/api/me", headers=_h(tok)).json()["data"]
        assert data["role"] == "supervised"
        assert data["permissions"] == ["own_space", "see_shared"]

    def test_guest_sees_shared_only(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch)
        tok = _provision(c, "guest-person")
        _set_role(c, "guest-person", "guest")
        data = c.get("/api/me", headers=_h(tok)).json()["data"]
        assert data["role"] == "guest"
        assert data["permissions"] == ["see_shared"]


class TestSingleModeUnchanged:
    def test_owner_can_everything_and_legacy_routes_work(self, tmp_path, monkeypatch):
        c = _app(tmp_path, monkeypatch, mode=None)
        headers = _h(OWNER_TOKEN)
        assert c.get("/api/prefs", headers=headers).status_code == 200
        assert c.get("/api/identity/users", headers=headers).status_code == 200
        assert c.get("/api/secrets/overview", headers=headers).status_code == 200
        data = c.get("/api/me", headers=headers).json()["data"]
        assert data["id"] == "primary"
        assert data["role"] == "owner"
        assert data["permissions"] == list(PERMISSIONS)

    def test_single_mode_people_api_refuses_transfer_without_an_admin(
        self, tmp_path, monkeypatch
    ):
        # One person, no admin to hand ownership to — refused honestly.
        c = _app(tmp_path, monkeypatch, mode=None)
        r = c.post(
            "/api/people/transfer-ownership", json={"to": "primary"}, headers=_h(OWNER_TOKEN)
        )
        assert r.status_code == 422
