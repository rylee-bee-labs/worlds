"""Card field mapping: a strict JSONPath subset plus value formats (C1 fields, C2 values).

Two rules shape this module:

* **No code execution.** Paths are read with a hand-written tokenizer, not a
  regex, an ``eval``, or a filter/script engine. Anything outside the subset
  below is a :class:`MappingError`, not a silently empty result.
* **Missing is not 0.** A key or index that is not there yields ``[]``, and a
  value that cannot be read formats as ``"unknown"``. Nothing is ever invented.

Supported path grammar (nothing else parses)::

    path    := "$" step*
    step    := "." name | "[" index "]" | "[*]"
    name    := [A-Za-z_][A-Za-z0-9_-]*      ; a leading "__" is refused
    index   := digits | "-1"                 ; "-1" is the last element; no other negatives

No filters, slices, recursion, quoted keys, scripts or unions.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Any, Literal

__all__ = ["MappingError", "Segment", "parse_path", "extract", "format_value", "FORMATS"]

UNKNOWN = "unknown"

Segment = "Name | Index | Wildcard"


class MappingError(ValueError):
    """A field path or format request is not something this module will run."""


@dataclass(frozen=True)
class _Name:
    name: str


@dataclass(frozen=True)
class _Index:
    index: int


@dataclass(frozen=True)
class _Wildcard:
    pass


# --------------------------------------------------------------------------
# tokenizer
# --------------------------------------------------------------------------

_NAME_START = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_NAME_BODY = _NAME_START | frozenset("0123456789-")
_DIGITS = frozenset("0123456789")


def parse_path(path: str) -> tuple[Any, ...]:
    """Tokenize ``path`` into steps. Raises MappingError on anything outside the subset."""
    if not isinstance(path, str) or not path:
        raise MappingError("path must be a non-empty string starting with '$'")
    if path[0] != "$":
        raise MappingError(f"path must start with '$': {path!r}")

    steps: list[Any] = []
    i = 1
    n = len(path)
    while i < n:
        char = path[i]
        if char == ".":
            i = _read_name(path, i, steps)
        elif char == "[":
            i = _read_bracket(path, i, steps)
        else:
            raise MappingError(f"unexpected {char!r} at offset {i} in path {path!r}")
    return tuple(steps)


def _read_name(path: str, i: int, steps: list[Any]) -> int:
    """Read ``.name`` (i points at the dot) and append a step. Returns the next offset."""
    start = i + 1
    j = start
    while j < len(path) and path[j] in _NAME_BODY:
        j += 1
    if j == start:
        raise MappingError(f"empty field name at offset {i} in path {path!r}")
    name = path[start:j]
    if name[0] not in _NAME_START:
        raise MappingError(f"field name {name!r} must start with a letter or underscore")
    if name.startswith("__"):
        raise MappingError(f"field name {name!r} is private and is not addressable")
    steps.append(_Name(name))
    return j


def _read_bracket(path: str, i: int, steps: list[Any]) -> int:
    """Read ``[n]`` or ``[*]`` (i points at the bracket) and append a step."""
    close = path.find("]", i + 1)
    if close == -1:
        raise MappingError(f"unclosed '[' at offset {i} in path {path!r}")
    inner = path[i + 1 : close]
    if inner == "*":
        steps.append(_Wildcard())
    elif inner.isdigit() or inner == "-1":
        # [-1] is the last element (C1.3). No other negative index, and no slice.
        steps.append(_Index(int(inner)))
    elif inner[:1] == "-" and inner[1:].isdigit():
        raise MappingError(f"only [-1] is allowed as a negative index, not [{inner}] in path {path!r}")
    else:
        raise MappingError(f"unsupported bracket {inner!r} in path {path!r}")
    return close + 1


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Resolved:
    """Result of reading a path: the values, and whether the path actually exists.

    ``found`` is False when a step did not apply anywhere (missing key, bad or
    out-of-range index, wildcard over a non-list) and nothing was produced. A
    wildcard over a list that exists but is empty is ``found=True`` with no values.
    """

    values: list[Any]
    found: bool


def resolve(doc: Any, path: str) -> Resolved:
    current = [doc]
    skipped = False
    for step in parse_path(path):
        nxt: list[Any] = []
        for node in current:
            if isinstance(step, _Name):
                if isinstance(node, dict) and step.name in node:
                    nxt.append(node[step.name])
                else:
                    skipped = True
            elif isinstance(step, _Wildcard):
                if isinstance(node, (list, tuple)):
                    nxt.extend(node)
                else:
                    skipped = True
            else:
                if isinstance(node, (list, tuple)) and (step.index == -1 and len(node) > 0 or 0 <= step.index < len(node)):
                    nxt.append(node[step.index])
                else:
                    skipped = True
        current = nxt
        if not current:
            return Resolved([], found=not skipped)
    return Resolved(current, found=True)


def count_of(res: Resolved, path: str) -> int | None:
    """``format: count`` (C1.3): the length of the list at the path.

    A wildcard path counts what it matched (``$.items[*]``); any other path must resolve to one list.
    A path that is not there, or a value that is not a list, is None (unknown, never 0); an existing
    empty list is a real 0.
    """
    if not res.found:
        return None
    if "[*]" in path:
        return len(res.values)
    if len(res.values) == 1 and isinstance(res.values[0], (list, tuple)):
        return len(res.values[0])
    return None


def extract(doc: Any, path: str) -> list[Any]:
    """Every matching value in document order; ``[]`` when nothing matches (never 0, never None)."""
    return resolve(doc, path).values


# --------------------------------------------------------------------------
# formats
# --------------------------------------------------------------------------

FORMATS = ("number", "percent", "bytes", "duration", "relative_time", "text", "count")
_IEC_UNITS = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB")
_MAX_DECIMALS = 6
_JUST_NOW_S = 60


def format_value(
    value: Any,
    fmt: Literal["number", "percent", "bytes", "duration", "relative_time", "text", "count"],
    unit: str | None,
    *,
    now: dt.datetime | None = None,
) -> str:
    """Render one mapped value as the text a card shows.

    ``unit`` is appended for ``number`` only; the other formats carry their own
    unit (``%``, ``KiB``, ``h/m/s``). Anything missing or unreadable is
    ``"unknown"`` — never ``0``.
    """
    if fmt not in FORMATS:
        raise MappingError(f"unsupported format {fmt!r}")

    if fmt == "text":
        return _format_text(value)
    if fmt == "relative_time":
        return _format_relative(value, now)

    number = _as_number(value)
    if number is None:
        return UNKNOWN
    if fmt == "number":
        return _with_unit(_format_number(number), unit)
    if fmt == "percent":
        return f"{_format_number(number * 100)}%"  # the input is a fraction: 0.256 -> 25.6%
    if fmt == "bytes":
        return _format_bytes(number)
    return _format_duration(number)


def _with_unit(text: str, unit: str | None) -> str:
    unit = unit.strip() if isinstance(unit, str) else ""
    return f"{text} {unit}" if unit else text


def _as_number(value: Any) -> float | None:
    """A finite number, or None. ``bool`` is not a number (missing is not 0)."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def _format_number(number: float, decimals: int | None = None) -> str:
    """Thousands-separated decimal text: 1234.5 -> ``1,234.5``, 1234 -> ``1,234``."""
    rounded = round(number, _MAX_DECIMALS if decimals is None else decimals)
    if rounded == int(rounded) and abs(rounded) < 1e16:
        return f"{int(rounded):,}"
    text = f"{rounded:,}"
    if decimals is not None:
        text = text.rstrip("0").rstrip(".") if "." in text else text
    return text


def _format_bytes(number: float) -> str:
    """IEC size: 1536 -> ``1.5 KiB``, 0 -> ``0 B``."""
    negative = number < 0
    size = abs(number)
    power = 0
    while size >= 1024 and power < len(_IEC_UNITS) - 1:
        size /= 1024
        power += 1
    sign = "-" if negative else ""
    if power == 0:
        return f"{sign}{int(size)} {_IEC_UNITS[0]}"
    return f"{sign}{_format_number(size, decimals=1)} {_IEC_UNITS[power]}"


def _format_duration(seconds: float) -> str:
    """Elapsed seconds: 3725 -> ``1h 2m``, 45 -> ``45s``."""
    if seconds < 0:
        return UNKNOWN  # a duration that has not happened is not a value we can show
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    if minutes:
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"
    return f"{secs}s"


def _format_text(value: Any) -> str:
    if value is None:
        return UNKNOWN
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        number = _as_number(value)
        return UNKNOWN if number is None else _format_number(number)
    return UNKNOWN  # a list or object is not a stat's text; the view renders it


def _parse_timestamp(value: Any) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        moment = value
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            moment = dt.datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if moment.tzinfo is None:
        return moment.replace(tzinfo=dt.timezone.utc)
    return moment


def _format_relative(value: Any, now: dt.datetime | None) -> str:
    moment = _parse_timestamp(value)
    if moment is None:
        return UNKNOWN
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)

    delta = (now - moment).total_seconds()
    future = delta < 0
    seconds = abs(delta)
    if seconds < _JUST_NOW_S:
        return "just now"

    minutes = int(seconds // 60)
    hours = int(seconds // 3600)
    days = int(seconds // 86400)
    if minutes < 60:
        return _relate(future, minutes, "minute")
    if hours < 24:
        return _relate(future, hours, "hour")
    if days < 7:
        return _relate(future, days, "day")
    if days < 30:
        return _relate(future, days // 7, "week")
    if days < 365:
        return _relate(future, days // 30, "month")
    return _relate(future, days // 365, "year")


def _relate(future: bool, count: int, unit: str) -> str:
    plural = "" if count == 1 else "s"
    return f"in {count} {unit}{plural}" if future else f"{count} {unit}{plural} ago"
