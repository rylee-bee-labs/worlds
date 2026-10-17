"""Native Notifications provider: tiny dispatcher for outbound notifications.

Conceptually:
native_notifications
  ├── generic webhook
  ├── SMTP
  ├── ntfy HTTP adapter
  └── future providers

No notification server required. Sends via outbound HTTP/SMTP.
"""

import json
import os
import urllib.error
import urllib.request

from ..envelope import Result, fail, ok
from ..status import Status
from ..url_safety import http_urlopen
from .registry import StatusContract


class WebhookAdapter:
    """Send notifications via generic webhook."""

    def __init__(self, url, headers=None):
        self.url = url
        self.headers = headers or {}

    def send(self, title, body, urgency="normal", **kwargs) -> bool:
        try:
            data = json.dumps({"title": title, "body": body, "urgency": urgency}).encode()
            headers = {"Content-Type": "application/json", **self.headers}
            req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
            with http_urlopen(req, timeout=15) as resp:
                return resp.status in (200, 201, 202, 204)
        except Exception:
            return False


class NtfyAdapter:
    """Send notifications via ntfy.sh HTTP API."""

    def __init__(self, topic, server="https://ntfy.sh", token=None):
        self.topic = topic
        self.server = server.rstrip("/")
        self.token = token

    def send(self, title, body, urgency="default", **kwargs) -> bool:
        try:
            url = f"{self.server}/{self.topic}"
            data = json.dumps({"topic": self.topic, "title": title, "message": body, "priority": urgency}).encode()
            headers = {"Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with http_urlopen(req, timeout=15) as resp:
                return resp.status in (200, 201, 202)
        except Exception:
            return False


class NativeNotificationsProvider(StatusContract):
    """Native notifications capability with webhook/ntfy adapters."""

    def __init__(self, config=None):
        self._adapters = []
        self._config = config or {}
        self._load_adapters()

    def _load_adapters(self):
        """Load configured notification targets."""
        targets = self._config.get("targets", [])
        for t in targets:
            ttype = t.get("type")
            if ttype == "webhook" and t.get("url"):
                self._adapters.append(WebhookAdapter(t["url"], t.get("headers")))
            elif ttype == "ntfy":
                topic = t.get("topic", os.environ.get("NTFY_TOPIC", ""))
                server = t.get("server", "https://ntfy.sh")
                token = os.environ.get(t.get("token_env", ""), "")
                if topic:
                    self._adapters.append(NtfyAdapter(topic, server, token))

    def observe(self) -> Result:
        """Report notification capability status."""
        if not self._adapters:
            return ok(Status.NOT_CONFIGURED.value, data={
                "targets": [],
                "message": "no notification targets configured",
                "provider": "native_notifications",
            })
        return ok(Status.HEALTHY.value, data={
            "targets": [type(a).__name__ for a in self._adapters],
            "provider": "native_notifications",
        })

    def send(self, title, body, urgency="normal", **kwargs) -> Result:
        """Send a notification to all configured targets."""
        if not self._adapters:
            return fail(Status.NOT_CONFIGURED.value, warnings=["no notification targets configured"])
        results = []
        for adapter in self._adapters:
            success = adapter.send(title, body, urgency, **kwargs)
            results.append({"adapter": type(adapter).__name__.lower().replace("adapter", ""), "success": success})
        any_success = any(r["success"] for r in results)
        status = Status.HEALTHY.value if any_success else Status.UNAVAILABLE.value
        return ok(status, data={"results": results, "sent": any_success})

    def health(self) -> bool:
        return len(self._adapters) > 0
