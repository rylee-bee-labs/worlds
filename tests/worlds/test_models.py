import pytest
from pydantic import ValidationError

from personal_world.worlds.models import Action, Auth, Card, Provider, Request, action_version, canonical_json


def prov(**kw):
    base = dict(id="ref", name="Ref", kind="reference", base_url="http://127.0.0.1:9000")
    base.update(kw)
    return Provider(**base)


def req(**kw):
    base = dict(id="ref.items", provider="ref", path="/items")
    base.update(kw)
    return Request(**base)


def test_provider_defaults_and_limits():
    p = prov()
    assert p.timeout_s == 5 and p.max_bytes == 2 * 1024 * 1024 and p.tls_verify and not p.network.lan
    with pytest.raises(ValidationError):
        prov(timeout_s=16)
    with pytest.raises(ValidationError):
        prov(max_bytes=9 * 1024 * 1024)
    with pytest.raises(ValidationError):
        prov(id="Bad_Id")
    with pytest.raises(ValidationError):
        prov(extra_field=1)


def test_auth_secret_ref_rules():
    assert Auth(type="bearer", secret_ref="env:TOKEN").secret_ref == "env:TOKEN"
    for bad in ("TOKEN", "file:/x", "env:", None):
        with pytest.raises(ValidationError):
            Auth(type="bearer", secret_ref=bad)
    with pytest.raises(ValidationError):
        Auth(type="header", secret_ref="env:T")  # header_name required
    with pytest.raises(ValidationError):
        Auth(type="none", secret_ref="env:T")


@pytest.mark.parametrize("path", ["items", "http://evil/x", "//evil/x", "/a/../b", "/a/%2e%2e/b", "/a\\b"])
def test_request_path_rejected(path):
    with pytest.raises(ValidationError):
        req(path=path)


@pytest.mark.parametrize("h", ["Authorization", "cookie", "Proxy-Authorization"])
def test_request_forbidden_headers(h):
    with pytest.raises(ValidationError):
        req(headers={h: "x"})


def test_request_id_must_match_provider():
    with pytest.raises(ValidationError):
        req(id="other.items")
    with pytest.raises(ValidationError):
        req(id="items")


def test_effect_resolution_never_lowers_write():
    assert req().resolved_effect() == "read"
    assert req(method="HEAD").resolved_effect() == "read"
    assert req(method="POST").resolved_effect() == "write"
    assert req(effect="write").resolved_effect() == "write"
    assert req(method="POST", effect="read").resolved_effect() == "write"
    assert req(method="POST", effect="read", known_safe=True).resolved_effect() == "read"


def test_card_needs_exactly_one_source():
    m = dict(short="s")
    with pytest.raises(ValidationError):
        Card(id="c", title="t", meaning={"concept": "x", **m})
    with pytest.raises(ValidationError):
        Card(id="c", title="t", request="ref.items", requests=["ref.items"], meaning={"concept": "x", **m})
    assert Card(id="c", title="t", request="ref.items", meaning={"concept": "x", **m}).request_ids() == ["ref.items"]


def test_action_version_changes_with_destination_and_credential_ref():
    a = Action(id="go", request="ref.items", name="Go")
    r, p = req(method="POST"), prov()
    v = action_version(a, r, p)
    assert v == action_version(a, r, p)
    assert v != action_version(a, r, prov(base_url="http://127.0.0.1:9001"))
    assert v != action_version(a, r, prov(auth=Auth(type="bearer", secret_ref="env:T")))
    assert v != action_version(a, req(method="POST", path="/other"), p)
    assert v != action_version(a.model_copy(update={"approval": "never"}), r, p)


def test_request_provenance_and_verified_default_to_the_least_claim():
    r = req()
    assert (r.provenance, r.verified) == ("owner", False)
    assert req(provenance="provider_declared", verified=True).provenance == "provider_declared"
    with pytest.raises(ValidationError):
        req(provenance="vendor")


def test_auth_scope_none_is_unscoped_and_a_scope_must_be_ids():
    assert Auth(type="bearer", secret_ref="env:T").scope is None
    assert Auth(type="bearer", secret_ref="env:T", scope=["health"]).scope == ["health"]
    assert Auth(type="bearer", secret_ref="env:T", scope=[]).scope == []
    with pytest.raises(ValidationError):
        Auth(type="bearer", secret_ref="env:T", scope=["has space"])


def test_action_state_defaults_to_adopted_and_is_closed():
    assert Action(id="go", request="ref.items", name="Go").state == "adopted"
    assert Action(id="go", request="ref.items", name="Go", state="proposed").state == "proposed"
    with pytest.raises(ValidationError):
        Action(id="go", request="ref.items", name="Go", state="done")


def test_action_version_is_unchanged_by_the_new_fields_at_their_defaults():
    a, r = Action(id="go", request="ref.items", name="Go"), req(method="POST")
    p = prov(auth=Auth(type="bearer", secret_ref="env:T"))
    v = action_version(a, r, p)
    assert v != action_version(a.model_copy(update={"state": "proposed"}), r, p)
    assert v != action_version(a, r, prov(auth=Auth(type="bearer", secret_ref="env:T", scope=["items"])))
    assert v != action_version(a, req(method="POST", verified=True), p)


def test_action_version_at_defaults_equals_the_pre_change_hash():
    """Defaults must hash as if the new fields did not exist. The expected value is rebuilt WITHOUT them, so dropping the compat code fails."""
    import hashlib
    a, r = Action(id="go", request="ref.items", name="Go"), req(method="POST")
    p = prov(auth=Auth(type="bearer", secret_ref="env:T"))
    old = {"action": {k: v for k, v in a.model_dump(mode="json").items() if k != "state"},
           "request": {k: v for k, v in r.model_dump(mode="json").items() if k not in ("provenance", "verified")},
           "provider": {"id": p.id, "kind": p.kind, "base_url": p.base_url, "path_prefix": p.path_prefix,
                        "auth": {k: v for k, v in p.auth.model_dump(mode="json").items() if k != "scope"},
                        "network": p.network.model_dump(mode="json"), "tls_verify": p.tls_verify}}
    assert action_version(a, r, p) == hashlib.sha256(canonical_json(old).encode()).hexdigest()
