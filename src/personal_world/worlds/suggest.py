"""Pure helpers for the Connect workshop: scrub a response sample and suggest fields to map.

Everything here works on parsed data and returns data; nothing sends or stores anything.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Iterable

from .mapping import MappingError, parse_path, resolve

REDACTED = "[redacted]"
SAMPLE_BYTES = 16 * 1024
MAX_SUGGESTIONS = 50
MAX_DEPTH = 6
_SECRET_KEY = re.compile(r"(pass(word|wd)?|secret|token|api[-_]?key|apikey|authorization|auth|cookie|session|credential|private|signature|bearer|jwt)", re.I)
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_SECRETISH_VALUE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9+/=_\-.]{24,}$")      # a long unbroken token-looking string
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{6,}")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


def secretish_key(key: str) -> bool:
    return bool(_SECRET_KEY.search(key))


def scrub_text(text: str, secret_values: Iterable[str] = ()) -> str:
    """Remove every known secret value and bearer/basic credential from free text (whitespace kept)."""
    for value in secret_values or ():
        if isinstance(value, str) and len(value) >= 4:
            text = text.replace(value, REDACTED)
    return _BEARER.sub(REDACTED, text)


def redact_sample(node: Any, secret_values: Iterable[str] = (), _depth: int = 0) -> Any:
    """A copy of parsed JSON safe to show: values under secret-looking keys, every known secret value, bearer
    strings and long token-looking strings are replaced. Depth and breadth are capped."""
    secrets = tuple(v for v in (secret_values or ()) if isinstance(v, str) and len(v) >= 4)
    if _depth > 12:
        return "[too deep]"
    if isinstance(node, dict):
        out = {}
        for i, (k, v) in enumerate(node.items()):
            if i >= 200:
                out["…"] = f"{len(node) - 200} more keys"
                break
            key = str(k)[:80]
            out[key] = REDACTED if secretish_key(key) else redact_sample(v, secrets, _depth + 1)
        return out
    if isinstance(node, list):
        items = [redact_sample(v, secrets, _depth + 1) for v in node[:100]]
        if len(node) > 100:
            items.append(f"… {len(node) - 100} more")
        return items
    if isinstance(node, str):
        if any(s in node for s in secrets) or _BEARER.search(node) or _SECRETISH_VALUE.match(node):
            return REDACTED
        return node[:500]
    return node


def _format_for(key: str, value: Any) -> str:
    k = key.lower()
    if isinstance(value, bool):
        return "text"
    if isinstance(value, (int, float)):
        if re.search(r"(percent|pct|ratio|load|usage|util|cpu)", k) and 0 <= value <= 1:
            return "percent"
        if re.search(r"(bytes|size|disk|memory|mem|ram|space)", k):
            return "bytes"
        if re.search(r"(uptime|duration|elapsed|seconds|secs|age)", k):
            return "duration"
        return "number"
    if isinstance(value, str) and _ISO.match(value):
        try:
            dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            return "relative_time"
        except ValueError:
            return "text"
    return "text"


def _label(key: str) -> str:
    words = re.sub(r"[_-]+", " ", key).strip()
    return (words[:1].upper() + words[1:])[:60] or "Value"


def suggest_fields(doc: Any, limit: int = MAX_SUGGESTIONS, secret_values: Iterable[str] = ()) -> list[dict[str, Any]]:
    """One suggestion per scalar leaf, as a JSONPath-subset path with a label, a format guess and a sample.

    Keys that are not plain names, secret-looking keys and secret-looking values are skipped, depth and count
    are capped, and every suggested path is checked against the real mapping engine before it is offered.
    """
    out: list[dict[str, Any]] = []
    secrets = tuple(secret_values or ())

    def leaf(path: str, key: str, value: Any, many: bool, parent: str = "") -> None:
        if len(out) >= limit or value is None:
            return
        if isinstance(value, str) and (_SECRETISH_VALUE.match(value) or _BEARER.search(value) or any(s and s in value for s in secrets)):
            return
        if not many and path == "$":
            return
        try:
            parse_path(path)
            found = resolve(doc, path)
        except MappingError:
            return
        if not found.found:
            return
        sample = value if not isinstance(value, str) else value[:80]
        out.append({"path": path, "label": _label(key), "format": _format_for(f"{parent} {key}", value), "sample": sample})

    def walk(node: Any, path: str, key: str, depth: int, many: bool, parent: str = "") -> None:
        if len(out) >= limit or depth > MAX_DEPTH:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if not isinstance(k, str) or not _NAME.match(k) or k.startswith("__") or secretish_key(k):
                    continue
                walk(v, f"{path}.{k}", k, depth + 1, many, key if key != "value" else "")
        elif isinstance(node, list):
            if node:
                walk(node[0], f"{path}[*]", key, depth + 1, True, parent)
        elif isinstance(node, (str, int, float, bool)):
            leaf(path, key, node, many, parent)

    walk(doc, "$", "value", 0, False)
    return out
