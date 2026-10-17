# Worlds

## What this is

Worlds is Rylee's own home for her agents: one front door that gathers useful
state, memory and outside services, so nobody has to learn every provider
underneath. It is source-ready work in progress, not the production cutover.

## Is it running?

**UNKNOWN.** Nothing in this repository proves what is running. The running
app's own health check is the only evidence:

```sh
curl -fsS http://127.0.0.1:8000/healthz
```

It answers `{"ok": true, "commit": "..."}` for the revision actually serving.
No answer, a refused connection, or anything other than that means it is not
running here, or not the app you think it is.

## How to use it

Run these from the repository root. You need Python 3.12+ and `uv`; the
container command also needs podman or docker.

```sh
# start from this source; needs PW_API_TOKEN in .env, or the image refuses to boot
docker compose -f compose.yaml -f compose.dev.yaml up -d --build

# or run from source with no containers
PW_CONFIG_DIR=$PWD/config.local PW_DATA_DIR=$PWD/data \
  uv run uvicorn personal_world.worlds.production:app_from_env --factory

# check your configuration before starting
uv run personal-world framework validate
```

Then open <http://127.0.0.1:8000/>. Set `PW_PORT` to move the compose port.

## Where to read more

- [`AGENTS.md`](AGENTS.md) — the rules for working in this repository.
- [`src/personal_world/worlds/production.py`](src/personal_world/worlds/production.py)
  — the entrypoint; `app_from_env` builds the app from `PW_CONFIG_DIR` and
  `PW_DATA_DIR`.
- [`config/`](config/) — configuration is files; the tracked recipes and
  prompts live here.
- [`docs/INDEX.md`](docs/INDEX.md) — the rest of the documentation.

Code and docs are licensed under [MPL-2.0](LICENSE); art under [CC BY-SA 4.0](LICENSE-CONTENT.md). Names and logos are covered by [TRADEMARKS.md](TRADEMARKS.md).