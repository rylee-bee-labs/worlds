import json

import pytest

from personal_world.worlds.config_store import ConfigStore
from personal_world.worlds.confinement import ConfinementError, RawResponse
from personal_world.worlds.models import Card, Provider, Request


class FakeSend:
    """Scriptable sender. responses: path -> RawResponse | ConfinementError | Exception | callable."""

    def __init__(self):
        self.responses = {}
        self.calls = []

    def __call__(self, provider, request, *, effect):
        self.calls.append((request.id, request.method, request.path, effect))
        item = self.responses.get(request.path)
        if callable(item):
            item = item()
        if isinstance(item, Exception):
            raise item
        return item if item is not None else ConfinementError("connection", "no script")

    def count(self, path=None):
        return len([c for c in self.calls if path is None or c[2] == path])


def ok(body, status=200):
    return RawResponse(status_code=status, headers={"content-type": "application/json"},
                       body=json.dumps(body).encode(), duration_ms=7)


@pytest.fixture
def send():
    return FakeSend()


@pytest.fixture
def store(tmp_path):
    s = ConfigStore(tmp_path / "cfg")
    s.save("provider", Provider(id="ref", name="Ref", kind="reference", base_url="http://127.0.0.1:9"))
    return s


def add_request(store, name="items", path="/items", **kw):
    store.save("request", Request(id=f"ref.{name}", provider="ref", path=path, **kw))


def add_card(store, cid="c1", request="ref.items", **kw):
    d = dict(id=cid, title="T", request=request, meaning={"concept": "stuff", "short": "short", "full": "full"})
    d.update(kw)
    store.save("card", Card(**d))
