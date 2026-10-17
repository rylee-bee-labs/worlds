"""Documentation validation: low-noise checks that keep the docs index
honest. Internal Markdown links must resolve, and the canonical
navigation files must exist. External links are deliberately NOT
checked — other people's websites are not this repository's CI
concern.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

CANONICAL_FILES = (
    "README.md",
    "CHANGELOG.md",
    "ROADMAP.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "AGENTS.md",
    "docs/INDEX.md",
    "docs/ARCHITECTURE.md",
    "docs/NATIVE-BASELINE-AND-ENRICHMENT.md",
    "docs/OPERATIONS.md",
    "docs/PROVIDERS.md",
    "design/tokens.json",
    "design/COMPANION_INTEGRATION.md",
)

# Build output and test-run leftovers are not documentation: without these
# the number of link checks depended on what a working tree happened to hold.
EXCLUDED_DIRS = (
    ".venv",
    "node_modules",
    ".git",
    "data",
    "config.local",
    ".pytest_cache",
    "test-results",
    "ui/dist/",
)


def _markdown_files() -> list[Path]:
    out = []
    for f in REPO_ROOT.rglob("*.md"):
        s = str(f)
        if any(d in s for d in EXCLUDED_DIRS):
            continue
        out.append(f)
    return out


def test_canonical_files_exist():
    for rel in CANONICAL_FILES:
        assert (REPO_ROOT / rel).exists(), f"canonical file missing: {rel}"


_LINK = re.compile(r"\]\(([^)\s]*?)(#[^)\s]*)?\)")
_FENCE = re.compile(r"^\s*(```|~~~)")


def _anchors(md: Path) -> set[str]:
    """The fragment ids a markdown file offers: GitHub-style heading slugs
    (with -1, -2 suffixes for repeats) plus explicit id/name attributes."""
    text = md.read_text(errors="ignore")
    found: set[str] = set()
    seen: dict[str, int] = {}
    in_fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if not m:
            continue
        title = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1))
        title = re.sub(r"[`*_~]", "", title).lower()
        slug = re.sub(r"[^\w\- ]", "", title).strip().replace(" ", "-")
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        found.add(slug if n == 0 else f"{slug}-{n}")
    found.update(re.findall(r"""(?:id|name)=["']([^"']+)["']""", text))
    return found


@pytest.mark.parametrize("md", _markdown_files(), ids=lambda p: str(p))
def test_internal_links_resolve(md: Path):
    text = md.read_text(errors="ignore")
    missing = []
    bad_anchor = []
    for m in _LINK.finditer(text):
        target = m.group(1).strip()
        fragment = (m.group(2) or "")[1:]
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        if target:
            resolved = (md.parent / target).resolve()
            if not resolved.exists():
                missing.append(target)
                continue
        else:
            resolved = md
        if fragment and resolved.is_file() and resolved.suffix == ".md":
            if fragment.lower() not in {a.lower() for a in _anchors(resolved)}:
                bad_anchor.append(f"{target}#{fragment}")
    assert not missing, f"{md}: broken internal links: {missing}"
    assert not bad_anchor, f"{md}: links to headings that do not exist: {bad_anchor}"

# ---------------------------------------------------------------------------
# Accessibility contract discoverability (truth-repair epoch 2026-09-07)
# ---------------------------------------------------------------------------

ACCESSIBILITY_CONTRACT = "docs/accessibility/ACCESSIBILITY_CONTRACT.md"
ACCESSIBILITY_SIBLINGS = (
    "docs/accessibility/SCREEN_READER_WALKTHROUGH.md",
    "docs/accessibility/RESPONSIVE_RULES.md",
    "docs/accessibility/PREFERENCES_SCHEMA.json",
)
# The old canonical home was design/handoff/ (an Archived directory).
# The move is a discoverability fix, not a rename: the archived copy of
# the contract must NOT come back, and the canonical pointer must stay.
ARCHIVED_ACCESSIBILITY_DIR = "design/handoff"


def test_accessibility_contract_is_canonical_in_docs():
    """The non-negotiable contract lives under docs/accessibility/, not
    inside the archived design/handoff/ package (audit PW-P1-01)."""
    contract = REPO_ROOT / ACCESSIBILITY_CONTRACT
    assert contract.is_file(), (
        f"{ACCESSIBILITY_CONTRACT} missing — the accessibility contract "
        "must live in a canonical docs location, not design/handoff/"
    )
    for rel in ACCESSIBILITY_SIBLINGS:
        assert (REPO_ROOT / rel).is_file(), f"accessibility sibling missing: {rel}"


def test_accessibility_contract_not_back_under_archived_handoff():
    """The archived spec package must not regain canonical copies."""
    archived = REPO_ROOT / ARCHIVED_ACCESSIBILITY_DIR
    for name in (
        "ACCESSIBILITY_CONTRACT.md",
        "SCREEN_READER_WALKTHROUGH.md",
        "RESPONSIVE_RULES.md",
        "PREFERENCES_SCHEMA.json",
    ):
        assert not (archived / name).exists(), (
            f"archived design/handoff/ regained a canonical accessibility "
            f"copy: {ARCHIVED_ACCESSIBILITY_DIR}/{name}"
        )


def test_agents_md_points_at_the_accessibility_contract():
    """AGENTS.md is the agent entry point; it must route UI work to the
    contract (audit PW-P1-02)."""
    agents = (REPO_ROOT / "AGENTS.md").read_text()
    assert ACCESSIBILITY_CONTRACT in agents, (
        "AGENTS.md must reference docs/accessibility/ACCESSIBILITY_CONTRACT.md "
        "so agents doing UI work discover the contract"
    )


def test_status_md_stays_a_pointer_to_worlds_current_state():
    """Root STATUS.md is a compatibility pointer, not another status ledger.

    Worlds owns its own current-state router. Cross-repo work is discovered
    through the owning repositories/issues rather than a maintained Homelab
    CHECKOFF snapshot.
    """
    status = REPO_ROOT / "STATUS.md"
    assert status.is_file(), "root STATUS.md missing"
    text = status.read_text()
    assert ".project/CURRENT.md" in text, (
        "STATUS.md must point at Worlds' canonical current-state router"
    )
    assert "github.com/rylee-bee-labs/worlds/issues" in text, (
        "STATUS.md must route durable unfinished work to GitHub Issues"
    )
    assert "docs/agent/CHECKOFF.md" not in text, (
        "STATUS.md must not resurrect the retired Homelab CHECKOFF protocol"
    )
    assert not re.search(r"^\|\s*(COMPLETE|WORKING|BLOCKED|WAITING)\b", text, re.M), (
        "STATUS.md must stay a pointer, not duplicate current-state rows"
    )
