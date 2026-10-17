# Local runtime config (never committed)

Copy this file to `config/connections.local.json` to add your own chat
providers or source-control paths. It is gitignored, so real data
stays on your machine across rebuilds.

Schema: `personal-world/connections/1`

## Chat provider (OpenAI-compatible)

```json
{
  "$schema": "personal-world/connections/1",
  "connections": [
    {
      "type": "openai_compat",
      "name": "my-chat",
      "capability": "reasoning",
      "base_url": "https://your-provider.example/v1",
      "model": "your-model-name",
      "api_key_env": "MY_KEY_ENV",
      "timeout": 60
    }
  ]
}
```

`type` may also be `ollama` for local models. `api_key_env` names an
environment variable passed in from compose; its value is never read
into settings, exports or chat context.

## Source-control search paths

```json
"source_control": {
  "search_paths": ["/data/repos/your-repo"]
}
```

Each path is checked directly — point `search_paths` at the repo
directory itself, not its parent.

## Ownership rule (public repository boundary)

The tracked `config/` directory holds only schemas, examples and
zero-provider defaults. Anything that is *yours* — provider endpoints,
model routing, project selection, followed feeds, display name,
environment-specific paths — lives in a private runtime location:
`config/*.local.json`, `config.local/`, or `data/`. All of these are
gitignored. `tests/test_public_safety.py` fails if the tracked
`connections.json` ever ships a provider or secret-shaped value.

## Where data lives across rebuilds

- Secrets: the `/data` named volume (`vault.enc`) — survives
  `docker compose down` and container recreation.
- World model, journal, reminders, repository cache: same volume.
- Connections and theme config: `/config` (bind-mounted from repo,
  read-only).

Rebuild freely with `docker compose up -d --force-recreate` — your
data stays.
