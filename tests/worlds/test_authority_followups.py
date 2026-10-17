"""Follow-ups A-E from the #233 re-check: credential header names, hard deadline, delete of invalid files,
IPv6 Host parsing, and the dev sender's port rule."""
import socket
import threading
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from personal_world.worlds.confinement import ConfinementError, confined_request
from personal_world.worlds.models import Auth, Provider, Request
from personal_world.worlds.reference_provider import ReferenceServer, reference_send
from personal_world.worlds.server import build_app, parse_host


# ---- A
@pytest.mark.parametrize("name", ["Host", "host", "Cookie", "Set-Cookie", "Transfer-Encoding", "Content-Length", "Content-Type",
                                  "Authorization", "Proxy-Authorization", "Forwarded", "X-Forwarded-For", "X-Forwarded-Host",
                                  "X-Forwarded-Proto", "X-Real-IP", "Connection", "Upgrade", "TE", "Via", "Origin",
                                  "Proxy-Foo", "Sec-Fetch-Mode", "Idempotency-Key", "bad name", "a:b", "", "x" * 65,
                                  "x\r\ny", "-lead", "name_underscore"])
def test_credential_header_names_are_constrained(name):
    with pytest.raises(ValidationError):
        Auth(type="header", header_name=name, secret_ref="env:K")


@pytest.mark.parametrize("name", ["X-Api-Key", "X-Token", "Api-Key", "Ocp-Apim-Subscription-Key", "apikey"])
def test_ordinary_credential_header_names_ok(name):
    assert Auth(type="header", header_name=name, secret_ref="env:K").header_name == name


def test_confinement_refuses_a_bad_credential_header_even_if_validation_was_bypassed(monkeypatch):
    monkeypatch.setenv("K", "v")
    bad = Auth.model_construct(type="header", header_name="Host", secret_ref="env:K")
    p = Provider.model_construct(schema_version=1, id="p", name="P", kind="http", base_url="http://127.0.0.1:9", path_prefix="",
                                 auth=bad, network=__import__("personal_world.worlds.models", fromlist=["Network"]).Network(lan=True),
                                 tls_verify=True, timeout_s=1, max_bytes=100)
    out = confined_request(p, Request(id="p.r", provider="p", path="/x"), effect="read")
    assert isinstance(out, ConfinementError) and out.error_class == "confinement_denied"


# ---- B: one blocked read must not outlive the budget
def _silent_server(delay):
    """Accepts and says nothing for `delay` seconds (header-phase stall)."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    conns = []

    def run():
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return
            conns.append(c)
            threading.Timer(delay, c.close).start()

    threading.Thread(target=run, daemon=True).start()
    return srv


def test_confinement_deadline_covers_a_stalled_body_read():
    with ReferenceServer() as ref:
        p = Provider(id="p", name="P", kind="http", base_url=ref.base_url, network={"lan": True}, timeout_s=0.5)
        t0 = time.monotonic()
        out = confined_request(p, Request(id="p.r", provider="p", path="/stall"), effect="read")
        assert isinstance(out, ConfinementError) and out.error_class == "timeout"
        assert time.monotonic() - t0 < 1.0, time.monotonic() - t0   # not ~2x the budget


def test_confinement_deadline_covers_a_stalled_header_phase():
    srv = _silent_server(5)
    try:
        port = srv.getsockname()[1]
        p = Provider(id="p", name="P", kind="http", base_url=f"http://127.0.0.1:{port}", network={"lan": True}, timeout_s=0.6)
        t0 = time.monotonic()
        out = confined_request(p, Request(id="p.r", provider="p", path="/x"), effect="read")
        assert isinstance(out, ConfinementError) and out.error_class == "timeout"
        assert time.monotonic() - t0 < 1.2, time.monotonic() - t0
    finally:
        srv.close()


def test_reference_sender_has_the_same_hard_deadline():
    with ReferenceServer() as ref:
        p = Provider(id="p", name="P", kind="reference", base_url=ref.base_url, network={"lan": True}, timeout_s=0.5)
        t0 = time.monotonic()
        out = reference_send({})(p, Request(id="p.r", provider="p", path="/stall"), effect="read")
        assert isinstance(out, ConfinementError) and out.error_class == "timeout"
        assert time.monotonic() - t0 < 1.0, time.monotonic() - t0


# ---- C
def _api(tmp_path):
    app = build_app(tmp_path / "cfg", principal_dependency=lambda: "owner", send_override=lambda *a, **k: None)
    return app, TestClient(app, base_url="http://127.0.0.1")


def _provider(c, pid="p1"):
    body = {"schema_version": 1, "id": pid, "name": "P", "kind": "http", "base_url": "http://127.0.0.1:9"}
    return c.put(f"/api/config/provider/{pid}", json=body, headers={"If-None-Match": "*"})


def test_delete_of_a_newly_invalid_file_needs_the_listed_etag(tmp_path):
    app, c = _api(tmp_path)
    f = tmp_path / "cfg" / "worlds" / "providers" / "broken.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("schema_version: 1\nid: broken\nname: [x\n")
    app.state.store.reload()
    err = [e for e in c.get("/api/config/provider").json()["errors"] if e["id"] == "broken"][0]
    assert c.get("/api/config/provider/broken").status_code == 404           # no valid version to read
    assert c.delete("/api/config/provider/broken").status_code == 409        # no etag
    assert c.delete("/api/config/provider/broken", headers={"If-Match": "deadbeef"}).status_code == 409
    assert c.delete("/api/config/provider/broken", headers={"If-Match": "*"}).status_code == 428
    assert f.exists()
    assert c.delete("/api/config/provider/broken", headers={"If-Match": '"' + err["etag"] + '"'}).status_code == 204
    assert not f.exists() and not [e for e in c.get("/api/config/provider").json()["errors"] if e["id"] == "broken"]


def test_delete_with_stale_etag_conflicts_and_missing_is_404(tmp_path):
    app, c = _api(tmp_path)
    r = _provider(c)
    etag = r.headers["etag"]
    _provider_put = c.put("/api/config/provider/p1", json=r.json() | {"name": "N"}, headers={"If-Match": etag})
    assert c.delete("/api/config/provider/p1", headers={"If-Match": etag}).status_code == 409
    assert c.delete("/api/config/provider/p1", headers={"If-Match": _provider_put.headers["etag"]}).status_code == 204
    assert c.delete("/api/config/provider/p1").status_code == 404
    assert c.delete("/api/config/provider/Bad..Id").status_code == 404
    assert c.delete("/api/config/bogus/x").status_code == 404


def test_delete_still_blocked_while_referenced_and_valid_delete_needs_no_etag(tmp_path):
    app, c = _api(tmp_path)
    _provider(c)
    req = {"schema_version": 1, "id": "p1.r", "provider": "p1", "path": "/x"}
    c.put("/api/config/request/p1.r", json=req, headers={"If-None-Match": "*"})
    assert c.delete("/api/config/provider/p1").status_code == 409
    assert c.delete("/api/config/request/p1.r").status_code == 204
    assert c.delete("/api/config/provider/p1").status_code == 204


# ---- D
@pytest.mark.parametrize("raw,host", [("127.0.0.1", "127.0.0.1"), ("127.0.0.1:8765", "127.0.0.1"), ("[::1]:8765", "::1"),
                                      ("[::1]", "::1"), ("LOCALHOST:80", "localhost"), ("[::ffff:7f00:1]:1", "::ffff:7f00:1")])
def test_parse_host_ok(raw, host):
    assert parse_host(raw) == host


@pytest.mark.parametrize("raw", [None, "", "a@127.0.0.1", "127.0.0.1/x", "127.0.0.1:abc", "[::1", "::1", "127.0.0.1\r\nx", "a b",
                                 "127.0.0.1:99999"])
def test_parse_host_rejects_malformed(raw):
    assert parse_host(raw) is None


def test_host_guard_end_to_end(tmp_path):
    app = build_app(tmp_path / "cfg", principal_dependency=lambda: "owner",
                    allowed_hosts=["127.0.0.1", "::1", "localhost"])
    c = TestClient(app, base_url="http://127.0.0.1")
    for good in ("127.0.0.1", "127.0.0.1:8765", "[::1]:8765", "[::1]", "localhost:1"):
        assert c.get("/healthz", headers={"Host": good}).status_code == 200, good
    for bad in ("evil.example", "127.0.0.1.evil.example", "a@127.0.0.1", "127.0.0.1:x", "[::2]:1", "0.0.0.0"):
        assert c.get("/healthz", headers={"Host": bad}).status_code == 400, bad


# ---- E
def test_reference_sender_accepts_only_loopback_literal_and_live_ports():
    with ReferenceServer(token="t") as ref, ReferenceServer(token="t") as other:
        def prov(base, **kw):
            return Provider(id="p", name="P", kind="reference", base_url=base, network={"lan": True},
                            auth={"type": "bearer", "secret_ref": "env:DEV"}, **kw)
        r = Request(id="p.r", provider="p", path="/secret")
        send = reference_send({"DEV": "t"}, allowed_ports={ref.port})
        assert send(prov(ref.base_url), r, effect="read").status_code == 200
        out = send(prov(other.base_url), r, effect="read")                   # a different port: never gets the token
        assert isinstance(out, ConfinementError) and out.error_class == "confinement_denied"
        assert other.calls == []
        for base in (f"http://localhost:{ref.port}", f"http://[::1]:{ref.port}", f"http://127.0.0.2:{ref.port}",
                     "http://127.0.0.1"):
            assert send(prov(base), r, effect="read").error_class == "confinement_denied", base
        default = reference_send({"DEV": "t"})                                # default: any LIVE reference server
        assert default(prov(other.base_url), r, effect="read").status_code == 200
    gone = reference_send({"DEV": "t"})(prov(other.base_url), r, effect="read")
    assert gone.error_class == "confinement_denied"                           # server stopped: port no longer live


# ---- review #236 M1: the budget covers DNS + connect + headers, not just the body
def _drip_header_server(gap):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)

    def run():
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return

            def talk(c=c):
                try:
                    c.recv(4096)
                    c.sendall(b"HTTP/1.1 200 OK\r\n")
                    for i in range(40):
                        time.sleep(gap)
                        c.sendall(f"X-Slow-{i}: y\r\n".encode())
                except OSError:
                    pass
                finally:
                    c.close()

            threading.Thread(target=talk, daemon=True).start()

    threading.Thread(target=run, daemon=True).start()
    return srv


def test_header_drip_ends_within_the_budget():
    srv = _drip_header_server(0.4)
    try:
        port = srv.getsockname()[1]
        p = Provider(id="p", name="P", kind="http", base_url=f"http://127.0.0.1:{port}", network={"lan": True}, timeout_s=1.0)
        t0 = time.monotonic()
        out = confined_request(p, Request(id="p.r", provider="p", path="/x"), effect="read")
        took = time.monotonic() - t0
        assert isinstance(out, ConfinementError) and out.error_class == "timeout"
        assert took <= 1.3, took
    finally:
        srv.close()


def test_slow_dns_ends_within_the_budget():
    release = threading.Event()

    def slow_resolver(host, port):
        release.wait(5)
        return ["127.0.0.1"]

    p = Provider(id="p", name="P", kind="http", base_url="http://slow.example.test", network={"lan": True}, timeout_s=0.5)
    t0 = time.monotonic()
    out = confined_request(p, Request(id="p.r", provider="p", path="/x"), effect="read", resolver=slow_resolver)
    release.set()
    assert isinstance(out, ConfinementError) and out.error_class == "timeout"
    assert time.monotonic() - t0 <= 0.8


def test_stalled_tls_handshake_ends_within_the_budget():
    srv = _silent_server(5)
    try:
        port = srv.getsockname()[1]
        p = Provider(id="p", name="P", kind="http", base_url=f"https://app.example.test:{port}", network={"lan": True},
                     timeout_s=0.6)
        t0 = time.monotonic()
        out = confined_request(p, Request(id="p.r", provider="p", path="/x"), effect="read",
                               resolver=lambda h, port_: ["127.0.0.1"])
        assert isinstance(out, ConfinementError) and out.error_class in ("timeout", "connection")
        assert time.monotonic() - t0 <= 0.9
    finally:
        srv.close()


# ---- minors
@pytest.mark.parametrize("secret", ["abc\r\nX-Evil: 1", "abc\ndef", "tab\there", "snowman-☃", "del\x7f"])
def test_unsendable_secret_values_fail_closed_before_sending(monkeypatch, secret):
    with ReferenceServer(token="t") as ref:
        monkeypatch.setenv("BAD_SECRET", secret)
        p = Provider(id="p", name="P", kind="http", base_url=ref.base_url, network={"lan": True},
                     auth={"type": "bearer", "secret_ref": "env:BAD_SECRET"})
        out = confined_request(p, Request(id="p.r", provider="p", path="/items"), effect="read")
        assert isinstance(out, ConfinementError) and out.error_class == "auth_failed" and ref.calls == []


@pytest.mark.parametrize("addr", ["fec0::1", "2002:0a00:0001::1", "2002:a9fe:a9fe::1", "64:ff9b::a9fe:a9fe", "168.63.129.16",
                                  "2001:0:4136:e378:8000:63bf:3f57:fefd"])
def test_more_always_or_default_denied_addresses(addr):
    from personal_world.worlds.confinement import classify_address
    assert classify_address(addr, lan=False)


@pytest.mark.parametrize("addr", ["2002:a9fe:a9fe::1", "64:ff9b::a9fe:a9fe", "168.63.129.16", "::ffff:168.63.129.16"])
def test_metadata_hidden_in_ipv6_is_refused_even_with_lan(addr):
    from personal_world.worlds.confinement import classify_address
    assert classify_address(addr, lan=True)


def test_encoded_bodies_are_refused_and_never_decompressed():
    import gzip
    import http.server

    bomb = gzip.compress(b"0" * 5_000_000)

    class H(http.server.BaseHTTPRequestHandler):
        seen = []

        def log_message(self, *a):
            pass

        def do_GET(self):
            H.seen.append(self.headers.get("Accept-Encoding"))
            self.send_response(200)
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(bomb)))
            self.end_headers()
            self.wfile.write(bomb)

    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        p = Provider(id="p", name="P", kind="http", base_url=f"http://127.0.0.1:{s.server_address[1]}", network={"lan": True},
                     max_bytes=1000 * 1024)
        out = confined_request(p, Request(id="p.r", provider="p", path="/x"), effect="read")
        assert isinstance(out, ConfinementError) and out.error_class == "malformed"
        assert H.seen == ["identity"]
    finally:
        s.shutdown()
        s.server_close()


# ---- review #237 follow-ups: descriptor race, connect clamp, bounded DNS
def test_descriptor_is_unregistered_the_moment_its_stream_closes():
    from personal_world.worlds.confinement import Deadline, _WatchedBackend
    with ReferenceServer() as ref:
        dl = Deadline(5)
        try:
            stream = _WatchedBackend(dl).connect_tcp("127.0.0.1", ref.port, timeout=2)
            fd = stream.get_extra_info("socket").fileno()
            assert fd in dl._fds
            stream.close()
            assert fd not in dl._fds                      # gone BEFORE the number can be reused
            dl._fire()                                    # a late fire must have nothing left to shut down
        finally:
            dl.disarm()


def test_connect_gets_only_the_remaining_budget(monkeypatch):
    import httpcore

    from personal_world.worlds.confinement import Deadline, _WatchedBackend
    seen = {}

    def fake(self, host, port, timeout=None, local_address=None, socket_options=None):
        seen["timeout"] = timeout
        raise httpcore.ConnectTimeout("stop")

    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", fake)
    dl = Deadline(0.5)
    try:
        time.sleep(0.2)
        with pytest.raises(httpcore.ConnectTimeout):
            _WatchedBackend(dl).connect_tcp("x", 1, timeout=5.0)
        assert seen["timeout"] <= 0.31
    finally:
        dl.disarm()


def test_dns_lookups_run_on_a_small_bounded_pool():
    release = threading.Event()
    started = []

    def slow(host, port):
        started.append(1)
        release.wait(3)
        return ["127.0.0.1"]

    p = Provider(id="p", name="P", kind="http", base_url="http://slow.example.test", network={"lan": True}, timeout_s=0.3)
    results = []
    ts = [threading.Thread(target=lambda: results.append(
        confined_request(p, Request(id="p.r", provider="p", path="/x"), effect="read", resolver=slow))) for _ in range(30)]
    [t.start() for t in ts]
    time.sleep(0.5)
    dns_threads = [t for t in threading.enumerate() if t.name.startswith("worlds-dns")]
    assert 0 < len(dns_threads) <= 8                       # never one thread per request
    [t.join() for t in ts]
    release.set()
    assert len(results) == 30 and all(isinstance(r, ConfinementError) and r.error_class == "timeout" for r in results)
    assert len(started) <= 8                               # queued lookups were cancelled, not started late


# ---- review #237 re-check 3: per-provider DNS cap, DNS failure means nothing was sent
def test_one_hostile_resolver_cannot_starve_other_providers():
    release = threading.Event()
    started = []

    def hostile(host, port):
        started.append(host)
        release.wait(3)
        return ["127.0.0.1"]

    bad = Provider(id="bad", name="Bad", kind="http", base_url="http://hostile.example.test", network={"lan": True}, timeout_s=0.4)
    out = []
    ts = [threading.Thread(target=lambda: out.append(confined_request(
        bad, Request(id="bad.r", provider="bad", path="/x"), effect="read", resolver=hostile))) for _ in range(12)]
    [t.start() for t in ts]
    time.sleep(0.15)
    with ReferenceServer() as ref:
        good = Provider(id="good", name="Good", kind="http", base_url=ref.base_url, network={"lan": True}, timeout_s=2)
        t0 = time.monotonic()
        ok = confined_request(good, Request(id="good.r", provider="good", path="/items"), effect="read")
        assert ok.status_code == 200 and time.monotonic() - t0 < 1.0     # the other provider is untouched
    [t.join() for t in ts]
    release.set()
    assert len(started) == 2                                             # only two lookups for the hostile provider
    assert all(isinstance(r, ConfinementError) and r.pre_send for r in out)
    assert sum("too many name lookups" in r.note for r in out) == 10


def test_pre_send_is_set_exactly_when_nothing_was_sent(monkeypatch):
    import socket as _socket
    p = Provider(id="p", name="P", kind="http", base_url="http://x.example.test", network={"lan": False})
    r = Request(id="p.r", provider="p", path="/x")
    assert confined_request(p, r, effect="read", resolver=lambda h, port: ["10.0.0.5"]).pre_send is True     # pw-safety: synthetic
    assert confined_request(p, r, effect="read", resolver=lambda h, port: (_ for _ in ()).throw(OSError("no"))).pre_send is True
    assert confined_request(p, r, effect="read", resolver=lambda h, port: []).pre_send is True
    monkeypatch.setenv("NOPE_SECRET", "")
    q = p.model_copy(update={"auth": Auth(type="bearer", secret_ref="env:NOPE_SECRET")})
    assert confined_request(q, r, effect="read", resolver=lambda h, port: ["93.184.216.34"]).pre_send is True
    s = _socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    lan = Provider(id="p", name="P", kind="http", base_url=f"http://127.0.0.1:{port}", network={"lan": True})
    refused = confined_request(lan, r, effect="read")
    assert refused.error_class == "connection" and refused.pre_send is False                              # we did try to connect


def test_dispatcher_settles_a_dns_timeout_as_failed_not_unknown(tmp_path):
    from personal_world.worlds.authn import Principal
    from personal_world.worlds.config_store import ConfigStore
    from personal_world.worlds.db import Database
    from personal_world.worlds.dispatcher import Dispatcher
    from personal_world.worlds.models import Action
    store = ConfigStore(tmp_path / "cfg")
    store.save("provider", Provider(id="svc", name="S", kind="http", base_url="http://slow.example.test", network={"lan": True}, timeout_s=0.3))
    store.save("request", Request(id="svc.go", provider="svc", method="POST", path="/go"))
    store.save("action", Action(id="go", request="svc.go", name="Go"))
    release = threading.Event()

    def slow_send(provider, request, *, effect):
        return confined_request(provider, request, effect=effect, resolver=lambda h, p: release.wait(2) and ["127.0.0.1"])

    d = Dispatcher(Database.in_dir(tmp_path / "data"), store, send=slow_send)
    o = Principal("owner", "owner", step_up_at=time.time(), via="session")
    a = d.approve(o, d.request_authorization(o, "go")["id"])
    receipt = d.execute(o, a["id"])
    release.set()
    assert receipt["state"] == "FAILED" and receipt["evidence"]["error_class"] == "timeout"
