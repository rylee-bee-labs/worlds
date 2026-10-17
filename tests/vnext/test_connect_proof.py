"""Synthetic, read-only, no-network proof of the Connect contract (docs/vnext/connect-contract.md, #329).

The contract is a MOCKUP: no ``/api/connect/v1`` route exists, and ``Auth.scope`` and ``Action.state``,
which it proposed, now exist (d-impl Steps 2-5). So this file proves the journey against the pieces that DO exist
(config store, runner, card service, confinement seam, dispatcher) and pins the one place the contract is still
ahead of the code (the "unscoped" label, build-plan Q2) as a strict ``xfail`` naming the missing piece. Nothing here
touches protected code, a real credential, a real URL or a socket: senders are fixtures, and the
confinement tests replace the dial functions with stubs for the length of the test.

Sol #158 conditions: 1 -> ``test_c1_*``, 2 -> ``test_c2_*``, 3 -> ``test_c3_*``, 4 -> ``test_c4_*`` and the journey.
The browser half of 4 (keyboard, 390px) is NOT RUN here; see docs/vnext/proof/c-proof.md.
"""
import json
import os

import pytest
from pydantic import ValidationError

from personal_world.worlds import confinement
from personal_world.worlds.cards import CardService, home_board_defs
from personal_world.worlds.config_store import ConfigInvalid, ConfigStore
from personal_world.worlds.confinement import ConfinementError, RawResponse
from personal_world.worlds.models import (
    Action,
    Auth,
    Board,
    BoardItem,
    Card,
    Network,
    Provider,
    Request,
    scope_allows,
    send_scoped,
)
from personal_world.worlds.room0 import valid_link
from personal_world.worlds.runner import Runner

SECRET_VALUE = "synthetic-not-a-real-secret-0000"   # exists only in this process's env, never in config
SECRET_REF = "env:SYNTH_CONNECT_TOKEN"
NOW = 1_800_000_000.0


class Clock:
    t = NOW

    def __call__(self):
        return self.t


class Fixture:
    """The synthetic provider. Records every call; answers from ``script`` (a RawResponse or ConfinementError)."""

    def __init__(self):
        self.calls = []
        self.script = None

    def __call__(self, provider, request, *, effect):
        self.calls.append({"method": request.method, "path": request.path, "effect": effect,
                           "secret_ref": provider.auth.secret_ref})
        return self.script


def ok(body):
    return RawResponse(status_code=200, headers={"content-type": "application/json"}, body=json.dumps(body).encode(),
                       duration_ms=5)


def connect(store, *, request_id="synth.health"):
    """Register a synthetic connection the way the contract says: reference only, one read, one card, one board."""
    store.save("provider", Provider(id="synth", name="Synthetic", kind="http", base_url="http://fixture.invalid",
                                    auth=Auth(type="bearer", secret_ref=SECRET_REF)))
    store.save("request", Request(id=request_id, provider="synth", method="GET", path="/health", ttl_s=0))
    store.save("card", Card(
        id="synth-health", title="Synthetic health", request=request_id, view="status",
        meaning={"concept": "health", "short": "Is the synthetic thing fine?"},
        fields=[{"path": "$.queue", "label": "Queue", "format": "number"}],
        status={"path": "$.status", "healthy": ["ok"], "needs_attention": ["warn"]}))
    store.save("board", Board(id="home", title="Home", home=True, items=[BoardItem(card="synth-health")]))


@pytest.fixture
def world(tmp_path):
    store = ConfigStore(tmp_path / "cfg")
    fx = Fixture()
    clock = Clock()
    runner = Runner(store, fx, clock=clock)
    return store, fx, clock, CardService(store, runner, clock=clock), tmp_path


# ---------------------------------------------------------------- the journey (also condition 4: read-only)

def test_journey_empty_to_disconnected_and_still_usable(world):
    store, fx, clock, cards, tmp_path = world
    os.environ["SYNTH_CONNECT_TOKEN"] = SECRET_VALUE
    try:
        # 1. empty Worlds
        assert list(store.iter_all()) == [] and home_board_defs(store) is None
        assert cards.build("synth-health") is None

        # 2. a connect fixture reached through a credential REFERENCE; the value is in env only
        connect(store)
        on_disk = "".join(p.read_text() for p in (tmp_path / "cfg").rglob("*.yaml"))
        assert SECRET_REF in on_disk and SECRET_VALUE not in on_disk

        # 3. one card rendered
        fx.script = ok({"status": "ok", "queue": 3})
        env = cards.build("synth-health")
        assert (env["source_state"], env["freshness"]) == ("healthy", "current")
        assert env["values"]["queue"] == {"text": "3", "raw": 3}
        assert [f["key"] for f in home_board_defs(store)["items"][0]["fields"]] == ["queue"]

        # 4. stale: the provider fails, last-good values stay but are labelled stale, never current
        fx.script = ConfinementError("timeout", "synthetic timeout")
        stale = cards.build("synth-health")
        assert (stale["source_state"], stale["freshness"]) == ("unavailable", "stale")
        assert stale["last_good_at"] is not None and stale["values"]["queue"]["text"] == "3"
        assert stale["evidence"]["error_class"] == "timeout"

        # 5. unknown: an unmapped status word is unknown, never healthy; a missing field is "unknown", never 0
        fx.script = ok({"status": "weird"})
        unknown = cards.build("synth-health")
        assert unknown["source_state"] == "unknown" and unknown["freshness"] == "current"
        assert unknown["values"]["queue"] == {"text": "unknown"}

        # 6. retry: the same read again, and the card recovers on its own evidence
        fx.script = ok({"status": "ok", "queue": 4})
        retried = cards.build("synth-health")
        assert (retried["source_state"], retried["freshness"]) == ("healthy", "current")
        assert retried["values"]["queue"]["text"] == "4"

        # 7. link out: a same-origin path survives, a cross-origin one is dropped (room0 rule 6, the only link rule in code)
        assert valid_link("/rooms/synth") == "/rooms/synth"
        assert valid_link("https://elsewhere.example/") is None and valid_link("//elsewhere.example/") is None

        # the secret VALUE is in no envelope; only the reference ever reached the sender
        blob = json.dumps([env, stale, unknown, retried, home_board_defs(store)])
        assert SECRET_VALUE not in blob and SECRET_REF not in blob
        assert {c["secret_ref"] for c in fx.calls} == {SECRET_REF}

        # 8. disconnect: refused while referenced, then removed in dependency order
        with pytest.raises(ConfigInvalid):
            store.delete("provider", "synth")
        before = len(fx.calls)
        store.delete("board", "home")
        store.delete("card", "synth-health")
        store.delete("request", "synth.health")
        store.delete("provider", "synth")

        # 9. the surface is still usable afterwards: empty again, nothing is sent, and a new connection works
        assert list(store.iter_all()) == [] and home_board_defs(store) is None
        assert cards.build("synth-health") is None
        assert Runner(store, fx, clock=clock).fetch("synth.health").error_class == "confinement_denied"
        assert len(fx.calls) == before
        connect(store)
        fx.script = ok({"status": "ok", "queue": 1})
        assert cards.build("synth-health")["source_state"] == "healthy"

        # read-only end to end: every call the whole journey made was a read GET
        assert fx.calls and all(c["effect"] == "read" and c["method"] == "GET" for c in fx.calls)
    finally:
        os.environ.pop("SYNTH_CONNECT_TOKEN", None)


# ---------------------------------------------------------------- condition 4: no write path

def test_c4_a_write_request_is_refused_before_the_sender(world):
    store, fx, _, cards, _ = world
    connect(store)
    store.save("request", Request(id="synth.change", provider="synth", method="POST", path="/change"))
    store.save("card", Card(id="synth-change", title="Change", request="synth.change",
                            meaning={"concept": "c", "short": "s"}))
    fx.script = ok({})
    env = cards.build("synth-change")
    assert env["evidence"]["error_class"] == "confinement_denied" and fx.calls == []


def test_c4_the_confinement_seam_refuses_a_mutating_read_effect():
    store_provider = Provider(id="synth", name="S", kind="http", base_url="http://fixture.invalid")
    req = Request(id="synth.change", provider="synth", method="DELETE", path="/x")
    out = confinement.confined_request(store_provider, req, effect="read",
                                       resolver=lambda *a, **k: pytest.fail("DNS must not be reached"))
    assert isinstance(out, ConfinementError) and out.error_class == "confinement_denied"


# ---------------------------------------------------------------- condition 3: scoped auth before the network

class _Dials:
    """Replace the two functions that put bytes on a socket; restored on exit, so nothing here can dial.

    Every call lands in ``dialed`` (the request path). The bearer path's calls also land in ``sent`` as
    (request path, credential headers): the fake never dials, so what the sender was asked to carry is the
    proof. The default answer is a connection error; a test that means its requests to succeed passes
    ``answer=``. The session path records only that it was reached: no c3 test takes it.
    """

    def __init__(self, answer=None):
        self.dialed = []
        self.sent = []
        self.answer = ConfinementError("connection", "stubbed: no network in the proof") if answer is None else answer

    def __enter__(self):
        self._saved = (confinement._exchange, confinement._session_send)
        answer = self.answer

        def stub_exchange(ready, provider, request, deadline, credential=None):
            self.dialed.append(request.path)
            self.sent.append({"path": request.path, "credential": dict(credential or {})})
            return answer

        def stub_session(provider, request, ready, effect, deadline):
            self.dialed.append(request.path)
            return answer

        confinement._exchange = stub_exchange
        confinement._session_send = stub_session
        return self

    def __exit__(self, *exc):
        confinement._exchange, confinement._session_send = self._saved


def test_c3_today_a_credential_applies_to_every_request_of_the_provider():
    """Observed legacy behaviour: no scope is set, so the provider's credential is for the WHOLE provider."""
    os.environ["SYNTH_CONNECT_TOKEN"] = SECRET_VALUE
    try:
        provider = Provider(id="synth", name="S", kind="http", base_url="http://fixture.invalid",
                            auth=Auth(type="bearer", secret_ref=SECRET_REF), network=Network(lan=True))
        assert provider.auth.scope is None               # None is the legacy unscoped state
        outs = []
        with _Dials(answer=ok({})) as dials:
            for path in ("/health", "/anything-else"):
                # an address confinement ACCEPTS for this provider, so nothing but the credential
                # (or the lack of one) can stand between the request and the sender
                outs.append(confinement.confined_request(
                    provider, Request(id="synth.r", provider="synth", path=path), effect="read",
                    resolver=lambda host, port: ["10.9.9.9"]))        # pw-safety: synthetic; allowed for a lan provider
        # BOTH requests reached the sender, and EACH one carried the provider's credential: miss it on
        # either request and this fails -- an unavailable credential never reaches the sender at all,
        # and a dropped one arrives bare.
        assert [s["path"] for s in dials.sent] == ["/health", "/anything-else"], "a request never reached the sender"
        assert all(s["credential"] == {"Authorization": f"Bearer {SECRET_VALUE}"} for s in dials.sent), \
            "a request reached the sender without the credential"
        assert all(isinstance(o, RawResponse) and o.status_code == 200 for o in outs)
        # and no request is refused FOR SCOPE while the credential is unscoped: the verdict allows both
        assert all(scope_allows(provider, Request(id="synth.r", provider="synth", path=p))
                   for p in ("/health", "/anything-else"))
    finally:
        os.environ.pop("SYNTH_CONNECT_TOKEN", None)


def test_c3_an_unresolvable_reference_sends_nothing():
    os.environ.pop("SYNTH_CONNECT_TOKEN", None)
    provider = Provider(id="synth", name="S", kind="http", base_url="http://fixture.invalid",
                        auth=Auth(type="bearer", secret_ref=SECRET_REF))
    with _Dials() as dials:
        out = confinement.confined_request(provider, Request(id="synth.r", provider="synth", path="/h"), effect="read",
                                           resolver=lambda host, port: ["127.0.0.1"])
    assert isinstance(out, ConfinementError) and dials.dialed == []


def test_c3_auth_scope_exists_and_none_is_the_legacy_unscoped_state():
    assert Auth(type="bearer", secret_ref=SECRET_REF, scope=["health"]).scope == ["health"]
    assert Auth(type="bearer", secret_ref=SECRET_REF).scope is None
    with pytest.raises(ValidationError):
        Auth(type="bearer", secret_ref=SECRET_REF, scope=["Not An Id"])


@pytest.mark.xfail(strict=True, reason="the word 'unscoped' exists in src/ but in no card envelope (cards.build) or UI surface; condition 3 needs one there (build-plan Q2)")
def test_c3_unscoped_is_labelled_wherever_it_appears(world):
    store, fx, _, cards, _ = world
    connect(store)
    fx.script = ok({"status": "ok", "queue": 1})
    assert "unscoped" in json.dumps(cards.build("synth-health")).lower()


def test_c3_out_of_scope_capability_fails_before_any_dns_lookup():
    # The credential is scoped to capability "synth.health"; this request serves "synth.other". The address
    # is one confinement accepts and the credential is available, so the ONLY thing that can refuse this
    # request is scope -- address classification can no longer mask the ordering.
    provider = Provider(id="synth", name="S", kind="http", base_url="http://fixture.invalid",
                        auth=Auth(type="bearer", secret_ref=SECRET_REF, scope=["health"]), network=Network(lan=True))
    lookups = []
    os.environ["SYNTH_CONNECT_TOKEN"] = SECRET_VALUE
    try:
        with _Dials() as dials:
            out = send_scoped(lambda p, r, *, effect, **kw: confinement.confined_request(
                p, r, effect=effect,
                resolver=lambda *a: lookups.append(a) or ["10.9.9.9"], **kw),                # pw-safety: synthetic
                provider, Request(id="synth.other", provider="synth", path="/other"), effect="read")
    finally:
        os.environ.pop("SYNTH_CONNECT_TOKEN", None)
    # the contract's ORDER (§4.2: auth_failed BEFORE any DNS, no bytes): the scope refusal comes first, so
    # the resolver was never asked and nothing was sent. A scope check that lands only AFTER DNS keeps this
    # test red on the lookups assertion.
    assert isinstance(out, ConfinementError) and out.error_class == "auth_failed", f"not refused for scope: {out!r}"
    assert lookups == [], "the capability was refused for scope, but only after DNS"
    assert dials.dialed == [] and dials.sent == [], "bytes were attempted"


def test_c3_the_reference_sender_honours_an_out_of_scope_verdict_before_any_socket():
    """reference_send has its own network path (it does not reach confined_request); it must take the verdict too."""
    from personal_world.worlds.reference_provider import reference_send
    provider = Provider(id="ref", name="R", kind="reference", base_url="http://127.0.0.1:1",
                        auth=Auth(type="bearer", secret_ref=SECRET_REF, scope=["health"]))
    send = reference_send({"SYNTH_CONNECT_TOKEN": SECRET_VALUE}, allowed_ports={1})
    refused = send_scoped(send, provider, Request(id="ref.other", provider="ref", path="/other"), effect="read")
    assert isinstance(refused, ConfinementError) and refused.error_class == "auth_failed" and refused.pre_send
    # an in-scope request is not refused as auth_failed: it proceeds to the (dead) port and fails as a connection
    went = send_scoped(send, provider, Request(id="ref.health", provider="ref", path="/h"), effect="read")
    assert isinstance(went, ConfinementError) and went.error_class != "auth_failed"


def test_c3_the_transport_enforces_the_verdict_it_is_given_and_does_not_decide_scope():
    """confined_request reads no scope: an unscoped-looking call refused by verdict is refused; a scoped one allowed by verdict goes."""
    provider = Provider(id="synth", name="S", kind="http", base_url="http://fixture.invalid",
                        auth=Auth(type="bearer", secret_ref=SECRET_REF, scope=["health"]))
    lookups = []
    os.environ["SYNTH_CONNECT_TOKEN"] = SECRET_VALUE
    try:
        with _Dials():
            refused = confinement.confined_request(provider, Request(id="synth.health", provider="synth", path="/h"),
                                                   effect="read", in_scope=False,
                                                   resolver=lambda *a: lookups.append(a) or ["127.0.0.1"])
            confinement.confined_request(provider, Request(id="synth.other", provider="synth", path="/o"), effect="read",
                                         resolver=lambda *a: lookups.append(a) or ["127.0.0.1"])
    finally:
        os.environ.pop("SYNTH_CONNECT_TOKEN", None)
    assert refused.error_class == "auth_failed"
    assert len(lookups) == 1                      # only the call whose verdict allowed it looked anything up


def test_c3_an_in_scope_capability_still_reaches_dns():
    provider = Provider(id="synth", name="S", kind="http", base_url="http://fixture.invalid",
                        auth=Auth(type="bearer", secret_ref=SECRET_REF, scope=["health"]))
    lookups = []
    os.environ["SYNTH_CONNECT_TOKEN"] = SECRET_VALUE
    try:
        with _Dials():
            send_scoped(lambda p, r, *, effect, **kw: confinement.confined_request(
                p, r, effect=effect, resolver=lambda *a: lookups.append(a) or ["127.0.0.1"], **kw),
                provider, Request(id="synth.health", provider="synth", path="/health"), effect="read")
    finally:
        os.environ.pop("SYNTH_CONNECT_TOKEN", None)
    assert len(lookups) == 1


# ---------------------------------------------------------------- conditions 1 and 2: the dispatcher

def _dispatch_env(tmp_path, *, governance=None, verifier=None, exposed=False, state="adopted"):
    pytest.importorskip("fastapi")   # authn imports it; without it these are SKIPPED, i.e. NOT RUN
    from personal_world.worlds.db import Database
    from personal_world.worlds.dispatcher import Dispatcher

    clock = Clock()
    db = Database.in_dir(tmp_path / "data")
    store = ConfigStore(tmp_path / "cfg")
    store.save("provider", Provider(id="ph", name="PH", kind="http", base_url="http://fixture.invalid",
                                    governance=governance))
    store.save("request", Request(id="ph.go", provider="ph", method="POST", path="/go"))
    store.save("action", Action(id="go", request="ph.go", name="Go", scope="deploy.run", exposed=exposed,
                                  state=state))
    fx = Fixture()
    fx.script = RawResponse(200, body=b"{}")
    return Dispatcher(db, store, send=fx, clock=clock, project_home_verifier=verifier), fx, clock


def _owner(clock):
    from personal_world.worlds.authn import Principal
    return Principal("owner", "owner", session_hash="h", step_up_at=clock(), via="session")


def _agent():
    from personal_world.worlds.authn import Principal
    return Principal("agent", "agent1", ("deploy.*",), via="token")


def test_c1_project_home_without_a_verifier_is_not_approved_and_never_runs(tmp_path):
    from personal_world.worlds.dispatcher import NotConsumable, NotPermitted
    d, fx, clock = _dispatch_env(tmp_path, governance="project_home")
    owner = _owner(clock)
    auth = d.request_authorization(owner, "go")
    with pytest.raises(NotPermitted):
        d.record_project_home_approval(auth["id"], "ph-approval-1")      # route maps NotPermitted -> 403
    with pytest.raises(NotPermitted):
        d.approve(owner, auth["id"])                                      # the owner cannot stand in for it
    with pytest.raises(NotConsumable):
        d.execute(owner, auth["id"])
    assert d.get_authorization(auth["id"])["state"] == "pending" and fx.calls == []


def test_c1_a_project_home_refusal_leaves_the_action_unapproved(tmp_path):
    from personal_world.worlds.dispatcher import NotConsumable, NotPermitted
    seen = []
    d, fx, clock = _dispatch_env(tmp_path, governance="project_home", verifier=lambda aid, row: seen.append(aid) or False)
    owner = _owner(clock)
    auth = d.request_authorization(owner, "go")
    with pytest.raises(NotPermitted):
        d.record_project_home_approval(auth["id"], "ph-denied")
    with pytest.raises(NotConsumable):
        d.execute(owner, auth["id"])
    assert seen == ["ph-denied"] and d.get_authorization(auth["id"])["state"] == "pending" and fx.calls == []


def test_c1_a_verifier_that_fails_hard_also_leaves_it_unapproved(tmp_path):
    from personal_world.worlds.dispatcher import NotConsumable

    def forbidden(aid, row):
        raise PermissionError("403 from Project Home")
    d, fx, clock = _dispatch_env(tmp_path, governance="project_home", verifier=forbidden)
    owner = _owner(clock)
    auth = d.request_authorization(owner, "go")
    with pytest.raises(PermissionError):
        d.record_project_home_approval(auth["id"], "ph-403")
    with pytest.raises(NotConsumable):
        d.execute(owner, auth["id"])
    assert d.get_authorization(auth["id"])["state"] == "pending" and fx.calls == []


def test_c2_an_unexposed_action_is_inert_for_an_agent_directly(tmp_path):
    """Closest real analogue of state=proposed (contract §6.1: 'already inert: exposed: false')."""
    from personal_world.worlds.dispatcher import NotPermitted
    d, fx, _ = _dispatch_env(tmp_path, exposed=False)
    with pytest.raises(NotPermitted):
        d.request_authorization(_agent(), "go")
    assert d.list_actions(_agent()) == [] and fx.calls == []


def test_c2_an_unexposed_action_is_inert_through_other_paths(tmp_path):
    """Indirect: the agent reaches the dispatcher by execute() and request_retry() on the owner's authorization."""
    from personal_world.worlds.dispatcher import BadRequest, NotPermitted
    d, fx, clock = _dispatch_env(tmp_path, exposed=False)
    owner_auth = d.request_authorization(_owner(clock), "go")             # pending, owner's
    with pytest.raises(NotPermitted):
        d.execute(_agent(), owner_auth["id"])                             # not the agent's authorization
    with pytest.raises(BadRequest):
        d.request_retry(_agent(), "no-such-execution")
    assert d.get_authorization(owner_auth["id"])["state"] == "pending" and fx.calls == []


def test_c2_a_state_proposed_action_can_exist():
    assert Action(id="go", request="ph.go", name="Go", state="proposed").state == "proposed"
    assert Action(id="go", request="ph.go", name="Go").state == "adopted"
    with pytest.raises(ValidationError):
        Action(id="go", request="ph.go", name="Go", state="executed")


def test_c2_a_state_proposed_action_is_inert_at_dispatcher_and_runtime(tmp_path):
    from personal_world.worlds.dispatcher import NotConsumable, NotPermitted
    d, fx, clock = _dispatch_env(tmp_path, exposed=True, state="adopted")
    owner = _owner(clock)
    auth = d.request_authorization(owner, "go")                           # adopted: authorizable
    assert [a.id for a in d.list_actions(_agent())] == ["go"]
    d.approve(owner, auth["id"])                                          # approved, not yet consumed
    # the proposal path: the same action file is rewritten as proposed (exposed stays true on purpose)
    d._store.save("action", Action(id="go", request="ph.go", name="Go", scope="deploy.run", exposed=True,
                                   state="proposed"))
    assert d.list_actions(_agent()) == []                                  # never exposed
    for who in (_agent(), owner):
        with pytest.raises(NotPermitted):
            d.request_authorization(who, "go")                             # never authorized
    with pytest.raises(NotConsumable):
        d.execute(owner, auth["id"])                                       # runtime: an old approval is not consumable
    assert fx.calls == []                                                  # nothing was ever sent
    assert d._db.conn().execute("SELECT count(*) FROM executions").fetchone()[0] == 0


def test_c2_a_state_consume_refuses_a_proposed_action_even_with_a_current_version_authorization(tmp_path):
    """Uniquely reaches the state check in _consume: the approval is forced current, so version invalidation cannot refuse it."""
    from personal_world.worlds.dispatcher import NotConsumable
    d, fx, clock = _dispatch_env(tmp_path, exposed=True, state="adopted")
    owner = _owner(clock)
    auth = d.request_authorization(owner, "go")
    d.approve(owner, auth["id"])
    d._store.save("action", Action(id="go", request="ph.go", name="Go", scope="deploy.run", exposed=True, state="proposed"))
    with d._db.write_tx() as tx:                                           # a current-version approval for the proposed action
        tx.execute("UPDATE authorizations SET state='approved', action_version=? WHERE id=?",
                   (d._store.action_version("go"), auth["id"]))
    with pytest.raises(NotConsumable, match="not adopted"):
        d.execute(owner, auth["id"])
    assert fx.calls == []
