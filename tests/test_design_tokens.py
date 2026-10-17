"""P1 T3: approved focus-ring design-truth correction (A11y §2.4).

Regression test added 2026-09-11 (UI-convergence session): the
original assertions here checked for the literal unresolved token
reference string "accent.primary" rather than a real color value —
i.e. this test was passing while `--pw-focus-ring` in the generated
CSS was invalid (`outline: 2px solid accent.primary, offset 2px`,
which browsers silently drop as invalid, since `accent.primary` is
not a CSS color and the shorthand doesn't take a comma or an
"offset" component). That left every keyboard focus indicator in the
app invisible despite this test showing green. `focus.ring` must be a
value the `outline` CSS shorthand actually accepts.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

_OUTLINE_SHORTHAND = re.compile(
    r"^2px solid (#[0-9A-Fa-f]{6}|#[0-9A-Fa-f]{3})$"
)


def test_focus_ring_matches_accessibility_contract():
    """Re-anchored 2026-09-20 to the names/values split (TOKEN-REANCHOR-BRIEF).

    Original intent preserved in full (2026-09-11 regression): the focus ring
    must resolve to a literal, valid CSS `outline` shorthand — width separate
    from offset forever, never an unresolved token reference, never folded
    together. Where the truth lives now:
      - STRUCTURE: design/tokens.json focus group (immutable 2px width,
        distinct offset token)
      - VALUES: design/themes/*.json accent/primary per theme
      - HIGH CONTRAST: docs/accessibility/ACCESSIBILITY_CONTRACT.md §2.4
        (teal comfortable / #FFFFFF high-contrast) until HC ships as a real
        theme pack, at which point this test must move that assertion there.
    """
    repo_root = Path(__file__).parent.parent
    tokens = json.loads((repo_root / "design" / "tokens.json").read_text())
    focus = tokens["focus"]

    width = focus["ring_width"]["_value"]
    assert width == "2px", f"ring_width must stay 2px, got {width!r}"
    assert focus["ring_width"].get("_immutable") is True, (
        "ring_width lost its _immutable flag — the 2026-09-11 class of bug "
        "returns the moment a theme can shrink the indicator to invisible"
    )
    assert "ring_offset" in focus and focus["ring_offset"]["_value"] == "2px", (
        "offset must remain a SEPARATE token, applied independently — folding "
        "it into the outline shorthand is what made browsers drop the rule"
    )

    # every theme pack (present AND future) must compose a valid literal ring
    themes = sorted((repo_root / "design" / "themes").glob("*.json"))
    assert themes, "no theme packs found to check"
    for tf in themes:
        theme = json.loads(tf.read_text())
        accent = theme["accent"]["primary"]
        composed = f"{width} solid {accent}"
        assert _OUTLINE_SHORTHAND.match(composed), (
            f"{tf.name}: focus ring resolves to invalid outline {composed!r}"
        )

    # comfortable = teal, and the ACTIVE production theme is station
    station = json.loads((repo_root / "design" / "themes" / "station.json").read_text())
    assert station["accent"]["primary"] == "#72b1b1", "station accent drifted from §2.4"

    # high contrast lives in the contract doc until an HC theme pack exists
    hc_doc = (repo_root / "docs" / "accessibility" / "ACCESSIBILITY_CONTRACT.md").read_text()
    assert "#FFFFFF" in hc_doc and "high-contrast" in hc_doc.lower(), (
        "§2.4 high-contrast white ring vanished from the accessibility "
        "contract — if this moved to a theme file, update this assertion's home"
    )

    # the served surface must still ship the resolved ring (no build-time
    # surprise). The interface is the front door (ui/src/fd, ADR-0008); its one
    # stylesheet carries the focus rule. The silent-drop class this guards is
    # unchanged: literal 2px width, the offset a SEPARATE declaration, never
    # folded into the shorthand.
    fd_css = (repo_root / "ui" / "src" / "fd" / "fd.css").read_text()
    assert "outline: 2px solid var(--focus)" in fd_css, (
        "the front door's focus ring no longer carries a literal 2px width in "
        "ui/src/fd/fd.css - the exact silent-drop failure this test was born from"
    )
    assert "outline-offset: 2px" in fd_css, (
        "outline-offset vanished as a separate declaration in ui/src/fd/fd.css - "
        "folding it back into the shorthand reintroduces the 2026-09-11 browser-drop bug"
    )

    # the focus token itself: teal (the station accent) in the dark default, and every
    # surface a focus ring can sit on keeps at least 3:1 against it (WCAG 1.4.11).
    def block(selector: str) -> dict[str, str]:
        m = re.search(re.escape(selector) + r"\s*\{(.*?)\}", fd_css, re.S)
        assert m, f"{selector} block not found in ui/src/fd/fd.css"
        return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})", m.group(1)))

    def luminance(hex_color: str) -> float:
        rgb = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    def contrast(a: str, b: str) -> float:
        hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    dark = block(":root")
    light = {**dark, **block(':root[data-theme="daylight"]')}
    assert dark["focus"].lower() == station["accent"]["primary"].lower(), (
        "the dark theme's --focus is no longer the teal station accent"
    )
    for name, theme in (("dark", dark), ("daylight", light)):
        for surface in ("void", "canvas", "hull", "panel", "elevated", "raised"):
            ratio = contrast(theme["focus"], theme[surface])
            assert ratio >= 3, f"{name}: focus ring on --{surface} is {ratio:.2f}:1, below 3:1"
