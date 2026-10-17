#!/usr/bin/env python3
"""S2: regenerate ui/src/generated/openapi.json from the LIVE rebuild app.

The front-door app is ``personal_world.worlds.production:create_app``; the old
``personal_world.api:create_app`` is being deleted. This writes the committed
OpenAPI document from the new app built on a throwaway config/data dir, so no
owner policy, credential or network is needed:

    uv run python scripts/gen-openapi.py

Consumer: ``ui/scripts/generate-api-types.mjs`` (run by ``npm run api:generate``,
which is part of ``npm run build``) reads this file and writes
``ui/src/generated/api-types.ts``.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from personal_world.worlds.production import create_app  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="pw-openapi-"))
spec = create_app(tmp / "config", tmp / "data").openapi()
out = ROOT / "ui" / "src" / "generated" / "openapi.json"
out.write_text(json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
print(f"regenerated {out} — {len(spec['paths'])} paths from live routes")
