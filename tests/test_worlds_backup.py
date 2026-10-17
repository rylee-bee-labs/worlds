"""Tests for the encrypted worlds backup/restore SOS escape hatch.

Every fixture is synthetic (tmp_path only; reserved example values).
The one deliberately planted secret canary carries the required
`pw-safety: synthetic` marker on the same line.
"""

import io
import json
import tarfile
from pathlib import Path

import pytest

from personal_world import worlds_backup
from personal_world.envelope import Result

# Planted ONLY to prove sanitization strips it; never a real credential.
CANARY = "SYNTHETIC-CANARY-0123456789abcdef-not-real"  # pw-safety: synthetic
PASSPHRASE = "correct horse battery staple"


def _seed_instance(data: Path, config: Path, home: Path) -> None:
    """A synthetic instance covering the whole restore boundary plus
    the ephemeral files that must NEVER be archived."""
    data.mkdir(parents=True, exist_ok=True)
    (data / "world.json").write_text(json.dumps({"facts": {"mood": "calm"}}))
    (data / "journal.ndjson").write_text('{"kind":"note","text":"hello"}\n')
    (data / "users.json").write_text(json.dumps({"users": ["rylee"]}))
    (data / "reminders.json").write_text(json.dumps({"reminders": []}))
    (data / "apps.json").write_text(json.dumps({"apps": []}))
    (data / "proposals.json").write_text(json.dumps({"proposals": []}))

    # Per-user tree — including a per-user vault and ephemeral files.
    user = data / "users" / "rylee"
    user.mkdir(parents=True)
    (user / "world.json").write_text(json.dumps({"per-user": True}))
    (user / "journal.ndjson").write_text('{"kind":"note"}\n')
    (user / "reminders.json").write_text(json.dumps([]))
    (user / "vault.enc").write_text(json.dumps({"salt": "aa", "data": "bb"}))
    (user / "sessions.json").write_text(json.dumps({"session": "ephemeral"}))
    (user / "memory.fts5.db").write_bytes(b"\x00fts-index")

    # Instance-level ephemeral / regenerable files.
    (data / "sessions.json").write_text(json.dumps({"never": "archived"}))
    (data / "memory.fts5.db").write_bytes(b"\x00fts")
    (data / "memory.fts5.db-wal").write_bytes(b"\x00wal")
    (data / "vault.enc").write_text(json.dumps({"salt": "cc", "data": "dd"}))

    # User-owned trees.
    pack = data / "theme-packs" / "aurora"
    pack.mkdir(parents=True)
    (pack / "manifest.json").write_text(json.dumps({"name": "aurora"}))
    tpl = data / "template-sources" / "tpl1"
    tpl.mkdir(parents=True)
    (tpl / "source.md").write_text("# template source")

    # App config dir.
    config.mkdir(parents=True, exist_ok=True)
    (config / "connections.local.json").write_text(
        json.dumps({"connections": [{"name": "example", "type": "ollama"}]})
    )
    (config / "oidc.json").write_text(
        json.dumps(
            {
                "issuer": "https://sso.example.invalid",
                "client_id": "personal-world",
                "client_secret_env": "PW_OIDC_CLIENT_SECRET",
                "client_secret": CANARY,
                "scopes": ["openid", "profile"],
            }
        )
    )
    (config / "connections.json").write_text(json.dumps({"connections": []}))

    # Per-user config home.
    (home / "reconciler" / "desired").mkdir(parents=True, exist_ok=True)
    (home / "lab.json").write_text(json.dumps({"services": {}}))
    (home / "reconciler" / "desired" / "traefik.yml").write_text("service: traefik\n")
    (home / "lab" / "desired").mkdir(parents=True)
    (home / "lab" / "desired" / "svc.json").write_text(json.dumps({"svc": True}))


@pytest.fixture()
def instance(tmp_path):
    data = tmp_path / "data"
    config = tmp_path / "config"
    home = tmp_path / "home"
    _seed_instance(data, config, home)
    return data, config, home


def _backup(instance, tmp_path, **kwargs):
    data, config, home = instance
    target = tmp_path / "sos" / f"world-{abs(hash(repr(kwargs)))}.pwbackup"
    result = worlds_backup.backup(
        data, target, PASSPHRASE, config_dir=config, home_config_dir=home, **kwargs
    )
    return result, target


def _tar_members(target: Path, passphrase: str = PASSPHRASE) -> dict[str, bytes]:
    """Decrypt an archive and return {member_name: content}."""
    _, tar_bytes = worlds_backup._decrypt(target, passphrase)
    out = {}
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tar:
        for m in tar.getmembers():
            fh = tar.extractfile(m)
            out[m.name] = fh.read() if fh else b""
    return out


# ── round-trip ────────────────────────────────────────────────────────


def test_roundtrip_restore_into_fresh_instance(instance, tmp_path):
    result, target = _backup(instance, tmp_path)
    assert result.ok, result.warnings
    assert target.is_file()
    assert result.data["format"] == worlds_backup.FORMAT_ID

    data2 = tmp_path / "fresh-data"
    config2 = tmp_path / "fresh-config"
    home2 = tmp_path / "fresh-home"
    data2.mkdir()
    r = worlds_backup.restore(
        data2, target, PASSPHRASE, config_dir=config2, home_config_dir=home2
    )
    assert r.ok, r.warnings
    assert not r.data["refused"]

    # Boundary content is byte-identical on the fresh side.
    src_data, src_config, src_home = instance
    assert (data2 / "world.json").read_bytes() == (src_data / "world.json").read_bytes()
    assert (data2 / "journal.ndjson").read_bytes() == (
        src_data / "journal.ndjson"
    ).read_bytes()
    assert (data2 / "users.json").is_file()
    assert (data2 / "users" / "rylee" / "world.json").read_bytes() == (
        src_data / "users" / "rylee" / "world.json"
    ).read_bytes()
    assert (data2 / "theme-packs" / "aurora" / "manifest.json").is_file()
    assert (data2 / "template-sources" / "tpl1" / "source.md").is_file()
    assert (config2 / "connections.local.json").is_file()
    assert (config2 / "oidc.json").is_file()
    assert (home2 / "lab.json").is_file()
    assert (home2 / "reconciler" / "desired" / "traefik.yml").is_file()
    assert (home2 / "lab" / "desired" / "svc.json").is_file()

    # Ephemeral / regenerable files were NOT resurrected.
    assert not (data2 / "sessions.json").exists()
    assert not (data2 / "memory.fts5.db").exists()
    assert not (data2 / "users" / "rylee" / "sessions.json").exists()
    assert not (data2 / "users" / "rylee" / "memory.fts5.db").exists()
    # Vault excluded by default.
    assert not (data2 / "vault.enc").exists()
    assert not (data2 / "users" / "rylee" / "vault.enc").exists()


def test_result_is_envelope(instance, tmp_path):
    result, _ = _backup(instance, tmp_path)
    assert isinstance(result, Result)
    assert result.changed is True
    # The passphrase never appears in the honest report.
    assert PASSPHRASE not in result.model_dump_json()


# ── fail closed ───────────────────────────────────────────────────────


def test_wrong_passphrase_fails_closed_and_writes_nothing(instance, tmp_path):
    _, target = _backup(instance, tmp_path)
    data2 = tmp_path / "fresh"
    data2.mkdir()
    r = worlds_backup.restore(data2, target, "wrong passphrase")
    assert not r.ok
    assert r.status == "unauthorized"
    assert list(data2.rglob("*")) == []


def test_tampered_ciphertext_detected(instance, tmp_path):
    _, target = _backup(instance, tmp_path)
    blob = bytearray(target.read_bytes())
    blob[-5] ^= 0xFF  # flip a ciphertext byte
    target.write_bytes(bytes(blob))
    r = worlds_backup.restore(tmp_path / "x", target, PASSPHRASE)
    assert not r.ok
    assert r.status == "unauthorized"


def test_tampered_header_detected(instance, tmp_path):
    """The plaintext header is bound as AAD: editing it fails auth."""
    _, target = _backup(instance, tmp_path)
    head, _, body = target.read_bytes().partition(b"\n")
    header = json.loads(head)
    header["included"] = ["data/world.json"]  # attacker prunes the manifest
    forged = json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
    target.write_bytes(forged + b"\n" + body)
    r = worlds_backup.restore(tmp_path / "x", target, PASSPHRASE)
    assert not r.ok
    assert r.status == "unauthorized"


def test_empty_passphrase_refused(instance, tmp_path):
    data, config, home = instance
    r = worlds_backup.backup(
        data, tmp_path / "no.pwbackup", "", config_dir=config, home_config_dir=home
    )
    assert not r.ok
    assert r.status == "rejected"
    assert not (tmp_path / "no.pwbackup").exists()


def test_missing_crypto_extra_fails_closed(instance, tmp_path, monkeypatch):
    monkeypatch.setattr(worlds_backup, "_HAS_CRYPTO", False)
    data, config, home = instance
    target = tmp_path / "never.pwbackup"
    rb = worlds_backup.backup(
        data, target, PASSPHRASE, config_dir=config, home_config_dir=home
    )
    assert not rb.ok
    assert rb.status == "unavailable"
    assert "cryptography" in rb.warnings[0]
    assert not target.exists()  # no plaintext fallback file

    # Restore refuses too, even with a valid archive on disk.
    monkeypatch.setattr(worlds_backup, "_HAS_CRYPTO", True)
    good, good_target = _backup(instance, tmp_path)
    assert good.ok
    monkeypatch.setattr(worlds_backup, "_HAS_CRYPTO", False)
    rr = worlds_backup.restore(tmp_path / "fresh", good_target, PASSPHRASE)
    assert not rr.ok
    assert rr.status == "unavailable"


def test_restore_missing_archive_not_found(tmp_path):
    r = worlds_backup.restore(tmp_path / "d", tmp_path / "nope.pwbackup", PASSPHRASE)
    assert not r.ok
    assert r.status == "not_found"


def test_not_an_archive_fails_corrupt(tmp_path):
    bogus = tmp_path / "bogus.pwbackup"
    bogus.write_bytes(b"this is not a worlds backup archive at all\n\xff\xfe")
    r = worlds_backup.restore(tmp_path / "d", bogus, PASSPHRASE)
    assert not r.ok
    assert r.status in ("corrupt", "unauthorized")


# ── boundary content rules ────────────────────────────────────────────


def test_vault_excluded_by_default_included_with_flag(instance, tmp_path):
    result, target = _backup(instance, tmp_path)
    names = set(result.data["included"])
    assert not any(n.endswith("vault.enc") for n in names)
    assert any("vault.enc" in e for e in result.data["excluded"])

    result_v, target_v = _backup(instance, tmp_path, include_vault=True)
    names_v = set(result_v.data["included"])
    assert "data/vault.enc" in names_v
    assert "data/users/rylee/vault.enc" in names_v
    members = _tar_members(target_v)
    assert members["data/vault.enc"] == (instance[0] / "vault.enc").read_bytes()


def test_sessions_and_fts_never_included_even_with_vault_flag(instance, tmp_path):
    result, target = _backup(instance, tmp_path, include_vault=True)
    names = set(result.data["included"])
    for banned in ("sessions.json", "memory.fts5.db"):
        assert not any(n.endswith(banned) for n in names)
    members = _tar_members(target)
    for member_name, content in members.items():
        assert b"ephemeral" not in content or "sessions" not in member_name
    assert not any("fts5" in n for n in members)


def test_oidc_secret_value_never_present_in_archive(instance, tmp_path):
    _, target = _backup(instance, tmp_path)
    members = _tar_members(target)
    # Plaintext scan of EVERY member: the canary value must not appear.
    for name, content in members.items():
        assert CANARY.encode() not in content, f"secret value leaked into {name}"
    oidc = json.loads(members["config/oidc.json"])
    # Config-only shape survives: env-var NAME stays, value is stripped.
    assert oidc["client_secret_env"] == "PW_OIDC_CLIENT_SECRET"
    assert oidc["client_secret"] == "<stripped-by-worlds-backup>"
    assert oidc["issuer"] == "https://sso.example.invalid"


def test_tracked_config_connections_json_not_archived(instance, tmp_path):
    """connections.json is tracked repo config, not instance state."""
    result, _ = _backup(instance, tmp_path)
    assert "config/connections.json" not in result.data["included"]


def test_unrecognized_data_entries_are_reported_not_silently_dropped(instance, tmp_path):
    """Lane B drill finding (2026-09-22): a data/ subtree outside the
    boundary must show up in the report as NOT archived — vanishing from
    an SOS backup without a word is how a backup becomes a lie."""
    data, _, _ = instance
    (data / "media").mkdir()
    (data / "media" / "photo.bin").write_bytes(b"not in any boundary")
    result, _ = _backup(instance, tmp_path)
    assert not any(n.startswith("data/media") for n in result.data["included"])
    notes = [e for e in result.data["excluded"] if "data/media" in e]
    assert notes and "NOT recognized" in notes[0]
    # Documented operational names stay silent — honesty, not noise.
    assert not any(".env" in e or "setup-complete" in e for e in result.data["excluded"])


# ── overwrite semantics ───────────────────────────────────────────────


def test_restore_create_if_absent_then_skip_then_overwrite(instance, tmp_path):
    _, target = _backup(instance, tmp_path)
    data2 = tmp_path / "target-data"
    config2 = tmp_path / "target-config"
    home2 = tmp_path / "target-home"
    data2.mkdir()
    # Explicit roots ALWAYS: the module default for home is the real
    # ~/.config/personal-world, which tests must never touch.
    roots = dict(config_dir=config2, home_config_dir=home2)

    r1 = worlds_backup.restore(data2, target, PASSPHRASE, **roots)
    assert r1.ok and r1.data["restored"] and not r1.data["skipped"]
    assert not r1.data["refused"]

    # Second restore without --overwrite: everything already exists.
    r2 = worlds_backup.restore(data2, target, PASSPHRASE, **roots)
    assert r2.ok
    assert not r2.data["restored"]
    assert len(r2.data["skipped"]) == len(r1.data["restored"])

    # Local edit survives a non-overwrite restore...
    (data2 / "world.json").write_text('{"local": "edit"}')
    worlds_backup.restore(data2, target, PASSPHRASE, **roots)
    assert json.loads((data2 / "world.json").read_text()) == {"local": "edit"}

    # ...and is replaced with overwrite=True.
    r3 = worlds_backup.restore(data2, target, PASSPHRASE, overwrite=True, **roots)
    assert r3.ok and r3.data["restored"]
    assert json.loads((data2 / "world.json").read_text()) == {"facts": {"mood": "calm"}}


def test_restore_refuses_traversal_and_ephemeral_members(tmp_path):
    """A hostile archive (crafted via internals) cannot escape the roots
    or resurrect never-restore files."""
    members = [
        ("../escaped.txt", b"pwned"),
        ("data/../../escaped2.txt", b"pwned"),
        ("data/sessions.json", b"{}"),
        ("data/memory.fts5.db", b"\x00"),
        ("data/world.json", b'{"ok": true}'),
        ("bogus/x.txt", b"unknown root"),
    ]
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w:gz") as tar:
        for name, content in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    included = [n for n, _ in members]
    blob = worlds_backup._encrypt(tar_buf.getvalue(), PASSPHRASE, included, [])
    archive = tmp_path / "hostile.pwbackup"
    archive.write_bytes(blob)

    data2 = tmp_path / "d"
    data2.mkdir()
    r = worlds_backup.restore(
        data2,
        archive,
        PASSPHRASE,
        config_dir=tmp_path / "c",
        home_config_dir=tmp_path / "h",
    )
    assert r.ok  # the one legitimate member restored
    assert r.data["restored"] == ["data/world.json"]
    refused = " ".join(r.data["refused"])
    assert "escaped.txt" in refused and "escaped2.txt" in refused
    assert "sessions.json" in refused and "memory.fts5.db" in refused
    assert "bogus/x.txt" in refused
    assert not (tmp_path / "escaped.txt").exists()
    assert not (tmp_path / "escaped2.txt").exists()
    assert not (data2 / "sessions.json").exists()


# ── API registration seam (the /api/worlds/* routes ARE wired into
# api.py, gated with require_step_up — the tests below prove it against
# the real create_app) ─────────────────────────────────────────────────


def test_register_refuses_without_step_up_gate():
    class FakeApp:
        def post(self, *a, **k):  # pragma: no cover
            raise AssertionError("must not register without a gate")

    with pytest.raises(ValueError, match="step-up"):
        worlds_backup.register_worlds_backup(FakeApp(), data_dir=Path("/tmp"))


def test_register_refuses_without_owner_gate():
    class FakeApp:
        def post(self, *a, **k):  # pragma: no cover
            raise AssertionError("must not register without an owner gate")

    with pytest.raises(ValueError, match="owner"):
        worlds_backup.register_worlds_backup(
            FakeApp(), data_dir=Path("/tmp"), step_up=lambda: None
        )


def test_registered_routes_roundtrip_behind_stub_gate(instance, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    data, config, home = instance
    app = FastAPI()
    worlds_backup.register_worlds_backup(
        app,
        data_dir=data,
        config_dir=config,
        home_config_dir=home,
        step_up=lambda: "stepped-up",
        owner_gate=lambda: "owner",
    )
    client = TestClient(app)

    resp = client.post(
        "/api/worlds/backup",
        json={"passphrase": PASSPHRASE, "include_vault": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["vault_included"] is False
    download = body["download"]

    arc = client.get(download)
    assert arc.status_code == 200
    archive = tmp_path / "downloaded.pwbackup"
    archive.write_bytes(arc.content)
    # One-time: a second fetch of the same token is gone.
    assert client.get(download).status_code == 404

    # The downloaded archive restores cleanly into a fresh tree.
    fresh = tmp_path / "api-fresh"
    fresh.mkdir()
    r = worlds_backup.restore(
        fresh,
        archive,
        PASSPHRASE,
        config_dir=tmp_path / "api-cfg",
        home_config_dir=tmp_path / "api-home",
    )
    assert r.ok and r.data["restored"]

    import base64

    rresp = client.post(
        "/api/worlds/restore",
        json={
            "passphrase": PASSPHRASE,
            "archive_b64": base64.b64encode(archive.read_bytes()).decode(),
            "overwrite": True,
        },
    )
    assert rresp.status_code == 200, rresp.text
    assert rresp.json()["restored"]

    # Wrong passphrase over the API fails closed with 403.
    bad = client.post(
        "/api/worlds/restore",
        json={
            "passphrase": "nope",
            "archive_b64": base64.b64encode(archive.read_bytes()).decode(),
        },
    )
    assert bad.status_code == 403


def test_real_app_refuses_and_serves_backup(tmp_path, monkeypatch):
    """Against the REAL create_app (not the stub-gate copy): the route
    is wired, refuses unauthenticated calls, and answers an honest
    envelope once the token credential is presented."""
    from fastapi.testclient import TestClient

    from personal_world.api import create_app
    from personal_world.init import init_world

    token = "instancetoken-do-not-leak-1c2d"  # pw-safety: synthetic
    monkeypatch.setenv("PW_API_TOKEN", token)
    monkeypatch.setenv("PW_IDENTITY_MODE", "single")
    monkeypatch.setenv("PW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PW_CONFIG_DIR", str(tmp_path))
    init_world(tmp_path, tmp_path)
    (tmp_path / "setup-complete").write_text("ok")
    client = TestClient(create_app(tmp_path, tmp_path))
    auth = {"Authorization": f"Bearer {token}"}

    # No credential → refused (401), never a silent success.
    refused = client.post(
        "/api/worlds/backup",
        json={"passphrase": PASSPHRASE, "include_vault": False},
    )
    assert refused.status_code == 401, refused.text

    # With the instance token the loopback test peer satisfies the
    # step-up gate (true-loopback local-owner exception) and the route
    # answers an honest non-500 envelope.
    resp = client.post(
        "/api/worlds/backup",
        headers=auth,
        json={"passphrase": PASSPHRASE, "include_vault": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["download"].startswith("/api/worlds/backup/download/")
    assert body["one_time"] is True
    assert body["included"] is not None
