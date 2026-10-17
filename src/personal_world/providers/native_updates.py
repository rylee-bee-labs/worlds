"""Native Updates provider: lightweight version/update discovery.

Checks GitHub Releases, OCI/container registry, or version URLs.
Runs only when requested or scheduled. No update service required.
Normalizes: installed version, available version, source, release date,
significance, provenance.
"""

import json
import urllib.error
import urllib.request

from ..envelope import Result, fail, ok
from ..status import Status
from ..url_safety import http_urlopen
from .registry import StatusContract


class GitHubReleasesAdapter:
    """Check GitHub releases for updates."""

    def __init__(self, repo, current_version=None):
        self.repo = repo  # e.g. "Rylee-Bee/personal-world"
        self.current_version = current_version

    def check(self) -> dict:
        try:
            url = f"https://api.github.com/repos/{self.repo}/releases/latest"
            req = urllib.request.Request(url, headers={
                "User-Agent": "ProjectWorlds/1.0",
                "Accept": "application/vnd.github.v3+json",
            })
            with http_urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            return {
                "available": data.get("tag_name", ""),
                "published": data.get("published_at", ""),
                "url": data.get("html_url", ""),
                "notes": (data.get("body") or "")[:500],
                "source": "github",
                "provider": f"github:{self.repo}",
            }
        except Exception as e:
            return {"error": str(e), "source": "github", "provider": f"github:{self.repo}"}


class VersionUrlAdapter:
    """Check a simple version URL for the latest version."""

    def __init__(self, url, current_version=None):
        self.url = url
        self.current_version = current_version

    def check(self) -> dict:
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "ProjectWorlds/1.0"})
            with http_urlopen(req, timeout=15) as resp:
                version = resp.read().decode().strip()
            return {
                "available": version,
                "source": "url",
                "provider": self.url,
            }
        except Exception as e:
            return {"error": str(e), "source": "url", "provider": self.url}


class NativeUpdatesProvider(StatusContract):
    """Native update discovery capability."""

    def __init__(self, config=None):
        self._adapters = []
        self._config = config or {}
        self._load_adapters()

    def _load_adapters(self):
        """Load configured update sources."""
        sources = self._config.get("sources", [])
        for s in sources:
            stype = s.get("type")
            if stype == "github" and s.get("repo"):
                self._adapters.append(GitHubReleasesAdapter(s["repo"], s.get("current_version")))
            elif stype == "url" and s.get("url"):
                self._adapters.append(VersionUrlAdapter(s["url"], s.get("current_version")))

    def observe(self) -> Result:
        """Report update discovery capability status."""
        if not self._adapters:
            return ok(Status.NOT_CONFIGURED.value, data={
                "sources": [],
                "message": "no update sources configured",
                "provider": "native_updates",
            })
        return ok(Status.HEALTHY.value, data={
            "sources": [type(a).__name__ for a in self._adapters],
            "provider": "native_updates",
        })

    def check(self) -> Result:
        """Check for available updates."""
        try:
            results = []
            for adapter in self._adapters:
                result = adapter.check()
                results.append(result)
            return ok(Status.HEALTHY.value, data={"updates": results, "count": len(results)})
        except Exception as e:
            return fail(Status.UNAVAILABLE.value, warnings=[f"updates: {e}"])

    def health(self) -> bool:
        return True
