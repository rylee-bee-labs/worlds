"""OpenAPI import (T12): a skeleton only - read-only, sanitised, bounded, C1-valid.

The document is untrusted input, so these tests pin the safe behaviour: only GET/HEAD become requests,
hostile ids/paths are dropped and reported, remote refs are never resolved, an oversize document is
refused, and an auth scheme C1 does not understand is never silently ``none``.
"""
from __future__ import annotations

import pytest

from personal_world.worlds.config_store import ConfigStore
from personal_world.worlds.models import Auth, Provider, Request
from personal_world.worlds.recipes import MAX_DOC_BYTES, RecipeError, from_openapi


def _doc(paths: dict, **extra):
    base = {
        "openapi": "3.0.3",
        "info": {"title": "Pet Store", "version": "1.0.0"},
        "paths": paths,
    }
    base.update(extra)
    return base


def _doc_with_security(scheme):
    doc = _doc({"/pets": {"get": {"operationId": "listPets"}}})
    doc["components"] = {"securitySchemes": {"auth": scheme}}
    return doc


def _reasons(result):
    return " ".join(str(item.get("reason", "")) for item in result["skipped"])


# ---- the skeleton -------------------------------------------------------------------------------


def test_openapi_import_emits_provider_request_skeleton():
    doc = _doc(
        {
            "/pets": {
                "get": {
                    "operationId": "listPets",
                    "parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer"}}],
                }
            },
            "/pets/{petId}": {
                "get": {
                    "operationId": "getPet",
                    "parameters": [{"name": "petId", "in": "path", "required": True, "schema": {"type": "string"}}],
                }
            },
        },
        servers=[{"url": "https://api.petstore.example/v2"}],
    )
    result = from_openapi(doc)

    provider = Provider.model_validate(result["provider"])
    assert provider.id == "pet-store" and provider.kind == "http"
    assert provider.base_url == "https://example.invalid"  # servers[] never copied
    assert "petstore" not in result["provider"]["base_url"]
    assert provider.auth.type == "none"

    assert [r["id"] for r in result["requests"]] == ["pet-store.listpets", "pet-store.getpet"]
    for raw in result["requests"]:
        req = Request.model_validate(raw)
        assert req.method == "GET" and req.effect == "read" and req.resolved_effect() == "read"
        assert req.provider == provider.id
    # a path template is documented, not substituted
    assert "/pets/{petId}" in [r["path"] for r in result["requests"]]
    assert any("path parameter 'petId'" in note for note in result["notes"])
    assert any("synthetic placeholder" in note for note in result["notes"])


def test_a_post_path_is_not_imported_and_is_listed():
    doc = _doc(
        {
            "/pets": {
                "get": {"operationId": "listPets"},
                "post": {"operationId": "createPet"},
                "delete": {"operationId": "deletePets"},
            },
            "/pets/{petId}": {"put": {"operationId": "replacePet"}, "patch": {"operationId": "patchPet"}},
        }
    )
    result = from_openapi(doc)
    assert [r["id"] for r in result["requests"]] == ["pet-store.listpets"]
    assert all(r["method"] in ("GET", "HEAD") for r in result["requests"])
    for method in ("POST", "DELETE", "PUT", "PATCH"):
        assert any(item.get("method") == method and item.get("reason") == "write-like: needs an approved action" for item in result["skipped"])


# ---- hostile input is dropped, never trusted ----------------------------------------------------


def test_hostile_ids_and_paths_are_dropped_and_reported():
    doc = _doc(
        {
            "/pets": {"get": {"operationId": "../../etc/passwd"}},
            "/../secret": {"get": {"operationId": "sneaky"}},
            "/good": {"get": {"operationId": "goodGet"}},
        }
    )
    result = from_openapi(doc)
    assert [r["id"] for r in result["requests"]] == ["pet-store.goodget"]
    assert result["provider"]["base_url"] == "https://example.invalid"
    reasons = _reasons(result)
    assert "operationId is missing or not a safe id" in reasons
    assert "invalid request" in reasons


def test_an_invalid_path_parameter_name_drops_the_operation():
    doc = _doc({"/pets/{pet id}": {"get": {"operationId": "oddOne"}}})
    result = from_openapi(doc)
    assert result["requests"] == []
    assert "invalid path parameter name" in _reasons(result)


def test_a_remote_ref_is_skipped_and_never_resolved():
    doc = _doc(
        {
            "/pets": {
                "get": {
                    "operationId": "listPets",
                    "parameters": [{"$ref": "https://evil.example/schemas.yaml#/components/parameters/Limit"}],
                }
            }
        }
    )
    result = from_openapi(doc)
    # the operation still imports; only the unresolvable parameter is dropped
    assert [r["id"] for r in result["requests"]] == ["pet-store.listpets"]
    assert any(item.get("reason") == "external $ref not resolved" for item in result["skipped"])


def test_a_remote_path_item_ref_skips_the_whole_path():
    doc = _doc({"/pets": {"$ref": "https://evil.example/paths.yaml#/pets"}})
    result = from_openapi(doc)
    assert result["requests"] == []
    assert any(item.get("reason") == "external $ref not resolved" for item in result["skipped"])


def test_a_local_ref_is_followed():
    doc = _doc(
        {"/pets": {"get": {"operationId": "listPets", "parameters": [{"$ref": "#/components/parameters/Limit"}]}}}
    )
    doc["components"] = {"parameters": {"Limit": {"name": "limit", "in": "query"}}}
    result = from_openapi(doc)
    assert [r["id"] for r in result["requests"]] == ["pet-store.listpets"]
    assert any("query parameter 'limit'" in note for note in result["notes"])


def test_an_oversize_document_is_refused_with_a_plain_error():
    doc = _doc({"/x": {"get": {"operationId": "x", "description": "a" * (MAX_DOC_BYTES + 1)}}})
    with pytest.raises(RecipeError) as excinfo:
        from_openapi(doc)
    assert "too large" in str(excinfo.value)


def test_a_deeply_nested_document_is_refused():
    node: dict = {}
    cursor = node
    for _ in range(100):
        child: dict = {}
        cursor["deep"] = child
        cursor = child
    with pytest.raises(RecipeError):
        from_openapi(_doc({"/x": {"get": node}}))


def test_a_swagger_2_document_is_refused():
    with pytest.raises(RecipeError):
        from_openapi({"swagger": "2.0", "info": {"title": "Old"}, "paths": {}})


# ---- auth mapping -------------------------------------------------------------------------------


def test_bearer_api_key_header_and_basic_map_to_c1_auth():
    bearer = from_openapi(_doc_with_security({"type": "http", "scheme": "bearer"}))
    Auth.model_validate(bearer["provider"]["auth"])
    assert bearer["provider"]["auth"] == {"type": "bearer", "secret_ref": "env:PET_STORE_AUTH"}
    assert bearer["needs_auth"] == "configured"

    header = from_openapi(_doc_with_security({"type": "apiKey", "in": "header", "name": "X-Api-Key"}))
    Auth.model_validate(header["provider"]["auth"])
    assert header["provider"]["auth"] == {
        "type": "header",
        "header_name": "X-Api-Key",
        "secret_ref": "env:PET_STORE_AUTH",
    }

    basic = from_openapi(_doc_with_security({"type": "http", "scheme": "basic"}))
    Auth.model_validate(basic["provider"]["auth"])
    assert basic["provider"]["auth"]["type"] == "basic"


@pytest.mark.parametrize(
    "scheme",
    [
        {"type": "oauth2", "flows": {}},
        {"type": "openIdConnect", "openIdConnectUrl": "https://issuer.example/.well-known"},
        {"type": "apiKey", "in": "cookie", "name": "sid"},
        {"type": "apiKey", "in": "query", "name": "key"},
        {"type": "apiKey", "in": "header", "name": "Authorization"},  # forbidden credential header
    ],
)
def test_an_unknown_scheme_is_a_todo_and_marks_needs_auth_unknown(scheme):
    result = from_openapi(_doc_with_security(scheme))
    assert result["needs_auth"] == "unknown"
    assert result["provider"]["auth"]["type"] == "none"  # present but explicitly marked unknown
    assert any("TODO" in note and "needs_auth unknown" in note for note in result["notes"])
    assert "PET_STORE_AUTH" not in str(result["provider"])  # no secret value is ever emitted


# ---- the output is real C1 config ---------------------------------------------------------------


def test_the_output_validates_and_installs_under_c1(tmp_path):
    doc = _doc(
        {
            "/pets": {"get": {"operationId": "listPets"}},
            "/pets/{petId}": {"get": {"operationId": "getPet"}},
            "/pets/filters": {"get": {"operationId": "filters"}},
        },
        components={"securitySchemes": {"auth": {"type": "http", "scheme": "bearer"}}},
    )
    result = from_openapi(doc)

    provider = Provider.model_validate(result["provider"])
    requests = [Request.model_validate(raw) for raw in result["requests"]]
    assert len(requests) == 3

    store = ConfigStore(tmp_path / "cfg")
    store.save("provider", provider)
    for request in requests:
        store.save("request", request)
    assert store.errors() == []
    assert store.get("provider", provider.id) is not None
    for request in requests:
        assert store.get("request", request.id) is not None
