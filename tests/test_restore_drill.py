"""CI guard for the restore drill: scripts/restore-drill.sh, pytest form.

Same round-trip the shell drill performs — seed a throwaway instance
through the app's OWN API, export an encrypted worlds bundle, restore
it into a clean data dir, and prove the restored instance works by
reading it back through the real API — but driven with tmp_path and
TestClient so no server, port or token ever enters the picture (and CI
can run it anywhere).

The assertions encode the OBSERVED recovery boundary, not the doc's
aspiration:

* journal, world state, identities, user trees, local connection
  config and sanitized OIDC config all travel;
* vault.enc does NOT travel by default (decision #4) — the restored
  instance must report the vault honestly as locked and unencrypted;
* ephemeral state (sessions.json, memory.fts5.db)
  and anything outside the boundary (e.g. a media/ tree) never travel;
* the setup-complete marker is NOT part of the bundle: a restored
  instance needs a first-run init/setup pass before it will boot the
  Station. That is deliberate (credentials are not portable) and this
  test pins it so a future boundary change notices HERE first.
"""

import secrets
import time
from pathlib import Path

from fastapi.testclient import TestClient

from personal_world import worlds_backup
from personal_world.api import create_app
from personal_world.init import init_world

# Synthetic values only. The planted "OIDC secret" below is short and
# fake; it exists to prove the strip works.
PASSPHRASE = "drill round-trip passphrase"  # pw-safety: synthetic
OIDC_CANARY = "canary-not-real"  # pw-safety: synthetic
NOTES = (
    "drill note alpha: kettle verified",
    "drill note beta: orbit quiet",
)
FACT_KEYS = ("drill.fact.one", "drill.fact.two")


def _seed_instance_a(tmp_path: Path, monkeypatch):
    """A throwaway instance built ONLY through the app's own APIs."""
    data = tmp_path / "a" / "data"
    config = tmp_path / "a" / "config"
    home = tmp_path / "a" / "home"
    for d in (data, config, home):
        d.mkdir(parents=True)

    # App's own init contract (the CLI path): world, journal, stores,
    # setup-complete marker.
    result = init_world(data, config)
    assert result.ok, result.warnings

    token = secrets.token_hex(16)
    vault_pass = secrets.token_hex(16)
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    monkeypatch.setenv("PW_API_TOKEN", token)
    client = TestClient(create_app(data, config))
    auth = {"Authorization": f"Bearer {token}"}

    # Journal entries via the person-facing API.
    for note in NOTES:
        r = client.post("/api/journal", json={"text": note}, headers=auth)
        assert r.status_code == 200, r.text

    # World mutations (facts + intent; TestClient peer is loopback, so
    # the local-owner step-up path applies — same as the shell drill).
    assert client.post(
        "/api/world/fact",
        json={"key": FACT_KEYS[0], "value": "kettle: online"},
        headers=auth,
    ).status_code == 200
    assert client.post(
        "/api/world/fact",
        json={"key": FACT_KEYS[1], "value": "orbit: stable"},
        headers=auth,
    ).status_code == 200
    assert client.post(
        "/api/world/intent",
        json={"key": "drill.intent.one", "value": "keep the garden lit"},
        headers=auth,
    ).status_code == 200

    # Identity records via the admin API.
    for uid in ("drill-person-a", "drill-person-b"):
        r = client.post(
            "/api/identity/users",
            json={"user_id": uid, "display_name": uid.title()},
            headers=auth,
        )
        assert r.status_code == 200, r.text

    # Vault with one synthetic secret: exists on A, must NOT travel.
    assert client.post(
        "/api/vault/unlock", json={"passphrase": vault_pass}, headers=auth
    ).status_code == 200
    assert client.post(
        "/api/vault/set",
        json={"name": "drill.canary", "value": "synthetic-not-a-secret"},
        headers=auth,
    ).status_code == 200
    assert (data / "vault.enc").is_file()

    # Boundary decoys: ephemeral + non-boundary files that must never
    # appear in the archive, user-owned trees that must.
    (data / "sessions.json").write_text('{"session":"ephemeral"}')
    (data / "memory.fts5.db").write_bytes(b"\x00fts")
    (data / "media").mkdir()
    (data / "media" / "photo.bin").write_text("not-archived")
    pack = data / "theme-packs" / "drizzle"
    pack.mkdir(parents=True)
    (pack / "manifest.json").write_text('{"name":"drizzle"}')
    tpl = data / "template-sources" / "tpl"
    tpl.mkdir(parents=True)
    (tpl / "source.md").write_text("source")

    # Home config state: reconciler state is seeded directly
    # because the app APIs resolve that store to the REAL default
    # ~/.config/personal-world, which tests must never touch.
    (home / "reconciler" / "desired").mkdir(parents=True)
    (home / "reconciler" / "desired" / "drill.yml").write_text("service: drill\n")

    # Config-dir side: local overrides travel; oidc.json travels
    # CONFIG ONLY with any inline secret value stripped.
    (config / "connections.local.json").write_text(
        '{"connections":[{"name":"drill","type":"ollama"}]}'
    )
    (config / "oidc.json").write_text(
        '{"issuer":"https://sso.example.invalid","client_id":"pw",'
        f'"client_secret_env":"PW_OIDC_CLIENT_SECRET","client_secret":"{OIDC_CANARY}"}}'
    )
    return data, config, home


def _restore_roots(tmp_path: Path):
    b_data = tmp_path / "b" / "data"
    b_data.mkdir(parents=True)
    return b_data, tmp_path / "b" / "config", tmp_path / "b" / "home"


def test_restore_drill_roundtrip(tmp_path, monkeypatch):
    """Export from A → restore into clean B → B serves A's state."""
    a_data, a_config, a_home = _seed_instance_a(tmp_path, monkeypatch)
    archive = tmp_path / "sos" / "world.pwbackup"

    # ── export ────────────────────────────────────────────────────────
    t0 = time.monotonic()
    backup = worlds_backup.backup(
        a_data,
        archive,
        PASSPHRASE,
        config_dir=a_config,
        home_config_dir=a_home,
    )
    backup_s = time.monotonic() - t0
    assert backup.ok, backup.warnings
    included = set(backup.data["included"])
    assert {
        "data/world.json",
        "data/journal.ndjson",
        "data/users.json",
        "data/theme-packs/drizzle/manifest.json",
        "data/template-sources/tpl/source.md",
        "home/reconciler/desired/drill.yml",
        "config/connections.local.json",
        "config/oidc.json",
    } <= included, f"boundary gap: {sorted(included)}"
    # Never-included stays never-included, and the non-boundary media
    # tree is invisibly outside the boundary (documented gap).
    for banned in ("vault.enc", "sessions.json", "memory.fts5.db",
                   "config/connections.json"):
        assert not any(n.endswith(banned) for n in included), banned
    assert not any("/media/" in n for n in included)
    # Secret stripping is reported, not silent.
    assert any(
        "config/oidc.json" in w and "stripped" in w for w in backup.data["excluded"]
    )
    assert backup_s < 60  # generous anti-pathology bound, not a perf gate

    # ── restore into the clean instance ───────────────────────────────
    b_data, b_config, b_home = _restore_roots(tmp_path)
    t0 = time.monotonic()
    restore = worlds_backup.restore(
        b_data,
        archive,
        PASSPHRASE,
        config_dir=b_config,
        home_config_dir=b_home,
    )
    restore_s = time.monotonic() - t0
    assert restore.ok, restore.warnings
    assert set(restore.data["restored"]) == included
    assert restore.data["skipped"] == [] and restore.data["refused"] == []
    assert restore_s < 60

    # Authoritative state is byte-identical on the far side.
    for name in ("world.json", "journal.ndjson", "users.json"):
        assert (b_data / name).read_bytes() == (a_data / name).read_bytes()
    assert (b_config / "connections.local.json").read_bytes() == (
        a_config / "connections.local.json"
    ).read_bytes()
    oidc = (b_config / "oidc.json").read_text()
    assert OIDC_CANARY not in oidc and "stripped-by-worlds-backup" in oidc
    assert "PW_OIDC_CLIENT_SECRET" in oidc

    # What must NOT be on the far side.
    assert not (b_data / "vault.enc").exists()
    assert not (b_data / "sessions.json").exists()
    assert not (b_data / "media" / "photo.bin").exists()
    assert (b_data / "theme-packs" / "drizzle" / "manifest.json").is_file()

    # OBSERVED BOUNDARY (pinned): the setup-complete marker and the
    # instance token do NOT travel. The operator must complete a
    # first-run pass to boot a restored instance. If a future change
    # adds them to the boundary, this assertion fires and the docs
    # must be updated with it.
    assert not (b_data / "setup-complete").exists()
    boot = init_world(b_data, b_config)  # the operator's bootstrap step
    assert boot.ok
    assert (b_data / "world.json").read_bytes() == (
        a_data / "world.json"
    ).read_bytes(), "init clobbered restored state"

    # ── the restored instance actually works ──────────────────────────
    token_b = secrets.token_hex(16)
    monkeypatch.setenv("PW_API_TOKEN", token_b)
    client_b = TestClient(create_app(b_data, b_config))
    auth = {"Authorization": f"Bearer {token_b}"}

    assert client_b.get("/api/setup/status", headers=auth).json()["data"][
        "complete"
    ] is True

    journal = client_b.get("/api/journal?n=100", headers=auth)
    assert journal.status_code == 200
    summaries = [e["summary"] for e in journal.json()["data"]]
    for note in NOTES:
        assert note in summaries, f"journal entry lost: {note}"
    assert "user provisioned: drill-person-a" in summaries

    status = client_b.get("/api/status", headers=auth).json()["data"]
    assert status["facts"] >= 2 and status["intents"] >= 1

    users = client_b.get("/api/identity/users", headers=auth).json()["data"]
    ids = {u["user_id"] for u in users}
    assert {"drill-person-a", "drill-person-b"} <= ids

    # Vault honesty: absent bundle member ⇒ locked AND not encrypted-
    # capable, exactly per the non-portable decision — never a silent
    # "we seem to have a vault" claim.
    vault = client_b.get("/api/vault/status", headers=auth).json()["data"]
    assert vault["locked"] is True
    assert vault.get("encrypted", True) is False

    # And B's journal is genuinely writable end-to-end post-restore:
    r = client_b.post(
        "/api/journal", json={"text": "post-restore note"}, headers=auth
    )
    assert r.status_code == 200, r.text
    assert (
        "post-restore note"
        in [
            e["summary"]
            for e in client_b.get("/api/journal?n=100", headers=auth).json()["data"]
        ]
    )


def test_restore_drill_wrong_passphrase_writes_nothing(tmp_path, monkeypatch):
    """Fail-closed half of the drill in CI form: a wrong passphrase
    changes NOTHING on the clean target."""
    a_data, a_config, a_home = _seed_instance_a(tmp_path, monkeypatch)
    archive = tmp_path / "sos" / "world.pwbackup"
    assert worlds_backup.backup(
        a_data, archive, PASSPHRASE, config_dir=a_config, home_config_dir=a_home
    ).ok
    b_data, b_config, b_home = _restore_roots(tmp_path)
    r = worlds_backup.restore(
        b_data,
        archive,
        "definitely the wrong passphrase",
        config_dir=b_config,
        home_config_dir=b_home,
    )
    assert not r.ok and r.status == "unauthorized"
    assert list(b_data.rglob("*")) == []
    assert not b_config.exists() and not b_home.exists()
