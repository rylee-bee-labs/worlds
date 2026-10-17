"""Tests for personal_world.worlds.confinement: SSRF guard, pinning, no redirects, caps, URL safety."""
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from personal_world.worlds import secrets as worlds_secrets
from personal_world.worlds.confinement import ConfinementError, RawResponse, classify_address, confined_request
from personal_world.worlds.models import Auth, Provider, Request


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    hits: list = []

    def log_message(self, *a):
        pass

    def _send(self, code, body=b"{}", headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        Handler.hits.append((self.command, self.path, dict(self.headers)))
        if self.path.startswith("/redirect"):
            return self._send(302, b"", {"Location": "/landed"})
        if self.path.startswith("/landed"):
            return self._send(200, b'{"landed":true}')
        if self.path.startswith("/big"):
            return self._send(200, b"x" * 5000)
        if self.path.startswith("/stream-big"):
            self.send_response(200)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                for _ in range(200):
                    self.wfile.write(b"400\r\n" + b"y" * 1024 + b"\r\n")
                self.wfile.write(b"0\r\n\r\n")
            except OSError:
                pass
            return
        if self.path.startswith("/drip"):
            self.send_response(200)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                for _ in range(20):
                    self.wfile.write(b"1\r\nz\r\n")
                    self.wfile.flush()
                    time.sleep(0.15)
            except OSError:
                pass
            return
        return self._send(200, json.dumps({"path": self.path, "host": self.headers.get("Host"),
                                           "auth": self.headers.get("Authorization")}).encode())

    do_HEAD = do_GET

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(n) if n else b""
        Handler.hits.append((self.command, self.path, dict(self.headers)))
        self._send(200, json.dumps({"got": data.decode()}).encode())


@pytest.fixture
def srv():
    Handler.hits = []
    s = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    yield s
    s.shutdown()
    s.server_close()


def prov(srv, lan=True, **kw):
    d = dict(id="p", name="P", kind="http", base_url=f"http://127.0.0.1:{srv.server_address[1]}", network={"lan": lan})
    d.update(kw)
    return Provider(**d)


def req(path="/x", method="GET", **kw):
    return Request(id="p.r", provider="p", path=path, method=method, **kw)


def go(p, r, effect="read", resolver=None):
    return confined_request(p, r, effect=effect, resolver=resolver)


def denied(out, why=None):
    assert isinstance(out, ConfinementError) and out.error_class == "confinement_denied", out
    if why:
        assert why in out.note, out.note


# ---- address classification


@pytest.mark.parametrize("addr", ["127.0.0.1", "127.8.9.1", "::1", "169.254.1.1", "fe80::1", "10.1.2.3", "172.16.0.1",  # pw-safety: synthetic
                                  "172.31.255.254", "192.0.2.11", "100.64.0.1", "fd12:3456::1", "::ffff:127.0.0.1",  # pw-safety: synthetic
                                  "::ffff:10.0.0.1"])  # pw-safety: synthetic
def test_internal_addresses_denied_unless_lan(addr):
    assert classify_address(addr, lan=False)
    assert classify_address(addr, lan=True) is None


@pytest.mark.parametrize("addr", ["169.254.169.254", "169.254.170.2", "100.100.100.200", "fd00:ec2::254",  # pw-safety: synthetic
                                  "::ffff:169.254.169.254", "0.0.0.0", "::", "224.0.0.1", "ff02::1", "240.0.0.1"])  # pw-safety: synthetic
def test_metadata_and_unroutable_always_denied(addr):
    assert classify_address(addr, lan=True)


@pytest.mark.parametrize("addr", ["93.184.216.34", "8.8.8.8", "2606:4700:4700::1111"])
def test_public_allowed(addr):
    assert classify_address(addr, lan=False) is None


# ---- guard behaviour with the real sender


def test_loopback_denied_by_default_and_nothing_is_sent(srv):
    denied(go(prov(srv, lan=False), req()), "internal")
    assert Handler.hits == []


def test_lan_provider_can_reach_loopback(srv):
    out = go(prov(srv), req("/ok"))
    assert isinstance(out, RawResponse) and out.status_code == 200
    assert json.loads(out.body)["path"] == "/ok"


def test_mixed_dns_answers_are_denied_if_any_is_internal(srv):
    p = prov(srv, lan=False, base_url="http://app.example.test:8080")
    denied(go(p, req(), resolver=lambda h, port: ["93.184.216.34", "10.0.0.5"]), "internal")  # pw-safety: synthetic


def test_metadata_denied_even_for_lan_provider(srv):
    p = prov(srv, base_url="http://meta.example.test")
    denied(go(p, req(), resolver=lambda h, port: ["169.254.169.254"]), "metadata")  # pw-safety: synthetic


@pytest.mark.parametrize("host", ["2130706433", "0x7f.1", "017700000001", "127.1", "localhost", "[::1]", "[::ffff:7f00:1]"])
def test_tricky_loopback_spellings_denied_by_resolved_address(srv, host):
    p = prov(srv, lan=False, base_url=f"http://{host}:{srv.server_address[1]}")
    out = go(p, req())
    assert isinstance(out, ConfinementError) and out.error_class in ("confinement_denied", "connection")
    assert Handler.hits == []


def test_dns_pinning_resolves_once_and_connects_to_the_vetted_ip(srv):
    calls = []

    def resolver(host, port):
        calls.append(host)
        return ["127.0.0.1"] if len(calls) == 1 else ["10.9.9.9"]  # pw-safety: synthetic

    p = prov(srv, base_url=f"http://app.example.test:{srv.server_address[1]}")
    out = go(p, req("/pinned"), resolver=resolver)
    assert isinstance(out, RawResponse) and out.status_code == 200
    assert calls == ["app.example.test"]
    assert json.loads(out.body)["host"] == f"app.example.test:{srv.server_address[1]}"


def test_rebinding_second_answer_never_used(srv):
    answers = iter([["93.184.216.34"], ["127.0.0.1"]])
    p = prov(srv, lan=False, base_url="http://rebind.example.test:81", timeout_s=0.5)
    out = go(p, req(), resolver=lambda h, port: next(answers))
    # public vetted address is dialled (unreachable here); the loopback answer is never consulted
    assert isinstance(out, ConfinementError) and out.error_class in ("connection", "timeout")
    assert Handler.hits == []


def test_unresolvable_host_is_connection_error():
    def boom(h, p):
        raise socket.gaierror("no")
    p = Provider(id="p", name="P", kind="http", base_url="http://nope.example.test")
    out = go(p, req(), resolver=boom)
    assert isinstance(out, ConfinementError) and out.error_class == "connection"


def test_redirects_are_refused_and_not_followed(srv):
    out = go(prov(srv), req("/redirect"))
    assert isinstance(out, ConfinementError) and out.error_class == "redirect_refused" and out.status_code == 302
    assert all(not h[1].startswith("/landed") for h in Handler.hits)


def test_size_cap_declared_and_streamed(srv):
    p = prov(srv, max_bytes=1000)
    assert go(p, req("/big")).error_class == "too_large"
    assert go(p, req("/stream-big")).error_class == "too_large"
    assert go(prov(srv), req("/big")).status_code == 200


def test_total_time_budget_applies_to_slow_drips(srv):
    t0 = time.monotonic()
    out = go(prov(srv, timeout_s=0.5), req("/drip"))
    assert isinstance(out, ConfinementError) and out.error_class == "timeout"
    assert time.monotonic() - t0 < 2.5


def test_connection_refused_is_connection_error():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    p = Provider(id="p", name="P", kind="http", base_url=f"http://127.0.0.1:{port}", network={"lan": True})
    assert go(p, req()).error_class == "connection"


def test_no_retry_on_failure(srv):
    go(prov(srv), req("/redirect"))
    assert len([h for h in Handler.hits if h[1].startswith("/redirect")]) == 1


# ---- URL join and path escape (models bypassed on purpose)


@pytest.mark.parametrize("path", ["x", "//evil.test/x", "/a/../b", "/./a", "/a/%2e%2e/b", "/a%2fb", "/a\\b", "/a@evil/x",
                                  "/a b", "/a#frag", "/a?x=1", "/a\r\nHost: evil", "http://evil.test/", "/a%00"])
def test_bad_paths_denied_before_any_dns(srv, path):
    r = Request.model_construct(schema_version=1, id="p.r", provider="p", method="GET", path=path, query={}, headers={},
                                body=None, effect="auto", known_safe=False, ttl_s=0, timeout_s=None, assertions=[])
    called = []
    out = go(prov(srv), r, resolver=lambda h, p: called.append(1) or ["127.0.0.1"])
    denied(out)
    assert not called and Handler.hits == []


def test_prefix_and_query_are_joined_and_encoded(srv):
    p = prov(srv, path_prefix="/api/v1")
    out = go(p, req("/items", query={"q": "a b&c=d", "n": "1"}))
    got = json.loads(out.body)["path"]
    assert got.startswith("/api/v1/items?") and "q=a%20b%26c%3Dd" in got and "Host" not in got


def test_base_url_userinfo_is_rejected(srv):
    p = Provider.model_construct(schema_version=1, id="p", name="P", kind="http", path_prefix="",
                                 base_url=f"http://user:pw@127.0.0.1:{srv.server_address[1]}", auth=Auth(), network={"lan": True}.__class__ and __import__("personal_world.worlds.models", fromlist=["Network"]).Network(lan=True),
                                 tls_verify=True, timeout_s=5, max_bytes=1000)
    denied(go(p, req()))


# ---- headers, effect, body


def raw_req(headers, path="/x"):
    """A request that bypassed model validation: confinement must refuse these on its own."""
    return Request.model_construct(schema_version=1, id="p.r", provider="p", method="GET", path=path, query={},
                                   headers=headers, body=None, effect="auto", known_safe=False, ttl_s=0,
                                   timeout_s=None, assertions=[])


@pytest.mark.parametrize("h", ["Host", "Content-Length", "Transfer-Encoding", "Connection", "Upgrade", "Expect", "TE",
                               "Authorization", "Cookie"])
def test_framing_headers_refused(srv, h):
    denied(go(prov(srv), raw_req({h: "x"})), "not allowed")


def test_crlf_in_header_value_refused(srv):
    denied(go(prov(srv), raw_req({"X-A": "a\r\nX-B: b"})), "control")


def test_read_effect_cannot_send_mutating_method(srv):
    denied(go(prov(srv), req("/x", "POST"), effect="read"), "read effect")
    assert Handler.hits == []


def test_write_sends_json_body_once(srv):
    out = go(prov(srv), req("/w", "POST", body={"a": 1}), effect="write")
    assert json.loads(json.loads(out.body)["got"]) == {"a": 1}
    assert len([h for h in Handler.hits if h[0] == "POST"]) == 1


# ---- credentials


def test_bearer_injected_from_env_and_never_in_notes(srv, monkeypatch):
    monkeypatch.setenv("CONF_TOKEN", "s3cret-value")
    p = prov(srv, auth=Auth(type="bearer", secret_ref="env:CONF_TOKEN"))
    out = go(p, req())
    assert json.loads(out.body)["auth"] == "Bearer s3cret-value"


def test_missing_secret_is_auth_failed_and_nothing_sent(srv, monkeypatch):
    monkeypatch.delenv("CONF_TOKEN", raising=False)
    p = prov(srv, auth=Auth(type="bearer", secret_ref="env:CONF_TOKEN"))
    out = go(p, req())
    assert isinstance(out, ConfinementError) and out.error_class == "auth_failed" and Handler.hits == []


def test_vault_ref_needs_unlocked_vault(srv):
    class V:
        is_unlocked = False
        def get(self, n):
            return "vv"
    v = V()
    worlds_secrets.set_vault(v)
    try:
        p = prov(srv, auth=Auth(type="bearer", secret_ref="vault:k"))
        assert go(p, req()).error_class == "auth_failed"
        v.is_unlocked = True
        assert json.loads(go(p, req()).body)["auth"] == "Bearer vv"
    finally:
        worlds_secrets.set_vault(None)


def test_secret_resolver_is_strict(monkeypatch):
    monkeypatch.setenv("plain-name", "x")
    assert worlds_secrets.resolve_secret_ref("plain-name") is None
    assert worlds_secrets.resolve_secret_ref("${HOME}") is None
    assert worlds_secrets.resolve_secret_ref("env:") is None


def test_internal_errors_fail_closed_without_raising(srv):
    out = confined_request(prov(srv), object(), effect="read")
    assert isinstance(out, ConfinementError)


def _tls_server(tmp_path):
    import datetime
    import ssl

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "app.example.test")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1).not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("app.example.test")]), critical=False)
            .sign(key, hashes.SHA256()))
    cf, kf = tmp_path / "c.pem", tmp_path / "k.pem"
    cf.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    kf.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption()))
    s = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cf, kf)
    s.socket = ctx.wrap_socket(s.socket, server_side=True)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def test_https_pins_ip_but_verifies_by_hostname(tmp_path):
    s = _tls_server(tmp_path)
    try:
        port = s.server_address[1]
        def resolver(h, p):
            return ["127.0.0.1"]
        p = Provider(id="p", name="P", kind="http", base_url=f"https://app.example.test:{port}",
                     network={"lan": True}, tls_verify=False)
        out = go(p, req("/tls"), resolver=resolver)
        assert isinstance(out, RawResponse) and out.status_code == 200
        assert json.loads(out.body)["host"] == f"app.example.test:{port}"
        strict = p.model_copy(update={"tls_verify": True})
        bad = go(strict, req("/tls"), resolver=resolver)  # self-signed is not trusted
        assert isinstance(bad, ConfinementError) and bad.error_class == "connection"
    finally:
        s.shutdown()
        s.server_close()


def test_query_templates_render_in_the_joined_url():
    import datetime as dt

    from personal_world.worlds.confinement import build_url
    from personal_world.worlds.models import Provider, Request

    provider = Provider(id="p", name="P", kind="http", base_url="http://svc.lan.example:8989")
    request = Request(id="p.cal", provider="p", path="/api/v3/calendar", query={"start": "{today}", "end": "{today+7d}", "unmonitored": "false"})
    now = dt.datetime(2026, 10, 1, 12, 0, tzinfo=dt.timezone.utc)
    target = build_url(provider, request, now)
    assert not isinstance(target, str)
    assert target[3] == "/api/v3/calendar?start=2026-10-01&end=2026-10-08&unmonitored=false"
