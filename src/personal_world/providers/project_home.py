"""Project Home source: read the operator's Project Home into the Worlds
briefing (contract: worlds-briefing/1).

Two transports, resolved from the environment at request time:

* CLI (preferred in dev): ``PW_PH_CLI`` -> ``<cli> home --json``
  (schema ``ph-home/1``), hard 3s timeout.
* HTTP: ``PW_PH_URL`` + ``PW_PH_TOKEN_ENV`` naming the env var that
  holds a bearer token -> ``GET <url>/api/home`` (a bare dict, no
  envelope).

Error handling: this module invents nothing. No transport configured ->
``not_configured``; any failure (timeout, bad JSON, HTTP error) ->
``unavailable`` with a short reason that names the failure class only.
The bearer token is read from its named env var and appears in no
returned field; redirects are never followed (the token must reach only
the configured origin).
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404  # drives the operator's own `lab` CLI, argument-list form only
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

#: Hard timeout for both transports — a dead source degrades, never hangs.
TIMEOUT_SECONDS = 3

CLI_ENV = "PW_PH_CLI"
URL_ENV = "PW_PH_URL"
TOKEN_ENV_ENV = "PW_PH_TOKEN_ENV"  # nosec B105  # the NAME of the env var holding the token
HTTP_PATH = "/api/home"
SCHEMA = "ph-home/1"


@dataclass(frozen=True)
class ProjectHomeResult:
    """The small result object callers receive; never raises."""

    status: str
    observed_at: str | None = None
    snapshot: dict | None = None
    reason: str | None = None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would carry the bearer token to another origin: refuse."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _valid_http_url(url: str) -> bool:
    try:
        parts = urllib.parse.urlparse(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def _pretty_project(project_id: str) -> str:
    """``proj-moon-base`` -> ``Moon Base``. Stable, no invention."""
    raw = str(project_id or "").strip()
    if raw.lower().startswith("proj-"):
        raw = raw[5:]
    return raw.replace("-", " ").replace("_", " ").strip().title()


def _derive_bookmarks(payload: dict) -> list[dict]:
    """Best-effort bookmarks when the HTTP payload omits them.

    Only what the payload already says: a ``projects`` list and/or a
    ``where_we_left_off`` map. No field is guessed into existence.
    """
    out: list[dict] = []
    projects = payload.get("projects")
    if isinstance(projects, dict):
        projects = list(projects.values())
    if isinstance(projects, list):
        for p in projects:
            if not isinstance(p, dict):
                continue
            pid = p.get("project_id") or p.get("id") or p.get("name")
            if pid is None:
                continue
            out.append({
                "project_id": pid,
                "working_on": p.get("working_on"),
                "next_action": p.get("next_action"),
                "updated_at": p.get("updated_at"),
            })
    where = payload.get("where_we_left_off")
    if isinstance(where, dict):
        for pid, text in where.items():
            out.append({
                "project_id": pid,
                "working_on": text if isinstance(text, str) else None,
                "next_action": None,
                "updated_at": None,
            })
    elif isinstance(where, str) and out:
        for b in out:
            if not b.get("working_on"):
                b["working_on"] = where
    return out


def _normalize(payload: dict) -> dict:
    """Map either transport's payload onto the briefing's snapshot shape."""
    if not isinstance(payload, dict):
        payload = {}
    if "attention_items" not in payload and isinstance(payload.get("data"), dict):
        payload = payload["data"]
    attention = payload.get("attention_items")
    if not isinstance(attention, list):
        attention = []
    bookmarks = payload.get("bookmarks")
    if not isinstance(bookmarks, list):
        bookmarks = _derive_bookmarks(payload)
    return {
        "schema": payload.get("schema", SCHEMA),
        "observed_at": payload.get("observed_at"),
        "attention_items": attention,
        "bookmarks": bookmarks,
        "last_sessions": payload.get("last_sessions") or [],
    }


class ProjectHomeSource:
    """Read-only Project Home source (CLI or HTTP)."""

    def __init__(
        self,
        cli: str | None = None,
        url: str | None = None,
        token: str | None = None,
        runner=None,
        opener=None,
    ) -> None:
        self.cli = cli
        self.url = url
        self.token = token
        #: Injection entry points for tests; default is the real machinery.
        self._runner = runner or subprocess.run
        self._opener = opener or urllib.request.build_opener(_NoRedirect)

    @classmethod
    def from_env(cls, env: dict | None = None) -> "ProjectHomeSource":
        env = os.environ if env is None else env
        cli = (env.get(CLI_ENV) or "").strip() or None
        url = (env.get(URL_ENV) or "").strip() or None
        token_env_name = (env.get(TOKEN_ENV_ENV) or "").strip()
        token = (env.get(token_env_name) or "") if token_env_name else ""
        return cls(cli=cli, url=url, token=token or None)

    def observe(self) -> ProjectHomeResult:
        """Never raises: returns a small result object."""
        try:
            if self.cli:
                return self._observe_cli()
            if self.url:
                return self._observe_http()
            return ProjectHomeResult(
                status="not_configured",
                reason="no Project Home transport configured",
            )
        except Exception as exc:  # noqa: BLE001 — a dead source must not break the view
            return ProjectHomeResult(
                status="unavailable",
                reason=f"project home read failed ({type(exc).__name__})",
            )

    # -- transports -----------------------------------------------------
    def _observe_cli(self) -> ProjectHomeResult:
        try:
            proc = self._runner(
                (self.cli, "home", "--json"),
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                check=False,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            return ProjectHomeResult(
                status="unavailable",
                reason=f"project home CLI failed ({type(exc).__name__})",
            )
        try:
            payload = json.loads(getattr(proc, "stdout", "") or "")
        except (json.JSONDecodeError, TypeError):
            return ProjectHomeResult(
                status="unavailable", reason="project home CLI returned invalid JSON"
            )
        if not isinstance(payload, dict):
            return ProjectHomeResult(
                status="unavailable", reason="project home CLI returned a non-object"
            )
        schema = payload.get("schema")
        if schema is not None and schema != SCHEMA:
            return ProjectHomeResult(
                status="unavailable",
                reason=f"project home schema is {schema!r}, expected {SCHEMA!r}",
            )
        snapshot = _normalize(payload)
        observed = snapshot.get("observed_at") or _iso_now()
        snapshot["observed_at"] = observed
        return ProjectHomeResult(
            status="healthy", observed_at=observed, snapshot=snapshot
        )

    def _observe_http(self) -> ProjectHomeResult:
        if not self.token:
            return ProjectHomeResult(
                status="not_configured",
                reason=f"{URL_ENV} set but no token is available via {TOKEN_ENV_ENV}",
            )
        url = self.url.rstrip("/") + HTTP_PATH
        if not _valid_http_url(url):
            return ProjectHomeResult(
                status="not_configured",
                reason=f"{URL_ENV} is not an absolute http(s) address",
            )
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            },
        )
        try:
            with self._opener.open(req, timeout=TIMEOUT_SECONDS) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            return ProjectHomeResult(
                status="unavailable", reason=f"project home HTTP {exc.code}"
            )
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return ProjectHomeResult(
                status="unavailable",
                reason=f"project home HTTP failed ({type(exc).__name__})",
            )
        try:
            payload = json.loads(raw.decode("utf-8", "replace"))
        except (json.JSONDecodeError, TypeError, AttributeError):
            return ProjectHomeResult(
                status="unavailable", reason="project home HTTP returned invalid JSON"
            )
        if not isinstance(payload, dict):
            return ProjectHomeResult(
                status="unavailable", reason="project home HTTP returned a non-object"
            )
        snapshot = _normalize(payload)
        observed = snapshot.get("observed_at") or _iso_now()
        snapshot["observed_at"] = observed
        return ProjectHomeResult(
            status="healthy", observed_at=observed, snapshot=snapshot
        )
