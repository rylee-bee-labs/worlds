# First-run on new hardware (daily-use runbook, 2026-09-09)

> **Status:** Historical · **Verified:** 2026-09-26 · **Canonical for:** nothing (see [Operations](../OPERATIONS.md)) · **Read this if:** you want the dated 2026-09-09 bring-up record. · **Superseded by:** [Operations](../OPERATIONS.md).

**In short:** a dated record of how the appliance was first brought up on new hardware. It is not a current deployment recipe — use [Operations](../OPERATIONS.md) and [Architecture](../ARCHITECTURE.md) instead.

Since this record: production Worlds runs on the transcode host at `/opt/personal-world` (docker compose, published GHCR image, one-tap update from Project Home's "What's live").

Steps matching what was actually done to bring the appliance up.
The public repo stays credential-free; all secrets are gitignored
local files.

**Scope correction (2026-09-10, kept from the original note):** this is a dated bring-up record, not a universal current deployment recipe. The tracked `compose.yaml` is the portable image-only base; host-specific mounts live in the opt-in `compose.homelab.yaml` override, and source builds in `compose.dev.yaml`. No container name, timezone, backup job, or external provider should be assumed present on a fresh install. `/setup` is the live wizard route (an older `/setup-wizard` alias is gone). Vault reset loses secrets and requires an explicit recovery decision; the historical reset command below is not a required installation step. Accessibility defaults are `motion: reduced` and comfortable contrast; OS requirements override application preferences.

## 1. Clone + install

```bash
git clone https://github.com/rylee-bee-labs/worlds.git
cd personal-world
uv sync --frozen --extra test --extra crypto
```

## 2. Local (gitignored) files you create once

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))" > .env-tmp
# paste that token into either one of these two paths:
#   (a) dev compose:  .env line  PW_API_TOKEN=...
#   (b) stack compose (VM deploy):  /opt/.env  PW_API_TOKEN=...  XIAOMI_MIMO_API_KEY=...
rm .env-tmp
```

## 3. Chat provider wiring (MiMo, OpenAI-compatible)

- put your real endpoint+model in
  `config/connections.local.json` (gitignored);
  tracked `config/connections.json` stays zero-provider
  (public-safety gate).
- put the actual API key in `.env`/`/opt/.env` under name
  `XIAOMI_MIMO_API_KEY` — compose forwards it into the core.
- form is serialized — never commit the literal value.

## 4. Vault unlock on first login

- the appliance serves `/setup` once for the token; the **vault
  passphrase is set in the app** (Settings → Advanced → Vault), not in
  the wizard. Passphrase is never stored; losing it requires deleting
  `/data/vault.enc` (you lose the stored secrets, not the world).
- `/data` volume holds world.json + journal.ndjson +
  reminders.json + repos/ + vault.enc; a rebuild preserves all.
- to reset: `docker exec personal-world sh -c "rm /data/vault.enc"`
  then re-unlock with the new passphrase.

## 5. Source-control status on new machine

`source_control.search_paths` entries are checked directly (no
recursion); point them at the repo dir itself:

```bash
docker exec personal-world sh -c \\\"git clone --bare https://github.com/rylee-bee-labs/worlds.git /data/repos/personal-world.git\\\" || true
```

(or plain `git clone` non-bare: same result for status).

## 6. Reminder key reminders

- no user-specific date or time — 24h clock topics; reminders use
  `cron_hour`/`cron_minute`, UTC-ish (container TZ=America/Chicago
  set in compose).
- Journal is append-only NDJSON. Backup via the nightly cron
  (NAS), or manual: `docker run --rm -v personal-world_world-data:/data alpine tar czf - /data > /path/backup.tar.gz`.

## 7. Accessibility floor, unchanged

Every dark-mode default, short-line, luminance-wording choice
stays as-is. If you add UI, keep contrast:high and motion:reduced.
