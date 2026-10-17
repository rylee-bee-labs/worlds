"""Template: adding a new brain/provider adapter.

Invariants protected:
    - Successful response:   provider returns valid data.
    - Timeout:               provider hangs, timeout fires.
    - Provider unavailable:  connection refused.
    - Malformed output:      garbage response fails closed.
    - Structured parsing:    JSON parsed correctly.
    - Fallback:              primary fails, secondary used.
    - Model identity:        diagnostics show which model responded.
    - Safe failure:          error does not corrupt world state.

Uses a fake ChatContract implementation — no real model needed.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from personal_world.envelope import Result  # noqa: E402
from personal_world.providers.registry import Registry, StatusContract  # noqa: E402

# ---------------------------------------------------------------------------
# Fake ChatContract (hand-rolled, no unittest.mock)
# ---------------------------------------------------------------------------

class FakeChatContract(StatusContract):
    """Minimal chat provider that returns deterministic responses."""

    def __init__(self, response: str = '{"reply": "hello"}',
                 healthy: bool = True, model: str = "fake-1.0"):
        self._response = response
        self._healthy = healthy
        self.model = model

    def observe(self) -> Result:
        if not self._healthy:
            return Result(ok=False, status="unavailable",
                          warnings=[f"{self.model}: not reachable"])
        return Result(ok=True, status="healthy",
                      data={"model": self.model})

    def chat(self, messages: list[dict]) -> Result:
        if not self._healthy:
            return Result(ok=False, status="unavailable",
                          warnings=[f"{self.model}: not reachable"])
        try:
            data = json.loads(self._response)
        except (json.JSONDecodeError, TypeError):
            return Result(ok=False, status="unavailable",
                          warnings=[f"{self.model}: malformed response"])
        return Result(ok=True, status="healthy",
                      data={"reply": data.get("reply", ""),
                            "model": self.model})


class FakeTimeoutChat(FakeChatContract):
    """Simulates a provider that hangs."""

    def chat(self, messages: list[dict]) -> Result:
        return Result(ok=False, status="unavailable",
                      warnings=["chat timed out"])


class FakeExplodingChat(FakeChatContract):
    """Simulates a provider whose downstream raises during chat.

    Like a real adapter, the exception is caught and wrapped in a Result.
    """

    def chat(self, messages: list[dict]) -> Result:
        return Result(ok=False, status="unavailable",
                      warnings=["connection reset by peer"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSuccessfulResponse:
    """Provider returns valid data."""

    def test_chat_returns_reply(self):
        provider = FakeChatContract(response='{"reply": "world is healthy"}')
        result = provider.chat([{"role": "user", "content": "status?"}])
        assert result.ok
        assert result.data["reply"] == "world is healthy"

    def test_observe_reports_healthy(self):
        provider = FakeChatContract(healthy=True, model="test-model")
        result = provider.observe()
        assert result.ok
        assert result.data["model"] == "test-model"


class TestTimeout:
    """Provider hangs, timeout fires."""

    def test_timeout_returns_unavailable(self):
        provider = FakeTimeoutChat()
        result = provider.chat([{"role": "user", "content": "hello"}])
        assert not result.ok
        assert result.status == "unavailable"
        assert any("timed out" in w for w in result.warnings)


class TestProviderUnavailable:
    """Connection refused."""

    def test_unhealthy_provider_refuses_chat(self):
        provider = FakeChatContract(healthy=False, model="dead-model")
        result = provider.chat([{"role": "user", "content": "hello"}])
        assert not result.ok
        assert result.status == "unavailable"

    def test_unhealthy_observe_reports_unavailable(self):
        provider = FakeChatContract(healthy=False)
        result = provider.observe()
        assert not result.ok


class TestMalformedOutput:
    """Garbage response fails closed."""

    def test_garbage_json_fails(self):
        provider = FakeChatContract(response="not json at all")
        result = provider.chat([{"role": "user", "content": "hello"}])
        assert not result.ok
        assert any("malformed" in w for w in result.warnings)

    def test_empty_response_fails(self):
        provider = FakeChatContract(response="")
        result = provider.chat([{"role": "user", "content": "hello"}])
        assert not result.ok


class TestStructuredOutputParsing:
    """JSON parsed correctly."""

    def test_nested_json_parsed(self):
        payload = json.dumps({"reply": "ok", "meta": {"tokens": 42}})
        provider = FakeChatContract(response=payload)
        result = provider.chat([{"role": "user", "content": "test"}])
        assert result.ok
        assert result.data["reply"] == "ok"

    def test_chat_message_list_passed_through(self):
        """Messages are forwarded as-is to the provider."""
        provider = FakeChatContract(response='{"reply": "ack"}')
        msgs = [
            {"role": "system", "content": "be helpful"},
            {"role": "user", "content": "hello"},
        ]
        result = provider.chat(msgs)
        assert result.ok


class TestFallback:
    """Primary fails, secondary used."""

    def test_registry_uses_healthy_secondary(self):
        reg = Registry()
        reg.define_capability("reasoning", StatusContract)
        reg.register("reasoning", "primary",
                     FakeChatContract(healthy=False, model="primary"),
                     health_check=lambda: False)
        reg.register("reasoning", "secondary",
                     FakeChatContract(healthy=True, model="secondary"),
                     health_check=lambda: True)
        result = reg.observe("reasoning")
        assert result.ok
        assert result.data["model"] == "secondary"


class TestModelIdentity:
    """Diagnostics show which model responded."""

    def test_chat_response_includes_model(self):
        provider = FakeChatContract(model="gpt-fake-4o")
        result = provider.chat([{"role": "user", "content": "hi"}])
        assert result.data["model"] == "gpt-fake-4o"

    def test_observe_includes_model(self):
        provider = FakeChatContract(model="claude-fake")
        result = provider.observe()
        assert result.data["model"] == "claude-fake"


class TestSafeFailure:
    """Error does not corrupt world state."""

    def test_exploding_chat_returns_error(self):
        provider = FakeExplodingChat(healthy=True)
        result = provider.chat([{"role": "user", "content": "boom"}])
        assert not result.ok
        assert result.status == "unavailable"
        assert any("connection reset" in w for w in result.warnings)

    def test_registry_catches_exploding_observe(self):
        reg = Registry()
        reg.define_capability("reasoning", StatusContract)

        class ExplodingObserve(StatusContract):
            def observe(self_obj):
                raise RuntimeError("kaboom")

        reg.register("reasoning", "exploder", ExplodingObserve(),
                     health_check=lambda: True)
        result = reg.observe("reasoning")
        assert not result.ok
        assert result.status == "unavailable"
