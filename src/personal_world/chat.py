"""Chat capability: the chat-loop machinery over the live providers.

Architecture target (docs/history/DESIGN-HANDOFF.md, ROADMAP "Now"):
Personal World UI -> Chat API -> small context builder ->
provider-neutral ChatContract -> local model endpoint.

This module owns the provider-neutral loop pieces: message building
(system prompt + persona/templates + context), the ONE tool-calling
loop (``chat_with_tools_loop``), assistant-drafted proposal extraction,
and ``chat_once``. The provider classes themselves are in
``chat_registry`` (single implementation — the former orphan copies in
this module were removed, ORPH-03) and are re-exported here for
compatibility.

The local AI is optional and replaceable. With no provider configured
the capability reports ``not_configured`` and the core still boots;
the dashboard degrades to an "AI not connected" state rather
than a fake conversation.

Adapters in this module never log or persist secret material; keys
arrive through env indirection (the framework's secret rule). Chat
context is built from safe read APIs only -- the chat path can observe
the world but never mutates privileged state.
"""

import json
from typing import Any

# ONE set of live provider classes (ORPH-03 de-duplication): the
# provider implementations, the builder, and the lenient small-model
# tool-call parser all are in ``chat_registry``. This module keeps the
# chat-loop machinery (message building, proposal extraction, the single
# tool-calling loop) and re-exports the provider names so historical
# ``from personal_world.chat import OllamaChat`` keeps working against
# the same classes the registry builds.
from .chat_registry import (  # noqa: F401
    CHAT_TIMEOUT_SECONDS,
    ChatContract,
    OllamaChat,
    OpenAICompatChat,
    build_chat_provider,
    lenient_tool_calls,
)
from .envelope import Result, fail, ok

MAX_CONTEXT_CHARS = 8000
"""Upper bound on the injected world-context block so a bloated world
state cannot silently exceed a small local model's context window."""

PARTIAL_FINDINGS_MAX = 6
"""How many tool results the loop-limit reply may carry (LANG-034):
partial accuracy, bounded."""

PARTIAL_SUMMARY_CHARS = 240
"""Per-finding summary cap, so a fat tool payload cannot bloat the
response the UI renders."""


def partial_finding(tool_name: str, tool_result: Result) -> dict[str, Any]:
    """One bounded partial finding (LANG-034).

    `summary` is a bounded plain-text excerpt of the tool result's own
    data — the real content the model already saw, never a summary the
    code invented. Malformed/non-JSON data degrades to the status only.
    """
    summary = ""
    try:
        summary = json.dumps(tool_result.data, default=str) if tool_result.data else ""
    except (TypeError, ValueError):
        summary = ""
    if len(summary) > PARTIAL_SUMMARY_CHARS:
        summary = summary[: PARTIAL_SUMMARY_CHARS - 1] + "…"
    return {
        "tool": tool_name,
        "ok": tool_result.ok,
        "status": tool_result.status,
        "summary": summary,
    }


def _repair_tool_arguments(raw: Any) -> tuple[dict[str, Any] | None, bool]:
    """Parse a tool-call ``arguments`` payload into a dict.

    Returns ``(args, repaired)``. ``args is None`` means the arguments
    are unrecoverable — the loop reports an invalid_args tool
    result instead of invoking with invented defaults. ``repaired``
    marks lenient recoveries (trailing commas, truncation, python-ish
    literals) so the loop can journal what happened.
    """
    if isinstance(raw, dict):
        return raw, False
    if raw is None:
        return {}, False
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}, False
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed, False
            return None, False
        except (json.JSONDecodeError, TypeError):
            pass
    from .chat_registry import _lenient_json_loads

    parsed = _lenient_json_loads(raw)
    if isinstance(parsed, dict):
        return parsed, True
    return None, True


def chat_with_tools_loop(
    provider: Any,
    messages: list[dict[str, Any]],
    tool_reg: Any,
    tool_schemas: list[dict[str, Any]],
    max_rounds: int = 3,
) -> Result:
    """THE single chat tool loop (shared by /api/chat and tests).

    The model selects read + proposal tools, the loop executes them
    through the ToolRegistry, and the model explains the results.
    Write-safety is structural: the registry exposes only read and
    proposal tools (``list_ollama_schemas``) and ``invoke`` refuses
    execution tools, so even a hallucinated ``execute_*`` call cannot
    mutate anything.

    Lenient by design (small local brains, ADR 0002): malformed
    ``arguments`` JSON is repaired when unambiguous; when it is not, the
    tool is NOT invoked and an ``invalid_args`` result goes back
    to the model. Tool results are never invented. ``max_rounds`` bounds
    the loop; a provider crash becomes an ``unavailable`` Result.
    """
    current_messages = list(messages)
    tool_calls_made: list[dict[str, Any]] = []
    partial_results: list[dict[str, Any]] = []
    last_model = "unknown"

    for _round in range(max_rounds):
        try:
            result = provider.chat_with_tools(current_messages, tool_schemas)
        except Exception as e:
            return Result(
                ok=False, status="unavailable", warnings=[f"chat provider failed: {e}"]
            )
        if not result.ok:
            return result

        data = result.data or {}
        last_model = data.get("model") or last_model
        tool_calls = data.get("tool_calls")
        if not tool_calls:
            # Final text response. Surface loop provenance when tools ran.
            if tool_calls_made and isinstance(data, dict):
                return ok(
                    result.status, data={**data, "tool_calls_made": tool_calls_made}
                )
            return result

        # Echo the assistant turn (content + calls) so providers that
        # require the pairing (OpenAI-compat, Anthropic) stay happy.
        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": data.get("reply") or "",
            "tool_calls": tool_calls,
        }
        current_messages.append(assistant_msg)

        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            func = tc.get("function") or {}
            tool_name = str(func.get("name") or tc.get("name") or "")
            tool_args, repaired = _repair_tool_arguments(
                func.get("arguments", tc.get("arguments"))
            )
            tool_call_id = tc.get("id", "")

            if tool_args is None:
                # Unrecoverable arguments: failure back to the
                # model, the tool is never invoked with invented args.
                tool_result: Result = fail(
                    "invalid_args",
                    warnings=[
                        f"tool '{tool_name}' was called with malformed "
                        "arguments that could not be recovered; retry "
                        "with valid JSON arguments"
                    ],
                )
            else:
                tool_result = tool_reg.invoke(tool_name, tool_args)
            tool_calls_made.append(
                {
                    "tool": tool_name,
                    "args": tool_args if tool_args is not None else None,
                    "args_repaired": repaired,
                    "ok": tool_result.ok,
                    "status": tool_result.status,
                }
            )
            # Real results the loop can already share if the round budget
            # runs out before the model wraps up (LANG-034). Bounded:
            # read-only payloads, capped count and summary length.
            partial_results.append(partial_finding(tool_name, tool_result))

            tool_msg: dict[str, Any] = {
                "role": "tool",
                "content": json.dumps(tool_result.model_dump(mode="json")),
            }
            if tool_call_id:
                tool_msg["tool_call_id"] = tool_call_id
            current_messages.append(tool_msg)

        # Continue the loop — the model now sees the real tool results.

    # Max rounds reached: report what was gathered, and INCLUDE
    # the partial tool results already in hand (LANG-034) instead of
    # promising findings the visible reply never carried. An additive
    # payload field, no contract break; `reply` is the canonical
    # manifest copy.
    return ok(
        "healthy",
        data={
            "reply": "I reached the lookup limit before I could finish. "
            "I can share the partial results or try a narrower question.",
            "partial_findings": partial_results[:PARTIAL_FINDINGS_MAX],
            "tool_calls_made": tool_calls_made,
            "model": last_model,
        },
    )


def trim_context(context: str, limit: int = MAX_CONTEXT_CHARS) -> str:
    """Bound the world-context block. Truncation is announced in the
    block itself so the model (and the human) can see it happened."""
    if len(context) <= limit:
        return context
    kept = context[:limit]
    return kept + f"\n[…context truncated at {limit} chars…]"


def build_chat_messages(
    user_message: str,
    world_context: str,
    history: list[dict[str, str]] | None = None,
    tool_descriptions: str | None = None,
    persona: str | None = None,
    tone: str | None = None,
) -> list[dict[str, str]]:
    """System prompt + optional short history + the new user message.

    The system prompt establishes the Personal World persona, injects
    the trimmed world-context block, and forbids the model from
    inventing state it was not shown. History is capped to the last six
    turns to stay inside small local-model context windows.

    ``persona`` carries first-class brain templates (TemplateRegistry
    compose output: core instructions, companion personality, surface
    focus). Templates LEAD the system prompt — a small model weighs the
    first lines heaviest — and the built-in identity below stays as the
    guaranteed minimum (truth rules, status vocabulary, proposal
    contract) so an empty or malformed template tree can never remove
    the safety text.

    ``tone`` selects the register of the ONE voice (TRUE-NORTH § Voice;
    ``voice.tone_instruction``): warm (default) · concise · playful ·
    formal. The tone block sits between the persona and the identity
    minimum and changes phrasing only — an unknown or absent tone adds no
    block, and no tone can remove or weaken the minimum. With the
    personality pack off (on by default since 2026-09-25), the caller passes no companion
    persona, so tone + the one voice minimum is the whole identity.

    SUGGESTIONS, not authority: the prompt teaches ONE tiny fenced
    proposal block the assistant MAY use when it notices a Journal
    entry that may need correcting (assistant-drafted correction
    proposals). The block is a CONTRIBUTION the human reviews — it is
    never executed, and ordinary chat confirmation is never
    authorization. Everything about the block is validated after the
    round-trip; anything malformed degrades to ordinary text.
    """
    tool_block = ""
    if tool_descriptions:
        tool_block = (
            "\n\n## Available tools\n"
            "You can answer questions about the world using these capabilities. "
            "When someone asks about something covered by a tool, answer from "
            "the context block. If the context doesn't have the answer, say so.\n\n"
            f"{tool_descriptions}\n"
        )
    persona_block = ""
    if persona and persona.strip():
        persona_block = persona.strip() + "\n\n"
    # The one voice's tone register (TRUE-NORTH § Voice). Unknown or
    # absent tones produce no block: the identity minimum below is
    # register-neutral, so the reply stays accurate rather than adopting
    # an invented register.
    from .voice import tone_instruction

    tone_block = ""
    tone_text = tone_instruction(tone)
    if tone_text:
        tone_block = tone_text + "\n\n"
    system = (
        persona_block
        + tone_block
        + "You are the Worlds assistant: a calm, factual companion "
        "embedded in a personal control plane. You answer questions "
        "about the state of the world using ONLY the context block below. "
        "If the context does not contain the answer, say so plainly "
        "instead of inventing status, names, or numbers. Status vocabulary "
        "is fixed: healthy, warning, unknown, needs_attention, unavailable, "
        "stale, disabled, not_configured. Keep replies short and "
        "structured; prefer lists over prose paragraphs when listing. "
        "The tone register above sets the phrasing; it never changes "
        "these rules.\n\n"
        "You may notice a recent Journal entry that looks wrong compared "
        "to later entries. If — and only if — the context clearly "
        "supports it, offer to prepare a correction: explain why in one "
        "sentence in your reply, then append a proposal block in "
        "EXACTLY this shape (one line per field, no extra fields):\n"
        "```\n"
        "PW-PROPOSAL journal_correction\n"
        "entry_ts: <the entry's exact timestamp from the context>\n"
        "proposed_text: <one corrected sentence>\n"
        "reason: <short reason>\n"
        "evidence_summary: <one sentence citing which later entries "
        "support this>\n"
        "```\n"
        "The proposal is a DRAFT for review — never a change. "
        "If evidence is weak or ambiguous, phrase the suggestion "
        "accordingly or do not propose. Never invent timestamps or "
        "evidence.\n\n"
        "--- Personal World context (observed, read-only) ---\n"
        f"{trim_context(world_context)}\n"
        "--- end context ---"
        f"{tool_block}"
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    if history:
        for m in history[-6:]:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages


#: The fenced proposal header the system prompt teaches.
PROPOSAL_HEADER = "PW-PROPOSAL journal_correction"
#: Hard caps mirroring the Journal write path (supersede: 2000/200).
PROPOSAL_TEXT_MAX = 2000
PROPOSAL_REASON_MAX = 200
PROPOSAL_EVIDENCE_MAX = 300
PROPOSAL_FIELDS = ("entry_ts", "proposed_text", "reason", "evidence_summary")


def extract_proposal(reply: str) -> tuple[str | None, str]:
    """Split a reply into (proposal dict as JSON string or None,
    visible reply text).

    Strict and fail-closed: a block is accepted ONLY when the header
    is exact and all four fields are present, non-empty, and within
    their caps — otherwise the whole block degrades to ordinary text
    (it stays visible in the reply; no proposal is surfaced). The
    returned JSON is a flat object with the validated fields.
    """
    import json as _json

    fence_start = reply.find("```")
    while fence_start != -1:
        fence_end = reply.find("```", fence_start + 3)
        if fence_end == -1:
            break
        block = reply[fence_start + 3 : fence_end].strip("\n")
        lines = [ln.rstrip() for ln in block.split("\n") if ln.strip()]
        if lines and lines[0].strip() == PROPOSAL_HEADER:
            fields: dict[str, str] = {}
            for ln in lines[1:]:
                if ":" not in ln:
                    fields = None  # type: ignore[assignment]
                    break
                key, _, value = ln.partition(":")
                key = key.strip()
                if key not in PROPOSAL_FIELDS or key in fields:
                    fields = None  # type: ignore[assignment]
                    break
                fields[key] = value.strip()
            if (
                fields
                and all(f in fields and fields[f] for f in PROPOSAL_FIELDS)
                and len(fields["proposed_text"]) <= PROPOSAL_TEXT_MAX
                and len(fields["reason"]) <= PROPOSAL_REASON_MAX
                and len(fields["evidence_summary"]) <= PROPOSAL_EVIDENCE_MAX
            ):
                proposal = {
                    "kind": "journal_correction",
                    **fields,
                }
                # The visible reply drops the machine block; the
                # suggestion sentence stays.
                visible = (
                    reply[:fence_start].rstrip()
                    + ("\n\n" if reply[fence_end + 3 :].lstrip() else "")
                    + reply[fence_end + 3 :].lstrip()
                ).strip()
                return _json.dumps(proposal), visible
            # Malformed proposal block: degrade to ordinary text (the
            # block simply remains part of the reply; no proposal).
            return None, reply
        fence_start = reply.find("```", fence_end + 3)
    return None, reply


def chat_once(
    provider: ChatContract,
    messages: list[dict[str, str]],
) -> Result:
    """One provider round-trip with fail-closed error mapping."""
    try:
        return provider.chat(messages)
    except Exception as e:  # provider crash must never reach the API surface
        return Result(
            ok=False, status="unavailable", warnings=[f"chat provider failed: {e}"]
        )
