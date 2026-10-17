"""Native Media provider: media library management for Project Worlds.

This is the native Media product that ships with Project Worlds.
It provides capabilities for:
- Media library inventory (movies, series, albums, episodes)
- Activity/queue monitoring (downloading, queued, completed, failed)
- Recently added content
- Search across connected providers
- degradation when providers are absent or unreachable

Supported providers: Plex, Sonarr, Radarr, Lidarr.
Users configure their own instances through connection config.
"""

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from ..envelope import Result, fail, ok
from ..status import Status
from ..url_safety import http_urlopen
from .registry import Contract

# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


@dataclass
class MediaItem:
    """Normalized media item from any provider."""

    id: str
    title: str
    kind: str  # movie | series | album | episode
    year: int | None = None
    poster_url: str | None = None
    provider: str = ""
    availability: str = "unknown"  # available | missing | downloading | unknown
    status: str = "unknown"  # monitored | unmonitored | unknown
    progress: float | None = None  # 0-100 or None
    added_at: str | None = None
    watched_at: str | None = None
    upstream_url: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "year": self.year,
            "poster_url": self.poster_url,
            "provider": self.provider,
            "availability": self.availability,
            "status": self.status,
            "progress": self.progress,
            "added_at": self.added_at,
            "watched_at": self.watched_at,
            "upstream_url": self.upstream_url,
            "provenance": self.provenance,
        }


@dataclass
class MediaLibrary:
    """Library section from a provider."""

    id: str
    name: str
    kind: str  # movie | series | music
    item_count: int = 0
    provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "item_count": self.item_count,
            "provider": self.provider,
        }


@dataclass
class MediaActivity:
    """Activity/queue item from a provider."""

    id: str
    title: str
    kind: str  # movie | series | album | episode
    status: str = "unknown"  # downloading | queued | completed | failed
    progress: float | None = None
    eta: str | None = None
    provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "status": self.status,
            "progress": self.progress,
            "eta": self.eta,
            "provider": self.provider,
        }


# ---------------------------------------------------------------------------
# Base adapter
# ---------------------------------------------------------------------------


class MediaAdapter(Contract):
    """Base class for media provider adapters."""

    provider_name: str = ""

    def _get_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        req = urllib.request.Request(url)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        with http_urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    def libraries(self) -> Result:
        return fail(
            "not_implemented",
            warnings=[f"{self.provider_name}: libraries not implemented"],
        )

    def recent(self, limit: int = 20) -> Result:
        return fail(
            "not_implemented",
            warnings=[f"{self.provider_name}: recent not implemented"],
        )

    def activity(self) -> Result:
        return fail(
            "not_implemented",
            warnings=[f"{self.provider_name}: activity not implemented"],
        )

    def search(self, query: str) -> Result:
        return fail(
            "not_implemented",
            warnings=[f"{self.provider_name}: search not implemented"],
        )

    def item(self, item_id: str) -> Result:
        return fail(
            "not_implemented", warnings=[f"{self.provider_name}: item not implemented"]
        )

    def status(self) -> Result:
        return fail(
            "not_implemented",
            warnings=[f"{self.provider_name}: status not implemented"],
        )


# ---------------------------------------------------------------------------
# Plex adapter
# ---------------------------------------------------------------------------


class PlexAdapter(MediaAdapter):
    """Plex Media Server adapter.

    Connects to Plex API for library sections, recently added, and status.
    Uses X-Plex-Token for authentication.
    """

    provider_name = "plex"

    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def _plex_url(self, path: str) -> str:
        sep = "&" if "?" in path else "?"
        return f"{self.base_url}{path}{sep}X-Plex-Token={self.token}"

    def status(self) -> Result:
        try:
            data = self._get_json(self._plex_url("/status/sessions"), self._headers())
            media_container = data.get("MediaContainer", {})
            return ok(
                Status.HEALTHY.value,
                data={
                    "provider": self.provider_name,
                    "active_sessions": media_container.get("size", 0),
                    "base_url": self.base_url,
                },
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"plex status: {e}"],
            )

    def libraries(self) -> Result:
        try:
            data = self._get_json(self._plex_url("/library/sections"), self._headers())
            directories = data.get("MediaContainer", {}).get("Directory", [])
            libs = []
            for d in directories:
                kind_map = {"movie": "movie", "show": "series", "artist": "music"}
                libs.append(
                    MediaLibrary(
                        id=str(d.get("key", "")),
                        name=d.get("title", ""),
                        kind=kind_map.get(d.get("type", ""), d.get("type", "unknown")),
                        item_count=d.get("leafCount", 0),
                        provider=self.provider_name,
                    )
                )
            return ok(
                Status.HEALTHY.value,
                data={"libraries": [lib.to_dict() for lib in libs], "count": len(libs)},
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"plex libraries: {e}"],
            )

    def recent(self, limit: int = 20) -> Result:
        try:
            data = self._get_json(
                self._plex_url(
                    "/library/recentlyAdded?X-Plex-Container-Start=0&X-Plex-Container-Size={limit}"
                ),
                self._headers(),
            )
            items_raw = data.get("MediaContainer", {}).get("Metadata", [])
            items = []
            for m in items_raw[:limit]:
                kind_map = {
                    "movie": "movie",
                    "show": "series",
                    "artist": "album",
                    "episode": "episode",
                }
                items.append(
                    MediaItem(
                        id=f"plex:{m.get('ratingKey', '')}",
                        title=m.get("title", ""),
                        kind=kind_map.get(m.get("type", ""), "unknown"),
                        year=m.get("year"),
                        poster_url=m.get("thumb"),
                        provider=self.provider_name,
                        availability="available",
                        added_at=m.get("addedAt"),
                        provenance={"source": "plex", "key": m.get("ratingKey")},
                    )
                )
            return ok(
                Status.HEALTHY.value,
                data={"items": [i.to_dict() for i in items], "count": len(items)},
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"plex recent: {e}"],
            )

    def activity(self) -> Result:
        try:
            data = self._get_json(self._plex_url("/status/sessions"), self._headers())
            items_raw = data.get("MediaContainer", {}).get("Metadata", [])
            activities = []
            for m in items_raw:
                media = (m.get("Media") or [{}])[0]
                part = (media.get("Part") or [{}])[0]
                activities.append(
                    MediaActivity(
                        id=f"plex:session:{m.get('ratingKey', '')}",
                        title=m.get("title", ""),
                        kind=m.get("type", "unknown"),
                        status="downloading"
                        if part.get("progress") is not None
                        else "completed",
                        progress=part.get("progress"),
                        provider=self.provider_name,
                    )
                )
            return ok(
                Status.HEALTHY.value,
                data={
                    "activities": [a.to_dict() for a in activities],
                    "count": len(activities),
                },
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"plex activity: {e}"],
            )


# ---------------------------------------------------------------------------
# Sonarr adapter
# ---------------------------------------------------------------------------


class SonarrAdapter(MediaAdapter):
    """Sonarr (TV) adapter.

    Connects to Sonarr v3 API for series, episodes, and queue.
    Uses X-Api-Key for authentication.
    """

    provider_name = "sonarr"

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self.api_key, "Accept": "application/json"}

    def status(self) -> Result:
        try:
            data = self._get_json(
                f"{self.base_url}/api/v3/system/status", self._headers()
            )
            return ok(
                Status.HEALTHY.value,
                data={
                    "provider": self.provider_name,
                    "version": data.get("version", "unknown"),
                    "base_url": self.base_url,
                },
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"sonarr status: {e}"],
            )

    def libraries(self) -> Result:
        try:
            data = self._get_json(f"{self.base_url}/api/v3/series", self._headers())
            libs_map: dict[str, MediaLibrary] = {}
            for s in data:
                path = s.get("path", "/")
                root = path.split("/")[1] if "/" in path else "default"
                if root not in libs_map:
                    libs_map[root] = MediaLibrary(
                        id=f"sonarr:{root}",
                        name=root,
                        kind="series",
                        item_count=0,
                        provider=self.provider_name,
                    )
                libs_map[root].item_count += 1
            return ok(
                Status.HEALTHY.value,
                data={
                    "libraries": [lib.to_dict() for lib in libs_map.values()],
                    "count": len(libs_map),
                },
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"sonarr libraries: {e}"],
            )

    def recent(self, limit: int = 20) -> Result:
        try:
            data = self._get_json(f"{self.base_url}/api/v3/series", self._headers())
            items = []
            for s in sorted(data, key=lambda x: x.get("added", ""), reverse=True)[
                :limit
            ]:
                items.append(
                    MediaItem(
                        id=f"sonarr:{s.get('id', '')}",
                        title=s.get("title", ""),
                        kind="series",
                        year=s.get("year"),
                        poster_url=s.get("images", [{}])[0].get("remoteUrl")
                        if s.get("images")
                        else None,
                        provider=self.provider_name,
                        availability="available"
                        if s.get("statistics", {}).get("episodeFileCount", 0) > 0
                        else "missing",
                        status="monitored" if s.get("monitored") else "unmonitored",
                        added_at=s.get("added"),
                        provenance={"source": "sonarr", "id": s.get("id")},
                    )
                )
            return ok(
                Status.HEALTHY.value,
                data={"items": [i.to_dict() for i in items], "count": len(items)},
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"sonarr recent: {e}"],
            )

    def activity(self) -> Result:
        try:
            data = self._get_json(f"{self.base_url}/api/v3/queue", self._headers())
            records = data.get("records", [])
            activities = []
            for r in records:
                title = r.get("title", "")
                series = r.get("series", {})
                if series:
                    title = f"{series.get('title', '')} - {title}"
                activities.append(
                    MediaActivity(
                        id=f"sonarr:queue:{r.get('id', '')}",
                        title=title,
                        kind="episode",
                        status=self._map_queue_status(r.get("status", "")),
                        progress=r.get("sizeleft", 0)
                        and round(
                            (1 - r.get("sizeleft", 0) / max(r.get("size", 1), 1)) * 100,
                            1,
                        ),
                        eta=r.get("timeleft"),
                        provider=self.provider_name,
                    )
                )
            return ok(
                Status.HEALTHY.value,
                data={
                    "activities": [a.to_dict() for a in activities],
                    "count": len(activities),
                },
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"sonarr activity: {e}"],
            )

    def search(self, query: str) -> Result:
        try:
            encoded = urllib.request.quote(query)
            data = self._get_json(
                f"{self.base_url}/api/v3/series/lookup?term={encoded}", self._headers()
            )
            items = []
            for s in data:
                items.append(
                    MediaItem(
                        id=f"sonarr:lookup:{s.get('tvdbId', s.get('title', ''))}",
                        title=s.get("title", ""),
                        kind="series",
                        year=s.get("year"),
                        poster_url=s.get("images", [{}])[0].get("remoteUrl")
                        if s.get("images")
                        else None,
                        provider=self.provider_name,
                        availability="unknown",
                        status="unknown",
                        provenance={"source": "sonarr", "tvdbId": s.get("tvdbId")},
                    )
                )
            return ok(
                Status.HEALTHY.value,
                data={"items": [i.to_dict() for i in items], "count": len(items)},
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"sonarr search: {e}"],
            )

    def item(self, item_id: str) -> Result:
        try:
            real_id = item_id.removeprefix("sonarr:")
            data = self._get_json(
                f"{self.base_url}/api/v3/series/{real_id}", self._headers()
            )
            stats = data.get("statistics", {})
            total = stats.get("episodeCount", 0)
            has_file = stats.get("episodeFileCount", 0)
            progress = round((has_file / max(total, 1)) * 100, 1) if total else None
            item = MediaItem(
                id=f"sonarr:{data.get('id', '')}",
                title=data.get("title", ""),
                kind="series",
                year=data.get("year"),
                poster_url=data.get("images", [{}])[0].get("remoteUrl")
                if data.get("images")
                else None,
                provider=self.provider_name,
                availability="available"
                if has_file == total and total > 0
                else "missing",
                status="monitored" if data.get("monitored") else "unmonitored",
                progress=progress,
                added_at=data.get("added"),
                provenance={"source": "sonarr", "id": data.get("id")},
            )
            return ok(Status.HEALTHY.value, data=item.to_dict())
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"sonarr item: {e}"],
            )

    @staticmethod
    def _map_queue_status(raw: str) -> str:
        mapping = {
            "downloading": "downloading",
            "queued": "queued",
            "completed": "completed",
            "failed": "failed",
            "paused": "queued",
        }
        return mapping.get(raw.lower(), raw)


# ---------------------------------------------------------------------------
# Radarr adapter
# ---------------------------------------------------------------------------


class RadarrAdapter(MediaAdapter):
    """Radarr (movies) adapter.

    Connects to Radarr v3 API for movies and queue.
    Uses X-Api-Key for authentication.
    """

    provider_name = "radarr"

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self.api_key, "Accept": "application/json"}

    def status(self) -> Result:
        try:
            data = self._get_json(
                f"{self.base_url}/api/v3/system/status", self._headers()
            )
            return ok(
                Status.HEALTHY.value,
                data={
                    "provider": self.provider_name,
                    "version": data.get("version", "unknown"),
                    "base_url": self.base_url,
                },
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"radarr status: {e}"],
            )

    def libraries(self) -> Result:
        try:
            data = self._get_json(f"{self.base_url}/api/v3/movie", self._headers())
            libs_map: dict[str, MediaLibrary] = {}
            for m in data:
                path = m.get("path", "/")
                root = path.split("/")[1] if "/" in path else "default"
                if root not in libs_map:
                    libs_map[root] = MediaLibrary(
                        id=f"radarr:{root}",
                        name=root,
                        kind="movie",
                        item_count=0,
                        provider=self.provider_name,
                    )
                libs_map[root].item_count += 1
            return ok(
                Status.HEALTHY.value,
                data={
                    "libraries": [lib.to_dict() for lib in libs_map.values()],
                    "count": len(libs_map),
                },
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"radarr libraries: {e}"],
            )

    def recent(self, limit: int = 20) -> Result:
        try:
            data = self._get_json(f"{self.base_url}/api/v3/movie", self._headers())
            items = []
            for m in sorted(data, key=lambda x: x.get("added", ""), reverse=True)[
                :limit
            ]:
                has_file = m.get("hasFile", False)
                items.append(
                    MediaItem(
                        id=f"radarr:{m.get('id', '')}",
                        title=m.get("title", ""),
                        kind="movie",
                        year=m.get("year"),
                        poster_url=m.get("images", [{}])[0].get("remoteUrl")
                        if m.get("images")
                        else None,
                        provider=self.provider_name,
                        availability="available" if has_file else "missing",
                        status="monitored" if m.get("monitored") else "unmonitored",
                        added_at=m.get("added"),
                        provenance={"source": "radarr", "id": m.get("id")},
                    )
                )
            return ok(
                Status.HEALTHY.value,
                data={"items": [i.to_dict() for i in items], "count": len(items)},
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"radarr recent: {e}"],
            )

    def activity(self) -> Result:
        try:
            data = self._get_json(f"{self.base_url}/api/v3/queue", self._headers())
            records = data.get("records", [])
            activities = []
            for r in records:
                activities.append(
                    MediaActivity(
                        id=f"radarr:queue:{r.get('id', '')}",
                        title=r.get("title", ""),
                        kind="movie",
                        status=self._map_queue_status(r.get("status", "")),
                        progress=r.get("sizeleft", 0)
                        and round(
                            (1 - r.get("sizeleft", 0) / max(r.get("size", 1), 1)) * 100,
                            1,
                        ),
                        eta=r.get("timeleft"),
                        provider=self.provider_name,
                    )
                )
            return ok(
                Status.HEALTHY.value,
                data={
                    "activities": [a.to_dict() for a in activities],
                    "count": len(activities),
                },
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"radarr activity: {e}"],
            )

    def search(self, query: str) -> Result:
        try:
            encoded = urllib.request.quote(query)
            data = self._get_json(
                f"{self.base_url}/api/v3/movie/lookup?term={encoded}", self._headers()
            )
            items = []
            for m in data:
                items.append(
                    MediaItem(
                        id=f"radarr:lookup:{m.get('tmdbId', m.get('title', ''))}",
                        title=m.get("title", ""),
                        kind="movie",
                        year=m.get("year"),
                        poster_url=m.get("images", [{}])[0].get("remoteUrl")
                        if m.get("images")
                        else None,
                        provider=self.provider_name,
                        availability="unknown",
                        status="unknown",
                        provenance={"source": "radarr", "tmdbId": m.get("tmdbId")},
                    )
                )
            return ok(
                Status.HEALTHY.value,
                data={"items": [i.to_dict() for i in items], "count": len(items)},
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"radarr search: {e}"],
            )

    def item(self, item_id: str) -> Result:
        try:
            real_id = item_id.removeprefix("radarr:")
            data = self._get_json(
                f"{self.base_url}/api/v3/movie/{real_id}", self._headers()
            )
            item = MediaItem(
                id=f"radarr:{data.get('id', '')}",
                title=data.get("title", ""),
                kind="movie",
                year=data.get("year"),
                poster_url=data.get("images", [{}])[0].get("remoteUrl")
                if data.get("images")
                else None,
                provider=self.provider_name,
                availability="available" if data.get("hasFile") else "missing",
                status="monitored" if data.get("monitored") else "unmonitored",
                added_at=data.get("added"),
                provenance={"source": "radarr", "id": data.get("id")},
            )
            return ok(Status.HEALTHY.value, data=item.to_dict())
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"radarr item: {e}"],
            )

    @staticmethod
    def _map_queue_status(raw: str) -> str:
        mapping = {
            "downloading": "downloading",
            "queued": "queued",
            "completed": "completed",
            "failed": "failed",
            "paused": "queued",
        }
        return mapping.get(raw.lower(), raw)


# ---------------------------------------------------------------------------
# Lidarr adapter
# ---------------------------------------------------------------------------


class LidarrAdapter(MediaAdapter):
    """Lidarr (music) adapter.

    Connects to Lidarr v1 API for artists, albums, and queue.
    Uses X-Api-Key for authentication.
    """

    provider_name = "lidarr"

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self.api_key, "Accept": "application/json"}

    def status(self) -> Result:
        try:
            data = self._get_json(
                f"{self.base_url}/api/v1/system/status", self._headers()
            )
            return ok(
                Status.HEALTHY.value,
                data={
                    "provider": self.provider_name,
                    "version": data.get("version", "unknown"),
                    "base_url": self.base_url,
                },
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"lidarr status: {e}"],
            )

    def libraries(self) -> Result:
        try:
            artists = self._get_json(f"{self.base_url}/api/v1/artist", self._headers())
            album_count = 0
            for a in artists:
                album_count += a.get("statistics", {}).get("albumCount", 0)
            libs = [
                MediaLibrary(
                    id="lidarr:music",
                    name="Music",
                    kind="music",
                    item_count=len(artists),
                    provider=self.provider_name,
                ),
            ]
            return ok(
                Status.HEALTHY.value,
                data={
                    "libraries": [lib.to_dict() for lib in libs],
                    "count": len(libs),
                    "artist_count": len(artists),
                    "album_count": album_count,
                },
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"lidarr libraries: {e}"],
            )

    def recent(self, limit: int = 20) -> Result:
        try:
            albums = self._get_json(f"{self.base_url}/api/v1/album", self._headers())
            items = []
            for a in sorted(albums, key=lambda x: x.get("added", ""), reverse=True)[
                :limit
            ]:
                items.append(
                    MediaItem(
                        id=f"lidarr:album:{a.get('id', '')}",
                        title=a.get("title", ""),
                        kind="album",
                        year=a.get("releaseDate", "")[:4]
                        if a.get("releaseDate")
                        else None,
                        provider=self.provider_name,
                        availability="available"
                        if a.get("statistics", {}).get("trackFileCount", 0) > 0
                        else "missing",
                        status="monitored" if a.get("monitored") else "unmonitored",
                        added_at=a.get("added"),
                        provenance={"source": "lidarr", "id": a.get("id")},
                    )
                )
            return ok(
                Status.HEALTHY.value,
                data={"items": [i.to_dict() for i in items], "count": len(items)},
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"lidarr recent: {e}"],
            )

    def activity(self) -> Result:
        try:
            data = self._get_json(f"{self.base_url}/api/v1/queue", self._headers())
            records = data.get("records", [])
            activities = []
            for r in records:
                activities.append(
                    MediaActivity(
                        id=f"lidarr:queue:{r.get('id', '')}",
                        title=r.get("title", ""),
                        kind="album",
                        status=self._map_queue_status(r.get("status", "")),
                        progress=r.get("sizeleft", 0)
                        and round(
                            (1 - r.get("sizeleft", 0) / max(r.get("size", 1), 1)) * 100,
                            1,
                        ),
                        eta=r.get("timeleft"),
                        provider=self.provider_name,
                    )
                )
            return ok(
                Status.HEALTHY.value,
                data={
                    "activities": [a.to_dict() for a in activities],
                    "count": len(activities),
                },
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"lidarr activity: {e}"],
            )

    def search(self, query: str) -> Result:
        try:
            encoded = urllib.request.quote(query)
            data = self._get_json(
                f"{self.base_url}/api/v1/artist/lookup?term={encoded}", self._headers()
            )
            items = []
            for a in data:
                items.append(
                    MediaItem(
                        id=f"lidarr:lookup:{a.get('foreignId', a.get('artistName', ''))}",
                        title=a.get("artistName", ""),
                        kind="album",
                        provider=self.provider_name,
                        availability="unknown",
                        status="unknown",
                        provenance={
                            "source": "lidarr",
                            "foreignId": a.get("foreignId"),
                        },
                    )
                )
            return ok(
                Status.HEALTHY.value,
                data={"items": [i.to_dict() for i in items], "count": len(items)},
            )
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"lidarr search: {e}"],
            )

    def item(self, item_id: str) -> Result:
        try:
            real_id = item_id.removeprefix("lidarr:album:")
            data = self._get_json(
                f"{self.base_url}/api/v1/album/{real_id}", self._headers()
            )
            stats = data.get("statistics", {})
            total = stats.get("trackCount", 0)
            has_file = stats.get("trackFileCount", 0)
            progress = round((has_file / max(total, 1)) * 100, 1) if total else None
            item = MediaItem(
                id=f"lidarr:album:{data.get('id', '')}",
                title=data.get("title", ""),
                kind="album",
                year=data.get("releaseDate", "")[:4]
                if data.get("releaseDate")
                else None,
                provider=self.provider_name,
                availability="available"
                if has_file == total and total > 0
                else "missing",
                status="monitored" if data.get("monitored") else "unmonitored",
                progress=progress,
                added_at=data.get("added"),
                provenance={"source": "lidarr", "id": data.get("id")},
            )
            return ok(Status.HEALTHY.value, data=item.to_dict())
        except Exception as e:
            return Result(
                ok=False,
                status=Status.UNAVAILABLE.value,
                warnings=[f"lidarr item: {e}"],
            )

    @staticmethod
    def _map_queue_status(raw: str) -> str:
        mapping = {
            "downloading": "downloading",
            "queued": "queued",
            "completed": "completed",
            "failed": "failed",
            "paused": "queued",
        }
        return mapping.get(raw.lower(), raw)


# ---------------------------------------------------------------------------
# Provider builder
# ---------------------------------------------------------------------------

_ADAPTERS: dict[str, type[MediaAdapter]] = {
    "plex": PlexAdapter,
    "sonarr": SonarrAdapter,
    "radarr": RadarrAdapter,
    "lidarr": LidarrAdapter,
}


def build_adapter(config: dict[str, Any]) -> MediaAdapter | None:
    """Build a MediaAdapter from a connection config dict.

    Credential resolution order:
        1. Env var indirection: token_env/api_key_env names an env var
        2. Default env var: PLEX_TOKEN, SONARR_API_KEY, etc.
        3. Inline credential (token/api_key fields) when the value is
           not a reference-shaped value.

    Secret references (vault refs and placeholder-style names) are
    NOT passed upstream as though they were credentials; inline
    credentials (from connections.json, not the UI) are
    still accepted for backward compatibility with env-var-based
    configurations.

    Returns None if no credential is available.
    """
    provider_type = config.get("type")
    base_url = config.get("base_url")

    if not provider_type or not base_url:
        return None

    cls = _ADAPTERS.get(provider_type)
    if cls is None:
        return None

    if provider_type == "plex":
        # Env var indirection, default env var, then inline credential
        # (only when the inline value is not a reference).
        token = (
            os.environ.get(config.get("token_env", ""), "")
            or os.environ.get("PLEX_TOKEN", "")
            or ("" if _is_secret_ref(config, "token") else config.get("token", ""))
        )
        if not token:
            return None
        return cls(base_url=base_url, token=token)

    api_key = (
        os.environ.get(config.get("api_key_env", ""), "")
        or os.environ.get(f"{provider_type.upper()}_API_KEY", "")
        or ("" if _is_secret_ref(config, "api_key") else config.get("api_key", ""))
    )
    if not api_key:
        return None
    return cls(base_url=base_url, api_key=api_key)


# Values that are unambiguously references, never credentials.
_SECRET_REF_URL_RE = re.compile(r"\b(?:vault|secret)://|\$\{")
# Reference-style names: short lowercase identifiers with separators,
# e.g. "my-plex-token". Real API keys/tokens are not name-shaped.
_SECRET_REF_NAME_RE = re.compile(r"^[a-z0-9]+([-_][a-z0-9]+)+$")


def _is_secret_ref(config: dict[str, Any], field: str) -> bool:
    """Detect whether a config field contains an unresolved secret reference.

    A field is a secret reference if:
    - It has a value AND
    - There is no corresponding _env field (env indirection is the
      declared credential path) AND
    - The value looks like a reference rather than a credential:
      a vault:// or secret:// URL, a ${VAR} placeholder, or a short
      lowercase name such as "my-plex-token".

    Real credentials (API keys, tokens) do not match that name shape,
    so inline credentials stay accepted for backward compatibility.
    Anything ambiguous is treated as a reference and refused.
    """
    value = config.get(field)
    if not value or not isinstance(value, str):
        return False
    # If there's a corresponding _env field, the direct value field
    # is not the primary credential path — the env var is.
    if config.get(f"{field}_env"):
        return False
    if _SECRET_REF_URL_RE.search(value):
        return True
    return bool(_SECRET_REF_NAME_RE.fullmatch(value))


# ---------------------------------------------------------------------------
# Canonical engine construction (single helper for API + tools)
# ---------------------------------------------------------------------------

MEDIA_CONNECTION_TYPES = ("plex", "sonarr", "radarr", "lidarr")


def build_media_engine_from_config(config_dir):
    """Build a NativeMediaEngine from a config dir's connections.json.

    THE one construction path (BATCH 9): the API route module and the
    tool registry both call this, so media engine behavior cannot
    drift between surfaces. Absent/unreadable config yields an empty
    engine (degradation, no crash). Adapters whose credential
    env is unset are skipped by build_adapter.
    """
    import json as _json
    from pathlib import Path as _Path

    config_path = _Path(config_dir) / "connections.json"
    if not config_path.exists():
        return NativeMediaEngine([])
    try:
        config = _json.loads(config_path.read_text())
    except (OSError, _json.JSONDecodeError):
        return NativeMediaEngine([])
    connections = [
        conn
        for conn in config.get("connections", [])
        if isinstance(conn, dict) and conn.get("type") in MEDIA_CONNECTION_TYPES
    ]
    return build_media_engine_from_connections(connections)


def build_media_engine_from_connections(
    connections: list[dict[str, Any]] | None,
) -> "NativeMediaEngine":
    """Build a NativeMediaEngine from already-loaded connection dicts.

    Companion to build_media_engine_from_config for callers whose
    config is merged in memory (ConnectionManager). Filters to the
    media connection types; the engine itself drops connections whose
    credentials do not resolve (degradation).
    """
    return NativeMediaEngine(
        [
            conn
            for conn in (connections or [])
            if isinstance(conn, dict) and conn.get("type") in MEDIA_CONNECTION_TYPES
        ]
    )


class NativeMediaEngine(Contract):
    """Orchestrator that aggregates media providers into a unified view.

    Takes a list of configured provider connections, normalizes all data
    into MediaItem/MediaLibrary/MediaActivity, and provides
    degradation when providers are absent or unreachable.
    """

    def __init__(self, connections: list[dict[str, Any]] | None = None) -> None:
        self._connections = connections or []
        self._adapters: dict[str, MediaAdapter] = {}
        self._build_adapters()

    def _build_adapters(self) -> None:
        for conn in self._connections:
            name = conn.get("name", conn.get("type", "unknown"))
            adapter = build_adapter(conn)
            if adapter is not None:
                self._adapters[name] = adapter

    def status(self) -> Result:
        """Aggregate status across all configured providers."""
        provider_statuses: list[dict[str, Any]] = []
        warnings: list[str] = []

        for name, adapter in self._adapters.items():
            r = adapter.status()
            provider_statuses.append(
                {
                    "name": name,
                    "provider": adapter.provider_name,
                    "ok": r.ok,
                    "status": r.status,
                    "data": r.data,
                }
            )
            if not r.ok:
                warnings.extend(r.warnings)

        configured_types = {c.get("type") for c in self._connections}
        for ct in configured_types:
            if ct not in _ADAPTERS:
                warnings.append(f"unknown provider type: {ct}")

        healthy = sum(1 for ps in provider_statuses if ps["ok"])
        total = len(provider_statuses)

        overall = Status.HEALTHY.value
        if total == 0:
            overall = Status.NOT_CONFIGURED.value
        elif healthy == 0:
            overall = Status.UNAVAILABLE.value
        elif healthy < total:
            overall = Status.NEEDS_ATTENTION.value

        return ok(
            overall,
            data={
                "providers": provider_statuses,
                "summary": {
                    "total": total,
                    "healthy": healthy,
                    "unavailable": total - healthy,
                },
            },
            warnings=warnings,
        )

    def library(self) -> Result:
        """Aggregate libraries from all providers."""
        all_libs: list[dict[str, Any]] = []
        warnings: list[str] = []

        for adapter in self._adapters.values():
            r = adapter.libraries()
            if r.ok and r.data:
                all_libs.extend(r.data.get("libraries", []))
            else:
                warnings.extend(r.warnings)

        return ok(
            Status.HEALTHY.value
            if all_libs or not self._adapters
            else Status.NEEDS_ATTENTION.value,
            data={"libraries": all_libs, "count": len(all_libs)},
            warnings=warnings,
        )

    def recent(self, limit: int = 20) -> Result:
        """Aggregate recently added items from all providers."""
        all_items: list[dict[str, Any]] = []
        warnings: list[str] = []

        for adapter in self._adapters.values():
            r = adapter.recent(limit=limit)
            if r.ok and r.data:
                all_items.extend(r.data.get("items", []))
            else:
                warnings.extend(r.warnings)

        all_items.sort(key=lambda x: x.get("added_at") or "", reverse=True)
        return ok(
            Status.HEALTHY.value,
            data={"items": all_items[:limit], "count": min(len(all_items), limit)},
            warnings=warnings,
        )

    def activity(self) -> Result:
        """Aggregate activity/queue from all providers."""
        all_activities: list[dict[str, Any]] = []
        warnings: list[str] = []

        for adapter in self._adapters.values():
            r = adapter.activity()
            if r.ok and r.data:
                all_activities.extend(r.data.get("activities", []))
            else:
                warnings.extend(r.warnings)

        return ok(
            Status.HEALTHY.value,
            data={"activities": all_activities, "count": len(all_activities)},
            warnings=warnings,
        )

    def search(self, query: str) -> Result:
        """Search across all providers."""
        all_items: list[dict[str, Any]] = []
        warnings: list[str] = []

        for adapter in self._adapters.values():
            r = adapter.search(query)
            if r.ok and r.data:
                all_items.extend(r.data.get("items", []))
            else:
                warnings.extend(r.warnings)

        return ok(
            Status.HEALTHY.value,
            data={"items": all_items, "count": len(all_items), "query": query},
            warnings=warnings,
        )

    def item(self, item_id: str) -> Result:
        """Fetch a single item by id from the appropriate provider."""
        for adapter in self._adapters.values():
            if item_id.startswith(f"{adapter.provider_name}:"):
                return adapter.item(item_id)

        return fail(
            Status.NOT_CONFIGURED.value,
            warnings=[f"no provider found for item id '{item_id}'"],
        )
