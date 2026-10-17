"""Query-value templates (C1.3): a closed set, rendered server-side, in query values only.

Tokens: ``{today}``, ``{today+Nd}``, ``{today-Nd}`` (N 0-366) as a UTC date, and ``{now}`` as a UTC
datetime. Nothing else is substituted, nothing nests, and a brace that is not one of these tokens is a
save-time error. Path, host and headers are never templated.
"""

from __future__ import annotations

import datetime as dt
import re

__all__ = ["check_query_value", "has_template", "render_query", "render_value"]

_TOKEN = re.compile(r"\{([^{}]*)\}")
_SHIFT = re.compile(r"^today([+-])(\d{1,3})d$")
_MAX_DAYS = 366


def _valid(token: str) -> bool:
    if token in ("today", "now"):
        return True
    m = _SHIFT.match(token)
    return bool(m) and int(m.group(2)) <= _MAX_DAYS


def check_query_value(value: str) -> str:
    """Raise ValueError unless every brace in ``value`` belongs to a known token."""
    for token in _TOKEN.findall(value):
        if not _valid(token):
            raise ValueError(f"unknown query template {{{token}}} (allowed: {{today}}, {{today+Nd}}, {{today-Nd}} with N 0-{_MAX_DAYS}, {{now}})")
    if "{" in _TOKEN.sub("", value) or "}" in _TOKEN.sub("", value):
        raise ValueError("unbalanced or nested braces in a query value")
    return value


def has_template(value: str) -> bool:
    """True when ``value`` contains a known template token (used to refuse them outside query values)."""
    return any(_valid(tok) for tok in _TOKEN.findall(value))


def render_value(value: str, now: dt.datetime | None = None) -> str:
    when = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)

    def sub(m: re.Match[str]) -> str:
        token = m.group(1)
        if token == "now":  # nosec B105  # a template placeholder name, not a credential
            return when.strftime("%Y-%m-%dT%H:%M:%SZ")
        if token == "today":  # nosec B105  # a template placeholder name, not a credential
            return when.date().isoformat()
        shift = _SHIFT.match(token)
        assert shift is not None  # check_query_value ran at save time; a bad token never renders
        days = int(shift.group(2)) * (1 if shift.group(1) == "+" else -1)
        return (when.date() + dt.timedelta(days=days)).isoformat()

    return _TOKEN.sub(sub, value)


def render_query(query: dict[str, str], now: dt.datetime | None = None) -> dict[str, str]:
    return {k: render_value(v, now) for k, v in query.items()}
