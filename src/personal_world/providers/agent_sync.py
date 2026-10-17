"""agent-sync project-status sensor for Project Worlds.

Consumes the read-only `agent-sync status --all --format json`
observation of Rylee's project estate and presents it as Project
Worlds' project-status truth. agent-sync (the pickle project's
adapter layer) stays AUTHORITATIVE for repository publication
state: this module invokes the tool, parses its documented
`play-nice/repo-status-v1` JSON schema, and normalizes it into
Project Worlds' internal read-only model. It never calls Git
directly, never re-implements agent-sync's computation, and never
mutates a repository — status observes, presentation presents.

There must NOT be a second Git-state implementation inside
Project Worlds. Git owns Git truth; agent-sync interprets
project/repository state; Project Worlds consumes and presents
that interpretation.

Failure model (every failure is reported, none is fatal):
  - command absent   -> 'unavailable'; Project Worlds continues
  - timeout          -> 'unavailable' (bounded; no request hangs)
  - malformed JSON   -> 'unavailable'; records are never partially
                        invented from a bad payload
  - one bad project  -> agent-sync itself isolates per-repo
                        failure into an `error` record; other
                        records survive and the bad one is kept
                        with its error text
  - remote unknown   -> safe_to_leave='unknown' is PRESERVED,
                        never converted to healthy or unhealthy

Exit-code semantics (from agent_status.py cmd_status): exit 0 =
all settled; exit 1 = valid observation but some project needs
attention ("work to do" signal, NOT a provider failure — the JSON
is still complete and ); exit 2 = no projects found. Only
non-zero-and-unparseable output is a provider failure.

Cache: none. agent-sync owns computation; every call is a fresh
dated observation carrying `observed_at`. The caller may cache a
dated result for responsiveness; a cached result must stay visibly
an observation, never timeless truth.
"""

import json
import shutil
import subprocess  # nosec B404  # reads project state through the operator's own `agent-sync` binary
from datetime import datetime, timedelta, timezone
from typing import Any

from ..envelope import Result, fail, ok
from .registry import StatusContract

SYNC_TIMEOUT_SECONDS = 60

#: Observation staleness minimum — the SAME product-wide freshness
#: convention as providers/lab_state.py's FRESHNESS (30 minutes).
#: Staleness is a claim about evidence AGE, never about state truth:
#: a stale observation of "diverged" is still a diverged observation,
#: it just isn't current evidence. Derived, not stored; state and
#: freshness remain separate dimensions.
STALE_AFTER = timedelta(minutes=30)

#: closed vocabularies straight from agent_status.py — anything
#: outside these sets is normalized to None (unknown), never
#: guessed, never silently dropped.
PUBLISH_STATES = {"match", "ahead", "behind", "diverged"}
SAFE_STATES = {"yes", "published-with-local-work", "no", "unknown"}
WORK_STATES = {
    "working", "waiting_for_help", "verifying", "complete",
    "blocked", "unknown", "deferred",
}
SCHEMA = "play-nice/repo-status-v1"


def _sync_binary() -> str | None:
    """The agent-sync CLI if present, else None. shutil.which only;
    'command absent' is an unavailable state, never fatal."""
    return shutil.which("agent-sync")


def _coerce_count(value: Any) -> int:
    """Non-negative int or 0. Counts are 0-or-int, never unknown —
    agent-sync guarantees the working_tree dict of four ints."""
    try:
        n = int(value)
        return n if n > 0 else 0
    except (TypeError, ValueError):
        return 0


def parse_observed_at(value: Any) -> datetime | None:
    """agent-sync's observed_at -> aware datetime, or None.

    None for missing/invalid timestamps — an age line that
    cannot be computed is simply not shown; no age is ever
    fabricated from a bad clock reading."""
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def freshness(observed_at: Any, now: datetime | None = None) -> dict[str, Any]:
    """Derive observation freshness from agent-sync's observed_at.

    Returns {freshness: "fresh"|"stale"|"unknown", age_seconds: int|None}
    — a SEPARATE dimension from publish_state/safe_to_leave, which are
    never altered by age. "unknown" (missing or invalid timestamp)
    stays unknown; it is not treated as stale or fresh."""
    parsed = parse_observed_at(observed_at)
    if parsed is None:
        return {"freshness": "unknown", "age_seconds": None}
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    age_seconds = max(0, int((moment - parsed).total_seconds()))
    stale = age_seconds > STALE_AFTER.total_seconds()
    return {
        "freshness": "stale" if stale else "fresh",
        "age_seconds": age_seconds,
    }


def _normalize(record: dict[str, Any]) -> dict[str, Any]:
    """One raw agent-sync record -> Project Worlds' read-only model.

    Unknown is preserved as None; closed vocabularies are enforced;
    nothing is invented. Per-repo `error` records (agent-sync's own
    isolation of a failed project) survive as error_text."""
    play_nice = record.get("play_nice") or {}
    tree = record.get("working_tree") or {}
    publish = record.get("publish_state")
    safe = record.get("safe_to_leave")
    work = record.get("work_state")
    return {
        "project": record.get("project") or record.get("path") or "unknown",
        "path": record.get("path"),
        "is_git_repo": bool(record.get("is_git_repo")),
        "branch": record.get("branch"),
        "local_head": record.get("local_head"),
        "remote_name": record.get("remote_name"),
        "remote_url": record.get("remote_url"),
        "remote_head": record.get("remote_head"),
        "publish_state": publish if publish in PUBLISH_STATES else None,
        "working_tree": {
            "staged": _coerce_count(tree.get("staged")),
            "modified": _coerce_count(tree.get("modified")),
            "untracked": _coerce_count(tree.get("untracked")),
            "conflicted": _coerce_count(tree.get("conflicted")),
        },
        "play_nice": {
            "present": bool(play_nice.get("present")),
            "revision": play_nice.get("revision"),
            "source_repository": play_nice.get("source_repository"),
        },
        "work_state": work if work in WORK_STATES else "unknown",
        "safe_to_leave": safe if safe in SAFE_STATES else "unknown",
        "error": record.get("error"),
    }


class AgentSyncProjectSensor(StatusContract):
    """Read-only project-estate observation over `agent-sync status`."""

    def __init__(self, timeout: int = SYNC_TIMEOUT_SECONDS) -> None:
        self.timeout = timeout

    def _run_all(self) -> list[dict[str, Any]] | None:
        """One `agent-sync status --all --format json` invocation.
        Returns the parsed record list, or None on any structural
        failure (missing binary, timeout, non-zero-exit with
        unparseable output, malformed JSON, non-list payload).
        Never raises; never partially invents records."""
        binary = _sync_binary()
        if binary is None:
            return None
        try:
            proc = subprocess.run(  # nosec B603  # argument list, no shell; `binary` was resolved with shutil.which
                [binary, "status", "--all", "--format", "json"],
                capture_output=True, text=True, timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
            return None
        if not proc.stdout.strip():
            return None
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, list):
            return None
        return payload

    def observe_projects(self) -> Result:
        """The estate observation: every project in agent-sync's
        curated registry, normalized, with the observation date.

        data:
          observed_at   agent-sync's own observation timestamp
          freshness     derived: fresh|stale|unknown (separate
                        dimension from publish_state; age never
                        rewrites state)
          age_seconds   seconds since observed_at (None when unknown)
          projects      list of normalized project records
        empty list when the registry is empty (that is an
        agent-sync configuration question, not a Project Worlds
        failure to be guessed around)."""
        records = self._run_all()
        if records is None:
            return fail("unavailable",
                        warnings=["agent-sync observation unavailable "
                                  "(command absent, timed out, or malformed)"])
        projects = []
        for raw in records:
            if isinstance(raw, dict) and raw.get("schema") == SCHEMA:
                projects.append(_normalize(raw))
            # a record without the expected schema is skipped rather
            # than guessed into being — a partial payload is not
            # partially trusted
        observed_at = None
        for raw in records:
            if isinstance(raw, dict) and raw.get("observed_at"):
                observed_at = raw.get("observed_at")
                break
        fresh = freshness(observed_at)
        return ok("healthy", data={
            "observed_at": observed_at,
            "freshness": fresh["freshness"],
            "age_seconds": fresh["age_seconds"],
            "projects": projects,
        })

    def observe(self) -> Result:
        """StatusContract: is the agent-sync tool usable at all?
        Cheap probe — the estate observation itself is served by
        observe_projects() so call cost stays bounded."""
        binary = _sync_binary()
        if binary is None:
            return fail("unavailable",
                        warnings=["agent-sync CLI not found on this host"])
        return ok("healthy", data={"provider": "agent-sync"})
