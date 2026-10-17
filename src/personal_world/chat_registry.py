"""Chat provider registry: multiple LLM providers with switching.

Supports:
  - Ollama (local, any model)
  - OpenAI-compatible (llama.cpp, vLLM, LiteLLM, OpenWebUI)
  - OpenAI direct (GPT-4, GPT-4o, etc.)
  - Anthropic Claude (via messages API)
  - Any future provider that speaks OpenAI-style chat

Providers are configured in connections.json under the "reasoning"
capability. The active provider can be switched at runtime via the
API. Preferences persist per-user.
"""

import json
import os
import re
import subprocess  # nosec B404  # drives the operator's own `opencode` CLI, argument-list form only
import urllib.request
from typing import Any

from .envelope import Result, fail, ok
from .url_safety import http_urlopen

CHAT_TIMEOUT_SECONDS = 120


# ── Lenient small-model tool-call parsing ────────────────────────────
#
# A tiny local brain (Qwen3 1.7B et al., ADR 0002) often cannot produce
# clean native function-calls. Observed failure modes: stray chat-template
# wrappers leaking into content (``<|tool_call_start|>…``), JSON objects
# with trailing commas / single quotes / python-style literals, or
# half-formed calls. The rules here:
#   - never crash on any input
#   - never invent a tool call or a tool RESULT from noise: a call is
#     recovered only when a tool name is unambiguously present
#   - whatever cannot be recovered stays (or becomes) ordinary reply text,
#     with wrapper tokens stripped so model plumbing never reaches a human.

_TOOL_CALL_MARKERS = (
    "<|tool_call_start|>",
    "<|tool_call_end|>",
    "<|tool_calls|>",
    "<|tool_call|>",
    "<tool_response>",
    "<|fim_middle|>",
    "<|end|>",
)


def _strip_markers(text: str) -> str:
    for marker in _TOOL_CALL_MARKERS:
        text = text.replace(marker, " ")
    return text


def _balance_json(text: str) -> str:
    """Close unbalanced braces/brackets left by a truncated generation.

    String-aware, so a '{' inside a quoted value does not confuse the
    balance. Best effort: if quoting is itself broken we fall back to a
    naive count — the downstream json.loads still gets the final word.
    """
    open_stack: list[str] = []
    in_string = False
    escaped = False
    naive = 0
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            open_stack.append(ch)
        elif ch in "}]":
            if open_stack:
                open_stack.pop()
            else:
                naive += 1
    repaired = text
    if in_string:
        repaired += '"'
    for opener in reversed(open_stack):
        repaired += "}" if opener == "{" else "]"
    return repaired


def _lenient_json_loads(raw: Any) -> Any:
    """json.loads with a small, bounded repair ladder for model output.

    Returns None when nothing parses — callers must treat None as
    "no recoverable call", never as an empty-argument call.
    """
    if isinstance(raw, (dict, list)):
        return raw
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    # Keep only the first balanced JSON object when prose surrounds it.
    start = text.find("{")
    if start > 0:
        text = text[start:]
    attempts = [
        text,
        re.sub(r",\s*([}\]])", r"\1", text),  # trailing commas
        _balance_json(re.sub(r",\s*([}\]])", r"\1", text)),  # + truncation
    ]
    for candidate in attempts:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:  # nosec B112  # one more parse strategy; none parsed, so try the next
            continue
    # Last resort: python-ish literals (single quotes, True/None). ast is
    # safe here — it evaluates literals only, never expressions.
    import ast

    try:
        parsed = ast.literal_eval(_balance_json(text))
        if isinstance(parsed, dict):
            return parsed
    except Exception:  # nosec B110  # a parse that did not yield an object is simply not JSON
        pass
    return None


def _coerce_tool_call(obj: Any) -> dict[str, Any] | None:
    """Normalize one recovered JSON object into an OpenAI-style tool call.

    Accepts the shapes small models actually emit::

        {"name": "...", "arguments": {...} | "..."}
        {"function": {"name": "...", "arguments": ...}}
        {"tool": "...", "args": {...}}

    Returns None unless a non-empty string tool name is present. No name,
    no call — we never guess one.
    """
    if not isinstance(obj, dict):
        return None
    name = None
    args: Any = {}
    if isinstance(obj.get("function"), dict):
        name = obj["function"].get("name")
        args = obj["function"].get("arguments", {})
    if not isinstance(name, str) or not name.strip():
        for key in ("name", "tool", "tool_name"):
            candidate = obj.get(key)
            if isinstance(candidate, str) and candidate.strip():
                name = candidate
                break
    if not isinstance(name, str) or not name.strip():
        return None
    for key in ("arguments", "args", "parameters", "inputs"):
        if key in obj:
            args = obj[key]
            break
    if args is None:
        args = {}
    if not isinstance(args, str):
        try:
            args = json.dumps(args)
        except (TypeError, ValueError):
            args = json.dumps({})
    return {
        "id": "",  # assigned by the caller (stable per response)
        "type": "function",
        "function": {"name": name.strip(), "arguments": args},
    }


def _split_objects(text: str) -> list[str]:
    """Split raw text into candidate top-level {...} chunks (string-aware)."""
    chunks: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    chunks.append(text[start : i + 1])
    if depth > 0 and start >= 0:
        chunks.append(text[start:])  # truncated tail; balancer handles it
    return chunks


def lenient_tool_calls(content: str) -> tuple[list[dict[str, Any]], str]:
    """Recover tool calls from raw model text.

    Returns ``(tool_calls, remaining_text)`` where tool_calls are
    OpenAI-style (``function.arguments`` is always a JSON string) and
    remaining_text is the visible reply with call syntax and wrapper
    tokens removed. Plain prose passes through untouched; unrecoverable
    call attempts degrade to text. Never raises.
    """
    if not isinstance(content, str) or not content:
        return [], content if isinstance(content, str) else ""
    has_marker = any(m in content for m in _TOOL_CALL_MARKERS)
    looks_like_call = (
        '"name"' in content or '"function"' in content or '"tool"' in content
    )
    if not has_marker and not looks_like_call:
        return [], content  # fast path: ordinary prose, byte-identical

    calls: list[dict[str, Any]] = []
    remaining = content
    if has_marker:
        # Prefer explicit wrapper segments when the model used them.
        segments = re.split(
            r"<\|tool_call_start\|>|<\|tool_call\|>|<tool_response>", remaining
        )
        kept: list[str] = [segments[0]]
        for seg in segments[1:]:
            for end_marker in (
                "<|tool_call_end|>",
                "<|fim_middle|>",
                "<|end|>",
                "</tool_response>",
            ):
                if end_marker in seg:
                    inner, _, after = seg.partition(end_marker)
                    kept.append(after)
                    seg = inner
                    break
            else:
                kept.append("")
            for chunk in _split_objects(seg):
                call = _coerce_tool_call(_lenient_json_loads(chunk))
                if call:
                    calls.append(call)
                    seg = seg.replace(chunk, " ", 1)
            # Whatever did not parse inside a call segment is noise from
            # the model plumbing, not prose for the human: drop it, but
            # keep any recovered call.
        remaining = "\n".join(part for part in kept if part and part.strip())
    if not calls:
        # Marker-free but call-shaped text (or nothing recovered above):
        # try each balanced JSON chunk in the remaining text.
        for chunk in _split_objects(remaining):
            call = _coerce_tool_call(_lenient_json_loads(chunk))
            if call:
                calls.append(call)
                remaining = remaining.replace(chunk, " ", 1)
    for i, call in enumerate(calls):
        if not call.get("id"):
            call["id"] = f"lenient-{i}"
    remaining = _strip_markers(remaining)
    remaining = re.sub(r"[ \t]{2,}", " ", remaining)
    remaining = re.sub(r"\n{3,}", "\n\n", remaining).strip()
    if not remaining and not calls:
        remaining = _strip_markers(content).strip()
    return calls, remaining


def _tool_response(
    message: dict[str, Any],
    model: str,
    extra: dict[str, Any] | None = None,
) -> Result:
    """Shared finalizer for chat_with_tools implementations.

    Native tool_calls win. Otherwise the content goes through lenient
    small-model parsing: recovered calls are returned as tool_calls,
    plain (or cleaned) text is returned as the reply. An empty response
    with nothing recoverable stays a failure.
    """
    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        return ok(
            "healthy",
            data={"tool_calls": tool_calls, "model": model, **(extra or {})},
        )
    content = (message.get("content") or "").strip()
    recovered, remaining = lenient_tool_calls(content)
    if recovered:
        data: dict[str, Any] = {"tool_calls": recovered, "model": model}
        if remaining:
            data["reply"] = remaining
        data.update(extra or {})
        return ok("healthy", data=data)
    if not remaining:
        return Result(ok=False, status="unavailable", warnings=["empty reply"])
    return ok("healthy", data={"reply": remaining, "model": model, **(extra or {})})


class ChatContract:
    """Provider-neutral conversation contract."""

    def health(self) -> Result:
        """Cheap reachability probe. Contract entry point used by
        registry health_check lambdas; default to observe()."""
        return self.observe()

    def chat(self, messages: list[dict[str, str]]) -> Result:
        raise NotImplementedError

    def observe(self) -> Result:
        raise NotImplementedError

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Result:
        """Tool-calling round-trip. ONE contract shape for every provider:
        ``data.reply`` (final text) or ``data.tool_calls`` (OpenAI-style
        calls the loop executes through the ToolRegistry).

        Default implementation for providers without a native tools
        parameter (e.g. the OpenCode CLI, which runs its own internal
        loop): fall back to ``chat()`` and recover any tool-call syntax
        the model leaked into text with the lenient parser. Providers
        with native function-calling override this.
        """
        try:
            result = self.chat(messages)
        except Exception as e:  # never let a provider crash reach the API
            return Result(
                ok=False,
                status="unavailable",
                warnings=[f"chat provider failed: {e}"],
            )
        if not result.ok:
            return result
        data = result.data or {}
        if data.get("tool_calls"):
            return result
        reply = data.get("reply") or ""
        calls, remaining = lenient_tool_calls(reply)
        if not calls:
            return result
        updated = {**data, "tool_calls": calls}
        if remaining:
            updated["reply"] = remaining
        else:
            updated.pop("reply", None)
        return ok("healthy", data=updated)


class OllamaChat(ChatContract):
    """Chat over Ollama's native /api/chat."""

    def __init__(
        self, base_url: str, model: str, timeout: int = CHAT_TIMEOUT_SECONDS
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.display_name = f"Ollama ({model})"

    def observe(self) -> Result:
        try:
            with http_urlopen(f"{self.base_url}/api/tags", timeout=5) as resp:
                payload = json.loads(resp.read().decode())
            models = [m.get("name", "") for m in payload.get("models", [])]
            present = any(
                m == self.model or m.split(":")[0] == self.model for m in models
            )
            if not present:
                return fail(
                    "unhealthy",
                    data={"base_url": self.base_url, "model": self.model},
                    warnings=[f"model '{self.model}' not in local library"],
                )
            return ok(
                "healthy",
                data={"base_url": self.base_url, "model": self.model, "models": models},
            )
        except Exception as e:
            return Result(ok=False, status="unavailable", warnings=[f"ollama: {e}"])

    def chat(self, messages: list[dict[str, str]]) -> Result:
        body = json.dumps(
            {"model": self.model, "messages": messages, "stream": False}
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with http_urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except Exception as e:
            return Result(
                ok=False, status="unavailable", warnings=[f"ollama chat: {e}"]
            )
        message = payload.get("message") or {}
        content = (message.get("content") or "").strip()
        if not content:
            return Result(
                ok=False,
                status="unavailable",
                warnings=["ollama returned an empty reply"],
            )
        return ok(
            "healthy",
            data={
                "reply": content,
                "thinking": message.get("thinking"),
                "model": payload.get("model", self.model),
            },
        )

    def chat_with_tools(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> Result:
        """Native Ollama function-calling (``tools`` on /api/chat).

        Small local models frequently emit call syntax as text instead
        of native tool_calls, so the response also goes through the
        lenient parser in ``_tool_response`` — stray
        ``<|tool_call_start|>`` wrappers and malformed JSON are
        recovered or degraded to text, never a crash and never
        an invented result.
        """
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            body["tools"] = tools
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with http_urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except Exception as e:
            return Result(
                ok=False, status="unavailable", warnings=[f"ollama chat: {e}"]
            )
        message = payload.get("message") or {}
        return _tool_response(
            message,
            payload.get("model", self.model),
            extra={"thinking": message.get("thinking")},
        )


class OpenAICompatChat(ChatContract):
    """Chat over any OpenAI-compatible /v1/chat/completions endpoint."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key_env: str | None = None,
        timeout: int = CHAT_TIMEOUT_SECONDS,
        display_name: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.display_name = display_name or f"OpenAI-compat ({model})"

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key_env and os.environ.get(self.api_key_env):
            h["Authorization"] = f"Bearer {os.environ[self.api_key_env]}"
        return h

    def observe(self) -> Result:
        try:
            # Don't double-append /v1 if base_url already ends with it
            base = self.base_url.rstrip("/")
            if base.endswith("/v1"):
                url = f"{base}/models"
            else:
                url = f"{base}/v1/models"
            req = urllib.request.Request(url, headers=self._headers())
            with http_urlopen(req, timeout=5) as resp:
                payload = json.loads(resp.read().decode())
            ids = [m.get("id", "") for m in payload.get("data", [])]
            present = self.model in ids if ids else True
            if not present:
                return fail(
                    "unhealthy",
                    data={"base_url": self.base_url, "model": self.model},
                    warnings=[f"model '{self.model}' not offered by endpoint"],
                )
            return ok(
                "healthy",
                data={"base_url": self.base_url, "model": self.model, "models": ids},
            )
        except Exception as e:
            return Result(
                ok=False, status="unavailable", warnings=[f"openai-compat: {e}"]
            )

    def chat(self, messages: list[dict[str, str]]) -> Result:
        # No "stream" flag: the OpenAI chat-completions API is
        # non-streaming by default, so it was never sent.
        body = json.dumps({"model": self.model, "messages": messages}).encode()
        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            url = f"{base}/chat/completions"
        else:
            url = f"{base}/v1/chat/completions"
        req = urllib.request.Request(
            url, data=body, headers=self._headers(), method="POST"
        )
        try:
            with http_urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except Exception as e:
            return Result(
                ok=False, status="unavailable", warnings=[f"openai-compat chat: {e}"]
            )
        choices = payload.get("choices") or []
        content = ""
        if choices:
            content = ((choices[0].get("message") or {}).get("content") or "").strip()
        if not content:
            return Result(
                ok=False,
                status="unavailable",
                warnings=["endpoint returned an empty reply"],
            )
        return ok(
            "healthy",
            data={
                "reply": content,
                "thinking": None,
                "model": payload.get("model", self.model),
            },
        )

    def chat_with_tools(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> Result:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            body["tools"] = tools
        data = json.dumps(body).encode()
        base = self.base_url.rstrip("/")
        url = (
            f"{base}/v1/chat/completions"
            if not base.endswith("/v1")
            else f"{base}/chat/completions"
        )
        req = urllib.request.Request(
            url, data=data, headers=self._headers(), method="POST"
        )
        try:
            with http_urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except Exception as e:
            return Result(
                ok=False, status="unavailable", warnings=[f"openai-compat: {e}"]
            )
        choices = payload.get("choices") or []
        if not choices:
            return Result(
                ok=False, status="unavailable", warnings=["no choices returned"]
            )
        message = choices[0].get("message") or {}
        return _tool_response(message, payload.get("model", self.model))


class OpenAIChat(ChatContract):
    """Chat with OpenAI's API directly (GPT-4, GPT-4o, etc.)."""

    def __init__(
        self,
        model: str,
        api_key_env: str = "OPENAI_API_KEY",
        timeout: int = CHAT_TIMEOUT_SECONDS,
    ) -> None:
        self.model = model
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.display_name = f"OpenAI ({model})"

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        key = os.environ.get(self.api_key_env)
        if key:
            h["Authorization"] = f"Bearer {key}"
        return h

    def observe(self) -> Result:
        key = os.environ.get(self.api_key_env)
        if not key:
            return fail("unavailable", warnings=[f"{self.api_key_env} not set"])
        try:
            req = urllib.request.Request(
                "https://api.openai.com/v1/models", headers=self._headers()
            )
            with http_urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode())
            ids = [m.get("id", "") for m in payload.get("data", [])]
            present = any(self.model in m for m in ids)
            if not present:
                return fail(
                    "unhealthy", warnings=[f"model '{self.model}' not available"]
                )
            return ok(
                "healthy", data={"model": self.model, "available_models": len(ids)}
            )
        except Exception as e:
            return Result(ok=False, status="unavailable", warnings=[f"openai: {e}"])

    def chat(self, messages: list[dict[str, str]]) -> Result:
        body = json.dumps({"model": self.model, "messages": messages}).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers=self._headers(),
            method="POST",
        )
        try:
            with http_urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except Exception as e:
            return Result(
                ok=False, status="unavailable", warnings=[f"openai chat: {e}"]
            )
        choices = payload.get("choices") or []
        content = ""
        if choices:
            content = ((choices[0].get("message") or {}).get("content") or "").strip()
        if not content:
            return Result(
                ok=False,
                status="unavailable",
                warnings=["openai returned an empty reply"],
            )
        return ok(
            "healthy",
            data={
                "reply": content,
                "thinking": None,
                "model": payload.get("model", self.model),
            },
        )

    def chat_with_tools(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> Result:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            body["tools"] = tools
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers=self._headers(),
            method="POST",
        )
        try:
            with http_urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except Exception as e:
            return Result(ok=False, status="unavailable", warnings=[f"openai: {e}"])
        choices = payload.get("choices") or []
        if not choices:
            return Result(ok=False, status="unavailable", warnings=["no choices"])
        message = choices[0].get("message") or {}
        tool_calls = message.get("tool_calls")
        if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
            return ok(
                "healthy",
                data={
                    "tool_calls": tool_calls,
                    "model": payload.get("model", self.model),
                },
            )
        content = (message.get("content") or "").strip()
        if not content:
            return Result(ok=False, status="unavailable", warnings=["empty reply"])
        return ok(
            "healthy",
            data={"reply": content, "model": payload.get("model", self.model)},
        )


class AnthropicChat(ChatContract):
    """Chat with Anthropic's Claude API."""

    def __init__(
        self,
        model: str,
        api_key_env: str = "ANTHROPIC_API_KEY",
        timeout: int = CHAT_TIMEOUT_SECONDS,
    ) -> None:
        self.model = model
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.display_name = f"Claude ({model})"

    def _headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        key = os.environ.get(self.api_key_env)
        if key:
            h["x-api-key"] = key
        return h

    def observe(self) -> Result:
        key = os.environ.get(self.api_key_env)
        if not key:
            return fail("unavailable", warnings=[f"{self.api_key_env} not set"])
        return ok("healthy", data={"model": self.model, "provider": "anthropic"})

    def chat(self, messages: list[dict[str, str]]) -> Result:
        # Anthropic uses a different message format
        system = ""
        claude_messages = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                claude_messages.append({"role": m["role"], "content": m["content"]})

        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": claude_messages,
        }
        if system:
            body["system"] = system

        data = json.dumps(body).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=data,
            headers=self._headers(),
            method="POST",
        )
        try:
            with http_urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except Exception as e:
            return Result(
                ok=False, status="unavailable", warnings=[f"claude chat: {e}"]
            )

        content_blocks = payload.get("content", [])
        text_parts = [
            b.get("text", "") for b in content_blocks if b.get("type") == "text"
        ]
        reply = "\n".join(text_parts).strip()
        if not reply:
            return Result(
                ok=False,
                status="unavailable",
                warnings=["claude returned an empty reply"],
            )
        return ok(
            "healthy",
            data={
                "reply": reply,
                "thinking": None,
                "model": payload.get("model", self.model),
            },
        )

    def chat_with_tools(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> Result:
        system = ""
        claude_messages = []

        def _arguments(tc: dict[str, Any]) -> dict[str, Any]:
            """OpenAI-style tool_call arguments (a JSON string) rendered
            as Anthropic's tool_use input object."""
            raw = tc.get("function", {}).get("arguments")
            if isinstance(raw, dict):
                return raw
            if isinstance(raw, str) and raw:
                try:
                    parsed = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return {}
                return parsed if isinstance(parsed, dict) else {}
            return {}

        for m in messages:
            if m.get("role") == "system":
                system = m.get("content", "")
            elif m.get("role") == "tool":
                claude_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.get("tool_call_id", ""),
                                "content": m.get("content", ""),
                            }
                        ],
                    }
                )
            elif m.get("role") == "assistant" and m.get("tool_calls"):
                # Replayed assistant turns must carry their tool_use
                # blocks, or Anthropic rejects the loop (tool_result
                # without a preceding tool_use is a protocol error).
                blocks = [
                    {
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": tc.get("function", {}).get("name", ""),
                        "input": _arguments(tc),
                    }
                    for tc in m["tool_calls"]
                    if isinstance(tc, dict)
                ]
                text = m.get("content", "")
                if isinstance(text, str) and text:
                    blocks = [{"type": "text", "text": text}, *blocks]
                claude_messages.append({"role": "assistant", "content": blocks})
            else:
                claude_messages.append(
                    {"role": m["role"], "content": m.get("content", "")}
                )

        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": claude_messages,
        }
        if system:
            body["system"] = system
        if tools:
            anthropic_tools = []
            for t in tools:
                func = t.get("function", {})
                anthropic_tools.append(
                    {
                        "name": func.get("name", ""),
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {}),
                    }
                )
            body["tools"] = anthropic_tools

        data = json.dumps(body).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=data,
            headers=self._headers(),
            method="POST",
        )
        try:
            with http_urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except Exception as e:
            return Result(ok=False, status="unavailable", warnings=[f"anthropic: {e}"])

        content_blocks = payload.get("content", [])
        tool_uses = [b for b in content_blocks if b.get("type") == "tool_use"]
        if tool_uses:
            tool_calls = []
            for tu in tool_uses:
                tool_calls.append(
                    {
                        "function": {
                            "name": tu.get("name", ""),
                            "arguments": json.dumps(tu.get("input", {})),
                        },
                        "id": tu.get("id", ""),
                    }
                )
            return ok(
                "healthy",
                data={
                    "tool_calls": tool_calls,
                    "model": payload.get("model", self.model),
                },
            )

        text_parts = [
            b.get("text", "") for b in content_blocks if b.get("type") == "text"
        ]
        reply = "\n".join(text_parts).strip()
        if not reply:
            return Result(ok=False, status="unavailable", warnings=["empty reply"])
        return ok(
            "healthy", data={"reply": reply, "model": payload.get("model", self.model)}
        )


class OpenCodeChat(ChatContract):
    """Chat via OpenCode Go CLI (opencode run).

    Uses the opencode CLI to send messages to any model available
    through OpenCode Go's provider system. This is the simplest
    integration — no API server needed, just the CLI binary.

    Tool-calling: the CLI runs its own internal agent loop and accepts
    no tools parameter, so ``chat_with_tools`` is the ChatContract
    default — ``chat()`` plus lenient recovery of any tool-call syntax
    the model leaks into its text.
    """

    def __init__(
        self, model: str = "opencode-go/mimo-v2.5", timeout: int = CHAT_TIMEOUT_SECONDS
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.display_name = f"OpenCode ({model.split('/')[-1]})"

    def observe(self) -> Result:
        try:
            proc = subprocess.run(  # nosec  # B603 and B607 both apply to this call — argument list, no shell; `opencode` is the operator's own CLI on PATH
                ["opencode", "models"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode != 0:
                return fail("unavailable", warnings=["opencode CLI not working"])
            models = proc.stdout.strip().split("\n")
            present = any(self.model in m for m in models)
            if not present:
                return fail(
                    "unhealthy",
                    warnings=[f"model '{self.model}' not found in opencode"],
                )
            return ok("healthy", data={"model": self.model, "available": len(models)})
        except FileNotFoundError:
            return fail("unavailable", warnings=["opencode CLI not installed"])
        except Exception as e:
            return Result(ok=False, status="unavailable", warnings=[f"opencode: {e}"])

    def chat(self, messages: list[dict[str, str]]) -> Result:
        # Build the prompt from messages
        prompt_parts = []
        for m in messages:
            if m["role"] == "system":
                prompt_parts.append(f"System: {m['content']}")
            elif m["role"] == "user":
                prompt_parts.append(m["content"])
            elif m["role"] == "assistant":
                prompt_parts.append(f"Assistant: {m['content']}")
        prompt = "\n\n".join(prompt_parts)

        try:
            proc = subprocess.run(  # nosec  # B603 and B607 both apply to this call — argument list, no shell; `opencode` is the operator's own CLI on PATH
                ["opencode", "run", "--model", self.model, "--format", "json"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return Result(
                ok=False, status="unavailable", warnings=["opencode timed out"]
            )
        except FileNotFoundError:
            return Result(
                ok=False, status="unavailable", warnings=["opencode CLI not installed"]
            )
        except Exception as e:
            return Result(
                ok=False, status="unavailable", warnings=[f"opencode run failed: {e}"]
            )

        if proc.returncode != 0:
            return Result(
                ok=False,
                status="unavailable",
                warnings=[f"opencode exited {proc.returncode}: {proc.stderr[:200]}"],
            )

        # Parse JSON events from stdout
        reply = ""
        thinking = None
        model_used = self.model
        for line in proc.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "text":
                text = event.get("part", {}).get("text", "")
                if text:
                    reply += text

        reply = reply.strip()
        if not reply:
            return Result(
                ok=False, status="unavailable", warnings=["opencode returned no text"]
            )

        return ok(
            "healthy",
            data={
                "reply": reply,
                "thinking": thinking,
                "model": model_used,
            },
        )


# --- Provider registry ---

_PROVIDER_BUILDERS: dict[str, type[ChatContract]] = {
    "ollama": OllamaChat,
    "openai_compat": OpenAICompatChat,
    "openai": OpenAIChat,
    "anthropic": AnthropicChat,
    "opencode": OpenCodeChat,
}


def build_chat_provider(connection: dict[str, Any]) -> tuple[str, ChatContract] | None:
    """Construct a chat provider from one connections.json entry."""
    ptype = connection.get("type")
    name = connection.get("name")
    base = connection.get("base_url")
    model = connection.get("model")

    if ptype == "ollama":
        if not base or not model:
            return None
        timeout = int(connection.get("timeout") or CHAT_TIMEOUT_SECONDS)
        return name or "ollama", OllamaChat(base, model, timeout=timeout)

    if ptype == "openai_compat":
        if not base or not model:
            return None
        timeout = int(connection.get("timeout") or CHAT_TIMEOUT_SECONDS)
        impl = OpenAICompatChat(
            base,
            model,
            connection.get("api_key_env"),
            timeout=timeout,
            display_name=connection.get("display_name"),
        )
        return name or "openai-compat", impl

    if ptype == "openai":
        if not model:
            return None
        timeout = int(connection.get("timeout") or CHAT_TIMEOUT_SECONDS)
        impl = OpenAIChat(
            model, connection.get("api_key_env", "OPENAI_API_KEY"), timeout=timeout
        )
        return name or "openai", impl

    if ptype == "anthropic":
        if not model:
            return None
        timeout = int(connection.get("timeout") or CHAT_TIMEOUT_SECONDS)
        impl = AnthropicChat(
            model, connection.get("api_key_env", "ANTHROPIC_API_KEY"), timeout=timeout
        )
        return name or "anthropic", impl

    if ptype == "opencode":
        model = connection.get("model", "opencode-go/mimo-v2.5")
        timeout = int(connection.get("timeout") or CHAT_TIMEOUT_SECONDS)
        impl = OpenCodeChat(model, timeout=timeout)
        return name or "opencode", impl

    return None
