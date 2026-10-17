# design/assets — where the design masters live

> **Status:** Current · **Verified:** 2026-09-29 · **Canonical for:** where Worlds' design masters (crew, companions, library, station and icon source art) live · **Read this if:** you are looking for a file that used to sit under `design/assets/`.

On 2026-09-29 the design masters moved out of this repository into the owner's shared media library (under
`designs/personal-world/`, with character art under `characters/`). The library keeps the original relative paths and a
ledger (`MOVE-LEDGER.csv`) mapping every old path to its new one.

The app does not load the masters. It ships its own runtime copies under `ui/public/assets/` and
`src/personal_world/static/`. Only two files stay here, because the icon build reads them:
`icons/sprite.svg` and `icons/manifest.json` (the `file` and `source` fields in the manifest name masters that now live in
the library).
