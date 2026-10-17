"""One way to open a URL in this package, and it only opens http(s).

``urllib.request.urlopen`` will happily open ``file://``, ``ftp://`` or
``data:`` — the scheme is what decides what a URL *is*. Every outbound call
here is built from an operator-supplied or config-supplied base URL, so a
base URL that is not pinned to http(s) turns a health probe into a local
file read (or worse, posts one somewhere it should never go).

``http_urlopen`` is that pin, in one place, so each call site does not have
to remember it. It delegates to ``urllib.request.urlopen`` at call time —
tests inject stubs by patching that attribute, and this keeps working.
"""

from __future__ import annotations

import urllib.request
from typing import Any
from urllib.parse import urlsplit

#: The only schemes this package will open.
HTTP_SCHEMES = ("http", "https")


def require_http_url(url: str) -> str:
    """Return ``url`` unchanged when it is an absolute http(s) URL.

    Raises ``ValueError`` for anything else — including a scheme that is
    merely well-formed but not one we are willing to speak to.
    """
    try:
        scheme = urlsplit(url).scheme.lower()
    except ValueError as exc:  # e.g. a malformed IPv6 literal
        raise ValueError(f"malformed URL {url!r}: {exc}") from exc
    if scheme not in HTTP_SCHEMES:
        raise ValueError(f"only http:// and https:// URLs can be opened, not {url!r}")
    return url


def http_urlopen(url_or_request: Any, *, timeout: float | None = None) -> Any:
    """``urllib.request.urlopen``, restricted to http(s) URLs."""
    url = getattr(url_or_request, "full_url", url_or_request)
    require_http_url(str(url))
    # The scheme is checked immediately above; this is the single place the
    # check lives, which is exactly what B310 asks for and cannot be
    # satisfied any closer to the call.
    return urllib.request.urlopen(url_or_request, timeout=timeout)  # nosec B310  # scheme pinned by require_http_url above
