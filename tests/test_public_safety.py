"""Public-safety gate: the tracked default configuration of this
intentionally public repository must not carry operator deployment
endpoints. Private addresses, private hostnames, and this project's
real deployment topology belong in a private runtime config directory
(see docs/OPERATIONS.md), never in the shipped default.

RFC 5737/2606 documentation ranges and example.invalid hosts are
allowed everywhere (docs, tests, example files).
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TRACKED_CONFIG = REPO_ROOT / "config" / "connections.json"
EXAMPLE_CONFIG = REPO_ROOT / "config" / "connections.example.json"

# RFC1918 + link-local ranges for the private halves only; public
# documentation ranges (RFC 5737: 192.0.2.0/24, 198.51.100.0/24,
# 203.0.113.0/24) are deliberately NOT matched. Loopback (127.0.0.1)
# is allowed: it is the documented local-dev binding, not topology.
PRIVATE_IP_PARTS = (
    "192.168.",
    "10.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
    "169.254.",
    "localhost",
)

# Real-world deployment hostnames discovered in the original exposure.
# Kept as an explicit regression list: a future edit that re-adds one
# of these strings fails CI with a name, not a mystery.
# (Literal redacted post-rewrite: the original operator hostname lives
# only in private runtime configs now; the RFC2606 .invalid TLD is
# reserved for documentation and can never be a real deployment host.)
FORBIDDEN_HOSTS = (
    ".home.example.test",
    "operator-home",
)


def _forbidden_strings() -> tuple[str, ...]:
    return PRIVATE_IP_PARTS + FORBIDDEN_HOSTS


def _assert_clean(payload: dict, source: Path) -> None:
    blob = json.dumps(payload)
    for marker in _forbidden_strings():
        assert marker not in blob, (
            f"{source.name} carries private deployment marker "
            f"'{marker}' -- move real endpoints to a private runtime "
            f"config directory, not the tracked default"
        )


def _is_safe_ollama_entry(conn: dict) -> bool:
    """Allow a single local-ollama provider with no secrets and no
    private-IP base_url.  Docker service names (e.g. 'ollama') are
    not real topology — they resolve only inside the compose network."""
    if conn.get("type") != "ollama":
        return False
    for forbidden in ("api_key", "apikey", "token", "password", "secret"):
        if forbidden in conn:
            return False
    base = conn.get("base_url", "")
    for marker in PRIVATE_IP_PARTS:
        if marker in base:
            return False
    return True


def test_tracked_connections_json_is_public_safe():
    """The shipped default config may carry only safe local-ollama
    providers (no secrets, no private IPs).  All other real endpoints
    belong in a private runtime config."""
    payload = json.loads(TRACKED_CONFIG.read_text())
    conns = payload.get("connections") or []
    bad = [c for c in conns if not _is_safe_ollama_entry(c)]
    assert not bad, (
        f"tracked config/connections.json must only contain safe local-ollama "
        f"providers (found {len(bad)} non-ollama entries); real endpoints "
        f"live in a private runtime config"
    )
    _assert_clean(payload, TRACKED_CONFIG)


def test_example_config_stays_documentation_safe():
    """The example may show the shape of wiring but only with
    documentation-reserved hosts (example.invalid)."""
    payload = json.loads(EXAMPLE_CONFIG.read_text())
    blob = json.dumps(payload)
    for marker in PRIVATE_IP_PARTS + FORBIDDEN_HOSTS:
        assert marker not in blob, (
            f"connections.example.json must use example.invalid hosts, found '{marker}'"
        )


@pytest.mark.parametrize(
    "path",
    [
        REPO_ROOT / "config" / "connections.json",
        REPO_ROOT / "config" / "connections.example.json",
        REPO_ROOT / "env.example",
        REPO_ROOT / "compose.yaml",
    ],
    ids=["tracked", "example", "env-example", "compose"],
)
def test_shipped_files_carry_no_private_endpoints(path):
    """Any file a stranger's clone bootstraps from must be free of
    operator topology."""
    assert path.exists(), f"{path.name} missing"
    text = path.read_text()
    for marker in _forbidden_strings():
        assert marker not in text, (
            f"{path.name} carries private deployment marker '{marker}'"
        )


# ---------------------------------------------------------------------------
# Secret-shape scan over every tracked text file (P0.7).
#
# The endpoint checks above catch topology. This catches *credential
# material*: a provider key pasted into a tracked JSON, a bearer token
# in a frontend env file, a private key block. It is shape-based and
# deliberately conservative — env-indirection forms (`api_key_env`,
# `token_env`, `secret_ref`) are the allowed way to reference secrets
# and never match. Findings are reported redacted: the test must never
# echo the very value it is guarding.
# ---------------------------------------------------------------------------

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "openai-style key (sk-…)": re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),
    "token-plan key (tp-…)": re.compile(r"\btp-[a-z0-9]{16,}"),
    "github token (ghp_/gho_/ghs_/ghr_)": re.compile(r"\bgh[posr]_[A-Za-z0-9]{30,}"),
    "aws access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "inline api_key/token/password/secret value": re.compile(
        r"""["']?\b(api_key|apikey|token|password|passwd|secret|bearer)["']?\s*[:=]\s*["'][^"'\s$<>{}]{24,}["']""",
        re.IGNORECASE,
    ),
    "client-side token env (VITE_*TOKEN|SECRET|KEY)": re.compile(
        r"\bVITE_[A-Z0-9_]*(TOKEN|SECRET|KEY|PASSWORD)\b"
    ),
}

# Source/config/test/script/frontend code must not bake in a personal
# home directory. Docs may mention the pattern when describing it.
HOME_PATH = re.compile(r"(/home/[a-z][a-z0-9_\-]*/|/Users/[A-Za-z][A-Za-z0-9_\-]*/)")
HOME_PATH_SCOPES = (
    "src/",
    "config/",
    "tests/",
    "scripts/",
    "frontend/",
    "frontend-v2/",
)

TEXT_SUFFIXES = {
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".sh",
    ".ts",
    ".tsx",
    ".js",
    ".html",
    ".css",
    ".txt",
    ".example",
    ".cfg",
    ".ini",
    ".env",
}
# Generated/asset files: hashes and base64 art, never credentials.
SKIP_PREFIXES = (
    "design/assets/",
    "design/screens/",
    "design/exports/",
    "design/handoff/",
)
SKIP_NAMES = {"uv.lock", "package-lock.json"}
# A synthetic canary a test deliberately plants (to prove it cannot leak)
# is allowed only with this exact marker on the same line, so the
# exception is visible in review and grep-able.
ALLOW_MARKER = "pw-safety: synthetic"


def _tracked_text_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True
        ).stdout
        names = [n for n in out.decode().split("\0") if n]
    except Exception:  # no git (e.g. a tarball checkout): walk instead
        names = [
            str(p.relative_to(REPO_ROOT))
            for p in REPO_ROOT.rglob("*")
            if p.is_file()
            and ".git" not in p.parts
            and "node_modules" not in p.parts
            and ".venv" not in p.parts
        ]
    files = []
    for n in names:
        if n.startswith(SKIP_PREFIXES) or Path(n).name in SKIP_NAMES:
            continue
        p = Path(n)
        if p.suffix.lower() in TEXT_SUFFIXES or p.name.startswith(".env"):
            full = REPO_ROOT / p
            if full.is_file():
                files.append(p)
    return files


def _redact(match: str) -> str:
    return match[:4] + "…" + f"({len(match)} chars)"


def test_tracked_text_files_carry_no_secret_shaped_values():
    """No credential material in any tracked text file. Redacted report."""
    findings: list[str] = []
    for rel in _tracked_text_files():
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # this very file defines the patterns; skip its own pattern table
        if rel.as_posix() == "tests/test_public_safety.py":
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if ALLOW_MARKER in line:
                continue  # explicit, reviewable canary (tests only)
            for label, pat in SECRET_PATTERNS.items():
                m = pat.search(line)
                if m:
                    findings.append(f"{rel}:{lineno} [{label}] {_redact(m.group(0))}")
    assert not findings, (
        "secret-shaped values in tracked files (values redacted). Move them "
        "to private runtime config via env indirection (api_key_env / "
        "token_env / secret_ref) and rotate the exposed credential:\n  "
        + "\n  ".join(findings)
    )


def test_code_and_config_carry_no_personal_home_paths():
    """A hard-coded /home/<user>/ or /Users/<user>/ path is both a
    personal-data leak and a portability bug (PW_DATA_DIR / PW_CONFIG_DIR
    exist for this)."""
    findings: list[str] = []
    for rel in _tracked_text_files():
        posix = rel.as_posix()
        if (
            not posix.startswith(HOME_PATH_SCOPES)
            or posix == "tests/test_public_safety.py"
        ):
            continue
        text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if HOME_PATH.search(line):
                findings.append(f"{posix}:{lineno}")
    assert not findings, "personal home paths in code/config:\n  " + "\n  ".join(
        findings
    )


# ---------------------------------------------------------------------------
# Repo-wide topology scan (extends the endpoint checks above to EVERY
# tracked text file, not just the shipped bootstrap files).
#
# Markers mirror PRIVATE_IP_PARTS + FORBIDDEN_HOSTS with two deliberate
# refinements, both consistent with the loopback rule documented at the
# top of this file:
#   * loopback/`localhost` is never flagged globally — it is the
#     documented local-dev binding, not operator topology;
#   * IP matches are octet-boundary regexes, not raw substrings like
#     "10.", so version strings ("3.10.1") never false-positive, and
#     RFC 5737 documentation ranges (192.0.2.x, 198.51.100.x,
#     203.0.113.x) and example.invalid hosts are valid everywhere.
# Exclusions for this scan are ONLY: this file's own pattern tables,
# binary/generated artifacts (handled by the TEXT_SUFFIXES filter in
# _tracked_text_files: images, .lottie, .svg, lockfiles are never
# scanned), and lines carrying the visible `pw-safety: synthetic`
# marker (synthetic test values).
# ---------------------------------------------------------------------------

TOPOLOGY_PATTERNS: dict[str, re.Pattern[str]] = {
    "private IPv4 (RFC1918/link-local)": re.compile(
        # exactly four octets: {1,2} let npm semver "^10.6.0" match as an
        # "IP" (two public-safety false positives, 2026-09-20) — versions
        # are three dotted parts; a real IPv4 is always four.
        r"(?<![\d.])(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|169\.254\.\d{1,3}\.\d{1,3})"
        r"(?![\d.])"
    ),
    "operator hostname (operator-home)": re.compile(r"operator-home"),
    "dynamic-DNS operator host": re.compile(r"[\w.-]*duckdns\.org"),
}

# Personal absolute paths that must not appear in current-facing tracked
# text. Historical, dated record files may keep them (checksummed-style
# evidence; editing would falsify the record), so they carry named
# exclusions below with a justification each.
PERSONAL_PATH_PATTERN = re.compile(r"/(?:var/)?home/rylee\b|/mnt/c/Users/ryleeb\b")
PERSONAL_PATH_EXEMPT = {
    # Dated 2026-09-12 evidence/attestation records: preserving what was
    # actually observed on that date is the point of the file; scrubbing
    # the operator path would rewrite a historical attestation.
    ".project/HANDOFF-FRESHNESS-EVIDENCE-2026-09-12.md",
    ".project/attestations/2026-09-12-auto-free-onboarding.json",
    ".project/attestations/2026-09-12-glm-next-phase-orchestration.json",
    # Deliberate single-user "Rylee-only enrichment" overlay whose local
    # mount paths (a Windows-mounted homelab and a Kilo auth file) are
    # its documented purpose; converting to env indirection is the
    # recommended follow-up, tracked in the remediation handoff.
    "compose.homelab.yaml",
}

TOPOLOGY_SELF_FILE = "tests/test_public_safety.py"


def _scan_tracked_text(patterns, label_flag: bool = False):
    """Yield (rel, lineno, label, snippet) for each match. Reports are
    short: one truncated context snippet, never a value dump."""
    for rel in _tracked_text_files():
        posix = rel.as_posix()
        if posix == TOPOLOGY_SELF_FILE:
            continue
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if ALLOW_MARKER in line:
                continue
            for label, pat in patterns.items():
                m = pat.search(line)
                if m:
                    snippet = line.strip()
                    if len(snippet) > 80:
                        snippet = snippet[:77] + "…"
                    yield posix, lineno, label, snippet


def test_tracked_text_files_carry_no_operator_topology():
    """Every tracked text file must be free of private deployment
    endpoints (docs-config markers). Failure names the marker with at
    most one short context snippet, never a dump."""
    findings = [
        f"{rel}:{lineno} [{label}] {snippet}"
        for rel, lineno, label, snippet in _scan_tracked_text(TOPOLOGY_PATTERNS)
    ]
    assert not findings, (
        "operator deployment topology in tracked files — move it to "
        "private runtime documentation (see SECURITY.md / "
        "docs/OPERATIONS.md):\n  " + "\n  ".join(findings)
    )


def test_tracked_text_files_carry_no_personal_absolute_paths():
    """`~`, `~`, and `/mnt/c/Users/ryleeb` must
    not appear in current-facing tracked text. Only the named historical
    records and the deliberate single-user overlay are exempt, each with
    a written justification in PERSONAL_PATH_EXEMPT."""
    findings = []
    for rel, lineno, _, snippet in _scan_tracked_text(
        {"personal absolute path": PERSONAL_PATH_PATTERN}
    ):
        if rel in PERSONAL_PATH_EXEMPT:
            continue
        findings.append(f"{rel}:{lineno} {snippet}")
    assert not findings, (
        "personal absolute paths in current-facing tracked files:\n  "
        + "\n  ".join(findings)
    )


def test_topology_scanner_detection():
    """The topology scanner must actually fire (canary samples; none of
    these literals appear in this file)."""
    sample_private_ipv4 = ".".join(["192", "168", "2", "141"])
    assert TOPOLOGY_PATTERNS["private IPv4 (RFC1918/link-local)"].search(
        sample_private_ipv4
    )
    assert TOPOLOGY_PATTERNS["operator hostname (operator-home)"].search(
        "world.operator-" + "home.example.test"
    )
    assert not any(
        p.search(s)
        for s in (
            "version 3.10.1",
            "192.0.2.15",
            "198.51.100.7",
            "203.0.113.9",
            "auth.example.invalid",
            "127.0.0.1",
        )
        for p in TOPOLOGY_PATTERNS.values()
    )


def test_tracked_connections_report_never_echoes_values():
    """Companion to test_tracked_connections_json_is_public_safe: if the
    tracked file ever gains a non-ollama provider, the failure message
    names the entry, never dumps it (a dump would print the key)."""
    payload = json.loads(TRACKED_CONFIG.read_text())
    names = [
        f"{c.get('type', '?')}:{c.get('name') or c.get('id') or '?'}"
        for c in payload.get("connections", [])
        if not _is_safe_ollama_entry(c)
    ]
    assert names == [], (
        "tracked config/connections.json ships non-ollama providers "
        "(names only shown): " + ", ".join(names)
    )


@pytest.mark.parametrize(
    "sample,label",
    [
        ('"api_key": "' + "A" * 40 + '"', "inline api_key/token/password/secret value"),
        ("sk-" + "x" * 40, "openai-style key (sk-…)"),
        ("tp-" + "a1" * 12, "token-plan key (tp-…)"),
        ("ghp_" + "Z" * 36, "github token (ghp_/gho_/ghs_/ghr_)"),
        ("-----BEGIN OPENSSH PRIVATE KEY-----", "private key block"),
        ("VITE_AUTH_TOKEN=whatever", "client-side token env (VITE_*TOKEN|SECRET|KEY)"),
        ("AKIA" + "Q" * 16, "aws access key"),
    ],
)
def test_secret_scanner_detects_shapes(sample, label):
    """The scanner must actually fire on the shapes it claims to catch.
    Samples are built by concatenation so this file never contains a
    literal that looks like a credential."""
    assert SECRET_PATTERNS[label].search(sample), label


@pytest.mark.parametrize(
    "sample",
    [
        '"api_key_env": "MY_PROVIDER_KEY"',
        '"token_env": "GITEA_TOKEN"',
        '"secret_ref": "vault://gitea-token"',
        "sha256:" + "f" * 64,
        '"password": "short"',
        "VITE_API_URL=/",
    ],
)
def test_secret_scanner_allows_indirection_and_hashes(sample):
    assert not any(p.search(sample) for p in SECRET_PATTERNS.values()), sample


def _walk_keys(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{path}.{k}" if path else k, k
            yield from _walk_keys(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_keys(v, f"{path}[{i}]")


INLINE_SECRET_KEYS = {
    "api_key",
    "apikey",
    "token",
    "password",
    "secret",
    "client_secret",
    "access_token",
    "refresh_token",
}


@pytest.mark.parametrize(
    "rel",
    sorted(
        p.as_posix()
        for p in _tracked_text_files()
        if p.as_posix().startswith("config/")
        and p.suffix == ".json"
        and not p.name.endswith(".example.json")
    ),
)
def test_tracked_non_example_config_is_zero_provider_and_secret_free(rel):
    """Ownership rule (completion plan C-1): tracked config/ holds only
    schemas, examples and safe defaults.  A single local-ollama entry
    (no secrets, no private IPs) is allowed.  Personal values live in
    config/*.local.json, config.local/ or data/ — all gitignored."""
    payload = json.loads((REPO_ROOT / rel).read_text())
    conns = payload.get("connections") or []
    bad_conns = [c for c in conns if not _is_safe_ollama_entry(c)]
    assert not bad_conns, f"{rel} ships non-ollama providers"
    bad = [
        path for path, key in _walk_keys(payload) if key.lower() in INLINE_SECRET_KEYS
    ]
    assert not bad, f"{rel} has inline secret keys at: {bad} (use *_env / *_ref)"
