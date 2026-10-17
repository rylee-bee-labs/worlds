# Third-Party Notices

Project Worlds depends on, vendors, or links to the following
third-party material. Each entry preserves the upstream license
and attribution the upstream project requires.

## Runtime dependencies (backend)

| Package | License | Source |
|---|---|---|
| FastAPI | BSD-3-Clause | https://github.com/tiangolo/fastapi |
| Uvicorn | BSD-3-Clause | https://github.com/encode/uvicorn |
| httpx | BSD-3-Clause | https://github.com/encode/httpx |
| Pydantic | MIT | https://github.com/pydantic/pydantic |
| SQLAlchemy | MIT | https://github.com/sqlalchemy/sqlalchemy |

## Runtime dependencies (frontend)

The frontend is a Vite + TypeScript + React application. Build-time
dependencies are listed in `web/package.json` (and `web/bun.lock`
when present); production dependencies are bundled into the public
build by Vite. Each dependency retains its upstream license in the
respective `node_modules/<package>/LICENSE` file.

## Bundled artwork

Project Worlds ships approved showcase artwork in `artifacts/`. Each
artwork file retains its upstream attribution in the file's
EXIF/metadata or in the surrounding `attribution.md` when present.
Showcase artwork is approved for redistribution as part of this
project; downstream forks may keep the artwork or replace it with
their own. The `artifacts/` directory is treated as curated
material, not as third-party-license-debt.

`ui/public/assets/painted/` holds the owner's own painted icons, copied from
the design-system icon set (source and version in its README). They are not
third-party material.

## Fonts and icons

Bundled fonts and icons retain their original licenses. Each
family's license and source are listed in `web/fonts/README.md`
or `web/src/assets/` (whichever applies) where present.

## Generated artifacts and runtime state

- `data/` is gitignored and never shipped.
- Personal journals, lore, deployment inventories, provider
  configs, backups, and operational logs are NEVER part of this
  repository. They live outside Git by design. See
  `SECURITY.md`'s "Public repository boundary" section.
- An ignore rule does not remove files already tracked or erase
  history.
