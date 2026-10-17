"""Chat context builder: assemble a safe, read-only world snapshot.

Everything the chat system prompt sees comes from the same read APIs
the dashboard uses. Private-class lore and journal events are excluded
by default (the journal API already disclosure-filters; the chat path
follows the strictest rule). Secrets never enter this path: no export,
no backup, no broker output is ever serialized into context.
"""

from pathlib import Path

from .journal import Journal
from .providers.registry import Registry
from .source_control import configured_search_paths, status_all
from .world import World

CONTEXT_HISTORY_EVENTS = 12
SOURCE_CONTROL_REPOS_IN_CONTEXT = 12
PROJECTS_IN_CONTEXT = 12


def _age_words(age_seconds: int) -> str:
    """Compact relative age for the assistant context — ONE wording
    for the whole backend ("4 minutes", "1 hour", "just now").
    The model gets the age as prose so it can answer "how fresh?"
    without doing date math, and can hedge when stale."""
    if age_seconds < 60:
        return "just now"
    minutes = age_seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''}"


def _fmt_caps(statuses: dict) -> list[str]:
    lines = []
    for cap, s in sorted(statuses.items()):
        warn = f" ({'; '.join(s['warnings'])})" if s.get("warnings") else ""
        lines.append(f"- {cap}: {s['status']}{warn}")
    return lines


def build_world_context(
    world: World,
    registry: Registry,
    journal: Journal,
    include_journal: bool = True,
    config_dir=None,
) -> str:
    """Render the world as plain text for the chat system prompt."""
    summary = world.summary()
    parts: list[str] = ["## World summary"]
    parts.append(
        f"- facts: {summary['facts']}, intents: {summary['intents']}, "
        f"policies: {summary['policies']} "
        f"({summary['cemented_policies']} cemented), packs: {summary['packs']}"
    )
    lore = summary.get("lore", {})
    lore_bits = [f"{k}: {v}" for k, v in lore.items() if v]
    parts.append(
        "- lore: " + (", ".join(lore_bits) if lore_bits else "none recorded")
    )

    parts.append("\n## Capability status")
    parts.extend(_fmt_caps(registry.status_map()))

    actors = registry.actors()
    if actors:
        parts.append("\n## Connected components (staff directory)")
        for a in actors:
            parts.append(
                f"- {a.name}: role={a.role}, status={a.status}, "
                f"writes={a.writes}"
            )

    intents = sorted(world.intents)
    if intents:
        parts.append("\n## Stated intent (what the operator wants true)")
        for key in intents:
            v = world.intents[key].value
            vs = v if isinstance(v, str) else str(v)
            parts.append(f"- {key} = {vs}")

    policies = sorted(world.policies)
    if policies:
        parts.append("\n## Policies (hard rules)")
        for key in policies:
            p = world.policies[key]
            extra = " (cemented)" if p.mutability == "cemented" else ""
            parts.append(f"- {key}: {p.effect.value}{extra}")

    public_lore = [
        (k, entry) for k, entry in sorted(world.lore.items())
        if entry.classification.value == "world"
    ]
    if public_lore:
        parts.append("\n## Lore (world-classified only)")
        for k, entry in public_lore:
            vs = entry.value if isinstance(entry.value, str) else str(entry.value)
            parts.append(f"- {k} [{entry.state.value}]: {vs}")

    if include_journal:
        events = journal.recent(CONTEXT_HISTORY_EVENTS)
        if events:
            parts.append("\n## Recent journal (newest last)")
            for e in events:
                # The exact ts key (what /api/journal serves and what a
                # correction proposal must reference) — not a display
                # truncation. The assistant may quote it in a
                # PW-PROPOSAL block; readers (human and code) resolve
                # the same identifier.
                ts = e.ts.isoformat()
                parts.append(f"- [{ts}] {e.kind.value}: {e.summary}")

    if config_dir is not None:
        parts.extend(
            _source_control_block(Path(config_dir))
        )
        parts.extend(_projects_block())

    return "\n".join(parts)


def build_ui_context(
    route: str | None,
    section_id: str | None,
    section_label: str | None,
    section_status: str | None,
    section_capabilities: tuple[str, ...] | list[str] | None,
    entity: str | None = None,
) -> str | None:
    """Render the caller's observed UI location for the system prompt.

    This is provenance, NOT canonical truth: the client says where in
    the interface the person is; the server trusts it only as a hint
    ("observed from the UI") and never as world state. Anything missing
    or unrecognized renders as `unknown` rather than being
    dropped silently — a stale tab must not produce a confident lie.
    Returns None when the caller sends nothing (global chat), in which
    case no UI-location block is injected at all.
    """
    if not route and not section_id:
        return None
    label = section_label or "unknown section"
    status = section_status or "unknown"
    caps = ", ".join(section_capabilities or ()) or "none declared"
    lines = [
        "## Where the person is (observed from the UI, not world state)",
        f"- route: {route or 'unknown'}",
        f"- section: {section_id or 'unknown'} ({label})",
        f"- section status: {status}",
        f"- section capabilities: {caps}",
        f"- selected: {entity}" if entity else "",
        "If the person asks about 'here' or 'this page', they mean this "
        "section. Answer from the canonical context block; if the answer "
        "is not there, say so plainly.",
    ]
    return "\n".join(lines)


def _projects_block() -> list[str]:
    """Bounded, compact project-estate projection from the
    agent-sync sensor (the same read-only observation the Projects
    screen serves). Context budget: one line per project that is NOT
    quiet (state word + tree summary), quiet projects as ONE count
    line, SHAs never (they enter context only when the person asks
    and the assistant reads the Projects details). Sensor absent ->
    no block at all (the estate is unknown, not empty). The assistant
    may summarize/explain/point to Projects; it may NOT mutate,
    and this block carries no authority to do anything."""
    from .providers.agent_sync import AgentSyncProjectSensor
    try:
        result = AgentSyncProjectSensor().observe_projects()
    except Exception:
        return []
    if not result.ok or not result.data:
        return []
    projects = result.data.get("projects") or []
    if not projects:
        return []
    quiet = 0
    lines = []
    for p in projects:
        publish = p.get("publish_state")
        tree = p.get("working_tree") or {}
        dirty = (tree.get("staged", 0) + tree.get("modified", 0)
                 + tree.get("untracked", 0) + tree.get("conflicted", 0))
        state: str | None = {
            "diverged": "diverged",
            "ahead": "unpublished (local ahead)",
            "behind": "behind remote",
            "match": None,
            None: "unknown (remote unreachable)",
        }.get(publish, "unknown")
        if publish == "match" and dirty > 0:
            state = "published; local work"
        if state is None:
            quiet += 1
            continue
        lines.append(
            f"- {p.get('project')}: {state}"
            + (f"; {dirty} uncommitted file(s)" if dirty else "; clean tree")
        )
    if quiet:
        lines.append(f"- {quiet} quiet")
    # Observation age, in the assistant's own vocabulary: the model
    # must know WHEN the estate was observed so it never presents an
    # old observation as current certainty. Calm language — "may be
    # stale", never error vocabulary. Invalid/missing timestamp ->
    # no age line (never a fabricated age).
    from .providers.agent_sync import freshness as observation_freshness
    fresh = observation_freshness(result.data.get("observed_at"))
    age_seconds = fresh.get("age_seconds")
    if age_seconds is not None:
        age_words = _age_words(age_seconds)
        # "just now old" is not a sentence anyone should read; the
        # sub-minute age is simply "just now"
        age_line = ("Project observations: just now."
                    if age_words == "just now"
                    else f"Project observations: {age_words} old.")
        if fresh.get("freshness") == "stale":
            age_line = (f"Project observations: {age_words} old; "
                        "may be stale.")
        lines.append(age_line)
    return ["\n## Projects (agent-sync observation)"] + lines


def _source_control_block(config_dir) -> list[str]:
    paths = configured_search_paths(Path(config_dir))
    if not paths:
        return []
    try:
        repos = status_all(paths)
    except Exception:
        return []
    if not repos:
        return ["\n## Source repositories", "- none found in configured paths"]
    ahead = sum(1 for r in repos if (r.get("ahead") or 0) > 0)
    behind = sum(1 for r in repos if (r.get("behind") or 0) > 0)
    dirty = sum(1 for r in repos if r.get("dirty"))
    out = [
        "\n## Source repositories",
        f"- {len(repos)} watched: {ahead} ahead of remote, {behind} behind, "
        f"{dirty} with uncommitted changes",
    ]
    for r in repos[:SOURCE_CONTROL_REPOS_IN_CONTEXT]:
        state = []
        if (r.get("ahead") or 0) > 0:
            state.append(f"ahead {r['ahead']}")
        if (r.get("behind") or 0) > 0:
            state.append(f"behind {r['behind']}")
        if r.get("dirty"):
            state.append("uncommitted changes")
        out.append(
            f"- {r['name']} [{r.get('branch') or '?'}]: "
            f"{', '.join(state) if state else 'clean'}"
            + (f" — last: {r['last_commit_subject']}"
               if r.get("last_commit_subject") else "")
        )
    return out
