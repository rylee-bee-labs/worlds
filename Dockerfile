# Base images are pinned by digest (bump: docs/OPERATIONS.md, "Bumping the pins").

# --- interface build stage ---------------------------------------------
# The React rebuild IS the product frontend (owner decision 2026-09-22).
# The image builds it from ui/ in this repo — a fresh clone can produce a
# complete, shippable container with no sibling checkouts and no manual
# staging step. The build reads design/tokens.json + design/themes/*.json
# (token generation is cross-directory by design), so both trees are in
# the stage.
FROM node:24-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6 AS ui-build
WORKDIR /src
COPY ui/package.json ui/package-lock.json ./ui/
RUN cd ui && npm ci --no-audit --no-fund
COPY design/ ./design/
# The Library's books (docs/library/*.md) are bundled into the UI.
COPY docs/library/ ./docs/library/
COPY ui/ ./ui/
# The same commit /healthz reports, baked into the UI so an open page knows
# which build its code is (StayFresh compares the two).
ARG PW_COMMIT=""
ENV VITE_PW_COMMIT=$PW_COMMIT
RUN cd ui && npm run build

# --- runtime stage ----------------------------------------------------
# Pinned by digest (see the note at the top of this file).
FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e

# git: source-control capability feeds the dashboard + chat context.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git jq curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --extra crypto \
    && rm -rf ~/.cache

COPY src ./src
# Stage the built interface where app_router() reads it. This is build
# output, not source: .gitignore keeps static/app/ out of git, while
# .dockerignore's `**/dist` drops only raw Vite dirs from the context —
# the COPY --from below is what puts the build into the image.
COPY --from=ui-build /src/ui/dist ./src/personal_world/static/app
RUN test -f src/personal_world/static/app/index.html \
    && echo "interface staged into image: $(ls src/personal_world/static/app | tr '\n' ' ')"
# NOTE on the install dance below: `uv run` (CMD) re-syncs the project
# editable at boot, so `import personal_world` resolves to /app/src/... —
# that is what makes the staged, gitignored static/app visible in the
# container (the non-editable wheel excludes it). Do not delete the src
# tree from the image.
RUN uv pip install --no-cache-dir .

# The commit this image was built from. publish-image.yml passes the
# validated main SHA as a build arg; /healthz reports its first 7 chars
# so Project Home can compare what is live against main. A local
# `docker build` passes nothing and the value is empty (reported null).
ARG PW_COMMIT=""

ENV PW_DATA_DIR=/data \
    PW_CONFIG_DIR=/config \
    PW_COMMIT=$PW_COMMIT
# What this image serves: the interface at / (built above), the API at
# /api/*, and server-rendered /login and /setup. The retired /station and
# /vnext paths only redirect to /. The vanilla Station is no longer
# packaged (owner decision 2026-09-22 — one interface, plain and
# responsive, with the starfield color system).

VOLUME /data
VOLUME /config

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys,os; \
        r=urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=4); \
        sys.exit(0 if r.status==200 else 1)"

# Fail fast at runtime when auth is unconfigured: an empty PW_API_TOKEN
# must never serve. This is the boot-time guard, kept deliberately separate
# from the owner.yaml bootstrap below: app_from_env is the production auth
# path, but a container that boots with no token at all is a misconfiguration
# we want to hear about in the log, not serve. Covered by
# tests/test_safety.py::TestEntrypointTokenGuard.
# Production auth itself is the owner.yaml bootstrap
# (worlds/production.py:app_from_env): with no valid owner.yaml nobody can
# sign in and cookie-authenticated writes are refused. The HEALTHCHECK above
# is the liveness gate.
CMD ["sh", "-c", \
     "test -n \"$PW_API_TOKEN\" || { echo 'FATAL: PW_API_TOKEN is empty or unset; refusing to boot (auth is fail-closed).' >&2; exit 1; }; \
      exec uv run uvicorn personal_world.worlds.production:app_from_env --factory \
       --proxy-headers --forwarded-allow-ips='*' \
       --host 0.0.0.0 --port 8000"]
