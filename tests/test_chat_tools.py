"""Tool-calling chat loop + lenient small-model parsing + first-class
brain templates (decision #18, ORPH-03).

Contract under test:
- ONE chat loop (``chat_with_tools_loop``) shared by every live
  provider class through the ChatContract — native tool_calls and the
  text-recovery default both flow through it
- lenient parsing for a 1.7B brain: stray ``<|tool_call_start|>``
  wrappers and malformed JSON are recovered or degraded to honest
  text; nothing ever crashes; tool RESULTS are never invented
  (unrecoverable arguments produce an invalid_args result and the tool
  is not invoked)
- write-safety stays structural: execution tools are not exposed in
  schemas and are refused by the registry even when the model asks
- templates load from config/prompts/{core,personas,surfaces,tasks,
  formats}, compose with persona support, and are discoverable
  read-only through GET /api/templates {id, surface, role, description}
"""

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personal_world.chat import (  # noqa: E402
    PARTIAL_FINDINGS_MAX,
    PARTIAL_SUMMARY_CHARS,
    build_chat_messages,
    chat_with_tools_loop,
)
from personal_world.chat_registry import (  # noqa: E402
    ChatContract,
    OllamaChat,
    OpenAIChat,
    OpenAICompatChat,
    lenient_tool_calls,
)
from personal_world.envelope import Result, ok  # noqa: E402
from personal_world.tool_registry import Tool, ToolRegistry  # noqa: E402

REPO = Path(__file__).parent.parent


# ── helpers ──────────────────────────────────────────────────────────


class StubProvider(ChatContract):
    """Scripted provider: each chat_with_tools call pops the next
    response. Records every message list it was shown."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []

    def observe(self):
        return ok("healthy", data={})

    def chat(self, messages):
        return ok("healthy", data={"reply": "stub", "model": "stub"})

    def chat_with_tools(self, messages, tools=None):
        self.seen.append([dict(m) for m in messages])
        item = self.script.pop(0) if self.script else {"reply": "done"}
        if isinstance(item, Exception):
            raise item
        return ok("healthy", data={"model": "stub", **item})


def _tool_call(name, args, call_id="call-1"):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


def _registry():
    reg = ToolRegistry()
    calls = []

    def handler(x):
        calls.append(x)
        return ok("healthy", data={"echo": x})

    reg.register(
        Tool(
            id="echo_tool",
            capability="test",
            operation="read",
            description="echo x",
            read_write="read",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "integer"}},
                "required": ["x"],
            },
            handler=handler,
        )
    )
    reg.register(
        Tool(
            id="execute_bad",
            capability="test",
            operation="execute",
            description="execution-class write tool",
            read_write="write",
            requires_step_up=True,
            parameters={"type": "object", "properties": {}},
            handler=lambda: ok("healthy", data={"mutated": True}),
        )
    )
    reg._test_calls = calls  # type: ignore[attr-defined]
    return reg


_MESSAGES = [{"role": "user", "content": "hi"}]


# ── 1. tool-calling round trip vs stub provider ─────────────────────


class TestToolLoopRoundTrip:
    def test_native_round_trip(self):
        reg = _registry()
        stub = StubProvider(
            [
                {"tool_calls": [_tool_call("echo_tool", {"x": 7})]},
                {"reply": "The echo was 7."},
            ]
        )
        result = chat_with_tools_loop(stub, _MESSAGES, reg, reg.list_ollama_schemas())
        assert result.ok
        assert result.data["reply"] == "The echo was 7."
        assert reg._test_calls == [7]  # the tool really ran
        made = result.data["tool_calls_made"]
        assert made == [
            {
                "tool": "echo_tool",
                "args": {"x": 7},
                "args_repaired": False,
                "ok": True,
                "status": "healthy",
            }
        ]
        # the stub saw the real tool result fed back as a tool message
        tool_msgs = [m for m in stub.seen[-1] if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["tool_call_id"] == "call-1"
        payload = json.loads(tool_msgs[0]["content"])
        assert payload["ok"] is True and payload["data"]["echo"] == 7

    def test_no_tools_is_plain_reply(self):
        stub = StubProvider([{"reply": "all calm"}])
        result = chat_with_tools_loop(stub, _MESSAGES, _registry(), [])
        assert result.ok and result.data["reply"] == "all calm"
        assert "tool_calls_made" not in (result.data or {})

    def test_max_rounds_terminates_honestly(self):
        """LANG-034: the loop-limit reply does not promise findings it
        does not include — the real, bounded tool payloads ship in
        `partial_findings`."""
        reg = _registry()
        stub = StubProvider(
            [{"tool_calls": [_tool_call("echo_tool", {"x": i})]} for i in range(10)]
        )
        result = chat_with_tools_loop(stub, _MESSAGES, reg, [], max_rounds=2)
        assert result.ok
        assert result.data["reply"] == (
            "I reached the lookup limit before I could finish. "
            "I can share the partial results or try a narrower question."
        )
        made = result.data["tool_calls_made"]
        assert len(made) == 2
        result.data["partial_findings"]
        # the partial findings are the REAL tool results, bounded
        assert len(made) == len(result.data["partial_findings"])
        assert all(f["tool"] == "echo_tool" for f in result.data["partial_findings"])
        assert any(f["summary"] for f in result.data["partial_findings"])

    def test_partial_findings_bounded(self):
        """The partial findings payload cannot exceed its caps
        (count and per-finding summary length)."""
        big = {"blob": "y" * 5000}
        calls_reg = ToolRegistry()
        calls_reg.register(
            Tool(
                id="echo_tool",
                capability="test",
                operation="read",
                description="echo x",
                read_write="read",
                parameters={
                    "type": "object",
                    "properties": {"x": {"type": "integer"}},
                    "required": ["x"],
                },
                handler=lambda x: ok("healthy", data=big),
            )
        )
        stub = StubProvider(
            [
                {"tool_calls": [_tool_call("echo_tool", {"x": i}, call_id=f"call-{i}")]}
                for i in range(10)
            ]
        )
        result = chat_with_tools_loop(stub, _MESSAGES, calls_reg, [], max_rounds=8)
        assert result.ok
        findings = result.data["partial_findings"]
        assert len(findings) <= PARTIAL_FINDINGS_MAX
        assert all(len(f["summary"]) <= PARTIAL_SUMMARY_CHARS for f in findings)

    def test_provider_crash_never_propagates(self):
        stub = StubProvider([RuntimeError("socket exploded")])
        result = chat_with_tools_loop(stub, _MESSAGES, _registry(), [])
        assert not result.ok and result.status == "unavailable"
        assert any("chat provider failed" in w for w in result.warnings)

    def test_provider_failure_result_passes_through(self):
        class Down(ChatContract):
            def observe(self):
                return ok("healthy", data={})

            def chat_with_tools(self, messages, tools=None):
                return Result(ok=False, status="unavailable", warnings=["model down"])

        result = chat_with_tools_loop(Down(), _MESSAGES, _registry(), [])
        assert not result.ok and result.status == "unavailable"


# ── 2. lenient parsing: never crash, never invent results ───────────


class TestLenientArguments:
    def test_malformed_arguments_are_not_invented(self):
        reg = _registry()
        stub = StubProvider(
            [
                {"tool_calls": [_tool_call("echo_tool", None)]},
                {"reply": "sorry"},
            ]
        )
        # arguments the model mangled beyond recovery: the tool is NOT
        # invoked with made-up defaults; an honest invalid_args goes back
        stub.script[0]["tool_calls"][0]["function"]["arguments"] = "{{{nope"
        result = chat_with_tools_loop(stub, _MESSAGES, reg, [])
        assert result.ok
        assert reg._test_calls == []  # never invoked
        made = result.data["tool_calls_made"][0]
        assert made["status"] == "invalid_args" and made["ok"] is False
        tool_msg = [m for m in stub.seen[-1] if m.get("role") == "tool"][0]
        assert "malformed arguments" in tool_msg["content"]

    def test_trailing_comma_arguments_repaired(self):
        reg = _registry()
        stub = StubProvider(
            [
                {"tool_calls": [_tool_call("echo_tool", None)]},
                {"reply": "ok"},
            ]
        )
        stub.script[0]["tool_calls"][0]["function"]["arguments"] = '{"x": 3,}'
        result = chat_with_tools_loop(stub, _MESSAGES, reg, [])
        assert result.ok
        assert reg._test_calls == [3]
        assert result.data["tool_calls_made"][0]["args_repaired"] is True

    def test_truncated_arguments_repaired(self):
        reg = _registry()
        stub = StubProvider(
            [
                {"tool_calls": [_tool_call("echo_tool", None)]},
                {"reply": "ok"},
            ]
        )
        stub.script[0]["tool_calls"][0]["function"]["arguments"] = '{"x": 5'
        result = chat_with_tools_loop(stub, _MESSAGES, reg, [])
        assert reg._test_calls == [5]
        assert result.data["tool_calls_made"][0]["args_repaired"] is True

    def test_dict_arguments_pass_through(self):
        reg = _registry()
        call = _tool_call("echo_tool", {"x": 1})
        call["function"]["arguments"] = {"x": 2}  # some stacks send dicts
        stub = StubProvider([{"tool_calls": [call]}, {"reply": "ok"}])
        chat_with_tools_loop(stub, _MESSAGES, reg, [])
        assert reg._test_calls == [2]


class TestLenientTextParsing:
    def test_plain_prose_untouched(self):
        calls, text = lenient_tool_calls("Everything is healthy. Nothing to do.")
        assert calls == []
        assert text == "Everything is healthy. Nothing to do."

    def test_well_formed_wrapped_call(self):
        raw = (
            '<|tool_call_start|>{"name": "read_journal", '
            '"arguments": {"count": 3}}<|tool_call_end|>'
        )
        calls, text = lenient_tool_calls(raw)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "read_journal"
        assert json.loads(calls[0]["function"]["arguments"]) == {"count": 3}
        assert "<|" not in text

    def test_prose_plus_wrapped_call_keeps_prose(self):
        raw = (
            "Let me check the journal.\n<|tool_call_start|>"
            '{"name": "read_journal", "arguments": {}}'
            "<|tool_call_end|>"
        )
        calls, text = lenient_tool_calls(raw)
        assert len(calls) == 1
        assert "Let me check the journal." in text
        assert "<|" not in text

    def test_malformed_json_in_wrapper_recovered(self):
        raw = (
            "<|tool_call_start|>{'name': 'inspect_world_status', "
            "'arguments': {},}<|tool_call_end|>"
        )
        calls, _ = lenient_tool_calls(raw)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "inspect_world_status"

    def test_truncated_call_recovered(self):
        raw = '<|tool_call_start|>{"name": "read_journal", "arguments": {"count": 2}'
        calls, _ = lenient_tool_calls(raw)
        assert len(calls) == 1
        assert json.loads(calls[0]["function"]["arguments"]) == {"count": 2}

    def test_bare_json_call_without_wrapper(self):
        calls, _ = lenient_tool_calls(
            '{"name": "read_journal", "arguments": {"count": 1}}'
        )
        assert len(calls) == 1

    def test_openai_function_shape(self):
        calls, _ = lenient_tool_calls(
            '{"function": {"name": "search_journal", "arguments": {"query": "backup"}}}'
        )
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "search_journal"

    def test_unrecoverable_call_degrades_to_text_without_markers(self):
        raw = "<|tool_call_start|>hmm [tool()]<|tool_call_end|>All quiet."
        calls, text = lenient_tool_calls(raw)
        assert calls == []  # never invent a call from noise
        assert "<|" not in text
        assert "All quiet." in text

    def test_json_without_name_is_not_a_call(self):
        calls, _ = lenient_tool_calls('{"status": "healthy", "count": 3}')
        assert calls == []

    @pytest.mark.parametrize(
        "garbage",
        [
            "",
            "<|tool_call_start|>",
            "<|tool_call_start|><|tool_call_end|>",
            "<|tool_call_start|>{<|tool_call_end|>",
            '{"name": ',
            "<|fim_prefix|>\n\n</tool_response>",
            '{"name": 42, "arguments": []}',
            "<|tool_call_start|>" + "{" * 40,
        ],
    )
    def test_never_raises_on_garbage(self, garbage):
        calls, text = lenient_tool_calls(garbage)
        assert isinstance(calls, list)
        assert isinstance(text, str)
        for call in calls:
            assert call["function"]["name"]


# ── 3. provider classes: one coherent chat_with_tools ───────────────


class _FakeHTTPResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _fake_urlopen(monkeypatch, payload):
    import urllib.request

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: _FakeHTTPResponse(payload)
    )


class TestProviderToolCalling:
    def test_ollama_native_tool_calls(self, monkeypatch):
        _fake_urlopen(
            monkeypatch,
            {
                "model": "qwen3:1.7b",
                "message": {
                    "tool_calls": [
                        {"function": {"name": "read_journal", "arguments": {}}}
                    ]
                },
            },
        )
        r = OllamaChat("http://127.0.0.1:11434", "qwen3:1.7b").chat_with_tools(
            _MESSAGES, [{"type": "function"}]
        )
        assert r.ok
        assert r.data["tool_calls"][0]["function"]["name"] == "read_journal"

    def test_ollama_wrapped_text_call_recovered(self, monkeypatch):
        _fake_urlopen(
            monkeypatch,
            {
                "model": "qwen3:1.7b",
                "message": {
                    "content": '<|tool_call_start|>{"name": "read_journal", '
                    '"arguments": {"count": 2}}<|tool_call_end|>'
                },
            },
        )
        r = OllamaChat("http://127.0.0.1:11434", "qwen3:1.7b").chat_with_tools(
            _MESSAGES
        )
        assert r.ok
        assert r.data["tool_calls"][0]["function"]["name"] == "read_journal"

    def test_ollama_plain_reply_with_thinking(self, monkeypatch):
        _fake_urlopen(
            monkeypatch,
            {
                "model": "qwen3:1.7b",
                "message": {"content": "All quiet.", "thinking": "hmm"},
            },
        )
        r = OllamaChat("http://127.0.0.1:11434", "qwen3:1.7b").chat_with_tools(
            _MESSAGES
        )
        assert r.ok and r.data["reply"] == "All quiet."
        assert r.data["thinking"] == "hmm"
        assert "tool_calls" not in r.data

    def test_ollama_empty_reply_stays_honest_failure(self, monkeypatch):
        _fake_urlopen(monkeypatch, {"message": {"content": "  "}})
        r = OllamaChat("http://127.0.0.1:11434", "m").chat_with_tools(_MESSAGES)
        assert not r.ok and r.status == "unavailable"

    def test_openai_compat_wrapped_text_call_recovered(self, monkeypatch):
        _fake_urlopen(
            monkeypatch,
            {
                "model": "lfm2.5",
                "choices": [
                    {
                        "message": {
                            "content": "<|tool_call_start|>"
                            '{"name": "inspect_lab_health", "arguments": {}}'
                            "<|tool_call_end|>"
                        }
                    }
                ],
            },
        )
        r = OpenAICompatChat("http://127.0.0.1:8080", "lfm2.5").chat_with_tools(
            _MESSAGES
        )
        assert r.ok
        assert r.data["tool_calls"][0]["function"]["name"] == "inspect_lab_health"

    def test_contract_default_recovers_from_text_only_provider(self):
        """Any provider without native tools (OpenCode CLI shape) gets
        the base chat_with_tools: chat() + lenient text recovery."""

        class TextOnly(ChatContract):
            def observe(self):
                return ok("healthy", data={})

            def chat(self, messages):
                return ok(
                    "healthy",
                    data={
                        "reply": "<|tool_call_start|>"
                        '{"name": "read_journal", "arguments": {}}'
                        "<|tool_call_end|>",
                        "model": "text-only",
                    },
                )

        r = TextOnly().chat_with_tools(_MESSAGES)
        assert r.ok
        assert r.data["tool_calls"][0]["function"]["name"] == "read_journal"

    def test_contract_default_passes_prose_through(self):
        class TextOnly(ChatContract):
            def observe(self):
                return ok("healthy", data={})

            def chat(self, messages):
                return ok("healthy", data={"reply": "Nothing needs attention."})

        r = TextOnly().chat_with_tools(_MESSAGES)
        assert r.ok and r.data["reply"] == "Nothing needs attention."
        assert "tool_calls" not in r.data

    def test_loop_end_to_end_with_text_only_provider(self):
        """Full round trip through the ONE loop with a provider that
        only leaks wrapped text calls — the small-model path."""
        reg = _registry()

        class LeakyText(ChatContract):
            def __init__(self):
                self.round = 0

            def observe(self):
                return ok("healthy", data={})

            def chat(self, messages):
                self.round += 1
                if self.round == 1:
                    return ok(
                        "healthy",
                        data={
                            "reply": "<|tool_call_start|>"
                            '{"name": "echo_tool", "arguments": {"x": 9}}'
                            "<|tool_call_end|>"
                        },
                    )
                tool_msg = [m for m in messages if m.get("role") == "tool"][-1]
                return ok(
                    "healthy",
                    data={"reply": f"tool said: {tool_msg['content'][:40]}"},
                )

        result = chat_with_tools_loop(LeakyText(), _MESSAGES, reg, [])
        assert result.ok
        assert reg._test_calls == [9]
        assert "tool said" in result.data["reply"]


# ── 4. write-safety stays structural ────────────────────────────────


class TestWriteSafety:
    def test_execution_tools_not_in_schemas(self):
        reg = _registry()
        names = [s["function"]["name"] for s in reg.list_ollama_schemas()]
        assert "echo_tool" in names
        assert "execute_bad" not in names

    def test_model_cannot_invoke_execution_tool(self):
        reg = _registry()
        stub = StubProvider(
            [
                {"tool_calls": [_tool_call("execute_bad", {})]},
                {"reply": "blocked, fine"},
            ]
        )
        result = chat_with_tools_loop(stub, _MESSAGES, reg, [])
        assert result.ok
        made = result.data["tool_calls_made"][0]
        assert made["status"] == "forbidden" and made["ok"] is False
        tool_msg = [m for m in stub.seen[-1] if m.get("role") == "tool"][0]
        assert "execution tool" in tool_msg["content"]


# ── 5. persona in the system prompt ─────────────────────────────────


class TestPersonaPrompt:
    def test_persona_leads_system_prompt(self):
        msgs = build_chat_messages(
            "hi", "ctx", persona="You speak as Mermaid, a shipmate."
        )
        system = msgs[0]["content"]
        assert system.startswith("You speak as Mermaid")
        # the built-in identity/truth floor always follows
        assert "ONLY the context" in system
        assert "PW-PROPOSAL journal_correction" in system

    def test_no_persona_keeps_floor(self):
        msgs = build_chat_messages("hi", "ctx")
        assert msgs[0]["content"].startswith("You are the Worlds assistant")


# ── 6. template loading + /api/templates shape ──────────────────────


class TestTemplateDiscovery:
    def test_shipped_tree_loads(self, tmp_path):
        from personal_world.template_registry import TemplateRegistry

        config = tmp_path / "config"
        config.mkdir()
        shutil.copytree(REPO / "config" / "prompts", config / "prompts")
        reg = TemplateRegistry(config, tmp_path)
        ids = {t["id"] for t in reg.list_templates()}
        assert "core.identity" in ids
        assert "core.truth-rules" in ids
        assert "surface.lab" in ids
        assert "task.inspect" in ids
        assert "persona.personal-world" in ids
        assert "persona.mermaid" in ids

    def test_public_shape(self, tmp_path):
        from personal_world.template_registry import TemplateRegistry

        config = tmp_path / "config"
        config.mkdir()
        shutil.copytree(REPO / "config" / "prompts", config / "prompts")
        reg = TemplateRegistry(config, tmp_path)
        rows = reg.list_public()
        assert rows, "shipped tree produced no public rows"
        for row in rows:
            assert set(row.keys()) == {"id", "surface", "role", "description"}
            assert isinstance(row["description"], str)
        lab = next(r for r in rows if r["id"] == "surface.lab")
        assert lab["role"] == "surface"
        assert lab["surface"] == "lab"
        assert lab["description"]
        identity = next(r for r in rows if r["id"] == "core.identity")
        assert identity["role"] == "core" and identity["surface"] is None

    def test_compose_includes_persona_and_surface(self, tmp_path):
        from personal_world.template_registry import TemplateRegistry

        config = tmp_path / "config"
        config.mkdir()
        shutil.copytree(REPO / "config" / "prompts", config / "prompts")
        reg = TemplateRegistry(config, tmp_path)
        out = reg.compose(surface="lab", persona="mermaid")
        assert "Mermaid" in out  # persona consumed
        assert "what needs attention" in out  # surface.lab consumed
        assert "Worlds assistant" in out  # core always
        # an unknown persona is a silent no-op, never an error
        assert reg.compose(persona="does-not-exist")

    def test_api_templates_endpoint(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        from personal_world.api import create_app

        config = tmp_path / "config"
        config.mkdir()
        shutil.copytree(REPO / "config" / "prompts", config / "prompts")
        monkeypatch.setenv("PW_API_TOKEN", "t")
        app = create_app(tmp_path, config)
        client = TestClient(app)
        headers = {"Authorization": "Bearer t"}

        r = client.get("/api/templates", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        rows = body["data"]["templates"]
        assert rows
        for row in rows:
            assert set(row.keys()) == {"id", "surface", "role", "description"}
        assert any(row["id"] == "core.identity" for row in rows)

        # read-only: no write verbs on the discovery surface
        assert client.post("/api/templates", headers=headers).status_code == 405
        assert client.put("/api/templates", headers=headers).status_code == 405
        assert client.delete("/api/templates", headers=headers).status_code == 405

        # auth-gated like every other API surface
        assert client.get("/api/templates").status_code in (401, 503)


# ── 8. request bodies: no `stream` flag where it was a no-op ────────
#
# The OpenAI chat-completions API is non-streaming by default, so the
# flag was never sent. Ollama's native /api/chat streams by default
# and MUST keep it, or the response stops being parseable JSON.


def _capturing_urlopen(monkeypatch, payload):
    """Patch the module's urlopen, recording each outgoing request body."""
    import personal_world.chat_registry as cr

    sent = []

    def fake(req, timeout=None):
        sent.append(json.loads(req.data.decode()))
        return _FakeHTTPResponse(payload)

    monkeypatch.setattr(cr, "http_urlopen", fake)
    return sent


_OPENAI_REPLY = {
    "model": "gpt-x",
    "choices": [{"message": {"content": "hello"}}],
}
_OLLAMA_REPLY = {"model": "qwen3:1.7b", "message": {"content": "hello"}}


class TestRequestBodyStreamFlag:
    def test_openai_compat_chat_sends_no_stream_flag(self, monkeypatch):
        sent = _capturing_urlopen(monkeypatch, _OPENAI_REPLY)
        r = OpenAICompatChat("http://127.0.0.1:8080", "m").chat(_MESSAGES)
        assert r.ok
        assert sent == [{"model": "m", "messages": _MESSAGES}]

    def test_openai_compat_tools_sends_no_stream_flag(self, monkeypatch):
        sent = _capturing_urlopen(monkeypatch, _OPENAI_REPLY)
        r = OpenAICompatChat("http://127.0.0.1:8080", "m").chat_with_tools(
            _MESSAGES, [{"type": "function"}]
        )
        assert r.ok
        assert "stream" not in sent[0]
        assert sent[0]["tools"] == [{"type": "function"}]

    def test_openai_chat_sends_no_stream_flag(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        sent = _capturing_urlopen(monkeypatch, _OPENAI_REPLY)
        r = OpenAIChat("gpt-x").chat(_MESSAGES)
        assert r.ok
        assert sent == [{"model": "gpt-x", "messages": _MESSAGES}]

    def test_openai_tools_sends_no_stream_flag(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        sent = _capturing_urlopen(monkeypatch, _OPENAI_REPLY)
        r = OpenAIChat("gpt-x").chat_with_tools(_MESSAGES)
        assert r.ok
        assert "stream" not in sent[0]

    def test_ollama_keeps_stream_false(self, monkeypatch):
        # Ollama's native endpoint streams by default: dropping the
        # flag would hand back newline-delimited JSON we cannot parse.
        sent = _capturing_urlopen(monkeypatch, _OLLAMA_REPLY)
        chat = OllamaChat("http://127.0.0.1:11434", "qwen3:1.7b")
        assert chat.chat(_MESSAGES).ok
        assert chat.chat_with_tools(_MESSAGES).ok
        assert [b["stream"] for b in sent] == [False, False]
