#!/usr/bin/env python3
"""Static floor check for the Direction 1 mockups.

This is not a browser and not a substitute for one: it cannot measure
layout, tap targets in pixels, or reflow at 390px. What it can do is check
the things a static file either gets right or gets wrong by construction:
text contrast of every declared colour pair, heading structure, the skip
link, the visible-focus rule, the reduced-motion rule, presence of the
MOCKUP label, status words, absence of any external network reference,
and absence of any real hostname.

    python3 docs/vnext/visuals/direction-1/check_floors.py

Exits non-zero on the first failed check. Add it to CI only if the
direction is adopted; today it is a mockup artefact.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATES = sorted(p for p in HERE.glob("*.html") if p.name != "index.html")
ALL_PAGES = STATES + [HERE / "index.html"]

FAILURES: list[str] = []


def check(ok: bool, message: str) -> None:
    if not ok:
        FAILURES.append(message)


# --------------------------------------------------------------------------
# colour
# --------------------------------------------------------------------------

def _srgb(value: str) -> tuple[float, float, float]:
    h = value.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def luminance(value: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _srgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    hi, lo = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


PALETTE = {
    "ink": "#0C1A1E",
    "hull": "#13262B",
    "panel": "#1A3238",
    "raised": "#24444B",
    "line": "#557F86",
    "foam": "#EAF4F1",
    "mist": "#BFD6D2",
    "sea": "#6FD8C2",
    "amber": "#FFC773",
    "slate": "#A9BEE0",
    "lilac": "#CDBDF2",
    "focus": "#FFD166",
    "deep": "#07201C",
}

# (foreground, background, minimum ratio, what it is)
CONTRAST_PAIRS = [
    ("foam", "ink", 4.5, "body text on canvas"),
    ("foam", "hull", 4.5, "body text on band and legend"),
    ("foam", "panel", 4.5, "body text on card"),
    ("foam", "raised", 4.5, "body text on card under prefers-contrast: more"),
    ("mist", "ink", 4.5, "lede and secondary text on canvas"),
    ("mist", "hull", 4.5, "secondary text on band"),
    ("mist", "panel", 4.5, "secondary text on card"),
    ("mist", "raised", 4.5, "secondary text on card under prefers-contrast: more"),
    ("sea", "ink", 4.5, "link text on canvas"),
    ("sea", "panel", 4.5, "quiet button border and text on card"),
    ("sea", "hull", 4.5, "healthy status word on its pill"),
    ("amber", "ink", 4.5, "needs-attention heading on canvas"),
    ("amber", "hull", 4.5, "needs-attention word on its pill"),
    ("amber", "panel", 4.5, "needs-attention word and card edge"),
    ("slate", "panel", 4.5, "stale word on its pill"),
    ("slate", "hull", 4.5, "stale word against band surface"),
    ("lilac", "panel", 4.5, "unknown word on its pill"),
    ("lilac", "hull", 4.5, "unknown word against band surface"),
    ("deep", "sea", 4.5, "primary button label"),
    ("deep", "amber", 4.5, "MOCKUP badge text"),
    ("focus", "ink", 3.0, "focus ring against canvas"),
    ("focus", "panel", 3.0, "focus ring against card"),
    ("focus", "hull", 3.0, "focus ring against band"),
    ("line", "panel", 3.0, "card border against card, and between bands"),
    ("line", "hull", 3.0, "band border against band"),
]


def check_contrast() -> None:
    for fg, bg, minimum, what in CONTRAST_PAIRS:
        ratio = contrast(PALETTE[fg], PALETTE[bg])
        check(
            ratio >= minimum,
            f"contrast {what}: {fg} on {bg} is {ratio:.2f}:1, needs {minimum}:1",
        )


# --------------------------------------------------------------------------
# markup
# --------------------------------------------------------------------------

class Scan(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headings: list[tuple[int, str]] = []
        self.anchors: list[tuple[str, dict]] = []
        self.has_mockup_label = False
        self.scripts = 0
        self.external_refs: list[str] = []
        self.lang = ""
        self.has_viewport = False
        self.status_pills: list[str] = []
        self._pill_depth = 0
        self._pill_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        classes = set(a.get("class", "").split())
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append((int(tag[1]), a.get("id", "")))
        if tag == "html":
            self.lang = a.get("lang", "")
        if tag == "meta" and a.get("name") == "viewport":
            self.has_viewport = True
        if tag == "a":
            self.anchors.append((a.get("class", ""), a))
        if "mockup" in classes:
            self.has_mockup_label = True
        if tag == "script":
            self.scripts += 1
        for key in ("src", "href"):
            ref = a.get(key, "")
            if ref.startswith(("http://", "https://", "//")):
                self.external_refs.append(ref)
        if tag == "link" and a.get("rel") in ("stylesheet", "preload", "prefetch"):
            self.external_refs.append(a.get("href", "<link rel=stylesheet>"))
        # A status pill is any element with a `pill` class. Collect the text
        # inside it, whatever tag it is, so "colour with no word" is caught.
        if "pill" in classes and "legend" not in classes and self._pill_depth == 0:
            self._pill_depth = 1
            self._pill_text = []
        elif self._pill_depth:
            self._pill_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._pill_depth:
            self._pill_depth -= 1
            if self._pill_depth == 0:
                self.status_pills.append("".join(self._pill_text).strip())

    def handle_data(self, data: str) -> None:
        if self._pill_depth:
            self._pill_text.append(data)


def scan(path: Path) -> tuple[str, Scan]:
    text = path.read_text(encoding="utf-8")
    s = Scan()
    s.feed(text)
    s.close()
    return text, s


def check_headings(name: str, s: Scan) -> None:
    check(len([h for h in s.headings if h[0] == 1]) == 1, f"{name}: needs exactly one h1")
    levels = [lvl for lvl, _ in s.headings]
    check(bool(levels) and levels[0] == 1, f"{name}: first heading must be the h1")
    for previous, current in zip(levels, levels[1:], strict=False):
        check(
            current <= previous + 1,
            f"{name}: heading level jumps from h{previous} to h{current}",
        )


def check_skip_link(name: str, text: str) -> None:
    body_at = text.find("<body")
    skip_at = text.find('class="skip"')
    check(
        0 < skip_at and skip_at < body_at + 200,
        f"{name}: skip link must be the first focusable element after <body>",
    )


def check_focus_and_motion(name: str, text: str) -> None:
    check(":focus-visible" in text, f"{name}: no :focus-visible rule")
    check(
        re.search(r"outline:3px solid var\(--focus\)", text) is not None,
        f"{name}: focus rule does not set a visible outline",
    )
    check(
        "outline:none" not in text and "outline: 0" not in text,
        f"{name}: an outline is removed somewhere",
    )
    compact = text.replace(" ", "")
    check(
        "(prefers-reduced-motion:reduce)" in compact,
        f"{name}: no prefers-reduced-motion rule",
    )


def check_offline(name: str, text: str, s: Scan) -> None:
    for ref in s.external_refs:
        check(
            ".invalid" in ref,
            f"{name}: external reference {ref!r} is not an unresolvable .invalid address",
        )
    for pattern, label in (
        (r"@import", "@import"),
        (r"url\(\s*['\"]?https?:", "css url(http)"),
        (r"<script\b", "a <script> tag"),
        (r"<link[^>]+stylesheet", "an external stylesheet"),
    ):
        check(re.search(pattern, text, re.I) is None, f"{name}: {label} is not allowed")
    check(s.scripts == 0, f"{name}: no JavaScript is expected in this direction")


def check_status_words(name: str, s: Scan) -> None:
    words = ("Healthy", "Needs attention", "Stale", "Unknown", "Not set up", "Nothing waiting")
    for pill in s.status_pills:
        check(
            any(w in pill for w in words),
            f"{name}: status pill {pill!r} has no status word beside the colour",
        )


# Anchor classes the stylesheet is allowed to use, and the selector whose
# rule must carry the 44px minimum height.
ALLOWED_ANCHOR_CLASSES = {
    "skip",
    "btn",
    "btn--primary",
    "btn--quiet",
    "is-current",
    "state__link",
    "footlink",
}
TAP_RULES = (".skip", ".btn", ".landmarks a", ".state__link", ".footlink")


def check_tap_targets(name: str, text: str, s: Scan) -> None:
    """Every anchor must use a class whose stylesheet rule sets a 44px
    minimum height. The measured pixel size still needs a browser."""
    for _, attrs in s.anchors:
        tokens = set(attrs.get("class", "").split())
        stray = tokens - ALLOWED_ANCHOR_CLASSES
        check(
            not stray,
            f"{name}: anchor {attrs!r} uses {sorted(stray)}, which has no 44px rule",
        )
    css = text.split("</style>")[0]
    for selector in TAP_RULES:
        if selector not in css:
            continue  # the page does not use this kind of control
        rule = css.split(selector, 1)[1].split("}", 1)[0]
        check(
            "min-height:var(--tap)" in rule,
            f"{name}: rule for {selector} does not set min-height:var(--tap)",
        )
    check(
        "--tap:44px" in css,
        f"{name}: --tap must be 44px (the accessibility floor)",
    )


def check_no_wide_geometry(name: str, text: str) -> None:
    """Proxy for no horizontal scroll at 390px: no element in the
    stylesheet may demand a fixed width wider than a phone. Media query
    conditions and `max-width` are not element widths."""
    css = text.split("</style>")[0]
    css = re.sub(r"@media[^{]*\{", "@media{", css)
    offenders = [
        m.group(0)
        for m in re.finditer(r"(?<![a-z-])(?:min-)?width:\s*(\d{3,})px", css)
        if int(m.group(1)) > 390
    ]
    # index.html frames the desktop state on purpose, inside its own
    # overflow-x container; that is the only allowed wide value.
    if name == "index.html":
        offenders = [o for o in offenders if "1440px" not in o]
    check(not offenders, f"{name}: fixed element width over 390px: {offenders}")


def main() -> int:
    check(len(STATES) == 4, f"expected four state pages, found {len(STATES)}")
    for path in ALL_PAGES:
        text, s = scan(path)
        name = path.name
        check(s.lang == "en", f"{name}: html element needs lang=\"en\"")
        check(s.has_viewport, f"{name}: needs a viewport meta tag")
        check(s.has_mockup_label, f"{name}: needs a visible MOCKUP label")
        check_headings(name, s)
        check_skip_link(name, text)
        check_focus_and_motion(name, text)
        check_offline(name, text, s)
        check_status_words(name, s)
        check_tap_targets(name, text, s)
        check_no_wide_geometry(name, text)

    check_contrast()

    if FAILURES:
        print(f"FAIL - {len(FAILURES)} problem(s):")
        for f in FAILURES:
            print(f"  - {f}")
        return 1

    print(
        f"OK - {len(ALL_PAGES)} pages, "
        f"{len(CONTRAST_PAIRS)} contrast pairs at or above their minimum, "
        "headings/skip link/focus/reduced-motion/MOCKUP labels/status words/offline "
        "all present. Layout, tap-target pixels and 390px reflow still need a "
        "browser."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
